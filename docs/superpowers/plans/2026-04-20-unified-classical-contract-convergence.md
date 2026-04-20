# Unified Classical Contract Next-Frontier Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the next convergence stage of the unified classical solver layer by centralizing classical-contract resolution, shrinking legacy fallback surfaces, and extending the standardized contract into auxiliary GLSWT / single-q workflows.

**Architecture:** The repository already has the first contract slice landed: spin-only and pseudospin classical solvers emit `classical_state_result`, bundle orchestration and LSWT / GSWT builders can consume that standardized result, and reports surface the normalized metadata. The next stage should stop duplicating ad hoc `classical_state_result` lookup logic across modules, quarantine raw `classical_state` compatibility paths behind a shared resolver, and make sidecar tools such as single-q convergence analysis load the same standardized contract instead of assuming raw solver-result shapes.

**Tech Stack:** Python 3, existing CLI / common / LSWT / output modules, `pytest`, unittest-style tests, current bundle and report infrastructure.

---

## Current Baseline

This plan assumes the following are already on `main`:

- shared `classical_state_result` schema and helper builders
- normalized spin-only classical outputs
- normalized pseudospin classical outputs
- LSWT / Python-GLSWT / Sunny-GSWT builders consuming `classical_state_result.classical_state`
- bundle-stage gating, report rendering, plot metadata, LSWT decisions, and rotating-frame supercell resolution preferring the standardized contract

This plan is therefore a forward-looking cleanup and convergence plan. It should not re-implement the earlier landed slices.

## File Structure

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/common/cpn_classical_state.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/output/render_report.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/output/render_plots.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/classical/decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lswt/single_q_z_harmonic_convergence_driver.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_contract_resolution.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_write_results_bundle.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_output_classical_contract_rendering.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_layer_adapters.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_build_python_glswt_payload.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_single_q_z_harmonic_convergence.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/docs/superpowers/specs/2026-04-20-unified-classical-solver-layer-design.md`

**Responsibilities:**
- `classical_contract_resolution.py`
  Provide the single shared place that resolves `classical_state_result`, standardized `classical_state`, and per-stage `downstream_compatibility` from mixed legacy payloads.
- `cpn_classical_state.py`
  Stop re-implementing raw `classical_state` crawling and instead consume the shared resolver before doing CP^(N-1)-specific normalization.
- `write_results_bundle.py`, `render_report.py`, `render_plots.py`, `decision_gates.py`
  Depend on the shared contract resolver rather than each carrying local lookup helpers and divergent fallback behavior.
- `solve_pseudospin_orbital_pipeline.py`
  Make bundle export explicitly contract-first and keep raw top-level `classical_state` as compatibility-only output.
- `build_python_glswt_payload.py` and `single_q_z_harmonic_convergence_driver.py`
  Accept pipeline artifacts and sidecar inputs through the standardized contract, not only raw solver-result shapes.
- Tests
  Lock in shared-resolution semantics and the remaining legacy-compatibility boundary before implementation.

Notes:
- Keep legacy fields temporarily where external scripts may still read them, but route all new internal logic through the shared resolver.
- Do not change solver numerics, Sunny backends, Julia scripts, or physical algorithm choices in this plan.
- Prefer one small shared helper module over repeating near-identical `_get_classical_state_result(...)` helpers in many files.
- For this stage, treat `build_lswt_payload.py` and `build_sun_gswt_payload.py` as already-good consumers and keep them out of scope unless Task 4 uncovers a concrete blocker in auxiliary GLSWT workflows.

## Task 1: Create A Shared Classical Contract Resolver

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_contract_resolution.py`

- [ ] **Step 1: Write the failing shared-resolver tests**

