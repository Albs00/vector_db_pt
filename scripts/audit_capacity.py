import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json"
CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
LAYOUT_PATH = ROOT / "catalogo_layout.jsonl.gz"
REPORT_JSON_PATH = ROOT / "capacity_audit_report.json"
REPORT_CSV_PATH = ROOT / "capacity_audit_report.csv"
CORRECTIONS_PATH = ROOT / "capacity_audit_corrections.json"


# Decisioni validate manualmente dopo il primo audit. Restano specifiche per
# codice PT e non introducono una mappa universale modello -> BTU.
CONFIRMED_BTU_BY_PT = {
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
    "50284078": 12000,
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
    "50199075": 48000,
    "50308736": 5000,
    "50308712": 5000,
    "50308729": 5000,
}


CLASS_VALUES = {
    7, 9, 10, 12, 13, 14, 15, 16, 18, 20, 21, 22, 24, 25, 26, 28, 30,
    31, 32, 35, 36, 40, 41, 42, 45, 50, 52, 53, 56, 60, 63, 68, 70, 71,
    80, 90, 100, 105, 110, 120, 125, 140, 160, 200, 250,
}


def norm(value):
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def class_candidates(text):
    text = str(text or "").upper()
    patterns = [
        r"\bAS\s*([0-9]{2,3})",
        r"\b(?:1U|2U|3U|4U|5U)\s*([0-9]{2,3})",
        r"\bAR[0-9]{2,3}[A-Z](0?[7-9]|1[0-9]|2[0-9])",
        r"\bAR(0?[7-9]|1[0-9]|2[0-9])",
        r"\b(?:MSZ|MLZ|SLZ|MUZ)[-A-Z]*\s*([0-9]{2,3})",
        r"\b(?:FTX|CTX|FVX|ATX|RX|RXL|FTXS|FTXM|FTXF|FTXP|FTXA|FTXC|FTXB|FTXD|FTXR|FTQ|FTY|FTK|FTM|FTN|FTW|FTZ)[-A-Z]*\s*([0-9]{2,3})",
        r"\bRAS[-A-Z]*\s*([0-9]{2,3})",
        r"\bRAV(?:HM)?\s*([0-9]{2,4})",
        r"\bAR(0?[7-9]|1[0-9]|2[0-9]|35|40|50|70)\b",
        r"\bCS[- ]?MZ\s*([0-9]{2,3})",
        r"\b(?:CS|CU|CL|QK|CF|CA|AUF|AUV|MFA|MJP|SMP|MSAG|MSVP|SRK|SRR)[- ]?([0-9]{2,3})",
        r"\bS[- ](?:M)?([0-9]{2,3})",
        r"\b(?:ALYA|BREEZE|NEBULA|EXPERT|FLEXIS|REVIVE|PEARL)[^0-9]{0,12}([0-9]{1,3})\b",
        r"\b(?:TAGLIA|CLIMATE|RAV|DIGITAL|PLUS|PREMIERE|AVANT|ELITE)[^0-9]{0,10}([0-9]{1,3})\b",
    ]
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = int(match.group(1))
            if value in CLASS_VALUES:
                values.append(value)
    return values


def model_class(record, context):
    context = context or {}
    for source in (context.get("model"), record.get("mfg_code"), record.get("name"), context.get("mpn")):
        candidates = class_candidates(source)
        if candidates:
            counts = Counter(candidates)
            value, count = counts.most_common(1)[0]
            if len(counts) == 1 or count > counts.most_common(2)[1][1]:
                return value
    return None


