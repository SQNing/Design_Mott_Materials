# Strict Literature Runtime Evidence Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish and commit the fail-closed runtime-evidence framework, migrate its 76 legacy audit tests without losing metadata coverage, and add strict Taylor Ising-chain and Tasaki LSM routes so the evidenced count rises from 2/155 to 4/155.

**Architecture:** Keep source acquisition and inventory validation separate from benchmark reproduction. `literature_runtime_evidence.py` owns source-specific parsers, local execution adapters, operand selection, and comparison traces; `literature_reproduction_audit.py` consumes those runtime bundles and never infers strict status from prose or legacy helper labels. Add strict routes in small source-backed batches, with every parser and adapter introduced through red-green TDD.

**Tech Stack:** Python 3.9, pytest, existing literature inventory/source-cache APIs, `pdftotext` extraction through `load_verified_source`, JSON/CSV/Markdown audit writers.

**Scope:** This is the first executable phase of the 155/155 objective, not a claim that the objective is complete. Source acquisition for the 25 blocked routes and source-specific designs for the remaining rows require subsequent plans based on a checked per-benchmark route manifest. This phase must leave those rows visibly non-strict.

---

### Task 1: Align the audit regression suite with fail-closed runtime evidence

**Files:**
- Modify: `tests/test_literature_reproduction_audit.py`
- Test: `tests/test_literature_runtime_evidence.py`

- [ ] **Step 1: Reproduce the obsolete strict-count failure**

Run: `python -m pytest -x -vv tests/test_literature_reproduction_audit.py`

Expected: the legacy assertion expects `strict_local_recomputed == 155`, while the runtime audit reports one strict recomputation, one strict source parse, and 153 projection-only rows.

- [ ] **Step 2: Replace the obsolete global promotion assertion with fail-closed invariants**

Assert that every strict row has a matching runtime evidence record, source hash, extraction trace, and the mode-specific execution trace. Assert the current supported routes by benchmark name and require all unsupported legacy entries to remain non-strict.

- [ ] **Step 3: Convert every benchmark-specific promotion test without dropping its metadata coverage**

Retain all assertions about `local_check_kind`, evidence text, task coverage, and negative evidence. Rename misleading `*_is_strict_*` and `*_promotes_*` tests to describe legacy projection evidence. For each row without runtime evidence, assert `strict_audit_category == "local_projection_only"`, `strict_literature_match_label == "no"`, and absent runtime traces. Do not delete benchmark-specific checks or collapse them into an unreviewable blanket assertion.

- [ ] **Step 4: Make report tests generate into `tmp_path`**

Import `write_audit_markdown` and `write_remaining_strict_reproduction_gaps_markdown` in the audit test module. Replace every read of existing files under `reports/` with a writer call to a fresh `tmp_path`; assert 2 strict rows and 153 named gaps for the current framework. Change the combined report wording from “strict local recomputations” to the neutral “strict runtime-evidenced entries,” and report `strict_local_recomputed` and `strict_local_source_parsed` separately. This verifies current writer behavior without overwriting or depending on the user's untracked reports.

- [ ] **Step 5: Run both audit suites**

Run: `python -m pytest -q tests/test_literature_runtime_evidence.py tests/test_literature_reproduction_audit.py`

Expected: all tests pass, with strict counts `strict_local_recomputed=1`, `strict_local_source_parsed=1`, and `local_projection_only=153` for the current two-route implementation.

- [ ] **Step 6: Commit the framework and coherent tests**

Run:

```bash
git add scripts/validation/literature_runtime_evidence.py scripts/validation/literature_reproduction_audit.py tests/test_literature_reproduction_audit.py
git add -f tests/test_literature_runtime_evidence.py docs/superpowers/plans/2026-07-21-strict-literature-runtime-evidence.md
git commit -m "Require runtime evidence for strict literature reproduction"
```

Do not stage or regenerate untracked report files.


### Task 2: Add the Taylor one-dimensional Ising correlation-length recomputation

