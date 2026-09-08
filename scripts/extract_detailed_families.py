import pymupdf
import json
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

def extract_detailed_families():
    doc = pymupdf.open('Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf')
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)

    # Index items by primary_page
    items_by_page = defaultdict(list)
    for it in items:
        p = it.get('primary_page')
        if p and 468 <= p <= 630:
            items_by_page[p].append(it)

    catalog_families = []

    for page_num in range(468, 627):
        p_idx = page_num - 1
        page = doc[p_idx]
        
        # Get blocks
        text_dict = page.get_text("dict")
        blocks = text_dict["blocks"]
        
        # Find brand from page items or header text
        page_items = items_by_page.get(page_num, [])
        brand_counts = defaultdict(int)
        for it in page_items:
            b = it.get('brand')
            if b:
                brand_counts[b] += 1
        
        main_brand = max(brand_counts.keys(), key=lambda k: brand_counts[k]) if brand_counts else "UNKNOWN"
        
        # Extract title candidates
        # Look for text with font size >= 10, or bold, or styled banners
        candidates = []
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    line_str = " ".join(s["text"] for s in l["spans"]).strip()
                    if not line_str:
                        continue
                    max_size = max(s["size"] for s in l["spans"]) if l["spans"] else 0
                    font_names = " ".join(s["font"] for s in l["spans"]).lower()
                    is_bold = "bold" in font_names or (l["spans"][0]["flags"] & 2 != 0 if l["spans"] else False)
                    y0 = b["bbox"][1]
                    x0 = b["bbox"][0]
                    
                    # Ignore common noise
                    if line_str in ['INDICE FOTOGRAFICO', 'INDICE DETTAGLIATO', 'INDICE PER MARCHIO', 'MODELLO', 'CODICE', 'DISP', 'DISPONIBILE']:
                        continue
                    if line_str.isdigit() and len(line_str) <= 4:
                        continue
                    if 'Prezzo' in line_str or 'Classe' in line_str or 'Kw - Classe' in line_str:
                        continue
                        
                    if max_size >= 9.5 or (is_bold and max_size >= 8.5) or line_str.isupper():
                        candidates.append({
                            "text": line_str,
                            "size": round(max_size, 1),
                            "bold": is_bold,
                            "y0": round(y0, 1),
                            "x0": round(x0, 1)
                        })

        # Distinct item model names on this page
        item_names = [it.get('name', '') for it in page_items]
        
        catalog_families.append({
            "page": page_num,
            "brand": main_brand,
            "all_brands": list(brand_counts.keys()),
            "item_count": len(page_items),
            "candidates": candidates[:15],
            "sample_items": item_names[:8]
        })

    with open('Knowledge/catalog_extracted_family_candidates.json', 'w', encoding='utf-8') as f:
        json.dump(catalog_families, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(catalog_families)} pages candidates into Knowledge/catalog_extracted_family_candidates.json")

if __name__ == '__main__':
    extract_detailed_families()
