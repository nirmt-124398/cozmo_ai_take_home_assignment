# Contents Claim Assistant

A local, text-only contents claim assistant for the Cozmo AI take-home brief.
It turns a messy list of lost items into a traceable `claim.json` and a readable
`report.txt`. It is rule-based, offline, and uses no LLM or paid API.

## Quick start

```bash
uv sync
uv run cozmo-ai-take-home
```

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
The file says `"source": "test fixture, not real market data"` and uses GBP.
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

The expected files are reviewed snapshots, not an independent oracle.

## Limitations

1. I only split on commas, semicolons, and newlines; `tv and laptop` is one item, and `2 in 1 laptop` is read as a 2-inch laptop.
2. I only extract `size_inch`; colour, brand, model, and serial number are ignored.
3. My fuzzy matching is tuned to this fixture and can miss typos or merge similar names incorrectly.
4. My ambiguity list is shallow: `remote control` may not be flagged, and `phone charger` is confirmed but unpriced.
5. The fixture is 10 invented GBP prices. If duplicates disagree on size, I keep the first value rather than resolving it.

## AI assistance

I used an AI assistant to help write and review this implementation. I can
explain each part of the code and the trade-offs in the walkthrough.

See [`WALKTHROUGH.md`](WALKTHROUGH.md) for the design and failure walkthrough.
