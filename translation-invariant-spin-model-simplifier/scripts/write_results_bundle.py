#!/usr/bin/env python3
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from render_plots import render_plots
from render_report import render_text


def write_results_bundle(payload, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_payload = deepcopy(payload)
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
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(json.dumps(write_results_bundle(payload, output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
