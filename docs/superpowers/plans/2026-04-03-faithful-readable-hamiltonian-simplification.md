# Faithful Readable Hamiltonian Simplification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the spin-model simplification pipeline so it accepts richer lattice input, asks for clarification when ambiguity matters, preserves low-weight terms by default, and emits `H_main + H_low_weight + H_residual` with a basic fidelity report.

**Architecture:** Keep the current Python script pipeline and unit-test style, but insert new intermediate stages for lattice parsing, symmetry inference, canonical term organization, readable-block extraction, effective-model assembly, and fidelity scoring. Treat canonical form as the internal truth, then generate user-facing candidate views from that assembled effective model instead of pruning terms directly.

**Tech Stack:** Python 3, `unittest`, JSON CLI scripts under `translation-invariant-spin-model-simplifier/scripts`, existing test layout under `translation-invariant-spin-model-simplifier/tests`

---

## File Structure

### Existing files to modify

- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/normalize_input.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/generate_simplifications.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_report.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_normalize_input.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generate_simplifications.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_render_report.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py`

### New files to create

- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/parse_lattice_description.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/infer_symmetries.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/canonicalize_terms.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/identify_readable_blocks.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/assemble_effective_model.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/score_fidelity.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_parse_lattice_description.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_infer_symmetries.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_canonicalize_terms.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_identify_readable_blocks.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_assemble_effective_model.py`
- `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_score_fidelity.py`

### Responsibility map

- `normalize_input.py`: normalize top-level schema and route lattice input into a standard description payload.
- `parse_lattice_description.py`: parse structured and controlled natural-language lattice descriptions into a canonical lattice object or return `needs_input`.
- `infer_symmetries.py`: infer candidate symmetries and identify user confirmation requirements.
- `canonicalize_terms.py`: normalize decomposed terms into body-order-aware canonical form with weight metadata.
- `identify_readable_blocks.py`: group canonical terms into high-confidence readable blocks.
- `assemble_effective_model.py`: split readable content into `main`, `low_weight`, and `residual`.
- `score_fidelity.py`: compute reconstruction and coverage metrics plus human-readable warnings.
- `generate_simplifications.py`: generate candidate views from the effective model rather than raw threshold pruning.
- `render_report.py`: render the new decomposition and fidelity sections.

---

## Chunk 1: Input Schema, Lattice Parsing, And Ambiguity Gates

### Task 1: Extend input normalization for lattice and symmetry fields

**Files:**
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/normalize_input.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_normalize_input.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering:
- structured `lattice_description`
- natural-language `lattice_description`
- `user_required_symmetries`
- `allowed_breaking`
- pass-through of unresolved interaction metadata

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_normalize_input -v`

Expected: FAIL because the normalized payload does not yet preserve the new schema sections.

- [ ] **Step 3: Write the minimal implementation**

Update `normalize_input.py` so the normalized output always contains:
- `lattice_description`
- `hamiltonian_description`
- `symmetry_hints`
- `user_required_symmetries`
- `allowed_breaking`

Retain backward compatibility with current payloads by deriving `hamiltonian_description` from the old representation fields when needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_normalize_input -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/normalize_input.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_normalize_input.py
git commit -m "feat: normalize lattice and symmetry input schema"
```

### Task 2: Implement lattice parsing with controlled ambiguity handling

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/parse_lattice_description.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_parse_lattice_description.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- structured square or triangular lattice parsing
- controlled natural-language honeycomb or triangular lattice parsing
- unresolved ambiguous input returning `interaction.status = needs_input`

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_parse_lattice_description -v`

Expected: FAIL because the parser module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement a parser that:
- accepts both structured and natural-language lattice input
- normalizes common lattice kinds into a standard object
- records magnetic-site count, shell language, and user notes when available
- returns a `needs_input` interaction object instead of guessing on ambiguous phrases

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_parse_lattice_description -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/parse_lattice_description.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_parse_lattice_description.py
git commit -m "feat: parse lattice descriptions with ambiguity gates"
```

