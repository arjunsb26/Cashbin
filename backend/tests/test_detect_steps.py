"""Step detection tests. PLAN.md section 19, the `steps` group."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.detect.steps import (
    DetectParams,
    Sample,
    StepDetector,
    detect,
    estimate_noise_sigma,
    samples_from_pairs,
)

RATE_HZ = 15.0
DT_MS = 1000.0 / RATE_HZ
SIGMA = 0.8


class Signal:
    """Builds a synthetic weight stream the way the bin behaves.

    A toss lands as an impact spike of three times the mass that rings down with a
    damped wobble that is back inside a gram between 430 ms and 680 ms depending on
    the mass, which is what `sim/bin_sim.py` emits and what the real load cell does.
    """

    def __init__(self, sigma: float = SIGMA, seed: int = 7, start_g: float = 0.0) -> None:
        self.rng = np.random.default_rng(seed)
        self.sigma = sigma
        self.t_ms = 0.0
        self.level = start_g
        self.samples: list[Sample] = []
        self._events: list[tuple[float, float, float, float]] = []

    def _value(self) -> float:
        g = self.level
        for t0, mass, overshoot, tau_ms in self._events:
            dt = self.t_ms - t0
            if dt < 0:
                continue
            wobble = overshoot * math.exp(-dt / tau_ms) * math.cos(2 * math.pi * 6.0 * dt / 1000.0)
            g += mass * wobble
        return g + float(self.rng.normal(0.0, self.sigma))

    def hold(self, seconds: float) -> Signal:
        n = round(seconds * RATE_HZ)
        for _ in range(n):
            self.samples.append(Sample(t_ms=self.t_ms, g=self._value()))
            self.t_ms += DT_MS
        return self

    def add(self, mass_g: float, overshoot: float = 2.0, tau_ms: float = 90.0) -> Signal:
        """Drop `mass_g` onto the scale at the current time."""
        self.level += mass_g
        self._events.append((self.t_ms, mass_g, overshoot, tau_ms))
        return self

    def drift(self, seconds: float, g_per_minute: float) -> Signal:
        n = round(seconds * RATE_HZ)
        per_sample = g_per_minute * (DT_MS / 60000.0)
        for _ in range(n):
            self.samples.append(Sample(t_ms=self.t_ms, g=self._value()))
            self.t_ms += DT_MS
            self.level += per_sample
        return self


SETTLE_BIAS_G = 0.6


def within_error(detected: float, intended: float, err: float) -> bool:
    """Three standard errors, plus the bit the standard error does not model.

    `mass_err_g` is white noise only. The scale is still ringing a little when the
    settle window opens, which biases the median by well under a gram. Measured over
    300 seeded runs of the demo masses the worst miss was 1.94 g and nothing fell
    outside this bar.
    """
    return abs(detected - intended) <= 3.0 * err + SETTLE_BIAS_G


def test_synthetic_staircase_recovers_five_tosses() -> None:
    masses = [95.0, 780.0, 62.0, 172.0, 310.0]
    sig = Signal(seed=11).hold(2.0)
    for m in masses:
        sig.add(m).hold(2.0)
    steps = detect(sig.samples)

    assert [s.kind for s in steps] == ["toss"] * 5
    for step, intended in zip(steps, masses, strict=True):
        assert step.mass_err_g > 0.0
        assert within_error(step.mass_g, intended, step.mass_err_g), (
            f"{step.mass_g:.2f} vs {intended} +/- {step.mass_err_g:.2f}"
        )


def test_impact_spike_does_not_create_a_step_or_inflate_the_mass() -> None:
    """A 200 ms spike of three times the mass must not show up in the answer."""
    sig = Signal(seed=3).hold(2.0)
    sig.add(100.0, overshoot=2.0, tau_ms=95.0).hold(2.0)
    steps = detect(sig.samples)

    assert len(steps) == 1
    peak = max(g for _, g in steps[0].trace)
    assert peak > 250.0, "the test signal must actually contain a spike"
    assert within_error(steps[0].mass_g, 100.0, steps[0].mass_err_g)


def test_pure_transient_is_rejected() -> None:
    """Somebody leans on the bin for 200 ms and lets go. No step."""
    sig = Signal(seed=5).hold(2.0)
    sig.add(300.0).hold(0.2)
    sig.add(-300.0).hold(2.0)
    assert detect(sig.samples) == []


def test_double_toss_400ms_apart_merges_at_the_default_settle_window() -> None:
    """Two tosses inside one 600 ms settle window cannot be told apart. Documented."""
    sig = Signal(seed=13).hold(2.0)
    sig.add(120.0).hold(0.4)
    sig.add(80.0).hold(2.0)
    steps = detect(sig.samples)

    assert len(steps) == 1
    assert within_error(steps[0].mass_g, 200.0, steps[0].mass_err_g)


def test_double_toss_400ms_apart_resolves_as_two_on_a_faster_settling_scale() -> None:
    """The settle window is what decides, not the gap. Damp the scale, shorten the
    window, and the same two tosses come back as two steps."""
    sig = Signal(seed=13).hold(2.0)
    sig.add(120.0, tau_ms=30.0).hold(0.4)
    sig.add(80.0, tau_ms=30.0).hold(2.0)
    steps = detect(sig.samples, DetectParams(settle_ms=150.0))

    assert len(steps) == 2
    assert within_error(steps[0].mass_g, 120.0, steps[0].mass_err_g)
    assert within_error(steps[1].mass_g, 80.0, steps[1].mass_err_g)


def test_bag_change_is_a_large_negative_step() -> None:
    sig = Signal(seed=17).hold(2.0)
    sig.add(1100.0).hold(2.0)
    sig.add(-1100.0).hold(2.0)
    steps = detect(sig.samples)

    assert [s.kind for s in steps] == ["toss", "bag_change"]
    assert within_error(steps[1].mass_g, -1100.0, steps[1].mass_err_g)
    assert steps[1].baseline_after_g == pytest.approx(0.0, abs=1.0)


def test_small_negative_step_is_a_removal() -> None:
    sig = Signal(seed=19).hold(2.0)
    sig.add(150.0).hold(2.0)
    sig.add(-40.0).hold(2.0)
    steps = detect(sig.samples)

    assert [s.kind for s in steps] == ["toss", "removal"]
    assert within_error(steps[1].mass_g, -40.0, steps[1].mass_err_g)


def test_slow_drift_produces_no_steps() -> None:
    """Half a gram a minute for ten minutes. The baseline follows it."""
    sig = Signal(seed=23).hold(2.0).drift(600.0, g_per_minute=0.5)
    assert detect(sig.samples) == []


def test_noise_sigma_estimate_on_a_flat_signal() -> None:
    sig = Signal(sigma=1.3, seed=29).hold(20.0)
    assert estimate_noise_sigma(sig.samples) == pytest.approx(1.3, rel=0.15)


def test_noise_sigma_estimate_survives_a_step() -> None:
    sig = Signal(sigma=0.6, seed=31).hold(10.0)
    sig.add(500.0, overshoot=0.0).hold(10.0)
    assert estimate_noise_sigma(sig.samples) == pytest.approx(0.6, rel=0.2)


def test_streaming_detector_agrees_with_the_batch_function() -> None:
    sig = Signal(seed=37).hold(2.0)
    for m in (95.0, 780.0, -60.0, 172.0):
        sig.add(m).hold(2.0)

    detector = StepDetector()
    streamed = [s for s in (detector.push(x) for x in sig.samples) if s is not None]
    batched = detect(sig.samples)

    assert [s.model_dump() for s in streamed] == [s.model_dump() for s in batched]


def test_trace_spans_two_seconds_before_open_to_one_after_settle() -> None:
    params = DetectParams()
    sig = Signal(seed=41).hold(3.0)
    sig.add(250.0).hold(3.0)
    step = detect(sig.samples, params)[0]

    first_t = step.trace[0][0]
    last_t = step.trace[-1][0]
    assert first_t >= step.t_open_ms - params.trace_pre_ms - DT_MS
    assert first_t <= step.t_open_ms - params.trace_pre_ms + DT_MS
    assert last_t == pytest.approx(step.t_settle_ms + params.trace_post_ms, abs=DT_MS)
    assert all(len(point) == 2 for point in step.trace)


def test_samples_from_pairs_round_trips() -> None:
    samples = samples_from_pairs([(0.0, 1.0), (66.7, 2.0)])
    assert [(s.t_ms, s.g) for s in samples] == [(0.0, 1.0), (66.7, 2.0)]


def test_empty_and_short_inputs_are_safe() -> None:
    assert detect([]) == []
    assert estimate_noise_sigma([]) == 0.0
    assert detect(samples_from_pairs([(0.0, 10.0), (66.0, 10.0)])) == []
