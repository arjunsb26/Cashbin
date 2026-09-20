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

# ---- the chaos script ----
#
# The seven ways the phone page used to get stuck, in order, with the wait the
# hand run leaves between them. The screenshot run drives the same steps one at a
# time through /api/dev/chaos so it can check the screen after each one, and
# --chaos plays the lot on its own for a run on a real phone.

CHAOS: list[dict[str, Any]] = [
    {
        # An unpriced ticket lands first with no figure in it.
        "name": "valuing",
        "after_s": 3.0,
        "send": [
            {
                "type": "result",
                "event_id": 21,
                "title": "Keyboard",
                "big": "...",
                "line": "Working out value",
                "tone": "neutral",
                "best_option": "recycle",
                "mass_g": 212,
            }
        ],
    },
    {
        # The same ticket again, this time with the money on it.
        "name": "figure",
        "after_s": 3.0,
        "send": [
            {
                "type": "result",
                "event_id": 21,
                "title": "Keyboard",
                "big": "-$20",
                "line": "Removed from register",
                "tone": "amber",
                "best_option": "recycle",
            }
        ],
    },
    {
        # A question lands while a ticket is up. The question wins at once.
        "name": "ask-during-result",
        "after_s": 7.0,
        "send": [
            {
                "type": "result",
                "event_id": 22,
                "title": "Bagel",
                "big": "-$0.48",
                "line": "Food waste, composted",
                "tone": "green",
                "best_option": "compost",
                "mass_g": 95,
            },
            {"wait_s": 0.6},
            {
                "type": "ask",
                "event_id": 23,
                "candidates": [{"label": "wrap", "p": 0.41}, {"label": "burrito", "p": 0.37}],
            },
        ],
    },
    {
        # A ticket lands while the question is up. The question stays.
        "name": "result-during-ask",
        "after_s": 4.0,
        "send": [
            {
                "type": "result",
                "event_id": 24,
                "title": "Coffee cup",
                "big": "-$0.12",
                "line": "Lined paper, landfill",
                "tone": "red",
                "best_option": "trash",
                "mass_g": 18,
            }
        ],
    },
    {
        # The socket dies under the open question and comes back by itself.
        "name": "drop-mid-ask",
        "after_s": 4.0,
        "drop_refuse_s": 3.0,
    },
    {
        # A ticket whose figure never turns up.
        "name": "no-figure",
        "after_s": 14.0,
        "send": [
            {
                "type": "result",
                "event_id": 25,
                "title": "Cable",
                "big": "...",
                "line": "Working out value",
                "tone": "neutral",
                "best_option": "recycle",
                "mass_g": 60,
            }
        ],
    },
    {
        # A question the model had no guess for. The picture and its own words
        # stand in for the buttons.
        "name": "ask-no-candidates",
        "after_s": 4.0,
        "send": [
            {
                "type": "ask",
                "event_id": 28,
                "candidates": [],
                "looks_like": "a black plastic handle with a frayed cable coming out of it",
            }
        ],
    },
    {
        # A question the backend wrote itself, which stands in for the heading.
        "name": "ask-question",
        "after_s": 6.0,
        "send": [
            {
                "type": "ask",
                "event_id": 29,
                "question": "Is this the broken monitor from the meeting room?",
                "candidates": [{"label": "monitor", "p": 0.52}],
                "looks_like": "a wide flat screen with a cracked corner",
            }
        ],
    },
    {
        # The backend says nothing is happening.
        "name": "idle",
        "after_s": 16.0,
        "send": [{"type": "idle"}],
    },
]


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
chaos_on = False
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


@app.post("/api/sim/expect")
async def sim_expect() -> JSONResponse:
    """Stand in for the real simulator route, so the page draws its Add control.

    The page only wants to know whether the route is there. A 404 keeps the
    control off the screen, and anything else turns it on.
    """
    return JSONResponse({"label": "", "mass_g": None})


@app.post("/api/sim/toss")
async def sim_toss(request: Request) -> JSONResponse:
    """Take a hand added toss and send back a ticket, the way the real one does."""
    body = await request.body()
    log(f"toss posted: {body.decode('utf-8', 'replace')}")
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {}
    mass = data.get("mass_g")
    grams = int(mass) if isinstance(mass, (int, float)) else 0
    message = dict(RESULT_MESSAGE)
    message["event_id"] = 20
    message["title"] = "Keyboard"
    message["mass_g"] = grams
    await broadcast(message)
    return JSONResponse({"event_id": 20, "status": "detected"})


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
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    count = await drop_sockets(float(body.get("refuse_s", 0) or 0))
    return JSONResponse({"dropped": count})


async def drop_sockets(refuse_s: float) -> int:
    """Close every phone socket and keep new ones out for a while."""
    global refuse_until
    refuse_until = asyncio.get_running_loop().time() + refuse_s
    count = len(clients)
    for client in list(clients):
        with contextlib.suppress(Exception):
            await client.close(code=1012)
        clients.discard(client)
    log(f"dropped {count} phone socket(s), refusing new ones for {refuse_s:.0f} s")
    return count


async def run_chaos_step(step: dict[str, Any]) -> None:
    """One step of the chaos script, whoever asked for it."""
    log(f"chaos step {step['name']}")
    if step.get("drop_refuse_s"):
        await drop_sockets(float(step["drop_refuse_s"]))
        return
    for message in step.get("send", []):
        if "wait_s" in message:
            await asyncio.sleep(float(message["wait_s"]))
            continue
        await broadcast(message)


@app.get("/api/dev/chaos")
async def chaos_list() -> JSONResponse:
    """The step names in order, so the screenshot run reads them off the server."""
    return JSONResponse({"steps": [step["name"] for step in CHAOS]})


@app.post("/api/dev/chaos")
async def chaos_run(request: Request) -> JSONResponse:
    """Play one named step of the chaos script."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    name = str(body.get("step", ""))
    for step in CHAOS:
        if step["name"] == name:
            await run_chaos_step(step)
            return JSONResponse({"step": name})
    return JSONResponse({"detail": "no such step"}, status_code=404)


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

    async def chaos() -> None:
        for step in CHAOS:
            await asyncio.sleep(float(step.get("after_s", 3.0)))
            await run_chaos_step(step)
        log("the chaos script is done")

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
                    if chaos_on:
                        jobs.append(asyncio.create_task(chaos()))
                    elif script_on:
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
    global script_on, chaos_on
    parser = argparse.ArgumentParser(description="Mock backend for the phone page")
    parser.add_argument("--port", type=int, default=8444)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-script", action="store_true", help="do not play the scripted result and ask")
    parser.add_argument(
        "--chaos",
        action="store_true",
        help="play the chaos script instead: a ticket twice, a question over a ticket, a ticket "
        "under a question, a dropped socket mid question, and a ticket with no figure",
    )
    args = parser.parse_args()
    script_on = not args.no_script
    chaos_on = args.chaos

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
