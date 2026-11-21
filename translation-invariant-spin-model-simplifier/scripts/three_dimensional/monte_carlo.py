"""Classical sphere Metropolis sampling and descriptive finite-size analysis."""

import math
import numpy as np
from classical.classical_solver_driver import integrated_autocorrelation_time
from three_dimensional.spin_system import PeriodicSpinSystem


def _uncertainty(values):
    values = np.asarray(values, dtype=float)
    tau = max(0.5, integrated_autocorrelation_time(values))
    effective = len(values) / (2 * tau)
    return float(np.std(values, ddof=1) / math.sqrt(effective)), tau, effective


def _fluctuations(samples, site_count, temperature):
    energy, squared = samples[:, 0], samples[:, 1]
    mean_squared = float(np.mean(squared))
    ratio = float(np.mean(squared ** 2)) / mean_squared ** 2 if mean_squared > 0 else None
    return np.array([np.var(energy) / (site_count * temperature ** 2),
                     1 - ratio / 3 if ratio is not None else 0.0])


def classical_monte_carlo(system, request):
    spin_length = float(request["spin_length"])
    temperatures = [float(value) for value in request["temperatures"]]
    sweeps, burn = int(request.get("sweeps", 2000)), int(request.get("burn_in", 1000))
    interval = int(request.get("measurement_interval", 1))
    if (not np.isfinite(spin_length) or spin_length <= 0 or not temperatures or
            any(not np.isfinite(value) or value <= 0 for value in temperatures) or
            sweeps < 2 or burn < 0 or interval < 1 or sweeps // interval < 2):
        raise ValueError("positive spin_length/temperatures and at least two measurement samples are required")
    rng = np.random.default_rng(int(request.get("seed", 0)))
    site_count = system.site_count
    outgoing = [np.flatnonzero(system.source == site) for site in range(site_count)]
    incoming = [np.flatnonzero(system.target == site) for site in range(site_count)]
    self_tensors = [np.sum(system.matrices[(system.source == site) & (system.target == site)], axis=0)
                    for site in range(site_count)]
    basis = np.array([record["position"] for record in system.payload["lattice_structure"]["basis_sites"]])
    positions = (system.cells[:, None, :] + basis[None, :, :]).reshape((-1, 3))
    q = np.array(request.get("order_momentum", [0, 0, 0]), dtype=float)
    if q.shape != (3,) or not np.all(np.isfinite(q)):
        raise ValueError("order_momentum must be a finite 3-vector in primitive reciprocal units")
    phases = np.exp(2j * math.pi * (positions @ q))
    certify = bool(request.get("certify_equilibration", True))
    z_limit = float(request.get("equilibration_z_limit", 3.0))
    min_tau_lengths = float(request.get("equilibration_min_tau_lengths", 20.0))
    min_effective = float(request.get("equilibration_min_effective_samples", 50.0))

    def run_chain(chain_rng, temperature):
        spins = chain_rng.normal(size=(site_count, 3))
        spins *= spin_length / np.linalg.norm(spins, axis=1, keepdims=True)
        samples, uniform_means = [], []
        accepts = 0
        for sweep in range(burn + sweeps):
            for site in chain_rng.permutation(site_count):
                forward, backward = outgoing[site], incoming[site]
                field = np.einsum("bij,bj->i", system.matrices[forward], spins[system.target[forward]])
                field += np.einsum("bji,bj->i", system.matrices[backward], spins[system.source[backward]])
                proposed = chain_rng.normal(size=3)
                proposed *= spin_length / np.linalg.norm(proposed)
                delta = proposed - spins[site]
                change = float(delta @ field + delta @ self_tensors[site] @ delta)
                if change <= 0 or chain_rng.random() < math.exp(-change / temperature):
                    spins[site] = proposed
                    if sweep >= burn:
                        accepts += 1
            if sweep >= burn and (sweep - burn) % interval == 0:
                energy, _gradient = system.energy_gradient(spins)
                order = np.sum(phases[:, None] * spins, axis=0) / site_count
                samples.append([energy, float(np.vdot(order, order).real)])
                uniform_means.append(np.mean(spins, axis=0))
        return np.array(samples), np.array(uniform_means), accepts

    grid = []
    for t_index, temperature in enumerate(temperatures):
        samples, uniform_means, accepts = run_chain(rng, temperature)
        energy, squared = samples[:, 0], samples[:, 1]
        energy_error, energy_tau, effective = _uncertainty(energy / site_count)
        order_error, order_tau, order_effective = _uncertainty(squared)
        heat_capacity, cumulant = _fluctuations(samples, site_count, temperature)
        ratio = float(np.mean(squared ** 2) / np.mean(squared) ** 2)
        block_size = max(1, int(math.ceil(10 * max(energy_tau, order_tau))), len(samples) // 32)
        blocks = len(samples) // block_size
        fluctuation_errors = [None, None]
        if blocks >= 4:
            used = samples[:blocks * block_size].reshape((blocks, block_size, 2))
            leave_one_out = [_fluctuations(np.concatenate([used[:i], used[i + 1:]]).reshape((-1, 2)),
                                           site_count, temperature) for i in range(blocks)]
            fluctuation_errors = (np.std(leave_one_out, axis=0, ddof=0) * math.sqrt(blocks - 1)).tolist()
        uniform = np.array(uniform_means)
        susceptibility = site_count / (3 * temperature) * float(np.sum(np.var(uniform, axis=0)))
        equilibration = None
        if certify:
            # Second independent chain (fresh initialization, independent seed):
            # equilibration requires the two chains' energy and order samples to
            # be statistically indistinguishable, long enough measured span in
            # units of the autocorrelation time, and enough effective samples.
            seed2 = int(request.get("seed", 0)) + 104729 * (t_index + 1) + 1
            rng2 = np.random.default_rng(seed2)
            samples2, _uniform2, _accepts2 = run_chain(rng2, temperature)
            e2, o2 = samples2[:, 0] / site_count, samples2[:, 1]
            e1, o1 = energy / site_count, squared
            err2_e, tau2_e, _eff2e = _uncertainty(e2)
            err2_o, tau2_o, _eff2o = _uncertainty(o2)
            z_energy = abs(float(np.mean(e1)) - float(np.mean(e2))) / max(
                math.sqrt(energy_error ** 2 + err2_e ** 2), 1e-300)
            z_order = abs(float(np.mean(o1)) - float(np.mean(o2))) / max(
                math.sqrt(order_error ** 2 + err2_o ** 2), 1e-300)
            tau_max = max(energy_tau, order_tau, tau2_e, tau2_o)
            span_tau = (sweeps // interval) / max(tau_max, 1e-300)
            reasons = []
            if z_energy > z_limit:
                reasons.append("energy distributions differ between independent chains (z=%.2f)" % z_energy)
            if z_order > z_limit:
                reasons.append("order-parameter distributions differ between independent chains (z=%.2f)" % z_order)
            if span_tau < min_tau_lengths:
                reasons.append("measured span %.1f tau_int below required %.1f" % (span_tau, min_tau_lengths))
            if min(effective, order_effective) < min_effective:
                reasons.append("effective samples %.1f below required %.1f"
                               % (min(effective, order_effective), min_effective))
            equilibration = {"certified": not reasons,
                             "z_limit": z_limit,
                             "z_energy": float(z_energy), "z_order": float(z_order),
                             "tau_int_sweeps": float(tau_max),
                             "span_tau_lengths": float(span_tau),
                             "min_tau_lengths": min_tau_lengths,
                             "second_chain_seed": seed2,
                             "failure_reasons": reasons}
        row = {
            "temperature": temperature, "energy_per_site": float(np.mean(energy)) / site_count,
            "energy_stderr": energy_error, "energy_tau_int_samples": energy_tau,
            "energy_effective_samples": effective, "samples": len(samples),
            "heat_capacity_per_site": float(heat_capacity), "heat_capacity_stderr": fluctuation_errors[0],
            "order_parameter_squared": float(np.mean(squared)), "order_squared_stderr": order_error,
            "order_effective_samples": order_effective,
            "binder_ratio": ratio, "binder_cumulant": float(cumulant), "binder_stderr": fluctuation_errors[1],
            "uniform_susceptibility_per_component": susceptibility,
            "acceptance_rate": accepts / (sweeps * site_count),
            "jackknife_block_size": block_size, "jackknife_blocks": blocks,
            "effective_sample_warning": min(effective, order_effective) < 50 or blocks < 8,
        }
        if equilibration is not None:
            row["equilibration"] = equilibration
        grid.append(row)
    all_certified = bool(grid) and all(row.get("equilibration", {}).get("certified", False)
                                       for row in grid)
    result = {
        "status": "ok", "method": "classical-periodic-sphere-Metropolis",
        "grid": grid, "site_count": site_count, "supercell_shape": list(system.shape),
        "spin_length": spin_length, "order_momentum": q.tolist(),
        "definitions": {"order": "M(q)=sum_i exp(2pi i q.r_i) S_i / N",
                        "binder_ratio": "<|M|^4>/<|M|^2>^2", "binder_cumulant": "1-binder_ratio/3",
                        "heat_capacity_per_site": "Var(H_total)/(N*T^2)",
                        "uniform_susceptibility_per_component": "N*sum_a Var(m_a)/(3*T)",
                        "temperature": "model energy units, k_B=1"},
        "sampling": {"burn_in_sweeps": burn, "measurement_sweeps": sweeps,
                     "measurement_interval": interval, "seed": int(request.get("seed", 0)),
                     "independent_initialization_each_temperature": True,
                     "equilibration_verified": all_certified,
                     "equilibration_check": ("dual-chain z-test + tau_int span + effective samples"
                                             if certify else "disabled")},
        "limitations": ["Classical, not quantum Monte Carlo; local updates can be slow near transitions.",
                        "Reported statistical errors do not establish equilibration or remove finite-size bias."],
    }
    if certify and not all_certified:
        result["equilibration_status"] = "equilibration_not_certified"
    result["thermodynamics_v1"] = {
        "schema_version": "thermodynamics/v1", "source": "classical_mc",
        "grid": [{"temperature": row["temperature"],
                  "energy_per_site": {"value": row["energy_per_site"],
                                      "stderr": row["energy_stderr"]},
                  "heat_capacity_per_site": {"value": row["heat_capacity_per_site"],
                                             "stderr": row["heat_capacity_stderr"]},
                  "entropy_per_site": {"value": None,
                                       "note": "not available from Metropolis sampling"},
                  "uniform_susceptibility_per_site": {
                      "value": row["uniform_susceptibility_per_component"] * 3.0,
                      "stderr": None,
                      "note": "isotropic sum (3x per-component value)"}}
                 for row in grid],
        "equilibration_certified": all_certified,
    }
    return result


def classical_finite_size(payload, request):
    shapes = request["supercell_shapes"]
    if len(shapes) < 2 or len({tuple(shape) for shape in shapes}) != len(shapes):
        raise ValueError("finite-size analysis requires at least two distinct supercell shapes")
    sizes = [classical_monte_carlo(PeriodicSpinSystem(payload, shape),
             {**request, "seed": int(request.get("seed", 0)) + 104729 * index})
             for index, shape in enumerate(shapes)]
    crossings = []
    for left_index in range(len(sizes) - 1):
        for right_index in range(left_index + 1, len(sizes)):
            left = sorted(sizes[left_index]["grid"], key=lambda row: row["temperature"])
            right = sorted(sizes[right_index]["grid"], key=lambda row: row["temperature"])
            for index in range(len(left) - 1):
                difference0 = left[index]["binder_cumulant"] - right[index]["binder_cumulant"]
                difference1 = left[index + 1]["binder_cumulant"] - right[index + 1]["binder_cumulant"]
                if difference0 * difference1 < 0:
                    t0, t1 = left[index]["temperature"], left[index + 1]["temperature"]
                    crossings.append({"size_indices": [left_index, right_index],
                                      "temperature_bracket": [t0, t1],
                                      "linear_interpolation": t0 + (t1 - t0) * difference0 / (difference0 - difference1),
                                      "statistically_resolved": False})
    return {"status": "ok", "method": "classical-finite-size-comparison", "sizes": sizes,
            "binder_crossing_candidates": crossings, "critical_temperature_certified": False,
            "limitations": ["Crossings are descriptive interpolations without a Tc fit or significance claim.",
                            "Use more sizes, longer independent runs and a denser T grid for scaling fits."]}
