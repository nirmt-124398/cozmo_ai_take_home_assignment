from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

SIZE_PATTERN = re.compile(
    r'(?<![\w.])(\d+(?:\.\d+)?)\s*(?:inch(?:es)?|in\b|"|\u201d|\u2033|\'\')',
    re.IGNORECASE,
)
QTY_PREFIX = re.compile(r"^\s*(\d{1,3})\s*(?:x\s*)?(.+?)\s*$", re.IGNORECASE)
QTY_SUFFIX = re.compile(r"^(.*?)\s+x\s*(\d{1,3})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Observation:
    raw_text: str
    item_text: str
    qty: int
    attributes: dict[str, Any]


def parse_observations(text: str) -> list[Observation]:
    segments = [segment.strip() for segment in re.split(r"[,;\n]", text) if segment.strip()]
    if not segments:
        raise ValueError("no items found in input")
    return [parse_segment(segment) for segment in segments]


def parse_segment(raw: str) -> Observation:
    original = raw.strip()
    if not original:
        raise ValueError("empty item segment")

    working = original
    attributes: dict[str, Any] = {}

    size_match = SIZE_PATTERN.search(working)
    if size_match is not None:
        size = Decimal(size_match.group(1))
        attributes["size_inch"] = (
            int(size) if size == size.to_integral_value() else float(size)
        )
        working = (working[: size_match.start()] + " " + working[size_match.end() :]).strip()

    qty = 1
    suffix = QTY_SUFFIX.match(working)
    if suffix is not None:
        qty = int(suffix.group(2))
        working = suffix.group(1).strip()
    else:
        prefix = QTY_PREFIX.match(working)
        if prefix is not None:
            qty = int(prefix.group(1))
            working = prefix.group(2).strip()

    if qty < 1:
        raise ValueError(f"quantity must be at least 1 in '{original}'")

    working = re.sub(r"\s+", " ", working).strip(" -")
    if not working:
        raise ValueError(f"could not find an item name in '{original}'")

    return Observation(
        raw_text=original,
        item_text=working,
        qty=qty,
        attributes=attributes,
    )
