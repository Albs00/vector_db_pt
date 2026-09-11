import unittest

from src.adapters.climate import ClimateCategoryAdapter
from src.core.color_variants import candidate_color_variant, normalize_color_variant


class ColorVariantNormalizationTests(unittest.TestCase):
    def test_required_aliases_normalize_to_canonical_base(self):
        aliases = {
            "WHITE": ("BIANCO", "BIANCA", "WHITE", "BCO"),
            "BLACK": ("NERO", "NERA", "BLACK", "NRO"),
            "SILVER": ("ARGENTO", "SILVER"),
            "RED": ("ROSSO", "ROSSA", "RED"),
            "GREY": ("GRIGIO", "GRIGIA", "GRAY", "GREY"),
        }
        for expected, values in aliases.items():
            for value in values:
                with self.subTest(value=value):
                    self.assertEqual(
                        normalize_color_variant(value)["color_base"], expected
                    )

    def test_named_variant_is_preserved_non_destructively(self):
        self.assertEqual(
            normalize_color_variant("Pearl White"),
            {"color_base": "WHITE", "variant_full": "PEARL WHITE"},
        )
        self.assertEqual(
            normalize_color_variant("Ruby Red"),
            {"color_base": "RED", "variant_full": "RUBY RED"},
        )
        self.assertEqual(
            normalize_color_variant("Onyx Black"),
            {"color_base": "BLACK", "variant_full": "ONYX BLACK"},
        )

    def test_explicit_variant_metadata_precedes_product_text(self):
        self.assertEqual(
            candidate_color_variant(
                {"variant": "Pearl White", "name": "Series Ruby Red"}
            ),
            {"color_base": "WHITE", "variant_full": "PEARL WHITE"},
        )

    def test_guard_blocks_only_same_series_explicit_color_conflict(self):
        candidates = [
            {"color_base": "WHITE", "variant_conflict": False,
             "family_key": "MITSUBISHI_MSZ_LN_PEARL_WHITE"},
            {"color_base": "RED", "variant_conflict": True,
             "family_key": "MITSUBISHI_MSZ_LN_RUBY_RED"},
            {"color_base": None, "variant_conflict": False,
             "family_key": "MITSUBISHI_MSZ_LN"},
            {"color_base": "RED", "variant_conflict": True,
             "family_key": "MITSUBISHI_MSZ_EF_RED"},
        ]
        ClimateCategoryAdapter.apply_color_variant_guard(
            candidates, {"requested_color": "WHITE"}
        )
        self.assertFalse(candidates[0].get("_variant_conflict_guard", False))
        self.assertTrue(candidates[1]["_variant_conflict_guard"])
        self.assertFalse(candidates[2].get("_variant_conflict_guard", False))
        self.assertFalse(candidates[3]["_variant_conflict_guard"])


if __name__ == "__main__":
    unittest.main()
