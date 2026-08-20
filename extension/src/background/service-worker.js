import { EVENT_TYPES, SIGNAL_TYPE_MAP, makeEvent } from '../events/event-schema.js';
import { validateEvent } from '../events/event-validator.js';
import { getSettings, saveSettings } from '../privacy/settings.js';
import { shouldIgnore, hostnameFromUrl } from '../privacy/domain-filter.js';
import { addEvent, getEvents, getPendingEvents, clearAllEvents, removePending } from '../storage/store.js';
import { HttpBackendAdapter } from '../transport/backend-adapter.js';
import { detectSearch } from '../collectors/search-collector.js';
import { getSessionId } from '../session/session.js';

const STATUS_POLL_ALARM = 'kawach-status-poll';
const STATUS_POLL_MINUTES = 5;

chrome.runtime.onInstalled.addListener(async () => {
  const s = await chrome.storage.local.get('settings');
  if (!s.settings) {
    const { DEFAULT_SETTINGS } = await import('../privacy/defaults.js');
    await chrome.storage.local.set({ settings: DEFAULT_SETTINGS });
  }
  chrome.alarms.create(STATUS_POLL_ALARM, { periodInMinutes: STATUS_POLL_MINUTES });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(STATUS_POLL_ALARM, { periodInMinutes: STATUS_POLL_MINUTES });
});

async function currentSettings() { return getSettings(); }

function adapterFor(settings, sessionId) {
  return new HttpBackendAdapter({
    baseUrl: settings.backendBaseUrl,
    signalsPath: settings.backendSignalsPath,
    eventsPath: settings.backendEventsPath,
    childId: settings.childId,
    sessionId
  });
}

async function record(event, sourceUrl = '') {
  const settings = await currentSettings();
  if (!settings.monitoringEnabled) return { ignored: true };
  const candidateUrl = sourceUrl || event.data?.url || event.data?.pageUrl || event.data?.sourceUrl || '';
  if (!candidateUrl || shouldIgnore(candidateUrl, settings)) return { ignored: true };
  const check = validateEvent(event);
  if (!check.valid) {
    console.warn('Rejected event', check.errors);
    return { ignored: true, errors: check.errors };
  }
  await addEvent(event);
  if (settings.backendEnabled) syncNow(settings).catch(() => {});
  return { saved: true, event };
}

chrome.webNavigation.onCommitted.addListener(async details => {
  if (details.frameId !== 0) return;
  const settings = await currentSettings();
  if (!settings.collectVisits || shouldIgnore(details.url, settings)) return;
  const data = { domain: hostnameFromUrl(details.url), pageTitle: '', url: settings.urlMode === 'full' ? details.url : undefined };
  await record(makeEvent(EVENT_TYPES.PAGE_VISIT, data), details.url);
  if (settings.collectSearches) {
    const searchEvent = detectSearch(details.url);
    if (searchEvent && !shouldIgnore(details.url, settings)) await record(searchEvent, details.url);
  }
  if (settings.collectPageMetadata) {
    chrome.tabs.get(details.tabId).then(tab => {
      const metadata = makeEvent(EVENT_TYPES.PAGE_METADATA, {
        url: settings.urlMode === 'full' ? details.url : undefined,
        domain: hostnameFromUrl(details.url),
        pageTitle: tab?.title || ''
      });
      return record(metadata, details.url);
    }).catch(() => {});
  }
});

chrome.downloads.onCreated.addListener(async item => {
  const settings = await currentSettings();
  if (!settings.collectDownloads) return;
  if (shouldIgnore(item.url || '', settings)) return;
  await record(makeEvent(EVENT_TYPES.FILE_DOWNLOAD, {
    fileName: item.filename?.split(/[/\\]/).pop() || '',
    fileExtension: (item.filename || '').includes('.') ? `.${item.filename.split('.').pop()}` : '',
    mimeType: item.mime || '',
    size: item.fileSize ?? null,
    sourceUrl: item.url || '',
    referrer: item.referrer || ''
  }), item.url || '');
});

