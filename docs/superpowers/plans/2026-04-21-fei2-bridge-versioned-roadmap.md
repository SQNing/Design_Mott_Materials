# FeI2 Bridge Versioned Roadmap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the FeI2 document-reader-to-solver work into explicit versions so V1 lands a narrow, verifiable bridge while V2 and V3 expand scope without destabilizing the first end-to-end success path.

**Architecture:** Treat the bridge as a staged contract rollout. V1 introduces a minimal selected-family spin-only bridge for one deterministic classical smoke path, V2 expands that same spin-only contract to full shell expansion and downstream stages, and V3 handles broader model classes that do not naturally collapse to the same `3x3` bond-matrix interface.

**Tech Stack:** Python 3, document-reader CLI, readable exchange simplification layer, classical solver layer, downstream routing layer, `unittest`/`pytest`

---

## Version Summary

### Version 1: Minimal FeI2 Spin-Only Bridge

**Purpose:** Replace manual FeI2 payload assembly with a reproducible bridge from a selected readable spin-only exchange block to a solver-ready minimal classical payload.

**Must ship in V1:**

- bridge one selected family only
- support spin-only readable bilinear block types already rich enough to become a `3x3` exchange matrix
- emit a deterministic minimal representative bond
- optionally run the classical solver and save artifacts
- keep the base document-reader simplification path unchanged by default

**Must not slip into V1:**

- full symmetry-equivalent bond expansion
- `selected_local_bond_family="all"`
- automatic LSWT / GSWT / thermodynamics chaining
- residual / multipolar / mixed spin-orbital bridge generalization

**Acceptance bar for V1:**

- FeI2 `2a'` can go from document-reader output to `classical/solver_payload.json` automatically
- the same run can optionally produce `classical/solver_result.json`
- targeted tests prove the bridge behavior and failure modes
- the real FeI2 fixture reproduces the current classical smoke success without hand-built payloads

### Version 2: Full Spin-Only Workflow Expansion

**Purpose:** Generalize the V1 spin-only bridge so supported readable spin-only models can be promoted from selected blocks into fuller solver and downstream workflows.

**Planned scope for V2:**

- full symmetry-equivalent bond expansion for a supported shell
- `selected_local_bond_family="all"` multi-shell assembly
- preservation of shell provenance and aggregation semantics
- downstream chaining for spin-only classical result consumers:
  - LSWT
  - GSWT where the current routing contract truly permits it
  - thermodynamics where the current routing contract truly permits it

**Acceptance bar for V2:**

- a supported FeI2 run can build a full shell-expanded spin-only model
- `selected_local_bond_family="all"` yields a stable combined payload for supported readable blocks
- downstream stages are auto-routed with explicit `ready` / `blocked` / `review` semantics
- tests clearly separate bridge failures from downstream-stage failures

### Version 3: Broader Model-Class Bridge Generalization

**Purpose:** Design and implement bridge contracts for model content that should not be forced into the same spin-only bilinear schema as V1/V2.

**Planned scope for V3:**

- residual-term handling policy
- multipolar coupling bridge design
- mixed spin-orbital and other non-spin-only bridge contracts
- explicit decisions on which model classes are bridgeable, partially bridgeable, or intentionally unsupported

**Acceptance bar for V3:**

- each new model class has its own explicit bridge contract or explicit rejection contract
- no broader model class is silently downcast into an incorrect spin-only bond matrix
- tests cover both successful promotion and principled rejection

## Why The Split Exists

- V1 is about proving that the missing FeI2 bridge can be automated at all.
- V2 is about broadening the same spin-only contract once V1 is stable.
- V3 is about different physics and therefore different contracts, not just “more cases.”

This split is intentional YAGNI. It protects the first real end-to-end bridge from being delayed by broader modeling questions.

## File Map

**Roadmap / Planning**

- Create: `docs/superpowers/plans/2026-04-21-fei2-bridge-versioned-roadmap.md`
- Read: `docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

**V1 Implementation Files**

- Create: `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- Create: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- Modify: `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

## Task 1: Write The Versioned Roadmap

**Files:**
- Create: `docs/superpowers/plans/2026-04-21-fei2-bridge-versioned-roadmap.md`
- Read: `docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

- [ ] **Step 1: Record V1, V2, and V3 boundaries**

Write down:

- V1 scope and explicit non-goals
- V2 scope as the spin-only expansion stage
- V3 scope as the broader model-class bridge stage

- [ ] **Step 2: Link V1 execution to the existing detailed plan**

State clearly that V1 execution follows:

`docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

- [ ] **Step 3: Verify the roadmap reads as staged contracts, not a wish list**

Run:

```bash
sed -n '1,260p' docs/superpowers/plans/2026-04-21-fei2-bridge-versioned-roadmap.md
```

Expected: the document cleanly states what belongs to each version and what V1 explicitly excludes.

## Task 2: Execute Version 1 Only

**Files:**
- Read: `docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

- [ ] **Step 1: Treat the existing detailed bridge plan as the V1 execution plan**

Execute only the V1 plan at:

`docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

- [ ] **Step 2: Reject V2/V3 scope creep during implementation**

If implementation pressure appears to require:

- full shell expansion
- multi-shell `all`
- downstream chaining beyond optional classical solving
- broader model-class promotion

stop and record it as V2/V3 follow-on work rather than expanding V1.

- [ ] **Step 3: Verify V1 against V1 acceptance criteria only**

Before claiming progress, verify only these V1 outcomes:

- deterministic minimal solver payload emission
- optional classical solver result emission
- targeted tests passing
- real FeI2 smoke reproduction

Do not block V1 completion on V2/V3 functionality.

## Task 3: Prepare The Handoff To Version 2

**Files:**
- Modify later: `docs/superpowers/specs/...` or `docs/superpowers/plans/...` for V2

- [ ] **Step 1: Record V2 follow-on questions discovered during V1**

Capture questions like:

- shell multiplicity semantics
- all-family aggregation rules
- downstream-stage gating mismatches

- [ ] **Step 2: Keep V3 questions separate from V2**

Anything involving residual, multipolar, or mixed spin-orbital content should be recorded under V3 notes, not folded into V2.

## Immediate Execution Handoff

V1 should be executed now using:

- roadmap file: `docs/superpowers/plans/2026-04-21-fei2-bridge-versioned-roadmap.md`
- detailed V1 file: `docs/superpowers/plans/2026-04-21-fei2-document-reader-classical-bridge.md`

The active implementation target is V1 only.
