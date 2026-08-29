export const EVENT_TYPES = Object.freeze({
  PAGE_VISIT: 'page_visit',
  SEARCH: 'search',
  FILE_UPLOAD: 'file_upload',
  FORM_SUBMISSION: 'form_submission',
  FILE_DOWNLOAD: 'file_download',
  PAGE_METADATA: 'page_metadata',
  CHAT_MESSAGE: 'chat_message',
  PAGE_TEXT: 'page_text'
});

// Maps our internal eventType to the backend's signal_type contract
// (spec Section 4.1 — search_query | url_visit | page_text | chat_text).
// Types with no entry here (file_upload, file_download, form_submission,
// page_metadata) aren't part of the backend's weighted-scoring signal
// set, and are only sent via the legacy /api/events batch endpoint so
// they still show up in the local dashboard / are available for future
// backend support.
export const SIGNAL_TYPE_MAP = Object.freeze({
  page_visit: 'url_visit',
  search: 'search_query',
  chat_message: 'chat_text',
  page_text: 'page_text'
});

export function makeEvent(eventType, data = {}) {
  return {
    eventId: crypto.randomUUID(),
    eventType,
    timestamp: new Date().toISOString(),
    data
  };
}
