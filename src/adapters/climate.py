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
from build_full_ac_matrix import extract_btu_and_kw


def extract_split_capacities(query: str) -> List[int]:
    """Estrae le capacità BTU richieste per le unità interne multisplit (es. 9+12 -> [9000, 12000], 7+15 -> [7000, 15000])."""
    q_u = query.upper()
    m = re.search(
        r'\b(\d{1,2}|7000|9000|12000|15000|18000|21000|24000)\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000)(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000))?(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000))?(?:\s*\+\s*(\d{1,2}|7000|9000|12000|15000|18000|21000|24000))?\b',
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
    m_single = re.search(r'\b(7000|9000|12000|15000|18000|21000|24000)\s*BTU\b', q_u)
    if m_single:
        return [int(m_single.group(1))]
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
        pdf_specs_path: Optional[str] = None
    ):
        self._ac_master_uis: Dict[str, Any] = {}
        self._ac_master_ues: Dict[str, Any] = {}
        self._pdf_specs: Dict[str, Any] = {}
        self._dynamic_capacity_class_map: Dict[Tuple[str, str], int] = {}
        self._series_vocab: List[str] = []
        self._series_aliases: Dict[str, List[str]] = {}

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

        self._init_dynamic_capacity_classes()
        self._init_dynamic_series_vocabulary()

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
            'R32', 'R410A', 'INVERTER', 'WHITE', 'BLACK', 'SILVER', 'MATT', 'WIFI',
            'PARETE', 'LIGHT COMMERCIAL', 'SUPER MATCH',
            'SPLIT', 'DUAL', 'TRIAL', 'QUADRI', 'PENTA', 'MULTI', 'MONO',
            'CLIMATIZZATORE', 'CONDIZIONATORE', 'CLIMATIZZATORI', 'CONDIZIONATORI',
            'GAS', 'SERIE', 'GAMMA', 'LINEA', 'CLASSE', 'UNITA', 'ESTERNA', 'INTERNA',
            'MOTOCONDENSANTE', 'SISTEMA', 'UNITA ESTERNA', 'UNITA INTERNA'
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
        is_ue_only = (
            ("UNITÀ ESTERNA" in q_u or "UNITA ESTERNA" in q_u or "MOTOCONDENSANTE" in q_u)
            and not any(k in q_u for k in ['MONOSPLIT', 'MONO SPLIT', 'DUAL SPLIT', 'TRIAL SPLIT', 'QUADRI SPLIT', 'PENTA SPLIT'])
            and len(btus) == 0
        )
        is_multi = (
            any(k in q_u for k in ['DUAL', 'TRIAL', 'QUADRI', 'PENTA', 'MULTISPLIT'])
            or len(btus) > 1
        )
        is_mono = (
            any(k in q_u for k in ['MONOSPLIT', 'MONO SPLIT'])
            or (len(btus) == 1 and not is_multi)
        )
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
        requested_series = None
        matched_series = []
        for term in self._series_vocab:
            if re.search(r'\b' + re.escape(term) + r'\b', q_u):
                matched_series.append(term)
        for canon, alts in self._series_aliases.items():
            if canon in matched_series:
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

        return {
            "query_text": query,
            "requested_btus": btus,
            "requested_series": requested_series,
            "requested_color": requested_color,
            "is_multisplit": is_multi,
            "is_monosplit": is_mono,
            "is_ue_only": is_ue_only,
            "has_commercial_kw": has_commercial_kw,
            "explicit_tipologia": explicit_tipologia,
            "probable_tipologia": probable_tipologia,
            "is_machine_query": True
        }

    def evaluate_series_match(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        req_ser = query_context.get("requested_series")
        if not req_ser:
            return "none"

        req_u = req_ser.upper()
        item_ser = (item.get("serie") or "").upper()
        item_fam = (item.get("famiglia_catalogo") or "").upper()
        item_name = (item.get("name") or "").upper()

        # Check exact
        if re.search(r'\b' + re.escape(req_u) + r'\b', item_name) or req_u in item_ser or req_u in item_fam:
            return "exact"

        # Check aliases
        req_aliases = self._series_aliases.get(req_u, [])
        for a in req_aliases:
            if re.search(r'\b' + re.escape(a) + r'\b', item_name) or a in item_ser or a in item_fam:
                return "alias"

        # Check mismatch
        for canon, alts in self._series_aliases.items():
            if canon == req_u or canon in req_aliases:
                continue
            all_alt_terms = [canon] + alts
            for alt_t in all_alt_terms:
                if re.search(r'\b' + re.escape(alt_t) + r'\b', item_name):
                    return "mismatch"

        for t in ['ASTRA', 'SIDERA', 'EXPERT', 'FLEXIS', 'ELEGANCE', 'XTREME PRO', 'BREEZELESS', 'HI COMFORT', 'EASY SMART', 'AIR MASTER', 'RZ2GT', 'PERFERA', 'EMURA', 'STYLISH', 'SENSIRA', 'COMFORA', 'WINDFREE']:
            if t == req_u or t in req_aliases:
                continue
            if re.search(r'\b' + re.escape(t) + r'\b', item_name) or t in item_ser or t in item_fam:
                return "mismatch"

        return "none"

    def assign_slot(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> str:
        self.enrich_item(item)
        if item.get("is_accessory"):
            return "slot_accessory"
        if item.get("is_ue"):
            return "slot_ue"
        if item.get("is_ui"):
            btu = item.get("taglia_btu")
            if btu:
                return f"slot_ui_{btu}"
            return "slot_ui"
        if item.get("is_monoblocco_sue"):
            return "slot_monoblocco"
        return "slot_clima_general"

    def compute_domain_boost(self, item: Dict[str, Any], query_context: Dict[str, Any]) -> float:
        self.enrich_item(item)
        boost = 0.0
        requested_btus = query_context.get("requested_btus", [])

        # Boost per UI con taglia richiesta esatta
        if item.get("is_ui") and requested_btus and item.get("taglia_btu") in requested_btus:
            boost += 25.0

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
            if item.get("is_ue") and code in self._ac_master_ues:
                compat_uis = self._ac_master_ues[code].get("unita_interne_compatibili", [])
                filtered_uis = []
                for ui_info in compat_uis:
                    ui_code = ui_info.get("code") or ui_info.get("codice_pt")
                    if not ui_code:
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
            elif item.get("is_ui") and code in self._ac_master_uis:
                ui_meta = self._ac_master_uis[code]

                # 2.A: PAIRED_WITH_VERIFIED da kit_commerciali_inclusi
                found_kit = False
                kits = ui_meta.get("kit_commerciali_inclusi", [])
                if is_mono and kits:
                    for k in kits:
                        ue_c = k.get("unita_esterna_codice")
                        if ue_c:
                            relations.append(TypedRelation(
                                source_code=code,
                                target_code=ue_c,
                                relation_type=RelationType.PAIRED_WITH_VERIFIED,
                                provenance=f"climatizzatori_compatibilita_master.json:kit_commerciali_inclusi[id_kit={k.get('id_kit')}]",
                                target_role="UE",
                                evidence={
                                    "ui_code": code,
                                    "ue_code": ue_c,
                                    "id_kit": k.get("id_kit"),
                                    "nome_kit": k.get("nome_kit")
                                },
                                confidence=0.95
                            ))
                            found_kit = True
                            break

                # 2.B: PAIRED_WITH_DERIVED per monosplit dedicato 1-a-1 senza kit esplicito
                compat_ues = ui_meta.get("unita_esterne_compatibili", [])
                if is_mono and not found_kit and compat_ues:
                    mono_ues = [
                        ue for ue in compat_ues
                        if ue.get("tipo_sistema") == "Mono-Split" or ue.get("ports") == 1
                    ]
                    if len(mono_ues) >= 1:
                        target_ue = mono_ues[0]
                        ue_code = target_ue.get("code") or target_ue.get("codice_pt")
                        if ue_code:
                            relations.append(TypedRelation(
                                source_code=code,
                                target_code=ue_code,
                                relation_type=RelationType.PAIRED_WITH_DERIVED,
                                provenance="climatizzatori_compatibilita_master.json:unita_interne.unita_esterne_compatibili[monosplit_derived]",
                                target_role="UE",
                                evidence={
                                    "ui_code": code,
                                    "ue_code": ue_code,
                                    "tipo_sistema": "Mono-Split",
                                    "serie": target_ue.get("serie") or target_ue.get("famiglia_catalogo")
                                },
                                confidence=0.85
                            ))

                # 2.C: COMPATIBLE_WITH per tutte le altre unità esterne (multisplit / alternative)
                for ue_info in compat_ues:
                    ue_code = ue_info.get("code") or ue_info.get("codice_pt")
                    if ue_code:
                        relations.append(TypedRelation(
                            source_code=code,
                            target_code=ue_code,
                            relation_type=RelationType.COMPATIBLE_WITH,
                            provenance="climatizzatori_compatibilita_master.json:unita_interne.unita_esterne_compatibili",
                            target_role="UE",
                            evidence={
                                "ui_code": code,
                                "ue_code": ue_code,
                                "porte_attacchi": ue_info.get("porte_attacchi"),
                                "tipo_sistema": ue_info.get("tipo_sistema")
                            },
                            confidence=0.70
                        ))

        return relations

    def get_slot_quotas(self, query_context: Dict[str, Any], limit: int) -> List[SlotConfig]:
        configs: List[SlotConfig] = []
        is_ue_only = query_context.get("is_ue_only", False)
        requested_btus = query_context.get("requested_btus", [])
        has_reliable_anchor = query_context.get("has_reliable_anchor", True)

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
        if "_ac_enriched" in item:
            return
        item["_ac_enriched"] = True

        code = str(item.get("code") or "").strip()
        name = (item.get("name") or "").upper()
        mfg = (item.get("mfg_code") or "").upper()
        cat = (item.get("category_path") or "").upper()

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
