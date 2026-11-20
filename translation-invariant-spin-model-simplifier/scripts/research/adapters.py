"""Complete-model adapters to existing numerical kernels, never paper routers."""
from copy import deepcopy
import inspect

from common.julia_environment import probe_julia_environment
from common.quantum_method_routing import quantum_method_stage_decision
from common.solver_capability_registry import registered_research_solver_capabilities
from research.contracts import restore_complex, runtime_identity

_QUANTUM_TASKS = {"quantum_low_energy"}
_NOT_CONNECTED = {
    "quantum-dmrg-itensor": "quantum-dmrg-itensor",
    "dmrg": "quantum-dmrg-itensor", "itensor": "quantum-dmrg-itensor",
    "julia-itensor": "quantum-dmrg-itensor", "mps": "quantum-dmrg-itensor",
    "quantum-vmc-netket": "quantum-vmc-netket",
    "vmc": "quantum-vmc-netket", "netket": "quantum-vmc-netket",
    "python-netket": "quantum-vmc-netket",
}
_SUNNY_BACKENDS = {"sunny", "julia-sunny", "sunny.jl"}
_SUNNY_TASKS = {"classical_ground_state": "sunny-sun-classical",
                "classical_monte_carlo": "sunny-sun-thermodynamics"}


def _model_spaces(model):
    return {v.get("kind") for v in
            model.get("local_hilbert", {}).get("classical_spaces", {}).values()}


def _sunny_capability(model, task):
    """Environment-gated Sunny route; explicit unavailability, never fallback."""
    solver_id = _SUNNY_TASKS[task]
    if not _model_spaces(model).issubset({"complex_projective_space"}):
        return {"status": "unsupported",
                "blocker": ("sunny route requires the retained-local CP^(N-1) model; "
                            "spin-only models use the python backends")}
    probe = probe_julia_environment()
    if not probe["available"]:
        return {"status": "unsupported",
                "blocker": "backend-not-connected: julia-unavailable (%s)" % probe["detail"],
                "julia_probe": probe}
    capability = next(cap for cap in registered_research_solver_capabilities()
                      if cap["solver_id"] == solver_id)
    return {"status": "supported", **capability, "julia_probe": probe}


def capability_for(model, task, settings):
    from common.canonical_hamiltonian import pair_coefficient_representation
    settings = settings if isinstance(settings, dict) else {}
    backend = str(settings.get("backend", "python"))
    # Explicit requests for declared-but-not-connected backends fail closed.
    requested = _NOT_CONNECTED.get(backend)
    if requested or task in {"quantum_ground_state_dmrg", "quantum_ground_state_vmc"}:
        solver_id = requested or ("quantum-dmrg-itensor" if "dmrg" in task
                                  else "quantum-vmc-netket")
        return {"status": "unsupported",
                "blocker": "backend-not-connected: " + solver_id,
                "declared_backend": solver_id}
    if backend in _SUNNY_BACKENDS:
        if task not in _SUNNY_TASKS:
            return {"status": "unsupported",
                    "blocker": ("sunny route is connected for %s only"
                                % "/".join(sorted(_SUNNY_TASKS)))}
        return _sunny_capability(model, task)
    if backend not in {"python", "auto"}:
        return {"status": "unsupported", "blocker": "backend-not-connected: " + backend}
    if any(v is None for v in runtime_identity()["packages"].values()):
        return {"status": "unsupported", "blocker": "python-numpy-scipy-environment-unavailable"}
    spaces = _model_spaces(model)
    terms = model.get("terms", [])
    families = {t["operator_family"] for t in terms}
    if task in _QUANTUM_TASKS:
        if spaces and spaces.issubset({"complex_projective_space"}):
            return {"status": "unsupported",
                    "blocker": ("quantum route for retained local multiplets is not connected; "
                                "classical CP^(N-1) solvers remain available")}
        decision = quantum_method_stage_decision(model, settings)
        if decision["status"] != "ok":
            blocker = decision.get("blocker") or decision.get("question", {}).get("id")
            return {"status": "unsupported", "blocker": blocker, "quantum_decision": decision}
    for cap in registered_research_solver_capabilities():
        if cap.get("connection", "connected") != "connected":
            continue
        if task not in cap["tasks"]:
            continue
        if cap.get("input_kind"):
            if model.get("kind") == cap["input_kind"]:
                return {"status": "supported", **cap}
            continue
        if (spaces and spaces.issubset(set(cap["classical_spaces"])) and
                families.issubset(set(cap["term_families"])) and
                all(0 < t["arity"] <= cap["max_body_order"] for t in terms)):
            if cap["solver_id"] == "retained-local-python" and any(
                    t["operator_family"] == "pair_matrix" and
                    pair_coefficient_representation(t, model) != "full_pair_operator" for t in terms):
                return {"status": "unsupported", "blocker": "retained-local route requires full pair operators, not operator-coefficient tensors"}
            return {"status": "supported", **cap}
    detail = ",".join("%s[%s,arity=%s]" % (t["term_ref"], t["operator_family"], t["arity"]) for t in terms)
    return {"status": "unsupported", "blocker": "no-complete-model-capability: %s; %s" % (task, detail)}


