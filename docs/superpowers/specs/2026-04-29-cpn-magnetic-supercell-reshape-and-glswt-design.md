# CP(N-1) Magnetic Supercell Reshape And GLSWT Design

**Date:** 2026-04-29

## Goal

Add a repository-native magnetic-supercell reshape workflow for general
multi-site `CP^(N-1)` periodic models so that:

1. a dominant nonuniform ordering wavevector can be converted into a candidate
   integer `magnetic_supercell_matrix`,
2. the original periodic model can be rewritten exactly in that magnetic-cell
   basis,
3. Python classical minimization can run directly on the reshaped model,
4. the optimized reshaped classical state can flow without ad hoc conversion
   into both Python GLSWT and Sunny GLSWT.

The design target is not a FeI2-only shortcut. The design target is a reusable
core layer for general periodic multi-site `CP^(N-1)` models represented by
site-indexed onsite terms and `(source, target, R)` bond data.

## User-Approved Direction

- Support general multi-site `CP^(N-1)` models from the first implementation.
- Support arbitrary nonsingular integer `magnetic_supercell_matrix`.
- Do not rely on external reshape packages for the model-layer transformation.
- Allow the reshaped classical branch to continue seamlessly into both Python
  and Sunny GLSWT.
- Treat the magnetic-supercell branch as an energy-lowering refinement step
  after an initial classical state has been found.

## Problem Statement

The current repository can already do three important things separately:

1. find classical `CP^(N-1)` states on explicit periodic supercells,
2. diagnose dominant ordering content through projector Fourier components,
3. run Python or Sunny GLSWT once given an explicit periodic classical state.

However, the current Python classical path still has a hard gap:

- it only understands ordinary `supercell_shape` periodicity,
- it explicitly rejects states encoded through `magnetic_supercell_matrix`
  semantics,
- it has no internal notion of rewriting a model into a reshaped magnetic-cell
  basis.

Because of that gap, the repository cannot currently do the full intended
workflow in Python:

1. detect that a lower-energy magnetic-cell refinement is plausible from the
   dominant nonuniform ordering component,
2. reshape the model into that magnetic cell,
3. re-optimize the classical state there,
4. feed the selected refined state into GLSWT backends.

Sunny can do parts of this already because `Sunny.reshape_supercell(...)`
exists for Sunny's own system object. But that is not sufficient for the
repository-wide workflow because:

- Python classical minimization still cannot run in the reshaped basis,
- Python GLSWT and Sunny GLSWT need a common repository-side model/state
  description,
- the repository needs a backend-independent representation of the reshaped
  Hamiltonian and reshaped classical state.

## Design Summary

Introduce a dedicated magnetic-supercell core layer that rewrites a periodic
`CP^(N-1)` model and optional classical state into a new periodic model defined
in the magnetic-cell basis.

This core layer becomes the single source of truth for:

- candidate magnetic-cell construction from ordering diagnostics,
- multi-site coset enumeration inside the magnetic cell,
- bond and onsite rewriting into the reshaped basis,
- state lifting between original-cell and magnetic-cell conventions.

The classical and GLSWT pipelines then consume the reshaped result as if it
were an ordinary periodic model with ordinary periodic local rays. No solver
should need custom magnetic-supercell semantics after the reshape stage is
complete.

## Core Design Principles

### 1. Reshape At The Model Layer, Not The State-Metadata Layer

The repository should not teach the Python classical solver to interpret
`magnetic_supercell_matrix` ad hoc while still operating on the original model.
Instead, the model itself should be transformed so that the reshaped output is a
plain periodic model in a new basis.

This keeps downstream solvers simple:

- Python classical minimization sees an ordinary periodic model,
- Python GLSWT sees an ordinary periodic model plus local rays,
- Sunny GLSWT sees a repository payload that can be lowered into its own
  reshaped system cleanly.

### 2. Preserve Exact Classical Energy Under Reshape

For any explicit periodic state that is faithfully lifted between the original
and reshaped descriptions, the classical energy density must be invariant.

This is the most important correctness criterion for the reshape machinery. If
reshape changes the energy of an equivalent state, the new workflow cannot be
trusted.

### 3. Keep Candidate Selection Separate From Candidate Acceptance

The workflow should distinguish:

- proposing a candidate magnetic cell from projector diagnostics,
- reshaping and optimizing within that candidate cell,
- deciding whether to accept the refined branch based on energy gain and
  configured safety limits.

This keeps the repository honest about what is diagnostic guidance versus what
is an accepted physical refinement.

## Architecture

Add a new repository-side reshape core with three responsibilities.

### A. Candidate Construction

`magnetic_supercell_candidate_from_projector(projector_summary, ...)`

Responsibilities:

