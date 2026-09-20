"""The wall around anything a model writes for a person to read.

CLAUDE.md: a model may describe numbers this code computed and may not produce
one of its own. So every sentence a model hands back is checked against the data
block it was given, and a sentence carrying a figure that is not in the block is
dropped rather than corrected. A dropped sentence is cheap. A number nobody can
trace is the one thing a finance product must not print.

The same pass strips advice. The user's words are "the suggestions need to be
reasonable, it shouldnt recommend stupid shit". A model told to summarise will
reach for "consider" and "optimize" unless it is stopped, and a sentence that
tells a CFO what to think is worth less than a sentence that tells them what
happened.
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any

# Words that turn a fact into advice. A sentence carrying one is dropped.
ADVICE_WORDS: frozenset[str] = frozenset(
    {
        "consider",
        "leverage",
        "optimize",
        "optimise",
        "should",
        "recommend",
        "recommended",
        "suggest",
        "suggests",
        "suggested",
        "seamless",
        "robust",
        "delve",
        "must",
        "ought",
    }
)

_HTML = re.compile(r"<[^>\n]{0,200}>")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z]+")


def numbers_in(value: Any) -> set[str]:
    """Every figure inside a value, as the plain digits a person would read.

    A block is walked whole, so `1234`, `12.34` and `"12.34 dollars"` all land as
    strings with no separators, and a sentence quoting any of them passes.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, int | float):
            found.update(_forms(node))
        elif isinstance(node, str):
            for match in _NUMBER.findall(node):
                found.add(_plain(match))
        elif isinstance(node, dict):
            for key, item in node.items():
                walk(key)
                walk(item)
        elif isinstance(node, list | tuple):
            for item in node:
                walk(item)

    walk(value)
    return found


def _plain(text: str) -> str:
    """One figure with its separators and its trailing zeros taken off."""
    cleaned = text.replace(",", "").lstrip("-")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def _forms(number: float) -> set[str]:
    """The ways one computed figure can legitimately appear in a sentence.

    Cents are written as dollars on the page, so a block holding 3185 cents makes
    both `3185` and `31.85` quotable, and a rounded `32` as well.
    """
    out: set[str] = set()
    if isinstance(number, int) or float(number).is_integer():
        whole = int(number)
        out.add(_plain(str(abs(whole))))
        out.add(_plain(f"{abs(whole) / 100:.2f}"))
        out.add(_plain(f"{round(abs(whole) / 100)}"))
    else:
        out.add(_plain(f"{abs(number):.4f}"))
        out.add(_plain(f"{abs(number):.3f}"))
        out.add(_plain(f"{abs(number):.2f}"))
        out.add(_plain(f"{abs(number):.1f}"))
        out.add(_plain(f"{round(abs(number))}"))
    return out


# Turning a data block into something a person can be shown ------------------
#
# A model handed {"book_loss_cents": 8600} writes "book_loss_cents of 8600", because that
# is what it was given and the figure rule stops it inventing anything better. So the
# block is written the way the memo should read before the model ever sees it: labels in
# words, money as money, weights to one decimal place, and nothing carrying an underscore.

_SNAKE = re.compile(r"[_\s]+")
_CENTS = "_cents"
_KG = "kg"


# The handful of stored values whose plain reading is not their name with the underscores
# taken out. A CFO does not say "bonus 100".
SAID_AS: dict[str, str] = {
    "bonus_100": "bonus depreciation",
    "straight_line": "straight line depreciation",
    "ghost_suspected": "possibly missing",
    "possible_unrecorded_asset": "equipment that was never on the register",
    "estimate_above_threshold": "an estimate over the threshold",
    "tax_memo": "the tax memo",
    "fixed_asset": "fixed asset",
}


def human_words(text: str) -> str:
    """A field name or an enum value as words. "fixed_asset" becomes "fixed asset"."""
    return _SNAKE.sub(" ", str(text)).strip()


def human_money(cents: float) -> str:
    """Whole cents as the figure a person reads, with its sign in front of the dollar."""
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(round(cents)) / 100:,.2f}"


def human_key(key: str) -> str:
    """The label this field goes under. The unit moves into the value."""
    name = str(key)
    if name.endswith(_CENTS):
        name = name[: -len(_CENTS)]
    return human_words(name) or human_words(key)


def human_value(key: str, value: Any) -> Any:
    """One value, written the way the memo should say it."""
    name = str(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and name.endswith(_CENTS):
        return human_money(float(value))
    if isinstance(value, int | float) and _KG in name.lower():
        return f"{float(value):.1f} kg"
    if isinstance(value, int | float) and name.lower().endswith("days"):
        return f"{human_words(str(round(float(value))))} days"
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, str):
        if value in SAID_AS:
            return SAID_AS[value]
        return human_words(value) if "_" in value else value
    return value


def humanise_block(node: dict[str, Any]) -> dict[str, Any]:
    """A whole data block, ready to hand to a model. Same rules, narrower type."""
    written = humanise(node)
    return written if isinstance(written, dict) else {}


def humanise(node: Any, key: str = "") -> Any:
    """A whole data block, written for a reader rather than for a database.

    Keys become labels, cents become dollars, weights lose their long tail, and every
    string that was a field name or an enum value reads as words.
    """
    if isinstance(node, dict):
        return {human_key(k): humanise(v, str(k)) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [humanise(item, key) for item in node]
    return human_value(key, node)


def sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping the punctuation on each one."""
    cleaned = _HTML.sub("", text or "").strip()
    if not cleaned:
        return []
    return [part.strip() for part in _SENTENCE.split(cleaned) if part.strip()]


def grounded(
    text: str,
    block: Any,
    *,
    ban_advice: bool = False,
) -> tuple[str, list[str]]:
    """Keep the sentences whose figures are all in the block. Return them and the rest.

    `block` is whatever was handed to the model: a dict, a list or the JSON string
    of one. The second return value is the sentences that were dropped, which the
    caller logs so a bad run is visible rather than silent.
    """
    if isinstance(block, str):
        with contextlib.suppress(json.JSONDecodeError):
            block = json.loads(block)
    known = numbers_in(block)

    kept: list[str] = []
    dropped: list[str] = []
    for sentence in sentences(text):
        figures = {_plain(match) for match in _NUMBER.findall(sentence)}
        if not figures.issubset(known):
            dropped.append(sentence)
            continue
        if ban_advice and ADVICE_WORDS.intersection(_WORD.findall(sentence.lower())):
            dropped.append(sentence)
            continue
        kept.append(sentence)
    return " ".join(kept), dropped


def word_count(text: str) -> int:
    return len([word for word in (text or "").split() if word.strip()])
