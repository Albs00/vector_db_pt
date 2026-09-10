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


_MULTISPLIT_BTU_TO_TOKENS = {
    7000: {"20", "21", "2.0", "7"},
    9000: {"25", "26", "2.5", "2.6", "9"},
    12000: {"35", "3.5", "12"},
    15000: {"42", "45", "4.2", "4.5", "15"},
    18000: {"50", "52", "53", "5.0", "18"},
    21000: {"60", "6.0", "21"},
    24000: {"70", "71", "7.0", "24"},
}

_MULTISPLIT_CANONICAL_BTU_TOKEN = {
    7000: "20", 9000: "25", 12000: "35", 15000: "42",
    18000: "50", 21000: "60", 24000: "70",
}


def _combination_provenance(
    ue_rec: Dict[str, Any], source_field: Optional[str], combination: Optional[str] = None
) -> Tuple[str, str]:
    """Classify only explicit source metadata; page/table labels are not proof."""
    metadata = (
        ue_rec.get(f"{source_field}_provenance") if source_field else None
    ) or ue_rec.get("combination_provenance") or ue_rec.get("combinazioni_provenance")
    if isinstance(metadata, dict) and combination and combination in metadata:
        metadata = metadata[combination]
    if isinstance(metadata, dict):
        strength = str(metadata.get("evidence_strength") or metadata.get("strength") or "").upper()
        provenance = str(metadata.get("provenance") or metadata.get("source") or "")
    else:
        strength = str(metadata or "").upper()
        provenance = str(metadata or "")
    if strength == "CATALOG_TABLE_VERIFIED":
        return strength, provenance or "explicit catalog-table provenance metadata"
    if strength == "MASTER_DERIVED":
        return strength, provenance or "explicit builder-derived provenance metadata"
    return (
        "UNKNOWN_PROVENANCE",
        "master record has no explicit per-combination origin metadata; page, table name, and generated kits are not sufficient",
    )


