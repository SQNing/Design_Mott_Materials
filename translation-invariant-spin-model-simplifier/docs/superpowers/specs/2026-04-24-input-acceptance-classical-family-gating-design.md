# Input Acceptance Classical Family Gating Design

## Goal

Require every upstream input path to classify the run as either:

- `spin-only`
- `cpn`

at input acceptance time, before normalization, simplification, bridge building, or solver selection proceeds.

If the family is not already explicit and cannot be determined by the entry contract itself, the
entrypoint must stop immediately and ask the user which family they want.

This is stricter than the earlier classical-entrypoint design. The family decision must move all the
way to the front door.

## Problem

The repository now has an explicit classical-family contract at the classical workflow layer, but
that still leaves a weaker behavior upstream:

- broad inputs such as `natural_language`, `operator`, and `matrix` can still be accepted before the
  family is explicit
- different upstreams may still carry hidden assumptions about whether they are “really”
  spin-only or `CP^(N-1)`
- downstream normalization and bridge code may spend effort on payloads that should have been
  rejected or clarified earlier

This violates the user's stronger requirement:

- all upstreams must distinguish `spin-only` from `CP^(N-1)` when the information is first accepted
- broad ambiguous upstreams must ask first instead of inferring later
- no stage should continue on an unresolved family

## Recommended Approach

Introduce one mandatory input-acceptance gate:

- `classical_family = "spin-only" | "cpn"`

Every user-facing or orchestration-facing entrypoint must either:

1. resolve this immediately from the entry contract, or
2. return `interaction.status = needs_input` before doing further semantic work.

The key point is that “accepting input” now means “accepting input together with a classical family
decision”.

## Scope

This design applies to:

- `normalize_input.py`
- `simplify_text_input.py`
- `run_document_reader_pipeline.py`
- `solve_pseudospin_orbital_pipeline.py`
- `solve_cpn_payload_pipeline.py`
- agent/demo/orchestration wrappers that accept user model content

This design does not require one single CLI. It requires one single gating rule.

## Family Acceptance Rules

There are three kinds of upstream inputs.

### Type A: Family-Intrinsic Inputs

These are upstreams whose contract already fixes the family.

Examples:

- current `many_body_hr` / `POSCAR + hr.dat` pseudospin-orbital inputs:
  `classical_family = cpn`
- current document-reader spin-only bridge flags:
  `classical_family = spin-only`
- explicit parsed retained-local-multiplet payload JSON accepted by
  `solve_cpn_payload_pipeline.py`:
  `classical_family = cpn`

For these inputs, the entrypoint may resolve family immediately without an extra user question.

### Type B: Family-Explicit Inputs

These are inputs where the caller explicitly provides the family.

Examples:

- a future API field
  `classical_family`
- a CLI flag
  `--classical-family spin-only|cpn`

These are accepted immediately, but still must be structurally validated against the payload.

### Type C: Family-Ambiguous Inputs

These are broad inputs that do not, by themselves, determine whether the user intends a spin-only
or retained-local-multiplet interpretation.

Examples:

- broad `natural_language`
- generic `operator`
- generic `matrix`
- document-style inputs before the bridge family is fixed

These inputs must not proceed until family is explicit.

If the family is missing, they must return:

- `interaction.status = needs_input`
- an interaction id dedicated to classical-family choice
- options:
  - `spin-only`
  - `cpn`

## Input Acceptance Policy

The new rule is:

> No upstream may accept a model-carrying request into the semantic pipeline without an explicit
> classical family.

That means:

- no normalization without family
- no document bridge without family
- no simplification without family
- no solver payload construction without family

This is intentionally stricter than the current behavior.

## Entry-Point Design

### `normalize_input.py`

This becomes the main enforcement point for broad inputs.

Behavior:

- if the input family is intrinsically `many_body_hr`, resolve `classical_family = cpn`
- if the payload already includes explicit family metadata, preserve it and validate it
- if the input is broad `natural_language`, `operator`, or `matrix` without explicit family,
  return `needs_input` before deeper normalization continues

