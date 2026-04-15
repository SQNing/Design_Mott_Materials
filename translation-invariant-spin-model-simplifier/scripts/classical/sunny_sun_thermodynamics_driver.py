#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
    from common.sunny_bond_adapter import adapt_model_for_sunny_pair_couplings
else:
    from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions
    from common.sunny_bond_adapter import adapt_model_for_sunny_pair_couplings


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


def _preflight_payload_error(thermodynamics_payload):
    model = thermodynamics_payload.get("model")
    if not isinstance(model, dict):
        return None
    if model.get("classical_manifold") != "CP^(N-1)":
        return _error(
            "invalid-thermodynamics-payload",
            "Sunny pseudospin-orbital SUN thermodynamics payload expects a CP^(N-1) model",
            payload_kind=thermodynamics_payload.get("payload_kind"),
            backend=thermodynamics_payload.get("backend", "Sunny.jl"),
        )
    try:
        resolve_pseudospin_orbital_conventions(model)
    except ValueError as exc:
        return _error(
            "invalid-thermodynamics-convention",
            str(exc),
            payload_kind=thermodynamics_payload.get("payload_kind"),
            backend=thermodynamics_payload.get("backend", "Sunny.jl"),
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

    stdout_chunks = []
    stdout_errors = []
    stderr_chunks = []
    stderr_errors = []

    def _read_stdout():
        try:
            stdout_chunks.append(process.stdout.read())
        except BaseException as exc:  # pragma: no cover - defensive propagation
            stdout_errors.append(exc)

    def _read_stderr():
        try:
            for line in process.stderr:
                stderr_chunks.append(line)
                print(line, file=sys.stderr, end="")
                sys.stderr.flush()
        except BaseException as exc:  # pragma: no cover - defensive propagation
            stderr_errors.append(exc)

    stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()

    returncode = process.wait()
    if stdout_errors:
        raise stdout_errors[0]
    if stderr_errors:
        raise stderr_errors[0]
    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode=returncode, cmd=command, output=stdout, stderr=stderr)
    return stdout, stderr


def run_sunny_sun_thermodynamics(payload, julia_cmd="julia", stream_progress=False):
    thermodynamics_payload = _extract_payload(payload)
    if thermodynamics_payload is None:
        return _error(
            "missing-thermodynamics-payload",
            "Thermodynamics stage requires a `thermodynamics_payload` dictionary",
        )

    preflight_error = _preflight_payload_error(thermodynamics_payload)
    if preflight_error is not None:
        return preflight_error

    payload_kind = thermodynamics_payload.get("payload_kind")
    backend = thermodynamics_payload.get("backend", "Sunny.jl")
    if payload_kind != "sunny_sun_thermodynamics":
        return _error(
            "unsupported-thermodynamics-payload",
            f"Unsupported thermodynamics payload kind: {payload_kind}",
            payload_kind=payload_kind,
            backend=backend,
        )

    if isinstance(thermodynamics_payload.get("model"), dict):
        thermodynamics_payload = dict(thermodynamics_payload)
        thermodynamics_payload["model"] = adapt_model_for_sunny_pair_couplings(thermodynamics_payload["model"])

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(thermodynamics_payload, handle, indent=2, sort_keys=True)

    try:
        command = [julia_cmd, str(SUNNY_THERMODYNAMICS_SCRIPT), str(payload_path)]
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
    print(json.dumps(run_sunny_sun_thermodynamics(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
