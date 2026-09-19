"""What happens when a person answers, and what the system keeps from it.

PLAN.md section 9, last paragraph. One answer does four things: it settles this event, it
leaves an exemplar so the next one is free, it moves the label's mass prior, and it tells
the round whether the system had been confidently wrong.

The answer has already been through ValidatedLabel by the time it arrives, so what lands
here is a plain lowercase label of at most forty characters. It is matched against the
catalog first, because a catalog hit also settles the class.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.identify.pipeline import IdentifyDeps, catalog_facts, get_deps, store_exemplar
from app.identify.priors import MassPrior, welford_update
from app.learn import metrics, rounds
from app.models import (
    CatalogItem,
    Correction,
    Event,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
)
from app.notify.bus import CHANNEL_PHONE, CHANNEL_UI
from app.schemas import CorrectionCreate, CorrectionResponse, PhoneIdle, UiAskResolved

log = logging.getLogger(__name__)

ANSWERABLE = (
    EventStatus.asking,
    EventStatus.identified,
    EventStatus.confirmed,
    EventStatus.posted,
)


class CorrectionRefusedError(ValueError):
    """The answer cannot be applied. The message is plain, because a person may read it."""


def load_crop(settings: Settings, event: Event) -> bytes | None:
    """The stored crop for this event, or nothing when the file is not there."""
    if not event.crop:
        return None
    name = event.crop.removeprefix("/media/").lstrip("/")
    path = Path(event.crop) if Path(event.crop).is_absolute() else settings.media_dir / name
    try:
        return path.read_bytes()
    except OSError:
        log.warning("no crop file on disk for event %s", event.id)
        return None


def _previous_final(session: Session, event_id: int) -> Identification | None:
    return (
        session.execute(
            select(Identification)
            .where(Identification.event_id == event_id, Identification.is_final.is_(True))
            .order_by(Identification.id.desc())
        )
        .scalars()
        .first()
    )


def update_mass_prior(session: Session, label: str, item_class: ItemClass, mass_g: float) -> None:
    """Fold this weighing into the label's prior, creating the catalog row when it is new."""
    row = session.execute(select(CatalogItem).where(CatalogItem.label == label)).scalars().first()
    if row is None:
        row = CatalogItem(label=label, item_class=item_class, mass_prior_n=0)
        session.add(row)
    prior = MassPrior(
        mean_g=row.mass_prior_mean_g or 0.0,
        var=row.mass_prior_var or 0.0,
        n=row.mass_prior_n or 0,
    )
    updated = welford_update(prior, mass_g)
    row.mass_prior_mean_g = updated.mean_g
    row.mass_prior_var = updated.var
    row.mass_prior_n = updated.n
    session.flush()


async def apply_correction(
    body: CorrectionCreate, deps: IdentifyDeps | None = None
) -> CorrectionResponse:
    """Apply one answer, then tell every surface and the round about it."""
    active = deps or get_deps()
    session = active.session_factory()
    try:
        event = session.get(Event, body.event_id)
        if event is None:
            raise CorrectionRefusedError("That ticket does not exist.")
        if event.status not in ANSWERABLE:
            raise CorrectionRefusedError("That ticket is not waiting for an answer.")

        label = str(body.label)
        facts = catalog_facts(session)
        item_class = body.item_class or facts.classes.get(label)
        previous = _previous_final(session, event.id)
        was_confident = (
            previous is not None
            and previous.method is not IdentifyMethod.human
            and event.status is not EventStatus.asking
        )
        if item_class is None:
            item_class = (
                previous.item_class
                if previous is not None and previous.item_class is not None
                else ItemClass.untracked
            )

        session.add(
            Correction(
                event_id=event.id,
                field="label",
                old_value=previous.label if previous else None,
                new_value=label,
                by=body.by,
            )
        )
        if body.item_class is not None:
            session.add(
                Correction(
                    event_id=event.id,
                    field="class",
                    old_value=(
                        previous.item_class.value
                        if previous and previous.item_class
                        else None
                    ),
                    new_value=item_class.value,
                    by=body.by,
                )
            )
        if previous is not None:
            previous.is_final = False

        final = Identification(
            event_id=event.id,
            method=IdentifyMethod.human,
            label=label,
            item_class=item_class,
            confidence=1.0,
            is_final=True,
            provider="human",
            model=body.by,
        )
        session.add(final)
        event.status = EventStatus.confirmed
        session.flush()

        crop = load_crop(active.settings, event)
        if crop:
            store_exemplar(
                session, active, event=event, label=label, crop=crop, confirmed_by=body.by
            )
        if event.mass_g is not None:
            update_mass_prior(session, label, item_class, event.mass_g)
        if was_confident:
            rounds.count_override(session, event)

        correction_id = (
            session.execute(
                select(Correction.id)
                .where(Correction.event_id == event.id)
                .order_by(Correction.id.desc())
            ).scalars().first()
            or 0
        )
        status = event.status
        session.commit()

        active.bus.publish(
            UiAskResolved(event_id=event.id, label=label, by=body.by), CHANNEL_UI
        )
        active.bus.publish(PhoneIdle(), CHANNEL_PHONE)
        metrics.publish_metrics(session, active.bus)
        await active.on_final(event.id, label, item_class, IdentifyMethod.human)
        return CorrectionResponse.model_validate(
            {
                "event_id": event.id,
                "label": label,
                "class": item_class,
                "correction_id": int(correction_id),
                "status": status,
            }
        )
    finally:
        session.commit()
        session.close()
