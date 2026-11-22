from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

import re
from pathlib import Path

from rapidfuzz import fuzz, process

from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    CONFIRMED = "confirmed"
    NEEDS_CLARIFICATION = "needs_clarification"


class HistoryEventType(str, Enum):
    CREATED = "created"
    CORRECTED = "corrected"
    MERGED = "merged"
    STATUS_CHANGED = "status_changed"


SOURCE_USER_SAID = "user said"


@dataclass(frozen=True)
class NormalizedItem:
    name: str
    status: ItemStatus
    reason: str | None


def clean_text(text: str) -> str:
    value = text.strip().lower()
    value = value.replace("&", " and ")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = re.sub(r"[^a-z0-9\s'\-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^(?:a|an|the)\s+", "", value)
    return value


CANONICAL: dict[str, tuple[str, ...]] = {
    "television": ("television", "tv", "telly"),
    "laptop": ("laptop", "laptop computer"),
    "smartphone": ("smartphone", "phone", "mobile"),
    "headphones": ("headphones", "headphone"),
    "microwave": ("microwave", "microwave oven"),
    "refrigerator": ("refrigerator", "fridge"),
    "washing machine": ("washing machine", "washer"),
    "sofa": ("sofa", "couch"),
    "dining table": ("dining table", "dinner table"),
    "kettle": ("kettle", "electric kettle"),
}

ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in CANONICAL.items()
    for alias in aliases
}

AMBIGUOUS: dict[str, str] = {
    "charger": "which device?",
    "cable": "which cable?",
    "remote": "which device's remote?",
}


def normalize(text: str) -> NormalizedItem:
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("empty item after cleaning")
    if cleaned in AMBIGUOUS:
        return NormalizedItem(name=cleaned, status=ItemStatus.NEEDS_CLARIFICATION, reason=f"'{cleaned}' is ambiguous ({AMBIGUOUS[cleaned]})")
    if cleaned in ALIAS_TO_CANONICAL:
        return NormalizedItem(name=ALIAS_TO_CANONICAL[cleaned], status=ItemStatus.CONFIRMED, reason=None)
    choices = list(ALIAS_TO_CANONICAL)
    match = process.extractOne(cleaned, choices, scorer=fuzz.ratio, score_cutoff=88)
    if match is not None:
        alias, _, _ = match
        return NormalizedItem(name=ALIAS_TO_CANONICAL[alias], status=ItemStatus.CONFIRMED, reason=None)
    return NormalizedItem(name=cleaned, status=ItemStatus.CONFIRMED, reason=None)


def extract_qty_and_size(raw: str) -> tuple[int, str, dict[str, Any]]:
    attributes: dict[str, Any] = {}
    text = raw.strip()
    size_match = re.search(r"(\d+)\s*(?:inch|\")", text, re.IGNORECASE)
    if size_match:
        attributes["size_inch"] = int(size_match.group(1))
        text = text[: size_match.start()] + text[size_match.end():]
    prefix = re.match(r"^\s*(\d+)\s*x?\s*(\S+)", text, re.IGNORECASE)
    if prefix:
        qty = int(prefix.group(1))
        item_text = prefix.group(2).strip()
    else:
        suffix = re.match(r"^(.*?)\s+x\s*(\d+)\s*$", text, re.IGNORECASE)
        if suffix:
            qty = int(suffix.group(2))
            item_text = suffix.group(1).strip()
        else:
            qty = 1
            item_text = text
    item_text = item_text.strip()
    if not item_text:
        raise ValueError("no item name found")
    return qty, item_text, attributes


class HistoryEvent(BaseModel):
    event: HistoryEventType
    field: str | None = None
    old: Any = None
    new: Any = None
    source: str | None = None
    note: str | None = None


class ItemRecord(BaseModel):
    id: str
    raw_text: str
    normalized_item: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    qty: int = Field(default=1, ge=1)
    status: ItemStatus = ItemStatus.CONFIRMED
    status_reason: str | None = None
    price: Decimal | None = None
    price_source: str | None = None
    source: str = SOURCE_USER_SAID
    history: list[HistoryEvent] = Field(default_factory=list)


