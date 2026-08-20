export const DEFAULT_SETTINGS = {
  monitoringEnabled: true,
  collectVisits: true,
  collectSearches: true,
  collectUploads: true,
  collectDownloads: true,
  collectForms: true,
  collectPageMetadata: true,
  collectPageText: false,
  collectChatMessages: true,
  pageTextMaxChars: 2000,
  urlMode: 'domain',
  protectSensitiveSites: true,
  excludedDomains: [],
  backendEnabled: false,
  backendBaseUrl: '',
  // Primary contract per spec Section 4.1 — one call per signal.
  backendSignalsPath: '/api/signals',
  // Legacy batch endpoint, still used for event types /api/signals
  // doesn't cover (uploads, downloads, forms, page metadata).
  backendEventsPath: '/api/events',
  childId: 'child_001'
};
