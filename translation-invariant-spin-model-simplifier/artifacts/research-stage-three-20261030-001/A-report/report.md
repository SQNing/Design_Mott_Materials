# Research report

Can anisotropy be omitted, and which interaction controls the sampled frequencies?

- Answer status: answered_within_scope
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/models/model-0001/readable.json)

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
[Candidate and operator mapping](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/reductions/drop/record.json)

- Limitation: Coefficient norms alone do not bound the requested observables.

## Mechanism studies

### couplings

Which interaction controls the frequency at the selected momentum?

- Preparation: ready
- Parent is current: True
- Full-model control: control
[Intervention plan and complete models](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/mechanisms/couplings/record.json)

- anisotropy: Uniaxial exchange anisotropy. Terms: small
- exchange: The isotropic exchange background. Terms: exchange:0, exchange:1, exchange:2

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"anisotropy": 1.0, "exchange": 1.0} | ready |
| anisotropy-off | {"anisotropy": 0.0, "exchange": 1.0} | ready |
| anisotropy-half | {"anisotropy": 0.5, "exchange": 1.0} | ready |
| exchange-off | {"anisotropy": 1.0, "exchange": 0.0} | ready |
| exchange-half | {"anisotropy": 1.0, "exchange": 0.5} | ready |

## validate

- Decision: Check energy, correlations and harmonic excitations in the same finite cell.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/result.json)

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

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/reference/full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/reference/candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/modes/full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/modes/candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "836043a70e66e80aeed237ec0f05b2b87c1d3a46483730586da537482b160ee4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/reference/full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "957a1feca71b4b4845fb3c5de23b57f85a64ab2911900774487c3d7beeff5342", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/reference/candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "a7eeba6262f86d2b94850df047cc9baad078b18b42dbed1a59523b262d462a45", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/modes/full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "71305c5d801d08467aad818dec9cef51746db5ed530895479e369944fec03a5a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/validate/evidence/modes/candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## response

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/result.json)

- Mechanism study: couplings
- New solver calls: 8

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| anisotropy-response | supported_within_scope | All sampled isolated increments follow the proposed direction and the span exceeds the threshold. |
| anisotropy-necessary | supported_within_scope | The phenomenon is present in the full-model control and disappears under the isolated removal. |
| exchange-response | refuted_within_scope | The measured span is smaller than the stated minimum effect. |
| exchange-insensitive | supported_within_scope | All sampled isolated responses stay within the stated change bound. |

### anisotropy-response

Claim: Anisotropy raises the sampled frequency.

Within the recorded finite model, varying group 'anisotropy' over [0.0, 0.5, 1.0] gives observable 'frequency' values [-3.329251562e-16, 0.01, 0.02]. All sampled isolated increments follow the proposed direction and the span exceeds the threshold.

Excluded confounded points: exchange-off, exchange-half

- [anisotropy-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/anisotropy-off.json): value -3.3292515621207596e-16; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [anisotropy-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/anisotropy-half.json): value 0.009999999999999787; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### anisotropy-necessary

Claim: Anisotropy is necessary for this finite frequency.

Within the recorded finite model, varying group 'anisotropy' over [0.0, 1.0] gives observable 'frequency' values [-3.329251562e-16, 0.02]. The phenomenon is present in the full-model control and disappears under the isolated removal.

Excluded confounded points: exchange-off, exchange-half

- [anisotropy-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/anisotropy-off.json): value -3.3292515621207596e-16; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### exchange-response

Claim: Exchange raises the sampled frequency.

Within the recorded finite model, varying group 'exchange' over [0.0, 0.5, 1.0] gives observable 'frequency' values [0.02, 0.02, 0.02]. The measured span is smaller than the stated minimum effect.

Excluded confounded points: anisotropy-off, anisotropy-half

- [exchange-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-off.json): value 0.020000000000000004; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [exchange-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-half.json): value 0.020000000000000018; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

### exchange-insensitive

Claim: This frequency is insensitive to exchange.

Within the recorded finite model, varying group 'exchange' over [0.0, 0.5, 1.0] gives observable 'frequency' values [0.02, 0.02, 0.02]. All sampled isolated responses stay within the stated change bound.

