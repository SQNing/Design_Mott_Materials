# Research report

Check the cost before launching a comparison.

- Answer status: pending
- Model status: ready
- Model identity: ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa
- Full source term count: 4
- Solver term count: 4
- Full-model coefficient weights are descriptive; physical reductions require separate comparisons.
- Default claim scope: finite calculations and the explicitly stated approximations.

## Model and conventions

[Original source](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/F-budget/models/model-0001/source.json)
[Model interpretation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/F-budget/models/model-0001/interpretation.json)

[Faithful term representation](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/F-budget/models/model-0001/readable.json)

All canonical terms remain in the solver Hamiltonian; no small-term deletion was performed.

Local spaces: {"space": {"dimension": 3, "kind": "unit_vector_sphere"}}

Units: {"energy": "dimensionless model units", "hbar": 1}

| Full-model term | Readable content | Sites and translations |
| --- | --- | --- |
| exchange:0 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |
| exchange:1 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 1, 0]}] |
| exchange:2 | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [0, 0, 1]}] |
| small | isotropic_exchange (main) | [{"site": 0, "translation": [0, 0, 0]}, {"site": 0, "translation": [1, 0, 0]}] |

## Proposed physical reductions

### drop

- Transformation: drop_terms
- Preparation: ready
- Parent is current: True
- Complexity: {"candidate_dimension": null, "candidate_terms": 3, "full_dimension": null, "full_terms": 4}
- A prepared candidate is not yet a validated approximation.
[Candidate and operator mapping](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/F-budget/reductions/drop/record.json)

- Limitation: Coefficient norms alone do not bound the requested observables.

## validate

- Decision: Check energy, correlations and harmonic excitations in the same finite cell.
- Execution: not_started
- Scientific usability: inconclusive
- Result model: ad008c1822c6d3f4126bc9614621338da8e834ad982080bdc4e69ef63b03edfa
- Task: reduction_validation

[Recorded evidence](/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-001/F-budget/steps/validate/result.json)

Blocker: solver-run-budget-exhausted

```json
{}
```



## Agent assessment

No explicit evidence-based assessment recorded. Successful execution does not complete the research question.

## Next decisions

Suggested actions are advisory; the host agent must choose settings and justify further computation.

