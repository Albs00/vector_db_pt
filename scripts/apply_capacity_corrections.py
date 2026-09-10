import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json"
LEDGER_PATH = ROOT / "capacity_audit_corrections.json"
REPORT_PATH = ROOT / "capacity_audit_report.json"


APPROVED_BTU = {
    "50368716": 48000,
    "50202140": 12000,
    "50202157": 18000,
    "99508685": 7000,
    "99508715": 18000,
    "99508616": 7000,
    "99508654": 12000,
    "99508661": 18000,
    "50224067": 15000,
    "50490486": 12000,
    "50490493": 15000,
    "50490462": 7000,
    "50284115": 12000,
    "50315833": 12000,
    "50109302": 18000,
    "99717810": 21000,
    "50134854": 12000,
    "50204915": 12000,
    "50364848": 12000,
    "50367719": 12000,
    "99643317": 5000,
    "99642983": 7000,
    "99643027": 18000,
    "99794088": 5000,
    "99793821": 7000,
    "99793852": 15000,
    "99793869": 18000,
    "99794071": 5000,
    "99793753": 15000,
    "99794095": 5000,
    "99793777": 7000,
    "99793807": 15000,
    "99793814": 18000,
    "50308736": 5000,
    "50308712": 5000,
    "50308729": 5000,
}

REVIEWED_NO_CHANGE = {
    "50284078": 12000,
    "50199075": 48000,
}

USER_OVERRIDES = {
    "99643317",
    "99794088",
    "99794071",
    "99794095",
    "50284078",
    "50199075",
    "50308736",
    "50308712",
    "50308729",
}


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_btu(value):
    return f"{value:,}".replace(",", ".") + " BTU"


def replace_capacity_text(value, old_btu, new_btu):
    if not isinstance(value, str):
        return value
    value = re.sub(
        rf"(?<!\d){old_btu}\s*BTU\b",
        f"{new_btu} BTU",
        value,
        flags=re.IGNORECASE,
    )
    if old_btu % 1000 == 0 and new_btu % 1000 == 0:
        value = re.sub(
            rf"(?<!\d){old_btu // 1000}k\b",
            f"{new_btu // 1000}k",
            value,
            flags=re.IGNORECASE,
        )
    return value


def update_embedded_kit_labels(record, old_btu, new_btu, field_counts):
    for item in record.get("kit_commerciali_inclusi") or []:
        if not isinstance(item, dict):
            continue
        for field in ("kit_name", "nome_kit", "configurazione", "configuration"):
            old_value = item.get(field)
            new_value = replace_capacity_text(old_value, old_btu, new_btu)
            if new_value != old_value:
                item[field] = new_value
                field_counts[f"kit_commerciali_inclusi.{field}"] += 1


def update_unit(record, code, new_btu, stats):
    old_btu = record.get("taglia_btu")
    stats[code]["occurrences_seen"] += 1
    stats[code]["old_values"][str(old_btu)] += 1

    expected_fields = {
        "taglia_btu": new_btu,
        "tag_btu": f"{new_btu} btu",
        "tag_btu_display": display_btu(new_btu),
    }
    for field, expected in expected_fields.items():
        if field in record and record[field] != expected:
            record[field] = expected
            stats[code]["field_updates"][field] += 1

    tags = record.get("tags")
    if isinstance(tags, list):
        expected_tag = display_btu(new_btu)
        for index, tag in enumerate(tags):
            if isinstance(tag, str) and re.fullmatch(r"\d{1,3}(?:\.\d{3})?\s*BTU", tag, re.IGNORECASE):
                if tag != expected_tag:
                    tags[index] = expected_tag
                    stats[code]["field_updates"]["tags"] += 1

    if old_btu is not None and old_btu != new_btu:
        update_embedded_kit_labels(record, old_btu, new_btu, stats[code]["field_updates"])


def update_kit_container(record, stats):
    components = record.get("componenti_ui")
    if not isinstance(components, list) or len(components) != 1:
        return
    component = components[0]
    if not isinstance(component, dict):
        return
    code = str(component.get("code") or component.get("codice_pt") or "")
    if code not in APPROVED_BTU:
        return
    new_btu = APPROVED_BTU[code]
    for field in ("kit_name", "nome_kit"):
        old_value = record.get(field)
        if not isinstance(old_value, str):
            continue
        new_value = re.sub(r"(?<!\d)\d{4,6}\s*BTU\b", f"{new_btu} BTU", old_value, flags=re.IGNORECASE)
        if new_value != old_value:
            record[field] = new_value
            stats[code]["field_updates"][field] += 1
    for field in ("configurazione", "configuration"):
        old_value = record.get(field)
        if not isinstance(old_value, str) or new_btu % 1000:
            continue
        new_value = re.sub(r"(?<!\d)\d+k\b", f"{new_btu // 1000}k", old_value, flags=re.IGNORECASE)
        if new_value != old_value:
            record[field] = new_value
            stats[code]["field_updates"][field] += 1


def walk_and_update(value, stats):
    if isinstance(value, dict):
        code = str(value.get("code") or value.get("codice_pt") or "")
        if code in APPROVED_BTU and "taglia_btu" in value:
            update_unit(value, code, APPROVED_BTU[code], stats)
        for child in value.values():
            walk_and_update(child, stats)
        update_kit_container(value, stats)
    elif isinstance(value, list):
        for child in value:
            walk_and_update(child, stats)


