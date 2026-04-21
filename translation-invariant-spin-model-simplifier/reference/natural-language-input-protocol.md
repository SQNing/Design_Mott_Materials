# Natural-Language Input Protocol

This document defines the skill-facing protocol for natural-language, LaTeX, and document-style
inputs before they are normalized into the runnable payload schema described in
`reference/input-schema.md`.

## Scope

Treat the following as first-class upstream inputs:

- freeform natural-language model descriptions,
- short dialogue-style requests that describe a model in a few sentences,
- natural-language plus short operator expressions,
- LaTeX formula fragments,
- mixed prose plus LaTeX mathematics,
- partial or full `.tex` documents,
- paper-style inputs containing structure sections, Hamiltonian sections, and parameter tables.
- freeform text that contains file-path references for structure files and `hr`-style hopping files,
- structured `many_body_hr` file-pair payloads,
- agent-normalized paper records that already expose bond-local or matrix-form candidates,
- mixed inputs that combine prose, formulas, and file references.

Do not promise full automatic support for:

- OCR-corrupted scanned PDFs,
- equations embedded only as images,
- highly ambiguous multi-model papers without user disambiguation,
- prose that never specifies a concrete lattice or Hamiltonian.

## Operator-Expression Notes

When the upstream text contains a short operator expression that is already close to a runnable
spin-model term, prefer landing that content through the shared operator-expression route rather
than inventing a separate document-specific parser.

Current supported operator-expression families include:

- compact operator strings such as `Sz@0 Sz@1`, `J*Sp@0 Sm@1`, or grouped products like
  `(J1*Sp@0 Sm@1 + J2*Sm@0 Sp@1) Sz@2`,
- LaTeX-like spin expressions such as `J S_i^z S_j^z`, `S_i^\pm`, grouped `\left(...\right)`
  products, and mixed prose-plus-formula fragments,
- explicit imaginary coefficients such as `i`, `-i`, and `1j`,
- projection wrappers such as `Re[...]`, `Im[...]`, `\mathrm{Re}[...]`, and `\mathrm{Im}[...]`,
- common literature shorthand such as `+ h.c.`, `+ c.c.`, `+ (i<->j)`,
  `+ (i \leftrightarrow j)`, `+ perm.`, `+ cyclic perm.`, and `+ all permutations`.

Interpretation notes:

- These shorthand forms are part of the shared operator-expression semantics for the current
  spin-`S` route; they are not document-only exceptions.
- If a shorthand or wrapper expands cleanly into canonical spin-operator terms, keep that expanded
  operator content and continue through the standard decomposition / canonicalization path.
- If the text mixes supported operator syntax with unsupported constructs, do not silently keep only
  the parseable prefix. Either preserve the unmatched structure in the intermediate record or stop
  with `interaction.status = needs_input`.
- `perm.` is currently only a safe shorthand when the intended permutation action is clear from the
  support already present in the explicit base expression. If a document uses `perm.` ambiguously,
  return `needs_input` instead of guessing the author's intended permutation set.

## Processing Workflow

1. Detect the concrete `source_kind` emitted by the current implementation:
   - `natural_language`
   - `latex_fragment`
   - `tex_document`
2. Treat broader upstream cases such as short dialogue-style requests, mixed prose-plus-formula
   inputs, and file-reference-heavy natural-language requests as conceptual routing cases within
   those concrete `source_kind` values rather than as separate emitted detector tags.
3. If the text contains both:
   - a structure path such as `POSCAR`, `CONTCAR`, `*.cif`, `*.cell`, `*.gen`, `*.stru`, `*.res`,
     `*.pdb`, `*.xyz`, `*.vasp`, or `*.xsf`, and
   - a hopping/integral path whose filename or explicit role indicates an `hr`-style file such as
     `VR_hr.dat`, `wannier90_hr.dat`, `H_R.dat`, or `*_hr*.dat`,
   route it to the `many_body_hr` payload family instead of forcing document-style text parsing.
   If the text instead supplies a directory path, the implementation may inspect that directory for
   a compatible structure file plus an `hr`-style Hamiltonian file and route the pair
   automatically.
   If only one side of that file pair is detected, stop with `interaction.status = needs_input`
   and ask for the missing counterpart instead of silently guessing.
4. If the input is a document-style source, segment it into semantic blocks such as:
   - structure-related passages,
   - Hamiltonian/model passages,
   - parameter tables,
   - ordered-state or analysis notes.
5. Extract all model candidates that appear in the source.
6. Bind parameters from tables, inline assignments, and uncertainty annotations.
7. Build an intermediate extraction record.
   If an upstream agent has already produced a structured record, translate it into the same
   intermediate schema instead of reparsing the source text from scratch.
