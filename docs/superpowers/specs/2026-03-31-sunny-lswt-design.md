# Sunny-Backed LSWT Design

## Context

The current `translation-invariant-spin-model-simplifier` skill advertises a workflow that continues from model simplification through classical analysis into linear spin wave theory. In practice, the current LSWT helper in `scripts/linear_spin_wave_driver.py` only supports a narrow scalar-exchange teaching example and cannot faithfully cover the broader anisotropic bilinear spin-model scope described elsewhere in the skill docs.

The requested upgrade is to make the LSWT stage operate from a classical ground state and use an open-source implementation path rather than extending the current toy solver beyond its scientifically reliable scope. The preferred external backend for the first production-quality implementation is `Sunny.jl`.

## Goal

Add a first-stage LSWT path that supports explicit bilinear spin models, consumes a classical reference state produced by the skill workflow, delegates the spin-wave calculation to `Sunny.jl`, and reports scope, assumptions, and failures clearly.

## Supported Scope

First-stage supported models:

- translation-invariant explicit spin models
- bilinear exchange couplings, including isotropic and anisotropic `3x3` exchange tensors
- named cases such as `Heisenberg`, `XXZ`, and `XYZ`
- Dzyaloshinskii-Moriya interactions expressible through antisymmetric exchange tensors
- Zeeman field terms
- on-site single-ion anisotropy terms where the model remains in explicit spin form
- one-site and multi-sublattice crystallographic unit cells
- LSWT around a supplied classical reference state

First-stage non-goals:

- arbitrary non-spin local operator algebras without a validated spin mapping
- generic higher-body interactions beyond the bilinear-plus-onsite scope
- nonlinear magnon interactions beyond harmonic LSWT
- automatic support for every possible classical ordering family on day one
- a second independent self-written Bogoliubov solver inside Python

## Scientific Basis

