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
SUNNY_THERMODYNAMICS_SCRIPT = SCRIPT_DIR / "run_sunny_sun_thermodynamics.jl"


def _error(code, message, *, payload_kind=None, backend=None):
    return {
        "status": "error",
        "backend": {"name": backend or "Sunny.jl", "mode": "SUN"},
        "payload_kind": payload_kind,
        "error": {"code": code, "message": message},
    }


def _extract_payload(payload):
    if isinstance(payload, dict) and "payload_kind" in payload:
        return payload
    if isinstance(payload, dict):
        embedded = payload.get("thermodynamics_payload")
        if isinstance(embedded, dict):
            return embedded
    return None


def run_sunny_sun_thermodynamics(payload, julia_cmd="julia"):
    thermodynamics_payload = _extract_payload(payload)
    if thermodynamics_payload is None:
        return _error(
            "missing-thermodynamics-payload",
            "Thermodynamics stage requires a `thermodynamics_payload` dictionary",
        )

    payload_kind = thermodynamics_payload.get("payload_kind")
    backend = thermodynamics_payload.get("backend", "Sunny.jl")
    if payload_kind != "sunny_sun_thermodynamics":
        return _error(
            "unsupported-thermodynamics-payload",
            f"Unsupported thermodynamics payload kind: {payload_kind}",
            payload_kind=payload_kind,
            backend=backend,
        )

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(thermodynamics_payload, handle, indent=2, sort_keys=True)

    try:
        completed = subprocess.run(
            [julia_cmd, str(SUNNY_THERMODYNAMICS_SCRIPT), str(payload_path)],
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
    print(json.dumps(run_sunny_sun_thermodynamics(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
