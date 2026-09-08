"""
extract_catalog_pdf_boilers.py
Estrazione sistematica delle specifiche ufficiali (kW) per tutte le Caldaie
del Catalogo Generale Puglia Termica 2026 nelle pagine 28 - 82.
Gli accessori situati nelle pagine intermedie vengono ignorati.
Regola di Dominio: LE CALDAIE SONO ESPRESSE RIGOROSAMENTE A KW (MAI A BTU).
"""

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
OUTPUT_BOILER_SPECS_PATH = "Knowledge/catalog_pdf_boiler_specs.json"

START_PAGE = 28
END_PAGE = 82

def is_boiler(it: Dict[str, Any]) -> bool:
    """Identifica se un articolo è una caldaia/generatore di calore, escludendo accessori e fumisteria."""
    name = (it.get("name") or "").upper().strip()
    cat = (it.get("category_path") or "").upper()

    # Prefissi inequivocabili di caldaie / generatori termici
    boiler_prefixes = [
        "CALD ", "CALDAIA ", "MODULO TERMICO ", "GRUPPO TERMICO ", "GENERATORE CALORE ", "GENERATORE TERMICO "
    ]
    if any(name.startswith(p) for p in boiler_prefixes):
        return True

    # Categorie esplicitamente accessorie da escludere
    if any(k in cat for k in ["ACCESSORI", "FUMISTERIA", "COMPONENTI", "TERMOREGOLAZIONE", "RADIATORI"]):
        return False

    # Prefissi accessori da escludere anche se situati in categorie generiche
    acc_prefixes = [
        "KIT ", "DIMA ", "SONDA ", "RACCORDO ", "FILTRO ", "VALVOLA ", "CRONOTERMOSTATO ", "TERMOSTATO ",
        "CURVA ", "PROLUNGA ", "SDOPPIATORE ", "COASSIALE ", "TERMINALE ", "BOX ", "ADATT", "ATTACCO ",
        "NEUTRALIZZATORE ", "DOSATORE ", "DEFANGATORE ", "COMANDO ", "SCHEDA ", "VASO ", "COLLETTORE ",
        "PANNELLO ", "INTERFACCIA ", "CAVO ", "TUBO ", "GUARNIZIONE ", "TAPPO ", "GRIGLIA ", "SIFONE "
    ]
    if any(name.startswith(p) for p in acc_prefixes):
        return False

    # Inclusione se in categorie di caldaie
    if any(k in cat for k in ["CALDAIE", "MURALI", "BASAMENTO", "CONDENSAZIONE"]):
        return True

    return False

