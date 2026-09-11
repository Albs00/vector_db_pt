import collections
import json
import math
import statistics
from datetime import datetime, timezone

from run_benchmark import (
    FROZEN,
    MANIFEST,
    OUTPUT,
    ROOT,
    SUMMARY,
    build_manifest,
    freeze_input,
    json_dump_line,
    percentile,
)


def main():
    records, meta = freeze_input()
    results = []
    for index in range(4):
        path = ROOT / ".codex_tmp" / "benchmark_before_v3" / f"part_{index}.jsonl"
        with open(path, "r", encoding="utf-8") as handle:
            results.extend(json.loads(line) for line in handle if line.strip())
    results.sort(key=lambda item: (item["sheet"], item["excel_row"]))
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        for record in results:
            handle.write(json_dump_line(record) + "\n")
    runtimes = [record["runtime_ms"] for record in results]
    raw_scopes = collections.Counter(record.get("product_scope") or "GENERAL" for record in results)
    scope_counts = collections.Counter()
    for key, value in raw_scopes.items():
        normalized = key if key in {"MONOSPLIT", "MULTISPLIT", "UI_ONLY", "UE_ONLY"} else "GENERAL"
        scope_counts[normalized] += value
    for key in ("MONOSPLIT", "MULTISPLIT", "UI_ONLY", "UE_ONLY", "GENERAL"):
        scope_counts.setdefault(key, 0)
    identity_counts = collections.Counter(record.get("main_unit_match_status") for record in results)
    config_counts = collections.Counter(record.get("configuration_status") for record in results)
    comparison_counts = collections.Counter(record.get("existing_mpn_comparison") for record in results)
    started_text = (ROOT / ".codex_tmp" / "benchmark_before_v3" / "started_at.txt").read_text(encoding="utf-8").strip()
    started = datetime.fromisoformat(started_text)
    summary = {
        **meta,
        "rows_processed": len(results),
        "rows_failed": sum(bool(record.get("error")) for record in results),
        "scope_counts": dict(scope_counts),
        "automatic_mpn_present": sum(bool(record.get("automatic_mpn")) for record in results),
        "automatic_mpn_missing": sum(not record.get("automatic_mpn") for record in results),
        "exact_identity_rows": identity_counts.get("EXACT", 0),
        "discovery_only_rows": identity_counts.get("DISCOVERY_ONLY", 0),
        "main_unit_status_counts": dict(identity_counts),
        "configuration_status_counts": dict(config_counts),
        "existing_mpn_comparison_counts": dict(comparison_counts),
        "runtime_total_seconds": round(sum(runtimes) / 1000, 3),
        "runtime_wall_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
        "runtime_mean_ms": round(statistics.mean(runtimes), 3),
        "runtime_median_ms": round(statistics.median(runtimes), 3),
        "runtime_p95_ms": round(percentile(runtimes, 0.95), 3),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = build_manifest(meta, summary, started)
    print(json.dumps({"summary": summary, "manifest": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
