# Research report

Distinguish an unattainable relaxed LT bound from a failed stationary search.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 20fda524766ed8237b76ed15e9447a3f7cb08bf81861eb5fbdb1cb76b1e8f985
- Full source term count: 3
- Solver term count: 3
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/C-loose-bound/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/C-loose-bound/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/C-loose-bound/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| chain:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| chain:1 | isotropic_exchange (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 1, "translation": [1, 0, 0]}] |
| chain:2 | isotropic_exchange (main) | [{"site": 2, "translation": [0, 0, 0]}, {"site": 2, "translation": [1, 0, 0]}] |

## reference

- Decision: Check the complete finite model and retain numerical evidence.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 20fda524766ed8237b76ed15e9447a3f7cb08bf81861eb5fbdb1cb76b1e8f985
- Task: classical_ground_state

- Charged compute seconds: 0.4971666680648923
- Time accounting: measured

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-reliability-20261114-001/workflows/C-loose-bound/steps/reference/result.json)

```json
{
  "energy_per_cell": -0.31250000000000006,
  "energy_total": -0.6250000000000001,
  "supercell_shape": [
    2,
    1,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 2.498001805406602e-16,
  "finite_cell_bound_gap": 0.43749999999999994,
  "infinite_lattice_certified": false,
  "ground_state_evidence": {
    "comparison_tolerance_per_cell": 1.7500000000000002e-09,
    "energy_gap_per_cell": 0.43749999999999994,
    "finite_cell_lower_bound_per_cell": -0.75,
    "finite_cell_status": "not_certified",
    "ground_state_absolute_tolerance": 1e-09,
    "ground_state_relative_tolerance": 1e-09,
    "infinite_lattice_status": "not_certified",
    "interpretation": "A positive LT gap is lack of certification, not proof of a wrong state: the relaxed bound can be unattainable.",
    "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.",
    "spin_length": 0.5,
    "stationary": true,
    "supercell_shape": [
      2,
      1,
      1
    ]
  },
  "initial_search": {
    "energy_per_cell": -0.31250000000000006,
    "stationarity_max_norm": 2.498001805406602e-16,
    "finite_cell_bound_gap": 0.43749999999999994
  },
  "recovery": {
    "accepted": false,
    "additional_starts": 0,
    "attempted": false,
    "enabled": true,
    "reason": "No tested lowest Fourier mode satisfies every local length constraint and the energy bound."
  }
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.498001805406602e-16}
- Diagnostic: {"evidence": {"comparison_tolerance_per_cell": 1.7500000000000002e-09, "energy_gap_per_cell": 0.43749999999999994, "finite_cell_lower_bound_per_cell": -0.75, "finite_cell_status": "not_certified", "ground_state_absolute_tolerance": 1e-09, "ground_state_relative_tolerance": 1e-09, "infinite_lattice_status": "not_certified", "interpretation": "A positive LT gap is lack of certification, not proof of a wrong state: the relaxed bound can be unattainable.", "scope": "This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.", "spin_length": 0.5, "stationary": true, "supercell_shape": [2, 1, 1]}, "kind": "finite_cell_ground_state", "satisfied": false}
- Diagnostic: {"finite_cell_bound_gap": 0.43749999999999994, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Stationary states remain usable references when the finite-cell bound is not saturated.
- Scope/limitation: A positive LT gap alone does not prove that a lower locally feasible state exists.
- Scope/limitation: Finite-cell saturation is numerical evidence for this cell, not an infinite-lattice proof.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.
- Scope/limitation: A positive LT gap is lack of certification, not proof of a wrong state: the relaxed bound can be unattainable.
- Scope/limitation: This fixed periodic cell only; floating-point evidence, not interval certification or a thermodynamic-limit proof.

## Agent assessment

answered_within_scope: A stationary reference is usable; no tested lowest mode meets all local constraints, so finite-cell certification remains unavailable.

Claim level: stationary_reference

Scope: The specified finite periodic cell and Hamiltonian.

Limitations: ['No thermodynamic-limit ground-state claim.', 'Checkpoint accounting preserves any uncertainty in an interrupted duration.']

Evidence: [{"path": "calculation.ground_state_evidence", "result_id": "reference"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Use independent starts and appropriate cells; an unsaturated relaxed LT bound alone does not prove that this state is wrong.
