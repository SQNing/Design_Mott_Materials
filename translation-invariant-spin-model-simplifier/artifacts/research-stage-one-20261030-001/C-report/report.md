# Research report

Find the requested finite-cell reference and harmonic spectrum after clarifying the operator normalization.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 58d703c063d0393a07c9ff533efb3bd4bc8e5e80fb96aba600f5525dffe2904f
- Full source term count: 3
- Solver term count: 3
- Reconstruction/physical fidelity: not assessed. Coefficient weights are descriptive.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-host-document/models/model-0002/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-host-document/models/model-0002/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-host-document/models/model-0002/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"classical-space:spin": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| term:J0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| term:J1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| term:J2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |

## host-ground

- Decision: The clarification fixes the operator scale; find a finite 2x2x2 reference with two independent starts.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 58d703c063d0393a07c9ff533efb3bd4bc8e5e80fb96aba600f5525dffe2904f
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-host-document/steps/host-ground/result.json)

```json
{
  "energy_per_cell": -0.6975000000000002,
  "energy_total": -5.580000000000002,
  "supercell_shape": [
    2,
    2,
    2
  ],
  "spin_length": 0.5,
  "stationarity_max_norm": 6.421083105632721e-14,
  "finite_cell_bound_gap": -2.220446049250313e-16,
  "infinite_lattice_certified": false
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 6.421083105632721e-14}
- Diagnostic: {"finite_cell_bound_gap": -2.220446049250313e-16, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Local minimization on the requested finite periodic supercell.
- Scope/limitation: An LT bound gap near zero certifies this cell, not the infinite lattice.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## host-spectrum

- Decision: The saved reference is stationary to 6.5e-14 and reaches its finite-cell LT bound; check its harmonic stability at the two requested momenta.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 58d703c063d0393a07c9ff533efb3bd4bc8e5e80fb96aba600f5525dffe2904f
- Task: spin_wave_spectrum

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-host-document/steps/host-spectrum/result.json)

Reference reused from: host-ground.

```json
{
  "supercell_shape": [
    2,
    2,
    2
  ],
  "spin": 0.5,
  "stability": {
    "is_stationary": true,
    "linear_term_max_norm": 3.236823339921665e-14,
    "maximum_imaginary_frequency": 3.8033812210791496e-16,
    "minimum_bdg_hessian_eigenvalue": -9.43689570931383e-16,
    "scope": "requested q points and zero-point quadrature only"
  }
}
```

- Diagnostic: {"details": {"is_stationary": true, "linear_term_max_norm": 3.236823339921665e-14, "maximum_imaginary_frequency": 3.8033812210791496e-16, "minimum_bdg_hessian_eigenvalue": -9.43689570931383e-16, "scope": "requested q points and zero-point quadrature only"}, "kind": "harmonic_stability", "satisfied": true}

- Scope/limitation: Harmonic approximation about the supplied or numerically optimized reference.
- Scope/limitation: For S > 1/2 all 2S local excited modes are retained (GSWT, not a one-mode LSWT truncation).
- Scope/limitation: Zero-point energy is a finite BZ quadrature, not an exact many-body energy.

[Spectrum samples, primitive reciprocal coordinates](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/C-report/host-spectrum-spectrum.csv)

## Agent assessment

answered_within_scope: The spins are parallel within numerical precision. The finite-cell energy is -0.6975 in the input units. The saved reference is stationary and harmonically stable within numerical tolerance at the two requested q points.

Scope: The specified 2x2x2 periodic cell and the two requested primitive-coordinate q points.

Limitations: ['No infinite-system or global phase-diagram claim.', 'The eight returned branches are folded by the 2x2x2 reference cell; unfolded primitive-cell spectral weights were not calculated.', 'The clarification was a scripted acceptance reply, not a new instruction from the project owner.']

Evidence: [{"path": "calculation.energy_per_cell", "result_id": "host-ground"}, {"path": "calculation.spins", "result_id": "host-ground"}, {"path": "calculation.stability", "result_id": "host-spectrum"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Refine the reference if unstable; otherwise increase q sampling for broader claims.