This changes `normalize_input.py` from “shape-only normalization” into “shape plus family
admission”.

### `simplify_text_input.py`

This must stop assuming that successful normalization is enough.

Behavior:

- if normalization returns `needs_input` because family is missing, surface that result unchanged
- do not continue into simplification

### `run_document_reader_pipeline.py`

Document-reader still has multiple internal stages, but it must not allow the model to progress
without an explicit family.

Behavior:

- spin-only bridge flags explicitly resolve `spin-only`
- a future `cpn` bridge path explicitly resolves `cpn`
- if the document content is otherwise broad or undecided, the pipeline must stop and ask for
  family before bridge selection

### `solve_pseudospin_orbital_pipeline.py`

This remains a family-intrinsic `cpn` entrypoint.

Behavior:

- resolve `cpn` immediately
- reject conflicting explicit `spin-only`

### `solve_cpn_payload_pipeline.py`

This remains a family-intrinsic or family-explicit `cpn` entrypoint.

Behavior:

- require or preserve `cpn`
- reject missing or conflicting family

## Interaction Contract For Ambiguous Inputs

For broad ambiguous inputs, the repository should return a stable interaction payload such as:

```json
{
  "status": "needs_input",
  "interaction": {
    "status": "needs_input",
    "id": "classical_family_selection",
    "question": "Should I interpret this model as spin-only or as a retained-local-multiplet CP^(N-1) model?",
    "options": ["spin-only", "cpn"]
  }
}
```

This interaction should happen before any model-family-specific decomposition or bridge logic.

## Structural Validation After Family Choice

Early family choice does not remove structural validation.

The two steps are:

1. choose family at input acceptance
2. validate that the payload really satisfies that family's contract

Examples:

- `spin-only` chosen for a retained-local-multiplet payload should still fail later with
  `incompatible-classical-family`
- `cpn` chosen for a document bridge that only supports spin-frame output should still fail unless a
  real `cpn` bridge exists

The new design prevents late guessing, not validation.

## Data Propagation

Once resolved, the family must be copied through:

- normalized payload
- simplification outputs
- bridge payloads
- parsed solver payloads
- classical result bundles

The family should become part of the persistent run story, not a transient local variable.

## Error Handling

Expected failure or interaction states:

- `needs_input` with `id = classical_family_selection`
- `missing-classical-family`
- `conflicting-classical-family`
- `incompatible-classical-family`

The repository should prefer `needs_input` when the issue is user choice and prefer `ValueError` or
equivalent hard failure when the issue is internal inconsistency or unsupported structure.

## Compatibility Plan

This should land in two stages.

### Stage 1: Input-Acceptance Family Gate

- make all broad upstreams require or ask for family before semantic processing
- preserve current family-intrinsic entrypoints
- add tests proving `needs_input` occurs before normalization/simplification continues

### Stage 2: Upstream Family-Specific Bridges

- expand actual `cpn` bridges for non-spin-only upstreams such as document-reader
- ensure those bridges land explicit `cpn` payloads without user hand-editing

## Testing Strategy

Add tests for:

1. `normalize_input.py` returns `needs_input` on broad ambiguous inputs with no family
2. `normalize_input.py` accepts explicit `spin-only`
3. `normalize_input.py` accepts explicit `cpn`
4. `many_body_hr` inputs still land directly as `cpn`
5. spin-only document-reader bridge still lands directly as `spin-only`
6. simplification pipeline does not continue when family selection is still pending
7. conflicting family inputs fail early

## Acceptance Criteria

This design is complete when:

- every upstream input path either resolves or requests `classical_family` at input acceptance
- ambiguous broad inputs stop with `needs_input` before deeper semantic processing
- no upstream silently defaults between `spin-only` and `cpn`
- family-intrinsic upstreams still work without unnecessary extra prompts
- downstream classical workflow continues to consume already-resolved family metadata
