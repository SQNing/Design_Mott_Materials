#!/usr/bin/env python3
"""Normalize a CPN pair model into the ``lattice-term-contract/v1`` shape.

The first half of this module builds the contract itself: sites, orbits, term
attachments and the solver request. The second half decides which structural
symmetry the payload may claim, which is the part that needs a cell, a magnetic
basis and a local representation. ``_resolved_symmetry_contract`` is the entry
point for that decision, and ``reference/cpn-pair-model-schema.md`` documents the
resulting modes.
"""

from copy import deepcopy

from common.canonical_hamiltonian import CanonicalHamiltonianError


def _require_dict(payload):
    if not isinstance(payload, dict):
        raise ValueError("cpn-pair-model-payload-must-be-dict")


def _matrix_shape(matrix):
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    return [rows, cols]


def _validate_serialized_matrix(matrix, *, expected_shape, error_code):
    if not isinstance(matrix, list):
        raise ValueError(error_code)
    actual_shape = _matrix_shape(matrix)
    if actual_shape != list(expected_shape):
        raise ValueError(error_code)


def _structured_complex(value):
    if isinstance(value, dict) and value.get("kind") == "complex":
        return dict(value)
    if isinstance(value, dict):
        return {
            "kind": "complex",
            "re": float(value.get("real", value.get("re", 0.0))),
            "im": float(value.get("imag", value.get("im", 0.0))),
        }
    if isinstance(value, complex):
        return {"kind": "complex", "re": float(value.real), "im": float(value.imag)}
    return {"kind": "complex", "re": float(value), "im": 0.0}


def _structured_pair_matrix(matrix):
    rows = list(matrix or [])
    return {
        "storage": "dense",
        "shape": [len(rows), len(rows[0]) if rows else 0],
        "scalar_type": "complex_parameter_expression",
        "data": [[_structured_complex(value) for value in row] for row in rows],
    }


def _identity_symmetry_operation():
    """Declare the trivial space-group operation every lattice admits.

    The identity is the floor of every CPN contract: it is always sound, and it
    is the only operation left when the declared cell or the declared terms do
    not certify anything stronger. Representative bond orbits still need a
    declared operator action for every operation.
    """
    return {
        "operation_ref": "symmetry-operation:identity",
        "kind": "identity",
        "rotation": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "translation": [0.0, 0.0, 0.0],
    }


def _identity_matrix_unit_action(dimension):
    """Identity action on the vectorized local matrix-unit space.

    ``op_basis:retained_local_matrix`` stores ``dimension ** 2`` matrix units,
    so a declared leg action is a ``dimension ** 2`` square matrix.
    """
    size = int(dimension) * int(dimension)
    return [
        [1.0 if row == column else 0.0 for column in range(size)]
        for row in range(size)
    ]


_SPACE_GROUP_TOLERANCE = 1.0e-5
_BOND_MATRIX_TOLERANCE = 1.0e-10
_ROTATION_TOLERANCE = 1.0e-8


def _identity_rotation():
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _local_representation_kind(payload):
    """Return how the retained local space transforms, or ``None``.

    ``scalar`` means a single retained state, where every structural operation
    can only multiply the state by a phase. ``pseudospin_multiplet`` means the
    retained space is one irreducible multiplet, so an operation acts through
    the axial rotation of that multiplet expressed in the standard ``|S, m>``
    basis. ``orbital_representation`` means the payload declares how the
    orbitals themselves transform, either by real-orbital character or by
    generator matrices. ``None`` means the payload does not determine the
    representation, and no operation beyond the identity may be asserted.

    A ``generic_multiplet`` payload only labels its states ``state_1 .. state_d``,
    so reading it as a multiplet is an assumption. It is never trusted on its
    own: every operation built from it is re-checked against the declared pair
    matrices, and an operation whose matrices disagree is dropped.
    """
    if int(payload.get("local_dimension", 0)) == 1:
        return "scalar"
    space = payload.get("retained_local_space")
    if not isinstance(space, dict):
        return None
    factorization = space.get("factorization")
    if not isinstance(factorization, dict):
        return None
    kind = str(factorization.get("kind") or "")
    if kind == "generic_multiplet":
        return "pseudospin_multiplet"
    if kind != "orbital_times_spin":
        return None
    if isinstance(space.get("orbital_representation"), dict):
        return "orbital_representation"
    if int(factorization.get("orbital_count") or 0) == 1:
        return "pseudospin_multiplet"
    return None


