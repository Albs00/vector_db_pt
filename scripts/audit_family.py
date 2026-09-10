import csv
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
REPORT_JSON_PATH = ROOT / "family_audit_report.json"
REPORT_CSV_PATH = ROOT / "family_audit_report.csv"


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.catalog_table_context import make_family_key


FIELD_NAMES = [
    "pt_code",
    "brand",
    "model",
    "current_family",
    "current_family_key",
    "proposed_family",
    "proposed_family_key",
    "page",
    "table_id",
    "issue_type",
    "confidence",
    "evidence",
    "auto_correctable",
]


def compact(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def normalized_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.upper()).strip()


def table_id_page(table_id):
    match = re.fullmatch(r"PDF_P(\d{4})_[A-F0-9]{10}", str(table_id or ""))
    return int(match.group(1)) if match else None


def model_tokens(value):
    tokens = re.findall(r"[A-Z0-9]{5,}", normalized_text(value))
    return sorted({compact(token) for token in tokens if len(compact(token)) >= 5}, key=len, reverse=True)


def load_layout():
    pages = {}
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            page = json.loads(line)
            page_number = page.get("page")
            if not isinstance(page_number, int):
                raise ValueError(f"Pagina layout non valida alla riga {line_number}")
            pages[page_number] = page
    return pages


def page_match(page, record):
    text = page.get("text") or ""
    compact_page = compact(text)
    title = record.get("table_title") or record.get("catalog_family")
    title_token = compact(title)
    title_match = bool(title_token and title_token in compact_page)
    model_candidates = model_tokens(record.get("model")) + model_tokens(record.get("mpn"))
    model_matches = [token for token in model_candidates if token and token in compact_page]
    blocks = page.get("blocks") or []
    title_blocks = []
    model_blocks = []
    for index, block in enumerate(blocks):
        block_parts = []
        for line in block.get("lines", []):
            line_text = line.get("text")
            if line_text is None:
                line_text = " ".join(str(span.get("text") or "") for span in line.get("spans", []))
            block_parts.append(str(line_text or ""))
        block_text = " ".join(block_parts)
        compact_block = compact(block_text)
        if title_token and title_token in compact_block:
            title_blocks.append({"index": index, "bbox": block.get("bbox"), "text": block_text[:500]})
        if any(token in compact_block for token in model_candidates):
            model_blocks.append({"index": index, "bbox": block.get("bbox"), "text": block_text[:500]})
    return {
        "page": page.get("page"),
        "source": page.get("source"),
        "title_match": title_match,
        "model_matches": model_matches[:8],
        "model_match": bool(model_matches),
        "title_blocks": title_blocks[:8],
        "model_blocks": model_blocks[:8],
        "same_block_match": bool({item["index"] for item in title_blocks} & {item["index"] for item in model_blocks}),
    }


def strict_leaf_map(contexts):
    families_by_brand = defaultdict(set)
    for record in contexts.values():
        brand = str(record.get("brand") or "").strip()
        family = str(record.get("catalog_family") or "").strip()
        if brand and family:
            families_by_brand[brand].add(family)
        for alternate in record.get("alternate_table_contexts") or []:
            family = str(alternate.get("catalog_family") or "").strip()
            if brand and family:
                families_by_brand[brand].add(family)

    leaves = {}
    parents = {}
    for brand, families in families_by_brand.items():
        for family in families:
            family_key = compact(family)
            children = sorted(
                candidate
                for candidate in families
                if candidate != family and compact(candidate).startswith(family_key + "")
                and len(compact(candidate)) > len(family_key)
                and re.match(rf"^{re.escape(family_key)}[A-Z0-9]", compact(candidate))
            )
            # The token boundary above avoids treating arbitrary substrings as children.
            if children:
                parents[(brand, family)] = children
            leaves[(brand, family)] = children
    return parents, leaves


def distinct_alternate_families(record):
    primary = record.get("catalog_family")
    return sorted({
        str(item.get("catalog_family") or "").strip()
        for item in record.get("alternate_table_contexts") or []
        if item.get("catalog_family") and item.get("catalog_family") != primary
    })


def likely_compatibility_context(record):
    text = " ".join(
        str(record.get(field) or "")
        for field in ("table_title", "section_title", "catalog_family")
    ).upper()
    return bool(re.search(r"COMPATIB|COMBINAZION|TABELLA|MULTI\s*SPLIT|UNIT[AÀ]'?\s+(?:ESTERNE|INTERNE)", text))


