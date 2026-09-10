"""Strict graphical-origin audit for catalog annotations.

This is intentionally a read-only audit of the catalog inputs.  It writes only
the two audit reports requested by the task.  In particular, it does not alter
the annotation dataset, component relations, table context, matcher, BOM, or
retrieval code/data.

The original extractor selected a complete PDF *line* if any span was red or
if a commercial-keyword heuristic matched.  An annotation can therefore be a
black clause from a mixed-colour line.  This audit maps each annotation back to
the exact source span(s) which overlap its raw text before deciding its origin.
"""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
RELATIONS_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
ORIGIN_REPORT_PATH = ROOT / "catalog_annotations_origin_audit.json"
SAFETY_REPORT_PATH = ROOT / "catalog_annotations_component_safety_report.json"

ORIGIN_VALUES = ("RED_TEXT_CONFIRMED", "NON_RED_TEXT", "UNKNOWN")
COMPONENT_TYPES = {
    "COMPONENT_INCLUDED",
    "COMPONENT_EXCLUDED",
    "COMPONENT_REQUIRED",
    "COMPONENT_OPTIONAL",
    "FEATURE_INCLUDED",
}


def normalize_text(text: str) -> str:
    """Normalise only for matching; source text is retained verbatim in reports."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("`", "'")
    return " ".join(text.casefold().split())


def rgb_from_hex(color: Any) -> list[int] | None:
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return None
    return [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)]


def is_original_filter_red(color: Any) -> bool:
    """The exact red predicate from extract_catalog_annotations.py."""
    rgb = rgb_from_hex(color)
    if rgb is None:
        return False
    red, green, blue = rgb
    return red >= 150 and red > green * 1.35 and red > blue * 1.35


def bbox_list(value: Any) -> list[float]:
    if isinstance(value, dict):
        return [
            float(value.get("x0", 0)),
            float(value.get("y0", 0)),
            float(value.get("x1", 0)),
            float(value.get("y1", 0)),
        ]
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [float(v) for v in value]
    return [0.0, 0.0, 0.0, 0.0]


def annotation_bbox_dict(value: Any) -> dict[str, float]:
    box = bbox_list(value)
    return {"x0": round(box[0], 2), "y0": round(box[1], 2), "x1": round(box[2], 2), "y1": round(box[3], 2)}


def rounded_bbox_key(value: Any) -> tuple[float, float, float, float]:
    return tuple(round(v, 2) for v in bbox_list(value))  # type: ignore[return-value]


def bbox_distance(a: Any, b: Any) -> float:
    aa, bb = bbox_list(a), bbox_list(b)
    return sum(abs(x - y) for x, y in zip(aa, bb))


def bbox_union(boxes: Iterable[Any]) -> list[float]:
    values = [bbox_list(box) for box in boxes]
    if not values:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        min(box[0] for box in values),
        min(box[1] for box in values),
        max(box[2] for box in values),
        max(box[3] for box in values),
    ]


def bbox_center_y(value: Any) -> float:
    box = bbox_list(value)
    return (box[1] + box[3]) / 2


def serialise_bbox(value: Any) -> list[float]:
    return [round(v, 2) for v in bbox_list(value)]


def build_page_lines(page_data: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for block in page_data.get("blocks", []):
        for line in block.get("lines", []):
            spans = list(line.get("spans") or [])
            joined = "".join(str(span.get("text") or "") for span in spans)
            lines.append(
                {
                    "bbox": bbox_list(line.get("bbox")),
                    "spans": spans,
                    "joined_text": joined,
                    "text": joined.strip(),
                    "norm_text": normalize_text(joined),
                }
            )
    return lines


def text_match_rank(annotation_text: str, source_text: str) -> int | None:
    target = normalize_text(annotation_text)
    source = normalize_text(source_text)
    if not target or not source:
        return None
    if target == source:
        return 0
    if target in source:
        return 1
    # This is allowed only alongside very-close geometry and handles a source
    # line clipped differently by the PDF text extractor.
    if len(source) >= 5 and source in target:
        return 2
    return None


def match_standard_line(
    annotation: dict[str, Any],
    page_lines: list[dict[str, Any]],
    bbox_index: dict[tuple[float, float, float, float], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str] | None:
    """Locate a normal extractor record using its original rounded line bbox."""
    target_text = str(annotation.get("raw_text") or "")
    target_box = annotation_bbox_dict(annotation.get("bbox"))
    candidates = bbox_index.get(rounded_bbox_key(target_box), [])
    ranked: list[tuple[int, float, dict[str, Any]]] = []
    for line in candidates:
        rank = text_match_rank(target_text, line["text"])
        if rank is not None:
            ranked.append((rank, bbox_distance(target_box, line["bbox"]), line))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [ranked[0][2]], "PAGE_BBOX_AND_TEXT"

    # Rounding or a source-side precision variation can leave a tiny mismatch.
    # Do not use generic page-text matching: an uncertain source must remain
    # UNKNOWN rather than inheriting colour from a nearby line.
    ranked = []
    for line in page_lines:
        distance = bbox_distance(target_box, line["bbox"])
        if distance > 0.25:
            continue
        rank = text_match_rank(target_text, line["text"])
        if rank is not None:
            ranked.append((rank, distance, line))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [ranked[0][2]], "PAGE_NEAR_BBOX_AND_TEXT"
    return None


OPTIONAL_RE = re.compile(r"^(?P<component>.+?)\s+\(?optional\)?$", re.IGNORECASE)


def match_synthesised_optional_row(
    annotation: dict[str, Any], page_lines: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str] | None:
    """Recover the two real source lines used by the extractor's optional-row synthesis."""
    raw_text = str(annotation.get("raw_text") or "").strip()
    match = OPTIONAL_RE.match(raw_text)
    if not match:
        return None
    component_text = normalize_text(match.group("component"))
    if not component_text:
        return None
    target_box = annotation_bbox_dict(annotation.get("bbox"))

    component_lines = [
        line for line in page_lines if normalize_text(line["text"]) == component_text
    ]
    optional_lines = [
        line
        for line in page_lines
        if normalize_text(line["text"]) in {"optional", "opzionale"}
    ]
    candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for component_line in component_lines:
        for optional_line in optional_lines:
            if component_line is optional_line:
                continue
            if abs(bbox_center_y(component_line["bbox"]) - bbox_center_y(optional_line["bbox"])) > 6.1:
                continue
            union = bbox_union([component_line["bbox"], optional_line["bbox"]])
            error = bbox_distance(target_box, union)
            if error <= 0.65:
                candidates.append((error, component_line, optional_line))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    _, component_line, optional_line = candidates[0]
    return [component_line, optional_line], "SYNTHESIZED_OPTIONAL_ROW"


