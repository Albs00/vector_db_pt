"""
src/adapters/base.py
Interfaccia base astratta per i Category Adapters del Catalogo Puglia Termica.
Ogni categoria di prodotto incapsula la propria semantica, definendo:
- Valutazione della confidenza di dominio (con brand come weak prior)
- Definizione dei nomi e della semantica degli slot_id per CandidatePoolManager
- Estrazione di attributi tecnici di query e regole di compatibilità tipizzate
- Provenienza ed evidenza delle relazioni
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from src.core.relation_types import TypedRelation


class BaseCategoryAdapter(ABC):
    """
    Interfaccia astratta per gli adapter di categoria.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificativo del dominio (es. 'CLIMA', 'BOILER', 'DEFAULT')."""
        pass

    @abstractmethod
    def evaluate_domain_confidence(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        """
        Valuta la confidenza (0.0 a 1.0) che la query appartenga a questa categoria,
        restituendo la lista delle evidenze (es. ['exact_token_ac_master', 'keyword_monosplit']).
        Il brand rilevato deve essere trattato ESCLUSIVAMENTE come weak prior (peso <= 0.15).
        """
        pass

    @abstractmethod
    def get_category_filter(self) -> Optional[str]:
        """Restituisce il valore di category_root per il filtraggio a catalogo."""
        pass

    @abstractmethod
    def filter_candidate(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> bool:
        """
        Igiene di categoria: verifica se l'articolo è ammesso nel pool primario della categoria.
        """
        pass

    @abstractmethod
    def extract_query_context(self, query: str) -> Dict[str, Any]:
        """
        Estrae parametri, vincoli e attributi specifici della query.
        """
        pass

    @abstractmethod
    def assign_slot(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        """
        Assegna un identificatore di slot (slot_id) completamente definito dall'adapter.
        Esempi: 'slot_ue', 'slot_ui_9000', 'slot_boiler', 'slot_flue_kit', 'slot_accessory'.
        """
        pass

    @abstractmethod
    def compute_domain_boost(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        """
        Calcola il boost per attributi tecnici specifici di dominio all'interno del proprio tier.
        """
        pass

    @abstractmethod
    def expand_relations(
        self,
        anchor_items: List[Dict[str, Any]],
        lookup_dict: Dict[str, Any]
    ) -> List[TypedRelation]:
        """
        Genera le relazioni tipizzate preservando provenienza ed evidenza certificata.
        """
        pass

    @abstractmethod
    def get_slot_quotas(self, query_context: Dict[str, Any], limit: int) -> List[Tuple[str, int]]:
        """
        Definisce le quote per ciascun slot_id nell'assemblaggio finale.
        """
        pass

    @abstractmethod
    def enrich_item(self, item: Dict[str, Any]) -> None:
        """
        Arricchisce l'articolo con attributi e metadati di categoria.
        """
        pass

    def select_ui_anchors(
        self,
        candidates: Any,
        query_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Seleziona candidati unità interna con forte evidenza identitaria da utilizzare
        come anchor per espansione inversa (UI -> UE) se nessuna UE anchor è presente.
        """
        return []

