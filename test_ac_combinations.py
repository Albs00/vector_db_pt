"""
test_ac_combinations.py
Verifica sistematica della compatibilità climatizzatori:
- Unità Esterne (Mono, Dual, Trial, Quadri) con kit commerciali e tabelle
- Unità Interne con matching verso Unità Esterne compatibili
"""

import sys
from accessory_engine import AccessoryEngine

sys.stdout.reconfigure(encoding='utf-8')

def main():
    engine = AccessoryEngine()

    test_units = [
        {"code": "50202171", "label": "Daikin Dual Split 2MXM40A9", "type": "UE"},
        {"code": "50420964", "label": "Daikin Quadri Split 4MXM80A8", "type": "UE"},
        {"code": "50131273", "label": "Haier Monosplit UE 1U25S2SM1FA", "type": "UE"},
        {"code": "50137008", "label": "Aermec Dual Split MPG 520", "type": "UE"},
        {"code": "50148936", "label": "Daikin UI Parete Emura 3 FTXJ25AW", "type": "UI"},
    ]

    all_passed = True
    print("=================================================================")
    print("      VERIFICA COMBINAZIONI CLIMA & TABELLE CATALOGO 2026        ")
    print("=================================================================\n")

    for t in test_units:
        code = t["code"]
        rel = engine.get_relations(code)
        item = engine._by_code.get(code, {})
        name = item.get("name", "N/D")
        brand = item.get("brand", "N/D")
        groups = rel.get("accessory_groups", [])

        kits = rel.get("kits", [])
        single_units = rel.get("single_units", [])
        real_accessories = rel.get("accessory_groups", [])

        print(f"TEST [{code}] - {t['label']} ({brand})")
        print(f"  Nome Articolo: {name}")
        print(f"  Tipo: {rel.get('product_type')} | Kit: {len(kits)} | Unità: {len(single_units)} | Accessori: {sum(len(g['items']) for g in real_accessories)} ({len(real_accessories)} gruppi)")

        if t["type"] == "UE":
            # Per una Unità Esterna dobbiamo avere kit compatibili oppure singole unità abbinabili
            if len(kits) > 0 or len(single_units) > 0:
                print("  STATUS: [PASS] - Combinazioni / Kit separati con successo!")
                if len(kits) > 0:
                    print(f"    🧩 Kit Preconfigurati: {len(kits)} bundle")
                    for it in kits[:2]:
                        conf = f" [{it.get('configuration')}]" if it.get('configuration') else ""
                        print(f"       • [{it.get('code')}] {it.get('name')}{conf} - Netto: {it.get('net_price')} € (P.{it.get('catalog_page')})")
                if len(single_units) > 0:
                    print(f"    ❄️ Singole Unità Interne Abbinabili: {len(single_units)} unità certificate")
                    for it in single_units[:2]:
                        print(f"       • [{it.get('code')}] {it.get('name')} - Netto: {it.get('net_price')} €")
            else:
                print("  STATUS: [FAIL] - Nessun kit o UI compatibile trovato!")
                all_passed = False
        elif t["type"] == "UI":
            if len(single_units) > 0:
                print("  STATUS: [PASS] - Unità Esterne compatibili separate con successo!")
                print(f"    🏢 Unità Esterne Abbinabili: {len(single_units)} modelli")
                for it in single_units[:2]:
                    print(f"       • [{it.get('code')}] {it.get('name')} (P.{it.get('catalog_page')})")
            else:
                print("  STATUS: [FAIL] - Nessuna UE compatibile trovata!")
                all_passed = False

        print("-----------------------------------------------------------------\n")

    if all_passed:
        print("TUTTI I TEST CLIMA SONO STATI SUPERATI CON SUCCESSO! [ALL PASS]")
    else:
        print("ALCUNI TEST SONO FALLITI.")

if __name__ == "__main__":
    main()
