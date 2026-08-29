// Chat message detection is inherently best-effort — messaging web apps
// don't expose a standard "this is a chat box" API, and their DOM/class
// names change often. Rather than hardcoding brittle per-site CSS
// selectors that break on the next redesign, this uses two independent
// signals and treats either one as enough to call something a chat
// input:
//
//   1. The element's aria-label/placeholder/name text looks like a
//      message box ("Type a message", "Message #general", etc).
//   2. The page's hostname is a known messaging platform, in which case
//      any contenteditable/textarea near a "Send"-labelled control is
//      treated as a chat input even without a matching label.
//
// It only reads text the user already typed, right as they send it
// (Enter, or clicking something that looks like a send button) — it
// never reads the DOM for text that wasn't actively being sent.

const MESSAGE_LABEL_PATTERN = /type an?( new)? message|message\s*#|write a message|send a message|new message/i;

// Hosts where we treat message-shaped inputs more permissively, since
// these are dedicated chat products where a text box near a send
// control is almost certainly a chat message.
const KNOWN_CHAT_HOSTS = [
  'web.whatsapp.com',
  'messenger.com',
  'www.messenger.com',
  'discord.com',
  'web.telegram.org',
  'www.instagram.com',
  'web.snapchat.com',
  'teams.microsoft.com',
  'slack.com'
];

function isKnownChatHost(hostname) {
  return KNOWN_CHAT_HOSTS.some(h => hostname === h || hostname.endsWith(`.${h}`));
}

function elementLabel(el) {
  return [
    el.getAttribute?.('aria-label'),
    el.getAttribute?.('placeholder'),
    el.getAttribute?.('data-placeholder'),
    el.getAttribute?.('name'),
    el.title
  ].filter(Boolean).join(' ');
}

function looksLikeChatInput(el) {
  if (!el) return false;
  const isEditable =
    (el instanceof HTMLTextAreaElement) ||
    (el instanceof HTMLInputElement && (el.type === 'text' || el.type === 'search')) ||
    el.isContentEditable;
  if (!isEditable) return false;

  if (MESSAGE_LABEL_PATTERN.test(elementLabel(el))) return true;
  if (isKnownChatHost(location.hostname)) return true;

  return false;
}

function readValue(el) {
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) return el.value;
  return el.innerText ?? el.textContent ?? '';
}

// Returns the chat text if `el` is a chat-like input worth recording,
// or null otherwise. Caller is responsible for trimming/length limits
// and for actually sending the event.
export function detectChatSend(el) {
  if (!looksLikeChatInput(el)) return null;
  const text = readValue(el).trim();
  if (!text) return null;
  return text;
}

function findNearbyEditable(button) {
  // Look for a contenteditable/textarea/text-input sibling in the same
  // form/container as a "Send"-looking button.
  const container = button.closest('form, [role="form"], [class*="compose"], [class*="footer"]') || button.parentElement;
  if (!container) return null;
  return container.querySelector('textarea, [contenteditable="true"], input[type="text"], input[type="search"]');
}

export function looksLikeSendButton(el) {
  const btn = el.closest?.('button, [role="button"]');
  if (!btn) return null;
  const label = elementLabel(btn) + ' ' + (btn.innerText || '');
  if (!/send/i.test(label)) return null;
  return findNearbyEditable(btn);
}

// --- Incoming message detection ---
// Everything above only ever captures what the CHILD types and sends.
// That misses the highest-signal content in a real grooming/scam
// conversation — the other party's messages ("what's your real name",
// "let's talk on a different app") never pass through the child's own
// input box. This section watches for new message-shaped elements
// appearing near a chat input and reports their text too, so both
// sides of a conversation are covered, not just the child's replies.
//
// Deliberately scoped, not a whole-page scraper: it only starts once a
// real chat input has been found on the page, and only observes the
// smallest scrollable ancestor of that input (a reasonable, generic
// proxy for "the message list" across most chat UIs) rather than the
// entire document.

export function findChatInputOnPage() {
  const candidates = document.querySelectorAll(
    'textarea, [contenteditable="true"], input[type="text"], input[type="search"]'
  );
  for (const el of candidates) {
    if (looksLikeChatInput(el)) return el;
  }
  return null;
}

function findMessageContainer(inputEl) {
  let el = inputEl;
  for (let i = 0; i < 8 && el; i++) {
    el = el.parentElement;
    if (!el) break;
    const style = getComputedStyle(el);
    const scrollable = /(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 40;
    if (scrollable) return el;
  }
  // Couldn't find a plausible message-list container — better to skip
  // incoming detection on this page than fall back to observing
  // something as broad as document.body.
  return null;
}

const MIN_INCOMING_CHARS = 2;
const MAX_INCOMING_CHARS = 2000; // longer than this is more likely a re-render than a single message

// Starts watching `inputEl`'s nearest message-list container for newly
// added elements and reports their text via onMessage(text). Returns
// the MutationObserver (so the caller can disconnect it later) or null
// if no plausible container was found.
export function observeIncomingMessages(inputEl, onMessage) {
  const container = findMessageContainer(inputEl);
  if (!container) return null;

  const seen = new WeakSet();
  const observer = new MutationObserver(mutations => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (!(node instanceof HTMLElement) || seen.has(node)) continue;
        seen.add(node);
        const text = (node.innerText ?? node.textContent ?? '').trim();
        if (text.length < MIN_INCOMING_CHARS || text.length > MAX_INCOMING_CHARS) continue;
        onMessage(text);
      }
    }
  });

  observer.observe(container, { childList: true, subtree: true });
  return observer;
}
