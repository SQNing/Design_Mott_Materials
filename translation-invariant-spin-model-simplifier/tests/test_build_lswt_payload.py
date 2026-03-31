import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from build_lswt_payload import build_lswt_payload


class BuildLswtPayloadTests(unittest.TestCase):
    def test_build_payload_normalizes_bilinear_bonds_and_reference_frames(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "xyz",
                "bonds": [
                    {
                        "source": 0,
                        "target": 0,
                        "vector": [1, 0, 0],
                        "matrix": [[1.0, 0.1, 0.0], [0.1, 0.8, 0.0], [0.0, 0.0, 1.2]],
                    }
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
            "q_path": [[0.0, 0.0, 0.0], [3.141592653589793, 0.0, 0.0]],
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["backend"], "Sunny.jl")
        self.assertEqual(result["payload"]["bonds"][0]["exchange_matrix"][0][1], 0.1)
        self.assertEqual(result["payload"]["reference_frames"][0]["spin_length"], 0.5)
        self.assertEqual(result["payload"]["q_path"][-1][0], 3.141592653589793)

    def test_build_payload_rejects_unsupported_non_bilinear_scope(self):
        model = {
            "lattice": {"kind": "chain", "dimension": 1, "unit_cell": [0], "sublattices": 1},
            "simplified_model": {
                "template": "generic",
                "three_body_terms": [
                    {"sites": [0, 1, 2], "coefficient": 1.0, "label": "Sz@0 Sz@1 Sz@2"},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "variational", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "unsupported-model-scope")

    def test_build_payload_auto_generates_dense_rectangular_2d_high_symmetry_path(self):
        model = {
            "lattice": {
                "kind": "rectangular",
                "lattice_vectors": [[3.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
            "q_samples": 8,
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        payload = result["payload"]
        self.assertEqual(payload["spatial_dimension"], 2)
        self.assertEqual(payload["path"]["labels"], ["G", "X", "S", "Y", "G"])
        self.assertGreater(len(payload["q_path"]), 20)
        self.assertEqual(payload["path"]["node_indices"][0], 0)

    def test_build_payload_marks_models_with_out_of_plane_bonds_as_3d(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "lattice_vectors": [[3.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [0, 0, 1], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["spatial_dimension"], 3)

    def test_build_payload_treats_orthorhombic_chain_connectivity_as_1d(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["spatial_dimension"], 1)
        self.assertEqual(result["payload"]["path"]["labels"], ["G", "X"])

    def test_build_payload_derives_lattice_vectors_from_cell_parameters_when_missing(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]},
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["payload"]["lattice_vectors"][0][0], 3.0, places=9)
        self.assertAlmostEqual(result["payload"]["lattice_vectors"][1][1], 8.0, places=9)
        self.assertAlmostEqual(result["payload"]["lattice_vectors"][2][2], 8.0, places=9)

    def test_build_payload_derives_heisenberg_bonds_from_lattice_shell_parameters(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "parameters": {"J1": -1.0, "J2": 2.0},
            "simplified_model": {"template": "heisenberg"},
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        bonds = result["payload"]["bonds"]
        self.assertEqual(sorted(tuple(bond["vector"]) for bond in bonds), [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)])
        shell_labels = result["payload"]["shell_map"].keys()
        self.assertEqual(sorted(shell_labels), ["J1", "J2"])

    def test_build_payload_respects_explicit_exchange_mapping_shell_overrides(self):
        model = {
            "lattice": {
                "kind": "orthorhombic",
                "cell_parameters": {
                    "a": 3.0,
                    "b": 8.0,
                    "c": 8.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "sublattices": 1,
            },
            "parameters": {"J1": -1.0, "J2": 2.0},
            "exchange_mapping": {"mode": "distance-shells", "shell_map": {"J1": 1, "J2": 3}},
            "simplified_model": {"template": "heisenberg"},
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "provenance": {"method": "luttinger-tisza", "converged": True},
            },
        }
        result = build_lswt_payload(model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(sorted(tuple(bond["vector"]) for bond in result["payload"]["bonds"]), [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)])
        self.assertAlmostEqual(result["payload"]["shell_map"]["J2"]["distance"], 8.0, places=9)


if __name__ == "__main__":
    unittest.main()
