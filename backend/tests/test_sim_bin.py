"""The simulator and the detector have to agree, or neither is worth anything.

`bin_sim` is run against a real websocket server in this process, and the weight
messages it puts on the wire are fed straight into `detect()`. If the masses do not
come back, either the fake scale or the maths is wrong.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
import websockets
from app.detect.steps import Sample, detect, estimate_noise_sigma, samples_from_pairs
from websockets.asyncio.server import ServerConnection, serve

SIM_DIR = Path(__file__).resolve().parents[2] / "sim"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from bin_sim import BinSim, parse_command  # noqa: E402
from lcd_box import render_screen, screen_lines  # noqa: E402
from run_scenario import drive, load_scenario, wait_nominal  # noqa: E402

DEMO_MASSES = [95.0, 780.0, 62.0, 172.0]


class Backend:
    """A stand-in for the real `/ws/bin`: keeps every message, can push screens."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.connection: ServerConnection | None = None
        self.ready = asyncio.Event()

    @property
    def samples(self) -> list[Sample]:
        return samples_from_pairs(
            [(float(m["t"]), float(m["g"])) for m in self.messages if m.get("type") == "weight"]
        )

    async def handler(self, ws: ServerConnection) -> None:
        self.connection = ws
        self.ready.set()
        with contextlib.suppress(websockets.ConnectionClosed):
            async for raw in ws:
                if isinstance(raw, str):
                    self.messages.append(json.loads(raw))

    async def send(self, msg: dict[str, Any]) -> None:
        assert self.connection is not None
        await self.connection.send(json.dumps(msg))


@contextlib.asynccontextmanager
async def running_bin(**kwargs: Any) -> AsyncIterator[tuple[BinSim, Backend]]:
    """Start the fake backend and a bin sim wired to it, and clean both up."""
    backend = Backend()
    async with serve(backend.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        sim = BinSim(
            url=f"ws://127.0.0.1:{port}/ws/bin",
            speed=0.0,
            seed=kwargs.pop("seed", 5),
            log=kwargs.pop("log", _quiet),
            **kwargs,
        )
        stop = asyncio.Event()
        task = asyncio.create_task(sim.run(stop))
        try:
            await asyncio.wait_for(sim.connected.wait(), timeout=10.0)
            await asyncio.wait_for(backend.ready.wait(), timeout=10.0)
            yield sim, backend
        finally:
            stop.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, websockets.ConnectionClosed):
                await task


def _quiet(_: str) -> None:
    return None


SETTLE_BIAS_G = 0.6


def within_error(detected: float, intended: float, err: float) -> bool:
    """Three standard errors, plus the bit the standard error does not model.

    `mass_err_g` is white noise only. The scale is still ringing a little when the
    settle window opens, which biases the median by well under a gram. Measured over
    300 seeded runs of the demo masses the worst miss was 1.94 g and nothing fell
    outside this bar.
    """
    return abs(detected - intended) <= 3.0 * err + SETTLE_BIAS_G


async def test_two_tosses_over_the_wire_come_back_from_the_detector() -> None:
    async with running_bin() as (sim, backend):
        await wait_nominal(sim, 2.0)
        sim.toss(95.0)
        await wait_nominal(sim, 3.0)
        sim.toss(780.0)
        await wait_nominal(sim, 3.0)

    steps = detect(backend.samples)

    assert [s.kind for s in steps] == ["toss", "toss"]
    for step, intended in zip(steps, [95.0, 780.0], strict=True):
        assert within_error(step.mass_g, intended, step.mass_err_g), (
            f"{step.mass_g:.2f} vs {intended} +/- {step.mass_err_g:.2f}"
        )


async def test_the_hello_and_the_weight_stream_match_the_wire_protocol() -> None:
    async with running_bin() as (sim, backend):
        await wait_nominal(sim, 1.0)

    hello = backend.messages[0]
    assert hello["type"] == "hello"
    assert hello["device"] == "bin-1"
    assert "fw" in hello

    weights = [m for m in backend.messages if m["type"] == "weight"]
    assert len(weights) >= 10
    assert all(isinstance(m["t"], int) and isinstance(m["g"], float) for m in weights)
    gaps = [b["t"] - a["t"] for a, b in itertools.pairwise(weights)]
    assert 60 <= sum(gaps) / len(gaps) <= 73, "the sim should stream at about 15 Hz"


async def test_the_sim_answers_a_ping_with_a_pong() -> None:
    async with running_bin() as (sim, backend):
        await wait_nominal(sim, 0.5)
        await backend.send({"type": "ping"})
        await wait_nominal(sim, 1.0)

    assert any(m["type"] == "pong" for m in backend.messages)


