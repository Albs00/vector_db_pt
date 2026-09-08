import os
import sys
import re
import json
import pymupdf
from typing import Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

CATALOG_PDF_PATH = "Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf"
MASTER_CATALOG_PATH = "Knowledge/unified_catalog_master.json"
OUTPUT_SPECS_PATH = "Knowledge/catalog_pdf_extracted_specs.json"

# Intervallo completo sezione climatizzazione catalogo Puglia Termica 2026
START_PAGE = 468
END_PAGE = 628

def is_outdoor_unit(name: str = "", mfg_code: str = "") -> bool:
    """Rileva se un articolo è una Unità Esterna (UE)"""
    n = (name or "").upper()
    m = (mfg_code or "").upper()
    if any(k in n for k in ["UI ", "UNITA INTERNA", "UNITA' INTERNA", "S/UE", "SENZA UNIT", "SENZA UNITA", "MONOBLOCCO"]):
        return False
    if any(n.startswith(p) or f" {p}" in n for p in ["UE ", "U.E. ", "UNITA ESTERNA", "UNITA' ESTERNA", "MOTOCONDENSANTE"]):
        return True
    if any(m.startswith(p) for p in ["1U", "2MXM", "3MXM", "4MXM", "5MXM", "MXZ-", "CU-", "AJ0", "AJ1", "RXJ", "RXM"]):
        return True
    return False

def kw_to_nominal_btu(kw: float, name: str = "", mfg_code: str = "", code: str = "") -> int:
    """
    Converte la potenza frigorifera nominale (kW) nella taglia commerciale standard BTU/h (solo per UI/Kit).
    Riconosce le taglie commerciali (es. 18.000 BTU basate su potenza max o modello 50/500/18).
    """
    full_text = f"{name} {mfg_code}".upper()

    # Regola esplicita: 50276639 (Bosch Climate 7000i 41ES Silver) resta 15000 BTU
    if code == "50276639":
        return 15000

    # Taglie 50 / 500 / 18 vendute commercialmente come 18000 BTU (es. 50117819 SPG500W, MLG500F, MSZ-BT50, SLZ-M50, KP50, PKA-M50, AS50, HEC50, RZGNP 50, UIKOCAN18, CL18)
    if any(k in full_text for k in [
        "SPG500", "MLG500", "SGE500", "500W", "500F",
        "CANALIZZ 18000", "CANALIZZATO 18000", "CASSETTA 18000", "CONSOLE 18000", "UIKOCAN18", "UIKOCAS18", "UIKOCON18",
        "CL18F", "CL18",
        "MSZ-BT50", "BT50", "SLZ-M50", "MLZ-KP50", "KP50", "PKA-M 50", "PKA-M50",
        "AS50", "HEC50", "RZGNP 50", "RZGNP50"
    ]):
        return 18000

    # Correzioni anomalie tabelle multisplit
    if "AS25" in full_text:
        return 9000
    if "FTXC35" in full_text:
        return 12000

    # Modelli specifici taglia 15000 (Bosch 41, Samsung 15, Toshiba 16, Argo 15000)
    if any(k in full_text for k in ["41 E", "41E", "41 EB", "41EB", "41 ES", "41ES", "AR50F15", "AR70F15", "AR70H15", "RAS-B16", "RASB16", "15000"]):
        return 15000

    if kw <= 2.29:
        return 7000
    elif kw <= 2.99:
        return 9000
    elif kw <= 3.99:
        return 12000
    elif kw <= 4.79:
        return 15000
    elif kw <= 5.89:
        return 18000
    elif kw <= 6.79:
        return 21000
    elif kw <= 7.89:
        return 24000
    elif kw <= 8.89:
        return 28000
    elif kw <= 11.09:
        return 36000
    elif kw <= 13.09:
        return 42000
    elif kw <= 15.09:
        return 48000
    elif kw <= 19.09:
        return 60000
    else:
        return int(round(kw * 3.412142)) * 1000

