"""Deciding by what it costs to be wrong, not by the margin alone.

PLAN.md 21a item 28. At effort `none` eleven of Lane K's sixty eight answers on real
photographs were wrong, all at confidence 0.97 or better. Two of them were a cable against
a cable: same class, same flag, same material, so the entry, the tax and the carbon come
out identical whichever one wins. Asking a person to pick between those teaches the room
that the bin cannot tell a cable from a cable.

Two of the others were a power bank against a portable speaker, and that one matters: one
carries a battery flag and one does not, so the bin is blocked for one and not the other.
That pair still has to ask.
"""

from __future__ import annotations

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import (
    SAME_TREATMENT_KEY,
    CatalogFacts,
    Treatment,
    catalog_facts,
)
from app.models import CatalogItem, ItemClass

CABLE = Treatment(
    item_class=ItemClass.untracked,
    flags=frozenset({"electronics"}),
    materials=(("mixed_electronics", 1.0),),
)
BATTERY_THING = Treatment(
    item_class=ItemClass.untracked,
    flags=frozenset({"electronics", "battery"}),
    materials=(("portable_electronic_devices", 1.0),),
)


def facts(**treatments: Treatment) -> CatalogFacts:
    return CatalogFacts(
        labels=tuple(sorted(treatments)),
        classes={name: t.item_class for name, t in treatments.items()},
        priors={},
        treatments=dict(treatments),
    )


# The rule ---------------------------------------------------------------------


def test_two_cables_come_out_the_same_on_the_books() -> None:
    known = facts(usb_cable=CABLE, hdmi_cable=CABLE)
    assert known.same_treatment("usb_cable", "hdmi_cable") is True


def test_a_battery_makes_two_things_different() -> None:
    known = facts(power_bank=BATTERY_THING, portable_speaker=CABLE)
    assert known.same_treatment("power_bank", "portable_speaker") is False


def test_a_label_the_catalog_does_not_carry_is_never_the_same_as_anything() -> None:
    known = facts(usb_cable=CABLE)
    assert known.same_treatment("usb_cable", "something invented") is False
    assert known.same_treatment("one invention", "another invention") is False


def test_the_real_catalog_agrees_about_the_two_pairs(settings: Settings) -> None:
    """Read off `catalog.csv`, not out of this file."""
    from tests.test_identify_support import setup_db

    setup_db(settings)
    with session_scope() as session:
        known = catalog_facts(session)
    assert known.same_treatment("usb cable", "hdmi cable") is True
    assert known.same_treatment("power bank", "phone") is True
    assert known.same_treatment("usb cable", "power bank") is False
    assert known.same_treatment("bagel", "cookie") is True
    assert known.same_treatment("bagel", "usb cable") is False


def test_a_catalog_row_added_by_a_person_is_read_too(settings: Settings) -> None:
    from tests.test_identify_support import setup_db

    setup_db(settings)
    with session_scope() as session:
        session.add(
            CatalogItem(
                label="display cable",
                item_class=ItemClass.untracked,
                material_mix_json='{"mixed_electronics": 1.0}',
                regulatory_flags_json='["electronics"]',
            )
        )
    with session_scope() as session:
        known = catalog_facts(session)
    assert known.same_treatment("display cable", "usb cable") is True


# Through the decision ----------------------------------------------------------


async def _decide(settings: Settings, first: str, second: str) -> tuple[bool, dict[str, float]]:
    """Run one toss whose two best candidates are these, too close to call apart."""
    import json

    from app.identify.pipeline import Providers, identify_event
    from app.identify.stub import StubEstimatorProvider
    from app.models import Identification
    from app.schemas import VisionResult
    from tests.test_identify_pipeline import ScriptedVision
    from tests.test_identify_support import make_deps, make_event, make_jpeg, setup_db

    # The scale is deliberately useless here: a huge error bar makes the mass prior say the
    # same thing about both candidates, so what is under test is the decision rule and not
    # the fusion stage that runs before it.
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=212.0, mass_err_g=5000.0).id

    # 0.55 and 0.44: sure enough on its own, nowhere near `min_margin` apart.
    answer = VisionResult.model_validate(
        {
            "label": first,
            "class": "untracked",
            "confidence": 0.55,
            "candidates": [{"label": first, "p": 0.55}, {"label": second, "p": 0.44}],
        }
    )
    deps = make_deps(
        settings,
        providers=Providers(
            vision=ScriptedVision(answer), estimator=StubEstimatorProvider(), name="stub"
        ),
    )
    conf = deps.settings.model_copy(update={"confident_p": 0.5, "min_margin": 0.25})
    deps.settings = conf
    outcome = await identify_event(event_id, make_jpeg(), [], 212.0, 5000.0, deps)

    with session_scope() as session:
        rows = list(
            session.execute(
                Identification.__table__.select().where(
                    Identification.event_id == event_id
                )
            ).mappings()
        )
    final = [row for row in rows if row["is_final"]]
    stored = json.loads(final[0]["posterior_json"] or "{}") if final else {}
    return outcome.final, stored


async def test_a_cable_against_a_cable_is_answered(settings: Settings) -> None:
    final, posterior = await _decide(settings, "usb cable", "hdmi cable")
    assert final is True, "the books cannot tell these apart, so neither should the ask"
    assert posterior.get(SAME_TREATMENT_KEY) == 1.0, (
        "the drawer has to be able to say two candidates, same treatment"
    )


async def test_a_power_bank_against_a_cable_still_asks(settings: Settings) -> None:
    final, _posterior = await _decide(settings, "power bank", "usb cable")
    assert final is False, "one carries a battery and one does not, so a person decides"


async def test_the_marker_is_not_written_when_the_margin_carried_it(
    settings: Settings,
) -> None:
    """A clear win is a clear win, and nothing about it needs explaining."""
    import json

    from app.identify.pipeline import Providers, identify_event
    from app.identify.stub import StubEstimatorProvider
    from app.models import Identification
    from app.schemas import VisionResult
    from tests.test_identify_pipeline import ScriptedVision
    from tests.test_identify_support import make_deps, make_event, make_jpeg, setup_db

    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=40.0, mass_err_g=5000.0).id
    answer = VisionResult.model_validate(
        {"label": "usb cable", "class": "untracked", "confidence": 0.95}
    )
    deps = make_deps(
        settings,
        providers=Providers(
            vision=ScriptedVision(answer), estimator=StubEstimatorProvider(), name="stub"
        ),
    )
    outcome = await identify_event(event_id, make_jpeg(), [], 40.0, 5000.0, deps)
    assert outcome.final is True

    with session_scope() as session:
        rows = list(
            session.execute(
                Identification.__table__.select().where(
                    Identification.event_id == event_id
                )
            ).mappings()
        )
    final = [row for row in rows if row["is_final"]]
    posterior = json.loads(final[0]["posterior_json"] or "{}")
    assert SAME_TREATMENT_KEY not in posterior


def test_the_marker_cannot_collide_with_a_label() -> None:
    """A validated label is letters, digits, spaces and hyphens. This is not one."""
    from app.schemas import normalise_label

    try:
        normalise_label(SAME_TREATMENT_KEY)
    except ValueError:
        return
    raise AssertionError("the marker key has to be something no label could ever be")
