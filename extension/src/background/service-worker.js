import { EVENT_TYPES, makeEvent } from '../events/event-schema.js';
import { validateEvent } from '../events/event-validator.js';
import { getSettings } from '../privacy/settings.js';
import { shouldIgnore, hostnameFromUrl } from '../privacy/domain-filter.js';
import { addEvent, getEvents, getPendingEvents, clearAllEvents, removePending } from '../storage/store.js';
import { HttpBackendAdapter } from '../transport/backend-adapter.js';
import { detectSearch } from '../collectors/search-collector.js';
import { DEFAULT_SETTINGS } from '../privacy/defaults.js';

chrome.runtime.onInstalled.addListener(async () => {
  const s = await chrome.storage.local.get('settings');
  if (!s.settings) {
    await chrome.storage.local.set({ settings: DEFAULT_SETTINGS });
  }
});

async function currentSettings() { return getSettings(); }

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
    sendResponse({ ok: false, error: 'Unknown message' });
  })().catch(err => sendResponse({ ok: false, error: err.message }));
  return true;
});

async function syncNow(settings) {
  if (!settings.backendEnabled) return { success: false, error: 'Backend disabled' };
  const pending = await getPendingEvents();
  if (!pending.length) return { success: true, received: 0 };
  const adapter = new HttpBackendAdapter({ baseUrl: settings.backendBaseUrl, eventsPath: settings.backendEventsPath, childId: settings.childId });
  const result = await adapter.sendEvents(pending);
  if (result.success) await removePending(pending.map(e => e.eventId));
  return result;
}