"""
src/adapters/boiler.py
Category Adapter per il dominio Caldaie e Riscaldamento.
Predisposizione generica:
- Slot IDs: 'slot_boiler', 'slot_flue_kit', 'slot_template', 'slot_thermostat', 'slot_accessory', 'slot_boiler_general'
- Relazioni: REQUIRES (es. kit fumi), con provenienza ed evidenza certificata
- Valutazione confidenza con brand come weak prior
"""

import re
import os
import json
from typing import Dict, Any, List, Optional, Tuple

from src.adapters.base import BaseCategoryAdapter
from src.core.relation_types import TypedRelation, RelationType

BOILER_KEYWORDS = [
    'caldaia', 'caldaie', 'condensazione', 'camera stagna', 'camera aperta',
    'modulo termico', 'gruppo termico', 'generatore calore'
]


class BoilerCategoryAdapter(BaseCategoryAdapter):
    """
    Adapter di categoria per caldaie e riscaldamento.
    """

    def __init__(self, boiler_specs_path: Optional[str] = None):
        self._boiler_specs: Dict[str, Any] = {}
        if boiler_specs_path and os.path.exists(boiler_specs_path):
            try:
                with open(boiler_specs_path, "r", encoding="utf-8") as f:
                    self._boiler_specs = json.load(f)
            except Exception:
                pass

    @property
    def name(self) -> str:
        return "BOILER"

    def evaluate_domain_confidence(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        evidences = []
        conf = 0.0

        for it in exact_items:
            cat_r = it.get("category_root") or ""
            cat_p = it.get("category_path") or ""
            if "CALDAIE" in cat_p or "RISCALDAMENTO" in cat_r:
                conf = 0.95
                evidences.append("exact_token_category_riscaldamento")
                break

        q_low = query.lower()
        matched = [kw for kw in BOILER_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', q_low)]
        if matched:
            conf = max(conf, 0.85)
            evidences.append(f"matched_boiler_keywords:{','.join(matched[:2])}")

        if detected_brand and detected_brand.upper() in ["FERROLI", "BERETTA", "VAILLANT", "ARISTON", "BAXI", "IMMERGAS", "HERMANN SAUNIER DUVAL"]:
            conf = min(1.0, conf + 0.05)
            evidences.append("known_boiler_brand_weak_prior")

        return conf, evidences

    def get_category_filter(self) -> Optional[str]:
        return "RISCALDAMENTO"

    def filter_candidate(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> bool:
        cat_root = item.get("category_root") or (item.get("category_path") or "").split(" > ")[0].strip()
        return cat_root in ["RISCALDAMENTO", "FUMISTERIA"]

    def extract_query_context(self, query: str) -> Dict[str, Any]:
        q_u = query.upper()
        m_kw = re.search(r'\b(\d{2,3})\s*(?:KW|K)\b', q_u)
        target_kw = float(m_kw.group(1)) if m_kw else None
        is_cs = "CS" in q_u or "STAGNA" in q_u
        is_ca = "CA" in q_u or "APERTA" in q_u
        is_cond = "COND" in q_u or "CONDENSAZIONE" in q_u
        is_gpl = "GPL" in q_u
        is_met = "MET" in q_u or "METANO" in q_u

        return {
            "target_kw": target_kw,
            "is_cs": is_cs,
            "is_ca": is_ca,
            "is_cond": is_cond,
            "is_gpl": is_gpl,
            "is_met": is_met,
            "is_machine_query": True
        }

    def assign_slot(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        self.enrich_item(item)
        name = (item.get("name") or "").upper()
        cat = (item.get("category_path") or "").upper()

        if any(k in name for k in ["KIT FUMI", "KIT SCARIC", "SDOPP", "COASS"]):
            return "slot_flue_kit"
        if "DIMA" in name:
            return "slot_template"
        if "CRONOTERM" in name or "TERMOST" in name:
            return "slot_thermostat"
        if item.get("is_boiler"):
            return "slot_boiler"
        if "ACCESSORI" in cat or item.get("is_accessory"):
            return "slot_accessory"
        return "slot_boiler_general"

    def compute_domain_boost(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        self.enrich_item(item)
        boost = 0.0
        target_kw = query_context.get("target_kw")
        if target_kw and item.get("taglia_kw") and abs(item["taglia_kw"] - target_kw) < 1.0:
            boost += 25.0

        name_u = (item.get("name") or "").upper()
        if query_context.get("is_cond") and "COND" in name_u:
            boost += 10.0
        if query_context.get("is_cs") and "CS" in name_u:
            boost += 5.0
        if query_context.get("is_gpl") and "GPL" in name_u:
            boost += 5.0
        if query_context.get("is_met") and "MET" in name_u:
            boost += 5.0

        return boost

    def expand_relations(
        self,
        anchor_items: List[Dict[str, Any]],
        lookup_dict: Dict[str, Any]
    ) -> List[TypedRelation]:
        return []

    def get_slot_quotas(self, query_context: Dict[str, Any], limit: int) -> List[Tuple[str, int]]:
        return [
            ("slot_boiler", max(5, limit // 2)),
            ("slot_flue_kit", 2),
            ("slot_thermostat", 2)
        ]

    def enrich_item(self, item: Dict[str, Any]) -> None:
        if "_boiler_enriched" in item:
            return
        item["_boiler_enriched"] = True
        code = str(item.get("code") or "").strip()
        name = (item.get("name") or "").upper()

        if self._boiler_specs and code in self._boiler_specs:
            meta = self._boiler_specs[code]
            item["is_boiler"] = True
            kw_val = meta.get("kw")
            if kw_val:
                item["taglia_kw"] = kw_val
                item["tag_kw"] = f"{kw_val:g} kW"
                item["tag_kw_display"] = f"{kw_val:g} kW"
        elif any(k in name for k in ["CALD ", "CALDAIA ", "MODULO TERMICO "]):
            item["is_boiler"] = True
            m_kw = re.search(r'\b(\d{2,3})\s*(?:KW|K)\b', name)
            if m_kw:
                kw = float(m_kw.group(1))
                item["taglia_kw"] = kw
                item["tag_kw"] = f"{kw:g} kW"
                item["tag_kw_display"] = f"{kw:g} kW"
