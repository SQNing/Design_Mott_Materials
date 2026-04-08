#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.build_pseudospin_orbital_classical_model import build_pseudospin_orbital_classical_model
from classical.build_sun_gswt_classical_payload import build_sun_gswt_classical_payload
from classical.pseudospin_orbital_solver import solve_pseudospin_orbital_variational
from classical.sun_gswt_classical_solver import (
    solve_sun_gswt_classical_ground_state,
    solve_sun_gswt_single_q_ground_state,
)
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from lswt.build_sun_gswt_payload import build_sun_gswt_payload
from lswt.sun_gswt_driver import run_sun_gswt
from output.render_pseudospin_orbital_report import write_pseudospin_orbital_reports
from simplify.group_pseudospin_orbital_terms import group_pseudospin_orbital_terms
from simplify.simplify_pseudospin_orbital_payload import simplify_pseudospin_orbital_payload


def _solver_phase_summary(parsed_payload, simplified_payload, grouped_payload, classical_model, solver_result, report_manifest, classical_method):
    convergence = solver_result.get("convergence", {})
    relaxed_lt = solver_result.get("relaxed_lt", {})
    projector = solver_result.get("projector_diagnostics", {})
    stationarity = solver_result.get("stationarity", {})
    ansatz_stationarity = solver_result.get("ansatz_stationarity", {})
    gswt = solver_result.get("gswt", {})
    gswt_ordering = gswt.get("ordering", {}) if isinstance(gswt, dict) else {}
    gswt_compatibility = gswt_ordering.get("compatibility_with_supercell", {}) if isinstance(gswt_ordering, dict) else {}
    grid_shape = projector.get("grid_shape")
    lines = [
        "# Pseudospin-Orbital Solver Phase",
        "",
        "## Conventions",
        "",
        "- local space: pseudospin_orbital",
        "- basis order: orbital_major_spin_minor",
        f"- local_dimension: {parsed_payload['inferred']['local_dimension']}",
        f"- orbital_count: {parsed_payload['inferred']['orbital_count']}",
        f"- classical_method: {classical_method}",
        "- coefficient convention in classical solver: require projected coefficients to be real within tolerance",
        "",
        "## Process",
        "",
        "- parsed POSCAR into lattice metadata",
        "- parsed wannier-style VR_hr.dat into R-resolved bond blocks",
        "- projected bond matrices into pseudospin-orbital operator basis",
        "- generated both human-friendly and full-coefficient reports",
        "- built a classical solver payload",
        "- executed the requested classical-ground-state solver branch",
        "",
        "## Current counts",
        "",
        f"- bond blocks: {len(parsed_payload['bond_blocks'])}",
        f"- grouped bonds: {len(grouped_payload['bonds'])}",
        f"- simplification candidates: {len(simplified_payload['simplification']['candidates'])}",
        f"- classical payload bond count: {classical_model.get('bond_count', classical_model.get('bond_count', len(classical_model.get('bond_tensors', []))))}",
        "",
        "## Solver result",
        "",
        f"- method: {solver_result['method']}",
        f"- energy: {solver_result['energy']}",
        f"- starts: {solver_result['starts']}",
        f"- seed: {solver_result['seed']}",
        f"- ansatz: {solver_result.get('ansatz')}",
        f"- q_vector: {solver_result.get('q_vector')}",
        f"- supercell_shape: {solver_result.get('supercell_shape')}",
        f"- gswt_payload_written: {classical_method in {'sun-gswt-cpn', 'sun-gswt-single-q'}}",
        f"- gswt_status: {gswt.get('status')}",
        f"- gswt_backend: {gswt.get('backend', {}).get('name')}",
        f"- gswt_payload_kind: {gswt.get('payload_kind')}",
        f"- gswt_ordering_ansatz: {gswt_ordering.get('ansatz')}",
        f"- gswt_ordering_compatibility_kind: {gswt_compatibility.get('kind')}",
        f"- ansatz_optimizer_method: {ansatz_stationarity.get('optimizer_method')}",
        f"- ansatz_optimization_mode: {ansatz_stationarity.get('optimization_mode')}",
        f"- ansatz_optimizer_success: {ansatz_stationarity.get('optimizer_success')}",
        f"- ansatz_optimizer_optimality: {ansatz_stationarity.get('optimizer_optimality')}",
        f"- ansatz_optimizer_constraint_violation: {ansatz_stationarity.get('optimizer_constraint_violation')}",
        f"- ansatz_active_q_axes: {ansatz_stationarity.get('active_q_axes')}",
        f"- ansatz_q_parameterization: {ansatz_stationarity.get('q_parameterization')}",
        f"- ansatz_generator_normalization: {ansatz_stationarity.get('generator_normalization')}",
        f"- energy_converged: {convergence.get('energy_converged')}",
        f"- structure_factor_converged: {convergence.get('structure_factor_converged')}",
        f"- structure_factor_peak_q: {convergence.get('structure_factor', {}).get('peak_q')}",
        f"- relaxed_lt_q_seed: {relaxed_lt.get('q_seed')}",
        f"- relaxed_lt_lower_bound: {relaxed_lt.get('lower_bound')}",
        f"- projector_ordering_kind: {projector.get('ordering_kind')}",
        f"- projector_uniform_q_weight: {projector.get('uniform_q_weight')}",
        f"- projector_dominant_ordering_q: {projector.get('dominant_ordering_q')}",
        f"- projector_dominant_ordering_weight: {projector.get('dominant_ordering_weight')}",
        f"- stationarity_max_residual_norm: {stationarity.get('max_residual_norm')}",
        f"- stationarity_mean_residual_norm: {stationarity.get('mean_residual_norm')}",
        "",
        "## Report artifacts",
        "",
        f"- human-friendly pdf status: {report_manifest['reports']['human_friendly']['pdf_status']}",
        f"- full-coefficients pdf status: {report_manifest['reports']['full_coefficients']['pdf_status']}",
        "",
        "## GSWT Diagnostics",
        "",
        "- for `sun-gswt-cpn`, the physically relevant ordering wavevector is read from the Fourier components of the projector field `Q_R = |z_R><z_R|`, not from a gauge phase of `z_R` itself",
        "- for `sun-gswt-single-q`, the current implementation performs single-q direct joint optimization over the ordering vector and internal ansatz variables; it does not do a preliminary q-mesh sweep",
        f"- stored projector diagnostic grid: {grid_shape}",
        f"- stationarity residual definition: {stationarity.get('residual_definition')}",
        "",
        "## Residual limitations",
        "",
        "- the parser remains general in orbital count, but downstream solver coverage is still method-dependent",
        "- the present solver does not yet map this pseudospin-orbital model into the existing spin-only thermodynamics or LSWT chain",
        "- the LT-style relaxed diagnostic is intentionally retained as an alternative classical route and has not been removed",
    ]
    if grid_shape == [1, 1, 1]:
        insertion_index = lines.index("## Residual limitations")
        lines[insertion_index:insertion_index] = [
            "- because the stored projector grid is `[1, 1, 1]`, this run probes only the uniform magnetic-cell ansatz; the absence of nonzero `q` components here is therefore not a model-level conclusion about the true ordering vector",
            "",
        ]
    return "\n".join(lines)