**Files:**
- Modify: `tests/test_literature_runtime_evidence.py`
- Modify: `scripts/validation/literature_runtime_evidence.py`
- Use existing adapter: `scripts/validation/literature_spin_model_benchmarks.py::classical_ising_chain_correlation_length`

- [ ] **Step 1: RED - specify the source parse and failure cases**

Add tests for source ID `arxiv_1210a896b82f8e645da1`, SHA-256 `a73cd384ccabcd594742cb3c38058c914cca0a4abd6b862784a38303ff1941e2`, and Taylor Eq. (5)'s statement that the correlation is `tanh^l(J beta)`. The parser must derive `xi = -1/log(tanh(beta J))`, return only the beta=J=1 numeric operand `correlation_length_beta_1_j_1`, record the symbolic derivation in the extraction trace, and reject text missing Eq. (5), the correlation definition, the exponent `l`, or `tanh(J beta)`.

- [ ] **Step 2: Verify RED**

Run the focused Taylor tests and confirm they fail because `parse_taylor_ising_correlation_length` and its collector route do not exist.

- [ ] **Step 3: GREEN - implement the source-specific parser and route**

Add `parse_taylor_ising_correlation_length`. Extend the collector spec with an explicit `registry_fields` override and test that it can only narrow the inventory selector, never select an unregistered field. Register `one_dimensional_classical_ising_correlation_length` as `local_recompute`, select only `correlation_length_beta_1_j_1`, call `classical_ising_chain_correlation_length(beta=1.0, exchange=1.0)`, and record the source derivation, source span, narrowed selector, adapter parameters, and exact three-way equality among the three numeric operands. The registry's formula string remains source-parse context and is not represented as an independently computed operand.

- [ ] **Step 4: Verify GREEN and exact count delta**

Run the focused runtime tests and audit tests. Require `strict_local_recomputed=2`, `strict_local_source_parsed=1`, and `local_projection_only=152` after this route alone.

### Task 3: Add the Tasaki LSM theorem source parse

**Files:**
- Modify: `tests/test_literature_runtime_evidence.py`
- Modify: `scripts/validation/literature_runtime_evidence.py`

- [ ] **Step 1: RED - specify the theorem statement and failure cases**

Add tests for source ID `doi_607b6dc8e2ebace9ef53`, SHA-256 `4f64a8e110740ffa2f595608e2807377c7a4132b2561f354788a9d757490c5f0`, and the statement that a one-dimensional spin system with half-odd-integer spin has gapless excitations in the infinite-volume limit provided the ground state is unique. Reject text missing one-dimensionality, half-odd-integer spin, uniqueness, gaplessness, or the infinite-volume limit.

- [ ] **Step 2: Verify RED**

Run the focused Tasaki tests and confirm they fail because `parse_tasaki_lsm_half_integer_constraint` and its collector route do not exist.

- [ ] **Step 3: GREEN - implement the parser as `local_source_parse`**

Return `{"unique_ground_state_implies_gapless_excitations": True}` with source-specific anchors and spans. Register `lieb_schultz_mattis_half_integer_constraint` as `local_source_parse`; do not invent an execution adapter for a theorem statement.

- [ ] **Step 4: Verify GREEN and exact count delta**

Run focused and audit tests. Require the phase endpoint `strict_local_recomputed=2`, `strict_local_source_parsed=2`, `local_projection_only=151`, and no other category changes.

- [ ] **Step 5: Commit the reviewed batch**

Run:

```bash
git add scripts/validation/literature_runtime_evidence.py tests/test_literature_runtime_evidence.py tests/test_literature_reproduction_audit.py
git commit -m "Add Taylor and Tasaki runtime literature evidence"
```

Do not include generated reports or unrelated worktree changes.

### Task 4: Add an automated completion gate that currently reports the remaining gap

