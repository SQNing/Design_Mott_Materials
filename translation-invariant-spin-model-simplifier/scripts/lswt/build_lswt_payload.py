#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.bravais_kpaths import default_high_symmetry_path
from common.classical_contract_resolution import get_classical_ordering, get_standardized_classical_state
from common.cpn_classical_state import has_spin_frame_classical_state, is_cpn_local_ray_classical_state
from common.lattice_geometry import (
    build_isotropic_heisenberg_bonds_from_parameters,
    lattice_vector_rank,
    resolve_lattice_vectors,
)
from common.quadratic_phase_dressing import resolve_quadratic_phase_dressing
from common.rotating_frame_metadata import resolve_rotating_frame_transform
from common.rotating_frame_realization import resolve_rotating_frame_realization


def _error(code, message):
    return {"status": "error", "error": {"code": code, "message": message}}


def _get_classical_state(model):
    return get_standardized_classical_state(model, prefer_nested_legacy=True)


def _vector_norm(vector):
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _active_axes_from_positions(positions, tolerance=1e-9):
    if not positions:
        return [False, False, False]
    active = [False, False, False]
    for axis in range(3):
        values = [float(position[axis]) if axis < len(position) else 0.0 for position in positions]
        if max(values) - min(values) > tolerance:
            active[axis] = True
    return active


def _dimension_hint_from_lattice_kind(lattice):
    kind = str(lattice.get("kind", "")).lower()
    if any(token in kind for token in {"chain", "1d"}):
        return 1
    if any(token in kind for token in {"square", "rect", "triang", "honeycomb", "kagome", "2d"}):
        return 2
    if any(token in kind for token in {"cubic", "orthorhombic", "tetragonal", "hexagonal", "3d"}):
        return 3
    return 0


def infer_spatial_dimension(lattice, bonds):
    active_axes = _active_axes_from_positions(lattice.get("positions") or [])
    for bond in bonds:
        vector = bond.get("vector", [])
        for axis in range(min(3, len(vector))):
            if abs(float(vector[axis])) > 1e-9:
                active_axes[axis] = True

    active_dimension = 0
    for axis, is_active in enumerate(active_axes):
        if is_active:
            active_dimension = axis + 1

    kind_dimension = _dimension_hint_from_lattice_kind(lattice)
    if active_dimension > 0:
        if kind_dimension > 0:
            return max(active_dimension, kind_dimension)
        explicit_dimension = lattice.get("dimension")
        if isinstance(explicit_dimension, int) and explicit_dimension > 0:
            return max(active_dimension, explicit_dimension)
        return active_dimension

    explicit_dimension = lattice.get("dimension")
    if isinstance(explicit_dimension, int) and explicit_dimension > 0:
        return explicit_dimension

    if kind_dimension > 0:
        return kind_dimension
    rank_dimension = lattice_vector_rank(lattice)
    if rank_dimension > 0:
        return rank_dimension
    return 1


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


def _points_match(left, right, tolerance=1e-9):
    if len(left) != len(right):
        return False
    for left_point, right_point in zip(left, right):
        if len(left_point) != len(right_point):
            return False
        for left_value, right_value in zip(left_point, right_point):
            if abs(float(left_value) - float(right_value)) > tolerance:
                return False
    return True


def _resolve_q_path(model, lattice, bonds):
    spatial_dimension = infer_spatial_dimension(lattice, bonds)
    q_samples = int(model.get("q_samples", 32))
    explicit_q_path = model.get("q_path", [])
    lattice_family, nodes = default_high_symmetry_path(lattice, spatial_dimension)
    if explicit_q_path:
        if len(explicit_q_path) <= 10:
            q_path, node_indices = _interpolate_q_path(explicit_q_path, samples_per_segment=q_samples)
            explicit_labels = model.get("q_path_labels", [])
            if explicit_labels and len(explicit_labels) == len(explicit_q_path):
                labels = list(explicit_labels)
            elif _points_match(explicit_q_path, nodes["points"]):
                labels = nodes["labels"]
            else:
                labels = [f"Q{index}" for index in range(len(explicit_q_path))]
        else:
            q_path = explicit_q_path
            step = max(1, len(explicit_q_path) - 1)
            node_indices = [0, step]
            labels = ["Q0", "Q1"]
    else:
        q_path, node_indices = _interpolate_q_path(nodes["points"], samples_per_segment=q_samples)
        labels = nodes["labels"]

    return {
        "spatial_dimension": spatial_dimension,
        "lattice_family": lattice_family,
        "q_path": q_path,
        "path": {"labels": labels, "node_indices": node_indices},
    }


