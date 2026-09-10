"""
src/adapters/climate.py
Category Adapter per il dominio Climatizzazione e Condizionamento.
Incapsula:
- Slot IDs dinamici: 'slot_ue', 'slot_ui_{btu}', 'slot_accessory', 'slot_monoblocco', 'slot_clima_general'.
- Relazioni tipizzate COMPATIBLE_WITH con provenienza da climatizzatori_compatibilita_master.json.
  (Le relazioni generano candidati per il pool ma non certificano inclusion automatica nella BOM).
- Category hygiene basata su membership anagrafica nel compatibility master e category_root.
- Riconoscimento capacità multisplit e monosplit.
- Valutazione della confidenza di dominio con brand come weak prior.
"""

import re
import json
import os
import collections
from typing import Dict, Any, List, Optional, Tuple, Set

from src.adapters.base import BaseCategoryAdapter
from src.core.relation_types import TypedRelation, RelationType
from src.core.candidate_pool import SlotConfig
from src.core.catalog_table_context import CatalogTableContextIndex
from build_full_ac_matrix import extract_btu_and_kw


def capacity_kw_for_btu(btu: int) -> float:
    """Restituisce la potenza nominale in kW commerciale corrispondente alla taglia BTU."""
    mapping = {
        7000: 2.0, 9000: 2.6, 12000: 3.5, 15000: 4.2, 18000: 5.0,
        21000: 6.0, 24000: 7.0, 28000: 8.0, 30000: 8.5, 36000: 10.0,
        42000: 12.0, 48000: 14.0, 55000: 15.0, 60000: 16.0
    }
    return mapping.get(btu, round(btu / 3412.14, 1))


def extract_split_capacities(query: str) -> List[int]:
    """Estrae le capacità BTU richieste per le unità interne multisplit (es. 9+12 -> [9000, 12000]) o monosplit."""
    q_u = query.upper()
    m = re.search(
        r'\b(\d{1,2}|7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000)\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000)(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000))?(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000))?(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000))?\b',
        q_u
    )
    if m:
        capacities = []
        for g in m.groups():
            if g:
                val = int(g)
                if val < 100:
                    val *= 1000
                capacities.append(val)
        return capacities
    m_single = re.search(r'\b(7000|9000|12000|15000|18000|21000|24000|28000|30000|36000|42000|48000|55000|60000)\s*BTU\b', q_u)
    if m_single:
        return [int(m_single.group(1))]
    m_single_gen = re.search(r'\b(\d{1,2}(?:\.000|000)?)\s*BTU\b', q_u)
    if m_single_gen:
        val = int(m_single_gen.group(1).replace('.', ''))
        if val < 100:
            val *= 1000
        return [val]
    return []


CLIMA_KEYWORDS = [
    'climatizzatore', 'condizionatore', 'climatizzatori', 'condizionatori',
    'monosplit', 'mono split', 'dual split', 'dualsplit', 'dual',
    'trial split', 'trialsplit', 'trial',
    'quadri split', 'quadrisplit', 'quadri',
    'penta split', 'pentasplit', 'penta',
    'multi split', 'multisplit',
    'unità interna', 'unita interna', 'unità esterna', 'unita esterna',
    'motocondensante', 'btu', 'split'
]


