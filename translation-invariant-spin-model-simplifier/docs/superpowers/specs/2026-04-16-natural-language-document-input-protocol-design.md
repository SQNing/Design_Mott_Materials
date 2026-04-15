# Natural-Language Document Input Protocol Design

**Date:** 2026-04-16

## Goal

Extend the `translation-invariant-spin-model-simplifier` skill so that natural-language, LaTeX,
and document-style inputs such as partial or full `.tex` files are handled through an explicit,
fidelity-aware extraction protocol rather than ad hoc agent judgment.

The design should preserve the current downstream simplifier pipeline while introducing a stable
upstream contract for broader document understanding.

## User-Approved Direction

- Treat natural-language, LaTeX, and whole-document inputs as first-class inputs.
- Add a new reference document under `reference/` rather than creating a second independent skill.
- Keep the current top-level skill as the single entrypoint.
- Define both an input/extraction schema and a processing workflow.
- Support a two-stage result:
  - a faithful intermediate extraction record for broad input coverage,
  - a landing path into the current runnable payloads when the extracted information is sufficient.
- Prefer explicit `needs_input` gates over silent guessing when a document contains ambiguity that
  would materially change the resulting spin model.

## Problem Statement

The current skill text claims support for natural-language spin-model descriptions, but the actual
runtime support is much narrower:

- `scripts/input/normalize_input.py` can wrap freeform text into a normalized payload.
- `scripts/input/parse_lattice_description.py` and
  `scripts/input/natural_language_parser.py` only support shallow controlled-language extraction
  for a limited set of lattice keywords and shell-mapping phrases.
- `scripts/simplify/decompose_local_term.py` does not convert document-style natural-language or
  LaTeX input into the canonical term structure used by the downstream simplifier stages.

This creates a mismatch between the advertised support surface and the real executable pipeline.
For broad inputs such as a paper-derived `.tex` file, the current system can often detect that
there is a model present, but it cannot reliably and transparently turn that document into a
structured Hamiltonian that the existing simplifier, classical, and LSWT tooling can consume.

## Approaches Considered

### 1. Expand the current Python scripts into a full document parser

Broaden the rule-based parsing logic so the Python scripts themselves parse most natural-language,
LaTeX, and paper-style inputs directly into runnable payloads.

Pros:

- strong determinism,
- good CLI ergonomics once complete,
- maximal script-level reproducibility.

Cons:

- very high implementation cost,
- brittle for broad paper-style inputs,
- difficult to grow quickly without a large rule explosion,
- forces the scripts to solve document understanding and physics extraction at the same time.

### 2. Use agent-only extraction with minimal protocol changes

Rely on the agent to interpret natural-language and document-style inputs and directly emit runnable
payloads, with the scripts largely unchanged.

Pros:

- broadest short-term coverage,
- fastest way to handle new document formats such as `.tex`.

Cons:

- weak repeatability,
- poor testability,
- inconsistent output structure over time,
- higher risk of silent drift between extracted meaning and runnable payload.

### 3. Hybrid protocol: agent-guided extraction plus strict structured landing

Add a new reference protocol for document-style inputs. The agent must first produce a structured
intermediate extraction record, then either:

- land that record into a currently supported runnable payload, or
- stop with `interaction.status = needs_input` if a faithful landing is not yet possible.

Pros:

- broad input coverage,
- maintains explicit structure and auditability,
- compatible with the current downstream pipeline,
- gives future scripts a stable contract to validate and automate against,
- allows partial success without pretending unsupported parts were solved.

Cons:

- requires a more detailed contract than a lightweight skill-only tweak,
- introduces a new intermediate artifact that must be documented carefully.

## Recommended Design

Use approach 3.

The skill should continue to be the single top-level entrypoint, but natural-language, LaTeX, and
document-style inputs must be routed through a new reference protocol before ordinary normalization
and simplification proceed.

The protocol should define:

- supported input classes,
- a document-aware extraction workflow,
- a stable intermediate schema,
- explicit landing rules into current payloads,
- mandatory `needs_input` gates,
- transparency requirements for unsupported or partially landed features.

## New Reference Artifact

Add:

- `reference/natural-language-input-protocol.md`

This document is a skill-facing protocol, not a generic user guide. Its purpose is to instruct the
agent how to convert broad textual inputs into a structured extraction record and then into the
current simplifier payloads when possible.

The existing `reference/input-schema.md` remains the contract for normalized runnable payloads.
The new protocol sits upstream of that schema.

## Supported Input Scope

The new protocol should treat the following as first-class inputs:

- freeform natural-language model descriptions,
- natural-language plus short operator expressions,
- LaTeX formula fragments,
- mixed prose plus LaTeX mathematics,
- partial or full `.tex` documents,
- paper-style inputs containing structure sections, Hamiltonian sections, and parameter tables.

The protocol should explicitly state that it does not promise full automatic support for:

- OCR-corrupted scanned PDFs,
- equations embedded only as images,
- extremely ambiguous multi-model papers without user disambiguation,
- arbitrary prose that never names a concrete Hamiltonian or lattice.

## Intermediate Extraction Schema

The protocol should define a structured intermediate record with at least these sections:

- `source_document`
  - input path or inline source
  - source kind such as `natural_language`, `latex_fragment`, `tex_document`
  - extracted spans or section identifiers
- `document_sections`
  - structure-related passages
  - Hamiltonian-related passages
  - parameter tables
  - analysis or ordered-state notes
