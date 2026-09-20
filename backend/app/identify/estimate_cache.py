"""Where a value estimate is kept so the same object is never priced twice.

PLAN.md 21a item 47: estimates are stable, which means the figure a person saw on the bin
is the figure they see on the dashboard an hour later and after a restart. Two things make
that true. The key is everything the estimator was told, not the label alone, so a mouse
with "MX Master 3" legible on it and a mouse with nothing legible are two different objects
with two different prices. And the whole cache is one row in the `settings` table, held as
one JSON object, read once at start and written back on every store, so a restart mid demo
keeps every figure anybody has already been shown.

One row rather than one row per label is deliberate. A restart used to mean a query per
label, and the settings table is also where the runtime settings live, so a cache that
grows a row per object seen makes that table unreadable by hand. It also gives the cache a
size cap it can actually enforce.

Outside text goes through the same wall here as everywhere else. A label that will not
normalise is refused rather than stored, because a cache key is a key.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pydantic import ValidationError

from app.schemas import ValueEstimate, _clean_free_text, normalise_label

log = logging.getLogger(__name__)

# The one settings row the whole cache lives in.
CACHE_SETTING_KEY = "estimate_cache"
# How many objects to remember. Oldest stored goes first. A demo sees tens, not hundreds.
MAX_ENTRIES = 400
# How much of each piece of outside text takes part in the key.
CONTEXT_MAX = 120


def cache_key(label: str, visible_text: str = "", detail: str = "",
              condition: str = "") -> str:
    """The key for one priced object: its label and what else the estimator was told.

    With nothing else to go on the key is the normalised label itself, which is what the
    rest of the system looks an estimate up by. Anything else adds a short digest, so two
    keys that differ read as the same object seen two ways rather than as two labels.
    """
    name = normalise_label(label)
    parts = [
        str(_clean_free_text(visible_text, CONTEXT_MAX) or ""),
        str(_clean_free_text(detail, CONTEXT_MAX) or ""),
        str(_clean_free_text(condition, CONTEXT_MAX) or "").lower(),
    ]
    if not any(part for part in parts if part and part != "unknown"):
        return name
    digest = hashlib.sha1("\u001f".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{name}|{digest}"


class EstimateCache:
    """The settings row, in memory. One instance per process; a new one reads it back."""

    def __init__(self, source: str = "") -> None:
        self._entries: dict[str, ValueEstimate] = {}
        self._latest: dict[str, str] = {}
        self._loaded = False
        # Which database this cache belongs to. Point the app at another file and the
        # figures in memory are somebody else's, so the cache is rebuilt rather than reused.
        self.source = source

    # Reading -----------------------------------------------------------------

    def load(self) -> None:
        """Read the row once. An unreadable row is an empty cache, never an error."""
        self._loaded = True
        raw = self._read_row()
        if not raw:
            return
        try:
            document = json.loads(raw)
            entries = document.get("entries", {})
            latest = document.get("latest", {})
        except (json.JSONDecodeError, AttributeError):
            log.warning("the stored estimate cache is not readable and was dropped")
            return
        if not isinstance(entries, dict) or not isinstance(latest, dict):
            log.warning("the stored estimate cache has the wrong shape and was dropped")
            return
        for key, value in entries.items():
            try:
                self._entries[str(key)] = ValueEstimate.model_validate(value)
            except (ValidationError, ValueError):
                log.warning("one stored estimate would not validate and was dropped")
        self._latest = {
            str(name): str(key)
            for name, key in latest.items()
            if str(key) in self._entries
        }

    def get(self, key: str) -> ValueEstimate | None:
        """The estimate for this key, or the newest one for this label, or nothing."""
        if not self._loaded:
            self.load()
        found = self._entries.get(key)
        if found is not None:
            return found
        # A caller with only a label, which is what the pipeline has when it draws a ticket,
        # gets the most recent estimate stored under that label.
        alias = self._latest.get(key)
        return self._entries.get(alias) if alias else None

    # Writing -----------------------------------------------------------------

    def put(self, key: str, estimate: ValueEstimate) -> None:
        """Store one estimate and write the row back. A dead database is not fatal."""
        if not self._loaded:
            self.load()
        self._entries.pop(key, None)
        self._entries[key] = estimate
        self._latest[key.split("|", 1)[0]] = key
        while len(self._entries) > MAX_ENTRIES:
            oldest = next(iter(self._entries))
            del self._entries[oldest]
            self._latest = {
                name: at for name, at in self._latest.items() if at in self._entries
            }
        self._write_row()

    def clear(self) -> None:
        """Forget everything, in memory and in the row. Used by the tests and the kit page."""
        self._entries.clear()
        self._latest.clear()
        self._loaded = True
        self._write_row()

    # The row itself ----------------------------------------------------------

    def as_document(self) -> dict[str, Any]:
        """What goes in the row: every estimate, and which key each label last used."""
        return {
            "v": 1,
            "entries": {k: v.model_dump(mode="json") for k, v in self._entries.items()},
            "latest": dict(self._latest),
        }

    @staticmethod
    def _read_row() -> str:
        from app.db import session_scope
        from app.models import Setting

        try:
            with session_scope() as session:
                row = session.get(Setting, CACHE_SETTING_KEY)
                return str(row.value_json) if row else ""
        except (ValueError, OSError):
            log.warning("the estimate cache is unreadable, this run starts with none")
            return ""

    def _write_row(self) -> None:
        from app.db import session_scope
        from app.models import Setting

        payload = json.dumps(self.as_document(), ensure_ascii=True)
        try:
            with session_scope() as session:
                row = session.get(Setting, CACHE_SETTING_KEY)
                if row is None:
                    session.add(Setting(key=CACHE_SETTING_KEY, value_json=payload))
                else:
                    row.value_json = payload
        except (ValueError, OSError):
            log.warning("the estimate cache is unavailable, nothing was stored")


def _db_source() -> str:
    """Which database the app is pointed at right now."""
    try:
        from app.config import get_settings

        return str(get_settings().db_path)
    except (ValueError, OSError):
        return ""


_CACHE = EstimateCache(_db_source())


def get_cache() -> EstimateCache:
    """The process's cache. One object, so a store is visible to every reader at once."""
    global _CACHE
    source = _db_source()
    if _CACHE.source != source:
        _CACHE = EstimateCache(source)
    return _CACHE


def reset_cache() -> EstimateCache:
    """A fresh cache that has not read the row yet. What a restart looks like."""
    global _CACHE
    _CACHE = EstimateCache(_db_source())
    return _CACHE


def read_estimate(key: str) -> ValueEstimate | None:
    """The stored estimate for a key or a bare label, or nothing."""
    try:
        return get_cache().get(key if "|" in key else normalise_label(key))
    except ValueError:
        log.warning("an estimate was looked up under something that is not a label")
        return None


def write_estimate(key: str, estimate: ValueEstimate) -> None:
    """Store one estimate under a key from `cache_key`, or under a bare label."""
    try:
        get_cache().put(key if "|" in key else normalise_label(key), estimate)
    except ValueError:
        log.warning("an estimate was stored under something that is not a label, ignored")
