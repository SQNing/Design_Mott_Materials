#!/usr/bin/env python3
"""Rotational action on a retained orbital basis.

A CPN payload that keeps several orbitals per site has to say how a structural
operation mixes them; without that the only defensible symmetry is the
identity. Two encodings are accepted, both stored under
``retained_local_space.orbital_representation`` and exactly one of them per
payload:

``real_spherical_harmonics``
    ``characters`` names the real orbital on every retained level, in basis
    order (``d_z2``, ``d_xz``, ...). The action is derived from the polynomial
    form of those functions, so no point-group table is stored and the only
    convention that matters is ``d_z2 = 2 z^2 - x^2 - y^2`` and friends. The
    derivation is exact: the polynomials are homogeneous, a rotation acts by
    substitution, and the Gram matrix of monomials over the sphere turns the
    substituted coefficients back into an orthogonal matrix in the declared
    basis.

``generator_matrices``
    ``generators`` gives the action of a few operations explicitly, in the same
    fractional-rotation convention as ``symmetry.operations[].rotation``. The
    group is closed from them. This is the route for Wannier functions that are
    hybrids rather than pure harmonics, where no label is honest.

A declared representation is never trusted on its own: the derived action is
applied to the declared bond terms and an operation survives only if the pair
matrices agree. A wrong convention can therefore drop operations, never invent
them.
"""

import math

# Real orbital characters as homogeneous polynomials in Cartesian coordinates.
# The overall normalisation is irrelevant -- ``orbital_rotation_matrix``
# normalises each function over the sphere before building the matrix -- so the
# coefficients are the conventional integer ones.
_CHARACTER_POLYNOMIALS = {
    "s": (0, {(0, 0, 0): 1.0}),
    "p_x": (1, {(1, 0, 0): 1.0}),
    "p_y": (1, {(0, 1, 0): 1.0}),
    "p_z": (1, {(0, 0, 1): 1.0}),
    "d_z2": (2, {(0, 0, 2): 2.0, (2, 0, 0): -1.0, (0, 2, 0): -1.0}),
    "d_xz": (2, {(1, 0, 1): 1.0}),
    "d_yz": (2, {(0, 1, 1): 1.0}),
    "d_xy": (2, {(1, 1, 0): 1.0}),
    "d_x2-y2": (2, {(2, 0, 0): 1.0, (0, 2, 0): -1.0}),
}

_CHARACTER_ALIASES = {
    "s": "s",
    "px": "p_x",
    "p_x": "p_x",
    "py": "p_y",
    "p_y": "p_y",
    "pz": "p_z",
    "p_z": "p_z",
    "dz2": "d_z2",
    "d_z2": "d_z2",
    "d_z^2": "d_z2",
    "dxz": "d_xz",
    "d_xz": "d_xz",
    "dyz": "d_yz",
    "d_yz": "d_yz",
    "dxy": "d_xy",
    "d_xy": "d_xy",
    "dx2-y2": "d_x2-y2",
    "d_x2-y2": "d_x2-y2",
    "d_x2y2": "d_x2-y2",
    "d_x2_y2": "d_x2-y2",
}

_TOLERANCE = 1.0e-8
_GENERATOR_TOLERANCE = 1.0e-6
_GROUP_ORDER_LIMIT = 192


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical_character(name):
    key = str(name).strip().lower()
    canonical = _CHARACTER_ALIASES.get(key)
    if canonical is None:
        raise ValueError(
            "orbital-representation-character-unknown:"
            + str(name)
            + "; supported: "
            + ", ".join(sorted(_CHARACTER_POLYNOMIALS))
        )
    return canonical


def _monomials(degree):
    """Return the exponent tuples of every monomial of the given degree."""
    degree = int(degree)
    _require(degree >= 0, "orbital-representation-degree-must-be-non-negative")
    return tuple(
        (left, middle, degree - left - middle)
        for left in range(degree, -1, -1)
        for middle in range(degree - left, -1, -1)
    )


def _double_factorial(value):
    """Return ``value!!`` with ``(-1)!! == 0!! == 1``."""
    value = int(value)
    result = 1
    while value > 0:
        result *= value
        value -= 2
    return result


def _sphere_gram(monomials):
    """Return ``<m_i, m_j>`` over the unit sphere, exactly.

    A monomial integrates to zero unless every exponent is even, and
    ``int x^(2a) y^(2b) z^(2c) dOmega`` is
    ``4 pi (2a-1)!! (2b-1)!! (2c-1)!! / (2a+2b+2c+1)!!``.
    """
    size = len(monomials)
    gram = [[0.0] * size for _ in range(size)]
    for left_index, left in enumerate(monomials):
        for right_index in range(left_index, size):
            total = tuple(
                a + b for a, b in zip(left, monomials[right_index])
            )
            if any(value % 2 for value in total):
                continue
            numerator = 1
            for value in total:
                numerator *= _double_factorial(value - 1)
            entry = (
                4.0
                * math.pi
                * float(numerator)
                / float(_double_factorial(sum(total) + 1))
            )
            gram[left_index][right_index] = entry
            gram[right_index][left_index] = entry
    return gram


