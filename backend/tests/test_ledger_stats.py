"""Stats over a range: buckets, categories, averages, and suggestions that behave.

The fixture is ten tickets across three days, built so the silly sentences are the
ones a careless version would write: a thirty cent napkin as the top category, and
a trend drawn off a single ticket.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import session_scope
from app.ledger import stats

DAY_ONE = date(2026, 9, 14)
DAY_TWO = date(2026, 9, 15)
DAY_THREE = date(2026, 9, 16)


def _at(day: date, minute: int) -> str:
    return f"{day.isoformat()}T12:{minute:02d}:00+00:00"


def _toss(
    session: Session,
    day: date,
    minute: int,
    *,
    label: str,
    item_class: models.ItemClass,
    mass_g: float,
    material: dict[str, float],
    flags: list[str],
    cost_basis_cents: int = 0,
    book_value_cents: int = 0,
    fmv_mid: int | None = None,
    status: models.EventStatus = models.EventStatus.posted,
    human: bool = False,
    options: list[tuple[models.OptionKind, bool, int, float, float, int | None]] | None = None,
) -> models.Event:
    event = models.Event(
        created_at=_at(day, minute),
        kind=models.EventKind.toss,
        mass_g=mass_g,
        mass_err_g=1.0,
        status=status,
    )
    session.add(event)
    session.flush()
    session.add(
        models.ItemRecord(
            event_id=event.id,
            label=label,
            item_class=item_class,
            mass_g=mass_g,
            condition="unknown",
            material_mix_json=json.dumps(material),
            regulatory_flags_json=json.dumps(flags),
            cost_basis_cents=cost_basis_cents,
            book_value_cents=book_value_cents,
            fmv_mid=fmv_mid,
        )
    )
    for option, allowed, net, co2e, landfill, rank in options or []:
        session.add(
            models.OptionScore(
                event_id=event.id,
                option=option,
                allowed=allowed,
                cash_cents=net,
                tax_effect_cents=0,
                net_after_tax_cents=net,
                kg_co2e=co2e,
                kg_landfill=landfill,
                notes_json=json.dumps([]),
                rule_ids_json=json.dumps([]),
                rank=rank,
            )
        )
    session.add(
        models.Identification(
            event_id=event.id,
            method=models.IdentifyMethod.human if human else models.IdentifyMethod.cloud,
            label=label,
            confidence=0.9,
            is_final=True,
        )
    )
    session.flush()
    return event


def build_range(session: Session) -> None:
    """Ten tickets across three days: food, packaging, an asset, and two untracked things."""
    _toss(
        session, DAY_ONE, 1, label="pizza slice", item_class=models.ItemClass.inventory,
        mass_g=107.0, material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=400,
        options=[
            (models.OptionKind.trash, True, -3, 0.5, 0.107, 2),
            (models.OptionKind.donate, True, 147, 0.02, 0.0, 1),
        ],
    )
    _toss(
        session, DAY_ONE, 2, label="bagel", item_class=models.ItemClass.inventory,
        mass_g=95.0, material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=350,
        options=[
            (models.OptionKind.trash, True, -2, 0.44, 0.095, 1),
        ],
    )
    _toss(
        session, DAY_ONE, 3, label="paper napkin", item_class=models.ItemClass.inventory,
        mass_g=4.0, material={"mixed_paper": 1.0}, flags=[], cost_basis_cents=30,
        options=[(models.OptionKind.trash, True, -1, 0.01, 0.004, 1)],
    )
    _toss(
        session, DAY_TWO, 4, label="cardboard box", item_class=models.ItemClass.inventory,
        mass_g=250.0, material={"corrugated_containers": 1.0}, flags=[],
        cost_basis_cents=120,
        options=[
            (models.OptionKind.trash, True, -5, 1.1, 0.25, 2),
            (models.OptionKind.recycle, True, 6, -0.8, 0.0, 1),
        ],
    )
    _toss(
        session, DAY_TWO, 5, label="paper cup", item_class=models.ItemClass.inventory,
        mass_g=45.0, material={"mixed_paper": 1.0}, flags=[], cost_basis_cents=12,
        options=[(models.OptionKind.trash, True, -1, 0.2, 0.045, 1)],
        human=True,
    )
    _toss(
        session, DAY_TWO, 6, label="mechanical keyboard",
        item_class=models.ItemClass.fixed_asset, mass_g=900.0,
        material={"mixed_plastics": 0.6, "steel_cans": 0.4}, flags=["electronics"],
        book_value_cents=3000,
        options=[
            (models.OptionKind.trash, False, -630, 2.4, 0.9, None),
            (models.OptionKind.recycle, True, -600, 0.9, 0.0, 1),
        ],
    )
    _toss(
        session, DAY_THREE, 7, label="office chair", item_class=models.ItemClass.untracked,
        mass_g=6000.0, material={"mixed_plastics": 1.0}, flags=[], fmv_mid=9000,
        options=[
            (models.OptionKind.trash, True, -5, 3.0, 6.0, 2),
            (models.OptionKind.resell, True, 7110, -8.0, 0.0, 1),
        ],
    )
    _toss(
        session, DAY_THREE, 8, label="desk lamp", item_class=models.ItemClass.untracked,
        mass_g=800.0, material={"mixed_plastics": 1.0}, flags=[], fmv_mid=2500,
        options=[
            (models.OptionKind.trash, True, -5, 0.8, 0.8, 2),
            (models.OptionKind.resell, True, 1975, -2.0, 0.0, 1),
        ],
    )
    _toss(
        session, DAY_THREE, 9, label="coffee grounds", item_class=models.ItemClass.inventory,
        mass_g=500.0, material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=200,
        options=[(models.OptionKind.trash, True, -3, 1.0, 0.5, 1)],
        status=models.EventStatus.asking,
    )
    _toss(
        session, DAY_THREE, 10, label="plastic tub", item_class=models.ItemClass.inventory,
        mass_g=60.0, material={"mixed_plastics": 1.0}, flags=[], cost_basis_cents=80,
        options=[(models.OptionKind.trash, True, -1, 0.3, 0.06, 1)],
    )
    session.commit()


def _loaded(session: Session) -> tuple[stats.Loaded, list[stats.Bucket]]:
    loaded = stats.load(session, DAY_ONE, DAY_THREE)
    return loaded, stats.fill_buckets(loaded, DAY_ONE, DAY_THREE, stats.BUCKET_DAY)


def test_days_come_back_in_order_with_their_totals(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        _, buckets = _loaded(session)

    rows: list[dict[str, Any]] = [row.as_dict() for row in buckets]
    assert [row["start"] for row in rows] == [
        "2026-09-14", "2026-09-15", "2026-09-16"
    ]
    assert [row["tosses"] for row in rows] == [3, 3, 4]
    assert rows[0]["wasted_cents"] == 780
    assert rows[1]["book_loss_cents"] == 3000
    assert rows[2]["estimated_value_cents"] == 11500
    assert rows[2]["asks"] == 1


def test_a_week_bucket_holds_the_whole_range(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        loaded = stats.load(session, DAY_ONE, DAY_THREE)
        weekly = stats.fill_buckets(loaded, DAY_ONE, DAY_THREE, stats.BUCKET_WEEK)

    assert len(weekly) == 1
    row = weekly[0].as_dict()
    assert row["start"] == "2026-09-14"
    assert row["tosses"] == 10
    assert row["wasted_cents"] == 1192


def test_categories_come_from_the_class_the_flags_and_the_mix(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        loaded = stats.load(session, DAY_ONE, DAY_THREE)
        weekly = stats.fill_buckets(loaded, DAY_ONE, DAY_THREE, stats.BUCKET_WEEK)

    table = {row["category"]: row for row in weekly[0].as_dict()["by_category"]}
    assert table["food"]["tosses"] == 3
    assert table["packaging"]["tosses"] == 4
    # The keyboard carries the electronics flag, so it is e-waste before it is equipment.
    assert table["e-waste"]["tosses"] == 1
    assert "equipment" not in table
    # The chair and the lamp are plastic, and neither one is packaging.
    assert table["other"]["tosses"] == 2


def test_first_try_accuracy_counts_what_the_model_settled(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        _, buckets = _loaded(session)

    # Day two has three tickets and a person settled one of them.
    assert buckets[1].as_dict()["first_try_accuracy"] == 0.6667


def test_averages_are_per_day_across_the_whole_range(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        _, buckets = _loaded(session)

    found = stats.averages(buckets, DAY_ONE, DAY_THREE)
    assert found["days"] == 3.0
    assert found["tosses_per_day"] == round(10 / 3, 3)
    assert found["wasted_cents_per_day"] == round(1192 / 3, 1)


def test_an_empty_day_is_still_drawn(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        loaded = stats.load(session, DAY_ONE, date(2026, 9, 18))
        buckets = stats.fill_buckets(loaded, DAY_ONE, date(2026, 9, 18), stats.BUCKET_DAY)

    assert [row.tosses for row in buckets] == [3, 3, 4, 0, 0]
    assert buckets[-1].as_dict()["by_category"] == []
    assert buckets[-1].as_dict()["first_try_accuracy"] is None


# Suggestions --------------------------------------------------------------


def test_suggestions_state_facts_with_their_amounts(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        loaded, buckets = _loaded(session)
        lines = stats.suggestions(loaded, buckets)

    assert 1 <= len(lines) <= stats.MAX_SUGGESTIONS
    joined = " ".join(lines)
    assert "percent of" in joined
    for word in ("consider", "should", "optimize", "leverage"):
        assert word not in joined.lower()


def test_a_percentage_never_appears_without_its_base(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        loaded, buckets = _loaded(session)
        lines = stats.suggestions(loaded, buckets)

    for line in lines:
        if "percent" in line:
            assert "percent of" in line


def test_a_thirty_cent_napkin_never_becomes_a_headline(settings: Settings) -> None:
    """Only the napkin in the range. Thirty cents and one ticket is not worth a sentence."""
    with session_scope() as session:
        _toss(
            session, DAY_ONE, 1, label="paper napkin",
            item_class=models.ItemClass.inventory, mass_g=4.0,
            material={"mixed_paper": 1.0}, flags=[], cost_basis_cents=30,
            options=[(models.OptionKind.trash, True, -1, 0.01, 0.004, 1)],
        )
        session.commit()
        loaded, buckets = _loaded(session)
        lines = stats.suggestions(loaded, buckets)

    assert lines == []


def test_three_small_tickets_do_clear_the_floor(settings: Settings) -> None:
    """The count rule, not the money rule. Three of anything is a pattern."""
    with session_scope() as session:
        for minute in (1, 2, 3):
            _toss(
                session, DAY_ONE, minute, label="paper napkin",
                item_class=models.ItemClass.inventory, mass_g=4.0,
                material={"mixed_paper": 1.0}, flags=[], cost_basis_cents=30,
                options=[(models.OptionKind.trash, True, -1, 0.01, 0.004, 1)],
            )
        session.commit()
        loaded, buckets = _loaded(session)
        lines = stats.suggestions(loaded, buckets)

    assert len(lines) == 1
    assert "3 tickets" in lines[0]


def test_no_suggestion_offers_to_sell_food(settings: Settings) -> None:
    """Resale is blocked on food, so the resale sentence can never count a bagel."""
    with session_scope() as session:
        build_range(session)
        loaded, buckets = _loaded(session)
        lines = stats.suggestions(loaded, buckets)

    resale = [line for line in lines if "selling" in line]
    assert len(resale) == 1
    # The chair and the lamp, not the food. 9000 plus 2500 cents.
    assert "115.00" in resale[0]
    assert "2 items" in resale[0]


def test_one_ticket_is_never_a_trend(settings: Settings) -> None:
    with session_scope() as session:
        _toss(
            session, DAY_ONE, 1, label="pizza slice",
            item_class=models.ItemClass.inventory, mass_g=107.0,
            material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=9000,
            options=[(models.OptionKind.trash, True, -3, 0.5, 0.107, 1)],
        )
        session.commit()
        loaded, buckets = _loaded(session)
        earlier = stats.load(session, date(2026, 9, 11), date(2026, 9, 13))
        earlier_buckets = stats.fill_buckets(
            earlier, date(2026, 9, 11), date(2026, 9, 13), stats.BUCKET_DAY
        )
        lines = stats.suggestions(loaded, buckets, earlier_buckets)

    assert not any("range before this one" in line for line in lines)


def test_a_trend_is_drawn_when_both_ranges_are_big_enough(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        for minute in range(1, 7):
            _toss(
                session, date(2026, 9, 12), minute, label="pizza slice",
                item_class=models.ItemClass.inventory, mass_g=107.0,
                material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=100,
                options=[(models.OptionKind.trash, True, -3, 0.5, 0.107, 1)],
            )
        session.commit()
        loaded, buckets = _loaded(session)
        earlier = stats.load(session, date(2026, 9, 11), date(2026, 9, 13))
        earlier_buckets = stats.fill_buckets(
            earlier, date(2026, 9, 11), date(2026, 9, 13), stats.BUCKET_DAY
        )
        lines = stats.suggestions(loaded, buckets, earlier_buckets)

    trend = [line for line in lines if "range before this one" in line]
    assert len(trend) == 1
    assert "up" in trend[0]
    assert "5.92" in trend[0]


def test_at_most_five_sentences_come_back(settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)
        for minute in range(1, 7):
            _toss(
                session, date(2026, 9, 12), minute, label="pizza slice",
                item_class=models.ItemClass.inventory, mass_g=107.0,
                material={"food_waste": 1.0}, flags=["food"], cost_basis_cents=100,
                options=[(models.OptionKind.trash, True, -3, 0.5, 0.107, 1)],
            )
        session.commit()
        loaded, buckets = _loaded(session)
        earlier = stats.load(session, date(2026, 9, 11), date(2026, 9, 13))
        earlier_buckets = stats.fill_buckets(
            earlier, date(2026, 9, 11), date(2026, 9, 13), stats.BUCKET_DAY
        )
        lines = stats.suggestions(loaded, buckets, earlier_buckets)

    assert len(lines) <= stats.MAX_SUGGESTIONS
    assert len(set(lines)) == len(lines)
