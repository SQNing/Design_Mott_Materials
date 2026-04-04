# Faithful Readable Hamiltonian Simplification Design

**Date:** 2026-04-03
**Status:** Approved in chat, pending user review of written spec
**Target:** `Design_Mott_Materials/translation-invariant-spin-model-simplifier`
**Design goal:** Upgrade the current simplification workflow from heuristic pruning into a semi-interactive, fidelity-aware pipeline that preserves physically relevant structure while presenting a human-readable effective Hamiltonian.

---

## 1. Overview

The current skill can normalize inputs, decompose local terms, and generate a few heuristic simplification candidates. That is useful for quick organization, but it is not yet a robust answer to the harder problem:

- preserve low-energy and symmetry-relevant physics as much as possible
- keep higher-body terms visible instead of hiding them behind an over-aggressive projection
- present the result in a form a physicist can read quickly
- stop and ask when ambiguity would materially change the interpretation

This redesign changes the core simplification philosophy.

Instead of asking the system to immediately drop or re-template terms, the new workflow first builds a lossless canonical representation, then extracts a readable main model, then separates lower-weight and unmatched terms into explicitly reported layers. The system remains semi-interactive throughout.

The default output model becomes:

```text
H = H_main + H_low_weight + H_residual
```

with a fidelity report that explains how trustworthy the readable summary is.

---

## 2. Goals And Non-Goals

### Goals

- Support translation-invariant spin Hamiltonians with two-body, three-body, and four-body local terms.
- Accept both structured lattice input and natural-language lattice descriptions.
- Automatically infer candidate symmetries from the lattice and Hamiltonian content.
- Require explicit user confirmation when ambiguity affects the simplification outcome.
- Preserve low-weight terms by default instead of deleting them automatically.
- Produce a readable effective model without pretending that all remaining structure has been fully absorbed into named templates.
- Report residual structure and fidelity indicators clearly.

### Non-Goals For The First Version

- Fully general natural-language understanding for arbitrary crystal descriptions.
- Exhaustive recognition of every possible three-body or four-body motif.
- Automatic small-cluster spectroscopy as a default part of every run.
- A universal external package dependency that solves symbolic simplification end-to-end.

---

## 3. User Experience

The user provides:

- a lattice description
- a Hamiltonian description
- optional symmetry hints or required symmetry constraints

The lattice description may be structured or written in controlled natural language. The system normalizes that information into a standard lattice object, then attempts to infer symmetry candidates. If anything remains ambiguous and the ambiguity could change term grouping, shell mapping, or simplification structure, the system returns:

```json
{
  "interaction": {
    "status": "needs_input",
    "question": "...",
    "options": ["..."]
  }
}
```

The system does not silently guess in such cases.

After confirmation, the system produces:

- a canonical model
- a readable main model
- a low-weight layer
- a residual layer
- a fidelity report
- 2-3 simplification views derived from the same underlying representation

The recommended default view is the most faithful readable one, not the shortest one.

---

## 4. Core Design Principles

### 4.1 No automatic deletion of low-weight terms

Small coefficients are not sufficient evidence that a term is physically irrelevant. A small term may:

- break a key symmetry
- lift a degeneracy
- control chirality or topology
- become important when larger contributions partially cancel

Therefore the system may identify low-weight terms, but it must not discard them automatically. It should surface them, explain why they were flagged, and let the user decide whether to:

- keep them in the main effective model
- demote them to `H_residual`
- explicitly drop them

The recommended default is to demote them to `H_residual` without deleting them.

### 4.2 Ambiguity requires confirmation

Whenever interpretation changes the result, the workflow stops and asks the user. This includes ambiguity in:

- lattice type
- shell mapping
- operator conventions
- symmetry status
- template classification
- low-weight term handling

### 4.3 Readability must remain honest

The system may produce a compact readable model, but only if it also keeps a visible record of what was not absorbed into that readable form. Readability must not come from pretending difficult terms do not exist.

### 4.4 Canonical form is the source of truth

All readable views are derived from a lossless canonical form. The readable model is a view over the canonical model, not a replacement for it.

---

## 5. Input Model

The redesigned workflow should normalize all raw input into a schema with separate lattice, Hamiltonian, and symmetry sections.

### 5.1 Required logical sections

- `system`
- `local_hilbert`
- `lattice_description`
- `hamiltonian_description`
- `symmetry_hints`
- `user_required_symmetries`
- `allowed_breaking`
- `timeouts`
- `user_notes`
- `provenance`

### 5.2 Lattice input

The lattice description should support two entry styles.

#### Structured lattice input

Examples of fields:

- lattice kind
- dimension
- cell parameters
- primitive vectors
- magnetic-site fractional coordinates
- sublattice labels
- shell map overrides

