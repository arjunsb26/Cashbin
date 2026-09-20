"""The period close: total the books, then check them against the scale.

PLAN.md section 13. Everything here is arithmetic done in Python over rows that
are already in the database. No model is called from this module and no number
in the report comes from anywhere else. The investigator in `app/agent` reads
what this module produced and writes prose about it; it never edits a figure.

The shape of the work is: load the period once, compute the totals as pure
functions over the loaded rows, run the five self-checks, then persist one
`close` row holding the totals, the checks and the whole report the Close page
draws.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.engine import carbon
from app.engine.options import summarise
from app.engine.records import AssetInfo, EngineSettings, Option
from app.engine.records import AssetStatus as EngineAssetStatus
from app.engine.records import ItemClass as EngineItemClass
from app.engine.records import ItemRecord as EngineItemRecord
from app.engine.records import OptionScore as EngineOptionScore
from app.engine.records import TaxMethod as EngineTaxMethod
from app.ledger import queries, register
from app.ledger.journal import untracked_flag
from app.schemas import CloseCheck

SUSTAINABILITY_TITLE = "Scope 3, Category 5 (waste generated in operations) inputs"
EWASTE_FLAGS: frozenset[str] = frozenset({"electronics", "battery"})
LOW_CONFIDENCE_WARN_SHARE = 0.5
TARE_SETTING_KEY = "last_tare"
# The scale cannot see a step smaller than this, so a gap smaller than this cannot be a
# ticket anyone missed. It is the floor under the three sigma band, never a replacement
# for it: the band wins whenever the measured errors are larger.
MIN_MASS_TOLERANCE_SOURCE = "step_min_g"

STATUS_CLEAN = "clean"
STATUS_NEEDS_REVIEW = "needs_review"


# Loading -------------------------------------------------------------------


class PeriodRows(BaseModel):
    """Every row the close needs, loaded once."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    period_start: str
    period_end: str
    events: list[models.Event] = Field(default_factory=list)
    item_records: dict[int, models.ItemRecord] = Field(default_factory=dict)
    option_scores: dict[int, list[models.OptionScore]] = Field(default_factory=dict)
    identifications: dict[int, list[models.Identification]] = Field(default_factory=dict)
    assets: list[models.Asset] = Field(default_factory=list)
    tare: dict[str, Any] | None = None

    @property
    def tosses(self) -> list[models.Event]:
        return [e for e in self.events if e.kind is models.EventKind.toss]

    @property
    def bag_changes(self) -> list[models.Event]:
        return [e for e in self.events if e.kind is models.EventKind.bag_change]

    @property
    def removals(self) -> list[models.Event]:
        return [e for e in self.events if e.kind is models.EventKind.removal]

    @property
    def counted(self) -> list[models.Event]:
        """Tosses that still count. A voided ticket is not part of the books."""
        return [e for e in self.tosses if e.status is not models.EventStatus.void]


