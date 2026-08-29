# Kawach / SafeSignal Browser Activity Monitor

A Manifest V3 Chrome extension for consent-based browser activity monitoring, connected to the SafeSignal/Kawach backend's weighted-scoring pipeline.

## Current activity detection

- Website visits
- Search queries on Google, Bing, DuckDuckGo and Yahoo
- Chat messages sent in chat-shaped inputs (WhatsApp Web, Messenger, Discord, Instagram, Telegram Web, Snapchat Web, Teams, Slack, and other message-box-shaped inputs elsewhere) — **best-effort**: this matches on input labels/placeholders that look like a message box, or a text input near a "Send" control on a known chat platform. It is not a fixed per-site scraper, so it can both miss messages on redesigned UIs and occasionally misfire on a non-chat text box that happens to look like one.
- Visible page text (off by default — see Options → "Visible text analysis")
- File uploads selected through standard `<input type="file">` controls
- File download creation events
- Form submission metadata without passwords or sensitive values
- Page title/domain metadata

### File upload data shown locally

For detected uploads, the local activity viewer can show:

- destination page/domain
- filename
- extension
- MIME type
- file size
- last modified time (when exposed by the browser)
- upload-selection timestamp

The actual file content is not read or sent.

## Load the extension

1. Open `chrome://extensions`.
2. Turn on Developer mode.
3. Choose **Load unpacked**.
4. Select this `Kawach_Extension` folder.
5. Open the extension popup and review settings.
6. Use **View local activity** to inspect detected events.

## Connecting to the backend

1. Run the SafeSignal/Kawach backend and note its base URL.
2. In the parent dashboard, create a child and get a one-time pairing code (`POST /api/children` → `pairing_code`).
3. In the extension's Options page, enter the backend base URL, turn on **Enable backend sync**, and enter the pairing code under **Link to a parent account**, then click **Pair this device**. This calls `POST /api/auth/pair` and stores the returned `child_id` locally — no manual child_id entry needed after that.
4. Searches, page/URL visits, chat messages, and (if enabled) page text are sent one at a time to `POST /api/signals`, matching the backend's weighted-scoring contract exactly (`child_id`, `session_id`, `signal_type`, `content`, `url`, `timestamp`). Uploads, downloads, form submissions, and page metadata are still sent as a batch to the legacy `/api/events` endpoint so nothing collected locally is dropped.
5. Every 5 minutes (and on browser startup) the extension polls `GET /api/monitoring/status/{child_id}` (no auth, read-only by design) so a parent toggling monitoring off from the dashboard actually pauses collection here, not just in the dashboard's own display.

Full contract details are in `BACKEND_INTEGRATION.md`.

## Security/privacy behavior

Monitoring is user-controlled. Sensitive-looking domains can be automatically excluded, and custom domain exclusions are supported. The extension does not capture passwords, authentication tokens, cookies or unrestricted keystrokes. Chat detection only reads text at the moment it's actively being sent (Enter or a Send click) — it does not read chat history or unsent drafts.
