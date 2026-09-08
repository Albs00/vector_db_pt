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

# Category Adapters
from src.adapters.climate import ClimateCategoryAdapter, extract_split_capacities
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
    return item.get("_final_score", 0.0)


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
            return {
                "query": query,
                "detected_brand": item.get("brand"),
                "match_type": "exact_code_short_circuit",
                "execution_time_ms": round(elapsed * 1000, 2),
                "total_results": 1,
                "results": [item]
            }

        # STADIO 1.2: EXACT TOKEN & NEAR MODEL PARSING
        exact_token_candidates, near_model_candidates = self._token_parser.parse_query_tokens(query)

        # STADIO 2: DYNAMIC BRAND DETECTION (con alias conservativi)
        target_brand = brand
        if not target_brand and exact_token_candidates:
            target_brand = exact_token_candidates[0].get('brand')
        if not target_brand:
            target_brand = self._brand_detector.detect_brand(query)

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

        query_analysis_data = {
            "query_context": query_context,
            "target_brand": target_brand,
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
                {"code": str(it.get("code")), "mfg_code": it.get("mfg_code")}
                for it in near_model_candidates
            ]
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
            "query_analysis": query_analysis_data
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
