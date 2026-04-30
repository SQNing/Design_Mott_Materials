# Skill Thinning And Agent Routing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the expert-facing `translation-invariant-spin-model-simplifier` skill into a thinner top-level `SKILL.md` plus a new `reference/agent-routing.md`, while preserving all currently supported repository capabilities and locking the new surface with lightweight doc-contract tests.

**Architecture:** Treat the skill refactor as a contract-preservation change rather than a feature removal. First add a focused regression test file that defines what the top-level skill must still guarantee, what routing detail must move into the new reference document, and what the reference index must expose. Then implement the split in two documentation slices: create the routing companion plus README entry, and only after that rewrite the top-level `SKILL.md` around the agreed five-section thin contract.

**Tech Stack:** Markdown documentation, Python 3, `pytest`, existing skill/reference files under `translation-invariant-spin-model-simplifier/`

---

## File Map

- `translation-invariant-spin-model-simplifier/SKILL.md`
  Top-level expert-facing capability contract. After the refactor, this should keep only overview,
  hard guarantees, weakly ordered workflow, output contract, and routing references.
- `translation-invariant-spin-model-simplifier/reference/agent-routing.md`
  New repository-specific routing decision guide covering input classes, agent-assisted landing,
  family resolution, backend routing, semantic conventions, and recommended entrypoints.
- `translation-invariant-spin-model-simplifier/reference/README.md`
  Index of required skill-facing reference documents. Must list the new routing companion so it is
  discoverable.
- `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`
  Lightweight regression tests that treat the skill and routing docs as a contract surface.

### Task 1: Lock the New Skill Surface with Failing Doc-Contract Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`

- [ ] **Step 1: Write the failing tests**

Add a focused test module that reads the docs as text and locks the intended split:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
ROUTING = ROOT / "reference" / "agent-routing.md"
README = ROOT / "reference" / "README.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_top_level_skill_keeps_core_guarantees_and_delegates_routing():
    text = _text(SKILL)
    assert "interaction.status = needs_input" in text
    assert "H_main + H_low_weight + H_residual" in text
    assert "reference/agent-routing.md" in text
    assert "normalize_document_with_agent.py" not in text
    assert "run_document_reader_pipeline.py" not in text
    assert "solve_cpn_payload_pipeline.py" not in text


def test_agent_routing_reference_covers_current_supported_routes():
    text = _text(ROUTING)
    for needle in [
        "Input Classes",
        "Routing By Input Class",
        "Agent-Assisted Landing",
        "Classical Family Resolution",
        "Backend And Solver Routing",
        "Current Semantic Conventions",
        "Recommended Entrypoints",
        "many_body_hr",
        "spin-only",
        "cpn",
        "agent_normalization_request",
        "agent_normalized_document",
        "sunny-cpn-minimize",
        "cpn-generalized-lt",
    ]:
        assert needle in text


def test_reference_readme_lists_agent_routing_reference():
    text = _text(README)
    assert "agent-routing.md" in text
```

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```bash
python3 -m pytest translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py -q
```

Expected: FAIL because `reference/agent-routing.md` does not exist yet, `reference/README.md`
does not list it, and the current top-level `SKILL.md` still contains repo-specific entrypoint
details that the new test forbids.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add \
  translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py \
git add -f \
  translation-invariant-spin-model-simplifier/docs/superpowers/plans/2026-04-30-skill-thinning-and-agent-routing.md
git commit -m "test: lock skill surface doc split"
```

### Task 2: Create the Routing Companion and Expose It in the Reference Index

**Files:**
- Create: `translation-invariant-spin-model-simplifier/reference/agent-routing.md`
- Modify: `translation-invariant-spin-model-simplifier/reference/README.md`
- Test: `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`

- [ ] **Step 1: Draft the routing companion with the agreed section structure**

Create `reference/agent-routing.md` with the agreed decision-oriented headings and concise routing
content:

```markdown
# Agent Routing for `translation-invariant-spin-model-simplifier`

## Input Classes
- operator expressions
- local matrices or tensors
- structured lattice or model inputs
- natural-language or document-style inputs
- `many_body_hr`
- already landed payloads

## Routing By Input Class
...

## Agent-Assisted Landing
- `agent_normalization_request`
- `agent_normalized_document`
...

## Classical Family Resolution
- `spin-only`
- `cpn`
...

## Backend And Solver Routing
- `sunny-cpn-minimize`
- `cpn-generalized-lt`
...

## Current Semantic Conventions
...

## Recommended Entrypoints
...

## Related References
...
```

The initial content should be concise but must cover every capability area listed in the approved
spec. Do not re-copy full protocol text from the existing reference documents.

- [ ] **Step 2: Update the reference index**

Modify `reference/README.md` so the retained reference list includes the new routing document and
briefly explains that it is the current decision guide for skill-facing route selection.

