#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.cpn_glt_reconstruction import minimal_commensurate_supercell, rationalize_q_vector
from common.bravais_kpaths import default_high_symmetry_path
from common.classical_contract_resolution import (
    get_classical_ordering,
    get_classical_supercell_shape,
    get_standardized_classical_state,
)
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


def _normalize_vector(vector):
    norm = _vector_norm(vector)
    if norm <= 1.0e-12:
        raise ValueError("rotation axis must have non-zero length")
    return [float(value) / norm for value in vector]


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


def _normalize_supercell_shape(shape):
    if not isinstance(shape, list) or len(shape) != 3:
        return None
    normalized = [int(value) for value in shape]
    if any(value <= 0 for value in normalized):
        return None
    return normalized


def _padded_q_vector(ordering):
    if not isinstance(ordering, dict):
        return None
    q_vector = ordering.get("q_vector")
    if not isinstance(q_vector, list):
        return None
    padded = [0.0, 0.0, 0.0]
    for axis in range(min(3, len(q_vector))):
        padded[axis] = float(q_vector[axis])
    return padded


def _resolve_lswt_supercell_shape(model, ordering):
    explicit_shape = get_classical_supercell_shape(model, prefer_nested_legacy=True)
    normalized_explicit = _normalize_supercell_shape(explicit_shape)
    if normalized_explicit is not None:
        return normalized_explicit

    q_vector = _padded_q_vector(ordering)
    if q_vector is None:
        return [1, 1, 1]

    rational_q = rationalize_q_vector(q_vector)
    if rational_q is None:
        return [1, 1, 1]
    return _normalize_supercell_shape(minimal_commensurate_supercell(rational_q)) or [1, 1, 1]


def _phase_sign_from_fractional_phase(phase_fraction, *, tolerance=1.0e-8):
    wrapped = float(phase_fraction) % 1.0
    if abs(wrapped) <= tolerance or abs(wrapped - 1.0) <= tolerance:
        return 1.0
    if abs(wrapped - 0.5) <= tolerance:
        return -1.0
    return None


def _resolve_rotation_axis_vector(rotation_axis, lattice_vectors):
    if isinstance(rotation_axis, list) and len(rotation_axis) == 3:
        return _normalize_vector(rotation_axis)

    axis_name = str(rotation_axis or "").strip().lower()
    cartesian_axes = {
        "x": [1.0, 0.0, 0.0],
        "y": [0.0, 1.0, 0.0],
        "z": [0.0, 0.0, 1.0],
    }
    if axis_name in cartesian_axes:
        return cartesian_axes[axis_name]

    lattice_axis_index = {"a": 0, "b": 1, "c": 2}.get(axis_name)
    if lattice_axis_index is None:
        raise ValueError(f"unsupported rotation axis {rotation_axis!r}")

    if lattice_axis_index < len(lattice_vectors):
        candidate = lattice_vectors[lattice_axis_index]
        if _vector_norm(candidate) > 1.0e-12:
            return _normalize_vector(candidate)
    return cartesian_axes[("x", "y", "z")[lattice_axis_index]]


def _rotate_direction(direction, axis_vector, phase):
    unit_axis = _normalize_vector(axis_vector)
    vector = [float(value) for value in direction]
    cosine = math.cos(float(phase))
    sine = math.sin(float(phase))
    dot = sum(vector[index] * unit_axis[index] for index in range(3))
    cross = [
        unit_axis[1] * vector[2] - unit_axis[2] * vector[1],
        unit_axis[2] * vector[0] - unit_axis[0] * vector[2],
        unit_axis[0] * vector[1] - unit_axis[1] * vector[0],
    ]
    return [
        vector[index] * cosine
        + cross[index] * sine
        + unit_axis[index] * dot * (1.0 - cosine)
        for index in range(3)
    ]


