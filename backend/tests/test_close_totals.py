"""The totals side of the close: write-offs, disposals, missed money, carbon, ghosts."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.db import session_scope
from app.ledger import close as close_module
from tests.test_close_fixtures import (
    PERIOD_END,
    PERIOD_START,
    Scenario,
    add_ghost_asset,
    build_clean_scenario,
)

Closed = tuple[Scenario, close_module.CloseResult]


@pytest.fixture
def closed(settings: Settings) -> Closed:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        result, _rows = close_module.compute_close(
            session, PERIOD_START, PERIOD_END, settings
        )
    return scenario, result


def test_write_offs_group_by_label(closed: Closed) -> None:
    _scenario, result = closed
    write_offs = result.totals["write_offs"]
    labels = {row["label"]: row for row in write_offs["rows"]}
    assert set(labels) == {
        "pizza slice",
        "bagel",
        "cardboard box",
        "mechanical keyboard",
        "paper cup",
    }
    assert labels["pizza slice"]["cents"] == 100
    # The asset leaves the books at its book value, not at an inventory cost.
    assert labels["mechanical keyboard"]["cents"] == 3000
    assert write_offs["total_cents"] == 100 + 33 + 40 + 3000 + 12
    assert write_offs["total_mass_g"] == pytest.approx(1397.0)
    assert write_offs["count"] == 5


def test_asset_disposal_carries_book_and_tax(closed: Closed) -> None:
    _scenario, result = closed
    disposals = result.totals["asset_disposals"]
    assert disposals["count"] == 1
    row = disposals["rows"][0]
    assert row["tag"] == "bb-0002"
    assert row["book_value_cents"] == 3000
    assert row["book_loss_cents"] == 3000
    assert row["tax_loss_cents"] == 2000
    assert row["abandonment"] is True
    assert row["book_minus_tax_cents"] == 1000
    # A loss on an abandonment reads as a negative subtotal on that line.
    assert disposals["form_4797_part_ii_line_10_cents"] == -2000


def test_missed_opportunity_splits_by_best_option(closed: Closed) -> None:
    _scenario, result = closed
    missed = result.totals["missed_opportunity"]
    by_option = missed["by_option"]
    assert by_option["would_have_donated_cents"] == 150 + 62
    assert by_option["would_have_resold_cents"] == 1830
    assert by_option["would_have_recycled_cents"] == 11
    assert by_option["would_have_repaired_cents"] == 0
    assert missed["total_cents"] == sum(by_option.values())
    assert missed["rows"][0]["label"] == "mechanical keyboard"


def test_sustainability_block_is_labelled_and_counted(closed: Closed) -> None:
    _scenario, result = closed
    block = result.totals["sustainability"]
    assert block["title"] == close_module.SUSTAINABILITY_TITLE
    assert block["kg_to_landfill"] == pytest.approx(1.397)
    # Everything but the paper cup had a better option than the bin.
    assert block["kg_diverted_if_followed"] == pytest.approx(1.352)
    assert block["kg_ewaste"] == pytest.approx(0.9)
    assert block["cheapest_equals_greenest_pct"] == pytest.approx(80.0)
    assert block["kg_co2e_avoided"] == pytest.approx(
        block["kg_co2e_actual"] - block["kg_co2e_best"]
    )
    assert block["source"] == "EPA WARM"


def test_clean_period_has_no_ghosts(closed: Closed) -> None:
    _scenario, result = closed
    assert result.totals["ghost_assets"]["count"] == 0
    assert result.totals["ghost_assets"]["possible_unrecorded_assets"] == []


def test_ghost_asset_is_found(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        add_ghost_asset(session, scenario.toss_ids[0])
    with session_scope() as session:
        result, _rows = close_module.compute_close(
            session, PERIOD_START, PERIOD_END, settings
        )
    ghosts = result.totals["ghost_assets"]
    assert ghosts["count"] == 1
    assert ghosts["rows"][0]["tag"] == "bb-0007"
    assert ghosts["rows"][0]["event_id"] == scenario.toss_ids[0]


def test_possible_unrecorded_asset_is_flagged(settings: Settings) -> None:
    from app import models

    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        record = session.get(models.ItemRecord, scenario.toss_ids[4])
        assert record is not None
        record.item_class = models.ItemClass.untracked
        record.fmv_mid = 90_000
        record.fmv_source = "model_estimate"
        session.commit()
    with session_scope() as session:
        result, _rows = close_module.compute_close(
            session, PERIOD_START, PERIOD_END, settings
        )
    flags = result.totals["ghost_assets"]["possible_unrecorded_assets"]
    assert len(flags) == 1
    assert flags[0]["kind"] == "possible_unrecorded_asset"
    assert flags[0]["event_id"] == scenario.toss_ids[4]


def test_a_period_outside_the_events_is_empty(settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    with session_scope() as session:
        result, _rows = close_module.compute_close(
            session, "2026-10-01", "2026-10-02", settings
        )
    assert result.totals["events"]["tosses"] == 0
    assert result.totals["write_offs"]["rows"] == []
    assert result.totals["sustainability"]["kg_to_landfill"] == 0.0
