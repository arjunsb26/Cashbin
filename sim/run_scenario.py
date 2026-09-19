"""Drive the bin and phone simulators through a scripted scenario.

    python sim/run_scenario.py --scenario demo --url wss://localhost:8443/ws/bin --insecure

The phone shows the item first and the bin sees it land 300 ms later, because that is
the order a real toss happens in: the item is in frame before it hits the scale.

When `--expect-url` is given, each toss first tells the backend which label to expect
(PLAN.md 21a item 2), so the stub provider can drive the whole pipeline with no model.
That endpoint is dev only and may not exist yet, so a refused connection or a 501 is
logged and the run carries on.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import time
from pathlib import Path
from typing import Any, Literal

import yaml
from bin_sim import BinSim
from phone_sim import PhoneSim
from pydantic import BaseModel, Field, model_validator

SCENARIOS = Path(__file__).resolve().parent / "scenarios"
ASSETS = Path(__file__).resolve().parent / "assets"
StepKind = Literal["toss", "bag_change", "removal"]


class ScenarioStep(BaseModel):
    """One scripted action. `image` is a file name inside `sim/assets`."""

    kind: StepKind
    label: str = Field(min_length=1, max_length=40)
    mass_g: float | None = None
    image: str | None = None
    tag: str | None = None

    @model_validator(mode="after")
    def check(self) -> ScenarioStep:
        if self.kind in {"toss", "removal"}:
            if self.mass_g is None or self.mass_g <= 0:
                raise ValueError(f"a {self.kind} needs a positive mass_g")
            if self.kind == "toss" and not self.image:
                raise ValueError("a toss needs an image for the phone to show")
        if self.kind == "bag_change" and self.mass_g is not None and self.mass_g <= 0:
            raise ValueError("a bag change with a mass_g needs it positive")
        return self


class Scenario(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    sigma: float = Field(default=0.8, ge=0.0, le=50.0)
    steps: list[ScenarioStep] = Field(min_length=1)


def scenario_path(name: str) -> Path:
    """Accept a bare name, a file name, or a path."""
    candidate = Path(name)
    if candidate.suffix and candidate.exists():
        return candidate
    for guess in (SCENARIOS / name, SCENARIOS / f"{name}.yaml", SCENARIOS / f"{name}.yml"):
        if guess.exists():
            return guess
    raise FileNotFoundError(f"no scenario called {name} under {SCENARIOS}")


def load_scenario(name: str) -> Scenario:
    path = scenario_path(name)
    with path.open(encoding="utf-8") as handle:
        return Scenario.model_validate(yaml.safe_load(handle))


def phone_url_for(bin_url: str) -> str:
    return bin_url.replace("/ws/bin", "/ws/phone")


async def wait_nominal(bin_sim: BinSim, seconds: float, *, timeout_s: float = 300.0) -> None:
    """Wait `seconds` of simulated time, not wall time.

    The scenario has to hold its shape whether the sims are paced in real time or
    running flat out, because the detector only ever sees the simulated clock.
    """
    target = bin_sim.t_ms + seconds * 1000.0
    deadline = time.monotonic() + timeout_s
    while bin_sim.t_ms < target:
        if time.monotonic() > deadline:
            raise TimeoutError("the bin simulator stopped advancing its clock")
        await asyncio.sleep(0.002)


async def post_expect(url: str, label: str, mass_g: float | None, insecure: bool) -> str:
    """Tell the backend what is coming next. Never fatal."""
    payload: dict[str, Any] = {"label": label}
    if mass_g is not None:
        payload["mass_g"] = mass_g
    try:
        import httpx
    except ImportError:
        return "expect skipped, no http client installed"
    try:
        async with httpx.AsyncClient(verify=not insecure, timeout=3.0) as client:
            reply = await client.post(url, json=payload)
    except Exception as exc:  # the endpoint is optional by design, so nothing here is fatal
        return f"expect not delivered ({type(exc).__name__})"
    if reply.status_code >= 400:
        return f"expect not accepted ({reply.status_code})"
    return f"expect {label}"


async def drive(
    scenario: Scenario,
    bin_sim: BinSim,
    phone_sim: PhoneSim,
    *,
    gap_s: float,
    lead_s: float,
    tail_s: float,
    land_delay_s: float,
    expect_url: str | None,
    insecure: bool,
    log: Any = print,
) -> None:
    """Play the scenario once, then let the tail run out."""
    await asyncio.wait_for(bin_sim.connected.wait(), timeout=20.0)
    await asyncio.wait_for(phone_sim.connected.wait(), timeout=20.0)
    log(f"scenario {scenario.name}: {len(scenario.steps)} steps")
    await wait_nominal(bin_sim, lead_s)

    for index, step in enumerate(scenario.steps, start=1):
        if expect_url and step.kind == "toss" and not step.tag:
            # A tagged item is identified by its tag before any provider is asked, so an
            # expectation for it would never be taken off the queue and every later toss
            # would get the wrong one.
            log(await post_expect(expect_url, step.label, step.mass_g, insecure))
        log(f"step {index}/{len(scenario.steps)}: {step.kind} {step.label}")
        if step.kind == "toss":
            if step.image:
                phone_sim.show(step.image)
            await wait_nominal(bin_sim, land_delay_s)
            bin_sim.toss(float(step.mass_g or 0.0))
        elif step.kind == "removal":
            bin_sim.remove(float(step.mass_g or 0.0))
            phone_sim.clear()
        else:
            bin_sim.bag_change(float(step.mass_g or 0.0))
            phone_sim.clear()
        await wait_nominal(bin_sim, gap_s)

    await wait_nominal(bin_sim, tail_s)
    log(
        f"scenario {scenario.name} done: bin at {bin_sim.level_g:.1f} g, "
        f"{phone_sim.frames_sent} frames sent, {len(bin_sim.screens)} screens received"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scripted toss sequence")
    parser.add_argument("--scenario", default="demo")
    parser.add_argument("--url", default="wss://localhost:8443/ws/bin", help="the bin socket")
    parser.add_argument("--phone-url", default=None, help="defaults to the bin url with /ws/phone")
    parser.add_argument("--expect-url", default=None, help="POST /api/sim/expect, dev only")
    parser.add_argument("--assets", default=str(ASSETS))
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument("--gap", type=float, default=4.0, help="seconds between steps")
    parser.add_argument("--lead", type=float, default=3.0, help="seconds of baseline first")
    parser.add_argument("--tail", type=float, default=3.0, help="seconds after the last step")
    parser.add_argument("--land-delay", type=float, default=0.3, help="frame before scale, seconds")
    parser.add_argument(
        "--speed", type=float, default=1.0, help="wall clock multiplier, 0 runs flat out"
    )
    parser.add_argument("--seed", type=int, default=None)
    return parser


async def amain(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenario = load_scenario(args.scenario)
    bin_sim = BinSim(
        url=args.url,
        sigma=scenario.sigma,
        insecure=args.insecure,
        speed=args.speed,
        seed=args.seed,
    )
    phone_sim = PhoneSim(
        url=args.phone_url or phone_url_for(args.url),
        assets_dir=Path(args.assets),
        insecure=args.insecure,
        speed=args.speed,
    )
    stop = asyncio.Event()
    runners = [
        asyncio.create_task(bin_sim.run(stop)),
        asyncio.create_task(phone_sim.run(stop)),
    ]
    try:
        await drive(
            scenario,
            bin_sim,
            phone_sim,
            gap_s=args.gap,
            lead_s=args.lead,
            tail_s=args.tail,
            land_delay_s=args.land_delay,
            expect_url=args.expect_url,
            insecure=args.insecure,
        )
    finally:
        stop.set()
        for task in runners:
            task.cancel()
        for task in runners:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(amain()))
    except KeyboardInterrupt:
        raise SystemExit(0) from None
