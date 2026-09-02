#!/usr/bin/env python3
from pathlib import Path
import sys

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.lattice_geometry import resolve_lattice_vectors
else:
    from common.lattice_geometry import resolve_lattice_vectors


def _site_numbers(lattice, site_count):
    types = list(lattice.get("types") or [])
    if len(types) != int(site_count):
        return [1] * int(site_count)
    labels = {}
    numbers = []
    for label in types:
        key = str(label)
        if key not in labels:
            labels[key] = len(labels) + 1
        numbers.append(labels[key])
    return numbers


def canonicalize_directed_bond(source, target, translation):
    source = int(source)
    target = int(target)
    translation = tuple(int(component) for component in translation)
    inverse = tuple(-component for component in translation)
    for component in translation:
        if component < 0:
            return target, source, inverse
        if component > 0:
            return source, target, translation
    return min((source, target, translation), (target, source, inverse))


def _position_to_site_and_offset(position, basis_positions, *, tolerance=1.0e-6):
    position = np.array(position, dtype=float)
    for site_index, basis in enumerate(basis_positions):
        delta = position - basis
        offset = np.rint(delta)
        if np.allclose(delta, offset, atol=tolerance):
            return int(site_index), tuple(int(value) for value in offset.tolist())
    raise ValueError(f"unable to resolve transformed position {position.tolist()} against basis positions")


def _transform_directed_bond_by_symmetry(source, target, translation, rotation, shift, basis_positions):
    source_position = basis_positions[int(source)]
    target_position = basis_positions[int(target)] + np.array(translation, dtype=float)
    rotation = np.array(rotation, dtype=float)
    shift = np.array(shift, dtype=float)
    transformed_source = rotation @ source_position + shift
    transformed_target = rotation @ target_position + shift
    source_site, source_offset = _position_to_site_and_offset(transformed_source, basis_positions)
    target_site, target_offset = _position_to_site_and_offset(transformed_target, basis_positions)
    transformed_offset = tuple(int(target_offset[axis] - source_offset[axis]) for axis in range(3))
    return source_site, target_site, transformed_offset


def _symmetry_dataset(lattice):
    import spglib

    lattice_vectors = np.array(resolve_lattice_vectors(lattice), dtype=float)
    basis_positions = np.array(lattice.get("positions") or [[0.0, 0.0, 0.0]], dtype=float)
    symmetry_positions = np.array(lattice.get("symmetry_positions") or basis_positions, dtype=float)
    symmetry_types = list(lattice.get("symmetry_types") or lattice.get("types") or [])
    symmetry_lattice = dict(lattice)
    symmetry_lattice["types"] = symmetry_types
    numbers = _site_numbers(symmetry_lattice, len(symmetry_positions))
    symmetry = spglib.get_symmetry((lattice_vectors, symmetry_positions, numbers), symprec=1.0e-5)
    if not symmetry:
        raise ValueError("unable to determine lattice symmetry")
    return lattice_vectors, basis_positions, symmetry


def generate_directed_bond_orbit(lattice, representative_bond):
    source = int(representative_bond["source"])
    target = int(representative_bond["target"])
    translation = tuple(int(component) for component in representative_bond["translation"])
    lattice_vectors, basis_positions, symmetry = _symmetry_dataset(lattice)
    members = {}
    for rotation, shift in zip(symmetry["rotations"], symmetry["translations"]):
        member = _transform_directed_bond_by_symmetry(source, target, translation, rotation, shift, basis_positions)
        members[member] = {
            "source": int(member[0]),
            "target": int(member[1]),
            "translation": list(member[2]),
        }
    ordered_members = sorted(
        members.values(),
        key=lambda item: (int(item["source"]), int(item["target"]), tuple(int(x) for x in item["translation"])),
    )
    return {
        "representative": {
            "source": source,
            "target": target,
            "translation": list(translation),
        },
        "members": ordered_members,
        "orbit_size": len(ordered_members),
        "lattice_vectors": lattice_vectors.tolist(),
    }


def generate_noncull_directed_bond_orbit(lattice, representative_bond):
    orbit = generate_directed_bond_orbit(lattice, representative_bond)
    members = []
    for member in orbit["members"]:
        canonical = canonicalize_directed_bond(
            member["source"], member["target"], tuple(int(x) for x in member["translation"])
        )
        if canonical == (
            int(member["source"]),
            int(member["target"]),
            tuple(int(x) for x in member["translation"]),
        ):
            members.append(member)
    return {
        **orbit,
        "members": members,
        "orbit_size": len(members),
    }
