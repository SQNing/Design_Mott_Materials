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

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/models/model-0001/readable.json)

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
[Candidate and operator mapping](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/reductions/candidate/record.json)

- Limitation: Direct subspace projection only; virtual-excitation corrections are not included.
- Limitation: The projection is not certified by a small coupling norm alone.

## validate

- Decision: Compare the proposed physical approximation with the full model.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/result.json)

- Simplification verdict: rejected
- Candidate: candidate
- New solver calls: 4

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 1.1099999999999999 | 0.03 | fail |  |
| reference | full_energy_penalty | 1.1099999999999999 | 0.03 | fail |  |
| reference | projector_distance | 1.4142135623730951 | 0.05 | fail |  |
| modes | spectrum_mode_count | 1.0 | 0 | fail | Different numbers of modes in the requested energy window at q=[0.0, 0.0, 0.0] |

Tested scope:

```json
{
  "candidate_model_id": "9c84e7d7af6a34534a16c15d7862dd4c3e4bf7b149d198b78568c21c90a3dee7",
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

- [reference / full](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/reference-full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/reference-candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/modes-full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/modes-candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2b303fae0cf1ea17bb37a9397d2f2b795f7d7e8c0e3834a58aa4456da4f7af0c", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/reference-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "2d6e05ec503a730efb103ac8d61890a4477da3e707c1ad5614b25b47f8bb8a8d", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/reference-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "d9840cf93e6bed950cd52257dbcb23c6fc0a6914e19d8d92cb520cf07c479376", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/modes-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "8f63ee72a4df5c8257fa8ea56acf4f1a8b9a2120937a0b1016048d519fd86a25", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/D-wrong-subspace/steps/validate/evidence/modes-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## Agent assessment

answered_within_scope: The selected local subspace fails the recorded low-energy tolerances; no conclusion applies above the tested window.

Scope: {'candidate_model_id': '9c84e7d7af6a34534a16c15d7862dd4c3e4bf7b149d198b78568c21c90a3dee7', 'energy_offset_per_cell': 0.0, 'energy_window_max': 2.0, 'experiments': [{'case_id': 'reference', 'metrics': {'energy_per_cell': 0.03, 'full_energy_penalty': 0.03, 'projector_distance': 0.05}, 'settings': {'max_linear_size': 1, 'max_sweeps': 100, 'seed': 6, 'starts': 2}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'metrics': {'spectrum': 0.03}, 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]]}, 'task': 'spin_wave_spectrum'}], 'full_model_id': '8fc12f64aaa15fbbd02da47ae5faa7b8ee58a0a5915eebe3f137a4dc4314c24d', 'full_reference_tolerance': 1e-07, 'realized_cases': [{'case_id': 'reference', 'local_dimension': 3, 'role': 'full', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': 2, 'role': 'candidate', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 3, 'role': 'full', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 2, 'role': 'candidate', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}]}

Limitations: ['Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.', 'Stationary variational states are not proofs of global or infinite-lattice ground states.', 'State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.', 'Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.']

Evidence: [{"path": "calculation.metrics", "result_id": "validate"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Refine inadequate controls or extend the tested cells, momenta and parameter points.