def _serialized_matrix(matrix):
    return [[{"real": float(x.real), "imag": float(x.imag)} for x in row] for row in matrix]


def retained_payload(canonical):
    """Reindex full onsite/pair matrices for existing CP and GLSWT kernels."""
    import numpy as np
    dimensions = {int(x["dimension"]) for x in canonical["local_hilbert"]["classical_spaces"].values()}
    if len(dimensions) != 1 or min(dimensions) < 2:
        raise ValueError("retained-local route requires one common local dimension >= 2")
    dim = dimensions.pop()
    structure = canonical["lattice_structure"]
    sites = structure["basis_sites"]
    if not sites:
        raise ValueError("retained-local model needs basis sites")
    payload = {"classical_manifold": "CP^(N-1)", "model_type": "sun_gswt_classical",
               "basis_order": "retained_state_index", "pair_basis_order": "site_i_major_site_j_minor",
               "basis_semantics": {"local_space": "pseudospin_orbital"},
               "retained_local_space": {"factorization": {"kind": "generic_multiplet"}},
               "local_dimension": dim, "orbital_count": 0, "magnetic_site_count": len(sites),
               "lattice_vectors": structure["lattice_vectors"],
               "positions": [s["position"] for s in sites],
               "local_basis_labels": canonical.get("local_basis_labels", ["state:%s" % i for i in range(dim)]),
               "bond_tensors": [], "pair_couplings": [], "onsite_terms": [],
               "term_mapping": []}
    for term in canonical["terms"]:
        family, cluster = term["operator_family"], term["cluster"]
        matrix = np.asarray(restore_complex(term["coefficient"]), dtype=complex)
        expected = dim if family == "local_operator_matrix" else dim * dim
        if matrix.shape != (expected, expected) or not np.all(np.isfinite(matrix)):
            raise ValueError("invalid full operator matrix: " + term["term_ref"])
        if np.max(np.abs(matrix - matrix.conjugate().T)) > 1e-10:
            raise ValueError("non-Hermitian full operator matrix: " + term["term_ref"])
        if any(c["site"] < 0 or c["site"] >= len(sites) for c in cluster):
            raise ValueError("operator site outside the declared basis")
        serialized = _serialized_matrix(matrix)
        if family == "local_operator_matrix" and len(cluster) == 1:
            payload["onsite_terms"].append({"site": cluster[0]["site"], "matrix": serialized,
                                            "matrix_shape": [dim, dim]})
            destination = "onsite_terms"
        elif family == "pair_matrix" and len(cluster) == 2:
            translation = [b - a for a, b in zip(cluster[0]["translation"], cluster[1]["translation"])]
            if cluster[0]["site"] == cluster[1]["site"] and not any(translation):
                raise ValueError("onsite self pair must be supplied as its full local operator")
            record = {"source": cluster[0]["site"], "target": cluster[1]["site"],
                      "R": translation, "pair_matrix": serialized}
            payload["pair_couplings"].append(record)
            tensor = matrix.reshape((dim, dim, dim, dim)).transpose((0, 2, 1, 3))
            # cpn energy uses [left_bra,left_ket,right_bra,right_ket].
            payload["bond_tensors"].append({**record, "tensor": [
                [[[_serialized_matrix([[tensor[a, b, c, d]]])[0][0] for d in range(dim)]
                    for c in range(dim)] for b in range(dim)] for a in range(dim)]})
            destination = "bond_tensors"
        else:
            raise ValueError("unsupported complete-model term: " + term["term_ref"])
        payload["term_mapping"].append({"term_ref": term["term_ref"], "destination": destination})
    if len(payload["term_mapping"]) != len(canonical["terms"]):
        raise ValueError("incomplete canonical-to-retained mapping")
    return payload


