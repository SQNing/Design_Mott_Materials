"""Finite-temperature quantum thermodynamics: FTLM and TPQ.

Two independent stochastic estimators that must agree within error bars:

- FTLM (Jaklic-Prelovsek): per Sz sector, Lanczos from random start vectors
  gives Ritz values theta_n with weights w_n = |<n|r>|^2. Per-realization
  numerator/denominator pairs are combined as ratios of means.
- TPQ (Sugiura-Shimizu): the canonical thermal pure state e^{-beta H/2}|r>,
  Taylor-propagated in beta slices with exact beta labels; expectations are
  read off the normalized state at every slice boundary.

Absolute free energies are obtained by INTEGRATING the well-conditioned
energy ratio estimator: ln Z_s(beta) = ln(dim_s) - int_0^beta E_s(beta') dbeta'.
This anchors every sector partition function exactly at beta = 0 and avoids
the O(1) ground-state-overlap fluctuation of raw typicality Z estimates.
Sector partition functions then combine exactly: Z = sum_s Z_s, so
magnetization in a field h (Zeeman term -h sum Sz) and the uniform
susceptibility follow from sector weights. Error bars are bootstrap
resamples over the random-state realizations (thermodynamics/v1).
"""

import math
import numpy as np
import scipy.linalg

from quantum.ed_sectors import spin_digit_data
from quantum.ed_solver import _assemble_sector, _grouped_bonds, _check_u1_conservation

_CONTRACT = "thermodynamics/v1"
_DEFAULT_STEPS = 150
_DEFAULT_SAMPLES = 10
_BOOTSTRAP = 200


# ---------------------------------------------------------------------------
# Lanczos core

def _lanczos(hamiltonian, v0, steps, keep_basis=False):
    """Three-term Lanczos, no reorthogonalization (standard FTLM practice).

    Ghost Ritz pairs do not harm the low-order spectral moments used here:
    the returned tridiagonal defines an exact Gauss quadrature of the start
    vector's spectral measure. keep_basis=True additionally returns the
    Krylov basis (for diagonal-operator expectations).
    """
    dim = hamiltonian.shape[0]
    steps = min(steps, dim)
    if np.iscomplexobj(hamiltonian.data) and not np.any(hamiltonian.data.imag):
        hamiltonian = hamiltonian.real  # real symmetric storage, real arithmetic
    alphas = np.zeros(steps)
    betas = np.zeros(steps)  # betas[k] connects k -> k+1; betas[-1] unused
    q = np.array(v0, dtype=float)
    q /= np.linalg.norm(q)
    q_prev = np.zeros(dim)
    basis = np.zeros((dim, steps)) if keep_basis else None
    for k in range(steps):
        if keep_basis:
            basis[:, k] = q
        w = hamiltonian @ q
        alphas[k] = float(q @ w)
        w -= alphas[k] * q
        if k:
            w -= betas[k - 1] * q_prev
        norm = np.linalg.norm(w)
        if k + 1 < steps:
            if norm < 1e-13:
                # Invariant subspace of v0 exhausted (degenerate spectrum).
                return alphas[:k + 1], betas[:k], basis[:, :k + 1] if keep_basis else None
            betas[k] = norm
            q_prev, q = q, w / norm
    return alphas, betas[:max(steps - 1, 0)], basis


def _ritz_pairs(alphas, betas):
    """Ritz values, start-vector weights and Ritz coefficients."""
    try:
        values, vectors = scipy.linalg.eigh_tridiagonal(alphas, betas)
    except scipy.linalg.LinAlgError:
        # stemr can fail to converge on tight clusters (LAPACK info=22);
        # the Krylov dimension here is at most a few hundred, so a dense
        # tridiagonal solve is a cheap, unconditional fallback.
        tri = np.diag(alphas)
        if len(betas):
            tri += np.diag(betas, 1) + np.diag(betas, -1)
        values, vectors = np.linalg.eigh(tri)
    weights = vectors[0, :] ** 2
    order = np.argsort(values)
    return values[order], weights[order], vectors[:, order]


# ---------------------------------------------------------------------------
# Per-realization estimators (numerator/denominator pairs)

