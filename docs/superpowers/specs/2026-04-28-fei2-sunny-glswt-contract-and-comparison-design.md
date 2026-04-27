# FeI2 Sunny GLSWT Contract And Comparison Design

**Date:** 2026-04-28

## Goal

Stabilize the repository's Sunny-based pseudospin-orbital GLSWT path around the
real FeI2 canonical `CP^(N-1)` validation case by:

1. tightening the Sunny GLSWT contract first,
2. comparing the resulting allowed execution paths against the official FeI2
   Sunny baseline second, and
3. only then adding a Python-GLSWT vs Sunny-GLSWT comparison layer.

The immediate purpose is not to force every FeI2 representation to execute. The
purpose is to make the repository distinguish clearly between:

- valid periodic SUNNY-GSWT inputs that can be executed meaningfully,
- reduced or ambiguous inputs that must be blocked before backend execution, and
- real backend/runtime instabilities that should surface as physics-facing
  diagnostics rather than contract confusion.

## User-Approved Direction

- Prioritize the work as:
  1. Sunny GLSWT contract hardening
  2. comparison against the official FeI2 Sunny baseline
  3. Python GLSWT vs Sunny GLSWT comparison
- Do not start from a broad "make everything run" objective.
- Prefer honest-fail boundaries over permissive but ambiguous execution.
- Keep the work FeI2-centered instead of expanding into a fully generic Sunny
  GLSWT redesign.
- Use the existing canonical FeI2 validation artifacts and real repository
  states rather than inventing synthetic-only comparison cases.

## Why This Phase Exists

The current repository is already beyond the "backend absent" stage for Sunny
GLSWT:

- `build_sun_gswt_payload.py` already exports canonical `CP^(N-1)` local-ray
  states, onsite terms, ordering metadata, and optional
  `magnetic_supercell_matrix`.
- `sun_gswt_driver.py` already performs meaningful preflight validation and can
  return structured errors such as
  `unsupported-incommensurate-single-q-sun-gswt`.
- `run_sunny_sun_gswt.jl` already reconstructs a Sunny `:SUN` system, applies
  pair couplings and onsite terms, optionally reshapes the supercell, and calls
  `Sunny.SpinWaveTheory(...)`.

That means the main unresolved problem is no longer "how do we talk to Sunny at
all?" The unresolved problem is narrower and more important:

> Which FeI2 classical-state representations are actually well-defined inputs to
> the current Sunny GLSWT backend, and how should the repository report the
> difference between contract invalidity, state-representation mismatch, and
> real backend instability?

Without tightening that boundary first:

- later FeI2 comparisons against the official Sunny example remain noisy,
- a backend error can still mean either "real instability" or "invalid state
  semantics",
- Python-vs-Sunny comparison work risks comparing states that are not actually
  equivalent inputs.

## Problem Statement

The FeI2 canonical validation thread has already established several strong
classical facts:

- the canonical `CP^(N-1)` contract uses full `N^2 x N^2` pair operators,
- the Python classical energy evaluator and Sunny agree exactly on identical
  non-reshaped real-space states,
- the suspicious low-energy Python basin is a genuine period-4 two-ray `ABBA`
  texture with dominant `q = [1/4, 0, 1/4]`,
- the official post-reshape Sunny single-`q` solution is locally close to that
  two-sublattice picture, but the full chemical-cell textures are not yet
  strictly identical.

Those conclusions make GLSWT the next meaningful layer, but they also expose a
representation problem:

- some states exist as explicit periodic `local_rays`,
- some states rely on `magnetic_supercell_matrix` to define the periodic object
  that Sunny should actually analyze,
- some states are reduced single-`q` descriptions that are not automatically
  equivalent to a fully lifted periodic supercell state.

If the repository blurs these categories, then a GLSWT result or failure is not
trustworthy enough to interpret.

## Design Summary

This phase should be implemented as three deliberately separated layers:

1. **Phase B: Contract Hardening**
   Tighten the Sunny GLSWT acceptance boundary for real FeI2-relevant state
   classes and make unsupported cases fail before Julia backend execution.

2. **Phase O: Official FeI2 Comparison**
   Compare the official FeI2-related states and repository states only after
   they pass the tightened contract classification, and summarize whether they
   execute, fail physically, or are blocked by contract.

3. **Phase C: Python vs Sunny Comparison**
   Compare Python GLSWT and Sunny GLSWT only on states already proven to be
   valid, well-defined, and comparable under the tightened contract.

The ordering is essential. Phase O depends on the semantic clarity established
by Phase B, and Phase C depends on both Phase B and Phase O.

## In Scope

### Technical Scope

This design covers only the Sunny GLSWT path and directly related FeI2
comparison utilities:

- `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_sun_gswt.jl`
- focused tests for those files
- new FeI2-oriented comparison harnesses and output summaries