8. Attempt landing into the currently supported payload families only after the intermediate record
   is complete enough to support a unique interpretation.
9. If the model cannot be landed faithfully, return `interaction.status = needs_input` with one
   focused blocking question.

For document-style sources specifically:

- prefer deterministic extraction first,
- only recommend agent-assisted document normalization when the document has already been detected as
  a paper/LaTeX source but deterministic landing still does not yield a trustworthy runnable
  operator-level payload,
- do not escalate to agent normalization merely because the user still needs to choose among
  legitimate physical options such as model candidate, bond family, or coordinate convention.
- a thin orchestration layer may implement this as a two-pass workflow:
  first run deterministic normalization on the raw document, then if an
  `agent_normalization_request`
  is returned, call an upstream agent and resubmit the same source text together with the produced
  `agent_normalized_document`.
- the formal end-to-end version of that workflow is now
  `scripts/cli/run_document_reader_pipeline.py`,
  which runs document orchestration first and then continues from the landed
  `normalized_model`
  into the shared simplification pipeline without re-reading the raw document as freeform text.
- if document verification reports
  `verification_report.status = needs_review`,
  the document-reader pipeline should preserve that review state visibly in the top-level result,
  but it may still continue into simplification; this is currently a warning/review condition, not
  a hard blocker by itself.

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

When an upstream agent supplies the intermediate content directly, preserve that same shape rather
than inventing a second backend-only schema. In practice this means the agent-facing structured
record should be convertible into the same fields above, with emphasis on:

- `candidate_models`
- `hamiltonian_model.local_bond_candidates`
- `hamiltonian_model.matrix_form_candidates`
- `parameter_registry`
- `system_context.coordinate_convention`
- `unresolved_items`

For evidence-backed parameter extraction, prefer rich
`parameter_registry`
entries that keep per-source observations inside
`evidence_values`
instead of collapsing conflicting values too early.
This lets downstream verifiers detect disagreement between equations, tables, and supplementary
material before a final Hamiltonian record is trusted.

If the paper contains distinct named candidates such as an
`effective`
Hamiltonian plus an
`Equivalent Exchange-Matrix Form`,
prefer storing them in
`candidate_models`
under separate keys and letting the shared landing logic apply
`selected_model_candidate`
and family-level matrix fallback later.

When fallback inference materially contributes during normalization, the normalized result may also
surface these compatibility fields alongside the landed payload or `interaction` block:

- `landing_readiness`
  - whether the helper found a safe landing proposal, still needs user input, or recognized content
    that stays unsupported even with helper assistance
- `agent_inferred`
  - helper-produced narrowing metadata such as recognized evidence, proposed safe fields,
    unresolved items, confidence, and a user-facing explanation
- `agent_normalization_request`
  - a document-ingestion recommendation that asks an upstream agent to convert the source paper into
    the constrained `agent_normalized_document` schema before normalization continues
  - the request should carry a concrete `template_version`, `template`, `example_payload`, and
    short `prompt_notes` so the upstream agent can fill a fixed contract instead of inventing its
    own JSON shape

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
- Freeform text that explicitly supplies both a structure-file path and an `hr`-style hopping-file
  path should land directly as `many_body_hr`, even if the rest of the message is conversational.
- Freeform text may also supply a case-directory path; when that directory contains a compatible
  structure file plus an `hr`-style Hamiltonian file, the pair may be auto-discovered.
- Explicit role phrases such as `structure file:` and `hr file:` may disambiguate otherwise generic
  filenames such as `FI2.dat`.
- If only an `hr`-style file is present, ask for the structure file. If only a structure file is
  present, ask for the `hr`-style Hamiltonian file.
- The higher-level text simplification pipeline can currently execute the routed `many_body_hr`
  branch directly for POSCAR/CONTCAR/VASP-style files and, through the broader structure reader,
  common crystal-structure formats such as `.cif`, `.xsf`, `.cell`, `.gen`, `.res`, and
  lightweight coordinate formats such as `.xyz` and `.pdb`, as well as common FHI-aims structure
  filenames such as `geometry.in`.
- If a detected structure file still cannot be parsed by the available structure readers, return
  `needs_input` and ask for conversion or replacement rather than silently downgrading the input.
- Keep unsupported or only partially representable content in `unsupported_features`,
  `user_notes`, or explicit residual annotations rather than silently dropping it.
- Do not merge multiple model candidates by default.
- If the user selected a specific model candidate, only that candidate may proceed to landing.

## Agent Fallback Contract

Natural-language normalization may attach helper metadata when the implementation can narrow the
route safely without fabricating missing physics.

The contract is:

