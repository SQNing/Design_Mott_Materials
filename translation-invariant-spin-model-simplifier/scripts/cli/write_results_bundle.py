#!/usr/bin/env python3
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from classical.classical_solver_driver import estimate_thermodynamics, run_classical_solver
from common.classical_contract_resolution import (
    get_classical_state_result,
    get_downstream_stage_status,
    get_standardized_classical_state,
)
from common.cpn_classical_state import has_spin_frame_classical_state
from common.lswt_failure_analysis import summarize_lswt_failure
from lswt.linear_spin_wave_driver import run_linear_spin_wave
from lswt.python_glswt_driver import run_python_glswt_driver
from lswt.sun_gswt_driver import run_sun_gswt
from output.render_plots import render_plots
from output.render_report import render_text

def _downstream_stage_status(payload, stage_name):
    return get_downstream_stage_status(payload, stage_name)


def _has_classical_state(payload):
    return bool(get_standardized_classical_state(payload, prefer_nested_legacy=True))


def _has_gswt_result(payload):
    return isinstance(payload.get("gswt"), dict)


def _get_gswt_payload(payload):
    gswt_payload = payload.get("gswt_payload")
    if isinstance(gswt_payload, dict):
        return gswt_payload
    return None


def _can_run_classical(payload):
    return bool(payload.get("bonds"))


def _can_run_gswt(payload):
    if _get_gswt_payload(payload) is None:
        return False
    compatibility_status = _downstream_stage_status(payload, "gswt")
    if compatibility_status is not None:
        return compatibility_status == "ready"
    return True


def _run_gswt_stage(payload):
    gswt_payload = _get_gswt_payload(payload)
    payload_kind = str(gswt_payload.get("payload_kind"))
    if payload_kind in {"python_glswt_local_rays", "python_glswt_single_q_z_harmonic"}:
        payload["gswt"] = run_python_glswt_driver(gswt_payload)
        return payload
    payload["gswt"] = run_sun_gswt(payload)
    return payload


def _can_run_lswt(payload):
    compatibility_status = _downstream_stage_status(payload, "lswt")
    if compatibility_status is not None:
        return compatibility_status == "ready"
    return has_spin_frame_classical_state(payload)


def _has_thermodynamics_result(payload):
    return bool(payload.get("thermodynamics_result", {}).get("grid"))


def _can_run_thermodynamics(payload):
    thermodynamics = payload.get("thermodynamics", {})
    if not (bool(payload.get("bonds")) and bool(thermodynamics.get("temperatures"))):
        return False
    compatibility_status = _downstream_stage_status(payload, "thermodynamics")
    if compatibility_status is not None:
        return compatibility_status in {"ready", "review"}
    return True


def _thermodynamics_configuration(payload):
    thermodynamics = payload.get("thermodynamics", {})
    if isinstance(thermodynamics, dict) and thermodynamics:
        return thermodynamics
    thermodynamics_result = payload.get("thermodynamics_result", {})
    if isinstance(thermodynamics_result, dict):
        configuration = thermodynamics_result.get("configuration", {})
        if isinstance(configuration, dict):
            return configuration
    return {}


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
    run_missing_gswt=True,
    run_missing_lswt=True,
):
    if run_missing_classical and not _has_classical_state(payload) and _can_run_classical(payload):
        classical_payload = deepcopy(payload)
        if not run_missing_thermodynamics:
            classical_payload.pop("thermodynamics", None)
        payload = run_classical_solver(classical_payload)

    if run_missing_thermodynamics and not _has_thermodynamics_result(payload) and _can_run_thermodynamics(payload):
        payload = _run_thermodynamics_stage(payload)

    if run_missing_gswt and not _has_gswt_result(payload) and _can_run_gswt(payload):
        payload = _run_gswt_stage(payload)

    if run_missing_lswt and "lswt" not in payload and _can_run_lswt(payload):
        payload["lswt"] = run_linear_spin_wave(payload)

    return payload


