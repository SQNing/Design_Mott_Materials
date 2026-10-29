#!/usr/bin/env python3
"""Host experiment for a user-selected model; no product routing by model name."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import minimize
import spglib

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "scripts"))
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.contracts import code_identity

POINTS = {"P1": [1., .1, .1], "P2": [1., .6, .8],
          "P3": [1., .4, -.5], "P4": [1., .3, .05]}
S = .5  # A classical length convention, not a quantum ground-state calculation.
A = np.array([[np.sqrt(3)/2, 1.5, 0], [-np.sqrt(3)/2, 1.5, 0], [0, 0, 8.]])
POSITIONS = np.array([[0., 0., 0.], [1/3, 1/3, 0.]])
SHIFTS = {1: [[0, 0, 0], [-1, 0, 0], [0, -1, 0]],
          2: [[1, 0, 0], [0, 1, 0], [1, -1, 0]],
          3: [[-1, -1, 0], [1, -1, 0], [-1, 1, 0]]}


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, allow_nan=False)
    if path.exists():
        if json.loads(path.read_text()) != data:
            raise ValueError("Refuse to replace a different saved record: " + str(path))
    else:
        path.write_text(payload)


def model(couplings):
    d = spglib.get_symmetry_dataset((A, POSITIONS, [1, 1]), symprec=1e-8)
    ops = [{"operation_ref": "space:%02d" % i, "rotation": r.tolist(),
            "translation": t.tolist()} for i, (r, t) in enumerate(zip(d.rotations, d.translations))]
    terms = []
    geometry = []
    for shell in (1, 2, 3):
        for source in ([0, 1] if shell == 2 else [0]):
            target = source if shell == 2 else 1
            for index, shift in enumerate(SHIFTS[shell]):
                delta = (POSITIONS[target] + shift - POSITIONS[source]) @ A
                ref = "J%d:%d:%d" % (shell, source, index)
                terms.append({"term_ref": ref,
                    "cluster": [{"site": source, "translation": [0, 0, 0]},
                                {"site": target, "translation": shift}],
                    "operator_basis_ref": "spin",
                    "payload": {"kind": "bilinear_exchange_matrix",
                                "matrix": {"shape": [3, 3], "data": (np.eye(3)*couplings[shell-1]).tolist()}},
                    "coordinate_convention": "global_crystallographic",
                    "attach_to": {"kind": "explicit_cluster", "orientation": "explicit"}})
                geometry.append({"term_ref": ref, "shell": shell, "distance": float(np.linalg.norm(delta)),
                                 "source": source, "target": target, "shift": shift})
    assert len(terms) == 12 and len(ops) == 24
    for shell, distance in [(1, 1.), (2, np.sqrt(3)), (3, 2.)]:
        assert all(abs(b["distance"]-distance) < 1e-12 for b in geometry if b["shell"] == shell)
        degrees = [0, 0]
        for b in geometry:
            if b["shell"] == shell:
                degrees[b["source"]] += 1
                degrees[b["target"]] += 1
        assert degrees == ([6, 6] if shell == 2 else [3, 3])
    data = {"schema_version": "lattice-term-contract/v1",
        "local_hilbert": {"operator_bases": {"spin": {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}},
                          "classical_spaces": {"sphere": {"kind": "unit_vector_sphere", "dimension": 3}}},
        "lattice_structure": {"lattice_vectors": A.tolist(),
            "basis_sites": [{"site_ref": "site:%d" % i, "position": p.tolist()} for i,p in enumerate(POSITIONS)],
            "bond_orbits": []},
        "symmetry": {"source": {"international_symbol": str(d.international), "number": int(d.number)},
                     "operations": ops, "unresolved": []},
        "parameters": {}, "term_attachments": {"site_terms": [], "bond_terms": terms,
            "higher_body_terms": [], "term_sets": []},
        "units": {"energy": "J1 with J1=+1; each undirected bond counted once", "hbar": 1}}
    return data, geometry


def independent_fourier(couplings):
    """2x2 scalar exchange matrix, independently derived from the three shells.

    This host cross-check is not a product solver or a literature answer.
    Continuous minimization is numerical, not an interval-certified global proof.
    """
    def energy(q):
        q = np.asarray(q)
        diagonal = 2*couplings[1]*np.cos(2*np.pi*q @ np.array(SHIFTS[2])[:, :2].T).sum(-1)
        off = (couplings[0]*np.exp(2j*np.pi*q @ np.array(SHIFTS[1])[:, :2].T).sum(-1)
               +couplings[2]*np.exp(2j*np.pi*q @ np.array(SHIFTS[3])[:, :2].T).sum(-1))
        return (diagonal-np.abs(off))/2
    q = np.stack(np.meshgrid(np.arange(151)/150, np.arange(151)/150, indexing="ij"), -1).reshape(-1, 2)
    values = energy(q)
    low = np.argsort(values)[:24]
    solutions = [minimize(lambda x: energy(x), q[i], method="Nelder-Mead",
        options={"xatol": 1e-11, "fatol": 1e-13, "maxiter": 1500}) for i in low]
    best = min(solutions, key=lambda r: r.fun)
    finite = {}
    for L in [2, 4, 6, 8, 10, 12, 18, 24, 36]:
        grid = np.array(list(np.ndindex((L, L))))/L
        vals = energy(grid)
        idx = int(np.argmin(vals))
        finite[str(L)] = {"energy_per_site_unit_spin": float(vals[idx]), "q": grid[idx].tolist()}
    return {"q": (best.x % 1).tolist(), "energy_per_site_unit_spin": float(best.fun),
            "mesh": [151, 151], "local_refinements": 24, "optimizer_success": bool(best.success),
            "finite_cells": finite,
            "limitation": "Numerical continuum minimum; no certified global interval bound or uniqueness claim."}


def summarize_state(result, geom):
    calc = result["calculation"]
    if "spins" not in calc:
        return {"scientific_status": result["scientific_status"], "blocker": result.get("blocker")}
    shape = calc["supercell_shape"]
    n = np.array(calc["spins"])/calc["spin_length"]
    spins = n.reshape(tuple(shape)+(2, 3))
    correlations = {1: [], 2: [], 3: []}
    directional = {}
    for b in geom:
        left = spins[..., b["source"], :]
        right = np.roll(spins[..., b["target"], :], tuple(-v for v in b["shift"]), axis=(0, 1, 2))
        value = float(np.mean(np.sum(left*right, axis=-1)))
        correlations[b["shell"]].append(value)
        directional[b["term_ref"]] = value
    cells = np.array(list(np.ndindex(tuple(shape))))
    qgrid = cells/np.array(shape)
    amplitudes = np.einsum("qr,ras->qas", np.exp(-2j*np.pi*qgrid@cells.T), n.reshape(-1, 2, 3))
    powers = np.sum(np.abs(amplitudes)**2, axis=(1, 2))/(2*len(cells)**2)
    assert abs(float(powers.sum())-1) < 1e-9
    shells = [float(np.mean(correlations[k])) for k in (1, 2, 3)]
    templates = {"Neel": [-1, 1, -1], "zigzag-manifold": [1/3, -1/3, -1],
                 "stripy-manifold": [-1/3, -1/3, 1], "ferromagnet": [1, 1, 1]}
    distances = {k: float(np.max(np.abs(np.array(v)-shells))) for k,v in templates.items()}
    closest = min(distances, key=distances.get)
    tensor = np.linalg.eigvalsh(n.T@n/len(n))[::-1]
    return {"scientific_status": result["scientific_status"], "result_id": result["result_id"],
        "shape": shape, "sites": len(n), "seed": calc["seed"],
        "energy_per_site_unit_spin": calc["energy_per_cell"]/(2*S*S),
        "stationarity_max_norm": calc["stationarity_max_norm"],
        "finite_cell_bound_gap_per_site_unit_spin": calc["finite_cell_bound_gap"]/(2*S*S),
        "start_energies_per_site_unit_spin": [x["energy_per_cell"]/(2*S*S) for x in calc["starts"]],
        "shell_correlations": shells, "directional_correlations": directional,
        "spin_tensor_eigenvalues": tensor.tolist(), "collinear": bool(tensor[1] < 1e-6),
        "observed_family": closest if distances[closest] < 1e-5 else "modulated/noncollinear",
        "bravais_fourier_peaks": [{"q": qgrid[i].tolist(), "weight": float(powers[i])}
            for i in np.argsort(powers)[::-1] if powers[i] > 1e-5],
        "spins": n.tolist()}


def act(run, action):
    start = time.monotonic()
    result = execute_research_action(run, action, wait=True)
    print(json.dumps({"run": run.name, "action": action["action_id"],
        "seconds": round(time.monotonic()-start, 2), "status": result.get("scientific_status", result.get("status")),
        "blocker": result.get("blocker"), "validation": result.get("validation_status")}), flush=True)
    return result


def ground_settings(L, seed, starts=6):
    return {"supercell_shape": [L,L,1], "spin_length": S, "seed": seed,
            "starts": starts, "maxiter": 2000, "stationarity_tolerance": 1e-6}


def prepare(output):
    manifest = {"model": "honeycomb J1-J2-J3 isotropic Heisenberg",
        "user_request": "J1-J2-J3 honeycomb; classical ground states and competition at representative points",
        "coupling_points_selected_by_agent": POINTS,
        "conventions": {"positive_J": "antiferromagnetic", "bond_counting": "each undirected bond once",
            "classical_spin_length": S, "reported_energy": "E/(N S^2 J1)",
            "physical_dimension": 2, "third_vector": "noninteracting periodic stacking for the 3D data contract"},
        "code_identity": code_identity(), "study_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save(output/"manifest.json", manifest)
    for name, couplings in POINTS.items():
        data, geom = model(couplings)
        save(output/(name+"-model.json"), data)
        save(output/(name+"-geometry.json"), geom)
        source = ("Classical isotropic Heisenberg exchange on the honeycomb lattice through third neighbours. "
            "Positive J is antiferromagnetic, each undirected bond once, no field or anisotropy. "
            "Agent-selected representative couplings are J1=%g, J2=%g, J3=%g. " % tuple(couplings)
            +"The user requested representative-point ground-state competition, not a quantum phase diagram.")
        req = {"source": {"kind": "text", "text": source},
            "question": "Determine the finite-cell classical ground-state family and numerical robustness at "+name,
            "requested_tasks": ["classical_ground_state"],
            "budget": {"max_solver_runs": 28, "max_wall_time_seconds": 500, "max_memory_mb": 3072}}
        run = output/name
        prepare_research_task(req, run)
        view = execute_research_action(run, {"action_id": "host-model-interpretation", "type": "provide_input",
            "reason": "The host resolves the supplied model into explicit first, second and third neighbour bonds.",
            "model": data, "answers": {"user_confirmed": "classical isotropic model; representative-point competition",
                "agent_choices": "couplings, unit convention, geometry, full structural symmetry"}})
        print(json.dumps({"prepared": name, "status": view["model"]["status"],
                          "terms": view["model"].get("term_count"), "symmetry_operations": 24,
                          "blocker": view["model"].get("blocker")}), flush=True)
        if view["model"]["status"] != "ready":
            raise RuntimeError("Model gate did not pass: " + name)
        save(output/(name+"-independent-fourier.json"), independent_fourier(couplings))


def baseline(output):
    for name in POINTS:
        run = output/name
        geom = json.loads((output/(name+"-geometry.json")).read_text())
        for L, seed, starts in [(4, 31, 6), (4, 97, 6), (6, 53, 6)] + ([(8, 71, 6), (12, 83, 6)] if name == "P4" else []):
            aid = "ground-L%d-seed%d" % (L, seed)
            result = act(run, {"action_id": aid, "type": "calculate", "task": "classical_ground_state",
                "reason": "Independent unconstrained starts, finite-cell LT bound and size checks.",
                "settings": ground_settings(L, seed, starts)})
            save(output/"observations"/(name+"-"+aid+".json"), summarize_state(result, geom))
        view = inspect_research_task(run)
        print(json.dumps({"baseline_complete": name, "solver_runs": view["solver_runs"]}), flush=True)


def competition(output):
    run = output/"P2"
    geom = json.loads((output/"P2-geometry.json").read_text())
    terms = json.loads((output/"P2-model.json").read_text())["term_attachments"]["bond_terms"]
    j2refs = [t["term_ref"] for t in terms if t["term_ref"].startswith("J2:")]
    j3refs = [t["term_ref"] for t in terms if t["term_ref"].startswith("J3:")]
    act(run, {"action_id": "drop-J3", "type": "propose_reduction",
        "reason": "Test whether third-neighbour exchange can be omitted at the full-model representative point.",
        "transformation": {"kind": "drop_terms", "term_refs": j3refs}})
    qpoints = [[0,0,0],[.125,0,0],[.125,.125,0],[.25,0,0]]
    matched = ground_settings(2, 19, 8)
    reduction = act(run, {"action_id": "validate-drop-J3", "type": "calculate", "task": "reduction_validation",
        "reason": "Measure energy, correlations and sampled harmonic consequences using matched controls.",
        "settings": {"candidate_id": "drop-J3", "experiments": [
            {"case_id": "reference", "task": "classical_ground_state", "settings": matched,
             "metrics": {"energy_per_cell": .01, "full_energy_penalty": .01, "spin_correlations": .05}},
            {"case_id": "modes", "task": "harmonic_spectrum", "reference_case": "reference",
             "settings": {"spin": S, "reduced_momenta": qpoints, "stability_tolerance": 1e-5},
             "metrics": {"spectrum": .01}}]}})
    save(output/"reduction-summary.json", {k: reduction.get(k) for k in
        ["scientific_status", "validation_status", "metrics", "scientific_scope", "blocker"]})
    points = [{"point_id": "control", "factors": {"J2": 1., "J3": 1.}}]
    for group in ("J2", "J3"):
        for word, factor in [("off",0.),("half",.5)]:
            factors = {"J2": 1., "J3": 1.}; factors[group] = factor
            points.append({"point_id": group+"-"+word, "factors": factors})
    act(run, {"action_id": "coupling-controls", "type": "propose_mechanism",
        "reason": "Vary complete symmetry-related shells separately, holding the other shell fixed.",
        "question": "Are J2 or J3 negligible for the ground-state energy and selected state at P2?",
        "groups": [{"group_id":"J2","term_refs":j2refs,"description":"All six second-neighbour bonds per cell"},
                   {"group_id":"J3","term_refs":j3refs,"description":"All three third-neighbour bonds per cell"}],
        "points": points})
    result = act(run, {"action_id":"coupling-responses", "type":"calculate", "task":"mechanism_test",
        "reason":"Test energetic insensitivity and inspect direct versus relaxation response.",
        "settings":{"mechanism_id":"coupling-controls", "experiments":[
            {"case_id":"ground","task":"classical_ground_state","settings":ground_settings(6,53,8)}],
            "observables":[{"observable_id":"energy","case_id":"ground","kind":"energy_per_cell"}],
            "hypotheses":[{"hypothesis_id":g+"-negligible", "statement":g+" scaling changes energy by at most the declared tolerance.",
                "kind":"insensitive_response","group_id":g,"observable_id":"energy", "max_change":.01,
                "numerical_tolerance":1e-6} for g in ["J2","J3"]]}})
    save(output/"mechanism-summary.json", {k: result.get(k) for k in
        ["scientific_status","observations","hypotheses","energy_responses","scientific_scope","blocker"]})
    for evidence in result.get("evidence", []):
        sub = json.loads(Path(evidence["path"]).read_text())
        save(output/"observations"/("P2-intervention-"+evidence["role"]+".json"), summarize_state(sub, geom))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", choices=["prepare","baseline","competition"], required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    {"prepare":prepare,"baseline":baseline,"competition":competition}[args.phase](output)
    print("STUDY_PHASE_COMPLETE", args.phase, flush=True)


if __name__ == "__main__":
    main()
