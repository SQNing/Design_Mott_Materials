#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SCRIPT_DIR = Path(__file__).resolve().parent
SUNNY_GSWT_SCRIPT = SCRIPT_DIR / "run_sunny_sun_gswt.jl"


def _error(code, message, *, payload_kind=None, backend=None):
    return {
        "status": "error",
        "backend": {"name": backend or "Sunny.jl", "mode": "SUN"},
        "payload_kind": payload_kind,
        "error": {"code": code, "message": message},
    }


def _preflight_payload_error(gswt_payload):
    ordering = gswt_payload.get("ordering")
    if not isinstance(ordering, dict):
        return None
    compatibility = ordering.get("compatibility_with_supercell")
    if not isinstance(compatibility, dict):
        return None
    if ordering.get("ansatz") != "single-q-unitary-ray":
        return None
    if compatibility.get("kind") != "incommensurate":
        return None

    q_vector = ordering.get("q_vector")
    supercell_shape = ordering.get("supercell_shape")
    axis_products = compatibility.get("axis_products", [])
    mismatch_summary = ", ".join(
        f"axis {item.get('axis')}: q*L={item.get('phase_winding')} (nearest integer {item.get('nearest_integer')}, mismatch {item.get('mismatch')})"
        for item in axis_products
    )
    if not mismatch_summary:
        mismatch_summary = "phase winding is not integer on at least one supercell axis"
    message = (
        "Sunny.jl SUN SpinWaveTheory currently requires a periodic magnetic supercell, "
        "but the supplied single-q classical state is incommensurate with that supercell. "
        f"q_vector={q_vector}, supercell_shape={supercell_shape}. {mismatch_summary}. "
        "The current backend cannot evaluate incommensurate single-q SUN-GSWT states through a finite periodic supercell."
    )
    result = _error(
        "unsupported-incommensurate-single-q-sun-gswt",
        message,
        payload_kind=gswt_payload.get("payload_kind"),
        backend=gswt_payload.get("backend", "Sunny.jl"),
    )
    result["ordering"] = ordering
    return result


def _extract_payload(payload):
    if isinstance(payload, dict) and "payload_kind" in payload:
        return payload
    if isinstance(payload, dict):
        embedded = payload.get("gswt_payload")
        if isinstance(embedded, dict):
            return embedded
    return None


def run_sun_gswt(payload, julia_cmd="julia"):
    gswt_payload = _extract_payload(payload)
    if gswt_payload is None:
        return _error("missing-gswt-payload", "GSWT stage requires a `gswt_payload` dictionary")

    preflight_error = _preflight_payload_error(gswt_payload)
    if preflight_error is not None:
        return preflight_error

    payload_kind = gswt_payload.get("payload_kind")
    backend = gswt_payload.get("backend", "Sunny.jl")
    if payload_kind != "sun_gswt_prototype":
        return _error(
            "unsupported-gswt-payload",
            f"Unsupported GSWT payload kind: {payload_kind}",
            payload_kind=payload_kind,
            backend=backend,
        )

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(gswt_payload, handle, indent=2, sort_keys=True)

    try:
        completed = subprocess.run(
            [julia_cmd, str(SUNNY_GSWT_SCRIPT), str(payload_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return _error(
            "missing-julia-command",
            str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return _error(
            "backend-process-failed",
            stderr or str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )
    finally:
        payload_path.unlink(missing_ok=True)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _error(
            "invalid-backend-json",
            str(exc),
            payload_kind=payload_kind,
            backend=backend,
        )

    if isinstance(result, dict) and "path" not in result:
        result["path"] = gswt_payload.get("path", {})
    return result


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--julia-cmd", default="julia")
    args = parser.parse_args()
    payload = _load_payload(args.input)
    print(json.dumps(run_sun_gswt(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
