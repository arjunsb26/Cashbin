"""Run a scenario against a real backend and print the acceptance table.

    uv run --project backend python scripts/acceptance.py --scenario demo

This is PLAN.md section 20's M1 check, automated, plus the parts of M3 and M5 that the same
run can answer. It starts its own backend on its own ports with its own database, plays the
scenario through the bin and phone simulators exactly as a person would at the terminal,
reads the answers back off the REST surface, and prints one row per check.

The provider is the stub. No key is read and no model is called, whatever the repository's
.env says, because an acceptance run has to give the same answer on a laptop with no
internet.

The tagged keyboard's register row is set through the REST surface at the start of the run,
to the figures this run's arithmetic is checked against, so the check table does not move when
the team changes an approximate price in `assets_seed.csv`. Nothing is ever written back to
that file.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_DIR / "backend"
SIM_DIR = REPO_DIR / "sim"

# Spare ports. Lane D holds 8000 and 8443, the coordinator holds 3000 and 8444.
DEFAULT_HTTPS_PORT = 9443
DEFAULT_HTTP_PORT = 9000

START_TIMEOUT_S = 60.0
SCENARIO_TIMEOUT_S = 300.0

# The tagged keyboard, as a fixture. Nothing here is written to a seed file.
KEYBOARD_TAG = "bb-0002"
KEYBOARD_COST_CENTS = 12_900
KEYBOARD_LIFE_MONTHS = 36

# Every line 2 the bin may draw, from `app/pipeline.py`.
KNOWN_LINES = frozenset(
    {
        "Recycle it instead",
        "Donate it instead",
        "Resell it instead",
        "Repair it instead",
        "Recycle, not trash",
        "Donate it, not trash",
        "Resell it, not trash",
        "Repair it, not trash",
        "Not for the bin",
        "Removed from books",
        "Written off as waste",
        "Nothing on the books",
    }
)
LCD_LINE_MAX = 20


@dataclass
class Check:
    name: str
    expected: str
    observed: str = ""
    passed: bool = False


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, expected: str, observed: Any, passed: bool) -> None:
        self.checks.append(Check(name, expected, str(observed), bool(passed)))

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    def table(self) -> str:
        name_w = max(len(c.name) for c in self.checks)
        exp_w = max(len(c.expected) for c in self.checks)
        obs_w = max(len(c.observed) for c in self.checks)
        head = (
            f"{'check'.ljust(name_w)}  {'expected'.ljust(exp_w)}  "
            f"{'observed'.ljust(obs_w)}  result"
        )
        rule = "-" * len(head)
        rows = [head, rule]
        for check in self.checks:
            mark = "pass" if check.passed else "FAIL"
            rows.append(
                f"{check.name.ljust(name_w)}  {check.expected.ljust(exp_w)}  "
                f"{check.observed.ljust(obs_w)}  {mark}"
            )
        return "\n".join(rows)


# Talking to the backend -------------------------------------------------------


def get(base: str, path: str) -> Any:
    with urllib.request.urlopen(f"{base}{path}", timeout=20) as reply:
        return json.loads(reply.read().decode("utf-8"))


def post(base: str, path: str, body: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as reply:
        return json.loads(reply.read().decode("utf-8"))


def wait_for_health(base: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"the backend stopped before it was ready, exit {process.poll()}")
        try:
            get(base, "/api/health")
            return
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
            time.sleep(0.4)
    raise RuntimeError(f"the backend did not answer on {base} within {START_TIMEOUT_S:.0f} s")


# Running the pieces -----------------------------------------------------------


def backend_env(work: Path, https_port: int, http_port: int) -> dict[str, str]:
    """A clean environment for the run. The stub provider, whatever the .env holds."""
    env = dict(os.environ)
    env.update(
        {
            "DB_PATH": str(work / "binbooks.db"),
            "MEDIA_DIR": str(work / "media"),
            "CERT_DIR": str(work / "certs"),
            "RECORDINGS_DIR": str(work / "recordings"),
            "DEV_TOOLS": "1",
            "SEED_ON_START": "1",
            "HTTPS_PORT": str(https_port),
            "HTTP_PORT": str(http_port),
            "LLM_PROVIDER": "stub",
            "OPENAI_API_KEY": "",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def start_backend(work: Path, https_port: int, http_port: int) -> subprocess.Popen[str]:
    log = (work / "backend.log").open("w", encoding="utf-8")
    return subprocess.Popen(
        [
            sys.executable,
            str(REPO_DIR / "scripts" / "run_backend.py"),
            "--host",
            "127.0.0.1",
            "--https-port",
            str(https_port),
            "--http-port",
            str(http_port),
        ],
        cwd=str(BACKEND_DIR),
        env=backend_env(work, https_port, http_port),
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
    )


def patch(base: str, path: str, body: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    with urllib.request.urlopen(request, timeout=60) as reply:
        return json.loads(reply.read().decode("utf-8"))


def seed_fixture_register(base: str) -> None:
    """Set the tagged keyboard to the figures this run's arithmetic is checked against."""
    today = date.today()
    row = {
        "description": "Mechanical keyboard",
        "category": "peripheral",
        "cost_cents": KEYBOARD_COST_CENTS,
        "in_service_date": today.replace(year=today.year - 1).isoformat(),
        "book_life_months": KEYBOARD_LIFE_MONTHS,
        "salvage_cents": 0,
        "tax_method": "bonus_100",
        "status": "active",
    }
    existing = next(
        (asset for asset in get(base, "/api/assets")["assets"] if asset["tag"] == KEYBOARD_TAG),
        None,
    )
    if existing is None:
        post(base, "/api/assets", {**row, "tag": KEYBOARD_TAG})
        where = "created"
    else:
        patch(base, f"/api/assets/{existing['id']}", row)
        where = "reset"
    print(
        f"register fixture: {KEYBOARD_TAG.upper()} {where} at "
        f"${KEYBOARD_COST_CENTS / 100:,.2f}, bonus_100, in service one year ago. "
        "A run fixture, not a purchase record."
    )


