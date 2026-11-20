# Research report

Optimize the full three-level onsite/pair model and obtain all local harmonic modes.

- Answer status: answered_within_scope
- Model status: ready
- Model identity: 3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f
- Full source term count: 2
- Solver term count: 2
- Reconstruction/physical fidelity: not assessed. Coefficient weights are descriptive.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-retained-local/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-retained-local/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-retained-local/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "complex_projective_space"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| onsite:levels | retained_onsite_operator (main) | [{"site": 0, "translation": [0, 0, 0]}] |
| pair:general | retained_pair_operator (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## local-rays

- Decision: Search the full CP local space, retaining onsite and complex pair matrix.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f
- Task: classical_ground_state

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-retained-local/steps/local-rays/result.json)

```json
{
  "energy_per_cell": -0.51,
  "supercell_shape": [
    1,
    1,
    1
  ],
  "local_dimension": 3,
  "onsite_term_count": 1,
  "pair_term_count": 1,
  "stationarity": {
    "max_residual_norm": 2.3699247728209005e-12,
    "mean_residual_norm": 2.3699247728209005e-12,
    "residual_definition": "r_i = H_i^eff z_i - (z_i^dagger H_i^eff z_i) z_i, measured in Euclidean norm",
    "sites": [
      {
        "cell": [
          0,
          0,
          0
        ],
        "lagrange_multiplier": {
          "imag": 0.0,
          "real": -0.8200000000000001
        },
        "residual_norm": 2.3699247728209005e-12,
        "residual_vector": [
          {
            "imag": -2.121248875172269e-42,
            "real": 0.0
          },
          {
            "imag": -4.833765553329771e-13,
            "real": -2.3201032659641973e-12
          },
          {
            "imag": -8.967179447653783e-16,
            "real": -3.2504990100593117e-15
          }
        ],
        "site": 0
      }
    ]
  },
  "convergence": {
    "energy_converged": false,
    "energy_tolerance": 1e-06,
    "history": [
      {
        "best_start_source": "random",
        "energy": -0.51,
        "max_local_change": 2.3699259415292345e-11,
        "shape": [
          1,
          1,
          1
        ]
      }
    ],
    "max_linear_size": 1,
    "repeats_required": 1,
    "search_mode": "bounded",
    "stopped_reason": "max_linear_size_reached",
    "structural_dimension": 3
  }
}
```

- Diagnostic: {"kind": "stationarity", "satisfied": true, "value": 2.3699247728209005e-12}
- Diagnostic: {"finite_cell_bound_gap": null, "kind": "global_ground_state", "note": "Only the recorded finite search was performed.", "satisfied": false}

- Scope/limitation: Finite periodic product-state variational search in the full retained local space.
- Scope/limitation: Local stationarity does not prove the global or infinite-lattice ground state.
- Scope/limitation: Size convergence remains separate from stationarity.
- Scope/limitation: Energy is per primitive cell in the supplied Hamiltonian's energy units.

## gswt

- Decision: Reuse the local rays without another classical search.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 3c13e01259005aa3ef80ecc3b1b864c0a8f2bd978601a156ba3f9d90d3bc843f
- Task: spin_wave_spectrum

[Recorded evidence](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-retained-local/steps/gswt/result.json)

Reference reused from: local-rays.

```json
{
  "supercell_shape": [
    1,
    1,
    1
  ],
  "local_dimension": 3,
  "onsite_term_count": 1,
  "pair_term_count": 1,
  "stability": {
    "is_stationary": true,
    "minimum_bdg_hessian_eigenvalue": 1.3599999999999999,
    "scope": "requested q points only"
  }
}
```

- Diagnostic: {"details": {"is_stationary": true, "minimum_bdg_hessian_eigenvalue": 1.3599999999999999, "scope": "requested q points only"}, "kind": "harmonic_stability", "satisfied": true}

- Scope/limitation: Harmonic expansion about saved periodic local rays.
- Scope/limitation: All N-1 retained local excitations included; only requested q points checked.
- Scope/limitation: No global-ground-state or thermodynamic-limit certification.

[Spectrum samples, primitive reciprocal coordinates](/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/B-report/gswt-spectrum.csv)

## Agent assessment

answered_within_scope: A stationary retained-space product state and two stable harmonic branches were obtained.

Scope: One-cell product state; full three-dimensional local Hilbert space; two q points.

Limitations: ['These small calculations do not establish an infinite-system phase diagram.']

Evidence: [{"path": "calculation.energy_per_cell", "result_id": "local-rays"}, {"path": "calculation.stability", "result_id": "gswt"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Check robustness with more starts, an independent seed or a larger finite cell.
- Refine the reference if unstable; otherwise increase q sampling for broader claims.
