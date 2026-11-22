from __future__ import annotations

import re
import shlex

from .catalog import display_name
from .engine import ClaimEngine
from .models import Item
from .report import format_money

HELP = """\
Commands:
  add: <items>                  Add comma-separated items, e.g. add: tv, 2 laptops, charger
  correct <id> <field> <value>  Correct a field, e.g. correct item_001 size_inch 43
  list                          Show current records
  report                        Write out/claim.json and out/report.txt, then print the report
  help                          Show this help
  quit                          Exit
"""


def _summary(item: Item) -> str:
    price = "blank" if item.price is None else format_money(item.price)
    return (
        f"  {item.id}  {display_name(item.normalized_item)} x{item.qty}  "
        f"{item.status.value}  unit price: {price}"
    )


def main() -> None:
    engine = ClaimEngine()
    print("Cozmo AI contents claim assistant (local, rule-based)")
    print("Type 'help' for commands.")

    while True:
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        command = raw.strip()
        if not command:
            continue

        lowered = command.lower()
        if lowered in {"quit", "exit"}:
            break

        if lowered == "help":
            print(HELP, end="")
            continue

        if re.match(r"^add\b", command, re.IGNORECASE):
            payload = command[3:].lstrip()
            if payload.startswith(":"):
                payload = payload[1:].lstrip()
            if not payload:
                print("Usage: add: <comma-separated items>")
                continue
            try:
                affected = engine.add(payload)
            except ValueError as exc:
                print(f"Error: {exc}")
                continue
            print(f"Processed input; {len(affected)} item(s) affected.")
            for item in affected:
                print(_summary(item))
            continue

        if re.match(r"^correct\b", command, re.IGNORECASE):
            parts = shlex.split(command)
            if len(parts) < 4:
                print("Usage: correct <item_id> <field> <value>")
                continue
            item_id, field = parts[1], parts[2]
            value = " ".join(parts[3:])
            try:
                item = engine.correct(item_id, field, value)
            except (KeyError, ValueError) as exc:
                print(f"Error: {exc}")
                continue
            print(f"Updated {item.id} {field}.")
            print(_summary(item))
            continue

        if lowered == "list":
            if not engine.items:
                print("No items recorded.")
                continue
            print(f"{'ID':<9} {'Item':<20} {'Qty':>3}  {'Status':<19} {'Unit price':>10}")
            for item in engine.items:
                price = "blank" if item.price is None else format_money(item.price)
                print(
                    f"{item.id:<9} {display_name(item.normalized_item):<20} "
                    f"{item.qty:>3}  {item.status.value:<19} {price:>10}"
                )
            continue

        if lowered == "report":
            try:
                claim_path, report_path = engine.write_outputs("out")
            except OSError as exc:
                print(f"Error: {exc}")
                continue
            print(engine.report(), end="")
            print(f"\nWrote {claim_path} and {report_path}")
            continue

        print("Unknown command. Type 'help'.")


if __name__ == "__main__":
    main()
