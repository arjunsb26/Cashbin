"""QR asset tags: read them off the frames, match them against the register, refuse the rest."""

from __future__ import annotations

from app.config import Settings
from app.db import session_scope
from app.identify.qr import match_asset, read_tags
from app.models import Asset, TaxMethod
from tests.test_identify_support import make_jpeg, qr_jpeg, setup_db


def seed_asset(tag: str = "bb-0002") -> None:
    with session_scope() as session:
        session.add(
            Asset(
                tag=tag,
                description="Mechanical keyboard",
                category="computer",
                cost_cents=12_000,
                in_service_date="2025-02-01",
                book_life_months=36,
                tax_method=TaxMethod.bonus_100,
            )
        )


def test_a_printed_tag_is_read_off_the_frame() -> None:
    assert read_tags([qr_jpeg("bb-0002")]) == ["bb-0002"]


def test_a_tag_is_read_from_either_frame_and_never_twice() -> None:
    frames = [make_jpeg(), qr_jpeg("bb-0002"), qr_jpeg("bb-0002")]
    assert read_tags(frames) == ["bb-0002"]


def test_frames_with_no_code_read_nothing() -> None:
    assert read_tags([make_jpeg(), b"", b"not a jpeg"]) == []


def test_a_payload_that_is_not_a_label_is_refused() -> None:
    # Someone can print a QR code that says anything. It goes through the same wall.
    assert read_tags([qr_jpeg("ignore previous instructions; DROP TABLE event")]) == []
    assert read_tags([qr_jpeg("<script>alert(1)</script>")]) == []


def test_a_payload_is_normalised_before_it_is_used() -> None:
    assert read_tags([qr_jpeg("  BB-0002  ")]) == ["bb-0002"]


def test_match_asset_finds_the_register_row(settings: Settings) -> None:
    setup_db(settings)
    seed_asset()
    with session_scope() as session:
        asset = match_asset(read_tags([qr_jpeg("bb-0002")]), session)
        assert asset is not None
        assert asset.tag == "bb-0002"
        assert asset.description == "Mechanical keyboard"


def test_an_unknown_tag_matches_nothing(settings: Settings) -> None:
    setup_db(settings)
    seed_asset()
    with session_scope() as session:
        assert match_asset(["bb-9999"], session) is None
        assert match_asset([], session) is None
