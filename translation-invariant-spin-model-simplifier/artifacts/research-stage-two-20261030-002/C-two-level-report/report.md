# Research report

Does the selected two-level projection preserve the tested low-energy sector?

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d
- Full source term count: 2
- Solver term count: 2
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "complex_projective_space"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| onsite:levels | retained_onsite_operator (main) | [{"site": 0, "translation": [0, 0, 0]}] |
| pair:general | retained_pair_operator (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Proposed physical reductions

### candidate

- Transformation: project_local_space
- Preparation: ready
- Parent is current: True
- Complexity: {"candidate_dimension": 2, "candidate_terms": 2, "full_dimension": 3, "full_terms": 2}
- A prepared candidate is not yet a validated approximation.
[Candidate and operator mapping](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/reductions/candidate/record.json)

- Limitation: Direct subspace projection only; virtual-excitation corrections are not included.
- Limitation: The projection is not certified by a small coupling norm alone.

## validate

- Decision: Compare the proposed physical approximation with the full model.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/result.json)

- Simplification verdict: accepted_within_scope
- Candidate: candidate
- New solver calls: 4

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.0 | 0.03 | pass |  |
| reference | full_energy_penalty | 0.0 | 0.03 | pass |  |
| reference | projector_distance | 1.2982073187987827e-12 | 0.05 | pass |  |
| modes | spectrum | 0.0 | 0.03 | pass |  |

Tested scope:

```json
{
  "candidate_model_id": "d6e0d4ba30ba77b989c00f39976c3d4bd1f4975cc62d4df26adbe3cd03169e6a",
  "energy_offset_per_cell": 0.0,
  "energy_window_max": 2.0,
  "experiments": [
    {
      "case_id": "reference",
      "metrics": {
        "energy_per_cell": 0.03,
        "full_energy_penalty": 0.03,
        "projector_distance": 0.05
      },
      "settings": {
        "max_linear_size": 1,
        "max_sweeps": 100,
        "seed": 6,
        "starts": 2
      },
      "task": "classical_ground_state"
    },
    {
      "case_id": "modes",
      "metrics": {
        "spectrum": 0.03
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
        ]
      },
      "task": "spin_wave_spectrum"
    }
  ],
  "full_model_id": "8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d",
  "full_reference_tolerance": 1e-07,
  "realized_cases": [
    {
      "case_id": "reference",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "reference",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
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

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/reference-full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/reference-candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/modes-full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/modes-candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2b303fae0cf1ea17bb37a9397d2f2b795f7d7e8c0e3834a58aa4456da4f7af0c", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/reference-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2ec44d6030458d1848c3bdbcd764dbcbd7d62314a6c8660d478964877eefd9f3", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/reference-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d9840cf93e6bed950cd52257dbcb23c6fc0a6914e19d8d92cb520cf07c479376", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/modes-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d95667b60e52cf196ae3f8451f76ff69bdf52b2ef2eb28215b684ac820a421c4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/validate/evidence/modes-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## tighter

- Decision: Compare the proposed physical approximation with the full model.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/result.json)

- Simplification verdict: accepted_within_scope
- Candidate: candidate
- New solver calls: 0

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.0 | 0.01 | pass |  |
| reference | full_energy_penalty | 0.0 | 0.01 | pass |  |
| reference | projector_distance | 1.2982073187987827e-12 | 0.05 | pass |  |
| modes | spectrum | 0.0 | 0.01 | pass |  |

Tested scope:

```json
{
  "candidate_model_id": "d6e0d4ba30ba77b989c00f39976c3d4bd1f4975cc62d4df26adbe3cd03169e6a",
  "energy_offset_per_cell": 0.0,
  "energy_window_max": 2.0,
  "experiments": [
    {
      "case_id": "reference",
      "metrics": {
        "energy_per_cell": 0.01,
        "full_energy_penalty": 0.01,
        "projector_distance": 0.05
      },
      "settings": {
        "max_linear_size": 1,
        "max_sweeps": 100,
        "seed": 6,
        "starts": 2
      },
      "task": "classical_ground_state"
    },
    {
      "case_id": "modes",
      "metrics": {
        "spectrum": 0.01
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
        ]
      },
      "task": "spin_wave_spectrum"
    }
  ],
  "full_model_id": "8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d",
  "full_reference_tolerance": 1e-07,
  "realized_cases": [
    {
      "case_id": "reference",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "reference",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
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

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/reference-full.json), reused: True
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/reference-candidate.json), reused: True
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/modes-full.json), reused: True
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/modes-candidate.json), reused: True

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2b303fae0cf1ea17bb37a9397d2f2b795f7d7e8c0e3834a58aa4456da4f7af0c", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/reference-full.json", "reused": true, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2ec44d6030458d1848c3bdbcd764dbcbd7d62314a6c8660d478964877eefd9f3", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/reference-candidate.json", "reused": true, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d9840cf93e6bed950cd52257dbcb23c6fc0a6914e19d8d92cb520cf07c479376", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/modes-full.json", "reused": true, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d95667b60e52cf196ae3f8451f76ff69bdf52b2ef2eb28215b684ac820a421c4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/tighter/evidence/modes-candidate.json", "reused": true, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## wide-window

