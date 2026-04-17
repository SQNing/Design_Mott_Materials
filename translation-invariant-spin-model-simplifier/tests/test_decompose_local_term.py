import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.decompose_local_term import decompose_local_term


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

    def test_decompose_operator_expression_rejects_partial_parse_when_unsupported_anisotropic_terms_remain(self):
        normalized = {
            "local_hilbert": {"dimension": 2},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": r"""
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right)
\nonumber\\
&-
\frac{iJ_1^{z\pm}}{2}
\left[
(\gamma_{ij}^\ast S_i^+-\gamma_{ij}S_i^-)S_j^z
+
S_i^z(\gamma_{ij}^\ast S_j^+-\gamma_{ij}S_j^-)
\right].
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


if __name__ == "__main__":
    unittest.main()
