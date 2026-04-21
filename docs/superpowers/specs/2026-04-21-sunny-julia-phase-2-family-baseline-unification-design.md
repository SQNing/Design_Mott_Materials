# Sunny Julia Migration Phase 2 Family Baseline Unification Design

## Goal

Unify every remaining Sunny-family pseudospin-orbital execution chain onto the
same Julia/Sunny runtime baseline that Phase 1 already established for the
spin-only LSWT path.

Phase 2 should make the remaining Sunny-backed chains agree on:

- the canonical repo-local Julia project:
  `translation-invariant-spin-model-simplifier/.julia-env-v09`
- the canonical repo-local Julia depot:
  `translation-invariant-spin-model-simplifier/scripts/.julia-depot`
- the optional Python-side Julia binary override:
  `DESIGN_MOTT_JULIA_CMD`
- consistent reference documentation and regression tests that lock this
  baseline in place

This phase is a runtime-baseline unification project, not a new backend-design
project. The classical minimization, thermodynamics, and SUN-GSWT routes
already exist on `main`; they are just not yet aligned with the corrected
Phase 1 environment story.

## Why Phase 2 Exists

Phase 1 deliberately stopped after migrating the spin-only LSWT path. That was
the correct scope boundary, and it succeeded:

- `run_sunny_lswt.jl` now activates `.julia-env-v09`
- `linear_spin_wave_driver.py` now respects `DESIGN_MOTT_JULIA_CMD`
- `reference/environment.md` describes `Sunny.jl 0.9.x`
- the real FeI2 LSWT rerun moved from missing-package failure to a real Sunny
  instability

However, the rest of the Sunny family still reflects the old pre-Phase-1
runtime assumptions.

Current remaining drift:

1. `run_sunny_sun_classical.jl` still points at `scripts/.julia-env-v06`
   semantics via `joinpath(SCRIPT_DIR, "..", ".julia-env-v06")`.
2. `run_sunny_sun_thermodynamics.jl` still points at the old `v06` location.
3. `run_sunny_sun_gswt.jl` still points at the old `v06` location.
4. `sunny_sun_classical_driver.py` still defaults directly to `"julia"` and
   does not inherit the `DESIGN_MOTT_JULIA_CMD` override pattern.
5. `sunny_sun_thermodynamics_driver.py` has the same problem.
6. `sun_gswt_driver.py` has the same problem.

That means the repository currently exposes one corrected Sunny launcher family
and one stale Sunny launcher family. Phase 2 exists to remove that split-brain
state in one pass.

## In Scope

### Runtime Surfaces

Phase 2 covers the remaining Sunny-family launchers and Python adapters:

- `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl`
- `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl`
- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_sun_gswt.jl`
- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py`

### Validation / Documentation Surfaces

Phase 2 also covers the docs and tests that must agree with that runtime:

- `translation-invariant-spin-model-simplifier/reference/environment.md`
- focused Sunny-family driver and launcher regression tests
- this Phase 2 spec and implementation plan
- session-memory notes tracking the new frontier

## Explicitly Out Of Scope

Phase 2 does not include:

- changing Sunny classical minimization algorithms
- changing Sunny thermodynamics sampling semantics
- changing SUN-GSWT payload structure or dispersion diagnostics
- broad refactoring of all Julia-command handling into a new shared module
- solving the real FeI2 Sunny instability exposed after Phase 1
- reworking the pseudospin-orbital CLI architecture, which is already present
  on `main`

If the unified baseline later exposes a real Sunny physics/runtime issue in
classical, thermodynamics, or GSWT, that should become a separate follow-up.

## Design Summary

Phase 2 should make the remaining Sunny family mirror the Phase 1 LSWT runtime
contract.

The desired steady state is:

```text
Sunny-family Python drivers
  -> optional DESIGN_MOTT_JULIA_CMD override
  -> repo-local Julia launchers
  -> repo-local .julia-env-v09 project
  -> repo-local scripts/.julia-depot
  -> Sunny 0.9.x / JSON3 in one shared baseline
```

The important design rule is:

> Every Sunny-family path should resolve Julia the same way on the Python side
> and activate the same repo-local Julia project on the Julia side.

## Core Design Choices

### 1. Reuse the Existing Phase 1 Baseline

Do not create a second post-Phase-1 Julia environment.

Phase 2 should reuse:

- `translation-invariant-spin-model-simplifier/.julia-env-v09`
- `translation-invariant-spin-model-simplifier/scripts/.julia-depot`

Why:

- Phase 1 already proved this environment is real, instantiable, and committed
- keeping one canonical Sunny project avoids environment drift by construction
- a second environment would recreate the exact ambiguity Phase 1 removed

### 2. Match the LSWT Julia-Command Resolution Pattern

The remaining Python drivers should follow the same resolution order as
`linear_spin_wave_driver.py`:

1. explicit `julia_cmd` argument if provided
2. `DESIGN_MOTT_JULIA_CMD` from the environment if set
3. plain `"julia"` as the final fallback

This behavior should apply both to library calls and to CLI entrypoints. That
means the `argparse` layer should not force the default back to `"julia"` when
the caller omitted `--julia-cmd`.

### 3. Keep Julia Launchers As The Source Of Truth For Project Activation

Each remaining Julia launcher should activate:

- `LOCAL_DEPOT = scripts/.julia-depot`
- `LOCAL_PROJECT = .julia-env-v09`

with path logic equivalent to the corrected Phase 1 LSWT launcher.

For scripts under `scripts/classical/` or `scripts/lswt/`, that means:

- depot path remains relative to `scripts/`
- project path must walk up to the repository-local
  `translation-invariant-spin-model-simplifier/.julia-env-v09`

### 4. Lock The Baseline With Focused Contract Tests

Phase 2 should add or extend tests that make future drift obvious:

- driver tests that prove `DESIGN_MOTT_JULIA_CMD` overrides the default Julia
  binary
- driver tests that prove plain `"julia"` remains the fallback when no override
  is present
- launcher source tests that prove the remaining Julia scripts now reference
  `.julia-env-v09`
- launcher source tests that prove `.julia-env-v06` is gone from the active
  Sunny-family runtime

These are intentionally narrow environment-contract tests. Phase 2 is not the
time to reopen backend-physics validation.

## Testing Strategy

Phase 2 should use three verification layers:

### 1. Python Driver Override Regression

Add focused tests for:

- `sunny_sun_classical_driver.py`
- `sunny_sun_thermodynamics_driver.py`
- `sun_gswt_driver.py`

to confirm the correct Julia binary resolution order.

### 2. Julia Launcher Path Regression

Add focused source-level tests for:

- `run_sunny_sun_classical.jl`
- `run_sunny_sun_thermodynamics.jl`
- `run_sunny_sun_gswt.jl`

to confirm that the remaining launchers now target `.julia-env-v09` and no
longer mention `.julia-env-v06`.

### 3. Focused Sunny-Family Regression Slice

After rewiring the drivers and launchers, rerun the focused test slice that
exercises:

- LSWT environment contract tests
- Sunny-family driver tests
- GSWT driver tests
- downstream execution routing tests
- skill/reference docs tests

Success for Phase 2 means the repository has one coherent Sunny-family runtime
story instead of one corrected LSWT path plus three stale pseudospin launchers.

## Implementation Slicing

Phase 2 should be implemented in this order:

### Task 1: Lock Python-Side Julia Resolution In Tests

Write failing tests for:

- environment override behavior in the classical driver
- environment override behavior in the thermodynamics driver
- environment override behavior in the GSWT driver

### Task 2: Rewire The Remaining Python Drivers

Update the three Python drivers so they all respect:

- explicit `julia_cmd`
- `DESIGN_MOTT_JULIA_CMD`
- fallback to `"julia"`

and ensure CLI entrypoints do not defeat that behavior.

### Task 3: Lock Julia Launcher Paths In Tests

Write or extend source-level tests that require:

- `.julia-env-v09` in the three remaining Julia launchers
- no active `.julia-env-v06` reference in those scripts

### Task 4: Rewire The Remaining Julia Launchers

Update the three Julia launchers so they activate the canonical Phase 1
project/depot baseline.

### Task 5: Refresh Docs And Re-run Focused Verification

Update environment/reference wording as needed, rerun the focused Sunny-family
regression slice, and record the resulting state in session memory.

## Expected Outcome

After Phase 2:

- every checked-in Sunny-family launcher uses `.julia-env-v09`
- every checked-in Sunny-family Python adapter can honor
  `DESIGN_MOTT_JULIA_CMD`
- `reference/environment.md` describes a single shared Sunny-family runtime
  story
- future environment drift is caught by tests instead of rediscovered during a
  downstream smoke