def family_relation(parent, child):
    parent_key = compact(parent)
    child_key = compact(child)
    return child_key.startswith(parent_key) and len(child_key) > len(parent_key)


def audit_record(code, record, pages, parents, model_families, mpn_families):
    brand = record.get("brand")
    family = record.get("catalog_family")
    family_key = record.get("family_key")
    expected_key = make_family_key(brand, family)
    page_number = record.get("page")
    page = pages.get(page_number)
    evidence = []
    proposed_family = None
    proposed_key = None
    issue = "OK"
    confidence = 1.0
    auto_correctable = False

    if family_key != expected_key:
        issue = "WRONG_FAMILY"
        confidence = 1.0
        auto_correctable = True
        proposed_family = family
        proposed_key = expected_key
        evidence.append({
            "source": "deterministic_family_key_normalization",
            "current_family": family,
            "expected_family_key": expected_key,
        })

    if page is None:
        issue = "LAYOUT_REVIEW_REQUIRED"
        confidence = 1.0
        auto_correctable = False
        evidence.append({"source": "catalogo_layout.jsonl.gz", "page": page_number, "page_found": False})
    else:
        layout = page_match(page, record)
        evidence.append({"source": "catalogo_layout.jsonl.gz", **layout})
        if table_id_page(record.get("table_id")) != page_number:
            issue = "LAYOUT_REVIEW_REQUIRED"
            confidence = 1.0
            auto_correctable = False
            evidence.append({
                "source": "table_id_page_consistency",
                "table_id": record.get("table_id"),
                "table_id_page": table_id_page(record.get("table_id")),
                "context_page": page_number,
            })
        elif not layout["model_match"] or not layout["title_match"]:
            issue = "LAYOUT_REVIEW_REQUIRED"
            confidence = 0.95
            auto_correctable = False
            evidence.append({
                "source": "catalogo_layout.jsonl.gz",
                "reason": "modello_o_titolo_non_verificato_nella_pagina",
                "model_match": layout["model_match"],
                "title_match": layout["title_match"],
            })

    current_model_families = model_families.get((brand, compact(record.get("model"))), set())
    current_mpn_families = mpn_families.get((brand, compact(record.get("mpn"))), set())
    if len(current_model_families) > 1 or len(current_mpn_families) > 1:
        issue = "CONFLICTING_CONTEXTS"
        confidence = max(confidence, 0.98)
        auto_correctable = False
        evidence.append({
            "source": "same_brand_model_or_mpn_contexts",
            "model_families": sorted(current_model_families),
            "mpn_families": sorted(current_mpn_families),
        })

    alternates = distinct_alternate_families(record)
    children = parents.get((brand, family), [])
    specific_alternates = [item for item in alternates if any(family_relation(family, item) for _ in [0])]
    if specific_alternates and not record.get("family_conflict"):
        issue = "MORE_SPECIFIC_FAMILY_AVAILABLE" if len(specific_alternates) == 1 else "AMBIGUOUS_FAMILY"
        confidence = max(confidence, 0.9 if len(specific_alternates) == 1 else 0.8)
        auto_correctable = False
        if len(specific_alternates) == 1:
            proposed_family = specific_alternates[0]
            proposed_key = make_family_key(brand, proposed_family)
        evidence.append({
            "source": "alternate_table_contexts",
            "primary_family": family,
            "specific_alternate_families": specific_alternates,
            "reason": "primary_context_generico_con_alternate_leaf" if len(specific_alternates) == 1 else "multiple_leaf_alternative",
        })
    elif children and issue == "OK":
        issue = "GENERIC_PARENT_FAMILY"
        confidence = 0.8 if likely_compatibility_context(record) else 0.65
        auto_correctable = False
        evidence.append({
            "source": "same_brand_family_hierarchy",
            "parent_family": family,
            "leaf_candidates": children[:20],
            "compatibility_context": likely_compatibility_context(record),
        })

    if alternates and issue == "OK":
        evidence.append({
            "source": "alternate_table_contexts",
            "alternate_families": alternates,
            "primary_family_is_specific": not any(family_relation(family, item) for item in alternates),
        })

    if record.get("family_conflict") is not False:
        issue = "CONFLICTING_CONTEXTS"
        confidence = max(confidence, 0.99)
        auto_correctable = False
        evidence.append({
            "source": "stored_family_conflict",
            "family_conflict": record.get("family_conflict"),
        })

    if likely_compatibility_context(record) and issue == "OK" and children:
        issue = "GENERIC_PARENT_FAMILY"
        confidence = max(confidence, 0.8)
        auto_correctable = False
        evidence.append({
            "source": "compatibility_table_context",
            "table_title": record.get("table_title"),
            "section_title": record.get("section_title"),
            "reason": "titolo_di_contesto_compatibilita_non_necessariamente_leaf_prodotto",
        })

    return {
        "pt_code": str(code),
        "brand": brand,
        "model": record.get("model"),
        "current_family": family,
        "current_family_key": family_key,
        "proposed_family": proposed_family,
        "proposed_family_key": proposed_key,
        "page": page_number,
        "table_id": record.get("table_id"),
        "issue_type": issue,
        "confidence": round(confidence, 4),
        "evidence": evidence,
        "auto_correctable": auto_correctable,
    }


