"""Fake bin. Speaks the `/ws/bin` protocol from PLAN.md section 6.

It streams a noisy weight baseline, and on command adds a step with an impact spike
of three times the mass that rings down and is back inside a gram between 430 ms
(a charger) and 680 ms (a full bag), which is what a load cell under a bin actually
does. Every `screen` message the backend sends
is printed as an LCD box so the LCD is provable from a terminal log.

Standalone:

    python sim/bin_sim.py --url ws://localhost:8000/ws/bin
    toss 95
    remove 20
    bag
    tare

Driven from a scenario, `sim/run_scenario.py` pushes the same commands onto
`BinSim.commands` instead of reading stdin.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import ssl
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import websockets
from lcd_box import render_screen

DEFAULT_URL = "wss://localhost:8443/ws/bin"
CommandKind = Literal["toss", "remove", "bag", "tare"]


@dataclass(frozen=True)
class BinCommand:
    kind: CommandKind
    grams: float = 0.0


@dataclass
class _Impact:
    """One landing: a spike that decays into a wobble."""

    t0_ms: float
    mass_g: float
    overshoot: float = 2.0
    tau_ms: float = 90.0
    hz: float = 6.0

    def offset(self, t_ms: float) -> float:
        dt = t_ms - self.t0_ms
        if dt < 0:
            return 0.0
        ring = math.exp(-dt / self.tau_ms) * math.cos(2 * math.pi * self.hz * dt / 1000.0)
        return self.mass_g * self.overshoot * ring

    def done(self, t_ms: float) -> bool:
        return t_ms - self.t0_ms > 8.0 * self.tau_ms


@dataclass
class BinSim:
    """The bin side of the wire. Drive it with `commands`, run it with `run`."""

    url: str = DEFAULT_URL
    sigma: float = 0.8
    rate_hz: float = 15.0
    device: str = "bin-1"
    firmware: str = "0.1-sim"
    insecure: bool = False
    speed: float = 1.0
    seed: int | None = None
    log: Callable[[str], None] = print

    commands: asyncio.Queue[BinCommand] = field(default_factory=asyncio.Queue)
    level_g: float = 0.0
    t_ms: float = 0.0
    screens: list[dict[str, Any]] = field(default_factory=list)
    sent: list[tuple[float, float]] = field(default_factory=list)
    keep_sent: bool = False

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._impacts: list[_Impact] = []
        self._connected = asyncio.Event()

    @property
    def connected(self) -> asyncio.Event:
        """Set once the hello has gone out, so a driver knows it can start tossing."""
        return self._connected

    def toss(self, grams: float) -> None:
        self.commands.put_nowait(BinCommand("toss", grams))

    def remove(self, grams: float) -> None:
        self.commands.put_nowait(BinCommand("remove", grams))

    def bag_change(self, grams: float = 0.0) -> None:
        self.commands.put_nowait(BinCommand("bag", grams))

    def tare(self) -> None:
        self.commands.put_nowait(BinCommand("tare"))

    async def run(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        async with websockets.connect(self.url, ssl=ssl_context_for(self.url, self.insecure)) as ws:
            await ws.send(json.dumps({"type": "hello", "fw": self.firmware, "device": self.device}))
            self._connected.set()
            self.log(f"bin sim connected to {self.url}")
            reader = asyncio.create_task(self._read(ws, stop))
            try:
                await self._stream(ws, stop)
            finally:
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reader

    async def _stream(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        dt_ms = 1000.0 / self.rate_hz
        while not stop.is_set():
            self._drain_commands()
            grams = self.reading()
            if self.keep_sent:
                self.sent.append((self.t_ms, grams))
            await ws.send(json.dumps({"type": "weight", "t": round(self.t_ms), "g": grams}))
            self.t_ms += dt_ms
            await asyncio.sleep(self.frame_delay_s(dt_ms / 1000.0))

    def frame_delay_s(self, period_s: float) -> float:
        """How long to wait between frames. A speed of 0 means run flat out, which is
        what the tests use so they do not spend real seconds watching a fake scale."""
        return 0.0 if self.speed <= 0 else period_s / self.speed

    def reading(self) -> float:
        """The value the load cell would report right now."""
        self._impacts = [i for i in self._impacts if not i.done(self.t_ms)]
        wobble = sum(i.offset(self.t_ms) for i in self._impacts)
        noise = float(self._rng.normal(0.0, self.sigma))
        return round(self.level_g + wobble + noise, 2)

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except asyncio.QueueEmpty:
                return
            self._apply(command)

    def _apply(self, command: BinCommand) -> None:
        if command.kind == "tare":
            self.level_g = 0.0
            self._impacts.clear()
            self.log("bin sim tared")
            return
        if command.kind == "toss":
            delta = command.grams
        elif command.kind == "remove":
            delta = -abs(command.grams)
        else:
            delta = -(abs(command.grams) if command.grams else self.level_g)
        if delta == 0.0:
            return
        self.level_g = round(self.level_g + delta, 3)
        self._impacts.append(_Impact(t0_ms=self.t_ms, mass_g=delta))
        self.log(f"bin sim {command.kind} {delta:+.1f} g, now {self.level_g:.1f} g")

    async def _read(self, ws: websockets.ClientConnection, stop: asyncio.Event) -> None:
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                msg: dict[str, Any] = json.loads(raw)
                kind = msg.get("type")
                if kind == "ping":
                    await ws.send(json.dumps({"type": "pong", "t": round(self.t_ms)}))
                elif kind == "screen":
                    self.screens.append(msg)
                    self.log(render_screen(msg, self.level_g))
                elif kind == "tare":
                    self._apply(BinCommand("tare"))
        except websockets.ConnectionClosed:
            stop.set()


def ssl_context_for(url: str, insecure: bool) -> ssl.SSLContext | None:
    if not url.startswith("wss://"):
        return None
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def parse_command(line: str) -> BinCommand | None:
    """Read one standalone-mode line. Unknown words are ignored, not fatal."""
    parts = line.strip().split()
    if not parts:
        return None
    word = parts[0].lower()
    grams = float(parts[1]) if len(parts) > 1 else 0.0
    if word == "toss":
        return BinCommand("toss", grams)
    if word in {"remove", "take"}:
        return BinCommand("remove", grams)
    if word in {"bag", "bag_change"}:
        return BinCommand("bag", grams)
    if word == "tare":
        return BinCommand("tare")
    return None


async def _read_stdin(sim: BinSim, stop: asyncio.Event) -> None:
    while not stop.is_set():
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line or line.strip() in {"quit", "exit"}:
            stop.set()
            return
        command = parse_command(line)
        if command is None:
            sim.log("commands: toss <grams>, remove <grams>, bag [grams], tare, quit")
            continue
        sim.commands.put_nowait(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulated bin on /ws/bin")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--sigma", type=float, default=0.8, help="noise standard deviation in g")
    parser.add_argument("--rate", type=float, default=15.0, help="weight samples per second")
    parser.add_argument("--device", default="bin-1")
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument(
        "--speed", type=float, default=1.0, help="wall clock multiplier, 0 runs flat out"
    )
    parser.add_argument("--seed", type=int, default=None)
    return parser


async def amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sim = BinSim(
        url=args.url,
        sigma=args.sigma,
        rate_hz=args.rate,
        device=args.device,
        insecure=args.insecure,
        speed=args.speed,
        seed=args.seed,
    )
    stop = asyncio.Event()
    typist = asyncio.create_task(_read_stdin(sim, stop))
    try:
        await sim.run(stop)
    finally:
        typist.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typist
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:
        raise SystemExit(0) from None
