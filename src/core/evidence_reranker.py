"""
src/core/evidence_reranker.py
Reranker generico basato su EVIDENCE TIERS (precedenza strutturale a livelli).
Gli exact match univoci hanno precedenza strutturale, non solo un bonus numerico.
Il reranking opera all'interno dei livelli di evidenza:

Livelli di Evidenza:
- TIER 1 (UNIQUE_EXACT): exact match univoco per codice PT o MPN nel proprio slot di ruolo.
- TIER 2 (AMBIGUOUS_EXACT): exact match con ambiguità tra più articoli dello stesso brand/categoria.
- TIER 3 (NEAR_MODEL_OR_STRONG): candidati NEAR_MODEL o con forte corrispondenza lessicale/attributi.
- TIER 4 (TYPED_RELATION): candidati espansi da relazioni certificate (es. COMPATIBLE_WITH).
- TIER 5 (BROAD_DISCOVERY): candidati da ricerca semantica o BM25 generica.

L'ordinamento prioritario è dato dalla tupla:
  (evidence_tier, -tier_score)
garantendo precedenza strutturale assoluta per i livelli superiori.
"""

import re
from enum import IntEnum
from typing import Dict, Any, List, Optional, Tuple

GENERIC_STOP_WORDS = {
    'climatizzatore', 'condizionatore', 'climatizzatori', 'condizionatori',
    'split', 'monosplit', 'dual', 'trial', 'quadri', 'penta', 'multisplit',
    'inverter', 'wifi', 'wi-fi', 'classe', 'gas', 'r32', 'r410a',
    'bianco', 'white', 'nero', 'black', 'silver', 'grigio',
    'incluso', 'integrato', 'con', 'per', 'del', 'della', 'serie',
    'unità', 'unita', 'interna', 'esterna', 'ui', 'ue', 'motocondensante',
    'aria', 'r32inverter', 'pompa', 'caldaia', 'scaldabagno', 'ventilconvettore',
    'fancoil', 'bollitore', 'radiatore'
}


class EvidenceTier(IntEnum):
    TIER_1_UNIQUE_EXACT = 1          # Exact PT, MPN, o unique exact catalog label
    TIER_2_AMBIGUOUS_EXACT = 2       # Exact PT/MPN o catalog label ambiguo
    TIER_3_NEAR_MODEL_OR_STRONG = 3  # Near model sintetico o prefisso/revisione
    TIER_4_TYPED_RELATION = 4        # Kit certificato PAIRED_WITH_VERIFIED da tabella PT
    TIER_5_EXACT_CATALOG_BUNDLE = 5  # Brand + Serie/Famiglia + Taglia BTU (+ eventuale Colore)
    TIER_6_STRONG_CATALOG_SPEC = 6   # Brand + Taglia BTU oppure Brand + Serie/Famiglia
    TIER_7_COMPATIBLE_RELATION = 7   # Candidati da relazione COMPATIBLE_WITH
    TIER_8_BROAD_DISCOVERY = 8       # Ricerca semantica/BM25 generica


