#!/usr/bin/env python3
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from classical_solver_driver import run_classical_solver
from linear_spin_wave_driver import run_linear_spin_wave
from render_plots import render_plots
from render_report import render_text


def _has_classical_state(payload):
    classical = payload.get("classical", {})
    return bool(classical.get("classical_state") or payload.get("classical_state"))


def _can_run_classical(payload):
    return bool(payload.get("bonds"))


def _can_run_lswt(payload):
    return _has_classical_state(payload)


def _populate_missing_results(payload, *, run_missing_classical=True, run_missing_lswt=True):
    if run_missing_classical and not _has_classical_state(payload) and _can_run_classical(payload):
        payload = run_classical_solver(payload)

    if run_missing_lswt and "lswt" not in payload and _can_run_lswt(payload):
        payload["lswt"] = run_linear_spin_wave(payload)

    return payload


def write_results_bundle(payload, output_dir, *, run_missing_classical=True, run_missing_lswt=True):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_payload = _populate_missing_results(
        deepcopy(payload),
        run_missing_classical=run_missing_classical,
        run_missing_lswt=run_missing_lswt,
    )
    plots = render_plots(bundle_payload, output_dir=output_dir)
    bundle_payload["plots"] = plots

    report_text = render_text(bundle_payload)
    (output_dir / "report.txt").write_text(report_text, encoding="utf-8")

    manifest = {
        "status": "ok" if plots.get("status") == "ok" else "partial",
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
    parser.add_argument("--no-auto-lswt", action="store_true")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(
        json.dumps(
            write_results_bundle(
                payload,
                output_dir=args.output_dir,
                run_missing_classical=not args.no_auto_classical,
                run_missing_lswt=not args.no_auto_lswt,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
