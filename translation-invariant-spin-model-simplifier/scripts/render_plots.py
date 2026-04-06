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

from build_lswt_payload import infer_spatial_dimension
from lattice_geometry import fractional_to_cartesian, resolve_lattice_vectors


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
    commensurate_repeat_request = _normalize_repeat_request(commensurate_cells, spatial_dimension, 2)
    incommensurate_repeat_request = _normalize_repeat_request(incommensurate_cells, spatial_dimension, 5)
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


def _build_classical_plot_state(payload, commensurate_cells, incommensurate_cells):
    classical_state = _get_classical_state(payload)
    frames = classical_state.get("site_frames", [])
    lattice = payload.get("lattice", {})
    bonds = payload.get("simplified_model", {}).get("bonds", payload.get("bonds", []))
    spatial_dimension = infer_spatial_dimension(lattice, bonds)
    ordering = classical_state.get("ordering", {})
    ordering_kind = ordering.get("kind", "commensurate")
    q_vector = ordering.get("q_vector", [0.0, 0.0, 0.0])
    plot_options = payload.get("plot_options", {})
    commensurate_cells = plot_options.get("commensurate_cells", commensurate_cells)
    incommensurate_cells = plot_options.get("incommensurate_cells", incommensurate_cells)
    magnetic_periods = _magnetic_periods(q_vector, ordering_kind, spatial_dimension)
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
        "magnetic_periods": magnetic_periods,
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
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_classical_state_plane(classical_state, output_path):
    expanded_sites = classical_state.get("expanded_sites", [])
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
    fig.tight_layout()
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
    return {
        "metadata": {
            "model_name": payload.get("model_name", ""),
            "backend": lswt.get("backend", {}).get("name", "unknown"),
            "classical_method": payload.get("classical", {}).get("chosen_method", ""),
            "lswt_status": lswt.get("status", "missing"),
        },
        "classical_state": classical_state,
        "lswt_dispersion": {
            "dispersion": dispersion,
            "band_count": band_count,
            "q_points": [point.get("q", []) for point in dispersion],
            "omega_min": min((point.get("omega", 0.0) for point in dispersion), default=0.0),
            "omega_max": max((point.get("omega", 0.0) for point in dispersion), default=0.0),
            "path": lswt.get("path", {}),
            "figure_size": _resolved_lswt_figure_size(plot_options),
            "style": _merged_lswt_style(plot_options),
        },
        "thermodynamics": {
            "grid": payload.get("thermodynamics_result", {}).get("grid", []),
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
        ax.legend(handles=legend_handles, title="Basis Atoms", loc="upper right", frameon=True)
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
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_dispersion(dispersion, output_path, figure_size=None, style=None):
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
    ax.set_title("LSWT Dispersion")
    ax.set_xlabel("High-symmetry path")
    ax.set_ylabel("omega")
    ax.grid(True, alpha=float(style.get("grid_alpha", 0.25)))
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_dispersion_with_path(dispersion, path_metadata, output_path, figure_size=None, style=None):
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
    ax.set_title("LSWT Dispersion")
    ax.set_xlabel("High-symmetry path")
    ax.set_ylabel("omega")
    ax.grid(True, alpha=float(style.get("grid_alpha", 0.25)))
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_thermodynamics(thermodynamics_grid, output_path, uncertainties=None, figure_size=None, style=None):
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
    fig.suptitle("Classical Thermodynamics", y=0.98)
    fig.tight_layout()
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
            "lswt_dispersion": {"status": "skipped", "path": None, "reason": ""},
            "thermodynamics": {"status": "skipped", "path": None, "reason": ""},
            "lt_diagnostics": {"status": "skipped", "path": None, "reason": ""},
        },
    }

    classical_state = plot_payload.get("classical_state", {})
    if classical_state.get("site_frames"):
        classical_path = output_dir / "classical_state.png"
        _render_classical_state(classical_state, classical_path)
        result["plots"]["classical_state"] = {"status": "ok", "path": str(classical_path)}

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
            )
        else:
            _render_dispersion(
                dispersion,
                dispersion_path,
                figure_size=dispersion_payload.get("figure_size"),
                style=dispersion_payload.get("style"),
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
