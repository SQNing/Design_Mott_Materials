#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.lswt_failure_analysis import summarize_lswt_failure
from common.symmetry_explanations import summarize_symmetry_interpretation
from common.classical_contract_resolution import get_classical_state_result


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


def _gswt_reference_dispersion_comparison_line(gswt):
    if not isinstance(gswt, dict):
        return None
    reference_dispersions = (
        gswt.get("reference_dispersions", {})
        if isinstance(gswt.get("reference_dispersions"), dict)
        else {}
    )
    diagnostics = gswt.get("diagnostics", {}) if isinstance(gswt.get("diagnostics"), dict) else {}
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
        "GSWT reference dispersion comparison: "
        f"selected_mode={resolved_mode} "
        f"input_omega_min={_format_summary_float(input_omega_min)} "
        f"input_omega_min_q={input_omega_min_q} "
        f"selected_omega_min={_format_summary_float(selected_omega_min)} "
        f"selected_omega_min_q={selected_omega_min_q} "
        f"delta_omega_min={_format_summary_float(delta_omega_min)}"
    )


def _single_q_convergence_lines(payload):
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

    def _scan_lines(entries, primary_key):
        lines = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            lines.append(
                "- "
                f"{primary_key}={entry.get(primary_key, 'n/a')} "
                f"omega_min={_format_summary_float(entry.get('omega_min'))} "
                f"omega_min_delta_vs_reference={_format_summary_float(entry.get('omega_min_delta_vs_reference'))} "
                f"max_band_delta_vs_reference={_format_summary_float(entry.get('max_band_delta_vs_reference'))} "
                f"retained_linear_term_max_norm={_format_summary_float(entry.get('retained_linear_term_max_norm'))} "
                f"full_tangent_linear_term_max_norm={_format_summary_float(entry.get('full_tangent_linear_term_max_norm'))}"
            )
        return lines or ["- n/a"]

    return [
        "",
        "Single-Q Z-Harmonic Convergence:",
        "- "
        f"reference_phase_grid_size={reference.get('phase_grid_size', 'n/a')} "
        f"reference_z_harmonic_cutoff={reference.get('z_harmonic_cutoff', 'n/a')} "
        f"reference_sideband_cutoff={reference.get('sideband_cutoff', 'n/a')} "
        f"reference_mode={reference.get('z_harmonic_reference_mode', 'n/a')} "
        f"reference_omega_min={_format_summary_float(metrics.get('omega_min'))} "
        f"reference_omega_min_q={metrics.get('omega_min_q_vector', 'n/a')}",
        "- phase_grid_scan:",
        *_scan_lines(convergence.get("phase_grid_scan", []), "phase_grid_size"),
        "- z_harmonic_cutoff_scan:",
        *_scan_lines(convergence.get("z_harmonic_cutoff_scan", []), "z_harmonic_cutoff"),
        "- sideband_cutoff_scan:",
        *_scan_lines(convergence.get("sideband_cutoff_scan", []), "sideband_cutoff"),
    ]


def _gswt_interpretation_line(gswt):
    diagnostics = gswt.get("diagnostics", {}) if isinstance(gswt, dict) else {}
    instability = diagnostics.get("instability", {}) if isinstance(diagnostics, dict) else {}
    if not instability:
        return None

    kind = instability.get("kind")
    nearest_kind = instability.get("nearest_q_path_kind")
    if kind != "wavevector-instability":
        return "GSWT interpretation: backend reported an instability in the supplied harmonic expansion."

    if nearest_kind == "high-symmetry-node":
        label = instability.get("nearest_high_symmetry_label", "the nearest high-symmetry node")
        return (
            "GSWT interpretation: the supplied classical reference shows a harmonic instability "
            f"near high-symmetry point {label}."
        )
    if nearest_kind == "path-segment-sample":
        label = instability.get("nearest_path_segment_label", "the sampled path segment")
        return (
            "GSWT interpretation: the supplied classical reference shows a harmonic instability "
            f"near path segment {label}."
        )
    q_vector = instability.get("q_vector", "the reported q vector")
    return (
        "GSWT interpretation: the supplied classical reference shows a harmonic instability "
        f"near q={q_vector}."
    )


