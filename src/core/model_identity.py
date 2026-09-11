"""Conservative structural comparison for catalog manufacturer models."""

import re
from typing import Dict, Optional


def normalize_structural_model(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def classify_structural_model_diff(
    query_model: str, catalog_model: str
) -> Dict[str, Optional[object]]:
    """Classify model differences without treating color suffixes as revisions."""
    query_text = str(query_model or "").upper().strip()
    catalog_text = str(catalog_model or "").upper().strip()
    query_norm = normalize_structural_model(query_text)
    catalog_norm = normalize_structural_model(catalog_text)
    result: Dict[str, Optional[object]] = {
        "matched": False,
        "structural_stem": None,
        "diff_type": "STRUCTURAL_MISMATCH",
        "diff_details": None,
        "penalty": 100,
    }
    if not query_norm or not catalog_norm:
        return result
    if query_norm == catalog_norm:
        result.update({
            "matched": True,
            "structural_stem": query_text,
            "diff_type": "EXACT",
            "diff_details": None,
            "penalty": 0,
        })
        return result

    # A terminal change is a revision only when both suffixes are numeric.
    # Terminal letters commonly encode color/finish (V/R/B/W).
    if len(query_norm) == len(catalog_norm) and query_norm[:-1] == catalog_norm[:-1]:
        query_suffix = query_norm[-1]
        catalog_suffix = catalog_norm[-1]
        stem_text = query_text[:-1].rstrip("-_. /")
        if query_suffix.isdigit() and catalog_suffix.isdigit():
            result.update({
                "matched": True,
                "structural_stem": stem_text,
                "diff_type": "REVISION_ONLY",
                "diff_details": f"{query_suffix} -> {catalog_suffix}",
                "penalty": 5,
            })
        else:
            result.update({
                "structural_stem": stem_text,
                "diff_type": "VARIANT_SUFFIX_MISMATCH",
                "diff_details": f"{query_suffix} -> {catalog_suffix}",
                "penalty": 80,
            })
        return result

    query_parts = re.findall(r"[A-Z]+|\d+", query_norm)
    catalog_parts = re.findall(r"[A-Z]+|\d+", catalog_norm)
    if query_parts and catalog_parts and query_parts[0] != catalog_parts[0]:
        result["diff_type"] = "SERIES_PREFIX_MISMATCH"
        result["penalty"] = 100
    elif len(query_parts) > 1 and len(catalog_parts) > 1 and query_parts[1] != catalog_parts[1]:
        result["diff_type"] = "TOPOLOGY_PORT_COUNT_MISMATCH"
        result["penalty"] = 90
    elif len(query_parts) > 3 and len(catalog_parts) > 3 and query_parts[3] != catalog_parts[3]:
        result["diff_type"] = "CAPACITY_CLASS_MISMATCH"
        result["penalty"] = 70
    else:
        result["diff_type"] = "CORE_MODEL_MISMATCH"
        result["penalty"] = 80
    result["diff_details"] = f"{query_text} != {catalog_text}"
    return result
