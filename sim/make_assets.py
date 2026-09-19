"""Generate the simulator's item images and bin background.

Run it once and commit what it writes. Each item is a flat coloured shape with its
label on it, distinct enough that the frame diff finds it and a person watching the
demo can tell them apart. The keyboard carries a real QR code of asset tag BB-0002,
so the identification lane has something to decode.

Real photographs can replace any of these later. Same file names, same sizes.

    python sim/make_assets.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent / "assets"
BACKGROUND_SIZE = (640, 480)
KEYBOARD_TAG = "BB-0002"
FONT = cv2.FONT_HERSHEY_SIMPLEX


class Item(NamedTuple):
    slug: str
    label: str
    width: int
    height: int
    colour: tuple[int, int, int]
    shape: str
    text_colour: tuple[int, int, int] = (255, 255, 255)


ITEMS = [
    Item("bagel", "bagel", 170, 170, (96, 150, 205), "ring"),
    Item("pizza_slice", "pizza slice", 200, 170, (58, 132, 214), "wedge"),
    Item("cookie", "cookie", 130, 130, (92, 140, 186), "disc"),
    Item("banana", "banana", 220, 110, (86, 214, 232), "arc"),
    Item("chips", "chips", 190, 230, (74, 96, 206), "bag"),
    Item("soda_can", "soda can", 110, 200, (168, 74, 74), "can"),
    Item("water_bottle", "water bottle", 100, 250, (196, 176, 96), "bottle"),
    Item("pasta", "pasta", 200, 150, (120, 196, 226), "blob"),
    Item("wrap", "wrap", 230, 120, (128, 178, 212), "roll"),
    Item("cardboard", "cardboard", 240, 180, (104, 142, 176), "box"),
    Item("paper_cup", "paper cup", 130, 170, (214, 214, 214), "cup", (60, 60, 60)),
    Item("plastic_cup", "plastic cup", 130, 170, (198, 206, 198), "cup", (60, 60, 60)),
    Item("usb_cable", "usb cable", 220, 160, (70, 70, 70), "cable"),
    Item("charger", "charger", 150, 120, (236, 236, 236), "brick", (40, 40, 40)),
    Item("mouse", "mouse", 130, 190, (72, 72, 80), "mouse"),
    Item("keyboard", "keyboard", 380, 150, (62, 62, 68), "keyboard"),
    Item("earbuds", "earbuds", 140, 140, (232, 232, 236), "buds", (50, 50, 50)),
    Item("phone", "phone", 110, 210, (46, 46, 52), "phone"),
    Item("phone_cracked", "phone", 110, 210, (46, 46, 52), "phone_cracked"),
    Item("unknown", "unknown", 160, 160, (150, 120, 190), "disc"),
]


def build_background() -> np.ndarray:
    """A bin liner seen from above: dark, slightly uneven, with a lit rim."""
    width, height = BACKGROUND_SIZE
    rng = np.random.default_rng(4)
    # Coarse mottling rather than per-pixel grain: it reads as a worn liner, it does
    # not fight the frame diff, and the PNG stays small.
    coarse = rng.integers(-8, 9, size=(height // 8, width // 8, 3), dtype=np.int16)
    grain = cv2.resize(coarse.astype(np.float32), (width, height)).astype(np.int16)
    img = np.clip(np.full((height, width, 3), 54, dtype=np.int16) + grain, 0, 255).astype(np.uint8)

    centre = (width // 2, height // 2)
    cv2.ellipse(img, centre, (width // 2 - 8, height // 2 - 8), 0, 0, 360, (86, 90, 92), 14)
    cv2.ellipse(img, centre, (width // 2 - 40, height // 2 - 34), 0, 0, 360, (40, 42, 44), -1)
    for i in range(6):
        y = 90 + i * 55
        cv2.line(img, (70, y), (width - 70, y + 6), (48, 50, 52), 2)
    soft = cv2.GaussianBlur(img, (5, 5), 0)
    # Quantise to 4 grey steps. The eye cannot see it, the threshold in crop.py is
    # well above it, and it keeps the committed PNG under 50 KB.
    quantised: np.ndarray = ((soft // 4) * 4).astype(np.uint8)
    return quantised


def build_item(item: Item) -> np.ndarray:
    """One RGBA sprite: the shape in colour, transparent everywhere else."""
    canvas = np.zeros((item.height, item.width, 4), dtype=np.uint8)
    mask = np.zeros((item.height, item.width), dtype=np.uint8)
    _draw_shape(mask, item)

    body = np.zeros((item.height, item.width, 3), dtype=np.uint8)
    body[:] = item.colour
    shade = np.linspace(0.82, 1.06, item.height, dtype=np.float32)[:, None, None]
    body = np.clip(body.astype(np.float32) * shade, 0, 255).astype(np.uint8)

    canvas[:, :, :3] = body
    canvas[:, :, 3] = mask
    _draw_detail(canvas, item)
    _draw_label(canvas, item)
    return canvas


def _draw_shape(mask: np.ndarray, item: Item) -> None:
    h, w = mask.shape
    cx, cy = w // 2, h // 2
    if item.shape in {"disc", "ring", "blob", "buds"}:
        cv2.ellipse(mask, (cx, cy), (w // 2 - 4, h // 2 - 4), 0, 0, 360, 255, -1)
        if item.shape == "ring":
            cv2.ellipse(mask, (cx, cy), (w // 8, h // 8), 0, 0, 360, 0, -1)
    elif item.shape == "wedge":
        pts = np.array([[6, h - 6], [w - 6, h - 6], [cx, 6]], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif item.shape == "arc":
        cv2.ellipse(mask, (cx, h - 10), (w // 2 - 6, h - 20), 0, 200, 340, 255, 34)
    elif item.shape in {"bag", "box", "brick", "keyboard", "cable", "roll"}:
        radius = 10 if item.shape != "roll" else h // 2 - 4
        _rounded_rect(mask, (6, 6, w - 12, h - 12), radius, 255)
    elif item.shape in {"can", "bottle", "cup", "phone", "phone_cracked", "mouse"}:
        radius = 8 if item.shape in {"phone", "phone_cracked"} else w // 3
        _rounded_rect(mask, (8, 6, w - 16, h - 12), radius, 255)
    else:
        _rounded_rect(mask, (6, 6, w - 12, h - 12), 12, 255)


def _draw_detail(canvas: np.ndarray, item: Item) -> None:
    h, w = canvas.shape[:2]
    dark = tuple(int(c * 0.6) for c in item.colour)
    if item.shape == "keyboard":
        for row in range(3):
            for col in range(12):
                x = 22 + col * 28
                y = 26 + row * 26
                cv2.rectangle(canvas, (x, y), (x + 20, y + 18), (*dark, 255), -1)
        _paste_qr(canvas, KEYBOARD_TAG)
        return
    if item.shape == "phone_cracked":
        cv2.rectangle(canvas, (10, 16), (w - 10, h - 30), (188, 190, 196, 255), -1)
        for pts in (
            [(20, 30), (60, 90), (36, 140), (80, 186)],
            [(90, 40), (54, 96), (92, 150)],
        ):
            cv2.polylines(canvas, [np.array(pts, dtype=np.int32)], False, (40, 40, 44, 255), 2)
        return
    if item.shape == "phone":
        cv2.rectangle(canvas, (10, 16), (w - 10, h - 30), (150, 158, 166, 255), -1)
        return
    if item.shape == "can":
        cv2.rectangle(canvas, (8, 12), (w - 8, 26), (216, 216, 216, 255), -1)
        return
    if item.shape == "bottle":
        cv2.rectangle(canvas, (w // 3, 4), (2 * w // 3, 40), (236, 236, 236, 255), -1)
        return
    if item.shape == "brick":
        cv2.rectangle(canvas, (w - 44, h // 2 - 22), (w - 12, h // 2 + 22), (70, 70, 70, 255), -1)
        return
    if item.shape == "cable":
        curve = np.array([[20, h - 30], [w // 2, 30], [w - 20, h - 30]], dtype=np.int32)
        cv2.polylines(canvas, [curve], False, (170, 170, 170, 255), 6)


def _draw_label(canvas: np.ndarray, item: Item) -> None:
    h, w = canvas.shape[:2]
    scale = 0.52 if w < 170 else 0.66
    thickness = 1 if w < 170 else 2
    (tw, th), _ = cv2.getTextSize(item.label, FONT, scale, thickness)
    while tw > w - 10 and scale > 0.24:
        # Shrink until the label fits the sprite. Text hanging off the edge would
        # show up in the camera frame as a floating word.
        scale -= 0.04
        thickness = 1 if scale < 0.6 else 2
        (tw, th), _ = cv2.getTextSize(item.label, FONT, scale, thickness)
    x = max(4, (w - tw) // 2)
    y = h - max(10, th // 2)

    text = np.zeros((h, w), dtype=np.uint8)
    cv2.putText(text, item.label, (x, y), FONT, scale, 255, thickness, cv2.LINE_AA)
    hit = text > 0
    for channel, value in enumerate(item.text_colour):
        canvas[:, :, channel][hit] = value
    canvas[:, :, 3] = np.maximum(canvas[:, :, 3], text)


def _paste_qr(canvas: np.ndarray, payload: str) -> None:
    code = cv2.QRCodeEncoder.create().encode(payload)
    size = 104
    big = cv2.resize(code, (size, size), interpolation=cv2.INTER_NEAREST)
    quiet = 10
    tile = np.full((size + 2 * quiet, size + 2 * quiet), 255, dtype=np.uint8)
    tile[quiet : quiet + size, quiet : quiet + size] = big
    side = tile.shape[0]
    x = canvas.shape[1] - side - 12
    y = (canvas.shape[0] - side) // 2
    canvas[y : y + side, x : x + side, :3] = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
    canvas[y : y + side, x : x + side, 3] = 255


def _rounded_rect(
    mask: np.ndarray,
    rect: tuple[int, int, int, int],
    radius: int,
    value: int,
) -> None:
    x, y, w, h = rect
    radius = max(1, min(radius, w // 2, h // 2))
    cv2.rectangle(mask, (x + radius, y), (x + w - radius, y + h), value, -1)
    cv2.rectangle(mask, (x, y + radius), (x + w, y + h - radius), value, -1)
    for cx, cy in (
        (x + radius, y + radius),
        (x + w - radius, y + radius),
        (x + radius, y + h - radius),
        (x + w - radius, y + h - radius),
    ):
        cv2.circle(mask, (cx, cy), radius, value, -1)


def check_qr_survives_a_frame() -> str:
    """Composite the keyboard the way `phone_sim` does and read the tag back."""
    from phone_sim import composite_items

    background = cv2.imread(str(ASSETS / "bin.png"), cv2.IMREAD_COLOR)
    if background is None:
        return ""
    frame = composite_items(background, [ASSETS / "keyboard.png"])
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return ""
    decoded = cv2.imdecode(np.frombuffer(buf.tobytes(), np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        return ""
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(decoded)
    return str(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate simulator item images")
    parser.add_argument("--out", default=str(ASSETS), help="where to write the PNGs")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / "bin.png"), build_background(), [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
    for item in ITEMS:
        path = out / f"{item.slug}.png"
        cv2.imwrite(str(path), build_item(item), [int(cv2.IMWRITE_PNG_COMPRESSION), 9])
        print(f"{path.name:22s} {path.stat().st_size / 1024:6.1f} KB")
    print(f"{'bin.png':22s} {(out / 'bin.png').stat().st_size / 1024:6.1f} KB")

    tag = check_qr_survives_a_frame()
    print(f"QR decoded from a composited frame: {tag!r}")
    return 0 if tag == KEYBOARD_TAG else 1


if __name__ == "__main__":
    raise SystemExit(main())
