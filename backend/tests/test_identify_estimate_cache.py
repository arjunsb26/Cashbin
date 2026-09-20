"""The estimate cache: one object, one price, however many times it is tossed."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.db import session_scope
from app.identify.estimate_cache import cache_key, estimate_key, read_estimate, write_estimate
from app.identify.openai_provider import OpenAIEstimatorProvider
from app.models import Setting
from app.schemas import ValueEstimate, VisionResult
from tests.test_identify_openai import GOOD_ESTIMATE, GOOD_VISION, FakeClient, conf
from tests.test_identify_support import setup_db


def an_estimate() -> ValueEstimate:
    return ValueEstimate.model_validate_json(GOOD_ESTIMATE)


def test_the_key_is_the_normalised_label() -> None:
    assert cache_key("  Cracked  Phone ") == "estimate:cracked phone"


def test_a_hostile_label_cannot_become_a_key() -> None:
    with pytest.raises(ValueError, match="letters"):
        cache_key("<script>alert(1)</script>")


def test_nothing_is_cached_until_something_is_written(settings: Settings) -> None:
    setup_db(settings)
    assert read_estimate("cracked phone") is None


def test_an_estimate_survives_a_round_trip(settings: Settings) -> None:
    setup_db(settings)
    write_estimate("Cracked Phone", an_estimate())
    found = read_estimate("cracked phone")
    assert found is not None
    assert found.fmv.mid == 2000
    with session_scope() as session:
        assert session.get(Setting, "estimate:cracked phone") is not None


def test_a_second_write_replaces_the_first(settings: Settings) -> None:
    setup_db(settings)
    write_estimate("cracked phone", an_estimate())
    dearer = an_estimate().model_copy(update={"scrap": an_estimate().scrap})
    dearer = ValueEstimate.model_validate(
        {**dearer.model_dump(), "fmv": {"low": 1, "mid": 9999, "high": 10000}}
    )
    write_estimate("cracked phone", dearer)
    found = read_estimate("cracked phone")
    assert found is not None and found.fmv.mid == 9999
    with session_scope() as session:
        rows = session.query(Setting).filter(Setting.key.like("estimate:%")).all()
        assert len(rows) == 1


def test_a_row_that_will_not_read_back_is_ignored(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        session.add(Setting(key="estimate:cracked phone", value_json="not json"))
    assert read_estimate("cracked phone") is None


def test_no_database_at_all_is_a_miss_not_a_crash(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_db(settings)

    def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("the database is gone")

    monkeypatch.setattr("app.db.get_session_factory", broken)
    assert read_estimate("cracked phone") is None
    write_estimate("cracked phone", an_estimate())


def test_an_object_is_never_priced_twice(settings: Settings) -> None:
    setup_db(settings)
    vision = VisionResult.model_validate_json(GOOD_VISION)
    client = FakeClient([GOOD_ESTIMATE])
    provider = OpenAIEstimatorProvider(conf(), client)

    first = provider.estimate("cracked phone", vision, 180.0)
    second = provider.estimate("Cracked  Phone", vision, 180.0)
    assert len(client.calls) == 1
    assert first == second
    assert first.provider == "openai"

    # The key carries what was read off the thing, so two different phones are two
    # entries. PLAN.md 21a item 29.
    stored = read_estimate(estimate_key("cracked phone", vision))
    assert stored is not None and stored.fmv.mid == 2000

    # A fresh provider, with no memory of its own, still finds the stored estimate.
    fresh = OpenAIEstimatorProvider(conf(), FakeClient([]))
    assert fresh.estimate("cracked phone", vision, 180.0).fmv.mid == 2000


def test_an_estimate_that_will_not_validate_is_refused(settings: Settings) -> None:
    setup_db(settings)
    vision = VisionResult.model_validate_json(GOOD_VISION)
    provider = OpenAIEstimatorProvider(conf(), FakeClient(["{}", "{}"]))
    with pytest.raises(ValueError, match="could read"):
        provider.estimate("mystery thing", vision, 50.0)
