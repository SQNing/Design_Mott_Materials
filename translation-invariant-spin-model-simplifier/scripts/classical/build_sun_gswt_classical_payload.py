#!/usr/bin/env python3
import math


def _complex_from_serialized(value):
    return complex(float(value["real"]), float(value["imag"]))


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _vector_norm(vector):
    return math.sqrt(sum(float(component) * float(component) for component in vector))


def _cartesian_from_R(R, lattice_vectors):
    return [
        float(R[0]) * float(lattice_vectors[0][axis])
        + float(R[1]) * float(lattice_vectors[1][axis])
        + float(R[2]) * float(lattice_vectors[2][axis])
        for axis in range(3)
    ]


def _deserialize_pair_matrix(serialized):
    return [[_complex_from_serialized(value) for value in row] for row in serialized]


def _pair_matrix_to_tensor(pair_matrix, local_dimension):
    tensor = []
    for left_a in range(local_dimension):
        left_block = []
        for right_b in range(local_dimension):
            row_index = left_a * local_dimension + right_b
            bra_block = []
            for left_c in range(local_dimension):
                ket_block = []
                for right_d in range(local_dimension):
                    col_index = left_c * local_dimension + right_d
                    ket_block.append(_serialize_complex(pair_matrix[row_index][col_index]))
                bra_block.append(ket_block)
            left_block.append(bra_block)
        tensor.append(left_block)
    return tensor


def build_sun_gswt_classical_payload(parsed_payload):
    if parsed_payload.get("input_mode") != "many_body_hr":
        raise ValueError("sun-gswt classical payload currently expects input_mode = many_body_hr")

    inferred = parsed_payload.get("inferred", {})
    local_dimension = int(inferred.get("local_dimension", 0))
    orbital_count = int(inferred.get("orbital_count", 0))
    if local_dimension <= 0:
        raise ValueError("parsed payload must include inferred.local_dimension")

    lattice_vectors = parsed_payload.get("structure", {}).get("lattice_vectors")
    if not lattice_vectors:
        raise ValueError("parsed payload must include structure.lattice_vectors")

    local_basis_labels = parsed_payload.get("local_basis_labels")
    if not local_basis_labels:
        raise ValueError("parsed payload must include local_basis_labels")

    bond_tensors = []
    for block in parsed_payload.get("bond_blocks", []):
        pair_matrix_serialized = block.get("pair_matrix")
        if pair_matrix_serialized is None:
            raise ValueError("parsed payload must include bond_blocks[*].pair_matrix for GSWT classical payloads")
        pair_matrix = _deserialize_pair_matrix(pair_matrix_serialized)
        displacement = _cartesian_from_R(block["R"], lattice_vectors)
        distance = _vector_norm(displacement)
        bond_tensors.append(
            {
                "R": list(block["R"]),
                "distance": float(distance),
                "matrix_shape": list(block["matrix_shape"]),
                "tensor_shape": [local_dimension, local_dimension, local_dimension, local_dimension],
                "tensor": _pair_matrix_to_tensor(pair_matrix, local_dimension),
                "pair_matrix": pair_matrix_serialized,
            }
        )

    return {
        "model_type": "sun_gswt_classical",
        "input_mode": parsed_payload.get("input_mode"),
        "classical_manifold": "CP^(N-1)",
        "basis_semantics": dict(parsed_payload.get("basis_semantics", {})),
        "basis_order": parsed_payload.get("basis_order"),
        "pair_basis_order": parsed_payload.get("pair_basis_order", "site_i_major_site_j_minor"),
        "local_dimension": local_dimension,
        "orbital_count": orbital_count,
        "local_basis_labels": list(local_basis_labels),
        "positions": parsed_payload.get("structure", {}).get("positions", []),
        "lattice_vectors": lattice_vectors,
        "bond_count": len(bond_tensors),
        "bond_tensors": bond_tensors,
    }