def _write_solver_stage_markdown(summary, docs_dir):
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{date.today().isoformat()}-pseudospin-orbital-solver-phase.md"
    path.write_text(summary, encoding="utf-8")
    return path


def solve_from_files(
    poscar_path,
    hr_path,
    output_dir,
    docs_dir,
    *,
    compile_pdf=True,
    coefficient_tolerance=1e-10,
    classical_method="restricted-product-state",
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    max_sweeps=200,
):
    parsed_payload = build_pseudospin_orbital_payload(
        poscar_path=poscar_path,
        hr_path=hr_path,
        coefficient_tolerance=coefficient_tolerance,
    )
    simplified_payload = simplify_pseudospin_orbital_payload(parsed_payload)
    grouped_payload = group_pseudospin_orbital_terms(parsed_payload)
    report_manifest = write_pseudospin_orbital_reports(
        parsed_payload,
        grouped_payload,
        output_dir=output_dir,
        compile_pdf=compile_pdf,
    )

    if classical_method == "restricted-product-state":
        classical_model = build_pseudospin_orbital_classical_model(parsed_payload)
        solver_result = solve_pseudospin_orbital_variational(
            classical_model,
            starts=starts,
            seed=seed,
            max_linear_size=max_linear_size,
            convergence_repeats=convergence_repeats,
            max_sweeps=max_sweeps,
        )
        gswt_payload = None
    elif classical_method == "sun-gswt-cpn":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        solver_result = solve_sun_gswt_classical_ground_state(
            classical_model,
            starts=starts,
            seed=seed,
        )
        gswt_payload = build_sun_gswt_payload(classical_model, classical_state=solver_result)
    elif classical_method == "sun-gswt-single-q":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        solver_result = solve_sun_gswt_single_q_ground_state(
            classical_model,
            starts=starts,
            seed=seed,
        )
        gswt_payload = build_sun_gswt_payload(classical_model, classical_state=solver_result)
    else:
        raise ValueError(f"unsupported classical_method: {classical_method}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_path = output_dir / "parsed_payload.json"
    simplified_path = output_dir / "simplified_payload.json"
    grouped_path = output_dir / "grouped_terms.json"
    classical_model_path = output_dir / "classical_model.json"
    solver_result_path = output_dir / "solver_result.json"
    gswt_payload_path = output_dir / "gswt_payload.json"
    gswt_result_path = output_dir / "gswt_result.json"

    parsed_path.write_text(json.dumps(parsed_payload, indent=2, sort_keys=True), encoding="utf-8")
    simplified_path.write_text(json.dumps(simplified_payload, indent=2, sort_keys=True), encoding="utf-8")
    grouped_path.write_text(json.dumps(grouped_payload, indent=2, sort_keys=True), encoding="utf-8")
    classical_model_path.write_text(json.dumps(classical_model, indent=2, sort_keys=True), encoding="utf-8")
    if gswt_payload is not None:
        gswt_result = run_sun_gswt(gswt_payload)
        solver_result = {**solver_result, "gswt": gswt_result}
        gswt_payload_path.write_text(json.dumps(gswt_payload, indent=2, sort_keys=True), encoding="utf-8")
        gswt_result_path.write_text(json.dumps(gswt_result, indent=2, sort_keys=True), encoding="utf-8")
    solver_result_path.write_text(json.dumps(solver_result, indent=2, sort_keys=True), encoding="utf-8")

    phase_note = _write_solver_stage_markdown(
        _solver_phase_summary(
            parsed_payload,
            simplified_payload,
            grouped_payload,
            classical_model,
            solver_result,
            report_manifest,
            classical_method,
        ),
        docs_dir=docs_dir,
    )

    return {
        "status": "ok",
        "reports": report_manifest["reports"],
        "solver": solver_result,
        "artifacts": {
            "parsed_payload": str(parsed_path),
            "simplified_payload": str(simplified_path),
            "grouped_terms": str(grouped_path),
            "classical_model": str(classical_model_path),
            "solver_result": str(solver_result_path),
            "gswt_payload": str(gswt_payload_path) if gswt_payload is not None else None,
            "gswt_result": str(gswt_result_path) if gswt_payload is not None else None,
            "phase_note": str(phase_note),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--docs-dir", required=True)
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    parser.add_argument(
        "--classical-method",
        default="restricted-product-state",
        choices=["restricted-product-state", "sun-gswt-cpn", "sun-gswt-single-q"],
    )
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-linear-size", type=int, default=5)
    parser.add_argument("--convergence-repeats", type=int, default=2)
    parser.add_argument("--max-sweeps", type=int, default=200)
    args = parser.parse_args()

    manifest = solve_from_files(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        output_dir=Path(args.output_dir),
        docs_dir=Path(args.docs_dir),
        compile_pdf=not args.no_pdf,
        coefficient_tolerance=float(args.coefficient_tolerance),
        classical_method=str(args.classical_method),
        starts=int(args.starts),
        seed=int(args.seed),
        max_linear_size=int(args.max_linear_size),
        convergence_repeats=int(args.convergence_repeats),
        max_sweeps=int(args.max_sweeps),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
