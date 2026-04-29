# CP(N-1) Magnetic Supercell Reshape And GLSWT Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-native magnetic-supercell reshape workflow for general multi-site periodic `CP^(N-1)` models so a dominant nonuniform ordering component can trigger model reshape, classical re-optimization, and seamless downstream Python/Sunny GLSWT.

**Architecture:** Introduce one shared reshape core that rewrites periodic `CP^(N-1)` models and explicit local-ray states into a magnetic-cell basis, then let existing classical and GLSWT code consume the reshaped result as an ordinary periodic model/state. Keep candidate selection, model reshape, state lifting, and branch acceptance separate so energy invariance and solver behavior can be tested in layers.

**Tech Stack:** Python, NumPy, existing `CP^(N-1)` classical/GLSWT builders, existing Sunny backend adapters, `python -m pytest`

**Spec Reference:** `docs/superpowers/specs/2026-04-29-cpn-magnetic-supercell-reshape-and-glswt-design.md`

---

## File Map

### New files to create

- `translation-invariant-spin-model-simplifier/scripts/common/cpn_magnetic_supercell.py`
  - Shared integer-cell, coset, model-reshape, and state-lift utilities.

- `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py`
  - Geometry, indexing, bond rewrite, and energy-invariance tests for the reshape core.

- `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py`
  - Workflow-level tests for candidate selection, reshaped classical re-optimization, branch acceptance, and GLSWT payload continuity.

### Existing files to modify

- `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py`
  - Allow Python classical minimization/energy evaluation on reshaped periodic models and add refinement helpers.

- `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
  - Add orchestration for the optional magnetic-supercell refinement branch.

- `translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
  - Confirm reshaped models/states are exported with the correct q-path and state semantics.

- `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
  - Confirm reshaped models/states are exported cleanly to the Sunny path.

- `translation-invariant-spin-model-simplifier/tmp/fei2-canonical-cpn-validation-2026-04-27/run_fei2_canonical_cpn_noreshape_compare.py`
  - Extend the FeI2 validation harness to exercise the refinement branch explicitly.

### Existing files to reuse without initial modification

- `translation-invariant-spin-model-simplifier/scripts/common/cpn_classical_state.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/build_sun_gswt_classical_payload.py`
- `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_payload.json`

---

## Task 1: Lock Candidate Construction And Integer-Cell Geometry In Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py`

- [ ] **Step 1: Write a failing test for candidate construction from a dominant nonzero projector q**

Add a test that feeds a projector summary with a largest nonzero `q = [1/4, 0, 1/4]` into the new candidate helper and requires a valid integer matrix candidate with finite determinant.

```python
def test_candidate_from_projector_returns_integer_matrix_for_commensurate_q():
    projector = {
        "top_components": [
            {"q": [0.25, 0.0, 0.25], "weight": 0.14},
            {"q": [0.0, 0.0, 0.0], "weight": 0.49},
        ]
    }

    candidate = magnetic_supercell_candidate_from_projector(projector)

    assert candidate["status"] == "ok"
    assert candidate["selected_q"] == [0.25, 0.0, 0.25]
    assert candidate["matrix"]
    assert candidate["determinant"] >= 1
```

- [ ] **Step 2: Write a failing test for coset enumeration count**

Require the reshape core to enumerate exactly `abs(det(M))` representatives for a nontrivial matrix.

```python
def test_enumerate_coset_representatives_matches_absolute_determinant():
    matrix = [[1, 0, 0], [0, 1, -2], [0, 1, 2]]

    reps = enumerate_magnetic_cell_cosets(matrix)

    assert len(reps) == 4
```

- [ ] **Step 3: Write a failing test for reshaped site-count scaling on a multi-site toy model**

Use a two-site toy model and require the reshaped model to contain `abs(det(M)) * n_site` positions.

```python
def test_reshape_model_multiplies_site_count_by_cell_volume():
    model = _toy_two_site_cpn_model()
    matrix = [[2, 0, 0], [0, 1, 0], [0, 0, 1]]

    reshaped = reshape_cpn_model_to_magnetic_supercell(model, matrix)

    assert len(reshaped["positions"]) == 4
```