**Files:**
- Modify: `scripts/validation/literature_runtime_evidence.py`
- Modify: `tests/test_literature_runtime_evidence.py`
- Modify: `scripts/validation/literature_reproduction_audit.py`
- Modify: `tests/test_literature_reproduction_audit.py`

- [ ] **Step 1: RED - specify exact-set completion semantics**

Add a test for a structural coverage validator that compares evidence keys to the exact 155-name registry set. It must report missing and extra names deterministically and reject the current four-route evidence map. Add synthetic-map unit tests proving the structural validator accepts only exact coverage with valid mode-specific traces and operand equality. Add a separate production-path test proving the public completion function invokes `collect_runtime_evidence` against verified local sources and currently returns `supported=4`, `missing=151`, `extra=0`, `invalid=0`, and `complete=False`. Add focused audit tests proving that an empty source hash, missing adapter identity, or malformed mode-specific trace cannot produce a strict audit row even when operand values match.

- [ ] **Step 2: GREEN - implement the validator**

Implement a side-effect-free internal structural validator returning a structured coverage result. Implement the authoritative public completion function so it accepts registry entries and a cache root, calls `collect_runtime_evidence` itself, then validates the result; caller-supplied evidence must not be accepted by this public path. Add a raising assertion helper suitable for the final completion command. Every route must validate record identity, nonempty source hash, extraction trace, source/registry equality, comparison match, and, for recomputation, execution trace, nonempty adapter identity, computed/source equality, and three-way equality.

- [ ] **Step 3: Integrate the validator into audit diagnostics**

Add `runtime_evidence_coverage` to the audit result with sorted `supported_names`, `missing_names`, `extra_names`, `invalid_names`, integer counts, and `complete`. Render these diagnostics in the Markdown audit and remaining-gaps report without changing incomplete rows to strict. The production-path expected result is `supported=4`, `missing=151`, `extra=0`, `invalid=0`, and `complete=False`.

- [ ] **Step 4: Commit the completion gate and diagnostics**

Run:

```bash
git add scripts/validation/literature_runtime_evidence.py scripts/validation/literature_reproduction_audit.py tests/test_literature_runtime_evidence.py tests/test_literature_reproduction_audit.py
git commit -m "Add strict literature completion coverage gate"
```

### Task 5: Verify Phase 1 without overstating the 155/155 objective

**Files:**
- Read only: existing inventory and source cache
- Write only: temporary report paths during tests

- [ ] **Step 1: Run runtime, audit, inventory, source, and schema tests**

Run: `python -m pytest -q tests/test_literature_runtime_evidence.py tests/test_literature_reproduction_audit.py tests/test_literature_evidence_inventory.py tests/test_literature_evidence_sources.py tests/test_literature_evidence_schema.py`

- [ ] **Step 2: Run the offline source gate**

Run: `PYTHONPATH=scripts python scripts/validation/fetch_literature_evidence_sources.py --all --verify-offline`

Treat this only as source provenance evidence; never count it as benchmark reproduction.

- [ ] **Step 3: Rebuild inventory data in memory and compare every deterministic section**

Require exact equality for `contracts`, `records`, `source_index`, `source_provisioning`, and `locator_inventory`.

- [ ] **Step 4: Inspect strict counts and every strict row**

For each strict row, verify benchmark identity, source SHA, extraction trace, source operand, registry operand, comparison result, and, for recomputation, execution trace and computed operand.

- [ ] **Step 5: Record the exact Phase 1 endpoint and start the route-manifest plan**

Require exactly 4/155 strict rows in this phase and list their four names. The next plan must create a checked 155-entry route manifest with benchmark name, source ID/SHA/payload availability, evidence mode, source locator, parser, registry selector, adapter where applicable, comparison rule, tests, and status. It must separately plan acquisition and provenance registration for all blocked sources. The persistent project goal is complete only when the completion validator passes exact 155-name coverage, `strict_local_recomputed + strict_local_source_parsed == 155`, every non-strict category count is zero, and each strict row satisfies its mode-specific evidence rules.
