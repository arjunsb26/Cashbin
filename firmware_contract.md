# Firmware contract

For whoever writes the bin firmware and the bridge script on the UNO Q. This is the whole
protocol between the bin and the backend. Build against this file and nothing else.

All messages are one JSON object per WebSocket text frame (or per line on serial). Unknown
fields are ignored. Every message has `type`.

## Bin to backend (`/ws/bin`)

```json
{"type":"hello","fw":"0.1","device":"bin-1"}
{"type":"weight","t":123456,"g":412.3}
{"type":"pong","t":123999}
{"type":"button","id":"a"}
```

- `weight` at 10 to 20 Hz. `t` is device milliseconds, `g` is raw grams after calibration, NOT filtered. All filtering is done in the backend.
- `button` is optional, reserved for a physical confirm button if the hardware gets one.

## Backend to bin

```json
{"type":"ping"}
{"type":"tare"}
{"type":"screen","s":"idle"}
{"type":"screen","s":"thinking"}
{"type":"screen","s":"result","l1":"Keyboard","big":"-$20","l2":"Removed from register","c":"amber"}
{"type":"screen","s":"ask","l1":"Not sure","l2":"Check the dashboard"}
{"type":"screen","s":"offline"}
```

- Firmware draws only: two text lines (max 20 chars each), one big string (max 7 chars), a background colour from `green`, `amber`, `red`, `neutral`. Backend is responsible for truncation. Put the truncation logic in `notify/lcd.py` with tests.
- If no `ping` for 5 s, firmware shows offline on its own.
