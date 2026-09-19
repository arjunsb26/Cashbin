"""Draw the home screen icons for the phone page.

The icon is a weigh ticket: paper ground, a white sheet, a band across its
top, two ruled lines. Colours are read out of the token block in phone.css so
there is one source for them. Run it after a token change:

    uv run --project backend python phone/dev/make_icons.py
"""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

PHONE = Path(__file__).resolve().parent.parent
CSS = PHONE / "phone.css"
ICONS = PHONE / "icons"
SIZES = (192, 512)

Colour = tuple[int, int, int]


def read_tokens() -> dict[str, Colour]:
    """Pull the colour variables out of the token block in phone.css."""
    text = CSS.read_text(encoding="utf-8")
    tokens: dict[str, Colour] = {}
    for name, value in re.findall(r"--([a-z-]+):\s*(#[0-9A-Fa-f]{6});", text):
        tokens[name] = (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    missing = {"paper", "ink", "surface", "rule"} - tokens.keys()
    if missing:
        raise SystemExit(f"phone.css is missing these tokens: {sorted(missing)}")
    return tokens


def write_png(path: Path, pixels: list[list[Colour]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # no per row filter
        for r, g, b in row:
            raw += bytes((r, g, b))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def draw(size: int, tokens: dict[str, Colour]) -> list[list[Colour]]:
    unit = size / 32
    pixels = [[tokens["paper"] for _ in range(size)] for _ in range(size)]

    def rect(x0: float, y0: float, x1: float, y1: float, colour: Colour) -> None:
        for y in range(max(0, round(y0)), min(size, round(y1))):
            row = pixels[y]
            for x in range(max(0, round(x0)), min(size, round(x1))):
                row[x] = colour

    # the sheet
    rect(5 * unit, 4 * unit, 27 * unit, 28 * unit, tokens["ink"])
    rect(5 * unit + 1, 4 * unit + 1, 27 * unit - 1, 28 * unit - 1, tokens["surface"])
    # the tone band across the top of the sheet
    rect(5 * unit + 1, 4 * unit + 1, 27 * unit - 1, 6 * unit, tokens["ink"])
    # the big figure, drawn as one heavy bar
    rect(8 * unit, 12 * unit, 24 * unit, 17 * unit, tokens["ink"])
    # two ruled lines
    rect(8 * unit, 20 * unit, 24 * unit, 20 * unit + max(1, unit / 2), tokens["rule"])
    rect(8 * unit, 23 * unit, 19 * unit, 23 * unit + max(1, unit / 2), tokens["rule"])
    return pixels


def main() -> None:
    tokens = read_tokens()
    ICONS.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        path = ICONS / f"icon-{size}.png"
        write_png(path, draw(size, tokens))
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
