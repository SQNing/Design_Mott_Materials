#!/usr/bin/env python3

import itertools
import math

import numpy as np
from scipy.optimize import minimize

from .boxes import ParameterBox
from .intervals import (
    quadratic_lower_over_radius_interval,
    radius_interval_from_values,
    spectral_lower_from_center_radius,
)

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from classical.cpn_generalized_lt_solver import (
        _active_axes,
        _kernel_at_q,
        _lt_blocks,
        _magnetic_site_count,
        _stable_hermitian_eigh,
        _trust_region_on_sphere,
        _uniform_field_vector,
        _weights_from_log_coordinates,
    )
else:
    from ..cpn_generalized_lt_solver import (
        _active_axes,
        _kernel_at_q,
        _lt_blocks,
        _magnetic_site_count,
        _stable_hermitian_eigh,
        _trust_region_on_sphere,
        _uniform_field_vector,
        _weights_from_log_coordinates,
    )


def search_coordinates_for_model(model, *, weight_bound=1.0):
    active_axes = list(_active_axes(model))
    site_count = max(1, int(_magnetic_site_count(model)))
    names = [f"q{axis}" for axis in active_axes]
    lower = [0.0] * len(active_axes)
    upper = [1.0] * len(active_axes)
    for index in range(max(0, site_count - 1)):
        names.append(f"log_p{index}")
        lower.append(-float(weight_bound))
        upper.append(float(weight_bound))
    return names, lower, upper


def build_search_box(model, *, weight_bound=1.0):
    names, lower, upper = search_coordinates_for_model(model, weight_bound=weight_bound)
    return ParameterBox(names=names, lower=lower, upper=upper, depth=0)


def _active_axis_values(active_axes, point):
    q_vector = [0.0, 0.0, 0.0]
    for offset, axis in enumerate(active_axes):
        q_vector[axis] = float(point[offset])
    return q_vector


def _point_to_weights(model, point):
    site_count = max(1, int(_magnetic_site_count(model)))
    free_count = max(0, site_count - 1)
    if free_count == 0:
        return [1.0]
    coordinates = point[-free_count:]
    p_weights, _, _ = _weights_from_log_coordinates(coordinates)
    return [float(value) for value in p_weights]


def _energy_for_point(model, blocks_payload, q_vector, p_weights):
    local_dimension = int(model["local_dimension"])
    alpha_weights = [float(value) ** -2 for value in p_weights]
    radius_sq = max(0.0, (1.0 - 1.0 / float(local_dimension)) * float(sum(alpha_weights)))
    field, constant_term = _uniform_field_vector(
        blocks_payload["blocks"],
        local_dimension,
        p_weights=p_weights,
        magnetic_site_count=int(blocks_payload["magnetic_site_count"]),
    )
    uniform_kernel = _kernel_at_q(
        blocks_payload["blocks"],
        [0.0, 0.0, 0.0],
        p_weights=p_weights,
        magnetic_site_count=int(blocks_payload["magnetic_site_count"]),
    )
    _, uniform_relative_energy, _ = _trust_region_on_sphere(
        uniform_kernel,
        field,
        radius_sq,
    )
    uniform_energy = float(constant_term + uniform_relative_energy)

    nonzero_energy = uniform_energy
    if any(abs(float(component)) > 1.0e-12 for component in q_vector):
        kernel = _kernel_at_q(
            blocks_payload["blocks"],
            q_vector,
            p_weights=p_weights,
            magnetic_site_count=int(blocks_payload["magnetic_site_count"]),
        )
        eigenvalues, _ = _stable_hermitian_eigh(kernel)
        nonzero_energy = float(constant_term + radius_sq * float(eigenvalues[0]))

    if nonzero_energy < uniform_energy - 1.0e-12:
        branch_kind = "nonzero-q"
        chosen = nonzero_energy
    elif uniform_energy < nonzero_energy - 1.0e-12:
        branch_kind = "uniform"
        chosen = uniform_energy
    else:
        branch_kind = "mixed"
        chosen = min(uniform_energy, nonzero_energy)
    return {
        "energy": float(chosen),
        "uniform_energy": float(uniform_energy),
        "nonzero_energy": float(nonzero_energy),
        "branch_kind": branch_kind,
        "radius_sq": float(radius_sq),
        "constant_term": float(constant_term),
        "field_norm": float(np.linalg.norm(field)),
    }


