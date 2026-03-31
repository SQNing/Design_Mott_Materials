#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "codex-matplotlib"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _get_classical_state(payload):
    classical = payload.get("classical", {})
    return classical.get("classical_state", payload.get("classical_state", {}))


def _build_plot_payload(payload):
    lswt = payload.get("lswt", {})
    dispersion = lswt.get("linear_spin_wave", {}).get("dispersion", [])
    band_count = max((len(point.get("bands", [])) for point in dispersion), default=0)
    classical_state = _get_classical_state(payload)
    return {
        "metadata": {
            "model_name": payload.get("model_name", ""),
            "backend": lswt.get("backend", {}).get("name", "unknown"),
            "classical_method": payload.get("classical", {}).get("chosen_method", ""),
            "lswt_status": lswt.get("status", "missing"),
        },
        "classical_state": {
            "site_frames": classical_state.get("site_frames", []),
            "ordering": classical_state.get("ordering", {}),
        },
        "lswt_dispersion": {
            "dispersion": dispersion,
            "band_count": band_count,
            "q_points": [point.get("q", []) for point in dispersion],
            "omega_min": min((point.get("omega", 0.0) for point in dispersion), default=0.0),
            "omega_max": max((point.get("omega", 0.0) for point in dispersion), default=0.0),
        },
    }


def _render_classical_state(classical_state, output_path):
    frames = classical_state.get("site_frames", [])
    fig, ax = plt.subplots(figsize=(6, 3))
    xs = list(range(len(frames)))
    ys = [0.0] * len(frames)
    us = [frame["direction"][0] for frame in frames]
    vs = [frame["direction"][2] for frame in frames]
    ax.quiver(xs, ys, us, vs, angles="xy", scale_units="xy", scale=1.0, width=0.008, color="#0b6e4f")
    ax.scatter(xs, ys, color="#1f2937", s=20, zorder=3)
    ax.set_title("Classical Ground State")
    ax.set_xlabel("Site Index")
    ax.set_ylabel("Projected Spin")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _render_dispersion(dispersion, output_path):
    fig, ax = plt.subplots(figsize=(6, 4))
    q_indices = list(range(len(dispersion)))
    band_count = max(len(point.get("bands", [])) for point in dispersion)
    for band_index in range(band_count):
        ys = []
        for point in dispersion:
            bands = point.get("bands", [])
            ys.append(bands[band_index] if band_index < len(bands) else float("nan"))
        ax.plot(q_indices, ys, marker="o", linewidth=1.5)
    ax.set_title("LSWT Dispersion")
    ax.set_xlabel("q-point index")
    ax.set_ylabel("omega")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def render_plots(payload, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_payload = _build_plot_payload(payload)
    (output_dir / "plot_payload.json").write_text(json.dumps(plot_payload, indent=2, sort_keys=True), encoding="utf-8")

    result = {
        "status": "ok",
        "plots": {
            "classical_state": {"status": "skipped", "path": None},
            "lswt_dispersion": {"status": "skipped", "path": None, "reason": ""},
        },
    }

    classical_state = plot_payload["classical_state"]
    if classical_state.get("site_frames"):
        classical_path = output_dir / "classical_state.png"
        _render_classical_state(classical_state, classical_path)
        result["plots"]["classical_state"] = {"status": "ok", "path": str(classical_path)}

    lswt = payload.get("lswt", {})
    dispersion = plot_payload["lswt_dispersion"]["dispersion"]
    if lswt.get("status") == "ok" and dispersion:
        dispersion_path = output_dir / "lswt_dispersion.png"
        _render_dispersion(dispersion, dispersion_path)
        result["plots"]["lswt_dispersion"] = {"status": "ok", "path": str(dispersion_path)}
    else:
        reason = "LSWT result unavailable"
        if lswt.get("error"):
            reason = f"{lswt['error'].get('code', 'lswt-error')}: {lswt['error'].get('message', '')}".strip()
        result["plots"]["lswt_dispersion"] = {"status": "skipped", "path": None, "reason": reason}
        if result["plots"]["classical_state"]["status"] == "ok":
            result["status"] = "partial"

    return result


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
    print(json.dumps(render_plots(payload, output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
