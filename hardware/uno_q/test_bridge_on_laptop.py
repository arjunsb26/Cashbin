"""Prove the bridge works before the bin exists.

It starts a real backend on free ports, runs `bridge.py` with the fake scale, types two
tosses and a bag change at it, and then checks both ends of the wire: the backend made
the events, and the display sink drew the screens the backend sent back.

    python hardware/uno_q/test_bridge_on_laptop.py

Against a backend that is already running, which is the faster loop when one is up:

    python hardware/uno_q/test_bridge_on_laptop.py --url http://127.0.0.1:8000

Its own backend gets its own database and media folder in a temporary directory, so a
run never touches the demo data or a backend someone else is running.

Standard library only. The subprocesses need `websockets`, which lives in the backend
environment, so this finds that interpreter when the one running this file lacks it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BRIDGE = HERE / "bridge.py"

BACKEND_START_TIMEOUT_S = 120.0
SETTLE_S = 2.2
BASELINE_S = 2.0
TAIL_S = 4.0


def free_port() -> int:
    """A port nothing is listening on. The race with another process is not worth
    solving here; this runs on one laptop."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def python_command() -> List[str]:
    """An interpreter with `websockets` on it, for the child processes."""
    try:
        import websockets  # noqa: F401

        return [sys.executable]
    except ImportError:
        pass
    if shutil.which("uv"):
        return ["uv", "run", "--project", "backend", "python"]
    raise SystemExit(
        "no interpreter with websockets. Install it, or install uv so this can use "
        "the backend environment."
    )


