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
