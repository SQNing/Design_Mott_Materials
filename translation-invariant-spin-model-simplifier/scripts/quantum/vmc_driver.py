"""netket VMC backend driver — stage E.

Mirrors the DMRG/Sunny driver contract: probe the dedicated interpreter
(``.venv-netket``), fail closed with ``backend-not-connected`` when netket
cannot be reached, never fall back silently. The heavy lifting lives in
``run_vmc_netket.py``; this module compiles the opsum payload (shared with
the DMRG route), manages the subprocess, and maps the result onto the
solver response conventions.

Under-optimization is an alarm, not a detail: when the final energy variance
exceeds the tolerance the response is ``inconclusive`` with an explicit
blocker. Optional cross-validation against exact diagonalization
(``crosscheck: true``) reports ``cross_method_inconsistent`` on disagreement
beyond 3 sigma of the Monte Carlo error bar.

Task entry: ``solve_quantum_vmc(system, request)`` (workflow dispatch).
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from quantum.ed_solver import solve_quantum_low_energy
from quantum.mpo_compiler import compile_opsum

_SCRIPT_DIR = Path(__file__).resolve().parent
_VMC_SCRIPT = _SCRIPT_DIR / "run_vmc_netket.py"
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]
_VENV = _PROJECT_ROOT / ".venv-netket"
_VENV_PYTHON = _VENV / "bin" / "python"

_CONTRACT = "vmc_ground_state/v1"

# Cross-validation is exact only up to this size (dense ED).
_CROSSCHECK_MAX_SITES = 20

_NETKET_VERSION_CACHE = None


def _not_connected(detail):
    return {
        "status": "backend-not-connected",
        "backend": {"name": "netket", "mode": "VMC"},
        "blocker": detail,
        "limitations": ["VMC backend requires the .venv-netket interpreter "
                        "with netket installed; no silent fallback to another "
                        "backend."],
    }


def _probe_netket():
    """(python_path, available, detail). Version probe is cached per process."""
    global _NETKET_VERSION_CACHE
    if not _VENV_PYTHON.is_file():
        return (None, False, "netket venv missing: %s (create with "
                "`python3.11 -m venv %s && %s -m pip install netket`)"
                % (_VENV, _VENV, _VENV_PYTHON))
    if _NETKET_VERSION_CACHE is None:
        try:
            completed = subprocess.run(
                [str(_VENV_PYTHON), "-c",
                 "import netket, jax; print(netket.__version__ + ' / jax ' "
                 "+ jax.__version__)"],
                capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return (str(_VENV_PYTHON), False, "netket import probe timed out")
        if completed.returncode != 0:
            return (str(_VENV_PYTHON), False,
                    "netket import failed: " + completed.stderr.strip()[-500:])
        _NETKET_VERSION_CACHE = completed.stdout.strip()
    return (str(_VENV_PYTHON), True, _NETKET_VERSION_CACHE)


def _crosscheck(system, spin, energy_per_site, energy_stderr, n_sites):
    """Exact-diagonalization reference comparison (small systems only)."""
    if n_sites > _CROSSCHECK_MAX_SITES:
        return None
    reference = solve_quantum_low_energy(system, {
        "spin": spin, "eigenvalue_count": 1, "observables": False,
    })
    if reference.get("status") != "ok":
        return {"consistent": None,
                "blocker": "reference ED unavailable: "
                           + str(reference.get("blocker"))}
    ref_e = float(reference["energy_per_site"])
    delta = energy_per_site - ref_e
    sigma = max(float(energy_stderr or 0.0), 1e-12)
    z_score = abs(delta) / sigma
    # Jastrow/RBM are variational: E_vmc >= E_exact must hold; a significant
    # undershoot signals a bug rather than noise.
    consistent = (z_score < 3.0) and (delta > -3.0 * sigma)
    return {
        "reference_method": "exact-diagonalization",
        "reference_energy_per_site": ref_e,
        "delta_per_site": delta,
        "z_score": z_score,
        "consistent": bool(consistent),
    }


def solve_quantum_vmc(system, request):
    """Variational ground state (Jastrow default, RBM optional)."""
    spin = float(request["spin"])
    python_path, netket_ok, detail = _probe_netket()
    if not netket_ok:
        return _not_connected(detail)

    try:
        spec = compile_opsum(system, spin, request)
    except ValueError as exc:
        return {"status": "invalid_request", "task": "quantum_vmc_ground_state",
                "blocker": str(exc)}
    n = spec["site_count"]
    ansatz = str(request.get("ansatz", "rbm"))
    spec["parameters"] = {
        "ansatz": ansatz,
        "rbm_alpha": int(request.get("rbm_alpha", 2)),
        "sampler": str(request.get("vmc_sampler", "auto")),
        "exact_threshold": int(request.get("vmc_exact_threshold", 20000)),
        "n_iter": int(request.get("vmc_n_iter", 300)),
        "n_samples": int(request.get("vmc_n_samples", 2048)),
        "final_samples": int(request.get("vmc_final_samples", 8192)),
        "n_chains": int(request.get("vmc_n_chains", 16)),
        "learning_rate": float(request.get("vmc_learning_rate", 0.02)),
        "sr_diag_shift": float(request.get("vmc_sr_diag_shift", 0.01)),
        # Per-site variance budget: a converged RBM/Jastrow optimum reaches
        # ~1e-4..1e-3 per site; anything larger is under-optimized.
        "variance_tol": float(request.get("vmc_variance_tol", 1e-3)) * n,
        "seed": int(request.get("seed", 0)),
        "observables": bool(request.get("observables", True)),
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                     delete=False) as handle:
        payload_path = Path(handle.name)
        json.dump(spec, handle)
    timeout = float(request.get("vmc_timeout_seconds", 3600))
    try:
        completed = subprocess.run([python_path, str(_VMC_SCRIPT),
                                    str(payload_path)],
                                   capture_output=True, text=True,
                                   timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "inconclusive",
                "backend": {"name": "netket", "mode": "VMC"},
                "blocker": "vmc subprocess exceeded timeout_seconds=%g" % timeout}
    finally:
        payload_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        return {"status": "error",
                "backend": {"name": "netket", "mode": "VMC"},
                "error": {"code": "vmc-subprocess-failed",
                          "message": completed.stderr.strip()[-2000:]}}
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    variance = float(result["variance"])
    converged = bool(result["converged"])
    energy_per_site = float(result["energy_per_site"])
    energy_stderr = float(result.get("energy_stderr") or 0.0)

    crosscheck = None
    blocker = None
    if request.get("crosscheck", False):
        crosscheck = _crosscheck(system, spin, energy_per_site,
                                 energy_stderr, n)
        if crosscheck and crosscheck.get("consistent") is False:
            blocker = ("cross_method_inconsistent: VMC E/N=%.10f vs ED "
                       "%.10f (z=%.1f)" % (energy_per_site,
                                            crosscheck["reference_energy_per_site"],
                                            crosscheck["z_score"]))
    if not converged:
        blocker = ("under-optimized: final energy variance %.3e exceeds "
                   "variance_tol %.3e; increase vmc_n_iter or check the ansatz"
                   % (variance, spec["parameters"]["variance_tol"]))

    observables = result.get("observables")
    return {
        "status": "ok" if blocker is None else "inconclusive",
        "schema_version": _CONTRACT,
        "method": "vmc-netket-" + ansatz,
        "backend": {"name": "netket", "mode": "VMC",
                    "environment": str(_VENV), "versions": detail},
        "spin": spin,
        "supercell_shape": list(system.shape),
        "site_count": n,
        "conserve_sz": spec["conserve_sz"],
        "ansatz": ansatz,
        "n_parameters": int(result.get("n_parameters", 0)),
        "energy": float(result["energy"]),
        "energy_per_site": energy_per_site,
        "energy_stderr": energy_stderr,
        "converged": converged,
        "blocker": blocker,
        "claim_level": "variational_upper_bound",
        "convergence": {
            "variance": variance,
            "variance_tol": spec["parameters"]["variance_tol"],
            "energy_trajectory": result.get("energy_trajectory") or [],
            "criteria": {"variance": "variance < variance_tol"},
        },
        "observables": observables,
        "cross_validation": crosscheck,
        "warnings": ([] if blocker is None else [blocker]),
    }
