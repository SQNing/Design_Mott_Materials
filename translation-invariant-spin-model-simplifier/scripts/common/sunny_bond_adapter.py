#!/usr/bin/env python3

from copy import deepcopy
import math

import numpy as np


def adapt_model_for_sunny_pair_couplings(model):
    adapted = deepcopy(model)
    bond_tensors = list(adapted.get("bond_tensors", []))
    if not bond_tensors:
        adapted["sunny_adapter"] = {
            "applied": True,
            "method": "aggregate-directed-bonds-into-undirected-representatives",
            "input_directed_bond_count": 0,
            "output_undirected_bond_count": 0,
        }
        return adapted

    local_dimension = _resolve_local_dimension(adapted, bond_tensors)
    grouped = {}
    for bond in bond_tensors:
        grouped.setdefault(_undirected_bond_key(bond), []).append(bond)

    aggregated = []
    for _, members in sorted(grouped.items(), key=lambda item: item[0]):
        canonical = deepcopy(min(members, key=_directed_bond_sort_key))
        canonical_source = int(canonical.get("source", 0))
        canonical_target = int(canonical.get("target", 0))
        canonical_R = tuple(int(value) for value in canonical.get("R", [0, 0, 0]))

        pair_matrix_sum = None
        tensor_sum = None

        for member in members:
            member_source = int(member.get("source", 0))
            member_target = int(member.get("target", 0))
            member_R = tuple(int(value) for value in member.get("R", [0, 0, 0]))
            requires_swap = (member_source, member_target, member_R) != (
                canonical_source,
                canonical_target,
                canonical_R,
            )

            pair_matrix = member.get("pair_matrix")
            if pair_matrix is not None:
                matrix = _deserialize_pair_matrix(pair_matrix)
                if requires_swap:
                    matrix = _swap_pair_matrix_orientation(matrix, local_dimension)
                pair_matrix_sum = matrix if pair_matrix_sum is None else pair_matrix_sum + matrix

            tensor = member.get("tensor")
            if tensor is not None:
                tensor_array = _deserialize_tensor(tensor)
                if requires_swap:
                    tensor_array = tensor_array.transpose(2, 3, 0, 1)
                tensor_sum = tensor_array if tensor_sum is None else tensor_sum + tensor_array

        if pair_matrix_sum is not None:
            canonical["pair_matrix"] = _serialize_pair_matrix(pair_matrix_sum)
        if tensor_sum is not None:
            canonical["tensor"] = _serialize_tensor(tensor_sum)
            canonical["tensor_shape"] = [int(value) for value in tensor_sum.shape]
        aggregated.append(canonical)

    adapted["bond_tensors"] = aggregated
    adapted["bond_count"] = len(aggregated)
    adapted["sunny_adapter"] = {
        "applied": True,
        "method": "aggregate-directed-bonds-into-undirected-representatives",
        "input_directed_bond_count": len(bond_tensors),
        "output_undirected_bond_count": len(aggregated),
    }
    return adapted


def _directed_bond_sort_key(bond):
    return (
        int(bond.get("source", 0)),
        int(bond.get("target", 0)),
        tuple(int(value) for value in bond.get("R", [0, 0, 0])),
    )


def _undirected_bond_key(bond):
    source = int(bond.get("source", 0))
    target = int(bond.get("target", 0))
    R = tuple(int(value) for value in bond.get("R", [0, 0, 0]))
    reverse = (target, source, tuple(-value for value in R))
    return min((source, target, R), reverse)


def _resolve_local_dimension(model, bond_tensors):
    local_dimension = int(model.get("local_dimension", 0))
    if local_dimension > 0:
        return local_dimension

    for bond in bond_tensors:
        shape = bond.get("tensor_shape", [])
        if len(shape) == 4 and int(shape[0]) > 0:
            return int(shape[0])
        pair_matrix = bond.get("pair_matrix")
        if isinstance(pair_matrix, list) and pair_matrix:
            inferred = int(round(math.sqrt(len(pair_matrix))))
            if inferred * inferred == len(pair_matrix):
                return inferred

    raise ValueError("Sunny bond adapter requires model.local_dimension or bond tensor metadata")


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _deserialize_pair_matrix(rows):
    return np.array([[_complex_from_serialized(value) for value in row] for row in rows], dtype=complex)


def _serialize_pair_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in np.asarray(matrix)]


def _deserialize_tensor(serialized):
    local_dimension = len(serialized)
    tensor = np.zeros((local_dimension, local_dimension, local_dimension, local_dimension), dtype=complex)
    for a in range(local_dimension):
        for b in range(local_dimension):
            for c in range(local_dimension):
                for d in range(local_dimension):
                    tensor[a, b, c, d] = _complex_from_serialized(serialized[a][b][c][d])
    return tensor


def _serialize_tensor(tensor):
    local_dimension = int(tensor.shape[0])
    serialized = []
    for a in range(local_dimension):
        block_a = []
        for b in range(local_dimension):
            block_b = []
            for c in range(local_dimension):
                block_c = []
                for d in range(local_dimension):
                    block_c.append(_serialize_complex(tensor[a, b, c, d]))
                block_b.append(block_c)
            block_a.append(block_b)
        serialized.append(block_a)
    return serialized


def _swap_pair_matrix_orientation(matrix, local_dimension):
    permutation = []
    for left_index in range(local_dimension):
        for right_index in range(local_dimension):
            permutation.append(right_index * local_dimension + left_index)
    swap = np.zeros((local_dimension * local_dimension, local_dimension * local_dimension), dtype=complex)
    for source_index, target_index in enumerate(permutation):
        swap[target_index, source_index] = 1.0
    return swap @ matrix @ swap.T
