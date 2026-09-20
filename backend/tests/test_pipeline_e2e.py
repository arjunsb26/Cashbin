"""The whole demo, end to end, through the app's own sockets.

PLAN.md section 19, last line, and the M1 acceptance check. A staircase goes in on
`/ws/bin`, camera frames land in the ring on the same clock, and what comes out is five
event rows, four posted tickets, balanced journal entries, and a result on every surface.

Nothing here talks to a model. The stub provider answers, told what is coming by
`/api/sim/expect` the way the scenario runner tells it, and the tagged keyboard is read
off a real QR code in a real composited frame.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.testclient import WebSocketTestSession

from app.config import Settings
from app.db import session_scope
from app.main import create_app
from app.models import (
    Asset,
    AssetStatus,
    Event,
    EventKind,
    EventStatus,
    ItemRecord,
    JournalBasis,
    OptionKind,
    OptionScore,
    TaxMethod,
)
from app.pipeline import (
    VALUING_BIG,
    VALUING_LINE,
    advice_line,
    headline_cents,
    lcd_big,
    signed_money,
    title_for,
)
from tests.ingest_helpers import ScriptedClock, weight_frames
from tests.test_detect_steps import Signal

REPO_DIR = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_DIR / "sim"
ASSETS = SIM_DIR / "assets"
for path in (str(REPO_DIR), str(SIM_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts.seed_db import seed_all  # noqa: E402
from sim.phone_sim import composite_items  # noqa: E402

HELLO = {"type": "hello", "fw": "0.1", "device": "bin-1"}
READ_CAP = 6000

KEYBOARD_TAG = "bb-0002"
# Register numbers for the tagged keyboard. This case sets its own so the assertions
# below do not move when the seed file's approximate values change.
KEYBOARD_COST_CENTS = 12_900
KEYBOARD_LIFE_MONTHS = 36

# The demo scenario, in the order the pitch tells it. The label is what the simulator
# says is coming; a tagged item has no label to announce, because its tag decides.
TOSSES: tuple[tuple[float, str, str | None], ...] = (
    (95.0, "bagel.png", "bagel"),
    (780.0, "keyboard.png", None),
    (62.0, "charger.png", "usb-c charger"),
    (172.0, "phone_cracked.png", "phone"),
)
BAG_CHANGE_G = -1109.0

# The item is in frame before it lands and stays there until the bin is cleared, which is
# what `sim/phone_sim.py` does on the wire.
LAND_LEAD_MS = 300.0
CLEAR_TRAIL_MS = 500.0


# Frames -----------------------------------------------------------------------


def _jpeg(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:  # pragma: no cover - opencv only fails on a broken build
        raise RuntimeError("could not encode a frame")
    return bytes(buffer.tobytes())


def _background() -> np.ndarray:
    image = cv2.imread(str(ASSETS / "bin.png"))
    if image is None:  # pragma: no cover - the asset ships with the repo
        raise RuntimeError("the bin background is missing from sim/assets")
    return image


def frame_for(items: list[str]) -> bytes:
    """One camera frame with these sprites in the bin, composited the way the sim does."""
    return _jpeg(composite_items(_background(), [ASSETS / name for name in items]))


class FramingClock:
    """One clock for the scale and the camera, so the ring lines up with the staircase.

    The bin session calls this once per weight message. Every call also drops the frame the
    camera would be showing at that moment into the ring, which is how a test gets the
    before, peak and after frames a real phone would have supplied.
    """

    def __init__(
        self,
        times: list[float],
        ring: Any,
        schedule: list[tuple[float, bytes]],
    ) -> None:
        self._inner = ScriptedClock(times)
        self._ring = ring
        self._schedule = sorted(schedule, key=lambda pair: pair[0])

    def __call__(self) -> float:
        t = self._inner()
        current = self._schedule[0][1]
        for start, jpeg in self._schedule:
            if start <= t:
                current = jpeg
            else:
                break
        self._ring.push(current, t)
        return t


def demo_run() -> tuple[Signal, list[tuple[float, bytes]]]:
    """The demo staircase and what the camera shows while it happens."""
    empty = frame_for([])
    signal = Signal(seed=11)
    signal.hold(3.0)
    schedule: list[tuple[float, bytes]] = [(0.0, empty)]
    for mass, image, _label in TOSSES:
        schedule.append((signal.t_ms - LAND_LEAD_MS, frame_for([image])))
        signal.add(mass)
        signal.hold(2.5)
        schedule.append((signal.t_ms - CLEAR_TRAIL_MS, empty))
    signal.add(BAG_CHANGE_G)
    signal.hold(2.5)
    return signal, schedule


# Sockets ----------------------------------------------------------------------


def collect(socket: WebSocketTestSession, topic: str, count: int) -> list[dict[str, Any]]:
    """Read from a socket until `count` messages of one type have arrived."""
    found: list[dict[str, Any]] = []
    for _ in range(READ_CAP):
        message = socket.receive_json()
        if message.get("type") == topic:
            found.append(message)
            if len(found) == count:
                return found
    raise AssertionError(f"only {len(found)} {topic} messages arrived, wanted {count}")


def collect_topics(
    socket: WebSocketTestSession, wanted: dict[str, int]
) -> dict[str, list[dict[str, Any]]]:
    """Read one socket once, into a bucket per topic.

    Topics interleave, so a reader that waits for all of one topic before starting on the
    next throws the next one away. This keeps everything it sees.
    """
    found: dict[str, list[dict[str, Any]]] = {topic: [] for topic in wanted}
    for _ in range(READ_CAP):
        message = socket.receive_json()
        topic = str(message.get("type"))
        if topic in found:
            found[topic].append(message)
        if all(len(found[name]) >= need for name, need in wanted.items()):
            return found
    missing = {name: len(found[name]) for name in wanted}
    raise AssertionError(f"the dashboard socket stopped short: {missing} against {wanted}")


def collect_screens(socket: WebSocketTestSession, count: int) -> list[dict[str, Any]]:
    """Every result or ask screen the bin was sent. Thinking screens are not answers."""
    found: list[dict[str, Any]] = []
    for _ in range(READ_CAP):
        message = socket.receive_json()
        if message.get("type") == "screen" and message.get("s") in {"result", "ask"}:
            found.append(message)
            if len(found) == count:
                return found
    raise AssertionError(f"only {len(found)} answer screens arrived, wanted {count}")


# The charger and the phone are untracked and the catalog does not price them, so each one
# is answered twice: the label now, the value when the second model call lands.
VALUED_TOSSES = 2


# Fixtures ---------------------------------------------------------------------


@pytest.fixture
def demo_settings(tmp_path: Path) -> Any:
    from app.config import reset_settings
    from app.db import dispose_db
    from app.notify.bus import reset_bus

    conf = Settings(
        _env_file=None,
        db_path=tmp_path / "binbooks.db",
        media_dir=tmp_path / "media",
        cert_dir=tmp_path / "certs",
        recordings_dir=tmp_path / "recordings",
        dev_tools=True,
        seed_on_start=False,
    )
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


def seed_for_demo() -> None:
    """The catalog and register from the seed files, with the keyboard row set to this
    case's own numbers so the assertions below do not depend on the CSV's values."""
    with session_scope() as session:
        seed_all(session)
        today = date.today()
        in_service = today.replace(year=today.year - 1)
        row = session.scalar(select(Asset).where(Asset.tag == KEYBOARD_TAG))
        if row is None:
            row = Asset(tag=KEYBOARD_TAG, description="Mechanical keyboard")
            session.add(row)
        row.category = "peripheral"
        row.cost_cents = KEYBOARD_COST_CENTS
        row.in_service_date = in_service.isoformat()
        row.book_life_months = KEYBOARD_LIFE_MONTHS
        row.salvage_cents = 0
        # Bought after 19 January 2025 and fully expensed, so the tax basis is zero and
        # the book and tax columns differ. PLAN.md section 10.
        row.tax_method = TaxMethod.bonus_100
        row.status = AssetStatus.active
        row.disposed_event_id = None


def run_demo(client: TestClient, app: FastAPI) -> dict[str, list[dict[str, Any]]]:
    """Play the demo through the three sockets and hand back what each one received."""
    signal, schedule = demo_run()
    app.state.ingest.clock = FramingClock(
        [s.t_ms for s in signal.samples], app.state.ingest.frames, schedule
    )
    for _mass, _image, label in TOSSES:
        if label is not None:
            client.post("/api/sim/expect", json={"label": label})

    with (
        client.websocket_connect("/ws/ui") as ui,
        client.websocket_connect("/ws/phone") as phone,
        client.websocket_connect("/ws/bin") as bin_sock,
    ):
        bin_sock.send_json(HELLO)
        assert bin_sock.receive_json() == {"type": "ping"}
        for frame in weight_frames(signal.samples):
            bin_sock.send_json(frame)
        seen = collect_topics(
            ui,
            {
                "event.created": 5,
                "event.updated": 4 + VALUED_TOSSES,
                "journal.posted": 1,
            },
        )
        screens = collect_screens(bin_sock, 4 + VALUED_TOSSES)
        results = collect(phone, "result", 4 + VALUED_TOSSES)
    return {
        "created": seen["event.created"],
        "updated": seen["event.updated"],
        "journal": seen["journal.posted"],
        "screens": screens,
        "results": results,
    }


# The run ----------------------------------------------------------------------


def test_the_demo_scenario_ends_as_posted_balanced_tickets(demo_settings: Settings) -> None:
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_for_demo()
        seen = run_demo(client, app)

        # Five events: four tosses and the bag going out.
        rows = client.get("/api/events").json()["events"]
        assert len(rows) == 5
        tosses = [row for row in rows if row["kind"] == EventKind.toss]
        changes = [row for row in rows if row["kind"] == EventKind.bag_change]
        assert len(tosses) == 4
        assert {row["status"] for row in tosses} == {EventStatus.posted}
        assert {row["status"] for row in changes} == {EventStatus.detected}

        by_label = {row["label"]: row for row in tosses}
        assert set(by_label) == {"bagel", "mechanical keyboard", "usb-c charger", "phone"}

        # The tagged keyboard came off the register, with a tax basis of zero.
        keyboard = by_label["mechanical keyboard"]
        assert keyboard["class"] == "fixed_asset"
        assert keyboard["net_book_cents"] > 0
        detail = client.get(f"/api/events/{keyboard['id']}").json()
        assert detail["item_record"]["tax_basis_cents"] == 0
        assert detail["item_record"]["book_value_cents"] > 0
        bases = [entry["basis"] for entry in detail["entries"]]
        assert JournalBasis.book in bases
        assert JournalBasis.tax_memo in bases
        with session_scope() as session:
            asset = session.query(Asset).filter(Asset.tag == KEYBOARD_TAG).one()
            assert asset.status is AssetStatus.disposed
            assert asset.disposed_event_id == keyboard["id"]

        # The bagel is worth more donated than binned, and a person has to sign it off.
        bagel = client.get(f"/api/events/{by_label['bagel']['id']}").json()
        ranks = {row["option"]: row["rank"] for row in bagel["options"]}
        assert ranks[OptionKind.donate] is not None
        assert ranks[OptionKind.trash] is not None
        assert ranks[OptionKind.donate] < ranks[OptionKind.trash]
        donate = next(row for row in bagel["options"] if row["option"] == OptionKind.donate)
        assert donate["needs_human_review"] is True
        assert "DONATE_FOOD" in donate["rule_ids"]
        assert by_label["bagel"]["saved_if_followed_cents"] > 0

        # Electronics do not go in the landfill, and the reason is on the row.
        for label in ("usb-c charger", "phone"):
            options = client.get(f"/api/events/{by_label[label]['id']}").json()["options"]
            trash = next(row for row in options if row["option"] == OptionKind.trash)
            assert trash["allowed"] is False
            assert trash["blocked_reason"]
            assert "EWASTE" in trash["rule_ids"]

        # Every entry balances, and so does the book trial balance.
        journal = client.get("/api/journal", params={"basis": "book"}).json()
        assert journal["entries"]
        for entry in journal["entries"]:
            debits = sum(line["debit_cents"] for line in entry["lines"])
            credited = sum(line["credit_cents"] for line in entry["lines"])
            assert debits == credited, entry["memo"]
        assert sum(row["debit_cents"] for row in journal["trial_balance"]) == sum(
            row["credit_cents"] for row in journal["trial_balance"]
        )

        # Every surface heard about it, and the two unpriced tickets were answered twice:
        # once with the label, and again when the value landed. PLAN.md 21a item 25.
        assert len(seen["screens"]) == 4 + VALUED_TOSSES
        assert {screen["s"] for screen in seen["screens"]} == {"result"}
        assert len(seen["results"]) == 4 + VALUED_TOSSES
        assert {result["type"] for result in seen["results"]} == {"result"}
        assert len(seen["updated"]) == 4 + VALUED_TOSSES
        assert {message["event"]["id"] for message in seen["updated"]} == {
            row["id"] for row in tosses
        }
        assert seen["journal"]

        # The first answer for an unpriced thing carries no figure, and says so.
        valuing = [screen for screen in seen["screens"] if screen["big"] == VALUING_BIG]
        assert len(valuing) == VALUED_TOSSES
        assert {screen["l2"] for screen in valuing} == {VALUING_LINE}
        waiting = [result for result in seen["results"] if result["big"] == VALUING_BIG]
        assert {result["event_id"] for result in waiting} == {
            result["event_id"]
            for result in seen["results"]
            if result["big"] != VALUING_BIG
        } & {result["event_id"] for result in waiting}

        # The header adds up.
        summary = client.get("/api/summary").json()
        assert summary["events"] == 4
        assert summary["saved_if_followed_cents"] > 0
        assert summary["kg_diverted"] >= 0.0

        # And the round the events landed in is real.
        rounds = client.get("/api/metrics/rounds").json()["rounds"]
        assert rounds
        assert rounds[-1]["n_events"] == 4


def test_the_setup_checklist_names_every_unfilled_cell(client: TestClient) -> None:
    body = client.get("/api/setup").json()
    assert body["items"]
    assert all(": " in line for line in body["items"])
    # The register is filled, so only the catalog's one unpriced row is waiting.
    assert not any(line.startswith("assets_seed.csv") for line in body["items"])
    assert any(line.startswith("catalog.csv") for line in body["items"])


def test_a_first_start_seeds_the_catalog(tmp_path: Path) -> None:
    """The lifespan loads the seed files once, when both seeded tables are empty."""
    from app.config import reset_settings
    from app.db import dispose_db
    from app.notify.bus import reset_bus

    conf = Settings(
        _env_file=None,
        db_path=tmp_path / "binbooks.db",
        media_dir=tmp_path / "media",
        cert_dir=tmp_path / "certs",
        recordings_dir=tmp_path / "recordings",
        seed_on_start=True,
    )
    reset_settings(conf)
    reset_bus()
    try:
        with TestClient(create_app(conf)) as client:
            items = client.get("/api/catalog").json()["items"]
            assert len(items) > 20
            assert any(item["label"] == "bagel" for item in items)
    finally:
        dispose_db()
        reset_settings(Settings(_env_file=None))


# The copy every surface shares ------------------------------------------------


def _record(**kwargs: Any) -> Any:
    from app.engine.records import ItemClass as EngineClass
    from app.engine.records import ItemRecord as EngineRecord

    base = {
        "event_id": 1,
        "label": "bagel",
        "class": EngineClass.inventory,
        "mass_g": 95.0,
        "event_date": date(2026, 9, 19),
    }
    base.update(kwargs)
    return EngineRecord.model_validate(base)


def test_the_headline_figure_reads_the_same_on_every_surface() -> None:
    from app.engine.records import ItemClass as EngineClass

    assert headline_cents(_record(cost_basis_cents=33)) == -33
    assert headline_cents(_record(**{"class": EngineClass.fixed_asset}, book_value_cents=2000)) == (
        -2000
    )
    assert headline_cents(_record(**{"class": EngineClass.untracked}, fmv_mid=800)) == 800
    assert signed_money(-2000) == "-$20.00"
    assert signed_money(800) == "$8.00"


def test_the_big_figure_is_cut_until_the_bin_can_draw_it() -> None:
    assert lcd_big(-2000) == "-$20.00"
    assert lcd_big(-123_400) == "-$1,234"
    assert lcd_big(-1_234_500) == "-$12345"
    assert lcd_big(-98_765_400) == "-$988k"
    assert len(lcd_big(-98_765_400)) <= 7


def test_the_advice_line_says_what_to_do_or_what_happened() -> None:
    from app.engine.options import Ranking
    from app.engine.records import ItemClass as EngineClass
    from app.engine.records import Option

    donate = Ranking(
        best_option=Option.donate,
        greenest_option=Option.donate,
        saved_if_followed_cents=3,
        tone="amber",
    )
    assert advice_line(_record(), donate, blocked=False) == "Donate it instead"
    recycle = donate.model_copy(update={"best_option": Option.recycle})
    assert advice_line(_record(), recycle, blocked=True) == "No bin. Recycle it"
    binned = donate.model_copy(update={"best_option": Option.trash})
    assert advice_line(_record(**{"class": EngineClass.fixed_asset}), binned, blocked=False) == (
        "Removed from books"
    )
    assert len(advice_line(_record(), recycle, blocked=True)) <= 20
    assert title_for("mechanical keyboard") == "Mechanical keyboard"


def test_every_stored_ticket_keeps_its_own_option_rows(demo_settings: Settings) -> None:
    """One row per event and option, rewritten rather than duplicated on a re-post."""
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_for_demo()
        client.post("/api/sim/expect", json={"label": "bagel"})
        event_id = client.post(
            "/api/sim/toss", json={"label": "bagel", "mass_g": 95.0, "image": "bagel.png"}
        ).json()["event_id"]
        client.post(
            "/api/corrections",
            json={"event_id": event_id, "label": "cookie", "by": "tester"},
        )
        with session_scope() as session:
            rows = session.query(OptionScore).filter(OptionScore.event_id == event_id).all()
            assert len(rows) == len({row.option for row in rows})
            record = session.get(ItemRecord, event_id)
            assert record is not None
            assert record.label == "cookie"
            event = session.get(Event, event_id)
            assert event is not None
            assert event.status is EventStatus.posted
        entries = client.get(f"/api/events/{event_id}").json()["entries"]
        # The first posting, its reversal, and the corrected posting. Nothing is deleted.
        assert len(entries) == 3
        for entry in entries:
            debits = sum(line["debit_cents"] for line in entry["lines"])
            credited = sum(line["credit_cents"] for line in entry["lines"])
            assert debits == credited