- [ ] **Step 4: Run the new geometry tests and verify they fail**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
```

Expected: FAIL because the candidate helper and reshape core do not exist yet.

- [ ] **Step 5: Commit the RED geometry slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
git commit -m "test: add magnetic supercell geometry red tests"
```

---

## Task 2: Implement Integer-Cell Candidate And Coset Utilities

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/common/cpn_magnetic_supercell.py`

- [ ] **Step 1: Implement `magnetic_supercell_candidate_from_projector(...)` minimally**

Add a helper that:
- extracts the largest nonzero q from `projector_summary["top_components"]`,
- rationalizes each component with a bounded denominator,
- returns a first valid integer candidate matrix plus diagnostics.

- [ ] **Step 2: Implement determinant and integer-matrix validation helpers**

Add helpers for:
- integer coercion,
- non-singularity checks,
- determinant computation,
- simple commensurability diagnostics.

- [ ] **Step 3: Implement `enumerate_magnetic_cell_cosets(...)` minimally**

Return a deterministic list of chemical-cell representatives inside the magnetic cell using a bounded search and uniqueness check modulo the integer matrix lattice.

- [ ] **Step 4: Run the geometry tests and verify they pass**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
```

Expected: PASS for the candidate/coset/site-count tests added so far.

- [ ] **Step 5: Commit the candidate/coset implementation**

```bash
git add \
  translation-invariant-spin-model-simplifier/scripts/common/cpn_magnetic_supercell.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
git commit -m "feat: add CP(N-1) magnetic supercell candidate core"
```

---

## Task 3: Lock Bond Rewrite And Energy Invariance In Tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py`

- [ ] **Step 1: Write a failing test for reshaped bond rewrite energy invariance**

Build a small periodic multi-site toy model and explicit local-ray state, then require original and reshaped model energies to match after lifting the state.

```python
def test_reshaped_model_preserves_classical_energy_for_equivalent_state():
    model = _toy_two_site_cpn_model()
    state = _toy_two_site_periodic_state()
    matrix = [[2, 0, 0], [0, 1, 0], [0, 0, 1]]

    reshaped_model = reshape_cpn_model_to_magnetic_supercell(model, matrix)
    reshaped_state = lift_cpn_state_between_cells(state, reshaped_model["magnetic_supercell_mapping"], direction="chemical_to_magnetic")

    e0 = evaluate_sun_gswt_classical_energy(model, state)
    e1 = evaluate_sun_gswt_classical_energy(reshaped_model, reshaped_state)

    assert abs(e0 - e1) <= 1e-10
```

- [ ] **Step 2: Write a failing test for bond-count diagnostics**

Require the reshaped model to emit deterministic mapping diagnostics including reshaped site count, representative count, and bond count.

```python
def test_reshape_model_reports_mapping_diagnostics():
    reshaped = reshape_cpn_model_to_magnetic_supercell(_toy_two_site_cpn_model(), [[2, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert reshaped["magnetic_supercell_mapping"]["representative_count"] == 2
    assert reshaped["magnetic_supercell_mapping"]["reshaped_site_count"] == 4
```

- [ ] **Step 3: Run the tests and verify they fail**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
```

Expected: FAIL because model reshape and state lifting are still incomplete.

- [ ] **Step 4: Commit the RED energy-invariance slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
git commit -m "test: add magnetic supercell energy invariance red tests"
```

---

## Task 4: Implement Model Reshape And State Lifting

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/common/cpn_magnetic_supercell.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py`

- [ ] **Step 1: Implement `reshape_cpn_model_to_magnetic_supercell(...)`**

Add logic to:
- build reshaped lattice vectors,
- enumerate `(alpha, site)` site identities,
- rewrite positions,
- duplicate onsite terms,
- rewrite `(source, target, R)` bonds into the magnetic-cell basis,
- attach a stable `magnetic_supercell_mapping` payload.

- [ ] **Step 2: Implement `lift_cpn_state_between_cells(...)`**

Support at least:
- `chemical_to_magnetic`
- `magnetic_to_chemical`

using explicit local-ray transport keyed by the reshape mapping.

- [ ] **Step 3: Remove the blanket magnetic-supercell rejection from Python classical energy for fully reshaped models**

Keep rejecting metadata-only states that still rely on hidden magnetic-supercell semantics, but allow models/states that are already rewritten into ordinary periodic form.

- [ ] **Step 4: Run the geometry and invariance tests and verify they pass**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
```

