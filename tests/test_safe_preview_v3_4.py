"""Blocking regression suite for Safe Preview V3.4."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V33_PATH = ROOT / "catalog_component_relations_safe_preview_v3_3.json"
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v3_4.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_4_report.json"


def signature(value: str) -> str:
    value = re.sub(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", "", str(value), flags=re.I)
    value = re.sub(r"\([^)]*\)\s*$", "", value)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class TestSafePreviewV34(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v33 = json.loads(V33_PATH.read_text(encoding="utf-8"))
        cls.records = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def for_pt(self, pt: str):
        return [
            row for row in self.records
            if any(str(item.get("pt")) == pt for item in row.get("accessories") or [])
        ]

    def for_model(self, model: str):
        return [
            row for row in self.records
            if any(str(item.get("model") or "").upper() == model.upper()
                   for item in row.get("accessories") or [])
        ]

    def test_report_ready_and_counts(self):
        self.assertEqual(len(self.v33), len(self.records))
        self.assertEqual(len(self.records), self.report["v3_4_total_records"])
        self.assertEqual(
            len(self.records),
            sum(self.report["model_reference_type_distribution"].values()),
        )
        self.assertTrue(self.report["production_ready"])
        self.assertTrue(all(self.report["production_ready_conditions"].values()))
        self.assertTrue(all(
            result["PASS"] for result in self.report["regression_results"].values()
        ))

    def test_only_new_metadata_changed(self):
        top_added = {"model_reference_type", "model_reference_type_reason"}
        for before, after in zip(self.v33, self.records):
            stripped = {key: value for key, value in after.items() if key not in top_added}
            expected = copy_without_accessory_type_fields(before)
            actual = copy_without_accessory_type_fields(stripped)
            self.assertEqual(expected, actual)

    def test_haier_compatible_product_models(self):
        expectations = {
            "50370139": {"AB25S2SA1FA", "AB35S2SA1FA"},
            "50370160": {"AB50S2SA1FA", "AB71S2SA1FA"},
        }
        for pt, expected in expectations.items():
            rows = self.for_pt(pt)
            self.assertTrue(rows)
            self.assertTrue(all(
                row["model_reference_type"] == "COMPATIBLE_PRODUCT_MODEL"
                for row in rows
            ))
            actual = {
                signature(model)
                for row in rows for model in row.get("applies_to_models") or []
            }
            self.assertEqual(expected, actual)

    def test_daikin_and_aermec_codes_are_accessory_models(self):
        codes = (
            "BYFQ60CS", "BYFQ60CW", "BYCQ140E", "BYCQ140EP", "BYCQ140EPB",
            "GLG40", "GLG40S",
        )
        for code in codes:
            rows = self.for_model(code)
            self.assertTrue(rows, code)
            for row in rows:
                self.assertEqual("ACCESSORY_MODEL", row["model_reference_type"])
                self.assertNotIn(
                    signature(code),
                    {signature(model) for model in row.get("applies_to_models") or []},
                )

    def test_all_coded_accessory_rows_propagate_type_to_accessory(self):
        allowed = {"ACCESSORY_MODEL", "COMPATIBLE_PRODUCT_MODEL", "UNKNOWN"}
        for row in self.records:
            self.assertIn(row["model_reference_type"], allowed)
            for accessory in row.get("accessories") or []:
                self.assertEqual(row["model_reference_type"], accessory["model_reference_type"])


def copy_without_accessory_type_fields(record):
    result = json.loads(json.dumps(record))
    result.pop("model_reference_type", None)
    result.pop("model_reference_type_reason", None)
    for accessory in result.get("accessories") or []:
        accessory.pop("model_reference_type", None)
        accessory.pop("model_reference_type_reason", None)
    return result


if __name__ == "__main__":
    unittest.main()
