import unittest
from catalog_search_engine import CatalogSearchEngine


class TestRequestedFamilyValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CatalogSearchEngine()

    def test_baxi_wifi_optional_no_family(self):
        query = "Baxi Climatizzatore Monosplit 12000 btu WiFi Optional"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})
        q_ctx = qa.get("query_context", {})

        self.assertIsNone(qa.get("requested_family_key"))
        self.assertTrue(q_ctx.get("feature_wifi"))

    def test_baxi_trifase_no_family(self):
        query = "Baxi Climatizzatore Monosplit 24000 btu Trifase"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})
        q_ctx = qa.get("query_context", {})

        self.assertIsNone(qa.get("requested_family_key"))
        self.assertEqual(q_ctx.get("phase"), "TRIFASE")

    def test_baxi_canalizzato_matches_family(self):
        query = "Baxi Climatizzatore Monosplit Inverter Canalizzato 48000 btu"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})

        self.assertEqual(qa.get("requested_family_key"), "BAXI_CANALIZZATA")

    def test_baxi_soffitto_pavimento_matches_family(self):
        query = "Baxi Climatizzatore Monosplit Soffitto/Pavimento 24000 btu"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})

        self.assertEqual(qa.get("requested_family_key"), "BAXI_PAVIMENTO_SOFFITTO")

    def test_midea_elegance_matches_family(self):
        query = "Midea Climatizzatore Dual Split serie Elegance 12+18"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})

        self.assertEqual(qa.get("requested_family_key"), "MIDEA_ELEGANCE")

    def test_haier_expert_matches_family(self):
        query = "Haier Climatizzatore Monosplit serie Expert 12000"
        res = self.engine.search(query, limit=5)
        qa = res.get("query_analysis", {})

        self.assertEqual(qa.get("requested_family_key"), "HAIER_EXPERT")

    def test_full_baxi_soffitto_pavimento_retrieval(self):
        query = (
            "Baxi Climatizzatore Monosplit Soffitto/Pavimento RZGNF 24000 btu "
            "Inverter R-32 Wi-Fi Optional Classe A++/A+"
        )
        res = self.engine.search(query, limit=10)
        qa = res.get("query_analysis", {})
        q_ctx = qa.get("query_context", {})

        self.assertEqual(qa.get("requested_family_key"), "BAXI_PAVIMENTO_SOFFITTO")
        self.assertTrue(q_ctx.get("feature_wifi"))
        self.assertTrue(q_ctx.get("feature_inverter"))
        self.assertTrue(q_ctx.get("feature_r32"))
        self.assertTrue(q_ctx.get("feature_optional"))

        # Verify candidate pools
        pools = res.get("candidate_pools", {})
        ui_cands = pools.get("slot_ui_24000", [])
        self.assertTrue(len(ui_cands) > 0)
        self.assertEqual(ui_cands[0]["code"], "50225149")
        self.assertEqual(ui_cands[0]["family_match"], "exact")

        ue_cands = pools.get("slot_ue", [])
        self.assertTrue(len(ue_cands) > 0)
        self.assertEqual(ue_cands[0]["code"], "50225187")


if __name__ == "__main__":
    unittest.main()
