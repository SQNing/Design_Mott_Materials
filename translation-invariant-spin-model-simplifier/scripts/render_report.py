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
    lines.append(f"Projection status: {payload['projection']['status']}")
    lines.append(f"Chosen classical method: {payload['classical']['chosen_method']}")
    if payload["classical"].get("method_note"):
        lines.append(f"Classical note: {payload['classical']['method_note']}")

    lswt = payload.get("lswt", {})
    if lswt:
        backend_name = lswt.get("backend", {}).get("name", "unknown")
        lines.append(f"LSWT backend: {backend_name}")
        lines.append(f"LSWT status: {lswt.get('status', 'unknown')}")
        if lswt.get("status") == "ok":
            lines.append("Linear spin-wave points:")
            for point in lswt.get("linear_spin_wave", {}).get("dispersion", []):
                lines.append(f"- q={point['q']} omega={point['omega']}")
        elif "error" in lswt:
            lines.append(f"LSWT stop reason: {lswt['error']['code']}")
            lines.append(f"Detail: {lswt['error']['message']}")
            lines.append("Next step: Keep the classical result and install or enable the LSWT backend for this model.")
    else:
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
