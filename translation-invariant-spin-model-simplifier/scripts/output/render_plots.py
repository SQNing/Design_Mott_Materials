#!/usr/bin/env python3
import argparse
import fractions
import json
import math
import os
import sys
import tempfile
from pathlib import Path


_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "codex-matplotlib"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.cpn_classical_state import resolve_cpn_classical_state_payload
from common.cpn_local_observables import build_cpn_local_observable_summary
from lswt.build_lswt_payload import infer_spatial_dimension
from common.lattice_geometry import fractional_to_cartesian, resolve_lattice_vectors


def _get_classical_state(payload):
    classical = payload.get("classical", {})
    return classical.get("classical_state", payload.get("classical_state", {}))


def _is_prebuilt_plot_payload(payload):
    return isinstance(payload, dict) and "classical_state" in payload and "lswt_dispersion" in payload and "thermodynamics" in payload


def _matvec(matrix, vector):
    result = [0.0, 0.0, 0.0]
    for row in range(3):
        result[row] = sum(float(matrix[row][col]) * float(vector[col]) for col in range(3))
    return result


def _vector_add(left, right):
    return [float(left[index]) + float(right[index]) for index in range(3)]


def _vector_scale(vector, scalar):
    return [float(scalar) * float(value) for value in vector]


def _vector_norm(vector):
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _normalize(vector):
    norm = _vector_norm(vector)
    if norm <= 1e-12:
        return [0.0, 0.0, 1.0]
    return [float(value) / norm for value in vector]


def _perpendicular(vector):
    x, y, z = vector
    if abs(x) < 0.8:
        candidate = [1.0, 0.0, 0.0]
    else:
        candidate = [0.0, 1.0, 0.0]
    dot = sum(candidate[index] * vector[index] for index in range(3))
    projected = [candidate[index] - dot * vector[index] for index in range(3)]
    return _normalize(projected)


def _cross(left, right):
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _dot(left, right):
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _rotation_matrix_from_vectors(source, target):
    source = _normalize(source)
    target = _normalize(target)
    axis = _cross(source, target)
    sine = _vector_norm(axis)
    cosine = max(-1.0, min(1.0, _dot(source, target)))
    if sine <= 1e-12:
        if cosine > 0.0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        axis = _perpendicular(source)
        sine = 1.0
        cosine = -1.0
    else:
        axis = [value / sine for value in axis]

    kx, ky, kz = axis
    k = [
        [0.0, -kz, ky],
        [kz, 0.0, -kx],
        [-ky, kx, 0.0],
    ]

    def matmul(a, b):
        return [
            [sum(a[row][pivot] * b[pivot][col] for pivot in range(3)) for col in range(3)]
            for row in range(3)
        ]

    identity = [[1.0 if row == col else 0.0 for col in range(3)] for row in range(3)]
    kk = matmul(k, k)
    factor = (1.0 - cosine)
    return [
        [
            identity[row][col] + sine * k[row][col] + factor * kk[row][col]
            for col in range(3)
        ]
        for row in range(3)
    ]


def _rotate_vector(vector, rotation_matrix):
    return [
        sum(float(rotation_matrix[row][col]) * float(vector[col]) for col in range(3))
        for row in range(3)
    ]


def _rotate_spin(base_direction, q_vector, cell_index):
    phase = 2.0 * math.pi * sum(float(q_vector[axis]) * float(cell_index[axis]) for axis in range(3))
    aligned = _normalize(base_direction)
    transverse = _perpendicular(aligned)
    return [
        math.cos(phase) * aligned[axis] + math.sin(phase) * transverse[axis]
        for axis in range(3)
    ]


def _default_repeat_cells(spatial_dimension, ordering_kind, commensurate_cells, incommensurate_cells):
    base = commensurate_cells if ordering_kind == "commensurate" else incommensurate_cells
    if spatial_dimension <= 1:
        return [base, 1, 1]
    if spatial_dimension == 2:
        return [base, base, 1]
    return [base, base, base]


def _normalize_repeat_request(request, spatial_dimension, default_scalar):
    if isinstance(request, int):
        if spatial_dimension <= 1:
            return [request, 1, 1]
        if spatial_dimension == 2:
            return [request, request, 1]
        return [request, request, request]

    if isinstance(request, (list, tuple)):
        values = [int(value) for value in request]
        if len(values) == 1:
            return _normalize_repeat_request(values[0], spatial_dimension, default_scalar)
        while len(values) < 3:
            values.append(1)
        return [max(1, values[0]), max(1, values[1]), max(1, values[2])]

    return _normalize_repeat_request(default_scalar, spatial_dimension, default_scalar)


