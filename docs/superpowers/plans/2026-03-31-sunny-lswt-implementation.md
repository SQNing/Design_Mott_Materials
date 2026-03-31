# Sunny-Backed LSWT Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current toy linear-spin-wave helper with a Sunny-backed LSWT pipeline for explicit bilinear spin models that starts from the classical reference state produced by the skill workflow.

**Architecture:** Keep the existing skill workflow shape, but formalize the classical solver output, add a backend-neutral LSWT payload builder in Python, and call a Julia `Sunny.jl` runner from the Python LSWT driver. Treat unsupported models and missing Sunny environments as structured stop conditions rather than silently falling back to a misleading scalar-exchange approximation.

**Tech Stack:** Python 3, `numpy`, `scipy`, Julia, `Sunny.jl`, `unittest`

---

## Chunk 1: Formalize Classical Output For Downstream LSWT

### Task 1: Capture the new classical output contract in tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Reference: `docs/superpowers/specs/2026-03-31-sunny-lswt-design.md`

- [ ] **Step 1: Read the existing classical solver tests and current output shape**

Run: `sed -n '1,240p' /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
Expected: current tests focus on energy and simple solver behavior, not a stable LSWT-ready payload

- [ ] **Step 2: Write a failing test for the new `classical_state` structure**

Add assertions that the solver output includes:
- `classical_state.site_frames`
- `classical_state.provenance.method`
- `classical_state.provenance.converged`
- `classical_state.ordering`

- [ ] **Step 3: Run the targeted test and verify it fails**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_classical_solver_driver -v`
Expected: FAIL because the current solver does not emit `classical_state`

- [ ] **Step 4: Commit the failing-test checkpoint**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: define LSWT-ready classical output contract"
```

### Task 2: Update the classical solver to emit a structured reference state

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`

- [ ] **Step 1: Add a helper that converts solver spins into `site_frames` records**

Implement a focused helper that turns the best classical solution into records like:

```python
{
    "site": index,
    "spin_length": 1.0,
    "direction": [sx, sy, sz],
}
```

- [ ] **Step 2: Add provenance and ordering placeholders**

Emit:
- `provenance.method`
- `provenance.converged`
- `ordering.kind`
- `ordering.q_vector`

Use explicit placeholder values such as commensurate `q_vector=[0.0, 0.0, 0.0]` when the current solver cannot infer a richer value yet, and keep that limitation explicit in code comments and output naming.

- [ ] **Step 3: Preserve the existing numerical outputs while adding the new structure**

Do not remove `variational_result` yet if downstream tests or current scripts still consume it. Add the new `classical_state` without breaking current call sites.

- [ ] **Step 4: Re-run the targeted classical solver tests**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_classical_solver_driver -v`
Expected: PASS

- [ ] **Step 5: Commit the classical output upgrade**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: emit structured classical reference states"
```

## Chunk 2: Build A Backend-Neutral LSWT Payload In Python

### Task 3: Add failing tests for LSWT payload construction and scope validation

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py`
- Reference: `docs/superpowers/specs/2026-03-31-sunny-lswt-design.md`

- [ ] **Step 1: Create a test file for LSWT payload building**

Cover:
- a supported bilinear Heisenberg or XXZ case
- an anisotropic `XYZ` case represented as a full `3x3` bond matrix
- an unsupported higher-body or non-spin case

- [ ] **Step 2: Write a failing test for explicit `3x3` exchange-matrix normalization**

Assert that the payload builder outputs bond records with explicit `exchange_matrix` entries and preserves site metadata from the classical state.

- [ ] **Step 3: Write a failing test for structured unsupported-scope errors**

Assert that unsupported inputs raise or return a code such as `unsupported-model-scope`.

- [ ] **Step 4: Run the new payload-builder tests and verify they fail**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_build_lswt_payload -v`
Expected: FAIL because the module does not exist yet

- [ ] **Step 5: Commit the failing tests**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: define LSWT payload builder behavior"
```

### Task 4: Implement `build_lswt_payload.py`

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/build_lswt_payload.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py`

- [ ] **Step 1: Create model-scope validation helpers**

