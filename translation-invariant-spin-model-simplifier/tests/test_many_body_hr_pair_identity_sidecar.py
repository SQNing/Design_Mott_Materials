import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.parse_many_body_hr import parse_many_body_hr_text
from common.many_body_hr_pair_identity_sidecar import load_many_body_hr_pair_identity_sidecar


def _minimal_hr_text():
    return """minimal wannier_hr.dat
  2
  1
1
0 0 0 1 1 1.000000000000000 0.000000000000000
0 0 0 1 2 0.000000000000000 0.000000000000000
0 0 0 2 1 0.000000000000000 0.000000000000000
0 0 0 2 2 1.000000000000000 0.000000000000000
"""


def _valid_sidecar_dict():
    return {
        "schema_version": 1,
        "pair_identity_provider": "sidecar",
        "site_pair_encoding": "explicit-source-target",
        "coordinate_convention": "global_crystallographic",
        "hr_binding": {
            "num_wann": 2,
            "nrpts": 1,
            "R_vectors": [[0, 0, 0]],
            "comment": "minimal wannier_hr.dat",
        },
        "pair_records": [
            {
                "source": 0,
                "target": 1,
                "translation": [0, 0, 0],
                "entry_refs": [0, 1, 2, 3],
            }
        ],
    }


class ManyBodyHrPairIdentitySidecarTests(unittest.TestCase):
    def _write_sidecar(self, path, payload):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def test_load_many_body_hr_pair_identity_sidecar_accepts_valid_sidecar(self):
        hamiltonian = parse_many_body_hr_text(_minimal_hr_text())
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "pair_identity.json"
            self._write_sidecar(sidecar_path, _valid_sidecar_dict())

            validated = load_many_body_hr_pair_identity_sidecar(sidecar_path=sidecar_path, hamiltonian=hamiltonian)

        self.assertEqual(validated["pair_identity_provider"], "sidecar")
        self.assertEqual(validated["site_pair_encoding"], "explicit-source-target")
        self.assertEqual(validated["coordinate_convention"], "global_crystallographic")
        self.assertEqual(len(validated["pair_records"]), 1)
        self.assertEqual(validated["pair_records"][0]["entry_refs"], [0, 1, 2, 3])

    def test_load_many_body_hr_pair_identity_sidecar_rejects_missing_entry_coverage(self):
        hamiltonian = parse_many_body_hr_text(_minimal_hr_text())
        sidecar = _valid_sidecar_dict()
        sidecar["pair_records"][0]["entry_refs"] = [0, 1, 2]
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "pair_identity.json"
            self._write_sidecar(sidecar_path, sidecar)

            with self.assertRaisesRegex(ValueError, "missing sidecar coverage"):
                load_many_body_hr_pair_identity_sidecar(sidecar_path=sidecar_path, hamiltonian=hamiltonian)

    def test_load_many_body_hr_pair_identity_sidecar_rejects_duplicate_entry_ownership(self):
        hamiltonian = parse_many_body_hr_text(_minimal_hr_text())
        sidecar = _valid_sidecar_dict()
        sidecar["pair_records"] = [
            {
                "source": 0,
                "target": 1,
                "translation": [0, 0, 0],
                "entry_refs": [0, 1],
            },
            {
                "source": 1,
                "target": 0,
                "translation": [0, 0, 0],
                "entry_refs": [1, 2, 3],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "pair_identity.json"
            self._write_sidecar(sidecar_path, sidecar)

            with self.assertRaisesRegex(ValueError, "duplicate sidecar entry_ref ownership"):
                load_many_body_hr_pair_identity_sidecar(sidecar_path=sidecar_path, hamiltonian=hamiltonian)

    def test_load_many_body_hr_pair_identity_sidecar_rejects_translation_mismatch(self):
        hamiltonian = parse_many_body_hr_text(_minimal_hr_text())
        sidecar = _valid_sidecar_dict()
        sidecar["pair_records"][0]["translation"] = [1, 0, 0]
        with tempfile.TemporaryDirectory() as tmpdir:
            sidecar_path = Path(tmpdir) / "pair_identity.json"
            self._write_sidecar(sidecar_path, sidecar)

            with self.assertRaisesRegex(ValueError, "translation does not match parser R"):
                load_many_body_hr_pair_identity_sidecar(sidecar_path=sidecar_path, hamiltonian=hamiltonian)


if __name__ == "__main__":
    unittest.main()
