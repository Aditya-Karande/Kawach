import { EVENT_TYPES, makeEvent } from '../events/event-schema.js';

const sensitiveNames = /pass(word)?|pwd|secret|token|cvv|cvc|card|credit|otp|pin/i;

export function inspectForm(form) {
  const elements = [...form.elements].filter(el => el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement);
  const fields = elements.map(el => ({
    name: (el.getAttribute('name') || el.id || el.getAttribute('aria-label') || '').slice(0, 120),
    type: el.type || el.tagName.toLowerCase()
  })).filter(f => !sensitiveNames.test(f.name) && f.type !== 'password');

  return makeEvent(EVENT_TYPES.FORM_SUBMISSION, {
    pageUrl: location.href,
    domain: location.hostname,
    pageTitle: document.title,
    method: String(form.method || 'get').toUpperCase(),
    actionDomain: (() => { try { return new URL(form.action || location.href).hostname; } catch { return ''; } })(),
    fieldCount: fields.length,
    fieldTypes: [...new Set(fields.map(f => f.type))].slice(0, 20),
    detection: 'form-submit'
  });
}
