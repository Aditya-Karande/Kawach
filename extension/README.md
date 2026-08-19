# Kawach Browser Activity Monitor

A Manifest V3 Chrome extension for consent-based browser activity monitoring. This build focuses on the activity data you said you need to see locally before a backend is connected.

## Current activity detection

- Website visits
- Search queries on Google, Bing, DuckDuckGo and Yahoo
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

## Backend

Backend sync is disabled by default. The adapter and event contract are documented in `BACKEND_INTEGRATION.md`.

## Security/privacy behavior

Monitoring is user-controlled. Sensitive-looking domains can be automatically excluded, and custom domain exclusions are supported. The extension does not capture passwords, authentication tokens, cookies or unrestricted keystrokes.
