"""Turn the EPA WARM workbook into backend/data/warm_factors.csv.

WARM version 16 ships as a single Excel workbook. The sheet named "Summary Data"
holds one row per material and one column per fate, in MTCO2E per short ton.
This script copies those numbers out verbatim. It never fills a blank.

Usage:

    uv run --with xlrd python ../scripts/extract_warm.py path/to/warm_v16.xls

Download the workbook from
https://www.epa.gov/waste-reduction-model/versions-waste-reduction-model

The reader library is imported lazily because neither xlrd nor openpyxl is a
project dependency. Run the script through `uv run --with xlrd` for a .xls file
and `uv run --with openpyxl` for a .xlsx file.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

SHEET = "Summary Data"

# The workbook's own column headings, matched exactly.
COLUMNS: dict[str, str] = {
    "source_reduction": "Source Reduction: Current Mix or 100% Virgin",
    "recycle": "Recycling of Post-Consumer Material: Default or Customized Transportation Distance",
    "landfill": "Landfilling, National Average: Default or Customized Transportation Distance",
    "combust": "Combustion",
    "composting": "Composting",
}

OUTPUT_FIELDS = [
    "material",
    "landfill",
    "recycle",
    "compost",
    "combust",
    "source_reduction",
    "source",
    "needs_human_check",
    "warm_material",
]

# A few WARM names are long. These short keys are what the catalog uses.
RENAMES: dict[str, str] = {
    "mixed_paper_general": "mixed_paper",
    "mixed_paper_primarily_residential": "mixed_paper_residential",
    "mixed_paper_primarily_from_offices": "mixed_paper_office",
    "food_waste_non_meat": "food_waste_non_meat",
    "food_waste_meat_only": "food_waste_meat",
    "magazines_third_class_mail": "magazines",
}



def slug(name: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return RENAMES.get(out, out)


def read_sheet(path: Path) -> list[list[Any]]:
    """Return the Summary Data sheet as a list of rows."""
    if path.suffix.lower() == ".xls":
        try:
            import xlrd
        except ImportError:
            print(
                "This is a .xls workbook and the xlrd package is not installed.\n"
                "Run the script again as: uv run --with xlrd python scripts/extract_warm.py "
                f"{path}",
                file=sys.stderr,
            )
            raise SystemExit(2) from None
        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_name(SHEET)
        return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]

    try:
        import openpyxl
    except ImportError:
        print(
            "This is a .xlsx workbook and the openpyxl package is not installed.\n"
            "Run the script again as: uv run --with openpyxl python scripts/extract_warm.py "
            f"{path}",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    book = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    sheet = book[SHEET]
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def cell(value: Any) -> str:
    """Render one factor. A blank stays blank, never a zero."""
    if value is None or isinstance(value, str | bool):
        # "NA" and every other word in this sheet means the fate does not apply.
        return ""
    return repr(float(value))


def extract(path: Path) -> list[dict[str, str]]:
    rows = read_sheet(path)
    if not rows:
        raise SystemExit(f"{SHEET} is empty in {path}")
    header = [str(h or "").strip() for h in rows[0]]
    index: dict[str, int] = {}
    for key, title in COLUMNS.items():
        wanted = title.strip()
        matches = [i for i, h in enumerate(header) if h == wanted]
        if not matches:
            raise SystemExit(f"column not found in {SHEET}: {title}")
        index[key] = matches[0]

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows[1:]:
        name = str(row[0] or "").strip()
        if not name or name.lower().startswith("all units"):
            continue
        key = slug(name)
        if not key or key in seen:
            continue
        seen.add(key)
        record = {
            "material": key,
            "landfill": cell(row[index["landfill"]]),
            "recycle": cell(row[index["recycle"]]),
            "compost": cell(row[index["composting"]]),
            "combust": cell(row[index["combust"]]),
            "source_reduction": cell(row[index["source_reduction"]]),
            "source": "WARM_v16_xls",
            "needs_human_check": "false",
            "warm_material": name,
        }
        if not any(record[f] for f in OUTPUT_FIELDS[1:6]):
            continue
        out.append(record)
    return out


def main() -> None:
    here = Path(__file__).resolve().parent
    default_out = here.parent / "backend" / "data" / "warm_factors.csv"
    parser = argparse.ArgumentParser(description="Extract WARM factors into a CSV.")
    parser.add_argument("workbook", type=Path, help="path to warm_v16.xls or .xlsx")
    parser.add_argument("--out", type=Path, default=default_out, help="output CSV path")
    args = parser.parse_args()

    if not args.workbook.exists():
        raise SystemExit(f"workbook not found: {args.workbook}")

    records = extract(args.workbook)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"wrote {len(records)} materials to {args.out}")
    print("units are MTCO2E per short ton, exactly as the workbook states")


if __name__ == "__main__":
    main()
