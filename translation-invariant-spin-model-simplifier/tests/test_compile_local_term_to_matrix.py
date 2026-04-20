import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.compile_local_term_to_matrix import (
    LocalMatrixCompilationError,
    compile_local_term_to_matrix,
)


class CompileLocalTermToMatrixTests(unittest.TestCase):
    def test_compile_direct_two_body_matrix_payload_to_local_matrix_record(self):
        matrix = [[0.0 for _ in range(9)] for _ in range(9)]
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "matrix",
                    "value": matrix,
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {},
            "selected_local_bond_family": "1",
        }

        record = compile_local_term_to_matrix(normalized)

        self.assertEqual(record["body_order"], 2)
        self.assertEqual(record["support"], [0, 1])
        self.assertEqual(record["family"], "1")
        self.assertEqual(record["representation"]["kind"], "matrix")
        self.assertEqual(record["representation"]["value"], matrix)

    def test_compile_onsite_anisotropy_operator_to_local_matrix_record(self):
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

        self.assertEqual(record["body_order"], 1)
        self.assertEqual(record["geometry_class"], "onsite")
        self.assertEqual(record["representation"]["kind"], "matrix")
        self.assertEqual(len(record["representation"]["value"]), 3)
        self.assertEqual(record["provenance"]["source_kind"], "operator_text")

    def test_compile_literature_style_spin_one_onsite_anisotropy_to_same_matrix_record(self):
        compact = {
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
        literature = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": r"D (S_i^z)^2",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"D": 2.165},
        }

        compact_record = compile_local_term_to_matrix(compact)
        literature_record = compile_local_term_to_matrix(literature)

        self.assertEqual(literature_record["body_order"], 1)
        self.assertEqual(literature_record["geometry_class"], "onsite")
        self.assertEqual(literature_record["representation"]["kind"], "matrix")
        self.assertEqual(
            literature_record["representation"]["value"],
            compact_record["representation"]["value"],
        )

    def test_compile_literature_style_spin_one_rhombic_onsite_anisotropy_to_same_matrix_record(self):
        compact = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": "E*((Sx@0)^2-(Sy@0)^2)",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"E": 0.314},
        }
        literature = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": r"E ((S_i^x)^2 - (S_i^y)^2)",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"E": 0.314},
        }

        compact_record = compile_local_term_to_matrix(compact)
        literature_record = compile_local_term_to_matrix(literature)

        self.assertEqual(literature_record["body_order"], 1)
        self.assertEqual(literature_record["geometry_class"], "onsite")
        self.assertEqual(literature_record["representation"]["kind"], "matrix")
        self.assertEqual(
            literature_record["representation"]["value"],
            compact_record["representation"]["value"],
        )

    def test_compile_literature_style_spin_two_quartic_onsite_anisotropy_to_same_matrix_record(self):
        compact = {
            "local_hilbert": {"dimension": 5},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": "B_4^0*(Sz@0)^4",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"B_4^0": 0.07},
        }
        literature = {
            "local_hilbert": {"dimension": 5},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": r"B_4^0 (S_i^z)^4",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"B_4^0": 0.07},
        }

        compact_record = compile_local_term_to_matrix(compact)
        literature_record = compile_local_term_to_matrix(literature)

        self.assertEqual(literature_record["body_order"], 1)
        self.assertEqual(literature_record["geometry_class"], "onsite")
        self.assertEqual(literature_record["representation"]["kind"], "matrix")
        self.assertEqual(
            literature_record["representation"]["value"],
            compact_record["representation"]["value"],
        )

    def test_compile_fei2_family_one_operator_text_to_bond_matrix_record(self):
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
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {
                "J_1^{zz}": -0.236,
                "J_1^{\\pm}": -0.236,
                "J_1^{\\pm\\pm}": -0.161,
                "J_1^{z\\pm}": -0.261,
            },
            "selected_local_bond_family": "1",
        }

        record = compile_local_term_to_matrix(normalized)

        self.assertEqual(record["body_order"], 2)
        self.assertEqual(record["family"], "1")
        self.assertEqual(record["geometry_class"], "bond")
        self.assertEqual(record["provenance"]["source_kind"], "operator_text")
        self.assertEqual(record["provenance"]["parameter_map"], normalized["parameters"])
        self.assertEqual(len(record["representation"]["value"]), 9)
        self.assertEqual(len(record["representation"]["value"][0]), 9)

    def test_compile_higher_body_candidate_is_rejected(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": "Sp@0 Sm@1 Sz@2",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {},
        }

        with self.assertRaises(LocalMatrixCompilationError):
            compile_local_term_to_matrix(normalized)


if __name__ == "__main__":
    unittest.main()