def _retained_run(model, task, settings, reference):
    import numpy as np
    payload = retained_payload(model)
    if task == "classical_ground_state":
        from classical.cpn_local_ray_solver import solve_cpn_local_ray_ground_state
        allowed = set(inspect.signature(solve_cpn_local_ray_ground_state).parameters) - {"model", "progress_callback"}
        unknown = set(settings) - allowed - {"backend", "max_memory_mb", "stationarity_tolerance"}
        if unknown:
            raise ValueError("unsupported retained-local settings: " + ",".join(sorted(unknown)))
        if int(settings.get("max_linear_size", 1) or 0) <= 0:
            raise ValueError("research route requires a finite max_linear_size")
        kwargs = {k: v for k, v in settings.items() if k in allowed}
        if reference:
            kwargs["initial_state"] = reference["calculation"]["classical_state"]
        calculation = solve_cpn_local_ray_ground_state(payload, **kwargs)
        residual = calculation["stationarity"]["max_residual_norm"]
        calculation["status"] = "ok" if residual <= settings.get("stationarity_tolerance", 1e-6) else "inconclusive"
        calculation["energy_per_cell"] = calculation["energy"]
        calculation["limitations"] = [
            "Finite periodic product-state variational search in the full retained local space.",
            "Local stationarity does not prove the global or infinite-lattice ground state.",
            "Size convergence remains separate from stationarity."]
    else:
        from lswt.build_python_glswt_payload import build_python_glswt_payload
        from lswt.python_glswt_solver import (solve_python_glswt, _quadratic_terms,
                                            _assemble_k_blocks, _bdg_hamiltonian_from_blocks)
        classical = reference["calculation"]["classical_state"]
        shape = classical["supercell_shape"]
        q = np.asarray(settings["reduced_momenta"], dtype=float)
        if q.ndim != 2 or q.shape[1] != 3 or not len(q) or not np.all(np.isfinite(q)):
            raise ValueError("reduced_momenta must be a nonempty finite Nx3 array in primitive reciprocal units")
        if settings.get("supercell_shape", shape) != shape:
            raise ValueError("spectrum shape differs from reference magnetic supercell")
        payload["q_path"] = (q * np.asarray(shape)).tolist()
        glswt = build_python_glswt_payload(payload, classical_state=classical)
        tolerance = float(settings.get("stability_tolerance", 1e-7))
        calculation = solve_python_glswt(glswt, stationarity_tolerance=tolerance, eigenvalue_tolerance=tolerance)
        # Existing kernel diagnostics count complex modes but do not test positive
        # quadratic energy. Check the same BdG Hessian used by the spin adapter.
        terms = _quadratic_terms(glswt)
        minimum = min(float(np.linalg.eigvalsh(_bdg_hamiltonian_from_blocks(
            *_assemble_k_blocks(terms, point)))[0]) for point in glswt["q_path"])
        d = calculation["diagnostics"]
        stable = (d["stationarity"]["is_stationary"] and
                  d["bogoliubov"]["max_complex_eigenvalue_count"] == 0 and minimum >= -tolerance and
                  all(len(p["bands"]) == d["bogoliubov"]["mode_count"] for p in calculation["dispersion"]))
        calculation["status"] = "ok" if stable else "inconclusive"
        calculation["stability"] = {"is_stationary": d["stationarity"]["is_stationary"],
                                     "minimum_bdg_hessian_eigenvalue": minimum,
                                     "scope": "requested q points only"}
        calculation["supercell_shape"] = shape
        calculation["momentum_coordinates"] = "primitive-reciprocal-lattice-units"
        for record, point in zip(calculation["dispersion"], q):
            record["q"] = point.tolist()
        calculation["limitations"] = ["Harmonic expansion about saved periodic local rays.",
                                      "All N-1 retained local excitations included; only requested q points checked.",
                                      "No global-ground-state or thermodynamic-limit certification."]
    calculation["local_dimension"] = payload["local_dimension"]
    calculation["term_mapping"] = payload["term_mapping"]
    calculation["onsite_term_count"] = len(payload["onsite_terms"])
    calculation["pair_term_count"] = len(payload["pair_couplings"])
    return {"status": calculation["status"], "calculation": calculation}


def _supercell_shape_setting(settings):
    shape = settings.get("supercell_shape")
    if (not isinstance(shape, (list, tuple)) or len(shape) != 3 or
            any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in shape)):
        raise ValueError("sunny route requires supercell_shape as three positive integers")
    return [int(v) for v in shape]