def parse_kw_cell(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Estrae potenza frigorifera (cooling) e riscaldamento (heating) da una cella o testo.
    """
    if not text:
        return None, None
    
    s = str(text).replace('\xa0', ' ').strip()
    
    # 1. Caso esplicito Freddo / Caldo con F / C
    m_fc = re.search(r'[Ff]\s*(\d{1,2}[\.,]\d{1,2})', s)
    m_cc = re.search(r'[Cc]\s*(\d{1,2}[\.,]\d{1,2})', s)
    if m_fc:
        kf = float(m_fc.group(1).replace(',', '.'))
        kc = float(m_cc.group(1).replace(',', '.')) if m_cc else None
        return kf, kc
    if m_cc and not m_fc:
        kc = float(m_cc.group(1).replace(',', '.'))
        return None, kc
    
    # 2. Caso intervallo con o senza classi energetiche (es. '2,35 (A) - 2,36 (A)', '2,0 A - 2,0 B', '3,5 - 4,0')
    m_range = re.search(r'\b(\d{1,2}[\.,]\d{1,2})\s*(?:\([A-Za-z0-9\+\s]+\)|[A-Za-z0-9\+]+)?\s*[-/]\s*(\d{1,2}[\.,]\d{1,2})', s)
    if m_range:
        v1 = float(m_range.group(1).replace(',', '.'))
        v2 = float(m_range.group(2).replace(',', '.'))
        if 0.8 <= v1 <= 35.0 and 0.8 <= v2 <= 40.0:
            return v1, v2

    # 3. Caso valore singolo con classe energetica (es. '3,5 (A)', '2,7 (A)', '3,7 (A)')
    m_single_class = re.search(r'\b(\d{1,2}[\.,]\d{1,2})\s*\([A-Za-z0-9\+\s]+\)', s)
    if m_single_class:
        v = float(m_single_class.group(1).replace(',', '.'))
        if 0.8 <= v <= 35.0:
            return v, None
            
    # 4. Caso esplicito kW: '3,5 kW' o '3.5kW'
    m_kw = re.search(r'\b(\d{1,2}[\.,]\d{1,2})\s*(?:KW|kW)\b', s)
    if m_kw:
        v = float(m_kw.group(1).replace(',', '.'))
        if 0.8 <= v <= 35.0:
            return v, None
            
    return None, None

def extract_all_catalog_specs() -> Dict[str, Dict[str, Any]]:
    print(f"[1/4] Scansione tabelle e testi PDF: {CATALOG_PDF_PATH} (pag. {START_PAGE} - {END_PAGE})...")
    if not os.path.exists(CATALOG_PDF_PATH):
        print(f"[ERRORE] File PDF catalogo non trovato in: {CATALOG_PDF_PATH}")
        return {}

    # Carica anagrafica master per lookup nomi/modelli durante la scansione
    master_by_code = {}
    if os.path.exists(MASTER_CATALOG_PATH):
        with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
            m_list = json.load(f)
            master_by_code = {str(it.get("code")).strip(): it for it in m_list if it.get("code")}

    doc = pymupdf.open(CATALOG_PDF_PATH)
    all_specs = {}

    for pno in range(START_PAGE - 1, END_PAGE):
        page = doc[pno]
        page_num = pno + 1
        text = page.get_text()

        # A. Riconoscimento tabelle multisplit senza bordi grafici (UE: solo kW e porte attacchi, NO BTU)
        for code, taglia_str, ports in re.findall(r'(50\d{6}|99\d{6})\s*\n\s*(\d{2,3})\s*[-/]\s*(\d)\b', text):
            kw_val = float(taglia_str)/10.0 if float(taglia_str) >= 20 else float(taglia_str)
            if code not in all_specs:
                all_specs[code] = {
                    "code": code,
                    "is_ue": True,
                    "is_ui": False,
                    "kw": kw_val,
                    "kw_cooling": kw_val,
                    "kw_heating": None,
                    "tag_kw": f"{kw_val} kW",
                    "tag_kw_display": f"{kw_val} kW",
                    "btu": None,
                    "tag_btu": None,
                    "tag_btu_display": None,
                    "tags": [f"{kw_val} kW", f"{ports} attacchi"],
                    "page": page_num,
                    "ports": int(ports),
                    "model_raw": f"Multi {ports} attacchi",
                    "source": "pdf_borderless_multisplit_table"
                }

        # B. Riconoscimento tabelle tabulari con pair-awareness UI / UE
        tabs = page.find_tables()
        if not tabs.tables:
            continue

        for tab in tabs.tables:
            rows = tab.extract()
            last_ui_kw = None
            
            for r in rows:
                if not r:
                    continue
                row_str = " | ".join([str(c) for c in r if c is not None])
                
                # Trova tutti i codici articolo PT (7 o 8 cifre)
                codes = re.findall(r'\b(50\d{6}|99\d{6}|20\d{6})\b', row_str)
                if not codes:
                    continue

                is_ui_row = any('U.I.' in str(c) or 'UI ' in str(c) for c in r[:2])
                is_ue_row = any('U.E.' in str(c) or 'UE ' in str(c) for c in r[:2])

                kw_cooling = None
                kw_heating = None
                
                for cell in r:
                    if not cell:
                        continue
                    kf, kh = parse_kw_cell(cell)
                    if kf is not None or kh is not None:
                        kw_cooling = kf
                        kw_heating = kh
                        break

                if is_ui_row and kw_cooling is not None:
                    last_ui_kw = (kw_cooling, kw_heating)
                    source_type = "pdf_table_ui"
                elif is_ue_row:
                    if kw_cooling is not None:
                        source_type = "pdf_table_ue_explicit"
                    elif last_ui_kw is not None:
                        kw_cooling = last_ui_kw[0]
                        if kw_heating is None:
                            kw_heating = last_ui_kw[1]
                        source_type = "pdf_table_ue_paired"
                    else:
                        source_type = "pdf_table_ue"
                else:
                    source_type = "pdf_table"

                model_str = ""
                for cell in r[:3]:
                    if not cell:
                        continue
                    cs = str(cell).strip()
                    if not re.fullmatch(r'\d+', cs) and not re.search(r'^\d+[\.,]\d+$', cs):
                        model_str = cs
                        break

                if kw_cooling is not None:
                    for code in codes:
                        if code not in all_specs:
                            it_meta = master_by_code.get(code, {})
                            it_name = it_meta.get("name") or model_str
                            it_mfg = it_meta.get("mfg_code") or ""
                            
                            is_ue = is_ue_row or is_outdoor_unit(it_name, it_mfg)
                            
                            if is_ue:
                                # REGOLE CHIAVE: LE UE SONO A KW, NON A BTU
                                all_specs[code] = {
                                    "code": code,
                                    "is_ue": True,
                                    "is_ui": False,
                                    "kw": kw_cooling,
                                    "kw_cooling": kw_cooling,
                                    "kw_heating": kw_heating,
                                    "tag_kw": f"{kw_cooling} kW",
                                    "tag_kw_display": f"{kw_cooling} kW",
                                    "btu": None,
                                    "tag_btu": None,
                                    "tag_btu_display": None,
                                    "tags": [f"{kw_cooling} kW"],
                                    "page": page_num,
                                    "model_raw": model_str,
                                    "source": source_type
                                }
                            else:
                                btu_nominal = kw_to_nominal_btu(kw_cooling, it_name, it_mfg, code)
                                all_specs[code] = {
                                    "code": code,
                                    "is_ue": False,
                                    "is_ui": True,
                                    "kw": kw_cooling,
                                    "kw_cooling": kw_cooling,
                                    "kw_heating": kw_heating,
                                    "btu": btu_nominal,
                                    "tag_btu": f"{btu_nominal} btu",
                                    "tag_btu_display": f"{btu_nominal} BTU",
                                    "tags": [f"{btu_nominal} btu", f"{btu_nominal} BTU", f"{kw_cooling} kW"],
                                    "page": page_num,
                                    "model_raw": model_str,
                                    "source": source_type
                                }

    print(f"      Estratti {len(all_specs)} codici dalle tabelle e schemi PDF.")
    return all_specs

def enrich_from_catalog_measures(specs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    print(f"[2/4] Integrazione con catalog_measures da anagrafica: {MASTER_CATALOG_PATH}...")
    if not os.path.exists(MASTER_CATALOG_PATH):
        return specs

    with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    added = 0
    for it in master_data:
        code = str(it.get("code") or "").strip()
        if not code or code in specs:
            continue

        meas_list = it.get("catalog_measures") or []
        if not meas_list:
            continue

        kw_cooling = None
        kw_heating = None
        for meas in meas_list:
            kf, kh = parse_kw_cell(meas)
            if kf is not None:
                kw_cooling = kf
                kw_heating = kh
                break

        if kw_cooling is not None:
            it_name = it.get("name") or ""
            it_mfg = it.get("mfg_code") or ""
            page = it.get("primary_page")
            is_ue = is_outdoor_unit(it_name, it_mfg)

            if is_ue:
                specs[code] = {
                    "code": code,
                    "is_ue": True,
                    "is_ui": False,
                    "kw": kw_cooling,
                    "kw_cooling": kw_cooling,
                    "kw_heating": kw_heating,
                    "tag_kw": f"{kw_cooling} kW",
                    "tag_kw_display": f"{kw_cooling} kW",
                    "btu": None,
                    "tag_btu": None,
                    "tag_btu_display": None,
                    "tags": [f"{kw_cooling} kW"],
                    "page": page,
                    "model_raw": it_mfg or it_name,
                    "source": "catalog_measures_ue"
                }
            else:
                btu_nominal = kw_to_nominal_btu(kw_cooling, it_name, it_mfg, code)
                specs[code] = {
                    "code": code,
                    "is_ue": False,
                    "is_ui": True,
                    "kw": kw_cooling,
                    "kw_cooling": kw_cooling,
                    "kw_heating": kw_heating,
                    "btu": btu_nominal,
                    "tag_btu": f"{btu_nominal} btu",
                    "tag_btu_display": f"{btu_nominal} BTU",
                    "tags": [f"{btu_nominal} btu", f"{btu_nominal} BTU", f"{kw_cooling} kW"],
                    "page": page,
                    "model_raw": it_mfg or it_name,
                    "source": "catalog_measures_ui"
                }
            added += 1

    print(f"      Aggiunti ulteriori {added} codici da catalog_measures.")
    return specs

def enrich_all_in_scope_ac_units(specs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    print(f"[3/4] Copertura 100% di tutte le macchine di condizionamento nelle pagine {START_PAGE}-{END_PAGE}...")
    with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    from build_full_ac_matrix import extract_btu_and_kw

    added_units = 0
    for it in master_data:
        code = str(it.get("code") or "").strip()
        if not code or code in specs:
            continue

        p = it.get("primary_page")
        pages = it.get("catalog_pages") or []
        is_in_page_range = (p and START_PAGE <= p <= END_PAGE) or any(START_PAGE <= pg <= END_PAGE for pg in pages)
        if not is_in_page_range:
            continue

        cat = it.get("category_path") or ""
        name = (it.get("name") or "").upper()
        mfg = str(it.get("mfg_code") or "").strip().upper()

        is_ac_machine = (
            any(k in cat for k in ["RESIDENZIALI", "COMMERCIALI", "SENZA UNITÀ ESTERNA", "PORTATILI"]) or
            any(k in name for k in ["UI ", "UE ", "UNITA INTERNA", "UNITA ESTERNA", "CLIMATIZZ", "SPLIT", "S/UE", "PORTATILE"])
        )
        is_accessory = (
            "ACCESSORI" in cat or
            any(k in name for k in ["COMANDO A FILO", "INTERFACCIA", "PANNELLO DECORATIVO", "GRIGLIA", "SCHEDA WIFI", "MODULO WI-FI", "KIT WI-FI"])
        )

        if is_ac_machine and not is_accessory:
            btu_val, kw_val = extract_btu_and_kw(name, mfg)
            if btu_val or kw_val:
                eff_kw = kw_val or round(btu_val / 3412.142, 1)
                is_ue = is_outdoor_unit(name, mfg)

                if is_ue:
                    specs[code] = {
                        "code": code,
                        "is_ue": True,
                        "is_ui": False,
                        "kw": eff_kw,
                        "kw_cooling": eff_kw,
                        "kw_heating": None,
                        "tag_kw": f"{eff_kw} kW",
                        "tag_kw_display": f"{eff_kw} kW",
                        "btu": None,
                        "tag_btu": None,
                        "tag_btu_display": None,
                        "tags": [f"{eff_kw} kW"],
                        "page": p,
                        "model_raw": mfg or name,
                        "source": "catalog_product_specs_ue"
                    }
                else:
                    eff_btu = btu_val or kw_to_nominal_btu(eff_kw, name, mfg, code)
                    specs[code] = {
                        "code": code,
                        "is_ue": False,
                        "is_ui": True,
                        "kw": eff_kw,
                        "kw_cooling": eff_kw,
                        "kw_heating": None,
                        "btu": eff_btu,
                        "tag_btu": f"{eff_btu} btu",
                        "tag_btu_display": f"{eff_btu} BTU",
                        "tags": [f"{eff_btu} btu", f"{eff_btu} BTU", f"{eff_kw} kW"],
                        "page": p,
                        "model_raw": mfg or name,
                        "source": "catalog_product_specs_ui"
                    }
                added_units += 1

    print(f"      Integrate ulteriori {added_units} unità residue di condizionamento censite a catalogo.")
    print(f"      TOTALE COMPLESSIVO CODICI SPECIFICHE CLIMA: {len(specs)}")
    return specs

def save_and_verify(specs: Dict[str, Dict[str, Any]]):
    print(f"[4/4] Salvataggio archivio specifiche ufficiali in: {OUTPUT_SPECS_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_SPECS_PATH), exist_ok=True)
    with open(OUTPUT_SPECS_PATH, "w", encoding="utf-8") as f:
        json.dump(specs, f, ensure_ascii=False, indent=2)
    print(f"      File salvato con successo ({os.path.getsize(OUTPUT_SPECS_PATH)} bytes).")

    # Sincronizzazione rigorosa in unified_catalog_master.json:
    # UE: is_ue=True, is_ui=False, taglia_btu=None, tag_btu=None, taglia_kw=kw, tag_kw="X.X kW"
    # UI: is_ui=True, is_ue=False, taglia_btu=btu, tag_btu="XXXX btu", taglia_kw=kw
    print(f"      Sincronizzazione anagrafica {MASTER_CATALOG_PATH}...")
    with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
        master_list = json.load(f)

    updated_in_master = 0
    for it in master_list:
        code = str(it.get("code") or "").strip()
        name = (it.get("name") or "").upper()
        cat = (it.get("category_path") or "").upper()
        mfg = (it.get("mfg_code") or "").upper()

        is_acc = "ACCESSORI" in cat or any(k in name for k in ["COMANDO A FILO", "INTERFACCIA", "PANNELLO DECORATIVO", "GRIGLIA", "SCHEDA WIFI", "MODULO WI-FI", "KIT WI-FI"])
        if is_acc:
            continue

        is_sue = "S/UE" in name or "SENZA UNIT" in name or "SENZA UNITA" in name or "MONOBLOCCO" in name
        is_ue = is_outdoor_unit(name, mfg) and not is_sue
        is_ui = (any(name.startswith(p) or f" {p}" in name for p in ["UI ", "U.I. ", "UNITA INTERNA", "UNITA' INTERNA"]) or is_sue or ("SPLIT" in name and not is_ue))

        if code in specs:
            spec = specs[code]
            if spec.get("is_ue"):
                it["is_ue"] = True
                it["is_ui"] = False
                it["taglia_btu"] = None
                it["tag_btu"] = None
                it["tag_btu_display"] = None
                it["taglia_kw"] = spec.get("kw")
                it["tag_kw"] = f"{spec.get('kw')} kW"
                it["tag_kw_display"] = f"{spec.get('kw')} kW"
                it["tags"] = [f"{spec.get('kw')} kW"]
                updated_in_master += 1
            elif spec.get("is_ui"):
                it["is_ui"] = True
                it["is_ue"] = False
                it["taglia_btu"] = spec.get("btu")
                it["tag_btu"] = spec.get("tag_btu")
                it["tag_btu_display"] = spec.get("tag_btu_display")
                it["taglia_kw"] = spec.get("kw")
                it["tags"] = spec.get("tags", [])
                updated_in_master += 1
        else:
            if is_ue:
                it["is_ue"] = True
                it["is_ui"] = False
                it["taglia_btu"] = None
                it["tag_btu"] = None
                it["tag_btu_display"] = None
                if it.get("taglia_kw"):
                    it["tag_kw"] = f"{it['taglia_kw']} kW"
                    it["tag_kw_display"] = f"{it['taglia_kw']} kW"
                    it["tags"] = [f"{it['taglia_kw']} kW"]
                updated_in_master += 1

    with open(MASTER_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(master_list, f, ensure_ascii=False, indent=2)
    print(f"      Aggiornati {updated_in_master} articoli in {MASTER_CATALOG_PATH}.")

    # Verifica codici test estesi
    # REGOLA: per UI -> verifichiamo BTU e kW. Per UE -> verifichiamo SOLO kW e che BTU sia None!
    test_cases = [
        # UI
        ("50367764", "UI", 12000, 3.5, "Samsung AR70F12C1ABNEU (UI)"),
        ("50117246", "UI", 18000, 5.0, "Panasonic S-50PY3E (UI)"),
        ("50117260", "UI", 21000, 6.0, "Panasonic S-60PY3E (UI)"),
        ("50117222", "UI", 9000, 2.5, "Panasonic S-25PY3E (UI)"),
        ("99786793", "UI", 24000, 7.1, "Olimpia Splendid AMK 70 P (UI)"),
        ("50332632", "UI", 36000, 9.2, "Olimpia Splendid AMK 100 P (UI)"),
        ("50328000", "UI", 12000, 3.5, "Olimpia Splendid AMW 35 PI (UI)"),
        ("50328017", "UI", 18000, 5.0, "Olimpia Splendid AMW 50 PI (UI)"),
        ("50327997", "UI", 9000, 2.8, "Olimpia Splendid AMW 25 PI (UI)"),
        ("50223671", "UI", 12000, 3.5, "Midea MFA2U-12HRFNX (UI)"),
        ("50223688", "UI", 18000, 5.0, "Midea MFA2U-17HRFNX (UI)"),
        ("50227525", "UI", 12000, 3.6, "Midea MSCB1BU-12HRFN8 (UI)"),
        ("50290178", "UI", 12000, 3.2, "Midea MSAGBU-12HRFN8 (UI)"),
        ("50474202", "UI", 18000, 5.3, "Midea CB1-18HRFN8-I (UI)"),
        ("50129492", "UI", 12000, 3.5, "Midea MSAGBU-12HRFN8/GR (UI)"),
        # UE (SOLO KW, NO BTU!)
        ("50376339", "UE", None, 7.0, "Midea UE MOX430U-24 (UE - 7.0 kW)"),
        ("50131273", "UE", None, 2.6, "Haier UE 1U25S2SM1FA-2 (UE - 2.6 kW)"),
        ("50115723", "UE", None, 3.5, "Hisense UE 2AMW35U4RGC (UE - 3.5 kW Multi)"),
        ("50238996", "UE", None, 5.5, "Riello UE AARIA MULTI 355 PI (UE - 5.5 kW Multi)")
    ]

    print("\n--- RISULTATO VERIFICA CODICI: UI A BTU/KW, UE RIGOROSAMENTE A KW ---")
    all_ok = True
    for code, unit_type, exp_btu, exp_kw, desc in test_cases:
        spec = specs.get(code)
        if not spec:
            print(f" [NON TROVATO] {code}: {desc}")
            all_ok = False
        else:
            actual_kw = spec.get("kw")
            actual_btu = spec.get("btu")
            is_ue = spec.get("is_ue", False)

            if unit_type == "UE":
                # Per UE: BTU DEVE essere None, kw deve corrispondere
                ok_kw = (actual_kw == exp_kw)
                ok_no_btu = (actual_btu is None)
                status = "OK" if (ok_kw and ok_no_btu and is_ue) else "MISMATCH"
                if status != "OK": all_ok = False
                print(f" [{status}] {code} (UE): {actual_kw} kW | tag_kw='{spec.get('tag_kw')}' | btu={actual_btu} (Atteso: {exp_kw} kW, NO BTU) | {desc}")
            else:
                # Per UI: BTU e kw devono corrispondere
                status = "OK" if (actual_btu == exp_btu and actual_kw == exp_kw) else "MISMATCH"
                if status != "OK": all_ok = False
                print(f" [{status}] {code} (UI): {actual_btu} BTU ({actual_kw} kW) (Atteso: {exp_btu} BTU / {exp_kw} kW) | {desc}")

    if all_ok:
        print("\n TUTTI I CODICI DI TEST RISPETTANO LA REGOLA: UI A BTU/KW, UE A KW SENZA BTU!")
    else:
        print("\n ALCUNI CODICI PRESENTANO DISCREPANZE.")

if __name__ == "__main__":
    s = extract_all_catalog_specs()
    s = enrich_from_catalog_measures(s)
    s = enrich_all_in_scope_ac_units(s)
    save_and_verify(s)