def _axis_angle(rotation):
    """Return the axis and angle of a proper Cartesian rotation."""
    import numpy

    matrix = numpy.asarray(rotation, dtype=float)
    cosine = max(-1.0, min(1.0, (float(numpy.trace(matrix)) - 1.0) / 2.0))
    angle = float(numpy.arccos(cosine))
    if angle <= _ROTATION_TOLERANCE:
        return numpy.zeros(3), 0.0
    values, vectors = numpy.linalg.eig(matrix)
    axis = numpy.real(vectors[:, int(numpy.argmin(numpy.abs(values - 1.0)))])
    norm = float(numpy.linalg.norm(axis))
    if norm <= _ROTATION_TOLERANCE:
        return numpy.zeros(3), 0.0
    return axis / norm, angle


def _multiplet_rotation(axis, angle, dimension):
    """Return the ``dimension``-dimensional rotation of one multiplet."""
    import numpy

    size = int(dimension)
    if size <= 1 or abs(float(angle)) <= _ROTATION_TOLERANCE:
        return numpy.eye(size, dtype=complex)
    spin = (size - 1) / 2.0
    sz = numpy.diag([spin - index for index in range(size)]).astype(complex)
    raising = numpy.zeros((size, size), dtype=complex)
    for index in range(size - 1):
        moment = spin - index
        raising[index, index + 1] = numpy.sqrt(spin * (spin + 1.0) - moment * (moment - 1.0))
    sx = 0.5 * (raising + raising.conj().T)
    sy = -0.5j * (raising - raising.conj().T)
    generator = axis[0] * sx + axis[1] * sy + axis[2] * sz
    values, vectors = numpy.linalg.eigh(generator)
    phases = numpy.exp(-1.0j * float(angle) * values)
    return (vectors * phases) @ vectors.conj().T


def _matrix_unit_action(representation):
    """Vectorize the action of a local basis rotation on matrix units.

    A matrix unit maps as ``|a><c| -> U |a><c| U^dagger``, whose row-major
    vectorization is ``kron(U, conj(U))``. A global phase of ``U`` therefore
    cancels, which is what makes the axis sign of a half turn irrelevant.
    """
    import numpy

    matrix = numpy.asarray(representation, dtype=complex)
    return numpy.kron(matrix, matrix.conjugate()).tolist()


def _json_safe_matrix(matrix):
    """Encode a matrix so a payload stays serializable without a custom hook.

    Real entries stay plain floats; entries with an imaginary part use the
    ``{"real", "imag"}`` form that pair matrices already use in this contract.
    """
    rows = []
    for row in matrix:
        values = []
        for value in row:
            number = complex(value)
            if number.imag == 0.0:
                values.append(float(number.real))
            else:
                values.append(
                    {"real": float(number.real), "imag": float(number.imag)}
                )
        rows.append(values)
    return rows


def _orbital_actions(payload, operations):
    """Return one matrix-unit action per operation from the orbital record.

    The local action is ``kron(D_orbital, S_spin)`` in the declared
    ``orbital_major_spin_minor`` order. The orbital factor comes from the
    payload's ``orbital_representation``; a malformed record raises rather than
    silently degrading, because a broken declaration is a producer bug, not a
    model without symmetry.
    """
    import numpy

    from common.hamiltonian_symmetry_action import (
        axial_spin_rotation,
        cartesian_rotation,
    )
    from common.orbital_representation import OrbitalRepresentation

    space = payload.get("retained_local_space")
    factorization = space.get("factorization") if isinstance(space, dict) else None
    if not isinstance(factorization, dict):
        return None
    orbital_count = int(factorization.get("orbital_count") or 0)
    spin_dimension = int(factorization.get("spin_dimension") or 2)
    lattice_vectors = _structure_field(payload, "lattice_vectors")
    if orbital_count <= 0 or not isinstance(lattice_vectors, list) or len(lattice_vectors) != 3:
        return None
    if orbital_count * spin_dimension != int(payload.get("local_dimension", 0)):
        raise ValueError("cpn-pair-model-orbital-space-dimension-mismatch")
    representation = OrbitalRepresentation(
        space.get("orbital_representation"), orbital_count=orbital_count
    )
    actions = []
    for operation in operations:
        try:
            cartesian = cartesian_rotation(lattice_vectors, operation["rotation"])
            axial = axial_spin_rotation(lattice_vectors, operation["rotation"])
        except (CanonicalHamiltonianError, TypeError, ValueError):
            return None
        orbital = representation.action(operation["rotation"], cartesian)
        if orbital is None:
            # The declared generators do not cover this operation; it is
            # simply not a candidate. The rest of the group is still usable.
            actions.append(None)
            continue
        axis, angle = _axis_angle(axial)
        spin = _multiplet_rotation(axis, angle, spin_dimension)
        actions.append(_matrix_unit_action(numpy.kron(orbital, spin)))
    return actions


