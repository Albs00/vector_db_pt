"""Blocking regression suite for Safe Preview V3.2."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_2_report.json"

HYDRONIC_RE = re.compile(
    r"HYDROBOX|HYDROTANK|ECODAN|HYDROKIT|IDRONIC|ARIA\s*[-/]?\s*ACQUA|"
    r"WATER\s+MODULE|BOLLITORE|ACCUMULO",
    re.I,
)
UI_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*I\s*[.]?", re.I)
UE_PREFIX_RE = re.compile(r"^\s*U\s*[.]?\s*E\s*[.]?", re.I)


class TestSafePreviewV32(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def accessory_model(record):
        accessories = record.get("accessories") or []
        return str(accessories[0].get("model") or "") if accessories else ""

    def matching(self, pattern: str):
        needle = pattern.upper()
        return [row for row in self.records if needle in self.accessory_model(row).upper()]

    def test_report_counts_and_production_ready(self):
        self.assertEqual(len(self.records), self.report["v3_2_total_records"])
        self.assertEqual(
            self.report["v3_1_total_records"] - self.report["hydronic_records_removed"],
            self.report["v3_2_total_records"],
        )
        self.assertTrue(self.report["production_ready"])
        self.assertTrue(all(self.report["production_ready_conditions"].values()))
        self.assertTrue(all(
            check["PASS"] for check in self.report["regression_results"].values()
        ))

    def test_only_air_air_domain_remains(self):
        self.assertTrue(self.records)
        self.assertEqual({"AIR_AIR_CLIMATE"}, {row["product_domain"] for row in self.records})
        for row in self.records:
            context = row.get("product_context") or {}
            text = " ".join([
                str(context.get("table_title") or ""), str(context.get("family_key") or ""),
                " ".join(str(model) for model in context.get("models") or []),
            ])
            self.assertIsNone(HYDRONIC_RE.search(text), text)

    def test_attachment_target_schema_and_confidence(self):
        targets = {"UI", "UE", "CASSETTE_UI", "SYSTEM", "UNKNOWN"}
        evidence = {
            "ACCESSORY_TYPE_DEFAULT", "EXPLICIT_TARGET_TEXT", "ROW_ALIGNMENT",
            "CATALOG_COMPONENT_ROLE", "TABLE_STRUCTURE", "UNKNOWN",
        }
        for row in self.records:
            self.assertIn(row["attachment_target"], targets)
            self.assertIn(row["attachment_target_evidence"], evidence)
            confidence = row["attachment_target_confidence"]
            self.assertGreaterEqual(confidence, 0)
            self.assertLessEqual(confidence, 1)
            if row["attachment_target_evidence"] == "ACCESSORY_TYPE_DEFAULT":
                self.assertEqual(0.9, confidence)
            if row["attachment_target"] == "UNKNOWN":
                self.assertLess(confidence, 0.8)
            for accessory in row.get("accessories") or []:
                self.assertEqual(row["attachment_target"], accessory["attachment_target"])
                self.assertEqual(row["applies_to_models"], accessory["applies_to_models"])

    def test_target_role_never_crosses_ui_ue(self):
        for row in self.records:
            target = row["attachment_target"]
            models = [str(model) for model in row.get("applies_to_models") or []]
            if target in {"UI", "CASSETTE_UI"}:
                self.assertFalse(any(UE_PREFIX_RE.search(model) for model in models), row)
            if target == "UE":
                self.assertFalse(any(UI_PREFIX_RE.search(model) for model in models), row)
            if target == "UNKNOWN" and row.get("scope_type") == "TABLE_WIDE":
                self.fail("UNKNOWN target must not propagate table-wide")

    def test_brp069_wifi_scope(self):
        gsi = [
            row for row in self.matching("BRP069B45")
            if "GSI LOW" in row["product_context"]["table_title"].upper()
        ]
        self.assertTrue(gsi)
        for row in gsi:
            self.assertEqual("UI", row["attachment_target"])
            self.assertEqual(
                {"U.I. FTXC25D", "U.I. FTXC35D"}, set(row["applies_to_models"])
            )
        c81 = self.matching("BRP069C81")
        self.assertTrue(c81)
        self.assertTrue(all(row["attachment_target"] == "UI" for row in c81))
        self.assertTrue(all(
            not any(UE_PREFIX_RE.search(str(model)) for model in row["applies_to_models"])
            for row in c81
        ))

    def test_daikin_cassette_grids_scope(self):
        for code, prefix in (("BYFQ60", "FFA"), ("BYCQ140", "FCAG")):
            rows = self.matching(code)
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual("CASSETTE_UI", row["attachment_target"])
                self.assertTrue(row["applies_to_models"])
                self.assertTrue(all(
                    re.sub(r"^U\.I\.\s*", "", str(model), flags=re.I).upper().startswith(prefix)
                    for model in row["applies_to_models"]
                ))

    def test_midea_cassette_grids_scope(self):
        for code, prefix in (("T-MBQ4-03", "MCA4U"), ("T-MBQ4-04", "MCD")):
            rows = self.matching(code)
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual("CASSETTE_UI", row["attachment_target"])
                self.assertTrue(all(
                    re.sub(r"^U\.I\.\s*", "", str(model), flags=re.I).upper().startswith(prefix)
                    for model in row["applies_to_models"]
                ))

    def test_aermec_and_haier_cassette_scope(self):
        for code in ("GLG40", "GLG40S"):
            rows = self.matching(code)
            self.assertTrue(rows)
            self.assertTrue(all(row["attachment_target"] == "CASSETTE_UI" for row in rows))
            self.assertTrue(all(
                not any(UE_PREFIX_RE.search(str(model)) for model in row["applies_to_models"])
                for row in rows
            ))
        for pt in ("50370139", "50370160"):
            rows = [
                row for row in self.records
                if any(item.get("pt") == pt for item in row.get("accessories") or [])
            ]
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual("CASSETTE_UI", row["attachment_target"])
                self.assertTrue(all(
                    re.sub(r"^U\.I\.\s*", "", str(model), flags=re.I).upper().startswith("AB")
                    for model in row["applies_to_models"]
                ))

    def test_total_colour_false_accessories_stay_absent(self):
        bad = [
            row for row in self.records
            if "TOTAL WHITE" in row.get("product_context", {}).get("table_title", "").upper()
            and any(
                "TOTAL BLACK" in str(item.get("accessory_section_title") or "").upper()
                or "TOTAL SILVER" in str(item.get("accessory_section_title") or "").upper()
                for item in row.get("accessories") or []
            )
        ]
        self.assertEqual([], bad)


if __name__ == "__main__":
    unittest.main()
