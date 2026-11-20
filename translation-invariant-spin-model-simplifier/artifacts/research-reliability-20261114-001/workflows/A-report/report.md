# Research report

Resume after an intentionally interrupted test worker.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/A-interruption/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/A-interruption/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/A-interruption/models/model-0001/readable.json)

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

## interrupted

- Decision: Check the complete finite model and retain numerical evidence.
- Execution: interrupted
- Scientific usability: pending
- Result model: pending
- Task: classical_ground_state

- Charged compute seconds: 0.8357331897132099
- Time accounting: last_checkpoint (uncertain duration)

## resumed

- Decision: Check the complete finite model and retain numerical evidence.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

- Charged compute seconds: 2.11772207217291
- Time accounting: measured

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/A-interruption/steps/resumed/result.json)

```json
{
  "energy_per_cell": -0.4147178498922259,
  "energy_total": -6.635485598275614,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 2.6742406642587807e-08,
  "finite_cell_bound_gap": 1.1600054250493486e-11,
  "infinite_lattice_certified": false,
  "ground_state_evidence": {
    "comparison_tolerance_per_cell": 1.414717849903826e-09,
    "energy_gap_per_cell": 1.1600054250493486e-11,
    "finite_cell_lower_bound_per_cell": -0.41471784990382593,
    "finite_cell_status": "bound_saturated",
    "ground_state_absolute_tolerance": 1e-09,
    "ground_state_relative_tolerance": 1e-09,
    "infinite_lattice_status": "not_certified",
    "interpretation": "A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.",
    "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.",
    "spin_length": 0.5,
    "stationary": true,
    "supercell_shape": [
      4,
      4,
      1
    ]
  },
  "initial_search": {
    "energy_per_cell": -0.4147178498922259,
    "stationarity_max_norm": 2.6742406642587807e-08,
    "finite_cell_bound_gap": 1.1600054250493486e-11
  },
  "recovery": {
    "accepted": false,
    "additional_starts": 0,
    "attempted": false,
    "enabled": true,
    "reason": "Initial search already saturates the finite-cell bound."
  }
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.6742406642587807e-08}
- Diagnostic: {"evidence": {"comparison_tolerance_per_cell": 1.414717849903826e-09, "energy_gap_per_cell": 1.1600054250493486e-11, "finite_cell_lower_bound_per_cell": -0.41471784990382593, "finite_cell_status": "bound_saturated", "ground_state_absolute_tolerance": 1e-09, "ground_state_relative_tolerance": 1e-09, "infinite_lattice_status": "not_certified", "interpretation": "A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.", "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.", "spin_length": 0.5, "stationary": true, "supercell_shape": [4, 4, 1]}, "kind": "finite_cell_ground_state", "satisfied": true}
- Diagnostic: {"finite_cell_bound_gap": 1.1600054250493486e-11, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Stationary states remain usable references when the finite-cell bound is not saturated.
- Scope/limitation: A positive LT gap alone does not prove that a lower locally feasible state exists.
- Scope/limitation: Finite-cell saturation is numerical evidence for this cell, not an infinite-lattice proof.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.
- Scope/limitation: A locally feasible stationary state attains the finite-cell LT lower bound within the declared numerical resolution.
- Scope/limitation: This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.

## Agent assessment

answered_within_scope: The resumed calculation attains its finite-cell numerical bound; the interrupted record is retained.

Claim level: finite_cell_ground_state

Scope: The specified finite periodic cell and Hamiltonian.

Limitations: ['No thermodynamic-limit ground-state claim.', 'Checkpoint accounting preserves any uncertainty in an interrupted duration.']

Evidence: [{"path": "calculation.ground_state_evidence", "result_id": "resumed"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- This cell saturates its numerical bound; compare larger or differently commensurate cells before extending the claim.
