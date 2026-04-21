# FeI2 V2a Shell Expansion And All-Family Assembly Design

## Goal

Extend the current FeI2 V1 document-reader solver bridge into a broader spin-only payload assembly stage that can:

- expand one selected supported family from a single representative bond into a full shell-resolved bond set
- assemble `selected_local_bond_family = "all"` into one stable multi-family spin-only solver payload
- preserve enough provenance and routing metadata for later classical and downstream consumers

This design is intentionally limited to payload assembly. It does not yet add automatic LSWT / GSWT / thermodynamics chaining.

## Why V2a Exists

V1 proved the missing bridge can be automated:

- a selected readable spin-only block can be converted into a solver-ready payload
- the pipeline can emit artifacts and optionally run the classical solver
- the real FeI2 `2a'` case can reproduce the previously hand-built LT smoke result

However, V1 intentionally stops at one deterministic representative bond. That is sufficient for a smoke path, but it is not yet a faithful shell-level spin-only model or a stable basis for `selected_local_bond_family = "all"`.

V2a is the next coherent expansion because it stays within the same physics contract:

- readable spin-only bilinear exchange blocks
- lattice shell geometry
- classical solver payloads built from `3x3` bond matrices

## In Scope

### Supported Model Classes

V2a remains limited to readable spin-only bilinear block types that already map cleanly into a `3x3` exchange matrix:

- `isotropic_exchange`
- `xxz_exchange`
- `symmetric_exchange_matrix`
- `exchange_tensor`

### Supported User Modes

- single selected family with full shell expansion
- `selected_local_bond_family = "all"` aggregation over all supported families present in the current readable model

### Required Output

V2a must produce a stable solver payload containing:

- expanded `bonds`
- family- and shell-level provenance
- routing hints required for the current classical solver layer
- explicit bridge metadata describing whether the payload is:
  - a single-family expanded model
  - an all-family aggregated model

## Explicitly Out Of Scope

These remain outside V2a and belong to later versions:

- automatic LSWT / GSWT / thermodynamics execution
- residual-term promotion into the spin-only solver payload
- multipolar bridge contracts
- mixed spin-orbital bridge contracts
- partial-support semantics that silently drop unsupported families from an `all` request

## Current-State Constraints

The repository now contains:

- a V1 bridge builder at
  `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- shell geometry helpers at
  `translation-invariant-spin-model-simplifier/scripts/common/lattice_geometry.py`
- shell-resolved readable assembly behavior in
  `translation-invariant-spin-model-simplifier/scripts/simplify/assemble_effective_model.py`

Important facts from V1 that V2a must preserve:

- a selected-family readable block may not repeat its `family` field after user selection has already narrowed the model
- solver auto-routing depends on preserving `effective_model` and `simplified_model` hints in the emitted payload
- shell geometry is currently inferred from lattice vectors and positions; the bridge must stay consistent with that geometry machinery

## Design Summary

V2a introduces two layers above the current V1 bridge:

1. **Family shell expansion**
   Convert one selected readable spin-only family block into all canonical bond pairs belonging to that shell.

2. **All-family assembly**
   Convert all bridgeable family blocks into one aggregated solver payload with stable ordering and explicit per-family summaries.

The new architecture should look like:

```text
document-reader simplification
  -> readable spin-only family blocks
  -> family shell expansion builder
  -> optional all-family payload assembler
  -> spin-only classical payload
