# Kawach backend integration contract

The extension is backend-agnostic. The browser-side pipeline is:

`Browser signal -> consent/privacy filter -> event normalization -> local queue -> adapter`

## Primary endpoint: `POST /api/signals`

As of the v2 backend spec, the one true endpoint the extension should call
going forward is `POST /api/signals`, one call per signal:

```json
{
  "child_id": "string",
  "session_id": "string",
  "signal_type": "search_query | url_visit | page_text | chat_text",
  "content": "string",
  "url": "string | null",
  "timestamp": "ISO 8601 string"
}
```

`session_id` matters: the backend now scores signals as a weighted total
per browsing *session*, not just per child, so the adapter should generate
and persist a session id (e.g. reset on browser restart or after a period
of inactivity) and send it with every signal.

The extension should also start sending `chat_text` signals for chat
messages on monitored pages/apps — this wasn't previously covered by any
event type below.

`GET /api/monitoring/status/{child_id}` (no auth, read-only) should be
polled/checked before sending any data, same as before.

## Legacy batch endpoint (still supported during migration)

The backend also still accepts the older batch shape below, for
backward compatibility while the extension migrates to `/api/signals`:

```json
{
  "events": [
    {
      "eventId": "uuid",
      "eventType": "file_upload",
      "timestamp": "2026-08-17T18:00:00.000Z",
      "data": {
        "pageUrl": "https://example.com/upload",
        "domain": "example.com",
        "pageTitle": "Example Upload",
        "fileName": "photo.jpg",
        "fileExtension": ".jpg",
        "mimeType": "image/jpeg",
        "size": 123456,
        "lastModified": "2026-08-17T17:59:00.000Z",
        "detection": "file-input-selection"
      }
    }
  ]
}
```

Supported event types:

- `page_visit`
- `search`
- `chat_message` (new — routed to the `chat_text` signal type)
- `file_upload`
- `form_submission`
- `file_download`
- `page_metadata`

The frontend intentionally does not implement authentication for the
signal-ingest endpoints above (`/api/signals`, `/api/events`) — those stay
open by design since the extension has no parent login of its own. Parent-
facing endpoints (`/api/monitoring/toggle`, `/api/alerts/*`, `/api/guardians`,
`/api/children`) now require a parent bearer token from `POST /api/auth/login`;
that's a dashboard concern, not something this extension needs to send. Add
the team's authentication headers/token mechanism inside
`src/transport/backend-adapter.js` only if/when the extension itself needs to
call an authenticated endpoint (e.g. pairing via `POST /api/auth/pair`).

## Important upload limitation

`file_upload` is based on a webpage file input selection. It records metadata (filename, extension, MIME type, size, page and time). It does not read or transmit the contents of the uploaded file.

The browser extension cannot guarantee visibility into every custom upload implementation. For broader coverage, the backend/team can later pair this signal with an appropriate network-level telemetry design within Chrome's permission model.
