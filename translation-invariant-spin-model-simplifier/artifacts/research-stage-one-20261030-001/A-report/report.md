# Research report

Find and check a finite periodic reference for this four-sublattice triclinic model.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Full source term count: 18
- Solver term count: 18
- Reconstruction/physical fidelity: not assessed. Coefficient weights are descriptive.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/models/model-0001/readable.json)

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

## initial

- Decision: Obtain an initial finite-cell candidate.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/steps/initial/result.json)

```json
{
  "energy_per_cell": -4.4252325,
  "energy_total": -4.4252325,
  "supercell_shape": [
    1,
    1,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 3.1607434352722436e-12,
  "finite_cell_bound_gap": 0.0024222338616608496,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 3.1607434352722436e-12}
- Diagnostic: {"finite_cell_bound_gap": 0.0024222338616608496, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## refine

- Decision: The initial run has only one start; check independent seeds and tighter minimization.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/steps/refine/result.json)

```json
{
  "energy_per_cell": -4.4252325,
  "energy_total": -4.4252325,
  "supercell_shape": [
    1,
    1,
    1
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 2.9489378501712237e-12,
  "finite_cell_bound_gap": 0.0024222338616608496,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.9489378501712237e-12}
- Diagnostic: {"finite_cell_bound_gap": 0.0024222338616608496, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## spectrum

- Decision: Check the saved candidate's stationarity and quadratic stability at three wavevectors.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 10b544492b6eb3bc5d92f8063e2aacf6a852bab00455cff4956b78a872e01e78
- Task: spin_wave_spectrum

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-multisublattice/steps/spectrum/result.json)

Reference reused from: refine.

```json
{
  "supercell_shape": [
    1,
    1,
    1
  ],
  "spin": 0.5,
  "stability": {
    "is_stationary": true,
    "linear_term_max_norm": 2.308812230396952e-12,
    "maximum_imaginary_frequency": 4.356442366977892e-16,
    "minimum_bdg_hessian_eigenvalue": 0.6429229255076073,
    "scope": "requested q points and zero-point quadrature only"
  }
}
```

- Diagnostic: {"details": {"is_stationary": true, "linear_term_max_norm": 2.308812230396952e-12, "maximum_imaginary_frequency": 4.356442366977892e-16, "minimum_bdg_hessian_eigenvalue": 0.6429229255076073, "scope": "requested q points and zero-point quadrature only"}, "kind": "harmonic_stability", "satisfied": true}

- Scope/limitation: Harmonic approximation about the supplied or numerically optimized reference.
- Scope/limitation: For S > 1/2 all 2S local excited modes are retained (GSWT, not a one-mode LSWT truncation).
- Scope/limitation: Zero-point energy is a finite BZ quadrature, not an exact many-body energy.

[Spectrum samples, primitive reciprocal coordinates](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/A-report/spectrum-spectrum.csv)

## Agent assessment

answered_within_scope: The refined periodic candidate is stationary and harmonically stable at the sampled wavevectors.

Scope: Four-site primitive periodic cell; independent starts; three q points.

Limitations: ['These small calculations do not establish an infinite-system phase diagram.']

Evidence: [{"path": "calculation.energy_per_cell", "result_id": "refine"}, {"path": "calculation.stability", "result_id": "spectrum"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Check robustness with more starts, an independent seed or a larger finite cell.
- Refine the reference if unstable; otherwise increase q sampling for broader claims.
