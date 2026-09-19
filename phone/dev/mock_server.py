"""Mock backend for the phone page.

It stands in for the real backend until that lane merges. It serves the phone
folder over HTTPS with a self signed certificate it makes itself, hosts the
phone socket, counts the frames it receives, and plays a scripted sequence so
the result sheet and the ask can be seen without any hardware.

Run it from the worktree root:

    uv run --project backend python phone/dev/mock_server.py

Then open https://<your laptop ip>:8444/phone/ on the phone and accept the
certificate once.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import ipaddress
import json
import socket
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from hypercorn.asyncio import serve
from hypercorn.config import Config

DEV = Path(__file__).resolve().parent
PHONE = DEV.parent
ROOT = PHONE.parent
CERTS = DEV / "certs"
FIXTURES = DEV / "fixtures"

RESULT_AFTER_S = 5.0
ASK_AFTER_RESULT_S = 8.0
PING_EVERY_S = 2.0

RESULT_MESSAGE: dict[str, Any] = {
    "type": "result",
    "event_id": 17,
    "title": "Keyboard",
    "big": "-$20",
    "line": "Removed from register",
    "tone": "amber",
    "best_option": "recycle",
    "mass_g": 212,
}

ASK_MESSAGE: dict[str, Any] = {
    "type": "ask",
    "event_id": 18,
    "candidates": [{"label": "wrap", "p": 0.41}, {"label": "burrito", "p": 0.37}],
}


def log(line: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S} {line}", flush=True)


# ---- certificate ----


def lan_addresses() -> list[str]:
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if address.is_loopback or address.is_link_local:
                continue
            found.add(str(address))
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 53))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    return sorted(found)


def make_cert() -> tuple[Path, Path]:
    CERTS.mkdir(parents=True, exist_ok=True)
    cert_path = CERTS / "dev.crt"
    key_path = CERTS / "dev.key"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    names: list[x509.GeneralName] = [x509.DNSName("localhost")]
    names.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    names.append(x509.IPAddress(ipaddress.ip_address("::1")))
    for address in lan_addresses():
        names.append(x509.IPAddress(ipaddress.ip_address(address)))

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "phone page mock")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    log(f"made a certificate for {[str(n.value) for n in names]}")
    return cert_path, key_path


# ---- the app ----

app = FastAPI()
clients: set[WebSocket] = set()
script_on = True
refuse_until = 0.0


async def broadcast(message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for client in list(clients):
        try:
            await client.send_text(json.dumps(message))
        except Exception:
            dead.append(client)
    for client in dead:
        clients.discard(client)
    log(f"sent {message['type']} to {len(clients)} phone(s)")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse("/phone/")


@app.get("/brand.json")
async def brand() -> JSONResponse:
    for candidate in (ROOT / "brand.json", FIXTURES / "brand.json"):
        if candidate.exists():
            return JSONResponse(json.loads(candidate.read_text(encoding="utf-8")))
    return JSONResponse({}, status_code=404)


@app.get("/media/{event_id}/crop.jpg", response_model=None)
async def crop(event_id: int) -> FileResponse | JSONResponse:
    path = FIXTURES / "crop.jpg"
    if not path.exists():
        return JSONResponse({"detail": "no fixture crop"}, status_code=404)
    log(f"served the crop for event {event_id}")
    return FileResponse(path, media_type="image/jpeg")


@app.post("/api/corrections")
async def corrections(request: Request) -> JSONResponse:
    body = await request.body()
    log(f"correction posted: {body.decode('utf-8', 'replace')}")
    await broadcast({"type": "idle"})
    return JSONResponse({"ok": True})


@app.post("/api/dev/send")
async def dev_send(request: Request) -> JSONResponse:
    """Push one message to the phone. Used by the screenshot run."""
    message = await request.json()
    await broadcast(message)
    return JSONResponse({"ok": True})


@app.post("/api/dev/script")
async def dev_script(request: Request) -> JSONResponse:
    """Turn the scripted result and ask on or off while the mock runs.

    The screenshot run turns it off, so the only messages the page sees are the
    ones that run sends and every shot comes out the same.
    """
    global script_on
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    script_on = bool(body.get("on", True))
    log(f"scripted sequence {'on' if script_on else 'off'}")
    return JSONResponse({"on": script_on})


@app.post("/api/dev/drop")
async def dev_drop(request: Request) -> JSONResponse:
    """Close every phone socket, so the reconnect path can be watched.

    An optional {"refuse_s": 6} keeps new sockets out for that long, which is
    what makes the reconnecting state sit still long enough to photograph.
    """
    global refuse_until
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    seconds = float(body.get("refuse_s", 0) or 0)
    refuse_until = asyncio.get_running_loop().time() + seconds
    count = len(clients)
    for client in list(clients):
        with contextlib.suppress(Exception):
            await client.close(code=1012)
        clients.discard(client)
    log(f"dropped {count} phone socket(s), refusing new ones for {seconds:.0f} s")
    return JSONResponse({"dropped": count})


@app.websocket("/ws/phone")
async def ws_phone(websocket: WebSocket) -> None:
    if asyncio.get_running_loop().time() < refuse_until:
        await websocket.close(code=1013)
        return
    await websocket.accept()
    clients.add(websocket)
    log("a phone connected")

    state = {"frames": 0, "bytes": 0, "seen_first": False}

    async def pinger() -> None:
        while True:
            await asyncio.sleep(PING_EVERY_S)
            await websocket.send_text(json.dumps({"type": "ping"}))

    async def counter() -> None:
        while True:
            await asyncio.sleep(1.0)
            frames = state["frames"]
            kb = state["bytes"] / 1000
            state["frames"] = 0
            state["bytes"] = 0
            log(f"frames received in the last second: {frames}, {kb:.1f} kB")

    async def script() -> None:
        await asyncio.sleep(RESULT_AFTER_S)
        await broadcast(RESULT_MESSAGE)
        await asyncio.sleep(ASK_AFTER_RESULT_S)
        await broadcast(ASK_MESSAGE)

    jobs = [asyncio.create_task(pinger()), asyncio.create_task(counter())]
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                state["frames"] += 1
                state["bytes"] += len(message["bytes"])
                if not state["seen_first"]:
                    state["seen_first"] = True
                    log("first frame arrived")
                    if script_on:
                        jobs.append(asyncio.create_task(script()))
            elif message.get("text") is not None:
                log(f"phone said: {message['text'][:200]}")
    except Exception as err:  # noqa: BLE001
        log(f"phone socket ended: {type(err).__name__}")
    finally:
        for job in jobs:
            job.cancel()
        clients.discard(websocket)
        log("a phone disconnected")


app.mount("/phone", StaticFiles(directory=PHONE, html=True), name="phone")


def main() -> None:
    global script_on
    parser = argparse.ArgumentParser(description="Mock backend for the phone page")
    parser.add_argument("--port", type=int, default=8444)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-script", action="store_true", help="do not play the scripted result and ask")
    args = parser.parse_args()
    script_on = not args.no_script

    cert_path, key_path = make_cert()
    config = Config()
    config.bind = [f"{args.host}:{args.port}"]
    config.certfile = str(cert_path)
    config.keyfile = str(key_path)
    config.accesslog = None
    config.errorlog = None

    log(f"open https://localhost:{args.port}/phone/ on this laptop")
    for address in lan_addresses():
        log(f"open https://{address}:{args.port}/phone/ on the phone")
    asyncio.run(serve(app, config))


if __name__ == "__main__":
    main()