def _substitution(exponents, matrix):
    """Expand ``prod_a (sum_b matrix[a][b] x_b)^exponents[a]``."""
    result = {(0, 0, 0): 1.0}
    for axis, power in enumerate(exponents):
        if power == 0:
            continue
        row = matrix[axis]
        for _repeat in range(power):
            expanded = {}
            for current, coefficient in result.items():
                for column in range(3):
                    factor = float(row[column])
                    if factor == 0.0:
                        continue
                    target = list(current)
                    target[column] += 1
                    key = tuple(target)
                    expanded[key] = expanded.get(key, 0.0) + coefficient * factor
            result = expanded
    return result


def _degree_block(characters, rotation):
    """Return the orthogonal action on one degree's characters."""
    import numpy

    degree = _CHARACTER_POLYNOMIALS[characters[0]][0]
    monomials = _monomials(degree)
    index_of = {monomial: index for index, monomial in enumerate(monomials)}
    gram = numpy.asarray(_sphere_gram(monomials), dtype=float)

    basis = numpy.zeros((len(monomials), len(characters)), dtype=float)
    for column, character in enumerate(characters):
        for exponents, coefficient in _CHARACTER_POLYNOMIALS[character][1].items():
            basis[index_of[exponents], column] += float(coefficient)

    norms = [
        math.sqrt(max(float(basis[:, column] @ gram @ basis[:, column]), 0.0))
        for column in range(len(characters))
    ]
    if any(norm <= 0.0 for norm in norms):
        raise ValueError("orbital-representation-character-degenerate")
    for column, norm in enumerate(norms):
        basis[:, column] /= norm

    substitution = numpy.zeros((len(monomials), len(monomials)), dtype=float)
    for column, exponents in enumerate(monomials):
        # A structural rotation acts on a function as ``f -> f(R^-1 x)``; the
        # transpose is the inverse for an orthogonal matrix.
        for image, coefficient in _substitution(exponents, rotation.T).items():
            substitution[index_of[image], column] += float(coefficient)

    return basis.T @ gram @ substitution @ basis


def _frame_for_axis(axis):
    """Return a right-handed frame whose third column is ``axis``."""
    import numpy

    vector = numpy.asarray(axis, dtype=float)
    _require(vector.shape == (3,), "orbital-representation-axis-must-be-3d")
    norm = float(numpy.linalg.norm(vector))
    _require(norm > _TOLERANCE, "orbital-representation-axis-must-be-nonzero")
    normal = vector / norm
    seed = numpy.array([1.0, 0.0, 0.0])
    if abs(float(normal[0])) > 0.9:
        seed = numpy.array([0.0, 1.0, 0.0])
    first = seed - float(seed @ normal) * normal
    first /= float(numpy.linalg.norm(first))
    second = numpy.cross(normal, first)
    return numpy.column_stack([first, second, normal])


def orbital_rotation_matrix(characters, rotation, quantization_axis=None):
    """Return the action of ``rotation`` on the declared orbital characters.

    ``characters`` lists one label per retained orbital, in basis order. Mixed
    degrees are allowed and produce a block-diagonal action, because a rotation
    cannot mix functions of different degree.

    ``quantization_axis`` rotates the frame the characters are defined in. It
    defaults to the Cartesian ``z`` axis of the lattice, which is the usual
    convention, and an explicit ``z`` axis is identical to leaving it out; a
    different axis conjugates the action into that frame.
    """
    import numpy

    matrix = numpy.asarray(rotation, dtype=float)
    _require(matrix.shape == (3, 3), "orbital-representation-rotation-must-be-3d")
    _require(
        float(numpy.max(numpy.abs(matrix @ matrix.T - numpy.eye(3)))) <= _GENERATOR_TOLERANCE,
        "orbital-representation-rotation-must-be-orthogonal",
    )

    if quantization_axis is not None:
        frame = _frame_for_axis(quantization_axis)
        matrix = frame.T @ matrix @ frame

    labels = [_canonical_character(name) for name in characters]
    _require(labels, "orbital-representation-characters-must-be-non-empty")
    degrees = [_CHARACTER_POLYNOMIALS[label][0] for label in labels]

    action = numpy.zeros((len(labels), len(labels)), dtype=complex)
    for degree in sorted(set(degrees)):
        indexes = [index for index, value in enumerate(degrees) if value == degree]
        block = _degree_block([labels[index] for index in indexes], matrix)
        for row, outer in enumerate(indexes):
            for column, inner in enumerate(indexes):
                action[outer, inner] = block[row, column]

    return action


