# Research report

Resume an in-progress finite classical calculation.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Full source term count: 18
- Solver term count: 18
- Reconstruction/physical fidelity: not assessed. Coefficient weights are descriptive.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/D-resume/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/D-resume/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/D-resume/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [0, 0, 0]}] |
| exchange:1 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 2, "translation": [0, 0, 0]}] |
| exchange:10 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 2, "translation": [0, 1, 0]}] |
| exchange:11 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 2, "translation": [0, 0, 1]}] |
| exchange:12 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 2, "translation": [0, 0, 0]}, {"site": 3, "translation": [1, 0, 0]}] |
| exchange:13 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 2, "translation": [0, 0, 0]}, {"site": 3, "translation": [0, 1, 0]}] |
| exchange:14 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 2, "translation": [0, 0, 0]}, {"site": 3, "translation": [0, 0, 1]}] |
| exchange:15 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 3, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:16 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 3, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:17 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 3, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| exchange:2 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 3, "translation": [0, 0, 0]}] |
| exchange:3 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 2, "translation": [0, 0, 0]}] |
| exchange:4 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 3, "translation": [0, 0, 0]}] |
| exchange:5 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 2, "translation": [0, 0, 0]}, {"site": 3, "translation": [0, 0, 0]}] |
| exchange:6 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [1, 0, 0]}] |
| exchange:7 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [0, 1, 0]}] |
| exchange:8 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 1, "translation": [0, 0, 1]}] |
| exchange:9 | anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm) (main) | [{"site": 1, "translation": [0, 0, 0]}, {"site": 2, "translation": [1, 0, 0]}] |

## persistent

- Decision: Exercise continuation while the worker remains active.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/D-resume/steps/persistent/result.json)

```json
{
  "energy_per_cell": -4.425232499999998,
  "energy_total": -17.700929999999993,
  "supercell_shape": [
    2,
    2,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 3.2302429762944495e-12,
  "finite_cell_bound_gap": 0.002422233861662626,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 3.2302429762944495e-12}
- Diagnostic: {"finite_cell_bound_gap": 0.002422233861662626, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## Agent assessment

answered_within_scope: A second host process recovered the same worker result without another solve.

Scope: The recorded finite periodic classical calculation.

Limitations: ['These small calculations do not establish an infinite-system phase diagram.']

Evidence: [{"path": "calculation.energy_per_cell", "result_id": "persistent"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
