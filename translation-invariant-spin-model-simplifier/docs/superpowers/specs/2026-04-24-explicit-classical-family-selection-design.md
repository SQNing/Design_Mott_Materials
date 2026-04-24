# Explicit Classical Family Selection Design

## Goal

Move the `spin-only` versus `CP^(N-1)` decision to the earliest shared entry layer and make that decision explicit.

After this change, the program must not silently choose a classical manifold by default.

Every runnable classical path must first resolve one of:

- `spin-only`
- `cpn`

If the family is missing, ambiguous, or structurally inconsistent with the landed payload, the program must stop before any solver-specific builder runs.

## Problem

The current repository still decides the classical manifold too late and too indirectly.

Today, the decision is spread across several layers:

- some entrypoints expose explicitly spin-only flags, such as the document-reader bridge
- the pseudospin pipeline assumes `many_body_hr` implies the retained-local-multiplet / `CP^(N-1)` route
- downstream routing sometimes infers intent from state shape, such as `site_frames` versus `local_rays`
- solver metadata encodes `spin_only_explicit` versus `retained_local_multiplet`, but that happens after a route has already been chosen

This has three concrete problems:

1. the system still has implicit defaults instead of one explicit contract
2. `many_body_hr` is currently acting as both an input-format marker and a manifold-selection proxy
3. future non-spin-only inputs cannot cleanly reuse the `CP^(N-1)` route unless they impersonate `many_body_hr`

The user requirement is stricter:

- the program must confirm `spin-only` versus `CP^(N-1)` at the start
- the program must not fall back to a default manifold
- non-spin-only should be able to route to `CP^(N-1)` without being artificially restricted to `many_body_hr`

## Recommended Approach

Introduce one explicit shared contract:

- `classical_family = "spin-only" | "cpn"`

This field is the only authoritative statement of which classical manifold the run is allowed to use.

It should be resolved once at the earliest meaningful entry layer and then propagated through the rest of the workflow as stable metadata.

The recommended approach is not to make this field globally hard-required in every on-disk payload on day one.
Instead:

- every runnable entrypoint must resolve it explicitly before selecting any solver builder
- the field may come from CLI input, landed payload metadata, or bridge metadata
- if it cannot be resolved unambiguously, the entrypoint must stop

This preserves compatibility with existing structures while eliminating silent manifold defaults.

## Non-Goals

This design does not attempt to:

- unify every existing CLI into one command
- redesign the full document-reader normalization schema
- broaden spin-only solvers to non-spin-only models
- claim that every future non-spin-only payload is automatically valid for `CP^(N-1)`

The scope here is strictly about explicit manifold-family selection and early gating.

## Family Semantics

The family contract means:

### `spin-only`

The run is expected to produce a classical state in a spin-frame-style contract.

Typical properties:

- explicit spin vectors or spin frames
- spin-only classical solvers
- LSWT-compatible spin-frame downstream semantics

### `cpn`

The run is expected to produce a retained-local-multiplet classical state whose local manifold is `CP^(N-1)`.

Typical properties:

- local rays or equivalent retained-local-multiplet state data
- pseudospin / generic-multiplet classical solvers
- GSWT / Sunny pseudospin-style downstream semantics where structurally supported

This is intentionally a manifold-family contract, not an input-format contract.

`many_body_hr` may still be one input source for `cpn`, but it must stop being the defining identity of the route.

## Resolution Rules

Each runnable entrypoint must perform one shared resolution step before building a solver payload.

Resolution sources, in priority order:

1. explicit user request, such as CLI `--classical-family`
2. explicit landed payload metadata
3. explicit bridge metadata

Disallowed source:

- implicit fallback from input representation alone without recording an explicit resolved family

Resolution outcomes:

### Success

The resolver returns one normalized internal value:

- `spin_only_explicit`
- `retained_local_multiplet`

and also stores the user-facing family label:

- `spin-only`
- `cpn`

### Failure

The resolver must stop if:

- no explicit family is available
- multiple explicit sources disagree
- the requested family conflicts with the landed payload structure

Examples:

- a `spin-only` request against a payload that only contains retained-local-multiplet state data should fail
- a `cpn` request against a spin-only bridge payload with only spin-frame semantics should fail

## Where The Resolution Lives

Add one shared module under `scripts/common/`, for example:

- `classical_family_resolution.py`

This module should expose:

- normalization of `spin-only` and `cpn`
- extraction from supported payload metadata locations
- structural consistency checks
- one final resolved object used by all entrypoints

The main purpose is to prevent each CLI from inventing its own rules.

## Entry-Point Changes

### Document Reader Pipeline

`run_document_reader_pipeline.py` currently exposes explicitly spin-only bridge flags.

After this design:

- the document-reader path must resolve `classical_family` before building any classical bridge artifacts
- the existing spin-only bridge path should require or land `classical_family = spin-only`
- if a future non-spin-only bridge is added, it must land `classical_family = cpn` explicitly rather than relying on a downstream guess

The current `--emit-spin-only-solver-payload` and `--run-spin-only-classical-solver` flags can remain for compatibility, but internally they should be treated as explicit requests for the `spin-only` family.