def _local_actions_for(payload, operations):
    """Return one matrix-unit action per operation, or ``None``.

    ``None`` means the retained local space does not determine a
    representation, so the caller must fall back to the identity alone.
    """
    kind = _local_representation_kind(payload)
    if kind is None:
        return None
    dimension = int(payload.get("local_dimension", 0))
    lattice_vectors = _structure_field(payload, "lattice_vectors")
    if kind == "scalar" or dimension <= 1:
        return [[[1.0]] for _operation in operations]
    if not isinstance(lattice_vectors, list) or len(lattice_vectors) != 3:
        return None
    if kind == "orbital_representation":
        return _orbital_actions(payload, operations)
    from common.hamiltonian_symmetry_action import axial_spin_rotation

    actions = []
    for operation in operations:
        try:
            axial = axial_spin_rotation(lattice_vectors, operation["rotation"])
        except (CanonicalHamiltonianError, TypeError, ValueError):
            return None
        axis, angle = _axis_angle(axial)
        actions.append(_matrix_unit_action(_multiplet_rotation(axis, angle, dimension)))
    return actions


def _is_identity_operation(operation):
    rotation = operation.get("rotation")
    translation = operation.get("translation")
    if not isinstance(rotation, list) or len(rotation) != 3:
        return False
    if not isinstance(translation, list) or len(translation) != 3:
        return False
    for row in range(3):
        if not isinstance(rotation[row], list) or len(rotation[row]) != 3:
            return False
        for column in range(3):
            expected = 1.0 if row == column else 0.0
            if abs(float(rotation[row][column]) - expected) > _SPACE_GROUP_TOLERANCE:
                return False
    return all(abs(float(value)) <= _SPACE_GROUP_TOLERANCE for value in translation)


def _declared_symmetry(payload):
    """Return the producer's symmetry declaration, or ``None``.

    A declaration that only repeats the identity carries no information: every
    lattice admits it, and ``normalize_cpn_pair_model`` always appends it. Such
    a declaration is treated as absent so that re-normalizing an already
    normalized payload can still derive the space group from the cell. A
    declaration with any further operation is authoritative and preserved.
    """
    symmetry = payload.get("symmetry")
    if not isinstance(symmetry, dict):
        return None
    operations = symmetry.get("operations")
    if not isinstance(operations, list) or not operations:
        return None
    normalized = []
    for operation in operations:
        if not isinstance(operation, dict):
            return None
        rotation = operation.get("rotation")
        translation = operation.get("translation") or [0.0, 0.0, 0.0]
        if not isinstance(rotation, list) or len(rotation) != 3:
            return None
        if any(not isinstance(row, list) or len(row) != 3 for row in rotation):
            return None
        if not isinstance(translation, list) or len(translation) != 3:
            return None
        normalized.append(
            {
                "operation_ref": str(operation.get("operation_ref") or ""),
                "kind": str(operation.get("kind") or "space_group"),
                "rotation": [[float(value) for value in row] for row in rotation],
                "translation": [float(value) for value in translation],
            }
        )
    if any(not operation["operation_ref"] for operation in normalized):
        return None
    if len(normalized) == 1 and _is_identity_operation(normalized[0]):
        return None
    return {
        "operations": normalized,
        "spin_space_rotations": deepcopy(symmetry.get("spin_space_rotations") or []),
        "local_frame_actions": deepcopy(symmetry.get("local_frame_actions") or []),
    }


def _declared_symmetry_actions(payload, basis_ref):
    local_hilbert = payload.get("local_hilbert")
    if not isinstance(local_hilbert, dict):
        return None
    bases = local_hilbert.get("operator_bases")
    if not isinstance(bases, dict):
        return None
    record = bases.get(basis_ref)
    if not isinstance(record, dict):
        return None
    actions = record.get("symmetry_actions")
    if not isinstance(actions, dict) or not actions:
        return None
    normalized = {}
    for operation_ref, action in actions.items():
        if not isinstance(action, dict) or "matrix" not in action:
            return None
        matrix = action.get("matrix")
        if not isinstance(matrix, list) or not matrix:
            return None
        if any(not isinstance(row, list) or len(row) != len(matrix) for row in matrix):
            return None
        # The matrices are kept in the encoding the producer used, so a payload
        # stays serializable and a re-normalization is a fixed point.
        normalized[str(operation_ref)] = {"matrix": deepcopy(matrix)}
    return normalized


