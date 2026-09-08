"""
sync_all_catalog_specs.py
Sincronizzazione master unificata di TUTTE le specifiche tabellari certificate estratte dal Catalogo PDF 2026:
  1. Climatizzazione (2.824 record: UE rigorosamente a kW, UI a BTU e kW)
  2. Caldaie (404 record: kW nominale certificato, zero BTU)
  3. Scaldabagni (527 record: litri, gas MET/GPL, camera stagna/aperta, zero BTU)
  4. Ventilconvettori (485 record: taglia modello, kW freddo, kW caldo, zero BTU)
  5. Pompe di Calore & Sistemi Ibridi (909 record: kW [F - C], litri accumulo, tubazioni, zero BTU)

Aggiorna:
  - Knowledge/unified_catalog_master.json
  - Knowledge/vector_db/exact_code_lookup.json
"""

import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
LOOKUP_PATH = os.path.join(BASE_DIR, "Knowledge", "vector_db", "exact_code_lookup.json")

CLIMA_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_extracted_specs.json")
BOILER_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_boiler_specs.json")
HEATER_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_water_heater_specs.json")
FANCOIL_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_fancoil_specs.json")
HEATPUMP_SPECS_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_pdf_heatpump_specs.json")

def load_json_safe(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def sync_all_specs():
    print("=================================================================")
    print("  SINCRONIZZAZIONE GLOBALE SPECIFICHE TABELLARI NEL MASTER CATALOG")
    print("=================================================================\n")

    clima_specs = load_json_safe(CLIMA_SPECS_PATH)
    boiler_specs = load_json_safe(BOILER_SPECS_PATH)
    heater_specs = load_json_safe(HEATER_SPECS_PATH)
    fancoil_specs = load_json_safe(FANCOIL_SPECS_PATH)
    heatpump_specs = load_json_safe(HEATPUMP_SPECS_PATH)

    print(f"Caricate specifiche:")
    print(f"  • Climatizzazione:      {len(clima_specs)} record")
    print(f"  • Caldaie:              {len(boiler_specs)} record")
    print(f"  • Scaldabagni:          {len(heater_specs)} record")
    print(f"  • Ventilconvettori:     {len(fancoil_specs)} record")
    print(f"  • Pompe di Calore/Ibr:  {len(heatpump_specs)} record")
    print()

    with open(MASTER_PATH, "r", encoding="utf-8") as f:
        master = json.load(f)

    updated_count = 0
    purged_btu_count = 0

    for it in master:
        code = it["code"]
        name = (it.get("name") or "").upper()
        cat = (it.get("category_path") or "").upper()

        # 0. Riconoscimento Accessori e Componenti: MAI BTU, MAI SPECIFICHE MACCHINA
        is_accessory = (
            "ACCESSORI" in cat or
            "RICAMBI" in cat or
            it.get("is_accessory") or
            any(name.startswith(k) or f" {k}" in name for k in [
                "GRIGLIA", "PANNELLO", "COMANDO", "TERMOSTATO",
                "FILTRO", "RACCORDO", "KIT SCARIC", "KIT FUMI", "KIT SDOPP", "KIT COASS",
                "KIT RACC", "KIT TUBI", "VALVOLA", "DIMA", "CONTROCASSA", "CASSA COPERTURA",
                "PIEDINI", "DEFLETTORE", "SONDA", "TAPPO", "BASETTA", "CAVO", "SCHEDA",
                "CENTRALINA", "MOTORE ELET", "BRUCIATORE", "DEUMIDIFICATORE", "ESTENS GARANZIA"
            ])
        ) and not any(k in name for k in ["VENTILCONV", "CALDAIA", "SCALDABAGNO", "CLIMATIZZATORE"])

        if is_accessory:
            it["is_ui"] = False
            it["is_ue"] = False
            it["is_boiler"] = False
            it["is_scaldabagno"] = False
            it["is_ventilconvettore"] = False
            it["is_pompa_calore"] = False
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            it["taglia_kw"] = None
            it["tag_kw"] = None
            it["tag_kw_display"] = None
            it["kw_freddo"] = None
            it["kw_caldo"] = None
            it["tags"] = []

        # 1. CLIMATIZZAZIONE (PER LE UE RIGOROSAMENTE KW, PER LE UI RIGOROSAMENTE BTU)
        elif code in clima_specs:
            spec = clima_specs[code]
            if spec.get("is_ue"):
                it["is_ue"] = True
                it["is_ui"] = False
                it["taglia_btu"] = None
                it["tag_btu"] = None
                it["tag_btu_display"] = None
                it["kw_freddo"] = None
                it["kw_caldo"] = None
                kw = spec.get("kw")
                if kw:
                    it["taglia_kw"] = kw
                    it["tag_kw"] = f"{kw} kW"
                    it["tag_kw_display"] = f"{kw} kW"
                    it["tags"] = [f"{kw} kW"]
            elif spec.get("is_ui"):
                it["is_ui"] = True
                it["is_ue"] = False
                it["taglia_btu"] = spec.get("btu")
                it["tag_btu"] = spec.get("tag_btu")
                it["tag_btu_display"] = spec.get("tag_btu_display")
                it["taglia_kw"] = spec.get("kw")
                it["tag_kw"] = None
                it["tag_kw_display"] = None
                it["kw_freddo"] = None
                it["kw_caldo"] = None
                it["tags"] = [spec.get("tag_btu"), spec.get("tag_btu_display")] if spec.get("tag_btu") else []
            updated_count += 1

        # 2. CALDAIE
        elif code in boiler_specs:
            spec = boiler_specs[code]
            it["is_boiler"] = True
            it["is_ui"] = False
            it["is_ue"] = False
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            kw = spec.get("kw")
            if kw:
                it["taglia_kw"] = kw
                it["tag_kw"] = f"{kw:g} kW"
                it["tag_kw_display"] = f"{kw:g} kW"
                it["tags"] = [f"{kw:g} kW"]
            updated_count += 1

        # 3. SCALDABAGNI
        elif code in heater_specs:
            spec = heater_specs[code]
            it["is_scaldabagno"] = True
            it["is_ui"] = False
            it["is_ue"] = False
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            it["capacita_litri"] = spec.get("capacita_litri")
            it["tag_litri"] = spec.get("tag_litri")
            it["gas"] = spec.get("gas")
            it["tipo_scaldabagno"] = spec.get("tipo_scaldabagno")
            it["camera"] = spec.get("camera")
            tags = [spec.get("tag_litri")]
            if spec.get("gas"):
                tags.append(spec.get("gas"))
            if spec.get("camera"):
                tags.append(spec.get("camera").replace("_", " "))
            it["tags"] = [t for t in tags if t]
            updated_count += 1

        # 4. VENTILCONVETTORI
        elif code in fancoil_specs:
            spec = fancoil_specs[code]
            it["is_ventilconvettore"] = True
            it["is_ui"] = False
            it["is_ue"] = False
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            it["taglia_modello"] = spec.get("taglia_modello")
            it["kw_freddo"] = spec.get("kw_freddo")
            it["kw_caldo"] = spec.get("kw_caldo")
            it["tag_kw"] = spec.get("tag_kw")
            it["tag_kw_display"] = spec.get("tag_kw_display")
            it["tags"] = [spec.get("tag_kw")]
            updated_count += 1

        # 5. POMPE DI CALORE & SISTEMI IBRIDI
        if code in heatpump_specs:
            spec = heatpump_specs[code]
            it["is_pompa_calore"] = True
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            if spec.get("is_ue"):
                it["is_ue"] = True
                it["is_ui"] = False
            elif spec.get("is_ui"):
                it["is_ui"] = True
                it["is_ue"] = False
            if spec.get("kw_freddo"):
                it["kw_freddo"] = spec.get("kw_freddo")
            if spec.get("kw_caldo"):
                it["kw_caldo"] = spec.get("kw_caldo")
            if spec.get("tag_kw"):
                it["tag_kw"] = spec.get("tag_kw")
                it["tag_kw_display"] = spec.get("tag_kw_display")
            if spec.get("litri"):
                it["litri"] = spec.get("litri")
                it["tag_litri"] = spec.get("tag_litri")
            if spec.get("tubi"):
                it["tubi"] = spec.get("tubi")
            tags = []
            if it.get("tag_kw"): tags.append(it.get("tag_kw"))
            if it.get("tag_litri"): tags.append(it.get("tag_litri"))
            if it.get("tubi"): tags.append(f"Tubi {it.get('tubi')}")
            if tags:
                it["tags"] = tags
            updated_count += 1

        # CONTROLLO DI SICUREZZA GLOBALE: Purga BTU per qualsiasi articolo che non sia UI Clima
        is_true_ui_clima = (
            it.get("is_ui") and 
            not it.get("is_pompa_calore") and 
            not it.get("is_boiler") and 
            not it.get("is_scaldabagno") and 
            not it.get("is_ventilconvettore") and
            any(k in cat for k in ["CONDIZIONAMENTO > RESIDENZIALI", "CONDIZIONAMENTO > COMMERCIALI"])
        )
        if not is_true_ui_clima and it.get("taglia_btu"):
            it["taglia_btu"] = None
            it["tag_btu"] = None
            it["tag_btu_display"] = None
            purged_btu_count += 1

        # Aggiorna search_text con i dati tecnici strutturati ufficiali
        st = it.get("search_text") or ""
        if "SPECIFICHE TECNICHE CATALOGO:" in st:
            st = st.split("SPECIFICHE TECNICHE CATALOGO:")[0].strip()

        tech_specs = []
        if it.get("is_scaldabagno"):
            if it.get("tag_litri"): tech_specs.append(f"Capacità: {it.get('tag_litri')}")
            if it.get("gas"): tech_specs.append(f"Combustibile: {it.get('gas')}")
            if it.get("camera"): tech_specs.append(f"Camera: {it.get('camera').replace('_', ' ')}")
            if it.get("tipo_scaldabagno"): tech_specs.append(f"Tipo: {it.get('tipo_scaldabagno').replace('_', ' ')}")
        elif it.get("is_ventilconvettore"):
            if it.get("taglia_modello"): tech_specs.append(f"Modello: {it.get('taglia_modello')}")
            if it.get("tag_kw"): tech_specs.append(f"Resa: {it.get('tag_kw')}")
        elif it.get("is_boiler"):
            if it.get("tag_kw"): tech_specs.append(f"Potenza: {it.get('tag_kw')}")
        elif it.get("is_pompa_calore"):
            if it.get("tag_kw"): tech_specs.append(f"Resa: {it.get('tag_kw')}")
            if it.get("tag_litri"): tech_specs.append(f"Accumulo: {it.get('tag_litri')}")
            if it.get("tubi"): tech_specs.append(f"Tubi: {it.get('tubi')}")
        elif it.get("is_ue") and it.get("tag_kw"):
            tech_specs.append(f"Unità Esterna Clima: {it.get('tag_kw')}")
        elif it.get("is_ui"):
            if it.get("tag_btu"): tech_specs.append(f"Unità Interna Clima: {it.get('tag_btu')}")
            if it.get("taglia_kw"): tech_specs.append(f"{it.get('taglia_kw')} kW")

        if tech_specs:
            st += "\nSPECIFICHE TECNICHE CATALOGO: " + " | ".join(tech_specs)
            it["search_text"] = st

    print(f"Articoli aggiornati con specifiche certificate: {updated_count}")
    print(f"Articoli bonificati da falsi BTU (UE, PDC, Caldaie, Scaldabagni): {purged_btu_count}")

    with open(MASTER_PATH, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)
    print(f"Master catalog salvato: {MASTER_PATH}")

    # Rigenera exact_code_lookup.json pre-arricchito
    print("Rigenerazione exact_code_lookup.json...")
    lookup = {}
    for it in master:
        c = str(it.get("code") or "").strip()
        m = str(it.get("mfg_code") or "").strip()
        
        lookup_entry = {
            "id": it.get("id"),
            "code": c,
            "mfg_code": m,
            "name": it.get("name"),
            "brand": it.get("brand"),
            "category_path": it.get("category_path"),
            "gross_price": it.get("gross_price"),
            "net_price": it.get("net_price"),
            "in_catalog_pdf": it.get("in_catalog_pdf"),
            "primary_page": it.get("primary_page"),
            "catalog_pages": it.get("catalog_pages", []),
            "related_accessories_count": it.get("related_accessories_count", 0),
            "image_url": it.get("image_url"),
            "is_boiler": it.get("is_boiler", False),
            "is_scaldabagno": it.get("is_scaldabagno", False),
            "is_ventilconvettore": it.get("is_ventilconvettore", False),
            "is_pompa_calore": it.get("is_pompa_calore", False),
            "is_ue": it.get("is_ue", False),
            "is_ui": it.get("is_ui", False),
            "taglia_kw": it.get("taglia_kw"),
            "taglia_btu": it.get("taglia_btu"),
            "tag_kw": it.get("tag_kw"),
            "tag_btu": it.get("tag_btu"),
            "capacita_litri": it.get("capacita_litri") or it.get("litri"),
            "tag_litri": it.get("tag_litri"),
            "litri": it.get("litri") or it.get("capacita_litri"),
            "tubi": it.get("tubi"),
            "gas": it.get("gas"),
            "camera": it.get("camera"),
            "tipo_scaldabagno": it.get("tipo_scaldabagno"),
            "taglia_modello": it.get("taglia_modello"),
            "kw_freddo": it.get("kw_freddo"),
            "kw_caldo": it.get("kw_caldo"),
            "tags": it.get("tags", [])
        }

        if c:
            lookup[c.lower()] = lookup_entry
            c_clean = c.replace(" ", "").replace("-", "").replace(".", "").replace("/", "").lower()
            if c_clean:
                lookup[c_clean] = lookup_entry

        if m:
            lookup[m.lower()] = lookup_entry
            m_clean = m.replace(" ", "").replace("-", "").replace(".", "").replace("/", "").lower()
            if m_clean:
                lookup[m_clean] = lookup_entry

    with open(LOOKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)
    print(f"Indice di lookup salvato: {LOOKUP_PATH} ({len(lookup)} chiavi indicizzate)")

if __name__ == "__main__":
    sync_all_specs()