def find_text_ranges(joined_text: str, target_text: str) -> list[tuple[int, int]]:
    """Find exact/case-insensitive source ranges; extraction normally preserves text exactly."""
    if not target_text:
        return []
    ranges: list[tuple[int, int]] = []
    start = 0
    while True:
        index = joined_text.find(target_text, start)
        if index < 0:
            break
        ranges.append((index, index + len(target_text)))
        start = index + max(1, len(target_text))
    if ranges:
        return ranges

    # Curly punctuation/case differences can occur in hand-built combinations;
    # preserve source positions with a regex rather than colouring an entire line.
    try:
        pattern = re.compile(re.escape(target_text), re.IGNORECASE)
        ranges = [(match.start(), match.end()) for match in pattern.finditer(joined_text)]
    except re.error:
        ranges = []
    return ranges


def span_metadata(span: dict[str, Any], matched_text: str, source_line_bbox: Any) -> dict[str, Any]:
    color = span.get("color")
    return {
        "matched_text": matched_text,
        "span_text": str(span.get("text") or ""),
        "color_hex": color,
        "rgb": rgb_from_hex(color),
        "fill": span.get("fill"),
        "stroke": span.get("stroke"),
        "font": span.get("font"),
        "size_pt": span.get("size_pt"),
        "bold": bool(span.get("bold", False)),
        "italic": bool(span.get("italic", False)),
        "bbox": serialise_bbox(span.get("bbox")),
        "source_line_bbox": serialise_bbox(source_line_bbox),
        "source": span.get("source"),
    }


