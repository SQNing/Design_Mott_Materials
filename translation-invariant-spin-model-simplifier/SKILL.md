---
name: translation-invariant-spin-model-simplifier
description: Simplify translation-invariant quantum spin Hamiltonians into human-friendly forms and run classical, thermodynamic, linear-spin-wave, and optional small-cluster exact-diagonalization workflows. Use when Codex needs to work from operator expressions, local-term matrices or tensors, or controlled natural-language descriptions of periodic spin models, especially when lattice geometry, shell-based exchange mapping, classical reference states, or first-stage LSWT checks are needed.
---

# Translation-Invariant Spin Model Simplifier

## Workflow

1. Normalize the raw model with `scripts/normalize_input.py`.
2. If normalization returns `interaction.status = needs_input`, stop and ask the user the reported clarification question before continuing.
3. Decompose matrix or tensor local terms with `scripts/decompose_local_term.py`.
4. Generate 2-3 simplification candidates with `scripts/generate_simplifications.py`.
5. Ask the user to choose a simplified Hamiltonian and mark one recommendation. Do not auto-select unless the user explicitly asks for automatic continuation.
6. Ask whether to project to a spin model if the current basis is not already explicit.
7. Present classical solver options and recommend one default. Use `scripts/decision_gates.py` to surface the next clarification question when the method or next stage has not been confirmed yet. Do not auto-run a stage unless the user explicitly says to auto-run or auto-continue.
8. Run classical ground-state calculations with `scripts/classical_solver_driver.py`.
9. Ask whether to continue to thermodynamics, linear spin wave, and optional small-cluster ED. Use the stage helpers in `scripts/decision_gates.py` so the workflow remains one-question-at-a-time instead of forcing a single all-in-one run.
10. Run thermodynamics with `scripts/classical_solver_driver.py` when the user confirms it.
11. Run linear spin-wave analysis and optional small-cluster ED with `scripts/linear_spin_wave_driver.py`, which validates explicit bilinear spin scope, builds an LSWT payload, and orchestrates a `Sunny.jl` backend when available.
12. Generate result plots with `scripts/render_plots.py`, including `lswt_dispersion.png`, `classical_state.png`, and a reusable `plot_payload.json`.
13. Render the final report with `scripts/render_report.py`.
14. When a durable run directory is desired, write the full result bundle with `scripts/write_results_bundle.py` so `report.txt`, plot files, and bundle metadata are materialized together.

## Input Notes

- Support operator expressions, local matrices or tensors, and controlled natural-language model descriptions.
- Assume translation invariance and a repeated local term `H = sum_i H_i`.
- Required normalized payload keys are: `system`, `local_hilbert`, `lattice`, `local_term`, `parameters`, `symmetry_hints`, `projection`, `timeouts`, `user_notes`, and `provenance`.
- `local_term.representation.kind` supports `operator`, `matrix`, and `natural_language`.
- Apply the default simplification in this order: merge symmetry-equivalent terms, prune terms that are parametrically small relative to the dominant coupling, then map the retained operator content onto a named template such as Heisenberg or XXZ when that mapping is faithful.
- Classical-method guidance: recommend `luttinger-tisza` for single-sublattice isotropic bilinear Heisenberg or XXZ-like models when its assumptions hold; otherwise recommend `variational`. Treat `annealing` as future scope, not a live implementation.
- Fallback rule: stop and ask whenever the model is ambiguous, out of supported scope, or needs a stage decision. Do not auto-continue unless the user explicitly asks for automatic continuation.
- LSWT method guidance: for a known classical ground state, default to a local-frame Holstein-Primakoff expansion plus paraunitary Bogoliubov diagonalization. If the helper scripts are too narrow for the model, say so and prefer an established package such as SpinW or Sunny.jl instead of forcing an uncontrolled approximation.
- The current controlled natural-language path extracts lattice kind, cell parameters, magnetic-atom fractional coordinates, shell-based `J1/J2/J3...` mappings, and basic solver hints. High-ambiguity cases surface `interaction.status = needs_input` instead of silently guessing.
- The current semi-interactive stage gates live in `scripts/decision_gates.py`. They cover the next classical-method question, whether to run thermodynamics, whether to continue to LSWT, how to choose the LSWT `q_path`, and whether to run optional small-cluster ED.
- The workflow is strictly semi-interactive by default: recommendations are allowed, but automatic continuation is only allowed when the user explicitly asks for it.
- For Heisenberg-like shell models, `scripts/lattice_geometry.py` can derive lattice vectors from cell parameters, enumerate neighbor shells from geometry, and map `J1/J2/J3...` to explicit bonds. If `exchange_mapping.shell_map` is present, use that override instead of assuming `J_n -> shell n`.
- Classical ground-state support currently includes `luttinger-tisza` and `variational`. Thermodynamic estimates use the Metropolis helper in `scripts/classical_solver_driver.py`. `annealing` is documented as a future method, not a live implementation.
- The current LT helper is limited to isotropic bilinear exchange and is best treated as a first-stage solver for single-sublattice Heisenberg/XXZ-like models.
- Treat the current LSWT path as first-stage support for explicit bilinear spin models with a classical reference state, not as a general solver for arbitrary many-body local terms.
- LSWT payload construction now derives lattice vectors when needed, distinguishes 1D/2D/3D from geometry plus connectivity, and auto-generates dense high-symmetry paths when the user does not provide `q_path`.
- The currently verified Sunny-backed success path is a one-sublattice ferromagnetic Heisenberg-like example with a consistent classical reference state and a short `q_path`.
- The currently verified plotting path covers the same minimal Sunny example and writes both image files and a reusable plotting payload.
- The current bundle-writing path can materialize a run directory containing `report.txt`, `plot_payload.json`, `lswt_dispersion.png`, `classical_state.png`, and a small bundle manifest.

## Output Requirements

- Always show 2-3 simplification candidates with trade-offs.
- Always state the recommendation and whether the user explicitly enabled automatic continuation.
- When normalization or later decision gates report `interaction.status = needs_input`, stop and ask the user the question before continuing to solver stages.
- Always list dropped terms, projection decisions, solver choices, and unsupported features.
- When using geometry-derived shell models, report how `J1/J2/J3...` were mapped to distance shells and call out any user-provided shell overrides.
- When discussing LSW for a known classical ground state, default to the local-frame Holstein-Primakoff plus paraunitary-Bogoliubov method unless you explicitly state that a narrower approximation is being used.
- If an open-source package such as SpinW or Sunny.jl is the better path for the current model, say so explicitly instead of pretending the in-skill helper scripts are sufficient.
- If `Sunny.jl` is unavailable or the model is outside first-stage bilinear scope, stop after the classical stage and explain the failure clearly instead of emitting a proxy scalar-exchange result.
- If the supplied classical reference state is not an energy minimum for the selected model, surface the backend instability clearly instead of coercing a dispersion from an unstable state.
- When plotting succeeds, preserve both the generated figure files and `plot_payload.json` so the same result can be redrawn later without rerunning the full workflow.
