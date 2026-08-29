import { SIGNAL_TYPE_MAP } from '../events/event-schema.js';

export class MockBackendAdapter {
  async sendSignal() { return { success: true, mode: 'mock' }; }
  async sendEvents(events) {
    await new Promise(r => setTimeout(r, 250));
    console.info('[Kawach mock backend]', events);
    return { success: true, received: events.length };
  }
  async pair() { return { success: false, error: 'Mock backend cannot pair' }; }
  async getMonitoringStatus() { return { success: true, monitoring_status: 'on' }; }
  async healthCheck() { return { success: true, mode: 'mock' }; }
}

// Picks the (url, content) pair to send for a given internal event,
// respecting the urlMode privacy setting (domain-only vs full URL) the
// same way the rest of the extension already does.
function contentAndUrlFor(event) {
  const d = event.data || {};
  switch (event.eventType) {
    case 'page_visit':
      return { content: d.url || d.domain || '', url: d.url || null };
    case 'search':
      return { content: d.query || '', url: d.pageUrl || null };
    case 'chat_message':
      return { content: d.text || '', url: d.pageUrl || null };
    case 'page_text':
      return { content: d.text || '', url: d.pageUrl || null };
    default:
      return { content: '', url: null };
  }
}

export class HttpBackendAdapter {
  constructor({ baseUrl, signalsPath, eventsPath, childId, sessionId }) {
    this.baseUrl = String(baseUrl || '').replace(/\/$/, '');
    this.signalsPath = signalsPath || '/api/signals';
    this.eventsPath = eventsPath || '/api/events';
    this.childId = childId || '';
    this.sessionId = sessionId || '';
  }

  async _post(path, body) {
    if (!this.baseUrl) return { success: false, error: 'Backend URL is not configured' };
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { success: false, error: json.detail || `Backend returned ${response.status}` };
    }
    return { success: true, ...json };
  }

  // Primary path: one call per signal, matching the spec's exact
  // payload shape (child_id, session_id, signal_type, content, url,
  // timestamp). Only called for event types that map to a signal_type
  // — see SIGNAL_TYPE_MAP in events/event-schema.js.
  async sendSignal(event) {
    const signalType = SIGNAL_TYPE_MAP[event.eventType];
    if (!signalType) return { success: false, error: `No signal_type mapping for ${event.eventType}` };

    const { content, url } = contentAndUrlFor(event);
    if (!content) return { success: false, error: 'Empty content, nothing to send' };

    return this._post(this.signalsPath, {
      child_id: this.childId,
      session_id: this.sessionId,
      signal_type: signalType,
      content,
      url,
      timestamp: event.timestamp
    });
  }

  // Legacy batch path, kept for event types /api/signals doesn't cover
  // yet (file_upload, file_download, form_submission, page_metadata) so
  // nothing collected locally is silently dropped.
  async sendEvents(events) {
    if (!this.baseUrl) return { success: false, error: 'Backend URL is not configured' };
    const response = await fetch(`${this.baseUrl}${this.eventsPath}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ child_id: this.childId, events })
    });
    if (!response.ok) throw new Error(`Backend returned ${response.status}`);
    return { success: true, ...(await response.json().catch(() => ({}))) };
  }

  // POST /api/auth/pair — exchanges a one-time pairing code (shown on
  // the parent dashboard) for the child_id this extension should store.
  async pair(pairingCode) {
    return this._post('/api/auth/pair', { pairing_code: pairingCode });
  }

  // GET /api/monitoring/status/{child_id} — open, read-only, no auth.
  // Extension polls this so a parent toggling monitoring off from the
  // dashboard actually takes effect here, not just locally.
  async getMonitoringStatus(childId) {
    if (!this.baseUrl || !childId) return { success: false, error: 'Backend URL or child_id missing' };
    try {
      const response = await fetch(`${this.baseUrl}/api/monitoring/status/${encodeURIComponent(childId)}`);
      if (!response.ok) return { success: false, error: `Backend returned ${response.status}` };
      const json = await response.json();
      return { success: true, ...json };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }

  async healthCheck() {
    if (!this.baseUrl) return { success: false, error: 'Backend URL is not configured' };
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return { success: response.ok };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }
}