### Functional Scope

This phase should produce:

- a clearer contract for which FeI2 state encodings may enter Sunny GLSWT,
- structured blocking for unsupported or semantically incomplete inputs,
- one official FeI2 comparison summary built on top of that contract,
- one later Python-vs-Sunny comparison summary built on the same valid input
  surface.

## Out Of Scope

This phase does not include:

- inventing a new general incommensurate Sunny GLSWT lifting algorithm,
- forcing every reduced single-`q` representation to run through Sunny,
- broad multi-material GLSWT benchmarking infrastructure,
- immediate full-branch or full-eigenvector matching between Python and Sunny,
- replacing the current Python GLSWT implementation,
- changing the already-validated classical-energy semantics unless a new
  contract bug is uncovered.

## Phase B: Sunny GLSWT Contract Hardening

### Core Design Principle

Phase B should make the Sunny GLSWT path answer one narrow question correctly:

> Is this classical-state representation a fully defined periodic input for the
> current Sunny `SpinWaveTheory` backend?

The correct outcome is not always "yes." The correct outcome is:

- execute if the state semantics are complete and periodic,
- block if the semantics are incomplete or representation-dependent,
- surface backend instability only after the input has passed contract checks.

### Target FeI2 State Classes

Phase B should explicitly distinguish three FeI2-relevant classes.

#### 1. Direct Periodic `local_rays`

These states already define a finite periodic configuration through:

- `initial_local_rays`
- `supercell_shape`

and do not require hidden lifting semantics.

Examples:

- the no-reshape Python low-energy `ABBA` FeI2 state,
- a no-reshape Sunny local-ray state exported explicitly site by site.

Policy:

- allow execution if the payload is otherwise valid,
- preserve the current path for structured success or backend instability
  reporting.

#### 2. Magnetic-Supercell-Derived Periodic States

These states are still periodic, but only after acknowledging that the backend
object is the reshaped magnetic supercell, not the original chemical-cell view.

Examples:

- FeI2 states exported together with a nontrivial
  `magnetic_supercell_matrix`,
- states whose ordering metadata refers to the reshaped cell convention.

Policy:

- allow execution only if the payload explicitly carries the reshape semantics
  needed to define the backend system,
- record that the resulting dispersion belongs to the reshaped magnetic-cell
  system,
- block early if the representation gestures at reshape-dependent semantics
  without fully specifying them.

#### 3. Reduced Single-`q` / Ansatz-Level States

These states describe an ordering pattern compactly, but are not automatically
identical to a fully lifted periodic supercell state that Sunny can consume.

Examples:

- single-`q` states identified through `ordering.ansatz`,
- official-like reduced states whose semantics depend on a lifting convention
  not yet explicit in the repository contract.

Policy:

- allow execution only if the state is demonstrably commensurate and already
  realized as an explicit periodic backend state,
- otherwise fail before backend execution with a precise contract error,
- do not silently reinterpret reduced ansatz data as a full periodic state.

### Contract Outcomes

Phase B should normalize Sunny GLSWT outcomes into four distinct categories:

1. `allowed_and_executed`
   The payload passed contract checks and backend execution returned
   dispersion-like output.

2. `allowed_but_unstable`
   The payload passed contract checks, but backend execution exposed an
   instability or soft-mode physics issue.

3. `blocked_by_contract`
   The payload never reached Julia because its state semantics were not
   sufficiently defined for the current backend.

4. `blocked_by_backend`
   The payload passed contract checks but hit a true backend/runtime problem
   unrelated to state-category ambiguity.

These categories should be visible in comparison harnesses rather than buried in
free-form log text.

### Recommended Implementation Surface

Phase B should stay focused on the existing interfaces:

- `build_sun_gswt_payload.py`
  owns exporting the relevant state/category metadata cleanly.
- `sun_gswt_driver.py`
  owns the preflight classification and honest-fail decisions.
- `run_sunny_sun_gswt.jl`
  remains a thin execution backend and should not become the primary place
  where ambiguous state semantics are interpreted.

This keeps the contract decision on the Python side, where repository-level
diagnostics and tests are easier to maintain.

### Testing Strategy For Phase B

Phase B needs focused tests that lock the three target state classes and the
expected allow/block behavior. The first version should prefer fixture-driven
unit tests and mocked driver tests over long cluster runs.

Representative checks:

- periodic no-reshape local-ray FeI2-like payloads remain executable,
- reshape-aware payloads carry through `magnetic_supercell_matrix` and are
  either allowed or blocked for explicit reasons,
- reduced single-`q` payloads that lack full periodic lifting are blocked
  before backend launch,
- error classification distinguishes contract failure from backend instability.

## Phase O: Official FeI2 Comparison After Contract Hardening

### Purpose

