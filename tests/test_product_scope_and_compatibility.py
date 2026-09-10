import unittest
from catalog_search_engine import CatalogSearchEngine
from src.adapters.climate import ClimateCategoryAdapter


class TestProductScopeAndCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CatalogSearchEngine()
        cls.adapter = ClimateCategoryAdapter()

    def test_query_context_scope_priorities(self):
        # UI_ONLY priorities
        ctx_ui = self.adapter.extract_query_context("Unità interna multisplit 9000 btu")
        self.assertEqual(ctx_ui.get("product_scope"), "UI_ONLY")
        self.assertTrue(ctx_ui.get("is_ui_only"))
        self.assertFalse(ctx_ui.get("is_multisplit"))

        # UE_ONLY priorities
        ctx_ue = self.adapter.extract_query_context("Unità esterna multisplit 5 attacchi")
        self.assertEqual(ctx_ue.get("product_scope"), "UE_ONLY")
        self.assertTrue(ctx_ue.get("is_ue_only"))
        self.assertFalse(ctx_ue.get("is_multisplit"))

        # MONOSPLIT explicit
        ctx_mono = self.adapter.extract_query_context("Climatizzatore monosplit 12000 btu")
        self.assertEqual(ctx_mono.get("product_scope"), "MONOSPLIT")
        self.assertTrue(ctx_mono.get("is_monosplit"))

        # MULTISPLIT
        ctx_multi = self.adapter.extract_query_context("Climatizzatore dual split 9+12")
        self.assertEqual(ctx_multi.get("product_scope"), "MULTISPLIT")
        self.assertTrue(ctx_multi.get("is_multisplit"))

    def test_exact_product_scope_inference_from_metadata(self):
        cases = [
            ("50224067", "50224067"),
            ("99718206", "99718206"),
            ("99759971", "99759971"),
            ("50307791", "50307791"),
            ("Daikin FFA25A9", "99718206"),
            ("Daikin FCAG71B", "99759971"),
            ("Daikin FTXM25A", "50307791"),
        ]
        for query, expected_code in cases:
            with self.subTest(query=query):
                res = self.engine.search(query, limit=20)
                self.assertEqual("UI_ONLY", res.get("product_scope"))
                self.assertEqual(
                    "EXACT_PRODUCT_METADATA",
                    (res.get("query_analysis") or {}).get("query_context", {}).get(
                        "product_scope_source"
                    ),
                )
                bom_codes = [str(item.get("code") or "") for item in res.get("bom", [])]
                self.assertIn(expected_code, bom_codes)
                self.assertFalse(any(item.get("is_ue") for item in res.get("bom", [])))

    def test_explicit_query_scope_has_priority(self):
        res = self.engine.search("Daikin Unità Esterna FFA25A9", limit=20)

        self.assertEqual("UE_ONLY", res.get("product_scope"))
        self.assertEqual(
            "QUERY_EXPLICIT_ROLE",
            res.get("query_analysis", {}).get("query_context", {}).get(
                "product_scope_source"
            ),
        )
        self.assertNotEqual("UI_ONLY", res.get("product_scope"))

    def test_a_ui_only_baxi(self):
        query = "Baxi Unità Interna Soffitto Pavimento RZ2GNF70 24000 btu R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "UI_ONLY")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertEqual(bom_codes, ["50225149"])
        self.assertNotIn("50225187", bom_codes)

        # Informative compatibility evidence should link the paired UE
        ev = res.get("compatibility_evidence") or {}
        conn_codes = [c.get("code") for c in ev.get("connected_components", [])]
        self.assertIn("50225187", conn_codes)
        self.assertEqual(ev.get("relation_type"), "PDF_TABLE_PAIRING_VERIFIED")

    def test_b_ue_only_midea(self):
        query = "Midea Unità Esterna MOX102-12HFN8/LT R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "UE_ONLY")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertEqual(bom_codes, ["50130993"])
        # No UI in BOM
        for c in res.get("bom", []):
            self.assertFalse(c.get("is_ui", False))

        ev = res.get("compatibility_evidence") or {}
        conn_codes = [c.get("code") for c in ev.get("connected_components", [])]
        self.assertIn("50130993", conn_codes)

    def test_c_monosplit_baxi(self):
        query = "Baxi Climatizzatore Monosplit Soffitto/Pavimento RZ2GNF70 24000 btu R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "MONOSPLIT")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertIn("50225149", bom_codes)
        self.assertIn("50225187", bom_codes)
        self.assertEqual(res.get("compatibility_status"), "VERIFIED")

        ev = res.get("compatibility_evidence") or {}
        self.assertEqual(ev.get("relation_type"), "PDF_TABLE_PAIRING_VERIFIED")

    def test_d_monosplit_bosch_regression(self):
        query = "Bosch Climatizzatore Monosplit Climate 3200i CL3200iU W26E da 9000 btu R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "MONOSPLIT")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertIn("50418718", bom_codes)
        self.assertIn("50009398", bom_codes)
        self.assertEqual(res.get("compatibility_status"), "VERIFIED")

        ev = res.get("compatibility_evidence") or {}
        self.assertEqual(ev.get("relation_type"), "PDF_TABLE_PAIRING_VERIFIED")

    def test_e_multisplit_midea_penta(self):
        query = "Midea Climatizzatore Penta Split Elegance 9+9+9+9+12 con M5OE-42HFN8-Q R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "MULTISPLIT")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        # Multiplicity: 4x 50131051 (9000 btu), 1x 50131075 (12000 btu), 1x 50131174 (UE)
        self.assertEqual(bom_codes.count("50131051"), 4)
        self.assertEqual(bom_codes.count("50131075"), 1)
        self.assertEqual(bom_codes.count("50131174"), 1)
        self.assertEqual(len(bom_codes), 6)

        # Relation must be COMPATIBLE_WITH, not replaced by PDF_TABLE_PAIRING_VERIFIED
        ev = res.get("compatibility_evidence") or {}
        self.assertEqual(ev.get("relation_type"), "COMPATIBLE_WITH")
        # In master, 9+9+9+9+12 is not an authorized combination for M5OE-42HFN8-Q
        self.assertEqual(res.get("compatibility_status"), "NOT_VERIFIED")

    def test_f_componente_multisplit_venduto_singolarmente(self):
        query = "Midea Unità Interna Multisplit Elegance 9000 btu MSAGSAU-09HRDN8"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "UI_ONLY")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertEqual(bom_codes, ["50131051"])

    def test_g_ue_multisplit_venduta_singolarmente(self):
        query = "Midea Unità Esterna Multisplit 5 attacchi M5OE-42HFN8-Q R32"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "UE_ONLY")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertEqual(bom_codes, ["50131174"])

    def test_h_daikin_multisplit_con_serbatoio_acs(self):
        query = "Daikin Sistema Multi+ con Serbatoio A.C.S. 120L EKHWET120BV3 + MultiSplit 4MWXM52A(9) Inverter Wi-Fi Optional Classe A+++"
        res = self.engine.search(query, limit=10)

        self.assertEqual(res.get("product_scope"), "MULTISPLIT")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        # BOM: 50248339 (Serbatoio) + 50228508 (UE)
        self.assertEqual(bom_codes, ["50248339", "50228508"])

        # Nessuna UI aggiunta automaticamente
        for c in res.get("bom", []):
            self.assertFalse(c.get("is_ui", False))

        # Nessun accessorio Wi-Fi aggiunto
        for c in res.get("bom", []):
            name_u = (c.get("name") or "").upper()
            mfg_u = (c.get("mfg_code") or "").upper()
            self.assertNotIn("WIFI", name_u)
            self.assertNotIn("WI-FI", name_u)
            self.assertNotIn("BRP", mfg_u)

        # compatibility_status può restare NOT_VERIFIED se la configurazione completa non è verificabile
        self.assertEqual(res.get("compatibility_status"), "NOT_VERIFIED")

    def test_boiler_and_default_adapter_expand_relations_signature(self):
        from src.adapters.boiler import BoilerCategoryAdapter
        from src.adapters.default import DefaultCategoryAdapter

        boiler_adapter = BoilerCategoryAdapter()
        default_adapter = DefaultCategoryAdapter()

        # 1. BoilerCategoryAdapter con query_context={}
        res1 = boiler_adapter.expand_relations(anchor_items=[], lookup_dict={}, query_context={})
        self.assertEqual(res1, [])

        # 2. BoilerCategoryAdapter senza query_context (backward-compatible)
        res2 = boiler_adapter.expand_relations(anchor_items=[], lookup_dict={})
        self.assertEqual(res2, [])

        # 3. DefaultCategoryAdapter con query_context={}
        res3 = default_adapter.expand_relations(anchor_items=[], lookup_dict={}, query_context={})
        self.assertEqual(res3, [])

        # 4. DefaultCategoryAdapter senza query_context
        res4 = default_adapter.expand_relations(anchor_items=[], lookup_dict={})
        self.assertEqual(res4, [])

    def test_end_to_end_ferroli_boiler_query(self):
        query = "Ferroli 50056552 Bluehelix Hitech RRT H Solar Solo Caldaia 28"
        res = self.engine.search(query, limit=10)
        self.assertEqual(res.get("detected_category"), "BOILER")
        bom_codes = [c.get("code") for c in res.get("bom", [])]
        self.assertIn("50056552", bom_codes)


if __name__ == "__main__":
    unittest.main()

