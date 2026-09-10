#!/usr/bin/env python3
"""Narrow Safe Preview V3.1 to air-air climate and harden attachment scope."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V31_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1.json"
V31_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1_report.json"
CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
PRODUCTION_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
OUTPUT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2_report.json"

DOMAINS = ("AIR_AIR_CLIMATE", "HYDRONIC_HEAT_PUMP", "NON_CLIMATE", "UNKNOWN")
TARGETS = ("UI", "UE", "CASSETTE_UI", "SYSTEM", "UNKNOWN")

HYDRONIC_RE = re.compile(
    r"\b(?:HYDROBOX|HYDROTANK|ECODAN|HYDROKIT|HYDRO\s*KIT|IDRONIC[OAHE]*|"
    r"ARIA\s*[-/]?\s*ACQUA|ACQUA\s*[-/]?\s*ACQUA|WATER\s+MODULE|TANK|"
    r"BOLLITORE(?:\s+INTEGRATO)?|ACCUMULO|MODUL[IO]\s+(?:ACQUA|IDRONIC[OI]))\b", re.I,
)
CASSETTE_RE = re.compile(r"CASSETT", re.I)
UI_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*I\s*[.]?\s*", re.I)
UE_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*E\s*[.]?\s*", re.I)
UI_TABLE_RE = re.compile(
    r"\b(?:PARETE|SPLIT|CANALIZZ|CASSETT|CONSOLE|COLONNA|PAVIMENTO|SOFFITTO|"
    r"PENSILE|UNIT[AÀ]\s+INTERNA)\b", re.I,
)
UE_TABLE_RE = re.compile(r"\bUNIT[AÀ]\s+ESTERNA\b", re.I)
UI_CODE_RE = re.compile(
    r"^(?:FTX|CTX|ATX|MSZ|QH|AS\d|MCA4U|MCD\d|FCAG|FFA|FNA|FDXM|FBA|"
    r"MLZ|SLZ|SEZ|PEAD|PKA|PCA|PLA|AB\d|LPG\d+C|MPG\d+C)", re.I,
)
ACCESSORY_MODEL_RE = re.compile(
    r"\b(?:OPTIONAL|OPZIONALE|FILO\s+COMANDO|COMANDO|TELECOMANDO|WI-?FI|"
    r"WIFIKEY|KITWIFI|BRC|BRP|BYCQ|BYFQ|GLG\d|T-MBQ|PANNELLO|GRIGLIA|"
    r"RICEVITORE|SENSORE|SONDA|FILTRO|POMPA|VALVOLA|BACINELLA)\b", re.I,
)
PANEL_GRID_RE = re.compile(
    r"\b(?:PANNELLO|GRIGLIA|BYCQ[A-Z0-9/-]*|BYFQ[A-Z0-9/-]*|"
    r"GLG[A-Z0-9/-]*|T-MBQ[A-Z0-9/-]*|MLP-[A-Z0-9/-]*)\b", re.I,
)
WIFI_RE = re.compile(r"\b(?:WI-?FI|WIFIKEY|KITWIFI|BRP069[A-Z0-9-]*|INWFI[A-Z0-9-]*|W-?LAN)\b", re.I)
WIRED_COMMAND_RE = re.compile(
    r"\b(?:COMANDO(?:\s+REMOTO)?\s+A\s+FILO|FILOCOMANDO|FILO\s+COMANDO)\b", re.I,
)
REMOTE_RE = re.compile(
    r"\b(?:TELECOMANDO|COMANDO\s+REMOTO|COMANDO\s+(?:A\s+INFRAROSSI|IR)|"
    r"RICEVITORE(?:\s+IR|\s+INFRAROSSI)?)\b",
    re.I,
)
FILTER_RE = re.compile(r"\bFILTRO\b", re.I)
CONDENSATE_PUMP_RE = re.compile(r"\bPOMPA\b.*\bCONDENSA\b|\bCONDENSA\b.*\bPOMPA\b", re.I)
EXPLICIT_UE_RE = re.compile(r"\b(?:PER|SU|UNIT[AÀ])\s+(?:L['’]\s*)?UNIT[AÀ]?\s*ESTERNA|\bU[.]?E[.]?\b", re.I)
EXPLICIT_UI_RE = re.compile(r"\b(?:PER|SU|UNIT[AÀ])\s+(?:L['’]\s*)?UNIT[AÀ]?\s*INTERNA|\bU[.]?I[.]?\b", re.I)
SYSTEM_TARGET_RE = re.compile(r"\b(?:INTERO\s+SISTEMA|SISTEMA\s+COMPLETO)\b", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper()


def context_index(context: dict[str, dict[str, Any]]) -> tuple[
    dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]
]:
    by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_pt: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    for pt, base in context.items():
        for raw in [base, *(base.get("alternate_table_contexts") or [])]:
            table_id = str(raw.get("table_id") or "")
            if not table_id:
                continue
            item = {
                "pt": str(pt),
                "table_id": table_id,
                "title": str(raw.get("table_title") or raw.get("catalog_family")
                             or base.get("table_title") or ""),
                "family": str(raw.get("family_key") or base.get("family_key") or ""),
                "section": str(raw.get("section_title") or base.get("section_title") or ""),
                "model": str(base.get("model") or ""),
                "mpn": str(base.get("mpn") or ""),
            }
            key = (table_id, item["pt"], item["model"], item["section"])
            if key in seen:
                continue
            seen.add(key)
            by_table[table_id].append(item)
            by_pt[str(pt)].append(item)
    return by_table, by_pt


def product_domain(
    record: dict[str, Any], by_table: dict[str, list[dict[str, str]]]
) -> tuple[str, str, str]:
    context = record.get("product_context") or {}
    entries = by_table.get(str(record.get("table_id") or ""), [])
    metadata_text = " | ".join(
        " ".join([item["title"], item["family"], item["section"], item["model"]])
        for item in entries
    )
    record_text = " ".join([
        str(context.get("table_title") or ""), str(context.get("family_key") or ""),
        " ".join(str(model) for model in context.get("models") or []), metadata_text,
    ])
    match = HYDRONIC_RE.search(norm(record_text))
    if match:
        return "HYDRONIC_HEAT_PUMP", "EXPLICIT_HYDRONIC_PRODUCT_CONTEXT", match.group(0)
    if record.get("product_domain") == "CLIMATE":
        return "AIR_AIR_CLIMATE", "V3_1_CLIMATE_GATE_PLUS_NO_HYDRONIC_EVIDENCE", ""
    if record.get("product_domain") == "NON_CLIMATE":
        return "NON_CLIMATE", "V3_1_NON_CLIMATE", ""
    return "UNKNOWN", "NO_AIR_AIR_EVIDENCE", ""


def candidate_metadata_text(
    record: dict[str, Any], accessory: dict[str, Any] | None,
    by_pt: dict[str, list[dict[str, str]]],
) -> str:
    entries = by_pt.get(str((accessory or {}).get("pt") or ""), [])
    context_text = " | ".join(
        " ".join([item["title"], item["family"], item["model"], item["mpn"]])
        for item in entries
    )
    return " | ".join(filter(None, [
        str(record.get("component", {}).get("type") or ""),
        str(record.get("raw_text") or ""), str(record.get("target_text") or ""),
        str((record.get("accessory_section") or {}).get("table_title") or ""),
        str((accessory or {}).get("model") or ""),
        str((accessory or {}).get("accessory_section_title") or ""), context_text,
    ]))


def attachment_target(
    record: dict[str, Any], accessory: dict[str, Any] | None,
    by_pt: dict[str, list[dict[str, str]]],
) -> tuple[str, str, float, str]:
    text = candidate_metadata_text(record, accessory, by_pt)
    parent_title = str(record.get("product_context", {}).get("table_title") or "")
    component_role = norm(record.get("component", {}).get("type") or "")
    explicit_text = " ".join([
        str(record.get("raw_text") or ""), str(record.get("target_text") or ""),
        str((accessory or {}).get("accessory_section_title") or ""),
    ])
    if SYSTEM_TARGET_RE.search(explicit_text):
        return "SYSTEM", "EXPLICIT_TARGET_TEXT", 1.0, text
    if EXPLICIT_UE_RE.search(explicit_text):
        return "UE", "EXPLICIT_TARGET_TEXT", 1.0, text
    if EXPLICIT_UI_RE.search(explicit_text):
        target = "CASSETTE_UI" if CASSETTE_RE.search(parent_title) else "UI"
        return target, "EXPLICIT_TARGET_TEXT", 1.0, text
    if PANEL_GRID_RE.search(text) and CASSETTE_RE.search(parent_title):
        return "CASSETTE_UI", "CATALOG_COMPONENT_ROLE", 1.0, text
    old_scope = str(record.get("scope_type") or "UNKNOWN")
    old_applies = list(record.get("applies_to_models") or [])
    if old_scope == "ROW_SCOPED" and old_applies:
        roles = {model_role(model, parent_title, set()) for model in old_applies}
        if roles == {"UI"}:
            target = "CASSETTE_UI" if CASSETTE_RE.search(parent_title) else "UI"
            return target, "ROW_ALIGNMENT", 1.0, text
        if roles == {"UE"}:
            return "UE", "ROW_ALIGNMENT", 1.0, text
    if (
        WIFI_RE.search(text) or WIRED_COMMAND_RE.search(text)
        or CONDENSATE_PUMP_RE.search(text) or FILTER_RE.search(text)
    ):
        return "UI", "ACCESSORY_TYPE_DEFAULT", 0.9, text
    if REMOTE_RE.search(text):
        target = "CASSETTE_UI" if CASSETTE_RE.search(parent_title) else "UI"
        return target, "ACCESSORY_TYPE_DEFAULT", 0.9, text
    if component_role.startswith("COMANDO") or component_role == "TELECOMANDO":
        target = "CASSETTE_UI" if CASSETTE_RE.search(parent_title) else "UI"
        return target, "ACCESSORY_TYPE_DEFAULT", 0.9, text
    return "UNKNOWN", "UNKNOWN", 0.5, text


def stripped_model(model: str) -> str:
    return UI_PREFIX_RE.sub("", UE_PREFIX_RE.sub("", str(model or ""))).strip()


def model_role(model: str, table_title: str, accessory_models: set[str]) -> str:
    value = str(model or "").strip()
    if not value or norm(value) in {"OPTIONAL", "OPZIONALE"}:
        return "OTHER"
    if UI_PREFIX_RE.search(value):
        return "UI"
    if UE_PREFIX_RE.search(value):
        return "UE"
    clean = stripped_model(value)
    if norm(clean) in accessory_models or ACCESSORY_MODEL_RE.search(clean):
        return "OTHER"
    if UI_CODE_RE.search(clean):
        return "UI"
    if UE_TABLE_RE.search(table_title):
        return "UE"
    if UI_TABLE_RE.search(table_title):
        return "UI"
    return "UNKNOWN"


def scoped_models(
    record: dict[str, Any], target: str,
) -> tuple[list[str], str, str]:
    context = record.get("product_context") or {}
    models = [str(model) for model in context.get("models") or []]
    accessory_models = {
        norm(str(item.get("model") or "")) for item in record.get("accessories") or []
    }
    roles = {model: model_role(model, str(context.get("table_title") or ""), accessory_models)
             for model in models}
    old_scope = str(record.get("scope_type") or "UNKNOWN")
    old_applies = [str(model) for model in record.get("applies_to_models") or []]
    if target in {"UI", "CASSETTE_UI"}:
        eligible = [model for model in models if roles[model] == "UI"]
    elif target == "UE":
        eligible = [model for model in models if roles[model] == "UE"]
    elif target == "SYSTEM":
        eligible = [model for model in models if roles[model] in {"UI", "UE"}]
    else:
        explicitly_scoped = old_scope in {"ROW_SCOPED", "MODEL_SCOPED"}
        kept = [model for model in old_applies if model in models] if explicitly_scoped else []
        return sorted(dict.fromkeys(kept)), old_scope if kept else "UNKNOWN", "EXPLICIT_OLD_SCOPE" if kept else "NO_SAFE_TARGET"

    if old_scope in {"ROW_SCOPED", "MODEL_SCOPED"}:
        narrowed = [model for model in old_applies if model in eligible]
        if narrowed:
            return sorted(dict.fromkeys(narrowed)), old_scope, "OLD_EXPLICIT_SCOPE_INTERSECT_TARGET_ROLE"
    return sorted(dict.fromkeys(eligible)), "TABLE_WIDE" if eligible else "UNKNOWN", "TABLE_TARGET_ROLE_FILTER"


def has_mixed_ui_ue(record: dict[str, Any]) -> bool:
    values = [str(model) for model in record.get("applies_to_models") or []]
    return any(UI_PREFIX_RE.search(model) for model in values) and any(
        UE_PREFIX_RE.search(model) for model in values
    )


def violation_counts(records: list[dict[str, Any]]) -> tuple[int, int, int]:
    ui = cassette = ue = 0
    for record in records:
        target = record.get("attachment_target")
        values = [str(model) for model in record.get("applies_to_models") or []]
        if target == "UI" and any(UE_PREFIX_RE.search(model) for model in values):
            ui += 1
        if target == "CASSETTE_UI" and any(UE_PREFIX_RE.search(model) for model in values):
            cassette += 1
        if target == "UE" and any(UI_PREFIX_RE.search(model) for model in values):
            ue += 1
    return ui, cassette, ue


def concise(record: dict[str, Any]) -> dict[str, Any]:
    accessory = next(iter(record.get("accessories") or []), {})
    return {
        "page": record.get("page"), "table_id": record.get("table_id"),
        "product_title": record.get("product_context", {}).get("table_title"),
        "family_key": record.get("product_context", {}).get("family_key"),
        "pt": accessory.get("pt"), "accessory_model": accessory.get("model"),
        "component_type": record.get("component", {}).get("type"),
        "attachment_target": record.get("attachment_target"),
        "applies_to_models": record.get("applies_to_models") or [],
        "scope_type": record.get("scope_type"),
    }


def deduplicate(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    removed = 0
    for record in records:
        accessories = record.get("accessories") or []
        if record.get("source_channel") == "RED_EDITORIAL_ANNOTATION" or len(accessories) != 1:
            kept.append(record)
            continue
        accessory = accessories[0]
        key = (
            record.get("table_id"), accessory.get("pt"), record.get("source_channel"),
            record.get("scope_type"), tuple(record.get("applies_to_models") or []),
            record.get("attachment_target"),
        )
        existing = seen.get(key)
        if existing is None:
            seen[key] = record
            kept.append(record)
            continue
        removed += 1
        for occurrence in record.get("source_occurrences") or []:
            if occurrence not in existing.setdefault("source_occurrences", []):
                existing["source_occurrences"].append(occurrence)
        for occurrence in accessory.get("source_occurrences") or []:
            target_occurrences = existing["accessories"][0].setdefault("source_occurrences", [])
            if occurrence not in target_occurrences:
                target_occurrences.append(occurrence)
    return kept, removed


def accessories(records: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    return [
        record for record in records
        if any(model.upper() in str(item.get("model") or "").upper()
               for item in record.get("accessories") or [])
    ]


def target_models(records: list[dict[str, Any]], model: str) -> list[str]:
    return sorted({
        target for record in accessories(records, model)
        for target in record.get("applies_to_models") or []
    })


def regression_checks(records: list[dict[str, Any]], v31_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    hydronic = [concise(record) for record in records if record.get("product_domain") == "HYDRONIC_HEAT_PUMP"]
    families = [str(record.get("product_context", {}).get("family_key") or "") for record in records]

    def no_ue(values: list[str]) -> bool:
        return not any(UE_PREFIX_RE.search(value) for value in values)

    def only_prefix(values: list[str], prefixes: tuple[str, ...]) -> bool:
        cleaned = [stripped_model(value).upper() for value in values]
        return bool(cleaned) and all(any(value.startswith(prefix) for prefix in prefixes) for value in cleaned)

    brp_b45 = target_models(records, "BRP069B45")
    brp_b45_gsi = sorted({
        target for record in accessories(records, "BRP069B45")
        if "GSI LOW" in str(record.get("product_context", {}).get("table_title") or "").upper()
        for target in record.get("applies_to_models") or []
    })
    brp_c81 = target_models(records, "BRP069C81")
    byfq = target_models(records, "BYFQ60CW") + target_models(records, "BYFQ60CS")
    bycq = sorted({model for code in ("BYCQ140E", "BYCQ140EGF", "BYCQ140EP", "BYCQ140EPB")
                   for model in target_models(records, code)})
    t03 = target_models(records, "T-MBQ4-03")
    t04 = target_models(records, "T-MBQ4-04")
    glg = sorted({model for code in ("GLG40", "GLG40S") for model in target_models(records, code)})
    glg_records = [record for code in ("GLG40", "GLG40S") for record in accessories(records, code)]
    haier = sorted({model for pt in ("50370139", "50370160")
                    for record in records for item in record.get("accessories") or []
                    if item.get("pt") == pt for model in record.get("applies_to_models") or []})
    haier_records = [
        record for record in records
        if any(item.get("pt") in {"50370139", "50370160"}
               for item in record.get("accessories") or [])
    ]
    ui_v, cassette_v, ue_v = violation_counts(records)
    total_colour = [
        concise(record) for record in records
        if "TOTAL WHITE" in str(record.get("product_context", {}).get("table_title") or "").upper()
        and any("TOTAL BLACK" in str(item.get("accessory_section_title") or "").upper()
                or "TOTAL SILVER" in str(item.get("accessory_section_title") or "").upper()
                for item in record.get("accessories") or [])
    ]
    old_checks = v31_report.get("hard_regression_checks") or {}
    prior_core = {
        name: bool(value.get("PASS")) for name, value in old_checks.items()
        if any(token in name for token in ("aermec", "daikin", "midea"))
    }
    checks: dict[str, dict[str, Any]] = {
        "01_no_hydronic_families": {
            "actual_records": hydronic,
            "forbidden_family_matches": [family for family in families if HYDRONIC_RE.search(norm(family))],
        },
        "02_brp069b45_ui_only": {
            "applies_to_models_all_contexts": brp_b45,
            "gsi_low_applies_to_models": brp_b45_gsi,
        },
        "03_brp069c81_ui_only": {"applies_to_models": brp_c81},
        "04_byfq60_only_ffa_ui": {"applies_to_models": sorted(set(byfq))},
        "05_bycq140_only_round_flow_ui": {"applies_to_models": bycq},
        "06_t_mbq4_03_only_mca4u": {"applies_to_models": t03},
        "07_t_mbq4_04_only_super_slim_ui": {"applies_to_models": t04},
        "08_glg40_glg40s_only_aermec_cassette_ui": {"applies_to_models": glg},
        "09_haier_panels_only_cassette_ui": {"applies_to_models": haier},
        "10_no_ui_target_with_ue": {"violation_count": ui_v},
        "11_no_cassette_ui_target_with_ue": {"violation_count": cassette_v},
        "12_no_ue_target_with_ui": {"violation_count": ue_v},
        "13_total_white_black_silver_still_absent": {"actual": total_colour},
        "14_v3_1_aermec_daikin_midea_regressions_preserved": {"prior_checks": prior_core},
    }
    checks["01_no_hydronic_families"]["PASS"] = not hydronic and not checks["01_no_hydronic_families"]["forbidden_family_matches"]
    checks["02_brp069b45_ui_only"]["PASS"] = (
        only_prefix(brp_b45_gsi, ("FTXC",))
        and no_ue(brp_b45)
        and not any(stripped_model(model).upper().startswith("RXC") for model in brp_b45)
    )
    checks["03_brp069c81_ui_only"]["PASS"] = bool(brp_c81) and no_ue(brp_c81)
    checks["04_byfq60_only_ffa_ui"]["PASS"] = only_prefix(list(set(byfq)), ("FFA",)) and no_ue(byfq)
    checks["05_bycq140_only_round_flow_ui"]["PASS"] = only_prefix(bycq, ("FCAG",)) and no_ue(bycq)
    checks["06_t_mbq4_03_only_mca4u"]["PASS"] = only_prefix(t03, ("MCA4U",)) and no_ue(t03)
    checks["07_t_mbq4_04_only_super_slim_ui"]["PASS"] = only_prefix(t04, ("MCD",)) and no_ue(t04)
    checks["08_glg40_glg40s_only_aermec_cassette_ui"]["PASS"] = (
        bool(glg_records) and no_ue(glg)
        and all(record.get("attachment_target") == "CASSETTE_UI" for record in glg_records)
        and all("CASSETT" in norm(record.get("product_context", {}).get("table_title"))
                for record in glg_records)
        and all(norm(record.get("product_context", {}).get("family_key")).startswith("AERMEC")
                for record in glg_records)
    )
    checks["09_haier_panels_only_cassette_ui"]["PASS"] = (
        only_prefix(haier, ("AB",)) and no_ue(haier) and bool(haier_records)
        and all(record.get("attachment_target") == "CASSETTE_UI" for record in haier_records)
        and all(norm(record.get("product_context", {}).get("family_key")).startswith("HAIER")
                for record in haier_records)
    )
    checks["10_no_ui_target_with_ue"]["PASS"] = ui_v == 0
    checks["11_no_cassette_ui_target_with_ue"]["PASS"] = cassette_v == 0
    checks["12_no_ue_target_with_ui"]["PASS"] = ue_v == 0
    checks["13_total_white_black_silver_still_absent"]["PASS"] = not total_colour
    checks["14_v3_1_aermec_daikin_midea_regressions_preserved"]["PASS"] = bool(prior_core) and all(prior_core.values())
    return checks


def main() -> None:
    started = time.time()
    inputs = [V31_PATH, V31_REPORT_PATH, CONTEXT_PATH, ANNOTATIONS_PATH, LAYOUT_PATH, PRODUCTION_PATH]
    input_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    source: list[dict[str, Any]] = load_json(V31_PATH)
    v31_report = load_json(V31_REPORT_PATH)
    context = load_json(CONTEXT_PATH)
    by_table, by_pt = context_index(context)
    mixed_before = sum(has_mixed_ui_ue(record) for record in source)
    hydronic_removed: list[dict[str, Any]] = []
    staged: list[dict[str, Any]] = []

    for original in source:
        record = copy.deepcopy(original)
        domain, evidence, match = product_domain(record, by_table)
        record["product_domain"] = domain
        record["product_domain_evidence"] = evidence
        if domain == "HYDRONIC_HEAT_PUMP":
            item = concise(record)
            item["reason"] = "HYDRONIC_OUT_OF_SCOPE"
            item["matched_evidence"] = match
            hydronic_removed.append(item)
            continue
        if domain != "AIR_AIR_CLIMATE":
            continue
        accessory = next(iter(record.get("accessories") or []), None)
        target, target_evidence, confidence, target_text = attachment_target(record, accessory, by_pt)
        applies, scope_type, scope_evidence = scoped_models(record, target)
        record["attachment_target"] = target
        record["attachment_target_evidence"] = target_evidence
        record["attachment_target_confidence"] = confidence
        record["attachment_target_source_text"] = target_text
        record["scope_type"] = scope_type
        record["applies_to_models"] = applies
        record["scope_evidence"] = scope_evidence
        for item in record.get("accessories") or []:
            item["attachment_target"] = target
            item["attachment_target_evidence"] = target_evidence
            item["attachment_target_confidence"] = confidence
            item["scope_type"] = scope_type
            item["applies_to_models"] = applies
            item["scope_evidence"] = scope_evidence
        staged.append(record)

    final, deduplicated = deduplicate(staged)
    mixed_after = sum(has_mixed_ui_ue(record) for record in final)
    ui_v, cassette_v, ue_v = violation_counts(final)
    target_distribution = Counter(record.get("attachment_target") or "UNKNOWN" for record in final)
    checks = regression_checks(final, v31_report)
    final_domains = Counter(record.get("product_domain") or "UNKNOWN" for record in final)
    readiness = {
        "zero_hydronic_heat_pump_records": final_domains.get("HYDRONIC_HEAT_PUMP", 0) == 0,
        "zero_non_climate_records": final_domains.get("NON_CLIMATE", 0) == 0,
        "zero_unknown_domain_records": final_domains.get("UNKNOWN", 0) == 0,
        "zero_ui_target_with_ue": ui_v == 0,
        "zero_cassette_ui_target_with_ue": cassette_v == 0,
        "zero_ue_target_with_ui": ue_v == 0,
        "all_regressions_pass": all(check["PASS"] for check in checks.values()),
    }
    ui_examples = [
        concise(record) for record in final
        if record.get("attachment_target") == "UI" and record.get("accessories")
    ] + [
        concise(record) for record in final
        if record.get("attachment_target") == "UI" and not record.get("accessories")
    ]
    cassette_examples = [
        concise(record) for record in final
        if record.get("attachment_target") == "CASSETTE_UI" and record.get("accessories")
    ] + [
        concise(record) for record in final
        if record.get("attachment_target") == "CASSETTE_UI" and not record.get("accessories")
    ]
    unknown_examples = [concise(record) for record in final if record.get("attachment_target") == "UNKNOWN"]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "SAFE_PREVIEW_V3_2_AIR_AIR_SCOPE_HARDENING",
        "input_sha256": input_hashes,
        "incremental_from": "catalog_component_relations_safe_preview_v3_1.json",
        "preserved_v3_1_production_ready": v31_report.get("production_ready"),
        "v3_1_total_records": len(source),
        "v3_2_total_records": len(final),
        "hydronic_records_removed": len(hydronic_removed),
        "hydronic_removed_records": hydronic_removed,
        "air_air_records_final": final_domains.get("AIR_AIR_CLIMATE", 0),
        "attachment_target_distribution": {
            target: target_distribution.get(target, 0) for target in TARGETS
        },
        "records_with_mixed_ui_ue_before": mixed_before,
        "records_with_mixed_ui_ue_after": mixed_after,
        "ui_target_with_ue_violation_count": ui_v,
        "cassette_ui_target_with_ue_violation_count": cassette_v,
        "ue_target_with_ui_violation_count": ue_v,
        "unknown_target_count": target_distribution.get("UNKNOWN", 0),
        "unknown_target_with_accessory_pt_count": sum(
            record.get("attachment_target") == "UNKNOWN" and bool(record.get("accessories"))
            for record in final
        ),
        "unknown_target_without_accessory_pt_count": sum(
            record.get("attachment_target") == "UNKNOWN" and not record.get("accessories")
            for record in final
        ),
        "deduplicated_after_scope_count": deduplicated,
        "ui_only_scope_examples": ui_examples[:100],
        "cassette_ui_scope_examples": cassette_examples[:100],
        "unknown_target_records": unknown_examples,
        "regression_results": checks,
        "production_ready_conditions": readiness,
        "production_ready": all(readiness.values()),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    after_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    if after_hashes != input_hashes:
        raise RuntimeError("An input or production file changed during V3.2 generation")
    if not report["production_ready"]:
        failed = [name for name, value in readiness.items() if not value]
        failed_checks = [name for name, value in checks.items() if not value["PASS"]]
        raise RuntimeError(f"V3.2 gates failed: conditions={failed}, regressions={failed_checks}")
    print(json.dumps({
        "v3_1_total_records": len(source), "v3_2_total_records": len(final),
        "hydronic_records_removed": len(hydronic_removed),
        "records_with_mixed_ui_ue_before": mixed_before,
        "records_with_mixed_ui_ue_after": mixed_after,
        "attachment_target_distribution": report["attachment_target_distribution"],
        "production_ready": report["production_ready"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
