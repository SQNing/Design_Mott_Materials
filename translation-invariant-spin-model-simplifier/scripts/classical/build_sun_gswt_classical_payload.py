#!/usr/bin/env python3
import math

from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions


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
    for left_bra in range(local_dimension):
        left_block = []
        for left_ket in range(local_dimension):
            bra_block = []
            for right_bra in range(local_dimension):
                row_index = left_bra * local_dimension + right_bra
                ket_block = []
                for right_ket in range(local_dimension):
                    col_index = left_ket * local_dimension + right_ket
                    ket_block.append(_serialize_complex(pair_matrix[row_index][col_index]))
                bra_block.append(ket_block)
            left_block.append(bra_block)
        tensor.append(left_block)
    return tensor


def build_sun_gswt_classical_payload(parsed_payload):
    if parsed_payload.get("input_mode") != "many_body_hr":
        raise ValueError("sun-gswt classical payload currently expects input_mode = many_body_hr")
    conventions = resolve_pseudospin_orbital_conventions(parsed_payload, require_local_space=True)

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

    magnetic_site_count = int(parsed_payload.get("magnetic_site_count", 1))
    magnetic_sites = parsed_payload.get("magnetic_sites")
    if not magnetic_sites:
        magnetic_sites = [
            {
                "index": 0,
                "label": "site0",
                "position": None,
                "kind": "assumed-single-sublattice",
            }
        ]
    magnetic_site_metadata = dict(parsed_payload.get("magnetic_site_metadata", {}))
    if not magnetic_site_metadata:
        magnetic_site_metadata = {
            "site_pair_encoding": "assumed-single-sublattice-many_body_hr",
        }

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
                "source": int(block.get("source", 0)),
                "target": int(block.get("target", 0)),
                "distance": float(distance),
                "matrix_shape": list(block["matrix_shape"]),
                "tensor_shape": [local_dimension, local_dimension, local_dimension, local_dimension],
                "tensor": _pair_matrix_to_tensor(pair_matrix, local_dimension),
                "pair_matrix": pair_matrix_serialized,
            }
        )

    return {
        "model_version": 2,
        "model_type": "sun_gswt_classical",
        "input_mode": parsed_payload.get("input_mode"),
        "classical_manifold": "CP^(N-1)",
        "classical_variable": "local_ray",
        "classical_constraints": "normalized_ray_mod_u1",
        "basis_semantics": dict(parsed_payload.get("basis_semantics", {})),
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "local_dimension": local_dimension,
        "orbital_count": orbital_count,
        "local_basis_labels": list(local_basis_labels),
        "magnetic_site_count": int(magnetic_site_count),
        "magnetic_sites": list(magnetic_sites),
        "magnetic_site_metadata": dict(magnetic_site_metadata),
        "retained_local_space": dict(parsed_payload.get("retained_local_space", {})),
        "pair_operator_convention": dict(parsed_payload.get("pair_operator_convention", {})),
        "operator_dictionary": dict(parsed_payload.get("operator_dictionary", {})),
        "positions": parsed_payload.get("structure", {}).get("positions", []),
        "lattice_vectors": lattice_vectors,
        "bond_count": len(bond_tensors),
        "bond_tensors": bond_tensors,
        "backend_requirements": {
            "sunny_sun_classical": {
                "periodic_supercell_required": True,
                "single_crystallographic_site_per_cell_required": True,
            },
            "sunny_sun_gswt": {
                "periodic_supercell_required": True,
                "single_crystallographic_site_per_cell_required": True,
            },
        },
    }