- `agent_inferred` may narrow missing information only within the approved compatibility boundary.
  Current safe narrowing is limited to helper-recognized fields such as `input_family`,
  `structure_file`, and `hamiltonian_file`; downstream stages decide whether to accept and commit
  those fields.
- A stronger upstream path is also allowed:
  an agent may convert a literature Hamiltonian into a constrained
  `agent_normalized_document`
  object and pass that object into the shared `natural_language` normalization entry.
  That path still lands through the same intermediate-record and `needs_input` policy described in
  this document; it does not bypass ambiguity gates or unsupported-feature reporting.
- `agent_inferred` does not override the mandatory `needs_input` gates below. If the remaining
  ambiguity would materially change the physical model, the result must still surface
  `interaction.status = needs_input` even when the helper recognized a likely route.
- `agent_inferred` must include a user-facing explanation. At minimum this means a
  `user_explanation` object with recognized evidence and a short summary of what was inferred and
  what still blocks landing.
- `unsupported_even_with_agent` is not a success state. It must surface as
  `interaction.status = needs_input` together with the blocking `unsupported_features`, plus a
  user-facing explanation of why manual handling is still required.

`landing_readiness` has the following semantics:

- `agent_proposed_ok`
  - the helper recognized enough bounded evidence to propose a safe landing route, such as a unique
    structure-file plus `hr`-style Hamiltonian-file pair for `many_body_hr`
- `agent_proposed_needs_input`
  - the helper narrowed the route but landing still requires user input because of unresolved
    ambiguities, a hard-gated field, low confidence, or a document-style path that intentionally
    preserves `needs_input`
- `unsupported_even_with_agent`
  - the helper recognized blocking content that current payload families still cannot represent
    faithfully; the public result remains `needs_input`

`agent_inferred` may contain:

- `status`
  - `proposed`, `accepted`, or `rejected`, depending on whether the helper proposal stayed pending,
    was committed by normalization, or was withheld for lack of confidence
- `confidence`
  - confidence level plus a short reason
- `inferred_fields`
  - only the helper fields that were actually narrowed
- `recognized_items`
  - user-readable recognized evidence derived from source spans and extracted evidence
- `unresolved_items`
  - remaining blockers that still require user input
- `unsupported_even_with_agent`
  - the subset of unsupported features that remain blocking even after helper assistance
- `user_explanation`
  - user-facing `recognized` and `summary` content that explains the helper outcome

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

These gates remain mandatory even when `agent_inferred` is present. The helper may narrow which
question to ask next, but it cannot bypass a blocking ambiguity, a hard-gated convention choice, or
unsupported content that still requires manual resolution.

## Unified Entry Contract

Document-style text inputs are not a separate public ingestion family. They enter through the same
`natural_language` normalization path as ordinary freeform text.

The contract is:

1. the caller submits text through the `natural_language` / freeform entry,
2. the implementation detects whether the text is plain language, a LaTeX fragment, or a full
   document such as a `.tex` source,
3. if a document contains multiple competing model candidates, normalization returns
   `interaction.status = needs_input`,
4. the caller may then resubmit the same text with `selected_model_candidate`,
5. if helper fallback metadata is surfaced for a document-style input, it may narrow the next
   blocking question through `agent_inferred`, but document-style ambiguity handling still remains
   `needs_input` until the mandatory gate is resolved,
6. only after that selection does the document land into a supported normalized payload, when
   possible.

This keeps the user-facing entry broad and uniform while allowing richer document-style ambiguity
handling internally.

When users explicitly want one command for this whole path, prefer the document-reader CLI over
manually chaining the document-normalization wrapper and the simplify-text CLI.

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

### Optional Spin-Only Classical Bridge

For readable spin-only exchange results, the document-reader pipeline may also emit a spin-only
classical-solver bridge after simplification.

Current V2a scope:

- supports readable spin-only bilinear blocks that map directly to a `3x3` exchange matrix:
  `isotropic_exchange`, `xxz_exchange`, `symmetric_exchange_matrix`, and `exchange_tensor`
- if one family is selected, expands that family into the full shell-resolved canonical bond set
- if `selected_local_bond_family = all`, assembles one aggregated payload from all supported
  family-resolved readable blocks
- treats per-family readable blocks as the authoritative bridge input when present
- uses `shell_resolved_exchange` summaries only for ordering and validation
- preserves enough `effective_model` / `simplified_model` metadata for the current classical solver
  routing layer
- may optionally run the classical solver and save both `classical/solver_payload.json` and
  `classical/solver_result.json`

Current V2a non-goals:

- automatic LSWT / GSWT / thermodynamics chaining
- residual-term promotion into the spin-only bridge payload
- multipolar bridge contracts
- mixed spin-orbital bridge contracts
- silent dropping of unsupported families from `selected_local_bond_family = all`
