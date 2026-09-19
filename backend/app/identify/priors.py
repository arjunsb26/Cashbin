"""Mass prior fusion and the running prior update.

PLAN.md section 9 item 4. The scale already knows what the thing weighs, so a label whose
typical mass is nowhere near the reading should lose probability to one that fits. All of it
is plain arithmetic in Python, never a model call, per PLAN.md rule 2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# PLAN.md section 9: a prior built from fewer than three weighings is not evidence yet.
MIN_PRIOR_N = 3
_EPS = 1e-12


@dataclass(frozen=True)
class MassPrior:
    """What the system believes one label weighs, and how sure it is."""

    mean_g: float
    var: float
    n: int

    @property
    def usable(self) -> bool:
        return self.n >= MIN_PRIOR_N and self.var > 0.0


def normal_pdf(x: float, mean: float, var: float) -> float:
    """Normal density. Used as a likelihood, so the constant factor matters for the ratio."""
    if var <= 0.0:
        return 0.0
    return math.exp(-((x - mean) ** 2) / (2.0 * var)) / math.sqrt(2.0 * math.pi * var)


def _normalised(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= _EPS:
        return {}
    return {label: value / total for label, value in weights.items()}


def fuse(
    vision: dict[str, float],
    mass_g: float | None,
    mass_err_g: float | None,
    priors: dict[str, MassPrior],
) -> dict[str, float]:
    """Posterior over labels after the scale reading is taken into account.

    posterior(label) is proportional to p_vision(label) times Normal(mass; prior_mean,
    prior_var + mass_err^2). A label with fewer than three weighings behind it is skipped,
    and gets the average likelihood of the labels that were fused, so the mass reading
    neither rewards nor punishes a label it knows nothing about. With no usable prior at
    all, or with an unreadable mass, this returns the vision distribution unchanged.
    """
    base = _normalised({label: max(p, 0.0) for label, p in vision.items()})
    if not base or mass_g is None:
        return base

    err = float(mass_err_g or 0.0)
    likelihood: dict[str, float] = {}
    for label in base:
        prior = priors.get(label)
        if prior is None or not prior.usable:
            continue
        likelihood[label] = normal_pdf(mass_g, prior.mean_g, prior.var + err * err)

    if not likelihood:
        return base

    neutral = sum(likelihood.values()) / len(likelihood)
    weights = {label: p * likelihood.get(label, neutral) for label, p in base.items()}
    fused = _normalised(weights)
    return fused or base


def welford_update(prior: MassPrior, mass_g: float) -> MassPrior:
    """Fold one weighing into a running mean and variance.

    The first observation of a new label fixes the mean and leaves the variance at zero.
    A seeded catalog row carries `n = 1` with a deliberately wide variance, so that seed is
    kept as the running sum of squares rather than thrown away on the second weighing.
    """
    if prior.n <= 0:
        return MassPrior(mean_g=mass_g, var=0.0, n=1)
    n = prior.n + 1
    delta = mass_g - prior.mean_g
    mean = prior.mean_g + delta / n
    m2 = prior.var * max(prior.n - 1, 1) + delta * (mass_g - mean)
    var = max(m2, 0.0) / max(n - 1, 1)
    return MassPrior(mean_g=mean, var=var, n=n)
