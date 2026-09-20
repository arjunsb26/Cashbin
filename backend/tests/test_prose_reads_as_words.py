"""Nothing a person reads carries a field name or a figure to four decimal places.

The live case: the close memo said "fixed_asset", "book_loss_cents" and "bonus_100" at a
finance lead, and the Trends paragraph said "Over 14.0 days" and "2.2195 kg". The cause
was the data block, which handed the model raw keys and raw floats and then, quite
correctly, refused to let it write any figure that was not one of them.
"""

from __future__ import annotations

import re
from datetime import date

from app.agent import close_memo, prose, stats_summary
from app.config import Settings
from app.ledger.close import CloseResult
from app.schemas import CloseCheck

# A word with an underscore inside it, which is a field name wearing a disguise.
SNAKE = re.compile(r"[A-Za-z]+_[A-Za-z]")
# A figure with more decimal places than anybody says out loud.
LONG_FLOAT = re.compile(r"\d+\.\d{3,}")

TOTALS = {
    "events": {"counted": 4, "void": 0, "asking": 1},
    "write_offs": {"total_cents": 331, "count": 2, "rows": []},
    "asset_disposals": {"count": 1, "book_loss_cents": 8_600, "tax_loss_cents": 0},
    "missed_opportunity": {"total_cents": 1_267, "by_option": {"donate": 1_267}},
    "sustainability": {"kg_landfill": 2.2195, "kg_co2e_avoided": 0.8331},
}


def a_close() -> CloseResult:
    return CloseResult(
        period_start=date(2026, 9, 1).isoformat(),
        period_end=date(2026, 9, 20).isoformat(),
        status="closed_clean",
        totals=TOTALS,
        checks=[
            CloseCheck(
                id="trial_balance",
                title="Trial balance",
                result="pass",
                numbers={"debits_cents": 12_933, "credits_cents": 12_933},
            )
        ],
        report={},
    )


def reads_as_words(text: str) -> None:
    assert text.strip(), "there is nothing to read"
    found = SNAKE.search(text)
    assert found is None, f"{text[max(0, found.start() - 30):found.end() + 30]!r}"
    long_float = LONG_FLOAT.search(text)
    assert long_float is None, f"{long_float.group(0)!r} is not a figure anybody says"


def test_the_close_memo_says_words_rather_than_field_names() -> None:
    result = a_close()
    memo = close_memo.write(
        Settings(_env_file=None),
        result,
        {"total": {"opening_nbv_cents": 12_900, "closing_nbv_cents": 4_300}},
        {"differences_cents": 8_600, "rows": []},
    )
    reads_as_words(memo)
    reads_as_words(str(close_memo.build_block(result)))


def test_the_trends_paragraph_says_words_rather_than_field_names() -> None:
    findings = [
        "Food is the biggest group at 3.31 dollars across 2 tickets.",
        "1 asset came off the register this range at a book loss of 86.00 dollars.",
        "1 ticket is still waiting on a person, holding 0.00 dollars that has not posted.",
    ]
    averages = {"days": 14.0, "tosses_per_day": 0.286, "kg_per_day": 0.1585}
    block = stats_summary.build_block(findings, TOTALS, averages)
    reads_as_words(str(block))
    paragraph = stats_summary.write(Settings(_env_file=None), findings, TOTALS, averages)
    reads_as_words(paragraph or "")


def test_a_figure_in_the_written_block_is_still_a_figure_the_wall_knows() -> None:
    """The validator matches on the formatted strings, so a memo can still quote them."""
    block = prose.humanise({"asset_disposals": {"book_loss_cents": 8_600}})
    assert block == {"asset disposals": {"book loss": "$86.00"}}
    kept, dropped = prose.grounded("The book loss was $86.00.", block)
    assert kept and not dropped
    kept, dropped = prose.grounded("The book loss was $91.00.", block)
    assert dropped and not kept
