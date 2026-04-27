# FeI2 Canonical CPN Validation Design

**Date:** 2026-04-27

## Goal

Add a test-first, fixture-first validation slice that proves the repository's canonical
`cpn_pair_model` path can reproduce the FeI2 spin-1 / `CP^2` baseline used in the Sunny SU(3)
example, first at the ordered-state level and then at the spectrum level.

The purpose is not to add a new model family. The purpose is to demonstrate that the canonical
CPN contract already implemented in the repository is physically reproducible on a known reference
case.

## User-Approved Direction

- Use **end-to-end physics validation**, not only schema or contract validation.
- Compare against the Sunny FeI2 SU(3) example at:
  `https://sunnysuite.github.io/Sunny.jl/stable/examples/03_LSWT_SU3_FeI2.html`
- Include the onsite anisotropy term `D = 2.165 meV`.
- Sequence the work as:
  1. ground-state validation
  2. spectrum validation
- Treat the Sunny / Bai-et-al. parameter set as the gold baseline.
- Start from a **manual canonical fixture** rather than requiring the automatic input bridge first.
- Prioritize repository tests and fixtures over ad hoc scripts or one-off notebooks.

## Problem Statement

The repository now has a canonical `cpn_pair_model` contract, but it still lacks one strong
physics-facing regression that answers the practical question:

> If a user writes down the FeI2 spin-1 canonical pair model directly, does the repository recover
> the same ordered state and the same qualitative low-energy spectrum structure as the Sunny FeI2
> SU(3) reference workflow?

Without that regression:

- the canonical payload is only contract-tested, not benchmarked on a recognized physical example,
- future refactors could preserve schema validity while drifting in solver semantics,
- it remains unclear whether onsite terms, bond conventions, and spectrum routing are aligned with
  the Sunny reference in a reproducible way.

## Reference Baseline

The manual canonical fixture should encode the FeI2 baseline using the parameter values already
used in the Sunny example / Bai et al. comparison:

- `J1pm = -0.236`
- `J1pmpm = -0.161`
- `J1zpm = -0.261`
- `J2pm = 0.026`
- `J3pm = 0.166`
- `J′0pm = 0.037`
- `J′1pm = 0.013`
- `J′2apm = 0.068`
- `J1zz = -0.236`
- `J2zz = 0.113`
- `J3zz = 0.211`
- `J′0zz = -0.036`
- `J′1zz = 0.051`
- `J′2azz = 0.073`
- `D = 2.165 meV`

The fixture is the authoritative repository-side baseline. Local exploratory artifacts such as
`VR_hr.dat`, `POSCAR`, or scratch CSV files may still help during development, but they are not the
validation contract.

## Recommended Architecture

### 1. Manual Canonical FeI2 Fixture

Create one repository-tracked fixture that is already normalized to the canonical internal model:

- `model_family = "cpn_pair_model"`
- `classical_family = "cpn"`
- `local_dimension = 3`
- explicit `bond_terms`
- explicit `onsite_terms`
- explicit retained-local-space and pair-operator metadata

This keeps the validation focused on canonical CPN semantics instead of coupling the first proof to
document-reader or `many_body_hr` import details.

### 2. Three-Layer Test Split

The validation should be split into three distinct test layers:

1. **Fixture-contract test**
   Confirms the FeI2 fixture is canonical, dimensionally correct, and structurally usable.

2. **Ground-state validation test**
   Confirms that classical minimization on the canonical fixture reproduces the expected FeI2
   ordering pattern.

3. **Spectrum validation test**
   Confirms that the spectrum route from the same canonical fixture reproduces the expected branch
   structure and representative energies along the official Sunny path.

This decomposition keeps failures interpretable. If spectrum validation fails, we can distinguish
fixture problems from ordered-state problems from dynamical problems.

### 3. Canonical-First Test Entry

The tests should enter through the canonical payload builders already present in the repository.
They should not rely on hand-written solver internals or temporary analysis scripts. If a later
automatic bridge is added, it can be tested against the same fixture expectations.

## File Layout

The initial validation slice should live in focused repository fixtures and tests:

- `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_payload.json`
- `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json`
- `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`

Recommended responsibility split:

- `fei2_canonical_cpn_payload.json`
  contains the canonical input fixture only.
- `fei2_canonical_cpn_reference.json`
  contains comparison targets such as accepted ordering vectors, path nodes, and representative
  spectral reference values.
- `test_fei2_canonical_cpn_validation.py`
  owns fixture loading, contract assertions, ground-state checks, and spectrum checks.

