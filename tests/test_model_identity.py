import unittest

from src.core.model_identity import classify_structural_model_diff


class StructuralModelIdentityTests(unittest.TestCase):
    def test_terminal_numeric_generation_is_revision_only(self):
        result = classify_structural_model_diff("MXZ-3F68VF3", "MXZ-3F68VF4")
        self.assertTrue(result["matched"])
        self.assertEqual(result["diff_type"], "REVISION_ONLY")
        self.assertEqual(result["structural_stem"], "MXZ-3F68VF")
        self.assertEqual(result["diff_details"], "3 -> 4")

    def test_capacity_and_topology_mismatches_are_not_revision_matches(self):
        capacity = classify_structural_model_diff("MXZ-3F68VF3", "MXZ-3F54VF4")
        topology = classify_structural_model_diff("MXZ-3F68VF3", "MXZ-6F120VF2")
        self.assertFalse(capacity["matched"])
        self.assertEqual(capacity["diff_type"], "CAPACITY_CLASS_MISMATCH")
        self.assertFalse(topology["matched"])
        self.assertEqual(topology["diff_type"], "TOPOLOGY_PORT_COUNT_MISMATCH")
        self.assertGreater(capacity["penalty"], 5)
        self.assertGreater(topology["penalty"], capacity["penalty"])

    def test_terminal_color_code_is_not_revision_only(self):
        result = classify_structural_model_diff("MSZ-LN35VG2V", "MSZ-LN35VG2R")
        self.assertFalse(result["matched"])
        self.assertEqual(result["diff_type"], "VARIANT_SUFFIX_MISMATCH")


if __name__ == "__main__":
    unittest.main()