- Decision: Compare the proposed physical approximation with the full model.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/result.json)

- Simplification verdict: rejected
- Candidate: candidate
- New solver calls: 0

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.0 | 0.03 | pass |  |
| reference | full_energy_penalty | 0.0 | 0.03 | pass |  |
| reference | projector_distance | 1.2982073187987827e-12 | 0.05 | pass |  |
| modes | spectrum_mode_count | 1.0 | 0 | fail | Different numbers of modes in the requested energy window at q=[0.0, 0.0, 0.0] |

Tested scope:

```json
{
  "candidate_model_id": "d6e0d4ba30ba77b989c00f39976c3d4bd1f4975cc62d4df26adbe3cd03169e6a",
  "energy_offset_per_cell": 0.0,
  "energy_window_max": 20.0,
  "experiments": [
    {
      "case_id": "reference",
      "metrics": {
        "energy_per_cell": 0.03,
        "full_energy_penalty": 0.03,
        "projector_distance": 0.05
      },
      "settings": {
        "max_linear_size": 1,
        "max_sweeps": 100,
        "seed": 6,
        "starts": 2
      },
      "task": "classical_ground_state"
    },
    {
      "case_id": "modes",
      "metrics": {
        "spectrum": 0.03
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
        ]
      },
      "task": "spin_wave_spectrum"
    }
  ],
  "full_model_id": "8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d",
  "full_reference_tolerance": 1e-07,
  "realized_cases": [
    {
      "case_id": "reference",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "reference",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 3,
      "role": "full",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "modes",
      "local_dimension": 2,
      "role": "candidate",
      "spin": null,
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

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/reference-full.json), reused: True
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/reference-candidate.json), reused: True
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/modes-full.json), reused: True
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/modes-candidate.json), reused: True

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2b303fae0cf1ea17bb37a9397d2f2b795f7d7e8c0e3834a58aa4456da4f7af0c", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/reference-full.json", "reused": true, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2ec44d6030458d1848c3bdbcd764dbcbd7d62314a6c8660d478964877eefd9f3", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/reference-candidate.json", "reused": true, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d9840cf93e6bed950cd52257dbcb23c6fc0a6914e19d8d92cb520cf07c479376", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/modes-full.json", "reused": true, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d95667b60e52cf196ae3f8451f76ff69bdf52b2ef2eb28215b684ac820a421c4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/C-two-level/steps/wide-window/evidence/modes-candidate.json", "reused": true, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## Agent assessment

answered_within_scope: The selected local subspace meets the recorded low-energy tolerances; no conclusion applies above the tested window.

Scope: {'candidate_model_id': 'd6e0d4ba30ba77b989c00f39976c3d4bd1f4975cc62d4df26adbe3cd03169e6a', 'energy_offset_per_cell': 0.0, 'energy_window_max': 2.0, 'experiments': [{'case_id': 'reference', 'metrics': {'energy_per_cell': 0.03, 'full_energy_penalty': 0.03, 'projector_distance': 0.05}, 'settings': {'max_linear_size': 1, 'max_sweeps': 100, 'seed': 6, 'starts': 2}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'metrics': {'spectrum': 0.03}, 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]]}, 'task': 'spin_wave_spectrum'}], 'full_model_id': '8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d', 'full_reference_tolerance': 1e-07, 'realized_cases': [{'case_id': 'reference', 'local_dimension': 3, 'role': 'full', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': 2, 'role': 'candidate', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 3, 'role': 'full', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 2, 'role': 'candidate', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}]}

Limitations: ['Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.', 'Stationary variational states are not proofs of global or infinite-lattice ground states.', 'State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.', 'Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.']

Evidence: [{"path": "calculation.metrics", "result_id": "validate"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Refine inadequate controls or extend the tested cells, momenta and parameter points.
- Refine inadequate controls or extend the tested cells, momenta and parameter points.
- Refine inadequate controls or extend the tested cells, momenta and parameter points.
