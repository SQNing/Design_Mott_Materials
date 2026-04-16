# Natural-Language Agent Fallback Design

**Date:** 2026-04-17

## Goal

Extend the existing natural-language and document-input protocol with an explicit agent-fallback
layer that improves broad-input coverage without weakening ambiguity handling, reproducibility, or
user trust.

The design should let the system accept freer dialogue-style inputs, mixed file-path hints, and
partially structured scientific text while still preserving the current rule-first philosophy:

- deterministic parsing remains the primary path,
- the agent may help infer missing non-critical fields,
- hard ambiguity gates must still return `needs_input`,
- the user must be shown a clear explanation whenever agent inference materially affects the result.

## User-Approved Direction

- Keep the current skill as the only top-level entrypoint.
- Do not create a separate natural-language skill or independent execution branch.
- Keep the current `natural_language` normalization path as the main ingress.
- Add an explicit `agent_inferred` intermediate block when rule-based parsing alone is
  insufficient.
- Require the agent to explain what it recognized, what it inferred, and what still needs user
  confirmation.
- Optimize for broad practical coverage, but do not pretend to fully automate physically ambiguous
  cases.
- Preserve current `needs_input` and `unsupported_features` semantics rather than bypassing them.

## Problem Statement

The project has already broadened support for:

- document-style `.tex` inputs,
- multiple model candidates such as `toy`, `effective`, and `matrix_form`,
- structure plus `hr` file-path routing into `many_body_hr`,
- broader structure file detection such as `POSCAR`, `.cif`, `.xsf`, `.cell`, `.gen`, `.res`,
  `.xyz`, `.pdb`, and common `geometry.in` style filenames,
- safer fallback behavior for effective-model local bond families.

That progress improves coverage, but there is still a major gap between:

1. inputs that the current rule-based stack can extract deterministically, and
2. inputs that a human can understand from a few sentences but the scripts cannot yet land
   uniquely.

Without a formal fallback layer, the system tends to fall into one of two unsatisfying modes:

- it stops too early with a shallow parser result even when the user intent is fairly recoverable,
  or
- it risks overfitting ad hoc heuristics that silently choose a model branch without enough
  transparency.

The design therefore needs a middle layer that can:

- capture agent-assisted inference explicitly,
- keep that inference auditable,
- reduce user back-and-forth by narrowing the missing information,
- and still refuse to auto-land when physically important ambiguity remains.

## Approaches Considered

### 1. Continue expanding only the rule-based parser

Keep adding more deterministic rules until the current parser can cover most dialogue and
document-derived inputs directly.

Pros:

- maximal reproducibility,
- straightforward testing,
- no extra intermediate semantics.

Cons:

- poor scalability for broad freeform dialogue,
- large rule explosion,
- increasingly brittle maintenance,
- still weak for mixed conversational and scientific inputs.

### 2. Let the agent directly produce the final normalized payload

Use the agent as a freeform interpreter that reads the user input and directly emits the payload to
the runnable pipeline.

Pros:

- broadest short-term language coverage,
- easiest way to handle conversational inputs.

Cons:

- weak auditability,
- difficult regression testing,
- higher risk of silent drift and overconfident auto-decisions,
- poor compatibility with the existing normalization contract.

### 3. Add an explicit agent-fallback intermediate layer after rule extraction

Keep rule-based parsing first. When it cannot fully land the input, produce an explicit
`agent_inferred` block that records what the agent recognized, inferred, assumed, and still cannot
decide. A final landing step then determines whether the result can become `ok` or must remain
`needs_input`.

Pros:

- broad practical coverage,
- preserves explicit ambiguity handling,
- remains testable and auditable,
- avoids silently bypassing the current normalization contract,
- fits naturally into the existing `normalize_input.py` pipeline.

Cons:

- introduces a new intermediate concept that must be documented carefully,
- requires consistent user-facing explanation formatting,
- adds one more decision layer to maintain.

## Recommended Design

Use approach 3.

