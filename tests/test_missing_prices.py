from __future__ import annotations

import pytest

from cozmo_ai_take_home.engine import ClaimEngine
from cozmo_ai_take_home.models import ItemStatus


@pytest.mark.parametrize("raw_text", ["antique clock", "guitar", "monitor"])
def test_known_item_without_fixture_price_stays_blank(
    engine: ClaimEngine, raw_text: str
) -> None:
    [item] = engine.add(raw_text)

    assert item.status is ItemStatus.CONFIRMED
    assert item.price is None
    assert item.price_source is None

    totals = engine.totals()
    assert totals.total == 0
    assert totals.excluded_unpriced_count == 1
    assert totals.excluded_ambiguous_count == 0
    assert totals.excluded_item_count == 1
