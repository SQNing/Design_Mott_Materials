# FeI2 V2b Downstream Chaining Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the landed FeI2 `V2a` bridge so document-reader runs can resolve downstream routes and automatically execute the approved subset of `LSWT` / `GSWT` / `thermodynamics` stages with explicit route, result, summary, and provenance artifacts.

**Architecture:** Keep `V2a` payload assembly untouched and add one focused downstream-orchestration helper above the classical solver result. The document-reader pipeline should call that helper after successful classical solving, then write stable downstream artifacts and mirror them into `final_pipeline_result.json` without re-implementing shared routing or execution logic.

**Tech Stack:** Python 3, document-reader CLI pipeline, shared downstream routing/execution helpers, JSON artifact writers, `unittest`/`pytest`

---

## Scope Lock

This plan implements FeI2 `V2b` only.

In scope:

- route resolution for `lswt`, `gswt`, and `thermodynamics`
- FeI2-specific policy for deciding which downstream stages auto-execute
- explicit downstream artifact emission
- preservation of classical success when downstream stages are blocked or fail
- protocol/documentation updates describing the `V2b` contract

Out of scope:

- changing `V2a` shell-expansion or all-family assembly behavior
- redesigning shared downstream routing rules
- making `review` stages auto-execute by default
- broad model-class bridge work beyond spin-only FeI2

## File Map

**Create**

- `translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py`
- `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`
- `docs/superpowers/plans/2026-04-21-fei2-v2b-downstream-chaining.md`

**Modify**

- `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

**Read For Context**

- `docs/superpowers/specs/2026-04-21-fei2-v2b-downstream-chaining-design.md`
- `docs/superpowers/specs/2026-04-21-fei2-v2a-shell-expansion-and-all-family-design.md`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_routing.py`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_execution.py`
- `translation-invariant-spin-model-simplifier/tests/test_downstream_stage_execution.py`
- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`

### Task 1: Lock The V2b Policy With Helper-Level Red Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_downstream_stage_execution.py`
- Read: `docs/superpowers/specs/2026-04-21-fei2-v2b-downstream-chaining-design.md`

- [ ] **Step 1: Write a failing test for all-route collection**

Add a helper-level test that patches route resolution for:

```python
{
    "lswt": {"status": "ready", "enabled": True, "recommended_backend": "linear_spin_wave"},
    "gswt": {"status": "blocked", "enabled": False, "reason": "missing-gswt-payload"},
    "thermodynamics": {"status": "review", "enabled": True, "recommended_backend": "spin_only_thermodynamics"},
}
```

and asserts:

```python
result = orchestrate_document_reader_downstream(payload)

assert result["downstream_routes"]["lswt"]["status"] == "ready"
assert result["downstream_routes"]["gswt"]["status"] == "blocked"
assert result["downstream_routes"]["thermodynamics"]["status"] == "review"
```

- [ ] **Step 2: Write a failing test for the approved stage policy**

Add a test proving:

- `lswt ready` executes
- `gswt blocked` does not execute
- `thermodynamics review` is recorded but does not execute by default

Suggested assertions:

```python
assert "lswt" in result["downstream_results"]
assert "gswt" not in result["downstream_results"]
assert "thermodynamics" not in result["downstream_results"]
assert result["downstream_summary"]["thermodynamics"]["execution_decision"] == "skipped_review"
```

- [ ] **Step 3: Write a failing test for thermodynamics config gating**

Add a test where thermodynamics route is `ready` but required temperatures are missing, then assert:

```python
assert result["downstream_summary"]["thermodynamics"]["execution_decision"] == "blocked_missing_inputs"
assert result["downstream_status"] == "partial"
```

- [ ] **Step 4: Write a failing test for isolated downstream failure semantics**

Patch `execute_downstream_stage` so `lswt` raises, then assert:

```python
assert result["downstream_status"] == "error"
assert result["downstream_results"]["lswt"]["status"] == "error"
assert result["downstream_routes"]["gswt"]["status"] == "blocked"
```

The test should verify that route evidence remains present even when one execution fails.

