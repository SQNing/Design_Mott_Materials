import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.local_matrix_record import LocalMatrixRecordError, build_local_matrix_record


class LocalMatrixRecordTests(unittest.TestCase):
    def test_build_valid_onsite_local_matrix_record(self):
        record = build_local_matrix_record(
            support=[0],
            geometry_class="onsite",
            coordinate_frame="global_xyz",
            local_basis_order=["m=1", "m=0", "m=-1"],
            tensor_product_order=[0],
            matrix=[[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, -1.0]],
            provenance={"source_kind": "operator_text", "source_expression": "D*(Sz@0)^2"},
        )

        self.assertEqual(record["body_order"], 1)
        self.assertEqual(record["support"], [0])
        self.assertEqual(record["geometry_class"], "onsite")
        self.assertEqual(record["representation"]["kind"], "matrix")

    def test_build_valid_two_body_local_matrix_record(self):
        zero_matrix = [[0.0 for _ in range(9)] for _ in range(9)]
        record = build_local_matrix_record(
            support=[0, 1],
            family="1",
            geometry_class="bond",
            coordinate_frame="global_xyz",
            local_basis_order=["m=1", "m=0", "m=-1"],
            tensor_product_order=[0, 1],
            matrix=zero_matrix,
            provenance={"source_kind": "operator_text", "source_expression": "Jzz*Sz@0 Sz@1"},
        )

        self.assertEqual(record["body_order"], 2)
        self.assertEqual(record["family"], "1")
        self.assertEqual(record["tensor_product_order"], [0, 1])
        self.assertEqual(record["representation"]["value"], zero_matrix)

    def test_missing_required_field_is_rejected(self):
        with self.assertRaises(LocalMatrixRecordError):
            build_local_matrix_record(
                support=[0, 1],
                geometry_class="bond",
                coordinate_frame="global_xyz",
                local_basis_order=["m=1", "m=0", "m=-1"],
                tensor_product_order=[0, 1],
                matrix=[[0.0 for _ in range(9)] for _ in range(9)],
                provenance={},
            )

    def test_body_order_must_match_support_size(self):
        with self.assertRaises(LocalMatrixRecordError):
            build_local_matrix_record(
                support=[0, 1],
                body_order=1,
                family="1",
                geometry_class="bond",
                coordinate_frame="global_xyz",
                local_basis_order=["m=1", "m=0", "m=-1"],
                tensor_product_order=[0, 1],
                matrix=[[0.0 for _ in range(9)] for _ in range(9)],
                provenance={"source_kind": "matrix_form"},
            )

    def test_body_order_greater_than_two_is_rejected_in_current_phase(self):
        with self.assertRaises(LocalMatrixRecordError):
            build_local_matrix_record(
                support=[0, 1, 2],
                body_order=3,
                family="triangle_1",
                geometry_class="cluster",
                coordinate_frame="global_xyz",
                local_basis_order=["m=1", "m=0", "m=-1"],
                tensor_product_order=[0, 1, 2],
                matrix=[[0.0 for _ in range(27)] for _ in range(27)],
                provenance={"source_kind": "operator_text"},
            )


if __name__ == "__main__":
    unittest.main()
