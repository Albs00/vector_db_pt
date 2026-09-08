import pymupdf
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def analyze_page_blocks(start_page=468, end_page=626):
    doc = pymupdf.open('Knowledge/CAT2600_CATALOGO_2026-V4pdf.pdf')
    with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
        items = json.load(f)
        
    items_by_page = {}
    for it in items:
        p = it.get('primary_page')
        if p and start_page <= p <= end_page:
            items_by_page.setdefault(p, []).append(it)

    results = []

    for page_num in range(start_page, end_page + 1):
        p_idx = page_num - 1
        page = doc[p_idx]
        blocks = page.get_text("dict")["blocks"]
        
        # Extract prominent text spans (font size > 8, or uppercase)
        prominent = []
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    max_size = max(s["size"] for s in l["spans"]) if l["spans"] else 0
                    flags = l["spans"][0]["flags"] if l["spans"] else 0
                    # bold is flag & 2
                    is_bold = bool(flags & 2 or "bold" in (l["spans"][0]["font"].lower() if l["spans"] else ""))
                    if line_text and len(line_text) > 1 and max_size >= 9.0:
                        prominent.append({
                            "text": line_text,
                            "size": round(max_size, 1),
                            "bold": is_bold,
                            "bbox": [round(x, 1) for x in b["bbox"]]
                        })
        
        page_items = items_by_page.get(page_num, [])
        brands = list(set(it.get('brand') for it in page_items if it.get('brand')))
        item_names = [it.get('name') for it in page_items[:5]]
        
        results.append({
            "page": page_num,
            "brands": brands,
            "prominent_titles": prominent[:12],
            "item_count": len(page_items),
            "sample_items": item_names
        })

    with open('Knowledge/catalog_raw_page_structure.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"Extracted layout structure for {len(results)} pages into Knowledge/catalog_raw_page_structure.json")

if __name__ == '__main__':
    analyze_page_blocks()