def play_scenario(scenario: str, http_port: int, gap: float, speed: float, work: Path) -> str:
    """Run the simulators against the backend and hand back everything they printed."""
    command = [
        sys.executable,
        str(SIM_DIR / "run_scenario.py"),
        "--scenario",
        scenario,
        "--url",
        f"ws://127.0.0.1:{http_port}/ws/bin",
        "--expect-url",
        f"http://127.0.0.1:{http_port}/api/sim/expect",
        "--gap",
        str(gap),
        "--speed",
        str(speed),
    ]
    result = subprocess.run(
        command,
        cwd=str(SIM_DIR),
        capture_output=True,
        text=True,
        timeout=SCENARIO_TIMEOUT_S,
        check=False,
    )
    output = result.stdout + result.stderr
    (work / "scenario.log").write_text(output, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"the scenario runner exited {result.returncode}\n{output[-2000:]}")
    return output


def lcd_results(output: str) -> list[dict[str, str]]:
    """Every result box the bin simulator drew, read back out of its own log.

    `sim/lcd_box.py` draws four bordered lines: line 1, a blank, the big figure, a blank,
    line 2, then the tone underneath. Reading them back is how this run proves the bin was
    told something, rather than trusting that the backend says it published.
    """
    boxes: list[dict[str, str]] = []
    lines = output.splitlines()
    inner: list[str] = []
    for line in lines:
        text = line.rstrip()
        if text.startswith("|") and text.endswith("|"):
            inner.append(text[1:-1].strip())
            continue
        if inner:
            body = [part for part in inner if part]
            if len(body) >= 3:
                boxes.append({"l1": body[0], "big": body[1], "l2": body[2]})
            inner = []
    return [box for box in boxes if box["l2"] in KNOWN_LINES]


# The checks -------------------------------------------------------------------


def option_rows(detail: dict[str, Any], option: str) -> dict[str, Any] | None:
    for row in detail.get("options", []):
        if row["option"] == option:
            return dict(row)
    return None


