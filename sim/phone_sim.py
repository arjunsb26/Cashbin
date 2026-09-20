"""Fake phone. Speaks the `/ws/phone` protocol from PLAN.md section 6.

It streams a bin background as JPEG at about 8 fps, 640 px wide. When something is
tossed, the item sprite is composited onto the background for every frame after that
until the next bag change, which is exactly how the real camera sees a filling bin.
Messages coming back (`result`, `ask`, `idle`) are logged one line each.

    python sim/phone_sim.py --url wss://localhost:8443/ws/phone --insecure
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import websockets
from bin_sim import ssl_context_for

DEFAULT_URL = "wss://localhost:8443/ws/phone"
ASSETS = Path(__file__).resolve().parent / "assets"
SLOTS = ((0.30, 0.34), (0.66, 0.40), (0.42, 0.66), (0.72, 0.70), (0.26, 0.60), (0.55, 0.26))


def composite_items(background: np.ndarray, items: Sequence[Path]) -> np.ndarray:
    """Paste each item sprite onto a copy of the background, oldest first."""
    frame = background.copy()
    for index, path in enumerate(items):
        sprite = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if sprite is None:
            continue
        fx, fy = SLOTS[index % len(SLOTS)]
        _paste(frame, sprite, fx, fy)
    return frame


def _paste(frame: np.ndarray, sprite: np.ndarray, fx: float, fy: float) -> None:
    h, w = sprite.shape[:2]
    fh, fw = frame.shape[:2]
    x = int(fx * fw) - w // 2
    y = int(fy * fh) - h // 2
    x = max(0, min(fw - w, x))
    y = max(0, min(fh - h, y))
    if sprite.shape[2] == 4:
        alpha = sprite[:, :, 3:4].astype(np.float32) / 255.0
        patch = frame[y : y + h, x : x + w].astype(np.float32)
        blended = sprite[:, :, :3].astype(np.float32) * alpha + patch * (1.0 - alpha)
        frame[y : y + h, x : x + w] = blended.astype(np.uint8)
    else:
        frame[y : y + h, x : x + w] = sprite


class MissingAsset(FileNotFoundError):
    """A scenario names a picture that is not on disk."""

    def __init__(self, path: Path, assets_dir: Path) -> None:
        self.path = path
        self.assets_dir = assets_dir
        super().__init__(str(path))

    def __str__(self) -> str:
        return (
            f"MISSING IMAGE: {self.path}\n"
            "The phone would stream an empty bin, so every ticket would open an ask.\n"
            f"Pictures are being read from {self.assets_dir}. A scenario built on "
            "photographs needs --assets sim/assets/real."
        )


@dataclass
class PhoneSim:
    """The phone side of the wire. Drive it with `show` and `clear`."""

    url: str = DEFAULT_URL
    assets_dir: Path = ASSETS
    background: str = "bin.png"
    fps: float = 8.0
    width: int = 640
    quality: int = 70
    insecure: bool = False
    speed: float = 1.0
    user_agent: str = "phone-sim"
    log: Callable[[str], None] = print

    items: list[Path] = field(default_factory=list)
    received: list[dict[str, Any]] = field(default_factory=list)
    frames_sent: int = 0

    def __post_init__(self) -> None:
        self._connected = asyncio.Event()
        self._background = self._load_background()

    @property
    def connected(self) -> asyncio.Event:
        return self._connected

    def resolve(self, image: str | Path) -> Path:
        """Where a scenario's picture lives, or a refusal saying why it does not."""
        path = Path(image)
        if not path.is_absolute():
            path = self.assets_dir / path
        if not path.exists():
            raise MissingAsset(path, self.assets_dir)
        return path

    def check_assets(self, images: Iterable[str | Path]) -> None:
        """Every picture a scenario names, before a single frame goes out."""
        for image in images:
            self.resolve(image)

    def show(self, image: str | Path) -> None:
        """Put an item in frame and leave it there.

        A missing file used to be a log line and an empty bin, which is the worst possible
        failure: every frame is then a photograph of nothing, the model correctly says it
        cannot name what is not there, every ticket opens an ask, and the whole run reads
        as a backend bug. It stops the run now, and names the flag that is usually the
        reason.
        """
        self.items.append(self.resolve(image))

    def clear(self) -> None:
        """Empty the bin, which is what a bag change looks like through the camera."""
        self.items.clear()

    def frame(self) -> bytes:
        image = composite_items(self._background, self.items)
        ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
        if not ok:
            raise RuntimeError("could not encode a phone frame")
        return bytes(buf.tobytes())

    async def run(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        async with websockets.connect(self.url, ssl=ssl_context_for(self.url, self.insecure)) as ws:
            await ws.send(json.dumps({"type": "hello", "ua": self.user_agent}))
            self._connected.set()
            self.log(f"phone sim connected to {self.url}")
            reader = asyncio.create_task(self._read(ws, stop))
            try:
                await self._stream(ws, stop)
            finally:
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader

    async def _stream(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        period = 1.0 / self.fps
        while not stop.is_set():
            await ws.send(self.frame())
            self.frames_sent += 1
            await asyncio.sleep(0.0 if self.speed <= 0 else period / self.speed)

    async def _read(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                msg: dict[str, Any] = json.loads(raw)
                self.received.append(msg)
                self.log(self.describe(msg))
                if msg.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
        except websockets.ConnectionClosed:
            stop.set()

    @staticmethod
    def describe(msg: dict[str, Any]) -> str:
        """One line per backend message, the way the phone screen would read."""
        kind = msg.get("type")
        if kind == "result":
            return (
                f"phone result: {msg.get('title')} {msg.get('big')} "
                f"[{msg.get('tone')}] {msg.get('line')}"
            )
        if kind == "ask":
            names = ", ".join(str(c.get("label")) for c in msg.get("candidates", []))
            return f"phone ask: which is it? {names}"
        if kind == "idle":
            return "phone idle"
        return f"phone message: {kind}"

    def _load_background(self) -> np.ndarray:
        path = self.assets_dir / self.background
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"no bin background at {path}, run sim/make_assets.py")
        if image.shape[1] != self.width:
            height = round(image.shape[0] * self.width / image.shape[1])
            image = cv2.resize(image, (self.width, height))
        return image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulated phone camera on /ws/phone")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--assets", default=str(ASSETS))
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--quality", type=int, default=70)
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument(
        "--speed", type=float, default=1.0, help="wall clock multiplier, 0 runs flat out"
    )
    parser.add_argument("--show", action="append", default=[], help="item image to start with")
    return parser


async def amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sim = PhoneSim(
        url=args.url,
        assets_dir=Path(args.assets),
        fps=args.fps,
        width=args.width,
        quality=args.quality,
        insecure=args.insecure,
        speed=args.speed,
    )
    for image in args.show:
        sim.show(image)
    await sim.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:
        raise SystemExit(0) from None
