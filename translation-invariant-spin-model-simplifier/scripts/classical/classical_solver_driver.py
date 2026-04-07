#!/usr/bin/env python3
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.generalized_lt_solver import find_generalized_lt_ground_state
    from classical.lt_constraint_recovery import recover_classical_state_from_lt, strong_constraint_residual
    from classical.lt_solver import find_lt_ground_state
else:
    from .generalized_lt_solver import find_generalized_lt_ground_state
    from .lt_constraint_recovery import recover_classical_state_from_lt, strong_constraint_residual
    from .lt_solver import find_lt_ground_state

try:
    from scipy.optimize import minimize
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly in tests
    minimize = None


def unit_vector(theta, phi):
    return np.array(
        [
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ]
    )


def classical_energy(model, spins):
    energy = 0.0
    for bond in model["bonds"]:
        matrix = np.array(bond["matrix"], dtype=float)
        s_i = spins[bond["source"]]
        s_j = spins[bond["target"]]
        energy += float(s_i @ matrix @ s_j)
    return energy


def _n_spins(model):
    return max(max(bond["source"], bond["target"]) for bond in model["bonds"]) + 1


def _n_sublattices(model):
    lattice = model.get("lattice", {})
    if lattice.get("sublattices") is not None:
        return max(1, int(lattice["sublattices"]))
    return _n_spins(model)


def _spatial_dimension(model):
    lattice = model.get("lattice", {})
    if lattice.get("dimension") is not None:
        return max(1, min(3, int(lattice["dimension"])))

    active_axes = set()
    for bond in model.get("bonds", []):
        for axis, value in enumerate(bond.get("vector", [])[:3]):
            if abs(float(value)) > 1e-12:
                active_axes.add(axis)
    return max(1, min(3, len(active_axes) or 1))


def _normalize_mesh_shape(mesh_shape, default_shape):
    if mesh_shape is None:
        return tuple(int(value) for value in default_shape)
    values = tuple(int(value) for value in mesh_shape)
    if len(values) != 3:
        raise ValueError("mesh_shape must have length 3")
    if any(value <= 0 for value in values):
        raise ValueError("mesh_shape entries must be positive")
    return values


def _default_lt_mesh_shape(model):
    dimension = _spatial_dimension(model)
    if dimension == 1:
        return (33, 1, 1)
    if dimension == 2:
        return (33, 33, 1)
    return (17, 17, 17)


def _default_generalized_lt_mesh_shape(model):
    dimension = _spatial_dimension(model)
    if dimension == 1:
        return (17, 1, 1)
    if dimension == 2:
        return (17, 17, 1)
    return (9, 9, 9)


def _normalize_lambda_bounds(lambda_bounds):
    if lambda_bounds is None:
        return (-1.0, 1.0)
    values = tuple(float(value) for value in lambda_bounds)
    if len(values) != 2:
        raise ValueError("lambda_bounds must have length 2")
    if values[0] > values[1]:
        raise ValueError("lambda_bounds must satisfy lower <= upper")
    return values


def _resolve_lt_settings(classical_config, model):
    lt_config = classical_config.get("lt", {})
    if not isinstance(lt_config, dict):
        lt_config = {}
    mesh_shape = lt_config.get("mesh_shape", classical_config.get("lt_mesh_shape"))
    return {"mesh_shape": _normalize_mesh_shape(mesh_shape, _default_lt_mesh_shape(model))}


def _resolve_generalized_lt_settings(classical_config, model):
    generalized_config = classical_config.get("generalized_lt", {})
    if not isinstance(generalized_config, dict):
        generalized_config = {}

    mesh_shape = generalized_config.get("mesh_shape", classical_config.get("generalized_lt_mesh_shape"))
    lambda_bounds = generalized_config.get(
        "lambda_bounds", classical_config.get("generalized_lt_lambda_bounds")
    )
    lambda_points = generalized_config.get(
        "lambda_points", classical_config.get("generalized_lt_lambda_points", 21)
    )
    search_strategy = generalized_config.get(
        "search_strategy", classical_config.get("generalized_lt_search_strategy")
    )
    if search_strategy is None:
        search_strategy = "grid" if _n_sublattices(model) <= 2 else "coordinate"

    lambda_points = int(lambda_points)
    if lambda_points <= 0:
        raise ValueError("lambda_points must be positive")

    return {
        "mesh_shape": _normalize_mesh_shape(mesh_shape, _default_generalized_lt_mesh_shape(model)),
        "lambda_bounds": _normalize_lambda_bounds(lambda_bounds),
        "lambda_points": lambda_points,
        "search_strategy": str(search_strategy),
    }


