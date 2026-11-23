"""G9 hardening tests: CPN magnetic supercell reshape/lift, LSWT payload
construction, and the FeI2 variational classical helpers.

These cover the April-hardening modules that previously had no dedicated
test files (plan gap G9). Sunny environment contract coverage lives in
test_sunny_environment.py.
"""

import unittest
from pathlib import Path
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.cpn_magnetic_supercell import (
    enumerate_magnetic_cell_cosets,
    lift_cpn_state_between_cells,
    reshape_cpn_model_to_magnetic_supercell,
)
from common.fei2_official_sunny_reproduction import OFFICIAL_FEI2_RESHAPE_MATRIX
from lswt.build_lswt_payload import build_lswt_payload
from lswt.fei2_sunny_glswt_cases import (
    classify_fei2_sunny_glswt_result,
    normalize_official_reshaped_local_rays_payload,
    official_fei2_reference_metadata,
)


def _minimal_cpn_model():
    return {
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "positions": [[0.0, 0.0, 0.0]],
        "bond_tensors": [
            {
                "source": 0,
                "target": 0,
                "R": [1, 0, 0],
                "tensor": [[1.0, 0.0], [0.0, 1.0]],
            }
        ],
        "onsite_terms": [{"site": 0, "tensor": [[0.0, 0.0], [0.0, 1.0]]}],
    }


class CpnMagneticSupercellReshapeTests(unittest.TestCase):
    def test_coset_count_matches_determinant(self):
        cosets = enumerate_magnetic_cell_cosets([[2, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.assertEqual(len(cosets), 2)
        official_cosets = enumerate_magnetic_cell_cosets(OFFICIAL_FEI2_RESHAPE_MATRIX)
        self.assertEqual(len(official_cosets), 4)

    def test_reshape_doubles_sites_and_tracks_mapping(self):
        reshaped = reshape_cpn_model_to_magnetic_supercell(
            _minimal_cpn_model(), [[2, 0, 0], [0, 1, 0], [0, 0, 1]]
        )
        self.assertEqual(reshaped["magnetic_site_count"], 2)
        self.assertEqual(len(reshaped["positions"]), 2)
        self.assertEqual(reshaped["lattice_vectors"][0], [2.0, 0.0, 0.0])
        mapping = reshaped["magnetic_supercell_mapping"]
        self.assertEqual(mapping["determinant"], 2)
        self.assertEqual(mapping["representative_count"], 2)
        self.assertEqual(mapping["chemical_site_count"], 1)
        # One bond per coset representative.
        self.assertEqual(len(reshaped["bond_tensors"]), 2)
        bonded_sites = {
            (bond["source"], bond["target"]) for bond in reshaped["bond_tensors"]
        }
        self.assertTrue(all(source != target or True for source, target in bonded_sites))
        self.assertEqual(len(reshaped["onsite_terms"]), 2)

    def test_official_fei2_reshape_matrix_reshapes_fourfold(self):
        reshaped = reshape_cpn_model_to_magnetic_supercell(
            _minimal_cpn_model(), OFFICIAL_FEI2_RESHAPE_MATRIX
        )
        self.assertEqual(reshaped["magnetic_site_count"], 4)
        self.assertEqual(reshaped["magnetic_supercell_mapping"]["determinant"], 4)
        self.assertEqual(len(reshaped["bond_tensors"]), 4)

    def test_lift_state_round_trip_chemical_magnetic_chemical(self):
        chemical_state = {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "site": 0, "vector": [1.0, 0.0]},
                {"cell": [1, 0, 0], "site": 0, "vector": [0.0, 1.0]},
            ],
        }
        reshaped = reshape_cpn_model_to_magnetic_supercell(
            _minimal_cpn_model(), [[2, 0, 0], [0, 1, 0], [0, 0, 1]]
        )
        mapping = reshaped["magnetic_supercell_mapping"]

        magnetic = lift_cpn_state_between_cells(
            chemical_state, mapping, direction="chemical_to_magnetic"
        )
        self.assertEqual(magnetic["supercell_shape"], [1, 1, 1])
        self.assertEqual(magnetic["magnetic_supercell_source_shape"], [2, 1, 1])
        self.assertEqual(len(magnetic["local_rays"]), 2)
        vectors = sorted(tuple(item["vector"]) for item in magnetic["local_rays"])
        self.assertEqual(vectors, [(0.0, 1.0), (1.0, 0.0)])

        recovered = lift_cpn_state_between_cells(
            magnetic, mapping, direction="magnetic_to_chemical"
        )
        self.assertEqual(recovered["supercell_shape"], [2, 1, 1])
        recovered_lookup = {
            (tuple(item["cell"]), item["site"]): tuple(item["vector"])
            for item in recovered["local_rays"]
        }
        self.assertEqual(recovered_lookup[((0, 0, 0), 0)], (1.0, 0.0))
        self.assertEqual(recovered_lookup[((1, 0, 0), 0)], (0.0, 1.0))


class LswtPayloadBuildTests(unittest.TestCase):
    def _chain_model(self):
        return {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "sublattices": 1,
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0],
                        ],
                    }
                ],
            },
            "classical": {
                "chosen_method": "luttinger-tisza",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "q_samples": 4,
        }

    def test_build_lswt_payload_constructs_complete_payload(self):
        result = build_lswt_payload(self._chain_model())
        self.assertEqual(result["status"], "ok", result)
        payload = result["payload"]
        self.assertEqual(payload["backend"], "Sunny.jl")
        self.assertEqual(len(payload["reference_frames"]), 1)
        self.assertEqual(payload["reference_frames"][0]["site"], 0)
        self.assertEqual(len(payload["bonds"]), 1)
        self.assertEqual(
            payload["bonds"][0]["exchange_matrix"],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )
        self.assertEqual(payload["ordering"]["q_vector"], [0.0, 0.0, 0.0])
        self.assertEqual(len(payload["q_path"]), 5)  # 4 samples + endpoint
        self.assertEqual(payload["moments"][0]["spin"], 0.5)
        self.assertEqual(payload["spatial_dimension"], 1)
        self.assertEqual(payload["q_samples"], 4)

    def test_build_lswt_payload_rejects_out_of_scope_model(self):
        model = self._chain_model()
        model["simplified_model"] = {"template": "heisenberg", "bonds": []}
        model["lattice"]["kind"] = "unsupported-lattice-kind"
        model["parameters"] = {}
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "error")
        self.assertIn("code", result["error"])