def _normalized_ordering_kind(ordering):
    if not isinstance(ordering, dict):
        return "commensurate"
    candidates = [
        ordering.get("kind"),
        ordering.get("compatibility_with_supercell", {}).get("kind")
        if isinstance(ordering.get("compatibility_with_supercell"), dict)
        else None,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip().lower()
        if "incommensurate" in text:
            return "incommensurate"
        if "commensurate" in text or text in {"uniform", "periodic", "supercell"}:
            return "commensurate"
    return "commensurate"


def _magnetic_repeat_cells(spatial_dimension, ordering_kind, commensurate_cells, incommensurate_cells):
    if ordering_kind == "incommensurate":
        return _normalize_repeat_request(incommensurate_cells, spatial_dimension, 5)
    return _normalize_repeat_request(commensurate_cells, spatial_dimension, 2)


def _magnetic_periods(q_vector, ordering_kind, spatial_dimension, max_denominator=24, tolerance=1e-6):
    if ordering_kind != "commensurate":
        return [1, 1, 1]
    periods = [1, 1, 1]
    active_axes = 1 if spatial_dimension <= 1 else 2 if spatial_dimension == 2 else 3
    for axis in range(active_axes):
        value = float(q_vector[axis]) if axis < len(q_vector) else 0.0
        if abs(value) <= tolerance:
            periods[axis] = 1
            continue
        fraction = fractions.Fraction(value).limit_denominator(max_denominator)
        if abs(float(fraction) - value) <= tolerance:
            periods[axis] = abs(fraction.denominator)
        else:
            periods[axis] = 1
    return periods


def _repeat_cells_from_magnetic_periods(spatial_dimension, ordering_kind, magnetic_periods, commensurate_cells, incommensurate_cells):
    commensurate_repeat_request = _magnetic_repeat_cells(
        spatial_dimension,
        "commensurate",
        commensurate_cells,
        incommensurate_cells,
    )
    incommensurate_repeat_request = _magnetic_repeat_cells(
        spatial_dimension,
        "incommensurate",
        commensurate_cells,
        incommensurate_cells,
    )
    if ordering_kind != "commensurate":
        return incommensurate_repeat_request
    repeat_cells = [1, 1, 1]
    active_axes = 1 if spatial_dimension <= 1 else 2 if spatial_dimension == 2 else 3
    for axis in range(active_axes):
        repeat_cells[axis] = max(1, int(magnetic_periods[axis])) * int(commensurate_repeat_request[axis])
    return repeat_cells


def _basis_position(lattice, basis_index, site_count):
    positions = lattice.get("positions") or []
    if positions and basis_index < len(positions):
        position = list(positions[basis_index])
    elif positions and len(positions) == 1:
        position = list(positions[0])
    else:
        position = [0.0, 0.0, 0.0]
    while len(position) < 3:
        position.append(0.0)
    return position


def _basis_labels(site_count):
    return [f"Atom {index}" for index in range(site_count)]


def _cell_origin(lattice_vectors, cell_index):
    return [
        cell_index[0] * lattice_vectors[0][axis]
        + cell_index[1] * lattice_vectors[1][axis]
        + cell_index[2] * lattice_vectors[2][axis]
        for axis in range(3)
    ]


def _unit_cell_segments_2d(lattice_vectors, repeat_cells):
    a1 = [float(value) for value in lattice_vectors[0]]
    a2 = [float(value) for value in lattice_vectors[1]]
    segments = []

    primitive = [[0.0, 0.0, 0.0], a1, _vector_add(a1, a2), a2]
    for index in range(4):
        segments.append(
            {
                "start": primitive[index],
                "end": primitive[(index + 1) % 4],
                "style": "primitive",
            }
        )

    supercell_corners = [
        [0.0, 0.0, 0.0],
        _cell_origin(lattice_vectors, [repeat_cells[0], 0, 0]),
        _cell_origin(lattice_vectors, [repeat_cells[0], repeat_cells[1], 0]),
        _cell_origin(lattice_vectors, [0, repeat_cells[1], 0]),
    ]
    for index in range(4):
        segments.append(
            {
                "start": supercell_corners[index],
                "end": supercell_corners[(index + 1) % 4],
                "style": "supercell",
            }
        )
    return segments


def _parallelepiped_edges(origin, a1, a2, a3, style):
    vertices = [
        origin,
        _vector_add(origin, a1),
        _vector_add(origin, a2),
        _vector_add(_vector_add(origin, a1), a2),
        _vector_add(origin, a3),
        _vector_add(_vector_add(origin, a1), a3),
        _vector_add(_vector_add(origin, a2), a3),
        _vector_add(_vector_add(_vector_add(origin, a1), a2), a3),
    ]
    edge_indices = [
        (0, 1),
        (0, 2),
        (0, 4),
        (1, 3),
        (1, 5),
        (2, 3),
        (2, 6),
        (3, 7),
        (4, 5),
        (4, 6),
        (5, 7),
        (6, 7),
    ]
    return [{"start": vertices[start], "end": vertices[end], "style": style} for start, end in edge_indices]


def _unit_cell_segments_3d(lattice_vectors, repeat_cells):
    a1 = [float(value) for value in lattice_vectors[0]]
    a2 = [float(value) for value in lattice_vectors[1]]
    a3 = [float(value) for value in lattice_vectors[2]]
    primitive = _parallelepiped_edges([0.0, 0.0, 0.0], a1, a2, a3, style="primitive")
    supercell_origin = [0.0, 0.0, 0.0]
    super_a1 = _vector_scale(a1, repeat_cells[0])
    super_a2 = _vector_scale(a2, repeat_cells[1])
    super_a3 = _vector_scale(a3, repeat_cells[2])
    supercell = _parallelepiped_edges(supercell_origin, super_a1, super_a2, super_a3, style="supercell")
    return primitive + supercell


def _build_unit_cell_segments(lattice_vectors, repeat_cells, spatial_dimension):
    if spatial_dimension >= 3:
        return _unit_cell_segments_3d(lattice_vectors, repeat_cells)
    return _unit_cell_segments_2d(lattice_vectors, repeat_cells)


def _default_view(spatial_dimension):
    if spatial_dimension >= 3:
        return {"projection": "3d", "elev": 22.0, "azim": -58.0}
    if spatial_dimension == 2:
        return {"projection": "2d"}
    return {"projection": "chain"}


def _default_structure_style():
    return {
        "atom_fill": "#c9c9c9",
        "atom_edge_width": 2.2,
        "atom_size": 300.0,
        "spin_color": "#d00000",
        "arrow_length_factor": 0.52,
        "arrow_line_width": 2.8,
    }


def _merged_classical_style(plot_options):
    style = dict(_default_structure_style())
    overrides = plot_options.get("classical_style", {})
    if isinstance(overrides, dict):
        style.update(overrides)
    return style


def _default_figure_size(render_mode):
    if render_mode == "chain":
        return [10.5, 4.2]
    if render_mode == "plane":
        return [9.2, 8.2]
    return [9.8, 6.8]


def _resolved_figure_size(plot_options, render_mode):
    figure_size = plot_options.get("classical_figsize")
    if isinstance(figure_size, (list, tuple)) and len(figure_size) == 2:
        return [float(figure_size[0]), float(figure_size[1])]
    return _default_figure_size(render_mode)


def _default_lswt_style():
    return {
        "line_width": 1.5,
        "node_line_width": 0.8,
        "node_alpha": 0.7,
        "grid_alpha": 0.25,
    }


def _merged_lswt_style(plot_options):
    style = dict(_default_lswt_style())
    overrides = plot_options.get("lswt_style", {})
    if isinstance(overrides, dict):
        style.update(overrides)
    return style


def _resolved_lswt_figure_size(plot_options):
    figure_size = plot_options.get("lswt_figsize")
    if isinstance(figure_size, (list, tuple)) and len(figure_size) == 2:
        return [float(figure_size[0]), float(figure_size[1])]
    return [7.0, 4.5]


def _default_thermodynamics_style():
    return {
        "line_width": 1.6,
        "marker_size": 4.0,
        "capsize": 3.0,
        "grid_alpha": 0.25,
    }


def _merged_thermodynamics_style(plot_options):
    style = dict(_default_thermodynamics_style())
    overrides = plot_options.get("thermodynamics_style", {})
    if isinstance(overrides, dict):
        style.update(overrides)
    return style


def _resolved_thermodynamics_figure_size(plot_options):
    figure_size = plot_options.get("thermodynamics_figsize")
    if isinstance(figure_size, (list, tuple)) and len(figure_size) == 2:
        return [float(figure_size[0]), float(figure_size[1])]
    return [9.0, 9.0]


def _thermodynamics_configuration_from_payload(payload):
    thermodynamics = payload.get("thermodynamics", {})
    if isinstance(thermodynamics, dict) and thermodynamics:
        return thermodynamics
    thermodynamics_result = payload.get("thermodynamics_result", {})
    if isinstance(thermodynamics_result, dict):
        configuration = thermodynamics_result.get("configuration", {})
        if isinstance(configuration, dict) and configuration:
            return configuration
    return {}


def _gswt_plot_summary_line(gswt):
    if not isinstance(gswt, dict) or not gswt:
        return None
    diagnostics = gswt.get("diagnostics", {})
    instability = diagnostics.get("instability", {}) if isinstance(diagnostics, dict) else {}
    if not instability:
        status = gswt.get("status")
        if status:
            return f"GSWT status={status}"
        return None
    nearest_kind = instability.get("nearest_q_path_kind")
    if nearest_kind == "high-symmetry-node":
        label = instability.get("nearest_high_symmetry_label", "node")
        return f"GSWT: harmonic instability near high-symmetry point {label}"
    if nearest_kind == "path-segment-sample":
        label = instability.get("nearest_path_segment_label", "path segment")
        return f"GSWT: harmonic instability near path segment {label}"
    q_vector = instability.get("q_vector")
    return f"GSWT: harmonic instability near q={q_vector}"


def _format_summary_float(value):
    if value is None:
        return "n/a"
    return format(float(value), ".8g")


def _dispersion_omega_minimum(dispersion):
    if not isinstance(dispersion, list):
        return None, None
    omega_min = None
    omega_min_q = None
    for point in dispersion:
        if not isinstance(point, dict):
            continue
        omega = point.get("omega")
        if omega is None:
            bands = point.get("bands", [])
            if not bands:
                continue
            omega = min(float(value) for value in bands)
        else:
            omega = float(omega)
        if omega_min is None or omega < omega_min:
            omega_min = omega
            omega_min_q = list(point.get("q", []))
    return omega_min, omega_min_q


def _gswt_reference_dispersion_summary_line(gswt, diagnostics):
    reference_dispersions = (
        gswt.get("reference_dispersions", {})
        if isinstance(gswt.get("reference_dispersions"), dict)
        else {}
    )
    reference_selection = (
        diagnostics.get("reference_selection", {})
        if isinstance(diagnostics.get("reference_selection"), dict)
        else {}
    )
    resolved_mode = str(reference_selection.get("resolved_mode", gswt.get("z_harmonic_reference_mode", "input")))
    input_dispersion = reference_dispersions.get("input")
    selected_dispersion = reference_dispersions.get(resolved_mode)
    if resolved_mode == "input" or input_dispersion is None or selected_dispersion is None:
        return None

    input_omega_min, input_omega_min_q = _dispersion_omega_minimum(input_dispersion)
    selected_omega_min, selected_omega_min_q = _dispersion_omega_minimum(selected_dispersion)
    if input_omega_min is None or selected_omega_min is None:
        return None

    delta_omega_min = float(selected_omega_min - input_omega_min)
    return (
        "reference_dispersion_comparison "
        f"selected_mode={resolved_mode} "
        f"input_omega_min={_format_summary_float(input_omega_min)} "
        f"input_omega_min_q={input_omega_min_q} "
        f"selected_omega_min={_format_summary_float(selected_omega_min)} "
        f"selected_omega_min_q={selected_omega_min_q} "
        f"delta_omega_min={_format_summary_float(delta_omega_min)}"
    )


def _single_q_convergence_summary_lines(payload):
    convergence = (
        payload.get("single_q_convergence", {})
        if isinstance(payload.get("single_q_convergence"), dict)
        else {}
    )
    if not convergence:
        return []

    reference = (
        convergence.get("reference_parameters", {})
        if isinstance(convergence.get("reference_parameters"), dict)
        else {}
    )
    metrics = (
        convergence.get("reference_metrics", {})
        if isinstance(convergence.get("reference_metrics"), dict)
        else {}
    )

    lines = [
        "single_q_convergence "
        f"reference_phase_grid_size={reference.get('phase_grid_size', 'n/a')} "
        f"reference_z_harmonic_cutoff={reference.get('z_harmonic_cutoff', 'n/a')} "
        f"reference_sideband_cutoff={reference.get('sideband_cutoff', 'n/a')} "
        f"reference_mode={reference.get('z_harmonic_reference_mode', 'n/a')} "
        f"reference_omega_min={_format_summary_float(metrics.get('omega_min'))}"
    ]

    for primary_key, scan_key, label in (
        ("phase_grid_size", "phase_grid_scan", "phase_grid_scan"),
        ("z_harmonic_cutoff", "z_harmonic_cutoff_scan", "z_harmonic_cutoff_scan"),
        ("sideband_cutoff", "sideband_cutoff_scan", "sideband_cutoff_scan"),
    ):
        entries = [entry for entry in convergence.get(scan_key, []) if isinstance(entry, dict)]
        if not entries:
            continue
        values = [entry.get(primary_key) for entry in entries]
        max_band_delta = None
        max_abs_omega_delta = None
        for entry in entries:
            band_delta = entry.get("max_band_delta_vs_reference")
            if band_delta is not None:
                band_delta = abs(float(band_delta))
                max_band_delta = band_delta if max_band_delta is None else max(max_band_delta, band_delta)
            omega_delta = entry.get("omega_min_delta_vs_reference")
            if omega_delta is not None:
                omega_delta = abs(float(omega_delta))
                max_abs_omega_delta = (
                    omega_delta if max_abs_omega_delta is None else max(max_abs_omega_delta, omega_delta)
                )
        lines.append(
            f"{label} values={values} "
            f"max_band_delta_vs_reference={_format_summary_float(max_band_delta)} "
            f"max_abs_omega_min_delta={_format_summary_float(max_abs_omega_delta)}"
        )

    return lines


def _gswt_summary_lines(payload, gswt):
    if not isinstance(gswt, dict) or not gswt:
        return []
    lines = []
    backend = gswt.get("backend", {}) if isinstance(gswt.get("backend"), dict) else {}
    status = gswt.get("status")
    if backend.get("name") is not None or status is not None:
        lines.append(f"GSWT backend={backend.get('name', 'unknown')} status={status or 'missing'}")
    interpretation = _gswt_plot_summary_line(gswt)
    if interpretation is not None:
        lines.append(interpretation)
    diagnostics = gswt.get("diagnostics", {}) if isinstance(gswt.get("diagnostics"), dict) else {}
    dispersion = diagnostics.get("dispersion", {}) if isinstance(diagnostics.get("dispersion"), dict) else {}
    if dispersion:
        lines.append(
            f"omega_min={dispersion.get('omega_min', 'n/a')} "
            f"soft_mode_count={dispersion.get('soft_mode_count', 'n/a')}"
        )
    harmonic = diagnostics.get("harmonic", {}) if isinstance(diagnostics.get("harmonic"), dict) else {}
    if gswt.get("payload_kind") == "python_glswt_single_q_z_harmonic" or harmonic:
        bogoliubov = diagnostics.get("bogoliubov", {}) if isinstance(diagnostics.get("bogoliubov"), dict) else {}
        lines.append(
            f"z_harmonic_cutoff={gswt.get('z_harmonic_cutoff', 'n/a')} "
            f"reference_mode={gswt.get('z_harmonic_reference_mode', 'input')} "
            f"phase_grid_size={gswt.get('phase_grid_size', harmonic.get('phase_grid_size', 'n/a'))} "
            f"sideband_cutoff={gswt.get('sideband_cutoff', bogoliubov.get('sideband_cutoff', 'n/a'))}"
        )
    reference_selection = (
        diagnostics.get("reference_selection", {})
        if isinstance(diagnostics.get("reference_selection"), dict)
        else {}
    )
    if reference_selection:
        lines.append(
            f"requested_mode={reference_selection.get('requested_mode', 'n/a')} "
            f"resolved_mode={reference_selection.get('resolved_mode', 'n/a')} "
            f"dispersion_recomputed={reference_selection.get('dispersion_recomputed', 'n/a')}"
        )
    reference_dispersion_summary = _gswt_reference_dispersion_summary_line(gswt, diagnostics)
    if reference_dispersion_summary is not None:
        lines.append(reference_dispersion_summary)
    restricted_ansatz = (
        diagnostics.get("restricted_ansatz_stationarity", {})
        if isinstance(diagnostics.get("restricted_ansatz_stationarity"), dict)
        else {}
    )
    if restricted_ansatz:
        lines.append(
            f"restricted_ansatz optimizer_success={restricted_ansatz.get('optimizer_success', 'n/a')} "
            f"optimization_mode={restricted_ansatz.get('optimization_mode', 'n/a')} "
            f"best_objective={restricted_ansatz.get('best_objective', 'n/a')}"
        )
    truncated_z_harmonic = (
        diagnostics.get("truncated_z_harmonic_stationarity", {})
        if isinstance(diagnostics.get("truncated_z_harmonic_stationarity"), dict)
        else {}
    )
    if truncated_z_harmonic:
        lines.append(
            f"truncated_z_harmonic scope={truncated_z_harmonic.get('scope', 'n/a')} "
            f"harmonic_cutoff={truncated_z_harmonic.get('harmonic_cutoff', 'n/a')} "
            f"discarded_harmonic_count={truncated_z_harmonic.get('discarded_harmonic_count', 'n/a')} "
            f"is_stationary={truncated_z_harmonic.get('is_stationary', 'n/a')} "
            f"linear_term_max_norm={truncated_z_harmonic.get('linear_term_max_norm', 'n/a')} "
            f"discarded_linear_term_max_norm={truncated_z_harmonic.get('discarded_linear_term_max_norm', 'n/a')}"
        )
    local_refinement = (
        diagnostics.get("truncated_z_harmonic_local_refinement", {})
        if isinstance(diagnostics.get("truncated_z_harmonic_local_refinement"), dict)
        else {}
    )
    if local_refinement:
        lines.append(
            f"local_refinement status={local_refinement.get('status', 'n/a')} "
            f"selected_step_size={local_refinement.get('selected_step_size', 'n/a')} "
            f"iteration_count={local_refinement.get('iteration_count', 'n/a')} "
            f"initial_retained_linear_term_max_norm={local_refinement.get('initial_retained_linear_term_max_norm', 'n/a')} "
            f"refined_retained_linear_term_max_norm={local_refinement.get('refined_retained_linear_term_max_norm', 'n/a')}"
        )
    stationarity = diagnostics.get("stationarity", {}) if isinstance(diagnostics.get("stationarity"), dict) else {}
    if stationarity:
        lines.append(
            f"scope={stationarity.get('scope', 'n/a')} "
            f"sampling_kind={stationarity.get('sampling_kind', 'n/a')} "
            f"stationary={stationarity.get('is_stationary', 'n/a')} "
            f"linear_term_max_norm={stationarity.get('linear_term_max_norm', 'n/a')}"
        )
    bogoliubov = diagnostics.get("bogoliubov", {}) if isinstance(diagnostics.get("bogoliubov"), dict) else {}
    if bogoliubov:
        lines.append(
            f"mode_count={bogoliubov.get('mode_count', 'n/a')} "
            f"max_complex_eigenvalue_count={bogoliubov.get('max_complex_eigenvalue_count', 'n/a')}"
        )
    lines.extend(_single_q_convergence_summary_lines(payload))
    return lines


def _lswt_summary_lines(payload, dispersion, band_count):
    lswt = payload.get("lswt", {})
    backend = lswt.get("backend", {}) if isinstance(lswt.get("backend"), dict) else {}
    lines = []
    if dispersion:
        omega_values = []
        for point in dispersion:
            bands = point.get("bands", [])
            if bands:
                omega_values.extend(float(value) for value in bands)
            elif point.get("omega") is not None:
                omega_values.append(float(point.get("omega")))
        if omega_values:
            lines.append(
                f"LSWT backend={backend.get('name', 'unknown')} band_count={int(band_count)} "
                f"omega_min={min(omega_values):.6g} omega_max={max(omega_values):.6g}"
            )
    gswt_line = _gswt_plot_summary_line(payload.get("gswt", {}))
    if gswt_line is not None:
        lines.append(gswt_line)
    return lines


def _thermodynamics_summary_lines(payload, thermodynamics_grid):
    thermodynamics_result = payload.get("thermodynamics_result", {})
    backend = thermodynamics_result.get("backend", {}) if isinstance(thermodynamics_result, dict) else {}
    configuration = _thermodynamics_configuration_from_payload(payload)
    if not thermodynamics_grid and not configuration:
        return []

    lines = []
    profile = configuration.get("profile")
    backend_method = configuration.get("backend_method") or backend.get("sampler")
    temperature_count = len(thermodynamics_grid)
    if profile is not None or backend_method is not None or temperature_count:
        lines.append(
            f"profile={profile or 'custom'} backend={backend_method or 'unknown'} "
            f"temperature_count={int(temperature_count)}"
        )
    detail_fields = []
    for label in ("sweeps", "burn_in", "measurement_interval", "proposal", "proposal_scale"):
        value = configuration.get(label)
        if value is not None:
            detail_fields.append(f"{label}={value}")
    if detail_fields:
        lines.append(" ".join(detail_fields))
    return lines


def _draw_figure_summary(fig, summary_lines, *, y_top=0.95):
    lines = [str(line).strip() for line in (summary_lines or []) if str(line).strip()]
    if not lines:
        return False
    joined = "\n".join(lines)
    fig.text(
        0.5,
        y_top,
        joined,
        ha="center",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85, "edgecolor": "#cccccc"},
    )
    return True


