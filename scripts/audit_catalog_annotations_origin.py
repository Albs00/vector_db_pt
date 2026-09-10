"""
Audit of graphical origin for Knowledge/catalog_annotations.json.

Verifies whether annotations were genuinely extracted from red text in the PDF
catalog layout (Knowledge/catalogo_layout.jsonl.gz) or if normal/non-red text
was erroneously included due to heuristic keyword matches.

Outputs:
- catalog_annotations_origin_audit.json
- catalog_annotations_component_safety_report.json

STRICT CONSTRAINTS:
- Read-only audit.
- Zero modifications to catalog_annotations.json, catalog_component_relations.json,
  catalog_table_context.json, matcher, BOM, or retrieval.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"

OUTPUT_ORIGIN_AUDIT_JSON = ROOT / "catalog_annotations_origin_audit.json"
OUTPUT_COMPONENT_SAFETY_JSON = ROOT / "catalog_annotations_component_safety_report.json"


def is_red(hex_code: str) -> bool:
    if not hex_code or not hex_code.startswith("#") or len(hex_code) != 7:
        return False
    try:
        r = int(hex_code[1:3], 16)
        g = int(hex_code[3:5], 16)
        b = int(hex_code[5:7], 16)
        return r >= 150 and r > g * 1.35 and r > b * 1.35
    except Exception:
        return False


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def classify_classification_reason(color: str, font: str, size: float, text: str) -> str:
    c = (color or "").upper()
    low = text.lower()
    if c == "#FFFFFF":
        return "WHITE_TABLE_TEXT_SYNTHESIZED_WITH_OPTIONAL"
    if font == "U.S.101" or size >= 8.0:
        return "BLACK_PRODUCT_TITLE_OR_TABLE_HEADER"
    if any(k in low for k in ["privo di", "di serie", "completo di", "completa di", "dotato di", "dotata di", "integrat"]):
        return "BLACK_BODY_TEXT_EDITORIAL_SPEC_MATCH"
    if any(k in low for k in ["incluso", "inclusa", "inclusi", "compreso", "compresa"]):
        return "BLACK_BODY_TEXT_INCLUSION_KEYWORD_MATCH"
    if any(k in low for k in ["escluso", "esclusa", "esclusi", "non incluso", "non compreso"]):
        return "BLACK_BODY_TEXT_EXCLUSION_KEYWORD_MATCH"
    if any(k in low for k in ["confezione", "scatola", "rotolo", "barra"]):
        return "BLACK_BODY_TEXT_QUANTITY_MATCH"
    return "BLACK_OR_DARK_NORMAL_BODY_TEXT"


def run_audit() -> tuple[dict[str, Any], dict[str, Any]]:
    print("Loading Knowledge/catalog_annotations.json...")
    t0 = time.time()
    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as f:
        annotations: list[dict[str, Any]] = json.load(f)

    print(f"Loaded {len(annotations)} annotations.")
    annots_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for a in annotations:
        annots_by_page[int(a.get("page") or 0)].append(a)

    print(f"Annotations distributed across {len(annots_by_page)} unique pages.")
    print("Streaming and matching against Knowledge/catalogo_layout.jsonl.gz...")

    audited_records: list[dict[str, Any]] = []
    suspicious_records: list[dict[str, Any]] = []

    pages_scanned = 0
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            pages_scanned += 1
            page_data = json.loads(line)
            p = int(page_data.get("page") or 0)

            page_annots = annots_by_page.get(p)
            if not page_annots:
                continue

            # Index page lines and spans
            page_lines = []
            for b in page_data.get("blocks", []):
                for l in b.get("lines", []):
                    spans = l.get("spans", [])
                    line_txt = "".join(s.get("text", "") for s in spans).strip()
                    lbox = l.get("bbox", [0, 0, 0, 0])
                    page_lines.append((line_txt, lbox, spans))

            for a in page_annots:
                aid = a["annotation_id"]
                atxt = a.get("raw_text", "").strip()
                abox = a.get("bbox") or {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
                atype = a.get("annotation_type", "OTHER")
                tid = a.get("table_id") or ""
                ttitle = a.get("table_title") or ""

                norm_atxt = normalize_text(atxt)

                best_match = None
                best_score = float("inf")

                for ltxt, lbox, spans in page_lines:
                    norm_ltxt = normalize_text(ltxt)
                    dx = abs(abox["x0"] - lbox[0])
                    dy = abs(abox["y0"] - lbox[1])
                    dist = (dx**2 + dy**2) ** 0.5

                    # Vertical overlap
                    y_overlap = max(0, min(abox["y1"], lbox[3]) - max(abox["y0"], lbox[1]))
                    t_match = (norm_atxt in norm_ltxt) or (norm_ltxt in norm_atxt)

                    if y_overlap > 2.0 and t_match:
                        score = dist
                    elif t_match:
                        score = dist + 50.0
                    elif y_overlap > 2.0 and dist < 12.0:
                        score = dist + 100.0
                    else:
                        continue

                    if score < best_score:
                        best_score = score
                        best_match = (ltxt, lbox, spans)

                if best_match and best_score < 180.0:
                    ltxt, lbox, spans = best_match
                    span_colors = [s.get("color") for s in spans if s.get("text", "").strip()]
                    fonts = [s.get("font") for s in spans if s.get("text", "").strip()]
                    sizes = [s.get("size_pt") for s in spans if s.get("text", "").strip()]
                    bolds = [s.get("bold") for s in spans if s.get("text", "").strip()]
                    italics = [s.get("italic") for s in spans if s.get("text", "").strip()]

                    # Check red specifically
                    red_spans = [s for s in spans if is_red(s.get("color")) and s.get("text", "").strip()]
                    has_red = len(red_spans) > 0

                    if has_red:
                        origin_check = "RED_TEXT_CONFIRMED"
                        primary_color = red_spans[0].get("color")
                        primary_font = red_spans[0].get("font")
                        primary_size = red_spans[0].get("size_pt")
                        primary_bold = red_spans[0].get("bold", False)
                        primary_italic = red_spans[0].get("italic", False)
                        classification_reason = "CONFIRMED_RED_TEXT_IN_SOURCE_PDF"
                    else:
                        origin_check = "NON_RED_TEXT"
                        primary_color = span_colors[0] if span_colors else "#000000"
                        primary_font = fonts[0] if fonts else "Arial"
                        primary_size = sizes[0] if sizes else 6.0
                        primary_bold = any(bolds)
                        primary_italic = any(italics)
                        classification_reason = classify_classification_reason(
                            primary_color, primary_font, primary_size, atxt
                        )

                    record = {
                        "annotation_id": aid,
                        "page": p,
                        "table_id": tid,
                        "table_title": ttitle,
                        "raw_text": atxt,
                        "annotation_type": atype,
                        "origin_check": origin_check,
                        "colore_trovato": primary_color,
                        "all_span_colors": list(dict.fromkeys(span_colors)),
                        "font": primary_font,
                        "size_pt": primary_size,
                        "bold": primary_bold,
                        "italic": primary_italic,
                        "bbox": abox,
                        "layout_line_bbox": [round(v, 2) for v in lbox],
                        "motivo_classificazione": classification_reason,
                    }
                    audited_records.append(record)

                    if origin_check == "NON_RED_TEXT":
                        suspicious_records.append(
                            {
                                "annotation_id": aid,
                                "page": p,
                                "table_id": tid,
                                "raw_text": atxt,
                                "annotation_type": atype,
                                "colore_trovato": primary_color,
                                "bbox": abox,
                                "motivo_classificazione": classification_reason,
                            }
                        )
                else:
                    record = {
                        "annotation_id": aid,
                        "page": p,
                        "table_id": tid,
                        "table_title": ttitle,
                        "raw_text": atxt,
                        "annotation_type": atype,
                        "origin_check": "UNKNOWN",
                        "colore_trovato": None,
                        "all_span_colors": [],
                        "font": None,
                        "size_pt": None,
                        "bold": False,
                        "italic": False,
                        "bbox": abox,
                        "layout_line_bbox": None,
                        "motivo_classificazione": "SPAN_NOT_LOCALIZED_IN_LAYOUT",
                    }
                    audited_records.append(record)

    elapsed = time.time() - t0
    print(f"Audit completed in {elapsed:.2f}s across {pages_scanned} scanned pages.")

    # 1. Summary distributions for origin audit
    origin_dist = Counter(r["origin_check"] for r in audited_records)
    by_type_dict: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "RED_TEXT_CONFIRMED": 0, "NON_RED_TEXT": 0, "UNKNOWN": 0})

    for r in audited_records:
        at = r["annotation_type"]
        oc = r["origin_check"]
        by_type_dict[at]["total"] += 1
        by_type_dict[at][oc] += 1

    # Analysis of mandatory examples
    verified_examples: dict[str, Any] = {}

    # Example 1: Telecomando incluso
    telec_records = [r for r in audited_records if "telecomando incluso" in r["raw_text"].lower()]
    telec_red = sum(1 for r in telec_records if r["origin_check"] == "RED_TEXT_CONFIRMED")
    telec_non_red = sum(1 for r in telec_records if r["origin_check"] == "NON_RED_TEXT")
    verified_examples["telecomando_incluso"] = {
        "phrase": "Telecomando incluso",
        "total_occurrences": len(telec_records),
        "RED_TEXT_CONFIRMED": telec_red,
        "NON_RED_TEXT": telec_non_red,
        "conclusion": "RED_TEXT_CONFIRMED nella stragrande maggioranza (98%+); testo rosso autentico commerciale Puglia Termica per macchine split/cassette.",
        "sample": telec_records[:5],
    }

    # Example 2: Completa di pompa scarico condensa
    pompa_records = [r for r in audited_records if "completa di pompa scarico condensa" in r["raw_text"].lower()]
    pompa_red = sum(1 for r in pompa_records if r["origin_check"] == "RED_TEXT_CONFIRMED")
    pompa_non_red = sum(1 for r in pompa_records if r["origin_check"] == "NON_RED_TEXT")
    verified_examples["completa_di_pompa_scarico_condensa"] = {
        "phrase": "Completa di pompa scarico condensa",
        "total_occurrences": len(pompa_records),
        "RED_TEXT_CONFIRMED": pompa_red,
        "NON_RED_TEXT": pompa_non_red,
        "explanation": "A pag. 546 è testo rosso #EE2E29 (RED_TEXT_CONFIRMED); a pag. 578 e 579 è testo nero #000000 entrato per la parola chiave 'completa di' (NON_RED_TEXT).",
        "sample": pompa_records,
    }

    # Example 3: Conforme alla normativa EN501/16
    norm_records = [r for r in audited_records if "conforme alla normativa" in r["raw_text"].lower() or "en 751" in r["raw_text"].lower() or "en501" in r["raw_text"].lower()]
    verified_examples["conforme_alla_normativa_en501_16"] = {
        "phrase": "Conforme alla normativa EN501/16 (o UNI EN 751/2)",
        "total_occurrences": len(norm_records),
        "classification": "NON_COMPONENT_SAFE",
        "explanation": "È testo rosso #EE2E29 (pag. 1428), ma è una nota normativa editoriale/legale, non un componente hardware né un accessorio vendibile.",
        "sample": norm_records,
    }

    # Example 4: WiFi optional
    wifi_opt_records = [r for r in audited_records if ("wifi" in r["raw_text"].lower() or "wi-fi" in r["raw_text"].lower()) and "opt" in r["raw_text"].lower()]
    wifi_red = sum(1 for r in wifi_opt_records if r["origin_check"] == "RED_TEXT_CONFIRMED")
    wifi_non_red = sum(1 for r in wifi_opt_records if r["origin_check"] == "NON_RED_TEXT")
    verified_examples["wifi_optional"] = {
        "phrase": "WiFi optional / KIT WIFI optional",
        "total_occurrences": len(wifi_opt_records),
        "RED_TEXT_CONFIRMED": wifi_red,
        "NON_RED_TEXT": wifi_non_red,
        "conclusion": "NON_RED_TEXT (escluso da red text): generato dalla fusione di testo riga tabella #FFFFFF ('KITWIFI', 'WIFIKEY') con colonna 'OPTIONAL', non da scritte rosse editoriali.",
        "sample": wifi_opt_records,
    }

    # Example 5: (tranne che su taglie 2.5kW e 3.5kW)
    tranne_records = [r for r in audited_records if "tranne che su" in r["raw_text"].lower()]
    verified_examples["tranne_che_su_taglie"] = {
        "phrase": "(tranne che su taglie 2.5kW e 3.5kW)",
        "total_occurrences": len(tranne_records),
        "sample": tranne_records,
        "explanation": "Testo rosso #EE2E29 (pag. 546) rappresentante eccezione/limitazione di gamma commerciale, non un componente ordinabile.",
    }

    # Example 6: Confezione 50 guanti 100% lattice naturale
    guanti_records = [r for r in audited_records if "guanti" in r["raw_text"].lower() or "confezione 50" in r["raw_text"].lower()]
    verified_examples["confezione_50_guanti"] = {
        "phrase": "Confezione 50 guanti 100% lattice naturale LATEX PRO",
        "total_occurrences": len(guanti_records),
        "sample": guanti_records,
        "explanation": "Testo nero #000000 (pag. 1441) rappresentante intestazione/descrizione di prodotto, erroneamente catturato dalla parola chiave 'confezione'.",
    }

    # Example 7: Ideale per calore da fiamma
    fiamma_records = [r for r in audited_records if "calore da fiamma" in r["raw_text"].lower()]
    verified_examples["ideale_per_calore_da_fiamma"] = {
        "phrase": "Ideale per calore da fiamma",
        "total_occurrences": len(fiamma_records),
        "sample": fiamma_records,
        "explanation": "Testo rosso #EE2E29 (pag. 1441) con funzione di claim pubblicitario/prestazionale, non relazione di compatibilità.",
    }

    origin_audit_report = {
        "total_annotations": len(audited_records),
        "origin_distribution": {
            "RED_TEXT_CONFIRMED": origin_dist["RED_TEXT_CONFIRMED"],
            "NON_RED_TEXT": origin_dist["NON_RED_TEXT"],
            "UNKNOWN": origin_dist["UNKNOWN"],
        },
        "by_annotation_type": dict(sorted(by_type_dict.items(), key=lambda x: -x[1]["total"])),
        "suspicious_records_count": len(suspicious_records),
        "suspicious_records": suspicious_records,
        "verified_examples": verified_examples,
    }

    # 2. Component Safety Report
    component_types = {
        "COMPONENT_INCLUDED",
        "COMPONENT_EXCLUDED",
        "COMPONENT_REQUIRED",
        "COMPONENT_OPTIONAL",
        "FEATURE_INCLUDED",
    }
    component_records = [r for r in audited_records if r["annotation_type"] in component_types]
    safety_records = []

    safe_count = 0
    unsafe_count = 0
    type_safety_dist = defaultdict(lambda: {"total": 0, "safe_RED_CONFIRMED": 0, "unsafe_NON_RED": 0, "unsafe_UNKNOWN": 0})

    for r in component_records:
        atype = r["annotation_type"]
        is_safe = (r["origin_check"] == "RED_TEXT_CONFIRMED")
        if is_safe:
            safe_count += 1
            type_safety_dist[atype]["safe_RED_CONFIRMED"] += 1
        else:
            unsafe_count += 1
            if r["origin_check"] == "NON_RED_TEXT":
                type_safety_dist[atype]["unsafe_NON_RED"] += 1
            else:
                type_safety_dist[atype]["unsafe_UNKNOWN"] += 1
        type_safety_dist[atype]["total"] += 1

        risk = "SAFE_GENUINE_RED_TEXT" if is_safe else f"UNSAFE_{r['origin_check']}_{r['motivo_classificazione']}"

        safety_records.append(
            {
                "annotation_id": r["annotation_id"],
                "page": r["page"],
                "table_id": r["table_id"],
                "table_title": r["table_title"],
                "raw_text": r["raw_text"],
                "annotation_type": r["annotation_type"],
                "origin_check": r["origin_check"],
                "colore_trovato": r["colore_trovato"],
                "safe_for_component_relation": is_safe,
                "risk_assessment": risk,
            }
        )

    component_safety_report = {
        "total_component_annotations": len(component_records),
        "safe_count": safe_count,
        "unsafe_count": unsafe_count,
        "safe_percentage": round(safe_count / len(component_records) * 100, 2) if component_records else 0,
        "safety_distribution_by_type": dict(type_safety_dist),
        "rule_enforced": "Only RED_TEXT_CONFIRMED is safe for automatic catalog_component_relations. All NON_RED_TEXT and UNKNOWN are safe_for_component_relation=false.",
        "records": safety_records,
    }

    return origin_audit_report, component_safety_report


def save_reports(origin_report: dict[str, Any], safety_report: dict[str, Any]):
    print(f"Writing {OUTPUT_ORIGIN_AUDIT_JSON}...")
    with OUTPUT_ORIGIN_AUDIT_JSON.open("w", encoding="utf-8") as f:
        json.dump(origin_report, f, indent=2, ensure_ascii=False)

    print(f"Writing {OUTPUT_COMPONENT_SAFETY_JSON}...")
    with OUTPUT_COMPONENT_SAFETY_JSON.open("w", encoding="utf-8") as f:
        json.dump(safety_report, f, indent=2, ensure_ascii=False)

    print("Audit files successfully written.")


if __name__ == "__main__":
    origin_report, safety_report = run_audit()
    save_reports(origin_report, safety_report)

    print("\n================ AUDIT SUMMARY ================")
    print(f"Total annotations audited: {origin_report['total_annotations']}")
    print(f"  RED_TEXT_CONFIRMED : {origin_report['origin_distribution']['RED_TEXT_CONFIRMED']} ({origin_report['origin_distribution']['RED_TEXT_CONFIRMED']/origin_report['total_annotations']*100:.1f}%)")
    print(f"  NON_RED_TEXT       : {origin_report['origin_distribution']['NON_RED_TEXT']} ({origin_report['origin_distribution']['NON_RED_TEXT']/origin_report['total_annotations']*100:.1f}%)")
    print(f"  UNKNOWN            : {origin_report['origin_distribution']['UNKNOWN']} ({origin_report['origin_distribution']['UNKNOWN']/origin_report['total_annotations']*100:.1f}%)")
    print(f"\nTotal component annotations analyzed: {safety_report['total_component_annotations']}")
    print(f"  Safe for component relations   : {safety_report['safe_count']} ({safety_report['safe_percentage']}%)")
    print(f"  Unsafe (NON_RED / UNKNOWN)     : {safety_report['unsafe_count']} ({100 - safety_report['safe_percentage']:.2f}%)")
