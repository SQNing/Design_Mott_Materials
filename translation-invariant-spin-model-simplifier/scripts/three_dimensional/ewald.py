"""Periodic dipole energy and dE/d(moment), with explicit macroscopic boundary.

Conventions: Wang & Holm, arXiv:cond-mat/0107064, Eqs. (2)-(8), generalized
from a cubic box to row-vector cell A using k = 2 pi n A^{-T} and V = |det A|.
The prefactor (e.g. mu_0/4pi with consistent units) is supplied by the caller.
This computes moment gradients, NOT forces on the positional coordinates.
"""

import itertools
import math
import numpy as np
from scipy.special import erfc


def _integer_vectors(bounds):
    count = math.prod(2 * int(value) + 1 for value in bounds)
    if count > 2_000_000:
        raise ValueError("Ewald vector enumeration exceeds 2000000; choose a better-conditioned cell or cutoffs")
    return np.array(list(itertools.product(*(range(-int(b), int(b) + 1) for b in bounds))), dtype=int)


def _evaluate(lattice, positions, moments, alpha, real_cutoff, reciprocal_cutoff, boundary):
    volume = abs(float(np.linalg.det(lattice)))
    count = len(moments)
    inverse = np.linalg.inv(lattice)
    translations = _integer_vectors(np.ceil(real_cutoff * np.linalg.norm(inverse, axis=0) + 1).astype(int))
    real_energy = 0.0
    gradient = np.zeros_like(moments)
    real_pairs = 0
    for i in range(count):
        for j in range(count):
            displacements = (positions[i] - positions[j] + translations) @ lattice
            radii = np.linalg.norm(displacements, axis=1)
            mask = (radii > 1e-12) & (radii <= real_cutoff)
            if i != j and np.any(radii <= 1e-12):
                raise ValueError("distinct point dipoles may not occupy the same periodic position")
            r, displacement = radii[mask], displacements[mask]
            real_pairs += len(r)
            exponential = 2 * alpha / math.sqrt(math.pi) * np.exp(-(alpha * r) ** 2)
            b = erfc(alpha * r) / r ** 3 + exponential / r ** 2
            c = 3 * erfc(alpha * r) / r ** 5 + exponential * (3 / r ** 4 + 2 * alpha ** 2 / r ** 2)
            tensor = np.sum(b) * np.eye(3) - np.einsum("n,na,nb->ab", c, displacement, displacement)
            real_energy += 0.5 * float(moments[i] @ tensor @ moments[j])
            gradient[i] += tensor @ moments[j]

    reciprocal_basis = 2 * math.pi * inverse.T
    reciprocal_bounds = np.ceil(reciprocal_cutoff * np.linalg.norm(np.linalg.inv(reciprocal_basis), axis=0)).astype(int)
    integers = _integer_vectors(reciprocal_bounds)
    wavevectors = integers @ reciprocal_basis
    norms = np.linalg.norm(wavevectors, axis=1)
    mask = (norms > 1e-12) & (norms <= reciprocal_cutoff)
    integers, wavevectors, norms = integers[mask], wavevectors[mask], norms[mask]
    phases = np.exp(2j * math.pi * (integers @ positions.T))
    projection = wavevectors @ moments.T
    structure = np.sum(projection * phases, axis=1)
    weights = (2 * math.pi / volume) * np.exp(-norms ** 2 / (4 * alpha ** 2)) / norms ** 2
    reciprocal_energy = float(np.sum(weights * np.abs(structure) ** 2))
    gradient += 2 * np.einsum("k,ki,ka->ia", weights,
                              np.real(structure.conjugate()[:, None] * phases), wavevectors)

    self_coefficient = -2 * alpha ** 3 / (3 * math.sqrt(math.pi))
    self_energy = self_coefficient * float(np.sum(moments ** 2))
    gradient += 2 * self_coefficient * moments
    surface_coefficient = 0.0 if boundary == "tin_foil" else 2 * math.pi / (3 * volume)
    total_moment = np.sum(moments, axis=0)
    surface_energy = surface_coefficient * float(total_moment @ total_moment)
    gradient += 2 * surface_coefficient * total_moment
    components = {"real": real_energy, "reciprocal": reciprocal_energy,
                  "self": self_energy, "surface": surface_energy}
    return {"energy_total": sum(components.values()), "components": components,
            "moment_gradient": gradient.tolist(), "real_pair_images": real_pairs,
            "reciprocal_vectors": len(norms)}


def dipolar_ewald(geometry, request):
    lattice = np.asarray(geometry["lattice_vectors"], dtype=float)
    positions = np.asarray(geometry["fractional_positions"], dtype=float)
    moments = np.asarray(geometry["moments"], dtype=float)
    if lattice.shape != (3, 3) or abs(float(np.linalg.det(lattice))) < 1e-12:
        raise ValueError("Ewald requires a nonsingular 3D periodic cell")
    if positions.ndim != 2 or positions.shape[1] != 3 or moments.shape != positions.shape or not len(positions):
        raise ValueError("fractional_positions and moments must be matching nonempty N by 3 arrays")
    if not all(np.all(np.isfinite(array)) for array in (lattice, positions, moments)):
        raise ValueError("Ewald geometry and moments must be finite")
    alpha, rc, kc = (float(request[key]) for key in ("alpha", "real_cutoff", "reciprocal_cutoff"))
    if any(not np.isfinite(value) or value <= 0 for value in (alpha, rc, kc)):
        raise ValueError("alpha and both cutoffs must be finite and positive")
    boundary = request["boundary"]
    if boundary not in {"tin_foil", "vacuum_sphere"}:
        raise ValueError("boundary must explicitly be tin_foil or vacuum_sphere")
    prefactor = float(request.get("prefactor", 1.0))
    if not np.isfinite(prefactor):
        raise ValueError("prefactor must be finite")
    positions = positions % 1
    result = _evaluate(lattice, positions, moments, alpha, rc, kc, boundary)
    factor = float(request.get("cutoff_comparison_factor", 1.25))
    if not np.isfinite(factor) or factor <= 1:
        raise ValueError("cutoff_comparison_factor must exceed one")
    refined = _evaluate(lattice, positions, moments, alpha, rc * factor, kc * factor, boundary)
    result["cutoff_comparison"] = {
        "factor": factor,
        "absolute_energy_change": abs(prefactor * (refined["energy_total"] - result["energy_total"])),
        "max_moment_gradient_change": abs(prefactor) * float(np.max(np.abs(
            np.array(refined["moment_gradient"]) - np.array(result["moment_gradient"])))),
        "rigorous_error_bound": False,
    }
    result["energy_total"] *= prefactor
    result["components"] = {key: prefactor * value for key, value in result["components"].items()}
    result["moment_gradient"] = (prefactor * np.array(result["moment_gradient"])).tolist()
    result.update({"status": "ok", "method": "three-dimensional-dipolar-ewald",
                   "alpha": alpha, "real_cutoff": rc, "reciprocal_cutoff": kc,
                   "boundary": boundary, "prefactor": prefactor,
                   "units": "prefactor * moment_unit^2 / lattice_length_unit^3",
                   "limitations": ["Periodic 3D point dipoles; no positional forces or slab correction.",
                                   "Cutoff comparison is empirical, not a rigorous truncation error bound."]})
    return result