def _render_gswt_diagnostics(gswt_payload, output_path):
    dispersion = gswt_payload.get("dispersion", [])
    path_metadata = gswt_payload.get("path", {})
    figure_size = gswt_payload.get("figure_size")
    style = gswt_payload.get("style")
    summary_lines = gswt_payload.get("summary_lines")
    if dispersion:
        if path_metadata:
            _render_dispersion_with_path(
                dispersion,
                path_metadata,
                output_path,
                figure_size=figure_size,
                style=style,
                summary_lines=summary_lines,
                title="GSWT Dispersion",
            )
        else:
            _render_dispersion(
                dispersion,
                output_path,
                figure_size=figure_size,
                style=style,
                summary_lines=summary_lines,
                title="GSWT Dispersion",
            )
        return

    instability = gswt_payload.get("instability", {})
    fig, ax = plt.subplots(figsize=figure_size or [7.0, 4.5])
    node_indices = list(path_metadata.get("node_indices", []))
    labels = list(path_metadata.get("labels", []))
    if node_indices and labels and len(node_indices) == len(labels):
        for index in node_indices:
            ax.axvline(index, color="#9ca3af", linewidth=float((style or {}).get("node_line_width", 0.8)), alpha=float((style or {}).get("node_alpha", 0.7)))
        ax.set_xticks(node_indices)
        ax.set_xticklabels(labels)
        max_index = max(node_indices)
    else:
        nearest_index = instability.get("nearest_q_path_index", 0)
        max_index = max(1, int(nearest_index))
        ax.set_xticks([0, max_index])
    ax.axhline(0.0, color="#666666", linewidth=1.0, alpha=0.7)
    nearest_index = instability.get("nearest_q_path_index")
    if nearest_index is not None:
        ax.scatter(
            [nearest_index],
            [0.0],
            color="#d00000",
            s=60,
            zorder=5,
            label=instability.get("nearest_path_segment_label", instability.get("nearest_high_symmetry_label", "instability")),
        )
    ax.set_xlim(-1, max_index + 1)
    ax.set_ylim(-1.0, 1.0)
    ax.set_yticks([])
    ax.set_xlabel("High-symmetry path")
    ax.grid(True, axis="x", alpha=float((style or {}).get("grid_alpha", 0.25)))
    fig.suptitle("GSWT Diagnostics", y=0.98)
    has_summary = _draw_figure_summary(fig, summary_lines, y_top=0.93)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88 if has_summary else 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _default_display_rotation():
    target_direction = _normalize([0.85, -0.38, 0.36])
    return {
        "kind": "global",
        "source_direction": [0.0, 0.0, 1.0],
        "target_direction": target_direction,
        "matrix": _rotation_matrix_from_vectors([0.0, 0.0, 1.0], target_direction),
    }