def _structure_site_numbers(payload):
    """Return one integer species label per crystallographic position.

    POSCAR-style payloads list positions in species blocks, so ``species`` plus
    ``counts`` reconstructs the per-site labels that spglib needs. Without them
    every site counts as one species, which can only over-generate the group and
    is filtered again by the term-invariance check.
    """
    positions = _structure_positions(payload)
    structure = payload.get("structure")
    if not isinstance(structure, dict):
        return [1] * len(positions)
    species = structure.get("species")
    counts = structure.get("counts")
    if not isinstance(species, list) or not isinstance(counts, list):
        return [1] * len(positions)
    if len(species) != len(counts) or not species:
        return [1] * len(positions)
    numbers = []
    for index, count in enumerate(counts):
        numbers.extend([index + 1] * int(count))
    if len(numbers) != len(positions):
        return [1] * len(positions)
    return numbers


def _space_group_operations(payload):
    """Derive the crystal space group from the declared cell, or return [].

    The cell uses every crystallographic position with its species label, so
    the result is the symmetry of the crystal rather than of the magnetic
    sublattice alone. Operations are returned in a deterministic order with the
    identity first; admissibility is decided afterwards by the term check.
    """
    lattice_vectors = _structure_field(payload, "lattice_vectors")
    positions = _structure_positions(payload)
    if not lattice_vectors or not positions:
        return []
    try:
        import numpy
        import spglib
    except ImportError:
        return []
    cell = (
        numpy.asarray(lattice_vectors, dtype=float),
        numpy.asarray(positions, dtype=float),
        numpy.asarray(_structure_site_numbers(payload), dtype=int),
    )
    try:
        symmetry = spglib.get_symmetry(cell, symprec=_SPACE_GROUP_TOLERANCE)
    except (TypeError, ValueError, RuntimeError):
        return []
    if not symmetry:
        return []
    candidates = []
    seen = set()
    for rotation, translation in zip(symmetry["rotations"], symmetry["translations"]):
        key = (
            tuple(int(value) for row in rotation for value in row),
            tuple(round(float(value) % 1.0, 9) for value in translation),
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "rotation": [[float(value) for value in row] for row in rotation],
                "translation": [float(value) for value in translation],
            }
        )
    identity_index = None
    for index, candidate in enumerate(candidates):
        if candidate["rotation"] == _identity_rotation() and all(
            abs(value) <= _SPACE_GROUP_TOLERANCE
            for value in candidate["translation"]
        ):
            identity_index = index
            break
    operations = []
    if identity_index is not None:
        identity = candidates.pop(identity_index)
        operations.append(
            {
                "operation_ref": "symmetry-operation:identity",
                "kind": "identity",
                "rotation": identity["rotation"],
                "translation": [0.0, 0.0, 0.0],
            }
        )
    for index, candidate in enumerate(candidates, start=1):
        operations.append(
            {
                "operation_ref": f"symmetry-operation:space-group:{index}",
                "kind": "space_group",
                "rotation": candidate["rotation"],
                "translation": candidate["translation"],
            }
        )
    return operations


def _fractional_image(position, rotation, translation):
    return [
        sum(rotation[row][column] * position[column] for column in range(3))
        + translation[row]
        for row in range(3)
    ]


def _resolve_basis_position(position, basis_positions, tolerance=1.0e-6):
    for index, basis in enumerate(basis_positions):
        offset = [
            int(round(position[axis] - basis[axis])) for axis in range(3)
        ]
        if all(
            abs(position[axis] - basis[axis] - offset[axis]) <= tolerance
            for axis in range(3)
        ):
            return index, offset
    return None


def _map_bond_member(member, operation, basis_positions):
    source, target, translation = member
    rotation = operation["rotation"]
    shift = operation["translation"]
    source_position = _fractional_image(
        basis_positions[source], rotation, shift
    )
    target_position = _fractional_image(
        [
            basis_positions[target][axis] + translation[axis]
            for axis in range(3)
        ],
        rotation,
        shift,
    )
    resolved_source = _resolve_basis_position(source_position, basis_positions)
    resolved_target = _resolve_basis_position(target_position, basis_positions)
    if resolved_source is None or resolved_target is None:
        return None
    mapped_source, source_offset = resolved_source
    mapped_target, target_offset = resolved_target
    return (
        mapped_source,
        mapped_target,
        tuple(
            target_offset[axis] - source_offset[axis] for axis in range(3)
        ),
    )


