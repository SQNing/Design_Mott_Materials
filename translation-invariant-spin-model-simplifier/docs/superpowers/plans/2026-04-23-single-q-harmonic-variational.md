# Single-Q Harmonic Variational Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LT-seeded constrained spin-only variational mode `lt-single-q-harmonic` that optimizes single-`Q` Cartesian harmonic coefficients `c cos(Q · r) + s sin(Q · r)` while preserving the existing downstream classical-state contract.

**Architecture:** Keep the existing `trust-constr` multi-start search, explicit `|u_i(R)|^2 = 1` constraints, feasibility-first candidate selection, and downstream result shape from `lt-single-q-cosine`. Add a parallel harmonic branch inside `classical_solver_driver.py` with its own LT payload conversion, raw-state cache, analytic objective gradient, analytic constraint Jacobian, and result metadata, while keeping the old cosine mode intact for A/B comparison.

**Tech Stack:** Python, NumPy, SciPy, unittest, pytest

---

## File Structure

- `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`
  Responsibility: add the new `lt-single-q-harmonic` route, helper functions for LT harmonic payload extraction, raw harmonic state construction, analytic derivatives, constrained optimization, and result/diagnostic assembly.
- `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
  Responsibility: add focused red-green coverage for routing, constrained execution, gradient/Jacobian correctness, and contract stability of the new harmonic mode.

### Task 1: Add routing and contract tests for the new harmonic mode

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`

- [ ] **Step 1: Write the failing test**

Add a test that clones the existing one-site LT-seeded AF-chain fixture, sets
`model["classical"]["variational"]["mode"] = "lt-single-q-harmonic"`,
calls `run_classical_solver(...)`, and asserts:

```python
self.assertEqual(result["classical"]["chosen_method"], "variational")
self.assertEqual(result["variational_result"]["ansatz"], "lt-single-q-harmonic")
self.assertEqual(result["variational_result"]["search_settings"]["mode"], "lt-single-q-harmonic")
self.assertEqual(result["variational_result"]["supercell_shape"], [4, 1, 1])
self.assertEqual(result["variational_result"]["ordering"]["ansatz"], "lt-single-q-harmonic")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k harmonic`

Expected: FAIL because `lt-single-q-harmonic` is not yet a recognized variational mode.

- [ ] **Step 3: Write minimal implementation**

In `classical_solver_driver.py`:

- add a small fixture helper path that accepts `settings["mode"] == "lt-single-q-harmonic"`
- route that mode to a new `_lt_single_q_harmonic_variational(...)` function stub
- return a minimal result object with:
  - `ansatz = "lt-single-q-harmonic"`
  - `search_settings["mode"] = "lt-single-q-harmonic"`
  - `ordering["ansatz"] = "lt-single-q-harmonic"`

Do not implement full optimization yet. Only wire enough structure for the routing test to pass once the function body is filled in later tasks.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k harmonic`

Expected: PASS for the new routing/contract test.

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "feat: add single-q harmonic variational routing"
```

### Task 2: Add failing tests for harmonic raw-field derivatives

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`

- [ ] **Step 1: Write the failing tests**

Add two tests modeled after the existing cosine derivative coverage:

```python
def test_single_q_harmonic_analytic_gradient_matches_finite_difference(self):
    ...

def test_single_q_harmonic_constraint_jacobian_matches_finite_difference(self):
    ...
```

Use a one-site chain, `shape = [3, 1, 1]`, and a trial vector containing:

- one reduced `Q` component
- one site's `c_x, c_y, c_z`
- one site's `s_x, s_y, s_z`

Assert `np.testing.assert_allclose(...)` against centered finite differences with tolerances similar to the cosine tests.

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and gradient"`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and jacobian"`

Expected: FAIL because the harmonic helper functions do not exist yet.

- [ ] **Step 3: Write minimal implementation**

In `classical_solver_driver.py`, add:

- `_lt_single_q_harmonic_mode_payload(...)`
- `_split_single_q_harmonic_vector(...)`
- `_single_q_harmonic_raw_state_and_cache(...)`
- `_single_q_harmonic_value_and_gradient(...)`
- `_single_q_harmonic_constraints_and_jacobian(...)`

