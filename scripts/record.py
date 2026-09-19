"""Run the backend with the session recorder on.

The backend is the server on both sockets, so nothing can record the real traffic from
the outside. The recorder lives in the ingest path and is switched on by `RECORD_DIR`,
which is all this script does before handing over to the usual run script.

    uv run --project backend python scripts/record.py --name demo-1

That writes `backend/recordings/demo-1/` with `bin.jsonl`, `phone.jsonl` and the frame
files. Play it back with:

    uv run --project backend python scripts/replay.py --name demo-1 --insecure

Every other argument is passed through to `scripts/run_backend.py`, so `--host`,
`--https-port`, `--http-port` and `--no-http` all work here too.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR))

from app.ingest.recorder import RECORD_ENV  # noqa: E402


def default_name() -> str:
    return datetime.now(UTC).strftime("session-%Y%m%d-%H%M%S")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the backend and record every bin message and camera frame."
    )
    parser.add_argument("--name", default=None, help="recording name, default a timestamp")
    parser.add_argument(
        "--dir",
        default=None,
        help="write here instead of under the configured recordings directory",
    )
    args, rest = parser.parse_known_args(argv)

    target = args.dir or args.name or default_name()
    os.environ[RECORD_ENV] = target
    print(f"recording into {target}")

    from scripts import run_backend

    sys.argv = [sys.argv[0], *rest]
    return run_backend.main()


if __name__ == "__main__":
    raise SystemExit(main())