def _bond_term_index(payload):
    """Index the declared bond terms by their directed bond identity."""
    index = {}
    for term in list(payload.get("bond_terms") or []):
        if not isinstance(term, dict):
            return {}
        key = (
            int(term.get("source", 0)),
            int(term.get("target", 0)),
            tuple(int(value) for value in list(term.get("translation") or [0, 0, 0])),
        )
        index.setdefault(key, []).append(term)
    return index


def _matrices_match(left, right, tolerance=_BOND_MATRIX_TOLERANCE):
    if not isinstance(left, list) or not isinstance(right, list):
        return False
    if len(left) != len(right):
        return False
    for left_row, right_row in zip(left, right):
        if not isinstance(left_row, list) or not isinstance(right_row, list):
            return False
        if len(left_row) != len(right_row):
            return False
        for left_value, right_value in zip(left_row, right_row):
            left_complex = _structured_complex(left_value)
            right_complex = _structured_complex(right_value)
            scale = max(
                1.0,
                abs(left_complex["re"]),
                abs(left_complex["im"]),
                abs(right_complex["re"]),
                abs(right_complex["im"]),
            )
            if abs(left_complex["re"] - right_complex["re"]) > tolerance * scale:
                return False
            if abs(left_complex["im"] - right_complex["im"]) > tolerance * scale:
                return False
    return True


def _numeric_matrix(matrix):
    """Return a dense complex array from any accepted pair-matrix encoding."""
    import numpy

    rows = []
    for row in list(matrix or []):
        values = []
        for value in list(row or []):
            record = _structured_complex(value)
            values.append(complex(record["re"], record["im"]))
        rows.append(values)
    try:
        return numpy.asarray(rows, dtype=complex)
    except ValueError:
        return numpy.asarray([], dtype=complex)


def _apply_local_action(matrix, action):
    """Contract one matrix-unit action onto both legs of a pair matrix.

    The stored pair matrix is indexed ``(left_bra, right_bra, left_ket,
    right_ket)`` while a matrix-unit action acts on the ``(bra, ket)`` pair of
    one site, so the two middle axes are exchanged before and after the
    contraction. This mirrors ``transform_operator_coefficient`` exactly.
    """
    import numpy
    from math import isqrt

    array = _numeric_matrix(matrix)
    operator = numpy.asarray(action, dtype=complex)
    if array.ndim != 2 or array.shape[0] != array.shape[1]:
        return None
    if operator.shape != array.shape:
        return None
    dimension = isqrt(int(array.shape[0]))
    if dimension * dimension != array.shape[0]:
        return None
    tensor = array.reshape([dimension] * 4).transpose(0, 2, 1, 3).reshape(array.shape)
    tensor = operator @ tensor @ operator.T
    return (
        tensor.reshape([dimension] * 4).transpose(0, 2, 1, 3).reshape(array.shape).tolist()
    )


def _transformed_bond_matrix(matrix, action):
    """Return the pair matrix an operation produces on its image bond.

    The declared pair matrix is already expressed for the directed bond, with
    the source factor on the left. A structural operation maps that directed
    bond onto another one and carries the factors with it, so the matrix is
    transformed by the local action alone: no factor exchange is applied here.
    Exchanging factors is a bookkeeping step of the canonical compiler, and
    applying it on both the incoming and the outgoing bond would cancel the
    orientation twice and silently accept matrices that are not invariant.
    """
    return _apply_local_action(matrix, action)


def _operation_preserves_terms(operation, action, term_index, basis_positions):
    """Return whether the declared terms are invariant under one operation.

    The operation is admissible only when it permutes the declared bonds onto
    each other and every pair matrix is carried onto its partner's matrix by
    the declared local action. Rejecting an operation here keeps the
    declaration inside the verified subgroup, so the strict gate downstream can
    only confirm what was already checked.
    """
    images = set()
    for bond, terms in term_index.items():
        image = _map_bond_member(bond, operation, basis_positions)
        if image is None or image in images:
            return False
        images.add(image)
        partners = term_index.get(image)
        if not partners:
            return False
        for term in terms:
            transformed = _transformed_bond_matrix(term.get("pair_matrix"), action)
            if not any(
                _matrices_match(transformed, partner.get("pair_matrix"))
                for partner in partners
            ):
                return False
    return True


def _structure_field(payload, name):
    structure = payload.get("structure")
    if not isinstance(structure, dict):
        return None
    return structure.get(name)


def _structure_positions(payload):
    positions = _structure_field(payload, "positions")
    if not isinstance(positions, list):
        return []
    normalized = []
    for position in positions:
        if not isinstance(position, list) or len(position) != 3:
            return []
        normalized.append([float(value) for value in position])
    return normalized