chrome.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name !== STATUS_POLL_ALARM) return;
  await pollMonitoringStatus();
});

async function pollMonitoringStatus() {
  const settings = await currentSettings();
  if (!settings.backendEnabled || !settings.childId) return;
  const adapter = adapterFor(settings, '');
  const result = await adapter.getMonitoringStatus(settings.childId);
  if (!result.success || !result.monitoring_status) return;
  const backendOn = result.monitoring_status === 'on';
  if (backendOn !== settings.monitoringEnabled) {
    // A parent toggled monitoring from the dashboard — reflect that
    // here so it actually takes effect, not just displays differently.
    await saveSettings({ monitoringEnabled: backendOn });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const settings = await currentSettings();
    if (message?.type === 'GET_STATUS') {
      const events = await getEvents(10);
      const pending = await getPendingEvents();
      sendResponse({ ok: true, settings, recentEvents: events, pendingCount: pending.length });
      return;
    }
    if (message?.type === 'RECORD_EVENT') {
      const result = await record(message.event);
      sendResponse({ ok: true, result });
      return;
    }
    if (message?.type === 'CLEAR_EVENTS') {
      await clearAllEvents();
      sendResponse({ ok: true });
      return;
    }
    if (message?.type === 'GET_EVENTS') {
      sendResponse({ ok: true, events: await getEvents(message.limit || 200) });
      return;
    }
    if (message?.type === 'SYNC_NOW') {
      sendResponse({ ok: true, result: await syncNow(settings) });
      return;
    }
    if (message?.type === 'PAIR_DEVICE') {
      sendResponse({ ok: true, result: await pairDevice(settings, message.pairingCode) });
      return;
    }
    if (message?.type === 'CHECK_MONITORING_STATUS') {
      await pollMonitoringStatus();
      sendResponse({ ok: true, settings: await currentSettings() });
      return;
    }
    sendResponse({ ok: false, error: 'Unknown message' });
  })().catch(err => sendResponse({ ok: false, error: err.message }));
  return true;
});

async function pairDevice(settings, pairingCode) {
  if (!settings.backendBaseUrl) return { success: false, error: 'Backend URL is not configured' };
  const adapter = adapterFor(settings, '');
  const result = await adapter.pair(pairingCode);
  if (result.success && result.child_id) {
    await saveSettings({ childId: result.child_id });
  }
  return result;
}

async function syncNow(settings) {
  if (!settings.backendEnabled) return { success: false, error: 'Backend disabled' };
  const pending = await getPendingEvents();
  if (!pending.length) return { success: true, received: 0 };

  const sessionId = await getSessionId();
  const adapter = adapterFor(settings, sessionId);

  // Split into signal-mappable events (sent one-by-one to /api/signals,
  // the spec's primary contract) and everything else (sent as a batch
  // to the legacy /api/events endpoint so nothing is dropped).
  const signalEvents = pending.filter(e => SIGNAL_TYPE_MAP[e.eventType]);
  const otherEvents = pending.filter(e => !SIGNAL_TYPE_MAP[e.eventType]);

  const sentIds = [];
  let signalFailures = 0;

  for (const event of signalEvents) {
    try {
      const result = await adapter.sendSignal(event);
      if (result.success) sentIds.push(event.eventId);
      else signalFailures++;
    } catch {
      signalFailures++;
    }
  }

  let batchResult = { success: true, received: 0 };
  if (otherEvents.length) {
    try {
      batchResult = await adapter.sendEvents(otherEvents);
      if (batchResult.success) sentIds.push(...otherEvents.map(e => e.eventId));
    } catch (e) {
      batchResult = { success: false, error: e.message };
    }
  }

  if (sentIds.length) await removePending(sentIds);

  return {
    success: signalFailures === 0 && batchResult.success,
    received: sentIds.length,
    signalsSent: signalEvents.length - signalFailures,
    signalFailures,
    batch: batchResult
  };
}