The system should remain rule-first, but add a formal agent-fallback stage inside the natural
language/document normalization path. The agent-fallback stage is not a new public input family.
It is an internal augmentation layer that can:

- recover non-critical missing fields from conversational or document context,
- narrow unresolved ambiguity down to a single blocking question,
- and explain the result to the user in an engineering-style, auditable format.

The final contract remains externally simple:

- return `status = ok` when the model can be uniquely and faithfully landed,
- return `status = needs_input` when any material ambiguity remains.

The new layer exists to improve how the system reaches one of those two outcomes.

## Placement in the Existing Architecture

The current high-level flow should become:

1. ingest raw freeform text, dialogue text, LaTeX fragment, document text, or mixed file-path
   hints,
2. run the existing rule-based extraction and routing logic,
3. build or update the intermediate extraction record,
4. if direct landing is blocked but the input is still partially interpretable, run the
   agent-fallback inference stage,
5. pass the extracted plus inferred state into a single landing decision stage,
6. return either a runnable normalized payload or `needs_input` with an explicit user explanation.

This keeps three responsibilities separate:

- rule extraction identifies explicit evidence,
- agent fallback proposes bounded inference,
- landing arbitration decides whether execution may continue.

The agent fallback must not mutate early parsing decisions in place without traceability. Instead,
it should produce an explicit intermediate record that the landing stage may accept or reject.

## New Intermediate Block: `agent_inferred`

When rule-based parsing alone is insufficient, the intermediate record may contain:

- `agent_inferred`
  - `status`
    - `proposed`
    - `accepted`
    - `rejected`
  - `confidence`
    - qualitative level such as `high`, `medium`, or `low`
    - optional numeric score
  - `source_kind`
    - for example `dialogue_text`, `natural_language`, `tex_document`, `mixed_input`
  - `source_spans`
    - short evidence excerpts or file-path hints used by the inference
  - `inferred_fields`
    - only the fields newly inferred by the agent
  - `assumptions`
    - defaults or interpretive assumptions the agent used
  - `alternatives_considered`
    - candidate interpretations the agent compared when relevant
  - `unresolved_items`
    - fields that still block faithful landing
  - `landing_decision`
    - the proposed target family and whether landing is safe
  - `user_explanation`
    - concise user-facing explanation of recognition, inference, assumptions, and remaining gap

This block is not a replacement for the normalized payload. It is only an auditable supplement to
the intermediate extraction record.

## Internal Landing Readiness States

For planning and implementation purposes, the intermediate record should also support an internal
landing-readiness concept:

- `direct_ok`
  - rule extraction already supports a unique faithful landing
- `agent_proposed_ok`
  - rule extraction was incomplete, but agent inference only filled safe fields and all material
    ambiguity is resolved
- `agent_proposed_needs_input`
  - the agent reduced ambiguity but at least one material question remains
- `unsupported_even_with_agent`
  - the input is understandable at a high level, but the current schema or pipeline cannot
    represent it faithfully

This state is mainly for internal reasoning and testing. The user-facing result should still remain
top-level `ok` or `needs_input`.

## Field Policy: What the Agent May and May Not Infer

The agent should not treat all missing fields equally. The design divides them into three classes.

### Class A: Safe auto-inference fields

These may be auto-filled when the evidence is strong and unique:

- `input_family`
- `source_kind`
- `structure_path`
- `hr_path`
- `material_or_system_name`
- uniquely bound `parameter_value`
- units such as `meV`, `eV`, or `K`
- explicit `site_spin` values such as `S=1` or `spin-3/2`
- `selected_model_candidate` only when the user input clearly contains one primary model and no
  competing model interpretation is actually present

Even for these fields, the system must record:

- the evidence span or file hint,
- the inferred value,
- and any default assumption that contributed to the result.

### Class B: Candidate-level inference fields

These may be proposed, but should usually not be silently committed unless the evidence is
exceptionally strong and no competing interpretation remains:

- `lattice_kind`
- `bond_shell_labels`
- `selected_local_bond_family`
- `coordinate_convention`
- `magnetic_basis`
- `active_subspace`
- `matrix_basis_label`

