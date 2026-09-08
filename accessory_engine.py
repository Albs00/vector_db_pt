"""
accessory_engine.py
Motore di Compatibilità e Relazioni Tecniche per il Catalogo Puglia Termica 2026.
Risolve in modo intelligente:
  1. 'variants': Varianti di potenza, taglia o modello analogo dello stesso apparecchio (es. caldaia 24 kW vs 28 kW vs 34 kW).
  2. 'accessory_groups': Veri accessori tecnici compatibili suddivisi per categoria funzionale:
     - Caldaie: Fumisteria Coassiale 60/100, Fumisteria Sdoppiata 80/80, Defangatori magnetici 3/4", Dosatori polifosfati, Cronotermostati/Sonde, Dime di montaggio.
     - Climatizzatori: Staffe/Mensole unità esterna, Scarico condensa (tubi/pompe), Schede Wi-Fi e comandi, Unità abbinata.
     - Pompe / Autoclavi: Vasi espansione a membrana (24L/50L), Presscontrol elettronici, Valvole di ritegno/fondo, Raccordi 5 vie.
     - Scaldabagni: Fumisteria, Valvole di sicurezza e raccordi.
     - Cassette WC: Placche di comando dello stesso marchio/serie, Canotti di risciacquo e allacciamento.
     - Altri prodotti: Accessori co-presenti sulla stessa pagina (filtrando le varianti doppie).
"""

import sys
import os
import json
import re
from typing import Dict, Any, List, Optional
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "unified_catalog_master.json")
RULES_PATH = os.path.join(BASE_DIR, "Knowledge", "catalog_accessory_rules.json")
AC_COMBINATIONS_PATH = os.path.join(BASE_DIR, "Knowledge", "ac_outdoor_combinations.json")
BOILER_FLUE_RULES_PATH = os.path.join(BASE_DIR, "Knowledge", "boiler_flue_compatibility_rules.json")
AC_MASTER_PATH = os.path.join(BASE_DIR, "Knowledge", "climatizzatori_compatibilita_master.json")

