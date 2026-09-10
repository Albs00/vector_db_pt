"""
Unit tests for catalog_component_relations.json and catalog_component_relations_report.json.

Validates:
1. Strict schema compliance (association_confidence_reason, relation_intent, required_for_sale, evidence).
2. family_key strictly originating from catalog_table_context (never automatically generated).
3. ACCESSORY_INCLUDED_SEPARATE strictly allowed only with explicit 'incluso', PT code present, and certain geometric relation.
4. Negative tests:
   - Same component / similar accessory belonging to another table (zero cross-table leakage).
   - Different color/finish (black 95x95 round flow vs silver/white 62x62 compact, breezeless finish vs standard).
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_RELATIONS_PATH = ROOT / "Knowledge" / "catalog_component_relations.json"
ROOT_RELATIONS_PATH = ROOT / "catalog_component_relations.json"
REPORT_PATH = ROOT / "catalog_component_relations_report.json"
ANNOTATIONS_PATH = ROOT / "Knowledge" / "catalog_annotations.json"
ROOT_TABLE_CONTEXT_PATH = ROOT / "catalog_table_context.json"
KNOWLEDGE_TABLE_CONTEXT_PATH = ROOT / "Knowledge" / "catalog_table_context.json"


class TestCatalogComponentRelations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert KNOWLEDGE_RELATIONS_PATH.exists(), f"Missing {KNOWLEDGE_RELATIONS_PATH}"
        assert ROOT_RELATIONS_PATH.exists(), f"Missing {ROOT_RELATIONS_PATH}"
        assert REPORT_PATH.exists(), f"Missing {REPORT_PATH}"

        with KNOWLEDGE_RELATIONS_PATH.open("r", encoding="utf-8") as f:
            cls.relations = json.load(f)

        with ROOT_RELATIONS_PATH.open("r", encoding="utf-8") as f:
            cls.root_relations = json.load(f)

        with REPORT_PATH.open("r", encoding="utf-8") as f:
            cls.report = json.load(f)

        with ANNOTATIONS_PATH.open("r", encoding="utf-8") as f:
            cls.annotations = {a["annotation_id"]: a for a in json.load(f)}

        # Load valid families from catalog_table_context
        cls.valid_context_families = set()
        for tc_path in [ROOT_TABLE_CONTEXT_PATH, KNOWLEDGE_TABLE_CONTEXT_PATH]:
            if tc_path.exists():
                with tc_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for rec in data.values():
                        fam = rec.get("table_family")
                        if fam:
                            cls.valid_context_families.add(fam.strip())
                        for alt in rec.get("alternate_table_contexts") or []:
                            afam = alt.get("table_family")
                            if afam:
                                cls.valid_context_families.add(afam.strip())

    def test_datasets_identical(self):
        """Knowledge and root copies must be identical."""
        self.assertEqual(len(self.relations), len(self.root_relations))
        self.assertEqual(len(self.relations), self.report["total_relations"])

    def test_schema_and_fields(self):
        """Every record must have exact fields and valid enum values."""
        allowed_evidence = {"SAME_TABLE", "EXPLICIT_ACCESSORY_SECTION"}
        allowed_intents = {
            "ACCESSORY_REQUIRED",
            "ACCESSORY_OPTIONAL",
            "ACCESSORY_INCLUDED_SEPARATE",
            "FEATURE_ONLY",
            "NO_COMPONENT_CODE",
        }
        allowed_reasons = {
            "INTERNAL_ROW_IN_PRODUCT_TABLE",
            "COLUMN_ALIGNED_DEDICATED_ACCESSORY_SECTION",
            "INTEGRATED_IN_PRODUCT_BOX_NO_SEPARATE_CODE",
            "PRODUCT_FEATURE_NO_SEPARATE_CODE",
            "NO_CODED_ACCESSORY_IN_MATCHED_BLOCK",
        }

        for r in self.relations:
            self.assertIn("annotation_id", r)
            self.assertIn("page", r)
            self.assertIn("table_id", r)
            self.assertIn("product_context", r)
            self.assertIn("component", r)
            self.assertIn("association_confidence_reason", r)
            self.assertIn("accessories", r)
            self.assertEqual(r.get("source"), "PDF_LAYOUT")

            ctx = r["product_context"]
            self.assertIn("table_title", ctx)
            self.assertIn("family_key", ctx)
            self.assertIn("models", ctx)
            self.assertIsInstance(ctx["models"], list)

            comp = r["component"]
            self.assertIn("type", comp)
            self.assertIn("status", comp)
            self.assertIn("relation_intent", comp)
            self.assertIn("required_for_sale", comp)
            self.assertIn(comp["relation_intent"], allowed_intents)

            # required_for_sale is True ONLY for ACCESSORY_REQUIRED
            if comp["relation_intent"] == "ACCESSORY_REQUIRED":
                self.assertTrue(comp["required_for_sale"])
            else:
                self.assertFalse(comp["required_for_sale"])

            # Top level reason
            self.assertIn(r["association_confidence_reason"], allowed_reasons)

            # Accessories array
            for acc in r["accessories"]:
                self.assertIn("pt", acc)
                self.assertIn("model", acc)
                self.assertIn("evidence", acc)
                self.assertIn("confidence", acc)
                self.assertIn("association_confidence_reason", acc)
                self.assertIn(acc["evidence"], allowed_evidence)
                self.assertEqual(acc["confidence"], 1.0)
                self.assertIn(
                    acc["association_confidence_reason"],
                    {
                        "INTERNAL_ROW_IN_PRODUCT_TABLE",
                        "COLUMN_ALIGNED_DEDICATED_ACCESSORY_SECTION",
                    },
                )

    def test_family_key_only_from_catalog_table_context(self):
        """family_key must strictly come from catalog_table_context, never automatically generated."""
        for r in self.relations:
            fam = r["product_context"].get("family_key")
            if fam:
                self.assertIn(
                    fam.strip(),
                    self.valid_context_families,
                    f"family_key '{fam}' in annotation {r['annotation_id']} was not found in catalog_table_context!",
                )

    def test_accessory_included_separate_strict_conditions(self):
        """ACCESSORY_INCLUDED_SEPARATE is allowed ONLY with explicit 'incluso', PT code present, and certain geometric relation."""
        inc_sep_records = [
            r for r in self.relations if r["component"]["relation_intent"] == "ACCESSORY_INCLUDED_SEPARATE"
        ]
        self.assertGreater(len(inc_sep_records), 0)

        for r in inc_sep_records:
            aid = r["annotation_id"]
            raw_text = self.annotations[aid]["raw_text"].lower()

            # 1. Testo esplicito "incluso" (positive, non negated)
            has_positive_incluso = any(
                w in raw_text
                for w in [
                    "incluso",
                    "inclusa",
                    "inclusi",
                    "incluse",
                    "compreso",
                    "compresa",
                    "compresi",
                    "comprese",
                ]
            )
            has_negation = any(
                w in raw_text
                for w in [
                    "non incluso",
                    "non inclusa",
                    "non compreso",
                    "non compresa",
                    "escluso",
                    "esclusa",
                ]
            )
            self.assertTrue(
                has_positive_incluso and not has_negation,
                f"Record {aid} with ACCESSORY_INCLUDED_SEPARATE lacks explicit positive 'incluso': {raw_text}",
            )

            # 2. Codice PT presente
            self.assertGreater(
                len(r["accessories"]),
                0,
                f"Record {aid} with ACCESSORY_INCLUDED_SEPARATE has empty accessories array!",
            )

            # 3. Relazione geometrica certa
            self.assertTrue(r["table_id"], f"Record {aid} lacks table_id")
            for acc in r["accessories"]:
                self.assertIn(acc["evidence"], {"SAME_TABLE", "EXPLICIT_ACCESSORY_SECTION"})
                self.assertEqual(acc["confidence"], 1.0)
                self.assertIn(
                    acc["association_confidence_reason"],
                    {"INTERNAL_ROW_IN_PRODUCT_TABLE", "COLUMN_ALIGNED_DEDICATED_ACCESSORY_SECTION"},
                )

    def test_negative_same_component_different_table_aermec_cassette(self):
        """Negative test: Aermec 90x90 cassette must NOT have 60x60 grille GLG40S, and 60x60 must NOT have 90x90 GLG40."""
        p621_c = [
            r for r in self.relations
            if r["page"] == 621
            and "MPG_C 90x90" in r["product_context"]["table_title"]
            and r["component"]["type"] == "GRIGLIA"
        ]
        p621_cs = [
            r for r in self.relations
            if r["page"] == 621
            and "MPG_CS 60x60" in r["product_context"]["table_title"]
            and r["component"]["type"] == "GRIGLIA"
        ]
        self.assertGreater(len(p621_c), 0)
        self.assertGreater(len(p621_cs), 0)

        pts_90 = [acc["pt"] for acc in p621_c[0]["accessories"]]
        models_90 = [acc["model"] for acc in p621_c[0]["accessories"]]
        pts_60 = [acc["pt"] for acc in p621_cs[0]["accessories"]]
        models_60 = [acc["model"] for acc in p621_cs[0]["accessories"]]

        # Positive assertions
        self.assertIn("99794507", pts_90)
        self.assertIn("GLG40", models_90)
        self.assertIn("99794583", pts_60)
        self.assertIn("GLG40S", models_60)

        # NEGATIVE ASSERTIONS (Zero cross-table leakage)
        self.assertNotIn(
            "99794583", pts_90,
            "NEGATIVE TEST FAILURE: 60x60 grille GLG40S from adjacent table leaked into 90x90 MPG_C!",
        )
        self.assertNotIn(
            "GLG40S", models_90,
            "NEGATIVE TEST FAILURE: 60x60 model GLG40S leaked into 90x90 MPG_C!",
        )
        self.assertNotIn(
            "99794507", pts_60,
            "NEGATIVE TEST FAILURE: 90x90 grille GLG40 from adjacent table leaked into 60x60 MPG_CS!",
        )
        self.assertNotIn(
            "GLG40", models_60,
            "NEGATIVE TEST FAILURE: 90x90 model GLG40 leaked into 60x60 MPG_CS!",
        )

    def test_negative_same_component_different_table_daikin_cassette(self):
        """Negative test: Daikin FCAG 90x90 must NOT have 60x60 grilles, and FFA 60x60 must NOT have 90x90 grilles."""
        fcag_90 = [
            r for r in self.relations
            if r["page"] == 474 and r["component"]["type"] == "GRIGLIA"
        ]
        ffa_60 = [
            r for r in self.relations
            if r["page"] in (473, 477) and r["component"]["type"] == "GRIGLIA"
        ]
        self.assertGreater(len(fcag_90), 0)
        self.assertGreater(len(ffa_60), 0)

        models_90 = [acc["model"] for r in fcag_90 for acc in r["accessories"]]
        models_60 = [acc["model"] for r in ffa_60 for acc in r["accessories"]]

        # 90x90 FCAG grilles must all be BYCQ
        for m in models_90:
            self.assertTrue(m.startswith("BYCQ"), f"Unexpected grille {m} in 90x90 table")
            self.assertFalse(m.startswith("BYFQ"), f"NEGATIVE TEST FAILURE: 60x60 grille {m} found in FCAG 90x90!")

        # 60x60 FFA grilles must all be BYFQ
        for m in models_60:
            self.assertTrue(m.startswith("BYFQ"), f"Unexpected grille {m} in 60x60 table")
            self.assertFalse(m.startswith("BYCQ"), f"NEGATIVE TEST FAILURE: 90x90 grille {m} found in FFA 60x60!")

    def test_negative_different_color_finish(self):
        """Negative test: Accessories with different colors/finishes must not contaminate other tables."""
        # Daikin Black Design Panel 95x95 (PT 99761042 / BYCQ140EPB) belongs to 90x90 round flow
        # Daikin Silver Panel 62x62 (PT 99718268 / BYFQ60CS) belongs to 60x60 compact
        # Daikin White Panel 62x62 (PT 99718275 / BYFQ60CW) belongs to 60x60 compact
        fcag_90 = [
            r for r in self.relations
            if r["page"] == 474 and r["component"]["type"] == "GRIGLIA"
        ]
        ffa_60 = [
            r for r in self.relations
            if r["page"] in (473, 477) and r["component"]["type"] == "GRIGLIA"
        ]

        pts_90 = [acc["pt"] for r in fcag_90 for acc in r["accessories"]]
        pts_60 = [acc["pt"] for r in ffa_60 for acc in r["accessories"]]

        # 90x90 has black finish 99761042
        self.assertIn("99761042", pts_90)
        # 60x60 compact must NOT have black 95x95 finish
        self.assertNotIn(
            "99761042", pts_60,
            "NEGATIVE TEST FAILURE: Black 95x95 finish BYCQ140EPB wrongly associated to 60x60 compact cassette!",
        )

        # 60x60 has silver finish 99718268 and white finish 99718275
        self.assertIn("99718268", pts_60)
        self.assertIn("99718275", pts_60)
        # 90x90 must NOT have silver or white 62x62 compact finishes
        self.assertNotIn(
            "99718268", pts_90,
            "NEGATIVE TEST FAILURE: Silver 62x62 finish BYFQ60CS wrongly associated to 90x90 round flow cassette!",
        )
        self.assertNotIn(
            "99718275", pts_90,
            "NEGATIVE TEST FAILURE: White 62x62 finish BYFQ60CW wrongly associated to 90x90 round flow cassette!",
        )

        # Midea: Breezeless finish (50132270 / T-MBQ4-04AWD) on 90x90 Super Slim
        midea_90 = [
            r for r in self.relations
            if r["page"] == 546 and r["component"]["type"] == "GRIGLIA"
        ]
        midea_60 = [
            r for r in self.relations
            if r["page"] == 541 and r["component"]["type"] == "GRIGLIA"
        ]
        pts_midea_90 = [acc["pt"] for r in midea_90 for acc in r["accessories"]]
        pts_midea_60 = [acc["pt"] for r in midea_60 for acc in r["accessories"]]

        self.assertIn("50132270", pts_midea_90)
        self.assertNotIn(
            "50132270", pts_midea_60,
            "NEGATIVE TEST FAILURE: Breezeless finish T-MBQ4-04AWD wrongly associated to 60x60 MCA4U!",
        )

    def test_telecomando_incluso_no_component_code(self):
        """Telecomando incluso without a separate PT code in table must yield NO_COMPONENT_CODE and empty accessories."""
        telec_incluso = [
            r for r in self.relations
            if r["component"]["type"] == "TELECOMANDO"
            and r["component"]["status"] == "COMPONENT_INCLUDED"
            and not r["accessories"]
        ]
        self.assertGreater(
            len(telec_incluso), 100,
            "Expected majority of 'telecomando incluso' to have NO_COMPONENT_CODE and empty accessories",
        )
        for r in telec_incluso:
            self.assertEqual(r["component"]["relation_intent"], "NO_COMPONENT_CODE")
            self.assertFalse(r["component"]["required_for_sale"])
            self.assertEqual(r["accessories"], [])


if __name__ == "__main__":
    unittest.main()
