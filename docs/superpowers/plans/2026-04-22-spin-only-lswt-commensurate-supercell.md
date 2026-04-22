# Spin-Only LSWT Commensurate Supercell Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the spin-only Sunny LSWT path to realize commensurate single-q magnetic supercells from the classical ordering contract, starting with the collinear sign-flip case needed by FeI2.

**Architecture:** Extend the LSWT payload builder to resolve/infer magnetic supercell metadata and expand base reference frames into explicit supercell reference frames. Then update the Julia LSWT launcher to build the Sunny system on that supercell and set dipoles cell-by-cell. Keep Phase 1 intentionally narrow: only commensurate single-q, single-site, collinear `0/π` phase patterns.

**Tech Stack:** Python payload builders and tests, Julia Sunny launcher, unittest/pytest, repo-local Julia wrapper baseline.

---

### Task 1: Lock payload-builder behavior with failing tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py`

- [ ] **Step 1: Write a failing test for inferred `[1, 1, 2]` FeI2-style supercell**

- [ ] **Step 2: Write a failing test for explicit `supercell_shape` precedence**

- [ ] **Step 3: Write a failing test for rejecting non-`0/π` commensurate phase patterns**

- [ ] **Step 4: Run only the new `test_build_lswt_payload.py` cases and confirm they fail for the intended missing behavior**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py -q`

Expected: new tests fail because payloads still contain only single-cell `reference_frames` and no explicit `supercell_reference_frames`.

### Task 2: Implement magnetic-supercell payload construction

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_lswt_payload.py`
- Reuse: `translation-invariant-spin-model-simplifier/scripts/classical/cpn_glt_reconstruction.py`
- Reuse: `translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py`

- [ ] **Step 1: Add helper logic to resolve/infer `supercell_shape` from classical contract and commensurate `q_vector`**

- [ ] **Step 2: Add helper logic to expand `site_frames` into `supercell_reference_frames`**

- [ ] **Step 3: Reject unsupported commensurate-but-noncollinear phase patterns with a structured LSWT payload error**

- [ ] **Step 4: Keep existing payload fields intact while adding explicit `supercell_shape` and `supercell_reference_frames`**

- [ ] **Step 5: Re-run `test_build_lswt_payload.py` and confirm the new tests pass**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py -q`

Expected: payload-builder tests pass with the new supercell metadata.

### Task 3: Lock runner integration with a failing test

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`

- [ ] **Step 1: Write a failing test that confirms the LSWT driver writes `supercell_shape` and `supercell_reference_frames` into the launcher payload**

- [ ] **Step 2: Run `test_run_linear_spin_wave_driver.py` and confirm the new expectation fails first**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py -q`

Expected: new test fails because current fixture or launcher-facing assertions do not yet cover the new payload fields.

### Task 4: Implement Sunny magnetic-supercell construction

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`

- [ ] **Step 1: Read `payload.supercell_shape` with fallback to `(1, 1, 1)`**

- [ ] **Step 2: Build `Sunny.System(...; dims=supercell_shape)`**

- [ ] **Step 3: Apply dipoles from `supercell_reference_frames` when present, otherwise preserve the old single-cell fallback**

- [ ] **Step 4: Re-run the focused Python driver tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py -q`

Expected: all focused LSWT payload/driver tests pass.

### Task 5: Verify the real FeI2 downstream rerun

**Files:**
- Read/Write: `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/fei2_v2b_lswt_rerun_<timestamp>/`

- [ ] **Step 1: Re-run the saved FeI2 `classical/solver_result.json` through `execute_downstream_stage(..., "lswt")` with `DESIGN_MOTT_JULIA_CMD` set to the repo wrapper**

- [ ] **Step 2: Save the route/result artifacts under a fresh rerun directory**

- [ ] **Step 3: Inspect whether the old `Not an energy-minimum` error is gone or replaced by a new blocker**

- [ ] **Step 4: Record the outcome in session-memory**

Run: same Python rerun harness used in-session for `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/fei2_v2b_smoke_phase1_v09_20260421-194456/classical/solver_result.json`

Expected: either a successful LSWT result or a new backend/model issue that is later in the pipeline than the current single-cell reference-state mismatch.

### Task 6: Final verification and checkpoint

**Files:**
- Modify if needed: `session-memory/sessions/design-mott-materials-2026-04-21-0342.md`
- Modify if needed: `session-memory/index/design-mott-materials.md`

- [ ] **Step 1: Run the focused LSWT regression slice**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py -q`

Expected: PASS

- [ ] **Step 2: Run any additional targeted test required by touched files**

- [ ] **Step 3: Update session-memory with spec, implementation, and real-rerun outcome**

- [ ] **Step 4: Commit the Phase 1 implementation**

```bash
git add docs/superpowers/specs/2026-04-22-spin-only-lswt-commensurate-supercell-design.md \
        docs/superpowers/plans/2026-04-22-spin-only-lswt-commensurate-supercell.md \
        translation-invariant-spin-model-simplifier/scripts/lswt/build_lswt_payload.py \
        translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl \
        translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py \
        translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py
git commit -m "feat: add commensurate supercell support for spin-only lswt"
```
