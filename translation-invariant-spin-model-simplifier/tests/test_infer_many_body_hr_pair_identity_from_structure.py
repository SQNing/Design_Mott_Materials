import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.infer_many_body_hr_pair_identity_from_structure import infer_many_body_hr_pair_identity_from_structure


def _minimal_structure():
    return {
        "lattice_vectors": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "positions": [
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
        ],
        "species": ["Fe"],
        "counts": [2],
    }


def _local_space_spec():
    return {
        "local_dimension": 4,
        "orbital_count": 2,
        "kind": "orbital_times_spin",
        "spin_dimension": 2,
    }


def _mapping():
    return {
        "schema_version": 1,
        "site_basis_mapping": [
            {"site": 0, "orbital_indexes": [0]},
            {"site": 1, "orbital_indexes": [1]},
        ],
        "orbital_owner_by_index": {0: 0, 1: 1},
    }


def _sparse_hamiltonian():
    return {
        "comment": "synthetic sparse hr",
        "num_wann": 16,
        "nrpts": 1,
        "R_vectors": [(1, 0, 0)],
        "entries": [
            {"row_index": 0, "R": (1, 0, 0), "m": 8, "n": 8, "value": complex(1.0, 0.0)},
            {"row_index": 1, "R": (1, 0, 0), "m": 9, "n": 9, "value": complex(2.0, 0.0)},
        ],
    }


class InferManyBodyHrPairIdentityFromStructureTests(unittest.TestCase):
    def test_infer_many_body_hr_pair_identity_from_structure_emits_sidecar_shaped_object(self):
        inferred = infer_many_body_hr_pair_identity_from_structure(
            structure=_minimal_structure(),
            hamiltonian=_sparse_hamiltonian(),
            mapping=_mapping(),
            local_space_spec=_local_space_spec(),
        )

        self.assertEqual(inferred["pair_identity_provider"], "structure+orbital-mapping")
        self.assertEqual(inferred["site_pair_encoding"], "explicit-source-target")
        self.assertEqual(inferred["coordinate_convention"], "global_crystallographic")
        self.assertEqual(inferred["hr_binding"]["num_wann"], 16)
        self.assertEqual(len(inferred["pair_records"]), 1)
        record = inferred["pair_records"][0]
        self.assertEqual(record["source"], 1)
        self.assertEqual(record["target"], 0)
        self.assertEqual(record["translation"], [1, 0, 0])
        self.assertEqual(record["entry_refs"], [0, 1])

    def test_infer_many_body_hr_pair_identity_from_structure_rejects_site_mixing_within_entry(self):
        hamiltonian = {
            "comment": "synthetic ambiguous hr",
            "num_wann": 16,
            "nrpts": 1,
            "R_vectors": [(1, 0, 0)],
            "entries": [
                {"row_index": 0, "R": (1, 0, 0), "m": 10, "n": 2, "value": complex(1.0, 0.0)},
            ],
        }

        with self.assertRaisesRegex(ValueError, "cannot infer a unique site pair"):
            infer_many_body_hr_pair_identity_from_structure(
                structure=_minimal_structure(),
                hamiltonian=hamiltonian,
                mapping=_mapping(),
                local_space_spec=_local_space_spec(),
            )


if __name__ == "__main__":
    unittest.main()
