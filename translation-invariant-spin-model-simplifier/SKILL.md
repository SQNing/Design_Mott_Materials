---
name: translation-invariant-spin-model-simplifier
description: Simplify translation-invariant quantum spin Hamiltonians into human-friendly forms and run classical, thermodynamic, linear-spin-wave, and optional small-cluster exact-diagonalization workflows. Use when Codex needs to work from operator expressions, local-term matrices or tensors, or natural-language descriptions of periodic spin models, propose 2-3 simplification candidates, apply user-approved or default choices, and report assumptions, truncations, solver choices, and fallbacks.
---

# Translation-Invariant Spin Model Simplifier

This skill uses a semi-interactive, fidelity-aware simplification workflow. It favors explicit ambiguity handling, preserves low-weight terms by default, and presents results as a readable main model plus residual structure instead of silently collapsing everything into an aggressively pruned template.

## Workflow

1. Normalize the raw model with `scripts/normalize_input.py`.
2. Parse the lattice description with `scripts/parse_lattice_description.py`.
3. Infer candidate symmetries with `scripts/infer_symmetries.py`.
4. If any ambiguity would materially change the result, stop and return `interaction.status = needs_input` with one clarification question.
5. Decompose matrix or tensor local terms with `scripts/decompose_local_term.py`.
6. Canonicalize decomposed terms with `scripts/canonicalize_terms.py`.
7. Extract high-confidence readable blocks with `scripts/identify_readable_blocks.py`.
8. Assemble `H_main`, `H_low_weight`, and `H_residual` with `scripts/assemble_effective_model.py`.
9. Score fidelity with `scripts/score_fidelity.py`.
10. Generate 2-3 simplification views with `scripts/generate_simplifications.py`.
11. Ask the user to choose a view whenever an aggressive simplification would hide low-weight or residual structure.
12. Ask whether to project to a spin model if the current basis is not already explicit.
13. Present classical solver options and recommend one default.
14. Run classical ground-state and thermodynamics calculations with `scripts/classical_solver_driver.py`.
15. Run linear spin-wave analysis and optional small-cluster ED with `scripts/linear_spin_wave_driver.py`.
16. Render the final report with `scripts/render_report.py`.

## Input Notes

- Support operator expressions, local matrices or tensors, structured lattice input, and controlled natural-language lattice or model descriptions.
- Assume translation invariance and a repeated local term `H = sum_i H_i`.
- Prefer exact parsing for common lattices and shell language; otherwise stop and ask instead of guessing.
- Distinguish `detected_symmetries`, `user_required_symmetries`, and `allowed_breaking`.
- Treat canonical form as the internal source of truth.
- Low-weight terms are surfaced for user choice; they are not dropped automatically.
- Return `interaction.status = needs_input` whenever lattice interpretation, shell mapping, symmetry status, or simplification classification is ambiguous.
- Prefer a faithful readable model with explicit `residual` structure over an over-compressed Hamiltonian that hides unmatched or weak but meaningful terms.
- Read `reference/input-schema.md` for required normalized fields and `reference/fallback-rules.md` whenever an unsupported or ambiguous branch is triggered.

## Output Requirements

- Always show 2-3 simplification candidates with trade-offs.
- Always present the readable result as `H_main + H_low_weight + H_residual`.
- Always state the recommendation and whether aggressive simplification was user-approved.
- Always list low-weight terms, residual terms, projection decisions, solver choices, and unsupported features.
- Always include a fidelity report with reconstruction and weight-coverage summaries.
- If a low-weight term is the only visible source of symmetry breaking, warn the user before demoting or dropping it.
- Always prefer surfacing ambiguity, residual structure, and symmetry-sensitive weak terms over silently pruning them away.
- When discussing LSW for a known classical ground state, default to the local-frame Holstein-Primakoff plus paraunitary-Bogoliubov method unless you explicitly state that a narrower approximation is being used.
- If an open-source package such as SpinW or Sunny.jl is the better path for the current model, say so explicitly instead of pretending the in-skill helper scripts are sufficient.
