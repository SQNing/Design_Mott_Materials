#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _match_isotropic_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = ["Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"]
    if not all(label in labels for label in needed):
        return None
    coefficients = [labels[label]["coefficient"] for label in needed]
    if coefficients[0] == coefficients[1] == coefficients[2]:
        return {
            "type": "isotropic_exchange",
            "source_terms": [labels[label] for label in needed],
            "coefficient": coefficients[0],
        }
    return None


def _match_xxz_exchange(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    needed = ["Sx@0 Sx@1", "Sy@0 Sy@1", "Sz@0 Sz@1"]
    if not all(label in labels for label in needed):
        return None
    coefficient_xy = labels["Sx@0 Sx@1"]["coefficient"]
    coefficient_y = labels["Sy@0 Sy@1"]["coefficient"]
    coefficient_z = labels["Sz@0 Sz@1"]["coefficient"]
    if coefficient_xy != coefficient_y or coefficient_xy == coefficient_z:
        return None
    return {
        "type": "xxz_exchange",
        "source_terms": [labels[label] for label in needed],
        "coefficient_xy": coefficient_xy,
        "coefficient_z": coefficient_z,
    }


def _match_symmetric_exchange_matrix(two_body_terms):
    labels = {term["canonical_label"]: term for term in two_body_terms}
    diagonal = {
        "xx": labels.get("Sx@0 Sx@1"),
        "yy": labels.get("Sy@0 Sy@1"),
        "zz": labels.get("Sz@0 Sz@1"),
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

    return {
        "type": "symmetric_exchange_matrix",
        "source_terms": source_terms,
        "matrix": [
            [coefficient_x, offdiag["xy"], offdiag["xz"]],
            [offdiag["xy"], coefficient_y, offdiag["yz"]],
            [offdiag["xz"], offdiag["yz"], coefficient_z],
        ],
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
            label = f"S{row_axis}@0 S{col_axis}@1"
            term = labels.get(label)
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

    return {
        "type": "exchange_tensor",
        "source_terms": source_terms,
        "matrix": matrix,
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
    lhs = labels.get("Sx@0 Sy@1")
    rhs = labels.get("Sy@0 Sx@1")
    if lhs and rhs and lhs["coefficient"] == -rhs["coefficient"]:
        return {
            "type": "dm_like",
            "source_terms": [lhs, rhs],
            "coefficient": lhs["coefficient"],
        }
    return None


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
        if has_resolved_axes:
            annotated["resolved_coordinate_frame"] = resolved_frame
            annotated["resolved_axis_labels"] = list(resolved_axis_labels)
            annotated["resolved_planar_axes"] = list(resolved_axis_labels[:2])
            annotated["resolved_longitudinal_axis"] = quantization_axis or resolved_axis_labels[2]
    elif block.get("type") in {"symmetric_exchange_matrix", "exchange_tensor"}:
        annotated["axis_labels"] = list(axis_labels)
        annotated["matrix_axes"] = list(axis_labels)
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
        for matcher in (
            _match_isotropic_exchange,
            _match_xxz_exchange,
            _match_symmetric_exchange_matrix,
            _match_pseudospin_exchange,
            _match_orbital_exchange,
            _match_dm_like,
            _match_exchange_tensor,
        ):
            block = matcher(family_two_body_terms)
            if block is not None:
                if family is not None:
                    block["family"] = family
                blocks.append(
                    _annotate_block_with_coordinate_convention(
                        block,
                        _coordinate_convention_for_family(coordinate_convention, family),
                    )
                )
                used.update(id(term) for term in block["source_terms"])

    for family, family_three_body_terms in three_body_by_family.items():
        chirality_block = _match_scalar_chirality(family_three_body_terms)
        if chirality_block is not None:
            if family is not None:
                chirality_block["family"] = family
            blocks.append(
                _annotate_block_with_coordinate_convention(
                    chirality_block,
                    _coordinate_convention_for_family(coordinate_convention, family),
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