def _magnetic_sites(payload):
    sites = payload.get("magnetic_sites")
    if not isinstance(sites, list) or not sites:
        return []
    return [site for site in sites if isinstance(site, dict)]


def _magnetic_positions(payload):
    """Return one fractional position per magnetic site, or an empty list.

    ``structure.positions`` describes the crystallographic cell, which is only
    the magnetic basis when the payload declares no richer site map. Magnetic
    sites win when they carry positions; a single-sublattice payload (every
    magnetic site position is null and the counts agree) falls back to the
    crystallographic positions; anything else stays unresolved rather than
    guessing a basis.
    """
    sites = _magnetic_sites(payload)
    if sites:
        declared = [site.get("position") for site in sites]
        if all(isinstance(position, list) and len(position) == 3 for position in declared):
            return [[float(value) for value in position] for position in declared]
        structure_positions = _structure_positions(payload)
        if len(structure_positions) == len(sites):
            return structure_positions
        return []
    structure_positions = _structure_positions(payload)
    count = _declared_magnetic_site_count(payload)
    if count is None or count == len(structure_positions):
        return structure_positions
    return []


def _declared_magnetic_site_count(payload):
    declared = payload.get("magnetic_site_count")
    if isinstance(declared, int) and declared > 0:
        return declared
    return None


def _magnetic_site_count(payload):
    sites = _magnetic_sites(payload)
    if sites:
        return len(sites)
    declared = _declared_magnetic_site_count(payload)
    if declared is not None:
        return declared
    positions = _structure_positions(payload)
    if positions:
        return len(positions)
    return 2


def _retained_local_hilbert(payload, symmetry_actions=None):
    local_dimension = int(payload.get("local_dimension", 0))
    basis_labels = list(payload.get("local_basis_labels") or [f"state:{index}" for index in range(local_dimension)])
    basis_semantics = dict(payload.get("basis_semantics") or {})
    site_count = _magnetic_site_count(payload)
    actions = dict(symmetry_actions or {})
    actions.setdefault(
        "symmetry-operation:identity",
        {"matrix": _identity_matrix_unit_action(local_dimension)},
    )
    return {
        "sites": [
            {
                "site_ref": f"site:{index}",
                "space_ref": "space:retained_local",
                "basis_ref": "basis:retained_local",
                "classical_space_ref": "classical_space:cpn_local_ray",
                "operator_basis_refs": ["op_basis:retained_local_matrix"],
            }
            for index in range(site_count)
        ],
        "basis_registry": {
            "basis:retained_local": {
                "kind": "retained_local_basis",
                "dimension": local_dimension,
                "basis_order": basis_labels,
                "basis_semantics": basis_semantics,
            }
        },
        "operator_bases": {
            "op_basis:retained_local_matrix": {
                "kind": "dense_local_matrix_units",
                "dimension": local_dimension,
                "symmetry_actions": actions,
            }
        },
        "classical_spaces": {
            "classical_space:cpn_local_ray": {
                "kind": "complex_projective_space",
                "dimension": local_dimension,
            }
        },
    }


def _orbit_ref_for_bond_term(index):
    return f"bond_orbit:retained_pair_{index}"


def _lattice_structure_from_bond_terms(bond_terms, payload):
    positions = _magnetic_positions(payload)
    bond_orbits = []
    for index, term in enumerate(list(bond_terms or [])):
        translation = [int(value) for value in list(term.get("translation") or [0, 0, 0])]
        source = int(term.get("source", 0))
        target = int(term.get("target", 0))
        representative = {
            "source": source,
            "target": target,
            "translation": translation,
        }
        bond_orbits.append(
            {
                "orbit_ref": _orbit_ref_for_bond_term(index),
                "kind": "pair",
                "directed": True,
                "representative": representative,
                "members": [deepcopy(representative)],
                "source_labels": [str(term.get("orbit", _orbit_ref_for_bond_term(index)))],
                "reverse_orientation": {
                    "kind": "swap_tensor_factors_then_adjoint",
                    "source_target_swap": True,
                    "translation": [-component for component in translation],
                },
            }
        )
    if positions:
        basis_sites = [
            {"site_ref": f"site:{index}", "position": position}
            for index, position in enumerate(positions)
        ]
    else:
        basis_sites = [
            {"site_ref": f"site:{index}"}
            for index in range(_magnetic_site_count(payload))
        ]
    structure = {
        "basis_sites": basis_sites,
        "bond_orbits": bond_orbits,
        "higher_body_orbits": [],
    }
    lattice_vectors = _structure_field(payload, "lattice_vectors")
    if isinstance(lattice_vectors, list) and len(lattice_vectors) == 3:
        structure["lattice_vectors"] = [
            [float(value) for value in vector] for vector in lattice_vectors
        ]
    return structure


