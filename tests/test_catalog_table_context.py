import json
import tempfile
import unittest
from pathlib import Path

from src.core.catalog_table_context import (
    CatalogTableContextIndex,
    make_family_key,
)
from src.core.evidence_reranker import EvidenceTier, GenericEvidenceReranker


def _write_context(tmp_path: Path):
    path = tmp_path / "catalog_table_context.json"
    path.write_text(
        json.dumps(
            {
                "50131075": {
                    "brand": "MIDEA",
                    "catalog_family": "ELEGANCE",
                    "family_key": "MIDEA_ELEGANCE",
                    "table_title": "ELEGANCE",
                    "table_id": "PDF_P0539_TEST",
                    "page": 539,
                    "section_title": "CONDIZIONATORI RESIDENZIALI R32",
                    "source": "PDF_LAYOUT",
                    "confidence": 1.0,
                    "alternate_table_contexts": [],
                },
                "50079599": {
                    "brand": "MIDEA",
                    "catalog_family": "XTREME PRO WIFI",
                    "family_key": "MIDEA_XTREME_PRO_WIFI",
                    "table_title": "XTREME PRO WIFI",
                    "table_id": "PDF_P0539_WIFI",
                    "page": 539,
                    "section_title": "CONDIZIONATORI RESIDENZIALI R32",
                    "source": "PDF_LAYOUT",
                    "confidence": 1.0,
                    "alternate_table_contexts": [
                        {
                            "brand": "MIDEA",
                            "catalog_family": "XTREME PRO GREEN",
                            "family_key": "MIDEA_XTREME_PRO_GREEN",
                            "table_title": "XTREME PRO GREEN",
                            "table_id": "PDF_P0539_GREEN",
                            "page": 539,
                            "source": "PDF_LAYOUT",
                        }
                    ],
                },
                "50283873": {
                    "brand": "HAIER",
                    "catalog_family": "EXPERT",
                    "family_key": "HAIER_EXPERT",
                    "table_title": "EXPERT",
                    "table_id": "PDF_P0562_EXPERT",
                    "page": 562,
                    "source": "PDF_LAYOUT",
                    "confidence": 1.0,
                    "alternate_table_contexts": [
                        {
                            "brand": "HAIER",
                            "catalog_family": "EXPERT BIANCO",
                            "table_title": "EXPERT BIANCO",
                            "table_id": "PDF_P0565_EXPERT_BIANCO",
                            "page": 565,
                            "source": "PDF_LAYOUT",
                        }
                    ],
                },
                "50283866": {
                    "brand": "HAIER",
                    "catalog_family": "EXPERT",
                    "family_key": "HAIER_EXPERT",
                    "table_title": "EXPERT",
                    "table_id": "PDF_P0562_3545FC84D5",
                    "page": 562,
                    "source": "PDF_LAYOUT",
                    "confidence": 1.0,
                    "alternate_table_contexts": [
                        {
                            "brand": "HAIER",
                            "catalog_family": "EXPERT BIANCO",
                            "family_key": "HAIER_EXPERT_BIANCO",
                            "table_title": "EXPERT BIANCO",
                            "table_id": "PDF_P0557_8B6F027F86",
                            "page": 557,
                            "source": "PDF_LAYOUT",
                        }
                    ],
                },
                "50283899": {
                    "brand": "HAIER",
                    "catalog_family": "EXPERT",
                    "family_key": "HAIER_EXPERT",
                    "table_title": "EXPERT",
                    "table_id": "PDF_P0562_EXPERT",
                    "page": 562,
                    "source": "PDF_LAYOUT",
                    "confidence": 1.0,
                    "alternate_table_contexts": [],
                },
            }
        ),
        encoding="utf-8",
    )
    return CatalogTableContextIndex(path)