def _lattice_label_positions(lattice_vectors, spatial_dimension):
    labels = []
    if spatial_dimension <= 1:
        labels.append({"text": "a1", "position": _vector_scale(lattice_vectors[0], 0.5)})
        return labels
    labels.append({"text": "a1", "position": _vector_add(_vector_scale(lattice_vectors[0], 0.55), _vector_scale(lattice_vectors[1], 0.06))})
    labels.append({"text": "a2", "position": _vector_add(_vector_scale(lattice_vectors[1], 0.62), _vector_scale(lattice_vectors[0], -0.05))})
    if spatial_dimension >= 3:
        labels.append({"text": "a3", "position": _vector_add(_vector_scale(lattice_vectors[2], 0.62), _vector_scale(lattice_vectors[0], 0.05))})
    return labels


def _cpn_orbital_palette(orbital_count):
    base_palette = plt.rcParams["axes.prop_cycle"].by_key().get(
        "color",
        ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"],
    )
    orbital_count = max(1, int(orbital_count))
    return [base_palette[index % len(base_palette)] for index in range(orbital_count)]


def _classical_legend_title(classical_state):
    return str(classical_state.get("legend_title", "Basis Atoms"))


def _classical_summary_lines(payload, classical_state):
    if not isinstance(classical_state, dict) or not classical_state:
        return []

    lines = []
    chosen_method = payload.get("classical", {}).get("chosen_method", "unknown")
    render_mode = classical_state.get("render_mode", "structure")
    spatial_dimension = classical_state.get("spatial_dimension", "n/a")
    lines.append(
        f"method={chosen_method} render_mode={render_mode} spatial_dimension={spatial_dimension}"
    )

    state_fields = []
    if classical_state.get("state_kind") is not None:
        state_fields.append(f"state_kind={classical_state.get('state_kind')}")
    if classical_state.get("manifold") is not None:
        state_fields.append(f"manifold={classical_state.get('manifold')}")
    if classical_state.get("local_dimension") is not None:
        state_fields.append(f"local_dimension={classical_state.get('local_dimension')}")
    if classical_state.get("orbital_count") is not None:
        state_fields.append(f"orbital_count={classical_state.get('orbital_count')}")
    if classical_state.get("local_ray_count") is not None:
        state_fields.append(f"local_ray_count={classical_state.get('local_ray_count')}")
    if state_fields:
        lines.append(" ".join(state_fields))

    ordering = classical_state.get("ordering", {})
    ordering_fields = []
    if isinstance(ordering, dict):
        if ordering.get("kind") is not None:
            ordering_fields.append(f"ordering_kind={ordering.get('kind')}")
        if ordering.get("ansatz") is not None:
            ordering_fields.append(f"ansatz={ordering.get('ansatz')}")
        if ordering.get("q_vector") is not None:
            ordering_fields.append(f"q_vector={ordering.get('q_vector')}")
    if classical_state.get("ordering_kind") is not None:
        ordering_fields.append(f"ordering_kind_normalized={classical_state.get('ordering_kind')}")
    if classical_state.get("magnetic_repeat_cells") is not None:
        ordering_fields.append(f"magnetic_repeat_cells={classical_state.get('magnetic_repeat_cells')}")
    if classical_state.get("repeat_cells") is not None:
        ordering_fields.append(f"repeat_cells={classical_state.get('repeat_cells')}")
    elif classical_state.get("supercell_shape") is not None:
        ordering_fields.append(f"supercell_shape={classical_state.get('supercell_shape')}")
    if ordering_fields:
        lines.append(" ".join(ordering_fields))
    return lines


def _cpn_plot_supercell_shape(summary, resolved_cpn_state):
    explicit = resolved_cpn_state.get("supercell_shape")
    if explicit:
        shape = [int(value) for value in explicit]
        while len(shape) < 3:
            shape.append(1)
        return shape[:3]

    max_index = [0, 0, 0]
    for item in summary.get("local_observables", []):
        cell = item.get("cell", [0, 0, 0])
        for axis in range(min(3, len(cell))):
            max_index[axis] = max(max_index[axis], int(cell[axis]))
    return [value + 1 for value in max_index]


