from __future__ import annotations

from pathlib import Path

from cozmo_ai_take_home.engine import ClaimEngine


def main() -> None:
    engine = ClaimEngine()
    engine.add("55 inch tv, 2 laptops, charger, television, antique clock")
    engine.correct("item_001", "size_inch", "43")

    examples = Path(__file__).resolve().parents[1] / "examples"
    claim_path, report_path = engine.write_outputs(examples)
    print(f"Wrote {claim_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
