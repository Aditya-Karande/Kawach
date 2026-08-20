const EVENT_TYPES = {
  FILE_UPLOAD: 'file_upload',
  FORM_SUBMISSION: 'form_submission',
  CHAT_MESSAGE: 'chat_message',
  PAGE_TEXT: 'page_text'
};
const SENSITIVE = /pass(word)?|pwd|secret|token|cvv|cvc|card|credit|otp|pin/i;
let monitoringEnabled = true;
let chatMonitoringEnabled = true;

chrome.storage.local.get('settings').then(({ settings }) => {
  monitoringEnabled = settings?.monitoringEnabled !== false;
  chatMonitoringEnabled = settings?.collectChatMessages !== false;
  pageTextSettings = {
    collectPageText: !!settings?.collectPageText,
    pageTextMaxChars: settings?.pageTextMaxChars || 2000
  };
}).catch(() => {});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.settings) return;
  const s = changes.settings.newValue || {};
  monitoringEnabled = s.monitoringEnabled !== false;
  chatMonitoringEnabled = s.collectChatMessages !== false;
  pageTextSettings = {
    collectPageText: !!s.collectPageText,
    pageTextMaxChars: s.pageTextMaxChars || 2000
  };
});

function makeEvent(eventType, data) {
  return { eventId: crypto.randomUUID(), eventType, timestamp: new Date().toISOString(), data };
}
function cleanName(name) { return String(name || '').split(/[/\\]/).pop().slice(0, 255); }
function ext(name) {
  const n = cleanName(name); const i = n.lastIndexOf('.'); return i > -1 ? n.slice(i).toLowerCase() : '';
}
function send(event) {
  if (!monitoringEnabled) return;
  chrome.runtime.sendMessage({ type: 'RECORD_EVENT', event }).catch(() => {});
}

document.addEventListener('change', event => {
  if (!monitoringEnabled) return;
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.type !== 'file' || !input.files?.length) return;
  for (const file of input.files) {
    send(makeEvent(EVENT_TYPES.FILE_UPLOAD, {
      pageUrl: location.href,
      domain: location.hostname,
      pageTitle: document.title,
      fileName: cleanName(file.name),
      fileExtension: ext(file.name),
      mimeType: file.type || 'application/octet-stream',
      size: Number.isFinite(file.size) ? file.size : null,
      lastModified: file.lastModified ? new Date(file.lastModified).toISOString() : null,
      detection: 'file-input-selection'
    }));
  }
}, true);

document.addEventListener('submit', event => {
  if (!monitoringEnabled) return;
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  const elements = [...form.elements].filter(el => el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement);
  const safeFields = elements.map(el => ({
    name: (el.getAttribute('name') || el.id || el.getAttribute('aria-label') || '').slice(0, 120),
    type: el.type || el.tagName.toLowerCase()
  })).filter(f => !SENSITIVE.test(f.name) && f.type !== 'password');
  send(makeEvent(EVENT_TYPES.FORM_SUBMISSION, {
    pageUrl: location.href,
    domain: location.hostname,
    pageTitle: document.title,
    method: String(form.method || 'get').toUpperCase(),
    actionDomain: (() => { try { return new URL(form.action || location.href).hostname; } catch { return ''; } })(),
    fieldCount: safeFields.length,
    fieldTypes: [...new Set(safeFields.map(f => f.type))].slice(0, 20),
    detection: 'form-submit'
  }));
}, true);

// --- chat message detection ---
// Best-effort: fires on Enter-to-send in a chat-shaped input, or a click
// on something that looks like a Send button next to one. See
// collectors/chat-collector.js for the (imperfect, heuristic) matching
// logic and its limitations.

import('../collectors/chat-collector.js').then(({ detectChatSend, looksLikeSendButton }) => {
  const MAX_CHAT_CHARS = 4000;

  function sendChat(text) {
    if (!chatMonitoringEnabled || !monitoringEnabled) return;
    const trimmed = text.slice(0, MAX_CHAT_CHARS);
    send(makeEvent(EVENT_TYPES.CHAT_MESSAGE, {
      pageUrl: location.href,
      domain: location.hostname,
      pageTitle: document.title,
      text: trimmed,
      detection: 'chat-input'
    }));
  }

  document.addEventListener('keydown', event => {
    if (!chatMonitoringEnabled || !monitoringEnabled) return;
    if (event.key !== 'Enter' || event.shiftKey) return;
    const text = detectChatSend(event.target);
    if (text) sendChat(text);
  }, true);

  document.addEventListener('click', event => {
    if (!chatMonitoringEnabled || !monitoringEnabled) return;
    const editable = looksLikeSendButton(event.target);
    if (!editable) return;
    const text = (editable.value ?? editable.innerText ?? '').trim();
    if (text) sendChat(text);
  }, true);
}).catch(() => {});

// --- visible page text (off by default — see options: "Visible text analysis") ---

let pageTextSettings = { collectPageText: false, pageTextMaxChars: 2000 };

function extractVisibleText() {
  // Cheap approximation of "visible text": body innerText, trimmed to
  // the configured character budget. Not sent unless the parent has
  // explicitly turned this on in options.
  const raw = document.body?.innerText || '';
  return raw.replace(/\s+/g, ' ').trim().slice(0, pageTextSettings.pageTextMaxChars);
}

function maybeSendPageText() {
  if (!monitoringEnabled || !pageTextSettings.collectPageText) return;
  const text = extractVisibleText();
  if (!text) return;
  send(makeEvent(EVENT_TYPES.PAGE_TEXT, {
    pageUrl: location.href,
    domain: location.hostname,
    pageTitle: document.title,
    text,
    detection: 'page-text'
  }));
}

// Give dynamic pages a moment to render before reading their text.
if (document.readyState === 'complete') {
  setTimeout(maybeSendPageText, 1200);
} else {
  window.addEventListener('load', () => setTimeout(maybeSendPageText, 1200));
}
