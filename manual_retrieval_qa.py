#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
manual_retrieval_qa.py
Strumento di Quality Assurance (QA) per test umano del motore di candidate retrieval.

Supporta:
1. Modalità Interattiva / Singola Query:
   Input:
     - Titolo query
     - Riferimento opzionale (es. codice fornitore, riga)
     - MPN attuale opzionale
   Output:
     - Query Analysis (Brand rilevato, Dominio/Adapter, Token esatti, Near-model, Contesto)
     - Top 5 candidati per ciascun candidate_pools[slot_id]
       (Codice PT, Nome catalogo, MFG code, Match Type, Identity Evidence,
        Relation Evidence separata, Relation Type, Pagina/Provenance, Rank within-slot)
     - BOM Candidata Completa assemblata

2. Modalità Batch (XLSX / CSV):
   Input: File Excel (.xlsx) o CSV con colonne (titolo/descrizione/query, riferimento, mpn)
   Output: File Excel (.xlsx) o CSV con l'intera analisi di retrieval e la BOM candidata.

Uso:
  python manual_retrieval_qa.py --title "Daikin Climatizzatore Monosplit Bluevolution Emura III 12000 btu FTXJ35AB9"
  python manual_retrieval_qa.py --batch dataset_holdout.xlsx --output results_qa.xlsx
  python manual_retrieval_qa.py --interactive
