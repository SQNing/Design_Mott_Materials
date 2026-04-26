import sys
import json
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_pseudospin_orbital_classical_model import build_pseudospin_orbital_classical_model
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload


class BuildPseudoSpinOrbitalClassicalModelTests(unittest.TestCase):
    @staticmethod
    def _write_two_site_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "two-site triangular lattice",
                    "1.0",
                    "1.0 0.0 0.0",
                    "0.5 0.8660254037844386 0.0",
                    "0.0 0.0 8.0",
                    "Fe",
                    "2",
                    "Direct",
                    "0.0 0.0 0.0",
                    "0.3333333333333333 0.6666666666666666 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_many_body_hr(path, R_vectors=((1, 0, 0),), num_wann=4):
        rows = []
        for rx, ry, rz in R_vectors:
            for m in range(1, int(num_wann) + 1):
                for n in range(1, int(num_wann) + 1):
                    value = 1.0 if m == n else 0.0
                    rows.append(
                        f"    {rx}    {ry}    {rz}    {m}    {n}    {value:.15f}    0.000000000000000"
                    )
        path.write_text(
            "\n".join(
                [
                    "minimal wannier_hr.dat",
                    str(int(num_wann)),
                    str(len(tuple(R_vectors))),
                    " ".join(["1"] * len(tuple(R_vectors))),
                    *rows,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_pair_identity_sidecar(path, payload):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def test_build_classical_model_preserves_lowered_onsite_terms(self):
        parsed_payload = {
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "orbital_count": 2,
                "local_dimension": 4,
                "site_count_assumption": 1,
            },
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
        }

        model = build_pseudospin_orbital_classical_model(parsed_payload)

        self.assertIn("onsite_terms", model)
        self.assertEqual(model["onsite_terms"][0]["matrix_shape"], [4, 4])
        self.assertEqual(model["onsite_terms"][0]["matrix"][0][0], 1.0)

    def test_build_classical_model_maps_coefficients_to_field_terms(self):
        parsed_payload = {
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "orbital_count": 2,
                "local_dimension": 4,
                "site_count_assumption": 2,
            },
            "bond_blocks": [
                {
                    "R": [1, 0, 0],
                    "matrix_shape": [16, 16],
                    "coefficients": [
                        {
                            "left_label": "spin_X__orbital_I",
                            "right_label": "spin_X__orbital_I",
                            "coefficient": {"real": 1.0, "imag": 0.0},
                        },
                        {
                            "left_label": "spin_Z__orbital_X",
                            "right_label": "spin_I__orbital_I",
                            "coefficient": {"real": 0.2, "imag": 0.0},
                        },
                    ],
                }
            ],
        }

        model = build_pseudospin_orbital_classical_model(parsed_payload)

        self.assertEqual(model["site_fields"], ["spin", "orbital"])
        self.assertEqual(model["orbital_count"], 2)
        self.assertEqual(model["bond_count"], 1)
        self.assertEqual(len(model["terms"]), 2)

        first = model["terms"][0]
        self.assertEqual(first["R"], [1, 0, 0])
        self.assertEqual(first["body_order"], 2)
        self.assertEqual(first["factors"][0]["field"], "spin")
        self.assertEqual(first["factors"][0]["axis"], "x")
        self.assertEqual(first["factors"][1]["field"], "spin")
        self.assertEqual(first["factors"][1]["axis"], "x")

        second = model["terms"][1]
        self.assertEqual(second["body_order"], 2)
        self.assertEqual(len(second["factors"]), 2)
        self.assertEqual(second["factors"][0]["field"], "spin")
        self.assertEqual(second["factors"][0]["axis"], "z")
        self.assertEqual(second["factors"][1]["field"], "orbital")
        self.assertEqual(second["factors"][1]["axis"], "x")

    def test_build_classical_model_expands_family_representative_orbit_before_term_projection(self):
        parsed_payload = {
            "selected_local_bond_family": "J1",
            "family_representative_map": {
                "J1": {
                    "source": 0,
                    "target": 0,
                    "translation": [1, 0, 0],
                }
            },
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, 0.8660254037844386, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
                "species": ["Fe"],
                "counts": [1],
            },
            "inferred": {
                "orbital_count": 2,
                "local_dimension": 4,
                "site_count_assumption": 1,
            },
            "bond_blocks": [
                {
                    "family": "J1",
                    "R": [1, 0, 0],
                    "source": 0,
                    "target": 0,
                    "matrix_shape": [16, 16],
                    "coefficients": [
                        {
                            "left_label": "spin_X__orbital_I",
                            "right_label": "spin_X__orbital_I",
                            "coefficient": {"real": 1.0, "imag": 0.0},
                        },
                    ],
                }
            ],
            "magnetic_site_count": 1,
            "magnetic_sites": [
                {"index": 0, "label": "Fe", "position": [0.0, 0.0, 0.0]},
            ],
        }

        model = build_pseudospin_orbital_classical_model(parsed_payload)

        self.assertEqual(model["bond_count"], 3)
        self.assertEqual(len(model["terms"]), 3)
        self.assertEqual(
            {tuple(term["R"]) for term in model["terms"]},
            {
                (1, 0, 0),
                (0, 1, 0),
                (1, -1, 0),
            },
        )

    def test_build_classical_model_expands_canonical_orbit_block_before_term_projection(self):
        parsed_payload = {
            "basis_order": "orbital_major_spin_minor",
            "structure": {
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, 0.8660254037844386, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
                "species": ["Fe"],
                "counts": [1],
            },
            "inferred": {
                "orbital_count": 2,
                "local_dimension": 4,
                "site_count_assumption": 1,
            },
            "bond_blocks": [
                {
                    "orbit_id": "0:0:(0, 1, 0)",
                    "coordinate_convention": "global_crystallographic",
                    "orbit_representative": {
                        "source": 0,
                        "target": 0,
                        "translation": [0, 1, 0],
                        "coordinate_convention": "global_crystallographic",
                    },
                    "orbit_members": [
                        {"source": 0, "target": 0, "translation": [1, 0, 0]},
                        {"source": 0, "target": 0, "translation": [0, 1, 0]},
                        {"source": 0, "target": 0, "translation": [1, -1, 0]},
                    ],
                    "R": [0, 1, 0],
                    "source": 0,
                    "target": 0,
                    "matrix_shape": [16, 16],
                    "coefficients": [
                        {
                            "left_label": "spin_X__orbital_I",
                            "right_label": "spin_X__orbital_I",
                            "coefficient": {"real": 1.0, "imag": 0.0},
                        },
                    ],
                }
            ],
        }

        model = build_pseudospin_orbital_classical_model(parsed_payload)

        self.assertEqual(model["bond_count"], 3)
        self.assertEqual(len(model["terms"]), 3)
        self.assertEqual(
            {tuple(term["R"]) for term in model["terms"]},
            {
                (1, 0, 0),
                (0, 1, 0),
                (1, -1, 0),
            },
        )

    def test_build_classical_model_accepts_current_example_payload(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        parsed = build_pseudospin_orbital_payload(
            poscar_path=poscar_path,
            hr_path=hr_path,
            local_space_mode="auto",
        )
        model = build_pseudospin_orbital_classical_model(parsed)

        self.assertEqual(model["orbital_count"], 2)
        self.assertTrue(model["terms"])

    def test_build_classical_model_sidecar_explicit_source_target_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            sidecar_path = Path(tmpdir) / "pair_identity.json"
            self._write_two_site_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0),), num_wann=16)
            self._write_pair_identity_sidecar(
                sidecar_path,
                {
                    "schema_version": 1,
                    "pair_identity_provider": "sidecar",
                    "site_pair_encoding": "explicit-source-target",
                    "coordinate_convention": "global_crystallographic",
                    "hr_binding": {
                        "num_wann": 16,
                        "nrpts": 1,
                        "R_vectors": [[1, 0, 0]],
                        "comment": "minimal wannier_hr.dat",
                    },
                    "pair_records": [
                        {
                            "source": 0,
                            "target": 1,
                            "translation": [1, 0, 0],
                            "entry_refs": list(range(256)),
                        }
                    ],
                },
            )

            parsed = build_pseudospin_orbital_payload(
                poscar_path=poscar_path,
                hr_path=hr_path,
                local_space_mode="auto",
                pair_identity_sidecar_path=sidecar_path,
            )
            model = build_pseudospin_orbital_classical_model(parsed)

        self.assertEqual(parsed["canonicalization_status"], "canonicalized")
        self.assertEqual(parsed["pair_identity_status"], "available")
        self.assertEqual(parsed["magnetic_site_metadata"]["site_pair_encoding"], "explicit-source-target")
        self.assertGreater(model["bond_count"], 0)
        self.assertTrue(model["terms"])
        self.assertIn([1, 0, 0], [term["R"] for term in model["terms"]])


if __name__ == "__main__":
    unittest.main()
