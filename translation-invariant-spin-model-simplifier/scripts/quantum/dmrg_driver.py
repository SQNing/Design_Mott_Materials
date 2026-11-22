"""DMRG backend driver (ITensor.jl) — stage D.

Mirrors the Sunny driver contract: probe the Julia route, fail closed with
``backend-not-connected`` when ITensor cannot be reached, never fall back to
another backend. The heavy lifting lives in ``run_dmrg_itensor.jl``; this
module compiles the OpSum payload, manages the subprocess, and maps the
result onto the solver response conventions used by ``ed_solver``.

Task entry: ``solve_quantum_dmrg(system, request)`` (workflow dispatch).
"""

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from common.julia_environment import probe_julia_environment
from quantum.mpo_compiler import compile_opsum

_SCRIPT_DIR = Path(__file__).resolve().parent
_DMRG_SCRIPT = _SCRIPT_DIR / "run_dmrg_itensor.jl"
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]
_DMRG_ENV = _PROJECT_ROOT / ".julia-env-dmrg"

_CONTRACT = "dmrg_ground_state/v1"


def _not_connected(detail):
    return {
        "status": "backend-not-connected",
        "backend": {"name": "ITensor.jl", "mode": "DMRG"},
        "blocker": detail,
        "limitations": ["DMRG backend requires a Julia interpreter with the "
                        ".julia-env-dmrg environment instantiated (ITensors + "
                        "ITensorMPS); no silent fallback to another backend."],
    }


def _julia_command():
    """(command_prefix, env_extra, available, detail) for the DMRG Julia route."""
    probe = probe_julia_environment()
    override = os.environ.get("SPINFORGE_JULIA_CMD") or os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if probe["source"] == "project-wrapper":
        # The wrapper selects the project via SPINFORGE_JULIA_PROJECT.
        return ([probe["command"]], {"SPINFORGE_JULIA_PROJECT": str(_DMRG_ENV)},
                probe["available"], probe["detail"])
    prefix = shlex.split(probe["command"])
    prefix += ["--project=%s" % _DMRG_ENV, "--startup-file=no",
               "--history-file=no", "--compiled-modules=no", "--pkgimages=no"]
    return (prefix, {}, probe["available"], probe["detail"] + (" (override)" if override else ""))


def solve_quantum_dmrg(system, request):
    """DMRG ground state of the periodic cluster (chains and 2D strips)."""
    spin = float(request["spin"])
    prefix, env_extra, julia_ok, detail = _julia_command()
    if not julia_ok:
        return _not_connected("julia route unavailable: " + detail)
    if not (_DMRG_ENV / "Manifest.toml").is_file():
        return _not_connected(
            "ITensor environment not instantiated: %s has no Manifest.toml; "
            "run `julia --project=%s -e 'using Pkg; Pkg.instantiate()'`"
            % (_DMRG_ENV, _DMRG_ENV))

    try:
        spec = compile_opsum(system, spin, request)
    except ValueError as exc:
        return {"status": "invalid_request", "task": "quantum_dmrg_ground_state",
                "blocker": str(exc)}
    spec["parameters"] = {
        "nsweeps": int(request.get("dmrg_sweeps", 12)),
        "maxdim": int(request.get("dmrg_maxdim", 200)),
        "cutoff": float(request.get("dmrg_cutoff", 1e-12)),
        # Noise >0 breaks QN block structure in ITensor's eigensolver.
        "noise": float(request.get("dmrg_noise", 0.0)),
        "energy_tol": float(request.get("dmrg_energy_tol", 1e-10)),
        "variance_tol": float(request.get("dmrg_variance_tol", 1e-8)),
        "truncation_tol": float(request.get("dmrg_truncation_tol", 1e-10)),
        "observables": bool(request.get("observables", True)),
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                     delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(spec, handle)
    env = dict(os.environ)
    env.update(env_extra)
    command = prefix + [str(_DMRG_SCRIPT), str(payload_path)]
    timeout = float(request.get("dmrg_timeout_seconds", 3600))
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"status": "inconclusive", "backend": {"name": "ITensor.jl", "mode": "DMRG"},
                "blocker": "dmrg subprocess exceeded timeout_seconds=%g" % timeout}
    finally:
        payload_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        return {"status": "error",
                "backend": {"name": "ITensor.jl", "mode": "DMRG"},
                "error": {"code": "dmrg-subprocess-failed",
                          "message": completed.stderr.strip()[-2000:]}}
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    diag = result["diagnostics"]
    converged = bool(result["converged"])
    correlations = result.get("correlations") or {}
    n = spec["site_count"]
    sz_sz = correlations.get("sz_sz")
    dot = correlations.get("dot")
    observables = None
    if dot is not None:
        observables = {
            "correlation_dot_flat": dot,
            "correlation_sz_sz_flat": sz_sz,
            "correlation_layout": correlations.get("layout"),
            "mps_order": spec["mps_order"],
            "bond_entropies": result["entanglement"]["bond_entropies"],
        }
    def _num(value):
        # null (None) marks non-finite diagnostics from starved runs.
        return float(value) if value is not None else float("nan")

    return {
        "status": "ok" if converged else "inconclusive",
        "schema_version": _CONTRACT,
        "method": "dmrg-itensor",
        "backend": {"name": "ITensor.jl", "mode": "DMRG",
                    "environment": str(_DMRG_ENV)},
        "spin": spin,
        "supercell_shape": list(system.shape),
        "site_count": n,
        "geometry": spec["geometry"],
        "conserve_sz": spec["conserve_sz"],
        "energy": _num(result["energy"]),
        "energy_per_site": _num(result["energy_per_site"]),
        "converged": converged,
        "claim_level": "finite_cell_ground_state",
        "convergence": {
            "variance": _num(diag["variance"]),
            "delta_e_last_sweep": _num(diag["delta_e_last_sweep"]),
            "truncation_discard": _num(diag["truncation_discard"]),
            "criteria": diag["criteria"],
            "sweep_energies": [_num(v) for v in diag["sweep_energies"]],
            "sweep_maxlinkdim": [int(v) for v in diag["sweep_maxlinkdim"]],
            "final_maxlinkdim": int(diag["sweep_maxlinkdim"][-1]),
        },
        "parameters": spec["parameters"],
        "observables": observables,
        "limitations": [
            "Finite periodic cluster; claim_level is finite_cell_ground_state — "
            "no thermodynamic-limit extrapolation is performed or implied.",
            "2D support is strip geometry only (snake MPS ordering); wider "
            "strips need larger dmrg_maxdim budgets.",
            "Variational DMRG energy is an upper bound when not converged; "
            "trust only converged=true results.",
        ],
    }
