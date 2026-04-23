# Single-Q Harmonic Variational Design

## Goal

Replace the current `lt-single-q-cosine` spin-only variational parametrization with a closely related but numerically cleaner single-`Q` harmonic mode that can still be seeded directly from LT data while retaining explicit strong constraints on the real-space spins.

## Problem

The current constrained FeI2 path already optimizes the ordering vector `Q`, per-site Cartesian phase offsets, and Cartesian amplitudes under explicit nonlinear constraints `|u_i(R)|^2 = 1`. That resolved the old projection artifact, but it did not reproduce the target Sunny-like branch.

The remaining issue is no longer whether amplitudes are fixed. The real restriction is the ansatz family itself:

`u_{ia}(R) = A_{ia} cos(Q · r_{iR} + phi_{ia})`

This representation is equivalent to a single harmonic mode, but the separate amplitude/phase parametrization is awkward near small amplitudes and creates a harder constrained optimization landscape than necessary.

## Recommended Approach

Introduce a new opt-in variational mode:

`variational.mode = "lt-single-q-harmonic"`

with raw real-space fields written as

`u_i(R) = c_i cos(Q · r_{iR}) + s_i sin(Q · r_{iR})`

where each `c_i` and `s_i` is a three-component real Cartesian vector for site `i`.

This keeps the solver within the same physical scope:

- single ordering vector `Q`
- single harmonic in real space
- direct magnetic-supercell energy minimization
- explicit nonlinear constraints `|u_i(R)|^2 = 1` at every supercell cell and site

but changes the optimization coordinates into a form that is smoother, easier to seed from LT, and easier to differentiate analytically.

## Why This Is The Right Next Step

This mode is the narrowest continuation that still meaningfully relaxes the current ansatz surface.

- It is broader than the current amplitude/phase parametrization in numerical practice, because the optimizer works directly with Cartesian harmonic coefficients instead of navigating angle wrapping and near-zero amplitudes.
- It remains much smaller in scope than a genuine multi-`Q` or multi-harmonic solver family.
- It preserves the current downstream contract, so LSWT and later stages do not need to be redesigned just to test whether the single-`Q` manifold is still the bottleneck.

If this new mode still fails to approach the desired FeI2 branch, we will have a much cleaner basis for concluding that the missing ingredient is the physical expressiveness of single-`Q` single-harmonic states rather than merely poor parametrization.

## LT Seeding

The new mode should continue to require an LT seed, as the current `lt-single-q-cosine` mode does.

The LT payload should be converted into initial harmonic coefficients by reading the real and imaginary parts of the LT mode:

- `c_i` from the LT-aligned cosine component
- `s_i` from the LT-aligned sine component

This preserves the intended interpretation of LT as a physically informed initializer rather than a separate solver branch.

The existing LT commensurate-shape logic should remain in force so that the first searched supercell can already represent the seeded `Q`.

## Objective And Constraints

The objective remains the direct classical energy per primitive cell evaluated on the raw supercell field. There should be no projection or post-hoc normalization inside the objective.

The explicit nonlinear equality constraints remain

`|u_i(R)|^2 - 1 = 0`

for every supercell cell and site.

This preserves the main lesson from the earlier debugging cycle: the solver must treat spin normalization as an explicit feasibility condition instead of allowing a low-energy but singular raw field to sneak through projection.

## Derivatives

The new mode should keep analytic derivatives for both:

- the objective gradient
- the constraint Jacobian

Relative to the current amplitude/phase form, the new derivatives are more direct:

- derivatives with respect to `c_i` scale with `cos(Q · r)`
- derivatives with respect to `s_i` scale with `sin(Q · r)`
- derivatives with respect to `Q` come from differentiating the harmonic phase
- the constraint Jacobian remains `2 u · du/dx`

The current `trust-constr` workflow, feasibility-first best-candidate selection, and constraint diagnostics can be reused with minimal structural change.

## Output Contract

The new mode should preserve the current variational result surface as much as possible:

- keep `ordering.q_vector`
- keep `supercell_shape` and `magnetic_supercell_shape`
- keep `ansatz_stationarity`
- keep `initialization.lt_seed_*`
- keep `diagnostics_summary`
- keep raw norm diagnostics as the main feasibility report

The key contract change is only the ansatz identity:

- `ansatz = "lt-single-q-harmonic"`
- `method` string updated to the new mode name
- stationarity diagnostics should describe the `c/s` harmonic parametrization explicitly

This minimizes downstream risk and keeps comparisons with existing `lt-single-q-cosine` artifacts straightforward.

## Scope

- Add a new `lt-single-q-harmonic` variational mode in `classical_solver_driver.py`.
- Implement LT-seeded initialization for per-site harmonic coefficients.
- Implement raw-state construction, objective evaluation, analytic gradient, explicit constraints, and analytic Jacobian for the new mode.
- Reuse the current `trust-constr` search structure and feasibility-first candidate ranking.
- Add focused regression tests for mode routing, gradients, Jacobians, contract stability, and basic constrained convergence on a simple AF chain.

## Non-Goals

- Do not remove `lt-single-q-cosine` yet.
- Do not introduce multi-`Q` support.
- Do not introduce higher harmonics.
- Do not redesign LSWT or downstream classical-state consumers.
- Do not treat FeI2 success as guaranteed from this step alone.

## Testing Strategy

Add test-first coverage in `tests/test_classical_solver_driver.py` for:

- routing to the new `lt-single-q-harmonic` mode
- successful LT-seeded constrained execution on the simple one-site AF chain fixture
- finite-difference agreement for the analytic objective gradient
- finite-difference agreement for the analytic constraint Jacobian
- preservation of the existing ordering/supercell output contract

The tests should be sufficient to prove that the new mode is not merely syntactically wired, but numerically consistent with the intended constrained optimization problem.

## Expected Outcome

After this change, the repository should support two closely related LT-seeded single-`Q` variational branches:

- the older `lt-single-q-cosine` amplitude/phase parametrization
- the new `lt-single-q-harmonic` Cartesian harmonic-coefficient parametrization

This gives the FeI2 investigation a controlled A/B comparison. If the harmonic mode improves optimization quality or reaches better feasible states, we gain a more reliable single-`Q` variational baseline. If it still misses the target branch, the next escalation can focus on physical expressiveness rather than numerical parametrization.
