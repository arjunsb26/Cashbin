"""Saving event images under the media directory, and turning a stored path into a URL.

The database stores a relative path such as `17/crop.jpg`. The app mounts the media
directory at `/media`, so the URL a client uses is that path with the mount in front.
Keeping the mount out of the column means moving the media directory does not rewrite
every row.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

MEDIA_MOUNT = "/media"

# The four images PLAN.md section 7 keeps for an event.
FRAME_NAMES = ("before", "after", "peak", "crop")


def event_dir(event_id: int, settings: Settings | None = None) -> Path:
    """Where one event's images live. The directory is created on first save, not here."""
    conf = settings or get_settings()
    return conf.media_dir / str(event_id)


def save_jpeg(
    event_id: int,
    name: str,
    data: bytes,
    settings: Settings | None = None,
) -> str | None:
    """Write one JPEG and return the relative path to store on the event row.

    Returns None when there is nothing to write or the write fails. A camera that did
    not deliver is a thin event, not a crash (PLAN.md rule 6), and the same holds for a
    disk that refuses.
    """
    if not data:
        return None
    directory = event_dir(event_id, settings)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{name}.jpg"
        target.write_bytes(data)
    except OSError:
        log.exception("could not save %s for event %d", name, event_id)
        return None
    return f"{event_id}/{name}.jpg"


def media_url(path: str | None) -> str | None:
    """The URL a client fetches for a stored relative path."""
    if not path:
        return None
    if path.startswith(("http://", "https://", MEDIA_MOUNT + "/")):
        return path
    return f"{MEDIA_MOUNT}/{path.lstrip('/')}"
