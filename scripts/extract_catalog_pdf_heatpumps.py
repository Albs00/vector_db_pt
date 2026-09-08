"""
extract_catalog_pdf_heatpumps.py
Estrazione rigorosa e tabellare delle Pompe di Calore e Sistemi Ibridi dal Catalogo PDF Puglia Termica 2026.
Regole:
  - Estrazione multi-fase:
    1. Misure tabellari strutturate (catalog_measures)
    2. Parsing riga per riga dalle tabelle del PDF ufficiale (pagine 674 - 761)
  - Estrazione dei KW [F - C] (Freddo e Caldo): es. 50121113 -> 15.0 kW Freddo / 16.0 kW Caldo.
  - Estrazione dei sistemi ibridi gas+pdc (es. 24 kW metano / 32 kW gpl).
  - Estrazione di eventuali litri accumulo (es. 150 L, 200 L) e tubazioni frigorifere.
  - Esclusione tassativa di BTU: nessuna pompa di calore riceve taglia_btu.
"""

import sys
import os
import re
import json
import pymupdf

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
PDF_PATH = os.path.join(BASE_DIR, "Knowledge", "CAT2600_CATALOGO_2026-V4pdf.pdf")
OUTPUT_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_heatpump_specs.json")

def extract_heatpumps():
    print("=================================================================")
    print(" ESTRAZIONE UFFICIALE POMPE DI CALORE DA TABELLE E MISURE PDF    ")
    print("=================================================================\n")

    if not os.path.exists(MASTER_PATH):
        print(f"[ERRORE] File non trovato: {MASTER_PATH}")
        return

    with open(MASTER_PATH, "r", encoding="utf-8") as f:
        master_list = json.load(f)
    master = {it["code"]: it for it in master_list}

    extracted = {}

    # FASE 1: Estrazione da catalog_measures esistente
    print("Fase 1: scansione catalog_measures...")
    pdc_items = [
        x for x in master_list 
        if 'POMPE DI CALORE' in (x.get('category_path') or '').upper() or 
           'SISTEMI IBRIDI' in (x.get('category_path') or '').upper() or
           any(k in (x.get('name') or '').upper() for k in ['P/CAL', 'POMPA DI CALORE', 'SIST IBR', 'SET MAGIS', 'OMNIA', 'ESTIA', 'YUTAKI', 'AQUAREA'])
    ]

    for it in pdc_items:
        code = it['code']
        name = (it.get('name') or '').upper()
        measures = it.get('catalog_measures', [])
        
        # Non trattare UI split di climatizzazione come pompe di calore
        if any(k in name for k in ['UI PARETE', 'UI CASSETTA', 'UI CONSOLE', 'UI CANALIZZ']) and not any(k in name for k in ['HYDROBOX', 'MODULO IDRONICO', 'ALLIN1', 'MAGIS']):
            continue

        is_acc = any(k in name for k in [
            'KIT SCARIC', 'DIMA', 'RACCORDO', 'PIEDINI', 'ANTIVIBRANT', 'DISGIUNTORE', 
            'TUBO', 'CAVO', 'FLANGIA', 'SONDA', 'TERMOSTATO', 'COMANDO'
        ]) and not any(k in name for k in ['SET MAGIS', 'SIST IBR', 'P/CAL', 'POMPA DI CALORE'])

        # Litri
        litri = None
        for m in measures:
            m_lit = re.search(r'\b(\d{2,3})\s*(?:L|LT|LITRI)\b', m, re.I)
            if m_lit:
                litri = int(m_lit.group(1))
                break
        if not litri:
            m_lit_n = re.search(r'\b(\d{2,3})\s*(?:L|LT)\b', name)
            if m_lit_n:
                litri = int(m_lit_n.group(1))

        # Tubazioni
        tubi = None
        for m in measures:
            m_tub = re.findall(r'\b(1/4|3/8|1/2|5/8|3/4)\b', m)
            if m_tub:
                tubi = '-'.join(dict.fromkeys(m_tub))
                break

        # Potenza Freddo (F) e Caldo (C)
        found_f, found_c = None, None
        if not is_acc:
            for m in measures:
                m_dash = re.search(r'\b([0-9]{1,2}(?:[\.\,][0-9])?)\s*-\s*([0-9]{1,2}(?:[\.\,][0-9])?)\b', m)
                if m_dash:
                    try:
                        v1 = float(m_dash.group(1).replace(',', '.'))
                        v2 = float(m_dash.group(2).replace(',', '.'))
                        if 1.5 <= v1 <= 55.0 and 1.5 <= v2 <= 55.0:
                            found_f, found_c = v1, v2
                            break
                    except ValueError:
                        pass

                m_fc = re.search(r'F\s*([0-9]{1,2}(?:[\,\.][0-9]+)?).*?C\s*([0-9]{1,2}(?:[\,\.][0-9]+)?)', m)
                if m_fc:
                    try:
                        found_f = float(m_fc.group(1).replace(',', '.'))
                        found_c = float(m_fc.group(2).replace(',', '.'))
                        break
                    except ValueError:
                        pass

                if not found_f:
                    m_f = re.search(r'\bF\s*([0-9]{1,2}(?:[\,\.][0-9]+)?)\b', m)
                    if m_f:
                        try:
                            found_f = float(m_f.group(1).replace(',', '.'))
                        except ValueError:
                            pass

                if not found_c:
                    m_c = re.search(r'\bC\s*([0-9]{1,2}(?:[\,\.][0-9]+)?)\b', m)
                    if m_c:
                        try:
                            found_c = float(m_c.group(1).replace(',', '.'))
                        except ValueError:
                            pass

        is_ue = any(name.startswith(p) or f' {p}' in name for p in ['UE ', 'U.E. ', 'UNITA ESTERNA', 'EST '])
        is_ui = any(name.startswith(p) or f' {p}' in name for p in ['UI ', 'U.I. ', 'UNITA INTERNA', 'INT ', 'MODULO IDRONICO'])

        if found_f is not None or found_c is not None or litri is not None or tubi is not None:
            tag_parts = []
            if found_f: tag_parts.append(f"{found_f:g} kW F")
            if found_c: tag_parts.append(f"{found_c:g} kW C")
            tag_kw = " / ".join(tag_parts) if tag_parts else None

            extracted[code] = {
                "code": code,
                "is_pompa_calore": True,
                "is_accessory": is_acc,
                "is_ue": is_ue,
                "is_ui": is_ui,
                "kw_freddo": found_f,
                "kw_caldo": found_c,
                "tag_kw": tag_kw,
                "tag_kw_display": f"[{tag_kw}]" if tag_kw else None,
                "litri": litri,
                "tag_litri": f"{litri} L" if litri else None,
                "tubi": tubi,
                "page": it.get("primary_page"),
                "source": "catalog_measures_table_cell"
            }

    print(f"Completata Fase 1: {len(extracted)} record.")

    # FASE 2: Parsing diretto dalle tabelle del PDF ufficiale (pagine 674 - 761)
    if os.path.exists(PDF_PATH):
        print("Fase 2: scansione diretta PDF pagine 674 - 761...")
        doc = pymupdf.open(PDF_PATH)
        added_count = 0
        updated_count = 0

        for pno in range(674, min(762, len(doc) + 1)):
            page = doc[pno - 1]
            lines = page.get_text().split('\n')
            for idx, l in enumerate(lines):
                m_code = re.search(r'\b(50\d{6}|99\d{6})\b', l)
                if not m_code: continue
                code = m_code.group(1)
                if code not in master: continue
                it = master[code]
                name = (it.get('name') or '').upper()

                if any(k in name for k in ['KIT SCARIC', 'DIMA', 'RACCORDO', 'PIEDINI', 'ANTIVIBRANT', 'DISGIUNTORE', 'TUBO', 'CAVO', 'FLANGIA', 'SONDA']):
                    continue

                if any(k in name for k in ['UI PARETE', 'UI CASSETTA', 'UI CONSOLE', 'UI CANALIZZ']) and not any(k in name for k in ['HYDROBOX', 'MODULO IDRONICO', 'ALLIN1', 'MAGIS']):
                    continue

                context = lines[max(0, idx-3):min(len(lines), idx+4)]
                
                f_val, c_val = None, None
                for cl in context:
                    # Pattern F - C: 15,0 - 16,0 oppure 5,00 - 4,40
                    m_fc = re.search(r'\b([0-9]{1,2}(?:[\,\.][0-9]{1,2})?)\s*-\s*([0-9]{1,2}(?:[\,\.][0-9]{1,2})?)\b', cl)
                    if m_fc:
                        try:
                            v1 = float(m_fc.group(1).replace(',', '.'))
                            v2 = float(m_fc.group(2).replace(',', '.'))
                            if 1.5 <= v1 <= 60.0 and 1.5 <= v2 <= 60.0:
                                f_val, c_val = v1, v2
                                break
                        except ValueError:
                            pass

                    # Pattern Gas ibrido: 24 - met / 32 - met / 24 - gpl
                    m_gas = re.search(r'\b(24|28|30|32|34)\s*-\s*(met|gpl)\b', cl, re.I)
                    if m_gas:
                        c_val = float(m_gas.group(1))
                        break

                # Cerca singolo kW in tabella se non presente trattino
                if not f_val and not c_val:
                    for cl in context:
                        m_single = re.search(r'\b([0-9]{1,2}(?:[\,\.][0-9])?)\s*KW\b', cl, re.I)
                        if m_single:
                            c_val = float(m_single.group(1).replace(',', '.'))
                            break

                # Cerca kW nel nome se non trovato nel testo
                if not f_val and not c_val:
                    m_name_kw = re.search(r'\b([0-9]{1,2}(?:[\,\.][0-9])?)\s*KW\b', name)
                    if m_name_kw:
                        c_val = float(m_name_kw.group(1).replace(',', '.'))

                # Cerca Litri accumulo
                litri_pdf = None
                for cl in context:
                    m_l = re.search(r'\b([1-9][0-9]{2})\s*(?:L|LT|LITRI)\b', cl, re.I)
                    if m_l:
                        litri_pdf = int(m_l.group(1))
                        break
                if not litri_pdf:
                    m_ln = re.search(r'\b([1-9][0-9]{2})\s*(?:L|LT)\b', name)
                    if m_ln:
                        litri_pdf = int(m_ln.group(1))

                if f_val or c_val or litri_pdf:
                    is_ue = any(name.startswith(p) or f' {p}' in name for p in ['UE ', 'U.E. ', 'UNITA ESTERNA', 'EST '])
                    is_ui = any(name.startswith(p) or f' {p}' in name for p in ['UI ', 'U.I. ', 'UNITA INTERNA', 'INT ', 'MODULO IDRONICO'])

                    if code not in extracted:
                        added_count += 1
                        tag_parts = []
                        if f_val: tag_parts.append(f"{f_val:g} kW F")
                        if c_val: tag_parts.append(f"{c_val:g} kW C")
                        tag_kw = " / ".join(tag_parts) if tag_parts else None

                        extracted[code] = {
                            "code": code,
                            "is_pompa_calore": True,
                            "is_accessory": False,
                            "is_ue": is_ue,
                            "is_ui": is_ui,
                            "kw_freddo": f_val,
                            "kw_caldo": c_val,
                            "tag_kw": tag_kw,
                            "tag_kw_display": f"[{tag_kw}]" if tag_kw else None,
                            "litri": litri_pdf,
                            "tag_litri": f"{litri_pdf} L" if litri_pdf else None,
                            "tubi": None,
                            "page": pno,
                            "source": "catalog_pdf_page_table"
                        }
                    else:
                        cur = extracted[code]
                        if not cur.get("kw_freddo") and not cur.get("kw_caldo") and (f_val or c_val):
                            updated_count += 1
                            cur["kw_freddo"] = f_val or cur.get("kw_freddo")
                            cur["kw_caldo"] = c_val or cur.get("kw_caldo")
                            tag_parts = []
                            if cur["kw_freddo"]: tag_parts.append(f"{cur['kw_freddo']:g} kW F")
                            if cur["kw_caldo"]: tag_parts.append(f"{cur['kw_caldo']:g} kW C")
                            cur["tag_kw"] = " / ".join(tag_parts) if tag_parts else None
                            cur["tag_kw_display"] = f"[{cur['tag_kw']}]" if cur["tag_kw"] else None
                        if litri_pdf and not cur.get("litri"):
                            cur["litri"] = litri_pdf
                            cur["tag_litri"] = f"{litri_pdf} L"

        print(f"Completata Fase 2: +{added_count} nuovi articoli estratti, {updated_count} completati.")

    print(f"\nTotale elementi Pompa di Calore / Sistemi Ibridi: {len(extracted)}")
    machines = [v for v in extracted.values() if not v.get("is_accessory") and (v.get("kw_freddo") or v.get("kw_caldo"))]
    print(f"  - Macchine con taglia termica KW [F - C]: {len(machines)}")
    accs = [v for v in extracted.values() if v.get("litri")]
    print(f"  - Accumuli/Bollitori con litri certificati: {len(accs)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"Salvate specifiche in: {OUTPUT_PATH}")

if __name__ == "__main__":
    extract_heatpumps()
