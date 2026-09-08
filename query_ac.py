"""
query_ac.py
Tool CLI di consultazione rapida della Matrice Compatibilità Climatizzatori 2026.
Uso:
    python query_ac.py <codice_pt_o_mpn>
    python query_ac.py --brand DAIKIN
    python query_ac.py --family PERFERA
    python query_ac.py --stats
"""

import sys
import os
import json
import argparse

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_JSON_PATH = os.path.join(BASE_DIR, "Knowledge", "climatizzatori_compatibilita_master.json")

def load_matrix():
    if not os.path.exists(MASTER_JSON_PATH):
        print(f"[ERRORE] File non trovato: {MASTER_JSON_PATH}")
        sys.exit(1)
    with open(MASTER_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def print_stats(data):
    meta = data.get("metadata") or data.get("_metadata") or {}
    brands = meta.get("marchi") or data.get("marchi") or {}
    print("=======================================================================")
    print("      MATRICE MASTER COMPATIBILITA CLIMATIZZATORI PUGLIA TERMICA       ")
    print("=======================================================================")
    print(f" • Versione:                      {meta.get('versione')}")
    print(f" • Totale Unità Esterne (UE):     {meta.get('totale_unita_esterne')}")
    print(f" • Totale Unità Interne (UI):     {meta.get('totale_unita_interne')}")
    print(f" • Totale Kit Preconfigurati:     {meta.get('totale_kit_preconfigurati')}")
    print(f" • Totale Famiglie Catalogo:      {meta.get('totale_famiglie_catalogo')}")
    print(f" • Marchi Censiti:                {meta.get('totale_marchi')}")
    print("\nElenco Principali Marchi e Famiglie Catalogo:")
    for b_name, b_info in sorted(brands.items()):
        ue_c = b_info.get("totale_unita_esterne", 0)
        ui_c = b_info.get("totale_unita_interne", 0)
        kit_c = b_info.get("totale_kit_preconfigurati", 0)
        fams = b_info.get("famiglie_catalogo_censite") or b_info.get("serie_commerciali") or []
        if ue_c > 0 or ui_c > 0:
            print(f"   - {b_name:<16}: {ue_c:>3} UE | {ui_c:>3} UI | {kit_c:>3} Kit Pronti | Famiglie: {', '.join(fams[:4])}")
    print("=======================================================================\n")

def query_family(data, family_str: str):
    f_q = family_str.strip().upper()
    unita_esterne = data.get("unita_esterne", {})
    unita_interne = data.get("unita_interne", {})

    matching_ue = [ue for ue in unita_esterne.values() if f_q in (ue.get("famiglia_catalogo") or ue.get("serie") or "").upper()]
    matching_ui = [ui for ui in unita_interne.values() if f_q in (ui.get("famiglia_catalogo") or ui.get("serie") or "").upper()]

    print("=======================================================================")
    print(f"          RISULTATI PER FAMIGLIA CATALOGO: '{family_str.upper()}'     ")
    print("=======================================================================")
    print(f"Trovate {len(matching_ue)} Unità Esterne (UE) e {len(matching_ui)} Unità Interne (UI).\n")

    if matching_ue:
        print("--- Unità Esterne (UE) ---")
        for ue in matching_ue[:10]:
            print(f"  • [{ue['codice_pt']}] {ue.get('codice_mfg', '-'):<14} | {ue['brand']:<10} | {ue['nome'][:45]:<45} | Listino: {ue.get('prezzo_listino')} € | P.{ue.get('pagina_catalogo')}")
        if len(matching_ue) > 10:
            print(f"    ... e altre {len(matching_ue) - 10} UE.")

    if matching_ui:
        print("\n--- Unità Interne (UI) ---")
        for ui in matching_ui[:15]:
            tag_str = ui.get('tag_btu') or f"{ui.get('taglia_btu', 9000)} btu"
            print(f"  • [{ui['codice_pt']}] {ui.get('codice_mfg', '-'):<14} | {ui['brand']:<10} | [{tag_str:<9}] | {ui.get('tipologia', 'PARETE'):<12} | {ui['nome'][:36]:<36} | P.{ui.get('pagina_catalogo')}")
        if len(matching_ui) > 15:
            print(f"    ... e altre {len(matching_ui) - 15} UI.")
    print("=======================================================================\n")

def query_code(data, query_str: str):
    q = query_str.strip().upper()
    unita_esterne = data.get("unita_esterne", {})
    unita_interne = data.get("unita_interne", {})

    found_ue = None
    found_ui = None

    # 1. Cerca tra le Unità Esterne
    if q in unita_esterne:
        found_ue = unita_esterne[q]
    else:
        for ue in unita_esterne.values():
            if (ue.get("codice_mfg") or "").upper() == q or q in (ue.get("nome") or "").upper():
                found_ue = ue
                break

    # 2. Cerca tra le Unità Interne
    if q in unita_interne:
        found_ui = unita_interne[q]
    else:
        for ui in unita_interne.values():
            if (ui.get("codice_mfg") or "").upper() == q or q in (ui.get("nome") or "").upper():
                found_ui = ui
                break

    if not found_ue and not found_ui:
        print(f"\n[INFO] Nessun climatizzatore trovato per '{query_str}'.")
        print("Suggerimento: prova con un codice PT a 8 cifre (es. 50202171) o un codice fornitore MPN (es. 2MXM40A).\n")
        return

    print("=======================================================================")
    if found_ue:
        print("                       SCHEDA UNITA ESTERNA (UE)                       ")
        print("=======================================================================")
        print(f" Codice PT:            {found_ue.get('codice_pt')} (MPN: {found_ue.get('codice_mfg') or '-'})")
        print(f" Descrizione:          {found_ue.get('nome')}")
        print(f" Marchio:              {found_ue.get('brand')}")
        print(f" Famiglia Catalogo:    {found_ue.get('famiglia_catalogo') or found_ue.get('serie')}")
        print(f" Tipologia:            {found_ue.get('tipo_sistema')} ({found_ue.get('porte_attacchi')} attacchi)")
        print(f" Potenza / Gas:        {found_ue.get('potenza_nominale_kw')} kW | Refrigerante: {found_ue.get('refrigerante')}")
        print(f" Prezzi:               Listino: {found_ue.get('prezzo_listino')} € | Netto PT: {found_ue.get('prezzo_netto')} €")
        print(f" Pagina Catalogo:      P.{found_ue.get('pagina_catalogo')}")
        
        comb_taglie = found_ue.get("combinazioni_ammesse_taglie", [])
        if comb_taglie:
            print(f"\n Combinazioni Taglie Ammesse: {', '.join(comb_taglie)}")

        fam_ui = found_ue.get("famiglie_ui_compatibili") or found_ue.get("serie_ui_compatibili", [])
        if fam_ui:
            print(f" Famiglie UI Compatibili:     {', '.join(fam_ui)}")

        modelli_ui = found_ue.get("modelli_ui_compatibili", [])
        if modelli_ui:
            print(f" Modelli UI Compatibili ({len(modelli_ui)}):  {', '.join(modelli_ui[:15])}{' ...' if len(modelli_ui) > 15 else ''}")

        kits = found_ue.get("kit_preconfigurati", [])
        if kits:
            print(f"\n Kit Commerciali Disponibili a Catalogo ({len(kits)}):")
            for k in kits:
                comps = [f"{c.get('nome', '')} [{c.get('codice_pt')}] [{c.get('tag_btu', str(c.get('taglia_btu', 9000)) + ' btu')}] ({c.get('famiglia_catalogo', '')})" for c in k.get("componenti_ui", [])]
                print(f"   • Kit: {k.get('nome_kit')} (Config: {k.get('configurazione')}) - Prezzo: {k.get('totale_prezzo_netto')} €")
                for comp in comps:
                    print(f"       -> UI: {comp}")

    if found_ui:
        if found_ue:
            print("\n-----------------------------------------------------------------------")
        print("                       SCHEDA UNITA INTERNA (UI)                       ")
        print("=======================================================================")
        print(f" Codice PT:            {found_ui.get('codice_pt')} (MPN: {found_ui.get('codice_mfg') or '-'})")
        print(f" Descrizione:          {found_ui.get('nome')}")
        print(f" Marchio:              {found_ui.get('brand')}")
        print(f" Famiglia Catalogo:    {found_ui.get('famiglia_catalogo') or found_ui.get('serie')}")
        print(f" Tipologia:            {found_ui.get('tipologia')}")
        print(f" Taglia / Tag BTU:     {found_ui.get('tag_btu', str(found_ui.get('taglia_btu')) + ' btu')} ({found_ui.get('taglia_btu')} BTU - {found_ui.get('taglia_kw')} kW)")
        print(f" Prezzi:               Listino: {found_ui.get('prezzo_listino')} € | Netto PT: {found_ui.get('prezzo_netto')} €")
        print(f" Pagina Catalogo:      P.{found_ui.get('pagina_catalogo')}")

        ue_compatibili = found_ui.get("unita_esterne_compatibili", [])
        print(f"\n Unità Esterne Compatibili a Catalogo ({len(ue_compatibili)}):")
        for ue in ue_compatibili[:10]:
            print(f"   • [{ue.get('codice_pt')}] {ue.get('codice_mfg') or '-'} | {ue.get('tipo_sistema')} | {ue.get('famiglia_catalogo') or ue.get('serie')} | {ue.get('prezzo_netto')} €")
        if len(ue_compatibili) > 10:
            print(f"     ... e altre {len(ue_compatibili) - 10} Unità Esterne compatibili.")
    print("=======================================================================\n")

def query_brand(data, brand_str: str):
    b = brand_str.strip().upper()
    meta = data.get("metadata") or data.get("_metadata") or {}
    brands = meta.get("marchi") or data.get("marchi") or {}

    if b not in brands:
        print(f"\n[INFO] Marchio '{brand_str}' non trovato. Marchi disponibili:")
        print(", ".join(sorted(brands.keys())))
        return

    b_info = brands[b]
    fams = b_info.get("famiglie_catalogo_censite") or b_info.get("serie_commerciali") or []
    print("=======================================================================")
    print(f"                      RIEPILOGO MARCHIO: {b}                           ")
    print("=======================================================================")
    print(f" • Unità Esterne a Catalogo: {b_info.get('totale_unita_esterne')}")
    print(f" • Unità Interne a Catalogo: {b_info.get('totale_unita_interne')}")
    print(f" • Kit Commerciali Pronti:   {b_info.get('totale_kit_preconfigurati')}")
    print(f" • Famiglie Catalogo:        {', '.join(fams)}")
    print("=======================================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Query Matrice Compatibilità Climatizzatori 2026")
    parser.add_argument("query", nargs="?", help="Codice PT (es. 50202171) o MPN (es. 2MXM40A)")
    parser.add_argument("--brand", "-b", help="Filtra per Marchio (es. DAIKIN, MITSUBISHI, SAMSUNG)")
    parser.add_argument("--family", "-f", help="Filtra per Famiglia Catalogo (es. PERFERA, EMURA, WINDFREE, ETHEREA)")
    parser.add_argument("--stats", "-s", action="store_true", help="Mostra statistiche generali della matrice")

    args = parser.parse_args()
    data = load_matrix()

    if args.stats:
        print_stats(data)
    elif args.brand:
        query_brand(data, args.brand)
    elif args.family:
        query_family(data, args.family)
    elif args.query:
        query_code(data, args.query)
    else:
        print_stats(data)

if __name__ == "__main__":
    main()
