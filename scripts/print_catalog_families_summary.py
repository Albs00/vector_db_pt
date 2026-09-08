import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('Knowledge/catalog_extracted_family_candidates.json', 'r', encoding='utf-8') as f:
        pages = json.load(f)

    # Group by brand
    by_brand = {}
    for p in pages:
        b = p['brand']
        if b not in by_brand:
            by_brand[b] = []
        by_brand[b].append(p)

    for b, p_list in sorted(by_brand.items()):
        p_nums = [p['page'] for p in p_list]
        total_items = sum(p['item_count'] for p in p_list)
        print(f"\n=======================================================")
        print(f"=== BRAND: {b} (Pages {min(p_nums)}-{max(p_nums)}, Items: {total_items}) ===")
        print(f"=======================================================")
        for p in p_list:
            cand_texts = [c['text'] for c in p['candidates'] if len(c['text']) > 2 and not c['text'].startswith('CONDIZION')][:5]
            sample_it = [it.split('(')[0].strip() for it in p['sample_items'][:3]]
            print(f"  Page {p['page']:3d} | Headers: {cand_texts}")
            print(f"            Samples: {sample_it}")

if __name__ == '__main__':
    main()