#### Natural-language lattice input

Examples:

- "2D triangular lattice with one spin per unit cell and nearest-neighbor J1, next-nearest-neighbor J2"
- "Honeycomb lattice, two magnetic sites per unit cell, first and second distance shells"

The first version should support a controlled subset of common lattices and common shell language, then return `needs_input` for unresolved cases.

### 5.3 Symmetry input

The workflow should distinguish:

- `detected_symmetries`
- `user_required_symmetries`
- `allowed_breaking`

This separation is important because the system may detect a likely symmetry, but the user may not wish to enforce it as an exact constraint on simplification.

---

## 6. High-Level Pipeline

The redesigned pipeline is:

1. `normalize_input`
2. `parse_lattice_description`
3. `infer_symmetry_candidates`
4. `confirm_symmetry_constraints`
5. `decompose_local_term`
6. `canonicalize_terms`
7. `identify_readable_blocks`
8. `assemble_effective_model`
9. `score_fidelity`
10. `generate_simplification_candidates`
11. `render_report`

This ordering matters.

- Lattice understanding must happen before symmetry reasoning.
- Symmetry confirmation must happen before term grouping decisions.
- Canonicalization must happen before readable extraction.
- Fidelity scoring must happen after the readable and residual layers are assembled.

---

## 7. Canonical Representation

The canonical model is the internal source of truth. It must preserve all information needed to reconstruct the supplied Hamiltonian within the supported basis.

### 7.1 Responsibilities

`canonicalize_terms` should:

- merge translation-equivalent terms
- merge Hermitian-conjugate-equivalent terms where appropriate
- normalize site ordering and operator ordering
- group terms by body order
- annotate support patterns and equivalence classes
- carry symmetry metadata
- compute weight metrics

### 7.2 Canonical organization

Terms should be grouped by:

- one-body
- two-body
- three-body
- four-body
- higher-body if future support is added

Each term entry should include at least:

- canonical label
- coefficient
- support
- body order
- equivalence-class metadata
- symmetry annotations
- absolute weight
- relative weight within its family

### 7.3 Design intent

This representation is not optimized for compact reading. It is optimized for correctness, traceability, and stable downstream extraction.

---

## 8. Readable Model Extraction

The readable model is the human-facing interpretation layer.

### 8.1 First-version readable blocks

The first version should support high-confidence extraction of:

- isotropic two-body exchange
- XXZ-like and anisotropic two-body exchange
- DM-like pair terms
- scalar-chirality-like three-body terms
- ring-exchange-like four-body terms
- generic residual clusters

### 8.2 Extraction behavior

`identify_readable_blocks` should:

- scan canonical terms
- assign terms to a supported readable block when the mapping is high confidence
- leave unmatched terms untouched rather than forcing a bad template match
- record which canonical terms contributed to each readable block

### 8.3 Honesty rule

If a three-body or four-body structure is not recognized with high confidence, it should remain generic. The system should prefer a generic but faithful classification over a misleading pretty name.

---

## 9. Effective Model Assembly

The effective output model is assembled into three visible layers:

- `H_main`
- `H_low_weight`
- `H_residual`

### 9.1 `H_main`

Contains the primary readable blocks that the system is confident are physically meaningful and human-readable.

### 9.2 `H_low_weight`

Contains terms that are retained but flagged for the user because their relative scale is small. They are not dropped automatically.

For each low-weight term, the report should include:

- coefficient
- relative scale
- body order
- whether it breaks a detected or required symmetry
- whether it has been retained in the readable view or demoted to residual

### 9.3 `H_residual`

Contains unmatched or user-demoted terms. This layer keeps the simplification honest.

---

## 10. Low-Weight Policy

Low-weight handling is a first-class design feature.

### 10.1 What low-weight means

Low weight may be defined relative to:

- the dominant absolute coupling scale
- the scale within the same body-order family
- the scale within the same readable block family

The exact metric can evolve, but the policy must not.

### 10.2 Policy

The workflow may flag low-weight terms, but it must not silently delete them.

The user should be offered three choices:

- retain in main or low-weight layer
- demote to residual
- explicitly drop

The recommended default is:

- demote to residual without deletion

### 10.3 Symmetry-sensitive warning

If a low-weight term is the only clear source of a symmetry breaking channel, the report must flag that prominently before asking whether to demote or drop it.

---

## 11. Symmetry Inference And Confirmation

Symmetry handling should become an explicit stage rather than a passive hint.

### 11.1 Automatically inferred candidates

The workflow should try to infer:

- translation invariance
- Hermiticity
- sublattice equivalence classes
- shell equivalence classes
- time-reversal status when detectable
- inversion or simple point-group candidates when supported
- spin-space candidates such as `SU(2)` or `U(1)` when recognizable

### 11.2 User confirmation

The user should then confirm:

- which symmetries are required to be preserved
- which suspected symmetries are only approximate
- which breaking channels are intentional and must remain visible

This confirmation should happen before readable extraction and low-weight handling decisions.

---

## 12. Ambiguity Handling

The redesign keeps the existing semi-interactive philosophy and extends it.

### 12.1 Cases that must return `needs_input`

- lattice language is ambiguous
- shell labels such as `J1/J2/J3` do not map unambiguously to geometry
- magnetic sites per unit cell are unclear
- operator conventions change classification
- the system cannot tell whether a symmetry is exact or approximate
- a high-order term has multiple plausible readable classifications
- a low-weight term might carry the only visible symmetry breaking signal

### 12.2 Interaction style

Only the most important next question should be asked at each stop. The system should not dump multiple unresolved issues at once.

---

## 13. Fidelity Report

The fidelity report tells the user how much trust to place in the readable simplification.

### 13.1 First-version metrics

The MVP report should include:

- operator-space or local-term reconstruction error
- main-model weight coverage
- low-weight fraction
- residual fraction
- symmetry preservation status
- generated risk notes

### 13.2 Risk note examples

- "The readable model captures the dominant two-body exchange, but a three-body chirality term remains visible in the residual layer."
- "Removing the flagged low-weight terms would restore a higher apparent symmetry and may change interpretation."
- "The current simplification is suitable for a readable summary but not yet for aggressive quantitative projection."

### 13.3 Future extensions

Later versions may add:

- representative classical-state energy comparison
- small-cluster low-energy spectrum comparison
- block-wise fidelity estimates

These are valuable, but not required for the first version.

---

## 14. Simplification Candidates

The system should still present 2-3 candidate views, but these are no longer different ad hoc pruning heuristics. They are views over the same effective decomposition.

### 14.1 Candidate set

- `faithful-readable`
  - `H_main + H_low_weight + H_residual`
- `readable-core`
  - `H_main + H_residual`
- `aggressive-minimal`
  - `H_main`

### 14.2 Recommendation

The recommended default candidate should be `faithful-readable`.

`aggressive-minimal` should never be treated as the implicit default. It must be clearly marked as a user-approved simplification choice.

---

## 15. Script And File Changes

The redesign should preserve the current repository structure as much as possible.

### 15.1 Keep and adapt

- `scripts/normalize_input.py`
- `scripts/decompose_local_term.py`
- `scripts/decision_gates.py`
- `scripts/render_report.py`
- `scripts/generate_simplifications.py`

### 15.2 Add

- `scripts/parse_lattice_description.py`
- `scripts/infer_symmetries.py`
- `scripts/canonicalize_terms.py`
- `scripts/identify_readable_blocks.py`
- `scripts/assemble_effective_model.py`
- `scripts/score_fidelity.py`

### 15.3 Responsibility changes

`generate_simplifications.py` should stop acting as a threshold-based pruning script and instead build the candidate views from the assembled effective model.

`render_report.py` should be upgraded to display:

- canonical model summary
- readable main model
- low-weight terms
- residual terms
- fidelity report
- candidate recommendation and whether the user enabled any aggressive simplification

---

## 16. MVP Scope

The first implementation should focus on correctness and honesty instead of broad coverage.

### 16.1 In scope for MVP

- structured lattice input
- controlled natural-language lattice input for common lattices
- basic symmetry inference and confirmation
- canonical term organization
- first-pass readable block extraction
- `main + low-weight + residual` assembly
- fidelity report with basic metrics
- `needs_input` handling for ambiguity

### 16.2 Out of scope for MVP

- exhaustive high-order block library
- default spectrum-based fidelity checks
- aggressive approximate symmetry discovery
- highly flexible free-form materials-language parsing

---

## 17. Future Extensions

After the MVP is stable, future work may include:

- stronger recognition of high-order motifs
- integration with `QuSpin` for optional small-cluster fidelity checks
- better use of `Sunny.jl` for pair-reducible readable blocks
- richer lattice language coverage
- more intelligent model-selection logic based on physical proxy observables rather than purely structural decomposition

---

## 18. Success Criteria

The redesign should be considered successful if the first version:

- does not silently guess when ambiguity matters
- does not silently discard low-weight terms
- can cleanly normalize supported lattice inputs
- can produce a traceable canonical form
- can separate a readable main model from residual structure
- can explain simplification quality in a way a user can act on

The target is not maximal compression. The target is a readable, defensible, fidelity-aware simplification workflow.