def _resolve_auto_settings(classical_config):
    auto_config = classical_config.get("auto_resolve", {})
    if not isinstance(auto_config, dict):
        auto_config = {}
    lt_accept_residual = float(auto_config.get("lt_accept_residual", 1e-6))
    generalized_lt_min_improvement = float(auto_config.get("generalized_lt_min_improvement", 5e-2))
    return {
        "lt_accept_residual": max(0.0, lt_accept_residual),
        "generalized_lt_min_improvement": max(0.0, generalized_lt_min_improvement),
    }


def _resolve_requested_method(classical_config, recommended_method):
    explicit_method = classical_config.get("method")
    chosen_method = classical_config.get("chosen_method")
    auto_selected = bool(classical_config.get("auto_selected", False))

    if explicit_method == "auto" or explicit_method is None and chosen_method is None:
        return {
            "requested_method": "auto",
            "initial_method": recommended_method,
            "auto_mode": True,
        }
    if auto_selected:
        return {
            "requested_method": explicit_method or chosen_method or recommended_method,
            "initial_method": explicit_method or chosen_method or recommended_method,
            "auto_mode": True,
        }
    requested_method = explicit_method or chosen_method or "variational"
    return {
        "requested_method": requested_method,
        "initial_method": requested_method,
        "auto_mode": False,
    }


def _deserialize_complex_vector(serialized):
    values = []
    for item in serialized:
        if isinstance(item, dict):
            values.append(complex(float(item.get("real", 0.0)), float(item.get("imag", 0.0))))
        else:
            values.append(complex(item))
    return values


def _infer_spin_length(payload):
    local_dimension = payload.get("normalized_model", {}).get("local_hilbert", {}).get("dimension")
    if local_dimension is None:
        local_dimension = payload.get("local_dim")
    if local_dimension is None:
        return 0.5
    local_dimension = max(2, int(local_dimension))
    return 0.5 * float(local_dimension - 1)


def _normalize_spin_direction(vector):
    spin = np.array(vector, dtype=float)
    norm = float(np.linalg.norm(spin))
    if norm <= 1e-12:
        return [0.0, 0.0, 1.0], 0.0
    return [float(value) / norm for value in spin], norm


def _build_variational_classical_state(payload):
    spins = payload.get("variational_result", {}).get("spins", [])
    if not spins:
        return None

    spin_length = _infer_spin_length(payload)
    spin_vectors = [np.array(spin, dtype=float) for spin in spins]
    site_frames = []
    site_norms = []
    for index, spin in enumerate(spin_vectors):
        direction, norm = _normalize_spin_direction(spin)
        site_frames.append({"site": int(index), "spin_length": float(spin_length), "direction": direction})
        site_norms.append(float(norm))

    return {
        "site_frames": site_frames,
        "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
        "constraint_recovery": {
            "source": "variational",
            "reconstruction": "direct",
            "strong_constraint_residual": strong_constraint_residual(spin_vectors),
            "site_norms": site_norms,
        },
    }


def _recover_lt_classical_state(payload, chosen_method):
    spin_length = _infer_spin_length(payload)
    source_result = payload.get("lt_result", {})
    amplitudes = _deserialize_complex_vector(source_result.get("eigenvector", []))
    q_vector = source_result.get("q", [0.0, 0.0, 0.0])
    target_result = source_result
    source_name = "lt"

    if chosen_method == "generalized-lt":
        target_result = payload.get("generalized_lt_result", {})
        q_vector = target_result.get("q", q_vector)
        eigenspace = target_result.get("eigenspace", [])
        if eigenspace:
            amplitudes = _deserialize_complex_vector(eigenspace[0])
        source_name = "generalized-lt"

    if not amplitudes:
        return None

    classical_state = recover_classical_state_from_lt(
        payload,
        q=q_vector,
        amplitudes=amplitudes,
        spin_length=spin_length,
        source=source_name,
    )
    target_result["constraint_recovery"] = classical_state["constraint_recovery"]
    return classical_state


