"""
src/core/relation_types.py
Definisce le relazioni tipizzate standard tra componenti di catalogo:
- COMPATIBLE_WITH: componente compatibile funzionalmente (es. UI <-> UE nel clima).
  NOTA: COMPATIBLE_WITH inietta candidati nel pool per il retrieval ma NON certifica
  né implica l'inclusione automatica nella BOM finale.
- PAIRED_WITH: abbinamento diretto 1-a-1 certificato (es. monosplit dedicato).
- REQUIRES: componente obbligatorio indispensabile certificato (es. kit scarico fumi).
- INCLUDES: componente incluso in un pacchetto/kit preconfigurato certificato.
- KIT_COMPONENT: componente appartenente a un kit certificato.
- REVISION_OF: revisione generazionale documentata nell'anagrafica/dataset.
- ACCESSORY_FOR: accessorio opzionale certificato.

Ogni relazione deve conservare rigorosamente:
- source_code
- target_code
- relation_type
- provenance (origine del dato, es. 'climatizzatori_compatibilita_master.json')
- evidence (dettagli di abbinamento, tabelle combinazioni, ecc.)
- confidence (confidenza dell'evidenza)

Il core non inventa relazioni REQUIRES/INCLUDES/REVISION_OF se non certificate dalla provenienza.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


class RelationType(str, Enum):
    PAIRED_WITH_VERIFIED = "PAIRED_WITH_VERIFIED"
    PAIRED_WITH_DERIVED = "PAIRED_WITH_DERIVED"
    PAIRED_WITH = "PAIRED_WITH"  # Retro-compatibilità
    COMPATIBLE_WITH = "COMPATIBLE_WITH"
    REQUIRES = "REQUIRES"
    INCLUDES = "INCLUDES"
    KIT_COMPONENT = "KIT_COMPONENT"
    REVISION_OF = "REVISION_OF"
    ACCESSORY_FOR = "ACCESSORY_FOR"


@dataclass
class TypedRelation:
    source_code: str
    target_code: str
    relation_type: RelationType
    provenance: str
    target_mfg_code: Optional[str] = None
    target_role: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_code": self.source_code,
            "target_code": self.target_code,
            "relation_type": self.relation_type.value if hasattr(self.relation_type, "value") else str(self.relation_type),
            "provenance": self.provenance,
            "target_mfg_code": self.target_mfg_code,
            "target_role": self.target_role,
            "evidence": self.evidence,
            "confidence": self.confidence
        }


class TypedRelationExpander:
    """
    Gestore generico di espansione relazioni tipizzate con conservazione di provenienza ed evidenza.
    """

    def __init__(self):
        self._relations_by_source: Dict[str, List[TypedRelation]] = {}

    def register_relation(self, relation: TypedRelation) -> None:
        src = str(relation.source_code).strip()
        if src not in self._relations_by_source:
            self._relations_by_source[src] = []
        self._relations_by_source[src].append(relation)

    def get_relations_for(self, source_code: str, relation_type: Optional[RelationType] = None) -> List[TypedRelation]:
        src = str(source_code).strip()
        rels = self._relations_by_source.get(src, [])
        if relation_type is not None:
            return [r for r in rels if r.relation_type == relation_type]
        return rels

    def expand_candidate_pool(
        self,
        anchor_codes: List[str],
        lookup_dict: Dict[str, Any],
        merged_candidates: Dict[str, Dict[str, Any]],
        allowed_relation_types: Optional[List[RelationType]] = None,
        max_expansions_per_anchor: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Espande il pool dei candidati a partire dai codici anchor forniti.
        Inietta candidati marcati come '_is_relation_candidate = True',
        conservando provenienza ed evidenza per il reranker e il validation engine.
        Ordina per priorità strutturale di relazione (PAIRED_WITH_VERIFIED > PAIRED_WITH_DERIVED > COMPATIBLE_WITH)
        e per confidenza decrescente prima dell'eventuale cap di sicurezza.
        """
        def _rel_priority(rel: TypedRelation) -> Tuple[int, float]:
            rt = rel.relation_type
            if rt == RelationType.PAIRED_WITH_VERIFIED or rt == RelationType.PAIRED_WITH:
                prio = 1
            elif rt == RelationType.PAIRED_WITH_DERIVED:
                prio = 2
            elif rt in (RelationType.REQUIRES, RelationType.INCLUDES, RelationType.KIT_COMPONENT):
                prio = 3
            else:
                prio = 4
            return (prio, -float(rel.confidence or 0.0))

        expanded = []
        for anchor in anchor_codes:
            rels = self.get_relations_for(anchor)
            if allowed_relation_types:
                rels = [r for r in rels if r.relation_type in allowed_relation_types]

            # Ordina le relazioni per priorità e confidenza (mai per indice casuale)
            sorted_rels = sorted(rels, key=_rel_priority)

            count = 0
            for r in sorted_rels:
                if max_expansions_per_anchor is not None and count >= max_expansions_per_anchor:
                    break
                tgt_code = r.target_code
                if tgt_code not in merged_candidates:
                    tgt_item = lookup_dict.get(tgt_code)
                    if tgt_item:
                        item_copy = dict(tgt_item)
                        item_copy["_is_relation_candidate"] = True
                        item_copy["_relation_type"] = r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type)
                        item_copy["_relation_source"] = anchor
                        item_copy["_relation_provenance"] = r.provenance
                        item_copy["_relation_evidence"] = r.evidence
                        item_copy["_relation_confidence"] = r.confidence
                        if r.target_role:
                            item_copy["_inferred_role"] = r.target_role
                        merged_candidates[tgt_code] = item_copy
                        expanded.append(item_copy)
                        count += 1
        return expanded
