#!/usr/bin/env python3
"""Incrementally harden model scope and recover implicit UI roles from V3.2."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import build_safe_preview_relations_v3_2 as v32


ROOT = Path(__file__).resolve().parents[1]
V32_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2.json"
V32_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2_report.json"
V31_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1_report.json"
CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
PRODUCTION_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
OUTPUT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3_report.json"

SCOPE_REASONS = (
    "EXPLICIT_COMPATIBLE_MODEL_REFERENCE",
    "EXPLICIT_ROW_REFERENCE",
    "PRODUCT_TABLE_ROLE_INFERENCE",
    "TABLE_WIDE_NO_MODEL_LIMIT",
    "UNKNOWN_REJECTED",
)
UI_TARGETS = {"UI", "CASSETTE_UI"}
UI_PRODUCT_ROLE_RE = re.compile(
    r"(?:CASSETT|PARETE|SPLIT|CANALIZZ|CONSOLE|COLONNA|PAVIMENTO|SOFFITTO|"
    r"PENSILE|UNIT[AÀ]\s+INTERNA)",
    re.I,
)
ROLE_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", re.I)
MODEL_REFERENCE_SPLIT_RE = re.compile(r"\s+-\s+|\s*[,;]\s*")
TRAILING_QUALIFIER_RE = re.compile(r"\s*\([^)]*\)\s*$")
MODELISH_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9./()_-]{7,}$", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ascii_upper(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper()


def model_signature(value: Any) -> str:
    text = ROLE_PREFIX_RE.sub("", str(value or "").strip())
    text = TRAILING_QUALIFIER_RE.sub("", text)
    return re.sub(r"[^A-Z0-9]", "", ascii_upper(text))


def explicit_compatible_model_references(accessory_model: Any) -> list[str]:
    """Return only an explicit list of product-like codes, never a fuzzy guess."""
    raw = str(accessory_model or "").strip()
    if not raw or not MODEL_REFERENCE_SPLIT_RE.search(raw):
        return []
    parts = [part.strip() for part in MODEL_REFERENCE_SPLIT_RE.split(raw) if part.strip()]
    modelish = [part for part in parts if MODELISH_RE.fullmatch(part)]
    return modelish if len(modelish) >= 2 else []


def exact_reference_matches(references: list[str], product_models: list[str]) -> list[str]:
    signatures = {model_signature(reference) for reference in references}
    return [model for model in product_models if model_signature(model) in signatures]


def accessory_model_signatures(record: dict[str, Any]) -> set[str]:
    return {
        model_signature(item.get("model"))
        for item in record.get("accessories") or []
        if item.get("model")
    }


def recover_ui_models(record: dict[str, Any]) -> list[str]:
    """Recover unprefixed UI identities only from an explicit air-air UI table role."""
    context = record.get("product_context") or {}
    title_and_family = " ".join([
        str(context.get("table_title") or ""),
        str(context.get("family_key") or ""),
    ])
    if not UI_PRODUCT_ROLE_RE.search(title_and_family):
        return []
    accessory_signatures = accessory_model_signatures(record)
    recovered: list[str] = []
    for model in context.get("models") or []:
        value = str(model).strip()
        if not value or v32.UE_PREFIX_RE.search(value):
            continue
        if v32.UI_PREFIX_RE.search(value):
            recovered.append(value)
            continue
        signature = model_signature(value)
        if not signature or signature in accessory_signatures:
            continue
        if v32.ACCESSORY_MODEL_RE.search(value):
            continue
        # The product table/family is explicitly an indoor-unit form factor.
        # This is structural role inference, not code-prefix or fuzzy matching.
        recovered.append(value)
    return sorted(dict.fromkeys(recovered))


def apply_scope_resolution(
    original: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    record = copy.deepcopy(original)
    accessory = next(iter(record.get("accessories") or []), None)
    product_models = [str(model) for model in record.get("product_context", {}).get("models") or []]
    references = explicit_compatible_model_references((accessory or {}).get("model"))
    old_scope = str(record.get("scope_type") or "UNKNOWN")
    old_applies = list(record.get("applies_to_models") or [])

    if references:
        matches = exact_reference_matches(references, product_models)
        if not matches:
            eliminated = v32.concise(record)
            eliminated.update({
                "reason": "EXPLICIT_COMPATIBLE_MODELS_NOT_IN_PRODUCT_TABLE",
                "accessory_model_reference": references,
                "before_scope_type": old_scope,
                "before_applies_to_models": old_applies,
                "match_method": "EXACT_NORMALIZED_MODEL_CODE",
            })
            return None, eliminated
        record["scope_type"] = "MODEL_SCOPED"
        record["applies_to_models"] = sorted(dict.fromkeys(matches))
        record["scope_resolution_reason"] = "EXPLICIT_COMPATIBLE_MODEL_REFERENCE"
        record["accessory_model_reference"] = references
        record["matched_compatible_models"] = record["applies_to_models"]
        record["model_reference_match_method"] = "EXACT_NORMALIZED_MODEL_CODE"
    elif old_scope in {"ROW_SCOPED", "MODEL_SCOPED"} and old_applies:
        record["scope_resolution_reason"] = "EXPLICIT_ROW_REFERENCE"
    elif old_scope == "UNKNOWN" and record.get("attachment_target") in UI_TARGETS:
        recovered = recover_ui_models(record)
        if recovered:
            record["scope_type"] = "TABLE_WIDE"
            record["applies_to_models"] = recovered
            record["scope_resolution_reason"] = "PRODUCT_TABLE_ROLE_INFERENCE"
        else:
            record["scope_type"] = "UNKNOWN"
            record["applies_to_models"] = []
            record["scope_resolution_reason"] = "UNKNOWN_REJECTED"
    elif old_scope == "TABLE_WIDE":
        record["scope_resolution_reason"] = "TABLE_WIDE_NO_MODEL_LIMIT"
    else:
        record["scope_type"] = "UNKNOWN"
        record["applies_to_models"] = []
        record["scope_resolution_reason"] = "UNKNOWN_REJECTED"

    for item in record.get("accessories") or []:
        item["scope_type"] = record.get("scope_type")
        item["applies_to_models"] = list(record.get("applies_to_models") or [])
        item["scope_resolution_reason"] = record["scope_resolution_reason"]
        if references:
            item["accessory_model_reference"] = references
            item["matched_compatible_models"] = list(record.get("applies_to_models") or [])
            item["model_reference_match_method"] = "EXACT_NORMALIZED_MODEL_CODE"
    return record, None


def concise_change(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    item = v32.concise(after)
    item.update({
        "before_scope_type": before.get("scope_type"),
        "before_applies_to_models": before.get("applies_to_models") or [],
        "after_scope_type": after.get("scope_type"),
        "after_applies_to_models": after.get("applies_to_models") or [],
        "scope_resolution_reason": after.get("scope_resolution_reason"),
        "accessory_model_reference": after.get("accessory_model_reference") or [],
    })
    return item


def layout_page_text(pages: set[int]) -> dict[int, str]:
    found: dict[int, str] = {}
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as handle:
        for line in handle:
            page = json.loads(line)
            number = int(page.get("page") or 0)
            if number in pages:
                found[number] = str(page.get("text") or "")
    return found


def records_for_pt(records: list[dict[str, Any]], pt: str) -> list[dict[str, Any]]:
    return [
        record for record in records
        if any(str(item.get("pt") or "") == pt for item in record.get("accessories") or [])
    ]


def clean_model(value: str) -> str:
    return ROLE_PREFIX_RE.sub("", value).upper()


def regression_checks(
    records: list[dict[str, Any]], v32_report: dict[str, Any], layout_text: dict[int, str]
) -> dict[str, dict[str, Any]]:
    haier_139 = records_for_pt(records, "50370139")
    haier_160 = records_for_pt(records, "50370160")
    panasonic = records_for_pt(records, "50117277")
    models_139 = sorted({model for row in haier_139 for model in row.get("applies_to_models") or []})
    models_160 = sorted({model for row in haier_160 for model in row.get("applies_to_models") or []})
    clean_139 = {model_signature(model) for model in models_139}
    clean_160 = {model_signature(model) for model in models_160}
    standard = [row for row in panasonic if row.get("product_context", {}).get("family_key") == "PANASONIC_PACI_NX_STANDARD_CASSETTA_60X60"]
    elite = [row for row in panasonic if row.get("product_context", {}).get("family_key") == "PANASONIC_PACI_NX_ELITE_CASSETTA_60X60"]
    generic = [row for row in panasonic if row.get("product_context", {}).get("family_key") == "PANASONIC_CASSETTA_60X60"]
    bad_panasonic = [
        v32.concise(row) for row in panasonic
        if not all(token in ascii_upper(row.get("product_context", {}).get("table_title"))
                   for token in ("CASSETTA", "60X60"))
    ]
    explicit_reference_rows = [row for row in records if row.get("accessory_model_reference")]
    fuzzy_rows = [
        v32.concise(row) for row in explicit_reference_rows
        if row.get("model_reference_match_method") != "EXACT_NORMALIZED_MODEL_CODE"
    ]
    prior_failures = [
        name for name, check in (v32_report.get("regression_results") or {}).items()
        if not check.get("PASS")
    ]
    ui_v, cassette_v, ue_v = v32.violation_counts(records)
    checks: dict[str, dict[str, Any]] = {
        "01_haier_50370139_only_ab25_ab35": {
            "actual_models": models_139,
            "expected_signatures": ["AB25S2SA1FA", "AB35S2SA1FA"],
        },
        "02_haier_50370160_only_ab50_ab71": {
            "actual_models": models_160,
            "expected_signatures": ["AB50S2SA1FA", "AB71S2SA1FA"],
        },
        "03_page_567_haier_row_resolution": {
            "pt_50370139_records": [v32.concise(row) for row in haier_139 if row.get("page") == 567],
            "pt_50370160_records": [v32.concise(row) for row in haier_160 if row.get("page") == 567],
        },
        "04_cz_kpy4_panasonic_cassette_only": {
            "record_count": len(panasonic),
            "bad_contexts": bad_panasonic,
            "standard_models": sorted({m for row in standard for m in row.get("applies_to_models") or []}),
            "elite_models": sorted({m for row in elite for m in row.get("applies_to_models") or []}),
            "generic_models": sorted({m for row in generic for m in row.get("applies_to_models") or []}),
        },
        "05_explicit_model_reference_never_table_wide": {
            "checked_records": len(explicit_reference_rows),
            "violations": [v32.concise(row) for row in explicit_reference_rows if row.get("scope_type") == "TABLE_WIDE"],
        },
        "06_no_similarity_matching_for_model_references": {
            "match_method": "EXACT_NORMALIZED_MODEL_CODE",
            "violations": fuzzy_rows,
        },
        "07_layout_ground_truth_present": {
            "page_563_has_haier_rows": all(token in layout_text.get(563, "") for token in ("50370139", "50370160", "AB25S2SA1FA - AB35S2SA1FA", "AB50S2SA1FA - AB71S2SA1FA")),
            "page_567_has_ab71_and_both_accessory_rows": all(token in layout_text.get(567, "") for token in ("AB71S2SA1FA", "50370139", "50370160")),
            "panasonic_pages_have_explicit_grid_section": all("GRIGLIA PER CASSETTA 60x60" in layout_text.get(page, "") for page in (514, 516, 519)),
        },
        "08_v3_2_regressions_preserved": {"prior_failures": prior_failures},
        "09_no_ui_ue_scope_regression": {
            "ui_target_with_ue": ui_v,
            "cassette_ui_target_with_ue": cassette_v,
            "ue_target_with_ui": ue_v,
        },
    }
    checks["01_haier_50370139_only_ab25_ab35"]["PASS"] = clean_139 == {"AB25S2SA1FA", "AB35S2SA1FA"}
    checks["02_haier_50370160_only_ab50_ab71"]["PASS"] = clean_160 == {"AB50S2SA1FA", "AB71S2SA1FA"}
    checks["03_page_567_haier_row_resolution"]["PASS"] = (
        not checks["03_page_567_haier_row_resolution"]["pt_50370139_records"]
        and len(checks["03_page_567_haier_row_resolution"]["pt_50370160_records"]) == 1
        and {model_signature(model) for model in checks["03_page_567_haier_row_resolution"]["pt_50370160_records"][0]["applies_to_models"]} == {"AB71S2SA1FA"}
    )
    expected_standard = {"S25PY3E", "S36PY3E", "S50PY3E", "S60PY3E"}
    actual_standard = {model_signature(model) for model in checks["04_cz_kpy4_panasonic_cassette_only"]["standard_models"]}
    checks["04_cz_kpy4_panasonic_cassette_only"]["PASS"] = (
        bool(standard) and bool(elite) and bool(generic) and not bad_panasonic
        and expected_standard.issubset(actual_standard)
        and all(row.get("scope_resolution_reason") == "PRODUCT_TABLE_ROLE_INFERENCE" for row in panasonic)
    )
    checks["05_explicit_model_reference_never_table_wide"]["PASS"] = (
        bool(explicit_reference_rows)
        and not checks["05_explicit_model_reference_never_table_wide"]["violations"]
        and all(row.get("scope_type") == "MODEL_SCOPED" for row in explicit_reference_rows)
    )
    checks["06_no_similarity_matching_for_model_references"]["PASS"] = not fuzzy_rows
    checks["07_layout_ground_truth_present"]["PASS"] = all(
        value for key, value in checks["07_layout_ground_truth_present"].items() if key != "PASS"
    )
    checks["08_v3_2_regressions_preserved"]["PASS"] = not prior_failures
    checks["09_no_ui_ue_scope_regression"]["PASS"] = ui_v == cassette_v == ue_v == 0
    return checks


def main() -> None:
    started = time.time()
    inputs = [
        V32_PATH, V32_REPORT_PATH, V31_REPORT_PATH, CONTEXT_PATH,
        ANNOTATIONS_PATH, LAYOUT_PATH, PRODUCTION_PATH,
    ]
    input_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    source: list[dict[str, Any]] = load_json(V32_PATH)
    v32_report = load_json(V32_REPORT_PATH)
    layout_text = layout_page_text({514, 516, 519, 563, 567})
    staged: list[dict[str, Any]] = []
    eliminated: list[dict[str, Any]] = []
    corrected: list[dict[str, Any]] = []
    table_to_model = 0

    for original in source:
        record, rejection = apply_scope_resolution(original)
        if rejection is not None:
            eliminated.append(rejection)
            continue
        assert record is not None
        changed = (
            record.get("scope_type") != original.get("scope_type")
            or record.get("applies_to_models") != original.get("applies_to_models")
        )
        if changed:
            corrected.append(concise_change(original, record))
        if original.get("scope_type") == "TABLE_WIDE" and record.get("scope_type") == "MODEL_SCOPED":
            table_to_model += 1
        staged.append(record)

    final, deduplicated = v32.deduplicate(staged)
    checks = regression_checks(final, v32_report, layout_text)
    before_scopes = Counter(row.get("scope_type") or "UNKNOWN" for row in source)
    after_scopes = Counter(row.get("scope_type") or "UNKNOWN" for row in final)
    reasons = Counter(row.get("scope_resolution_reason") or "UNKNOWN_REJECTED" for row in final)
    corrected_accessories = [item for item in corrected if item.get("pt")]
    unknown = [v32.concise(row) | {"scope_resolution_reason": row.get("scope_resolution_reason")} for row in final if row.get("scope_type") == "UNKNOWN"]
    final_domains = Counter(row.get("product_domain") or "UNKNOWN" for row in final)
    ui_v, cassette_v, ue_v = v32.violation_counts(final)
    readiness = {
        "v3_2_was_production_ready": bool(v32_report.get("production_ready")),
        "only_air_air_climate_domain": set(final_domains) == {"AIR_AIR_CLIMATE"},
        "zero_ui_target_with_ue": ui_v == 0,
        "zero_cassette_ui_target_with_ue": cassette_v == 0,
        "zero_ue_target_with_ui": ue_v == 0,
        "all_v3_3_regressions_pass": all(check.get("PASS") for check in checks.values()),
    }
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "SAFE_PREVIEW_V3_3_MODEL_SCOPED_ACCESSORY_RESOLUTION",
        "incremental_from": "catalog_component_relations_safe_preview_v3_2.json",
        "input_sha256": input_hashes,
        "v3_2_total_records": len(source),
        "v3_3_total_records": len(final),
        "scope_type_distribution_before": dict(sorted(before_scopes.items())),
        "scope_type_distribution_after": dict(sorted(after_scopes.items())),
        "model_scoped_before": before_scopes.get("MODEL_SCOPED", 0),
        "model_scoped_after": after_scopes.get("MODEL_SCOPED", 0),
        "table_wide_converted_to_model_scoped_count": table_to_model,
        "product_table_role_inference_count": reasons.get("PRODUCT_TABLE_ROLE_INFERENCE", 0),
        "scope_resolution_reason_distribution": {
            reason: reasons.get(reason, 0) for reason in SCOPE_REASONS
        },
        "scope_corrected_records_count": len(corrected),
        "scope_corrected_records": corrected,
        "corrected_accessories_count": len(corrected_accessories),
        "corrected_accessories": corrected_accessories,
        "relations_eliminated_for_wrong_propagation_count": len(eliminated),
        "relations_eliminated_for_wrong_propagation": eliminated,
        "deduplicated_after_scope_count": deduplicated,
        "unknown_relations_count": len(unknown),
        "unknown_relations": unknown,
        "regression_results": checks,
        "production_ready_conditions": readiness,
        "production_ready": all(readiness.values()),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    after_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    if after_hashes != input_hashes:
        raise RuntimeError("An input or production file changed during V3.3 generation")
    if not report["production_ready"]:
        failed_conditions = [name for name, value in readiness.items() if not value]
        failed_checks = [name for name, value in checks.items() if not value.get("PASS")]
        raise RuntimeError(
            f"V3.3 gates failed: conditions={failed_conditions}, regressions={failed_checks}"
        )
    print(json.dumps({
        "v3_2_total_records": len(source),
        "v3_3_total_records": len(final),
        "model_scoped_before": before_scopes.get("MODEL_SCOPED", 0),
        "model_scoped_after": after_scopes.get("MODEL_SCOPED", 0),
        "table_wide_converted_to_model_scoped_count": table_to_model,
        "product_table_role_inference_count": reasons.get("PRODUCT_TABLE_ROLE_INFERENCE", 0),
        "eliminated_wrong_propagation": len(eliminated),
        "unknown_relations": len(unknown),
        "production_ready": report["production_ready"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