def _box_corner_points(box):
    if box.dimension == 0:
        return [[]]
    corners = []
    for selector in itertools.product([0, 1], repeat=box.dimension):
        point = []
        for index, take_upper in enumerate(selector):
            point.append(box.upper[index] if take_upper else box.lower[index])
        corners.append(point)
    return corners


def _site_log_intervals(box, active_axes, site_count):
    free_count = max(0, int(site_count) - 1)
    if free_count == 0:
        return [(0.0, 0.0)]
    offset = len(active_axes)
    intervals = []
    for index in range(free_count):
        intervals.append((float(box.lower[offset + index]), float(box.upper[offset + index])))
    lower_sum = sum(interval[0] for interval in intervals)
    upper_sum = sum(interval[1] for interval in intervals)
    intervals.append((-upper_sum, -lower_sum))
    return intervals


def _site_weight_intervals(box, active_axes, site_count):
    return [
        (math.exp(float(lower)), math.exp(float(upper)))
        for lower, upper in _site_log_intervals(box, active_axes, site_count)
    ]


def _phase_interval_for_block(block, active_axes, box):
    lower = 0.0
    upper = 0.0
    for offset, axis in enumerate(active_axes):
        coefficient = 2.0 * math.pi * float(block["R"][axis])
        low_value = coefficient * float(box.lower[offset])
        high_value = coefficient * float(box.upper[offset])
        lower += min(low_value, high_value)
        upper += max(low_value, high_value)
    return float(lower), float(upper)


def _cos_interval_bounds(lower, upper):
    lower = float(lower)
    upper = float(upper)
    if upper < lower:
        lower, upper = upper, lower
    if upper - lower >= 2.0 * math.pi - 1.0e-15:
        return -1.0, 1.0
    values = [math.cos(lower), math.cos(upper)]
    max_k = math.floor(upper / (2.0 * math.pi))
    min_k = math.ceil(lower / (2.0 * math.pi))
    if min_k <= max_k:
        values.append(1.0)
    max_k = math.floor((upper - math.pi) / (2.0 * math.pi))
    min_k = math.ceil((lower - math.pi) / (2.0 * math.pi))
    if min_k <= max_k:
        values.append(-1.0)
    return float(min(values)), float(max(values))


def _interval_product(left, right):
    candidates = [
        float(left[0]) * float(right[0]),
        float(left[0]) * float(right[1]),
        float(left[1]) * float(right[0]),
        float(left[1]) * float(right[1]),
    ]
    return float(min(candidates)), float(max(candidates))


def _scaled_interval(value, interval):
    candidates = [float(value) * float(interval[0]), float(value) * float(interval[1])]
    return float(min(candidates)), float(max(candidates))


def interval_gershgorin_lower_bound(lower_matrix, upper_matrix):
    lower = np.array(lower_matrix, dtype=float)
    upper = np.array(upper_matrix, dtype=float)
    if lower.size == 0:
        return 0.0
    best = None
    for row in range(lower.shape[0]):
        diagonal_lower = float(lower[row, row])
        offdiag_sum = 0.0
        for col in range(lower.shape[1]):
            if row == col:
                continue
            offdiag_sum += max(abs(float(lower[row, col])), abs(float(upper[row, col])))
        candidate = diagonal_lower - offdiag_sum
        best = candidate if best is None else min(best, candidate)
    return float(best if best is not None else 0.0)


