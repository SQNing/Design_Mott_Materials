import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.many_body_hr_orbital_to_atom_mapping import load_many_body_hr_orbital_to_atom_mapping


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
        "level_count": 4,
        "kind": "generic_multiplet",
    }


def _valid_mapping():
    return {
        "schema_version": 1,
        "site_level_mapping": [
            {"site": 0, "level_indexes": [0, 1]},
            {"site": 1, "level_indexes": [2, 3]},
        ],
    }


class ManyBodyHrLevelToSiteMappingTests(unittest.TestCase):
    def _write_mapping(self, path, payload):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def test_load_many_body_hr_orbital_to_atom_mapping_accepts_valid_level_mapping(self):
        structure = _minimal_structure()
        with tempfile.TemporaryDirectory() as tmpdir:
            mapping_path = Path(tmpdir) / "orbital_mapping.json"
            self._write_mapping(mapping_path, _valid_mapping())

            validated = load_many_body_hr_orbital_to_atom_mapping(
                mapping_path=mapping_path,
                structure=structure,
                local_space_spec=_local_space_spec(),
            )

        self.assertEqual(validated["schema_version"], 1)
        self.assertEqual(validated["site_level_mapping"][0]["site"], 0)
        self.assertEqual(validated["level_owner_by_index"], {0: 0, 1: 0, 2: 1, 3: 1})

    def test_load_many_body_hr_orbital_to_atom_mapping_rejects_duplicate_level_ownership(self):
        structure = _minimal_structure()
        mapping = _valid_mapping()
        mapping["site_level_mapping"] = [
            {"site": 0, "level_indexes": [0, 1, 2]},
            {"site": 1, "level_indexes": [2, 3]},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            mapping_path = Path(tmpdir) / "orbital_mapping.json"
            self._write_mapping(mapping_path, mapping)

            with self.assertRaisesRegex(ValueError, "duplicate level ownership"):
                load_many_body_hr_orbital_to_atom_mapping(
                    mapping_path=mapping_path,
                    structure=structure,
                    local_space_spec=_local_space_spec(),
                )

    def test_load_many_body_hr_orbital_to_atom_mapping_rejects_missing_level_ownership(self):
        structure = _minimal_structure()
        mapping = _valid_mapping()
        mapping["site_level_mapping"] = [{"site": 0, "level_indexes": [0, 1]}]
        with tempfile.TemporaryDirectory() as tmpdir:
            mapping_path = Path(tmpdir) / "orbital_mapping.json"
            self._write_mapping(mapping_path, mapping)

            with self.assertRaisesRegex(ValueError, "missing level ownership"):
                load_many_body_hr_orbital_to_atom_mapping(
                    mapping_path=mapping_path,
                    structure=structure,
                    local_space_spec=_local_space_spec(),
                )

    def test_load_many_body_hr_orbital_to_atom_mapping_rejects_nonexistent_site_index(self):
        structure = _minimal_structure()
        mapping = _valid_mapping()
        mapping["site_level_mapping"] = [
            {"site": 0, "level_indexes": [0, 1]},
            {"site": 2, "level_indexes": [2, 3]},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            mapping_path = Path(tmpdir) / "orbital_mapping.json"
            self._write_mapping(mapping_path, mapping)

            with self.assertRaisesRegex(ValueError, "site index does not exist in structure"):
                load_many_body_hr_orbital_to_atom_mapping(
                    mapping_path=mapping_path,
                    structure=structure,
                    local_space_spec=_local_space_spec(),
                )


if __name__ == "__main__":
    unittest.main()
