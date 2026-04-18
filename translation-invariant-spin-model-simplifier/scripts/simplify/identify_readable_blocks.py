#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dipole_operator_aliases(axis):
    return {
        "x": ["Sx", "T1_x"],
        "y": ["Sy", "T1_y"],
        "z": ["Sz", "T1_z"],
    }.get(axis, [f"S{axis}"])


def _lookup_dipole_term(labels, row_axis, col_axis):
    for left in _dipole_operator_aliases(row_axis):
        for right in _dipole_operator_aliases(col_axis):
            term = labels.get(f"{left}@0 {right}@1")
            if term is not None:
                return term
    return None


def _match_isotropic_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = [
        _lookup_dipole_term(labels, "x", "x"),
        _lookup_dipole_term(labels, "y", "y"),
        _lookup_dipole_term(labels, "z", "z"),
    ]
    if not all(needed):
        return None
    coefficients = [term["coefficient"] for term in needed]
    if coefficients[0] == coefficients[1] == coefficients[2]:
        return {
            "type": "isotropic_exchange",
            "source_terms": needed,
            "coefficient": coefficients[0],
        }
    return None


def _match_xxz_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    xx = _lookup_dipole_term(labels, "x", "x")
    yy = _lookup_dipole_term(labels, "y", "y")
    zz = _lookup_dipole_term(labels, "z", "z")
    if not all((xx, yy, zz)):
        return None
    coefficient_xy = xx["coefficient"]
    coefficient_y = yy["coefficient"]
    coefficient_z = zz["coefficient"]
    if coefficient_xy != coefficient_y or coefficient_xy == coefficient_z:
        return None
    return {
        "type": "xxz_exchange",
        "source_terms": [xx, yy, zz],
        "coefficient_xy": coefficient_xy,
        "coefficient_z": coefficient_z,
    }