def kernel_entrywise_bounds(model, box):
    blocks_payload = _lt_blocks(model)
    blocks = blocks_payload["blocks"]
    site_count = int(blocks_payload["magnetic_site_count"])
    traceless_dim = int(blocks[0]["traceless"].shape[0]) if blocks else 0
    size = site_count * traceless_dim
    lower = np.zeros((size, size), dtype=float)
    upper = np.zeros((size, size), dtype=float)
    if size == 0:
        return lower, upper

    active_axes = list(_active_axes(model))
    weight_intervals = _site_weight_intervals(box, active_axes, site_count)

    for block in blocks:
        source = int(block.get("source", 0))
        target = int(block.get("target", 0))
        phase_interval = _phase_interval_for_block(block, active_axes, box)
        cos_interval = _cos_interval_bounds(*phase_interval)
        scale_interval = _interval_product(
            _interval_product(weight_intervals[source], weight_intervals[target]),
            cos_interval,
        )
        source_slice = slice(source * traceless_dim, (source + 1) * traceless_dim)
        target_slice = slice(target * traceless_dim, (target + 1) * traceless_dim)
        matrix = np.array(block["traceless"], dtype=float)

        if source == target:
            effective = 0.5 * (matrix + matrix.T)
            for row in range(traceless_dim):
                for col in range(traceless_dim):
                    contribution = _scaled_interval(effective[row, col], scale_interval)
                    lower[source_slice.start + row, source_slice.start + col] += contribution[0]
                    upper[source_slice.start + row, source_slice.start + col] += contribution[1]
            continue

        forward = 0.5 * matrix
        backward = 0.5 * matrix.T
        for row in range(traceless_dim):
            for col in range(traceless_dim):
                contribution = _scaled_interval(forward[row, col], scale_interval)
                lower[source_slice.start + row, target_slice.start + col] += contribution[0]
                upper[source_slice.start + row, target_slice.start + col] += contribution[1]
                contribution_t = _scaled_interval(backward[row, col], scale_interval)
                lower[target_slice.start + row, source_slice.start + col] += contribution_t[0]
                upper[target_slice.start + row, source_slice.start + col] += contribution_t[1]

    return lower, upper


def _vector_interval_norm_upper(lower, upper):
    return float(
        math.sqrt(
            sum(
                max(abs(float(low)), abs(float(high))) ** 2
                for low, high in zip(lower, upper)
            )
        )
    )


def _preferred_split_axis(box, branch_kind, lower_bound_components):
    scores = _split_axis_scores(box, branch_kind, lower_bound_components)
    if not scores:
        return box.widest_dimension()
    return max(range(len(scores)), key=lambda index: (float(scores[index]), -index))


def _uniform_uncertainty(lower_bound_components):
    uniform = lower_bound_components.get("uniform", {})
    coarse = float(uniform.get("coarse", 0.0))
    chosen = float(uniform.get("chosen", coarse))
    interval_analysis = uniform.get("interval_analysis", {})
    components = interval_analysis.get("components", {}) if isinstance(interval_analysis, dict) else {}
    if components:
        spread = max(float(value) for value in components.values()) - min(float(value) for value in components.values())
    else:
        spread = 0.0
    return abs(chosen - coarse) + max(0.0, spread)


def _nonzero_uncertainty(lower_bound_components):
    nonzero = lower_bound_components.get("nonzero_q", {})
    return abs(float(nonzero.get("chosen", 0.0)) - float(nonzero.get("kernel_lower", nonzero.get("chosen", 0.0))))


def _split_axis_scores(box, branch_kind, lower_bound_components):
    diagnostics = _split_axis_diagnostics(box, branch_kind, lower_bound_components)
    return [float(item["projected_gap_reduction"]) for item in diagnostics]


def _split_axis_diagnostics(box, branch_kind, lower_bound_components):
    names = list(box.names)
    widths = box.widths()
    if not names:
        return []
    uniform_chosen = float(lower_bound_components.get("uniform", {}).get("chosen", float("inf")))
    nonzero_chosen = float(lower_bound_components.get("nonzero_q", {}).get("chosen", float("inf")))
    uniform_gap = _uniform_uncertainty(lower_bound_components)
    nonzero_gap = _nonzero_uncertainty(lower_bound_components)
    diagnostics = []
    for index, name in enumerate(names):
        width = float(widths[index])
        if name.startswith("log_p"):
            dominance = 2.0 if branch_kind == "uniform" or uniform_chosen <= nonzero_chosen + 1.0e-12 else 0.5
            uncertainty = float(uniform_gap)
            projected_gap_reduction = width * (dominance + uncertainty)
            channel = "uniform"
        elif name.startswith("q"):
            dominance = 2.0 if branch_kind == "nonzero-q" else 1.2 if branch_kind == "mixed" else 0.5
            uncertainty = float(nonzero_gap)
            projected_gap_reduction = width * (dominance + uncertainty)
            channel = "nonzero_q"
        else:
            uncertainty = 0.0
            projected_gap_reduction = width
            channel = "generic"
        diagnostics.append(
            {
                "axis": int(index),
                "name": str(name),
                "width": float(width),
                "dominance": float(dominance if name.startswith(("q", "log_p")) else 1.0),
                "uncertainty": float(uncertainty),
                "channel": channel,
                "projected_gap_reduction": float(projected_gap_reduction),
            }
        )
    return diagnostics


