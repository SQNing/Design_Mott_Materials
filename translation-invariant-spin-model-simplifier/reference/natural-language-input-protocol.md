# Natural-Language Input Protocol

This document defines the skill-facing protocol for natural-language, LaTeX, and document-style
inputs before they are normalized into the runnable payload schema described in
`reference/input-schema.md`.

## Scope

Treat the following as first-class upstream inputs:

- freeform natural-language model descriptions,
- natural-language plus short operator expressions,
- LaTeX formula fragments,
- mixed prose plus LaTeX mathematics,
- partial or full `.tex` documents,
- paper-style inputs containing structure sections, Hamiltonian sections, and parameter tables.

Do not promise full automatic support for:

- OCR-corrupted scanned PDFs,
- equations embedded only as images,
- highly ambiguous multi-model papers without user disambiguation,
- prose that never specifies a concrete lattice or Hamiltonian.

## Processing Workflow

1. Identify the input kind:
   - `natural_language`
   - `latex_fragment`
   - `tex_document`
2. If the input is a document-style source, segment it into semantic blocks such as:
   - structure-related passages,
   - Hamiltonian/model passages,
   - parameter tables,
   - ordered-state or analysis notes.
3. Extract all model candidates that appear in the source.
4. Bind parameters from tables, inline assignments, and uncertainty annotations.
5. Build an intermediate extraction record.
6. Attempt landing into the currently supported payload families only after the intermediate record
   is complete enough to support a unique interpretation.
7. If the model cannot be landed faithfully, return `interaction.status = needs_input` with one
   focused blocking question.

## Intermediate Extraction Schema

The intermediate extraction record should contain at least:

- `source_document`
  - source kind, source path or inline origin, and extracted spans
- `document_sections`
  - structure, model, parameter, and analysis sections
- `model_candidates`
  - named candidates such as `toy`, `effective`, or `matrix_form`
- `system_context`
  - material/system name, local Hilbert-space hints, and magnetic-ion context
- `lattice_model`
  - lattice kind, magnetic basis, shell labels, and bond-direction metadata when available
- `hamiltonian_model`
  - extracted one-body, two-body, or higher-body terms plus symbolic forms
- `parameter_registry`
  - names, values, units, uncertainties, and source locations
- `ambiguities`
  - unresolved choices and whether they block landing
- `confidence_report`
  - direct extraction vs inference annotations
- `unsupported_features`
  - extracted content the current payloads cannot yet represent faithfully

## Landing Rules

Use a two-step policy:

1. Extract into the intermediate record first.
2. Only then decide whether the result can be translated into a runnable payload.

Current landing targets remain:

- `operator`
- `matrix`
- `many_body_hr`

Rules:

- Only generate a runnable payload when the extracted record supports a unique, internally
  consistent model interpretation.
- Keep unsupported or only partially representable content in `unsupported_features`,
  `user_notes`, or explicit residual annotations rather than silently dropping it.
- Do not merge multiple model candidates by default.
- If the user selected a specific model candidate, only that candidate may proceed to landing.

## Mandatory `needs_input` Gates

Return `interaction.status = needs_input` whenever any of the following would materially change the
result:

- multiple competing Hamiltonians are present and the user has not selected one,
- lattice interpretation is ambiguous,
- exchange labels might mean either distance shells or named exchange paths,
- parameter tables conflict with formula definitions,
- a missing parameter component would change the physical conclusion if guessed,
- bond-dependent phase or direction conventions are under-specified,
- an equivalent matrix form disagrees with the main Hamiltonian form,
- the extracted content exceeds what current payload families can represent.

## Worked Example

### FeI2-style `.tex` Input

For a document containing:

- a structure section,
- a `Toy Hamiltonian`,
- an `Effective Hamiltonian`,
- an `Equivalent Exchange-Matrix Form`,
- and parameter tables,

the protocol should:

1. detect the source kind as `tex_document`,
2. segment the document into structure, model, parameter, and analysis sections,
3. create model candidates such as `toy`, `effective`, and `matrix_form`,
4. stop with `interaction.status = needs_input` if the user has not selected between competing
   physical models,
5. bind the selected candidate's parameters into `parameter_registry`,
6. land into the nearest supported payload family while carrying unmatched metadata in
   `unsupported_features`.
