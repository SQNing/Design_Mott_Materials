"""Numerical finite-cell evidence and locally feasible Fourier initial states."""
import math
import numpy as np

from classical.lt_fourier_exchange import fourier_exchange_matrix


def evidence_settings(request):
    values = {}
    for name in ("ground_state_absolute_tolerance", "ground_state_relative_tolerance"):
        value = request.get(name, 1e-9)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(name + " must be finite and nonnegative")
        values[name] = float(value)
    enabled = request.get("fourier_seed_recovery", True)
    if not isinstance(enabled, bool):
        raise ValueError("fourier_seed_recovery must be a boolean")
    return values, enabled


def ground_state_evidence(system, spin_length, energy, residual, bound, settings, stationarity_tolerance):
    gap = float(energy - bound)
    resolution = (settings["ground_state_absolute_tolerance"] +
                  settings["ground_state_relative_tolerance"] * max(abs(energy), abs(bound)))
    stationary = math.isfinite(residual) and residual <= stationarity_tolerance
    if not np.all(np.isfinite([energy, bound, gap, residual])) or gap < -resolution:
        status = "inconsistent_bound"
    elif stationary and gap <= resolution:
        status = "bound_saturated"
    else:
        status = "not_certified"
    return {"stationary": stationary, "finite_cell_status": status,
        "finite_cell_lower_bound_per_cell": float(bound), "energy_gap_per_cell": gap,
        "comparison_tolerance_per_cell": resolution, **settings,
        "supercell_shape": list(system.shape), "spin_length": spin_length,
        "infinite_lattice_status": "not_certified",
        "interpretation": ("A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution."
            if status == "bound_saturated" else
            "Energy is inconsistent with the numerical lower bound; this result cannot support physical claims."
            if status == "inconsistent_bound" else
            "A positive LT gap is lack of certification, not proof of a wrong state: the relaxed bound can be unattainable."),
        "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof."}


def feasible_fourier_seed(system, q, spin_length, bound, resolution, stationarity_tolerance):
    """Only accept a lowest-mode construction that obeys every local constraint.

    The kernel uses exp(-i q.R); the real-space reconstruction uses the same
    phase. Isotropic exchange permits an orthogonal cosine/sine spin plane.
    General tensors are tested using real combinations of their actual modes.
    Failure to find a feasible single-q mode is not a ground-state verdict.
    """
    payload = {"lattice": {"sublattices": system.basis_count}, "bonds": system.payload["bonds"]}
    matrix = fourier_exchange_matrix(payload, q)
    phase = np.exp(-2j*np.pi*system.cells @ np.asarray(q))
    eigen_resolution = max(1e-12*max(1., np.linalg.norm(matrix, ord=2)),
                           2*resolution/(system.basis_count*spin_length**2))

    def accept(raw, construction):
        vectors = np.asarray(raw, dtype=float).reshape((system.site_count, 3))
        norms = np.linalg.norm(vectors, axis=1)
        scale = float(np.max(norms))
        if not np.all(np.isfinite(norms)) or scale == 0 or np.min(norms) <= scale*1e-12:
            return None
        # Do not turn an unequal-amplitude LT mode into a claimed certificate
        # by projecting each site separately onto its sphere.
        if np.ptp(norms) > 1e-10*scale:
            return None
        spins = vectors * (spin_length / float(np.mean(norms)))
        energy, gradient = system.energy_gradient(spins)
        directions = spins/spin_length
        tangent = gradient-directions*np.sum(gradient*directions, axis=1, keepdims=True)
        gap = float(energy/system.cell_count-bound)
        residual = float(np.max(np.linalg.norm(tangent, axis=1)))
        if abs(gap) > resolution or residual > stationarity_tolerance:
            return None
        return {"spins": spins, "construction": construction, "q": list(q),
            "energy_gap_per_cell": gap, "stationarity_max_norm": residual,
            "local_length_max_error": float(np.max(np.abs(np.linalg.norm(spins, axis=1)-spin_length)))}

    isotropic = True
    for bond in system.payload["bonds"]:
        coupling = np.asarray(bond["matrix"], dtype=float)
        scale = float(np.max(np.abs(coupling)))
        if scale and np.max(np.abs(coupling-np.trace(coupling)/3*np.eye(3))) > 1e-12*scale:
            isotropic = False
            break
    if isotropic:
        values, vectors = np.linalg.eigh(matrix[::3, ::3])
        for index in np.flatnonzero(values <= values[0]+eigen_resolution):
            amplitudes = phase[:, None]*vectors[None, :, index]
            raw = np.stack([amplitudes.real, amplitudes.imag, np.zeros_like(amplitudes.real)], axis=-1)
            seed = accept(raw, "isotropic_cosine_sine_plane")
            if seed is not None:
                return seed
    values, vectors = np.linalg.eigh(matrix)
    for index in np.flatnonzero(values <= values[0]+eigen_resolution):
        mode = vectors[:, index].reshape((system.basis_count, 3))
        for angle in (0., np.pi/2, np.pi/4):
            raw = np.real(np.exp(1j*angle)*phase[:, None, None]*mode[None, ...])
            seed = accept(raw, "full_tensor_real_fourier_mode")
            if seed is not None:
                return seed
    return None