Implement focused helpers such as:
- `validate_lswt_scope(model)`
- `normalize_exchange_matrix(term)`
- `build_reference_frames(classical_state)`

- [ ] **Step 2: Normalize supported bilinear terms into one payload schema**

Build a single payload contract containing:
- lattice metadata
- sublattice metadata
- bond list with `3x3` matrices
- onsite anisotropy list
- field list
- spin magnitudes
- classical reference directions
- requested `q_path` or `q_grid`

- [ ] **Step 3: Return structured error payloads for unsupported cases**

Do not throw generic uncaught exceptions for model-scope failures. Use machine-readable codes and short messages that the report layer can surface.

- [ ] **Step 4: Re-run the payload-builder tests**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_build_lswt_payload -v`
Expected: PASS

- [ ] **Step 5: Commit the payload builder**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/build_lswt_payload.py translation-invariant-spin-model-simplifier/tests/test_build_lswt_payload.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: add backend-neutral LSWT payload builder"
```

## Chunk 3: Add A Sunny Julia Runner And Python Driver Orchestration

### Task 5: Define the Python-driver behavior with failing tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py`
- Reference: `translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py`

- [ ] **Step 1: Replace the toy-dispersion expectations with orchestration expectations**

Write tests for:
- missing Julia runtime
- missing Sunny package
- successful parsing of backend JSON
- out-of-scope model short-circuit

- [ ] **Step 2: Add a failing test that mocks a successful backend call**

Assert that the driver returns:
- `backend.name == "Sunny.jl"`
- `status == "ok"`
- a `linear_spin_wave.dispersion` field copied from backend output

- [ ] **Step 3: Run the LSWT driver tests and verify they fail**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_linear_spin_wave_driver -v`
Expected: FAIL because the current driver is still the toy implementation

- [ ] **Step 4: Commit the driver-contract tests**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: define Sunny-backed LSWT driver behavior"
```

### Task 6: Add the Julia runner script

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/run_sunny_lswt.jl`
- Create: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_lswt_contract.py`

- [ ] **Step 1: Create a tiny Python-side contract test for the runner input and output schema**

The test should check file-level contract assumptions only, for example that a canned JSON input can be handed to the runner and the returned JSON contains:
- `status`
- `backend`
- `linear_spin_wave`

- [ ] **Step 2: Implement `run_sunny_lswt.jl`**

The first version should:
- parse JSON input
- build the Sunny model from lattice plus bond data
- apply the provided classical reference state
- run LSWT on the requested momentum path
- print JSON to stdout

- [ ] **Step 3: Keep Julia errors structured**

Map common failures into readable JSON responses instead of raw stack traces when practical:
- missing `Sunny`
- malformed payload
- backend execution failure

- [ ] **Step 4: Run the contract test**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_run_sunny_lswt_contract -v`
Expected: PASS for file-level contract checks that do not require Sunny

- [ ] **Step 5: Commit the Julia runner scaffold**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/run_sunny_lswt.jl translation-invariant-spin-model-simplifier/tests/test_run_sunny_lswt_contract.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: add Sunny LSWT Julia runner scaffold"
```

### Task 7: Refactor the Python LSWT driver into an orchestrator

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py`

- [ ] **Step 1: Add environment-detection helpers**

Implement small helpers such as:
- `detect_julia()`
- `check_sunny_available()`
- `run_backend(payload)`

- [ ] **Step 2: Integrate `build_lswt_payload.py`**

The driver should:
- validate the model scope
- short-circuit unsupported inputs
- invoke Julia only when the payload is valid

- [ ] **Step 3: Parse backend JSON into a stable response**

Return a response object that includes:
- `status`
- `backend`
- `linear_spin_wave`
- optional `error`
- optional `exact_diagonalization`

- [ ] **Step 4: Remove the misleading toy fallback from the default path**

Delete or isolate the current scalar-exchange helper so it is no longer the code path used for production LSWT requests.

- [ ] **Step 5: Re-run the LSWT driver tests**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_linear_spin_wave_driver -v`
Expected: PASS