- `model_candidates`
  - named model candidates such as `toy`, `effective`, `matrix_form`
  - source spans for each candidate
  - candidate role such as `main`, `simplified`, `equivalent_form`
- `system_context`
  - material/system name
  - local Hilbert-space hints
  - space group
  - lattice constants
  - magnetic ion information
- `lattice_model`
  - magnetic lattice kind
  - magnetic basis / site count
  - shell labels or explicit bond families
  - bond-direction metadata when available
- `hamiltonian_model`
  - one-body terms
  - two-body terms
  - higher-body terms
  - bond-dependent phase or direction conventions
  - original symbolic form plus normalized extracted form
- `parameter_registry`
  - parameter names
  - numerical values
  - units
  - uncertainties
  - source table/equation locations
- `ambiguities`
  - unresolved choices that affect the physical model
  - whether each ambiguity blocks landing
- `confidence_report`
  - direct extraction vs inferred binding
  - confidence or provenance tags for each major block
- `unsupported_features`
  - extracted content that current payloads cannot faithfully represent yet

## Landing Rules

The protocol should define a two-step landing policy:

1. Extract into the intermediate record first.
2. Only then decide whether the result can be translated into a currently supported runnable
   payload.

Landing targets remain the existing payload families:

- `operator`
- `matrix`
- `many_body_hr`

Landing rules:

- Generate a runnable payload only if the intermediate record contains a unique, internally
  consistent model interpretation.
- Preserve unsupported or only partially representable features in `unsupported_features`,
  `user_notes`, or explicit residual annotations rather than silently dropping them.
- When the document contains multiple model candidates, do not merge them by default.
- When a user has explicitly selected a model candidate, only that candidate should proceed to the
  landing stage.
- If the extracted model cannot be faithfully represented by the current payload families, return
  `interaction.status = needs_input` or stop with an explicit unsupported-feature report.

## `needs_input` Gates

The protocol should define mandatory stop conditions. The skill must not continue silently if any
of these are unresolved and materially affect the final result:

- multiple competing Hamiltonians are present and the user has not selected one,
- lattice interpretation is ambiguous,
- exchange labels may correspond either to distance shells or named exchange paths,
- parameter tables conflict with formula definitions,
- a missing parameter component would change the physical conclusion if guessed,
- bond-dependent phases or direction conventions are not sufficiently defined,
- an equivalent matrix form disagrees with the main Hamiltonian form,
- the user requests numerical solving but only symbolic parameters are available,
- the extracted content exceeds what current payload families can represent.

The protocol should favor faithful incompleteness over false completeness.

## Agent Extraction Procedure

The protocol should prescribe the following workflow for broad text or document inputs:

1. Identify input kind.
2. For `.tex` or paper-style inputs, segment the document into semantically meaningful blocks.
3. Extract structure, lattice, and magnetic-site context from the structure-related blocks.
4. Extract all Hamiltonian candidates from equation and model-description blocks.
5. Bind parameters from tables, inline definitions, and uncertainty statements.
6. Record equivalent representations as linked supporting evidence, not silent replacements.
7. Build the intermediate extraction record.
8. Evaluate whether landing to a current payload is uniquely possible.
9. If landing is possible, generate the runnable payload and carry unsupported features forward.
10. If landing is not possible, return `interaction.status = needs_input` with one focused
    blocking question.

## Example Expectations

The protocol document should include at least:

- one short controlled natural-language example,
- one document-style example modeled after a paper-like `.tex` source containing:
  - a structure section,
  - multiple Hamiltonian candidates,
  - parameter tables,
  - an ordered-state note.

The document-style example should show how to:

- preserve multiple model candidates,
- select the user-approved candidate,
- bind parameters,
- expose residual ambiguity rather than silently collapsing it.

## Minimal Changes To The Main Skill

Update `SKILL.md` with minimal but explicit workflow changes:

- In the workflow, before ordinary normalization, add a rule that natural-language, LaTeX, and
  document-style inputs must first read `reference/natural-language-input-protocol.md` and produce
  an intermediate extraction record.
- In the input notes, replace the current narrow wording about controlled natural-language support
  with a broader note that these inputs are supported through the new protocol.
- Add a hard rule that the skill must not claim document-style natural-language input has been
  converted into a runnable model unless:
  - the intermediate record landed in a supported payload, or
  - the skill explicitly returned `interaction.status = needs_input`.
- Keep the current ambiguity-first stance and make it stronger for broad document inputs.

## Non-Goals

- Do not replace the existing `reference/input-schema.md`.
- Do not promise that every broad natural-language or LaTeX document becomes a runnable payload in
  one pass.
- Do not rewrite the downstream simplifier, classical solver, or LSWT stack in this design slice.
- Do not force broad document understanding into the existing shallow parser without an intermediate
  representation.

## Testing Strategy

The eventual implementation should be testable in three layers:

- protocol examples and extraction-schema validation,
- landing tests from intermediate extraction records to current payload families,
- regression tests for representative document inputs such as a paper-style `.tex` Hamiltonian.

The first implementation slice should prioritize examples and contract tests over ambitious fully
automatic parsing claims.

## Risks

- If the protocol is too loose, the agent behavior will still drift and broad-input support will
  remain non-reproducible.
- If the protocol is too rigid, it may block useful partial extraction from realistic papers.
- Document-style inputs often mix simplified and final Hamiltonians; candidate separation must be a
  first-class concept.
- Broad input support can create false user confidence; the skill text must not over-promise what
  the downstream runnable payloads can currently absorb.
