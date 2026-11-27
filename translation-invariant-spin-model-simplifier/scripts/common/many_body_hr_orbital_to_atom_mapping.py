#!/usr/bin/env python3
import json
from pathlib import Path


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_many_body_hr_orbital_to_atom_mapping(mapping, structure, local_space_spec):
    _require(int(mapping.get("schema_version", -1)) == 1, "mapping schema_version must be 1")
    site_level_mapping = list(mapping.get("site_level_mapping") or [])
    _require(site_level_mapping, "site_level_mapping must be non-empty")

    structure_positions = list(structure.get("positions") or [])
    site_count = len(structure_positions)
    local_level_count = int(local_space_spec.get("local_dimension", 0))
    _require(local_level_count > 0, "local_space_spec.local_dimension must be positive")

    normalized_mappings = []
    level_owner_by_index = {}
    duplicate_levels = set()
    for item in site_level_mapping:
        site = int(item.get("site", -1))
        _require(0 <= site < site_count, "site index does not exist in structure")
        level_indexes = [int(value) for value in list(item.get("level_indexes") or [])]
        _require(level_indexes, "level_indexes must be non-empty")
        for level_index in level_indexes:
            _require(0 <= level_index < local_level_count, "level index is out of range")
            if level_index in level_owner_by_index:
                duplicate_levels.add(level_index)
            level_owner_by_index[level_index] = site
        normalized_mappings.append(
            {
                "site": site,
                "level_indexes": level_indexes,
            }
        )

    _require(not duplicate_levels, "duplicate level ownership")
    missing_levels = sorted(set(range(local_level_count)) - set(level_owner_by_index))
    _require(not missing_levels, f"missing level ownership: {missing_levels}")

    result = {
        "schema_version": 1,
        "site_level_mapping": normalized_mappings,
        "level_owner_by_index": {int(key): int(value) for key, value in level_owner_by_index.items()},
    }

    representation = mapping.get("orbital_representation")
    if representation is not None:
        from common.orbital_representation import OrbitalRepresentation

        _require(
            str(local_space_spec.get("kind") or "") == "orbital_times_spin",
            "orbital_representation requires an orbital_times_spin local space",
        )
        orbital_count = int(local_space_spec.get("orbital_count") or 0)
        _require(orbital_count > 0, "orbital_space.orbital_count must be positive")
        # Constructing the representation validates the encoding, its size and,
        # for generators, that they close into a group.
        OrbitalRepresentation(representation, orbital_count=orbital_count)
        result["orbital_representation"] = dict(representation)
    return result


def load_many_body_hr_orbital_to_atom_mapping(mapping_path, structure, local_space_spec):
    mapping_path = Path(mapping_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    return validate_many_body_hr_orbital_to_atom_mapping(mapping, structure, local_space_spec)