def find_occurrences(value, expected):
    seen = Counter()
    mismatches = []

    def walk(item, path="$"):
        if isinstance(item, dict):
            code = str(item.get("code") or item.get("codice_pt") or "")
            if code in expected and "taglia_btu" in item:
                seen[code] += 1
                btu = expected[code]
                checks = {
                    "taglia_btu": btu,
                    "tag_btu": f"{btu} btu",
                    "tag_btu_display": display_btu(btu),
                }
                for field, wanted in checks.items():
                    if field in item and item[field] != wanted:
                        mismatches.append({"path": path, "field": field, "actual": item[field], "expected": wanted})
            for key, child in item.items():
                walk(child, f"{path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")

    walk(value)
    return seen, mismatches


def main():
    existing_ledger = {}
    if LEDGER_PATH.exists():
        existing_ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    before_hash = file_sha256(MASTER_PATH)
    with MASTER_PATH.open(encoding="utf-8") as handle:
        master = json.load(handle)

    top_level_ui = master["unita_interne"]
    original_values = {code: top_level_ui[code].get("taglia_btu") for code in APPROVED_BTU | REVIEWED_NO_CHANGE}
    pending_codes = {code for code, value in APPROVED_BTU.items() if original_values[code] != value}
    if not pending_codes:
        print("Le correzioni risultano gia applicate; nessuna scrittura eseguita.")
        return
    ue_kw_before = {code: record.get("potenza_nominale_kw") for code, record in master["unita_esterne"].items()}

    source_corrections = {
        item["pt_code"]: item for item in existing_ledger.get("corrections", [])
    }
    report_rows = {}
    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        report_rows = {item["pt_code"]: item for item in report.get("records", [])}
    stats = defaultdict(lambda: {"occurrences_seen": 0, "old_values": Counter(), "field_updates": Counter()})
    walk_and_update(master, stats)

    expected_all = APPROVED_BTU | REVIEWED_NO_CHANGE
    seen, mismatches = find_occurrences(master, expected_all)
    missing_codes = sorted(code for code in expected_all if not seen[code])
    ue_kw_after = {code: record.get("potenza_nominale_kw") for code, record in master["unita_esterne"].items()}
    if mismatches or missing_codes or ue_kw_before != ue_kw_after:
        raise RuntimeError(json.dumps({
            "mismatches": mismatches[:20],
            "missing_codes": missing_codes,
            "ue_kw_changed": ue_kw_before != ue_kw_after,
        }, ensure_ascii=False, indent=2))

    temporary_path = MASTER_PATH.with_suffix(MASTER_PATH.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(master, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary_path.replace(MASTER_PATH)
    after_hash = file_sha256(MASTER_PATH)

    decisions = []
    for code, new_btu in APPROVED_BTU.items():
        record = top_level_ui[code]
        source = source_corrections.get(code, {})
        if source.get("status") == "applied" and code not in pending_codes:
            decisions.append(source)
            continue
        report_row = report_rows.get(code, {})
        decisions.append({
            "pt_code": code,
            "brand": record.get("brand"),
            "mfg_code": record.get("mfg_code"),
            "name": record.get("name") or record.get("nome"),
            "series": record.get("serie") or record.get("famiglia_catalogo"),
            "field": "taglia_btu",
            "old_value": original_values[code],
            "audit_proposed_value": source.get("audit_proposed_value", source.get("proposed_value", report_row.get("proposed_btu"))),
            "applied_value": new_btu,
            "status": "applied",
            "decision_source": "user_override" if code in USER_OVERRIDES else "user_approved_audit",
            "occurrences_updated": stats[code]["occurrences_seen"],
            "field_updates": dict(stats[code]["field_updates"]),
            "evidence": source.get("evidence", report_row.get("evidence", [])),
        })
    for code, value in REVIEWED_NO_CHANGE.items():
        record = top_level_ui[code]
        source = source_corrections.get(code, {})
        if source.get("status") == "reviewed_no_change":
            decisions.append(source)
            continue
        decisions.append({
            "pt_code": code,
            "brand": record.get("brand"),
            "mfg_code": record.get("mfg_code"),
            "name": record.get("name") or record.get("nome"),
            "series": record.get("serie") or record.get("famiglia_catalogo"),
            "field": "taglia_btu",
            "old_value": original_values[code],
            "audit_proposed_value": source.get("proposed_value"),
            "applied_value": value,
            "status": "reviewed_no_change",
            "decision_source": "user_override",
            "occurrences_verified": seen[code],
            "field_updates": {},
            "evidence": source.get("evidence", []),
        })

    ledger = {
        "metadata": {
            "file": LEDGER_PATH.name,
            "status": "applied",
            "applied_at_utc": existing_ledger.get("metadata", {}).get("applied_at_utc", datetime.now(timezone.utc).isoformat()),
            "last_applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "application_runs": existing_ledger.get("metadata", {}).get("application_runs", 1) + 1,
            "master": str(MASTER_PATH.relative_to(ROOT)),
            "source_report": "capacity_audit_report.json",
            "master_sha256_before": existing_ledger.get("metadata", {}).get("master_sha256_before", before_hash),
            "last_application_sha256_before": before_hash,
            "master_sha256_after": after_hash,
            "scope": "Solo dati di capacita; nessuna modifica a search engine, ranking o algoritmi.",
        },
        "summary": {
            "records_changed": sum(item["status"] == "applied" for item in decisions),
            "records_reviewed_no_change": sum(item["status"] == "reviewed_no_change" for item in decisions),
            "unit_occurrences_updated": sum(item.get("occurrences_updated", 0) for item in decisions),
            "field_values_updated": sum(sum(item.get("field_updates", {}).values()) for item in decisions),
            "kw_fields_changed": 0,
            "validation_mismatches": 0,
        },
        "corrections": decisions,
    }
    with LEDGER_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(ledger["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
