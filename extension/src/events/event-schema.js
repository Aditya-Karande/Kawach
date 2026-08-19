export const EVENT_TYPES = Object.freeze({
  PAGE_VISIT: 'page_visit',
  SEARCH: 'search',
  FILE_UPLOAD: 'file_upload',
  FORM_SUBMISSION: 'form_submission',
  FILE_DOWNLOAD: 'file_download',
  PAGE_METADATA: 'page_metadata'
});

export function makeEvent(eventType, data = {}) {
  return {
    eventId: crypto.randomUUID(),
    eventType,
    timestamp: new Date().toISOString(),
    data
  };
}
