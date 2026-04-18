import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.decompose_local_term import decompose_local_term
from simplify.compile_local_term_to_matrix import compile_local_term_to_matrix
from simplify.local_matrix_record import build_local_matrix_record


class DecomposeLocalTermTests(unittest.TestCase):
    def test_decompose_operator_expression_supports_parameterized_spin_basis_labels(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Jxy * Sx@0 Sx@1 + Jxy * Sy@0 Sy@1 + Jz * Sz@0 Sz@1",
                },
            },
            "parameters": {"Jxy": -0.161, "Jz": -0.236},
        }

        decomposition = decompose_local_term(normalized)

        by_label = {term["label"]: term["coefficient"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.161)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.161)
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)

    def test_decompose_operator_expression_supports_latex_transverse_exchange_subset(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": r"""
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
""",
                },
            },
            "parameters": {"J_1^{zz}": -0.236, "J_1^{\\pm}": -0.161},
        }

        decomposition = decompose_local_term(normalized)

        by_label = {term["label"]: term["coefficient"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.161)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.161)

    def test_decompose_operator_expression_rejects_when_coefficients_cannot_be_resolved(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": r"""
J_missing^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
""",
                },
            },
            "parameters": {
                "J_1^{\\pm}": -0.236,
            },
        }

        decomposition = decompose_local_term(normalized)

        self.assertEqual(decomposition["mode"], "operator")
        self.assertEqual(decomposition["terms"][0]["label"], "raw-operator")

    def test_decompose_operator_expression_supports_cartesian_expansion_for_pm_pm_and_zpm_terms(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": r"""
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}(S_i^+S_j^+ + S_i^-S_j^-)
-
\frac{iJ_1^{z\pm}}{2}
\left[
(S_i^+-S_i^-)S_j^z
+
S_i^z(S_j^+-S_j^-)
\right]
""",
                },
            },
            "parameters": {
                "J_1^{zz}": -0.236,
                "J_1^{\\pm}": -0.236,
                "J_1^{\\pm\\pm}": -0.161,
                "J_1^{z\\pm}": -0.261,
            },
        }

        decomposition = decompose_local_term(normalized)

        by_label = {term["label"]: term["coefficient"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.397)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.075)
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(by_label["Sy@0 Sz@1"], -0.261)
        self.assertAlmostEqual(by_label["Sz@0 Sy@1"], -0.261)

    def test_decompose_supported_three_body_operator_string_without_raw_operator(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": "Sp@0 Sm@1 Sz@2",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)

        by_label = {term["label"]: term["coefficient"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertNotIn("raw-operator", by_label)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1 Sz@2"], 1.0)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1 Sz@2"], 1.0)
        self.assertAlmostEqual(by_label["Sx@0 Sy@1 Sz@2"], -1.0j)
        self.assertAlmostEqual(by_label["Sy@0 Sx@1 Sz@2"], 1.0j)

    def test_decompose_compact_multipole_product_passes_through_cleanly(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "T2_0@0 T2_c1@1",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertEqual(
            decomposition["terms"],
            [{"label": "T2_0@0 T2_c1@1", "coefficient": 1.0}],
        )

    def test_decompose_operator_family_collection_preserves_shell_metadata(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator_family_collection",
                    "value": [
                        {
                            "family": "0'",
                            "shell_index": 2,
                            "distance": 6.75214,
                            "expression": "J0 * Sx@0 Sx@1 + J0 * Sy@0 Sy@1 + K0 * Sz@0 Sz@1",
                        }
                    ],
                },
            },
            "parameters": {"J0": 0.037, "K0": -0.036},
        }

        decomposition = decompose_local_term(normalized)

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertTrue(decomposition["terms"])
        for term in decomposition["terms"]:
            self.assertEqual(term["family"], "0'")
            self.assertEqual(term["shell_index"], 2)
            self.assertAlmostEqual(term["distance"], 6.75214)

    def test_decompose_local_matrix_record_accepts_direct_matrix_backbone(self):
        record = build_local_matrix_record(
            support=[0],
            geometry_class="onsite",
            coordinate_frame="global_xyz",
            local_basis_order=["m=1", "m=0", "m=-1"],
            tensor_product_order=[0],
            matrix=[[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, -1.0]],
            provenance={"source_kind": "matrix_form"},
        )

        decomposition = decompose_local_term({"local_term_record": record})

        self.assertTrue(decomposition["terms"])
        self.assertEqual(decomposition["source_backbone"], "local_matrix_record")

    def test_decompose_spin_one_operator_text_matrix_record_prefers_multipole_matrix_path(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": "D*(Sz@0)^2",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"D": 2.165},
        }

        record = compile_local_term_to_matrix(normalized)
        decomposition = decompose_local_term({"local_term_record": record})

        labels = {term["label"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "spin-multipole-basis")
        self.assertEqual(decomposition["source_backbone"], "local_matrix_record")
        self.assertTrue(any(label.startswith("T2_") for label in labels))
        self.assertNotIn("raw-operator", labels)

    def test_decompose_spin_one_compact_two_body_operator_text_prefers_multipole_matrix_path(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Jx * Sx@0 Sx@1 + Jy * Sy@0 Sy@1 + Jz * Sz@0 Sz@1",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"Jx": 0.4, "Jy": 0.1, "Jz": -0.2},
            "selected_local_bond_family": "1",
        }

        record = compile_local_term_to_matrix(normalized)
        decomposition = decompose_local_term({"local_term_record": record})

        labels = {term["label"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "spin-multipole-basis")
        self.assertEqual(decomposition["source_backbone"], "local_matrix_record")
        self.assertTrue(any(label.startswith("T1_") for label in labels))
        self.assertNotIn("raw-operator", labels)

    def test_decompose_spin_one_latex_two_body_exchange_keeps_existing_operator_route(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": r"""
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
""",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"J_1^{zz}": -0.236, "J_1^{\\pm}": -0.161},
            "selected_local_bond_family": "1",
        }

        record = compile_local_term_to_matrix(normalized)
        decomposition = decompose_local_term({"local_term_record": record})

        labels = {term["label"] for term in decomposition["terms"]}
        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertIn("Sx@0 Sx@1", labels)
        self.assertIn("Sy@0 Sy@1", labels)
        self.assertIn("Sz@0 Sz@1", labels)

    def test_decompose_local_matrix_record_with_operator_text_provenance_avoids_raw_operator(self):
        record = build_local_matrix_record(
            support=[0, 1],
            family="1",
            geometry_class="bond",
            coordinate_frame="global_xyz",
            local_basis_order=["m=1", "m=0", "m=-1"],
            tensor_product_order=[0, 1],
            matrix=[[0.0 for _ in range(9)] for _ in range(9)],
            provenance={
                "source_kind": "operator_text",
                "source_expression": "Sp@0 Sm@1",
                "parameter_map": {},
            },
        )

        decomposition = decompose_local_term({"local_term_record": record})

        self.assertEqual(decomposition["source_backbone"], "local_matrix_record")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))


if __name__ == "__main__":
    unittest.main()
