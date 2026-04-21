# FeI2 V2b Downstream Chaining Design

## Goal

Extend the landed FeI2 `V2a` spin-only bridge into the original broader `V2`
workflow stage by adding explicit downstream chaining on top of the stable
bridge payload contract.

For supported FeI2 document-reader runs, this stage should:

- consume the existing `V2a` shell-expanded or all-family bridge payload
- optionally run the classical solver if requested
- compute downstream route status for `lswt`, `gswt`, and `thermodynamics`
- execute only the downstream stages allowed by the `V2b` policy
- write explicit routing, result, summary, and provenance artifacts instead of
  hiding stage decisions inside one opaque success/failure bit

This design is intentionally about workflow expansion and execution policy. It
does not redesign `V2a` payload assembly.

## Why V2b Exists

The repository now has the main prerequisites that `V2b` needs:

- the FeI2 document-reader path works and emits stable readable-model artifacts
- the FeI2 bridge no longer requires manual payload construction for `V2a`
  assembly
- `build_spin_only_solver_payload.py` already supports:
  - full shell expansion for one supported selected family
  - `selected_local_bond_family = "all"` aggregation
- the shared classical solver layer already emits standardized
  `classical_state_result` and downstream compatibility metadata
- shared downstream routing and execution helpers already exist in:
  - `scripts/common/downstream_stage_routing.py`
  - `scripts/common/downstream_stage_execution.py`

What is still missing is the FeI2-specific orchestration layer that turns a
successful document-reader plus bridge plus classical run into a productized
downstream workflow with explicit stage-level semantics.

## In Scope

### Workflow Scope

`V2b` adds downstream orchestration for FeI2 spin-only document-reader runs:

- compute route status for `lswt`, `gswt`, and `thermodynamics`
- execute downstream stages according to an explicit FeI2 `V2b` policy
- write route, result, and summary artifacts under the document-reader output
  tree
- preserve classical success even when one downstream stage is blocked or fails

### Design Scope

This design covers:

- architecture and component boundaries
- stage execution policy
- failure semantics
- artifact/provenance contracts
- testing strategy and implementation slicing

## Explicitly Out Of Scope

The following do not belong to `V2b`:

- changing the `V2a` block-to-bond assembly contract
- re-defining shell expansion semantics or `all`-family aggregation semantics
- adding support for residual, multipolar, or mixed spin-orbital bridge payloads
- forcing `GSWT` into the default FeI2 spin-only path when the payload contract
  is not already explicit
- making `review` downstream routes auto-execute by default

Those remain either `V2a` concerns, later `V2` follow-on work, or `V3` model
class generalization work.

## Current-State Constraints

Important current constraints that this design must preserve:

- `build_spin_only_solver_payload.py` is now the stable `V2a` boundary and
  should remain a payload builder rather than an execution runner
- `run_document_reader_pipeline.py` already orchestrates:
  - document normalization
  - simplification
  - optional bridge payload emission
  - optional classical solver execution
- the repository already has shared downstream helpers and `V2b` should consume
  them instead of open-coding new FeI2-specific routing rules
- stage readiness and backend hints should continue to come from the shared
  standardized contract whenever possible

The main architecture risk is contract entanglement, not missing execution
capability. `V2b` should therefore connect existing layers cleanly rather than
rebuild them.

## Design Summary

`V2b` should adopt a two-phase downstream model:

```text
document normalization
  -> simplification
  -> V2a bridge payload
  -> classical solver
  -> downstream route resolution
  -> policy-based stage execution
  -> explicit route/result/summary artifacts
```

The key design rule is:

> `V2b` consumes the stable `V2a` payload contract. It does not redefine
> payload assembly.

This gives the FeI2 bridge thread a clean split:

- `V2a` = payload assembly
- `V2b` = downstream orchestration

## Core Design Choice

`V2b` should not be implemented by stuffing downstream policy directly into
`build_spin_only_solver_payload.py` or by open-coding stage logic throughout
`run_document_reader_pipeline.py`.

Instead, `V2b` should introduce one focused orchestration helper that:

- resolves all downstream routes from the post-classical payload
- decides which stages to execute under the FeI2 `V2b` policy
- executes the selected stages through the shared execution helper
- returns a structured result bundle for artifact writing

This keeps:

- `V2a` payload logic isolated
- policy logic testable in one place
- pipeline orchestration thin
- future follow-on tuning of stage policy possible without rewriting the bridge

## Proposed Components

