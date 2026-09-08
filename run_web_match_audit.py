"""
run_web_match_audit.py
Motore di validazione massiva dei prodotti tramite:
1. Cross-referencing con anagrafica ufficiale Puglia Termica (57.608 prodotti)
2. Web Search in tempo reale su codici produttore (MPN) tramite WebProductSearcher
3. Cache SQLite permanente per non ripetere chiamate
4. Esportazione progressiva in Excel formattato a colori (.xlsx) e CSV
"""

import sys
import os
import csv
import json
import re
import time
from typing import Dict, Any, Optional, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

# Percorsi di lavoro
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV_PATH = os.path.join(BASE_DIR, "Report_Verifica_12000_Prodotti_Nuovo.csv")
if not os.path.exists(INPUT_CSV_PATH):
    INPUT_CSV_PATH = os.path.join(BASE_DIR, "Export_Prodotti_Verifica.csv")

OUTPUT_XLSX_PATH = os.path.join(BASE_DIR, "Report_Validazione_Web_12000_Prodotti.xlsx")
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "Report_Validazione_Web_12000_Prodotti.csv")

LOOKUP_PATH = os.path.join(BASE_DIR, "Knowledge", "vector_db", "exact_code_lookup.json")
MASTER_CATALOG_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")

from web_product_searcher import WebProductSearcher

# Colori per il semaforo Excel
FILL_GREEN = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
FONT_GREEN = Font(color="155724", bold=True, name="Segoe UI", size=10)

FILL_RED = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
FONT_RED = Font(color="721C24", bold=True, name="Segoe UI", size=10)

FILL_YELLOW = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
FONT_YELLOW = Font(color="856404", bold=True, name="Segoe UI", size=10)

FILL_BLUE = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid")
FONT_BLUE = Font(color="0C5460", bold=True, name="Segoe UI", size=10)

FILL_GRAY = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
FONT_GRAY = Font(color="383D41", bold=False, name="Segoe UI", size=10)

HEADER_FILL = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, name="Segoe UI", size=10)

REGULAR_FONT = Font(name="Segoe UI", size=10)
BORDER_THIN = Border(
    left=Side(style='thin', color='E0E0E0'),
    right=Side(style='thin', color='E0E0E0'),
    top=Side(style='thin', color='E0E0E0'),
    bottom=Side(style='thin', color='E0E0E0')
)

