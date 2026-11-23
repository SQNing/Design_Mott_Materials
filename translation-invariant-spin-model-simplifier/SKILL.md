---
name: translation-invariant-spin-model-simplifier
description: Use when Codex needs to simplify a translation-invariant spin or pseudospin model from operator expressions, local-term matrices or tensors, structured model inputs, or broad text/document descriptions into a readable effective model with explicit ambiguity handling, fidelity reporting, and optional downstream classical, thermodynamic, or spin-wave analysis.
---

# Translation-Invariant Spin Model Simplifier

## Overview

Use this skill to turn a translation-invariant spin or pseudospin model into a
readable effective model and, when appropriate, continue into downstream
classical, thermodynamic, or spin-wave analysis.

This skill is written for expert or semi-skilled users, including users who
expect a strong agent to help route broad inputs into the repository's supported
backends. It is not a novice-first guided tutorial.

## Core Guarantees

- If any ambiguity would materially change the physical meaning, accepted model
  bond_label, or executable route, stop with `interaction.status = needs_input`.
- Do not silently guess physically important branches.
- Preserve the readable decomposition as
  `H_main + H_low_weight + H_residual`.
- Prefer explicit residual structure and unsupported-feature reporting over
  fake simplification.
- Surface environment blockers early, before promising unavailable backend
  paths.
- Do not silently replace a required Sunny-backed route with a different
  backend.
- Keep canonicalized structure as the internal source of truth when a readable
  block is incomplete or unavailable.
- Validate the complete canonical Hamiltonian against the structural space
  group before public solver execution. Strict failure stops the workflow.
- Only repair symmetry when the user explicitly requests `symmetry_repair: true`
  or `--symmetry-repair`; finite-group averaging must be followed by validation
  and a visible `hamiltonian-symmetry-repaired` warning when coefficients change.
- Never continue by silently lowering to the Hamiltonian's diagnostic symmetry
  subgroup, and never discard unsupported many-body terms to fit a solver.

## Workflow

For a research question that spans preparation, calculations, interpretation or
continuation, use the public Research workflow described in
[reference/research-workflow.md](reference/research-workflow.md). The host agent
chooses and explains each action. Read the recorded diagnostics before choosing
another calculation; do not treat a successful process as an answered question.
Use the existing individual commands for a narrowly requested one-stage task.

1. Identify the input route.
2. Check environment and execution constraints.
3. Land the input into a trusted normalized form.
4. Resolve material ambiguity before simplification.
5. Build the readable effective model.
6. Compile the complete canonical Hamiltonian and run the structural
   space-group gate.
7. Select a solver only if its capability covers every retained term.
8. Run optional downstream analysis when appropriate.
9. Report assumptions, limits, choices, hashes, and recommendations.

Stage-one simplification is a faithful readable view of the complete Hamiltonian.
No measured reconstruction error means null with assessment=not_assessed.
Coefficient weights do not validate physical reduction. Silence or a timeout
never authorizes projection, truncation, symmetry repair or a change of model.

For classical ground-state questions, read `ground_state_evidence` separately
from execution success and stationary-reference usability. A feasible state
that saturates its finite-cell numerical LT bound can support
`assess.claim_level=finite_cell_ground_state`; a stationary state alone cannot.
An unsaturated relaxed bound can be unattainable, so it is not by itself proof
of a wrong state. Default Fourier recovery tests local constraints and the full
energy before adding at most one optimization start, preserving the initial
search. No finite-cell result certifies the thermodynamic limit. See the
evidence levels and settings in `reference/research-workflow.md`.

When resuming interrupted work, inspect `time_accounting`: a last timing
checkpoint leaves an unmeasured tail, and a legacy timeout reservation is not
an exact measurement. Do not charge the host's subsequent idle time as solver
work or rewrite archived execution records to create a precise termination time.

For an authorized physical approximation, use `propose_reduction` followed by
`calculate/task=reduction_validation` as described in
[reference/physical-reductions.md](reference/physical-reductions.md). Supply the
selected full terms or local isometry, matched experiments and explicit observable
tolerances. Keep the complete Hamiltonian as the control. Read both
`scientific_status` and `validation_status`; a prepared candidate is not an
accepted approximation, and a reliable rejection can answer the research question.
Report the checked cells, momenta, energy window and observables with the verdict.
Never promote a candidate to the original model automatically.

For a mechanism question, use `propose_mechanism` and
`calculate/task=mechanism_test` from
[reference/mechanism-workflow.md](reference/mechanism-workflow.md). Declare the
interaction groups, coupling points, scalar observables and falsifiable
hypotheses. Keep all other groups at the full-model values when attributing a
response to one group. Read the fixed-state and relaxed-state energy diagnostics
before interpreting reference-dependent spectra. Report supporting evidence,
counterexamples, missing controls and the exact finite scope. A hypothesis
supported under these interventions is not a unique or universal mechanism.

## Output Contract

The final result should include:

- the recommended simplified result
- `H_main`, `H_low_weight`, and `H_residual`
- key assumptions and any unresolved limitations
- unsupported features or blocked routes
- the chosen solver or backend path, or the blocker that prevented it
- fidelity or reconstruction context when available
- structural target group, failed operations or repair changes, diagnostic
  subgroup status, input-model hash, and solver-model hash when the symmetry
  gate runs

Provide multiple simplification views when there are materially different
trusted views and the choice matters. Do not fabricate extra choices when one
faithful readable result is clearly preferable.

## Routing References

Use the repository reference docs to choose the current supported route:

- `reference/agent-routing.md`
- `reference/input-schema.md`
- `reference/natural-language-input-protocol.md`
- `reference/fallback-rules.md`
- `reference/environment.md`
- `reference/independent-research-handbook.md`

Treat those references as the detailed routing, schema, fallback, and
environment companions for this top-level contract.
