#!/usr/bin/env python3
"""Add model-reference typing to Safe Preview V3.3 without changing relations."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import build_safe_preview_relations_v3_3 as v33


ROOT = Path(__file__).resolve().parents[1]
V33_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3.json"
V33_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3_report.json"
PRODUCTION_PATHS = [
    ROOT / "Knowledge" / "catalog_component_relations.json",
    ROOT / "Knowledge" / "catalog_annotations.json",
    ROOT / "Knowledge" / "catalog_table_context.json",
    ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json",
    ROOT / "Knowledge" / "unified_catalog_master.json",
]
OUTPUT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_4.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_4_report.json"

REFERENCE_TYPES = (
    "ACCESSORY_MODEL",
    "COMPATIBLE_PRODUCT_MODEL",
    "UNKNOWN",
)
PROTECTED_FIELDS = (
    "product_context",
    "component",
    "scope_type",
    "applies_to_models",
    "source_channel",
    "sources",
    "evidence",
    "confidence",
    "association_confidence_reason",
    "governor_evidence",
    "governor_confidence",
    "product_domain",
    "product_domain_evidence",
    "candidate_identity",
    "candidate_identity_evidence",
    "attachment_target",
    "attachment_target_evidence",
    "attachment_target_confidence",
    "scope_resolution_reason",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reference_type(record: dict[str, Any]) -> tuple[str, str]:
    accessory = next(iter(record.get("accessories") or []), None)
    if accessory is None:
        return "UNKNOWN", "NO_SEPARATE_ACCESSORY_MODEL_FIELD"
    if (
        record.get("scope_resolution_reason") == "EXPLICIT_COMPATIBLE_MODEL_REFERENCE"
        and record.get("accessory_model_reference")
        and record.get("model_reference_match_method") == "EXACT_NORMALIZED_MODEL_CODE"
    ):
        return "COMPATIBLE_PRODUCT_MODEL", "EXACT_PRODUCT_MODEL_REFERENCES_RESOLVED_IN_V3_3"
    if (
        accessory.get("pt")
        and str(accessory.get("model") or "").strip()
        and accessory.get("candidate_identity") == "CLIMATE_ACCESSORY"
        and record.get("candidate_identity") == "CLIMATE_ACCESSORY"
    ):
        return "ACCESSORY_MODEL", "PT_CODED_CLIMATE_ACCESSORY_ROW_MODEL"
    return "UNKNOWN", "INSUFFICIENT_REFERENCE_IDENTITY_EVIDENCE"


def protected_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changed = [field for field in PROTECTED_FIELDS if before.get(field) != after.get(field)]
    before_accessories = before.get("accessories") or []
    after_accessories = after.get("accessories") or []
    if len(before_accessories) != len(after_accessories):
        changed.append("accessories.length")
    for index, (old, new) in enumerate(zip(before_accessories, after_accessories)):
        for field in (
            "pt", "model", "scope_type", "applies_to_models", "source_channel",
            "evidence", "governor_evidence", "governor_confidence",
            "candidate_identity", "attachment_target", "attachment_target_evidence",
            "attachment_target_confidence", "scope_resolution_reason",
        ):
            if old.get(field) != new.get(field):
                changed.append(f"accessories[{index}].{field}")
    return changed


def concise(record: dict[str, Any]) -> dict[str, Any]:
    item = v33.v32.concise(record)
    item.update({
        "model_reference_type": record.get("model_reference_type"),
        "model_reference_type_reason": record.get("model_reference_type_reason"),
        "scope_resolution_reason": record.get("scope_resolution_reason"),
        "accessory_model_reference": record.get("accessory_model_reference") or [],
    })
    return item


def records_for_model(records: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    needle = model.upper()
    return [
        record for record in records
        if any(str(item.get("model") or "").upper() == needle
               for item in record.get("accessories") or [])
    ]


def records_for_pt(records: list[dict[str, Any]], pt: str) -> list[dict[str, Any]]:
    return [
        record for record in records
        if any(str(item.get("pt") or "") == pt for item in record.get("accessories") or [])
    ]


def regression_checks(
    records: list[dict[str, Any]], v33_report: dict[str, Any], protected_change_count: int
) -> dict[str, dict[str, Any]]:
    haier_139 = records_for_pt(records, "50370139")
    haier_160 = records_for_pt(records, "50370160")
    accessory_codes = (
        "BYFQ60CS", "BYFQ60CW", "BYCQ140E", "BYCQ140EP", "BYCQ140EPB",
        "GLG40", "GLG40S", "BRP069B45", "BRC1H52W", "KITWIFI", "WIFIKEY",
    )
    typed_accessories = {
        code: records_for_model(records, code) for code in accessory_codes
    }
    accessory_as_compatible: list[dict[str, Any]] = []
    accessory_in_applies: list[dict[str, Any]] = []
    for code, matching in typed_accessories.items():
        signature = v33.model_signature(code)
        for record in matching:
            if record.get("model_reference_type") != "ACCESSORY_MODEL":
                accessory_as_compatible.append(concise(record))
            if signature in {v33.model_signature(model) for model in record.get("applies_to_models") or []}:
                accessory_in_applies.append(concise(record))
    compatible = [
        record for record in records
        if record.get("model_reference_type") == "COMPATIBLE_PRODUCT_MODEL"
    ]
    compatible_without_exact_product_match = [
        concise(record) for record in compatible
        if (
            record.get("model_reference_match_method") != "EXACT_NORMALIZED_MODEL_CODE"
            or not record.get("applies_to_models")
            or not all(
                v33.model_signature(model) in {
                    v33.model_signature(reference)
                    for reference in record.get("accessory_model_reference") or []
                }
                for model in record.get("applies_to_models") or []
            )
        )
    ]
    prior_failures = [
        name for name, check in (v33_report.get("regression_results") or {}).items()
        if not check.get("PASS")
    ]
    checks: dict[str, dict[str, Any]] = {
        "01_haier_50370139_compatible_product_models": {
            "actual": [concise(record) for record in haier_139],
        },
        "02_haier_50370160_compatible_product_models": {
            "actual": [concise(record) for record in haier_160],
        },
        "03_daikin_grid_codes_are_accessory_models": {
            "models": {code: [concise(record) for record in typed_accessories[code]]
                       for code in ("BYFQ60CS", "BYFQ60CW", "BYCQ140E", "BYCQ140EP", "BYCQ140EPB")},
        },
        "04_aermec_grid_codes_are_accessory_models": {
            "models": {code: [concise(record) for record in typed_accessories[code]]
                       for code in ("GLG40", "GLG40S")},
        },
        "05_no_accessory_code_used_as_compatible_product_model": {
            "type_violations": accessory_as_compatible,
            "applies_to_models_violations": accessory_in_applies,
        },
        "06_compatible_product_models_require_exact_match": {
            "compatible_record_count": len(compatible),
            "violations": compatible_without_exact_product_match,
        },
        "07_v3_3_regressions_preserved": {"prior_failures": prior_failures},
        "08_no_protected_relation_field_changed": {
            "protected_change_count": protected_change_count,
        },
    }
    sig_139 = {
        v33.model_signature(model)
        for record in haier_139 for model in record.get("applies_to_models") or []
    }
    sig_160 = {
        v33.model_signature(model)
        for record in haier_160 for model in record.get("applies_to_models") or []
    }
    checks["01_haier_50370139_compatible_product_models"]["PASS"] = (
        len(haier_139) == 1
        and sig_139 == {"AB25S2SA1FA", "AB35S2SA1FA"}
        and all(record.get("model_reference_type") == "COMPATIBLE_PRODUCT_MODEL" for record in haier_139)
    )
    checks["02_haier_50370160_compatible_product_models"]["PASS"] = (
        len(haier_160) == 2
        and sig_160 == {"AB50S2SA1FA", "AB71S2SA1FA"}
        and all(record.get("model_reference_type") == "COMPATIBLE_PRODUCT_MODEL" for record in haier_160)
    )
    checks["03_daikin_grid_codes_are_accessory_models"]["PASS"] = all(
        typed_accessories[code]
        and all(record.get("model_reference_type") == "ACCESSORY_MODEL"
                for record in typed_accessories[code])
        for code in ("BYFQ60CS", "BYFQ60CW", "BYCQ140E", "BYCQ140EP", "BYCQ140EPB")
    )
    checks["04_aermec_grid_codes_are_accessory_models"]["PASS"] = all(
        typed_accessories[code]
        and all(record.get("model_reference_type") == "ACCESSORY_MODEL"
                for record in typed_accessories[code])
        for code in ("GLG40", "GLG40S")
    )
    checks["05_no_accessory_code_used_as_compatible_product_model"]["PASS"] = (
        not accessory_as_compatible and not accessory_in_applies
    )
    checks["06_compatible_product_models_require_exact_match"]["PASS"] = (
        bool(compatible) and not compatible_without_exact_product_match
    )
    checks["07_v3_3_regressions_preserved"]["PASS"] = not prior_failures
    checks["08_no_protected_relation_field_changed"]["PASS"] = protected_change_count == 0
    return checks


def main() -> None:
    started = time.time()
    inputs = [V33_PATH, V33_REPORT_PATH, *PRODUCTION_PATHS]
    before_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    source: list[dict[str, Any]] = load_json(V33_PATH)
    v33_report = load_json(V33_REPORT_PATH)
    final: list[dict[str, Any]] = []
    protected_violations: list[dict[str, Any]] = []

    for original in source:
        record = copy.deepcopy(original)
        value, reason = reference_type(record)
        record["model_reference_type"] = value
        record["model_reference_type_reason"] = reason
        for accessory in record.get("accessories") or []:
            accessory["model_reference_type"] = value
            accessory["model_reference_type_reason"] = reason
        changed = protected_changes(original, record)
        if changed:
            protected_violations.append({"record": concise(record), "fields": changed})
        final.append(record)

    distribution = Counter(record.get("model_reference_type") for record in final)
    accessory_examples = [
        concise(record) for record in final
        if record.get("model_reference_type") == "ACCESSORY_MODEL"
    ]
    compatible_examples = [
        concise(record) for record in final
        if record.get("model_reference_type") == "COMPATIBLE_PRODUCT_MODEL"
    ]
    checks = regression_checks(final, v33_report, len(protected_violations))
    converted = sum(
        record.get("model_reference_type") == "COMPATIBLE_PRODUCT_MODEL"
        and record.get("scope_type") == "MODEL_SCOPED"
        for record in final
    )
    readiness = {
        "v3_3_was_production_ready": bool(v33_report.get("production_ready")),
        "record_count_unchanged": len(final) == len(source),
        "zero_protected_relation_changes": not protected_violations,
        "all_v3_4_regressions_pass": all(check.get("PASS") for check in checks.values()),
    }
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "SAFE_PREVIEW_V3_4_MODEL_REFERENCE_TYPE_FIX",
        "incremental_from": "catalog_component_relations_safe_preview_v3_3.json",
        "input_sha256": before_hashes,
        "v3_3_total_records": len(source),
        "v3_4_total_records": len(final),
        "model_reference_type_distribution": {
            value: distribution.get(value, 0) for value in REFERENCE_TYPES
        },
        "converted_to_model_scoped_count": converted,
        "converted_to_model_scoped_semantics": (
            "Relations already narrowed by V3.3 exact compatible-product references; "
            "V3.4 adds type metadata and does not change scope."
        ),
        "scope_changes_applied_by_v3_4": 0,
        "accessory_model_examples": {
            "requested_limit": 20,
            "available_count": len(accessory_examples),
            "returned_count": min(20, len(accessory_examples)),
            "records": accessory_examples[:20],
        },
        "compatible_product_model_examples": {
            "requested_limit": 20,
            "available_count": len(compatible_examples),
            "returned_count": min(20, len(compatible_examples)),
            "records": compatible_examples[:20],
            "note": "Only three distinct retained relations contain explicit compatible-product model lists; no examples are duplicated or fabricated.",
        },
        "protected_relation_change_violations": protected_violations,
        "regression_results": checks,
        "production_ready_conditions": readiness,
        "production_ready": all(readiness.values()),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    after_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    if after_hashes != before_hashes:
        raise RuntimeError("A V3.3 input or production file changed during V3.4 generation")
    if not report["production_ready"]:
        failed = [name for name, value in readiness.items() if not value]
        failed_checks = [name for name, value in checks.items() if not value.get("PASS")]
        raise RuntimeError(f"V3.4 gates failed: conditions={failed}, regressions={failed_checks}")
    print(json.dumps({
        "v3_3_total_records": len(source),
        "v3_4_total_records": len(final),
        "model_reference_type_distribution": report["model_reference_type_distribution"],
        "converted_to_model_scoped_count": converted,
        "scope_changes_applied_by_v3_4": 0,
        "production_ready": report["production_ready"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
