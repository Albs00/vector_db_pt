#!/usr/bin/env python3
"""Second structural pass for the catalog family audit.

The resolver deliberately accepts a change only where a PT/model row is
geometrically attributable to a different catalog heading.  It never infers a
variant from a model suffix or from semantic similarity alone.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ISSUES = ROOT / "family_audit_issues_report.csv"
CONTEXT = ROOT / "Knowledge" / "catalog_table_context.json"
LAYOUT = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
OUT_JSON = ROOT / "family_audit_resolved.json"
OUT_CSV = ROOT / "family_audit_resolved.csv"
OUT_FIXES = ROOT / "family_corrections_to_apply.json"

VERDICTS = {
    "CORRECT", "CHANGE_FAMILY", "KEEP_PARENT", "PROMOTE_TO_LEAF",
    "MULTIPLE_VALID_CONTEXTS", "AMBIGUOUS", "FIX_KEY_ONLY",
}


def norm(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def normal_key_part(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.upper().replace("+", " PLUS ")
    value = re.sub(r"[^A-Z0-9]+", "_", value).strip("_")
    return value.replace("SOFFI_TTO", "SOFFITTO")


def family_key(brand: str, family: str) -> str:
    return "_".join(x for x in (normal_key_part(brand), normal_key_part(family)) if x)


def bcenter(box: list[float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def union_box(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def model_tokens(model: str) -> list[str]:
    raw = unicodedata.normalize("NFKD", str(model or "")).upper()
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    tokens = re.findall(r"[A-Z0-9]+(?:[-./][A-Z0-9]+)*", raw)
    ignore = {"U", "I", "E", "F", "S", "MODELLO", "CODICE", "UNITA"}
    candidates = {norm(t) for t in tokens if norm(t) not in ignore and len(norm(t)) >= 3}
    # The full compact model is preferred, then meaningful model fragments.
    full = norm(raw.replace("U.I.", "").replace("U.E.", "").replace("F.E.S.", ""))
    if len(full) >= 5:
        candidates.add(full)
    return sorted(candidates, key=len, reverse=True)


def json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Occurrence:
    page: int
    code_box: tuple[float, float, float, float]
    model_box: tuple[float, float, float, float] | None
    model_token: str | None
    model_exact: bool


class LayoutIndex:
    def __init__(self, relevant_codes: set[str], relevant_pages: set[int]):
        self.relevant_codes = relevant_codes
        self.relevant_pages = relevant_pages
        self.pages: dict[int, dict[str, Any]] = {}
        self.codes: dict[str, list[Occurrence]] = defaultdict(list)
        self._title_cache: dict[tuple[int, str], list[list[float]]] = {}

    def load(self, path: Path) -> None:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for raw in handle:
                page = json.loads(raw)
                page_no = int(page.get("page", 0))
                if page_no not in self.relevant_pages:
                    continue
                lines: list[dict[str, Any]] = []
                for block_no, block in enumerate(page.get("blocks", [])):
                    for line_no, line in enumerate(block.get("lines", [])):
                        spans = line.get("spans", [])
                        text = "".join(str(s.get("text", "")) for s in spans)
                        if not text.strip():
                            continue
                        boxes = [s.get("bbox") for s in spans if isinstance(s.get("bbox"), list)]
                        bbox = line.get("bbox") if isinstance(line.get("bbox"), list) else (union_box(boxes) if boxes else None)
                        if not bbox:
                            continue
                        lines.append({"text": text, "norm": norm(text), "bbox": bbox,
                                      "spans": spans, "block": block_no, "line": line_no})
                self.pages[page_no] = {"lines": lines}
                self._index_codes(page_no, lines)

    def _index_codes(self, page: int, lines: list[dict[str, Any]]) -> None:
        for line in lines:
            for span in line["spans"]:
                text = str(span.get("text", "")).strip()
                code = text if text in self.relevant_codes else None
                if not code:
                    match = re.fullmatch(r"\s*(\d{6,10})\s*", str(span.get("text", "")))
                    code = match.group(1) if match and match.group(1) in self.relevant_codes else None
                if code and isinstance(span.get("bbox"), list):
                    self.codes[code].append(Occurrence(page, tuple(span["bbox"]), None, None, False))

    def locate(self, code: str, model: str, expected_page: int | None) -> Occurrence | None:
        occurrences = self.codes.get(str(code), [])
        if not occurrences:
            return None
        tokens = model_tokens(model)
        ranked: list[tuple[tuple[float, float, float], Occurrence]] = []
        for occ in occurrences:
            lines = self.pages.get(occ.page, {}).get("lines", [])
            cx, cy = bcenter(list(occ.code_box))
            best: tuple[float, list[float], str, bool] | None = None
            for line in lines:
                lx, ly = bcenter(line["bbox"])
                if abs(ly - cy) > 18:
                    continue
                line_norm = line["norm"]
                for token in tokens:
                    if token and token in line_norm:
                        # Use the exact span when available; a line bbox is still valid geometry.
                        span_boxes = [s.get("bbox") for s in line["spans"]
                                      if isinstance(s.get("bbox"), list) and token in norm(s.get("text", ""))]
                        box = union_box(span_boxes) if span_boxes else line["bbox"]
                        exact = norm(model) == token or token == max(tokens, key=len)
                        score = abs(ly - cy) + abs(lx - cx) * 0.02 - min(len(token), 30) * 0.01
                        if best is None or score < best[0]:
                            best = (score, box, token, exact)
            code_page_penalty = 0 if expected_page is None or occ.page == expected_page else 20
            if best:
                score, box, token, exact = best
                result = Occurrence(occ.page, occ.code_box, tuple(box), token, exact)
                ranked.append(((code_page_penalty, score, 0), result))
            else:
                ranked.append(((code_page_penalty, 1000, 1), occ))
        ranked.sort(key=lambda pair: pair[0])
        return ranked[0][1]

    def title_boxes(self, page: int, title: str) -> list[list[float]]:
        key = (page, norm(title))
        if not key[1]:
            return []
        if key in self._title_cache:
            return self._title_cache[key]
        matches: list[list[float]] = []
        for line in self.pages.get(page, {}).get("lines", []):
            # Exact span/line matches are high-confidence headings.  A contained match
            # is retained only as a weaker fallback (some catalog headings split spans).
            exact_spans = [s.get("bbox") for s in line["spans"]
                           if isinstance(s.get("bbox"), list) and norm(s.get("text", "")) == key[1]]
            if exact_spans:
                matches.append(union_box(exact_spans))
            elif line["norm"] == key[1]:
                matches.append(line["bbox"])
        if not matches:
            for line in self.pages.get(page, {}).get("lines", []):
                if key[1] in line["norm"] and len(key[1]) >= 6:
                    matches.append(line["bbox"])
        # Deduplicate exact layout repeats.
        seen: set[tuple[float, float, float, float]] = set()
        result: list[list[float]] = []
        for box in matches:
            rounded = tuple(round(float(x), 1) for x in box)
            if rounded not in seen:
                seen.add(rounded)
                result.append(box)
        self._title_cache[key] = result
        return result


def is_parent(parent: str, child: str) -> bool:
    p, c = norm(parent), norm(child)
    return bool(p and c and p != c and c.startswith(p))


def structural_match(index: LayoutIndex, occurrence: Occurrence | None, page: int,
                     title: str) -> dict[str, Any] | None:
    if not occurrence or occurrence.page != page:
        return None
    valid: list[dict[str, Any]] = []
    cx, cy = bcenter(list(occurrence.code_box))
    for box in index.title_boxes(page, title):
        hx, hy = bcenter(box)
        # A heading must precede the row and belong to the same vertical column.
        vertical = cy - box[3]
        horizontal = abs(cx - hx)
        if -3 <= vertical <= 330 and horizontal <= 230:
            score = vertical + horizontal * 1.8
            valid.append({"bbox": box, "vertical_gap": round(vertical, 1),
                          "horizontal_gap": round(horizontal, 1), "score": round(score, 1)})
    if not valid:
        return None
    valid.sort(key=lambda item: item["score"])
    return valid[0]


def context_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def row_context(row: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": row.get("catalog_family") or base.get("catalog_family") or "",
        "key": row.get("family_key") or base.get("family_key") or "",
        "title": row.get("table_title") or row.get("catalog_family") or "",
        "page": int(row.get("page") or base.get("page") or 0),
        "table_id": row.get("table_id") or base.get("table_id") or "",
    }


def evidence(occ: Occurrence | None, match: dict[str, Any] | None, title: str) -> str:
    if not occ:
        return "PT code non trovato nel layout indicizzato."
    parts = [f"PT bbox={list(occ.code_box)} pagina={occ.page}"]
    if occ.model_box:
        parts.append(f"modello '{occ.model_token}' bbox={list(occ.model_box)}")
    else:
        parts.append("modello non localizzato sulla stessa riga")
    if match:
        parts.append(f"titolo '{title}' bbox={match['bbox']}; gap verticale={match['vertical_gap']}, orizzontale={match['horizontal_gap']}")
    return "; ".join(parts)


def resolve_one(issue: dict[str, str], source: dict[str, Any], index: LayoutIndex,
                page_contexts: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    code = str(issue["pt_code"])
    brand = source.get("brand") or issue.get("brand") or ""
    model = source.get("model") or issue.get("model") or ""
    current_family = source.get("catalog_family") or issue.get("current_family") or ""
    current_key = source.get("family_key") or issue.get("current_family_key") or ""
    page = int(source.get("page") or issue.get("page") or 0)
    table_id = source.get("table_id") or issue.get("table_id") or ""
    current = {"family": current_family, "key": current_key,
               "title": source.get("table_title") or current_family, "page": page, "table_id": table_id}
    occurrence = index.locate(code, model, page)
    primary_match = structural_match(index, occurrence, page, current["title"])
    model_confirmed = bool(occurrence and occurrence.model_box)
    primary_verified = bool(primary_match and model_confirmed)

    alternates = []
    for raw in context_rows(source.get("alternate_table_contexts")):
        alt = row_context(raw, source)
        alt_occ = index.locate(code, model, alt["page"])
        alt_match = structural_match(index, alt_occ, alt["page"], alt["title"])
        if alt_match and alt_occ and alt_occ.model_box:
            alternates.append((alt, alt_occ, alt_match))

    # Other catalog contexts on the physical page can expose a wrong primary title.
    page_matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if occurrence and occurrence.page == page and occurrence.model_box:
        for candidate in page_contexts.get(page, []):
            match = structural_match(index, occurrence, page, candidate["title"])
            if match:
                page_matches.append((candidate, match))
    page_matches.sort(key=lambda item: item[1]["score"])

    expected_key = family_key(brand, current_family)
    correct_family = current_family
    correct_key = current_key
    alternate_out = [{"family": alt["family"], "family_key": alt["key"], "page": alt["page"],
                      "table_id": alt["table_id"], "table_title": alt["title"],
                      "evidence": evidence(occ, match, alt["title"])}
                     for alt, occ, match in alternates]
    verdict = "AMBIGUOUS"
    action = "no_change"
    confidence = 0.55
    reason = "Il layout non collega con sufficiente certezza il PT/modello a un heading di family."
    layout = evidence(occurrence, primary_match, current["title"])

    if primary_verified and current_key != expected_key:
        verdict, action, confidence = "FIX_KEY_ONLY", "fix_family_key", 1.0
        correct_key = expected_key
        reason = "La family corrente è nel blocco geometrico corretto; solo la normalizzazione della key è errata."
    elif primary_verified:
        leaf_alts = [(alt, occ, match) for alt, occ, match in alternates if is_parent(current_family, alt["family"])]
        if len(leaf_alts) == 1:
            alt, alt_occ, alt_match = leaf_alts[0]
            verdict, action, confidence = "PROMOTE_TO_LEAF", "replace_primary_keep_parent_alternate", 1.0
            correct_family, correct_key = alt["family"], family_key(brand, alt["family"])
            reason = "Lo stesso PT/modello è localizzato direttamente sotto la leaf in una tabella catalogo separata."
            layout = evidence(alt_occ, alt_match, alt["title"])
        elif alternates:
            verdict, action, confidence = "MULTIPLE_VALID_CONTEXTS", "keep_primary_keep_valid_alternates", 0.99
            reason = "Il layout localizza il prodotto sia nel contesto primario sia in contesti alternativi distinti."
        else:
            leaves = {c["family"] for c in page_contexts.get(page, []) if is_parent(current_family, c["family"])}
            if leaves:
                verdict, action, confidence = "KEEP_PARENT", "keep_parent", 0.99
                reason = "Il prodotto è fisicamente nella tabella parent; il layout non lo colloca in una leaf specifica."
            else:
                verdict, action, confidence = "CORRECT", "keep_primary", 0.99
                reason = "PT, modello e heading della family corrente coincidono nello stesso blocco geometrico."
    else:
        # A nearby title on the same page is deliberately *not* sufficient proof:
        # pages often contain adjacent columns and sequential mini-tables. A family
        # change requires a direct second context (handled above), not proximity.
        if page_matches:
            reason = "Il PT/modello è stato trovato, ma il titolo primario non è ricostruibile con prova tabellare; i titoli vicini non sono prova sufficiente."

    safe = verdict in {"CHANGE_FAMILY", "PROMOTE_TO_LEAF", "FIX_KEY_ONLY"} and confidence >= 0.95
    if verdict == "PROMOTE_TO_LEAF":
        # The promoted leaf becomes primary. Preserve the former parent as context;
        # keeping the old leaf occurrence here would merely duplicate the primary.
        parent_context = {"family": current_family, "family_key": current_key, "page": page,
                          "table_id": table_id, "table_title": current["title"],
                          "evidence": evidence(occurrence, primary_match, current["title"])}
        alternate_out = [parent_context] + [item for item in alternate_out
                                            if item["family_key"] != correct_key]
    assert verdict in VERDICTS
    return {
        "pt_code": code, "brand": brand, "model": model, "page": page, "table_id": table_id,
        "current_family": current_family, "current_family_key": current_key,
        "audit_issue_type": issue.get("issue_type", ""), "final_verdict": verdict,
        "correct_family": correct_family, "correct_family_key": correct_key,
        "primary_context_action": action, "alternate_contexts_to_keep": alternate_out,
        "confidence": confidence, "layout_evidence": layout, "reason": reason, "safe_to_apply": safe,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=Path, default=ISSUES)
    parser.add_argument("--context", type=Path, default=CONTEXT)
    parser.add_argument("--layout", type=Path, default=LAYOUT)
    args = parser.parse_args()
    with args.issues.open("r", encoding="utf-8-sig", newline="") as handle:
        issues = list(csv.DictReader(handle))
    with args.context.open("r", encoding="utf-8") as handle:
        context: dict[str, dict[str, Any]] = json.load(handle)

    codes = {str(row["pt_code"]) for row in issues}
    relevant_pages: set[int] = set()
    page_contexts: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unique_contexts: set[tuple[int, str, str, str]] = set()
    for base in context.values():
        primary = row_context(base, base)
        if primary["page"]:
            identity = (primary["page"], primary["family"], primary["title"], primary["table_id"])
            if identity not in unique_contexts:
                unique_contexts.add(identity)
                page_contexts[primary["page"]].append(primary)
        for raw in context_rows(base.get("alternate_table_contexts")):
            alt = row_context(raw, base)
            if alt["page"]:
                identity = (alt["page"], alt["family"], alt["title"], alt["table_id"])
                if identity not in unique_contexts:
                    unique_contexts.add(identity)
                    page_contexts[alt["page"]].append(alt)
    for issue in issues:
        base = context.get(str(issue["pt_code"]), {})
        try:
            relevant_pages.add(int(base.get("page") or issue.get("page") or 0))
        except ValueError:
            pass
        for raw in context_rows(base.get("alternate_table_contexts")):
            if raw.get("page"):
                relevant_pages.add(int(raw["page"]))
    relevant_pages.discard(0)
    print(f"Indexing {len(codes):,} PT codes across {len(relevant_pages):,} pages...")
    index = LayoutIndex(codes, relevant_pages)
    index.load(args.layout)
    print(f"Indexed {sum(map(len, index.codes.values())):,} PT occurrences.")

    resolved = []
    for no, issue in enumerate(issues, 1):
        base = context.get(str(issue["pt_code"]), {})
        resolved.append(resolve_one(issue, base, index, page_contexts))
        if no % 1000 == 0:
            print(f"Resolved {no:,}/{len(issues):,}")

    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(resolved, handle, ensure_ascii=False, indent=2)
    fields = ["pt_code", "brand", "model", "page", "table_id", "current_family", "current_family_key",
              "audit_issue_type", "final_verdict", "correct_family", "correct_family_key",
              "primary_context_action", "alternate_contexts_to_keep", "confidence", "layout_evidence",
              "reason", "safe_to_apply"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in resolved:
            item = dict(row)
            item["alternate_contexts_to_keep"] = json_value(item["alternate_contexts_to_keep"])
            writer.writerow(item)

    corrections = []
    for row in resolved:
        if not row["safe_to_apply"]:
            continue
        proof = re.search(r"pagina=(\d+)", row["layout_evidence"])
        proof_page = int(proof.group(1)) if proof else row["page"]
        if row["final_verdict"] == "FIX_KEY_ONLY":
            corrections.append({"pt_code": row["pt_code"], "field": "family_key",
                                "old_value": row["current_family_key"], "new_value": row["correct_family_key"],
                                "verdict": row["final_verdict"], "confidence": row["confidence"],
                                "page": proof_page, "evidence": row["layout_evidence"]})
        else:
            corrections.append({"pt_code": row["pt_code"], "old_family": row["current_family"],
                                "new_family": row["correct_family"], "old_family_key": row["current_family_key"],
                                "new_family_key": row["correct_family_key"], "verdict": row["final_verdict"],
                                "confidence": row["confidence"], "page": proof_page,
                                "evidence": row["layout_evidence"]})
    with OUT_FIXES.open("w", encoding="utf-8") as handle:
        json.dump(corrections, handle, ensure_ascii=False, indent=2)

    verdicts = Counter(row["final_verdict"] for row in resolved)
    originals = Counter(row["audit_issue_type"] for row in resolved)
    brands = Counter(row["brand"] for row in resolved)
    stats = {
        "records_analyzed": len(resolved), "verdicts": verdicts, "safe_corrections": len(corrections),
        "original_issue_types": originals, "brands": brands,
        "generic_parent_confirmed_parent": sum(1 for row in resolved if row["audit_issue_type"] == "GENERIC_PARENT_FAMILY" and row["final_verdict"] == "KEEP_PARENT"),
        "more_specific_promoted": sum(1 for row in resolved if row["audit_issue_type"] == "MORE_SPECIFIC_FAMILY_AVAILABLE" and row["final_verdict"] == "PROMOTE_TO_LEAF"),
        "conflicting_multi_context_valid": sum(1 for row in resolved if row["audit_issue_type"] == "CONFLICTING_CONTEXTS" and row["final_verdict"] == "MULTIPLE_VALID_CONTEXTS"),
        "layout_review_resolved": sum(1 for row in resolved if row["audit_issue_type"] == "LAYOUT_REVIEW_REQUIRED" and row["final_verdict"] != "AMBIGUOUS"),
    }
    print(json.dumps(stats, ensure_ascii=False, default=dict, indent=2))


if __name__ == "__main__":
    main()