def _ftlm_realization(hamiltonian, steps, rng, observable_diag=None):
    """One FTLM realization.

    Returns (theta, weights, obs) with obs_n = <n|O|n> when a diagonal
    observable is requested.
    """
    dim = hamiltonian.shape[0]
    v0 = rng.normal(size=dim)
    keep = observable_diag is not None
    alphas, betas, basis = _lanczos(hamiltonian, v0, steps, keep_basis=keep)
    values, weights, coefficients = _ritz_pairs(alphas, betas)
    obs = None
    if keep:
        ritz_vectors = basis @ coefficients
        obs = (ritz_vectors ** 2).T @ observable_diag
    return values, weights, obs


def _gershgorin_bound(hamiltonian):
    """Rigorous upper bound on lambda_max(H) for the TPQ shift."""
    abs_h = abs(hamiltonian).tocsr()
    row_sums = np.asarray(abs_h.sum(axis=1)).ravel()
    return float(row_sums.max(initial=0.0))


def _smooth_interp(x_new, x, y):
    """Shape-preserving cubic interpolation with linear fallback at edges."""
    if len(x) < 4:
        return np.interp(x_new, x, y)
    from scipy.interpolate import PchipInterpolator
    return PchipInterpolator(x, y, extrapolate=False)(x_new)


def _tpq_realization(hamiltonian, shift, beta_max, rng, observable_diag=None,
                     slice_beta=0.5, tolerance=1e-13, max_slice_terms=256):
    """One canonical-TPQ realization: e^{-beta H/2}|r> by Taylor propagation.

    Sugiura-Shimizu define the TPQ state at inverse temperature beta as
    e^{-beta H/2}|random>/norm. Propagating in beta slices of width
    ``slice_beta`` (renormalizing between slices, exact beta labels) keeps the
    Taylor partial sums machine-precision accurate; each slice converges
    after ~e*beta_slice*shift/2 terms. Returns (betas, <H>, <H^2>, <O>) at
    every slice boundary.
    """
    if np.iscomplexobj(hamiltonian.data) and not np.any(hamiltonian.data.imag):
        hamiltonian = hamiltonian.real
    dim = hamiltonian.shape[0]
    v = rng.normal(size=dim)
    v /= np.linalg.norm(v)
    n_slices = max(1, int(math.ceil(beta_max / slice_beta)))
    dbeta = beta_max / n_slices
    betas = np.arange(n_slices + 1) * dbeta
    energies = np.zeros(n_slices + 1)
    energies2 = np.zeros(n_slices + 1)
    obs = np.zeros(n_slices + 1) if observable_diag is not None else None

    def measure(vec, k):
        hv = hamiltonian @ vec
        energies[k] = float(vec @ hv)
        energies2[k] = float(hv @ hv)
        if obs is not None:
            obs[k] = float(np.sum(observable_diag * vec ** 2))

    measure(v, 0)
    log_norms = np.zeros(n_slices + 1)
    for k in range(1, n_slices + 1):
        # psi <- e^{-dbeta H/2} psi, Taylor in the slice
        psi = v
        term = v.copy()
        for j in range(1, max_slice_terms + 1):
            term = (-dbeta / (2.0 * j)) * (hamiltonian @ term)
            psi = psi + term
            scale = np.linalg.norm(psi)
            if np.linalg.norm(term) <= tolerance * scale:
                break
        norm = np.linalg.norm(psi)
        log_norms[k] = log_norms[k - 1] + 2.0 * math.log(norm)
        v = psi / norm
        measure(v, k)
    return betas, energies, energies2, obs, log_norms


# ---------------------------------------------------------------------------
# Sector assembly

def _sz_values(site_count, spin):
    """All total-Sz quantum numbers from -S_max to +S_max (U(1) sectors)."""
    d, m, _up, _down = spin_digit_data(spin)
    max_sz = float(np.sum(np.full(site_count, m[-1])))
    count = int(round(2 * max_sz)) + 1
    return [(-max_sz + i * 1.0) for i in range(count)]


