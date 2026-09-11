"""Finalize the immutable CLIMA BEFORE benchmark from completed legacy shards.

This script does not execute or modify the matcher.  It validates the frozen
input and the four legacy-runtime shards produced before the production master
files were activated, normalizes their benchmark schema, and writes the
release artifacts requested under reports/clima_ab.
"""

from __future__ import annotations

import collections
import hashlib
import json
import shutil
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "clima_ab"
SOURCE_FROZEN = ROOT / "benchmark_clima_input_frozen.jsonl"
TARGET_FROZEN = REPORT_DIR / "benchmark_input_frozen.jsonl"
BEFORE = REPORT_DIR / "before.jsonl"
SUMMARY = REPORT_DIR / "before_summary.json"
MANIFEST = REPORT_DIR / "before_manifest.json"
SHARD_DIR = ROOT / ".codex_tmp" / "benchmark_before_v3"
EXCEL = ROOT / "audit_da_compilare_MPN.xlsx"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def pt_mpn(components: list[dict[str, Any]]) -> str | None:
    """Render main-unit PTs with duplicate UIs preserved and UE last."""
    ui = [str(item.get("pt")) for item in components if item.get("role") == "UI" and item.get("pt")]
    ue = [str(item.get("pt")) for item in components if item.get("role") == "UE" and item.get("pt")]
    pts = ui + ue
    return " + ".join(pts) if pts else None


def normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    components = list(record.get("selected_components") or [])
    selected_ui = [item for item in components if item.get("role") == "UI"]
    selected_ue_items = [item for item in components if item.get("role") == "UE"]
    accessories = [item for item in components if item.get("role") not in {"UI", "UE"}]
    automatic_mpn = pt_mpn(components)
    tiers = [item.get("tier") for item in components if item.get("tier") is not None]
    scores = [item.get("score") for item in components if isinstance(item.get("score"), (int, float))]
    normalized = dict(record)
    normalized.update(
        {
            "selected_ui": selected_ui,
            "selected_ue": selected_ue_items[0] if selected_ue_items else None,
            "accessory_components": accessories,
            "automatic_mpn": automatic_mpn,
            "main_tier": min(tiers) if tiers else None,
            "main_score": max(scores) if scores else None,
            "runtime_source": "LEGACY_CURRENT_RUNTIME",
            "dataset_release": None,
            "schema_version": None,
            "policy": None,
        }
    )
    current = "".join(str(record.get("current_mpn") or "").upper().split())
    automatic = "".join(str(automatic_mpn or "").upper().split())
    if not current or current in {"NT", "NONTROVATO", "N/D", "ND"}:
        normalized["existing_mpn_comparison"] = "NO_EXISTING_MPN"
    else:
        normalized["existing_mpn_comparison"] = (
            "SAME_AS_EXISTING" if current == automatic else "DIFFERENT_FROM_EXISTING"
        )
    return normalized


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not SOURCE_FROZEN.exists() or not EXCEL.exists():
        raise SystemExit("Frozen input or source Excel is missing")

    frozen = read_jsonl(SOURCE_FROZEN)
    climate_ids = {
        item["row_id"] for item in frozen if item.get("benchmark_scope") == "CLIMA"
    }
    if len(frozen) != 4615 or len(climate_ids) != 4453:
        raise SystemExit(
            f"Unexpected frozen population: total={len(frozen)} clima={len(climate_ids)}"
        )

    shard_records: list[dict[str, Any]] = []
    for index in range(4):
        path = SHARD_DIR / f"part_{index}.jsonl"
        if not path.exists():
            raise SystemExit(f"Missing legacy shard: {path}")
        shard_records.extend(read_jsonl(path))

    ids = [item.get("row_id") for item in shard_records]
    duplicate_ids = [key for key, count in collections.Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise SystemExit(f"Duplicate BEFORE row ids: {duplicate_ids[:10]}")
    if set(ids) != climate_ids:
        missing = sorted(climate_ids - set(ids))
        extra = sorted(set(ids) - climate_ids)
        raise SystemExit(f"BEFORE coverage mismatch; missing={missing[:10]} extra={extra[:10]}")

    records = [normalized_record(item) for item in shard_records]
    records.sort(key=lambda item: (str(item.get("sheet")), int(item.get("excel_row") or 0)))
    shutil.copyfile(SOURCE_FROZEN, TARGET_FROZEN)
    write_jsonl(BEFORE, records)

    runtimes = [float(item.get("runtime_ms") or 0.0) for item in records]
    status_counts = collections.Counter(item.get("main_unit_match_status") for item in records)
    config_counts = collections.Counter(item.get("configuration_status") for item in records)
    scope_counts = collections.Counter(item.get("product_scope") for item in records)
    summary = {
        "phase": "BEFORE",
        "runtime": "LEGACY_CURRENT_RUNTIME",
        "rows_processed": len(records),
        "rows_with_automatic_mpn": sum(bool(item.get("automatic_mpn")) for item in records),
        "rows_without_automatic_mpn": sum(not item.get("automatic_mpn") for item in records),
        "rows_failed": sum(bool(item.get("error")) for item in records),
        "main_unit_status_counts": dict(status_counts),
        "configuration_status_counts": dict(config_counts),
        "scope_counts": dict(scope_counts),
        "runtime_total_seconds": round(sum(runtimes) / 1000, 3),
        "runtime_mean_ms": round(statistics.mean(runtimes), 3),
        "runtime_median_ms": round(statistics.median(runtimes), 3),
        "excel_rows_total": len(frozen),
        "clima_rows": len(climate_ids),
        "non_clima_rows": len(frozen) - len(climate_ids),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    started_path = SHARD_DIR / "started_at.txt"
    started_at = started_path.read_text(encoding="utf-8").strip() if started_path.exists() else None
    completed_at = max((SHARD_DIR / f"part_{i}.jsonl").stat().st_mtime for i in range(4))
    manifest = {
        "phase": "BEFORE",
        "captured_runtime": "LEGACY_CURRENT_RUNTIME",
        "git_commit": "1a2cd79495c177e7951faeebb3bb2c095cad2760",
        "git_dirty": True,
        "workspace_freeze": "reports/clima_ab/workspace_freeze.json",
        "excel_path": "audit_da_compilare_MPN.xlsx",
        "excel_sha256": sha256_file(EXCEL),
        "benchmark_input_frozen": "reports/clima_ab/benchmark_input_frozen.jsonl",
        "benchmark_input_frozen_sha256": sha256_file(TARGET_FROZEN),
        "before": "reports/clima_ab/before.jsonl",
        "before_sha256": sha256_file(BEFORE),
        "rows": len(records),
        "started_at": started_at,
        "completed_at": datetime.fromtimestamp(completed_at, tz=timezone.utc).isoformat(),
        "new_master_files_present_but_not_loaded": True,
        "new_clima_master_runtime_active": False,
        "source_shards": [
            {
                "path": f".codex_tmp/benchmark_before_v3/part_{i}.jsonl",
                "sha256": sha256_file(SHARD_DIR / f"part_{i}.jsonl"),
                "rows": len(read_jsonl(SHARD_DIR / f"part_{i}.jsonl")),
            }
            for i in range(4)
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "manifest": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
