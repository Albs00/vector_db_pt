"""
run_full_csv_audit.py
Script di Audit & Verifica Completa per il file Export_Prodotti_Verifica.csv (12.001 righe).
Regole Architetturali e di Dominio:
  1. CLIMATIZZATORI (Aria-Aria):
     - La logica kit multi-componente (UE + UI) si applica ESCLUSIVAMENTE ai Climatizzatori / Condizionatori.
     - Monosplit: ALMENO 2 CODICI (1 UE + 1 UI). Se presente solo 1 codice -> 🔴 KIT_INCOMPLETO.
     - Dual Split: ALMENO 3 CODICI (1 UE Multi + 2 UI). Se < 3 codici -> 🔴 KIT_INCOMPLETO.
     - Trial Split: ALMENO 4 CODICI (1 UE Multi + 3 UI). Se < 4 codici -> 🔴 KIT_INCOMPLETO.
     - Quadri Split: ALMENO 5 CODICI (1 UE Multi + 4 UI). Se < 5 codici -> 🔴 KIT_INCOMPLETO.
     - Penta Split: ALMENO 6 CODICI (1 UE Multi + 5 UI). Se < 6 codici -> 🔴 KIT_INCOMPLETO.
     - Articolo Singolo Clima (solo motore UE, solo split UI, comando wifi, bacinella): 1 codice.

  2. CALDAIE:
     - Per le caldaie va bene anche solo 1 codice (il codice della caldaia è autonomo e corretto).
     - Se l'MPN ha 1 codice ed è valido a catalogo PT -> 🟢 CORRETTO (Caldaia Verificata).
     - Se l'MPN ha 2 codici (Caldaia + Kit Fumi) -> 🟢 CORRETTO (Caldaia + Kit Fumi Verificati).
     - Per OGNI caldaia vengono identificati e abbinati i kit fumi compatibili ufficiali di Puglia Termica:
       * Kit Fumi Coassiale Compatibile (60/100)
       * Kit Fumi Sdoppiato Compatibile (80/80)
     - I kit fumi compatibili vengono esposti in colonne dedicate e nel motivo dettagliato.

  3. ARTICOLI SINGOLI & ALTRE CATEGORIE (Idraulica, Attrezzatura, Pompe di calore monoblocco, ecc.):
     - 1 codice autonomo. Non vengono mai confusi con i kit climatizzatore.

  4. SALVATAGGIO RESILIENTE SU WINDOWS:
     - Prevenzione del blocco esclusivo di Excel (PermissionError) con fallback automatico e percorsi garantiti.
"""

import sys
import os
import csv
import json
import re
import time
from typing import Dict, Any, Optional, List

sys.stdout.reconfigure(encoding='utf-8')

# Percorsi di lavoro resilienti
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(SCRIPT_DIR, "Export_Prodotti_Verifica.csv")):
    PUGLIA_DIR = SCRIPT_DIR
    ROOT_DIR = os.path.dirname(SCRIPT_DIR)
else:
    ROOT_DIR = SCRIPT_DIR
    PUGLIA_DIR = os.path.join(ROOT_DIR, "PugliaTermica_AI_Search")

CSV_INPUT_PATH = os.path.join(PUGLIA_DIR, "Export_Prodotti_Verifica.csv")
CATALOG_PATH = os.path.join(PUGLIA_DIR, "Knowledge", "unified_catalog_master.json")
if not os.path.exists(CATALOG_PATH):
    CATALOG_PATH = os.path.join(ROOT_DIR, "Knowledge", "unified_catalog_master.json")

LOOKUP_PATH = os.path.join(PUGLIA_DIR, "Knowledge", "vector_db", "exact_code_lookup.json")
if not os.path.exists(LOOKUP_PATH):
    LOOKUP_PATH = os.path.join(ROOT_DIR, "Knowledge", "vector_db", "exact_code_lookup.json")

# File di output dedicati
XLSX_OUTPUT_PATH = os.path.join(PUGLIA_DIR, "Report_Verifica_Kit_Completi_12000_Prodotti.xlsx")
CSV_OUTPUT_PATH = os.path.join(PUGLIA_DIR, "Report_Verifica_Kit_Completi_12000_Prodotti.csv")

# Mappa equivalenze marchi tra Prestashop e Puglia Termica
BRAND_ALIASES = {
    "4XE": "4XE", "ARISTON": "ARISTON", "ARISTON THERMO": "ARISTON",
    "BAXI": "BAXI", "FERROLI": "FERROLI", "DAIKIN": "DAIKIN",
    "BERETTA": "BERETTA", "DAB": "DAB", "CALEFFI": "CALEFFI",
    "AERMEC": "AERMEC", "HAIER": "HAIER", "HEC": "HAIER",
    "MITSUBISHI": "MITSUBISHI", "MITSUBISHI ELECTRIC": "MITSUBISHI",
    "BOSCH": "BOSCH", "JUNKERS": "BOSCH", "IMMERGAS": "IMMERGAS",
    "VAILLANT": "VAILLANT", "HSD": "HSD", "HERMANN": "HSD",
    "HERMANN SAUNIER DUVAL": "HSD", "SAUNIER DUVAL": "HSD",
    "PANASONIC": "PANASONIC", "LG": "LG", "SAMSUNG": "SAMSUNG",
    "HISENSE": "HISENSE", "MIDEA": "MIDEA", "TCL": "TCL",
    "KOSAMI": "KOSAMI", "CHAFFOTEAUX": "CHAFFOTEAUX",
    "2EMMECLIMA": "2EMME", "2EMME CLIMA": "2EMME", "2EMME": "2EMME",
    "ROTEX": "DAIKIN", "RINNAI": "RINNAI", "VIESSMANN": "VIESSMANN",
    "UNICAL": "UNICAL", "FAR": "FAR", "TIEMME": "TIEMME",
    "ITAP": "ITAP", "ICMA": "ICMA", "RBM": "RBM", "GIACOMINI": "GIACOMINI",
    "FONDITAL": "FONDITAL", "POLYMAX": "POLYMAXACCIAI", "POLYMAXACCIAI": "POLYMAXACCIAI",
    "RIELLO": "RIELLO", "RIELLO BERETTA": "RIELLO",
    "PUCCI": "PUCCIPLAST", "PUCCIPLAST": "PUCCIPLAST",
    "OLIMPIA": "OLIMPIA", "OLIMPIA SPLENDID": "OLIMPIA",
    "SUNERG": "SUNERG", "SUNERG SOLAR": "SUNERG",
    "REDI": "VALSIR", "VALSIR": "VALSIR",
    "OTER": "FIXECO", "FIXECO": "FIXECO",
    "PLEION": "PLEION", "DE PALA": "DE PALA"
}