def _term_attachments_from_bond_terms(payload):
    local_basis_refs = ["basis:retained_local", "basis:retained_local"]
    bond_terms = []
    candidate_terms = []
    for index, term in enumerate(list(payload.get("bond_terms") or [])):
        term_ref = f"term:retained_pair_{index}"
        orbit_ref = _orbit_ref_for_bond_term(index)
        attachment = {
            "term_ref": term_ref,
            "support_ref": [f"site:{int(term.get('source', 0))}", f"site:{int(term.get('target', 0))}"],
            "attach_to": {"kind": "bond_orbit", "orbit_ref": orbit_ref, "orientation": "representative"},
            "operator_basis_ref": "op_basis:retained_local_matrix",
            "channel_kind": "two_body",
            "operator_channel": "pair_matrix",
            "readable_block_kind": "pair_matrix",
            "payload": {
                "kind": "pair_matrix",
                "local_basis_refs": list(local_basis_refs),
                "tensor_product_order": {
                    "kind": "left_major_right_minor",
                    "left_site_role": "source",
                    "right_site_role": "target",
                },
                "pair_identity": {
                    "status": "verified",
                    "provider": str(payload.get("pair_identity_provider") or "many_body_hr_pair_identity_sidecar"),
                    "basis_order_status": "matched",
                },
                "matrix": _structured_pair_matrix(term.get("pair_matrix")),
                "orientation_transform": "swap_tensor_factors_then_adjoint",
            },
            "provenance": {"entry_refs": list(term.get("entry_refs") or [])},
        }
        bond_terms.append(attachment)
        candidate_terms.append(deepcopy(attachment))
    term_refs = [term["term_ref"] for term in bond_terms]
    orbit_refs = [term["attach_to"]["orbit_ref"] for term in bond_terms]
    return {
        "site_terms": [],
        "bond_terms": bond_terms,
        "higher_body_terms": [],
        "candidate_terms": candidate_terms,
        "term_sets": [
            {
                "term_set_ref": "term_set:all_retained_local_pair_matrices",
                "selection_mode": "all_compatible",
                "term_refs": term_refs,
                "bond_orbit_refs": orbit_refs,
            }
        ]
        if bond_terms
        else [],
    }


def _derived_symmetry(payload):
    """Return verified operations with their local actions, or ``[]``.

    The crystal group is only a candidate set: a CPN payload may describe a
    magnetic order, an anisotropic exchange model, or a bond subset that breaks
    part of it. Every candidate is therefore verified against the declared bond
    terms, with the local action its retained space implies, and the identity is
    the floor.
    """
    candidates = _space_group_operations(payload)
    if len(candidates) <= 1:
        return []
    actions = _local_actions_for(payload, candidates)
    if actions is None:
        return []
    positions = _magnetic_positions(payload)
    term_index = _bond_term_index(payload)
    if not positions or not term_index:
        return []
    verified = [
        (operation, action)
        for operation, action in zip(candidates, actions)
        if action is not None
        and _operation_preserves_terms(operation, action, term_index, positions)
    ]
    if len(verified) <= 1:
        return []
    return verified


def _resolved_symmetry_contract(payload):
    """Resolve the symmetry declaration and its local operator actions.

    A producer that knows the retained-space representation may declare
    ``symmetry.operations`` together with ``operator_bases[...].symmetry_actions``;
    that declaration is authoritative and is preserved. Otherwise the identity
    is always available, and the space group of the declared cell is derived and
    verified against the declared terms, with the matrix-unit action that the
    retained local space implies.
    """
    local_dimension = int(payload.get("local_dimension", 0))
    declared = _declared_symmetry(payload)
    if declared is not None:
        actions = _declared_symmetry_actions(
            payload, "op_basis:retained_local_matrix"
        ) or {}
        missing = [
            operation["operation_ref"]
            for operation in declared["operations"]
            if operation["operation_ref"] not in actions
            and operation["operation_ref"] != "symmetry-operation:identity"
        ]
        if missing:
            raise ValueError(
                "cpn-pair-model-symmetry-action-missing:"
                + ",".join(sorted(missing))
            )
        return declared, actions, {
            "mode": "declared",
            "operation_count": len(declared["operations"]),
        }

    derived = _derived_symmetry(payload)
    if derived:
        operations = [operation for operation, _action in derived]
        actions = {
            operation["operation_ref"]: {"matrix": _json_safe_matrix(action)}
            for operation, action in derived
        }
        return (
            {
                "operations": operations,
                "spin_space_rotations": [],
                "local_frame_actions": [],
            },
            actions,
            {"mode": "derived-from-lattice", "operation_count": len(operations)},
        )

    return (
        {
            "operations": [_identity_symmetry_operation()],
            "spin_space_rotations": [],
            "local_frame_actions": [],
        },
        {
            "symmetry-operation:identity": {
                "matrix": _identity_matrix_unit_action(local_dimension)
            }
        },
        {"mode": "identity-only", "operation_count": 1},
    )


