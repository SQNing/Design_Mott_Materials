import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.operator_expression_parser import OperatorExpressionParseError, parse_operator_expression


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


if __name__ == "__main__":
    unittest.main()
