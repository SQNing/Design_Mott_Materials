#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def render_text(payload):
    lines = []
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
    lines.append(f"Projection status: {payload['projection']['status']}")
    lines.append(f"Chosen classical method: {payload['classical']['chosen_method']}")
    lines.append("Linear spin-wave points:")
    for point in payload.get("linear_spin_wave", {}).get("dispersion", []):
        lines.append(f"- q={point['q']} omega={point['omega']}")
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