class ClimateCategoryAdapter(BaseCategoryAdapter):
    """
    Adapter di categoria per climatizzatori e condizionatori.
    """

    def __init__(
        self,
        ac_master_path: Optional[str] = None,
        pdf_specs_path: Optional[str] = None,
        table_context_index: Optional[CatalogTableContextIndex] = None,
    ):
        self._ac_master_uis: Dict[str, Any] = {}
        self._ac_master_ues: Dict[str, Any] = {}
        self._pdf_specs: Dict[str, Any] = {}
        self._dynamic_capacity_class_map: Dict[Tuple[str, str], int] = {}
        self._series_vocab: List[str] = []
        self._series_aliases: Dict[str, List[str]] = {}
        self._table_context_index = table_context_index
        self._pdf_table_pairs_ui_to_ue: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        self._pdf_table_pairs_ue_to_ui: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if ac_master_path is None:
            default_master = os.path.join(base_dir, "Knowledge", "climatizzatori_compatibilita_master.json")
            if os.path.exists(default_master):
                ac_master_path = default_master

        if ac_master_path and os.path.exists(ac_master_path):
            try:
                with open(ac_master_path, "r", encoding="utf-8") as f:
                    ac_data = json.load(f)
                    self._ac_master_uis = ac_data.get("unita_interne", {})
                    self._ac_master_ues = ac_data.get("unita_esterne", {})
            except Exception:
                pass

        if pdf_specs_path and os.path.exists(pdf_specs_path):
            try:
                with open(pdf_specs_path, "r", encoding="utf-8") as f:
                    self._pdf_specs = json.load(f)
            except Exception:
                pass

        if self._table_context_index is None:
            default_ctx = os.path.join(base_dir, "Knowledge", "catalog_table_context.json")
            if os.path.exists(default_ctx):
                self._table_context_index = CatalogTableContextIndex(default_ctx)

        self._init_dynamic_capacity_classes()
        self._init_dynamic_series_vocabulary()
        self._init_pdf_table_pairings()

    def _extract_commercial_sizes(self, code: str, ctx: Dict[str, Any]) -> Set[str]:
        """Estrae i token di taglia/classe commerciale (kW, BTU, sigla modello) per match di tabella PDF."""
        sizes: Set[str] = set()
        master_rec = self._ac_master_uis.get(code) or self._ac_master_ues.get(code) or {}

        # 1. Da potenza nominale kW
        kw = master_rec.get("potenza_nominale_kw")
        if kw:
            try:
                f_kw = float(kw)
                s_kw = str(round(f_kw, 1))
                sizes.add(s_kw)
                sizes.add(s_kw.replace(".", ""))
                sizes.add(str(int(round(f_kw * 10))))
            except Exception:
                pass

        # 2. Da taglia BTU
        btu = master_rec.get("taglia_btu")
        if btu:
            sizes.add(str(btu))
            btu_map = {
                7000: {"20", "21", "25", "2.0", "2.1", "200"},
                9000: {"25", "26", "2.5", "2.6", "025", "026", "250", "260"},
                12000: {"35", "3.5", "035", "350"},
                15000: {"42", "4.2", "45", "4.5"},
                18000: {"50", "52", "53", "5.0", "5.2", "5.3", "050", "052", "500", "520", "530"},
                21000: {"60", "6.0"},
                24000: {"70", "71", "7.0", "7.1", "070", "071", "700", "710"},
                28000: {"80", "8.0"},
                30000: {"85", "8.5"},
                36000: {"100", "10.0", "105"},
                42000: {"120", "125", "12.0", "12.5"},
                48000: {"140", "14.0"},
                55000: {"150", "15.0"},
                60000: {"160", "16.0"},
            }
            if btu in btu_map:
                sizes.update(btu_map[btu])

        raw_text = (ctx.get("model") or "") + " " + (master_rec.get("name") or "")

        # Pulizia stopword / pattern serie per evitare falsi match numerici (es. CL3000i, CL7000i, R32)
        cleaned = re.sub(r"\bCL(?:IMATE)?\s*\d{4}[iI]?\b", " ", raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bCL\d{4}[iI]?\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:U\.I\.|U\.E\.|UI|UE|OPTIONAL)\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bR32\b|\bR-32\b|\bR410A\b|\bINVERTER\b", " ", cleaned, flags=re.IGNORECASE)

        # Estrazione token taglia commerciale (2 o 3 cifre, es. 26WE, 350W, AC026, S24EQ)
        for m in re.finditer(r"\b(\d{2,3})\s*(?:WE|W|E|K|VG|NSK|RX|U|IU|OU)?\b", cleaned):
            token = m.group(1)
            sizes.add(token)
            if len(token) == 3 and token.startswith("0"):
                sizes.add(token[1:])

        return sizes

    def _init_pdf_table_pairings(self) -> None:
        """
        Estrae le coppie commerciali esplicite UI <-> UE presenti nella stessa tabella/blocco PDF.
        Regola:
        1. Stessa tabella_id
        2. Stessa pagina
        3. Stesso gruppo prodotto (brand coerente)
        4. Stessa classe/taglia commerciale (intersezione taglie non vuota)
        Genera relazioni di tipo PDF_TABLE_PAIRING_VERIFIED.
        """
        if not self._table_context_index or not getattr(self._table_context_index, "_contexts", None):
            return

        raw_contexts = self._table_context_index._contexts
        tables: Dict[Tuple[str, int], List[Dict[str, Any]]] = collections.defaultdict(list)

        def add_table_entry(tid: Optional[str], page: Optional[int], brand: Optional[str], family: Optional[str], c_code: str, c_ctx: Dict[str, Any]):
            if not tid or not page:
                return
            m_name = (c_ctx.get("model") or "").upper()
            if "OPTIONAL" in m_name or "CHIAVETTA" in m_name or "COMANDO" in m_name:
                return
            is_ui = c_code in self._ac_master_uis or m_name.startswith("U.I.") or "UNITA INTERNA" in m_name
            is_ue = c_code in self._ac_master_ues or m_name.startswith("U.E.") or "UNITA ESTERNA" in m_name or "MOTOCONDENSANTE" in m_name
            if not (is_ui or is_ue):
                return
            c_sizes = self._extract_commercial_sizes(c_code, c_ctx)
            tables[(tid, int(page))].append({
                "code": c_code,
                "is_ui": is_ui,
                "is_ue": is_ue,
                "sizes": c_sizes,
                "brand": (brand or "").strip().upper(),
                "family": family,
                "model": c_ctx.get("model"),
                "table_id": tid,
                "page": int(page)
            })

        for code, ctx in raw_contexts.items():
            add_table_entry(ctx.get("table_id"), ctx.get("page"), ctx.get("brand"), ctx.get("catalog_family"), code, ctx)
            for alt in ctx.get("alternate_table_contexts") or []:
                add_table_entry(alt.get("table_id"), alt.get("page"), alt.get("brand") or ctx.get("brand"), alt.get("catalog_family") or ctx.get("catalog_family"), code, ctx)

        for (tid, page), items in tables.items():
            uis_in_t = [x for x in items if x["is_ui"]]
            ues_in_t = [x for x in items if x["is_ue"]]
            if not uis_in_t or not ues_in_t:
                continue

            for ui in uis_in_t:
                for ue in ues_in_t:
                    if ui["brand"] and ue["brand"] and ui["brand"] != ue["brand"]:
                        continue
                    common = ui["sizes"].intersection(ue["sizes"])
                    if common:
                        rep_size = sorted(list(common), key=lambda x: (len(x), x), reverse=True)[0]
                        pair_meta = {
                            "table_id": tid,
                            "page": page,
                            "brand": ui["brand"] or ue["brand"],
                            "family": ui["family"] or ue["family"],
                            "commercial_size": rep_size,
                            "confidence": 0.99
                        }
                        if not any(p["target_code"] == ue["code"] for p in self._pdf_table_pairs_ui_to_ue[ui["code"]]):
                            self._pdf_table_pairs_ui_to_ue[ui["code"]].append({**pair_meta, "target_code": ue["code"]})
                        if not any(p["target_code"] == ui["code"] for p in self._pdf_table_pairs_ue_to_ui[ue["code"]]):
                            self._pdf_table_pairs_ue_to_ui[ue["code"]].append({**pair_meta, "target_code": ui["code"]})

    def _init_dynamic_capacity_classes(self) -> None:
        """Costruisce dinamicamente la mappa brand + capacity_class -> BTU dal master con voto a maggioranza."""
        raw_counts: Dict[Tuple[str, str], Dict[int, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        for c, ui in self._ac_master_uis.items():
            brand = str(ui.get("brand") or "").strip().upper()
            btu = ui.get("taglia_btu")
            if not brand or not btu:
                continue
            name = str(ui.get("name") or "").upper()
            mfg = str(ui.get("mfg_code") or "").upper()
            combined = f"{name} {mfg}"

            digits_found = re.findall(
                r'(?:AS|AD|AF|JSGNW|MHGNW|LSGND|FTX[A-Z]|MSZ-[A-Z]+|CS-[A-Z]+|ALYA-|ELEGANCE\s*|XTREME\s*PRO\s*|HI\s*COMFORT\s*)(\d{2})',
                combined
            )
            if not digits_found:
                digits_found = re.findall(r'\b[A-Z]{1,4}(\d{2})[A-Z0-9\-]*\b', combined)

            for d in set(digits_found):
                raw_counts[(brand, d)][btu] += 1

        self._dynamic_capacity_class_map = {}
        for key, btu_counts in raw_counts.items():
            best_btu = max(btu_counts, key=btu_counts.get)
            self._dynamic_capacity_class_map[key] = best_btu

    def _init_dynamic_series_vocabulary(self) -> None:
        """Costruisce dinamicamente il vocabolario canonico delle serie/famiglie dal compatibility master."""
        STOPWORDS = {
            'COMMERCIALE', 'SERIE COMMERCIALE', 'MONO SPLIT', 'MULTI SPLIT',
            'CANALIZZATO', 'CASSETTA', 'PAVIMENTO', 'CONSOLE', 'COLONNA', 'SOFFITTO',
            'R32', 'R-32', 'R410A', 'INVERTER', 'WHITE', 'BLACK', 'SILVER', 'MATT',
            'WIFI', 'WI-FI',
            'PARETE', 'LIGHT COMMERCIAL', 'SUPER MATCH',
            'SPLIT', 'DUAL', 'TRIAL', 'QUADRI', 'PENTA', 'MULTI', 'MONO',
            'CLIMATIZZATORE', 'CONDIZIONATORE', 'CLIMATIZZATORI', 'CONDIZIONATORI',
            'GAS', 'SERIE', 'GAMMA', 'LINEA', 'CLASSE', 'UNITA', 'ESTERNA', 'INTERNA',
            'MOTOCONDENSANTE', 'SISTEMA', 'UNITA ESTERNA', 'UNITA INTERNA',
            'TRIFASE', 'MONOFASE', '400V', '230V', 'TRIF', 'MONOF', 'TRIFASE T', 'MONOFASE M',
            'OPTIONAL', 'COMANDO', 'COMANDO INCLUSO', 'INCLUSO', 'A++', 'A+', 'A+++', 'BTU'
        }

        self._series_aliases = {
            "HI COMFORT": ["HI-COMFORT", "HICOMFORT"],
            "EASY SMART": ["EASY-SMART"],
            "ELEGANCE": ["EVOL/ELEG", "ELEG"],
            "XTREME PRO": ["XTREME", "XTREME-PRO"],
            "BREEZELESS": ["BREEZELESS+", "BREEZELESS E"],
            "FLEXIS PLUS": ["FLEXIS"],
            "EXPERT": ["EXPERT NORDIC"],
            "RZ2GT": ["LIGHTCOMM RZ2GT", "RZ2GND"]
        }

        raw_terms = set()
        for d in [self._ac_master_uis, self._ac_master_ues]:
            for c, it in d.items():
                for fld in ['serie', 'famiglia_catalogo']:
                    val = it.get(fld)
                    if val and isinstance(val, str):
                        raw_terms.add(val.strip())
                        for part in re.split(r'[/()]', val):
                            cp = part.strip()
                            if len(cp) >= 3:
                                raw_terms.add(cp)
                name = it.get('name') or ''
                words = [w for w in re.findall(r'[A-Z0-9\+\-]+', name) if len(w) >= 4]
                for w in words:
                    if w not in STOPWORDS and not any(w.startswith(p) for p in ['MULTI', 'COMM', 'ATT', '1U', '2U', '3U', '4U', '5U']):
                        raw_terms.add(w)

        for k in self._series_aliases.keys():
            raw_terms.add(k)

        filtered_vocab = set()
        for t in raw_terms:
            tu = t.strip().upper()
            if not tu or len(tu) < 3 or tu in STOPWORDS:
                continue
            if tu.isdigit():
                continue
            if re.fullmatch(r'\d+[A-Z]?', tu) or re.fullmatch(r'\d+\+\d+', tu) or re.fullmatch(r'\d+BTU', tu) or re.fullmatch(r'\d+KW', tu):
                continue
            filtered_vocab.add(tu)

        self._series_vocab = sorted(
            filtered_vocab,
            key=len,
            reverse=True
        )

    @property
    def name(self) -> str:
        return "CLIMA"

    def get_catalog_label_extractors(self) -> List[Any]:
        """
        Restituisce estrattori di sigle modello commerciali da catalogo specifici per il clima.
        Estrae sigle commerciali direttamente dai nomi a catalogo per tutti i brand.
        """
        patterns = [
            # Bosch
            r'\b(5000M\s*\d+/\d+\s*E)\b',
            # Haier UEs e UIs
            r'\b([1-5]U\d{2}[A-Z0-9\-\/]+)\b',
            r'\b(A[SDF]\d{2}[A-Z0-9\-\/]+)\b',
            # Baxi UEs e UIs
            r'\b(LSGT\d{2,3}-[1-5][A-Z0-9]*)\b',
            r'\b(LSGND\d{2,3}-[A-Z0-9]+)\b',
            r'\b([JM]SGNW\d{2})\b',
            r'\b(RZ2G[A-Z0-9\-\/]+)\b',
            # Midea UEs e UIs
            r'\b(M[2-5]O[A-Z0-9\-\/]+)\b',
            r'\b(MO[A-Z0-9\-\/]+U-[0-9]+[A-Z0-9\-]*)\b',
            r'\b([A-Z0-9]+-[0-9]+(?:IU|OU|HFN[0-9\-Q]*))\b',
            # Daikin
            r'\b([2-5]MXM\d{2}[A-Z0-9]*)\b',
            r'\b([FR]TX[A-Z]\d{2}[A-Z0-9]*)\b',
            # Mitsubishi
            r'\b(M[XSU]Z-[A-Z0-9\-\/]+)\b',
            # Panasonic
            r'\b(C[US]-[0-9A-Z\-\/]+)\b',
            # Hisense
            r'\b([2-5]AMW\d{2}[A-Z0-9]*)\b',
            r'\b([A-Z]{2}\d{2}[A-Z0-9]{3,})\b',
            # Samsung
            r'\b(AJ\d{3}[A-Z0-9]*)\b'
        ]
        compiled_regexes = [re.compile(p, re.IGNORECASE) for p in patterns]

        def extract_ac_labels(item: Dict[str, Any]) -> List[Dict[str, Any]]:
            brand = str(item.get("brand") or "").strip().upper()
            name = str(item.get("name") or "")
            labels = []
            seen = set()

            for rx in compiled_regexes:
                for m in rx.finditer(name):
                    raw_lbl = m.group(1).strip()
                    norm = re.sub(r'[^a-zA-Z0-9]', '', raw_lbl).lower()
                    if norm and norm not in seen:
                        seen.add(norm)
                        labels.append({
                            "raw_label": raw_lbl,
                            "normalized_label": norm,
                            "brand": brand,
                            "source_field": "name",
                            "provenance": "unified_catalog_master.name"
                        })
            return labels

        return [extract_ac_labels]

    def evaluate_domain_confidence(
        self,
        query: str,
        exact_items: List[Dict[str, Any]],
        detected_brand: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        evidences: List[str] = []
        conf = 0.0

        # 1. Segnale primario: anagrafica catalogo associata ai token esatti
        for it in exact_items:
            code = str(it.get("code") or "")
            if code in self._ac_master_uis or code in self._ac_master_ues:
                conf = 0.95
                evidences.append("exact_token_in_ac_master")
                break
            cat_r = it.get("category_root") or ""
            cat_p = it.get("category_path") or ""
            if cat_r == "CONDIZIONAMENTO" or cat_p.startswith("CONDIZIONAMENTO"):
                conf = max(conf, 0.90)
                evidences.append("exact_token_category_condizionamento")
                break

        # 2. Segnale secondario: lessico tecnico specifico della query
        q_low = query.lower()
        matched_kw = [kw for kw in CLIMA_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', q_low)]
        if matched_kw:
            conf = max(conf, 0.85)
            evidences.append(f"matched_clima_keywords:{','.join(matched_kw[:3])}")

        # 2.5 Segnale di serie / famiglia clima nota (es. Astra, Expert, Elegance, ecc.)
        q_up = query.upper()
        if self._table_context_index and detected_brand:
            family_request = self._table_context_index.analyze_query(query, detected_brand)
            if family_request.get("requested_family_key"):
                conf = max(conf, 0.90)
                evidences.append(f"matched_table_family:{family_request['requested_family_key']}")

        for s in self._series_vocab:
            if len(s) >= 4 and re.search(r'\b' + re.escape(s) + r'\b', q_up):
                conf = max(conf, 0.85)
                evidences.append(f"matched_clima_series:{s}")
                break

        # 3. Brand prior: debole priorità aggiuntiva (max 0.10)
        if detected_brand and detected_brand.upper() in ["DAIKIN", "MITSUBISHI", "PANASONIC", "HAIER", "HISENSE", "MIDEA", "SAMSUNG", "TOSHIBA"]:
            conf = min(1.0, conf + 0.05)
            evidences.append("known_ac_brand_weak_prior")

        return conf, evidences

    def get_category_filter(self) -> Optional[str]:
        return "CONDIZIONAMENTO"

    def filter_candidate(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> bool:
        code = str(item.get("code") or "")
        # Priorità 1: appartenenza al master compatibilità clima
        if code in self._ac_master_uis or code in self._ac_master_ues:
            return True

        # Priorità 2: category root/path di catalogo
        cat_root = item.get("category_root") or (item.get("category_path") or "").split(" > ")[0].strip()
        if cat_root == "CONDIZIONAMENTO":
            return True

        return False

    def extract_query_context(self, query: str) -> Dict[str, Any]:
        q_u = query.upper()
        btus = extract_split_capacities(query)

        # Riconoscimento esplicito Product Scope / Topology:
        # UI_ONLY: "UNITÀ INTERNA", "UNITA INTERNA", riferimenti espliciti a sola UI.
        # UE_ONLY: "UNITÀ ESTERNA", "UNITA ESTERNA", "MOTOCONDENSANTE", riferimenti espliciti a sola UE.
        # MULTISPLIT: DUAL, TRIAL, QUADRI, PENTA, MULTISPLIT o più taglie BTU.
        # MONOSPLIT: solo quando dichiarato "MONOSPLIT"/"MONO SPLIT" oppure come fallback da una singola taglia BTU se NON UI_ONLY o UE_ONLY.
        # Priorità: UI_ONLY / UE_ONLY > inferenza MONOSPLIT da singola taglia BTU.
        has_ui_explicit = bool(re.search(r'\b(UNIT[AÀ]\s+INTERNA|UNITA\s+INTERNA|SOLO\s+UI|SOLO\s+UNIT[AÀ]\s+INTERNA)\b', q_u))
        has_ue_explicit = bool(re.search(r'\b(UNIT[AÀ]\s+ESTERNA|UNITA\s+ESTERNA|MOTOCONDENSANTE|SOLO\s+UE|SOLO\s+UNIT[AÀ]\s+ESTERNA)\b', q_u))
        has_multi_kw = any(k in q_u for k in ['DUAL', 'TRIAL', 'QUADRI', 'PENTA', 'MULTISPLIT', 'MULTI SPLIT'])
        has_mono_kw = any(k in q_u for k in ['MONOSPLIT', 'MONO SPLIT'])

        is_multi = has_multi_kw or len(btus) > 1

        if has_ui_explicit and has_ue_explicit:
            product_scope = "MULTISPLIT" if is_multi else "MONOSPLIT"
            product_scope_source = "QUERY_EXPLICIT_CONFIGURATION"
        elif has_ui_explicit and not has_ue_explicit:
            product_scope = "UI_ONLY"
            product_scope_source = "QUERY_EXPLICIT_ROLE"
        elif has_ue_explicit and not has_ui_explicit:
            product_scope = "UE_ONLY"
            product_scope_source = "QUERY_EXPLICIT_ROLE"
        elif is_multi:
            product_scope = "MULTISPLIT"
            product_scope_source = "QUERY_EXPLICIT_CONFIGURATION"
        elif has_mono_kw or len(btus) == 1:
            product_scope = "MONOSPLIT"
            product_scope_source = (
                "QUERY_EXPLICIT_CONFIGURATION"
                if has_mono_kw else "QUERY_CAPACITY_FALLBACK"
            )
        else:
            product_scope = "GENERAL"
            product_scope_source = "FALLBACK"

        is_ui_only = (product_scope == "UI_ONLY")
        is_ue_only = (product_scope == "UE_ONLY")
        is_monosplit = (product_scope == "MONOSPLIT")
        is_multisplit = (product_scope == "MULTISPLIT")
        has_commercial_kw = any(k in q_u for k in ['CASSETTA', 'CANALIZZAT', 'SOFFITTO', 'PAVIMENTO', 'CONSOLE'])

        # Rilevamento tipologia su 3 livelli:
        # 1. Esplicita con alta confidenza
        explicit_tipologia = None
        if any(k in q_u for k in ["CASSETTA", "CASSETTE"]):
            explicit_tipologia = "CASSETTA"
        elif any(k in q_u for k in ["CANALIZZAT", "CANALE"]):
            explicit_tipologia = "CANALIZZATO"
        elif any(k in q_u for k in ["PAVIMENTO", "CONSOLLE", "CONSOLE"]):
            explicit_tipologia = "PAVIMENTO"
        elif any(k in q_u for k in ["SOFFITTO", "CEILING"]):
            explicit_tipologia = "SOFFITTO"
        elif any(k in q_u for k in ["PARETE", "MURO", "WALL"]):
            explicit_tipologia = "PARETE"

        # 2. Probabile (desunta da pattern o serie specifiche)
        probable_tipologia = None
        if not explicit_tipologia:
            if any(k in q_u for k in ["SFZ", "MFZ"]):
                probable_tipologia = "PAVIMENTO"
            elif any(k in q_u for k in ["MLZ", "SLZ"]):
                probable_tipologia = "CASSETTA"
            elif any(k in q_u for k in ["SEZ", "PEZ", "FBA"]):
                probable_tipologia = "CANALIZZATO"
            elif any(k in q_u for k in [
                "ETHEREA", "PERFERA", "EMURA", "STYLISH", "SENSIRA", "COMFORA",
                "WINDFREE", "CEBU", "ELITE", "AVANT", "EDGE", "HAORI", "SHORAI",
                "MSZ-AY", "MSZ-EF", "MSZ-BT", "MSZ-HR", "CLIMATE 3000", "CLIMATE 5000"
            ]):
                probable_tipologia = "PARETE"

        # Rilevamento serie/famiglia richiesta dal vocabolario canonico
        TECHNICAL_TOKENS = {
            "WIFI", "WI-FI", "R32", "R-32", "R410A", "INVERTER", "BTU",
            "CLASSE", "A++", "A+", "A+++", "OPTIONAL", "COMANDO",
            "COMANDO INCLUSO", "INCLUSO", "TRIFASE", "MONOFASE", "400V", "230V",
            "TRIF", "MONOF", "TRIFASE T", "MONOFASE M"
        }
        technical_norms = {re.sub(r'[^A-Z0-9]', '', t) for t in TECHNICAL_TOKENS}

        requested_series = None
        matched_series = []
        for term in self._series_vocab:
            if re.search(r'\b' + re.escape(term) + r'\b', q_u):
                norm_t = re.sub(r'[^A-Z0-9]', '', term)
                if term not in TECHNICAL_TOKENS and norm_t not in technical_norms:
                    matched_series.append(term)
        for canon, alts in self._series_aliases.items():
            if canon in matched_series:
                continue
            norm_c = re.sub(r'[^A-Z0-9]', '', canon)
            if canon in TECHNICAL_TOKENS or norm_c in technical_norms:
                continue
            for a in alts:
                if re.search(r'\b' + re.escape(a) + r'\b', q_u):
                    matched_series.append(canon)
                    break
        if matched_series:
            matched_series.sort(key=len, reverse=True)
            requested_series = matched_series[0]

        # Rilevamento colore
        requested_color = None
        for col in ["NERO", "BLACK", "BIANCO", "WHITE", "BCO", "SILVER", "GRIGIO"]:
            if re.search(r'\b' + col + r'\b', q_u):
                requested_color = col
                break

        # Rilevamento attributi tecnici / feature (NON possono mai creare family)
        phase = None
        if re.search(r'\b(TRIFASE|TRIF|400V)\b', q_u):
            phase = "TRIFASE"
        elif re.search(r'\b(MONOFASE|MONOF|230V)\b', q_u):
            phase = "MONOFASE"

        feature_wifi = bool(re.search(r'\b(WI-?FI)\b', q_u))
        feature_inverter = bool(re.search(r'\bINVERTER\b', q_u))
        feature_r32 = bool(re.search(r'\b(R-?32)\b', q_u))
        feature_optional = bool(re.search(r'\bOPTIONAL\b', q_u))
        feature_comando = bool(re.search(r'\bCOMANDO\b', q_u))

        return {
            "query_text": query,
            "requested_btus": btus,
            "requested_series": requested_series,
            "requested_color": requested_color,
            "phase": phase,
            "feature_wifi": feature_wifi,
            "feature_inverter": feature_inverter,
            "feature_r32": feature_r32,
            "feature_optional": feature_optional,
            "feature_comando": feature_comando,
            "is_trifase": phase == "TRIFASE",
            "is_monofase": phase == "MONOFASE",
            "product_scope": product_scope,
            "product_scope_source": product_scope_source,
            "is_ui_only": is_ui_only,
            "is_multisplit": is_multisplit,
            "is_monosplit": is_monosplit,
            "is_ue_only": is_ue_only,
            "has_commercial_kw": has_commercial_kw,
            "explicit_tipologia": explicit_tipologia,
            "probable_tipologia": probable_tipologia,
            "is_machine_query": True
        }

    def evaluate_series_match(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        req_ser = query_context.get("requested_series")
        req_key = str(query_context.get("requested_family_key") or "").strip()
        req_brand = str(query_context.get("requested_brand") or "").strip().upper()
        item_brand = str(item.get("brand") or "").strip().upper()
        candidate_keys = CatalogTableContextIndex.candidate_family_keys(item)

        if req_key and req_key in candidate_keys:
            item["_series_match_source"] = "PDF_LAYOUT"
            item["_table_family_match"] = "exact"
            item["_table_family_evidence"] = "TABLE_FAMILY_EXACT"
            item["_matched_table_family_key"] = req_key
            return "exact"

        if (
            req_key
            and req_brand
            and item_brand == req_brand
            and candidate_keys
            and item.get("table_source") == "PDF_LAYOUT"
        ):
            item["_series_match_source"] = "PDF_LAYOUT"
            item["_table_family_match"] = "mismatch"
            item["_table_family_evidence"] = "TABLE_FAMILY_MISMATCH"
            return "mismatch"

        if not req_ser:
            return "none"

        req_u = req_ser.upper()
        item_ser = (item.get("serie") or "").upper()
        item_fam = (item.get("famiglia_catalogo") or "").upper()
        item_name = (item.get("name") or "").upper()

        # Compatibility master is the second family source. It may fill a
        # missing PDF context, but never replace one.
        if req_u in item_ser or req_u in item_fam:
            item["_series_match_source"] = "COMPATIBILITY_MASTER"
            return "exact"

        req_aliases = self._series_aliases.get(req_u, [])
        for alias in req_aliases:
            if alias in item_ser or alias in item_fam:
                item["_series_match_source"] = "COMPATIBILITY_MASTER"
                return "alias"

        # Name is deliberately the last fallback and never creates a table tier.
        if re.search(r'\b' + re.escape(req_u) + r'\b', item_name):
            item["_series_match_source"] = "PRODUCT_NAME"
            return "exact"

        for alias in req_aliases:
            if re.search(r'\b' + re.escape(alias) + r'\b', item_name):
                item["_series_match_source"] = "PRODUCT_NAME"
                return "alias"

        # Family mismatches are meaningful only inside the requested brand.
        if req_brand and item_brand and req_brand != item_brand:
            return "none"

        for canon, alts in self._series_aliases.items():
            if canon == req_u or canon in req_aliases:
                continue
            for alt_t in [canon] + alts:
                if re.search(r'\b' + re.escape(alt_t) + r'\b', item_name):
                    item["_series_match_source"] = "PRODUCT_NAME"
                    return "mismatch"

        for term in ['ASTRA', 'SIDERA', 'EXPERT', 'FLEXIS', 'ELEGANCE', 'XTREME PRO', 'BREEZELESS', 'HI COMFORT', 'EASY SMART', 'AIR MASTER', 'RZ2GT', 'PERFERA', 'EMURA', 'STYLISH', 'SENSIRA', 'COMFORA', 'WINDFREE']:
            if term == req_u or term in req_aliases:
                continue
            if term in item_ser or term in item_fam:
                item["_series_match_source"] = "COMPATIBILITY_MASTER"
                return "mismatch"
            if re.search(r'\b' + re.escape(term) + r'\b', item_name):
                item["_series_match_source"] = "PRODUCT_NAME"
                return "mismatch"

        return "none"

    def assign_slot(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        self.enrich_item(item)
        if item.get("is_accessory"):
            slot_id = "slot_accessory"
        elif item.get("is_ue"):
            slot_id = "slot_ue"
        elif item.get("is_ui"):
            btu = item.get("taglia_btu")
            if btu:
                slot_id = f"slot_ui_{btu}"
            else:
                slot_id = "slot_ui"
        elif item.get("is_monoblocco_sue"):
            slot_id = "slot_monoblocco"
        else:
            slot_id = "slot_clima_general"
        item["slot_id"] = slot_id
        return slot_id

    def compute_domain_boost(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        self.enrich_item(item)
        boost = 0.0
        requested_btus = query_context.get("requested_btus", [])

        # Boost per UI con taglia richiesta esatta
        if item.get("is_ui") and requested_btus and item.get("taglia_btu") in requested_btus:
            boost += 25.0

        # Boost per UI se la query è specificamente per UI
        if query_context.get("is_ui_only") and item.get("is_ui"):
            boost += 15.0

        # Boost per UE se la query è specificamente per UE
        if query_context.get("is_ue_only") and item.get("is_ue"):
            boost += 15.0

        # Calcola e registra _series_match
        series_match = self.evaluate_series_match(item, query_context)
        item["_series_match"] = series_match

        if series_match in ("exact", "alias"):
            boost += 30.0
        elif series_match == "mismatch":
            boost -= 50.0

        # Colore
        req_color = query_context.get("requested_color")
        if req_color:
            name_u = (item.get("name") or "").upper()
            if req_color in name_u:
                item["_color_match"] = True
                boost += 15.0
            elif any(c in name_u for c in ["NERO", "BLACK", "BIANCO", "WHITE", "BCO", "SILVER"]):
                item["_color_mismatch"] = True
                boost -= 20.0

        return boost

    def expand_relations(
        self,
        anchor_items: List[Dict[str, Any]],
        lookup_dict: Dict[str, Any],
        query_context: Optional[Dict[str, Any]] = None
    ) -> List[TypedRelation]:
        relations: List[TypedRelation] = []
        ctx = query_context or {}
        requested_btus = ctx.get("requested_btus", [])
        is_mono = ctx.get("is_monosplit", False)
        has_commercial = ctx.get("has_commercial_kw", False)
        q_text = (ctx.get("query_text") or "").lower()

        for item in anchor_items:
            code = str(item.get("code") or "")
            self.enrich_item(item)

            # CASO 1: Anchor è UE
            if item.get("is_ue") and (code in self._ac_master_ues or code in self._pdf_table_pairs_ue_to_ui):
                seen_ui_codes = set()
                # 1. Priorità massima: coppie commerciali esplicite da tabella PDF (PDF_TABLE_PAIRING_VERIFIED)
                for pair in self._pdf_table_pairs_ue_to_ui.get(code, []):
                    ui_c = str(pair.get("target_code") or "")
                    if not ui_c:
                        continue
                    ui_rec = self._ac_master_uis.get(ui_c) or lookup_dict.get(ui_c) or {}
                    ui_btu = ui_rec.get("taglia_btu")
                    if requested_btus and ui_btu and ui_btu not in requested_btus:
                        continue
                    seen_ui_codes.add(ui_c)
                    relations.append(TypedRelation(
                        source_code=code,
                        target_code=ui_c,
                        relation_type=RelationType.PDF_TABLE_PAIRING_VERIFIED,
                        provenance=f"catalog_table_context.json:table_id={pair.get('table_id')}[p.{pair.get('page')}]",
                        target_role="UI",
                        evidence={
                            "ue_code": code,
                            "ui_code": ui_c,
                            "table_id": pair.get("table_id"),
                            "page": pair.get("page"),
                            "brand": pair.get("brand"),
                            "taglia_commerciale": pair.get("commercial_size"),
                        },
                        confidence=0.99
                    ))

                compat_uis = self._ac_master_ues.get(code, {}).get("unita_interne_compatibili", [])
                filtered_uis = []
                for ui_info in compat_uis:
                    ui_code = ui_info.get("code") or ui_info.get("codice_pt")
                    if not ui_code or ui_code in seen_ui_codes:
                        continue

                    ui_btu = ui_info.get("taglia_btu")
                    # Filtro 1: Taglia BTU (se richiesta esplicitamente)
                    if requested_btus and ui_btu and ui_btu not in requested_btus:
                        continue

                    # Filtro 2: Gestione tipologia su 3 livelli (mai dedurre PARETE dall'assenza di parole)
                    explicit_tipo = ctx.get("explicit_tipologia")
                    probable_tipo = ctx.get("probable_tipologia")
                    ui_tipo = (ui_info.get("tipologia") or "").upper()
                    ui_name = (ui_info.get("name") or ui_info.get("nome") or "").upper()

                    # Livello 1: Hard filter solo se tipologia esplicitamente identificata nella query
                    if explicit_tipo:
                        matches_explicit = (
                            ui_tipo == explicit_tipo or
                            (explicit_tipo == "CASSETTA" and "CASSETT" in ui_name) or
                            (explicit_tipo == "CANALIZZATO" and "CANALIZZ" in ui_name) or
                            (explicit_tipo == "PAVIMENTO" and ("PAVIMENTO" in ui_name or "CONSOL" in ui_name)) or
                            (explicit_tipo == "PARETE" and "PARETE" in ui_name) or
                            (explicit_tipo == "SOFFITTO" and "SOFFITTO" in ui_name)
                        )
                        if not matches_explicit:
                            continue

                    # Livello 2: Tipologia probabile -> soft boost
                    matches_probable = False
                    if probable_tipo:
                        if ui_tipo == probable_tipo or (probable_tipo in ui_name):
                            matches_probable = True

                    # Priorità per serie richiesta
                    ui_serie = (ui_info.get("serie") or ui_info.get("famiglia_catalogo") or "").lower()
                    serie_matched = any(w in ui_serie for w in re.findall(r'\w+', q_text) if len(w) >= 4)
                    filtered_uis.append((ui_info, ui_code, serie_matched, matches_probable))

                # Ordina: prima serie richiesta (priorità massima), poi tipologia probabile
                filtered_uis.sort(key=lambda x: (not x[2], not x[3]))

                for ui_info, ui_code, _, _ in filtered_uis:
                    relations.append(TypedRelation(
                        source_code=code,
                        target_code=ui_code,
                        relation_type=RelationType.COMPATIBLE_WITH,
                        provenance="climatizzatori_compatibilita_master.json:unita_esterne.unita_interne_compatibili",
                        target_role="UI",
                        evidence={
                            "ue_code": code,
                            "ui_code": ui_code,
                            "taglia_btu": ui_info.get("taglia_btu"),
                            "serie": ui_info.get("serie") or ui_info.get("famiglia_catalogo"),
                            "tipologia": ui_info.get("tipologia")
                        },
                        confidence=0.75
                    ))

            # CASO 2: Anchor è UI
            elif item.get("is_ui") and (code in self._ac_master_uis or code in self._pdf_table_pairs_ui_to_ue):
                ui_meta = self._ac_master_uis.get(code, {})

                candidate_ue_records: Dict[str, Tuple[Dict[str, Any], bool, bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = {}

                # 1. Da coppie commerciali esplicite da tabella PDF (PDF_TABLE_PAIRING_VERIFIED)
                for pair in self._pdf_table_pairs_ui_to_ue.get(code, []):
                    ue_c = str(pair.get("target_code") or "")
                    if ue_c:
                        ue_rec = dict(self._ac_master_ues.get(ue_c) or lookup_dict.get(ue_c) or {})
                        if self._table_context_index and "catalog_family" not in ue_rec:
                            ue_ctx = self._table_context_index.get(ue_c)
                            if ue_ctx:
                                ue_rec.update(ue_ctx)
                        candidate_ue_records[ue_c] = (ue_rec, True, False, None, pair)

                # 2. Da kit_commerciali_inclusi (kit espliciti dichiarati a catalogo)
                for k in ui_meta.get("kit_commerciali_inclusi", []):
                    ue_c = str(k.get("unita_esterna_codice") or "")
                    if ue_c:
                        ue_rec = dict(self._ac_master_ues.get(ue_c) or lookup_dict.get(ue_c) or {})
                        if self._table_context_index and "catalog_family" not in ue_rec:
                            ue_ctx = self._table_context_index.get(ue_c)
                            if ue_ctx:
                                ue_rec.update(ue_ctx)
                        if ue_c not in candidate_ue_records:
                            candidate_ue_records[ue_c] = (ue_rec, False, True, k, None)
                        else:
                            old = candidate_ue_records[ue_c]
                            candidate_ue_records[ue_c] = (old[0], old[1], True, k, old[4])

                # 3. Da unita_esterne_compatibili (layout / tabella compatibilità)
                for ue_info in ui_meta.get("unita_esterne_compatibili", []):
                    ue_c = str(ue_info.get("code") or ue_info.get("codice_pt") or "")
                    if ue_c and ue_c not in candidate_ue_records:
                        ue_rec = dict(self._ac_master_ues.get(ue_c) or lookup_dict.get(ue_c) or ue_info)
                        if self._table_context_index and "catalog_family" not in ue_rec:
                            ue_ctx = self._table_context_index.get(ue_c)
                            if ue_ctx:
                                ue_rec.update(ue_ctx)
                        candidate_ue_records[ue_c] = (ue_rec, False, False, None, None)

                # Valuta ogni UE candidata con le priorità discriminanti
                scored_candidates = []
                for ue_c, (ue_rec, from_pdf_table, from_kit, k_data, pair_info) in candidate_ue_records.items():
                    c_score = self.score_ue_for_ui_anchor(ue_rec, item, ctx)
                    if from_pdf_table:
                        c_score += 50.0  # priorità massima: PDF_TABLE_PAIRING_VERIFIED
                    elif from_kit:
                        c_score += 25.0  # priorità 2: kit esplicito dichiarato dal catalogo
                    else:
                        c_score += 10.0  # priorità 3: compatibilità master
                    scored_candidates.append((c_score, ue_c, ue_rec, from_pdf_table, from_kit, k_data, pair_info))

                scored_candidates.sort(key=lambda x: x[0], reverse=True)

                if is_mono and scored_candidates:
                    top_score, top_ue_c, top_ue_rec, top_from_pdf, top_from_kit, top_k, top_pair = scored_candidates[0]
                    if top_score > 0:
                        if top_from_pdf and top_pair:
                            # PDF_TABLE_PAIRING_VERIFIED: coppia commerciale esplicita da tabella PDF
                            relations.append(TypedRelation(
                                source_code=code,
                                target_code=top_ue_c,
                                relation_type=RelationType.PDF_TABLE_PAIRING_VERIFIED,
                                provenance=f"catalog_table_context.json:table_id={top_pair.get('table_id')}[p.{top_pair.get('page')}]",
                                target_role="UE",
                                evidence={
                                    "ui_code": code,
                                    "ue_code": top_ue_c,
                                    "table_id": top_pair.get("table_id"),
                                    "page": top_pair.get("page"),
                                    "brand": top_pair.get("brand"),
                                    "taglia_commerciale": top_pair.get("commercial_size"),
                                    "discriminant_score": top_score
                                },
                                confidence=0.99
                            ))
                        elif top_from_kit and top_k and top_k.get("id_kit"):
                            # PAIRED_WITH_VERIFIED: solo kit/coppie esplicitamente dichiarate dal catalogo
                            relations.append(TypedRelation(
                                source_code=code,
                                target_code=top_ue_c,
                                relation_type=RelationType.PAIRED_WITH_VERIFIED,
                                provenance=f"climatizzatori_compatibilita_master.json:kit_commerciali_inclusi[id_kit={top_k.get('id_kit')}]",
                                target_role="UE",
                                evidence={
                                    "ui_code": code,
                                    "ue_code": top_ue_c,
                                    "id_kit": top_k.get("id_kit"),
                                    "nome_kit": top_k.get("nome_kit"),
                                    "discriminant_score": top_score
                                },
                                confidence=0.95
                            ))
                        else:
                            # PAIRED_WITH_DERIVED: UI anchor -> UE derivata da tabella compatibilità/layout
                            relations.append(TypedRelation(
                                source_code=code,
                                target_code=top_ue_c,
                                relation_type=RelationType.PAIRED_WITH_DERIVED,
                                provenance="climatizzatori_compatibilita_master.json:unita_interne.unita_esterne_compatibili[monosplit_derived]",
                                target_role="UE",
                                evidence={
                                    "ui_code": code,
                                    "ue_code": top_ue_c,
                                    "tipo_sistema": "Mono-Split",
                                    "serie": top_ue_rec.get("serie") or top_ue_rec.get("famiglia_catalogo"),
                                    "discriminant_score": top_score
                                },
                                confidence=0.90
                            ))

                        # Altre UE compatibili: COMPATIBLE_WITH
                        for sc, oth_ue_c, oth_ue_rec, _, _, _, _ in scored_candidates[1:]:
                            if sc > -30:
                                relations.append(TypedRelation(
                                    source_code=code,
                                    target_code=oth_ue_c,
                                    relation_type=RelationType.COMPATIBLE_WITH,
                                    provenance="climatizzatori_compatibilita_master.json:unita_interne.unita_esterne_compatibili",
                                    target_role="UE",
                                    evidence={
                                        "ui_code": code,
                                        "ue_code": oth_ue_c,
                                        "discriminant_score": sc
                                    },
                                    confidence=0.60
                                ))
                else:
                    for sc, ue_c, ue_rec, _, _, _, _ in scored_candidates:
                        relations.append(TypedRelation(
                            source_code=code,
                            target_code=ue_c,
                            relation_type=RelationType.COMPATIBLE_WITH,
                            provenance="climatizzatori_compatibilita_master.json:unita_interne.unita_esterne_compatibili",
                            target_role="UE",
                            evidence={
                                "ui_code": code,
                                "ue_code": ue_c,
                                "discriminant_score": sc
                            },
                            confidence=0.70
                        ))

        return relations

    def select_ui_anchors(
        self,
        candidates: Any,
        query_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Seleziona candidati UI con forte evidenza di identità da utilizzare come anchor
        per relation expansion inversa (UI -> UE) quando non è presente una UE anchor nella query.
        """
        target_brand = (query_context.get("detected_brand") or "").strip().upper()
        requested_btus = query_context.get("requested_btus", [])
        explicit_tipologia = query_context.get("explicit_tipologia")
        requested_key = query_context.get("requested_family_key")
        q_u = (query_context.get("query_text") or "").upper()

        scored_uis: List[Tuple[float, Dict[str, Any]]] = []
        for it in candidates:
            code = str(it.get("code") or "")
            if not (it.get("is_ui") or code in self._ac_master_uis or code in self._pdf_table_pairs_ui_to_ue):
                continue
            item_brand = (it.get("brand") or "").strip().upper()
            if target_brand and item_brand and target_brand != item_brand:
                continue

            score = 0.0
            btu = it.get("taglia_btu")
            if requested_btus and btu and btu in requested_btus:
                score += 50.0

            it_tipo = (it.get("tipologia") or "").upper()
            it_name = (it.get("name") or "").upper()
            if explicit_tipologia:
                if (
                    it_tipo == explicit_tipologia or
                    (explicit_tipologia == "CANALIZZATO" and "CANALIZZ" in it_name) or
                    (explicit_tipologia == "CASSETTA" and "CASSETT" in it_name) or
                    (explicit_tipologia == "PAVIMENTO" and ("PAVIMENTO" in it_name or "CONSOL" in it_name)) or
                    (explicit_tipologia == "PARETE" and "PARETE" in it_name) or
                    (explicit_tipologia == "SOFFITTO" and "SOFFITTO" in it_name)
                ):
                    score += 40.0

            cand_keys = CatalogTableContextIndex.candidate_family_keys(it)
            if requested_key and requested_key in cand_keys:
                score += 30.0

            mfg = (it.get("mfg_code") or "").upper()
            model_tokens = re.findall(r'[A-Z0-9]{3,}', q_u)
            matched_toks = 0
            for tok in model_tokens:
                if tok in ("CLIMATIZZATORE", "CONDIZIONATORE", "INVERTER", "MONOSPLIT", "TRIFASE", "MONOFASE", "OPTIONAL", "BOSCH", "DAIKIN", "MITSUBISHI", "MIDEA", "HAIER", "BAXI", "SAMSUNG", "PANASONIC", "BTU"):
                    continue
                if tok in it_name or tok in mfg:
                    matched_toks += 1
            if matched_toks > 0:
                score += min(matched_toks * 15.0, 45.0)

            # Penalità per mismatch di colore (es. NERO quando non richiesto)
            if any(c in it_name for c in ("NERO", "NER", "BLACK")) and not any(c in q_u for c in ("NERO", "BLACK", "NER")):
                score -= 20.0

            if it.get("table_source") == "PDF_LAYOUT":
                score += 10.0

            if score >= 60.0:
                scored_uis.append((score, it))

        scored_uis.sort(key=lambda x: (x[0], float(x[1].get("_relevance_score") or 0.0)), reverse=True)
        if not scored_uis:
            return []

        if query_context.get("is_multisplit") and len(requested_btus) > 1:
            selected_by_btu = {}
            for sc, it in scored_uis:
                b = it.get("taglia_btu")
                if b and b not in selected_by_btu:
                    it["_is_ui_anchor"] = True
                    selected_by_btu[b] = it
            return list(selected_by_btu.values())

        best = scored_uis[0][1]
        best["_is_ui_anchor"] = True
        return [best]

    def score_ue_for_ui_anchor(
        self,
        ue_item: Dict[str, Any],
        ui_item: Dict[str, Any],
        query_context: Dict[str, Any]
    ) -> float:
        """
        Calcola il punteggio di selezione della UE a partire da una UI anchor
        seguendo rigidamente l'ordine di priorità:
        1. Stessa tabella PDF
        2. Stesso family_key
        3. Stessa capacità commerciale (kW <-> BTU)
        4. Stessa classe modello
        5. Stessa fase elettrica
        6. Compatibilità master
        """
        score = 0.0

        # 1. Stessa tabella PDF
        ui_page = ui_item.get("table_page") or (ui_item.get("table_context") or {}).get("page") or ui_item.get("primary_page")
        ue_page = ue_item.get("table_page") or (ue_item.get("table_context") or {}).get("page") or ue_item.get("primary_page")
        ui_tid = ui_item.get("table_id") or (ui_item.get("table_context") or {}).get("table_id")
        ue_tid = ue_item.get("table_id") or (ue_item.get("table_context") or {}).get("table_id")
        if ui_tid and ue_tid and ui_tid == ue_tid:
            score += 100.0
        elif ui_page and ue_page and int(ui_page) == int(ue_page):
            score += 80.0

        # 2. Stesso family_key
        ui_fk = ui_item.get("family_key")
        ue_fk = ue_item.get("family_key")
        if ui_fk and ue_fk and ui_fk == ue_fk:
            score += 60.0
        elif (ui_item.get("catalog_family") or "").strip().upper() == (ue_item.get("catalog_family") or "").strip().upper() and (ui_item.get("catalog_family") or "").strip():
            score += 40.0

        # 3. Stessa capacità commerciale
        ui_btu = ui_item.get("taglia_btu")
        ue_kw = float(ue_item.get("potenza_nominale_kw") or ue_item.get("potenza_kw") or ue_item.get("taglia_kw") or 0.0)
        if ui_btu and ue_kw > 0.0:
            expected_kw = capacity_kw_for_btu(ui_btu)
            diff = abs(ue_kw - expected_kw)
            if diff <= 1.5:
                score += 50.0
            elif diff <= 3.0:
                score += 10.0
            else:
                score -= 100.0

        # 4. Stessa classe modello
        ui_name = (ui_item.get("name") or ui_item.get("nome") or "").upper()
        ue_name = (ue_item.get("name") or ue_item.get("nome") or "").upper()
        ui_tags = set(re.findall(r'(?:RZ2G[A-Z]+|LSG[A-Z]+|[A-Z]{2,})(\d{2,3})\b', ui_name))
        ue_tags = set(re.findall(r'(?:RZ2G[A-Z]+|LSG[A-Z]+|[A-Z]{2,})(\d{2,3})\b', ue_name))
        common_tags = ui_tags.intersection(ue_tags) - {'32', '410'}
        if common_tags:
            score += 40.0

        # 5. Stessa fase elettrica
        req_phase = query_context.get("phase")
        is_ue_trifase = bool(re.search(r'(?:\bT\b|TRIFASE|400V)', ue_name))
        if req_phase == "TRIFASE":
            if is_ue_trifase:
                score += 30.0
            else:
                score -= 80.0
        elif req_phase == "MONOFASE":
            if not is_ue_trifase:
                score += 30.0
            else:
                score -= 80.0

        return score

    def get_slot_quotas(self, query_context: Dict[str, Any], limit: int) -> List[SlotConfig]:
        configs: List[SlotConfig] = []
        is_ui_only = query_context.get("is_ui_only", False)
        is_ue_only = query_context.get("is_ue_only", False)
        requested_btus = query_context.get("requested_btus", [])
        has_reliable_anchor = query_context.get("has_reliable_anchor", True)

        if is_ui_only:
            unique_btus = []
            for b in requested_btus:
                if b not in unique_btus:
                    unique_btus.append(b)
            prio = 10 if has_reliable_anchor else 0
            min_res = 1 if has_reliable_anchor else 0
            if unique_btus:
                for btu in unique_btus:
                    configs.append(SlotConfig(slot_id=f"slot_ui_{btu}", priority=prio, min_reserved=min_res, max_candidates=limit))
            else:
                configs.append(SlotConfig(slot_id="slot_ui", priority=prio, min_reserved=min_res, max_candidates=limit))
            return configs

        if is_ue_only:
            prio = 10 if has_reliable_anchor else 0
            min_res = 1 if has_reliable_anchor else 0
            configs.append(SlotConfig(slot_id="slot_ue", priority=prio, min_reserved=min_res, max_candidates=limit))
            return configs

        # Deduplica le taglie richieste mantenendo l'ordine di apparizione
        # Molteplicità (es. 9+9) vive nella ExpectedBOM, non crea slot duplicati
        unique_btus = []
        for b in requested_btus:
            if b not in unique_btus:
                unique_btus.append(b)

        # Calcola quote dinamiche in base al numero di slot attivi
        num_slots = 1 + len(unique_btus)  # 1 slot_ue + N slot UI
        dynamic_quota = max(3, min(8, limit // num_slots if num_slots > 0 else 6))

        # Lo slot UE ha priorità e min_reserved=1 solo quando esiste un anchor affidabile
        # (se c'è solo near-model candidate, min_reserved=0)
        prio_ue = 10 if has_reliable_anchor else 0
        min_res_ue = 1 if has_reliable_anchor else 0
        configs.append(SlotConfig(slot_id="slot_ue", priority=prio_ue, min_reserved=min_res_ue, max_candidates=dynamic_quota))

        # Aggiungi slot per ciascuna taglia UI richiesta
        for btu in unique_btus:
            configs.append(SlotConfig(slot_id=f"slot_ui_{btu}", priority=5, min_reserved=0, max_candidates=dynamic_quota))

        # Fallback slot_ui generico
        configs.append(SlotConfig(slot_id="slot_ui", priority=0, min_reserved=0, max_candidates=max(2, dynamic_quota // 2)))

        return configs

    def enrich_item(self, item: Dict[str, Any]) -> None:
        """Arricchisce l'articolo clima con tag UE/UI/BTU/KW e accessori."""
        if self._table_context_index is not None:
            self._table_context_index.enrich_item(item)
        if "_ac_enriched" in item:
            return
        item["_ac_enriched"] = True

        code = str(item.get("code") or "").strip()
        name = (item.get("name") or "").upper()
        mfg = (item.get("mfg_code") or "").upper()
        cat = (item.get("category_path") or "").upper()

        # Product-name detection is only the last fallback. The PDF context
        # and the compatibility master below have higher priority.
        if self._table_context_index is not None and not item.get("catalog_family"):
            for family in self._series_vocab:
                if re.search(r'\b' + re.escape(family) + r'\b', name):
                    self._table_context_index.apply_family_fallback(
                        item, family, "PRODUCT_NAME", priority=4
                    )
                    break

        # 0. Accessori e ricambi
        is_accessory = (
            "ACCESSORI" in cat or
            "RICAMBI" in cat or
            item.get("is_accessory") or
            any(name.startswith(k) or f" {k}" in name for k in [
                "GRIGLIA", "PANNELLO", "COMANDO", "TERMOSTATO",
                "FILTRO", "RACCORDO", "KIT SCARIC", "KIT FUMI", "KIT SDOPP", "KIT COASS",
                "KIT RACC", "KIT TUBI", "VALVOLA", "DIMA", "CONTROCASSA", "CASSA COPERTURA",
                "PIEDINI", "DEFLETTORE", "SONDA", "TAPPO", "BASETTA", "CAVO", "SCHEDA",
                "CENTRALINA", "MOTORE ELET", "BRUCIATORE", "DEUMIDIFICATORE", "ESTENS GARANZIA"
            ])
        ) and not any(k in name for k in ["VENTILCONV", "CALDAIA", "SCALDABAGNO", "CLIMATIZZATORE"])

        if is_accessory:
            item["is_accessory"] = True
            item["is_ui"] = False
            item["is_ue"] = False
            item["taglia_btu"] = None
            item["taglia_kw"] = None
            return

        # 1. Unità Esterne (UE)
        if self._ac_master_ues and code in self._ac_master_ues:
            ue_meta = self._ac_master_ues[code]
            item["tipo_unita"] = "UE"
            item["is_ue"] = True
            item["is_ui"] = False
            item["porte_attacchi"] = ue_meta.get("porte_attacchi")
            item["max_ui_collegabili"] = ue_meta.get("max_ui_collegabili")
            item["tipo_sistema"] = ue_meta.get("tipo_sistema")
            item["famiglia_catalogo"] = ue_meta.get("famiglia_catalogo")
            if self._table_context_index is not None:
                self._table_context_index.apply_family_fallback(
                    item,
                    ue_meta.get("famiglia_catalogo") or ue_meta.get("serie"),
                    "COMPATIBILITY_MASTER",
                    priority=2,
                )
            item["serie"] = ue_meta.get("serie")
            item["refrigerante"] = ue_meta.get("refrigerante")
            item["primary_page"] = ue_meta.get("primary_page") or ue_meta.get("pagina_catalogo")
            item["taglia_btu"] = None
            kw_val = ue_meta.get("potenza_nominale_kw")
            if kw_val:
                item["taglia_kw"] = kw_val
                item["tag_kw"] = f"{kw_val} kW"
                item["tag_kw_display"] = f"{kw_val} kW"
            return

        is_ue_text = (
            any(name.startswith(p) or f" {p}" in name for p in ["UE ", "U.E. ", "UNITA ESTERNA", "UNITA' ESTERNA", "MOTOCONDENSANTE"]) or
            (self._pdf_specs and code in self._pdf_specs and self._pdf_specs[code].get("is_ue"))
        )
        if is_ue_text:
            item["tipo_unita"] = "UE"
            item["is_ue"] = True
            item["is_ui"] = False
            item["taglia_btu"] = None
            kw_val = self._pdf_specs.get(code, {}).get("kw") if (self._pdf_specs and code in self._pdf_specs) else None
            if not kw_val:
                m_kw = re.search(r'\b(\d+[\.,]?\d*)\s*KW\b', name)
                if m_kw:
                    try:
                        kw_val = float(m_kw.group(1).replace(',', '.'))
                    except Exception:
                        pass
            if kw_val:
                item["taglia_kw"] = kw_val
                item["tag_kw"] = f"{kw_val} kW"
                item["tag_kw_display"] = f"{kw_val} kW"
            return

        # 2. Unità Interne (UI)
        if self._ac_master_uis and code in self._ac_master_uis:
            ui_meta = self._ac_master_uis[code]
            item["tipo_unita"] = "UI"
            item["is_ui"] = True
            item["is_ue"] = False
            item["tag_btu"] = ui_meta.get("tag_btu")
            item["tag_btu_display"] = ui_meta.get("tag_btu_display")
            item["taglia_btu"] = ui_meta.get("taglia_btu")
            item["famiglia_catalogo"] = ui_meta.get("famiglia_catalogo")
            if self._table_context_index is not None:
                self._table_context_index.apply_family_fallback(
                    item,
                    ui_meta.get("famiglia_catalogo") or ui_meta.get("serie"),
                    "COMPATIBILITY_MASTER",
                    priority=2,
                )
            item["serie"] = ui_meta.get("serie")
            item["tipologia"] = ui_meta.get("tipologia")
            item["tipo_sistema"] = ui_meta.get("tipo_sistema")
            item["refrigerante"] = ui_meta.get("refrigerante")
            item["primary_page"] = ui_meta.get("primary_page") or ui_meta.get("pagina_catalogo")
            item["kit_commerciali_inclusi"] = ui_meta.get("kit_commerciali_inclusi", [])
            item["taglia_kw"] = None
            return

        if self._pdf_specs and code in self._pdf_specs:
            spec = self._pdf_specs[code]
            item["tipo_unita"] = "UI"
            item["is_ui"] = True
            item["is_ue"] = False
            item["tag_btu"] = spec.get("tag_btu")
            item["tag_btu_display"] = spec.get("tag_btu_display")
            item["taglia_btu"] = spec.get("btu")
            item["taglia_kw"] = None
            return

        # Monoblocco senza unità esterna
        if any(k in cat for k in ["SENZA UNIT", "MONOBLOCCO"]) or "UNICO" in name:
            item["tipo_unita"] = "MONOBLOCCO_SUE"
            item["is_monoblocco_sue"] = True
            item["is_ui"] = False
            item["is_ue"] = False
            return

        if any(k in name for k in ["UI ", "UNITA INTERNA", "UNITA' INTERNA", "CLIMATIZZ", "SPLIT"]):
            # 3. Mappatura dinamica capacity class derivata dal catalogo
            brand = (item.get("brand") or "").strip().upper()
            combined = f"{name} {mfg}"
            digits_found = re.findall(r'(?:AS|AD|AF|JSGNW|MHGNW|LSGND|FTX[A-Z]|MSZ-[A-Z]+|CS-[A-Z]+|ALYA-|ELEGANCE\s*|XTREME\s*PRO\s*|HI\s*COMFORT\s*)(\d{2})', combined)
            if not digits_found:
                digits_found = re.findall(r'\b[A-Z]{1,4}(\d{2})[A-Z0-9\-]*\b', combined)

            btu_val = None
            for d in digits_found:
                if (brand, d) in self._dynamic_capacity_class_map:
                    btu_val = self._dynamic_capacity_class_map[(brand, d)]
                    break

            # 4. Fallback: taglia BTU letterale esplicita nel testo
            if not btu_val:
                m_btu = re.search(r'\b(7\.?000|9\.?000|12\.?000|15\.?000|18\.?000|21\.?000|24\.?000)\s*(?:BTU)?\b', combined)
                if m_btu:
                    btu_val = int(m_btu.group(1).replace('.', ''))

            if btu_val:
                item["tipo_unita"] = "UI"
                item["is_ui"] = True
                item["is_ue"] = False
                item["tag_btu"] = f"{btu_val} btu"
                item["tag_btu_display"] = f"{btu_val} BTU"
                item["taglia_btu"] = btu_val
                item["taglia_kw"] = None
                return

            # 5. Classi commerciali / grandi potenze (senza invenzione arbitraria di BTU)
            m_comm = re.search(r'\b(100|105|120|125|140|160|200|250)\b', combined)
            if m_comm:
                item["tipo_unita"] = "UI"
                item["is_ui"] = True
                item["is_ue"] = False
                item["classe_commerciale"] = m_comm.group(1)
                item["taglia_btu"] = None
                return
