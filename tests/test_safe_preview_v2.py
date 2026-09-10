"""Blocking checks for the read-only component-relation Safe Preview v2."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v2.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v2_report.json"

STRONG_GOVERNORS = {
    "SAME_PRODUCT_BLOCK",
    "EXPLICIT_TARGET_TEXT",
    "TABLE_HEADER_GOVERNS_SECTION",
    "ROW_SCOPED_REFERENCE",
}
EXCLUSIVE_IDS = {
    "ANN_P0232_0769",
    "ANN_P0232_0770",
    "ANN_P0233_0771",
    "ANN_P0234_0772",
    "ANN_P0238_0773",
}


class TestSafePreviewV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preview = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def records(self, *, table_id: str | None = None, page: int | None = None,
                title_contains: str | None = None):
        rows = self.preview
        if table_id is not None:
            rows = [row for row in rows if row.get("table_id") == table_id]
        if page is not None:
            rows = [row for row in rows if row.get("page") == page]
        if title_contains is not None:
            needle = title_contains.casefold()
            rows = [
                row for row in rows
                if needle in (row.get("product_context", {}).get("table_title") or "").casefold()
            ]
        return rows

    @staticmethod
    def accessory_pairs(rows):
        return {
            (str(item.get("pt") or ""), str(item.get("model") or ""))
            for row in rows for item in row.get("accessories") or []
        }

    def test_all_blocking_regressions_and_readiness(self):
        checks = self.report["blocking_regression_checks"]
        self.assertEqual(10, len(checks))
        self.assertTrue(all(check["PASS"] for check in checks.values()))
        self.assertTrue(self.report["production_ready"])
        self.assertTrue(all(self.report["production_ready_conditions"].values()))
        self.assertTrue(all(
            check["PASS"] for check in self.report["known_issue_regressions"].values()
        ))

    def test_known_wrong_table_relations_are_absent(self):
        cases = {
            "PDF_P0052_15AF0BE982": "50234561",
            "PDF_P0080_5D6F5491C6": "50171361",
            "PDF_P0125_F894064DD2": "99328726",
        }
        for table_id, forbidden_pt in cases.items():
            pts = {pt for pt, _ in self.accessory_pairs(self.records(table_id=table_id))}
            self.assertNotIn(forbidden_pt, pts, table_id)

    def test_exclusively_white_annotations_never_create_accessorio(self):
        matching = [
            row for row in self.preview
            if EXCLUSIVE_IDS.intersection(row.get("source_annotation_ids") or [])
        ]
        self.assertEqual([], matching)
        rejected = {
            item["annotation_id"]: item["reason"]
            for item in self.report["variant_finish_false_positive_records"]
        }
        for annotation_id in EXCLUSIVE_IDS:
            self.assertEqual("VARIANT_OR_FINISH_LIMITATION", rejected.get(annotation_id))

    def test_start_ln_is_retained_and_row_scoped(self):
        rows = self.records(page=57, title_contains="START LN")
        by_pt = {
            item["pt"]: row
            for row in rows for item in row.get("accessories") or []
            if item.get("pt") in {"99784997", "99785000"}
        }
        self.assertEqual({"99784997", "99785000"}, set(by_pt))
        for row in by_pt.values():
            self.assertEqual("ROW_SCOPED_REFERENCE", row["governor_evidence"])
            self.assertEqual("ROW_SCOPED", row["scope_type"])
            self.assertEqual(1, len(row["applies_to_models"]))

    def test_aermec_wifi_rows_remain_structural(self):
        expected = {"SPG": ("50253210", "KITWIFI"), "SGE": ("50021123", "WIFIKEY")}
        for title, pair in expected.items():
            rows = self.records(page=620, title_contains=title)
            self.assertIn(pair, self.accessory_pairs(rows))
            matching = [
                row for row in rows
                if pair in self.accessory_pairs([row])
            ]
            self.assertTrue(matching)
            self.assertTrue(all(
                row["source_channel"] == "EXPLICIT_TABLE_ACCESSORY_ROW"
                and row["evidence"] == "SAME_TABLE"
                for row in matching
            ))

    def test_aermec_cassette_codes_do_not_cross(self):
        mpg_c = self.records(page=621, title_contains="MPG_C 90x90")
        mpg_cs = self.records(page=621, title_contains="MPG_CS 60x60")
        c_pairs, cs_pairs = self.accessory_pairs(mpg_c), self.accessory_pairs(mpg_cs)
        self.assertIn(("99794507", "GLG40"), c_pairs)
        self.assertNotIn(("99794583", "GLG40S"), c_pairs)
        self.assertIn(("99794583", "GLG40S"), cs_pairs)
        self.assertNotIn(("99794507", "GLG40"), cs_pairs)
        for row in mpg_c + mpg_cs:
            if row.get("accessories"):
                component = row["component"]
                self.assertEqual("EXCLUDED", component["catalog_inclusion_status"])
                self.assertTrue(component["mandatory_pairing"])
                self.assertEqual("ADD_IF_SOLD_TITLE_INCLUDES", component["bom_action"])

    def test_daikin_and_midea_dimension_finish_separation(self):
        daikin = self.report["blocking_regression_checks"]["09_daikin_dimension_finish_separation"]
        midea = self.report["blocking_regression_checks"]["10_midea_dimension_separation"]
        self.assertTrue(daikin["PASS"])
        self.assertTrue(daikin["finishes_kept_distinct"])
        self.assertTrue(midea["PASS"])
        self.assertIn({"model": "BYCQ140E", "pt": "99759964"}, daikin["grid_model_pt_pairs"])
        self.assertIn({"model": "BYFQ60CS", "pt": "99718268"}, daikin["grid_model_pt_pairs"])
        self.assertIn({"model": "T-MBQ4-04A1", "pt": "50131419"}, midea["super_slim_model_pt_pairs"])
        self.assertIn({"model": "T-MBQ4-03A", "pt": "50395835"}, midea["compact_model_pt_pairs"])

    def test_every_emitted_accessory_section_has_strong_governor_and_provenance(self):
        rows = [
            row for row in self.preview
            if row["source_channel"] == "EXPLICIT_ACCESSORY_SECTION"
        ]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row["governor_evidence"], STRONG_GOVERNORS)
            self.assertEqual(1.0, row["governor_confidence"])
            provenance = row
            for field in (
                "product_table_id", "accessory_table_id", "page", "product_bbox",
                "accessory_heading_bbox", "accessory_row_bbox", "pt_bbox", "model_bbox",
                "target_text", "target_text_bbox", "governor_evidence",
                "governor_confidence", "scope_type", "applies_to_models",
            ):
                self.assertIn(field, provenance)
            self.assertEqual(row["table_id"], provenance["product_table_id"])

    def test_conservative_dedup_key_is_unique(self):
        keys = []
        for row in self.preview:
            if row["source_channel"] == "RED_EDITORIAL_ANNOTATION":
                continue
            for accessory in row.get("accessories") or []:
                keys.append((
                    row["table_id"], accessory["pt"], row["source_channel"],
                    row["scope_type"], tuple(sorted(row["applies_to_models"])),
                ))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreater(self.report["deduplicated_same_scope_count"], 0)


if __name__ == "__main__":
    unittest.main()
