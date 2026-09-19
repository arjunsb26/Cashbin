"""Score every fate an item could have had, then rank them.

This is the module the pipeline calls once an item record exists. It leans on
`tax.py` for the money and `carbon.py` for the climate, adds the replacement a
repair avoids, then ranks what is left.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.engine import carbon, tax
from app.engine.records import (
    AssetInfo,
    EngineSettings,
    ItemRecord,
    Option,
    OptionScore,
)

Tone = str

TONE_GREEN = "green"
TONE_AMBER = "amber"
TONE_RED = "red"


class Ranking(BaseModel):
    """The one line summary the LCD, the phone and the header all read."""

    model_config = ConfigDict(frozen=True)

    best_option: Option | None
    greenest_option: Option | None
    saved_if_followed_cents: int
    tone: Tone


def score_one(
    option: Option,
    record: ItemRecord,
    settings: EngineSettings,
    asset: AssetInfo | None = None,
) -> OptionScore | None:
    """One option, fully priced, or None when the table does not offer it."""
    effect = tax.tax_effect_for(option, record, settings, asset)
    if effect is None:
        return None

    result = carbon.carbon_for(record, option)
    notes = list(effect.notes)

    net = effect.cash_cents + effect.tax_effect_cents
    if option is Option.repair and record.replacement_cents is not None:
        net += record.replacement_cents
        notes.append(
            f"Repairing avoids buying a replacement at {tax.money(record.replacement_cents)}."
        )

    if result.missing_materials:
        names = ", ".join(result.missing_materials)
        notes.append(f"Carbon is unknown because there is no factor for {names}.")
    elif option in {Option.resell, Option.donate, Option.repair}:
        notes.append("Carbon counts the new item this displaces.")

    return OptionScore(
        event_id=record.event_id,
        option=option,
        allowed=effect.allowed,
        blocked_reason=effect.blocked_reason,
        cash_cents=effect.cash_cents,
        tax_effect_cents=effect.tax_effect_cents,
        net_after_tax_cents=net,
        kg_co2e=result.kg_co2e,
        kg_landfill=result.kg_landfill,
        needs_human_review=effect.needs_human_review,
        notes=notes,
        rule_ids=list(effect.rule_ids),
        rank=None,
    )


def _co2e_key(score: OptionScore) -> float:
    """An unknown carbon figure never wins a tie."""
    return float("inf") if score.kg_co2e is None else score.kg_co2e


def _rank(scores: list[OptionScore], settings: EngineSettings) -> None:
    """Rank the allowed options in place. Blocked options keep rank None."""
    allowed = [s for s in scores if s.allowed]
    allowed.sort(key=lambda s: -s.net_after_tax_cents)

    ordered: list[OptionScore] = []
    index = 0
    while index < len(allowed):
        head = allowed[index]
        group = [head]
        index += 1
        while (
            index < len(allowed)
            and head.net_after_tax_cents - allowed[index].net_after_tax_cents
            <= settings.tie_break_cents
        ):
            group.append(allowed[index])
            index += 1
        group.sort(key=_co2e_key)
        ordered.extend(group)

    for position, score in enumerate(ordered, start=1):
        score.rank = position


def score_options(
    record: ItemRecord,
    settings: EngineSettings,
    asset: AssetInfo | None = None,
) -> list[OptionScore]:
    """Every option this item actually has, ranked best first.

    An option the table does not offer is left out entirely. An option that is
    offered but blocked stays in the list so a person can see the reason.
    """
    scores = [
        score
        for option in Option
        if (score := score_one(option, record, settings, asset)) is not None
    ]
    _rank(scores, settings)
    return scores


def by_option(scores: list[OptionScore]) -> dict[Option, OptionScore]:
    return {score.option: score for score in scores}


def _tone_for(
    best: OptionScore | None, trash: OptionScore | None, settings: EngineSettings
) -> Tone:
    """The colour the LCD and the ticket use, per PLAN.md section 21a item 10.

    Red when the bin is blocked outright. Otherwise green only when the bin was
    already a fine answer, which means either the bin is the best option or the
    best option beats it by less than the tie break on money and by less than
    `tone_co2e_kg` on carbon. Anything else is amber, so an option that is worth
    the same money but much less carbon still says a better answer existed.

    An unknown carbon figure never buys a green tone. Unknown is unknown, and
    claiming the bin was fine on a figure nobody has is the one thing this
    product must not do.
    """
    if trash is not None and not trash.allowed:
        return TONE_RED
    if best is None or trash is None:
        return TONE_AMBER
    if best.option is Option.trash:
        return TONE_GREEN

    money_gap = best.net_after_tax_cents - trash.net_after_tax_cents
    if money_gap >= settings.tie_break_cents:
        return TONE_AMBER
    if best.kg_co2e is None or trash.kg_co2e is None:
        return TONE_AMBER
    if abs(best.kg_co2e - trash.kg_co2e) >= settings.tone_co2e_kg:
        return TONE_AMBER
    return TONE_GREEN


def summarise(scores: list[OptionScore], settings: EngineSettings | None = None) -> Ranking:
    """Best, greenest, what following the best would have saved, and the tone."""
    settings = settings or EngineSettings()
    table = by_option(scores)
    trash = table.get(Option.trash)

    ranked = sorted(
        (s for s in scores if s.allowed and s.rank is not None),
        key=lambda s: s.rank or 0,
    )
    best = ranked[0] if ranked else None

    with_carbon = [s for s in scores if s.allowed and s.kg_co2e is not None]
    greenest = min(with_carbon, key=lambda s: s.kg_co2e or 0.0) if with_carbon else None

    saved = 0
    if best is not None and trash is not None:
        saved = best.net_after_tax_cents - trash.net_after_tax_cents

    return Ranking(
        best_option=best.option if best else None,
        greenest_option=greenest.option if greenest else None,
        saved_if_followed_cents=max(saved, 0),
        tone=_tone_for(best, trash, settings),
    )