If the single test file becomes noisy, a later implementation plan may split it into
`test_fei2_canonical_cpn_fixture.py` and `test_fei2_canonical_cpn_physics.py`, but that split is
not required by the design itself.

## Ground-State Validation Design

### Comparison Target

The ground-state test should verify that the canonical FeI2 model lands in the same symmetry class
as the Sunny example. The primary comparison target is the ordering / propagation vector, allowing
for symmetry-equivalent representatives.

Accepted symmetry-equivalent vectors should include:

- `[0, -1/4, 1/4]`
- `[1/4, 0, 1/4]`
- `[-1/4, 1/4, 1/4]`

The test should not require one literal vector if the solver returns a symmetry-equivalent member
of the same ordered manifold.

### Supercell Convention

Where the solver path needs an explicit supercell, the validation should use the same convention as
the Sunny tutorial baseline:

```text
[1 0 0;
 0 1 -2;
 0 1  2]
```

This reduces false disagreement caused only by differing commensurate embeddings.

### What To Assert

The ground-state slice should assert:

- the canonical fixture builds a valid CPN classical payload,
- the minimizer converges to an ordered state consistent with the accepted FeI2 manifold,
- the recovered ordering vector matches one of the allowed symmetry-equivalent targets,
- onsite anisotropy is actually present in the classical payload rather than dropped in routing.

The test does **not** need to prove bitwise identity of every local director gauge choice. Gauge and
symmetry freedom should be normalized at the level of physically meaningful invariants.

## Spectrum Validation Design

### Path Definition

The spectrum test should use the official Sunny FeI2 path:

- `[0, 0, 0]`
- `[1, 0, 0]`
- `[0, 1, 0]`
- `[1/2, 0, 0]`
- `[0, 1, 0]`
- `[0, 0, 0]`

### What To Compare

The first spectrum slice should compare structured numerical outputs, not rendered images. The test
should validate:

- expected branch count,
- representative eigenvalues at key path nodes,
- coarse consistency of low-energy mode placement and gaps,
- routing consistency between the canonical fixture and the Sunny-style SU(3) interpretation.

This avoids brittle image-diff testing while still proving physical reproducibility.

### Comparison Policy

The comparison should be representative rather than exhaustive:

- do not require every sampled k-point to match an external dense grid,
- do not compare plot pixels or full figure rasters,
- do compare a small reference table of path nodes and selected branch energies.

If intensity comparisons are included later, they should also be representative and structured, not
whole-image exact matching.

## Tolerances And Failure Interpretation

The validation should use explicit tolerances stored with the reference data. The design does not
hard-code the final numbers, but it does require that:

- ordering-vector matching is exact up to symmetry equivalence and numerical rounding,
- spectral comparisons use bounded numeric tolerances on representative energies,
- failures report whether the mismatch is:
  - fixture/schema level
  - ordered-state level
  - spectral level

This matters because different failure classes imply different debugging paths. A propagation-vector
miss points to model or minimization semantics, while a spectrum-only miss may point to the
dynamical solver path or path-convention mismatches.

## Scope And Non-Goals

### In Scope

- one manual canonical FeI2 fixture,
- one repository-tracked reference snapshot,
- repository tests proving canonical reproducibility,
- ground-state validation first,
- spectrum validation second,
- direct comparison against the Sunny official FeI2 example baseline.

### Out Of Scope

- automatic generation of the FeI2 canonical fixture from document-reader or `VR_hr.dat`,
- broad multi-material benchmark infrastructure,
- whole-plot image diffing,
- thermodynamics validation,
- extending the validation to arbitrary spin-only or multipolar models in the same slice.

## Risks

- The largest risk is convention drift: the fixture may encode the right couplings in the wrong
  bond, basis, or supercell convention and still look superficially plausible.
- Ground-state and spectrum mismatches may reflect symmetry-equivalent embeddings rather than real
  physics disagreement unless the test normalizes those equivalences explicitly.
- If the reference snapshot is too dense, the tests will become brittle; if it is too sparse, the
  validation will be weak.

## Success Criteria

This design is successful when the repository has a stable, tracked validation slice showing that:

- FeI2 can be expressed directly as a canonical `CP^2` pair model,
- the canonical payload preserves the onsite anisotropy term `D = 2.165 meV`,
- the repository reproduces the expected FeI2 ordered state up to symmetry equivalence,
- the repository reproduces representative FeI2 spectral structure along the official Sunny path,
- future canonical CPN refactors can be regression-tested against one recognized physical example.
