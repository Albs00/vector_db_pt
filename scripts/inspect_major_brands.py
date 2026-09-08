import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    with open('Knowledge/all_catalog_families_raw.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    for b in ['PANASONIC', 'TOSHIBA', 'MIDEA', 'HISENSE', 'KOSAMI', 'HAIER', 'SAMSUNG', 'LG']:
        print(f"\n=======================================================")
        print(f"=== {b} ===")
        print(f"=======================================================")
        for p_info in data.get(b, []):
            hdrs = [h for h in p_info['headers'] if not h.isdigit() and len(h) > 2]
            p = p_info['page']
            samples = [s.split('(')[0].strip() for s in p_info.get('sample_items', [])[:2]]
            print(f"  Page {p:3d}: {hdrs[:4]}")
            if samples:
                print(f"            Samples: {samples}")

if __name__ == '__main__':
    main()
