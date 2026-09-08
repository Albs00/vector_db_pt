"""
Modulo di Matching e Validazione Prodotti Climatizzazione <-> Puglia Termica.

Principi fondamentali:
1. Ricostruzione analitica della BOM attesa (ExpectedBOM) da Titolo e Riferimento.
2. Multiset matching: quantità duplicate rigorosamente verificate (es. 9+9 richiede 2x UI 9k).
3. Fall-through: se l'MPN esistente non è coerente, si scarta il match e si riesegue da zero la risoluzione a catalogo.
4. Riconoscimento revisioni: varianti simili/generazionali marcate con DA_VERIFICARE_VERSIONE e penalizzate nello score.
5. Verifica configurazione multisplit: porte e capacità verificate; se incerte, marcate con CONFIGURAZIONE_NON_CONFERMATA.
6. Punteggio basato su evidenze oggettive (Evidence-based scoring).
7. Autocorrezione sopra soglia alta (>= 80%); sotto soglia nessun codice forzato.
8. Zero codici inventati: ogni codice DEVE esistere nel catalogo PT con radice di categoria 'CONDIZIONAMENTO' (o accessorio lecito).
"""

import re
import json
import collections
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Set

BASE_DIR = Path(__file__).resolve().parents[1]
LOOKUP_PATH = BASE_DIR / "Knowledge" / "vector_db" / "exact_code_lookup.json"
MASTER_PATH = BASE_DIR / "Knowledge" / "unified_catalog_master.json"

norm = lambda s: re.sub(r'[^A-Z0-9]', '', str(s or '').upper())

@dataclass
class ExpectedBOM:
    brand: Optional[str] = None
    series: Optional[str] = None
    split_count: int = 1
    ui_btus: List[int] = field(default_factory=list)
    ui_colors: List[str] = field(default_factory=list)
    ue_model: Optional[str] = None
    generation: Optional[str] = None
    accessories: List[str] = field(default_factory=list)
    raw_title: str = ""
    raw_rif: str = ""

@dataclass
class MatchResult:
    status: str                         # COERENTE, DA VERIFICARE, DA_VERIFICARE_VERSIONE, CONFIGURAZIONE_NON_CONFERMATA, DISCORDANZA, SENZA CODICI
    confidence_score: str              # es. "100% (Certificato DB)", "95% (Risolto da Catalogo PT)", "85% (DA_VERIFICARE_VERSIONE)"
    score_value: int                   # Punteggio numerico 0-100
    mpn_suggerito: str                 # "codice+codice" se score >= 80%, altrimenti ""
    feedback: str
    componenti_db: str
    confronto_titolo_db: str
    fonte_verifica: str = "LanceDB / Catalogo Master PT"
    tua_verifica: str = "Da rivedere"
    note_revisione: str = ""


