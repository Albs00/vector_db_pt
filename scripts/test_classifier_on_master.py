import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

with open('Knowledge/catalog_official_families_2026.json', 'r', encoding='utf-8') as f:
    families_db = json.load(f)

def detect_catalog_family(brand: str, name: str, mfg_code: str = "", page: int = None, cat_path: str = ""):
    b = (brand or "").strip().upper()
    n = (name or "").strip().upper()
    m = (mfg_code or "").strip().upper()
    full_text = f"{n} {m}"
    
    # 1. Direct check for Senza Unita Esterna
    if any(k in full_text for k in ["SENZA UNITA ESTERNA", "S/UE", "MONOBLOCCO", "UNICO", "APOLLO", "FK260", "FK360", "FK261", "FK361"]):
        for fam in families_db.get("SENZA_UNITA_ESTERNA", []):
            if any(k in full_text for k in fam["keywords"]):
                return fam["name"], fam["type"], fam["id"]

    # 2. Check brand specific families
    brand_fams = families_db.get(b, [])
    
    # Check page-aware match first if primary_page is known
    if page:
        for fam in brand_fams:
            if page in fam.get("pages", []):
                if any(k in full_text for k in fam.get("keywords", [])):
                    return fam["name"], fam["type"], fam["id"]
                    
    # Check keyword / prefix matches for the brand
    for fam in brand_fams:
        if any(k in full_text for k in fam.get("keywords", [])):
            return fam["name"], fam["type"], fam["id"]
            
    # Check if page is within a brand section and assign family by page header
    if page:
        for fam in brand_fams:
            if page in fam.get("pages", []):
                return fam["name"], fam["type"], fam["id"]

    # If brand has fallback family
    if brand_fams:
        # Check general type
        if "CANALIZZ" in full_text:
            for fam in brand_fams:
                if fam["type"] == "CANALIZZATO":
                    return fam["name"], fam["type"], fam["id"]
        if "CASSETTA" in full_text:
            for fam in brand_fams:
                if "CASSETTA" in fam["type"]:
                    return fam["name"], fam["type"], fam["id"]
        if "CONSOLE" in full_text or "PAVIMENTO" in full_text:
            for fam in brand_fams:
                if "CONSOLE" in fam["type"]:
                    return fam["name"], fam["type"], fam["id"]
        if "MULTI" in full_text or "ATT" in full_text:
            for fam in brand_fams:
                if fam["type"] == "MULTI_SPLIT":
                    return fam["name"], fam["type"], fam["id"]

    # Generic fallback
    return f"{b} SERIE COMMERCIALE", "PARETE", f"{b}_GENERIC"

def test_on_master():
    with open('Knowledge/climatizzatori_compatibilita_master.json', 'r', encoding='utf-8') as f:
        master = json.load(f)

    ue_dict = master.get("unita_esterne", {})
    ui_dict = master.get("unita_interne", {})
    
    print(f"Master file loaded: {len(ue_dict)} UEs, {len(ui_dict)} UIs.")
    
    ue_fams = Counter()
    ui_fams = Counter()
    
    for ue_code, ue in ue_dict.items():
        b = ue.get("brand", "")
        n = ue.get("nome", "")
        m = ue.get("codice_mfg", "")
        p = ue.get("pagina_catalogo")
        fam, ftype, fid = detect_catalog_family(b, n, m, p)
        ue_fams[(b, fam)] += 1
        
    for ui_code, ui in ui_dict.items():
        b = ui.get("brand", "")
        n = ui.get("nome", "")
        m = ui.get("codice_mfg", "")
        p = ui.get("pagina_catalogo")
        fam, ftype, fid = detect_catalog_family(b, n, m, p)
        ui_fams[(b, fam)] += 1
        
    print("\nTop 25 UE Families detected:")
    for (b, fam), cnt in ue_fams.most_common(25):
        print(f"  [{b:12s}] {fam:45s}: {cnt:4d} UEs")
        
    print("\nTop 25 UI Families detected:")
    for (b, fam), cnt in ui_fams.most_common(25):
        print(f"  [{b:12s}] {fam:45s}: {cnt:4d} UIs")

if __name__ == '__main__':
    test_on_master()
