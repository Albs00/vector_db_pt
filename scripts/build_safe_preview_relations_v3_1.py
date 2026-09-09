#!/usr/bin/env python3
"""Apply the climate-domain and accessory-identity gates to Safe Preview v2.

This is deliberately a narrow post-processing layer: v2 remains responsible
for red annotation safety, layout geometry, strong governors, scope,
provenance, and conservative deduplication. Production datasets are read-only.
"""

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
V2_PATH = ROOT / "catalog_component_relations_safe_preview_v2.json"
V2_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v2_report.json"
CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
CLIMATE_MASTER_PATH = ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json"
UNIFIED_MASTER_PATH = ROOT / "Knowledge" / "unified_catalog_master.json"
PRODUCTION_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
OUTPUT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1_report.json"

DOMAINS = ("CLIMATE", "NON_CLIMATE", "UNKNOWN")
IDENTITIES = (
    "CLIMATE_ACCESSORY", "CLIMATE_UI", "CLIMATE_UE", "CLIMATE_SYSTEM", "UNKNOWN",
)
ACCESSORY_CHANNELS = {
    "EXPLICIT_TABLE_ACCESSORY_ROW", "EXPLICIT_ACCESSORY_SECTION",
}

CLIMATE_SECTION_RE = re.compile(r"\bCONDIZIONATOR", re.I)
UI_EXPLICIT_RE = re.compile(r"(?:\bU\s*[.]?\s*I\s*[.]?\s+|UNIT[AÀ]\s+INTERNA)", re.I)
UE_EXPLICIT_RE = re.compile(r"(?:\bU\s*[.]?\s*E\s*[.]?\s+|UNIT[AÀ]\s+ESTERNA)", re.I)
UI_CODE_RE = re.compile(
    r"^(?:U\s*[.]?\s*I\s*[.]?\s+)?(?:FTX[A-Z0-9-]*|CTX[A-Z0-9-]*|ATX[A-Z0-9-]*|MSZ[A-Z0-9-]*|"
    r"QH[A-Z0-9-]*|AS[A-Z0-9-]*|MCA4U[A-Z0-9()/-]*|FCAG[A-Z0-9-]*|"
    r"FFA[A-Z0-9-]*|FNA[A-Z0-9-]*|FDXM[A-Z0-9-]*|FBA[A-Z0-9-]*|"
    r"MLZ[A-Z0-9-]*|SLZ[A-Z0-9-]*|SEZ[A-Z0-9-]*|PEAD[A-Z0-9-]*|"
    r"PKA[A-Z0-9-]*|PCA[A-Z0-9-]*|PLA[A-Z0-9-]*)\b", re.I,
)
UE_CODE_RE = re.compile(
    r"^(?:U\s*[.]?\s*E\s*[.]?\s+)?(?:RX[A-Z][A-Z0-9-]*|[2-5]?MXM[A-Z0-9-]*|PUMY[A-Z0-9-]*|"
    r"MOX[A-Z0-9()/-]*|AOYG[A-Z0-9-]*)\b", re.I,
)
SYSTEM_RE = re.compile(
    r"\b(?:CLIMATIZZATORE\s+COMPLETO|MONOSPLIT|MULTISPLIT|SISTEMA\s+COMPLETO|"
    r"SISTEMA\s+CLIMA|SET\s+COMPLETO)\b", re.I,
)
ACCESSORY_RE = re.compile(
    r"\b(?:ACCESSORI?|KIT|WI-?FI|WIFIKEY|KITWIFI|COMANDO|TELECOMANDO|"
    r"RICEVITORE|SENSORE|SONDA|GRIGLIA|PANNELLO|FILTRO|POMPA\s+SCARICO|"
    r"CONDENSA|VALVOLA|BACINELLA|CAVO|CONNETTORE|ADATTATORE|PLENUM|"
    r"STAFFA|SUPPORTO|DEFLETTORE|MODULO|SCHEDA|GATEWAY|BRC[A-Z0-9/-]*|"
    r"BYCQ[A-Z0-9/-]*|BYFQ[A-Z0-9/-]*|GLG[A-Z0-9/-]*|T-MBQ[A-Z0-9/-]*)\b", re.I,
)
PANEL_GRID_RE = re.compile(
    r"\b(?:PANNELLO(?:\s+CASSETTA)?|GRIGLIA(?:\s+(?:MANDATA|RIPRESA))?|"
    r"BYCQ[A-Z0-9/-]*|BYFQ[A-Z0-9/-]*|GLG[A-Z0-9/-]*|T-MBQ[A-Z0-9/-]*)\b", re.I,
)
COLOUR_RE = re.compile(
    r"\b(?:TOTAL\s+(?:WHITE|BLACK|SILVER)|BIANC[OA]|NER[OA]|SILVER|ARGENTO|"
    r"ANTRACITE|RAL\s*\d{4})\b", re.I,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).upper()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_candidate_identity_index(
    climate_master: dict[str, Any], unified_master: list[dict[str, Any]],
) -> dict[str, tuple[str, str]]:
    """Build an authoritative PT identity index without changing either master."""
    result: dict[str, tuple[str, str]] = {}
    for pt in climate_master.get("unita_interne") or {}:
        result[str(pt)] = ("CLIMATE_UI", "CLIMATE_MASTER_INTERNAL_UNIT_PT")
    for pt in climate_master.get("unita_esterne") or {}:
        result[str(pt)] = ("CLIMATE_UE", "CLIMATE_MASTER_EXTERNAL_UNIT_PT")

    for product in unified_master:
        pt = str(product.get("code") or "")
        if not pt or pt in result:
            continue
        category_root = norm(product.get("category_root"))
        category_leaf = norm(product.get("category_leaf"))
        if category_root != "CONDIZIONAMENTO":
            continue
        if category_leaf == "ACCESSORI":
            result[pt] = (
                "CLIMATE_ACCESSORY", "UNIFIED_MASTER_CLIMATE_ACCESSORY_CATEGORY",
            )
        else:
            result[pt] = (
                "CLIMATE_SYSTEM", "UNIFIED_MASTER_CLIMATE_PRODUCT_CATEGORY",
            )
    return result


