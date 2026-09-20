"""The estimate cache: one object, one price, however many times it is tossed.

PLAN.md 21a item 47. Three claims are checked here. The key is everything the estimator was
told, not the label alone. The whole cache is one settings row rather than a row per label.
And a restart keeps every figure a person has already been shown.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import Settings
from app.db import session_scope
from app.identify.estimate_cache import (
    CACHE_SETTING_KEY,
    MAX_ENTRIES,
    EstimateCache,
    estimate_key,
    get_cache,
    label_of,
    read_estimate,
    reset_cache,
    write_estimate,
)
from app.identify.openai_provider import OpenAIEstimatorProvider
from app.models import Setting
from app.schemas import ValueEstimate, VisionResult
from tests.test_identify_openai import GOOD_ESTIMATE, GOOD_VISION, FakeClient, conf
from tests.test_identify_support import setup_db


def an_estimate() -> ValueEstimate:
    return ValueEstimate.model_validate_json(GOOD_ESTIMATE)


def test_the_key_is_the_normalised_label_when_there_is_nothing_else() -> None:
    assert estimate_key("  Cracked  Phone ") == "cracked phone"


def test_a_hostile_label_cannot_become_a_key() -> None:
    with pytest.raises(ValueError, match="letters"):
        estimate_key("<script>alert(1)</script>")


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
        assert session.get(Setting, CACHE_SETTING_KEY) is not None


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
        row = session.get(Setting, CACHE_SETTING_KEY)
        assert row is not None
        assert len(json.loads(row.value_json)["entries"]) == 1


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


# The same item gives the same figure ------------------------------------------


def test_the_key_carries_everything_that_would_change_the_answer() -> None:
    """PLAN.md 21a item 47. A judge who saw a number once should see it again."""
    def seen(**kwargs: object) -> VisionResult:
        base = {"label": "mouse", "class": "untracked", "confidence": 0.9}
        return VisionResult.model_validate({**base, **kwargs})

    plain = seen()
    assert estimate_key("mouse", plain) == "mouse"

    # Each of the three parts moves the key, and moving none of them does not.
    branded = seen(visible_text="MX MASTER 3")
    broken = seen(condition="broken")
    keys = {
        estimate_key("mouse", plain),
        estimate_key("mouse", branded),
        estimate_key("mouse", broken),
        estimate_key("mouse", plain, detail="64 gb"),
    }
    assert len(keys) == 4

    # And the same item, twice, is the same key.
    assert estimate_key("mouse", branded) == estimate_key("mouse", seen(visible_text="MX MASTER 3"))
    assert estimate_key("mouse", branded) == estimate_key("mouse", seen(visible_text="mx master 3"))


def test_the_same_item_priced_twice_is_one_cache_entry(settings: Settings) -> None:
    setup_db(settings)
    vision = VisionResult.model_validate_json(GOOD_VISION)
    client = FakeClient([GOOD_ESTIMATE])
    provider = OpenAIEstimatorProvider(conf(), client)

    first = provider.estimate("cracked phone", vision, 180.0)
    fresh = OpenAIEstimatorProvider(conf(), FakeClient([]))
    second = fresh.estimate("cracked phone", vision, 180.0)

    assert len(client.calls) == 1, "the second one never reached a model"
    assert first == second


# One row, and what happens to it ---------------------------------------------


def test_the_whole_cache_is_one_settings_row(settings: Settings) -> None:
    setup_db(settings)
    reset_cache()
    vision = VisionResult.model_validate_json(GOOD_VISION)
    write_estimate(estimate_key("cracked phone"), an_estimate())
    write_estimate(estimate_key("mouse", vision), an_estimate())
    with session_scope() as session:
        rows = session.query(Setting).all()
        assert [row.key for row in rows] == [CACHE_SETTING_KEY]
        document = json.loads(rows[0].value_json)
    assert len(document["entries"]) == 2
    assert document["latest"]["mouse"] != "mouse"


def test_a_label_on_its_own_finds_the_newest_estimate_for_that_label(
    settings: Settings,
) -> None:
    """The ticket has a label and nothing else. It still gets the figure the bin drew."""
    setup_db(settings)
    reset_cache()
    vision = VisionResult.model_validate_json(GOOD_VISION)
    write_estimate(estimate_key("mouse", vision), an_estimate())
    found = read_estimate("mouse")
    assert found is not None and found.fmv.mid == 2000


def test_the_label_comes_back_out_of_a_key() -> None:
    vision = VisionResult.model_validate_json(GOOD_VISION)
    assert label_of(estimate_key("cracked phone", vision)) == "cracked phone"
    assert label_of("cracked phone") == "cracked phone"
    assert label_of("cracked phone 3") == "cracked phone 3"


def test_one_unreadable_entry_does_not_cost_the_others(settings: Settings) -> None:
    setup_db(settings)
    reset_cache()
    document = {
        "v": 1,
        "entries": {"cracked phone": an_estimate().model_dump(mode="json"), "mouse": {}},
        "latest": {"cracked phone": "cracked phone", "mouse": "mouse"},
    }
    with session_scope() as session:
        session.add(Setting(key=CACHE_SETTING_KEY, value_json=json.dumps(document)))
    assert read_estimate("cracked phone") is not None
    assert read_estimate("mouse") is None


def test_the_cache_stops_growing(settings: Settings) -> None:
    setup_db(settings)
    cache = reset_cache()
    for index in range(MAX_ENTRIES + 5):
        cache.put(f"thing {index}", an_estimate())
    assert len(cache.as_document()["entries"]) == MAX_ENTRIES
    assert cache.get("thing 0") is None
    assert cache.get(f"thing {MAX_ENTRIES + 4}") is not None


# A restart -------------------------------------------------------------------


def test_a_restart_keeps_every_figure_a_person_has_seen(settings: Settings) -> None:
    setup_db(settings)
    reset_cache()
    vision = VisionResult.model_validate_json(GOOD_VISION)
    key = estimate_key("mouse", vision, "still works")
    write_estimate(key, an_estimate())

    # What a restart is: a new cache object, nothing in memory, the same database.
    fresh = EstimateCache(str(settings.db_path))
    fresh.load()
    found = fresh.get(key)
    assert found is not None and found.fmv.mid == 2000
    assert fresh.get("mouse") is not None


def test_another_database_is_not_this_cache(settings: Settings) -> None:
    setup_db(settings)
    reset_cache()
    write_estimate("cracked phone", an_estimate())
    assert get_cache().get("cracked phone") is not None
    settings.db_path = settings.db_path.parent / "somewhere-else.db"
    assert get_cache().source == str(settings.db_path)
