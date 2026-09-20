"""What the bin saw over time, by day or by week, with the categories behind it.

PLAN.md 21a items 43 and 48. The user asked to "track daily avg weekly avg
whatever, see data, categories" and then for suggestions that are "reasonable,
it shouldnt recommend stupid shit, nothing nonsensical".

So every figure here is arithmetic over rows already in the database, and every
suggestion has to earn its place: it is written only when the money or the count
behind it is large enough to be worth a sentence, it never names an option the
engine did not actually offer for that item, and a comparison between two ranges
is only drawn when both have enough tickets to mean anything. A sentence that
cannot pass those tests is not softened, it is left out.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.engine import carbon
from app.engine.tax import money

# What counts as enough to say out loud. PLAN.md 21a item 48.
MIN_SUGGESTION_CENTS = 200
MIN_SUGGESTION_COUNT = 3
MIN_TREND_TOSSES = 5
MAX_SUGGESTIONS = 5

CATEGORY_FOOD = "food"
CATEGORY_PACKAGING = "packaging"
CATEGORY_EQUIPMENT = "equipment"
CATEGORY_EWASTE = "e-waste"
CATEGORY_OTHER = "other"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_FOOD,
    CATEGORY_PACKAGING,
    CATEGORY_EQUIPMENT,
    CATEGORY_EWASTE,
    CATEGORY_OTHER,
)

EWASTE_FLAGS: frozenset[str] = frozenset({"electronics", "battery"})

# WARM's own material names, grouped the way a person groups a bin.
PACKAGING_MATERIALS: frozenset[str] = frozenset(
    {
        "corrugated_containers",
        "mixed_paper",
        "mixed_paper_residential",
        "mixed_paper_office",
        "office_paper",
        "newspaper",
        "magazines",
        "glass",
        "hdpe",
        "ldpe",
        "lldpe",
        "pet",
        "pp",
        "ps",
        "pvc",
        "pla",
        "mixed_plastics",
        "aluminum_cans",
        "steel_cans",
        "mixed_recyclables",
    }
)

BUCKET_DAY = "day"
BUCKET_WEEK = "week"


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _event_date(row: models.Event) -> date:
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return datetime.now(UTC).date()
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).date()


def parse_day(text: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return fallback


def bucket_start(day: date, bucket: str) -> date:
    """The day a bucket begins. A week begins on its Monday."""
    if bucket == BUCKET_WEEK:
        return day - timedelta(days=day.weekday())
    return day


def category_of(record: models.ItemRecord | None) -> str:
    """Which of the five groups this item belongs to.

    Electronics first, because a laptop is an e-waste problem before it is an
    equipment one, and that is the row a person acts on.
    """
    if record is None:
        return CATEGORY_OTHER
    flags = _loads(record.regulatory_flags_json, [])
    flag_set = {str(flag) for flag in flags} if isinstance(flags, list) else set()
    if EWASTE_FLAGS.intersection(flag_set):
        return CATEGORY_EWASTE
    if record.item_class is models.ItemClass.fixed_asset:
        return CATEGORY_EQUIPMENT

    mix = _loads(record.material_mix_json, {})
    shares: dict[str, float] = {}
    if isinstance(mix, dict):
        for name, share in mix.items():
            try:
                shares[str(name)] = float(share)
            except (TypeError, ValueError):
                continue
    food_share = sum(
        share for name, share in shares.items() if carbon.is_food_material(name)
    )
    if "food" in flag_set or food_share > 0.5:
        return CATEGORY_FOOD
    # Packaging is a stock item made of paper, plastic, glass or metal. An untracked
    # thing made of the same plastic is a chair, not a wrapper, so it stays in other
    # rather than swelling the packaging row with objects nobody buys by the case.
    if record.item_class is not models.ItemClass.inventory:
        return CATEGORY_OTHER
    packaging_share = sum(
        share for name, share in shares.items() if name in PACKAGING_MATERIALS
    )
    if packaging_share > 0.5:
        return CATEGORY_PACKAGING
    return CATEGORY_OTHER


class Loaded:
    """Every row the stats need, read once."""

    def __init__(
        self,
        events: list[models.Event],
        records: dict[int, models.ItemRecord],
        options: dict[int, list[models.OptionScore]],
        finals: dict[int, models.Identification],
    ) -> None:
        self.events = events
        self.records = records
        self.options = options
        self.finals = finals


def load(session: Session, start: date, end: date) -> Loaded:
    """Tickets in the range, with their records, options and final identification."""
    all_events = list(session.scalars(select(models.Event).order_by(models.Event.id)))
    events = [
        row
        for row in all_events
        if row.kind is models.EventKind.toss and start <= _event_date(row) <= end
    ]
    ids = [row.id for row in events]

    records: dict[int, models.ItemRecord] = {}
    options: dict[int, list[models.OptionScore]] = {}
    finals: dict[int, models.Identification] = {}
    if ids:
        for record in session.scalars(
            select(models.ItemRecord).where(models.ItemRecord.event_id.in_(ids))
        ):
            records[record.event_id] = record
        for score in session.scalars(
            select(models.OptionScore)
            .where(models.OptionScore.event_id.in_(ids))
            .order_by(models.OptionScore.id)
        ):
            options.setdefault(score.event_id, []).append(score)
        for ident in session.scalars(
            select(models.Identification)
            .where(models.Identification.event_id.in_(ids))
            .order_by(models.Identification.id)
        ):
            if ident.is_final:
                finals[ident.event_id] = ident
    return Loaded(events, records, options, finals)


def _best(scores: list[models.OptionScore]) -> models.OptionScore | None:
    allowed = [row for row in scores if row.allowed]
    if not allowed:
        return None
    ranked = [row for row in allowed if row.rank == 1]
    return ranked[0] if ranked else max(allowed, key=lambda row: row.net_after_tax_cents)


def _trash(scores: list[models.OptionScore]) -> models.OptionScore | None:
    return next((row for row in scores if row.option is models.OptionKind.trash), None)


class Bucket:
    """One day or one week of tickets, totalled."""

    def __init__(self, start: date) -> None:
        self.start = start
        self.tosses = 0
        self.wasted_cents = 0
        self.book_loss_cents = 0
        self.estimated_value_cents = 0
        self.kg_landfill = 0.0
        self.kg_co2e_avoided = 0.0
        self.asks = 0
        self.settled_by_person = 0
        self.by_category: dict[str, dict[str, float]] = {}

    def category(self, name: str) -> dict[str, float]:
        return self.by_category.setdefault(
            name, {"tosses": 0.0, "cents": 0.0, "kg": 0.0}
        )

    def as_dict(self) -> dict[str, Any]:
        accuracy = (
            None
            if self.tosses == 0
            else round((self.tosses - self.settled_by_person) / self.tosses, 4)
        )
        rows = [
            {
                "category": name,
                "tosses": int(values["tosses"]),
                "cents": int(values["cents"]),
                "kg": round(values["kg"], 4),
            }
            for name, values in self.by_category.items()
            if values["tosses"]
        ]
        rows.sort(key=lambda row: (-int(str(row["cents"])), str(row["category"])))
        return {
            "start": self.start.isoformat(),
            "tosses": self.tosses,
            "wasted_cents": self.wasted_cents,
            "book_loss_cents": self.book_loss_cents,
            "estimated_value_cents": self.estimated_value_cents,
            "kg_landfill": round(self.kg_landfill, 4),
            "kg_co2e_avoided": round(self.kg_co2e_avoided, 4),
            "asks": self.asks,
            "first_try_accuracy": accuracy,
            "by_category": rows,
        }


def fill_buckets(loaded: Loaded, start: date, end: date, bucket: str) -> list[Bucket]:
    """Every ticket dropped into its day or week, oldest bucket first.

    Buckets with no tickets are still drawn, because a quiet Tuesday is a fact and
    a chart that skips it lies about the shape of the week.
    """
    step = timedelta(days=7 if bucket == BUCKET_WEEK else 1)
    cursor = bucket_start(start, bucket)
    table: dict[date, Bucket] = {}
    order: list[Bucket] = []
    while cursor <= end:
        made = Bucket(cursor)
        table[cursor] = made
        order.append(made)
        cursor += step

    for event in loaded.events:
        key = bucket_start(_event_date(event), bucket)
        holder = table.get(key)
        if holder is None:
            continue
        record = loaded.records.get(event.id)
        scores = loaded.options.get(event.id, [])
        mass_kg = (record.mass_g if record is not None else (event.mass_g or 0.0)) / 1000.0

        if event.status is models.EventStatus.asking:
            holder.asks += 1
        if event.status is models.EventStatus.void:
            continue

        holder.tosses += 1
        final = loaded.finals.get(event.id)
        if final is not None and final.method is models.IdentifyMethod.human:
            holder.settled_by_person += 1

        cents = 0
        if record is not None:
            if record.item_class is models.ItemClass.inventory:
                cents = record.cost_basis_cents
                holder.wasted_cents += cents
            elif record.item_class is models.ItemClass.fixed_asset:
                cents = record.book_value_cents
                holder.book_loss_cents += cents
            elif record.fmv_mid is not None:
                cents = record.fmv_mid
                holder.estimated_value_cents += cents

        trash = _trash(scores)
        holder.kg_landfill += trash.kg_landfill if trash is not None else mass_kg
        best = _best(scores)
        if trash is not None and best is not None:
            holder.kg_co2e_avoided += carbon.avoided_co2e(trash.kg_co2e, best.kg_co2e) or 0.0

        group = holder.category(category_of(record))
        group["tosses"] += 1
        group["cents"] += cents
        group["kg"] += mass_kg

    return order


def averages(buckets: list[Bucket], start: date, end: date) -> dict[str, float]:
    """Per day across the whole range, however the buckets were cut."""
    days = max((end - start).days + 1, 1)
    tosses = sum(row.tosses for row in buckets)
    cents = sum(row.wasted_cents for row in buckets)
    kg = sum(row.kg_landfill for row in buckets)
    return {
        "days": float(days),
        "tosses_per_day": round(tosses / days, 3),
        "wasted_cents_per_day": round(cents / days, 1),
        "kg_per_day": round(kg / days, 4),
    }


# Suggestions ---------------------------------------------------------------


def _said(name: str) -> str:
    """A stored category name as a person says it. "fixed_asset" is not a word."""
    from app.agent.prose import human_words

    words = human_words(name)
    return words[:1].upper() + words[1:]


def _plural(count: int, one: str, many: str) -> str:
    """Counted nouns read as a person would say them, never "1 tickets"."""
    return f"{count} {one if count == 1 else many}"


def _worth_saying(cents: int, count: int) -> bool:
    """The floor under every sentence. Small money and small counts stay quiet."""
    return cents >= MIN_SUGGESTION_CENTS or count >= MIN_SUGGESTION_COUNT


def _category_totals(buckets: list[Bucket]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for holder in buckets:
        for name, values in holder.by_category.items():
            bucket = out.setdefault(name, {"tosses": 0.0, "cents": 0.0, "kg": 0.0})
            for key, value in values.items():
                bucket[key] += value
    return out


def _resale_rows(loaded: Loaded) -> list[tuple[int, int]]:
    """Untracked tickets whose best option the engine actually allowed was resale.

    Reading the stored rows rather than guessing is what keeps this from telling
    anyone to sell food: the engine blocked that row, so it is never the best one.
    """
    rows: list[tuple[int, int]] = []
    for event in loaded.events:
        record = loaded.records.get(event.id)
        if record is None or record.item_class is not models.ItemClass.untracked:
            continue
        best = _best(loaded.options.get(event.id, []))
        if best is None or best.option is not models.OptionKind.resell:
            continue
        rows.append((event.id, record.fmv_mid or best.cash_cents))
    return rows


def suggestions(
    loaded: Loaded,
    buckets: list[Bucket],
    previous: list[Bucket] | None = None,
) -> list[str]:
    """Plain sentences about the range, largest money first, at most five.

    Each one states a fact and an amount. None of them tells anyone what to do,
    and none is written at all unless the money or the count behind it clears the
    floor in PLAN.md 21a item 48.
    """
    found: list[tuple[int, str]] = []
    totals = _category_totals(buckets)
    wasted = sum(row.wasted_cents for row in buckets)
    tosses = sum(row.tosses for row in buckets)

    ranked = sorted(
        ((name, values) for name, values in totals.items() if values["cents"] > 0),
        key=lambda pair: -pair[1]["cents"],
    )
    if ranked:
        name, values = ranked[0]
        cents = int(values["cents"])
        count = int(values["tosses"])
        base = sum(int(row["cents"]) for _, row in ranked)
        if _worth_saying(cents, count) and base > 0:
            share = cents / base * 100
            found.append(
                (
                    cents,
                    f"{_said(name)} is the biggest group at {money(cents)} dollars "
                    f"across {_plural(count, 'ticket', 'tickets')}, {share:.0f} percent "
                    f"of the {money(base)} dollars in the range.",
                )
            )

    resale = _resale_rows(loaded)
    resale_cents = sum(value for _, value in resale)
    if resale and _worth_saying(resale_cents, len(resale)):
        found.append(
            (
                resale_cents,
                f"{_plural(len(resale), 'item', 'items')} nothing on the books tracked "
                f"went in the bin, and the engine priced selling them at "
                f"{money(resale_cents)} dollars.",
            )
        )

    asks = sum(row.asks for row in buckets)
    if asks:
        waiting = _asking_cents(loaded)
        if _worth_saying(waiting, asks):
            found.append(
                (
                    waiting,
                    f"{_plural(asks, 'ticket is', 'tickets are')} still waiting on a "
                    f"person, holding {money(waiting)} dollars that has not posted.",
                )
            )

    book_loss = sum(row.book_loss_cents for row in buckets)
    disposals = sum(
        1
        for event in loaded.events
        if (record := loaded.records.get(event.id)) is not None
        and record.item_class is models.ItemClass.fixed_asset
        and event.status is not models.EventStatus.void
    )
    if disposals and _worth_saying(book_loss, disposals):
        found.append(
            (
                book_loss,
                f"{_plural(disposals, 'asset', 'assets')} came off the register this "
                f"range at a book loss of {money(book_loss)} dollars.",
            )
        )

    trend = _trend(tosses, wasted, previous)
    if trend is not None:
        found.append(trend)

    found.sort(key=lambda pair: -pair[0])
    return [text for _, text in found[:MAX_SUGGESTIONS]]


def _asking_cents(loaded: Loaded) -> int:
    """What the unanswered tickets would post if somebody answered them."""
    total = 0
    for event in loaded.events:
        if event.status is not models.EventStatus.asking:
            continue
        record = loaded.records.get(event.id)
        if record is None:
            continue
        if record.item_class is models.ItemClass.inventory:
            total += record.cost_basis_cents
        elif record.item_class is models.ItemClass.fixed_asset:
            total += record.book_value_cents
        else:
            total += record.fmv_mid or 0
    return total


def _trend(
    tosses: int, wasted: int, previous: list[Bucket] | None
) -> tuple[int, str] | None:
    """A comparison only when both ranges hold enough tickets to carry one."""
    if previous is None:
        return None
    before_tosses = sum(row.tosses for row in previous)
    if tosses < MIN_TREND_TOSSES or before_tosses < MIN_TREND_TOSSES:
        return None
    before_cents = sum(row.wasted_cents for row in previous)
    gap = wasted - before_cents
    if abs(gap) < MIN_SUGGESTION_CENTS:
        return None
    direction = "up" if gap > 0 else "down"
    return (
        abs(gap),
        f"Write-offs are {direction} {money(abs(gap))} dollars on the range before this "
        f"one, {money(wasted)} dollars against {money(before_cents)} dollars.",
    )
