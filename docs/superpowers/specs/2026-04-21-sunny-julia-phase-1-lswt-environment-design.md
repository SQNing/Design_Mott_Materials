# Sunny Julia Migration Phase 1 LSWT Environment Design

## Goal

Upgrade the repository's spin-only Sunny LSWT path to a current, explicit, and
internally consistent Julia/Sunny environment, then validate that environment
through the real FeI2 `V2b` downstream chain.

Phase 1 should:

- move the spin-only LSWT path onto a canonical local Julia environment
- target a current Julia 1.12.x line and Sunny 0.9.x line
- eliminate the current drift between script paths, local environment layout,
  and reference documentation
- keep the migration scoped to the spin-only LSWT chain plus directly related
  environment docs, plans, and tests
- finish with a real FeI2 `V2b` smoke that proves `lswt=ready` can execute in
  the upgraded environment

This phase intentionally does not migrate the pseudospin/SUN classical,
thermodynamics, or GSWT chains.

## Why Phase 1 Exists

The repository currently has a broken but highly informative intermediate state:

- the environment reference claims the expected Sunny line is `0.9.x`
- the actual local Julia project still points at a `Sunny-v0.6.0` vendor path
- the LSWT Julia launcher still looks for `scripts/.julia-env-v06`
- the actual local environment now lives at `.julia-env-v06` under the project
  root, not under `scripts/`
- the first real FeI2 `V2b` smoke proved the route and artifact contract is
  correct, but the auto-executed LSWT backend failed at runtime

This means the next useful step is not more LSWT contract design. The next step
is environment convergence.

## In Scope

### Technical Scope

Phase 1 covers only the spin-only LSWT path and the environment surfaces that
must agree with it:

- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`
- `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`
- the canonical local Julia project/depot layout used by spin-only LSWT
- `translation-invariant-spin-model-simplifier/reference/environment.md`
- directly related tests and smoke-report documentation

### Functional Scope

Phase 1 should produce:

- one canonical Julia project location for the current Sunny backend
- one canonical depot expectation for that backend
- consistent script launch behavior
- clear environment verification instructions
- a real FeI2 smoke showing:
  - `lswt=ready`
  - successful LSWT backend execution, or
  - a narrower, more truthful runtime error if another root cause remains

## Explicitly Out Of Scope

Phase 1 does not include:

- migrating `run_sunny_sun_classical.jl`
- migrating `run_sunny_sun_thermodynamics.jl`
- migrating `run_sunny_sun_gswt.jl`
- changing pseudospin/SUN payload contracts
- broader Julia/Sunny upgrades for every backend in one step

Those are deferred to Phase 2.

## Current-State Evidence

The current drift is visible in four places:

1. `reference/environment.md` says the local Julia project is
   `scripts/.julia-env-v06`, and also says the expected Sunny line is `0.9.x`,
   even though the current official Sunny release line is `0.7.x`.
2. `run_sunny_lswt.jl` resolves `LOCAL_PROJECT` relative to `scripts/`.
3. The actual environment directory now exists at project root as
   `.julia-env-v06/`.
4. The current manifest still pins `Sunny` to a vendor path under
   `.vendor/Sunny-v0.6.0`.

The real FeI2 `V2b` smoke already showed that the LSWT route is correct:

- `lswt = ready`
- `gswt = blocked`
- `thermodynamics = review`

So the main architecture is working. The environment is not.

## Design Summary

Phase 1 should treat the LSWT runtime as an environment-migration project with
one narrow execution chain:

```text
reference docs
  -> canonical Julia project/depot layout
  -> LSWT Python launcher
  -> LSWT Julia launcher
  -> local package instantiate/precompile
  -> real FeI2 V2b smoke
