import csv
import json
import sys
from collections import Counter
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "family_audit_report.json"
OUTPUT_JSON = ROOT / "family_audit_issues_report.json"
OUTPUT_CSV = ROOT / "family_audit_issues_report.csv"

FIELDS = [
    "pt_code", "brand", "model", "current_family", "current_family_key",
    "proposed_family", "proposed_family_key", "page", "table_id", "issue_type",
    "confidence", "evidence", "auto_correctable",
]


def main():
    report = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    records = [record for record in report["records"] if record["issue_type"] != "OK"]
    counts = Counter(record["issue_type"] for record in records)
    by_brand = {}
    for record in records:
        by_brand.setdefault(record["brand"], Counter())[record["issue_type"]] += 1

    filtered = {
        "metadata": {
            "audit": "family_audit_filtered",
            "source_report": "family_audit_report.json",
            "source_context": report["metadata"]["context"],
            "primary_source": report["metadata"]["primary_source"],
            "scope": "Solo casi ambigui o da correggere/revisionare; issue_type diverso da OK.",
            "context_modified": False,
        },
        "summary": {
            "record_filtrati": len(records),
            "issue_counts": dict(counts),
            "errori_certi": sum(record["auto_correctable"] for record in records),
            "distribuzione_per_brand": {brand: dict(value) for brand, value in sorted(by_brand.items())},
            "top_50": records[:50],
        },
        "records": records,
    }
    OUTPUT_JSON.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["evidence"] = json.dumps(row["evidence"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow({field: row.get(field) for field in FIELDS})
    print(json.dumps({
        "json": str(OUTPUT_JSON),
        "csv": str(OUTPUT_CSV),
        "summary": filtered["summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
