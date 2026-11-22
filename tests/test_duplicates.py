from __future__ import annotations

from cozmo_ai_take_home.engine import ClaimEngine
from cozmo_ai_take_home.models import HistoryEventType


def test_synonyms_merge_into_one_record(engine: ClaimEngine) -> None:
    engine.add("tv, television")

    items = engine.items
    assert len(items) == 1
    assert items[0].normalized_item == "television"
    assert items[0].qty == 2
    assert items[0].raw_text == "tv"
    assert items[0].source == "user said"
    assert any(event.event is HistoryEventType.MERGED for event in items[0].history)
    assert engine.totals().total == 900


def test_fuzzy_typo_merges_instead_of_duplicating(engine: ClaimEngine) -> None:
    engine.add("tv, telivision")

    items = engine.items
    assert len(items) == 1
    assert items[0].normalized_item == "television"
    assert items[0].qty == 2
    assert any(event.event is HistoryEventType.MERGED for event in items[0].history)
