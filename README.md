# Contents Claim Assistant

A rule-based, offline Python CLI for turning a comma-separated list of lost items into a structured `claim.json` and a human-readable `report.txt`. No LLM or paid APIs are used — all decisions are made via synonym normalization, RapidFuzz fuzzy matching, and a hardcoded INR price fixture.


## Quick start

```bash
uv sync
uv run cozmo-ai-take-home
```

## Demo Script

| Step | Command | Result |
|------|---------|--------|
| 1. Add items | `add: 55 inch tv, laptop, charger, cable, television, antique clock, guitar, kettle, smartphone, sofa` | 9 items processed — television merged from `tv` + `television`, charger & cable flagged ambiguous, others confirmed |
| 2. List records | `list` | Shows ID, item, qty, status, unit price in a table |
| 3. Correct size | `correct item_001 size_inch 43` | Updates size from 55″ to 43″, logs history, updates total |
| 4. List again | `list` | Shows updated size_inch on the television item |
| 5. Generate report | `report` | Writes `out/claim.json` + `out/report.txt`, prints report to console |
| 6. Quit | `quit` | Exits the CLI |

## Key Features

| Feature | What It Does |
|---------|-------------|
| Comma/semicolon parsing | `add: item1, item2; item3` splits correctly |
| Synonym normalization | `tv` + `television` → unified as `television` (merged, qty adds) |
| Ambiguity detection | `charger`, `cable`, `remote` → `needs_clarification` with reason |
| Price fixture | 10 hardcoded INR prices; unpriced items get `price: null` |
| Merge dedup | Exact + fuzzy (>=90 ratio) merge adds quantities, logs raw input |
| Corrections | `correct <id> <field> <value>` updates size, qty, item name; appends history; sets source to `corrected by user` |
| Decimal totals | Only confirmed + priced items included; excludes ambiguous + unpriced |
| Output files | `claim.json` (structured data) + `report.txt` (human-readable) |

Sample session:

```text
> add: 55 inch tv, laptop, charger, cable, television, antique clock, guitar, kettle, smartphone, sofa
Processed input; 9 item(s) affected.
> correct item_001 size_inch 43
> report
```

The full sample report is in `examples/report.txt`: 9 records, 2 ambiguous,
2 unpriced, one merge, one correction, total `2,690.00`, 4 excluded.

## Commands

| Command | Meaning |
| --- | --- |
| `add: <items>` | Add comma-separated items. |
| `correct <id> <field> <value>` | Correct `qty`, `normalized_item`, `size_inch`, or an existing attribute. |
| `list` | Show current records. |
| `report` | Write `out/claim.json` and `out/report.txt`, then print the report. |
| `help` / `quit` | Show help / exit. |

## Data model

Each observation becomes one Pydantic `Item`:

- `id` — session-local ID, e.g. `item_001`.
- `raw_text` — exactly what the user typed; never overwritten.
- `normalized_item` — canonical name, e.g. `tv` and `television` become `television`.
- `attributes` — extracted structured values, currently `size_inch`.
- `qty` — quantity, at least 1.
- `status` — `confirmed` or `needs_clarification`.
- `status_reason` — why an item needs clarification, or `null`.
- `price` / `price_source` — `Decimal` fixture price and its source, or `null`.
- `source` — `user said` or `corrected by user`.
- `history` — every create, merge, correction, status change, and reprice.

History events use `from` in JSON (the Python field is `source` because `from` is
a keyword). Merges are history events; the surviving record stays `confirmed`.

## How it works

1. **Parse** — split on commas, semicolons, or newlines; extract quantity and `size_inch`.
2. **Normalize** — synonym dictionary, singularisation, then RapidFuzz fallback.
3. **Merge** — exact normalized name, then fuzzy match at 90; add quantity and log the raw duplicate.
4. **Flag** — single ambiguous words such as `charger`, `cable`, and `remote` become `needs_clarification`.
5. **Price** — exact fixture lookup only. No match means `price=null`.
6. **Total** — plain Python `Decimal`, summing only confirmed priced records.

Corrections update the field, append a `corrected` history event with old/new
values, and set `source` to `corrected by user`. `raw_text` is never changed.
Price corrections are rejected because prices are fixture-only.

## Price fixture

`src/cozmo_ai_take_home/data/prices.json` has exactly 10 labelled items:
television 450, laptop 600, smartphone 350, headphones 120, microwave 90,
refrigerator 700, washing machine 550, sofa 800, dining table 300, kettle 40.
The file says `"source": "test fixture, not real market data"` and uses INR.
Anything outside the fixture stays blank.

## Tests

```bash
uv run pytest -v
```

`test-results.txt` contains the current run: **16 passed**.

| Category | Coverage |
| --- | --- |
| Ambiguous | `charger`, `cable`, `remote` |
| Missing prices | `antique clock`, `guitar`, `monitor` |
| Corrections | size, quantity, item-name reprice |
| Duplicates | `tv` + `television`, `telivision` typo |
| Negative merge | `monitor` and `television` stay separate |
| Totals | `Decimal` calculation and exclusion counts |
| Snapshot | reviewed expected JSON and report in `tests/expected/` |

## Limitations

See [limitations.md](limitations.md) for a detailed list of current limitations, written in simpler English with explanations and examples.