def _is_exact_array(lower, upper, *, tolerance=1.0e-14):
    return bool(np.allclose(np.array(lower, dtype=float), np.array(upper, dtype=float), atol=tolerance, rtol=0.0))


def _is_diagonal_interval(kernel_lower, kernel_upper, *, tolerance=1.0e-14):
    kernel_lower = np.array(kernel_lower, dtype=float)
    kernel_upper = np.array(kernel_upper, dtype=float)
    if kernel_lower.shape != kernel_upper.shape:
        return False
    for row in range(kernel_lower.shape[0]):
        for col in range(kernel_lower.shape[1]):
            if row == col:
                continue
            if abs(float(kernel_lower[row, col])) > tolerance or abs(float(kernel_upper[row, col])) > tolerance:
                return False
    return True


def uniform_branch_bounds(model, box):
    blocks_payload = _lt_blocks(model)
    blocks = blocks_payload["blocks"]
    site_count = int(blocks_payload["magnetic_site_count"])
    active_axes = list(_active_axes(model))
    weight_intervals = _site_weight_intervals(box, active_axes, site_count)
    local_dimension = int(model["local_dimension"])
    alpha_intervals = [
        (float(weight[1]) ** -2, float(weight[0]) ** -2)
        for weight in weight_intervals
    ]
    radius_sq_lower = max(
        0.0,
        (1.0 - 1.0 / float(local_dimension)) * sum(interval[0] for interval in alpha_intervals),
    )
    radius_sq_upper = max(
        0.0,
        (1.0 - 1.0 / float(local_dimension)) * sum(interval[1] for interval in alpha_intervals),
    )

    if not blocks:
        kernel_lower = np.zeros((0, 0), dtype=float)
        kernel_upper = np.zeros((0, 0), dtype=float)
        field_lower = np.zeros((0,), dtype=float)
        field_upper = np.zeros((0,), dtype=float)
        constant_lower = 0.0
        constant_upper = 0.0
        return {
            "mode": "analytic-interval",
            "kernel_lower": kernel_lower,
            "kernel_upper": kernel_upper,
            "field_lower": field_lower,
            "field_upper": field_upper,
            "constant_lower": float(constant_lower),
            "constant_upper": float(constant_upper),
            "radius_sq_lower": float(radius_sq_lower),
            "radius_sq_upper": float(radius_sq_upper),
        }

    full_dim = int(blocks[0]["full"].shape[0])
    total_dim = site_count * full_dim
    full_lower = np.zeros((total_dim, total_dim), dtype=float)
    full_upper = np.zeros((total_dim, total_dim), dtype=float)

    for block in blocks:
        source = int(block.get("source", 0))
        target = int(block.get("target", 0))
        source_start = source * full_dim
        target_start = target * full_dim
        full = np.array(block["full"], dtype=float)
        for row in range(full_dim):
            for col in range(full_dim):
                coefficient = float(full[row, col])
                if row == 0 and col == 0:
                    scale_interval = (1.0, 1.0)
                elif row == 0:
                    scale_interval = weight_intervals[target]
                elif col == 0:
                    scale_interval = weight_intervals[source]
                else:
                    scale_interval = _interval_product(weight_intervals[source], weight_intervals[target])
                contribution = _scaled_interval(coefficient, scale_interval)
                full_lower[source_start + row, target_start + col] += contribution[0]
                full_upper[source_start + row, target_start + col] += contribution[1]

    symmetric_lower = 0.5 * (full_lower + full_lower.T)
    symmetric_upper = 0.5 * (full_upper + full_upper.T)
    x0 = 1.0 / math.sqrt(float(local_dimension))
    fixed = np.zeros((total_dim,), dtype=float)
    identity_indices = []
    traceless_indices = []
    for site_index in range(site_count):
        identity_index = site_index * full_dim
        identity_indices.append(identity_index)
        fixed[identity_index] = x0
        traceless_indices.extend(range(identity_index + 1, identity_index + full_dim))

    field_lower = symmetric_lower @ fixed
    field_upper = symmetric_upper @ fixed
    field_lower = np.array([float(value) for value in field_lower[traceless_indices]], dtype=float)
    field_upper = np.array([float(value) for value in field_upper[traceless_indices]], dtype=float)
    kernel_lower = np.array(symmetric_lower[np.ix_(traceless_indices, traceless_indices)], dtype=float)
    kernel_upper = np.array(symmetric_upper[np.ix_(traceless_indices, traceless_indices)], dtype=float)
    constant_lower = float(fixed @ symmetric_lower @ fixed)
    constant_upper = float(fixed @ symmetric_upper @ fixed)

    return {
        "mode": "analytic-interval",
        "kernel_lower": kernel_lower,
        "kernel_upper": kernel_upper,
        "field_lower": np.array(field_lower, dtype=float),
        "field_upper": np.array(field_upper, dtype=float),
        "constant_lower": float(constant_lower),
        "constant_upper": float(constant_upper),
        "radius_sq_lower": float(radius_sq_lower),
        "radius_sq_upper": float(radius_sq_upper),
    }


