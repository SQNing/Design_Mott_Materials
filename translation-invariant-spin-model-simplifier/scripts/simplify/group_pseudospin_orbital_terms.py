#!/usr/bin/env python3
import math


def _complex_from_serialized(value):
    return complex(float(value["real"]), float(value["imag"]))


def _vector_norm(vector):
    return math.sqrt(sum(float(component) * float(component) for component in vector))


def _cartesian_from_R(R, lattice_vectors):
    return [
        float(R[0]) * float(lattice_vectors[0][axis])
        + float(R[1]) * float(lattice_vectors[1][axis])
        + float(R[2]) * float(lattice_vectors[2][axis])
        for axis in range(3)
    ]


def _orbital_latex(label, site_index):
    if label == "orbital_I":
        return None
    if label == "orbital_X":
        return rf"\hat T_{{{site_index}}}^x"
    if label == "orbital_Y":
        return rf"\hat T_{{{site_index}}}^y"
    if label == "orbital_Z":
        return rf"\hat T_{{{site_index}}}^z"
    if label.startswith("orbital_SYM_"):
        left, right = label.replace("orbital_SYM_", "").split("_")
        return rf"\hat T_{{{site_index}}}^{{({left}{right},c)}}"
    if label.startswith("orbital_ASYM_"):
        left, right = label.replace("orbital_ASYM_", "").split("_")
        return rf"\hat T_{{{site_index}}}^{{({left}{right},s)}}"
    if label.startswith("orbital_DIAG_"):
        rank = label.replace("orbital_DIAG_", "")
        return rf"\hat T_{{{site_index}}}^{{(\mathrm{{diag}},{rank})}}"
    return rf"\hat T_{{{site_index}}}^{{({label})}}"


def _spin_latex(label, site_index):
    if label == "spin_I":
        return None
    axis = label.replace("spin_", "").lower()
    return rf"\hat S_{{{site_index}}}^{axis}"


def _local_factor_info(local_label, site_index):
    spin_label, orbital_label = local_label.split("__", 1)
    spin = _spin_latex(spin_label, site_index)
    orbital = _orbital_latex(orbital_label, site_index)
    factors = [item for item in (spin, orbital) if item is not None]
    local_kind = "I"
    if spin and orbital:
        local_kind = "ST"
    elif spin:
        local_kind = "S"
    elif orbital:
        local_kind = "T"
    return {
        "latex": " ".join(factors) if factors else rf"\hat I_{{{site_index}}}",
        "body_count": len(factors),
        "local_kind": local_kind,
        "orbital_label": orbital_label,
    }


def _family_name(left_kind, right_kind):
    pair = (left_kind, right_kind)
    if pair == ("I", "I"):
        return "constant"
    if pair in {("S", "I"), ("I", "S")}:
        return "one_body_spin"
    if pair in {("T", "I"), ("I", "T")}:
        return "one_body_orbital"
    if pair in {("ST", "I"), ("I", "ST")}:
        return "one_body_spin_orbital"
    if pair == ("S", "S"):
        return "two_body_spin_spin"
    if pair == ("T", "T"):
        return "two_body_orbital_orbital"
    if pair in {("S", "T"), ("T", "S")}:
        return "two_body_spin_orbital"
    if pair in {("ST", "S"), ("S", "ST")}:
        return "three_body_spin_spin_orbital"
    if pair in {("ST", "T"), ("T", "ST")}:
        return "three_body_spin_orbital_orbital"
    if pair == ("ST", "ST"):
        return "four_body_spin_orbital_mixed"
    return "residual"


def _residual_reason(left_info, right_info, coefficient_magnitude, threshold):
    if coefficient_magnitude < threshold:
        return "below_threshold"
    if left_info["orbital_label"].startswith("orbital_DIAG_") or right_info["orbital_label"].startswith("orbital_DIAG_"):
        return "unclassified_local_orbital_generator"
    return "rule_not_implemented"


def _serialize_coefficient(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _group_single_bond(block, lattice_vectors, significant_threshold):
    displacement = _cartesian_from_R(block["R"], lattice_vectors)
    distance = _vector_norm(displacement)
    grouped_terms = []
    residual_terms = []

    for item in block.get("coefficients", []):
        left_info = _local_factor_info(item["left_label"], 0)
        right_info = _local_factor_info(item["right_label"], 1)
        coefficient = _complex_from_serialized(item["coefficient"])
        family = _family_name(left_info["local_kind"], right_info["local_kind"])
        body_order = left_info["body_count"] + right_info["body_count"]
        latex_label = f"{left_info['latex']} {right_info['latex']}".strip()
        if left_info["orbital_label"].startswith("orbital_DIAG_") or right_info["orbital_label"].startswith("orbital_DIAG_"):
            family = "residual"

        entry = {
            "family": family,
            "body_order": body_order,
            "left_label": item["left_label"],
            "right_label": item["right_label"],
            "latex_label": latex_label,
            "coefficient": _serialize_coefficient(coefficient),
            "magnitude": float(abs(coefficient)),
        }

        if family == "residual" or abs(coefficient) < significant_threshold:
            entry["residual_reason"] = _residual_reason(left_info, right_info, abs(coefficient), significant_threshold)
            residual_terms.append(entry)
        else:
            grouped_terms.append(entry)

    return {
        "R": list(block["R"]),
        "distance": float(distance),
        "matrix_shape": list(block["matrix_shape"]),
        "grouped_terms": grouped_terms,
        "residual_terms": residual_terms,
    }


def group_pseudospin_orbital_terms(parsed_payload, significant_threshold=1e-4):
    lattice_vectors = parsed_payload.get("structure", {}).get("lattice_vectors")
    if not lattice_vectors:
        raise ValueError("parsed payload must include structure.lattice_vectors")

    bonds = [
        _group_single_bond(block, lattice_vectors, significant_threshold)
        for block in parsed_payload.get("bond_blocks", [])
    ]

    shells = {}
    for bond in bonds:
        key = round(bond["distance"], 10)
        shells.setdefault(
            key,
            {
                "distance": bond["distance"],
                "R_vectors": [],
                "bond_count": 0,
            },
        )
        shells[key]["R_vectors"].append(bond["R"])
        shells[key]["bond_count"] += 1

    distance_shells = []
    for index, key in enumerate(sorted(shells), start=1):
        item = shells[key]
        distance_shells.append(
            {
                "shell_index": index,
                "distance": item["distance"],
                "bond_count": item["bond_count"],
                "R_vectors": item["R_vectors"],
            }
        )

    return {
        "distance_shells": distance_shells,
        "bonds": bonds,
    }