def _match_symmetric_exchange_matrix(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    diagonal = {
        "xx": _lookup_dipole_term(labels, "x", "x"),
        "yy": _lookup_dipole_term(labels, "y", "y"),
        "zz": _lookup_dipole_term(labels, "z", "z"),
    }
    if not all(diagonal.values()):
        return None

    pairs = {
        "xy": ("Sx@0 Sy@1", "Sy@0 Sx@1"),
        "xz": ("Sx@0 Sz@1", "Sz@0 Sx@1"),
        "yz": ("Sy@0 Sz@1", "Sz@0 Sy@1"),
    }
    offdiag = {}
    source_terms = list(diagonal.values())
    has_offdiag = False
    for key, (lhs_label, rhs_label) in pairs.items():
        lhs = labels.get(lhs_label)
        rhs = labels.get(rhs_label)
        if lhs is None and rhs is None:
            offdiag[key] = 0.0
            continue
        if lhs is None or rhs is None or lhs["coefficient"] != rhs["coefficient"]:
            return None
        offdiag[key] = lhs["coefficient"]
        source_terms.extend([lhs, rhs])
        has_offdiag = True

    coefficient_x = diagonal["xx"]["coefficient"]
    coefficient_y = diagonal["yy"]["coefficient"]
    coefficient_z = diagonal["zz"]["coefficient"]
    if not has_offdiag and (coefficient_x == coefficient_y == coefficient_z or coefficient_x == coefficient_y):
        return None

    matrix = [
        [coefficient_x, offdiag["xy"], offdiag["xz"]],
        [offdiag["xy"], coefficient_y, offdiag["yz"]],
        [offdiag["xz"], offdiag["yz"], coefficient_z],
    ]
    isotropic_exchange = (coefficient_x + coefficient_y + coefficient_z) / 3.0
    symmetric_traceless_matrix = [
        [
            matrix[row_index][col_index] - (isotropic_exchange if row_index == col_index else 0.0)
            for col_index in range(3)
        ]
        for row_index in range(3)
    ]

    return {
        "type": "symmetric_exchange_matrix",
        "source_terms": source_terms,
        "matrix": matrix,
        "symmetric_matrix": matrix,
        "symmetric_traceless_matrix": symmetric_traceless_matrix,
        "isotropic_exchange": isotropic_exchange,
    }


def _match_exchange_tensor(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    axes = ["x", "y", "z"]
    matrix = []
    source_terms = []
    diagonal_present = False
    offdiag_present = False
    asymmetric_present = False

    for row_axis in axes:
        row = []
        for col_axis in axes:
            term = _lookup_dipole_term(labels, row_axis, col_axis)
            coefficient = 0.0 if term is None else term["coefficient"]
            row.append(coefficient)
            if term is not None:
                source_terms.append(term)
                if row_axis == col_axis:
                    diagonal_present = True
                else:
                    offdiag_present = True
        matrix.append(row)

    if not diagonal_present:
        return None

    for row_index in range(3):
        for col_index in range(row_index + 1, 3):
            if matrix[row_index][col_index] != matrix[col_index][row_index]:
                asymmetric_present = True
                break
        if asymmetric_present:
            break

    if not offdiag_present or not asymmetric_present:
        return None

    symmetric_matrix = [
        [
            0.5 * (matrix[row_index][col_index] + matrix[col_index][row_index])
            for col_index in range(3)
        ]
        for row_index in range(3)
    ]
    antisymmetric_matrix = [
        [
            0.5 * (matrix[row_index][col_index] - matrix[col_index][row_index])
            for col_index in range(3)
        ]
        for row_index in range(3)
    ]
    isotropic_exchange = (
        symmetric_matrix[0][0] + symmetric_matrix[1][1] + symmetric_matrix[2][2]
    ) / 3.0
    symmetric_traceless_matrix = [
        [
            symmetric_matrix[row_index][col_index]
            - (isotropic_exchange if row_index == col_index else 0.0)
            for col_index in range(3)
        ]
        for row_index in range(3)
    ]
    dm_vector = [
        antisymmetric_matrix[1][2],
        antisymmetric_matrix[2][0],
        antisymmetric_matrix[0][1],
    ]

    return {
        "type": "exchange_tensor",
        "source_terms": source_terms,
        "matrix": matrix,
        "symmetric_matrix": symmetric_matrix,
        "antisymmetric_matrix": antisymmetric_matrix,
        "symmetric_traceless_matrix": symmetric_traceless_matrix,
        "isotropic_exchange": isotropic_exchange,
        "dm_vector": dm_vector,
    }


def _match_pseudospin_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = [
        "spin_X__orbital_I@0 spin_X__orbital_I@1",
        "spin_Y__orbital_I@0 spin_Y__orbital_I@1",
        "spin_Z__orbital_I@0 spin_Z__orbital_I@1",
    ]
    if not all(label in labels for label in needed):
        return None
    coefficients = [labels[label]["coefficient"] for label in needed]
    if coefficients[0] == coefficients[1] == coefficients[2]:
        return {
            "type": "pseudospin_exchange",
            "source_terms": [labels[label] for label in needed],
            "coefficient": coefficients[0],
        }
    return None


def _match_orbital_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = [
        "spin_I__orbital_X@0 spin_I__orbital_X@1",
        "spin_I__orbital_Y@0 spin_I__orbital_Y@1",
        "spin_I__orbital_Z@0 spin_I__orbital_Z@1",
    ]
    if not all(label in labels for label in needed):
        return None
    coefficients = [labels[label]["coefficient"] for label in needed]
    if coefficients[0] == coefficients[1] == coefficients[2]:
        return {
            "type": "orbital_exchange",
            "source_terms": [labels[label] for label in needed],
            "coefficient": coefficients[0],
        }
    return None


def _match_dm_like(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    lhs = _lookup_dipole_term(labels, "x", "y")
    rhs = _lookup_dipole_term(labels, "y", "x")
    if lhs and rhs and lhs["coefficient"] == -rhs["coefficient"]:
        return {
            "type": "dm_like",
            "source_terms": [lhs, rhs],
            "coefficient": lhs["coefficient"],
        }
    return None


def _parse_canonical_label_factors(label):
    factors = []
    for factor in str(label or "").split():
        match = re.fullmatch(r"([A-Za-z0-9_]+)@(-?\d+)", factor)
        if not match:
            return []
        operator, site = match.groups()
        factors.append((int(site), operator))
    return factors


def _quadrupole_component_label(term):
    factors = sorted(_parse_canonical_label_factors(term.get("canonical_label")), key=lambda item: item[0])
    if len(factors) != 2:
        return term.get("canonical_label")
    return f"{factors[0][1]}:{factors[1][1]}"


def _physical_multipole_label(rank, family):
    if family == "quadrupole" or rank == 2:
        return "quadrupolar"
    if rank == 3:
        return "octupolar"
    if rank == 4:
        return "hexadecapolar"
    if rank == 5:
        return "dotriacontapolar"
    if rank == 6:
        return "hexacontatetrapolar"
    return f"rank-{rank} multipolar"


def _physical_multipole_label_aliases(rank, family):
    if family == "quadrupole" or rank == 2:
        return []
    if rank == 3:
        return []
    if rank == 4:
        return []
    if rank == 5:
        return ["triakontadipolar"]
    if rank == 6:
        return ["tetrahexacontapolar"]
    return []


def _copy_shared_shell_metadata(block, terms):
    shell_indices = {term.get("shell_index") for term in terms if term.get("shell_index") is not None}
    if len(shell_indices) == 1:
        block["shell_index"] = next(iter(shell_indices))

    distances = {term.get("distance") for term in terms if term.get("distance") is not None}
    if len(distances) == 1:
        block["distance"] = next(iter(distances))

    shell_labels = {term.get("shell_label") for term in terms if term.get("shell_label") is not None}
    if len(shell_labels) == 1:
        block["shell_label"] = next(iter(shell_labels))
    return block


def _same_component_channel(component_label):
    parts = str(component_label or "").split(":")
    return len(parts) == 2 and parts[0] == parts[1]


def _quadrupolar_tendency(component_label, coefficient):
    if not _same_component_channel(component_label):
        return None
    if coefficient is None:
        return None
    if coefficient < 0:
        return "ferroquadrupolar_like"
    if coefficient > 0:
        return "antiferroquadrupolar_like"
    return None


def _quadrupole_component_sector(component):
    component = str(component or "")
    if component == "T2_0":
        return "axial quadrupolar (Q3z2-r2-like)"
    if component in {"T2_c1", "T2_s1"}:
        return "off-diagonal quadrupolar (Qzx/Qyz-like)"
    if component in {"T2_c2", "T2_s2"}:
        return "planar/nematic quadrupolar (Qx2-y2/Qxy-like)"
    return "generic quadrupolar"


def _quadrupolar_channel_label(component_label):
    parts = str(component_label or "").split(":")
    if len(parts) != 2:
        return "generic quadrupolar"
    left = _quadrupole_component_sector(parts[0])
    right = _quadrupole_component_sector(parts[1])
    if left == right:
        return left
    return f"mixed quadrupolar ({left} x {right})"


def _match_quadrupole_coupling(two_body_terms):
    matched_terms = [
        term
        for term in two_body_terms
        if term.get("multipole_family") == "quadrupole"
        and term.get("multipole_rank") == 2
        and term.get("body_order") == 2
    ]
    if not matched_terms:
        return None

    components = []
    for term in sorted(matched_terms, key=lambda item: (-abs(item["coefficient"]), item["canonical_label"])):
        components.append(
            {
                "label": _quadrupole_component_label(term),
                "coefficient": term["coefficient"],
                "canonical_label": term["canonical_label"],
            }
        )

    dominant = components[0]
    return {
        "type": "quadrupole_coupling",
        "source_terms": matched_terms,
        "multipole_family": "quadrupole",
        "multipole_rank": 2,
        "body_order": 2,
        "term_count": len(matched_terms),
        "dominant_component": dominant["label"],
        "dominant_coefficient": dominant["coefficient"],
        "components": components,
    }


def _match_higher_multipole_coupling(two_body_terms):
    matched_terms = [
        term
        for term in two_body_terms
        if term.get("multipole_family") == "higher_multipole"
        and term.get("body_order") == 2
        and isinstance(term.get("multipole_rank"), int)
        and term.get("multipole_rank", 0) >= 3
    ]
    if not matched_terms:
        return []

    by_rank = {}
    for term in matched_terms:
        by_rank.setdefault(term.get("multipole_rank"), []).append(term)

    blocks = []
    for rank, rank_terms in sorted(
        by_rank.items(),
        key=lambda item: (
            -max(abs(term["coefficient"]) for term in item[1]),
            -item[0],
        ),
    ):
        components = []
        for term in sorted(rank_terms, key=lambda item: (-abs(item["coefficient"]), item["canonical_label"])):
            components.append(
                {
                    "label": _quadrupole_component_label(term),
                    "coefficient": term["coefficient"],
                    "canonical_label": term["canonical_label"],
                }
            )

        dominant = components[0]
        blocks.append(
            {
                "type": "higher_multipole_coupling",
                "source_terms": rank_terms,
                "multipole_family": "higher_multipole",
                "multipole_rank": rank,
                "body_order": 2,
                "term_count": len(rank_terms),
                "dominant_component": dominant["label"],
                "dominant_coefficient": dominant["coefficient"],
                "components": components,
            }
        )

    return blocks


def _match_scalar_chirality(three_body_terms):
    for term in three_body_terms:
        if term["canonical_label"] == "Sx@0 Sy@1 Sz@2":
            return {
                "type": "scalar_chirality_like",
                "source_terms": [term],
                "coefficient": term["coefficient"],
            }
    return None


def _group_terms_by_family(terms):
    grouped = {}
    for term in terms:
        family = term.get("family")
        grouped.setdefault(family, []).append(term)
    return grouped


def _transpose(matrix):
    return [[matrix[col][row] for col in range(len(matrix))] for row in range(len(matrix[0]))]


def _matmul(lhs, rhs):
    rows = len(lhs)
    shared = len(rhs)
    cols = len(rhs[0])
    return [
        [
            sum(lhs[row][index] * rhs[index][col] for index in range(shared))
            for col in range(cols)
        ]
        for row in range(rows)
    ]


def _rotate_exchange_matrix(matrix, rotation_matrix):
    if not isinstance(rotation_matrix, list) or len(rotation_matrix) != 3:
        return None
    if any(not isinstance(row, list) or len(row) != 3 for row in rotation_matrix):
        return None
    return _matmul(_transpose(rotation_matrix), _matmul(matrix, rotation_matrix))


def _format_human_value(value):
    if isinstance(value, (int, float)):
        return f"{value:.3f}"
    return str(value)


def _is_effectively_zero(value, tolerance=1.0e-12):
    return abs(float(value)) <= tolerance


def _human_axis_token(axis_label):
    token = "".join(char for char in str(axis_label or "") if char.isalnum())
    return token or str(axis_label or "")


def _matrix_parameter_name(left_axis, right_axis=None):
    left = _human_axis_token(left_axis)
    right = _human_axis_token(right_axis if right_axis is not None else left_axis)
    return f"J{left}{right}"


def _gamma_parameter_name(left_axis, right_axis):
    left = _human_axis_token(left_axis)
    right = _human_axis_token(right_axis)
    return f"Gamma_{left}{right}"


def _display_axes_for_block(block, axes):
    axis_list = list(axes or [])
    if len(axis_list) != 3:
        return axis_list
    if block.get("coordinate_frame") == "global_crystallographic":
        return ["x", "y", "z"]
    return axis_list


def _dominant_axis_from_diagonal(diagonals):
    axis_label, _value = max(diagonals, key=lambda item: abs(item[1]))
    return axis_label


def _derive_jzz_jpm_jpmpm_jzpm_view(matrix, axis_labels):
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        return None
    if len(axis_labels) != 3:
        return None
    if not (
        _is_effectively_zero(matrix[0][1])
        and _is_effectively_zero(matrix[1][0])
        and _is_effectively_zero(matrix[0][2])
        and _is_effectively_zero(matrix[2][0])
    ):
        return None

    planar_a = matrix[0][0]
    planar_b = matrix[1][1]
    longitudinal = matrix[2][2]
    offdiag = matrix[1][2]
    if not _is_effectively_zero(matrix[2][1] - offdiag):
        return None

    return {
        "physical_label": "anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm)",
        "axis_labels": list(axis_labels),
        "parameter_entries": [
            {"name": "Jzz", "value": longitudinal, "kind": "longitudinal"},
            {"name": "Jpm", "value": 0.5 * (planar_a + planar_b), "kind": "planar_average"},
            {"name": "Jpmpm", "value": 0.5 * (planar_a - planar_b), "kind": "planar_anisotropy"},
            {"name": "Jzpm", "value": offdiag, "kind": "offdiagonal_mixing"},
        ],
    }


def _derive_symmetric_offdiagonal_parameters(matrix, axis_labels):
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        return []
    if len(axis_labels) != 3:
        return []

    pairs = [
        (0, 1, axis_labels[0], axis_labels[1]),
        (0, 2, axis_labels[0], axis_labels[2]),
        (1, 2, axis_labels[1], axis_labels[2]),
    ]
    parameter_entries = []
    for row_index, col_index, left_axis, right_axis in pairs:
        value = 0.5 * (matrix[row_index][col_index] + matrix[col_index][row_index])
        if _is_effectively_zero(value):
            continue
        parameter_entries.append(
            {
                "name": _gamma_parameter_name(left_axis, right_axis),
                "value": value,
                "kind": "symmetric_offdiagonal",
                "axes": [left_axis, right_axis],
            }
        )
    return parameter_entries


def _derive_symmetric_exchange_physical_parameter_view(block, axis_labels):
    matrix = list(block.get("symmetric_matrix") or block.get("matrix") or [])
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        return None

    isotropic_exchange = block.get("isotropic_exchange")
    if isotropic_exchange is None:
        isotropic_exchange = (matrix[0][0] + matrix[1][1] + matrix[2][2]) / 3.0

    gamma_parameters = _derive_symmetric_offdiagonal_parameters(matrix, axis_labels)
    if not gamma_parameters:
        return None

    return {
        "view_kind": "symmetric_exchange_matrix_jiso_gamma",
        "parameters": [{"name": "Jiso", "value": isotropic_exchange, "kind": "isotropic"}] + gamma_parameters,
        "physical_label": "symmetric exchange matrix (Jiso/Gamma)",
    }


def _derive_exchange_tensor_physical_parameter_view(block, axis_labels):
    isotropic_exchange = block.get("isotropic_exchange")
    dm_vector = list(block.get("dm_vector") or [])
    if isotropic_exchange is None or len(dm_vector) != 3:
        return None

    symmetric_matrix = list(block.get("symmetric_matrix") or block.get("matrix") or [])
    gamma_parameters = _derive_symmetric_offdiagonal_parameters(symmetric_matrix, axis_labels)
    parameter_entries = [{"name": "Jiso", "value": isotropic_exchange, "kind": "isotropic"}]
    parameter_entries.extend(gamma_parameters)
    parameter_entries.extend(
        [
            {"name": "Dx", "value": dm_vector[0], "kind": "dm"},
            {"name": "Dy", "value": dm_vector[1], "kind": "dm"},
            {"name": "Dz", "value": dm_vector[2], "kind": "dm"},
        ]
    )
    return {
        "view_kind": "exchange_tensor_jiso_gamma_dm",
        "parameters": parameter_entries,
        "physical_label": "general exchange tensor (Jiso/Gamma/DM)",
    }


def _derive_quadrupole_physical_parameter_view(block):
    components = list(block.get("components") or [])
    if not components:
        return None
    parameter_entries = [
        {
            "name": component.get("label"),
            "value": component.get("coefficient"),
            "kind": "quadrupole_component",
        }
        for component in components[:6]
        if component.get("label") is not None
    ]
    if not parameter_entries:
        return None
    return {
        "view_kind": "quadrupole_coupling_components",
        "parameters": parameter_entries,
        "physical_label": "quadrupolar coupling components",
    }


def _derive_dipole_multipole_physical_parameter_view(source_terms):
    ordered_names = [
        "T1_x:T1_x",
        "T1_y:T1_y",
        "T1_z:T1_z",
        "T1_x:T1_y",
        "T1_x:T1_z",
        "T1_y:T1_z",
        "T1_y:T1_x",
        "T1_z:T1_x",
        "T1_z:T1_y",
    ]
    operator_aliases = {
        "Sx": "T1_x",
        "Sy": "T1_y",
        "Sz": "T1_z",
    }

    def _as_dipole_parameter_name(label):
        parts = str(label or "").split(":")
        if len(parts) != 2:
            return None
        converted = []
        for part in parts:
            if part.startswith("T1_"):
                converted.append(part)
                continue
            alias = operator_aliases.get(part)
            if alias is None:
                return None
            converted.append(alias)
        return f"{converted[0]}:{converted[1]}"

    entries = []
    for term in list(source_terms or []):
        label = _as_dipole_parameter_name(_quadrupole_component_label(term))
        if label is None:
            continue
        entries.append(
            {
                "name": label,
                "value": term.get("coefficient"),
                "kind": "dipole_component",
            }
        )
    if not entries:
        return None
    order_index = {name: idx for idx, name in enumerate(ordered_names)}
    entries.sort(key=lambda entry: (order_index.get(entry["name"], 999), entry["name"]))
    return {
        "view_kind": "dipole_multipole_components",
        "parameters": entries,
        "physical_label": "dipole multipole components",
    }


def _derive_higher_multipole_physical_parameter_view(block):
    components = list(block.get("components") or [])
    rank = block.get("multipole_rank")
    if not components or rank is None:
        return None
    parameter_entries = [
        {
            "name": component.get("label"),
            "value": component.get("coefficient"),
            "kind": "higher_multipole_component",
        }
        for component in components[:6]
        if component.get("label") is not None
    ]
    if not parameter_entries:
        return None
    return {
        "view_kind": f"higher_multipole_coupling_rank_{rank}_components",
        "parameters": parameter_entries,
        "physical_label": f"{_physical_multipole_label(rank, block.get('multipole_family'))} coupling components",
    }


def _annotate_block_for_humans(block):
    annotated = dict(block)
    block_type = block.get("type")
    if block_type == "quadrupole_coupling":
        components = list(block.get("components") or [])
        dominant_component = block.get("dominant_component") or "unspecified"
        dominant_value = block.get("dominant_coefficient")
        physical_label = _physical_multipole_label(block.get("multipole_rank"), block.get("multipole_family"))
        physical_tendency = _quadrupolar_tendency(dominant_component, dominant_value)
        dominant_channel_label = _quadrupolar_channel_label(dominant_component)
        annotated["physical_label"] = physical_label
        annotated["physical_label_aliases"] = _physical_multipole_label_aliases(
            block.get("multipole_rank"),
            block.get("multipole_family"),
        )
        annotated["dominant_channel_label"] = dominant_channel_label
        if physical_tendency is not None:
            annotated["physical_tendency"] = physical_tendency
        summary = (
            f"Quadrupolar two-body coupling with {block.get('term_count', len(components))} retained components. "
            f"Dominant component {dominant_component} = {_format_human_value(dominant_value)}."
        )
        summary += f" Dominant channel sits in the {dominant_channel_label} sector."
        if physical_tendency == "ferroquadrupolar_like":
            summary += " Dominant channel is ferroquadrupolar-like under the H = JQQ convention."
        elif physical_tendency == "antiferroquadrupolar_like":
            summary += " Dominant channel is antiferroquadrupolar-like under the H = JQQ convention."
        if len(components) > 1:
            summary += " Residual quadrupole structure remains component-resolved."
        annotated["human_summary"] = summary
        annotated["human_parameters"] = [
            {
                "name": component.get("label"),
                "value": component.get("coefficient"),
                "kind": "quadrupole_component",
            }
            for component in components[:6]
        ]
        quadrupole_view = _derive_quadrupole_physical_parameter_view(block)
        if quadrupole_view is not None:
            annotated["physical_parameter_view"] = quadrupole_view
        return annotated

    if block_type == "higher_multipole_coupling":
        components = list(block.get("components") or [])
        dominant_component = block.get("dominant_component") or "unspecified"
        dominant_value = block.get("dominant_coefficient")
        rank = block.get("multipole_rank")
        physical_label = _physical_multipole_label(rank, block.get("multipole_family"))
        annotated["physical_label"] = physical_label
        annotated["physical_label_aliases"] = _physical_multipole_label_aliases(
            rank,
            block.get("multipole_family"),
        )
        summary = (
            f"{physical_label.capitalize()} two-body coupling with {block.get('term_count', len(components))} retained components. "
            f"Dominant component {dominant_component} = {_format_human_value(dominant_value)}."
        )
        if len(components) > 1:
            summary += " Structure remains component-resolved."
        annotated["human_summary"] = summary
        annotated["human_parameters"] = [
            {
                "name": component.get("label"),
                "value": component.get("coefficient"),
                "kind": "higher_multipole_component",
            }
            for component in components[:6]
        ]
        higher_view = _derive_higher_multipole_physical_parameter_view(block)
        if higher_view is not None:
            annotated["physical_parameter_view"] = higher_view
        return annotated

    if block_type == "xxz_exchange":
        planar_axes = list(block.get("display_planar_axes") or block.get("planar_axes") or ["x", "y"])
        longitudinal_axis = block.get("display_longitudinal_axis") or block.get("longitudinal_axis") or "z"
        coefficient_xy = block.get("coefficient_xy")
        coefficient_z = block.get("coefficient_z")
        summary = (
            f"Planar coupling Jxy = {_format_human_value(block.get('coefficient_xy'))} "
            f"on ({planar_axes[0]}, {planar_axes[1]}) and longitudinal coupling "
            f"Jz = {_format_human_value(block.get('coefficient_z'))} on {longitudinal_axis}."
        )
        if abs(coefficient_z - coefficient_xy) <= 1e-9:
            summary += " Nearly isotropic."
        elif abs(coefficient_z) > abs(coefficient_xy):
            summary += " Easy-axis-like anisotropy."
        else:
            summary += " Easy-plane-like anisotropy."
        annotated["human_summary"] = summary
        annotated["human_parameters"] = [
            {
                "name": "Jxy",
                "value": block.get("coefficient_xy"),
                "kind": "planar",
                "axes": planar_axes,
            },
            {
                "name": "Jz",
                "value": block.get("coefficient_z"),
                "kind": "longitudinal",
                "axis": longitudinal_axis,
            },
        ]
        annotated["physical_parameter_view"] = {
            "view_kind": "xxz_exchange_jxy_jz",
            "parameters": list(annotated["human_parameters"]),
            "physical_label": "xxz exchange",
        }
        dipole_view = _derive_dipole_multipole_physical_parameter_view(block.get("source_terms"))
        if dipole_view is not None:
            annotated["additional_physical_parameter_views"] = [dipole_view]
        return annotated

    if block_type in {"symmetric_exchange_matrix", "exchange_tensor"}:
        matrix = list(block.get("matrix") or [])
        if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
            return annotated
        axis_labels = list(block.get("matrix_axes") or block.get("axis_labels") or ["x", "y", "z"])
        display_axis_labels = _display_axes_for_block(block, axis_labels)
        exchange_tensor_view = None
        symmetric_exchange_view = None
        if block_type == "symmetric_exchange_matrix":
            symmetric_exchange_view = _derive_symmetric_exchange_physical_parameter_view(block, display_axis_labels)
            if symmetric_exchange_view is not None:
                annotated["physical_parameter_view"] = symmetric_exchange_view
                annotated.setdefault("physical_label", symmetric_exchange_view.get("physical_label"))
        if block_type == "exchange_tensor":
            exchange_tensor_view = _derive_exchange_tensor_physical_parameter_view(block, display_axis_labels)
            if exchange_tensor_view is not None:
                annotated["physical_parameter_view"] = exchange_tensor_view
                gamma_parameters = [
                    entry
                    for entry in exchange_tensor_view["parameters"]
                    if str(entry.get("name", "")).startswith("Gamma_")
                ]
                if gamma_parameters:
                    annotated["symmetric_offdiagonal_parameters"] = gamma_parameters
        physical_view = _derive_jzz_jpm_jpmpm_jzpm_view(matrix, display_axis_labels)
        if physical_view is not None:
            parameter_entries = list(physical_view["parameter_entries"])
            summary = (
                f"Anisotropic spin exchange on axes ({display_axis_labels[0]}, {display_axis_labels[1]}, {display_axis_labels[2]}) "
                f"with Jzz = {_format_human_value(parameter_entries[0]['value'])}, "
                f"Jpm = {_format_human_value(parameter_entries[1]['value'])}, "
                f"Jpmpm = {_format_human_value(parameter_entries[2]['value'])}, "
                f"and Jzpm = {_format_human_value(parameter_entries[3]['value'])}."
            )
            if abs(parameter_entries[0]["value"]) > abs(parameter_entries[1]["value"]):
                summary += f" Longitudinal channel along {display_axis_labels[2]} is dominant over the planar average."
            else:
                summary += " Planar average competes with or exceeds the longitudinal channel."
            if not _is_effectively_zero(parameter_entries[3]["value"]):
                summary += f" Mixed {display_axis_labels[1]}{display_axis_labels[2]} channel is present."
            if block_type == "exchange_tensor":
                dm_vector = list(block.get("dm_vector") or [0.0, 0.0, 0.0])
                if len(dm_vector) == 3:
                    summary += (
                        f" Antisymmetric exchange gives DM = (Dx, Dy, Dz) = "
                        f"({_format_human_value(dm_vector[0])}, {_format_human_value(dm_vector[1])}, {_format_human_value(dm_vector[2])})."
                    )
                    parameter_entries.extend(
                        [
                            {"name": "Dx", "value": dm_vector[0], "kind": "dm"},
                            {"name": "Dy", "value": dm_vector[1], "kind": "dm"},
                            {"name": "Dz", "value": dm_vector[2], "kind": "dm"},
                        ]
                    )
                if exchange_tensor_view is not None:
                    annotated["physical_parameter_view"] = exchange_tensor_view
            elif block_type == "symmetric_exchange_matrix":
                annotated["physical_parameter_view"] = {
                    "view_kind": "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm",
                    "parameters": list(parameter_entries),
                    "physical_label": physical_view["physical_label"],
                }
            annotated["physical_label"] = physical_view["physical_label"]
            annotated["human_summary"] = summary
            annotated["human_parameters"] = parameter_entries
            dipole_view = _derive_dipole_multipole_physical_parameter_view(block.get("source_terms"))
            if dipole_view is not None:
                annotated["additional_physical_parameter_views"] = [dipole_view]
            return annotated

        diagonals = [
            (axis_labels[0], matrix[0][0]),
            (axis_labels[1], matrix[1][1]),
            (axis_labels[2], matrix[2][2]),
        ]
        offdiagonals = [
            ((axis_labels[0], axis_labels[1]), matrix[0][1], matrix[1][0]),
            ((axis_labels[0], axis_labels[2]), matrix[0][2], matrix[2][0]),
            ((axis_labels[1], axis_labels[2]), matrix[1][2], matrix[2][1]),
        ]
        parameter_entries = [
            {"name": _matrix_parameter_name(display_axis_label), "value": value, "kind": "diagonal"}
            for display_axis_label, (_axis_label, value) in zip(display_axis_labels, diagonals)
        ]
        nonzero_offdiag = []
        display_offdiag_axes = [
            (display_axis_labels[0], display_axis_labels[1]),
            (display_axis_labels[0], display_axis_labels[2]),
            (display_axis_labels[1], display_axis_labels[2]),
        ]
        for ((left_axis, right_axis), lhs, rhs), (display_left_axis, display_right_axis) in zip(offdiagonals, display_offdiag_axes):
            if lhs == 0.0 and rhs == 0.0:
                continue
            value = lhs if lhs == rhs else [lhs, rhs]
            is_symmetric_offdiagonal = block_type == "symmetric_exchange_matrix" and lhs == rhs
            name = (
                _gamma_parameter_name(display_left_axis, display_right_axis)
                if is_symmetric_offdiagonal
                else _matrix_parameter_name(display_left_axis, display_right_axis)
            )
            parameter_entries.append(
                {
                    "name": name,
                    "value": value,
                    "kind": "symmetric_offdiagonal" if is_symmetric_offdiagonal else "offdiagonal",
                }
            )
            nonzero_offdiag.append(((display_left_axis, display_right_axis), name, value))

        symmetric_matrix = list(block.get("symmetric_matrix") or matrix)
        symmetric_offdiagonal_parameters = _derive_symmetric_offdiagonal_parameters(
            symmetric_matrix,
            display_axis_labels,
        )
        if symmetric_offdiagonal_parameters:
            annotated["symmetric_offdiagonal_parameters"] = symmetric_offdiagonal_parameters
            existing_parameter_names = {entry.get("name") for entry in parameter_entries}
            for entry in symmetric_offdiagonal_parameters:
                if entry["name"] not in existing_parameter_names:
                    parameter_entries.append(entry)
        if symmetric_exchange_view is not None:
            existing_parameter_names = {entry.get("name") for entry in parameter_entries}
            for entry in symmetric_exchange_view["parameters"]:
                if entry["name"] not in existing_parameter_names:
                    parameter_entries.append(entry)

        diagonal_summary = ", ".join(
            f"{_matrix_parameter_name(display_axis_label)} = {_format_human_value(value)}"
            for display_axis_label, (_axis_label, value) in zip(display_axis_labels, diagonals)
        )
        summary = f"Exchange matrix on axes ({display_axis_labels[0]}, {display_axis_labels[1]}, {display_axis_labels[2]}) with {diagonal_summary}"
        if nonzero_offdiag:
            summary += " and off-diagonal "
            summary += ", ".join(
                f"{name} = {_format_human_value(value)}" for _axes, name, value in nonzero_offdiag
            )
        summary += "."
        if block_type == "symmetric_exchange_matrix":
            summary = "Symmetric " + summary[0].lower() + summary[1:]
        elif block_type == "exchange_tensor":
            dm_vector = list(block.get("dm_vector") or [0.0, 0.0, 0.0])
            isotropic_exchange = block.get("isotropic_exchange")
            if isotropic_exchange is not None:
                summary += (
                    f" Symmetric exchange decomposes into an isotropic part "
                    f"Jiso = {_format_human_value(isotropic_exchange)} plus anisotropic symmetric corrections."
                )
            if len(dm_vector) == 3:
                parameter_entries.extend(
                    [
                        {"name": "Jiso", "value": isotropic_exchange, "kind": "isotropic"}
                    ]
                    if isotropic_exchange is not None
                    else []
                )
                parameter_entries.extend(
                    [
                        {"name": "Dx", "value": dm_vector[0], "kind": "dm"},
                        {"name": "Dy", "value": dm_vector[1], "kind": "dm"},
                        {"name": "Dz", "value": dm_vector[2], "kind": "dm"},
                    ]
                )
                summary += (
                    f" DM = (Dx, Dy, Dz) = "
                    f"({_format_human_value(dm_vector[0])}, {_format_human_value(dm_vector[1])}, {_format_human_value(dm_vector[2])})."
                )
        if symmetric_offdiagonal_parameters:
            summary += " Symmetric off-diagonal exchange gives "
            summary += ", ".join(
                f"{entry['name']} = {_format_human_value(entry['value'])}"
                for entry in symmetric_offdiagonal_parameters
            )
            summary += "."
        dominant_axis = _dominant_axis_from_diagonal(
            list(zip(display_axis_labels, [value for _axis, value in diagonals]))
        )
        interpretation_bits = [f"Strongest along {dominant_axis}."]
        if nonzero_offdiag:
            interpretation_bits.append(
                ", ".join(
                    f"{_human_axis_token(left_axis).lower()}{_human_axis_token(right_axis).lower()} mixing present"
                    for (left_axis, right_axis), _name, _value in nonzero_offdiag
                ).capitalize()
                + "."
            )
        summary += " " + " ".join(interpretation_bits)
        annotated["human_summary"] = summary
        annotated["human_parameters"] = parameter_entries
        dipole_view = _derive_dipole_multipole_physical_parameter_view(block.get("source_terms"))
        if dipole_view is not None:
            annotated["additional_physical_parameter_views"] = [dipole_view]
        if symmetric_exchange_view is not None:
            annotated["physical_parameter_view"] = symmetric_exchange_view
        if exchange_tensor_view is not None:
            annotated["physical_parameter_view"] = exchange_tensor_view
        return annotated

    return annotated


def _coordinate_convention_for_family(coordinate_convention, family):
    convention = dict(coordinate_convention or {})
    if family is None:
        return convention
    overrides = dict(convention.get("family_overrides") or {})
    bond_overrides = dict(convention.get("bond_overrides") or {})
    merged = dict(convention)
    if family in bond_overrides:
        merged.update(dict(bond_overrides[family] or {}))
    if family in overrides:
        merged.update(dict(overrides[family] or {}))
    merged.pop("family_overrides", None)
    merged.pop("bond_overrides", None)
    return merged


def _annotate_block_with_coordinate_convention(block, coordinate_convention):
    convention = dict(coordinate_convention or {})
    frame = str(convention.get("frame") or "").strip()
    axis_labels = list(convention.get("axis_labels") or [])
    axis_mapping = dict(convention.get("axis_mapping") or {})
    resolved_frame = convention.get("resolved_frame")
    resolved_axis_labels = list(convention.get("resolved_axis_labels") or [])
    rotation_matrix = convention.get("rotation_matrix")
    quantization_axis = convention.get("quantization_axis")

    annotated = dict(block)
    if frame and frame != "unspecified":
        annotated["coordinate_frame"] = frame

    if len(axis_labels) != 3:
        return annotated

    if not resolved_axis_labels:
        resolved_axis_labels = [axis_mapping.get(axis) for axis in axis_labels]
    has_resolved_axes = bool(resolved_frame) and len(resolved_axis_labels) == 3 and all(
        label is not None for label in resolved_axis_labels
    )

    if block.get("type") == "xxz_exchange":
        annotated["axis_labels"] = list(axis_labels)
        annotated["planar_axes"] = list(axis_labels[:2])
        annotated["longitudinal_axis"] = quantization_axis or axis_labels[2]
        if frame == "global_crystallographic":
            annotated["display_axis_labels"] = ["x", "y", "z"]
            annotated["display_planar_axes"] = ["x", "y"]
            annotated["display_longitudinal_axis"] = "z"
            annotated["reference_axis_labels"] = list(axis_labels)
        if has_resolved_axes:
            annotated["resolved_coordinate_frame"] = resolved_frame
            annotated["resolved_axis_labels"] = list(resolved_axis_labels)
            annotated["resolved_planar_axes"] = list(resolved_axis_labels[:2])
            annotated["resolved_longitudinal_axis"] = quantization_axis or resolved_axis_labels[2]
    elif block.get("type") in {"symmetric_exchange_matrix", "exchange_tensor"}:
        annotated["axis_labels"] = list(axis_labels)
        annotated["matrix_axes"] = list(axis_labels)
        if frame == "global_crystallographic":
            annotated["display_axis_labels"] = ["x", "y", "z"]
            annotated["display_matrix_axes"] = ["x", "y", "z"]
            annotated["reference_axis_labels"] = list(axis_labels)
            annotated["reference_matrix_axes"] = list(axis_labels)
        if has_resolved_axes:
            annotated["resolved_coordinate_frame"] = resolved_frame
            annotated["resolved_axis_labels"] = list(resolved_axis_labels)
            annotated["resolved_matrix_axes"] = list(resolved_axis_labels)
            resolved_matrix = _rotate_exchange_matrix(block.get("matrix"), rotation_matrix)
            if resolved_matrix is not None:
                annotated["resolved_matrix"] = resolved_matrix

    return annotated


def identify_readable_blocks(canonical_model, coordinate_convention=None):
    two_body_terms = list(canonical_model.get("two_body", []))
    three_body_terms = list(canonical_model.get("three_body", []))

    blocks = []
    used = set()

    two_body_by_family = _group_terms_by_family(two_body_terms)
    three_body_by_family = _group_terms_by_family(three_body_terms)
    for family, family_two_body_terms in two_body_by_family.items():
        higher_blocks = _match_higher_multipole_coupling(family_two_body_terms)
        for block in higher_blocks:
            if family is not None:
                block["family"] = family
            _copy_shared_shell_metadata(block, block.get("source_terms", []))
            blocks.append(
                _annotate_block_for_humans(
                    _annotate_block_with_coordinate_convention(
                        block,
                        _coordinate_convention_for_family(coordinate_convention, family),
                    )
                )
            )
            used.update(id(term) for term in block["source_terms"])

        for matcher in (
            _match_isotropic_exchange,
            _match_xxz_exchange,
            _match_symmetric_exchange_matrix,
            _match_quadrupole_coupling,
            _match_pseudospin_exchange,
            _match_orbital_exchange,
            _match_dm_like,
            _match_exchange_tensor,
        ):
            block = matcher(family_two_body_terms)
            if block is not None:
                if family is not None:
                    block["family"] = family
                _copy_shared_shell_metadata(block, block.get("source_terms", []))
                blocks.append(
                    _annotate_block_for_humans(
                        _annotate_block_with_coordinate_convention(
                            block,
                            _coordinate_convention_for_family(coordinate_convention, family),
                        )
                    )
                )
                used.update(id(term) for term in block["source_terms"])

    for family, family_three_body_terms in three_body_by_family.items():
        chirality_block = _match_scalar_chirality(family_three_body_terms)
        if chirality_block is not None:
            if family is not None:
                chirality_block["family"] = family
            _copy_shared_shell_metadata(chirality_block, chirality_block.get("source_terms", []))
            blocks.append(
                _annotate_block_for_humans(
                    _annotate_block_with_coordinate_convention(
                        chirality_block,
                        _coordinate_convention_for_family(coordinate_convention, family),
                    )
                )
            )
            used.update(id(term) for term in chirality_block["source_terms"])

    residual_terms = []
    for family_key in ("one_body", "two_body", "three_body", "four_body", "higher_body"):
        for term in canonical_model.get(family_key, []):
            if id(term) not in used:
                residual_terms.append(term)

    return {"blocks": blocks, "residual_terms": residual_terms}


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(identify_readable_blocks(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