async def test_a_tare_from_the_backend_zeroes_the_scale() -> None:
    async with running_bin() as (sim, backend):
        await wait_nominal(sim, 1.0)
        sim.toss(400.0)
        await wait_nominal(sim, 2.0)
        assert sim.level_g == pytest.approx(400.0)
        await backend.send({"type": "tare"})
        await wait_nominal(sim, 1.5)
        assert sim.level_g == 0.0


async def test_a_screen_message_is_printed_as_an_lcd_box() -> None:
    printed: list[str] = []
    async with running_bin(log=_recorder(printed)) as (sim, backend):
        await wait_nominal(sim, 0.5)
        await backend.send(
            {
                "type": "screen",
                "s": "result",
                "l1": "Keyboard",
                "big": "-$20",
                "l2": "Removed from register",
                "c": "amber",
            }
        )
        await wait_nominal(sim, 1.0)

    assert sim.screens, "the sim should keep the screens it was sent"
    box = "\n".join(printed)
    assert "Keyboard" in box
    assert "-$20" in box
    assert "amber" in box


async def test_the_noise_the_sim_emits_matches_the_sigma_it_was_asked_for() -> None:
    async with running_bin(sigma=1.2) as (sim, backend):
        await wait_nominal(sim, 20.0)

    assert estimate_noise_sigma(backend.samples) == pytest.approx(1.2, rel=0.2)


async def test_a_bag_change_empties_the_bin_and_reads_as_a_bag_change() -> None:
    async with running_bin() as (sim, backend):
        await wait_nominal(sim, 2.0)
        sim.toss(600.0)
        await wait_nominal(sim, 3.0)
        sim.bag_change()
        await wait_nominal(sim, 3.0)

    steps = detect(backend.samples)
    assert [s.kind for s in steps] == ["toss", "bag_change"]
    assert sim.level_g == 0.0


async def test_the_whole_demo_scenario_produces_its_five_steps() -> None:
    """The proof for M1: the scenario the demo runs, end to end, off the wire."""
    scenario = load_scenario("demo")
    backend = Backend()
    async with serve(backend.handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        bin_sim = BinSim(url=f"ws://127.0.0.1:{port}/ws/bin", speed=0.0, seed=9, log=_quiet)
        phone = _FakePhone()
        stop = asyncio.Event()
        task = asyncio.create_task(bin_sim.run(stop))
        try:
            await asyncio.wait_for(bin_sim.connected.wait(), timeout=10.0)
            await drive(
                scenario,
                bin_sim,
                phone,  # type: ignore[arg-type]
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
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, websockets.ConnectionClosed):
                await task

    steps = detect(backend.samples)
    assert [s.kind for s in steps] == ["toss", "toss", "toss", "toss", "bag_change"]
    for step, intended in zip(steps, DEMO_MASSES, strict=False):
        assert within_error(step.mass_g, intended, step.mass_err_g), (
            f"{step.mass_g:.2f} vs {intended} +/- {step.mass_err_g:.2f}"
        )
    assert within_error(steps[4].mass_g, -sum(DEMO_MASSES), steps[4].mass_err_g)
    assert phone.shown == ["bagel.png", "keyboard.png", "charger.png", "phone_cracked.png"]


def test_the_standalone_command_parser_reads_the_documented_words() -> None:
    assert parse_command("toss 95") is not None
    assert parse_command("remove 20") is not None
    assert parse_command("bag") is not None
    assert parse_command("tare") is not None
    assert parse_command("") is None
    assert parse_command("dance 4") is None


def test_the_lcd_box_truncates_the_way_the_firmware_does() -> None:
    line1, big, line2, tone = screen_lines(
        {
            "s": "result",
            "l1": "A label far longer than the screen",
            "big": "-$1234567890",
            "l2": "And a second line that is also far too long",
            "c": "purple",
        }
    )
    assert len(line1) == 20
    assert len(big) == 7
    assert len(line2) == 20
    assert tone == "neutral", "an unknown tone falls back rather than breaking the screen"


def test_the_idle_screen_shows_the_weight() -> None:
    box = render_screen({"type": "screen", "s": "idle"}, weight_g=2412.0)
    assert "2,412 g" in box
    assert "neutral" in box


class _FakePhone:
    """Enough of PhoneSim for the driver, with no camera and no socket."""

    def __init__(self) -> None:
        self.shown: list[str] = []
        self.cleared = 0
        self.frames_sent = 0
        self.connected = asyncio.Event()
        self.connected.set()

    def show(self, image: str) -> None:
        self.shown.append(image)

    def clear(self) -> None:
        self.cleared += 1


def _recorder(sink: list[str]) -> Callable[[str], None]:
    return sink.append