def _build_supercell_phase_map(entries, supercell_shape, reference_frames):
    if not isinstance(entries, list) or not entries:
        raise ValueError("rotating-frame realization is missing usable supercell_site_phases")

    normalized_shape = _normalize_supercell_shape(supercell_shape) or [1, 1, 1]
    expected_sites = {int(frame["site"]) for frame in reference_frames}
    phase_map = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("rotating-frame realization contains a non-dictionary phase entry")
        cell = entry.get("cell")
        site = entry.get("site")
        phase = entry.get("phase")
        if not isinstance(cell, list) or len(cell) != 3 or site is None or phase is None:
            raise ValueError("rotating-frame realization contains an invalid phase entry")
        normalized_cell = [int(value) for value in cell]
        if any(value < 0 for value in normalized_cell):
            raise ValueError("rotating-frame phase entry has a negative cell index")
        if any(normalized_cell[axis] >= normalized_shape[axis] for axis in range(3)):
            raise ValueError("rotating-frame phase entry falls outside the inferred supercell shape")
        site_index = int(site)
        if site_index not in expected_sites:
            raise ValueError("rotating-frame phase entry references a site outside classical_state.site_frames")
        key = (tuple(normalized_cell), site_index)
        if key in phase_map:
            raise ValueError("rotating-frame realization contains duplicate supercell phase entries")
        phase_map[key] = float(phase)

    expected_count = normalized_shape[0] * normalized_shape[1] * normalized_shape[2] * len(expected_sites)
    if len(phase_map) != expected_count:
        raise ValueError("rotating-frame phase coverage is incomplete for the inferred supercell")
    return phase_map


