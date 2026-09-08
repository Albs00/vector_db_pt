import pymupdf
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def inspect_brand_pages(brand_name, start_p, end_p):
    doc = pymupdf.open('Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf')
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)

    print(f"\n=======================================================")
    print(f"=== DETAILED AUDIT FOR BRAND: {brand_name} (Pages {start_p}-{end_p}) ===")
    print(f"=======================================================")

    for p in range(start_p, end_p + 1):
        page = doc[p - 1]
        text = page.get_text('text')
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Get items from unified_catalog for this page
        p_items = [it for it in items if it.get('primary_page') == p]
        
        print(f"\n--- PAGE {p} ---")
        # Print top lines
        header_lines = [
            l for l in lines[:35] 
            if not l.isdigit() 
            and l not in ['INDICE FOTOGRAFICO', 'INDICE DETTAGLIATO', 'INDICE PER MARCHIO', 'MODELLO', 'CODICE', 'DISP', 'DISPONIBILE']
            and 'Prezzo' not in l and 'Kw -' not in l and 'Tubi' not in l
        ]
        print("Page Prominent Text:")
        for hl in header_lines[:12]:
            print(f"   [HDR] {hl}")
            
        print(f"Catalog Items on Page {p} ({len(p_items)} items):")
        for it in p_items[:6]:
            print(f"   * [{it.get('code')}] {it.get('name')}")

if __name__ == '__main__':
    inspect_brand_pages("MITSUBISHI", 490, 509)
