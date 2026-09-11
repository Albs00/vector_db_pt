import unittest
import json
from pathlib import Path

from catalog_search_engine import CatalogSearchEngine
from src.adapters.climate import validate_multisplit_combination


class ClimateCommercialPairingPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CatalogSearchEngine()

    @staticmethod
    def _role(result, role):
        return next(
            item
            for item in result.get("bom", [])
            if item.get("role") == role or item.get(f"is_{role.lower()}")
        )

    @staticmethod
    def _role_codes(result, role):
        return [
            str(item.get("code"))
            for item in result.get("bom", [])
            if item.get("role") == role or item.get(f"is_{role.lower()}")
        ]

    @staticmethod
    def _exact_mfg_codes(result):
        return [
            str(item.get("mfg_code") or "")
            for item in result.get("query_analysis", {}).get("exact_token_candidates", [])
            if item.get("mfg_code")
        ]

    def test_toshiba_haori_uses_exact_pdf_commercial_pair(self):
        result = self.engine.search(
            "Toshiba Climatizzatore Haori Bianco 9000 btu con Rivestimenti "
            "in Tessuto Inclusi Inverter R-32 Wi-Fi Classe A+++",
            limit=20,
        )

        self.assertEqual(self._role(result, "UI")["code"], "50383573")
        self.assertEqual(self._role(result, "UE")["code"], "50213924")
        self.assertNotEqual(self._role(result, "UE")["code"], "50292301")
        self.assertEqual(result["pairing_reason"], "PDF_TABLE_PAIRING")
        self.assertEqual(result["pairing_score_breakdown"]["PDF_PAIRING"], 100.0)

    def test_baxi_astra_explicit_commercial_ue_beats_merely_compatible_ue_without_auto_certification(self):
        result = self.engine.search(
            "Baxi Climatizzatore Condizionatore Dual Split Astra 7+12 con "
            "LSGT50-2M Inverter R-32 Wi-Fi Opt. Classe A++",
            limit=20,
        )

        ue = self._role(result, "UE")
        self.assertEqual(ue["code"], "50124121")
        self.assertIn("LSGT 50-2M", ue["name"])
        self.assertEqual(result["pairing_reason"], "EXPLICIT_MODEL_IN_QUERY")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertEqual(result["pairing_status"], "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertFalse(result["mpn_final_allowed"])

    def test_haier_flexis_black_does_not_select_white_ui(self):
        result = self.engine.search(
            "Haier Climatizzatore Monosplit Flexis Plus Nero 12000 btu R-32 "
            "Wi-Fi Classe A+++ Cod. AS35S2SF1FA-MB3",
            limit=20,
        )

        ui = self._role(result, "UI")
        self.assertEqual(ui["code"], "50021642")
        self.assertIn("NERO", ui["name"])
        self.assertNotIn(" BCO", ui["name"])

    def test_haier_flexis_black_multisplit_keeps_black_ui_family(self):
        result = self.engine.search(
            "Haier Climatizzatore Quadri Split Flexis Plus Black 7+12+12+12 "
            "Con 4U75S2SR5FA Inverter Wi-Fi Classe A++",
            limit=20,
        )

        ui_items = [item for item in result["bom"] if item.get("role") == "UI"]
        self.assertEqual(len(ui_items), 4)
        self.assertTrue(all("NERO" in item["name"] for item in ui_items))
        self.assertTrue(all(" BCO" not in item["name"] for item in ui_items))

    def test_explicit_ue_model_in_query_wins_after_ui_identification(self):
        result = self.engine.search(
            "Haier AS42XCAHRA-MB + 1U42S2SM1FA",
            limit=30,
        )

        self.assertEqual(self._role(result, "UI")["code"], "50224067")
        self.assertEqual(self._role(result, "UE")["code"], "99715779")
        self.assertEqual(result["pairing_reason"], "EXPLICIT_MODEL_IN_QUERY")

    def test_pairwise_multisplit_without_catalog_configuration_is_not_final(self):
        result = self.engine.search(
            "Daikin Trial Split Perfera 24000+24000+24000",
            limit=20,
        )

        self.assertEqual(result["compatibility_status"], "NOT_VERIFIED")
        self.assertEqual(result["pairing_status"], "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertFalse(result["mpn_final_allowed"])

    def test_model_tokens_do_not_collapse_revisions(self):
        adapter = self.engine._climate_adapter
        self.assertIsNone(adapter._explicit_model_in_query({"mfg_code": "RXM25A"}, "RXM25A9"))
        self.assertIsNone(adapter._explicit_model_in_query({"mfg_code": "MODEL-V3"}, "MODEL-V4"))
        self.assertIsNone(adapter._explicit_model_in_query({"mfg_code": "RAS-10AVG-E"}, "RAS-10AVG-E1"))

    def test_flexis_white_dual_uses_only_selected_bom_uis_and_is_not_certified_by_master(self):
        result = self.engine.search("Haier Dual Flexis Plus White 9+12", limit=30)

        self.assertEqual(self._role_codes(result, "UI"), ["50026470", "50026487"])
        self.assertEqual(result["pairing_status"], "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertFalse(result["mpn_final_allowed"])
        self.assertEqual(
            result["pairing_diagnostics"]["SELECTED_UI_EVIDENCE_PT"],
            [{"pt": "50026470", "quantity": 1}, {"pt": "50026487", "quantity": 1}],
        )

    def test_flexis_black_dual_uses_only_selected_bom_uis_and_is_not_certified_by_master(self):
        result = self.engine.search("Haier Dual Flexis Plus Black 9+12", limit=30)

        self.assertEqual(self._role_codes(result, "UI"), ["50021635", "50021642"])
        self.assertEqual(result["pairing_status"], "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertFalse(result["mpn_final_allowed"])
        self.assertEqual(
            result["pairing_diagnostics"]["SELECTED_UI_EVIDENCE_PT"],
            [{"pt": "50021635", "quantity": 1}, {"pt": "50021642", "quantity": 1}],
        )

    def test_explicit_haier_ue_base_model_beats_unrelated_master_candidate(self):
        result = self.engine.search(
            "Haier Dual Split con 2U50S2SM1FA 9000+12000",
            limit=30,
        )

        self.assertEqual(self._role(result, "UE")["code"], "50125265")
        self.assertEqual(result["pairing_reason"], "EXPLICIT_MODEL_REVISION_MATCH")
        self.assertEqual(result["pairing_diagnostics"]["EXPLICIT_UE_TOKEN"], "2U50S2SM1FA")
        self.assertEqual(
            result["pairing_diagnostics"]["EXPLICIT_UE_MATCH_TYPE"],
            "EXPLICIT_MODEL_REVISION_MATCH",
        )
        selected_ui_codes = set(self._role_codes(result, "UI"))
        rejected_ui_codes = set(
            result["pairing_diagnostics"]["REJECTED_NON_BOM_UI_EVIDENCE"]
        )
        self.assertTrue(rejected_ui_codes)
        self.assertTrue(selected_ui_codes.isdisjoint(rejected_ui_codes))
        ue_relation_sources = {
            str(evidence.get("source_code"))
            for evidence in self._role(result, "UE").get("relation_evidences", [])
        }
        self.assertTrue(ue_relation_sources.issubset(selected_ui_codes))

    def test_haier_penta_bom_remains_unchanged(self):
        result = self.engine.search(
            "Haier Penta Flexis Plus White 7+9+9+12+12 con 5U105S2SS5FA",
            limit=30,
        )

        self.assertEqual(
            [str(item.get("code")) for item in result["bom"]],
            ["50125319", "50028528", "50026470", "50026470", "50026487", "50026487"],
        )

    def test_toshiba_dual_haori_master_only_pairing_is_not_final(self):
        result = self.engine.search("Toshiba Dual Haori 9000+12000", limit=30)

        self.assertEqual(result["pairing_reason"], "MASTER_COMPATIBILITY_FALLBACK")
        self.assertEqual(result["pairing_status"], "CONFIGURAZIONE_NON_CONFERMATA")
        self.assertEqual(result["compatibility_status"], "NOT_VERIFIED")
        self.assertFalse(result["mpn_final_allowed"])

    def test_beretta_multisplit_ue_regressions_remain_unchanged(self):
        cases = (
            ("Beretta Dual Breva 9000+12000 con EX18000-2", "50318438"),
            ("Beretta Dual Breva 9000+18000 con EX18000-3", "50215218"),
            ("Beretta Dual Breva 9000+24000 con EX24000-4", "50215232"),
        )

        for query, expected_ue in cases:
            with self.subTest(query=query):
                result = self.engine.search(query, limit=30)
                self.assertEqual(self._role(result, "UE")["code"], expected_ue)

    def test_a_exact_haier_ue_does_not_certify_pairwise_only_configuration(self):
        result = self.engine.search(
            "Haier Dual Split con 2U50S2SM1FA-3 9000+12000", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50125265")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(
            result["pairing_diagnostics"]["EXPLICIT_UE_MATCH_TYPE"],
            "EXPLICIT_MODEL_EXACT_MATCH",
        )
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_b_exact_haier_2u40_is_preserved_but_not_auto_certified(self):
        result = self.engine.search(
            "Haier Dual Split con 2U40S2SM1FA 9000+12000", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "99787707")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_c_nonexistent_revision_remains_explicit_and_never_becomes_exact(self):
        result = self.engine.search(
            "Haier Dual Split con 2U50S2SM1FA-2 9000+12000", limit=30
        )
        diag = result["pairing_diagnostics"]
        self.assertEqual(diag["EXPLICIT_UE_TOKEN"], "2U50S2SM1FA-2")
        self.assertEqual(result["product_identity_status"], "REVISION_CANDIDATE")
        self.assertNotEqual(diag["EXPLICIT_UE_MATCH_TYPE"], "EXPLICIT_MODEL_EXACT_MATCH")
        self.assertFalse(result["mpn_final_allowed"])

    def test_d_explicit_two_port_ue_is_not_replaced_for_trial_configuration(self):
        result = self.engine.search(
            "Haier Trial Split con 2U50S2SM1FA 9000+9000+12000", limit=30
        )
        self.assertEqual(result["pairing_diagnostics"]["EXPLICIT_UE_TOKEN"], "2U50S2SM1FA")
        self.assertEqual(self._role(result, "UE")["code"], "50125265")
        self.assertEqual(result["configuration_status"], "CONFLICT")
        self.assertEqual(
            result["mpn_final_block_reason"],
            "EXPLICIT_UE_CONFIGURATION_CONFLICT",
        )
        self.assertFalse(result["mpn_final_allowed"])

    def test_e_explicit_penta_ue_is_preserved_for_dual_but_configuration_conflicts(self):
        result = self.engine.search(
            "Haier Dual Split con 5U105S2SS5FA 9000+12000", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50125319")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "CONFLICT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_f_generic_haier_dual_is_discovery_only_and_not_final(self):
        result = self.engine.search("Haier Dual Split 9000+12000 R32", limit=30)
        self.assertEqual(result["product_identity_status"], "DISCOVERY_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_g_flexis_white_ui_identity_is_preserved_without_auto_certification(self):
        result = self.engine.search(
            "Haier Dual Split Flexis Plus White 9000+12000 R32", limit=30
        )
        self.assertEqual(self._role_codes(result, "UI"), ["50026470", "50026487"])
        self.assertFalse(result["mpn_final_allowed"])

    def test_h_expert_ui_identity_is_preserved_without_auto_certification(self):
        result = self.engine.search(
            "Haier Dual Split Expert 9000+12000 R32", limit=30
        )
        self.assertEqual(self._role_codes(result, "UI"), ["50125210", "50125227"])
        self.assertFalse(result["mpn_final_allowed"])

    def test_i_selected_ui_context_preserves_multiset_quantities(self):
        result = self.engine.search(
            "Haier Trial Split Flexis Plus White 9000+9000+12000", limit=30
        )
        self.assertEqual(
            result["pairing_diagnostics"]["SELECTED_UI_EVIDENCE_PT"],
            [{"pt": "50026470", "quantity": 2}, {"pt": "50026487", "quantity": 1}],
        )

    def test_j_toshiba_without_explicit_ue_remains_pairwise_only(self):
        result = self.engine.search("Toshiba Dual Split Haori 9000+12000", limit=30)
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_k_toshiba_exact_2m14_identity_does_not_replace_full_configuration_proof(self):
        result = self.engine.search(
            "Toshiba Dual Split Haori 9000+12000 con RAS-2M14G3AVG-E", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215768")
        self.assertEqual(self._role_codes(result, "UI"), ["50383573", "50214044"])
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_l_toshiba_exact_2m10_identity_does_not_replace_full_configuration_proof(self):
        result = self.engine.search(
            "Toshiba Dual Split Haori 9000+12000 con RAS-2M10G3AVG-E", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215881")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_m_daikin_exact_a_identity_is_distinct_and_not_pairwise_certified(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40A", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50202164")
        self.assertEqual(self._role_codes(result, "UI"), ["50307791", "50307791"])
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_n_daikin_exact_a9_identity_remains_distinct(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40A9", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50202171")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_o_daikin_incomplete_model_is_ambiguous_and_has_no_definitive_ue(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40", limit=30
        )
        self.assertEqual(result["product_identity_status"], "AMBIGUOUS_REVISION")
        self.assertFalse(result["mpn_final_allowed"])
        candidates = {
            item["catalog_model"]
            for item in result["pairing_diagnostics"]["EXPLICIT_UE_CANDIDATES"]
        }
        self.assertTrue({"2MXM40A", "2MXM40A9", "2MXM40N9"}.issubset(candidates))
        self.assertFalse(any(item.get("role") == "UE" for item in result["bom"]))

    def test_p_beretta_explicit_four_port_ue_is_preserved_but_conflicts_with_dual(self):
        result = self.engine.search(
            "Beretta Dual Split Breva E 9000+9000 con EX24000-4 R32", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215232")
        self.assertEqual(self._role_codes(result, "UI"), ["50318322", "50318322"])
        self.assertEqual(result["configuration_status"], "CONFLICT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_microfix_1_beretta_quadri_mixed_capacities_is_not_false_conflict(self):
        result = self.engine.search(
            "Beretta Climatizzatore Quadri split Breva 9+9+12+12 con EX24000-4 R32",
            limit=30,
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215232")
        self.assertEqual(
            self._role_codes(result, "UI"),
            ["99840730", "99840730", "50019380", "50019380"],
        )
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertIsNone(
            result["pairing_diagnostics"].get("CONFIGURATION_CONFLICT_REASON")
        )
        self.assertFalse(result["mpn_final_allowed"])

    def test_microfix_2_beretta_quadri_equal_capacities_uses_direct_table(self):
        result = self.engine.search(
            "Beretta Climatizzatore Quadri split Breva 9+9+9+9 con EX24000-4 R32",
            limit=30,
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215232")
        self.assertEqual(self._role_codes(result, "UI"), ["99840730"] * 4)
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertTrue(result["mpn_final_allowed"])

    def test_microfix_3_daikin_a_exact_token_has_full_model_boundary(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40A", limit=30
        )
        exact_models = self._exact_mfg_codes(result)
        self.assertIn("2MXM40A", exact_models)
        self.assertNotIn("2MXM40A9", exact_models)
        self.assertEqual(self._role(result, "UE")["code"], "50202164")

    def test_microfix_4_daikin_a9_does_not_report_a_as_exact(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40A9", limit=30
        )
        exact_models = self._exact_mfg_codes(result)
        self.assertIn("2MXM40A9", exact_models)
        self.assertNotIn("2MXM40A", exact_models)
        self.assertEqual(self._role(result, "UE")["code"], "50202171")

    def test_microfix_5_daikin_incomplete_token_has_only_near_candidates(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40", limit=30
        )
        self.assertFalse(self._exact_mfg_codes(result))
        self.assertEqual(result["product_identity_status"], "AMBIGUOUS_REVISION")
        self.assertFalse(any(item.get("role") == "UE" for item in result["bom"]))
        self.assertFalse(result["mpn_final_allowed"])

    def test_microfix_6_beretta_spaced_suffix_is_part_of_exact_ue_identity(self):
        result = self.engine.search(
            "Beretta Climatizzatore Dual split Breva E 9+9 con EX18000-2 E R32",
            limit=30,
        )
        diag = result["pairing_diagnostics"]
        self.assertEqual(self._role(result, "UE")["code"], "50318438")
        self.assertEqual(diag["EXPLICIT_UE_TOKEN"], "EX18000-2 E")
        self.assertEqual(diag["EXPLICIT_UE_MATCH_TYPE"], "EXPLICIT_MODEL_EXACT_MATCH")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertTrue(result["mpn_final_allowed"])

    def test_microfix_7_beretta_trial_exact_identity_uses_direct_combination_evidence(self):
        result = self.engine.search(
            "Beretta Trial Split Breva 9+9+12 con EX18000-3", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50215218")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertTrue(result["mpn_final_allowed"])

    def test_microfix_8_haier_trial_revision_topology_conflict_is_preserved(self):
        result = self.engine.search(
            "Haier Trial Split con 2U50S2SM1FA 9+9+12", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50125265")
        self.assertEqual(result["product_identity_status"], "REVISION_CANDIDATE")
        self.assertEqual(result["configuration_status"], "CONFLICT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_microfix_9_haier_penta_exact_dual_conflict_is_preserved(self):
        result = self.engine.search(
            "Haier Dual Split con 5U105S2SS5FA 9+12", limit=30
        )
        self.assertEqual(self._role(result, "UE")["code"], "50125319")
        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "CONFLICT")
        self.assertFalse(result["mpn_final_allowed"])

    def test_microfix_10_flexis_white_ui_selection_and_gate_are_preserved(self):
        result = self.engine.search(
            "Haier Dual Split Flexis Plus White 9+12", limit=30
        )
        self.assertEqual(self._role_codes(result, "UI"), ["50026470", "50026487"])
        self.assertFalse(result["mpn_final_allowed"])

    def test_full_combination_validator_returns_structured_multiset_match(self):
        self.engine._ensure_initialized()
        adapter = self.engine._climate_adapter
        ue = adapter._ac_master_ues["50215218"]
        uis = [
            dict(adapter._ac_master_uis["99840730"], code="99840730"),
            dict(adapter._ac_master_uis["99840730"], code="99840730"),
            dict(adapter._ac_master_uis["50019380"], code="50019380"),
        ]

        match = validate_multisplit_combination(ue, uis)

        self.assertTrue(match["matched"])
        self.assertEqual(match["requested_configuration"], "25+25+35")
        self.assertEqual(match["matched_configuration"], "25+25+35")
        self.assertEqual(
            match["selected_ui_multiset"],
            {"99840730": 2, "50019380": 1},
        )
        self.assertEqual(match["source_field"], "combinazioni_ammesse")
        self.assertEqual(match["evidence_strength"], "UNKNOWN_PROVENANCE")

    def test_full_combination_strength_requires_explicit_origin_metadata(self):
        ue = {
            "code": "SYNTHETIC-UE",
            "porte_attacchi": 2,
            "combinazioni_ammesse": ["25+25"],
            "combinazioni_ammesse_provenance": {
                "25+25": {
                    "evidence_strength": "CATALOG_TABLE_VERIFIED",
                    "provenance": "test-only explicit table-row provenance",
                }
            },
        }
        uis = [
            {"code": "UI-1", "taglia_btu": 9000},
            {"code": "UI-1", "taglia_btu": 9000},
        ]

        match = validate_multisplit_combination(ue, uis)

        self.assertTrue(match["matched"])
        self.assertEqual(match["evidence_strength"], "CATALOG_TABLE_VERIFIED")
        self.assertEqual(
            match["evidence_provenance"],
            "test-only explicit table-row provenance",
        )

    def test_full_combination_match_is_wired_to_gate_with_direct_sidecar_provenance(self):
        result = self.engine.search(
            "Beretta Trial Split Breva 9+9+12 con EX18000-3", limit=30
        )
        diag = result["pairing_diagnostics"]

        self.assertTrue(diag["FULL_CONFIGURATION_MATCHED"])
        self.assertEqual(diag["FULL_CONFIGURATION_REQUESTED"], "25+25+35")
        self.assertEqual(diag["FULL_CONFIGURATION_CATALOG"], "25+25+35")
        self.assertEqual(
            diag["FULL_CONFIGURATION_EVIDENCE_STRENGTH"],
            "CATALOG_TABLE_VERIFIED",
        )
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertTrue(result["mpn_final_allowed"])

    def test_missing_full_combination_is_not_promoted_or_marked_conflict(self):
        result = self.engine.search(
            "Beretta Quadri Split Breva 9+9+12+12 con EX24000-4", limit=30
        )
        diag = result["pairing_diagnostics"]

        self.assertFalse(diag["FULL_CONFIGURATION_MATCHED"])
        self.assertEqual(diag["FULL_CONFIGURATION_REQUESTED"], "25+25+35+35")
        self.assertIsNone(diag["FULL_CONFIGURATION_CATALOG"])
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_per_combination_sidecar_has_direct_beretta_layout_evidence(self):
        sidecar_path = Path("Knowledge/climatizzatori_combinazioni_provenance.json")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        evidence = sidecar["50215218"]["25+25+35"]

        self.assertEqual(evidence["evidence_strength"], "CATALOG_TABLE_VERIFIED")
        self.assertEqual(evidence["page"], 604)
        self.assertEqual(evidence["source"], "PDF_LAYOUT")
        self.assertEqual(evidence["normalized_configuration"], "25+25+35")
        self.assertTrue(evidence["layout_evidence"])

    def test_direct_per_combination_evidence_unlocks_exact_beretta_trial(self):
        result = self.engine.search(
            "Beretta Trial Split Breva 9+9+12 con EX18000-3", limit=30
        )
        diag = result["pairing_diagnostics"]

        self.assertEqual(result["product_identity_status"], "EXACT")
        self.assertEqual(result["configuration_status"], "VERIFIED_FULL_COMBINATION")
        self.assertEqual(
            diag["FULL_CONFIGURATION_EVIDENCE_STRENGTH"],
            "CATALOG_TABLE_VERIFIED",
        )
        self.assertTrue(result["mpn_final_allowed"])

    def test_matrix_only_daikin_combination_remains_master_derived(self):
        result = self.engine.search(
            "Daikin Dual Split Perfera 9000+9000 con 2MXM40A", limit=30
        )
        diag = result["pairing_diagnostics"]

        self.assertTrue(diag["FULL_CONFIGURATION_MATCHED"])
        self.assertEqual(
            diag["FULL_CONFIGURATION_EVIDENCE_STRENGTH"], "MASTER_DERIVED"
        )
        self.assertEqual(result["configuration_status"], "PAIRWISE_ONLY")
        self.assertFalse(result["mpn_final_allowed"])

    def test_haier_matrix_does_not_promote_generated_full_combinations(self):
        sidecar = json.loads(
            Path("Knowledge/climatizzatori_combinazioni_provenance.json").read_text(
                encoding="utf-8"
            )
        )
        combinations = sidecar["50125319"]

        self.assertEqual(
            set(combinations),
            {
                "20+20+20+20+20",
                "20+20+20+20+25",
                "20+20+20+25+25",
                "25+25+25+25+25",
            },
        )
        self.assertTrue(
            all(
                evidence["evidence_strength"] == "MASTER_DERIVED"
                for evidence in combinations.values()
            )
        )

    def test_mitsubishi_kirigamine_white_multisplit_never_selects_ruby_red_ui(self):
        result = self.engine.search(
            "Mitsubishi Climatizzatore Trial Split Kirigamine MSZ-LN Bianco "
            "12+12+18 con MXZ-3F68VF4",
            limit=30,
        )

        self.assertEqual(self._role(result, "UE")["code"], "50196142")
        self.assertEqual(
            self._role_codes(result, "UI"),
            ["99788605", "99788605", "99788636"],
        )
        self.assertNotIn("99788599", self._role_codes(result, "UI"))
        self.assertEqual(result["query_analysis"]["query_context"]["query_color"], "WHITE")
        for item in result["bom"]:
            if item.get("role") == "UI":
                self.assertEqual(item.get("color_base"), "WHITE")
                self.assertFalse(item.get("variant_conflict"))


if __name__ == "__main__":
    unittest.main()
