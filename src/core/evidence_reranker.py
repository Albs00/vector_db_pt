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
- TIER 5 (TABLE_FAMILY_EXACT): brand + family_key da tabella PDF.
- TIER 6 (COMPATIBILITY_FAMILY): famiglia/serie dal compatibility master.
- TIER 7 (STRONG_CATALOG_SPEC): attributi tecnici strutturati.
- TIER 8 (COMPATIBLE_RELATION): relazioni COMPATIBLE_WITH.
- TIER 9 (BROAD_DISCOVERY): candidati da ricerca semantica o BM25 generica.

L'ordinamento prioritario è dato dalla tupla:
  (evidence_tier, -tier_score)
garantendo precedenza strutturale assoluta per i livelli superiori.
"""

import re
from enum import IntEnum
from typing import Dict, Any, List, Optional, Tuple

from src.core.catalog_table_context import CatalogTableContextIndex

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
    TIER_5_CATALOG_FAMILY_EXACT = 5  # Brand + family_key esatto dal catalogo (PDF Layout)
    TIER_6_COMPATIBILITY_FAMILY = 6  # Serie/famiglia dal compatibility master
    TIER_7_STRONG_CATALOG_SPEC = 7   # Brand + taglia/attributi; mai solo nome
    TIER_8_COMPATIBLE_RELATION = 8   # Candidati da relazione COMPATIBLE_WITH
    TIER_9_BROAD_DISCOVERY = 9       # Ricerca semantica/BM25 generica

# Alias retrocompatibile
EvidenceTier.TIER_5_TABLE_FAMILY_EXACT = EvidenceTier.TIER_5_CATALOG_FAMILY_EXACT


class GenericEvidenceReranker:
    """
    Reranker generico basato su livelli strutturali di evidenza.
    """

    @staticmethod
    def evaluate_catalog_family_match(
        item: Dict[str, Any], query_context: Optional[Dict[str, Any]] = None
    ) -> str:
        ctx = query_context or {}
        requested_key = str(ctx.get("requested_family_key") or "").strip()
        requested_brand = str(ctx.get("requested_brand") or "").strip().upper()
        item_brand = str(item.get("brand") or "").strip().upper()
        candidate_keys = CatalogTableContextIndex.candidate_family_keys(item)

        if requested_key and requested_key in candidate_keys:
            item["_series_match"] = "exact"
            item["_series_match_source"] = "PDF_LAYOUT"
            item["_table_family_match"] = "exact"
            item["family_match"] = "exact"
            item["_table_family_evidence"] = "CATALOG_FAMILY_EXACT"
            item["family_evidence"] = "CATALOG_FAMILY_EXACT"
            item["_matched_table_family_key"] = requested_key
            context = item.get("table_context") or {}
            if context.get("family_key") == requested_key:
                item["_matched_table_context"] = context
            else:
                for alternate in context.get("alternate_table_contexts") or []:
                    if alternate.get("family_key") == requested_key:
                        item["_matched_table_context"] = alternate
                        break
            return "exact"
        if (
            requested_key
            and requested_brand
            and item_brand == requested_brand
            and candidate_keys
            and item.get("table_source") == "PDF_LAYOUT"
        ):
            item["_series_match"] = "mismatch"
            item["_series_match_source"] = "PDF_LAYOUT"
            item["_table_family_match"] = "mismatch"
            item["family_match"] = "mismatch"
            item["_table_family_evidence"] = "CATALOG_FAMILY_MISMATCH"
            item["family_evidence"] = "CATALOG_FAMILY_MISMATCH"
            return "mismatch"
        item["family_match"] = "none"
        return "none"

    # Alias per retrocompatibilità
    evaluate_table_family_match = evaluate_catalog_family_match

    def assign_evidence_tier(
        self,
        item: Dict[str, Any],
        is_unique_exact: bool = True,
        query_context: Optional[Dict[str, Any]] = None
    ) -> EvidenceTier:
        """Determina il livello strutturale di evidenza del candidato."""
        self.evaluate_catalog_family_match(item, query_context)
        if item.get("_is_exact_token_match"):
            if is_unique_exact:
                return EvidenceTier.TIER_1_UNIQUE_EXACT
            return EvidenceTier.TIER_2_AMBIGUOUS_EXACT

        if item.get("_is_near_model_candidate"):
            return EvidenceTier.TIER_3_NEAR_MODEL_OR_STRONG

        # PAIRED_WITH_VERIFIED, PAIRED_WITH_DERIVED e kit certificati ottengono precedenza strutturale Tier 4
        rel_type = item.get("_relation_type")
        if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "PAIRED_WITH", "PAIRED_WITH_DERIVED"):
            return EvidenceTier.TIER_4_TYPED_RELATION

        # Mismatch esplicito di serie: mai promuovere a Tier elevati
        series_match = item.get("_series_match", "none")
        if series_match == "mismatch":
            return EvidenceTier.TIER_9_BROAD_DISCOVERY

        ctx = query_context or {}
        requested_btus = ctx.get("requested_btus", [])
        target_brand = (ctx.get("detected_brand") or "").strip().upper()
        item_brand = (item.get("brand") or "").strip().upper()
        brand_match = bool(target_brand and item_brand and (target_brand == item_brand or target_brand in item_brand))

        item_btu = item.get("taglia_btu")
        capacity_match = bool(requested_btus and item_btu and item_btu in requested_btus)

        # Tier 5: evidenza commerciale forte, brand-scoped e derivata dal catalogo (PDF Layout)
        if brand_match and (item.get("family_match") == "exact" or item.get("_table_family_match") == "exact"):
            return EvidenceTier.TIER_5_CATALOG_FAMILY_EXACT

        # Tier 6: famiglia/serie certificata dal compatibility master.
        if (
            brand_match
            and series_match in ("exact", "alias")
            and item.get("_series_match_source") == "COMPATIBILITY_MASTER"
        ):
            return EvidenceTier.TIER_6_COMPATIBILITY_FAMILY

        # Tier 7: attributi strutturati; un match nel solo nome non basta.
        if brand_match and capacity_match:
            return EvidenceTier.TIER_7_STRONG_CATALOG_SPEC

        # Tier 7: Candidato espanso da relazione COMPATIBLE_WITH
        if item.get("_is_relation_candidate") and rel_type == "COMPATIBLE_WITH":
            return EvidenceTier.TIER_8_COMPATIBLE_RELATION

        return EvidenceTier.TIER_9_BROAD_DISCOVERY

    def compute_tier_score(
        self,
        item: Dict[str, Any],
        query_tokens: List[str],
        detected_brand: Optional[str] = None,
        domain_boost: float = 0.0,
        is_machine_query: bool = False,
        query_context: Optional[Dict[str, Any]] = None
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
            all_rels = item.get("_relation_evidences") or []
            if all_rels:
                best_boost = 0.0
                for r_info in all_rels:
                    rt = r_info.get("relation_type")
                    rc = float(r_info.get("confidence") or 0.7)
                    if rt == "PDF_TABLE_PAIRING_VERIFIED":
                        b = 35.0 * rc
                    elif rt in ("KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "PAIRED_WITH"):
                        b = 25.0 * rc
                    elif rt == "PAIRED_WITH_DERIVED":
                        b = 20.0 * rc
                    elif rt == "COMPATIBLE_WITH":
                        b = 15.0 * rc
                    else:
                        b = 10.0 * rc
                    if b > best_boost:
                        best_boost = b
                rel_boost = best_boost
            else:
                rel_type = item.get("_relation_type")
                rel_conf = float(item.get("_relation_confidence") or 0.7)
                if rel_type == "PDF_TABLE_PAIRING_VERIFIED":
                    rel_boost = 35.0 * rel_conf
                elif rel_type in ("KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "PAIRED_WITH"):
                    rel_boost = 25.0 * rel_conf
                elif rel_type == "PAIRED_WITH_DERIVED":
                    rel_boost = 20.0 * rel_conf
                elif rel_type == "COMPATIBLE_WITH":
                    rel_boost = 15.0 * rel_conf
            score += rel_boost
        item["_computed_relation_boost"] = rel_boost

        # Serie e variante: boost per esatta o forte penalità per mismatch
        family_match = item.get("family_match") or item.get("_table_family_match", "none")
        if family_match == "exact":
            score += 45.0
        elif family_match == "mismatch":
            score -= 75.0

        series_match = item.get("_series_match", "none")
        if family_match not in ("exact", "mismatch") and series_match in ("exact", "alias"):
            score += 30.0
        elif family_match not in ("exact", "mismatch") and series_match == "mismatch":
            score -= 50.0

        if item.get("_color_match"):
            score += 15.0
        elif item.get("_color_mismatch"):
            score -= 20.0

        if is_machine_query and item.get("is_accessory"):
            score -= 30.0

        # Discriminanti tecnici di fase per Unità Esterne (UE)
        if item.get("is_ue") and query_context:
            req_phase = query_context.get("phase")
            item_name_u = (item.get("name") or "").upper()
            is_ue_trifase = bool(re.search(r'(?:\bT\b|TRIFASE|400V)', item_name_u))
            if req_phase == "TRIFASE":
                if is_ue_trifase:
                    score += 20.0
                else:
                    score -= 40.0
            elif req_phase == "MONOFASE":
                if not is_ue_trifase:
                    score += 20.0
                else:
                    score -= 40.0

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
            is_machine_query=is_machine_query,
            query_context=query_context
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
            "series_match": item.get("_series_match", "none"),
            "series_match_source": item.get("_series_match_source"),
            "family_match": item.get("family_match") or item.get("_table_family_match", "none"),
            "family_evidence": item.get("family_evidence") or item.get("_table_family_evidence"),
            "table_family_match": item.get("_table_family_match", "none"),
            "table_family_evidence": item.get("_table_family_evidence"),
            "requested_family_key": (query_context or {}).get("requested_family_key"),
            "candidate_family_key": item.get("family_key"),
        }

        if item.get("_is_relation_candidate"):
            rel_type = item.get("_relation_type")
            rel_conf = float(item.get("_relation_confidence") or 0.7)
            rel_strength = "STRONG" if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "PAIRED_WITH") else ("HIGH" if rel_type == "PAIRED_WITH_DERIVED" else "ELIGIBLE")
            rel_list = list(item.get("_relation_evidences") or [])
            if not rel_list and rel_type:
                rel_list = [{
                    "relation_type": rel_type,
                    "source_code": item.get("_relation_source"),
                    "confidence": rel_conf,
                    "provenance": item.get("_relation_provenance"),
                    "evidence": item.get("_relation_evidence"),
                }]
            item["_relation_evidences"] = rel_list
            item["relation_evidences"] = rel_list
            item["_relation_evidence_meta"] = {
                "relation_type": rel_type,
                "confidence": rel_conf,
                "relation_strength": rel_strength,
                "provenance": item.get("_relation_provenance"),
                "evidence_payload": item.get("_relation_evidence"),
                "relation_boost": round(item.get("_computed_relation_boost", 0.0), 2),
                "total_relations": len(rel_list),
            }
            item["_relation_strength"] = rel_strength
        else:
            item["_relation_evidence_meta"] = None
            item["_relation_strength"] = None
            item["_relation_evidences"] = []
            item["relation_evidences"] = []

        tier_offsets = {
            EvidenceTier.TIER_1_UNIQUE_EXACT: 1000.0,
            EvidenceTier.TIER_2_AMBIGUOUS_EXACT: 500.0,
            EvidenceTier.TIER_3_NEAR_MODEL_OR_STRONG: 300.0,
            EvidenceTier.TIER_4_TYPED_RELATION: 200.0,
            EvidenceTier.TIER_5_CATALOG_FAMILY_EXACT: 175.0,
            EvidenceTier.TIER_6_COMPATIBILITY_FAMILY: 125.0,
            EvidenceTier.TIER_7_STRONG_CATALOG_SPEC: 100.0,
            EvidenceTier.TIER_8_COMPATIBLE_RELATION: 50.0,
            EvidenceTier.TIER_9_BROAD_DISCOVERY: 0.0,
        }
        item["_final_score"] = tier_offsets[tier] + tier_score
        return int(tier), tier_score
