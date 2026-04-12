#!/usr/bin/env python3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.bravais_kpaths import default_high_symmetry_path
from common.cpn_classical_state import resolve_cpn_classical_state_payload
from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
from lswt.build_lswt_payload import infer_spatial_dimension
from lswt.single_q_z_harmonic_adapter import build_single_q_z_harmonic_payload


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


def _resolve_pair_couplings(model):
    pair_couplings = model.get("pair_couplings")
    if isinstance(pair_couplings, list) and pair_couplings:
        return [
            {
                "R": [int(value) for value in coupling.get("R", [0, 0, 0])],
                "pair_matrix": coupling.get("pair_matrix"),
                "tensor_shape": list(coupling.get("tensor_shape", [])),
            }
            for coupling in pair_couplings
        ]

    bond_tensors = model.get("bond_tensors", [])
    couplings = []
    for bond in bond_tensors:
        pair_matrix = bond.get("pair_matrix")
        if pair_matrix is None:
            raise ValueError("bond_tensors[*].pair_matrix is required for python GLSWT payload construction")
        couplings.append(
            {
                "R": [int(value) for value in bond.get("R", [0, 0, 0])],
                "pair_matrix": pair_matrix,
                "tensor_shape": list(bond.get("tensor_shape", [])),
            }
        )
    if not couplings:
        raise ValueError("at least one pair coupling is required for python GLSWT payload construction")
    return couplings


def _resolve_default_q_path(model, supercell_shape):
    lattice = {
        "positions": model.get("positions", []),
        "lattice_vectors": model.get("lattice_vectors", []),
        "dimension": model.get("spatial_dimension"),
        "kind": model.get("lattice_kind", "generic"),
    }
    bonds = [{"vector": list(coupling.get("R", [0, 0, 0]))} for coupling in _resolve_pair_couplings(model)]
    spatial_dimension = infer_spatial_dimension(lattice, bonds)
    lattice_family, nodes = default_high_symmetry_path(lattice, spatial_dimension)
    q_path, node_indices = _interpolate_q_path(nodes["points"], samples_per_segment=int(model.get("q_samples", 32)))
    return {
        "spatial_dimension": spatial_dimension,
        "lattice_family": lattice_family,
        "magnetic_supercell_shape": [int(value) for value in supercell_shape],
        "q_path": q_path,
        "path": {"labels": list(nodes["labels"]), "node_indices": node_indices},
    }


def _resolve_q_path(model, supercell_shape):
    explicit_q_path = model.get("q_path")
    path_metadata = model.get("path")
    if explicit_q_path:
        q_path = [[float(value) for value in point] for point in explicit_q_path]
        labels = []
        node_indices = []
        if isinstance(path_metadata, dict):
            labels = [str(value) for value in path_metadata.get("labels", [])]
            node_indices = [int(value) for value in path_metadata.get("node_indices", [])]
        if not labels:
            labels = ["Q0", f"Q{len(q_path) - 1}"]
        if not node_indices:
            node_indices = [0, len(q_path) - 1]
        spatial_dimension = int(model.get("spatial_dimension", 0))
        if spatial_dimension <= 0:
            lattice = {
                "positions": model.get("positions", []),
                "lattice_vectors": model.get("lattice_vectors", []),
                "dimension": model.get("spatial_dimension"),
                "kind": model.get("lattice_kind", "generic"),
            }
            bonds = [{"vector": list(coupling.get("R", [0, 0, 0]))} for coupling in _resolve_pair_couplings(model)]
            spatial_dimension = infer_spatial_dimension(lattice, bonds)
        return {
            "spatial_dimension": spatial_dimension,
            "lattice_family": str(model.get("lattice_kind", "generic")),
            "magnetic_supercell_shape": [int(value) for value in supercell_shape],
            "q_path": q_path,
            "path": {"labels": labels, "node_indices": node_indices},
        }
    return _resolve_default_q_path(model, supercell_shape)