def uniform_branch_interval_analysis(
    *,
    mode=None,
    kernel_lower,
    kernel_upper,
    field_lower,
    field_upper,
    constant_lower,
    constant_upper,
    radius_sq_lower,
    radius_sq_upper,
):
    kernel_lower = np.array(kernel_lower, dtype=float)
    kernel_upper = np.array(kernel_upper, dtype=float)
    field_lower = np.array(field_lower, dtype=float)
    field_upper = np.array(field_upper, dtype=float)
    constant_lower = float(constant_lower)
    constant_upper = float(constant_upper)
    radius_sq_lower = float(radius_sq_lower)
    radius_sq_upper = float(radius_sq_upper)

    exact_kernel = np.allclose(kernel_lower, kernel_upper, atol=1.0e-14, rtol=0.0)
    exact_field = np.allclose(field_lower, field_upper, atol=1.0e-14, rtol=0.0)
    exact_radius = abs(radius_sq_upper - radius_sq_lower) <= 1.0e-14
    components = {}
    if exact_kernel and exact_field and exact_radius:
        _, relative_energy, _ = _trust_region_on_sphere(
            kernel_lower,
            field_lower,
            radius_sq_lower,
        )
        lower_bound = float(constant_lower + relative_energy)
        components["exact_point"] = lower_bound
        return {
            "mode": "exact-point",
            "lower_bound": lower_bound,
            "components": components,
        }

    kernel_center = 0.5 * (kernel_lower + kernel_upper)
    kernel_radius = 0.5 * (kernel_upper - kernel_lower)
    center_radius_lower = spectral_lower_from_center_radius(kernel_center, kernel_radius)
    entrywise_lower = interval_gershgorin_lower_bound(kernel_lower, kernel_upper)
    kernel_spectral_lower = max(center_radius_lower, entrywise_lower)
    field_norm_upper = _vector_interval_norm_upper(field_lower, field_upper)
    radius_interval = radius_interval_from_values([radius_sq_lower, radius_sq_upper])
    components["center_radius"] = float(
        quadratic_lower_over_radius_interval(
            center_radius_lower,
            field_norm_upper,
            constant_lower,
            radius_interval,
        )
    )
    components["entrywise_gershgorin"] = float(
        quadratic_lower_over_radius_interval(
            entrywise_lower,
            field_norm_upper,
            constant_lower,
            radius_interval,
        )
    )
    components["spectral_max"] = float(
        quadratic_lower_over_radius_interval(
            kernel_spectral_lower,
            field_norm_upper,
            constant_lower,
            radius_interval,
        )
    )
    if _is_diagonal_interval(kernel_lower, kernel_upper) and exact_field and exact_radius:
        diagonal_matrix = np.diag(np.diag(kernel_lower))
        _, relative_energy, _ = _trust_region_on_sphere(
            diagonal_matrix,
            field_lower,
            radius_sq_lower,
        )
        components["diagonal_exact_radius"] = float(constant_lower + relative_energy)

    mode_name = "analytic-interval"
    lower_bound = max(components.values()) if components else float(constant_lower)
    if "diagonal_exact_radius" in components and components["diagonal_exact_radius"] >= lower_bound - 1.0e-12:
        mode_name = "diagonal-interval"
    return {
        "mode": mode_name,
        "lower_bound": float(lower_bound),
        "components": components,
    }


def uniform_branch_interval_lower_bound(
    *,
    mode=None,
    kernel_lower,
    kernel_upper,
    field_lower,
    field_upper,
    constant_lower,
    constant_upper,
    radius_sq_lower,
    radius_sq_upper,
):
    return float(
        uniform_branch_interval_analysis(
            mode=mode,
            kernel_lower=kernel_lower,
            kernel_upper=kernel_upper,
            field_lower=field_lower,
            field_upper=field_upper,
            constant_lower=constant_lower,
            constant_upper=constant_upper,
            radius_sq_lower=radius_sq_lower,
            radius_sq_upper=radius_sq_upper,
        )["lower_bound"]
    )


