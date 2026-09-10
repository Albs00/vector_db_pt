"""Blocking regression suite for Safe Preview V3.3."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3_report.json"
ROLE_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", re.I)


def signature(value: str) -> str:
    value = ROLE_PREFIX_RE.sub("", str(value))
    value = re.sub(r"\([^)]*\)\s*$", "", value)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class TestSafePreviewV33(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def records_for_pt(self, pt: str):
        return [
            row for row in self.records
            if any(str(item.get("pt")) == pt for item in row.get("accessories") or [])
        ]

    def test_report_and_readiness(self):
        self.assertEqual(len(self.records), self.report["v3_3_total_records"])
        self.assertTrue(self.report["production_ready"])
        self.assertTrue(all(self.report["production_ready_conditions"].values()))
        self.assertTrue(all(
            result["PASS"] for result in self.report["regression_results"].values()
        ))

    def test_scope_resolution_reason_schema(self):
        allowed = {
            "EXPLICIT_COMPATIBLE_MODEL_REFERENCE", "EXPLICIT_ROW_REFERENCE",
            "PRODUCT_TABLE_ROLE_INFERENCE", "TABLE_WIDE_NO_MODEL_LIMIT",
            "UNKNOWN_REJECTED",
        }
        for row in self.records:
            self.assertIn(row["scope_resolution_reason"], allowed)
            for accessory in row.get("accessories") or []:
                self.assertEqual(row["scope_resolution_reason"], accessory["scope_resolution_reason"])
                self.assertEqual(row["scope_type"], accessory["scope_type"])
                self.assertEqual(row["applies_to_models"], accessory["applies_to_models"])

    def test_haier_50370139_model_scope(self):
        rows = self.records_for_pt("50370139")
        self.assertEqual(1, len(rows))
        self.assertEqual(563, rows[0]["page"])
        self.assertEqual("MODEL_SCOPED", rows[0]["scope_type"])
        self.assertEqual(
            {"AB25S2SA1FA", "AB35S2SA1FA"},
            {signature(model) for model in rows[0]["applies_to_models"]},
        )

    def test_haier_50370160_model_scope(self):
        rows = self.records_for_pt("50370160")
        self.assertEqual(2, len(rows))
        by_page = {row["page"]: row for row in rows}
        self.assertEqual({563, 567}, set(by_page))
        self.assertEqual(
            {"AB50S2SA1FA", "AB71S2SA1FA"},
            {signature(model) for model in by_page[563]["applies_to_models"]},
        )
        self.assertEqual(
            {"AB71S2SA1FA"},
            {signature(model) for model in by_page[567]["applies_to_models"]},
        )
        self.assertTrue(all(row["scope_type"] == "MODEL_SCOPED" for row in rows))

    def test_explicit_model_reference_is_exact_and_not_table_wide(self):
        rows = [row for row in self.records if row.get("accessory_model_reference")]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual("MODEL_SCOPED", row["scope_type"])
            self.assertEqual(
                "EXACT_NORMALIZED_MODEL_CODE", row["model_reference_match_method"]
            )
            reference_signatures = {signature(ref) for ref in row["accessory_model_reference"]}
            self.assertTrue(all(
                signature(model) in reference_signatures
                for model in row["applies_to_models"]
            ))

    def test_panasonic_cz_kpy4_scope_recovery(self):
        rows = self.records_for_pt("50117277")
        self.assertEqual(3, len(rows))
        families = {row["product_context"]["family_key"] for row in rows}
        self.assertEqual({
            "PANASONIC_CASSETTA_60X60",
            "PANASONIC_PACI_NX_STANDARD_CASSETTA_60X60",
            "PANASONIC_PACI_NX_ELITE_CASSETTA_60X60",
        }, families)
        for row in rows:
            self.assertEqual("CASSETTE_UI", row["attachment_target"])
            self.assertEqual("TABLE_WIDE", row["scope_type"])
            self.assertEqual("PRODUCT_TABLE_ROLE_INFERENCE", row["scope_resolution_reason"])
            self.assertTrue(row["applies_to_models"])
            self.assertTrue(all(not re.match(r"^\s*U\.?E\.?\b", str(model), re.I)
                                for model in row["applies_to_models"]))

    def test_panasonic_standard_exact_models(self):
        row = next(
            row for row in self.records_for_pt("50117277")
            if row["product_context"]["family_key"] == "PANASONIC_PACI_NX_STANDARD_CASSETTA_60X60"
        )
        self.assertEqual(
            {"S25PY3E", "S36PY3E", "S50PY3E", "S60PY3E"},
            {signature(model) for model in row["applies_to_models"]},
        )

    def test_cz_kpy4_never_propagates_to_other_panasonic_forms(self):
        for row in self.records_for_pt("50117277"):
            title = row["product_context"]["table_title"].upper()
            self.assertIn("CASSETTA", title)
            self.assertIn("60X60", title)
            self.assertNotIn("SPLIT", title)
            self.assertNotIn("CANALIZZ", title)
            self.assertNotIn("SOFFITTO", title)

    def test_v3_2_guards_remain_true(self):
        for row in self.records:
            self.assertEqual("AIR_AIR_CLIMATE", row["product_domain"])
            values = [str(model) for model in row.get("applies_to_models") or []]
            if row.get("attachment_target") in {"UI", "CASSETTE_UI"}:
                self.assertFalse(any(re.match(r"^\s*U\.?E\.?\b", model, re.I) for model in values))
            if row.get("attachment_target") == "UE":
                self.assertFalse(any(re.match(r"^\s*U\.?I\.?\b", model, re.I) for model in values))


if __name__ == "__main__":
    unittest.main()
