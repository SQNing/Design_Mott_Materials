# Skill Thinning And Agent Routing Design

## Goal

Restructure the top-level `translation-invariant-spin-model-simplifier` skill into a thinner,
more reusable expert-facing entrypoint without removing any currently supported repository
capability.

The design should:

- preserve the current scientific and reproducibility contracts
- keep all currently supported input, routing, solver, and reporting capabilities reachable
- move repository-specific routing and backend-selection detail out of the top-level skill and into
  a dedicated reference document
- make the top-level skill easier for a strong agent to apply consistently without re-reading a
  large implementation-heavy monolith

The intended primary audience remains:

- experts
- semi-skilled users working with agent help

This design does not try to optimize for a fully novice self-serve experience.

## User-Approved Direction

- Use a dual-layer structure:
  - a thin top-level `SKILL.md`
  - a new `reference/agent-routing.md`
- Keep strong top-level contracts rather than loosening scientific behavior
- Preserve all currently available repository functionality
- Target experts and semi-skilled users rather than novice-first onboarding
- Use a weakly ordered top-level workflow rather than a purely abstract phase list

## Problem

The current top-level `SKILL.md` successfully captures a large amount of project behavior, but it
mixes several responsibilities that should be separated:

- user-facing capability definition
- scientific contract and safety policy
- repository-specific routing logic
- backend and CLI selection details
- current implementation-phase semantic conventions

This has several costs.

### 1. The top-level skill is too implementation-heavy

The current file names many concrete scripts, wrappers, flags, and route-specific execution
details. That makes it harder to use as a stable capability contract because the user-facing skill
becomes tightly coupled to current repository internals.

### 2. Stable principles and current routing details are mixed together

Some rules in the current skill are long-lived scientific requirements:

- stop on material ambiguity
- preserve residual structure
- surface environment blockers early
- do not silently downgrade required backends

Other rules are current repository routing choices:

- which wrapper CLI to run
- which family-explicit path to use for a given payload
- which document handoff path to prefer
- how current retained-local-multiplet semantics are represented

When both categories are written together in one long top-level skill, maintainers must edit the
same file for both principle changes and routing changes.

### 3. The workflow is more rigid than the real agent task requires

The current workflow reads like a concrete orchestrator recipe. That is useful as implementation
history, but the top-level skill should instead guide an agent through stable responsibilities while
leaving room to choose the right reference material and backend path for the current input.

### 4. The current structure makes generalization harder

A strong agent can already do several high-value tasks that do not belong in a static monolithic
skill:

- infer the likely input route from mixed user context
- decide which reference file needs to be consulted next
- explain tradeoffs and blockers to the user
- choose among repository-supported entrypoints based on current constraints

The top-level skill should preserve the hard scientific boundaries while letting the agent do more
of this routing and interpretation work explicitly.

## Recommended Approach

Adopt a dual-layer design:

1. keep `SKILL.md` as the authoritative expert-facing capability and contract layer
2. add `reference/agent-routing.md` as the authoritative repository-routing companion

The key split is:

- `SKILL.md` answers:
  - what this capability is for
  - which scientific and execution boundaries must not be violated
  - what the minimum workflow and output contract are
- `reference/agent-routing.md` answers:
  - how the current repository routes each supported input family
  - when agent-assisted landing is allowed
  - how classical-family and backend routing currently work
  - which entrypoints are currently preferred

This keeps the entry skill thinner without reducing capability coverage.

## Scope

This design applies to the top-level expert-facing capability description for:

- operator-expression inputs
- local matrix or tensor inputs
- structured lattice or model inputs
- natural-language and document-style inputs
- `many_body_hr` pseudospin-orbital inputs
- family resolution across `spin-only` and `cpn`
- downstream classical, thermodynamic, and spin-wave routing
- final reporting expectations

This design does not change the underlying backend contracts, schemas, or solver behavior. It only
changes where that information is declared and how the top-level skill presents it.

## Top-Level `SKILL.md` Design

The new top-level `SKILL.md` should be concise and stable. It should contain five sections.

### 1. Overview

This section should state that the skill is used to simplify a translation-invariant spin or
pseudospin model into a readable effective model and, when appropriate, continue into downstream
classical, thermodynamic, or spin-wave analysis.

It should explicitly state that the audience is expert or semi-skilled, not fully novice-first.

### 2. Core Guarantees

This section should preserve the non-negotiable top-level contracts.

Required guarantees:

- if any ambiguity would materially change the physical meaning or execution route, stop with
  `interaction.status = needs_input`
- do not silently guess physically important branches
- preserve a readable decomposition as
  `H_main + H_low_weight + H_residual`
- surface environment blockers early, before promising unavailable backend paths
- do not silently replace a required Sunny-backed path with a different backend
- prefer explicit residual structure and unsupported-feature reporting over false simplification

These are stable scientific and execution guarantees and belong in the top-level skill.

### 3. Workflow

The workflow should remain weakly ordered and execution-oriented, but no longer name a long list of
concrete scripts.

Recommended workflow:

1. identify the input route
2. check environment and execution constraints
3. land the input into a trusted normalized form
4. resolve material ambiguity before simplification
5. build the readable effective model
6. run optional downstream analysis when appropriate
7. report assumptions, limits, choices, and recommendations

This gives the agent a stable skeleton without over-encoding implementation order.

### 4. Output Contract

The top-level skill should require the final result to include:

- the recommended simplified result
- the decomposition into `H_main`, `H_low_weight`, and `H_residual`
- key assumptions and unresolved limitations
- unsupported features or blocked routes
- chosen solver or backend path, or the blocker that prevented it
- fidelity or reconstruction context when available

