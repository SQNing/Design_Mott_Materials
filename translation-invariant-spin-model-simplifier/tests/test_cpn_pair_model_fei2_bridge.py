import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.build_sun_gswt_classical_payload import build_sun_gswt_classical_payload
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from common.cpn_pair_model import validate_cpn_pair_model


class CanonicalCpnPairModelFeI2BridgeTests(unittest.TestCase):
    @staticmethod
    def _write_single_site_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "single-site FeI2-like lattice",
                    "1.0",
                    "4.0 0.0 0.0",
                    "0.0 4.0 0.0",
                    "0.0 0.0 6.0",
                    "Fe",
                    "1",
                    "Direct",
                    "0.0 0.0 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_many_body_hr(path, R_vectors=((1, 0, 0),), num_wann=9):
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
                    "minimal FeI2-style wannier_hr.dat",
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
    def _serialized_diag(size, scale):
        matrix = []
        for row_index in range(size):
            row = []
            for column_index in range(size):
                value = float(scale * (row_index + 1)) if row_index == column_index else 0.0
                row.append({"real": value, "imag": 0.0})
            matrix.append(row)
        return matrix

    def test_document_derived_fei2_cp2_payload_carries_pair_and_onsite_terms(self):
        canonical_payload = {
            "schema_version": 1,
            "model_family": "cpn_pair_model",
            "classical_family": "cpn",
            "local_dimension": 3,
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "retained_state_index",
            "pair_basis_order": "site_i_major_site_j_minor",
            "retained_local_space": {
                "dimension": 3,
                "factorization": {"kind": "generic_multiplet", "multiplet_dimension": 3},
                "basis_labels": ["m_plus_1", "m_0", "m_minus_1"],
            },
            "pair_operator_convention": {
                "representation": "pair_matrix",
                "pair_basis_order": "site_i_major_site_j_minor",
                "tensor_view": {
                    "kind": "K_ab_cd",
                    "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
                },
            },
            "structure": {
                "lattice_vectors": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 6.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {
                "local_dimension": 3,
                "multiplet_dimension": 3,
                "two_site_dimension": 9,
            },
            "local_basis_labels": ["m_plus_1", "m_0", "m_minus_1"],
            "bond_terms": [
                {
                    "source": 0,
                    "target": 0,
                    "translation": [1, 0, 0],
                    "matrix_shape": [9, 9],
                    "pair_matrix": self._serialized_diag(9, 0.1),
                }
            ],
            "onsite_terms": [
                {
                    "kind": "local_operator_matrix",
                    "site_scope": {"kind": "site", "site": 0},
                    "operator_basis": {
                        "family": "retained_local_basis",
                        "labels": ["m_plus_1", "m_0", "m_minus_1"],
                    },
                    "frame": {"kind": "retained_local_basis"},
                    "payload": {
                        "matrix": [
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, 0.0],
                            [0.0, 0.0, -2.165],
                        ]
                    },
                }
            ],
        }

        validate_cpn_pair_model(canonical_payload)
        payload = build_sun_gswt_classical_payload(canonical_payload)

        self.assertEqual(payload["local_dimension"], 3)
        self.assertEqual(payload["classical_manifold"], "CP^(N-1)")
        self.assertEqual(payload["bond_tensors"][0]["tensor_shape"], [3, 3, 3, 3])
        self.assertEqual(payload["onsite_terms"][0]["matrix_shape"], [3, 3])
        self.assertEqual(payload["onsite_terms"][0]["matrix"][2][2], -2.165)

    def test_exchange_only_legacy_fei2_hr_import_normalizes_into_canonical_cp2_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            poscar_path = tmpdir / "POSCAR"
            hr_path = tmpdir / "VR_hr.dat"
            self._write_single_site_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, num_wann=9)

            payload = build_pseudospin_orbital_payload(
                poscar_path=poscar_path,
                hr_path=hr_path,
                local_space_mode="generic-multiplet",
            )

        self.assertEqual(payload["model_family"], "cpn_pair_model")
        self.assertEqual(payload["classical_family"], "cpn")
        self.assertEqual(payload["local_dimension"], 3)
        self.assertTrue(payload["bond_terms"])
        self.assertEqual(payload["bond_terms"][0]["matrix_shape"], [9, 9])
        self.assertEqual(payload["onsite_terms"], [])
