import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

from test_catalog_families import classify_family

with open('Knowledge/unified_catalog_master.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

ac_items = [it for it in items if any(k in (it.get('category_path') or '').upper() for k in ['RESIDENZIALI', 'COMMERCIALI', 'SENZA UNIT'])]

unmatched_by_brand = Counter()
unmatched_samples = {}

for it in ac_items:
    brand = it.get('brand', '')
    name = it.get('name', '')
    page = it.get('primary_page')
    fam_name, _ = classify_family(brand, name, page)
    if fam_name == "ALTRE SERIE":
        unmatched_by_brand[brand] += 1
        if brand not in unmatched_samples:
            unmatched_samples[brand] = []
        if len(unmatched_samples[brand]) < 6:
            unmatched_samples[brand].append((page, name))

print("Unmatched items count by brand:")
for b, count in unmatched_by_brand.most_common(20):
    print(f"\n[{b}] ({count} items):")
    for p, n in unmatched_samples.get(b, []):
        print(f"   P.{p}: {n}")
