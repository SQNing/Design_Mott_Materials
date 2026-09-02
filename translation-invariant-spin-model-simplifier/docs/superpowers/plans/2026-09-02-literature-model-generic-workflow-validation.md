# Literature Models Through the Generic Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate literature-derived models by sending answer-free model inputs through the repository's generic model workflow, then compare the resulting product output with literature claims in a separate test/audit layer.

**Architecture:** A literature case is split into an answer-free `model_input` plus `analysis_request`, and a comparison-only `literature_claim`. Test runners call the existing generic normalization/simplification and solver-routing entrypoints; adapters may translate source records into this contract but may not calculate the registered answer. Scientifically reusable calculations live in generic solver backends, while independent oracles and paper-value comparisons remain under `scripts/validation/` and `tests/`.

**Tech Stack:** Python 3, pytest, existing `cli.simplify_text_input` generic pipeline, existing solver capability/routing modules, JSON/CSV audit reports.

## Global Constraints

- Follow repository-root `AGENTS.md`.
- The product entrypoint must remain usable for a model with no literature registry entry.
- Literature IDs, expected values, tolerances derived from expected values, and oracle outputs must not enter product computation.
- Material physical ambiguity must produce `interaction.status = needs_input`; unsupported representation or analysis must be reported explicitly.
- Prefer physics, normalization, convergence, and independent-method tests over adversarial/static-scanner expansion.
- Preserve every pre-existing WIP file; do not delete, truncate, move, overwrite, stage, or commit unrelated changes.
- Subagents, if explicitly authorized, may use only GPT-5.6 low, medium, or high; never fast and never above high.

---

### Task 1: Audit and isolate the current literature coordinator

**Files:**
- Inspect: `scripts/validation/literature_evidence_isolation.py`
- Inspect: `scripts/validation/literature_evidence_adapters.py`
- Inspect: `tests/test_literature_evidence_adapters.py`
- Modify only after a failing scope test: the exact files above

**Interfaces:**
- Consumes: `run_isolated_recomputation(adapter_id, authority_context, *, run_parent)`
- Produces: an explicit audit-only boundary; no import or call edge from `scripts/cli/`, `scripts/input/`, `scripts/simplify/`, `scripts/classical/`, or `scripts/lswt/` to literature catalogs

- [x] **Step 1: Record the current diff by responsibility**

Classify each new block as `test_audit`, `generic_product`, or `misrouted`. Record exact functions and paths in the task report.

- [x] **Step 2: Write a failing architecture test if a product import exists**

Add a test that parses product modules and rejects imports of:

```python
FORBIDDEN_PRODUCT_DEPENDENCIES = {
    "validation.literature_evidence_adapters",
    "validation.literature_evidence_adapter_oracles",
    "validation.literature_evidence_isolation",
}
```

The test must inspect only product directories and must allow test/audit modules to import these dependencies.

- [x] **Step 3: Run the architecture test and verify the observed result**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider \
  tests/test_literature_generic_workflow.py::test_product_modules_do_not_depend_on_literature_catalogs -vv
```

Expected now: PASS if the current separation is already real; otherwise a genuine FAIL naming the product import edge.

- [x] **Step 4: Remove only proven misrouted product edges**

Keep `run_isolated_recomputation` audit-only. Move a calculation into product code only if it is parameterized by a generic model/method contract and has a non-literature caller test.

- [x] **Step 5: Stop expanding the static attack surface**

Do not add new descriptor, receiver, AST, mutation, or adversarial cases unless a concrete answer-leak or product-boundary regression requires one.

---

### Task 2: Add an answer-separated literature case contract

**Files:**
- Create: `scripts/validation/literature_generic_workflow.py`
- Create: `tests/test_literature_generic_workflow.py`

**Interfaces:**
- Produces: `LiteratureModelCase`, `LiteratureClaim`, `run_literature_case(case)`, and `compare_literature_claim(product_result, claim)`
- Consumes: `run_text_simplification_pipeline(...)` or `run_simplification_from_normalized_model(...)`

- [x] **Step 1: Write failing contract tests**

Require exact, immutable records with this separation:

```python
LiteratureModelCase(
    case_id="onsager_square_ising_tc",
    source_id="Onsager_1944",
    model_input={...},
    input_route="operator",
    analysis_request={"task": "critical_temperature"},
    claim_id="critical_temperature",
)

