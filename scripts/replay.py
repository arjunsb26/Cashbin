"""Play a recorded session back into a running backend.

PLAN.md section 16 calls replay the demo insurance. A recording made by
`scripts/record.py` is two timelines, the bin messages and the camera frames, and this
plays both back on their original spacing as an ordinary bin client and an ordinary
phone client. The backend cannot tell the difference, so the detector, the crop, the
event builder and the LCD all run for real.

    uv run --project backend python scripts/replay.py --name demo-1 --insecure
    uv run --project backend python scripts/replay.py --name demo-1 --speed 4

The connection code is the simulator's, not a copy of it: `ssl_context_for` and the
phone url rule come from `sim/`, so a change to how the sims connect changes this too.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR / "sim"))
sys.path.insert(0, str(REPO_DIR))

from bin_sim import ssl_context_for  # type: ignore[import-not-found]  # noqa: E402
from run_scenario import phone_url_for  # type: ignore[import-not-found]  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.ingest.recorder import BIN_FILE, PHONE_INDEX, recording_dir  # noqa: E402

DEFAULT_URL = "wss://localhost:8443/ws/bin"


@dataclass
class Recording:
    """One recorded session, read off disk."""

    directory: Path
    bin_messages: list[tuple[float, dict[str, Any]]] = field(default_factory=list)
    phone_frames: list[tuple[float, Path]] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        times = self._times()
        return max(times) - min(times) if times else 0.0

    def _times(self) -> list[float]:
        return [t for t, _ in self.bin_messages] + [t for t, _ in self.phone_frames]

    def rebase(self) -> None:
        """Slide both timelines so the first thing recorded happens at zero.

        The stamps are seconds since the backend started, so a recording of a run that
        began a minute in would otherwise open the sockets and then sit silent for a
        minute. The gap between the two timelines is kept, because that gap is what
        puts the item in shot before it lands on the scale.
        """
        times = self._times()
        if not times:
            return
        base = min(times)
        self.bin_messages = [(t - base, m) for t, m in self.bin_messages]
        self.phone_frames = [(t - base, f) for t, f in self.phone_frames]


def read_recording(directory: Path) -> Recording:
    """Read the two index files. A missing one is an empty timeline, not an error."""
    recording = Recording(directory=directory)
    bin_path = directory / BIN_FILE
    if bin_path.is_file():
        for line in bin_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            recording.bin_messages.append((float(row.get("t", 0.0)), row.get("msg", {})))
    phone_path = directory / PHONE_INDEX
    if phone_path.is_file():
        for line in phone_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            recording.phone_frames.append((float(row.get("t", 0.0)), directory / row["file"]))
    recording.bin_messages.sort(key=lambda item: item[0])
    recording.phone_frames.sort(key=lambda item: item[0])
    recording.rebase()
    return recording


async def _pace(target_s: float, started: float, speed: float) -> None:
    """Wait until the recording's own clock reaches `target_s`. Speed 0 runs flat out."""
    if speed <= 0:
        return
    now = asyncio.get_running_loop().time() - started
    delay = target_s / speed - now
    if delay > 0:
        await asyncio.sleep(delay)


async def play_bin(
    recording: Recording,
    url: str,
    insecure: bool,
    speed: float,
    quiet: bool = False,
) -> int:
    """Replay the bin timeline as a bin client. Returns how many messages went out."""
    sent = 0
    async with websockets.connect(url, ssl=ssl_context_for(url, insecure)) as ws:
        reader = asyncio.create_task(_answer_pings(ws, quiet))
        started = asyncio.get_running_loop().time()
        try:
            for offset, message in recording.bin_messages:
                await _pace(offset, started, speed)
                await ws.send(json.dumps(message))
                sent += 1
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader
    return sent


async def _answer_pings(ws: websockets.ClientConnection, quiet: bool) -> None:
    """Answer the backend's heartbeat and print the screens, same as the bin sim does."""
    from lcd_box import render_screen  # type: ignore[import-not-found]

    with contextlib.suppress(websockets.ConnectionClosed, asyncio.CancelledError):
        async for raw in ws:
            if isinstance(raw, bytes):
                continue
            message = json.loads(raw)
            kind = message.get("type")
            if kind == "ping":
                await ws.send(json.dumps({"type": "pong", "t": 0}))
            elif kind == "screen" and not quiet:
                print(render_screen(message, 0.0))


async def play_phone(
    recording: Recording,
    url: str,
    insecure: bool,
    speed: float,
) -> int:
    """Replay the camera timeline as a phone client. Returns how many frames went out."""
    if not recording.phone_frames:
        return 0
    sent = 0
    async with websockets.connect(url, ssl=ssl_context_for(url, insecure)) as ws:
        await ws.send(json.dumps({"type": "hello", "ua": "replay"}))
        started = asyncio.get_running_loop().time()
        for offset, path in recording.phone_frames:
            await _pace(offset, started, speed)
            try:
                await ws.send(path.read_bytes())
            except OSError:
                print(f"missing frame file {path.name}")
                continue
            sent += 1
    return sent


async def replay(
    directory: Path,
    url: str = DEFAULT_URL,
    phone_url: str | None = None,
    insecure: bool = False,
    speed: float = 1.0,
    quiet: bool = False,
) -> tuple[int, int]:
    """Play both timelines at once. Returns the bin message count and the frame count."""
    recording = read_recording(directory)
    if not recording.bin_messages and not recording.phone_frames:
        print(f"nothing recorded in {directory}")
        return (0, 0)
    print(
        f"replaying {len(recording.bin_messages)} bin messages and "
        f"{len(recording.phone_frames)} frames over {recording.duration_s:.1f} s at {speed}x"
    )
    results = await asyncio.gather(
        play_bin(recording, url, insecure, speed, quiet),
        play_phone(recording, phone_url or phone_url_for(url), insecure, speed),
    )
    return (int(results[0]), int(results[1]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay a recorded session into the backend.")
    parser.add_argument("--name", default=None, help="recording name under the recordings folder")
    parser.add_argument("--dir", default=None, help="the recording directory itself")
    parser.add_argument("--url", default=DEFAULT_URL, help="the bin socket")
    parser.add_argument("--phone-url", default=None, help="defaults to the bin url with /ws/phone")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument("--speed", type=float, default=1.0, help="1 is real time, 0 is flat out")
    parser.add_argument("--quiet", action="store_true", help="do not print the LCD boxes")
    return parser


async def amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.name and not args.dir:
        print("give a recording with --name or --dir")
        return 2
    directory = Path(args.dir) if args.dir else recording_dir(args.name, get_settings())
    if not directory.is_dir():
        print(f"no recording at {directory}")
        return 1
    messages, frames = await replay(
        directory,
        url=args.url,
        phone_url=args.phone_url,
        insecure=args.insecure,
        speed=args.speed,
        quiet=args.quiet,
    )
    print(f"replayed {messages} bin messages and {frames} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