Expected: PASS including the energy-invariance checks.

- [ ] **Step 5: Commit the reshape core**

```bash
git add \
  translation-invariant-spin-model-simplifier/scripts/common/cpn_magnetic_supercell.py \
  translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py
git commit -m "feat: add CP(N-1) magnetic supercell reshape core"
```

---

## Task 5: Lock Classical Refinement Branch Behavior In Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py`

- [ ] **Step 1: Write a failing test for candidate-branch proposal from projector diagnostics**

Require a classical result with a dominant nonzero q to produce a refinement candidate object instead of silently doing nothing.

```python
def test_refinement_branch_proposes_candidate_from_largest_nonzero_q():
    classical_result = _toy_classical_result_with_projector_q([0.25, 0.0, 0.25])

    branch = build_cpn_magnetic_supercell_refinement_candidate(model=_toy_two_site_cpn_model(), classical_result=classical_result)

    assert branch["status"] == "candidate"
    assert branch["candidate"]["selected_q"] == [0.25, 0.0, 0.25]
```

- [ ] **Step 2: Write a failing test for branch rejection when energy gain is too small**

```python
def test_refinement_branch_rejects_when_energy_gain_is_below_tolerance():
    decision = choose_refined_classical_branch(
        original_energy=-1.0000000,
        refined_python_energy=-1.0000000001,
        refined_sunny_energy=None,
        energy_gain_tolerance=1e-6,
    )

    assert decision["accepted"] is False
```

- [ ] **Step 3: Write a failing test for accepted branch carrying a GLSWT-ready selected state**

```python
def test_refinement_branch_accepts_lower_energy_state_and_returns_selected_state():
    decision = choose_refined_classical_branch(
        original_energy=-1.0,
        refined_python_energy=-1.1,
        refined_state={"supercell_shape": [2, 1, 1], "local_rays": []},
        energy_gain_tolerance=1e-6,
    )

    assert decision["accepted"] is True
    assert decision["selected_classical_state"]["supercell_shape"] == [2, 1, 1]
```

- [ ] **Step 4: Run the refinement tests and verify they fail**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
```

Expected: FAIL because refinement orchestration helpers do not exist yet.

- [ ] **Step 5: Commit the RED refinement slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
git commit -m "test: add magnetic supercell refinement red tests"
```

---

## Task 6: Implement Classical Refinement Orchestration

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`

- [ ] **Step 1: Implement small orchestration helpers in the classical layer**

Suggested helpers:
- `build_cpn_magnetic_supercell_refinement_candidate(...)`
- `run_cpn_magnetic_supercell_refinement(...)`
- `choose_refined_classical_branch(...)`

Keep them solver-agnostic where possible.

- [ ] **Step 2: Add a pipeline hook after the initial explicit classical state is found**

In `solve_pseudospin_orbital_pipeline.py`, insert the refinement step:
- inspect projector diagnostics,
- propose candidate,
- reshape model,
- lift initial state,
- rerun classical minimization on the reshaped model,
- decide whether to accept the branch.

- [ ] **Step 3: Record explicit refinement diagnostics in the returned payload**

Add a stable result section such as:

```python
"magnetic_supercell_refinement": {
    "trigger_q": ...,
    "candidate_matrix": ...,
    "accepted": ...,
    "energy_before": ...,
    "energy_after_python": ...,
    "energy_after_sunny": ...,
    "selected_backend": ...,
}
```

- [ ] **Step 4: Run the refinement tests and verify they pass**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
```

Expected: PASS for branch proposal, rejection, and acceptance behavior.

- [ ] **Step 5: Commit the refinement orchestration**

```bash
git add \
  translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py \
  translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
git commit -m "feat: add CP(N-1) magnetic supercell refinement branch"
```

---

## Task 7: Lock GLSWT Continuity Through The Refined Branch In Tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`

- [ ] **Step 1: Write a failing test that an accepted reshaped branch builds a Python GLSWT payload**

```python
def test_refined_reshaped_state_builds_python_glswt_payload():
    model, classical_state = _accepted_refined_branch_fixture()
    payload = build_python_glswt_payload(model, classical_state=classical_state)
    assert payload["initial_local_rays"]
    assert payload["supercell_shape"] == classical_state["supercell_shape"]
```