def _attach_lattice_term_contract(normalized):
    bond_terms = list(normalized.get("bond_terms") or [])
    normalized["schema_version"] = "lattice-term-contract/v1"
    symmetry, symmetry_actions, synthesis = _resolved_symmetry_contract(
        normalized
    )
    normalized["symmetry"] = symmetry
    normalized["symmetry_synthesis"] = synthesis
    normalized["local_hilbert"] = _retained_local_hilbert(
        normalized, symmetry_actions
    )
    normalized["lattice_structure"] = _lattice_structure_from_bond_terms(
        bond_terms, normalized
    )
    normalized["term_attachments"] = _term_attachments_from_bond_terms(normalized)
    normalized["solver_request"] = {
        "task": "classical_ground_state",
        "preferred_methods": ["auto"],
        "outputs": ["classical_state"],
        "selected_term_set_ref": (
            normalized["term_attachments"]["term_sets"][0]["term_set_ref"]
            if normalized["term_attachments"]["term_sets"]
            else None
        ),
        "selected_term_refs": [],
        "selected_bond_orbit_refs": [],
        "selection_policy": "term_set_then_explicit_refs",
    }
    normalized.setdefault("parameters", {})
    normalized.setdefault("provenance", {})
    return normalized


def normalize_cpn_pair_model(payload):
    _require_dict(payload)
    normalized = deepcopy(payload)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("model_bond_label", "cpn_pair_model")
    normalized.setdefault("classical_bond_label", "cpn")
    normalized.setdefault("onsite_terms", [])
    normalized.setdefault("bond_terms", [])
    normalized.setdefault("pair_operator_convention", {})
    normalized["pair_operator_convention"].setdefault("representation", "pair_matrix")
    normalized["pair_operator_convention"].setdefault("pair_basis_order", "site_i_major_site_j_minor")
    normalized["pair_operator_convention"].setdefault(
        "tensor_view",
        {
            "kind": "K_ab_cd",
            "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
        },
    )
    normalized.setdefault("provenance", {})
    return _attach_lattice_term_contract(normalized)


def validate_cpn_pair_model(payload):
    _require_dict(payload)
    if str(payload.get("model_bond_label")) != "cpn_pair_model":
        raise ValueError("unsupported-model-bond_label")
    if str(payload.get("classical_bond_label")) != "cpn":
        raise ValueError("unsupported-classical-bond_label")

    local_dimension = int(payload.get("local_dimension", 0))
    if local_dimension <= 0:
        raise ValueError("invalid-local-dimension")

    pair_operator_convention = dict(payload.get("pair_operator_convention") or {})
    if str(pair_operator_convention.get("pair_basis_order")) != "site_i_major_site_j_minor":
        raise ValueError("unsupported-pair-basis-order")

    bond_terms = list(payload.get("bond_terms") or [])
    expected_pair_shape = [local_dimension * local_dimension, local_dimension * local_dimension]
    for term in bond_terms:
        if not isinstance(term, dict):
            raise ValueError("bond-term-must-be-dict")
        if "source" not in term or "target" not in term or "translation" not in term:
            raise ValueError("bond-term-missing-site-identity")
        translation = list(term.get("translation") or [])
        if len(translation) != 3:
            raise ValueError("bond-term-translation-must-have-length-3")
        matrix_shape = list(term.get("matrix_shape") or [])
        if matrix_shape and matrix_shape != expected_pair_shape:
            raise ValueError("pair-matrix-dimension-mismatch")
        _validate_serialized_matrix(
            term.get("pair_matrix"),
            expected_shape=expected_pair_shape,
            error_code="pair-matrix-dimension-mismatch",
        )

    onsite_terms = list(payload.get("onsite_terms") or [])
    for term in onsite_terms:
        if not isinstance(term, dict):
            raise ValueError("onsite-term-must-be-dict")
        if term.get("kind") != "local_operator_matrix":
            continue
        matrix = term.get("payload", {}).get("matrix")
        _validate_serialized_matrix(
            matrix,
            expected_shape=[local_dimension, local_dimension],
            error_code="onsite-matrix-dimension-mismatch",
        )

    return payload