When the agent touches these fields, the result should usually include:

- a stated confidence level,
- alternatives considered,
- and either a very explicit `accepted` rationale or a remaining `needs_input` gate.

Some fields in this class, especially `coordinate_convention`, must be promoted to a hard gate
whenever the choice changes the physical meaning of the resulting model rather than only changing a
presentation detail.

### Class C: Hard gate fields

These must not be decided automatically by agent inference when the choice would materially change
the resulting physical model:

- choosing between multiple competing Hamiltonians when they are not provably equivalent,
- choosing a coordinate convention that changes tensor or phase meaning,
- resolving bond-dependent anisotropy direction conventions,
- choosing between conflicting parameter definitions in text and tables,
- selecting among multiple possible structure and `hr` file pairings,
- deciding whether the user wants a simplified effective spin model or only raw matrix/`hr`
  ingestion when the input is ambiguous,
- choosing between truncated and full-dimensional model interpretations when both are plausible,
- interpreting the same local dimension as `spin-S` versus retained multiplets or multiple Kramers
  doublets when the physics differs.

If any of these remain unresolved, the top-level result must stay `needs_input` even if the agent
has a strong guess.

## Mandatory Compatibility with Existing `needs_input` Gates

The agent-fallback layer must not weaken the current mandatory stop conditions already documented in
the natural-language input protocol. The compatibility rule is:

The agent may reduce the amount of missing information, but it may not bypass a hard ambiguity gate
whose resolution would materially change the result.

That means:

- `agent_inferred` can shrink a vague input into one sharply focused question,
- but it cannot convert a hard physics ambiguity into a silent auto-decision.

This rule is essential for preserving scientific fidelity while improving usability.

## Relationship to `unsupported_features`

The design distinguishes two separate failure modes:

- understanding failure,
- representation failure.

The new `agent_inferred` block addresses understanding failure by capturing what the system could
recognize or plausibly infer from freeform input.

The existing `unsupported_features` mechanism addresses representation failure by recording model
content that the current payload schema or downstream simplifier cannot represent faithfully.

These must remain distinct:

- use `agent_inferred` to explain what the system thinks the user meant,
- use `unsupported_features` to explain what the current implementation still cannot encode or run.

An input may legitimately have both.

When the internal readiness state is `unsupported_even_with_agent`, the top-level response should
still surface as:

- `status = needs_input`
- with `unsupported_features` populated
- and with `agent_inferred.user_explanation` explaining that the input was understood better than
  it can currently be represented or executed.

## User-Facing Explanation Contract

Whenever `agent_inferred` materially affects the outcome, the result must include a concise
user-facing explanation. The tone should be engineering-style and auditable rather than chatty or
overconfident.

The explanation should follow this order:

1. what the system recognized,
2. what processing path it selected,
3. what assumptions or defaults it used,
4. what still blocks execution, if anything.

The explanation should avoid opening with vague language such as "I guess you meant". Prefer
factual wording such as:

- "Recognized structure file ..."
- "Detected hr-style Hamiltonian file ..."
- "Interpreting this input via ..."
- "Still need confirmation of ..."

### Minimal explanation template

For blocking cases:

```text
I recognized:
- structure file: structure.cif
- hr-style Hamiltonian file: wannier90_hr.dat
- model keyword: effective Hamiltonian

I therefore interpret this input through the many_body_hr -> effective path.

Current defaults or assumptions:
- treat the hr-style file as the bond-Hamiltonian source
- treat the only named Hamiltonian as the selected model candidate

One remaining item still changes the physical result:
- coordinate convention

Please confirm:
- global crystallographic or local bond frame?
```

For auto-landed cases:

```text
I recognized:
- structure file: structure.cif
- hr-style Hamiltonian file: wannier90_hr.dat
- model keyword: effective Hamiltonian

This is sufficient to continue through the many_body_hr -> effective path.

Defaults used:
- treat the hr-style file as the Hamiltonian source

If this default is not what you intended, explicitly specify the desired model branch.
```

