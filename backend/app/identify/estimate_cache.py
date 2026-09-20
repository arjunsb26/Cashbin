"""Where a value estimate is kept so the same object is never priced twice.

PLAN.md section 9: "Cache by normalised label so the same object is never estimated twice."
The cache lives in the `settings` table under `estimate:<label>`, so it survives a restart
and a demo run does not pay for the same keyboard three times.

The key is a normalised label, which means a label that has been through the same wall as
every other piece of outside text. Anything that will not survive that is refused here
rather than stored, because a cache key is a key like any other.
"""

from __future__ import annotations

import hashlib
import logging

from pydantic import ValidationError

from app.schemas import ValueEstimate, VisionResult, normalise_label

log = logging.getLogger(__name__)

KEY_PREFIX = "estimate:"


def cache_key(label: str) -> str:
    """The settings key for one label. Raises if the label is not a label."""
    return f"{KEY_PREFIX}{normalise_label(label)}"


def estimate_key(label: str, vision: VisionResult | None = None) -> str:
    """What makes two estimates the same estimate.

    The label alone made every mouse one entry, so the first one priced set the price for
    every mouse after it. Anything legible on the thing goes in the key as well, which is
    what tells a fifteen dollar mouse from a hundred and fifty dollar one. It is hashed
    rather than stored, because it is outside text and a key is not the place for prose.
    """
    text = (vision.visible_text if vision else "") or ""
    if not text.strip():
        return normalise_label(label)
    digest = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"{normalise_label(label)} {digest}"


def read_estimate(label: str) -> ValueEstimate | None:
    """The stored estimate, or nothing. An unreadable row is a miss, never an error."""
    from app.db import session_scope
    from app.models import Setting

    try:
        with session_scope() as session:
            row = session.get(Setting, cache_key(label))
            return ValueEstimate.model_validate_json(row.value_json) if row else None
    except (ValidationError, ValueError, OSError):
        log.warning("no readable cached estimate for %s", label)
        return None


def write_estimate(label: str, estimate: ValueEstimate) -> None:
    """Store one estimate, replacing whatever was there. A dead database is not fatal."""
    from app.db import session_scope
    from app.models import Setting

    try:
        with session_scope() as session:
            key = cache_key(label)
            row = session.get(Setting, key)
            if row is None:
                session.add(Setting(key=key, value_json=estimate.model_dump_json()))
            else:
                row.value_json = estimate.model_dump_json()
    except (ValueError, OSError):
        log.warning("the estimate cache is unavailable, %s was not stored", label)