def render_text(payload):
    lines = []
    lswt = payload.get("lswt", {})
    nested_linear_spin_wave = lswt.get("linear_spin_wave", {})
    linear_spin_wave = payload.get("linear_spin_wave", {}) or nested_linear_spin_wave

    lines.append("Spin Model Simplifier Report")
    lines.append("============================")
    lines.append("")
    lines.append(f"Local Hilbert dimension: {payload['normalized_model']['local_hilbert']['dimension']}")
    lines.append(
        f"Recommended simplification: {payload['simplification']['candidates'][payload['simplification']['recommended']]['name']}"
    )
    lines.append("")
    lines.append("Canonical model summary:")
    canonical_model = payload.get("canonical_model", {})
    for key in ("one_body", "two_body", "three_body", "four_body", "higher_body"):
        count = len(canonical_model.get(key, []))
        if count:
            lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("Readable main model:")
    for block in payload.get("effective_model", {}).get("main", []):
        lines.append(f"- {block.get('type', 'block')} coeff={block.get('coefficient', 'n/a')}")
    lines.append("")
    lines.append("Low-weight terms:")
    for term in payload.get("effective_model", {}).get("low_weight", []):
        line = f"- {term.get('canonical_label', term.get('type', 'term'))} coeff={term.get('coefficient', 'n/a')}"
        if term.get("warning"):
            line += f" warning={term['warning']}"
        lines.append(line)
    lines.append("")
    lines.append("Residual terms:")
    for term in payload.get("effective_model", {}).get("residual", []):
        lines.append(f"- {term.get('canonical_label', term.get('type', 'term'))} coeff={term.get('coefficient', 'n/a')}")
    lines.append("")
    lines.append("Fidelity report:")
    fidelity = payload.get("fidelity", {})
    lines.append(f"- reconstruction error: {fidelity.get('reconstruction_error', 'n/a')}")
    lines.append(f"- main fraction: {fidelity.get('main_fraction', 'n/a')}")
    lines.append(f"- low-weight fraction: {fidelity.get('low_weight_fraction', 'n/a')}")
    lines.append(f"- residual fraction: {fidelity.get('residual_fraction', 'n/a')}")
    for note in fidelity.get("risk_notes", []):
        lines.append(f"- risk: {note}")
    symmetry_lines = summarize_symmetry_interpretation(payload)
    if symmetry_lines:
        lines.append("")
        lines.append("Symmetry interpretation:")
        for line in symmetry_lines:
            lines.append(f"- {line}")
    plots = payload.get("plots")
    if plots:
        lines.append("")
        lines.append(f"Plot status: {plots.get('status', 'unknown')}")
        for plot_name, metadata in plots.get("plots", {}).items():
            if metadata.get("path"):
                lines.append(f"- {plot_name}: {metadata['path']}")
            elif metadata.get("reason"):
                lines.append(f"- {plot_name}: {metadata.get('status', 'skipped')} ({metadata['reason']})")
    thermodynamics_config = payload.get("thermodynamics", {})
    thermodynamics = payload.get("thermodynamics_result", {})
    if not thermodynamics_config and isinstance(thermodynamics, dict):
        configuration = thermodynamics.get("configuration", {})
        if isinstance(configuration, dict):
            thermodynamics_config = configuration
    if thermodynamics_config:
        lines.append("")
        lines.append("Thermodynamics configuration:")
        lines.append(
            "- "
            f"profile={thermodynamics_config.get('profile', 'n/a')} "
            f"backend_method={thermodynamics_config.get('backend_method', 'n/a')} "
            f"temperatures={thermodynamics_config.get('temperatures', 'n/a')} "
            f"sweeps={thermodynamics_config.get('sweeps', 'n/a')} "
            f"burn_in={thermodynamics_config.get('burn_in', 'n/a')} "
            f"measurement_interval={thermodynamics_config.get('measurement_interval', 'n/a')} "
            f"proposal={thermodynamics_config.get('proposal', 'n/a')} "
            f"proposal_scale={thermodynamics_config.get('proposal_scale', 'n/a')}"
        )
    thermo_grid = thermodynamics.get("grid", [])
    if thermo_grid:
        lines.append("")
        lines.append("Classical thermodynamics:")
        reference = thermodynamics.get("reference", {})
        sampling = thermodynamics.get("sampling", {})
        uncertainties = thermodynamics.get("uncertainties", {})
        autocorrelation = thermodynamics.get("autocorrelation", {})
        if reference:
            lines.append(
                "- normalization: "
                f"{reference.get('normalization', 'n/a')} "
                f"high_T_entropy={reference.get('high_temperature_entropy', 'n/a')} "
                f"energy_infinite_temperature={reference.get('energy_infinite_temperature', 'n/a')}"
            )
        if sampling:
            lines.append(
                "- sampling: "
                f"scan_order={sampling.get('scan_order', 'n/a')} "
                f"reuse_configuration={sampling.get('reuse_configuration', 'n/a')} "
                f"sweeps={sampling.get('sweeps', 'n/a')} "
                f"burn_in={sampling.get('burn_in', 'n/a')} "
                f"measurement_interval={sampling.get('measurement_interval', 'n/a')}"
            )
        for point in thermo_grid:
            temperature = point.get("temperature", "n/a")
            index = next(
                (
                    idx
                    for idx, item in enumerate(thermo_grid)
                    if item.get("temperature", None) == temperature
                ),
                None,
            )
            energy_stderr = uncertainties.get("energy", [])[index] if index is not None and index < len(uncertainties.get("energy", [])) else "n/a"
            free_energy_stderr = uncertainties.get("free_energy", [])[index] if index is not None and index < len(uncertainties.get("free_energy", [])) else "n/a"
            specific_heat_stderr = uncertainties.get("specific_heat", [])[index] if index is not None and index < len(uncertainties.get("specific_heat", [])) else "n/a"
            magnetization_stderr = uncertainties.get("magnetization", [])[index] if index is not None and index < len(uncertainties.get("magnetization", [])) else "n/a"
            susceptibility_stderr = uncertainties.get("susceptibility", [])[index] if index is not None and index < len(uncertainties.get("susceptibility", [])) else "n/a"
            entropy_stderr = uncertainties.get("entropy", [])[index] if index is not None and index < len(uncertainties.get("entropy", [])) else "n/a"
            tau_energy = autocorrelation.get("energy", [])[index] if index is not None and index < len(autocorrelation.get("energy", [])) else "n/a"
            tau_magnetization = autocorrelation.get("magnetization", [])[index] if index is not None and index < len(autocorrelation.get("magnetization", [])) else "n/a"
            lines.append(
                "- "
                f"T={temperature} "
                f"energy={point.get('energy', 'n/a')} "
                f"free_energy={point.get('free_energy', 'n/a')} "
                f"specific_heat={point.get('specific_heat', 'n/a')} "
                f"magnetization={point.get('magnetization', 'n/a')} "
                f"susceptibility={point.get('susceptibility', 'n/a')} "
                f"entropy={point.get('entropy', 'n/a')} "
                f"energy_stderr={energy_stderr} "
                f"free_energy_stderr={free_energy_stderr} "
                f"specific_heat_stderr={specific_heat_stderr} "
                f"magnetization_stderr={magnetization_stderr} "
                f"susceptibility_stderr={susceptibility_stderr} "
                f"entropy_stderr={entropy_stderr} "
                f"tau_E={tau_energy} "
                f"tau_M={tau_magnetization}"
            )
    lt_result = payload.get("lt_result", {})
    if lt_result:
        constraint_recovery = lt_result.get("constraint_recovery", {})
        lines.append("")
        lines.append("Luttinger-Tisza diagnostics:")
        lines.append(
            "- "
            f"best_q={lt_result.get('q', 'n/a')} "
            f"lowest_eigenvalue={lt_result.get('lowest_eigenvalue', 'n/a')} "
            f"matrix_size={lt_result.get('matrix_size', 'n/a')} "
            f"strong_constraint_residual={constraint_recovery.get('strong_constraint_residual', 'n/a')}"
        )
    generalized_lt_result = payload.get("generalized_lt_result", {})
    if generalized_lt_result:
        constraint_recovery = generalized_lt_result.get("constraint_recovery", {})
        lines.append("")
        lines.append("Generalized LT diagnostics:")
        lines.append(
            "- "
            f"lambda={generalized_lt_result.get('lambda', 'n/a')} "
            f"tightened_lower_bound={generalized_lt_result.get('tightened_lower_bound', 'n/a')} "
            f"best_q={generalized_lt_result.get('q', 'n/a')} "
            f"strong_constraint_residual={constraint_recovery.get('strong_constraint_residual', 'n/a')}"
        )
    classical_state_result = get_classical_state_result(payload) or {}
    classical = payload.get("classical", {})
    chosen_method = classical_state_result.get("method", classical.get("chosen_method", "n/a"))
    lines.append(f"Projection status: {payload['projection']['status']}")
    lines.append(f"Chosen classical method: {chosen_method}")
    if classical_state_result.get("role") is not None:
        lines.append(f"Classical solver role: {classical_state_result.get('role')}")
    if classical_state_result.get("solver_family") is not None:
        lines.append(f"Classical solver family: {classical_state_result.get('solver_family')}")
    downstream_compatibility = classical_state_result.get("downstream_compatibility", {})
    if isinstance(downstream_compatibility, dict) and downstream_compatibility:
        lines.append("Classical downstream compatibility:")
        lines.append(
            "- "
            f"lswt={downstream_compatibility.get('lswt', {}).get('status', 'n/a')} "
            f"gswt={downstream_compatibility.get('gswt', {}).get('status', 'n/a')} "
            f"thermodynamics={downstream_compatibility.get('thermodynamics', {}).get('status', 'n/a')}"
        )
    auto_resolution = payload.get("classical", {}).get("auto_resolution", {})
    if auto_resolution.get("enabled"):
        lines.append("Classical auto-resolution:")
        lines.append(
            "- "
            f"requested={payload.get('classical', {}).get('requested_method', 'n/a')} "
            f"recommended={auto_resolution.get('recommended_method', 'n/a')} "
            f"initial={auto_resolution.get('initial_method', 'n/a')} "
            f"resolved={auto_resolution.get('resolved_method', 'n/a')} "
            f"reason={auto_resolution.get('reason', 'n/a')} "
            f"lt_residual={auto_resolution.get('lt_residual', 'n/a')} "
            f"generalized_lt_residual={auto_resolution.get('generalized_lt_residual', 'n/a')}"
        )
    backend_name = lswt.get("backend", {}).get("name")
    gswt = payload.get("gswt", {})
    gswt_backend_name = gswt.get("backend", {}).get("name")
    if gswt_backend_name:
        lines.append(f"GSWT backend: {gswt_backend_name}")
    gswt_status = gswt.get("status")
    if gswt_status:
        lines.append(f"GSWT status: {gswt_status}")
    gswt_classical_reference = gswt.get("classical_reference", {})
    if gswt_classical_reference:
        lines.append(
            "GSWT reference state: "
            f"{gswt_classical_reference.get('state_kind', 'n/a')} "
            f"manifold={gswt_classical_reference.get('manifold', 'n/a')} "
            f"frame={gswt_classical_reference.get('frame_construction', 'n/a')} "
            f"schema_version={gswt_classical_reference.get('schema_version', 'n/a')}"
        )
    gswt_ordering = gswt.get("ordering", {})
    if gswt_ordering:
        compatibility = gswt_ordering.get("compatibility_with_supercell", {})
        lines.append(
            "GSWT ordering: "
            f"ansatz={gswt_ordering.get('ansatz', 'n/a')} "
            f"q_vector={gswt_ordering.get('q_vector', 'n/a')} "
            f"supercell_shape={gswt_ordering.get('supercell_shape', 'n/a')} "
            f"compatibility={compatibility.get('kind', 'n/a')}"
        )
    gswt_diagnostics = gswt.get("diagnostics", {})
    gswt_instability = gswt_diagnostics.get("instability", {})
    if gswt_instability:
        lines.append(
            "GSWT instability diagnostics: "
            f"kind={gswt_instability.get('kind', 'n/a')} "
            f"q_vector={gswt_instability.get('q_vector', 'n/a')} "
            f"nearest_path_index={gswt_instability.get('nearest_q_path_index', 'n/a')} "
            f"nearest_q_path_kind={gswt_instability.get('nearest_q_path_kind', 'n/a')} "
            f"nearest_q_path_distance={gswt_instability.get('nearest_q_path_distance', 'n/a')} "
            f"nearest_path_segment_label={gswt_instability.get('nearest_path_segment_label', 'n/a')} "
            f"nearest_high_symmetry_label={gswt_instability.get('nearest_high_symmetry_label', 'n/a')}"
        )
    interpretation = _gswt_interpretation_line(gswt)
    if interpretation is not None:
        lines.append(interpretation)
    gswt_dispersion_diag = gswt_diagnostics.get("dispersion", {})
    if gswt_dispersion_diag:
        lines.append(
            "GSWT dispersion diagnostics: "
            f"omega_min={gswt_dispersion_diag.get('omega_min', 'n/a')} "
            f"omega_min_q={gswt_dispersion_diag.get('omega_min_q_vector', 'n/a')} "
            f"soft_mode_count={gswt_dispersion_diag.get('soft_mode_count', 'n/a')}"
        )
    gswt_harmonic = gswt_diagnostics.get("harmonic", {})
    if gswt.get("payload_kind") == "python_glswt_single_q_z_harmonic" or gswt_harmonic:
        lines.append(
            "GSWT single-q z-harmonic diagnostics: "
            f"z_harmonic_cutoff={gswt.get('z_harmonic_cutoff', 'n/a')} "
            f"reference_mode={gswt.get('z_harmonic_reference_mode', 'input')} "
            f"phase_grid_size={gswt.get('phase_grid_size', gswt_harmonic.get('phase_grid_size', 'n/a'))} "
            f"sideband_cutoff={gswt.get('sideband_cutoff', gswt_diagnostics.get('bogoliubov', {}).get('sideband_cutoff', 'n/a'))} "
            f"max_reconstruction_error={gswt_harmonic.get('max_reconstruction_error', 'n/a')} "
            f"max_norm_error={gswt_harmonic.get('max_norm_error', 'n/a')}"
        )
    reference_selection = gswt_diagnostics.get("reference_selection", {})
    if reference_selection:
        lines.append(
            "GSWT reference selection: "
            f"requested_mode={reference_selection.get('requested_mode', 'n/a')} "
            f"resolved_mode={reference_selection.get('resolved_mode', 'n/a')} "
            f"dispersion_recomputed={reference_selection.get('dispersion_recomputed', 'n/a')} "
            f"input_retained_linear_term_max_norm={reference_selection.get('input_retained_linear_term_max_norm', 'n/a')} "
            f"selected_retained_linear_term_max_norm={reference_selection.get('selected_retained_linear_term_max_norm', 'n/a')}"
        )
    reference_dispersion_comparison = _gswt_reference_dispersion_comparison_line(gswt)
    if reference_dispersion_comparison is not None:
        lines.append(reference_dispersion_comparison)
    restricted_ansatz_stationarity = gswt_diagnostics.get("restricted_ansatz_stationarity", {})
    if restricted_ansatz_stationarity:
        lines.append(
            "GSWT restricted-ansatz stationarity diagnostics: "
            f"optimizer_success={restricted_ansatz_stationarity.get('optimizer_success', 'n/a')} "
            f"optimizer_method={restricted_ansatz_stationarity.get('optimizer_method', 'n/a')} "
            f"optimization_mode={restricted_ansatz_stationarity.get('optimization_mode', 'n/a')} "
            f"best_objective={restricted_ansatz_stationarity.get('best_objective', 'n/a')}"
        )
    truncated_z_harmonic_stationarity = gswt_diagnostics.get("truncated_z_harmonic_stationarity", {})
    if truncated_z_harmonic_stationarity:
        lines.append(
            "GSWT truncated z-harmonic stationarity diagnostics: "
            f"scope={truncated_z_harmonic_stationarity.get('scope', 'n/a')} "
            f"projection_kind={truncated_z_harmonic_stationarity.get('projection_kind', 'n/a')} "
            f"harmonic_cutoff={truncated_z_harmonic_stationarity.get('harmonic_cutoff', 'n/a')} "
            f"full_dft_harmonic_count={truncated_z_harmonic_stationarity.get('full_dft_harmonic_count', 'n/a')} "
            f"discarded_harmonic_count={truncated_z_harmonic_stationarity.get('discarded_harmonic_count', 'n/a')} "
            f"is_stationary={truncated_z_harmonic_stationarity.get('is_stationary', 'n/a')} "
            f"linear_term_max_norm={truncated_z_harmonic_stationarity.get('linear_term_max_norm', 'n/a')} "
            f"linear_term_mean_norm={truncated_z_harmonic_stationarity.get('linear_term_mean_norm', 'n/a')} "
            f"discarded_linear_term_max_norm={truncated_z_harmonic_stationarity.get('discarded_linear_term_max_norm', 'n/a')}"
        )
    truncated_z_harmonic_local_refinement = gswt_diagnostics.get("truncated_z_harmonic_local_refinement", {})
    if truncated_z_harmonic_local_refinement:
        lines.append(
            "GSWT truncated z-harmonic local refinement: "
            f"status={truncated_z_harmonic_local_refinement.get('status', 'n/a')} "
            f"selected_step_size={truncated_z_harmonic_local_refinement.get('selected_step_size', 'n/a')} "
            f"iteration_count={truncated_z_harmonic_local_refinement.get('iteration_count', 'n/a')} "
            f"initial_retained_linear_term_max_norm={truncated_z_harmonic_local_refinement.get('initial_retained_linear_term_max_norm', 'n/a')} "
            f"refined_retained_linear_term_max_norm={truncated_z_harmonic_local_refinement.get('refined_retained_linear_term_max_norm', 'n/a')}"
        )
    gswt_stationarity = gswt_diagnostics.get("stationarity", {})
    if gswt_stationarity:
        lines.append(
            "GSWT stationarity diagnostics: "
            f"scope={gswt_stationarity.get('scope', 'n/a')} "
            f"sampling_kind={gswt_stationarity.get('sampling_kind', 'n/a')} "
            f"is_stationary={gswt_stationarity.get('is_stationary', 'n/a')} "
            f"linear_term_max_norm={gswt_stationarity.get('linear_term_max_norm', 'n/a')} "
            f"linear_term_mean_norm={gswt_stationarity.get('linear_term_mean_norm', 'n/a')}"
        )
    gswt_bogoliubov = gswt_diagnostics.get("bogoliubov", {})
    if gswt_bogoliubov:
        lines.append(
            "GSWT Bogoliubov diagnostics: "
            f"mode_count={gswt_bogoliubov.get('mode_count', 'n/a')} "
            f"max_A_antihermitian_norm={gswt_bogoliubov.get('max_A_antihermitian_norm', 'n/a')} "
            f"max_B_asymmetry_norm={gswt_bogoliubov.get('max_B_asymmetry_norm', 'n/a')} "
            f"max_complex_eigenvalue_count={gswt_bogoliubov.get('max_complex_eigenvalue_count', 'n/a')}"
        )
    gswt_error = gswt.get("error", {})
    if gswt_error:
        lines.append(
            f"GSWT error: {gswt_error.get('code', 'gswt-error')} {gswt_error.get('message', '')}".strip()
        )
    if gswt.get("message"):
        lines.append(f"GSWT message: {gswt.get('message')}")
    lines.extend(_single_q_convergence_lines(payload))
    if backend_name:
        lines.append(f"LSWT backend: {backend_name}")
    lswt_status = lswt.get("status")
    if lswt_status:
        lines.append(f"LSWT status: {lswt_status}")
    lswt_error = lswt.get("error", {})
    if lswt_error:
        lines.append(
            f"LSWT error: {lswt_error.get('code', 'lswt-error')} {lswt_error.get('message', '')}".strip()
        )
    lswt_failure_summary = summarize_lswt_failure(payload)
    if lswt_failure_summary:
        lines.append(f"LSWT interpretation: {lswt_failure_summary['interpretation']}")
        lines.append(f"LSWT likely cause: {lswt_failure_summary['likely_cause']}")
        lines.append("LSWT suggested next steps:")
        for step in lswt_failure_summary["next_steps"]:
            lines.append(f"- {step}")
    lswt_path = lswt.get("path", {})
    if lswt_path.get("labels"):
        lines.append(f"LSWT path labels: {lswt_path.get('labels')}")
    dispersion = linear_spin_wave.get("dispersion", [])
    if dispersion:
        lines.append("Linear spin-wave points:")
        for point in dispersion:
            lines.append(f"- q={point['q']} omega={point['omega']}")
    else:
        lines.append("Linear spin-wave points: unavailable")
    return "\n".join(lines)


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