def run_checks(base: str, output: str) -> Report:
    report = Report()

    events = get(base, "/api/events")["events"]
    tosses = [row for row in events if row["kind"] == "toss"]
    changes = [row for row in events if row["kind"] == "bag_change"]
    report.add("M1 events on the API", "5", len(events), len(events) == 5)
    report.add(
        "M1 tosses posted",
        "4 posted",
        f"{sum(1 for row in tosses if row['status'] == 'posted')} of {len(tosses)}",
        len(tosses) == 4 and all(row["status"] == "posted" for row in tosses),
    )
    report.add(
        "M1 bag change not ticketed",
        "1 detected",
        f"{len(changes)} {[row['status'] for row in changes]}",
        len(changes) == 1 and changes[0]["status"] == "detected",
    )

    boxes = lcd_results(output)
    report.add("M1 LCD result screens", "4", len(boxes), len(boxes) == 4)
    too_long = [box["l2"] for box in boxes if len(box["l2"]) > LCD_LINE_MAX]
    report.add(
        "LCD line 2 fits and is known copy",
        "every line",
        f"{len(boxes)} lines, {len(too_long)} too long",
        bool(boxes) and not too_long,
    )

    journal = get(base, "/api/journal?basis=book")
    entries = journal["entries"]
    unbalanced = [
        entry["memo"]
        for entry in entries
        if sum(line["debit_cents"] for line in entry["lines"])
        != sum(line["credit_cents"] for line in entry["lines"])
    ]
    report.add(
        "M1 every entry balances",
        "0 unbalanced",
        f"{len(entries)} entries, {len(unbalanced)} unbalanced",
        bool(entries) and not unbalanced,
    )
    debit_total = sum(row["debit_cents"] for row in journal["trial_balance"])
    credit_total = sum(row["credit_cents"] for row in journal["trial_balance"])
    report.add(
        "M1 trial balance",
        "debits equal credits",
        f"{debit_total} / {credit_total}",
        debit_total == credit_total,
    )

    by_label = {row["label"]: row for row in tosses}
    keyboard = by_label.get("mechanical keyboard")
    if keyboard is None:
        report.add("M3 tagged keyboard", "a fixed asset disposal", "no keyboard ticket", False)
    else:
        detail = get(base, f"/api/events/{keyboard['id']}")
        record = detail["item_record"] or {}
        bases = {entry["basis"] for entry in detail["entries"]}
        report.add(
            "M3 keyboard book loss and tax basis",
            "book > 0, tax basis 0",
            f"book {record.get('book_value_cents')} tax {record.get('tax_basis_cents')}",
            keyboard["class"] == "fixed_asset"
            and (record.get("book_value_cents") or 0) > 0
            and record.get("tax_basis_cents") == 0,
        )
        report.add(
            "M3 disposal and tax memo entries",
            "book and tax_memo",
            ", ".join(sorted(bases)) or "none",
            {"book", "tax_memo"} <= bases,
        )
        assets = get(base, "/api/assets")["assets"]
        tagged = next((row for row in assets if row["tag"] == KEYBOARD_TAG), None)
        report.add(
            "M3 asset off the register",
            "disposed",
            (tagged or {}).get("status", "missing"),
            bool(tagged) and tagged["status"] == "disposed",
        )

    bagel = by_label.get("bagel")
    if bagel is None:
        report.add("M3 bagel", "donate above trash", "no bagel ticket", False)
    else:
        detail = get(base, f"/api/events/{bagel['id']}")
        donate = option_rows(detail, "donate") or {}
        trash = option_rows(detail, "trash") or {}
        ranks_right = (
            donate.get("rank") is not None
            and trash.get("rank") is not None
            and donate["rank"] < trash["rank"]
        )
        report.add(
            "M3 bagel donate beats trash",
            "donate ranked first, review",
            f"donate {donate.get('rank')} trash {trash.get('rank')} "
            f"review {donate.get('needs_human_review')}",
            ranks_right and bool(donate.get("needs_human_review")),
        )

    blocked_ok = True
    seen = []
    for label in ("usb-c charger", "phone"):
        row = by_label.get(label)
        if row is None:
            blocked_ok = False
            seen.append(f"{label}: missing")
            continue
        trash = option_rows(get(base, f"/api/events/{row['id']}"), "trash") or {}
        blocked_ok = blocked_ok and trash.get("allowed") is False
        seen.append(f"{label}: allowed={trash.get('allowed')}")
    report.add("M3 electronics blocked from the bin", "both blocked", "; ".join(seen), blocked_ok)

    summary = get(base, "/api/summary")
    report.add(
        "header totals",
        "4 tosses, money saved",
        f"{summary['events']} tosses, {summary['saved_if_followed_cents']} cents",
        summary["events"] == 4 and summary["saved_if_followed_cents"] > 0,
    )

    today = date.today().isoformat()
    close = post(base, "/api/close", {"period_start": today, "period_end": today})
    failed = [check["id"] for check in close["checks"] if check["result"] != "pass"]
    report.add(
        "M5 close runs clean",
        "5 checks pass",
        f"{len(close['checks'])} checks, failed {failed or 'none'}",
        len(close["checks"]) == 5 and not failed,
    )

    setup = get(base, "/api/setup")["items"]
    report.add(
        "setup checklist answers",
        "a list, however short",
        f"{len(setup)} cells still waiting on a person",
        isinstance(setup, list),
    )
    return report


# Entry point ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scenario and print the check table.")
    parser.add_argument("--scenario", default="demo")
    parser.add_argument("--https-port", type=int, default=DEFAULT_HTTPS_PORT)
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--gap", type=float, default=2.0, help="seconds between tosses")
    parser.add_argument("--speed", type=float, default=3.0, help="wall clock multiplier")
    parser.add_argument("--keep", action="store_true", help="keep the run directory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    work = Path(tempfile.mkdtemp(prefix="binbooks-acceptance-"))
    base = f"http://127.0.0.1:{args.http_port}"
    print(f"run directory {work}")
    process = start_backend(work, args.https_port, args.http_port)
    try:
        wait_for_health(base, process)
        print(f"backend up on {base} with the stub provider")
        seed_fixture_register(base)
        output = play_scenario(args.scenario, args.http_port, args.gap, args.speed, work)
        report = run_checks(base, output)
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()

    print()
    print(report.table())
    print()
    failed = [check.name for check in report.checks if not check.passed]
    if failed:
        print(f"{len(failed)} checks failed: {', '.join(failed)}")
        print(f"logs are in {work}")
        return 1
    print(f"all {len(report.checks)} checks passed")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"logs are in {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
