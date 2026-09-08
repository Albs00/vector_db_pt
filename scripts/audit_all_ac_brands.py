import pymupdf
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def audit_all_brands():
    doc = pymupdf.open('Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf')
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)

    brand_ranges = [
        ("PANASONIC", 510, 522),
        ("TOSHIBA", 523, 538),
        ("MIDEA", 539, 547),
        ("HISENSE", 548, 552),
        ("KOSAMI", 553, 555),
        ("HAIER", 556, 570),
        ("SAMSUNG", 571, 581),
        ("LG", 582, 593),
        ("FERROLI", 594, 595),
        ("BAXI", 596, 599),
        ("ARISTON", 600, 603),
        ("BERETTA", 604, 604),
        ("RIELLO", 605, 608),
        ("BOSCH", 609, 612),
        ("IMMERGAS", 613, 614),
        ("HSD", 615, 616),
        ("VAILLANT", 617, 619),
        ("AERMEC", 620, 623),
        ("SENZA UNITA ESTERNA", 624, 626)
    ]

    summary_brand_families = {}

    for brand, start_p, end_p in brand_ranges:
        print(f"\n=================================================================")
        print(f"=== {brand} (Pages {start_p} to {end_p}) ===")
        print(f"=================================================================")
        brand_families = []
        for p in range(start_p, end_p + 1):
            page = doc[p - 1]
            text = page.get_text('text')
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Filter headers
            headers = []
            for l in lines[:30]:
                if l.isdigit() or len(l) < 3:
                    continue
                if any(x in l for x in ['INDICE', 'MODELLO', 'CODICE', 'DISP', 'Prezzo', 'Kw -', 'Tubi', 'Classe', 'TABELLA COMBINAZIONI']):
                    continue
                if l.startswith('CONDIZIONATORI'):
                    continue
                headers.append(l)
                
            p_items = [it for it in items if it.get('primary_page') == p]
            sample_names = [it.get('name') for it in p_items[:3]]
            
            print(f"Page {p:3d}: {headers[:4]}")
            if sample_names:
                print(f"         Samples: {sample_names}")
                
            brand_families.append({
                "page": p,
                "headers": headers[:6],
                "sample_items": sample_names
            })
        summary_brand_families[brand] = brand_families

    with open('Knowledge/all_catalog_families_raw.json', 'w', encoding='utf-8') as f:
        json.dump(summary_brand_families, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    audit_all_brands()
