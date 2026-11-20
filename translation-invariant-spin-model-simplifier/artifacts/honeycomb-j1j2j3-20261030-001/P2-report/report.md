# Research report

Determine the finite-cell classical ground-state family and numerical robustness at P2

- Answer status: answered_within_scope
- Model status: ready
- Model identity: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/models/model-0002/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/models/model-0002/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/models/model-0002/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"sphere": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "J1 with J1=+1; each undirected bond counted once", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| J1:0:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [0, 0, 0]}] |
| J1:0:1 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| J1:0:2 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| J2:0:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| J2:0:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| J2:0:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, -1, 0]}] |
| J2:1:0 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 1, "translation": [1, 0, 0]}] |
| J2:1:1 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 1, "translation": [0, 1, 0]}] |
| J2:1:2 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 1, "translation": [1, -1, 0]}] |
| J3:0:0 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 1, 0]}] |
| J3:0:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [1, -1, 0]}] |
| J3:0:2 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, -1, 0]}] |

## Proposed physical reductions

### drop-J3

- Transformation: drop_terms
- Preparation: ready
- Parent is current: True
- Complexity: {"candidate_dimension": null, "candidate_terms": 9, "full_dimension": null, "full_terms": 12}
- A prepared candidate is not yet a validated approximation.
[Candidate and operator mapping](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/reductions/drop-J3/record.json)

- Limitation: Coefficient norms alone do not bound the requested observables.

## Mechanism studies

### coupling-controls

Are J2 or J3 negligible for the ground-state energy and selected state at P2?

- Preparation: ready
- Parent is current: True
- Full-model control: control
[Intervention plan and complete models](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/mechanisms/coupling-controls/record.json)

- J2: All six second-neighbour bonds per cell Terms: J2:0:0, J2:0:1, J2:0:2, J2:1:0, J2:1:1, J2:1:2
- J3: All three third-neighbour bonds per cell Terms: J3:0:0, J3:0:1, J3:0:2

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"J2": 1.0, "J3": 1.0} | ready |
| J2-off | {"J2": 0.0, "J3": 1.0} | ready |
| J2-half | {"J2": 0.5, "J3": 1.0} | ready |
| J3-off | {"J2": 1.0, "J3": 0.0} | ready |
| J3-half | {"J2": 1.0, "J3": 0.5} | ready |

## ground-L4-seed31

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/ground-L4-seed31/result.json)

```json
{
  "energy_per_cell": -0.6500000000000005,
  "energy_total": -10.400000000000007,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.1236916626776756e-12,
  "finite_cell_bound_gap": -4.440892098500626e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.1236916626776756e-12}
- Diagnostic: {"finite_cell_bound_gap": -4.440892098500626e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L4-seed97

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/ground-L4-seed97/result.json)

```json
{
  "energy_per_cell": -0.6500000000000001,
  "energy_total": -10.400000000000002,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 2.1714203649641368e-10,
  "finite_cell_bound_gap": -1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.1714203649641368e-10}
- Diagnostic: {"finite_cell_bound_gap": -1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L6-seed53

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/ground-L6-seed53/result.json)

