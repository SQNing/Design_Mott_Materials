#!/usr/bin/env python3

from copy import deepcopy
from fractions import Fraction
from math import gcd


def _coerce_integer_vector(vector):
    values = [int(value) for value in vector]
    if len(values) != 3:
        raise ValueError("magnetic supercell vectors must have length 3")
    return values


def _coerce_integer_matrix(matrix):
    rows = [_coerce_integer_vector(row) for row in matrix]
    if len(rows) != 3:
        raise ValueError("magnetic supercell matrices must be 3x3")
    return rows


def _determinant_3x3(matrix):
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return (
        a * (e * i - f * h)
        - b * (d * i - f * g)
        + c * (d * h - e * g)
    )


def _adjugate_3x3(matrix):
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    cofactors = [
        [e * i - f * h, -(d * i - f * g), d * h - e * g],
        [-(b * i - c * h), a * i - c * g, -(a * h - b * g)],
        [b * f - c * e, -(a * f - c * d), a * e - b * d],
    ]
    return [
        [cofactors[0][0], cofactors[1][0], cofactors[2][0]],
        [cofactors[0][1], cofactors[1][1], cofactors[2][1]],
        [cofactors[0][2], cofactors[1][2], cofactors[2][2]],
    ]


def _validate_integer_matrix(matrix):
    matrix = _coerce_integer_matrix(matrix)
    determinant = int(_determinant_3x3(matrix))
    if determinant == 0:
        raise ValueError("magnetic supercell matrix must be nonsingular")
    return matrix, determinant


def _row_vector_times_inverse(vector, adjugate, determinant):
    if determinant == 0:
        raise ValueError("magnetic supercell matrix must be nonsingular")
    result = []
    for column in range(3):
        numerator = sum(int(vector[row]) * int(adjugate[row][column]) for row in range(3))
        result.append(Fraction(numerator, determinant))
    return result


def _rationalize_q_vector(q_vector, *, max_denominator):
    rationalized = []
    for component in q_vector:
        fraction = Fraction(float(component)).limit_denominator(int(max_denominator))
        rationalized.append(fraction)
    return rationalized


