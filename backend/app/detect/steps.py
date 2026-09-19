"""Step detection on the weight stream.

PLAN.md section 7. The weight signal is a staircase plus noise plus short impact
transients. This module turns that signal into `Step` records.

Pure maths and no I/O. Nothing here imports the rest of the app, so it can be
tested on recorded arrays and reused by the simulator.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

StepKind = Literal["toss", "bag_change", "removal"]

MIN_STABLE_SAMPLES = 3


class Sample(BaseModel):
    """One reading off the scale. `t_ms` is the backend arrival clock in milliseconds."""

    model_config = ConfigDict(frozen=True)

    t_ms: float
    g: float


class DetectParams(BaseModel):
    """Tunables. Defaults match PLAN.md section 18."""

    step_min_g: float = 3.0
    settle_ms: float = 600.0
    bag_change_g: float = 200.0
    noise_sigma: float = 0.8
    stable_k: float = 2.0
    buffer_s: float = 10.0
    trace_pre_ms: float = 2000.0
    trace_post_ms: float = 1000.0

    @property
    def stable_std_g(self) -> float:
        """A window counts as stable when its standard deviation is below this."""
        return self.noise_sigma * self.stable_k

    @property
    def max_open_ms(self) -> float:
        """Give up on a candidate that never settles, so the buffer cannot grow forever."""
        return self.buffer_s * 1000.0


class Step(BaseModel):
    """One settled change in weight, with the evidence trace around it."""

    kind: StepKind
    t_open_ms: float
    t_settle_ms: float
    mass_g: float
    mass_err_g: float
    baseline_before_g: float
    baseline_after_g: float
    trace: list[list[float]] = Field(default_factory=list)


def samples_from_pairs(pairs: Iterable[tuple[float, float]]) -> list[Sample]:
    """Build samples from `(t_ms, g)` pairs. Convenient for tests and replay files."""
    return [Sample(t_ms=t, g=g) for t, g in pairs]


def estimate_noise_sigma(samples: Sequence[Sample]) -> float:
    """Estimate the per-sample noise sigma of a weight stream.

    Uses the median absolute deviation of successive differences, so a step in the
    middle of the recording moves one difference and not the estimate. Scaled by
    1.4826 to read as a standard deviation, then by 1/sqrt(2) because differencing
    two independent samples doubles the variance.
    """
    if len(samples) < MIN_STABLE_SAMPLES:
        return 0.0
    g = np.asarray([s.g for s in samples], dtype=float)
    d = np.diff(g)
    mad = float(np.median(np.abs(d - np.median(d))))
    return mad * 1.4826 / math.sqrt(2.0)


class _Window:
    """A trailing slice of the buffer, with the statistics the detector needs."""

    __slots__ = ("covered", "median", "n", "se", "std")

    def __init__(self, values: np.ndarray, covered: bool) -> None:
        self.n = int(values.size)
        self.covered = covered
        if self.n == 0:
            self.median = 0.0
            self.std = 0.0
            self.se = 0.0
            return
        self.median = float(np.median(values))
        if self.n < 2:
            self.std = 0.0
            self.se = 0.0
            return
        self.std = float(np.std(values, ddof=1))
        self.se = self.std / math.sqrt(self.n)

    def is_stable(self, max_std: float) -> bool:
        return self.covered and self.n >= MIN_STABLE_SAMPLES and self.std <= max_std


class StepDetector:
    """Streaming step detection.

    Feed samples in time order with `push`. It returns a `Step` on the sample where
    the step settles, and `None` otherwise.

    The trace on a returned step runs from `trace_pre_ms` before the open to the
    settle. The detector keeps the returned object and appends the tail out to
    `trace_post_ms` after the settle as later samples arrive, so the caller ends up
    with the full window without having to wait a second for the step itself. Copy
    the step if you need a snapshot that will not grow.
    """

    def __init__(self, params: DetectParams | None = None) -> None:
        self.params = params or DetectParams()
        self._buf: list[Sample] = []
        self._baseline: float | None = None
        self._baseline_se = 0.0
        self._open_t: float | None = None
        self._open_baseline = 0.0
        self._open_baseline_se = 0.0
        self._growing: list[tuple[Step, float]] = []

    @property
    def baseline_g(self) -> float | None:
        """The current stable baseline, or None while the detector is still syncing."""
        return self._baseline

    @property
    def is_open(self) -> bool:
        """True while a candidate step is open and waiting to settle."""
        return self._open_t is not None

    def push(self, sample: Sample) -> Step | None:
        self._buf.append(sample)
        self._grow_traces(sample)
        self._trim(sample.t_ms)
        if self._open_t is None:
            return self._push_idle(sample)
        return self._push_open(sample)

    def _push_idle(self, sample: Sample) -> Step | None:
        window = self._window(sample.t_ms, since=None)
        if window.is_stable(self.params.stable_std_g):
            self._baseline = window.median
            self._baseline_se = window.se
        if self._baseline is None:
            return None
        if abs(sample.g - self._baseline) > self.params.step_min_g:
            self._open_t = sample.t_ms
            self._open_baseline = self._baseline
            self._open_baseline_se = self._baseline_se
        return None

    def _push_open(self, sample: Sample) -> Step | None:
        open_t = self._open_t
        assert open_t is not None
        if sample.t_ms - open_t > self.params.max_open_ms:
            self._abort(resync=True)
            return None
        window = self._window(sample.t_ms, since=open_t)
        if not window.is_stable(self.params.stable_std_g):
            return None
        delta = window.median - self._open_baseline
        if abs(delta) <= self.params.step_min_g:
            # The signal came back to where it started. That was a transient, not a step.
            self._baseline = window.median
            self._baseline_se = window.se
            self._abort(resync=False)
            return None
        step = self._build_step(open_t, sample.t_ms, delta, window)
        self._baseline = window.median
        self._baseline_se = window.se
        self._open_t = None
        self._growing.append((step, sample.t_ms + self.params.trace_post_ms))
        return step

    def _build_step(self, open_t: float, settle_t: float, delta: float, after: _Window) -> Step:
        if delta > 0:
            kind: StepKind = "toss"
        elif abs(delta) > self.params.bag_change_g:
            kind = "bag_change"
        else:
            kind = "removal"
        err = math.hypot(self._open_baseline_se, after.se)
        trace_from = open_t - self.params.trace_pre_ms
        trace = [[s.t_ms, s.g] for s in self._buf if trace_from <= s.t_ms <= settle_t]
        return Step(
            kind=kind,
            t_open_ms=open_t,
            t_settle_ms=settle_t,
            mass_g=delta,
            mass_err_g=err,
            baseline_before_g=self._open_baseline,
            baseline_after_g=after.median,
            trace=trace,
        )

    def _abort(self, *, resync: bool) -> None:
        self._open_t = None
        if resync:
            self._baseline = None
            self._baseline_se = 0.0

    def _grow_traces(self, sample: Sample) -> None:
        if not self._growing:
            return
        still: list[tuple[Step, float]] = []
        for step, until in self._growing:
            if sample.t_ms <= until:
                step.trace.append([sample.t_ms, sample.g])
                still.append((step, until))
        self._growing = still

    def _trim(self, now_ms: float) -> None:
        oldest = now_ms - self.params.buffer_s * 1000.0
        if self._open_t is not None:
            oldest = min(oldest, self._open_t - self.params.trace_pre_ms)
        if self._buf and self._buf[0].t_ms >= oldest:
            return
        self._buf = [s for s in self._buf if s.t_ms >= oldest]

    def _window(self, t_end: float, *, since: float | None) -> _Window:
        start = t_end - self.params.settle_ms
        values: list[float] = []
        covered = False
        for s in self._buf:
            if since is not None and s.t_ms < since:
                continue
            if s.t_ms >= start:
                values.append(s.g)
            else:
                # A sample older than the window proves the window covers the full
                # settle time rather than being everything we happen to have.
                covered = True
        return _Window(np.asarray(values, dtype=float), covered)


def detect(samples: Sequence[Sample], params: DetectParams | None = None) -> list[Step]:
    """Detect every step in a recorded weight stream.

    This is `StepDetector` folded over the samples, so the batch and streaming
    answers cannot drift apart.
    """
    detector = StepDetector(params)
    steps: list[Step] = []
    for sample in samples:
        step = detector.push(sample)
        if step is not None:
            steps.append(step)
    return steps