def _build_cpn_local_ray_plot_state(
    payload,
    resolved_cpn_state,
    spatial_dimension,
    *,
    commensurate_cells,
    incommensurate_cells,
):
    try:
        summary = build_cpn_local_observable_summary(payload, resolved_cpn_state)
    except ValueError as exc:
        return {
            "site_frames": [],
            "state_kind": resolved_cpn_state.get("state_kind"),
            "manifold": resolved_cpn_state.get("manifold"),
            "ordering": resolved_cpn_state.get("ordering", {}),
            "supercell_shape": list(resolved_cpn_state.get("supercell_shape", [])),
            "local_ray_count": len(resolved_cpn_state.get("local_rays", [])),
            "spatial_dimension": spatial_dimension,
            "plot_reason": f"CP^(N-1) local-ray observable projection failed: {exc}",
        }
    if summary is None:
        return None

    lattice = payload.get("lattice", {})
    lattice_vectors = resolve_lattice_vectors(lattice)
    supercell_shape = _cpn_plot_supercell_shape(summary, resolved_cpn_state)
    ordering = resolved_cpn_state.get("ordering", {})
    ordering_kind = _normalized_ordering_kind(ordering)
    magnetic_repeat_cells = _magnetic_repeat_cells(
        spatial_dimension,
        ordering_kind,
        commensurate_cells,
        incommensurate_cells,
    )
    repeat_cells = [
        max(1, int(supercell_shape[axis])) * max(1, int(magnetic_repeat_cells[axis]))
        for axis in range(3)
    ]
    base_position = _basis_position(lattice, 0, 1)
    base_cartesian = fractional_to_cartesian([base_position], lattice_vectors)[0]
    palette = _cpn_orbital_palette(summary["orbital_count"])
    display_rotation = _default_display_rotation()
    expanded_sites = []
    for mx in range(magnetic_repeat_cells[0]):
        for my in range(magnetic_repeat_cells[1]):
            for mz in range(magnetic_repeat_cells[2]):
                magnetic_offset = [
                    int(mx) * int(supercell_shape[0]),
                    int(my) * int(supercell_shape[1]),
                    int(mz) * int(supercell_shape[2]),
                ]
                for item in summary["local_observables"]:
                    base_cell_index = [int(value) for value in item.get("cell", [0, 0, 0])]
                    cell_index = [
                        int(base_cell_index[axis]) + int(magnetic_offset[axis])
                        for axis in range(3)
                    ]
                    cell_shift = _cell_origin(lattice_vectors, cell_index)
                    cart_position = _vector_add(base_cartesian, cell_shift)
                    spin_expectation = item.get("spin_expectation", [0.0, 0.0, 1.0])
                    if _vector_norm(spin_expectation) <= 1e-12:
                        direction = [0.0, 0.0, 1.0]
                    else:
                        direction = _normalize(spin_expectation)
                    display_direction = direction if spatial_dimension <= 2 else _rotate_vector(direction, display_rotation["matrix"])
                    color = palette[int(item.get("dominant_orbital_index", 0)) % len(palette)]
                    annotation = (
                        f"{item.get('dominant_orbital_label', 'orb')} "
                        f"(w={float(item.get('dominant_orbital_weight', 0.0)):.3f}, "
                        f"|<S>|={float(item.get('spin_polarization_norm', 0.0)):.3f})"
                    )
                    expanded_sites.append(
                        {
                            "basis_index": 0,
                            "label": item.get("dominant_orbital_label", "orb"),
                            "position": cart_position,
                            "direction": direction,
                            "display_direction": display_direction,
                            "color": color,
                            "cell": list(cell_index),
                            "magnetic_cell_index": [int(mx), int(my), int(mz)],
                            "spin_polarization_norm": float(item.get("spin_polarization_norm", 0.0)),
                            "annotation": annotation,
                        }
                    )

    plot_options = payload.get("plot_options", {})
    render_mode = "chain" if spatial_dimension <= 1 else "plane" if spatial_dimension == 2 else "structure"
    return {
        "site_frames": [],
        "state_kind": resolved_cpn_state.get("state_kind"),
        "manifold": resolved_cpn_state.get("manifold"),
        "ordering": ordering,
        "ordering_kind": ordering_kind,
        "supercell_shape": list(supercell_shape),
        "magnetic_repeat_cells": list(magnetic_repeat_cells),
        "repeat_cells": list(repeat_cells),
        "local_ray_count": len(resolved_cpn_state.get("local_rays", [])),
        "spatial_dimension": spatial_dimension,
        "observable_mode": "cpn_local_observables",
        "color_mode": "dominant_orbital",
        "local_dimension": int(summary["local_dimension"]),
        "orbital_count": int(summary["orbital_count"]),
        "orbital_labels": list(summary["orbital_labels"]),
        "local_observables": list(summary["local_observables"]),
        "expanded_sites": expanded_sites,
        "legend_title": "Dominant Orbital",
        "orbital_legend": [
            {"orbital_index": index, "label": label, "color": palette[index % len(palette)]}
            for index, label in enumerate(summary["orbital_labels"])
        ],
        "basis_legend": [
            {"basis_index": index, "label": label, "color": palette[index % len(palette)]}
            for index, label in enumerate(summary["orbital_labels"])
        ],
        "unit_cell_segments": _build_unit_cell_segments(lattice_vectors, repeat_cells, spatial_dimension),
        "lattice_vectors": lattice_vectors,
        "render_mode": render_mode,
        "view": _default_view(spatial_dimension),
        "style": _merged_classical_style(plot_options),
        "figure_size": _resolved_figure_size(plot_options, render_mode),
        "display_rotation": {
            "kind": display_rotation["kind"],
            "source_direction": display_rotation["source_direction"],
            "target_direction": display_rotation["target_direction"],
        },
        "lattice_labels": _lattice_label_positions(lattice_vectors, spatial_dimension),
    }


def _build_classical_plot_state(payload, commensurate_cells, incommensurate_cells):
    classical_state = _get_classical_state(payload)
    frames = classical_state.get("site_frames", [])
    lattice = payload.get("lattice", {})
    bonds = payload.get("simplified_model", {}).get("bonds", payload.get("bonds", []))
    spatial_dimension = infer_spatial_dimension(lattice, bonds)
    resolved_cpn_state = resolve_cpn_classical_state_payload(classical_state)
    plot_options = payload.get("plot_options", {})
    commensurate_cells = plot_options.get("commensurate_cells", commensurate_cells)
    incommensurate_cells = plot_options.get("incommensurate_cells", incommensurate_cells)
    if not frames:
        if resolved_cpn_state.get("local_rays"):
            cpn_plot_state = _build_cpn_local_ray_plot_state(
                payload,
                resolved_cpn_state,
                spatial_dimension,
                commensurate_cells=commensurate_cells,
                incommensurate_cells=incommensurate_cells,
            )
            if cpn_plot_state is not None:
                return cpn_plot_state
        return {
            "site_frames": [],
            "ordering": {},
            "spatial_dimension": spatial_dimension,
            "plot_reason": "Classical-state plotting requires a classical reference state with either spin site_frames or CP^(N-1) local_rays",
        }
    ordering = classical_state.get("ordering", {})
    ordering_kind = _normalized_ordering_kind(ordering)
    q_vector = ordering.get("q_vector", [0.0, 0.0, 0.0])
    magnetic_periods = _magnetic_periods(q_vector, ordering_kind, spatial_dimension)
    magnetic_repeat_cells = _magnetic_repeat_cells(
        spatial_dimension,
        ordering_kind,
        commensurate_cells,
        incommensurate_cells,
    )
    repeat_cells = _repeat_cells_from_magnetic_periods(
        spatial_dimension,
        ordering_kind,
        magnetic_periods=magnetic_periods,
        commensurate_cells=commensurate_cells,
        incommensurate_cells=incommensurate_cells,
    )
    lattice_vectors = resolve_lattice_vectors(lattice)
    site_count = max((int(frame["site"]) for frame in frames), default=-1) + 1
    if site_count <= 0:
        site_count = len(lattice.get("positions") or []) or 1

    color_cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    display_rotation = _default_display_rotation()
    expanded_sites = []
    for ix in range(repeat_cells[0]):
        for iy in range(repeat_cells[1]):
            for iz in range(repeat_cells[2]):
                cell_index = [ix, iy, iz]
                cell_shift = [
                    ix * lattice_vectors[0][axis] + iy * lattice_vectors[1][axis] + iz * lattice_vectors[2][axis]
                    for axis in range(3)
                ]
                for basis_index in range(site_count):
                    base_position = _basis_position(lattice, basis_index, site_count)
                    cart_position = _vector_add(fractional_to_cartesian([base_position], lattice_vectors)[0], cell_shift)
                    frame = frames[basis_index] if basis_index < len(frames) else frames[0]
                    direction = _rotate_spin(frame["direction"], q_vector, cell_index)
                    display_direction = direction if spatial_dimension <= 2 else _rotate_vector(direction, display_rotation["matrix"])
                    expanded_sites.append(
                        {
                            "basis_index": basis_index,
                            "label": f"Atom {basis_index}",
                            "position": cart_position,
                            "direction": direction,
                            "display_direction": display_direction,
                            "color": color_cycle[basis_index % len(color_cycle)],
                        }
                    )

    basis_legend = [
        {"basis_index": index, "label": label, "color": color_cycle[index % len(color_cycle)]}
        for index, label in enumerate(_basis_labels(site_count))
    ]
    unit_cell_segments = _build_unit_cell_segments(lattice_vectors, repeat_cells, spatial_dimension)
    render_mode = "chain" if spatial_dimension <= 1 else "plane" if spatial_dimension == 2 else "structure"
    return {
        "site_frames": frames,
        "ordering": ordering,
        "ordering_kind": ordering_kind,
        "magnetic_periods": magnetic_periods,
        "magnetic_repeat_cells": magnetic_repeat_cells,
        "repeat_cells": repeat_cells,
        "spatial_dimension": spatial_dimension,
        "expanded_sites": expanded_sites,
        "basis_legend": basis_legend,
        "unit_cell_segments": unit_cell_segments,
        "lattice_vectors": lattice_vectors,
        "render_mode": render_mode,
        "view": _default_view(spatial_dimension),
        "style": _merged_classical_style(plot_options),
        "figure_size": _resolved_figure_size(plot_options, render_mode),
        "display_rotation": {
            "kind": display_rotation["kind"],
            "source_direction": display_rotation["source_direction"],
            "target_direction": display_rotation["target_direction"],
        },
        "lattice_labels": _lattice_label_positions(lattice_vectors, spatial_dimension),
    }


