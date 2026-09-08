"""
src/core/token_parser.py
Exact Token Parser per il Catalogo Puglia Termica.
Classifica i token in modo rigoroso:
1. EXACT_RAW: corrispondenza letterale case-insensitive su MPN o codice PT indicizzato.
2. EXACT_NORMALIZED: corrispondenza esatta rimuovendo spazi/delimitatori (-, /, .),
   senza perdita di lettere, cifre o suffissi.
3. NEAR_MODEL_CANDIDATE: candidati di prossimità sintattica (stessa radice ma suffisso/revisione
   non coincidente, es. VF vs VF4, 3MXM68A vs 3MXM68A9, RXJ50A vs RXJ50A9).
   Non viene MAI considerato exact match. Nessuna sostituzione automatica arbitraria (XKE != ZKE).
4. CATALOG_VERIFIED_REVISION: solo quando la relazione di revisione è esplicitamente supportata
   dall'anagrafica/dataset.

Evita l'estrazione indiscriminata di token generici/numerici ambigui tramite:
- Boundary matching sui modelli e codici effettivamente indicizzati
- Soglie di informatività (lunghezza, presenza di lettere e cifre)
- Sub-token splitting per token concatenati da trattini (es. 'CLIMATIZZATORE-CS-TZ35ZKEW-PANASONIC')
"""

import re
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Tuple


class MatchType(str, Enum):
    EXACT_RAW = "EXACT_RAW"
    EXACT_NORMALIZED = "EXACT_NORMALIZED"
    EXACT_CATALOG_MODEL_LABEL = "EXACT_CATALOG_MODEL_LABEL"
    AMBIGUOUS_CATALOG_MODEL_LABEL = "AMBIGUOUS_CATALOG_MODEL_LABEL"
    NEAR_MODEL_CANDIDATE = "NEAR_MODEL_CANDIDATE"
    CATALOG_VERIFIED_REVISION = "CATALOG_VERIFIED_REVISION"