- [ ] **Step 2: Write a failing test that an accepted reshaped branch builds a Sunny GLSWT payload**

```python
def test_refined_reshaped_state_builds_sunny_glswt_payload():
    model, classical_state = _accepted_refined_branch_fixture()
    payload = build_sun_gswt_payload(model, classical_state=classical_state)
    assert payload["initial_local_rays"]
    assert payload["supercell_shape"] == classical_state["supercell_shape"]
```

- [ ] **Step 3: Write a failing FeI2 regression-style harness test**

Extend or add a small harness test around
`tmp/fei2-canonical-cpn-validation-2026-04-27/run_fei2_canonical_cpn_noreshape_compare.py`
so the script can report refinement diagnostics and, when accepted, produce a GLSWT-ready selected state.

- [ ] **Step 4: Run the GLSWT continuity tests and verify they fail**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
```

Expected: FAIL because the GLSWT payload builders do not yet treat the accepted refinement branch as a first-class downstream state.

- [ ] **Step 5: Commit the RED GLSWT continuity slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
git commit -m "test: add reshaped branch GLSWT continuity red tests"
```

---

## Task 8: Implement GLSWT Continuity And FeI2 Harness Wiring

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
- Modify: `translation-invariant-spin-model-simplifier/tmp/fei2-canonical-cpn-validation-2026-04-27/run_fei2_canonical_cpn_noreshape_compare.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py`

- [ ] **Step 1: Ensure reshaped explicit periodic states remain ordinary consumers for both payload builders**

Only add the minimum necessary metadata handling so accepted refined states flow through as normal explicit local-ray states. Do not add a second special-case payload family.

- [ ] **Step 2: Extend the FeI2 validation harness to exercise the refinement branch**

Teach the harness to:
- report the proposed candidate matrix,
- report accepted/rejected status,
- if accepted, continue from the selected reshaped state into GLSWT-ready payload generation.

- [ ] **Step 3: Run the focused refinement + GLSWT tests and verify they pass**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py \
  translation-invariant-spin-model-simplifier/tests/test_python_glswt_solver.py \
  translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py
```

Expected: PASS, confirming reshaped refined states are classical-energy consistent and GLSWT-ready.

- [ ] **Step 4: Run one real FeI2 smoke command**

Run:

```bash
python translation-invariant-spin-model-simplifier/tmp/fei2-canonical-cpn-validation-2026-04-27/run_fei2_canonical_cpn_noreshape_compare.py \
  --output /tmp/fei2_cpn_refinement_smoke.json \
  --starts 2 \
  --seed 0
```

Expected:
- script completes,
- output JSON contains `magnetic_supercell_refinement`,
- if accepted, selected state can be passed to GLSWT builders without contract errors.

- [ ] **Step 5: Commit the GLSWT continuity implementation**

```bash
git add \
  translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py \
  translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py \
  translation-invariant-spin-model-simplifier/tmp/fei2-canonical-cpn-validation-2026-04-27/run_fei2_canonical_cpn_noreshape_compare.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py
git commit -m "feat: connect reshaped CP(N-1) refinement to GLSWT"
```

---

## Task 9: Final Regression Sweep And Cleanup

**Files:**
- Modify only if needed based on failures from the full regression sweep

- [ ] **Step 1: Run the full focused regression suite**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell.py \
  translation-invariant-spin-model-simplifier/tests/test_cpn_magnetic_supercell_refinement.py \
  translation-invariant-spin-model-simplifier/tests/test_python_glswt_solver.py \
  translation-invariant-spin-model-simplifier/tests/test_build_python_glswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py
```

Expected: PASS.

- [ ] **Step 2: If a regression fails, add the smallest missing test and minimal fix**

Keep any cleanup strictly tied to reshape/refinement/GLSWT continuity.

- [ ] **Step 3: Re-run the regression suite and verify all green**

Run the same command again and confirm clean output.

- [ ] **Step 4: Commit the regression cleanup if required**

```bash
git add <only files changed for regression cleanup>
git commit -m "fix: stabilize magnetic supercell refinement regressions"
```