def parse_kw_string(s: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Estrae potenza sanitario (max nominale) e potenza riscaldamento da una stringa tabella catalogo.
    Es. '20 A - 25 A' -> (25.0, 20.0) | '24 A - 28 A' -> (28.0, 24.0) | '32 A' -> (32.0, None)
    """
    if not s:
        return None, None
    s = s.replace('\xa0', ' ').strip()

    # 1. Pattern intervallo con trattino (es. 20 A - 25 A, 24 A - 28 A, 20 - 25)
    m_range = re.search(
        r'\b(\d{1,3}(?:[\.,]\d)?)\s*(?:[A-Za-z0-9\+\s]*)\s*[-/]\s*(\d{1,3}(?:[\.,]\d)?)\s*(?:[A-Za-z0-9\+\(\)]+|\bKW\b|\bkw\b|\bA\b|\bB\b|\bC\b)?',
        s
    )
    if m_range:
        v_heat = float(m_range.group(1).replace(',', '.'))
        v_san = float(m_range.group(2).replace(',', '.'))
        if 4.0 <= v_san <= 600.0:
            return v_san, v_heat

    # 2. Pattern valore singolo con classe o kW (es. '28 A', '32 A', '58,0 A', '35 kW')
    m_single = re.search(r'\b(\d{1,3}(?:[\.,]\d)?)\s*(?:[A-C]\b|\bKW\b|\bkw\b|\bA\b|\bB\b|\bC\b|\bHP\b)', s)
    if m_single:
        v = float(m_single.group(1).replace(',', '.'))
        if 4.0 <= v <= 600.0:
            return v, None

    return None, None

def extract_from_meas(meas_list: list) -> Tuple[Optional[float], Optional[float]]:
    """Estrae la taglia kW da catalog_measures (tabelle pre-estratte da PDF)."""
    for m in meas_list:
        v_san, v_heat = parse_kw_string(m)
        if v_san is not None:
            return v_san, v_heat
    return None, None

def extract_from_name(name: str) -> Tuple[Optional[float], Optional[float]]:
    """Estrae la taglia nominale kW dal nome modello caldaia."""
    n = name.upper()
    m_kw = re.search(r'\b(\d{1,3}(?:[\.,]\d)?)\s*(?:KW|kW)\b', n)
    if m_kw:
        return float(m_kw.group(1).replace(',', '.')), None

    m_num = re.search(r'\b(?:TOR|OPERA)\s+(\d{1,3})\b', n)
    if m_num:
        return float(m_num.group(1)), None

    m_wp = re.search(r'WP(\d{2,3})\b', n)
    if m_wp:
        return float(m_wp.group(1)), None

    m = re.search(
        r'\b(?:CALD|CALDAIA|CONDEXA|FBC|VICTRIX|CARES|ALTEAS|GENUS|CLAS|BLUEHELIX|START|CIAO|MYNUTE|EXCLUSIVE|FAMILY|METEO|RINNOVA|MURELLE|THELMA|ARES|HERCULES|MAIOR|SUPERIOR|ZEUS|AVIO|ECO|KOMPAKT|DIVA|ENERGY|LUNA|DUO-TEC|NUVOLA|PRIMA|PLATINUM|EVO|DOMUS|INSIEME|LOGAMAX|CONDENS)\s+.*?\b(\d{2,3})\b',
        n
    )
    if m:
        val = float(m.group(1))
        if 4.0 <= val <= 500.0:
            return val, None

    m2 = re.search(r'\b(1[4-9]|[2-9]\d|1\d{2})\s*(?:KW|C|KIS|IS|PLUS|MET|GPL|LN)?\b', n)
    if m2:
        val = float(m2.group(1))
        if 4.0 <= val <= 500.0:
            return val, None

    return None, None

def run_boiler_extraction():
    print("=======================================================================")
    print("  ESTRAZIONE SPECIFICHE UFFICIALI CALDAIE (PAGINE 28 - 82)            ")
    print("=======================================================================\n")

    if not os.path.exists(CATALOG_PDF_PATH):
        print(f"[ERRORE] Catalogo PDF non trovato: {CATALOG_PDF_PATH}")
        sys.exit(1)
    if not os.path.exists(MASTER_CATALOG_PATH):
        print(f"[ERRORE] Master catalog non trovato: {MASTER_CATALOG_PATH}")
        sys.exit(1)

    print("[1/4] Caricamento anagrafica e scansione tabelle e testi PDF...")
    with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
        master_list = json.load(f)

    # Identifica tutte le caldaie nel range 28-82 (escludendo gli accessori)
    boilers_in_scope = []
    accessories_in_scope = []
    for it in master_list:
        p = it.get("primary_page")
        if p and START_PAGE <= p <= END_PAGE:
            if is_boiler(it):
                boilers_in_scope.append(it)
            else:
                accessories_in_scope.append(it)

    print(f"      Articoli totali nelle pagine {START_PAGE}-{END_PAGE}: {len(boilers_in_scope) + len(accessories_in_scope)}")
    print(f"      • Caldaie identificate:   {len(boilers_in_scope)}")
    print(f"      • Accessori da ignorare:  {len(accessories_in_scope)}")

    # Scansione testo e tabelle PDF su pagine 28-82
    doc = pymupdf.open(CATALOG_PDF_PATH)
    pdf_page_specs = {}

    for pno in range(START_PAGE, END_PAGE + 1):
        page = doc[pno - 1]
        text = page.get_text("text")
        lines = [l.strip() for l in text.split("\n")]
        for i, line in enumerate(lines):
            m = re.search(r'\b(50\d{6}|99\d{6})\b', line)
            if m:
                code = m.group(1)
                after = line[m.end():].strip()
                v_san, v_heat = parse_kw_string(after)
                if v_san is None and i + 1 < len(lines):
                    v_san, v_heat = parse_kw_string(lines[i+1])
                if v_san is not None:
                    pdf_page_specs[code] = (v_san, v_heat, pno, line)

    print(f"      Estratti valori kW direttamente dalle righe PDF per {len(pdf_page_specs)} codici.")

    print("\n[2/4] Elaborazione specifiche caldaie con cascata a 3 livelli...")
    boiler_specs_dict = {}

    for it in boilers_in_scope:
        code = str(it.get("code")).strip()
        name = it.get("name") or ""
        mfg = str(it.get("mfg_code") or "").strip()
        p = it.get("primary_page")
        meas = it.get("catalog_measures") or []

        kw_san, kw_heat, source = None, None, None

        # Livello 1: Riconoscimento riga esatta tabella PDF
        if code in pdf_page_specs:
            kw_san, kw_heat, _, line_match = pdf_page_specs[code]
            source = "catalog_pdf_table_line"

        # Livello 2: Riconoscimento catalog_measures
        if kw_san is None:
            kw_san, kw_heat = extract_from_meas(meas)
            if kw_san is not None:
                source = "catalog_measures_table"

        # Livello 3: Riconoscimento modello/potenza
        if kw_san is None:
            kw_san, kw_heat = extract_from_name(name)
            if kw_san is not None:
                source = "catalog_model_name"

        if kw_san is not None:
            eff_kw = round(kw_san, 1)
            boiler_specs_dict[code] = {
                "code": code,
                "is_boiler": True,
                "is_ui": False,
                "is_ue": False,
                "kw": eff_kw,
                "kw_sanitario": eff_kw,
                "kw_riscaldamento": round(kw_heat, 1) if kw_heat else None,
                "tag_kw": f"{eff_kw:g} kW",
                "tag_kw_display": f"{eff_kw:g} kW",
                "btu": None,
                "tag_btu": None,
                "tag_btu_display": None,
                "tags": [f"{eff_kw:g} kW"],
                "page": p,
                "model_raw": mfg or name,
                "source": source
            }

    resolved_count = len(boiler_specs_dict)
    total_count = len(boilers_in_scope)
    print(f"      Caldaie con potenza kW determinata: {resolved_count} / {total_count} ({resolved_count/total_count*100:.1f}%)")

    print(f"\n[3/4] Salvataggio archivio specifiche caldaie in: {OUTPUT_BOILER_SPECS_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_BOILER_SPECS_PATH), exist_ok=True)
    with open(OUTPUT_BOILER_SPECS_PATH, "w", encoding="utf-8") as f:
        json.dump(boiler_specs_dict, f, ensure_ascii=False, indent=2)
    print(f"      File salvato con successo ({os.path.getsize(OUTPUT_BOILER_SPECS_PATH)} bytes).")

    print(f"\n[4/4] Sincronizzazione anagrafica master: {MASTER_CATALOG_PATH}...")
    updated_master_boilers = 0
    updated_master_acc = 0

    acc_codes_set = {str(it.get("code")).strip() for it in accessories_in_scope}

    for it in master_list:
        code = str(it.get("code") or "").strip()
        if code in boiler_specs_dict:
            spec = boiler_specs_dict[code]
            it["is_boiler"] = True
            it["taglia_kw"] = spec["kw"]
            it["tag_kw"] = spec["tag_kw"]
            it["tag_kw_display"] = spec["tag_kw_display"]
            it["tags"] = spec["tags"]
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            updated_master_boilers += 1
        elif code in acc_codes_set:
            it["is_boiler"] = False
            it["taglia_kw"] = None
            it["tag_kw"] = None
            it["tag_kw_display"] = None
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            updated_master_acc += 1

    with open(MASTER_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(master_list, f, ensure_ascii=False, indent=2)
    print(f"      Aggiornate {updated_master_boilers} Caldaie (con potenza kW) e {updated_master_acc} Accessori (puliti) in master.")

    # Verifica codici di test utente
    print("\n--- RISCONTRO TEST CODE FORNITI DALL'UTENTE ---")
    user_test_codes = [
        ("50350223", 25.0, "Ferroli CALD FBC 24C MET/GPL (Atteso: 25 kW)"),
        ("50350247", 28.0, "Ferroli CALD FBC 28C MET/GPL (Atteso: 28 kW)"),
        ("99482282", 28.0, "Immergas CALD VICTRIX MAIOR 28 TT MET (Atteso: 28 kW)"),
        ("50131235", 32.0, "Immergas CALD VICTRIX SUPERIOR 35 PLUS (Atteso: 32 kW)")
    ]

    all_user_ok = True
    for c, exp_kw, desc in user_test_codes:
        spec = boiler_specs_dict.get(c)
        if not spec:
            print(f" [NON TROVATO] {c}: {desc}")
            all_user_ok = False
        else:
            act_kw = spec.get("kw")
            status = "OK" if act_kw == exp_kw else "MISMATCH"
            if status != "OK": all_user_ok = False
            print(f" [{status}] {c}: {act_kw:g} kW (Tag: '{spec.get('tag_kw')}') | Fonte: {spec.get('source')} | {desc}")

    if all_user_ok:
        print("\n SUCCESSO TOTALE! TUTTI I CODICI DI TEST DELL'UTENTE RISULTANO ESATTI.")
    else:
        print("\n ATTENZIONE: DISCREPANZE RILEVATE SUI CODICI TEST.")

if __name__ == "__main__":
    run_boiler_extraction()
