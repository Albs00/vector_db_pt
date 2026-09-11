import collections
import json
import os
import re
import sys
import time
from pathlib import Path

from run_benchmark import (
    FROZEN,
    ROOT,
    compact_component,
    compact_top_candidates,
    existing_mpn_status,
    json_dump_line,
)


def process(engine, record):
    wall_start = time.perf_counter()
    try:
        result = engine.search(record["title"], limit=20)
        qa = result.get("query_analysis") or {}
        context = qa.get("query_context") or {}
        bom = result.get("bom") or []
        selected_components = [compact_component(item) for item in bom]
        ue = next((item for item in selected_components if item.get("role") == "UE"), None)
        models = [item.get("model") for item in selected_components if item.get("model")]
        automatic_mpn = " + ".join(models) if models else None
        identity = result.get("product_identity_status") or qa.get("product_identity_status")
        if not selected_components:
            main_status = "NO_MAIN_UNIT_SELECTED"
        elif identity:
            main_status = identity
        elif qa.get("exact_token_candidates"):
            main_status = "EXACT"
        else:
            main_status = "DISCOVERY_ONLY"
        elapsed_ms = round((time.perf_counter() - wall_start) * 1000, 2)
        return {
            **{key: record.get(key) for key in (
                "row_id", "sheet", "excel_row", "title", "current_mpn", "reference", "brand_original"
            )},
            "benchmark_scope": "CLIMA",
            "detected_brand": result.get("detected_brand"),
            "product_scope": result.get("product_scope") or context.get("product_scope") or "GENERAL",
            "requested_btu": context.get("requested_btus") or [],
            "requested_type": context.get("explicit_tipologia") or context.get("probable_tipologia"),
            "requested_family": context.get("requested_family_key") or context.get("requested_family"),
            "requested_color": context.get("query_color") or context.get("requested_color"),
            "exact_tokens": qa.get("exact_token_candidates") or [],
            "near_model_candidates": qa.get("near_model_candidates") or [],
            "selected_components": selected_components,
            "selected_ue": ({"pt": ue.get("pt"), "model": ue.get("model"), "family": ue.get("family")} if ue else None),
            "automatic_mpn": automatic_mpn,
            "mpn_final_allowed": bool(result.get("mpn_final_allowed")),
            "main_unit_match_status": main_status,
            "configuration_status": result.get("configuration_status") or "NOT_APPLICABLE",
            "existing_mpn_comparison": existing_mpn_status(record.get("current_mpn"), automatic_mpn),
            "top_candidates_by_slot": compact_top_candidates(result.get("candidate_pools")),
            "runtime_ms": elapsed_ms,
            "error": None,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - wall_start) * 1000, 2)
        return {
            **{key: record.get(key) for key in (
                "row_id", "sheet", "excel_row", "title", "current_mpn", "reference", "brand_original"
            )},
            "benchmark_scope": "CLIMA",
            "selected_components": [],
            "selected_ue": None,
            "automatic_mpn": None,
            "main_unit_match_status": "RUNTIME_ERROR",
            "configuration_status": "ERROR",
            "existing_mpn_comparison": existing_mpn_status(record.get("current_mpn"), None),
            "top_candidates_by_slot": {},
            "runtime_ms": elapsed_ms,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def main():
    shard_index = int(sys.argv[1])
    shard_count = int(sys.argv[2])
    output = Path(sys.argv[3])
    records = [json.loads(line) for line in FROZEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    clima = [record for record in records if record["benchmark_scope"] == "CLIMA"]
    shard = [record for index, record in enumerate(clima) if index % shard_count == shard_index]
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from catalog_search_engine import CatalogSearchEngine
    engine = CatalogSearchEngine()
    engine._ensure_initialized()
    with open(output, "w", encoding="utf-8", newline="\n", buffering=1) as handle:
        for index, record in enumerate(shard, start=1):
            handle.write(json_dump_line(process(engine, record)) + "\n")
            if index % 50 == 0 or index == len(shard):
                print(json.dumps({
                    "shard": shard_index,
                    "completed": index,
                    "total": len(shard),
                    "last_row_id": record["row_id"],
                }), flush=True)


if __name__ == "__main__":
    main()
