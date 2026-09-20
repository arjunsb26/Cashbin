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
