import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.operator_expression_normalizer import normalize_operator_expression
from simplify.operator_expression_parser import OperatorExpressionParseError, parse_operator_expression
from simplify.operator_expression_sparse_expand import sparse_expand_operator_expression


class OperatorExpressionParserTests(unittest.TestCase):
    def test_parse_compact_single_factor(self):
        ast = parse_operator_expression("Sz@0")

        self.assertEqual(ast.kind, "product")
        self.assertEqual(len(ast.factors), 1)
        self.assertEqual(ast.factors[0].kind, "factor")
        self.assertEqual(ast.factors[0].label, "Sz")
        self.assertEqual(ast.factors[0].site, 0)

    def test_parse_compact_three_body_product(self):
        ast = parse_operator_expression("Sp@0 Sm@1 Sz@2")

        self.assertEqual(ast.kind, "product")
        self.assertEqual([factor.label for factor in ast.factors], ["Sp", "Sm", "Sz"])
        self.assertEqual([factor.site for factor in ast.factors], [0, 1, 2])

    def test_parse_compact_sum_with_coefficients(self):
        ast = parse_operator_expression("0.5*Sz@0 Sz@1 + Jpm*Sp@0 Sm@1")

        self.assertEqual(ast.kind, "sum")
        self.assertEqual(len(ast.terms), 2)

        first, second = ast.terms
        self.assertEqual(first.kind, "scaled")
        self.assertEqual(first.coefficient.kind, "number")
        self.assertEqual(first.coefficient.value, 0.5)
        self.assertEqual(first.expression.kind, "product")
        self.assertEqual([factor.label for factor in first.expression.factors], ["Sz", "Sz"])

        self.assertEqual(second.kind, "scaled")
        self.assertEqual(second.coefficient.kind, "symbol")
        self.assertEqual(second.coefficient.name, "Jpm")
        self.assertEqual([factor.label for factor in second.expression.factors], ["Sp", "Sm"])

    def test_parse_compact_multipole_product(self):
        ast = parse_operator_expression("T2_0@0 T2_c1@1")

        self.assertEqual(ast.kind, "product")
        self.assertEqual([factor.label for factor in ast.factors], ["T2_0", "T2_c1"])
        self.assertEqual([factor.site for factor in ast.factors], [0, 1])

    def test_parse_compact_expression_rejects_unsupported_tokens(self):
        with self.assertRaises(OperatorExpressionParseError):
            parse_operator_expression("Sz@0 + [bad-token]")

    def test_latex_and_compact_bilinear_normalize_identically(self):
        left = normalize_operator_expression("S_i^z S_j^z")
        right = normalize_operator_expression("Sz@0 Sz@1")

        self.assertEqual(left, right)
        self.assertEqual(left[0]["coefficient_kind"], "number")
        self.assertEqual(left[0]["coefficient_value"], 1.0)
        self.assertEqual(left[0]["factors"], (("Sz", 0), ("Sz", 1)))

    def test_normalize_ladder_sum_into_two_monomials_before_rewrite(self):
        normalized = normalize_operator_expression("S_i^+ S_j^- + S_i^- S_j^+")

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["factors"], (("Sp", 0), ("Sm", 1)))
        self.assertEqual(normalized[1]["factors"], (("Sm", 0), ("Sp", 1)))

    def test_normalize_preserves_symbolic_coefficients(self):
        normalized = normalize_operator_expression("Jzz*Sz@0 Sz@1")

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["coefficient_kind"], "symbol")
        self.assertEqual(normalized[0]["coefficient_name"], "Jzz")
        self.assertEqual(normalized[0]["coefficient_multiplier"], 1.0)

    def test_normalize_maps_named_sites_to_support_positions(self):
        normalized = normalize_operator_expression("S_k^z S_i^z S_j^z")

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["factors"], (("Sz", 0), ("Sz", 1), ("Sz", 2)))

    def test_normalize_latex_three_body_with_symbolic_coefficient(self):
        normalized = normalize_operator_expression(r"K_{ijk} S_i^z S_j^z S_k^z")

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["coefficient_kind"], "symbol")
        self.assertEqual(normalized[0]["coefficient_name"], "K_{ijk}")
        self.assertEqual(normalized[0]["coefficient_multiplier"], 1.0)
        self.assertEqual(normalized[0]["factors"], (("Sz", 0), ("Sz", 1), ("Sz", 2)))

    def test_sparse_expand_latex_three_body_with_symbolic_coefficient(self):
        terms = sparse_expand_operator_expression(
            r"K_{ijk} S_i^z S_j^z S_k^z",
            {"K_{ijk}": 0.5},
        )

        self.assertEqual(
            terms,
            [{"label": "Sz@0 Sz@1 Sz@2", "coefficient": 0.5}],
        )

    def test_sparse_expand_compact_parenthesized_sum_times_factor(self):
        terms = sparse_expand_operator_expression(
            "(Sp@0 Sm@1 + Sm@0 Sp@1) Sz@2",
            {},
        )

        labels = {entry["label"]: entry["coefficient"] for entry in terms}
        self.assertEqual(labels["Sx@0 Sx@1 Sz@2"], 2.0)
        self.assertEqual(labels["Sy@0 Sy@1 Sz@2"], 2.0)
        self.assertNotIn("raw-operator", labels)

    def test_sparse_expand_latex_parenthesized_sum_times_factor(self):
        terms = sparse_expand_operator_expression(
            r"\left(S_i^+ S_j^- + S_i^- S_j^+\right) S_k^z",
            {},
        )

        labels = {entry["label"]: entry["coefficient"] for entry in terms}
        self.assertEqual(labels["Sx@0 Sx@1 Sz@2"], 2.0)
        self.assertEqual(labels["Sy@0 Sy@1 Sz@2"], 2.0)

    def test_sparse_expand_latex_symbolic_coefficient_times_parenthesized_sum(self):
        terms = sparse_expand_operator_expression(
            r"K_{ijk}\left(S_i^+ S_j^- + S_i^- S_j^+\right) S_k^z",
            {"K_{ijk}": 0.75},
        )

        labels = {entry["label"]: entry["coefficient"] for entry in terms}
        self.assertEqual(labels["Sx@0 Sx@1 Sz@2"], 1.5)
        self.assertEqual(labels["Sy@0 Sy@1 Sz@2"], 1.5)

    def test_sparse_expand_latex_adjacent_parenthesized_groups(self):
        terms = sparse_expand_operator_expression(
            r"\left(S_i^+ + S_i^-\right)\left(S_j^+ + S_j^-\right) S_k^z",
            {},
        )

        self.assertEqual(
            terms,
            [{"label": "Sx@0 Sx@1 Sz@2", "coefficient": 4.0}],
        )

    def test_sparse_expand_compact_grouped_sum_with_term_coefficients(self):
        terms = sparse_expand_operator_expression(
            "(J1*Sp@0 Sm@1 + J2*Sm@0 Sp@1) Sz@2",
            {"J1": 1.0, "J2": 2.0},
        )

        labels = {entry["label"]: entry["coefficient"] for entry in terms}
        self.assertEqual(labels["Sx@0 Sx@1 Sz@2"], 3.0)
        self.assertEqual(labels["Sy@0 Sy@1 Sz@2"], 3.0)
        self.assertEqual(labels["Sx@0 Sy@1 Sz@2"], 1.0j)
        self.assertEqual(labels["Sy@0 Sx@1 Sz@2"], -1.0j)

    def test_sparse_expand_latex_grouped_sum_with_symbolic_coefficient_products(self):
        terms = sparse_expand_operator_expression(
            r"\left(J_1 S_i^+ + J_2 S_i^-\right)\left(A S_j^+ + B S_j^-\right) S_k^z",
            {"J_1": 1.0, "J_2": 2.0, "A": 3.0, "B": 4.0},
        )

        labels = {entry["label"]: entry["coefficient"] for entry in terms}
        self.assertEqual(labels["Sx@0 Sx@1 Sz@2"], 21.0)
        self.assertEqual(labels["Sx@0 Sy@1 Sz@2"], -3.0j)
        self.assertEqual(labels["Sy@0 Sx@1 Sz@2"], -7.0j)
        self.assertEqual(labels["Sy@0 Sy@1 Sz@2"], -1.0)

    def test_sparse_expand_supports_imaginary_unit_coefficient(self):
        terms = sparse_expand_operator_expression(
            "-i*(Sp@0 Sm@1 - Sm@0 Sp@1)",
            {},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sy@1", "coefficient": -2.0},
                {"label": "Sy@0 Sx@1", "coefficient": 2.0},
            ],
        )

    def test_sparse_expand_supports_complex_literal_coefficient(self):
        terms = sparse_expand_operator_expression(
            "1j*(Sp@0 Sm@1 - Sm@0 Sp@1)",
            {},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sy@1", "coefficient": 2.0},
                {"label": "Sy@0 Sx@1", "coefficient": -2.0},
            ],
        )

    def test_sparse_expand_supports_hc_shorthand_for_ladder_expression(self):
        terms = sparse_expand_operator_expression(
            "J*Sp@0 Sz@1 + h.c.",
            {"J": 1.5},
        )

        self.assertEqual(
            terms,
            [{"label": "Sx@0 Sz@1", "coefficient": 3.0}],
        )

    def test_sparse_expand_supports_latex_cc_shorthand(self):
        terms = sparse_expand_operator_expression(
            r"J S_i^+ S_j^z + \mathrm{c.c.}",
            {"J": 2.0},
        )

        self.assertEqual(
            terms,
            [{"label": "Sx@0 Sz@1", "coefficient": 4.0}],
        )

    def test_sparse_expand_supports_compact_site_swap_shorthand(self):
        terms = sparse_expand_operator_expression(
            "J*Sz@0 Sz@1 + (i<->j)",
            {"J": 1.25},
        )

        self.assertEqual(
            terms,
            [{"label": "Sz@0 Sz@1", "coefficient": 2.5}],
        )

    def test_sparse_expand_supports_latex_site_swap_shorthand(self):
        terms = sparse_expand_operator_expression(
            r"J S_i^z S_j^z + (i \leftrightarrow j)",
            {"J": 1.25},
        )

        self.assertEqual(
            terms,
            [{"label": "Sz@0 Sz@1", "coefficient": 2.5}],
        )

    def test_sparse_expand_supports_perm_shorthand_for_two_site_expression(self):
        terms = sparse_expand_operator_expression(
            "J*Sz@0 Sz@1 + perm.",
            {"J": 1.25},
        )

        self.assertEqual(
            terms,
            [{"label": "Sz@0 Sz@1", "coefficient": 2.5}],
        )

    def test_sparse_expand_supports_compact_real_part_wrapper(self):
        terms = sparse_expand_operator_expression(
            "Re[J*Sp@0 Sz@1]",
            {"J": 1.0 + 2.0j},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sz@1", "coefficient": 1.0},
                {"label": "Sy@0 Sz@1", "coefficient": -2.0},
            ],
        )

    def test_sparse_expand_supports_latex_imaginary_part_wrapper(self):
        terms = sparse_expand_operator_expression(
            r"\mathrm{Im}[J S_i^+ S_j^z]",
            {"J": 1.0 + 2.0j},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sz@1", "coefficient": 2.0},
                {"label": "Sy@0 Sz@1", "coefficient": 1.0},
            ],
        )

    def test_sparse_expand_supports_cyclic_permutation_shorthand(self):
        terms = sparse_expand_operator_expression(
            "K*Sx@0 Sy@1 Sz@2 + cyclic perm.",
            {"K": 0.5},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.5},
                {"label": "Sx@1 Sy@2 Sz@0", "coefficient": 0.5},
                {"label": "Sx@2 Sy@0 Sz@1", "coefficient": 0.5},
            ],
        )

    def test_sparse_expand_supports_all_permutations_shorthand(self):
        terms = sparse_expand_operator_expression(
            "K*Sx@0 Sy@1 Sz@2 + all permutations",
            {"K": 0.5},
        )

        self.assertEqual(
            terms,
            [
                {"label": "Sx@0 Sy@1 Sz@2", "coefficient": 0.5},
                {"label": "Sx@0 Sy@2 Sz@1", "coefficient": 0.5},
                {"label": "Sx@1 Sy@0 Sz@2", "coefficient": 0.5},
                {"label": "Sx@1 Sy@2 Sz@0", "coefficient": 0.5},
                {"label": "Sx@2 Sy@0 Sz@1", "coefficient": 0.5},
                {"label": "Sx@2 Sy@1 Sz@0", "coefficient": 0.5},
            ],
        )


if __name__ == "__main__":
    unittest.main()
