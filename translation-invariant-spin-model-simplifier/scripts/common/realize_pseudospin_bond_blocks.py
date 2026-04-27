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


def _resolve_family_representative_map(parsed_payload):
    for container in (
        parsed_payload,
        parsed_payload.get("structure", {}),
        parsed_payload.get("lattice", {}),
    ):
        if isinstance(container, dict):
            mapping = container.get("family_representative_map")
            if isinstance(mapping, dict) and mapping:
                return mapping
    return {}


def _resolve_selected_family(parsed_payload):
    family = str(parsed_payload.get("selected_local_bond_family") or "").strip()
    return family or None


def _resolve_block_family(block, *, selected_family, single_block_mode):
    family = str(block.get("family") or "").strip()
    if family:
        return family
    if single_block_mode and selected_family:
        return selected_family
    return None


def _resolve_magnetic_basis_positions(parsed_payload):
    magnetic_sites = list(parsed_payload.get("magnetic_sites") or [])
    indexed_positions = []
    for default_index, site in enumerate(magnetic_sites):
        position = site.get("position")
        if position is None:
            continue
        indexed_positions.append((int(site.get("index", default_index)), [float(value) for value in position]))
    if indexed_positions:
        return [position for _index, position in sorted(indexed_positions, key=lambda item: item[0])]

    structure_positions = list(parsed_payload.get("structure", {}).get("positions", []))
    magnetic_site_count = int(parsed_payload.get("magnetic_site_count", 0))
    if magnetic_site_count > 0 and len(structure_positions) == magnetic_site_count:
        return [[float(value) for value in position] for position in structure_positions]
    if magnetic_site_count == 1:
        return [[0.0, 0.0, 0.0]]
    return [[float(value) for value in position] for position in structure_positions]


def _expand_canonical_orbit_blocks(source_blocks):
    expanded_blocks = []
    for block in source_blocks:
        orbit_members = list(block.get("orbit_members") or [])
        if not orbit_members:
            expanded_blocks.append(block)
            continue
        for member in orbit_members:
            expanded_block = dict(block)
            expanded_block["source"] = int(member["source"])
            expanded_block["target"] = int(member["target"])
            expanded_block["R"] = [int(value) for value in member["translation"]]
            expanded_blocks.append(expanded_block)
    return expanded_blocks


def _canonical_bond_terms_to_blocks(bond_terms):
    blocks = []
    for term in list(bond_terms or []):
        block = {
            "R": [int(value) for value in term["translation"]],
            "source": int(term["source"]),
            "target": int(term["target"]),
            "matrix_shape": list(term["matrix_shape"]),
            "pair_matrix": term["pair_matrix"],
        }
        for optional_key in ("family", "orbit", "orbit_members", "diagnostics", "provenance", "entry_refs"):
            if optional_key in term:
                block[optional_key] = term[optional_key]
        blocks.append(block)
    return blocks


def realize_pseudospin_bond_blocks(parsed_payload, bond_blocks=None):
    if bond_blocks is None:
        source_blocks = list(parsed_payload.get("bond_blocks", []))
        if not source_blocks and parsed_payload.get("model_family") == "cpn_pair_model":
            source_blocks = _canonical_bond_terms_to_blocks(parsed_payload.get("bond_terms", []))
    else:
        source_blocks = list(bond_blocks)
    if any(block.get("orbit_members") for block in source_blocks):
        return _expand_canonical_orbit_blocks(source_blocks)

    family_representative_map = _resolve_family_representative_map(parsed_payload)
    if not family_representative_map:
        return source_blocks

    selected_family = _resolve_selected_family(parsed_payload)
    single_block_mode = len(source_blocks) == 1
    family_counts = {}
    for block in source_blocks:
        family = _resolve_block_family(block, selected_family=selected_family, single_block_mode=single_block_mode)
        if family is not None:
            family_counts[family] = family_counts.get(family, 0) + 1

    structure = parsed_payload.get("structure", {})
    orbit_lattice = {
        "lattice_vectors": structure.get("lattice_vectors", []),
        "positions": _resolve_magnetic_basis_positions(parsed_payload),
        "symmetry_positions": structure.get("symmetry_positions", structure.get("positions", [])),
        "symmetry_types": structure.get("symmetry_types", _expanded_structure_types(structure)),
    }

    realized_blocks = []
    for block in source_blocks:
        family = _resolve_block_family(block, selected_family=selected_family, single_block_mode=single_block_mode)
        representative = family_representative_map.get(family) if family is not None else None
        if not isinstance(representative, dict) or family_counts.get(family, 0) != 1:
            realized_blocks.append(block)
            continue

        orbit = generate_noncull_directed_bond_orbit(orbit_lattice, representative)
        for member in orbit["members"]:
            realized_block = dict(block)
            realized_block["R"] = list(member["translation"])
            realized_block["source"] = int(member["source"])
            realized_block["target"] = int(member["target"])
            realized_block.setdefault("family", family)
            realized_blocks.append(realized_block)
    return realized_blocks
