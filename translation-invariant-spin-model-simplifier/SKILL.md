---
name: translation-invariant-spin-model-simplifier
description: Use when Codex needs to simplify a translation-invariant spin model from operator expressions, local-term matrices or tensors, or natural-language periodic-spin descriptions into a readable effective model with explicit ambiguity handling, fidelity reporting, and downstream classical, thermodynamic, or spin-wave analysis.
---

# Translation-Invariant Spin Model Simplifier

This skill uses a semi-interactive, fidelity-aware simplification workflow. It favors explicit ambiguity handling, preserves low-weight terms by default, and presents results as a readable main model plus residual structure instead of silently collapsing everything into an aggressively pruned template.

## Workflow

1. Read `reference/environment.md` and identify the baseline and backend-specific dependencies for the requested path.
2. Ask the user which baseline and optional dependencies are already installed before choosing execution paths.
3. If the input is natural-language, LaTeX, or a document-style source, read `reference/natural-language-input-protocol.md` and construct an intermediate extraction record before normalization.
4. Normalize the raw model with `scripts/input/normalize_input.py`.
5. Parse the lattice description with `scripts/input/parse_lattice_description.py`.
6. Infer candidate symmetries with `scripts/simplify/infer_symmetries.py`.
7. If any ambiguity would materially change the result, stop and return `interaction.status = needs_input` with one clarification question.
8. Decompose matrix or tensor local terms with `scripts/simplify/decompose_local_term.py`.
9. Canonicalize decomposed terms with `scripts/simplify/canonicalize_terms.py`.
10. Extract high-confidence readable blocks with `scripts/simplify/identify_readable_blocks.py`.
11. Assemble `H_main`, `H_low_weight`, and `H_residual` with `scripts/simplify/assemble_effective_model.py`.
12. Score fidelity with `scripts/simplify/score_fidelity.py`.
13. Generate 2-3 simplification views with `scripts/simplify/generate_simplifications.py`.
14. Ask the user to choose a view whenever an aggressive simplification would hide low-weight or residual structure.
15. Ask whether to project to a spin model if the current basis is not already explicit.
16. Present classical solver options and recommend one default.
17. Run classical ground-state and thermodynamics calculations with `scripts/classical/classical_solver_driver.py`, or use the pseudospin-orbital Sunny adapters when the input path is `many_body_hr`.
18. Run linear spin-wave analysis and optional small-cluster ED with `scripts/lswt/linear_spin_wave_driver.py`.
19. Render the final report with `scripts/output/render_report.py`.

## Input Notes

- Support operator expressions, local matrices or tensors, structured lattice input, natural-language, LaTeX, and document-style inputs through `reference/natural-language-input-protocol.md`, and a dedicated `many_body_hr` input mode for `POSCAR + hr.dat`-style pseudo-spin-orbital effective models.
- For supported spin-model text inputs, route LaTeX-like expressions and compact operator strings through one shared parser core before decomposition, rather than treating each syntax as a separate ad hoc path.
- Treat the current one-body and two-body simplification backbone as a `local_matrix_record` pipeline: extract or compile a local onsite / bond term, attach support, family, basis, and coordinate metadata, then decompose that local matrix deterministically.
- In the current phase, fully support `body_order <= 2` through this local-matrix backbone, and treat higher-body terms as future-facing schema / failure-path cases rather than silently forcing them into a fake bond interpretation.
- Support generic `n-body` operator monomials in the spin-`S` operator route, including higher-body terms that may remain outside the current readable-block library.
- When a supported operator expression can be parsed and canonicalized but not promoted into a trusted readable block, keep it as canonical residual structure instead of collapsing it to a raw opaque fallback.
- Assume translation invariance and a repeated local term `H = sum_i H_i`.
- Read `reference/environment.md` before solver selection, and treat it as the source of truth for baseline versus optional backend dependencies.
- Ask the user which baseline and optional dependencies are already installed before promising any execution path.
- Distinguish missing baseline dependencies from missing optional backend dependencies, and explain the difference clearly.
- Prefer exact parsing for common lattices and shell language; otherwise stop and ask instead of guessing.
- For `many_body_hr` inputs, treat the `hr.dat` object as a bond Hamiltonian on a two-site tensor-product space and use the fixed local basis order `|up, orb1>, |down, orb1>, |up, orb2>, |down, orb2>, ...`.
- For `many_body_hr` pseudospin-orbital inputs, preserve the legacy `orbital x spin(2)` / Kramers-style interpretation when that retained local-space semantics is actually intended, but allow an explicit generic retained-local-multiplet branch when the low-energy manifold is not a Kramers-doublet factorization.
- For these generic retained-local-multiplet inputs, treat the local basis as a retained-state index basis, build a Hermitian generator basis directly on the retained `N`-dimensional local space, and route the model through the `CP^(N-1)` Sunny / local-ray path rather than pretending there is a physical `spin x orbital` split.
- Keep the two Sunny families distinct in user-facing explanations and downstream choices:
  - spin-only Sunny LSWT is for explicit bilinear spin models with `classical_state.site_frames`
  - pseudospin-orbital Sunny `:SUN` / GSWT / thermodynamics routes are for `many_body_hr` models whose local classical-state manifold is represented as `CP^(N-1)` local rays
