from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from .catalog import NormalizationResult, normalize_item
from .models import (
    SOURCE_CORRECTED_BY_USER,
    SOURCE_USER_SAID,
    Claim,
    FixtureInfo,
    HistoryEvent,
    HistoryEventType,
    Item,
    ItemStatus,
    Totals,
)
from .parsing import Observation, parse_observations
from .pricing import PriceFixture, Pricer
from .report import render_report

FUZZY_MERGE_CUTOFF = 90.0


class ClaimEngine:
    def __init__(self, fixture: PriceFixture | None = None):
        self.fixture = fixture or PriceFixture.load_default()
        self.pricer = Pricer(self.fixture)
        self._items: list[Item] = []
        self._counter = 0

    @property
    def items(self) -> list[Item]:
        return list(self._items)

    def get(self, item_id: str) -> Item:
        for item in self._items:
            if item.id == item_id:
                return item
        raise KeyError(f"unknown item id '{item_id}'")

    def add(self, text: str) -> list[Item]:
        observations = parse_observations(text)
        affected: list[Item] = []
        seen: set[str] = set()
        for observation in observations:
            item = self._add_observation(observation)
            if item.id not in seen:
                seen.add(item.id)
                affected.append(item)
        return affected

    def _add_observation(self, observation: Observation) -> Item:
        normalization = normalize_item(observation.item_text)
        target, fuzzy_score = self._find_merge_target(normalization.normalized_item)
        if target is not None:
            self._merge(target, observation, normalization, fuzzy_score)
            return target

        self._counter += 1
        item_id = f"item_{self._counter:03d}"
        price, price_source = self._price_for(normalization)
        created_note = f"status={normalization.status.value}"
        if normalization.status_reason:
            created_note += f"; {normalization.status_reason}"

        item = Item(
            id=item_id,
            raw_text=observation.raw_text,
            normalized_item=normalization.normalized_item,
            attributes=dict(observation.attributes),
            qty=observation.qty,
            status=normalization.status,
            status_reason=normalization.status_reason,
            price=price,
            price_source=price_source,
            source=SOURCE_USER_SAID,
            history=[
                HistoryEvent(
                    event=HistoryEventType.CREATED,
                    source="user input",
                    note=created_note,
                )
            ],
        )
        self._items.append(item)
        return item

    def _find_merge_target(self, normalized_item: str) -> tuple[Item | None, float | None]:
        for item in self._items:
            if item.normalized_item == normalized_item:
                return item, 100.0

        best_item: Item | None = None
        best_score = 0.0
        for item in self._items:
            score = fuzz.ratio(normalized_item, item.normalized_item)
            if score >= FUZZY_MERGE_CUTOFF and score > best_score:
                best_item = item
                best_score = score
        if best_item is not None:
            return best_item, best_score
        return None, None

    def _merge(
        self,
        target: Item,
        observation: Observation,
        normalization: NormalizationResult,
        fuzzy_score: float | None,
    ) -> None:
        old_qty = target.qty
        target.qty = target.qty + observation.qty
        target.history.append(
            HistoryEvent(
                event=HistoryEventType.MERGED,
                field="qty",
                old=old_qty,
                new=target.qty,
                source=SOURCE_USER_SAID,
                note=f'merged raw input "{observation.raw_text}" (qty {observation.qty})',
            )
        )

        if fuzzy_score is not None and fuzzy_score < 100.0:
            target.history.append(
                HistoryEvent(
                    event=HistoryEventType.MERGED,
                    field="normalized_item",
                    old=target.normalized_item,
                    new=normalization.normalized_item,
                    source="rule: fuzzy match",
                    note=f"matched existing item by fuzzy name (score {fuzzy_score:.1f})",
                )
            )

        for key, value in observation.attributes.items():
            if key not in target.attributes:
                target.attributes[key] = value
                target.history.append(
                    HistoryEvent(
                        event=HistoryEventType.MERGED,
                        field=key,
                        new=value,
                        source=SOURCE_USER_SAID,
                        note=f'filled {key} from raw input "{observation.raw_text}"',
                    )
                )

        if normalization.status is ItemStatus.NEEDS_CLARIFICATION and target.status is ItemStatus.CONFIRMED:
            target.status = ItemStatus.NEEDS_CLARIFICATION
            target.status_reason = normalization.status_reason
            target.history.append(
                HistoryEvent(
                    event=HistoryEventType.STATUS_CHANGED,
                    field="status",
                    old=ItemStatus.CONFIRMED.value,
                    new=ItemStatus.NEEDS_CLARIFICATION.value,
                    source="rule: ambiguity",
                    note=normalization.status_reason,
                )
            )

    def _price_for(self, normalization: NormalizationResult) -> tuple[Decimal | None, str | None]:
        if normalization.status is ItemStatus.NEEDS_CLARIFICATION:
            return None, None
        return self.pricer.lookup(normalization.normalized_item)

    def correct(self, item_id: str, field: str, value: str) -> Item:
        item = self.get(item_id)
        field = field.strip()
        if not field:
            raise ValueError("field name is empty")

        if field == "price":
            raise ValueError(
                "price is fixture-only; correct normalized_item or edit the fixture instead"
            )

        if field == "qty":
            new_value: Any = self._parse_positive_int(value, "qty")
            old_value = item.qty
            item.qty = new_value
            item.history.append(self._correction_event(field, old_value, new_value))
            self._mark_corrected(item)
            return item

        if field == "size_inch":
            new_value = self._parse_size(value)
            old_value = item.attributes.get("size_inch")
            item.attributes["size_inch"] = new_value
            item.history.append(self._correction_event(field, old_value, new_value))
            self._mark_corrected(item)
            return item

        if field == "normalized_item":
            normalization = normalize_item(value)
            old_value = item.normalized_item
            old_status = item.status
            item.normalized_item = normalization.normalized_item
            item.history.append(self._correction_event(field, old_value, normalization.normalized_item))

            if normalization.status is ItemStatus.NEEDS_CLARIFICATION:
                item.status = ItemStatus.NEEDS_CLARIFICATION
                item.status_reason = normalization.status_reason
            else:
                item.status = ItemStatus.CONFIRMED
                item.status_reason = None

            if item.status is not old_status:
                item.history.append(
                    HistoryEvent(
                        event=HistoryEventType.STATUS_CHANGED,
                        field="status",
                        old=old_status.value,
                        new=item.status.value,
                        source="user correction",
                        note=item.status_reason,
                    )
                )

            new_price, new_source = self._price_for(normalization)
            self._apply_price(item, new_price, new_source)
            self._mark_corrected(item)
            return item

        if field in item.attributes:
            current = item.attributes[field]
            new_value = self._coerce_like(value, current)
            old_value = current
            item.attributes[field] = new_value
            item.history.append(self._correction_event(field, old_value, new_value))
            self._mark_corrected(item)
            return item

        raise ValueError(
            f"unknown field '{field}'; correctable fields are qty, normalized_item, "
            "size_inch, or an existing attribute"
        )

    def _correction_event(self, field: str, old: Any, new: Any) -> HistoryEvent:
        return HistoryEvent(
            event=HistoryEventType.CORRECTED,
            field=field,
            old=old,
            new=new,
            source="user correction",
        )

    @staticmethod
    def _mark_corrected(item: Item) -> None:
        item.source = SOURCE_CORRECTED_BY_USER

    def _apply_price(self, item: Item, price: Decimal | None, source: str | None) -> None:
        old_price = item.price
        old_source = item.price_source
        if old_price == price and old_source == source:
            return
        item.price = price
        item.price_source = source
        item.history.append(
            HistoryEvent(
                event=HistoryEventType.REPRICED,
                field="price",
                old=old_price,
                new=price,
                source="fixture lookup",
            )
        )

    @staticmethod
    def _parse_positive_int(value: str, field: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be a whole number") from exc
        if parsed < 1:
            raise ValueError(f"{field} must be at least 1")
        return parsed

    @staticmethod
    def _parse_size(value: str) -> int | float:
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("size_inch must be a number") from exc
        if parsed <= 0:
            raise ValueError("size_inch must be greater than 0")
        return int(parsed) if parsed == parsed.to_integral_value() else float(parsed)

    @staticmethod
    def _coerce_like(value: str, current: Any) -> Any:
        if isinstance(current, bool):
            return value.lower() in {"true", "yes", "1"}
        if isinstance(current, int):
            return ClaimEngine._parse_positive_int(value, "attribute")
        if isinstance(current, float):
            try:
                return float(value)
            except ValueError as exc:
                raise ValueError("attribute must be a number") from exc
        return value

    def totals(self) -> Totals:
        ambiguous = [item for item in self._items if item.status is ItemStatus.NEEDS_CLARIFICATION]
        unpriced = [
            item
            for item in self._items
            if item.status is not ItemStatus.NEEDS_CLARIFICATION and item.price is None
        ]
        priced = [
            item
            for item in self._items
            if item.status is not ItemStatus.NEEDS_CLARIFICATION and item.price is not None
        ]
        total = sum((item.price * item.qty for item in priced), Decimal("0.00"))
        return Totals(
            currency=self.fixture.currency,
            total=total.quantize(Decimal("0.01")),
            priced_item_count=len(priced),
            excluded_item_count=len(ambiguous) + len(unpriced),
            excluded_ambiguous_count=len(ambiguous),
            excluded_unpriced_count=len(unpriced),
        )

    def claim(self) -> Claim:
        return Claim(
            currency=self.fixture.currency,
            price_fixture=FixtureInfo(
                version=self.fixture.version,
                source=self.fixture.source,
                currency=self.fixture.currency,
            ),
            items=[item.model_copy(deep=True) for item in self._items],
            totals=self.totals(),
            disclaimer=self.fixture.disclaimer,
        )

    def report(self) -> str:
        return render_report(self.claim())

    def write_outputs(self, out_dir: str | Path) -> tuple[Path, Path]:
        directory = Path(out_dir)
        directory.mkdir(parents=True, exist_ok=True)
        claim = self.claim()
        claim_path = directory / "claim.json"
        report_path = directory / "report.txt"
        claim_path.write_text(
            json.dumps(claim.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(render_report(claim), encoding="utf-8")
        return claim_path, report_path
