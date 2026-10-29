# Research report

Check the full cost before a mechanism study.

- Answer status: inconclusive
- Model status: ready
- Model identity: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/G-budget/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/G-budget/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/G-budget/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| small | bilinear_exchange_tensor (residual) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Mechanism studies

### couplings

Which interaction controls the frequency at the selected momentum?

- Preparation: ready
- Parent is current: True
- Full-model control: control
[Intervention plan and complete models](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/G-budget/mechanisms/couplings/record.json)

- anisotropy: Uniaxial exchange anisotropy. Terms: small
- exchange: The isotropic exchange background. Terms: exchange:0, exchange:1, exchange:2

| Point | Coupling multipliers | Model status |
| --- | --- | --- |
| control | {"anisotropy": 1.0, "exchange": 1.0} | ready |
| anisotropy-off | {"anisotropy": 0.0, "exchange": 1.0} | ready |
| anisotropy-half | {"anisotropy": 0.5, "exchange": 1.0} | ready |
| exchange-off | {"anisotropy": 1.0, "exchange": 0.0} | ready |
| exchange-half | {"anisotropy": 1.0, "exchange": 0.5} | ready |

## response

- Decision: Measure controlled responses and test the stated mechanism hypotheses.
- Execution: not_started
- Scientific usability: inconclusive
- Result model: ceff8be5ef317e92f82a3148f25f25ff394c7c9c503f0367d86d6012522978bf
- Task: mechanism_test

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/G-budget/steps/response/result.json)

Blocker: solver-run-budget-exhausted

```json
{}
```



## Agent assessment

inconclusive: The planned comparison requires more numerical jobs than the declared budget allows.

Scope: No numerical experiment launched.

Limitations: ['The declared resource budget is insufficient.']

Evidence: [{"path": "blocker", "result_id": "response"}]


## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