def normalize_token(token: str) -> str:
    """Normalizza rimuovendo delimitatori ma preservando tutte le lettere e cifre."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(token or "")).lower()


# Stop-words e token generici/rumore che non possono MAI essere considerati codici modello
GENERIC_STOP_WORDS = {
    'r32', 'r410a', 'wifi', 'wi-fi', 'classe', 'inverter', 'gas',
    'monosplit', 'multisplit', 'dual', 'trial', 'quadri', 'penta',
    'climatizzatore', 'condizionatore', 'climatizzatori', 'condizionatori',
    'split', 'btu', 'caldaia', 'caldaie', 'ventilconvettore', 'fancoil',
    'scaldabagno', 'pompa', 'pompe', 'autoclave', 'attacchi', 'motocondensante',
    'bianco', 'white', 'nero', 'black', 'silver', 'grigio', 'optional',
    'integrato', 'incluso', 'offerta', 'promo', 'serie', 'gamma', 'linea',
    'con', 'per', 'del', 'della', 'degli', 'delle', 'completa', 'compatibile'
}


class ExactTokenParser:
    """
    Parser ed estrattore di codici/modelli per l'anagrafica catalogo.
    Totalmente agnostico: supporta estrattori di label commerciali forniti da adapter di categoria.
    """

    def __init__(
        self,
        lookup_dict: Optional[Dict[str, Any]] = None,
        master_catalog: Optional[List[Dict[str, Any]]] = None,
        label_extractors: Optional[List[Any]] = None
    ):
        self._lookup: Dict[str, Any] = lookup_dict or {}
        self._label_extractors: List[Any] = label_extractors or []
        self._raw_mfg_map: Dict[str, List[Dict[str, Any]]] = {}
        self._raw_code_map: Dict[str, Dict[str, Any]] = {}
        self._norm_mfg_map: Dict[str, List[Dict[str, Any]]] = {}
        self._norm_code_map: Dict[str, Dict[str, Any]] = {}
        self._catalog_model_label_map: Dict[str, List[Dict[str, Any]]] = {}
        self._near_model_prefix_map: Dict[str, List[Dict[str, Any]]] = {}

        if master_catalog:
            self._build_indices(master_catalog)
        elif self._lookup:
            self._build_indices(list(self._lookup.values()))

    def _build_indices(self, items: List[Dict[str, Any]]):
        for it in items:
            code = str(it.get("code") or "").strip()
            mfg = str(it.get("mfg_code") or "").strip()

            if code and len(code) == 8 and code.isdigit():
                raw_c = code.lower()
                norm_c = normalize_token(code)
                self._raw_code_map[raw_c] = it
                self._norm_code_map[norm_c] = it

            if mfg and len(mfg) >= 3:
                raw_m = mfg.lower()
                norm_m = normalize_token(mfg)
                if raw_m not in self._raw_mfg_map:
                    self._raw_mfg_map[raw_m] = []
                self._raw_mfg_map[raw_m].append(it)

                if norm_m not in self._norm_mfg_map:
                    self._norm_mfg_map[norm_m] = []
                self._norm_mfg_map[norm_m].append(it)

                # Indice per near model candidates (radice >= 6 caratteri con divergenza finale di 1-2 char)
                if len(norm_m) >= 6:
                    root = norm_m[:-1]
                    if root not in self._near_model_prefix_map:
                        self._near_model_prefix_map[root] = []
                    self._near_model_prefix_map[root].append(it)
                    if len(norm_m) >= 7:
                        root2 = norm_m[:-2]
                        if root2 not in self._near_model_prefix_map:
                            self._near_model_prefix_map[root2] = []
                        self._near_model_prefix_map[root2].append(it)

            # Indice generico per sigle commerciali presenti nei nomi a catalogo ma non in mfg_code
            # Costruito tramite gli estrattori forniti dai singoli CategoryAdapter
            if self._label_extractors:
                for extractor in self._label_extractors:
                    try:
                        labels = extractor(it)
                        for lbl_info in labels:
                            raw_lbl = lbl_info.get("raw_label", "")
                            norm_lbl = lbl_info.get("normalized_label") or normalize_token(raw_lbl)
                            brand_lbl = lbl_info.get("brand", "")
                            src_field = lbl_info.get("source_field", "name")
                            provenance = lbl_info.get("provenance", "catalog")
                            if norm_lbl:
                                if norm_lbl not in self._catalog_model_label_map:
                                    self._catalog_model_label_map[norm_lbl] = []
                                self._catalog_model_label_map[norm_lbl].append({
                                    "item": it,
                                    "raw_label": raw_lbl,
                                    "normalized_label": norm_lbl,
                                    "brand": brand_lbl,
                                    "source_field": src_field,
                                    "provenance": provenance,
                                    "pt_code": code
                                })
                    except Exception:
                        pass

    def extract_model_tokens(self, query: str) -> List[str]:
        """
        Estrae i token candidato con boundary e soglie di informatività.
        Evita token numerici/generici ambigui e scompone stringhe concatenate con trattini.
        """
        valid: List[str] = []
        seen_norm: Set[str] = set()

        def add_token(tok: str):
            clean = tok.strip(" ,;:./()[]{}'\"")
            nt = normalize_token(clean)
            if not nt or nt in seen_norm or nt in GENERIC_STOP_WORDS:
                return
            # Filtra taglie generiche (es. 9000btu, 12k, 28kw)
            if re.match(r'^\d+(?:btu|k|kw)$', nt):
                return
            # Soglie di informatività:
            # - Codice PT numerico: esattamente 8 cifre
            if nt.isdigit():
                if len(nt) == 8 and nt in self._norm_code_map:
                    seen_norm.add(nt)
                    valid.append(clean)
                return
            # - Modello alfanumerico: deve contenere almeno una lettera e una cifra, lunghezza >= 4
            has_digit = any(c.isdigit() for c in nt)
            has_letter = any(c.isalpha() for c in nt)
            if has_digit and has_letter and len(nt) >= 4:
                seen_norm.add(nt)
                valid.append(clean)
            # - Codice alfabetico puro solo se è un modello esatto a catalogo di lunghezza >= 5
            elif has_letter and not has_digit and len(nt) >= 5 and nt in self._norm_mfg_map:
                seen_norm.add(nt)
                valid.append(clean)

        # 1. Estrazione standard con boundary
        raw_words = re.findall(r'[A-Za-z0-9]+(?:[\-\.\/][A-Za-z0-9]+)+|[A-Za-z0-9]{4,}', query)
        for w in raw_words:
            add_token(w)
            # 2. Sub-token boundary splitting:
            # Se un token contiene trattini (es. 'CLIMATIZZATORE-CS-TZ35ZKEW-PANASONIC'),
            # scompone e analizza le singole parti informative
            if '-' in w:
                parts = w.split('-')
                for p in parts:
                    add_token(p)
                # Prova combinazioni consecutive (es. CS + TZ35ZKEW -> CS-TZ35ZKEW)
                for i in range(len(parts) - 1):
                    add_token(f"{parts[i]}-{parts[i+1]}")

        # 3. Gestione token separati da spazio che compongono un modello indicizzato (es. 'CU 2Z50TBE')
        words = query.split()
        for i in range(len(words) - 1):
            w_comb = f"{words[i]}{words[i+1]}"
            nt_comb = normalize_token(w_comb)
            if nt_comb in self._norm_mfg_map and len(nt_comb) >= 5:
                comb_str = f"{words[i]}-{words[i+1]}"
                add_token(comb_str)

        return valid

    def parse_query_tokens(self, query: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Esegue il parsing dei token della query.
        Restituisce:
        - exact_matches: elementi aventi EXACT_RAW o EXACT_NORMALIZED match.
        - near_model_candidates: elementi con divergenza sintattica di modello/suffisso.
        """
        raw_tokens = self.extract_model_tokens(query)
        exact_matches: List[Dict[str, Any]] = []
        near_model_candidates: List[Dict[str, Any]] = []
        seen_exact_codes: Set[str] = set()
        seen_near_codes: Set[str] = set()

        # Short-circuit diretto sull'intera query
        clean_q = query.strip().lower()
        norm_q = normalize_token(query)
        if clean_q in self._raw_code_map:
            it = self._raw_code_map[clean_q]
            item_copy = dict(it)
            item_copy["_is_exact_token_match"] = True
            item_copy["_exact_match_type"] = MatchType.EXACT_RAW.value
            item_copy["_matched_token"] = query.strip()
            exact_matches.append(item_copy)
            seen_exact_codes.add(item_copy["code"])
        elif norm_q in self._norm_code_map:
            it = self._norm_code_map[norm_q]
            item_copy = dict(it)
            item_copy["_is_exact_token_match"] = True
            item_copy["_exact_match_type"] = MatchType.EXACT_NORMALIZED.value
            item_copy["_matched_token"] = query.strip()
            exact_matches.append(item_copy)
        # Controllo preventivo per sigle commerciali a catalogo composte (es. 5000M 82/4 E)
        for norm_lbl, candidates in self._catalog_model_label_map.items():
            if len(norm_lbl) >= 6 and norm_lbl in norm_q:
                unique_pt_codes = {entry["pt_code"] for entry in candidates}
                is_unique = (len(unique_pt_codes) == 1)
                for entry in candidates:
                    it = entry["item"]
                    pt_code = entry["pt_code"]
                    orig_lbl = entry["raw_label"]
                    lbl_brand = entry["brand"]
                    provenance_src = entry["provenance"]

                    if is_unique:
                        if pt_code not in seen_exact_codes:
                            seen_exact_codes.add(pt_code)
                            c_it = dict(it)
                            c_it["_is_exact_token_match"] = True
                            c_it["_exact_match_type"] = MatchType.EXACT_CATALOG_MODEL_LABEL.value
                            c_it["_matched_token"] = orig_lbl
                            c_it["_provenance"] = provenance_src
                            c_it["_catalog_model_label"] = orig_lbl
                            c_it["_is_unique_catalog_label"] = True
                            c_it["_detected_label_brand"] = lbl_brand
                            exact_matches.append(c_it)
                    else:
                        if pt_code not in seen_exact_codes and pt_code not in seen_near_codes:
                            seen_near_codes.add(pt_code)
                            c_it = dict(it)
                            c_it["_is_near_model_candidate"] = True
                            c_it["_exact_match_type"] = MatchType.AMBIGUOUS_CATALOG_MODEL_LABEL.value
                            c_it["_matched_token"] = orig_lbl
                            c_it["_provenance"] = provenance_src
                            c_it["_catalog_model_label"] = orig_lbl
                            c_it["_is_unique_catalog_label"] = False
                            c_it["_detected_label_brand"] = lbl_brand
                            near_model_candidates.append(c_it)

        for raw_tok in raw_tokens:
            tok_lower = raw_tok.lower()
            nt = normalize_token(raw_tok)

            # 1. EXACT RAW (identità letterale case-insensitive)
            found_raw = False
            if tok_lower in self._raw_code_map:
                it = self._raw_code_map[tok_lower]
                if it["code"] not in seen_exact_codes:
                    seen_exact_codes.add(it["code"])
                    c_it = dict(it)
                    c_it["_is_exact_token_match"] = True
                    c_it["_exact_match_type"] = MatchType.EXACT_RAW.value
                    c_it["_matched_token"] = raw_tok
                    exact_matches.append(c_it)
                found_raw = True

            if tok_lower in self._raw_mfg_map:
                for it in self._raw_mfg_map[tok_lower]:
                    if it["code"] not in seen_exact_codes:
                        seen_exact_codes.add(it["code"])
                        c_it = dict(it)
                        c_it["_is_exact_token_match"] = True
                        c_it["_exact_match_type"] = MatchType.EXACT_RAW.value
                        c_it["_matched_token"] = raw_tok
                        exact_matches.append(c_it)
                found_raw = True

            if found_raw:
                continue

            # 2. EXACT NORMALIZED (identità completa rimuovendo delimitatori, preservando cifre e lettere)
            found_norm = False
            if nt in self._norm_code_map:
                it = self._norm_code_map[nt]
                if it["code"] not in seen_exact_codes:
                    seen_exact_codes.add(it["code"])
                    c_it = dict(it)
                    c_it["_is_exact_token_match"] = True
                    c_it["_exact_match_type"] = MatchType.EXACT_NORMALIZED.value
                    c_it["_matched_token"] = raw_tok
                    exact_matches.append(c_it)
                found_norm = True

            if nt in self._norm_mfg_map:
                for it in self._norm_mfg_map[nt]:
                    if it["code"] not in seen_exact_codes:
                        seen_exact_codes.add(it["code"])
                        c_it = dict(it)
                        c_it["_is_exact_token_match"] = True
                        c_it["_exact_match_type"] = MatchType.EXACT_NORMALIZED.value
                        c_it["_matched_token"] = raw_tok
                        exact_matches.append(c_it)
                found_norm = True

            # 2.2 EXACT_CATALOG_MODEL_LABEL (sigle commerciali a catalogo con provenance tracciata e verifica unicità)
            if nt in self._catalog_model_label_map:
                candidates = self._catalog_model_label_map[nt]
                unique_pt_codes = {entry["pt_code"] for entry in candidates}
                is_unique = (len(unique_pt_codes) == 1)

                for entry in candidates:
                    it = entry["item"]
                    pt_code = entry["pt_code"]
                    orig_lbl = entry["raw_label"]
                    lbl_brand = entry["brand"]
                    provenance_src = entry["provenance"]

                    if is_unique:
                        if pt_code not in seen_exact_codes:
                            seen_exact_codes.add(pt_code)
                            c_it = dict(it)
                            c_it["_is_exact_token_match"] = True
                            c_it["_exact_match_type"] = MatchType.EXACT_CATALOG_MODEL_LABEL.value
                            c_it["_matched_token"] = raw_tok
                            c_it["_provenance"] = provenance_src
                            c_it["_catalog_model_label"] = orig_lbl
                            c_it["_is_unique_catalog_label"] = True
                            c_it["_detected_label_brand"] = lbl_brand
                            exact_matches.append(c_it)
                    else:
                        # Non univoco: candidate set da disambiguare, NON exact winner!
                        if pt_code not in seen_exact_codes and pt_code not in seen_near_codes:
                            seen_near_codes.add(pt_code)
                            c_it = dict(it)
                            c_it["_is_near_model_candidate"] = True
                            c_it["_exact_match_type"] = MatchType.AMBIGUOUS_CATALOG_MODEL_LABEL.value
                            c_it["_matched_token"] = raw_tok
                            c_it["_provenance"] = provenance_src
                            c_it["_catalog_model_label"] = orig_lbl
                            c_it["_is_unique_catalog_label"] = False
                            c_it["_detected_label_brand"] = lbl_brand
                            near_model_candidates.append(c_it)
                found_norm = True

            if found_norm:
                continue

            # 3. NEAR_MODEL_CANDIDATE (stessa radice >= 6 char con suffisso diverso o mancante)
            # MAI classificato come exact match!
            if nt in self._near_model_prefix_map:
                for it in self._near_model_prefix_map[nt]:
                    code = it["code"]
                    if code not in seen_exact_codes and code not in seen_near_codes:
                        seen_near_codes.add(code)
                        c_it = dict(it)
                        c_it["_is_near_model_candidate"] = True
                        c_it["_exact_match_type"] = MatchType.NEAR_MODEL_CANDIDATE.value
                        c_it["_matched_token"] = raw_tok
                        c_it["_near_model_detail"] = f"Radice coincidente tra {raw_tok} e {it.get('mfg_code')}"
                        near_model_candidates.append(c_it)

            # Caso inverso: query token ha suffisso in più rispetto al modello base a catalogo
            if len(nt) >= 6:
                root = nt[:-1]
                if root in self._norm_mfg_map:
                    for it in self._norm_mfg_map[root]:
                        code = it["code"]
                        if code not in seen_exact_codes and code not in seen_near_codes:
                            seen_near_codes.add(code)
                            c_it = dict(it)
                            c_it["_is_near_model_candidate"] = True
                            c_it["_exact_match_type"] = MatchType.NEAR_MODEL_CANDIDATE.value
                            c_it["_matched_token"] = raw_tok
                            c_it["_near_model_detail"] = f"Query ha suffisso in più rispetto al catalogo {it.get('mfg_code')}"
                            near_model_candidates.append(c_it)

        return exact_matches, near_model_candidates
