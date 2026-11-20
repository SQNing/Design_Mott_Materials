# Research report

Test a specified finite-cluster level spacing.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| small | bilinear_exchange_tensor (residual) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Mechanism studies

### couplings

Which interaction controls the frequency at the selected momentum?

- Preparation: ready
- Parent is current: True
- Full-model control: control
[Intervention plan and complete models](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/mechanisms/couplings/record.json)

- anisotropy: Uniaxial exchange anisotropy. Terms: small

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"anisotropy": 1.0} | ready |
| anisotropy-off | {"anisotropy": 0.0} | ready |
| anisotropy-half | {"anisotropy": 0.5} | ready |

## response

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/result.json)

- Mechanism study: couplings
- New solver calls: 3

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| anisotropy-response | supported_within_scope | All sampled isolated increments follow the proposed direction and the span exceeds the threshold. |

### anisotropy-response

Claim: Anisotropy raises the sampled frequency.

Within the recorded finite model, varying group 'anisotropy' over [0.0, 0.5, 1.0] gives observable 'frequency' values [8.881784197e-16, 0.01, 0.02]. All sampled isolated increments follow the proposed direction and the span exceeds the threshold.

Excluded confounded points: 

- [anisotropy-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/anisotropy-off.json): value 8.881784197001252e-16; selector {"case_id": "levels", "kind": "quantum_gap", "level": 2, "observable_id": "frequency"}
- [anisotropy-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/anisotropy-half.json): value 0.009999999999999787; selector {"case_id": "levels", "kind": "quantum_gap", "level": 2, "observable_id": "frequency"}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/control.json): value 0.02000000000000135; selector {"case_id": "levels", "kind": "quantum_gap", "level": 2, "observable_id": "frequency"}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | control | 0.02000000000000135 | usable_within_scope |
| frequency | anisotropy-off | 8.881784197001252e-16 | usable_within_scope |
| frequency | anisotropy-half | 0.009999999999999787 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |

Tested scope:

```json
{
  "baseline_point_id": "control",
  "experiments": [
    {
      "case_id": "levels",
      "settings": {
        "eigenvalues": 3,
        "seed": 31,
        "spin": 0.5,
        "supercell_shape": [
          2,
          2,
          2
        ]
      },
      "task": "quantum_low_energy"
    }
  ],
  "full_model_id": "ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf",
  "groups": [
    {
      "description": "Uniaxial exchange anisotropy.",
      "group_id": "anisotropy",
      "term_refs": [
        "small"
      ]
    }
  ],
  "local_basis_labels": [],
  "mechanism_id": "couplings",
  "observables": [
    {
      "case_id": "levels",
      "kind": "quantum_gap",
      "level": 2,
      "observable_id": "frequency"
    }
  ],
  "points": [
    {
      "factors": {
        "anisotropy": 1.0
      },
      "model_id": "ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf",
      "point_id": "control"
    },
    {
      "factors": {
        "anisotropy": 0.0
      },
      "model_id": "08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6",
      "point_id": "anisotropy-off"
    },
    {
      "factors": {
        "anisotropy": 0.5
      },
      "model_id": "40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c",
      "point_id": "anisotropy-half"
    }
  ],
  "realized_cases": [
    {
      "case_id": "levels",
      "local_dimension": null,
      "point_id": "control",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        2,
        2,
        2
      ]
    },
    {
      "case_id": "levels",
      "local_dimension": null,
      "point_id": "anisotropy-off",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        2,
        2,
        2
      ]
    },
    {
      "case_id": "levels",
      "local_dimension": null,
      "point_id": "anisotropy-half",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        2,
        2,
        2
      ]
    }
  ],
  "reference_tolerance": 1e-07,
  "units": {
    "energy": "dimensionless model units",
    "hbar": 1
  }
}
```

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "levels", "job_fingerprint": "c9b72911abfe8ff92789f7b70b6e3886da82a94cd1a2133c7f0d91b6c8633c8d", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "levels", "job_fingerprint": "7148604ba19e7928eba1feed3dbd2a253a51458666e5bd6f26f5c306b373e505", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/anisotropy-off.json", "reused": false, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "levels", "job_fingerprint": "e603ff1f5f3b4e6522cd32ae67e9e8c1e1a07e62c8bb43a66ee64bbbb3476315", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/C-finite-quantum/steps/response/evidence/levels/anisotropy-half.json", "reused": false, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## Agent assessment

answered_within_scope: The explicitly selected finite-cluster level spacing increases over the sampled anisotropy factors.

Scope: {'baseline_point_id': 'control', 'experiments': [{'case_id': 'levels', 'settings': {'eigenvalues': 3, 'seed': 31, 'spin': 0.5, 'supercell_shape': [2, 2, 2]}, 'task': 'quantum_low_energy'}], 'full_model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'groups': [{'description': 'Uniaxial exchange anisotropy.', 'group_id': 'anisotropy', 'term_refs': ['small']}], 'local_basis_labels': [], 'mechanism_id': 'couplings', 'observables': [{'case_id': 'levels', 'kind': 'quantum_gap', 'level': 2, 'observable_id': 'frequency'}], 'points': [{'factors': {'anisotropy': 1.0}, 'model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'point_id': 'control'}, {'factors': {'anisotropy': 0.0}, 'model_id': '08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6', 'point_id': 'anisotropy-off'}, {'factors': {'anisotropy': 0.5}, 'model_id': '40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c', 'point_id': 'anisotropy-half'}], 'realized_cases': [{'case_id': 'levels', 'local_dimension': None, 'point_id': 'control', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [2, 2, 2]}, {'case_id': 'levels', 'local_dimension': None, 'point_id': 'anisotropy-off', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [2, 2, 2]}, {'case_id': 'levels', 'local_dimension': None, 'point_id': 'anisotropy-half', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [2, 2, 2]}], 'reference_tolerance': 1e-07, 'units': {'energy': 'dimensionless model units', 'hbar': 1}}

Limitations: ['Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.', 'Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.', 'Stationary finite classical states are not proofs of unique global or infinite-system ground states.', 'Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.', 'Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.', 'Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.', "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]

Evidence: [{"path": "calculation.hypotheses", "result_id": "response"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