- [ ] **Step 5: Run the new helper test file and verify it fails**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py -v
```

Expected: FAIL because the helper module and policy behavior do not exist yet.

- [ ] **Step 6: Commit the helper red-test baseline**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py
git commit -m "test: define FeI2 V2b downstream policy contract"
```

### Task 2: Implement The Downstream Orchestration Helper

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_routing.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_execution.py`

- [ ] **Step 1: Add a helper that resolves all stage routes**

Implement a function like:

```python
def orchestrate_document_reader_downstream(payload, *, allow_review_execution=False):
    ...
```

It should always collect route data for:

- `lswt`
- `gswt`
- `thermodynamics`

using the shared routing helper.

- [ ] **Step 2: Add FeI2 V2b execution-policy helpers**

Add focused policy helpers such as:

```python
def _should_execute_lswt(route):
    ...

def _should_execute_gswt(route, payload):
    ...

def _should_execute_thermodynamics(route, payload, allow_review_execution):
    ...
```

Implement the approved policy:

- `lswt`: execute only when `ready`
- `gswt`: execute only when `ready` and an explicit `gswt_payload` exists
- `thermodynamics`: execute only when `ready` and required inputs exist; keep `review` as recorded-only unless explicitly enabled

- [ ] **Step 3: Add downstream summary and status rollup**

Return a structure with:

```python
{
    "downstream_status": "...",
    "downstream_routes": {...},
    "downstream_results": {...},
    "downstream_summary": {...},
}
```

The summary should record per-stage:

- route status
- execution decision
- selected backend when executed
- failure reason when skipped or blocked

- [ ] **Step 4: Preserve isolated stage failures**

Wrap each execution attempt so one stage failure records:

```python
{
    "status": "error",
    "message": str(exc),
}
```

without deleting previously collected route data or successful stage results.

- [ ] **Step 5: Run the helper test file to green**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py -v
```

Expected: PASS for route collection, policy gating, config gating, and isolated failure behavior.

- [ ] **Step 6: Commit the helper implementation slice**

```bash
git add translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py
git add translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py
git commit -m "feat: add FeI2 V2b downstream orchestration helper"
```

### Task 3: Lock Pipeline-Level V2b Behavior With Red Tests

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`

- [ ] **Step 1: Add a failing pipeline test for downstream artifact emission**

Patch the bridge, classical solver, and new orchestration helper so the pipeline returns:

```python
{
    "downstream_status": "partial",
    "downstream_routes": {...},
    "downstream_results": {"lswt": {"status": "ok"}},
    "downstream_summary": {...},
}
```

Then assert:

```python
assert result["downstream_status"] == "partial"
assert (output_dir / "classical" / "downstream_routes.json").exists()
assert (output_dir / "classical" / "downstream_results.json").exists()
assert (output_dir / "classical" / "downstream_summary.json").exists()
```

- [ ] **Step 2: Add a failing pipeline test for classical-success preservation**

Patch the orchestration helper to return an error result for `lswt`, then assert:

```python
assert result["classical_solver"]["classical_state_result"]["status"] == "ok"
assert result["downstream_results"]["lswt"]["status"] == "error"
```

- [ ] **Step 3: Add a failing pipeline test for route-only downstream cases**

Patch the helper so no stages execute but all routes are present, then assert:

```python
assert result["downstream_routes"]["gswt"]["status"] == "blocked"
assert result["downstream_routes"]["thermodynamics"]["status"] == "review"
assert result["downstream_results"] == {}
```

- [ ] **Step 4: Run the pipeline V2b tests and verify they fail**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py -k downstream -v
```

Expected: FAIL because the pipeline has not yet been updated to integrate the downstream helper or write the new artifacts.

- [ ] **Step 5: Commit the pipeline red-test slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py
git commit -m "test: define FeI2 V2b pipeline artifact contract"
```

### Task 4: Integrate V2b Into The Document-Reader Pipeline

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py`

- [ ] **Step 1: Add downstream artifact writers**

Add a small writer helper like:

```python
def _write_downstream_artifacts(output_dir, downstream_result):
    ...
```

