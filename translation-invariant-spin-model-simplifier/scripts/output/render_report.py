#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


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
    plots = payload.get("plots")
    if plots:
        lines.append("")
        lines.append(f"Plot status: {plots.get('status', 'unknown')}")
        for plot_name, metadata in plots.get("plots", {}).items():
            if metadata.get("path"):
                lines.append(f"- {plot_name}: {metadata['path']}")
            elif metadata.get("reason"):
                lines.append(f"- {plot_name}: {metadata.get('status', 'skipped')} ({metadata['reason']})")
    thermodynamics = payload.get("thermodynamics_result", {})
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
    lines.append(f"Projection status: {payload['projection']['status']}")
    lines.append(f"Chosen classical method: {payload['classical']['chosen_method']}")
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
    gswt_error = gswt.get("error", {})
    if gswt_error:
        lines.append(
            f"GSWT error: {gswt_error.get('code', 'gswt-error')} {gswt_error.get('message', '')}".strip()
        )
    if gswt.get("message"):
        lines.append(f"GSWT message: {gswt.get('message')}")
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
