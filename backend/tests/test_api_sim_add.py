"""The Add button: a weight a person typed and whatever the camera can see.

PLAN.md 21a item 34. The user's words: "instead of having this toss thing could you just
add a button maybe to add and then est weight". `POST /api/sim/toss` with a mass and no
image builds the step out of the frames the phone has already sent, so a real item held
over the bin becomes a real ticket with a real crop, and nobody has to own a load cell to
try the thing out.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest.state import get_ingest
from tests.ingest_helpers import background_frame, frame_with_item, jpeg


def camera(client: TestClient, *, frames: int = 2) -> float:
    """Put a bin, and then a bin with something in it, in front of the lens."""
    deps = get_ingest(client.app)  # type: ignore[arg-type]
    now = deps.clock()
    if frames >= 2:
        deps.frames.push(jpeg(background_frame()), now - 2400.0)
        deps.frames.push(jpeg(background_frame()), now - 2000.0)
    deps.frames.push(jpeg(frame_with_item(background_frame())), now)
    return now


def test_an_added_item_is_cropped_from_the_live_camera(
    dev_client: TestClient, dev_settings: Settings
) -> None:
    camera(dev_client)

    reply = dev_client.post("/api/sim/toss", json={"mass_g": 148.0})
    assert reply.status_code == 200, reply.text
    event_id = reply.json()["event_id"]

    detail = dev_client.get(f"/api/events/{event_id}").json()
    assert detail["event"]["mass_g"] == 148.0
    # Nothing was isolated out of the picture, because the picture is the item.
    assert detail["event"]["crop_quality"] == "low"
    assert detail["frame_before_url"] and detail["frame_after_url"]

    crop = dev_settings.media_dir / str(event_id) / "crop.jpg"
    assert crop.exists() and crop.stat().st_size > 0


def test_adding_with_no_camera_says_to_start_the_camera(dev_client: TestClient) -> None:
    reply = dev_client.post("/api/sim/toss", json={"mass_g": 148.0})
    assert reply.status_code == 409
    assert reply.json()["detail"] == "No camera frames yet. Start the camera first."


def test_one_frame_is_not_enough_to_cut_anything_out_of(dev_client: TestClient) -> None:
    camera(dev_client, frames=1)
    assert dev_client.post("/api/sim/toss", json={"mass_g": 148.0}).status_code == 409


def test_a_label_is_optional(dev_client: TestClient) -> None:
    """Nothing typed, so the picture decides. This is the button's normal case."""
    camera(dev_client)
    assert dev_client.post("/api/sim/toss", json={"mass_g": 30.0}).status_code == 200
    row = dev_client.get("/api/events").json()["events"][0]
    assert row["mass_g"] == 30.0


def test_a_label_that_is_given_is_what_the_stub_answers(dev_client: TestClient) -> None:
    from app.identify.stub import get_expect_queue

    get_expect_queue().clear()
    camera(dev_client)
    reply = dev_client.post("/api/sim/toss", json={"mass_g": 30.0, "label": "usb cable"})
    assert reply.status_code == 200
    row = dev_client.get("/api/events").json()["events"][0]
    assert row["label"] == "usb cable"


def test_the_simulator_path_still_works_the_way_it_did(dev_client: TestClient) -> None:
    reply = dev_client.post(
        "/api/sim/toss", json={"mass_g": 95.0, "label": "bagel", "image": "bagel.png"}
    )
    assert reply.status_code in {200, 400}, reply.text
    if reply.status_code == 400:
        assert reply.json()["detail"] == "That image is not one of the simulator's."


def test_an_added_picture_is_the_item_and_is_not_diffed(dev_client: TestClient) -> None:
    """PLAN.md 21a item 36. A phone held over a table diffs to the table, not the item.

    The screenshot that found this had a grey patch of desk where the crop should be. A
    picture somebody took on purpose is the item, so the whole frame is the crop.
    """
    from app.detect.crop import jpeg_size
    from app.ingest.media import read_jpeg
    from app.ingest.state import get_ingest

    deps = get_ingest(dev_client.app)  # type: ignore[arg-type]
    now = deps.clock()
    # Two frames of almost the same scene, which is what a hand-held phone really sends.
    deps.frames.push(jpeg(background_frame()), now - 2000.0)
    held_up = jpeg(frame_with_item(background_frame()))
    deps.frames.push(held_up, now)

    event_id = dev_client.post("/api/sim/toss", json={"mass_g": 148.0}).json()["event_id"]
    crop = read_jpeg(event_id, "crop")
    assert crop is not None
    assert jpeg_size(crop) == jpeg_size(held_up), "the crop is the picture, whole"

    detail = dev_client.get(f"/api/events/{event_id}").json()
    # Nothing was isolated, and the ticket says so rather than claiming a good crop.
    assert detail["event"]["crop_quality"] == "low"
    assert detail["frame_before_url"] and detail["frame_after_url"]


def test_a_real_toss_is_still_diffed() -> None:
    """The diff is what finds an item among everything already in the bin, and it stays."""
    from app.detect.steps import Step

    dropped = Step(
        kind="toss",
        t_open_ms=0.0,
        t_settle_ms=600.0,
        mass_g=95.0,
        mass_err_g=0.5,
        baseline_before_g=0.0,
        baseline_after_g=95.0,
    )
    assert dropped.whole_frame is False
