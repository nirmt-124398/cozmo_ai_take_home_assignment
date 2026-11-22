from __future__ import annotations

import json
from pathlib import Path

from cozmo_ai_take_home.engine import ClaimEngine

EXPECTED_DIR = Path(__file__).parent / "expected"


def test_sample_claim_matches_reviewed_snapshot(sample_engine: ClaimEngine) -> None:
    expected = json.loads((EXPECTED_DIR / "sample_claim.json").read_text(encoding="utf-8"))
    actual = sample_engine.claim().to_dict()

    assert actual == expected


def test_sample_report_matches_reviewed_snapshot(sample_engine: ClaimEngine) -> None:
    expected = (EXPECTED_DIR / "sample_report.txt").read_text(encoding="utf-8")

    assert sample_engine.report() == expected
