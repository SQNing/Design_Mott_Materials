"""Live literature benchmark wall driven by the real quantum backends (G1).

The literature registry
(:data:`validation.literature_spin_model_benchmarks.LITERATURE_STANDARD_RESULTS`)
tags entries with ``backend_needed`` labels such as ``dmrg_or_vmc`` or
``bethe_or_extrapolated_ed``.  Historically those labels were audit metadata
only.  This module binds a curated subset of entries to executable checks
that run the real DMRG (ITensor.jl) and VMC (netket) backends through the
three-dimensional workflow, so a backend regression raises an explicit alarm
instead of silently remaining a paper tag.

Design rules:

- Every binding names an existing literature entry; the entry supplies the
  literature reference value used in the report.
- Finite-size honesty: benchmarks compare against the finite-cluster
  reference (Bethe roots at N=100, dense ED at N=12); the thermodynamic
  literature value is reported alongside with the expected finite-size
  shift, never silently equated with a finite-N result.
- Gated bindings are expensive (tens of minutes) and run only when the
  benchmark wall is enabled (``SPINFORGE_BENCHMARK=1``), matching the
  existing wall style in ``scripts/quantum/tests``.
"""

from dataclasses import dataclass

import numpy as np

from three_dimensional.workflow import run_three_dimensional_workflow
from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS

_ENTRIES = {entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS}


# ---------------------------------------------------------------------------
# Model builders (lattice-term-contract/v1, P1 identity symmetry).
# ---------------------------------------------------------------------------

def _spin_bond_model(lattice_vectors, basis_positions, bonds):
    return {
        "schema_version": "lattice-term-contract/v1",
        "lattice_structure": {
            "lattice_vectors": [list(map(float, v)) for v in lattice_vectors],
            "basis_sites": [{"site_ref": "site:%d" % i, "position": list(map(float, p))}
                            for i, p in enumerate(basis_positions)]},
        "local_hilbert": {
            "operator_bases": {"operator-basis:spin": {"kind": "spin_vector",
                                                       "labels": ["Sx", "Sy", "Sz"]}},
            "classical_spaces": {"classical-space:spin": {"kind": "unit_vector_sphere",
                                                          "dimension": 3}}},
        "symmetry": {"source": {"international_symbol": "P1", "number": 1},
                     "operations": [{"operation_ref": "symop:0",
                                     "rotation": np.eye(3, dtype=int).tolist(),
                                     "translation": [0, 0, 0]}],
                     "unresolved": []},
        "parameters": {},
        "term_attachments": {"site_terms": [], "higher_body_terms": [],
                             "bond_terms": [
                                 {"term_ref": "term:b%d" % index,
                                  "cluster": [{"site": int(source), "translation": [0, 0, 0]},
                                              {"site": int(target),
                                               "translation": [int(v) for v in translation]}],
                                  "operator_basis_ref": "operator-basis:spin",
                                  "coordinate_convention": "global_crystallographic",
                                  "payload": {"kind": "bilinear_exchange_matrix",
                                              "matrix": np.asarray(matrix, dtype=float).tolist()}}
                                 for index, (source, target, translation, matrix)
                                 in enumerate(bonds)]}}


def chain_heisenberg_model(exchange=1.0):
    """1D spin-1/2 Heisenberg chain along x, P1 symmetry."""
    return _spin_bond_model(np.eye(3), [[0, 0, 0]],
                            [(0, 0, (1, 0, 0), exchange * np.eye(3))])


def triangular_heisenberg_model(exchange=1.0):
    """Triangular lattice nearest-neighbor Heisenberg model (z=6)."""
    vectors = [[1, 0, 0], [0.5, float(np.sqrt(3) / 2), 0], [0, 0, 1]]
    bonds = [(0, 0, (1, 0, 0), exchange * np.eye(3)),
             (0, 0, (0, 1, 0), exchange * np.eye(3)),
             (0, 0, (1, -1, 0), exchange * np.eye(3))]
    return _spin_bond_model(vectors, [[0, 0, 0]], bonds)