class PriceFixture(BaseModel):
    version: str
    source_label: str
    currency: str
    items: dict[str, Decimal] = Field(default_factory=dict)

    @classmethod
    def load_default(cls) -> "PriceFixture":
        path = Path(__file__).parent / "data" / "prices.json"
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class ClaimEngine:
    def __init__(self, fixture: PriceFixture | None = None):
        self.fixture = fixture or PriceFixture.load_default()
        self._items: list[ItemRecord] = []
        self._counter = 0

    def add(self, text: str) -> list[ItemRecord]:
        segments = [s.strip() for s in re.split(r"[,;]", text) if s.strip()]
        affected: list[ItemRecord] = []
        seen_ids: set[str] = set()
        for segment in segments:
            obs = self._parse_segment(segment)
            item = self._add_observation(obs)
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                affected.append(item)
        return affected

    def _parse_segment(self, segment: str) -> dict:
        qty, item_text, attributes = extract_qty_and_size(segment)
        normalized = normalize(item_text)
        return {
            "raw": segment,
            "item_text": item_text,
            "qty": qty,
            "normalized_name": normalized.name,
            "normalized_status": normalized.status,
            "normalized_reason": normalized.reason,
            "attributes": attributes,
        }

    def _add_observation(self, obs: dict) -> ItemRecord:
        target = self._find_merge_target(obs["normalized_name"])
        if target is not None:
            self._merge(target, obs)
            return target
        self._counter += 1
        item_id = f"item_{self._counter:03d}"
        price, price_source = self._lookup_price(obs["normalized_name"])
        created = HistoryEvent(event=HistoryEventType.CREATED, source="user input", note=f"status={obs['normalized_status'].value}")
        if obs["normalized_reason"]:
            created.note += f"; {obs['normalized_reason']}"
        item = ItemRecord(
            id=item_id,
            raw_text=obs["raw"],
            normalized_item=obs["normalized_name"],
            attributes=obs["attributes"],
            qty=obs["qty"],
            status=obs["normalized_status"],
            status_reason=obs["normalized_reason"],
            price=price,
            price_source=price_source,
            source=SOURCE_USER_SAID,
            history=[created],
        )
        self._items.append(item)
        return item

    def _find_merge_target(self, normalized_name: str) -> ItemRecord | None:
        for item in self._items:
            if item.normalized_item == normalized_name:
                return item
        best: ItemRecord | None = None
        best_score = 0
        for item in self._items:
            score = fuzz.ratio(normalized_name, item.normalized_item)
            if score >= 90 and score > best_score:
                best = item
                best_score = score
        if best is not None:
            return best
        return None

    def _merge(self, target: ItemRecord, obs: dict) -> None:
        old_qty = target.qty
        target.qty += obs["qty"]
        merge_event = HistoryEvent(event=HistoryEventType.MERGED, field="qty", old=old_qty, new=target.qty, source="user said", note=f'merged raw input "{obs["raw"]}" (qty {obs["qty"]})')
        target.history.append(merge_event)
        if target.normalized_item != obs["normalized_name"]:
            name_event = HistoryEvent(event=HistoryEventType.MERGED, field="normalized_item", old=target.normalized_item, new=obs["normalized_name"], source="rule: fuzzy match", note=f'fuzzy matched "{obs["raw"]}" to existing item')
            target.history.append(name_event)
        for key, value in obs["attributes"].items():
            if key not in target.attributes:
                target.attributes[key] = value
                target.history.append(HistoryEvent(event=HistoryEventType.MERGED, field=key, new=value, source="user said", note=f'filled {key} from raw input "{obs["raw"]}"'))
        if obs["normalized_status"] is ItemStatus.NEEDS_CLARIFICATION and target.status is ItemStatus.CONFIRMED:
            target.status = ItemStatus.NEEDS_CLARIFICATION
            target.status_reason = obs["normalized_reason"]
            status_event = HistoryEvent(event=HistoryEventType.STATUS_CHANGED, field="status", old=ItemStatus.CONFIRMED.value, new=ItemStatus.NEEDS_CLARIFICATION.value, source="rule: ambiguity", note=obs["normalized_reason"])
            target.history.append(status_event)

    def _lookup_price(self, normalized_name: str) -> tuple[Decimal | None, str | None]:
        entry = self.fixture.items.get(normalized_name)
        if entry is None:
            return None, None
        return Decimal(entry), f"fixture {self.fixture.version} ({self.fixture.source_label})"

    def correct(self, item_id: str, field: str, value: str) -> ItemRecord:
        item = self._get_item(item_id)
        field = field.strip()
        if field == "price":
            raise ValueError("price is fixture-only; edit the fixture instead")
        if field == "qty":
            new_qty = int(value)
            if new_qty < 1:
                raise ValueError("qty must be at least 1")
            old_qty = item.qty
            item.qty = new_qty
            event = HistoryEvent(event=HistoryEventType.CORRECTED, field="qty", old=old_qty, new=new_qty, source="user correction")
            item.history.append(event)
            self._mark_corrected(item)
            return item
        if field == "size_inch":
            new_size = Decimal(value)
            old_size = item.attributes.get("size_inch")
            item.attributes["size_inch"] = new_size
            event = HistoryEvent(event=HistoryEventType.CORRECTED, field="size_inch", old=old_size, new=new_size, source="user correction")
            item.history.append(event)
            self._mark_corrected(item)
            return item
        if field == "normalized_item":
            norm = normalize(value)
            old_norm = item.normalized_item
            old_status = item.status
            old_reason = item.status_reason
            item.normalized_item = norm.name
            item.history.append(HistoryEvent(event=HistoryEventType.CORRECTED, field="normalized_item", old=old_norm, new=norm.name, source="user correction"))
            if norm.status is ItemStatus.NEEDS_CLARIFICATION:
                item.status = ItemStatus.NEEDS_CLARIFICATION
                item.status_reason = norm.reason
            else:
                item.status = ItemStatus.CONFIRMED
                item.status_reason = None
            price, price_source = self._lookup_price(norm.name)
            item.price = price
            item.price_source = price_source
            self._mark_corrected(item)
            if item.status is not old_status:
                event = HistoryEvent(event=HistoryEventType.STATUS_CHANGED, field="status", old=old_status.value, new=item.status.value, source="user correction", note=item.status_reason)
                item.history.append(event)
            return item
        if field in item.attributes:
            current = item.attributes[field]
            new_val = Decimal(value) if isinstance(current, Decimal) else value
            old_val = current
            item.attributes[field] = new_val
            event = HistoryEvent(event=HistoryEventType.CORRECTED, field=field, old=old_val, new=new_val, source="user correction")
            item.history.append(event)
            self._mark_corrected(item)
            return item
        raise ValueError(f"unknown field '{field}'; correctable fields are qty, size_inch, normalized_item, or an existing attribute")

    def _mark_corrected(self, item: ItemRecord) -> None:
        item.source = "corrected by user"

    def _get_item(self, item_id: str) -> ItemRecord:
        for item in self._items:
            if item.id == item_id:
                return item
        raise KeyError(f"unknown item id '{item_id}'")

    @property
    def items(self) -> list[ItemRecord]:
        return list(self._items)

    def totals(self) -> dict[str, Any]:
        ambiguous = [i for i in self._items if i.status is ItemStatus.NEEDS_CLARIFICATION]
        unpriced = [i for i in self._items if i.status is not ItemStatus.NEEDS_CLARIFICATION and i.price is None]
        priced = [i for i in self._items if i.status is not ItemStatus.NEEDS_CLARIFICATION and i.price is not None]
        total = sum((i.price * i.qty for i in priced), Decimal("0.00"))
        return {
            "currency": self.fixture.currency,
            "total": total.quantize(Decimal("0.01")),
            "priced_item_count": len(priced),
            "excluded_item_count": len(ambiguous) + len(unpriced),
            "excluded_ambiguous_count": len(ambiguous),
            "excluded_unpriced_count": len(unpriced),
        }

    def claim_json(self) -> dict[str, Any]:
        def safe_float(v: Any) -> Any:
            return float(v) if isinstance(v, Decimal) else v
        items_data = []
        for item in self._items:
            items_data.append({
                "id": item.id,
                "raw_text": item.raw_text,
                "normalized_item": item.normalized_item,
                "attributes": item.attributes,
                "qty": item.qty,
                "status": item.status.value,
                "status_reason": item.status_reason,
                "price": safe_float(item.price) if item.price is not None else None,
                "price_source": item.price_source,
                "source": item.source,
                "history": [{"event": e.event, "field": e.field, "old": safe_float(e.old) if e.old is not None else None, "new": safe_float(e.new) if e.new is not None else None, "source": e.source, "note": e.note} for e in item.history],
            })
        totals = self.totals()
        return {"schema_version": "1.0", "currency": safe_float(totals["currency"]), "items": items_data, "totals": {k: safe_float(v) for k, v in totals.items()}, "disclaimer": f"Prices come from a test fixture, not real market data ({self.fixture.source_label})."}

    def report_text(self) -> str:
        lines = ["CONTENTS CLAIM REPORT", "---------------------", f"Currency: {self.totals()['currency']}", ""]
        if not self._items:
            lines.append("No items recorded.")
        else:
            for idx, item in enumerate(self._items, start=1):
                label = item.normalized_item.replace("_", " ").title()
                if item.attributes.get("size_inch"):
                    label += f' ({item.attributes["size_inch"]}" )'
                label += f" x{item.qty}"
                if item.status is ItemStatus.NEEDS_CLARIFICATION:
                    amount = ""
                    tag = f"NEEDS CLARIFICATION ({item.status_reason or ''})"
                elif item.price is None:
                    amount = ""
                    tag = "PRICE BLANK (not in fixture)"
                else:
                    amount = f"£{item.price * item.qty:,.2f}"
                    tag = "[fixture price]"
                line = f"{idx}. {label:<35} {amount:>10}  {tag}"
                lines.append(line.rstrip())
                for ev in item.history:
                    if ev.event is HistoryEventType.CORRECTED:
                        old_v = ev.old if ev.old is None else float(ev.old)
                        new_v = ev.new if ev.new is None else float(ev.new)
                        lines.append(f"   Note: corrected {ev.field} from {old_v} to {new_v}")
                    elif ev.event is HistoryEventType.MERGED:
                        lines.append(f"   Note: {ev.note}")
                    elif ev.event is HistoryEventType.STATUS_CHANGED:
                        lines.append(f"   Note: status changed to {ev.new}")
        totals = self.totals()
        excluded = totals["excluded_item_count"]
        total_str = str(totals["total"]) if not isinstance(totals["total"], Decimal) else str(float(totals["total"]))
        lines.append("")
        lines.append(f"Total (priced items only): {total_str}")
        if excluded:
            parts: list[str] = []
            if totals["excluded_ambiguous_count"]:
                parts.append(f"{totals['excluded_ambiguous_count']} ambiguous")
            if totals["excluded_unpriced_count"]:
                parts.append(f"{totals['excluded_unpriced_count']} unpriced")
            lines.append(f"Excluded from total: {excluded} items ({', '.join(parts)})")
        else:
            lines.append("Excluded from total: 0 items")
        lines.append("")
        lines.append(self.claim_json()["disclaimer"])
        return "\n".join(lines) + "\n"

    def write_outputs(self, out_dir: str) -> tuple:
        from pathlib import Path as _P
        d = _P(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        claim = self.claim_json()
        jpath = d / "claim.json"
        rpath = d / "report.txt"
        jpath.write_text(__import__("json").dumps(claim, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
        rpath.write_text(self.report_text(), encoding="utf-8")
        return jpath, rpath