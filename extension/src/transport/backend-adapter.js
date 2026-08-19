export class MockBackendAdapter {
  async sendEvents(events) {
    await new Promise(r => setTimeout(r, 250));
    console.info('[Kawach mock backend]', events);
    return { success: true, received: events.length };
  }
  async healthCheck() { return { success: true, mode: 'mock' }; }
}

export class HttpBackendAdapter {
  constructor({ baseUrl, eventsPath, childId }) {
    this.baseUrl = String(baseUrl || '').replace(/\/$/, '');
    this.eventsPath = eventsPath || '/api/events';
    this.childId = childId || '';
  }

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

  async healthCheck() {
    if (!this.baseUrl) return { success: false, error: 'Backend URL is not configured' };
    const response = await fetch(this.baseUrl, { method: 'HEAD' });
    return { success: response.ok };
  }
}