Excluded confounded points: anisotropy-off, anisotropy-half

- [exchange-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-off.json): value 0.020000000000000004; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [exchange-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-half.json): value 0.020000000000000018; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/control.json): value 0.019999999999999574; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0, 0, 0]}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | control | 0.019999999999999574 | usable_within_scope |
| frequency | anisotropy-off | -3.3292515621207596e-16 | usable_within_scope |
| frequency | anisotropy-half | 0.009999999999999787 | usable_within_scope |
| frequency | exchange-off | 0.020000000000000004 | usable_within_scope |
| frequency | exchange-half | 0.020000000000000018 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| reference / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| reference / anisotropy-off | 0.0050000000000000044 | -2.220446049250313e-16 | 0.004999999999999782 | usable_within_scope |
| reference / anisotropy-half | 0.0024999999999999467 | 0.0 | 0.0024999999999999467 | usable_within_scope |
| reference / exchange-off | 0.75 | -3.642919299551295e-17 | 0.75 | usable_within_scope |
| reference / exchange-half | 0.375 | 0.0 | 0.375 | usable_within_scope |

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
        "anisotropy": 0.0,
        "exchange": 1.0
      },
      "model_id": "08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6",
      "point_id": "anisotropy-off"
    },
    {
      "factors": {
        "anisotropy": 0.5,
        "exchange": 1.0
      },
      "model_id": "40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c",
      "point_id": "anisotropy-half"
    },
    {
      "factors": {
        "anisotropy": 1.0,
        "exchange": 0.0
      },
      "model_id": "04f89d665504698c73a6acce3f698a9dab1efa0661dc3bad655847d5d7557056",
      "point_id": "exchange-off"
    },
    {
      "factors": {
        "anisotropy": 1.0,
        "exchange": 0.5
      },
      "model_id": "90b8050f05c9fb5c06f3a2a019c9a23876293f05ab1db7a56ecba530931a8a9a",
      "point_id": "exchange-half"
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
      "case_id": "reference",
      "local_dimension": null,
      "point_id": "exchange-off",
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
      "point_id": "exchange-half",
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
    },
    {
      "case_id": "modes",
      "local_dimension": null,
      "point_id": "exchange-off",
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
      "point_id": "exchange-half",
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

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "836043a70e66e80aeed237ec0f05b2b87c1d3a46483730586da537482b160ee4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/reference/control.json", "reused": true, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "c0dc131b37f17a3e4ff29784a51d295175447a00d96d9274e03ecaba70ad476a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/reference/anisotropy-off.json", "reused": false, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "99237db5788ea70fcb0c2b79f62880808b9214b9b4be1868f518cf92606ca40d", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/reference/anisotropy-half.json", "reused": false, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "6f03dead1dd3603c5df96f5ac0bc5a88454082d815743f532385054bb0be090a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/reference/exchange-off.json", "reused": false, "role": "exchange-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "0b10cd526cdcba284b8f2b6b83c453d912ae3d2783c8faa914a98c464c654ade", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/reference/exchange-half.json", "reused": false, "role": "exchange-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "a7eeba6262f86d2b94850df047cc9baad078b18b42dbed1a59523b262d462a45", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/control.json", "reused": true, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "deb8fef24ad34445c5b513816b8dc911b71716f4c0989ba75157b12483c993ee", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/anisotropy-off.json", "reused": false, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "c2605d0d78cb74adb1ad93ffbb6db6c749ed227998bacc6467f85d253eec8260", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/anisotropy-half.json", "reused": false, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "6dc5c48c6854dcfc197be8904423537dd46e3d30dbd7627ae702eed13c644e09", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-off.json", "reused": false, "role": "exchange-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "3750e83bc517d777aeaf02bc9868c7563f77ba297b7bfd8132bc152dc80b20b0", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/response/evidence/modes/exchange-half.json", "reused": false, "role": "exchange-half", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## finite-momentum

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/result.json)

- Mechanism study: couplings
- New solver calls: 0

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| exchange-response | supported_within_scope | All sampled isolated increments follow the proposed direction and the span exceeds the threshold. |

