# Multi-Sublattice LT And Generalized LT Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Luttinger-Tisza and generalized Luttinger-Tisza workflow to `translation-invariant-spin-model-simplifier`, designed from the start for multi-sublattice matrix Fourier exchange problems.

**Architecture:** The implementation should treat the Fourier-space exchange object as a sublattice-space Hermitian matrix `J_{alpha,beta}(q)` from the first line of code, with single-sublattice models handled only as the `m = 1` special case. Standard LT, strong-constraint recovery, generalized LT Lagrange-parameter optimization, and result reporting should be split into focused modules so that lower-bound search, candidate reconstruction, and downstream verification remain independently testable.

**Tech Stack:** Python 3, NumPy, SciPy, existing project scripts in `translation-invariant-spin-model-simplifier/scripts`, existing report/plot pipeline, pytest-style regression coverage.

---

## File Structure

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_fourier_exchange.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_brillouin_zone.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_solver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_constraint_recovery.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/generalized_lt_solver.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_report.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_plots.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_fourier_exchange.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_solver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_constraint_recovery.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_pipeline_integration.py`
- Reference: `/data/work/zhli/docs/notes/2026-04-06-luttinger-tisza-and-generalized-lt-note.md`

### Responsibility Map

- `lt_fourier_exchange.py`
  Build `J_{alpha,beta}(q)` from bond-shell or explicit bond input. This module owns the Fourier transform convention and any canonical ordering of sublattice indices.

- `lt_brillouin_zone.py`
  Generate full Brillouin-zone sampling meshes and optional refinement utilities. This module exists to prevent accidental “high-symmetry-line only” misuse in LT searches.

- `lt_solver.py`
  Solve the standard multi-sublattice LT problem by diagonalizing `J(q)` over a full `q` mesh, returning the LT lower bound, the minimizing `q`, and the corresponding eigenvector or eigenspace data.

- `lt_constraint_recovery.py`
  Reconstruct real-space candidate spin configurations from low-energy Fourier modes and explicitly evaluate strong-constraint residuals.

- `generalized_lt_solver.py`
  Add sublattice-diagonal Lagrange parameters `Lambda`, optimize them, and expose a tightened lower bound together with the best `q` and low-energy subspace.

- `decision_gates.py`
  Surface LT / generalized-LT as explicit classical-solver choices instead of forcing the workflow into only `luttinger-tisza` or `variational`.

- `render_report.py`
  Show LT outputs clearly: minimizing `q`, lowest eigenvalue, strong-constraint residual, generalized-LT `Lambda`, and whether a lower bound was saturated.

- `render_plots.py`
  Add LT-specific diagnostics plots only after the solver output is stable. Do not fold plotting assumptions into solver modules.

---

### Task 1: Fourier Exchange Matrix Foundation

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_fourier_exchange.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_fourier_exchange.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- a single-sublattice Heisenberg chain where `J(q)` reduces to a scalar matrix with the expected cosine form
- a multi-sublattice toy model where `J_{alpha,beta}(q)` has the expected Hermitian structure
- explicit confirmation that the single-sublattice case is represented as a `1 x 1` matrix, not a separate scalar code path

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_fourier_exchange.py -q
```

Expected:
- import or missing-function failures for the new module

- [ ] **Step 3: Implement the minimal Fourier exchange builder**

Add a first version of:
- bond canonicalization for LT input
- `fourier_exchange_matrix(model, q)`
- helpers for enumerating sublattices and assembling Hermitian matrices

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_fourier_exchange.py -q
```

Expected:
- all tests pass

---

### Task 2: Full Brillouin-Zone LT Search

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_solver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_brillouin_zone.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_solver.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- a single-sublattice antiferromagnetic chain with minimum near `q = pi`
- a toy multi-sublattice model where the minimizing `q` and lowest eigenvalue are known analytically or by direct construction
- a regression asserting that the solver uses a full mesh instead of only the high-symmetry path

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_solver.py -q
```

Expected:
- missing-module or missing-function failures

- [ ] **Step 3: Implement the minimal LT search**

Implement:
- Brillouin-zone mesh generation
- matrix diagonalization over the mesh
- return payload with:
  - best `q`
  - lowest eigenvalue
  - corresponding eigenvector or eigenspace
  - mesh metadata

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_solver.py -q
```

Expected:
- all tests pass

---

### Task 3: Strong-Constraint Recovery

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_constraint_recovery.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lt_constraint_recovery.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- a simple LT mode that reconstructs an exact unit-length spiral
- a multi-sublattice candidate that does not satisfy sitewise normalization and therefore reports a nonzero residual
- a helper returning an explicit residual measure, not only a boolean

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_constraint_recovery.py -q
```

Expected:
- missing recovery functions

- [ ] **Step 3: Implement the minimal recovery layer**

Implement:
- single-`q` real-space reconstruction
- strong-constraint residual evaluation
- a minimal projection or normalization helper for diagnostics only

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_constraint_recovery.py -q
```

Expected:
- all tests pass

---

### Task 4: Generalized LT Outer Optimization

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/generalized_lt_solver.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- a small multi-sublattice toy model where generalized LT improves on the standard LT lower bound
- gauge fixing of `Lambda` via a condition such as `sum(lambda_i) = 0`
- output contract including:
  - optimized `Lambda`
  - tightened lower bound
  - best `q`
  - low-energy eigenspace basis vectors

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py -q
```

Expected:
- missing generalized LT module or functions

- [ ] **Step 3: Implement the minimal generalized LT solver**

Implement:
- diagonal `Lambda` parameterization
- gauge reduction
- derivative-free outer optimization
- integration with the existing LT eigensolver core

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py -q
```

Expected:
- all tests pass

---

### Task 5: Pipeline Integration

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_report.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_plots.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_pipeline_integration.py`

- [ ] **Step 1: Write the failing integration tests**

Cover at least:
- classical solver choice gate includes LT and generalized LT options
- report rendering shows LT diagnostics
- plotting layer can visualize LT diagnostics without altering the classical solver behavior

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_pipeline_integration.py -q
```

Expected:
- missing LT/gLT integration fields in decisions and reports

- [ ] **Step 3: Implement the minimal integration**

Implement:
- gate options for LT / generalized LT
- report sections for:
  - minimizing `q`
  - LT lower bound
  - strong-constraint residual
  - generalized-LT `Lambda`
- optional diagnostic plot payload fields only after the solver payload is stable

- [ ] **Step 4: Run the integration tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_pipeline_integration.py -q
```

Expected:
- all tests pass

---

### Task 6: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run the LT-focused tests**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_fourier_exchange.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_solver.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_constraint_recovery.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generalized_lt_solver.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_lt_pipeline_integration.py \
  -q
```

Expected:
- all LT-related tests pass

- [ ] **Step 2: Run the broader skill test suite**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -q
```

Expected:
- no regressions in existing simplification, plotting, or LSWT behavior

- [ ] **Step 3: Record remaining limitations**

Document any still-open limitations such as:
- multi-`q` states not yet reconstructed exactly
- generalized LT still used as lower-bound/candidate generator in difficult cases
- full 3D space-group k-path standardization still orthogonal to LT implementation

---

Plan complete and saved to `/data/work/zhli/docs/superpowers/plans/2026-04-07-multisublattice-lt-and-generalized-lt-implementation.md`. Ready to execute. 
