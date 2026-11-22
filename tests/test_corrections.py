from __future__ import annotations

from decimal import Decimal

from cozmo_ai_take_home.engine import ClaimEngine
from cozmo_ai_take_home.models import HistoryEventType


def test_size_correction_updates_value_and_logs_history(engine: ClaimEngine) -> None:
    [item] = engine.add("55 inch tv")
    corrected = engine.correct(item.id, "size_inch", "43")

    assert corrected.attributes["size_inch"] == 43
    assert corrected.raw_text == "55 inch tv"
    assert corrected.source == "corrected by user"

    correction = [
        event
        for event in corrected.history
        if event.event is HistoryEventType.CORRECTED
    ][-1]
    assert correction.field == "size_inch"
    assert correction.old == 55
    assert correction.new == 43
    assert correction.source == "user correction"


def test_qty_correction_changes_total(engine: ClaimEngine) -> None:
    [item] = engine.add("laptop")
    assert engine.totals().total == Decimal("600.00")

    engine.correct(item.id, "qty", "3")

    assert item.qty == 3
    assert item.source == "corrected by user"
    assert engine.totals().total == Decimal("1800.00")
    correction = [
        event
        for event in item.history
        if event.event is HistoryEventType.CORRECTED
    ][-1]
    assert correction.old == 1
    assert correction.new == 3


def test_normalized_item_correction_reprices_from_fixture(engine: ClaimEngine) -> None:
    [item] = engine.add("monitor")
    assert item.price is None
    assert engine.totals().total == 0

    engine.correct(item.id, "normalized_item", "television")

    assert item.normalized_item == "television"
    assert item.price == Decimal("450.00")
    assert item.price_source == "fixture v1 (test fixture, not real market data)"
    assert item.source == "corrected by user"
    assert engine.totals().total == Decimal("450.00")
    assert any(event.event is HistoryEventType.REPRICED for event in item.history)