def build_report():
    contexts = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    pages = load_layout()
    parents, _ = strict_leaf_map(contexts)

    model_families = defaultdict(set)
    mpn_families = defaultdict(set)
    for record in contexts.values():
        brand = record.get("brand")
        family = record.get("catalog_family")
        model = compact(record.get("model"))
        mpn = compact(record.get("mpn"))
        if brand and model:
            model_families[(brand, model)].add(family)
        if brand and mpn:
            mpn_families[(brand, mpn)].add(family)

    records = [
        audit_record(code, record, pages, parents, model_families, mpn_families)
        for code, record in contexts.items()
    ]
    issue_counts = Counter(record["issue_type"] for record in records)
    by_brand = defaultdict(Counter)
    for record in records:
        if record["issue_type"] != "OK":
            by_brand[record["brand"]][record["issue_type"]] += 1

    family_counts = Counter((record["brand"], record["current_family"]) for record in records)
    suspicious_families = []
    for (brand, family), count in family_counts.items():
        issues = Counter(
            record["issue_type"]
            for record in records
            if record["brand"] == brand and record["current_family"] == family and record["issue_type"] != "OK"
        )
        if issues or (brand, family) in parents:
            suspicious_families.append({
                "brand": brand,
                "family": family,
                "records": count,
                "issue_counts": dict(issues),
                "leaf_candidates": parents.get((brand, family), [])[:20],
                "sample_pt_codes": [
                    record["pt_code"]
                    for record in records
                    if record["brand"] == brand and record["current_family"] == family
                ][:10],
            })
    suspicious_families.sort(key=lambda item: (-sum(item["issue_counts"].values()), -item["records"], item["brand"], item["family"]))

    haier_expert = [
        record for record in records
        if record["brand"] == "HAIER" and "EXPERT" in str(record["current_family"] or "").upper()
    ]
    report = {
        "metadata": {
            "audit": "family_audit",
            "context": str(CONTEXT_PATH.relative_to(ROOT)),
            "primary_source": str(LAYOUT_PATH.relative_to(ROOT)),
            "context_modified": False,
            "matcher_modified": False,
            "method": "Confronto pagina/titolo/modello/MPN e blocchi layout; gerarchia parent/leaf brand-scoped; nessuna inferenza colore da suffissi non confermati.",
        },
        "summary": {
            "totale_record": len(records),
            "totale_ok": issue_counts.get("OK", 0),
            "errori_certi": sum(record["auto_correctable"] for record in records),
            "family_parent_generiche": issue_counts.get("GENERIC_PARENT_FAMILY", 0),
            "ambigui": issue_counts.get("AMBIGUOUS_FAMILY", 0),
            "distribuzione_per_brand": {brand: dict(counts) for brand, counts in sorted(by_brand.items())},
            "issue_counts": dict(issue_counts),
            "family_key_mismatch": sum(
                any(item.get("source") == "deterministic_family_key_normalization" for item in record["evidence"])
                for record in records
            ),
            "context_con_alternate": sum(bool(contexts[record["pt_code"]].get("alternate_table_contexts")) for record in records),
            "layout_pages": len(pages),
            "layout_page_min": min(pages) if pages else None,
            "layout_page_max": max(pages) if pages else None,
            "family_parent_distinte": len(parents),
            "top_50_family_sospette": suspicious_families[:50],
            "regression_case_haier": [
                record for record in haier_expert if record["pt_code"] == "50283866"
            ],
            "haier_expert_records": haier_expert,
        },
        "records": records,
    }
    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with REPORT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_NAMES)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["evidence"] = json.dumps(row["evidence"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow({field: row.get(field) for field in FIELD_NAMES})
    print(json.dumps({
        "report_json": str(REPORT_JSON_PATH),
        "report_csv": str(REPORT_CSV_PATH),
        "summary": report["summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build_report()
