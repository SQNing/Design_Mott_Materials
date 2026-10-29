"""Finite periodic realization of the existing validated spin-bond payload."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from classical.lt_fourier_exchange import fourier_exchange_matrix
from classical.classical_solver_driver import _refine_spin_supercell_state


def supercell_shape(values):
    shape = tuple(int(value) for value in values)
    if len(shape) != 3 or any(value < 1 for value in shape) or list(shape) != list(values):
        raise ValueError("supercell_shape must contain three positive integers")
    return shape


class PeriodicSpinSystem:
    """Each input bond contributes once per primitive cell, including images.

    Energy is extensive. Distinct periodic images are not deduplicated when a
    small supercell makes their endpoints coincide.
    """

    def __init__(self, payload, shape):
        self.payload = payload
        self.shape = supercell_shape(shape)
        self.basis_count = len(payload["lattice_structure"]["basis_sites"])
        self.cell_count = int(np.prod(self.shape))
        self.site_count = self.cell_count * self.basis_count
        self.cells = np.array(list(np.ndindex(self.shape)), dtype=int)
        source, target, matrices = [], [], []
        for cell_index, cell in enumerate(self.cells):
            for bond in payload["bonds"]:
                matrix = np.asarray(bond["matrix"], dtype=float)
                if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
                    raise ValueError("exchange tensors must be finite real 3 by 3 matrices")
                delta = np.asarray(bond["vector"], dtype=int)
                target_cell = tuple((cell + delta) % np.array(self.shape))
                source.append(cell_index * self.basis_count + int(bond["source"]))
                target.append(np.ravel_multi_index(target_cell, self.shape) * self.basis_count
                              + int(bond["target"]))
                matrices.append(matrix)
        self.source = np.asarray(source, dtype=int)
        self.target = np.asarray(target, dtype=int)
        self.matrices = np.asarray(matrices, dtype=float).reshape((-1, 3, 3))

    def energy_gradient(self, spins):
        spins = np.asarray(spins, dtype=float).reshape((self.site_count, 3))
        left, right = spins[self.source], spins[self.target]
        right_field = np.einsum("bij,bj->bi", self.matrices, right)
        left_field = np.einsum("bji,bj->bi", self.matrices, left)
        energy = float(np.einsum("bi,bi->", left, right_field))
        gradient = np.zeros_like(spins)
        np.add.at(gradient, self.source, right_field)
        np.add.at(gradient, self.target, left_field)
        return energy, gradient

    def finite_cell_lower_bound(self, spin_length):
        kernel_payload = {"lattice": {"sublattices": self.basis_count},
                          "bonds": self.payload["bonds"]}
        sectors = []
        for indices in np.ndindex(self.shape):
            q = np.array(indices) / np.array(self.shape)
            eigenvalue = float(np.linalg.eigvalsh(fourier_exchange_matrix(kernel_payload, q))[0])
            sectors.append((eigenvalue, q.tolist()))
        lowest, q = min(sectors, key=lambda entry: entry[0])
        return 0.5 * self.basis_count * spin_length ** 2 * lowest, q


def minimize_fixed_length(system, request):
    spin_length = float(request["spin_length"])
    starts = int(request.get("starts", 8))
    tolerance = float(request.get("stationarity_tolerance", 1e-6))
    if not np.isfinite(spin_length) or spin_length <= 0 or starts < 1:
        raise ValueError("positive spin_length and starts are required")
    rng = np.random.default_rng(int(request.get("seed", 0)))

    def objective(raw):
        vectors = raw.reshape((system.site_count, 3))
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        directions = vectors / np.maximum(norms, 1e-15)
        energy, gradient = system.energy_gradient(spin_length * directions)
        tangent = gradient - directions * np.sum(directions * gradient, axis=1, keepdims=True)
        derivative = spin_length * tangent / np.maximum(norms, 1e-15)
        return energy, derivative.ravel()

    results = []
    best = None
    for index in range(starts):
        if index == 0 and request.get("initial_spins") is not None:
            raw = np.array(request["initial_spins"], dtype=float).reshape((system.site_count, 3))
        else:
            raw = rng.normal(size=(system.site_count, 3))
        if np.any(np.linalg.norm(raw, axis=1) < 1e-14):
            raise ValueError("initial_spins must have nonzero length")
        raw /= np.linalg.norm(raw, axis=1, keepdims=True)
        optimized = minimize(objective, raw.ravel(), jac=True, method="L-BFGS-B",
                             options={"maxiter": int(request.get("maxiter", 1500)),
                                      "ftol": 1e-15, "gtol": tolerance * 0.01})
        vectors = optimized.x.reshape((system.site_count, 3))
        directions = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        # L-BFGS can stop on roundoff in the total energy before a requested
        # tight tangent-gradient tolerance is reached. For distinct endpoints,
        # the existing exact single-site field sweep monotonically lowers this
        # bilinear energy and polishes its stationary point. Do not apply that
        # linear-field update to self-image quadratic terms.
        polished = False
        if not np.any(system.source == system.target):
            refined, _change, _residual = _refine_spin_supercell_state(
                system.payload, directions.reshape(system.shape + (system.basis_count, 3)),
                system.shape, max_sweeps=100, sweep_tolerance=1e-12,
                gradient_tolerance=tolerance / (4 * spin_length))
            directions = refined.reshape((system.site_count, 3))
            polished = True
        spins = spin_length * directions
        energy, gradient = system.energy_gradient(spins)
        tangent = gradient - directions * np.sum(gradient * directions, axis=1, keepdims=True)
        residual = float(np.max(np.linalg.norm(tangent, axis=1)))
        results.append({"energy_per_cell": energy / system.cell_count,
                        "stationarity_max_norm": residual,
                        "optimizer_success": bool(optimized.success),
                        "local_field_polishing": polished,
                        "iterations": int(optimized.nit)})
        if best is None or energy < best[0]:
            best = energy, spins, residual
    energy, spins, residual = best
    bound, q = system.finite_cell_lower_bound(spin_length)
    return {
        "status": "ok" if residual <= tolerance else "inconclusive",
        "method": "fixed-length-real-space-L-BFGS-B",
        "supercell_shape": list(system.shape), "boundary": "periodic",
        "spin_length": spin_length, "spins": spins.tolist(),
        "energy_total": energy, "energy_per_cell": energy / system.cell_count,
        "stationarity_max_norm": residual, "stationarity_tolerance": tolerance,
        "finite_cell_lt_lower_bound_per_cell": bound,
        "finite_cell_lt_minimum_q": q,
        "finite_cell_bound_gap": energy / system.cell_count - bound,
        "infinite_lattice_certified": False,
        "starts": results, "seed": int(request.get("seed", 0)),
        "limitations": ["Local minimization on the requested finite periodic supercell.",
                        "An LT bound gap near zero certifies this cell, not the infinite lattice."],
    }