### Task 3: Infer symmetry candidates and prompt for confirmation when needed

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/infer_symmetries.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_infer_symmetries.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- exact detection of always-available structural symmetries such as translation and Hermiticity
- detection of likely spin-space symmetry from simple XXZ-like or isotropic terms
- escalation to `needs_input` when the inferred symmetry status is materially ambiguous

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_infer_symmetries -v`

Expected: FAIL because the inference module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- a symmetry inference helper returning `detected_symmetries`
- a comparison against `user_required_symmetries` and `allowed_breaking`
- a single-question `needs_input` output when confirmation is required before simplification proceeds

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_infer_symmetries -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/infer_symmetries.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_infer_symmetries.py
git commit -m "feat: infer and confirm symmetry constraints"
```

---

## Chunk 2: Canonical Form And Readable Block Extraction

### Task 4: Build canonical term organization with body-order and weight metadata

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/canonicalize_terms.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_canonicalize_terms.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- grouping into one-body, two-body, three-body, and four-body buckets
- normalized support ordering
- equivalent-label merging
- relative-weight computation inside each body-order family

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_canonicalize_terms -v`

Expected: FAIL because the canonicalization module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement a canonicalization layer that consumes decomposition output and emits:
- grouped canonical terms
- per-term support and body order
- family-relative weights
- symmetry metadata placeholders for later refinement

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_canonicalize_terms -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/canonicalize_terms.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_canonicalize_terms.py
git commit -m "feat: add canonical term organization"
```

### Task 5: Extract high-confidence readable blocks without forcing weak matches

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/identify_readable_blocks.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_identify_readable_blocks.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- isotropic exchange recognition
- XXZ-like anisotropy recognition
- DM-like pair term recognition
- scalar-chirality-like three-body recognition
- fallback of unmatched terms into generic buckets

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_identify_readable_blocks -v`

Expected: FAIL because the readable-block module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement block identification that:
- consumes canonical terms
- emits readable blocks plus references to source canonical terms
- leaves uncertain high-order terms unmatched instead of forcing a template

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_identify_readable_blocks -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/identify_readable_blocks.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_identify_readable_blocks.py
git commit -m "feat: extract readable interaction blocks"
```

---

## Chunk 3: Effective Model Assembly, Candidate Views, And Fidelity Report

### Task 6: Assemble `main`, `low_weight`, and `residual` layers

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/assemble_effective_model.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_assemble_effective_model.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- assignment of readable blocks to `main`
- flagging of low-weight terms without dropping them
- demotion of unmatched terms to `residual`
- symmetry-sensitive warnings for low-weight symmetry-breaking terms

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_assemble_effective_model -v`

Expected: FAIL because the assembly module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement assembly rules that:
- create `H_main`, `H_low_weight`, and `H_residual`
- preserve explicit records of user-decision-needed low-weight terms
- attach warning metadata when a low-weight term is the only visible source of symmetry breaking

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_assemble_effective_model -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/assemble_effective_model.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_assemble_effective_model.py
git commit -m "feat: assemble main low-weight and residual models"
```

### Task 7: Compute fidelity metrics and human-readable risk notes

**Files:**
- Create: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/score_fidelity.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_score_fidelity.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- reconstruction error calculation
- main-model coverage fraction
- low-weight and residual fractions
- risk-note emission for symmetry-sensitive demotions

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_score_fidelity -v`

Expected: FAIL because the fidelity module does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement a scorer that emits:
- reconstruction metrics
- coverage metrics
- symmetry preservation summary
- textual risk notes intended for report rendering

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_score_fidelity -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/score_fidelity.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_score_fidelity.py
git commit -m "feat: add effective-model fidelity scoring"
```

### Task 8: Replace pruning-based candidate generation with view generation

**Files:**
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/generate_simplifications.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generate_simplifications.py`

- [ ] **Step 1: Write the failing tests**

Update tests to assert:
- candidate generation uses effective-model layers
- `faithful-readable` is recommended by default
- low-weight terms are never silently dropped
- aggressive minimal mode requires explicit selection

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_generate_simplifications -v`

Expected: FAIL because the current implementation still produces threshold-pruned candidates.

- [ ] **Step 3: Write the minimal implementation**

Refactor candidate generation so it emits:
- `faithful-readable`
- `readable-core`
- `aggressive-minimal`

