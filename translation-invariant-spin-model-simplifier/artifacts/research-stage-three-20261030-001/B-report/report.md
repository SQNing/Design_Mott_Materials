# Research report

Test onsite control without truncating any local levels.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f
- Full source term count: 2
- Solver term count: 2
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "complex_projective_space"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| onsite:levels | retained_onsite_operator (main) | [{"site": 0, "translation": [0, 0, 0]}] |
| pair:general | retained_pair_operator (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Mechanism studies

### levels

How do the local levels affect the sampled excitations and ground-state population?

- Preparation: ready
- Parent is current: True
- Full-model control: control
[Intervention plan and complete models](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/mechanisms/levels/record.json)

- onsite: All onsite matrix elements. Terms: onsite:levels

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| half | {"onsite": 0.5} | ready |
| control | {"onsite": 1.0} | ready |
| strong | {"onsite": 1.5} | ready |

## levels-response

- Decision: Compare full three-level references and harmonic modes.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/result.json)

- Mechanism study: levels
- New solver calls: 6

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| levels-raise-mode | supported_within_scope | All sampled isolated increments follow the proposed direction and the span exceeds the threshold. |
| population-preserved | supported_within_scope | All sampled isolated responses stay within the stated change bound. |

### levels-raise-mode

Claim: Stronger onsite splitting raises the selected mode.

Within the recorded finite model, varying group 'onsite' over [0.5, 1.0, 1.5] gives observable 'frequency' values [1.12, 1.52, 1.92]. All sampled isolated increments follow the proposed direction and the span exceeds the threshold.

Excluded confounded points: 

- [half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/half.json): value 1.1199999999999997; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/control.json): value 1.52; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [strong, factor 1.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/strong.json): value 1.9199999999999995; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### population-preserved

Claim: The selected local ground-level population remains unchanged.

Within the recorded finite model, varying group 'onsite' over [0.5, 1.0, 1.5] gives observable 'population' values [1.0, 1.0, 1.0]. All sampled isolated responses stay within the stated change bound.

Excluded confounded points: 

- [half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/half.json): value 1.0; selector {"basis_index": 0, "case_id": "rays", "kind": "local_population", "observable_id": "population"}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/control.json): value 1.0; selector {"basis_index": 0, "case_id": "rays", "kind": "local_population", "observable_id": "population"}
- [strong, factor 1.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/strong.json): value 1.0; selector {"basis_index": 0, "case_id": "rays", "kind": "local_population", "observable_id": "population"}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | half | 1.1199999999999997 | usable_within_scope |
| frequency | control | 1.52 | usable_within_scope |
| frequency | strong | 1.9199999999999995 | usable_within_scope |
| population | half | 1.0 | usable_within_scope |
| population | control | 1.0 | usable_within_scope |
| population | strong | 1.0 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| rays / half | 0.09999999999999998 | 0.0 | 0.09999999999999998 | usable_within_scope |
| rays / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| rays / strong | -0.10000000000000009 | 0.0 | -0.10000000000000009 | usable_within_scope |

Tested scope:

