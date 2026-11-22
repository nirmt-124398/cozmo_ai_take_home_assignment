# Walkthrough

## What I built

A local CLI that turns a messy list such as
`55 inch tv, 2 laptops, charger, television, antique clock` into a traceable
`claim.json` and a readable `report.txt`. It is rule-based and offline. I did
not use an LLM or a paid API.

## Design

The record is the centre of the solution. Each item keeps `raw_text`,
`normalized_item`, `qty`, `attributes`, `status`, `price`, `price_source`,
`source`, and `history`. `raw_text` is never overwritten, and every change adds
an old/new history event.

The pipeline is split so language and arithmetic stay separate:

1. Parse comma-separated items, quantity, and `size_inch`.
2. Normalize with a synonym dictionary and a RapidFuzz fallback.
3. Merge exact or fuzzy duplicates by adding quantity and logging the raw input.
4. Flag single ambiguous words such as `charger` and `cable`.
5. Price only from the 10-item fixture.
6. Total with plain Python `Decimal`, counting only confirmed priced records.

This gives the two kinds of unknown the brief asks for: `charger` is
`needs_clarification`, while `antique clock` is confirmed with a blank price.
Both are excluded from the total, and the report says why.

## Evidence

`raw_text` shows what was typed. `source` says whether the record is still
`user said` or has been `corrected by user`. `price_source` names the fixture.
`status_reason` explains uncertainty. `history` records old/new values for
corrections and the raw text and quantity for merges.

Money is always `Decimal`:

```python
total = sum(item.price * item.qty for item in priced_items)
```

## Tests

`uv run pytest -v` gives **16 passed** (see `test-results.txt`). The suite covers
3 ambiguous items, 3 missing prices, 3 corrections, 2 duplicates, Decimal
totals, parsing, and a reviewed JSON/report snapshot in `tests/expected/`. The
snapshot files were reviewed, not independently derived.

## Where it fails

1. I only split on commas, semicolons, and newlines. `tv and laptop` is one item.
2. I only extract `size_inch`; colour, brand, model, and serial number are ignored.
3. My fuzzy matching is tuned to this fixture. It can miss typos or merge two
   similar names incorrectly.
4. My ambiguity list is shallow. `remote control` may not be flagged, and
   `phone charger` is confirmed but unpriced.
5. The fixture is 10 invented GBP prices. If duplicates disagree on size, I keep
   the first value instead of resolving the conflict.

I also do not persist sessions, undo corrections, or accept user-supplied
prices. Those are deliberate scope limits, not hidden behaviour.

## AI use and next steps

I used an AI assistant to help write and review this implementation. I can
explain each part live. With more time I would add a clarification dialogue that
stores answers, a larger alias catalogue, and persistence. For this take-home I
kept the scope small and left uncertain values blank rather than inventing them.

Brief received 22 November 2026; implementation, tests, and docs were completed
the same day, inside the 72-hour window.
