"""QR asset tags, the first and cheapest stage of identification.

PLAN.md section 9 item 1. A printed tag in the after or peak frame is an exact match against
the asset register, so a tagged keyboard never needs a model at all. Whatever the camera read
goes through normalise_label before it is used, because a QR code is outside text like any
other: someone can print one that says anything.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identify.embed import decode_jpeg
from app.models import Asset
from app.schemas import normalise_label


def _decode_one(frame: bytes) -> list[str]:
    """Every QR payload in one frame. A frame that will not decode contributes nothing."""
    try:
        image = decode_jpeg(frame)
    except ValueError:
        return []
    detector = cv2.QRCodeDetector()
    found: list[str] = []
    ok, payloads, _points, _codes = detector.detectAndDecodeMulti(image)
    if ok and payloads:
        found.extend(str(p) for p in payloads if p)
    if not found:
        single, _points_one, _code = detector.detectAndDecode(image)
        if single:
            found.append(str(single))
    return found


def read_tags(frames: Sequence[bytes]) -> list[str]:
    """Tags read off the given frames, in the order seen, each one validated and deduplicated."""
    tags: list[str] = []
    for frame in frames:
        for payload in _decode_one(frame):
            try:
                tag = normalise_label(payload)
            except ValueError:
                continue
            if tag not in tags:
                tags.append(tag)
    return tags


def match_asset(tags: Sequence[str], session: Session) -> Asset | None:
    """The first tag that is an exact asset tag. No fuzzy matching: a tag is a key."""
    for tag in tags:
        asset = session.execute(select(Asset).where(Asset.tag == tag)).scalars().first()
        if asset is not None:
            return asset
    return None
