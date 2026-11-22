from __future__ import annotations

from decimal import Decimal
from typing import Any

from .catalog import ambiguity_hint, display_name
from .models import Claim, HistoryEventType, Item, ItemStatus


def format_money(value: Decimal) -> str:
    return f"{value:,.2f}"


def format_size(value: Any) -> str:
    if value is None:
        return "blank"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f'{value}"'


def item_label(item: Item) -> str:
    label = display_name(item.normalized_item)
    attributes: list[str] = []
    if "size_inch" in item.attributes:
        attributes.append(format_size(item.attributes["size_inch"]))
    for key, value in item.attributes.items():
        if key == "size_inch":
            continue
        attributes.append(f"{key}={value}")
    if attributes:
        label += " (" + ", ".join(attributes) + ")"
    return label


def _clarification_hint(item: Item) -> str:
    return ambiguity_hint(item.normalized_item)


def _event_notes(item: Item) -> list[str]:
    notes: list[str] = []
    for event in item.history:
        if event.event is HistoryEventType.CORRECTED:
            if event.field == "size_inch":
                notes.append(f"corrected from {format_size(event.old)} to {format_size(event.new)}")
            elif event.field == "qty":
                notes.append(f"corrected qty from {event.old} to {event.new}")
            elif event.field == "normalized_item":
                notes.append(f'corrected item from "{event.old}" to "{event.new}"')
            else:
                notes.append(f"corrected {event.field} from {event.old} to {event.new}")
        elif event.event is HistoryEventType.MERGED:
            if event.note:
                notes.append(event.note)
        elif event.event is HistoryEventType.REPRICED:
            old = "blank" if event.old is None else format_money(Decimal(str(event.old)))
            new = "blank" if event.new is None else format_money(Decimal(str(event.new)))
            notes.append(f"price changed from {old} to {new} after correction")
        elif event.event is HistoryEventType.STATUS_CHANGED:
            if event.old == ItemStatus.NEEDS_CLARIFICATION.value and event.new == ItemStatus.CONFIRMED.value:
                notes.append("clarification resolved")
    return notes


def render_report(claim: Claim) -> str:
    lines = [
        "CONTENTS CLAIM REPORT",
        "---------------------",
        f"Currency: {claim.currency}",
        "",
    ]

    if not claim.items:
        lines.append("No items recorded.")
    else:
        for index, item in enumerate(claim.items, start=1):
            left = f"{index}. {item_label(item)} x{item.qty}"
            if item.status is ItemStatus.NEEDS_CLARIFICATION:
                amount = ""
                tag = f"NEEDS CLARIFICATION ({_clarification_hint(item)})"
            elif item.price is None:
                amount = ""
                tag = "PRICE BLANK (not in fixture)"
            else:
                amount = format_money(item.price * item.qty)
                tag = "[fixture price]"

            lines.append(f"{left:<38} {amount:>12}  {tag}".rstrip())
            for note in _event_notes(item):
                lines.append(f"   Note: {note}")

        lines.append("")
        lines.append(f"Total (priced items only): {format_money(claim.totals.total)}")
        if claim.totals.excluded_item_count == 0:
            lines.append("Excluded from total: 0 items")
        else:
            parts: list[str] = []
            if claim.totals.excluded_ambiguous_count:
                parts.append(f"{claim.totals.excluded_ambiguous_count} ambiguous")
            if claim.totals.excluded_unpriced_count:
                parts.append(f"{claim.totals.excluded_unpriced_count} unpriced")
            lines.append(
                f"Excluded from total: {claim.totals.excluded_item_count} items "
                f"({', '.join(parts)})"
            )

    lines.append("")
    lines.append("Prices come from a test fixture, not real market data.")
    return "\n".join(lines) + "\n"