def _as_datetime(text: str, *, end: bool) -> datetime:
    """Read a period bound. A bare date means the whole of that day, UTC."""
    raw = (text or "").strip()
    try:
        if len(raw) == 10:
            day = date.fromisoformat(raw)
            clock = datetime.max.time() if end else datetime.min.time()
            return datetime.combine(day, clock, tzinfo=UTC)
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return datetime.max.replace(tzinfo=UTC) if end else datetime.min.replace(tzinfo=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _event_time(row: models.Event) -> datetime:
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _event_date(row: models.Event) -> date:
    return _event_time(row).date()


def load_period(session: Session, period_start: str, period_end: str) -> PeriodRows:
    """Read the whole period in a handful of queries, oldest event first."""
    start = _as_datetime(period_start, end=False)
    end = _as_datetime(period_end, end=True)

    all_events = list(session.scalars(select(models.Event).order_by(models.Event.id)))
    events = [row for row in all_events if start <= _event_time(row) <= end]
    ids = [row.id for row in events]

    item_records: dict[int, models.ItemRecord] = {}
    option_scores: dict[int, list[models.OptionScore]] = {}
    identifications: dict[int, list[models.Identification]] = {}
    if ids:
        for record in session.scalars(
            select(models.ItemRecord).where(models.ItemRecord.event_id.in_(ids))
        ):
            item_records[record.event_id] = record
        for score in session.scalars(
            select(models.OptionScore)
            .where(models.OptionScore.event_id.in_(ids))
            .order_by(models.OptionScore.id)
        ):
            option_scores.setdefault(score.event_id, []).append(score)
        for ident in session.scalars(
            select(models.Identification)
            .where(models.Identification.event_id.in_(ids))
            .order_by(models.Identification.id)
        ):
            identifications.setdefault(ident.event_id, []).append(ident)

    assets = list(session.scalars(select(models.Asset).order_by(models.Asset.id)))
    tare_row = session.get(models.Setting, TARE_SETTING_KEY)
    tare: dict[str, Any] | None = None
    if tare_row is not None:
        loaded = _load_json(tare_row.value_json, {})
        if isinstance(loaded, dict):
            tare = loaded

    return PeriodRows(
        period_start=period_start,
        period_end=period_end,
        events=events,
        item_records=item_records,
        option_scores=option_scores,
        identifications=identifications,
        assets=assets,
        tare=tare,
    )


def _load_json(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _trace(row: models.Event) -> list[list[float]]:
    """The weight trace as `[[t_seconds, grams], ...]`, or nothing readable."""
    loaded = _load_json(row.trace_json, [])
    if not isinstance(loaded, list):
        return []
    points: list[list[float]] = []
    for point in loaded:
        if isinstance(point, list | tuple) and len(point) >= 2:
            try:
                points.append([float(point[0]), float(point[1])])
            except (TypeError, ValueError):
                continue
    return points


# Row conversion ------------------------------------------------------------


def to_engine_record(row: models.ItemRecord, event: models.Event) -> EngineItemRecord:
    """One `item_record` row as the engine's own type, so the pure code can read it."""
    material = _load_json(row.material_mix_json, {})
    flags = _load_json(row.regulatory_flags_json, [])
    return EngineItemRecord.model_validate(
        {
            "event_id": row.event_id,
            "label": row.label,
            "class": EngineItemClass(row.item_class.value),
            "mass_g": row.mass_g,
            "event_date": _event_date(event),
            "material_mix": material if isinstance(material, dict) else {},
            "regulatory_flags": flags if isinstance(flags, list) else [],
            "book_value_cents": row.book_value_cents,
            "tax_basis_cents": row.tax_basis_cents,
            "asset_id": row.asset_id,
            "cost_basis_cents": row.cost_basis_cents,
            "fmv_low": row.fmv_low,
            "fmv_mid": row.fmv_mid,
            "fmv_high": row.fmv_high,
            "fmv_source": row.fmv_source,
            "repair_low": row.repair_low,
            "repair_mid": row.repair_mid,
            "repair_high": row.repair_high,
            "repair_source": row.repair_source,
            "replacement_cents": row.replacement_cents,
            "replacement_source": row.replacement_source,
            "scrap_cents": row.scrap_cents,
            "scrap_source": row.scrap_source,
            "condition": row.condition,
        }
    )


def to_engine_scores(rows: Iterable[models.OptionScore]) -> list[EngineOptionScore]:
    """`option_score` rows as the engine's type, ready for `options.summarise`."""
    out: list[EngineOptionScore] = []
    for row in rows:
        notes = _load_json(row.notes_json, [])
        rule_ids = _load_json(row.rule_ids_json, [])
        out.append(
            EngineOptionScore(
                id=row.id,
                event_id=row.event_id,
                option=Option(row.option.value),
                allowed=row.allowed,
                blocked_reason=row.blocked_reason,
                cash_cents=row.cash_cents,
                tax_effect_cents=row.tax_effect_cents,
                net_after_tax_cents=row.net_after_tax_cents,
                kg_co2e=row.kg_co2e,
                kg_landfill=row.kg_landfill,
                needs_human_review=row.needs_human_review,
                notes=notes if isinstance(notes, list) else [],
                rule_ids=rule_ids if isinstance(rule_ids, list) else [],
                rank=row.rank,
            )
        )
    return out


def to_asset_info(row: models.Asset) -> AssetInfo:
    """A register row as the engine's type. Mirrors `api/assets.to_asset_info`."""
    try:
        in_service = date.fromisoformat(row.in_service_date[:10])
    except ValueError:
        in_service = None
    return AssetInfo(
        id=row.id,
        tag=row.tag,
        description=row.description,
        category=row.category,
        cost_cents=row.cost_cents,
        in_service_date=in_service,
        book_life_months=row.book_life_months,
        salvage_cents=row.salvage_cents,
        tax_method=EngineTaxMethod(row.tax_method.value),
        tax_basis_cents_override=row.tax_basis_cents_override,
        status=EngineAssetStatus(row.status.value),
        disposed_event_id=row.disposed_event_id,
        insured=row.insured,
        location=row.location,
    )


# Totals --------------------------------------------------------------------


def waste_by_item(rows: PeriodRows) -> dict[str, Any]:
    """Write-offs grouped by label: how many, how heavy, how much money."""
    grouped: dict[str, dict[str, Any]] = {}
    for event in rows.counted:
        record = rows.item_records.get(event.id)
        if record is None:
            continue
        bucket = grouped.setdefault(
            record.label,
            {"label": record.label, "class": record.item_class.value, "count": 0,
             "mass_g": 0.0, "cents": 0},
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["mass_g"] = round(float(bucket["mass_g"]) + record.mass_g, 3)
        bucket["cents"] = int(bucket["cents"]) + _write_off_cents(record)

    items = sorted(grouped.values(), key=lambda row: (-int(row["cents"]), str(row["label"])))
    return {
        "rows": items,
        "total_cents": sum(int(row["cents"]) for row in items),
        "total_mass_g": round(sum(float(row["mass_g"]) for row in items), 3),
        "count": sum(int(row["count"]) for row in items),
    }


def _write_off_cents(record: models.ItemRecord) -> int:
    """What left the books when this went in the bin."""
    if record.item_class is models.ItemClass.inventory:
        return record.cost_basis_cents
    if record.item_class is models.ItemClass.fixed_asset:
        return record.book_value_cents
    return 0


def asset_disposals(rows: PeriodRows, entries: Sequence[Any]) -> dict[str, Any]:
    """Every asset the bin took off the register, on both bases.

    The Form 4797 Part II line 10 subtotal is the ordinary loss side of
    abandonments: an asset thrown away with no proceeds. It is carried as a
    negative number of cents, which is how a loss reads on that line.
    """
    by_event: dict[int, dict[str, Any]] = {}
    for entry in entries:
        event_id = getattr(entry, "event_id", None)
        if event_id is None:
            continue
        evidence = getattr(entry, "evidence", {}) or {}
        basis = getattr(entry, "basis", None)
        basis_value = getattr(basis, "value", basis)
        bucket = by_event.setdefault(event_id, {})
        if basis_value == models.JournalBasis.tax_memo.value:
            bucket["tax_loss_cents"] = int(evidence.get("tax_loss_cents") or 0)
            bucket["tax_gain_cents"] = int(evidence.get("tax_gain_cents") or 0)
            bucket["tax_basis_cents"] = int(evidence.get("tax_basis_cents") or 0)
            bucket["rule_ids"] = list(evidence.get("rule_ids") or [])
        else:
            if "gain_cents" in evidence:
                bucket["proceeds_cents"] = int(evidence.get("proceeds_cents") or 0)
                bucket["book_gain_cents"] = int(evidence.get("gain_cents") or 0)

    disposals: list[dict[str, Any]] = []
    for event in rows.counted:
        record = rows.item_records.get(event.id)
        if record is None or record.item_class is not models.ItemClass.fixed_asset:
            continue
        found = by_event.get(event.id, {})
        proceeds = int(found.get("proceeds_cents", 0))
        book_loss = max(record.book_value_cents - proceeds, 0)
        tax_loss = int(found.get("tax_loss_cents", 0))
        tax_gain = int(found.get("tax_gain_cents", 0))
        asset = next((a for a in rows.assets if a.id == record.asset_id), None)
        disposals.append(
            {
                "event_id": event.id,
                "label": record.label,
                "asset_id": record.asset_id,
                "tag": asset.tag if asset else None,
                "description": asset.description if asset else record.label,
                "book_value_cents": record.book_value_cents,
                "proceeds_cents": proceeds,
                "book_loss_cents": book_loss,
                "tax_basis_cents": int(found.get("tax_basis_cents", record.tax_basis_cents)),
                "tax_loss_cents": tax_loss,
                "tax_gain_cents": tax_gain,
                "abandonment": proceeds == 0,
                "book_minus_tax_cents": record.book_value_cents - record.tax_basis_cents,
                "rule_ids": list(found.get("rule_ids", [])),
            }
        )

    abandon_loss = sum(
        row["tax_loss_cents"] for row in disposals if row["abandonment"]
    )
    abandon_gain = sum(
        row["tax_gain_cents"] for row in disposals if row["abandonment"]
    )
    return {
        "rows": disposals,
        "count": len(disposals),
        "book_loss_cents": sum(int(row["book_loss_cents"]) for row in disposals),
        "tax_loss_cents": sum(int(row["tax_loss_cents"]) for row in disposals),
        "tax_gain_cents": sum(int(row["tax_gain_cents"]) for row in disposals),
        "form_4797_part_ii_line_10_cents": abandon_gain - abandon_loss,
        "form_4797_line_label": "Form 4797, Part II, line 10 (abandonments)",
    }


_MISSED_KEYS: dict[Option, str] = {
    Option.donate: "would_have_donated_cents",
    Option.resell: "would_have_resold_cents",
    Option.repair: "would_have_repaired_cents",
    Option.recycle: "would_have_recycled_cents",
    Option.trash: "already_the_best_cents",
}


def missed_opportunity(rows: PeriodRows, settings: EngineSettings) -> dict[str, Any]:
    """What following the best option would have been worth, split by that option."""
    by_option: dict[str, int] = dict.fromkeys(_MISSED_KEYS.values(), 0)
    detail: list[dict[str, Any]] = []
    total = 0
    for event in rows.counted:
        scores = to_engine_scores(rows.option_scores.get(event.id, []))
        if not scores:
            continue
        ranking = summarise(scores, settings)
        saved = ranking.saved_if_followed_cents
        total += saved
        if ranking.best_option is not None:
            by_option[_MISSED_KEYS[ranking.best_option]] += saved
        record = rows.item_records.get(event.id)
        detail.append(
            {
                "event_id": event.id,
                "label": record.label if record else None,
                "best_option": ranking.best_option.value if ranking.best_option else None,
                "greenest_option": (
                    ranking.greenest_option.value if ranking.greenest_option else None
                ),
                "saved_if_followed_cents": saved,
                "tone": ranking.tone,
            }
        )
    detail.sort(key=lambda row: -int(row["saved_if_followed_cents"]))
    return {"total_cents": total, "by_option": by_option, "rows": detail}


def sustainability(rows: PeriodRows, settings: EngineSettings) -> dict[str, Any]:
    """The climate block. Actual means what the bin did, which is landfill."""
    kg_landfill = 0.0
    kg_diverted = 0.0
    kg_co2e_actual = 0.0
    kg_co2e_best = 0.0
    kg_co2e_avoided = 0.0
    kg_ewaste = 0.0
    unknown_carbon = 0
    cheapest_is_greenest = 0
    scored = 0

    for event in rows.counted:
        record = rows.item_records.get(event.id)
        scores = to_engine_scores(rows.option_scores.get(event.id, []))
        mass_kg = (record.mass_g if record else (event.mass_g or 0.0)) / 1000.0
        if record is not None:
            flags = _load_json(record.regulatory_flags_json, [])
            if isinstance(flags, list) and EWASTE_FLAGS.intersection(flags):
                kg_ewaste += mass_kg
        if not scores:
            kg_landfill += mass_kg
            unknown_carbon += 1
            continue

        table = {score.option: score for score in scores}
        trash = table.get(Option.trash)
        ranking = summarise(scores, settings)
        scored += 1

        kg_landfill += trash.kg_landfill if trash is not None else mass_kg
        best = table.get(ranking.best_option) if ranking.best_option else None
        if best is not None and best.option is not Option.trash:
            kg_diverted += mass_kg

        if trash is not None and trash.kg_co2e is not None:
            kg_co2e_actual += trash.kg_co2e
        else:
            unknown_carbon += 1
        if best is not None and best.kg_co2e is not None:
            kg_co2e_best += best.kg_co2e
        if trash is not None and best is not None:
            # Added per event and never below zero, so the total reads as emissions this
            # period could have avoided rather than as a difference of two signed figures.
            avoided = carbon.avoided_co2e(trash.kg_co2e, best.kg_co2e)
            kg_co2e_avoided += avoided or 0.0

        if (
            ranking.best_option is not None
            and ranking.greenest_option is not None
            and ranking.best_option is ranking.greenest_option
        ):
            cheapest_is_greenest += 1

    share = (cheapest_is_greenest / scored * 100.0) if scored else 0.0
    return {
        "title": SUSTAINABILITY_TITLE,
        "kg_to_landfill": round(kg_landfill, 4),
        "kg_diverted_if_followed": round(kg_diverted, 4),
        "kg_co2e_actual": round(kg_co2e_actual, 4),
        "kg_co2e_best": round(kg_co2e_best, 4),
        "kg_co2e_avoided": round(kg_co2e_avoided, 4),
        "cheapest_equals_greenest_pct": round(share, 1),
        "kg_ewaste": round(kg_ewaste, 4),
        "events_scored": scored,
        "events_without_carbon": unknown_carbon,
        "source": "EPA WARM",
    }


def ghost_assets(rows: PeriodRows, settings: EngineSettings) -> dict[str, Any]:
    """Assets the bin disposed of that the register still shows as in use."""
    disposed_ids = [
        record.asset_id
        for event in rows.counted
        if (record := rows.item_records.get(event.id)) is not None
        and record.asset_id is not None
    ]
    infos = [to_asset_info(row) for row in rows.assets]
    ghosts = register.find_ghosts(infos, disposed_ids)
    by_asset = {
        record.asset_id: event.id
        for event in rows.counted
        if (record := rows.item_records.get(event.id)) is not None
        and record.asset_id is not None
    }

    flags: list[dict[str, Any]] = []
    for event in rows.counted:
        record = rows.item_records.get(event.id)
        if record is None:
            continue
        flag = untracked_flag(to_engine_record(record, event), settings)
        if flag is not None:
            flags.append(flag.model_dump())

    suspected = [
        {
            "id": row.id,
            "tag": row.tag,
            "description": row.description,
            "location": row.location,
            "status": row.status.value,
        }
        for row in rows.assets
        if row.status is models.AssetStatus.ghost_suspected
    ]

    return {
        "rows": [
            {
                "id": asset.id,
                "tag": asset.tag,
                "description": asset.description,
                "location": asset.location,
                "event_id": by_asset.get(asset.id),
            }
            for asset in ghosts
        ],
        "count": len(ghosts),
        "ghost_suspected": suspected,
        "possible_unrecorded_assets": flags,
    }


# Checks --------------------------------------------------------------------


def _grams(value: float) -> str:
    """Grams the way the statement prints them: thousands separated, no decimals."""
    return f"{value:,.0f} g"


def _plural(count: int, one: str, many: str) -> str:
    """Counted nouns read as a person would say them, never "1 tickets"."""
    return f"{count} {one if count == 1 else many}"


def _balance_line(label: str, value: str, tail: str = "") -> str:
    line = f"{label:<22}{value:>12}"
    return f"{line}    {tail}" if tail else line


def mass_tolerance(errors: Sequence[float], floor_g: float) -> float:
    """Three sigma on the combined measurement error, never below the scale's own step."""
    combined = math.sqrt(sum(err * err for err in errors))
    return max(3.0 * combined, floor_g)


def check_mass_conservation(rows: PeriodRows, floor_g: float) -> CloseCheck:
    """The physical invariant: what the scale lost has to equal what the tickets say.

    The scale reading is the last weight sample in the period, less the weight at the
    last tare, plus every gram a bag change or a removal took back out of the bin.
    """
    tosses = rows.counted
    samples: list[tuple[float, float]] = []
    for event in rows.events:
        for t_s, grams in _trace(event):
            samples.append((t_s, grams))
    samples.sort(key=lambda point: point[0])

    tare_source = "the last tare recorded by the bin"
    tare_g = 0.0
    if rows.tare and isinstance(rows.tare.get("weight_g"), int | float):
        tare_g = float(rows.tare["weight_g"])
    elif samples:
        tare_g = samples[0][1]
        tare_source = "the first weight sample of the period, because no tare was recorded"
    else:
        tare_source = "nothing, because the bin recorded no weight at all"

    scale_now_g = samples[-1][1] if samples else tare_g
    removed_g = sum(-(event.mass_g or 0.0) for event in rows.bag_changes + rows.removals)
    scale_reads_g = scale_now_g - tare_g + removed_g
    tickets_g = sum(event.mass_g or 0.0 for event in tosses)
    difference_g = scale_reads_g - tickets_g
    tolerance_g = mass_tolerance([event.mass_err_g or 0.0 for event in tosses], floor_g)
    within = abs(difference_g) <= tolerance_g

    detail = "\n".join(
        [
            _balance_line("Scale reads", _grams(scale_reads_g)),
            _balance_line("Tickets sum to", _grams(tickets_g)),
            _balance_line(
                "Difference",
                _grams(abs(difference_g)),
                f"within +/- {_grams(tolerance_g)}    {'Pass' if within else 'Fail'}",
            ),
            "",
            f"The tare is {tare_source}.",
            f"{_plural(len(tosses), 'ticket', 'tickets')}, "
            f"{_plural(len(rows.bag_changes), 'bag change', 'bag changes')}, "
            f"{_plural(len(rows.removals), 'removal', 'removals')}, "
            f"{_grams(removed_g)} taken back out.",
        ]
    )
    if not within:
        missing = "more than the tickets" if difference_g > 0 else "less than the tickets"
        detail += (
            f"\nThe scale lost {missing}, a gap of {_grams(abs(difference_g))}. "
            "Either a toss was never ticketed or one was counted twice."
        )

    return CloseCheck(
        id="mass_conservation",
        title="Mass conservation",
        result="pass" if within else "fail",
        detail=detail,
        numbers={
            "scale_now_g": round(scale_now_g, 3),
            "tare_g": round(tare_g, 3),
            "removed_g": round(removed_g, 3),
            "scale_reads_g": round(scale_reads_g, 3),
            "tickets_g": round(tickets_g, 3),
            "difference_g": round(difference_g, 3),
            "tolerance_g": round(tolerance_g, 3),
            "tickets": float(len(tosses)),
        },
    )


def check_ledger_balance(session: Session, entries: Sequence[Any]) -> CloseCheck:
    """Every entry balances on its own, and the trial balance agrees column to column."""
    unbalanced: list[int] = []
    for entry in entries:
        lines = getattr(entry, "lines", [])
        debits = sum(line.debit_cents for line in lines)
        credit_sum = sum(line.credit_cents for line in lines)
        if debits != credit_sum:
            unbalanced.append(entry.id)

    rows = queries.trial_balance(session, models.JournalBasis.book)
    debit_total = sum(row.debit_cents for row in rows)
    credit_total = sum(row.credit_cents for row in rows)
    balanced = not unbalanced and debit_total == credit_total

    if balanced:
        detail = (
            f"{_plural(len(entries), 'entry', 'entries')}, every one balanced. "
            f"The trial balance shows {debit_total} cents on each side."
        )
    elif unbalanced:
        listed = ", ".join(str(entry_id) for entry_id in unbalanced[:10])
        detail = f"{len(unbalanced)} entries do not balance on their own: {listed}."
    else:
        detail = (
            f"The trial balance does not agree: {debit_total} cents of debits against "
            f"{credit_total} cents of credits."
        )

    return CloseCheck(
        id="ledger_balance",
        title="Ledger balance",
        result="pass" if balanced else "fail",
        detail=detail,
        numbers={
            "entries": float(len(entries)),
            "unbalanced_entries": float(len(unbalanced)),
            "debit_cents": float(debit_total),
            "credit_cents": float(credit_total),
            "difference_cents": float(debit_total - credit_total),
        },
    )


def check_register_consistency(rows: PeriodRows, entries: Sequence[Any]) -> CloseCheck:
    """Every disposed asset needs exactly one disposal entry, no more and no fewer."""
    disposal_counts: dict[int, int] = {}
    for entry in entries:
        evidence = getattr(entry, "evidence", {}) or {}
        basis = getattr(entry, "basis", None)
        if getattr(basis, "value", basis) != models.JournalBasis.book.value:
            continue
        asset_id = evidence.get("asset_id")
        if isinstance(asset_id, int) and "gain_cents" in evidence:
            disposal_counts[asset_id] = disposal_counts.get(asset_id, 0) + 1

    missing: list[str] = []
    duplicated: list[str] = []
    disposed = [row for row in rows.assets if row.status is models.AssetStatus.disposed]
    for asset in disposed:
        count = disposal_counts.get(asset.id, 0)
        if count == 0:
            missing.append(asset.tag)
        elif count > 1:
            duplicated.append(asset.tag)

    ok = not missing and not duplicated
    if ok:
        detail = (
            f"{_plural(len(disposed), 'disposed asset', 'disposed assets')}, "
            "each with one disposal entry."
            if disposed
            else "No assets were disposed in this period."
        )
    else:
        parts: list[str] = []
        if missing:
            parts.append(f"no disposal entry for {', '.join(missing)}")
        if duplicated:
            parts.append(f"more than one disposal entry for {', '.join(duplicated)}")
        detail = "The register and the ledger disagree: " + "; ".join(parts) + "."

    return CloseCheck(
        id="register_consistency",
        title="Register consistency",
        result="pass" if ok else "fail",
        detail=detail,
        numbers={
            "disposed_assets": float(len(disposed)),
            "missing_entries": float(len(missing)),
            "duplicate_entries": float(len(duplicated)),
        },
    )


def check_unresolved_asks(rows: PeriodRows) -> CloseCheck:
    """Tickets still waiting on a person. Any at all is worth a warning."""
    asking = [e for e in rows.tosses if e.status is models.EventStatus.asking]
    if asking:
        listed = ", ".join(str(event.id) for event in asking[:10])
        detail = (
            f"{_plural(len(asking), 'ticket is', 'tickets are')} still waiting on an "
            f"answer: {listed}."
        )
    else:
        detail = "Nothing is waiting on a person."
    return CloseCheck(
        id="unresolved_asks",
        title="Unresolved asks",
        result="warn" if asking else "pass",
        detail=detail,
        numbers={"asking": float(len(asking)), "tosses": float(len(rows.tosses))},
    )


def check_low_confidence_share(rows: PeriodRows) -> CloseCheck:
    """How much of the period a person had to settle. Above half is worth a warning."""
    counted = rows.counted
    by_person = 0
    for event in counted:
        finals = [
            ident
            for ident in rows.identifications.get(event.id, [])
            if ident.is_final
        ]
        if any(ident.method is models.IdentifyMethod.human for ident in finals):
            by_person += 1
    share = by_person / len(counted) if counted else 0.0
    high = share > LOW_CONFIDENCE_WARN_SHARE

    if not counted:
        detail = "No tickets in this period."
    elif high:
        detail = (
            f"A person settled {by_person} of {len(counted)} tickets, "
            f"{share * 100:.0f} percent. The model is carrying less than half the work."
        )
    else:
        detail = (
            f"A person settled {by_person} of {len(counted)} tickets, "
            f"{share * 100:.0f} percent."
        )

    return CloseCheck(
        id="low_confidence_share",
        title="Settled by a person",
        result="warn" if high else "pass",
        detail=detail,
        numbers={
            "settled_by_person": float(by_person),
            "tickets": float(len(counted)),
            "share": round(share, 4),
            "warn_above": LOW_CONFIDENCE_WARN_SHARE,
        },
    )


# Ranking the inputs --------------------------------------------------------


def rank_by_error_contribution(rows: PeriodRows) -> list[dict[str, Any]]:
    """Tickets ordered by how much of the measurement variance each one owns.

    The investigator is handed this as data. It is computed here so no model has
    to do arithmetic to decide which ticket to look at first.
    """
    tosses = rows.counted
    total_variance = sum((event.mass_err_g or 0.0) ** 2 for event in tosses)
    ranked: list[dict[str, Any]] = []
    for event in tosses:
        err = event.mass_err_g or 0.0
        variance = err * err
        record = rows.item_records.get(event.id)
        ranked.append(
            {
                "event_id": event.id,
                "label": record.label if record else None,
                "mass_g": round(event.mass_g or 0.0, 3),
                "mass_err_g": round(err, 3),
                "variance_g2": round(variance, 4),
                "variance_share": round(variance / total_variance, 4) if total_variance else 0.0,
                "status": event.status.value,
                "has_trace": bool(_trace(event)),
                "has_item_record": record is not None,
            }
        )
    ranked.sort(key=lambda row: (-float(row["variance_g2"]), int(row["event_id"])))
    return ranked


# The close -----------------------------------------------------------------


class CloseResult(BaseModel):
    """Everything one close produced, before it becomes a `CloseRead`."""

    id: int | None = None
    period_start: str
    period_end: str
    created_at: str = ""
    status: str = STATUS_CLEAN
    totals: dict[str, Any] = Field(default_factory=dict)
    checks: list[CloseCheck] = Field(default_factory=list)
    investigation_md: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)

    @property
    def needs_investigation(self) -> bool:
        return any(check.result in {"warn", "fail"} for check in self.checks)


def compute_close(
    session: Session,
    period_start: str,
    period_end: str,
    settings: Any,
) -> tuple[CloseResult, PeriodRows]:
    """Totals and checks for the period. Nothing is written and no model is called."""
    rows = load_period(session, period_start, period_end)
    engine_settings = EngineSettings.from_settings(settings)
    entries = queries.list_entries(session)

    totals: dict[str, Any] = {
        "period": {"start": period_start, "end": period_end},
        "events": {
            "tosses": len(rows.tosses),
            "counted": len(rows.counted),
            "bag_changes": len(rows.bag_changes),
            "removals": len(rows.removals),
            "asking": len([e for e in rows.tosses if e.status is models.EventStatus.asking]),
            "void": len([e for e in rows.tosses if e.status is models.EventStatus.void]),
        },
        "write_offs": waste_by_item(rows),
        "asset_disposals": asset_disposals(rows, entries),
        "missed_opportunity": missed_opportunity(rows, engine_settings),
        "sustainability": sustainability(rows, engine_settings),
        "ghost_assets": ghost_assets(rows, engine_settings),
    }

    floor_g = float(getattr(settings, "step_min_g", 3.0))
    checks = [
        check_mass_conservation(rows, floor_g),
        check_ledger_balance(session, entries),
        check_register_consistency(rows, entries),
        check_unresolved_asks(rows),
        check_low_confidence_share(rows),
    ]

    status = (
        STATUS_NEEDS_REVIEW
        if any(check.result in {"warn", "fail"} for check in checks)
        else STATUS_CLEAN
    )
    result = CloseResult(
        period_start=period_start,
        period_end=period_end,
        status=status,
        totals=totals,
        checks=checks,
    )
    return result, rows


def persist_close(session: Session, result: CloseResult) -> models.Close:
    """Write one `close` row holding the totals, the checks and the whole report."""
    report = dict(result.report)
    report.setdefault("period", {"start": result.period_start, "end": result.period_end})
    report["totals"] = result.totals
    report["checks"] = [check.model_dump() for check in result.checks]
    report["status"] = result.status
    report["investigation_md"] = result.investigation_md

    row = models.Close(
        period_start=result.period_start,
        period_end=result.period_end,
        status=result.status,
        totals_json=json.dumps(result.totals),
        checks_json=json.dumps([check.model_dump() for check in result.checks]),
        investigation_md=result.investigation_md,
        report_json=json.dumps(report),
    )
    session.add(row)
    session.flush()
    result.id = row.id
    result.created_at = row.created_at
    result.report = report
    return row


Investigator = Callable[[PeriodRows, "CloseResult"], None]


def run_close(
    session: Session,
    period_start: str,
    period_end: str,
    settings: Any,
    investigator: Investigator | None = None,
) -> CloseResult:
    """The whole close: total the books, check them, narrate a failure, save the row.

    The investigator is passed in rather than imported, so this module never
    reaches a model and the pure path stays testable on its own. It runs only
    when a check warns or fails, and it may write only `investigation_md` and
    `report["investigation"]`. Every number was already fixed before it ran.
    """
    result, rows = compute_close(session, period_start, period_end, settings)
    if investigator is not None and result.needs_investigation:
        investigator(rows, result)
    persist_close(session, result)
    return result
