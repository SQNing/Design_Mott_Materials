# Research report

Resume the same full/candidate comparison from another host process.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| small | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Proposed physical reductions

### drop

- Transformation: drop_terms
- Preparation: ready
- Parent is current: True
- Complexity: {"candidate_dimension": null, "candidate_terms": 3, "full_dimension": null, "full_terms": 4}
- A prepared candidate is not yet a validated approximation.
[Candidate and operator mapping](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/reductions/drop/record.json)

- Limitation: Coefficient norms alone do not bound the requested observables.

## persistent

- Decision: Check energy, correlations and harmonic excitations in the same finite cell.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/result.json)

- Simplification verdict: accepted_within_scope
- Candidate: drop
- New solver calls: 4

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.00024999999999997247 | 0.01 | pass |  |
| reference | full_energy_penalty | 0.0 | 0.01 | pass |  |
| reference | spin_correlations | 0.0 | 0.01 | pass |  |
| modes | spectrum | 0.001000000000000445 | 0.005 | pass |  |

Tested scope:

```json
{
  "candidate_model_id": "7eab83330e09dd4aa9cdd0d986f3434aa0ac315f9432130637d0f18bde96d831",
  "energy_offset_per_cell": 0.0,
  "energy_window_max": null,
  "experiments": [
    {
      "case_id": "reference",
      "metrics": {
        "energy_per_cell": 0.01,
        "full_energy_penalty": 0.01,
        "spin_correlations": 0.01
      },
      "settings": {
        "seed": 18,
        "spin_length": 0.5,
        "starts": 3,
        "supercell_shape": [
          1,
          1,
          1
        ]
      },
      "task": "classical_ground_state"
    },
    {
      "case_id": "modes",
      "metrics": {
        "spectrum": 0.005
      },
      "reference_case": "reference",
      "settings": {
        "reduced_momenta": [
          [
            0,
            0,
            0
          ],
          [
            0.25,
            0,
            0
          ]
        ],
        "spin": 0.5
      },
      "task": "spin_wave_spectrum"
    }
  ],
  "full_model_id": "ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa",
  "full_reference_tolerance": 1e-07,
  "realized_cases": [
    {
      "case_id": "reference",
      "local_dimension": null,
      "role": "full",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "reference",
      "local_dimension": null,
      "role": "candidate",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": null,
      "role": "full",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": null,
      "role": "candidate",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    }
  ]
}
```

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/reference-full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/reference-candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/modes-full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/modes-candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "c4b5357ec3ddad7d34f71ff32f26a3757efccf54203fd72bc398156c5f2789b8", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/reference-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "8d5948c4a2bc6344e48347fe99ccba65ac3c8f2f8c3b21f02ff05dab1fe74196", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/reference-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "62a2fb41a95796ca6d077c83e64ad6d38be9cbcb63bf848d25b5afcb3863cc15", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/modes-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "265ad13a1f239213766374a81b2070ecdbae93e43ec8f4db3ad76e8892cdf258", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/E-resume/steps/persistent/evidence/modes-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## Agent assessment

answered_within_scope: The same finite comparison was recovered without extra solver calls.

Scope: {'candidate_model_id': '7eab83330e09dd4aa9cdd0d986f3434aa0ac315f9432130637d0f18bde96d831', 'energy_offset_per_cell': 0.0, 'energy_window_max': None, 'experiments': [{'case_id': 'reference', 'metrics': {'energy_per_cell': 0.01, 'full_energy_penalty': 0.01, 'spin_correlations': 0.01}, 'settings': {'seed': 18, 'spin_length': 0.5, 'starts': 3, 'supercell_shape': [1, 1, 1]}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'metrics': {'spectrum': 0.005}, 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]], 'spin': 0.5}, 'task': 'spin_wave_spectrum'}], 'full_model_id': 'ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa', 'full_reference_tolerance': 1e-07, 'realized_cases': [{'case_id': 'reference', 'local_dimension': None, 'role': 'full', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'role': 'candidate', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'role': 'full', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'role': 'candidate', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}]}

Limitations: ['Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.', 'Stationary variational states are not proofs of global or infinite-lattice ground states.', 'State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.', 'Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.']

Evidence: [{"path": "calculation.metrics", "result_id": "persistent"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Refine inadequate controls or extend the tested cells, momenta and parameter points.