- inspect the largest nonzero Fourier component from projector diagnostics,
- convert the selected reduced-coordinate `q` into a commensurate integer
  magnetic-cell candidate,
- return a normalized candidate object containing:
  - selected `q`,
  - candidate integer matrix `M`,
  - determinant,
  - commensurability diagnostics,
  - any rejection reason if no acceptable candidate exists.

This component does not mutate models or run solvers.

### B. Model Reshape Core

`reshape_cpn_model_to_magnetic_supercell(model, magnetic_supercell_matrix, ...)`

Responsibilities:

- enumerate all chemical-cell coset representatives inside the magnetic cell,
- build reshaped lattice vectors,
- create reshaped positions with new site numbering,
- rewrite all bond terms `(source, target, R)` into the reshaped basis,
- duplicate onsite terms onto each replicated site in the reshaped magnetic
  cell,
- emit a reshaped model that downstream code can consume as a standard periodic
  `CP^(N-1)` model.

### C. State Lifting Core

`lift_cpn_state_between_cells(state, mapping, direction=...)`

Responsibilities:

- map explicit local-ray states from original-cell to reshaped-cell convention,
- map explicit local-ray states from reshaped-cell back to original-cell
  convention when needed,
- preserve local-ray projectors up to gauge conventions,
- attach enough metadata so downstream diagnostics know which basis the state is
  expressed in.

## Data Representation

Let the original chemical-cell basis vectors be `a`, and the new magnetic-cell
basis vectors be `A`, with

`A = M a`

for an integer nonsingular matrix `M`.

If the original model has `n_site` crystallographic sites per chemical cell,
then the reshaped magnetic cell has

`n_site_reshaped = |det(M)| * n_site`

sites.

### Coset Representatives

The reshape core should explicitly enumerate a complete set of chemical-cell
translation representatives `t_alpha` inside the magnetic cell.

Each reshaped site is labeled by a pair:

- chemical-cell representative index `alpha`,
- original site index `s`.

The new site numbering is then a deterministic flattening of `(alpha, s)`.

This avoids hidden assumptions and gives every downstream mapping a stable,
invertible indexing convention.

### Reshaped Positions

For each representative `t_alpha` and original position `r_s`, define the
reshaped site position by

`r'_(alpha, s) = t_alpha + r_s`

then fold it into the canonical fractional range of the magnetic-cell basis.

### Reshaped Bonds

For an original bond from site `s_i` to site `s_j` with translation `R_old`,
the reshape core must, for each representative `t_alpha`, decompose

`t_alpha + R_old = R_new + t_beta`

where:

- `t_beta` is another representative inside the magnetic cell,
- `R_new` is an integer translation in the magnetic-cell basis.

The reshaped bond becomes:

- `source = (alpha, s_i)`
- `target = (beta, s_j)`
- `R = R_new`

with the same pair tensor payload as the original bond.

### Onsite Terms

Each original onsite term on site `s` is duplicated onto every reshaped site
`(alpha, s)`.

No extra geometric logic is needed beyond the site-index remapping.

## Workflow Integration

The new branch should be inserted after the repository has already found an
explicit classical state on some initial periodic supercell and before GLSWT is
launched.

### Proposed Flow

1. Run the existing classical solver path on the original model.
2. Inspect projector diagnostics.
3. Select the largest nonzero `q` component.
4. Build a candidate magnetic-supercell matrix.
5. Reject the branch immediately if:
   - no acceptable nonzero `q` exists,
   - the selected `q` is not reliably commensurate,
   - the candidate determinant exceeds configured limits,
   - reshape diagnostics fail.
6. Reshape the model into the candidate magnetic cell.
7. Lift the current explicit classical state into the reshaped-cell basis to
   obtain a structured initial state.
8. Run classical minimization on the reshaped model:
   - Python classical minimization on the reshaped model,
   - optionally Sunny classical minimization on the same reshaped model for
     cross-checking.
9. Compare energies against the original branch.
10. Accept the magnetic-cell refinement only if energy is lower by more than a
    configured tolerance.
11. If accepted, use the refined reshaped model and refined classical state as
    the selected downstream GLSWT input.
12. Build Python GLSWT and Sunny GLSWT payloads from that selected result
    without special-case conversion logic.

### Acceptance Policy

The branch should be conservative by default.

Recommended acceptance rules:

- require a nonzero energy improvement exceeding `energy_gain_tolerance`,
- reject candidates with determinant above `max_magnetic_cell_volume`,
- reject candidates that blow up site or bond counts beyond configured limits,
- record all rejection reasons explicitly in diagnostics.

The default behavior should be "keep the old branch unless the refinement is
clearly better."

## GLSWT Integration

Once the reshaped model and reshaped classical state are selected, GLSWT should
be a normal downstream consumer.

### Python GLSWT

