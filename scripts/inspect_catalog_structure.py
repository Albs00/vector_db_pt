import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('Knowledge/catalog_raw_page_structure.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total pages in raw structure: {len(data)}")

# Map each page
pages_info = []
for entry in data:
    p = entry.get('page')
    brands = entry.get('brands', [])
    titles = [t.get('text', '').strip() for t in entry.get('prominent_titles', []) if t.get('text')]
    samples = entry.get('sample_items', [])
    pages_info.append((p, brands, titles, samples))

pages_info.sort(key=lambda x: x[0])

out_lines = [f"Total pages in raw structure: {len(data)}"]
for p, brands, titles, samples in pages_info:
    b_str = ", ".join(brands) if brands else "UNKNOWN"
    clean_titles = [t for t in titles if not t.isdigit() and len(t) > 2]
    dedup_titles = []
    for t in clean_titles:
        if t not in dedup_titles:
            dedup_titles.append(t)
    out_lines.append(f"P.{p:3d} | Brands: {b_str:<15} | Titles: {dedup_titles[:4]}")
    if samples:
        out_lines.append(f"       Samples: {samples[:3]}")

with open('Knowledge/catalog_pages_full_scan.txt', 'w', encoding='utf-8') as out_f:
    out_f.write('\n'.join(out_lines))
print("Saved Knowledge/catalog_pages_full_scan.txt (UTF-8)")