def _kernel_radius_bound(blocks_payload, active_axes, box, p_center, q_center):
    blocks = blocks_payload["blocks"]
    site_count = int(blocks_payload["magnetic_site_count"])
    local_dimension = int(blocks[0]["traceless"].shape[0]) if blocks else max(0, int(site_count) - 1)
    size = site_count * local_dimension
    if size == 0:
        return np.zeros((0, 0), dtype=float)
    radius = np.zeros((size, size), dtype=float)
    log_widths = box.widths()[len(active_axes) :]
    q_widths = box.widths()[: len(active_axes)]
    free_count = max(0, site_count - 1)
    free_center = [0.0] * free_count
    if free_count:
        free_center = box.midpoint()[-free_count:]
    p_low, _, _ = _weights_from_log_coordinates(
        [box.lower[len(active_axes) + index] for index in range(free_count)]
    )
    p_high, _, _ = _weights_from_log_coordinates(
        [box.upper[len(active_axes) + index] for index in range(free_count)]
    )
    p_max = [max(abs(float(low)), abs(float(high)), abs(float(center))) for low, high, center in zip(p_low, p_high, p_center)]
    q_width_by_axis = {axis: q_widths[offset] for offset, axis in enumerate(active_axes)}
    for block in blocks:
        source = int(block.get("source", 0))
        target = int(block.get("target", 0))
        source_slice = slice(source * local_dimension, (source + 1) * local_dimension)
        target_slice = slice(target * local_dimension, (target + 1) * local_dimension)
        matrix = np.array(block["traceless"], dtype=float)
        phase_width = 2.0 * math.pi * sum(
            abs(float(block["R"][axis])) * q_width_by_axis.get(axis, 0.0) for axis in range(3)
        )
        phase_radius = min(2.0, 0.5 * phase_width)
        block_radius = abs(float(p_max[source]) * float(p_max[target])) * abs(matrix) * phase_radius
        radius[source_slice, target_slice] += block_radius
        radius[target_slice, source_slice] += block_radius.T
    return radius