LiteratureClaim(
    claim_id="critical_temperature",
    observable="critical_temperature",
    value=2.269185314213022,
    uncertainty=0.0,
    units="J/k_B",
    source_location="Phys. Rev. 65, 117 (1944)",
)
```

`LiteratureModelCase` must have no expected value, uncertainty, match tolerance, oracle result, or literature-derived answer field.

- [x] **Step 2: Verify RED**

Run the contract test and confirm failure because the records/functions do not exist, not because of collection or fixture errors.

- [x] **Step 3: Implement the minimal immutable records**

Use frozen dataclasses and exact validation. Keep claims in a separate mapping keyed by `claim_id`; `run_literature_case` receives a case only, never a claim.

- [x] **Step 4: Verify GREEN**

Run all tests in `tests/test_literature_generic_workflow.py` and confirm the case cannot expose a paper value to the product call.

---

### Task 3: Complete one real generic-workflow vertical slice

**Files:**
- Modify: `scripts/validation/literature_generic_workflow.py`
- Modify: `tests/test_literature_generic_workflow.py`
- Reuse without literature imports: `scripts/cli/simplify_text_input.py`

**Interfaces:**
- Consumes: answer-free operator/model input for one published benchmark
- Produces: `normalization_status`, `simplification_status`, `analysis_status`, and an optional `computed_observable`

- [x] **Step 1: Select a first case that the existing product pipeline can represent**

Use a simple translation-invariant operator model, initially the square-lattice Ising Hamiltonian, expressed without its paper value:

```text
-J * Sz@0 Sz@1 on every nearest-neighbor bond of a square lattice
```

The model input contains `J`, lattice/bond structure, spin convention, and requested analysis only.

- [x] **Step 2: Write a failing end-to-end test**

Assert that the case invokes the generic pipeline, returns a canonical/readable model, and produces identical product material after changing `case_id` and `source_id`.

- [x] **Step 3: Verify RED**

The failure must show the missing literature-to-generic runner or unsupported generic analysis route.

- [x] **Step 4: Implement only the missing generic connection**

Call `run_text_simplification_pipeline` for text/operator cases and `run_simplification_from_normalized_model` for already normalized cases. Do not call `ADAPTER_DEFINITIONS`, `ADAPTER_ELIGIBILITY`, or `ORACLE_DEFINITIONS`.

- [x] **Step 5: Verify simplification GREEN**

Require canonical model output, readable blocks, effective model, fidelity, and explicit residual/unsupported information.

- [x] **Step 6: Add the analysis result only through a generic backend**

If no generic critical-temperature backend exists, report `analysis_status="unsupported"` for this case and choose a second benchmark already supported by a generic solver. Do not import the literature adapter calculation to force a pass.

---

### Task 4: Add representative model-family slices

**Files:**
- Modify: `scripts/validation/literature_generic_workflow.py`
- Modify: `tests/test_literature_generic_workflow.py`
- Modify or create generic solver modules only when reusable outside literature tests

**Interfaces:**
- Consumes: answer-free operator, matrix/tensor, structured, and document-derived model inputs
- Produces: at least four working generic route classifications and explicit unsupported outcomes

- [x] **Step 1: Add one local-matrix/ED case**

Use a two-site or small-cell Hamiltonian represented through the existing matrix route. Assert reconstruction and a generic eigenvalue calculation, not a benchmark-specific helper.

- [x] **Step 2: Add one transfer/root case**

Route through a reusable transfer-matrix or root-solving backend. The backend API must consume equations/model parameters rather than a literature ID.

- [x] **Step 3: Add one classical or Fourier case**

Use the existing solver capability registry and downstream routing. Assert explicit backend selection and normalized energy/observable conventions.

- [x] **Step 4: Add one unsupported case**

Assert that a model requiring an unavailable method reports `unsupported` with a concrete blocker and does not fall back to an adapter answer.

- [x] **Step 5: Run focused tests**

Run only the new generic-workflow tests plus the directly affected product-route tests.

---

### Task 5: Classify and migrate all 29 eligible literature models

**Files:**
- Modify: `scripts/validation/literature_generic_workflow.py`
- Create: `reports/literature_generic_workflow_coverage.csv`
- Create: `reports/literature_generic_workflow_coverage.md`
- Modify: `tests/test_literature_generic_workflow.py`

**Interfaces:**
- Consumes: the 29 current eligible benchmark definitions as source metadata only
- Produces: one row per model/claim with layered status

- [x] **Step 1: Export the exact 29-case inventory**

Each row must contain:

```text
source_id, model_id, claim_id, input_route, normalization_status,
simplification_status, analysis_kind, backend_status, computation_status,
convergence_status, oracle_status, literature_match_status, blocker
```

- [x] **Step 2: Build answer-free inputs**

For every case, separate model parameters and conventions from paper values. Review each case for hidden expected-value constants in solver inputs or tolerances.

- [x] **Step 3: Run the generic workflow for all 29**

Do not require all analyses to succeed. Record `unsupported`, `needs_input`, or `inconclusive` honestly at the exact failing layer.

- [x] **Step 4: Promote reusable missing capabilities by solver family**

Group gaps into ED, root/transfer, Fourier/constraint, classical, thermodynamic, or other reusable backends. Add one backend capability only when it serves a generic model contract and has a non-literature test.

- [x] **Step 5: Compare claims after product execution**

Normalize units and conventions in the comparison layer. Use an oracle only after product computation and record whether it is scientifically independent.

---

### Task 6: Extend the layered inventory to all registered results and candidate papers

**Files:**
- Modify: `scripts/validation/literature_generic_workflow.py`
- Modify: `reports/literature_generic_workflow_coverage.csv`
- Modify: `reports/literature_generic_workflow_coverage.md`

**Interfaces:**
- Consumes: 137 canonical sources, 155 registered results, and any separately retained discovery pool
- Produces: deduplicated source/model/claim counts and layered coverage, without conflating parsing with numerical reproduction

- [x] **Step 1: Deduplicate by source, model candidate, and claim**

Report source count, model count, and model-claim count separately.

- [x] **Step 2: Run extraction and generic landing first**

Do not write a solver while the Hamiltonian, convention, or requested observable remains ambiguous.

- [x] **Step 3: Batch gaps by reusable capability**

Prioritize implementations that unlock multiple cases. Never create a paper-ID-dispatched product solver.

- [x] **Step 4: Publish honest layered totals**

The report must distinguish extracted, normalized, simplified, computed, converged, oracle-checked, literature-matched, unsupported, and needs-review totals.

---

### Task 7: Final verification and handoff

**Files:**
- Verify all files changed by Tasks 1–6
- Update: `reports/literature_generic_workflow_coverage.md`

**Interfaces:**
- Produces: reproducible commands and evidence proving the generic workflow boundary and the achieved literature coverage

- [x] **Step 1: Run focused behavior tests**

Run the literature generic-workflow tests, affected simplification tests, and affected solver tests with `PYTHONDONTWRITEBYTECODE=1` and pytest cache disabled.

- [x] **Step 2: Run architecture checks**

Confirm product modules have no dependency on literature catalogs and product results are invariant to literature identity metadata.

- [x] **Step 3: Run full relevant suites**

Run the complete generic-workflow validation suite and all directly affected repository tests. Record exact pass/fail/deselected counts.

- [x] **Step 4: Audit every coverage row**

For every model/claim, verify that the reported status is supported by a real current result, not a default or stale report row.

- [x] **Step 5: Report completion against the full objective**

Do not claim completion until the vertical slices work, all 29 eligible cases have current layered outcomes, the registered inventory is represented, and the product/literature boundary is proven by source and behavior.

## Completion evidence (2026-09-02)

- The product boundary is recorded in repository-root `AGENTS.md`. Product
  directories contain no import of the literature adapter, oracle, or
  isolation catalogs. Renaming literature identity metadata leaves generic
  normalized/simplified model material unchanged.
- `LiteratureModelCase` and `LiteratureClaim` are immutable, separate records.
  A poison-object regression proves the complete inventory path does not read
  registry `standard_result` values.
- Generic product analysis is implemented in `scripts/common/model_analysis.py`
  and is selected by model/analysis contracts, not by paper or benchmark ID.
- All 29 eligible answer-free cases land in the generic workflow: 29 normalize,
  29 simplify, 27 compute and match their separately held literature claims;
  two finite-size residual-entropy cases remain honestly `inconclusive`.
- The complete inventory contains 137 canonical DOI/arXiv sources, 138 distinct
  registered models, and 155 model-claim rows. The remaining 126 rows are
  explicitly `not_landed`; none inherits a green status from the legacy
  literature audit. Independent-oracle coverage is explicitly 0 rather than
  being conflated with paper-value comparison.
- Reproducible reports are
  `reports/literature_generic_workflow_coverage.{csv,md}` and
  `reports/literature_generic_workflow_registered_inventory.{csv,md}`. A test
  regenerates all four and compares every row/current Markdown byte-for-byte
  (CSV semantically, to ignore CRLF versus LF).
- Final relevant-suite command:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python -m pytest \
    -p no:cacheprovider -q \
    tests/test_generic_model_analysis.py \
    tests/test_literature_generic_workflow.py \
    tests/test_lattice_structure_builder.py \
    tests/test_normalize_input.py
  ```

  Result: `70 passed in 51.53s`. Nonlegacy flake8, AST parsing of the four new
  Python files, and scoped `git diff --check` also passed.
