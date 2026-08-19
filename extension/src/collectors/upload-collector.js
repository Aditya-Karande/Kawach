import { EVENT_TYPES, makeEvent } from '../events/event-schema.js';

function sanitizeName(name) {
  return String(name || '').split(/[/\\]/).pop().slice(0, 255);
}

function getExtension(name) {
  const clean = sanitizeName(name);
  const i = clean.lastIndexOf('.');
  return i > -1 ? clean.slice(i).toLowerCase() : '';
}

export function inspectFileInput(input) {
  if (!(input instanceof HTMLInputElement) || input.type !== 'file' || !input.files?.length) return [];
  return [...input.files].map(file => makeEvent(EVENT_TYPES.FILE_UPLOAD, {
    pageUrl: location.href,
    domain: location.hostname,
    pageTitle: document.title,
    fileName: sanitizeName(file.name),
    fileExtension: getExtension(file.name),
    mimeType: file.type || 'application/octet-stream',
    size: Number.isFinite(file.size) ? file.size : null,
    lastModified: file.lastModified ? new Date(file.lastModified).toISOString() : null,
    detection: 'file-input-selection'
  }));
}