def _render_classical_state_chain(classical_state, output_path):
    expanded_sites = classical_state.get("expanded_sites", [])
    basis_legend = classical_state.get("basis_legend", [])
    style = classical_state.get("style", _default_structure_style())
    fig, ax = plt.subplots(figsize=classical_state.get("figure_size", _default_figure_size("chain")))

    xs = [site["position"][0] for site in expanded_sites]
    ys = [0.0 for _ in expanded_sites]
    if not xs:
        xs = [0.0]
        ys = [0.0]

    for segment in classical_state.get("unit_cell_segments", []):
        start = segment["start"]
        end = segment["end"]
        ax.plot([start[0], end[0]], [0.0, 0.0], color="#9ca3af", linewidth=1.2, alpha=0.8, zorder=1)

    for site in expanded_sites:
        x = site["position"][0]
        direction = _normalize(site.get("display_direction", site["direction"]))
        ax.scatter(
            [x],
            [0.0],
            color=style.get("atom_fill", "#c9c9c9"),
            s=float(style.get("atom_size", 220.0)),
            edgecolors=site["color"],
            linewidths=float(style.get("atom_edge_width", 2.2)),
            zorder=3,
        )
        ax.quiver(
            [x],
            [0.0],
            [direction[0]],
            [direction[1]],
            angles="xy",
            scale_units="xy",
            scale=1.8,
            color=style.get("spin_color", "#d00000"),
            width=0.004,
            zorder=4,
        )

    ax.set_title("Classical Ground State")
    ax.set_xlabel("Chain direction")
    ax.set_yticks([])
    ax.grid(True, axis="x", alpha=0.2)
    ax.set_aspect("equal", adjustable="datalim")
    if basis_legend:
        legend_handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor=style.get("atom_fill", "#c9c9c9"),
                markeredgecolor=item["color"],
                markeredgewidth=2.0,
                markersize=8,
                label=item["label"],
            )
            for item in basis_legend
        ]
        ax.legend(handles=legend_handles, title=_classical_legend_title(classical_state), loc="upper right", frameon=True)
    has_summary = _draw_figure_summary(fig, classical_state.get("summary_lines"), y_top=0.93)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88 if has_summary else 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_classical_state_plane(classical_state, output_path):
    expanded_sites = classical_state.get("expanded_sites", [])
    basis_legend = classical_state.get("basis_legend", [])
    style = classical_state.get("style", _default_structure_style())
    fig, ax = plt.subplots(figsize=classical_state.get("figure_size", _default_figure_size("plane")))

    for segment in classical_state.get("unit_cell_segments", []):
        start = segment["start"]
        end = segment["end"]
        segment_style = segment.get("style", "supercell")
        color = "#0f8b8d" if segment_style == "primitive" else "#8f8f8f"
        linewidth = 1.6 if segment_style == "primitive" else 1.3
        alpha = 0.95 if segment_style == "primitive" else 0.9
        ax.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=linewidth, alpha=alpha, zorder=1)

    for site in expanded_sites:
        x, y = site["position"][:2]
        direction = _normalize(site.get("display_direction", site["direction"]))
        ax.scatter(
            [x],
            [y],
            color=style.get("atom_fill", "#c9c9c9"),
            s=float(style.get("atom_size", 220.0)),
            edgecolors=site["color"],
            linewidths=float(style.get("atom_edge_width", 2.2)),
            zorder=3,
        )
        ax.quiver(
            [x],
            [y],
            [direction[0]],
            [direction[1]],
            angles="xy",
            scale_units="xy",
            scale=1.8,
            color=style.get("spin_color", "#d00000"),
            width=0.004,
            zorder=4,
        )

    for label in classical_state.get("lattice_labels", []):
        anchor = label["position"]
        ax.text(anchor[0], anchor[1], label["text"], fontsize=12, weight="bold", color="#111111")

    xs = [site["position"][0] for site in expanded_sites] + [coord for segment in classical_state.get("unit_cell_segments", []) for coord in [segment["start"][0], segment["end"][0]]]
    ys = [site["position"][1] for site in expanded_sites] + [coord for segment in classical_state.get("unit_cell_segments", []) for coord in [segment["start"][1], segment["end"][1]]]
    if not xs:
        xs = [0.0]
        ys = [0.0]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    x_margin = max(0.2, 0.08 * max(x_span, 1.0))
    y_margin = max(0.2, 0.08 * max(y_span, 1.0))
    ax.set_xlim(min(xs) - x_margin, max(xs) + x_margin)
    ax.set_ylim(min(ys) - y_margin, max(ys) + y_margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("Classical Ground State")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.2)
    if basis_legend:
        legend_handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor=style.get("atom_fill", "#c9c9c9"),
                markeredgecolor=item["color"],
                markeredgewidth=2.0,
                markersize=8,
                label=item["label"],
            )
            for item in basis_legend
        ]
        ax.legend(handles=legend_handles, title=_classical_legend_title(classical_state), loc="upper right", frameon=True)
    has_summary = _draw_figure_summary(fig, classical_state.get("summary_lines"), y_top=0.93)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88 if has_summary else 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _build_plot_payload(payload, commensurate_cells=2, incommensurate_cells=5):
    lswt = payload.get("lswt", {})
    dispersion = lswt.get("linear_spin_wave", {}).get("dispersion", [])
    band_count = max((len(point.get("bands", [])) for point in dispersion), default=0)
    plot_options = payload.get("plot_options", {})
    classical_state = _build_classical_plot_state(
        payload,
        commensurate_cells=commensurate_cells,
        incommensurate_cells=incommensurate_cells,
    )
    if isinstance(classical_state, dict):
        classical_state = {
            **classical_state,
            "summary_lines": _classical_summary_lines(payload, classical_state),
        }
    return {
        "metadata": {
            "model_name": payload.get("model_name", ""),
            "backend": lswt.get("backend", {}).get("name", "unknown"),
            "classical_method": payload.get("classical", {}).get("chosen_method", ""),
            "lswt_status": lswt.get("status", "missing"),
            "gswt_status": payload.get("gswt", {}).get("status", "missing"),
        },
        "classical_state": classical_state,
        "gswt_diagnostics": {
            "status": payload.get("gswt", {}).get("status", "missing"),
            "dispersion": payload.get("gswt", {}).get("dispersion", []),
            "path": payload.get("gswt", {}).get("path", {}),
            "instability": payload.get("gswt", {}).get("diagnostics", {}).get("instability", {}),
            "summary_lines": _gswt_summary_lines(payload, payload.get("gswt", {})),
            "figure_size": _resolved_lswt_figure_size(plot_options),
            "style": _merged_lswt_style(plot_options),
        },
        "lswt_dispersion": {
            "dispersion": dispersion,
            "band_count": band_count,
            "q_points": [point.get("q", []) for point in dispersion],
            "omega_min": min((point.get("omega", 0.0) for point in dispersion), default=0.0),
            "omega_max": max((point.get("omega", 0.0) for point in dispersion), default=0.0),
            "path": lswt.get("path", {}),
            "summary_lines": _lswt_summary_lines(payload, dispersion, band_count),
            "figure_size": _resolved_lswt_figure_size(plot_options),
            "style": _merged_lswt_style(plot_options),
        },
        "thermodynamics": {
            "grid": payload.get("thermodynamics_result", {}).get("grid", []),
            "summary_lines": _thermodynamics_summary_lines(
                payload,
                payload.get("thermodynamics_result", {}).get("grid", []),
            ),
            "figure_size": _resolved_thermodynamics_figure_size(plot_options),
            "style": _merged_thermodynamics_style(plot_options),
        },
    }


def _resolve_plot_payload(payload, commensurate_cells=2, incommensurate_cells=5):
    if _is_prebuilt_plot_payload(payload):
        return payload
    return _build_plot_payload(
        payload,
        commensurate_cells=commensurate_cells,
        incommensurate_cells=incommensurate_cells,
    )