```json
{
  "baseline_point_id": "control",
  "experiments": [
    {
      "case_id": "rays",
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
      "reference_case": "rays",
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
  "full_model_id": "3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f",
  "groups": [
    {
      "description": "All onsite matrix elements.",
      "group_id": "onsite",
      "term_refs": [
        "onsite:levels"
      ]
    }
  ],
  "local_basis_labels": [
    "g",
    "e1",
    "e2"
  ],
  "mechanism_id": "levels",
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
    },
    {
      "basis_index": 0,
      "case_id": "rays",
      "kind": "local_population",
      "observable_id": "population"
    }
  ],
  "points": [
    {
      "factors": {
        "onsite": 0.5
      },
      "model_id": "d46b8eddc1e93902679a5a55cf9cc3fdeaf198f740f98f4e8ff11c78f26fadc2",
      "point_id": "half"
    },
    {
      "factors": {
        "onsite": 1.0
      },
      "model_id": "3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f",
      "point_id": "control"
    },
    {
      "factors": {
        "onsite": 1.5
      },
      "model_id": "4a4a73ad06f3fdc865fe7eca417e13818c60ae970641fb17fffc67842f13a3db",
      "point_id": "strong"
    }
  ],
  "realized_cases": [
    {
      "case_id": "rays",
      "local_dimension": 3,
      "point_id": "half",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "rays",
      "local_dimension": 3,
      "point_id": "control",
      "spin": null,
      "spin_length": null,
      "supercell_shape": [
        1,
        1,
        1
      ]
    },
    {
      "case_id": "rays",
      "local_dimension": 3,
      "point_id": "strong",
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
      "point_id": "half",
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
      "point_id": "control",
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
      "point_id": "strong",
      "spin": null,
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

- Diagnostic: {"blocker": null, "case_id": "rays", "job_fingerprint": "9fb8d5ff189c593f4b95a4e62453b84487d58f0871a815f6dee107b3e3224c6c", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/half.json", "reused": false, "role": "half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "rays", "job_fingerprint": "0dd13535f504dbe8bc76d46cdeb280a745c072a5c67536eea91ae07422e8e15a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "rays", "job_fingerprint": "aa51e92c2ae81e41a75f009928543a5ddee6b53dd9554061b36918c3b0951e5d", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/rays/strong.json", "reused": false, "role": "strong", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "b61006569631bc9939b3e515d357e6e4d592ddb53610cff13b6af2373463293a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/half.json", "reused": false, "role": "half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "b76f0d1015be4d0511af58e5efcf07338690bc73051f71a9ee8ac6d7ee3dc5e5", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "f893c84c1035f234373977c6a70128348777255c0dcbd704a6ff91c7be4c8c52", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/B-retained-levels/steps/levels-response/evidence/modes/strong.json", "reused": false, "role": "strong", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## Agent assessment

answered_within_scope: At the sampled points the selected onsite scaling raises the ordered harmonic frequency while the declared local ground-level population stays within tolerance; all three levels are retained.

Scope: {'baseline_point_id': 'control', 'experiments': [{'case_id': 'rays', 'settings': {'max_linear_size': 1, 'max_sweeps': 100, 'seed': 6, 'starts': 2}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'reference_case': 'rays', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]]}, 'task': 'spin_wave_spectrum'}], 'full_model_id': '3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f', 'groups': [{'description': 'All onsite matrix elements.', 'group_id': 'onsite', 'term_refs': ['onsite:levels']}], 'local_basis_labels': ['g', 'e1', 'e2'], 'mechanism_id': 'levels', 'observables': [{'band_index': 0, 'case_id': 'modes', 'kind': 'harmonic_frequency', 'observable_id': 'frequency', 'q': [0, 0, 0]}, {'basis_index': 0, 'case_id': 'rays', 'kind': 'local_population', 'observable_id': 'population'}], 'points': [{'factors': {'onsite': 0.5}, 'model_id': 'd46b8eddc1e93902679a5a55cf9cc3fdeaf198f740f98f4e8ff11c78f26fadc2', 'point_id': 'half'}, {'factors': {'onsite': 1.0}, 'model_id': '3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f', 'point_id': 'control'}, {'factors': {'onsite': 1.5}, 'model_id': '4a4a73ad06f3fdc865fe7eca417e13818c60ae970641fb17fffc67842f13a3db', 'point_id': 'strong'}], 'realized_cases': [{'case_id': 'rays', 'local_dimension': 3, 'point_id': 'half', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'rays', 'local_dimension': 3, 'point_id': 'control', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'rays', 'local_dimension': 3, 'point_id': 'strong', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 3, 'point_id': 'half', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 3, 'point_id': 'control', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': 3, 'point_id': 'strong', 'spin': None, 'spin_length': None, 'supercell_shape': [1, 1, 1]}], 'reference_tolerance': 1e-07, 'units': {'energy': 'dimensionless model units', 'hbar': 1}}

Limitations: ['Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.', 'Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.', 'Stationary finite classical states are not proofs of unique global or infinite-system ground states.', 'Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.', 'Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.', 'Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.', "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]

Evidence: [{"path": "calculation.hypotheses", "result_id": "levels-response"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
