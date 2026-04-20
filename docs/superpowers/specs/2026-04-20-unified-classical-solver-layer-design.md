# Unified Classical Solver Layer Design

## Goal

Introduce a unified `Classical Solver Layer` for effective-Hamiltonian solving in
`translation-invariant-spin-model-simplifier`, so that:

- all supported effective Hamiltonians first enter one classical-ground-state layer
- classical methods are listed in parallel, but each declares its role and applicability
- all final classical solvers emit one standardized `classical_state_result`
- downstream spin-wave and thermodynamics stages consume that standardized output instead of method-specific payloads

The architectural target is:

```text
effective Hamiltonian
  -> normalized solver family
  -> classical solver layer
  -> standardized classical output
  -> downstream spectrum and thermodynamics layers
```

This change is about solver architecture and interface unification. It is not a
proposal to remove physically distinct solver families or to force every model
through every solver.

## Implementation Status

The first contract-convergence stage and the planned phase-2 completion cleanup
of this design have now been landed in the repository.

Implemented in code:

- shared `classical_state_result` helpers and schema tests
- shared classical-contract resolution helpers for:
  - `classical_state_result`
  - standardized `classical_state_result.classical_state`
  - per-stage `downstream_compatibility` status lookups
- additive spin-only classical adapters for:
  - `spin-only-variational`
  - `spin-only-luttinger-tisza`
  - `spin-only-generalized-lt`
- additive pseudospin classical adapters for:
  - `pseudospin-cpn-local-ray-minimize`
  - `pseudospin-sunny-cpn-minimize`
  - diagnostic-only `pseudospin-cpn-generalized-lt`
  - diagnostic-only `pseudospin-cpn-luttinger-tisza`
- downstream bundle orchestration now prefers the standardized contract for:
  - classical-stage presence detection
  - LSWT / GSWT / thermodynamics auto-run gating
  - stage summaries and output manifests
- report and plot layers now surface standardized classical metadata:
  - `method`
  - `role`
  - `solver_family`
  - `downstream_compatibility`
- LSWT decision gates now prefer standardized compatibility and standardized
  LT-family method detection
- rotating-frame realization now resolves standardized supercell metadata before
  legacy nested fallbacks
- LSWT / Python-GLSWT / Sunny-GSWT payload builders now accept
  `classical_state_result.classical_state` as a standardized upstream classical
  reference
- auxiliary Python-GLSWT / single-q workflows now consume standardized contract
  inputs for:
  - bare `classical_state_result` payloads
  - top-level wrapper payloads
  - nested `payload["classical"]` bundle shapes
  while still preserving rich single-q metadata needed by the
  `single-q-unitary-ray` path
- shared classical reference payload helpers now centralize rich single-q
  wrapper normalization so Python-GLSWT builders, auxiliary single-q adapters,
  and convergence drivers no longer need independent wrapper heuristics
- pseudospin bundle export now treats `classical_state_result` as the
  authoritative classical contract, with raw top-level `classical_state`
  retained only as a compatibility mirror
- LSWT payload construction and rotating-frame realization now consume shared
  classical ordering / supercell helpers instead of carrying local raw-field
  crawling logic
- report and plot rendering now treat standardized classical metadata as
  authoritative whenever a standardized contract exists, and use legacy
  `chosen_method` only as a compatibility fallback when no standardized
  contract is present
- results-bundle stage manifests now preserve `chosen_method` and
  `requested_method` only as compatibility mirrors while keeping canonical
  `method`, `role`, `solver_family`, and `downstream_compatibility` sourced
  from the standardized contract
- the current targeted regression slice for this convergence work passes with
  120 tests covering contract resolution, bundle/report/plot rendering, LSWT /
  GLSWT payload builders, rotating-frame helpers, and auxiliary single-q
  workflows

Not yet fully migrated:

- legacy `classical_state` and `chosen_method` fields are still emitted in
  parallel for backward compatibility with older scripts and artifacts
- some helper paths still allow carefully scoped legacy fallback precedence when
  no standardized contract is present
- repository-wide operation is now strongly contract-first and much closer to
  contract-only internally, but emitted artifacts and compatibility shims still
  deliberately preserve legacy mirrors

### Next Migration Frontier

The next likely cleanup steps after this stage are:

- reduce remaining compatibility-only legacy mirrors once downstream callers no
  longer depend on them, especially at CLI/artifact boundaries
- decide whether to make some CLI and artifact-loading surfaces fully
  standardized internally while keeping compatibility translation only at
  explicit read/write edges
- expand regression coverage beyond the current contract-convergence slice to
  catch future drift in less frequently used solver-entry paths
- continue the broader unified-classical-solver-layer roadmap above the
  contract level, especially solver-family routing and later downstream-stage
  convergence

## Current State

The repository already supports two strong, but separate, solving lines.

### 1. Explicit Spin-Only Effective Hamiltonians

Current support is strongest for explicit spin-only periodic models, especially
for bilinear Hamiltonians with classical reference frames.

Relevant code paths include:

- `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/build_lswt_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`

Current classical methods in this family are:

- `variational`
- `luttinger-tisza`
- `generalized-lt`

Current downstream support in this family is:

- classical ground state
- spin-only Sunny LSWT for explicit bilinear spin Hamiltonians with `classical_state.site_frames`
- a Python-side classical thermodynamics estimation path

### 2. `many_body_hr` Pseudospin-Orbital / Retained-Local-Multiplet Hamiltonians

The repository also contains a strong solving line for projected local-multiplet
models coming from `many_body_hr`.

Relevant code paths include:

- `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/build_sun_gswt_classical_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/cpn_generalized_lt_solver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/cpn_local_ray_solver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/python_glswt_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py`

Current public classical methods in this family are:

- `restricted-product-state`
- `sun-gswt-cpn`
- `sun-gswt-single-q`
- `cpn-local-ray-minimize`
- `sunny-cpn-minimize`
- `cpn-generalized-lt`
- `cpn-luttinger-tisza`

Current downstream support in this family is:

- classical ground state on the local `CP^(N-1)` manifold
- GSWT-like spectrum calculations through Python and Sunny backends
- Sunny thermodynamics through:
  - `sunny-local-sampler`
  - `sunny-parallel-tempering`
  - `sunny-wang-landau`

### 3. Current Structural Problem

The repository is not missing solver capability as much as it is missing a
unified solver interface.

Today, the main structural problems are:

- physically different solver roles are mixed together as flat method choices
- some methods are final classical solvers, some are diagnostics, and some are specialized ansatz routes
- downstream stages still reason too much about method-specific payload structure
- the generic spin-`S` operator/local-matrix path is stronger on normalization and simplification than on a fully unified solving path

## User-Approved Direction

The approved direction for this design is:

- use a unified `Classical Solver Layer`
- keep classical methods listed in parallel
- require that every supported effective Hamiltonian enter some classical route
- require that successful final classical results feed downstream GLSPW / GSWT / LSWT or thermodynamics through a standardized interface

Important clarification:

- the design does **not** require that every Hamiltonian be compatible with every classical method
- instead, every supported Hamiltonian must be routable to at least one appropriate classical family
- solver applicability must be explicit and machine-readable

## Design Principles

### 1. One Classical Entry Layer

All solver-ready effective Hamiltonians must first enter a shared classical
solver layer before any spectrum or thermodynamics stage is launched.

There should be no direct bypass from normalized effective-Hamiltonian payloads
to GSWT/LSWT/thermodynamics that skips classical-state normalization.

### 2. Parallel Methods, Explicit Roles

Classical methods should still be shown in parallel at the user-facing level,
but each must declare one of the following roles:

- `final`
- `diagnostic`
- `specialized`

This prevents lower-bound or seed methods from being silently presented as final
classical solvers.

### 3. Standardized Classical Output

All final classical solvers must emit a shared result contract called
`classical_state_result`.

Downstream stages must consume this shared contract rather than method-specific
internal fields.

### 4. Downstream Compatibility Must Be Explicit

Each classical result must declare whether it is ready for:

- LSWT
- GSWT / GLSPW
- thermodynamics

The compatibility statement must be carried in the classical result itself,
along with blocking reasons where applicable.

## Architecture

The target architecture is a four-layer model.

### Layer 1: Normalized Effective Hamiltonian

This layer represents the already-obtained effective Hamiltonian in a canonical
solver-facing form.

Its responsibilities include:

- local-space dimension and retained-space semantics
- lattice and bond metadata
- operator/body-order support
- explicit spin-only vs generic retained-local-space semantics
- enough metadata to decide solver family