### Pseudospin-Orbital Pipeline

`solve_pseudospin_orbital_pipeline.py` currently assumes the retained-local-multiplet route because it starts from `POSCAR + hr.dat`.

After this design:

- the entrypoint must first resolve `classical_family`
- the allowed family for the current payload shape is `cpn`
- if the family is absent, the run must stop instead of defaulting implicitly
- if the family is `spin-only`, the run must stop with a structural mismatch

This makes the route explicit without changing the fact that current `many_body_hr` payloads are structurally `cpn`-family payloads.

### Future Non-Spin-Only Entrypoints

Any future input path that is not spin-only should not need to masquerade as `many_body_hr`.

Instead, it should:

- land enough retained-local-multiplet metadata to satisfy the shared `cpn` structural checks
- resolve `classical_family = cpn`
- reuse the same downstream `CP^(N-1)` builder stack where valid

## Builder-Level Changes

### `build_sun_gswt_classical_payload(...)`

This builder currently hard-requires:

- `parsed_payload.input_mode == "many_body_hr"`

That is too narrow for the desired contract.

After this design, its gating should shift from input-family identity to classical-family identity plus structural requirements.

The builder should require:

- resolved `classical_family = cpn`
- retained-local-space metadata
- local dimension
- local basis labels
- pair interaction data in the expected tensorizable form

It may still accept current `many_body_hr` payloads as the first supported source, but it should stop using `many_body_hr` as the logical definition of the route.

### Spin-Only Builders

Spin-only builders should likewise require:

- resolved `classical_family = spin-only`

and reject `cpn` payloads early.

## Solver Routing Changes

Solver routing should no longer be the first place that tells us whether the run is spin-only.

Instead:

- family resolution happens first
- solver-method selection is validated against the resolved family

Examples:

- `variational`, `luttinger-tisza`, and `generalized-lt` are valid only for `spin-only`
- `restricted-product-state`, `cpn-local-ray-minimize`, `sunny-cpn-minimize`, `cpn-generalized-lt`, and `cpn-luttinger-tisza` are valid only for `cpn`

This means the existing `solver_family` metadata stays useful, but becomes a consistency check and reporting surface rather than the first semantic classifier.

## Downstream Routing Changes

Downstream routing may still use final state shape to decide backend details.

That is acceptable, but it should no longer be responsible for inferring the top-level manifold family.

Concretely:

- `site_frames` versus `local_rays` remains a valid state-shape distinction
- backend hints may still inspect `manifold` and `state_kind`
- but the run should already have a resolved family before downstream code executes

This removes a current ambiguity where downstream state-shape inference partly compensates for missing upstream family decisions.

## Error Handling

Error messages should be explicit and early.

Preferred failure shapes:

- `missing-classical-family`
- `conflicting-classical-family`
- `incompatible-classical-family`

Messages should name:

- the requested family, if any
- the payload source
- the structural reason the route cannot continue

Example:

`incompatible-classical-family: requested cpn, but the landed payload only exposes spin-only bridge bonds and spin-frame semantics`

## Compatibility Plan

This design should land in two phases.

### Phase 1: Explicit Resolution With Compatibility Shims

- add shared family resolver
- add explicit family option to relevant entrypoints
- map old spin-only bridge flags to `spin-only`
- map current pseudospin CLI contract to explicit `cpn`
- remove silent defaults inside those entrypoints

This phase changes behavior where ambiguity previously fell through to implicit routing.

### Phase 2: Broaden `cpn` Builder Inputs

- relax `build_sun_gswt_classical_payload(...)` away from `input_mode == "many_body_hr"`
- accept additional retained-local-multiplet payload sources once they satisfy the same structural contract

This phase is what enables “not spin-only implies `CP^(N-1)`” beyond the current `many_body_hr` source family.

## Testing Strategy

Add focused tests for:

1. family normalization
2. missing-family failure at entrypoints
3. conflicting explicit-family sources
4. structural mismatch failures
5. valid spin-only entry success
6. valid `cpn` entry success
7. builder rejection when family and payload structure disagree

Regression tests should cover at least:

- existing document-reader spin-only FeI2 path
- current `many_body_hr` pseudospin path
- one synthetic non-spin-only payload that is not labeled `many_body_hr` but satisfies the retained-local-multiplet contract, once Phase 2 lands

## Recommended First Implementation Slice

The first implementation slice should stop at Phase 1.

That gives the repository the semantic cleanup the user asked for:

- no silent default manifold choice
- explicit early `spin-only` versus `cpn` confirmation
- consistent error behavior

Only after that should the repository broaden `cpn` inputs beyond `many_body_hr`.

## Acceptance Criteria

This design is complete when:

- every runnable classical entrypoint resolves `classical_family` before choosing a solver builder
- ambiguous runs stop early instead of defaulting
- spin-only routes and `cpn` routes reject incompatible requests explicitly
- current `many_body_hr` runs remain valid under explicit `cpn`
- current document-reader spin-only bridge runs remain valid under explicit `spin-only`
- builder logic no longer treats `many_body_hr` as the conceptual definition of `CP^(N-1)` routing
