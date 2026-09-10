"""Integration regressions for identity-first climate accessory lookup."""

from __future__ import annotations

import re
import unittest

from catalog_search_engine import CatalogSearchEngine
from manual_retrieval_qa import format_qa_single_report


def model_signature(value):
    value = re.sub(r"^\s*U\s*[.]?\s*[IE]\s*[.]?\s*", "", str(value), flags=re.I)
    value = re.sub(r"\([^)]*\)\s*$", "", value)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class TestComponentRelationsLookupAfterProductMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CatalogSearchEngine()
        cls.engine._ensure_initialized()

    @staticmethod
    def accessory_pairs(result):
        return {
            (str(accessory.get("pt") or ""), str(accessory.get("model") or ""))
            for relation in result.get("component_relations") or []
            for accessory in relation.get("accessories") or []
        }

    def test_component_relations_lookup_after_product_match(self):
        cases = {
            "ffa": "Daikin Cassetta 4 vie FFA25A9 60x60 Griglia esclusa da abbinare obbligatoriamente",
            "round_flow": "Daikin Cassetta Round Flow FCAG71A 90x90 Griglia esclusa da abbinare obbligatoriamente",
            "haier": "Haier Cassetta a 1 via AB71S2SA1FA Pannello Bianco",
            "spg": "Aermec SPG WiFi optional",
        }
        results = {name: self.engine.search(query, limit=20) for name, query in cases.items()}
        for result in results.values():
            accessory_pts = {pt for pt, _ in self.accessory_pairs(result) if pt}
            bom_pts = {str(item.get("code") or "") for item in result.get("bom") or []}
            self.assertFalse(
                accessory_pts.intersection(bom_pts),
                "Component relations must remain informative and outside the BOM",
            )

        ffa = results["ffa"]
        self.assertIn(
            ("99718268", "BYFQ60CS"), self.accessory_pairs(ffa)
        )
        self.assertIn(
            ("99718275", "BYFQ60CW"), self.accessory_pairs(ffa)
        )
        self.assertTrue(any(
            product.get("code") == "99718206"
            for product in ffa["component_relation_products"]
        ))
        self.assertFalse(any(
            model.startswith("BYCQ140") for _, model in self.accessory_pairs(ffa)
        ))
        self.assertFalse(any(
            relation.get("attachment_target") == "UE"
            for relation in ffa["component_relations"]
        ))

        round_flow = results["round_flow"]
        expected_bycq = {
            ("99759964", "BYCQ140E"),
            ("99761028", "BYCQ140EGF"),
            ("99761035", "BYCQ140EP"),
            ("99761042", "BYCQ140EPB"),
        }
        self.assertTrue(expected_bycq.issubset(self.accessory_pairs(round_flow)))
        self.assertFalse(any(
            model.startswith("BYFQ60") for _, model in self.accessory_pairs(round_flow)
        ))
        # FCAG71A is not present in the current catalog; the deterministic
        # final-revision fallback identifies its catalog successor FCAG71B.
        self.assertTrue(any(
            product.get("code") == "99759971" and product.get("mfg_code") == "FCAG71B"
            for product in round_flow["component_relation_products"]
        ))
        self.assertEqual(
            "EXACT_MODEL_REVISION_PRODUCT_CONTEXT",
            round_flow["component_relation_lookup_status"],
        )

        haier = results["haier"]
        self.assertIn(("50370160", "AB50S2SA1FA - AB71S2SA1FA"), self.accessory_pairs(haier))
        self.assertNotIn("50370139", {pt for pt, _ in self.accessory_pairs(haier)})
        panel_relation = next(
            relation for relation in haier["component_relations"]
            if any(str(item.get("pt")) == "50370160" for item in relation.get("accessories") or [])
        )
        self.assertEqual("CASSETTE_UI", panel_relation["attachment_target"])
        self.assertEqual(
            {"AB71S2SA1FA"},
            {model_signature(model) for model in panel_relation["applies_to_models"]},
        )

        spg = results["spg"]
        self.assertIn(("50253210", "KITWIFI"), self.accessory_pairs(spg))
        wifi = next(
            relation for relation in spg["component_relations"]
            if any(str(item.get("pt")) == "50253210" for item in relation.get("accessories") or [])
        )
        self.assertEqual("ACCESSORY_OPTIONAL", wifi["component"]["relation_intent"])

    def test_exact_pt_table_and_family_lookup_precedence(self):
        index = self.engine._component_relation_index
        exact = index.lookup_product({
            "code": "99718206", "mfg_code": "FFA25A9", "is_ui": True,
        })
        self.assertTrue(exact)
        self.assertEqual({"EXACT_PRODUCT_PT"}, {row["lookup_strategy"] for row in exact})

        table = index.lookup_product({
            "code": "NOT_IN_CONTEXT", "mfg_code": "FFA25A9", "is_ui": True,
            "table_id": "PDF_P0473_84E198812D",
            "family_key": "DAIKIN_CASSETTA_A_4_VIE_FFA_A_9_60X60",
        })
        self.assertTrue(table)
        self.assertEqual({"TABLE_ID"}, {row["lookup_strategy"] for row in table})

        family = index.lookup_family("AERMEC_SPG")
        self.assertIn(
            ("50253210", "KITWIFI"),
            {
                (str(accessory.get("pt")), str(accessory.get("model")))
                for relation in family for accessory in relation.get("accessories") or []
            },
        )
        self.assertEqual(
            {"FAMILY_PRODUCT_CONTEXT"}, {row["lookup_strategy"] for row in family}
        )

    def test_expert_has_no_cassette_accessory(self):
        query = "Haier Expert AS25XCAHRA-MB Nero"
        result = self.engine.search(query, limit=20)
        self.assertEqual("EXACT_PRODUCT_IDENTITY", result["component_relation_lookup_status"])
        for relation in result["component_relations"]:
            component = str(relation.get("component", {}).get("type") or "").upper()
            self.assertNotIn(component, {"GRIGLIA", "PANNELLO", "PANNELLO CASSETTA"})
            self.assertNotEqual("CASSETTE_UI", relation.get("attachment_target"))

    def test_compatibility_and_component_graphs_remain_separate(self):
        query = "Daikin Dual Split Perfera 9000+12000"
        result = self.engine.search(query, limit=20)
        compatibility = result.get("compatibility_evidence") or {}
        self.assertNotEqual(
            result.get("component_relation_source"), compatibility.get("source")
        )
        self.assertNotEqual(
            result.get("component_relation_source"), compatibility.get("provenance")
        )
        self.assertEqual("catalog_component_relations_v3_4", result["component_relation_source"])
        self.assertTrue(result.get("bom"))
        self.assertTrue(all(
            item.get("role") in {"UI", "UE"} for item in result["bom"]
        ))

    def test_manual_qa_has_separate_component_section(self):
        query = "Aermec SPG WiFi optional"
        result = self.engine.search(query, limit=20)
        report = format_qa_single_report(query, result)
        self.assertIn("5. INFORMAZIONI COMPONENTI / ACCESSORI", report)
        self.assertIn("PT 50253210", report)
        self.assertIn("KITWIFI", report)
        self.assertIn("ACCESSORY_OPTIONAL", report)


if __name__ == "__main__":
    unittest.main()