def _lcm(a, b):
    a = abs(int(a))
    b = abs(int(b))
    if a == 0 or b == 0:
        return max(a, b)
    return (a // gcd(a, b)) * b


def _extended_gcd(a, b):
    a = int(a)
    b = int(b)
    if b == 0:
        if a == 0:
            return 0, 1, 0
        return abs(a), 1 if a > 0 else -1, 0
    g, x1, y1 = _extended_gcd(b, a % b)
    return g, y1, x1 - (a // b) * y1


def _common_denominator_q_vector(fractions):
    common_denominator = 1
    for fraction in fractions:
        common_denominator = _lcm(common_denominator, fraction.denominator)
    return common_denominator


def _normalize_row_sign(row):
    row = [int(value) for value in row]
    for value in row:
        if value < 0:
            return [-entry for entry in row]
        if value > 0:
            return row
    return row


def _deterministic_basis_order(rows):
    normalized = [_normalize_row_sign(row) for row in rows]
    normalized.sort(key=lambda row: (sum(abs(value) for value in row), max(abs(value) for value in row), tuple(row)))
    return normalized


def _construct_minimal_commensurate_basis(scaled_q, common_denominator):
    scaled_q = [int(value) for value in scaled_q]
    common_denominator = int(common_denominator)
    gcd_q = 0
    for value in scaled_q:
        gcd_q = gcd(gcd_q, abs(int(value)))
    common_gcd = gcd(abs(common_denominator), gcd_q)
    target_index = abs(common_denominator) // max(1, common_gcd)

    coordinate_pairs = [(0, 1, 2), (0, 2, 1), (1, 2, 0)]
    selected = None
    for i, j, k in coordinate_pairs:
        pair_gcd = gcd(abs(scaled_q[i]), abs(scaled_q[j]))
        if pair_gcd != 0:
            selected = (i, j, k, pair_gcd)
            break
    if selected is None:
        raise ValueError("cannot construct magnetic supercell basis from an all-zero ordering vector")

    i, j, k, pair_gcd = selected
    pair_gcd, s, t = _extended_gcd(scaled_q[i], scaled_q[j])
    full_gcd = gcd(pair_gcd, abs(scaled_q[k]))
    full_gcd, u, v = _extended_gcd(pair_gcd, scaled_q[k])

    period_multiplier = abs(common_denominator) // gcd(abs(common_denominator), abs(full_gcd))

    seed_vector = [0, 0, 0]
    null_vector_1 = [0, 0, 0]
    null_vector_2 = [0, 0, 0]

    seed_values = [s * u, t * u, v]
    null_values_1 = [scaled_q[j] // pair_gcd, -(scaled_q[i] // pair_gcd), 0]
    null_values_2 = [-(scaled_q[k] // full_gcd) * s, -(scaled_q[k] // full_gcd) * t, pair_gcd // full_gcd]

    for index, value in zip((i, j, k), seed_values):
        seed_vector[index] = int(value)
    for index, value in zip((i, j, k), null_values_1):
        null_vector_1[index] = int(value)
    for index, value in zip((i, j, k), null_values_2):
        null_vector_2[index] = int(value)

    basis = [
        [period_multiplier * int(value) for value in seed_vector],
        null_vector_1,
        null_vector_2,
    ]
    basis = _deterministic_basis_order(basis)
    determinant = abs(int(_determinant_3x3(basis)))
    if determinant != target_index:
        raise ValueError(
            f"constructed magnetic supercell basis has determinant {determinant}, expected {target_index}"
        )
    return basis


def _is_zero_q(q_vector, *, tolerance=1e-10):
    return all(abs(float(value)) <= tolerance for value in q_vector)


def _select_projector_component(projector_summary):
    top_components = projector_summary.get("top_components")
    if isinstance(top_components, list) and top_components:
        components = top_components
    else:
        components = projector_summary.get("components", [])
    ranked = []
    for component in components:
        if not isinstance(component, dict):
            continue
        q_vector = list(component.get("q", []))
        if len(q_vector) != 3 or _is_zero_q(q_vector):
            continue
        ranked.append((float(component.get("weight", 0.0)), [float(value) for value in q_vector]))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1]


def _candidate_matrix_from_q(q_vector, *, max_denominator):
    fractions = _rationalize_q_vector(q_vector, max_denominator=max_denominator)
    common_denominator = _common_denominator_q_vector(fractions)
    scaled_q = [int(fraction * common_denominator) for fraction in fractions]
    matrix = _construct_minimal_commensurate_basis(scaled_q, common_denominator)
    return matrix, fractions


def magnetic_supercell_candidate_from_projector(projector_summary, *, max_denominator=16):
    projector_summary = projector_summary if isinstance(projector_summary, dict) else {}
    q_vector = _select_projector_component(projector_summary)
    if q_vector is None:
        return {
            "status": "no_nonzero_component",
            "selected_q": None,
            "matrix": None,
            "determinant": 0,
        }

    matrix, fractions = _candidate_matrix_from_q(q_vector, max_denominator=max_denominator)
    matrix, determinant = _validate_integer_matrix(matrix)
    phase_winding = []
    for row_index, row in enumerate(matrix):
        winding_fraction = sum(
            fractions[axis] * int(row[axis])
            for axis in range(3)
        )
        phase_winding.append(
            {
                "row": int(row_index),
                "row_vector": [int(value) for value in row],
                "phase_winding": float(winding_fraction),
            }
        )
    return {
        "status": "ok",
        "selected_q": [float(value) for value in q_vector],
        "matrix": matrix,
        "determinant": abs(int(determinant)),
        "commensurability": {
            "max_denominator": int(max_denominator),
            "axis_phase_winding": phase_winding,
            "basis_phase_winding": phase_winding,
        },
    }


def enumerate_magnetic_cell_cosets(matrix):
    matrix, determinant = _validate_integer_matrix(matrix)
    determinant_abs = abs(int(determinant))
    adjugate = _adjugate_3x3(matrix)

    lower_bounds = []
    upper_bounds = []
    for column in range(3):
        column_values = [int(matrix[row][column]) for row in range(3)]
        lower_bounds.append(sum(min(0, value) for value in column_values))
        upper_bounds.append(sum(max(0, value) for value in column_values))

    representatives = []
    seen = set()
    for x in range(lower_bounds[0], upper_bounds[0] + 1):
        for y in range(lower_bounds[1], upper_bounds[1] + 1):
            for z in range(lower_bounds[2], upper_bounds[2] + 1):
                candidate = [int(x), int(y), int(z)]
                fractional = _row_vector_times_inverse(candidate, adjugate, determinant)
                if all(Fraction(0, 1) <= value < Fraction(1, 1) for value in fractional):
                    key = tuple(candidate)
                    if key not in seen:
                        seen.add(key)
                        representatives.append(candidate)

    representatives.sort()
    if len(representatives) != determinant_abs:
        raise ValueError(
            "failed to enumerate the expected number of magnetic-cell coset representatives: "
            f"expected {determinant_abs}, found {len(representatives)}"
        )
    return representatives


def _decompose_chemical_cell(matrix, representatives, chemical_cell):
    matrix, determinant = _validate_integer_matrix(matrix)
    adjugate = _adjugate_3x3(matrix)
    chemical_cell = _coerce_integer_vector(chemical_cell)
    for representative_index, representative in enumerate(representatives):
        delta = [
            int(chemical_cell[axis]) - int(representative[axis])
            for axis in range(3)
        ]
        magnetic_translation = _row_vector_times_inverse(delta, adjugate, determinant)
        if all(value.denominator == 1 for value in magnetic_translation):
            return representative_index, [int(value) for value in representative], [int(value) for value in magnetic_translation]
    raise ValueError(f"could not decompose chemical cell {chemical_cell!r} into the magnetic lattice")


def _serialize_fractional_direct_coordinate(value):
    return float(value.numerator) / float(value.denominator)


def _magnetic_position_from_chemical(position, representative, matrix):
    matrix, determinant = _validate_integer_matrix(matrix)
    adjugate = _adjugate_3x3(matrix)
    chemical_direct = [
        Fraction(str(position[axis])) + Fraction(int(representative[axis]), 1)
        for axis in range(3)
    ]
    magnetic_direct = []
    for column in range(3):
        numerator = sum(chemical_direct[row] * adjugate[row][column] for row in range(3))
        magnetic_direct.append(numerator / determinant)
    return [_serialize_fractional_direct_coordinate(value) for value in magnetic_direct]


def _reshape_lattice_vectors(lattice_vectors, matrix):
    reshaped = []
    for row in matrix:
        reshaped.append(
            [
                sum(float(row[column]) * float(lattice_vectors[column][axis]) for column in range(3))
                for axis in range(3)
            ]
        )
    return reshaped


def _copy_term(term):
    return deepcopy(term)


def reshape_cpn_model_to_magnetic_supercell(model, matrix):
    matrix, determinant = _validate_integer_matrix(matrix)
    representatives = enumerate_magnetic_cell_cosets(matrix)
    site_count = len(list(model.get("positions", [])))
    reshaped_positions = []
    reshaped_sites = []
    site_index_map = {}
    for representative_index, representative in enumerate(representatives):
        for site in range(site_count):
            reshaped_site = len(reshaped_positions)
            reshaped_positions.append(
                _magnetic_position_from_chemical(model["positions"][site], representative, matrix)
            )
            reshaped_sites.append(
                {
                    "reshaped_site": int(reshaped_site),
                    "chemical_site": int(site),
                    "chemical_cell": [int(value) for value in representative],
                    "representative_index": int(representative_index),
                }
            )
            site_index_map[(representative_index, site)] = reshaped_site

    reshaped_bonds = []
    for bond in model.get("bond_tensors", []):
        for representative_index, representative in enumerate(representatives):
            target_chemical_cell = [
                int(representative[axis]) + int(bond.get("R", [0, 0, 0])[axis])
                for axis in range(3)
            ]
            target_representative_index, _target_representative, magnetic_translation = _decompose_chemical_cell(
                matrix,
                representatives,
                target_chemical_cell,
            )
            reshaped_bond = _copy_term(bond)
            reshaped_bond["source"] = int(site_index_map[(representative_index, int(bond.get("source", 0)))])
            reshaped_bond["target"] = int(site_index_map[(target_representative_index, int(bond.get("target", 0)))])
            reshaped_bond["R"] = [int(value) for value in magnetic_translation]
            reshaped_bonds.append(reshaped_bond)

    reshaped_onsite_terms = []
    for onsite in model.get("onsite_terms", []):
        for representative_index in range(len(representatives)):
            reshaped_onsite = _copy_term(onsite)
            reshaped_onsite["site"] = int(site_index_map[(representative_index, int(onsite.get("site", 0)))])
            reshaped_onsite_terms.append(reshaped_onsite)

    reshaped_model = deepcopy(model)
    reshaped_model["lattice_vectors"] = _reshape_lattice_vectors(model.get("lattice_vectors", []), matrix)
    reshaped_model["positions"] = reshaped_positions
    reshaped_model["bond_tensors"] = reshaped_bonds
    reshaped_model["bond_count"] = len(reshaped_bonds)
    reshaped_model["magnetic_site_count"] = len(reshaped_positions)
    if "onsite_terms" in reshaped_model or reshaped_onsite_terms:
        reshaped_model["onsite_terms"] = reshaped_onsite_terms
    reshaped_model["magnetic_supercell_mapping"] = {
        "magnetic_supercell_matrix": matrix,
        "determinant": abs(int(determinant)),
        "representative_count": len(representatives),
        "reshaped_site_count": len(reshaped_positions),
        "chemical_site_count": int(site_count),
        "coset_representatives": [[int(value) for value in representative] for representative in representatives],
        "reshaped_sites": reshaped_sites,
    }
    return reshaped_model


def _is_diagonal_matrix(matrix):
    return all(
        int(matrix[row][column]) == (int(matrix[row][row]) if row == column else 0)
        for row in range(3)
        for column in range(3)
    )


def _resolve_state_supercell_shape(state):
    shape = state.get("supercell_shape", state.get("shape"))
    if shape is None:
        raise ValueError("classical state must provide supercell_shape or shape")
    return [int(value) for value in shape]


def _state_ray_lookup(state):
    lookup = {}
    for item in state.get("local_rays", []):
        cell = tuple(int(value) for value in item.get("cell", [0, 0, 0]))
        site = int(item.get("site", 0))
        lookup[(cell, site)] = deepcopy(item.get("vector"))
    return lookup


def _state_explicitly_tracks_site_axis(state):
    return any("site" in item for item in state.get("local_rays", []))


def _wrap_chemical_cell(cell, shape):
    return tuple(int(cell[axis]) % int(shape[axis]) for axis in range(3))


def _diagonal_extent_vector(matrix):
    if not _is_diagonal_matrix(matrix):
        return None
    extents = [int(matrix[axis][axis]) for axis in range(3)]
    if any(extent <= 0 for extent in extents):
        return None
    return extents


def _minimal_axis_period_for_row(row, chemical_shape):
    period = 1
    for axis in range(3):
        modulus = int(chemical_shape[axis])
        if modulus <= 0:
            raise ValueError("chemical supercell shape entries must be positive")
        component = abs(int(row[axis]))
        period = _lcm(period, modulus // gcd(modulus, component))
    return max(1, int(period))


def _enumerate_supercell_cells(shape):
    shape = [int(value) for value in shape]
    return [
        (ix, iy, iz)
        for ix in range(shape[0])
        for iy in range(shape[1])
        for iz in range(shape[2])
    ]


def _chemical_to_magnetic_supercell_shape(chemical_shape, matrix, *, mapping=None):
    chemical_shape = [int(value) for value in chemical_shape]
    if chemical_shape == [1, 1, 1]:
        return [1, 1, 1]
    return [
        _minimal_axis_period_for_row(matrix[axis], chemical_shape)
        for axis in range(3)
    ]


def _magnetic_to_chemical_supercell_shape(magnetic_shape, matrix, *, mapping=None, state=None):
    extents = _diagonal_extent_vector(matrix)
    if extents is None:
        if isinstance(state, dict) and state.get("magnetic_supercell_source_shape") is not None:
            return [int(value) for value in state["magnetic_supercell_source_shape"]]
        if isinstance(mapping, dict) and mapping.get("chemical_supercell_shape") is not None:
            return [int(value) for value in mapping["chemical_supercell_shape"]]
        if magnetic_shape == [1, 1, 1]:
            return [1, 1, 1]
        raise ValueError(
            "magnetic-to-chemical state lifting for non-diagonal magnetic supercells "
            "requires chemical_supercell_shape metadata"
        )
    return [int(magnetic_shape[axis]) * int(extents[axis]) for axis in range(3)]


def _row_vector_times_matrix(vector, matrix):
    return [
        sum(int(vector[row]) * int(matrix[row][column]) for row in range(3))
        for column in range(3)
    ]


def _finite_magnetic_to_chemical_lookup(mapping, magnetic_shape):
    matrix = _coerce_integer_matrix(mapping.get("magnetic_supercell_matrix"))
    chemical_shape = None
    if mapping.get("chemical_supercell_shape") is not None:
        chemical_shape = [int(value) for value in mapping["chemical_supercell_shape"]]
    reshaped_sites = list(mapping.get("reshaped_sites", []))
    if chemical_shape is None:
        raise ValueError("finite magnetic lookup requires chemical_supercell_shape metadata")
    lookup = {}
    for magnetic_cell in _enumerate_supercell_cells(magnetic_shape):
        base_chemical_cell = _row_vector_times_matrix(magnetic_cell, matrix)
        for reshaped_site in reshaped_sites:
            representative = [int(value) for value in reshaped_site["chemical_cell"]]
            chemical_site = int(reshaped_site["chemical_site"])
            chemical_cell = _wrap_chemical_cell(
                [
                    int(base_chemical_cell[axis]) + int(representative[axis])
                    for axis in range(3)
                ],
                chemical_shape,
            )
            lookup.setdefault(
                (tuple(chemical_cell), int(chemical_site)),
                (tuple(int(value) for value in magnetic_cell), int(reshaped_site["reshaped_site"])),
            )
    return lookup


def lift_cpn_state_between_cells(state, mapping, *, direction):
    state = dict(state) if isinstance(state, dict) else {}
    mapping = dict(mapping) if isinstance(mapping, dict) else {}
    if str(direction) not in {"chemical_to_magnetic", "magnetic_to_chemical"}:
        raise ValueError("direction must be chemical_to_magnetic or magnetic_to_chemical")

    matrix = _coerce_integer_matrix(mapping.get("magnetic_supercell_matrix"))
    reshaped_sites = list(mapping.get("reshaped_sites", []))
    if not reshaped_sites:
        raise ValueError("magnetic supercell mapping must include reshaped_sites")

    source_shape = _resolve_state_supercell_shape(state)
    source_lookup = _state_ray_lookup(state)
    source_payload = {
        "schema_version": int(state.get("schema_version", 1)),
        "state_kind": str(state.get("state_kind", "local_rays")),
        "manifold": str(state.get("manifold", "CP^(N-1)")),
        "basis_order": state.get("basis_order"),
        "pair_basis_order": state.get("pair_basis_order"),
    }

    if direction == "chemical_to_magnetic":
        target_shape = _chemical_to_magnetic_supercell_shape(source_shape, matrix, mapping=mapping)
        local_rays = []
        for magnetic_cell in _enumerate_supercell_cells(target_shape):
            base_chemical_cell = _row_vector_times_matrix(magnetic_cell, matrix)
            for reshaped_site in reshaped_sites:
                representative = reshaped_site["chemical_cell"]
                chemical_site = int(reshaped_site["chemical_site"])
                chemical_cell = _wrap_chemical_cell(
                    [
                        int(base_chemical_cell[axis]) + int(representative[axis])
                        for axis in range(3)
                    ],
                    source_shape,
                )
                key = (chemical_cell, chemical_site)
                if key not in source_lookup:
                    raise ValueError(
                        f"missing chemical local ray for cell {list(chemical_cell)} site {chemical_site}"
                    )
                local_rays.append(
                    {
                        "cell": [int(value) for value in magnetic_cell],
                        "site": int(reshaped_site["reshaped_site"]),
                        "vector": deepcopy(source_lookup[key]),
                    }
                )
        return {
            **source_payload,
            "supercell_shape": [int(value) for value in target_shape],
            "magnetic_supercell_source_shape": [int(value) for value in source_shape],
            "local_rays": local_rays,
        }

    target_shape = _magnetic_to_chemical_supercell_shape(source_shape, matrix, mapping=mapping, state=state)
    magnetic_lookup = source_lookup
    local_rays = []
    preserve_site_field = (
        int(mapping.get("chemical_site_count", 1)) > 1
        or _state_explicitly_tracks_site_axis(state)
    )
    finite_lookup = _finite_magnetic_to_chemical_lookup(
        {
            **mapping,
            "chemical_supercell_shape": [int(value) for value in target_shape],
        },
        source_shape,
    )
    for chemical_cell in _enumerate_supercell_cells(target_shape):
        for chemical_site in range(int(mapping.get("chemical_site_count", 1))):
            finite_key = (tuple(int(value) for value in chemical_cell), int(chemical_site))
            if finite_key not in finite_lookup:
                raise ValueError(
                    f"missing finite magnetic representative for chemical cell {list(chemical_cell)} site {chemical_site}"
                )
            magnetic_cell, reshaped_site = finite_lookup[finite_key]
            key = (tuple(int(value) for value in magnetic_cell), int(reshaped_site))
            if key not in magnetic_lookup:
                raise ValueError(
                    f"missing magnetic local ray for cell {list(magnetic_cell)} site {reshaped_site}"
                )
            ray = {
                "cell": [int(value) for value in chemical_cell],
                "vector": deepcopy(magnetic_lookup[key]),
            }
            if preserve_site_field:
                ray["site"] = int(chemical_site)
            local_rays.append(ray)
    return {
        **source_payload,
        "supercell_shape": [int(value) for value in target_shape],
        "local_rays": local_rays,
    }
