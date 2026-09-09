"""Blocking checks for the climate-only Safe Preview v3.1."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1.json"
REPORT_PATH = ROOT / "catalog_component_relations_safe_preview_v3_1_report.json"
CLIMATE_MASTER_PATH = ROOT / "Knowledge" / "climatizzatori_compatibilita_master.json"


class TestSafePreviewV31(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preview = json.loads(PREVIEW_PATH.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        climate_master = json.loads(CLIMATE_MASTER_PATH.read_text(encoding="utf-8"))
        cls.ui_pts = set(climate_master["unita_interne"])
        cls.ue_pts = set(climate_master["unita_esterne"])

    def records(self, page: int, title: str) -> list[dict]:
        return [
            record for record in self.preview
            if record.get("page") == page
            and title.casefold() in str(
                record.get("product_context", {}).get("table_title") or ""
            ).casefold()
        ]

    @staticmethod
    def pairs(records: list[dict]) -> set[tuple[str, str]]:
        return {
            (str(accessory.get("pt") or ""), str(accessory.get("model") or ""))
            for record in records for accessory in record.get("accessories") or []
        }

    def test_production_ready_and_all_hard_regressions(self) -> None:
        self.assertTrue(self.report["production_ready"])
        self.assertTrue(all(self.report["production_ready_conditions"].values()))
        self.assertTrue(all(
            check["PASS"] for check in self.report["hard_regression_checks"].values()
        ))

    def test_only_climate_parents_and_accessory_candidates(self) -> None:
        self.assertTrue(self.preview)
        for record in self.preview:
            self.assertEqual("CLIMATE", record["product_domain"])
            for accessory in record.get("accessories") or []:
                pt = str(accessory.get("pt") or "")
                self.assertEqual("CLIMATE_ACCESSORY", accessory["candidate_identity"])
                self.assertNotIn(pt, self.ui_pts)
                self.assertNotIn(pt, self.ue_pts)

    def test_panels_and_grids_only_govern_cassettes(self) -> None:
        component_types = {
            "GRIGLIA", "PANNELLO", "PANNELLO CASSETTA",
            "GRIGLIA MANDATA", "GRIGLIA RIPRESA",
        }
        for record in self.preview:
            context = record["product_context"]
            parent = " ".join([
                str(context.get("table_title") or ""),
                str(context.get("family_key") or ""),
                *[str(model) for model in context.get("models") or []],
            ]).upper()
            for accessory in record.get("accessories") or []:
                model = str(accessory.get("model") or "").upper()
                section = str(accessory.get("accessory_section_title") or "").upper()
                is_panel_or_grid = (
                    str(record["component"].get("type") or "").upper() in component_types
                    or bool(re.match(r"^(?:BYCQ|BYFQ|GLG|T-MBQ)", model))
                    or bool(re.match(r"^(?:PANNELLO|GRIGLIA)", section))
                )
                if is_panel_or_grid:
                    self.assertIn("CASSETT", parent)

    def test_total_white_has_no_colour_variant_edges(self) -> None:
        for record in self.records(468, "TOTAL WHITE"):
            for accessory in record.get("accessories") or []:
                section = str(accessory.get("accessory_section_title") or "").upper()
                self.assertNotIn("TOTAL BLACK", section)
                self.assertNotIn("TOTAL SILVER", section)

    def test_aermec_wifi_and_cassette_separation(self) -> None:
        self.assertIn(("50253210", "KITWIFI"), self.pairs(self.records(620, "SPG")))
        self.assertIn(("50021123", "WIFIKEY"), self.pairs(self.records(620, "SGE")))
        mpg_c = self.pairs(self.records(621, "MPG_C 90x90"))
        mpg_cs = self.pairs(self.records(621, "MPG_CS 60x60"))
        self.assertIn(("99794507", "GLG40"), mpg_c)
        self.assertFalse(any(pt == "99794583" for pt, _ in mpg_c))
        self.assertIn(("99794583", "GLG40S"), mpg_cs)
        self.assertFalse(any(pt == "99794507" for pt, _ in mpg_cs))

    def test_included_remote_never_gets_an_inferred_pt(self) -> None:
        included_remote = [
            record for record in self.preview
            if "TELECOMANDO" in str(record.get("raw_text") or "").upper()
            and "INCLUS" in str(record.get("raw_text") or "").upper()
        ]
        self.assertTrue(included_remote)
        self.assertTrue(all(not record.get("accessories") for record in included_remote))

    def test_report_has_twenty_examples_per_side(self) -> None:
        self.assertEqual(20, len(self.report["removed_edge_examples"]))
        self.assertEqual(20, len(self.report["kept_climate_edge_examples"]))


if __name__ == "__main__":
    unittest.main()
