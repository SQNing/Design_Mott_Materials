# Spin-Only LSWT Single-Q Rotating-Frame Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend spin-only Sunny LSWT from Phase 1 collinear commensurate supercells to general commensurate single-q rotating-frame textures using explicit per-cell phase metadata.

**Architecture:** Keep the Julia runner simple and explicit. All rotating-frame interpretation happens in the Python LSWT payload builder, which resolves `rotating_frame_realization.supercell_site_phases` plus a rotation axis into concrete `supercell_reference_frames`. The runner continues to consume only explicit cell-by-cell spin directions.

**Tech Stack:** Python LSWT payload builder, rotating-frame metadata helpers, Julia Sunny LSWT launcher, unittest/pytest.

---

### Task 1: Lock Phase 2 behavior with failing payload-builder tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py`

- [ ] **Step 1: Add a failing test for a `q = 1/4` single-q rotating-frame texture that should produce non-collinear `supercell_reference_frames`**

- [ ] **Step 2: Add a failing test for incomplete `supercell_site_phases` coverage**

- [ ] **Step 3: Add a failing test that confirms the Phase 1 sign-flip fallback still works when rotating-frame metadata is absent**

- [ ] **Step 4: Run the focused payload-builder tests and verify the new Phase 2 tests fail for the intended missing behavior**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py -q`

Expected: the new rotating-frame tests fail because the current payload builder only supports `0/π` sign-flip expansion.

### Task 2: Implement rotating-frame expansion in the LSWT payload builder

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_lswt_payload.py`
- Reuse: `translation-invariant-spin-model-simplifier/scripts/common/rotating_frame_realization.py`
- Reuse: `translation-invariant-spin-model-simplifier/scripts/common/rotating_frame_metadata.py`

- [ ] **Step 1: Add helpers to resolve rotation-axis vectors from `"x/y/z/a/b/c"` aliases**

- [ ] **Step 2: Add helpers to build a complete `(cell, site) -> phase` map from `supercell_site_phases`**

- [ ] **Step 3: Rotate each base `site_frame.direction` by the sampled phase around the resolved axis**

- [ ] **Step 4: Prefer rotating-frame realization when present, but keep the Phase 1 sign-flip fallback when it is absent**

- [ ] **Step 5: Re-run the focused payload-builder tests and verify the new Phase 2 cases pass**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py -q`

Expected: rotating-frame Phase 2 tests pass, and Phase 1 tests remain green.

### Task 3: Lock launcher integration with a focused driver test

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`

- [ ] **Step 1: Add a failing test asserting that non-collinear rotated `supercell_reference_frames` are written unchanged into the launcher payload**

- [ ] **Step 2: Run the focused driver test and verify failure before implementation if needed**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py -q`

Expected: the new expectation fails until the fixture/serialization path is updated.

### Task 4: Keep the Julia runner explicit and verify nothing else is needed

**Files:**
- Inspect/Modify if needed: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`

- [ ] **Step 1: Confirm the runner already consumes `supercell_reference_frames` generically**

- [ ] **Step 2: If any assumptions remain about collinearity, remove only the minimal ones**

- [ ] **Step 3: Re-run focused LSWT tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py -q`

Expected: PASS

### Task 5: Real downstream verification

**Files:**
- Read/Write: `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/`

- [ ] **Step 1: If a real commensurate non-collinear single-q payload is available, rerun it through `execute_downstream_stage(..., "lswt")`**

- [ ] **Step 2: Otherwise create a minimal saved synthetic payload and validate end-to-end launcher execution**

- [ ] **Step 3: Record the outcome in session-memory**

### Task 6: Final verification and checkpoint

**Files:**
- Modify if needed: `session-memory/sessions/design-mott-materials-2026-04-21-0342.md`
- Modify if needed: `session-memory/index/design-mott-materials.md`

- [ ] **Step 1: Run the focused LSWT regression slice**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py translation-invariant-spin-model-simplifier/tests/test_sunny_family_julia_command_resolution.py -q`

Expected: PASS

- [ ] **Step 2: Update session-memory with Phase 2 findings**

- [ ] **Step 3: Commit the Phase 2 implementation**

```bash
git add docs/superpowers/specs/2026-04-22-spin-only-lswt-single-q-rotating-frame-phase-2-design.md \
        docs/superpowers/plans/2026-04-22-spin-only-lswt-single-q-rotating-frame-phase-2.md \
        translation-invariant-spin-model-simplifier/scripts/lswt/build_lswt_payload.py \
        translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl \
        translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py \
        translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py
git commit -m "feat: add rotating-frame support for commensurate single-q lswt"
```
