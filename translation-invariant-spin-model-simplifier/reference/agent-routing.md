# Agent Routing for `translation-invariant-spin-model-simplifier`

This document is the repository-specific routing companion for the top-level
skill. It tells an expert-capable agent how to choose among the currently
supported input, landing, family, backend, and reporting paths without turning
the top-level `SKILL.md` into a monolithic runbook.

## Input Classes

The current repository supports these input classes:

- operator expressions
- local matrices or tensors
- structured lattice or model inputs
- natural-language or document-style inputs
- `many_body_hr`
- already landed payloads

## Routing By Input Class

Use the input class to choose the first shared backbone:

- operator expressions
  Route through the shared operator-expression normalization path, then into
  deterministic decomposition, canonicalization, readable-block extraction, and
  effective-model assembly.
- local matrices or tensors
  Route through the local-matrix-record path before decomposition and readable
  simplification.
- structured lattice or model inputs
  Route directly into normalization plus lattice interpretation, then continue
  through the shared simplification/report backbone.
- natural-language or document-style inputs
  Start with deterministic extraction and consult
  `reference/natural-language-input-protocol.md` before attempting broader
  landing.
- `many_body_hr`
  Treat this as the pseudospin-orbital retained-local-multiplet route rather
  than a generic spin-only text-input path.
- already landed payloads
  Preserve the landed contract and choose the downstream solver/report path that
  matches the existing payload family.

If route selection remains physically ambiguous, stop at
`interaction.status = needs_input` instead of guessing.

## Agent-Assisted Landing

Document and broad-text routes remain deterministic-first.

- Use rule-based extraction first.
- Escalate to `agent_normalization_request` only when the current parser cannot
  land a trustworthy runnable payload on its own.
- Treat `agent_normalized_document` as a constrained handoff product, not a
  freeform replacement schema.
- Use the agent to narrow or explain missing information, but keep material
  ambiguity at `needs_input`.

The main helper entrypoints for this family are:

- `scripts/cli/normalize_document_with_agent.py`
- `scripts/cli/run_document_reader_pipeline.py`
- `scripts/cli/orchestrate_agent_document_normalization.py`
- `scripts/cli/run_agent_document_normalization_demo.py`

## Classical Family Resolution

The current public classical families are:

- `spin-only`
- `cpn`

Routing rules:

- broad text, operator, matrix, and document entrypoints must not silently pick
  between `spin-only` and `cpn`
- family-intrinsic routes may resolve immediately
- family-explicit payloads or flags should be preserved and validated
- unresolved family choice must remain a `needs_input` interaction

## Backend And Solver Routing

After landing and family resolution, choose the solver path that matches both
the family and the available environment.

- generic classical workflows use the shared classical solver drivers
- explicit spin-bilinear Sunny LSWT remains separate from retained-local-space
  Sunny `:SUN` / GSWT / thermodynamics routes
- `many_body_hr` pseudospin-orbital classical routing uses
  `sunny-cpn-minimize`
- available Sunny thermodynamics routes include
  `sunny-local-sampler`, `sunny-parallel-tempering`, and
  `sunny-wang-landau`
- `cpn-generalized-lt` is conditionally final:
  it may be final when `solver_role == "final"`, but must remain
  diagnostic-only when it is only acting as a lower-bound or seed stage

Do not silently substitute a different backend when the requested Sunny-backed
route is unavailable.

## Current Semantic Conventions

The current repository semantics include several important conventions:

- `many_body_hr` is routed as a retained-local-multiplet / pseudospin-orbital
  path
- the default retained-local basis semantics for that route are
  `generic-multiplet`
- preserve `orbital-times-spin` style interpretation only when that semantics
  is explicitly intended
- `CP^(N-1)` here describes the local-state / payload manifold, not a blanket
  claim that the effective Hamiltonian is SU(`N`) symmetric
- exchange-component subscripts such as `Jxx`, `Jxy`, `Jyz`, `Jzz`, `Jpm`, and
  `Jzpm` should be explained in a fixed orthogonal spin frame unless a separate
  crystallographic convention is made explicit

## Recommended Entrypoints

Prefer the following current repository entrypoints:

- `scripts/cli/simplify_text_input.py`
  for broad text-to-simplification expert workflows
- `scripts/cli/run_document_reader_pipeline.py`
  for end-to-end document-reader orchestration
- `scripts/cli/normalize_document_with_agent.py`
  when the document route needs constrained agent assistance
- `scripts/cli/solve_pseudospin_orbital_pipeline.py`
  for `many_body_hr` pseudospin-orbital workflows
- `scripts/cli/solve_cpn_payload_pipeline.py`
  for explicit retained-local-multiplet / `CP^(N-1)` payload JSON that is not
  entering through `POSCAR + hr.dat`

These entrypoints are current routing recommendations, not the stable user-level
contract of the top-level skill.

## Related References

Read these alongside this routing guide when needed:

- `reference/input-schema.md`
- `reference/natural-language-input-protocol.md`
- `reference/fallback-rules.md`
- `reference/environment.md`
