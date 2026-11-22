from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemStatus(str, Enum):
    CONFIRMED = "confirmed"
    NEEDS_CLARIFICATION = "needs_clarification"


class HistoryEventType(str, Enum):
    CREATED = "created"
    CORRECTED = "corrected"
    MERGED = "merged"
    STATUS_CHANGED = "status_changed"
    REPRICED = "repriced"


SOURCE_USER_SAID = "user said"
SOURCE_CORRECTED_BY_USER = "corrected by user"


class HistoryEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event: HistoryEventType
    field: str | None = None
    old: Any = None
    new: Any = None
    source: str | None = Field(default=None, alias="from")
    note: str | None = None


class Item(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    raw_text: str
    normalized_item: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    qty: int = Field(ge=1)
    status: ItemStatus = ItemStatus.CONFIRMED
    status_reason: str | None = None
    price: Decimal | None = None
    price_source: str | None = None
    source: str = SOURCE_USER_SAID
    history: list[HistoryEvent] = Field(default_factory=list)

    @field_validator("price")
    @classmethod
    def _price_must_not_be_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("price cannot be negative")
        return value


class FixtureInfo(BaseModel):
    version: str
    source: str
    currency: str


class Totals(BaseModel):
    currency: str
    total: Decimal
    priced_item_count: int
    excluded_item_count: int
    excluded_ambiguous_count: int
    excluded_unpriced_count: int


class Claim(BaseModel):
    schema_version: str = "1.0"
    currency: str
    price_fixture: FixtureInfo
    items: list[Item]
    totals: Totals
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json", by_alias=True)
        for item_data, item in zip(data["items"], self.items, strict=True):
            # Keep item price/price_source nulls, but drop irrelevant history nulls.
            item_data["history"] = [
                event.model_dump(mode="json", by_alias=True, exclude_none=True)
                for event in item.history
            ]
        return data
