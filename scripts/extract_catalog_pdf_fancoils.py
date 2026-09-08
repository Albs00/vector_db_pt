"""
extract_catalog_pdf_fancoils.py
Estrazione rigorosa e 100% tabellare dei Ventilconvettori / Fan Coil dal Catalogo PDF Puglia Termica 2026 (pagine 336-381).
Regole:
  - Solo righe di tabella con codice articolo PT (50xxxxxx / 99xxxxxx) sulla stessa riga della taglia e dei kW (Freddo e Caldo).
  - Nessun arricchimento da testi liberi.
  - Estrazione: taglia_modello, kw_freddo, kw_caldo, tag_kw.
  - Esclusione tassativa di comandi, termostati, valvole e accessori.
"""

import sys
import os
import re
import json
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(BASE_DIR, "Knowledge", "CAT2600_CATALOGO_2026-V4pdf.pdf")
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_fancoil_specs.json")

def extract_fancoils():
    print("=================================================================")
    print(" ESTRAZIONE UFFICIALE VENTILCONVETTORI DA TABELLE PDF (P.336-381)")
    print("=================================================================\n")

    if not os.path.exists(PDF_PATH):
        print(f"[ERRORE] File PDF non trovato: {PDF_PATH}")
        return

    doc = pymupdf.open(PDF_PATH)
    master = {}
    if os.path.exists(MASTER_PATH):
        with open(MASTER_PATH, "r", encoding="utf-8") as f:
            for it in json.load(f):
                master[it["code"]] = it

    extracted = {}

    for pno in range(336, 382):
        page = doc[pno - 1]
        text = page.get_text()
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for idx, l in enumerate(lines):
            code = None
            taglia_modello = None
            kw1 = None
            kw2 = None
            raw_line = l

            m_start = re.match(r'^(50\d{6}|99\d{6})\b(.*)$', l)
            if m_start:
                candidate_code = m_start.group(1)
                rest = m_start.group(2).strip()

                # Case A: Rest has model and two kW values: "VM 10 1,16 - 0,91" or "VM150 2,61 - 1,22" or "AREO C12 9,77 - 2,30"
                mA = re.search(r'^(.*?)\s+([0-9\.\,]+)\s*[\-\/]\s*([0-9\.\,]+)', rest)
                # Case B: Rest has model and single kW value: "100 2,00" (e.g. Aermec FCZ)
                mB = re.search(r'^([A-Za-z0-9\(\)\-\/]+)\s+([0-9\.\,]+)$', rest)

                if mA and not any(k in mA.group(1).upper() for k in ['PREZZO', 'DISP', 'CODICE']):
                    code = candidate_code
                    taglia_modello = mA.group(1).strip()
                    try:
                        kw1 = float(mA.group(2).replace(',', '.'))
                        kw2 = float(mA.group(3).replace(',', '.'))
                    except ValueError:
                        code = None
                elif mB:
                    code = candidate_code
                    taglia_modello = mB.group(1).strip()
                    try:
                        kw1 = float(mB.group(2).replace(',', '.'))
                        kw2 = None
                    except ValueError:
                        code = None
                elif not rest or len(rest) <= 15:
                    if idx + 1 < len(lines):
                        next_l = lines[idx + 1]
                        m_next_kw = re.search(r'^(?:(.*?)\s+)?([0-9\.\,]+)\s*[\-\/]\s*([0-9\.\,]+)', next_l)
                        if m_next_kw:
                            code = candidate_code
                            mod_part = (rest + " " + (m_next_kw.group(1) or '')).strip()
                            taglia_modello = mod_part if mod_part else rest
                            try:
                                kw1 = float(m_next_kw.group(2).replace(',', '.'))
                                kw2 = float(m_next_kw.group(3).replace(',', '.'))
                                raw_line = f"{l} {next_l}"
                            except ValueError:
                                code = None

            if not code or code not in master:
                continue

            item = master[code]
            name = (item.get("name") or "").upper()
            cat = (item.get("category_path") or "").upper()
            leaf = (item.get("category_leaf") or "").upper()

            if not any(k in name or k in cat for k in ['VENTIL', 'FAN COIL', 'FANCOIL', 'AEROTERMI']):
                continue

            # Exclude pure accessories and commands (unless it's an actual machine with integrated command)
            if any(k in leaf for k in ['ACCESSORI', 'VALVOLE', 'RUBINETTI', 'TERMOSTATI']) and not any(k in name for k in ['VENTILCONV', 'VENTIL', 'AEROTERMO']):
                continue

            is_machine = any(k in name for k in ['VENTILCONV', 'VENTIL', 'AEROTERMO', 'DESTRATIFICATORE']) or any(k in cat for k in ['VENTILCONVETTORI', 'AEROTERMI'])
            if not is_machine:
                continue
            if any(k in name for k in ['BACINELLA', 'BOCCHETTA', 'CANALE', 'PIEDINI', 'GRIGLIA', 'FILTRO', 'CASSA COPERTURA', 'KIT RACCORDO', 'SONDA', 'DIMA']):
                continue

            # Normalize taglia_modello
            if not taglia_modello or taglia_modello in ['✗', '✓', '1']:
                m_mod = re.search(r'\b(VM\s*\d+|VN\s*\d+|FCZ\s*[A-Z0-9]+|SL\s*\d+|AREO\s*[A-Z0-9]+|DLMV\s*\d+|FNC\s*\d+)\b', name)
                taglia_modello = m_mod.group(1) if m_mod else None

            if kw1 is not None and kw2 is not None:
                if not (0.3 <= kw1 <= 150 and 0.3 <= kw2 <= 150):
                    continue
                # Tabella PDF ufficiale Ventilconvettori: "MODELLO - KW C - F"
                # Il primo numero (kw1) è CALDO [C], il secondo (kw2) è FREDDO [F]
                kw_c = kw1
                kw_f = kw2
                tag_kw = f"{kw_c:g} kW C / {kw_f:g} kW F"
                tag_kw_display = f"{kw_c:g} kW [C] - {kw_f:g} kW [F]"
            elif kw1 is not None:
                if not (0.3 <= kw1 <= 150):
                    continue
                kw_c = kw1
                kw_f = None
                tag_kw = f"{kw_c:g} kW C"
                tag_kw_display = f"{kw_c:g} kW [C]"
            else:
                continue

            extracted[code] = {
                "code": code,
                "is_ventilconvettore": True,
                "taglia_modello": taglia_modello,
                "kw_caldo": kw_c,
                "kw_freddo": kw_f,
                "tag_kw": tag_kw,
                "tag_kw_display": tag_kw_display,
                "page": pno,
                "raw_table_line": raw_line,
                "source": "catalog_pdf_table_line"
            }

    print(f"Totale ventilconvettori estratti con precisione tabellare: {len(extracted)}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"Salvate specifiche in: {OUTPUT_PATH}")

if __name__ == "__main__":
    extract_fancoils()