class TestCatalogTableContext(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.index = _write_context(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_family_key_preserves_brand_and_meaningful_plus(self):
        self.assertEqual(make_family_key("Midea", "BREEZELESS+"), "MIDEA_BREEZELESS_PLUS")
        self.assertEqual(make_family_key("Baxi", "CASSETTA"), "BAXI_CASSETTA")
        self.assertEqual(make_family_key("Hisense", "CASSETTA"), "HISENSE_CASSETTA")

    def test_pdf_context_overrides_lower_priority_family(self):
        item = {
            "code": "50131075",
            "brand": "MIDEA",
            "catalog_family": "XTREME PRO",
            "family_key": "MIDEA_XTREME_PRO",
            "table_source": "PRODUCT_NAME",
        }
        self.index.enrich_item(item)
        self.index.apply_family_fallback(item, "XTREME PRO", "COMPATIBILITY_MASTER", priority=2)
        self.assertEqual(item["catalog_family"], "ELEGANCE")
        self.assertEqual(item["family_key"], "MIDEA_ELEGANCE")
        self.assertEqual(item["table_source"], "PDF_LAYOUT")
        self.assertEqual(item["table_context"]["page"], 539)

    def test_brand_scoped_query_analysis_and_structured_retrieval(self):
        analysis = self.index.analyze_query("Climatizzatore Midea Xtreme Pro WiFi", "MIDEA")
        self.assertEqual(
            analysis,
            {
                "requested_brand": "MIDEA",
                "requested_family": "XTREME PRO WIFI",
                "requested_family_key": "MIDEA_XTREME_PRO_WIFI",
            },
        )
        self.assertEqual(self.index.codes_for_family_key("MIDEA_XTREME_PRO_GREEN"), ["50079599"])

    def test_alternate_family_matches_without_replacing_primary_family(self):
        from src.adapters.climate import ClimateCategoryAdapter

        item = {"code": "50283873", "brand": "HAIER"}
        self.index.enrich_item(item)

        match = GenericEvidenceReranker.evaluate_catalog_family_match(
            item,
            {
                "requested_brand": "HAIER",
                "requested_family": "EXPERT BIANCO",
                "requested_family_key": "HAIER_EXPERT_BIANCO",
            },
        )

        self.assertEqual(match, "exact")
        self.assertEqual(item["catalog_family"], "EXPERT")
        self.assertEqual(item["family_key"], "HAIER_EXPERT")
        self.assertEqual(
            CatalogTableContextIndex.candidate_family_keys(item),
            {"HAIER_EXPERT", "HAIER_EXPERT_BIANCO"},
        )
        self.assertEqual(
            item["_matched_table_context"]["catalog_family"],
            "EXPERT BIANCO",
        )
        climate_match = ClimateCategoryAdapter(
            ac_master_path="__missing__",
            pdf_specs_path="__missing__",
            table_context_index=self.index,
        ).evaluate_series_match(
            item,
            {
                "requested_brand": "HAIER",
                "requested_family_key": "HAIER_EXPERT_BIANCO",
            },
        )
        self.assertEqual(climate_match, "exact")
        self.assertEqual(item["catalog_family"], "EXPERT")

    def test_parent_only_product_does_not_match_unproven_leaf(self):
        item = {"code": "50283899", "brand": "HAIER"}
        self.index.enrich_item(item)

        match = GenericEvidenceReranker.evaluate_catalog_family_match(
            item,
            {
                "requested_brand": "HAIER",
                "requested_family": "EXPERT BIANCO",
                "requested_family_key": "HAIER_EXPERT_BIANCO",
            },
        )

        self.assertEqual(match, "mismatch")
        self.assertEqual(item["catalog_family"], "EXPERT")
        self.assertEqual(
            CatalogTableContextIndex.candidate_family_keys(item),
            {"HAIER_EXPERT"},
        )

    def test_table_family_exact_is_strong_and_same_brand_mismatch_is_penalized(self):
        reranker = GenericEvidenceReranker()
        query_context = {
            "detected_brand": "MIDEA",
            "requested_brand": "MIDEA",
            "requested_family": "ELEGANCE",
            "requested_family_key": "MIDEA_ELEGANCE",
        }
        exact = {"code": "50131075", "brand": "MIDEA", "name": "UI ELEGANCE 12"}
        self.index.enrich_item(exact)
        tier, exact_score = reranker.evaluate_candidate(
            exact, ["midea", "elegance"], detected_brand="MIDEA", query_context=query_context
        )
        self.assertEqual(tier, EvidenceTier.TIER_5_CATALOG_FAMILY_EXACT)
        self.assertEqual(exact["family_match"], "exact")
        self.assertEqual(exact["family_evidence"], "CATALOG_FAMILY_EXACT")

        mismatch = {"code": "50079599", "brand": "MIDEA", "name": "UE XTREME PRO GREEN"}
        self.index.enrich_item(mismatch)
        mismatch_tier, mismatch_score = reranker.evaluate_candidate(
            mismatch, ["midea", "elegance"], detected_brand="MIDEA", query_context=query_context
        )
        self.assertEqual(mismatch_tier, EvidenceTier.TIER_9_BROAD_DISCOVERY)
        self.assertEqual(mismatch["family_match"], "mismatch")
        self.assertEqual(mismatch["family_evidence"], "CATALOG_FAMILY_MISMATCH")
        self.assertGreater(exact_score, mismatch_score)

    def test_different_brand_family_is_not_a_family_mismatch(self):
        reranker = GenericEvidenceReranker()
        item = {
            "brand": "HISENSE",
            "catalog_family": "CASSETTA",
            "family_key": "HISENSE_CASSETTA",
            "table_source": "PDF_LAYOUT",
            "table_context": {"family_key": "HISENSE_CASSETTA"},
        }
        query_context = {
            "detected_brand": "MIDEA",
            "requested_brand": "MIDEA",
            "requested_family": "CASSETTA",
            "requested_family_key": "MIDEA_CASSETTA",
        }
        tier, _ = reranker.evaluate_candidate(
            item, ["midea", "cassetta"], detected_brand="MIDEA", query_context=query_context
        )
        self.assertEqual(tier, EvidenceTier.TIER_9_BROAD_DISCOVERY)
        self.assertEqual(item.get("family_match"), "none")

    def test_same_brand_same_compatibility_different_family_loses_to_exact_family(self):
        """
        Test negativo obbligatorio:
        Stessa marca (MIDEA) + stessa compatibilità con UE (COMPATIBLE_WITH) + famiglia diversa (XTREME PRO)
        DEVE perdere contro la famiglia esatta richiesta (ELEGANCE).
        """
        reranker = GenericEvidenceReranker()
        query_context = {
            "detected_brand": "MIDEA",
            "requested_brand": "MIDEA",
            "requested_family": "ELEGANCE",
            "requested_family_key": "MIDEA_ELEGANCE",
            "requested_btus": [12000],
        }

        # UI A: Midea Elegance 12 con relazione di compatibilità
        ui_elegance = {
            "code": "50131075",
            "brand": "MIDEA",
            "name": "UI ELEGANCE 12",
            "taglia_btu": 12000,
            "_is_relation_candidate": True,
            "_relation_type": "COMPATIBLE_WITH",
            "_relation_confidence": 0.90,
            "_relation_evidences": [{
                "relation_type": "COMPATIBLE_WITH",
                "source_code": "50131174",
                "confidence": 0.90,
                "provenance": "climatizzatori_compatibilita_master.json",
            }],
        }
        self.index.enrich_item(ui_elegance)

        # UI B: Midea Xtreme Pro 12 con IDENTICA relazione di compatibilità con la stessa UE
        ui_xtreme = {
            "code": "50079599",
            "brand": "MIDEA",
            "name": "UI XTREME PRO 12",
            "taglia_btu": 12000,
            "_is_relation_candidate": True,
            "_relation_type": "COMPATIBLE_WITH",
            "_relation_confidence": 0.90,
            "_relation_evidences": [{
                "relation_type": "COMPATIBLE_WITH",
                "source_code": "50131174",
                "confidence": 0.90,
                "provenance": "climatizzatori_compatibilita_master.json",
            }],
        }
        self.index.enrich_item(ui_xtreme)

        tier_a, score_a = reranker.evaluate_candidate(
            ui_elegance, ["midea", "elegance", "12"], detected_brand="MIDEA", query_context=query_context
        )
        tier_b, score_b = reranker.evaluate_candidate(
            ui_xtreme, ["midea", "elegance", "12"], detected_brand="MIDEA", query_context=query_context
        )

        # L'UI con famiglia esatta vince nettamente sia per Tier (T5 vs T9) che per punteggio
        self.assertEqual(tier_a, EvidenceTier.TIER_5_CATALOG_FAMILY_EXACT)
        self.assertEqual(ui_elegance["family_match"], "exact")
        self.assertEqual(tier_b, EvidenceTier.TIER_9_BROAD_DISCOVERY)
        self.assertEqual(ui_xtreme["family_match"], "mismatch")
        self.assertGreater(score_a, score_b + 100.0)

    def test_candidates_assigned_to_natural_product_slots_never_slot_table_family(self):
        from src.adapters.climate import ClimateCategoryAdapter
        adapter = ClimateCategoryAdapter()
        query_context = {
            "detected_brand": "MIDEA",
            "requested_family_key": "MIDEA_ELEGANCE",
            "requested_btus": [12000, 18000],
        }
        ui_12 = {"code": "50131075", "brand": "MIDEA", "is_ui": True, "taglia_btu": 12000}
        ue_multi = {"code": "50131174", "brand": "MIDEA", "is_ue": True}
        acc = {"code": "50418541", "brand": "MIDEA", "is_accessory": True}

        self.index.enrich_item(ui_12)
        self.index.enrich_item(ue_multi)
        self.index.enrich_item(acc)

        self.assertEqual(adapter.assign_slot(ui_12, query_context), "slot_ui_12000")
        self.assertEqual(adapter.assign_slot(ue_multi, query_context), "slot_ue")
        self.assertEqual(adapter.assign_slot(acc, query_context), "slot_accessory")

    def test_expand_candidate_pool_enriches_existing_candidates_with_relation_evidences(self):
        from src.core.relation_types import TypedRelationExpander, TypedRelation, RelationType
        expander = TypedRelationExpander()
        expander.register_relation(
            TypedRelation(
                source_code="50131174",
                target_code="50131075",
                relation_type=RelationType.COMPATIBLE_WITH,
                confidence=0.95,
                provenance="test_matrix",
            )
        )
        merged = {
            "50131075": {"code": "50131075", "name": "UI ELEGANCE 12", "brand": "MIDEA"}
        }
        lookup = {"50131075": merged["50131075"]}
        expanded = expander.expand_candidate_pool(["50131174"], lookup, merged)

        self.assertEqual(len(merged), 1)  # nessun duplicato
        item = merged["50131075"]
        self.assertTrue(item["_is_relation_candidate"])
        self.assertEqual(item["_relation_type"], "COMPATIBLE_WITH")
        self.assertEqual(len(item["_relation_evidences"]), 1)
        self.assertEqual(item["_relation_evidences"][0]["relation_type"], "COMPATIBLE_WITH")
        self.assertIn(item, expanded)

    def test_haier_50283866_candidate_family_keys_and_search_regression(self):
        from catalog_search_engine import CATALOG_TABLE_CONTEXT_PATH, CatalogSearchEngine

        real_index = CatalogTableContextIndex(CATALOG_TABLE_CONTEXT_PATH)
        item = {"code": "50283866", "brand": "HAIER"}
        real_index.enrich_item(item)
        keys = CatalogTableContextIndex.candidate_family_keys(item)
        self.assertIn("HAIER_EXPERT", keys)
        self.assertIn("HAIER_EXPERT_BIANCO", keys)

        engine = CatalogSearchEngine()
        query = "Haier Unità Interna Expert Bianco AS42XCAHRA-1 R32"
        res = engine.search(query, limit=5)
        found = False
        for r in res.get("results", []):
            if str(r.get("code")) == "50283866":
                found = True
                self.assertEqual(r.get("family_match"), "exact")
                self.assertEqual(r.get("catalog_family"), "EXPERT")
                self.assertEqual(r.get("family_key"), "HAIER_EXPERT")
                break
        self.assertTrue(found, "PT 50283866 non trovato nei risultati di ricerca per la query Haier Expert Bianco")


if __name__ == "__main__":
    unittest.main()