- [ ] **Step 6: Commit the LSWT driver refactor**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: orchestrate Sunny-backed LSWT from Python"
```

## Chunk 4: Report Successful Runs And Structured Stop Conditions

### Task 8: Add failing report tests for Sunny-backed output and blocked runs

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_render_report.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/render_report.py`

- [ ] **Step 1: Add a failing test for successful Sunny-backed LSWT reporting**

Assert the rendered text includes:
- `Sunny.jl`
- classical reference-state method
- LSWT success indication

- [ ] **Step 2: Add a failing test for partial-stop reporting**

Assert the rendered text includes:
- classical result still valid
- LSWT stop reason
- recommended next action

- [ ] **Step 3: Run the report tests and verify they fail**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_render_report -v`
Expected: FAIL because the current report format is too narrow

- [ ] **Step 4: Commit the report tests**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/tests/test_render_report.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: expand report coverage for Sunny-backed LSWT"
```

### Task 9: Implement the report changes

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/render_report.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_render_report.py`

- [ ] **Step 1: Extend the report renderer to handle structured backend metadata**

Display:
- backend name
- LSWT run status
- classical method and reference-state note
- dispersion summary when available
- structured stop reasons when LSWT did not run

- [ ] **Step 2: Preserve concise output for successful small examples**

Do not turn the text report into an unreadable dump. Summarize the essentials and list omitted features explicitly.

- [ ] **Step 3: Re-run the report tests**

Run: `python3 -m unittest translation-invariant-spin-model-simplifier.tests.test_render_report -v`
Expected: PASS

- [ ] **Step 4: Commit the report update**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/render_report.py translation-invariant-spin-model-simplifier/tests/test_render_report.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: report Sunny-backed LSWT outcomes clearly"
```

## Chunk 5: End-To-End Verification And Documentation Updates

### Task 10: Update skill-facing docs to match the new true scope

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/SKILL.md`
- Modify: `translation-invariant-spin-model-simplifier/references/supported-models.md`
- Modify: `translation-invariant-spin-model-simplifier/references/lsw-assumptions.md`
- Modify: `translation-invariant-spin-model-simplifier/WORKLOG.md`
- Modify: `translation-invariant-spin-model-simplifier/REVIEW.md`

- [ ] **Step 1: Update `SKILL.md` to state the first-stage LSWT scope explicitly**

Make it clear that the formal backend is `Sunny.jl` and that unsupported models or missing environments cause a clear stop after the classical stage.

- [ ] **Step 2: Update the support and assumptions references**

Align the docs with the actual new boundary:
- explicit bilinear spin scope
- classical-reference-state requirement
- no silent scalar-exchange fallback

- [ ] **Step 3: Record the implementation and verification status**

Append concise entries to `WORKLOG.md` and `REVIEW.md` that capture the new architecture and any remaining limitations.

- [ ] **Step 4: Commit the documentation update**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/SKILL.md translation-invariant-spin-model-simplifier/references/supported-models.md translation-invariant-spin-model-simplifier/references/lsw-assumptions.md translation-invariant-spin-model-simplifier/WORKLOG.md translation-invariant-spin-model-simplifier/REVIEW.md
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "docs: align skill docs with Sunny-backed LSWT scope"
```

### Task 11: Run full verification

**Files:**
- Test: `translation-invariant-spin-model-simplifier/tests/*.py`

- [ ] **Step 1: Run the full Python test suite**

Run: `python3 -m unittest discover -s /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -v`
Expected: PASS

- [ ] **Step 2: Run a backend-availability smoke check**

Run: `julia --project=/Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier -e 'using Sunny; println("Sunny OK")'`
Expected: prints `Sunny OK` if the environment is configured; otherwise capture the exact failure and ensure the Python driver reports it clearly

- [ ] **Step 3: Run one end-to-end LSWT smoke example**

Use a tiny explicit bilinear spin model with a known classical reference state and verify that:
- the payload builder succeeds
- the Python driver invokes Julia
- the report includes `Sunny.jl`

- [ ] **Step 4: Commit the verification checkpoint**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add .
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: verify Sunny-backed LSWT integration"
```
