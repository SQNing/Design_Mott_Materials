# Certified GLT Bundle Aggregator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thin CLI tool that scans one or more certified GLT bundle directories and emits a stable JSON summary for batch triage and rerun planning.

**Architecture:** Keep the aggregator outside the certifier and reuse the existing bundle artifacts as the only data source. Implement the tool as a small standalone script under `scripts/classical/` and verify it with focused CLI-style tests using synthetic bundle directories.

**Tech Stack:** Python 3, `json`, `pathlib`, `argparse`, `subprocess`, `tempfile`, `unittest`/`pytest`

---

### Task 1: Define The Aggregator CLI Contract

**Files:**
- Create: `tests/test_aggregate_certified_glt_bundles.py`
- Create: `scripts/classical/aggregate_certified_glt_bundles.py`

- [ ] **Step 1: Write the failing test**

Add a test that builds two minimal bundle directories with:
- `next_action_summary.json`
- `summary.json`
- `applied_run_config.json`

Require the CLI to:
- accept explicit bundle directory paths
- emit JSON to `stdout`
- include one normalized output record per bundle

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py -q
```

Expected:
- import or script-not-found failure

- [ ] **Step 3: Write the minimal implementation**

Implement a script that:
- accepts bundle directories as positional arguments
- reads the three bundle JSON files
- emits a top-level JSON object with `bundles` and summary counts

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py -q
```

Expected:
- PASS

### Task 2: Add Stable Sorting And Parent-Directory Scanning

**Files:**
- Modify: `tests/test_aggregate_certified_glt_bundles.py`
- Modify: `scripts/classical/aggregate_certified_glt_bundles.py`

- [ ] **Step 1: Write the failing tests**

Extend coverage so the CLI must:
- accept a parent directory and scan child bundle directories automatically
- sort records with non-`certified` status first
- then prioritize bundles with blocking reasons
- then sort by suggested box budget descending
- then use bundle path as a stable tiebreaker

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py -q
```

Expected:
- FAIL due to missing scan or ordering behavior

- [ ] **Step 3: Write the minimal implementation**

Implement:
- parent-directory child discovery based on `next_action_summary.json`
- normalized record extraction fields:
  - `bundle_dir`
  - `status`
  - `blocking_reason`
  - `candidate_action_count`
  - `primary_action_kind`
  - `primary_action_target_axis`
  - `suggested_box_budget`
  - `applied_box_budget`
- stable sort matching the agreed priority rules

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py -q
```

Expected:
- PASS

### Task 3: Run Focused Regression

**Files:**
- Modify: none expected

- [ ] **Step 1: Run targeted aggregator and driver tests**

Run:
```bash
python -m pytest tests/test_aggregate_certified_glt_bundles.py tests/test_certified_glt_driver.py -q
```

Expected:
- PASS

- [ ] **Step 2: Run the certified GLT regression set**

Run:
```bash
python -m pytest tests/test_certified_glt_boxes.py tests/test_certified_glt_relaxed_bounds.py tests/test_certified_glt_branch_and_bound.py tests/test_certified_glt_shell_certificate.py tests/test_certified_glt_projector_certificate.py tests/test_certified_glt_incommensurate.py tests/test_certify_cpn_glt.py tests/test_certified_glt_driver.py tests/test_aggregate_certified_glt_bundles.py -q
```

Expected:
- PASS

- [ ] **Step 3: Summarize the new workflow**

Document that batch triage can now:
- read one parent directory of bundles
- produce a sorted JSON queue
- feed later rerun scripts without changing certifier semantics
