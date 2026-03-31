#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _error(code, message):
    return {"status": "error", "error": {"code": code, "message": message}}


def normalize_exchange_matrix(term):
    matrix = term.get("matrix")
    if not isinstance(matrix, list) or len(matrix) != 3:
        raise ValueError("bond matrix must be a 3x3 list")
    normalized = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("bond matrix must be a 3x3 list")
        normalized.append([float(value) for value in row])
    return normalized


def build_reference_frames(classical_state):
    frames = classical_state.get("site_frames", [])
    if not frames:
        raise ValueError("classical_state.site_frames is required")
    return [
        {
            "site": int(frame["site"]),
            "spin_length": float(frame["spin_length"]),
            "direction": [float(value) for value in frame["direction"]],
        }
        for frame in frames
    ]


def validate_lswt_scope(model):
    simplified_model = model.get("simplified_model", {})
    if simplified_model.get("three_body_terms"):
        return _error("unsupported-model-scope", "higher-body terms are outside first-stage Sunny-backed LSWT scope")
    bonds = simplified_model.get("bonds", model.get("bonds", []))
    if not bonds:
        return _error("unsupported-model-scope", "at least one bilinear bond is required for LSWT payload construction")
    if "classical_state" not in model:
        return _error("invalid-classical-reference-state", "classical_state is required to build an LSWT payload")
    return None


def build_lswt_payload(model):
    scope_error = validate_lswt_scope(model)
    if scope_error is not None:
        return scope_error

    simplified_model = model.get("simplified_model", {})
    bonds = simplified_model.get("bonds", model.get("bonds", []))
    reference_frames = build_reference_frames(model["classical_state"])
    site_count = max(frame["site"] for frame in reference_frames) + 1
    lattice = model.get("lattice", {})
    positions = lattice.get("positions") or [[0.0, 0.0, 0.0] for _ in range(site_count)]
    lattice_vectors = lattice.get("lattice_vectors") or [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    payload = {
        "backend": "Sunny.jl",
        "lattice": lattice,
        "lattice_vectors": lattice_vectors,
        "positions": positions,
        "template": simplified_model.get("template", "generic"),
        "bonds": [
            {
                "source": int(term["source"]),
                "target": int(term["target"]),
                "vector": [float(value) for value in term.get("vector", [])],
                "exchange_matrix": normalize_exchange_matrix(term),
            }
            for term in bonds
        ],
        "reference_frames": reference_frames,
        "moments": [
            {
                "site": int(frame["site"]),
                "spin": float(frame["spin_length"]),
                "g": 2.0,
            }
            for frame in reference_frames
        ],
        "ordering": model["classical_state"].get("ordering", {}),
        "q_path": model.get("q_path", []),
        "q_grid": model.get("q_grid", []),
        "q_samples": int(model.get("q_samples", 64)),
    }
    return {"status": "ok", "payload": payload}


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    payload = _load_payload(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(build_lswt_payload(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