The Python GLSWT payload builder should accept the reshaped model and reshaped
explicit local rays as an ordinary periodic local-ray problem.

No extra magnetic-supercell-only logic should remain in the solver once the
reshape stage has completed.

### Sunny GLSWT

The Sunny GLSWT payload builder should likewise consume the reshaped model and
reshaped explicit local rays as its input surface.

Sunny may still use its own system-level reshape internally where appropriate,
but the repository contract should already be consistent before lowering into
Julia.

## Out Of Scope

This design does not require:

- using third-party structure or symmetry packages for the core reshape logic,
- supporting incommensurate ordering in this first reshape branch,
- adding a generic search over multiple nonzero `q` candidates in the first
  implementation,
- proving exact branch equivalence across all possible gauges in GLSWT output,
- replacing the existing single-q ansatz pathway.

The first implementation is about commensurate, explicit, periodic,
model-exact reshaping.

## Testing Strategy

The implementation must be driven by layered tests.

### 1. Geometry / Indexing Tests

Test that reshape produces the expected number of reshaped sites:

- `n_site_reshaped = |det(M)| * n_site`

Check:

- coset representatives are unique and complete,
- reshaped positions lie in canonical magnetic-cell coordinates,
- old/new site-index mappings are invertible.

### 2. Bond Rewrite Energy-Invariance Tests

Build small toy multi-site `CP^(N-1)` models with explicit pair tensors and
onsite terms. For explicit periodic states:

- evaluate energy in the original model,
- lift the state to the reshaped basis,
- evaluate energy in the reshaped model.

These energies must agree to numerical tolerance.

This is the key correctness test for the reshape core.

### 3. State Lift Round-Trip Tests

For explicit local-ray states:

- original -> reshaped -> original

should preserve projectors and energy density up to accepted gauge conventions.

### 4. Classical Workflow Tests

Construct at least one toy case where a nonzero `q` branch corresponds to a
smaller-energy reshaped-cell refinement.

Verify that:

- the candidate branch is proposed,
- the reshaped Python classical solver runs successfully,
- the refined branch is accepted,
- the selected output state is explicit and periodic.

### 5. GLSWT Integration Tests

Verify that an accepted reshaped refined state can be consumed by:

- `build_python_glswt_payload(...)`
- `build_sun_gswt_payload(...)`

and that both payloads execute through their respective GLSWT backends without
contract-level failures.

### 6. FeI2 Regression Test

Use the canonical FeI2 validation path as a real integration case.

The goal is not to require acceptance of the magnetic-cell branch on every run.
The goal is to ensure:

- the branch can be proposed and diagnosed,
- the branch either accepts or rejects with explicit reasons,
- any accepted refined state feeds into the existing Python/Sunny GLSWT
  downstream path.

## Files Likely Involved

New or heavily modified areas are expected to include:

- `translation-invariant-spin-model-simplifier/scripts/common/...`
  - new magnetic-supercell candidate and reshape helpers
- `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py`
  - allow reshaped periodic models to run through ordinary Python minimization
- `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
  - orchestration and branch-selection logic
- `translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
  - confirm reshaped models/states flow through cleanly
- `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
  - confirm reshaped models/states flow through cleanly
- new targeted tests under
  `translation-invariant-spin-model-simplifier/tests/`

## Risks

### 1. Wrong Integer-Cell Enumeration

If coset representatives are wrong, every downstream object will be wrong while
still looking superficially plausible.

Mitigation:

- explicit determinant-based counting tests,
- bijective mapping tests,
- energy-invariance tests on toy models.

### 2. Bond Double Counting Or Missing Representatives

A reshape bug can silently duplicate or drop bonds.

Mitigation:

- state-by-state energy invariance tests,
- reshaped bond-count diagnostics,
- deterministic canonical representative rules.

### 3. State Lift Gauge Confusion

Local rays carry gauge freedom, so naive equality checks can fail even when the
physical state is equivalent.

Mitigation:

- compare projectors rather than raw vectors when appropriate,
- use energy preservation as the invariant of record.

### 4. Workflow Explosion

Allowing every nonzero `q` candidate could make the refinement branch too
expensive.

Mitigation:

- first implementation only tries the largest nonzero projector component,
- configurable determinant/site-count/bond-count cutoffs,
- explicit skip diagnostics.

## Recommended First Implementation Boundary

The first implementation should be fully general over:

- multi-site periodic `CP^(N-1)` models,
- arbitrary nonsingular integer magnetic-supercell matrices,
- explicit periodic local-ray states.

But it should stay conservative in search behavior:

- only one candidate branch from the largest nonuniform projector component,
- only commensurate candidates,
- no broad candidate ranking search in the first pass.

That boundary gives a reusable core without letting the first rollout turn into
an uncontrolled magnetic-ordering search engine.
