# Changelog

Newest first, one section per lane.

## Lane E, the phone page

### 2026-09-19

- Added the camera page at `/phone`: start screen, full bleed rear camera preview, a
  status pill with a dot and Live or Reconnecting, a result sheet built like the ticket
  at phone scale, and the ask with candidate buttons and a validated free text answer.
- Streams JPEG frames at 640 px wide, quality 0.7, about eight a second on a timer, over
  a secure WebSocket to `/ws/phone`, dropping frames when the send buffer holds more than
  two of them so a slow link never builds latency. Reconnects with backoff from 0.5 s to
  8 s and answers ping with pong.
- Copied the colour, type, space and motion tokens from DESIGN.md section 2 into
  `phone.css`. No other colour value appears in the page. IBM Plex Sans and Sans
  Condensed ship as local woff2 files with the OFL licence beside them.
- Product name comes from `GET /brand.json` at runtime and falls back to the page title.
- Typed answers are read into one field: trimmed, lowercased, letters, digits, spaces and
  hyphens only, 40 characters at most, with the understood value and every dropped part
  shown before it is sent.
- Screen wake lock while the camera runs, re-requested when the page becomes visible
  again. Safe area insets respected. Web app manifest for add to home screen.
- Errors read as sentences: camera refused, no camera, camera busy, connection dropped,
  and the page opened over plain HTTP.
- Added `phone/dev/`: a mock backend over HTTPS with its own certificate, a frame counter,
  a scripted result and ask, and a Playwright run that captures the six states at 390x844.
