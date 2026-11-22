from __future__ import annotations

from decimal import Decimal
from importlib.resources import files

from pydantic import BaseModel


class FixtureItem(BaseModel):
    label: str
    price: Decimal


class PriceFixture(BaseModel):
    version: str
    source: str
    currency: str
    disclaimer: str
    items: dict[str, FixtureItem]

    @classmethod
    def load_default(cls) -> PriceFixture:
        path = files("cozmo_ai_take_home.data").joinpath("prices.json")
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class Pricer:
    def __init__(self, fixture: PriceFixture):
        self.fixture = fixture

    def lookup(self, normalized_item: str) -> tuple[Decimal | None, str | None]:
        entry = self.fixture.items.get(normalized_item)
        if entry is None:
            return None, None
        return entry.price, f"fixture {self.fixture.version} ({self.fixture.source})"
