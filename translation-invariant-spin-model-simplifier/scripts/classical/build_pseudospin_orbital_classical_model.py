#!/usr/bin/env python3
import math


def _complex_from_serialized(value):
    return complex(float(value["real"]), float(value["imag"]))


def _field_factors(local_label, site_role):
    spin_label, orbital_label = local_label.split("__", 1)
    factors = []
    if spin_label != "spin_I":
        factors.append(
            {
                "site_role": site_role,
                "field": "spin",
                "axis": spin_label.replace("spin_", "").lower(),
            }
        )
    if orbital_label != "orbital_I":
        axis = orbital_label.replace("orbital_", "").lower()
        factors.append(
            {
                "site_role": site_role,
                "field": "orbital",
                "axis": axis,
            }
        )
    return factors


def _vector_norm(vector):
    return math.sqrt(sum(float(component) * float(component) for component in vector))


def _cartesian_from_R(R, lattice_vectors):
    return [
        float(R[0]) * float(lattice_vectors[0][axis])
        + float(R[1]) * float(lattice_vectors[1][axis])
        + float(R[2]) * float(lattice_vectors[2][axis])
        for axis in range(3)
    ]


def build_pseudospin_orbital_classical_model(parsed_payload):
    inferred = parsed_payload.get("inferred", {})
    orbital_count = int(inferred.get("orbital_count", 0))
    if orbital_count != 2:
        raise ValueError("first classical bridge only supports orbital_count = 2")

    lattice_vectors = parsed_payload.get("structure", {}).get("lattice_vectors")
    if not lattice_vectors:
        raise ValueError("parsed payload must include structure.lattice_vectors")

    terms = []
    for block in parsed_payload.get("bond_blocks", []):
        displacement = _cartesian_from_R(block["R"], lattice_vectors)
        distance = _vector_norm(displacement)
        for item in block.get("coefficients", []):
            factors = _field_factors(item["left_label"], "left") + _field_factors(item["right_label"], "right")
            terms.append(
                {
                    "R": list(block["R"]),
                    "distance": float(distance),
                    "body_order": len(factors),
                    "left_label": item["left_label"],
                    "right_label": item["right_label"],
                    "coefficient": {
                        "real": float(item["coefficient"]["real"]),
                        "imag": float(item["coefficient"]["imag"]),
                    },
                    "coefficient_abs": float(abs(_complex_from_serialized(item["coefficient"]))),
                    "factors": factors,
                }
            )

    return {
        "model_type": "classical_pseudospin_orbital",
        "site_fields": ["spin", "orbital"],
        "orbital_count": orbital_count,
        "local_dimension": int(inferred.get("local_dimension", 0)),
        "basis_order": parsed_payload.get("basis_order"),
        "lattice_vectors": lattice_vectors,
        "positions": parsed_payload.get("structure", {}).get("positions", []),
        "bond_count": len(parsed_payload.get("bond_blocks", [])),
        "terms": terms,
    }
