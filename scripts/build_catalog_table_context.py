"""Build the PDF-layout table context dataset for the Puglia Termica catalog.

The family assignment is made from the title physically attached to the table
header containing each product-code row. Product names are used only to report
conflicts and never to overwrite the table-derived family.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "Knowledge" / "CAT2600_CATALOGO_2026-V4pdf.pdf"
MASTER_PATH = ROOT / "Knowledge" / "unified_catalog_master.json"
OUTPUT_PATH = ROOT / "catalog_table_context.json"
DIAGNOSTICS_PATH = ROOT / "scratch" / "table_context" / "diagnostics.json"

CODE_RE = re.compile(r"(?<!\d)(?:50|99)\d{6}(?!\d)")
SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")

HEADER_WORDS = {
    "CODICE",
    "COD.",
    "COD",
    "CODICEART.",
    "COD.ART.",
    "CODART",
}

NON_TITLE_TOKENS = {
    "CODICE",
    "MODELLO",
    "MODEL",
    "MISURA",
    "PREZZO",
    "PREZZO €",
    "PREZZO TOT €",
    "DISP",
    "GAS",
    "KW",
    "CLASSE",
    "TUBI",
    "PESO",
    "TAGLIA",
    "ACCUMULO",
    "ARTICOLO",
    "BOLLITORE LT/PERSONE",
    "DATI ELETTRICI",
    "DATI IDRAULICI",
    "DESCRIZIONE",
    "DIAMETRO",
    "LUNGHEZZA",
    "N. DESCRIZIONE",
    "PREZZO UNITÀ €",
    "PREZZO TOTALE €",
    "INDICE FOTOGRAFICO",
    "INDICE DETTAGLIATO",
    "INDICE PER MARCHIO",
}

GENERIC_NAME_TOKENS = {
    "A",
    "AD",
    "AL",
    "ALLA",
    "ALLE",
    "CON",
    "DA",
    "DEI",
    "DEL",
    "DELLA",
    "DI",
    "E",
    "F",
    "FF",
    "IL",
    "IN",
    "KIT",
    "LA",
    "LE",
    "M",
    "MF",
    "MM",
    "PER",
    "PRO",
    "R32",
    "UE",
    "UI",
}


def clean_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip(" \t\r\n-|;")


def normalized(value: str) -> str:
    return NON_ALNUM_RE.sub(" ", value.upper()).strip()


def normalized_compact(value: str) -> str:
    return NON_ALNUM_RE.sub("", value.upper())


def rect_list(rect: pymupdf.Rect, digits: int = 2) -> list[float]:
    return [round(float(v), digits) for v in rect]


def rect_overlap_x(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    overlap = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    denom = max(1.0, min(a.width, b.width))
    return overlap / denom


def rgb_is_header_gray(fill: Any) -> bool:
    if not fill or len(fill) < 3:
        return False
    r, g, b = (float(fill[0]), float(fill[1]), float(fill[2]))
    return max(r, g, b) - min(r, g, b) <= 0.08 and 0.35 <= (r + g + b) / 3 <= 0.9


@dataclass
class TextLine:
    text: str
    bbox: pymupdf.Rect
    max_size: float
    fonts: tuple[str, ...]
    flags: tuple[int, ...]
    dominant_color: int

    @property
    def center_x(self) -> float:
        return (self.bbox.x0 + self.bbox.x1) / 2


@dataclass
class TableHeader:
    word_bbox: pymupdf.Rect
    band_bbox: pymupdf.Rect
    inferred_band: bool
    title: str = ""
    title_bbox: pymupdf.Rect | None = None
    title_method: str = ""

    @property
    def key(self) -> tuple[float, float, float, float]:
        return tuple(round(float(v), 2) for v in self.band_bbox)


def load_master() -> tuple[dict[str, dict[str, Any]], dict[int, set[str]]]:
    with MASTER_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    master: dict[str, dict[str, Any]] = {}
    page_codes: dict[int, set[str]] = defaultdict(set)
    for item in raw:
        code = str(item.get("code") or "").strip()
        if not CODE_RE.fullmatch(code) or not item.get("in_catalog_pdf"):
            continue
        master[code] = item
        pages = item.get("catalog_pages") or [item.get("primary_page")]
        for page in pages:
            if isinstance(page, int) and page > 0:
                page_codes[page].add(code)
    return master, page_codes


def extract_lines(page: pymupdf.Page) -> list[TextLine]:
    result: list[TextLine] = []
    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT).get("blocks", []):
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if span.get("text")]
            if not spans:
                continue
            text = clean_text("".join(str(span.get("text") or "") for span in spans))
            if not text:
                continue
            dominant_span = max(spans, key=lambda span: len(clean_text(str(span.get("text") or ""))))
            result.append(
                TextLine(
                    text=text,
                    bbox=pymupdf.Rect(line["bbox"]),
                    max_size=max(float(span.get("size") or 0) for span in spans),
                    fonts=tuple(str(span.get("font") or "") for span in spans),
                    flags=tuple(int(span.get("flags") or 0) for span in spans),
                    dominant_color=int(dominant_span.get("color") or 0),
                )
            )
    return result


def color_is_red(color: int) -> bool:
    red = (color >> 16) & 255
    green = (color >> 8) & 255
    blue = color & 255
    return red >= 150 and red >= green * 1.35 and red >= blue * 1.35


def is_header_word(text: str) -> bool:
    token = clean_text(text).upper().replace(" ", "")
    return token in HEADER_WORDS or token.startswith("CODICE")


def containing_header_band(
    word_rect: pymupdf.Rect, drawings: list[dict[str, Any]], page_rect: pymupdf.Rect
) -> tuple[pymupdf.Rect, bool]:
    center = pymupdf.Point((word_rect.x0 + word_rect.x1) / 2, (word_rect.y0 + word_rect.y1) / 2)
    candidates: list[tuple[float, pymupdf.Rect]] = []
    for drawing in drawings:
        rect = pymupdf.Rect(drawing.get("rect") or (0, 0, 0, 0))
        if not rect.contains(center):
            continue
        if not (5.0 <= rect.height <= 18.0 and rect.width >= 70.0):
            continue
        fill = drawing.get("fill")
        gray_bonus = 0 if rgb_is_header_gray(fill) else 100000
        candidates.append((gray_bonus + rect.get_area(), rect))
    if candidates:
        return min(candidates, key=lambda pair: pair[0])[1], False

    # Fallback for headers whose background is embedded/rasterized. The inferred
    # region uses the physical page column containing the CODICE label.
    middle = page_rect.width / 2
    if word_rect.x0 < middle - 20:
        x0, x1 = 0.0, middle - 5.0
    elif word_rect.x0 > middle + 20:
        x0, x1 = middle + 5.0, page_rect.width
    else:
        x0, x1 = 0.0, page_rect.width
    return pymupdf.Rect(x0, word_rect.y0 - 1.0, x1, word_rect.y1 + 1.0), True


def title_candidate(line: TextLine, band: pymupdf.Rect) -> bool:
    if line.bbox.y1 > band.y0 + 0.8:
        return False
    if line.bbox.x1 < band.x0 - 15 or line.bbox.x0 > band.x1 + 15:
        return False
    upper = clean_text(line.text).upper()
    if not upper or upper.isdigit() or upper in NON_TITLE_TOKENS:
        return False
    if upper.startswith("INDICE ") or CODE_RE.search(upper):
        return False
    if color_is_red(line.dominant_color):
        return False
    has_catalog_title_font = any("U.S.101" in font.upper() for font in line.fonts)
    if has_catalog_title_font and line.max_size >= 5.2:
        return True
    # Fallbacks for brand-specific sections that use a different condensed font.
    if line.max_size >= 12.0 and len(upper) <= 120:
        return True
    return line.max_size >= 8.1 and any(flag & 16 for flag in line.flags) and len(upper) <= 120


def attach_title(header: TableHeader, lines: list[TextLine]) -> None:
    candidates = [line for line in lines if title_candidate(line, header.band_bbox)]
    if not candidates:
        return
    chosen = min(candidates, key=lambda line: header.band_bbox.y0 - line.bbox.y1)
    group = [chosen]
    current = chosen
    for prior in sorted((line for line in candidates if line.bbox.y0 < current.bbox.y0), key=lambda line: line.bbox.y0, reverse=True):
        vertical_gap = current.bbox.y0 - prior.bbox.y1
        if vertical_gap > 2.5:
            break
        if abs(prior.max_size - chosen.max_size) > 0.8:
            break
        if rect_overlap_x(prior.bbox, chosen.bbox) < 0.15 and abs(prior.bbox.x0 - chosen.bbox.x0) > 8:
            break
        group.insert(0, prior)
        current = prior

    title = clean_text(" ".join(line.text for line in group))
    if title.upper() in NON_TITLE_TOKENS:
        return
    title_rect = pymupdf.Rect(group[0].bbox)
    for line in group[1:]:
        title_rect.include_rect(line.bbox)
    header.title = title
    header.title_bbox = title_rect
    header.title_method = "CATALOG_TITLE_FONT" if any(
        "U.S.101" in font.upper() for line in group for font in line.fonts
    ) else "BOLD_TITLE_FALLBACK"


def attach_spare_parts_banner(header: TableHeader, lines: list[TextLine]) -> None:
    candidates = [
        line
        for line in lines
        if line.bbox.y1 <= header.band_bbox.y0 + 0.8
        and line.max_size >= 10.0
        and normalized(line.text).startswith("RICAMBI")
    ]
    if not candidates:
        return
    chosen = min(candidates, key=lambda line: header.band_bbox.y0 - line.bbox.y1)
    header.title = clean_text(chosen.text)
    header.title_bbox = pymupdf.Rect(chosen.bbox)
    header.title_method = "CATALOG_TITLE_FONT"


def page_section_title(lines: list[TextLine]) -> str:
    candidates = []
    for line in lines:
        if line.bbox.y0 > 42 or line.max_size < 11:
            continue
        text = clean_text(line.text)
        upper = text.upper()
        if not text or upper.isdigit() or upper.startswith("INDICE "):
            continue
        score = line.max_size * 100 + len(text)
        candidates.append((score, text))
    return max(candidates, default=(0, ""), key=lambda pair: pair[0])[1]


def header_words_on_band(words: list[tuple], header: TableHeader) -> list[tuple]:
    band = header.band_bbox
    result = []
    for word in words:
        rect = pymupdf.Rect(word[:4])
        cy = (rect.y0 + rect.y1) / 2
        if band.x0 - 2 <= (rect.x0 + rect.x1) / 2 <= band.x1 + 2 and band.y0 - 2 <= cy <= band.y1 + 2:
            result.append(word)
    return sorted(result, key=lambda word: word[0])


def row_words_for_code(words: list[tuple], code_rect: pymupdf.Rect, band: pymupdf.Rect) -> list[tuple]:
    center_y = (code_rect.y0 + code_rect.y1) / 2
    result = []
    for word in words:
        rect = pymupdf.Rect(word[:4])
        word_center_y = (rect.y0 + rect.y1) / 2
        vertical_overlap = max(0.0, min(rect.y1, code_rect.y1) - max(rect.y0, code_rect.y0))
        if not (abs(word_center_y - center_y) <= 4.2 or vertical_overlap >= min(rect.height, code_rect.height) * 0.45):
            continue
        if band.x0 - 2 <= (rect.x0 + rect.x1) / 2 <= band.x1 + 2:
            result.append(word)
    return sorted(result, key=lambda word: word[0])


def model_from_row(row_words: list[tuple], header_words: list[tuple], code_rect: pymupdf.Rect, band: pymupdf.Rect) -> str:
    labels = []
    for word in header_words:
        token = normalized(str(word[4]))
        if token in {"MODELLO", "MODEL", "DESCRIZIONE", "ARTICOLO", "TIPO"}:
            rect = pymupdf.Rect(word[:4])
            labels.append(((rect.x0 + rect.x1) / 2, token))
    if not labels:
        return ""

    code_center = (code_rect.x0 + code_rect.x1) / 2
    model_center, _ = min(labels, key=lambda pair: abs(pair[0] - code_center))
    all_centers = sorted(
        ((pymupdf.Rect(word[:4]).x0 + pymupdf.Rect(word[:4]).x1) / 2 for word in header_words)
    )
    left_neighbors = [center for center in all_centers if center < model_center - 1]
    right_neighbors = [center for center in all_centers if center > model_center + 1]
    left = (max(left_neighbors) + model_center) / 2 if left_neighbors else band.x0
    right = (min(right_neighbors) + model_center) / 2 if right_neighbors else band.x1

    selected = []
    for word in row_words:
        rect = pymupdf.Rect(word[:4])
        center = (rect.x0 + rect.x1) / 2
        if left <= center <= right and not CODE_RE.search(clean_text(str(word[4]))):
            selected.append(str(word[4]))
    return clean_text(" ".join(selected))


def mpn_if_present(mfg_code: str, row_text: str, model_text: str) -> str:
    mfg_code = clean_text(mfg_code)
    if not mfg_code:
        return ""
    needle = normalized_compact(mfg_code)
    haystack = normalized_compact(f"{row_text} {model_text}")
    if len(needle) >= 4 and needle in haystack:
        return mfg_code
    return ""


def confidence_for(header: TableHeader) -> float:
    if header.title_method == "CATALOG_TITLE_FONT" and not header.inferred_band:
        return 1.0
    if header.title_method == "CATALOG_TITLE_FONT":
        return 0.97
    if header.title_method == "BOLD_TITLE_FALLBACK" and not header.inferred_band:
        return 0.94
    if header.title_method == "SECTION_TITLE_FALLBACK" and not header.inferred_band:
        return 0.88
    if header.title:
        return 0.88
    if not header.inferred_band:
        return 0.65
    return 0.4


def find_headers(page: pymupdf.Page, words: list[tuple], lines: list[TextLine]) -> list[TableHeader]:
    drawings = page.get_drawings()
    headers: list[TableHeader] = []
    seen = set()
    for word in words:
        if not is_header_word(str(word[4])):
            continue
        word_rect = pymupdf.Rect(word[:4])
        band, inferred = containing_header_band(word_rect, drawings, page.rect)
        key = (round(band.x0, 2), round(band.y0, 2), round(word_rect.x0, 2))
        if key in seen:
            continue
        seen.add(key)
        header = TableHeader(word_bbox=word_rect, band_bbox=band, inferred_band=inferred)
        attach_title(header, lines)
        headers.append(header)
    return headers


def choose_header(code_rect: pymupdf.Rect, headers: list[TableHeader]) -> TableHeader | None:
    code_center_x = (code_rect.x0 + code_rect.x1) / 2
    candidates = []
    for header in headers:
        if header.band_bbox.y0 > code_rect.y0 + 1:
            continue
        if not (header.band_bbox.x0 - 2 <= code_center_x <= header.band_bbox.x1 + 2):
            continue
        x_delta = abs(code_rect.x0 - header.word_bbox.x0)
        # PT codes occupy the column headed by CODICE; this alignment guards
        # against codes mentioned later in descriptions or footnotes.
        if x_delta > 48:
            continue
        y_delta = code_rect.y0 - header.band_bbox.y1
        candidates.append((y_delta, x_delta, header))
    return min(candidates, default=(math.inf, math.inf, None), key=lambda item: (item[0], item[1]))[2]


def extract_occurrences(
    master: dict[str, dict[str, Any]], page_codes: dict[int, set[str]], pages: set[int] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    doc = pymupdf.open(PDF_PATH)
    occurrences: list[dict[str, Any]] = []
    stats = Counter()
    missing_on_expected_page: dict[str, list[int]] = defaultdict(list)

    target_pages = sorted(pages or set(page_codes))
    for index, page_num in enumerate(target_pages, start=1):
        if not (1 <= page_num <= len(doc)):
            continue
        page = doc[page_num - 1]
        words = page.get_text("words", flags=pymupdf.TEXTFLAGS_TEXT, sort=False)
        lines = extract_lines(page)
        headers = find_headers(page, words, lines)
        section = page_section_title(lines)
        if normalized(section).startswith("RICAMBI"):
            for header in headers:
                attach_spare_parts_banner(header, lines)
        for header in headers:
            if not header.title and section:
                header.title = section
                header.title_method = "SECTION_TITLE_FALLBACK"
                matching_section_lines = [line for line in lines if clean_text(line.text) == section]
                if matching_section_lines:
                    header.title_bbox = pymupdf.Rect(matching_section_lines[0].bbox)
        page_occurrence_codes: set[str] = set()
        header_word_cache = {header.key: header_words_on_band(words, header) for header in headers}

        for word in words:
            token = clean_text(str(word[4]))
            code_matches = [match.group(0) for match in CODE_RE.finditer(token) if match.group(0) in master]
            if not code_matches:
                continue
            code_rect = pymupdf.Rect(word[:4])
            header = choose_header(code_rect, headers)
            if header is None:
                stats["unassigned_occurrences"] += len(code_matches)
                continue

            row_words = row_words_for_code(words, code_rect, header.band_bbox)
            row_text = clean_text(" ".join(str(item[4]) for item in row_words))
            header_row_words = header_word_cache[header.key]
            model_pdf = model_from_row(row_words, header_row_words, code_rect, header.band_bbox)
            for code in code_matches:
                item = master[code]
                mpn = mpn_if_present(str(item.get("mfg_code") or ""), row_text, model_pdf)
                model = model_pdf or mpn or clean_text(str(item.get("name") or ""))
                confidence = confidence_for(header)
                family = clean_text(header.title).upper()

                occurrences.append(
                    {
                        "code": code,
                        "page": page_num,
                        "table_family": family,
                        "table_series": family,
                        "table_title": clean_text(header.title),
                        "section_title": section,
                        "source": "PDF_LAYOUT",
                        "confidence": confidence,
                        "model": model,
                        "mpn": mpn,
                        "product_name": clean_text(str(item.get("name") or "")),
                        "table_bbox": rect_list(header.band_bbox),
                        "title_bbox": rect_list(header.title_bbox) if header.title_bbox else [],
                        "code_bbox": rect_list(code_rect),
                        "row_text": row_text,
                        "layout_method": (
                            "HEADER_BAND+BBOX+CATALOG_TITLE_FONT"
                            if not header.inferred_band and header.title_method == "CATALOG_TITLE_FONT"
                            else f"{'INFERRED_HEADER' if header.inferred_band else 'HEADER_BAND'}+BBOX+{header.title_method or 'NO_TITLE'}"
                        ),
                    }
                )
                page_occurrence_codes.add(code)
                stats["assigned_occurrences"] += 1
                if family:
                    stats["assigned_with_title"] += 1
                if header.inferred_band:
                    stats["inferred_header_occurrences"] += 1

        expected = page_codes.get(page_num, set())
        for code in expected - page_occurrence_codes:
            missing_on_expected_page[code].append(page_num)

        if index % 100 == 0 or index == len(target_pages):
            print(
                f"Processed {index}/{len(target_pages)} catalog pages; "
                f"assigned occurrences: {stats['assigned_occurrences']}",
                flush=True,
            )

    diagnostics = {
        "pdf_pages": len(doc),
        "target_pages": len(target_pages),
        "master_codes_in_pdf": len(master),
        "stats": dict(stats),
        "missing_expected_codes": len(missing_on_expected_page),
        "missing_expected_sample": dict(list(sorted(missing_on_expected_page.items()))[:100]),
    }
    return occurrences, diagnostics


def compact_family_candidate(value: str) -> bool:
    norm = normalized(value)
    tokens = norm.split()
    if not (1 <= len(tokens) <= 8 and 4 <= len(norm) <= 70):
        return False
    distinctive = [token for token in tokens if token not in GENERIC_NAME_TOKENS and len(token) >= 3]
    return bool(distinctive)


def detect_family_conflict(record: dict[str, Any], page_families: dict[int, set[str]]) -> bool | dict[str, str]:
    product_name = normalized(record.get("product_name") or "")
    assigned = normalized(record.get("table_family") or "")
    if not product_name or not assigned or assigned in product_name:
        return False

    matches = []
    for family in page_families.get(int(record["page"]), set()):
        candidate = normalized(family)
        if candidate == assigned or not compact_family_candidate(candidate):
            continue
        if candidate in product_name:
            matches.append(candidate)
    if not matches:
        return False
    detected = max(matches, key=len)
    return {
        "name_detected": detected,
        "table_detected": record["table_family"],
        "reason": "La famiglia rilevata nel nome differisce dal titolo della tabella PDF; il dato tabellare non è stato modificato.",
    }


def choose_canonical_occurrence(items: list[dict[str, Any]], master_item: dict[str, Any]) -> dict[str, Any]:
    primary_page = master_item.get("primary_page")

    def score(item: dict[str, Any]) -> tuple[float, float, float, float]:
        return (
            1.0 if item["page"] == primary_page else 0.0,
            float(item["confidence"]),
            1.0 if item["table_family"] else 0.0,
            -float(item["page"]),
        )

    return max(items, key=score)


def build_dataset(
    occurrences: list[dict[str, Any]], master: dict[str, dict[str, Any]], diagnostics: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    page_families: dict[int, set[str]] = defaultdict(set)
    for item in occurrences:
        by_code[item["code"]].append(item)
        if item["table_family"]:
            page_families[int(item["page"])].add(item["table_family"])

    dataset: dict[str, dict[str, Any]] = {}
    validation_rows: list[dict[str, Any]] = []
    multiple_distinct = 0
    for code, items in sorted(by_code.items()):
        canonical = choose_canonical_occurrence(items, master[code])
        family_conflict = detect_family_conflict(canonical, page_families)
        distinct_origins = sorted(
            {
                (int(item["page"]), item["table_family"], item["table_title"], tuple(item["table_bbox"]))
                for item in items
                if item["table_family"]
            }
        )
        if len({origin[1] for origin in distinct_origins}) > 1:
            multiple_distinct += 1

        entry: dict[str, Any] = {
            "table_family": canonical["table_family"],
            "table_series": canonical["table_series"],
            "page": canonical["page"],
            "table_title": canonical["table_title"],
            "section_title": canonical["section_title"],
            "source": "PDF_LAYOUT",
            "confidence": canonical["confidence"],
            "model": canonical["model"],
            "mpn": canonical["mpn"],
            "family_conflict": family_conflict,
            "layout_evidence": {
                "table_bbox": canonical["table_bbox"],
                "title_bbox": canonical["title_bbox"],
                "code_bbox": canonical["code_bbox"],
                "method": canonical["layout_method"],
            },
        }
        if len(distinct_origins) > 1:
            entry["alternate_table_contexts"] = [
                {
                    "page": page,
                    "table_family": family,
                    "table_title": title,
                    "table_bbox": list(bbox),
                }
                for page, family, title, bbox in distinct_origins
                if not (
                    page == canonical["page"]
                    and family == canonical["table_family"]
                    and title == canonical["table_title"]
                    and list(bbox) == canonical["table_bbox"]
                )
            ]
        dataset[code] = entry

        for occurrence in items:
            row_conflict = detect_family_conflict(occurrence, page_families)
            validation_rows.append(
                {
                    "page": occurrence["page"],
                    "table_title": occurrence["table_title"],
                    "code": code,
                    "model": occurrence["model"],
                    "family": occurrence["table_family"],
                    "mpn": occurrence["mpn"],
                    "confidence": occurrence["confidence"],
                    "conflict": row_conflict,
                    "canonical": occurrence is canonical,
                    "table_bbox": occurrence["table_bbox"],
                    "title_bbox": occurrence["title_bbox"],
                    "code_bbox": occurrence["code_bbox"],
                    "layout_method": occurrence["layout_method"],
                }
            )

    diagnostics["unique_codes_assigned"] = len(dataset)
    diagnostics["unique_codes_unassigned"] = len(master) - len(dataset)
    diagnostics["codes_with_multiple_distinct_families"] = multiple_distinct
    diagnostics["confidence_counts"] = dict(Counter(str(item["confidence"]) for item in dataset.values()))
    diagnostics["blank_family_codes"] = sum(not item["table_family"] for item in dataset.values())
    diagnostics["family_conflict_codes"] = sum(item["family_conflict"] is not False for item in dataset.values())
    return dataset, validation_rows


def parse_pages(raw: str) -> set[int] | None:
    if not raw:
        return None
    pages: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(value) for value in part.split("-", 1))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    return pages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", default="", help="Optional comma-separated PDF page numbers or ranges")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--validation-json", type=Path, default=ROOT / "scratch" / "table_context" / "validation_rows.json")
    args = parser.parse_args()

    if not PDF_PATH.exists() or not MASTER_PATH.exists():
        raise FileNotFoundError("Catalog PDF or unified catalog master not found")

    master, page_codes = load_master()
    selected_pages = parse_pages(args.pages)
    occurrences, diagnostics = extract_occurrences(master, page_codes, selected_pages)
    dataset, validation_rows = build_dataset(occurrences, master, diagnostics)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.validation_json.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with args.validation_json.open("w", encoding="utf-8") as handle:
        json.dump(validation_rows, handle, ensure_ascii=False)
    with DIAGNOSTICS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
