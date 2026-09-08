"""Build the Knowledge PDF-table context and optionally enrich LanceDB."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

import lancedb
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.catalog_table_context import make_family_key


SOURCE_PATH = ROOT / "catalog_table_context.json"
MASTER_PATH = ROOT / "Knowledge" / "unified_catalog_master.json"
OUTPUT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
DB_PATH = ROOT / "Knowledge" / "vector_db" / "lancedb_store"


def table_id(page: Any, title: Any, bbox: Any) -> str:
    signature = json.dumps(
        [int(page or 0), str(title or ""), [round(float(v), 2) for v in (bbox or [])]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:10].upper()
    return f"PDF_P{int(page or 0):04d}_{digest}"


def load_master() -> Dict[str, Dict[str, Any]]:
    with MASTER_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(item.get("code") or ""): item for item in data if item.get("code")}


def build_context() -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    with SOURCE_PATH.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    master = load_master()
    output: Dict[str, Dict[str, Any]] = {}

    for code, raw in sorted(source.items()):
        item = master.get(str(code))
        if not item:
            raise ValueError(f"Codice layout assente dal master: {code}")
        brand = str(item.get("brand") or "").strip().upper()
        family = str(raw.get("table_family") or "").strip()
        title = str(raw.get("table_title") or family).strip()
        bbox = (raw.get("layout_evidence") or {}).get("table_bbox") or []
        entry: Dict[str, Any] = {
            "brand": brand,
            "catalog_family": family,
            "family_key": make_family_key(brand, family),
            "table_title": title,
            "table_id": table_id(raw.get("page"), title, bbox),
            "page": int(raw.get("page") or 0),
            "section_title": str(raw.get("section_title") or ""),
            "source": "PDF_LAYOUT",
            "confidence": float(raw.get("confidence") or 0.0),
            "model": str(raw.get("model") or item.get("name") or ""),
            "mpn": str(raw.get("mpn") or item.get("mfg_code") or ""),
            "family_conflict": raw.get("family_conflict", False),
        }

        alternates = []
        for alt in raw.get("alternate_table_contexts") or []:
            alt_family = str(alt.get("table_family") or "").strip()
            alt_title = str(alt.get("table_title") or alt_family).strip()
            alt_bbox = alt.get("table_bbox") or []
            alternates.append(
                {
                    "brand": brand,
                    "catalog_family": alt_family,
                    "family_key": make_family_key(brand, alt_family),
                    "table_title": alt_title,
                    "table_id": table_id(alt.get("page"), alt_title, alt_bbox),
                    "page": int(alt.get("page") or 0),
                    "source": "PDF_LAYOUT",
                }
            )
        if alternates:
            entry["alternate_table_contexts"] = alternates
        distinct_families = {family, *(alt["catalog_family"] for alt in alternates)} - {""}
        entry["multiple_table_families"] = len(distinct_families) > 1
        output[str(code)] = entry

    if set(output) != set(source):
        raise AssertionError("Il dataset trasformato non conserva tutti i codici sorgente")
    if any(not value["catalog_family"] for value in output.values()):
        raise AssertionError("Sono presenti prodotti senza catalog_family")
    if any(not value["family_key"] for value in output.values()):
        raise AssertionError("Sono presenti prodotti senza family_key")

    family_brands: Dict[str, set[str]] = defaultdict(set)
    for value in output.values():
        family_brands[value["catalog_family"]].add(value["brand"])
    stats = {
        "records": len(output),
        "pdf_layout_records": sum(value["source"] == "PDF_LAYOUT" for value in output.values()),
        "blank_catalog_family": sum(not value["catalog_family"] for value in output.values()),
        "name_table_conflicts": sum(value["family_conflict"] is not False for value in output.values()),
        "codes_with_multiple_table_families": sum(value["multiple_table_families"] for value in output.values()),
        "families_used_by_multiple_brands": sum(len(brands) > 1 for brands in family_brands.values()),
        "confidence_counts": dict(Counter(str(value["confidence"]) for value in output.values())),
    }
    return output, stats


def save_context(output: Dict[str, Dict[str, Any]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def enrich_lancedb(output: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    db = lancedb.connect(str(DB_PATH))
    table = db.open_table("catalog_products")
    desired_fields = {
        "catalog_family": pa.string(),
        "family_key": pa.string(),
        "table_title": pa.string(),
        "table_id": pa.string(),
        "table_page": pa.int64(),
        "table_section_title": pa.string(),
        "table_source": pa.string(),
        "table_confidence": pa.float64(),
    }
    existing = set(table.schema.names)
    missing = [pa.field(name, dtype) for name, dtype in desired_fields.items() if name not in existing]
    if missing:
        table.add_columns(missing)

    records = [
        {
            "code": code,
            "catalog_family": value["catalog_family"],
            "family_key": value["family_key"],
            "table_title": value["table_title"],
            "table_id": value["table_id"],
            "table_page": value["page"],
            "table_section_title": value["section_title"],
            "table_source": value["source"],
            "table_confidence": value["confidence"],
        }
        for code, value in output.items()
    ]
    table.merge_insert("code").when_matched_update_all().execute(records)
    total = table.count_rows()
    with_context = table.count_rows("table_source = 'PDF_LAYOUT' AND catalog_family IS NOT NULL")
    if total != len(output) or with_context != len(output):
        raise AssertionError(
            f"Copertura LanceDB inattesa: total={total}, PDF_LAYOUT={with_context}, context={len(output)}"
        )
    return {
        "lancedb_rows": total,
        "lancedb_pdf_layout_rows": with_context,
        "lancedb_columns": table.schema.names,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-lancedb", action="store_true")
    args = parser.parse_args()
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Dataset layout sorgente non trovato: {SOURCE_PATH}")
    output, stats = build_context()
    save_context(output)
    if args.update_lancedb:
        stats.update(enrich_lancedb(output))
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
