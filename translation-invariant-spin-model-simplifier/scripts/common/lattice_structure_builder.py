#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import re

import numpy as np

from common.bond_orbits import canonicalize_directed_bond
from common.hamiltonian_symmetry_action import axial_spin_rotation
from common.lattice_geometry import resolve_lattice_vectors


def _copy_dict(value):
    return dict(value) if isinstance(value, dict) else {}


def _sanitize_label(label):
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(label or "").strip().lower()).strip("-")
    return cleaned or "unlabeled"


def bond_orbit_ref_from_source_label(label):
    return f"bond-orbit:{_sanitize_label(label)}"


def _site_orbit_ref(index):
    return f"site-orbit:{index}"


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


def _symmetry_operations(lattice):
    lattice_model = _copy_dict(lattice)
    try:
        _lattice_vectors, basis_positions, symmetry = _symmetry_dataset(lattice_model)
    except Exception:
        return [], []

    operations = []
    for index, (rotation, shift) in enumerate(zip(symmetry["rotations"], symmetry["translations"])):
        operations.append(
            {
                "operation_ref": f"symmetry-operation:{index}",
                "kind": "space_group_operation",
                "rotation": np.array(rotation, dtype=float).tolist(),
                "translation": [float(value) for value in np.array(shift, dtype=float).tolist()],
            }
        )
    return operations, list(basis_positions)


def _representative_from_legacy_maps(lattice_model, bond_label):
    representative_map = lattice_model.get("bond_orbit_representative_map")
    if not isinstance(representative_map, dict):
        return None
    metadata = representative_map.get(bond_label)
    if not isinstance(metadata, dict):
        return None
    source = metadata.get("source")
    target = metadata.get("target")
    translation = metadata.get("translation")
    if source is None or target is None or translation is None:
        return None
    return {
        "source": int(source),
        "target": int(target),
        "translation": [int(component) for component in translation],
    }


def _bond_orbit_members(lattice_model, representative, operations):
    basis_positions = np.array(lattice_model.get("positions") or [[0.0, 0.0, 0.0]], dtype=float)
    members = {}
    if not operations:
        canonical = canonicalize_directed_bond(
            representative["source"], representative["target"], representative["translation"]
        )
        members[canonical] = {
            "source": int(canonical[0]),
            "target": int(canonical[1]),
            "translation": list(canonical[2]),
            "generated_by_operation_ref": "symmetry-operation:identity",
        }
        return list(members.values())

    for operation in operations:
        transformed = _transform_directed_bond_by_symmetry(
            representative["source"],
            representative["target"],
            representative["translation"],
            operation["rotation"],
            operation["translation"],
            basis_positions,
        )
        canonical = canonicalize_directed_bond(transformed[0], transformed[1], transformed[2])
        members[canonical] = {
            "source": int(canonical[0]),
            "target": int(canonical[1]),
            "translation": list(canonical[2]),
            "generated_by_operation_ref": operation["operation_ref"],
        }
    return [
        members[key]
        for key in sorted(members, key=lambda item: (int(item[0]), int(item[1]), tuple(int(x) for x in item[2])))
    ]


def build_bond_orbit_from_representative(
    source_model,
    *,
    source_labels,
    representative,
    shell=None,
    kind="pair",
    directed=True,
    orientation_convention="source_to_target",
    selection_aliases=None,
):
    lattice_model = _copy_dict(source_model.get("lattice_model"))
    operations, _basis_positions = _symmetry_operations(lattice_model)
    orbit_ref = bond_orbit_ref_from_source_label(source_labels[0] if source_labels else representative.get("orbit_ref"))
    members = _bond_orbit_members(lattice_model, representative, operations)
    reverse_translation = [-int(component) for component in representative["translation"]]
    return {
        "orbit_ref": orbit_ref,
        "kind": kind,
        "directed": bool(directed),
        "orientation_convention": orientation_convention,
        "source_labels": list(source_labels),
        "shell": int(shell) if shell is not None else None,
        "representative": {
            "source": int(representative["source"]),
            "target": int(representative["target"]),
            "translation": [int(component) for component in representative["translation"]],
        },
        "members": members,
        "reverse_orientation": {
            "kind": "transpose_and_swap",
            "source_target_swap": True,
            "transpose": True,
            "translation": reverse_translation,
        },
        "selection_aliases": list(selection_aliases or list(source_labels)),
    }


def _bond_orbits_from_legacy_maps(source_model):
    lattice_model = _copy_dict(source_model.get("lattice_model"))
    bond_orbit_shell_map = _copy_dict(lattice_model.get("bond_orbit_shell_map"))
    bond_orbit_representative_map = _copy_dict(lattice_model.get("bond_orbit_representative_map"))
    if not bond_orbit_shell_map or not bond_orbit_representative_map:
        return []

    grouped = []
    for bond_label, shell_metadata in sorted(bond_orbit_shell_map.items()):
        representative = _representative_from_legacy_maps(lattice_model, bond_label)
        if representative is None:
            continue
        grouped.append(
            build_bond_orbit_from_representative(
                source_model,
                source_labels=[bond_label],
                representative=representative,
                shell=shell_metadata.get("shell_index"),
                selection_aliases=[bond_label],
            )
        )
    return grouped


