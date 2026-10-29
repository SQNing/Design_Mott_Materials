# Research report

Resume the same mechanism experiment.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/models/model-0001/readable.json)

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
[Intervention plan and complete models](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/mechanisms/couplings/record.json)

- anisotropy: Uniaxial exchange anisotropy. Terms: small

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"anisotropy": 1.0} | ready |
| anisotropy-off | {"anisotropy": 0.0} | ready |
| anisotropy-half | {"anisotropy": 0.5} | ready |

## persistent

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/result.json)

- Mechanism study: couplings
- New solver calls: 6

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| anisotropy-response | supported_within_scope | All sampled isolated increments follow the proposed direction and the span exceeds the threshold. |
| anisotropy-necessary | supported_within_scope | The phenomenon is present in the full-model control and disappears under the isolated removal. |

### anisotropy-response

Claim: Anisotropy raises the sampled frequency.

Within the recorded finite model, varying group 'anisotropy' over [0.0, 0.5, 1.0] gives observable 'frequency' values [-3.329251562e-16, 0.01, 0.02]. All sampled isolated increments follow the proposed direction and the span exceeds the threshold.

Excluded confounded points: 

- [anisotropy-off, factor 0.0](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/anisotropy-off.json): value -3.3292515621207596e-16; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [anisotropy-half, factor 0.5](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/anisotropy-half.json): value 0.009999999999999787; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### anisotropy-necessary

Claim: Anisotropy is necessary for this finite frequency.

Within the recorded finite model, varying group 'anisotropy' over [0.0, 1.0] gives observable 'frequency' values [-3.329251562e-16, 0.02]. The phenomenon is present in the full-model control and disappears under the isolated removal.

Excluded confounded points: 

- [anisotropy-off, factor 0.0](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/anisotropy-off.json): value -3.3292515621207596e-16; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | control | 0.019999999999999574 | usable_within_scope |
| frequency | anisotropy-off | -3.3292515621207596e-16 | usable_within_scope |
| frequency | anisotropy-half | 0.009999999999999787 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| reference / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| reference / anisotropy-off | 0.0050000000000000044 | -2.220446049250313e-16 | 0.004999999999999782 | usable_within_scope |
| reference / anisotropy-half | 0.0024999999999999467 | 0.0 | 0.0024999999999999467 | usable_within_scope |

Tested scope:

```json
{
  "baseline_point_id": "control",
  "experiments": [
    {
      "case_id": "reference",
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
      "band_index": 0,
      "case_id": "modes",
      "kind": "harmonic_frequency",
      "observable_id": "frequency",
      "q": [
        0,
        0,
        0
      ]
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
      "case_id": "reference",
      "local_dimension": null,
      "point_id": "control",
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
      "point_id": "anisotropy-off",
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
      "point_id": "anisotropy-half",
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
      "point_id": "control",
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
      "point_id": "anisotropy-off",
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
      "point_id": "anisotropy-half",
      "spin": 0.5,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
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

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "836043a70e66e80aeed237ec0f05b2b87c1d3a46483730586da537482b160ee4", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/reference/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "c0dc131b37f17a3e4ff29784a51d295175447a00d96d9274e03ecaba70ad476a", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/reference/anisotropy-off.json", "reused": false, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "99237db5788ea70fcb0c2b79f62880808b9214b9b4be1868f518cf92606ca40d", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/reference/anisotropy-half.json", "reused": false, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "a7eeba6262f86d2b94850df047cc9baad078b18b42dbed1a59523b262d462a45", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "deb8fef24ad34445c5b513816b8dc911b71716f4c0989ba75157b12483c993ee", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/anisotropy-off.json", "reused": false, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "c2605d0d78cb74adb1ad93ffbb6db6c749ed227998bacc6467f85d253eec8260", "path": "/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/E-resume/steps/persistent/evidence/modes/anisotropy-half.json", "reused": false, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## Agent assessment

answered_within_scope: Another host process recovered the same mechanism result without repeating numerical jobs.

Scope: {'baseline_point_id': 'control', 'experiments': [{'case_id': 'reference', 'settings': {'seed': 18, 'spin_length': 0.5, 'starts': 3, 'supercell_shape': [1, 1, 1]}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]], 'spin': 0.5}, 'task': 'spin_wave_spectrum'}], 'full_model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'groups': [{'description': 'Uniaxial exchange anisotropy.', 'group_id': 'anisotropy', 'term_refs': ['small']}], 'local_basis_labels': [], 'mechanism_id': 'couplings', 'observables': [{'band_index': 0, 'case_id': 'modes', 'kind': 'harmonic_frequency', 'observable_id': 'frequency', 'q': [0, 0, 0]}], 'points': [{'factors': {'anisotropy': 1.0}, 'model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'point_id': 'control'}, {'factors': {'anisotropy': 0.0}, 'model_id': '08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6', 'point_id': 'anisotropy-off'}, {'factors': {'anisotropy': 0.5}, 'model_id': '40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c', 'point_id': 'anisotropy-half'}], 'realized_cases': [{'case_id': 'reference', 'local_dimension': None, 'point_id': 'control', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'anisotropy-off', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'anisotropy-half', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'control', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'anisotropy-off', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'anisotropy-half', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}], 'reference_tolerance': 1e-07, 'units': {'energy': 'dimensionless model units', 'hbar': 1}}

Limitations: ['Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.', 'Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.', 'Stationary finite classical states are not proofs of unique global or infinite-system ground states.', 'Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.', 'Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.', 'Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.', "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]

Evidence: [{"path": "calculation.hypotheses", "result_id": "persistent"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
