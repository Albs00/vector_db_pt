from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "Knowledge" / "clima_multisplit_master.json"
AFTER = ROOT / "reports" / "clima_ab" / "after.jsonl"


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def stable_key(row):
    return hashlib.sha256(str(row["row_id"]).encode("utf-8")).hexdigest()


master = json.loads(MASTER.read_text(encoding="utf-8"))
rows = [
    row for row in read_jsonl(AFTER)
    if row.get("scope") == "MULTISPLIT"
    and row.get("configuration_status") == "CONFIGURAZIONE_NON_CONFERMATA"
]
groups = collections.defaultdict(list)
for row in rows:
    groups[row.get("detected_brand") or "UNKNOWN"].append(row)
for values in groups.values():
    values.sort(key=stable_key)

# Maximum brand coverage: one deterministic record for every represented brand,
# plus a second record for the largest group to reach 20.
brands = sorted(groups, key=lambda brand: (-len(groups[brand]), brand))
sample = [groups[brand][0] for brand in brands]
cursor = 1
while len(sample) < 20:
    for brand in brands:
        if cursor < len(groups[brand]):
            sample.append(groups[brand][cursor])
            if len(sample) == 20:
                break
    cursor += 1
sample = sample[:20]

products = {(str(item.get("pt")), item.get("role")): item for item in master.get("products") or []}
index = master.get("index_by_configuration_key") or {}
combinations = master.get("combination_master") or []
systems = master.get("systems") or []
results = []
for row in sample:
    main = row.get("main_unit_bom") or []
    ui_pts = [str(item.get("pt")) for item in main if item.get("role") == "UI" and item.get("pt")]
    ue_pts = [str(item.get("pt")) for item in main if item.get("role") == "UE" and item.get("pt")]
    key = f"MULTISPLIT|{ue_pts[0]}|{','.join(sorted(ui_pts))}" if len(ue_pts) == 1 else None
    position = index.get(key) if key in index else None
    combination = combinations[position] if isinstance(position, int) and 0 <= position < len(combinations) else None
    system = systems[combination["system_id"]] if combination and isinstance(combination.get("system_id"), int) and combination["system_id"] < len(systems) else None
    references_valid = bool(combination) and all((pt, "UI") in products for pt in ui_pts) and (ue_pts[0], "UE") in products
    results.append({
        "row_id": row["row_id"],
        "brand": row.get("detected_brand"),
        "title": row["title"],
        "previous_after_mpn": row.get("main_unit_mpn"),
        "previous_status": row.get("configuration_status"),
        "configuration_key": key,
        "present_in_updated_index": key in index if key else False,
        "combination_status": combination.get("status") if combination else None,
        "newly_confirmable_by_master": bool(combination and combination.get("status") == "CONFIRMED"),
        "ui_count_expected": len(ui_pts),
        "ui_count_master": combination.get("ui_count") if combination else None,
        "duplicates_preserved": bool(combination and collections.Counter(combination.get("ui_pts") or []) == collections.Counter(ui_pts)),
        "references_and_roles_valid": references_valid,
        "system_id": combination.get("system_id") if combination else None,
        "system_brand": system.get("brand") if system else None,
        "system_configuration_status": system.get("configuration_status") if system else None,
        "source": combination.get("source") if combination else None,
    })

report = {
    "selection": "Deterministic maximum-brand-coverage sample from prior AFTER MULTISPLIT CONFIGURAZIONE_NON_CONFERMATA rows",
    "population": len(rows),
    "sample_size": len(results),
    "brands_in_population": len(groups),
    "brands_in_sample": len({row["brand"] for row in results}),
    "master_sha256": hashlib.sha256(MASTER.read_bytes()).hexdigest(),
    "dataset_version": master.get("dataset_version"),
    "combination_master_count": len(combinations),
    "index_count": len(index),
    "confirmed_in_sample": sum(row["newly_confirmable_by_master"] for row in results),
    "missing_in_sample": sum(not row["present_in_updated_index"] for row in results),
    "invalid_reference_or_role_in_sample": sum(not row["references_and_roles_valid"] for row in results if row["present_in_updated_index"]),
    "duplicate_multisets_preserved_in_sample": sum(row["duplicates_preserved"] for row in results),
    "results": results,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
