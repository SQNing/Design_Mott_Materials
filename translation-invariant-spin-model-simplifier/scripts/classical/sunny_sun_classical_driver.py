#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
else:
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions


SCRIPT_DIR = Path(__file__).resolve().parent
SUNNY_CLASSICAL_SCRIPT = SCRIPT_DIR / "run_sunny_sun_classical.jl"


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
        embedded = payload.get("classical_payload")
        if isinstance(embedded, dict):
            return embedded
    return None


def _preflight_payload_error(classical_payload):
    model = classical_payload.get("model")
    if not isinstance(model, dict):
        return None
    try:
        resolve_pseudospin_orbital_conventions(model)
    except ValueError as exc:
        return _error(
            "invalid-classical-convention",
            str(exc),
            payload_kind=classical_payload.get("payload_kind"),
            backend=classical_payload.get("backend", "Sunny.jl"),
        )
    return None


def _run_backend_process(command):
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout, getattr(completed, "stderr", "") or ""


def _run_backend_process_with_progress(command):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    stderr_chunks = []
    for line in process.stderr:
        stderr_chunks.append(line)
        print(line, file=sys.stderr, end="")
        sys.stderr.flush()

    stdout = process.stdout.read()
    returncode = process.wait()
    stderr = "".join(stderr_chunks)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode=returncode, cmd=command, output=stdout, stderr=stderr)
    return stdout, stderr


def run_sunny_sun_classical(payload, julia_cmd="julia", stream_progress=False):
    classical_payload = _extract_payload(payload)
    if classical_payload is None:
        return _error("missing-classical-payload", "Classical stage requires a `classical_payload` dictionary")

    preflight_error = _preflight_payload_error(classical_payload)
    if preflight_error is not None:
        return preflight_error

    payload_kind = classical_payload.get("payload_kind")
    backend = classical_payload.get("backend", "Sunny.jl")
    if payload_kind != "sunny_sun_classical":
        return _error(
            "unsupported-classical-payload",
            f"Unsupported classical payload kind: {payload_kind}",
            payload_kind=payload_kind,
            backend=backend,
        )

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(classical_payload, handle, indent=2, sort_keys=True)

    try:
        command = [julia_cmd, str(SUNNY_CLASSICAL_SCRIPT), str(payload_path)]
        if stream_progress:
            stdout, _stderr = _run_backend_process_with_progress(command)
        else:
            stdout, _stderr = _run_backend_process(command)
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
        result = json.loads(stdout)
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
    print(json.dumps(run_sunny_sun_classical(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
