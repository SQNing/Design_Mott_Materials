# Research report

Determine the finite-cell classical ground-state family and numerical robustness at P3

- Answer status: answered_within_scope
- Model status: ready
- Model identity: f1621088ecc4ebbcb9b40928ea957ecb682916c9c5ff09a3e430908c33f4d351
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/models/model-0002/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/models/model-0002/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/models/model-0002/readable.json)

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
- Result model: f1621088ecc4ebbcb9b40928ea957ecb682916c9c5ff09a3e430908c33f4d351
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/steps/ground-L4-seed31/result.json)

```json
{
  "energy_per_cell": -0.8250000000000004,
  "energy_total": -13.200000000000006,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 4.171768495962887e-13,
  "finite_cell_bound_gap": -3.3306690738754696e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 4.171768495962887e-13}
- Diagnostic: {"finite_cell_bound_gap": -3.3306690738754696e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L4-seed97

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: f1621088ecc4ebbcb9b40928ea957ecb682916c9c5ff09a3e430908c33f4d351
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/steps/ground-L4-seed97/result.json)

```json
{
  "energy_per_cell": -0.8250000000000002,
  "energy_total": -13.200000000000003,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 6.333841925448032e-13,
  "finite_cell_bound_gap": -1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 6.333841925448032e-13}
- Diagnostic: {"finite_cell_bound_gap": -1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L6-seed53

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: f1621088ecc4ebbcb9b40928ea957ecb682916c9c5ff09a3e430908c33f4d351
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/steps/ground-L6-seed53/result.json)

```json
{
  "energy_per_cell": -0.8250000000000005,
  "energy_total": -29.700000000000017,
  "supercell_shape": [
    6,
    6,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 8.245603009498977e-13,
  "finite_cell_bound_gap": -4.440892098500626e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 8.245603009498977e-13}
- Diagnostic: {"finite_cell_bound_gap": -4.440892098500626e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## fourier-seeded-L2

- Decision: Validate an equal-length single-q state constructed from the model's own finite-cell Fourier minimum.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: f1621088ecc4ebbcb9b40928ea957ecb682916c9c5ff09a3e430908c33f4d351
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P3/steps/fourier-seeded-L2/result.json)

```json
{
  "energy_per_cell": -0.825,
  "energy_total": -3.3,
  "supercell_shape": [
    2,
    2,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.010049830915136e-16,
  "finite_cell_bound_gap": 1.1102230246251565e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.010049830915136e-16}
- Diagnostic: {"finite_cell_bound_gap": 1.1102230246251565e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: Random searches find degenerate M-point multi-q states. A collinear stripy member has the same energy; uniqueness is not established.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "ground-L6-seed53"}, {"path": "calculation.energy_per_cell", "result_id": "fourier-seeded-L2"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
