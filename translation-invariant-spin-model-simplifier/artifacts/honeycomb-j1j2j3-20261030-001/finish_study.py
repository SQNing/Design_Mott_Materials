#!/usr/bin/env python3
"""Finite-size follow-ups, evidence assessment and compact export."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

import run_study as study
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.contracts import code_identity


def followups(output):
    for suffix, j3 in [("off", 0.), ("half", .4)]:
        name = "P2-J3-"+suffix+"-L36"
        couplings = [1., .6, j3]
        data, geom = study.model(couplings)
        scan = study.independent_fourier(couplings)
        study.save(output/(name+"-independent-fourier.json"), scan)
        request = {"model": data, "question": "Resolve finite-cell commensurability in the J3-"+suffix+" intervention.",
            "requested_tasks": ["classical_ground_state"],
            "budget": {"max_solver_runs": 2,"max_wall_time_seconds": 60,"max_memory_mb":3072}}
        run = output/name
        view = prepare_research_task(request, run)
        assert view["model"]["status"] == "ready", view["model"]
        L = 36
        q = np.array(scan["finite_cells"][str(L)]["q"])
        off = (couplings[0]*np.exp(2j*np.pi*np.array(study.SHIFTS[1])[:, :2]@q).sum()
               +couplings[2]*np.exp(2j*np.pi*np.array(study.SHIFTS[3])[:, :2]@q).sum())
        cells = np.array(list(np.ndindex((L,L,1))))
        phase = 2*np.pi*cells[:, :2]@q
        phase = np.stack([phase,phase+np.pi-np.angle(off)],-1).ravel()
        initial = study.S*np.stack([np.cos(phase),np.sin(phase),np.zeros_like(phase)],-1)
        settings = study.ground_settings(L, 137, 1)
        settings["initial_spins"] = initial.tolist()
        result = study.act(run, {"action_id":"fourier-seeded-L36", "type":"calculate", "task":"classical_ground_state",
            "reason":"Verify the larger commensurate cell from a model-derived LT seed; no presumed order is imposed.",
            "settings":settings})
        obs = study.summarize_state(result,geom)
        study.save(output/"observations"/(name+".json"),obs)
        study.save(output/(name+"-provenance.json"), {"parent_run":"P2", "mechanism_id":"coupling-controls",
            "point_id":"J3-"+suffix, "couplings":couplings,
            "reason":"The 8x8 cell undersamples a noncommensurate Fourier minimum.",
            "initial_state":"Equal-length single-q construction from this model's finite-cell 2x2 Fourier matrix"})

    # A stationary random search need not attain the finite-cell ground state.
    # Retain that result and verify a separate model-derived candidate.
    name="P4"; L=12; couplings=study.POINTS[name]
    scan=json.loads((output/(name+"-independent-fourier.json")).read_text())
    q=np.array(scan["finite_cells"][str(L)]["q"])
    off=(couplings[0]*np.exp(2j*np.pi*np.array(study.SHIFTS[1])[:, :2]@q).sum()
         +couplings[2]*np.exp(2j*np.pi*np.array(study.SHIFTS[3])[:, :2]@q).sum())
    cells=np.array(list(np.ndindex((L,L,1))))
    angle=2*np.pi*cells[:, :2]@q
    angle=np.stack([angle,angle+np.pi-np.angle(off)],-1).ravel()
    settings=study.ground_settings(L,149,1)
    settings["initial_spins"]=(study.S*np.stack([np.cos(angle),np.sin(angle),np.zeros_like(angle)],-1)).tolist()
    result=study.act(output/name,{"action_id":"fourier-seeded-L12","type":"calculate","task":"classical_ground_state",
        "reason":"The random L12 state is stationary but above the finite-cell bound; test a separately constructed equal-length LT state.",
        "settings":settings})
    geom=json.loads((output/(name+"-geometry.json")).read_text())
    study.save(output/"observations"/"P4-fourier-seeded-L12.json",study.summarize_state(result,geom))


def assessment(output, name):
    run = output/name
    view = inspect_research_task(run)
    if name in study.POINTS:
        evidence = [{"result_id":"ground-L6-seed53","path":"calculation.finite_cell_bound_gap"},
            {"result_id":"fourier-seeded-L36" if name == "P4" else "fourier-seeded-L2",
             "path":"calculation.energy_per_cell"}]
        conclusions = {
            "P1":"Independent random searches recover Neel order and saturate the finite-cell LT lower bound.",
            "P2":"Random searches find degenerate M-point multi-q states. A collinear zigzag member has the same energy. Removing J3 fails the declared approximation tests; isolated J2/J3 controls change the energy and correlations.",
            "P3":"Random searches find degenerate M-point multi-q states. A collinear stripy member has the same energy; uniqueness is not established.",
            "P4":"Random searches and a larger Fourier-seeded cell recover modulated states; the finite-cell LT bound is saturated. The ordering wavevector remains subject to commensurability."}
        conclusion = conclusions[name]
        if name == "P4":
            evidence.append({"result_id":"fourier-seeded-L12","path":"calculation.finite_cell_bound_gap"})
            conclusion += " The original L12 random search was stationary but above the cell bound; a separate Fourier-seeded L12 calculation closes that gap."
        if name == "P2":
            evidence.extend([{"result_id":"validate-drop-J3","path":"calculation.metrics"},
                             {"result_id":"coupling-responses","path":"calculation.hypotheses"}])
    else:
        evidence = [{"result_id":"fourier-seeded-L36","path":"calculation.finite_cell_bound_gap"}]
        conclusion = "A model-derived single-q state saturates the 36x36 finite-cell bound, resolving part of the 8x8 commensurability error."
    execute_research_action(run, {"action_id":"host-evidence-assessment-v2" if name == "P4" else "host-evidence-assessment", "type":"assess",
        "reason":"Interpret recorded computations and distinguish stationary states, finite-cell optima and degeneracy.",
        "answer_status":"answered_within_scope", "conclusion":conclusion,
        "scope":"Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.",
        "limitations":["No full parameter-space phase diagram or unique ordered state is claimed.",
            "No thermal or quantum fluctuation selection was computed.",
            "The continuous Fourier minimization is numerical and is not an interval-certified global proof.",
            "Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches."],
        "evidence":evidence})
    report = render_research_report(run,output/(name+"-report"))
    final = inspect_research_task(run)
    assert not final["active_actions"]
    return {"answer_status":final["answer_status"], "solver_runs":final["solver_runs"],
        "compute_seconds":final["compute_seconds"], "report":report["report"],
        "source_hash":next(s["result"]["code_identity"]["source_hash"] for s in final["steps"] if s.get("result") and s["result"].get("code_identity")),
        "steps":[{"id":s["action_id"],"status":s["result"]["scientific_status"]} for s in final["steps"] if s.get("result")]}


def export(output):
    summary = {"manifest":json.loads((output/"manifest.json").read_text()),
        "remote_root":str(output), "code_identity":code_identity(), "runs":{},"observations":{},"fourier":{}}
    for name in list(study.POINTS)+["P2-J3-off-L36","P2-J3-half-L36"]:
        summary["runs"][name] = assessment(output,name)
        summary["fourier"][name] = json.loads((output/(name+"-independent-fourier.json")).read_text())
    for p in sorted((output/"observations").glob("*.json")):
        d=json.loads(p.read_text())
        if "spins" in d:
            n=np.array(d.pop("spins")).reshape(tuple(d["shape"])+(2,3))
            side=min(d["shape"][0],4)
            crop=n[:side,:side]
            d["plot_shape"]=[side,side,1]
            d["plot_spins"]=crop.reshape(-1,3).tolist()
        assert d["scientific_status"] == "usable_within_scope", (p,d)
        assert d["finite_cell_bound_gap_per_site_unit_spin"] > -1e-6, (p,d)
        d["finite_cell_bound_saturated"] = abs(d["finite_cell_bound_gap_per_site_unit_spin"]) < 1e-6
        summary["observations"][p.stem]=d
    failures=[k for k,v in summary["observations"].items() if not v["finite_cell_bound_saturated"]]
    for key in failures:
        old=summary["observations"][key]
        point=key.split('-')[0]
        repair=point+'-fourier-seeded-L'+str(old['shape'][0])
        assert repair in summary["observations"], (key,'No verified replacement')
        replacement=summary["observations"][repair]
        assert replacement['shape']==old['shape'] and replacement['finite_cell_bound_saturated'],(key,repair)
        old['stationary_nonminimum']=True
        old['verified_replacement']=repair
    summary["reduction"] = json.loads((output/"reduction-summary.json").read_text())
    summary["mechanism"] = json.loads((output/"mechanism-summary.json").read_text())
    summary["total_solver_runs"]=sum(d["solver_runs"] for d in summary["runs"].values())
    summary["total_compute_seconds"]=sum(d["compute_seconds"] for d in summary["runs"].values())
    summary["verification"]={"all_saved_observations_usable":True,
        "stationary_nonminimum_observations":failures,
        "all_nonminimum_observations_have_verified_replacements":True,
        "max_abs_finite_cell_gap_per_site_unit_spin":max(abs(d["finite_cell_bound_gap_per_site_unit_spin"]) for d in summary["observations"].values()),
        "max_stationarity_residual":max(d["stationarity_max_norm"] for d in summary["observations"].values()),
        "observation_count":len(summary["observations"]),
        "notes":"Machine precision agreement is numerical evidence, not a rigorous interval-arithmetic certificate."}
    for p in sorted(output.glob("*-invocation.json")):
        summary.setdefault("invocations",{})[p.name]=json.loads(p.read_text())
    study.save(output/"summary.json",summary)
    print(json.dumps({"study_complete":True,"solver_runs":summary["total_solver_runs"],
        "compute_seconds":summary["total_compute_seconds"],"verification":summary["verification"]}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",required=True)
    args=parser.parse_args();output=Path(args.output).resolve()
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    study.save(output/("finish-"+source_hash[:12]+"-invocation.json"),{"script_sha256":source_hash,
        "code_identity":code_identity()})
    followups(output)
    export(output)


if __name__ == "__main__":
    main()
