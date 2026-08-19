const MAX_STRING = 5000;
const ALLOWED_TYPES = new Set([
  'page_visit','search','file_upload','form_submission','file_download','page_metadata'
]);

export function validateEvent(event) {
  const errors = [];
  if (!event || typeof event !== 'object') errors.push('Event must be an object');
  if (!event?.eventId) errors.push('Missing eventId');
  if (!ALLOWED_TYPES.has(event?.eventType)) errors.push('Unsupported eventType');
  if (!event?.timestamp || Number.isNaN(Date.parse(event.timestamp))) errors.push('Invalid timestamp');
  if (JSON.stringify(event).length > MAX_STRING * 10) errors.push('Event payload too large');
  return { valid: errors.length === 0, errors };
}