def _extract_source_labels(source_model):
    source_labels = []
    lattice_model = _copy_dict(source_model.get("lattice_model"))
    for mapping_name in ("bond_orbit_shell_map", "bond_orbit_representative_map"):
        mapping = lattice_model.get(mapping_name)
        if isinstance(mapping, dict):
            for label in mapping:
                if str(label) not in source_labels:
                    source_labels.append(str(label))
    hamiltonian_model = _copy_dict(source_model.get("hamiltonian_model"))
    for entry in list(hamiltonian_model.get("local_bond_candidates") or []):
        bond_label = str(entry.get("bond_label") or "").strip()
        if bond_label and bond_label not in source_labels:
            source_labels.append(bond_label)
    return source_labels


def resolve_document_label_to_bond_orbit(source_label, bond_orbits):
    matches = [orbit for orbit in list(bond_orbits or []) if str(source_label) in set(map(str, orbit.get("source_labels") or []))]
    if len(matches) > 1:
        raise ValueError("ambiguous-document-label")
    if not matches:
        return None
    return matches[0]


def build_lattice_structure(source_model):
    source_model = source_model or {}
    lattice_model = _copy_dict(source_model.get("lattice_model"))
    source_labels = _extract_source_labels(source_model)
    explicit_bond_orbits = lattice_model.get("bond_orbits")
    bond_orbits = (
        deepcopy(explicit_bond_orbits)
        if isinstance(explicit_bond_orbits, list)
        else _bond_orbits_from_legacy_maps(source_model)
    )
    if not bond_orbits and lattice_model:
        representative = {
            "source": 0,
            "target": 0,
            "translation": [0, 0, 0],
        }
        bond_orbits = [
            build_bond_orbit_from_representative(
                source_model,
                source_labels=source_labels[:1] or ["unlabeled"],
                representative=representative,
                shell=1,
                selection_aliases=source_labels[:1] or ["unlabeled"],
            )
        ]
    return {
        "lattice_vectors": resolve_lattice_vectors(lattice_model),
        "basis_sites": [
            {
                "site_ref": f"site:{index}",
                "position": [float(value) for value in position],
                "source_labels": [],
            }
            for index, position in enumerate(lattice_model.get("positions") or [])
        ],
        "local_frames": [
            {
                "site_ref": f"site:{index}",
                "frame_ref": f"frame:{index}",
                "rotation_matrix": None,
                "source_labels": [],
            }
            for index, _position in enumerate(lattice_model.get("positions") or [])
        ],
        "site_orbits": [
            {
                "orbit_ref": _site_orbit_ref(index),
                "source_labels": [],
                "members": [{"site_ref": f"site:{index}"}],
            }
            for index, _position in enumerate(lattice_model.get("positions") or [])
        ],
        "bond_orbits": bond_orbits,
        "higher_body_orbits": [],
        "source_labels": source_labels,
    }


def _bond_spin_space_rotation_record(operation, source_labels, lattice_vectors):
    return {
        "operation_ref": operation["operation_ref"],
        "kind": "axial_vector_rotation",
        "matrix": axial_spin_rotation(lattice_vectors, operation.get("rotation", [])).tolist(),
        "source_labels": list(source_labels),
    }


def build_symmetry_record(source_model):
    source_model = source_model or {}
    lattice_model = _copy_dict(source_model.get("lattice_model"))
    hamiltonian_model = _copy_dict(source_model.get("hamiltonian_model"))
    source_labels = _extract_source_labels(source_model)
    lattice_vectors = resolve_lattice_vectors(lattice_model)
    operations, _basis_positions = _symmetry_operations(lattice_model)
    if not operations:
        operations = [
            {
                "operation_ref": "symmetry-operation:identity",
                "kind": "space_group_operation",
                "rotation": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "translation": [0.0, 0.0, 0.0],
            }
        ]

    spin_space_rotations = []
    local_frame_actions = []
    spin_term_refs = []
    for entry in list(hamiltonian_model.get("bond_terms") or []):
        spin_term_refs.append(str(entry.get("bond_ref") or entry.get("orbit_ref") or "bond-term"))
    if not spin_term_refs:
        for entry in list(hamiltonian_model.get("local_bond_candidates") or []):
            spin_term_refs.append(str(entry.get("bond_label") or "bond-term"))
    if not spin_term_refs:
        spin_term_refs = ["spin-term"]

    for index, operation in enumerate(operations):
        term_ref = spin_term_refs[min(index, len(spin_term_refs) - 1)]
        spin_space_rotations.append(
            _bond_spin_space_rotation_record(
                operation,
                source_labels or [term_ref],
                lattice_vectors,
            )
        )
        local_frame_actions.append(
            {
                "operation_ref": operation["operation_ref"],
                "kind": "local_frame_action",
                "action": "preserve",
                "term_ref": term_ref,
                "source_labels": list(source_labels or [term_ref]),
            }
        )

    unresolved = []
    if not lattice_model.get("positions"):
        unresolved.append(
            {
                "code": "unresolved-lattice-symmetry",
                "reason": "lattice symmetry could not be determined from the available document model",
            }
        )

    return {
        "source": {
            "source_kind": source_model.get("source_document", {}).get("source_kind"),
            "source_path": source_model.get("source_document", {}).get("source_path"),
            "source_labels": source_labels,
        },
        "operations": operations,
        "spin_space_rotations": spin_space_rotations,
        "local_frame_actions": local_frame_actions,
        "unresolved": unresolved,
    }
