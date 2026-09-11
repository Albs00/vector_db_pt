"""
catalog_search_engine.py
Motore di Ricerca Ibrido e Modulare per il Catalogo Puglia Termica 2026.
Architettura generica, riutilizzabile e agnostica per tutte le categorie PT
(Climatizzazione, Caldaie, Pompe di Calore, Scaldabagni, Idraulica, Trattamento Acque).

Caratteristiche:
  1. Exact Token Parser: matching dei codici/modelli indicizzati con boundary e soglie di informatività
     (distingue EXACT_RAW, EXACT_NORMALIZED e NEAR_MODEL_CANDIDATE; XKE != ZKE).
  2. Dynamic Brand Detector: 416 marchi catalogo master con alias layer strettamente conservativo e documentato.
  3. Category Router: restituisce category/domain candidates ranked (nessun hard routing immediato, brand come weak prior).
  4. Typed Relation Expander: relazioni tipizzate con source/evidence/provenance (COMPATIBLE_WITH genera candidati senza implicare inclusion nella BOM).
  5. Evidence Tiers Reranker: precedenza strutturale per exact match univoci (Tier 1 a 5), con reranking all'interno dei livelli di evidenza.
  6. Candidate Pool Manager: architettura completamente slot-agnostic (candidate_pools[slot_id]).
  7. Bundle & Accessory Expander: arricchimento accessori pagina PDF.
  8. Rendering visivo opzionale pagina PDF tramite CatalogPageViewer.
"""

import sys
import os
import json
import time
import re
import collections
from typing import List, Dict, Any, Optional, Tuple

import lancedb
from lancedb.rerankers import LinearCombinationReranker
from fastembed import TextEmbedding

from catalog_page_viewer import CatalogPageViewer
from accessory_engine import AccessoryEngine
from build_full_ac_matrix import extract_btu_and_kw

# Componenti core generici
from src.core.token_parser import ExactTokenParser, normalize_token, MatchType
from src.core.brand_detector import DynamicBrandDetector, CONSERVATIVE_BRAND_ALIASES
from src.core.candidate_pool import CandidatePoolManager
from src.core.relation_types import TypedRelation, RelationType, TypedRelationExpander
from src.core.evidence_reranker import GenericEvidenceReranker, EvidenceTier
from src.core.category_router import CategoryRouter, DomainCandidate
from src.core.catalog_table_context import (
    CatalogTableContextIndex,
    normalize_family_key_part,
)
from src.core.component_relations import ClimateComponentRelationIndex
from src.core.clima_master_resolver import ClimaMasterResolver

# Category Adapters
from src.adapters.climate import (
    ClimateCategoryAdapter,
    extract_split_capacities,
    validate_multisplit_combination,
)
from src.adapters.boiler import BoilerCategoryAdapter
from src.adapters.default import DefaultCategoryAdapter

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "Knowledge", "vector_db", "lancedb_store")
LOOKUP_INDEX_PATH = os.path.join(BASE_DIR, "Knowledge", "vector_db", "exact_code_lookup.json")
MASTER_CATALOG_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
AC_MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "climatizzatori_compatibilita_master.json")
PDF_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_extracted_specs.json")
BOILER_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_boiler_specs.json")
HEATER_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_water_heater_specs.json")
FANCOIL_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_fancoil_specs.json")
HEATPUMP_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_heatpump_specs.json")
CATALOG_TABLE_CONTEXT_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_table_context.json")
COMPONENT_RELATIONS_V34_PATH = os.path.join(
    BASE_DIR, "catalog_component_relations_safe_preview_v3_4.json"
)
if not os.path.exists(MASTER_CATALOG_PATH):
    MASTER_CATALOG_PATH = os.path.join(os.path.dirname(BASE_DIR), "Knowledge", "unified_catalog_master.json")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Inizializzatori globali per retro-compatibilità
_GLOBAL_BRAND_DETECTOR = None
_GLOBAL_TOKEN_PARSER = None

BRAND_ALIASES = CONSERVATIVE_BRAND_ALIASES

def init_dynamic_brands(master_catalog=None):
    global _GLOBAL_BRAND_DETECTOR
    if _GLOBAL_BRAND_DETECTOR is None:
        _GLOBAL_BRAND_DETECTOR = DynamicBrandDetector(
            master_catalog=master_catalog,
            master_catalog_path=MASTER_CATALOG_PATH
        )
    return [(b, b) for b in _GLOBAL_BRAND_DETECTOR.get_all_brands()]

def detect_brand(query: str, master_catalog=None) -> Optional[str]:
    global _GLOBAL_BRAND_DETECTOR
    if _GLOBAL_BRAND_DETECTOR is None:
        _GLOBAL_BRAND_DETECTOR = DynamicBrandDetector(
            master_catalog=master_catalog,
            master_catalog_path=MASTER_CATALOG_PATH
        )
    return _GLOBAL_BRAND_DETECTOR.detect_brand(query)

def normalize_model_token(token: str) -> str:
    return normalize_token(token)

def extract_query_model_tokens(query: str) -> List[str]:
    global _GLOBAL_TOKEN_PARSER
    if _GLOBAL_TOKEN_PARSER is None:
        _GLOBAL_TOKEN_PARSER = ExactTokenParser()
    return _GLOBAL_TOKEN_PARSER.extract_model_tokens(query)

def is_climate_query(query: str) -> bool:
    adapter = ClimateCategoryAdapter()
    conf, _ = adapter.evaluate_domain_confidence(query, [])
    return conf >= 0.5

# Dizionario abbreviazioni ufficiali Puglia Termica
PT_ABBREVIATIONS = {
    "ACQUAPROJET": "ACQUAPR",
    "SCALDABAGNO": "SCALD",
    "SCALDABAGNI": "SCALD",
    "CALDAIA": "CALD",
    "CALDAIE": "CALD",
    "CONDENSAZIONE": "COND",
    "CAMERA STAGNA": "CS",
    "CAMERA APERTA": "CA",
    "METANO": "MET",
    "VENTILCONVETTORE": "VENTILCONV",
    "VENTILCONVETTORI": "VENTILCONV",
    "FAN COIL": "VENTILCONV",
    "FANCOIL": "VENTILCONV",
    "BOLLITORE": "BOLL",
    "BOLLITORI": "BOLL",
    "ACCUMULO": "ACCUM",
    "PRESSCONTROL": "PRESS",
    "PRESSOSTATO": "PRESS",
    "CIRCOLATORE": "CIRCOL",
    "CIRCOLATORI": "CIRCOL",
    "CRONOTERMOSTATO": "CRONOTERM",
    "TERMOSTATO": "TERMOST",
    "COASSIALE": "COASS",
    "SDOPPIATO": "SDOPP"
}

# Espansioni tecniche e commerciali
PT_EXPANSIONS = [
    (re.compile(r"\bacquaprojet\b", re.I), "acquapr acquaprojet"),
    (re.compile(r"\bscaldabagn[oi]\b", re.I), "scald scaldabagno"),
    (re.compile(r"\bcamera\s*stagna\b", re.I), "cs camera stagna"),
    (re.compile(r"\bcamera\s*aperta\b", re.I), "ca camera aperta"),
    (re.compile(r"\bcondensazione\b", re.I), "cond condensazione"),
    (re.compile(r"\bcaldaie?\b", re.I), "cald caldaia"),
    (re.compile(r"\bventilconvettor[ei]\b", re.I), "ventilconv fancoil"),
    (re.compile(r"\bfan\s*coil\b", re.I), "ventilconv fancoil"),
    (re.compile(r"\bbollitor[ei]\b", re.I), "boll bollitore"),
    (re.compile(r"\baccumul[oi]\b", re.I), "accum accumulo"),
    (re.compile(r"\bpresscontrol\b", re.I), "press presscontrol"),
    (re.compile(r"\bpressostat[oi]\b", re.I), "press pressostato"),
    (re.compile(r"\bcircolator[ei]\b", re.I), "circol circolatore"),
    (re.compile(r"\bcronotermostato\b", re.I), "cronoterm cronotermostato"),
    (re.compile(r"\btermostato\b", re.I), "termost termostato"),
    (re.compile(r"\bcoassiale\b", re.I), "coass coassiale 60/100"),
    (re.compile(r"\bsdoppiato\b", re.I), "sdopp sdoppiato 80/80"),
    (re.compile(r"\b(\d+)\s*litr[io]\b", re.I), r"\1 \1l \1fi \1igl"),
    (re.compile(r"\bfi\s*(\d+)\b", re.I), r"\1fi \1"),
]

BTU_KW_EXPANSIONS = [
    (re.compile(r"\b(?:7000\s*btu|7\s*k\s*btu|7000\s*b)\b", re.I), "20 2.0 kw 7000"),
    (re.compile(r"\b(?:9000\s*btu|9\s*k\s*btu|9000\s*b)\b", re.I), "25 2.5 kw 9000"),
    (re.compile(r"\b(?:12000\s*btu|12\s*k\s*btu|12000\s*b)\b", re.I), "35 3.5 kw 12000"),
    (re.compile(r"\b(?:18000\s*btu|18\s*k\s*btu|18000\s*b)\b", re.I), "50 5.0 kw 18000"),
    (re.compile(r"\b(?:24000\s*btu|24\s*k\s*btu|24000\s*b)\b", re.I), "70 7.0 kw 24000"),
    (re.compile(r"\b(?:dual\s*split|dual)\b", re.I), "multi 2 att 2mxm 2 attacchi"),
    (re.compile(r"\b(?:trial\s*split|trial)\b", re.I), "multi 3 att 3mxm 3 attacchi"),
    (re.compile(r"\b(?:quadri\s*split|quadri)\b", re.I), "multi 4 att 4mxm 4 attacchi"),
    (re.compile(r"\b(?:penta\s*split|penta)\b", re.I), "multi 5 att 5mxm 5 attacchi"),
    (re.compile(r"\b(?:monosplit|mono\s*split)\b", re.I), "mono ue ui"),
]

def expand_technical_query(query: str) -> str:
    expanded = query
    for pat, repl in BTU_KW_EXPANSIONS:
        if pat.search(expanded):
            expanded = pat.sub(lambda m: f"{m.group(0)} {repl}", expanded)
    for pat, repl in PT_EXPANSIONS:
        if pat.search(expanded):
            expanded = pat.sub(lambda m: f"{m.group(0)} {repl}", expanded)
    return expanded

def compute_field_boost(item: Dict[str, Any], query_tokens: List[str], requested_btus: Optional[List[int]] = None) -> float:
    reranker = GenericEvidenceReranker()
    domain_boost = 0.0
    if item.get('is_ui') and requested_btus and item.get('taglia_btu') in requested_btus:
        domain_boost += 25.0
    _, tier_score = reranker.evaluate_candidate(item, query_tokens, domain_boost=domain_boost)
    return tier_score

