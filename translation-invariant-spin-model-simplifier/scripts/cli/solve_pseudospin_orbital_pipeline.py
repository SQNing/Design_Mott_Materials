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
    diagnose_sun_gswt_classical_state,
    solve_sun_gswt_classical_ground_state,
    solve_sun_gswt_single_q_ground_state,
)
from classical.sunny_sun_classical_driver import run_sunny_sun_classical
from classical.sunny_sun_thermodynamics_driver import run_sunny_sun_thermodynamics
from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload
from common.cpn_classical_state import resolve_cpn_classical_state_payload, resolve_cpn_local_state
from lswt.build_sun_gswt_payload import build_sun_gswt_payload
from lswt.sun_gswt_driver import run_sun_gswt
from output.render_pseudospin_orbital_report import write_pseudospin_orbital_reports
from simplify.group_pseudospin_orbital_terms import group_pseudospin_orbital_terms
from simplify.simplify_pseudospin_orbital_payload import simplify_pseudospin_orbital_payload


def _solver_phase_summary(
    parsed_payload,
    simplified_payload,
    grouped_payload,
    classical_model,
    solver_result,
    report_manifest,
    classical_method,
    *,
    thermodynamics_backend=None,
    thermodynamics_result=None,
    dos_result=None,
):
    convergence = solver_result.get("convergence", {})
    relaxed_lt = solver_result.get("relaxed_lt", {})
    projector = solver_result.get("projector_diagnostics", {})
    stationarity = solver_result.get("stationarity", {})
    ansatz_stationarity = solver_result.get("ansatz_stationarity", {})
    backend = solver_result.get("backend", {}) if isinstance(solver_result.get("backend"), dict) else {}
    gswt = solver_result.get("gswt", {})
    gswt_ordering = gswt.get("ordering", {}) if isinstance(gswt, dict) else {}
    gswt_compatibility = gswt_ordering.get("compatibility_with_supercell", {}) if isinstance(gswt_ordering, dict) else {}
    grid_shape = projector.get("grid_shape")
    thermodynamics_result = thermodynamics_result or {}
    thermodynamics_grid = thermodynamics_result.get("grid", []) if isinstance(thermodynamics_result, dict) else []
    thermodynamics_backend_info = (
        thermodynamics_result.get("backend", {})
        if isinstance(thermodynamics_result.get("backend"), dict)
        else {}
    )
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
        f"- classical_backend: {backend.get('name')}",
        f"- classical_backend_mode: {backend.get('mode')}",
        f"- classical_backend_solver: {backend.get('solver')}",
        f"- ansatz: {solver_result.get('ansatz')}",
        f"- q_vector: {solver_result.get('q_vector')}",
        f"- supercell_shape: {solver_result.get('supercell_shape')}",
        f"- gswt_payload_written: {classical_method in {'sun-gswt-cpn', 'sun-gswt-single-q', 'sunny-cpn-minimize'}}",
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
        "## Thermodynamics",
        "",
        f"- thermodynamics_backend: {thermodynamics_backend}",
        f"- thermodynamics_present: {bool(thermodynamics_grid)}",
        f"- thermodynamics_method: {thermodynamics_result.get('method')}",
        f"- thermodynamics_backend_name: {thermodynamics_backend_info.get('name')}",
        f"- thermodynamics_backend_sampler: {thermodynamics_backend_info.get('sampler')}",
        f"- thermodynamics_temperature_count: {len(thermodynamics_grid)}",
        f"- dos_present: {dos_result is not None}",
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
    supercell_shape=(1, 1, 1),
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    max_sweeps=200,
    run_thermodynamics=False,
    thermodynamics_backend=None,
    temperatures=None,
    thermo_seed=0,
    thermo_sweeps=100,
    thermo_burn_in=50,
    thermo_measurement_interval=1,
    thermo_proposal="delta",
    thermo_proposal_scale=0.2,
    thermo_pt_temperatures=None,
    thermo_pt_exchange_interval=1,
    thermo_wl_bounds=None,
    thermo_wl_bin_size=None,
    thermo_wl_windows=1,
    thermo_wl_overlap=0.25,
    thermo_wl_ln_f=1.0,
    thermo_wl_sweeps=100,
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

    if run_thermodynamics and classical_method == "restricted-product-state":
        raise ValueError("Sunny thermodynamics requires a CP^(N-1) classical state")

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
    elif classical_method == "sunny-cpn-minimize":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        backend_result = run_sunny_sun_classical(
            {
                "backend": "Sunny.jl",
                "payload_kind": "sunny_sun_classical",
                "model": classical_model,
                "supercell_shape": list(supercell_shape),
                "starts": int(starts),
                "seed": int(seed),
            }
        )
        solver_result = {key: value for key, value in backend_result.items() if key != "status"}
        state = resolve_cpn_local_state(solver_result, default_supercell_shape=supercell_shape)
        if state is not None:
            diagnostics = diagnose_sun_gswt_classical_state(classical_model, state)
            solver_result = {
                **solver_result,
                "supercell_shape": list(solver_result.get("supercell_shape", state["shape"])),
                "local_rays": list(solver_result.get("local_rays", state["local_rays"])),
                "classical_state": resolve_cpn_classical_state_payload(
                    solver_result,
                    default_supercell_shape=supercell_shape,
                ),
                "projector_diagnostics": diagnostics["projector_diagnostics"],
                "stationarity": diagnostics["stationarity"],
            }
        gswt_payload = build_sun_gswt_payload(classical_model, classical_state=solver_result) if state is not None else None
    else:
        raise ValueError(f"unsupported classical_method: {classical_method}")

    thermodynamics_result = None
    dos_result = None
    if run_thermodynamics:
        resolved_backend = str(thermodynamics_backend or "sunny-local-sampler")
        resolved_temperatures = [float(value) for value in (temperatures or [])]
        resolved_pt_temperatures = [float(value) for value in (thermo_pt_temperatures or [])]

        if resolved_backend == "sunny-parallel-tempering":
            if not resolved_pt_temperatures:
                raise ValueError("sunny-parallel-tempering requires --thermo-pt-temperatures")
            if resolved_temperatures and resolved_temperatures != resolved_pt_temperatures:
                raise ValueError("for sunny-parallel-tempering, --temperatures must match --thermo-pt-temperatures")
            resolved_temperatures = list(resolved_pt_temperatures)
        elif resolved_backend == "sunny-wang-landau":
            if thermo_wl_bounds is None or thermo_wl_bin_size is None:
                raise ValueError("sunny-wang-landau requires --thermo-wl-bounds and --thermo-wl-bin-size")
            if not resolved_temperatures:
                raise ValueError("sunny-wang-landau requires --temperatures")
        else:
            if not resolved_temperatures:
                raise ValueError(f"{resolved_backend} requires --temperatures")

        initial_state = resolve_cpn_local_state(solver_result, default_supercell_shape=supercell_shape)
        if initial_state is None:
            raise ValueError("Sunny thermodynamics requires a CP^(N-1) classical state")

        thermodynamics_payload = {
            "backend": "Sunny.jl",
            "payload_kind": "sunny_sun_thermodynamics",
            "backend_method": resolved_backend,
            "model": classical_model,
            "initial_state": initial_state,
            "supercell_shape": list(initial_state["shape"]),
            "temperatures": resolved_temperatures,
            "seed": int(thermo_seed),
            "sweeps": int(thermo_sweeps),
            "burn_in": int(thermo_burn_in),
            "measurement_interval": int(thermo_measurement_interval),
            "proposal": str(thermo_proposal),
            "proposal_scale": float(thermo_proposal_scale),
            "pt_temperatures": resolved_pt_temperatures,
            "pt_exchange_interval": int(thermo_pt_exchange_interval),
            "wl_bounds": list(thermo_wl_bounds) if thermo_wl_bounds is not None else None,
            "wl_bin_size": float(thermo_wl_bin_size) if thermo_wl_bin_size is not None else None,
            "wl_windows": int(thermo_wl_windows),
            "wl_overlap": float(thermo_wl_overlap),
            "wl_ln_f": float(thermo_wl_ln_f),
            "wl_sweeps": int(thermo_wl_sweeps),
        }
        backend_output = run_sunny_sun_thermodynamics(thermodynamics_payload)
        if backend_output.get("status") != "ok":
            error = backend_output.get("error", {})
            code = error.get("code", "thermodynamics-backend-error")
            message = error.get("message", "Sunny thermodynamics backend failed")
            raise RuntimeError(f"{code}: {message}")

        thermodynamics_result = backend_output.get("thermodynamics_result")
        dos_result = backend_output.get("dos_result")
        thermodynamics_backend = resolved_backend

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_path = output_dir / "parsed_payload.json"
    simplified_path = output_dir / "simplified_payload.json"
    grouped_path = output_dir / "grouped_terms.json"
    classical_model_path = output_dir / "classical_model.json"
    solver_result_path = output_dir / "solver_result.json"
    gswt_payload_path = output_dir / "gswt_payload.json"
    gswt_result_path = output_dir / "gswt_result.json"
    thermodynamics_result_path = output_dir / "thermodynamics_result.json"
    dos_result_path = output_dir / "dos_result.json"

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
    if thermodynamics_result is not None:
        thermodynamics_result_path.write_text(
            json.dumps(thermodynamics_result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if dos_result is not None:
        dos_result_path.write_text(json.dumps(dos_result, indent=2, sort_keys=True), encoding="utf-8")

    phase_note = _write_solver_stage_markdown(
        _solver_phase_summary(
            parsed_payload,
            simplified_payload,
            grouped_payload,
            classical_model,
            solver_result,
            report_manifest,
            classical_method,
            thermodynamics_backend=thermodynamics_backend,
            thermodynamics_result=thermodynamics_result,
            dos_result=dos_result,
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
            "thermodynamics_result": str(thermodynamics_result_path) if thermodynamics_result is not None else None,
            "dos_result": str(dos_result_path) if dos_result is not None else None,
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
        choices=["restricted-product-state", "sun-gswt-cpn", "sun-gswt-single-q", "sunny-cpn-minimize"],
    )
    parser.add_argument("--supercell-shape", type=int, nargs=3, metavar=("NX", "NY", "NZ"), default=(1, 1, 1))
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-linear-size", type=int, default=5)
    parser.add_argument("--convergence-repeats", type=int, default=2)
    parser.add_argument("--max-sweeps", type=int, default=200)
    parser.add_argument("--run-thermodynamics", action="store_true")
    parser.add_argument(
        "--thermodynamics-backend",
        choices=["sunny-local-sampler", "sunny-parallel-tempering", "sunny-wang-landau"],
    )
    parser.add_argument("--temperatures", type=float, nargs="+")
    parser.add_argument("--thermo-seed", type=int, default=0)
    parser.add_argument("--thermo-sweeps", type=int, default=100)
    parser.add_argument("--thermo-burn-in", type=int, default=50)
    parser.add_argument("--thermo-measurement-interval", type=int, default=1)
    parser.add_argument("--thermo-proposal", choices=["delta", "uniform", "flip"], default="delta")
    parser.add_argument("--thermo-proposal-scale", type=float, default=0.2)
    parser.add_argument("--thermo-pt-temperatures", type=float, nargs="+")
    parser.add_argument("--thermo-pt-exchange-interval", type=int, default=1)
    parser.add_argument("--thermo-wl-bounds", type=float, nargs=2)
    parser.add_argument("--thermo-wl-bin-size", type=float)
    parser.add_argument("--thermo-wl-windows", type=int, default=1)
    parser.add_argument("--thermo-wl-overlap", type=float, default=0.25)
    parser.add_argument("--thermo-wl-ln-f", type=float, default=1.0)
    parser.add_argument("--thermo-wl-sweeps", type=int, default=100)
    args = parser.parse_args()

    manifest = solve_from_files(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        output_dir=Path(args.output_dir),
        docs_dir=Path(args.docs_dir),
        compile_pdf=not args.no_pdf,
        coefficient_tolerance=float(args.coefficient_tolerance),
        classical_method=str(args.classical_method),
        supercell_shape=tuple(int(value) for value in args.supercell_shape),
        starts=int(args.starts),
        seed=int(args.seed),
        max_linear_size=int(args.max_linear_size),
        convergence_repeats=int(args.convergence_repeats),
        max_sweeps=int(args.max_sweeps),
        run_thermodynamics=bool(args.run_thermodynamics),
        thermodynamics_backend=str(args.thermodynamics_backend) if args.thermodynamics_backend is not None else None,
        temperatures=list(args.temperatures) if args.temperatures is not None else None,
        thermo_seed=int(args.thermo_seed),
        thermo_sweeps=int(args.thermo_sweeps),
        thermo_burn_in=int(args.thermo_burn_in),
        thermo_measurement_interval=int(args.thermo_measurement_interval),
        thermo_proposal=str(args.thermo_proposal),
        thermo_proposal_scale=float(args.thermo_proposal_scale),
        thermo_pt_temperatures=list(args.thermo_pt_temperatures) if args.thermo_pt_temperatures is not None else None,
        thermo_pt_exchange_interval=int(args.thermo_pt_exchange_interval),
        thermo_wl_bounds=list(args.thermo_wl_bounds) if args.thermo_wl_bounds is not None else None,
        thermo_wl_bin_size=float(args.thermo_wl_bin_size) if args.thermo_wl_bin_size is not None else None,
        thermo_wl_windows=int(args.thermo_wl_windows),
        thermo_wl_overlap=float(args.thermo_wl_overlap),
        thermo_wl_ln_f=float(args.thermo_wl_ln_f),
        thermo_wl_sweeps=int(args.thermo_wl_sweeps),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