def _resolve_explicit_rotating_frame_phase_override(model):
    if not isinstance(model, dict):
        return None
    candidates = [
        model.get("rotating_frame_realization"),
        (model.get("effective_model", {}) or {}).get("rotating_frame_realization"),
        (model.get("normalized_model", {}) or {}).get("rotating_frame_realization"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        entries = candidate.get("supercell_site_phases")
        if not isinstance(entries, list):
            continue
        normalized_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cell = entry.get("cell")
            site = entry.get("site")
            phase = entry.get("phase")
            if not isinstance(cell, list) or len(cell) != 3 or site is None or phase is None:
                continue
            normalized_entries.append(
                {
                    "cell": [int(value) for value in cell],
                    "site": int(site),
                    "phase": float(phase),
                }
            )
        override = {"supercell_site_phases": normalized_entries}
        normalized_shape = _normalize_supercell_shape(candidate.get("supercell_shape"))
        if normalized_shape is not None:
            override["supercell_shape"] = normalized_shape
        if candidate.get("rotation_axis") not in {None, ""}:
            override["rotation_axis"] = candidate.get("rotation_axis")
        return override
    return None


def _expand_rotating_frame_supercell_reference_frames(
    reference_frames,
    supercell_shape,
    rotating_frame_transform,
    rotating_frame_realization,
    lattice_vectors,
):
    if rotating_frame_realization is None and rotating_frame_transform is None:
        return None

    normalized_shape = _normalize_supercell_shape(supercell_shape) or [1, 1, 1]
    realization_shape = _normalize_supercell_shape(
        (rotating_frame_realization or {}).get("supercell_shape") if isinstance(rotating_frame_realization, dict) else None
    )
    if realization_shape is not None and realization_shape != normalized_shape:
        raise ValueError(
            "rotating-frame realization supercell_shape does not match the inferred LSWT supercell"
        )

    rotation_axis = None
    if isinstance(rotating_frame_realization, dict):
        rotation_axis = rotating_frame_realization.get("rotation_axis")
    if rotation_axis in {None, ""} and isinstance(rotating_frame_transform, dict):
        rotation_axis = rotating_frame_transform.get("rotation_axis")
    axis_vector = _resolve_rotation_axis_vector(rotation_axis, lattice_vectors)
    phase_map = _build_supercell_phase_map(
        (rotating_frame_realization or {}).get("supercell_site_phases") if isinstance(rotating_frame_realization, dict) else None,
        normalized_shape,
        reference_frames,
    )

    expanded = []
    for cell_x in range(int(normalized_shape[0])):
        for cell_y in range(int(normalized_shape[1])):
            for cell_z in range(int(normalized_shape[2])):
                cell = [cell_x, cell_y, cell_z]
                for frame in reference_frames:
                    site = int(frame["site"])
                    phase = phase_map[(tuple(cell), site)]
                    expanded.append(
                        {
                            "cell": list(cell),
                            "site": site,
                            "spin_length": float(frame["spin_length"]),
                            "direction": _rotate_direction(frame["direction"], axis_vector, phase),
                        }
                    )
    return expanded


def _expand_phase1_sign_flip_supercell_reference_frames(reference_frames, positions, supercell_shape, ordering):
    normalized_shape = _normalize_supercell_shape(supercell_shape) or [1, 1, 1]
    q_vector = _padded_q_vector(ordering)
    if normalized_shape == [1, 1, 1]:
        return [
            {
                "cell": [0, 0, 0],
                "site": int(frame["site"]),
                "spin_length": float(frame["spin_length"]),
                "direction": [float(value) for value in frame["direction"]],
            }
            for frame in reference_frames
        ]

    if q_vector is None:
        raise ValueError(
            "commensurate LSWT supercell expansion requires ordering.q_vector when supercell_shape is not [1, 1, 1]"
        )

    expanded = []
    for cell_x in range(int(normalized_shape[0])):
        for cell_y in range(int(normalized_shape[1])):
            for cell_z in range(int(normalized_shape[2])):
                cell = [cell_x, cell_y, cell_z]
                for frame in reference_frames:
                    site = int(frame["site"])
                    position = positions[site] if site < len(positions) else [0.0, 0.0, 0.0]
                    phase_fraction = sum(
                        float(q_vector[axis]) * (float(cell[axis]) + float(position[axis]))
                        for axis in range(3)
                    )
                    sign = _phase_sign_from_fractional_phase(phase_fraction)
                    if sign is None:
                        raise ValueError(
                            "commensurate single-q LSWT Phase 1 only supports 0/pi collinear cell phases"
                        )
                    expanded.append(
                        {
                            "cell": list(cell),
                            "site": site,
                            "spin_length": float(frame["spin_length"]),
                            "direction": [sign * float(value) for value in frame["direction"]],
                        }
                    )
    return expanded


def _expand_supercell_reference_frames(
    reference_frames,
    positions,
    supercell_shape,
    ordering,
    rotating_frame_transform,
    rotating_frame_realization,
    lattice_vectors,
):
    if rotating_frame_transform is not None or rotating_frame_realization is not None:
        return _expand_rotating_frame_supercell_reference_frames(
            reference_frames,
            supercell_shape,
            rotating_frame_transform,
            rotating_frame_realization,
            lattice_vectors,
        )

    return _expand_phase1_sign_flip_supercell_reference_frames(
        reference_frames,
        positions,
        supercell_shape,
        ordering,
    )


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
    ordering = get_classical_ordering(model, prefer_nested_legacy=True) or classical_state.get("ordering", {})
    supercell_shape = _resolve_lswt_supercell_shape(model, ordering)
    rotating_frame_transform = resolve_rotating_frame_transform(model)
    rotating_frame_realization = resolve_rotating_frame_realization(
        {
            **model,
            "lattice": lattice,
            "positions": positions,
            "lattice_vectors": lattice_vectors,
            "supercell_shape": supercell_shape,
            "ordering": ordering,
        }
    )
    explicit_phase_override = _resolve_explicit_rotating_frame_phase_override(model)
    if explicit_phase_override is not None:
        rotating_frame_realization = dict(rotating_frame_realization or {})
        rotating_frame_realization.update(explicit_phase_override)
    try:
        supercell_reference_frames = _expand_supercell_reference_frames(
            reference_frames,
            positions,
            supercell_shape,
            ordering,
            rotating_frame_transform,
            rotating_frame_realization,
            lattice_vectors,
        )
    except ValueError as exc:
        return _error(
            "unsupported-lswt-ordering",
            f"spin-only LSWT commensurate supercell expansion failed: {exc}. "
            "Supported cases are Phase 1 commensurate 0/pi collinear supercells or "
            "Phase 2 commensurate single-q rotating-frame realizations with complete phase coverage.",
        )

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
        "supercell_reference_frames": supercell_reference_frames,
        "supercell_shape": supercell_shape,
        "moments": [
            {
                "site": int(frame["site"]),
                "spin": float(frame["spin_length"]),
                "g": 2.0,
            }
            for frame in reference_frames
        ],
        "ordering": ordering,
        "q_path": q_path_summary["q_path"],
        "q_grid": model.get("q_grid", []),
        "q_samples": int(model.get("q_samples", 64)),
        "spatial_dimension": q_path_summary["spatial_dimension"],
        "path": q_path_summary["path"],
        "shell_map": shell_map,
    }
    if rotating_frame_transform is not None:
        payload["rotating_frame_transform"] = rotating_frame_transform
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
