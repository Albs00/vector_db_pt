"""
export_ac_matrix_excel.py
Esporta la Matrice Master di Compatibilità Climatizzatori 2026
in un Report Excel formattato multi-foglio (.xlsx) e CSV con TUTTI i modelli UI e serie.
"""

import sys
import os
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_JSON_PATH = os.path.join(BASE_DIR, "Knowledge", "climatizzatori_compatibilita_master.json")
EXCEL_OUTPUT_PATH = os.path.join(BASE_DIR, "Report_Matrice_Compatibilita_Climatizzatori_2026.xlsx")

def export_to_excel():
    print("[1/3] Caricamento Matrice Master JSON...")
    if not os.path.exists(MASTER_JSON_PATH):
        print(f"[ERRORE] File non trovato: {MASTER_JSON_PATH}")
        sys.exit(1)

    with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    wb = Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    right_align = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="E0E0E0"),
        right=Side(style="thin", color="E0E0E0"),
        top=Side(style="thin", color="E0E0E0"),
        bottom=Side(style="thin", color="E0E0E0")
    )

    print("[2/3] Generazione fogli Excel con Modelli e Serie UI...")

    # FOGLIO 1: UNITA ESTERNE (UE)
    ws_ue = wb.create_sheet(title="Unità Esterne (UE)")
    ue_headers = [
        "Codice PT", "Codice Fornitore (MPN)", "Descrizione Articolo", "Marchio",
        "Serie Commerciale", "Tipologia Sistema", "Attacchi (Porte)", "Potenza Nominale (kW)",
        "Gas Refrigerante", "Prezzo Listino (€)", "Prezzo Netto PT (€)", "Pagina Catalogo",
        "Serie UI Compatibili", "Totale Modelli UI Compatibili", "Modelli UI Compatibili (MPN)",
        "Combinazioni Taglie Ammesse", "Totale Kit Pronti"
    ]
    ws_ue.append(ue_headers)
    for col_idx in range(1, len(ue_headers) + 1):
        cell = ws_ue.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    for ue in data.get("unita_esterne", {}).values():
        models_list = ue.get("modelli_ui_compatibili", [])
        models_str = ", ".join(models_list[:15]) + (f" ... (+ altri {len(models_list)-15})" if len(models_list) > 15 else "")
        row = [
            ue.get("codice_pt"),
            ue.get("codice_mfg") or "-",
            ue.get("nome"),
            ue.get("brand"),
            ue.get("serie"),
            ue.get("tipo_sistema"),
            ue.get("porte_attacchi"),
            ue.get("potenza_nominale_kw"),
            ue.get("refrigerante"),
            ue.get("prezzo_listino"),
            ue.get("prezzo_netto"),
            ue.get("pagina_catalogo") or "-",
            ", ".join(ue.get("serie_ui_compatibili", [])),
            ue.get("totale_modelli_ui_compatibili", 0),
            models_str,
            ", ".join(ue.get("combinazioni_ammesse_taglie", [])),
            ue.get("totale_kit_pronti", 0)
        ]
        ws_ue.append(row)
        for col_idx in range(1, len(row) + 1):
            c = ws_ue.cell(row=ws_ue.max_row, column=col_idx)
            c.font = data_font
            c.border = thin_border
            if col_idx in [1, 2, 7, 8, 9, 12, 14, 17]:
                c.alignment = center_align
            elif col_idx in [10, 11]:
                c.alignment = right_align
                c.number_format = "#,##0.00"

    # FOGLIO 2: UNITA INTERNE (UI)
    ws_ui = wb.create_sheet(title="Unità Interne (UI)")
    ui_headers = [
        "Codice PT", "Codice Fornitore (MPN)", "Descrizione Articolo", "Tag BTU", "Marchio",
        "Serie Commerciale", "Tipologia Split", "Taglia (BTU)", "Potenza (kW)",
        "Gas Refrigerante", "Prezzo Listino (€)", "Prezzo Netto PT (€)", "Pagina Catalogo",
        "Totale UE Abbinabili", "Modelli UE Compatibili (MPN)", "Serie UE Compatibili"
    ]
    ws_ui.append(ui_headers)
    for col_idx in range(1, len(ui_headers) + 1):
        cell = ws_ui.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    for ui in data.get("unita_interne", {}).values():
        ue_models = ui.get("modelli_ue_compatibili", [])
        ue_models_str = ", ".join(ue_models[:12]) + (f" ... (+ altri {len(ue_models)-12})" if len(ue_models) > 12 else "")
        tag_btu_val = ui.get("tag_btu") or f"{ui.get('taglia_btu', 9000)} btu"
        row = [
            ui.get("codice_pt"),
            ui.get("codice_mfg") or "-",
            ui.get("nome"),
            tag_btu_val,
            ui.get("brand"),
            ui.get("serie"),
            ui.get("tipologia"),
            ui.get("taglia_btu"),
            ui.get("taglia_kw"),
            ui.get("refrigerante"),
            ui.get("prezzo_listino"),
            ui.get("prezzo_netto"),
            ui.get("pagina_catalogo") or "-",
            len(ui.get("unita_esterne_compatibili", [])),
            ue_models_str,
            ", ".join(ui.get("serie_ue_compatibili", []))
        ]
        ws_ui.append(row)
        for col_idx in range(1, len(row) + 1):
            c = ws_ui.cell(row=ws_ui.max_row, column=col_idx)
            c.font = data_font
            c.border = thin_border
            if col_idx in [1, 2, 4, 8, 9, 10, 13, 14]:
                c.alignment = center_align
            elif col_idx in [11, 12]:
                c.alignment = right_align
                c.number_format = "#,##0.00"

    # FOGLIO 3: KIT PRONTI
    ws_kits = wb.create_sheet(title="Kit Commerciali Preconfigurati")
    kit_headers = [
        "Codice Kit / Mexal", "Nome Commerciale Kit", "Configurazione", "Marchio",
        "Prezzo Listino Totale (€)", "Prezzo Netto Totale (€)",
        "Pagina Catalogo", "Dettaglio Componenti UI"
    ]
    ws_kits.append(kit_headers)
    for col_idx in range(1, len(kit_headers) + 1):
        cell = ws_kits.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    kits_list = data.get("kit_completi") or data.get("kit_commerciali_completi", [])
    for kit in kits_list:
        comps = kit.get("componenti_ui") or kit.get("ui_components", [])
        ui_details = " + ".join([f"[{c.get('codice_mfg') or c.get('codice_pt')}] {c.get('nome')} [{c.get('tag_btu') or str(c.get('taglia_btu', 9000)) + ' btu'}]" for c in comps])
        b_name = kit.get("brand") or (comps[0].get("brand") if comps else "")
        gross_p = kit.get("totale_prezzo_listino") or kit.get("total_gross_price") or kit.get("prezzo_listino_totale") or 0.0
        net_p = kit.get("totale_prezzo_netto") or kit.get("total_net_price") or kit.get("prezzo_netto_totale") or 0.0
        row = [
            kit.get("id_kit") or kit.get("code"),
            kit.get("nome_kit") or kit.get("kit_name") or kit.get("name"),
            kit.get("configurazione") or kit.get("configuration"),
            b_name,
            gross_p,
            net_p,
            kit.get("pagina_catalogo") or kit.get("catalog_page") or "-",
            ui_details
        ]
        ws_kits.append(row)
        for col_idx in range(1, len(row) + 1):
            c = ws_kits.cell(row=ws_kits.max_row, column=col_idx)
            c.font = data_font
            c.border = thin_border
            if col_idx in [1, 3, 4, 7]:
                c.alignment = center_align
            elif col_idx in [5, 6]:
                c.alignment = right_align
                c.number_format = "#,##0.00"

    # FOGLIO 4: MARCHI
    ws_brand = wb.create_sheet(title="Riepilogo Marchi")
    b_headers = ["Marchio", "Totale UE", "Totale UI", "Totale Kit Pronti", "Serie Commerciali Gestite", "Gas Refrigeranti"]
    ws_brand.append(b_headers)
    for col_idx in range(1, len(b_headers) + 1):
        cell = ws_brand.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    for b_name, b_info in sorted(data.get("marchi", {}).items()):
        row = [
            b_name,
            b_info.get("totale_unita_esterne", 0),
            b_info.get("totale_unita_interne", 0),
            b_info.get("totale_kit_preconfigurati", 0),
            ", ".join(b_info.get("serie_commerciali", [])),
            ", ".join(b_info.get("refrigeranti", []))
        ]
        ws_brand.append(row)
        for col_idx in range(1, len(row) + 1):
            c = ws_brand.cell(row=ws_brand.max_row, column=col_idx)
            c.font = data_font
            c.border = thin_border
            if col_idx in [2, 3, 4]:
                c.alignment = center_align

    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)

    print(f"[3/3] Salvataggio report Excel in: {EXCEL_OUTPUT_PATH}...")
    wb.save(EXCEL_OUTPUT_PATH)
    file_size_mb = os.path.getsize(EXCEL_OUTPUT_PATH) / (1024 * 1024)
    print(f"[SUCCESSO] Report Excel aggiornato con successo ({file_size_mb:.2f} MB)")

if __name__ == "__main__":
    export_to_excel()