This layer does not choose a solver directly.

### Layer 2: Classical Solver Family Routing

This layer maps a normalized effective Hamiltonian into one solver family.

The design introduces the following family taxonomy.

#### `family = spin_only_explicit`

Use for:

- explicit spin-component Hamiltonians
- bilinear periodic spin models
- models that can produce a trusted spin-frame classical reference

Public final methods in this family:

- `spin-only-variational`
- `spin-only-luttinger-tisza`
- `spin-only-generalized-lt`

#### `family = retained_local_multiplet`

Use for:

- `many_body_hr` pseudospin-orbital models
- generic retained local multiplets
- models more naturally described on a local `CP^(N-1)` manifold than as explicit three-component spins

Public final methods in this family:

- `pseudospin-restricted-product-state`
- `pseudospin-cpn-local-ray-minimize`
- `pseudospin-sunny-cpn-minimize`

#### `family = diagnostic_seed_only`

Use for:

- lower-bound calculations
- ordering hints
- preconditioner generation

Public diagnostic methods in this family:

- `pseudospin-cpn-generalized-lt`
- `pseudospin-cpn-luttinger-tisza`

These methods remain available and parallel, but must be labeled as
`diagnostic`, not `final`.

#### `family = specialized_classical_ansatz`

Use for:

- strong ansatz-based classical routes
- cases where the classical solver is already tied to a narrower manifold or
  ordering form

Public specialized methods in this family:

- `pseudospin-sun-gswt-cpn`
- `pseudospin-sun-gswt-single-q`

These methods should stay available but must not be presented as the default
general-purpose classical routes.

### Layer 3: Unified Classical Solver Layer

All methods above register into one classical solver layer with:

- method id
- family id
- role
- applicability predicate
- result adapter

Conceptually, each solver should expose something like:

```text
supports(model) -> bool
run(model, settings) -> result
```

### Layer 4: Downstream Solver Layers

Downstream stages consume standardized classical output rather than upstream
method names.

Two downstream groups are in scope:

- `Spin-Wave Layer`
  - spin-only LSWT
  - pseudospin Python GSWT
  - pseudospin Sunny GSWT
  - future GLSPW-compatible stages

- `Thermodynamics Layer`
  - spin-only classical thermodynamics
  - Sunny `CP^(N-1)` thermodynamics backends
  - future additional thermal backends

## Unified Classical Output Contract

### `classical_state_result`

All final classical methods must emit one standardized object with at least the
following fields:

- `status`
  - `ok | needs_review | unsupported`
- `solver_family`
- `method`
- `role`
- `classical_state`
- `energy`
- `supercell_shape`
- `ordering`
- `diagnostics`
- `downstream_compatibility`

### `classical_state`

`classical_state` is the payload downstream stages consume. It must support at
least the currently relevant representations:

- spin-frame classical states for spin-only LSWT-compatible models
- local-ray / `CP^(N-1)` classical states for pseudospin-orbital GSWT and Sunny thermodynamics

This contract should preserve existing useful structure such as:

- `site_frames`
- `local_rays`
- `ordering`
- `schema_version`
- basis-order metadata when relevant

### `diagnostics`

Diagnostics must be normalized enough that downstream and report layers can
reason about solver quality uniformly. Candidate fields include:

- constraint residual
- stationarity residual
- supercell convergence summary
- ordering confidence / interpretation
- preconditioner provenance

### `downstream_compatibility`

Each result must carry an explicit compatibility matrix:

- `lswt`
- `gswt`
- `glspw`
- `thermodynamics`

Each entry should contain:

- `status = ready | blocked | review`
- `reason`
- `recommended_backend`

This is the main mechanism that decouples downstream stages from upstream method
names.

## Diagnostic Result Contract

Diagnostic-only methods should not pretend to emit final classical states.
Instead, they should emit a different contract carrying:

- `lower_bound`
- `seed_candidate`
- `ordering_hint`
- `projector_exactness`
- `recommended_followup`

Diagnostic results may still be registered in the same layer, but they must
never automatically set downstream spectrum or thermodynamics readiness to
`ready`.

## Downstream Consumption Rules

### Spin-Wave Layer

All spin-wave-like stages must consume `classical_state_result`, not method
names.

The spin-wave router should use compatibility and state semantics:

