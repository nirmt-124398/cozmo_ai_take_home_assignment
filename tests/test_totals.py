from __future__ import annotations

from decimal import Decimal

from cozmo_ai_take_home.engine import ClaimEngine


def test_total_uses_decimal_and_unit_prices(engine: ClaimEngine) -> None:
    engine.add("laptop, smartphone, kettle")
    totals = engine.totals()

    assert totals.total == Decimal("990.00")
    assert isinstance(totals.total, Decimal)
    assert totals.priced_item_count == 3
    assert totals.excluded_item_count == 0