"""

import sys
import os
import re
import csv
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Aggiungi root del progetto al path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from catalog_search_engine import CatalogSearchEngine


def format_qa_single_report(
    title: str,
    search_res: Dict[str, Any],
    reference: Optional[str] = None,
    current_mpn: Optional[str] = None
) -> str:
    lines = []
    sep = "=" * 80
    subsep = "-" * 80

    lines.append(sep)
    lines.append("  MANUAL RETRIEVAL QA REPORT")
    lines.append(sep)
    lines.append(f"TITOLO QUERY : {title}")
    if reference:
        lines.append(f"RIFERIMENTO  : {reference}")
    if current_mpn:
        lines.append(f"MPN ATTUALE  : {current_mpn}")
    lines.append(f"TEMPO ESEC.  : {search_res.get('execution_time_ms', 0)} ms")

    # 1. QUERY ANALYSIS
    lines.append(subsep)
    lines.append("1. QUERY ANALYSIS")
    lines.append(subsep)
    lines.append(f"  • Detected Brand     : {search_res.get('detected_brand') or 'N/D'}")
    lines.append(f"  • Category / Domain  : {search_res.get('detected_category') or 'CLIMA'}")
    lines.append(f"  • Match Type Global  : {search_res.get('match_type') or 'DESCRIPTIVE'}")

    qa_info = search_res.get("query_analysis", {})
    q_ctx = qa_info.get("query_context", {})
    if q_ctx:
        btus = q_ctx.get("requested_btus", [])
        lines.append(f"  • BTU Richiesti      : {btus if btus else 'Non specificati'}")
        lines.append(f"  • Configurazione     : {'Monosplit' if q_ctx.get('is_monosplit') else ('Multisplit' if q_ctx.get('is_multisplit') else 'Singola/Generale')}")
        lines.append(f"  • Tipologia Esplicita: {q_ctx.get('explicit_tipologia') or 'Nessuna (no hard filter)'}")
        lines.append(f"  • Tipologia Probabile: {q_ctx.get('probable_tipologia') or 'Non determinata'}")
        lines.append(f"  • Reliable Anchor    : {q_ctx.get('has_reliable_anchor', False)}")

    exact_cands = qa_info.get("exact_token_candidates", [])
    lines.append(f"  • Exact Tokens Trovati ({len(exact_cands)}):")
    if exact_cands:
        for ec in exact_cands:
            lines.append(f"      - PT: {ec.get('code')} | MFG: {ec.get('mfg_code')} | Tipo: {ec.get('match_type')}")
    else:
        lines.append("      - Nessun match esatto su codice produttore o anagrafica catalogo")

    near_cands = qa_info.get("near_model_candidates", [])
    if near_cands:
        lines.append(f"  • Near-Model Candidates ({len(near_cands)}):")
        for nc in near_cands[:5]:
            lines.append(f"      - PT: {nc.get('code')} | MFG: {nc.get('mfg_code')}")

    # 2. CANDIDATE POOLS (Top 5 per ciascun slot_id)
    lines.append(subsep)
    lines.append("2. CANDIDATE POOLS PER SLOT (Top 5)")
    lines.append(subsep)

    pools = search_res.get("candidate_pools", {})
    if not pools:
        lines.append("  Nessun candidate pool generato.")
    else:
        for slot_id, cands in pools.items():
            lines.append(f"\n[SLOT: {slot_id.upper()}] - Totale candidati: {len(cands)}")
            lines.append(f"{'#':<3} {'CODICE PT':<10} {'MFG CODE':<18} {'MATCH TYPE':<24} {'TIER':<6} {'SCORE':<7} {'RELATION TYPE & STRENGTH':<32} {'PAG.':<6} {'NOME CATALOGO'}")
            lines.append("-" * 125)

            for rank_idx, c in enumerate(cands[:5], 1):
                pt_code = str(c.get("code") or "")
                mfg = str(c.get("mfg_code") or "-")[:16]
                mtype = str(c.get("match_type") or "DISCOVERY")[:22]
                tier = f"T{c.get('evidence_tier', 5)}"
                score = f"{c.get('score', 0.0):.1f}"

                rel_meta = c.get("relation_evidence")
                if rel_meta:
                    rel_str = f"{rel_meta.get('relation_type')} ({rel_meta.get('relation_strength')})"
                else:
                    rel_str = "-"
                rel_str = rel_str[:30]

                pag = str(c.get("primary_page") or "-")[:4]
                name = str(c.get("name") or "")[:40]

                lines.append(f"{rank_idx:<3} {pt_code:<10} {mfg:<18} {mtype:<24} {tier:<6} {score:<7} {rel_str:<32} {pag:<6} {name}")

    # 3. BOM CANDIDATA COMPLETA
    lines.append(subsep)
    lines.append("3. BOM CANDIDATA RECUPERATA")
    lines.append(subsep)

    # Identifica i componenti primari per ciascun ruolo richiesto
    bom_items = []
    # 1. Unità Esterna
    ue_cands = pools.get("slot_ue", [])
    if ue_cands:
        bom_items.append(("UE (Motore Esterno)", ue_cands[0]))

    # 2. Unità Interne per ciascuna taglia richiesta
    if q_ctx and q_ctx.get("requested_btus"):
        for btu in q_ctx.get("requested_btus"):
            slot_name = f"slot_ui_{btu}"
            ui_cands = pools.get(slot_name, pools.get("slot_ui", []))
            if ui_cands:
                bom_items.append((f"UI {btu} BTU", ui_cands[0]))
    else:
        # Fallback slot UI generico
        ui_cands = pools.get("slot_ui", [])
        if ui_cands:
            bom_items.append(("UI (Unità Interna)", ui_cands[0]))

    if not bom_items:
        # Fallback dai risultati ordinati Top 2
        results = search_res.get("results", [])
        for idx, r in enumerate(results[:2], 1):
            bom_items.append((f"Candidato #{idx}", r))

    for role_lbl, item in bom_items:
        pt_code = item.get("code")
        name = item.get("name")
        mfg = item.get("mfg_code") or "-"
        score = item.get("score")
        tier = item.get("evidence_tier")

        ident_meta = item.get("identity_evidence") or {}
        rel_meta = item.get("relation_evidence") or {}

        ident_desc = f"Tier {tier} [{ident_meta.get('match_type', 'N/D')}]"
        if rel_meta:
            rel_desc = f"{rel_meta.get('relation_type')} (conf: {rel_meta.get('confidence')}, prov: {rel_meta.get('provenance')})"
        else:
            rel_desc = "Nessuna relazione (riconoscimento lessicale/diretto)"

        lines.append(f"  • {role_lbl:<22}: PT {pt_code} | MFG: {mfg}")
        lines.append(f"    Nome Catalogo       : {name}")
        lines.append(f"    Identity Evidence   : {ident_desc}")
        lines.append(f"    Relation Evidence   : {rel_desc}")
        lines.append(f"    Score Complessivo   : {score}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def run_batch_qa(engine: CatalogSearchEngine, input_file: str, output_file: str):
    print(f"Avvio batch QA da: {input_file}")
    in_path = Path(input_file)
    if not in_path.exists():
        print(f"ERRORE: File di input '{input_file}' non trovato.")
        return

    rows_to_process = []
    is_xlsx = in_path.suffix.lower() in [".xlsx", ".xlsm"]

    if is_xlsx:
        import openpyxl
        wb = openpyxl.load_workbook(in_path, data_only=True)
        ws = wb.active
        headers = [str(cell.value or "").strip() for cell in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(row):
                row_dict = {headers[i]: (row[i] if i < len(row) else None) for i in range(len(headers))}
                rows_to_process.append(row_dict)
    else:
        with open(in_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows_to_process.append(r)

    print(f"Caricate {len(rows_to_process)} righe da analizzare.")

    out_records = []
    for idx, r in enumerate(rows_to_process, 1):
        if idx % 20 == 0 or idx == len(rows_to_process):
            print(f"  Elaborate {idx}/{len(rows_to_process)}...")

        # Individua campo titolo/query
        title = (
            r.get("titolo") or r.get("Titolo") or r.get("title") or r.get("query") or
            r.get("descrizione") or r.get("Descrizione") or r.get("nome") or list(r.values())[0]
        )
        title = str(title or "").strip()
        ref = r.get("riferimento") or r.get("codice_fornitore") or r.get("id") or r.get("ID")
        mpn = r.get("mpn") or r.get("mpn_attuale") or r.get("mfg_code")

        if not title:
            continue

        res = engine.search(title, limit=20)
        pools = res.get("candidate_pools", {})
        q_ctx = res.get("query_analysis", {}).get("query_context", {})

        # Estrai BOM candidata
        ue_item = pools.get("slot_ue", [{}])[0] if pools.get("slot_ue") else {}
        btus = q_ctx.get("requested_btus", [])

        ui_items = []
        if btus:
            for b in btus:
                cands = pools.get(f"slot_ui_{b}", pools.get("slot_ui", []))
                if cands:
                    ui_items.append(cands[0])
        else:
            if pools.get("slot_ui"):
                ui_items.append(pools["slot_ui"][0])

        rec = dict(r)
        rec["RETRIEVAL_BRAND"] = res.get("detected_brand")
        rec["RETRIEVAL_MATCH_TYPE"] = res.get("match_type")
        rec["CANDIDATE_UE_PT"] = ue_item.get("code")
        rec["CANDIDATE_UE_MFG"] = ue_item.get("mfg_code")
        rec["CANDIDATE_UE_NAME"] = ue_item.get("name")
        rec["CANDIDATE_UE_TIER"] = ue_item.get("evidence_tier")

        for u_idx, ui_it in enumerate(ui_items, 1):
            rec[f"CANDIDATE_UI{u_idx}_PT"] = ui_it.get("code")
            rec[f"CANDIDATE_UI{u_idx}_MFG"] = ui_it.get("mfg_code")
            rec[f"CANDIDATE_UI{u_idx}_NAME"] = ui_it.get("name")
            rec[f"CANDIDATE_UI{u_idx}_BTU"] = ui_it.get("taglia_btu")
            rec[f"CANDIDATE_UI{u_idx}_TIER"] = ui_it.get("evidence_tier")

        out_records.append(rec)

    # Scrittura output
    out_p = Path(output_file)
    if out_p.suffix.lower() == ".xlsx":
        import openpyxl
        wb_out = openpyxl.Workbook()
        ws_out = wb_out.active
        ws_out.title = "QA_Results"

        if out_records:
            fieldnames = list(out_records[0].keys())
            ws_out.append(fieldnames)
            for rec in out_records:
                ws_out.append([rec.get(k) for k in fieldnames])
        wb_out.save(out_p)
    else:
        with open(out_p, "w", newline="", encoding="utf-8-sig") as f:
            if out_records:
                writer = csv.DictWriter(f, fieldnames=list(out_records[0].keys()))
                writer.writeheader()
                writer.writerows(out_records)

    print(f"Batch QA completato con successo. Risultati salvati in: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Strumento Manual QA per test e verifica del Candidate Retrieval.")
    parser.add_argument("--title", type=str, help="Titolo della query per test singolo")
    parser.add_argument("--ref", type=str, help="Riferimento opzionale (es. codice riga o codice fornitore)")
    parser.add_argument("--mpn", type=str, help="MPN attuale opzionale")
    parser.add_argument("--batch", type=str, help="Percorso del file input XLSX o CSV per test batch")
    parser.add_argument("--output", type=str, default="qa_results.xlsx", help="Percorso file output per test batch")
    parser.add_argument("--interactive", action="store_true", help="Avvia modalità interattiva da riga di comando")

    args = parser.parse_args()

    print("Inizializzazione CatalogSearchEngine per QA...")
    engine = CatalogSearchEngine()
    engine._ensure_initialized()

    if args.batch:
        run_batch_qa(engine, args.batch, args.output)
    elif args.title:
        res = engine.search(args.title, limit=20)
        report = format_qa_single_report(args.title, res, reference=args.ref, current_mpn=args.mpn)
        print("\n" + report)
    elif args.interactive or len(sys.argv) == 1:
        print("\n=== MODALITA' INTERATTIVA MANUAL QA (Digita 'exit' per uscire) ===")
        while True:
            try:
                title = input("\nInserisci Titolo Query: ").strip()
                if not title or title.lower() in ["exit", "quit"]:
                    break
                ref = input("Inserisci Riferimento (opzionale, premi INVIO per saltare): ").strip() or None
                mpn = input("Inserisci MPN attuale (opzionale, premi INVIO per saltare): ").strip() or None

                res = engine.search(title, limit=20)
                report = format_qa_single_report(title, res, reference=ref, current_mpn=mpn)
                print("\n" + report)
            except (KeyboardInterrupt, EOFError):
                break
        print("\nSessione QA terminata.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
