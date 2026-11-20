# Research report

Determine the finite-cell classical ground-state family and numerical robustness at P1

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 3c275008a68221d35093888b800e33809ef3643369f6cdcd5de863981e6b50c9
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/models/model-0002/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/models/model-0002/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/models/model-0002/readable.json)

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

## ground-L4-seed31

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c275008a68221d35093888b800e33809ef3643369f6cdcd5de863981e6b50c9
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/steps/ground-L4-seed31/result.json)

```json
{
  "energy_per_cell": -0.6750000000000003,
  "energy_total": -10.800000000000004,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 5.461157772581562e-13,
  "finite_cell_bound_gap": -1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 5.461157772581562e-13}
- Diagnostic: {"finite_cell_bound_gap": -1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L4-seed97

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c275008a68221d35093888b800e33809ef3643369f6cdcd5de863981e6b50c9
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/steps/ground-L4-seed97/result.json)

```json
{
  "energy_per_cell": -0.6750000000000006,
  "energy_total": -10.80000000000001,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 4.814031053047499e-13,
  "finite_cell_bound_gap": -4.440892098500626e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 4.814031053047499e-13}
- Diagnostic: {"finite_cell_bound_gap": -4.440892098500626e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L6-seed53

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c275008a68221d35093888b800e33809ef3643369f6cdcd5de863981e6b50c9
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/steps/ground-L6-seed53/result.json)

```json
{
  "energy_per_cell": -0.6750000000000005,
  "energy_total": -24.30000000000002,
  "supercell_shape": [
    6,
    6,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 7.764664122556099e-13,
  "finite_cell_bound_gap": -3.3306690738754696e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 7.764664122556099e-13}
- Diagnostic: {"finite_cell_bound_gap": -3.3306690738754696e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## fourier-seeded-L2

- Decision: Validate an equal-length single-q state constructed from the model's own finite-cell Fourier minimum.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c275008a68221d35093888b800e33809ef3643369f6cdcd5de863981e6b50c9
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P1/steps/fourier-seeded-L2/result.json)

```json
{
  "energy_per_cell": -0.675,
  "energy_total": -2.7,
  "supercell_shape": [
    2,
    2,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.210257032909503e-16,
  "finite_cell_bound_gap": 1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.210257032909503e-16}
- Diagnostic: {"finite_cell_bound_gap": 1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: Independent random searches recover Neel order and saturate the finite-cell LT lower bound.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "ground-L6-seed53"}, {"path": "calculation.energy_per_cell", "result_id": "fourier-seeded-L2"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
