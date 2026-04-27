# Single-Q Harmonic Variational Design

## Goal

Keep the existing outward entry point

- `variational.mode = "lt-single-q-harmonic"`
- `_lt_single_q_harmonic_variational(...)`

but replace its internal `trust-constr` constrained-NLP kernel with a more Sunny-like spiral minimization flow:

- LT provides the initial `Q`
- LT provides the initial single-`Q` spin texture
- spins are relaxed on a unit-spin manifold
- `Q` is relaxed as an ordinary Euclidean variable in the same optimization loop

The intent is not to rename the mode or broaden scope to multi-`Q`. The intent is to keep the same user-facing feature while swapping the minimization core to something closer to Sunny's `minimize_spiral_energy!`.

## Problem

The current `lt-single-q-harmonic` branch uses the right single-harmonic coordinates,

`u_i(R) = c_i cos(Q · r_{iR}) + s_i sin(Q · r_{iR})`,

but it still solves them as a generic equality-constrained nonlinear program with `trust-constr`.

This has shown three practical problems in the FeI2 runs:

- progress is highly budget-sensitive
- feasible states often stop at the iteration limit
- warm-start continuation can move uphill while still reporting optimizer success by generic termination criteria

This is a poor match to the user's intended comparison, because Sunny's spiral minimization is not built around generic nonlinear constraints. Sunny treats spins as primary unit vectors on a manifold and optimizes them together with `k` using manifold-aware descent and restarts.

## Recommended Approach

Retain the current harmonic state family but enforce unit-spin structure by construction instead of by explicit equality constraints.

Represent each site's harmonic texture by an orthonormal in-plane pair

- `e1_i`
- `e2_i`

and define

`S_i(R) = e1_i cos(Q · r_{iR}) + e2_i sin(Q · r_{iR})`.

If `e1_i · e1_i = 1`, `e2_i · e2_i = 1`, and `e1_i · e2_i = 0`, then every generated spin is automatically unit length for every cell `R`.

This changes the numerical problem from:

- unconstrained `c_i, s_i` plus many explicit `|u_i(R)|^2 = 1` constraints

to:

- per-site Stiefel-like spin variables `(e1_i, e2_i)` with retraction back to an orthonormal pair after each step
- free reduced `Q` variables updated in Euclidean space

This is much closer in spirit to Sunny's spiral optimizer:

- the spin degrees of freedom live on a normalized manifold
- `Q` is optimized jointly
- line-search/restart behavior can be judged directly from energy descent rather than from generic NLP convergence codes

## Relationship To Sunny

This is not a byte-for-byte reimplementation of Sunny.

Sunny's `minimize_spiral_energy!`:

- works on a single chemical cell
- keeps unit spins via a `SpinManifold`
- treats the wavevector `k` as extra Euclidean coordinates
- uses manifold CG with restart support
- optionally regularizes against pathological alignment with the spiral axis before a final unregularized pass

The proposed Python replacement copies the essential mechanism we need here:

- unit spins are the primary variables
- optimization proceeds by manifold conjugate-gradient steps plus retraction
- `Q` is updated from the same energy gradient, not held fixed
- accepted progress is based on actual energy decrease and gradient/stationarity checks

We will not require a single global spiral axis in this first pass. Each site keeps its own orthonormal in-plane pair. That preserves compatibility with the existing LT-derived harmonic data while still moving decisively toward the Sunny optimization style the user asked for.

## LT Seeding

LT remains mandatory for this mode.

The LT eigenspace mode provides:

- the initial `Q`
- the initial real/imag harmonic components

These are converted into the initial per-site plane as follows:

1. read LT real part as the cosine direction seed
2. read LT imaginary part as the sine direction seed
3. orthonormalize the pair with Gram-Schmidt
4. fall back to a simple planar basis when LT is locally degenerate

This preserves the current meaning of LT as a physics-informed initializer while making the state immediately admissible for manifold optimization.

## Basin-Entry Follow-On

After the first converged FeI2 manifold-CG runs, the evidence changed.

The new bottleneck is no longer simple optimizer instability. Instead, the harmonic manifold-CG route appears to converge reproducibly into one basin near

- `Q ~= [0.7947, 0, 0]`
- `E ~= -1.9206856`

which is well below the old trust-constr harmonic runs but still above the constrained-cosine best `-2.0010584`.

This suggests the next meaningful improvement is not "more undirected budget", but better basin entry.

### Recommended Follow-On Mechanism

Add a generic guided-start mechanism to `lt-single-q-harmonic`:

- optional `variational.guided_q_vectors`
- optional conservative CG setting `variational.cg_beta_max`

`guided_q_vectors` should accept a small list of full three-component fractional `Q` vectors. For each guided `Q`, the solver should build targeted feasible starts such as:

- `guided-lt-aligned-q-<n>`
- `guided-planar-q-<n>`

This lets us test specific basin hypotheses without hardcoding FeI2-specific values into the generic solver.

For the current FeI2 investigation, the most relevant guided `Q` hypotheses are:

- the converged harmonic manifold-CG basin near `[0.7947, 0, 0]`
- the constrained-cosine best basin near `[1/2, 1/4, 0]`
- the old trust-constr harmonic basin near `[0.4678, 0.0331, 0.5]`

These should be passed through settings in experiments, not embedded as defaults in the solver.

## Optimization Kernel

