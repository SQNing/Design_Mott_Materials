#!/usr/bin/env python3
"""Real interruption, honeycomb recovery and an unattainable LT-bound control."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from research.contracts import code_identity
from research.examples import _base, _term
from research.workflow import prepare_research_task, execute_research_action, inspect_research_task
from research.report import render_research_report
from research.state import read_json, write_json, process_identity


def request(model, question, runs=4):
    return {"model":model,"question":question,"requested_tasks":["classical_ground_state"],
        "budget":{"max_solver_runs":runs,"max_wall_time_seconds":240,"max_memory_mb":3072}}


def action(name, **settings):
    return {"action_id":name,"type":"calculate","task":"classical_ground_state",
        "reason":"Check the complete finite model and retain numerical evidence.",
        "settings":{"spin_length":.5,"supercell_shape":[12,12,1],"starts":6,
                    "maxiter":2000,"seed":83,"stationarity_tolerance":1e-6,**settings}}


def assess(run, result, claim, conclusion):
    return execute_research_action(run,{"action_id":"assessment","type":"assess","claim_level":claim,
        "reason":"State exactly what the saved numerical evidence supports.",
        "answer_status":"answered_within_scope","conclusion":conclusion,
        "scope":"The specified finite periodic cell and Hamiltonian.",
        "limitations":["No thermodynamic-limit ground-state claim.",
                       "Checkpoint accounting preserves any uncertainty in an interrupted duration."],
        "evidence":[{"result_id":result['result_id'],"path":"calculation.ground_state_evidence"}]})


def finish(run, result, output):
    before=inspect_research_task(run)
    report=render_research_report(run,output)
    after=inspect_research_task(run)
    assert before['solver_runs']==after['solver_runs'] and not after['active_actions']
    return {'solver_runs':after['solver_runs'],'compute_seconds':after['compute_seconds'],
        'answer_status':after['answer_status'],'ground_state_evidence':result['calculation']['ground_state_evidence'],
        'report':report['report']}


def wait_for(function):
    end=time.monotonic()+10
    while time.monotonic()<end:
        value=function()
        if value:return value
        time.sleep(.05)
    raise RuntimeError('The test worker did not reach its expected checkpoint.')


def interruption_case(output, model):
    run=output/'A-interruption'
    prepare_research_task(request(model,'Resume after an intentionally interrupted test worker.'),run)
    interrupted=action('interrupted',starts=100,seed=89)
    view=inspect_research_task(run)
    if not any(s['action_id']=='interrupted' for s in view['steps']):
        execute_research_action(run,interrupted)
    view=inspect_research_task(run)
    step=next(s for s in view['steps'] if s['action_id']=='interrupted')
    if step['execution']['status'] in {'running','pending'}:
        directory=run/'steps/interrupted'
        def checkpoint():
            if not (directory/'timing.json').exists() or not (directory/'computation.json').exists():return None
            value=read_json(directory/'timing.json')
            return value if value['elapsed_seconds']>=.6 else None
        timing=wait_for(checkpoint)
        supervisor=step['execution']['worker']
        child=read_json(directory/'computation.json')['worker']
        assert process_identity(supervisor['pid'])==supervisor
        assert process_identity(child['pid'])==child
        # Both groups belong to the workers just created by this acceptance.
        os.killpg(supervisor['pid'],signal.SIGKILL)
        if process_identity(child['pid'])==child:os.killpg(child['pid'],signal.SIGKILL)
        write_json(output/'A-interruption-injection.json',{'supervisor':supervisor,'child':child,'checkpoint':timing},exclusive=True)
        wait_for(lambda: process_identity(supervisor['pid']) is None and process_identity(child['pid']) is None)
    first=inspect_research_task(run)
    stopped=next(s for s in first['steps'] if s['action_id']=='interrupted')
    assert stopped['execution']['status']=='interrupted' and stopped['result'] is None
    time.sleep(.35)
    second=inspect_research_task(run)
    assert first['compute_seconds']==second['compute_seconds']
    assert stopped['execution']['time_accounting']['uncertain']
    result=execute_research_action(run,action('resumed',supercell_shape=[4,4,1],starts=2,seed=31),wait=True)
    assert result['scientific_status']=='usable_within_scope',result
    assess(run,result,'finite_cell_ground_state','The resumed calculation attains its finite-cell numerical bound; the interrupted record is retained.')
    summary=finish(run,result,output/'A-report')
    summary['interrupted_charge_before']=first['compute_seconds']
    summary['interrupted_charge_after_idle']=second['compute_seconds']
    summary['interrupted_accounting']=stopped['execution']['time_accounting']
    print('A interruption and resume complete',flush=True)
    return summary


def honeycomb_case(output, model):
    run=output/'B-honeycomb'
    prepare_research_task(request(model,'Recover and assess the original stationary 12x12 honeycomb search.'),run)
    result=execute_research_action(run,action('automatic-recovery'),wait=True)
    calc=result['calculation']
    assert result['scientific_status']=='usable_within_scope',result
    assert calc['initial_search']['finite_cell_bound_gap']>calc['ground_state_evidence']['comparison_tolerance_per_cell']
    assert calc['recovery']['attempted'] and calc['recovery']['accepted']
    assert calc['recovery']['additional_starts']==1
    assert calc['ground_state_evidence']['finite_cell_status']=='bound_saturated'
    assess(run,result,'finite_cell_ground_state','Automatic feasible-Fourier recovery reaches the finite-cell bound and retains the original stationary higher-energy state.')
    claim={'action_id':'invalid-thermodynamic-claim','type':'assess','claim_level':'thermodynamic_ground_state',
        'reason':'Check the finite-to-infinite claim boundary.','answer_status':'answered_within_scope',
        'conclusion':'The infinite-system ground state is known.','scope':'infinite',
        'limitations':['Only finite evidence exists.'],
        'evidence':[{'result_id':result['result_id'],'path':'calculation.ground_state_evidence'}]}
    try:execute_research_action(run,claim)
    except ValueError as exc:write_json(output/'B-rejected-claim.json',{'reason':str(exc)},exclusive=not (output/'B-rejected-claim.json').exists())
    else:raise AssertionError('A finite-cell result was promoted to an infinite-system claim.')
    summary=finish(run,result,output/'B-report')
    summary['initial_energy_per_cell']=calc['initial_search']['energy_per_cell']
    summary['final_energy_per_cell']=calc['energy_per_cell']
    summary['initial_gap']=calc['initial_search']['finite_cell_bound_gap']
    summary['final_gap']=calc['finite_cell_bound_gap']
    print('B original honeycomb search recovered',flush=True)
    return summary


def loose_bound_case(output):
    model=_base({'kind':'unit_vector_sphere','dimension':3},
                {'kind':'spin_vector','labels':['Sx','Sy','Sz']},
                [[0.,0.,0.],[.19,.23,.31],[.43,.11,.67]])
    for i,strength in enumerate([1.,-.1,-.15]):
        matrix=[[strength if a==b else 0. for b in range(3)] for a in range(3)]
        model['term_attachments']['bond_terms'].append(_term('chain:%d'%i,[i,i],[[0,0,0],[1,0,0]],'bilinear_exchange_matrix',matrix))
    run=output/'C-loose-bound'
    prepare_research_task(request(model,'Distinguish an unattainable relaxed LT bound from a failed stationary search.'),run)
    result=execute_research_action(run,action('reference',supercell_shape=[2,1,1],starts=3,seed=7),wait=True)
    calc=result['calculation']
    assert result['scientific_status']=='usable_within_scope',result
    assert abs(calc['energy_per_cell']+.3125)<1e-8
    assert calc['ground_state_evidence']['stationary']
    assert calc['ground_state_evidence']['finite_cell_status']=='not_certified'
    assert not calc['recovery']['attempted']
    claim={'action_id':'invalid-finite-claim','type':'assess','claim_level':'finite_cell_ground_state',
        'reason':'A stationary result alone must not become a bound certificate.',
        'answer_status':'answered_within_scope','conclusion':'Finite-cell certificate.','scope':'finite',
        'limitations':['The relaxed bound is not saturated.'],
        'evidence':[{'result_id':result['result_id'],'path':'calculation.ground_state_evidence'}]}
    try:execute_research_action(run,claim)
    except ValueError as exc:write_json(output/'C-rejected-claim.json',{'reason':str(exc)},exclusive=not (output/'C-rejected-claim.json').exists())
    else:raise AssertionError('An unsaturated loose bound was falsely certified.')
    assess(run,result,'stationary_reference','A stationary reference is usable; no tested lowest mode meets all local constraints, so finite-cell certification remains unavailable.')
    summary=finish(run,result,output/'C-report')
    summary['recovery']=calc['recovery']
    print('C unattainable LT bound remains uncertified',flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',required=True);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();output=Path(args.output_dir).resolve();output.mkdir(parents=True,exist_ok=args.resume)
    identity=code_identity()
    model_path=SCRIPTS.parent/'artifacts/honeycomb-j1j2j3-20261030-001/P4-model.json'
    model=read_json(model_path)
    summary={'code_identity':identity,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_model':str(model_path),'source_model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest()}
    summary['A']=interruption_case(output,model)
    summary['B']=honeycomb_case(output,model)
    summary['C']=loose_bound_case(output)
    assert code_identity()==identity
    summary['solver_attempts']=sum(summary[k]['solver_runs'] for k in ['A','B','C'])
    write_json(output/'summary.json',summary)
    print('RELIABILITY_ACCEPTANCE_COMPLETE',summary['solver_attempts'],flush=True)


if __name__=='__main__':main()
