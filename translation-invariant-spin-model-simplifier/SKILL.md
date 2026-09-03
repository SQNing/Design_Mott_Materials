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

Treat those references as the detailed routing, schema, fallback, and
environment companions for this top-level contract.