def _render_classical_state(classical_state, output_path):
    render_mode = classical_state.get("render_mode", "structure")
    if render_mode == "chain":
        _render_classical_state_chain(classical_state, output_path)
        return
    if render_mode == "plane":
        _render_classical_state_plane(classical_state, output_path)
        return

    expanded_sites = classical_state.get("expanded_sites", [])
    spatial_dimension = classical_state.get("spatial_dimension", 2)
    basis_legend = classical_state.get("basis_legend", [])
    lattice_vectors = classical_state.get("lattice_vectors", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    view = classical_state.get("view", _default_view(spatial_dimension))
    style = classical_state.get("style", _default_structure_style())
    fig = plt.figure(figsize=classical_state.get("figure_size", _default_figure_size("structure")))
    ax = fig.add_subplot(111, projection="3d")

    primitive_scale = min(_vector_norm(vector) for vector in lattice_vectors if _vector_norm(vector) > 1e-12)
    arrow_length = float(style.get("arrow_length_factor", 0.42)) * primitive_scale if primitive_scale > 1e-12 else 0.8

    for segment in classical_state.get("unit_cell_segments", []):
        start = segment["start"]
        end = segment["end"]
        segment_style = segment.get("style", "supercell")
        color = "#0f8b8d" if segment_style == "primitive" else "#8f8f8f"
        linewidth = 1.6 if segment_style == "primitive" else 1.3
        alpha = 0.95 if segment_style == "primitive" else 0.9
        ax.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            [start[2], end[2]],
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=1,
        )

    for site in expanded_sites:
        x, y, z = site["position"]
        u, v, w = _normalize(site.get("display_direction", site["direction"]))
        ax.scatter(
            [x],
            [y],
            [z],
            color=style.get("atom_fill", "#c9c9c9"),
            s=float(style.get("atom_size", 220.0)),
            edgecolors=site["color"],
            linewidths=float(style.get("atom_edge_width", 2.2)),
            depthshade=True,
            zorder=3,
        )
        ax.quiver(
            [x],
            [y],
            [z],
            [u],
            [v],
            [w],
            color=style.get("spin_color", "#d00000"),
            length=arrow_length,
            normalize=True,
            arrow_length_ratio=0.35,
            linewidth=float(style.get("arrow_line_width", 2.4)),
            zorder=4,
        )

    if spatial_dimension <= 2:
        for label in classical_state.get("lattice_labels", []):
            anchor = label["position"]
            ax.text(anchor[0], anchor[1], anchor[2], label["text"], fontsize=16, weight="bold", color="#111111")
    else:
        for label in classical_state.get("lattice_labels", []):
            anchor = label["position"]
            ax.text(anchor[0], anchor[1], anchor[2], label["text"], fontsize=13, weight="bold", color="#111111")

    xs = [site["position"][0] for site in expanded_sites] + [coord for segment in classical_state.get("unit_cell_segments", []) for coord in [segment["start"][0], segment["end"][0]]]
    ys = [site["position"][1] for site in expanded_sites] + [coord for segment in classical_state.get("unit_cell_segments", []) for coord in [segment["start"][1], segment["end"][1]]]
    zs = [site["position"][2] for site in expanded_sites] + [coord for segment in classical_state.get("unit_cell_segments", []) for coord in [segment["start"][2], segment["end"][2]]]
    if not zs:
        zs = [0.0]

    x_span = max(xs) - min(xs) if xs else 1.0
    y_span = max(ys) - min(ys) if ys else 1.0
    z_span = max(zs) - min(zs) if zs else 1.0
    x_margin = max(0.2, 0.08 * max(x_span, primitive_scale))
    y_margin = max(0.2, 0.08 * max(y_span, primitive_scale))
    z_margin = max(0.1, 0.15 * max(z_span, primitive_scale))
    ax.set_xlim(min(xs) - x_margin, max(xs) + x_margin)
    ax.set_ylim(min(ys) - y_margin, max(ys) + y_margin)
    ax.set_zlim(min(zs) - z_margin, max(zs) + z_margin if spatial_dimension >= 3 else max(z_margin, primitive_scale * 0.4))
    ax.set_box_aspect((max(x_span, 1.0), max(y_span, 1.0), max(z_span, primitive_scale * 0.35 if spatial_dimension <= 2 else 1.0)))
    ax.view_init(elev=float(view.get("elev", 18.0)), azim=float(view.get("azim", -64.0)))
    ax.set_proj_type("persp")
    ax.set_axis_off()

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=style.get("atom_fill", "#c9c9c9"),
            markeredgecolor=item["color"],
            markeredgewidth=2.0,
            markersize=9,
            label=item["label"],
        )
        for item in basis_legend
    ]
    if legend_handles:
        ax.legend(handles=legend_handles, title=_classical_legend_title(classical_state), loc="upper right", frameon=True)
    triad = fig.add_axes([0.07, 0.08, 0.12, 0.16])
    triad.axis("off")
    triad.annotate("", xy=(0.88, 0.30), xytext=(0.18, 0.30), arrowprops={"arrowstyle": "-|>", "color": "#d00000", "lw": 3})
    triad.annotate("", xy=(0.30, 0.88), xytext=(0.30, 0.18), arrowprops={"arrowstyle": "-|>", "color": "#c78a00", "lw": 3})
    triad.annotate("", xy=(0.16, 0.16), xytext=(0.30, 0.30), arrowprops={"arrowstyle": "-|>", "color": "#0f8b8d", "lw": 3})
    triad.text(0.92, 0.22, "x", fontsize=12, weight="bold")
    triad.text(0.22, 0.90, "y", fontsize=12, weight="bold")
    triad.text(0.06, 0.06, "z", fontsize=12, weight="bold")
    ax.set_title("Classical Ground State")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.92)
    _draw_figure_summary(fig, classical_state.get("summary_lines"), y_top=0.95)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_dispersion(dispersion, output_path, figure_size=None, style=None, summary_lines=None, title="LSWT Dispersion"):
    style = style or _default_lswt_style()
    fig, ax = plt.subplots(figsize=figure_size or [7.0, 4.5])
    q_indices = list(range(len(dispersion)))
    band_count = max(len(point.get("bands", [])) for point in dispersion)
    for band_index in range(band_count):
        ys = []
        for point in dispersion:
            bands = point.get("bands", [])
            ys.append(bands[band_index] if band_index < len(bands) else float("nan"))
        ax.plot(q_indices, ys, linewidth=float(style.get("line_width", 1.5)))
    fig.suptitle(title, y=0.98)
    ax.set_xlabel("High-symmetry path")
    ax.set_ylabel("omega")
    ax.grid(True, alpha=float(style.get("grid_alpha", 0.25)))
    has_summary = _draw_figure_summary(fig, summary_lines, y_top=0.93)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88 if has_summary else 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_dispersion_with_path(dispersion, path_metadata, output_path, figure_size=None, style=None, summary_lines=None, title="LSWT Dispersion"):
    style = style or _default_lswt_style()
    fig, ax = plt.subplots(figsize=figure_size or [7.0, 4.5])
    q_indices = list(range(len(dispersion)))
    band_count = max(len(point.get("bands", [])) for point in dispersion)
    for band_index in range(band_count):
        ys = []
        for point in dispersion:
            bands = point.get("bands", [])
            ys.append(bands[band_index] if band_index < len(bands) else float("nan"))
        ax.plot(q_indices, ys, linewidth=float(style.get("line_width", 1.5)))

    node_indices = path_metadata.get("node_indices", [])
    labels = path_metadata.get("labels", [])
    if node_indices and labels and len(node_indices) == len(labels):
        for index in node_indices:
            ax.axvline(
                index,
                color="#9ca3af",
                linewidth=float(style.get("node_line_width", 0.8)),
                alpha=float(style.get("node_alpha", 0.7)),
            )
        ax.set_xticks(node_indices)
        ax.set_xticklabels(labels)
    fig.suptitle(title, y=0.98)
    ax.set_xlabel("High-symmetry path")
    ax.set_ylabel("omega")
    ax.grid(True, alpha=float(style.get("grid_alpha", 0.25)))
    has_summary = _draw_figure_summary(fig, summary_lines, y_top=0.93)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.88 if has_summary else 0.94])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_thermodynamics(thermodynamics_grid, output_path, uncertainties=None, figure_size=None, style=None, summary_lines=None):
    style = style or _default_thermodynamics_style()
    temperatures = [point.get("temperature") for point in thermodynamics_grid]
    series = [
        ("energy", "Energy"),
        ("free_energy", "Free energy"),
        ("specific_heat", "Specific heat"),
        ("magnetization", "Magnetization"),
        ("susceptibility", "Susceptibility"),
        ("entropy", "Entropy"),
    ]

    fig, axes = plt.subplots(3, 2, figsize=figure_size or [9.0, 9.0], sharex=True)
    axes = axes.flatten()
    for axis, (key, label) in zip(axes, series):
        values = [point.get(key, float("nan")) for point in thermodynamics_grid]
        if uncertainties and key in uncertainties and len(uncertainties[key]) == len(values):
            axis.errorbar(
                temperatures,
                values,
                yerr=uncertainties[key],
                marker="o",
                linewidth=float(style.get("line_width", 1.6)),
                markersize=float(style.get("marker_size", 4.0)),
                capsize=float(style.get("capsize", 3.0)),
            )
        else:
            axis.plot(
                temperatures,
                values,
                marker="o",
                linewidth=float(style.get("line_width", 1.6)),
                markersize=float(style.get("marker_size", 4.0)),
            )
        axis.set_ylabel(label)
        axis.grid(True, alpha=float(style.get("grid_alpha", 0.25)))
    axes[-2].set_xlabel("Temperature")
    axes[-1].set_xlabel("Temperature")
    fig.suptitle("Classical Thermodynamics", y=0.99)
    has_summary = _draw_figure_summary(fig, summary_lines, y_top=0.955)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.90 if has_summary else 0.95])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _lt_eigenvector_magnitudes(lt_result):
    magnitudes = []
    for element in lt_result.get("eigenvector", []):
        if isinstance(element, dict):
            real_part = float(element.get("real", 0.0))
            imag_part = float(element.get("imag", 0.0))
        elif element:
            first = element[0]
            real_part = float(first.get("real", 0.0))
            imag_part = float(first.get("imag", 0.0))
        else:
            real_part = 0.0
            imag_part = 0.0
        magnitudes.append((real_part**2 + imag_part**2) ** 0.5)
    return magnitudes


def _lt_diagnostic_summary(result, label_value_pairs):
    lines = [f"q = {result.get('q', 'n/a')}"]
    for label, value in label_value_pairs:
        lines.append(f"{label} = {value}")
    constraint_recovery = result.get("constraint_recovery", {})
    if "strong_constraint_residual" in constraint_recovery:
        lines.append(f"residual = {constraint_recovery['strong_constraint_residual']}")
    return "\n".join(lines)


def _auto_resolution_summary(auto_resolution):
    if not auto_resolution or not auto_resolution.get("enabled"):
        return ""
    lines = [
        f"recommended = {auto_resolution.get('recommended_method', 'n/a')}",
        f"initial = {auto_resolution.get('initial_method', 'n/a')}",
        f"resolved = {auto_resolution.get('resolved_method', 'n/a')}",
        f"reason = {auto_resolution.get('reason', 'n/a')}",
    ]
    if auto_resolution.get("lt_residual") is not None:
        lines.append(f"lt_residual = {auto_resolution.get('lt_residual')}")
    if auto_resolution.get("generalized_lt_residual") is not None:
        lines.append(f"generalized_lt_residual = {auto_resolution.get('generalized_lt_residual')}")
    return "\n".join(lines)