- if `downstream_compatibility.lswt.status == ready`, route to spin-only LSWT
- if `downstream_compatibility.gswt.status == ready`, route to Python or Sunny GSWT
- if future `glspw` stages are added, they should follow the same rule

Blocked cases must return structured reasons, for example:

- missing spin-frame classical reference
- missing `CP^(N-1)` local-ray state
- unsupported ordering type

### Thermodynamics Layer

Thermodynamics stages must also consume `classical_state_result`.

The thermodynamics router should use:

- `thermodynamics.status`
- manifold / representation semantics from `classical_state`
- backend availability

This means:

- spin-only thermal routes depend on spin-compatible classical states
- Sunny pseudospin-orbital thermal routes depend on valid `CP^(N-1)` local-ray classical states

The thermodynamics stage must no longer rely on method-name checks such as
```
classical_method == "sunny-cpn-minimize"
```
as the primary compatibility gate.

## Support Matrix After Refactor

The target support story becomes:

- every supported effective Hamiltonian enters one normalized family
- every family exposes parallel classical methods
- every final classical result emits one standard contract
- every downstream stage consumes that standard contract

This does not imply universal solver compatibility. Instead:

- every supported model must route to at least one classical family
- every final classical result states exactly which downstream stages it can feed

## Migration Strategy

The migration should proceed in five phases.

### Phase 1: Define the Shared Result Schema

Do not start by rewriting solver internals.

First:

- define `classical_state_result`
- define role tags (`final`, `diagnostic`, `specialized`)
- define downstream compatibility fields
- add schema-level tests

This phase is low-risk and unlocks the rest of the migration.

### Phase 2: Add Adapters for Existing Final Classical Solvers

Wrap the current final classical methods to emit the shared result format.

Priority set:

- `spin-only-variational`
- `spin-only-luttinger-tisza`
- `spin-only-generalized-lt`
- `pseudospin-restricted-product-state`
- `pseudospin-cpn-local-ray-minimize`
- `pseudospin-sunny-cpn-minimize`

The goal is not to rewrite algorithms, only to standardize outputs.

### Phase 3: Reclassify Diagnostic / Seed Methods

Convert:

- `pseudospin-cpn-generalized-lt`
- `pseudospin-cpn-luttinger-tisza`
- `certified_glt`

into explicit diagnostic outputs with:

- lower-bound semantics
- seed/preconditioner semantics
- structured followup advice

They remain visible and parallel, but they stop impersonating final classical
solvers.

### Phase 4: Refactor Downstream Stages to Consume the Shared Contract

Refactor downstream stages in this order:

1. spin-wave / GSWT / LSWT stages
2. thermodynamics stages

Each downstream stage should check standardized compatibility flags and
representation semantics instead of upstream method ids.

### Phase 5: Clean Up the CLI and Reporting Surface

Only after the underlying architecture is stable should the public interface be
cleaned up.

This phase includes:

- grouped method display
- role-aware reporting
- default-method recommendation
- explicit blocking and fallback messages

## Minimum Viable First Landing

The smallest meaningful first landing is:

1. define `classical_state_result`
2. adapt four critical final methods:
   - `spin-only-variational`
   - `spin-only-luttinger-tisza`
   - `pseudospin-cpn-local-ray-minimize`
   - `pseudospin-sunny-cpn-minimize`
3. make spin-only LSWT and pseudospin GSWT consume the shared result
4. explicitly mark `cpn-generalized-lt` as diagnostic in the shared layer

This is the smallest change that begins real architectural convergence rather
than only documentation cleanup.

## Non-Goals

The first implementation of this design does not attempt to:

- force every effective Hamiltonian into every classical method
- erase the physical distinction between spin-only and retained-local-multiplet models
- eliminate diagnostic or specialized methods
- replace working solver kernels with one monolithic solver

The goal is interface unification and solver-layer clarity, not homogenization
of physically different models.

## Final Intended Outcome

After this design is implemented, the repository should satisfy the following
statement:

> Every supported effective Hamiltonian first enters a unified classical solver
> layer. Classical methods are listed in parallel but declare their role and
> applicability explicitly. Every successful final classical solve emits one
> standardized classical output. Downstream GLSPW / GSWT / LSWT and
> thermodynamics stages consume that standardized output rather than a
> method-specific internal payload.
