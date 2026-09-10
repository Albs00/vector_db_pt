#!/usr/bin/env python3
"""Build a conservative three-channel component relation preview.

Inputs are read-only.  Coded accessory links are accepted only when the PDF
layout proves a same-row link or a continuous, same-column accessory section.
Family keys are copied exclusively from catalog_table_context.json.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
ORIGIN_AUDIT_PATH = ROOT / "catalog_annotations_origin_audit.json"
COMPONENT_SAFETY_PATH = ROOT / "catalog_annotations_component_safety_report.json"
TABLE_CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"
LAYOUT_PATH = ROOT / "Knowledge" / "catalogo_layout.jsonl.gz"
CURRENT_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
PREVIOUS_PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview.json"
PREVIOUS_REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_report.json"
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v2.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v2_report.json"

CHANNEL_RED = "RED_EDITORIAL_ANNOTATION"
CHANNEL_ROW = "EXPLICIT_TABLE_ACCESSORY_ROW"
CHANNEL_SECTION = "EXPLICIT_ACCESSORY_SECTION"
CHANNELS = (CHANNEL_RED, CHANNEL_ROW, CHANNEL_SECTION)

ALLOWED_RED_TYPES = {
    "COMPONENT_INCLUDED", "COMPONENT_EXCLUDED", "COMPONENT_REQUIRED",
    "FEATURE_INCLUDED", "FEATURE", "USAGE_LIMITATION", "SALE_QUANTITY",
    "PACKAGE_QUANTITY", "INSTALLATION_REQUIREMENT", "COMPATIBILITY_NOTE",
}

FEATURE_ONLY_TYPES = {
    "FEATURE_INCLUDED", "FEATURE", "USAGE_LIMITATION", "SALE_QUANTITY",
    "PACKAGE_QUANTITY", "INSTALLATION_REQUIREMENT", "COMPATIBILITY_NOTE",
}

MACHINE_PREFIXES = (
    "CALDAIA", "SCALDABAGNO", "UNITA", "U.I", "U.E", "PARETE", "CONSOLE",
    "CANALIZZ", "CASSETTA", "PAVIMENTO", "SOFFITTO", "MONOSPLIT", "MULTISPLIT",
    "POMPA DI CALORE", "STUFA", "TERMOSTUFA", "VENTILCONVETTORE", "FANCOIL",
)

ACCESSORY_TITLE_RE = re.compile(
    r"^(?:ACCESSORI|ACCESSORIO|GRIGLIA|PANNELLO|COMANDO|TELECOMANDO|"
    r"FILTRO|KIT\b|CAVO|SONDA|SENSORE|RICEVITORE|MODULO WI|WIFI|WI-FI|"
    r"POMPA SCARICO CONDENSA|STAFFA|SUPPORTO|BACINELLA|VALVOLA)", re.I,
)

ACCESSORY_ROW_RE = re.compile(
    r"(?:KIT\s*WI[- ]?FI|KITWIFI|WIFIKEY|WIFIKIT|WI[- ]?FI|"
    r"BYCQ\w*|BYFQ\w*|T-MBQ[\w/-]*|GLG\w*|BRC[\w/-]*|PAR-[\w/-]*|"
    r"KJR-[\w/-]*|WRC\w*|RBC-[\w/-]*|CZ-[\w/-]*|MLP-[\w/-]*|"
    r"SLP-[\w/-]*|FILO\s+COMANDO|COMANDO\s+(?:A\s+FILO|DA\s+PARETE)|"
    r"TELECOMANDO|GRIGLIA(?:\s+\w+)*)",
    re.I,
)

PHYSICAL_COMPONENT_RE = re.compile(
    r"\b(?:GRIGLIA|COMANDO|TELECOMANDO|PANNELLO|POMPA|VALVOLA|SONDA|SENSORE|"
    r"FILTRO|STAFFA|SUPPORTO|KIT|MODULO|CAVO|BATTERIA|BRUCIATORE|PILETTA|SEDILE)\b",
    re.I,
)

STANDALONE_ACCESSORY_TITLE_RE = re.compile(
    r"^(?:KIT\b|GRIGLIA\b|SONDA\b|COMANDO\b|TERMOSTATO\b|ATTACCO\b|CURVA\b|"
    r"RACCORDO\b|ACCESSORI?\b|PANNELLO\b|TELECOMANDO\b|STAFFA\b|TUBO\b|"
    r"GIUNTO\b|FILTRO\b|COPERCHIO\b|SET VALVOLE\b|GRUPPO DI SICUREZZA\b)",
    re.I,
)


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def words(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    return re.findall(r"[A-Z0-9]+", text)


GENERIC_TARGET_WORDS = {
    "ACCESSORI", "ACCESSORIO", "OPTIONAL", "OPZIONALI", "KIT", "PER", "SERIE",
    "MODELLO", "MODELLI", "DA", "DI", "A", "CON", "IL", "LA", "LE", "I", "GLI",
    "DEL", "DELLA", "DELLE", "IN", "ARIA", "MURO", "PERIMETRALE", "STANDARD",
    "DESIGN", "BIANCO", "BIANCA", "NERO", "NERA", "FILO", "COMANDO", "GRIGLIA",
}


def significant_words(value: Any) -> set[str]:
    return {
        token for token in words(value)
        if token not in GENERIC_TARGET_WORDS and (len(token) >= 3 or token.isdigit())
    }


def is_standalone_accessory_like(title: str) -> bool:
    return bool(STANDALONE_ACCESSORY_TITLE_RE.search(str(title or "").strip()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def center(box: Iterable[float]) -> tuple[float, float]:
    values = list(box)
    return ((values[0] + values[2]) / 2, (values[1] + values[3]) / 2)


def bbox_dict(box: Iterable[float]) -> dict[str, float]:
    values = [round(float(x), 3) for x in box]
    return dict(zip(("x0", "y0", "x1", "y1"), values))


def bbox_union(*boxes: Iterable[float] | None) -> dict[str, float]:
    values = [list(box) for box in boxes if box is not None]
    return bbox_dict([
        min(box[0] for box in values), min(box[1] for box in values),
        max(box[2] for box in values), max(box[3] for box in values),
    ])


def color_hex(value: Any) -> str:
    if isinstance(value, int):
        return f"#{value & 0xFFFFFF:06X}"
    text = str(value or "").strip().upper()
    if text.startswith("#") and len(text) == 7:
        return text
    return text


def annotation_box(annotation: dict[str, Any]) -> list[float]:
    box = annotation.get("bbox") or {}
    return [float(box.get(k) or 0) for k in ("x0", "y0", "x1", "y1")]


def column_for_x(x: float, width: float) -> int:
    return 0 if x < width / 2 else 1


def is_accessory_title(title: str) -> bool:
    value = str(title or "").strip()
    upper = value.upper()
    if any(upper.startswith(prefix) for prefix in MACHINE_PREFIXES):
        return False
    return bool(ACCESSORY_TITLE_RE.search(value))


def component_type(text: str, fallback: str = "") -> str:
    value = f"{text} {fallback}".upper()
    if value.strip().startswith("CAVO"):
        return "CAVO"
    if "TELECOMANDO" in value or "RICEVITORE INFRAROSSI" in value:
        return "TELECOMANDO"
    if "COMANDO A FILO" in value or "FILO COMANDO" in value or "FILOCOMANDO" in value:
        return "COMANDO A FILO"
    if "COMANDO" in value or re.search(r"\b(?:BRC|PAR-|KJR-|WRC|RBC-)", value):
        return "COMANDO"
    if "WIFI" in value or "WI-FI" in value:
        return "WIFI"
    if "POMPA" in value and "CONDENSA" in value:
        return "POMPA SCARICO CONDENSA"
    if "GRIGLIA" in value or re.search(r"\b(?:BYCQ|BYFQ|GLG\d|T-MBQ)", value):
        return "GRIGLIA"
    if "FILTRO" in value:
        return "FILTRO"
    if "SONDA" in value or "SENSORE" in value:
        return "SONDA"
    if "VALVOLA" in value:
        return "VALVOLA"
    if "STAFFA" in value or "SUPPORTO" in value or "FISSAGGIO" in value:
        return "STRUTTURA DI FISSAGGIO"
    if "BRUCIATORE" in value:
        return "BRUCIATORE"
    if "SEDILE" in value:
        return "SEDILE"
    if "PILETTA" in value:
        return "PILETTA"
    if fallback:
        return fallback
    return "ACCESSORIO"


def red_component(annotation: dict[str, Any]) -> str:
    text = str(annotation.get("raw_text") or "")
    atype = str(annotation.get("annotation_type") or "")
    if atype in FEATURE_ONLY_TYPES:
        fallback = "FEATURE" if atype in {"FEATURE", "FEATURE_INCLUDED"} else atype
        return component_type(text, fallback)
    entities = annotation.get("entities") or []
    entity = next(
        (str(item.get("value") or "") for item in entities
         if item.get("type") == "COMPONENT" and item.get("value") != "ACCESSORIO"),
        "",
    )
    return component_type(text, entity or "ACCESSORIO")


def red_intent(annotation: dict[str, Any]) -> tuple[str, bool]:
    status = str(annotation.get("annotation_type") or "")
    text = str(annotation.get("raw_text") or "").lower()
    required = status == "COMPONENT_REQUIRED" or any(
        phrase in text for phrase in (
            "obbligatoriamente", "obbligatorio da abbinare", "acquisto obbligatorio",
        )
    )
    if required:
        return "ACCESSORY_REQUIRED", True
    if status in FEATURE_ONLY_TYPES:
        return "FEATURE_ONLY", False
    if component_type(str(annotation.get("raw_text") or "")) == "POMPA SCARICO CONDENSA" and any(
        token in text for token in ("dotat", "integrat", "complet", "con pompa", "inclus", "compres")
    ):
        return "FEATURE_ONLY", False
    if status == "COMPONENT_EXCLUDED":
        return "ACCESSORY_OPTIONAL", False
    if status == "COMPONENT_INCLUDED":
        return "NO_COMPONENT_CODE", False
    return "NO_COMPONENT_CODE", False


def red_non_component_reason(annotation: dict[str, Any]) -> str | None:
    text = str(annotation.get("raw_text") or "")
    folded = " ".join(words(text))
    physical = bool(PHYSICAL_COMPONENT_RE.search(text))
    finish_tokens = (
        "ESCLUSIVAMENTE", "ESCLUSIVO", "ESCLUSIVA", "ESCLUSIVI", "ESCLUSIVE",
        "ESCLUSIVITA", "SOLO DISPONIBILE IN", "DISPONIBILE SOLO", "REALIZZABILE SOLO",
        "REALIZZABILE ESCLUSIVAMENTE", "COLORE", "FINITURA",
    )
    if any(token in folded for token in finish_tokens) and not physical:
        return "VARIANT_OR_FINISH_LIMITATION"
    editorial_tokens = (
        "CONFORME ALLA NORMATIVA", "IDEALE PER", "PRODUZIONE DI ACQUA CALDA",
        "CLASSE ENERGETICA", "REALIZZABILE IN BIANCO",
    )
    if any(token in folded for token in editorial_tokens) and not physical:
        return "NON_COMPONENT_EDITORIAL_TEXT"
    return None


def component_commercial_fields(
    annotation: dict[str, Any] | None,
    intent: str,
    mandatory_pairing: bool,
    default_inclusion: str = "UNKNOWN",
) -> dict[str, Any]:
    inclusion = default_inclusion
    if annotation:
        status = str(annotation.get("annotation_type") or "")
        text = str(annotation.get("raw_text") or "").lower()
        valid_excluded = bool(re.search(r"\besclus[oaie]\b", text)) and not bool(
            re.search(r"\besclusiv(?:o|a|i|e|amente|ita)\b", text)
        )
        if any(token in text for token in ("non incluso", "non inclusa", "non compreso", "non compresa", "senza ")):
            inclusion = "EXCLUDED"
        elif valid_excluded:
            inclusion = "EXCLUDED"
        elif status == "COMPONENT_INCLUDED":
            inclusion = "INCLUDED"
        elif status == "COMPONENT_EXCLUDED":
            inclusion = "EXCLUDED"
        elif "optional" in text or "opzional" in text:
            inclusion = "OPTIONAL"
    if intent == "ACCESSORY_INCLUDED_SEPARATE":
        bom_action = "ADD_SEPARATE_INCLUDED_COMPONENT"
    elif mandatory_pairing:
        bom_action = "ADD_IF_SOLD_TITLE_INCLUDES"
    elif inclusion in {"INCLUDED", "OPTIONAL"} or intent in {"FEATURE_ONLY", "NO_COMPONENT_CODE"}:
        bom_action = "NONE"
    else:
        bom_action = "REVIEW"
    return {
        "catalog_inclusion_status": inclusion,
        "mandatory_pairing": mandatory_pairing,
        "bom_action": bom_action,
        "required_for_sale_semantics": "MANDATORY_PAIRING_NOT_BASE_PRODUCT_INCLUSION",
    }


@dataclass
class LayoutLine:
    text: str
    bbox: list[float]
    block: int
    line: int
    colors: list[str]


@dataclass
class LayoutPage:
    number: int
    width: float
    height: float
    lines: list[LayoutLine]
    code_boxes: dict[str, list[list[float]]] = field(default_factory=lambda: defaultdict(list))

    def title_boxes(self, title: str) -> list[list[float]]:
        target = normalized(title)
        if not target:
            return []
        exact = [line.bbox for line in self.lines if normalized(line.text) == target]
        if exact:
            return exact
        return [
            line.bbox for line in self.lines
            if target in normalized(line.text) and len(normalized(line.text)) <= len(target) + 12
        ]

    def row_lines(self, box: list[float]) -> list[LayoutLine]:
        x, y = center(box)
        col = column_for_x(x, self.width)
        return sorted(
            [line for line in self.lines
             if column_for_x(center(line.bbox)[0], self.width) == col
             and abs(center(line.bbox)[1] - y) <= 5.0],
            key=lambda line: line.bbox[0],
        )


@dataclass
class ContextAppearance:
    pt: str
    brand: str
    model: str
    mpn: str
    page: int
    table_id: str
    title: str
    family_key: str


@dataclass
class TableGeometry:
    page: int
    table_id: str
    title: str
    family_key: str
    brand: str
    heading_bbox: list[float]
    column: int
    accessory: bool
    appearances: list[ContextAppearance]
    rows: list[tuple[ContextAppearance, list[float]]] = field(default_factory=list)

    @property
    def models(self) -> list[str]:
        return sorted({a.model for a, _ in self.rows if a.model and a.model != "OPTIONAL"})

    @property
    def max_code_y(self) -> float:
        return max((box[3] for _, box in self.rows), default=self.heading_bbox[3])

    @property
    def product_bbox(self) -> dict[str, float]:
        return bbox_union(self.heading_bbox, *(box for _, box in self.rows))


def load_layout(codes: set[str]) -> dict[int, LayoutPage]:
    pages: dict[int, LayoutPage] = {}
    code_re = re.compile(r"(?<!\d)(\d{8})(?!\d)")
    with gzip.open(LAYOUT_PATH, "rt", encoding="utf-8") as handle:
        for raw in handle:
            source = json.loads(raw)
            page = LayoutPage(
                int(source.get("page") or 0),
                float(source.get("width_pt") or 595),
                float(source.get("height_pt") or 842),
                [],
            )
            for block_index, block in enumerate(source.get("blocks") or []):
                for line_index, line in enumerate(block.get("lines") or []):
                    spans = line.get("spans") or []
                    text = "".join(str(span.get("text") or "") for span in spans).strip()
                    box = line.get("bbox")
                    if not text or not isinstance(box, list) or len(box) != 4:
                        continue
                    colors = list(dict.fromkeys(
                        color_hex(span.get("color")) for span in spans if span.get("color") is not None
                    ))
                    layout_line = LayoutLine(
                        text, [float(x) for x in box], block_index, line_index, colors,
                    )
                    page.lines.append(layout_line)
                    for match in code_re.finditer(text):
                        code = match.group(1)
                        if code in codes:
                            page.code_boxes[code].append(layout_line.bbox)
            pages[page.number] = page
    return pages


def context_appearances(context: dict[str, dict[str, Any]]) -> list[ContextAppearance]:
    result: list[ContextAppearance] = []
    seen: set[tuple[str, int, str]] = set()
    for pt, base in context.items():
        raw_contexts = [base, *(base.get("alternate_table_contexts") or [])]
        for raw in raw_contexts:
            page = int(raw.get("page") or 0)
            table_id = str(raw.get("table_id") or "")
            identity = (str(pt), page, table_id)
            if not page or not table_id or identity in seen:
                continue
            seen.add(identity)
            result.append(ContextAppearance(
                str(pt), str(raw.get("brand") or base.get("brand") or ""),
                str(base.get("model") or ""), str(base.get("mpn") or ""), page,
                table_id, str(raw.get("table_title") or raw.get("catalog_family") or ""),
                str(raw.get("family_key") or ""),
            ))
    return result


def choose_heading_and_rows(
    appearances: list[ContextAppearance], page: LayoutPage
) -> tuple[list[float] | None, list[tuple[ContextAppearance, list[float]]]]:
    title = appearances[0].title
    headings = page.title_boxes(title)
    if not headings:
        return None, []
    options: list[tuple[int, float, list[float], list[tuple[ContextAppearance, list[float]]]]] = []
    for heading in headings:
        hx, _ = center(heading)
        col = column_for_x(hx, page.width)
        rows: list[tuple[ContextAppearance, list[float]]] = []
        total_gap = 0.0
        for appearance in appearances:
            candidates = [
                box for box in page.code_boxes.get(appearance.pt, [])
                if column_for_x(center(box)[0], page.width) == col
                and -2 <= box[1] - heading[3] <= 420
            ]
            if candidates:
                selected = min(candidates, key=lambda box: box[1] - heading[3])
                rows.append((appearance, selected))
                total_gap += selected[1] - heading[3]
        options.append((-len(rows), total_gap, heading, rows))
    options.sort(key=lambda item: (item[0], item[1]))
    if not options or not options[0][3]:
        return None, []
    if len(options) > 1 and options[0][:2] == options[1][:2]:
        return None, []
    return options[0][2], options[0][3]


def build_tables(
    appearances: list[ContextAppearance], pages: dict[int, LayoutPage]
) -> tuple[list[TableGeometry], list[dict[str, Any]]]:
    grouped: dict[tuple[int, str], list[ContextAppearance]] = defaultdict(list)
    for appearance in appearances:
        grouped[(appearance.page, appearance.table_id)].append(appearance)
    tables: list[TableGeometry] = []
    rejected: list[dict[str, Any]] = []
    for (page_number, table_id), group in grouped.items():
        page = pages.get(page_number)
        if not page:
            continue
        heading, rows = choose_heading_and_rows(group, page)
        if not heading:
            rejected.append({
                "page": page_number, "table_id": table_id, "table_title": group[0].title,
                "reason": "AMBIGUOUS_GEOMETRY",
            })
            continue
        family_keys = {item.family_key for item in group if item.family_key}
        family_key = next(iter(family_keys)) if len(family_keys) == 1 else ""
        tables.append(TableGeometry(
            page_number, table_id, group[0].title, family_key, group[0].brand,
            heading, column_for_x(center(heading)[0], page.width),
            is_accessory_title(group[0].title), group, rows,
        ))
    return tables, rejected


def table_payload(table: TableGeometry) -> dict[str, Any]:
    return {
        "table_title": table.title,
        "family_key": table.family_key,
        "models": table.models,
    }


def row_accessory_model(
    page: LayoutPage, appearance: ContextAppearance, code_box: list[float], require_exact: bool
) -> tuple[str, list[float] | None, bool, list[float] | None]:
    lines = page.row_lines(code_box)
    row_text = " ".join(line.text for line in lines)
    optional = appearance.model.upper() == "OPTIONAL" or "OPTIONAL" in row_text.upper()
    optional_box = next(
        (line.bbox for line in lines if normalized(line.text) in {"OPTIONAL", "OPZIONALE"}),
        None,
    )
    for candidate in (appearance.model, appearance.mpn):
        if not candidate or candidate.upper() == "OPTIONAL":
            continue
        target = normalized(candidate)
        for line in lines:
            if target and target in normalized(line.text):
                return line.text.strip(), line.bbox, optional, optional_box
    for line in lines:
        cleaned = re.sub(r"\b\d{8}\b", "", line.text).strip()
        match = ACCESSORY_ROW_RE.search(cleaned)
        if match:
            return match.group(0).strip(), line.bbox, optional, optional_box
    if require_exact:
        return "", None, optional, optional_box
    return "", None, optional, optional_box


def colors_for_box(page: LayoutPage, box: list[float] | None) -> list[str]:
    if box is None:
        return []
    return next((line.colors for line in page.lines if line.bbox == box), [])


def assign_annotation_table(
    annotation: dict[str, Any], product_tables: list[TableGeometry], pages: dict[int, LayoutPage]
) -> TableGeometry | None:
    page_number = int(annotation.get("page") or 0)
    page = pages.get(page_number)
    if not page:
        return None
    box = annotation_box(annotation)
    ax, ay = center(box)
    col = column_for_x(ax, page.width)
    candidates = [
        table for table in product_tables
        if table.page == page_number and table.column == col and table.heading_bbox[1] <= ay
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda table: table.heading_bbox[1], reverse=True)
    direct = next((table for table in candidates if table.table_id == annotation.get("table_id")), None)
    if direct and candidates[0].heading_bbox[1] == direct.heading_bbox[1]:
        return direct
    return candidates[0]


def annotation_scope(
    annotation: dict[str, Any], table: TableGeometry,
) -> tuple[str, list[str]]:
    box = annotation_box(annotation)
    _, annotation_y = center(box)
    row_matches = [
        appearance.model for appearance, row_box in table.rows
        if appearance.model and appearance.model != "OPTIONAL"
        and abs(center(row_box)[1] - annotation_y) <= 4.0
    ]
    if row_matches:
        return "ROW_SCOPED", sorted(set(row_matches))
    first_row_y = min((box[1] for _, box in table.rows), default=table.heading_bbox[3])
    if annotation_y < first_row_y:
        return "TABLE_WIDE", table.models
    return "UNKNOWN", []


def make_red_record(annotation: dict[str, Any], table: TableGeometry | None) -> dict[str, Any]:
    intent, required = red_intent(annotation)
    ctype = red_component(annotation)
    scope_type, applies_to_models = annotation_scope(annotation, table) if table else ("UNKNOWN", [])
    commercial = component_commercial_fields(annotation, intent, required)
    return {
        "page": int(annotation.get("page") or 0),
        "table_id": table.table_id if table else "",
        "product_context": table_payload(table) if table else {
            "table_title": "", "family_key": "", "models": [],
        },
        "component": {
            "type": ctype,
            "status": annotation.get("annotation_type"),
            "relation_intent": intent,
            "required_for_sale": required,
            **commercial,
        },
        "scope_type": scope_type,
        "applies_to_models": applies_to_models,
        "accessories": [],
        "source_channel": CHANNEL_RED,
        "sources": [CHANNEL_RED],
        "evidence": "RED_TEXT_CONFIRMED",
        "confidence": 1.0,
        "association_confidence_reason": "RED_EDITORIAL_COMPONENT_REQUIREMENT",
        "source_annotation_ids": [annotation.get("annotation_id")],
        "raw_text": annotation.get("raw_text") or "",
        "annotation_bbox": annotation.get("bbox") or {},
        "source": "PDF_LAYOUT",
    }


def build_red_records(
    annotations: list[dict[str, Any]], origins: dict[str, str],
    product_tables: list[TableGeometry], pages: dict[int, LayoutPage],
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[int, str, str], list[dict[str, Any]]],
    list[dict[str, Any]],
]:
    records: list[dict[str, Any]] = []
    by_parent_component: dict[tuple[int, str, str], list[dict[str, Any]]] = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    for annotation in annotations:
        aid = str(annotation.get("annotation_id") or "")
        if origins.get(aid) != "RED_TEXT_CONFIRMED":
            continue
        if annotation.get("annotation_type") not in ALLOWED_RED_TYPES:
            continue
        semantic_rejection = red_non_component_reason(annotation)
        if semantic_rejection:
            rejected.append({
                "stage": "RED_EDITORIAL_ANNOTATION",
                "annotation_id": aid,
                "page": int(annotation.get("page") or 0),
                "raw_text": annotation.get("raw_text") or "",
                "reason": semantic_rejection,
                "decision": "REJECTED",
            })
            continue
        table = assign_annotation_table(annotation, product_tables, pages)
        if table is None:
            rejected.append({
                "stage": "RED_EDITORIAL_ANNOTATION",
                "annotation_id": aid,
                "page": int(annotation.get("page") or 0),
                "raw_text": annotation.get("raw_text") or "",
                "reason": "AMBIGUOUS_GEOMETRY",
            })
            continue
        record = make_red_record(annotation, table)
        records.append(record)
        if table:
            key = (table.page, table.table_id, record["component"]["type"])
            by_parent_component[key].append(record)
    return records, by_parent_component, rejected


def build_inline_rows(
    product_tables: list[TableGeometry], pages: dict[int, LayoutPage]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str, str], dict[str, Any]] = {}
    for table in product_tables:
        page = pages[table.page]
        for appearance, code_box in table.rows:
            model, model_box, optional, optional_box = row_accessory_model(
                page, appearance, code_box, False,
            )
            if not optional or not model or not model_box:
                continue
            ctype = component_type(model)
            key = (
                table.page, table.table_id, ctype, appearance.pt,
                "TABLE_WIDE", tuple(table.models),
            )
            relation = grouped.setdefault(key, {
                "page": table.page,
                "table_id": table.table_id,
                "product_context": table_payload(table),
                "component": {
                    "type": ctype, "status": "COMPONENT_OPTIONAL",
                    "relation_intent": "ACCESSORY_OPTIONAL", "required_for_sale": False,
                    **component_commercial_fields(
                        None, "ACCESSORY_OPTIONAL", False, default_inclusion="OPTIONAL",
                    ),
                },
                "scope_type": "TABLE_WIDE",
                "applies_to_models": table.models,
                "accessories": [],
                "source_channel": CHANNEL_ROW,
                "sources": [CHANNEL_ROW],
                "evidence": "SAME_TABLE",
                "confidence": 1.0,
                "association_confidence_reason": "SAME_ROW_DESCRIPTION_OPTIONAL_PT",
                "source_annotation_ids": [],
                "source_occurrences": [],
                "source": "PDF_LAYOUT",
            })
            if appearance.pt not in {item["pt"] for item in relation["accessories"]}:
                occurrence = {
                    "page": table.page,
                    "bbox": bbox_union(code_box, model_box, optional_box),
                    "source_section_id": None,
                    "source_row": "SAME_ROW_DESCRIPTION_OPTIONAL_PT",
                }
                relation["accessories"].append({
                    "pt": appearance.pt, "model": model,
                    "page": table.page, "table_id": table.table_id,
                    "source_channel": CHANNEL_ROW, "evidence": "SAME_TABLE",
                    "confidence": 1.0,
                    "association_confidence_reason": "SAME_ROW_DESCRIPTION_OPTIONAL_PT",
                    "accessory_bbox": bbox_union(code_box, model_box, optional_box),
                    "pt_bbox": bbox_dict(code_box), "model_bbox": bbox_dict(model_box),
                    "optional_bbox": bbox_dict(optional_box) if optional_box else None,
                    "accessory_section_title": None,
                    "accessory_section_title_bbox": None,
                    "accessory_section_table_id": None,
                    "source_colors": list(dict.fromkeys(
                        colors_for_box(page, code_box)
                        + colors_for_box(page, model_box)
                        + colors_for_box(page, optional_box)
                    )),
                    "scope_type": "TABLE_WIDE",
                    "applies_to_models": table.models,
                    "source_occurrences": [occurrence],
                })
                relation["source_occurrences"].append(occurrence)
    return list(grouped.values())


def matching_models(reference: str, table: TableGeometry) -> list[str]:
    ref_norm = normalized(reference)
    ref_words = significant_words(reference)
    ref_numbers = {token for token in words(reference) if token.isdigit()}
    exact = [model for model in table.models if normalized(model) == ref_norm]
    if exact:
        return exact
    family_words = {token for token in significant_words(table.title) if not token.isdigit()}
    if len(family_words) < 2 or not family_words <= ref_words:
        return []
    matched = []
    for model in table.models:
        model_words = set(words(model))
        if not family_words <= model_words:
            continue
        model_numbers = {token for token in model_words if token.isdigit()}
        if ref_numbers and model_numbers and not (ref_numbers & model_numbers):
            continue
        matched.append(model)
    return matched


def no_interposed_primary(
    parent: TableGeometry, accessory: TableGeometry, tables: list[TableGeometry],
) -> bool:
    return not any(
        table.page == accessory.page
        and table.column == accessory.column
        and not table.accessory
        and table.table_id != parent.table_id
        and parent.heading_bbox[1] < table.heading_bbox[1] < accessory.heading_bbox[1]
        for table in tables
    )


def governor_for_accessory(
    accessory: TableGeometry,
    tables: list[TableGeometry],
    page: LayoutPage,
    red_by_parent: dict[tuple[int, str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    products = [
        table for table in tables
        if table.page == accessory.page and not table.accessory
        and not is_standalone_accessory_like(table.title)
    ]
    # Strongest evidence: the accessory row names an exact product model.
    row_targets: list[tuple[TableGeometry, str, list[str], list[float]]] = []
    for appearance, code_box in accessory.rows:
        reference = str(appearance.model or "")
        if not reference or reference.upper() == "OPTIONAL":
            continue
        for product in products:
            matched = matching_models(reference, product)
            if matched and normalized(reference) in {normalized(model) for model in matched}:
                model_box = next(
                    (
                        line.bbox for line in page.row_lines(code_box)
                        if normalized(reference) in normalized(line.text)
                    ),
                    code_box,
                )
                row_targets.append((product, reference, matched, model_box))
    unique_row_products = {item[0].table_id for item in row_targets}
    if len(unique_row_products) == 1:
        parent, target_text, _, target_box = row_targets[0]
        applies = sorted({model for item in row_targets for model in item[2]})
        target_text = " | ".join(dict.fromkeys(item[1] for item in row_targets))
        return {
            "parent": parent,
            "governor_evidence": "ROW_SCOPED_REFERENCE",
            "governor_confidence": 1.0,
            "target_text": target_text,
            "target_text_bbox": bbox_dict(target_box),
            "scope_type": "ROW_SCOPED",
            "applies_to_models": sorted(set(applies)),
            "decision": "ACCEPTED",
            "reason": None,
        }

    # Explicit family/model target in the accessory title or row description.
    reference_text = " ".join(
        [accessory.title]
        + [str(appearance.model or "") for appearance, _ in accessory.rows]
    )
    reference_words = significant_words(reference_text)
    explicit_targets: list[tuple[TableGeometry, list[str]]] = []
    for product in products:
        title_words = significant_words(product.title)
        if len(title_words) >= 2 and title_words <= reference_words:
            explicit_targets.append((product, matching_models(reference_text, product)))
    if len(explicit_targets) == 1:
        parent, applies = explicit_targets[0]
        applies = applies or parent.models
        scope_type = "MODEL_SCOPED" if applies and set(applies) != set(parent.models) else "TABLE_WIDE"
        return {
            "parent": parent,
            "governor_evidence": "EXPLICIT_TARGET_TEXT",
            "governor_confidence": 1.0,
            "target_text": reference_text,
            "target_text_bbox": bbox_dict(accessory.heading_bbox),
            "scope_type": scope_type,
            "applies_to_models": sorted(set(applies)),
            "decision": "ACCEPTED",
            "reason": None,
        }

    preceding = sorted(
        [
            table for table in products
            if table.column == accessory.column and table.heading_bbox[1] < accessory.heading_bbox[1]
        ],
        key=lambda table: table.heading_bbox[1],
    )
    parent = preceding[-1] if preceding else None
    header = None
    if parent and no_interposed_primary(parent, accessory, tables):
        headers = [
            line for line in page.lines
            if line.text.strip().upper().startswith("ACCESSORI")
            and column_for_x(center(line.bbox)[0], page.width) == accessory.column
            and parent.max_code_y - 2 <= line.bbox[1] < accessory.heading_bbox[1]
        ]
        header = max(headers, key=lambda line: line.bbox[1], default=None)
    if parent and header:
        header_words = significant_words(header.text)
        parent_words = significant_words(" ".join([parent.title, *parent.models]))
        target_words = header_words - {"ACCESSORI", "ACCESSORIO", "OPZIONALI", "OPTIONAL"}
        if target_words and target_words <= parent_words:
            return {
                "parent": parent,
                "governor_evidence": "TABLE_HEADER_GOVERNS_SECTION",
                "governor_confidence": 1.0,
                "target_text": header.text,
                "target_text_bbox": bbox_dict(header.bbox),
                "scope_type": "TABLE_WIDE",
                "applies_to_models": parent.models,
                "decision": "ACCEPTED",
                "reason": None,
            }
        if not target_words and 0 <= header.bbox[1] - parent.max_code_y <= 25:
            return {
                "parent": parent,
                "governor_evidence": "SAME_PRODUCT_BLOCK",
                "governor_confidence": 1.0,
                "target_text": header.text,
                "target_text_bbox": bbox_dict(header.bbox),
                "scope_type": "TABLE_WIDE",
                "applies_to_models": parent.models,
                "decision": "ACCEPTED",
                "reason": None,
            }

    # A component-specific red note inside the product table can close the
    # governor chain when the matching accessory section follows directly.
    if parent and no_interposed_primary(parent, accessory, tables):
        ctype = component_type(accessory.title)
        notes = red_by_parent.get((parent.page, parent.table_id, ctype), [])
        if notes and 0 <= accessory.heading_bbox[1] - parent.max_code_y <= 25:
            note = notes[0]
            return {
                "parent": parent,
                "governor_evidence": "SAME_PRODUCT_BLOCK",
                "governor_confidence": 1.0,
                "target_text": str(note.get("raw_text") or ""),
                "target_text_bbox": note.get("annotation_bbox") or {},
                "scope_type": "TABLE_WIDE",
                "applies_to_models": parent.models,
                "decision": "ACCEPTED",
                "reason": None,
            }

    raw_preceding = sorted(
        [
            table for table in tables
            if table.page == accessory.page and not table.accessory
            and table.column == accessory.column and table.heading_bbox[1] < accessory.heading_bbox[1]
        ],
        key=lambda table: table.heading_bbox[1],
    )
    raw_parent = raw_preceding[-1] if raw_preceding else None
    if raw_parent and is_standalone_accessory_like(raw_parent.title):
        reason, decision, confidence = "SIBLING_ACCESSORY_TABLE", "REJECTED", 0.0
    elif header:
        reason, decision, confidence = "AMBIGUOUS_GOVERNOR", "AMBIGUOUS", 0.5
    elif parent:
        reason, decision, confidence = "ACCESSORY_TABLE_WITHOUT_TARGET", "REJECTED", 0.0
    else:
        reason, decision, confidence = "AMBIGUOUS_GOVERNOR", "AMBIGUOUS", 0.0
    return {
        "parent": None,
        "governor_evidence": None,
        "governor_confidence": confidence,
        "target_text": header.text if header else None,
        "target_text_bbox": bbox_dict(header.bbox) if header else None,
        "scope_type": "UNKNOWN",
        "applies_to_models": [],
        "decision": decision,
        "reason": reason,
    }


def merge_red_semantics(
    relation: dict[str, Any], parent: TableGeometry,
    red_by_parent: dict[tuple[int, str, str], list[dict[str, Any]]], consumed: set[str],
) -> None:
    key = (parent.page, parent.table_id, relation["component"]["type"])
    notes = red_by_parent.get(key, [])
    required = next(
        (note for note in notes if note["component"]["relation_intent"] == "ACCESSORY_REQUIRED"),
        None,
    )
    optional = next(
        (note for note in notes if note["component"]["relation_intent"] == "ACCESSORY_OPTIONAL"),
        None,
    )
    selected = required or optional
    if not selected:
        return
    relation["component"] = dict(selected["component"])
    relation["sources"] = [CHANNEL_RED, relation["source_channel"]]
    relation["source_annotation_ids"] = list(selected["source_annotation_ids"])
    relation["raw_text"] = selected["raw_text"]
    relation["association_confidence_reason"] = (
        "RED_EDITORIAL_COMPONENT_REQUIREMENT + "
        "COLUMN_ALIGNED_DEDICATED_ACCESSORY_SECTION"
    )
    consumed.update(str(aid) for aid in selected["source_annotation_ids"] if aid)


def build_accessory_sections(
    accessory_tables: list[TableGeometry], all_tables: list[TableGeometry],
    pages: dict[int, LayoutPage],
    red_by_parent: dict[tuple[int, str, str], list[dict[str, Any]]],
) -> tuple[
    list[dict[str, Any]], set[str], list[dict[str, Any]], list[dict[str, Any]],
]:
    records: list[dict[str, Any]] = []
    consumed: set[str] = set()
    rejected: list[dict[str, Any]] = []
    governor_audit: list[dict[str, Any]] = []
    for table in accessory_tables:
        page = pages[table.page]
        governor = governor_for_accessory(table, all_tables, page, red_by_parent)
        parent = governor["parent"]
        audit_record = {
            "product_table_id": parent.table_id if parent else None,
            "product_title": parent.title if parent else None,
            "accessory_table_id": table.table_id,
            "accessory_title": table.title,
            "accessory_pts": sorted({appearance.pt for appearance, _ in table.rows}),
            "page": table.page,
            "governor_evidence": governor["governor_evidence"],
            "governor_confidence": governor["governor_confidence"],
            "target_text": governor["target_text"],
            "target_text_bbox": governor["target_text_bbox"],
            "scope_type": governor["scope_type"],
            "applies_to_models": governor["applies_to_models"],
            "decision": governor["decision"],
            "reason": governor["reason"],
        }
        governor_audit.append(audit_record)
        if not parent:
            rejected.append({
                "stage": "ACCESSORY_SECTION_GOVERNOR",
                "page": table.page,
                "table_id": table.table_id,
                "table_title": table.title,
                "reason": governor["reason"],
                "decision": governor["decision"],
                "governor_confidence": governor["governor_confidence"],
                "target_text": governor["target_text"],
            })
            continue
        for appearance, code_box in table.rows:
            model, model_box, _, optional_box = row_accessory_model(
                page, appearance, code_box, True,
            )
            if not model or not model_box:
                rejected.append({
                    "stage": "ACCESSORY_SECTION_ROW",
                    "page": table.page,
                    "table_id": table.table_id,
                    "table_title": table.title,
                    "pt": appearance.pt,
                    "reason": "AMBIGUOUS_GEOMETRY",
                    "decision": "AMBIGUOUS",
                })
                continue
            applies_to_models = list(governor["applies_to_models"])
            if governor["scope_type"] == "ROW_SCOPED":
                applies_to_models = matching_models(str(appearance.model or model), parent)
            occurrence = {
                "page": table.page,
                "bbox": bbox_union(code_box, model_box),
                "source_section_id": table.table_id,
                "source_row": model,
            }
            accessory_payload = {
                "pt": appearance.pt, "model": model,
                "page": table.page, "table_id": parent.table_id,
                "product_table_id": parent.table_id,
                "accessory_table_id": table.table_id,
                "source_channel": CHANNEL_SECTION,
                "evidence": "EXPLICIT_ACCESSORY_SECTION",
                "confidence": 1.0,
                "association_confidence_reason": f"STRONG_GOVERNOR_{governor['governor_evidence']}",
                "accessory_bbox": bbox_union(code_box, model_box),
                "accessory_row_bbox": bbox_union(code_box, model_box),
                "pt_bbox": bbox_dict(code_box), "model_bbox": bbox_dict(model_box),
                "optional_bbox": bbox_dict(optional_box) if optional_box else None,
                "accessory_section_title": table.title,
                "accessory_section_title_bbox": bbox_dict(table.heading_bbox),
                "accessory_section_table_id": table.table_id,
                "product_bbox": parent.product_bbox,
                "accessory_heading_bbox": bbox_dict(table.heading_bbox),
                "target_text": governor["target_text"],
                "target_text_bbox": governor["target_text_bbox"],
                "governor_evidence": governor["governor_evidence"],
                "governor_confidence": governor["governor_confidence"],
                "scope_type": governor["scope_type"],
                "applies_to_models": sorted(set(applies_to_models)),
                "source_colors": list(dict.fromkeys(
                    colors_for_box(page, code_box)
                    + colors_for_box(page, model_box)
                    + colors_for_box(page, table.heading_bbox)
                )),
                "source_occurrences": [occurrence],
            }
            default_inclusion = (
                "OPTIONAL"
                if "OPTIONAL" in str(governor["target_text"] or "").upper()
                or "OPZIONAL" in str(governor["target_text"] or "").upper()
                else "UNKNOWN"
            )
            relation = {
                "page": table.page,
                "table_id": parent.table_id,
                "product_table_id": parent.table_id,
                "accessory_table_id": table.table_id,
                "product_context": table_payload(parent),
                "component": {
                    "type": component_type(table.title), "status": "COMPONENT_OPTIONAL",
                    "relation_intent": "ACCESSORY_OPTIONAL", "required_for_sale": False,
                    **component_commercial_fields(
                        None, "ACCESSORY_OPTIONAL", False,
                        default_inclusion=default_inclusion,
                    ),
                },
                "scope_type": governor["scope_type"],
                "applies_to_models": sorted(set(applies_to_models)),
                "accessories": [accessory_payload],
                "source_channel": CHANNEL_SECTION,
                "sources": [CHANNEL_SECTION],
                "evidence": "EXPLICIT_ACCESSORY_SECTION",
                "confidence": 1.0,
                "association_confidence_reason": f"STRONG_GOVERNOR_{governor['governor_evidence']}",
                "source_annotation_ids": [],
                "accessory_section": {
                    "table_id": table.table_id, "table_title": table.title,
                    "heading_bbox": bbox_dict(table.heading_bbox),
                },
                "product_bbox": parent.product_bbox,
                "accessory_heading_bbox": bbox_dict(table.heading_bbox),
                "accessory_row_bbox": bbox_union(code_box, model_box),
                "pt_bbox": bbox_dict(code_box),
                "model_bbox": bbox_dict(model_box),
                "target_text": governor["target_text"],
                "target_text_bbox": governor["target_text_bbox"],
                "governor_evidence": governor["governor_evidence"],
                "governor_confidence": governor["governor_confidence"],
                "source_occurrences": [occurrence],
                "source": "PDF_LAYOUT",
            }
            merge_red_semantics(relation, parent, red_by_parent, consumed)
            records.append(relation)
    return records, consumed, rejected, governor_audit


def identity(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(record.get("page") or 0),
        str(record.get("table_id") or ""),
        str(record.get("component", {}).get("type") or ""),
        tuple(sorted(str(item.get("pt") or "") for item in record.get("accessories") or [])),
    )


def deduplicate_same_scope(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    removed: list[dict[str, Any]] = []
    for record in records:
        accessories = record.get("accessories") or []
        if len(accessories) != 1 or record.get("source_channel") == CHANNEL_RED:
            kept.append(record)
            continue
        accessory = accessories[0]
        key = (
            str(record.get("table_id") or ""),
            str(accessory.get("pt") or ""),
            str(record.get("source_channel") or ""),
            str(record.get("scope_type") or "UNKNOWN"),
            tuple(sorted(str(model) for model in record.get("applies_to_models") or [])),
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = record
            kept.append(record)
            continue
        existing_occurrences = existing.setdefault("source_occurrences", [])
        accessory_occurrences = existing["accessories"][0].setdefault("source_occurrences", [])
        for occurrence in record.get("source_occurrences") or []:
            marker = json.dumps(occurrence, sort_keys=True, ensure_ascii=False)
            if marker not in {
                json.dumps(item, sort_keys=True, ensure_ascii=False)
                for item in existing_occurrences
            }:
                existing_occurrences.append(occurrence)
                accessory_occurrences.append(occurrence)
        existing["source_annotation_ids"] = list(dict.fromkeys(
            list(existing.get("source_annotation_ids") or [])
            + list(record.get("source_annotation_ids") or [])
        ))
        removed.append({
            "reason": "DUPLICATE_SAME_SCOPE",
            "product_table_id": key[0],
            "accessory_pt": key[1],
            "source_channel": key[2],
            "scope_type": key[3],
            "applies_to_models": list(key[4]),
            "merged_occurrences": record.get("source_occurrences") or [],
        })
    return kept, removed


def elimination_reason(
    current: dict[str, Any], origin: str, annotations: dict[str, dict[str, Any]],
    preview_pts: dict[str, list[dict[str, Any]]],
) -> str:
    pts = {str(item.get("pt") or "") for item in current.get("accessories") or []}
    if pts and any(preview_pts.get(pt) for pt in pts):
        return "WRONG_TABLE_ASSOCIATION"
    annotation = annotations.get(str(current.get("annotation_id") or ""), {})
    if origin == "NON_RED_TEXT":
        if annotation.get("annotation_type") in {
            "COMPONENT_INCLUDED", "COMPONENT_EXCLUDED", "COMPONENT_REQUIRED",
            "COMPONENT_OPTIONAL", "FEATURE_INCLUDED", "FEATURE", "OTHER",
            "SALE_QUANTITY", "PACKAGE_QUANTITY",
        }:
            return "KEYWORD_FALSE_POSITIVE"
        return "NON_STRUCTURED_NON_RED_TEXT"
    if origin == "RED_TEXT_CONFIRMED" and not current.get("table_id"):
        return "AMBIGUOUS_GEOMETRY"
    return "NO_ACCESSORY_EVIDENCE"


def compare_current(
    preview: list[dict[str, Any]], current: list[dict[str, Any]],
    origins: dict[str, str], annotations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    preview_by_aid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    preview_by_identity = {identity(record): record for record in preview}
    preview_pts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in preview:
        for aid in record.get("source_annotation_ids") or []:
            if aid:
                preview_by_aid[str(aid)].append(record)
        for accessory in record.get("accessories") or []:
            preview_pts[str(accessory.get("pt") or "")].append(record)

    maintained: list[dict[str, Any]] = []
    reconstructed: list[dict[str, Any]] = []
    eliminated: list[dict[str, Any]] = []
    matched_preview_ids: set[int] = set()
    for old in current:
        aid = str(old.get("annotation_id") or "")
        old_pts = sorted(str(item.get("pt") or "") for item in old.get("accessories") or [])
        matches = preview_by_aid.get(aid, [])
        exact = preview_by_identity.get(identity(old))
        if exact:
            maintained.append({"annotation_id": aid, "identity": identity(old)})
            matched_preview_ids.add(id(exact))
        elif matches:
            new_pts = sorted({
                str(item.get("pt") or "") for record in matches
                for item in record.get("accessories") or []
            })
            if old_pts == new_pts:
                maintained.append({"annotation_id": aid, "preview_pts": new_pts})
            else:
                reconstructed.append({
                    "annotation_id": aid, "page": old.get("page"),
                    "current_pts": old_pts, "preview_pts": new_pts,
                    "reason": "STRUCTURAL_EVIDENCE_REBUILT",
                })
            matched_preview_ids.update(id(record) for record in matches)
        else:
            reason = elimination_reason(old, origins.get(aid, "UNKNOWN"), annotations, preview_pts)
            eliminated.append({
                "annotation_id": aid, "page": old.get("page"),
                "table_id": old.get("table_id"),
                "table_title": old.get("product_context", {}).get("table_title", ""),
                "component_type": old.get("component", {}).get("type", ""),
                "pts": old_pts, "elimination_reason": reason,
            })

    new_relations = [
        {"page": record["page"], "table_id": record["table_id"],
         "table_title": record["product_context"]["table_title"],
         "component_type": record["component"]["type"],
         "accessory_pts": [item["pt"] for item in record["accessories"]],
         "source_channel": record["source_channel"]}
        for record in preview if id(record) not in matched_preview_ids
    ]
    recovered = [
        record for record in new_relations if record["accessory_pts"]
    ] + [record for record in reconstructed if record["preview_pts"]]
    reasons = Counter(item["elimination_reason"] for item in eliminated)
    current_pts = {
        str(item.get("pt") or "") for record in current
        for item in record.get("accessories") or [] if item.get("pt")
    }
    preview_pt_set = {
        str(item.get("pt") or "") for record in preview
        for item in record.get("accessories") or [] if item.get("pt")
    }
    return {
        "current_total": len(current), "preview_total": len(preview),
        "maintained": len(maintained), "eliminated": len(eliminated),
        "removed": len(eliminated),
        "reconstructed": len(reconstructed), "new": len(new_relations),
        "changed_scope": 0,
        "elimination_reasons": dict(reasons),
        "relations_maintained_count": len(maintained),
        "relations_maintained": maintained,
        "relations_eliminated_count": len(eliminated),
        "relations_eliminated": eliminated,
        "eliminated_by_reason": dict(reasons),
        "relations_reconstructed_from_structured_row_count": len(reconstructed),
        "relations_reconstructed_from_structured_row": reconstructed,
        "new_relations_count": len(new_relations),
        "eliminated_relations": eliminated,
        "reconstructed_relations": reconstructed,
        "new_relations": new_relations,
        "recovered_relations": recovered,
        "pt_accessori_persi_count": len(current_pts - preview_pt_set),
        "pt_accessori_persi": sorted(current_pts - preview_pt_set),
        "pt_accessori_recuperati_count": len(preview_pt_set - current_pts),
        "pt_accessori_recuperati": sorted(preview_pt_set - current_pts),
    }


def relation_edges(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for record in records:
        accessories = record.get("accessories") or []
        if accessories:
            for accessory in accessories:
                edges.append({
                    "page": int(record.get("page") or 0),
                    "product_table_id": str(record.get("table_id") or ""),
                    "source_channel": str(record.get("source_channel") or ""),
                    "accessory_pt": str(accessory.get("pt") or ""),
                    "model": str(accessory.get("model") or ""),
                    "scope_type": str(
                        accessory.get("scope_type") or record.get("scope_type") or "UNKNOWN"
                    ),
                    "applies_to_models": sorted(
                        str(model) for model in (
                            accessory.get("applies_to_models")
                            or record.get("applies_to_models")
                            or []
                        )
                    ),
                })
        else:
            for aid in record.get("source_annotation_ids") or [""]:
                edges.append({
                    "page": int(record.get("page") or 0),
                    "product_table_id": str(record.get("table_id") or ""),
                    "source_channel": str(record.get("source_channel") or ""),
                    "annotation_id": str(aid or ""),
                    "accessory_pt": "",
                    "model": "",
                    "scope_type": str(record.get("scope_type") or "UNKNOWN"),
                    "applies_to_models": sorted(
                        str(model) for model in record.get("applies_to_models") or []
                    ),
                })
    return edges


def compare_preview_versions(
    previous: list[dict[str, Any]], current: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_edges = relation_edges(previous)
    current_edges = relation_edges(current)

    def base(edge: dict[str, Any]) -> tuple[Any, ...]:
        if edge.get("accessory_pt"):
            return (
                edge["page"], edge["product_table_id"], edge["source_channel"],
                edge["accessory_pt"],
            )
        return (
            edge["page"], edge["product_table_id"], edge["source_channel"],
            edge.get("annotation_id") or "",
        )

    previous_by_base = {base(edge): edge for edge in previous_edges}
    current_by_base = {base(edge): edge for edge in current_edges}
    maintained: list[dict[str, Any]] = []
    changed_scope: list[dict[str, Any]] = []
    for key in sorted(previous_by_base.keys() & current_by_base.keys(), key=str):
        old, new = previous_by_base[key], current_by_base[key]
        if (
            old["scope_type"] != new["scope_type"]
            or old["applies_to_models"] != new["applies_to_models"]
        ):
            changed_scope.append({"key": list(key), "before": old, "after": new})
        else:
            maintained.append(new)
    removed = [
        previous_by_base[key]
        for key in sorted(previous_by_base.keys() - current_by_base.keys(), key=str)
    ]
    new = [
        current_by_base[key]
        for key in sorted(current_by_base.keys() - previous_by_base.keys(), key=str)
    ]
    current_pt_lookup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in current_edges:
        if edge.get("accessory_pt"):
            current_pt_lookup[(edge["source_channel"], edge["accessory_pt"])].append(edge)
    reconstructed = [
        {
            "before": edge,
            "after": current_pt_lookup[(edge["source_channel"], edge["accessory_pt"])],
        }
        for edge in removed
        if edge.get("accessory_pt")
        and current_pt_lookup.get((edge["source_channel"], edge["accessory_pt"]))
    ]
    return {
        "granularity": "RELATION_EDGE",
        "previous_records": len(previous),
        "current_records": len(current),
        "previous_edges": len(previous_edges),
        "current_edges": len(current_edges),
        "maintained": len(maintained),
        "removed": len(removed),
        "reconstructed": len(reconstructed),
        "new": len(new),
        "changed_scope": len(changed_scope),
        "maintained_relations": maintained,
        "removed_relations": removed,
        "reconstructed_relations": reconstructed,
        "new_relations": new,
        "changed_scope_relations": changed_scope,
    }


def accessories_for(
    records: list[dict[str, Any]], page: int, title: str
) -> list[dict[str, Any]]:
    return [
        accessory for record in records
        if record["page"] == page
        and title.upper() in record["product_context"]["table_title"].upper()
        for accessory in record.get("accessories") or []
    ]


def regression_checks(
    records: list[dict[str, Any]], governor_audit: list[dict[str, Any]],
) -> dict[str, Any]:
    spg = accessories_for(records, 620, "SPG")
    sge = accessories_for(records, 620, "SGE")
    mpg90 = accessories_for(records, 621, "MPG_C 90x90")
    mpg60 = accessories_for(records, 621, "MPG_CS 60x60")
    round_flow = accessories_for(records, 474, "ROUND FLOW")
    compact = accessories_for(records, 473, "60x60")
    super_slim = accessories_for(records, 546, "SUPER SLIM 90x90")
    mca4u = [
        accessory for record in records
        if record["page"] in {541, 546}
        and any("MCA4U" in model.upper() for model in record["product_context"]["models"])
        for accessory in record.get("accessories") or []
    ]

    def pts(items: list[dict[str, Any]]) -> set[str]:
        return {str(item.get("pt") or "") for item in items}

    def models(items: list[dict[str, Any]]) -> set[str]:
        return {str(item.get("model") or "") for item in items}

    def model_pt_pairs(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
        return {
            (str(item.get("model") or ""), str(item.get("pt") or ""))
            for item in items
        }

    daikin_pairs = model_pt_pairs(round_flow + compact)
    expected_daikin_grid_pairs = {
        ("BYCQ140E", "99759964"),
        ("BYCQ140EGF", "99761028"),
        ("BYCQ140EP", "99761035"),
        ("BYCQ140EPB", "99761042"),
        ("BYFQ60CS", "99718268"),
        ("BYFQ60CW", "99718275"),
    }
    daikin_grid_pairs = {
        pair for pair in daikin_pairs
        if pair[0].upper().startswith(("BYCQ140", "BYFQ60"))
    }
    daikin_finishes_distinct = expected_daikin_grid_pairs <= daikin_grid_pairs

    def pts_for_table(table_id: str) -> list[str]:
        return sorted({
            str(item.get("pt") or "")
            for record in records if record.get("table_id") == table_id
            for item in record.get("accessories") or [] if item.get("pt")
        })

    exclusive_ids = [
        "ANN_P0232_0769", "ANN_P0232_0770", "ANN_P0233_0771",
        "ANN_P0234_0772", "ANN_P0238_0773",
    ]
    exclusive_records = [
        record for record in records
        if set(str(aid) for aid in record.get("source_annotation_ids") or []) & set(exclusive_ids)
    ]
    family_externa_pts = pts_for_table("PDF_P0052_15AF0BE982")
    attacco_fumi_pts = pts_for_table("PDF_P0080_5D6F5491C6")
    curva_nuos_pts = pts_for_table("PDF_P0125_F894064DD2")
    start_ln = accessories_for(records, 57, "START LN")

    checks = {
        "aermec_wifi_page_620": {
            "SPG": {"pts": sorted(pts(spg)), "models": sorted(models(spg))},
            "SGE": {"pts": sorted(pts(sge)), "models": sorted(models(sge))},
            "PASS": "50253210" in pts(spg) and "50021123" in pts(sge)
                    and all(item.get("source_channel") == CHANNEL_ROW for item in spg + sge),
        },
        "aermec_cassette": {
            "MPG_C_90x90_pts": sorted(pts(mpg90)),
            "MPG_CS_60x60_pts": sorted(pts(mpg60)),
            "PASS": pts(mpg90) == {"99794507"} and pts(mpg60) == {"99794583"},
        },
        "daikin": {
            "round_flow_models": sorted(models(round_flow)),
            "compact_models": sorted(models(compact)),
            "grid_model_pt_pairs": [
                {"model": model, "pt": pt} for model, pt in sorted(daikin_grid_pairs)
            ],
            "finishes_kept_distinct": daikin_finishes_distinct,
            "PASS": bool(round_flow) and bool(compact)
                    and all("BYFQ" not in item["model"].upper() for item in round_flow)
                    and all("BYCQ" not in item["model"].upper() for item in compact)
                    and any("BYCQ" in item["model"].upper() for item in round_flow)
                    and any("BYFQ" in item["model"].upper() for item in compact)
                    and daikin_finishes_distinct,
        },
        "midea": {
            "super_slim_models": sorted(models(super_slim)),
            "mca4u_models": sorted(models(mca4u)),
            "super_slim_model_pt_pairs": [
                {"model": model, "pt": pt} for model, pt in sorted(model_pt_pairs(super_slim))
            ],
            "compact_model_pt_pairs": [
                {"model": model, "pt": pt} for model, pt in sorted(model_pt_pairs(mca4u))
            ],
            "PASS": {normalized(x) for x in models(super_slim)} >= {
                        normalized("T-MBQ4-04A1"), normalized("T-MBQ4-04AWD")}
                    and normalized("T-MBQ4-03A") in {normalized(x) for x in models(mca4u)}
                    and all("TMBQ403" not in normalized(item["model"]) for item in super_slim)
                    and all("TMBQ404" not in normalized(item["model"]) for item in mca4u),
        },
        "negative_text": {
            "normative_false_positive_count": sum(
                "CONFORME ALLA NORMATIVA EN501/16" in str(record.get("raw_text") or "").upper()
                for record in records
            ),
            "flame_false_positive_count": sum(
                "IDEALE PER CALORE DA FIAMMA" in str(record.get("raw_text") or "").upper()
                for record in records
            ),
            "package_keyword_false_positive_count": sum(
                "CONFEZIONE50GUANTI" in normalized(record.get("raw_text") or "")
                for record in records
            ),
        },
    }
    checks["negative_text"]["PASS"] = not any(checks["negative_text"].values())
    blocking = {
        "01_family_externa_absent_50234561": {
            "expected": "ABSENT", "actual": family_externa_pts,
            "PASS": "50234561" not in family_externa_pts,
        },
        "02_attacco_fumi_absent_50171361": {
            "expected": "ABSENT", "actual": attacco_fumi_pts,
            "PASS": "50171361" not in attacco_fumi_pts,
        },
        "03_curva_nuos_absent_99328726": {
            "expected": "ABSENT", "actual": curva_nuos_pts,
            "PASS": "99328726" not in curva_nuos_pts,
        },
        "04_exclusive_white_0769_no_accessorio": {
            "annotation_ids": ["ANN_P0232_0769"],
            "actual_records": [record.get("component") for record in exclusive_records if "ANN_P0232_0769" in record.get("source_annotation_ids", [])],
            "PASS": not any(
                "ANN_P0232_0769" in record.get("source_annotation_ids", [])
                and record.get("component", {}).get("type") == "ACCESSORIO"
                for record in records
            ),
        },
        "05_exclusive_white_related_ids_no_accessorio": {
            "annotation_ids": exclusive_ids[1:],
            "actual_records": [record.get("component") for record in exclusive_records],
            "PASS": not any(
                set(record.get("source_annotation_ids") or []) & set(exclusive_ids[1:])
                and record.get("component", {}).get("type") == "ACCESSORIO"
                for record in records
            ),
        },
        "06_start_ln_retains_gpl_kits": {
            "expected_pts": ["99784997", "99785000"],
            "actual_pts": sorted(pts(start_ln)),
            "PASS": {"99784997", "99785000"} <= pts(start_ln),
        },
        "07_aermec_wifi_rows": checks["aermec_wifi_page_620"],
        "08_aermec_cassette_separation": checks["aermec_cassette"],
        "09_daikin_dimension_finish_separation": checks["daikin"],
        "10_midea_dimension_separation": checks["midea"],
    }
    known_issue_regressions = {
        "family_externa_50234561": {
            "expected": "ABSENT", "actual": [pt for pt in family_externa_pts if pt == "50234561"],
            "PASS": "50234561" not in family_externa_pts,
        },
        "attacco_fumi_50171361": {
            "expected": "ABSENT", "actual": [pt for pt in attacco_fumi_pts if pt == "50171361"],
            "PASS": "50171361" not in attacco_fumi_pts,
        },
        "curva_nuos_99328726": {
            "expected": "ABSENT", "actual": [pt for pt in curva_nuos_pts if pt == "99328726"],
            "PASS": "99328726" not in curva_nuos_pts,
        },
        "exclusive_white_false_component": {
            "annotation_ids": exclusive_ids,
            "expected": "REJECTED_NON_COMPONENT",
            "actual_component_records": len(exclusive_records),
            "PASS": not exclusive_records,
        },
    }
    emitted_weak_governor = [
        record for record in records
        if record.get("source_channel") == CHANNEL_SECTION
        and (
            record.get("governor_evidence") not in {
                "SAME_PRODUCT_BLOCK", "EXPLICIT_TARGET_TEXT",
                "TABLE_HEADER_GOVERNS_SECTION", "ROW_SCOPED_REFERENCE",
            }
            or float(record.get("governor_confidence") or 0) < 1.0
        )
    ]
    exclusive_component_excluded = [
        record for record in records
        if record.get("component", {}).get("status") == "COMPONENT_EXCLUDED"
        and "ESCLUSIV" in str(record.get("raw_text") or "").upper()
    ]
    conditions = {
        "all_positive_and_negative_hard_asserts_pass": all(item["PASS"] for item in blocking.values()),
        "no_known_wrong_relation_remains": all(item["PASS"] for item in known_issue_regressions.values()),
        "no_ambiguous_governor_emitted_at_confidence_1": not emitted_weak_governor,
        "no_component_excluded_from_esclusivamente": not exclusive_component_excluded,
    }
    checks["blocking_regression_checks"] = blocking
    checks["known_issue_regressions"] = known_issue_regressions
    checks["production_ready_conditions"] = conditions
    checks["all_pass"] = all(conditions.values())
    checks["production_ready"] = all(conditions.values())
    checks["emitted_weak_governor_records"] = len(emitted_weak_governor)
    checks["exclusive_component_excluded_records"] = len(exclusive_component_excluded)
    checks["ambiguous_governor_candidates"] = sum(
        item.get("decision") == "AMBIGUOUS" for item in governor_audit
    )
    return checks


def validate(records: list[dict[str, Any]], valid_family_keys: set[str]) -> None:
    for record in records:
        assert record["source_channel"] in CHANNELS
        assert record["association_confidence_reason"]
        assert record["scope_type"] in {"TABLE_WIDE", "MODEL_SCOPED", "ROW_SCOPED", "UNKNOWN"}
        assert isinstance(record["applies_to_models"], list)
        assert record["component"]["catalog_inclusion_status"] in {
            "INCLUDED", "EXCLUDED", "OPTIONAL", "UNKNOWN",
        }
        assert isinstance(record["component"]["mandatory_pairing"], bool)
        assert record["component"]["bom_action"] in {
            "NONE", "ADD_IF_SOLD_TITLE_INCLUDES", "ADD_SEPARATE_INCLUDED_COMPONENT", "REVIEW",
        }
        key = record["product_context"]["family_key"]
        assert not key or key in valid_family_keys
        for accessory in record.get("accessories") or []:
            assert accessory["source_channel"] in {CHANNEL_ROW, CHANNEL_SECTION}
            assert accessory["association_confidence_reason"]
            assert accessory["page"] == record["page"]
            assert accessory["table_id"] == record["table_id"]
            assert accessory["accessory_bbox"] and accessory["pt_bbox"] and accessory["model_bbox"]
            if accessory["source_channel"] == CHANNEL_ROW:
                assert accessory["optional_bbox"]
            if accessory["source_channel"] == CHANNEL_SECTION:
                assert accessory["accessory_section_title"]
                assert accessory["governor_evidence"] in {
                    "SAME_PRODUCT_BLOCK", "EXPLICIT_TARGET_TEXT",
                    "TABLE_HEADER_GOVERNS_SECTION", "ROW_SCOPED_REFERENCE",
                }
                assert accessory["governor_confidence"] == 1.0
                assert accessory["product_table_id"] == record["table_id"]
                assert accessory["accessory_table_id"]
                assert accessory["source_occurrences"]


def main() -> None:
    started = time.time()
    input_hashes = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in (
            ANNOTATIONS_PATH, ORIGIN_AUDIT_PATH, COMPONENT_SAFETY_PATH,
            TABLE_CONTEXT_PATH, LAYOUT_PATH, CURRENT_PATH,
            PREVIOUS_PREVIEW_PATH, PREVIOUS_REPORT_PATH,
        )
    }
    annotations = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    annotations_by_id = {str(item.get("annotation_id") or ""): item for item in annotations}
    audit = json.loads(ORIGIN_AUDIT_PATH.read_text(encoding="utf-8"))
    origins = {
        str(item.get("annotation_id") or ""): str(item.get("origin_check") or "UNKNOWN")
        for item in audit.get("annotations_with_source_graphics") or []
    }
    component_safety = json.loads(COMPONENT_SAFETY_PATH.read_text(encoding="utf-8"))
    safety_origins = {
        str(item.get("annotation_id") or ""): str(item.get("origin_check") or "UNKNOWN")
        for item in component_safety.get("records") or []
    }
    context = json.loads(TABLE_CONTEXT_PATH.read_text(encoding="utf-8"))
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    previous_preview = json.loads(PREVIOUS_PREVIEW_PATH.read_text(encoding="utf-8"))
    previous_report = json.loads(PREVIOUS_REPORT_PATH.read_text(encoding="utf-8"))
    appearances = context_appearances(context)
    pages = load_layout(set(context))
    tables, geometry_rejected = build_tables(appearances, pages)
    product_tables = [table for table in tables if not table.accessory]
    accessory_tables = [table for table in tables if table.accessory]

    red_records, red_by_parent, red_rejected = build_red_records(
        annotations, origins, product_tables, pages,
    )
    inline_records = build_inline_rows(product_tables, pages)
    section_records, consumed_red, section_rejected, governor_audit = build_accessory_sections(
        accessory_tables, tables, pages, red_by_parent,
    )
    red_records = [
        record for record in red_records
        if not consumed_red.intersection(str(x) for x in record["source_annotation_ids"] if x)
    ]
    preview, duplicate_rejections = deduplicate_same_scope(
        [*red_records, *inline_records, *section_records],
    )
    preview = sorted(
        preview,
        key=lambda record: (
            record["page"], record["table_id"], record["component"]["type"],
            record["source_channel"],
        ),
    )

    valid_family_keys = {
        str(raw.get("family_key") or "")
        for base in context.values()
        for raw in [base, *(base.get("alternate_table_contexts") or [])]
        if raw.get("family_key")
    }
    validate(preview, valid_family_keys)
    comparison = compare_current(preview, current, origins, annotations_by_id)
    previous_comparison = compare_preview_versions(previous_preview, preview)
    current_edge_keys = {
        (
            int(record.get("page") or 0), str(record.get("table_id") or ""),
            str(item.get("pt") or ""),
        )
        for record in current for item in record.get("accessories") or [] if item.get("pt")
    }
    production_changed_scope = [
        edge for edge in relation_edges(preview)
        if edge.get("accessory_pt")
        and (edge["page"], edge["product_table_id"], edge["accessory_pt"]) in current_edge_keys
        and edge["scope_type"] != "UNKNOWN"
    ]
    comparison["changed_scope"] = len(production_changed_scope)
    comparison["changed_scope_relations"] = production_changed_scope
    checks = regression_checks(preview, governor_audit)
    channel_counts = Counter(record["source_channel"] for record in preview)
    source_evidence_counts = Counter(
        source for record in preview for source in record.get("sources") or []
    )
    intents = Counter(record["component"]["relation_intent"] for record in preview)
    rejected = [*geometry_rejected, *section_rejected, *red_rejected]
    all_rejections = [*rejected, *duplicate_rejections]
    non_red_structured = [
        accessory
        for record in preview if record["source_channel"] != CHANNEL_RED
        for accessory in record.get("accessories") or []
        if not accessory.get("source_colors")
        or any(color not in {"#EE2E29", "#FF0000"} for color in accessory.get("source_colors") or [])
    ]
    red_non_component_ids = sorted(
        str(annotation.get("annotation_id") or "")
        for annotation in annotations
        if origins.get(str(annotation.get("annotation_id") or "")) == "RED_TEXT_CONFIRMED"
        and annotation.get("annotation_type") == "OTHER"
    )
    previous_sections = [
        record for record in previous_preview
        if record.get("source_channel") == CHANNEL_SECTION
    ]
    previous_by_accessory_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in previous_sections:
        accessory_table_id = str((record.get("accessory_section") or {}).get("table_id") or "")
        if accessory_table_id:
            previous_by_accessory_table[accessory_table_id].append(record)
    for item in governor_audit:
        previous_records = previous_by_accessory_table.get(item["accessory_table_id"], [])
        item["was_in_previous_safe_preview"] = bool(previous_records)
        item["previous_product_table_ids"] = sorted({
            str(record.get("table_id") or "") for record in previous_records
        })
    governor_by_id = {item["accessory_table_id"]: item for item in governor_audit}
    previous_section_decisions = []
    for record in previous_sections:
        accessory_table_id = str((record.get("accessory_section") or {}).get("table_id") or "")
        audit_item = governor_by_id.get(accessory_table_id)
        same_parent = bool(
            audit_item
            and audit_item["decision"] == "ACCEPTED"
            and audit_item["product_table_id"] == record.get("table_id")
        )
        previous_section_decisions.append({
            "previous_product_table_id": record.get("table_id"),
            "previous_product_title": (record.get("product_context") or {}).get("table_title"),
            "accessory_table_id": accessory_table_id,
            "accessory_title": (record.get("accessory_section") or {}).get("table_title"),
            "accessory_pts": [item.get("pt") for item in record.get("accessories") or []],
            "decision": (
                "RETAINED" if same_parent
                else "RECONSTRUCTED" if audit_item and audit_item["decision"] == "ACCEPTED"
                else audit_item["decision"] if audit_item else "AMBIGUOUS"
            ),
            "new_product_table_id": audit_item["product_table_id"] if audit_item else None,
            "reason": audit_item["reason"] if audit_item else "AMBIGUOUS_GEOMETRY",
            "governor_evidence": audit_item["governor_evidence"] if audit_item else None,
        })
    retained_previous_sections = sum(
        item["decision"] == "RETAINED" for item in previous_section_decisions
    )
    rejected_previous_sections = sum(
        item["decision"] in {"REJECTED", "AMBIGUOUS"} for item in previous_section_decisions
    )
    strictly_rejected_previous_sections = sum(
        item["decision"] == "REJECTED" for item in previous_section_decisions
    )
    ambiguous_previous_sections = sum(
        item["decision"] == "AMBIGUOUS" for item in previous_section_decisions
    )
    reconstructed_previous_sections = sum(
        item["decision"] == "RECONSTRUCTED" for item in previous_section_decisions
    )
    ambiguous_governor_count = sum(
        item["decision"] == "AMBIGUOUS" for item in governor_audit
    )
    variant_finish_removed = [
        item for item in red_rejected if item.get("reason") == "VARIANT_OR_FINISH_LIMITATION"
    ]
    scope_counts = Counter(record.get("scope_type") or "UNKNOWN" for record in preview)
    accepted_governors = [item for item in governor_audit if item["decision"] == "ACCEPTED"]
    removed_governors = [
        item for item in previous_section_decisions if item["decision"] in {"REJECTED", "AMBIGUOUS", "RECONSTRUCTED"}
    ]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": "SAFE_PREVIEW_READ_ONLY_INPUTS",
        "input_sha256": input_hashes,
        "input_consistency": {
            "annotations": len(annotations),
            "origin_audit_records": len(origins),
            "component_safety_records": len(safety_origins),
            "origin_vs_component_safety_mismatches": sorted(
                aid for aid, origin in safety_origins.items() if origins.get(aid) != origin
            ),
            "table_context_records": len(context),
            "layout_pages": len(pages),
        },
        "total_preview_records": len(preview),
        "by_source_channel": {channel: channel_counts.get(channel, 0) for channel in CHANNELS},
        "accessory_relations_total": sum(bool(record["accessories"]) for record in preview),
        "red_editorial_records_total": channel_counts.get(CHANNEL_RED, 0),
        "ambiguous_governor_count": ambiguous_governor_count,
        "wrong_previous_governor_relations_removed": rejected_previous_sections + reconstructed_previous_sections,
        "variant_finish_false_positives_removed": len(variant_finish_removed),
        "variant_finish_false_positive_records": variant_finish_removed,
        "deduplicated_same_scope_count": len(duplicate_rejections),
        "deduplicated_same_scope_records": duplicate_rejections,
        "model_scoped_relations": scope_counts.get("MODEL_SCOPED", 0),
        "row_scoped_relations": scope_counts.get("ROW_SCOPED", 0),
        "table_wide_relations": scope_counts.get("TABLE_WIDE", 0),
        "unknown_scope_relations": scope_counts.get("UNKNOWN", 0),
        "by_evidence_source": {channel: source_evidence_counts.get(channel, 0) for channel in CHANNELS},
        "relations_with_accessory_pt": sum(bool(record["accessories"]) for record in preview),
        "relations_without_accessory_pt": sum(not record["accessories"] for record in preview),
        "required_count": intents.get("ACCESSORY_REQUIRED", 0),
        "optional_count": intents.get("ACCESSORY_OPTIONAL", 0),
        "included_separate_count": intents.get("ACCESSORY_INCLUDED_SEPARATE", 0),
        "feature_only_count": intents.get("FEATURE_ONLY", 0),
        "no_component_code_count": intents.get("NO_COMPONENT_CODE", 0),
        "non_red_structured_rows_kept": len(non_red_structured),
        "non_red_structured_rows_kept_records": [
            {
                "page": item["page"], "table_id": item["table_id"],
                "pt": item["pt"], "model": item["model"],
                "source_channel": item["source_channel"],
                "source_colors": item.get("source_colors") or [],
            }
            for item in non_red_structured
        ],
        "non_red_keyword_false_positives_rejected": comparison["eliminated_by_reason"].get(
            "KEYWORD_FALSE_POSITIVE", 0,
        ),
        "red_annotations_rejected_as_non_component": len(red_non_component_ids),
        "red_annotations_rejected_as_non_component_ids": red_non_component_ids,
        "ambiguous_cases_count": len(rejected),
        "ambiguous_cases": rejected,
        "comparison": {
            "vs_production_current": comparison,
            "vs_previous_safe_preview": previous_comparison,
        },
        "comparison_with_current_dataset": comparison,
        "comparison_with_previous_safe_preview": previous_comparison,
        "previous_safe_preview_baseline": {
            "total_preview_records": previous_report.get("total_preview_records"),
            "by_source_channel": previous_report.get("by_source_channel"),
            "explicit_accessory_sections": len(previous_sections),
            "retained_with_same_governor": retained_previous_sections,
            "reconstructed_with_new_governor": reconstructed_previous_sections,
            "rejected_governor_not_demonstrated": strictly_rejected_previous_sections,
            "ambiguous_governor": ambiguous_previous_sections,
            "rejected_or_ambiguous_governor": rejected_previous_sections,
        },
        "accessory_section_governor_audit": governor_audit,
        "previous_accessory_section_decisions": previous_section_decisions,
        "governor_removed_examples": removed_governors[:100],
        "governor_strong_accepted_examples": accepted_governors[:100],
        "rejected_structural_candidates_count": len(all_rejections),
        "rejected_structural_candidates_by_reason": dict(Counter(x["reason"] for x in all_rejections)),
        "rejected_structural_candidates": all_rejections,
        "blocking_regression_checks": checks["blocking_regression_checks"],
        "known_issue_regressions": checks["known_issue_regressions"],
        "production_ready": checks["production_ready"],
        "production_ready_conditions": checks["production_ready_conditions"],
        "schema_notes": {
            "required_for_sale": "Mandatory commercial pairing; it does not mean shipped in the base product.",
            "mandatory_pairing": "True only for an explicit obligation to pair/buy separately.",
            "catalog_inclusion_status": "Describes inclusion in the base product independently of mandatory pairing.",
            "bom_action": "Preview-only guidance; no BOM was modified.",
        },
        "regression_checks": checks,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    PREVIEW_PATH.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    after_hashes = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in (
            ANNOTATIONS_PATH, ORIGIN_AUDIT_PATH, COMPONENT_SAFETY_PATH,
            TABLE_CONTEXT_PATH, LAYOUT_PATH, CURRENT_PATH,
            PREVIOUS_PREVIEW_PATH, PREVIOUS_REPORT_PATH,
        )
    }
    if after_hashes != input_hashes:
        raise RuntimeError("An input dataset changed while building the preview")
    print(json.dumps({
        "total_preview_records": len(preview),
        "by_source_channel": report["by_source_channel"],
        "relations_with_accessory_pt": report["relations_with_accessory_pt"],
        "comparison": {k: comparison[k] for k in ("maintained", "eliminated", "reconstructed", "new")},
        "regression_all_pass": checks["all_pass"],
        "production_ready": checks["production_ready"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