- For `many_body_hr` pseudospin-orbital inputs, the Sunny-backed classical option is `sunny-cpn-minimize`, and the Sunny thermodynamics options are `sunny-local-sampler`, `sunny-parallel-tempering`, and `sunny-wang-landau`.
- For these pseudospin-orbital Sunny `:SUN` paths, treat `CP^(N-1)` as a local-state / payload-manifold statement, not as a claim that the effective Hamiltonian is SU(`N`)-symmetric.
- If the retained local space is even-dimensional but physically still an arbitrary local multiplet, do not silently infer a Kramers-doublet factorization from dimension alone; require or preserve an explicit generic local-space choice instead.
- For these Sunny-backed pseudospin-orbital options, fail explicitly if `julia` or `Sunny.jl` is unavailable instead of silently falling back to the Python helpers.
- If the user requests a backend whose optional dependencies are missing, stop, explain the gap, and ask whether to install them or switch to an available alternative.
- Distinguish `detected_symmetries`, `user_required_symmetries`, and `allowed_breaking`.
- Treat canonical form as the internal source of truth.
- Low-weight terms are surfaced for user choice; they are not dropped automatically.
- For supported two-body local matrices, prefer matrix-driven physical interpretation over text-template guessing, including general exchange tensors, DM terms, and literature-specific anisotropic exchange parameterizations such as `Jzz`, `Jpm`, `Jpmpm`, and `Jzpm` when the matrix pattern justifies them.
- When explaining exchange-component subscripts such as `Jxx`, `Jxy`, `Jyz`, `Jzz`, `Jpm`, or `Jzpm`, interpret them in a fixed orthogonal spin-component frame `x,y,z` by default; do not reinterpret those subscripts as crystallographic `a,b,c` labels in user-facing explanations. If crystallographic directions matter, surface `a,b,c` separately as reference directions instead of overloading the exchange subscripts.
- Return `interaction.status = needs_input` whenever lattice interpretation, shell mapping, symmetry status, or simplification classification is ambiguous.
- Do not claim that a document-style natural-language input has been converted into a runnable model unless the intermediate extraction record has either landed in a supported payload or explicitly returned `interaction.status = needs_input`.
- Prefer a faithful readable model with explicit `residual` structure over an over-compressed Hamiltonian that hides unmatched or weak but meaningful terms.
- Read `reference/input-schema.md` for required normalized fields, `reference/natural-language-input-protocol.md` for broad text and document inputs, `reference/fallback-rules.md` whenever an unsupported or ambiguous branch is triggered, and `reference/environment.md` before environment-sensitive solver choices.

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
- Always surface environment blockers early rather than discovering them deep in the workflow.
