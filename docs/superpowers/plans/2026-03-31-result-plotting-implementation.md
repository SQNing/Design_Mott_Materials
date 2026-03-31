# Result Plotting Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic result plotting for the skill by generating `lswt_dispersion.png`, `classical_state.png`, and `plot_payload.json` from completed classical plus LSWT runs.

**Architecture:** Introduce a dedicated plotting stage in Python via `scripts/render_plots.py`, keep plot generation independent from text reporting, and update the report layer to reference generated plot files rather than embedding plotting logic there.

**Tech Stack:** Python 3, `matplotlib`, `json`, `unittest`

---

## Chunk 1: Define Plotting Contracts In Tests

### Task 1: Add failing tests for plot payload generation and output files

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_render_plots.py`
- Reference: `docs/superpowers/specs/2026-03-31-result-plotting-design.md`

- [ ] **Step 1: Create a new plotting test module**

Add coverage for:
- a successful LSWT result with dispersion data
- a classical-only fallback where LSWT failed

- [ ] **Step 2: Write a failing test for successful figure generation**

Assert that a minimal successful payload produces:
- `plot_payload.json`
- `lswt_dispersion.png`
- `classical_state.png`

- [ ] **Step 3: Write a failing test for partial plotting behavior**

Assert that when LSWT failed:
- `classical_state.png` still exists
- `plot_payload.json` records the LSWT failure
- the LSWT dispersion image is skipped or omitted with an explicit reason

- [ ] **Step 4: Run the new plotting test module and verify it fails**

Run: `python3 -m unittest discover -s /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -p 'test_render_plots.py' -v`
Expected: FAIL because `render_plots.py` does not exist yet

- [ ] **Step 5: Commit the failing plotting tests**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/tests/test_render_plots.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: define result plotting behavior"
```

## Chunk 2: Implement Plot Generation

### Task 2: Add `render_plots.py`

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/render_plots.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_render_plots.py`

- [ ] **Step 1: Implement plot-payload extraction helpers**

Add helpers to normalize:
- classical site-frame data
- LSWT dispersion data
- metadata for plot regeneration

- [ ] **Step 2: Implement LSWT dispersion plotting**

Create a `matplotlib` line plot where:
- x-axis is q-point index
- y-axis is `omega`
- each band is a separate line

- [ ] **Step 3: Implement classical-state plotting**

Create a simple arrow plot from `classical_state.site_frames`:
- site order on x-axis
- arrow direction from the 3D spin projected into a simple 2D view

- [ ] **Step 4: Implement graceful partial-output behavior**

If LSWT data is missing or failed:
- still write `plot_payload.json`
- still write `classical_state.png` when possible
- skip the dispersion figure with an explicit recorded reason

- [ ] **Step 5: Re-run plotting tests**

Run: `python3 -m unittest discover -s /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -p 'test_render_plots.py' -v`
Expected: PASS

- [ ] **Step 6: Commit the plotting implementation**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/render_plots.py translation-invariant-spin-model-simplifier/tests/test_render_plots.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: generate result plots and plot payloads"
```

## Chunk 3: Integrate Plotting Into Result Assembly And Reporting

### Task 3: Update reporting to reference generated plots

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/render_report.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_render_report.py`

- [ ] **Step 1: Add failing report assertions for plot references**

Extend report tests to require:
- plot generation summary
- file path references for generated images
- skip reasons for omitted plots

- [ ] **Step 2: Update the report renderer**

Make `render_report.py` include:
- whether plotting ran
- generated plot file names or paths
- whether LSWT dispersion plotting was skipped

- [ ] **Step 3: Re-run report tests**

Run: `python3 -m unittest discover -s /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -p 'test_render_report.py' -v`
Expected: PASS

- [ ] **Step 4: Commit the report integration**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/scripts/render_report.py translation-invariant-spin-model-simplifier/tests/test_render_report.py
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "feat: reference generated plots in result reports"
```

## Chunk 4: Verify On A Real Minimal Sunny Example

### Task 4: Add an end-to-end plotting smoke test

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_lswt_contract.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_render_plots.py`

- [ ] **Step 1: Reuse the verified minimal ferromagnetic Heisenberg Sunny example**

Feed its output through the plotting layer and assert:
- `plot_payload.json` exists
- `lswt_dispersion.png` exists and is non-empty
- `classical_state.png` exists and is non-empty

- [ ] **Step 2: Run the full test suite**

Run: `python3 -m unittest discover -s /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -v`
Expected: PASS

- [ ] **Step 3: Run skill validation**

Run: `python3 /Users/mengsu/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/mengsu/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier`
Expected: `Skill is valid!`

- [ ] **Step 4: Commit the end-to-end plotting checkpoint**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add .
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "test: verify plotting on a minimal Sunny example"
```

## Chunk 5: Update Skill Documentation

### Task 5: Update `SKILL.md` and related docs

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/SKILL.md`
- Modify: `translation-invariant-spin-model-simplifier/WORKLOG.md`
- Modify: `translation-invariant-spin-model-simplifier/REVIEW.md`

- [ ] **Step 1: Update the skill workflow text**

Mention that the skill now:
- automatically writes plot images
- preserves plot input data for regeneration

- [ ] **Step 2: Record the plotting capability in worklog and review notes**

Summarize:
- supported first-stage figures
- verified example
- remaining limitations

- [ ] **Step 3: Commit the documentation update**

```bash
git -C /Users/mengsu/soft/Design_Mott_Materials add translation-invariant-spin-model-simplifier/SKILL.md translation-invariant-spin-model-simplifier/WORKLOG.md translation-invariant-spin-model-simplifier/REVIEW.md
git -C /Users/mengsu/soft/Design_Mott_Materials commit -m "docs: describe automatic result plotting support"
```
