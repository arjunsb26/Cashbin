"""The two halves of this lane have to meet: sim frames in, a usable crop out.

`test_sim_bin.py` proves the fake scale and the detector agree. This proves the fake
camera and the crop agree, on the same run, on the same clock. It is the regression
guard for the `before_lead_ms` default: at the 300 ms PLAN.md section 7 suggests, the
before frame already has the item in it and every crop in the demo comes back `low`.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path

import pytest
import websockets
from websockets.asyncio.server import serve

from app.detect.crop import CropParams, Frame, crop_item, pick_frames
from app.detect.steps import Step, detect
from tests.test_sim_bin import Backend, _quiet

SIM_DIR = Path(__file__).resolve().parents[2] / "sim"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

# The simulators live outside the backend package and are put on the path above,
# which mypy cannot follow from a static read of the file.
from bin_sim import BinSim  # type: ignore[import-not-found]  # noqa: E402
from phone_sim import PhoneSim  # type: ignore[import-not-found]  # noqa: E402
from run_scenario import (  # type: ignore[import-not-found]  # noqa: E402
    drive,
    load_scenario,
)

PHONE_FPS = 8.0


class _RecordingPhone:
    """A real `PhoneSim` with no socket, sampled on the bin's simulated clock.

    The backend stamps every frame with its own arrival time, so the frames and the
    weight samples have to share one clock here too.
    """

    def __init__(self, bin_sim: BinSim) -> None:
        self._bin = bin_sim
        self._phone = PhoneSim(url="ws://unused/ws/phone")
        self.frames: list[Frame] = []
        self.connected = asyncio.Event()
        self.connected.set()
        self.frames_sent = 0

    def show(self, image: str) -> None:
        self._phone.show(image)

    def clear(self) -> None:
        self._phone.clear()

    async def record(self, stop: asyncio.Event) -> None:
        period_ms = 1000.0 / PHONE_FPS
        next_at = 0.0
        while not stop.is_set():
            if self._bin.t_ms >= next_at:
                self.frames.append(Frame(t_ms=self._bin.t_ms, jpeg=self._phone.frame()))
                self.frames_sent += 1
                next_at = self._bin.t_ms + period_ms
            await asyncio.sleep(0)


async def _run_demo() -> tuple[list[Step], list[Frame]]:
    scenario = load_scenario("demo")
    backend = Backend()
    async with serve(backend.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        bin_sim = BinSim(url=f"ws://127.0.0.1:{port}/ws/bin", speed=0.0, seed=9, log=_quiet)
        phone = _RecordingPhone(bin_sim)
        stop = asyncio.Event()
        tasks = [
            asyncio.create_task(bin_sim.run(stop)),
            asyncio.create_task(phone.record(stop)),
        ]
        try:
            await asyncio.wait_for(bin_sim.connected.wait(), timeout=10.0)
            await drive(
                scenario,
                bin_sim,
                phone,
                gap_s=3.0,
                lead_s=2.0,
                tail_s=3.0,
                land_delay_s=0.3,
                expect_url=None,
                insecure=False,
                log=_quiet,
            )
        finally:
            stop.set()
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError, websockets.ConnectionClosed):
                    await task
    return detect(backend.samples), phone.frames


@pytest.fixture(scope="module")
def demo_run() -> tuple[list[Step], list[Frame]]:
    return asyncio.run(_run_demo())


def test_every_demo_toss_crops_to_the_item_that_landed(
    demo_run: tuple[list[Step], list[Frame]],
) -> None:
    steps, frames = demo_run
    tosses = [s for s in steps if s.kind == "toss"]
    assert len(tosses) == 4

    for index, step in enumerate(tosses, start=1):
        pick = pick_frames(frames, step)
        assert pick.complete, f"toss {index} has no before or after frame"
        assert pick.peak is not None
        result = crop_item(pick.before.jpeg, pick.after.jpeg)  # type: ignore[union-attr]
        assert result.crop_quality == "good", (
            f"toss {index} cropped at {result.changed_area_frac:.4f} of the frame"
        )
        assert result.bbox.w > 0 and result.bbox.h > 0
        assert len(result.jpeg) > 0


def test_a_short_before_lead_loses_the_crop(demo_run: tuple[list[Step], list[Frame]]) -> None:
    """The 300 ms in PLAN.md section 7 is shorter than the flight time, so the before
    frame already contains the item. Keep the reason for the 600 ms default visible."""
    steps, frames = demo_run
    short = CropParams(before_lead_ms=300.0)
    qualities = []
    for step in (s for s in steps if s.kind == "toss"):
        pick = pick_frames(frames, step, short)
        assert pick.before is not None and pick.after is not None
        qualities.append(crop_item(pick.before.jpeg, pick.after.jpeg, short).crop_quality)

    assert "low" in qualities, "if this passes at a 300 ms lead the default can go back"

