#!/usr/bin/env python3
"""Shared real-space action of structural symmetry on Hamiltonian terms."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import numpy as np

from common.canonical_hamiltonian import CanonicalHamiltonianError, canonicalize_cluster


def cartesian_rotation(lattice_vectors, fractional_rotation, *, tolerance=1.0e-8):
    """Convert a fractional-coordinate point operation to Cartesian form."""

    lattice = np.asarray(lattice_vectors, dtype=float)
    rotation = np.asarray(fractional_rotation, dtype=float)
    if lattice.shape != (3, 3) or rotation.shape != (3, 3):
        raise CanonicalHamiltonianError("invalid-space-group-operation", "expected 3-by-3 matrices")
    basis = lattice.T
    try:
        raw = basis @ rotation @ np.linalg.inv(basis)
    except np.linalg.LinAlgError as exc:
        raise CanonicalHamiltonianError("invalid-lattice-vectors", "singular lattice") from exc
    left, _singular_values, right = np.linalg.svd(raw)
    orthogonal = left @ right
    if not np.allclose(raw, orthogonal, atol=float(tolerance), rtol=float(tolerance)):
        raise CanonicalHamiltonianError(
            "invalid-space-group-operation",
            "fractional rotation is not Cartesian-orthogonal for this lattice",
        )
    return orthogonal


def axial_spin_rotation(lattice_vectors, fractional_rotation):
    """Return the axial-vector representation of a structural point operation."""

    polar = cartesian_rotation(lattice_vectors, fractional_rotation)
    determinant = float(np.linalg.det(polar))
    sign = 1.0 if determinant >= 0.0 else -1.0
    return sign * polar


def _basis_positions(lattice_structure):
    records = list(lattice_structure.get("basis_sites") or [])
    if records:
        positions = []
        for record in records:
            position = record.get("position", record.get("fractional_position"))
            if position is None:
                raise CanonicalHamiltonianError(
                    "canonical-term-identity-unresolved", "basis-site-position-required"
                )
            positions.append([float(value) for value in position])
        return np.asarray(positions, dtype=float)
    positions = lattice_structure.get("positions")
    if positions:
        return np.asarray(positions, dtype=float)
    raise CanonicalHamiltonianError("canonical-term-identity-unresolved", "basis-sites-required")


def _resolve_site_and_offset(position, basis_positions, *, tolerance=1.0e-6):
    position = np.asarray(position, dtype=float)
    for index, basis in enumerate(basis_positions):
        delta = position - basis
        offset = np.rint(delta)
        if np.allclose(delta, offset, atol=float(tolerance), rtol=0.0):
            return int(index), [int(value) for value in offset.tolist()]
    raise CanonicalHamiltonianError(
        "canonical-term-identity-unresolved",
        f"unable to map position {position.tolist()} into magnetic basis",
    )


def map_cluster(operation, cluster, lattice_structure):
    """Map every site/cell pair without canonicalizing cluster orientation."""

    rotation = np.asarray(operation.get("rotation"), dtype=float)
    translation = np.asarray(operation.get("translation", [0.0, 0.0, 0.0]), dtype=float)
    if rotation.shape != (3, 3) or translation.shape != (3,):
        raise CanonicalHamiltonianError("invalid-space-group-operation")
    basis_positions = _basis_positions(lattice_structure)
    mapped = []
    for entry in list(cluster or []):
        site = int(entry["site"])
        cell = np.asarray(entry.get("translation", [0, 0, 0]), dtype=float)
        absolute = basis_positions[site] + cell
        mapped_site, mapped_cell = _resolve_site_and_offset(
            rotation @ absolute + translation,
            basis_positions,
        )
        mapped.append({"site": mapped_site, "translation": mapped_cell})
    return mapped


def _lattice_vectors(lattice_structure):
    vectors = lattice_structure.get("lattice_vectors")
    if vectors is None:
        raise CanonicalHamiltonianError("invalid-lattice-vectors", "lattice_vectors-required")
    return np.asarray(vectors, dtype=float)


def _local_frames(lattice_structure):
    frames = {}
    for index, record in enumerate(list(lattice_structure.get("local_frames") or [])):
        site_ref = str(record.get("site_ref", f"site:{index}"))
        try:
            site = int(site_ref.split(":", 1)[-1])
        except ValueError as exc:
            raise CanonicalHamiltonianError("canonical-term-identity-unresolved", site_ref) from exc
        matrix = record.get("rotation_matrix")
        if matrix is not None:
            array = np.asarray(matrix, dtype=float)
            if array.shape != (3, 3):
                raise CanonicalHamiltonianError("invalid-local-frame", site_ref)
            frames[site] = array
    return frames


def _leg_actions(term, mapped_cluster, spin_rotation, lattice_structure):
    convention = str(term.get("coordinate_convention") or "global_crystallographic")
    if convention == "global_crystallographic":
        return [np.asarray(spin_rotation, dtype=float) for _entry in mapped_cluster]
    if convention != "local_frames":
        raise CanonicalHamiltonianError("unsupported-coordinate-convention", convention)
    frames = _local_frames(lattice_structure)
    actions = []
    for source_entry, mapped_entry in zip(term["cluster"], mapped_cluster):
        source_site = int(source_entry["site"])
        mapped_site = int(mapped_entry["site"])
        source_frame = frames.get(source_site, np.eye(3))
        mapped_frame = frames.get(mapped_site, np.eye(3))
        actions.append(np.linalg.inv(mapped_frame) @ spin_rotation @ source_frame)
    return actions


def _clean_matrix(matrix, *, tolerance=1.0e-14):
    result = []
    for row in np.asarray(matrix, dtype=complex).tolist():
        cleaned_row = []
        for value in row:
            value = complex(value)
            real = 0.0 if abs(value.real) <= tolerance else float(value.real)
            imag = 0.0 if abs(value.imag) <= tolerance else float(value.imag)
            cleaned_row.append(real if imag == 0.0 else complex(real, imag))
        result.append(cleaned_row)
    return result


def transform_term(term, operation, context):
    """Transform one onsite or bilinear physical-spin term."""

    family = str(term.get("operator_family") or "")
    if family not in {"bilinear_exchange_tensor", "bilinear_exchange_matrix"}:
        raise CanonicalHamiltonianError("symmetry-projection-unsupported-term", family)
    if int(term.get("arity", 0)) != 2:
        raise CanonicalHamiltonianError("symmetry-projection-unsupported-term", family)

    lattice_structure = context.get("lattice_structure", context) if isinstance(context, Mapping) else context
    mapped_cluster = map_cluster(operation, term.get("cluster") or [], lattice_structure)
    spin_rotation = axial_spin_rotation(
        _lattice_vectors(lattice_structure),
        operation.get("rotation"),
    )
    actions = _leg_actions(term, mapped_cluster, spin_rotation, lattice_structure)
    coefficient = np.asarray(term.get("coefficient"), dtype=complex)
    if coefficient.shape != (3, 3):
        raise CanonicalHamiltonianError("matrix-shape-mismatch", coefficient.shape)
    transformed_coefficient = actions[0] @ coefficient @ actions[1].conjugate().T

    canonical = canonicalize_cluster(mapped_cluster, family)
    if canonical["orientation_reversed"]:
        transformed_coefficient = transformed_coefficient.conjugate().T

    transformed = deepcopy(dict(term))
    transformed["cluster"] = canonical["cluster"]
    transformed["coefficient"] = _clean_matrix(transformed_coefficient)
    transformed["symmetry_action"] = {
        "operation_ref": str(operation.get("operation_ref") or ""),
        "leg_actions": [_clean_matrix(action) for action in actions],
        "permutation": list(canonical["permutation"]),
        "orientation_reversed": bool(canonical["orientation_reversed"]),
    }
    return [transformed]