It should write:

- `downstream_routes.json`
- `downstream_results.json`
- `downstream_summary.json`

- [ ] **Step 2: Add explicit V2b pipeline flags**

Extend `run_document_reader_pipeline(...)` with explicit parameters such as:

```python
run_downstream_stages=False,
allow_review_downstream=False,
```

and thread them through the CLI argument parser.

- [ ] **Step 3: Call the new orchestration helper after successful classical solving**

Only invoke downstream orchestration when:

- bridge succeeded
- classical solver was requested and returned a result
- `run_downstream_stages` is enabled

Then mirror:

- `downstream_status`
- `downstream_routes`
- `downstream_results`
- `downstream_summary`

into the returned pipeline result.

- [ ] **Step 4: Keep the pipeline file orchestration-only**

Do not add stage-specific `if stage == ...` policy logic inside
`run_document_reader_pipeline.py`; leave that behavior in the helper module.

- [ ] **Step 5: Run the downstream pipeline tests to green**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py -k downstream -v
```

Expected: PASS for downstream artifact writing, classical-success preservation, and route-only outcomes.

- [ ] **Step 6: Commit the pipeline integration slice**

```bash
git add translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py
git add translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py
git commit -m "feat: add FeI2 V2b downstream pipeline orchestration"
```

### Task 5: Update The Protocol Documentation

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`
- Read: `docs/superpowers/specs/2026-04-21-fei2-v2b-downstream-chaining-design.md`

- [ ] **Step 1: Add a V2b section after the current V2a bridge notes**

Document that `V2b`:

- consumes the `V2a` bridge payload
- resolves downstream routes for `lswt`, `gswt`, and `thermodynamics`
- auto-runs `lswt` when `ready`
- keeps `gswt` conservative unless an explicit payload exists
- does not auto-run `review` stages by default

- [ ] **Step 2: Document the new downstream artifacts**

Describe:

- `classical/downstream_routes.json`
- `classical/downstream_results.json`
- `classical/downstream_summary.json`

and explain the difference between route evidence and execution results.

- [ ] **Step 3: Run the narrow protocol-adjacent regression slice**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py -k downstream -v
```

Expected: PASS, confirming the documented interface is aligned with the implemented pipeline behavior.

- [ ] **Step 4: Commit the documentation slice**

```bash
git add translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md
git commit -m "docs: describe FeI2 V2b downstream chaining"
```

### Task 6: Run Focused Regression And Real FeI2 Smoke

**Files:**
- Read: `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- Read: `docs/test-reports/test-feature-20260421-112609.md`

- [ ] **Step 1: Run the focused automated regression slice**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py \
  translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_downstream_stage_execution.py -q
```

Expected: PASS for the new helper contract, pipeline integration, and compatibility with the shared execution layer.

- [ ] **Step 2: Re-run a real FeI2 downstream smoke**

Run the document-reader pipeline on the FeI2 fixture with:

- bridge emission enabled
- classical solving enabled
- downstream stages enabled

Save the output under a fresh result directory in:

- `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/`

Expected:

- route artifacts are written
- `lswt` executes when the route is `ready`
- `gswt` and `thermodynamics` outcomes remain explicit even if not executed

- [ ] **Step 3: Write or update the feature test report**

Record:

- which stages were routed as `ready`, `review`, or `blocked`
- which stages were actually executed
- whether route-only outcomes were understandable without reading source

- [ ] **Step 4: Commit the regression-closure slice**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py
git add translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py
git add translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md
git add translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py
git add translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py
git commit -m "test: verify FeI2 V2b downstream chaining"
```

## Execution Notes

- Preserve the `V2a` boundary: do not move downstream logic into
  `build_spin_only_solver_payload.py`.
- Prefer route evidence even when no execution happens.
- Treat `review` as visible-but-not-default-execute.
- Keep `GSWT` conservative until the payload contract is explicit.
- If `docs/` is ignored in this worktree, use `git add -f` only for the plan or
  spec files themselves; do not broadly force-add ignored directories.
