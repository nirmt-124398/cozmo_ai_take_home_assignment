from __future__ import annotations

import pytest

from cozmo_ai_take_home.engine import ClaimEngine
from cozmo_ai_take_home.models import ItemStatus


@pytest.mark.parametrize(
    ("raw_text", "expected_term", "hint"),
    [
        ("charger", "charger", "which device?"),
        ("cable", "cable", "which cable?"),
        ("remote", "remote", "which device's remote?"),
    ],
)
def test_ambiguous_items_are_flagged_not_guessed(
    engine: ClaimEngine, raw_text: str, expected_term: str, hint: str
) -> None:
    [item] = engine.add(raw_text)

    assert item.normalized_item == expected_term
    assert item.status is ItemStatus.NEEDS_CLARIFICATION
    assert item.status_reason is not None
    assert hint in item.status_reason
    assert item.price is None
    assert item.price_source is None

    totals = engine.totals()
    assert totals.total == 0
    assert totals.excluded_ambiguous_count == 1
    assert totals.excluded_unpriced_count == 0
    assert totals.excluded_item_count == 1
