"""The five self-checks. Clean passes; each failure is one deliberate change away."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.config import Settings
from app.db import session_scope
from app.ledger import close as close_module
from app.schemas import CloseCheck
from tests.test_close_fixtures import (
    PERIOD_END,
    PERIOD_START,
    build_clean_scenario,
    delete_event,
)


def run(settings: Settings) -> close_module.CloseResult:
    with session_scope() as session:
        return close_module.compute_close(session, PERIOD_START, PERIOD_END, settings)[0]


def by_id(result: close_module.CloseResult) -> dict[str, CloseCheck]:
    return {check.id: check for check in result.checks}


def test_clean_scenario_passes_every_check(settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    result = run(settings)
    assert [check.result for check in result.checks] == ["pass"] * 5
    assert result.status == close_module.STATUS_CLEAN
    assert result.needs_investigation is False


def test_mass_check_draws_the_balance(settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    check = by_id(run(settings))["mass_conservation"]
    lines = check.detail.splitlines()
    assert lines[0].startswith("Scale reads")
    assert lines[0].rstrip().endswith("1,397 g")
    assert lines[1].startswith("Tickets sum to")
    assert lines[1].rstrip().endswith("1,397 g")
    assert lines[2].startswith("Difference")
    assert "within +/-" in lines[2]
    assert lines[2].rstrip().endswith("Pass")
    assert check.numbers["removed_g"] == pytest.approx(452.0)
    assert check.numbers["scale_reads_g"] == pytest.approx(1397.0)


def test_deleting_one_event_fails_mass_conservation(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        delete_event(session, scenario.toss_ids[2])

    result = run(settings)
    check = by_id(result)["mass_conservation"]
    assert check.result == "fail"
    # The cardboard box weighed 250 g and is the whole of the gap.
    assert check.numbers["difference_g"] == pytest.approx(250.0)
    assert check.numbers["tickets_g"] == pytest.approx(1147.0)
    assert check.numbers["scale_reads_g"] == pytest.approx(1397.0)
    assert check.numbers["difference_g"] > check.numbers["tolerance_g"]
    assert "250 g" in check.detail
    assert check.detail.rstrip().splitlines()[2].endswith("Fail")
    assert result.status == close_module.STATUS_NEEDS_REVIEW
    assert result.needs_investigation is True


def test_the_tolerance_is_three_sigma_with_the_step_floor() -> None:
    assert close_module.mass_tolerance([3.0, 4.0], 3.0) == pytest.approx(15.0)
    # Perfect errors do not make the band zero: the scale's own step is the floor.
    assert close_module.mass_tolerance([0.0, 0.0], 3.0) == pytest.approx(3.0)


def test_a_missing_tare_falls_back_to_the_first_sample(settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    with session_scope() as session:
        row = session.get(models.Setting, "last_tare")
        assert row is not None
        session.delete(row)
        session.commit()
    check = by_id(run(settings))["mass_conservation"]
    assert check.result == "pass"
    assert "no tare was recorded" in check.detail


def test_an_unbalanced_entry_fails_the_ledger_check(settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    with session_scope() as session:
        row = session.scalars(
            select(models.JournalLine).order_by(models.JournalLine.id).limit(1)
        ).first()
        assert row is not None
        row.debit_cents += 500
        session.commit()

    check = by_id(run(settings))["ledger_balance"]
    assert check.result == "fail"
    assert check.numbers["unbalanced_entries"] == 1.0
    assert "do not balance" in check.detail


def test_a_disposed_asset_with_no_entry_fails_the_register_check(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        delete_event(session, scenario.asset_event_id)

    check = by_id(run(settings))["register_consistency"]
    assert check.result == "fail"
    assert check.numbers["missing_entries"] == 1.0
    assert "bb-0002" in check.detail


def test_an_unanswered_ask_warns(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        event = session.get(models.Event, scenario.toss_ids[1])
        assert event is not None
        event.status = models.EventStatus.asking
        session.commit()

    result = run(settings)
    check = by_id(result)["unresolved_asks"]
    assert check.result == "warn"
    assert check.numbers["asking"] == 1.0
    assert "1 ticket is still waiting" in check.detail
    assert result.status == close_module.STATUS_NEEDS_REVIEW


def test_mostly_human_labels_warn(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        for ident in session.scalars(
            select(models.Identification).where(
                models.Identification.event_id.in_(scenario.toss_ids[:4])
            )
        ):
            ident.method = models.IdentifyMethod.human
        session.commit()

    check = by_id(run(settings))["low_confidence_share"]
    assert check.result == "warn"
    assert check.numbers["settled_by_person"] == 4.0
    assert check.numbers["share"] == pytest.approx(0.8)


def test_a_void_ticket_leaves_the_books(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        event = session.get(models.Event, scenario.toss_ids[4])
        assert event is not None
        event.status = models.EventStatus.void
        session.commit()

    result = run(settings)
    assert result.totals["events"]["counted"] == 4
    labels = {row["label"] for row in result.totals["write_offs"]["rows"]}
    assert "paper cup" not in labels


def test_ranking_puts_the_largest_variance_first(settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        rows = close_module.load_period(session, PERIOD_START, PERIOD_END)
        ranked = close_module.rank_by_error_contribution(rows)
    assert [row["event_id"] for row in ranked][:2] == [
        scenario.asset_event_id,
        scenario.toss_ids[2],
    ]
    assert ranked[0]["variance_g2"] == pytest.approx(9.0)
    assert sum(row["variance_share"] for row in ranked) == pytest.approx(1.0, abs=1e-3)
