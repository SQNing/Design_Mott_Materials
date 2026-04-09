#!/usr/bin/env python3
from common.bravais_kpaths import default_high_symmetry_path
from common.cpn_classical_state import resolve_cpn_classical_state_payload
from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
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
    resolved_state = resolve_cpn_classical_state_payload(classical_state)
    if not resolved_state:
        return None
    ordering = resolved_state.get("ordering")
    if isinstance(ordering, dict):
        summary = dict(ordering)
        q_vector = summary.get("q_vector")
        if q_vector is not None:
            summary["q_vector"] = [float(value) for value in q_vector]
        supercell_shape = summary.get("supercell_shape")
        if supercell_shape is not None:
            summary["supercell_shape"] = [int(value) for value in supercell_shape]
        ansatz = summary.get("ansatz")
        if ansatz is not None:
            summary["ansatz"] = str(ansatz)
        if summary.get("q_vector") is not None and summary.get("supercell_shape") is not None:
            summary.setdefault(
                "compatibility_with_supercell",
                _ordering_compatibility_with_supercell(summary["q_vector"], summary["supercell_shape"]),
            )
        return summary or None

    ansatz = resolved_state.get("ansatz")
    q_vector = resolved_state.get("q_vector")
    supercell_shape = resolved_state.get("supercell_shape")
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
    conventions = resolve_pseudospin_orbital_conventions(model)
    resolved_classical_state = resolve_cpn_classical_state_payload(classical_state)

    q_path_summary = _resolve_default_q_path(model)
    ordering = _ordering_summary(classical_state)

    payload = {
        "payload_version": 2,
        "backend": "Sunny.jl",
        "mode": "SUN",
        "payload_kind": "sun_gswt_prototype",
        "local_dimension": int(model["local_dimension"]),
        "orbital_count": int(model.get("orbital_count", 0)),
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
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
        "initial_local_rays": list(resolved_classical_state.get("local_rays", [])),
        "supercell_shape": list(resolved_classical_state.get("supercell_shape", [])),
        "classical_reference": {
            "state_kind": str(resolved_classical_state.get("state_kind", "local_rays")),
            "manifold": str(resolved_classical_state.get("manifold", model.get("classical_manifold", "CP^(N-1)"))),
            "frame_construction": "first-column-is-reference-ray",
            "schema_version": int(resolved_classical_state.get("schema_version", 1)),
        },
        "backend_requirements": {
            "sunny_sun_gswt": {
                "periodic_supercell_required": True,
                "single_crystallographic_site_per_cell_required": True,
            }
        },
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
