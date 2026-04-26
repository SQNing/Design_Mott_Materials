#!/usr/bin/env python3
import json
from pathlib import Path


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_many_body_hr_orbital_to_atom_mapping(mapping, structure, local_space_spec):
    _require(int(mapping.get("schema_version", -1)) == 1, "mapping schema_version must be 1")
    site_basis_mapping = list(mapping.get("site_basis_mapping") or [])
    _require(site_basis_mapping, "site_basis_mapping must be non-empty")

    structure_positions = list(structure.get("positions") or [])
    site_count = len(structure_positions)
    orbital_count = int(local_space_spec.get("orbital_count", 0))
    _require(orbital_count > 0, "local_space_spec.orbital_count must be positive")

    normalized_mappings = []
    orbital_owner_by_index = {}
    duplicate_orbitals = set()
    for item in site_basis_mapping:
        site = int(item.get("site", -1))
        _require(0 <= site < site_count, "site index does not exist in structure")
        orbital_indexes = [int(value) for value in list(item.get("orbital_indexes") or [])]
        _require(orbital_indexes, "orbital_indexes must be non-empty")
        for orbital_index in orbital_indexes:
            _require(0 <= orbital_index < orbital_count, "orbital index is out of range")
            if orbital_index in orbital_owner_by_index:
                duplicate_orbitals.add(orbital_index)
            orbital_owner_by_index[orbital_index] = site
        normalized_mappings.append(
            {
                "site": site,
                "orbital_indexes": orbital_indexes,
            }
        )

    _require(not duplicate_orbitals, "duplicate orbital ownership")
    missing_orbitals = sorted(set(range(orbital_count)) - set(orbital_owner_by_index))
    _require(not missing_orbitals, f"missing orbital ownership: {missing_orbitals}")

    return {
        "schema_version": 1,
        "site_basis_mapping": normalized_mappings,
        "orbital_owner_by_index": {int(key): int(value) for key, value in orbital_owner_by_index.items()},
    }


def load_many_body_hr_orbital_to_atom_mapping(mapping_path, structure, local_space_spec):
    mapping_path = Path(mapping_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    return validate_many_body_hr_orbital_to_atom_mapping(mapping, structure, local_space_spec)
