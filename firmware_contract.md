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
{"type":"screen","s":"result","l1":"Keyboard","big":"-$20","l2":"Removed from books","c":"amber"}
{"type":"screen","s":"ask","l1":"Not sure","l2":"Check the dashboard"}
{"type":"screen","s":"offline"}
```

- Firmware draws only: two text lines (max 20 chars each), one big string (max 7 chars), a background colour from `green`, `amber`, `red`, `neutral`. The backend truncates before sending.
- If no `ping` for 5 s, firmware shows offline on its own.

## How to connect

The bin is a WebSocket client. The backend listens; the bin dials in.

    ws://<laptop>:8000/ws/bin

Port 8000 is plain HTTP with no TLS, which is the port to use from the board. The
backend also serves `wss://<laptop>:8443/ws/bin`, but that certificate is self signed,
so a client there has to be told to skip verification. A microcontroller or a small
Linux board has no business doing that, and nothing on the bin needs encryption.

The `<laptop>` part is the address of the machine running the backend, on the network
the bin is joined to. Run `hardware/find_laptop_ip.ps1` on the laptop to get it.

Order of business on a new connection:

1. The bin sends `hello` first, before anything else. A connection that sends a weight
   before a hello is closed.
2. The backend answers with a `ping`.
3. The bin streams `weight` at 10 to 20 Hz from then on.
4. Every `ping` gets a `pong` back. They arrive about every 20 s.
5. No `ping` for 5 s means the link is as good as gone, and the bin shows the offline
   screen on its own without waiting to be told.

If the socket drops, reconnect and start again from the hello. The backend keeps one
bin at a time; a second connection replaces the first.

A reference client that does all of this is `hardware/uno_q/bridge.py`, and
`hardware/README.md` is the wiring and calibration guide that goes with it.
