"""
src/core/category_router.py
Router generico di categoria.
Principi architetturali:
1. Restituisce una lista graduata di domini/categorie candidati (ranked category candidates),
   evitando hard routing immediato e prematuro.
2. Il brand dominante è trattato esclusivamente come weak prior (influenza marginale <= 0.2).
3. Segnale primario: token esatti di catalogo che determinano la categoria anagrafica.
4. Segnale secondario: vocabolario tecnico e attributi espliciti della query.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from src.adapters.base import BaseCategoryAdapter
from src.adapters.default import DefaultCategoryAdapter


@dataclass
class DomainCandidate:
    adapter: BaseCategoryAdapter
    confidence: float
    evidence_sources: List[str]
    category_filter: Optional[str] = None


class CategoryRouter:
    """
    Router modulare per la classificazione e il ranking dei domini di categoria.
    """

    def __init__(self, adapters: Optional[List[BaseCategoryAdapter]] = None):
        self._adapters: List[BaseCategoryAdapter] = list(adapters or [])
        self._default_adapter = DefaultCategoryAdapter()

    def register_adapter(self, adapter: BaseCategoryAdapter) -> None:
        self._adapters.append(adapter)

    def rank_domains(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> List[DomainCandidate]:
        """
        Restituisce l'elenco ordinato di tutti i domini candidati con il relativo grado di confidenza.
        """
        candidates: List[DomainCandidate] = []

        for adapter in self._adapters:
            conf, evidence = adapter.evaluate_domain_confidence(query, exact_items, detected_brand)
            if conf > 0.15:
                candidates.append(DomainCandidate(
                    adapter=adapter,
                    confidence=conf,
                    evidence_sources=evidence,
                    category_filter=adapter.get_category_filter()
                ))

        candidates.sort(key=lambda c: c.confidence, reverse=True)

        if not candidates:
            candidates.append(DomainCandidate(
                adapter=self._default_adapter,
                confidence=0.1,
                evidence_sources=["fallback_default"],
                category_filter=None
            ))

        return candidates

    def route(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> BaseCategoryAdapter:
        """
        Restituisce l'adapter primario (il top-ranked domain candidate).
        Garantisce retrocompatibilità con chiamate standard.
        """
        ranked = self.rank_domains(query, exact_items, detected_brand)
        return ranked[0].adapter