### 1. Stable V2a Bridge Payload

Responsible module:

- `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`

Responsibility:

- accept the simplified readable model
- emit the stable spin-only classical payload
- preserve `effective_model`, `simplified_model`, and `bridge_metadata`

`V2b` should treat this output as an input contract, not as a work area for
new downstream execution code.

### 2. Document-Reader Downstream Orchestration Helper

Suggested new module:

- `translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py`

Responsibility:

- accept the post-classical payload and policy options
- resolve downstream routes for:
  - `lswt`
  - `gswt`
  - `thermodynamics`
- execute only the allowed stages
- compute:
  - `downstream_status`
  - `downstream_routes`
  - `downstream_results`
  - `downstream_summary`

This helper should be the only FeI2-specific `V2b` policy layer.

### 3. Pipeline Integration

Responsible module:

- `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`

Responsibility:

- call the bridge builder
- call the classical solver
- call the new downstream orchestration helper
- write artifacts
- assemble the final pipeline result

It should remain an orchestrator. It should not contain the detailed
`LSWT` / `GSWT` / `thermodynamics` policy logic itself.

### 4. Shared Routing And Execution Layers

Responsible modules:

- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_routing.py`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_execution.py`

Responsibility:

- route interpretation
- backend selection
- stage execution

`V2b` should reuse them as-is wherever possible. FeI2-specific policy belongs
above them, not inside them.

## State Model

`V2b` should keep bridge, classical, and downstream status separate.

### Existing Status Layers

- `bridge_status`
  - did bridge payload construction succeed?
- `classical_solver`
  - what happened in the classical solver stage?

### New Downstream Layers

- `downstream_routes`
  - route snapshot for every stage, whether executed or not
- `downstream_results`
  - results only for stages that were actually executed
- `downstream_summary`
  - human-readable rollup of route and execution outcomes
- `downstream_status`
  - overall summary of downstream orchestration

Suggested `downstream_status` values:

- `not_requested`
- `ok`
- `partial`
- `blocked`
- `error`

This separation is critical because `V2b` must distinguish:

- bridge failure
- classical success with downstream block
- classical success with partial downstream execution
- downstream execution errors after a valid classical result

## Route-Then-Execute Model

`V2b` should always resolve routes for all supported downstream stages before
deciding whether to execute any of them.

That means every eligible FeI2 run produces route records for:

- `lswt`
- `gswt`
- `thermodynamics`

even if none of those stages are executed.

Benefits:

- artifact consumers can tell the difference between “not run” and “not ready”
- policy changes do not require changing route interpretation
- debugging gets easier because the route evidence remains visible

## Stage Policy

### LSWT Policy

`LSWT` is the primary auto-run target for the first `V2b` implementation.

Policy:

- if `lswt` route status is `ready`, execute automatically
- if `lswt` route status is `blocked`, record the route but do not attempt any
  FeI2-specific workaround
- do not introduce a `review`-auto-run path for `LSWT` in the first `V2b`
  implementation

Rationale:

- `LSWT` is the natural downstream consumer for spin-only FeI2 classical states
- current repository support for spin-frame classical states into LSWT is the
  most mature downstream path on this branch

### GSWT Policy

`GSWT` should be routed but handled conservatively.

Policy:

- always record the `gswt` route
- auto-execute only when:
  - route status is `ready`, and
  - a compatible explicit `gswt_payload` already exists
- otherwise do not auto-execute

Rationale:

- `GSWT` support in this repository often depends on payload kinds that are
  richer than the current FeI2 spin-only default bridge contract
- pretending that `GSWT` is a routine automatic FeI2 downstream stage would be
  misleading until the payload contract is explicit

### Thermodynamics Policy

`thermodynamics` should be gated by both route semantics and runtime inputs.

Policy:

- record the route in all cases
- execute automatically only when:
  - route status is `ready`, and
  - required thermodynamics inputs are present
- if route status is `review`, do not auto-execute by default
- if route is `ready` or `review` but inputs are missing, surface that as a
  configuration block rather than a physics-contract block

Rationale:

- thermodynamics needs more than route readiness; it also needs explicit
  parameterization
- `review` should remain visible without silently becoming an implicit execute

## Failure Semantics

`V2b` should use isolated stage failures rather than one monolithic pipeline
failure mode.

Rules:

- if bridge fails, downstream does not begin
- if classical solving fails, downstream does not execute
- if one downstream stage fails, preserve:
  - bridge payload
  - classical solver result
  - other successful downstream stage results