class ClimaMatchingEngine:
    AUTOCORRECT_THRESHOLD = 80

    def __init__(self, master_path: Optional[Path] = None, lookup_path: Optional[Path] = None):
        master_p = master_path or MASTER_PATH
        lookup_p = lookup_path or LOOKUP_PATH
        
        with open(lookup_p, "r", encoding="utf-8") as f:
            self.lookup: Dict[str, dict] = json.load(f)
            
        with open(master_p, "r", encoding="utf-8") as f:
            self.master_items: List[dict] = json.load(f)
            self.master_by_code: Dict[str, dict] = {it["code"]: it for it in self.master_items}

        self.clima_by_brand: Dict[str, List[dict]] = collections.defaultdict(list)
        for it in self.master_items:
            b = str(it.get("brand", "")).upper()
            if b:
                self.clima_by_brand[b].append(it)

        self.brands = sorted({p.get('brand') for p in self.lookup.values() if p.get('brand')}, key=len, reverse=True)
        self.aliases = {
            'HERMANN SAUNIER DUVAL': 'HSD',
            'MITSUBISHI ELECTRIC': 'MITSUBISHI',
            'DAB': 'DAB PUMPS'
        }

        self.families = [
            'ENERGY PRO X', 'HI COMFORT', 'UNI HB', 'CLIMATE 3000I', 'CLIMATE 3200I', 'CLIMATE 4000I', 'CLIMATE 7000I',
            'VIVAIR UNI COMFORT', 'VIVAIR TOP COMFORT', 'VIVAIR ONE', 'VIVAIR LITE',
            'WINDFREE AVANT S2', 'WINDFREE AVANT', 'WINDFREE ELITE S2', 'WINDFREE BLACK', 'CEBU S2', 'CEBU',
            'FLEXIS PLUS', 'GEOS PLUS', 'REVIVE', 'EXPERT', 'PEARL', 'ASTRA', 'BREVA E', 'BREVA',
            'PERFERA', 'STYLISH', 'COMFORA', 'EMURA', 'SENSIRA', 'GIADA', 'GOTHA', 'THOR', 'PEONY', 'VENUS',
            'LIBERO SMART', 'LIBERO S', 'LIBERO', 'ARTCOOL GALLERY LCD', 'ARTCOOL GALLERY PHOTO',
            'DELUXE AL AIR', 'DUALCOOL PREMIUM', 'BREEZELESS E', 'BREEZELESS+', 'FLEXI', 'ELEGANCE', 'EVOLUTION',
            'XTREME PRO', 'MSZ-AY', 'MSZ-BT', 'MSZ-LN', 'MSZ-HR', 'MSZ-EF', 'ETHEREA', 'BZ', 'SHORAI', 'HAORI',
            'CLIMAVAIR EXCLUSIVE', 'CLIMAVAIR INTRO', 'CKG', 'SPG', 'SGE', 'MPG/D',
            'CLIMATE 6000I', 'MCA4U', 'MFA2U', 'MTJ', 'RZGNP', 'RZ2GBK', 'RZGBK', 'RZ2GND', 'RZGND', 'RZ2GNF', 'RZGNF',
            'ACT', 'ADT', 'AKT', 'TZ', 'AARIA', 'ELIXA'
        ]
        self.families.sort(key=lambda s: (s.startswith('MSZ-'), len(norm(s))), reverse=True)

        # Mappature catalogo certificate
        self._init_catalog_mappings()

    def _init_catalog_mappings(self):
        # 1. SAMSUNG AVANT
        self.AVANT_UI = {
            7000: '50367801', 9000: '50367818', 12000: '50367825',
            15000: '50367832', 18000: '50367849', 24000: '50367856'
        }
        self.AVANT_UE_MONO = {
            7000: '50367771', 9000: '50367788', 12000: '50367795',
            15000: '50367863', 18000: '50367887', 24000: '50367894'
        }
        self.SAMSUNG_FJM = {
            'AJ040': ('99786168', 2, 14000), 'AJ050': ('99786182', 2, 18000),
            'AJ052': ('99786199', 3, 18000), 'AJ068': ('99786212', 3, 24000),
            'AJ080': ('99786236', 4, 28000), 'AJ100': ('99793463', 5, 34000)
        }

        # 2. PANASONIC BZ
        self.BZ_MAP = {
            9000: ('50203277', '50203246'),
            12000: ('50203260', '50203253'),
            18000: ('50221615', '50221592'),
            21000: ('50221622', '50221608'),
            24000: ('50221622', '50221608')
        }

        # 3. PANASONIC ETHEREA
        self.ETHEREA_UI_WHITE = {
            7000: '50207893', 9000: '50207572', 12000: '50207909',
            15000: '50207916', 18000: '50207725', 24000: '50207923'
        }
        self.ETHEREA_UI_DARK = {
            7000: '50212446', 9000: '50212460', 12000: '50212477',
            15000: '50212484', 18000: '50207954'
        }
        self.ETHEREA_UI_SILVER = {
            7000: '50212378', 9000: '50207930', 12000: '50207947',
            18000: '50207954'
        }
        self.ETHEREA_UE_MONO = {
            7000: '50212514', 9000: '50207824', 12000: '50207831',
            15000: '50207848', 18000: '50207855', 24000: '50207862'
        }
        self.PANASONIC_MULTI = {
            '2Z35': ('99675219', 2, 12000), '2Z41': ('99675226', 2, 14000), '2Z50': ('99675233', 2, 18000),
            '3Z52': ('99675240', 3, 18000), '3Z68': ('99675257', 3, 24000),
            '4Z68': ('99675264', 4, 24000), '4Z80': ('99675271', 4, 28000),
            '5Z90': ('99675288', 5, 30000)
        }

        # 4. MITSUBISHI KIRIGAMINE (MSZ-LN & MSZ-EF)
        self.LN_UI_NERO = {9000: '99788544', 12000: '99788575', 18000: '99788612'}
        self.LN_UI_ROSSO = {9000: '99788551', 12000: '99788599', 18000: '99788629'}
        self.LN_UI_BIANCO = {9000: '99788568', 12000: '99788605', 18000: '99788636'}
        self.LN_UE_MONO = {9000: '99788643', 12000: '99788650', 18000: '99788667'}

        self.EF_UI_BIANCO = {9000: '50441907', 12000: '50444625', 15000: '99788773', 18000: '99788803'}
        self.EF_UI_NERO = {9000: '50441891', 12000: '50441860', 15000: '50441495', 18000: '50444649'}
        self.EF_UI_SILVER = {9000: '50432646', 12000: '50443512', 15000: '99788766', 18000: '99788797'}
        self.EF_UE_MONO = {9000: '99712624', 12000: '99712631', 15000: '99712648', 18000: '50440849'}

        self.MITSUBISHI_MXZ = {
            '2F33': ('50196104', 2, 12000), '2F42': ('50196111', 2, 14000), '2F53': ('50196128', 2, 18000),
            '2HA40': ('50195695', 2, 14000), '2HA50': ('50195718', 2, 18000),
            '3F54': ('50196135', 3, 18000), '3F68': ('50196142', 3, 24000), '3HA50': ('50195725', 3, 18000),
            '4F72': ('50196166', 4, 25000), '4F80': ('50196173', 4, 28000), '5F102': ('50235551', 5, 35000),
            '6F120': ('50196197', 6, 42000), '6F122': ('50196197', 6, 42000)
        }

        # 5. HAIER EXPERT
        self.EXPERT_UI_NERO = {7000: '50224050', 9000: '50224012', 12000: '50224029', 15000: '50224067', 18000: '50224036', 24000: '50283910'}
        self.EXPERT_UI_BCO = {7000: '50125326', 9000: '50125210', 12000: '50125227', 15000: '50283866', 18000: '50125234', 24000: '50283873'}
        self.EXPERT_UE_MONO = {9000: '50131273', 12000: '50150212', 15000: '99715779', 18000: '50199242'}
        self.HAIER_MULTI = {
            2: ('50125265', 2), 3: ('50125289', 3), 4: ('50125296', 4), 5: ('50125302', 5)
        }

        # 6. MIDEA ELEGANCE & MULTI
        self.ELEGANCE_UI = {9000: '50131051', 12000: '50131075'}
        self.ELEGANCE_UE_MONO = {9000: '50131099', 12000: '50131105'}
        self.MIDEA_MULTI = {
            'M2OH-14': ('50131129', 2),
            'M2OE-18': ('50131136', 2),
            'M3OG-21': ('50131143', 3),
            'M3OA-27': ('50131150', 3),
            'M4OE-28': ('99717094', 4),
            'M4O-36': ('99649173', 4),
            'M5OE-42': ('50131174', 5)
        }

        # 7. SAMSUNG CEBU
        self.CEBU_UI = {7000: '50367900', 9000: '50367917', 12000: '50367924', 15000: '50367931', 18000: '50367948', 24000: '50367955'}
        self.CEBU_UE_MONO = {7000: '50367962', 9000: '50367979', 12000: '50367986', 15000: '50367993', 18000: '50368006', 24000: '50368013'}

        # 8. BOSCH CLIMATE (3000i/3200i, 4000i, 6000i, 7000i, 5000M)
        self.BOSCH_3000_UI = {7000: '50416219', 9000: '50418718', 12000: '50418725', 18000: '50410330', 24000: '50009442'}
        self.BOSCH_3000_UE_MONO = {9000: '50009398', 12000: '50009411', 18000: '50009435', 24000: '50009459'}

        self.BOSCH_4000_UI = {9000: '50279784', 12000: '50279807', 18000: '50381531'}
        self.BOSCH_4000_UE_MONO = {9000: '50279791', 12000: '50279814', 18000: '50381586'}

        self.BOSCH_6000_UI = {9000: '50113040', 12000: '50113064', 18000: '50113071', 24000: '50113088'}
        self.BOSCH_6000_UE_MONO = {9000: '50113217', 12000: '50113224', 18000: '50113248', 24000: '50113255'}

        self.BOSCH_7000_UE_MONO = {7000: '50276431', 9000: '50276479', 12000: '50276493', 15000: '50276516', 18000: '50276530'}
        self.BOSCH_7000_UI_WHITE = {7000: '50276394', 9000: '50276462', 12000: '50276486', 15000: '50276509', 18000: '50276523'}
        self.BOSCH_7000_UI_SILVER = {7000: '50276547', 9000: '50276561', 12000: '50276615', 15000: '50276639', 18000: '50276653'}
        self.BOSCH_7000_UI_BLACK = {7000: '50276684', 9000: '50276707', 12000: '50276714', 15000: '50276820', 18000: '50276851'}

        self.BOSCH_5000M = {
            '41/2': ('50195626', 2), '53/2': ('50195633', 2),
            '62/3': ('50195640', 3), '79/3': ('50252343', 3),
            '82/4': ('50195657', 4), '105/4': ('50250516', 4),
            '125/5': ('50252374', 5)
        }

    def validate_code_is_ac(self, code_str: str, row_idx: Any = 0, is_dynamic: bool = False) -> bool:
        if not code_str:
            return True
        for c in code_str.split('+'):
            c = c.strip()
            if not c:
                continue
            p = self.master_by_code.get(c)
            if not p:
                raise ValueError(f"CRITICAL ERROR [Row {row_idx}]: Code {c} NOT IN MASTER CATALOG!")
            cat_root = p.get('category_root', '')
            if cat_root in ['UTENSILI ED ATTREZZATURA', 'FERRAMENTA']:
                raise ValueError(f"CRITICAL ERROR [Row {row_idx}]: Code {c} ({p.get('name')}) is '{cat_root}'! Inserimento bloccato.")
            if is_dynamic and cat_root != 'CONDIZIONAMENTO':
                raise ValueError(f"CRITICAL ERROR [Row {row_idx}]: Suggested dynamic code {c} ({p.get('name')}) is '{cat_root}', NOT CONDIZIONAMENTO!")
        return True

    def get_btu(self, p: dict) -> Tuple[Optional[int], str]:
        btu_val = p.get('taglia_btu')
        if btu_val:
            return btu_val, 'specifica certificata DB'
        name = p.get('name', '')
        explicit = re.findall(r'(?<!\d)(7000|9000|12000|15000|18000|21000|24000|30000|36000|42000|43000|48000|60000)(?!\d)', name)
        if len(set(explicit)) == 1:
            return int(explicit[0]), 'descrizione articolo'
        st = p.get('search_text', '')
        m = re.search(r'Unit[àa]\s+Interna\s+Clima:\s*(\d+)\s*btu', st, re.I)
        if m:
            return int(m.group(1)), 'specifiche nel record DB'
        return None, 'taglia non leggibile'

    def parse_expected_bom(self, title: str, rif: str) -> ExpectedBOM:
        text = f"{rif} {title}".upper()
        bom = ExpectedBOM(raw_title=title, raw_rif=rif)

        # 1. Brand Detection
        matched_brand = next((v for k, v in self.aliases.items() if text.startswith(k + ' ') or f" {k} " in text), None)
        if not matched_brand:
            matched_brand = next((b for b in self.brands if b.upper() in text), None)
        bom.brand = matched_brand

        # 2. Split Count Detection
        # Check if product is ONLY an Outdoor Unit (UE only)
        is_ue_only = (
            ('UNITÀ ESTERNA' in text or 'UNITA ESTERNA' in text)
            and not any(k in text for k in ['MONOSPLIT', 'MONO SPLIT', 'DUAL SPLIT', 'TRIAL SPLIT', 'QUADRI SPLIT', 'PENTA SPLIT'])
            and 'SENZA UNITÀ ESTERNA' not in text
            and 'SENZA UNITA ESTERNA' not in text
        )
        if is_ue_only:
            bom.split_count = 0
        else:
            split_map = [('penta', 5), ('quadri', 4), ('trial', 3), ('dual', 2), ('mono', 1)]
            n = next((n for label, n in split_map if re.search(r'\b' + label + r'\s*-?\s*split\b', text, re.I)), None)
            if not n:
                if 'MONOSPLIT' in text or 'MONO SPLIT' in text:
                    n = 1
            bom.split_count = n or 1

        # 3. Taglie BTU Detection
        if re.search(r'9\+9 Bianco e 12 Nero', text, re.I):
            bom.ui_btus = [9000, 9000, 12000]
            bom.ui_colors = ['BIANCO', 'BIANCO', 'NERO']
            bom.split_count = 3
        else:
            cfg = re.search(r'(?<![A-Za-z0-9])(?:7|9|12|15|18|21|22|24)(?:\s*\+\s*(?:7|9|12|15|18|21|22|24))+(?!\d)', text)
            if cfg:
                bom.ui_btus = [int(x) * 1000 for x in re.findall(r'\d+', cfg.group(0))]
                if len(bom.ui_btus) > bom.split_count:
                    bom.split_count = len(bom.ui_btus)
            elif bom.split_count == 1:
                # 1. Esplicito "X BTU"
                m_btu_explicit = re.findall(r'(?<!\d)(7000|9000|12000|15000|18000|21000|24000|30000|36000|42000|48000|60000)\s*BTU\b', text)
                if m_btu_explicit:
                    bom.ui_btus = [int(m_btu_explicit[-1])]
                else:
                    # Sanifica i nomi serie contenenti numeri (es. CLIMATE 7000I, CL7000, CLIMATE 3000I)
                    clean_text = re.sub(r'\bCLIMATE\s*[0-9]+I?\b|\bCL[0-9]+[A-Z0-9]*\b', '', text)
                    nums = re.findall(r'(?<!\d)(7000|9000|12000|15000|18000|21000|24000|30000|36000|42000|48000|60000)(?!\d)', clean_text)
                    if nums:
                        bom.ui_btus = [int(nums[0])]
                    else:
                        m_code = re.search(r'[-_](20|25|26|35|41|42|50|52|53|60|70|71)\b', text)
                        if m_code:
                            mapping = {
                                '20': 7000, '25': 9000, '26': 9000, '35': 12000,
                                '41': 15000, '42': 15000, '50': 18000, '52': 18000, '53': 18000,
                                '60': 21000, '70': 24000, '71': 24000
                            }
                            bom.ui_btus = [mapping[m_code.group(1)]]

        # 4. Color Detection
        color_nero = bool(re.search(r'\b(NERO|NERA|BLACK|ONICE)\b', text)) or '_N' in rif
        color_rosso = bool(re.search(r'\b(ROSSO|RUBINO|RED)\b', text)) or '_R' in rif
        color_silver = bool(re.search(r'\b(SILVER|ARGENTO)\b', text)) or '_S' in rif
        color_dark = bool(re.search(r'\b(DARK|GRAFITE)\b', text))
        color_bianco = bool(re.search(r'\b(BIANCO|BIANCA|WHITE|PERLA)\b', text)) or '_B' in rif

        if not bom.ui_colors and bom.ui_btus:
            if color_dark:
                bom.ui_colors = ['DARK'] * len(bom.ui_btus)
            elif color_rosso:
                bom.ui_colors = ['ROSSO'] * len(bom.ui_btus)
            elif color_silver:
                bom.ui_colors = ['SILVER'] * len(bom.ui_btus)
            elif color_nero and color_bianco and len(bom.ui_btus) == 2:
                bom.ui_colors = ['NERO', 'BIANCO']
            elif color_nero:
                bom.ui_colors = ['NERO'] * len(bom.ui_btus)
            elif color_bianco:
                bom.ui_colors = ['BIANCO'] * len(bom.ui_btus)

        # 5. Series Detection
        bom.series = next((f for f in self.families if re.search(r'\b' + re.escape(f).replace(r'\ ', r'\s*') + (r'(?=\d|\b)' if f.startswith('MSZ-') or len(f) <= 6 else r'\b'), title, re.I)), None)

        # 6. Generation / Revision Token Detection
        gen = re.search(r'\b(FTXM|FTXA|FTXP|FTXJ|FTXF)\s*-\s*([A-Z])\b', text, re.I)
        if gen:
            bom.generation = gen.group(0).upper()
        elif 'ZKE' in text:
            bom.generation = 'ZKE'
        elif 'XKE' in text:
            bom.generation = 'XKE'
        elif ' S2' in text or 'S2_' in text:
            bom.generation = 'S2'

        # 7. Outdoor Unit Requested Detection
        m_ue = re.search(r'\bcon\s+([A-Za-z0-9/-]+(?:\s+[A-Za-z0-9/-]+)?)', text, re.I)
        if m_ue:
            cand_token = m_ue.group(1).strip()
            cand_token = re.split(r'\s+(?:INVERTER|WI-?FI|R-?32|R 32|CLASSE|GAS|BTU)\b', cand_token, flags=re.I)[0].strip()
            if re.match(r'[A-Za-z0-9/-]*\d', cand_token):
                bom.ue_model = cand_token

        # 8. Accessories Detection
        if 'STAFFA' in text or 'STAFFE' in text:
            bom.accessories.append('STAFFA')
        if 'WIFI OPTIONAL' in text or 'WI-FI OPTIONAL' in text:
            bom.accessories.append('WIFI_OPTIONAL')

        return bom

    def family_ok(self, f: str, p: dict) -> bool:
        p_name = p.get('name', '')
        if f == 'MPG/D': return bool(re.search(r'MPG\d+D', norm(p_name)))
        if f == 'BREVA E': return bool(re.search(r'BREVA.*\bE\b', p_name))
        if f in ['CLIMATE 3000I', 'CLIMATE 3200I']:
            return 'CLIMATE3000I' in norm(p_name) or 'CLIMATE3200I' in norm(p_name)
        return norm(f) in norm(p_name)

    def get_multi_ports(self, ue_name: str, mfg_code: str = "") -> Optional[int]:
        txt = f"{ue_name} {mfg_code}".upper()
        # Explicit "N ATT"
        m = re.search(r'(\d)\s*ATT', txt)
        if m:
            return int(m.group(1))
        # Words like DUAL, TRIAL, QUADRI, PENTA
        if 'PENTA' in txt or '5 ATT' in txt: return 5
        if 'QUADRI' in txt or '4 ATT' in txt: return 4
        if 'TRIAL' in txt or '3 ATT' in txt: return 3
        if 'DUAL' in txt or '2 ATT' in txt: return 2
        # Bosch multi: 5000M 41/2 -> 2, 5000M 79/3 -> 3, 5000M 105/4 -> 4, 5000M 125/5 -> 5
        m_bsh = re.search(r'5000M\s*\d+/([2-5])', txt)
        if m_bsh: return int(m_bsh.group(1))
        # Panasonic multi: 2Z -> 2, 3Z -> 3, 4Z -> 4, 5Z -> 5
        m_pan = re.search(r'\b([2-5])Z\d{2}', txt)
        if m_pan: return int(m_pan.group(1))
        # Daikin multi: 2MX -> 2, 3MX -> 3, 4MX -> 4, 5MX -> 5
        m_dak = re.search(r'\b([2-5])MX', txt)
        if m_dak: return int(m_dak.group(1))
        # Midea multi: M2O -> 2, M3O -> 3, M4O -> 4, M5O -> 5
        m_mid = re.search(r'\bM([2-5])O', txt)
        if m_mid: return int(m_mid.group(1))
        # Samsung multi: AJ040/050 -> 2, AJ052/068 -> 3, AJ080 -> 4, AJ100 -> 5
        if re.search(r'AJ0[45]0', txt): return 2
        if re.search(r'AJ0[56]8|AJ052', txt): return 3
        if re.search(r'AJ080', txt): return 4
        if re.search(r'AJ100', txt): return 5
        return None

    def validate_existing_mpn(self, cs: List[str], bom: ExpectedBOM) -> Tuple[bool, str, int, List[str], List[dict]]:
        """
        Valida i codici numerici già presenti in Colonna D con approccio MULTISET.
        Ritorna: (is_coherent, status, score, reasons, components_list)
        """
        reasons = []
        components_list = []

        for c in cs:
            p = self.lookup.get(c) or self.master_by_code.get(c, {})
            components_list.append(p if p else {'code': c, 'name': 'ASSENTE DAL DB'})

        missing = [c for c in cs if c not in self.lookup and c not in self.master_by_code]
        if missing:
            reasons.append('Codici non identificati nel DB: ' + ', '.join(sorted(set(missing))))
            return False, 'DISCORDANZA', 0, reasons, components_list

        # Verifica di non-contaminazione da categorie non clima
        for p in components_list:
            c = p.get('code', '')
            cat_root = p.get('category_root', '')
            if cat_root in ['UTENSILI ED ATTREZZATURA', 'FERRAMENTA']:
                reasons.append(f"Codice {c} appartiene a '{cat_root}' ({p.get('name')}), incompatibile con climatizzazione.")
                return False, 'DISCORDANZA', 0, reasons, components_list

        ui = [p for p in components_list if p.get('is_ui') or str(p.get('name', '')).startswith('UI ')]
        ue = [p for p in components_list if p.get('is_ue') or str(p.get('name', '')).startswith(('UE ', 'U.E. '))]
        extra = [p for p in components_list if p not in ui and p not in ue]

        # 1. Multiset UI Quantity check
        if bom.split_count == 0:
            if len(ui) != 0:
                reasons.append(f'Presenti UI nel codice ({len(ui)}) ma il prodotto è una sola Unità Esterna.')
            if len(ue) != 1:
                reasons.append(f'Quantità UE diversa dal titolo: presenti {len(ue)} UE vs attesa 1 UE')
        else:
            if len(ui) != bom.split_count:
                reasons.append(f'Quantità UI diversa dal titolo: presenti {len(ui)} UI nel codice vs attese {bom.split_count}')
            if len(ue) != 1:
                reasons.append(f'Quantità UE diversa dal titolo: presenti {len(ue)} UE vs attesa 1 UE')

        # 2. Multiset BTU Taglie check
        actual_btus = [self.get_btu(p)[0] for p in ui]
        if bom.ui_btus:
            expected_counter = collections.Counter(bom.ui_btus)
            actual_counter = collections.Counter([b for b in actual_btus if b is not None])
            if expected_counter != actual_counter:
                reasons.append(f'Discordanza taglie multiset: richieste {dict(expected_counter)}, trovate {dict(actual_counter)}')

        # 3. Brand check
        if bom.brand:
            wrong_brand = [p.get('code') for p in ui + ue if p.get('brand') and p.get('brand').upper() != bom.brand.upper()]
            if wrong_brand:
                reasons.append(f'Marca diversa dal titolo ({bom.brand}): codici {wrong_brand}')

        # 4. Series check
        if bom.series:
            wrong_series = [p.get('code', '') + ' ' + p.get('name', '') for p in ui if not self.family_ok(bom.series, p)]
            if 'Console UQ09F' in bom.raw_title and bom.series == 'LIBERO SMART':
                wrong_series = [x for x in wrong_series if 'UQ09F' not in x]
            if wrong_series:
                reasons.append(f'Serie UI diversa da quella richiesta ({bom.series}): ' + '; '.join(wrong_series))

        # 5. Generation / Revision check
        version_divergence = False
        if bom.generation:
            for p in ui:
                m_gen = re.search(r'\b(FTXM|FTXA|FTXP|FTXJ|FTXF)\s*[-_]?\s*([A-Z])\b', bom.raw_title, re.I)
                if m_gen:
                    actual_gen = re.search(m_gen.group(1) + r'\d{2}([A-Z])', norm(p.get('name', '') + ' ' + p.get('mfg_code', '')))
                    if actual_gen and actual_gen.group(1) != m_gen.group(2).upper():
                        version_divergence = True
                        reasons.append(f'Revisione/Generazione diversa: titolo {m_gen.group(0)} vs DB {p.get("name", "")}')
                if bom.generation in ['XKE', 'ZKE']:
                    actual_name = norm(p.get('name', '') + ' ' + p.get('mfg_code', ''))
                    if bom.generation == 'XKE' and 'ZKE' in actual_name:
                        version_divergence = True
                        reasons.append(f'Revisione/Generazione diversa: titolo richiede {bom.generation} vs DB {p.get("name", "")}')
                    elif bom.generation == 'ZKE' and 'XKE' in actual_name:
                        version_divergence = True
                        reasons.append(f'Revisione/Generazione diversa: titolo richiede {bom.generation} vs DB {p.get("name", "")}')
                if bom.generation == 'S2':
                    actual_name = p.get('name', '').upper()
                    if 'S2' not in actual_name and 'AVANT' in actual_name:
                        version_divergence = True
                        reasons.append(f'Revisione/Generazione diversa: titolo richiede S2 vs DB {p.get("name", "")}')

        # 6. UE Model Token check
        if bom.ue_model and len(ue) == 1:
            clean_ue_req = norm(bom.ue_model)
            clean_ue_actual = norm(ue[0].get('name', '') + ' ' + ue[0].get('mfg_code', ''))
            if clean_ue_req not in clean_ue_actual:
                reasons.append(f'Modello UE titolo non riscontrato esattamente: {bom.ue_model} vs DB {ue[0].get("name", "")}')

        # 7. Multisplit ports & compatibility check
        unconfirmed_multi = False
        if bom.split_count > 1:
            for p in ue:
                ports = self.get_multi_ports(p.get('name', ''), p.get('mfg_code', ''))
                if ports is not None and ports < bom.split_count:
                    unconfirmed_multi = True
                    reasons.append(f'Attacchi UE insufficienti: UE {p.get("name", "")} ha {ports} attacchi, split attesi {bom.split_count}')

        # 8. Accessories check
        missing_accessory = False
        if 'STAFFA' in bom.accessories and not any('STAFF' in p.get('name', '').upper() for p in extra):
            missing_accessory = True
            reasons.append('Staffa indicata nel titolo ma non presente nei codici MPN')

        # Se ci sono problemi di configurazione multisplit (porte insufficienti)
        if unconfirmed_multi:
            return False, 'CONFIGURAZIONE_NON_CONFERMATA', 75, reasons, components_list

        # Valutazione Esito e Score
        has_critical_error = any(
            'Quantità UI' in r or 'Quantità UE' in r or 'Discordanza taglie' in r or
            'Marca diversa' in r or 'Serie UI diversa' in r
            for r in reasons
        )

        if has_critical_error:
            return False, 'DISCORDANZA', 0, reasons, components_list

        if version_divergence:
            return False, 'DA_VERIFICARE_VERSIONE', 85, reasons, components_list

        if missing_accessory or reasons:
            return False, 'DA VERIFICARE', 90, reasons, components_list

        return True, 'COERENTE', 100, ['Quantità, serie/modello e taglie perfettamente coerenti nei controlli multiset.'], components_list

    def resolve_bom_from_catalog(self, bom: ExpectedBOM) -> Tuple[List[str], List[dict], str, int, str]:
        """
        Risolve la BOM da zero direttamente dal catalogo master PT.
        Ritorna: (candidate_codes, candidate_components, status, score, feedback)
        """
        text = f"{bom.raw_rif} {bom.raw_title}".upper()

        # Verifica preliminare marchi non commercializzati
        if any(nb in text for nb in ['4XE', 'AERMEC', 'MAXA', 'INNOVA', 'SAMSUNG COMMERCIAL', 'CLIVET COMMERCIAL']):
            return [], [], 'SENZA CODICI', 0, 'Marchio o gamma commerciale fuori dal catalogo Puglia Termica.'

        # 1. SAMSUNG AVANT
        if 'AVANT' in text:
            if bom.ui_btus:
                if len(bom.ui_btus) == 1:
                    b = bom.ui_btus[0]
                    if b in self.AVANT_UI and b in self.AVANT_UE_MONO:
                        codes = [self.AVANT_UI[b], self.AVANT_UE_MONO[b]]
                        return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con componenti certificati Samsung WindFree Avant S2.'
                else:
                    uis = [self.AVANT_UI.get(b) for b in bom.ui_btus]
                    ue = None
                    ue_conf_ok = True
                    for k, (ue_code, ports, cap) in self.SAMSUNG_FJM.items():
                        if k in text:
                            ue = ue_code
                            if ports < len(bom.ui_btus):
                                ue_conf_ok = False
                            break
                    if not ue:
                        return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Samsung Avant: unità esterna FJM non specificata nel titolo/riferimento. UE non inferibile automaticamente senza conferma dal catalogo PT. Autocorrezione bloccata.'
                    if not ue_conf_ok:
                        return [c for c in uis if c] + [ue], [self.master_by_code[c] for c in uis + [ue] if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Attacchi UE FJM insufficienti per gli split richiesti. Autocorrezione bloccata.'
                    if all(uis) and ue:
                        codes = uis + [ue]
                        return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con multisplit Samsung Avant S2 e UE FJM certificata.'

        # 2. PANASONIC BZ
        if re.search(r'\bBZ\b|BZ25|BZ35|BZ50|BZ60', text):
            if bom.ui_btus and bom.ui_btus[0] in self.BZ_MAP:
                codes = list(self.BZ_MAP[bom.ui_btus[0]])
                return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con monosplit Panasonic serie BZ ZKE certificato a catalogo.'

        # 3. PANASONIC ETHEREA
        if 'ETHEREA' in text:
            if bom.ui_btus:
                color = bom.ui_colors[0] if bom.ui_colors else 'WHITE'
                ui_map = self.ETHEREA_UI_DARK if color == 'DARK' else (self.ETHEREA_UI_SILVER if color == 'SILVER' else self.ETHEREA_UI_WHITE)
                
                version_flag = False
                if 'XKE' in text:
                    version_flag = True

                if len(bom.ui_btus) == 1:
                    b = bom.ui_btus[0]
                    ui_code = ui_map.get(b, self.ETHEREA_UI_WHITE.get(b))
                    ue_code = self.ETHEREA_UE_MONO.get(b)
                    if ui_code and ue_code:
                        codes = [ui_code, ue_code]
                        st = 'DA_VERIFICARE_VERSIONE' if version_flag else 'COERENTE'
                        sc = 85 if version_flag else 95
                        fb = 'Discrepanza revisione XKE vs ZKE a catalogo. Autocorrezione bloccata.' if version_flag else 'Risolto con monosplit Panasonic Etherea certificato.'
                        return codes, [self.master_by_code[c] for c in codes], st, sc, fb
                else:
                    uis = [ui_map.get(b, self.ETHEREA_UI_WHITE.get(b)) for b in bom.ui_btus]
                    ue = None
                    ue_conf_ok = True
                    for k, (ue_code, ports, cap) in self.PANASONIC_MULTI.items():
                        if k in text:
                            ue = ue_code
                            if ports < len(bom.ui_btus):
                                ue_conf_ok = False
                            break
                    if not ue:
                        return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Panasonic Etherea: unità esterna multi non specificata nel titolo/riferimento. UE non inferibile automaticamente senza conferma da catalogo PT. Autocorrezione bloccata.'
                    if not ue_conf_ok:
                        return [c for c in uis if c] + [ue], [self.master_by_code[c] for c in uis + [ue] if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Attacchi UE insufficienti per il numero di UI richieste. Autocorrezione bloccata.'
                    if all(uis) and ue:
                        codes = uis + [ue]
                        st = 'DA_VERIFICARE_VERSIONE' if version_flag else 'COERENTE'
                        sc = 80 if (color == 'DARK' and 18000 in bom.ui_btus) else (85 if version_flag else 95)
                        fb = 'Taglia 18k Dark adattata a Silver.' if (color == 'DARK' and 18000 in bom.ui_btus) else ('Discrepanza revisione XKE vs ZKE a catalogo. Autocorrezione bloccata.' if version_flag else 'Risolto con multisplit Panasonic Etherea.')
                        return codes, [self.master_by_code[c] for c in codes], st, sc, fb

        # 4. MITSUBISHI KIRIGAMINE (MSZ-LN & MSZ-EF)
        if 'MSZ-LN' in text or 'MSZ-EF' in text or 'KIRIGAMINE' in text or any(k in text for k in ['LN25', 'LN35', 'LN50', 'EF25', 'EF35', 'EF42', 'EF50']):
            if bom.ui_btus:
                is_ef = 'MSZ-EF' in text or 'ZEN' in text or 'EF-' in text or any(k in text for k in ['EF25', 'EF35', 'EF42', 'EF50'])
                color_nero = 'NERO' in text or 'BLACK' in text or 'ONICE' in text or '_N' in bom.raw_rif or 'KB' in text
                color_rosso = 'ROSSO' in text or 'RUBINO' in text or 'RED' in text or '_R' in bom.raw_rif
                color_silver = 'SILVER' in text or 'ARGENTO' in text or 'KS' in text or '_S' in bom.raw_rif
                color_bianco = 'BIANCO' in text or 'WHITE' in text or 'PERLA' in text or '_B' in bom.raw_rif or 'KW' in text

                if is_ef:
                    ef_map = self.EF_UI_NERO if color_nero else (self.EF_UI_SILVER if color_silver else self.EF_UI_BIANCO)
                    if len(bom.ui_btus) == 1:
                        b = bom.ui_btus[0]
                        if b in ef_map and b in self.EF_UE_MONO:
                            codes = [ef_map[b], self.EF_UE_MONO[b]]
                            return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con monosplit Mitsubishi Kirigamine Zen MSZ-EF.'
                    else:
                        uis = [ef_map.get(b) for b in bom.ui_btus]
                        ue = None
                        ue_conf_ok = True
                        for k, (ue_code, ports, cap) in self.MITSUBISHI_MXZ.items():
                            if k in text:
                                ue = ue_code
                                if ports < len(bom.ui_btus):
                                    ue_conf_ok = False
                                break
                        if not ue:
                            return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Mitsubishi MXZ: unità esterna non specificata nel titolo/riferimento. UE non inferibile automaticamente senza conferma da catalogo PT. Autocorrezione bloccata.'
                        if not ue_conf_ok:
                            return [c for c in uis if c] + [ue], [self.master_by_code[c] for c in uis + [ue] if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Attacchi MXZ insufficienti per il numero di UI richieste. Autocorrezione bloccata.'
                        if all(uis) and ue:
                            codes = uis + [ue]
                            return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con multisplit Mitsubishi Kirigamine Zen MSZ-EF.'
                else:
                    # MSZ-LN
                    if len(bom.ui_btus) == 1:
                        b = bom.ui_btus[0]
                        ln_map = self.LN_UI_NERO if color_nero else (self.LN_UI_ROSSO if color_rosso else self.LN_UI_BIANCO)
                        if b in ln_map and b in self.LN_UE_MONO:
                            codes = [ln_map[b], self.LN_UE_MONO[b]]
                            return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con monosplit Mitsubishi Kirigamine Style MSZ-LN.'
                    else:
                        # Kit misti colore
                        if 'NERO+BIANCO' in text or 'BIANCO+NERO' in text:
                            uis = [self.LN_UI_NERO.get(bom.ui_btus[0]), self.LN_UI_BIANCO.get(bom.ui_btus[1])]
                        elif 'NERO+ROSSO' in text or 'ROSSO+NERO' in text:
                            uis = [self.LN_UI_NERO.get(bom.ui_btus[0]), self.LN_UI_ROSSO.get(bom.ui_btus[1])]
                        elif 'BIANCO+NERO+NERO' in text:
                            uis = [self.LN_UI_BIANCO.get(bom.ui_btus[0]), self.LN_UI_NERO.get(bom.ui_btus[1]), self.LN_UI_NERO.get(bom.ui_btus[2])]
                        else:
                            ln_map = self.LN_UI_NERO if color_nero else (self.LN_UI_ROSSO if color_rosso else self.LN_UI_BIANCO)
                            uis = [ln_map.get(b) for b in bom.ui_btus]
                        ue = None
                        ue_conf_ok = True
                        for k, (ue_code, ports, cap) in self.MITSUBISHI_MXZ.items():
                            if k in text:
                                ue = ue_code
                                if ports < len(bom.ui_btus):
                                    ue_conf_ok = False
                                break
                        if not ue:
                            return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Mitsubishi MXZ: unità esterna non specificata nel titolo/riferimento. UE non inferibile automaticamente senza conferma da catalogo PT. Autocorrezione bloccata.'
                        if not ue_conf_ok:
                            return [c for c in uis if c] + [ue], [self.master_by_code[c] for c in uis + [ue] if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Attacchi MXZ insufficienti per il numero di UI richieste. Autocorrezione bloccata.'
                        if all(uis) and ue:
                            codes = uis + [ue]
                            return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con multisplit Mitsubishi Kirigamine Style MSZ-LN.'

        # 5. MITSUBISHI KIT MISTO (MSZ-LN + MSZ-AY)
        if 'MSZ-LN' in text and 'MSZ-AY' in text:
            ue = '50196111' if '2F42' in text else ('50196128' if '2F53' in text else None)
            if ue:
                codes = ['99788544', '50195824', ue]
                return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto da catalogo PT per kit misto MSZ-LN + MSZ-AY.'
            else:
                return ['99788544', '50195824'], [self.master_by_code['99788544'], self.master_by_code['50195824']], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Kit misto MSZ-LN + MSZ-AY: unità esterna multi non confermata nel titolo. Autocorrezione bloccata.'

        # 6. HAIER EXPERT
        if 'EXPERT' in text and 'HAIER' in text:
            color_nero = bool(re.search(r'NERO|NERA|BLACK', text))
            ui_map = self.EXPERT_UI_NERO if color_nero else self.EXPERT_UI_BCO
            if bom.ui_btus:
                if len(bom.ui_btus) == 1:
                    b = bom.ui_btus[0]
                    if b in ui_map and b in self.EXPERT_UE_MONO:
                        codes = [ui_map[b], self.EXPERT_UE_MONO[b]]
                        return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con monosplit Haier Expert certificato.'
                else:
                    uis = [ui_map.get(b) for b in bom.ui_btus]
                    ue = None
                    for k, v in [('2U40', '50125265'), ('2U50', '50125265'), ('3U55', '50125289'), ('3U70', '50125289'), ('4U85', '50125296'), ('5U100', '50125302')]:
                        if k in text:
                            ue = v
                            break
                    if not ue:
                        return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Haier Expert: unità esterna multi non specificata nel titolo. UE non inferibile automaticamente. Autocorrezione bloccata.'
                    codes = [c for c in uis if c] + [ue]
                    return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con multisplit Haier Expert certificato a catalogo.'

        # 7. MIDEA ELEGANCE
        if 'ELEGANCE' in text and 'MIDEA' in text:
            if bom.ui_btus:
                if len(bom.ui_btus) == 1:
                    b = bom.ui_btus[0]
                    if b in self.ELEGANCE_UI and b in self.ELEGANCE_UE_MONO:
                        codes = [self.ELEGANCE_UI[b], self.ELEGANCE_UE_MONO[b]]
                        return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 90, 'Risolto con codici ufficiali serie Midea Elegance certificati a catalogo.'
                else:
                    uis = [self.ELEGANCE_UI.get(b) for b in bom.ui_btus]
                    ue = None
                    ue_conf_ok = True
                    for k, (ue_code, ports) in self.MIDEA_MULTI.items():
                        if k in text:
                            ue = ue_code
                            if ports < len(bom.ui_btus):
                                ue_conf_ok = False
                            break
                    if not ue:
                        return [c for c in uis if c], [self.master_by_code[c] for c in uis if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, 'Configurazione multisplit Midea Elegance: unità esterna multi non specificata nel titolo. UE non inferibile automaticamente senza conferma da catalogo PT. Autocorrezione bloccata.'
                    if not ue_conf_ok:
                        return [c for c in uis if c] + [ue], [self.master_by_code[c] for c in uis + [ue] if c], 'CONFIGURAZIONE_NON_CONFERMATA', 75, f'Attacchi UE Midea ({ports}) insufficienti per {len(bom.ui_btus)} split. Autocorrezione bloccata.'
                    if all(uis) and ue:
                        codes = uis + [ue]
                        return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 90, 'Risolto con multisplit serie Midea Elegance certificato a catalogo.'

        # 8. SAMSUNG CEBU
        if 'CEBU' in text and ('SAMSUNG' in text or any(k in text for k in ['AR09', 'AR12', 'AR18', 'AR24'])):
            if bom.ui_btus:
                b = bom.ui_btus[0]
                if b in self.CEBU_UI and b in self.CEBU_UE_MONO:
                    codes = [self.CEBU_UI[b], self.CEBU_UE_MONO[b]]
                    return codes, [self.master_by_code[c] for c in codes], 'COERENTE', 95, 'Risolto con monosplit Samsung Cebu S2 certificato.'

        # Fallback generico da catalogo
        if not bom.brand:
            return [], [], 'SENZA CODICI', 0, 'Marchio non riconosciuto nel titolo/riferimento.'

        brand_prods = self.clima_by_brand.get(bom.brand.upper(), [])
        if not brand_prods:
            return [], [], 'SENZA CODICI', 0, f'Nessun articolo per il marchio {bom.brand} a catalogo PT.'

        # Tentativo di isolamento monosplit per marca, serie e taglia (HARD GATE: match solo serie/taglia)
        if bom.split_count == 1 and bom.ui_btus:
            desired_btu = bom.ui_btus[0]
            ui_cands = [p for p in brand_prods if (p.get('is_ui') or str(p.get('name', '')).startswith('UI ')) and self.get_btu(p)[0] == desired_btu]
            if bom.series:
                ui_cands = [p for p in ui_cands if self.family_ok(bom.series, p)]
            
            if len(ui_cands) == 1:
                ui_cand = ui_cands[0]
                ue_cands = [p for p in brand_prods if (p.get('is_ue') or 'UE ' in str(p.get('name', ''))) and 'MULTI' not in p.get('name', '').upper() and self.get_btu(p)[0] == desired_btu]
                if bom.series:
                    ue_cands_fam = [p for p in ue_cands if self.family_ok(bom.series, p)]
                    if len(ue_cands_fam) == 1:
                        ue_cands = ue_cands_fam
                if len(ue_cands) == 1:
                    codes = [ui_cand['code'], ue_cands[0]['code']]
                    return codes, [ui_cand, ue_cands[0]], 'DA VERIFICARE', 80, f'Match candidato basato solo su serie {bom.series} e taglia {desired_btu} BTU: richiede verifica manuale del modello esatto. Autocorrezione bloccata.'

        return [], [], 'SENZA CODICI', 0, 'Modello specifico non identificato in modo univoco nel catalogo unificato PT.'

    def match_product(self, row_id: Any, rif: str, title: str, mpn_orig: str) -> MatchResult:
        """
        Punto di ingresso principale per il match di una riga.
        """
        bom = self.parse_expected_bom(title, rif)
        cs = re.findall(r'(?<!\d)\d{8}(?!\d)', str(mpn_orig or ''))

        # SE MPN ESISTE:
        if cs:
            is_coherent, status, score, reasons, components_list = self.validate_existing_mpn(cs, bom)
            
            if is_coherent:
                # 100% Coerente
                comp_lines = []
                qty_map = collections.Counter(cs)
                for p in components_list:
                    c = p.get('code', '')
                    btu_str = f" ({p.get('taglia_btu')} BTU)" if p.get('taglia_btu') else ""
                    comp_lines.append(f"{qty_map[c]} × {c}: {p.get('name', '')}{btu_str}")
                
                return MatchResult(
                    status='COERENTE',
                    confidence_score='100% (Certificato DB)',
                    score_value=100,
                    mpn_suggerito="+".join(cs),
                    feedback='Quantità, serie/modello e taglie perfettamente coerenti nei controlli multiset.',
                    componenti_db='\n'.join(list(dict.fromkeys(comp_lines))),
                    confronto_titolo_db=f"Brand: {bom.brand} | Serie: {bom.series} | UI: {bom.ui_btus} | UE: 1 unità"
                )
            
            # Se è una revisione simile / accessorio / configurazione non confermata:
            if status in ['DA_VERIFICARE_VERSIONE', 'DA VERIFICARE', 'CONFIGURAZIONE_NON_CONFERMATA']:
                comp_lines = []
                qty_map = collections.Counter(cs)
                for p in components_list:
                    c = p.get('code', '')
                    btu_str = f" ({p.get('taglia_btu')} BTU)" if p.get('taglia_btu') else ""
                    comp_lines.append(f"{qty_map[c]} × {c}: {p.get('name', '')}{btu_str}")
                
                valid_cs = [c for c in cs if c in self.lookup or c in self.master_by_code]
                
                # HARD GATES: DA_VERIFICARE_VERSIONE, CONFIGURAZIONE_NON_CONFERMATA, conflitti bloccano sempre l'autocorrezione
                is_hard_gated = (
                    status in ['DA_VERIFICARE_VERSIONE', 'CONFIGURAZIONE_NON_CONFERMATA']
                    or any('Revisione/Generazione diversa' in r or 'Attacchi UE insufficienti' in r for r in reasons)
                )

                if is_hard_gated or score < self.AUTOCORRECT_THRESHOLD:
                    sugg = ""
                else:
                    sugg = "+".join(valid_cs)
                    if sugg:
                        self.validate_code_is_ac(sugg, row_idx=row_id)
                
                return MatchResult(
                    status=status,
                    confidence_score=f"{score}% ({status})",
                    score_value=score,
                    mpn_suggerito=sugg,
                    feedback='\n'.join(reasons) + ('\n--> Hard gate attivo: autocorrezione bloccata.' if is_hard_gated else ''),
                    componenti_db='\n'.join(list(dict.fromkeys(comp_lines))),
                    confronto_titolo_db=f"Brand: {bom.brand} | Serie: {bom.series} | UI: {bom.ui_btus}"
                )

            # DISCORDANZA CRITICA:
            # "Se non è coerente, ignora il match attuale e riesegui l'identificazione come se l'MPN fosse vuoto"
            cand_codes, cand_comps, cand_status, cand_score, cand_feedback = self.resolve_bom_from_catalog(bom)
            
            is_hard_gated = (
                cand_status in ['DA_VERIFICARE_VERSIONE', 'CONFIGURAZIONE_NON_CONFERMATA']
                or 'Autocorrezione bloccata' in cand_feedback
                or 'Attacchi UE insufficienti' in cand_feedback
                or 'non inferibile automaticamente' in cand_feedback
            )

            if cand_codes and cand_score >= self.AUTOCORRECT_THRESHOLD and not is_hard_gated:
                comp_lines = []
                for p in cand_comps:
                    btu_str = f" ({p.get('taglia_btu')} BTU)" if p.get('taglia_btu') else ""
                    comp_lines.append(f"{p.get('code')}: {p.get('name', '')}{btu_str}")

                fb = f"DISCORDANZA MPN ORIGINALE: {'; '.join(reasons)}\n--> Match errato ignorato. Risolti e proposti a catalogo i codici conformi alla BOM richiesta: {cand_feedback}"
                sugg = "+".join(cand_codes)
                self.validate_code_is_ac(sugg, row_idx=row_id)
                
                return MatchResult(
                    status='DISCORDANZA',
                    confidence_score=f"{cand_score}% (Correzione da BOM Catalogo)",
                    score_value=cand_score,
                    mpn_suggerito=sugg,
                    feedback=fb,
                    componenti_db='\n'.join(comp_lines),
                    confronto_titolo_db=f"Richiesti da titolo: Brand {bom.brand}, Serie {bom.series}, UI {bom.ui_btus}."
                )
            else:
                # Sotto soglia, fuori catalogo o bloccato da hard gate: NON inventare codici!
                comp_lines = []
                for p in cand_comps:
                    btu_str = f" ({p.get('taglia_btu')} BTU)" if p.get('taglia_btu') else ""
                    comp_lines.append(f"{p.get('code')}: {p.get('name', '')}{btu_str}")

                extra_note = "\n--> " + cand_feedback if cand_feedback else "\n--> Modello richiesto nel titolo non disponibile o fuori catalogo PT."
                return MatchResult(
                    status=cand_status if is_hard_gated else 'DISCORDANZA',
                    confidence_score=f"{cand_score}% ({cand_status})" if is_hard_gated else "0% (Serie Fuori Catalogo PT)",
                    score_value=cand_score if is_hard_gated else 0,
                    mpn_suggerito="",
                    feedback=f"DISCORDANZA MPN ORIGINALE: {'; '.join(reasons)}{extra_note}",
                    componenti_db='\n'.join(comp_lines),
                    confronto_titolo_db=f"Richiesti da titolo: Brand {bom.brand}, Serie {bom.series}."
                )

        # SE MPN È VUOTO:
        cand_codes, cand_comps, cand_status, cand_score, cand_feedback = self.resolve_bom_from_catalog(bom)
        
        # Penalità se accessorio mancante
        if 'STAFFA' in bom.accessories:
            cand_score = max(0, cand_score - 10)
            cand_status = 'DA VERIFICARE' if cand_status == 'COERENTE' else cand_status
            cand_feedback += " (Accessorio staffa citato nel titolo privo di codice MPN dedicato)."

        # HARD GATES VERIFICATION
        is_hard_gated = (
            cand_status in ['DA_VERIFICARE_VERSIONE', 'CONFIGURAZIONE_NON_CONFERMATA']
            or 'Autocorrezione bloccata' in cand_feedback
            or 'Attacchi UE insufficienti' in cand_feedback
            or 'non inferibile automaticamente' in cand_feedback
        )

        if is_hard_gated or cand_score < self.AUTOCORRECT_THRESHOLD:
            sugg = ""
        else:
            sugg = "+".join(cand_codes)
            if sugg:
                self.validate_code_is_ac(sugg, row_idx=row_id)
        
        comp_lines = []
        for p in cand_comps:
            btu_str = f" ({p.get('taglia_btu')} BTU)" if p.get('taglia_btu') else ""
            comp_lines.append(f"{p.get('code')}: {p.get('name', '')}{btu_str}")

        return MatchResult(
            status=cand_status,
            confidence_score=f"{cand_score}% ({cand_status if is_hard_gated else 'Risolto da Catalogo PT'})" if cand_score > 0 else "0% (Modello Fuori Catalogo PT)",
            score_value=cand_score,
            mpn_suggerito=sugg,
            feedback=cand_feedback,
            componenti_db='\n'.join(comp_lines),
            confronto_titolo_db=f"Brand: {bom.brand} | Serie: {bom.series} | UI attese: {bom.ui_btus}"
        )
