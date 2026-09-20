"""What the bin saw over time. One route, by day or by week.

PLAN.md 21a items 43 and 48. The arithmetic is in `ledger/stats.py` and the
paragraph is in `agent/stats_summary.py`. This handler loads a range, totals it,
and hands back the buckets, the averages, the suggestions and the paragraph.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.agent import stats_summary
from app.config import Settings, get_settings
from app.db import session_scope
from app.ledger import stats
from app.schemas import StatsAverages, StatsBucket, StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])

DEFAULT_DAYS = 14


@router.get("", response_model=StatsResponse)
def get_stats(
    bucket: Literal["day", "week"] = Query(
        default="day", description="Group tickets by day or by week."
    ),
    from_day: str | None = Query(
        default=None, alias="from", max_length=32, description="First day, as YYYY-MM-DD."
    ),
    to_day: str | None = Query(
        default=None, alias="to", max_length=32, description="Last day, as YYYY-MM-DD."
    ),
    settings: Settings = Depends(get_settings),
) -> StatsResponse:
    """The range totalled, with what stands out in it said in plain sentences."""
    today = datetime.now(UTC).date()
    end = stats.parse_day(to_day, today)
    start = stats.parse_day(from_day, end - timedelta(days=DEFAULT_DAYS - 1))
    if start > end:
        start, end = end, start

    span = (end - start).days + 1
    before_end = start - timedelta(days=1)
    before_start = before_end - timedelta(days=span - 1)

    with session_scope() as session:
        loaded = stats.load(session, start, end)
        buckets = stats.fill_buckets(loaded, start, end, bucket)
        earlier = stats.load(session, before_start, before_end)
        earlier_buckets = stats.fill_buckets(earlier, before_start, before_end, bucket)

    averages = stats.averages(buckets, start, end)
    lines = stats.suggestions(loaded, buckets, earlier_buckets)
    totals = _totals(buckets)
    paragraph = stats_summary.write(settings, lines, totals, averages)

    return StatsResponse(
        bucket=bucket,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        buckets=[StatsBucket.model_validate(row.as_dict()) for row in buckets],
        averages=StatsAverages.model_validate(averages),
        suggestions=lines,
        summary_md=paragraph,
    )


def _totals(buckets: list[stats.Bucket]) -> dict[str, int | float]:
    """The range added up, which is what the paragraph is allowed to quote."""
    return {
        "tosses": sum(row.tosses for row in buckets),
        "wasted_cents": sum(row.wasted_cents for row in buckets),
        "book_loss_cents": sum(row.book_loss_cents for row in buckets),
        "estimated_value_cents": sum(row.estimated_value_cents for row in buckets),
        "kg_landfill": round(sum(row.kg_landfill for row in buckets), 4),
        "kg_co2e_avoided": round(sum(row.kg_co2e_avoided for row in buckets), 4),
        "asks": sum(row.asks for row in buckets),
    }


def default_range(today: date | None = None) -> tuple[date, date]:
    """The fortnight the page opens on when nobody asked for a range."""
    end = today or datetime.now(UTC).date()
    return end - timedelta(days=DEFAULT_DAYS - 1), end