def validate_multisplit_combination(
    ue_rec: Dict[str, Any], uis_in_bom: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Canonical, multiset-preserving full-combination matcher."""
    source_field = None
    combinations = ue_rec.get("combinazioni_ammesse") or []
    if combinations:
        source_field = "combinazioni_ammesse"
    else:
        combinations = ue_rec.get("combinazioni_ammesse_taglie") or []
        if combinations:
            source_field = "combinazioni_ammesse_taglie"

    selected_ui_multiset = dict(collections.Counter(
        str(item.get("code") or item.get("codice_pt") or "")
        for item in uis_in_bom
        if item.get("code") or item.get("codice_pt")
    ))
    ui_btus = [item.get("taglia_btu") for item in uis_in_bom]
    canonical_tokens = [
        _MULTISPLIT_CANONICAL_BTU_TOKEN.get(btu, str(btu) if btu else "")
        for btu in ui_btus
    ]
    requested_configuration = (
        "+".join(sorted(canonical_tokens, key=lambda token: float(token)))
        if canonical_tokens and all(canonical_tokens)
        else None
    )
    strength, provenance = _combination_provenance(ue_rec, source_field)
    result = {
        "matched": False,
        "requested_configuration": requested_configuration,
        "matched_configuration": None,
        "ue_pt": str(ue_rec.get("codice_pt") or ue_rec.get("code") or "") or None,
        "selected_ui_multiset": selected_ui_multiset,
        "source_field": source_field,
        "source": "climatizzatori_compatibilita_master.json",
        "catalog_page": ue_rec.get("pagina_catalogo"),
        "catalog_combination_page": ue_rec.get("pagina_combinazioni_catalogo"),
        "catalog_table": ue_rec.get("nome_tabella_combinazioni"),
        "evidence_strength": strength,
        "evidence_provenance": provenance,
    }
    if not ue_rec or not combinations or not ui_btus or any(not btu for btu in ui_btus):
        return result
    max_ports = ue_rec.get("porte_attacchi") or ue_rec.get("max_ui_collegabili") or 99
    if len(uis_in_bom) > int(max_ports):
        return result

    for combination in combinations:
        parts = [part for part in re.split(r"[+\s,]+", str(combination)) if part]
        if len(parts) != len(ui_btus):
            continue
        unmatched = list(ui_btus)
        for part in parts:
            match_index = next(
                (
                    index for index, btu in enumerate(unmatched)
                    if part in _MULTISPLIT_BTU_TO_TOKENS.get(int(btu), {str(btu)})
                ),
                None,
            )
            if match_index is None:
                break
            unmatched.pop(match_index)
        if not unmatched:
            result["matched"] = True
            result["matched_configuration"] = str(combination)
            strength, provenance = _combination_provenance(
                ue_rec, source_field, str(combination)
            )
            result["evidence_strength"] = strength
            result["evidence_provenance"] = provenance
            return result
    return result


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
            colour_groups = {
                "BLACK": {"BLACK", "NERO", "NER"},
                "WHITE": {"WHITE", "BIANCO", "BCO"},
                "SILVER": {"SILVER", "ARGENTO", "GRIGIO"},
            }
            requested_group = next(
                (group for group, tokens in colour_groups.items() if req_color in tokens),
                req_color,
            )
            item_groups = {
                group
                for group, tokens in colour_groups.items()
                if any(token in name_u for token in tokens)
            }
            if requested_group in item_groups:
                item["_color_match"] = True
                boost += 15.0
            elif item_groups:
                item["_color_mismatch"] = True
                boost -= 40.0

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

    @staticmethod
    def _flexible_model_pattern(label: str) -> Optional[re.Pattern]:
        """Build a strict model matcher while tolerating catalog punctuation."""
        parts = re.findall(r"[A-Z0-9]+", str(label or "").upper())
        if not parts or sum(len(part) for part in parts) < 4:
            return None
        body = r"[-\s_./]*".join(re.escape(part) for part in parts)
        return re.compile(rf"(?<![A-Z0-9]){body}(?![A-Z0-9])", re.IGNORECASE)

    def _candidate_model_labels(self, item: Dict[str, Any]) -> List[str]:
        labels: List[str] = []
        for value in (item.get("mfg_code"), item.get("codice_mfg"), item.get("model")):
            if value:
                labels.append(str(value).strip())

        code = str(item.get("code") or "")
        if code and self._table_context_index:
            table_ctx = self._table_context_index.get(code) or {}
            for value in (table_ctx.get("model"), table_ctx.get("mpn")):
                if value:
                    raw_value = str(value).strip()
                    labels.append(raw_value)
                    without_role = re.sub(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", "", raw_value, flags=re.IGNORECASE)
                    if without_role and without_role != raw_value:
                        labels.append(without_role)

        # Product names often contain the commercial model even when the MFG
        # field contains an ERP/vendor code (notably Baxi).
        name = str(item.get("name") or item.get("nome") or "").upper()
        labels.extend(
            token for token in re.findall(r"\b[A-Z][A-Z0-9]*(?:[-/][A-Z0-9]+)+\b", name)
            if len(re.sub(r"[^A-Z0-9]", "", token)) >= 5
        )
        labels.extend(
            token for token in re.findall(r"\b(?=[A-Z0-9]{6,}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]+\b", name)
            if token not in {"INVERTER"}
        )

        result: List[str] = []
        seen = set()
        normalized_labels = [
            re.sub(r"[^A-Z0-9]", "", str(value).upper())
            for value in labels
            if value
        ]
        for label in labels:
            norm = re.sub(r"[^A-Z0-9]", "", label.upper())
            if any(other.startswith(norm) and len(other) > len(norm) for other in normalized_labels):
                continue
            if norm and norm not in seen:
                seen.add(norm)
                result.append(label)
        return result

    def _explicit_model_in_query(self, item: Dict[str, Any], query: str) -> Optional[str]:
        for label in self._candidate_model_labels(item):
            pattern = self._flexible_model_pattern(label)
            if pattern and pattern.search(str(query or "")):
                return label
        return None

    @staticmethod
    def _query_model_tokens(query: str) -> List[str]:
        """Return only model-like query tokens (letters + digits), not capacities."""
        matches = list(re.finditer(
            r"(?<![A-Z0-9])(?=[A-Z0-9._/-]{6,})(?=[A-Z0-9._/-]*[A-Z])"
            r"(?=[A-Z0-9._/-]*\d)[A-Z0-9]+(?:[-_./][A-Z0-9]+)*(?![A-Z0-9])",
            str(query or "").upper(),
        ))
        tokens = []
        query_text = str(query or "").upper()
        for match in matches:
            token = match.group(0)
            suffix_match = re.match(r"\s+([A-Z](?:\d{1,2})?)\b", query_text[match.end():])
            if suffix_match and suffix_match.group(1) not in {"R", "K"}:
                # A short, immediately adjacent variant may be part of the
                # model (EX18000-2 E, MODEL V3). Keep the base token as a
                # secondary candidate; catalog identity decides whether the
                # combined form is valid.
                tokens.append(f"{token} {suffix_match.group(1)}")
            tokens.append(token)
        result = []
        seen = set()
        for token in tokens:
            norm = re.sub(r"[^A-Z0-9]", "", token)
            if len(norm) >= 6 and norm not in seen:
                seen.add(norm)
                result.append(token)
        return result

    def _explicit_ue_model_match(self, item: Dict[str, Any], query: str) -> Dict[str, Optional[str]]:
        """Match an explicit UE token, preserving suffix/revision distinctions."""
        for token in self._query_model_tokens(query):
            match = self._ue_candidate_token_match(item, token)
            if match:
                return match
        return {"token": None, "label": None, "match_type": None}

    @staticmethod
    def _revision_base(value: str) -> str:
        text = str(value or "").upper().strip()
        base = re.sub(
            r"[-_./]\s*(?:REV(?:ISIONE)?\s*)?[A-Z0-9]{1,3}$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return re.sub(r"[^A-Z0-9]", "", base)

    def _ue_candidate_token_match(
        self, item: Dict[str, Any], token: str
    ) -> Optional[Dict[str, str]]:
        token_text = str(token or "").upper().strip()
        token_norm = re.sub(r"[^A-Z0-9]", "", token_text)
        if len(token_norm) < 6:
            return None

        raw_values = []
        for value in (
            item.get("mfg_code"),
            item.get("codice_mfg"),
            item.get("model"),
            *self._candidate_model_labels(item),
        ):
            value = str(value or "").strip()
            if value and value not in raw_values:
                raw_values.append(value)

        revision_matches = []
        for label in raw_values:
            label_norm = re.sub(r"[^A-Z0-9]", "", label.upper())
            if label_norm == token_norm or label_norm.endswith(token_norm):
                return {
                    "token": token,
                    "label": label,
                    "catalog_model": label,
                    "match_type": "EXPLICIT_MODEL_EXACT_MATCH",
                }

            same_delimited_revision = (
                self._revision_base(label)
                and self._revision_base(label) == self._revision_base(token_text)
                and label_norm != token_norm
            )
            short_prefix_variant = (
                label_norm.startswith(token_norm)
                and 1 <= len(label_norm) - len(token_norm) <= 3
            )
            descriptive_prefix_variant = False
            if token_norm in label_norm:
                suffix = label_norm.split(token_norm, 1)[1]
                descriptive_prefix_variant = 1 <= len(suffix) <= 2
            if same_delimited_revision or short_prefix_variant or descriptive_prefix_variant:
                catalog_model = label
                direct_mfg = str(item.get("mfg_code") or "").strip()
                direct_mfg_norm = re.sub(r"[^A-Z0-9]", "", direct_mfg.upper())
                if direct_mfg and (
                    direct_mfg_norm.startswith(token_norm)
                    or token_norm.startswith(direct_mfg_norm)
                ):
                    catalog_model = direct_mfg
                revision_matches.append({
                    "token": token,
                    "label": label,
                    "catalog_model": catalog_model,
                    "match_type": "EXPLICIT_MODEL_REVISION_MATCH",
                })

        return revision_matches[0] if revision_matches else None

    def _explicit_ue_identity_analysis(
        self, candidates: List[Dict[str, Any]], query: str
    ) -> Dict[str, Any]:
        """Resolve UE model identity independently from configuration validity."""
        token_matches = []
        for token in self._query_model_tokens(query):
            matches = []
            for candidate in candidates:
                match = self._ue_candidate_token_match(candidate, token)
                if match:
                    matches.append({"candidate": candidate, **match})
            if matches:
                token_matches.append((token, matches))

        if not token_matches:
            return {
                "status": "DISCOVERY_ONLY",
                "token": None,
                "match_type": None,
                "matches": [],
                "candidates": [],
            }

        exact_groups = [
            (token, matches)
            for token, matches in token_matches
            if any(match["match_type"] == "EXPLICIT_MODEL_EXACT_MATCH" for match in matches)
        ]
        if exact_groups:
            token, matches = exact_groups[0]
            matches = [
                match for match in matches
                if match["match_type"] == "EXPLICIT_MODEL_EXACT_MATCH"
            ]
            status = "EXACT" if len(matches) == 1 else "CONFLICT"
            match_type = "EXPLICIT_MODEL_EXACT_MATCH" if status == "EXACT" else "CONFLICT"
        else:
            token, matches = token_matches[0]
            status = "REVISION_CANDIDATE" if len(matches) == 1 else "AMBIGUOUS_REVISION"
            match_type = (
                "EXPLICIT_MODEL_REVISION_MATCH"
                if status == "REVISION_CANDIDATE"
                else "AMBIGUOUS_REVISION"
            )

        diagnostic_candidates = []
        seen = set()
        for match in matches:
            candidate = match["candidate"]
            code = str(candidate.get("code") or "")
            if code in seen:
                continue
            seen.add(code)
            diagnostic_candidates.append({
                "pt": code,
                "catalog_model": match.get("catalog_model") or match.get("label"),
                "match_type": match.get("match_type"),
            })
        return {
            "status": status,
            "token": token,
            "match_type": match_type,
            "matches": matches,
            "candidates": diagnostic_candidates,
        }

    def _has_pdf_pairing(self, ui_codes: List[str], ue_code: str) -> bool:
        if not ui_codes or not ue_code:
            return False
        return all(
            any(str(pair.get("target_code") or "") == ue_code for pair in self._pdf_table_pairs_ui_to_ue.get(ui_code, []))
            for ui_code in ui_codes
        )

    def _master_compatible_selected_ui_codes(
        self, ui_items: List[Dict[str, Any]], ue_code: str
    ) -> List[str]:
        if not ui_items or not ue_code:
            return []
        ue_master = self._ac_master_ues.get(ue_code) or {}
        compatible_ui_models = {
            re.sub(r"[^A-Z0-9]", "", str(value).upper())
            for value in (ue_master.get("modelli_ui_compatibili") or [])
            if value
        }

        compatible_codes = []
        for ui_item in ui_items:
            ui_code = str(ui_item.get("code") or "")
            ui_master = self._ac_master_uis.get(ui_code) or {}
            direct_codes = {
                str(rec.get("code") or rec.get("codice_pt") or "")
                for rec in (ui_master.get("unita_esterne_compatibili") or [])
            }
            ui_mfg = re.sub(
                r"[^A-Z0-9]", "",
                str(ui_item.get("mfg_code") or ui_master.get("mfg_code") or "").upper(),
            )
            if ue_code not in direct_codes and (not ui_mfg or ui_mfg not in compatible_ui_models):
                continue
            compatible_codes.append(ui_code)
        return compatible_codes

    def _has_master_compatibility(self, ui_items: List[Dict[str, Any]], ue_code: str) -> bool:
        if not ui_items:
            return False
        return len(self._master_compatible_selected_ui_codes(ui_items, ue_code)) == len(ui_items)

    def _multisplit_configuration_verified(self, ui_items: List[Dict[str, Any]], ue_code: str) -> bool:
        """Require a full catalog combination, never only pairwise UI links."""
        ue_master = self._ac_master_ues.get(ue_code) or {}
        return bool(validate_multisplit_combination(ue_master, ui_items)["matched"])

    @staticmethod
    def _commercial_family_match(ui_items: List[Dict[str, Any]], ue_item: Dict[str, Any], query_context: Dict[str, Any]) -> bool:
        ue_text = " ".join(str(ue_item.get(key) or "") for key in ("name", "serie", "famiglia_catalogo", "catalog_family")).upper()
        requested = str(query_context.get("requested_series") or "").strip().upper()
        if requested and requested in ue_text:
            return True
        for ui_item in ui_items:
            for key in ("serie", "famiglia_catalogo", "catalog_family"):
                family = str(ui_item.get(key) or "").strip().upper()
                if family and family in ue_text:
                    return True
            ui_name = str(ui_item.get("name") or "").upper()
            for family in ("HAORI", "DAISEIKAI", "PERFERA", "STYLISH", "FLEXIS", "ASTRA", "EXPERT"):
                if family in ui_name and family in ue_text:
                    return True
        return False

    @staticmethod
    def _colour_variant_score(ue_item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        requested = str(query_context.get("requested_color") or "").upper()
        if not requested:
            return 0.0
        groups = {
            "BLACK": {"BLACK", "NERO", "NER"},
            "WHITE": {"WHITE", "BIANCO", "BCO"},
            "SILVER": {"SILVER", "ARGENTO"},
        }
        requested_group = next((group for group, tokens in groups.items() if requested in tokens), requested)
        text = " ".join(str(ue_item.get(key) or "") for key in ("name", "serie", "famiglia_catalogo", "catalog_family")).upper()
        present_groups = {group for group, tokens in groups.items() if any(token in text for token in tokens)}
        if not present_groups:
            return 0.0
        return 40.0 if requested_group in present_groups else -120.0

    def pairing_score_breakdown(
        self,
        ui_items: List[Dict[str, Any]],
        ue_item: Dict[str, Any],
        query_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score a UE candidate using evidence in the requested commercial order."""
        ue_code = str(ue_item.get("code") or "")
        ui_codes = [str(item.get("code") or "") for item in ui_items if item.get("code")]
        pdf_pair_is_strong = self._has_pdf_pairing(ui_codes, ue_code)
        if query_context.get("is_multisplit"):
            pdf_pair_is_strong = pdf_pair_is_strong and self._multisplit_configuration_verified(
                ui_items, ue_code
            )
        pdf_pairing = 100.0 if pdf_pair_is_strong else 0.0
        if query_context.get("is_multisplit"):
            explicit_match = self._explicit_ue_model_match(
                ue_item, query_context.get("query_text") or ""
            )
        else:
            mono_explicit_label = self._explicit_model_in_query(
                ue_item, query_context.get("query_text") or ""
            )
            explicit_match = {
                "token": mono_explicit_label,
                "label": mono_explicit_label,
                "match_type": "EXPLICIT_MODEL_EXACT_MATCH" if mono_explicit_label else None,
            }
        explicit_label = explicit_match.get("label")
        explicit_match_type = explicit_match.get("match_type")
        explicit_model = 90.0 if explicit_match_type == "EXPLICIT_MODEL_EXACT_MATCH" else 0.0
        explicit_revision = 85.0 if explicit_match_type == "EXPLICIT_MODEL_REVISION_MATCH" else 0.0
        family = 80.0 if self._commercial_family_match(ui_items, ue_item, query_context) else 0.0
        master_compatible_ui_codes = self._master_compatible_selected_ui_codes(ui_items, ue_code)
        master = 70.0 if len(master_compatible_ui_codes) == len(ui_items) else 0.0
        master_pairwise = 10.0 * len(master_compatible_ui_codes)

        btu = 0.0
        if len(ui_items) == 1:
            ui_btu = ui_items[0].get("taglia_btu")
            ue_master = self._ac_master_ues.get(ue_code) or {}
            ue_kw = float(
                ue_item.get("potenza_nominale_kw") or ue_item.get("taglia_kw") or
                ue_master.get("potenza_nominale_kw") or ue_master.get("taglia_kw") or 0.0
            )
            if ui_btu and ue_kw:
                diff = abs(ue_kw - capacity_kw_for_btu(int(ui_btu)))
                if diff <= 1.5:
                    btu = 50.0

        variant = self._colour_variant_score(ue_item, query_context)
        final = (
            pdf_pairing + explicit_model + explicit_revision + family + master
            + master_pairwise + btu + variant
        )
        return {
            "PDF_PAIRING": pdf_pairing,
            "EXPLICIT_MODEL": explicit_model,
            "EXPLICIT_MODEL_REVISION": explicit_revision,
            "FAMILY": family,
            "MASTER": master,
            "MASTER_PAIRWISE_SELECTED_UI": master_pairwise,
            "MASTER_COMPATIBLE_SELECTED_UI_PT": master_compatible_ui_codes,
            "BTU": btu,
            "VARIANT": variant,
            "FINAL": final,
            "explicit_model_label": explicit_label,
            "explicit_ue_token": explicit_match.get("token"),
            "explicit_ue_match_type": explicit_match_type,
        }

    def resolve_main_component_pairing(
        self,
        bom: List[Dict[str, Any]],
        candidate_pools: Dict[str, List[Dict[str, Any]]],
        query_context: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Resolve the commercial UE only after the UI identity is established."""
        ui_items = [item for item in bom if item.get("role") == "UI" or item.get("is_ui")]
        ue_candidates = list(candidate_pools.get("slot_ue") or [])
        selected_ui_counts = collections.Counter(
            str(item.get("code") or "") for item in ui_items if item.get("code")
        )
        selected_ui_context = [
            {"pt": code, "quantity": quantity}
            for code, quantity in selected_ui_counts.items()
        ]
        identity_analysis = {
            "status": "DISCOVERY_ONLY",
            "token": None,
            "match_type": None,
            "matches": [],
            "candidates": [],
        }
        if query_context.get("is_multisplit"):
            identity_analysis = self._explicit_ue_identity_analysis(
                ue_candidates, query_context.get("query_text") or ""
            )

            if identity_analysis["status"] in ("AMBIGUOUS_REVISION", "CONFLICT"):
                bom = [
                    item for item in bom
                    if not (item.get("role") == "UE" or item.get("is_ue"))
                ]
                block_reason = (
                    "AMBIGUOUS_UE_REVISION"
                    if identity_analysis["status"] == "AMBIGUOUS_REVISION"
                    else "EXPLICIT_UE_IDENTITY_CONFLICT"
                )
                return bom, {
                    "PAIRING_REASON": block_reason,
                    "PAIRING_SCORE_BREAKDOWN": {},
                    "PAIRING_STATUS": "CONFIGURAZIONE_NON_CONFERMATA",
                    "MPN_FINAL_ALLOWED": False,
                    "PRODUCT_IDENTITY_STATUS": identity_analysis["status"],
                    "CONFIGURATION_STATUS": "NOT_VERIFIED",
                    "EXPLICIT_UE_TOKEN": identity_analysis["token"],
                    "EXPLICIT_UE_MATCH_TYPE": identity_analysis["match_type"],
                    "EXPLICIT_UE_CANDIDATES": identity_analysis["candidates"],
                    "SELECTED_UI_EVIDENCE_PT": selected_ui_context,
                    "REJECTED_NON_BOM_UI_EVIDENCE": [],
                    "FULL_CONFIGURATION_EVIDENCE": [],
                    "FULL_CONFIGURATION_MATCHED": False,
                    "FULL_CONFIGURATION_REQUESTED": None,
                    "FULL_CONFIGURATION_CATALOG": None,
                    "FULL_CONFIGURATION_SOURCE_FIELD": None,
                    "FULL_CONFIGURATION_EVIDENCE_STRENGTH": "UNKNOWN_PROVENANCE",
                    "FULL_CONFIGURATION_PROVENANCE": "UE identity is ambiguous or conflicting; no full-combination validation was attempted",
                    "FULL_CONFIGURATION_PAGE": None,
                    "FULL_CONFIGURATION_TABLE": None,
                    "CONFIGURATION_CONFLICT_REASON": None,
                    "CONFIGURATION_CONFLICT_DETAILS": {},
                    "MPN_FINAL_BLOCK_REASON": block_reason,
                    "UE_SELECTION_REASON": block_reason,
                }

            if identity_analysis["matches"]:
                # Explicit product identity wins even when its topology later
                # proves incompatible with the requested number of UIs.
                explicit_codes = {
                    str(match["candidate"].get("code") or "")
                    for match in identity_analysis["matches"]
                }
                ue_candidates = [
                    candidate for candidate in ue_candidates
                    if str(candidate.get("code") or "") in explicit_codes
                ]
            elif ui_items:
                # Topology is only a discovery filter when no UE model was
                # explicit; it must never replace an explicit conflicting UE.
                topology_candidates = []
                for candidate in ue_candidates:
                    ue_master = self._ac_master_ues.get(str(candidate.get("code") or "")) or {}
                    ports = (
                        candidate.get("porte_attacchi") or candidate.get("max_ui_collegabili") or
                        ue_master.get("porte_attacchi") or ue_master.get("max_ui_collegabili")
                    )
                    if ports and int(ports) >= len(ui_items):
                        topology_candidates.append(candidate)
                if topology_candidates:
                    ue_candidates = topology_candidates
        if not ui_items or not ue_candidates:
            return bom, {
                "PAIRING_REASON": None,
                "PAIRING_SCORE_BREAKDOWN": {},
                "PAIRING_STATUS": "NOT_APPLICABLE",
                "MPN_FINAL_ALLOWED": False,
                "PRODUCT_IDENTITY_STATUS": identity_analysis["status"],
                "CONFIGURATION_STATUS": "NOT_VERIFIED",
                "EXPLICIT_UE_TOKEN": identity_analysis["token"],
                "EXPLICIT_UE_MATCH_TYPE": identity_analysis["match_type"],
                "EXPLICIT_UE_CANDIDATES": identity_analysis["candidates"],
                "SELECTED_UI_EVIDENCE_PT": selected_ui_context,
                "REJECTED_NON_BOM_UI_EVIDENCE": [],
                "FULL_CONFIGURATION_EVIDENCE": [],
                "FULL_CONFIGURATION_MATCHED": False,
                "FULL_CONFIGURATION_REQUESTED": None,
                "FULL_CONFIGURATION_CATALOG": None,
                "FULL_CONFIGURATION_SOURCE_FIELD": None,
                "FULL_CONFIGURATION_EVIDENCE_STRENGTH": "UNKNOWN_PROVENANCE",
                "FULL_CONFIGURATION_PROVENANCE": "selected UI/UE set is incomplete; no full-combination validation was attempted",
                "FULL_CONFIGURATION_PAGE": None,
                "FULL_CONFIGURATION_TABLE": None,
                "CONFIGURATION_CONFLICT_REASON": None,
                "CONFIGURATION_CONFLICT_DETAILS": {},
                "MPN_FINAL_BLOCK_REASON": "FULL_COMBINATION_NOT_VERIFIED",
            }

        ranked = []
        for candidate in ue_candidates:
            breakdown = self.pairing_score_breakdown(ui_items, candidate, query_context)
            if query_context.get("is_multisplit"):
                # The final UE decision is made only after the BOM UI slots are
                # fixed. Candidate/intermediate UI relation boosts are excluded.
                priority_key = (
                    int(breakdown["EXPLICIT_MODEL"] > 0),
                    int(breakdown["EXPLICIT_MODEL_REVISION"] > 0),
                    int(breakdown["PDF_PAIRING"] > 0),
                    int(breakdown["MASTER"] > 0),
                    len(breakdown["MASTER_COMPATIBLE_SELECTED_UI_PT"]),
                    -int(str(candidate.get("code") or "0"))
                    if str(candidate.get("code") or "").isdigit()
                    else 0,
                )
            else:
                priority_key = (
                    int(breakdown["PDF_PAIRING"] > 0),
                    int(breakdown["EXPLICIT_MODEL"] > 0),
                    int(breakdown["FAMILY"] > 0),
                    int(breakdown["MASTER"] > 0),
                    int(breakdown["BTU"] > 0),
                    float(breakdown["VARIANT"]),
                    float(breakdown["FINAL"]),
                )
            ranked.append((priority_key, candidate, breakdown))
        ranked.sort(key=lambda row: row[0], reverse=True)

        _, selected, breakdown = ranked[0]
        if query_context.get("is_multisplit"):
            reason = (
                "EXPLICIT_MODEL_IN_QUERY" if breakdown["EXPLICIT_MODEL"] else
                "EXPLICIT_MODEL_REVISION_MATCH" if breakdown["EXPLICIT_MODEL_REVISION"] else
                "PDF_TABLE_PAIRING" if breakdown["PDF_PAIRING"] else
                "MASTER_COMPATIBILITY_FALLBACK" if breakdown["MASTER"] else
                "MASTER_PAIRWISE_DIAGNOSTIC_FALLBACK"
                if breakdown["MASTER_PAIRWISE_SELECTED_UI"] else
                "BTU_FALLBACK"
            )
        else:
            reason = (
                "PDF_TABLE_PAIRING" if breakdown["PDF_PAIRING"] else
                "EXPLICIT_MODEL_IN_QUERY" if breakdown["EXPLICIT_MODEL"] else
                "FAMILY_SERIES_MATCH" if breakdown["FAMILY"] else
                "MASTER_COMPATIBILITY_FALLBACK" if breakdown["MASTER"] else
                "BTU_FALLBACK"
            )

        product_identity_status = (
            identity_analysis["status"]
            if query_context.get("is_multisplit")
            else "EXACT" if breakdown["EXPLICIT_MODEL"] else "DISCOVERY_ONLY"
        )
        configuration_status = "NOT_VERIFIED"
        full_configuration_evidence = []
        full_combination_validation = {
            "matched": False,
            "requested_configuration": None,
            "matched_configuration": None,
            "source_field": None,
            "evidence_strength": "UNKNOWN_PROVENANCE",
            "evidence_provenance": "no selected multisplit UE/UI combination was validated",
            "catalog_combination_page": None,
            "catalog_table": None,
        }
        configuration_conflict_reason = None
        configuration_conflict_details = {}
        if query_context.get("is_multisplit"):
            selected_code = str(selected.get("code") or "")
            ue_master = self._ac_master_ues.get(selected_code) or {}
            full_combination_validation = validate_multisplit_combination(
                ue_master, ui_items
            )
            if full_combination_validation["matched"]:
                full_configuration_evidence = [dict(full_combination_validation)]
            ports = (
                selected.get("porte_attacchi") or selected.get("max_ui_collegabili") or
                ue_master.get("porte_attacchi") or ue_master.get("max_ui_collegabili")
            )
            combinations = (
                ue_master.get("combinazioni_ammesse")
                or ue_master.get("combinazioni_ammesse_taglie")
                or []
            )
            combination_arities = {
                len([part for part in re.split(r"[+\s,]+", str(combination)) if part])
                for combination in combinations
            }
            explicit_identity = product_identity_status in ("EXACT", "REVISION_CANDIDATE")
            if explicit_identity and ports and int(ports) < len(ui_items):
                configuration_conflict_reason = "UI_COUNT_MISMATCH"
                configuration_conflict_details = {
                    "requested_ui_count": len(ui_items),
                    "ue_ports": int(ports),
                }
            elif (
                explicit_identity
                and combination_arities
                and len(ui_items) not in combination_arities
            ):
                configuration_conflict_reason = "EXPLICIT_SCOPE_CONFLICT"
                configuration_conflict_details = {
                    "requested_ui_count": len(ui_items),
                    "ue_ports": int(ports) if ports else None,
                    "catalog_combination_ui_counts": sorted(combination_arities),
                    "evidence_source": "compatibility_master.combinazioni_ammesse",
                }
            explicit_configuration_conflict = bool(configuration_conflict_reason)

            if explicit_configuration_conflict:
                configuration_status = "CONFLICT"
            elif (
                full_combination_validation["matched"]
                and full_combination_validation["evidence_strength"]
                == "CATALOG_TABLE_VERIFIED"
            ):
                configuration_status = "VERIFIED_FULL_COMBINATION"
            elif breakdown["MASTER_PAIRWISE_SELECTED_UI"]:
                configuration_status = "PAIRWISE_ONLY"

        if product_identity_status == "AMBIGUOUS_REVISION":
            block_reason = "AMBIGUOUS_UE_REVISION"
        elif configuration_status == "CONFLICT":
            block_reason = "EXPLICIT_UE_CONFIGURATION_CONFLICT"
        elif product_identity_status == "REVISION_CANDIDATE":
            block_reason = "REVISION_NOT_EXACT"
        elif configuration_status == "PAIRWISE_ONLY":
            block_reason = "PAIRWISE_COMPATIBILITY_ONLY"
        elif configuration_status != "VERIFIED_FULL_COMBINATION":
            block_reason = "FULL_COMBINATION_NOT_VERIFIED"
        elif product_identity_status != "EXACT":
            block_reason = "UI_IDENTITY_NOT_RELIABLE"
        else:
            block_reason = None

        selected_copy = dict(selected)

        selected_ui_codes = set(selected_ui_counts)
        selected_evidences = []
        rejected_non_bom_ui_evidence = []
        for evidence in selected.get("relation_evidences") or []:
            source_code = str(evidence.get("source_code") or "")
            target_code = str(evidence.get("target_code") or "")
            evidence_ui_code = source_code if source_code != str(selected.get("code") or "") else target_code
            if evidence_ui_code in selected_ui_codes:
                selected_evidences.append(evidence)
            elif evidence_ui_code and evidence_ui_code not in rejected_non_bom_ui_evidence:
                rejected_non_bom_ui_evidence.append(evidence_ui_code)
        selected_copy["relation_evidences"] = selected_evidences
        selected_copy["relation_evidence"] = selected_evidences[0] if selected_evidences else None
        selected_copy["role"] = "UE"
        selected_copy["role_label"] = "UE (Motore Esterno)"
        selected_copy["pairing_reason"] = reason
        selected_copy["pairing_score_breakdown"] = breakdown
        selected_copy["product_identity_status"] = product_identity_status
        selected_copy["configuration_status"] = configuration_status
        selected_copy["configuration_conflict_reason"] = configuration_conflict_reason
        selected_copy["configuration_conflict_details"] = configuration_conflict_details
        selected_copy["selected_ui_context"] = selected_ui_context
        selected_copy["rejected_non_bom_ui_evidence"] = rejected_non_bom_ui_evidence

        ue_index = next(
            (idx for idx, item in enumerate(bom) if item.get("role") == "UE" or item.get("is_ue")),
            None,
        )
        if ue_index is None:
            bom.insert(0, selected_copy)
        else:
            bom[ue_index] = selected_copy

        # Keep diagnostics and downstream inspection aligned with the selected
        # component without changing the general retrieval ranking.
        candidate_pools["slot_ue"] = [selected_copy] + [
            candidate for candidate in ue_candidates
            if str(candidate.get("code") or "") != str(selected.get("code") or "")
        ]
        mpn_final_allowed = bool(
            product_identity_status == "EXACT"
            and configuration_status == "VERIFIED_FULL_COMBINATION"
        )
        return bom, {
            "PAIRING_REASON": reason,
            "PAIRING_SCORE_BREAKDOWN": breakdown,
            "PAIRING_STATUS": (
                "PAIRING_CONFIRMED"
                if mpn_final_allowed
                else "CONFIGURAZIONE_NON_CONFERMATA"
            ),
            "MPN_FINAL_ALLOWED": mpn_final_allowed,
            "selected_ue_code": str(selected.get("code") or ""),
            "selected_ue_mfg": selected.get("mfg_code"),
            "selected_ui_codes": [str(item.get("code") or "") for item in ui_items],
            "selected_ui_context": selected_ui_context,
            "PRODUCT_IDENTITY_STATUS": product_identity_status,
            "CONFIGURATION_STATUS": configuration_status,
            "EXPLICIT_UE_TOKEN": identity_analysis.get("token") or breakdown.get("explicit_ue_token"),
            "EXPLICIT_UE_MATCH_TYPE": identity_analysis.get("match_type") or breakdown.get("explicit_ue_match_type"),
            "EXPLICIT_UE_CANDIDATES": identity_analysis.get("candidates") or [],
            "SELECTED_UI_EVIDENCE_PT": selected_ui_context,
            "MASTER_COMPATIBLE_SELECTED_UI_PT": breakdown.get(
                "MASTER_COMPATIBLE_SELECTED_UI_PT"
            ) or [],
            "REJECTED_NON_BOM_UI_EVIDENCE": rejected_non_bom_ui_evidence,
            "FULL_CONFIGURATION_EVIDENCE": full_configuration_evidence,
            "FULL_CONFIGURATION_VALIDATION": full_combination_validation,
            "FULL_CONFIGURATION_MATCHED": bool(full_combination_validation.get("matched")),
            "FULL_CONFIGURATION_REQUESTED": full_combination_validation.get("requested_configuration"),
            "FULL_CONFIGURATION_CATALOG": full_combination_validation.get("matched_configuration"),
            "FULL_CONFIGURATION_SOURCE_FIELD": full_combination_validation.get("source_field"),
            "FULL_CONFIGURATION_EVIDENCE_STRENGTH": full_combination_validation.get("evidence_strength"),
            "FULL_CONFIGURATION_PROVENANCE": full_combination_validation.get("evidence_provenance"),
            "FULL_CONFIGURATION_PAGE": full_combination_validation.get("catalog_combination_page"),
            "FULL_CONFIGURATION_TABLE": full_combination_validation.get("catalog_table"),
            "CONFIGURATION_CONFLICT_REASON": configuration_conflict_reason,
            "CONFIGURATION_CONFLICT_DETAILS": configuration_conflict_details,
            "MPN_FINAL_BLOCK_REASON": block_reason,
            "UE_SELECTION_REASON": reason,
        }

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
        # Same page alone is deliberately not evidence of a commercial pair.

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