```

The key rule is:

> Phase 1 upgrades and stabilizes the spin-only LSWT environment only. It does
> not opportunistically migrate the wider Sunny/SUN backend family.

## Core Design Choice

Phase 1 should introduce a **new canonical environment identity** rather than
continuing to overload the ambiguous old `scripts/.julia-env-v06` story.

Recommended direction:

- create a new canonical local environment directory:
  - `translation-invariant-spin-model-simplifier/.julia-env-v09`
- continue using the local depot under:
  - `translation-invariant-spin-model-simplifier/scripts/.julia-depot`

Why a new environment directory is preferable:

- it breaks the accidental coupling to the old `v06` naming
- it makes the migration visible and auditable
- it avoids pretending the old environment layout is still canonical

## Proposed Components

### 1. Canonical LSWT Julia Environment

Create or derive one canonical environment for Phase 1:

- `translation-invariant-spin-model-simplifier/.julia-env-v09`

It should declare at least:

- `Sunny`
- `JSON3`

and should be instantiated against the local depot used by LSWT launcher
scripts.

### 2. LSWT Launcher Alignment

The spin-only LSWT execution chain should agree on:

- Julia executable expectation
- local project path
- local depot path

Relevant code:

- `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`

These files should not guess different environment roots.

### 3. Environment Reference Alignment

The environment reference should reflect the canonical layout and target
versions exactly.

Relevant file:

- `translation-invariant-spin-model-simplifier/reference/environment.md`

It should document:

- Julia 1.12.x as the expected stable line
- Sunny 0.9.x as the expected Sunny line
- the new local project location
- the local depot expectation
- the exact verification and instantiate commands

### 4. Smoke Validation Surface

The final correctness check for Phase 1 is not just a unit test. It is the
real FeI2 `V2b` smoke path that previously produced:

- `lswt=ready`
- `missing-sunny-package`

Phase 1 is successful only when that smoke either:

- runs through LSWT successfully, or
- reveals a new, narrower backend issue after environment convergence

## Testing Strategy

Phase 1 needs three layers of verification:

### 1. Environment-structure regression

Add or extend tests that lock the expected environment reference and launcher
paths so future drift is caught earlier.

Examples:

- reference docs mention the new canonical project path
- launcher scripts no longer point at `scripts/.julia-env-v06`

### 2. LSWT launcher regression

Add a narrow test that proves the Python-side LSWT driver invokes the Julia
launcher in a way that is compatible with the new canonical environment.

### 3. Real FeI2 smoke

Repeat the FeI2 `V2b` downstream smoke and inspect:

- `downstream_routes.json`
- `downstream_results.json`
- `downstream_summary.json`

The expected improvement is that the route contract stays the same, while the
LSWT runtime moves from environment failure toward successful execution.

## Implementation Slicing

Phase 1 should be implemented in this order:

### Task 1: Lock The Current Drift In Tests

Write failing tests that capture:

- the old incorrect project-path assumption
- the required new environment reference
- the LSWT launcher expectation

### Task 2: Introduce The Canonical `.julia-env-v09`

Create the new local Julia environment metadata and pin the target Sunny line
there.

### Task 3: Rewire The Spin-Only LSWT Launchers

Update the Python and Julia LSWT launcher pair to use the new canonical
environment.

### Task 4: Update Environment Reference And Related Docs

Align the docs with the new environment and verification commands.

### Task 5: Instantiate, Reproduce, And Re-run The FeI2 Smoke

Only after the launchers and docs agree should the local depot be
instantiated/precompiled and the real FeI2 smoke re-run.

## Deferred To Phase 2

Phase 2 should start from the stabilized Julia/Sunny baseline created here and
then migrate the broader Sunny/SUN backend family:

- `run_sunny_sun_classical.jl`
- `run_sunny_sun_thermodynamics.jl`
- `run_sunny_sun_gswt.jl`
- the corresponding Python adapters
- pseudospin/SUN reference and plan documents

Phase 2 should be planned after Phase 1 finishes so it can inherit the final
canonical environment layout rather than guessing it.

## Completion Criteria

Phase 1 is complete when all of the following are true:

- the canonical Julia/Sunny LSWT environment is explicit and documented
- LSWT launchers point to that canonical environment
- environment reference commands match the real repository layout
- focused tests covering the environment/launcher assumptions pass
- the real FeI2 `V2b` smoke no longer fails with the current
  `missing-sunny-package` environment error