def normalize_exchange_matrix(term):
    matrix = term.get("matrix")
    if not isinstance(matrix, list) or len(matrix) != 3:
        raise ValueError("bond matrix must be a 3x3 list")
    normalized = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("bond matrix must be a 3x3 list")
        normalized.append([float(value) for value in row])
    return normalized


def build_reference_frames(classical_state):
    frames = classical_state.get("site_frames", [])
    if not frames:
        raise ValueError("classical_state.site_frames is required")
    return [
        {
            "site": int(frame["site"]),
            "spin_length": float(frame["spin_length"]),
            "direction": [float(value) for value in frame["direction"]],
        }
        for frame in frames
    ]


def validate_lswt_scope(model):
    simplified_model = model.get("simplified_model", {})
    if simplified_model.get("three_body_terms"):
        return _error("unsupported-model-scope", "higher-body terms are outside first-stage Sunny-backed LSWT scope")
    bonds = simplified_model.get("bonds", model.get("bonds", []))
    if not bonds and simplified_model.get("template") == "heisenberg":
        exchange_mapping = model.get("exchange_mapping", {})
        bonds, _shell_map = build_isotropic_heisenberg_bonds_from_parameters(
            model.get("lattice", {}),
            model.get("parameters", {}),
            shell_map_override=exchange_mapping.get("shell_map", {}),
        )
    if not bonds:
        return _error("unsupported-model-scope", "at least one bilinear bond is required for LSWT payload construction")
    classical_state = _get_classical_state(model)
    if not classical_state:
        return _error("invalid-classical-reference-state", "classical_state is required to build an LSWT payload")
    if is_cpn_local_ray_classical_state(classical_state):
        return _error(
            "invalid-classical-reference-state",
            "spin-only Sunny LSWT requires classical_state.site_frames; CP^(N-1) local-ray classical states should use the pseudospin-orbital SUN/GSWT path instead",
        )
    if not has_spin_frame_classical_state(classical_state):
        return _error(
            "invalid-classical-reference-state",
            "spin-only Sunny LSWT requires classical_state.site_frames",
        )
    return None


def build_lswt_payload(model):
    scope_error = validate_lswt_scope(model)
    if scope_error is not None:
        return scope_error

    simplified_model = model.get("simplified_model", {})
    shell_map = {}
    bonds = simplified_model.get("bonds", model.get("bonds", []))
    if not bonds and simplified_model.get("template") == "heisenberg":
        exchange_mapping = model.get("exchange_mapping", {})
        bonds, shell_map = build_isotropic_heisenberg_bonds_from_parameters(
            model.get("lattice", {}),
            model.get("parameters", {}),
            shell_map_override=exchange_mapping.get("shell_map", {}),
        )
    classical_state = _get_classical_state(model) or {}
    reference_frames = build_reference_frames(classical_state)
    site_count = max(frame["site"] for frame in reference_frames) + 1
    lattice = model.get("lattice", {})
    positions = lattice.get("positions") or [[0.0, 0.0, 0.0] for _ in range(site_count)]
    lattice_vectors = resolve_lattice_vectors(lattice)
    q_path_summary = _resolve_q_path(model, lattice, bonds)
    payload = {
        "backend": "Sunny.jl",
        "lattice": lattice,
        "lattice_vectors": lattice_vectors,
        "positions": positions,
        "template": simplified_model.get("template", "generic"),
        "bonds": [
            {
                "source": int(term["source"]),
                "target": int(term["target"]),
                "vector": [float(value) for value in term.get("vector", [])],
                "exchange_matrix": normalize_exchange_matrix(term),
            }
            for term in bonds
        ],
        "reference_frames": reference_frames,
        "moments": [
            {
                "site": int(frame["site"]),
                "spin": float(frame["spin_length"]),
                "g": 2.0,
            }
            for frame in reference_frames
        ],
        "ordering": get_classical_ordering(model, prefer_nested_legacy=True) or classical_state.get("ordering", {}),
        "q_path": q_path_summary["q_path"],
        "q_grid": model.get("q_grid", []),
        "q_samples": int(model.get("q_samples", 64)),
        "spatial_dimension": q_path_summary["spatial_dimension"],
        "path": q_path_summary["path"],
        "shell_map": shell_map,
    }
    rotating_frame_transform = resolve_rotating_frame_transform(model)
    if rotating_frame_transform is not None:
        payload["rotating_frame_transform"] = rotating_frame_transform
    rotating_frame_realization = resolve_rotating_frame_realization(model)
    if rotating_frame_realization is not None:
        payload["rotating_frame_realization"] = rotating_frame_realization
    quadratic_phase_dressing = resolve_quadratic_phase_dressing(model)
    if quadratic_phase_dressing is not None:
        payload["quadratic_phase_dressing"] = quadratic_phase_dressing
    return {"status": "ok", "payload": payload}


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    payload = _load_payload(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(build_lswt_payload(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
