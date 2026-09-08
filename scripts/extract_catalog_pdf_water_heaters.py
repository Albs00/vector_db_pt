"""
extract_catalog_pdf_water_heaters.py
Estrazione rigorosa e 100% tabellare degli Scaldabagni dal Catalogo PDF Puglia Termica 2026 (pagine 112-145).
Regole:
  - Solo righe di tabella con codice articolo PT (50xxxxxx / 99xxxxxx) sulla stessa riga della misura/litri.
  - Nessun arricchimento da testi liberi.
  - Estrazione: litri, combustibile (METANO/GPL), camera (stagna/aperta), tipologia (elettrico/gas/pompa di calore).
  - Esclusione tassativa di ricambi e accessori (resistenze, termostati, kit fumi, flange, ecc.).
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
OUTPUT_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_water_heater_specs.json")

def extract_water_heaters():
    print("=================================================================")
    print(" ESTRAZIONE UFFICIALE SCALDABAGNI DA TABELLE PDF (PAGINE 112-145)")
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

    for pno in range(112, 146):
        page = doc[pno - 1]
        text = page.get_text()
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        header_text = ' '.join(lines[:15]).upper()
        is_cs = any(k in header_text for k in ['CAMERA STAGNA', ' C/S', 'TURBOMAG', 'KONA', 'INFINITY', 'OPALIA F', 'FAST EVO X', 'MINI LN'])
        is_ca = any(k in header_text for k in ['CAMERA APERTA', ' C/A', 'ATMOMAG', 'PEGASO', 'OPALIA C', 'FAST R'])

        for idx, l in enumerate(lines):
            code = None
            val1 = None
            val2 = ''
            raw_line = l

            m1 = re.match(r'^(50\d{6}|99\d{6})\s+(?:(?:dx|sx)\s*[\-\/]\s*)?([0-9\.\,]+)\s*(?:[\/\-]\s*([A-Za-z0-9]+))?', l, re.I)
            m2 = re.match(r'^(50\d{6}|99\d{6})\s+([0-9\.\,]+)\s*\-\s*(met|gpl)', l, re.I)

            if m1:
                code = m1.group(1)
                val1 = m1.group(2)
                val2 = (m1.group(3) or '').upper()
            elif m2:
                code = m2.group(1)
                val1 = m2.group(2)
                val2 = m2.group(3).upper()
            elif re.match(r'^(50\d{6}|99\d{6})$', l) and idx + 1 < len(lines):
                next_l = lines[idx + 1]
                m_next1 = re.match(r'^(?:(?:dx|sx)\s*[\-\/]\s*)?([0-9\.\,]+)\s*(?:[\/\-]\s*([A-Za-z0-9]+))?', next_l, re.I)
                m_next2 = re.match(r'^([0-9\.\,]+)\s*\-\s*(met|gpl)', next_l, re.I)
                if m_next2:
                    code = l
                    val1 = m_next2.group(1)
                    val2 = m_next2.group(2).upper()
                    raw_line = f"{l} {next_l}"
                elif m_next1:
                    try:
                        test_num = float(m_next1.group(1).replace(',', '.'))
                        if test_num <= 1000:
                            code = l
                            val1 = m_next1.group(1)
                            val2 = (m_next1.group(2) or '').upper()
                            raw_line = f"{l} {next_l}"
                    except ValueError:
                        pass

            if not code or code not in master:
                continue

            item = master[code]
            name = (item.get("name") or "").upper()
            cat = (item.get("category_path") or "").upper()
            leaf = (item.get("category_leaf") or "").upper()

            if not ('SCALD' in name or 'SCALD' in cat):
                continue

            if any(k in leaf for k in ['ACCESSORI', 'RUBINETTI', 'GUARNIZIONI', 'NON ORIGINALI']):
                continue
            if any(k in name for k in ['RESIST', 'TERMOST', 'VALVOLA', 'KIT', 'RACCORD', 'DIMA', 'SONDA', 'PIEDINI', 'COLLARE', 'ESALATORE', 'COASSIALE', 'SDOPPIATO', 'FLANGIA', 'ANODO', 'GUAINA', 'GRUPPO DI SICUREZZA', 'GRUPPO SICUR']):
                continue

            try:
                litri = float(val1.replace(',', '.'))
            except (ValueError, TypeError):
                continue

            if litri > 1000:
                continue

            gas = None
            if 'MET' in val2 or 'MET' in name:
                gas = 'METANO'
            elif 'GPL' in val2 or 'GPL' in name:
                gas = 'GPL'

            tipo = 'ELETTRICO'
            if 'GAS' in name or 'GAS' in cat or gas is not None or is_cs or is_ca:
                tipo = 'GAS_ISTANTANEO'
            if 'POMPA DI CALORE' in cat or 'NUOS' in name or 'CALYPSO' in name:
                tipo = 'POMPA_DI_CALORE'
            if 'LEGNA' in name or 'LEGNA' in cat:
                tipo = 'LEGNA'

            camera = None
            if tipo == 'GAS_ISTANTANEO':
                if is_cs or 'CS' in name or 'STAGNA' in name or 'OPALIA F' in name:
                    camera = 'CAMERA_STAGNA'
                elif is_ca or 'CA' in name or 'APERTA' in name or 'OPALIA C' in name:
                    camera = 'CAMERA_APERTA'

            tag_litri = f"{int(litri) if litri.is_integer() else litri} L"

            extracted[code] = {
                "code": code,
                "is_scaldabagno": True,
                "capacita_litri": litri,
                "tag_litri": tag_litri,
                "gas": gas,
                "tipo_scaldabagno": tipo,
                "camera": camera,
                "page": pno,
                "raw_table_line": raw_line,
                "source": "catalog_pdf_table_line"
            }

    print(f"Totale scaldabagni estratti con precisione tabellare: {len(extracted)}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"Salvate specifiche in: {OUTPUT_PATH}")

if __name__ == "__main__":
    extract_water_heaters()
