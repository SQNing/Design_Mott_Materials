#!/usr/bin/env python3
from common.bravais_kpaths import default_high_symmetry_path
from lswt.build_lswt_payload import infer_spatial_dimension


def _ordering_compatibility_with_supercell(q_vector, supercell_shape, *, tolerance=1e-8):
    axis_products = []
    commensurate = True
    for axis in range(3):
        q_component = float(q_vector[axis]) if axis < len(q_vector) else 0.0
        extent = int(supercell_shape[axis]) if axis < len(supercell_shape) else 1
        phase_winding = q_component * float(extent)
        nearest_integer = int(round(phase_winding))
        mismatch = phase_winding - float(nearest_integer)
        if abs(mismatch) > tolerance:
            commensurate = False
        axis_products.append(
            {
                "axis": int(axis),
                "q_component": q_component,
                "supercell_extent": extent,
                "phase_winding": phase_winding,
                "nearest_integer": nearest_integer,
                "mismatch": mismatch,
            }
        )
    return {
        "kind": "commensurate" if commensurate else "incommensurate",
        "tolerance": float(tolerance),
        "axis_products": axis_products,
    }


def _ordering_summary(classical_state):
    if not classical_state:
        return None
    ansatz = classical_state.get("ansatz")
    q_vector = classical_state.get("q_vector")
    supercell_shape = classical_state.get("supercell_shape")
    if ansatz is None and q_vector is None:
        return None

    ordering = {}
    if ansatz is not None:
        ordering["ansatz"] = str(ansatz)
    if q_vector is not None:
        ordering["q_vector"] = [float(value) for value in q_vector]
    if supercell_shape is not None:
        ordering["supercell_shape"] = [int(value) for value in supercell_shape]
    if q_vector is not None and supercell_shape is not None:
        ordering["compatibility_with_supercell"] = _ordering_compatibility_with_supercell(q_vector, supercell_shape)
    return ordering


def _interpolate_q_path(nodes, samples_per_segment):
    samples_per_segment = max(1, int(samples_per_segment))
    q_path = []
    node_indices = []
    for start_index in range(len(nodes) - 1):
        node_indices.append(len(q_path))
        start = nodes[start_index]
        end = nodes[start_index + 1]
        for step in range(samples_per_segment):
            weight = float(step) / float(samples_per_segment)
            q_path.append(
                [start[axis] * (1.0 - weight) + end[axis] * weight for axis in range(3)]
            )
    node_indices.append(len(q_path))
    q_path.append(list(nodes[-1]))
    return q_path, node_indices


def _resolve_default_q_path(model):
    lattice = {
        "positions": model.get("positions", []),
        "lattice_vectors": model.get("lattice_vectors", []),
        "dimension": model.get("spatial_dimension"),
        "kind": model.get("lattice_kind", "generic"),
    }
    bonds = [
        {"vector": list(bond.get("R", [0, 0, 0]))}
        for bond in model.get("bond_tensors", [])
    ]
    spatial_dimension = infer_spatial_dimension(lattice, bonds)
    _family, nodes = default_high_symmetry_path(lattice, spatial_dimension)
    q_path, node_indices = _interpolate_q_path(nodes["points"], samples_per_segment=32)
    return {"q_path": q_path, "path": {"labels": nodes["labels"], "node_indices": node_indices}}


def build_sun_gswt_payload(model, classical_state=None):
    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("Sunny GSWT payload expects a CP^(N-1) classical model")

    q_path_summary = _resolve_default_q_path(model)
    ordering = _ordering_summary(classical_state)

    payload = {
        "backend": "Sunny.jl",
        "mode": "SUN",
        "payload_kind": "sun_gswt_prototype",
        "local_dimension": int(model["local_dimension"]),
        "orbital_count": int(model.get("orbital_count", 0)),
        "pair_basis_order": model.get("pair_basis_order", "site_i_major_site_j_minor"),
        "local_basis_labels": list(model.get("local_basis_labels", [])),
        "lattice_vectors": model.get("lattice_vectors", []),
        "positions": model.get("positions", []),
        "pair_couplings": [
            {
                "R": list(bond["R"]),
                "pair_matrix": bond.get("pair_matrix"),
                "tensor_shape": list(bond.get("tensor_shape", [])),
            }
            for bond in model.get("bond_tensors", [])
        ],
        "initial_local_rays": list(classical_state.get("local_rays", [])) if classical_state else [],
        "supercell_shape": list(classical_state.get("supercell_shape", [])) if classical_state else [],
        "q_path": q_path_summary["q_path"],
        "path": q_path_summary["path"],
        "capabilities": {
            "spin_wave": "prototype",
            "monte_carlo": "prototype",
            "observables": "adapter-required",
        },
        "notes": {
            "local_variable": "coherent_state_ray",
            "manifold": "CP^(N-1)",
            "status": "prototype-adapter-payload",
        },
    }
    if ordering is not None:
        payload["ordering"] = ordering
    return payload
