"""Optional session recorder. Replay is the demo insurance if the hardware fails.

PLAN.md section 16 wants every incoming bin and phone message on disk with its arrival
time. The backend is the server on both sockets, so a recorder that connects as a
client would record a second conversation rather than the real one. It lives inside the
ingest path instead, and `scripts/record.py` is a launcher that switches it on.

On disk, one recording is a directory:

    meta.json          name, when it started, the wire clock offset
    bin.jsonl          {"t": seconds since start, "msg": {...}} per line
    phone.jsonl        {"t": seconds since start, "file": "phone/000001.jpg"} per line
    phone/000001.jpg   the frame bytes exactly as they arrived

`scripts/replay.py` reads that back and plays it into a running backend.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.config import Settings

log = logging.getLogger(__name__)

RECORD_ENV = "RECORD_DIR"
META_FILE = "meta.json"
BIN_FILE = "bin.jsonl"
PHONE_INDEX = "phone.jsonl"
PHONE_DIR = "phone"

# How often the metadata counts are refreshed while a recording runs.
META_EVERY = 100


class Recorder:
    """Appends bin messages and phone frames to one recording directory."""

    def __init__(self, directory: Path, name: str | None = None) -> None:
        self.directory = directory
        self.name = name or directory.name
        self.started_at = time.time()
        self._t0 = time.monotonic()
        self._frames = 0
        self._lines = 0
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / PHONE_DIR).mkdir(parents=True, exist_ok=True)
        self._write_meta()

    @property
    def frame_count(self) -> int:
        return self._frames

    @property
    def line_count(self) -> int:
        return self._lines

    def elapsed_s(self) -> float:
        return time.monotonic() - self._t0

    def bin_message(self, message: dict[str, Any]) -> None:
        """One text frame off `/ws/bin`, already parsed. Unparseable text is not recorded."""
        self._append(BIN_FILE, {"t": round(self.elapsed_s(), 4), "msg": message})
        self._lines += 1
        self._maybe_refresh_meta()

    def phone_frame(self, jpeg: bytes) -> None:
        """One binary frame off `/ws/phone`, written beside an index line."""
        index = self._frames
        rel = f"{PHONE_DIR}/{index:06d}.jpg"
        try:
            (self.directory / rel).write_bytes(jpeg)
        except OSError:
            log.exception("could not record phone frame %d", index)
            return
        self._frames += 1
        self._append(PHONE_INDEX, {"t": round(self.elapsed_s(), 4), "file": rel})
        self._maybe_refresh_meta()

    def close(self) -> None:
        self._write_meta(done=True)
        log.info(
            "recording %s closed with %d bin messages and %d frames",
            self.name,
            self._lines,
            self._frames,
        )

    def _maybe_refresh_meta(self) -> None:
        """Keep the counts honest for a process that is killed rather than shut down.

        A recording is worth most when the thing being recorded fell over, and that is
        exactly the case where `close` never runs.
        """
        if (self._lines + self._frames) % META_EVERY == 0:
            self._write_meta()

    def _write_meta(self, done: bool = False) -> None:
        meta = {
            "name": self.name,
            "started_at": self.started_at,
            "duration_s": round(self.elapsed_s(), 4),
            "bin_messages": self._lines,
            "phone_frames": self._frames,
            "complete": done,
        }
        try:
            (self.directory / META_FILE).write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )
        except OSError:
            log.exception("could not write recording metadata")

    def _append(self, filename: str, row: dict[str, Any]) -> None:
        try:
            with (self.directory / filename).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        except OSError:
            log.exception("could not append to %s", filename)


def recording_dir(raw: str, settings: Settings) -> Path:
    """Read RECORD_DIR either way round.

    A bare name is a folder under the configured recordings directory, which is what
    `scripts/record.py --name demo` produces. Anything with a separator or a drive
    letter is taken as the directory itself.
    """
    cleaned = raw.strip().strip('"')
    candidate = Path(cleaned)
    if candidate.is_absolute() or len(candidate.parts) > 1:
        return candidate
    return settings.recordings_dir / cleaned


def recorder_from_env(settings: Settings) -> Recorder | None:
    """Build a recorder when RECORD_DIR is set, and nothing otherwise."""
    raw = os.environ.get(RECORD_ENV, "")
    if not raw.strip():
        return None
    directory = recording_dir(raw, settings)
    recorder = Recorder(directory)
    log.info("recording this session into %s", directory)
    return recorder