# ---------------------------------------------------------------------------
# Finite-size references.
# ---------------------------------------------------------------------------

def bethe_ground_state_energy(n_sites, exchange=1.0, iterations=2000, damping=0.5):
    """XXX chain ground-state energy from the real Bethe roots (N even).

    Equations: N * acot(2 lambda_j) = pi I_j + sum_k acot(lambda_j - lambda_k),
    I_j half-integers -(M-1)/2 .. (M-1)/2 for M = N/2 down spins.
    Energy: E = N J/4 - (J/2) sum_j 1/(lambda_j^2 + 1/4).
    Mirrors ``scripts/quantum/tests/test_ed_benchmarks.py``.
    """
    m_down = n_sites // 2
    quantum_numbers = np.arange(m_down) - (m_down - 1) / 2.0
    lam = 0.5 * np.tan(np.pi * quantum_numbers / n_sites)
    for _step in range(iterations):
        diff = lam[:, None] - lam[None, :]
        np.fill_diagonal(diff, 1.0)  # placeholder; excluded below
        pair = np.arctan(diff)  # atan(lambda_j - lambda_k)
        np.fill_diagonal(pair, 0.0)  # k == j term is excluded from the sum
        rhs = np.pi * quantum_numbers + pair.sum(axis=1)
        target = 0.5 * np.tan(rhs / n_sites)
        shift = np.max(np.abs(target - lam))
        lam = (1 - damping) * lam + damping * target
        if shift < 1e-13:
            break
    energy = n_sites * exchange / 4.0 - exchange / 2.0 * np.sum(1.0 / (lam ** 2 + 0.25))
    return float(energy)


# Dense exact diagonalization reference for the 12-site (4x3) triangular
# Heisenberg cluster, computed with
# ``scripts/quantum/tests/helpers.py::heisenberg_dense_reference`` on
# 2026-11-23 (E0/N = -0.5775676969063245).
TRIANGULAR_N12_ED_ENERGY = -6.930812362875893
TRIANGULAR_N12_SHAPE = [4, 3, 1]


# ---------------------------------------------------------------------------
# Live bindings.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiveWallRow:
    name: str
    backend: str
    status: str            # pass | fail | skipped-gated | backend-not-connected | registry-missing
    measured: object
    reference: object
    tolerance: object
    literature_value: object
    detail: str


def _failure(name, backend, detail):
    return LiveWallRow(name=name, backend=backend, status="fail",
                       measured=None, reference=None, tolerance=None,
                       literature_value=None, detail=detail)


def _check_dmrg_xxx_chain_bethe(entry, runner):
    """DMRG N=100 XXX chain vs finite-N Bethe roots (rel < 1e-6)."""
    n_sites = 100
    result = runner(chain_heisenberg_model(1.0), {
        "task": "quantum_ground_state_dmrg",
        "supercell_shape": [n_sites, 1, 1], "spin": 0.5,
        "dmrg_sweeps": 14, "dmrg_maxdim": 500, "dmrg_noise": 0.0,
        "dmrg_cutoff": 1e-14, "observables": False,
        "dmrg_timeout_seconds": 7200})
    if result.get("status") == "backend-not-connected":
        return LiveWallRow(entry["name"], "dmrg", "backend-not-connected",
                           None, None, None,
                           entry["standard_result"]["energy_per_site"],
                           str(result.get("blocker") or "ITensor.jl backend not connected"))
    calc = result.get("calculation", {})
    if result.get("status") != "ok" or calc.get("converged") is not True:
        return _failure(entry["name"], "dmrg",
                        "DMRG did not certify convergence: status=%s blocker=%s"
                        % (result.get("status"), result.get("blocker") or calc.get("blocker")))
    measured = float(calc["energy"])
    reference = bethe_ground_state_energy(n_sites)
    rel = abs(measured - reference) / abs(reference)
    literature = float(entry["standard_result"]["energy_per_site"])
    finite_shift = abs(reference / n_sites - literature) / abs(literature)
    status = "pass" if rel < 1e-6 else "fail"
    return LiveWallRow(
        entry["name"], "dmrg", status, measured, reference, "relative<1e-6",
        literature,
        "relative deviation vs finite-N Bethe %.3e; finite-size shift vs "
        "thermodynamic literature %.3e (expected ~2e-4 at N=100)" % (rel, finite_shift))