def evaluate_relaxed_box(model, box, *, heuristic_seed=None):
    blocks_payload = _lt_blocks(model)
    active_axes = list(_active_axes(model))
    midpoint = box.midpoint()
    q_center = _active_axis_values(active_axes, midpoint)
    p_center = _point_to_weights(model, midpoint)
    center_eval = _energy_for_point(model, blocks_payload, q_center, p_center)

    sample_points = _box_corner_points(box)
    sample_points.append(midpoint)
    best_upper = None
    best_point = None
    branch_kinds = set()
    radius_sq_samples = []
    constant_samples = []
    field_norm_samples = []
    for point in sample_points:
        q_vector = _active_axis_values(active_axes, point)
        p_weights = _point_to_weights(model, point)
        evaluated = _energy_for_point(model, blocks_payload, q_vector, p_weights)
        branch_kinds.add(evaluated["branch_kind"])
        radius_sq_samples.append(evaluated["radius_sq"])
        constant_samples.append(evaluated["constant_term"])
        field_norm_samples.append(evaluated["field_norm"])
        if best_upper is None or evaluated["energy"] < best_upper:
            best_upper = float(evaluated["energy"])
            best_point = {
                "q_vector": list(q_vector),
                "p_weights": list(p_weights),
            }

    kernel_center = _kernel_at_q(
        blocks_payload["blocks"],
        q_center,
        p_weights=p_center,
        magnetic_site_count=int(blocks_payload["magnetic_site_count"]),
    )
    radius_matrix = _kernel_radius_bound(blocks_payload, active_axes, box, p_center, q_center)
    center_radius_lower = spectral_lower_from_center_radius(kernel_center, radius_matrix)
    entrywise_lower, entrywise_upper = kernel_entrywise_bounds(model, box)
    kernel_lower = max(center_radius_lower, interval_gershgorin_lower_bound(entrywise_lower, entrywise_upper))
    radius_interval = radius_interval_from_values(radius_sq_samples)
    constant_lower = min(constant_samples) if constant_samples else 0.0
    field_upper = max(field_norm_samples) if field_norm_samples else 0.0
    coarse_uniform_lower = quadratic_lower_over_radius_interval(
        kernel_lower,
        field_upper,
        constant_lower,
        radius_interval,
    )
    uniform_bounds = uniform_branch_bounds(model, box)
    uniform_analysis = uniform_branch_interval_analysis(**uniform_bounds)
    uniform_lower = max(
        float(coarse_uniform_lower),
        float(uniform_analysis["lower_bound"]),
    )
    nonzero_lower = constant_lower
    if kernel_center.size:
        squared_radius_interval = (radius_interval[0] ** 2, radius_interval[1] ** 2)
        if kernel_lower >= 0.0:
            nonzero_lower += squared_radius_interval[0] * kernel_lower
        else:
            nonzero_lower += squared_radius_interval[1] * kernel_lower
    lower_bound = min(float(uniform_lower), float(nonzero_lower), float(best_upper))
    if heuristic_seed is not None:
        best_upper = min(float(best_upper), float(heuristic_seed.get("energy_upper_bound", best_upper)))
    if branch_kinds == {"uniform"}:
        branch_kind = "uniform"
    elif branch_kinds == {"nonzero-q"}:
        branch_kind = "nonzero-q"
    else:
        branch_kind = "mixed"
    lower_bound_components = {
        "uniform": {
            "coarse": float(coarse_uniform_lower),
            "interval_analysis": dict(uniform_analysis),
            "chosen": float(uniform_lower),
        },
        "nonzero_q": {
            "kernel_lower": float(kernel_lower),
            "chosen": float(nonzero_lower),
        },
    }
    split_axis_diagnostics = _split_axis_diagnostics(box, branch_kind, lower_bound_components)
    split_axis_scores = [float(item["projected_gap_reduction"]) for item in split_axis_diagnostics]
    return {
        "lower_bound": float(lower_bound),
        "upper_bound": float(best_upper),
        "candidate_point": dict(best_point) if best_point is not None else {"q_vector": list(q_center), "p_weights": list(p_center)},
        "branch_kind": branch_kind,
        "lower_bound_components": lower_bound_components,
        "split_axis_scores": list(split_axis_scores),
        "split_axis_diagnostics": list(split_axis_diagnostics),
        "split_axis_hint": int(_preferred_split_axis(box, branch_kind, lower_bound_components)),
        "box": box.to_dict(),
    }


def refine_candidate_upper_bound(model, seed):
    blocks_payload = _lt_blocks(model)
    active_axes = list(_active_axes(model))
    initial_q = [float(seed.get("q_vector", [0.0, 0.0, 0.0])[axis]) for axis in active_axes]
    initial_weights = list(seed.get("p_weights", [1.0]))
    free_count = max(0, len(initial_weights) - 1)
    initial_logs = []
    if free_count:
        initial_logs = [math.log(max(1.0e-12, float(value))) for value in initial_weights[:free_count]]
    initial = np.array(initial_q + initial_logs, dtype=float)
    bounds = [(0.0, 1.0)] * len(initial_q) + [(-1.0, 1.0)] * len(initial_logs)

    def objective(vector):
        q_vector = [0.0, 0.0, 0.0]
        for offset, axis in enumerate(active_axes):
            q_vector[axis] = float(vector[offset] % 1.0)
        p_weights = _point_to_weights(model, vector)
        return float(_energy_for_point(model, blocks_payload, q_vector, p_weights)["energy"])

    best_energy = float(seed.get("energy_upper_bound", 0.0))
    best_vector = np.array(initial, copy=True)
    if initial.size:
        result = minimize(objective, initial, method="L-BFGS-B", bounds=bounds)
        if result.success and float(result.fun) <= best_energy + 1.0e-12:
            best_energy = float(result.fun)
            best_vector = np.array(result.x, dtype=float)
            status = "refined"
        else:
            status = "seed-retained"
    else:
        candidate_energy = objective(initial)
        if candidate_energy <= best_energy + 1.0e-12:
            best_energy = float(candidate_energy)
        status = "seed-retained"

    q_vector = [0.0, 0.0, 0.0]
    for offset, axis in enumerate(active_axes):
        q_vector[axis] = float(best_vector[offset] % 1.0)
    p_weights = _point_to_weights(model, best_vector)
    return {
        "status": status,
        "energy_upper_bound": float(best_energy),
        "q_vector": list(q_vector),
        "p_weights": [float(value) for value in p_weights],
    }