def _assemble_thermo_sectors(system, spin, request):
    """Resolve the requested Sz decomposition and assemble each sector."""
    grouped = _grouped_bonds(system)
    try:
        _check_u1_conservation(grouped)
        u1 = True
    except ValueError:
        u1 = False
    requested = request.get("sz_sectors", "all")
    max_memory_mb = float(request.get("max_memory_mb", 4096))
    chunk = int(request.get("assembly_chunk_size", 100000))
    if requested not in ("all", None):
        sectors = [float(v) for v in requested]
    elif u1:
        sectors = _sz_values(system.site_count, spin)
    else:
        sectors = [None]
    if not u1 and requested == "all":
        sectors = [None]
    if any(s is not None for s in sectors) and not u1:
        raise ValueError(
            "sz_sectors requested but the Hamiltonian does not conserve total Sz "
            "(e.g. Kitaev-type anisotropy); run without Sz decomposition")
    assembled = []
    for sz in sectors:
        hamiltonian, states, codes, sector, _order, estimated = _assemble_sector(
            system, spin, sz, None, max_memory_mb, chunk_size=chunk)
        assembled.append({"sz_total": sz, "hamiltonian": hamiltonian,
                          "states": states, "dimension": sector["dimension"],
                          "estimated_bytes": estimated})
    return assembled, u1


def _staggered_diagonal(system, spin, states, q):
    """Diagonal of |M_q^z|^2 on the computational basis of one sector."""
    from quantum.ed_observables import _site_positions
    d, m, _up, _down = spin_digit_data(spin)
    positions = np.asarray(_site_positions(system), dtype=float)
    phases = np.exp(2j * math.pi * (positions @ np.asarray(q, dtype=float)))
    m_states = m[states]  # (M, N)
    order = m_states @ phases
    return np.abs(order) ** 2


# ---------------------------------------------------------------------------
# Sector curves from realizations

def _sector_samples(sector, method, samples, steps, rng, obs_diag, fine,
                    tpq_slice_beta=0.5):
    """Per-realization numerator/denominator curves on the fine beta grid.

    Returns dict with arrays (R, B): e_num/e_den (energy), e2_num, o_num, and
    the shift c used for numerical stability. Observables are reconstructed
    as ratios of summed numerators over summed denominators, which cancels
    the typicality scale fluctuation of each realization.
    """
    ham = sector["hamiltonian"]
    n_beta = len(fine)
    e_num = np.zeros((samples, n_beta))
    e2_num = np.zeros((samples, n_beta))
    o_num = np.zeros((samples, n_beta)) if obs_diag is not None else None
    den = np.zeros((samples, n_beta))
    if method == "ftlm":
        # One sector-level energy shift (deepest realization ground estimate)
        # keeps every Boltzmann factor <= 1; reconstruction happens in _curves.
        realizations = [_ftlm_realization(ham, steps, rng, obs_diag)
                        for _ in range(samples)]
        shift_c = min(float(theta[0]) for theta, _w, _o in realizations)
        for r, (theta, w, obs) in enumerate(realizations):
            factor = np.exp(-np.outer(fine, theta - shift_c))
            den[r] = factor @ w
            e_num[r] = factor @ (w * (theta - shift_c))
            e2_num[r] = factor @ (w * (theta - shift_c) ** 2)
            if obs is not None:
                o_num[r] = factor @ (w * obs)
    else:
        shift_c = 0.0
        bound = _gershgorin_bound(ham) * 1.001 + 1e-12  # slice sizing only
        # Unnormalized ||phi(beta)||^2 = <r|e^{-beta H}|r> is kept in log
        # form so numerator and denominator can be summed BEFORE dividing
        # (ratio of sums), removing the O(1/dim) typicality bias of
        # per-realization normalized expectations.
        log_den = np.zeros((samples, n_beta))
        energies_all = np.zeros((samples, n_beta))
        energies2_all = np.zeros((samples, n_beta))
        obs_all = np.zeros((samples, n_beta)) if obs_diag is not None else None
        for r in range(samples):
            beta_k, energies, energies2, obs, log_norms = _tpq_realization(
                ham, bound, float(fine[-1]), rng, obs_diag,
                slice_beta=tpq_slice_beta)
            log_den[r] = _smooth_interp(fine, beta_k, log_norms)
            energies_all[r] = _smooth_interp(fine, beta_k, energies)
            energies2_all[r] = _smooth_interp(fine, beta_k, energies2)
            if obs is not None:
                obs_all[r] = _smooth_interp(fine, beta_k, obs)
        # Convert to shifted linear weights; numerator/denominator are summed
        # over realizations before dividing (ratio of sums), removing the
        # O(1/dim) typicality bias of per-realization normalized expectations.
        row_shift = log_den.max(axis=0)
        W = np.exp(log_den - row_shift)
        den[:] = W
        e_num[:] = energies_all * W
        e2_num[:] = energies2_all * W
        if obs is not None:
            o_num[:] = obs_all * W
    return {"e_num": e_num, "e2_num": e2_num, "o_num": o_num, "den": den,
            "shift": shift_c, "dimension": sector["dimension"],
            "sz_total": sector["sz_total"]}


