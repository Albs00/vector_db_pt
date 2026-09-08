import unittest
from src.adapters.climate import extract_split_capacities, ClimateCategoryAdapter
from src.core.relation_types import RelationType
from catalog_search_engine import CatalogSearchEngine


class TestBaxiCanalizzatoInverseRelation(unittest.TestCase):
    def test_extract_split_capacities_commercial_btu(self):
        # Tutte le taglie commerciali richieste fino a 60000
        commercial_btus = [
            7000, 9000, 12000, 15000, 18000, 21000, 24000,
            28000, 30000, 36000, 42000, 48000, 55000, 60000
        ]
        for btu in commercial_btus:
            extracted = extract_split_capacities(f"Climatizzatore Baxi {btu} btu R32")
            self.assertEqual(extracted, [btu], f"Fallita estrazione per {btu} btu")

        # Formati con punto o abbreviazioni
        self.assertEqual(extract_split_capacities("48.000 btu"), [48000])
        self.assertEqual(extract_split_capacities("48000 btu"), [48000])

    def test_technical_attributes_phase_isolation(self):
        adapter = ClimateCategoryAdapter()
        q = "Baxi Climatizzatore Monosplit Inverter Canalizzato RZGND 48000 btu R32 Trifase WiFi Optional"
        ctx = adapter.extract_query_context(q)

        # 1. requested_btus=[48000]
        self.assertEqual(ctx.get("requested_btus"), [48000])

        # 2. phase=TRIFASE come attributo tecnico
        self.assertEqual(ctx.get("phase"), "TRIFASE")
        self.assertTrue(ctx.get("is_trifase"))
        self.assertFalse(ctx.get("is_monofase"))

        # 3. NON deve mai entrare in requested_series o family
        self.assertNotEqual(ctx.get("requested_series"), "TRIFASE")
        self.assertNotEqual(ctx.get("requested_series"), "MONOFASE")

    def test_end_to_end_baxi_canalizzato_48000(self):
        engine = CatalogSearchEngine()
        q = "Baxi Climatizzatore Monosplit Inverter Canalizzato RZGND 48000 btu R32 Trifase WiFi Optional"
        res = engine.search(q, limit=10)

        qa_info = res.get("query_analysis", {})
        q_ctx = qa_info.get("query_context", {})

        # Verifiche Query Analysis
        self.assertEqual(q_ctx.get("requested_btus"), [48000])
        self.assertEqual(q_ctx.get("phase"), "TRIFASE")
        self.assertEqual(qa_info.get("requested_family_key"), "BAXI_CANALIZZATA")
        self.assertTrue(q_ctx.get("has_reliable_anchor"))

        pools = res.get("candidate_pools", {})

        # Verifica UI: 50388295 al 1° posto nello slot_ui_48000
        slot_ui = pools.get("slot_ui_48000", [])
        self.assertTrue(len(slot_ui) > 0)
        self.assertEqual(slot_ui[0]["code"], "50388295")
        self.assertEqual(slot_ui[0]["family_match"], "exact")

        # Verifica UE: 50386345 al 1° posto nello slot_ue con relazione da UI anchor
        slot_ue = pools.get("slot_ue", [])
        self.assertTrue(len(slot_ue) > 0)
        top_ue = slot_ue[0]
        self.assertEqual(top_ue["code"], "50386345")
        self.assertEqual(top_ue["family_match"], "exact")
        self.assertEqual(top_ue["evidence_tier"], 4)
        self.assertIn(top_ue["relation_type"], ("PDF_TABLE_PAIRING_VERIFIED", "PAIRED_WITH_VERIFIED"))

        # Verifica che 50225187 non sia primo
        self.assertNotEqual(top_ue["code"], "50225187")


if __name__ == "__main__":
    unittest.main()
