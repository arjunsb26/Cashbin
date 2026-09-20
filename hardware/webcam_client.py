"""A webcam standing in for the phone. Speaks the `/ws/phone` protocol from PLAN.md section 6.

The laptop's own camera, or any USB webcam, becomes the eye over the bin. It captures
continuously, sends about 8 JPEG frames a second as binary WebSocket frames, and prints
every result and ask the backend sends back as one readable line.

    uv run --project backend python hardware/webcam_client.py --list
    uv run --project backend python hardware/webcam_client.py --camera 0
    uv run --project backend python hardware/webcam_client.py --camera 0 --preview

Over localhost the default `ws://localhost:8000/ws/phone` needs no certificate. From
another machine use `wss://<laptop>:8443/ws/phone --insecure`, because the certificate
is self signed.

It keeps capturing while the backend is away and reconnects with backoff, and it reopens
the camera every two seconds if someone unplugs it.

Packages: this repo installs `opencv-python-headless`, which captures on Windows but has
no window support, so `--preview` draws with tkinter from the standard library instead.
Nothing new is needed. If you would rather have the OpenCV window, install the full
`opencv-python` in place of the headless build; do not add it to `pyproject.toml`.

It runs on the bin's own Debian as well as on the laptop. The capture backend is chosen
by operating system, Video4Linux there and DirectShow here, and `--preview` turns itself
off when there is no window toolkit and no display, which is the normal case on the board.
See `hardware/uno_q/board_linux_setup.md` section 10.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import ssl
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
import websockets

DEFAULT_URL = "ws://localhost:8000/ws/phone"
USER_AGENT = "webcam-client"
BACKOFF_START_S = 0.5
BACKOFF_MAX_S = 8.0
REOPEN_WAIT_S = 2.0


def api_preferences(name: str) -> list[tuple[str, int]]:
    """The capture backends to try, in order.

    DirectShow opens fastest on Windows and does not exist anywhere else. Video4Linux is
    the one that works on the bin's own Debian. Asking for a backend the build does not
    have is not an error worth crashing over, so a missing constant is simply skipped and
    `any` is always left at the end as the backend that exists everywhere.
    """
    table = {
        "dshow": ["CAP_DSHOW"],
        "msmf": ["CAP_MSMF"],
        "v4l2": ["CAP_V4L2", "CAP_V4L"],
        "avfoundation": ["CAP_AVFOUNDATION"],
        "any": ["CAP_ANY"],
    }
    if name in table:
        wanted = list(table[name])
    elif sys.platform == "win32":
        wanted = ["CAP_DSHOW", "CAP_MSMF", "CAP_ANY"]
    elif sys.platform == "darwin":
        wanted = ["CAP_AVFOUNDATION", "CAP_ANY"]
    else:
        wanted = ["CAP_V4L2", "CAP_V4L", "CAP_ANY"]

    order: list[tuple[str, int]] = []
    for attr in wanted:
        flag = getattr(cv2, attr, None)
        if flag is None:
            continue
        label = attr.removeprefix("CAP_").lower()
        if all(existing != flag for _, existing in order):
            order.append((label, int(flag)))
    if not order:
        order = [("any", int(cv2.CAP_ANY))]
    return order


def list_cameras(limit: int = 6, api: str = "auto") -> list[tuple[int, str, int, int]]:
    """Open every index up to `limit` and report the ones that give a frame."""
    found: list[tuple[int, str, int, int]] = []
    for index in range(limit):
        for label, flag in api_preferences(api):
            capture = cv2.VideoCapture(index, flag)
            if not capture.isOpened():
                capture.release()
                continue
            ok, frame = capture.read()
            capture.release()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            found.append((index, label, int(width), int(height)))
            break
    return found


@dataclass
class Camera:
    """One capture device, reopened as often as it takes."""

    index: int = 0
    api: str = "auto"
    width: int = 640
    quality: int = 70

    def __post_init__(self) -> None:
        self._capture: cv2.VideoCapture | None = None
        self.api_used = ""

    @property
    def is_open(self) -> bool:
        return self._capture is not None

    def open(self) -> bool:
        for label, flag in api_preferences(self.api):
            capture = cv2.VideoCapture(self.index, flag)
            if capture.isOpened():
                self._capture = capture
                self.api_used = label
                return True
            capture.release()
        return False

    def read(self) -> np.ndarray | None:
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        return self.fit(frame)

    def fit(self, frame: np.ndarray) -> np.ndarray:
        if frame.shape[1] == self.width:
            return frame
        height = max(1, round(frame.shape[0] * self.width / frame.shape[1]))
        return cv2.resize(frame, (self.width, height))

    def encode(self, frame: np.ndarray) -> bytes:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if not ok:
            raise RuntimeError("could not encode a webcam frame")
        return bytes(buf.tobytes())

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


@dataclass
class WebcamClient:
    """The camera side of the wire. Capture runs in a thread, the socket in asyncio."""

    url: str = DEFAULT_URL
    camera_index: int = 0
    api: str = "auto"
    fps: float = 8.0
    width: int = 640
    quality: int = 70
    insecure: bool = False
    preview: bool = False
    user_agent: str = USER_AGENT
    log: Any = print

    frames_sent: int = 0
    received: list[dict[str, Any]] = field(default_factory=list)
    caption: str = "waiting for the first result"

    def __post_init__(self) -> None:
        self.camera = Camera(self.camera_index, self.api, self.width, self.quality)
        self._latest_jpeg: bytes | None = None
        self._latest_frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self._connected = asyncio.Event()

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    def latest(self) -> tuple[bytes | None, np.ndarray | None]:
        with self._lock:
            return self._latest_jpeg, self._latest_frame

    def capture_forever(self) -> None:
        """Grab, resize and encode, whatever the socket is doing. Runs in its own thread."""
        period = 1.0 / self.fps if self.fps > 0 else 0.125
        complained = False
        while not self._halt.is_set():
            if not self.camera.is_open:
                if self.camera.open():
                    self.log(f"camera {self.camera_index} open on {self.camera.api_used}")
                    complained = False
                else:
                    if not complained:
                        self.log(f"no camera at index {self.camera_index}, retrying every 2 s")
                        complained = True
                    self._halt.wait(REOPEN_WAIT_S)
                    continue
            start = time.monotonic()
            frame = self.camera.read()
            if frame is None:
                self.log("the camera stopped giving frames, reopening")
                self.camera.release()
                self._halt.wait(REOPEN_WAIT_S)
                continue
            jpeg = self.camera.encode(frame)
            with self._lock:
                self._latest_jpeg = jpeg
                self._latest_frame = frame
            self._halt.wait(max(0.0, period - (time.monotonic() - start)))
        self.camera.release()

    async def run(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        grabber = threading.Thread(target=self.capture_forever, name="capture", daemon=True)
        grabber.start()
        window = PreviewWindow(self.width) if self.preview else None
        if window is not None and not window.ready:
            self.log("no window toolkit here, running without the preview")
            window = None
        painter = asyncio.create_task(self._paint(window, stop)) if window else None
        backoff = BACKOFF_START_S
        try:
            while not stop.is_set():
                try:
                    await self._session(stop)
                    backoff = BACKOFF_START_S
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.log(f"socket: {short(exc)}")
                self._connected.clear()
                if stop.is_set():
                    break
                self.log(f"reconnecting in {backoff:.1f} s")
                await wait_for(stop, backoff)
                backoff = min(backoff * 2.0, BACKOFF_MAX_S)
        finally:
            self._halt.set()
            if painter is not None:
                painter.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await painter
            if window is not None:
                window.close()
            grabber.join(timeout=3.0)

    async def _session(self, stop: asyncio.Event) -> None:
        async with websockets.connect(self.url, ssl=ssl_context_for(self.url, self.insecure)) as ws:
            await ws.send(json.dumps({"type": "hello", "ua": self.user_agent}))
            self._connected.set()
            self.log(f"webcam connected to {self.url}")
            reader = asyncio.create_task(self._read(ws, stop))
            try:
                await self._stream(ws, stop)
            finally:
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader

    async def _stream(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        period = 1.0 / self.fps if self.fps > 0 else 0.125
        while not stop.is_set():
            jpeg, _ = self.latest()
            if jpeg is not None:
                await ws.send(jpeg)
                self.frames_sent += 1
            await asyncio.sleep(period)

    async def _read(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                msg: dict[str, Any] = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                    continue
                self.received.append(msg)
                line = describe(msg)
                if msg.get("type") in {"result", "ask"}:
                    self.caption = line
                self.log(line)
        except websockets.ConnectionClosed:
            return

    async def _paint(self, window: PreviewWindow, stop: asyncio.Event) -> None:
        while not stop.is_set():
            _, frame = self.latest()
            if frame is not None:
                window.show(frame, self.caption)
            await asyncio.sleep(0.1)


def describe(msg: dict[str, Any]) -> str:
    """One line per backend message, the way the phone screen would read."""
    kind = msg.get("type")
    if kind == "result":
        return f"result: {msg.get('title')} {msg.get('big')} [{msg.get('tone')}] {msg.get('line')}"
    if kind == "ask":
        names = ", ".join(str(c.get("label")) for c in msg.get("candidates", []))
        return f"ask: which is it? {names}"
    if kind == "idle":
        return "idle"
    return f"message: {kind}"


def short(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 120 else text[:117] + "..."


def ssl_context_for(url: str, insecure: bool) -> ssl.SSLContext | None:
    if not url.startswith("wss://"):
        return None
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


async def wait_for(stop: asyncio.Event, seconds: float) -> None:
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


class PreviewWindow:
    """A small tkinter window showing what is being sent, captioned with the last result.

    The headless OpenCV build this repo installs has no `imshow`, and tkinter is in the
    standard library, so the preview costs no new package.
    """

    def __init__(self, width: int = 640) -> None:
        self.width = min(width, 480)
        self.ready = False
        self._label: Any = None
        self._caption: Any = None
        self._image: Any = None
        try:
            import tkinter as tk
        except ImportError:
            return
        try:
            self._tk = tk
            self._root = tk.Tk()
            self._root.title("Webcam, what the bin sees")
            self._label = tk.Label(self._root)
            self._label.pack()
            self._caption = tk.Label(self._root, text="", wraplength=self.width, justify="left")
            self._caption.pack(fill="x")
            self.ready = True
        except Exception:
            self.ready = False

    def show(self, frame: np.ndarray, caption: str) -> None:
        if not self.ready:
            return
        small = frame
        if frame.shape[1] != self.width:
            height = max(1, round(frame.shape[0] * self.width / frame.shape[1]))
            small = cv2.resize(frame, (self.width, height))
        ok, buf = cv2.imencode(".png", small)
        if not ok:
            return
        try:
            self._image = self._tk.PhotoImage(data=base64.b64encode(buf.tobytes()))
            self._label.configure(image=self._image)
            self._caption.configure(text=caption)
            self._root.update()
        except Exception:
            self.ready = False

    def close(self) -> None:
        if not self.ready:
            return
        self.ready = False
        with contextlib.suppress(Exception):
            self._root.destroy()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A webcam on /ws/phone")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--camera", type=int, default=0, help="capture device index")
    parser.add_argument(
        "--api",
        default="auto",
        choices=["auto", "dshow", "msmf", "v4l2", "avfoundation", "any"],
        help="capture backend, auto picks by operating system",
    )
    parser.add_argument("--list", action="store_true", help="print the camera indices that open")
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument("--preview", action="store_true", help="show a window while sending")
    return parser


def print_camera_list(api: str) -> int:
    cameras = list_cameras(api=api)
    if not cameras:
        print("no camera opened on indices 0 to 5")
        print("close anything else using the camera, then check Windows camera privacy")
        return 1
    print("cameras that open:")
    for index, label, width, height in cameras:
        print(f"  --camera {index}   {width}x{height} on {label}")
    return 0


async def amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return print_camera_list(args.api)
    client = WebcamClient(
        url=args.url,
        camera_index=args.camera,
        api=args.api,
        fps=args.fps,
        width=args.width,
        quality=args.quality,
        insecure=args.insecure,
        preview=args.preview,
    )
    await client.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:
        raise SystemExit(0) from None