def table_metadata(context: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    for pt, base in context.items():
        for raw in [base, *(base.get("alternate_table_contexts") or [])]:
            table_id = str(raw.get("table_id") or "")
            if not table_id:
                continue
            item = {
                "pt": str(pt),
                "brand": str(raw.get("brand") or base.get("brand") or ""),
                "title": str(raw.get("table_title") or raw.get("catalog_family")
                             or base.get("table_title") or ""),
                "section": str(raw.get("section_title") or base.get("section_title") or ""),
                "model": str(base.get("model") or ""),
                "mpn": str(base.get("mpn") or ""),
            }
            key = (table_id, item["pt"], item["model"], item["section"])
            if key not in seen:
                seen.add(key)
                result[table_id].append(item)
    return result


def product_domain(record: dict[str, Any], meta: dict[str, list[dict[str, str]]]) -> tuple[str, str]:
    entries = meta.get(str(record.get("table_id") or ""), [])
    sections = sorted({item["section"] for item in entries if item["section"]})
    if any(CLIMATE_SECTION_RE.search(norm(section)) for section in sections):
        return "CLIMATE", "EXPLICIT_CONDIZIONATORI_SECTION"
    if sections:
        return "NON_CLIMATE", "EXPLICIT_NON_CLIMATE_SECTION"
    return "UNKNOWN", "NO_EXPLICIT_CATEGORY_EVIDENCE"


def exact_candidate_entries(
    accessory: dict[str, Any], meta: dict[str, list[dict[str, str]]]
) -> list[dict[str, str]]:
    table_id = str(
        accessory.get("accessory_table_id")
        or accessory.get("accessory_section_table_id")
        or accessory.get("table_id") or ""
    )
    pt = str(accessory.get("pt") or "")
    exact = [item for item in meta.get(table_id, []) if item["pt"] == pt]
    global_entries = [
        item for entries in meta.values() for item in entries
        if item["pt"] == pt
    ]
    combined: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in [*exact, *global_entries]:
        key = (item["model"], item["mpn"], item["title"])
        if key not in seen:
            seen.add(key)
            combined.append(item)
    return combined


def candidate_identity(
    record: dict[str, Any], accessory: dict[str, Any],
    meta: dict[str, list[dict[str, str]]],
    identity_index: dict[str, tuple[str, str]],
) -> tuple[str, str, str]:
    entries = exact_candidate_entries(accessory, meta)
    context_text = " | ".join(
        f"{item['model']} {item['mpn']}" for item in entries
    )
    candidate_model_text = str(accessory.get("model") or "").strip()
    heading_text = " ".join(filter(None, [
        str(accessory.get("accessory_section_title") or ""),
        str((record.get("accessory_section") or {}).get("table_title") or ""),
        str(record.get("component", {}).get("type") or ""),
    ]))
    catalog_title_text = " | ".join(item["title"] for item in entries if item["title"])
    identity_text = f"{context_text} | {candidate_model_text} | {heading_text} | {catalog_title_text}".strip()
    indexed_identity = identity_index.get(str(accessory.get("pt") or ""))
    if indexed_identity:
        return indexed_identity[0], indexed_identity[1], identity_text
    # Explicit catalog model roles override misleading headings such as
    # "PANNELLO TOTAL BLACK": those rows are complete FTXA indoor units.
    if UI_EXPLICIT_RE.search(context_text) or UI_CODE_RE.search(context_text):
        return "CLIMATE_UI", "CATALOG_MODEL_IS_INTERNAL_UNIT", identity_text
    if UE_EXPLICIT_RE.search(context_text) or UE_CODE_RE.search(context_text):
        return "CLIMATE_UE", "CATALOG_MODEL_IS_EXTERNAL_UNIT", identity_text
    if SYSTEM_RE.search(context_text):
        return "CLIMATE_SYSTEM", "CATALOG_MODEL_IS_COMPLETE_SYSTEM", identity_text
    if UI_EXPLICIT_RE.search(candidate_model_text) or UI_CODE_RE.search(candidate_model_text):
        return "CLIMATE_UI", "VISIBLE_MODEL_IS_INTERNAL_UNIT", identity_text
    if UE_EXPLICIT_RE.search(candidate_model_text) or UE_CODE_RE.search(candidate_model_text):
        return "CLIMATE_UE", "VISIBLE_MODEL_IS_EXTERNAL_UNIT", identity_text
    if SYSTEM_RE.search(candidate_model_text) or SYSTEM_RE.search(catalog_title_text):
        return "CLIMATE_SYSTEM", "VISIBLE_MODEL_IS_COMPLETE_SYSTEM", identity_text
    if (
        record.get("source_channel") == "EXPLICIT_TABLE_ACCESSORY_ROW"
        and record.get("evidence") == "SAME_TABLE"
        and any(norm(item["model"]).strip() in {"OPTIONAL", "OPZIONALE"} for item in entries)
    ):
        return "CLIMATE_ACCESSORY", "SAME_TABLE_EXPLICIT_OPTIONAL_ROW", identity_text
    if (
        ACCESSORY_RE.search(candidate_model_text)
        or ACCESSORY_RE.search(heading_text)
        or ACCESSORY_RE.search(catalog_title_text)
        or ACCESSORY_RE.search(context_text)
    ):
        return "CLIMATE_ACCESSORY", "EXPLICIT_ACCESSORY_IDENTITY", identity_text
    return "UNKNOWN", "NO_ACCESSORY_IDENTITY_EVIDENCE", identity_text


def is_cassette(record: dict[str, Any]) -> bool:
    context = record.get("product_context") or {}
    parent_text = " ".join([
        str(context.get("table_title") or ""), str(context.get("family_key") or ""),
        " ".join(str(model) for model in context.get("models") or []),
    ])
    return "CASSETT" in norm(parent_text)


def panel_or_grid(record: dict[str, Any], accessory: dict[str, Any] | None = None) -> bool:
    text = " ".join(filter(None, [
        str(record.get("component", {}).get("type") or ""),
        str(record.get("raw_text") or ""),
        str((record.get("accessory_section") or {}).get("table_title") or ""),
        str((accessory or {}).get("model") or ""),
        str((accessory or {}).get("accessory_section_title") or ""),
    ]))
    return bool(PANEL_GRID_RE.search(text))


def colour_variant(record: dict[str, Any], accessory: dict[str, Any], identity_text: str) -> bool:
    text = " ".join([
        identity_text,
        str(record.get("product_context", {}).get("table_title") or ""),
        str((record.get("accessory_section") or {}).get("table_title") or ""),
        str(accessory.get("model") or ""),
    ])
    return bool(COLOUR_RE.search(text))


def concise(record: dict[str, Any], accessory: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "page": record.get("page"),
        "product_table_id": record.get("table_id"),
        "product_title": record.get("product_context", {}).get("table_title"),
        "source_channel": record.get("source_channel"),
    }
    if accessory:
        item.update({
            "pt": accessory.get("pt"), "model": accessory.get("model"),
            "accessory_table_id": accessory.get("accessory_table_id")
                                  or accessory.get("accessory_section_table_id"),
            "accessory_title": accessory.get("accessory_section_title"),
        })
    else:
        item["annotation_ids"] = record.get("source_annotation_ids") or []
        item["raw_text"] = record.get("raw_text") or ""
    return item


def hard_regressions(
    records: list[dict[str, Any]], identity_index: dict[str, tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    def rows(page: int | None = None, title: str | None = None) -> list[dict[str, Any]]:
        return [
            row for row in records
            if (page is None or row.get("page") == page)
            and (title is None or title.upper() in str(
                row.get("product_context", {}).get("table_title") or ""
            ).upper())
        ]

    def pairs(selected: list[dict[str, Any]]) -> set[tuple[str, str]]:
        return {
            (str(accessory.get("pt") or ""), str(accessory.get("model") or ""))
            for row in selected for accessory in row.get("accessories") or []
        }

    total_white_rows = rows(468, "TOTAL WHITE")
    total_white = pairs(total_white_rows)
    total_white_accessories = [
        accessory for row in total_white_rows
        for accessory in row.get("accessories") or []
    ]

    def section_contains(accessory: dict[str, Any], value: str) -> bool:
        section = str(
            accessory.get("accessory_section_title")
            or accessory.get("accessory_title") or ""
        )
        return value in norm(section)

    all_accessories = [
        accessory for row in records for accessory in row.get("accessories") or []
    ]
    spg, sge = pairs(rows(620, "SPG")), pairs(rows(620, "SGE"))
    mpg_c, mpg_cs = pairs(rows(621, "MPG_C 90x90")), pairs(rows(621, "MPG_CS 60x60"))
    round_flow = pairs(rows(474, "ROUND FLOW"))
    compact = pairs(rows(473, "CASSETTA A 4 VIE FFA-A")) | pairs(rows(477, "CASSETTA A 4 VIE FFA-A"))
    super_slim = pairs(rows(546, "SUPER SLIM"))
    midea_compact = pairs(rows(541, "CASSETTA 57x57")) | pairs(rows(546, "CASSETTA 57x57"))

    checks = {
        "01_total_white_no_total_black_panel": {
            "expected": "ABSENT",
            "actual": [
                {"pt": item.get("pt"), "model": item.get("model"),
                 "accessory_section_title": item.get("accessory_section_title")}
                for item in total_white_accessories
                if section_contains(item, "TOTAL BLACK")
            ],
        },
        "02_total_white_no_total_silver_panel": {
            "expected": "ABSENT",
            "actual": [
                {"pt": item.get("pt"), "model": item.get("model"),
                 "accessory_section_title": item.get("accessory_section_title")}
                for item in total_white_accessories
                if section_contains(item, "TOTAL SILVER")
            ],
        },
        "03_no_climate_product_as_accessory": {
            "expected": "NO_UI_UE_SYSTEM_ACCESSORY", "actual": [
                {"pt": item.get("pt"), "model": item.get("model"),
                 "candidate_identity": item.get("candidate_identity")}
                for item in all_accessories
                if item.get("candidate_identity") != "CLIMATE_ACCESSORY"
                or identity_index.get(str(item.get("pt") or ""), ("", ""))[0]
                   in {"CLIMATE_UI", "CLIMATE_UE", "CLIMATE_SYSTEM"}
                or UI_CODE_RE.search(str(item.get("model") or ""))
            ],
        },
        "04_aermec_spg_kitwifi": {
            "expected": ["50253210", "KITWIFI"], "actual": sorted(spg),
        },
        "05_aermec_sge_wifikey": {
            "expected": ["50021123", "WIFIKEY"], "actual": sorted(sge),
        },
        "06_aermec_mpg_c_separation": {
            "expected_present": "99794507", "expected_absent": "99794583",
            "actual": sorted(mpg_c),
        },
        "07_aermec_mpg_cs_separation": {
            "expected_present": "99794583", "expected_absent": "99794507",
            "actual": sorted(mpg_cs),
        },
        "08_daikin_grid_dimension_separation": {
            "round_flow": sorted(pair for pair in round_flow if pair[1].upper().startswith("BYCQ140")),
            "compact": sorted(pair for pair in compact if pair[1].upper().startswith("BYFQ60")),
            "cross_round": sorted(pair for pair in round_flow if pair[1].upper().startswith("BYFQ60")),
            "cross_compact": sorted(pair for pair in compact if pair[1].upper().startswith("BYCQ140")),
        },
        "09_midea_grid_dimension_separation": {
            "super_slim": sorted(pair for pair in super_slim if pair[1].upper().startswith("T-MBQ4-04")),
            "compact": sorted(pair for pair in midea_compact if pair[1].upper().startswith("T-MBQ4-03")),
            "cross_super_slim": sorted(pair for pair in super_slim if pair[1].upper().startswith("T-MBQ4-03")),
            "cross_compact": sorted(pair for pair in midea_compact if pair[1].upper().startswith("T-MBQ4-04")),
        },
        "10_no_non_climate_relation": {
            "expected": "ALL_CLIMATE", "actual_non_climate": [
                concise(row) for row in records if row.get("product_domain") != "CLIMATE"
            ],
        },
    }
    checks["01_total_white_no_total_black_panel"]["PASS"] = not checks["01_total_white_no_total_black_panel"]["actual"]
    checks["02_total_white_no_total_silver_panel"]["PASS"] = not checks["02_total_white_no_total_silver_panel"]["actual"]
    checks["03_no_climate_product_as_accessory"]["PASS"] = not checks["03_no_climate_product_as_accessory"]["actual"]
    checks["04_aermec_spg_kitwifi"]["PASS"] = ("50253210", "KITWIFI") in spg
    checks["05_aermec_sge_wifikey"]["PASS"] = ("50021123", "WIFIKEY") in sge
    checks["06_aermec_mpg_c_separation"]["PASS"] = (
        any(pt == "99794507" for pt, _ in mpg_c) and not any(pt == "99794583" for pt, _ in mpg_c)
    )
    checks["07_aermec_mpg_cs_separation"]["PASS"] = (
        any(pt == "99794583" for pt, _ in mpg_cs) and not any(pt == "99794507" for pt, _ in mpg_cs)
    )
    checks["08_daikin_grid_dimension_separation"]["PASS"] = (
        bool(checks["08_daikin_grid_dimension_separation"]["round_flow"])
        and bool(checks["08_daikin_grid_dimension_separation"]["compact"])
        and not checks["08_daikin_grid_dimension_separation"]["cross_round"]
        and not checks["08_daikin_grid_dimension_separation"]["cross_compact"]
    )
    checks["09_midea_grid_dimension_separation"]["PASS"] = (
        bool(checks["09_midea_grid_dimension_separation"]["super_slim"])
        and bool(checks["09_midea_grid_dimension_separation"]["compact"])
        and not checks["09_midea_grid_dimension_separation"]["cross_super_slim"]
        and not checks["09_midea_grid_dimension_separation"]["cross_compact"]
    )
    checks["10_no_non_climate_relation"]["PASS"] = not checks["10_no_non_climate_relation"]["actual_non_climate"]
    return checks


def main() -> None:
    started = time.time()
    inputs = [
        V2_PATH, V2_REPORT_PATH, CONTEXT_PATH, ANNOTATIONS_PATH, LAYOUT_PATH,
        CLIMATE_MASTER_PATH, UNIFIED_MASTER_PATH, PRODUCTION_PATH,
    ]
    before_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    source: list[dict[str, Any]] = load_json(V2_PATH)
    v2_report = load_json(V2_REPORT_PATH)
    context: dict[str, dict[str, Any]] = load_json(CONTEXT_PATH)
    climate_master: dict[str, Any] = load_json(CLIMATE_MASTER_PATH)
    unified_master: list[dict[str, Any]] = load_json(UNIFIED_MASTER_PATH)
    meta = table_metadata(context)
    identity_index = build_candidate_identity_index(climate_master, unified_master)

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    removed_edge_examples: list[dict[str, Any]] = []
    kept_edge_examples: list[dict[str, Any]] = []
    identity_distribution: Counter[str] = Counter()
    domain_distribution: Counter[str] = Counter()
    removed_ui = removed_ue = removed_system = 0
    removed_panel = removed_colour = 0

    for original in source:
        record = copy.deepcopy(original)
        domain, domain_reason = product_domain(record, meta)
        domain_distribution[domain] += 1
        record["product_domain"] = domain
        record["product_domain_evidence"] = domain_reason
        if domain != "CLIMATE":
            rejection = {
                **concise(record), "product_domain": domain,
                "reason": "NON_CLIMATE_SCOPE", "detail": domain_reason,
            }
            rejected.append(rejection)
            for accessory in record.get("accessories") or []:
                removed_edge_examples.append({
                    **concise(record, accessory), "product_domain": domain,
                    "candidate_identity": "NOT_EVALUATED_OUTSIDE_CLIMATE",
                    "reason": "NON_CLIMATE_SCOPE",
                })
            continue

        accessories = record.get("accessories") or []
        if not accessories:
            identity_distribution["UNKNOWN"] += 1
            record["candidate_identity"] = "UNKNOWN"
            record["candidate_identity_evidence"] = "NO_SEPARATE_ACCESSORY_PT"
            if panel_or_grid(record) and not is_cassette(record):
                removed_panel += 1
                rejected.append({
                    **concise(record), "product_domain": domain,
                    "candidate_identity": "UNKNOWN", "reason": "PANEL_GRID_NOT_APPLICABLE",
                })
                continue
            kept.append(record)
            continue

        kept_accessories: list[dict[str, Any]] = []
        for accessory in accessories:
            identity, identity_reason, identity_text = candidate_identity(
                record, accessory, meta, identity_index,
            )
            identity_distribution[identity] += 1
            candidate = copy.deepcopy(accessory)
            candidate["candidate_identity"] = identity
            candidate["candidate_identity_evidence"] = identity_reason
            colour = colour_variant(record, candidate, identity_text)
            invalid_panel = panel_or_grid(record, candidate) and not is_cassette(record)
            if colour and identity in {"CLIMATE_UI", "CLIMATE_UE", "CLIMATE_SYSTEM"}:
                removed_colour += 1
            if identity != "CLIMATE_ACCESSORY":
                if identity == "CLIMATE_UI":
                    removed_ui += 1
                elif identity == "CLIMATE_UE":
                    removed_ue += 1
                elif identity == "CLIMATE_SYSTEM":
                    removed_system += 1
                removed = {
                    **concise(record, candidate), "product_domain": domain,
                    "candidate_identity": identity,
                    "identity_evidence": identity_reason,
                    "reason": (
                        "CLIMATE_PRODUCT_NOT_ACCESSORY"
                        if identity in {"CLIMATE_UI", "CLIMATE_UE", "CLIMATE_SYSTEM"}
                        else "UNKNOWN_ACCESSORY_IDENTITY"
                    ),
                    "panel_grid_not_applicable": invalid_panel,
                    "colour_variant": colour,
                }
                rejected.append(removed)
                removed_edge_examples.append(removed)
                if invalid_panel:
                    removed_panel += 1
                continue
            if invalid_panel:
                removed_panel += 1
                removed = {
                    **concise(record, candidate), "product_domain": domain,
                    "candidate_identity": identity, "reason": "PANEL_GRID_NOT_APPLICABLE",
                }
                rejected.append(removed)
                removed_edge_examples.append(removed)
                continue
            kept_accessories.append(candidate)
            kept_edge_examples.append({
                **concise(record, candidate), "product_domain": domain,
                "candidate_identity": identity,
                "identity_evidence": identity_reason,
                "governor_evidence": record.get("governor_evidence"),
                "scope_type": record.get("scope_type"),
            })
        if not kept_accessories:
            continue
        record["accessories"] = kept_accessories
        record["candidate_identity"] = (
            kept_accessories[0]["candidate_identity"]
            if len(kept_accessories) == 1 else "CLIMATE_ACCESSORY"
        )
        record["candidate_identity_evidence"] = "ALL_EMITTED_PTS_ARE_CLIMATE_ACCESSORIES"
        kept.append(record)

    checks = hard_regressions(kept, identity_index)
    final_non_climate = sum(row.get("product_domain") != "CLIMATE" for row in kept)
    final_bad_identity = sum(
        accessory.get("candidate_identity") != "CLIMATE_ACCESSORY"
        for row in kept for accessory in row.get("accessories") or []
    )
    final_panel_bad = sum(
        panel_or_grid(row, accessory) and not is_cassette(row)
        for row in kept for accessory in row.get("accessories") or []
    ) + sum(
        not row.get("accessories") and panel_or_grid(row) and not is_cassette(row)
        for row in kept
    )
    readiness = {
        "zero_non_climate_relations": final_non_climate == 0,
        "zero_ui_as_accessory": not any(
            accessory.get("candidate_identity") == "CLIMATE_UI"
            for row in kept for accessory in row.get("accessories") or []
        ),
        "zero_ue_as_accessory": not any(
            accessory.get("candidate_identity") == "CLIMATE_UE"
            for row in kept for accessory in row.get("accessories") or []
        ),
        "zero_system_as_accessory": not any(
            accessory.get("candidate_identity") == "CLIMATE_SYSTEM"
            for row in kept for accessory in row.get("accessories") or []
        ),
        "zero_panel_grid_outside_cassette": final_panel_bad == 0,
        "all_hard_regressions_pass": all(item["PASS"] for item in checks.values()),
    }
    channel_before = Counter(row.get("source_channel") for row in source)
    channel_after = Counter(row.get("source_channel") for row in kept)
    removed_example_sample = [
        *[item for item in removed_edge_examples if item["reason"] != "NON_CLIMATE_SCOPE"],
        *[item for item in removed_edge_examples if item["reason"] == "NON_CLIMATE_SCOPE"],
    ][:20]
    regression_pts = {
        "50253210", "50021123", "99794507", "99794583",
        "99759964", "99759971", "99759988", "99759995",
        "99718268", "99718275", "50131419", "50395835",
    }
    kept_example_sample = [
        *[item for item in kept_edge_examples if str(item.get("pt") or "") in regression_pts],
        *[item for item in kept_edge_examples if str(item.get("pt") or "") not in regression_pts],
    ][:20]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "SAFE_PREVIEW_V3_1_CLIMATE_ONLY",
        "architecture": {
            "upstream": "SAFE_PREVIEW_V2",
            "incremental_change": [
                "GATE_0_PRODUCT_DOMAIN", "GATE_1_ACCESSORY_IDENTITY",
                "PANEL_GRID_CASSETTE_APPLICABILITY",
            ],
            "candidate_identity_authority": [
                "CLIMATE_COMPATIBILITY_MASTER_PT_ROLE",
                "UNIFIED_MASTER_CATEGORY",
                "CATALOG_TABLE_CONTEXT_FALLBACK",
            ],
            "preserved": [
                "GLOBAL_RED_ANNOTATION_EXTRACTION", "COMPONENT_SAFETY",
                "STRONG_GOVERNOR", "SCOPE_TYPE", "DEDUPLICATION", "PROVENANCE",
                "AERMEC_DAIKIN_MIDEA_REGRESSIONS",
            ],
        },
        "input_sha256": before_hashes,
        "previous_v2_production_ready": v2_report.get("production_ready"),
        "previous_v2_records": len(source),
        "final_climate_relations_count": len(kept),
        "removed_total_count": len(source) - len(kept),
        "removed_non_climate_count": sum(
            item.get("reason") == "NON_CLIMATE_SCOPE" for item in rejected
        ),
        "removed_ui_as_accessory_count": removed_ui,
        "removed_ue_as_accessory_count": removed_ue,
        "removed_system_as_accessory_count": removed_system,
        "removed_panel_non_cassette_count": removed_panel,
        "removed_colour_variant_count": removed_colour,
        "candidate_identity_distribution": {
            value: identity_distribution.get(value, 0) for value in IDENTITIES
        },
        "product_domain_distribution_before_gate": {
            value: domain_distribution.get(value, 0) for value in DOMAINS
        },
        "final_validation": {
            "non_climate_relations": final_non_climate,
            "non_accessory_pt_candidates": final_bad_identity,
            "panel_grid_outside_cassette": final_panel_bad,
        },
        "by_source_channel_before": dict(channel_before),
        "by_source_channel_after": dict(channel_after),
        "removed_by_reason": dict(Counter(item["reason"] for item in rejected)),
        "removed_records": rejected,
        "removed_edge_examples": removed_example_sample,
        "kept_climate_edge_examples": kept_example_sample,
        "hard_regression_checks": checks,
        "production_ready_conditions": readiness,
        "production_ready": all(readiness.values()),
        "elapsed_seconds": round(time.time() - started, 2),
    }

    OUTPUT_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    after_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    if after_hashes != before_hashes:
        raise RuntimeError("An input or production dataset changed during V3.1 generation")
    if not report["production_ready"]:
        failed = [name for name, value in readiness.items() if not value]
        raise RuntimeError(f"V3.1 failed production-ready gates: {failed}")
    print(json.dumps({
        "previous_v2_records": len(source),
        "final_climate_relations_count": len(kept),
        "removed_total_count": report["removed_total_count"],
        "removed_non_climate_count": report["removed_non_climate_count"],
        "removed_ui_as_accessory_count": removed_ui,
        "removed_ue_as_accessory_count": removed_ue,
        "removed_system_as_accessory_count": removed_system,
        "removed_panel_non_cassette_count": removed_panel,
        "removed_colour_variant_count": removed_colour,
        "production_ready": report["production_ready"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