```json
{
  "energy_per_cell": -0.6500000000000004,
  "energy_total": -23.400000000000013,
  "supercell_shape": [
    6,
    6,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 5.985864361085724e-11,
  "finite_cell_bound_gap": -3.3306690738754696e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 5.985864361085724e-11}
- Diagnostic: {"finite_cell_bound_gap": -3.3306690738754696e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## validate-drop-J3

- Decision: Measure energy, correlations and sampled harmonic consequences using matched controls.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/result.json)

- Simplification verdict: rejected
- Candidate: drop-J3
- New solver calls: 4

| Experiment | Observable | Error | Tolerance | Verdict | Reason |
| --- | --- | --- | --- | --- | --- |
| reference | energy_per_cell | 0.1000000000000002 | 0.01 | fail |  |
| reference | full_energy_penalty | 0.607783652850554 | 0.01 | fail |  |
| reference | spin_correlations | 2.0 | 0.05 | fail |  |
| modes | spectrum | 0.9485858657604984 | 0.01 | fail |  |

Tested scope:

```json
{
  "candidate_model_id": "cd46005c9d58b3f3d7f9776adda961b3e23bb598eeb98adb32ff7137c90d921f",
  "energy_offset_per_cell": 0.0,
  "energy_window_max": null,
  "experiments": [
    {
      "case_id": "reference",
      "metrics": {
        "energy_per_cell": 0.01,
        "full_energy_penalty": 0.01,
        "spin_correlations": 0.05
      },
      "settings": {
        "maxiter": 2000,
        "seed": 19,
        "spin_length": 0.5,
        "starts": 8,
        "stationarity_tolerance": 1e-06,
        "supercell_shape": [
          4,
          4,
          1
        ]
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
            0.125,
            0,
            0
          ],
          [
            0.125,
            0.125,
            0
          ],
          [
            0.25,
            0,
            0
          ]
        ],
        "spin": 0.5,
        "stability_tolerance": 1e-05
      },
      "task": "spin_wave_spectrum"
    }
  ],
  "full_model_id": "d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35",
  "full_reference_tolerance": 1e-07,
  "realized_cases": [
    {
      "case_id": "reference",
      "local_dimension": null,
      "role": "full",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        4,
        4,
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
        4,
        4,
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
        4,
        4,
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
        4,
        4,
        1
      ]
    }
  ]
}
```

- [reference / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/reference/full.json), reused: False
- [reference / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/reference/candidate.json), reused: False
- [modes / full](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/modes/full.json), reused: False
- [modes / candidate](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/modes/candidate.json), reused: False

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "cb734150e75dbd77a0a84a386cec8c96a0ac7b11ccea780a79e09325003822d7", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/reference/full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "reference", "job_fingerprint": "b474b33ee8c9bc842c03658d266fd9c13c9bef72e2af1a71cec689ea1ebdb467", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/reference/candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "50b83b1ab912708e916b31d7691d749cabfe1bbdfc7a09a5861a1f81616ee9e5", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/modes/full.json", "reused": false, "role": "full", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "modes", "job_fingerprint": "3a4c5726a3d0fd303c46926a2b4c2d52c2fdd3f2ef959683c70b53cf72bd33c9", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/validate-drop-J3/evidence/modes/candidate.json", "reused": false, "role": "candidate", "scientific_status": "usable_within_scope"}

- Scope/limitation: Only this parameter point, the recorded finite cells, sampled momenta and selected observables were compared.
- Scope/limitation: Stationary variational states are not proofs of global or infinite-lattice ground states.
- Scope/limitation: State distances can distinguish symmetry-related representatives; rejection concerns the stated metric.
- Scope/limitation: Agreement does not certify phase equivalence, parameter robustness or virtual-excitation corrections.

## coupling-responses

- Decision: Test energetic insensitivity and inspect direct versus relaxation response.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/result.json)

- Mechanism study: coupling-controls
- New solver calls: 5

| Hypothesis | Verdict | Reason |
| --- | --- | --- |
| J2-negligible | refuted_within_scope | An isolated intervention exceeds the stated change bound. |
| J3-negligible | refuted_within_scope | An isolated intervention exceeds the stated change bound. |

### J2-negligible

Claim: J2 scaling changes energy by at most the declared tolerance.

Within the recorded finite model, varying group 'J2' over [0.0, 0.5, 1.0] gives observable 'energy' values [-1.35, -0.9, -0.65]. An isolated intervention exceeds the stated change bound.

Excluded confounded points: J3-off, J3-half

- [J2-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J2-off.json): value -1.3500000000000019; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}
- [J2-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J2-half.json): value -0.9000000000000008; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/control.json): value -0.6500000000000006; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}

### J3-negligible

Claim: J3 scaling changes energy by at most the declared tolerance.

Within the recorded finite model, varying group 'J3' over [0.0, 0.5, 1.0] gives observable 'energy' values [-0.55, -0.45, -0.65]. An isolated intervention exceeds the stated change bound.

Excluded confounded points: J2-off, J2-half

- [J3-off, factor 0.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J3-off.json): value -0.5499999999999998; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}
- [J3-half, factor 0.5](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J3-half.json): value -0.44999999999999996; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}
- [control, factor 1.0](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/control.json): value -0.6500000000000006; selector {"case_id": "ground", "kind": "energy_per_cell", "observable_id": "energy"}

| Observable | Point | Value | Scientific usability |
| --- | --- | --- | --- |
| energy | control | -0.6500000000000006 | usable_within_scope |
| energy | J2-off | -1.3500000000000019 | usable_within_scope |
| energy | J2-half | -0.9000000000000008 | usable_within_scope |
| energy | J3-off | -0.5499999999999998 | usable_within_scope |
| energy | J3-half | -0.44999999999999996 | usable_within_scope |

Energy response (per primitive cell):

| Experiment / point | Fixed-state change | Relaxation change | Total change | Scientific usability |
| --- | --- | --- | --- | --- |
| ground / control | 0.0 | 0.0 | 0.0 | usable_within_scope |
| ground / J2-off | 0.3000000000000006 | -1.0000000000000018 | -0.7000000000000013 | usable_within_scope |
| ground / J2-half | 0.15000000000000074 | -0.40000000000000097 | -0.2500000000000002 | usable_within_scope |
| ground / J3-off | 0.6000000000000006 | -0.4999999999999999 | 0.10000000000000075 | usable_within_scope |
| ground / J3-half | 0.3000000000000005 | -0.09999999999999987 | 0.20000000000000062 | usable_within_scope |

Tested scope:

```json
{
  "baseline_point_id": "control",
  "experiments": [
    {
      "case_id": "ground",
      "settings": {
        "maxiter": 2000,
        "seed": 53,
        "spin_length": 0.5,
        "starts": 6,
        "stationarity_tolerance": 1e-06,
        "supercell_shape": [
          8,
          8,
          1
        ]
      },
      "task": "classical_ground_state"
    }
  ],
  "full_model_id": "d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35",
  "groups": [
    {
      "description": "All six second-neighbour bonds per cell",
      "group_id": "J2",
      "term_refs": [
        "J2:0:0",
        "J2:0:1",
        "J2:0:2",
        "J2:1:0",
        "J2:1:1",
        "J2:1:2"
      ]
    },
    {
      "description": "All three third-neighbour bonds per cell",
      "group_id": "J3",
      "term_refs": [
        "J3:0:0",
        "J3:0:1",
        "J3:0:2"
      ]
    }
  ],
  "local_basis_labels": [],
  "mechanism_id": "coupling-controls",
  "observables": [
    {
      "case_id": "ground",
      "kind": "energy_per_cell",
      "observable_id": "energy"
    }
  ],
  "points": [
    {
      "factors": {
        "J2": 1.0,
        "J3": 1.0
      },
      "model_id": "d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35",
      "point_id": "control"
    },
    {
      "factors": {
        "J2": 0.0,
        "J3": 1.0
      },
      "model_id": "1e53c2d8891e9cdfe84497b0db70d82d09c821bad3f020b31d8f5e39c0ace09a",
      "point_id": "J2-off"
    },
    {
      "factors": {
        "J2": 0.5,
        "J3": 1.0
      },
      "model_id": "4c6ca7d8ff537fd2726bfb65bd26a05634fb42e0f434faf5654b3c8f47a392db",
      "point_id": "J2-half"
    },
    {
      "factors": {
        "J2": 1.0,
        "J3": 0.0
      },
      "model_id": "e868ac79682be13a0a8a93ecdaf0de2c62a92ad1468719f5b22b78f07d9119f9",
      "point_id": "J3-off"
    },
    {
      "factors": {
        "J2": 1.0,
        "J3": 0.5
      },
      "model_id": "9ffb9a0eaece0f01f48a2457ef80c1e44f18b5663535a65a4570ab1009d4cafd",
      "point_id": "J3-half"
    }
  ],
  "realized_cases": [
    {
      "case_id": "ground",
      "local_dimension": null,
      "point_id": "control",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        8,
        8,
        1
      ]
    },
    {
      "case_id": "ground",
      "local_dimension": null,
      "point_id": "J2-off",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        8,
        8,
        1
      ]
    },
    {
      "case_id": "ground",
      "local_dimension": null,
      "point_id": "J2-half",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        8,
        8,
        1
      ]
    },
    {
      "case_id": "ground",
      "local_dimension": null,
      "point_id": "J3-off",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        8,
        8,
        1
      ]
    },
    {
      "case_id": "ground",
      "local_dimension": null,
      "point_id": "J3-half",
      "spin": null,
      "spin_length": 0.5,
      "supercell_shape": [
        8,
        8,
        1
      ]
    }
  ],
  "reference_tolerance": 1e-07,
  "units": {
    "energy": "J1 with J1=+1; each undirected bond counted once",
    "hbar": 1
  }
}
```

```json
{}
```

- Diagnostic: {"blocker": null, "case_id": "ground", "job_fingerprint": "8698f635e5a3421af14b9c050f36a4c14f8763ae62b4f1f943d255f776bd6b95", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/control.json", "reused": false, "role": "control", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "ground", "job_fingerprint": "03dd61e7e0aa1b8c5c54c2b62d62dc83de06699470e6f016f5e129354c03baf0", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J2-off.json", "reused": false, "role": "J2-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "ground", "job_fingerprint": "3fa35deee6dceace90c1fc8838e31df6e17fdaf3d9efb39d64445360732385f8", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J2-half.json", "reused": false, "role": "J2-half", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "ground", "job_fingerprint": "dfe2f05f40855f3e6ee59d153dc689f20fdc941a28cb7bdb839fff62d8a236cd", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J3-off.json", "reused": false, "role": "J3-off", "scientific_status": "usable_within_scope"}
- Diagnostic: {"blocker": null, "case_id": "ground", "job_fingerprint": "2695d91b2baabddec7d500b99c0146743a6dc0bc6236a763680cd27c431718ae", "path": "/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/coupling-responses/evidence/ground/J3-half.json", "reused": false, "role": "J3-half", "scientific_status": "usable_within_scope"}

- Scope/limitation: Mechanism tests concern only the explicit Hamiltonian interventions, sampled coupling points and observables.
- Scope/limitation: Other groups stay at their full-model values for each one-group hypothesis; confounded points are excluded explicitly.
- Scope/limitation: Stationary finite classical states are not proofs of unique global or infinite-system ground states.
- Scope/limitation: Harmonic observables use sorted frequencies at specified q in the saved magnetic cell, without unfolding or eigenvector branch tracking.
- Scope/limitation: Numerical tolerances are declared comparison resolutions, not certified error bars or phase-equivalence bounds.
- Scope/limitation: Necessity in this context does not establish sufficiency, exclusivity or a universal mechanism.
- Scope/limitation: No virtual-excitation corrections or automatic extension of a simplified model's validated scope.

## fourier-seeded-L2

- Decision: Validate an equal-length single-q state constructed from the model's own finite-cell Fourier minimum.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: d6f73977d3efcccb76626173af54baf882875bab0436b1a6ae2333076ca94e35
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2/steps/fourier-seeded-L2/result.json)

```json
{
  "energy_per_cell": -0.6499999999999999,
  "energy_total": -2.5999999999999996,
  "supercell_shape": [
    2,
    2,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.024170082872281e-16,
  "finite_cell_bound_gap": 1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.024170082872281e-16}
- Diagnostic: {"finite_cell_bound_gap": 1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: Random searches find degenerate M-point multi-q states. A collinear zigzag member has the same energy. Removing J3 fails the declared approximation tests; isolated J2/J3 controls change the energy and correlations.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "ground-L6-seed53"}, {"path": "calculation.energy_per_cell", "result_id": "fourier-seeded-L2"}, {"path": "calculation.metrics", "result_id": "validate-drop-J3"}, {"path": "calculation.hypotheses", "result_id": "coupling-responses"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Refine inadequate controls or extend the tested cells, momenta and parameter points.
- Resolve inadequate controls or test additional finite sizes, momenta and isolated coupling points.
- Check robustness with more starts, an independent seed or a larger finite cell.