The target LSWT architecture follows the local-frame workflow recommended in Toth and Lake, *Linear spin wave theory for single-Q incommensurate magnetic structures* ([arXiv:1402.6069](https://arxiv.org/abs/1402.6069)):

1. Start from a classical reference state.
2. Rotate each spin into its local frame.
3. Apply the Holstein-Primakoff expansion to quadratic order.
4. Build the bosonic quadratic Hamiltonian in momentum space.
5. Diagonalize the bosonic problem with a paraunitary Bogoliubov method.

The skill should use `Sunny.jl` as the implementation backend for this route instead of re-deriving and maintaining the full LSWT machinery in local Python code.

## High-Level Architecture

The end-to-end workflow becomes:

`normalize -> simplify -> classical solve -> build LSWT payload -> run Sunny -> collect results -> render report`

Responsibilities by component:

- `scripts/classical_solver_driver.py`
  - Produce a structured classical reference state suitable for downstream LSWT.
  - Stop reporting only an ad hoc spin array without model context.
- `scripts/build_lswt_payload.py` (new)
  - Validate that the simplified model is within first-stage LSWT scope.
  - Convert the simplified model plus classical reference state into a backend-neutral LSWT payload.
  - Normalize exchange, onsite, and field terms into an explicit representation.
- `scripts/run_sunny_lswt.jl` (new)
  - Read the normalized LSWT payload.
  - Construct the Sunny system and couplings.
  - Inject the classical reference state.
  - Run LSWT and serialize results to JSON.
- `scripts/linear_spin_wave_driver.py`
  - Become an orchestration wrapper instead of a toy solver.
  - Call the payload builder.
  - Detect Julia and Sunny availability.
  - Execute the Julia backend and capture structured failures.
- `scripts/render_report.py`
  - Report the backend used, LSWT assumptions, scope checks, and any failure or fallback reasons.

## Data Contracts

### Classical Output Contract

The classical stage must emit a stable structure that downstream code can trust. At minimum it should contain:

- lattice and unit-cell metadata used during the classical solve
- the simplified bilinear spin model actually solved
- reference-state site directions for the unit cell or magnetic cell
- spin length per site or per species
- ordering metadata when known, such as a propagation vector or magnetic-cell expansion note
- method provenance and convergence metadata

Example conceptual shape:

```json
{
  "classical_state": {
    "site_frames": [
      {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}
    ],
    "ordering": {
      "kind": "commensurate",
      "q_vector": [0.0, 0.0, 0.0]
    },
    "provenance": {
      "method": "variational",
      "converged": true
    }
  }
}
```

### LSWT Payload Contract

The backend-neutral payload passed into the Julia runner should include:

- crystal or graph topology information
- sublattice metadata
- bond list with explicit `3x3` exchange matrices
- onsite anisotropy terms
- field terms
- spin magnitudes
- reference-state directions
- requested momentum path or grid
- optional output flags such as dispersion, structure factor, or thermodynamics

This contract must be explicit enough that future non-Sunny backends could consume the same payload without changing the upstream skill flow.

## Backend Strategy

`Sunny.jl` is the only formal LSWT backend for the first stage.

Why:

- it already implements the scientifically appropriate route from a classical magnetic structure into harmonic spin-wave calculations
- it is a better fit for automated scripting than a MATLAB-dependent package
- it provides a path to richer future outputs without forcing a fragile custom solver today

The existing Python scalar-exchange LSWT approximation should not remain as the default hidden fallback. If Sunny is unavailable or the model is outside scope, the LSWT stage must stop clearly and explain why.

## Failure Handling

Before attempting LSWT, the driver must perform:

1. scope validation
2. environment validation
3. payload validation

Required failure classes:

- `unsupported-model-scope`
- `missing-julia-runtime`
- `missing-sunny-package`
- `invalid-classical-reference-state`
- `backend-execution-failed`
- `result-parse-failed`

Each failure must include:

- a short machine-readable code
- a human-readable explanation
- whether the classical stage result remains valid
- what the user can do next

Allowed fallback behavior:

- stop after the classical stage and render a partial report
- suggest installing or enabling Julia plus Sunny
- suggest narrowing the model to first-stage supported bilinear scope

Disallowed fallback behavior:

- silently substituting the current toy scalar-exchange dispersion model
- presenting approximation results as if they were formal LSWT outputs

## Reporting Requirements

The report must clearly state:

- whether LSWT ran successfully
- that the backend was `Sunny.jl`
- what classical reference state was used
- what parts of the model were passed to LSWT
- whether the result is a first-stage harmonic spin-wave result or a partial-stop report
- any omitted terms or unsupported features

If LSWT does not run, the report must still include the completed classical result and the reason LSWT stopped.

## Testing Strategy

### Python Unit Tests

Add unit tests for:

- model-scope validation
- conversion of simplified bilinear models into explicit exchange tensors
- conversion of classical reference states into LSWT payload directions
- failure classification for missing runtime or unsupported models

### Julia Integration Tests

Add backend tests that exercise `run_sunny_lswt.jl` on small reference cases:

- two-site antiferromagnetic Heisenberg example
- a small anisotropic `XXZ` or `XYZ` example
- a small case with DM or onsite anisotropy if Sunny input coverage is confirmed

The tests should check for:

- successful backend execution
- JSON result shape
- dispersion data presence
- basic physically expected behavior such as non-negative frequencies where appropriate and identifiable soft modes in benchmark cases

### End-to-End Skill Tests

Add integration coverage for:

- simplification plus classical plus Sunny-backed LSWT success path
- classical success plus LSWT blocked due to missing Sunny
- classical success plus LSWT blocked due to out-of-scope model

## Rollout Plan

Phase 1:

- formalize classical output contract
- add LSWT payload builder
- add Sunny Julia runner
- replace Python toy LSWT logic with orchestration
- update report output

Phase 2:

- extend classical-state encoding for richer multi-sublattice and ordered-state cases
- add additional benchmark models
- expand report outputs such as structure factors if needed

## Open Decisions

These decisions should be resolved during implementation planning:

- exact representation of multi-sublattice and magnetic-cell classical reference states in the payload
- minimum required Sunny environment contract and how installation guidance is surfaced
- whether thermodynamic outputs are part of phase 1 or deferred until dispersion is stable
- how much q-path generation should be implemented locally versus supplied explicitly by the user or upstream stages

## Recommendation

Proceed with a first-stage implementation that narrows the skill’s formal LSWT claim to explicit bilinear spin models with a supplied classical reference state and uses `Sunny.jl` as the only production LSWT backend.
