# Limitations

This section lists what this assistant currently cannot do, or does poorly, along with simple explanations and examples.

---

## 1. Limited item parsing

The assistant only splits input on commas, semicolons, and newlines. Anything else in the text is treated as part of the item name.

- **Example:** `tv and laptop` is read as one combined item, not two separate items.
- **Example:** `2 in 1 laptop` is read as a single item with text `"2 in 1 laptop"` — the `2` is not interpreted as a quantity, it's just part of the name.

---

## 2. Only `size_inch` is extracted

The assistant looks for a number followed by `inch` or `"` to capture size. Other details like colour, brand, model, or serial number are ignored and lost.

- **Example:** `red 55-inch Sony TV` — the assistant only captures `size_inch: 55`, the colour `red` and brand `Sony` are not stored.
- **Example:** `blue leather sofa` — only the text `blue leather sofa` is kept as the item name; no size is extracted because there's no inch marker.

---

## 3. Fuzzy matching is tuned to this fixture

The assistant uses RapidFuzz to match item names at a 90+ similarity score. If the real-world names differ more, or if typos are outside the cutoff, the match may fail or merge items incorrectly.

- **Example:** Typing `telivision` (missing an `l`) may not match `television` because the similarity score could drop below 90.
- **Example:** `monitor` and `television` have a moderate fuzzy score — they may or may not be merged depending on the exact text and score threshold.

---

## 4. Ambiguity list is shallow

Only a few single words are flagged as ambiguous: `charger`, `cable`, and `remote`. Phrases or less-common words are not checked.

- **Example:** `phone charger` is confirmed (because `phone` is recognized), but the assistant does not flag it as ambiguous even though "which device?" is a reasonable question.
- **Example:** `remote control` is not automatically flagged — the user would need to manually `correct` it or add clarification.

---

## 5. Prices are from a test fixture only

The price list contains exactly 10 hardcoded INR amounts. These are not real market prices — they are test data.

- **Example:** `antique clock` and `guitar` have no fixture entry, so their price is `null` (blank) and they are excluded from the total.
- **Example:** If a user adds an item not in the fixture, the price field stays blank and the item is marked as unpriced in the report.

---
