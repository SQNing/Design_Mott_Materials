# Research report

Recover and assess the original stationary 12x12 honeycomb search.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-002/workflows/B-honeycomb/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-002/workflows/B-honeycomb/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-002/workflows/B-honeycomb/models/model-0001/readable.json)

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

## automatic-recovery

- Decision: Check the complete finite model and retain numerical evidence.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

- Charged compute seconds: 38.860560497734696
- Time accounting: measured

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-002/workflows/B-honeycomb/steps/automatic-recovery/result.json)

```json
{
  "energy_per_cell": -0.4249999999999998,
  "energy_total": -61.199999999999974,
  "supercell_shape": [
    12,
    12,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.790180836524724e-15,
  "finite_cell_bound_gap": 2.7755575615628914e-16,
  "infinite_lattice_certified": false,
  "ground_state_evidence": {
    "comparison_tolerance_per_cell": 1.4250000000000001e-09,
    "energy_gap_per_cell": 2.7755575615628914e-16,
    "finite_cell_lower_bound_per_cell": -0.4250000000000001,
    "finite_cell_status": "bound_saturated",
    "ground_state_absolute_tolerance": 1e-09,
    "ground_state_relative_tolerance": 1e-09,
    "infinite_lattice_status": "not_certified",
    "interpretation": "A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.",
    "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.",
    "spin_length": 0.5,
    "stationary": true,
    "supercell_shape": [
      12,
      12,
      1
    ]
  },
  "initial_search": {
    "energy_per_cell": -0.42498789285113153,
    "stationarity_max_norm": 3.195300853559411e-07,
    "finite_cell_bound_gap": 1.2107148868567563e-05
  },
  "recovery": {
    "accepted": true,
    "additional_starts": 1,
    "attempted": true,
    "enabled": true,
    "reason": "A lowest-mode state satisfies all local length and energy checks.",
    "seed": {
      "construction": "isotropic_cosine_sine_plane",
      "energy_gap_per_cell": 1.6653345369377348e-16,
      "local_length_max_error": 1.6653345369377348e-16,
      "q": [
        0.3333333333333333,
        0.16666666666666666,
        0.0
      ],
      "stationarity_max_norm": 4.379404155611337e-15
    }
  }
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.790180836524724e-15}
- Diagnostic: {"evidence": {"comparison_tolerance_per_cell": 1.4250000000000001e-09, "energy_gap_per_cell": 2.7755575615628914e-16, "finite_cell_lower_bound_per_cell": -0.4250000000000001, "finite_cell_status": "bound_saturated", "ground_state_absolute_tolerance": 1e-09, "ground_state_relative_tolerance": 1e-09, "infinite_lattice_status": "not_certified", "interpretation": "A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.", "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.", "spin_length": 0.5, "stationary": true, "supercell_shape": [12, 12, 1]}, "kind": "finite_cell_ground_state", "satisfied": true}
- Diagnostic: {"finite_cell_bound_gap": 2.7755575615628914e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Stationary states remain usable references when the finite-cell bound is not saturated.
- Scope/limitation: A positive LT gap alone does not prove that a lower locally feasible state exists.
- Scope/limitation: Finite-cell saturation is numerical evidence for this cell, not an infinite-lattice proof.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.
- Scope/limitation: A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.
- Scope/limitation: This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.

## Agent assessment

answered_within_scope: Automatic feasible-Fourier recovery reaches the finite-cell bound and retains the original stationary higher-energy state.

Claim level: finite_cell_ground_state

Scope: The specified finite periodic cell and Hamiltonian.

Limitations: ['No thermodynamic-limit ground-state claim.', 'Checkpoint accounting preserves any uncertainty in an interrupted duration.']

Evidence: [{"path": "calculation.ground_state_evidence", "result_id": "automatic-recovery"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- This cell saturates its numerical bound; compare larger or differently commensurate cells before extending the claim.