def _curves(sector_samples, fine):
    """Ratio-of-sums thermodynamic curves of one sector (log domain)."""
    den = sector_samples["den"].sum(axis=0)
    safe = np.maximum(den, 1e-300)
    c = sector_samples["shift"]
    E_shifted = sector_samples["e_num"].sum(axis=0) / safe
    E = c + E_shifted
    E2 = (sector_samples["e2_num"].sum(axis=0) / safe
          + 2.0 * c * E_shifted + c ** 2)
    out = {"E": E, "E2": E2}
    if sector_samples["o_num"] is not None:
        out["O"] = sector_samples["o_num"].sum(axis=0) / safe
    # ln Z anchored exactly at beta = 0 (Z(0) = dim), via trapezoid integral.
    ln_z = np.zeros(len(fine))
    if len(fine) > 1:
        ln_z[1:] = np.cumsum(0.5 * (E[1:] + E[:-1]) * np.diff(fine))
    out["lnZ"] = math.log(sector_samples["dimension"]) - ln_z
    return out


def _combine(sector_curves, fine):
    """Combine sector curves into full-cluster thermodynamics."""
    ln_max = max(float(np.max(c["lnZ"])) for c in sector_curves)
    W = np.array([np.exp(c["lnZ"] - ln_max) for c in sector_curves])  # (S, B)
    Zref = W.sum(axis=0)
    E = (W * np.array([c["E"] for c in sector_curves])).sum(axis=0) / Zref
    E2 = (W * np.array([c["E2"] for c in sector_curves])).sum(axis=0) / Zref
    out = {"lnZ": np.log(Zref) + ln_max, "E": E, "E2": E2,
           "weights": W / Zref}
    if any("O" in c for c in sector_curves):
        O = np.array([c.get("O", np.zeros(len(fine))) for c in sector_curves])
        out["O"] = (W * O).sum(axis=0) / Zref
    return out


def _thermo_from_curves(curves, fine, site_count, sector_samples_list, u1,
                        q_stag):
    """Map combined curves to the thermodynamics/v1 quantities."""
    E = curves["E"]
    C = (curves["E2"] - E ** 2) * fine ** 2 / site_count
    S = (fine * E + curves["lnZ"]) / site_count
    out = {"E_site": E / site_count, "C_site": C, "S_site": S,
           "lnZ": curves["lnZ"]}
    if u1:
        sz = np.array([s["sz_total"] for s in sector_samples_list])
        mean_sz = (curves["weights"].T @ sz)
        mean_sz2 = (curves["weights"].T @ sz ** 2)
        out["chi_uniform_site"] = fine * (mean_sz2 - mean_sz ** 2) / site_count
        out["sector_sz"] = sz
    if q_stag is not None and "O" in curves:
        out["chi_staggered_zz_site"] = fine * curves["O"] / site_count
    return out


# ---------------------------------------------------------------------------
# Public solver