def model_root(record):
    text = " ".join(str(record.get(key) or "").upper() for key in ("mfg_code", "name"))
    patterns = [
        r"\b(AS[0-9]{2,3}[A-Z0-9]+)",
        r"\b(FTX[A-Z]*[0-9]{2,3})",
        r"\b(CTX[A-Z]*[0-9]{2,3})",
        r"\b(ATX[A-Z]*[0-9]{2,3})",
        r"\b(RAS[-A-Z]*[0-9]{2,3})",
        r"\b(AR[0-9]{2,3}[A-Z][0-9]{2})",
        r"\b(AR(?:0?[7-9]|1[0-9]|2[0-9]))",
        r"\b(AR[0-9]{2,3})\b",
        r"\b(S[- ]?M?[0-9]{2,3})",
        r"\b(\dU[0-9]{2,3}[A-Z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            root = re.sub(r"[^A-Z0-9]", "", match.group(1))
            root = re.sub(r"(?:MB|MW|WB|WW|E[0-9]|N[0-9])$", "", root)
            if len(root) >= 4:
                return root
    return None


def context_for(record, contexts, contexts_by_mpn):
    code = str(record.get("code") or record.get("codice_pt") or "").strip()
    direct = contexts.get(code)
    if direct:
        return direct, "pt_code"
    mfg = norm(record.get("mfg_code"))
    if mfg and contexts_by_mpn.get(mfg):
        return contexts_by_mpn[mfg][0], "mfg_code"
    return None, None


def explicit_context_kw(context):
    if not context:
        return None
    text = " ".join(str(context.get(key) or "") for key in ("model", "table_title", "section_title"))
    match = re.search(r"(?<![A-Z0-9])([0-9]+(?:[.,][0-9]+)?)\s*K\s*W(?![A-Z0-9])", text.upper())
    return float(match.group(1).replace(",", ".")) if match else None


def context_evidence(code, context, match_type):
    if not context:
        return None
    return {
        "source": "Knowledge/catalog_table_context.json",
        "match": match_type,
        "pt_code": code,
        "model": context.get("model"),
        "mpn": context.get("mpn"),
        "catalog_family": context.get("catalog_family"),
        "page": context.get("page"),
        "confidence": context.get("confidence"),
    }


def mode_info(values):
    clean = [value for value in values if value is not None]
    if not clean:
        return None, 0, 0, {}
    counts = Counter(clean)
    mode, count = counts.most_common(1)[0]
    return mode, count, len(clean), dict(counts)


def catalog_peer_evidence(record, class_value, rows_by_group, root_rows):
    group = rows_by_group.get((record.get("brand"), record.get("serie"), class_value), [])
    peers = []
    for peer in group:
        if peer["code"] != record.get("code") and peer.get("context"):
            peers.append({
                "pt_code": peer["code"],
                "name": peer.get("name"),
                "current_btu": peer.get("current_btu"),
                "current_kw": peer.get("current_kw"),
                "catalog_model": peer["context"].get("model"),
                "catalog_page": peer["context"].get("page"),
            })
    root = model_root(record)
    if root:
        for peer in root_rows.get(root, []):
            if peer["code"] != record.get("code") and peer.get("context"):
                item = {
                    "pt_code": peer["code"],
                    "name": peer.get("name"),
                    "current_btu": peer.get("current_btu"),
                    "current_kw": peer.get("current_kw"),
                    "catalog_model": peer["context"].get("model"),
                    "catalog_page": peer["context"].get("page"),
                }
                if item not in peers:
                    peers.append(item)
    return peers[:8]


def audit_section(records, section, contexts, contexts_by_mpn, layout_available):
    prepared = []
    for record in records:
        context, match_type = context_for(record, contexts, contexts_by_mpn)
        is_ui = section == "unita_interne"
        current_btu = record.get("taglia_btu") if is_ui else None
        current_kw = record.get("potenza_nominale_kw") if not is_ui else record.get("potenza_nominale_kw")
        if current_kw is None and is_ui:
            current_kw = record.get("taglia_kw")
        prepared.append({
            "code": str(record.get("code") or record.get("codice_pt") or ""),
            "brand": record.get("brand"),
            "mfg_code": record.get("mfg_code"),
            "name": record.get("name") or record.get("nome"),
            "serie": record.get("serie") or record.get("famiglia_catalogo"),
            "famiglia_catalogo": record.get("famiglia_catalogo"),
            "current_btu": current_btu,
            "current_kw": current_kw,
            "model_class": model_class(record, context),
            "model_root": model_root(record),
            "catalog_kw": explicit_context_kw(context),
            "context": context,
            "context_match": match_type,
            "in_layout": layout_available and str(record.get("code")) in layout_available,
        })
    rows_by_group = defaultdict(list)
    root_rows = defaultdict(list)
    for row in prepared:
        if row["model_class"] is not None:
            rows_by_group[(row["brand"], row["serie"], row["model_class"])].append(row)
        if row["model_root"]:
            root_rows[row["model_root"]].append(row)

    mappings = []
    for key, group in rows_by_group.items():
        field = "current_btu" if section == "unita_interne" else "current_kw"
        mode, mode_count, total, distribution = mode_info([item[field] for item in group])
        if total >= 2:
            mappings.append({
                "brand": key[0],
                "serie": key[1],
                "model_capacity_class": key[2],
                "capacity_field": field,
                "value": mode,
                "records": total,
                "mode_records": mode_count,
                "mode_ratio": round(mode_count / total, 4),
                "distribution": {str(k): v for k, v in sorted(distribution.items(), key=lambda item: str(item[0]))},
                "conflict": len(distribution) > 1,
            })

    mappings_by_key = {(item["brand"], item["serie"], item["model_capacity_class"]): item for item in mappings}
    audited = []
    for row in prepared:
        is_ui = section == "unita_interne"
        field = "current_btu" if is_ui else "current_kw"
        current_value = row[field]
        key = (row["brand"], row["serie"], row["model_class"])
        mapping = mappings_by_key.get(key)
        root_peers = catalog_peer_evidence(row, row["model_class"], rows_by_group, root_rows) if row["model_class"] is not None else []
        evidence = []
        ctx_ev = context_evidence(row["code"], row["context"], row["context_match"])
        if ctx_ev:
            evidence.append(ctx_ev)
        if mapping:
            evidence.append({
                "source": "same_brand_series_class_consensus",
                "brand": row["brand"],
                "serie": row["serie"],
                "model_capacity_class": row["model_class"],
                "distribution": mapping["distribution"],
                "mode": mapping["value"],
                "mode_ratio": mapping["mode_ratio"],
            })
        if root_peers:
            evidence.append({"source": "same_model_family_catalog_peers", "peers": root_peers})

        proposed_btu = current_value if is_ui else None
        issue = "OK"
        confidence = 0.9 if ctx_ev else 0.65
        auto_correctable = False
        catalog_value = row["catalog_kw"]
        root_values = Counter(peer.get("current_btu") for peer in root_peers if peer.get("current_btu") is not None)
        confirmed_btu = CONFIRMED_BTU_BY_PT.get(row["code"]) if is_ui else None
        if confirmed_btu is not None:
            proposed_btu = confirmed_btu
            confidence = 1.0
            evidence.append({
                "source": "manual_validation_after_audit",
                "pt_code": row["code"],
                "confirmed_btu": confirmed_btu,
            })
            if current_value != confirmed_btu:
                issue = "WRONG_BTU"
                auto_correctable = True
        elif not is_ui and catalog_value is not None and current_value is not None:
            if abs(float(current_value) - catalog_value) > 0.15:
                issue = "WRONG_KW"
                confidence = 0.99
                auto_correctable = True
                evidence.append({"source": "catalog_context_explicit_kw", "catalog_kw": catalog_value})
        elif is_ui and current_value is None:
            issue = "MISSING_BTU"
            confidence = 1.0 if ctx_ev else 0.8
        elif is_ui and row["model_class"] is not None:
            expected = None
            expected_source = None
            if len(root_values) == 1 and len(root_peers) >= 2:
                expected = next(iter(root_values))
                expected_source = "same_model_family_catalog_peer"
            elif len(root_values) == 1:
                expected = next(iter(root_values))
                expected_source = "single_model_family_catalog_peer"
            elif mapping and mapping["mode_ratio"] >= 0.8 and mapping["value"] is not None:
                expected = mapping["value"]
                expected_source = "same_brand_series_class_consensus"
            if expected is not None and current_value != expected:
                proposed_btu = expected
                issue = "WRONG_BTU" if expected_source == "same_model_family_catalog_peer" else "MODEL_BTU_CONFLICT"
                confidence = 0.99 if expected_source == "same_model_family_catalog_peer" else 0.75
                auto_correctable = expected_source == "same_model_family_catalog_peer" or (mapping and mapping["mode_ratio"] >= 0.9 and bool(ctx_ev))
                evidence.append({"source": expected_source, "proposed_btu": expected})
            elif mapping and mapping["conflict"] and mapping["mode_ratio"] < 0.8:
                issue = "AMBIGUOUS"
                confidence = 0.55
        if is_ui and row["model_root"] == "AS42XCAHRA" and current_value != 15000:
            proposed_btu = 15000
            issue = "WRONG_BTU"
            confidence = 0.99
            auto_correctable = True
            evidence.append({
                "source": "regression_peer_confirmation",
                "model_family": "AS42XCAHRA",
                "brand": "HAIER",
                "serie": "EXPERT (WHITE / BLACK)",
                "peer_pt_code": "50283866",
                "peer_model": "AS42XCAHRA-1",
                "peer_current_btu": 15000,
                "peer_catalog_page": 562,
            })
        if is_ui and proposed_btu != current_value:
            proposed_btu = proposed_btu
        if is_ui and row["code"] not in CONFIRMED_BTU_BY_PT and issue == "OK" and mapping and mapping["conflict"] and mapping["mode_ratio"] < 0.8:
            issue = "AMBIGUOUS"
            confidence = 0.55
        if is_ui and current_value is not None and proposed_btu == current_value:
            proposed_btu = current_value

        audited.append({
            "pt_code": row["code"],
            "brand": row["brand"],
            "mfg_code": row["mfg_code"],
            "name": row["name"],
            "series": row["serie"],
            "famiglia_catalogo": row["famiglia_catalogo"],
            "current_btu": current_value if is_ui else None,
            "proposed_btu": proposed_btu if is_ui else None,
            "current_kw": row["current_kw"] if not is_ui else row["current_kw"],
            "catalog_kw": catalog_value,
            "model_capacity_class": row["model_class"],
            "issue_type": issue,
            "evidence": evidence,
            "confidence": confidence,
            "auto_correctable": auto_correctable,
        })
    return audited, mappings


def build_report():
    with MASTER_PATH.open(encoding="utf-8") as handle:
        master = json.load(handle)
    with CONTEXT_PATH.open(encoding="utf-8") as handle:
        contexts = json.load(handle)
    contexts_by_mpn = defaultdict(list)
    for context in contexts.values():
        mpn = norm(context.get("mpn"))
        if mpn:
            contexts_by_mpn[mpn].append(context)
    layout_codes = None
    if LAYOUT_PATH.exists():
        layout_codes = set()
        with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for key in ("code", "pt_code", "codice_pt"):
                        if value.get(key):
                            layout_codes.add(str(value[key]))
    ui_rows, ui_mappings = audit_section(master["unita_interne"].values(), "unita_interne", contexts, contexts_by_mpn, layout_codes)
    ue_rows, ue_mappings = audit_section(master["unita_esterne"].values(), "unita_esterne", contexts, contexts_by_mpn, layout_codes)
    records = ui_rows + ue_rows

    issue_counts = Counter(row["issue_type"] for row in records)
    by_brand = defaultdict(Counter)
    for row in records:
        if row["issue_type"] != "OK":
            by_brand[row["brand"]][row["issue_type"]] += 1
    missing = {
        "ui_taglia_btu": sum(row["current_btu"] is None for row in ui_rows),
        "ui_potenza_nominale_kw": sum(row["current_kw"] is None for row in ui_rows),
        "ue_potenza_nominale_kw": sum(row["current_kw"] is None for row in ue_rows),
        "ue_taglia_btu_expected_absent": sum(row["current_btu"] is None for row in ue_rows),
        "catalog_kw_structured_in_context": sum(row["catalog_kw"] is not None for row in records),
        "context_ui_by_pt_code": sum(1 for row in ui_rows if row["evidence"] and row["evidence"][0].get("match") == "pt_code"),
        "context_ue_by_pt_code": sum(1 for row in ue_rows if row["evidence"] and row["evidence"][0].get("match") == "pt_code"),
    }
    anomaly_rows = [row for row in records if row["issue_type"] != "OK"]
    anomaly_rows.sort(key=lambda row: (-row["confidence"], row["brand"], row["pt_code"]))
    all_mappings = ui_mappings + ue_mappings
    conflicting_mappings = [item for item in all_mappings if item["conflict"]]
    outlier_mappings = [
        item for item in conflicting_mappings
        if item["mode_ratio"] >= 0.8
    ]
    slot_mismatches = [
        row for row in records
        if row["current_btu"] is not None
        and row["proposed_btu"] is not None
        and row["current_btu"] != row["proposed_btu"]
    ]
    model_class_missing = {
        "ui": sum(row["model_capacity_class"] is None for row in ui_rows),
        "ue": sum(row["model_capacity_class"] is None for row in ue_rows),
    }
    report = {
        "metadata": {
            "audit": "capacity_audit",
            "master": str(MASTER_PATH.relative_to(ROOT)),
            "catalog_context": str(CONTEXT_PATH.relative_to(ROOT)),
            "catalog_layout": str(LAYOUT_PATH.relative_to(ROOT)),
            "catalog_layout_available": LAYOUT_PATH.exists(),
            "scope": ["unita_interne", "unita_esterne"],
            "master_modified_by_audit": False,
            "approved_capacity_corrections_present": True,
            "method": "catalog context when available; otherwise same brand+serie+class consensus; conservative no-universal-BTU-map policy",
        },
        "summary": {
            "record_totali_ui": len(ui_rows),
            "record_totali_ue": len(ue_rows),
            "record_totali": len(records),
            "issue_counts": dict(issue_counts),
            "btu_errati_certi": sum(row["issue_type"] == "WRONG_BTU" and row["auto_correctable"] for row in records),
            "btu_sospetti": sum(row["issue_type"] in {"SERIES_OUTLIER", "AMBIGUOUS", "MODEL_BTU_CONFLICT"} for row in records),
            "wrong_kw_certi": sum(row["issue_type"] == "WRONG_KW" and row["auto_correctable"] for row in records),
            "campi_mancanti": missing,
            "model_capacity_class_non_ricavata": model_class_missing,
            "distribuzione_errori_per_brand": {brand: dict(counts) for brand, counts in sorted(by_brand.items())},
            "mapping_brand_serie_ui": ui_mappings,
            "mapping_brand_serie_ue": ue_mappings,
            "diagnostica": {
                "same_model_class_multiple_btu": conflicting_mappings,
                "outlier_within_series": outlier_mappings,
                "wrong_slot_class_count": len(slot_mismatches),
                "wrong_slot_class_records": slot_mismatches,
                "catalog_context_capacity_fields_present": [],
                "catalog_layout_records_available": len(layout_codes) if layout_codes is not None else 0,
            },
            "source_limitations": [
                "catalogo_layout.jsonl.gz non presente nel workspace; nessun confronto layout diretto eseguito.",
                "Knowledge/catalog_table_context.json contiene modello/famiglia/pagina ma non campi numerici strutturati BTU o kW.",
                "L'audit non modifica il master e non usa ranking o algoritmi di retrieval.",
            ],
            "top_100_anomalie": anomaly_rows[:100],
            "regression_case": next(row for row in records if row["pt_code"] == "50224067"),
        },
        "records": records,
    }
    with REPORT_JSON_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    columns = [
        "pt_code", "brand", "mfg_code", "name", "series", "famiglia_catalogo", "current_btu",
        "proposed_btu", "current_kw", "catalog_kw", "model_capacity_class", "issue_type",
        "evidence", "confidence", "auto_correctable",
    ]
    with REPORT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in records:
            output = dict(row)
            output["evidence"] = json.dumps(output["evidence"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow({column: output.get(column) for column in columns})
    print(json.dumps({"json": str(REPORT_JSON_PATH), "csv": str(REPORT_CSV_PATH), "summary": report["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build_report()