def _stage_summary(
    original_payload,
    bundle_payload,
    *,
    run_missing_classical,
    run_missing_thermodynamics,
    run_missing_gswt,
    run_missing_lswt,
):
    classical_present_before = _has_classical_state(original_payload)
    classical_present_after = _has_classical_state(bundle_payload)
    thermodynamics_present_before = _has_thermodynamics_result(original_payload)
    thermodynamics_present_after = _has_thermodynamics_result(bundle_payload)
    gswt_present_before = _has_gswt_result(original_payload)
    gswt_present_after = _has_gswt_result(bundle_payload)
    lswt_present_before = "lswt" in original_payload
    lswt_present_after = "lswt" in bundle_payload
    thermodynamics_configuration = _thermodynamics_configuration(bundle_payload)
    classical_state_result = get_classical_state_result(bundle_payload) or {}
    original_classical = original_payload.get("classical", {}) if isinstance(original_payload, dict) else {}
    bundle_classical = bundle_payload.get("classical", {}) if isinstance(bundle_payload, dict) else {}
    if not isinstance(original_classical, dict):
        original_classical = {}
    if not isinstance(bundle_classical, dict):
        bundle_classical = {}
    lswt_summary = {
        "present": bool(lswt_present_after),
        "auto_ran": bool(run_missing_lswt and not lswt_present_before and lswt_present_after),
        "status": bundle_payload.get("lswt", {}).get("status"),
        "backend": bundle_payload.get("lswt", {}).get("backend", {}).get("name"),
    }
    lswt_failure_summary = summarize_lswt_failure(bundle_payload)
    if lswt_failure_summary:
        lswt_summary.update(lswt_failure_summary)

    return {
        "classical": {
            "present": bool(classical_present_after),
            "auto_ran": bool(run_missing_classical and not classical_present_before and classical_present_after),
            "chosen_method": bundle_classical.get("chosen_method", original_classical.get("chosen_method")),
            "requested_method": bundle_classical.get("requested_method", original_classical.get("requested_method")),
            "method": classical_state_result.get("method"),
            "role": classical_state_result.get("role"),
            "solver_family": classical_state_result.get("solver_family"),
            "downstream_compatibility": classical_state_result.get("downstream_compatibility"),
        },
        "thermodynamics": {
            "present": bool(thermodynamics_present_after),
            "auto_ran": bool(run_missing_thermodynamics and not thermodynamics_present_before and thermodynamics_present_after),
            "temperature_count": len(bundle_payload.get("thermodynamics_result", {}).get("grid", []))
            if thermodynamics_present_after
            else 0,
            "profile": thermodynamics_configuration.get("profile"),
            "backend_method": thermodynamics_configuration.get("backend_method"),
            "sweeps": thermodynamics_configuration.get("sweeps"),
            "burn_in": thermodynamics_configuration.get("burn_in"),
            "measurement_interval": thermodynamics_configuration.get("measurement_interval"),
        },
        "gswt": {
            "present": bool(gswt_present_after),
            "auto_ran": bool(run_missing_gswt and not gswt_present_before and gswt_present_after),
            "status": bundle_payload.get("gswt", {}).get("status"),
            "backend": bundle_payload.get("gswt", {}).get("backend", {}).get("name"),
        },
        "lswt": lswt_summary,
    }


def write_results_bundle(
    payload,
    output_dir,
    *,
    run_missing_classical=True,
    run_missing_thermodynamics=True,
    run_missing_gswt=True,
    run_missing_lswt=True,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    original_payload = deepcopy(payload)
    bundle_payload = _populate_missing_results(
        deepcopy(payload),
        run_missing_classical=run_missing_classical,
        run_missing_thermodynamics=run_missing_thermodynamics,
        run_missing_gswt=run_missing_gswt,
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
            run_missing_gswt=run_missing_gswt,
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
    parser.add_argument("--no-auto-gswt", action="store_true")
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
                run_missing_gswt=not args.no_auto_gswt,
                run_missing_lswt=not args.no_auto_lswt,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
