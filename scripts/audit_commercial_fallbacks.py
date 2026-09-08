import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

with open('Knowledge/climatizzatori_compatibilita_master.json', 'r', encoding='utf-8') as f:
    master = json.load(f)

ues = master.get('unita_esterne', {})
uis = master.get('unita_interne', {})

print("==================================================")
print("  AUDIT FALLBACKS 'SERIE COMMERCIALE' IN UE E UI  ")
print("==================================================")

# 1. Analisi UE fallback
ue_fallbacks = [u for u in ues.values() if 'COMMERCIALE' in u.get('famiglia_catalogo', '')]
print(f"\n1. Totale UE con 'COMMERCIALE': {len(ue_fallbacks)} su {len(ues)}")
ue_brands = Counter(u.get('brand') for u in ue_fallbacks)
for b, count in ue_brands.most_common(10):
    print(f"   - {b:<15}: {count} articoli")
    # Mostra 3 campioni per brand
    samples = [u for u in ue_fallbacks if u.get('brand') == b][:3]
    for s in samples:
        print(f"       [{s.get('codice_pt')}] {s.get('nome')} | MFG: {s.get('codice_mfg')} | P.{s.get('pagina_catalogo')}")

# 2. Analisi UI fallback
ui_fallbacks = [u for u in uis.values() if 'COMMERCIALE' in u.get('famiglia_catalogo', '')]
print(f"\n2. Totale UI con 'COMMERCIALE': {len(ui_fallbacks)} su {len(uis)}")
ui_brands = Counter(u.get('brand') for u in ui_fallbacks)
for b, count in ui_brands.most_common(10):
    print(f"   - {b:<15}: {count} articoli")
    samples = [u for u in ui_fallbacks if u.get('brand') == b][:3]
    for s in samples:
        print(f"       [{s.get('codice_pt')}] {s.get('nome')} | MFG: {s.get('codice_mfg')} | P.{s.get('pagina_catalogo')}")
