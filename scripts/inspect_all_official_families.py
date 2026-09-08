import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Knowledge/catalog_official_families_2026.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

print(f"Total Brands: {len(db)}")
total_fams = 0
for brand, fams in sorted(db.items()):
    total_fams += len(fams)
    print(f"\n=======================================================")
    print(f"BRAND: {brand} ({len(fams)} Famiglie)")
    print(f"=======================================================")
    for f in fams:
        fid = f.get('id', '')
        name = f.get('name', '')
        ftype = f.get('type', '')
        pages = f.get('pages', [])
        models = f.get('models_prefix', [])
        p_str = ", ".join(str(p) for p in pages) if pages else "N/D"
        m_str = ", ".join(models[:4]) if models else ""
        print(f"  • {name:<35} | Tipo: {ftype:<18} | Pagg: {p_str:<12} | Modelli: {m_str}")

print(f"\nTOTALE COMPLESSIVO FAMIGLIE CATALOGO: {total_fams}")