- [ ] **Step 3: Run the targeted tests to verify partial GREEN**

Run:

```bash
python3 -m pytest translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py -q
```

Expected: the routing-reference and README checks pass, but the top-level `SKILL.md` check still
fails because the old monolithic skill text has not yet been thinned.

- [ ] **Step 4: Commit the routing companion slice**

```bash
git add \
  translation-invariant-spin-model-simplifier/reference/agent-routing.md \
  translation-invariant-spin-model-simplifier/reference/README.md \
  translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py
git commit -m "docs: add agent routing reference for skill"
```

### Task 3: Rewrite the Top-Level `SKILL.md` Around the Thin Contract

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/SKILL.md`
- Test: `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`

- [ ] **Step 1: Replace the long implementation-heavy workflow with the thin five-section shape**

Restructure the file so it contains:

```markdown
# Translation-Invariant Spin Model Simplifier

## Overview
...

## Core Guarantees
...

## Workflow
1. identify the input route
2. check environment and execution constraints
3. land the input into a trusted normalized form
4. resolve material ambiguity before simplification
5. build the readable effective model
6. run optional downstream analysis when appropriate
7. report assumptions, limits, choices, and recommendations

## Output Contract
...

## Routing References
...
```

- [ ] **Step 2: Preserve the hard guarantees while deleting repo-specific entrypoint sprawl**

Keep explicit statements for:

- `interaction.status = needs_input`
- `H_main + H_low_weight + H_residual`
- early environment blocker surfacing
- no silent replacement of required Sunny-backed paths
- residual-first honesty over fake simplification

Remove the long list of specific scripts, flags, wrapper CLIs, and current route-specific semantic
notes that now belong in `reference/agent-routing.md`.

- [ ] **Step 3: Wire the thin skill back to the detailed references**

Make `Routing References` point to:

- `reference/agent-routing.md`
- `reference/input-schema.md`
- `reference/natural-language-input-protocol.md`
- `reference/fallback-rules.md`
- `reference/environment.md`

- [ ] **Step 4: Re-run the doc-contract tests to verify GREEN**

Run:

```bash
python3 -m pytest translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the thinned top-level skill**

```bash
git add \
  translation-invariant-spin-model-simplifier/SKILL.md \
  translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py
git commit -m "docs: thin skill and delegate routing detail"
```

### Task 4: Verification Sweep and Expert-Flow Sanity Check

**Files:**
- Modify: none expected
- Test: `translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py`
- Reference: `translation-invariant-spin-model-simplifier/docs/test-reports/translation-invariant-spin-model-simplifier-20260411-170348.md`

- [ ] **Step 1: Re-run the doc-contract regression test**

Run:

```bash
python3 -m pytest translation-invariant-spin-model-simplifier/tests/test_skill_surface_docs.py -q
```

Expected: PASS

- [ ] **Step 2: Run a grep-based sanity check that the top-level skill no longer owns routing trivia**

Run:

```bash
rg -n "normalize_document_with_agent.py|run_document_reader_pipeline.py|solve_cpn_payload_pipeline.py|sunny-cpn-minimize" \
  translation-invariant-spin-model-simplifier/SKILL.md
```

Expected: no matches

- [ ] **Step 3: Compare the new docs against the previously exercised expert flow**

Read the earlier expert-flow rerun report at:

`translation-invariant-spin-model-simplifier/docs/test-reports/translation-invariant-spin-model-simplifier-20260411-170348.md`

Confirm the new split still leaves the following concepts discoverable:

- ambiguity handling and `needs_input`
- visible low-weight and residual terms
- solver recommendation / backend explanation
- document-agent handoff concepts
- retained `spin-only` and `cpn` family routing

- [ ] **Step 4: If the harness supports workspace skill testing, rerun one skill-level scenario**

Use the same ambiguous natural-language plus weak-anisotropy expert use case from the earlier test
reports and verify that the thinner top-level skill plus routing companion still give a coherent
entry story.

If the harness cannot run workspace skill testing safely in this session, explicitly record that as
a verification gap instead of improvising a fake pass.

- [ ] **Step 5: Check whether verification triggered a wording fix**

```bash
git status --short
```

Expected: no further changes, unless a small wording fix was needed during the verification readback.

If a wording fix was needed, commit it explicitly:

```bash
git add \
  translation-invariant-spin-model-simplifier/SKILL.md \
  translation-invariant-spin-model-simplifier/reference/agent-routing.md \
  translation-invariant-spin-model-simplifier/reference/README.md
git commit -m "docs: polish skill routing references"
```

- [ ] **Step 6: Summarize residual risk**

Document any remaining gap, especially if the routing companion still feels too close to a copied
runbook or if the new top-level skill became so thin that an expert agent would miss a critical
constraint.
