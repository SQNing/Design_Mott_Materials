#!/usr/bin/env python3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lswt.build_python_glswt_payload import build_python_glswt_payload
from lswt.python_glswt_solver import solve_python_glswt


def _normalize_scan_values(values, *, name, minimum):
    if values is None:
        raise ValueError(f"{name} is required")
    normalized = sorted({int(value) for value in values})
    if not normalized:
        raise ValueError(f"{name} must be non-empty")
    if normalized[0] < int(minimum):
        raise ValueError(f"{name} values must be >= {minimum}")
    return normalized


def _solve_scan_case(
    model,
    *,
    classical_state,
    phase_grid_size,
    z_harmonic_cutoff,
    sideband_cutoff,
    z_harmonic_reference_mode,
    cache,
):
    key = (
        int(phase_grid_size),
        int(z_harmonic_cutoff),
        int(sideband_cutoff),
        str(z_harmonic_reference_mode),
    )
    if key in cache:
        return cache[key]

    scan_model = dict(model)
    scan_model["phase_grid_size"] = int(phase_grid_size)
    scan_model["z_harmonic_cutoff"] = int(z_harmonic_cutoff)
    scan_model["sideband_cutoff"] = int(sideband_cutoff)
    scan_model["z_harmonic_reference_mode"] = str(z_harmonic_reference_mode)
    payload = build_python_glswt_payload(scan_model, classical_state=classical_state)
    if payload.get("payload_kind") != "python_glswt_single_q_z_harmonic":
        raise ValueError("single-q convergence analysis requires a python_glswt_single_q_z_harmonic payload")

    result = solve_python_glswt(payload)
    cache[key] = result
    return result


def _omega_min(dispersion_diagnostics):
    omega_min = dispersion_diagnostics.get("omega_min")
    if omega_min is None:
        return None
    return float(omega_min)


def _max_band_delta(candidate_dispersion, reference_dispersion, *, tolerance=1e-10):
    if len(candidate_dispersion) != len(reference_dispersion):
        raise ValueError("dispersion lengths differ between candidate and reference scans")

    max_delta = 0.0
    compared_any = False
    for candidate_point, reference_point in zip(candidate_dispersion, reference_dispersion):
        candidate_q = [float(value) for value in candidate_point.get("q", [])]
        reference_q = [float(value) for value in reference_point.get("q", [])]
        if len(candidate_q) != len(reference_q):
            raise ValueError("q-vector lengths differ between candidate and reference scans")
        if any(abs(left - right) > tolerance for left, right in zip(candidate_q, reference_q)):
            raise ValueError("q-point grids differ between candidate and reference scans")

        candidate_bands = [float(value) for value in candidate_point.get("bands", [])]
        reference_bands = [float(value) for value in reference_point.get("bands", [])]
        common_band_count = min(len(candidate_bands), len(reference_bands))
        if common_band_count <= 0:
            continue
        compared_any = True
        for candidate_band, reference_band in zip(
            candidate_bands[:common_band_count],
            reference_bands[:common_band_count],
        ):
            max_delta = max(max_delta, abs(candidate_band - reference_band))

    if not compared_any:
        return None
    return float(max_delta)


def _resolved_reference_mode(result):
    diagnostics = result.get("diagnostics", {}) if isinstance(result.get("diagnostics"), dict) else {}
    reference_selection = (
        diagnostics.get("reference_selection", {})
        if isinstance(diagnostics.get("reference_selection"), dict)
        else {}
    )
    return str(reference_selection.get("resolved_mode", result.get("z_harmonic_reference_mode", "input")))


def _scan_entry(parameters, result, reference_result):
    diagnostics = result.get("diagnostics", {}) if isinstance(result.get("diagnostics"), dict) else {}
    reference_diagnostics = (
        reference_result.get("diagnostics", {})
        if isinstance(reference_result.get("diagnostics"), dict)
        else {}
    )
    dispersion_diagnostics = (
        diagnostics.get("dispersion", {}) if isinstance(diagnostics.get("dispersion"), dict) else {}
    )
    reference_dispersion_diagnostics = (
        reference_diagnostics.get("dispersion", {})
        if isinstance(reference_diagnostics.get("dispersion"), dict)
        else {}
    )
    truncated = (
        diagnostics.get("truncated_z_harmonic_stationarity", {})
        if isinstance(diagnostics.get("truncated_z_harmonic_stationarity"), dict)
        else {}
    )
    stationarity = (
        diagnostics.get("stationarity", {}) if isinstance(diagnostics.get("stationarity"), dict) else {}
    )
    reference_selection = (
        diagnostics.get("reference_selection", {})
        if isinstance(diagnostics.get("reference_selection"), dict)
        else {}
    )

    omega_min = _omega_min(dispersion_diagnostics)
    reference_omega_min = _omega_min(reference_dispersion_diagnostics)
    omega_min_delta = None
    if omega_min is not None and reference_omega_min is not None:
        omega_min_delta = float(omega_min - reference_omega_min)

    return {
        "phase_grid_size": int(parameters["phase_grid_size"]),
        "z_harmonic_cutoff": int(parameters["z_harmonic_cutoff"]),
        "sideband_cutoff": int(parameters["sideband_cutoff"]),
        "resolved_reference_mode": _resolved_reference_mode(result),
        "reference_dispersion_recomputed": bool(reference_selection.get("dispersion_recomputed", False)),
        "omega_min": omega_min,
        "omega_min_delta_vs_reference": omega_min_delta,
        "max_band_delta_vs_reference": _max_band_delta(
            result.get("dispersion", []),
            reference_result.get("dispersion", []),
        ),
        "retained_linear_term_max_norm": truncated.get("linear_term_max_norm"),
        "discarded_linear_term_max_norm": truncated.get("discarded_linear_term_max_norm"),
        "full_tangent_linear_term_max_norm": stationarity.get("linear_term_max_norm"),
    }


