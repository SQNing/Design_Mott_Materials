# Research report

Determine the finite-cell classical ground-state family and numerical robustness at P4

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/models/model-0002/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/models/model-0002/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/models/model-0002/readable.json)

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
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/ground-L4-seed31/result.json)

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
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.6742406642587807e-08}
- Diagnostic: {"finite_cell_bound_gap": 1.1600054250493486e-11, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L4-seed97

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/ground-L4-seed97/result.json)

```json
{
  "energy_per_cell": -0.41471784989866295,
  "energy_total": -6.635485598378607,
  "supercell_shape": [
    4,
    4,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.4076876798559683e-08,
  "finite_cell_bound_gap": 5.162981153716828e-12,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.4076876798559683e-08}
- Diagnostic: {"finite_cell_bound_gap": 5.162981153716828e-12, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L6-seed53

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/ground-L6-seed53/result.json)

```json
{
  "energy_per_cell": -0.4249999999818243,
  "energy_total": -15.299999999345674,
  "supercell_shape": [
    6,
    6,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 4.977158159414378e-08,
  "finite_cell_bound_gap": 1.8175794203045825e-11,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 4.977158159414378e-08}
- Diagnostic: {"finite_cell_bound_gap": 1.8175794203045825e-11, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L8-seed71

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/ground-L8-seed71/result.json)

```json
{
  "energy_per_cell": -0.42591812591313893,
  "energy_total": -27.258760058440892,
  "supercell_shape": [
    8,
    8,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 6.393269243261026e-08,
  "finite_cell_bound_gap": 2.1881663148093367e-11,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 6.393269243261026e-08}
- Diagnostic: {"finite_cell_bound_gap": 2.1881663148093367e-11, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## ground-L12-seed83

- Decision: Independent unconstrained starts, finite-cell LT bound and size checks.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/ground-L12-seed83/result.json)

```json
{
  "energy_per_cell": -0.42498789285113153,
  "energy_total": -61.19825657056294,
  "supercell_shape": [
    12,
    12,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 3.195300853559411e-07,
  "finite_cell_bound_gap": 1.2107148868567563e-05,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 3.195300853559411e-07}
- Diagnostic: {"finite_cell_bound_gap": 1.2107148868567563e-05, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## fourier-seeded-L36

- Decision: Validate an equal-length single-q state constructed from the model's own finite-cell Fourier minimum.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/fourier-seeded-L36/result.json)

```json
{
  "energy_per_cell": -0.42732430681663525,
  "energy_total": -553.8123016343593,
  "supercell_shape": [
    36,
    36,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.1247414067735156e-14,
  "finite_cell_bound_gap": 2.220446049250313e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.1247414067735156e-14}
- Diagnostic: {"finite_cell_bound_gap": 2.220446049250313e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## fourier-seeded-L12

- Decision: The random L12 state is stationary but above the finite-cell bound; test a separately constructed equal-length LT state.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 8a1f43603a41ba426648e039b8d5b2a3889be217920c0f970c5403105419c7b2
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P4/steps/fourier-seeded-L12/result.json)

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
  "stationarity_max_norm": 3.162048167326065e-15,
  "finite_cell_bound_gap": 2.7755575615628914e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 3.162048167326065e-15}
- Diagnostic: {"finite_cell_bound_gap": 2.7755575615628914e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: Random searches and a larger Fourier-seeded cell recover modulated states; the finite-cell LT bound is saturated. The ordering wavevector remains subject to commensurability.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "ground-L6-seed53"}, {"path": "calculation.energy_per_cell", "result_id": "fourier-seeded-L36"}]

answered_within_scope: Random searches and a larger Fourier-seeded cell recover modulated states; the finite-cell LT bound is saturated. The ordering wavevector remains subject to commensurability. The original L12 random search was stationary but above the cell bound; a separate Fourier-seeded L12 calculation closes that gap.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "ground-L6-seed53"}, {"path": "calculation.energy_per_cell", "result_id": "fourier-seeded-L36"}, {"path": "calculation.finite_cell_bound_gap", "result_id": "fourier-seeded-L12"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