def _render_lt_diagnostics(lt_result, generalized_lt_result, auto_resolution, output_path):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))

    lt_magnitudes = _lt_eigenvector_magnitudes(lt_result)
    if lt_magnitudes:
        axes[0].bar(range(len(lt_magnitudes)), lt_magnitudes, color="#1f77b4")
    axes[0].set_title("LT Lowest-Mode Amplitudes")
    axes[0].set_xlabel("Sublattice index")
    axes[0].set_ylabel("|u|")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].text(
        0.02,
        0.98,
        _lt_diagnostic_summary(
            lt_result,
            label_value_pairs=[("lambda_min", lt_result.get("lowest_eigenvalue", "n/a"))],
        ),
        transform=axes[0].transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85, "edgecolor": "#cccccc"},
    )

    lambda_values = generalized_lt_result.get("lambda", []) if generalized_lt_result else []
    if lambda_values:
        axes[1].bar(range(len(lambda_values)), lambda_values, color="#d62728")
    axes[1].axhline(0.0, color="#666666", linewidth=1.0, alpha=0.7)
    axes[1].set_title("Generalized LT Lagrange Parameters")
    axes[1].set_xlabel("Sublattice index")
    axes[1].set_ylabel("lambda")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].text(
        0.02,
        0.98,
        _lt_diagnostic_summary(
            generalized_lt_result or {},
            label_value_pairs=[
                (
                    "bound",
                    generalized_lt_result.get("tightened_lower_bound", "n/a") if generalized_lt_result else "n/a",
                )
            ],
        ),
        transform=axes[1].transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85, "edgecolor": "#cccccc"},
    )

    auto_summary = _auto_resolution_summary(auto_resolution)
    if auto_summary:
        fig.text(
            0.5,
            0.02,
            auto_summary,
            ha="center",
            va="bottom",
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.82, "edgecolor": "#cccccc"},
        )

    fig.suptitle("LT / Generalized LT Diagnostics", y=0.98)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def render_plots(payload, output_dir, commensurate_cells=2, incommensurate_cells=5):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_payload = _resolve_plot_payload(
        payload,
        commensurate_cells=commensurate_cells,
        incommensurate_cells=incommensurate_cells,
    )
    (output_dir / "plot_payload.json").write_text(json.dumps(plot_payload, indent=2, sort_keys=True), encoding="utf-8")

    result = {
        "status": "ok",
        "plots": {
            "classical_state": {"status": "skipped", "path": None},
            "gswt_diagnostics": {"status": "skipped", "path": None, "reason": ""},
            "lswt_dispersion": {"status": "skipped", "path": None, "reason": ""},
            "thermodynamics": {"status": "skipped", "path": None, "reason": ""},
            "lt_diagnostics": {"status": "skipped", "path": None, "reason": ""},
        },
    }

    classical_state = plot_payload.get("classical_state", {})
    if classical_state.get("expanded_sites"):
        classical_path = output_dir / "classical_state.png"
        _render_classical_state(classical_state, classical_path)
        result["plots"]["classical_state"] = {"status": "ok", "path": str(classical_path)}
    elif classical_state.get("plot_reason"):
        result["plots"]["classical_state"] = {
            "status": "skipped",
            "path": None,
            "reason": classical_state.get("plot_reason", ""),
        }

    gswt_payload = plot_payload.get("gswt_diagnostics", {})
    gswt_dispersion = gswt_payload.get("dispersion", [])
    gswt_instability = gswt_payload.get("instability", {})
    if gswt_dispersion or gswt_instability:
        gswt_path = output_dir / "gswt_diagnostics.png"
        _render_gswt_diagnostics(gswt_payload, gswt_path)
        result["plots"]["gswt_diagnostics"] = {"status": "ok", "path": str(gswt_path)}
    else:
        gswt_error = payload.get("gswt", {}).get("error", {})
        reason = ""
        if gswt_error:
            reason = f"{gswt_error.get('code', 'gswt-error')}: {gswt_error.get('message', '')}".strip()
        elif payload.get("gswt"):
            reason = "GSWT diagnostics unavailable"
        result["plots"]["gswt_diagnostics"] = {"status": "skipped", "path": None, "reason": reason}

    lswt_status = plot_payload.get("metadata", {}).get("lswt_status", payload.get("lswt", {}).get("status", "missing"))
    dispersion_payload = plot_payload.get("lswt_dispersion", {})
    dispersion = dispersion_payload.get("dispersion", [])
    if lswt_status == "ok" and dispersion:
        dispersion_path = output_dir / "lswt_dispersion.png"
        path_metadata = dispersion_payload.get("path", {})
        if path_metadata:
            _render_dispersion_with_path(
                dispersion,
                path_metadata,
                dispersion_path,
                figure_size=dispersion_payload.get("figure_size"),
                style=dispersion_payload.get("style"),
                summary_lines=dispersion_payload.get("summary_lines"),
            )
        else:
            _render_dispersion(
                dispersion,
                dispersion_path,
                figure_size=dispersion_payload.get("figure_size"),
                style=dispersion_payload.get("style"),
                summary_lines=dispersion_payload.get("summary_lines"),
            )
        result["plots"]["lswt_dispersion"] = {"status": "ok", "path": str(dispersion_path)}
    else:
        reason = "LSWT result unavailable"
        lswt_error = payload.get("lswt", {}).get("error", {})
        if lswt_error:
            reason = f"{lswt_error.get('code', 'lswt-error')}: {lswt_error.get('message', '')}".strip()
        result["plots"]["lswt_dispersion"] = {"status": "skipped", "path": None, "reason": reason}
        if result["plots"]["classical_state"]["status"] == "ok":
            result["status"] = "partial"

    thermodynamics_payload = plot_payload.get("thermodynamics", {})
    thermodynamics = payload.get("thermodynamics_result", {})
    thermo_grid = thermodynamics_payload.get("grid", thermodynamics.get("grid", []))
    if thermo_grid:
        thermodynamics_path = output_dir / "thermodynamics.png"
        _render_thermodynamics(
            thermo_grid,
            thermodynamics_path,
            uncertainties=thermodynamics.get("uncertainties"),
            figure_size=thermodynamics_payload.get("figure_size"),
            style=thermodynamics_payload.get("style"),
            summary_lines=thermodynamics_payload.get("summary_lines"),
        )
        result["plots"]["thermodynamics"] = {"status": "ok", "path": str(thermodynamics_path)}
    else:
        result["plots"]["thermodynamics"] = {
            "status": "skipped",
            "path": None,
            "reason": "Thermodynamics result unavailable",
        }

    lt_result = payload.get("lt_result", {})
    generalized_lt_result = payload.get("generalized_lt_result", {})
    if lt_result or generalized_lt_result:
        diagnostics_path = output_dir / "lt_diagnostics.png"
        _render_lt_diagnostics(
            lt_result,
            generalized_lt_result,
            payload.get("classical", {}).get("auto_resolution", {}),
            diagnostics_path,
        )
        result["plots"]["lt_diagnostics"] = {"status": "ok", "path": str(diagnostics_path)}
    else:
        result["plots"]["lt_diagnostics"] = {
            "status": "skipped",
            "path": None,
            "reason": "LT diagnostics unavailable",
        }

    return result


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def _load_or_materialize_plot_payload(input_path, commensurate_cells=2, incommensurate_cells=5):
    payload = _load_payload(input_path)
    if _is_prebuilt_plot_payload(payload):
        return payload

    if input_path:
        input_path = Path(input_path)
        sibling_plot_payload = input_path.with_name("plot_payload.json")
        if sibling_plot_payload.exists():
            sibling_payload = _load_payload(sibling_plot_payload)
            if not _is_prebuilt_plot_payload(sibling_payload):
                raise ValueError(f"{sibling_plot_payload} exists but is not a valid plot payload")
            return sibling_payload

        plot_payload = _resolve_plot_payload(
            payload,
            commensurate_cells=commensurate_cells,
            incommensurate_cells=incommensurate_cells,
        )
        sibling_plot_payload.write_text(json.dumps(plot_payload, indent=2, sort_keys=True), encoding="utf-8")
        return plot_payload

    return _resolve_plot_payload(
        payload,
        commensurate_cells=commensurate_cells,
        incommensurate_cells=incommensurate_cells,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--commensurate-cells", type=int, default=2)
    parser.add_argument("--incommensurate-cells", type=int, default=5)
    args = parser.parse_args()
    payload = _load_or_materialize_plot_payload(
        args.input,
        commensurate_cells=args.commensurate_cells,
        incommensurate_cells=args.incommensurate_cells,
    )
    print(
        json.dumps(
            render_plots(
                payload,
                output_dir=args.output_dir,
                commensurate_cells=args.commensurate_cells,
                incommensurate_cells=args.incommensurate_cells,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
