"""What a toss meant, in the words its class earns.

PLAN.md 21a items 41, 30, 37 and 54. The figure alone says nothing: minus four dollars on
a bagel and minus four dollars on a laptop are different events. These cases go through
the real finalisation path, because a word that never reaches a surface is not a word.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.agent import sense_check
from app.config import Settings
from app.db import session_scope
from app.engine.records import (
    Condition,
    EstimateSource,
    ItemRecord,
    build_item_record,
    catalog_by_label,
)
from app.engine.records import (
    ItemClass as EngineClass,
)
from app.identify.pipeline import Providers, write_identification
from app.identify.providers import CallUsage, EstimatorProvider
from app.learn.corrections import apply_correction
from app.models import (
    Event,
    EventKind,
    EventStatus,
    IdentifyMethod,
    ItemClass,
    JournalEntry,
)
from app.models import (
    ItemRecord as ItemRecordRow,
)
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, get_bus
from app.pipeline import PipelineDeps, build_pipeline, still_usable
from app.schemas import CorrectionCreate, PhoneAsk, ScreenResult, ValueEstimate
from tests.test_identify_support import Listener, setup_db
from tests.test_pipeline_valuing import SlowEstimator

TODAY = date(2026, 3, 1)


class CheapEstimator:
    """Prices everything at what a pencil is worth: a thing nobody would buy."""

    name = "stub"

    def __init__(self, fmv_cents: int = 20) -> None:
        self.fmv_cents = fmv_cents
        self.last_call: CallUsage | None = None

    def estimate(
        self, label: str, vision: object, mass_g: float, crop: bytes | None = None,
        detail: str = "",
    ) -> ValueEstimate:
        return ValueEstimate.model_validate(
            {
                "label": label,
                "fmv": {"low": 10, "mid": self.fmv_cents, "high": 40},
                "repair": {"low": 0, "mid": 0, "high": 0},
                "replacement": {"low": 30, "mid": 50, "high": 90},
                "scrap": {"low": 0, "mid": 0, "high": 0},
                "material_mix": {"mixed_paper": 1.0},
            }
        )


def a_pipeline(
    settings: Settings, estimator: EstimatorProvider | None = None
) -> PipelineDeps:
    from app.db import get_session_factory

    pipe = build_pipeline(settings, get_session_factory(), get_bus())
    pipe.providers = Providers(
        vision=pipe.providers.vision,
        estimator=estimator or SlowEstimator(0.0),
        name="stub",
    )
    return pipe


def a_toss(label: str, cls: ItemClass, mass_g: float) -> int:
    with session_scope() as session:
        row = Event(kind=EventKind.toss, mass_g=mass_g, status=EventStatus.identified)
        session.add(row)
        session.flush()
        write_identification(
            session,
            event_id=int(row.id),
            method=IdentifyMethod.stub,
            label=label,
            item_class=cls,
            confidence=0.95,
            posterior={label: 0.95},
            is_final=True,
        )
        return int(row.id)


def screens(listener: Listener) -> list[ScreenResult]:
    return [m for m in listener.messages() if isinstance(m, ScreenResult)]


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    sense_check.reset_cache()


# The words, on the bin -----------------------------------------------------


async def test_food_the_catalog_prices_is_wasted_and_is_asked_nothing(
    settings: Settings,
) -> None:
    setup_db(settings)
    event_id = a_toss("pizza slice", ItemClass.inventory, 107.0)
    pipe = a_pipeline(settings)
    bin_screens = Listener(CHANNEL_BIN)
    phone = Listener(CHANNEL_PHONE)

    await pipe.finalise_event(event_id, "pizza slice", ItemClass.inventory, IdentifyMethod.stub)

    drawn = screens(bin_screens)
    assert drawn and drawn[-1].l1 == "Wasted"
    assert drawn[-1].big == "$1.00"
    assert not [m for m in phone.messages() if isinstance(m, PhoneAsk)]


async def test_a_tagged_asset_is_written_off(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        from app.models import Asset, AssetStatus, TaxMethod

        session.add(
            Asset(
                tag="bb-0002",
                description="mechanical keyboard",
                cost_cents=12_900,
                in_service_date="2025-09-20",
                book_life_months=36,
                tax_method=TaxMethod.bonus_100,
                status=AssetStatus.active,
            )
        )
    event_id = a_toss("bb-0002", ItemClass.fixed_asset, 900.0)
    pipe = a_pipeline(settings)
    bin_screens = Listener(CHANNEL_BIN)

    await pipe.finalise_event(event_id, "bb-0002", ItemClass.fixed_asset, IdentifyMethod.qr)

    drawn = screens(bin_screens)
    assert drawn and drawn[-1].l1 == "Written off"


async def test_a_pencil_is_still_usable(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("pencil", ItemClass.untracked, 6.0)
    pipe = a_pipeline(settings, CheapEstimator())
    bin_screens = Listener(CHANNEL_BIN)

    await pipe.finalise_event(event_id, "pencil", ItemClass.untracked, IdentifyMethod.stub)

    drawn = screens(bin_screens)
    assert drawn and drawn[-1].l2 == "Still usable"
    assert drawn[-1].l1 == "Worth about"


def a_record(**kwargs: object) -> ItemRecord:
    base: dict[str, object] = {
        "event_id": 1,
        "label": "pencil",
        "class": EngineClass.untracked,
        "mass_g": 6.0,
        "event_date": TODAY,
        "fmv_low": 20,
        "fmv_mid": 20,
        "fmv_high": 20,
        "fmv_source": EstimateSource.model_estimate,
    }
    base.update(kwargs)
    return ItemRecord.model_validate(base)


def test_what_still_usable_means() -> None:
    assert still_usable(a_record()) is True
    assert still_usable(a_record(condition=Condition.broken)) is False
    assert still_usable(a_record(fmv_mid=900, fmv_low=900, fmv_high=900)) is False
    assert still_usable(a_record(**{"class": EngineClass.inventory})) is False
    assert still_usable(a_record(material_mix={"corrugated": 1.0})) is False


# Food nobody priced --------------------------------------------------------


async def test_food_off_the_catalog_is_asked_what_it_cost(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("burrito", ItemClass.inventory, 400.0)
    pipe = a_pipeline(settings)
    phone = Listener(CHANNEL_PHONE)

    await pipe.finalise_event(event_id, "burrito", ItemClass.inventory, IdentifyMethod.stub)

    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    assert asks, "the bin priced food nobody priced without asking"
    assert asks[-1].question == "What did the whole thing cost?"
    with session_scope() as session:
        event = session.get(Event, event_id)
        assert event is not None and event.status is EventStatus.asking
        assert session.get(ItemRecordRow, event_id) is None


async def test_ten_dollars_and_a_quarter_is_two_fifty(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("burrito", ItemClass.inventory, 400.0)
    pipe = a_pipeline(settings)
    await pipe.finalise_event(event_id, "burrito", ItemClass.inventory, IdentifyMethod.stub)

    phone = Listener(CHANNEL_PHONE)
    await apply_correction(
        CorrectionCreate.model_validate({"event_id": event_id, "label": "10 dollars"}),
        pipe.identify,
    )
    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    assert asks and asks[-1].question == "How much of it is this?"

    await apply_correction(
        CorrectionCreate.model_validate({"event_id": event_id, "label": "a quarter"}),
        pipe.identify,
    )

    with session_scope() as session:
        row = session.get(ItemRecordRow, event_id)
        assert row is not None
        assert row.cost_basis_cents == 250
        assert row.label == "burrito"


# The empty container -------------------------------------------------------


def test_an_empty_can_is_the_can_and_a_full_one_is_the_drink() -> None:
    catalog = catalog_by_label()["energy drink can"]
    empty = build_item_record(
        event_id=1,
        label="energy drink can",
        item_class=EngineClass.inventory,
        mass_g=12.0,
        event_date=TODAY,
        catalog=catalog,
    )
    assert empty.empty_container is True
    assert empty.cost_basis_cents is None
    assert empty.description == "empty energy drink can"
    assert set(empty.material_mix) == {"aluminum_cans"}
    assert "food" not in empty.regulatory_flags

    full = build_item_record(
        event_id=2,
        label="energy drink can",
        item_class=EngineClass.inventory,
        mass_g=250.0,
        event_date=TODAY,
        catalog=catalog,
    )
    assert full.empty_container is False
    # 250 g of a 260 g unit that cost 140 cents. The whole can is $1.40.
    assert full.cost_basis_cents == 135
    assert full.cost_basis_source is EstimateSource.catalog


async def test_an_empty_can_posts_nothing_and_says_recycle(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("energy drink can", ItemClass.inventory, 12.0)
    pipe = a_pipeline(settings)
    bin_screens = Listener(CHANNEL_BIN)

    await pipe.finalise_event(
        event_id, "energy drink can", ItemClass.inventory, IdentifyMethod.stub
    )

    with session_scope() as session:
        assert (
            session.scalars(
                select(JournalEntry.id).where(JournalEntry.event_id == event_id)
            ).first()
            is None
        ), "an empty can was written off as wasted drink"
    drawn = screens(bin_screens)
    assert drawn and drawn[-1].l2 == "Recycle, not trash"
    assert drawn[-1].l1 != "Wasted"


async def test_a_full_can_is_still_wasted_money(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("energy drink can", ItemClass.inventory, 260.0)
    pipe = a_pipeline(settings)
    bin_screens = Listener(CHANNEL_BIN)

    await pipe.finalise_event(
        event_id, "energy drink can", ItemClass.inventory, IdentifyMethod.stub
    )

    drawn = screens(bin_screens)
    assert drawn and drawn[-1].l1 == "Wasted"
    assert drawn[-1].big == "$1.40"