def _sunny_unavailable():
    probe = probe_julia_environment()
    if probe["available"]:
        return None
    return {"status": "unsupported",
            "blocker": "backend-not-connected: julia-unavailable (%s)" % probe["detail"]}


def _sunny_classical_run(model, settings, reference):
    """Sunny :SUN minimization on the retained CP^(N-1) manifold."""
    from classical.sunny_sun_classical_driver import run_sunny_sun_classical
    unavailable = _sunny_unavailable()
    if unavailable:
        return unavailable
    if reference:
        raise ValueError("sunny classical route does not accept reference refinement; start a fresh action")
    allowed = {"supercell_shape", "starts", "seed", "wall_time_seconds",
               "backend", "max_memory_mb", "stationarity_tolerance"}
    unknown = set(settings) - allowed
    if unknown:
        raise ValueError("unsupported sunny classical settings: " + ",".join(sorted(unknown)))
    shape = _supercell_shape_setting(settings)
    backend_payload = {"backend": "Sunny.jl", "payload_kind": "sunny_sun_classical",
                       "model": retained_payload(model),
                       "supercell_shape": shape,
                       "starts": int(settings.get("starts", 8)),
                       "seed": int(settings.get("seed", 0))}
    timeout = settings.get("wall_time_seconds")
    backend_result = run_sunny_sun_classical(
        backend_payload, timeout_seconds=float(timeout) if timeout else None)
    if backend_result.get("status") != "ok":
        return {"status": "unsupported", "blocker": "sunny-backend: " +
                str((backend_result.get("error") or {}).get("code", backend_result.get("status"))),
                "backend_result": backend_result}
    from common.cpn_classical_state import resolve_cpn_local_state
    state = resolve_cpn_local_state(backend_result, default_supercell_shape=shape)
    calculation = {
        "status": "ok",
        "method": backend_result.get("method", "sunny-cpn-minimize"),
        "backend": backend_result.get("backend", {"name": "Sunny.jl", "mode": "SUN"}),
        "energy": float(backend_result["energy"]),
        "energy_normalization": "per magnetic site (Sunny energy_per_site on the simulated supercell)",
        "supercell_shape": [int(v) for v in backend_result.get("supercell_shape", shape)],
        "starts": int(backend_result.get("starts", backend_payload["starts"])),
        "seed": int(backend_result.get("seed", backend_payload["seed"])),
        "backend_stationarity": backend_result.get("backend_stationarity"),
        "classical_state": ({
            "kind": "local_rays",
            "supercell_shape": state["shape"],
            "local_rays": state["local_rays"],
        } if state else None),
        "limitations": [
            "Sunny :SUN minimization on the CP^(N-1) product-state manifold of one finite supercell.",
            "Best-of-starts result is not a certified global or thermodynamic-limit ground state.",
            "Energy normalization follows the Sunny backend; compare like-for-like supercells only.",
        ],
    }
    return {"status": "ok", "calculation": calculation, "backend_result": backend_result}


def _sunny_thermodynamics_run(model, settings, reference):
    """Sunny finite-temperature samplers on the retained CP^(N-1) manifold."""
    from classical.sunny_sun_thermodynamics_driver import run_sunny_sun_thermodynamics
    unavailable = _sunny_unavailable()
    if unavailable:
        return unavailable
    if reference:
        raise ValueError("sunny thermodynamics does not take a classical reference yet; supply initial_state explicitly")
    allowed = {"supercell_shape", "temperatures", "pt_temperatures", "wl_bin_size", "wl_bounds",
               "sweeps", "burn_in", "exchange_interval", "field_direction", "seed",
               "backend", "max_memory_mb", "wall_time_seconds"}
    unknown = set(settings) - allowed
    if unknown:
        raise ValueError("unsupported sunny thermodynamics settings: " + ",".join(sorted(unknown)))
    shape = _supercell_shape_setting(settings)
    backend_payload = {"backend": "Sunny.jl", "payload_kind": "sunny_sun_thermodynamics",
                       "model": retained_payload(model),
                       "supercell_shape": shape}
    for key in ("temperatures", "pt_temperatures", "wl_bin_size", "wl_bounds",
                "sweeps", "burn_in", "exchange_interval", "field_direction", "seed"):
        if key in settings:
            backend_payload[key] = settings[key]
    if not any(k in backend_payload for k in ("temperatures", "pt_temperatures", "wl_bounds")):
        raise ValueError("sunny thermodynamics requires temperatures, pt_temperatures or wl_bounds")
    backend_result = run_sunny_sun_thermodynamics(backend_payload)
    if backend_result.get("status") != "ok":
        return {"status": "unsupported", "blocker": "sunny-backend: " +
                str((backend_result.get("error") or {}).get("code", backend_result.get("status"))),
                "backend_result": backend_result}
    # The Julia launcher nests the sampled data under thermodynamics_result;
    # the research layer expects grid/observables at the calculation top level.
    sampled = backend_result.get("thermodynamics_result") or {}
    calculation = dict(sampled)
    calculation["status"] = "ok"
    calculation["method"] = sampled.get("method", backend_result.get("method", "sunny-sun-thermodynamics"))
    calculation["backend"] = backend_result.get("backend", sampled.get("backend"))
    if "dos_result" in backend_result:
        calculation["dos_result"] = backend_result["dos_result"]
    calculation.setdefault("limitations", [
        "Sunny finite-temperature sampling on one finite supercell; no equilibration certificate.",
        "Observables are raw backend aggregates; apply the thermodynamics contract before claims.",
    ])
    return {"status": "ok", "calculation": calculation, "backend_result": backend_result}


