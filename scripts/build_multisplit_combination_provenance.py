"""Build an auditable per-combination provenance sidecar from PDF layout evidence.

The compatibility master is read-only. Every master combination starts as
MASTER_DERIVED because build_full_ac_matrix.py assigns the combination lists from
builder rules/fallbacks. A combination is promoted only when a bounded PDF-layout
region contains an explicit UE-governed complete configuration.
"""

import collections
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
OUTPUT_PATH = ROOT / "Knowledge" / "climatizzatori_combinazioni_provenance.json"


# Manually audited regions in the explicit combination table on PDF page 604.
# Bounds are PDF points [x0, y0, x1, y1]. The table has no combination table_id
# in catalog_table_context.json, so table_id/section_id deliberately remain null.
DIRECT_LAYOUT_REGIONS = {
    ("50318438", "25+25"): {
        "bbox": [28.0, 615.0, 175.0, 660.0],
        "ue_model_identifier": "BREVA EX 18000-2 E",
        "required_counts": {"BREVA IN 9000 E": 2, "BREVA EX 18000-2 E": 1},
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 9000 E",
    },
    ("50318438", "25+35"): {
        "bbox": [28.0, 663.0, 175.0, 716.0],
        "ue_model_identifier": "BREVA EX 18000-2 E",
        "required_counts": {
            "BREVA IN 9000 E": 1,
            "BREVA IN 12000 E": 1,
            "BREVA EX 18000-2 E": 1,
        },
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 12000 E",
    },
    ("50318438", "35+35"): {
        "bbox": [28.0, 717.0, 175.0, 774.0],
        "ue_model_identifier": "BREVA EX 18000-2 E",
        "required_counts": {"BREVA IN 12000 E": 2, "BREVA EX 18000-2 E": 1},
        "raw_configuration": "BREVA IN 12000 E + BREVA IN 12000 E",
    },
    ("50215218", "25+25+25"): {
        "bbox": [210.0, 614.0, 345.0, 669.0],
        "ue_model_identifier": "BREVA EX 18.000-3",
        "required_counts": {"BREVA EX 18.000-3": 1, "BREVA IN 9000 E": 3},
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 9000 E",
    },
    ("50215218", "25+25+35"): {
        "bbox": [210.0, 670.0, 345.0, 715.0],
        "ue_model_identifier": "BREVA EX 18.000-3",
        "required_counts": {"ABBINATA A:": 1, "BREVA IN 9000 E": 2, "BREVA IN 12000 E": 1},
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 12000 E",
    },
    ("50215232", "25+25+25+25"): {
        "bbox": [380.0, 614.0, 520.0, 680.0],
        "ue_model_identifier": "BREVA EX 24.000-4",
        "required_counts": {"BREVA EX 24.000-4": 1, "BREVA IN 9000 E": 4},
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 9000 E",
    },
    ("50215232", "25+25+25+35"): {
        "bbox": [380.0, 680.0, 520.0, 737.0],
        "ue_model_identifier": "BREVA EX 24.000-4",
        "required_counts": {"ABBINATA A:": 1, "BREVA IN 9000 E": 3, "BREVA IN 12000 E": 1},
        "raw_configuration": "BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 9000 E + BREVA IN 12000 E",
    },
}


def _page_spans(page_number):
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as stream:
        for line in stream:
            page = json.loads(line)
            if page.get("page") != page_number:
                continue
            spans = []
            for block in page.get("blocks", []):
                for line_obj in block.get("lines", []):
                    for span in line_obj.get("spans", []):
                        text = " ".join(str(span.get("text") or "").split())
                        if text and span.get("bbox"):
                            spans.append({"text": text, "bbox": span["bbox"]})
            return spans
    raise RuntimeError(f"PDF layout page {page_number} not found")


def _inside(span, bounds):
    x0, y0, x1, y1 = span["bbox"]
    bx0, by0, bx1, by1 = bounds
    return x0 >= bx0 and x1 <= bx1 and y0 >= by0 and y1 <= by1


