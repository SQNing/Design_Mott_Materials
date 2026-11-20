"""Explicit scalar observables and finite-state energy diagnostics."""
import math
import numpy as np

from research.contracts import restore_complex, validate_id

OBSERVABLE_TASKS = {
    "energy_per_cell": "classical_ground_state",
    "local_population": "classical_ground_state",
    "harmonic_frequency": "spin_wave_spectrum",
    "quantum_gap": "quantum_low_energy",
    "spin_correlation": "quantum_low_energy",
    "mc_energy_per_site": "classical_monte_carlo",
}


def validate_observables(observables, experiments, model):
    if not isinstance(observables, list) or not observables:
        raise ValueError("provide explicit scalar observables")
    seen = set()
    dimensions = {int(s.get("dimension", 0)) for s in model["local_hilbert"]["classical_spaces"].values()}
    retained = all(s["kind"] == "complex_projective_space"
                   for s in model["local_hilbert"]["classical_spaces"].values())
    for spec in observables:
        if not isinstance(spec, dict):
            raise ValueError("observable must be an object")
        identifier = validate_id(spec.get("observable_id"))
        if identifier in seen:
            raise ValueError("duplicate observable_id")
        seen.add(identifier)
        kind, case = spec.get("kind"), spec.get("case_id")
        if kind not in OBSERVABLE_TASKS or case not in experiments:
            raise ValueError("unknown observable kind or case_id")
        if experiments[case]["task"] != OBSERVABLE_TASKS[kind]:
            raise ValueError("observable does not match the numerical experiment")
        allowed = {"observable_id", "case_id", "kind"}
        if kind == "harmonic_frequency":
            allowed |= {"q", "band_index"}
            q = np.asarray(spec.get("q"), dtype=float)
            if q.shape != (3,) or not np.all(np.isfinite(q)):
                raise ValueError("harmonic observable requires an explicit finite three-component q")
            grid = experiments[case]["settings"].get("reduced_momenta", [])
            if not any(np.asarray(x).shape == (3,) and np.allclose(q, x, atol=1e-12, rtol=0) for x in grid):
                raise ValueError("observable q is not in the computed momentum grid")
            _index(spec.get("band_index"), "band_index")
        if kind == "quantum_gap":
            allowed.add("level")
            _index(spec.get("level"), "level", minimum=1)
            if spec["level"] >= experiments[case]["settings"].get("eigenvalues", 0):
                raise ValueError("quantum level must lie in the requested eigenvalue list")
        if kind == "spin_correlation":
            allowed |= {"site_i", "site_j"}
            _index(spec.get("site_i"), "site_i")
            _index(spec.get("site_j"), "site_j")
            settings = experiments[case]["settings"]
            if "correlations" not in (settings.get("observables") or []):
                raise ValueError("spin_correlation requires 'correlations' in the experiment's observables")
            shape = settings.get("supercell_shape", [1, 1, 1])
            site_total = len(model["lattice_structure"]["basis_sites"])
            for key in shape:
                site_total *= int(key)
            if spec["site_i"] >= site_total or spec["site_j"] >= site_total:
                raise ValueError("correlation site index is outside the finite cluster")
        if kind == "local_population":
            allowed |= {"basis_index", "site"}
            _index(spec.get("basis_index"), "basis_index")
            if not retained or len(dimensions) != 1 or spec["basis_index"] >= next(iter(dimensions)):
                raise ValueError("local population requires an explicit retained-state basis index")
            if "site" in spec:
                _index(spec["site"], "site")
                if spec["site"] >= len(model["lattice_structure"]["basis_sites"]):
                    raise ValueError("population site is outside the basis")
        if kind == "mc_energy_per_site":
            allowed.add("temperature")
            value = spec.get("temperature")
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or value <= 0 or
                    value not in experiments[case]["settings"].get("temperatures", [])):
                raise ValueError("MC observable requires one of the requested positive temperatures")
        if set(spec) - allowed:
            raise ValueError("unknown observable fields")


def _index(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + " must be an integer >= " + str(minimum))


def _rays(calculation):
    from classical.cpn_local_ray_energy import state_array_from_serialized
    state = calculation["classical_state"]
    return state_array_from_serialized({**state, "shape": state["supercell_shape"]})


def evaluate_state_energy(model, calculation):
    model = restore_complex(model)
    if "classical_state" in calculation:
        from classical.cpn_local_ray_energy import evaluate_cpn_local_ray_energy
        from research.adapters import retained_payload
        return float(evaluate_cpn_local_ray_energy(retained_payload(model), _rays(calculation)))
    from common.hamiltonian_symmetry_gate import run_hamiltonian_symmetry_gate
    from three_dimensional.spin_payload import global_spin_payload
    from three_dimensional.spin_system import PeriodicSpinSystem
    payload = global_spin_payload(run_hamiltonian_symmetry_gate(model))
    system = PeriodicSpinSystem(payload, calculation["supercell_shape"])
    energy, _ = system.energy_gradient(calculation["spins"])
    return float(energy / system.cell_count)


