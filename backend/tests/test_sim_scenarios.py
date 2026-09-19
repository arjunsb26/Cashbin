"""The scenario files have to mean what the simulator thinks they mean."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

SIM_DIR = Path(__file__).resolve().parents[2] / "sim"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

# The simulators live outside the backend package and are put on the path above,
# which mypy cannot follow from a static read of the file.
from make_assets import ITEMS, KEYBOARD_TAG  # type: ignore[import-not-found]  # noqa: E402
from phone_sim import ASSETS, composite_items  # type: ignore[import-not-found]  # noqa: E402
from run_scenario import (  # type: ignore[import-not-found]  # noqa: E402
    Scenario,
    load_scenario,
    phone_url_for,
    scenario_path,
)

SCENARIOS = ("demo", "soak")


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_file_validates(name: str) -> None:
    scenario = load_scenario(name)
    assert scenario.name
    assert scenario.steps


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_image_exists(name: str) -> None:
    for step in load_scenario(name).steps:
        if step.image:
            assert (ASSETS / step.image).exists(), f"{name}: missing {step.image}"


def test_demo_is_the_five_steps_the_pitch_describes() -> None:
    demo = load_scenario("demo")
    assert [(s.kind, s.label, s.mass_g) for s in demo.steps] == [
        ("toss", "bagel", 95.0),
        ("toss", "keyboard", 780.0),
        ("toss", "charger", 62.0),
        ("toss", "phone", 172.0),
        ("bag_change", "bag out", None),
    ]
    keyboard = demo.steps[1]
    assert keyboard.tag == KEYBOARD_TAG


def test_soak_is_sixty_tosses_with_a_tenth_unknown() -> None:
    soak = load_scenario("soak")
    tosses = [s for s in soak.steps if s.kind == "toss"]
    known = {item.label for item in ITEMS}
    unknown = [s for s in tosses if s.label not in known]

    assert len(tosses) == 60
    assert len(unknown) == 6
    assert all(s.mass_g and 0 < s.mass_g < 1500 for s in tosses)
    assert any(s.kind == "bag_change" for s in soak.steps)


def test_a_toss_without_a_mass_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs a positive mass_g"):
        Scenario.model_validate(
            {"name": "bad", "steps": [{"kind": "toss", "label": "bagel", "image": "bagel.png"}]}
        )


def test_a_toss_without_an_image_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs an image"):
        Scenario.model_validate(
            {"name": "bad", "steps": [{"kind": "toss", "label": "bagel", "mass_g": 95}]}
        )


def test_an_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        Scenario.model_validate({"name": "bad", "steps": [{"kind": "burn", "label": "x"}]})


def test_a_scenario_with_no_steps_is_rejected() -> None:
    with pytest.raises(ValueError, match="steps"):
        Scenario.model_validate({"name": "empty", "steps": []})


def test_an_overlong_label_is_rejected() -> None:
    with pytest.raises(ValueError, match="label"):
        Scenario.model_validate(
            {"name": "bad", "steps": [{"kind": "bag_change", "label": "x" * 41}]}
        )


def test_scenario_files_on_disk_parse_as_yaml_mappings() -> None:
    for name in SCENARIOS:
        raw = yaml.safe_load(scenario_path(name).read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert set(raw) <= {"name", "sigma", "steps"}


def test_phone_url_is_derived_from_the_bin_url() -> None:
    assert phone_url_for("wss://localhost:8443/ws/bin") == "wss://localhost:8443/ws/phone"
    assert phone_url_for("ws://10.0.0.4:8000/ws/bin") == "ws://10.0.0.4:8000/ws/phone"


def test_the_keyboard_tag_decodes_from_a_composited_camera_frame() -> None:
    """Lane C reads this QR off a phone frame, so it has to survive the JPEG."""
    background = cv2.imread(str(ASSETS / "bin.png"), cv2.IMREAD_COLOR)
    frame = composite_items(background, [ASSETS / "keyboard.png"])
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    assert ok
    decoded = cv2.imdecode(np.frombuffer(buf.tobytes(), np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(decoded)
    assert text == KEYBOARD_TAG


def test_every_item_image_was_generated() -> None:
    for item in ITEMS:
        path = ASSETS / f"{item.slug}.png"
        assert path.exists(), f"missing {path.name}"
        assert path.stat().st_size < 50 * 1024, f"{path.name} is too big to commit"
    assert (ASSETS / "bin.png").stat().st_size < 50 * 1024