def solve_quantum_thermodynamics(system, request):
    """FTLM/TPQ finite-temperature thermodynamics on the finite cluster."""
    spin = float(request["spin"])
    temperatures = sorted((float(t) for t in request["temperatures"]), reverse=True)
    if not temperatures or any(t <= 0 or not math.isfinite(t) for t in temperatures):
        raise ValueError("temperatures must be positive finite values in model energy units")
    method = str(request.get("method", "ftlm")).lower()
    if method not in {"ftlm", "tpq", "both"}:
        raise ValueError("method must be ftlm, tpq or both")
    samples = int(request.get("samples", _DEFAULT_SAMPLES))
    steps = int(request.get("lanczos_steps", _DEFAULT_STEPS))
    if samples < 1 or steps < 2:
        raise ValueError("samples >= 1 and lanczos_steps >= 2 are required")
    seed = int(request.get("seed", 0))
    fields = [float(h) for h in request.get("fields", []) or []]
    q_stag = request.get("staggered_momentum")
    if q_stag is not None and len(q_stag) != 3:
        raise ValueError("staggered_momentum must be a 3-vector in primitive reciprocal units")

    sectors, u1 = _assemble_thermo_sectors(system, spin, request)
    if fields and not u1:
        raise ValueError("M(T,H) requires total-Sz conservation")

    site_count = system.site_count
    betas = 1.0 / np.asarray(temperatures)
    beta_max = float(betas.max())
    fine = np.unique(np.concatenate([
        np.linspace(0.0, beta_max, max(128, 16 * len(betas))), betas]))
    fine.sort()

    rng = np.random.default_rng(seed)
    obs_diags = None
    if q_stag is not None:
        obs_diags = {id(s): _staggered_diagonal(system, spin, s["states"], q_stag)
                     for s in sectors}

    methods = ("ftlm", "tpq") if method == "both" else (method,)
    slice_beta = float(request.get("tpq_slice_beta", 0.5))
    per_method = {}
    for label in methods:
        sector_samples = [
            _sector_samples(sector, label, samples, steps, rng,
                            None if obs_diags is None else obs_diags[id(sector)],
                            fine, tpq_slice_beta=slice_beta)
            for sector in sectors]
        per_method[label] = sector_samples

    def evaluate(sector_samples_list):
        curves = [_curves(s, fine) for s in sector_samples_list]
        combined = _combine(curves, fine)
        return _thermo_from_curves(combined, fine, site_count,
                                   sector_samples_list, u1, q_stag)

    results = {label: evaluate(per_method[label]) for label in methods}

    consistency = None  # filled after bootstrap errors are available

    primary_label = "ftlm" if "ftlm" in results else "tpq"
    primary = results[primary_label]
    primary_samples = per_method[primary_label]

    def bootstrap(fn, label=None):
        if samples < 2:
            return None
        source = per_method[label] if label else primary_samples
        n_boot = int(request.get("bootstrap_samples", _BOOTSTRAP))
        brng = np.random.default_rng(seed + 7919)
        estimates = []
        for _ in range(n_boot):
            resampled = []
            for s in source:
                r = s["den"].shape[0]
                idx = brng.integers(0, r, size=r)
                resampled.append({**s, "e_num": s["e_num"][idx],
                                  "e2_num": s["e2_num"][idx],
                                  "den": s["den"][idx],
                                  "o_num": None if s["o_num"] is None else s["o_num"][idx]})
            estimates.append(fn(evaluate(resampled)))
        return np.std(np.asarray(estimates), axis=0, ddof=1)

    e_err = bootstrap(lambda t: t["E_site"])
    c_err = bootstrap(lambda t: t["C_site"])
    chi_err = bootstrap(lambda t: t["chi_uniform_site"]) if u1 else None

    if method == "both":
        # Principled agreement test: |delta| / sqrt(sigma_a^2 + sigma_b^2)
        # per grid point; consistent when every point lies within z_max.
        a, b = results["ftlm"], results["tpq"]
        e_err_b = bootstrap(lambda t: t["E_site"], label="tpq")
        c_err_b = bootstrap(lambda t: t["C_site"], label="tpq")
        z_limit = float(request.get("consistency_z", 3.0))

        def z_scores(da, db, sa, sb):
            if sa is None or sb is None:
                return None
            return np.abs(da - db) / np.maximum(np.sqrt(sa ** 2 + sb ** 2), 1e-300)

        z_e = z_scores(a["E_site"], b["E_site"], e_err, e_err_b)
        z_c = z_scores(a["C_site"], b["C_site"], c_err, c_err_b)
        max_abs_e = float(np.max(np.abs(a["E_site"] - b["E_site"])))
        max_abs_c = float(np.max(np.abs(a["C_site"] - b["C_site"])))
        consistency = {
            "max_abs_deviation_energy_per_site": max_abs_e,
            "max_abs_deviation_heat_capacity_per_site": max_abs_c,
            "max_z_energy": None if z_e is None else float(np.max(z_e)),
            "max_z_heat_capacity": None if z_c is None else float(np.max(z_c)),
            "z_limit": z_limit,
            "consistent": (bool(np.max(z_e) <= z_limit and np.max(z_c) <= z_limit)
                           if z_e is not None and z_c is not None else None)}

    idx = [int(np.argmin(np.abs(fine - b))) for b in betas]
    grid = []
    for t, i in zip(temperatures, idx):
        entry = {
            "temperature": t, "beta": float(fine[i]),
            "energy_per_site": {"value": float(primary["E_site"][i]),
                                "stderr": None if e_err is None else float(e_err[i])},
            "heat_capacity_per_site": {"value": float(primary["C_site"][i]),
                                       "stderr": None if c_err is None else float(c_err[i])},
            "entropy_per_site": {"value": float(primary["S_site"][i]), "stderr": None},
        }
        if u1:
            entry["uniform_susceptibility_per_site"] = {
                "value": float(primary["chi_uniform_site"][i]),
                "stderr": None if chi_err is None else float(chi_err[i])}
        if q_stag is not None and "chi_staggered_zz_site" in primary:
            entry["staggered_susceptibility_zz_per_site"] = {
                "value": float(primary["chi_staggered_zz_site"][i]), "stderr": None}
        grid.append(entry)

    field_scans = []
    if fields and u1:
        sz = primary["sector_sz"]
        curves = [_curves(s, fine) for s in primary_samples]
        ln_max = max(float(np.max(c["lnZ"])) for c in curves)
        lnZ = np.array([c["lnZ"] for c in curves])  # (S, B)
        for t, i in zip(temperatures, idx):
            beta = fine[i]
            log_w = lnZ[:, i] - ln_max
            mags = []
            for h in fields:
                w = np.exp(log_w + beta * h * sz)
                mags.append(float(np.sum(sz * w) / np.sum(w) / site_count))
            field_scans.append({"temperature": t, "fields": fields,
                                "magnetization_per_site": mags})

    return {
        "status": "ok",
        "schema_version": _CONTRACT,
        "method": "+".join(sorted(results)),
        "source": "+".join(sorted(results)),
        "spin": spin, "supercell_shape": list(system.shape),
        "site_count": site_count,
        "sz_decomposition": u1,
        "sectors": [{"sz_total": s["sz_total"], "dimension": s["dimension"],
                     "estimated_bytes": s["estimated_bytes"]} for s in sectors],
        "grid": grid,
        "field_scans": field_scans,
        "consistency": consistency,
        "sampling": {"random_state_samples": samples, "lanczos_steps": steps,
                     "seed": seed,
                     "bootstrap_samples": int(request.get("bootstrap_samples", _BOOTSTRAP)),
                     "methods": sorted(results),
                     "tpq_slice_beta": slice_beta
                                      if "tpq" in results else None},
        "definitions": {
            "energy_per_site": "<H>/N from sector-combined partition function",
            "heat_capacity_per_site": "beta^2 (<H^2>-<H>^2)/N, k_B=1",
            "entropy_per_site": "(beta<E> + ln Z)/N, ln Z anchored at ln(dim) for beta=0",
            "uniform_susceptibility_per_site": "beta/N Var(Sz_total) at zero field",
            "staggered_susceptibility_zz_per_site": "beta/N <|M_q^z|^2>, zz component only",
            "magnetization_per_site": "<Sz_total>/N in field h (Zeeman -h sum Sz)"},
        "limitations": [
            "Finite periodic cluster; no thermodynamic-limit claim. T -> 0 "
            "results reflect the finite-size gap.",
            "Stochastic estimators: error bars cover random-state sampling "
            "only, not Lanczos truncation.",
            "Sector free energies come from integrating the energy ratio "
            "estimator (anchored exactly at beta=0).",
            "Canonical TPQ states e^{-beta H/2}|r> are Taylor-propagated in beta "
            "slices with exact beta labels, then interpolated to the requested grid."],
    }