def classical_energy_responses(plan, experiments, results, models, tolerance):
    rows, invalid = [], {}
    baseline_id = plan["baseline_point_id"]
    for case, experiment in experiments.items():
        if experiment["task"] != "classical_ground_state":
            continue
        baseline = results[(case, baseline_id)]
        base = baseline.get("calculation", {})
        baseline_bad = baseline.get("scientific_status") != "usable_within_scope"
        for point in plan["points"]:
            point_id = point["point_id"]
            result = results[(case, point_id)]
            calc = result.get("calculation", {})
            row = {"case_id": case, "point_id": point_id, "scientific_status": "inconclusive"}
            try:
                if baseline_bad or result.get("scientific_status") != "usable_within_scope":
                    raise ValueError("a classical control is not scientifically usable")
                if base["supercell_shape"] != calc["supercell_shape"]:
                    raise ValueError("classical controls have different finite cells")
                if base.get("spin_length") != calc.get("spin_length"):
                    raise ValueError("classical controls have different spin lengths")
                original = float(base["energy_per_cell"])
                relaxed = float(calc["energy_per_cell"])
                frozen = evaluate_state_energy(models[point_id]["model"], base)
                lifted = evaluate_state_energy(models[baseline_id]["model"], calc)
                base_check = evaluate_state_energy(models[baseline_id]["model"], base)
                own_check = evaluate_state_energy(models[point_id]["model"], calc)
                if not np.all(np.isfinite([original, relaxed, frozen, lifted, base_check, own_check])):
                    raise ValueError("nonfinite classical energy")
                row.update(full_reference_energy=original, frozen_state_energy=frozen,
                    relaxed_state_energy=relaxed, relaxed_state_in_full_model_energy=lifted,
                    direct_energy_change=frozen - original,
                    relaxation_energy_change=relaxed - frozen,
                    total_energy_change=relaxed - original,
                    full_model_penalty=lifted - original, supercell_shape=base["supercell_shape"])
                if abs(base_check - original) > tolerance or lifted < original - tolerance:
                    baseline_bad = True
                    raise ValueError("full-model reference is inadequate; refine it before testing this mechanism")
                if abs(own_check - relaxed) > tolerance or frozen < relaxed - tolerance:
                    raise ValueError("intervention reference is inadequate; refine it before testing this mechanism")
                row["scientific_status"] = "usable_within_scope"
            except (ValueError, TypeError, KeyError) as exc:
                row["reason"] = str(exc)
                invalid[(case, point_id)] = str(exc)
            rows.append(row)
        if baseline_bad:
            for point in plan["points"]:
                invalid[(case, point["point_id"])] = "full-model reference is inadequate or unusable"
            for row in rows:
                if row["case_id"] == case:
                    row["scientific_status"] = "inconclusive"
                    row["reason"] = "full-model reference is inadequate or unusable"
    return rows, invalid


def read_observable(spec, result, evidence, blocker=None):
    record = {"observable_id": spec["observable_id"], "kind": spec["kind"], "value": None,
              "scientific_status": "inconclusive",
              "evidence": {"path": evidence["path"], "job_fingerprint": evidence["job_fingerprint"],
                           "selector": spec, "calculation_path": "calculation"}}
    if blocker or result.get("scientific_status") != "usable_within_scope":
        record["reason"] = blocker or result.get("blocker") or "numerical result is not scientifically usable"
        return record
    calculation = result["calculation"]
    try:
        kind = spec["kind"]
        if kind == "energy_per_cell":
            value = calculation["energy_per_cell"]
            record["evidence"]["calculation_path"] = "calculation.energy_per_cell"
        elif kind == "harmonic_frequency":
            rows = [r for r in calculation["dispersion"] if np.allclose(r["q"], spec["q"], atol=1e-12, rtol=0)]
            if len(rows) != 1:
                raise ValueError("momentum selection is absent or ambiguous")
            value = np.sort(rows[0]["bands"])[spec["band_index"]]
            record["evidence"]["calculation_path"] = "calculation.dispersion"
        elif kind == "quantum_gap":
            energies = np.sort(calculation["eigenvalues"])
            value = energies[spec["level"]] - energies[0]
            record["evidence"]["calculation_path"] = "calculation.eigenvalues"
        elif kind == "spin_correlation":
            correlations = calculation["observables"]["static"]["correlations"]["matrix"]
            value = correlations[spec["site_i"]][spec["site_j"]]
            record["evidence"]["calculation_path"] = "calculation.observables.static.correlations"
        elif kind == "local_population":
            rays = _rays(calculation)
            if "site" in spec:
                rays = rays[..., spec["site"], :]
            value = np.mean(np.abs(rays[..., spec["basis_index"]]) ** 2)
            record["evidence"]["calculation_path"] = "calculation.classical_state"
        else:
            raise ValueError("equilibrated MC observable extraction is not implemented")
        if not math.isfinite(float(value)):
            raise ValueError("nonfinite observable")
        record.update(value=float(value), scientific_status="usable_within_scope")
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        record["reason"] = str(exc)
    return record