Implementation notes:

- interpret each site's variables as real Cartesian vectors `c_i` and `s_i`
- compute
  `raw = c_i * cos(base_phase) + s_i * sin(base_phase)`
- cache `coordinates`, `phase`, `cos_phase`, `sin_phase`, and `raw`
- differentiate `Q` through the phase and differentiate `c/s` directly through the harmonic basis
- keep the constraint form `np.dot(raw, raw) - 1.0`

- [ ] **Step 4: Run tests to verify they pass**

Run:
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and gradient"`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and jacobian"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "feat: add single-q harmonic derivatives"
```

### Task 3: Add constrained-execution tests and implement the full harmonic solver path

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`

- [ ] **Step 1: Write the failing tests**

Add a focused constrained-execution test on the one-site AF-chain LT-quarter-seed fixture that asserts:

```python
self.assertEqual(result["variational_result"]["ansatz_stationarity"]["optimizer_method"], "trust-constr")
self.assertLess(
    result["variational_result"]["ansatz_stationarity"]["optimizer_constraint_violation"],
    1.0e-8,
)
self.assertLess(
    result["variational_result"]["ansatz_stationarity"]["raw_norm_diagnostics"]["max_abs_norm_minus_1"],
    1.0e-8,
)
self.assertEqual(
    result["variational_result"]["initialization"]["lt_seed_q_vector"],
    [0.25, 0.0, 0.0],
)
```

Add a second contract test that feeds a harmonic `variational_result` into `_build_variational_classical_state(...)` and confirms the explicit `ordering` block is preserved.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k "harmonic and (constraint or classical_state)"`

Expected: FAIL because the full harmonic constrained solver path and ordering integration are not implemented yet.

- [ ] **Step 3: Write minimal implementation**

Fill in `_lt_single_q_harmonic_variational(...)` so it:

- resolves LT seed and commensurate shape exactly as the cosine path does
- converts LT data to initial `c/s` coefficients
- builds deterministic starts:
  - LT-seeded start
  - simple uniform feasible harmonic start
  - simple planar feasible harmonic start
- runs `scipy.optimize.minimize(..., method="trust-constr", jac=True, constraints=[...])`
- ranks candidates with the existing feasibility-first logic
- emits a result payload mirroring the cosine branch, but with:
  - `ansatz = "lt-single-q-harmonic"`
  - harmonic-specific `objective_definition`
  - harmonic-specific optimized/initial coefficient diagnostics

Keep `_build_variational_classical_state(...)` unchanged if explicit `ordering` already passes through. Only touch it if the new ansatz identity or metadata requires a tiny compatibility adjustment.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q -k harmonic`

Expected: PASS for all harmonic routing, derivative, constrained-execution, and contract tests.

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "feat: add single-q harmonic constrained variational mode"
```

### Task 4: Run the targeted regression suite and compare against the existing cosine branch

**Files:**
- Test: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_lt_solver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_lt_tensor_constraint_completion.py`

- [ ] **Step 1: Run the targeted harmonic-focused suite**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py -q`

Expected: PASS

- [ ] **Step 2: Run adjacent LT/GLT regression slices**

Run:
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_lt_solver.py -q`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py -q`
- `python -m pytest translation-invariant-spin-model-simplifier/tests/test_lt_tensor_constraint_completion.py -q`

Expected: PASS

- [ ] **Step 3: Run one explicit A/B comparison artifact if time permits**

Run a narrow local smoke using the existing FeI2 workflow harness so that both
`lt-single-q-cosine` and `lt-single-q-harmonic` can be compared on the same payload.

Suggested success criterion:

- harmonic run is feasible
- artifact records `ansatz = "lt-single-q-harmonic"`
- result is comparable against cosine without breaking the classical contract

- [ ] **Step 4: Record the observed comparison in docs or session memory**

Capture whether the new mode:

- improves energy
- changes `Q`
- only improves conditioning/diagnostics

This note is enough; no new permanent report file is required unless the comparison materially changes the roadmap.

- [ ] **Step 5: Commit**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py \
        translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py
git commit -m "test: verify single-q harmonic variational regressions"
```