def find_explicit_included_components(
    query: str,
    candidate_pools: Dict[str, List[Dict[str, Any]]],
    query_context: Dict[str, Any],
    product_scope: Optional[str] = None,
    exact_token_candidates: Optional[List[Dict[str, Any]]] = None,
    near_model_candidates: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Identifica componenti fisici esplicitamente menzionati nel titolo del prodotto venduto:
    - il suo manufacturer model/code è esplicitamente presente nella query;
    - il match è univoco e forte;
    - il componente è descritto come parte del prodotto venduto;
    - non è dichiarato opzionale.

    Evidence ammesse per auto-inclusione:
    - UNIQUE EXACT / EXACT_RAW / EXACT_CATALOG_MODEL_LABEL / EXACT_PT / EXACT_MFG
    - near-model SOLO quando la differenza deriva da normalizzazione non semantica
      del modello, ad esempio: 4MWXM52A(9) -> 4MWXM52A9

    NON includere automaticamente:
    - accessori solo scoperti semanticamente;
    - accessori opzionali non fisicamente inclusi;
    - candidati generici del slot_accessory;
    - componenti che non hanno un modello/riferimento esplicito nella query.
    """
    if not query:
        return []

    q_raw = query.strip()
    raw_tokens = re.findall(r'[A-Za-z0-9]+(?:[\(\)\-\/\.][A-Za-z0-9]+)+|[A-Za-z0-9]{3,}', q_raw)

    # Raccoglie tutti i candidati potenziali da pool ed exact tokens
    candidate_map: Dict[str, Dict[str, Any]] = {}
    if exact_token_candidates:
        for it in exact_token_candidates:
            c = str(it.get("code") or "")
            if c:
                candidate_map[c] = it
    if near_model_candidates:
        for it in near_model_candidates:
            c = str(it.get("code") or "")
            if c and c not in candidate_map:
                candidate_map[c] = it

    for s_id, cands in candidate_pools.items():
        for it in cands:
            c = str(it.get("code") or "")
            if c:
                if c not in candidate_map:
                    candidate_map[c] = it
                else:
                    for k in ("evidence_tier", "identity_evidence", "is_ui", "is_ue", "taglia_btu"):
                        if k in it and k not in candidate_map[c]:
                            candidate_map[c][k] = it[k]

    explicit_items = []
    seen_codes = set()

    for code, cand in candidate_map.items():
        tier = cand.get("evidence_tier", 9)
        ident_ev = cand.get("identity_evidence") or {}
        match_type = ident_ev.get("match_type") or cand.get("_exact_match_type") or ""

        # Verifica evidence ammessa (Tier 1, Tier 2, o Tier 3 near-model con non-semantic norm)
        is_tier_1_2 = (
            tier in (1, 2) or
            cand.get("_is_exact_token_match") or
            match_type in ("EXACT_RAW", "EXACT_NORMALIZED", "EXACT_CATALOG_MODEL_LABEL", "EXACT_PT", "EXACT_MFG", "UNIQUE EXACT")
        )
        is_tier_3 = (
            tier == 3 or
            cand.get("_is_near_model_candidate") or
            match_type == "NEAR_MODEL_CANDIDATE"
        )

        if not (is_tier_1_2 or is_tier_3):
            continue

        mfg = str(cand.get("mfg_code") or "").strip()
        matched_token = None
        matched_pos = 9999

        # Verifica presenza esplicita di mfg_code nella query
        if mfg:
            norm_mfg = normalize_token(mfg)
            if len(norm_mfg) >= 4:
                for tok in raw_tokens:
                    norm_tok = normalize_token(tok)
                    if norm_tok == norm_mfg:
                        matched_token = tok
                        matched_pos = q_raw.find(tok)
                        break

        # Verifica presenza esplicita di codice PT a 8 cifre
        if not matched_token and len(code) == 8 and code.isdigit():
            m_pt = re.search(r'\b' + re.escape(code) + r'\b', q_raw)
            if m_pt:
                matched_token = code
                matched_pos = m_pt.start()

        if not matched_token:
            continue

        # Verifica se il componente è dichiarato opzionale nel titolo
        # es: "BRP069B45 optional", "optional BRP069B45", "con comando ... (optional)"
        opt_pattern = rf'(?:{re.escape(matched_token)}\s*(?:\([^)]*\))?\s*(?:optional|opzionale|non\s+inclus[oai]|esclus[oai])\b|\b(?:optional|opzionale|non\s+inclus[oai]|esclus[oai])\s*(?:\([^)]*\))?\s*{re.escape(matched_token)})'
        if re.search(opt_pattern, q_raw, re.I):
            continue

        # Rispetta i vincoli di product_scope per UI_ONLY ed UE_ONLY
        if product_scope == "UI_ONLY" and cand.get("is_ue"):
            continue
        if product_scope == "UE_ONLY" and cand.get("is_ui"):
            continue

        if code in seen_codes:
            continue
        seen_codes.add(code)

        cand_copy = dict(cand)
        cand_copy["_matched_query_pos"] = matched_pos

        if cand_copy.get("is_ue"):
            cand_copy["role"] = "UE"
            cand_copy["role_label"] = "UE (Motore Esterno)"
        elif cand_copy.get("is_ui"):
            btu = cand_copy.get("taglia_btu")
            cand_copy["role"] = "UI"
            cand_copy["role_label"] = f"UI {btu} BTU" if btu else "UI (Unità Interna)"
        else:
            name_u = (cand_copy.get("name") or "").upper()
            if any(w in name_u for w in ["ACCUMULO", "SERBATOIO", "BOLLITORE", "DHW", "TANK"]):
                cand_copy["role"] = "ACCUMULO"
                cand_copy["role_label"] = "Serbatoio A.C.S. / Accumulo"
            elif any(w in name_u for w in ["HYDROBOX", "HYDROTANK", "MODULO IDRONICO"]):
                cand_copy["role"] = "HYDROBOX"
                cand_copy["role_label"] = "Modulo Idronico / Hydrobox"
            elif any(w in name_u for w in ["PANNELLO", "GRIGLIA"]):
                cand_copy["role"] = "PANNELLO"
                cand_copy["role_label"] = "Pannello / Griglia"
            elif any(w in name_u for w in ["COMANDO", "CONTROLLER", "TERMOSTATO"]):
                cand_copy["role"] = "COMANDO"
                cand_copy["role_label"] = "Comando / Controllo"
            else:
                cand_copy["role"] = "INCLUDED_COMPONENT"
                cand_copy["role_label"] = "Componente Fisico Incluso"

        explicit_items.append(cand_copy)

    # Ordina per apparizione naturale nel titolo
    explicit_items.sort(key=lambda x: x.get("_matched_query_pos", 9999))
    return explicit_items


def assemble_bom(
    product_scope: Optional[str],
    candidate_pools: Dict[str, List[Dict[str, Any]]],
    query_context: Dict[str, Any],
    formatted_results: List[Dict[str, Any]],
    query: str = "",
    exact_token_candidates: Optional[List[Dict[str, Any]]] = None,
    near_model_candidates: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Assembla la distinta base (BOM) candidata in base alle regole di product_scope ed
    include componenti fisici esplicitamente presenti nella query (es. accumuli, serbatoi, ecc.):
    - Fase 1: explicit_included_components
    - Fase 2: topology_required_components
    BOM finale: explicit_included_components + topology_required_components
    Evita duplicazioni accidentali dello stesso codice tra le due fasi, ma preserva
    la molteplicità reale di UI multisplit (es. 9+9+9).
    """
    explicit_components = find_explicit_included_components(
        query=query,
        candidate_pools=candidate_pools,
        query_context=query_context,
        product_scope=product_scope,
        exact_token_candidates=exact_token_candidates,
        near_model_candidates=near_model_candidates
    )

    bom: List[Dict[str, Any]] = []
    seen_bom_codes = set()

    for exp_c in explicit_components:
        c_code = str(exp_c.get("code") or "")
        if c_code not in seen_bom_codes:
            seen_bom_codes.add(c_code)
            bom.append(exp_c)

    has_ue_in_bom = any(it.get("role") == "UE" or it.get("is_ue") for it in bom)
    has_ui_in_bom = any(it.get("role") == "UI" or it.get("is_ui") for it in bom)
    btus = query_context.get("requested_btus", [])

    if product_scope == "UI_ONLY":
        if not has_ui_in_bom:
            if btus:
                for btu in btus:
                    cands = candidate_pools.get(f"slot_ui_{btu}", candidate_pools.get("slot_ui", []))
                    if cands and str(cands[0].get("code") or "") not in seen_bom_codes:
                        cand = dict(cands[0])
                        cand["role"] = "UI"
                        cand["role_label"] = f"UI {btu} BTU"
                        bom.append(cand)
                        seen_bom_codes.add(str(cand.get("code") or ""))
            else:
                cands = candidate_pools.get("slot_ui", [])
                if not cands:
                    # Some catalog model labels identify a UI exactly even when
                    # the title omits the BTU value and the ERP MFG field is a
                    # vendor code. In that case use the best already-ranked UI
                    # slot instead of losing the explicit UI identity.
                    cands = sorted(
                        [
                            candidate
                            for slot_id, slot_candidates in candidate_pools.items()
                            if slot_id.startswith("slot_ui_")
                            for candidate in slot_candidates
                        ],
                        key=lambda candidate: float(candidate.get("score") or 0.0),
                        reverse=True,
                    )
                if cands and str(cands[0].get("code") or "") not in seen_bom_codes:
                    cand = dict(cands[0])
                    cand["role"] = "UI"
                    cand["role_label"] = "UI (Unità Interna)"
                    bom.append(cand)
                    seen_bom_codes.add(str(cand.get("code") or ""))
                elif formatted_results:
                    ui_cands = [r for r in formatted_results if r.get("is_ui")]
                    if ui_cands and str(ui_cands[0].get("code") or "") not in seen_bom_codes:
                        cand = dict(ui_cands[0])
                        cand["role"] = "UI"
                        cand["role_label"] = "UI (Unità Interna)"
                        bom.append(cand)
                        seen_bom_codes.add(str(cand.get("code") or ""))

    elif product_scope == "UE_ONLY":
        if not has_ue_in_bom:
            ue_cands = candidate_pools.get("slot_ue", [])
            if ue_cands and str(ue_cands[0].get("code") or "") not in seen_bom_codes:
                cand = dict(ue_cands[0])
                cand["role"] = "UE"
                cand["role_label"] = "UE (Motore Esterno)"
                bom.append(cand)
                seen_bom_codes.add(str(cand.get("code") or ""))
            elif formatted_results:
                ue_res = [r for r in formatted_results if r.get("is_ue")]
                if ue_res and str(ue_res[0].get("code") or "") not in seen_bom_codes:
                    cand = dict(ue_res[0])
                    cand["role"] = "UE"
                    cand["role_label"] = "UE (Motore Esterno)"
                    bom.append(cand)
                    seen_bom_codes.add(str(cand.get("code") or ""))

    elif product_scope == "MONOSPLIT":
        # UE:
        if not has_ue_in_bom:
            ue_cands = candidate_pools.get("slot_ue", [])
            if ue_cands and str(ue_cands[0].get("code") or "") not in seen_bom_codes:
                cand = dict(ue_cands[0])
                cand["role"] = "UE"
                cand["role_label"] = "UE (Motore Esterno)"
                bom.insert(0, cand)
                seen_bom_codes.add(str(cand.get("code") or ""))

        # UI:
        if not has_ui_in_bom:
            if btus:
                for btu in btus:
                    cands = candidate_pools.get(f"slot_ui_{btu}", candidate_pools.get("slot_ui", []))
                    if cands and str(cands[0].get("code") or "") not in seen_bom_codes:
                        cand = dict(cands[0])
                        cand["role"] = "UI"
                        cand["role_label"] = f"UI {btu} BTU"
                        bom.append(cand)
                        seen_bom_codes.add(str(cand.get("code") or ""))
            else:
                cands = candidate_pools.get("slot_ui", [])
                if not cands:
                    cands = sorted(
                        [
                            candidate
                            for slot_id, slot_candidates in candidate_pools.items()
                            if slot_id.startswith("slot_ui_")
                            for candidate in slot_candidates
                        ],
                        key=lambda candidate: float(candidate.get("score") or 0.0),
                        reverse=True,
                    )
                if cands and str(cands[0].get("code") or "") not in seen_bom_codes:
                    cand = dict(cands[0])
                    cand["role"] = "UI"
                    cand["role_label"] = "UI (Unità Interna)"
                    bom.append(cand)
                    seen_bom_codes.add(str(cand.get("code") or ""))

    elif product_scope == "MULTISPLIT":
        # UE:
        if not has_ue_in_bom:
            ue_cands = candidate_pools.get("slot_ue", [])
            if ue_cands and str(ue_cands[0].get("code") or "") not in seen_bom_codes:
                cand = dict(ue_cands[0])
                cand["role"] = "UE"
                cand["role_label"] = "UE (Motore Esterno)"
                bom.insert(0, cand)
                seen_bom_codes.add(str(cand.get("code") or ""))

        # UIs for MULTISPLIT:
        # Aggiunge UIs solo se richieste taglie BTU (preservando molteplicità per 9+9+9)
        if btus:
            for btu in btus:
                cands = candidate_pools.get(f"slot_ui_{btu}", candidate_pools.get("slot_ui", []))
                if cands:
                    cand = dict(cands[0])
                    cand["role"] = "UI"
                    cand["role_label"] = f"UI {btu} BTU"
                    bom.append(cand)

    else:
        if not bom and formatted_results:
            cand = dict(formatted_results[0])
            cand["role"] = "PRIMARY"
            cand["role_label"] = "Prodotto Primario"
            bom.append(cand)

    return bom


def check_multisplit_combination_verified(ue_rec: Dict[str, Any], uis_in_bom: List[Dict[str, Any]]) -> bool:
    """Backward-compatible boolean wrapper around the canonical matcher."""
    return bool(validate_multisplit_combination(ue_rec, uis_in_bom)["matched"])


def compute_compatibility_info(
    product_scope: Optional[str],
    adapter_name: str,
    bom: List[Dict[str, Any]],
    candidate_pools: Dict[str, List[Dict[str, Any]]],
    relations: List[Any],
    query_context: Dict[str, Any],
    adapter: Any = None,
    lookup_dict: Optional[Dict[str, Any]] = None,
    full_combination_result: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Calcola compatibility_status (VERIFIED | NOT_VERIFIED | NOT_APPLICABLE)
    e compatibility_evidence (relation_type, provenance, confidence, source_code, target_code, connected_components, relation_evidences).
    """
    if adapter_name != "CLIMA" or not product_scope or product_scope == "GENERAL":
        return "NOT_APPLICABLE", {
            "relation_type": None,
            "provenance": None,
            "source": None,
            "confidence": None,
            "source_code": None,
            "target_code": None,
            "connected_components": [],
            "componenti_collegati": [],
            "relation_evidences": []
        }

    rel_dicts = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in relations]

    ue_in_bom = next((it for it in bom if it.get("role") == "UE" or it.get("is_ue")), None)
    uis_in_bom = [it for it in bom if it.get("role") == "UI" or it.get("is_ui")]

    if product_scope == "MONOSPLIT":
        if ue_in_bom and uis_in_bom:
            ue_code = str(ue_in_bom.get("code") or "")
            ui_code = str(uis_in_bom[0].get("code") or "")
            source_code = ue_code
            target_code = ui_code

            matching_rels = [
                r for r in rel_dicts
                if (str(r.get("source_code")) == ue_code and str(r.get("target_code")) == ui_code) or
                   (str(r.get("source_code")) == ui_code and str(r.get("target_code")) == ue_code)
            ]

            if adapter and hasattr(adapter, "_pdf_table_pairs_ui_to_ue"):
                for p in adapter._pdf_table_pairs_ui_to_ue.get(ui_code, []):
                    if str(p.get("target_code") or "") == ue_code:
                        matching_rels.append({
                            "source_code": ui_code,
                            "target_code": ue_code,
                            "relation_type": "PDF_TABLE_PAIRING_VERIFIED",
                            "provenance": f"catalog_table_context.json:table_id={p.get('table_id')}[p.{p.get('page')}]",
                            "confidence": float(p.get("confidence") or 0.99)
                        })

            all_pair_evs = list(matching_rels)
            for ev in ue_in_bom.get("relation_evidences", []):
                if str(ev.get("source_code")) == ui_code or str(ev.get("target_code")) == ui_code:
                    all_pair_evs.append(ev)
            for ev in uis_in_bom[0].get("relation_evidences", []):
                if str(ev.get("source_code")) == ue_code or str(ev.get("target_code")) == ue_code:
                    all_pair_evs.append(ev)

            verified_rel = next(
                (r for r in all_pair_evs if r.get("relation_type") in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED")),
                None
            )

            connected = [
                {"code": ue_code, "mfg_code": ue_in_bom.get("mfg_code"), "name": ue_in_bom.get("name"), "role": "UE"},
                {"code": ui_code, "mfg_code": uis_in_bom[0].get("mfg_code"), "name": uis_in_bom[0].get("name"), "role": "UI"}
            ]

            if verified_rel:
                status = "VERIFIED"
                rel_type = verified_rel.get("relation_type")
                prov = verified_rel.get("provenance")
                conf = float(verified_rel.get("confidence") or 0.99)
            elif all_pair_evs:
                status = "NOT_VERIFIED"
                rel_type = all_pair_evs[0].get("relation_type")
                prov = all_pair_evs[0].get("provenance")
                conf = float(all_pair_evs[0].get("confidence") or 0.70)
            else:
                status = "NOT_VERIFIED"
                rel_type = None
                prov = None
                conf = None

            evidence = {
                "relation_type": rel_type,
                "provenance": prov,
                "source": prov,
                "confidence": conf,
                "source_code": source_code,
                "target_code": target_code,
                "connected_components": connected,
                "componenti_collegati": connected,
                "relation_evidences": all_pair_evs
            }
            return status, evidence
        else:
            return "NOT_VERIFIED", {
                "relation_type": None,
                "provenance": None,
                "source": None,
                "confidence": None,
                "source_code": None,
                "target_code": None,
                "connected_components": [],
                "componenti_collegati": [],
                "relation_evidences": []
            }

    elif product_scope == "MULTISPLIT":
        if ue_in_bom and uis_in_bom:
            ue_code = str(ue_in_bom.get("code") or "")
            source_code = ue_code
            target_code = [str(ui.get("code") or "") for ui in uis_in_bom]
            connected = [{"code": ue_code, "mfg_code": ue_in_bom.get("mfg_code"), "name": ue_in_bom.get("name"), "role": "UE"}]
            for ui in uis_in_bom:
                connected.append({
                    "code": ui.get("code"),
                    "mfg_code": ui.get("mfg_code"),
                    "name": ui.get("name"),
                    "taglia_btu": ui.get("taglia_btu"),
                    "role": "UI"
                })

            all_pairwise_compat = True
            all_pair_evs = []
            for ui in uis_in_bom:
                ui_code = str(ui.get("code") or "")
                matching = [
                    r for r in rel_dicts
                    if (str(r.get("source_code")) == ue_code and str(r.get("target_code")) == ui_code) or
                       (str(r.get("source_code")) == ui_code and str(r.get("target_code")) == ue_code)
                ]
                for ev in ui.get("relation_evidences", []):
                    if str(ev.get("source_code")) == ue_code or str(ev.get("target_code")) == ue_code:
                        matching.append(ev)
                if matching:
                    all_pair_evs.extend(matching)
                else:
                    all_pairwise_compat = False

            ue_master_rec = {}
            if adapter and hasattr(adapter, "_ac_master_ues"):
                ue_master_rec = adapter._ac_master_ues.get(ue_code) or {}
            elif lookup_dict:
                ue_master_rec = lookup_dict.get(ue_code) or {}

            combination_result = full_combination_result
            if all_pairwise_compat and ue_master_rec:
                if combination_result is None:
                    combination_result = validate_multisplit_combination(
                        ue_master_rec, uis_in_bom
                    )

            combination_result = combination_result or {}
            direct_full_evidence = bool(
                combination_result.get("matched")
                and combination_result.get("evidence_strength") == "CATALOG_TABLE_VERIFIED"
            )
            status = "VERIFIED" if direct_full_evidence else "NOT_VERIFIED"
            evidence = {
                "relation_type": "COMPATIBLE_WITH",
                "provenance": "climatizzatori_compatibilita_master.json:unita_esterne.unita_interne_compatibili",
                "source": "climatizzatori_compatibilita_master.json:unita_esterne.unita_interne_compatibili",
                "confidence": 0.85,
                "source_code": source_code,
                "target_code": target_code,
                "connected_components": connected,
                "componenti_collegati": connected,
                "relation_evidences": all_pair_evs,
                "full_combination_validation": combination_result,
            }
            return status, evidence
        else:
            connected = [
                {
                    "code": str(it.get("code") or ""),
                    "mfg_code": it.get("mfg_code"),
                    "name": it.get("name"),
                    "role": it.get("role") or ("UE" if it.get("is_ue") else "ACCUMULO")
                }
                for it in bom
            ]
            return "NOT_VERIFIED", {
                "relation_type": "COMPATIBLE_WITH" if ue_in_bom else None,
                "provenance": "climatizzatori_compatibilita_master.json:unita_esterne" if ue_in_bom else None,
                "source": "climatizzatori_compatibilita_master.json:unita_esterne" if ue_in_bom else None,
                "confidence": 0.85 if ue_in_bom else None,
                "source_code": str(ue_in_bom.get("code")) if ue_in_bom else None,
                "target_code": [str(it.get("code")) for it in bom if it != ue_in_bom],
                "connected_components": connected,
                "componenti_collegati": connected,
                "relation_evidences": []
            }

    elif product_scope == "UI_ONLY":
        if uis_in_bom:
            ui_item = uis_in_bom[0]
            ui_code = str(ui_item.get("code") or "")
            source_code = ui_code
            target_code = None
            status = "NOT_VERIFIED"
            rel_type = None
            prov = None
            conf = None

            if adapter and hasattr(adapter, "_pdf_table_pairs_ui_to_ue"):
                pdf_pairs = adapter._pdf_table_pairs_ui_to_ue.get(ui_code, [])
                if pdf_pairs:
                    pair = pdf_pairs[0]
                    target_code = str(pair.get("target_code") or "")
                    rel_type = "PDF_TABLE_PAIRING_VERIFIED"
                    prov = f"catalog_table_context.json:table_id={pair.get('table_id')}[p.{pair.get('page')}]"
                    conf = float(pair.get("confidence") or 0.99)
                    status = "VERIFIED"

            if not target_code:
                paired_rel = next(
                    (r for r in rel_dicts if str(r.get("source_code")) == ui_code or str(r.get("target_code")) == ui_code),
                    None
                )
                if paired_rel:
                    target_code = str(paired_rel.get("target_code") if str(paired_rel.get("source_code")) == ui_code else paired_rel.get("source_code"))
                    rel_type = paired_rel.get("relation_type")
                    prov = paired_rel.get("provenance")
                    conf = float(paired_rel.get("confidence") or 0.85)
                    if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "COMPATIBLE_WITH", "PAIRED_WITH_DERIVED"):
                        status = "VERIFIED"

            if not target_code:
                ue_cands = candidate_pools.get("slot_ue", [])
                if ue_cands:
                    top_ue = ue_cands[0]
                    target_code = str(top_ue.get("code") or "")
                    rel_meta = top_ue.get("relation_evidence") or {}
                    rel_type = rel_meta.get("relation_type") or top_ue.get("relation_type")
                    prov = rel_meta.get("provenance") or top_ue.get("relation_provenance")
                    conf = float(rel_meta.get("confidence") or 0.70)
                    if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "COMPATIBLE_WITH", "PAIRED_WITH_DERIVED"):
                        status = "VERIFIED"

            connected = [
                {"code": ui_code, "mfg_code": ui_item.get("mfg_code"), "name": ui_item.get("name"), "role": "UI"}
            ]
            if target_code:
                lookup = lookup_dict or {}
                ue_info = lookup.get(target_code) or {}
                connected.append({
                    "code": target_code,
                    "mfg_code": ue_info.get("mfg_code"),
                    "name": ue_info.get("name"),
                    "role": "UE",
                    "note": "Unità esterna compatibile a scopo informativo (NON inclusa nella BOM)"
                })

            all_rel_evs = [r for r in rel_dicts if str(r.get("source_code")) == ui_code or str(r.get("target_code")) == ui_code]
            if ui_item.get("relation_evidences"):
                all_rel_evs.extend(ui_item.get("relation_evidences"))

            evidence = {
                "relation_type": rel_type,
                "provenance": prov,
                "source": prov,
                "confidence": conf,
                "source_code": source_code,
                "target_code": target_code,
                "connected_components": connected,
                "componenti_collegati": connected,
                "relation_evidences": all_rel_evs
            }
            return status, evidence
        return "NOT_VERIFIED", {
            "relation_type": None,
            "provenance": None,
            "source": None,
            "confidence": None,
            "source_code": None,
            "target_code": None,
            "connected_components": [],
            "componenti_collegati": [],
            "relation_evidences": []
        }

    elif product_scope == "UE_ONLY":
        if ue_in_bom:
            ue_item = ue_in_bom
            ue_code = str(ue_item.get("code") or "")
            source_code = ue_code
            target_code = None
            status = "NOT_VERIFIED"
            rel_type = None
            prov = None
            conf = None

            if adapter and hasattr(adapter, "_pdf_table_pairs_ue_to_ui"):
                pdf_pairs = adapter._pdf_table_pairs_ue_to_ui.get(ue_code, [])
                if pdf_pairs:
                    pair = pdf_pairs[0]
                    target_code = str(pair.get("target_code") or "")
                    rel_type = "PDF_TABLE_PAIRING_VERIFIED"
                    prov = f"catalog_table_context.json:table_id={pair.get('table_id')}[p.{pair.get('page')}]"
                    conf = float(pair.get("confidence") or 0.99)
                    status = "VERIFIED"

            if not target_code:
                paired_rel = next(
                    (r for r in rel_dicts if str(r.get("source_code")) == ue_code or str(r.get("target_code")) == ue_code),
                    None
                )
                if paired_rel:
                    target_code = str(paired_rel.get("target_code") if str(paired_rel.get("source_code")) == ue_code else paired_rel.get("source_code"))
                    rel_type = paired_rel.get("relation_type")
                    prov = paired_rel.get("provenance")
                    conf = float(paired_rel.get("confidence") or 0.85)
                    if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "COMPATIBLE_WITH", "PAIRED_WITH_DERIVED"):
                        status = "VERIFIED"

            if not target_code:
                ui_candidates_found = []
                for s_id, cands in candidate_pools.items():
                    if s_id.startswith("slot_ui") and cands:
                        ui_candidates_found.extend(cands[:2])
                if ui_candidates_found:
                    top_ui = ui_candidates_found[0]
                    target_code = str(top_ui.get("code") or "")
                    rel_meta = top_ui.get("relation_evidence") or {}
                    rel_type = rel_meta.get("relation_type") or top_ui.get("relation_type")
                    prov = rel_meta.get("provenance") or top_ui.get("relation_provenance")
                    conf = float(rel_meta.get("confidence") or 0.70)
                    if rel_type in ("PDF_TABLE_PAIRING_VERIFIED", "KIT_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED", "COMPATIBLE_WITH", "PAIRED_WITH_DERIVED"):
                        status = "VERIFIED"

            connected = [
                {"code": ue_code, "mfg_code": ue_item.get("mfg_code"), "name": ue_item.get("name"), "role": "UE"}
            ]
            if target_code:
                lookup = lookup_dict or {}
                ui_info = lookup.get(target_code) or {}
                connected.append({
                    "code": target_code,
                    "mfg_code": ui_info.get("mfg_code"),
                    "name": ui_info.get("name"),
                    "role": "UI",
                    "note": "Unità interna compatibile a scopo informativo (NON inclusa nella BOM)"
                })

            all_rel_evs = [r for r in rel_dicts if str(r.get("source_code")) == ue_code or str(r.get("target_code")) == ue_code]
            if ue_item.get("relation_evidences"):
                all_rel_evs.extend(ue_item.get("relation_evidences"))

            evidence = {
                "relation_type": rel_type,
                "provenance": prov,
                "source": prov,
                "confidence": conf,
                "source_code": source_code,
                "target_code": target_code,
                "connected_components": connected,
                "componenti_collegati": connected,
                "relation_evidences": all_rel_evs
            }
            return status, evidence
        return "NOT_VERIFIED", {
            "relation_type": None,
            "provenance": None,
            "source": None,
            "confidence": None,
            "source_code": None,
            "target_code": None,
            "connected_components": [],
            "componenti_collegati": [],
            "relation_evidences": []
        }

    return "NOT_APPLICABLE", {
        "relation_type": None,
        "provenance": None,
        "source": None,
        "confidence": None,
        "source_code": None,
        "target_code": None,
        "connected_components": [],
        "componenti_collegati": [],
        "relation_evidences": []
    }


class CatalogSearchEngine:
    """
    Motore di ricerca ibrido generico per il catalogo Puglia Termica.
    Supporta multi-categoria (clima, caldaie, ecc.) tramite architettura ad Adapter.
    """

    def __init__(
        self,
        db_dir: str = DB_DIR,
        lookup_path: str = LOOKUP_INDEX_PATH,
        master_path: str = MASTER_CATALOG_PATH
    ):
        self.db_dir = db_dir
        self.lookup_path = lookup_path
        self.master_path = master_path
        self._clima_master_runtime_enabled = os.environ.get(
            "CLIMA_MASTER_RUNTIME_ENABLED", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}

        self._table = None
        self._lookup = None
        self._master_catalog = None
        self._brand_catalog = {}
        self._embed_model = None
        self._reranker = LinearCombinationReranker(weight=0.35)
        self._page_viewer = CatalogPageViewer()
        self._acc_engine = AccessoryEngine()

        # Componenti generici Core
        self._token_parser: Optional[ExactTokenParser] = None
        self._brand_detector: Optional[DynamicBrandDetector] = None
        self._evidence_reranker = GenericEvidenceReranker()
        self._relation_expander = TypedRelationExpander()
        self._catalog_table_context: Optional[CatalogTableContextIndex] = None
        self._component_relation_index: Optional[ClimateComponentRelationIndex] = None
        self._clima_master_resolver: Optional[ClimaMasterResolver] = None

        # Adapters e Router
        self._climate_adapter: Optional[ClimateCategoryAdapter] = None
        self._boiler_adapter: Optional[BoilerCategoryAdapter] = None
        self._router: Optional[CategoryRouter] = None

        # Retro-compatibilità
        self._ac_master_uis = None
        self._ac_master_ues = None
        self._ac_mfg_to_code = None
        self._pdf_specs = None
        self._boiler_specs = None
        self._heater_specs = None
        self._fancoil_specs = None
        self._heatpump_specs = None

    def _ensure_initialized(self):
        if self._catalog_table_context is None:
            self._catalog_table_context = CatalogTableContextIndex(CATALOG_TABLE_CONTEXT_PATH)

        if self._component_relation_index is None:
            self._component_relation_index = ClimateComponentRelationIndex(
                COMPONENT_RELATIONS_V34_PATH,
                CATALOG_TABLE_CONTEXT_PATH,
            )

        if self._lookup is None:
            if os.path.exists(self.lookup_path):
                with open(self.lookup_path, "r", encoding="utf-8") as f:
                    self._lookup = json.load(f)
            else:
                self._lookup = {}

        if self._master_catalog is None:
            if os.path.exists(self.master_path):
                with open(self.master_path, "r", encoding="utf-8") as f:
                    self._master_catalog = json.load(f)
                for it in self._master_catalog:
                    b = (it.get('brand') or '').strip().upper()
                    if b not in self._brand_catalog:
                        self._brand_catalog[b] = []
                    self._brand_catalog[b].append(it)
            else:
                self._master_catalog = []

        if self._brand_detector is None:
            self._brand_detector = DynamicBrandDetector(
                master_catalog=self._master_catalog,
                master_catalog_path=self.master_path
            )
            global _GLOBAL_BRAND_DETECTOR
            _GLOBAL_BRAND_DETECTOR = self._brand_detector

        if self._climate_adapter is None:
            self._climate_adapter = ClimateCategoryAdapter(
                ac_master_path=AC_MASTER_PATH,
                pdf_specs_path=PDF_SPECS_PATH,
                table_context_index=self._catalog_table_context,
            )
            self._ac_master_uis = self._climate_adapter._ac_master_uis
            self._ac_master_ues = self._climate_adapter._ac_master_ues

        if self._clima_master_runtime_enabled and self._clima_master_resolver is None:
            self._clima_master_resolver = ClimaMasterResolver(
                os.path.join(BASE_DIR, "Knowledge")
            )

        if self._token_parser is None:
            extractors = self._climate_adapter.get_catalog_label_extractors() if self._climate_adapter else []
            self._token_parser = ExactTokenParser(
                lookup_dict=self._lookup,
                master_catalog=self._master_catalog,
                label_extractors=extractors
            )
            global _GLOBAL_TOKEN_PARSER
            _GLOBAL_TOKEN_PARSER = self._token_parser

        if self._boiler_adapter is None:
            self._boiler_adapter = BoilerCategoryAdapter(
                boiler_specs_path=BOILER_SPECS_PATH
            )

        if self._router is None:
            self._router = CategoryRouter([
                self._climate_adapter,
                self._boiler_adapter
            ])

        if self._ac_mfg_to_code is None:
            self._ac_mfg_to_code = {}
            if self._master_catalog:
                for it in self._master_catalog:
                    cat = it.get('category_path') or ''
                    cat_r = it.get('category_root') or ''
                    if cat.startswith('CONDIZIONAMENTO') or cat_r == 'CONDIZIONAMENTO':
                        mfg = it.get('mfg_code')
                        if mfg:
                            nt_mfg = normalize_token(mfg)
                            if nt_mfg:
                                self._ac_mfg_to_code[nt_mfg] = (str(it.get('code')), mfg)
                        c = it.get('code')
                        if c:
                            nt_c = normalize_token(c)
                            if nt_c:
                                self._ac_mfg_to_code[nt_c] = (str(c), str(c))

        if self._table is None:
            if os.path.exists(self.db_dir):
                db = lancedb.connect(self.db_dir)
                try:
                    self._table = db.open_table("catalog_products")
                except Exception:
                    self._table = None

        if self._embed_model is None:
            self._embed_model = TextEmbedding(model_name=MODEL_NAME)

    def extract_exact_token_matches(self, query: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        exacts, _ = self._token_parser.parse_query_tokens(query)
        return exacts

    def extract_near_model_candidates(self, query: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        _, nears = self._token_parser.parse_query_tokens(query)
        return nears

    def _find_prefix_or_revision_candidates(self, nt: str) -> List[Dict[str, Any]]:
        self._ensure_initialized()
        _, nears = self._token_parser.parse_query_tokens(nt)
        return nears

    def _enrich_item_ac_tags(self, item: Dict[str, Any]):
        self._ensure_initialized()
        self._climate_adapter.enrich_item(item)

    def _enrich_candidate(self, item: Dict[str, Any], adapter=None) -> None:
        """Attach table context before any category-specific enrichment."""
        if self._catalog_table_context is not None:
            self._catalog_table_context.enrich_item(item)
        if adapter is not None:
            adapter.enrich_item(item)

    @staticmethod
    def _component_product_payload(item: Dict[str, Any]) -> Dict[str, Any]:
        role = str(item.get("role") or "").upper()
        if role not in {"UI", "UE"}:
            if item.get("is_ui") and not item.get("is_ue"):
                role = "UI"
            elif item.get("is_ue") and not item.get("is_ui"):
                role = "UE"
            else:
                role = ""
        return {
            "code": str(item.get("code") or "") or None,
            "mfg_code": item.get("mfg_code"),
            "name": item.get("name"),
            "role": role or None,
            "is_ui": bool(item.get("is_ui")),
            "is_ue": bool(item.get("is_ue")),
            "table_id": item.get("table_id"),
            "family_key": item.get("family_key"),
            "catalog_family": item.get("catalog_family"),
            "model": (item.get("table_context") or {}).get("model"),
        }

    @staticmethod
    def _deduplicate_component_products(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept = []
        seen = set()
        for item in items:
            key = (
                str(item.get("code") or ""), str(item.get("table_id") or ""),
                str(item.get("family_key") or ""), str(item.get("mfg_code") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            kept.append(item)
        return kept

    @staticmethod
    def _is_climate_scope_product(item: Dict[str, Any]) -> bool:
        """Return whether product metadata reliably places an item in climate."""
        category_root = str(item.get("category_root") or "").strip().upper()
        category_path = str(
            item.get("category_path") or item.get("category") or ""
        ).strip().upper()
        product_domain = str(item.get("product_domain") or "").strip().upper()
        return (
            category_root == "CONDIZIONAMENTO"
            or category_path.startswith("CONDIZIONAMENTO")
            or product_domain == "AIR_AIR_CLIMATE"
        )

    @staticmethod
    def _set_product_scope_context(
        query_context: Dict[str, Any],
        product_scope: str,
        source: str,
    ) -> str:
        """Keep the scalar scope and its legacy boolean projections aligned."""
        query_context["product_scope"] = product_scope
        query_context["product_scope_source"] = source
        query_context["is_ui_only"] = product_scope == "UI_ONLY"
        query_context["is_ue_only"] = product_scope == "UE_ONLY"
        query_context["is_monosplit"] = product_scope == "MONOSPLIT"
        query_context["is_multisplit"] = product_scope == "MULTISPLIT"
        return product_scope

    def _reconcile_product_scope(
        self,
        query_context: Dict[str, Any],
        identified_products: List[Dict[str, Any]],
        query: str = "",
    ) -> str:
        """Reconcile a weak query scope with already identified product roles.

        Explicit role/topology language always wins.  Metadata is considered
        only for exact products in the climate domain and only when their UI/UE
        flags are mutually exclusive.  Ambiguous alternatives for the same
        model may still establish a role when every alternative agrees.
        """
        current_scope = str(query_context.get("product_scope") or "GENERAL").upper()
        current_source = str(query_context.get("product_scope_source") or "")
        if current_source in {
            "QUERY_EXPLICIT_ROLE",
            "QUERY_EXPLICIT_CONFIGURATION",
        }:
            return self._set_product_scope_context(
                query_context, current_scope, current_source
            )

        products = self._deduplicate_component_products(identified_products or [])
        requested_pt_codes = set(re.findall(r"(?<!\d)\d{8}(?!\d)", query or ""))
        if requested_pt_codes:
            pt_products = [
                item for item in products
                if str(item.get("code") or "") in requested_pt_codes
            ]
            if pt_products:
                products = pt_products

        role_products = []
        for item in products:
            if not self._is_climate_scope_product(item):
                continue
            is_ui = bool(item.get("is_ui"))
            is_ue = bool(item.get("is_ue"))
            if is_ui == is_ue:
                continue
            role_products.append((item, "UI" if is_ui else "UE"))

        if not role_products:
            return self._set_product_scope_context(
                query_context,
                current_scope,
                current_source or "FALLBACK",
            )

        roles = {role for _, role in role_products}
        matched_tokens = {
            normalize_token(item.get("_matched_token") or "")
            for item, _ in role_products
            if normalize_token(item.get("_matched_token") or "")
        }

        if roles == {"UI", "UE"}:
            reconciled_scope = "MONOSPLIT"
            source = "EXACT_PRODUCT_COMPOSITION"
        elif roles == {"UI"}:
            # Multiple candidates for one ambiguous label are alternatives,
            # not a multisplit.  Multiple distinct exact tokens are components.
            if len(matched_tokens) > 1:
                reconciled_scope = "MULTISPLIT"
                source = "EXACT_PRODUCT_COMPOSITION"
            else:
                reconciled_scope = "UI_ONLY"
                source = "EXACT_PRODUCT_METADATA"
        else:
            reconciled_scope = "UE_ONLY"
            source = "EXACT_PRODUCT_METADATA"

        return self._set_product_scope_context(
            query_context, reconciled_scope, source
        )

    def _component_relations_after_product_match(
        self,
        adapter_name: str,
        exact_token_candidates: List[Dict[str, Any]],
        bom: List[Dict[str, Any]],
        formatted_results: List[Dict[str, Any]],
        query_context: Dict[str, Any],
        product_scope: Optional[str],
        query: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """Lookup accessories only after product identity has been established."""
        if adapter_name != "CLIMA" or self._component_relation_index is None:
            return [], [], "NOT_APPLICABLE"

        def product_candidates(items):
            return self._deduplicate_component_products([
                self._component_product_payload(item)
                for item in items
                if item.get("is_ui") or item.get("is_ue")
                or str(item.get("role") or "").upper() in {"UI", "UE"}
            ])

        def lookup_products(products):
            relations = []
            for product in products:
                relations.extend(self._component_relation_index.lookup_product(product))
            return self._component_relation_index._deduplicate(relations)

        def role_products(products, role):
            return [
                product for product in products
                if str(product.get("role") or "").upper() == role
            ]

        def select_role_product(role, exact_products, bom_products, result_products):
            """Select one concrete PT for a role, preferring exact + BOM agreement."""
            exact_for_role = role_products(exact_products, role)
            bom_for_role = role_products(bom_products, role)
            result_for_role = role_products(result_products, role)
            exact_codes = {
                str(product.get("code") or "") for product in exact_for_role
                if product.get("code")
            }

            # The BOM has already resolved ambiguous alternatives (for example
            # white vs black variants).  It may select an exact product but must
            # never promote a different-role context.
            for product in bom_for_role:
                if str(product.get("code") or "") in exact_codes:
                    return product
            if len(exact_for_role) == 1:
                return exact_for_role[0]
            for product in result_for_role:
                if str(product.get("code") or "") in exact_codes:
                    return product
            if bom_for_role:
                return bom_for_role[0]
            if exact_for_role:
                return exact_for_role[0]
            if result_for_role:
                return result_for_role[0]
            return None

        exact_products = product_candidates(exact_token_candidates)
        bom_products = product_candidates(bom)
        result_products = product_candidates(formatted_results)
        exact_codes = {
            str(product.get("code") or "") for product in exact_products
            if product.get("code")
        }

        def selection_status(products):
            if any(str(product.get("code") or "") in exact_codes for product in products):
                return "EXACT_PRODUCT_IDENTITY"
            return "BOM_PRODUCT_IDENTITY"

        if product_scope in {"UI_ONLY", "UE_ONLY"}:
            role = "UI" if product_scope == "UI_ONLY" else "UE"
            target = select_role_product(
                role, exact_products, bom_products, result_products
            )
            if target:
                products = [target]
                return lookup_products(products), products, selection_status(products)
            return [], [], "NO_ROLE_MATCHED_PRODUCT_CONTEXT"

        if product_scope == "MONOSPLIT":
            ui_product = select_role_product(
                "UI", exact_products, bom_products, result_products
            )
            ue_product = select_role_product(
                "UE", exact_products, bom_products, result_products
            )
            products = []
            relations = []
            if ui_product:
                products.append(ui_product)
                relations.extend(self._component_relation_index.lookup_product(ui_product))
            if ue_product:
                ue_relations = self._component_relation_index.lookup_product(ue_product)
                if ue_relations:
                    products.append(ue_product)
                    relations.extend(ue_relations)
            if products:
                return (
                    self._component_relation_index._deduplicate(relations),
                    products,
                    selection_status(products),
                )
            return [], [], "NO_ROLE_MATCHED_PRODUCT_CONTEXT"

        # Strong product identity wins.  If it has no component relation, do not
        # guess a different product from semantic candidates.
        if exact_products:
            return lookup_products(exact_products), exact_products, "EXACT_PRODUCT_IDENTITY"

        if product_scope and product_scope != "GENERAL":
            if bom_products:
                matches = lookup_products(bom_products)
                return matches, bom_products, "BOM_PRODUCT_IDENTITY"

        requested_family_key = query_context.get("requested_family_key")
        if requested_family_key:
            matches = self._component_relation_index.lookup_family(requested_family_key)
            family_product = [{
                "code": None,
                "mfg_code": None,
                "name": query_context.get("requested_family"),
                "role": "FAMILY",
                "is_ui": False,
                "is_ue": False,
                "table_id": None,
                "family_key": requested_family_key,
                "catalog_family": query_context.get("requested_family"),
                "model": None,
            }]
            return matches, family_product, "EXACT_FAMILY_CONTEXT"

        # The catalog can replace a final model revision letter (for example
        # FCAG71A in a legacy title vs FCAG71B in the current table).  Resolve
        # only that exact one-character revision pattern, never fuzzy or
        # semantic similarity, and only among already retrieved UI products.
        query_model_tokens = {
            normalize_token(token)
            for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9()/.\-]{4,}", query)
            if normalize_token(token)
        }
        revision_products = []
        for product in product_candidates(formatted_results):
            model = normalize_token(product.get("mfg_code") or product.get("model") or "")
            if not model or not product.get("is_ui"):
                continue
            if any(
                len(model) == len(token)
                and len(model) >= 6
                and model[:-1] == token[:-1]
                and model[-1:].isalpha()
                and token[-1:].isalpha()
                for token in query_model_tokens
            ):
                revision_products.append(product)
        revision_products = self._deduplicate_component_products(revision_products)
        if revision_products:
            matches = lookup_products(revision_products)
            return matches, revision_products, "EXACT_MODEL_REVISION_PRODUCT_CONTEXT"

        # Last deterministic product-identification fallback: use only concrete
        # UI candidates already selected by retrieval.  Accessory candidates are
        # never searched or used to guess the product.
        result_products = product_candidates([
            item for item in formatted_results if item.get("is_ui")
        ])
        if result_products:
            matches = lookup_products(result_products)
            return matches, result_products, "RETRIEVED_UI_PRODUCT_CONTEXT"
        return [], [], "NO_IDENTIFIED_CLIMATE_PRODUCT"

    def _search_master_retry(
        self,
        query: str,
        brand: Optional[str] = None,
        top_k: int = 15,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not self._master_catalog:
            return []

        candidates = self._brand_catalog.get(brand.upper(), self._master_catalog) if brand else self._master_catalog
        if category_filter:
            candidates = [
                it for it in candidates
                if it.get('category_root') == category_filter or (it.get('category_path') or '').startswith(category_filter)
            ]

        q_u = query.upper()
        expanded_q = q_u
        for k, v in PT_ABBREVIATIONS.items():
            expanded_q = re.sub(r'\b' + re.escape(k) + r'\b', v, expanded_q)

        noise = {'CON', 'PER', 'DEL', 'DELLA', 'SERIE', 'CLASSE', 'COMPLETA', 'OMAGGIO', 'WIFI', 'INVERTER', 'GAS', 'R32', 'OFFERTA', 'PROMO', 'PRONTA', 'CONSEGNA', 'KIT', 'FUMI', 'LOW', 'NOX', 'A', 'LO', 'IL', 'LA', 'LE', 'GLI'}
        words = [w for w in re.findall(r'[A-Za-z0-9]+', expanded_q) if len(w) >= 2 and w not in noise]
        if not words:
            return []

        is_cs = 'CS' in expanded_q or 'STAGNA' in q_u
        is_ca = 'CA' in expanded_q or 'APERTA' in q_u
        is_gpl = 'GPL' in q_u
        is_met = 'METANO' in q_u or 'MET' in q_u
        m_lit = re.search(r'\b(11|14|17)\b', q_u)
        lit = m_lit.group(1) if m_lit else None

        target_b_u = brand.upper() if brand else None
        scored = []
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()

            score = 0.0
            matched_model_tokens = 0
            for w in words:
                is_brand_token = target_b_u and w == target_b_u
                if f" {w} " in f" {name_u} " or name_u.startswith(w + " ") or name_u.endswith(" " + w):
                    score += 5.0 if is_brand_token else 35.0
                    if not is_brand_token: matched_model_tokens += 1
                elif w in name_u:
                    score += 3.0 if is_brand_token else 20.0
                    if not is_brand_token: matched_model_tokens += 1
                elif len(w) >= 5 and (w[:6] in name_u or w[:5] in name_u):
                    score += 2.0 if is_brand_token else 15.0
                    if not is_brand_token: matched_model_tokens += 1
                elif w in mfg_u:
                    score += 5.0 if is_brand_token else 25.0
                    if not is_brand_token: matched_model_tokens += 1

            if matched_model_tokens == 0:
                continue

            if is_gpl and 'GPL' in name_u: score += 10.0
            elif is_met and 'MET' in name_u: score += 10.0
            if is_cs and 'CS' in name_u: score += 10.0
            elif is_ca and 'CA' in name_u: score += 10.0
            if lit and lit in name_u: score += 15.0
            if 'AIR' in q_u and 'AIR' in name_u: score += 15.0

            if score >= 15.0:
                r_copy = dict(it)
                r_copy["_relevance_score"] = score
                scored.append(r_copy)

        scored.sort(key=lambda x: x["_relevance_score"], reverse=True)
        return scored[:top_k]

    def search(
        self,
        query: str,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        catalog_only: bool = False,
        limit: int = 10,
        include_accessories: bool = True
    ) -> Dict[str, Any]:
        """
        Esegue la ricerca con architettura generica, evidence tiers e slot-agnostic pools.
        """
        t0 = time.time()
        self._ensure_initialized()

        clean_q = query.strip().lower()
        stripped_q = re.sub(r"[\s\-\.\/]", "", clean_q)

        # STADIO 1: EXACT CODE SHORT-CIRCUIT MATCH
        single_exact_match = None
        if clean_q in self._lookup:
            single_exact_match = self._lookup[clean_q]
        elif stripped_q in self._lookup:
            single_exact_match = self._lookup[stripped_q]

        raw_model_tokens = self._token_parser.extract_model_tokens(query)
        if single_exact_match and len(raw_model_tokens) <= 1 and len(clean_q.split()) <= 2:
            elapsed = time.time() - t0
            item = dict(single_exact_match)
            self._enrich_candidate(item, self._climate_adapter)
            is_climate_product = self._is_climate_scope_product(item)
            query_context = self._climate_adapter.extract_query_context(query)
            product_scope = (
                self._reconcile_product_scope(query_context, [item], query)
                if is_climate_product else None
            )
            if is_climate_product and self._clima_master_resolver is not None:
                master_result = self._clima_master_resolver.resolve(
                    query,
                    {**query_context, "product_scope": product_scope},
                    [item],
                    include_accessories=include_accessories,
                )
                if master_result is not None:
                    master_result["execution_time_ms"] = round((time.time() - t0) * 1000, 2)
                    master_result["query_analysis"]["query_context"].update(query_context)
                    master_result["query_analysis"]["query_context"]["product_scope"] = master_result["product_scope"]
                    return master_result
            if include_accessories:
                rel = self._acc_engine.get_relations(item)
                item["product_type"] = rel["product_type"]
                item["variants"] = rel.get("variants", [])
                item["kits"] = rel.get("kits", [])
                item["single_units"] = rel.get("single_units", [])
                item["accessory_groups"] = rel.get("accessory_groups", [])
                item["total_accessories_count"] = sum(len(g["items"]) for g in rel.get("accessory_groups", []))
                item["total_kits_count"] = len(rel.get("kits", []))
                item["total_units_count"] = len(rel.get("single_units", []))
                all_acc_items = []
                for g in rel.get("accessory_groups", []):
                    all_acc_items.extend(g["items"])
                item["page_accessories"] = all_acc_items[:8]
                if "ac_details" in rel and rel["ac_details"]:
                    for k, v in rel["ac_details"].items():
                        if v is not None:
                            item[k] = v
            else:
                item["product_type"] = "GENERAL"
                item["variants"] = []
                item["kits"] = []
                item["single_units"] = []
                item["accessory_groups"] = []
                item["total_accessories_count"] = 0
                item["total_kits_count"] = 0
                item["total_units_count"] = 0
                item["page_accessories"] = []

            item["score"] = 1000.0
            component_relations = []
            component_products = []
            component_lookup_status = "NOT_APPLICABLE"
            if item.get("is_ui") or item.get("is_ue"):
                product = self._component_product_payload(item)
                component_products = [product]
                component_relations = self._component_relation_index.lookup_product(product)
                component_lookup_status = "EXACT_PRODUCT_IDENTITY"
            return {
                "query": query,
                "detected_brand": item.get("brand"),
                "detected_category": "CLIMA" if is_climate_product else None,
                "match_type": "exact_code_short_circuit",
                "execution_time_ms": round(elapsed * 1000, 2),
                "total_results": 1,
                "results": [item],
                "query_analysis": {
                    "query_context": query_context,
                    "product_scope": product_scope,
                    "exact_token_candidates": [{
                        "code": str(item.get("code") or ""),
                        "mfg_code": item.get("mfg_code"),
                        "match_type": "EXACT_PT",
                    }],
                    "near_model_candidates": [],
                    "component_relation_lookup_status": component_lookup_status,
                    "component_relation_products": component_products,
                },
                "product_scope": product_scope,
                "compatibility_status": "NOT_APPLICABLE",
                "compatibility_evidence": {
                    "relation_type": None,
                    "provenance": None,
                    "source": None,
                    "connected_components": [],
                    "componenti_collegati": [],
                    "confidence": None
                },
                "bom": [item],
                "component_relations": component_relations,
                "component_relation_products": component_products,
                "component_relation_lookup_status": component_lookup_status,
                "component_relation_source": ClimateComponentRelationIndex.SOURCE_NAME,
            }

        # STADIO 1.2: EXACT TOKEN & NEAR MODEL PARSING
        exact_token_candidates, near_model_candidates = self._token_parser.parse_query_tokens(query)

        # STADIO 2: DYNAMIC BRAND DETECTION (con alias conservativi)
        target_brand = brand
        if not target_brand and exact_token_candidates:
            target_brand = exact_token_candidates[0].get('brand')
        if not target_brand:
            target_brand = self._brand_detector.detect_brand(query)

        # A production-master family/model may itself be the strongest CLIMA
        # domain signal (for example "TOSHIBA HAORI BIANCO 9000").  Evaluate
        # the authoritative resolver before generic category routing so such
        # requests cannot fall into the default-domain legacy path.
        if self._clima_master_resolver is not None:
            pre_master_context = self._climate_adapter.extract_query_context(query)
            pre_master_context["detected_brand"] = target_brand
            pre_master_result = self._clima_master_resolver.resolve(
                query,
                pre_master_context,
                exact_token_candidates,
                include_accessories=include_accessories,
            )
            if pre_master_result is not None:
                pre_master_result["execution_time_ms"] = round((time.time() - t0) * 1000, 2)
                pre_context = pre_master_result["query_analysis"]["query_context"]
                master_scope = pre_master_result["product_scope"]
                pre_context.update(pre_master_context)
                pre_context["product_scope"] = master_scope
                pre_master_result["query_analysis"]["product_scope"] = master_scope
                return pre_master_result

        # STADIO 3: CATEGORY ROUTING (Ranked Domain Candidates, Brand come weak prior)
        domain_candidates = self._router.rank_domains(query, exact_token_candidates, target_brand)
        primary_domain = domain_candidates[0]
        adapter = primary_domain.adapter
        query_context = adapter.extract_query_context(query)
        query_context["detected_brand"] = target_brand
        family_request = self._catalog_table_context.analyze_query(
            query,
            target_brand,
            fallback_family=query_context.get("requested_series"),
        )
        # Midea XTREME PRO without an exact legacy identity is a commercial
        # request for the currently sold XTREME PRO WIFI family.  The legacy
        # family remains indexed and wins whenever its exact PT/model is present.
        if (
            adapter.name == "CLIMA"
            and normalize_family_key_part(target_brand) == "MIDEA"
            and family_request.get("requested_family_key") == "MIDEA_XTREME_PRO"
        ):
            legacy_codes = set(
                self._catalog_table_context.codes_for_family_key("MIDEA_XTREME_PRO")
            )
            has_exact_legacy_identity = any(
                str(item.get("code") or "") in legacy_codes
                for item in exact_token_candidates
            )
            if (
                not has_exact_legacy_identity
                and self._catalog_table_context.codes_for_family_key(
                    "MIDEA_XTREME_PRO_WIFI"
                )
            ):
                family_request = dict(family_request)
                family_request.update({
                    "requested_family": "XTREME PRO WIFI",
                    "requested_family_key": "MIDEA_XTREME_PRO_WIFI",
                    "commercial_family_override_from": "MIDEA_XTREME_PRO",
                    "commercial_family_override_reason": "LEGACY_FAMILY_NOT_SOLD",
                })
        gen_family_key = family_request.get("requested_family_key")
        if gen_family_key:
            brand_norm = normalize_family_key_part(target_brand)
            brand_families = (
                self._catalog_table_context._families_by_brand.get(brand_norm, [])
                if hasattr(self._catalog_table_context, "_families_by_brand")
                else []
            )
            has_codes = bool(self._catalog_table_context.codes_for_family_key(gen_family_key))
            req_family = family_request.get("requested_family")
            is_valid_brand_family = bool(req_family and req_family in brand_families)

            if not has_codes and not is_valid_brand_family:
                family_request["requested_family_key"] = None
                family_request["requested_family"] = None

        query_context.update(family_request)
        if family_request.get("requested_family") and not query_context.get("requested_series"):
            query_context["requested_series"] = family_request["requested_family"]
        elif not family_request.get("requested_family_key"):
            query_context["requested_series"] = None
        target_category = category or primary_domain.category_filter

        # Production CLIMA masters are authoritative and are evaluated before
        # vector/BM25 discovery.  Only an exact identity, exact pair, or exact
        # full configuration can short-circuit the legacy candidate path.
        if adapter.name == "CLIMA" and self._clima_master_resolver is not None:
            master_result = self._clima_master_resolver.resolve(
                query,
                query_context,
                exact_token_candidates,
                include_accessories=include_accessories,
            )
            if master_result is not None:
                master_result["execution_time_ms"] = round((time.time() - t0) * 1000, 2)
                master_context = master_result["query_analysis"]["query_context"]
                master_scope = master_result["product_scope"]
                master_context.update(query_context)
                master_context["product_scope"] = master_scope
                master_result["query_analysis"]["product_scope"] = master_scope
                return master_result

        fts_query = expand_technical_query(query)

        # STADIO 4: RICERCA IBRIDA LANCEDB
        raw_results = []
        if self._table is not None:
            query_vec = list(self._embed_model.embed([query]))[0]
            query_vec_float = [float(v) for v in query_vec]

            def build_conditions(use_brand, use_cat):
                conds = []
                if catalog_only:
                    conds.append("in_catalog_pdf = true")
                if use_brand:
                    safe_b = use_brand.strip().upper().replace("'", "''")
                    conds.append(f"brand LIKE '%{safe_b}%'")
                if use_cat:
                    safe_c = use_cat.replace("'", "''")
                    conds.append(f"category_root = '{safe_c}'")
                return " AND ".join(conds) if conds else None

            filter_expr = build_conditions(target_brand, target_category)
            candidate_limit = max(limit * 4, 40)
            search_query = self._table.search(query_type="hybrid").vector(query_vec_float).text(fts_query)
            if filter_expr:
                search_query = search_query.where(filter_expr)
            search_query = search_query.rerank(reranker=self._reranker)
            raw_results = search_query.limit(candidate_limit).to_list()

            if not raw_results and target_brand:
                fallback_filter = build_conditions(None, target_category)
                search_query = self._table.search(query_type="hybrid").vector(query_vec_float).text(fts_query)
                if fallback_filter:
                    search_query = search_query.where(fallback_filter)
                search_query = search_query.rerank(reranker=self._reranker)
                raw_results = search_query.limit(candidate_limit).to_list()

        # STADIO 5: QUERY RETRY SULL'ANAGRAFICA MASTER
        master_results = self._search_master_retry(
            query,
            target_brand,
            top_k=limit * 2,
            category_filter=target_category
        )

        # Structured retrieval from PDF table membership. This makes the
        # commercial family searchable even when the product name conflicts
        # with the table title or omits it entirely.
        table_family_results = []
        requested_family_key = query_context.get("requested_family_key")
        if requested_family_key:
            for code in self._catalog_table_context.codes_for_family_key(requested_family_key):
                source_item = self._lookup.get(code)
                if source_item:
                    family_item = dict(source_item)
                    family_item["_is_table_family_candidate"] = True
                    family_item["_relevance_score"] = max(
                        float(family_item.get("_relevance_score") or 0.0), 40.0
                    )
                    table_family_results.append(family_item)

        # STADIO 5.5: CANDIDATE MERGE & CATEGORY HYGIENE
        merged_candidates: Dict[str, Dict[str, Any]] = {}

        # 1. Exact token matches
        for it in exact_token_candidates:
            self._enrich_candidate(it, adapter)
            if adapter.filter_candidate(it, query_context):
                merged_candidates[it['code']] = it

        # 2. Near model candidates
        for it in near_model_candidates:
            self._enrich_candidate(it, adapter)
            c = it['code']
            if c not in merged_candidates and adapter.filter_candidate(it, query_context):
                merged_candidates[c] = it

        # 3. Exact table-family membership
        for it in table_family_results:
            self._enrich_candidate(it, adapter)
            c = it['code']
            if c not in merged_candidates and adapter.filter_candidate(it, query_context):
                merged_candidates[c] = it

        # 4. LanceDB results
        for r in raw_results:
            self._enrich_candidate(r, adapter)
            c = r['code']
            if c not in merged_candidates and adapter.filter_candidate(r, query_context):
                merged_candidates[c] = dict(r)

        # 5. Master retry results
        for r in master_results:
            self._enrich_candidate(r, adapter)
            c = r['code']
            if adapter.filter_candidate(r, query_context):
                if c not in merged_candidates:
                    merged_candidates[c] = dict(r)
                else:
                    merged_candidates[c]["_relevance_score"] = max(
                        merged_candidates[c].get("_relevance_score", 0.0),
                        r.get("_relevance_score", 0.0)
                    )

        # STADIO 5.6: TYPED RELATION EXPANSION (con provenance ed evidenza)
        relations = []
        anchor_items = [
            it for it in merged_candidates.values()
            if it.get('_is_exact_token_match') or it.get('_is_near_model_candidate')
        ]
        # Inversa: se non abbiamo ancora anchor UE, selezioniamo UI con forte evidenza identitaria
        has_ue_anchor = any(it.get('is_ue') for it in anchor_items)
        if not has_ue_anchor and hasattr(adapter, "select_ui_anchors"):
            ui_anchors = adapter.select_ui_anchors(merged_candidates.values(), query_context)
            if ui_anchors:
                anchor_items.extend(ui_anchors)

        if anchor_items:
            relations = adapter.expand_relations(anchor_items, self._lookup, query_context=query_context)
            for rel in relations:
                self._relation_expander.register_relation(rel)

            anchor_codes = [str(it.get('code')) for it in anchor_items]
            expanded = self._relation_expander.expand_candidate_pool(
                anchor_codes,
                self._lookup,
                merged_candidates,
                max_expansions_per_anchor=50
            )
            for exp_it in expanded:
                self._enrich_candidate(exp_it, adapter)
                if not adapter.filter_candidate(exp_it, query_context):
                    merged_candidates.pop(exp_it['code'], None)

        # STADIO 6: EVIDENCE TIERS & SLOT-AGNOSTIC POOL MANAGER
        q_tokens = [t.lower() for t in re.findall(r'\w+', fts_query) if len(t) > 1]
        pool_manager = CandidatePoolManager()

        # Disambiguazione exact matches per slot_id
        exact_by_slot = collections.defaultdict(list)
        for it in merged_candidates.values():
            if it.get('_is_exact_token_match'):
                slot_id = adapter.assign_slot(it, query_context)
                exact_by_slot[slot_id].append(it)

        for c_code, it in list(merged_candidates.items()):
            slot_id = adapter.assign_slot(it, query_context)
            it["slot_id"] = slot_id
            domain_boost = adapter.compute_domain_boost(it, query_context)

            is_unique_exact = True
            if it.get('_is_exact_token_match'):
                slot_exacts = exact_by_slot.get(slot_id, [])
                if len(slot_exacts) > 1:
                    if target_brand and (it.get('brand') or '').upper() == target_brand.upper():
                        is_unique_exact = True
                    else:
                        is_unique_exact = False

            # Valutazione strutturale per Evidence Tiers
            self._evidence_reranker.evaluate_candidate(
                item=it,
                query_tokens=q_tokens,
                detected_brand=target_brand,
                domain_boost=domain_boost,
                is_unique_exact=is_unique_exact,
                is_machine_query=query_context.get("is_machine_query", False),
                query_context=query_context
            )
            pool_manager.add_candidate(slot_id, it)

        if adapter.name == "CLIMA" and hasattr(adapter, "apply_color_variant_guard"):
            for slot_id in pool_manager.get_all_slots():
                adapter.apply_color_variant_guard(
                    pool_manager.get_pool(slot_id), query_context
                )

        # STADIO 6.2: INTERLEAVED COMPOSITE RESULT ASSEMBLY
        # Verifica se esiste un anchor affidabile per abilitare la riserva prioritaria
        # (La riserva è ammessa solo per EXACT_PT, EXACT_MFG, EXACT_CATALOG_MODEL_LABEL univoco o kit verified/derived)
        has_reliable_anchor = any(
            it.get("_is_exact_token_match") and not it.get("_is_near_model_candidate")
            for it in merged_candidates.values()
        ) or any(
            getattr(r, "relation_type", None) in (
                RelationType.PDF_TABLE_PAIRING_VERIFIED,
                RelationType.KIT_PAIRING_VERIFIED,
                RelationType.PAIRED_WITH_VERIFIED,
                RelationType.PAIRED_WITH_DERIVED
            )
            for r in relations
        )
        query_context["has_reliable_anchor"] = has_reliable_anchor
        quotas = adapter.get_slot_quotas(query_context, limit)
        top_candidates = pool_manager.interleave(slot_quotas=quotas, total_limit=limit)

        elapsed = time.time() - t0

        formatted_results = []
        for r in top_candidates:
            self._enrich_candidate(r, adapter)
            if include_accessories:
                rel = self._acc_engine.get_relations(r)
                item_variants = rel.get("variants", [])
                item_kits = rel.get("kits", [])
                item_single_units = rel.get("single_units", [])
                item_acc_groups = rel.get("accessory_groups", [])
                total_acc = sum(len(g["items"]) for g in item_acc_groups)
                p_type = rel["product_type"]
                flat_accs = []
                for g in item_acc_groups:
                    flat_accs.extend(g["items"])
            else:
                item_variants = []
                item_kits = []
                item_single_units = []
                item_acc_groups = []
                total_acc = 0
                p_type = "GENERAL"
                flat_accs = []

            res_item = {
                "code": r.get("code"),
                "mfg_code": r.get("mfg_code"),
                "name": r.get("name"),
                "brand": r.get("brand"),
                "category": r.get("category_path"),
                "category_root": r.get("category_root") or (r.get("category_path") or "").split(" > ")[0].strip(),
                "gross_price": r.get("gross_price"),
                "net_price": r.get("net_price"),
                "image_url": r.get("image_url"),
                "in_catalog_pdf": r.get("in_catalog_pdf"),
                "primary_page": r.get("primary_page"),
                "catalog_pages": r.get("catalog_pages"),
                "score": round(r.get("_final_score", 0.0), 4),
                "evidence_tier": r.get("_evidence_tier", 9),
                "tier_score": round(r.get("_tier_score", 0.0), 4),
                "product_type": p_type,
                "variants": item_variants,
                "kits": item_kits,
                "single_units": item_single_units,
                "accessory_groups": item_acc_groups,
                "total_kits_count": len(item_kits),
                "total_units_count": len(item_single_units),
                "total_accessories_count": total_acc,
                "page_accessories": flat_accs[:8]
            }
            for key in [
                "catalog_family", "family_key", "table_title", "table_id",
                "table_page", "table_section_title", "table_source",
                "table_confidence", "table_context",
            ]:
                if key in r:
                    res_item[key] = r[key]
            for key in ["color_base", "variant_full", "candidate_color", "variant_conflict"]:
                if key in r:
                    res_item[key] = r[key]

            evidence_tags = []
            f_match = r.get("family_match") or r.get("_table_family_match")
            if f_match == "exact":
                evidence_tags.extend(["CATALOG_FAMILY_MATCH", "CATALOG_FAMILY_EXACT"])
            elif f_match == "mismatch":
                evidence_tags.append("CATALOG_FAMILY_MISMATCH")
            res_item["evidence_tags"] = evidence_tags
            res_item["slot_id"] = r.get("slot_id")
            res_item["family_match"] = f_match or "none"
            res_item["family_evidence"] = r.get("family_evidence") or r.get("_table_family_evidence")
            res_item["table_family_match"] = f_match or "none"
            res_item["matched_table_family_key"] = r.get("_matched_table_family_key")
            res_item["matched_table_context"] = r.get("_matched_table_context")
            # Metadati di slot e tracciabilità separata di identità e relazione
            res_item["identity_evidence"] = r.get("_identity_evidence")
            res_item["relation_evidence"] = r.get("_relation_evidence_meta")
            res_item["relation_evidences"] = r.get("relation_evidences") or r.get("_relation_evidences") or []
            res_item["relation_strength"] = r.get("_relation_strength")
            res_item["match_type"] = r.get("_exact_match_type") or ("NEAR_MODEL" if r.get("_is_near_model_candidate") else "DISCOVERY")
            if "_relation_provenance" in r:
                res_item["relation_provenance"] = r["_relation_provenance"]

            for k in ["is_ui", "is_ue", "is_boiler", "is_scaldabagno", "is_ventilconvettore", "is_pompa_calore",
                      "taglia_btu", "taglia_kw", "tag_btu", "tag_btu_display", "tag_kw", "tag_kw_display",
                      "porte_attacchi", "max_ui_collegabili", "tipo_sistema", "tipo_unita"]:
                if k in r:
                    res_item[k] = r[k]

            formatted_results.append(res_item)

        # Preparazione candidate_pools e relations per architettura avanzata (Point 5)
        candidate_pools_data = {}
        for s_id in pool_manager.get_all_slots():
            candidate_pools_data[s_id] = [
                {
                    "code": str(c.get("code")),
                    "name": c.get("name"),
                    "brand": c.get("brand"),
                    "mfg_code": c.get("mfg_code"),
                    "slot_id": s_id,
                    "match_type": c.get("_exact_match_type") or ("NEAR_MODEL" if c.get("_is_near_model_candidate") else "DISCOVERY"),
                    "identity_evidence": c.get("_identity_evidence"),
                    "relation_evidence": c.get("_relation_evidence_meta"),
                    "relation_evidences": c.get("relation_evidences") or c.get("_relation_evidences") or [],
                    "relation_strength": c.get("_relation_strength"),
                    "evidence_tier": c.get("_evidence_tier", 9),
                    "tier_score": round(c.get("_tier_score", 0.0), 4),
                    "score": round(c.get("_final_score", 0.0), 4),
                    "relation_type": c.get("_relation_type"),
                    "relation_provenance": c.get("_relation_provenance"),
                    "primary_page": c.get("primary_page"),
                    "catalog_family": c.get("catalog_family"),
                    "family_key": c.get("family_key"),
                    "family_match": c.get("family_match") or c.get("_table_family_match", "none"),
                    "family_evidence": c.get("family_evidence") or c.get("_table_family_evidence"),
                    "table_title": c.get("table_title"),
                    "color_base": c.get("color_base"),
                    "variant_full": c.get("variant_full"),
                    "candidate_color": c.get("candidate_color"),
                    "variant_conflict": bool(c.get("variant_conflict")),
                    "table_page": c.get("table_page"),
                    "table_source": c.get("table_source"),
                    "table_context": c.get("table_context"),
                    "is_ui": c.get("is_ui", False),
                    "is_ue": c.get("is_ue", False),
                    "taglia_btu": c.get("taglia_btu")
                }
                for c in pool_manager.get_pool(s_id)
            ]

        relations_data = [
            rel.to_dict() if hasattr(rel, "to_dict") else dict(rel)
            for rel in relations
        ]

        product_scope = None
        if adapter.name == "CLIMA":
            product_scope = self._reconcile_product_scope(
                query_context,
                exact_token_candidates,
                query,
            )

        bom = assemble_bom(
            product_scope, candidate_pools_data, query_context, formatted_results,
            query=query, exact_token_candidates=exact_token_candidates, near_model_candidates=near_model_candidates
        )
        pairing_diagnostics = {
            "PAIRING_REASON": None,
            "PAIRING_SCORE_BREAKDOWN": {},
            "PAIRING_STATUS": "NOT_APPLICABLE",
            "MPN_FINAL_ALLOWED": False,
        }
        if (
            adapter.name == "CLIMA"
            and product_scope in ("MONOSPLIT", "MULTISPLIT")
            and hasattr(adapter, "resolve_main_component_pairing")
        ):
            bom, pairing_diagnostics = adapter.resolve_main_component_pairing(
                bom, candidate_pools_data, query_context
            )
            ue_for_pairing = next(
                (item for item in bom if item.get("role") == "UE" or item.get("is_ue")),
                None,
            )
            uis_for_pairing = [
                item for item in bom if item.get("role") == "UI" or item.get("is_ui")
            ]
            if product_scope == "MULTISPLIT":
                product_identity_status = pairing_diagnostics.get(
                    "PRODUCT_IDENTITY_STATUS", "DISCOVERY_ONLY"
                )
                configuration_status = pairing_diagnostics.get(
                    "CONFIGURATION_STATUS", "NOT_VERIFIED"
                )
                pairing_confirmed = bool(
                    product_identity_status == "EXACT"
                    and configuration_status == "VERIFIED_FULL_COMBINATION"
                )
                pairing_diagnostics["PAIRING_STATUS"] = (
                    "PAIRING_CONFIRMED"
                    if pairing_confirmed
                    else "CONFIGURAZIONE_NON_CONFERMATA"
                )
                pairing_diagnostics["MPN_FINAL_ALLOWED"] = pairing_confirmed
                pairing_diagnostics["full_configuration_verified"] = bool(
                    configuration_status == "VERIFIED_FULL_COMBINATION"
                )
            elif pairing_diagnostics.get("selected_ue_code"):
                pairing_diagnostics["PAIRING_STATUS"] = "PAIRING_CONFIRMED"
                pairing_diagnostics["MPN_FINAL_ALLOWED"] = True
        compat_status, compat_evidence = compute_compatibility_info(
            product_scope, adapter.name, bom, candidate_pools_data, relations, query_context,
            adapter=adapter, lookup_dict=self._lookup,
            full_combination_result=pairing_diagnostics.get(
                "FULL_CONFIGURATION_VALIDATION"
            ),
        )
        if (
            product_scope == "MULTISPLIT"
            and pairing_diagnostics.get("PAIRING_STATUS") == "CONFIGURAZIONE_NON_CONFERMATA"
        ):
            # Pairwise master compatibility is eligibility evidence only.  It
            # cannot certify the complete commercial combination or unlock MPN.
            compat_status = "NOT_VERIFIED"
            compat_evidence = dict(compat_evidence or {})
            compat_evidence["commercial_pairing_status"] = "CONFIGURAZIONE_NON_CONFERMATA"
            compat_evidence["commercial_pairing_gate"] = "SELECTED_UI_BOM_ONLY"
        elif (
            product_scope == "MULTISPLIT"
            and pairing_diagnostics.get("PAIRING_STATUS") == "PAIRING_CONFIRMED"
        ):
            compat_status = "VERIFIED"
            compat_evidence = dict(compat_evidence or {})
            compat_evidence["commercial_pairing_status"] = "PAIRING_CONFIRMED"
            compat_evidence["commercial_pairing_gate"] = "SELECTED_UI_BOM_ONLY"
        component_relations, component_products, component_lookup_status = (
            self._component_relations_after_product_match(
                adapter.name,
                exact_token_candidates,
                bom,
                formatted_results,
                query_context,
                product_scope,
                query,
            )
        )
        master_validation = None
        accessory_bom = []
        accessory_status = "NOT_APPLICABLE"
        accessory_ambiguous = []
        component_relation_source = ClimateComponentRelationIndex.SOURCE_NAME
        if adapter.name == "CLIMA" and self._clima_master_resolver is not None:
            master_validation = self._clima_master_resolver.validate_legacy_bom(
                product_scope, bom
            )
            if product_scope in ("MONOSPLIT", "MULTISPLIT"):
                if master_validation.get("confirmed"):
                    pairing_diagnostics["CONFIGURATION_STATUS"] = master_validation["configuration_status"]
                    pairing_diagnostics["PAIRING_STATUS"] = "PAIRING_CONFIRMED"
                    pairing_diagnostics["MPN_FINAL_ALLOWED"] = True
                else:
                    pairing_diagnostics["CONFIGURATION_STATUS"] = "CONFIGURAZIONE_NON_CONFERMATA"
                    pairing_diagnostics["PAIRING_STATUS"] = "CONFIGURAZIONE_NON_CONFERMATA"
                    pairing_diagnostics["MPN_FINAL_ALLOWED"] = False
                    pairing_diagnostics["MPN_FINAL_BLOCK_REASON"] = "MASTER_CONFIGURATION_NOT_CONFIRMED"
                    compat_status = "NOT_VERIFIED"
            accessory_resolution = self._clima_master_resolver.resolve_accessories(query, bom)
            accessory_bom = accessory_resolution["bom"]
            accessory_status = accessory_resolution["status"]
            accessory_ambiguous = accessory_resolution["ambiguous"]
            bom = bom + accessory_bom
            # The climate accessory master is the sole CLIMA relation source.
            # V3.4 remains available to other domains but cannot override it.
            component_relations = accessory_resolution["evidence"]
            component_lookup_status = "CLIMA_ACCESSORY_MASTER"
            component_relation_source = "clima_accessori_master.json"

        query_analysis_data = {
            "query_context": query_context,
            "target_brand": target_brand,
            "product_scope": product_scope,
            "product_scope_source": query_context.get("product_scope_source"),
            "compatibility_status": compat_status,
            "compatibility_evidence": compat_evidence,
            "phase": query_context.get("phase"),
            "requested_brand": query_context.get("requested_brand"),
            "requested_family": query_context.get("requested_family"),
            "requested_family_key": query_context.get("requested_family_key"),
            "domain_candidates": [d.adapter.name for d in domain_candidates] if domain_candidates else [],
            "exact_token_candidates": [
                {"code": str(it.get("code")), "mfg_code": it.get("mfg_code"), "match_type": it.get("_exact_match_type")}
                for it in exact_token_candidates
            ],
            "near_model_candidates": [
                {
                    "code": str(it.get("code")),
                    "mfg_code": it.get("mfg_code"),
                    "query_model_token": it.get("_matched_token"),
                    "model_structural_stem": it.get("_model_structural_stem"),
                    "model_diff_type": it.get("_model_diff_type"),
                    "model_diff_details": it.get("_model_diff_details"),
                }
                for it in near_model_candidates
            ],
            "component_relation_lookup_status": component_lookup_status,
            "component_relation_products": component_products,
            "pairing_reason": pairing_diagnostics.get("PAIRING_REASON"),
            "pairing_score_breakdown": pairing_diagnostics.get("PAIRING_SCORE_BREAKDOWN"),
            "pairing_status": pairing_diagnostics.get("PAIRING_STATUS"),
            "mpn_final_allowed": pairing_diagnostics.get("MPN_FINAL_ALLOWED"),
            "product_identity_status": pairing_diagnostics.get("PRODUCT_IDENTITY_STATUS"),
            "configuration_status": pairing_diagnostics.get("CONFIGURATION_STATUS"),
            "mpn_final_block_reason": pairing_diagnostics.get("MPN_FINAL_BLOCK_REASON"),
            "master_validation": master_validation,
            "accessory_status": accessory_status,
        }

        return {
            "query": query,
            "detected_brand": target_brand,
            "detected_category": adapter.name,
            "domain_confidence": primary_domain.confidence,
            "domain_evidence": primary_domain.evidence_sources,
            "match_type": "hybrid_vector_bm25",
            "execution_time_ms": round(elapsed * 1000, 2),
            "total_results": len(formatted_results),
            "results": formatted_results,
            # Nuovi campi per architettura avanzata:
            "candidate_pools": candidate_pools_data,
            "relations": relations_data,
            "query_analysis": query_analysis_data,
            # Campi espliciti richiesti:
            "product_scope": product_scope,
            "compatibility_status": compat_status,
            "compatibility_evidence": compat_evidence,
            "bom": bom,
            "component_relations": component_relations,
            "component_relation_products": component_products,
            "component_relation_lookup_status": component_lookup_status,
            "component_relation_source": component_relation_source,
            "accessory_bom": accessory_bom,
            "accessory_status": accessory_status,
            "accessory_ambiguous": accessory_ambiguous,
            "master_validation": master_validation,
            "dataset_release": (
                self._clima_master_resolver.DATASET_VERSION
                if adapter.name == "CLIMA" and self._clima_master_resolver is not None
                else None
            ),
            "pairing_reason": pairing_diagnostics.get("PAIRING_REASON"),
            "pairing_score_breakdown": pairing_diagnostics.get("PAIRING_SCORE_BREAKDOWN"),
            "pairing_status": pairing_diagnostics.get("PAIRING_STATUS"),
            "mpn_final_allowed": pairing_diagnostics.get("MPN_FINAL_ALLOWED"),
            "product_identity_status": pairing_diagnostics.get("PRODUCT_IDENTITY_STATUS"),
            "configuration_status": pairing_diagnostics.get("CONFIGURATION_STATUS"),
            "mpn_final_block_reason": pairing_diagnostics.get("MPN_FINAL_BLOCK_REASON"),
            "pairing_diagnostics": pairing_diagnostics,
        }


if __name__ == "__main__":
    engine = CatalogSearchEngine()
    test_queries = [
        "50042371",
        "caldaia a condensazione ferroli 28 kw",
        "daikin stylish 12000 btu",
        "CU-2Z50TBE",
        "AJ052TXJ3KG/EU",
        "pompa DAB autoclave",
        "fumisteria condensazione polymaxacciai"
    ]
    print("=== TESTING ADVANCED MODULAR CATALOG SEARCH ENGINE ===")
    for q in test_queries:
        res = engine.search(q, limit=3)
        print(f"\nQUERY: '{q}' (Brand: {res.get('detected_brand')}, Domain: {res.get('detected_category')} [conf={res.get('domain_confidence')}]) in {res['execution_time_ms']}ms - Trovati: {res['total_results']}")
        for r in res["results"]:
            print(f"  -> [{r['code']}] {r['brand']} - {r['name']} (Tier: {r.get('evidence_tier')}, Score: {r['score']})")
            if r.get('taglia_kw'):
                print(f"     kW: {r['taglia_kw']}")
            if r.get('taglia_btu'):
                print(f"     BTU: {r['taglia_btu']}")
