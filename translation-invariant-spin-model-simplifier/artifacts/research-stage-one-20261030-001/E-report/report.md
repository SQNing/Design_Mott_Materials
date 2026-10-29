# Research report

Obtain small finite-temperature samples and a finite quantum spectrum.

- Answer status: partial
- Model status: ready
- Model identity: 1dbef8e38db3a86e1458f843ca3360664e5c38caff592ae43843b25b67364b16
- Full source term count: 3
- Solver term count: 3
- Reconstruction/physical fidelity: not assessed. Coefficient weights are descriptive.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-mc-quantum/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-mc-quantum/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-mc-quantum/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"classical-space:spin": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "input coefficient units; absolute unit unspecified"}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| term:J0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| term:J1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| term:J2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |

## mc

- Decision: Check sampling and diagnostic output on a tiny periodic system.
- Execution: succeeded
- Scientific usability: inconclusive
- Result model: 1dbef8e38db3a86e1458f843ca3360664e5c38caff592ae43843b25b67364b16
- Task: classical_monte_carlo

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-mc-quantum/steps/mc/result.json)

```json
{
  "supercell_shape": [
    2,
    1,
    1
  ],
  "spin_length": 0.5,
  "sampling": {
    "burn_in_sweeps": 8,
    "equilibration_verified": false,
    "independent_initialization_each_temperature": true,
    "measurement_interval": 1,
    "measurement_sweeps": 32,
    "seed": 91
  }
}
```

- Diagnostic: {"kind": "effective_samples", "satisfied": false}
- Diagnostic: {"kind": "equilibration", "note": "Statistics alone do not certify equilibration.", "satisfied": false}

- Scope/limitation: Classical, not quantum Monte Carlo; local updates can be slow near transitions.
- Scope/limitation: Reported statistical errors do not establish equilibration or remove finite-size bias.

[Finite-temperature samples and errors](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-report/mc-thermodynamics.json)

## quantum

- Decision: Check low-energy residuals for the full finite quantum model.
- Execution: succeeded
- Scientific usability: usable_within_scope
- Result model: 1dbef8e38db3a86e1458f843ca3360664e5c38caff592ae43843b25b67364b16
- Task: quantum_low_energy

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-one-20261030-001/E-mc-quantum/steps/quantum/result.json)

```json
{
  "energy_per_site": -0.6000000000000002,
  "supercell_shape": [
    2,
    2,
    2
  ],
  "spin": 0.5,
  "eigenvalues": [
    -4.800000000000002,
    -4.800000000000001
  ],
  "residual_norms": [
    4.491785925587987e-14,
    2.6162114649541992e-15
  ],
  "hilbert_dimension": 256
}
```


- Scope/limitation: Exact finite-cluster Hamiltonian; iterative eigenpairs have the reported residuals.
- Scope/limitation: No thermodynamic-limit claim, no QMC, and no symmetry-sector compression.
- Scope/limitation: Hilbert-space vectors still grow exponentially with site count.

## Agent assessment

partial: Finite-cluster quantum eigenpairs converged; short MC samples do not establish equilibration.

Scope: Tiny finite periodic systems; temperatures in model energy units with k_B=1.

Limitations: ['These small calculations do not establish an infinite-system phase diagram.']

Evidence: [{"path": "calculation.sampling", "result_id": "mc"}, {"path": "calculation.residual_norms", "result_id": "quantum"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

- Compare independent seeds and longer burn-in/sampling; inspect finite-size effects.
