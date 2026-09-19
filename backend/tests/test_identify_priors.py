"""Mass prior fusion and the running prior. PLAN.md section 19, the `priors` tests."""

from __future__ import annotations

import pytest

from app.identify.priors import MIN_PRIOR_N, MassPrior, fuse, welford_update


def prior(mean: float, var: float, n: int = 5) -> MassPrior:
    return MassPrior(mean_g=mean, var=var, n=n)


def test_fusion_moves_probability_to_the_label_whose_mass_fits() -> None:
    vision = {"bagel": 0.5, "keyboard": 0.5}
    priors = {"bagel": prior(95.0, 100.0), "keyboard": prior(900.0, 2500.0)}
    fused = fuse(vision, mass_g=96.0, mass_err_g=2.0, priors=priors)
    assert fused["bagel"] > 0.99
    assert fused["bagel"] > vision["bagel"]
    assert sum(fused.values()) == pytest.approx(1.0)


def test_a_flat_prior_changes_nothing() -> None:
    vision = {"bagel": 0.6, "cookie": 0.4}
    flat = {"bagel": prior(100.0, 400.0), "cookie": prior(100.0, 400.0)}
    fused = fuse(vision, mass_g=250.0, mass_err_g=5.0, priors=flat)
    assert fused["bagel"] == pytest.approx(0.6)
    assert fused["cookie"] == pytest.approx(0.4)


def test_a_thin_prior_is_skipped_and_lands_in_the_middle() -> None:
    third = 1.0 / 3.0
    vision = {"bagel": third, "keyboard": third, "mystery": third}
    priors = {
        "bagel": prior(95.0, 100.0),
        "keyboard": prior(900.0, 2500.0),
        # Two weighings is not evidence yet, however well this one would have fitted.
        "mystery": MassPrior(mean_g=95.0, var=100.0, n=MIN_PRIOR_N - 1),
    }
    fused = fuse(vision, mass_g=96.0, mass_err_g=2.0, priors=priors)
    assert fused["bagel"] > fused["mystery"] > fused["keyboard"]
    assert sum(fused.values()) == pytest.approx(1.0)


def test_one_usable_prior_on_its_own_cannot_discriminate() -> None:
    vision = {"bagel": 0.5, "mystery": 0.5}
    priors = {"bagel": prior(95.0, 100.0)}
    fused = fuse(vision, mass_g=400.0, mass_err_g=2.0, priors=priors)
    assert fused == pytest.approx(vision)


def test_no_usable_prior_leaves_the_vision_answer_alone() -> None:
    vision = {"bagel": 0.7, "cookie": 0.3}
    assert fuse(vision, 95.0, 2.0, {}) == pytest.approx(vision)
    thin = {"bagel": MassPrior(95.0, 100.0, 1)}
    assert fuse(vision, 95.0, 2.0, thin) == pytest.approx(vision)


def test_an_unknown_mass_leaves_the_vision_answer_alone() -> None:
    vision = {"bagel": 0.7, "cookie": 0.3}
    assert fuse(vision, None, None, {"bagel": prior(95.0, 100.0)}) == pytest.approx(vision)


def test_the_vision_input_is_normalised_first() -> None:
    fused = fuse({"bagel": 2.0, "cookie": 2.0}, None, None, {})
    assert fused == {"bagel": 0.5, "cookie": 0.5}


def test_scale_error_widens_the_likelihood() -> None:
    vision = {"bagel": 0.5, "pizza slice": 0.5}
    priors = {"bagel": prior(95.0, 25.0), "pizza slice": prior(107.0, 25.0)}
    sharp = fuse(vision, 96.0, 1.0, priors)
    blunt = fuse(vision, 96.0, 40.0, priors)
    assert sharp["bagel"] > blunt["bagel"] > 0.5


def test_the_first_weighing_of_a_new_label_fixes_the_mean() -> None:
    updated = welford_update(MassPrior(0.0, 0.0, 0), 92.0)
    assert updated == MassPrior(mean_g=92.0, var=0.0, n=1)


def test_the_running_mean_and_variance_match_the_plain_formula() -> None:
    values = [90.0, 100.0, 110.0]
    current = MassPrior(0.0, 0.0, 0)
    for value in values:
        current = welford_update(current, value)
    assert current.n == 3
    assert current.mean_g == pytest.approx(100.0)
    # Sample variance of 90, 100, 110 is 100.
    assert current.var == pytest.approx(100.0)


def test_a_seeded_catalog_row_keeps_its_wide_variance() -> None:
    seeded = MassPrior(mean_g=95.0, var=3249.0, n=1)
    updated = welford_update(seeded, 97.0)
    assert updated.n == 2
    assert updated.mean_g == pytest.approx(96.0)
    assert updated.var > 3000.0
