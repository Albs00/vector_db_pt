#!/usr/bin/env python3
"""Standalone runtime release gate for PT26_CLIMA_PROD_2_CAPACITY_MAPPING_FIX1.

This suite validates only delivered production artifacts.  It deliberately has
no dependency on the historical offline generator, PDF tooling, or parsers.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "Knowledge"
EXPECTED = {
    "clima_monosplit_master.json": "e574156a33b9db8068175970aa789daad6de69b7db1eb6bbfd76f5f0d3429e3c",
    "clima_multisplit_master.json": "87523b02548d6dfa812a250a41ddf212ae1d7796c7f28d3a51d9c621f439790a",
    "manual_overrides_clima.json": "ce4eb075c46717276835e18219ba36c5a59879befe11bca32b97709403a9ba68",
    "clima_accessori_master.json": "134bb387c70211376d782d46debe0e90d5a91b71d7a87a746d00993866a49425",
}


def load_json(path: Path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configuration_key(scope: str, ue_pt: str, ui_pts: list[str]) -> str:
    return f"{scope}|{ue_pt}|{','.join(sorted(ui_pts))}"


class RuntimeReleaseGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mono = load_json(KNOWLEDGE / "clima_monosplit_master.json")
        cls.multi = load_json(KNOWLEDGE / "clima_multisplit_master.json")
        cls.manual = load_json(KNOWLEDGE / "manual_overrides_clima.json")
        cls.manifest = load_json(KNOWLEDGE / "clima_master_manifest.json")
        cls.documents = (cls.mono, cls.multi)
        cls.pt_union = {product["pt"] for document in cls.documents for product in document["products"]}

    def test_a_monosplit_sha256(self):
        self.assertEqual(sha256(KNOWLEDGE / "clima_monosplit_master.json"), EXPECTED["clima_monosplit_master.json"])

    def test_b_multisplit_sha256(self):
        self.assertEqual(sha256(KNOWLEDGE / "clima_multisplit_master.json"), EXPECTED["clima_multisplit_master.json"])

    def test_c_manual_overrides_sha256(self):
        self.assertEqual(sha256(KNOWLEDGE / "manual_overrides_clima.json"), EXPECTED["manual_overrides_clima.json"])

    def test_c2_accessory_master_sha256_and_schema(self):
        path = KNOWLEDGE / "clima_accessori_master.json"
        self.assertTrue(path.exists())
        self.assertEqual(sha256(path), EXPECTED["clima_accessori_master.json"])
        self.assertEqual(load_json(path)["schema_version"], "1.0.0")

    def test_d_schema_version(self):
        for document in self.documents:
            self.assertEqual(document["schema_version"], "3.0.0")

    def test_e_dataset_version(self):
        self.assertEqual(self.mono["dataset_version"], "PT26_CLIMA_PROD_2_CAPACITY_MAPPING")
        self.assertEqual(self.multi["dataset_version"], "PT26_CLIMA_PROD_2_CAPACITY_MAPPING_FIX1")

    def test_f_release_status(self):
        for document in self.documents:
            self.assertEqual(document["release_status"], "PRODUCTION_MASTER")

    def test_g_fail_closed_policy(self):
        for document in self.documents:
            self.assertEqual(document["production_policy"], "FAIL_CLOSED")

    def test_h_manifest_is_production_approved(self):
        self.assertEqual(self.manifest["release_status"], "PRODUCTION_APPROVED")
        self.assertEqual(self.manifest["dataset_version"], "PT26_CLIMA_PROD_2_CAPACITY_MAPPING_FIX1")
        self.assertTrue(self.manifest["fail_closed"])
        for key, filename in (("monosplit", "clima_monosplit_master.json"), ("multisplit", "clima_multisplit_master.json"), ("manual_overrides", "manual_overrides_clima.json")):
            self.assertEqual(self.manifest["files"][key]["sha256"], EXPECTED[filename])

    def test_i_principal_pt_union(self):
        self.assertEqual(len(self.pt_union), 2039)

    def test_j_monosplit_counts(self):
        self.assertEqual(len(self.mono["pairs"]), 1480)
        self.assertEqual(len(self.mono["combination_master"]), 1480)

    def test_k_multisplit_counts(self):
        self.assertEqual(len(self.multi["systems"]), 200)
        self.assertEqual(sum(len(system["allowed_ui"]) for system in self.multi["systems"]), 2898)
        self.assertEqual(len(self.multi["combination_master"]), 506773)

    def test_l_all_pt_are_eight_digits(self):
        pt_pattern = re.compile(r"^\d{8}$")
        for document in self.documents:
            for product in document["products"]:
                self.assertRegex(product["pt"], pt_pattern)
        for pair in self.mono["pairs"]:
            self.assertRegex(pair["ui_pt"], pt_pattern)
            self.assertRegex(pair["ue_pt"], pt_pattern)
        for combo in self.multi["combination_master"]:
            self.assertRegex(combo["ue_pt"], pt_pattern)
            for pt in combo["ui_pts"]:
                self.assertRegex(pt, pt_pattern)

    def test_m_all_product_references_are_valid(self):
        mono_products = self.mono["products"]
        for pair in self.mono["pairs"]:
            self.assertEqual(mono_products[pair["ui_product_id"]]["pt"], pair["ui_pt"])
            self.assertEqual(mono_products[pair["ue_product_id"]]["pt"], pair["ue_pt"])
        for combo in self.mono["combination_master"]:
            pair = self.mono["pairs"][combo["pair_id"]]
            self.assertEqual((combo["ui_pt"], combo["ue_pt"]), (pair["ui_pt"], pair["ue_pt"]))

        multi_products = self.multi["products"]
        ui_catalog = self.multi["ui_catalog"]
        for context in ui_catalog:
            self.assertEqual(multi_products[context["product_id"]]["pt"], context["pt"])
        for system in self.multi["systems"]:
            self.assertEqual(multi_products[system["ue_product_id"]]["pt"], system["ue_pt"])
            for edge in system["allowed_ui"]:
                self.assertEqual(ui_catalog[edge["ui_context_id"]]["pt"], edge["pt"])
        for combo in self.multi["combination_master"]:
            system = self.multi["systems"][combo["system_id"]]
            self.assertEqual(system["ue_pt"], combo["ue_pt"])

    def test_n_ui_references_have_ui_role(self):
        products = self.mono["products"]
        for pair in self.mono["pairs"]:
            self.assertEqual(products[pair["ui_product_id"]]["role"], "UI")
        products = self.multi["products"]
        for context in self.multi["ui_catalog"]:
            self.assertEqual(products[context["product_id"]]["role"], "UI")

    def test_o_ue_references_have_ue_role(self):
        products = self.mono["products"]
        for pair in self.mono["pairs"]:
            self.assertEqual(products[pair["ue_product_id"]]["role"], "UE")
        products = self.multi["products"]
        for system in self.multi["systems"]:
            self.assertEqual(products[system["ue_product_id"]]["role"], "UE")

    def test_p_no_cross_scope_reference(self):
        products = self.mono["products"]
        for pair in self.mono["pairs"]:
            self.assertEqual(pair["scope"], "MONOSPLIT")
            self.assertEqual(products[pair["ui_product_id"]]["scope"], pair["scope"])
            self.assertEqual(products[pair["ue_product_id"]]["scope"], pair["scope"])
        products = self.multi["products"]
        for system in self.multi["systems"]:
            self.assertEqual(products[system["ue_product_id"]]["scope"], system["scope"])
            for edge in system["allowed_ui"]:
                context = self.multi["ui_catalog"][edge["ui_context_id"]]
                self.assertEqual(context["scope"], system["scope"])
                self.assertEqual(products[context["product_id"]]["scope"], system["scope"])
        for combo in self.multi["combination_master"]:
            self.assertEqual(combo["scope"], self.multi["systems"][combo["system_id"]]["scope"])

    def test_q_multisplit_combinations_are_confirmed(self):
        self.assertEqual({combo["status"] for combo in self.multi["combination_master"]}, {"CONFIRMED"})

    def test_r_pairwise_systems_never_authorize_full_configuration(self):
        forbidden = {"PAIRWISE_ONLY", "NOT_CONFIRMED"}
        for combo in self.multi["combination_master"]:
            self.assertNotIn(self.multi["systems"][combo["system_id"]]["evidence"], forbidden)

    def test_s_configuration_keys_are_reconstructible(self):
        for combo in self.mono["combination_master"]:
            self.assertEqual(combo["configuration_key"], f"MONOSPLIT|{combo['ui_pt']}|{combo['ue_pt']}")
        for combo in self.multi["combination_master"]:
            self.assertEqual(combo["configuration_key"], configuration_key(combo["scope"], combo["ue_pt"], combo["ui_pts"]))

    def test_t_ui_count_matches_multiset_length(self):
        for combo in self.multi["combination_master"]:
            self.assertEqual(combo["ui_count"], len(combo["ui_pts"]))

    def test_u_duplicate_ui_instances_are_preserved(self):
        duplicates = [combo for combo in self.multi["combination_master"] if len(set(combo["ui_pts"])) < len(combo["ui_pts"])]
        self.assertTrue(duplicates)
        target = self.multi["combination_master"][self.multi["index_by_configuration_key"]["MULTISPLIT|50196142|99788605,99788605,99788636"]]
        self.assertEqual(target["ui_pts"], ["99788605", "99788605", "99788636"])

    def test_v_no_quantity_shorthand(self):
        shorthand = re.compile(r"(?:^|[^A-Z0-9])X[2-9](?:$|[^A-Z0-9])", re.IGNORECASE)
        for combo in self.multi["combination_master"]:
            self.assertFalse(shorthand.search(combo["configuration_key"]))
            for pt in combo["ui_pts"]:
                self.assertFalse(shorthand.search(pt))

    def test_w_configuration_indices_are_coherent(self):
        mono_expected = defaultdict(list)
        for index, combo in enumerate(self.mono["combination_master"]):
            mono_expected[combo["configuration_key"]].append(index)
        self.assertEqual(dict(mono_expected), self.mono["index_by_configuration_key"])
        multi_expected = {combo["configuration_key"]: index for index, combo in enumerate(self.multi["combination_master"])}
        self.assertEqual(multi_expected, self.multi["index_by_configuration_key"])

    def test_x_unresolved_cases_are_non_authorizing(self):
        unresolved_ids = {
            case["id"]
            for document in self.documents
            for case in document["unresolved_cases"]
            if case.get("status") != "CONFIRMED"
        }
        self.assertTrue(unresolved_ids)
        for document in self.documents:
            for case in document["unresolved_cases"]:
                if case.get("status") != "CONFIRMED":
                    self.assertIn("BLOCK", case.get("authorization_policy", "").upper())
        for combo in self.multi["combination_master"]:
            source_id = str((combo.get("source") or {}).get("override_id") or "")
            self.assertNotIn(source_id, unresolved_ids)
            self.assertNotIn(str(combo.get("rule_id") or ""), unresolved_ids)

    def test_y_manual_overrides_are_loadable_and_referentially_valid(self):
        overrides = self.manual["overrides"]
        self.assertEqual(len(overrides), 8)
        self.assertEqual(self.manual["policy"], "EXISTING_V3_MANUAL_ASSERTIONS_ONLY_NO_NEW_AUTHORIZATION")
        self.assertEqual(self.manual["index_by_id"], {row["id"]: index for index, row in enumerate(overrides)})
        role_by_pt = defaultdict(set)
        for document in self.documents:
            for product in document["products"]:
                role_by_pt[product["pt"]].add(product["role"])
        for override in overrides:
            self.assertEqual(override["status"], "CONFIRMED")
            for pt in override["pts"]:
                self.assertIn(pt, self.pt_union)
            assertion = override.get("assertion") or {}
            if assertion.get("pt"):
                asserted_pts = assertion["pt"] if isinstance(assertion["pt"], list) else [assertion["pt"]]
                self.assertTrue(set(asserted_pts) <= set(override["pts"]))
                if assertion.get("role"):
                    for pt in asserted_pts:
                        self.assertIn(assertion["role"], role_by_pt[pt])


if __name__ == "__main__":
    unittest.main(verbosity=2)