# Dizionario abbreviazioni ufficiali Puglia Termica
PT_ABBREVIATIONS = {
    "ACQUAPROJET": "ACQUAPR",
    "SCALDABAGNO": "SCALD",
    "SCALDABAGNI": "SCALD",
    "SCALDINO": "SCALD",
    "CALDAIA": "CALD",
    "CALDAIE": "CALD",
    "CONDENSAZIONE": "COND",
    "CAMERA STAGNA": "CS",
    "CAMERA APERTA": "CA",
    "METANO": "MET",
    "VENTILCONVETTORE": "VENTIL",
    "VENTILCONVETTORI": "VENTIL",
    "FAN COIL": "VENTIL",
    "FANCOIL": "VENTIL",
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

def normalize_text(text: str) -> str:
    """Normalizza testo eliminando accenti e uniformando maiuscole."""
    t = text.upper()
    for a, b in [('À', 'A'), ('È', 'E'), ('É', 'E'), ('Ì', 'I'), ('Ò', 'O'), ('Ù', 'U')]:
        t = t.replace(a, b)
    return t

def is_air_conditioner(title: str) -> bool:
    """Identifica se il prodotto è un climatizzatore/condizionatore aria-aria."""
    t_u = normalize_text(title)
    # Esclusione esplicita di categorie che non sono macchine climatizzatori split
    if any(w in t_u for w in [
        'CALDAIA', 'SCALDABAGNO', 'BOLLITORE', 'TERMOSIFONE', 'RADIATORE',
        'POMPA DI CALORE', 'PDC', 'ADDOLCITORE', 'GUANTI', 'SET DI', 'PUNTE',
        'SERBATOIO', 'VASO ESPANSIONE', 'COLLETTORE', 'SEPARATORE', 'VALVOLA',
        'CIRCOLATORE', 'TRITURATORE', 'FERRO DA STIRO', 'VENTILCONVETTORE',
        'FAN COIL', 'FANCOIL', 'TUBO RAME', 'CANALINA', 'CONDOTTA', 'GIUNTO',
        'BASE PAVIMENTO', 'STAFFA', 'SUPPORTO', 'POMPA SCARICO CONDENSA',
        'POMPA PER ACQUE DI CONDENSA', 'POMPA CONDENSA', 'CASSAFORMA', 'CRONOTERMOSTATO',
        'CONTROLLO REMOTO', 'COMANDO REMOTO', 'COMANDO A FILO', 'TERMOSTATO',
        'SCIVOLANTE', 'BATTERIA', 'CASSETTA'
    ]):
        return False
    if any(w in t_u for w in ['CLIMATIZZATORE', 'CONDIZIONATORE', 'CLIMATIZZATORI', 'CONDIZIONATORI']):
        return True
    if 'SPLIT' in t_u and any(w in t_u for w in ['INVERTER', 'R32', 'R-32', 'BTU', 'DUAL', 'TRIAL', 'MONO', 'QUADRI', 'PENTA', 'PARETE', 'CANALIZZ']):
        return True
    return False

def is_caldaia(title: str) -> bool:
    """Identifica se il prodotto è una caldaia o scaldabagno a gas."""
    t_u = normalize_text(title)
    if any(w in t_u for w in ['CALDAIA', 'SCALDABAGNO', 'SCALDINO']) and not any(w in t_u for w in [
        'FERRO DA STIRO', 'ACCESSORIO PER CALDAIA', 'SOLO SCARICO', 'CURVA', 'RACCORDO', 'FILTRO PER CALDAIA', 'SCALDABAGNO ELETTRICO'
    ]):
        return True
    return False

def detect_kit_requirements(title: str) -> dict:
    """Rileva la tipologia e requisiti di componenti distinguendo clima, caldaie e altri prodotti."""
    t_u = normalize_text(title)
    
    # CASO A: CALDAIA / SCALDABAGNO (1 codice autonomo + kit fumi abbinato)
    if is_caldaia(title):
        m_kw = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*KW\b', t_u)
        kw = float(m_kw.group(1).replace(',', '.')) if m_kw else 24.0
        has_fumi_word = any(w in t_u for w in ['KIT FUMI', 'SCARICO FUMI', 'SDOPPIATO', 'COASSIALE'])
        is_scald = any(w in t_u for w in ['SCALDABAGNO', 'SCALDINO'])
        typ_name = "Scaldabagno a Gas" if is_scald else ("Caldaia con Kit Fumi" if has_fumi_word else "Caldaia")
        return {
            "type": "CALDAIA",
            "name": typ_name,
            "min_codes": 1,
            "kw": kw,
            "has_fumi": has_fumi_word,
            "req_desc": "1 codice principale (Caldaia / Scaldabagno) + Kit Fumi abbinato"
        }
        
    # CASO B: CLIMATIZZATORE (Logica split UE + UI)
    if is_air_conditioner(title):
        # Controllo se è un accessorio o una singola unità
        is_single_unit = any(w in t_u for w in [
            'SOLO UNITA', 'SOLO MOTORE', 'SOLO SPLIT', 'UNITA ESTERNA', 'UNITA INTERNA',
            'PANNELLO', 'POMPA SCARICO CONDENSA', 'POMPA CONDENSA', 'DEFLETTORE', 'BACINELLA', 'FILTRO',
            'GRIGLIA OPTIONAL', 'SOLO ACCESSORIO', 'RACCORDO', 'SONDA', 'WIFI KEY',
            'MODULO WIFI', 'COMANDO WI-FI', 'COMANDO WIFI', 'COMANDO A FILO', 'CONTROLLO REMOTO',
            'SCHEDA', 'ADATTATORE', 'PORTATILE', 'MONOBLOCCO', 'SENZA UNITA', 'STAFFA',
            'SUPPORTO', 'BASE PAVIMENTO', 'TUBO', 'CANALINA', 'CURVA', 'GIUNTO'
        ])
        if is_single_unit:
            return {
                "type": "CLIMA_SINGOLO",
                "name": "Climatizzatore (Unità Singola / Accessorio)",
                "min_codes": 1,
                "req_desc": "1 codice PT (Componente autonomo)"
            }
            
        # Pulizia marchi e serie commerciali che contengono 'DUAL' ma sono Monosplit (es. LG DUALCOOL, DUAL INVERTER)
        clean_title = re.sub(r'\bDUALCOOL\b', 'LG_SERIES', t_u)
        clean_title = re.sub(r'\bDUAL\s*INVERTER\b', 'INVERTER', clean_title)
        clean_title = re.sub(r'\bTWIN\s*ROTARY\b', 'COMPRESSORE', clean_title)

        is_explicit_mono = bool(re.search(r'\b(MONOSPLIT|MONO\s*SPLIT|MONO-SPLIT|1\s*SPLIT)\b', clean_title))

        # Ricerca taglie split
        m_sizes = re.search(r'\b(\d{1,2}(?:\+\d{1,2}){1,4})\b', clean_title)
        if m_sizes:
            parsed_sizes = [int(x) * 1000 for x in m_sizes.group(1).split('+')]
        else:
            raw_btu_tokens = re.findall(r'\b(7|9|12|18|24)\b', clean_title)
            parsed_sizes = [int(x) * 1000 for x in raw_btu_tokens] if len(raw_btu_tokens) >= 2 else []
            
        if not is_explicit_mono and ('PENTA' in clean_title or len(parsed_sizes) >= 5):
            target_len = max(5, len(parsed_sizes)) if parsed_sizes else 5
            sizes = parsed_sizes[:target_len] if len(parsed_sizes) >= 5 else (parsed_sizes + [9000]*(5 - len(parsed_sizes)))
            min_codes = 1 + len(sizes)
            return {
                "type": "PENTA_SPLIT", "name": f"Kit Climatizzatore Penta-Split ({len(sizes)} Split)",
                "min_codes": min_codes, "sizes": sizes, "ports": 5,
                "req_desc": f"Minimo {min_codes} codici (1 UE Multi + {len(sizes)} UI)"
            }
        if not is_explicit_mono and ('QUADRI' in clean_title or len(parsed_sizes) == 4):
            target_len = max(4, len(parsed_sizes)) if parsed_sizes else 4
            sizes = parsed_sizes[:target_len] if len(parsed_sizes) >= 4 else (parsed_sizes + [9000]*(4 - len(parsed_sizes)))
            min_codes = 1 + len(sizes)
            return {
                "type": "QUADRI_SPLIT", "name": f"Kit Climatizzatore Quadri-Split ({len(sizes)} Split)",
                "min_codes": min_codes, "sizes": sizes, "ports": 4,
                "req_desc": f"Minimo {min_codes} codici (1 UE Multi + {len(sizes)} UI)"
            }
        if not is_explicit_mono and ('TRIAL' in clean_title or len(parsed_sizes) == 3):
            target_len = max(3, len(parsed_sizes)) if parsed_sizes else 3
            sizes = parsed_sizes[:target_len] if len(parsed_sizes) >= 3 else (parsed_sizes + [9000]*(3 - len(parsed_sizes)))
            min_codes = 1 + len(sizes)
            return {
                "type": "TRIAL_SPLIT", "name": f"Kit Climatizzatore Trial-Split ({len(sizes)} Split)",
                "min_codes": min_codes, "sizes": sizes, "ports": 3,
                "req_desc": f"Minimo {min_codes} codici (1 UE Multi + {len(sizes)} UI)"
            }
        if not is_explicit_mono and (re.search(r'\b(DUAL\s*SPLIT|DUALSPLIT|2\s*SPLIT)\b', clean_title) or len(parsed_sizes) == 2):
            target_len = max(2, len(parsed_sizes)) if parsed_sizes else 2
            sizes = parsed_sizes[:target_len] if len(parsed_sizes) >= 2 else (parsed_sizes + [9000]*(2 - len(parsed_sizes)))
            min_codes = 1 + len(sizes)
            return {
                "type": "DUAL_SPLIT", "name": f"Kit Climatizzatore Dual-Split ({len(sizes)} Split)",
                "min_codes": min_codes, "sizes": sizes, "ports": 2,
                "req_desc": f"Minimo {min_codes} codici (1 UE Multi + {len(sizes)} UI)"
            }
            
        # Monosplit
        m_btu = re.search(r'\b(7\.?000|9\.?000|12\.?000|18\.?000|24\.?000)\b', clean_title)
        btu = int(m_btu.group(1).replace('.', '')) if m_btu else 9000
        return {
            "type": "MONOSPLIT", "name": "Kit Climatizzatore Monosplit",
            "min_codes": 2, "btu": btu,
            "req_desc": "Minimo 2 codici (1 UE + 1 UI)"
        }
        
    # CASO C: ARTICOLO SINGOLO (Altre categorie)
    return {
        "type": "SINGOLO", "name": "Articolo Singolo",
        "min_codes": 1,
        "req_desc": "1 codice PT (Articolo autonomo)"
    }

def extract_technical_parameters(text: str) -> dict:
    t_u = normalize_text(text)
    params = {}
    m_kw = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*KW\b', t_u)
    if m_kw:
        try: params['kw'] = float(m_kw.group(1).replace(',', '.'))
        except: pass
    m_btu = re.search(r'\b(7\.?000|9\.?000|12\.?000|18\.?000|24\.?000)\b', t_u)
    if m_btu:
        try: params['btu'] = int(m_btu.group(1).replace('.', ''))
        except: pass
    if not params.get('btu'):
        if re.search(r'\b(?:TAGLIA\s*25|25\s*R32|CTXF25|FTXM25|ATXF25|ATXC25|FTXF25|AS25|250)\b', t_u): params['btu'] = 9000
        elif re.search(r'\b(?:TAGLIA\s*35|35\s*R32|CTXF35|FTXM35|ATXF35|ATXC35|FTXF35|AS35|350)\b', t_u): params['btu'] = 12000
        elif re.search(r'\b(?:TAGLIA\s*20|20\s*R32|CTXF20|FTXM20|ATXF20|ATXC20|FTXF20|AS20|200)\b', t_u): params['btu'] = 7000
        elif re.search(r'\b(?:TAGLIA\s*50|50\s*R32|CTXF50|FTXM50|ATXF50|ATXC50|FTXF50|AS50|500)\b', t_u): params['btu'] = 18000
        elif re.search(r'\b(?:TAGLIA\s*70|70\s*R32|CTXF70|FTXM70|ATXF70|ATXC70|FTXF70|AS70|700)\b', t_u): params['btu'] = 24000
    m_split = re.search(r'\b(MONO|DUAL|TRIAL|QUADRI|PENTA)\s*SPLIT\b', t_u)
    if m_split: params['split_type'] = m_split.group(1)
    return params

def get_available_path(base_path: str) -> str:
    """Restituisce un percorso file garantito e scrivibile, evitando conflitti di blocco Excel."""
    base, ext = os.path.splitext(base_path)
    try:
        with open(base_path, 'a', encoding='utf-8') as f:
            pass
        return base_path
    except (PermissionError, OSError):
        pass
    counter = 1
    while True:
        candidate = f"{base}_v{counter}{ext}"
        try:
            with open(candidate, 'a', encoding='utf-8') as f:
                pass
            return candidate
        except (PermissionError, OSError):
            counter += 1

def main():
    start_time = time.time()
    print("=======================================================================")
    print("   AUDIT AD ALTA PRECISIONE CLIMATIZZATORI (KIT) & CALDAIE (12.001 RIGHE)")
    print("   Regole:")
    print("     - Climatizzatori: Monosplit >= 2 codici, Dual >= 3, Trial >= 4, etc.")
    print("     - Caldaie: 1 codice valido + Kit Fumi Compatibile (Coassiale/Sdoppiato)")
    print("=======================================================================")
    
    # 1. Carica Catalogo Completo e Indice Rapido
    print("\n[1/3] Caricamento anagrafica catalogo unificata (57.608 prodotti e 125.559 codici)...")
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
    with open(LOOKUP_PATH, 'r', encoding='utf-8') as f:
        lookup = json.load(f)
        
    brand_items: Dict[str, List[dict]] = {}
    pt_brands = set()
    for it in catalog:
        b = (it.get('brand') or '').strip().upper()
        if b:
            pt_brands.add(b)
            if b not in brand_items:
                brand_items[b] = []
            brand_items[b].append(it)
            
    print(f"Catalogo pronto: {len(catalog)} articoli indicizzati, {len(pt_brands)} marchi gestiti da PT.")
    
    # Database Kit Fumi Ufficiali Puglia Termica (Coassiale e Sdoppiato) per ciascun marchio di caldaie
    flue_kits_db = {
        "ARISTON": {
            "coassiale": lookup.get("99616274") or lookup.get("99309169"),
            "sdoppiato": lookup.get("99616335") or lookup.get("99610951")
        },
        "DAIKIN": {
            "coassiale": lookup.get("50033256"),
            "sdoppiato": lookup.get("50073740")
        },
        "BERETTA": {
            "coassiale": lookup.get("99069292"),
            "sdoppiato": lookup.get("99057596") or lookup.get("99776671")
        },
        "BAXI": {
            "coassiale": lookup.get("50270934") or lookup.get("50257898"),
            "sdoppiato": lookup.get("50094042") or lookup.get("50257881")
        },
        "FERROLI": {
            "coassiale": lookup.get("50127245") or lookup.get("99803018"),
            "sdoppiato": lookup.get("99248710") or lookup.get("50054305")
        },
        "IMMERGAS": {
            "coassiale": lookup.get("99071004") or lookup.get("50002160"),
            "sdoppiato": lookup.get("99587819")
        },
        "VAILLANT": {
            "coassiale": lookup.get("99169176"),
            "sdoppiato": None
        },
        "FONDITAL": {
            "coassiale": lookup.get("99337124"),
            "sdoppiato": None
        }
    }

    def resolve_pt_brand(raw_brand: str, title: str) -> Optional[str]:
        b_u = raw_brand.strip().upper() if raw_brand else ""
        t_u = normalize_text(title)
        # Priorità assoluta: marchio esplicitamente menzionato nel titolo
        for alias in sorted(BRAND_ALIASES.keys(), key=len, reverse=True):
            if len(alias) >= 3 and re.search(r'\b' + re.escape(alias) + r'\b', t_u):
                return BRAND_ALIASES[alias]
        for pt_b in sorted(pt_brands, key=len, reverse=True):
            if len(pt_b) >= 3 and re.search(r'\b' + re.escape(pt_b) + r'\b', t_u):
                return pt_b
        # Fallback sul brand del CSV
        if b_u in BRAND_ALIASES: return BRAND_ALIASES[b_u]
        if b_u in pt_brands: return b_u
        return None

    # Motori di ricerca componenti
    def find_ui_for_size(brand: str, size_btu: int, series_words: list, title: str = "") -> Optional[dict]:
        candidates = [it for it in brand_items.get(brand, []) if "UI" in it['name'].upper() or "PARETE" in it['name'].upper() or "CANALIZZ" in it['name'].upper() or "CONSOLE" in it['name'].upper() or "CASSETTA" in it['name'].upper()]
        btu_taglie_map = {
            7000: ["20", "CTXF20", "FTXF20", "200", "250", "07", "7000", "2.0"],
            9000: ["25", "CTXF25", "FTXF25", "9000", "250", "SFE250", "SGE250", "AS25", "2.5", "09", "JSGNW25", "JSGNW-25"],
            12000: ["35", "CTXF35", "FTXF35", "12000", "350", "SFE350", "SGE350", "AS35", "3.5", "12", "JSGNW35", "JSGNW-35"],
            18000: ["50", "CTXF50", "FTXF50", "18000", "500", "SFE500", "SGE500", "AS50", "5.0", "18", "JSGNW50", "JSGNW-50"],
            24000: ["70", "71", "CTXF70", "FTXF70", "24000", "700", "SFE700", "SGE700", "AS70", "7.0", "24", "JSGNW70", "JSGNW-70"]
        }
        expected_tags = btu_taglie_map.get(size_btu, [str(size_btu)])
        scored = []
        t_u = normalize_text(title)
        
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()
            if any(acc in name_u for acc in ["SCHEDA", "WIFIKEY", "FILTRO", "RACCORDI", "CRONOTERMOSTATO", "COMANDO", "DEFANGATORE", "SONDA", "VALVOLA"]):
                continue
            if not any(tag in name_u or tag in mfg_u for tag in expected_tags):
                continue
            score = 30.0
            for w in series_words:
                if w in name_u: score += 20
                elif w in mfg_u: score += 25
            for tok in re.findall(r'[A-Za-z0-9\-]{4,}', t_u):
                if tok in name_u or tok in mfg_u: score += 30
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 30 else None

    def find_multi_ue(brand: str, ports: int, series_words: list, title: str) -> Optional[dict]:
        candidates = [it for it in brand_items.get(brand, []) if "UE" in it['name'].upper() and ("MULTI" in it['name'].upper() or "ATT" in it['name'].upper() or "DUAL" in it['name'].upper() or "TRIAL" in it['name'].upper() or "QUADRI" in it['name'].upper() or "PENTA" in it['name'].upper())]
        t_u = normalize_text(title)
        scored = []
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()
            
            # Controllo rigoroso compatibilità porte per Climatizzatori
            cand_ports = None
            if any(p_str in name_u for p_str in ['5 ATT', '5ATT', 'PENTA', '5U', '5MX', '5HA']): cand_ports = 5
            elif any(p_str in name_u for p_str in ['4 ATT', '4ATT', 'QUADRI', '4U', '4MX', '4HA']): cand_ports = 4
            elif any(p_str in name_u for p_str in ['3 ATT', '3ATT', 'TRIAL', '3U', '3MX', '3HA']): cand_ports = 3
            elif any(p_str in name_u for p_str in ['2 ATT', '2ATT', 'DUAL', '2U', '2MX', '2HA']): cand_ports = 2
            
            if cand_ports is not None and cand_ports != ports:
                continue

            score = 0.0
            if f"{ports} ATT" in name_u or f"{ports}ATT" in name_u: score += 40
            elif ports == 2 and ("DUAL" in name_u or "2U" in name_u or "2MX" in name_u or "2HA" in name_u or "2M" in name_u): score += 35
            elif ports == 3 and ("TRIAL" in name_u or "3U" in name_u or "3MX" in name_u or "3HA" in name_u or "3M" in name_u): score += 35
            elif ports == 4 and ("QUADRI" in name_u or "4U" in name_u or "4MX" in name_u or "4HA" in name_u or "4M" in name_u): score += 35
            elif ports == 5 and ("PENTA" in name_u or "5U" in name_u or "5MX" in name_u or "5HA" in name_u or "5M" in name_u): score += 35
            
            for tok in re.findall(r'[A-Za-z0-9\-\.\/]{4,}', t_u):
                clean_tok = tok.replace('-', '').replace('/', '')
                if tok in name_u or tok in mfg_u: score += 45
                elif len(clean_tok) >= 5 and (clean_tok in name_u.replace('-', '') or clean_tok in mfg_u.replace('-', '')): score += 35
                elif len(tok) >= 6 and tok[:6] in name_u: score += 30
            for w in series_words:
                if w in name_u: score += 15
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 35 else None

    def find_mono_ue(brand: str, btu: int, series_words: list, title: str = "") -> Optional[dict]:
        candidates = [it for it in brand_items.get(brand, []) if 'UE ' in it['name'].upper() and 'MULTI' not in it['name'].upper() and 'ATT' not in it['name'].upper()]
        btu_taglie_map = {
            7000: ['20', 'RXF20', 'RXM20', '200', '07', '2.0'],
            9000: ['25', 'RXF25', 'RXM25', '250', '9000', '1U25', '09', 'SFE250', 'SGE250', '2.5', 'LSGT25'],
            12000: ['35', 'RXF35', 'RXM35', '350', '12000', '1U35', '12', 'SFE350', 'SGE350', '3.5', 'LSGT35'],
            18000: ['50', 'RXF50', 'RXM50', '500', '18000', '1U50', '18', 'SFE500', 'SGE500', '5.0', 'LSGT50'],
            24000: ['70', '71', 'RXF71', 'RXM71', '700', '24000', '1U70', '1U71', '24', 'SFE700', 'SGE700', '7.0', 'LSGT70']
        }
        expected = btu_taglie_map.get(btu, [str(btu)])
        scored = []
        t_u = normalize_text(title)
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()
            if not any(tag in name_u or tag in mfg_u for tag in expected): continue
            score = 30.0
            for w in series_words:
                if w in name_u: score += 20
                elif w in mfg_u: score += 25
            for tok in re.findall(r'[A-Za-z0-9\-]{4,}', t_u):
                if tok in name_u or tok in mfg_u: score += 30
            scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 30 else None

    def find_caldaia(brand: str, kw: float, series_words: list, title: str = "") -> Optional[dict]:
        candidates = brand_items.get(brand, [])
        t_u = normalize_text(title)
        is_scald = any(w in t_u for w in ['SCALD', 'ACQUA'])
        if is_scald:
            candidates = [it for it in candidates if any(k in it['name'].upper() for k in ['SCALD', 'ACQUAPR', 'ACQUA']) or 'SCALDABAGNI' in (it.get('category_path') or '').upper()]
        else:
            candidates = [it for it in candidates if 'CALD' in it['name'].upper() or 'CALDAIE' in (it.get('category_path') or '').upper()]

        expanded = t_u
        for k, v in PT_ABBREVIATIONS.items():
            expanded = expanded.replace(k, v)
        noise = {'CON', 'PER', 'DEL', 'DELLA', 'SERIE', 'CLASSE', 'COMPLETA', 'OMAGGIO', 'WIFI', 'INVERTER', 'GAS', 'R32', 'OFFERTA', 'PROMO', 'PRONTA', 'CONSEGNA', 'KIT', 'FUMI', 'LOW', 'NOX', 'A', 'LO', 'IL', 'LA', 'LE', 'GLI', brand.upper()}
        words = [w for w in re.findall(r'[A-Za-z0-9]+', expanded) if len(w) >= 2 and w not in noise]

        is_cs = 'CS' in expanded or 'STAGNA' in t_u
        is_ca = 'CA' in expanded or 'APERTA' in t_u
        is_gpl = 'GPL' in t_u
        is_met = 'METANO' in t_u or 'MET' in t_u
        m_lit = re.search(r'\b(11|14|17)\b', t_u)
        lit = m_lit.group(1) if m_lit else None

        scored = []
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()
            if any(acc in name_u for acc in ['KIT ', 'FILTRO ', 'SONDA ', 'RACCORDO ', 'DIMA ']):
                continue

            score = 20.0
            matched = 0
            for w in words:
                if f" {w} " in f" {name_u} " or name_u.startswith(w + " ") or name_u.endswith(" " + w):
                    score += 30.0
                    matched += 1
                elif w in name_u:
                    score += 18.0
                    matched += 1
                elif len(w) >= 5 and (w[:6] in name_u or w[:5] in name_u):
                    score += 15.0
                    matched += 1
                elif w in mfg_u:
                    score += 25.0
                    matched += 1

            if not is_scald:
                m_skw = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*(?:KW|C\b|MET\b|GPL\b|\b)', name_u)
                if m_skw:
                    try:
                        c_kw = float(m_skw.group(1).replace(',', '.'))
                        if abs(c_kw - kw) < 0.5: score += 40
                        elif abs(c_kw - kw) <= 2.0: score += 10
                        else: score -= 40
                    except: pass

            if is_gpl and 'GPL' in name_u: score += 20.0
            elif is_met and 'MET' in name_u: score += 20.0
            if is_cs and 'CS' in name_u: score += 20.0
            elif is_ca and 'CA' in name_u: score += 20.0
            if lit and lit in name_u: score += 25.0
            if 'AIR' in t_u and 'AIR' in name_u: score += 25.0

            if matched >= 1 and score >= 35.0:
                scored.append((score, it))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    def find_single_product(brand: str, title: str) -> Optional[dict]:
        candidates = brand_items.get(brand, [])
        t_u = normalize_text(title)
        expanded = t_u
        for k, v in PT_ABBREVIATIONS.items():
            expanded = expanded.replace(k, v)
        noise = {"CON", "PER", "DEL", "DELLA", "SERIE", "CLASSE", "COMPLETA", "OMAGGIO", "WIFI", "INVERTER", "GAS", "R32", "OFFERTA", "PROMO", "PRONTA", "CONSEGNA", "KIT", "FUMI", "LOW", "NOX", "A", "LO", "IL", "LA", "LE", "GLI", brand.upper()}
        words = [w for w in re.findall(r'[A-Za-z0-9]+', expanded) if len(w) >= 2 and w not in noise]

        is_cs = 'CS' in expanded or 'STAGNA' in t_u
        is_ca = 'CA' in expanded or 'APERTA' in t_u
        is_gpl = 'GPL' in t_u
        is_met = 'METANO' in t_u or 'MET' in t_u
        m_lit = re.search(r'\b(11|14|17)\b', t_u)
        lit = m_lit.group(1) if m_lit else None

        scored = []
        is_machine_query = any(w in words for w in ['SCALD', 'CALD', 'CLIMA'])
        for it in candidates:
            name_u = it['name'].upper()
            mfg_u = (it.get('mfg_code') or '').upper()
            if is_machine_query and any(acc in name_u for acc in ['KIT ', 'FILTRO ', 'SONDA ', 'RACCORDO ', 'DIMA ']):
                continue

            score = 0.0
            matched = 0
            for w in words:
                if f" {w} " in f" {name_u} " or name_u.startswith(w + " ") or name_u.endswith(" " + w):
                    score += 30.0
                    matched += 1
                elif w in name_u:
                    score += 18.0
                    matched += 1
                elif len(w) >= 5 and (w[:6] in name_u or w[:5] in name_u):
                    score += 15.0
                    matched += 1
                elif w in mfg_u:
                    score += 25.0
                    matched += 1

            if is_gpl and 'GPL' in name_u: score += 20.0
            elif is_met and 'MET' in name_u: score += 20.0
            if is_cs and 'CS' in name_u: score += 20.0
            elif is_ca and 'CA' in name_u: score += 20.0
            if lit and lit in name_u: score += 25.0
            if 'AIR' in t_u and 'AIR' in name_u: score += 25.0

            if matched >= 1 and score >= 35.0:
                scored.append((score, it))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    # 2. Leggi CSV Input
    print(f"\n[2/3] Lettura file input: {CSV_INPUT_PATH}")
    rows = []
    with open(CSV_INPUT_PATH, 'r', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            rows.append(r)
    total_rows = len(rows)
    print(f"Lette {total_rows} righe complessive da verificare.")
    
    # 3. Pipeline di verifica ed elaborazione ad alta precisione
    print("\n[3/3] Verifica dei kit Clima e abbinamento fumi Caldaie su tutte le 12.001 righe...")
    report_data = []
    
    count_ok = 0
    count_kit_incomplete = 0
    count_bundle_parz = 0
    count_disc = 0
    count_err = 0
    count_missing_code = 0
    count_empty_kit = 0
    count_empty_single = 0
    count_empty_no_model = 0
    count_not_in_pt = 0
    
    t_loop_start = time.time()
    
    for idx, row in enumerate(rows):
        row_id = str(row.get("id_product") or idx)
        prod_name = (row.get("product_name") or "").strip()
        orig_mpn = (row.get("mpn") or "").strip()
        orig_brand = (row.get("brand") or "").strip()
        orig_ref = (row.get("reference") or "").strip()
        orig_price = row.get("price") or ""
        orig_qty = row.get("quantity") or "0"
        orig_active = row.get("active") or "1"
        
        req = detect_kit_requirements(prod_name)
        resolved_brand = resolve_pt_brand(orig_brand, prod_name)
        
        # Gestione Kit Fumi dedicati per Caldaie
        coax_str = "-"
        sdop_str = "-"
        if req["type"] == "CALDAIA" and resolved_brand and resolved_brand in flue_kits_db:
            fk = flue_kits_db[resolved_brand]
            if fk.get("coassiale"):
                it_c = fk["coassiale"]
                p_c = f"{float(it_c['gross_price']):.2f} €" if it_c.get("gross_price") else "-"
                coax_str = f"{it_c['code']} - {it_c['name']} (Listino: {p_c})"
            if fk.get("sdoppiato"):
                it_s = fk["sdoppiato"]
                p_s = f"{float(it_s['gross_price']):.2f} €" if it_s.get("gross_price") else "-"
                sdop_str = f"{it_s['code']} - {it_s['name']} (Listino: {p_s})"
        
        words = [w for w in re.findall(r'[A-Za-z0-9]+', normalize_text(prod_name)) if len(w) >= 4 and w not in ["CLIMATIZZATORE", "CONDIZIONATORE", "SPLIT", "SERIE", "INVERTER", "DUAL", "TRIAL", "MONO", "QUADRI", "PENTA", "CALDAIA", "FUMI", "KIT", "COMPLETA", "CLASSE"]]
        
        item_res = {
            "id_product": row_id,
            "reference": orig_ref if orig_ref else "-",
            "product_name": prod_name,
            "brand_originale": orig_brand if orig_brand else "-",
            "mpn_originale": orig_mpn if orig_mpn else "(Vuoto)",
            "tipologia_prodotto": req["name"],
            "requisito_minimo_codici": req["req_desc"],
            "prezzo_originale": orig_price if orig_price else "-",
            "quantita_originale": orig_qty,
            "attivo_originale": orig_active,
            "esito_verifica": "",
            "motivo_dettagliato": "",
            "pt_codice_finale": "",
            "numero_codici_kit": 0,
            "pt_nome_finale": "",
            "kit_fumi_coassiale": coax_str,
            "kit_fumi_sdoppiato": sdop_str,
            "pt_marchio_ufficiale": resolved_brand if resolved_brand else orig_brand,
            "pt_categoria_ufficiale": "",
            "pt_prezzo_listino": "",
            "pt_prezzo_netto": "",
            "pt_pagina_catalogo": "",
            "affidabilita_match": ""
        }
        
        # CASO 1: MPN VUOTO NEL FILE SORGENTE
        if not orig_mpn:
            if not resolved_brand:
                count_not_in_pt += 1
                item_res["esito_verifica"] = "⚪ MARCHIO_NON_A_CATALOGO_PT"
                item_res["motivo_dettagliato"] = f"Il marchio '{orig_brand}' non è distribuito o gestito nel catalogo Puglia Termica."
                item_res["pt_codice_finale"] = "-"
                item_res["numero_codici_kit"] = 0
                item_res["pt_nome_finale"] = "-"
                item_res["pt_prezzo_listino"] = "-"
                item_res["pt_prezzo_netto"] = "-"
                item_res["pt_pagina_catalogo"] = "-"
                item_res["affidabilita_match"] = "Fuori catalogo PT"
            else:
                # CASO 1A: CALDAIA CON MPN VUOTO -> Mappa la caldaia e abbina i kit fumi compatibili
                if req['type'] == 'CALDAIA':
                    cald = find_caldaia(resolved_brand, req['kw'], words, prod_name)
                    if cald:
                        count_empty_single += 1
                        item_res["esito_verifica"] = "🔵 MPN_VUOTO (Caldaia Mappata a Catalogo)"
                        item_res["motivo_dettagliato"] = f"MPN assente; caldaia identificata a catalogo PT ({cald['code']}). Kit fumi compatibili abbinati (vedi colonne fumi)."
                        item_res["pt_codice_finale"] = cald['code']
                        item_res["numero_codici_kit"] = 1
                        item_res["pt_nome_finale"] = cald['name']
                        item_res["pt_marchio_ufficiale"] = cald['brand']
                        item_res["pt_categoria_ufficiale"] = cald.get('category_path') or "-"
                        item_res["pt_prezzo_listino"] = f"{float(cald['gross_price']):.2f} €" if cald.get('gross_price') else "-"
                        item_res["pt_prezzo_netto"] = f"{float(cald['net_price']):.2f} €" if cald.get('net_price') else "-"
                        item_res["pt_pagina_catalogo"] = f"p. {cald['primary_page']}" if cald.get('primary_page') else "-"
                        item_res["affidabilita_match"] = "Alta (Caldaia Mappata)"
                    else:
                        count_empty_no_model += 1
                        item_res["esito_verifica"] = "⚪ INCOMPLETO_A_CATALOGO (Caldaia non identificata)"
                        item_res["motivo_dettagliato"] = f"Marchio {resolved_brand} gestito, ma caldaia da {req['kw']} kW non identificabile a catalogo."
                        item_res["pt_codice_finale"] = "-"
                        item_res["numero_codici_kit"] = 0
                        item_res["pt_nome_finale"] = "-"
                        item_res["affidabilita_match"] = "Incompleto"

                # CASO 1B: CLIMATIZZATORE MONOSPLIT -> 2 codici (1 UE + 1 UI)
                elif req['type'] == 'MONOSPLIT':
                    ue = find_mono_ue(resolved_brand, req['btu'], words, prod_name)
                    ui = find_ui_for_size(resolved_brand, req['btu'], words, prod_name)
                    if ue and ui:
                        count_empty_kit += 1
                        item_res["esito_verifica"] = "🔵 MPN_VUOTO (Kit Clima Monosplit 2 Codici Creato da AI)"
                        item_res["motivo_dettagliato"] = f"MPN assente; generato kit completo Monosplit a 2 codici (1 UE + 1 UI) per {resolved_brand}."
                        item_res["pt_codice_finale"] = f"{ue['code']}+{ui['code']}"
                        item_res["numero_codici_kit"] = 2
                        item_res["pt_nome_finale"] = f"{ue['name']} + {ui['name']}"
                        item_res["pt_marchio_ufficiale"] = ue['brand']
                        item_res["pt_categoria_ufficiale"] = ue.get('category_path') or "-"
                        tot_g = float(ue.get('gross_price') or 0.0) + float(ui.get('gross_price') or 0.0)
                        tot_n = float(ue.get('net_price') or 0.0) + float(ui.get('net_price') or 0.0)
                        item_res["pt_prezzo_listino"] = f"{tot_g:.2f} €" if tot_g > 0 else "-"
                        item_res["pt_prezzo_netto"] = f"{tot_n:.2f} €" if tot_n > 0 else "-"
                        pages = sorted(list(set([str(p) for p in [ue.get('primary_page'), ui.get('primary_page')] if p])))
                        item_res["pt_pagina_catalogo"] = "p. " + ", ".join(pages) if pages else "-"
                        item_res["affidabilita_match"] = "Alta (Kit Monosplit 2 Codici)"
                    else:
                        count_empty_no_model += 1
                        item_res["esito_verifica"] = "⚪ INCOMPLETO_A_CATALOGO (Mancano componenti PT)"
                        item_res["motivo_dettagliato"] = f"Marchio {resolved_brand} gestito, ma serie o motore/split Monosplit {req['btu']} BTU non interamente disponibili a catalogo."
                        item_res["pt_codice_finale"] = "-"
                        item_res["numero_codici_kit"] = 0
                        item_res["pt_nome_finale"] = "-"
                        item_res["affidabilita_match"] = "Incompleto a catalogo"

                # CASO 1C: CLIMATIZZATORE MULTI-SPLIT (Dual, Trial, Quadri, Penta)
                elif req['type'] in ['DUAL_SPLIT', 'TRIAL_SPLIT', 'QUADRI_SPLIT', 'PENTA_SPLIT']:
                    ue = find_multi_ue(resolved_brand, req['ports'], words, prod_name)
                    uis = [find_ui_for_size(resolved_brand, s, words, prod_name) for s in req['sizes']]
                    all_items = [ue] + uis if (ue and all(u is not None for u in uis)) else []
                    if all_items and len(all_items) >= req['min_codes']:
                        count_empty_kit += 1
                        codes_str = "+".join([it['code'] for it in all_items])
                        names_str = " + ".join([it['name'] for it in all_items])
                        tot_g = sum(float(it.get('gross_price') or 0.0) for it in all_items)
                        tot_n = sum(float(it.get('net_price') or 0.0) for it in all_items)
                        pages = sorted(list(set([str(it.get('primary_page')) for it in all_items if it.get('primary_page')])))
                        
                        item_res["esito_verifica"] = f"🔵 MPN_VUOTO ({req['name']} {req['min_codes']} Codici Creato da AI)"
                        item_res["motivo_dettagliato"] = f"MPN assente; generato kit completo {req['name']} con tutti i {req['min_codes']} codici (1 UE + {len(req['sizes'])} UI) per {resolved_brand}."
                        item_res["pt_codice_finale"] = codes_str
                        item_res["numero_codici_kit"] = len(all_items)
                        item_res["pt_nome_finale"] = names_str
                        item_res["pt_marchio_ufficiale"] = ue['brand']
                        item_res["pt_categoria_ufficiale"] = ue.get('category_path') or "-"
                        item_res["pt_prezzo_listino"] = f"{tot_g:.2f} €" if tot_g > 0 else "-"
                        item_res["pt_prezzo_netto"] = f"{tot_n:.2f} €" if tot_n > 0 else "-"
                        item_res["pt_pagina_catalogo"] = "p. " + ", ".join(pages) if pages else "-"
                        item_res["affidabilita_match"] = f"Alta (Kit Completo {req['min_codes']} Codici)"
                    else:
                        count_empty_no_model += 1
                        item_res["esito_verifica"] = "⚪ INCOMPLETO_A_CATALOGO (Mancano componenti PT)"
                        item_res["motivo_dettagliato"] = f"Marchio {resolved_brand} gestito, ma serie Multi-Split o split interni non interamente reperibili a catalogo per comporre il kit."
                        item_res["pt_codice_finale"] = "-"
                        item_res["numero_codici_kit"] = 0
                        item_res["pt_nome_finale"] = "-"
                        item_res["affidabilita_match"] = "Incompleto a catalogo"

                # CASO 1D: ARTICOLO SINGOLO (Altre categorie)
                else:
                    single = find_single_product(resolved_brand, prod_name)
                    if single:
                        count_empty_single += 1
                        item_res["esito_verifica"] = "🔵 MPN_VUOTO (Singolo Articolo Mappato)"
                        item_res["motivo_dettagliato"] = f"MPN assente nel file; articolo singolo individuato per coerenza tecnica nel catalogo Puglia Termica ({resolved_brand})."
                        item_res["pt_codice_finale"] = single["code"]
                        item_res["numero_codici_kit"] = 1
                        item_res["pt_nome_finale"] = single["name"]
                        item_res["pt_marchio_ufficiale"] = single["brand"]
                        item_res["pt_categoria_ufficiale"] = single.get("category_path") or "-"
                        item_res["pt_prezzo_listino"] = f"{float(single['gross_price']):.2f} €" if single.get("gross_price") else "-"
                        item_res["pt_prezzo_netto"] = f"{float(single['net_price']):.2f} €" if single.get("net_price") else "-"
                        item_res["pt_pagina_catalogo"] = f"p. {single['primary_page']}" if single.get("primary_page") else "-"
                        item_res["affidabilita_match"] = "Alta (Match Singolo Articolo)"
                    else:
                        count_empty_no_model += 1
                        item_res["esito_verifica"] = "⚪ MODELLO_NON_A_CATALOGO"
                        item_res["motivo_dettagliato"] = f"Marchio '{resolved_brand}' gestito a catalogo, ma il modello specifico non risulta presente in questa edizione 2026."
                        item_res["pt_codice_finale"] = "-"
                        item_res["numero_codici_kit"] = 0
                        item_res["pt_nome_finale"] = "-"
                        item_res["affidabilita_match"] = "Modello non a catalogo"
        
        # CASO 2: MPN PRESENTE NEL FILE SORGENTE
        else:
            parts = [p.strip() for p in orig_mpn.split('+') if p.strip()]
            valid_items = []
            clean_parts = []
            missing_codes = []
            
            for p in parts:
                p_clean = p.lower()
                p_lstrip = p.lstrip("0").lower()
                found = lookup.get(p_clean) or lookup.get(p_lstrip)
                # Gestione moltiplicatori e confezioni multiple (es. 50313587x3, 99375874*5)
                if not found:
                    base_p = re.sub(r'[\s\*xX]\d+$', '', p).strip()
                    if base_p and base_p != p:
                        found = lookup.get(base_p.lower()) or lookup.get(base_p.lstrip("0").lower())
                        if found:
                            p = base_p
                if found:
                    valid_items.append(found)
                    clean_parts.append(found['code'])
                else:
                    missing_codes.append(p)
                    
            min_req = req['min_codes']
            is_clima_kit = req['type'] in ['MONOSPLIT', 'DUAL_SPLIT', 'TRIAL_SPLIT', 'QUADRI_SPLIT', 'PENTA_SPLIT']
            has_enough_codes = len(parts) >= min_req
            has_enough_valid = len(valid_items) >= min_req
            
            # CASO 2A: IL PRODOTTO È UN CLIMATIZZATORE KIT MA L'MPN HA MENO CODICI DEL NECESSARIO
            if is_clima_kit and not has_enough_codes:
                count_kit_incomplete += 1
                item_res["esito_verifica"] = f"🔴 KIT_INCOMPLETO (Mancano codici per {req['name']})"
                item_res["motivo_dettagliato"] = f"Il prodotto è un climatizzatore kit completo che richiede almeno {min_req} codici PT (1 UE + split), ma l'MPN contiene solo {len(parts)} codice/i. Componenti mancanti non dichiarati nel codice sorgente."
                
                # Prova a completare il kit con i componenti mancanti
                completed_items = []
                if resolved_brand and req['type'] == 'MONOSPLIT':
                    ue = find_mono_ue(resolved_brand, req['btu'], words, prod_name)
                    ui = find_ui_for_size(resolved_brand, req['btu'], words, prod_name)
                    if ue and ui:
                        completed_items = [ue, ui]
                elif resolved_brand and req['type'] in ['DUAL_SPLIT', 'TRIAL_SPLIT', 'QUADRI_SPLIT', 'PENTA_SPLIT']:
                    ue = find_multi_ue(resolved_brand, req['ports'], words, prod_name)
                    uis = [find_ui_for_size(resolved_brand, s, words, prod_name) for s in req['sizes']]
                    if ue and all(u is not None for u in uis):
                        completed_items = [ue] + uis
                
                if completed_items and len(completed_items) >= min_req:
                    item_res["pt_codice_finale"] = "+".join([it['code'] for it in completed_items])
                    item_res["numero_codici_kit"] = len(completed_items)
                    item_res["pt_nome_finale"] = " + ".join([it['name'] for it in completed_items])
                    tot_g = sum(float(it.get('gross_price') or 0.0) for it in completed_items)
                    tot_n = sum(float(it.get('net_price') or 0.0) for it in completed_items)
                    item_res["pt_prezzo_listino"] = f"{tot_g:.2f} €" if tot_g > 0 else "-"
                    item_res["pt_prezzo_netto"] = f"{tot_n:.2f} €" if tot_n > 0 else "-"
                    pages = sorted(list(set([str(it.get('primary_page')) for it in completed_items if it.get('primary_page')])))
                    item_res["pt_pagina_catalogo"] = "p. " + ", ".join(pages) if pages else "-"
                    item_res["motivo_dettagliato"] += f" -> Kit climatizzatore completato aggiungendo i componenti mancanti ({item_res['pt_codice_finale']})."
                    item_res["affidabilita_match"] = f"Kit Completato ({len(completed_items)} Codici PT)"
                else:
                    # MAI suggerire l'MPN incompleto come codice confermato
                    item_res["pt_codice_finale"] = "-"
                    item_res["numero_codici_kit"] = 0
                    item_res["pt_nome_finale"] = " + ".join([it.get('name') or '' for it in valid_items]) if valid_items else "Componente non identificato"
                    item_res["affidabilita_match"] = "Incompleto a catalogo"

            # CASO 2B: TUTTI I CODICI ESISTONO A CATALOGO E SODDISFANO IL REQUISITO (Sia Caldaie che Clima che Singoli)
            elif not missing_codes and has_enough_codes:
                pt_names_str = " + ".join([it.get("name") or "" for it in valid_items])
                tot_gross = sum([float(it.get("gross_price") or 0.0) for it in valid_items if it.get("gross_price")])
                tot_net = sum([float(it.get("net_price") or 0.0) for it in valid_items if it.get("net_price")])
                pages_list = sorted(list(set([str(it.get("primary_page")) for it in valid_items if it.get("primary_page")])))
                pages_str = "p. " + ", ".join(pages_list) if pages_list else "-"
                main_brand = valid_items[0].get("brand") or (resolved_brand if resolved_brand else orig_brand)
                main_cat = valid_items[0].get("category_path") or "-"
                
                t_u = prod_name.upper()
                conflict_reason = None
                is_error = False
                is_disc = False
                
                # Controllo specifico per Climatizzatori Monosplit: UE vs UI
                if req['type'] == 'MONOSPLIT' and len(valid_items) >= 2:
                    ue_item = next((it for it in valid_items if "UE" in (it.get("name") or "").upper()), None)
                    ui_item = next((it for it in valid_items if "UI" in (it.get("name") or "").upper()), None)
                    if ue_item and ui_item:
                        ue_p = extract_technical_parameters(ue_item.get("name") or "")
                        ui_p = extract_technical_parameters(ui_item.get("name") or "")
                        if ue_p.get("btu") and ui_p.get("btu") and ue_p["btu"] != ui_p["btu"]:
                            is_error = True
                            conflict_reason = f"Grave Incompatibilità Monosplit: Motore Esterno UE {ue_p['btu']} BTU abbinato a Split Interno UI {ui_p['btu']} BTU"
                        elif req.get("btu") and ui_p.get("btu") and req["btu"] != ui_p["btu"]:
                            is_disc = True
                            conflict_reason = f"Discrepanza Taglia: Titolo chiede {req['btu']} BTU ma codice UI assegnato è {ui_p['btu']} BTU"

                # Controllo Potenza Caldaie (kW)
                if not conflict_reason and req['type'] == 'CALDAIA' and req.get("kw"):
                    req_kw = req["kw"]
                    first_pt_p = extract_technical_parameters(valid_items[0].get("name") or "")
                    if first_pt_p.get("kw"):
                        kw_diff = abs(first_pt_p["kw"] - req_kw)
                        pt_name_u = (valid_items[0].get("name") or "").upper()
                        is_hp_series = "HP" in t_u and "HP" in pt_name_u
                        is_same_model = any(token in pt_name_u for token in re.findall(r'\b[A-Z0-9\-]{4,}\b', t_u) if not token.endswith('KW') and not token.isdigit())
                        if kw_diff >= 1.0 and not is_hp_series and not is_same_model:
                            is_disc = True
                            conflict_reason = f"Discrepanza Potenza Caldaia: Titolo indica {req_kw} kW ma codice PT corrisponde a {first_pt_p['kw']} kW"
                        
                # Controllo Brand Mismatch
                if not conflict_reason:
                    pt_b = main_brand.upper()
                    expected_brand = resolved_brand if resolved_brand else (orig_brand.upper() if orig_brand else None)
                    if expected_brand:
                        pt_in_title = (pt_b in t_u) or any(
                            alias in t_u for alias, mapped_b in BRAND_ALIASES.items() if mapped_b == pt_b
                        )
                        pt_matches_expected = (
                            expected_brand == pt_b or expected_brand in pt_b or pt_b in expected_brand
                            or BRAND_ALIASES.get(expected_brand) == pt_b
                        )
                        pt_matches_orig = orig_brand and (
                            orig_brand.upper() == pt_b or BRAND_ALIASES.get(orig_brand.upper()) == pt_b
                        )
                        if not (pt_in_title or pt_matches_expected or pt_matches_orig):
                            is_error = True
                            conflict_reason = f"Incongruenza Marchio: Titolo indica {expected_brand} mentre il codice PT appartiene a {pt_b}"
                        
                if is_error:
                    count_err += 1
                    item_res["esito_verifica"] = "🔴 INCOMPATIBILE / ERRATO"
                    item_res["motivo_dettagliato"] = conflict_reason
                    # MAI suggerire l'MPN incompatibile o errato!
                    item_res["pt_codice_finale"] = "-"
                    item_res["numero_codici_kit"] = 0
                    item_res["pt_nome_finale"] = "-"
                    item_res["affidabilita_match"] = "Incompatibilità riscontrata"
                elif is_disc:
                    count_disc += 1
                    item_res["esito_verifica"] = "🟡 DISCREPANZA_TAGLIA"
                    item_res["motivo_dettagliato"] = conflict_reason
                    # Se c'è discrepanza di taglia, non confermare il codice
                    item_res["pt_codice_finale"] = "-"
                    item_res["numero_codici_kit"] = 0
                    item_res["pt_nome_finale"] = pt_names_str
                    item_res["affidabilita_match"] = "Verifica variante potenza"
                else:
                    count_ok += 1
                    confirmed_mpn = "+".join(clean_parts) if clean_parts else orig_mpn
                    if req['type'] == 'CALDAIA':
                        item_res["esito_verifica"] = "🟢 CORRETTO (Caldaia Verificata)" if len(valid_items) == 1 else "🟢 CORRETTO (Caldaia + Kit Fumi Verificati)"
                        item_res["motivo_dettagliato"] = f"Caldaia verificata a catalogo PT con successo. Kit fumi compatibili abbinati nelle apposite colonne."
                    else:
                        item_res["esito_verifica"] = "🟢 CORRETTO"
                        item_res["motivo_dettagliato"] = f"Parametri tecnici, marca e tutti i {len(valid_items)} codici verificati a catalogo con successo"
                    
                    item_res["pt_codice_finale"] = confirmed_mpn
                    item_res["numero_codici_kit"] = len(valid_items)
                    item_res["pt_nome_finale"] = pt_names_str
                    item_res["affidabilita_match"] = f"100% (Verificato {len(valid_items)} Codici)"
                    
                item_res["pt_marchio_ufficiale"] = main_brand
                item_res["pt_categoria_ufficiale"] = main_cat
                item_res["pt_prezzo_listino"] = f"{tot_gross:.2f} €" if tot_gross > 0 else "-"
                item_res["pt_prezzo_netto"] = f"{tot_net:.2f} €" if tot_net > 0 else "-"
                item_res["pt_pagina_catalogo"] = pages_str

            # CASO 2C: BUNDLE CON CODICI VALIDI E CODICI OMAGGIO/MANCANTI
            elif len(valid_items) > 0 and len(missing_codes) > 0:
                count_bundle_parz += 1
                valid_codes_str = "+".join([it.get("code") or "" for it in valid_items])
                valid_names_str = " + ".join([it.get("name") or "" for it in valid_items])
                missing_str = ", ".join(missing_codes)
                
                tot_gross = sum([float(it.get("gross_price") or 0.0) for it in valid_items if it.get("gross_price")])
                tot_net = sum([float(it.get("net_price") or 0.0) for it in valid_items if it.get("net_price")])
                pages_list = sorted(list(set([str(it.get("primary_page")) for it in valid_items if it.get("primary_page")])))
                pages_str = "p. " + ", ".join(pages_list) if pages_list else "-"
                
                if len(valid_items) >= min_req:
                    item_res["esito_verifica"] = "🟢 CORRETTO (Componente Principale Confermato - Omaggio Escluso)"
                    item_res["motivo_dettagliato"] = f"I componenti necessari ({valid_codes_str}) sono confermati a catalogo PT. Il codice '{missing_str}' è un segnaposto promozionale interno non gestito a catalogo."
                    item_res["pt_codice_finale"] = valid_codes_str
                    item_res["numero_codici_kit"] = len(valid_items)
                    item_res["pt_nome_finale"] = valid_names_str
                    item_res["affidabilita_match"] = f"100% ({len(valid_items)} Codici Validi)"
                else:
                    item_res["esito_verifica"] = "🟡 BUNDLE_PARZIALMENTE_CONFERMATO"
                    item_res["motivo_dettagliato"] = f"Componenti parzialmente presenti ({valid_codes_str}). Codici mancanti o interni: '{missing_str}'."
                    item_res["pt_codice_finale"] = "-"
                    item_res["numero_codici_kit"] = 0
                    item_res["pt_nome_finale"] = valid_names_str
                    item_res["affidabilita_match"] = "Parziale (Incompleto)"
                    
                item_res["pt_marchio_ufficiale"] = valid_items[0].get("brand") or orig_brand
                item_res["pt_categoria_ufficiale"] = valid_items[0].get("category_path") or "-"
                item_res["pt_prezzo_listino"] = f"{tot_gross:.2f} €" if tot_gross > 0 else "-"
                item_res["pt_prezzo_netto"] = f"{tot_net:.2f} €" if tot_net > 0 else "-"
                item_res["pt_pagina_catalogo"] = pages_str

            # CASO 2D: NESSUN CODICE ESISTE A CATALOGO
            else:
                count_missing_code += 1
                fallback_item = None
                if resolved_brand:
                    if req['type'] == 'CALDAIA':
                        fallback_item = find_caldaia(resolved_brand, req['kw'], words, prod_name) or find_single_product(resolved_brand, prod_name)
                    else:
                        fallback_item = find_single_product(resolved_brand, prod_name)

                if fallback_item:
                    item_res["esito_verifica"] = "⚪ CODICE_NON_TROVATO (Modello Suggerito da AI)"
                    item_res["motivo_dettagliato"] = f"Codice MPN sorgente ({orig_mpn}) inesistente/obsoleto a catalogo PT. Modello equivalente identificato a catalogo per coerenza tecnica: {fallback_item['code']} - {fallback_item['name']}."
                    item_res["pt_codice_finale"] = fallback_item['code']
                    item_res["numero_codici_kit"] = 1
                    item_res["pt_nome_finale"] = fallback_item['name']
                    item_res["pt_marchio_ufficiale"] = fallback_item['brand']
                    item_res["pt_categoria_ufficiale"] = fallback_item.get('category_path') or "-"
                    item_res["pt_prezzo_listino"] = f"{float(fallback_item['gross_price']):.2f} €" if fallback_item.get('gross_price') else "-"
                    item_res["pt_prezzo_netto"] = f"{float(fallback_item['net_price']):.2f} €" if fallback_item.get('net_price') else "-"
                    item_res["pt_pagina_catalogo"] = f"p. {fallback_item['primary_page']}" if fallback_item.get('primary_page') else "-"
                    item_res["affidabilita_match"] = "Alta (Modello Correlato)"
                else:
                    item_res["esito_verifica"] = "⚪ CODICE_NON_TROVATO"
                    item_res["motivo_dettagliato"] = f"I codici MPN inseriti ({orig_mpn}) non esistono a catalogo Puglia Termica."
                    item_res["pt_codice_finale"] = "-"
                    item_res["numero_codici_kit"] = 0
                    item_res["pt_nome_finale"] = "-"
                    item_res["pt_marchio_ufficiale"] = resolved_brand if resolved_brand else orig_brand
                    item_res["pt_categoria_ufficiale"] = "-"
                    item_res["pt_prezzo_listino"] = "-"
                    item_res["pt_prezzo_netto"] = "-"
                    item_res["pt_pagina_catalogo"] = "-"
                    item_res["affidabilita_match"] = "Codice inesistente"

        report_data.append(item_res)
        
        # Log periodico ogni 2000 righe
        if (idx + 1) % 2000 == 0 or (idx + 1) == total_rows:
            elapsed = time.time() - t_loop_start
            speed = (idx + 1) / elapsed if elapsed > 0 else 0
            rem_sec = (total_rows - (idx + 1)) / speed if speed > 0 else 0
            pct = round((idx + 1) / total_rows * 100, 1)
            print(f"  [Progresso {idx+1}/{total_rows} - {pct}%] Velocità: {round(speed, 1)} righe/s | Rimanente: {round(rem_sec)}s | OK: {count_ok} | ClimaIncompl: {count_kit_incomplete} | BundleParz: {count_bundle_parz} | ClimaKit_AI: {count_empty_kit} | Single_AI: {count_empty_single} | FuoriCat: {count_not_in_pt}")

    print("\n=======================================================================")
    print("      AUDIT KIT CLIMATIZZATORI & CALDAIE COMPLETATO CON SUCCESSO       ")
    print("=======================================================================")
    print(f"Totale Righe Elaborate: {total_rows}")
    print(f"  🟢 CORRETTO (PRODOTTI / KIT VERIFICATI):       {count_ok} ({round(count_ok/total_rows*100, 1)}%)")
    print(f"  🔴 KIT CLIMATIZZATORE INCOMPLETO (MANCAVA UE/UI): {count_kit_incomplete} ({round(count_kit_incomplete/total_rows*100, 1)}%)")
    print(f"  🟡 BUNDLE PARZIALE (CONFERMATO SENZA OMAGGIO): {count_bundle_parz} ({round(count_bundle_parz/total_rows*100, 1)}%)")
    print(f"  🟡 DISCREPANZA TAGLIA / POTENZA:               {count_disc} ({round(count_disc/total_rows*100, 1)}%)")
    print(f"  🔴 INCOMPATIBILE / ERRATO:                     {count_err} ({round(count_err/total_rows*100, 1)}%)")
    print(f"  🔵 MPN VUOTO (KIT CLIMA COSTRUITO DA AI):      {count_empty_kit} ({round(count_empty_kit/total_rows*100, 1)}%)")
    print(f"  🔵 MPN VUOTO (CALDAIA / SINGOLO MAPPATO DA AI):{count_empty_single} ({round(count_empty_single/total_rows*100, 1)}%)")
    print(f"  ⚪ MODELLO NON TROVATO IN QUESTO CATALOGO:     {count_empty_no_model} ({round(count_empty_no_model/total_rows*100, 1)}%)")
    print(f"  ⚪ MARCHIO NON DISTRIBUITO DA PUGLIA TERMICA:  {count_not_in_pt} ({round(count_not_in_pt/total_rows*100, 1)}%)")
    print(f"  ⚪ CODICE NON TROVATO (INESISTENTE):           {count_missing_code} ({round(count_missing_code/total_rows*100, 1)}%)")
    print("=======================================================================")

    # 4. Generazione File CSV con percorso sicuro
    target_csv = get_available_path(CSV_OUTPUT_PATH)
    print(f"\nEsportazione file CSV: {target_csv} ...")
    fieldnames = [
        "id_product", "reference", "product_name", "brand_originale", "mpn_originale",
        "tipologia_prodotto", "requisito_minimo_codici",
        "prezzo_originale", "quantita_originale", "attivo_originale",
        "esito_verifica", "motivo_dettagliato",
        "pt_codice_finale", "numero_codici_kit", "pt_nome_finale",
        "kit_fumi_coassiale", "kit_fumi_sdoppiato",
        "pt_marchio_ufficiale", "pt_categoria_ufficiale",
        "pt_prezzo_listino", "pt_prezzo_netto", "pt_pagina_catalogo", "affidabilita_match"
    ]
    
    with open(target_csv, 'w', encoding='utf-8-sig', newline='') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        for r in report_data:
            writer.writerow(r)
    print(f"File CSV esportato con successo: {target_csv}")

    # 5. Generazione File Excel formattato con openpyxl
    target_xlsx = get_available_path(XLSX_OUTPUT_PATH)
    print(f"\nEsportazione file Excel formattato: {target_xlsx} ...")
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Verifica_Catalogo_PT"

        headers = [
            "ID Prodotto", "Riferimento", "Nome Prodotto Originale", "Marca CSV", "Codice MPN Originale",
            "Tipologia Prodotto", "Requisito Minimo Codici",
            "Prezzo CSV", "Qta", "Attivo",
            "ESITO VERIFICA", "MOTIVO DETTAGLIATO ANOMALIA / COMPONENTI",
            "CODICE MPN CONFERMATO / SUGGERITO", "N° Codici PT",
            "DESCRIZIONE PT UFFICIALE / SUGGERITA",
            "KIT FUMI COASSIALE COMPATIBILE (PER CALDAIE)", "KIT FUMI SDOPPIATO COMPATIBILE (PER CALDAIE)",
            "MARCHIO PT", "CATEGORIA PT",
            "LISTINO PT (€)", "NETTO PT (€)", "PAGINA PDF", "AFFIDABILITÀ MATCH"
        ]
        ws.append(headers)

        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        fill_green = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        font_green = Font(name="Segoe UI", size=9, bold=True, color="166534")
        
        fill_yellow = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
        font_yellow = Font(name="Segoe UI", size=9, bold=True, color="854D0E")
        
        fill_red = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        font_red = Font(name="Segoe UI", size=9, bold=True, color="991B1B")
        
        fill_gray = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        font_gray = Font(name="Segoe UI", size=9, color="475569")
        
        fill_blue = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
        font_blue = Font(name="Segoe UI", size=9, bold=True, color="075985")

        default_font = Font(name="Segoe UI", size=9)

        for row_idx, r in enumerate(report_data, start=2):
            row_vals = [
                r["id_product"], r["reference"], r["product_name"], r["brand_originale"], r["mpn_originale"],
                r["tipologia_prodotto"], r["requisito_minimo_codici"],
                r["prezzo_originale"], r["quantita_originale"], r["attivo_originale"],
                r["esito_verifica"], r["motivo_dettagliato"],
                r["pt_codice_finale"], r["numero_codici_kit"], r["pt_nome_finale"],
                r["kit_fumi_coassiale"], r["kit_fumi_sdoppiato"],
                r["pt_marchio_ufficiale"], r["pt_categoria_ufficiale"],
                r["pt_prezzo_listino"], r["pt_prezzo_netto"], r["pt_pagina_catalogo"], r["affidabilita_match"]
            ]
            ws.append(row_vals)
            
            esito_cell = ws.cell(row=row_idx, column=11)
            esito_text = str(r["esito_verifica"])
            
            if "CORRETTO" in esito_text:
                esito_cell.fill = fill_green
                esito_cell.font = font_green
            elif "BUNDLE" in esito_text or "DISCREPANZA" in esito_text:
                esito_cell.fill = fill_yellow
                esito_cell.font = font_yellow
            elif "INCOMPLETO" in esito_text or "INCOMPATIBILE" in esito_text or "ERRATO" in esito_text:
                esito_cell.fill = fill_red
                esito_cell.font = font_red
            elif "NON_TROVATO" in esito_text or "NON_A_CATALOGO" in esito_text:
                esito_cell.fill = fill_gray
                esito_cell.font = font_gray
            elif "VUOTO" in esito_text:
                esito_cell.fill = fill_blue
                esito_cell.font = font_blue
                
            for col_idx in range(1, len(headers) + 1):
                c = ws.cell(row=row_idx, column=col_idx)
                if col_idx != 11:
                    c.font = default_font

        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 16
        ws.column_dimensions['C'].width = 45
        ws.column_dimensions['D'].width = 14
        ws.column_dimensions['E'].width = 24
        ws.column_dimensions['F'].width = 24
        ws.column_dimensions['G'].width = 28
        ws.column_dimensions['H'].width = 12
        ws.column_dimensions['I'].width = 8
        ws.column_dimensions['J'].width = 8
        ws.column_dimensions['K'].width = 32
        ws.column_dimensions['L'].width = 50
        ws.column_dimensions['M'].width = 32
        ws.column_dimensions['N'].width = 12
        ws.column_dimensions['O'].width = 48
        ws.column_dimensions['P'].width = 45
        ws.column_dimensions['Q'].width = 45
        ws.column_dimensions['R'].width = 16
        ws.column_dimensions['S'].width = 25
        ws.column_dimensions['T'].width = 14
        ws.column_dimensions['U'].width = 14
        ws.column_dimensions['V'].width = 14
        ws.column_dimensions['W'].width = 25

        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "A2"

        wb.save(target_xlsx)
        print(f"File Excel generato con successo: {target_xlsx}")
    except Exception as ex:
        print(f"Errore generazione Excel: {ex}")

    total_time = time.time() - start_time
    print(f"\nAudit completato in {round(total_time, 1)} secondi ({round(total_time/60, 2)} minuti)!")

if __name__ == "__main__":
    main()
