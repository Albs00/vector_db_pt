"""
src/adapters/default.py
Adapter generico di default per categorie non specializzate.
"""

from typing import Dict, Any, List, Optional, Tuple
from src.adapters.base import BaseCategoryAdapter
from src.core.relation_types import TypedRelation


class DefaultCategoryAdapter(BaseCategoryAdapter):
    """
    Adapter di fallback generico.
    """

    @property
    def name(self) -> str:
        return "DEFAULT"

    def evaluate_domain_confidence(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        return 0.1, ["default_fallback"]

    def get_category_filter(self) -> Optional[str]:
        return None

    def filter_candidate(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> bool:
        return True

    def extract_query_context(self, query: str) -> Dict[str, Any]:
        return {"is_machine_query": False}

    def assign_slot(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        if item.get("is_accessory"):
            return "slot_accessory"
        return "slot_general"

    def compute_domain_boost(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        return 0.0

    def expand_relations(
        self,
        anchor_items: List[Dict[str, Any]],
        lookup_dict: Dict[str, Any],
        query_context: Optional[Dict[str, Any]] = None
    ) -> List[TypedRelation]:
        return []

    def get_slot_quotas(self, query_context: Dict[str, Any], limit: int) -> List[Tuple[str, int]]:
        return [("slot_general", limit)]

    def enrich_item(self, item: Dict[str, Any]) -> None:
        pass