class GenericEvidenceReranker:
    """
    Reranker generico basato su livelli strutturali di evidenza.
    """

    def assign_evidence_tier(
        self,
        item: Dict[str, Any],
        is_unique_exact: bool = True,
        query_context: Optional[Dict[str, Any]] = None
    ) -> EvidenceTier:
        """Determina il livello strutturale di evidenza del candidato."""
        if item.get("_is_exact_token_match"):
            if is_unique_exact:
                return EvidenceTier.TIER_1_UNIQUE_EXACT
            return EvidenceTier.TIER_2_AMBIGUOUS_EXACT

        if item.get("_is_near_model_candidate"):
            return EvidenceTier.TIER_3_NEAR_MODEL_OR_STRONG

        # PAIRED_WITH_VERIFIED e kit certificati ottengono precedenza strutturale Tier 4
        rel_type = item.get("_relation_type")
        if rel_type in ("PAIRED_WITH_VERIFIED", "PAIRED_WITH"):
            return EvidenceTier.TIER_4_TYPED_RELATION

        # Mismatch esplicito di serie: mai promuovere a Tier elevati
        series_match = item.get("_series_match", "none")
        if series_match == "mismatch":
            return EvidenceTier.TIER_8_BROAD_DISCOVERY

        ctx = query_context or {}
        requested_btus = ctx.get("requested_btus", [])
        target_brand = (ctx.get("detected_brand") or "").strip().upper()
        item_brand = (item.get("brand") or "").strip().upper()
        brand_match = bool(target_brand and item_brand and (target_brand == item_brand or target_brand in item_brand))

        item_btu = item.get("taglia_btu")
        capacity_match = bool(requested_btus and item_btu and item_btu in requested_btus)

        # Tier 5: Brand + Serie/Famiglia + Taglia BTU
        if brand_match and series_match in ("exact", "alias") and (not requested_btus or capacity_match):
            return EvidenceTier.TIER_5_EXACT_CATALOG_BUNDLE

        # Tier 6: Brand + Taglia BTU, oppure Brand + Serie/Famiglia
        if brand_match and (capacity_match or series_match in ("exact", "alias")):
            return EvidenceTier.TIER_6_STRONG_CATALOG_SPEC

        # Tier 7: Candidato espanso da relazione COMPATIBLE_WITH
        if item.get("_is_relation_candidate") and rel_type == "COMPATIBLE_WITH":
            return EvidenceTier.TIER_7_COMPATIBLE_RELATION

        return EvidenceTier.TIER_8_BROAD_DISCOVERY

    def compute_tier_score(
        self,
        item: Dict[str, Any],
        query_tokens: List[str],
        detected_brand: Optional[str] = None,
        domain_boost: float = 0.0,
        is_machine_query: bool = False
    ) -> float:
        """
        Calcola il punteggio di ordinamento all'interno del proprio livello di evidenza.
        """
        score = float(item.get("_relevance_score") or item.get("_score") or 0.0)
        score += domain_boost

        name_lower = (item.get("name") or "").lower()
        brand_lower = (item.get("brand") or "").lower()
        brand_tokens = set(re.findall(r"\w+", brand_lower))
        mfg_lower = (item.get("mfg_code") or "").lower()
        cat_lower = (item.get("category_path") or "").lower()

        for t in query_tokens:
            t_low = t.lower()
            if t_low in GENERIC_STOP_WORDS:
                score += 0.2
                continue

            if t_low in brand_tokens:
                score += 5.0

            if t_low in mfg_lower:
                score += 15.0
            elif t_low in name_lower:
                score += 4.0
            elif len(t_low) >= 5 and (t_low[:6] in name_lower or t_low[:5] in name_lower):
                score += 2.0

            if t_low in cat_lower:
                score += 0.5

        if detected_brand:
            item_brand = (item.get("brand") or "").strip().upper()
            if item_brand == detected_brand.strip().upper():
                score += 5.0
            elif item_brand:
                score -= 10.0

        # Relazioni tipizzate: conferiscono relation_strength e boost proporzionato
        rel_boost = 0.0
        if item.get("_is_relation_candidate"):
            rel_type = item.get("_relation_type")
            rel_conf = float(item.get("_relation_confidence") or 0.7)
            if rel_type in ("PAIRED_WITH_VERIFIED", "PAIRED_WITH"):
                rel_boost = 25.0 * rel_conf
            elif rel_type == "PAIRED_WITH_DERIVED":
                rel_boost = 20.0 * rel_conf
            elif rel_type == "COMPATIBLE_WITH":
                rel_boost = 15.0 * rel_conf
            score += rel_boost
        item["_computed_relation_boost"] = rel_boost

        # Serie e variante: boost per esatta o forte penalità per mismatch
        series_match = item.get("_series_match", "none")
        if series_match in ("exact", "alias"):
            score += 30.0
        elif series_match == "mismatch":
            score -= 50.0

        if item.get("_color_match"):
            score += 15.0
        elif item.get("_color_mismatch"):
            score -= 20.0

        if is_machine_query and item.get("is_accessory"):
            score -= 30.0

        return score

    def evaluate_candidate(
        self,
        item: Dict[str, Any],
        query_tokens: List[str],
        detected_brand: Optional[str] = None,
        domain_boost: float = 0.0,
        is_unique_exact: bool = True,
        is_machine_query: bool = False,
        query_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, float]:
        """
        Assegna il tier di evidenza e il relativo punteggio.
        Restituisce la tupla di ordinamento (tier, tier_score) separando formalmente
        Identity Evidence e Relation Evidence.
        """
        tier = self.assign_evidence_tier(
            item,
            is_unique_exact=is_unique_exact,
            query_context=query_context
        )
        tier_score = self.compute_tier_score(
            item=item,
            query_tokens=query_tokens,
            detected_brand=detected_brand,
            domain_boost=domain_boost,
            is_machine_query=is_machine_query
        )

        item["_evidence_tier"] = int(tier)
        item["_tier_score"] = tier_score

        # Separazione formale tra Identity Evidence e Relation Evidence
        item["_identity_evidence"] = {
            "tier": int(tier),
            "match_type": item.get("_exact_match_type") or ("NEAR_MODEL" if item.get("_is_near_model_candidate") else "DISCOVERY"),
            "matched_token": item.get("_matched_token"),
            "is_exact": bool(item.get("_is_exact_token_match")),
            "is_unique": bool(item.get("_is_unique_catalog_label", is_unique_exact)),
            "series_match": item.get("_series_match", "none")
        }

        if item.get("_is_relation_candidate"):
            rel_type = item.get("_relation_type")
            rel_conf = float(item.get("_relation_confidence") or 0.7)
            rel_strength = "STRONG" if rel_type in ("PAIRED_WITH_VERIFIED", "PAIRED_WITH") else ("HIGH" if rel_type == "PAIRED_WITH_DERIVED" else "ELIGIBLE")
            item["_relation_evidence_meta"] = {
                "relation_type": rel_type,
                "confidence": rel_conf,
                "relation_strength": rel_strength,
                "provenance": item.get("_relation_provenance"),
                "evidence_payload": item.get("_relation_evidence"),
                "relation_boost": round(item.get("_computed_relation_boost", 0.0), 2)
            }
            item["_relation_strength"] = rel_strength
        else:
            item["_relation_evidence_meta"] = None
            item["_relation_strength"] = None

        tier_offsets = {
            EvidenceTier.TIER_1_UNIQUE_EXACT: 1000.0,
            EvidenceTier.TIER_2_AMBIGUOUS_EXACT: 500.0,
            EvidenceTier.TIER_3_NEAR_MODEL_OR_STRONG: 300.0,
            EvidenceTier.TIER_4_TYPED_RELATION: 200.0,
            EvidenceTier.TIER_5_EXACT_CATALOG_BUNDLE: 150.0,
            EvidenceTier.TIER_6_STRONG_CATALOG_SPEC: 100.0,
            EvidenceTier.TIER_7_COMPATIBLE_RELATION: 50.0,
            EvidenceTier.TIER_8_BROAD_DISCOVERY: 0.0
        }
        item["_final_score"] = tier_offsets[tier] + tier_score
        return int(tier), tier_score