class Reader(threading.Thread):
    """Drain a pipe into a list, so a full pipe buffer cannot wedge the child."""

    def __init__(self, stream: Any, echo: bool = False) -> None:
        threading.Thread.__init__(self, daemon=True)
        self.stream = stream
        self.echo = echo
        self.lines: List[str] = []

    def run(self) -> None:
        for raw in iter(self.stream.readline, ""):
            line = raw.rstrip("\n")
            self.lines.append(line)
            if self.echo:
                print(line)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def get_json(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(base: str, deadline: float, child: Optional[Any] = None) -> Dict[str, Any]:
    last = ""
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            raise SystemExit("the backend stopped before it answered. Its output is above.")
        try:
            return get_json(base + "/api/health", timeout=2.0)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last = str(exc)
            time.sleep(0.4)
    raise SystemExit("the backend never answered /api/health. Last error: " + last)


def start_backend(http_port: int, https_port: int, workdir: Path) -> Tuple[Any, Reader]:
    """A backend of this checkout, on its own ports, with its own database."""
    env = dict(os.environ)
    env["DB_PATH"] = str(workdir / "bridge-test.db")
    env["MEDIA_DIR"] = str(workdir / "media")
    env["RECORDINGS_DIR"] = str(workdir / "recordings")
    # No model, no key, no cost. The stub provider is what an empty provider means.
    env["LLM_PROVIDER"] = ""
    env["OPENAI_API_KEY"] = ""
    env["DEV_TOOLS"] = "0"
    env["PYTHONUNBUFFERED"] = "1"

    command = python_command() + [
        str(REPO / "scripts" / "run_backend.py"),
        "--host",
        "127.0.0.1",
        "--http-port",
        str(http_port),
        "--https-port",
        str(https_port),
    ]
    print("starting a backend on http port {}".format(http_port))
    child = subprocess.Popen(  # noqa: S603
        command,
        cwd=str(REPO),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    reader = Reader(child.stdout)
    reader.start()
    return child, reader


def run_bridge(ws_url: str, seconds: float) -> Tuple[int, Reader, Reader]:
    """The bridge with the fake scale, driven by typed commands."""
    command = python_command() + [
        str(BRIDGE),
        "--url",
        ws_url,
        "--source",
        "fake",
        "--commands",
        "stdin",
        "--seed",
        "7",
        "--device",
        "bin-test",
        "--seconds",
        str(seconds),
    ]
    print("starting the bridge against {}".format(ws_url))
    child = subprocess.Popen(  # noqa: S603
        command,
        cwd=str(REPO),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    out = Reader(child.stdout, echo=True)
    err = Reader(child.stderr)
    out.start()
    err.start()

    def say(line: str) -> None:
        print("  typing: {}".format(line))
        assert child.stdin is not None
        child.stdin.write(line + "\n")
        child.stdin.flush()

    # A quiet baseline first, because the detector needs a stable window to measure the
    # step against, exactly as it will on the real bin.
    time.sleep(BASELINE_S)
    say("toss 95")
    time.sleep(SETTLE_S)
    say("toss 240")
    time.sleep(SETTLE_S)
    say("bag")
    time.sleep(TAIL_S)
    say("quit")

    code = child.wait(timeout=30)
    out.join(timeout=5)
    err.join(timeout=5)
    return code, out, err


def check(passed: bool, message: str) -> bool:
    print("{} {}".format("ok  " if passed else "FAIL", message))
    return passed


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bridge against a real backend.")
    parser.add_argument(
        "--url",
        default="",
        help="Base URL of a backend that is already running, for example "
        "http://127.0.0.1:8000. Without it, one is started on free ports.",
    )
    args = parser.parse_args(argv)

    backend: Optional[Any] = None
    backend_out: Optional[Reader] = None
    workdir: Optional[Path] = None
    base = args.url.rstrip("/")

    try:
        if not base:
            workdir = Path(tempfile.mkdtemp(prefix="bridge-test-"))
            http_port = free_port()
            https_port = free_port()
            backend, backend_out = start_backend(http_port, https_port, workdir)
            base = "http://127.0.0.1:{}".format(http_port)
            health = wait_for_health(
                base, time.monotonic() + BACKEND_START_TIMEOUT_S, backend
            )
        else:
            health = wait_for_health(base, time.monotonic() + 10.0)
        print("backend up: {}".format(json.dumps(health)))

        before = get_json(base + "/api/events")["events"]
        ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws/bin"
        code, out, err = run_bridge(ws_url, seconds=BASELINE_S + 2 * SETTLE_S + TAIL_S + 8)

        # The events the backend built out of the fake scale's steps.
        time.sleep(1.5)
        after = get_json(base + "/api/events")["events"]
        seen = {row["id"] for row in before}
        fresh = [row for row in after if row["id"] not in seen]
        kinds = [row["kind"] for row in fresh]
        masses = [row.get("massG") or row.get("mass_g") for row in fresh]

        print("")
        print("bridge exit code {}".format(code))
        print("new events: {}".format(json.dumps(kinds)))
        print("masses in g: {}".format(json.dumps(masses)))
        print("")

        thinking = out.text.count("Weighing")
        results = [line for line in out.lines if line.strip() in ("green", "amber", "red")]
        pongs = "pings answered" in err.text

        good = True
        good &= check(code == 0, "the bridge exited cleanly")
        good &= check("connected as bin-test" in err.text, "the bridge said hello and connected")
        good &= check(
            len(fresh) >= 3, "the backend created at least 3 events, got {}".format(len(fresh))
        )
        good &= check(kinds.count("toss") >= 2, "two tosses became toss events")
        good &= check("bag_change" in kinds, "the bag change became a bag_change event")
        good &= check(
            thinking >= 2, "the display drew at least 2 thinking screens, got {}".format(thinking)
        )
        good &= check("Offline" in out.text, "the display drew the offline screen when there was no socket")
        good &= check("0 g" in out.text, "the display drew the idle screen with the live weight")
        good &= check(pongs, "the bridge answered the backend's pings")

        # A result screen needs an identified item, and identification needs a photo.
        # There is no phone in this test, so a tone fill is reported and not required.
        print("note: {} result screens with a tone fill (a phone is needed for one)".format(
            len(results)
        ))

        if not good:
            print("")
            print("--- bridge log ---")
            print(err.text[-4000:])
        print("")
        print("PASS" if good else "FAILED")
        return 0 if good else 1
    finally:
        if backend is not None:
            backend.terminate()
            try:
                backend.wait(timeout=15)
            except subprocess.TimeoutExpired:
                backend.kill()
        if backend_out is not None:
            backend_out.join(timeout=3)
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