Cover:
- resolving `classical_state_result` from top-level payloads and nested `payload["classical"]`
- resolving `classical_state_result.classical_state` before legacy `classical_state`
- resolving stage compatibility status and reason from `downstream_compatibility`
- returning `None` cleanly when no standardized contract exists

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest tests/test_classical_contract_resolution.py -q
```

Expected:
- FAIL because the shared resolver module does not exist yet

- [ ] **Step 3: Implement the minimal shared resolver**

Implement:
- `get_classical_state_result(payload)`
- `get_standardized_classical_state(payload)`
- `get_downstream_stage_compatibility(payload, stage_name)`
- `get_downstream_stage_status(payload, stage_name)`

Required behavior:
- helpers must accept either a full payload or a bare `classical_state_result` mapping
- standardized contract lookup always wins over legacy raw-state lookup
- helper outputs are read-only resolution utilities and do not mutate payloads
- canonical stage names for this plan are `lswt`, `gswt`, and `thermodynamics`
- `get_downstream_stage_compatibility(...)` and `get_downstream_stage_status(...)` return `None` when the standardized contract or requested stage entry is absent
- legacy compatibility remains representable by returning `None` when the standardized contract is absent

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest tests/test_classical_contract_resolution.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_classical_contract_resolution.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add shared classical contract resolver"
```

## Task 2: Rebase Contract Consumers On The Shared Resolver

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/common/cpn_classical_state.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/output/render_report.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/output/render_plots.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/classical/decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_write_results_bundle.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_output_classical_contract_rendering.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decision_gates.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_contract_resolution.py`

- [ ] **Step 1: Write the failing consumer tests**

Cover:
- `resolve_cpn_classical_state_payload(...)` unwraps standardized contract input before legacy raw payloads
- bundle helpers and stage summaries keep their current contract-first behavior after switching to the shared resolver
- report text and plot summaries still surface standardized `method / role / solver_family / downstream_compatibility`
- LSWT decision helpers still prefer standardized `downstream_compatibility.lswt`

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_classical_contract_resolution.py \
  tests/test_write_results_bundle.py \
  tests/test_output_classical_contract_rendering.py \
  tests/test_decision_gates.py \
  -q
```

Expected:
- FAIL because the current modules still carry duplicated local lookup logic

- [ ] **Step 3: Implement the minimal shared-resolver adoption**

Implement:
- replace local `_get_classical_state_result(...)` clones with imports from `common.classical_contract_resolution`
- make `cpn_classical_state.py` resolve standardized contract input before CP^(N-1) normalization
- preserve current user-visible output strings and stage-summary fields

Required behavior:
- no regression in contract-first gating or rendering
- no new behavior differences between top-level and nested `payload["classical"]` wrappers
- legacy raw `classical_state` support remains only as fallback inside the shared resolver or CP^(N-1) normalizer

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_classical_contract_resolution.py \
  tests/test_write_results_bundle.py \
  tests/test_output_classical_contract_rendering.py \
  tests/test_decision_gates.py \
  -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/common/cpn_classical_state.py \
  translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py \
  translation-invariant-spin-model-simplifier/scripts/output/render_report.py \
  translation-invariant-spin-model-simplifier/scripts/output/render_plots.py \
  translation-invariant-spin-model-simplifier/scripts/classical/decision_gates.py \
  translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_classical_contract_resolution.py \
  translation-invariant-spin-model-simplifier/tests/test_write_results_bundle.py \
  translation-invariant-spin-model-simplifier/tests/test_output_classical_contract_rendering.py \
  translation-invariant-spin-model-simplifier/tests/test_decision_gates.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "refactor: share classical contract resolution"
```

## Task 3: Narrow The Pseudospin Bundle Compatibility Surface

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_layer_adapters.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_write_results_bundle.py`

- [ ] **Step 1: Write the failing pseudospin bundle tests**

Cover:
- `_build_result_payload(...)` always exports `classical_state_result` when present
- `_resolved_bundle_classical_state(...)` derives compatibility raw state from the standardized contract before looking at raw `solver_result["classical_state"]`
- top-level `payload["classical_state"]` remains present only as a compatibility mirror, not as the authoritative source for downstream routing

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_classical_solver_layer_adapters.py \
  tests/test_write_results_bundle.py \
  -q -k "pseudospin or bundle"
