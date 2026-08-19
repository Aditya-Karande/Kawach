const EVENT_KEY = 'localEvents';
const QUEUE_KEY = 'pendingEvents';

export async function addEvent(event) {
  const { localEvents = [], pendingEvents = [] } = await chrome.storage.local.get([EVENT_KEY, QUEUE_KEY]);
  const nextEvents = [event, ...localEvents].slice(0, 2000);
  const nextQueue = [...pendingEvents, event].slice(-1000);
  await chrome.storage.local.set({ [EVENT_KEY]: nextEvents, [QUEUE_KEY]: nextQueue });
}

export async function getEvents(limit = 200) {
  const { localEvents = [] } = await chrome.storage.local.get(EVENT_KEY);
  return localEvents.slice(0, limit);
}

export async function getPendingEvents() {
  const { pendingEvents = [] } = await chrome.storage.local.get(QUEUE_KEY);
  return pendingEvents;
}

export async function clearAllEvents() {
  await chrome.storage.local.set({ [EVENT_KEY]: [], [QUEUE_KEY]: [] });
}

export async function removePending(eventIds) {
  const ids = new Set(eventIds);
  const { pendingEvents = [] } = await chrome.storage.local.get(QUEUE_KEY);
  await chrome.storage.local.set({ [QUEUE_KEY]: pendingEvents.filter(e => !ids.has(e.eventId)) });
}
