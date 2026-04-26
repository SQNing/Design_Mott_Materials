#!/usr/bin/env python3
from common.bond_orbits import generate_noncull_directed_bond_orbit


def _expanded_structure_types(structure):
    positions = list(structure.get("positions", []))
    species = list(structure.get("species", []))
    counts = list(structure.get("counts", []))
    if not positions or not species or not counts or len(species) != len(counts):
        return []
    expanded = []
    for label, count in zip(species, counts):
        expanded.extend([str(label)] * int(count))
    if len(expanded) != len(positions):
        return []
    return expanded


def _resolve_magnetic_positions(structure, magnetic_site_payload):
    magnetic_sites = list(magnetic_site_payload.get("magnetic_sites", []))
    indexed_positions = []
    for default_index, site in enumerate(magnetic_sites):
        position = site.get("position")
        if position is None:
            continue
        indexed_positions.append((int(site.get("index", default_index)), [float(value) for value in position]))
    if indexed_positions:
        return [position for _index, position in sorted(indexed_positions, key=lambda item: item[0])]

    positions = list(structure.get("positions", []))
    if positions:
        return [[float(value) for value in position] for position in positions]
    return [[0.0, 0.0, 0.0]]


def _orbit_lattice(structure, magnetic_site_payload):
    return {
        "lattice_vectors": structure.get("lattice_vectors", []),
        "positions": _resolve_magnetic_positions(structure, magnetic_site_payload),
        "symmetry_positions": structure.get("symmetry_positions", structure.get("positions", [])),
        "symmetry_types": structure.get("symmetry_types", _expanded_structure_types(structure)),
    }


def _has_usable_lattice_vectors(structure):
    lattice_vectors = list(structure.get("lattice_vectors", []))
    if len(lattice_vectors) != 3:
        return False
    return any(abs(float(component)) > 1.0e-12 for vector in lattice_vectors for component in vector)


def canonicalize_pseudospin_bond_blocks(structure, magnetic_site_payload, raw_bond_blocks):
    if (
        len(list(structure.get("positions", []))) > 1
        and magnetic_site_payload.get("magnetic_site_metadata", {}).get("site_pair_encoding")
        == "assumed-single-sublattice-many_body_hr"
    ):
        return {
            "canonicalization_status": "unresolved",
            "bond_blocks": [],
            "raw_bond_blocks": list(raw_bond_blocks),
            "diagnostics": {
                "reason": "pair-identity-unavailable-for-multisite-direct-route",
                "unresolved_blocks": list(range(len(raw_bond_blocks))),
            },
        }

    if not _has_usable_lattice_vectors(structure):
        return {
            "canonicalization_status": "unresolved",
            "bond_blocks": [],
            "raw_bond_blocks": list(raw_bond_blocks),
            "diagnostics": {
                "reason": "missing-or-invalid-lattice-vectors-for-symmetry-canonicalization",
                "unresolved_blocks": list(range(len(raw_bond_blocks))),
            },
        }

    orbit_lattice = _orbit_lattice(structure, magnetic_site_payload)
    canonical_blocks_by_key = {}
    for block_index, raw_block in enumerate(raw_bond_blocks):
        representative = {
            "source": int(raw_block.get("source", 0)),
            "target": int(raw_block.get("target", 0)),
            "translation": [int(value) for value in raw_block.get("R", [0, 0, 0])],
        }
        try:
            orbit = generate_noncull_directed_bond_orbit(orbit_lattice, representative)
        except ValueError:
            return {
                "canonicalization_status": "unresolved",
                "bond_blocks": [],
                "raw_bond_blocks": list(raw_bond_blocks),
                "diagnostics": {
                    "reason": "unable-to-determine-lattice-symmetry-for-canonicalization",
                    "unresolved_blocks": list(range(len(raw_bond_blocks))),
                },
            }
        canonical_member = min(
            (
                int(member["source"]),
                int(member["target"]),
                tuple(int(value) for value in member["translation"]),
            )
            for member in orbit["members"]
        )
        orbit_key = canonical_member
        canonical_block = canonical_blocks_by_key.get(orbit_key)
        if canonical_block is None:
            canonical_block = dict(raw_block)
            canonical_block["source"] = int(canonical_member[0])
            canonical_block["target"] = int(canonical_member[1])
            canonical_block["R"] = list(canonical_member[2])
            canonical_block["orbit_id"] = (
                f"{canonical_member[0]}:{canonical_member[1]}:{canonical_member[2]}"
            )
            canonical_block["orbit_representative"] = {
                "source": int(canonical_member[0]),
                "target": int(canonical_member[1]),
                "translation": list(canonical_member[2]),
                "coordinate_convention": "global_crystallographic",
            }
            canonical_block["orbit_members"] = list(orbit["members"])
            canonical_block["coordinate_convention"] = "global_crystallographic"
            canonical_block["raw_block_refs"] = []
            canonical_blocks_by_key[orbit_key] = canonical_block
        canonical_block["raw_block_refs"].append(block_index)
    canonical_blocks = []
    for canonical_member in sorted(canonical_blocks_by_key):
        canonical_block = canonical_blocks_by_key[canonical_member]
        canonical_block["orbit_representative"] = {
            **canonical_block["orbit_representative"],
            "coordinate_convention": "global_crystallographic",
        }
        canonical_blocks.append(canonical_block)
    return {
        "canonicalization_status": "canonicalized",
        "bond_blocks": canonical_blocks,
        "raw_bond_blocks": list(raw_bond_blocks),
        "diagnostics": {
            "unresolved_blocks": [],
        },
    }
