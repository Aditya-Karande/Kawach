# Kawach backend integration contract

The extension is backend-agnostic. The browser-side pipeline is:

`Browser signal -> consent/privacy filter -> event normalization -> local queue -> adapter`

The backend team only needs to implement an endpoint that accepts a JSON object shaped like:

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
- `file_upload`
- `form_submission`
- `file_download`
- `page_metadata`

The frontend intentionally does not implement authentication. Add the team's authentication headers/token mechanism inside `src/transport/backend-adapter.js` when the backend is ready.

## Important upload limitation

`file_upload` is based on a webpage file input selection. It records metadata (filename, extension, MIME type, size, page and time). It does not read or transmit the contents of the uploaded file.

The browser extension cannot guarantee visibility into every custom upload implementation. For broader coverage, the backend/team can later pair this signal with an appropriate network-level telemetry design within Chrome's permission model.
