# Research report

Resolve finite-cell commensurability in the J3-half intervention.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 5fdb0593496517616a3f5e2fe5b1feab3ca82119a6c956d423b95ea1e7b40d05
- Full source term count: 12
- Solver term count: 12
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2-J3-half-L36/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2-J3-half-L36/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2-J3-half-L36/models/model-0001/readable.json)

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

## fourier-seeded-L36

- Decision: Verify the larger commensurate cell from a model-derived LT seed; no presumed order is imposed.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 5fdb0593496517616a3f5e2fe5b1feab3ca82119a6c956d423b95ea1e7b40d05
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/honeycomb-j1j2j3-20261030-001/P2-J3-half-L36/steps/fourier-seeded-L36/result.json)

```json
{
  "energy_per_cell": -0.4613340798452848,
  "energy_total": -597.8889674794891,
  "supercell_shape": [
    36,
    36,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 1.0892109756435228e-14,
  "finite_cell_bound_gap": -6.661338147750939e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 1.0892109756435228e-14}
- Diagnostic: {"finite_cell_bound_gap": -6.661338147750939e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: A model-derived single-q state saturates the 36x36 finite-cell bound, resolving part of the 8x8 commensurability error.

Scope: Only the listed coupling points, finite periodic cells and explicitly sampled harmonic momenta.

Limitations: ['No full parameter-space phase diagram or unique ordered state is claimed.', 'No thermal or quantum fluctuation selection was computed.', 'The continuous Fourier minimization is numerical and is not an interval-certified global proof.', 'Small cells can miss incommensurate minima; larger Fourier-seeded cells are not independent random-start searches.']

Evidence: [{"path": "calculation.finite_cell_bound_gap", "result_id": "fourier-seeded-L36"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
