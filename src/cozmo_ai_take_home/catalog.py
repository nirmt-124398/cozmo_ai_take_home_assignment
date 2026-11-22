from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .models import ItemStatus

# Canonical item name -> known aliases.
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "television": (
        "television",
        "tv",
        "telly",
        "television set",
        "flat screen",
        "flat screen tv",
        "smart tv",
    ),
    "laptop": ("laptop", "laptop computer", "laptop pc"),
    "smartphone": ("smartphone", "phone", "mobile", "mobile phone", "cell phone", "cellphone"),
    "headphones": ("headphones", "headphone", "earphones", "earphone", "headset"),
    "microwave": ("microwave", "microwave oven"),
    "refrigerator": ("refrigerator", "fridge", "fridge freezer"),
    "washing machine": ("washing machine", "washer"),
    "sofa": ("sofa", "couch", "settee"),
    "dining table": ("dining table", "dinner table"),
    "kettle": ("kettle", "electric kettle"),
}

ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in CANONICAL_ALIASES.items()
    for alias in aliases
}

# A single word here is not enough evidence to identify an item. The value is
# the clarification question shown in the report.
AMBIGUOUS_TERMS: dict[str, str] = {
    "charger": "which device?",
    "cable": "which cable?",
    "remote": "which device's remote?",
    "adapter": "which adapter?",
    "battery": "which battery?",
    "case": "which case?",
    "cover": "which cover?",
    "stand": "which stand?",
    "bag": "which bag?",
    "controller": "which controller?",
}

CATALOG_FUZZY_CUTOFF = 88.0
AMBIGUOUS_FUZZY_CUTOFF = 90.0


@dataclass(frozen=True)
class NormalizationResult:
    normalized_item: str
    status: ItemStatus
    status_reason: str | None


def clean_text(text: str) -> str:
    value = text.strip().lower()
    value = value.replace("&", " and ")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = re.sub(r"[^a-z0-9\s'\-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^(?:a|an|the)\s+", "", value)
    return value


def singularize_last_word(text: str) -> str:
    parts = text.split()
    if not parts:
        return text
    last = parts[-1]
    if last.endswith("ies") and len(last) > 3:
        last = last[:-3] + "y"
    elif last.endswith(("sses", "shes", "ches", "xes")):
        last = last[:-2]
    elif last.endswith("s") and not last.endswith("ss") and len(last) > 1:
        last = last[:-1]
    parts[-1] = last
    return " ".join(parts)


def _match_catalog(cleaned: str) -> str | None:
    candidates = (cleaned, singularize_last_word(cleaned))
    for candidate in candidates:
        canonical = ALIAS_TO_CANONICAL.get(candidate)
        if canonical is not None:
            return canonical

    for candidate in candidates:
        match = process.extractOne(
            candidate,
            list(ALIAS_TO_CANONICAL),
            scorer=fuzz.ratio,
            score_cutoff=CATALOG_FUZZY_CUTOFF,
        )
        if match is not None:
            alias, _, _ = match
            return ALIAS_TO_CANONICAL[alias]
    return None


def _match_ambiguous(cleaned: str) -> str | None:
    candidates = (cleaned, singularize_last_word(cleaned))
    for candidate in candidates:
        if candidate in AMBIGUOUS_TERMS:
            return candidate

    # Only fuzzy-match single words; phrases like "phone charger" are treated
    # as qualified rather than ambiguous.
    for candidate in candidates:
        if " " in candidate:
            continue
        match = process.extractOne(
            candidate,
            list(AMBIGUOUS_TERMS),
            scorer=fuzz.ratio,
            score_cutoff=AMBIGUOUS_FUZZY_CUTOFF,
        )
        if match is not None:
            term, _, _ = match
            return term
    return None


def normalize_item(text: str) -> NormalizationResult:
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("item name is empty after cleaning")

    ambiguous = _match_ambiguous(cleaned)
    if ambiguous is not None:
        hint = AMBIGUOUS_TERMS[ambiguous]
        return NormalizationResult(
            normalized_item=ambiguous,
            status=ItemStatus.NEEDS_CLARIFICATION,
            status_reason=f"'{ambiguous}' is ambiguous ({hint})",
        )

    canonical = _match_catalog(cleaned)
    if canonical is not None:
        return NormalizationResult(
            normalized_item=canonical,
            status=ItemStatus.CONFIRMED,
            status_reason=None,
        )

    # Unknown but not necessarily ambiguous: we know what the words mean, we
    # just have no fixture price for it.
    return NormalizationResult(
        normalized_item=singularize_last_word(cleaned),
        status=ItemStatus.CONFIRMED,
        status_reason=None,
    )


def display_name(normalized_item: str) -> str:
    return " ".join(
        word[:1].upper() + word[1:] if word else word
        for word in normalized_item.split()
    )


def ambiguity_hint(normalized_item: str) -> str:
    return AMBIGUOUS_TERMS.get(normalized_item, "ambiguous item")