def _reference_metrics(reference_result):
    diagnostics = (
        reference_result.get("diagnostics", {})
        if isinstance(reference_result.get("diagnostics"), dict)
        else {}
    )
    dispersion_diagnostics = (
        diagnostics.get("dispersion", {}) if isinstance(diagnostics.get("dispersion"), dict) else {}
    )
    truncated = (
        diagnostics.get("truncated_z_harmonic_stationarity", {})
        if isinstance(diagnostics.get("truncated_z_harmonic_stationarity"), dict)
        else {}
    )
    stationarity = (
        diagnostics.get("stationarity", {}) if isinstance(diagnostics.get("stationarity"), dict) else {}
    )
    return {
        "omega_min": _omega_min(dispersion_diagnostics),
        "omega_min_q_vector": dispersion_diagnostics.get("omega_min_q_vector"),
        "retained_linear_term_max_norm": truncated.get("linear_term_max_norm"),
        "discarded_linear_term_max_norm": truncated.get("discarded_linear_term_max_norm"),
        "full_tangent_linear_term_max_norm": stationarity.get("linear_term_max_norm"),
    }


def analyze_single_q_z_harmonic_convergence(
    model,
    *,
    classical_state=None,
    phase_grid_sizes,
    z_harmonic_cutoffs,
    sideband_cutoffs,
    z_harmonic_reference_mode="input",
):
    phase_grid_sizes = _normalize_scan_values(phase_grid_sizes, name="phase_grid_sizes", minimum=1)
    z_harmonic_cutoffs = _normalize_scan_values(z_harmonic_cutoffs, name="z_harmonic_cutoffs", minimum=0)
    sideband_cutoffs = _normalize_scan_values(sideband_cutoffs, name="sideband_cutoffs", minimum=0)
    reference_parameters = {
        "phase_grid_size": int(phase_grid_sizes[-1]),
        "z_harmonic_cutoff": int(z_harmonic_cutoffs[-1]),
        "sideband_cutoff": int(sideband_cutoffs[-1]),
        "z_harmonic_reference_mode": str(z_harmonic_reference_mode),
    }

    cache = {}
    reference_result = _solve_scan_case(
        model,
        classical_state=classical_state,
        phase_grid_size=reference_parameters["phase_grid_size"],
        z_harmonic_cutoff=reference_parameters["z_harmonic_cutoff"],
        sideband_cutoff=reference_parameters["sideband_cutoff"],
        z_harmonic_reference_mode=reference_parameters["z_harmonic_reference_mode"],
        cache=cache,
    )

    phase_grid_scan = []
    for phase_grid_size in phase_grid_sizes:
        parameters = {
            "phase_grid_size": int(phase_grid_size),
            "z_harmonic_cutoff": int(reference_parameters["z_harmonic_cutoff"]),
            "sideband_cutoff": int(reference_parameters["sideband_cutoff"]),
        }
        result = _solve_scan_case(
            model,
            classical_state=classical_state,
            z_harmonic_reference_mode=reference_parameters["z_harmonic_reference_mode"],
            cache=cache,
            **parameters,
        )
        phase_grid_scan.append(_scan_entry(parameters, result, reference_result))

    z_harmonic_cutoff_scan = []
    for z_harmonic_cutoff in z_harmonic_cutoffs:
        parameters = {
            "phase_grid_size": int(reference_parameters["phase_grid_size"]),
            "z_harmonic_cutoff": int(z_harmonic_cutoff),
            "sideband_cutoff": int(reference_parameters["sideband_cutoff"]),
        }
        result = _solve_scan_case(
            model,
            classical_state=classical_state,
            z_harmonic_reference_mode=reference_parameters["z_harmonic_reference_mode"],
            cache=cache,
            **parameters,
        )
        z_harmonic_cutoff_scan.append(_scan_entry(parameters, result, reference_result))

    sideband_cutoff_scan = []
    for sideband_cutoff in sideband_cutoffs:
        parameters = {
            "phase_grid_size": int(reference_parameters["phase_grid_size"]),
            "z_harmonic_cutoff": int(reference_parameters["z_harmonic_cutoff"]),
            "sideband_cutoff": int(sideband_cutoff),
        }
        result = _solve_scan_case(
            model,
            classical_state=classical_state,
            z_harmonic_reference_mode=reference_parameters["z_harmonic_reference_mode"],
            cache=cache,
            **parameters,
        )
        sideband_cutoff_scan.append(_scan_entry(parameters, result, reference_result))

    return {
        "status": "ok",
        "analysis_kind": "single_q_z_harmonic_convergence",
        "reference_parameters": reference_parameters,
        "reference_metrics": _reference_metrics(reference_result),
        "phase_grid_scan": phase_grid_scan,
        "z_harmonic_cutoff_scan": z_harmonic_cutoff_scan,
        "sideband_cutoff_scan": sideband_cutoff_scan,
        "ordering": dict(reference_result.get("ordering", {})),
        "path": dict(reference_result.get("path", {})),
    }