def run_calculation(inputs):
    if inputs["task"] == "mechanism_test":
        from research.mechanism_analysis import run_mechanism_test
        return run_mechanism_test(inputs)
    if inputs["task"] == "reduction_validation":
        from research.reduction_validation import run_reduction_validation
        return run_reduction_validation(inputs)
    model = restore_complex(inputs["model"])
    settings, reference = deepcopy(inputs["settings"]), inputs.get("reference")
    task, solver = inputs["task"], inputs["capability"]["solver_id"]
    if solver == "sunny-sun-classical":
        raw = _sunny_classical_run(model, settings, reference)
    elif solver == "sunny-thermodynamics" or solver == "sunny-sun-thermodynamics":
        raw = _sunny_thermodynamics_run(model, settings, reference)
    elif solver == "retained-local-python":
        raw = _retained_run(model, task, settings, reference)
    else:
        from three_dimensional.workflow import run_three_dimensional_workflow
        if reference:
            saved = reference["calculation"]
            shape = saved["supercell_shape"]
            if task == "spin_wave_spectrum":
                if settings.get("supercell_shape", shape) != shape:
                    raise ValueError("spectrum shape differs from reference magnetic supercell")
                if float(settings["spin"]) != float(saved["spin_length"]):
                    raise ValueError("spectrum spin differs from reference spin length")
                settings["supercell_shape"] = shape
                settings["reference_spins"] = saved["spins"]
            elif task == "classical_ground_state":
                if settings.get("supercell_shape") != shape:
                    raise ValueError("initial reference shape differs; supply explicit tiled state or use new starts")
                if float(settings["spin_length"]) != float(saved["spin_length"]):
                    raise ValueError("refinement spin length differs from reference")
                settings["initial_spins"] = saved["spins"]
        raw = run_three_dimensional_workflow(model, {**settings, "task": task})
    calculation = raw.get("calculation", {})
    status = raw.get("status")
    scientific = "usable_within_scope" if status == "ok" else (
        "unsupported" if status == "unsupported" else "inconclusive")
    diagnostics, suggestions = [], []
    scopes = list(calculation.get("limitations", []))
    if task == "classical_ground_state" and calculation:
        evidence = calculation.setdefault("ground_state_evidence", {
            "stationary": status == "ok", "finite_cell_status": "not_assessed",
            "infinite_lattice_status": "not_certified",
            "interpretation": "No finite-cell bound certificate is connected for this local-space route.",
            "scope": "Stationary finite variational reference only."})
        scopes.append("Energy is per primitive cell in the supplied Hamiltonian's energy units.")
        scopes.extend([evidence["interpretation"], evidence["scope"]])
        diagnostics.append({"kind": "stationarity", "satisfied": status == "ok",
                            "value": calculation.get("stationarity_max_norm",
                                     calculation.get("stationarity", {}).get("max_residual_norm"))})
        gap = calculation.get("finite_cell_bound_gap")
        diagnostics.append({"kind": "finite_cell_ground_state",
                            "satisfied": evidence["finite_cell_status"] == "bound_saturated",
                            "evidence": evidence})
        diagnostics.append({"kind": "global_ground_state", "satisfied": False,
                            "finite_cell_bound_gap": gap,
                            "note": "Only the recorded finite search was performed."})
        reason = ("This cell saturates its numerical bound; compare larger or differently commensurate cells before extending the claim."
                  if evidence["finite_cell_status"] == "bound_saturated" else
                  "Diagnose the bound, energy normalization and local constraints before further physical claims."
                  if evidence["finite_cell_status"] == "inconsistent_bound" else
                  "Use independent starts and appropriate cells; an unsaturated relaxed LT bound alone does not prove that this state is wrong.")
        suggestions.append({"type": "calculate", "task": task,
                            "reason": reason,
                            "requires_agent_choice": True})
    if task == "spin_wave_spectrum" and calculation:
        diagnostics.append({"kind": "harmonic_stability", "satisfied": status == "ok",
                            "details": calculation.get("stability", calculation.get("diagnostics"))})
        suggestions.append({"type": "calculate", "task": "classical_ground_state" if status != "ok" else task,
                            "reason": "Refine the reference if unstable; otherwise increase q sampling for broader claims.",
                            "requires_agent_choice": True})
    if task in {"classical_monte_carlo", "classical_finite_size"} and calculation:
        grids = [calculation.get("grid", [])] if task == "classical_monte_carlo" else [
            size["grid"] for size in calculation.get("sizes", [])]
        warning = any(row.get("effective_sample_warning", True) for grid in grids for row in grid)
        scientific = "inconclusive"  # existing MC explicitly does not verify equilibration
        diagnostics.extend([{"kind": "effective_samples", "satisfied": not warning},
                            {"kind": "equilibration", "satisfied": False,
                             "note": "Statistics alone do not certify equilibration."}])
        suggestions.append({"type": "calculate", "task": task,
                            "reason": "Compare independent seeds and longer burn-in/sampling; inspect finite-size effects.",
                            "requires_agent_choice": True})
    if task == "quantum_low_energy" and calculation:
        from research.contracts import validate_observables_block
        sector = calculation.get("sector", {})
        residuals = calculation.get("residual_norms") or []
        diagnostics.append({"kind": "ed_convergence", "satisfied": status == "ok",
                            "max_residual_norm": max(residuals) if residuals else None,
                            "orthogonality_error": calculation.get("eigenvector_orthogonality_error")})
        diagnostics.append({"kind": "sector_resolution",
                            "satisfied": bool(sector),
                            "details": {key: sector.get(key) for key in
                                        ("basis_kind", "sz_total", "momentum",
                                         "sector_dimension", "hilbert_dimension")}})
        scopes.append("Exact finite-cluster eigenpairs in the reported symmetry sector; "
                      "no thermodynamic-limit or infinite-lattice claim.")
        if calculation.get("observables"):
            validate_observables_block(calculation["observables"], backend="ed-sparse-sector")
            scopes.append("Observables follow observables/v1 on the primary-sector ground state.")
        suggestions.append({"type": "calculate", "task": task,
                            "reason": "Compare larger commensurate clusters or add compare_sectors "
                                      "for cross-sector gaps before extending claims.",
                            "requires_agent_choice": True})
    if task == "fourier_exchange_spectrum" and status == "ok":
        scientific = "diagnostic_only"
        scopes.append("Fourier/LT modes are diagnostic seeds; local constraints require a separate classical search.")
    if task == "dipolar_ewald" and calculation:
        comparison = calculation["cutoff_comparison"]
        threshold = settings.get("cutoff_tolerance")
        sufficient = threshold is not None and max(comparison["absolute_energy_change"],
                                                    comparison["max_moment_gradient_change"]) <= threshold
        scientific = "usable_within_scope" if sufficient else "inconclusive"
        diagnostics.append({"kind": "cutoff_comparison", "satisfied": sufficient,
                            "details": comparison, "requested_tolerance": threshold})
        scopes.append("Independent dipole geometry calculation; not added to a short-range Hamiltonian.")
    return {"schema_version": "research-result/v1", "result_id": inputs["result_id"],
            "model_id": inputs["model_id"], "task": task,
            "execution_status": "succeeded", "scientific_status": scientific,
            "capability": inputs["capability"], "code_identity": inputs["code_identity"],
            "reference_result": reference["result_id"] if reference else None,
            "settings": inputs["settings"], "calculation": calculation,
            "backend_result": raw, "diagnostics": diagnostics, "scientific_scope": scopes,
            "suggested_actions": suggestions,
            **({"blocker": raw["blocker"]} if raw.get("blocker") else {})}