```

Expected:
- FAIL because the pseudospin pipeline still resolves some bundle fields from raw solver-result structure first

- [ ] **Step 3: Implement the minimal compatibility tightening**

Implement:
- route pseudospin bundle export through the shared contract resolver
- keep raw top-level `classical_state` only as mirrored compatibility data
- add one explicit compatibility helper instead of repeated raw `classical_state` branching

Required behavior:
- external payload shape remains backward compatible
- internal bundle logic and any future callers can treat `classical_state_result` as authoritative
- no change to thermodynamics eligibility semantics already landed on `main`

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_classical_solver_layer_adapters.py \
  tests/test_write_results_bundle.py \
  -q -k "pseudospin or bundle"
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_classical_solver_layer_adapters.py \
  translation-invariant-spin-model-simplifier/tests/test_write_results_bundle.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "refactor: quarantine pseudospin classical compatibility fields"
```

## Task 4: Extend The Standardized Contract Into Auxiliary GLSWT Workflows

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/lswt/single_q_z_harmonic_convergence_driver.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_build_python_glswt_payload.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_single_q_z_harmonic_convergence.py`

- [ ] **Step 1: Write the failing auxiliary-workflow tests**

Cover:
- `build_python_glswt_payload(...)` still accepts `classical_state_result` wrappers after the shared resolver refactor
- `run_single_q_z_harmonic_convergence_driver(...)` can load pipeline output directories where `solver_result.json` is treated as a standardized contract source rather than blindly injected as raw `payload["classical_state"]`
- single-q convergence still works when the pipeline artifact carries both `classical_state_result` and compatibility `classical_state`

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_build_python_glswt_payload.py \
  tests/test_single_q_z_harmonic_convergence.py \
  -q
```

Expected:
- FAIL because the sidecar driver still assumes solver-result directories should be rehydrated as raw `classical_state`

- [ ] **Step 3: Implement the minimal auxiliary-path migration**

Implement:
- make `build_python_glswt_payload(...)` use the shared resolver for standardized contract inputs
- make `_load_pipeline_output_directory(...)` attach solver artifacts through `classical_state_result` first, while still populating compatibility `classical_state` if needed
- keep existing single-q convergence scan semantics unchanged

Required behavior:
- sidecar GLSWT tools and convergence scans consume the same authoritative classical contract as the main pipeline
- old pipeline directories without standardized contract still remain readable
- no changes to scan parameter defaults or physical interpretation

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_build_python_glswt_payload.py \
  tests/test_single_q_z_harmonic_convergence.py \
  -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/lswt/build_python_glswt_payload.py \
  translation-invariant-spin-model-simplifier/scripts/lswt/single_q_z_harmonic_convergence_driver.py \
  translation-invariant-spin-model-simplifier/scripts/common/classical_contract_resolution.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_build_python_glswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_single_q_z_harmonic_convergence.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: extend classical contract into auxiliary glswt workflows"
```

## Task 5: Regression Verification And Spec Refresh

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/docs/superpowers/specs/2026-04-20-unified-classical-solver-layer-design.md`

- [ ] **Step 1: Run the full targeted regression suite**

Run:
```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
python -m pytest \
  tests/test_classical_state_result.py \
  tests/test_classical_contract_resolution.py \
  tests/test_classical_solver_layer_adapters.py \
  tests/test_write_results_bundle.py \
  tests/test_output_classical_contract_rendering.py \
  tests/test_decision_gates.py \
  tests/test_build_lswt_payload.py \
  tests/test_build_python_glswt_payload.py \
  tests/test_build_sun_gswt_payload.py \
  tests/test_python_glswt_driver.py \
  tests/test_run_sun_gswt_driver.py \
  tests/test_rotating_frame_consistency.py \
  tests/test_single_q_z_harmonic_convergence.py \
  -q
```

Expected:
- PASS with all contract-convergence tests green

- [ ] **Step 2: Update the spec implementation-status section**

Document:
- that contract-first resolution is now shared rather than duplicated across consumers
- that pseudospin bundle export and auxiliary GLSWT tools now consume the standardized contract first
- what legacy compatibility fields still remain and why
- the next migration frontier after this plan

- [ ] **Step 3: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  docs/superpowers/specs/2026-04-20-unified-classical-solver-layer-design.md
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "docs: refresh unified classical contract status"
```
