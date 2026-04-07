#!/usr/bin/env python3
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.classical_solver_driver import estimate_thermodynamics, run_classical_solver
from lswt.linear_spin_wave_driver import run_linear_spin_wave
from output.render_plots import render_plots
from output.render_report import render_text


def _has_classical_state(payload):
    classical = payload.get("classical", {})
    return bool(classical.get("classical_state") or payload.get("classical_state"))


def _can_run_classical(payload):
    return bool(payload.get("bonds"))


def _can_run_lswt(payload):
    return _has_classical_state(payload)


def _has_thermodynamics_result(payload):
    return bool(payload.get("thermodynamics_result", {}).get("grid"))


def _can_run_thermodynamics(payload):
    thermodynamics = payload.get("thermodynamics", {})
    return bool(payload.get("bonds")) and bool(thermodynamics.get("temperatures"))


def _run_thermodynamics_stage(payload):
    thermodynamics = payload.get("thermodynamics", {})
    payload["thermodynamics_result"] = estimate_thermodynamics(
        payload,
        thermodynamics["temperatures"],
        sweeps=int(thermodynamics.get("sweeps", 100)),
        burn_in=int(thermodynamics.get("burn_in", 50)),
        seed=int(thermodynamics.get("seed", 0)),
        measurement_interval=int(thermodynamics.get("measurement_interval", 1)),
        field_direction=thermodynamics.get("field_direction"),
        high_temperature_entropy=float(thermodynamics.get("high_temperature_entropy", 0.0)),
        energy_infinite_temperature=thermodynamics.get("energy_infinite_temperature"),
        scan_order=str(thermodynamics.get("scan_order", "as_given")),
        reuse_configuration=bool(thermodynamics.get("reuse_configuration", True)),
    )
    return payload


def _populate_missing_results(
    payload,
    *,
    run_missing_classical=True,
    run_missing_thermodynamics=True,
    run_missing_lswt=True,
):
    if run_missing_classical and not _has_classical_state(payload) and _can_run_classical(payload):
        classical_payload = deepcopy(payload)
        if not run_missing_thermodynamics:
            classical_payload.pop("thermodynamics", None)
        payload = run_classical_solver(classical_payload)

    if run_missing_thermodynamics and not _has_thermodynamics_result(payload) and _can_run_thermodynamics(payload):
        payload = _run_thermodynamics_stage(payload)

    if run_missing_lswt and "lswt" not in payload and _can_run_lswt(payload):
        payload["lswt"] = run_linear_spin_wave(payload)

    return payload


def _stage_summary(
    original_payload,
    bundle_payload,
    *,
    run_missing_classical,
    run_missing_thermodynamics,
    run_missing_lswt,
):
    classical_present_before = _has_classical_state(original_payload)
    classical_present_after = _has_classical_state(bundle_payload)
    thermodynamics_present_before = _has_thermodynamics_result(original_payload)
    thermodynamics_present_after = _has_thermodynamics_result(bundle_payload)
    lswt_present_before = "lswt" in original_payload
    lswt_present_after = "lswt" in bundle_payload

    return {
        "classical": {
            "present": bool(classical_present_after),
            "auto_ran": bool(run_missing_classical and not classical_present_before and classical_present_after),
            "chosen_method": bundle_payload.get("classical", {}).get("chosen_method"),
            "requested_method": bundle_payload.get("classical", {}).get("requested_method"),
        },
        "thermodynamics": {
            "present": bool(thermodynamics_present_after),
            "auto_ran": bool(run_missing_thermodynamics and not thermodynamics_present_before and thermodynamics_present_after),
            "temperature_count": len(bundle_payload.get("thermodynamics_result", {}).get("grid", []))
            if thermodynamics_present_after
            else 0,
        },
        "lswt": {
            "present": bool(lswt_present_after),
            "auto_ran": bool(run_missing_lswt and not lswt_present_before and lswt_present_after),
            "status": bundle_payload.get("lswt", {}).get("status"),
            "backend": bundle_payload.get("lswt", {}).get("backend", {}).get("name"),
        },
    }


def write_results_bundle(
    payload,
    output_dir,
    *,
    run_missing_classical=True,
    run_missing_thermodynamics=True,
    run_missing_lswt=True,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    original_payload = deepcopy(payload)
    bundle_payload = _populate_missing_results(
        deepcopy(payload),
        run_missing_classical=run_missing_classical,
        run_missing_thermodynamics=run_missing_thermodynamics,
        run_missing_lswt=run_missing_lswt,
    )
    plots = render_plots(bundle_payload, output_dir=output_dir)
    bundle_payload["plots"] = plots

    report_text = render_text(bundle_payload)
    (output_dir / "report.txt").write_text(report_text, encoding="utf-8")

    manifest = {
        "status": "ok" if plots.get("status") == "ok" else "partial",
        "stages": _stage_summary(
            original_payload,
            bundle_payload,
            run_missing_classical=run_missing_classical,
            run_missing_thermodynamics=run_missing_thermodynamics,
            run_missing_lswt=run_missing_lswt,
        ),
        "plots": plots,
        "report": {"path": str(output_dir / "report.txt")},
    }
    (output_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--no-auto-classical", action="store_true")
    parser.add_argument("--no-auto-thermodynamics", action="store_true")
    parser.add_argument("--no-auto-lswt", action="store_true")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(
        json.dumps(
            write_results_bundle(
                payload,
                output_dir=args.output_dir,
                run_missing_classical=not args.no_auto_classical,
                run_missing_thermodynamics=not args.no_auto_thermodynamics,
                run_missing_lswt=not args.no_auto_lswt,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
