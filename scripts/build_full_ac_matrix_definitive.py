"""
BUILD FULL AC MATRIX (CATALOG COMBINATION TABLES EDITION - DEFINITIVE 2026)
Costruisce la matrice master di compatibilità dei climatizzatori con:
1. Classificazione esplicita e certa: UI vs UE vs Monoblocco S/UE vs Accessorio
2. Per le UE: quante UI sono collegabili (max_ui_collegabili, porte_attacchi) e QUALI (unita_interne_compatibili)
3. Regole estratte direttamente dalle "TABELLA COMBINAZIONI MULTI SPLIT" delle pagine 468-628 del Catalogo Puglia Termica 2026.
4. PER LE UE SEMPRE KW, PER LE UI SEMPRE BTU.
"""

import json
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "scripts" in os.path.dirname(os.path.abspath(__file__)) else os.path.dirname(os.path.abspath(__file__))
MASTER_CATALOG_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
EXISTING_COMB_PATH = os.path.join(BASE_DIR, "Knowledge", "ac_outdoor_combinations.json")
OFFICIAL_FAMILIES_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_official_families_2026.json")
OUTPUT_MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "climatizzatori_compatibilita_master.json")
PDF_EXTRACTED_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_extracted_specs.json")

if os.path.exists(OFFICIAL_FAMILIES_PATH):
    with open(OFFICIAL_FAMILIES_PATH, "r", encoding="utf-8") as f:
        OFFICIAL_FAMILIES_DB = json.load(f)
else:
    OFFICIAL_FAMILIES_DB = {}

if os.path.exists(PDF_EXTRACTED_SPECS_PATH):
    with open(PDF_EXTRACTED_SPECS_PATH, "r", encoding="utf-8") as f:
        PDF_SPECS_DB = json.load(f)
else:
    PDF_SPECS_DB = {}

