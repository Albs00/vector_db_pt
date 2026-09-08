"""
src/core/candidate_pool.py
Gestore di pool di candidati completamente SLOT-AGNOSTIC.
Principi architetturali:
- Struttura interna: candidate_pools[slot_id].
- Il core non conosce ruoli specifici (es. UI, UE, Caldaia, Fumi, ecc.).
- I nomi e la semantica degli slot_id sono definiti ESCLUSIVAMENTE dai CategoryAdapter.
- Supporta l'ordinamento strutturale per Evidence Tiers:
    (evidence_tier, -tier_score)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set, Tuple, Union
import collections


@dataclass
class SlotConfig:
    """
    Configurazione generica di uno slot per l'interleaving dei candidati.
    Totalmente agnostica rispetto alla categoria merceologica.
    """
    slot_id: str
    priority: int = 0          # Priorità per la riserva in testa (valori più alti esaminati prima)
    min_reserved: int = 0      # Numero minimo di candidati qualificati riservati in testa
    max_candidates: int = 20   # Quota massima di candidati ammessi dal round-robin per questo slot

    def __iter__(self):
        """Permette l'unpacking (slot_id, max_candidates) per retrocompatibilità."""
        yield self.slot_id
        yield self.max_candidates


class CandidatePoolManager:
    """
    Gestore slot-agnostic di pool di candidati indicizzati per slot_id.
    """

    def __init__(self):
        # candidate_pools[slot_id] -> List[Dict[str, Any]]
        self._pools: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self._codes_by_slot: Dict[str, Set[str]] = collections.defaultdict(set)

    def add_candidate(self, slot_id: str, item: Dict[str, Any]) -> None:
        """Aggiunge un candidato a un determinato slot_id."""
        code = str(item.get("code") or "").strip()
        if code and code in self._codes_by_slot[slot_id]:
            return
        if code:
            self._codes_by_slot[slot_id].add(code)
        self._pools[slot_id].append(item)

    def get_pool(self, slot_id: str) -> List[Dict[str, Any]]:
        """Restituisce la lista di candidati associati allo slot_id."""
        return self._pools.get(slot_id, [])

    def get_all_slots(self) -> List[str]:
        """Restituisce tutti gli slot_id correntemente registrati."""
        return list(self._pools.keys())

    def sort_pools(self) -> None:
        """
        Ordina ciascun pool applicando la precedenza strutturale degli Evidence Tiers:
        1. _evidence_tier (crescente: 1 prima di 5)
        2. -_tier_score (decrescente: punteggi più alti prima all'interno dello stesso tier)
        Preserva l'ordine naturale di inserimento come terzo criterio stabile.
        """
        for slot_id, pool in self._pools.items():
            pool.sort(
                key=lambda x: (
                    x.get("_evidence_tier", 5),
                    -x.get("_tier_score", 0.0)
                )
            )

    def get_slot_rank(self, slot_id: str, code: str) -> Optional[int]:
        """Restituisce la posizione 1-based del codice nel pool dello slot specificato."""
        pool = self.get_pool(slot_id)
        for idx, item in enumerate(pool, start=1):
            if str(item.get("code")) == str(code):
                return idx
        return None

    def get_all_pools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Restituisce una copia del dizionario dei pool ordinati per ciascun slot_id."""
        self.sort_pools()
        return {slot: list(pool) for slot, pool in self._pools.items()}

    def interleave(
        self,
        slot_quotas: Union[List[SlotConfig], List[Tuple[str, int]]],
        fallback_slots: Optional[List[str]] = None,
        total_limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Assembla l'output finale in modo totalmente generico:
        1. Riserva posizioni in testa per slot con min_reserved > 0 ordinati per priority decrescente.
           Regola fondamentale: NON riserva candidati NEAR_MODEL_CANDIDATE.
        2. Round-robin ciclico tra gli slot richiesti fino alla rispettiva quota max_candidates.
        3. Drenaggio dei residui da fallback_slots o da tutti i pool ordinati fino a total_limit.
        """
        self.sort_pools()
        final_list: List[Dict[str, Any]] = []
        seen_codes: Set[str] = set()

        def add_if_unique(it: Dict[str, Any]) -> bool:
            c = str(it.get("code") or "")
            if c and c not in seen_codes:
                seen_codes.add(c)
                final_list.append(it)
                return True
            return False

        # Normalizza le quote in istanze SlotConfig
        normalized_configs: List[SlotConfig] = []
        seen_slots = set()
        for item in slot_quotas:
            if isinstance(item, SlotConfig):
                cfg = item
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                cfg = SlotConfig(slot_id=str(item[0]), max_candidates=int(item[1]))
            else:
                continue
            if cfg.slot_id not in seen_slots:
                seen_slots.add(cfg.slot_id)
                normalized_configs.append(cfg)

        # 1. Riserva garantita in testa per slot ad alta priorità (min_reserved > 0)
        # Esclude espressamente candidati NEAR_MODEL_CANDIDATE dalla riserva
        priority_slots = sorted(
            [c for c in normalized_configs if c.min_reserved > 0],
            key=lambda x: -x.priority
        )
        for cfg in priority_slots:
            pool = self.get_pool(cfg.slot_id)
            reserved_placed = 0
            for cand in pool:
                if reserved_placed >= cfg.min_reserved or len(final_list) >= total_limit:
                    break
                # Esclusione formale: i candidati near-model non possono occupare posti riservati
                is_near = (
                    cand.get("_is_near_model_candidate", False) or
                    cand.get("_exact_match_type") == "NEAR_MODEL_CANDIDATE"
                )
                if is_near:
                    continue
                if add_if_unique(cand):
                    reserved_placed += 1

        # 2. Round-Robin tra tutti gli slot specificati nelle quote
        max_rounds = max((c.max_candidates for c in normalized_configs), default=10)
        for r in range(max_rounds):
            if len(final_list) >= total_limit:
                break
            for cfg in normalized_configs:
                if len(final_list) >= total_limit:
                    break
                if r < cfg.max_candidates:
                    pool = self.get_pool(cfg.slot_id)
                    if r < len(pool):
                        add_if_unique(pool[r])

        # 3. Riempi residui fino a total_limit dai fallback_slots o da tutti i pool ordinati
        if len(final_list) < total_limit:
            slots_to_drain = fallback_slots if fallback_slots is not None else list(self._pools.keys())
            remaining_items = []
            for slot_id in slots_to_drain:
                for it in self.get_pool(slot_id):
                    c = str(it.get("code") or "")
                    if c not in seen_codes:
                        remaining_items.append(it)

            # Ordina i rimanenti per evidence tier e tier score
            remaining_items.sort(
                key=lambda x: (
                    x.get("_evidence_tier", 5),
                    -x.get("_tier_score", 0.0)
                )
            )
            for it in remaining_items:
                if len(final_list) >= total_limit:
                    break
                add_if_unique(it)

        return final_list[:total_limit]
