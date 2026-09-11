from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "clima_ab"
WORK_DIR = ROOT / ".codex_tmp" / "benchmark_after"
FROZEN = REPORT_DIR / "benchmark_input_frozen.jsonl"
BEFORE = REPORT_DIR / "before.jsonl"
BEFORE_SUMMARY = REPORT_DIR / "before_summary.json"
BEFORE_MANIFEST = REPORT_DIR / "before_manifest.json"
AFTER = REPORT_DIR / "after.jsonl"
AFTER_SUMMARY = REPORT_DIR / "after_summary.json"
AFTER_MANIFEST = REPORT_DIR / "after_manifest.json"
DIFF = REPORT_DIR / "before_after_diff.jsonl"
DIFF_SUMMARY = REPORT_DIR / "before_after_summary.json"
RUN_META = WORK_DIR / "run_meta.json"

EXPECTED_FROZEN_SHA256 = "5dc37e253b7382df289ea1013f656ea2c5cac359fea311414a4925f0679eacda"
EXPECTED_BEFORE_SHA256 = "2f93bc4f333059a3a1100c0c943e1d41934eb6d911cd35fa00a533cbab4cf10b"
EXPECTED_ROWS = 4453
TRUE_VALUES = {"1", "true", "yes", "on"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def normalize_mpn(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").upper())


def assert_inputs(check_engine: bool = True) -> dict[str, Any]:
    frozen_hash = sha256_file(FROZEN)
    before_hash = sha256_file(BEFORE)
    if frozen_hash != EXPECTED_FROZEN_SHA256:
        raise AssertionError(f"Frozen input SHA256 mismatch: {frozen_hash}")
    if before_hash != EXPECTED_BEFORE_SHA256:
        raise AssertionError(f"BEFORE SHA256 mismatch: {before_hash}")

    frozen_all = read_jsonl(FROZEN)
    frozen = [row for row in frozen_all if row.get("benchmark_scope") == "CLIMA"]
    before = read_jsonl(BEFORE)
    frozen_ids = [row.get("row_id") for row in frozen]
    before_ids = [row.get("row_id") for row in before]
    if len(frozen) != EXPECTED_ROWS or len(before) != EXPECTED_ROWS:
        raise AssertionError(f"Unexpected row counts: frozen={len(frozen)} before={len(before)}")
    if len(set(frozen_ids)) != EXPECTED_ROWS or len(set(before_ids)) != EXPECTED_ROWS:
        raise AssertionError("row_id values are not unique")
    if frozen_ids != before_ids:
        raise AssertionError("Frozen and BEFORE row_id sequences differ")

    compare_fields = ("title", "current_mpn", "reference", "brand_original")
    mismatches = []
    for frozen_row, before_row in zip(frozen, before):
        for field in compare_fields:
            if frozen_row.get(field) != before_row.get(field):
                mismatches.append({"row_id": frozen_row["row_id"], "field": field})
                break
    if mismatches:
        raise AssertionError(f"Frozen/BEFORE input mismatch: {mismatches[:10]}")
    if any(not isinstance(row.get("original_columns"), dict) for row in frozen):
        raise AssertionError("Frozen original input columns are missing")

    env_value = os.environ.get("CLIMA_MASTER_RUNTIME_ENABLED", "")
    if env_value.strip().lower() not in TRUE_VALUES:
        raise AssertionError("CLIMA_MASTER_RUNTIME_ENABLED is not explicitly true")
    if check_engine:
        sys.path.insert(0, str(ROOT))
        from catalog_search_engine import CatalogSearchEngine
        engine = CatalogSearchEngine()
        if not engine._clima_master_runtime_enabled:
            raise AssertionError("Runtime engine reports master resolver disabled")

    manifest = read_json(BEFORE_MANIFEST)
    if manifest.get("rows") != EXPECTED_ROWS:
        raise AssertionError("BEFORE manifest row count mismatch")
    return {
        "rows_after_expected": len(frozen),
        "unique_row_ids": len(set(frozen_ids)),
        "row_id_sequence_equal": True,
        "titles_equal": True,
        "original_reference_fields_equal": True,
        "original_columns_present": True,
        "clima_master_runtime_enabled": True,
        "frozen_sha256": frozen_hash,
        "before_sha256": before_hash,
    }


def role_of(item: dict[str, Any]) -> str | None:
    role = item.get("role")
    if role:
        return str(role).upper()
    if item.get("is_ui"):
        return "UI"
    if item.get("is_ue"):
        return "UE"
    return "ACCESSORY" if item.get("code") else None


def compact_component(item: dict[str, Any]) -> dict[str, Any]:
    role = role_of(item)
    slot = item.get("slot_id")
    requested_slot = item.get("taglia_btu") or item.get("requested_slot")
    if requested_slot is None and isinstance(slot, str):
        match = re.search(r"slot_ui_(\d+)", slot)
        requested_slot = int(match.group(1)) if match else None
    variant = item.get("variant_full") or item.get("variant") or item.get("candidate_color")
    color = item.get("color_base") or item.get("candidate_color")
    revision = item.get("revision") or item.get("model_revision") or item.get("generation")
    evidence = item.get("relation_evidence") or {}
    relation = evidence.get("relation_type") if isinstance(evidence, dict) else None
    if not relation:
        evidences = item.get("relation_evidences") or []
        relation = evidences[0].get("relation_type") if evidences else None
    return {
        "role": role,
        "requested_slot": requested_slot,
        "pt": str(item.get("code") or item.get("pt") or "") or None,
        "model": item.get("mfg_code") or item.get("model"),
        "family": item.get("family_key") or item.get("catalog_family") or item.get("family"),
        "variant": variant,
        "color": color,
        "revision": revision,
        "tier": item.get("evidence_tier") or item.get("tier"),
        "score": item.get("score"),
        "relation": relation,
        "source": item.get("source"),
    }


def pt_mpn(components: list[dict[str, Any]]) -> str | None:
    pts = [str(item["pt"]) for item in components if item.get("pt")]
    return " + ".join(pts) if pts else None


def master_resolution_type(result: dict[str, Any], legacy_fallback: bool) -> str:
    evidence = result.get("master_evidence") or (result.get("query_analysis") or {}).get("master_evidence") or {}
    reason = evidence.get("reason") if isinstance(evidence, dict) else None
    if reason in {"MASTER_EXACT_IDENTITY", "MASTER_EXACT_PAIR", "MASTER_EXACT_CONFIGURATION"}:
        return reason
    status = result.get("configuration_status")
    if status == "VERIFIED_MASTER_PAIR":
        return "MASTER_EXACT_PAIR"
    if status == "VERIFIED_FULL_COMBINATION":
        return "MASTER_EXACT_CONFIGURATION"
    if status == "NOT_APPLICABLE_EXACT_IDENTITY":
        return "MASTER_EXACT_IDENTITY"
    return "LEGACY_FALLBACK" if legacy_fallback else "MASTER_UNRESOLVED"


def process(engine: Any, record: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    base = {key: record.get(key) for key in (
        "row_id", "sheet", "excel_row", "title", "current_mpn", "reference", "brand_original"
    )}
    try:
        result = engine.search(record["title"], limit=20, include_accessories=True)
        qa = result.get("query_analysis") or {}
        context = qa.get("query_context") or {}
        all_bom = [compact_component(item) for item in (result.get("bom") or [])]
        explicit_main = result.get("main_unit_bom")
        if explicit_main is not None:
            main_unit_bom = [compact_component(item) for item in explicit_main]
        else:
            main_unit_bom = [item for item in all_bom if item.get("role") in {"UI", "UE"}]
        explicit_accessories = result.get("accessory_bom")
        if explicit_accessories is not None:
            accessory_bom = [compact_component(item) for item in explicit_accessories]
        else:
            accessory_bom = [item for item in all_bom if item.get("role") not in {"UI", "UE"}]
        selected_ui = [item for item in main_unit_bom if item.get("role") == "UI"]
        selected_ues = [item for item in main_unit_bom if item.get("role") == "UE"]
        identity = result.get("product_identity_status") or qa.get("product_identity_status")
        if not main_unit_bom:
            main_status = "NO_MAIN_UNIT_SELECTED"
        elif identity:
            main_status = identity
        elif qa.get("exact_token_candidates"):
            main_status = "EXACT"
        else:
            main_status = "DISCOVERY_ONLY"
        legacy_fallback = result.get("match_type") != "clima_master_authoritative"
        resolution_type = master_resolution_type(result, legacy_fallback)
        master_validation = result.get("master_validation") or qa.get("master_validation")
        master_evidence = result.get("master_evidence") or qa.get("master_evidence")
        configuration_status = result.get("configuration_status") or qa.get("configuration_status") or "NOT_APPLICABLE"
        combined = main_unit_bom + accessory_bom
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            **base,
            "benchmark_scope": "CLIMA",
            "scope": result.get("product_scope") or context.get("product_scope") or "GENERAL",
            "detected_brand": result.get("detected_brand"),
            "requested_btu": context.get("requested_btus") or [],
            "requested_type": context.get("explicit_tipologia") or context.get("probable_tipologia"),
            "requested_family": context.get("requested_family_key") or context.get("requested_family"),
            "requested_color": context.get("query_color") or context.get("requested_color"),
            "automatic_mpn": pt_mpn(combined),
            "main_unit_mpn": pt_mpn(main_unit_bom),
            "main_unit_bom": main_unit_bom,
            "accessory_bom": accessory_bom,
            "selected_ui": selected_ui,
            "selected_ue": selected_ues[0] if selected_ues else None,
            "models": [item.get("model") for item in main_unit_bom if item.get("model")],
            "variant_color": [
                item.get("color") or item.get("variant") for item in main_unit_bom
                if item.get("color") or item.get("variant")
            ],
            "main_unit_match_status": main_status,
            "configuration_status": configuration_status,
            "accessory_status": result.get("accessory_status") or qa.get("accessory_status") or "NOT_APPLICABLE",
            "mpn_final_allowed": bool(result.get("mpn_final_allowed")),
            "master_resolution_type": resolution_type,
            "master_unresolved": configuration_status == "CONFIGURAZIONE_NON_CONFERMATA",
            "legacy_fallback_used": legacy_fallback,
            "master_evidence": master_evidence,
            "master_validation": master_validation,
            "source": (result.get("compatibility_evidence") or {}).get("source") or result.get("component_relation_source"),
            "dataset_release": result.get("dataset_release"),
            "runtime_ms": elapsed_ms,
            "error": None,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            **base,
            "benchmark_scope": "CLIMA",
            "scope": None,
            "automatic_mpn": None,
            "main_unit_mpn": None,
            "main_unit_bom": [],
            "accessory_bom": [],
            "selected_ui": [],
            "selected_ue": None,
            "models": [],
            "variant_color": [],
            "main_unit_match_status": "RUNTIME_ERROR",
            "configuration_status": "ERROR",
            "accessory_status": "ERROR",
            "mpn_final_allowed": False,
            "master_resolution_type": "ERROR",
            "master_unresolved": False,
            "legacy_fallback_used": False,
            "master_evidence": None,
            "master_validation": None,
            "source": None,
            "dataset_release": None,
            "runtime_ms": elapsed_ms,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def run_shard(index: int, count: int) -> None:
    if os.environ.get("CLIMA_MASTER_RUNTIME_ENABLED", "").strip().lower() not in TRUE_VALUES:
        raise SystemExit("CLIMA_MASTER_RUNTIME_ENABLED must be explicitly true")
    frozen = [row for row in read_jsonl(FROZEN) if row.get("benchmark_scope") == "CLIMA"]
    if len(frozen) != EXPECTED_ROWS:
        raise SystemExit("Frozen CLIMA row count changed")
    shard = [row for position, row in enumerate(frozen) if position % count == index]
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from catalog_search_engine import CatalogSearchEngine
    engine = CatalogSearchEngine()
    engine._ensure_initialized()
    if not engine._clima_master_runtime_enabled or engine._clima_master_resolver is None:
        raise SystemExit("Production CLIMA master runtime is not active")
    output = WORK_DIR / f"part_{index}.jsonl"
    with output.open("w", encoding="utf-8", newline="\n", buffering=1) as handle:
        for position, record in enumerate(shard, start=1):
            handle.write(json.dumps(process(engine, record), ensure_ascii=False, separators=(",", ":")) + "\n")
            if position % 25 == 0 or position == len(shard):
                print(json.dumps({
                    "shard": index,
                    "completed": position,
                    "total": len(shard),
                    "last_row_id": record["row_id"],
                    "at": now_iso(),
                }), flush=True)


def component_list(record: dict[str, Any], role: str) -> list[dict[str, Any]]:
    if "main_unit_bom" in record:
        source = record.get("main_unit_bom") or []
    else:
        source = record.get("selected_components") or []
    return [item for item in source if str(item.get("role") or "").upper() == role]


def accessories(record: dict[str, Any]) -> list[dict[str, Any]]:
    if "accessory_bom" in record:
        return record.get("accessory_bom") or []
    if "accessory_components" in record:
        return record.get("accessory_components") or []
    return [
        item for item in (record.get("selected_components") or [])
        if str(item.get("role") or "").upper() not in {"UI", "UE"}
    ]


def pts(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("pt")) for item in items if item.get("pt")]


def values(items: list[dict[str, Any]], *keys: str) -> list[str]:
    output = []
    for item in items:
        value = next((item.get(key) for key in keys if item.get(key) not in (None, "")), None)
        if value is not None:
            output.append(normalize_text(value))
    return sorted(output)


def named_ground_truth(title: str) -> tuple[str, list[str]] | None:
    text = normalize_text(title).replace("BIANCO", "WHITE").replace("NERO", "BLACK")
    checks = [
        ("TOSHIBA_HAORI_WHITE_9000", r"TOSHIBA.*HAORI.*WHITE.*9000", ["50383573", "50213924"]),
        ("PANASONIC_STANDARD_21000", r"PANASONIC.*PACI.*STANDARD.*CASSETTA.*21000", ["50117260", "50003952"]),
        ("MITSUBISHI_WHITE_12_12_18", r"MITSUBISHI.*WHITE.*12\D+12\D+18", ["99788605", "99788605", "99788636", "50196142"]),
        ("DAIKIN_FFA25A9", r"DAIKIN.*FFA[\s\-]?25A9", ["99718206"]),
        ("HAIER_FLEXIS_WHITE_9000", r"HAIER.*FLEXIS.*WHITE.*9000", ["50026470", "50131273"]),
        ("HAIER_FLEXIS_BLACK_9000", r"HAIER.*FLEXIS.*BLACK.*9000", ["50021635", "50131273"]),
        ("PAROS_WHITE_9000", r"(?:KOSAMI.*)?PAROS.*WHITE.*9000", ["50453016", "50452965"]),
        ("PAROS_BLACK_9000", r"(?:KOSAMI.*)?PAROS.*BLACK.*9000", ["50453054", "50452965"]),
    ]
    for name, pattern, expected in checks:
        if re.search(pattern, text):
            return name, expected
    return None


def main_pts(record: dict[str, Any]) -> list[str]:
    return pts(component_list(record, "UI")) + pts(component_list(record, "UE"))


def canonicalize_after_record(record: dict[str, Any]) -> dict[str, Any]:
    """Use the audit canonical order: every UI instance, then UE, then accessories."""
    ui = component_list(record, "UI")
    ue = component_list(record, "UE")
    accessory = accessories(record)
    record["main_unit_bom"] = ui + ue
    record["selected_ui"] = ui
    record["selected_ue"] = ue[0] if ue else None
    record["main_unit_mpn"] = pt_mpn(ui + ue)
    record["automatic_mpn"] = pt_mpn(ui + ue + accessory)
    return record


def classify_quality(before: dict[str, Any], after: dict[str, Any], unchanged: bool) -> tuple[str, str | None]:
    truth = named_ground_truth(after.get("title") or "")
    if not truth:
        return ("NOT_ASSESSED" if unchanged else "CHANGED_UNVERIFIED"), None
    name, expected = truth
    before_correct = main_pts(before) == expected
    after_correct = main_pts(after) == expected
    if after_correct and not before_correct:
        return "IMPROVED", name
    if before_correct and not after_correct:
        return "REGRESSED", name
    if before_correct and after_correct:
        return "UNCHANGED_CORRECT", name
    if unchanged:
        return "UNCHANGED_WRONG", name
    return "CHANGED_UNVERIFIED", name


def diff_record(before: dict[str, Any], after: dict[str, Any], known_pts: set[str]) -> dict[str, Any]:
    before_ui = component_list(before, "UI")
    after_ui = component_list(after, "UI")
    before_ue = component_list(before, "UE")
    after_ue = component_list(after, "UE")
    before_acc = accessories(before)
    after_acc = accessories(after)
    fields = {
        "ui_pt_changed": pts(before_ui) != pts(after_ui),
        "ue_pt_changed": pts(before_ue) != pts(after_ue),
        "ui_quantity_changed": collections.Counter(pts(before_ui)) != collections.Counter(pts(after_ui)),
        "revision_changed": values(before_ui + before_ue, "revision", "model") != values(after_ui + after_ue, "revision", "model"),
        "color_changed": values(before_ui + before_ue, "color", "variant") != values(after_ui + after_ue, "color", "variant"),
        "family_changed": values(before_ui + before_ue, "family") != values(after_ui + after_ue, "family"),
        "main_unit_mpn_changed": main_pts(before) != main_pts(after),
        "accessory_pt_changed": pts(before_acc) != pts(after_acc),
        "configuration_status_changed": before.get("configuration_status") != after.get("configuration_status"),
        "mpn_final_allowed_changed": bool(before.get("mpn_final_allowed")) != bool(after.get("mpn_final_allowed")),
    }
    changed = any(fields.values())
    quality, ground_truth = classify_quality(before, after, not changed)
    resolution = after.get("master_resolution_type")
    if fields["accessory_pt_changed"]:
        reason = "MASTER_ACCESSORY"
    elif fields["ui_quantity_changed"] and collections.Counter(pts(before_ui)) != collections.Counter(pts(after_ui)):
        reason = "MASTER_QUANTITY_RESOLUTION"
    elif fields["color_changed"]:
        reason = "MASTER_VARIANT_RESOLUTION"
    elif fields["revision_changed"]:
        reason = "MASTER_REVISION_RESOLUTION"
    elif resolution in {"MASTER_EXACT_IDENTITY", "MASTER_EXACT_PAIR", "MASTER_EXACT_CONFIGURATION"}:
        reason = resolution
    elif after.get("legacy_fallback_used"):
        reason = "LEGACY_FALLBACK"
    else:
        reason = "OTHER"

    suspicious = []
    score = 0
    if after.get("error"):
        suspicious.append("AFTER_RUNTIME_ERROR")
        score += 100
    if quality == "REGRESSED":
        suspicious.append("VERIFIED_REGRESSION")
        score += 100
    unknown = [pt for pt in main_pts(after) if pt not in known_pts]
    if unknown:
        suspicious.append("MAIN_PT_NOT_IN_PRODUCTION_MASTER")
        score += 90
    title = normalize_text(after.get("title"))
    after_colors = set(values(after_ui + after_ue, "color", "variant"))
    if ("WHITE" in title or "BIANCO" in title) and any("BLACK" in value or "NERO" in value for value in after_colors):
        suspicious.append("POSSIBLE_CROSS_COLOR")
        score += 90
    if ("BLACK" in title or "NERO" in title) and any("WHITE" in value or "BIANCO" in value for value in after_colors):
        suspicious.append("POSSIBLE_CROSS_COLOR")
        score += 90
    if before.get("mpn_final_allowed") and not after.get("mpn_final_allowed"):
        suspicious.append("MPN_FINAL_BECAME_BLOCKED")
        score += 60
    if str(before.get("configuration_status") or "").startswith("VERIFIED") and not str(after.get("configuration_status") or "").startswith("VERIFIED"):
        suspicious.append("CONFIGURATION_CONFIRMATION_LOST")
        score += 60
    if fields["ui_quantity_changed"]:
        suspicious.append("UI_QUANTITY_CHANGED")
        score += 25
    if fields["color_changed"]:
        suspicious.append("COLOR_CHANGED")
        score += 20
    if fields["revision_changed"]:
        suspicious.append("REVISION_OR_MODEL_CHANGED")
        score += 15
    if fields["main_unit_mpn_changed"]:
        suspicious.append("MAIN_MPN_CHANGED")
        score += 10
    if after.get("legacy_fallback_used"):
        suspicious.append("LEGACY_FALLBACK_USED")
        score += 5

    return {
        "row_id": after.get("row_id") or before.get("row_id"),
        "title": after.get("title") or before.get("title"),
        "diff_classification": "CHANGED" if changed else "UNCHANGED",
        "quality_classification": quality,
        "ground_truth_case": ground_truth,
        "reason": reason if changed else None,
        "before_mpn": before.get("automatic_mpn"),
        "after_mpn": after.get("automatic_mpn"),
        "before_main_unit_mpn": " + ".join(main_pts(before)) or None,
        "after_main_unit_mpn": after.get("main_unit_mpn"),
        "before_components": before.get("selected_components") or [],
        "after_components": after.get("main_unit_bom") or [],
        "before_accessories": before_acc,
        "after_accessories": after_acc,
        "before_configuration_status": before.get("configuration_status"),
        "after_configuration_status": after.get("configuration_status"),
        "before_mpn_final_allowed": bool(before.get("mpn_final_allowed")),
        "after_mpn_final_allowed": bool(after.get("mpn_final_allowed")),
        "master_resolution_type": after.get("master_resolution_type"),
        "legacy_fallback_used": bool(after.get("legacy_fallback_used")),
        "master_evidence": after.get("master_evidence") or after.get("master_validation"),
        "source": after.get("source"),
        "changes": fields,
        "suspicion_score": score,
        "suspicion_reasons": suspicious,
        "unknown_main_pts": unknown,
    }


def performance(records: list[dict[str, Any]], wall_seconds: float | None = None) -> dict[str, Any]:
    runtimes = [float(row.get("runtime_ms") or 0.0) for row in records]
    result = {
        "runtime_cumulative_seconds": round(sum(runtimes) / 1000, 3),
        "runtime_mean_ms": round(statistics.mean(runtimes), 3) if runtimes else 0,
        "runtime_median_ms": round(statistics.median(runtimes), 3) if runtimes else 0,
        "runtime_p95_ms": round(percentile(runtimes, 0.95), 3),
        "runtime_p99_ms": round(percentile(runtimes, 0.99), 3),
    }
    if wall_seconds is not None:
        result["wall_clock_seconds"] = round(wall_seconds, 3)
    return result


def run_regression_probes() -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from catalog_search_engine import CatalogSearchEngine
    engine = CatalogSearchEngine()
    cases = [
        ("TOSHIBA_HAORI", "TOSHIBA HAORI BIANCO 9000", ["50383573", "50213924"]),
        ("PANASONIC_STANDARD_21000", "PANASONIC PACI NX STANDARD CASSETTA 21000", ["50117260", "50003952"]),
        ("MITSUBISHI_WHITE_12_12_18", "MITSUBISHI WHITE 12+12+18", ["99788605", "99788605", "99788636", "50196142"]),
        ("DAIKIN_FFA25A9", "DAIKIN FFA25A9", ["99718206"]),
        ("HAIER_FLEXIS_WHITE", "HAIER FLEXIS WHITE 9000", ["50026470", "50131273"]),
        ("HAIER_FLEXIS_BLACK", "HAIER FLEXIS BLACK 9000", ["50021635", "50131273"]),
        ("PAROS_WHITE", "KOSAMI PAROS WHITE 9000", ["50453016", "50452965"]),
        ("PAROS_BLACK", "KOSAMI PAROS BLACK 9000", ["50453054", "50452965"]),
        ("VENUS_MONO_IDENTITY", "50282814", ["50282814"]),
        ("VENUS_MULTI_IDENTITY", "50282883", ["50282883"]),
    ]
    output = []
    for name, query, expected in cases:
        result = engine.search(query, include_accessories=False)
        actual = [str(item.get("code")) for item in result.get("bom") or [] if role_of(item) in {"UI", "UE"}]
        extra_checks = []
        if name == "MITSUBISHI_WHITE_12_12_18":
            extra_checks.append("99788599" not in actual)
        output.append({
            "name": name,
            "query": query,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected and all(extra_checks or [True]),
            "configuration_status": result.get("configuration_status"),
            "mpn_final_allowed": bool(result.get("mpn_final_allowed")),
        })
    return output


def load_known_pts() -> set[str]:
    paths = [ROOT / "Knowledge" / "clima_monosplit_master.json", ROOT / "Knowledge" / "clima_multisplit_master.json"]
    known = set()
    for path in paths:
        document = read_json(path)
        known.update(str(product.get("pt")) for product in document.get("products") or [] if product.get("pt"))
    return known


def finalize() -> None:
    assertions = assert_inputs(check_engine=True)
    meta = read_json(RUN_META)
    before = read_jsonl(BEFORE)
    order = [row["row_id"] for row in before]
    after_by_id: dict[str, dict[str, Any]] = {}
    for index in range(meta["shard_count"]):
        shard_path = WORK_DIR / f"part_{index}.jsonl"
        if not shard_path.exists():
            raise SystemExit(f"Missing AFTER shard: {shard_path}")
        for row in read_jsonl(shard_path):
            if row["row_id"] in after_by_id:
                raise SystemExit(f"Duplicate AFTER row_id: {row['row_id']}")
            after_by_id[row["row_id"]] = row
    if set(after_by_id) != set(order) or len(after_by_id) != EXPECTED_ROWS:
        raise SystemExit("AFTER shard coverage does not match frozen BEFORE sequence")
    after = [canonicalize_after_record(after_by_id[row_id]) for row_id in order]
    if any(row["row_id"] != row_id for row, row_id in zip(after, order)):
        raise SystemExit("AFTER sequence reconstruction failed")
    write_jsonl(AFTER, after)

    artifact_completed_at = datetime.now(timezone.utc)
    completed_at = datetime.fromtimestamp(
        max((WORK_DIR / f"part_{index}.jsonl").stat().st_mtime for index in range(meta["shard_count"])),
        tz=timezone.utc,
    )
    started_at = datetime.fromisoformat(meta["started_at"])
    wall_seconds = (completed_at - started_at).total_seconds()
    resolution_counts = collections.Counter(row.get("master_resolution_type") for row in after)
    main_counts = collections.Counter(row.get("main_unit_match_status") for row in after)
    config_counts = collections.Counter(row.get("configuration_status") for row in after)
    accessory_counts = collections.Counter(row.get("accessory_status") for row in after)
    final_allowed = collections.Counter(str(bool(row.get("mpn_final_allowed"))).lower() for row in after)
    regression = run_regression_probes()
    if not all(item["passed"] for item in regression):
        print("WARNING: one or more named regression probes failed", file=sys.stderr)

    after_summary = {
        "phase": "AFTER",
        "runtime": "NEW_CLIMA_MASTER_RUNTIME",
        "dataset_release": "PT26_CLIMA_PROD_1",
        "rows_processed": len(after),
        "rows_with_automatic_mpn": sum(bool(row.get("automatic_mpn")) for row in after),
        "rows_without_automatic_mpn": sum(not row.get("automatic_mpn") for row in after),
        "rows_failed": sum(bool(row.get("error")) for row in after),
        "main_unit_status_counts": dict(main_counts),
        "configuration_status_counts": dict(config_counts),
        "master_resolution_type_counts": dict(resolution_counts),
        "master_exact_pair_count": resolution_counts.get("MASTER_EXACT_PAIR", 0),
        "master_exact_configuration_count": resolution_counts.get("MASTER_EXACT_CONFIGURATION", 0),
        "master_exact_identity_count": resolution_counts.get("MASTER_EXACT_IDENTITY", 0),
        "master_exact_total_count": sum(
            resolution_counts.get(key, 0) for key in (
                "MASTER_EXACT_PAIR", "MASTER_EXACT_CONFIGURATION", "MASTER_EXACT_IDENTITY"
            )
        ),
        "confirmed_configuration_count": (
            config_counts.get("VERIFIED_MASTER_PAIR", 0)
            + config_counts.get("VERIFIED_FULL_COMBINATION", 0)
        ),
        "master_unresolved_count": sum(bool(row.get("master_unresolved")) for row in after),
        "legacy_fallback_count": sum(bool(row.get("legacy_fallback_used")) for row in after),
        "direct_master_resolver_count": sum(not row.get("legacy_fallback_used") for row in after),
        "legacy_fallback_master_validated_count": sum(
            bool(row.get("legacy_fallback_used"))
            and row.get("master_resolution_type") in {
                "MASTER_EXACT_PAIR", "MASTER_EXACT_CONFIGURATION", "MASTER_EXACT_IDENTITY"
            }
            for row in after
        ),
        "legacy_fallback_unresolved_count": sum(
            bool(row.get("legacy_fallback_used")) and bool(row.get("master_unresolved"))
            for row in after
        ),
        "accessory_status_counts": dict(accessory_counts),
        "accessory_resolved_count": accessory_counts.get("CONFIRMED", 0),
        "accessory_ambiguous_count": accessory_counts.get("ACCESSORY_AMBIGUOUS", 0),
        "accessory_not_confirmed_count": sum(
            value for key, value in accessory_counts.items()
            if key not in {"CONFIRMED", "NONE_SELECTED", "NOT_APPLICABLE", "DISABLED"}
        ),
        "mpn_final_allowed_counts": dict(final_allowed),
        "performance": performance(after, wall_seconds),
        "input_assertions": assertions,
        "named_regressions": regression,
    }
    write_json(AFTER_SUMMARY, after_summary)

    known_pts = load_known_pts()
    diffs = [diff_record(before_row, after_row, known_pts) for before_row, after_row in zip(before, after)]
    write_jsonl(DIFF, diffs)
    diff_counts = collections.Counter(row["diff_classification"] for row in diffs)
    quality_counts = collections.Counter(row["quality_classification"] for row in diffs)
    reason_counts = collections.Counter(row.get("reason") for row in diffs if row.get("reason"))
    changed = [row for row in diffs if row["diff_classification"] == "CHANGED"]
    suspicious = sorted(changed, key=lambda row: (-row["suspicion_score"], row["row_id"]))[:50]

    before_manifest = read_json(BEFORE_MANIFEST)
    before_started = datetime.fromisoformat(before_manifest["started_at"])
    before_completed = datetime.fromisoformat(before_manifest["completed_at"])
    before_perf = performance(before, (before_completed - before_started).total_seconds())
    after_perf = after_summary["performance"]
    performance_comparison = {
        "before": before_perf,
        "after": after_perf,
        "delta": {
            key: round(float(after_perf.get(key, 0)) - float(before_perf.get(key, 0)), 3)
            for key in set(before_perf) | set(after_perf)
        },
    }
    diff_summary = {
        "dataset_release": "PT26_CLIMA_PROD_1",
        "rows_compared": len(diffs),
        "diff_classification_counts": {
            "UNCHANGED": diff_counts.get("UNCHANGED", 0),
            "CHANGED": diff_counts.get("CHANGED", 0),
            "AFTER_ONLY": 0,
            "BEFORE_ONLY": 0,
        },
        "quality_classification_counts": dict(quality_counts),
        "reason_counts": dict(reason_counts),
        "rows_with_mpn_changed": sum(row["changes"]["main_unit_mpn_changed"] or row["changes"]["accessory_pt_changed"] for row in diffs),
        "rows_with_main_unit_mpn_changed": sum(row["changes"]["main_unit_mpn_changed"] for row in diffs),
        "rows_with_ui_quantity_changed": sum(row["changes"]["ui_quantity_changed"] for row in diffs),
        "rows_with_color_changed": sum(row["changes"]["color_changed"] for row in diffs),
        "rows_with_revision_or_model_changed": sum(row["changes"]["revision_changed"] for row in diffs),
        "verified_improvements": quality_counts.get("IMPROVED", 0),
        "verified_regressions": quality_counts.get("REGRESSED", 0),
        "changed_unverified": quality_counts.get("CHANGED_UNVERIFIED", 0),
        "before_indicators": {
            "rows": len(before),
            "automatic_mpn": sum(bool(row.get("automatic_mpn")) for row in before),
            "failed": sum(bool(row.get("error")) for row in before),
            "main_unit_status_counts": dict(collections.Counter(row.get("main_unit_match_status") for row in before)),
            "configuration_status_counts": dict(collections.Counter(row.get("configuration_status") for row in before)),
        },
        "after_indicators": {
            "rows": len(after),
            "automatic_mpn": sum(bool(row.get("automatic_mpn")) for row in after),
            "failed": sum(bool(row.get("error")) for row in after),
            "main_unit_status_counts": dict(main_counts),
            "configuration_status_counts": dict(config_counts),
        },
        "performance_comparison": performance_comparison,
        "named_regressions": regression,
        "top_50_suspicious_changes": [{
            key: row.get(key) for key in (
                "row_id", "title", "suspicion_score", "suspicion_reasons", "quality_classification",
                "reason", "before_main_unit_mpn", "after_main_unit_mpn", "before_configuration_status",
                "after_configuration_status", "legacy_fallback_used", "master_resolution_type"
            )
        } for row in suspicious],
    }
    write_json(DIFF_SUMMARY, diff_summary)

    runtime_files = [
        "catalog_search_engine.py",
        "src/core/clima_master_resolver.py",
        "Knowledge/clima_monosplit_master.json",
        "Knowledge/clima_multisplit_master.json",
        "Knowledge/manual_overrides_clima.json",
        "Knowledge/clima_accessori_master.json",
    ]
    manifest = {
        "phase": "AFTER",
        "captured_runtime": "NEW_CLIMA_MASTER_RUNTIME",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).strip()),
        "benchmark_input_frozen": "reports/clima_ab/benchmark_input_frozen.jsonl",
        "benchmark_input_frozen_sha256": sha256_file(FROZEN),
        "before": "reports/clima_ab/before.jsonl",
        "before_sha256": sha256_file(BEFORE),
        "after": "reports/clima_ab/after.jsonl",
        "after_sha256": sha256_file(AFTER),
        "rows": len(after),
        "input_assertions": assertions,
        "started_at": meta["started_at"],
        "completed_at": completed_at.isoformat(),
        "artifacts_completed_at": artifact_completed_at.isoformat(),
        "clima_master_runtime_enabled": True,
        "dataset_release": "PT26_CLIMA_PROD_1",
        "schema_version": "3.0.0",
        "policy": "FAIL_CLOSED",
        "runtime_files": [
            {"path": relative, "sha256": sha256_file(ROOT / relative)} for relative in runtime_files
        ],
        "source_excel_read": False,
        "notes": "AFTER used only benchmark_input_frozen.jsonl; production runtime and master artifacts were not modified.",
    }
    write_json(AFTER_MANIFEST, manifest)
    print(json.dumps({
        "after_summary": after_summary,
        "diff_summary": {key: value for key, value in diff_summary.items() if key != "top_50_suspicious_changes"},
        "after_sha256": manifest["after_sha256"],
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assert-input", action="store_true")
    parser.add_argument("--shard", type=int)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if args.assert_input:
        assertions = assert_inputs(check_engine=True)
        meta = {
            "started_at": now_iso(),
            "shard_count": args.shard_count,
            "input_assertions": assertions,
        }
        write_json(RUN_META, meta)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    elif args.shard is not None:
        run_shard(args.shard, args.shard_count)
    elif args.finalize:
        finalize()
    else:
        parser.error("choose --assert-input, --shard, or --finalize")


if __name__ == "__main__":
    main()
