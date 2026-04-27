# Single-Q Harmonic Variational Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `lt-single-q-harmonic` as the public variational mode, but improve basin entry for the converged manifold-CG branch by adding guided `Q` start families and a conservative `beta` clamp.

**Architecture:** Reuse the now-working manifold-CG harmonic kernel in `classical_solver_driver.py`, but add a small generic mechanism for targeted basin entry. The solver should accept optional `guided_q_vectors`, synthesize deterministic guided feasible starts around those `Q` values with both LT-aligned and planar in-plane bases, and modestly stabilize CG direction inheritance with a configurable `cg_beta_max` clamp plus `beta_clamped_count` diagnostics. Preserve the existing mode name and result surface while making basin hypotheses explicit in settings and output.

**Tech Stack:** Python, NumPy, unittest, pytest

---

## File Structure

- `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`
  Responsibility: add orthonormal-pair helpers, manifold projection/retraction, Sunny-like line search/update loop, and updated harmonic result diagnostics while keeping the mode entry point unchanged.
- `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
  Responsibility: add red-green coverage for the new minimizer contract, helper invariants, and ordering/state compatibility.

### Task 1: Lock the guided-start and beta-clamp contract with failing tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`

- [ ] **Step 1: Write the failing tests**

Add a focused execution test for the one-site LT-seeded AF-chain harmonic fixture that sets:

```python
model["classical"]["variational"]["guided_q_vectors"] = [
    [0.5, 0.25, 0.0],
    [0.75, 0.0, 0.0],
]
```

and asserts:

```python
self.assertEqual(result["variational_result"]["ansatz"], "lt-single-q-harmonic")
self.assertEqual(
    result["variational_result"]["ansatz_stationarity"]["optimizer_method"],
    "sunny-like-manifold-cg",
)
self.assertEqual(
    result["variational_result"]["ansatz_stationarity"]["optimization_mode"],
    "lt-seeded-spiral-manifold-cg-and-q-relaxation",
)
self.assertLess(
    result["variational_result"]["ansatz_stationarity"]["raw_norm_diagnostics"]["max_abs_norm_minus_1"],
    1.0e-8,
)
self.assertLessEqual(
    result["variational_result"]["energy"],
    result["variational_result"]["ansatz_stationarity"]["initial_objective"] + 1.0e-10,
)
self.assertIn("restart_count", result["variational_result"]["ansatz_stationarity"])
self.assertIn("final_beta", result["variational_result"]["ansatz_stationarity"])
self.assertIn("beta_clamped_count", result["variational_result"]["ansatz_stationarity"])
```

Add a second test that checks the first eight `candidate_start_summaries[*]["start_source"]` values are:

```python
[
    "lt-harmonic-seed",
    "lt-aligned-feasible",
    "planar-feasible",
    "uniform-feasible",
    "guided-lt-aligned-q-0",
    "guided-planar-q-0",
    "guided-lt-aligned-q-1",
    "guided-planar-q-1",
]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and (guided or explicit_norm_constraints)"`

Expected: FAIL because guided start families and `beta_clamped_count` are not implemented yet.

- [ ] **Step 3: Write minimal implementation**

Do not change the full solver yet. Only update enough reporting scaffolding, if needed, to support the new contract once the real kernel lands.

- [ ] **Step 4: Run test to verify it still fails for the right reason**

Run the same command and confirm failure is now about missing manifold behavior rather than a typo in the test.

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py
git commit -m "test: lock sunny-like harmonic minimizer contract"
```

### Task 2: Add helper-level failing tests for guided starts and beta clamp

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`

- [ ] **Step 1: Write the failing tests**

Add helper tests for:

- orthonormal retraction:

```python
pair = np.array([[1.2, 0.1], [0.3, 0.9], [0.0, 0.4]], dtype=float)
retracted = _single_q_harmonic_retract_pair(pair)
np.testing.assert_allclose(retracted.T @ retracted, np.eye(2), atol=1e-8)
```

- tangent projection:

```python
projected = _single_q_harmonic_project_pair_tangent(pair, gradient)
np.testing.assert_allclose(pair.T @ projected + projected.T @ pair, np.zeros((2, 2)), atol=1e-8)
```

- LT-seeded pair construction keeps the generated supercell spins normalized to numerical precision.
- tangent transport keeps the spin block in the current tangent space.
- `beta` clamp helper returns the configured ceiling and reports that clamping occurred.

- [ ] **Step 2: Run tests to verify they fail**

Run:

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and (retract or tangent or normalized)"`

and

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and beta"`

Expected: FAIL because the clamp helper and guided start helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add helpers for:

- pair retraction by Gram-Schmidt
- tangent projection using `G - Y sym(Y^T G)`
- tangent transport by re-projecting the previous spin direction to the new tangent space
- a small `beta` clamp helper that returns `(beta, was_clamped)`
- guided `Q` parsing from settings
- guided feasible start builders for LT-aligned and planar bases
- joint vector helpers that split spin and `Q` blocks cleanly
- conversion between flat vector form and per-site orthonormal pairs
- state generation using retracted pairs and the current `Q`

- [ ] **Step 4: Run tests to verify they pass**

Run the same helper-focused command and confirm PASS.

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "feat: add harmonic manifold helper mechanics"
```

### Task 3: Extend the harmonic manifold-CG loop with guided starts and conservative `beta` handling

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`

- [ ] **Step 1: Write the failing tests**

Add focused tests that exercise a real run and assert:

- reported optimizer method is `sunny-like-manifold`
- reported optimizer method is `sunny-like-manifold-cg`
- raw norm residual remains tiny
- `optimizer_constraint_violation` is `0.0` or omitted in favor of structural norm preservation
- final energy is not higher than the LT-seeded initial energy
- stationarity reports both spin and `Q` residuals
- stationarity reports CG-specific diagnostics such as restart count and final `beta`
- stationarity reports `beta_clamped_count`
- guided starts appear in `candidate_start_summaries`

- [ ] **Step 2: Run tests to verify they fail**

Run:

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k harmonic`

Expected: FAIL because the current solver does not yet synthesize guided starts or clamp large `beta` values.

- [ ] **Step 3: Write minimal implementation**

Inside `_lt_single_q_harmonic_variational(...)`:

- keep LT seed resolution and commensurate shape handling
- convert LT cosine/sine coefficients into orthonormal per-site pairs
- parse optional `guided_q_vectors`
- build the baseline start family:
  - LT-seeded pair start
  - simple planar fallback
- append deterministic guided starts for each guided `Q`:
  - `guided-lt-aligned-q-<n>`
  - `guided-planar-q-<n>`
- keep LT-randomized and broad random starts after the deterministic family
- keep the manifold-CG loop, but add conservative `beta` handling:
  - evaluate energy and analytic ambient gradient
  - project spin gradients onto the pair tangent space
  - transport the previous spin direction into the current tangent space
  - compute a Polak-Ribiere-style `beta` with restart safeguards
  - clamp `beta` to `cg_beta_max` when configured
  - build one joint search direction for the full spin-plus-`Q` vector
  - take one Armijo backtracking step on that joint direction
  - retract the spin block and clip the `Q` block
  - restart to steepest descent if `beta` is invalid or the trial direction is not descending
- accept convergence only when actual stationarity tolerances are met
- emit updated diagnostics:
  - `optimizer_method = "sunny-like-manifold-cg"`
  - `optimization_mode = "lt-seeded-spiral-manifold-cg-and-q-relaxation"`
  - `initial_objective`
  - `spin_gradient_norm`
  - `q_gradient_norm`
  - `accepted_iterations`
  - `restart_count`
  - `final_beta`
  - `beta_clamped_count`
  - `candidate_start_summaries`

- [ ] **Step 4: Run tests to verify they pass**

Run:

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k harmonic`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "feat: add guided harmonic starts and beta clamp"
```

### Task 4: Run focused regression verification and one guided FeI2 comparison

**Files:**
- Test: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_lt_solver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_lt_tensor_constraint_completion.py`
- Update: `session-memory/sessions/design-mott-materials-2026-04-23-1713.md`
- Update: `session-memory/index/design-mott-materials.md`

- [ ] **Step 1: Run the focused harmonic suite**

Run:

`python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q`

Expected: PASS

- [ ] **Step 2: Run adjacent LT regression slices**

Run:

- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_lt_solver.py -q`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py -q`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_lt_tensor_constraint_completion.py -q`

Expected: PASS

- [ ] **Step 3: If budget permits, run one narrow FeI2 harmonic smoke**

Success criteria:

- the run finishes without `trust-constr`
- the run reports the manifold-CG kernel explicitly
- the run records the guided start source when it wins
- the artifact records `ansatz = "lt-single-q-harmonic"`
- the run exposes meaningful spin/Q stationarity diagnostics

- [ ] **Step 4: Record the observed outcome in session memory**

Capture whether the new kernel:

- improves energy through a different basin
- changes `Q`
- reduces or increases restart/beta-clamp pressure

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py \
        session-memory/sessions/design-mott-materials-2026-04-23-1713.md \
        session-memory/index/design-mott-materials.md
git commit -m "test: verify sunny-like harmonic minimizer regressions"
```
