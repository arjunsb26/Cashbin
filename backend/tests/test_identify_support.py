"""Scaffolding the identification and learning tests share.

Kept in one place so every test builds its crops, its events and its dependencies the same
way. The two tests at the bottom keep this file honest: if the helpers stop producing a
readable JPEG or a readable QR code, they go red here rather than somewhere confusing.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from app.config import Settings
from app.db import get_session_factory, init_db
from app.identify.embed import BaselineEmbedder
from app.identify.memory import MemoryIndex
from app.identify.pipeline import IdentifyDeps, Providers, build_providers
from app.models import Event, EventKind, EventStatus, IdentifyMethod, ItemClass
from app.notify.bus import get_bus


def make_jpeg(
    colour: tuple[int, int, int] = (30, 60, 200),
    patch: tuple[int, int, int] | None = None,
    size: int = 64,
) -> bytes:
    """A small BGR JPEG. Different colours give crops the embedder tells apart."""
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = colour
    if patch is not None:
        image[size // 4 : size // 2, size // 4 : size // 2] = patch
    ok, buffer = cv2.imencode(".jpg", image)
    assert ok
    return bytes(buffer.tobytes())


def qr_jpeg(text: str) -> bytes:
    """A photographable QR code carrying `text`, on a white background with a quiet zone."""
    code = cv2.QRCodeEncoder.create().encode(text)
    big = cv2.resize(code, (320, 320), interpolation=cv2.INTER_NEAREST)
    canvas = np.full((400, 400), 255, dtype=np.uint8)
    canvas[40:360, 40:360] = big
    ok, buffer = cv2.imencode(".jpg", cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR))
    assert ok
    return bytes(buffer.tobytes())


def setup_db(settings: Settings) -> None:
    init_db(settings)


def make_event(
    session: object,
    *,
    mass_g: float = 95.0,
    mass_err_g: float = 2.0,
    status: EventStatus = EventStatus.detected,
    crop: str | None = None,
) -> Event:
    from sqlalchemy.orm import Session

    assert isinstance(session, Session)
    event = Event(
        kind=EventKind.toss,
        mass_g=mass_g,
        mass_err_g=mass_err_g,
        status=status,
        crop=crop,
    )
    session.add(event)
    session.flush()
    return event


def write_crop(settings: Settings, name: str, data: bytes) -> str:
    """Put a crop where the correction path will look for it."""
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    (settings.media_dir / name).write_bytes(data)
    return name


class RecordingFinal:
    """Stands in for the engine and the ledger, which the coordinator attaches later."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, ItemClass, IdentifyMethod]] = []

    async def __call__(
        self, event_id: int, label: str, item_class: ItemClass, method: IdentifyMethod
    ) -> None:
        self.calls.append((event_id, label, item_class, method))


def make_deps(
    settings: Settings,
    *,
    providers: Providers | None = None,
    memory: MemoryIndex | None = None,
    on_final: RecordingFinal | None = None,
) -> IdentifyDeps:
    deps = IdentifyDeps(
        session_factory=get_session_factory(),
        providers=providers or build_providers(settings),
        embedder=BaselineEmbedder(),
        memory=memory or MemoryIndex(),
        settings=settings,
        bus=get_bus(),
    )
    if on_final is not None:
        deps.on_final = on_final
    return deps


class Listener:
    """Reads one bus channel the way a socket would, so a test can assert what was sent."""

    def __init__(self, channel: str) -> None:
        self.subscription = get_bus().subscribe(channel)

    def messages(self) -> list[object]:
        import asyncio

        out: list[object] = []
        while True:
            try:
                message = self.subscription.take_nowait()
            except asyncio.QueueEmpty:
                return out
            if message is not None:
                out.append(message)

    def types(self) -> list[str]:
        return types_of(self.messages())


def types_of(messages: Sequence[object]) -> list[str]:
    return [str(getattr(m, "type", "")) for m in messages]


def test_the_jpeg_helper_produces_something_decodable() -> None:
    image = cv2.imdecode(np.frombuffer(make_jpeg(), np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape == (64, 64, 3)


def test_the_qr_helper_produces_a_readable_code() -> None:
    from app.identify.qr import read_tags

    assert read_tags([qr_jpeg("bb-0002")]) == ["bb-0002"]