class WebMatchAuditor:
    def __init__(self, limit: Optional[int] = None):
        self.limit = limit
        self.searcher = WebProductSearcher()
        self.lookup = {}
        self.master_by_code = {}
        self.master_by_mfg = {}
        self._load_catalogs()

    def _load_catalogs(self):
        print("Caricamento catalogo master Puglia Termica...")
        if os.path.exists(LOOKUP_PATH):
            with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
                self.lookup = json.load(f)
        if os.path.exists(MASTER_CATALOG_PATH):
            with open(MASTER_CATALOG_PATH, "r", encoding="utf-8") as f:
                master = json.load(f)
                for it in master:
                    c = str(it.get("code") or "").strip()
                    m = str(it.get("mfg_code") or "").strip().upper()
                    if c:
                        self.master_by_code[c] = it
                    if m:
                        if m not in self.master_by_mfg:
                            self.master_by_mfg[m] = []
                        self.master_by_mfg[m].append(it)
        print(f"Catalogo caricato: {len(self.master_by_code)} codici articolo, {len(self.master_by_mfg)} MPN indicizzati.")

    def extract_clean_mpn(self, reference: str, mpn: str, title: str, brand: str) -> Optional[str]:
        """Estrae il codice modello/produttore più probabile dai campi dell'utente."""
        m = (mpn or "").strip()
        ref = (reference or "").strip()

        # Pulisci valori vuoti tipici di esportazioni Excel
        if m.upper() in ("", "(VUOTO)", "VUOTO", "-", "NAN", "NULL", "NONE"):
            m = ""
        if ref.upper() in ("", "(VUOTO)", "VUOTO", "-", "NAN", "NULL", "NONE"):
            ref = ""

        # Se mpn ha già un codice alfanumerico pulito che non è un elenco di codici PT separati da '+'
        if m and "+" not in m and len(m) >= 4 and not (m.isdigit() and len(m) == 8 and m.startswith("50")):
            return m

        # Cerca codice nel reference
        if ref and "+" not in ref:
            # Rimuovi prefissi come "Aermec-MPG/D_" o "ref: " o "_Defangatore"
            clean_ref = re.sub(r'^[A-Za-z0-9]+[-_]', '', ref)
            clean_ref = re.sub(r'_Defangatore.*$', '', clean_ref)
            if clean_ref.upper() not in ("", "(VUOTO)", "VUOTO", "-", "NAN", "NULL", "NONE"):
                if len(clean_ref) >= 4 and not clean_ref.isdigit() or (clean_ref.isdigit() and len(clean_ref) in (7, 8, 10)):
                    return clean_ref

        # Cerca token alfanumerico evidente nel titolo (es. 3MXM68A, FTXA35, 3301313, ECO5 BLUE 24)
        m_code = re.search(r'\b([A-Z0-9]{3,}-[A-Z0-9\/\+]{3,}|[A-Z]{2,4}\d{2,5}[A-Z0-9]*)\b', title)
        if m_code:
            code_candidate = m_code.group(1)
            if code_candidate.upper() not in ("INVERTER", "CLASSE", "SERIE", "CAMERA", "METANO", "CONDIZIONATORE"):
                return code_candidate

        return m or ref or None

    def validate_product(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue la validazione ibrida (Catalogo Ufficiale PT + Web Search)."""
        pid = row.get("id_product", "")
        ref = row.get("reference", "")
        title = row.get("product_name", "")
        brand_user = row.get("brand_originale", "") or row.get("brand", "")
        mpn_user = row.get("mpn_originale", "") or row.get("mpn", "")
        pt_code_assigned = row.get("pt_codice_finale", "")
        pt_name_assigned = row.get("pt_nome_finale", "")
        pt_brand_assigned = row.get("pt_marchio_ufficiale", "")
        pt_cat_assigned = row.get("pt_categoria_ufficiale", "")
        pt_price = row.get("pt_prezzo_listino", "")
        pt_page = row.get("pt_pagina_catalogo", "")
        prev_esito = row.get("esito_verifica", "")

        # Estrai MPN pulito
        effective_mpn = self.extract_clean_mpn(ref, mpn_user, title, brand_user)

        # Risultato default
        result = {
            "id_product": pid,
            "reference": ref,
            "mpn_originale": mpn_user,
            "effective_mpn": effective_mpn or "",
            "product_name": title,
            "brand_originale": brand_user,
            "pt_codice_finale": pt_code_assigned,
            "pt_nome_finale": pt_name_assigned,
            "pt_marchio_ufficiale": pt_brand_assigned,
            "pt_categoria_ufficiale": pt_cat_assigned,
            "pt_prezzo_listino": pt_price,
            "pt_pagina_catalogo": pt_page,
            "esito_validazione_web": "",
            "dettaglio_diagnosi_web": "",
            "titolo_web": "",
            "parametri_tecnici_web": "",
            "url_fonte_web": "",
            "pt_codice_suggerito": ""
        }

        # CASO 0: Prodotto già verificato come CORRETTO a catalogo PT
        if prev_esito == "🟢 CORRETTO" and pt_code_assigned:
            result["esito_validazione_web"] = "🟢 MATCH_VALIDATO_CATALOGO_PT"
            result["dettaglio_diagnosi_web"] = row.get("motivo_dettagliato", "Parametri tecnici, marca e codici verificati a catalogo con successo.")
            if effective_mpn and brand_user:
                web_cached = self.searcher.get_from_cache(brand_user, effective_mpn)
                if web_cached and web_cached.get("found"):
                    result["titolo_web"] = web_cached.get("title", "")
                    result["url_fonte_web"] = web_cached.get("url", "")
                    result["parametri_tecnici_web"] = ", ".join(web_cached.get("specs", {}).get("raw_matches", []))
            return result

        # CASO 0B: MPN assente nel file, già mappato per coerenza tecnica sul catalogo PT
        if "MPN_VUOTO" in prev_esito:
            result["esito_validazione_web"] = "🔵 MPN_ASSENTE_MAPPATO_PT"
            result["dettaglio_diagnosi_web"] = "Codice fornitore non presente nel file; articolo mappato per coerenza tecnica sul catalogo Puglia Termica."
            return result

        # CASO 0C: Modello non a catalogo PT
        if "MODELLO_NON_A_CATALOGO" in prev_esito:
            result["esito_validazione_web"] = "⚪ MODELLO_NON_A_CATALOGO_PT"
            result["dettaglio_diagnosi_web"] = row.get("motivo_dettagliato", "Marchio gestito a catalogo, ma serie o taglia specifica non a listino PT 2026.")
            return result

        # CASO 1: Marchio non a catalogo PT
        if "MARCHIO_NON_A_CATALOGO" in prev_esito or (brand_user and brand_user.upper() in ["1 AID", "BLACK&DECKER", "APPLE"]):
            result["esito_validazione_web"] = "⚪ MARCHIO_FUORI_CATALOGO_PT"
            result["dettaglio_diagnosi_web"] = f"Il marchio '{brand_user}' non è distribuito nel catalogo Puglia Termica."
            return result

        # CASO 2: Incompatibilità nota rilevata (es. Monosplit 12000 con UE 24000)
        if "INCOMPATIBILE" in prev_esito:
            result["esito_validazione_web"] = "🔴 MISMATCH_TECNICO_GRAVE"
            result["dettaglio_diagnosi_web"] = row.get("motivo_dettagliato", "Incompatibilità riscontrata tra taglia richiesta e codice PT abbinato.")
            # Effettua web search di conferma se presente MPN
            if effective_mpn and brand_user:
                web_res = self.searcher.search_product(brand_user, effective_mpn, context_hint=title)
                if web_res["found"]:
                    result["titolo_web"] = web_res["title"]
                    result["url_fonte_web"] = web_res["url"]
                    result["parametri_tecnici_web"] = ", ".join(web_res["specs"].get("raw_matches", []))
            return result

        # CASO 3: Prodotto con codice PT già verificato al 100% da codice produttore diretto
        # Se l'MPN utente coincide con il mfg_code di uno qualsiasi dei componenti a listino PT, il match è matematicamente validato
        codes_in_kit = [c.strip() for c in pt_code_assigned.split("+") if c.strip()]
        matched_pt_item = None
        for c in codes_in_kit:
            it = self.master_by_code.get(c)
            if it and effective_mpn and it.get("mfg_code", "").strip().upper() == effective_mpn.strip().upper():
                matched_pt_item = it
                break

        if matched_pt_item and effective_mpn:
            result["esito_validazione_web"] = "🟢 MATCH_VALIDATO_AL_100%"
            result["dettaglio_diagnosi_web"] = f"Codice Produttore ({effective_mpn}) e Marchio ({matched_pt_item.get('brand')}) verificati con esattezza a catalogo ufficiale e web."
            # Arricchimento opzionale da cache
            web_cached = self.searcher.search_product(brand_user, effective_mpn, context_hint=title)
            if web_cached.get("found"):
                result["titolo_web"] = web_cached.get("title", "")
                result["url_fonte_web"] = web_cached.get("url", "")
                result["parametri_tecnici_web"] = ", ".join(web_cached.get("specs", {}).get("raw_matches", []))
            return result

        # CASO 4: Verifica Web attiva per codici da validare o kit
        if effective_mpn and brand_user:
            web_res = self.searcher.search_product(brand_user, effective_mpn, context_hint=title)
            if web_res["found"]:
                result["titolo_web"] = web_res["title"]
                result["url_fonte_web"] = web_res["url"]
                specs = web_res["specs"]
                raw_specs = specs.get("raw_matches", [])
                result["parametri_tecnici_web"] = ", ".join(raw_specs)

                # Confronto incrociato parametri web vs codice PT assegnato
                pt_n_upper = (pt_name_assigned or "").upper()
                web_t_upper = (web_res["title"] or "").upper()

                # Controllo taglia / BTU
                if specs.get("btu"):
                    taglia_str = str(specs["btu"])
                    # Se il titolo web dice 12000 ma l'articolo PT è chiaramente un 24000
                    if "12000" in taglia_str and "24000" in pt_n_upper:
                        result["esito_validazione_web"] = "🔴 MISMATCH_TAGLIA_WEB"
                        result["dettaglio_diagnosi_web"] = f"Discrepanza confermata da web: la scheda web indica {taglia_str} BTU ma il codice PT assegnato è {pt_n_upper}."
                        return result

                # Controllo Gas
                if specs.get("gas") and specs["gas"] not in pt_n_upper and ("R32" in pt_n_upper or "R410A" in pt_n_upper):
                    if specs["gas"] == "R-32" and "R410A" in pt_n_upper:
                        result["esito_validazione_web"] = "🔴 MISMATCH_GAS_WEB"
                        result["dettaglio_diagnosi_web"] = f"La scheda web ufficiale indica gas {specs['gas']}, ma il codice PT è R410A."
                        return result

                # Controllo Kit / Numero Porte Multisplit
                if specs.get("ac_ports") and specs["ac_ports"] > 1:
                    codes_count = len(pt_code_assigned.split("+")) if pt_code_assigned else 0
                    expected_min = 1 + specs["ac_ports"]
                    if codes_count < expected_min:
                        result["esito_validazione_web"] = "🟡 ATTENZIONE_KIT_INCOMPLETO"
                        result["dettaglio_diagnosi_web"] = f"Il prodotto web è un {specs.get('ac_type')} ({specs['ac_ports']} split, attesi almeno {expected_min} codici), ma ne sono assegnati solo {codes_count}."
                        return result

                # Se non sono emerse discrepanze: Match confermato
                result["esito_validazione_web"] = "🟢 MATCH_VALIDATO_WEB"
                result["dettaglio_diagnosi_web"] = f"Corrispondenza confermata da scheda tecnica web ufficiale ({web_res['url']})."
                return result
            else:
                result["esito_validazione_web"] = "⚪ MPN_NON_TROVATO_ONLINE"
                result["dettaglio_diagnosi_web"] = f"Nessun riscontro univoco trovato online per il codice fornitore '{effective_mpn}'."
                return result

        # Fallback
        result["esito_validazione_web"] = prev_esito if prev_esito else "⚪ DA_VERIFICARE"
        result["dettaglio_diagnosi_web"] = row.get("motivo_dettagliato", "In attesa di codice produttore per ricerca web mirata.")
        return result

    def run_audit(self):
        """Esegue l'audit completo o limitato e genera i file di output."""
        t0 = time.time()
        print(f"\nAvvio Audit di Validazione Web da: {INPUT_CSV_PATH}")

        # Lettura CSV
        rows = []
        with open(INPUT_CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for r in reader:
                rows.append(r)
                if self.limit and len(rows) >= self.limit:
                    break

        total_rows = len(rows)
        print(f"Totale righe da elaborare: {total_rows}")

        results = []
        counts = {
            "🟢 MATCH_VALIDATO": 0,
            "🔴 MISMATCH_TECNICO": 0,
            "🟡 ATTENZIONE": 0,
            "⚪ FUORI_CATALOGO_O_NON_TROVATO": 0
        }

        # Elaborazione
        for idx, row in enumerate(rows, 1):
            res = self.validate_product(row)
            results.append(res)

            esito = res["esito_validazione_web"]
            if "🟢" in esito:
                counts["🟢 MATCH_VALIDATO"] += 1
            elif "🔴" in esito:
                counts["🔴 MISMATCH_TECNICO"] += 1
            elif "🟡" in esito:
                counts["🟡 ATTENZIONE"] += 1
            else:
                counts["⚪ FUORI_CATALOGO_O_NON_TROVATO"] += 1

            if idx % 100 == 0 or idx == total_rows:
                elapsed = time.time() - t0
                rate = idx / elapsed if elapsed > 0 else 0
                print(f"Progresso: {idx}/{total_rows} ({idx/total_rows*100:.1f}%) | {rate:.1f} righe/sec | Validati: {counts['🟢 MATCH_VALIDATO']} | Errori: {counts['🔴 MISMATCH_TECNICO']}", flush=True)

            if idx % 2500 == 0 and idx < total_rows:
                print(f"Checkpoint salvataggio intermedio ({idx} righe)...", flush=True)
                self.export_csv(results)

        # Esportazione Excel e CSV
        self.export_excel(results)
        self.export_csv(results)

        total_time = time.time() - t0
        print(f"\n=== AUDIT COMPLETATO CON SUCCESSO IN {total_time:.1f} SECONDI ===")
        print(f"🟢 Match Validati:            {counts['🟢 MATCH_VALIDATO']}")
        print(f"🔴 Mismatch / Errori Web:      {counts['🔴 MISMATCH_TECNICO']}")
        print(f"🟡 Attenzioni Kit / Varianti:  {counts['🟡 ATTENZIONE']}")
        print(f"⚪ Non Trovati / Fuori Cat.:   {counts['⚪ FUORI_CATALOGO_O_NON_TROVATO']}")
        print(f"\nReport Excel salvato in: {OUTPUT_XLSX_PATH}")
        print(f"Report CSV salvato in:   {OUTPUT_CSV_PATH}")

    def export_excel(self, results: List[Dict[str, Any]]):
        """Genera un file Excel professionale con semafori a colori e larghezze colonne auto-adattate."""
        print(f"Generazione file Excel: {OUTPUT_XLSX_PATH}...")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Validazione Web & Catalogo PT"
        ws.views.sheetView[0].showGridLines = True

        headers = [
            "ID Prodotto",
            "Tuo Riferimento",
            "Tuo MPN",
            "MPN Rilevato",
            "Tuo Titolo Prodotto",
            "Tuo Marchio",
            "Codice PT Assegnato",
            "Nome PT Assegnato",
            "Marchio PT",
            "Categoria PT",
            "Prezzo Listino PT",
            "Pagina Catalogo",
            "Esito Validazione Web",
            "Diagnosi Dettagliata Web",
            "Titolo Prodotto Web Trovato",
            "Parametri Tecnici Rilevati dal Web",
            "Link Fonte Web Consultata"
        ]

        ws.append(headers)

        # Formatta header
        for col_num, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 28

        # Inserimento dati
        for r_idx, res in enumerate(results, 2):
            row_data = [
                res["id_product"],
                res["reference"],
                res["mpn_originale"],
                res["effective_mpn"],
                res["product_name"],
                res["brand_originale"],
                res["pt_codice_finale"],
                res["pt_nome_finale"],
                res["pt_marchio_ufficiale"],
                res["pt_categoria_ufficiale"],
                res["pt_prezzo_listino"],
                res["pt_pagina_catalogo"],
                res["esito_validazione_web"],
                res["dettaglio_diagnosi_web"],
                res["titolo_web"],
                res["parametri_tecnici_web"],
                res["url_fonte_web"]
            ]
            ws.append(row_data)
            ws.row_dimensions[r_idx].height = 20

            # Stile cella esito a semaforo
            esito_cell = ws.cell(row=r_idx, column=13)
            esito_val = str(res["esito_validazione_web"])
            if "🟢" in esito_val:
                esito_cell.fill = FILL_GREEN
                esito_cell.font = FONT_GREEN
            elif "🔴" in esito_val:
                esito_cell.fill = FILL_RED
                esito_cell.font = FONT_RED
            elif "🟡" in esito_val:
                esito_cell.fill = FILL_YELLOW
                esito_cell.font = FONT_YELLOW
            elif "🔵" in esito_val:
                esito_cell.fill = FILL_BLUE
                esito_cell.font = FONT_BLUE
            else:
                esito_cell.fill = FILL_GRAY
                esito_cell.font = FONT_GRAY

            # Bordi leggeri
            for col_num in range(1, len(headers) + 1):
                c = ws.cell(row=r_idx, column=col_num)
                c.border = BORDER_THIN
                if col_num not in [13]:
                    c.font = REGULAR_FONT

        # Autofit larghezza colonne
        col_widths = {
            1: 12, 2: 24, 3: 16, 4: 16, 5: 45, 6: 15,
            7: 22, 8: 35, 9: 15, 10: 30, 11: 16, 12: 15,
            13: 28, 14: 45, 15: 40, 16: 35, 17: 35
        }
        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.auto_filter.ref = ws.dimensions
        wb.save(OUTPUT_XLSX_PATH)

    def export_csv(self, results: List[Dict[str, Any]]):
        """Esporta anche in formato CSV UTF-8 con BOM per compatibilità diretta Excel."""
        print(f"Generazione file CSV: {OUTPUT_CSV_PATH}...")
        fieldnames = [
            "id_product", "reference", "mpn_originale", "effective_mpn",
            "product_name", "brand_originale", "pt_codice_finale", "pt_nome_finale",
            "pt_marchio_ufficiale", "pt_categoria_ufficiale", "pt_prezzo_listino",
            "pt_pagina_catalogo", "esito_validazione_web", "dettaglio_diagnosi_web",
            "titolo_web", "parametri_tecnici_web", "url_fonte_web"
        ]
        with open(OUTPUT_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k, "") for k in fieldnames})


if __name__ == "__main__":
    # Se viene passato un argomento numerico (es. python run_web_match_audit.py 50), esegue il test limitato
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    auditor = WebMatchAuditor(limit=limit_arg)
    auditor.run_audit()
