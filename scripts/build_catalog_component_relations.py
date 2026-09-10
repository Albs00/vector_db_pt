"""
Build catalog_component_relations.json and catalog_component_relations_report.json.

Correlates commercial annotations with coded accessories strictly using PDF layout
bounding boxes and table contexts. Zero deduction by similarity or external compatibility.

Outputs:
- Knowledge/catalog_component_relations.json
- catalog_component_relations.json
- catalog_component_relations_report.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure stdout for Windows UTF-8
sys.stdout.reconfigure(encoding="utf-8")

def calc_table_id(page: int, title: str, bbox: list) -> str:
    signature = json.dumps(
        [int(page or 0), str(title or ""), [round(float(v), 2) for v in (bbox or [])]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:10].upper()
    return f"PDF_P{int(page or 0):04d}_{digest}"

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
TABLE_CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
ROOT_TABLE_CONTEXT_PATH = ROOT / "catalog_table_context.json"
UNIFIED_MASTER_PATH = ROOT / "Knowledge" / "unified_catalog_master.json"

OUTPUT_KNOWLEDGE_JSON = ROOT / "Knowledge" / "catalog_component_relations.json"
OUTPUT_ROOT_JSON = ROOT / "catalog_component_relations.json"
OUTPUT_REPORT_JSON = ROOT / "catalog_component_relations_report.json"


def is_accessory_title(title: str) -> bool:
    tt = (title or "").upper()
    return any(
        w in tt
        for w in [
            "GRIGLIA",
            "COMANDO",
            "ACCESSOR",
            "FILTRO",
            "KIT CONNETTORI",
            "TELECOMANDO",
            "RICAMBI",
            "CHIAVE",
            "SET 3",
        ]
    )


def extract_component_type_and_status(annotation: dict[str, Any]) -> tuple[Optional[str], str]:
    atype = annotation.get("annotation_type", "OTHER")
    txt = annotation.get("raw_text", "")
    low = txt.lower()

    # Rule-based component extraction with strict hierarchy
    ctype = None
    if "griglia" in low:
        ctype = "GRIGLIA"
    elif "telecomando" in low:
        ctype = "TELECOMANDO"
    elif any(w in low for w in ["filo comando", "comando a filo", "filocomando"]):
        ctype = "COMANDO A FILO"
    elif "comando" in low:
        ctype = "COMANDO"
    elif "wifi" in low or "wi-fi" in low:
        ctype = "WIFI"
    elif "pompa" in low and "condensa" in low:
        ctype = "POMPA SCARICO CONDENSA"
    elif "sedile" in low:
        ctype = "SEDILE"
    elif "piletta" in low:
        ctype = "PILETTA"
    elif "valvola" in low:
        ctype = "VALVOLA"
    elif "batteria" in low:
        ctype = "BATTERIA"
    elif any(w in low for w in ["fissaggio", "staffa", "struttura", "telaio", "controtelaio", "supporto"]):
        ctype = "STRUTTURA DI FISSAGGIO"
    elif "bruciatore" in low:
        ctype = "BRUCIATORE"
    elif "rubinetter" in low or "miscelat" in low:
        ctype = "RUBINETTERIA"
    elif "sonda" in low:
        ctype = "SONDA"
    elif "bollitore" in low or "accumulo" in low or "serbatoio" in low:
        ctype = "BOLLITORE"
    else:
        # Check pre-extracted entities
        for e in annotation.get("entities", []):
            if e.get("type") == "COMPONENT" and e.get("value") != "ACCESSORIO":
                ctype = e.get("value")
                break
        if not ctype and atype in (
            "COMPONENT_REQUIRED",
            "COMPONENT_OPTIONAL",
            "COMPONENT_EXCLUDED",
            "COMPONENT_INCLUDED",
        ):
            ctype = "ACCESSORIO"

    return ctype, atype


def is_matching_accessory(comp_type: str, title: str, model: str, name: str, family: str) -> bool:
    combo = f"{title} {model} {name} {family}".upper()
    tt = (title or "").upper()
    mm = (model or "").upper()

    is_main_machine = any(
        tt.startswith(p)
        for p in [
            "CALDAIA",
            "SCALDABAGNO",
            "UNITA ESTERNA",
            "UNITA' ESTERNA",
            "U.E.",
            "MONOSPLIT",
            "MULTISPLIT",
            "STUFA",
            "TERMOSTUFA",
            "POMPA DI CALORE",
        ]
    )

    if comp_type == "GRIGLIA":
        # Discard cables, adapters, remote controls that reference grilles
        if any(w in combo for w in ["COMANDO", "TELECOMANDO", "CAVO", "ADATTATORE", "SENSORE", "RICEVITORE"]):
            return False
        if "FILTRO" in combo and "GRIGLIA" not in combo:
            return False
        return "GRIGLIA" in combo or any(
            m in combo
            for m in [
                "GLG40",
                "GLG40S",
                "BYFQ",
                "BYCQ",
                "SLP-2F",
                "T-MBQ",
                "PE-QEA",
                "CZ-KPY",
                "RBC-U",
                "MLP-",
            ]
        )

    if comp_type == "WIFI":
        if any(
            w in combo
            for w in [
                "KITWIFI",
                "WIFIKEY",
                "MODULO WIFI",
                "SCHEDA WIFI",
                "KIT WI-FI",
                "INTERFACCIA WI-FI",
                "GATEWAY IOT",
                "WIFIKIT",
            ]
        ):
            return True
        if ("WIFI" in combo or "WI-FI" in combo) and not is_main_machine:
            return not any(
                w in tt
                for w in ["CALDAIA", "LUNA", "THEMA", "ECOTEC", "TITANO", "MICRA", "DOMUS", "INSIEME"]
            )
        return False

    if comp_type == "TELECOMANDO":
        if any(w in combo for w in ["TELECOMANDO", "RICEVITORE", "INFRA"]) or any(
            m in combo for m in ["PAR-FL", "PAR-FA", "BRC7F"]
        ):
            return not is_main_machine
        return False

    if comp_type in ("COMANDO", "COMANDO A FILO"):
        if any(w in combo for w in ["COMANDO", "CRONOTERMOSTATO", "TERMOSTATO"]) or any(
            m in combo for m in ["PAR-41", "PAR-CT", "BRC1H", "KJR-", "REC10", "WRC50", "MADOKA"]
        ):
            return not is_main_machine
        return False

    if comp_type == "POMPA SCARICO CONDENSA":
        return "POMPA" in combo and "CONDENSA" in combo

    if comp_type == "SEDILE":
        return "SEDILE" in combo

    if comp_type == "PILETTA":
        return "PILETTA" in combo

    if comp_type == "VALVOLA":
        return "VALVOLA" in combo

    if comp_type == "BATTERIA":
        return "BATTERIA" in combo

    if comp_type == "STRUTTURA DI FISSAGGIO":
        return any(w in combo for w in ["FISSAGGIO", "STAFFA", "TELAIO", "CONTROTELAIO", "SUPPORTO"])

    if comp_type == "BRUCIATORE":
        return "BRUCIATORE" in combo

    if comp_type == "RUBINETTERIA":
        return "RUBINETT" in combo or "MISCELAT" in combo

    if comp_type == "BOLLITORE":
        return any(w in combo for w in ["BOLLITORE", "ACCUMULO", "SERBATOIO"]) and not is_main_machine

    if comp_type == "SONDA":
        return "SONDA" in combo

    if comp_type == "ACCESSORIO":
        return "ACCESSOR" in combo

    return False


def load_tables_and_codes() -> tuple[dict[int, dict[str, dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
    print("Loading catalog table contexts and product metadata...")
    tables_by_page: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    codes_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)

    # Load unified master for canonical models and descriptions
    catalog_by_code: dict[str, dict[str, Any]] = {}
    if UNIFIED_MASTER_PATH.exists():
        with UNIFIED_MASTER_PATH.open("r", encoding="utf-8") as f:
            master_list = json.load(f)
            catalog_by_code = {item["code"]: item for item in master_list if "code" in item}
        print(f"Loaded {len(catalog_by_code)} items from unified catalog master.")

    # Load table context (root is primary as it contains layout_evidence with bounding boxes)
    tc_data = {}
    if ROOT_TABLE_CONTEXT_PATH.exists():
        with ROOT_TABLE_CONTEXT_PATH.open("r", encoding="utf-8") as f:
            tc_data.update(json.load(f))
    if TABLE_CONTEXT_PATH.exists():
        with TABLE_CONTEXT_PATH.open("r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if k not in tc_data:
                    tc_data[k] = v

    for code, rec in tc_data.items():
        page = int(rec.get("page") or 0)
        title = rec.get("table_title") or ""
        bbox = (rec.get("layout_evidence") or {}).get("table_bbox") or []
        title_bbox = (rec.get("layout_evidence") or {}).get("title_bbox") or []
        code_bbox = (rec.get("layout_evidence") or {}).get("code_bbox") or []
        section = rec.get("section_title") or ""

        tid = calc_table_id(page, title, bbox)
        family_key = rec.get("table_family") or ""
        model = rec.get("model") or ""
        if page:
            if tid not in tables_by_page[page]:
                tables_by_page[page][tid] = {
                    "table_id": tid,
                    "page": page,
                    "title": title,
                    "family_key": family_key,
                    "models": [],
                    "section": section,
                    "table_bbox": bbox,
                    "title_bbox": title_bbox,
                    "min_code_y": code_bbox[1] if code_bbox else (bbox[3] if bbox else 0),
                    "max_code_y": code_bbox[3] if code_bbox else (bbox[3] if bbox else 0),
                    "min_x": min(code_bbox[0] if code_bbox else 600, bbox[0] if bbox else 600),
                    "max_x": max(code_bbox[2] if code_bbox else 0, bbox[2] if bbox else 0),
                }
            t = tables_by_page[page][tid]
            if family_key and not t.get("family_key"):
                t["family_key"] = family_key
            if code_bbox:
                t["min_code_y"] = min(t["min_code_y"], code_bbox[1])
                t["max_code_y"] = max(t["max_code_y"], code_bbox[3])
                t["min_x"] = min(t["min_x"], code_bbox[0])
                t["max_x"] = max(t["max_x"], code_bbox[2])
            if model and model != "OPTIONAL" and not is_accessory_title(title) and model not in t["models"]:
                t["models"].append(model)

        # Index primary appearance
        if page and code_bbox and len(code_bbox) == 4 and (code_bbox[2] > code_bbox[0]) and (code_bbox[3] > code_bbox[1]):
            eff_bbox = code_bbox
            prod = catalog_by_code.get(code, {})
            mfg = prod.get("mfg_code") or rec.get("model") or ""
            name = prod.get("name") or prod.get("description") or title or ""
            codes_by_page[page].append(
                {
                    "pt": code,
                    "model": mfg if mfg != "OPTIONAL" else (rec.get("model") or "OPTIONAL"),
                    "mfg_code": mfg,
                    "name": name,
                    "title": title,
                    "family": rec.get("table_family") or "",
                    "bbox": eff_bbox,
                    "source": "primary",
                }
            )

        # Index alternate appearances
        for alt in rec.get("alternate_table_contexts") or []:
            ap = int(alt.get("page") or 0)
            abbox = alt.get("table_bbox") or []
            if ap and abbox and len(abbox) == 4 and (abbox[2] > abbox[0]) and (abbox[3] > abbox[1]):
                atitle = alt.get("table_title") or ""
                atid = calc_table_id(ap, atitle, abbox)
                afamily = alt.get("table_family") or rec.get("table_family") or ""

                if atid not in tables_by_page[ap]:
                    tables_by_page[ap][atid] = {
                        "table_id": atid,
                        "page": ap,
                        "title": atitle,
                        "family_key": afamily,
                        "models": [],
                        "section": section,
                        "table_bbox": abbox,
                        "title_bbox": [],
                        "min_code_y": abbox[1],
                        "max_code_y": abbox[3],
                        "min_x": abbox[0],
                        "max_x": abbox[2],
                    }
                t = tables_by_page[ap][atid]
                if afamily and not t.get("family_key"):
                    t["family_key"] = afamily
                if model and model != "OPTIONAL" and not is_accessory_title(atitle) and model not in t["models"]:
                    t["models"].append(model)

                prod = catalog_by_code.get(code, {})
                mfg = prod.get("mfg_code") or rec.get("model") or ""
                name = prod.get("name") or prod.get("description") or atitle or ""
                codes_by_page[ap].append(
                    {
                        "pt": code,
                        "model": mfg if mfg != "OPTIONAL" else (rec.get("model") or "OPTIONAL"),
                        "mfg_code": mfg,
                        "name": name,
                        "title": atitle,
                        "family": alt.get("table_family") or "",
                        "bbox": abbox,
                        "source": "alternate",
                    }
                )

    print(f"Loaded {len(tables_by_page)} pages with tables and {sum(len(v) for v in codes_by_page.values())} indexed code appearances.")
    return tables_by_page, codes_by_page


def build_component_relations() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    t0 = time.time()
    tables_by_page, codes_by_page = load_tables_and_codes()

    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as f:
        annotations = json.load(f)

    print(f"Processing {len(annotations)} annotations from {ANNOTATIONS_PATH}...")

    relations: list[dict[str, Any]] = []
    unique_accessories: set[str] = set()
    certain_relations_count = 0
    annotations_without_accessory: list[dict[str, Any]] = []
    ambiguous_cases: list[dict[str, Any]] = []

    for a in annotations:
        ctype, status = extract_component_type_and_status(a)
        if not ctype:
            continue

        p = int(a.get("page") or 0)
        tid = a.get("table_id")
        tt = a.get("table_title")
        sec = a.get("section_title")
        raw_text = a.get("raw_text", "")
        abox = a.get("bbox") or {"x0": 0, "y0": 0, "x1": 0, "y1": 0}

        page_tables = list(tables_by_page.get(p, {}).values())
        matched_table = None
        for t in page_tables:
            if (tid and t["table_id"] == tid) or (tt and t["title"] == tt):
                matched_table = t
                break

        if not matched_table and page_tables:
            acx = (abox["x0"] + abox["x1"]) / 2
            for t in page_tables:
                if t["min_x"] - 20 <= acx <= t["max_x"] + 20:
                    matched_table = t
                    break

        col_x0 = (matched_table["min_x"] - 25) if matched_table else (abox["x0"] - 25)
        col_x1 = (matched_table["max_x"] + 25) if matched_table else (abox["x1"] + 25)
        if matched_table:
            top_y = min((matched_table["title_bbox"][1] if matched_table.get("title_bbox") else 999), matched_table["min_code_y"]) - 10
        else:
            top_y = abox["y0"] - 20

        # Calculate bottom_y: find next PRIMARY table in same column
        bottom_y = 790.0
        if matched_table:
            for other_t in page_tables:
                if other_t != matched_table and not is_accessory_title(other_t["title"]):
                    other_cx = (other_t["min_x"] + other_t["max_x"]) / 2
                    if col_x0 <= other_cx <= col_x1:
                        other_top = other_t["min_code_y"]
                        if other_top > matched_table["max_code_y"] + 15:
                            bottom_y = min(bottom_y, other_top - 5)

        # Match coded accessories inside the same table/block
        matched_accs: list[dict[str, Any]] = []
        seen_pts: set[str] = set()
        for c in codes_by_page.get(p, []):
            pt = c["pt"]
            if pt in seen_pts:
                continue
            cbox = c["bbox"]
            if not cbox or len(cbox) < 4 or (cbox[2] <= cbox[0]) or (cbox[3] <= cbox[1]):
                continue

            cx = (cbox[0] + cbox[2]) / 2
            cy = (cbox[1] + cbox[3]) / 2

            if col_x0 <= cx <= col_x1 and top_y <= cy <= bottom_y:
                if is_matching_accessory(ctype, c["title"], c["model"], c["name"], c["family"]):
                    seen_pts.add(pt)
                    if matched_table and (matched_table["min_code_y"] - 2 <= cy <= matched_table["max_code_y"] + 2):
                        evidence = "SAME_TABLE"
                        reason = "INTERNAL_ROW_IN_PRODUCT_TABLE"
                    else:
                        evidence = "EXPLICIT_ACCESSORY_SECTION"
                        reason = "COLUMN_ALIGNED_DEDICATED_ACCESSORY_SECTION"

                    matched_accs.append(
                        {
                            "pt": pt,
                            "model": c["model"],
                            "evidence": evidence,
                            "confidence": 1.0,
                            "association_confidence_reason": reason,
                        }
                    )

        # Determine relation_intent and required_for_sale
        low = raw_text.lower()
        has_non_incluso = any(w in low for w in ["non incluso", "non inclusa", "non inclusi", "non incluse", "non compreso", "non compresa", "non compresi", "non comprese", "senza "]) or status == "COMPONENT_EXCLUDED" or ("esclus" in low and not any(w in low for w in ["obbligatoriamente", "obbligatorio"]))
        # Positive explicit inclusion
        has_incluso = (not has_non_incluso) and any(w in low for w in ["incluso", "inclusa", "inclusi", "incluse", "compreso", "compresa", "compresi", "comprese"])
        has_obbligatorio = any(w in low for w in ["obbligatoriamente", "obbligatorio da abbinare", "abbinare obbligatoriamente", "acquisto obbligatorio", "accessorio obbligatorio"]) or status == "COMPONENT_REQUIRED"
        has_optional = ("optional" in low or "opzionale" in low or status == "COMPONENT_OPTIONAL" or has_non_incluso)
        is_feature = (status in ("FEATURE_INCLUDED", "FEATURE") or any(w in low for w in ["reversibile", "trifase", "monofase", "dotata di pompa", "con pompa"]))

        if has_obbligatorio:
            relation_intent = "ACCESSORY_REQUIRED"
            required_for_sale = True
        elif has_optional:
            relation_intent = "ACCESSORY_OPTIONAL"
            required_for_sale = False
        elif has_incluso:
            # ACCESSORY_INCLUDED_SEPARATE: consentito SOLO con testo esplicito "incluso", codice PT presente e relazione geometrica certa
            if matched_accs and matched_table:
                relation_intent = "ACCESSORY_INCLUDED_SEPARATE"
            else:
                relation_intent = "NO_COMPONENT_CODE"
                matched_accs = []
            required_for_sale = False
        elif is_feature:
            relation_intent = "FEATURE_ONLY"
            required_for_sale = False
            matched_accs = []
        else:
            if matched_accs:
                relation_intent = "ACCESSORY_OPTIONAL"
                required_for_sale = False
            else:
                relation_intent = "NO_COMPONENT_CODE"
                required_for_sale = False

        if relation_intent in ("NO_COMPONENT_CODE", "FEATURE_ONLY"):
            matched_accs = []

        if matched_accs:
            top_reason = matched_accs[0]["association_confidence_reason"]
        elif has_incluso:
            top_reason = "INTEGRATED_IN_PRODUCT_BOX_NO_SEPARATE_CODE"
        elif is_feature:
            top_reason = "PRODUCT_FEATURE_NO_SEPARATE_CODE"
        else:
            top_reason = "NO_CODED_ACCESSORY_IN_MATCHED_BLOCK"

        relation_record = {
            "annotation_id": a["annotation_id"],
            "page": p,
            "table_id": (matched_table.get("table_id") if matched_table else tid) or "",
            "product_context": {
                "table_title": (matched_table.get("title") if matched_table else tt) or "",
                "family_key": (matched_table.get("family_key") if matched_table else "") or "",
                "models": (matched_table.get("models") if matched_table else []) or [],
            },
            "component": {
                "type": ctype,
                "status": status,
                "relation_intent": relation_intent,
                "required_for_sale": required_for_sale,
            },
            "association_confidence_reason": top_reason,
            "accessories": matched_accs,
            "source": "PDF_LAYOUT",
        }

        relations.append(relation_record)

        if matched_accs:
            certain_relations_count += 1
            for acc in matched_accs:
                unique_accessories.add(acc["pt"])
            if len(matched_accs) > 4:
                ambiguous_cases.append({
                    "annotation_id": a["annotation_id"],
                    "page": p,
                    "component_type": ctype,
                    "table_title": tt,
                    "matched_count": len(matched_accs),
                    "raw_text": raw_text,
                })
        else:
            annotations_without_accessory.append({
                "annotation_id": a["annotation_id"],
                "page": p,
                "component_type": ctype,
                "status": status,
                "relation_intent": relation_intent,
                "table_title": tt,
                "raw_text": raw_text,
            })

    elapsed = time.time() - t0
    print(f"Extraction and relation building completed in {elapsed:.2f}s.")

    # Audit Report preparation
    comp_dist = Counter(r["component"]["type"] for r in relations)
    status_dist = Counter(r["component"]["status"] for r in relations)
    intent_dist = Counter(r["component"]["relation_intent"] for r in relations)

    report = {
        "total_relations": len(relations),
        "total_unique_accessories_found": len(unique_accessories),
        "total_accessories_with_code": len(unique_accessories),
        "certain_relations_count": certain_relations_count,
        "annotations_without_accessory_count": len(annotations_without_accessory),
        "annotations_without_accessory_sample": annotations_without_accessory[:50],
        "ambiguous_cases_count": len(ambiguous_cases),
        "ambiguous_cases_sample": ambiguous_cases[:50],
        "distribution_by_component_type": dict(comp_dist.most_common()),
        "distribution_by_status": dict(status_dist.most_common()),
        "distribution_by_relation_intent": dict(intent_dist.most_common()),
    }

    return relations, report


def save_results(relations: list[dict[str, Any]], report: dict[str, Any]):
    print(f"Writing {OUTPUT_KNOWLEDGE_JSON}...")
    with OUTPUT_KNOWLEDGE_JSON.open("w", encoding="utf-8") as f:
        json.dump(relations, f, indent=2, ensure_ascii=False)

    print(f"Writing {OUTPUT_ROOT_JSON}...")
    with OUTPUT_ROOT_JSON.open("w", encoding="utf-8") as f:
        json.dump(relations, f, indent=2, ensure_ascii=False)

    print(f"Writing {OUTPUT_REPORT_JSON}...")
    with OUTPUT_REPORT_JSON.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("All outputs successfully written.")


if __name__ == "__main__":
    relations, report = build_component_relations()
    save_results(relations, report)
    print("\n--- COMPONENT RELATIONS REPORT SUMMARY ---")
    print(f"Total relations: {report['total_relations']}")
    print(f"Unique coded accessories found: {report['total_unique_accessories_found']}")
    print(f"Certain relations (with >= 1 accessory in same table/block): {report['certain_relations_count']}")
    print(f"Annotations without accessory (included/in box or no separate code): {report['annotations_without_accessory_count']}")
    print(f"Ambiguous cases (>4 accessories in block): {report['ambiguous_cases_count']}")
    print("\nTop Component Types:")
    for k, v in list(report['distribution_by_component_type'].items())[:15]:
        print(f"  {k:26s}: {v:5d}")
    print("\nStatus Distribution:")
    for k, v in report['distribution_by_status'].items():
        print(f"  {k:26s}: {v:5d}")
    print("\nRelation Intent Distribution:")
    for k, v in report['distribution_by_relation_intent'].items():
        print(f"  {k:30s}: {v:5d}")

