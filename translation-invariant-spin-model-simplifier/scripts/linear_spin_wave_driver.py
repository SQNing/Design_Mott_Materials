#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from build_lswt_payload import build_lswt_payload


def detect_julia():
    return shutil.which("julia")


def check_sunny_available(julia_cmd):
    try:
        completed = subprocess.run(
            [julia_cmd, "-e", "using Sunny"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return False, str(exc)
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Sunny.jl is not available"
        return False, message
    return True, None


def _error(code, message):
    return {"status": "error", "error": {"code": code, "message": message}}


def run_backend(payload, julia_cmd):
    runner = Path(__file__).with_name("run_sunny_lswt.jl")
    if not runner.exists():
        return _error("backend-execution-failed", "Sunny LSWT runner script is missing")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle)
        input_path = handle.name

    completed = subprocess.run(
        [julia_cmd, str(runner), input_path],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Sunny backend execution failed"
        return _error("backend-execution-failed", message)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _error("result-parse-failed", f"Could not parse Sunny backend output: {exc}")


def run_linear_spin_wave(model, julia_cmd=None):
    payload_result = build_lswt_payload(model)
    if payload_result["status"] != "ok":
        return payload_result

    julia_cmd = julia_cmd or detect_julia()
    if not julia_cmd:
        return _error("missing-julia-runtime", "Julia runtime is required for Sunny-backed LSWT")

    sunny_available, message = check_sunny_available(julia_cmd)
    if not sunny_available:
        return _error("missing-sunny-package", message or "Sunny.jl is not installed in the selected Julia environment")

    result = run_backend(payload_result["payload"], julia_cmd=julia_cmd)
    if isinstance(result, dict):
        result.setdefault("path", payload_result["payload"].get("path", {}))
        result.setdefault("spatial_dimension", payload_result["payload"].get("spatial_dimension"))
    return result


def exact_diagonalization_branch(model):
    local_dim = int(model["local_dim"])
    cluster_size = int(model["cluster_size"])
    if local_dim ** cluster_size > 256:
        return {"supported": False, "reason": "hilbert-space-too-large"}

    exchange = float(model.get("exchange", 1.0))
    sx = 0.5 * np.array([[0, 1], [1, 0]], dtype=complex)
    sy = 0.5 * np.array([[0, -1j], [1j, 0]], dtype=complex)
    sz = 0.5 * np.array([[1, 0], [0, -1]], dtype=complex)
    hamiltonian = exchange * (np.kron(sx, sx) + np.kron(sy, sy) + np.kron(sz, sz))
    eigenvalues = np.linalg.eigvalsh(hamiltonian)
    return {
        "supported": True,
        "ground_state_energy": float(np.min(eigenvalues)),
        "eigenvalues": eigenvalues.real.tolist(),
    }


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--julia", default=None)
    args = parser.parse_args()
    payload = _load_payload(args.input)
    output = run_linear_spin_wave(payload, julia_cmd=args.julia)
    if "cluster_size" in payload and "local_dim" in payload:
        output["exact_diagonalization"] = exact_diagonalization_branch(payload)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
