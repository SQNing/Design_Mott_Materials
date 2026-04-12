# Pipeline Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the current pseudospin-orbital pipeline by making thermodynamics runs more self-describing, enriching GSWT instability diagnostics, and upgrading `CP^(N-1)` classical plot payloads without breaking existing spin-only or older pseudospin-orbital paths.

**Architecture:** Keep all changes additive and schema-compatible. Extend the existing result payload, report renderer, and plot payload builder rather than introducing a new pipeline layer. Implement in three TDD slices: thermodynamics visibility first, GSWT diagnostics second, and `CP^(N-1)` plot semantics third.

**Tech Stack:** Python 3, `unittest`/`pytest`, existing CLI/report/plot modules under `scripts/`

---

### Task 1: Thermodynamics Profile Visibility

**Files:**
- Modify: `scripts/cli/solve_pseudospin_orbital_pipeline.py`
- Modify: `scripts/output/render_report.py`
- Test: `tests/test_solve_pseudospin_orbital_pipeline_cli.py`
- Test: `tests/test_render_report.py`

- [ ] **Step 1: Write the failing tests**

Add tests that require:
- the resolved thermodynamics profile and effective sampling settings to be stored in the pipeline manifest/result payload
- the text report to show the chosen profile plus effective sampler settings

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:
```bash
python3 -m pytest tests/test_solve_pseudospin_orbital_pipeline_cli.py tests/test_render_report.py -q
```

Expected: failure because the new thermodynamics profile/report fields do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Extend the thermodynamics payload/result handoff so the resolved profile name and effective settings are preserved in the final payload, then render them in the report.

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run:
```bash
python3 -m pytest tests/test_solve_pseudospin_orbital_pipeline_cli.py tests/test_render_report.py -q
```

Expected: PASS

### Task 2: Richer GSWT Instability Diagnostics

**Files:**
- Modify: `scripts/lswt/sun_gswt_driver.py`
- Modify: `scripts/output/render_report.py`
- Test: `tests/test_run_sun_gswt_driver.py`
- Test: `tests/test_render_report.py`

- [ ] **Step 1: Write the failing tests**

Add tests that require:
- classification of the nearest instability target as an exact node vs an interior path segment sample
- direct reporting of nearest path vector/distance and any matched symmetry label

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:
```bash
python3 -m pytest tests/test_run_sun_gswt_driver.py tests/test_render_report.py -q
```

Expected: failure because the enriched path classification is not present yet.

- [ ] **Step 3: Write the minimal implementation**

Extend GSWT diagnostics enrichment to compute a stable node/segment classification from the supplied `q_path` and path metadata, then surface it in the text report.

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run:
```bash
python3 -m pytest tests/test_run_sun_gswt_driver.py tests/test_render_report.py -q
```

Expected: PASS

### Task 3: `CP^(N-1)` Plot Payload Semantics

**Files:**
- Modify: `scripts/common/cpn_local_observables.py`
- Modify: `scripts/output/render_plots.py`
- Test: `tests/test_plotting_kpaths_and_magnetic_cells.py`

- [ ] **Step 1: Write the failing tests**

Add tests that require:
- richer orbital legend metadata in `plot_payload.json`
- explicit site annotations or summary fields that work for general `N_orb`
- preservation of the existing rendered classical-state path

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:
```bash
python3 -m pytest tests/test_plotting_kpaths_and_magnetic_cells.py -q
```

Expected: failure because the richer `CP^(N-1)` plot metadata is not present yet.

- [ ] **Step 3: Write the minimal implementation**

Add lightweight observable summaries and legend metadata without changing the old plot renderer contract for spin-only states.

- [ ] **Step 4: Run the targeted tests to verify GREEN**

Run:
```bash
python3 -m pytest tests/test_plotting_kpaths_and_magnetic_cells.py -q
```

Expected: PASS

### Task 4: Full Verification

**Files:**
- Modify: none expected
- Test: `tests/`

- [ ] **Step 1: Run the full test suite**

Run:
```bash
python3 -m pytest -q
```

Expected: PASS

- [ ] **Step 2: Optional real-data smoke verification**

Run the existing real sample pipeline with a thermodynamics smoke configuration if the code changes touched runtime payload wiring.

- [ ] **Step 3: Summarize compatibility**

Document that the new fields are additive and that old spin-only / previous pseudospin-orbital paths remain supported.