def build_python_glswt_payload(model, classical_state=None):
    if model.get("payload_kind") in {"python_glswt_local_rays", "python_glswt_single_q_z_harmonic"}:
        return dict(model)

    if model.get("classical_manifold") != "CP^(N-1)":
        raise ValueError("python GLSWT payload expects a CP^(N-1) classical model")

    conventions = resolve_pseudospin_orbital_conventions(model)
    source_state = classical_state if classical_state is not None else model
    resolved_state = resolve_cpn_classical_state_payload(source_state)
    pair_couplings = _resolve_pair_couplings(model)
    supercell_shape = resolved_state.get("supercell_shape", [1, 1, 1])
    q_path_summary = _resolve_q_path(model, supercell_shape)
    ordering = dict(resolved_state.get("ordering", {}))
    ansatz = str(ordering.get("ansatz", resolved_state.get("ansatz", "")))

    if ansatz == "single-q-unitary-ray":
        payload = build_single_q_z_harmonic_payload(
            model,
            classical_state=source_state,
            z_harmonic_cutoff=int(model.get("z_harmonic_cutoff", 1)),
            phase_grid_size=int(model.get("phase_grid_size", 64)),
            sideband_cutoff=int(model.get("sideband_cutoff", 2)),
        )
        payload.update(
            {
                "orbital_count": int(model.get("orbital_count", 0)),
                "basis_order": conventions["basis_order"],
                "pair_basis_order": conventions["pair_basis_order"],
                "local_basis_labels": list(model.get("local_basis_labels", [])),
                "lattice_vectors": list(model.get("lattice_vectors", [])),
                "positions": list(model.get("positions", [])),
                "pair_couplings": pair_couplings,
                "classical_reference": {
                    "state_kind": str(resolved_state.get("state_kind", "local_rays")),
                    "manifold": str(resolved_state.get("manifold", "CP^(N-1)")),
                    "frame_construction": "z-harmonic-reconstructed-ray",
                    "schema_version": int(resolved_state.get("schema_version", 1)),
                },
                "ordering": ordering,
                "spatial_dimension": int(q_path_summary["spatial_dimension"]),
                "q_path": q_path_summary["q_path"],
                "path": q_path_summary["path"],
                "z_harmonic_reference_mode": str(model.get("z_harmonic_reference_mode", "input")),
                "notes": {
                    "q_path_coordinates": "reduced coordinates of the crystallographic reciprocal basis",
                    "reference_state_scope": "single-q-z-harmonic-truncation",
                },
            }
        )
        return payload

    local_rays = list(resolved_state.get("local_rays", []))
    if not local_rays:
        raise ValueError("python GLSWT payload requires canonical classical_state.local_rays")

    if not resolved_state.get("supercell_shape"):
        raise ValueError("python GLSWT payload requires classical_state.supercell_shape")

    return {
        "payload_version": 1,
        "backend": "python",
        "mode": "GLSWT",
        "payload_kind": "python_glswt_local_rays",
        "local_dimension": int(model["local_dimension"]),
        "orbital_count": int(model.get("orbital_count", 0)),
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "local_basis_labels": list(model.get("local_basis_labels", [])),
        "lattice_vectors": list(model.get("lattice_vectors", [])),
        "positions": list(model.get("positions", [])),
        "pair_couplings": pair_couplings,
        "supercell_shape": [int(value) for value in supercell_shape],
        "initial_local_rays": local_rays,
        "classical_reference": {
            "state_kind": str(resolved_state.get("state_kind", "local_rays")),
            "manifold": str(resolved_state.get("manifold", "CP^(N-1)")),
            "frame_construction": "first-column-is-reference-ray",
            "schema_version": int(resolved_state.get("schema_version", 1)),
        },
        "ordering": dict(resolved_state.get("ordering", {})),
        "spatial_dimension": int(q_path_summary["spatial_dimension"]),
        "q_path": q_path_summary["q_path"],
        "path": q_path_summary["path"],
        "notes": {
            "q_path_coordinates": "reduced coordinates of the magnetic-supercell reciprocal basis",
            "reference_state_scope": "periodic-local-rays-only",
        },
    }