def _constraint_residual(result):
    if not isinstance(result, dict):
        return None
    constraint_recovery = result.get("constraint_recovery", {})
    residual = constraint_recovery.get("strong_constraint_residual")
    if residual is None:
        return None
    return float(residual)


def _choose_auto_method(recommended_method, lt_residual, generalized_lt_residual, model, auto_settings):
    if recommended_method == "variational":
        return "variational", "recommended-variational"

    if lt_residual is not None and lt_residual <= auto_settings["lt_accept_residual"]:
        return "luttinger-tisza", "lt-residual-within-tolerance"

    if _n_sublattices(model) > 1 and generalized_lt_residual is not None and lt_residual is not None:
        if generalized_lt_residual + auto_settings["generalized_lt_min_improvement"] < lt_residual:
            return "generalized-lt", "generalized-lt-improved-residual"
        return "variational", "generalized-lt-did-not-improve-residual"

    if _n_sublattices(model) > 1 and generalized_lt_residual is not None and lt_residual is None:
        return "generalized-lt", "generalized-lt-available-without-lt-residual"

    if _n_sublattices(model) <= 1:
        return "variational", "single-sublattice-lt-residual-too-large"

    return "variational", "missing-residual-diagnostics"


def _normalized_direction(direction):
    if direction is None:
        direction = [0.0, 0.0, 1.0]
    vector = np.array(direction, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("field direction must have non-zero norm")
    return vector / norm


def magnetization_per_spin(spins, field_direction=None):
    direction = _normalized_direction(field_direction)
    return float(np.mean(spins, axis=0) @ direction)


def infer_high_temperature_energy_per_spin(model):
    n_spins = _n_spins(model)
    energy_total = 0.0
    for bond in model["bonds"]:
        if int(bond["source"]) != int(bond["target"]):
            continue
        matrix = np.array(bond["matrix"], dtype=float)
        energy_total += float(np.trace(matrix) / 3.0)
    return energy_total / float(n_spins)


def resolve_temperature_schedule(temperatures, scan_order="as_given"):
    indexed = [(index, float(temperature)) for index, temperature in enumerate(temperatures)]
    if scan_order == "as_given":
        return indexed
    if scan_order == "ascending":
        return sorted(indexed, key=lambda item: item[1])
    if scan_order == "descending":
        return sorted(indexed, key=lambda item: item[1], reverse=True)
    raise ValueError(f"unsupported scan_order: {scan_order}")


def integrated_autocorrelation_time(samples):
    values = np.array(samples, dtype=float)
    sample_count = len(values)
    if sample_count < 2:
        return 0.0
    centered = values - float(np.mean(values))
    variance = float(np.mean(centered**2))
    if variance <= 1e-15:
        return 0.0

    tau = 0.5
    max_lag = sample_count - 1
    for lag in range(1, max_lag + 1):
        covariance = float(np.mean(centered[:-lag] * centered[lag:]))
        rho = covariance / variance
        if rho <= 0.0:
            break
        tau += rho
    return float(tau)


def _mean_stderr(samples):
    values = np.array(samples, dtype=float)
    sample_count = len(values)
    if sample_count == 0:
        raise ValueError("at least one sample is required")
    if sample_count == 1:
        return 0.0, 0.0

    variance = float(np.mean((values - float(np.mean(values))) ** 2))
    if variance <= 1e-15:
        return 0.0, integrated_autocorrelation_time(values)

    tau = integrated_autocorrelation_time(values)
    correlation_factor = max(1.0, 2.0 * tau)
    stderr = math.sqrt(variance * correlation_factor / float(sample_count))
    return float(stderr), float(tau)


def _variance_stderr(samples):
    values = np.array(samples, dtype=float)
    if len(values) < 2:
        return 0.0
    centered_squares = (values - float(np.mean(values))) ** 2
    stderr, _tau = _mean_stderr(centered_squares)
    return float(stderr)


def recommend_method(model):
    effective_main = model.get("effective_model", {}).get("main", [])
    effective_types = {block.get("type") for block in effective_main}
    simplified_template = model.get("simplified_model", {}).get("template")
    if simplified_template == "heisenberg" or "isotropic_exchange" in effective_types:
        return "luttinger-tisza"
    if model.get("lattice", {}).get("sublattices", 1) == 1 and (
        simplified_template == "xxz" or "xxz_like" in effective_types
    ):
        return "luttinger-tisza"
    return "variational"


def choose_method(model, user_choice=None, timed_out=False, allow_auto_select=False):
    if user_choice is not None:
        return {"method": user_choice, "auto_selected": False}
    recommended = recommend_method(model)
    if timed_out:
        return {"method": recommended, "auto_selected": True}
    if allow_auto_select:
        return {"method": recommended, "auto_selected": True}
    return {"method": None, "auto_selected": False, "recommended": recommended}


def solve_variational(model, starts=16, seed=0):
    rng = np.random.default_rng(seed)
    n_spins = _n_spins(model)
    best = None

    def objective(params):
        spins = np.array([unit_vector(params[2 * index], params[2 * index + 1]) for index in range(n_spins)])
        return classical_energy(model, spins)

    for _ in range(starts):
        guess = rng.uniform(0.0, 2.0 * math.pi, size=2 * n_spins)
        if minimize is None:
            result = type("FallbackResult", (), {"fun": objective(guess), "x": guess})()
        else:
            result = minimize(objective, guess, method="Powell")
        if best is None or result.fun < best.fun:
            best = result

    spins = [unit_vector(best.x[2 * index], best.x[2 * index + 1]).tolist() for index in range(n_spins)]
    return {"method": "variational", "energy": float(best.fun), "spins": spins}


def random_spin(rng):
    u = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    xy = math.sqrt(max(0.0, 1.0 - u * u))
    return np.array([xy * math.cos(phi), xy * math.sin(phi), u])


def metropolis_step(model, spins, temperature, rng, current_energy=None):
    trial = spins.copy()
    index = int(rng.integers(0, len(spins)))
    old_energy = classical_energy(model, spins) if current_energy is None else current_energy
    trial[index] = random_spin(rng)
    new_energy = classical_energy(model, trial)
    if new_energy <= old_energy:
        return trial, new_energy
    if temperature <= 0.0:
        return spins, old_energy
    accept_prob = math.exp(-(new_energy - old_energy) / temperature)
    if rng.uniform() < accept_prob:
        return trial, new_energy
    return spins, old_energy


def metropolis_sweep(model, spins, temperature, rng):
    energy = classical_energy(model, spins)
    for _ in range(len(spins)):
        spins, energy = metropolis_step(model, spins, temperature, rng, current_energy=energy)
    return spins, energy


def summarize_thermodynamics(
    temperatures,
    energy_samples,
    magnetization_samples,
    *,
    n_spins=1,
    high_temperature_entropy=0.0,
    energy_infinite_temperature=0.0,
    scan_order="as_given",
    reuse_configuration=True,
    sweeps=None,
    burn_in=None,
    measurement_interval=1,
):
    if len(temperatures) != len(energy_samples) or len(temperatures) != len(magnetization_samples):
        raise ValueError("temperature grid and sample collections must have the same length")

    summaries = []
    for index, temperature in enumerate(temperatures):
        temperature = float(temperature)
        if temperature <= 0.0:
            raise ValueError("temperatures must be strictly positive")

        local_energies = np.array(energy_samples[index], dtype=float)
        local_magnetizations = np.array(magnetization_samples[index], dtype=float)
        if local_energies.size == 0 or local_magnetizations.size == 0:
            raise ValueError("each temperature requires at least one post-burn-in measurement")

        mean_energy = float(np.mean(local_energies))
        mean_magnetization = float(np.mean(local_magnetizations))
        energy_variance = float(max(0.0, np.mean(local_energies**2) - mean_energy**2))
        magnetization_variance = float(max(0.0, np.mean(local_magnetizations**2) - mean_magnetization**2))
        beta = 1.0 / temperature
        energy_stderr, energy_tau = _mean_stderr(local_energies)
        magnetization_stderr, magnetization_tau = _mean_stderr(local_magnetizations)
        specific_heat_stderr = float(beta * beta * n_spins * _variance_stderr(local_energies))
        susceptibility_stderr = float(beta * n_spins * _variance_stderr(local_magnetizations))
        summaries.append(
            {
                "index": index,
                "temperature": temperature,
                "beta": beta,
                "energy": mean_energy,
                "magnetization": mean_magnetization,
                "energy_variance": energy_variance,
                "magnetization_variance": magnetization_variance,
                "energy_stderr": energy_stderr,
                "magnetization_stderr": magnetization_stderr,
                "energy_tau": energy_tau,
                "magnetization_tau": magnetization_tau,
                "specific_heat": float(beta * beta * n_spins * energy_variance),
                "susceptibility": float(beta * n_spins * magnetization_variance),
                "specific_heat_stderr": specific_heat_stderr,
                "susceptibility_stderr": susceptibility_stderr,
            }
        )

    sorted_summaries = sorted(summaries, key=lambda item: item["beta"])
    previous_beta = 0.0
    previous_energy = float(energy_infinite_temperature)
    previous_energy_stderr = 0.0
    cumulative_beta_f = -float(high_temperature_entropy)
    cumulative_beta_f_variance = 0.0
    for summary in sorted_summaries:
        delta_beta = summary["beta"] - previous_beta
        cumulative_beta_f += 0.5 * (previous_energy + summary["energy"]) * delta_beta
        cumulative_beta_f_variance += (0.5 * delta_beta) ** 2 * (
            previous_energy_stderr**2 + summary["energy_stderr"] ** 2
        )
        summary["free_energy"] = float(cumulative_beta_f / summary["beta"])
        summary["free_energy_stderr"] = float(math.sqrt(cumulative_beta_f_variance) / summary["beta"])
        summary["entropy"] = float((summary["energy"] - summary["free_energy"]) / summary["temperature"])
        summary["entropy_stderr"] = float(
            math.sqrt(summary["energy_stderr"] ** 2 + summary["free_energy_stderr"] ** 2) / summary["temperature"]
        )
        previous_beta = summary["beta"]
        previous_energy = summary["energy"]
        previous_energy_stderr = summary["energy_stderr"]

    sorted_summaries.sort(key=lambda item: item["index"])
    grid = [
        {
            "temperature": summary["temperature"],
            "beta": summary["beta"],
            "energy": summary["energy"],
            "magnetization": summary["magnetization"],
            "specific_heat": summary["specific_heat"],
            "susceptibility": summary["susceptibility"],
            "free_energy": summary["free_energy"],
            "entropy": summary["entropy"],
            "energy_stderr": summary["energy_stderr"],
            "magnetization_stderr": summary["magnetization_stderr"],
            "specific_heat_stderr": summary["specific_heat_stderr"],
            "susceptibility_stderr": summary["susceptibility_stderr"],
            "free_energy_stderr": summary["free_energy_stderr"],
            "entropy_stderr": summary["entropy_stderr"],
            "energy_autocorrelation_time": summary["energy_tau"],
            "magnetization_autocorrelation_time": summary["magnetization_tau"],
        }
        for summary in sorted_summaries
    ]

    return {
        "grid": grid,
        "observables": {
            "energy": [summary["energy"] for summary in sorted_summaries],
            "free_energy": [summary["free_energy"] for summary in sorted_summaries],
            "specific_heat": [summary["specific_heat"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization"] for summary in sorted_summaries],
            "susceptibility": [summary["susceptibility"] for summary in sorted_summaries],
            "entropy": [summary["entropy"] for summary in sorted_summaries],
        },
        "uncertainties": {
            "energy": [summary["energy_stderr"] for summary in sorted_summaries],
            "free_energy": [summary["free_energy_stderr"] for summary in sorted_summaries],
            "specific_heat": [summary["specific_heat_stderr"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization_stderr"] for summary in sorted_summaries],
            "susceptibility": [summary["susceptibility_stderr"] for summary in sorted_summaries],
            "entropy": [summary["entropy_stderr"] for summary in sorted_summaries],
        },
        "autocorrelation": {
            "energy": [summary["energy_tau"] for summary in sorted_summaries],
            "magnetization": [summary["magnetization_tau"] for summary in sorted_summaries],
        },
        "reference": {
            "high_temperature_entropy": float(high_temperature_entropy),
            "energy_infinite_temperature": float(energy_infinite_temperature),
            "normalization": "per_spin",
        },
        "sampling": {
            "scan_order": scan_order,
            "reuse_configuration": bool(reuse_configuration),
            "sweeps": sweeps,
            "burn_in": burn_in,
            "measurement_interval": int(measurement_interval),
        },
    }


def estimate_thermodynamics(
    model,
    temperatures,
    sweeps=100,
    burn_in=50,
    seed=0,
    measurement_interval=1,
    field_direction=None,
    high_temperature_entropy=0.0,
    energy_infinite_temperature=None,
    scan_order="as_given",
    reuse_configuration=True,
):
    rng = np.random.default_rng(seed)
    n_spins = _n_spins(model)
    spins = np.array([random_spin(rng) for _ in range(n_spins)])
    if measurement_interval <= 0:
        raise ValueError("measurement_interval must be positive")
    if energy_infinite_temperature is None:
        energy_infinite_temperature = infer_high_temperature_energy_per_spin(model)

    energy_samples = [None] * len(temperatures)
    magnetization_samples = [None] * len(temperatures)

    for index, temperature in resolve_temperature_schedule(temperatures, scan_order=scan_order):
        if not reuse_configuration:
            spins = np.array([random_spin(rng) for _ in range(n_spins)])
        local_energies = []
        local_mags = []
        for sweep in range(sweeps + burn_in):
            spins, energy = metropolis_sweep(model, spins, temperature, rng)
            if sweep >= burn_in and (sweep - burn_in) % measurement_interval == 0:
                local_energies.append(float(energy) / float(n_spins))
                local_mags.append(magnetization_per_spin(spins, field_direction=field_direction))

        energy_samples[index] = local_energies
        magnetization_samples[index] = local_mags

    return summarize_thermodynamics(
        temperatures,
        energy_samples,
        magnetization_samples,
        n_spins=n_spins,
        high_temperature_entropy=high_temperature_entropy,
        energy_infinite_temperature=energy_infinite_temperature,
        scan_order=scan_order,
        reuse_configuration=reuse_configuration,
        sweeps=sweeps,
        burn_in=burn_in,
        measurement_interval=measurement_interval,
    )


def run_classical_solver(payload, starts=16, seed=0):
    recommended_method = payload.setdefault("recommended_method", recommend_method(payload))
    classical_config = payload.setdefault("classical", {})
    method_resolution = _resolve_requested_method(classical_config, recommended_method)
    requested_method = method_resolution["requested_method"]
    initial_method = method_resolution["initial_method"]
    auto_mode = method_resolution["auto_mode"]
    auto_settings = _resolve_auto_settings(classical_config)

    classical_config["requested_method"] = requested_method
    classical_config["auto_resolution"] = {
        "enabled": bool(auto_mode),
        "recommended_method": recommended_method,
        "initial_method": initial_method,
        "resolved_method": None,
        "lt_residual": None,
        "generalized_lt_residual": None,
        "reason": None,
        "lt_accept_residual": auto_settings["lt_accept_residual"],
        "generalized_lt_min_improvement": auto_settings["generalized_lt_min_improvement"],
    }

    if not auto_mode:
        classical_config["chosen_method"] = initial_method

    if initial_method in {"luttinger-tisza", "generalized-lt"}:
        lt_settings = _resolve_lt_settings(classical_config, payload)
        payload["lt_result"] = find_lt_ground_state(payload, mesh_shape=lt_settings["mesh_shape"])

    if initial_method == "generalized-lt":
        generalized_settings = _resolve_generalized_lt_settings(classical_config, payload)
        payload["generalized_lt_result"] = find_generalized_lt_ground_state(
            payload,
            mesh_shape=generalized_settings["mesh_shape"],
            lambda_bounds=generalized_settings["lambda_bounds"],
            lambda_points=generalized_settings["lambda_points"],
            search_strategy=generalized_settings["search_strategy"],
        )

    payload["variational_result"] = solve_variational(payload, starts=starts, seed=seed)

    lt_classical_state = None
    generalized_lt_classical_state = None
    variational_classical_state = _build_variational_classical_state(payload)

    if "lt_result" in payload:
        lt_classical_state = _recover_lt_classical_state(payload, "luttinger-tisza")
        classical_config["auto_resolution"]["lt_residual"] = _constraint_residual(payload.get("lt_result"))

    if initial_method == "generalized-lt":
        generalized_lt_classical_state = _recover_lt_classical_state(payload, "generalized-lt")
        classical_config["auto_resolution"]["generalized_lt_residual"] = _constraint_residual(
            payload.get("generalized_lt_result")
        )

    chosen_method = initial_method
    classical_state = None
    resolution_reason = "explicit-user-choice"

    if auto_mode:
        lt_residual = classical_config["auto_resolution"]["lt_residual"]
        generalized_lt_residual = classical_config["auto_resolution"]["generalized_lt_residual"]

        if initial_method == "luttinger-tisza" and lt_residual is not None and lt_residual > auto_settings["lt_accept_residual"]:
            generalized_settings = _resolve_generalized_lt_settings(classical_config, payload)
            payload["generalized_lt_result"] = find_generalized_lt_ground_state(
                payload,
                mesh_shape=generalized_settings["mesh_shape"],
                lambda_bounds=generalized_settings["lambda_bounds"],
                lambda_points=generalized_settings["lambda_points"],
                search_strategy=generalized_settings["search_strategy"],
            )
            generalized_lt_classical_state = _recover_lt_classical_state(payload, "generalized-lt")
            generalized_lt_residual = _constraint_residual(payload.get("generalized_lt_result"))
            classical_config["auto_resolution"]["generalized_lt_residual"] = generalized_lt_residual

        chosen_method, resolution_reason = _choose_auto_method(
            recommended_method,
            lt_residual=classical_config["auto_resolution"]["lt_residual"],
            generalized_lt_residual=classical_config["auto_resolution"]["generalized_lt_residual"],
            model=payload,
            auto_settings=auto_settings,
        )

    if chosen_method == "luttinger-tisza":
        classical_state = lt_classical_state
    elif chosen_method == "generalized-lt":
        classical_state = generalized_lt_classical_state
    elif chosen_method == "variational":
        classical_state = variational_classical_state

    classical_config["chosen_method"] = chosen_method
    classical_config["auto_resolution"]["resolved_method"] = chosen_method
    classical_config["auto_resolution"]["reason"] = resolution_reason

    if classical_state is not None:
        payload["classical_state"] = classical_state
        classical_config["classical_state"] = classical_state

    thermodynamics = payload.get("thermodynamics")
    if isinstance(thermodynamics, dict) and thermodynamics.get("temperatures"):
        payload["thermodynamics_result"] = estimate_thermodynamics(
            payload,
            thermodynamics["temperatures"],
            sweeps=int(thermodynamics.get("sweeps", 100)),
            burn_in=int(thermodynamics.get("burn_in", 50)),
            seed=int(thermodynamics.get("seed", seed)),
            measurement_interval=int(thermodynamics.get("measurement_interval", 1)),
            field_direction=thermodynamics.get("field_direction"),
            high_temperature_entropy=float(thermodynamics.get("high_temperature_entropy", 0.0)),
            energy_infinite_temperature=thermodynamics.get("energy_infinite_temperature"),
            scan_order=str(thermodynamics.get("scan_order", "as_given")),
            reuse_configuration=bool(thermodynamics.get("reuse_configuration", True)),
        )
    return payload


def _load_payload(path):
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    payload = _load_payload(args.input)
    payload = run_classical_solver(payload, starts=args.starts, seed=args.seed)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
