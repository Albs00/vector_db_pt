"""Deterministic post-identification lookup for climate component relations.

This index is deliberately separate from UI/UE compatibility.  It never uses
embeddings, semantic similarity, or query keywords: a caller must first supply
an identified product PT, table context, or exact catalog family context.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


ROLE_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", re.I)
TRAILING_ROLE_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_product_model(value: Any) -> str:
    """Normalize an exact catalog model label without fuzzy matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = ROLE_PREFIX_RE.sub("", text.strip())
    text = TRAILING_ROLE_SUFFIX_RE.sub("", text)
    return re.sub(r"[^A-Z0-9]", "", text.upper())


class ClimateComponentRelationIndex:
    """Read-only index over the approved V3.4 Safe Preview dataset."""

    SOURCE_NAME = "catalog_component_relations_v3_4"

    def __init__(self, relations_path: str | Path, table_context_path: str | Path):
        self.relations_path = Path(relations_path)
        self.table_context_path = Path(table_context_path)
        self._relations: list[Dict[str, Any]] = []
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._by_table: dict[str, list[Dict[str, Any]]] = defaultdict(list)
        self._by_family: dict[str, list[Dict[str, Any]]] = defaultdict(list)
        self._load()

    def _load(self) -> None:
        if self.relations_path.exists():
            with self.relations_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self._relations = [
                dict(record) for record in raw
                if record.get("product_domain") == "AIR_AIR_CLIMATE"
            ]
        if self.table_context_path.exists():
            with self.table_context_path.open("r", encoding="utf-8") as handle:
                raw_context = json.load(handle)
            self._contexts = {
                str(code): dict(context) for code, context in raw_context.items()
            }
        for record in self._relations:
            table_id = str(record.get("product_table_id") or record.get("table_id") or "")
            family_key = str(record.get("product_context", {}).get("family_key") or "")
            if table_id:
                self._by_table[table_id].append(record)
            if family_key:
                self._by_family[family_key].append(record)

    @staticmethod
    def _context_variants(context: Dict[str, Any]) -> list[Dict[str, Any]]:
        variants = [dict(context)]
        base_model = context.get("model") or context.get("mpn")
        base_family = context.get("family_key")
        for alternate in context.get("alternate_table_contexts") or []:
            item = dict(alternate)
            item.setdefault("model", base_model)
            item.setdefault("mpn", context.get("mpn"))
            item.setdefault("family_key", base_family)
            variants.append(item)
        return variants

    @staticmethod
    def _product_role(product: Dict[str, Any]) -> str:
        if product.get("is_ui") or str(product.get("role") or "").upper() == "UI":
            return "UI"
        if product.get("is_ue") or str(product.get("role") or "").upper() == "UE":
            return "UE"
        model = str(product.get("model") or product.get("mfg_code") or "")
        if re.match(r"^\s*U\s*[.]?\s*I\s*[.]?", model, re.I):
            return "UI"
        if re.match(r"^\s*U\s*[.]?\s*E\s*[.]?", model, re.I):
            return "UE"
        return "UNKNOWN"

    @staticmethod
    def _target_allows_role(record: Dict[str, Any], role: str) -> bool:
        target = str(record.get("attachment_target") or "UNKNOWN")
        if role == "UI":
            return target in {"UI", "CASSETTE_UI", "SYSTEM", "UNKNOWN"}
        if role == "UE":
            return target in {"UE", "SYSTEM", "UNKNOWN"}
        return True

    @staticmethod
    def _record_matches_model(record: Dict[str, Any], models: Iterable[Any]) -> bool:
        scope = str(record.get("scope_type") or "UNKNOWN")
        if scope == "UNKNOWN":
            return False
        requested = {
            normalize_product_model(model) for model in models
            if normalize_product_model(model)
        }
        applies = {
            normalize_product_model(model)
            for model in record.get("applies_to_models") or []
            if normalize_product_model(model)
        }
        if not requested:
            return scope == "TABLE_WIDE"
        if applies:
            return bool(requested.intersection(applies))
        return scope == "TABLE_WIDE"

    def _records_for_contexts(
        self,
        contexts: Iterable[Dict[str, Any]],
        role: str,
        strategy: str,
        product: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        found: list[Dict[str, Any]] = []
        for context in contexts:
            table_id = str(context.get("table_id") or "")
            family_key = str(context.get("family_key") or "")
            model_values = [
                context.get("model"), context.get("mpn"), product.get("model"),
                product.get("catalog_model"), product.get("mfg_code"),
            ]
            if strategy in {"EXACT_PRODUCT_PT", "TABLE_ID"}:
                candidates = self._by_table.get(table_id, [])
            else:
                candidates = self._by_family.get(family_key, [])
            for record in candidates:
                if not self._target_allows_role(record, role):
                    continue
                if not self._record_matches_model(record, model_values):
                    continue
                found.append(self._format_match(record, product, context, strategy))
        return found

    def _format_match(
        self,
        record: Dict[str, Any],
        product: Dict[str, Any],
        context: Dict[str, Any],
        strategy: str,
    ) -> Dict[str, Any]:
        relation = copy.deepcopy(record)
        matched_models = {
            normalize_product_model(value): str(value)
            for value in (
                context.get("model"), context.get("mpn"), product.get("model"),
                product.get("catalog_model"), product.get("mfg_code"),
            )
            if normalize_product_model(value)
        }
        source_applies = list(record.get("applies_to_models") or [])
        resolved_applies = [
            model for model in source_applies
            if normalize_product_model(model) in matched_models
        ]
        relation["source_applies_to_models"] = source_applies
        if resolved_applies:
            relation["applies_to_models"] = resolved_applies
            for accessory in relation.get("accessories") or []:
                accessory["source_applies_to_models"] = list(
                    accessory.get("applies_to_models") or source_applies
                )
                accessory["applies_to_models"] = list(resolved_applies)
        relation["lookup_strategy"] = strategy
        relation["lookup_source"] = self.SOURCE_NAME
        relation["matched_product"] = {
            "pt": str(product.get("code") or "") or None,
            "mfg_code": product.get("mfg_code"),
            "name": product.get("name"),
            "role": self._product_role(product),
            "table_id": context.get("table_id") or product.get("table_id"),
            "family_key": context.get("family_key") or product.get("family_key"),
            "model": context.get("model") or product.get("model") or product.get("mfg_code"),
        }
        return relation

    @staticmethod
    def _deduplicate(matches: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
        priority = {"EXACT_PRODUCT_PT": 0, "TABLE_ID": 1, "FAMILY_PRODUCT_CONTEXT": 2}
        ordered = sorted(
            matches,
            key=lambda item: (
                priority.get(str(item.get("lookup_strategy")), 9),
                int(item.get("page") or 0),
            ),
        )
        kept: dict[tuple[Any, ...], Dict[str, Any]] = {}
        for relation in ordered:
            accessories = relation.get("accessories") or []
            if accessories:
                accessory = accessories[0]
                key = (
                    str(accessory.get("pt") or ""),
                    str(accessory.get("model") or ""),
                    relation.get("component", {}).get("relation_intent"),
                    relation.get("component", {}).get("type"),
                    relation.get("attachment_target"),
                )
            else:
                key = (
                    "NO_COMPONENT_CODE",
                    relation.get("component", {}).get("relation_intent"),
                    relation.get("component", {}).get("type"),
                    relation.get("raw_text"),
                    relation.get("attachment_target"),
                )
            if key not in kept:
                relation["source_relation_occurrences"] = [{
                    "page": relation.get("page"),
                    "table_id": relation.get("table_id"),
                    "accessory_table_id": relation.get("accessory_table_id"),
                }]
                kept[key] = relation
                continue
            occurrence = {
                "page": relation.get("page"),
                "table_id": relation.get("table_id"),
                "accessory_table_id": relation.get("accessory_table_id"),
            }
            current = kept[key].setdefault("source_relation_occurrences", [])
            if occurrence not in current:
                current.append(occurrence)
        return list(kept.values())

    def lookup_product(self, product: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Resolve relations by PT, then table, then family + exact product model."""
        code = str(product.get("code") or "").strip()
        role = self._product_role(product)
        context = self._contexts.get(code)
        if code and context:
            matches = self._records_for_contexts(
                self._context_variants(context), role, "EXACT_PRODUCT_PT", product
            )
            if matches:
                return self._deduplicate(matches)

        table_id = str(product.get("table_id") or "")
        if table_id:
            table_context = {
                "table_id": table_id,
                "family_key": product.get("family_key"),
                "model": product.get("model") or product.get("catalog_model") or product.get("mfg_code"),
                "mpn": product.get("mfg_code"),
            }
            matches = self._records_for_contexts(
                [table_context], role, "TABLE_ID", product
            )
            if matches:
                return self._deduplicate(matches)

        family_key = str(product.get("family_key") or "")
        if family_key:
            family_context = {
                "family_key": family_key,
                "model": product.get("model") or product.get("catalog_model") or product.get("mfg_code"),
                "mpn": product.get("mfg_code"),
            }
            matches = self._records_for_contexts(
                [family_context], role, "FAMILY_PRODUCT_CONTEXT", product
            )
            if matches:
                return self._deduplicate(matches)
        return []

    def lookup_family(self, family_key: Any) -> list[Dict[str, Any]]:
        """Fallback for an exactly identified family with no individual model."""
        key = str(family_key or "").strip()
        if not key:
            return []
        product = {"family_key": key, "role": "UNKNOWN"}
        matches: list[Dict[str, Any]] = []
        for record in self._by_family.get(key, []):
            if record.get("scope_type") != "TABLE_WIDE":
                continue
            context = {
                "family_key": key,
                "table_id": record.get("product_table_id") or record.get("table_id"),
            }
            matches.append(self._format_match(
                record, product, context, "FAMILY_PRODUCT_CONTEXT"
            ))
        return self._deduplicate(matches)