def _check_vmc_triangular_energy(entry, runner):
    """VMC (netket RBM) 12-site triangular cluster vs dense ED (rel < 2e-2).

    The frustrated triangular cluster converges slowly with a complex RBM;
    the binding therefore runs 4000 SR iterations with a documented per-site
    variance budget of 5e-2 (achieved: variance ~0.3-0.6 total, energy within
    ~1% of ED on studio2).  The thermodynamic literature value (-0.545) is
    reported for context with the finite-size shift (~6e-2 at N=12) made
    explicit.
    """
    result = runner(triangular_heisenberg_model(1.0), {
        "task": "quantum_ground_state_vmc",
        "supercell_shape": TRIANGULAR_N12_SHAPE, "spin": 0.5,
        "vmc_n_iter": 4000, "vmc_variance_tol": 5e-2,
        "observables": False,
        "vmc_timeout_seconds": 3600})
    if result.get("status") == "backend-not-connected":
        return LiveWallRow(entry["name"], "vmc", "backend-not-connected",
                           None, None, None,
                           entry["standard_result"]["energy_per_site_approx"],
                           str(result.get("blocker") or "netket backend not connected"))
    calc = result.get("calculation", {})
    if result.get("status") != "ok":
        return _failure(entry["name"], "vmc",
                        "VMC run not ok: status=%s blocker=%s"
                        % (result.get("status"), result.get("blocker") or calc.get("blocker")))
    measured = float(calc["energy"])
    reference = TRIANGULAR_N12_ED_ENERGY
    rel = abs(measured - reference) / abs(reference)
    if measured < reference - 1e-8 * abs(reference):
        return _failure(entry["name"], "vmc",
                        "variational principle violated: VMC energy %.10f below ED "
                        "reference %.10f" % (measured, reference))
    literature = float(entry["standard_result"]["energy_per_site_approx"])
    finite_shift = abs(reference / 12.0 - literature) / abs(literature)
    status = "pass" if rel < 2e-2 else "fail"
    return LiveWallRow(
        entry["name"], "vmc", status, measured, reference, "relative<2e-2",
        literature,
        "relative deviation vs finite-cluster ED %.3e; finite-size shift vs "
        "thermodynamic literature %.3e at N=12" % (rel, finite_shift))


@dataclass(frozen=True)
class LiveBinding:
    name: str
    backend: str
    check: object
    gated: bool = True


LIVE_WALL_BINDINGS = (
    LiveBinding("xxx_spin_half_chain_bethe_ground_state", "dmrg",
                _check_dmrg_xxx_chain_bethe),
    LiveBinding("triangular_heisenberg_spin_half_energy_reference", "vmc",
                _check_vmc_triangular_energy),
)


def evaluate_live_wall(*, include_gated=False, runner=run_three_dimensional_workflow):
    """Run the live wall; returns rows plus an aggregate status and alarms."""
    rows = []
    alarms = []
    for binding in LIVE_WALL_BINDINGS:
        entry = _ENTRIES.get(binding.name)
        if entry is None:
            row = LiveWallRow(binding.name, binding.backend, "registry-missing",
                              None, None, None, None,
                              "literature registry entry renamed or removed")
        elif binding.gated and not include_gated:
            row = LiveWallRow(binding.name, binding.backend, "skipped-gated",
                              None, None, None,
                              (entry.get("standard_result") or {}).get("energy_per_site"),
                              "benchmark wall disabled; run with SPINFORGE_BENCHMARK=1")
        else:
            row = binding.check(entry, runner)
        rows.append(row)
        if row.status in {"fail", "registry-missing"}:
            alarms.append("live literature wall alarm [%s/%s]: %s"
                          % (row.name, row.backend, row.detail))
    status = "fail" if alarms else "pass"
    return {
        "status": status,
        "rows": [row.__dict__ for row in rows],
        "alarms": alarms,
    }
