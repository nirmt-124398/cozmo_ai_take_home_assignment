from __future__ import annotations

from .engine import ClaimEngine, ItemStatus


def main() -> None:
    engine = ClaimEngine()
    print("Cozmo AI contents claim assistant (local, rule-based)")
    print("Type help for commands.")

    while True:
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        cmd = raw.strip().lower()
        if not cmd:
            continue
        if cmd in {"quit", "exit"}:
            break
        if cmd == "help":
            print(
                "Commands:\n"
                "  add: <items>                 Add comma-separated items\n"
                "  correct <id> <field> <value>  Correct a field\n"
                "  list                         Show current records\n"
                "  report                       Write claim.json and report.txt\n"
                "  help                         Show this help\n"
                "  quit                         Exit\n"
            )
            continue
        if cmd.startswith("add:"):
            payload = raw[4:].strip()
            if payload.startswith(":"):
                payload = payload[1:].strip()
            try:
                affected = engine.add(payload)
            except ValueError as exc:
                print(f"Error: {exc}")
                continue
            for item in affected:
                price_str = f"unit price: {item.price}" if item.price is not None else "unit price: blank"
                status_str = f"{item.status.value}"
                if item.status is ItemStatus.NEEDS_CLARIFICATION:
                    status_str += f" ({item.status_reason})"
                print(f"  {item.id}  {item.normalized_item} x{item.qty}  {status_str}  {price_str}")
            continue
        if cmd.startswith("correct "):
            parts = raw.split(None, 3)
            if len(parts) < 4:
                print("Usage: correct <item_id> <field> <value>")
                continue
            _, item_id, field, value = parts
            try:
                item = engine.correct(item_id, field, value)
            except (KeyError, ValueError) as exc:
                print(f"Error: {exc}")
                continue
            price_str = f"unit price: {item.price}" if item.price is not None else "unit price: blank"
            status_str = f"{item.status.value}"
            if item.status is ItemStatus.NEEDS_CLARIFICATION:
                status_str += f" ({item.status_reason})"
            print(f"Updated {item.id} {field}.")
            print(f"  {item.id}  {item.normalized_item} x{item.qty}  {status_str}  {price_str}")
            continue
        if cmd == "list":
            if not engine.items:
                print("No items recorded.")
                continue
            print(f"{'ID':<9} {'Item':<20} {'Qty':>3}  {'Status':<15} {'Unit price':>10}")
            for item in engine.items:
                price_str = f"£{item.price}" if item.price is not None else "blank"
                print(
                    f"{item.id:<9} {item.normalized_item:<20} "
                    f"{item.qty:>3}  {item.status.value:<15} {price_str:>10}"
                )
            continue
        if cmd == "report":
            try:
                jpath, rpath = engine.write_outputs("out")
            except OSError as exc:
                print(f"Error: {exc}")
                continue
            print(engine.report_text(), end="")
            print(f"\nWrote {jpath} and {rpath}")
            continue
        print("Unknown command. Type help.")


if __name__ == "__main__":
    main()