class AccessoryEngine:
    def __init__(self, master_path: str = MASTER_PATH, rules_path: str = RULES_PATH, ac_comb_path: str = AC_COMBINATIONS_PATH, boiler_flue_path: str = BOILER_FLUE_RULES_PATH, ac_master_path: str = AC_MASTER_PATH):
        self.master_path = master_path
        self.rules_path = rules_path
        self.ac_comb_path = ac_comb_path
        self.boiler_flue_path = boiler_flue_path
        self.ac_master_path = ac_master_path
        self._master = None
        self._by_code = {}
        self._by_brand = defaultdict(list)
        self._by_page = defaultdict(list)
        self._rules = {}
        self._boiler_flue_rules = {}
        self._ac_combinations = {}
        self._ac_master_ues = {}
        self._ac_master_uis = {}
        self._ac_by_code = {}
        self._ac_by_mfg = {}
        self._ac_ui_to_ue = defaultdict(list)
        
        # Pre-indicizzazioni veloci per categorie universali di accessori
        self._defangatori_caldaia = []
        self._dosatori_caldaia = []
        self._vasi_autoclave = []
        self._presscontrol_pompa = []
        self._valvole_pompa = []
        self._staffe_clima = []
        self._scarico_clima = []
        self._placche_geberit = []
        self._placche_valsir = []

        self._load_and_index()

    def _load_and_index(self):
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as rf:
                    self._rules = json.load(rf)
            except Exception as e:
                print(f"[AccessoryEngine] Errore caricamento regole catalogo: {e}")

        if os.path.exists(self.boiler_flue_path):
            try:
                with open(self.boiler_flue_path, "r", encoding="utf-8") as bff:
                    self._boiler_flue_rules = json.load(bff)
            except Exception as e:
                print(f"[AccessoryEngine] Errore caricamento regole fumi caldaia: {e}")

        if os.path.exists(self.ac_master_path):
            try:
                with open(self.ac_master_path, "r", encoding="utf-8") as acm:
                    master_ac_dict = json.load(acm)
                    self._ac_master_ues = master_ac_dict.get("unita_esterne", {})
                    self._ac_master_uis = master_ac_dict.get("unita_interne", {})
                for ue_code, ue_data in self._ac_master_ues.items():
                    ue_code_clean = str(ue_code).strip()
                    self._ac_by_code[ue_code_clean] = ue_data
                    mfg = (ue_data.get("codice_mfg") or ue_data.get("mfg_code") or "").strip().upper()
                    if mfg:
                        self._ac_by_mfg[mfg] = ue_data
                for ui_code, ui_data in self._ac_master_uis.items():
                    ui_code_clean = str(ui_code).strip()
                    for ue_sum in ui_data.get("unita_esterne_compatibili", []):
                        self._ac_ui_to_ue[ui_code_clean].append((ue_sum, None))
            except Exception as e:
                print(f"[AccessoryEngine] Errore caricamento master AC: {e}")

        if os.path.exists(self.ac_comb_path) and not self._ac_master_ues:
            try:
                with open(self.ac_comb_path, "r", encoding="utf-8") as acf:
                    self._ac_combinations = json.load(acf)
                for ue_code, ue_data in self._ac_combinations.items():
                    ue_code_clean = str(ue_code).strip()
                    self._ac_by_code[ue_code_clean] = ue_data
                    mfg = (ue_data.get("mfg_code") or "").strip().upper()
                    if mfg:
                        self._ac_by_mfg[mfg] = ue_data
                    for kit in ue_data.get("ready_kits", []):
                        for comp in kit.get("ui_components", []):
                            c_code = str(comp.get("code") or "").strip()
                            if c_code:
                                self._ac_ui_to_ue[c_code].append((ue_data, kit))
                    for comp in ue_data.get("compatible_uis_sample", []):
                        c_code = str(comp.get("code") or "").strip()
                        if c_code:
                            self._ac_ui_to_ue[c_code].append((ue_data, None))
            except Exception as e:
                print(f"[AccessoryEngine] Errore caricamento combinazioni clima: {e}")

        if not os.path.exists(self.master_path):
            return

        with open(self.master_path, "r", encoding="utf-8") as f:
            self._master = json.load(f)

        for r in self._master:
            code = str(r.get("code") or "").strip()
            if not code:
                continue
            self._by_code[code] = r
            brand = (r.get("brand") or "").strip().upper()
            if brand:
                self._by_brand[brand].append(r)
            for p in r.get("catalog_pages", []):
                self._by_page[int(p)].append(r)

            name = (r.get("name") or "").upper()
            cat = (r.get("category_path") or "").upper()

            # 1. Defangatori compatti sotto-caldaia 3/4"
            if "DEFANGAT" in name and "3/4" in name and any(k in name for k in ["MAGNET", "COMPAT", "MINI", "XS", "SQUADRA", "DRITTO"]):
                self._defangatori_caldaia.append(r)

            # 2. Dosatori polifosfati
            if "DOSATORE" in name and "POLIFOSF" in name:
                self._dosatori_caldaia.append(r)

            # 3. Vasi espansione autoclave (24L, 50L)
            if "VASO ESPANSIONE" in name and any(k in name for k in [" 24", "LT 24", "ER 24", " 50", "LT 50"]) and not any(k in name for k in ["SOLAR", "PIATTO", "ERP"]):
                self._vasi_autoclave.append(r)

            # 4. Presscontrol per pompe
            if any(re.search(r'\b' + k + r'\b', name) for k in ["BRIO", "EASYPRESS", "PRESSCONTROL", "REGOLATORE ELETTRONICO"]) and not any(k in name for k in ["CASSETTA", "CAVO"]):
                self._presscontrol_pompa.append(r)

            # 5. Valvole ritegno / fondo / 5 vie
            if ("VALVOLA DI RITEGNO" in name or "VALVOLA DI FONDO" in name or "RACCORDO 5 VIE" in name) and any(k in name for k in ['1"', '1"1/4']):
                self._valvole_pompa.append(r)

            # 6. Staffe e mensole clima
            if "MENSOLE PER UNITA" in cat or ("STAFFA" in name and any(k in name for k in ["CLIMA", "CONDIZION", "REGOLABILE", "ANTIVIBR"])):
                self._staffe_clima.append(r)

            # 7. Scarico condensa clima
            if any(k in name for k in ["POMPA SCARICO CONDENSA", "TUBO SPIRALATO CONDENSA", "TUBO SCARICO CONDENSA"]):
                self._scarico_clima.append(r)

            # 8. Placche di comando Geberit
            if brand == "GEBERIT" and any(k in name for k in ["PLACCA", "SIGMA", "DELTA", "OMEGA"]):
                self._placche_geberit.append(r)

            # 9. Placche Valsir
            if brand == "VALSIR" and "PLACCA" in name:
                self._placche_valsir.append(r)

    def classify_product(self, item: Dict[str, Any]) -> str:
        """Determina la macro-famiglia tecnica del prodotto."""
        code = str(item.get("code") or "").strip()
        if code in self._ac_by_code or code in self._ac_ui_to_ue or code in self._ac_master_ues or code in self._ac_master_uis:
            return "AC"

        cat = (item.get("category_path") or "").upper()
        name = (item.get("name") or "").upper()

        # Boilers
        if any(k in cat for k in ["CALDAIE A GAS", "CALDAIE A CONDENSAZIONE", "MURALI A CONDENSAZIONE", "CALDAIE POLICOMBUSTIBILI", "CALDAIE A PELLET"]):
            if not any(k in cat for k in ["ACCESSORI", "FUMISTERIA"]):
                return "BOILER"

        # Climatizzatori
        if any(k in cat for k in ["CONDIZIONAMENTO > RESIDENZIALI", "CONDIZIONAMENTO > COMMERCIALI", "SENZA UNIT", "CONDIZIONAMENTO"]) or any(k in name for k in ["CLIMATIZZ", "CONDIZIONATORE", "MONOSPLIT", "DUAL SPLIT", "TRIAL SPLIT", "QUADRI SPLIT", "UE MULTI", "UI MULTI"]):
            if not any(k in cat for k in ["CANALIZZAZIONE", "CANALINE"]):
                if any(k in name for k in ["UE ", "UI ", "UNITA ESTERNA", "UNITA' ESTERNA", "CLIMATIZZ"]) or not any(k in cat for k in ["ACCESSORI"]):
                    return "AC"

        # Pompe / Autoclavi
        if any(k in cat for k in ["POMPE > ELETTROPOMPE", "POMPE > SISTEMI DI PRESSURIZZAZIONE", "CIRCOLATORI > PER RISCALDAMENTO"]):
            if not any(k in cat for k in ["ACCESSORI", "RICAMBI"]):
                return "PUMP"

        # Scaldabagni
        if "SCALDABAGN" in cat and "ACCESSORI" not in cat:
            return "WATER_HEATER"

        # Cassette WC
        if "CASSETTE" in cat and not any(k in cat for k in ["ACCESSORI", "PLACCHE"]):
            return "WC_CISTERN"

        return "GENERAL"

    def get_relations(self, item_or_code: Any) -> Dict[str, Any]:
        """
        Restituisce un dizionario contenente:
          - 'product_type': tipo macchina rilevato
          - 'variants': elenco di varianti di taglia/potenza (caldaie/clima/pompe analoghe)
          - 'accessory_groups': gruppi di veri accessori compatibili
        """
        if isinstance(item_or_code, str):
            item = self._by_code.get(item_or_code.strip())
        else:
            item = item_or_code

        if not item:
            return {"product_type": "UNKNOWN", "variants": [], "kits": [], "single_units": [], "accessory_groups": [], "ac_details": {}}

        prod_type = self.classify_product(item)
        brand = (item.get("brand") or "").upper()
        name = (item.get("name") or "").upper()
        code = str(item.get("code") or "").strip()
        primary_page = item.get("primary_page")

        page_items = self._by_page.get(primary_page, []) if primary_page else []
        brand_items = self._by_brand.get(brand, [])
        polymax_items = self._by_brand.get("POLYMAXACCIAI", [])

        variants = []
        kits = []
        single_units = []
        accessory_groups = []
        ac_details = {}

        # -------------------------------------------------------------
        # 1. ESTRAZIONE DELLE VARIANTI DI POTENZA / MODELLO
        # -------------------------------------------------------------
        for other in page_items:
            other_code = str(other.get("code") or "").strip()
            if other_code == code:
                continue

            other_cat = (other.get("category_path") or "").upper()
            other_brand = (other.get("brand") or "").upper()
            other_type = self.classify_product(other)

            # Se è della stessa famiglia macchina e stesso brand, è una VARIANTE!
            if other_brand == brand and other_type != "GENERAL" and other_type == prod_type:
                variants.append({
                    "code": other["code"],
                    "mfg_code": other.get("mfg_code", ""),
                    "name": other["name"],
                    "brand": other["brand"],
                    "gross_price": other.get("gross_price"),
                    "net_price": other.get("net_price"),
                    "primary_page": other.get("primary_page")
                })

        # -------------------------------------------------------------
        # 2. ESTRAZIONE DEGLI ACCESSORI COMPATIBILI (PER CATEGORIA)
        # -------------------------------------------------------------

        # CASE A: CALDAIE (e SCALDABAGNI A CONDENSAZIONE)
        if prod_type == "BOILER":
            brand_key = brand
            if brand in ["HERMANN SAUNIER DUVAL", "HERMANN", "HSD"]:
                brand_key = "HSD"

            b_rules = self._boiler_flue_rules.get("brands", {}).get(brand_key, {})
            flue_page = b_rules.get("catalog_flue_page")

            # 1. Matching Fumisteria Compatibile e Originale certificata da catalogo
            matching_compat = []
            matching_orig = []

            def match_flue_rules(rule_list, is_compat):
                results = []
                for r in rule_list:
                    # Check esclusioni di modello (es. FBC, THETA, LUNA, THEMIS)
                    excl = False
                    for ex in r.get("exclusions", []):
                        if re.search(r'\b' + re.escape(ex) + r'\b', name) or ex in name:
                            excl = True
                            break
                    if excl:
                        continue

                    # Check inclusioni di modello
                    inc_list = r.get("inclusions", [])
                    if inc_list == ["*"]:
                        inc_ok = True
                    else:
                        inc_ok = False
                        for inc in inc_list:
                            if re.search(r'\b' + re.escape(inc) + r'\b', name) or inc in name:
                                inc_ok = True
                                break
                    if not inc_ok:
                        continue

                    it = self._by_code.get(r["code"])
                    if it:
                        results.append({
                            "code": it["code"],
                            "mfg_code": it.get("mfg_code", ""),
                            "name": it["name"],
                            "brand": it.get("brand"),
                            "gross_price": it.get("gross_price"),
                            "net_price": it.get("net_price"),
                            "primary_page": flue_page or it.get("primary_page"),
                            "catalog_page": flue_page or it.get("primary_page"),
                            "compatibility_level": "OFFICIAL_CERTIFIED",
                            "badge_text": "✓ Compatibile Consigliato" if is_compat else f"Alternativa {it.get('brand')}",
                            "catalog_note": f"Fumisteria (pag. {flue_page}): {r.get('note', '')}",
                            "flue_type": r.get("flue_type"),
                            "diameter": r.get("diameter"),
                            "is_starter_kit": r.get("is_starter_kit", False)
                        })
                return results

            if b_rules:
                matching_compat = match_flue_rules(b_rules.get("compatible", []), is_compat=True)
                matching_orig = match_flue_rules(b_rules.get("original", []), is_compat=False)

            # Suddivisione tra Coassiali e Sdoppiati
            compat_coax = [x for x in matching_compat if x["flue_type"] == "COAXIAL"]
            compat_split = [x for x in matching_compat if x["flue_type"] == "SPLIT"]
            orig_coax = [x for x in matching_orig if x["flue_type"] == "COAXIAL"]
            orig_split = [x for x in matching_orig if x["flue_type"] == "SPLIT"]
            orig_acc = [x for x in matching_orig if x["flue_type"] not in ["COAXIAL", "SPLIT"]]

            # Se non sono state trovate regole specifiche per il brand, usa fallback euristico
            if not matching_compat and not matching_orig:
                coass_fb = []
                for r in brand_items:
                    n = (r.get("name") or "").upper()
                    if ("60/100" in n or "100/60" in n) and any(k in n for k in ["KIT", "CURVA", "PROLUNGA", "PARTENZA"]):
                        coass_fb.append(r)
                for r in polymax_items:
                    n = (r.get("name") or "").upper()
                    if "60/100" in n and any(k in n for k in ["KIT COASS", "CURVA COASS"]):
                        coass_fb.append(r)
                formatted_coass = self._format_items(coass_fb, target_item=item)
                if formatted_coass:
                    compat_coax = formatted_coass

            # GRUPPI ACCESSORI (Le compatibili SEMPRE prime come principali, originali come backup)
            if compat_coax:
                accessory_groups.append({
                    "group_id": "flue_compatible_coax",
                    "group_name": "Kit Fumi Coassiali 60/100 Compatibili (Consigliati)",
                    "icon": "💨",
                    "items": compat_coax
                })

            if compat_split:
                accessory_groups.append({
                    "group_id": "flue_compatible_split",
                    "group_name": "Kit Fumi Sdoppiati 80/80 Compatibili (Consigliati)",
                    "icon": "💨",
                    "items": compat_split
                })

            if orig_coax:
                accessory_groups.append({
                    "group_id": "flue_original_coax",
                    "group_name": f"Fumisteria Coassiale Originale {brand} (Alternativa)",
                    "icon": "💨",
                    "items": orig_coax
                })

            if orig_split:
                accessory_groups.append({
                    "group_id": "flue_original_split",
                    "group_name": f"Fumisteria Sdoppiata Originale {brand} (Alternativa)",
                    "icon": "💨",
                    "items": orig_split
                })

            if orig_acc:
                accessory_groups.append({
                    "group_id": "flue_original_acc",
                    "group_name": f"Accessori Fumi Originali {brand}",
                    "icon": "💨",
                    "items": orig_acc
                })

            # 3. Defangatore Magnetico Universale 50405633 & Trattamento Acqua
            defang_universal_code = "50405633"
            defang_universal_item = self._by_code.get(defang_universal_code)
            water_treatment_items = []

            if defang_universal_item:
                water_treatment_items.append({
                    "code": defang_universal_item["code"],
                    "mfg_code": defang_universal_item.get("mfg_code", "061506"),
                    "name": defang_universal_item["name"],
                    "brand": defang_universal_item.get("brand", "FERRARI"),
                    "gross_price": defang_universal_item.get("gross_price"),
                    "net_price": defang_universal_item.get("net_price"),
                    "primary_page": 90,
                    "catalog_page": 90,
                    "compatibility_level": "OFFICIAL_CERTIFIED",
                    "badge_text": "⭐ Defangatore Universale Sotto-Caldaia (Ferrari)",
                    "catalog_note": "Filtro defangatore magnetico KJ 3/4\" universale per tutte le caldaie a condensazione (pag. 90)",
                })

            # Aggiungi altri defangatori e dosatori disponibili nel catalogo (senza duplicare 50405633)
            other_defang = self._format_items(self._defangatori_caldaia + self._dosatori_caldaia, target_item=item)
            for od in other_defang:
                if od["code"] != defang_universal_code:
                    water_treatment_items.append(od)

            if water_treatment_items:
                accessory_groups.append({
                    "group_id": "water_treatment",
                    "group_name": "Defangatori Magnetici & Trattamento Acqua",
                    "icon": "🛡️",
                    "items": water_treatment_items[:6]
                })

            # 4. Termoregolazione Modulante & Sonde
            termo = []
            for r in brand_items:
                n = (r.get("name") or "").upper()
                if any(k in n for k in ["CRONOT", "COMANDO REM", "SONDA ESTERNA", "CONNECT", "MAGO", "CAR V2", "SENSYS", "EXACONTROL", "AMBIZEN"]):
                    termo.append(r)
            formatted_termo = self._format_items(termo, target_item=item)
            if formatted_termo:
                accessory_groups.append({
                    "group_id": "thermoregulation",
                    "group_name": f"Termoregolazione Modulante & Sonde {brand}",
                    "icon": "🌡️",
                    "items": formatted_termo[:5]
                })

            # 5. Dime di Montaggio & Neutralizzatori
            dime = []
            for r in brand_items:
                n = (r.get("name") or "").upper()
                if any(k in n for k in ["DIMA", "NEUTRALIZZ", "RACCORDI ESTENSIONE", "KIT COLLEGAMENTO"]):
                    dime.append(r)
            formatted_dime = self._format_items(dime, target_item=item)
            if formatted_dime:
                accessory_groups.append({
                    "group_id": "mounting_brackets",
                    "group_name": "Dime di Collegamento & Accessori",
                    "icon": "🔧",
                    "items": formatted_dime[:5]
                })

            # 6. GENERAZIONE KIT TURNKEY DI INSTALLAZIONE (Tab "Kit & Abbinamenti")
            # Kit 1: Caldaia + Starter Kit Fumi Coassiale Compatibile + Defangatore Universale 50405633
            starter_coax = next((x for x in compat_coax if x.get("is_starter_kit")), (compat_coax[0] if compat_coax else None))
            if not starter_coax and orig_coax:
                starter_coax = next((x for x in orig_coax if x.get("is_starter_kit")), orig_coax[0])

            # Kit 2: Caldaia + Starter Kit Fumi Sdoppiato Compatibile + Defangatore Universale 50405633
            starter_split = next((x for x in compat_split if x.get("is_starter_kit")), (compat_split[0] if compat_split else None))
            if not starter_split and orig_split:
                starter_split = next((x for x in orig_split if x.get("is_starter_kit")), orig_split[0])

            defang_ref = defang_universal_item or (self._by_code.get(defang_universal_code) if defang_universal_code in self._by_code else None)

            if starter_coax and defang_ref:
                c_gross = round((item.get("gross_price") or 0.0) + (starter_coax.get("gross_price") or 0.0) + (defang_ref.get("gross_price") or 0.0), 2)
                c_net = round((item.get("net_price") or 0.0) + (starter_coax.get("net_price") or 0.0) + (defang_ref.get("net_price") or 0.0), 2)
                kits.append({
                    "code": f"{code}+{starter_coax['code']}+{defang_ref['code']}",
                    "name": f"Kit Completo Caldaia {brand} + Fumi Coassiali + Defangatore KJ",
                    "configuration": "Kit Base Coassiale 60/100",
                    "brand": brand,
                    "badge_text": "Kit Installazione Consigliato",
                    "is_boiler_kit": True,
                    "components_label": "Componenti Inclusi nel Kit di Installazione:",
                    "gross_price": c_gross,
                    "net_price": c_net,
                    "catalog_page": flue_page,
                    "catalog_note": f"Bundle completo caldaia + fumisteria coassiale 60/100 (pag. {flue_page}) + defangatore KJ Ferrari (pag. 90)",
                    "ui_components": [
                        {
                            "code": code,
                            "name": item.get("name"),
                            "brand": brand,
                            "gross_price": item.get("gross_price"),
                            "net_price": item.get("net_price"),
                            "component_type": "CALDAIA",
                            "tag_btu": f"{item.get('taglia_kw', '')} kW" if item.get('taglia_kw') else "Caldaia"
                        },
                        {
                            "code": starter_coax["code"],
                            "name": starter_coax["name"],
                            "brand": starter_coax["brand"],
                            "gross_price": starter_coax.get("gross_price"),
                            "net_price": starter_coax.get("net_price"),
                            "component_type": "FUMISTERIA_COAX",
                            "tag_btu": starter_coax.get("diameter") or "60/100"
                        },
                        {
                            "code": defang_ref["code"],
                            "name": defang_ref["name"],
                            "brand": defang_ref.get("brand", "FERRARI"),
                            "gross_price": defang_ref.get("gross_price"),
                            "net_price": defang_ref.get("net_price"),
                            "component_type": "DEFANGATORE",
                            "tag_btu": "Defangatore 3/4\""
                        }
                    ]
                })

            if starter_split and defang_ref:
                s_gross = round((item.get("gross_price") or 0.0) + (starter_split.get("gross_price") or 0.0) + (defang_ref.get("gross_price") or 0.0), 2)
                s_net = round((item.get("net_price") or 0.0) + (starter_split.get("net_price") or 0.0) + (defang_ref.get("net_price") or 0.0), 2)
                kits.append({
                    "code": f"{code}+{starter_split['code']}+{defang_ref['code']}",
                    "name": f"Kit Completo Caldaia {brand} + Fumi Sdoppiati + Defangatore KJ",
                    "configuration": "Kit Base Sdoppiato 80/80",
                    "brand": brand,
                    "badge_text": "Kit Installazione Consigliato",
                    "is_boiler_kit": True,
                    "components_label": "Componenti Inclusi nel Kit di Installazione:",
                    "gross_price": s_gross,
                    "net_price": s_net,
                    "catalog_page": flue_page,
                    "catalog_note": f"Bundle completo caldaia + fumisteria sdoppiata 80/80 (pag. {flue_page}) + defangatore KJ Ferrari (pag. 90)",
                    "ui_components": [
                        {
                            "code": code,
                            "name": item.get("name"),
                            "brand": brand,
                            "gross_price": item.get("gross_price"),
                            "net_price": item.get("net_price"),
                            "component_type": "CALDAIA",
                            "tag_btu": f"{item.get('taglia_kw', '')} kW" if item.get('taglia_kw') else "Caldaia"
                        },
                        {
                            "code": starter_split["code"],
                            "name": starter_split["name"],
                            "brand": starter_split["brand"],
                            "gross_price": starter_split.get("gross_price"),
                            "net_price": starter_split.get("net_price"),
                            "component_type": "FUMISTERIA_SPLIT",
                            "tag_btu": starter_split.get("diameter") or "80/80"
                        },
                        {
                            "code": defang_ref["code"],
                            "name": defang_ref["name"],
                            "brand": defang_ref.get("brand", "FERRARI"),
                            "gross_price": defang_ref.get("gross_price"),
                            "net_price": defang_ref.get("net_price"),
                            "component_type": "DEFANGATORE",
                            "tag_btu": "Defangatore 3/4\""
                        }
                    ]
                })

        # CASE B: CLIMATIZZATORI (MONO / MULTI SPLIT)
        elif prod_type == "AC":
            # 1. CONTROLLO SE È UN'UNITÀ ESTERNA (UE)
            is_ue = code in self._ac_master_ues or (item.get("mfg_code") and any(u.get("codice_mfg") == item.get("mfg_code") for u in self._ac_master_ues.values()))
            is_ui = code in self._ac_master_uis or (item.get("mfg_code") and any(u.get("codice_mfg") == item.get("mfg_code") for u in self._ac_master_uis.values()))

            ue_info = self._ac_master_ues.get(code)
            if not ue_info and item.get("mfg_code"):
                mfg_clean = item["mfg_code"].strip().upper()
                ue_info = next((u for u in self._ac_master_ues.values() if (u.get("codice_mfg") or "").strip().upper() == mfg_clean), None)
            if not ue_info:
                ue_info = self._ac_by_code.get(code) or self._ac_by_mfg.get((item.get("mfg_code") or "").strip().upper())

            if is_ue or ue_info:
                comb_page = ue_info.get("catalog_combination_page") if ue_info else None
                max_ui = ue_info.get("max_ui_collegabili", 1) if ue_info else 1
                ports = ue_info.get("porte_attacchi", 1) if ue_info else 1
                sys_type = ue_info.get("tipo_sistema", "Mono-Split") if ue_info else "Mono-Split"
                nome_tab = ue_info.get("nome_tabella_combinazioni", "") if ue_info else ""
                combos = ue_info.get("combinazioni_ammesse", []) if ue_info else []
                kw_val = ue_info.get("potenza_nominale_kw") if ue_info else item.get("taglia_kw")
                tag_kw_val = ue_info.get("tag_kw") if ue_info else (f"{kw_val} kW" if kw_val else None)

                ac_details = {
                    "tipo_unita": "UE",
                    "is_ue": True,
                    "is_ui": False,
                    "max_ui_collegabili": max_ui,
                    "porte_attacchi": ports,
                    "tipo_sistema": sys_type,
                    "catalog_combination_page": comb_page,
                    "nome_tabella_combinazioni": nome_tab,
                    "combinazioni_ammesse": combos,
                    "tag_kw": tag_kw_val,
                    "taglia_kw": kw_val
                }

                ready_kits = (ue_info.get("kit_preconfigurati") or ue_info.get("ready_kits") or []) if ue_info else []

                # A. Kit Completi Certificati Commerciali (Multi-Split / Mono-Split) -> KITS
                if ready_kits:
                    for k in ready_kits:
                        enriched_comps = []
                        for c in (k.get("componenti_ui") or k.get("ui_components") or []):
                            c_dict = dict(c)
                            btu = c_dict.get("taglia_btu") or 9000
                            btu_disp = c_dict.get("tag_btu_display") or f"{btu} BTU"
                            c_dict["tag_btu"] = f"{btu} btu"
                            c_dict["tag_btu_display"] = btu_disp
                            c_dict["taglia_btu"] = btu
                            c_dict["tag_kw"] = None # RIGOROSAMENTE NESSUN KW PER LE UI
                            enriched_comps.append(c_dict)

                        k_code = k.get("id_kit") or k.get("mexal_code") or f"KIT-{code}"
                        k_name = k.get("nome_kit") or k.get("kit_name") or f"Kit {sys_type}"
                        k_conf = k.get("configurazione") or k.get("configuration") or ""
                        k_gross = k.get("prezzo_listino_totale") or k.get("total_gross_price")
                        k_net = k.get("prezzo_netto_totale") or k.get("total_net_price")

                        kits.append({
                            "code": k_code,
                            "mfg_code": k_conf,
                            "name": k_name,
                            "brand": ue_info.get("brand"),
                            "gross_price": k_gross,
                            "net_price": k_net,
                            "primary_page": comb_page or ue_info.get("pagina_catalogo") or ue_info.get("primary_page"),
                            "compatibility_level": "CERTIFIED_CATALOG",
                            "badge_text": f"🟢 Kit Ufficiale (Tabella P.{comb_page})" if comb_page else "🟢 Kit Certificato Catalogo",
                            "catalog_note": f"Configurazione certificata dal costruttore ({k_conf}). Include: " + ", ".join([f"{c.get('nome') or c.get('name', '')} [{c.get('tag_btu_display', '')}]" for c in enriched_comps]),
                            "catalog_page": comb_page,
                            "is_bundle_kit": True,
                            "configuration": k_conf,
                            "ui_components": enriched_comps
                        })

                # B. Se Mono-Split con unità interna abbinata e senza kit bundle
                elif ue_info and ue_info.get("paired_ui"):
                    paired = dict(ue_info["paired_ui"])
                    p_btu = paired.get("taglia_btu") or 9000
                    p_btu_disp = paired.get("tag_btu_display") or f"{p_btu} BTU"
                    p_code = paired.get("codice_pt") or paired.get("code")
                    p_name = paired.get("nome") or paired.get("name")
                    p_mfg = paired.get("codice_mfg") or paired.get("mfg_code", "")
                    p_gross = paired.get("prezzo_listino") or paired.get("gross_price")
                    p_net = paired.get("prezzo_netto") or paired.get("net_price")
                    paired_comp = {
                        "code": p_code,
                        "mfg_code": p_mfg,
                        "name": p_name,
                        "brand": paired.get("brand") or ue_info.get("brand"),
                        "tag_btu": f"{p_btu} btu",
                        "tag_btu_display": p_btu_disp,
                        "taglia_btu": p_btu,
                        "tag_kw": None,
                        "gross_price": p_gross,
                        "net_price": p_net
                    }
                    kits.append({
                        "code": p_code,
                        "mfg_code": p_mfg,
                        "name": f"Kit Mono-Split con {p_name}",
                        "brand": paired.get("brand") or ue_info.get("brand"),
                        "gross_price": p_gross,
                        "net_price": p_net,
                        "primary_page": comb_page or paired.get("pagina_catalogo") or paired.get("primary_page"),
                        "compatibility_level": "CERTIFIED_CATALOG",
                        "badge_text": f"🟢 Unità Abbinata (Tabella P.{comb_page})" if comb_page else "🟢 Unità Abbinata Catalogo",
                        "catalog_note": f"Unità interna abbinata a catalogo per {name}.",
                        "catalog_page": comb_page,
                        "is_bundle_kit": True,
                        "configuration": "1 Split",
                        "ui_components": [paired_comp]
                    })

                # C. Unità Interne Compatibili Singole (per comporre combinazioni personalizzate) -> SINGLE_UNITS
                compatible_uis = (ue_info.get("unita_interne_compatibili") or ue_info.get("compatible_uis_sample") or []) if ue_info else []
                for u in compatible_uis:
                    btu = u.get("taglia_btu") or 9000
                    tag_btu = u.get("tag_btu") or f"{btu} btu"
                    tag_btu_disp = u.get("tag_btu_display") or f"{btu} BTU"
                    u_code = u.get("codice_pt") or u.get("code")
                    u_mfg = u.get("codice_mfg") or u.get("mfg_code", "")
                    u_name = u.get("nome") or u.get("name", "")
                    u_gross = u.get("prezzo_listino") or u.get("gross_price")
                    u_net = u.get("prezzo_netto") or u.get("net_price")
                    u_page = comb_page or u.get("pagina_catalogo") or u.get("primary_page")

                    badge_label = f"❄️ UI · {tag_btu_disp} (Tab. P.{comb_page})" if comb_page else f"❄️ UI · {tag_btu_disp}"
                    single_units.append({
                        "code": u_code,
                        "mfg_code": u_mfg,
                        "name": u_name,
                        "brand": u.get("brand") or (ue_info.get("brand") if ue_info else ""),
                        "taglia_btu": btu,
                        "tag_btu": tag_btu,
                        "tag_btu_display": tag_btu_disp,
                        "tag_kw": None, # RIGOROSAMENTE NESSUN KW PER LE UI!
                        "taglia_kw": None,
                        "gross_price": u_gross,
                        "net_price": u_net,
                        "primary_page": u_page,
                        "catalog_page": comb_page,
                        "compatibility_level": "CERTIFIED_CATALOG",
                        "badge_text": badge_label,
                        "catalog_note": f"Unità interna certificata nella tabella di combinazione a pag. {comb_page} per {name}." if comb_page else f"Unità interna compatibile a catalogo per {name}.",
                        "is_indoor_unit": True
                    })

            # 2. CONTROLLO SE È UN'UNITÀ INTERNA (UI) -> Mostra le Unità Esterne compatibili in SINGLE_UNITS
            elif is_ui or code in self._ac_master_uis or code in self._ac_ui_to_ue:
                ui_info = self._ac_master_uis.get(code)
                if not ui_info and item.get("mfg_code"):
                    mfg_clean = item["mfg_code"].strip().upper()
                    ui_info = next((u for u in self._ac_master_uis.values() if (u.get("codice_mfg") or "").strip().upper() == mfg_clean), None)

                if ui_info:
                    ac_details = {
                        "tipo_unita": "UI",
                        "is_ui": True,
                        "is_ue": False,
                        "tag_btu": ui_info.get("tag_btu"),
                        "tag_btu_display": ui_info.get("tag_btu_display"),
                        "taglia_btu": ui_info.get("taglia_btu")
                    }
                    ues_list = ui_info.get("unita_esterne_compatibili", [])
                    seen_ue_codes = set()
                    for ue_sum in ues_list:
                        ue_code = ue_sum.get("codice_pt") or ue_sum.get("code")
                        if not ue_code or ue_code in seen_ue_codes:
                            continue
                        seen_ue_codes.add(ue_code)
                        c_page = ue_sum.get("pagina_combinazioni_catalogo") or ue_sum.get("pagina_catalogo") or ue_sum.get("catalog_page")
                        sys_type = ue_sum.get("tipo_sistema", "Multi-Split")
                        ports = ue_sum.get("porte_attacchi", 1)
                        max_ui = ue_sum.get("max_ui_collegabili", ports)
                        kw_val = ue_sum.get("potenza_nominale_kw")
                        kw_tag = ue_sum.get("tag_kw") or (f"{kw_val} kW" if kw_val else "")

                        badge_label = f"🏢 UE · {kw_tag} ({sys_type}) (Tab. P.{c_page})" if c_page else f"🏢 UE · {kw_tag} ({sys_type})"
                        single_units.append({
                            "code": ue_code,
                            "mfg_code": ue_sum.get("codice_mfg") or ue_sum.get("mfg_code", ""),
                            "name": ue_sum.get("nome") or ue_sum.get("name", ""),
                            "brand": ue_sum.get("brand") or ui_info.get("brand"),
                            "tag_kw": kw_tag, # RIGOROSAMENTE KW PER LE UE!
                            "taglia_kw": kw_val,
                            "tag_btu": None, # MAI BTU PER LE UE!
                            "taglia_btu": None,
                            "tipo_sistema": sys_type,
                            "porte_attacchi": ports,
                            "max_ui_collegabili": max_ui,
                            "gross_price": ue_sum.get("gross_price"),
                            "net_price": ue_sum.get("net_price") or ue_sum.get("prezzo_netto"),
                            "primary_page": c_page,
                            "catalog_page": c_page,
                            "compatibility_level": "CERTIFIED_CATALOG",
                            "badge_text": badge_label,
                            "catalog_note": f"Unità Esterna {sys_type} ({ports} attacchi) certificata nella tabella a pag. {c_page} per questa UI." if c_page else f"Unità Esterna compatibile a catalogo.",
                            "is_outdoor_unit": True
                        })
                else:
                    # Fallback backward-compatibile
                    ue_mappings = self._ac_ui_to_ue[code]
                    seen_ue_codes = set()
                    for ue_data, kit_data in ue_mappings:
                        ue_code = ue_data.get("code") or ue_data.get("codice_pt")
                        if ue_code and ue_code not in seen_ue_codes:
                            seen_ue_codes.add(ue_code)
                            c_page = ue_data.get("catalog_combination_page") or ue_data.get("pagina_catalogo")
                            system_type = ue_data.get("tipo_sistema") or ue_data.get("system_type", "Mono/Multi-Split")
                            ports = ue_data.get("porte_attacchi") or ue_data.get("ports", 1)
                            kw_tag = ue_data.get("tag_kw") or ""
                            badge_label = f"🏢 UE · {kw_tag} ({system_type})" if kw_tag else f"🏢 UE {system_type}"
                            single_units.append({
                                "code": ue_code,
                                "mfg_code": ue_data.get("mfg_code") or ue_data.get("codice_mfg", ""),
                                "name": ue_data.get("name") or ue_data.get("nome", ""),
                                "brand": ue_data.get("brand"),
                                "tag_kw": kw_tag,
                                "tag_btu": None,
                                "gross_price": ue_data.get("gross_price"),
                                "net_price": ue_data.get("net_price"),
                                "primary_page": c_page,
                                "compatibility_level": "CERTIFIED_CATALOG",
                                "badge_text": badge_label,
                                "catalog_note": f"Unità Esterna {system_type} ({ports} attacchi) certificata a catalogo per questa unità interna.",
                                "catalog_page": c_page,
                                "is_outdoor_unit": True
                            })

            # Monoblocco senza unità esterna
            if not ac_details:
                cat_up = (item.get("category_path") or "").upper()
                if "SENZA UNIT" in cat_up or "MONOBLOCCO" in cat_up or "UNICO" in name:
                    ac_details = {
                        "tipo_unita": "MONOBLOCCO_SUE",
                        "is_monoblocco_sue": True,
                        "is_ui": False,
                        "is_ue": False
                    }

            # 3. Staffe & Supporti per Unità Esterna
            if self._staffe_clima:
                formatted_staffe = self._format_items(self._staffe_clima, target_item=item)
                if formatted_staffe:
                    accessory_groups.append({
                        "group_id": "ac_brackets",
                        "group_name": "Staffe e Mensole per Unità Esterna",
                        "icon": "🔩",
                        "items": formatted_staffe[:5]
                    })

            # 4. Scarico Condensa (Tubi e Pompe)
            if self._scarico_clima:
                formatted_scarico = self._format_items(self._scarico_clima, target_item=item)
                if formatted_scarico:
                    accessory_groups.append({
                        "group_id": "condensate_drain",
                        "group_name": "Scarico Condensa (Tubi e Pompe)",
                        "icon": "💧",
                        "items": formatted_scarico[:5]
                    })

            # 5. Schede Wi-Fi e Comandi del Brand
            wifi = []
            for r in brand_items:
                n = (r.get("name") or "").upper()
                if any(k in n for k in ["WI-FI", "WIFI", "BRP069", "MIM-H", "TELECOMANDO"]):
                    wifi.append(r)
            formatted_wifi = self._format_items(wifi, target_item=item)
            if formatted_wifi:
                accessory_groups.append({
                    "group_id": "wifi_controls",
                    "group_name": f"Schede Wi-Fi & Controlli {brand}",
                    "icon": "📶",
                    "items": formatted_wifi[:5]
                })

        # CASE C: POMPE / AUTOCLAVI
        elif prod_type == "PUMP":
            # 1. Vasi d'espansione a membrana
            if self._vasi_autoclave:
                formatted_vasi = self._format_items(self._vasi_autoclave, target_item=item)
                if formatted_vasi:
                    accessory_groups.append({
                        "group_id": "expansion_vessels",
                        "group_name": "Vasi d'Espansione a Membrana (24L / 50L)",
                        "icon": "🔴",
                        "items": formatted_vasi[:5]
                    })

            # 2. Presscontrol e regolazione
            if self._presscontrol_pompa:
                formatted_press = self._format_items(self._presscontrol_pompa, target_item=item)
                if formatted_press:
                    accessory_groups.append({
                        "group_id": "pressure_controls",
                        "group_name": "Presscontrol e Regolatori di Pressione",
                        "icon": "⚡",
                        "items": formatted_press[:5]
                    })

            # 3. Valvole di ritegno e fondo
            if self._valvole_pompa:
                formatted_valv = self._format_items(self._valvole_pompa, target_item=item)
                if formatted_valv:
                    accessory_groups.append({
                        "group_id": "valves_fittings",
                        "group_name": "Valvole di Ritegno, Fondo e Raccordi 5 Vie",
                        "icon": "🚰",
                        "items": formatted_valv[:5]
                    })

        # CASE D: SCALDABAGNI
        elif prod_type == "WATER_HEATER":
            water_accs = []
            for r in brand_items:
                n = (r.get("name") or "").upper()
                if any(k in n for k in ["FUMI", "COASS", "RACCORDI", "SICUREZZA", "RUBINETTO"]):
                    water_accs.append(r)
            formatted_water = self._format_items(water_accs, target_item=item)
            if formatted_water:
                accessory_groups.append({
                    "group_id": "water_heater_acc",
                    "group_name": "Fumisteria e Raccordi Scaldabagno",
                    "icon": "🔥",
                    "items": formatted_water[:6]
                })

        # CASE E: CASSETTE WC (Geberit / Valsir)
        elif prod_type == "WC_CISTERN":
            placche = self._placche_geberit if brand == "GEBERIT" else (self._placche_valsir if brand == "VALSIR" else [])
            formatted_placche = self._format_items(placche, target_item=item)
            if formatted_placche:
                accessory_groups.append({
                    "group_id": "flush_plates",
                    "group_name": f"Placche di Comando Compatibili {brand}",
                    "icon": "🔘",
                    "items": formatted_placche[:6]
                })

        # FALLBACK O PRODOTTI GENERALI:
        # Prendi gli accessori co-presenti sulla pagina escludendo varianti o cloni della stessa categoria
        if not accessory_groups and page_items:
            page_accs = []
            for other in page_items:
                if str(other.get("code")).strip() == code:
                    continue
                if other.get("category_path") != item.get("category_path"):
                    page_accs.append(other)
            formatted_page = self._format_items(page_accs, target_item=item)
            if formatted_page:
                accessory_groups.append({
                    "group_id": "page_accessories",
                    "group_name": "Accessori e Componenti Correlati di Pagina",
                    "icon": "📦",
                    "items": formatted_page[:8]
                })

        return {
            "product_type": prod_type,
            "variants": variants[:6],
            "kits": kits,
            "single_units": single_units,
            "accessory_groups": accessory_groups,
            "ac_details": ac_details
        }

    def evaluate_compatibility(self, acc_item: Dict[str, Any], target_item: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Valuta la compatibilità tecnica tra l'accessorio candidato e l'apparecchio target.
        Restituisce un dizionario con livello, etichetta badge, nota letterale, pagina catalogo e priorità di ordinamento.
        """
        acc_code = str(acc_item.get("code") or "").strip()
        rule = self._rules.get(acc_code)
        
        acc_name = (acc_item.get("name") or "").upper()
        acc_brand = (acc_item.get("brand") or "").upper()
        page = acc_item.get("primary_page")

        # 1. Standard Idraulico Universale (UNI 8065) - Valido fisicamente per tutte le macchine
        if "DEFANGAT" in acc_name and "3/4" in acc_name:
            return {
                "level": "UNIVERSAL_HYDRAULIC",
                "badge": "🔵 Standard UNI 8065 (3/4\")",
                "note": "Attacco standard 3/4\" MF sottocaldaia - Idoneo per qualsiasi caldaia murale residenziale (<35 kW)",
                "page": page,
                "is_excluded": False,
                "priority": 3
            }
        if "DOSATORE" in acc_name and "POLIFOSF" in acc_name:
            return {
                "level": "UNIVERSAL_HYDRAULIC",
                "badge": "🔵 Standard Sanitario (1/2\")",
                "note": "Attacco standard 1/2\" - Dosatore proporzionale anticalcare per ingresso acqua fredda",
                "page": page,
                "is_excluded": False,
                "priority": 4
            }
        if "VASO ESPANSIONE" in acc_name and any(k in acc_name for k in [" 24", "LT 24", " 50", "LT 50"]):
            return {
                "level": "UNIVERSAL_HYDRAULIC",
                "badge": "🔵 Standard Autoclave (1\")",
                "note": "Attacco filettato 1\" Maschio - Vaso a membrana universale per gruppi autoclave",
                "page": page,
                "is_excluded": False,
                "priority": 3
            }

        if not target_item:
            return {
                "level": "BRAND_SERIES",
                "badge": f"🟡 Compatibile {acc_brand}",
                "note": "",
                "page": page,
                "is_excluded": False,
                "priority": 5
            }

        target_name = (target_item.get("name") or "").upper()
        target_brand = (target_item.get("brand") or "").upper()

        if rule:
            note = rule.get("compatibility_note") or ""
            page = rule.get("catalog_page") or page
            excl = (rule.get("excluded_models_raw") or "").upper()
            incl = (rule.get("included_models_raw") or "").upper()

            # 1. Controllo modelli espressamente ESCLUSI dal catalogo (es. 'escluso tutti i modelli Luna')
            clean_excl = re.sub(r'(?i)\b(?:esclus[oi]\s*)?(?:tutti\s+i\s+)?(?:modelli|mod\.?)\b', '', excl).strip(' .-:')
            if clean_excl:
                tokens = [t.strip(' .') for t in re.split(r'[,/-]|\be\b', clean_excl) if len(t.strip(' .')) > 2]
                for tok in tokens:
                    if tok in target_name:
                        return {
                            "level": "EXCLUDED",
                            "badge": f"❌ Incompatibile (Escluso {tok})",
                            "note": f"Nota catalogo (pag. {page}): {note}",
                            "page": page,
                            "is_excluded": True,
                            "priority": 99
                        }

            # Controlla anche se nella nota c'è una clausola 'escluso/i ...' che matcha il modello target
            excl_match = re.search(r'(?i)esclus[oi]\s*[-:\s]*(.+)', note)
            if excl_match:
                raw_excl = excl_match.group(1).upper()
                clean_raw_excl = re.sub(r'(?i)\b(?:tutti\s+i\s+)?(?:modelli|mod\.?)\b', '', raw_excl).strip(' .-:')
                for tok in [t.strip(' .') for t in re.split(r'[,/-]|\be\b', clean_raw_excl) if len(t.strip(' .')) > 2]:
                    if tok in target_name:
                        return {
                            "level": "EXCLUDED",
                            "badge": f"❌ Incompatibile (Escluso {tok})",
                            "note": f"Nota catalogo (pag. {page}): {note}",
                            "page": page,
                            "is_excluded": True,
                            "priority": 99
                        }

            # 2. Controllo inclusione specifica per modello
            clean_incl = re.sub(r'(?i)\b(?:tutti\s+i\s+)?(?:modelli|mod\.?)\b', '', incl).strip(' .-:')
            if clean_incl:
                tokens = [t.strip(' .') for t in re.split(r'[,/-]|\be\b', clean_incl) if len(t.strip(' .')) > 2]
                for tok in tokens:
                    if tok in target_name:
                        return {
                            "level": "CERTIFIED_CATALOG",
                            "badge": f"🟢 Certificato per {tok} (P.{page})",
                            "note": f"Nota catalogo (pag. {page}): {note}",
                            "page": page,
                            "is_excluded": False,
                            "priority": 1
                        }

            # Cerca nel testo della nota eventuali modelli specifici citati dopo 'Per '
            for m in re.finditer(r'(?i)\bper\s+([a-z0-9 /_\-]+)', note):
                raw_mod = m.group(1).upper()
                # Rimuovi eventuale parte escluso
                raw_mod = re.split(r'(?i)esclus', raw_mod)[0]
                clean_mod = re.sub(r'(?i)\b(?:tutti\s+i\s+)?(?:modelli|mod\.?)\b', '', raw_mod).strip(' .-:')
                parts = [p.strip(' .') for p in re.split(r'[,/-]', clean_mod) if len(p.strip(' .')) > 2]
                for p_tok in parts:
                    if p_tok not in ["TUTTI I MODELLI", "CALDAIE", "INSTALLAZIONI"] and p_tok in target_name:
                        return {
                            "level": "CERTIFIED_CATALOG",
                            "badge": f"🟢 Certificato per {p_tok} (P.{page})",
                            "note": f"Nota catalogo (pag. {page}): {note}",
                            "page": page,
                            "is_excluded": False,
                            "priority": 1
                        }

            # 3. Universale di marchio dichiarato a catalogo ('Per tutti i modelli')
            # Valido solo se NON sono presenti clausole restrittive o di esclusione
            if (rule.get("is_universal") or "TUTTI I MODELLI" in note.upper()) and not clean_excl and not excl_match:
                return {
                    "level": "BRAND_UNIVERSAL",
                    "badge": f"🟡 Per tutti i modelli {target_brand} (P.{page})",
                    "note": f"Nota catalogo (pag. {page}): {note}",
                    "page": page,
                    "is_excluded": False,
                    "priority": 2
                }

            if note:
                return {
                    "level": "BRAND_SERIES",
                    "badge": f"🟡 Compatibile {acc_brand} (P.{page})",
                    "note": f"Nota catalogo (pag. {page}): {note}",
                    "page": page,
                    "is_excluded": False,
                    "priority": 5
                }

        # Fallback generico
        return {
            "level": "BRAND_SERIES",
            "badge": f"🟡 Compatibile {acc_brand}",
            "note": f"Accessorio correlato della serie {acc_brand}",
            "page": page,
            "is_excluded": False,
            "priority": 6
        }

    def _format_items(self, items: List[Dict[str, Any]], target_item: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        formatted = []
        for it in items:
            compat = self.evaluate_compatibility(it, target_item)
            if compat["is_excluded"]:
                continue  # Scarta automaticamente accessori esclusi/incompatibili

            formatted.append({
                "code": it.get("code"),
                "mfg_code": it.get("mfg_code", ""),
                "name": it.get("name"),
                "brand": it.get("brand"),
                "gross_price": it.get("gross_price"),
                "net_price": it.get("net_price"),
                "primary_page": compat["page"] or it.get("primary_page"),
                "compatibility_level": compat["level"],
                "badge_text": compat["badge"],
                "catalog_note": compat["note"],
                "catalog_page": compat["page"],
                "_priority": compat["priority"]
            })

        # Ordina per priorità: prima CERTIFICATI da catalogo (1), poi universali di marca (2), poi universali idraulici (3/4)
        formatted.sort(key=lambda x: x.get("_priority", 10))
        for f in formatted:
            f.pop("_priority", None)
        return formatted

if __name__ == "__main__":
    engine = AccessoryEngine()
    test_codes = [
        "50018697", # Caldaia Ferroli Bluehelix Maxima 28
        "50149230", # Caldaia Baxi Luna Classic 24
        "50307609", # Clima Daikin Stylish UI
        "50042371", # Pompa DAB Esydock Max
    ]
    for c in test_codes:
        rel = engine.get_relations(c)
        prod = engine._by_code.get(c, {})
        print(f"\n=======================================================")
        print(f"PRODOTTO: [{c}] {prod.get('brand')} | {prod.get('name')} ({rel['product_type']})")
        print(f"=======================================================")
        print(f"VARIANTI DI MODELLO / TAGLIA ({len(rel['variants'])}):")
        for v in rel['variants']:
            print(f"   • [{v['code']}] {v['name']} ({v['net_price']} €)")
        print(f"\nGRUPPI ACCESSORI COMPATIBILI ({len(rel['accessory_groups'])}):")
        for g in rel['accessory_groups']:
            print(f"   {g['icon']} {g['group_name']} ({len(g['items'])} articoli):")
            for it in g['items'][:3]:
                print(f"       - [{it['code']}] {it['brand']} - {it['name']} ({it['net_price']} €)")
