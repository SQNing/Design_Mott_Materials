# Research report

Can the explicitly selected interaction be neglected for these observables?

- Answer status: answered_within_scope
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| small | bilinear_exchange_tensor (residual) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Proposed physical reductions

### drop

- Transformation: drop_terms
- Preparation: ready
- Parent is current: True
- Complexity: {"candidate_dimension": null, "candidate_terms": 3, "full_dimension": null, "full_terms": 4}
- A prepared candidate is not yet a validated approximation.
[Candidate and operator mapping](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/reductions/drop/record.json)

- Limitation: Coefficient norms alone do not bound the requested observables.

## validate

- Decision: Check energy, correlations and harmonic excitations in the same finite cell.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/result.json)

- Simplification verdict: rejected
- Candidate: drop
- New solver calls: 4

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.004999999999999782 | 0.01 | pass |  |
| reference | full_energy_penalty | 0.000744743129729053 | 0.01 | pass |  |
| reference | spin_correlations | 2.220446049250313e-16 | 0.01 | pass |  |
| modes | spectrum | 0.019999999999999907 | 0.005 | fail |  |

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
  "full_model_id": "ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf",
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

- [reference / full](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/reference-full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/reference-candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/modes-full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/modes-candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "e66a23b2120fe0a105b03c160374f9a2754d4741a55331717f3a1ec72b028b40", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/reference-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "8d5948c4a2bc6344e48347fe99ccba65ac3c8f2f8c3b21f02ff05dab1fe74196", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/reference-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "c26ce040b95b0b4e64a90f1a2b2b78325cb3f81c03cb8274d118fecd72004918", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/modes-full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "265ad13a1f239213766374a81b2070ecdbae93e43ec8f4db3ad76e8892cdf258", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/B-small-anisotropy/steps/validate/evidence/modes-candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## Agent assessment

answered_within_scope: The candidate fails the specified tolerances for the recorded finite observables.

Scope: {'candidate_model_id': '7eab83330e09dd4aa9cdd0d986f3434aa0ac315f9432130637d0f18bde96d831', 'energy_offset_per_cell': 0.0, 'energy_window_max': None, 'experiments': [{'case_id': 'reference', 'metrics': {'energy_per_cell': 0.01, 'full_energy_penalty': 0.01, 'spin_correlations': 0.01}, 'settings': {'seed': 18, 'spin_length': 0.5, 'starts': 3, 'supercell_shape': [1, 1, 1]}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'metrics': {'spectrum': 0.005}, 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]], 'spin': 0.5}, 'task': 'spin_wave_spectrum'}], 'full_model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'full_reference_tolerance': 1e-07, 'realized_cases': [{'case_id': 'reference', 'local_dimension': None, 'role': 'full', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'role': 'candidate', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'role': 'full', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'role': 'candidate', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}]}

Limitations: ['Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.', 'Stationary variational states are not proofs of global or infinite-lattice ground states.', 'State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.', 'Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.']

Evidence: [{"path": "calculation.metrics", "result_id": "validate"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Refine inadequate controls or extend the tested cells, momenta and parameter points.
