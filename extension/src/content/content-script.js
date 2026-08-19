const EVENT_TYPES = {
  FILE_UPLOAD: 'file_upload',
  FORM_SUBMISSION: 'form_submission'
};
const SENSITIVE = /pass(word)?|pwd|secret|token|cvv|cvc|card|credit|otp|pin/i;
let monitoringEnabled = true;

chrome.storage.local.get('settings').then(({ settings }) => {
  monitoringEnabled = settings?.monitoringEnabled !== false;
}).catch(() => {});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.settings) monitoringEnabled = changes.settings.newValue?.monitoringEnabled !== false;
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