The user should never need to inspect raw JSON to understand what happened.

## CLI and API Output Contract

The public result format should remain small and stable.

Always keep the top-level result centered on:

- `status`
- normalized or landed payload fields
- `interaction`
- `unsupported_features`

Only include `agent_inferred` when the fallback stage actually contributed to the result.

For normal user-facing output, expose only the parts of `agent_inferred` that help explain or
audit the inference:

- `confidence`
- `recognized_items`
- `assumptions`
- `unresolved_items`
- `user_explanation`

`recognized_items` should not become a second independent evidence store. It should be a compact
public-facing rendered view derived from:

- `source_spans` produced by the agent-fallback layer,
- plus any especially important rule-extracted evidence already present in the intermediate record.

Deeper diagnostic content such as:

- `source_spans`
- `alternatives_considered`
- `landing_decision`

may remain available in development or debug-oriented outputs, but should not be required for basic
CLI consumption.

## Integration Plan for Existing Modules

This design is intended to fit directly into the current code layout.

### `reference/natural-language-input-protocol.md`

Extend the protocol so that the intermediate extraction schema explicitly includes:

- `agent_inferred`
- internal landing-readiness semantics
- the relationship between agent inference and hard `needs_input` gates
- the user-facing explanation requirement

### `scripts/input/normalize_input.py`

Add a bounded agent-fallback decision stage after rule-based extraction but before final landing.

This stage should:

- receive the current extraction state,
- detect whether agent fallback is warranted,
- produce `agent_inferred` and a proposed field patch,
- and pass both into a single landing-arbitration step.

The implementation should avoid mutating payloads early in scattered branches. The final landing
stage should be the only place that commits inferred fields into the normalized result.

### CLI-facing layers

CLI helpers should surface the explanation in a stable and compact way. They should not require the
user to understand the internal extraction record.

## Testing Strategy

The implementation should be verified at four levels.

### 1. Protocol-level tests

Check that suitable natural-language or dialogue-style inputs produce an `agent_inferred` block
when rule extraction alone is incomplete.

### 2. Landing-decision tests

Check the difference between:

- high-confidence safe auto-landing,
- high-confidence but hard-gated `needs_input`,
- low-confidence fallback that must remain non-landing.

### 3. Explanation-contract tests

Check that `user_explanation` always communicates:

- recognized evidence,
- selected processing path,
- assumptions,
- and the minimal remaining question when blocked.

### 4. Regression tests for existing supported flows

Protect the currently working paths so that agent fallback does not destabilize them:

- structure plus `hr` routing into `many_body_hr`,
- document candidate selection,
- effective-to-matrix fallback behavior,
- FeI2 family-specific ambiguity blocking and recovery.

## Non-Goals

This design does not attempt to:

- build a fully autonomous scientific document parser,
- guarantee correct automatic model selection for every paper,
- replace hard physics choices with language-model confidence,
- merge multiple competing candidate models automatically,
- or remove the distinction between broad understanding and faithful executable representation.

## Open Constraints and Explicit Limits

These limits should remain visible in the downstream spec and plan:

- broad natural-language support improves practical coverage, not formal completeness,
- file-path and dialogue interpretation can reduce friction but still depends on clear evidence,
- local-space interpretation remains physically sensitive and should stay conservative,
- any case where an inferred choice changes the resulting Hamiltonian class must remain a
  `needs_input` gate,
- the first implementation should favor explicit explanations and stable behavior over ambitious
  freeform inference.

## Why This Design Is Recommended

This design is the best fit for the current project because it improves breadth without sacrificing
the project's most important behavior: fidelity-aware ambiguity handling.

It allows the system to understand more of what users actually type:

- a few conversational sentences,
- file paths embedded in prose,
- mixed document plus path inputs,
- or partially structured scientific descriptions,

while keeping the contract honest:

- the system can explain what it recognized,
- it can say what it inferred,
- it can stop when a real scientific ambiguity remains,
- and it can distinguish "I understand you" from "I can already run this faithfully."
