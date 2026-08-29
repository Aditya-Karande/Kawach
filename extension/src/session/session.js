// The backend sums signal weights over a rolling window scoped by
// session_id, not just child_id (spec Section 5) — so the extension
// needs to generate and persist one. We use chrome.storage.session
// (cleared automatically when the browser fully closes) and rotate it
// after a period of inactivity, mirroring the backend's own 30-minute
// scoring window so a session boundary here roughly matches a session
// boundary there.

const SESSION_KEY = 'kawachSession';
const INACTIVITY_RESET_MINUTES = 30;

function newSessionId() {
  return `sess_${crypto.randomUUID()}`;
}

export async function getSessionId() {
  const now = Date.now();
  const { [SESSION_KEY]: session } = await chrome.storage.session.get(SESSION_KEY);

  if (session && (now - session.lastActivity) < INACTIVITY_RESET_MINUTES * 60 * 1000) {
    await chrome.storage.session.set({ [SESSION_KEY]: { ...session, lastActivity: now } });
    return session.id;
  }

  const fresh = { id: newSessionId(), lastActivity: now };
  await chrome.storage.session.set({ [SESSION_KEY]: fresh });
  return fresh.id;
}
