# Certified GLT Rerun Batch Executor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thin batch executor that consumes a certified GLT bundle shortlist and launches each bundle's `reproduce.sh` into a shared output root.

**Architecture:** Keep shortlist generation and shortlist execution separate. The new executor will only read the already-ranked aggregate JSON payload, preserve its order, and invoke bundle-local `reproduce.sh` scripts with a shared naming convention for output subdirectories.

**Tech Stack:** Python 3, `json`, `argparse`, `subprocess`, `pathlib`, `tempfile`, `unittest`/`pytest`

---

### Task 1: Define The Batch Executor Contract

**Files:**
- Create: `tests/test_execute_certified_glt_rerun_batch.py`
- Create: `scripts/classical/execute_certified_glt_rerun_batch.py`

- [ ] **Step 1: Write the failing test**

Add a test that:
- creates two fake bundle directories with executable `reproduce.sh`
- writes an aggregate shortlist JSON payload pointing at those bundles
- requires the executor to:
  - read the shortlist from a file
  - execute bundles in order
  - create subdirectories under `--output-root`
  - write a JSON execution summary to `stdout`

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
python -m pytest tests/test_execute_certified_glt_rerun_batch.py -q
```

Expected:
- script-not-found failure

- [ ] **Step 3: Write the minimal implementation**

Implement:
- shortlist loading from file
- output directory naming such as `01-<bundle-name>`
- bundle command execution through `bash <bundle>/reproduce.sh <output_dir> --candidate-rank <rank>`
- compact JSON execution summary to `stdout`

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
python -m pytest tests/test_execute_certified_glt_rerun_batch.py -q
```

Expected:
- PASS

### Task 2: Add stdin Input And Candidate-Rank Forwarding

**Files:**
- Modify: `tests/test_execute_certified_glt_rerun_batch.py`
- Modify: `scripts/classical/execute_certified_glt_rerun_batch.py`

- [ ] **Step 1: Write the failing test**

Extend coverage so the executor must:
- read the shortlist JSON from `stdin` when no input file is given
- forward a configurable `--candidate-rank`
- preserve bundle order from the shortlist

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest tests/test_execute_certified_glt_rerun_batch.py -q
```

Expected:
- FAIL due to missing stdin or rank-forwarding behavior

- [ ] **Step 3: Write the minimal implementation**

Implement:
- optional positional shortlist path
- fallback to `stdin`
- configurable `--candidate-rank` with default `1`
- short stderr progress lines for each launched bundle

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest tests/test_execute_certified_glt_rerun_batch.py -q
```

Expected:
- PASS

### Task 3: Run Focused Regression

**Files:**
- Modify: none expected

- [ ] **Step 1: Run batch-tool focused regression**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py tests/test_execute_certified_glt_rerun_batch.py tests/test_certified_glt_driver.py -q
```

Expected:
- PASS

- [ ] **Step 2: Run certified GLT regression with the new batch executor**

Run:
```bash
python -m pytest tests/test_certified_glt_boxes.py tests/test_certified_glt_relaxed_bounds.py tests/test_certified_glt_branch_and_bound.py tests/test_certified_glt_shell_certificate.py tests/test_certified_glt_projector_certificate.py tests/test_certified_glt_incommensurate.py tests/test_certify_cpn_glt.py tests/test_certified_glt_driver.py tests/test_aggregate_certified_glt_bundles.py tests/test_execute_certified_glt_rerun_batch.py -q
```

Expected:
- PASS

- [ ] **Step 3: Summarize the new closed loop**

Document that the workflow is now:
- aggregate bundles
- filter / rank / emit shortlist
- execute rerun wave into a shared output root
