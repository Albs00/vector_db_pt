import os
import unittest

from catalog_search_engine import CatalogSearchEngine
from src.core.clima_master_resolver import ClimaMasterResolver
from src.core.model_identity import normalize_structural_model


class ClimaMasterRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CLIMA_MASTER_RUNTIME_ENABLED"] = "1"
        cls.resolver = ClimaMasterResolver("Knowledge")
        cls.engine = CatalogSearchEngine()

    def assert_main_pts(self, query, expected):
        result = self.engine.search(query, limit=10, include_accessories=False)
        actual = [item["code"] for item in result["bom"] if item.get("role") in {"UI", "UE"}]
        self.assertEqual(actual, expected)
        self.assertTrue(result["mpn_final_allowed"])
        self.assertEqual(result["dataset_release"], "PT26_CLIMA_PROD_1")
        return result

    def test_release_hashes_are_verified(self):
        self.assertEqual(self.resolver.hashes, {
            "clima_monosplit_master.json": "05f56077cc1254025bc995ca2cfcdcf374ce8529846cba023f3898e1b0bbd81b",
            "clima_multisplit_master.json": "0cf07f4e71768af267c81b1dd64171604a72432ea796f159245991af9a0c1e9b",
            "manual_overrides_clima.json": "ce4eb075c46717276835e18219ba36c5a59879befe11bca32b97709403a9ba68",
            "clima_accessori_master.json": "134bb387c70211376d782d46debe0e90d5a91b71d7a87a746d00993866a49425",
        })

    def test_release_contract(self):
        self.assertEqual(self.resolver.DATASET_VERSION, "PT26_CLIMA_PROD_1")
        self.assertEqual(self.resolver.SCHEMA_VERSION, "3.0.0")
        self.assertEqual(self.resolver.POLICY, "FAIL_CLOSED")

    def test_toshiba_haori_white_9000(self):
        self.assert_main_pts("TOSHIBA HAORI BIANCO 9000", ["50383573", "50213924"])

    def test_toshiba_exact_pair(self):
        self.assert_main_pts("50383573 + 50213924", ["50383573", "50213924"])

    def test_panasonic_paci_standard(self):
        self.assert_main_pts(
            "PANASONIC PACI NX STANDARD CASSETTA 21000",
            ["50117260", "50003952"],
        )

    def test_panasonic_exact_pair(self):
        self.assert_main_pts("50117260 + 50003952", ["50117260", "50003952"])

    def test_mitsubishi_white_multiset(self):
        result = self.assert_main_pts(
            "MITSUBISHI WHITE 12+12+18",
            ["99788605", "99788605", "99788636", "50196142"],
        )
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertNotIn("99788599", [item["code"] for item in result["bom"]])

    def test_mitsubishi_exact_multiset(self):
        self.assert_main_pts(
            "99788605 99788605 99788636 50196142",
            ["99788605", "99788605", "99788636", "50196142"],
        )

    def test_haier_flexis_white(self):
        self.assert_main_pts("HAIER FLEXIS WHITE 9000", ["50026470", "50131273"])

    def test_haier_flexis_black(self):
        self.assert_main_pts("HAIER FLEXIS BLACK 9000", ["50021635", "50131273"])

    def test_daikin_ffa25a9_is_ui_only(self):
        result = self.assert_main_pts("DAIKIN FFA25A9", ["99718206"])
        self.assertEqual(result["product_scope"], "UI_ONLY")

    def test_venus_scope_does_not_inherit(self):
        mono = self.engine.search("50282814", include_accessories=False)
        multi = self.engine.search("50282883", include_accessories=False)
        self.assertEqual([item["code"] for item in mono["bom"]], ["50282814"])
        self.assertEqual([item["code"] for item in multi["bom"]], ["50282883"])

    def test_paros_white_black_separation(self):
        self.assert_main_pts("KOSAMI PAROS WHITE 9000", ["50453016", "50452965"])
        self.assert_main_pts("KOSAMI PAROS BLACK 9000", ["50453054", "50452965"])

    def test_semantic_revisions_remain_distinct(self):
        for left, right in (("A", "A8"), ("A8", "A9"), ("V3", "V4"), ("VF", "VFHZ"), ("VG", "VG2"), ("E", "E1")):
            self.assertNotEqual(
                normalize_structural_model("MODEL-" + left),
                normalize_structural_model("MODEL-" + right),
            )

    def test_unauthorized_configuration_is_fail_closed(self):
        validation = self.resolver.validate_legacy_bom("MULTISPLIT", [
            {"role": "UI", "code": "99788599"},
            {"role": "UI", "code": "99788605"},
            {"role": "UI", "code": "99788636"},
            {"role": "UE", "code": "50196142"},
        ])
        self.assertFalse(validation["confirmed"])
        self.assertEqual(validation["configuration_status"], "CONFIGURAZIONE_NON_CONFERMATA")

    def test_clima_accessories_do_not_use_legacy_v34(self):
        result = self.engine.search("DAIKIN FFA25A9", include_accessories=True)
        self.assertEqual(result["component_relation_source"], "clima_accessori_master.json")
        self.assertNotEqual(result.get("component_relation_source"), "catalog_component_relations_safe_preview_v3_4.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