def spans_for_source_text(line: dict[str, Any], source_text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Return exactly the non-blank source spans overlapping source_text."""
    joined = line["joined_text"]
    ranges = find_text_ranges(joined, source_text)
    if not ranges:
        return [], "RAW_TEXT_NOT_FOUND_IN_MATCHED_LAYOUT_LINE"

    span_offsets: list[tuple[int, int, dict[str, Any]]] = []
    cursor = 0
    for span in line["spans"]:
        text = str(span.get("text") or "")
        span_offsets.append((cursor, cursor + len(text), span))
        cursor += len(text)

    candidate_sets: list[list[dict[str, Any]]] = []
    for begin, end in ranges:
        records: list[dict[str, Any]] = []
        for span_begin, span_end, span in span_offsets:
            overlap_begin = max(begin, span_begin)
            overlap_end = min(end, span_end)
            if overlap_begin >= overlap_end:
                continue
            matched = joined[overlap_begin:overlap_end]
            if not matched.strip():
                continue
            records.append(span_metadata(span, matched, line["bbox"]))
        if records:
            candidate_sets.append(records)

    if not candidate_sets:
        return [], "RAW_TEXT_MATCHED_BUT_NO_TEXTUAL_SOURCE_SPAN"

    # A repeated target phrase with different graphic attributes cannot be
    # assigned to one occurrence with certainty.  Report it as UNKNOWN.
    fingerprints = {
        tuple(
            (item["color_hex"], item["font"], item["size_pt"], item["bold"], item["italic"])
            for item in records
        )
        for records in candidate_sets
    }
    if len(fingerprints) > 1:
        return [], "REPEATED_RAW_TEXT_WITH_DIFFERENT_GRAPHIC_ATTRIBUTES"
    return candidate_sets[0], None


def graphics_for_match(
    source_lines: list[dict[str, Any]], annotation_text: str, match_method: str
) -> tuple[list[dict[str, Any]], str | None]:
    if match_method == "SYNTHESIZED_OPTIONAL_ROW":
        # The extractor explicitly constructed "<component line> optional".
        # Associate all non-whitespace spans from its two known source lines.
        fragments = [
            span_metadata(span, str(span.get("text") or ""), line["bbox"])
            for line in source_lines
            for span in line["spans"]
            if str(span.get("text") or "").strip()
        ]
        return fragments, None if fragments else "OPTIONAL_ROW_HAS_NO_TEXTUAL_SOURCE_SPANS"

    if len(source_lines) != 1:
        return [], "UNEXPECTED_SOURCE_LINE_CARDINALITY"
    return spans_for_source_text(source_lines[0], annotation_text)


def compact_colors(fragments: list[dict[str, Any]]) -> list[Any]:
    colors: list[Any] = []
    for fragment in fragments:
        color = fragment.get("color_hex")
        if color not in colors:
            colors.append(color)
    return colors


def primary_color_label(colors: list[Any]) -> Any:
    if not colors:
        return None
    if len(colors) == 1:
        return colors[0]
    return ", ".join(str(color) if color is not None else "MISSING" for color in colors)


def classify_non_red_context(annotation: dict[str, Any], colors: list[Any], match_method: str) -> str:
    text = str(annotation.get("raw_text") or "").casefold()
    if match_method == "SYNTHESIZED_OPTIONAL_ROW":
        return "NOTA_DI_RIGA_TABELLA_SINTETIZZATA_NON_ROSSA"
    if "#FFFFFF" in colors:
        return "TESTO_BIANCO_DI_TABELLA_O_INTESTAZIONE_NON_ROSSO"
    if any(word in text for word in ("confezione", "scatola", "rotolo", "vendita")):
        return "TESTO_NERO_DI_TABELLA_O_DESCRIZIONE_COMMERCIALE"
    if any(word in text for word in ("inclus", "esclus", "privo di", "completa di", "dotata di", "di serie", "optional")):
        return "TESTO_EDITORIALE_DI_CORPO_CON_PAROLA_CHIAVE_COMMERCIALE"
    return "TESTO_EDITORIALE_O_DI_TABELLA_NON_ROSSO"


def classify_origin(
    fragments: list[dict[str, Any]], annotation: dict[str, Any], match_method: str, alignment_error: str | None
) -> tuple[str, str]:
    if alignment_error:
        return "UNKNOWN", alignment_error
    if not fragments:
        return "UNKNOWN", "NESSUN_METADATO_GRAFICO_TESTUALE_RECUPERATO"
    colors = compact_colors(fragments)
    if any(rgb_from_hex(color) is None for color in colors):
        return "UNKNOWN", "COLORE_DELLO_SPAN_ASSENTE_O_NON_VALIDO_NEL_LAYOUT"
    if all(is_original_filter_red(color) for color in colors):
        return (
            "RED_TEXT_CONFIRMED",
            "TUTTI_GLISPAN_TESTUALI_ASSOCIATI_SONO_ROSSI_SECONDO_IL_FILTRO_ORIGINALE",
        )
    if any(is_original_filter_red(color) for color in colors):
        return (
            "NON_RED_TEXT",
            "TESTO_A_COLORI_MISTI_CON_ALMENO_UNO_SPAN_NON_ROSSO; NON_E_ESCLUSIVAMENTE_TESTO_ROSSO",
        )
    return (
        "NON_RED_TEXT",
        f"{classify_non_red_context(annotation, colors, match_method)}; COLORI_SORGENTE={primary_color_label(colors)}",
    )


def audit_annotation(
    annotation: dict[str, Any],
    page_lines: list[dict[str, Any]],
    bbox_index: dict[tuple[float, float, float, float], list[dict[str, Any]]],
) -> dict[str, Any]:
    matched = match_standard_line(annotation, page_lines, bbox_index)
    if matched is None:
        matched = match_synthesised_optional_row(annotation, page_lines)

    if matched is None:
        source_lines: list[dict[str, Any]] = []
        match_method = "NOT_MATCHED"
        fragments: list[dict[str, Any]] = []
        alignment_error = "SPAN_NON_LOCALIZZATO_CON_SUFFICIENTE_CERTEZZA_NEL_LAYOUT"
    else:
        source_lines, match_method = matched
        fragments, alignment_error = graphics_for_match(
            source_lines, str(annotation.get("raw_text") or ""), match_method
        )

    origin_check, reason = classify_origin(fragments, annotation, match_method, alignment_error)
    colors = compact_colors(fragments)
    source_line_bboxes = [serialise_bbox(line["bbox"]) for line in source_lines]
    source_line_text = [line["text"] for line in source_lines]
    fonts = list(dict.fromkeys(fragment.get("font") for fragment in fragments))
    sizes = list(dict.fromkeys(fragment.get("size_pt") for fragment in fragments))
    bold_values = list(dict.fromkeys(bool(fragment.get("bold", False)) for fragment in fragments))
    italic_values = list(dict.fromkeys(bool(fragment.get("italic", False)) for fragment in fragments))

    return {
        "annotation_id": annotation.get("annotation_id"),
        "page": int(annotation.get("page") or 0),
        "table_id": annotation.get("table_id"),
        "table_title": annotation.get("table_title"),
        "raw_text": annotation.get("raw_text"),
        "annotation_type": annotation.get("annotation_type"),
        "origin_check": origin_check,
        "colore_trovato": primary_color_label(colors),
        "colori_trovati": colors,
        "rgb_trovati": [rgb_from_hex(color) for color in colors],
        "font": fonts[0] if len(fonts) == 1 else fonts,
        "size_pt": sizes[0] if len(sizes) == 1 else sizes,
        "bold": bold_values[0] if len(bold_values) == 1 else bold_values,
        "italic": italic_values[0] if len(italic_values) == 1 else italic_values,
        "bbox": annotation_bbox_dict(annotation.get("bbox")),
        "layout_match": {
            "method": match_method,
            "source_line_bboxes": source_line_bboxes,
            "source_line_text": source_line_text,
            "graphic_fields_available": {
                "color": True,
                "fill": False,
                "stroke": False,
            },
            "source_spans": fragments,
        },
        "motivo_classificazione": reason,
    }


def make_suspicious_record(record: dict[str, Any]) -> dict[str, Any]:
    """The requested all-NON_RED ledger, retaining enough evidence to review it."""
    return {
        "annotation_id": record["annotation_id"],
        "page": record["page"],
        "table_id": record["table_id"],
        "raw_text": record["raw_text"],
        "annotation_type": record["annotation_type"],
        "colore_trovato": record["colore_trovato"],
        "rgb_trovati": record["rgb_trovati"],
        "font": record["font"],
        "size_pt": record["size_pt"],
        "bold": record["bold"],
        "italic": record["italic"],
        "bbox": record["bbox"],
        "layout_match_method": record["layout_match"]["method"],
        "source_line_bboxes": record["layout_match"]["source_line_bboxes"],
        "motivo_classificazione": record["motivo_classificazione"],
    }


def find_examples(records: list[dict[str, Any]]) -> dict[str, Any]:
    def select(predicate: Any) -> list[dict[str, Any]]:
        return [record for record in records if predicate(str(record.get("raw_text") or "").casefold())]

    telecomando = select(lambda text: normalize_text(text) == "telecomando incluso")
    pompa = select(lambda text: "completa di pompa scarico condensa" in normalize_text(text))
    conforme = select(lambda text: "conforme alla normativa" in normalize_text(text) and ("en501" in text or "en 501" in text))
    wifi = select(lambda text: ("wifi" in text or "wi-fi" in text) and "optional" in text)
    tranne = select(lambda text: "tranne che su taglie 2.5kw e 3.5kw" in normalize_text(text))
    guanti = select(lambda text: "confezione 50 guanti 100% lattice naturale" in normalize_text(text))
    fiamma = select(lambda text: "ideale per calore da fiamma" in normalize_text(text))

    def brief(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "annotation_id": item["annotation_id"],
                "page": item["page"],
                "raw_text": item["raw_text"],
                "annotation_type": item["annotation_type"],
                "origin_check": item["origin_check"],
                "colore_trovato": item["colore_trovato"],
                "bbox": item["bbox"],
                "motivo_classificazione": item["motivo_classificazione"],
            }
            for item in items
        ]

    def distribution(items: list[dict[str, Any]]) -> dict[str, int]:
        count = Counter(item["origin_check"] for item in items)
        return {origin: count[origin] for origin in ORIGIN_VALUES}

    return {
        "telecomando_incluso": {
            "phrase": "Telecomando incluso",
            "occurrence_count": len(telecomando),
            "origin_distribution": distribution(telecomando),
            "conclusion": (
                "La frase non ha un'unica origine: solo le singole occorrenze con tutti gli span rossi "
                "sono RED_TEXT_CONFIRMED; le occorrenze nere restano NON_RED_TEXT e non sono sicure."
            ),
            "records": brief(telecomando),
        },
        "completa_di_pompa_scarico_condensa": {
            "phrase": "Completa di pompa scarico condensa",
            "occurrence_count": len(pompa),
            "origin_distribution": distribution(pompa),
            "conclusion": (
                "Sono RED_TEXT_CONFIRMED soltanto le occorrenze con colore rosso sorgente; "
                "le copie in nero sono NON_RED_TEXT e non sicure per relazioni automatiche."
            ),
            "records": brief(pompa),
        },
        "conforme_alla_normativa_en501_16": {
            "phrase": "Conforme alla normativa EN501/16",
            "occurrence_count": len(conforme),
            "origin_distribution": distribution(conforme),
            "component_safety": "NON_COMPONENT_SAFE",
            "conclusion": (
                "Anche quando rosso, e' una nota normativa/editoriale (annotation_type OTHER), "
                "non un componente. Non e' idonea a catalog_component_relations."
            ),
            "records": brief(conforme),
        },
        "wifi_optional": {
            "phrase": "WiFi optional",
            "occurrence_count": len(wifi),
            "origin_distribution": distribution(wifi),
            "component_safety": "NON_COMPONENT_SAFE_WHEN_NOT_RED",
            "conclusion": (
                "Le righe sintetizzate KIT WI-FI/WIFIKEY + OPTIONAL sono verificate sui loro span di tabella, "
                "non su un presunto sfondo: se gli span non sono rossi, sono esclusi. Fill/stroke non esistono nel layout."
            ),
            "records": brief(wifi),
        },
        "tranne_che_su_taglie_2_5kw_e_3_5kw": {
            "phrase": "(tranne che su taglie 2.5kW e 3.5kW)",
            "occurrence_count": len(tranne),
            "origin_distribution": distribution(tranne),
            "conclusion": "Nota di limitazione commerciale; non implica un componente o una relazione automatica.",
            "records": brief(tranne),
        },
        "confezione_50_guanti_100_lattice_naturale": {
            "phrase": "Confezione 50 guanti 100% lattice naturale",
            "occurrence_count": len(guanti),
            "origin_distribution": distribution(guanti),
            "conclusion": "Verificare i record elencati: testo di tabella/prodotto non rosso, non una prova di claim rosso.",
            "records": brief(guanti),
        },
        "ideale_per_calore_da_fiamma": {
            "phrase": "Ideale per calore da fiamma",
            "occurrence_count": len(fiamma),
            "origin_distribution": distribution(fiamma),
            "conclusion": "Claim prestazionale: il colore stabilisce l'origine, non lo trasforma in relazione componente.",
            "records": brief(fiamma),
        },
    }


def build_origin_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    origin_count = Counter(record["origin_check"] for record in records)
    source_match_count = Counter(record["layout_match"]["method"] for record in records)
    by_type: dict[str, dict[str, int]] = {}
    for annotation_type in sorted({str(record.get("annotation_type") or "OTHER") for record in records}):
        selected = [record for record in records if record.get("annotation_type") == annotation_type]
        distribution = Counter(record["origin_check"] for record in selected)
        by_type[annotation_type] = {
            "total": len(selected),
            **{origin: distribution[origin] for origin in ORIGIN_VALUES},
        }
    suspicious = [make_suspicious_record(record) for record in records if record["origin_check"] == "NON_RED_TEXT"]
    unknown = [record["annotation_id"] for record in records if record["origin_check"] == "UNKNOWN"]
    return {
        "audit_scope": {
            "mode": "READ_ONLY",
            "annotation_source": "Knowledge/catalog_annotations.json",
            "layout_source": "Knowledge/catalogo_layout.jsonl.gz",
            "classification_is_temporary_in_this_report_only": True,
            "original_red_filter": "#RRGGBB; R>=150; R>1.35*G; R>1.35*B",
            "fill_stroke_status": "The supplied layout schema has no fill/stroke/vector fields; null means unavailable, not white/transparent.",
            "span_alignment": "Normal records: page + original rounded line bbox + raw-text range. Synthesised optional rows: the two source lines whose union bbox produced the annotation.",
        },
        "total_annotations": len(records),
        "source_match_distribution": dict(sorted(source_match_count.items())),
        "origin_distribution": {origin: origin_count[origin] for origin in ORIGIN_VALUES},
        "by_annotation_type": by_type,
        "suspicious_records_count": len(suspicious),
        "suspicious_records": suspicious,
        "unknown_annotation_ids": unknown,
        "annotations_with_source_graphics": records,
        "mandatory_examples": find_examples(records),
    }


def build_safety_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    component_records = [record for record in records if record.get("annotation_type") in COMPONENT_TYPES]
    safety_records: list[dict[str, Any]] = []
    distribution: dict[str, dict[str, int]] = {}
    for annotation_type in sorted(COMPONENT_TYPES):
        selected = [record for record in component_records if record["annotation_type"] == annotation_type]
        colors = Counter(record["origin_check"] for record in selected)
        distribution[annotation_type] = {
            "total": len(selected),
            "safe_RED_TEXT_CONFIRMED": colors["RED_TEXT_CONFIRMED"],
            "unsafe_NON_RED_TEXT": colors["NON_RED_TEXT"],
            "unsafe_UNKNOWN": colors["UNKNOWN"],
        }
    for record in component_records:
        safe = record["origin_check"] == "RED_TEXT_CONFIRMED"
        safety_records.append(
            {
                "annotation_id": record["annotation_id"],
                "page": record["page"],
                "table_id": record["table_id"],
                "raw_text": record["raw_text"],
                "annotation_type": record["annotation_type"],
                "origin_check": record["origin_check"],
                "safe_for_component_relation": safe,
                "colore_trovato": record["colore_trovato"],
                "rgb_trovati": record["rgb_trovati"],
                "font": record["font"],
                "size_pt": record["size_pt"],
                "bold": record["bold"],
                "italic": record["italic"],
                "bbox": record["bbox"],
                "layout_match": record["layout_match"],
                "motivo_classificazione": record["motivo_classificazione"],
            }
        )

    record_by_id = {record["annotation_id"]: record for record in records}
    relation_impact: dict[str, Any] = {
        "relations_file": str(RELATIONS_PATH.relative_to(ROOT)),
        "relations_file_present": RELATIONS_PATH.exists(),
        "total_relations": 0,
        "origin_distribution": {origin: 0 for origin in ORIGIN_VALUES},
        "relations_with_accessory_links_by_origin": {origin: 0 for origin in ORIGIN_VALUES},
        "accessory_links_by_origin": {origin: 0 for origin in ORIGIN_VALUES},
        "unmatched_annotation_ids": [],
        "unsafe_relation_records": 0,
        "recommend_regeneration": False,
        "recommendation": "No relation file found; no mutation was performed.",
    }
    if RELATIONS_PATH.exists():
        with RELATIONS_PATH.open("r", encoding="utf-8") as file:
            relations = json.load(file)
        relation_impact["total_relations"] = len(relations)
        rel_counter: Counter[str] = Counter()
        linked_relation_counter: Counter[str] = Counter()
        accessory_link_counter: Counter[str] = Counter()
        unmatched: list[Any] = []
        for relation in relations:
            record = record_by_id.get(relation.get("annotation_id"))
            if record is None:
                unmatched.append(relation.get("annotation_id"))
            else:
                origin = record["origin_check"]
                rel_counter[origin] += 1
                accessory_count = len(relation.get("accessories") or [])
                if accessory_count:
                    linked_relation_counter[origin] += 1
                    accessory_link_counter[origin] += accessory_count
        relation_impact["origin_distribution"] = {origin: rel_counter[origin] for origin in ORIGIN_VALUES}
        relation_impact["relations_with_accessory_links_by_origin"] = {
            origin: linked_relation_counter[origin] for origin in ORIGIN_VALUES
        }
        relation_impact["accessory_links_by_origin"] = {
            origin: accessory_link_counter[origin] for origin in ORIGIN_VALUES
        }
        relation_impact["unmatched_annotation_ids"] = sorted(set(unmatched))
        unsafe = rel_counter["NON_RED_TEXT"] + rel_counter["UNKNOWN"] + len(unmatched)
        relation_impact["unsafe_relation_records"] = unsafe
        relation_impact["recommend_regeneration"] = unsafe > 0
        relation_impact["recommendation"] = (
            "Rigenerazione consigliata dopo revisione della policy: la relazione corrente contiene annotazioni "
            "NON_RED_TEXT/UNKNOWN che questa policy vieta di usare automaticamente. Questo audit non modifica il file."
            if unsafe
            else "Nessuna relazione corrente risulta collegata a un'origine non sicura."
        )

    safe_count = sum(1 for record in safety_records if record["safe_for_component_relation"])
    origin_count = Counter(record["origin_check"] for record in component_records)
    normative = [
        record
        for record in records
        if "conforme alla normativa" in normalize_text(str(record.get("raw_text") or ""))
        and ("en501" in str(record.get("raw_text") or "").casefold() or "en 501" in str(record.get("raw_text") or "").casefold())
    ]
    return {
        "audit_scope": {
            "included_annotation_types": sorted(COMPONENT_TYPES),
            "rule_enforced": "Only RED_TEXT_CONFIRMED has safe_for_component_relation=true. NON_RED_TEXT and UNKNOWN are always false.",
        },
        "total_component_annotations": len(component_records),
        "safe_count": safe_count,
        "unsafe_count": len(component_records) - safe_count,
        "origin_distribution": {origin: origin_count[origin] for origin in ORIGIN_VALUES},
        "safety_distribution_by_type": distribution,
        "records": safety_records,
        "mandatory_non_component_case": {
            "phrase": "Conforme alla normativa EN501/16",
            "classification": "NON_COMPONENT_SAFE",
            "reason": "Nota normativa/editoriale: e' fuori dai tipi componente analizzati e safe_for_component_relation e' false anche quando l'origine e' rossa.",
            "records": [
                {
                    "annotation_id": record["annotation_id"],
                    "page": record["page"],
                    "raw_text": record["raw_text"],
                    "annotation_type": record["annotation_type"],
                    "origin_check": record["origin_check"],
                    "safe_for_component_relation": False,
                    "colore_trovato": record["colore_trovato"],
                }
                for record in normative
            ],
        },
        "catalog_component_relations_impact": relation_impact,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")
    temporary_path.replace(path)


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    with ANNOTATIONS_PATH.open("r", encoding="utf-8") as file:
        annotations: list[dict[str, Any]] = json.load(file)
    annotations_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for annotation in annotations:
        annotations_by_page[int(annotation.get("page") or 0)].append(annotation)

    audited: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as file:
        for raw_page in file:
            page_data = json.loads(raw_page)
            page = int(page_data.get("page") or 0)
            page_annotations = annotations_by_page.get(page)
            if not page_annotations:
                continue
            seen_pages.add(page)
            page_lines = build_page_lines(page_data)
            bbox_index: dict[tuple[float, float, float, float], list[dict[str, Any]]] = defaultdict(list)
            for line in page_lines:
                bbox_index[rounded_bbox_key(line["bbox"])].append(line)
            for annotation in page_annotations:
                audited.append(audit_annotation(annotation, page_lines, bbox_index))

    # Retain order and explicitly show a damaged/missing page rather than
    # silently dropping its annotations.
    unseen_annotations = [
        annotation for annotation in annotations if int(annotation.get("page") or 0) not in seen_pages
    ]
    for annotation in unseen_annotations:
        audited.append(
            audit_annotation(annotation, [], defaultdict(list))
        )

    audited.sort(key=lambda record: str(record["annotation_id"]))
    return build_origin_report(audited), build_safety_report(audited)


if __name__ == "__main__":
    origin_report, safety_report = run()
    write_json(ORIGIN_REPORT_PATH, origin_report)
    write_json(SAFETY_REPORT_PATH, safety_report)
    print(json.dumps({
        "total_annotations": origin_report["total_annotations"],
        "origin_distribution": origin_report["origin_distribution"],
        "total_component_annotations": safety_report["total_component_annotations"],
        "safe_component_annotations": safety_report["safe_count"],
        "unsafe_component_annotations": safety_report["unsafe_count"],
        "recommend_relation_regeneration": safety_report["catalog_component_relations_impact"]["recommend_regeneration"],
    }, ensure_ascii=False, indent=2))