The new kernel should use a Sunny-like joint manifold conjugate-gradient loop rather than alternating steepest-descent substeps.

### Joint Variable Layout

The optimization vector should be treated as a product space:

- manifold block: all per-site orthonormal harmonic pairs `(e1_i, e2_i)`
- Euclidean block: the reduced `Q` components

This matches Sunny's spirit more closely than our current alternating loop because both the spin texture and `Q` are updated through one coupled search direction.

### Tangent Gradient

At each iterate:

1. compute the ambient energy gradient with respect to the cosine/sine pair entries and `Q`
2. project each site's pair gradient onto the tangent space of the orthonormal-pair manifold
3. keep the `Q` gradient unchanged as the Euclidean component

For each site pair `Y = [e1_i e2_i]`, use the Stiefel projection

`G_tangent = G - Y sym(Y^T G)`.

### Conjugate Direction

The search direction should be built from the projected gradient together with the previous transported direction, using a standard nonlinear CG update such as Polak-Ribiere with restart safeguards.

Important details:

- the spin part of the previous direction must be transported to the current tangent space before reuse
- if the computed `beta` is negative, non-finite, or produces a non-descent direction, restart to steepest descent
- if the computed `beta` is excessively large, clamp it conservatively before building the candidate direction
- the `Q` block can reuse the ordinary Euclidean CG recurrence

### Retraction And Line Search

Take one joint step along the combined spin-plus-`Q` direction:

- retract each site's pair back to an orthonormal basis by Gram-Schmidt
- clip `Q` to the allowed bounds
- use backtracking / Armijo line search on the full joint direction

This should preserve the two most important Sunny-like properties:

- spin normalization is structural rather than constraint-enforced
- accepted iterations are based on actual energy decrease along a coupled direction

### Restart / Accept Logic

Repeat the manifold CG loop until one of the following is true:

- projected spin gradient norm and `Q` gradient norm are both below tolerance
- maximum iterations are reached
- repeated line-search failure forces termination

Unlike the current `trust-constr` branch, a state should not be labeled converged merely because an optimizer returned a generic success flag. We should only call the run converged if the final stationarity metrics actually satisfy our tolerances.

## Objective

The objective remains the direct classical energy per primitive cell of the generated magnetic supercell state. There is still no projection inside the objective.

The difference is that unit norms are now guaranteed by the parameterization and retraction rather than by separate nonlinear constraints.

## Output Contract

Preserve the current outward result surface as much as possible:

- `ansatz = "lt-single-q-harmonic"`
- `ordering.q_vector`
- `supercell_shape`
- `magnetic_supercell_shape`
- `state`
- `initialization.lt_seed_*`
- `diagnostics_summary`
- `ansatz_stationarity`

The main contract changes are internal diagnostics:

- `optimizer_method` should report the Sunny-like manifold kernel, not `trust-constr`
- `optimizer_method` should distinguish the CG kernel explicitly
- `optimization_mode` should describe LT-seeded manifold-CG spin + `Q` relaxation
- `raw_norm_diagnostics.max_abs_norm_minus_1` should remain near machine precision because norm preservation is structural
- stationarity should report both spin-manifold and `Q` residuals
- accepted convergence should require non-uphill termination
- diagnostics should expose CG-specific fields such as restart count and final `beta`
- diagnostics should also expose `beta_clamped_count` when conservative clamping is active

## Scope

- Keep the current mode/function names unchanged.
- Replace only the internal minimization kernel of `lt-single-q-harmonic`.
- Reuse existing LT payload extraction and downstream result assembly where possible.
- Add helper functions for orthonormal-pair projection, retraction, tangent transport, CG direction updates, line search, and Sunny-like iteration bookkeeping.
- Add helper functions for parsing guided `Q` starts and synthesizing guided feasible starts from those `Q` values.
- Update focused tests to assert the new minimizer contract rather than the old `trust-constr` one.

## Non-Goals

- Do not rename the mode.
- Do not remove `lt-single-q-cosine`.
- Do not introduce multi-`Q`.
- Do not introduce higher harmonics.
- Do not require a single global spiral axis in this pass.
- Do not claim FeI2 success ahead of the actual reruns.

## Testing Strategy

Use test-first coverage in `tests/test_classical_solver_driver.py` for:

- routing still goes through `lt-single-q-harmonic`
- the reported optimizer method is the new manifold-CG kernel, not `trust-constr`
- LT-seeded runs keep unit norms by construction
- the accepted final energy does not exceed the recorded LT-seeded initial energy
- the ordering/output contract remains compatible with existing consumers

Focused helper-level tests should also cover:

- orthonormal-pair retraction
- tangent projection shape/invariants
- tangent transport / CG restart invariants
- `beta` clamping behavior
- guided `Q` start synthesis / source naming
- energy-gradient-driven joint spin-`Q` update path on a simple one-site AF-chain fixture

## Expected Outcome

After this change, `lt-single-q-harmonic` should stop behaving like a difficult equality-constrained NLP and instead behave like an LT-seeded spiral minimizer:

- better aligned with Sunny's optimization philosophy
- more trustworthy acceptance/convergence logic
- easier to continue from LT-informed basins without the misleading `xtol`-style uphill success behavior we observed with `trust-constr`

If FeI2 still does not reach the desired branch after this kernel replacement, we will have a much stronger basis for blaming the single-`Q` physics restriction rather than the current minimizer.