Base all three on the assembled effective model and preserve explicit metadata about whether a user allowed any aggressive simplification.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_generate_simplifications -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/generate_simplifications.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_generate_simplifications.py
git commit -m "feat: generate layered simplification views"
```

### Task 9: Render the new effective-model and fidelity sections

**Files:**
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_report.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_render_report.py`

- [ ] **Step 1: Write the failing tests**

Add assertions for report sections covering:
- canonical model summary
- readable main model
- low-weight terms
- residual terms
- fidelity metrics
- recommendation and user-choice status

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_render_report -v`

Expected: FAIL because the report renderer does not yet show the new sections.

- [ ] **Step 3: Write the minimal implementation**

Update the report renderer to:
- summarize canonical structure by body order
- print readable blocks and residual layers separately
- include warnings for symmetry-sensitive low-weight terms
- report the recommended candidate and whether aggressive simplification was user-approved

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_render_report -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/render_report.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_render_report.py
git commit -m "feat: render layered effective-model reports"
```

---

## Chunk 4: Pipeline Integration, Downstream Compatibility, And Documentation

### Task 10: Thread the new effective model through downstream drivers without changing solver scope

**Files:**
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py`
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py`
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py`

- [ ] **Step 1: Write the failing tests**

Add tests showing that downstream drivers:
- prefer `effective_model.main` when present
- can still fall back to legacy simplified-model structures for backward compatibility
- do not consume `aggressive-minimal` unless the user explicitly selected it

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_classical_solver_driver Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_linear_spin_wave_driver -v`

Expected: FAIL because the drivers currently only know the old simplification shape.

- [ ] **Step 3: Write the minimal implementation**

Update both drivers so they can read the new layered effective model while preserving current solver limitations and existing fallbacks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_classical_solver_driver Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_linear_spin_wave_driver -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/linear_spin_wave_driver.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_linear_spin_wave_driver.py
git commit -m "feat: feed layered effective models into downstream solvers"
```

### Task 11: Update the skill instructions to match the new semi-interactive workflow

**Files:**
- Modify: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`

- [ ] **Step 1: Write the failing documentation check**

Manually compare the spec and `SKILL.md`, then list the mismatches:
- missing lattice parsing stage
- missing symmetry confirmation stage
- obsolete pruning language
- missing `main + low_weight + residual` output contract

- [ ] **Step 2: Verify the mismatch exists**

Run: `rg -n "prune|Generate 2-3 simplification candidates|decision gates|dropped terms" Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`

Expected: Existing lines reflect the older pruning-oriented workflow.

- [ ] **Step 3: Write the minimal documentation update**

Update `SKILL.md` so it:
- describes the new pipeline stages
- makes user confirmation mandatory for ambiguity and low-weight handling
- updates output requirements to include canonical, readable, low-weight, residual, and fidelity reporting

- [ ] **Step 4: Verify the updated documentation**

Run: `sed -n '1,260p' Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`

Expected: The skill reflects the implemented workflow and no longer implies automatic pruning.

- [ ] **Step 5: Commit**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md
git commit -m "docs: align skill workflow with layered simplification design"
```

### Task 12: Run the focused test suite and a full regression pass

**Files:**
- Test: `Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/`

- [ ] **Step 1: Run focused new-module tests**

Run:
```bash
python -m unittest \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_parse_lattice_description \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_infer_symmetries \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_canonicalize_terms \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_identify_readable_blocks \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_assemble_effective_model \
  Design_Mott_Materials.translation-invariant-spin-model-simplifier.tests.test_score_fidelity -v
```

Expected: PASS

- [ ] **Step 2: Run the full skill test suite**

Run:
```bash
python -m unittest discover -s Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests -v
```

Expected: PASS

- [ ] **Step 3: Record any intentional compatibility notes**

Update implementation notes or commit message text if:
- old payload shapes are still accepted with translation
- some advanced high-order motifs remain generic by design

- [ ] **Step 4: Commit the final integration state**

```bash
git add Design_Mott_Materials/translation-invariant-spin-model-simplifier
git commit -m "feat: add faithful readable Hamiltonian simplification pipeline"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-03-faithful-readable-hamiltonian-simplification.md`. Ready to execute?