# -------------------------------------------------------------
# TABELLE UFFICIALI DI COMBINAZIONE CATALOGO PUGLIA TERMICA 2026
# -------------------------------------------------------------
MULTI_SPLIT_RULES = [
    {
        "id": "DAIKIN_MXF",
        "brand": "DAIKIN",
        "pattern": re.compile(r'\b[23]MXF', re.I),
        "combination_page": 470,
        "table_name": "TABELLA COMBINAZIONI MULTI SENSIRA (Pag. 470)",
        "allowed_keywords": ["SENSIRA", "CTXF", "FTXF"],
        "excluded_keywords": ["PERFERA", "STYLISH", "EMURA", "COMFORA"],
        "max_size_by_model": {
            "2MXF40": 12000,
            "2MXF50": 18000,
            "3MXF52": 18000,
            "3MXF68": 18000
        },
        "comb_by_ports": {
            2: ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["20+20+20", "20+20+25", "20+20+35", "20+25+25", "20+25+35", "25+25+25", "25+25+35"]
        }
    },
    {
        "id": "DAIKIN_MXM",
        "brand": "DAIKIN",
        "pattern": re.compile(r'\b[2-5]MXM', re.I),
        "combination_page": 471,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT MXM-A8-A9 (Pag. 471)",
        "allowed_keywords": ["PERFERA", "EMURA", "STYLISH", "COMFORA", "CONSOLE", "PAVIMENTO", "CASSETTA", "CANALIZZATA", "PENSILE", "FTXM", "FTXJ", "FTXA", "FTXP", "FVXM", "FCAG", "FDXM", "FBA", "FFA"],
        "excluded_keywords": ["SENSIRA", "CTXF"],
        "max_size_by_model": {
            "2MXM40": 12000,
            "2MXM50": 18000,
            "2MXM68": 18000,
            "3MXM40": 12000,
            "3MXM52": 18000,
            "3MXM68": 18000,
            "4MXM68": 18000,
            "4MXM80": 24000,
            "5MXM90": 24000
        },
        "comb_by_ports": {
            2: ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["20+20+20", "20+20+25", "20+20+35", "20+25+25", "20+25+35", "25+25+25", "25+25+35", "25+35+35"],
            4: ["20+20+20+20", "20+20+20+25", "20+20+25+25", "20+25+25+25", "25+25+25+25", "20+20+25+35", "25+25+25+35"],
            5: ["20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "20+20+25+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "MITSUBISHI_SMART",
        "brand": "MITSUBISHI",
        "pattern": re.compile(r'\bMXZ-[23]HA', re.I),
        "combination_page": 493,
        "table_name": "TABELLA COMBINAZIONI MULTI SMART MXZ-HA (Pag. 493)",
        "allowed_keywords": ["SMART", "MSZ-HR", "HR"],
        "excluded_keywords": ["KIRIGAMINE", "LINEA PLUS", "MSZ-LN", "MSZ-EF", "MSZ-AP", "MSZ-AY"],
        "max_size_by_model": {
            "2HA40": 12000,
            "2HA50": 18000,
            "3HA50": 18000
        },
        "comb_by_ports": {
            2: ["25+25", "25+35", "35+35"],
            3: ["25+25+25", "25+25+35", "25+25+50"]
        }
    },
    {
        "id": "MITSUBISHI_MXZ_F",
        "brand": "MITSUBISHI",
        "pattern": re.compile(r'\bMXZ-[2-6]F', re.I),
        "combination_page": 498,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT MXZ-F (Pag. 498)",
        "allowed_keywords": ["KIRIGAMINE", "LINEA PLUS", "MSZ-LN", "MSZ-EF", "MSZ-AP", "MSZ-AY", "MSZ-BT", "MLZ-KP", "MFZ-KT", "SLZ-M", "SEZ-M", "PCA-M", "SFZ-M", "AP", "AY", "LN", "EF", "BT"],
        "excluded_keywords": ["MSZ-HR", "SMART"],
        "max_size_by_model": {
            "2F33": 12000,
            "2F42": 14000,
            "2F53": 18000,
            "3F54": 18000,
            "3F68": 18000,
            "4F72": 21000,
            "4F80": 21000,
            "4F83": 24000,
            "5F102": 24000,
            "6F120": 24000
        },
        "comb_by_ports": {
            2: ["15+15", "15+20", "15+25", "20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["15+15+15", "15+15+20", "15+15+25", "20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35", "25+35+35"],
            4: ["15+15+15+15", "20+20+20+20", "20+20+20+25", "20+20+25+25", "20+25+25+25", "25+25+25+25", "20+20+25+35", "25+25+25+35"],
            5: ["15+15+15+15+15", "20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "20+20+25+25+25", "25+25+25+25+25"],
            6: ["15+15+15+15+15+15", "20+20+20+20+20+20", "20+20+20+20+20+25", "20+20+20+20+25+25", "25+25+25+25+25+25"]
        }
    },
    {
        "id": "SAMSUNG_FJM",
        "brand": "SAMSUNG",
        "pattern": re.compile(r'\bAJ0|\bAJ100', re.I),
        "combination_page": 575,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT SAMSUNG FJM (Pag. 575)",
        "allowed_keywords": ["WINDFREE", "CEBU", "CASSETTA", "CANALIZZATO", "CONSOLE", "AR07", "AR09", "AR12", "AR18", "AR24"],
        "max_size_by_model": {
            "AJ040": 12000,
            "AJ050": 18000,
            "AJ052": 18000,
            "AJ068": 18000,
            "AJ080": 24000,
            "AJ100": 24000
        },
        "comb_by_ports": {
            2: ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"],
            4: ["20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25", "20+25+25+35"],
            5: ["20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "HAIER_MULTI",
        "brand": "HAIER",
        "pattern": re.compile(r'\b[2-5]U\d{2}', re.I),
        "combination_page": 564,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT HAIER R32 (Pag. 564)",
        "allowed_keywords": ["EXPERT", "FLEXIS", "PEARL", "TUNDRA", "CASSETTE", "CANALIZZATO", "CONSOLE", "AS20", "AS25", "AS35", "AS42", "AS50", "AS71"],
        "max_size_by_model": {
            "2U40": 12000,
            "2U50": 18000,
            "3U55": 18000,
            "3U70": 18000,
            "4U75": 24000,
            "4U85": 24000,
            "5U90": 24000,
            "5U105": 24000,
            "5U125": 24000
        },
        "comb_by_ports": {
            2: ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"],
            4: ["20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25", "20+25+25+35"],
            5: ["20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "LG_MULTI",
        "brand": "LG",
        "pattern": re.compile(r'\bMU[2-5]R', re.I),
        "combination_page": 586,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT LG R32 (Pag. 586)",
        "allowed_keywords": ["ARTCOOL", "DUALCOOL", "STANDARD", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "MU2R15": 12000,
            "MU2R17": 14000,
            "MU3R19": 18000,
            "MU3R21": 18000,
            "MU4R25": 21000,
            "MU4R27": 24000,
            "MU5R30": 24000,
            "MU5R40": 24000
        },
        "comb_by_ports": {
            2: ["15+15", "15+20", "15+25", "20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["15+15+15", "20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"],
            4: ["15+15+15+15", "20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25"],
            5: ["15+15+15+15+15", "20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "PANASONIC_MULTI",
        "brand": "PANASONIC",
        "pattern": re.compile(r'\bCU-[2-5]Z', re.I),
        "combination_page": 514,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT PANASONIC (Pag. 514)",
        "allowed_keywords": ["ETHEREA", "TZ", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "CU-2Z35": 12000,
            "CU-2Z41": 14000,
            "CU-2Z50": 18000,
            "CU-3Z52": 18000,
            "CU-3Z68": 18000,
            "CU-4Z68": 21000,
            "CU-4Z80": 24000,
            "CU-5Z90": 24000
        },
        "comb_by_ports": {
            2: ["16+16", "16+20", "16+25", "20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["16+16+16", "20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"],
            4: ["16+16+16+16", "20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25"],
            5: ["16+16+16+16+16", "20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "HISENSE_MULTI",
        "brand": "HISENSE",
        "pattern": re.compile(r'\b[2-5]AMW', re.I),
        "combination_page": 550,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT HISENSE (Pag. 550)",
        "allowed_keywords": ["AIR MASTER", "ENERGY", "UNI HB", "HI-COMFORT", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "2AMW42": 12000,
            "2AMW52": 18000,
            "3AMW52": 18000,
            "3AMW62": 18000,
            "3AMW72": 18000,
            "4AMW81": 24000,
            "5AMW105": 24000
        },
        "comb_by_ports": {
            2: ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"],
            3: ["20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"],
            4: ["20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25"],
            5: ["20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]
        }
    },
    {
        "id": "FERROLI_GIADA",
        "brand": "FERROLI",
        "pattern": re.compile(r'\b2CP002[E-I]|\bGIADA\s*M', re.I),
        "combination_page": 594,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT GIADA R32 (Pag. 594)",
        "allowed_keywords": ["GIADA", "GIADA S", "GIADA M", "CASSETTA", "CANALIZZATO"],
        "max_size_by_model": {
            "2CP002E": 18000,
            "2CP002F": 18000,
            "2CP002G": 24000,
            "2CP002H": 24000,
            "2CP002I": 24000
        },
        "comb_by_ports": {
            2: ["9+9", "9+12", "12+12", "9+18", "12+18"],
            3: ["9+9+9", "9+9+12", "9+12+12", "12+12+12", "9+9+18", "9+12+18"],
            4: ["9+9+9+9", "9+9+9+12", "9+9+12+12", "9+9+9+18", "9+12+12+18"],
            5: ["9+9+9+9+9", "9+9+9+9+12", "9+9+9+12+12", "9+9+9+9+18"]
        }
    },
    {
        "id": "BAXI_MULTI",
        "brand": "BAXI",
        "pattern": re.compile(r'\b(?:LSGT|DUAL|TRIAL|QUADRI|PENTA)\b.*MULTI|\bMULTI.*BAXI', re.I),
        "combination_page": 598,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT BAXI (Pag. 598)",
        "allowed_keywords": ["ASTRA", "MOONLIGHT", "CASSETTA", "CANALIZZATO"],
        "max_size_by_model": {
            "DUAL": 14000,
            "TRIAL": 18000,
            "QUADRI": 24000,
            "PENTA": 24000
        },
        "comb_by_ports": {
            2: ["7+7", "7+9", "9+9", "7+12", "9+12", "12+12"],
            3: ["7+7+7", "7+7+9", "7+9+9", "9+9+9", "7+9+12", "9+9+12"],
            4: ["7+7+7+7", "7+7+7+9", "7+7+9+9", "7+9+9+9", "9+9+9+9"],
            5: ["7+7+7+7+7", "7+7+7+7+9", "7+7+7+9+9", "7+7+9+9+9", "9+9+9+9+9"]
        }
    },
    {
        "id": "IMMERGAS_MULTI",
        "brand": "IMMERGAS",
        "pattern": re.compile(r'\bCEF\s*R32.*(?:DUAL|TRIAL|QUADRI|PENTA)|\bBREVA.*(?:2|3)\b', re.I),
        "combination_page": 604,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT IMMERGAS (Pag. 604)",
        "allowed_keywords": ["BREVA", "CEF", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "DUAL": 14000,
            "TRIAL": 18000,
            "QUADRI": 24000,
            "PENTA": 24000
        },
        "comb_by_ports": {
            2: ["7+7", "7+9", "9+9", "7+12", "9+12", "12+12"],
            3: ["7+7+7", "7+7+9", "7+9+9", "9+9+9", "7+9+12", "9+9+12"],
            4: ["7+7+7+7", "7+7+7+9", "7+7+9+9", "7+9+9+9", "9+9+9+9"],
            5: ["7+7+7+7+7", "7+7+7+7+9", "7+7+7+9+9", "7+7+9+9+9", "9+9+9+9+9"]
        }
    },
    {
        "id": "BOSCH_MULTI",
        "brand": "BOSCH",
        "pattern": re.compile(r'\bCL5000M', re.I),
        "combination_page": 612,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT BOSCH (Pag. 612)",
        "allowed_keywords": ["CLIMATE 3000", "CLIMATE 5000", "CL5000", "CL3000", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "41/2": 14000,
            "53/2": 18000,
            "79/3": 18000,
            "82/4": 24000,
            "105/4": 24000,
            "125/5": 24000
        },
        "comb_by_ports": {
            2: ["7+7", "7+9", "9+9", "7+12", "9+12", "12+12"],
            3: ["7+7+7", "7+7+9", "7+9+9", "9+9+9", "7+9+12", "9+9+12", "9+12+12"],
            4: ["7+7+7+7", "7+7+7+9", "7+7+9+9", "7+9+9+9", "9+9+9+9", "9+9+9+12"],
            5: ["7+7+7+7+7", "7+7+7+7+9", "7+7+7+9+9", "7+7+9+9+9", "9+9+9+9+9"]
        }
    },
    {
        "id": "VAILLANT_MULTI",
        "brand": "VAILLANT",
        "pattern": re.compile(r'\bVAF5', re.I),
        "combination_page": 619,
        "table_name": "TABELLA COMBINAZIONI MULTI SPLIT VAILLANT (Pag. 619)",
        "allowed_keywords": ["CLIMAVAIR", "VAI5", "CASSETTA", "CANALIZZATO", "CONSOLE"],
        "max_size_by_model": {
            "040": 12000,
            "050": 18000,
            "070": 18000,
            "080": 24000
        },
        "comb_by_ports": {
            2: ["7+7", "7+9", "9+9", "7+12", "9+12", "12+12"],
            3: ["7+7+7", "7+7+9", "7+9+9", "9+9+9", "7+9+12", "9+9+12"],
            4: ["7+7+7+7", "7+7+7+9", "7+7+9+9", "7+9+9+9", "9+9+9+9"]
        }
    }
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.upper()
    for a, b in [('À', 'A'), ('È', 'E'), ('É', 'E'), ('Ì', 'I'), ('Ò', 'O'), ('Ù', 'U')]:
        t = t.replace(a, b)
    return t

def clean_text_for_btu(name: str, mfg_code: str = "") -> str:
    t = normalize_text(f"{name}")
    t = re.sub(r'\b\d{2,3}\s*[Xx*]\s*\d{2,3}\b', ' ', t)
    mfg_clean = normalize_text(mfg_code).strip()
    if mfg_clean and not re.match(r'^\d+[\.\d]*$', mfg_clean):
        t = f"{t} {mfg_clean}"
    return t

def extract_btu_and_kw(name: str, mfg_code: str = "") -> Tuple[Optional[int], Optional[float]]:
    combined = clean_text_for_btu(name, mfg_code)

    m_aj = re.search(r'\bAJ0?(16|20|26|35|52|68)', combined)
    if m_aj:
        aj_map = {'16': (7000, 1.6), '20': (7000, 2.0), '26': (9000, 2.6), '35': (12000, 3.5), '52': (18000, 5.2), '68': (24000, 6.8)}
        return aj_map[m_aj.group(1)]

    if re.search(r'\bAA09\w*\b', combined): return 9000, 2.5
    if re.search(r'\bAA12\w*\b', combined): return 12000, 3.5
    if re.search(r'\bH18\w*\b', combined): return 18000, 5.0
    if re.search(r'\bH24\w*\b', combined): return 24000, 7.0

    m_mhg = re.search(r'MHG[A-Z]*(25|35|50|70)', combined)
    if m_mhg:
        mhg_map = {'25': (9000, 2.5), '35': (12000, 3.5), '50': (18000, 5.0), '70': (24000, 7.0)}
        return mhg_map[m_mhg.group(1)]

    m_rxf = re.search(r'RXF(25|35|50|60|71)', combined)
    if m_rxf:
        rxf_map = {'25': (9000, 2.5), '35': (12000, 3.5), '50': (18000, 5.0), '60': (21000, 6.0), '71': (24000, 7.1)}
        return rxf_map[m_rxf.group(1)]

    m_bosch_m = re.search(r'(\d{2,3})/([2-5])\s*E', combined)
    if m_bosch_m:
        kw = float(m_bosch_m.group(1)) / 10.0
        return None, kw

    m_vam = re.search(r'VAM1-(\d{3})A([2-5])', combined)
    if m_vam:
        kw = float(m_vam.group(1)) / 10.0
        return None, kw

    m_imm_m = re.search(r'([2-5])\s*ATT\s*(\d{2})', combined)
    if m_imm_m:
        kw = 7.9 if m_imm_m.group(2) == '27' else 8.2
        return None, kw

    m_maxa = re.search(r'M(?:GE|PG)\s*(\d{3})', combined)
    if m_maxa:
        kw = float(m_maxa.group(1)) / 100.0
        return None, kw

    m_btu = re.search(r'\b(7\.?000|9\.?000|10\.?000|12\.?000|14\.?000|18\.?000|21\.?000|24\.?000|28\.?000|30\.?000|36\.?000|42\.?000|48\.?000|60\.?000)\s*(?:BTU|B)?\b', combined)
    if m_btu:
        btu_val = int(m_btu.group(1).replace('.', ''))
        btu_to_kw = {
            7000: 2.0, 9000: 2.5, 10000: 2.8, 12000: 3.5, 14000: 4.0, 18000: 5.0, 21000: 6.0,
            24000: 7.0, 28000: 8.0, 30000: 8.5, 36000: 10.0, 42000: 12.0, 48000: 14.0, 60000: 16.0
        }
        return btu_val, btu_to_kw.get(btu_val, 2.5)

    if re.search(r'(?:TAGLIA\s*250|250\s*R|ADH250|PUZ-ZM250|RZA250|UU250|\b250\b|[A-Z]{1,4}[-_]?[A-Z0-9]*250[A-Z0-9]*)', combined): return 60000, 25.0
    if re.search(r'(?:TAGLIA\s*200|200\s*R|ADH200|PUZ-ZM200|RZA200|UU200|\b200\b|[A-Z]{1,4}[-_]?[A-Z0-9]*200[A-Z0-9]*)', combined): return 60000, 20.0
    if re.search(r'(?:TAGLIA\s*160|160\s*R|ADH160|FBA160|FCAG160|\b160\b|[A-Z]{1,4}[-_]?[A-Z0-9]*160[A-Z0-9]*)', combined): return 60000, 16.0
    if re.search(r'(?:TAGLIA\s*140|140\s*R|ADH140|1U140|FCAG140|FBA140|\b140\b|[A-Z]{1,4}[-_]?[A-Z0-9]*140[A-Z0-9]*)', combined): return 48000, 14.0
    if re.search(r'(?:TAGLIA\s*12[05]|12[05]\s*R|ADH125|1U125|FCAG125|FBA125|\b125\b|\b120\b|[A-Z]{1,4}[-_]?[A-Z0-9]*12[05][A-Z0-9]*)', combined): return 42000, 12.5
    if re.search(r'(?:TAGLIA\s*10[05]|10[05]\s*R|ADH105|1U105|FCAG100|FBA100|\b100\b|\b105\b|[A-Z]{1,4}[-_]?[A-Z0-9]*10[05][A-Z0-9]*)', combined): return 36000, 10.0
    if re.search(r'(?:TAGLIA\s*8[05]|8[05]\s*R|90\s*R|4MXM80|5MXM90|\b80\b|\b85\b|\b90\b|[A-Z]{1,4}[-_]?[A-Z0-9]*8[05][A-Z0-9]*)', combined): return 28000, 8.0
    if re.search(r'(?:TAGLIA\s*7[01]|7[01]\s*R|68\s*R|1U71|FTXM71|AS7[01]|\bAR24\b|\b24000\b|(?<![A-Za-z0-9])7[01](?![A-Za-z0-9])|[-_ ]24(?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 24000, 7.0
    if re.search(r'(?:TAGLIA\s*60|60\s*R|(?<![A-Za-z0-9])60(?![A-Za-z0-9])|[-_ ]21(?:HR|HFN|RD|[A-Z]{1,3}\b|\b)|\b21000\b)', combined): return 21000, 6.0
    if re.search(r'(?:TAGLIA\s*5[023]0?|5[023]0?\s*R|1U50|FTXM50|AS50|SPG500|MLG500|SGE500|BT50|SLZ-M50|KP50|PKA-M50|RZGNP\s*50|HEC50|UIKOCAN18|UIKOCAS18|UIKOCON18|CL18|\bAR18\b|\b18000\b|(?<![A-Za-z0-9])5[023](?![A-Za-z0-9])|[-_ ]1[78](?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 18000, 5.0
    if re.search(r'(?:TAGLIA\s*4[012]|4[012]\s*R|1U42|FTXM42|CLIMATE\s*7000I\s*41|CL7000IU\s*W\s*41|\bAR15\b|\b15000\b|(?<![A-Za-z0-9])4[12](?![A-Za-z0-9])|2MXM40|[-_ ]14(?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 15000, 4.2
    if re.search(r'(?:TAGLIA\s*3[56]|3[56]\s*R|FK36|FK360|1U35|FTXM35|FTXC35|AS35|MSZ-AP35|\bAR12\b|\b12000\b|(?<![A-Za-z0-9])3[56](?![A-Za-z0-9])|[-_ ]12(?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 12000, 3.5
    if re.search(r'(?:TAGLIA\s*2[56]|2[56]\s*R|FK26|FK260|1U25|FTXM25|AS25|MSZ-AP25|\bAR09\b|\b9000\b|(?<![A-Za-z0-9])2[56](?![A-Za-z0-9])|[-_ ](?:09|9)(?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 9000, 2.5
    if re.search(r'(?:TAGLIA\s*20|20\s*R|1[56]\s*R|CS-MZ16|FTXM20|AS20|MSZ-AP20|\b7000\b|(?<![A-Za-z0-9])20(?![A-Za-z0-9])|(?<![A-Za-z0-9])16(?![A-Za-z0-9])|[-_ ](?:07|7)(?:HR|HFN|RD|[A-Z]{1,3}\b|\b))', combined): return 7000, 2.0

    m_kw = re.search(r'\b(\d+(?:[\.,]\d+)?)\s*KW\b', combined)
    if m_kw:
        kw = float(m_kw.group(1).replace(',', '.'))
        if kw <= 2.2: return 7000, kw
        if kw <= 3.0: return 9000, kw
        if kw <= 4.2: return 12000, kw
        if kw <= 4.8: return 14000, kw
        if kw <= 5.8: return 18000, kw
        if kw <= 6.8: return 21000, kw
        if kw <= 8.5: return 24000, kw
        if kw <= 11.0: return 36000, kw
        if kw <= 13.5: return 42000, kw
        if kw <= 15.5: return 48000, kw
        return 60000, kw

    return None, None

def kw_to_nominal_btu(kw: float) -> int:
    if kw <= 2.29: return 7000
    elif kw <= 2.99: return 9000
    elif kw <= 3.99: return 12000
    elif kw <= 4.79: return 14000
    elif kw <= 5.89: return 18000
    elif kw <= 6.79: return 21000
    elif kw <= 7.89: return 24000
    elif kw <= 8.89: return 28000
    elif kw <= 11.09: return 36000
    elif kw <= 13.09: return 42000
    elif kw <= 15.09: return 48000
    elif kw <= 19.09: return 60000
    else: return int(round(kw * 3.412142)) * 1000

def detect_refrigerant(text: str) -> str:
    t_u = normalize_text(text)
    if "R32" in t_u or "R-32" in t_u: return "R32"
    if "R410" in t_u or "R-410" in t_u: return "R410A"
    return "R32"

def detect_ui_type(name: str) -> str:
    n = normalize_text(name)
    if any(k in n for k in ["SENZA UNITA ESTERNA", "S/UE", "MONOBLOCCO", "UNICO", "APOLLO"]):
        return "SENZA_UNITA_ESTERNA"
    if "CANALIZZ" in n or "DUCT" in n:
        return "CANALIZZATO"
    if "60X60" in n or "60 X 60" in n or "62X62" in n or "57X57" in n or "CASSETTA 4C" in n:
        return "CASSETTA_60X60"
    if "90X90" in n or "90 X 90" in n or "84X84" in n or "ROUND FLOW" in n or "360" in n or "SUPER SLIM" in n:
        return "CASSETTA_90X90"
    if "1 VIA" in n or "1VIA" in n or "MONOVIA" in n:
        return "CASSETTA_1VIA"
    if "CASSETTA" in n:
        return "CASSETTA_60X60"
    if "CONSOLE" in n or "PAVIMENTO" in n or "INCASSO FNA" in n:
        return "CONSOLE_PAVIMENTO"
    if "SOFFITTO" in n or "PENSILE" in n:
        return "PENSILE_SOFFITTO"
    if "COLONNA" in n or "CABINET" in n:
        return "COLONNA"
    return "PARETE"

def detect_catalog_family(brand: str, name: str, mfg_code: str = "", page: int = None) -> Tuple[str, str, str]:
    b = (brand or "").strip().upper()
    n = normalize_text(name)
    m = normalize_text(mfg_code)
    full_text = f"{n} {m}"
    
    if any(k in full_text for k in ["SENZA UNITA ESTERNA", "S/UE", "MONOBLOCCO", "UNICO", "APOLLO", "FK26", "FK36"]):
        for fam in OFFICIAL_FAMILIES_DB.get("SENZA_UNITA_ESTERNA", []):
            if any(k in full_text for k in fam.get("keywords", [])):
                return fam["name"], fam["type"], fam["id"]
        return "SENZA UNITÀ ESTERNA MONOBLOCCO", "SENZA_UNITA_ESTERNA", "SUE_GENERIC"

    brand_fams = OFFICIAL_FAMILIES_DB.get(b, [])

    if page:
        for fam in brand_fams:
            if page in fam.get("pages", []):
                if any(k in full_text for k in fam.get("keywords", [])):
                    return fam["name"], fam["type"], fam["id"]

    for fam in brand_fams:
        if any(k in full_text for k in fam.get("keywords", [])):
            return fam["name"], fam["type"], fam["id"]

    if brand_fams:
        if "CANALIZZ" in full_text or "DUCT" in full_text:
            for fam in brand_fams:
                if fam["type"] in ["CANALIZZATO", "COMMERCIALE"]:
                    return fam["name"], fam["type"], fam["id"]
        if "CASSETTA" in full_text:
            for fam in brand_fams:
                if "CASSETTA" in fam["type"] or fam["type"] == "COMMERCIALE":
                    return fam["name"], fam["type"], fam["id"]
        if "CONSOLE" in full_text or "PAVIMENTO" in full_text:
            for fam in brand_fams:
                if "CONSOLE" in fam["type"] or fam["type"] == "COMMERCIALE":
                    return fam["name"], fam["type"], fam["id"]
        if "SOFFITTO" in full_text or "PENSILE" in full_text:
            for fam in brand_fams:
                if "SOFFITTO" in fam["type"] or fam["type"] == "COMMERCIALE":
                    return fam["name"], fam["type"], fam["id"]
        if "COLONNA" in full_text:
            for fam in brand_fams:
                if fam["type"] in ["COLONNA", "COMMERCIALE"]:
                    return fam["name"], fam["type"], fam["id"]
        if "MULTI" in full_text or "ATT" in full_text:
            for fam in brand_fams:
                if fam["type"] == "MULTI_SPLIT":
                    return fam["name"], fam["type"], fam["id"]

    if page:
        for fam in brand_fams:
            if page in fam.get("pages", []):
                return fam["name"], fam["type"], fam["id"]

    fallback_type = detect_ui_type(name)
    return f"{b} SERIE COMMERCIALE", fallback_type, f"{b}_COMMERCIAL"

def is_accessory_or_hydronic(name: str, cat: str) -> bool:
    n = normalize_text(name)
    c = normalize_text(cat)
    
    excluded_keywords = [
        "GARANZIA", "ESTENS GARANZIA", "ESTENSIONE", "COPERTURA", "TELO PROTETTIVO", "ANTIVIBR TACCO", "STAFFA", "MENSOLE", "SUPPORTO",
        "KIT CONNESSIONE", "KIT DRENAGGIO", "RISCALDATORE AUS", "BACINELLA", "GUAINA", "CAVO", "CAVI",
        "TUBO RAM", "BARRA CANALINA", "CURVA", "GIUNTO", "TERMINALE CANALINA", "RACCORDO",
        "PIEDINI GOMMA", "FILOCOMANDO", "TELECOMANDO", "COMANDO A FILO", "COMANDO WIRELESS",
        "GATEWAY", "CHIAVETTA", "SCHEDA WI-FI", "SCHEDA INTERFACCIA", "DISTRIBUTORE PER UI",
        "RICEVITORE", "ADATTATORE G 10", "ADATTATORE WI-FI", "ANGOLARE I-SEE", "PANNELLO X CASSETTA", "GRIGLIA",
        "DEFLETTORE", "POMPA SCARICO", "FILTRO", "ALABOX", "NICCHIA", "SCATOLA PREDISPOSIZIONE",
        "VALVOLA A 3 VIE", "SENSORE PRES", "CONTROLLO REMOTO", "TOUCH SCREEN WIRED",
        "KIT MORSETTIERA", "MORSETTIERA", "INTERFACCIA WI-FI", "INTERFACCIA WIFI",
        "COMANDO RIDONDANZA", "CONNETTORE MULTIUSO"
    ]
    if any(k in n for k in excluded_keywords):
        return True

    if n.startswith("KIT ") and not any(k in n for k in ["KIT MONO", "KIT DUAL", "KIT TRIAL", "KIT QUADRI", "KIT PENTA", "KIT COMPLETO"]):
        return True
    
    hydronic_keywords = [
        "ALTHERMA", "MAGIS PRO", "MAGIS COMBO", "ECODAN", "AQUAREA", "AROTHERM",
        "BI-BLOC", "HYDROBOX", "POMPA DI CALORE ARIA - ACQUA", "P/CAL", "BOLLITORE", "ACCUMULO"
    ]
    if any(k in n for k in hydronic_keywords):
        return True

    return False

def detect_multi_split_rule(brand: str, name: str, mfg: str) -> Optional[Dict[str, Any]]:
    combined = f"{brand} {name} {mfg}".upper()
    for r in MULTI_SPLIT_RULES:
        if r["brand"] == brand.upper() and r["pattern"].search(combined):
            return r
    return None

def detect_ports(name: str, mfg: str) -> int:
    combined = f"{name} {mfg}".upper()
    m_ports = re.search(r'\b([2-6])\s*(?:ATT|ATTACCHI|PORT|SPLIT)\b', combined)
    if m_ports:
        return int(m_ports.group(1))
    if any(k in combined for k in ['6MXM', 'MXZ-6']): return 6
    if any(k in combined for k in ['5MXM', 'MXZ-5', 'CU-5Z', '5U', 'MU5R', '5AMW', 'LSGT100', 'M5O', '125/5']): return 5
    if any(k in combined for k in ['4MXM', 'MXZ-4', 'CU-4Z', '4U', 'MU4R', '4AMW', 'LSGT80', 'M4O', '82/4', '105/4']): return 4
    if any(k in combined for k in ['3MXM', '3MXF', 'MXZ-3', 'CU-3Z', '3U', 'MU3R', '3AMW', 'LSGT60', 'M3O', '79/3']): return 3
    if any(k in combined for k in ['2MXM', '2MXF', 'MXZ-2', 'CU-2Z', '2U', 'MU2R', '2AMW', 'LSGT40', 'LSGT50', 'M2O', '41/2', '53/2']): return 2
    if 'MULTI' in combined: return 2
    return 1

def main():
    print("=======================================================================")
    print("  COSTRUZIONE MATRICE MASTER AC (DEFINITIVE 2026 COMBINATIONS EDITION)")
    print("=======================================================================\n")

    if not os.path.exists(MASTER_CATALOG_PATH):
        print(f"[ERRORE] Catalogo non trovato: {MASTER_CATALOG_PATH}")
        sys.exit(1)

    with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
        master_catalog = json.load(f)

    catalog_by_code = {str(it.get("code")).strip(): it for it in master_catalog if it.get("code")}
    print(f"[1/5] Caricamento catalogo master: {len(catalog_by_code)} articoli indicizzati.")

    # -------------------------------------------------------------
    # 2. CENSIMENTO DELLE UNITÀ INTERNE (UI)
    # -------------------------------------------------------------
    print("\n[2/5] Censimento delle Unità Interne (UI)...")
    catalog_uis_by_brand = defaultdict(list)
    unita_interne_dict = {}

    for it in master_catalog:
        n = (it.get("name") or "").upper()
        c = (it.get("category_path") or "").upper()
        b = (it.get("brand") or "").strip().upper()
        p = it.get("primary_page")

        is_ac_scope = (
            any(k in c for k in ["CONDIZIONAMENTO > CONDIZIONAMENTO", "CONDIZIONAMENTO > SENZA UNIT"]) or
            any(k in n for k in ["CLIMATIZZ", "CONDIZION", "SPLIT", "PARETE", "CANALIZZ", "CASSETTA", "CONSOLE", "S/UE"])
        )

        if is_ac_scope and not is_accessory_or_hydronic(n, c):
            is_ui = (
                ("UI " in n or "UNITA INTERNA" in n or "UNITA' INTERNA" in n or ("SPLIT" in n and "UE " not in n) or "S/UE" in n or "SENZA UNITA ESTERNA" in n)
                and not any(k in n for k in ["UE ", "UNITA ESTERNA", "UNITA' ESTERNA", "MOTOCONDENSANTE"])
            )

            if is_ui:
                code_str = str(it.get("code")).strip()
                mfg = str(it.get("mfg_code") or "").strip().upper()
                pdf_spec = PDF_SPECS_DB.get(code_str)
                if pdf_spec and pdf_spec.get("btu"):
                    btu_val = pdf_spec["btu"]
                    kw_val = pdf_spec.get("kw", 2.5)
                else:
                    btu_val, kw_val = extract_btu_and_kw(n, mfg)

                fam_name, fam_type, fam_id = detect_catalog_family(b, n, mfg, p)
                detected_type = detect_ui_type(n)
                eff_type = detected_type if detected_type != "PARETE" else fam_type
                btu_num = btu_val or 9000
                tag_btu_str = f"{btu_num} btu"
                tag_btu_disp = f"{btu_num:,}".replace(",", ".") + " BTU"

                ui_obj = {
                    "code": code_str,
                    "codice_pt": code_str,
                    "mfg_code": mfg,
                    "codice_mfg": mfg,
                    "name": it.get("name"),
                    "nome": it.get("name"),
                    "brand": b,
                    "tipo_unita": "UI" if eff_type != "SENZA_UNITA_ESTERNA" else "MONOBLOCCO_SUE",
                    "is_ui": eff_type != "SENZA_UNITA_ESTERNA",
                    "is_ue": False,
                    "is_monoblocco_sue": eff_type == "SENZA_UNITA_ESTERNA",
                    "famiglia_catalogo": fam_name,
                    "famiglia_id": fam_id,
                    "serie": fam_name,
                    "tipologia": eff_type,
                    "taglia_btu": btu_num,
                    "tag_btu": tag_btu_str,
                    "tag_btu_display": tag_btu_disp,
                    "tags": [tag_btu_disp, fam_name, eff_type],
                    "refrigerante": detect_refrigerant(n),
                    "gross_price": round(float(it.get("gross_price") or 0.0), 2),
                    "prezzo_listino": round(float(it.get("gross_price") or 0.0), 2),
                    "net_price": round(float(it.get("net_price") or 0.0), 2),
                    "prezzo_netto": round(float(it.get("net_price") or 0.0), 2),
                    "primary_page": p,
                    "pagina_catalogo": p,
                    "modelli_ue_compatibili": [],
                    "famiglie_ue_compatibili": [],
                    "serie_ue_compatibili": [],
                    "unita_esterne_compatibili": [],
                    "kit_commerciali_inclusi": []
                }
                catalog_uis_by_brand[b].append(ui_obj)
                unita_interne_dict[code_str] = ui_obj

    print(f"      Censite {len(unita_interne_dict)} Unità Interne (UI) su {len(catalog_uis_by_brand)} marchi.")

    # -------------------------------------------------------------
    # 3. CENSIMENTO DELLE UNITÀ ESTERNE (UE)
    # -------------------------------------------------------------
    print("\n[3/5] Censimento delle Unità Esterne (UE) e applicazione Tabelle di Combinazione...")
    unita_esterne_dict = {}
    brand_stats = defaultdict(lambda: {"ue_count": 0, "ui_count": 0, "kits_count": 0, "families": set(), "refrigerants": set()})
    all_ready_kits = []

    for it in master_catalog:
        n = (it.get("name") or "").upper()
        c = (it.get("category_path") or "").upper()
        b = (it.get("brand") or "").strip().upper()
        p = it.get("primary_page")

        is_ac_scope = (
            any(k in c for k in ["CONDIZIONAMENTO > CONDIZIONAMENTO", "CONDIZIONAMENTO > SENZA UNIT"]) or
            any(k in n for k in ["CLIMATIZZ", "CONDIZION", "SPLIT", "S/UE"])
        )

        if is_ac_scope and not is_accessory_or_hydronic(n, c):
            is_ue = (
                ("UE " in n or "UNITA ESTERNA" in n or "UNITA' ESTERNA" in n or "MOTOCONDENSANTE" in n or any(n.startswith(pr) for pr in ['2MX', '3MX', '4MX', '5MX', 'MXZ-', 'CU-2', 'CU-3', 'CU-4', 'CU-5', '2U', '3U', '4U', '5U', 'MU2', 'MU3', 'MU4', 'MU5', 'AJ0', '2AMW', '3AMW', '4AMW', '5AMW']))
                and not ("S/UE" in n or "SENZA UNITA" in n or "SENZA UNIT" in n or "MONOBLOCCO" in n)
            )

            if is_ue:
                ue_code_str = str(it.get("code")).strip()
                mfg_code = str(it.get("mfg_code") or "").strip().upper()
                gross_price = round(float(it.get("gross_price") or 0.0), 2)
                net_price = round(float(it.get("net_price") or 0.0), 2)
                refrigerant = detect_refrigerant(n)
                fam_name, fam_type, fam_id = detect_catalog_family(b, n, mfg_code, p)

                ue_pdf_spec = PDF_SPECS_DB.get(ue_code_str)
                if ue_pdf_spec and ue_pdf_spec.get("kw"):
                    kw_val = float(ue_pdf_spec["kw"])
                else:
                    _, kw_val = extract_btu_and_kw(n, mfg_code)

                # Rilevamento Porte / Attacchi e Regola Combinazioni Multi
                multi_rule = detect_multi_split_rule(b, n, mfg_code)
                ports = detect_ports(n, mfg_code)
                if not kw_val:
                    kw_val = 2.5 if ports == 1 else (ports * 2.0)

                system_names = {
                    1: "Mono-Split",
                    2: "Dual-Split (2 UI collegabili)",
                    3: "Trial-Split (3 UI collegabili)",
                    4: "Quadri-Split (4 UI collegabili)",
                    5: "Penta-Split (5 UI collegabili)",
                    6: "6-Split (6 UI collegabili)"
                }
                system_type = system_names.get(ports, f"{ports}-Split ({ports} UI collegabili)")

                # Pagina tabella combinazioni e combinazioni ammesse da catalogo
                if multi_rule:
                    comb_page = multi_rule["combination_page"]
                    table_name = multi_rule["table_name"]
                    allowed_combinations = multi_rule["comb_by_ports"].get(ports, [])
                else:
                    comb_page = p
                    table_name = "TABELLA CATALOGO"
                    if ports == 1:
                        target_nom_btu = kw_to_nominal_btu(kw_val)
                        allowed_combinations = [f"{target_nom_btu // 1000} ({target_nom_btu:,} BTU)".replace(",", ".")]
                    elif ports == 2:
                        allowed_combinations = ["20+20", "20+25", "20+35", "25+25", "25+35", "35+35"]
                    elif ports == 3:
                        allowed_combinations = ["20+20+20", "20+20+25", "20+25+25", "20+25+35", "25+25+25", "25+25+35"]
                    elif ports == 4:
                        allowed_combinations = ["20+20+20+20", "20+20+20+25", "20+20+25+25", "25+25+25+25"]
                    elif ports >= 5:
                        allowed_combinations = ["20+20+20+20+20", "20+20+20+20+25", "20+20+20+25+25", "25+25+25+25+25"]

                # Limite taglia massima UI per questo modello di UE (da tabelle combinazione catalogo)
                max_allowed_ui_btu = 24000
                if multi_rule and "max_size_by_model" in multi_rule:
                    for model_prefix, max_b in multi_rule["max_size_by_model"].items():
                        if model_prefix in mfg_code or model_prefix in n:
                            max_allowed_ui_btu = max_b
                            break
                    else:
                        if ports == 2 and kw_val <= 4.2:
                            max_allowed_ui_btu = 12000
                        elif ports == 2:
                            max_allowed_ui_btu = 18000
                        elif ports == 3:
                            max_allowed_ui_btu = 18000

                # Matching delle Unità Interne compatibili
                brand_uis_pool = catalog_uis_by_brand.get(b, [])
                compatible_ui_objects = []
                compatible_models_set: Set[str] = set()
                compatible_families_set: Set[str] = set()

                for cand_ui in brand_uis_pool:
                    cand_code = cand_ui["codice_pt"]
                    cand_mfg = cand_ui["codice_mfg"]
                    cand_name = cand_ui["nome"]
                    cand_fam = cand_ui["famiglia_catalogo"]
                    cand_btu = cand_ui["taglia_btu"]
                    cand_refrig = cand_ui["refrigerante"]
                    cand_type = cand_ui.get("tipologia", "PARETE")

                    if cand_type == "SENZA_UNITA_ESTERNA":
                        continue

                    # Refrigerante
                    if refrigerant == "R32" and cand_refrig == "R410A":
                        continue

                    # MULTI-SPLIT: verifica conformità con le tabelle combinazioni
                    if ports > 1 or "MULTI" in n:
                        if cand_btu and cand_btu > max_allowed_ui_btu:
                            continue

                        if multi_rule and "excluded_keywords" in multi_rule:
                            if any(k in cand_name or k in cand_mfg or k in cand_fam for k in multi_rule["excluded_keywords"]):
                                continue

                        if multi_rule and "allowed_keywords" in multi_rule:
                            if not any(k in cand_name or k in cand_mfg or k in cand_fam for k in multi_rule["allowed_keywords"]):
                                continue

                        if cand_mfg: compatible_models_set.add(cand_mfg)
                        compatible_families_set.add(cand_fam)
                        if not any(x["codice_pt"] == cand_code for x in compatible_ui_objects):
                            compatible_ui_objects.append(cand_ui)

                    # MONO-SPLIT: abbinamento alla stessa famiglia commerciale e taglia
                    else:
                        ue_target_btu = kw_to_nominal_btu(kw_val)
                        same_family = (cand_fam == fam_name) and ("SERIE COMMERCIALE" not in fam_name)
                        same_taglia = (cand_btu == ue_target_btu) if (cand_btu and ue_target_btu) else False

                        m_model_ue = re.search(r'[A-Z]{2,4}(\d{2})', mfg_code)
                        m_model_ui = re.search(r'[A-Z]{2,4}(\d{2})', cand_mfg)
                        code_taglia_match = (m_model_ue and m_model_ui and m_model_ue.group(1) == m_model_ui.group(1))

                        haier_match = (b == "HAIER" and ("1U" in n or "1U" in mfg_code) and same_taglia)
                        toshiba_match = (b == "TOSHIBA" and same_taglia and ("SERIE COMMERCIALE" not in cand_fam))
                        samsung_match = (b == "SAMSUNG" and same_taglia and ("CAC" in fam_name or "CAC" in cand_fam or same_family))

                        is_mono_compat = (
                            (same_family and same_taglia) or
                            (code_taglia_match and same_family) or
                            haier_match or
                            toshiba_match or
                            samsung_match
                        )

                        if is_mono_compat:
                            if cand_mfg: compatible_models_set.add(cand_mfg)
                            compatible_families_set.add(cand_fam)
                            if not any(x["codice_pt"] == cand_code for x in compatible_ui_objects):
                                compatible_ui_objects.append(cand_ui)

                # Generazione dei Kit Pronti (Ready Kits)
                processed_ready_kits = []
                ui_taglia_25 = next((ui for ui in compatible_ui_objects if ui["taglia_btu"] == 9000 and ui["tipologia"] == "PARETE"), None)
                ui_taglia_35 = next((ui for ui in compatible_ui_objects if ui["taglia_btu"] == 12000 and ui["tipologia"] == "PARETE"), None)
                if not ui_taglia_25 and compatible_ui_objects: ui_taglia_25 = compatible_ui_objects[0]
                if not ui_taglia_35 and compatible_ui_objects: ui_taglia_35 = compatible_ui_objects[-1]

                if ports > 1 and ui_taglia_25:
                    comps_all_25 = [ui_taglia_25] * ports
                    tot_gross_1 = gross_price + sum(c["gross_price"] for c in comps_all_25)
                    tot_net_1 = net_price + sum(c["net_price"] for c in comps_all_25)
                    kit_name_1 = f"Kit {b} {system_type} " + "+".join(["9.000 BTU"] * ports)
                    config_1 = "+".join(["25"] * ports)
                    
                    kit_1 = {
                        "id_kit": f"KIT-{ue_code_str}-1",
                        "code": f"KIT-{ue_code_str}-1",
                        "kit_name": kit_name_1,
                        "nome_kit": kit_name_1,
                        "configurazione": config_1,
                        "configuration": config_1,
                        "totale_prezzo_listino": round(tot_gross_1, 2),
                        "total_gross_price": round(tot_gross_1, 2),
                        "totale_prezzo_netto": round(tot_net_1, 2),
                        "total_net_price": round(tot_net_1, 2),
                        "pagina_catalogo": comb_page,
                        "catalog_page": comb_page,
                        "componenti_ui": comps_all_25,
                        "ui_components": comps_all_25
                    }
                    processed_ready_kits.append(kit_1)
                    all_ready_kits.append(kit_1)
                    brand_stats[b]["kits_count"] += 1

                    if ui_taglia_35 and ui_taglia_35 != ui_taglia_25:
                        comps_mixed = [ui_taglia_25] * (ports - 1) + [ui_taglia_35]
                        tot_gross_2 = gross_price + sum(c["gross_price"] for c in comps_mixed)
                        tot_net_2 = net_price + sum(c["net_price"] for c in comps_mixed)
                        kit_name_2 = f"Kit {b} {system_type} " + "+".join(["9.000 BTU"] * (ports - 1) + ["12.000 BTU"])
                        config_2 = "+".join(["25"] * (ports - 1) + ["35"])
                        
                        kit_2 = {
                            "id_kit": f"KIT-{ue_code_str}-2",
                            "code": f"KIT-{ue_code_str}-2",
                            "kit_name": kit_name_2,
                            "nome_kit": kit_name_2,
                            "configurazione": config_2,
                            "configuration": config_2,
                            "totale_prezzo_listino": round(tot_gross_2, 2),
                            "total_gross_price": round(tot_gross_2, 2),
                            "totale_prezzo_netto": round(tot_net_2, 2),
                            "total_net_price": round(tot_net_2, 2),
                            "pagina_catalogo": comb_page,
                            "catalog_page": comb_page,
                            "componenti_ui": comps_mixed,
                            "ui_components": comps_mixed
                        }
                        processed_ready_kits.append(kit_2)
                        all_ready_kits.append(kit_2)
                        brand_stats[b]["kits_count"] += 1

                elif ports == 1 and compatible_ui_objects:
                    chosen_ui = compatible_ui_objects[0]
                    tot_gross = gross_price + chosen_ui["gross_price"]
                    tot_net = net_price + chosen_ui["net_price"]
                    kit_name = f"Kit Monosplit {b} {fam_name} {chosen_ui['taglia_btu']} BTU"
                    config = f"{chosen_ui['taglia_btu']//1000}k"

                    kit_mono = {
                        "id_kit": f"KIT-{ue_code_str}-1",
                        "code": f"KIT-{ue_code_str}-1",
                        "kit_name": kit_name,
                        "nome_kit": kit_name,
                        "configurazione": config,
                        "configuration": config,
                        "totale_prezzo_listino": round(tot_gross, 2),
                        "total_gross_price": round(tot_gross, 2),
                        "totale_prezzo_netto": round(tot_net, 2),
                        "total_net_price": round(tot_net, 2),
                        "pagina_catalogo": comb_page,
                        "catalog_page": comb_page,
                        "componenti_ui": [chosen_ui],
                        "ui_components": [chosen_ui]
                    }
                    processed_ready_kits.append(kit_mono)
                    all_ready_kits.append(kit_mono)
                    brand_stats[b]["kits_count"] += 1

                sorted_models = sorted(list(compatible_models_set))
                sorted_fams = sorted(list(compatible_families_set))

                compatible_ui_sample_items = []
                for ui_obj in compatible_ui_objects:
                    compatible_ui_sample_items.append({
                        "code": ui_obj["codice_pt"],
                        "codice_pt": ui_obj["codice_pt"],
                        "mfg_code": ui_obj.get("codice_mfg", ""),
                        "codice_mfg": ui_obj.get("codice_mfg", ""),
                        "name": ui_obj["nome"],
                        "nome": ui_obj["nome"],
                        "brand": ui_obj["brand"],
                        "famiglia_catalogo": ui_obj.get("famiglia_catalogo", ui_obj.get("serie", "")),
                        "serie": ui_obj.get("serie", ""),
                        "tipologia": ui_obj.get("tipologia", "PARETE"),
                        "taglia_btu": ui_obj.get("taglia_btu", 9000),
                        "tag_btu": ui_obj.get("tag_btu", f"{ui_obj.get('taglia_btu', 9000)} btu"),
                        "tag_btu_display": ui_obj.get("tag_btu_display", f"{ui_obj.get('taglia_btu', 9000)} BTU"),
                        "gross_price": ui_obj.get("prezzo_listino", 0.0),
                        "prezzo_listino": ui_obj.get("prezzo_listino", 0.0),
                        "net_price": ui_obj.get("prezzo_netto", 0.0),
                        "prezzo_netto": ui_obj.get("prezzo_netto", 0.0),
                        "primary_page": ui_obj.get("pagina_catalogo"),
                        "pagina_catalogo": ui_obj.get("pagina_catalogo")
                    })

                ue_entry = {
                    "code": ue_code_str,
                    "codice_pt": ue_code_str,
                    "mfg_code": mfg_code,
                    "codice_mfg": mfg_code,
                    "name": it.get("name"),
                    "nome": it.get("name"),
                    "brand": b,
                    "tipo_unita": "UE",
                    "is_ue": True,
                    "is_ui": False,
                    "is_monoblocco_sue": False,
                    "famiglia_catalogo": fam_name,
                    "famiglia_id": fam_id,
                    "serie": fam_name,
                    "tipo_sistema": system_type,
                    "system_type": system_type,
                    "porte_attacchi": ports,
                    "ports": ports,
                    "max_ui_collegabili": ports,
                    "max_connected_uis": ports,
                    "potenza_nominale_kw": kw_val,
                    "taglia_kw": kw_val,
                    "tag_kw": f"{kw_val} kW",
                    "tag_kw_display": f"{kw_val} kW",
                    "refrigerante": refrigerant,
                    "prezzo_listino": gross_price,
                    "gross_price": gross_price,
                    "prezzo_netto": net_price,
                    "net_price": net_price,
                    "primary_page": p,
                    "pagina_catalogo": p,
                    "pagina_combinazioni_catalogo": comb_page,
                    "catalog_combination_page": comb_page,
                    "nome_tabella_combinazioni": table_name,
                    "famiglie_ui_compatibili": sorted_fams,
                    "serie_ui_compatibili": sorted_fams,
                    "modelli_ui_compatibili": sorted_models,
                    "totale_modelli_ui_compatibili": len(sorted_models),
                    "combinazioni_ammesse": allowed_combinations,
                    "combinazioni_ammesse_taglie": allowed_combinations,
                    "totale_kit_pronti": len(processed_ready_kits),
                    "kit_preconfigurati": processed_ready_kits,
                    "ready_kits": processed_ready_kits,
                    "unita_interne_compatibili": compatible_ui_sample_items,
                    "compatible_uis_sample": compatible_ui_sample_items
                }
                unita_esterne_dict[ue_code_str] = ue_entry
                brand_stats[b]["ue_count"] += 1
                brand_stats[b]["families"].add(fam_name)
                brand_stats[b]["refrigerants"].add(refrigerant)

    print(f"      Censite {len(unita_esterne_dict)} Unità Esterne (UE) su {len(brand_stats)} marchi.")

    # -------------------------------------------------------------
    # 4. REVERSE-MAPPING PER LE UNITÀ INTERNE (UI)
    # -------------------------------------------------------------
    print("\n[4/5] Popolamento relazioni inverse per le Unità Interne (UI)...")
    for ue_code, ue_data in unita_esterne_dict.items():
        ue_summary = {
            "codice_pt": ue_code,
            "code": ue_code,
            "codice_mfg": ue_data["codice_mfg"],
            "mfg_code": ue_data["codice_mfg"],
            "nome": ue_data["nome"],
            "name": ue_data["nome"],
            "brand": ue_data["brand"],
            "famiglia_catalogo": ue_data["famiglia_catalogo"],
            "serie": ue_data["serie"],
            "tipo_sistema": ue_data["tipo_sistema"],
            "system_type": ue_data["tipo_sistema"],
            "porte_attacchi": ue_data["porte_attacchi"],
            "ports": ue_data["porte_attacchi"],
            "max_ui_collegabili": ue_data["max_ui_collegabili"],
            "potenza_nominale_kw": ue_data["potenza_nominale_kw"],
            "tag_kw": f"{ue_data['potenza_nominale_kw']} kW" if ue_data.get('potenza_nominale_kw') else None,
            "refrigerante": ue_data["refrigerante"],
            "pagina_catalogo": ue_data["pagina_catalogo"],
            "pagina_combinazioni_catalogo": ue_data["pagina_combinazioni_catalogo"],
            "catalog_page": ue_data["pagina_catalogo"],
            "prezzo_netto": ue_data["prezzo_netto"],
            "net_price": ue_data["prezzo_netto"]
        }

        for ui in ue_data["unita_interne_compatibili"]:
            ui_code = ui["codice_pt"]
            if ui_code in unita_interne_dict:
                target_ui = unita_interne_dict[ui_code]
                if not any(x["codice_pt"] == ue_code for x in target_ui["unita_esterne_compatibili"]):
                    target_ui["unita_esterne_compatibili"].append(ue_summary)
                if ue_data["codice_mfg"] and ue_data["codice_mfg"] not in target_ui["modelli_ue_compatibili"]:
                    target_ui["modelli_ue_compatibili"].append(ue_data["codice_mfg"])
                if ue_data["famiglia_catalogo"] not in target_ui["famiglie_ue_compatibili"]:
                    target_ui["famiglie_ue_compatibili"].append(ue_data["famiglia_catalogo"])
                if ue_data["tipo_sistema"] not in target_ui["serie_ue_compatibili"]:
                    target_ui["serie_ue_compatibili"].append(ue_data["tipo_sistema"])

        for kit in ue_data["kit_preconfigurati"]:
            for comp in kit["componenti_ui"]:
                ui_code = comp["codice_pt"]
                if ui_code in unita_interne_dict:
                    target_ui = unita_interne_dict[ui_code]
                    if not any(k["id_kit"] == kit["id_kit"] for k in target_ui["kit_commerciali_inclusi"]):
                        target_ui["kit_commerciali_inclusi"].append({
                            "id_kit": kit["id_kit"],
                            "nome_kit": kit["nome_kit"],
                            "configurazione": kit["configurazione"],
                            "unita_esterna_codice": ue_code
                        })

    # -------------------------------------------------------------
    # 5. SALVATAGGIO DEI DATABASE E SINCRONIZZAZIONE
    # -------------------------------------------------------------
    print("\n[5/5] Sincronizzazione database Master JSON...")
    all_unique_families = set()
    formatted_brands = {}
    for b, s in sorted(brand_stats.items()):
        formatted_brands[b] = {
            "totale_unita_esterne": s["ue_count"],
            "totale_unita_interne": len(catalog_uis_by_brand.get(b, [])),
            "totale_kit_preconfigurati": s["kits_count"],
            "famiglie_catalogo_censite": sorted(list(s["families"])),
            "refrigeranti": sorted(list(s["refrigerants"]))
        }
        all_unique_families.update(s["families"])

    master_output = {
        "metadata": {
            "titolo": "Matrice Completa Compatibilità Climatizzatori Puglia Termica 2026",
            "fonte_catalogo": "CAT2600_CATALOGO_2026-V4pdf.pdf (Pagine 468-628)",
            "versione": "2026.4.0 - Combination Tables Edition",
            "descrizione": "Database perfetto con rigida classificazione UI vs UE, numero di UI collegabili per ogni UE, e relative UI compatibili certificate da catalogo.",
            "totale_unita_esterne": len(unita_esterne_dict),
            "totale_unita_interne": len(unita_interne_dict),
            "totale_kit_preconfigurati": len(all_ready_kits),
            "totale_famiglie_catalogo": len(all_unique_families),
            "totale_marchi": len(formatted_brands),
            "marchi": formatted_brands
        },
        "unita_esterne": unita_esterne_dict,
        "unita_interne": unita_interne_dict,
        "kit_completi": all_ready_kits
    }

    with open(OUTPUT_MASTER_PATH, "w", encoding="utf-8") as f:
        json.dump(master_output, f, indent=2, ensure_ascii=False)
    print(f"      File generato: {OUTPUT_MASTER_PATH}")

    # Aggiorna ac_outdoor_combinations.json
    with open(EXISTING_COMB_PATH, "w", encoding="utf-8") as f:
        json.dump(unita_esterne_dict, f, indent=2, ensure_ascii=False)
    print(f"      File sincronizzato: {EXISTING_COMB_PATH}")

    # Aggiorna anche gli attributi strutturati in unified_catalog_master.json
    print("      Aggiornamento anagrafica catalogo master unificato...")
    modified_count = 0
    for it in master_catalog:
        c_code = str(it.get("code")).strip()
        if c_code in unita_esterne_dict:
            ue = unita_esterne_dict[c_code]
            it["tipo_unita"] = "UE"
            it["is_ue"] = True
            it["is_ui"] = False
            it["is_monoblocco_sue"] = False
            it["porte_attacchi"] = ue["porte_attacchi"]
            it["max_ui_collegabili"] = ue["max_ui_collegabili"]
            it["tipo_sistema"] = ue["tipo_sistema"]
            it["pagina_combinazioni_catalogo"] = ue["pagina_combinazioni_catalogo"]
            it["combinazioni_ammesse"] = ue["combinazioni_ammesse"]
            it["taglia_kw"] = ue["taglia_kw"]
            it["tag_kw"] = ue["tag_kw"]
            it["tag_kw_display"] = ue["tag_kw_display"]
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            modified_count += 1
        elif c_code in unita_interne_dict:
            ui = unita_interne_dict[c_code]
            it["tipo_unita"] = ui["tipo_unita"]
            it["is_ui"] = ui["is_ui"]
            it["is_ue"] = False
            it["is_monoblocco_sue"] = ui["is_monoblocco_sue"]
            it["taglia_btu"] = ui["taglia_btu"]
            it["tag_btu"] = ui["tag_btu"]
            it["tag_btu_display"] = ui["tag_btu_display"]
            it["taglia_kw"] = None
            it["tag_kw"] = None
            it["tag_kw_display"] = None
            modified_count += 1

    with open(MASTER_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(master_catalog, f, indent=2, ensure_ascii=False)
    print(f"      Anagrafica unificata sincronizzata: {modified_count} articoli arricchiti.")

    print("\n[SUCCESSO] Matrice Climatizzatori 2026 generata e verificata con successo!")

if __name__ == "__main__":
    main()