```

## Core Design Choice

V2a should not rewrite the V1 builder into one monolithic function.

Instead, it should split responsibilities into smaller units:

- a block-to-matrix mapper
- a family shell expander
- an all-family assembler
- a thin public bridge entry point

This keeps:

- single-family shell logic testable in isolation
- `all` aggregation rules separate from shell geometry rules
- future V2b downstream chaining free to consume one stable assembled payload contract

## Input Source Precedence

V2a should treat **per-family readable blocks** as the authoritative bridge input whenever they are present.

That means:

- if `effective_model.main` contains individual family-resolved readable blocks, the bridge should consume those blocks directly
- `shell_resolved_exchange` should be treated as:
  - a stable ordering hint
  - a summary/checkpoint for cross-validation
  - a reporting-friendly mirror
- `shell_resolved_exchange` should become the primary bridge source only when the underlying family-resolved readable blocks are not otherwise available

This rule keeps single-family and all-family bridge logic aligned:

- both modes ultimately consume the same family-level readable block contract
- shell summaries help with ordering and validation without becoming the only source of truth

If the family-resolved blocks and the shell summary disagree on:

- family membership
- shell ordering
- block type

the builder should fail explicitly rather than silently prefer one inconsistent representation.

## Proposed Components

### 1. Family Shell Expansion Helper

Purpose:

- accept one selected readable family block
- look up the target shell in `family_shell_map`
- enumerate all raw shell pairs via existing lattice geometry helpers
- canonicalize and de-duplicate those pairs
- emit one bond per canonical pair with the readable block's `3x3` exchange matrix

Suggested module placement:

- extend `build_spin_only_solver_payload.py`, or
- split helper logic into a sibling module if the file grows too large

Expected output for one family:

```json
{
  "family": "2a'",
  "shell_index": 6,
  "distance": 9.736622,
  "pair_count": 6,
  "bonds": [
    {
      "source": 0,
      "target": 0,
      "vector": [1, -1, 1],
      "distance": 9.736622,
      "shell_index": 6,
      "family": "2a'",
      "matrix": [[0.068, 0.0, 0.0], [0.0, 0.068, 0.0], [0.0, 0.0, 0.073]]
    }
  ]
}
```

### 2. All-Family Assembler

Purpose:

- read all bridgeable readable spin-only family blocks
- expand each family independently
- concatenate expanded bond sets in a stable order
- preserve per-family summaries

Stable family order should come from shell order when available:

1. ascending `shell_index`
2. textual family label as tiebreaker

This mirrors the existing shell-resolved readable reporting order and avoids unstable payload diffs.

### 3. Public V2a Bridge Entry Point

The public builder should accept both modes:

- one selected family
- `all`

It should decide:

- if selected family is one label: expand just that family
- if selected family is `all`: build the aggregated payload

It should reject requests when:

- zero bridgeable families are present
- one or more requested families map to unsupported readable block types
- geometry expansion cannot recover the declared shell

## Data Contract

### Single-Family Expanded Payload

The V2a single-family expanded payload should preserve the V1 top-level shape, but update metadata:

```json
{
  "lattice": {...},
  "local_dim": 3,
  "normalized_model": {...},
  "effective_model": {...},
  "simplified_model": {
    "template": "xxz"
  },
  "bonds": [... full expanded shell bonds ...],
  "classical": {
    "method": "auto"
  },
  "bridge_metadata": {
    "bridge_kind": "document_reader_spin_only_shell_expanded",
    "expansion_mode": "full_shell",
    "selected_family": "2a'",
    "block_type": "xxz_exchange",
    "shell_index": 6,
    "pair_count": 6
  }
}
```

### All-Family Aggregated Payload

The aggregated payload should add family-level bookkeeping:

```json
{
  "lattice": {...},
  "local_dim": 3,
  "normalized_model": {...},
  "effective_model": {...},
  "simplified_model": {
    "template": "generic"
  },
  "bonds": [... all expanded supported families ...],
  "classical": {
    "method": "auto"
  },
  "bridge_metadata": {
    "bridge_kind": "document_reader_spin_only_all_family_assembled",
    "expansion_mode": "all_families",
    "selected_families": ["1", "0'", "2", "1'", "3", "2a'"],
    "family_order": ["1", "0'", "2", "1'", "3", "2a'"],
    "family_summaries": [
      {
        "family": "1",
        "shell_index": 1,
        "block_type": "symmetric_exchange_matrix",
        "pair_count": 3
      }
    ]
  }
}
```

## Simplified Template Rule

For one-family payloads, `simplified_model.template` should continue to reflect the one selected readable block.

For `all` payloads, the template should not pretend the aggregate model is more specific than it is.
If all assembled families share one readable block class and that class admits one meaningful template, the implementation may keep that template. Otherwise it should normalize to a broader stable value such as `generic`.

The important rule is:

- never lie for the sake of prettiness
- keep enough hints for solver routing
- do not collapse heterogeneous multi-family assembled models into a misleading narrow template

## Error Handling

### Single-Family Mode

Return explicit errors for:

- missing `family_shell_map` metadata
- unsupported readable block type
- shell enumeration mismatch
- selected family not present in readable output and not inferable from single-block selected context

### All-Family Mode

V2a should be strict by default.

If `selected_local_bond_family = "all"` is requested and any family in the readable output is not bridgeable:

- return an explicit error listing the unsupported families
- do not silently drop them

This is important because otherwise the aggregated payload would appear physically complete when it is not.

## Testing Strategy

### Unit Tests

Add tests for:

- full-shell expansion emits more than one bond for a shell with multiple canonical pairs
- expanded bonds carry stable `family`, `shell_index`, and `distance`
- selected-family context is still accepted when the readable block omits repeated `family`
- `all` payloads preserve stable family ordering
- `all` payloads reject mixed support when one family is unbridgeable

### Integration Tests

Add tests for:

- FeI2 single-family `2a'` expanded payload generation
- FeI2 `all` payload generation from current readable output
- preservation of `effective_model` and `simplified_model` hints in both modes

### Not Yet In V2a Tests

Do not make V2a completion depend on:

- LSWT success
- GSWT success
- thermodynamics success

Those belong to V2b.

## Acceptance Criteria

V2a is complete when all of the following are true:

- the bridge can expand one supported selected family into a full shell bond set
- the bridge can assemble `selected_local_bond_family = "all"` into one stable aggregated payload for supported readable families
- the payload preserves the provenance and routing hints needed by the existing classical solver layer
- unsupported families in `all` mode fail explicitly rather than being silently dropped
- FeI2 single-family and all-family cases have regression coverage

## Deferred To V2b

Once V2a is stable, V2b should consume the V2a payload contract and add:

- automatic LSWT chaining when routing says `ready`
- thermodynamics chaining when routing says `ready` or approved `review`
- any carefully justified GSWT chaining that matches the current state semantics

That later stage should treat V2a payload assembly as a finished dependency rather than re-defining the assembly contract.