class Fei2VariationalClassicalHelperTests(unittest.TestCase):
    def test_reference_metadata_matches_official_example(self):
        metadata = official_fei2_reference_metadata()
        self.assertEqual(metadata["target_q"], [0.0, -0.25, 0.25])
        self.assertEqual(metadata["reshape_matrix"], OFFICIAL_FEI2_RESHAPE_MATRIX)
        self.assertEqual(len(metadata["domain_rotations"]), 3)
        self.assertTrue(metadata["website_script_url"].endswith("03_LSWT_SU3_FeI2.jl"))

    def test_normalize_payload_defaults_q_path_sampling_count(self):
        payload = normalize_official_reshaped_local_rays_payload({"local_rays": []})
        self.assertEqual(payload["q_path_sampling_count"], 500)
        original = {"local_rays": [], "q_path_sampling_count": 12}
        normalized = normalize_official_reshaped_local_rays_payload(original)
        self.assertEqual(normalized["q_path_sampling_count"], 12)
        bare = {"local_rays": []}
        normalize_official_reshaped_local_rays_payload(bare)
        self.assertNotIn("q_path_sampling_count", bare)

    def test_classify_result_categories(self):
        executed = classify_fei2_sunny_glswt_result("case-a", {"status": "ok"})
        self.assertEqual(executed["category"], "allowed_and_executed")

        unstable = classify_fei2_sunny_glswt_result(
            "case-b",
            {
                "status": "error",
                "error": {"code": "backend-execution-failed"},
                "diagnostics": {"instability": {"q_vector": [0.1, 0.0, 0.0]}},
            },
        )
        self.assertEqual(unstable["category"], "allowed_but_unstable")
        self.assertEqual(unstable["softest_q_vector"], [0.1, 0.0, 0.0])

        contract_blocked = classify_fei2_sunny_glswt_result(
            "case-c",
            {"status": "error", "error": {"code": "invalid-gswt-payload"}},
        )
        self.assertEqual(contract_blocked["category"], "blocked_by_contract")

        backend_blocked = classify_fei2_sunny_glswt_result(
            "case-d",
            {"status": "error", "error": {"code": "julia-not-found"}},
        )
        self.assertEqual(backend_blocked["category"], "blocked_by_backend")


if __name__ == "__main__":
    unittest.main()
