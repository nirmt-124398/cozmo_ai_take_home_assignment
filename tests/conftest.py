from __future__ import annotations

import pytest

from cozmo_ai_take_home.engine import ClaimEngine

SAMPLE_INPUT = "55 inch tv, 2 laptops, charger, television, antique clock"


@pytest.fixture
def engine() -> ClaimEngine:
    return ClaimEngine()


@pytest.fixture
def sample_engine() -> ClaimEngine:
    engine = ClaimEngine()
    engine.add(SAMPLE_INPUT)
    engine.correct("item_001", "size_inch", "43")
    return engine
