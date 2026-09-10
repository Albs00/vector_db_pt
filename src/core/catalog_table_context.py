"""Commercial-family context derived from PDF table layout.

The catalog family is authoritative only when it comes from ``PDF_LAYOUT``.
The display value is never rewritten; normalization is limited to the matcher
key ``BRAND_CATALOG_FAMILY``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def normalize_family_key_part(value: Any) -> str:
    """Return a stable ASCII key component without changing display values."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("+", " PLUS ")
    cleaned = NON_ALNUM_RE.sub("_", text.upper()).strip("_")
    cleaned = cleaned.replace("SOFFI_TTO", "SOFFITTO")
    return cleaned


def make_family_key(brand: Any, catalog_family: Any) -> str:
    brand_key = normalize_family_key_part(brand)
    family_key = normalize_family_key_part(catalog_family)
    if not brand_key or not family_key:
        return ""
    return f"{brand_key}_{family_key}"


class CatalogTableContextIndex:
    """In-memory index used to enrich every search candidate by PT code."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._families_by_brand: Dict[str, list[str]] = {}
        self._codes_by_family_key: Dict[str, list[str]] = {}
        if self.path and self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self._contexts = {str(code): dict(value) for code, value in raw.items()}
            self._build_family_vocabulary()

    def _build_family_vocabulary(self) -> None:
        grouped: Dict[str, set[str]] = {}
        codes_by_key: Dict[str, set[str]] = {}
        for code, context in self._contexts.items():
            brand = normalize_family_key_part(context.get("brand"))
            if not brand:
                continue
            families = grouped.setdefault(brand, set())
            family = str(context.get("catalog_family") or "").strip()
            if family:
                families.add(family)
                norm_f = family.replace("SOFFI TTO", "SOFFITTO")
                if norm_f != family:
                    families.add(norm_f)
                key = str(context.get("family_key") or make_family_key(context.get("brand"), family))
                if key:
                    codes_by_key.setdefault(key, set()).add(code)
                    canon_key = key.replace("SOFFI_TTO", "SOFFITTO")
                    if canon_key != key:
                        codes_by_key.setdefault(canon_key, set()).add(code)
            for alternate in context.get("alternate_table_contexts") or []:
                alt_family = str(alternate.get("catalog_family") or "").strip()
                if alt_family:
                    families.add(alt_family)
                    norm_af = alt_family.replace("SOFFI TTO", "SOFFITTO")
                    if norm_af != alt_family:
                        families.add(norm_af)
                    alt_key = str(
                        alternate.get("family_key")
                        or make_family_key(context.get("brand"), alt_family)
                    )
                    if alt_key:
                        codes_by_key.setdefault(alt_key, set()).add(code)
                        canon_alt_key = alt_key.replace("SOFFI_TTO", "SOFFITTO")
                        if canon_alt_key != alt_key:
                            codes_by_key.setdefault(canon_alt_key, set()).add(code)
        self._families_by_brand = {
            brand: sorted(values, key=lambda value: (len(value), value), reverse=True)
            for brand, values in grouped.items()
        }
        self._codes_by_family_key = {
            key: sorted(codes) for key, codes in codes_by_key.items()
        }

    def __len__(self) -> int:
        return len(self._contexts)

    def get(self, code: Any) -> Optional[Dict[str, Any]]:
        return self._contexts.get(str(code or "").strip())

    def codes_for_family_key(self, family_key: Any) -> list[str]:
        return list(self._codes_by_family_key.get(str(family_key or "").strip(), []))

    @staticmethod
    def _context_payload(context: Dict[str, Any]) -> Dict[str, Any]:
        fields = (
            "brand",
            "catalog_family",
            "family_key",
            "table_title",
            "table_id",
            "page",
            "section_title",
            "source",
            "confidence",
            "family_conflict",
            "multiple_table_families",
            "alternate_table_contexts",
        )
        return {field: context.get(field) for field in fields if field in context}

    def enrich_item(self, item: Dict[str, Any]) -> None:
        """Apply PDF context first and never let lower-priority fields replace it."""
        code = str(item.get("code") or "").strip()
        context = self.get(code)
        if context:
            # The dedicated dataset is the source of truth, including over any
            # values already serialized in LanceDB.
            item["catalog_family"] = context.get("catalog_family")
            item["family_key"] = context.get("family_key")
            item["table_title"] = context.get("table_title")
            item["table_id"] = context.get("table_id")
            item["table_page"] = context.get("page")
            item["table_section_title"] = context.get("section_title")
            item["table_source"] = context.get("source") or "PDF_LAYOUT"
            item["table_confidence"] = context.get("confidence")
            item["table_context"] = self._context_payload(context)
            item["_catalog_family_priority"] = 1
            return

        # LanceDB carries the same context columns. This path keeps search
        # results useful if the JSON sidecar is temporarily unavailable.
        if item.get("table_source") == "PDF_LAYOUT" and item.get("catalog_family"):
            item["family_key"] = item.get("family_key") or make_family_key(
                item.get("brand"), item.get("catalog_family")
            )
            item["table_context"] = {
                "brand": item.get("brand"),
                "catalog_family": item.get("catalog_family"),
                "family_key": item.get("family_key"),
                "table_title": item.get("table_title"),
                "table_id": item.get("table_id"),
                "page": item.get("table_page"),
                "section_title": item.get("table_section_title"),
                "source": "PDF_LAYOUT",
                "confidence": item.get("table_confidence"),
            }
            item["_catalog_family_priority"] = 1

    def apply_family_fallback(
        self,
        item: Dict[str, Any],
        catalog_family: Any,
        source: str,
        priority: int,
    ) -> None:
        """Fill a missing family while enforcing the declared source priority."""
        family = str(catalog_family or "").strip()
        if not family:
            return
        current_priority = int(item.get("_catalog_family_priority") or 999)
        if item.get("catalog_family") and current_priority <= priority:
            return
        item["catalog_family"] = family
        item["family_key"] = make_family_key(item.get("brand"), family)
        item["table_source"] = source
        item["_catalog_family_priority"] = priority

    def analyze_query(
        self,
        query: str,
        requested_brand: Any,
        fallback_family: Any = None,
    ) -> Dict[str, Optional[str]]:
        """Extract a brand-scoped family request matching only real catalog families."""
        brand_key = normalize_family_key_part(requested_brand)
        query_key = normalize_family_key_part(query)
        detected: Optional[str] = None
        detected_key: Optional[str] = None

        if brand_key and query_key:
            padded_query = f"_{query_key}_"
            for family in self._families_by_brand.get(brand_key, []):
                family_part = normalize_family_key_part(family)
                if not family_part:
                    continue

                # Check 1: Direct substring match (e.g. ASTRA, SIDERA, ELEGANCE, EXPERT_NERO, EXPERT)
                if f"_{family_part}_" in padded_query:
                    detected = family
                    detected_key = make_family_key(requested_brand, family)
                    break

                # Check 2: Italian inflection (e.g. CANALIZZATA <-> CANALIZZATO, CASSETTA <-> CASSETTE)
                matched_inflection = False
                if len(family_part) >= 5 and family_part[-1] in ('A', 'O', 'E', 'I'):
                    stem = family_part[:-1]
                    if any(f"_{stem}{v}_" in padded_query for v in ('A', 'O', 'E', 'I')):
                        detected = family
                        detected_key = make_family_key(requested_brand, family)
                        matched_inflection = True
                        break
                if matched_inflection:
                    break

                # Check 3: Compound multi-word locutions (e.g. PAVIMENTO/SOFFITTO vs SOFFITTO/PAVIMENTO)
                words = [w for w in family_part.split("_") if len(w) >= 3]
                if len(words) == 2:
                    # Check permutations (e.g. SOFFITTO_PAVIMENTO <-> PAVIMENTO_SOFFITTO)
                    rev_part = f"{words[1]}_{words[0]}"
                    if f"_{rev_part}_" in padded_query:
                        detected = family
                        detected_key = make_family_key(requested_brand, family)
                        break
                    # Permutations with inflections
                    w0_stem = words[0][:-1] if len(words[0]) >= 5 and words[0][-1] in ('A', 'O', 'E', 'I') else words[0]
                    w1_stem = words[1][:-1] if len(words[1]) >= 5 and words[1][-1] in ('A', 'O', 'E', 'I') else words[1]
                    if any(f"_{w1_stem}{v1}_{w0_stem}{v0}_" in padded_query for v0 in ('A', 'O', 'E', 'I', '') for v1 in ('A', 'O', 'E', 'I', '')):
                        detected = family
                        detected_key = make_family_key(requested_brand, family)
                        break
                elif len(words) > 2:
                    if all(f"_{w}_" in padded_query for w in words):
                        detected = family
                        detected_key = make_family_key(requested_brand, family)
                        break

        # Strictly verify against catalog_table_context - NEVER invent synthetic families
        final_family_key = None
        if detected_key:
            if detected_key in self._codes_by_family_key:
                final_family_key = detected_key
            elif detected_key.replace("SOFFI_TTO", "SOFFITTO") in self._codes_by_family_key:
                final_family_key = detected_key.replace("SOFFI_TTO", "SOFFITTO")
            elif detected_key.replace("SOFFITTO", "SOFFI_TTO") in self._codes_by_family_key:
                final_family_key = detected_key.replace("SOFFITTO", "SOFFI_TTO")

        if not final_family_key:
            detected = None

        return {
            "requested_brand": str(requested_brand).strip().upper() if requested_brand else None,
            "requested_family": detected,
            "requested_family_key": final_family_key,
        }

    @staticmethod
    def _family_key_aliases(key: Any) -> set[str]:
        value = str(key or "").strip()
        if not value:
            return set()
        aliases = {value}
        if "SOFFI_TTO" in value:
            aliases.add(value.replace("SOFFI_TTO", "SOFFITTO"))
        if "SOFFITTO" in value:
            aliases.add(value.replace("SOFFITTO", "SOFFI_TTO"))
        return aliases

    @classmethod
    def candidate_family_contexts(cls, item: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Return the primary context plus every explicitly valid alternate.

        The primary fields remain untouched.  A missing alternate ``family_key``
        is derived only for matching, using the alternate family and the catalog
        brand; this does not promote that alternate to primary.
        """
        table_context = item.get("table_context") or {}
        fallback_brand = table_context.get("brand") or item.get("brand")
        raw_contexts: list[Dict[str, Any]] = [table_context or item]
        for source in (table_context, item):
            for alternate in source.get("alternate_table_contexts") or []:
                if isinstance(alternate, dict):
                    raw_contexts.append(alternate)

        contexts: list[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for raw in raw_contexts:
            key = str(raw.get("family_key") or "").strip()
            if not key:
                key = make_family_key(
                    raw.get("brand") or fallback_brand,
                    raw.get("catalog_family"),
                )
            if not key:
                continue
            identity = (
                key,
                str(raw.get("table_id") or ""),
                str(raw.get("page") or ""),
            )
            if identity in seen:
                continue
            seen.add(identity)
            context = dict(raw)
            context["family_key"] = key
            contexts.append(context)
        return contexts

    @classmethod
    def candidate_family_keys(cls, item: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        for context in cls.candidate_family_contexts(item):
            keys.update(cls._family_key_aliases(context.get("family_key")))
        return keys

    @classmethod
    def matching_family_context(
        cls, item: Dict[str, Any], requested_family_key: Any
    ) -> Optional[Dict[str, Any]]:
        requested = str(requested_family_key or "").strip()
        if not requested:
            return None
        for context in cls.candidate_family_contexts(item):
            if requested in cls._family_key_aliases(context.get("family_key")):
                return context
        return None