### exchange-response

Claim: Exchange raises the sampled frequency.

Within the recorded finite model, varying group 'exchange' over [0.0, 0.5, 1.0] gives observable 'frequency' values [0.02, 0.52, 1.02]. All sampled isolated increments follow the proposed direction and the span exceeds the threshold.

Excluded confounded points: anisotropy-off, anisotropy-half

- [exchange-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/exchange-off.json): value 0.020000000000000004; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0.25, 0, 0]}
- [exchange-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/exchange-half.json): value 0.52; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0.25, 0, 0]}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/control.json): value 1.0199999999999996; selector {"band_index": 0, "case_id": "modes", "kind": "harmonic_frequency", "observable_id": "frequency", "q": [0.25, 0, 0]}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| frequency | control | 1.0199999999999996 | usable_within_scope |
| frequency | anisotropy-off | 0.9999999999999999 | usable_within_scope |
| frequency | anisotropy-half | 1.0100000000000002 | usable_within_scope |
| frequency | exchange-off | 0.020000000000000004 | usable_within_scope |
| frequency | exchange-half | 0.52 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| reference / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| reference / anisotropy-off | 0.0050000000000000044 | -2.220446049250313e-16 | 0.004999999999999782 | usable_within_scope |
| reference / anisotropy-half | 0.0024999999999999467 | 0.0 | 0.0024999999999999467 | usable_within_scope |
| reference / exchange-off | 0.75 | -3.642919299551295e-17 | 0.75 | usable_within_scope |
| reference / exchange-half | 0.375 | 0.0 | 0.375 | usable_within_scope |

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
        0.25,
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
        "anisotropy": 0.0,
        "exchange": 1.0
      },
      "model_id": "08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6",
      "point_id": "anisotropy-off"
    },
    {
      "factors": {
        "anisotropy": 0.5,
        "exchange": 1.0
      },
      "model_id": "40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c",
      "point_id": "anisotropy-half"
    },
    {
      "factors": {
        "anisotropy": 1.0,
        "exchange": 0.0
      },
      "model_id": "04f89d665504698c73a6acce3f698a9dab1efa0661dc3bad655847d5d7557056",
      "point_id": "exchange-off"
    },
    {
      "factors": {
        "anisotropy": 1.0,
        "exchange": 0.5
      },
      "model_id": "90b8050f05c9fb5c06f3a2a019c9a23876293f05ab1db7a56ecba530931a8a9a",
      "point_id": "exchange-half"
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
      "case_id": "reference",
      "local_dimension": null,
      "point_id": "exchange-off",
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
      "point_id": "exchange-half",
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
    },
    {
      "case_id": "modes",
      "local_dimension": null,
      "point_id": "exchange-off",
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
      "point_id": "exchange-half",
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

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "836043a70e66e80aeed237ec0f05b2b87c1d3a46483730586da537482b160ee4", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/reference/control.json", "reused": true, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "c0dc131b37f17a3e4ff29784a51d295175447a00d96d9274e03ecaba70ad476a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/reference/anisotropy-off.json", "reused": true, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "99237db5788ea70fcb0c2b79f62880808b9214b9b4be1868f518cf92606ca40d", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/reference/anisotropy-half.json", "reused": true, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "6f03dead1dd3603c5df96f5ac0bc5a88454082d815743f532385054bb0be090a", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/reference/exchange-off.json", "reused": true, "role": "exchange-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "0b10cd526cdcba284b8f2b6b83c453d912ae3d2783c8faa914a98c464c654ade", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/reference/exchange-half.json", "reused": true, "role": "exchange-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "a7eeba6262f86d2b94850df047cc9baad078b18b42dbed1a59523b262d462a45", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/control.json", "reused": true, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "deb8fef24ad34445c5b513816b8dc911b71716f4c0989ba75157b12483c993ee", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/anisotropy-off.json", "reused": true, "role": "anisotropy-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "c2605d0d78cb74adb1ad93ffbb6db6c749ed227998bacc6467f85d253eec8260", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/anisotropy-half.json", "reused": true, "role": "anisotropy-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "6dc5c48c6854dcfc197be8904423537dd46e3d30dbd7627ae702eed13c644e09", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/exchange-off.json", "reused": true, "role": "exchange-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "3750e83bc517d777aeaf02bc9868c7563f77ba297b7bfd8132bc152dc80b20b0", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/A-reduction-to-mechanism/steps/finite-momentum/evidence/modes/exchange-half.json", "reused": true, "role": "exchange-half", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## Agent assessment

answered_within_scope: Deleting anisotropy fails the sampled spectrum tolerance. Its isolated removal suppresses the zone-center frequency; exchange controls the frequency response at the other sampled momentum. These statements concern the specified finite model.

Scope: {'baseline_point_id': 'control', 'experiments': [{'case_id': 'reference', 'settings': {'seed': 18, 'spin_length': 0.5, 'starts': 3, 'supercell_shape': [1, 1, 1]}, 'task': 'classical_ground_state'}, {'case_id': 'modes', 'reference_case': 'reference', 'settings': {'reduced_momenta': [[0, 0, 0], [0.25, 0, 0]], 'spin': 0.5}, 'task': 'spin_wave_spectrum'}], 'full_model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'groups': [{'description': 'Uniaxial exchange anisotropy.', 'group_id': 'anisotropy', 'term_refs': ['small']}, {'description': 'The isotropic exchange background.', 'group_id': 'exchange', 'term_refs': ['exchange:0', 'exchange:1', 'exchange:2']}], 'local_basis_labels': [], 'mechanism_id': 'couplings', 'observables': [{'band_index': 0, 'case_id': 'modes', 'kind': 'harmonic_frequency', 'observable_id': 'frequency', 'q': [0, 0, 0]}], 'points': [{'factors': {'anisotropy': 1.0, 'exchange': 1.0}, 'model_id': 'ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf', 'point_id': 'control'}, {'factors': {'anisotropy': 0.0, 'exchange': 1.0}, 'model_id': '08c1cd796bba2162a93a820f4d1db2961d746bffbdda9c5d5ed3113139cccaa6', 'point_id': 'anisotropy-off'}, {'factors': {'anisotropy': 0.5, 'exchange': 1.0}, 'model_id': '40346f66bf4795e61e5e3a7f4b0fecb14c8d5e260be21f7bf4414e9c4b55104c', 'point_id': 'anisotropy-half'}, {'factors': {'anisotropy': 1.0, 'exchange': 0.0}, 'model_id': '04f89d665504698c73a6acce3f698a9dab1efa0661dc3bad655847d5d7557056', 'point_id': 'exchange-off'}, {'factors': {'anisotropy': 1.0, 'exchange': 0.5}, 'model_id': '90b8050f05c9fb5c06f3a2a019c9a23876293f05ab1db7a56ecba530931a8a9a', 'point_id': 'exchange-half'}], 'realized_cases': [{'case_id': 'reference', 'local_dimension': None, 'point_id': 'control', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'anisotropy-off', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'anisotropy-half', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'exchange-off', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'reference', 'local_dimension': None, 'point_id': 'exchange-half', 'spin': None, 'spin_length': 0.5, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'control', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'anisotropy-off', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'anisotropy-half', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'exchange-off', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}, {'case_id': 'modes', 'local_dimension': None, 'point_id': 'exchange-half', 'spin': 0.5, 'spin_length': None, 'supercell_shape': [1, 1, 1]}], 'reference_tolerance': 1e-07, 'units': {'energy': 'dimensionless model units', 'hbar': 1}}

Limitations: ['Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.', 'Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.', 'Stationary finite classical states are not proofs of unique global or infinite-system ground states.', 'Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.', 'Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.', 'Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.', "No virtual-excitation corrections or automatic extension of a simplified model's validated scope."]

Evidence: [{"path": "calculation.metrics", "result_id": "validate"}, {"path": "calculation.hypotheses", "result_id": "finite-momentum"}, {"path": "calculation.hypotheses", "result_id": "response"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Refine inadequate controls or extend the tested cells, momenta and parameter points.
- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