The output contract should not require mechanically generating multiple alternatives in every case.
Instead, multiple simplification views should be provided when materially different trusted views
exist and the choice matters to the user.

### 5. Routing References

The top-level skill should explicitly delegate repository-specific execution details to:

- `reference/agent-routing.md`
- `reference/input-schema.md`
- `reference/natural-language-input-protocol.md`
- `reference/fallback-rules.md`
- `reference/environment.md`

This section is the bridge that keeps the top-level skill thin without making it incomplete.

## `reference/agent-routing.md` Design

The new routing companion should hold the repository-specific decision knowledge that is currently
overloaded into the top-level skill.

It should be written as an agent-executable routing guide rather than a broad narrative essay.

### 1. Input Classes

This section should enumerate the currently supported input classes:

- operator expressions
- local matrices or tensors
- structured lattice or model inputs
- natural-language or document-style inputs
- `many_body_hr`
- already landed payloads

### 2. Routing By Input Class

For each input class, specify:

- the preferred shared backbone
- whether deterministic landing is expected first
- whether further family resolution is still needed
- which reference file should be consulted when ambiguity remains

### 3. Agent-Assisted Landing

This section should absorb the current guidance around:

- `agent_normalization_request`
- `agent_normalized_document`
- deterministic-first document handling
- when the agent may help infer non-critical structure
- when the workflow must still remain at `needs_input`

This preserves the current broad-input capability while moving the details out of the top-level
skill.

### 4. Classical Family Resolution

This section should document the current family-routing rules:

- `spin-only`
- `cpn`

It should also preserve the current policy that broad ambiguous text and document entrypoints must
not silently choose between these families.

### 5. Backend And Solver Routing

This section should preserve current routing knowledge for:

- generic classical workflows
- pseudospin-orbital Sunny routes
- thermodynamics options
- LSWT and related downstream analysis
- `cpn-generalized-lt` final versus diagnostic-only handling

This is where current backend-specific route knowledge should live instead of in the top-level
skill.

### 6. Current Semantic Conventions

This section should preserve repository-specific but scientifically important current conventions,
including:

- current `many_body_hr` interpretation
- retained-local-multiplet semantics
- generic multiplet versus `orbital-times-spin`
- the repository meaning of `CP^(N-1)` payload and local-ray language
- current exchange-component explanation defaults

These conventions must remain available because they affect interpretation, but they do not belong
in a thin top-level skill.

### 7. Recommended Entrypoints

This section should list the currently preferred repository entrypoints for major routes, including
document-reader, agent-assisted normalization, and explicit payload pipelines.

These are recommendations for the current repository rather than eternal user-facing capability
contracts.

### 8. Related References

This section should point agents to the more detailed authoritative documents:

- `reference/input-schema.md`
- `reference/natural-language-input-protocol.md`
- `reference/fallback-rules.md`
- `reference/environment.md`

## Migration Map From The Current `SKILL.md`

The current file content should be redistributed rather than deleted.

### Keep In The New Top-Level `SKILL.md`

Preserve, in compressed form:

- the general fidelity-aware simplification philosophy
- the `needs_input` contract for material ambiguity
- the no-silent-downgrade backend policy
- the residual-preserving output philosophy
- the early environment-blocker policy
- the final readable-model output contract

### Move To `reference/agent-routing.md`

Move most current repository-specific content covering:

- detailed input route distinctions
- document and agent-assisted landing guidance
- explicit `spin-only` versus `cpn` routing rules
- retained-local-multiplet and `many_body_hr` route semantics
- backend and solver family distinctions
- current preferred entrypoint scripts and wrappers

### Leave In Existing Detailed Reference Files

Do not duplicate full detail from:

- schema documents
- fallback-rule documents
- environment documents
- document-input protocol documents

The new routing document should summarize routing decisions and point to the detailed sources
instead of re-copying them wholesale.

## Capability Preservation Rules

The redesign must not remove or obscure any currently available capability. In particular:

- all currently supported input families must remain discoverable
- all current family-routing choices must remain reachable
- all current Sunny and non-Sunny supported routes must remain routable
- current reporting expectations must remain intact
- current document-agent handoff capability must remain documented and usable

The refactor is successful only if the entry experience becomes thinner while supported
functionality remains fully represented.

## Risks

### Risk 1: Over-thinning The Top-Level Skill

If the new `SKILL.md` becomes too abstract, agents may miss important repository routing
constraints.

Mitigation:

- keep strong core guarantees in the top-level file
- explicitly point to `reference/agent-routing.md`
- retain a weakly ordered workflow rather than a fully abstract description

### Risk 2: Duplicating Too Much Detail In The Routing Companion

If `reference/agent-routing.md` simply copies the old `SKILL.md`, the redesign fails.

Mitigation:

- write the routing companion as a decision guide
- avoid restating full schema or protocol detail already maintained elsewhere
- prefer short routing summaries plus references

### Risk 3: Losing Discoverability Of Current Features

If some current repository-supported route is omitted from the new routing companion, the thinner
top-level skill will make that omission more costly.

Mitigation:

- explicitly enumerate supported input classes
- explicitly enumerate routing families and backend families
- review the old `SKILL.md` line by line during migration

## Acceptance Criteria

The redesign is complete when:

- `SKILL.md` is materially shorter and no longer dominated by repository-specific script names and
  route details
- `reference/agent-routing.md` exists and captures the current repository routing knowledge in a
  compact decision-oriented form
- all currently supported capability areas remain documented
- the top-level skill still clearly states the scientific and execution guarantees that must not be
  violated
- the resulting pair is more reusable for strong agents without weakening the current contracts
