# Research report

Can simultaneous changes identify either group's mechanism?

- Answer status: inconclusive
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/models/model-0001/readable.json)

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
[Intervention plan and complete models](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/mechanisms/couplings/record.json)

- anisotropy: Uniaxial exchange anisotropy. Terms: small
- exchange: The isotropic exchange background. Terms: exchange:0, exchange:1, exchange:2

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"anisotropy": 1.0, "exchange": 1.0} | ready |
| joint-half | {"anisotropy": 0.5, "exchange": 0.5} | ready |
| joint-quarter | {"anisotropy": 0.25, "exchange": 0.25} | ready |

## response

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: succeeded
- Scientific usability: inconclusive
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/result.json)

- Mechanism study: couplings
- New solver calls: 6

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| anisotropy-response | inconclusive | Insufficient isolated coupling points with all other groups fixed to the full-model control. |
| anisotropy-necessary | inconclusive | Necessity requires an isolated zero-factor intervention. |
| exchange-response | inconclusive | Insufficient isolated coupling points with all other groups fixed to the full-model control. |
| exchange-insensitive | inconclusive | Insufficient isolated coupling points with all other groups fixed to the full-model control. |

### anisotropy-response

Claim: Anisotropy raises the sampled frequency.

Insufficient isolated coupling points with all other groups fixed to the full-model control.

Excluded confounded points: joint-half, joint-quarter

- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### anisotropy-necessary

Claim: Anisotropy is necessary for this finite frequency.

Necessity requires an isolated zero-factor intervention.

Excluded confounded points: joint-half, joint-quarter

- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### exchange-response

Claim: Exchange raises the sampled frequency.

Insufficient isolated coupling points with all other groups fixed to the full-model control.

Excluded confounded points: joint-half, joint-quarter

- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### exchange-insensitive

Claim: This frequency is insensitive to exchange.

Insufficient isolated coupling points with all other groups fixed to the full-model control.

Excluded confounded points: joint-half, joint-quarter

- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | control | 0.019999999999999574 | usable_within_scope |
| frequency | joint-half | 0.010000000000000175 | usable_within_scope |
| frequency | joint-quarter | 0.004999999999999866 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| reference / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| reference / joint-half | 0.3775 | 0.0 | 0.3775 | usable_within_scope |
| reference / joint-quarter | 0.56625 | 0.0 | 0.56625 | usable_within_scope |

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
    },
    {
      "description": "The isotropic exchange background.",
      "group_id": "exchange",
      "term_refs": [
        "exchange:0",
        "exchange:1",
        "exchange:2"
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
        "anisotropy": 1.0,
        "exchange": 1.0
      },
      "model_id": "ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf",
      "point_id": "control"
    },
    {
      "factors": {
        "anisotropy": 0.5,
        "exchange": 0.5
      },
      "model_id": "ce00702ea0bf69227e27b9cf0b53be316ba5bc132dbb2588664510db9965ac04",
      "point_id": "joint-half"
    },
    {
      "factors": {
        "anisotropy": 0.25,
        "exchange": 0.25
      },
      "model_id": "76ba24b01ec84b62da3caa53513e39f01381a9610a695e03a339a70d67ea0f15",
      "point_id": "joint-quarter"
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
      "point_id": "joint-half",
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
      "point_id": "joint-quarter",
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
      "point_id": "joint-half",
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
      "point_id": "joint-quarter",
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

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "836043a70e66e80aeed237ec0f05b2b87c1d3a46483730586da537482b160ee4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/reference/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "4a0fc6b8a618ce283d52a1889a98d53d19ba5b6d264f616e04d4bfd31d44cf85", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/reference/joint-half.json", "reused": false, "role": "joint-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "9b148aca8a87e86ff55f06b9e8a6a9868390ee692b1c8445367e99d58c01e6be", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/reference/joint-quarter.json", "reused": false, "role": "joint-quarter", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "a7eeba6262f86d2b94850df047cc9baad078b18b42dbed1a59523b262d462a45", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "21f840afd5f0ecbd338f9fa4aa47d68a307d29436093c3f124953d33b60162aa", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/joint-half.json", "reused": false, "role": "joint-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "ed582a39ba7cdb861d5299e7b9dd584e0f6c50335d33c390530a1896117f3f85", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/D-confounded-controls/steps/response/evidence/modes/joint-quarter.json", "reused": false, "role": "joint-quarter", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## Agent assessment

inconclusive: The jointly varied points do not identify either one-group mechanism; isolated controls are needed.

Scope: {'baseline_point_id': 'control', 'experiments': [{'case_id': 'reference', 'settings': {'seed': 18, 'spin_length': 0.5, 'starts': 3, 'supercell_shape': [1, 1, 1]}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]], 'spin': 0.5}, 'task': 'spin_wave_spectrum'}], 'full_model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'groups': [{'description': 'Uniaxial exchange anisotropy.', 'group_id': 'anisotropy', 'term_refs': ['small']}, {'description': 'The isotropic exchange background.', 'group_id': 'exchange', 'term_refs': ['exchange:0', 'exchange:1', 'exchange:2']}], 'local_basis_labels': [], 'mechanism_id': 'couplings', 'observables': [{'band_index': 0, 'case_id': 'modes', 'kind': 'harmonic_frequency', 'observable_id': 'frequency', 'q': [0, 0, 0]}], 'points': [{'factors': {'anisotropy': 1.0, 'exchange': 1.0}, 'model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'point_id': 'control'}, {'factors': {'anisotropy': 0.5, 'exchange': 0.5}, 'model_id': 'ce00702ea0bf69227e27b9cf0b53be316ba5bc132dbb2588664510db9965ac04', 'point_id': 'joint-half'}, {'factors': {'anisotropy': 0.25, 'exchange': 0.25}, 'model_id': '76ba24b01ec84b62da3caa53513e39f01381a9610a695e03a339a70d67ea0f15', 'point_id': 'joint-quarter'}], 'realized_cases': [{'case_id': 'reference', 'local_dimension': None, 'point_id': 'control', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'joint-half', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'joint-quarter', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'control', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'joint-half', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'joint-quarter', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}], 'reference_tolerance': 1e-07, 'units': {'energy': 'dimensionless model units', 'hbar': 1}}

Limitations: ['Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.', 'Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.', 'Stationary finite classical states are not proofs of unique global or infinite-system ground states.', 'Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.', 'Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.', 'Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.', "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]

Evidence: [{"path": "calculation.hypotheses", "result_id": "response"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
