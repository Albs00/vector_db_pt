import pymupdf
import json
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)

    # Let's inspect pages 468 to 626
    ac_items_by_page = defaultdict(list)
    for it in items:
        p = it.get('primary_page')
        if p and 468 <= p <= 630:
            ac_items_by_page[p].append(it)

    print(f"Total AC pages populated in unified_catalog: {len(ac_items_by_page)}")
    
    doc = pymupdf.open('Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf')

    page_family_map = {}

    for page_num in range(468, 627):
        p_idx = page_num - 1 # 0-indexed
        page = doc[p_idx]
        text = page.get_text('text')
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Items on this page
        page_items = ac_items_by_page.get(page_num, [])
        brands = list(set(it.get('brand') for it in page_items if it.get('brand')))
        
        print(f"\n==================== PAGE {page_num} (Brands: {', '.join(brands)}) [Items: {len(page_items)}] ====================")
        # Print first 25 non-trivial lines from the page
        filtered_lines = [
            l for l in lines 
            if not l.isdigit() 
            and l not in ['INDICE FOTOGRAFICO', 'INDICE DETTAGLIATO', 'INDICE PER MARCHIO', 'CONDIZIONAMENTO', 'COMMERCIALI', 'RESIDENZIALI', 'MODELLO', 'CODICE', 'Prezzo  €', 'Tubi', 'Kw - Classe Prezzo Unità € Prezzo TOT €', 'Kw - Classe']
            and len(l) > 2
        ]
        print("Header & prominent lines:")
        for l in filtered_lines[:15]:
            print(f"  - {l}")
        
        if page_items:
            print("Sample item names:")
            for it in page_items[:4]:
                print(f"    * [{it.get('code')}] {it.get('name')}")

if __name__ == '__main__':
    main()