After Phase B, the repository should answer a more precise comparison question:

> Which official-FeI2-related states are valid Sunny GLSWT inputs under the
> repository contract, and for those that are valid, what high-level execution
> outcome do they produce?

This phase is intentionally narrower than a full physics reproduction study.
The first purpose is semantic classification with meaningful execution results.

### Comparison Inputs

The comparison harness should reuse existing repository-side FeI2 artifacts
instead of inventing new ad hoc states. Candidate input groups are:

- repository canonical no-reshape periodic states,
- repository reshaped or reshape-aware FeI2 states,
- official-like FeI2 reference states already reproduced in the workspace,
- any reduced single-`q` state only if its lifted periodic semantics are already
  explicit.

### Comparison Questions

The first official-comparison slice should answer:

1. Which states are `allowed_and_executed`?
2. Which states are `allowed_but_unstable`?
3. Which states are `blocked_by_contract`?
4. Which states are `blocked_by_backend`?

Only after that classification should the harness summarize soft-mode or
dispersion information for the allowed states.

### What To Compare

For allowed states, the first comparison layer should stay on robust summary
quantities:

- overall execution `status`,
- whether `SpinWaveTheory` construction succeeds,
- minimum sampled `omega`,
- soft-mode or instability location in `q`,
- any structured instability summary already emitted by the driver.

The first official comparison should not require:

- full band-by-band matching,
- full path-point spectral equality,
- eigenvector matching,
- image-diff reproduction of the official plot.

### Output Format

The official comparison should write a structured artifact, ideally one compact
JSON plus an optional short markdown summary. The summary should group each
state into one of the four normalized outcome categories and then report the
most relevant dispersion or instability summary for the allowed ones.

This keeps the comparison readable and makes it easier to inspect whether a
future discrepancy is semantic, numerical, or physical.

## Phase C: Python GLSWT vs Sunny GLSWT Comparison

### Entry Condition

Phase C should not accept arbitrary states. It should accept only states that
already satisfy the tightened Phase B contract, or states that have explicit,
audited reasons for why both backends consume the same realized periodic input.

This protects the comparison from being polluted by representation mismatch.

### Comparison Principle

The first Python-vs-Sunny comparison should compare:

- the same state,
- under the same periodic interpretation,
- using the same path summary,
- through a small set of stable observables.

It should not begin with exhaustive spectral equivalence claims.

### First Comparison Metrics

The initial metric set should include:

- execution `status`,
- minimum `omega`,
- `q` position of the softest mode,
- presence or absence of instability / soft mode,
- if path sampling is consistent, the lowest branch summary `omega_min(q)` along
  the path.

These metrics are strong enough to identify meaningful differences while still
being tractable to interpret.

### Difference Classification

Phase C should classify disagreement into three buckets:

1. `contract_difference`
   One backend received an input the other does not legitimately accept.

2. `state_difference`
   The compared states were only approximately related and were not actually the
   same periodic reference state.

3. `backend_physics_difference`
   The same valid periodic state produces materially different GLSWT summaries
   between Python and Sunny.

This distinction is necessary to avoid over-attributing every mismatch to the
solver mathematics.

### Output Format

Phase C should write:

- one FeI2-focused comparison JSON artifact,
- one concise markdown summary explaining where the two backends agree and
  where they do not,
- a short diagnostic note pointing to the next debugging layer: contract, state
  preparation, or backend physics.

## Implementation Slicing

The recommended implementation order is:

### Task 1: Lock Phase B State Categories In Tests

Add or extend tests that encode the three target state classes and expected
allow/block behavior.

### Task 2: Tighten Python-Side Preflight Classification

Refine the export and driver logic so contract-invalid FeI2-related inputs fail
before Julia execution with precise reasons.

### Task 3: Add A FeI2 Official-Comparison Harness

Create a narrow harness that runs the curated FeI2 state set through the
contract-hardened Sunny GLSWT path and writes categorized output summaries.

### Task 4: Add A Python-Vs-Sunny Comparison Harness

Build the later comparison layer on top of the already-validated state set and
summary metrics.

## Success Criteria

This design is successful when:

- the repository can explain why a given FeI2 GLSWT state is executable or not,
- official FeI2-related states are compared through a categorized and
  reproducible summary instead of informal logs,
- Python-vs-Sunny comparison happens only on semantically valid inputs,
- future FeI2 GLSWT debugging can clearly separate contract issues from backend
  or physics issues.

## Non-Goals

This design does not promise:

- complete agreement with the official FeI2 spectrum in the first comparison
  slice,
- a generic all-material Sunny GLSWT contract framework,
- support for arbitrary incommensurate single-`q` states,
- full multiband spectral matching between Python and Sunny in one pass.

Those may become later follow-on phases, but they are not required for this
design to be successful.