def _verify_direct_regions():
    spans = _page_spans(604)
    verified = {}
    for key, spec in DIRECT_LAYOUT_REGIONS.items():
        region_spans = [span for span in spans if _inside(span, spec["bbox"])]
        counts = {
            text: sum(1 for span in region_spans if text in span["text"])
            for text in spec["required_counts"]
        }
        missing = {
            text: expected - counts[text]
            for text, expected in spec["required_counts"].items()
            if counts[text] < expected
        }
        if missing:
            raise RuntimeError(f"Layout evidence changed for {key}: missing {missing}")
        verified[key] = {
            "evidence_strength": "CATALOG_TABLE_VERIFIED",
            "raw_configuration": spec["raw_configuration"],
            "normalized_configuration": key[1],
            "page": 604,
            "table_id": None,
            "section_id": None,
            "table_title": "TABELLA COMBINAZIONI MULTI SPLIT",
            "ue_model_identifier": spec["ue_model_identifier"],
            "source": "PDF_LAYOUT",
            "evidence_details": (
                "Complete configuration is enumerated inside the bounded UE-governed "
                "column/group on catalog layout page 604. No combination table_id is "
                "available in catalog_table_context.json."
            ),
            "confidence": 1.0,
            "region_bbox": spec["bbox"],
            "layout_evidence": region_spans,
        }
    return verified


def build_sidecar():
    master = json.loads(MASTER_PATH.read_text(encoding="utf-8"))
    direct = _verify_direct_regions()
    sidecar = {}
    strength_counts = collections.Counter({
        "CATALOG_TABLE_VERIFIED": 0,
        "MASTER_DERIVED": 0,
        "UNKNOWN_PROVENANCE": 0,
    })
    brand_counts = collections.defaultdict(collections.Counter)

    for ue_pt, ue in master.get("unita_esterne", {}).items():
        combinations = ue.get("combinazioni_ammesse") or ue.get("combinazioni_ammesse_taglie") or []
        if not combinations:
            continue
        records = {}
        for combination in combinations:
            normalized = str(combination).replace(" ", "")
            evidence = direct.get((str(ue_pt), normalized))
            if evidence is None:
                evidence = {
                    "evidence_strength": "MASTER_DERIVED",
                    "raw_configuration": str(combination),
                    "normalized_configuration": normalized,
                    "page": ue.get("pagina_combinazioni_catalogo"),
                    "table_id": None,
                    "section_id": None,
                    "table_title": ue.get("nome_tabella_combinazioni"),
                    "ue_model_identifier": ue.get("codice_mfg") or ue.get("mfg_code"),
                    "source": "BUILD_FULL_AC_MATRIX",
                    "evidence_details": (
                        "The master builder assigns allowed_combinations from a static "
                        "MULTI_SPLIT_RULES comb_by_ports list or a port-count fallback. "
                        "No unambiguous PDF-layout row/cell for this exact full multiset "
                        "was established by this audit."
                    ),
                    "confidence": 1.0,
                    "builder_reference": "build_full_ac_matrix.py:756-774,1013-1014",
                    "layout_evidence": [],
                }
            records[normalized] = evidence
            strength = evidence["evidence_strength"]
            strength_counts[strength] += 1
            brand_counts[str(ue.get("brand") or "UNKNOWN")][strength] += 1
        sidecar[str(ue_pt)] = records

    sidecar["_metadata"] = {
        "schema_version": "1.0",
        "source_master": "Knowledge/climatizzatori_compatibilita_master.json",
        "source_layout": "Knowledge/catalogo_layout.jsonl.gz",
        "classification_policy": (
            "Per-configuration. Direct only with bounded UE-governed complete layout "
            "evidence; builder page/table/kit metadata alone is never direct evidence."
        ),
        "total_master_combinations": sum(strength_counts.values()),
        "evidence_strength_distribution": dict(sorted(strength_counts.items())),
        "by_brand": {
            brand: dict(sorted(counts.items()))
            for brand, counts in sorted(brand_counts.items())
        },
        "ambiguous_cases": [
            {
                "ue_pt": "50215232",
                "normalized_configuration": "25+25+25+35",
                "issue": "LAYOUT_CONFIGURATION_ABSENT_FROM_MASTER",
                "decision": "NOT_ADDED_TO_SIDECAR",
            },
            {
                "ue_pt": "50215232",
                "normalized_configuration": "25+25+35+35",
                "issue": "LAYOUT_CONFIGURATION_ABSENT_FROM_MASTER",
                "decision": "NOT_ADDED_TO_SIDECAR",
            },
        ],
        "negative_audit": {
            "50215232:25+25+35+35": {
                "present_in_master": False,
                "sidecar_entry_created": False,
                "decision": "NOT_VERIFIED",
                "reason": "Configuration is absent from the master and is not added by the provenance sidecar.",
            }
        },
    }
    return sidecar


if __name__ == "__main__":
    OUTPUT_PATH.write_text(
        json.dumps(build_sidecar(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH)
