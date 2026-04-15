#!/usr/bin/env python3
import math


def _complex_from_serialized(value):
    return complex(float(value["real"]), float(value["imag"]))


def _serialize_coefficient(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _serialize_nested_coefficients(value):
    if isinstance(value, dict):
        return {key: _serialize_nested_coefficients(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_nested_coefficients(item) for item in value]
    if isinstance(value, complex):
        return _serialize_coefficient(value)
    if isinstance(value, (int, float)):
        return _serialize_coefficient(complex(float(value), 0.0))
    return value


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


def _spin_axis(label):
    if label == "spin_I":
        return None
    return label.replace("spin_", "").lower()


def _orbital_axis(label, orbital_count):
    if label == "orbital_I":
        return None
    if orbital_count == 2 and label in {"orbital_X", "orbital_Y", "orbital_Z"}:
        return label.replace("orbital_", "").lower()
    return label


def _local_factor_info(local_label, site_index, orbital_count):
    if "__" not in local_label:
        if local_label == "multiplet_I":
            return {
                "latex": rf"\hat I_{{{site_index}}}",
                "body_count": 0,
                "local_kind": "I",
                "spin_label": None,
                "orbital_label": None,
                "spin_axis": None,
                "orbital_axis": None,
                "generic_label": local_label,
            }
        return {
            "latex": rf"\hat \Lambda_{{{site_index}}}^{{({local_label})}}",
            "body_count": 1,
            "local_kind": "L",
            "spin_label": None,
            "orbital_label": None,
            "spin_axis": None,
            "orbital_axis": None,
            "generic_label": local_label,
        }

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
        "spin_label": spin_label,
        "orbital_label": orbital_label,
        "spin_axis": _spin_axis(spin_label),
        "orbital_axis": _orbital_axis(orbital_label, orbital_count),
        "generic_label": None,
    }


def _family_name(left_kind, right_kind):
    pair = (left_kind, right_kind)
    if pair == ("I", "I"):
        return "constant"
    if pair in {("L", "I"), ("I", "L")}:
        return "one_body_local_generator"
    if pair == ("L", "L"):
        return "two_body_local_generator"
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
    if pair in {("ST", "S"), ("S", "ST"), ("ST", "T"), ("T", "ST")}:
        return "three_body"
    if pair == ("ST", "ST"):
        return "four_body_spin_orbital_mixed"
    return "residual"


def _residual_reason(left_info, right_info, coefficient_magnitude, threshold):
    if coefficient_magnitude < threshold:
        return "below_threshold"
    left_orbital_label = left_info.get("orbital_label") or ""
    right_orbital_label = right_info.get("orbital_label") or ""
    if left_orbital_label.startswith("orbital_DIAG_") or right_orbital_label.startswith("orbital_DIAG_"):
        return "unclassified_local_orbital_generator"
    return "rule_not_implemented"


def _new_kugel_khomskii_bucket():
    return {
        "constant": 0.0 + 0.0j,
        "spin_fields": {
            "left": {},
            "right": {},
            "symmetric": {},
            "antisymmetric": {},
        },
        "orbital_fields": {
            "left": {},
            "right": {},
            "symmetric": {},
            "antisymmetric": {},
        },
        "spin_exchange": {},
        "orbital_exchange": {},
        "quartic_exchange": {},
        "additional_channels": {
            "one_body_spin_orbital": [],
            "crossed_spin_orbital": [],
            "three_body": [],
        },
    }


def _accumulate(mapping, key, value):
    mapping[key] = mapping.get(key, 0.0 + 0.0j) + value


def _accumulate_nested(mapping, keys, value):
    current = mapping
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = current.get(keys[-1], 0.0 + 0.0j) + value


def _populate_kugel_khomskii(entry, left_info, right_info, coefficient, orbital_count, bucket):
    if orbital_count != 2:
        return

    family = entry["family"]
    if family == "constant":
        bucket["constant"] += coefficient
        return

    if family == "one_body_spin":
        target = "left" if left_info["local_kind"] == "S" else "right"
        axis = left_info["spin_axis"] if left_info["local_kind"] == "S" else right_info["spin_axis"]
        _accumulate(bucket["spin_fields"][target], axis, coefficient)
        return

    if family == "one_body_orbital":
        target = "left" if left_info["local_kind"] == "T" else "right"
        axis = left_info["orbital_axis"] if left_info["local_kind"] == "T" else right_info["orbital_axis"]
        _accumulate(bucket["orbital_fields"][target], axis, coefficient)
        return

    if family == "two_body_spin_spin":
        _accumulate_nested(bucket["spin_exchange"], [left_info["spin_axis"], right_info["spin_axis"]], coefficient)
        return

    if family == "two_body_orbital_orbital":
        _accumulate_nested(
            bucket["orbital_exchange"],
            [left_info["orbital_axis"], right_info["orbital_axis"]],
            coefficient,
        )
        return

    if family == "four_body_spin_orbital_mixed":
        _accumulate_nested(
            bucket["quartic_exchange"],
            [
                left_info["spin_axis"],
                right_info["spin_axis"],
                left_info["orbital_axis"],
                right_info["orbital_axis"],
            ],
            coefficient,
        )
        return

    if family == "one_body_spin_orbital":
        bucket["additional_channels"]["one_body_spin_orbital"].append(
            {
                "site": "left" if left_info["local_kind"] == "ST" else "right",
                "spin_axis": left_info["spin_axis"] or right_info["spin_axis"],
                "orbital_axis": left_info["orbital_axis"] or right_info["orbital_axis"],
                "latex_label": entry["latex_label"],
                "coefficient": coefficient,
            }
        )
        return

    if family == "two_body_spin_orbital":
        bucket["additional_channels"]["crossed_spin_orbital"].append(
            {
                "left_kind": left_info["local_kind"],
                "right_kind": right_info["local_kind"],
                "latex_label": entry["latex_label"],
                "coefficient": coefficient,
            }
        )
        return

    if family == "three_body":
        bucket["additional_channels"]["three_body"].append(
            {
                "left_kind": left_info["local_kind"],
                "right_kind": right_info["local_kind"],
                "latex_label": entry["latex_label"],
                "coefficient": coefficient,
            }
        )


def _finalize_kugel_khomskii(bucket):
    for axis in sorted(set(bucket["spin_fields"]["left"]) | set(bucket["spin_fields"]["right"])):
        left = bucket["spin_fields"]["left"].get(axis, 0.0 + 0.0j)
        right = bucket["spin_fields"]["right"].get(axis, 0.0 + 0.0j)
        bucket["spin_fields"]["symmetric"][axis] = 0.5 * (left + right)
        bucket["spin_fields"]["antisymmetric"][axis] = 0.5 * (left - right)

    for axis in sorted(set(bucket["orbital_fields"]["left"]) | set(bucket["orbital_fields"]["right"])):
        left = bucket["orbital_fields"]["left"].get(axis, 0.0 + 0.0j)
        right = bucket["orbital_fields"]["right"].get(axis, 0.0 + 0.0j)
        bucket["orbital_fields"]["symmetric"][axis] = 0.5 * (left + right)
        bucket["orbital_fields"]["antisymmetric"][axis] = 0.5 * (left - right)

    return _serialize_nested_coefficients(bucket)


def _group_single_bond(block, lattice_vectors, orbital_count, significant_threshold, factorization_kind):
    displacement = _cartesian_from_R(block["R"], lattice_vectors)
    distance = _vector_norm(displacement)
    grouped_terms = []
    residual_terms = []
    kugel_khomskii = (
        _new_kugel_khomskii_bucket() if factorization_kind == "orbital_times_spin" and orbital_count == 2 else None
    )

    for item in block.get("coefficients", []):
        left_info = _local_factor_info(item["left_label"], 0, orbital_count)
        right_info = _local_factor_info(item["right_label"], 1, orbital_count)
        coefficient = _complex_from_serialized(item["coefficient"])
        family = _family_name(left_info["local_kind"], right_info["local_kind"])
        body_order = left_info["body_count"] + right_info["body_count"]
        latex_label = f"{left_info['latex']} {right_info['latex']}".strip()
        left_orbital_label = left_info.get("orbital_label") or ""
        right_orbital_label = right_info.get("orbital_label") or ""
        if left_orbital_label.startswith("orbital_DIAG_") or right_orbital_label.startswith("orbital_DIAG_"):
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
            continue

        grouped_terms.append(entry)
        if kugel_khomskii is not None:
            _populate_kugel_khomskii(entry, left_info, right_info, coefficient, orbital_count, kugel_khomskii)

    result = {
        "R": list(block["R"]),
        "distance": float(distance),
        "matrix_shape": list(block["matrix_shape"]),
        "grouped_terms": grouped_terms,
        "residual_terms": residual_terms,
    }
    if kugel_khomskii is not None:
        result["kugel_khomskii"] = _finalize_kugel_khomskii(kugel_khomskii)
    return result


def group_pseudospin_orbital_terms(parsed_payload, significant_threshold=1e-4):
    lattice_vectors = parsed_payload.get("structure", {}).get("lattice_vectors")
    if not lattice_vectors:
        raise ValueError("parsed payload must include structure.lattice_vectors")

    factorization = parsed_payload.get("retained_local_space", {}).get("factorization", {})
    factorization_kind = str(factorization.get("kind") or "orbital_times_spin")
    orbital_count = int(parsed_payload.get("inferred", {}).get("orbital_count", 0))
    bonds = [
        _group_single_bond(block, lattice_vectors, orbital_count, significant_threshold, factorization_kind)
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