- route evidence should still be written even when one downstream execution
  step fails

This preserves debugging value and avoids making downstream execution errors
look like bridge or classical failures.

## Artifact Contract

`V2b` should add explicit downstream artifacts under the existing
`classical/` output directory.

Suggested files:

- `classical/downstream_routes.json`
- `classical/downstream_results.json`
- `classical/downstream_summary.json`

The final pipeline result should also expose:

- `downstream_status`
- `downstream_routes`
- `downstream_results`
- `downstream_summary`

### Route Artifact Requirements

Each route entry should preserve:

- `status`
- `enabled`
- `reason`
- `recommended_backend`
- `method`
- `role`
- `solver_family`

### Result Artifact Requirements

Each executed stage result should preserve provenance, including:

- `stage_name`
- `route_status_at_execution`
- `backend_selected`
- `execution_policy`
- `input_source`
- `artifacts_written`

This makes it clear whether a stage was:

- auto-run because it was `ready`
- intentionally skipped because it was `review`
- blocked because inputs were missing

## Testing Strategy

`V2b` tests should separate bridge, classical, route, and downstream execution
layers instead of collapsing everything into one fragile end-to-end assertion.

### 1. Pipeline Orchestration Tests

Primary test file:

- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`

Add focused cases that lock:

- `lswt=ready` leads to automatic execution
- `gswt=blocked` is recorded but not executed
- `thermodynamics=review` is recorded but not executed by default
- a downstream execution failure preserves the classical solver result

### 2. Downstream Orchestration Helper Tests

Suggested new test file:

- `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`

This file should focus on:

- route collection
- policy-based stage selection
- `downstream_status` rollup
- summary/provenance structure

### 3. Shared-Layer Compatibility Regressions

Only add narrow regression tests when needed to prove the FeI2 payload shape is
compatible with existing routing/execution helpers.

Do not turn shared routing or execution test files into FeI2-specific policy
test suites.

### 4. Real FeI2 Feature Smoke

Retain a real FeI2 smoke path whose purpose is to verify:

- route artifacts are emitted
- automatic `LSWT` runs when allowed
- non-executed stages remain explicitly explained

The completion criterion is not “every downstream stage passes”; it is “every
stage outcome is explicit and correctly classified.”

## Implementation Slicing

`V2b` should be implemented in this order:

### Task 1: Introduce The Downstream Orchestration Helper

Add one focused helper module that owns:

- route collection
- execution policy
- downstream status rollup
- summary generation

This is the main new boundary in `V2b`.

### Task 2: Integrate The Helper Into The Document-Reader Pipeline

Modify `run_document_reader_pipeline.py` so that:

- classical execution still happens first
- downstream orchestration runs afterward when requested
- the pipeline only coordinates modules and writes artifacts

Do not embed detailed per-stage policy directly into the pipeline file.

### Task 3: Add The Downstream Artifact Contract

Write the new route/result/summary artifacts and mirror those structures into
`final_pipeline_result.json`.

### Task 4: Run Real FeI2 Smoke And Update Docs

After the code path is stable:

- run the real FeI2 smoke
- update the protocol/reference documentation to explain:
  - `V2a` payload assembly
  - `V2b` downstream chaining
  - conservative `GSWT` behavior
  - non-default handling of `review` stages

## Minimal File Surface

### Create

- `translation-invariant-spin-model-simplifier/scripts/common/document_reader_downstream_orchestration.py`
- `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`

### Modify

- `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

### Avoid Changing Unless Required

- `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_routing.py`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_execution.py`

## Completion Criteria

The `V2b` design is complete when all of the following are true:

- `V2b` is clearly defined as downstream orchestration on top of `V2a`
- `LSWT` is the primary auto-run stage
- `GSWT` is routed but remains conservative unless an explicit payload exists
- `thermodynamics` distinguishes route gating from configuration gating
- route, result, summary, and provenance artifacts are all first-class outputs
- implementation work can proceed by adding one orchestration helper, then
  integrating it into the document-reader pipeline

## Relationship To Other FeI2 Bridge Versions

- `V1` proved that a minimal selected-family bridge could be automated
- `V2a` expanded that bridge into a stable shell-expanded and all-family payload
  contract
- `V2b` now turns that stable payload into an explicit downstream workflow
- `V3` still remains the place for broader model-class bridge questions such as
  residual, multipolar, or mixed spin-orbital payloads
