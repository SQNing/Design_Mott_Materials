---
name: translation-invariant-spin-model-simplifier
description: Simplify translation-invariant quantum spin Hamiltonians into human-friendly forms and run classical, thermodynamic, linear-spin-wave, and optional small-cluster exact-diagonalization workflows. Use when Codex needs to work from operator expressions, local-term matrices or tensors, or natural-language descriptions of periodic spin models, propose 2-3 simplification candidates, apply user-approved or default choices, and report assumptions, truncations, solver choices, and fallbacks.
---

# Translation-Invariant Spin Model Simplifier

## Workflow

1. Normalize the raw model with `scripts/normalize_input.py`.
2. Decompose matrix or tensor local terms with `scripts/decompose_local_term.py`.
3. Generate 2-3 simplification candidates with `scripts/generate_simplifications.py`.
4. Ask the user to choose a simplified Hamiltonian and mark one recommendation.
5. Ask whether to project to a spin model if the current basis is not already explicit.
6. Present classical solver options and recommend one default.
7. Run classical ground-state and thermodynamics calculations with `scripts/classical_solver_driver.py`.
8. Run linear spin-wave analysis and optional small-cluster ED with `scripts/linear_spin_wave_driver.py`.
9. Render the final report with `scripts/render_report.py`.

## Input Notes

- Support operator expressions, local matrices or tensors, and natural-language model descriptions.
- Assume translation invariance and a repeated local term `H = sum_i H_i`.
- Read `references/input-schema.md` for required normalized fields.
- Read `references/simplification-heuristics.md` before choosing a default candidate.
- Read `references/classical-methods.md`, `references/lsw-assumptions.md`, `references/lsw-method.md`, and `references/lsw-packages.md` before running solvers.
- Read `references/fallback-rules.md` whenever a timeout or unsupported-scope branch is triggered.

## Output Requirements

- Always show 2-3 simplification candidates with trade-offs.
- Always state the recommendation and any auto-choice timeout rule.
- Always list dropped terms, projection decisions, solver choices, and unsupported features.
- When discussing LSW for a known classical ground state, default to the local-frame Holstein-Primakoff plus paraunitary-Bogoliubov method unless you explicitly state that a narrower approximation is being used.
- If an open-source package such as SpinW or Sunny.jl is the better path for the current model, say so explicitly instead of pretending the in-skill helper scripts are sufficient.