def close_generator_group(generators, max_order=_GROUP_ORDER_LIMIT):
    """Close a list of ``{"rotation", "matrix"}`` generators into a group.

    Returns a list of ``(rotation, matrix)`` pairs containing the identity
    first. Closure is what makes a handful of declared operations usable as a
    lookup table for every candidate the crystal group offers.
    """
    import numpy

    _require(generators, "orbital-representation-generators-must-be-non-empty")
    rotations = []
    matrices = []
    for record in generators:
        if not isinstance(record, dict):
            raise ValueError("orbital-representation-generator-must-be-a-mapping")
        rotation = numpy.asarray(record["rotation"], dtype=float)
        matrix = numpy.asarray(record["matrix"], dtype=complex)
        _require(rotation.shape == (3, 3), "orbital-representation-generator-rotation-must-be-3d")
        _require(
            float(numpy.max(numpy.abs(rotation @ rotation.T - numpy.eye(3))))
            <= _GENERATOR_TOLERANCE,
            "orbital-representation-generator-rotation-must-be-orthogonal",
        )
        determinant = float(numpy.linalg.det(rotation))
        _require(
            abs(abs(determinant) - 1.0) <= _GENERATOR_TOLERANCE,
            "orbital-representation-generator-rotation-must-have-unit-determinant",
        )
        _require(
            matrix.ndim == 2 and matrix.shape[0] == matrix.shape[1],
            "orbital-representation-generator-matrix-must-be-square",
        )
        _require(
            float(numpy.max(numpy.abs(matrix @ matrix.conj().T - numpy.eye(matrix.shape[0]))))
            <= _GENERATOR_TOLERANCE,
            "orbital-representation-generator-matrix-must-be-unitary",
        )
        if _index_of_rotation(rotations, rotation) is None:
            rotations.append(rotation)
            matrices.append(matrix)

    identity = numpy.eye(3)
    if _index_of_rotation(rotations, identity) is None:
        rotations.insert(0, identity)
        matrices.insert(0, numpy.eye(matrices[0].shape[0], dtype=complex))

    frontier = list(range(len(rotations)))
    while frontier:
        index = frontier.pop()
        for other in range(len(rotations)):
            for left, right in ((index, other), (other, index)):
                product = rotations[left] @ rotations[right]
                if _index_of_rotation(rotations, product) is not None:
                    continue
                rotations.append(product)
                matrices.append(matrices[left] @ matrices[right])
                if len(rotations) > int(max_order):
                    raise ValueError("orbital-representation-group-too-large")
                frontier.append(len(rotations) - 1)
    return list(zip(rotations, matrices))


def _index_of_rotation(rotations, candidate, tolerance=_GENERATOR_TOLERANCE):
    import numpy

    for index, rotation in enumerate(rotations):
        if float(numpy.max(numpy.abs(rotation - candidate))) <= tolerance:
            return index
    return None


def _generator_action(group, rotation, tolerance=1.0e-5):
    import numpy

    candidate = numpy.asarray(rotation, dtype=float)
    for reference, matrix in group:
        if float(numpy.max(numpy.abs(reference - candidate))) <= tolerance:
            return matrix
    return None


class OrbitalRepresentation:
    """Resolve the orbital action of a structural operation, once per payload."""

    def __init__(self, record, orbital_count):
        _require(isinstance(record, dict), "orbital-representation-must-be-a-mapping")
        self.orbital_count = int(orbital_count)
        _require(self.orbital_count > 0, "orbital-representation-needs-a-positive-orbital-count")
        self.convention = str(record.get("convention") or "")
        if self.convention == "real_spherical_harmonics":
            characters = [
                _canonical_character(name)
                for name in list(record.get("characters") or [])
            ]
            _require(
                len(characters) == self.orbital_count,
                "orbital-representation-character-count-mismatch:"
                + f"expected {self.orbital_count}, got {len(characters)}",
            )
            self.characters = characters
            axis = record.get("quantization_axis")
            self.quantization_axis = (
                [float(value) for value in axis] if axis is not None else None
            )
            self.group = None
        elif self.convention == "generator_matrices":
            self.characters = None
            self.quantization_axis = None
            self.group = close_generator_group(list(record.get("generators") or []))
            size = self.group[0][1].shape[0]
            _require(
                size == self.orbital_count,
                "orbital-representation-generator-size-mismatch:"
                + f"expected {self.orbital_count}, got {size}",
            )
        else:
            raise ValueError(
                "orbital-representation-convention-unknown:" + self.convention
            )

    def action(self, fractional_rotation, cartesian_rotation):
        """Return the orbital matrix for one operation, or ``None``."""
        if self.convention == "real_spherical_harmonics":
            return orbital_rotation_matrix(
                self.characters, cartesian_rotation, self.quantization_axis
            )
        return _generator_action(self.group, fractional_rotation)
