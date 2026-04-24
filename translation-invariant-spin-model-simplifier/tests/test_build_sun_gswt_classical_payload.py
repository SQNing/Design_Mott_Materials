import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_sun_gswt_classical_payload import build_sun_gswt_classical_payload


class BuildSunGswtClassicalPayloadTests(unittest.TestCase):
    @staticmethod
    def _with_cpn_family(payload):
        payload = dict(payload)
        payload["classical_family"] = "cpn"
        return payload

    def test_build_payload_requires_explicit_cpn_family(self):
        parsed_payload = {
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "bond_blocks": [],
        }

        with self.assertRaisesRegex(ValueError, "missing-classical-family"):
            build_sun_gswt_classical_payload(parsed_payload)

    def test_build_payload_rejects_spin_only_family(self):
        parsed_payload = {
            "input_mode": "many_body_hr",
            "classical_family": "spin-only",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "bond_blocks": [],
        }

        with self.assertRaisesRegex(ValueError, "incompatible-classical-family"):
            build_sun_gswt_classical_payload(parsed_payload)

    def test_build_payload_preserves_lowered_onsite_terms(self):
        parsed_payload = self._with_cpn_family({
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 4,
                "orbital_count": 2,
                "two_site_dimension": 16,
            },
            "local_basis_labels": ["state_1", "state_2", "state_3", "state_4"],
            "onsite_terms": [
                {
                    "kind": "local_operator_matrix",
                    "site_scope": {"kind": "site", "site": 0},
                    "operator_basis": {
                        "family": "retained_local_basis",
                        "labels": ["state_1", "state_2", "state_3", "state_4"],
                    },
                    "frame": {"kind": "retained_local_basis"},
                    "payload": {
                        "matrix": [
                            [1.0, 0.0, 0.0, 0.0],
                            [0.0, 0.5, 0.0, 0.0],
                            [0.0, 0.0, -0.5, 0.0],
                            [0.0, 0.0, 0.0, -1.0],
                        ]
                    },
                }
            ],
            "bond_blocks": [],
        })

        payload = build_sun_gswt_classical_payload(parsed_payload)

        self.assertIn("onsite_terms", payload)
        self.assertEqual(payload["onsite_terms"][0]["matrix_shape"], [4, 4])
        self.assertEqual(payload["onsite_terms"][0]["matrix"][0][0], 1.0)

    def test_build_payload_maps_pair_matrix_indices_into_left_right_tensor_order(self):
        zero = {"real": 0.0, "imag": 0.0}
        value = {"real": 7.0, "imag": 0.0}
        pair_matrix = [
            [zero, zero, zero, zero],
            [value, zero, zero, zero],
            [zero, zero, zero, zero],
            [zero, zero, zero, zero],
        ]
        parsed_payload = self._with_cpn_family({
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "bond_blocks": [
                {
                    "R": [1, 0, 0],
                    "matrix_shape": [4, 4],
                    "pair_matrix": pair_matrix,
                }
            ],
        })

        payload = build_sun_gswt_classical_payload(parsed_payload)
        tensor = payload["bond_tensors"][0]["tensor"]

        self.assertAlmostEqual(tensor[0][0][1][0]["real"], 7.0, places=12)
        self.assertAlmostEqual(tensor[0][1][0][0]["real"], 0.0, places=12)

    def test_build_payload_from_synthetic_pair_matrix_preserves_tensor_indices(self):
        parsed_payload = self._with_cpn_family({
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "bond_blocks": [
                {
                    "R": [1, 0, 0],
                    "matrix_shape": [4, 4],
                    "pair_matrix": [
                        [
                            {"real": 1.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 2.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 3.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 4.0, "imag": 0.0},
                        ],
                    ],
                }
            ],
        })

        payload = build_sun_gswt_classical_payload(parsed_payload)

        self.assertEqual(payload["model_version"], 2)
        self.assertEqual(payload["local_dimension"], 2)
        self.assertEqual(payload["classical_manifold"], "CP^(N-1)")
        self.assertEqual(payload["classical_variable"], "local_ray")
        self.assertEqual(payload["classical_constraints"], "normalized_ray_mod_u1")
        self.assertEqual(payload["pair_basis_order"], "site_i_major_site_j_minor")
        self.assertEqual(payload["local_basis_labels"], ["up", "down"])
        self.assertEqual(payload["backend_requirements"]["sunny_sun_classical"]["periodic_supercell_required"], True)
        self.assertEqual(
            payload["backend_requirements"]["sunny_sun_gswt"]["single_crystallographic_site_per_cell_required"],
            True,
        )
        self.assertEqual(len(payload["bond_tensors"]), 1)

        bond = payload["bond_tensors"][0]
        self.assertEqual(bond["R"], [1, 0, 0])
        self.assertEqual(bond["tensor_shape"], [2, 2, 2, 2])
        self.assertAlmostEqual(bond["tensor"][0][0][0][0]["real"], 1.0, places=12)
        self.assertAlmostEqual(bond["tensor"][0][0][1][1]["real"], 2.0, places=12)
        self.assertAlmostEqual(bond["tensor"][1][1][0][0]["real"], 3.0, places=12)
        self.assertAlmostEqual(bond["tensor"][1][1][1][1]["real"], 4.0, places=12)

    def test_build_payload_accepts_current_example_payload(self):
        from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload

        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        parsed = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)
        payload = build_sun_gswt_classical_payload(parsed)

        self.assertEqual(payload["model_version"], 2)
        self.assertEqual(payload["local_dimension"], 4)
        self.assertEqual(payload["basis_order"], "retained_state_index")
        self.assertEqual(payload["orbital_count"], 0)
        self.assertEqual(payload["classical_variable"], "local_ray")
        self.assertEqual(payload["classical_constraints"], "normalized_ray_mod_u1")
        self.assertTrue(payload["bond_tensors"])

    def test_build_payload_preserves_explicit_multisublattice_source_target_metadata(self):
        parsed_payload = self._with_cpn_family({
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "magnetic_site_count": 2,
            "magnetic_sites": [
                {"index": 0, "label": "A", "position": [0.0, 0.0, 0.0]},
                {"index": 1, "label": "B", "position": [0.5, 0.5, 0.0]},
            ],
            "magnetic_site_metadata": {
                "site_pair_encoding": "explicit-source-target",
            },
            "bond_blocks": [
                {
                    "R": [1, 0, 0],
                    "source": 1,
                    "target": 0,
                    "matrix_shape": [4, 4],
                    "pair_matrix": [
                        [
                            {"real": 1.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                        [
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0},
                        ],
                    ],
                }
            ],
        })

        payload = build_sun_gswt_classical_payload(parsed_payload)

        self.assertEqual(payload["magnetic_site_count"], 2)
        self.assertEqual(payload["magnetic_sites"][1]["label"], "B")
        self.assertEqual(payload["magnetic_site_metadata"]["site_pair_encoding"], "explicit-source-target")
        self.assertEqual(payload["bond_tensors"][0]["source"], 1)
        self.assertEqual(payload["bond_tensors"][0]["target"], 0)

    def test_build_payload_rejects_explicitly_inconsistent_basis_convention(self):
        parsed_payload = self._with_cpn_family({
            "input_mode": "many_body_hr",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "spin_major_orbital_minor",
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 2,
                "orbital_count": 1,
                "two_site_dimension": 4,
            },
            "local_basis_labels": ["up", "down"],
            "bond_blocks": [
                {
                    "R": [1, 0, 0],
                    "matrix_shape": [4, 4],
                    "pair_matrix": [
                        [{"real": 1.0, "imag": 0.0}] * 4,
                        [{"real": 0.0, "imag": 0.0}] * 4,
                        [{"real": 0.0, "imag": 0.0}] * 4,
                        [{"real": 0.0, "imag": 0.0}] * 4,
                    ],
                }
            ],
        })

        with self.assertRaises(ValueError):
            build_sun_gswt_classical_payload(parsed_payload)


if __name__ == "__main__":
    unittest.main()
