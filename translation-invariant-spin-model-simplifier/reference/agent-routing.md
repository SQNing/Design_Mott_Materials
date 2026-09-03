# Agent Routing for `translation-invariant-spin-model-simplifier`

This document is the repository-specific routing companion for the top-level
skill. It tells an expert-capable agent how to choose among the currently
supported input, landing, bond_label, backend, and reporting paths without turning
the top-level `SKILL.md` into a monolithic runbook.

For the public reference contract, treat `lattice_structure` as the primary
conceptual object. `bond_label`, `model_bond_label`, and related route labels remain
legacy compatibility data for adapters and validation, not the main organizing
object of the normalized model.

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
  through the shared simplification/report backbone with Hamiltonian content
  attached as site, bond, or higher-body terms on `lattice_structure`.
- natural-language or document-style inputs
  Start with deterministic extraction and consult
  `reference/natural-language-input-protocol.md` before attempting broader
  landing.
- `many_body_hr`
  Treat this as the pseudospin-orbital retained-local-multiplet route rather
  than a generic spin-only text-input path.
- already landed payloads
  Preserve the landed contract and choose the downstream solver/report path that
  matches the existing payload bond_label.

If route selection remains physically ambiguous, stop at
`interaction.status = needs_input` instead of guessing.

## Pre-Solver Hamiltonian Symmetry Gate

After landing and before capability or solver selection, compile the complete
Hamiltonian into `canonical-hamiltonian/v1` and target the structure's full
space group. The default route is validate-only. On failure, return the failed
operations and the verified diagnostic subgroup, suggest `--symmetry-repair`,
and stop with no solver backend invoked. Do not use the diagnostic subgroup as
an automatic fallback.

When the user explicitly enables repair, average the full canonical coefficient
map over the finite target group, revalidate it, and route only the validated
solver model. Preserve both hashes. Then match solver capability against every
term family and arity; an unsupported ring or other higher-body term produces
`solver-capability-mismatch`, never a truncated bilinear calculation.

## Broad-Text Escalation Checklist

When the user starts from broad text rather than an intrinsic file-backed route,
use this checklist before choosing between staying `spin-only`, escalating
toward retained-local-multiplet handling, or stopping for clarification.

### Evidence that usually supports staying `spin-only`

- the request is phrased in ordinary spin-model language without an explicit
  retained-local-space construction
- the main content is exchange-like operator structure on a conventional spin
  lattice
- weak anisotropy, bond-dependent exchange, or low-weight symmetry-lowering
  terms are present, but the text still reads as a spin Hamiltonian rather than
  as an on-site multiplet reduction problem
- there is no intrinsic `many_body_hr`-style file pair or explicit retained
  local-space payload

### Evidence that should trigger escalation

- the input explicitly supplies `POSCAR + hr.dat` or another clear
  `many_body_hr`-style retained-local-space route
- the text centers on retained local multiplets, local-ray states, or a
  pseudospin-orbital reduction rather than on a conventional spin model
- the intended semantics depend on preserving a nontrivial local-space
  interpretation such as `generic-multiplet` or an explicitly requested
  `orbital-times-spin` route
- the user is already asking for Sunny-backed retained-local-multiplet
  classical or thermodynamic workflows

### Evidence that should stop at `needs_input`

- missing detail alone is not evidence that retained-local-multiplet handling is required
- the text mixes ordinary spin-model notation with retained-local-multiplet or
  pseudospin language strongly enough that the bond_label choice would change the
  executable route
- the user-facing description leaves unresolved whether the intended object is a
  conventional spin Hamiltonian or a retained-local-space effective model
- the available evidence is suggestive but not sufficient to justify either
  `spin-only` or `cpn` explicitly

## Agent-Assisted Landing

Document and broad-text routes remain deterministic-first.

- Use rule-based extraction first.
- Escalate to `agent_normalization_request` only when the current parser cannot
  land a trustworthy runnable payload on its own.
- Treat `agent_normalized_document` as a constrained handoff product, not a
  freeform replacement schema.
- Use the agent to narrow or explain missing information, but keep material
  ambiguity at `needs_input`.

The main helper entrypoints for this bond_label are:

- `scripts/cli/normalize_document_with_agent.py`
- `scripts/cli/run_document_reader_pipeline.py`
- `scripts/cli/orchestrate_agent_document_normalization.py`
- `scripts/cli/run_agent_document_normalization_demo.py`

## Agent-Assisted Landing Audit

Use this section to keep document assistance auditable.

### What agent assistance may transform

- rewrite broad document content into the constrained
  `agent_normalized_document` schema expected by the repository
- normalize notation, organize evidence spans, and align model candidates with
  the shared intermediate-record structure
- narrow non-critical missing fields when the deterministic-first route already
  supports that inference safely

### What agent assistance must preserve

- the bond_label status at the time assistance begins
- the evidence-backed distinction between extracted content and inferred content
- the source-side cues needed to explain how the normalized artifact was formed
- the fact that `agent_normalization_request` is a bounded normalization step,
  not a license to silently choose a different physical bond_label

### What still forces `needs_input`

- unresolved `spin-only` versus `cpn` bond_label choice when that choice changes
  the executable route
- competing model candidates or coordinate conventions that would materially
  change the landed payload
- any case where the current parser plus bounded agent help still cannot land a
  trustworthy runnable payload without making a physical guess

## Classical Bond Label Resolution

The current public classical families are:

- `spin-only`
- `cpn`

Routing rules:

- broad text, operator, matrix, and document entrypoints must not silently pick
  between `spin-only` and `cpn`
- bond_label-intrinsic routes may resolve immediately
- bond_label-explicit payloads or flags should be preserved and validated
- unresolved bond_label choice must remain a `needs_input` interaction
- once routing is resolved, preserve any resulting bond_label labels only as legacy
  compatibility data alongside the primary `lattice_structure`-based contract

## Backend And Solver Routing

After landing and bond_label resolution, choose the solver path that matches both
the bond_label and the available environment.

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
