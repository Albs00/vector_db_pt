import unittest
from src.adapters.climate import ClimateCategoryAdapter
from src.core.relation_types import RelationType
from catalog_search_engine import CatalogSearchEngine


class TestBoschClimateTablePairing(unittest.TestCase):
    def test_pdf_table_pairing_extraction_bosch(self):
        adapter = ClimateCategoryAdapter()
        ui_pairs = adapter._pdf_table_pairs_ui_to_ue.get("50418718", [])
        self.assertTrue(len(ui_pairs) > 0, "Nessuna coppia trovata per UI Bosch 50418718")

        # Verifica target UE atteso
        paired_ues = [p["target_code"] for p in ui_pairs]
        self.assertIn("50009398", paired_ues, "UE 50009398 non trovata tra le coppie PDF")
        self.assertNotIn("50113217", paired_ues, "UE 50113217 (Climate 6000i) non deve essere accoppiata da tabella PDF")

        match_meta = [p for p in ui_pairs if p["target_code"] == "50009398"][0]
        self.assertEqual(match_meta["table_id"], "PDF_P0609_266067E51C")
        self.assertEqual(match_meta["page"], 609)
        self.assertEqual(match_meta["brand"], "BOSCH")

    def test_end_to_end_bosch_climate_3200i(self):
        engine = CatalogSearchEngine()
        query = "Bosch Climatizzatore Monosplit Climate 3200i CL3200iU W26E 9000 btu"
        res = engine.search(query, limit=10)

        pools = res.get("candidate_pools", {})

        # 1. Verifica UI 50418718 al primo posto in slot_ui_9000
        slot_ui = pools.get("slot_ui_9000", [])
        self.assertTrue(len(slot_ui) > 0, "Nessun candidato in slot_ui_9000")
        self.assertEqual(slot_ui[0]["code"], "50418718", f"UI attesa 50418718, trovata {slot_ui[0]['code']}")

        # 2. Verifica UE 50009398 al primo posto in slot_ue con relazione PDF_TABLE_PAIRING_VERIFIED
        slot_ue = pools.get("slot_ue", [])
        self.assertTrue(len(slot_ue) > 0, "Nessun candidato in slot_ue")
        top_ue = slot_ue[0]
        self.assertEqual(top_ue["code"], "50009398", f"UE attesa 50009398, trovata {top_ue['code']}")
        self.assertNotEqual(top_ue["code"], "50113217", "UE non deve essere Climate 6000i (50113217)")
        self.assertEqual(top_ue["relation_type"], "PDF_TABLE_PAIRING_VERIFIED")
        self.assertEqual(top_ue["evidence_tier"], 4)

    def test_relation_priority_order(self):
        # Verifica priorità formale relazioni:
        # PDF_TABLE_PAIRING_VERIFIED > KIT_PAIRING_VERIFIED > PAIRED_WITH_DERIVED > COMPATIBLE_WITH
        def prio(rt):
            if rt == RelationType.PDF_TABLE_PAIRING_VERIFIED:
                return 0
            elif rt in (RelationType.KIT_PAIRING_VERIFIED, RelationType.PAIRED_WITH_VERIFIED, RelationType.PAIRED_WITH):
                return 1
            elif rt == RelationType.PAIRED_WITH_DERIVED:
                return 2
            elif rt in (RelationType.REQUIRES, RelationType.INCLUDES, RelationType.KIT_COMPONENT):
                return 3
            return 4

        self.assertLess(prio(RelationType.PDF_TABLE_PAIRING_VERIFIED), prio(RelationType.KIT_PAIRING_VERIFIED))
        self.assertLess(prio(RelationType.KIT_PAIRING_VERIFIED), prio(RelationType.PAIRED_WITH_DERIVED))
        self.assertLess(prio(RelationType.PAIRED_WITH_DERIVED), prio(RelationType.COMPATIBLE_WITH))


if __name__ == "__main__":
    unittest.main()
