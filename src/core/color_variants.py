"""Centralized, non-destructive color and named-variant normalization."""

import re
from typing import Any, Dict, Iterable, Optional


COLOR_ALIASES = {
    "WHITE": {"BIANCO", "BIANCA", "WHITE", "BCO"},
    "BLACK": {"NERO", "NERA", "BLACK", "NRO"},
    "SILVER": {"ARGENTO", "SILVER"},
    "RED": {"ROSSO", "ROSSA", "RED"},
    "GREY": {"GRIGIO", "GRIGIA", "GRAY", "GREY"},
}

_ALIAS_TO_BASE = {
    alias: base for base, aliases in COLOR_ALIASES.items() for alias in aliases
}
_COLOR_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _ALIAS_TO_BASE), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_NAMED_VARIANT_PATTERN = re.compile(
    r"\b(PEARL|RUBY|ONYX)\s+(" +
    "|".join(sorted(map(re.escape, _ALIAS_TO_BASE), key=len, reverse=True)) +
    r")\b",
    re.IGNORECASE,
)
_VARIANT_WORD_PATTERN = re.compile(
    r"\b(?:PEARL|RUBY|ONYX|PERLA|RUBINO|ONICE|"
    + "|".join(sorted(map(re.escape, _ALIAS_TO_BASE), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


def _text_values(values: Iterable[Any]):
    for value in values:
        if isinstance(value, str) and value.strip():
            yield " ".join(value.upper().split())


def normalize_color_variant(*values: Any) -> Dict[str, Optional[str]]:
    """Return canonical color_base while preserving a meaningful full variant."""
    texts = list(_text_values(values))
    for text in texts:
        named = _NAMED_VARIANT_PATTERN.search(text)
        if named:
            alias = named.group(2).upper()
            base = _ALIAS_TO_BASE[alias]
            return {"color_base": base, "variant_full": f"{named.group(1).upper()} {base}"}
    for text in texts:
        match = _COLOR_PATTERN.search(text)
        if match:
            base = _ALIAS_TO_BASE[match.group(1).upper()]
            return {"color_base": base, "variant_full": base}
    return {"color_base": None, "variant_full": None}


def candidate_color_variant(item: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Inspect explicit variant metadata first, then family and product text."""
    return normalize_color_variant(
        item.get("variant_full"), item.get("variant"), item.get("variante"),
        item.get("color"), item.get("colore"), item.get("finish"), item.get("finitura"),
        item.get("name"), item.get("famiglia_catalogo"), item.get("catalog_family"),
        item.get("serie"), item.get("table_title"),
    )


def color_neutral_variant_key(item: Dict[str, Any]) -> Optional[str]:
    """Return a family/series key with only color wording removed."""
    for field in (
        "family_key", "catalog_family", "famiglia_catalogo", "serie", "table_title"
    ):
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        neutral = re.sub(r"[^A-Z0-9]+", " ", value.upper())
        neutral = _VARIANT_WORD_PATTERN.sub(" ", neutral)
        neutral = " ".join(neutral.split())
        if neutral:
            return neutral
    return None
