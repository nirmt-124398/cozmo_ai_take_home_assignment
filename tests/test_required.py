from __future__ import annotations

from decimal import Decimal

import pytest

from cozmo_ai_take_home import ClaimEngine, ItemStatus


@pytest.fixture
def engine() -> ClaimEngine:
    return ClaimEngine()


@pytest.fixture
def two_items() -> ClaimEngine:
    engine = ClaimEngine()
    engine.add("tv, television")
    return engine


@pytest.fixture
def sample_items() -> ClaimEngine:
    engine = ClaimEngine()
    engine.add("55 inch tv, laptop, charger, cable, television, antique clock, guitar, kettle, smartphone, sofa")
    engine.correct("item_001", "size_inch", "43")
    return engine


# 3 aMbiguous items
def test_ambiguous_charger(engine: ClaimEngine) -> None:
    [item] = engine.add("charger")
    assert item.status is ItemStatus.NEEDS_CLARIFICATION
    assert item.price is None
    assert "which device" in (item.status_reason or "")


def test_ambiguous_cable(engine: ClaimEngine) -> None:
    [item] = engine.add("cable")
    assert item.status is ItemStatus.NEEDS_CLARIFICATION
    assert item.price is None
    assert "which cable" in (item.status_reason or "")


def test_ambiguous_remote(engine: ClaimEngine) -> None:
    [item] = engine.add("remote")
    assert item.status is ItemStatus.NEEDS_CLARIFICATION
    assert item.price is None
    assert "which device" in (item.status_reason or "")


# 3 missing pRices
def test_antique_clock_unpriced(engine: ClaimEngine) -> None:
    [item] = engine.add("antique clock")
    assert item.status is ItemStatus.CONFIRMED
    assert item.price is None
    assert item.price_source is None


def test_guitar_unpriced(engine: ClaimEngine) -> None:
    [item] = engine.add("guitar")
    assert item.status is ItemStatus.CONFIRMED
    assert item.price is None
    assert item.price_source is None


def test_monitor_unpriced(engine: ClaimEngine) -> None:
    [item] = engine.add("monitor")
    assert item.status is ItemStatus.CONFIRMED
    assert item.price is None
    assert item.price_source is None


#  corrections
def test_correction_size(engine: ClaimEngine) -> None:
    [item] = engine.add("55 inch tv")
    corrected = engine.correct(item.id, "size_inch", "43")
    assert corrected.attributes["size_inch"] == 43
    correction = [e for e in corrected.history if e.event.name == "CORRECTED"][0]
    assert correction.field == "size_inch"
    assert correction.old == 55
    assert correction.new == 43


def test_correction_qty(engine: ClaimEngine) -> None:
    [item] = engine.add("laptop")
    engine.correct(item.id, "qty", "3")
    assert item.qty == 3
    correction = [e for e in item.history if e.event.name == "CORRECTED"][0]
    assert correction.old == 1
    assert correction.new == 3


def test_correction_item_name(engine: ClaimEngine) -> None:
    [item] = engine.add("monitor")
    engine.correct(item.id, "normalized_item", "television")
    assert item.normalized_item == "television"
    assert item.price == Decimal("450.00")


# 2 duplicates
def test_duplicate_merge_tv_television(two_items: ClaimEngine) -> None:
    items = two_items.items
    assert len(items) == 1
    assert items[0].normalized_item == "television"
    assert items[0].qty == 2


def test_duplicate_merge_typo(two_items: ClaimEngine) -> None:
    engine = ClaimEngine()
    engine.add("tv, telivision")
    items = engine.items
    assert len(items) == 1
    assert items[0].normalized_item == "television"
    assert items[0].qty == 2


# 1 totals test (Decimal)
def test_totals_decimal(engine: ClaimEngine) -> None:
    engine.add("laptop, smartphone, kettle")
    totals = engine.totals()
    assert totals["total"] == Decimal("990.00")
    assert isinstance(totals["total"], Decimal)
    assert totals["priced_item_count"] == 3


# 1 ground truth (reviewed snapshot) - JSON
def test_ground_truth_claim_json(sample_items: ClaimEngine) -> None:
    claim = sample_items.claim_json()
    # 10 items: 2 ambiguous (charger, cable), 2 unpriced (antique clock, guitar),
    # 5 priced (television@2, laptop, kettle, smartphone, sofa), total = 2*450 + 600 + 40 + 350 + 800 = 2690
    assert claim["totals"]["total"] == 2690.0
    assert claim["totals"]["priced_item_count"] == 5
    assert claim["totals"]["excluded_ambiguous_count"] == 2


# 1 ground truth (reviewed snapshot) - report
def test_ground_truth_report(sample_items: ClaimEngine) -> None:
    report = sample_items.report_text()
    assert "NEEDS CLARIFICATION" in report
    # Both ambiguous (charger, cable) and unpriced (antique clock, guitar) appear
    assert "PRICE BLANK" in report
    assert "2690.0" in report

def test_different_items_are_not_wrongly_merged(two_items: ClaimEngine) -> None:
    """Ensure two different items are not wrongly merged into one."""
    engine = ClaimEngine()
    engine.add("monitor, television")
    items = engine.items
    assert len(items) == 2
    assert {item.normalized_item for item in items} == {"monitor", "television"}
    monitor = next(item for item in items if item.normalized_item == "monitor")
    assert monitor.price is None
    assert engine.totals()["total"] == Decimal("450.00")