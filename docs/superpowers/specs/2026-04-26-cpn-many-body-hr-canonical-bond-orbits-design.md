# CPN Many-Body-HR Canonical Bond Orbits Design

## Context

The `CP^(N-1)` pseudospin-orbital route now has a shared downstream realization
helper in
`translation-invariant-spin-model-simplifier/scripts/common/realize_pseudospin_bond_blocks.py`.
Core consumers such as the classical model builder, GSWT payload builders,
simplification, grouping, and report/pipeline layers already rely on that helper
to turn a family-level representative bond into its full directed-bond orbit.

However, the direct `many_body_hr` route still enters the pipeline in a weaker
form. `build_pseudospin_orbital_payload.py` currently emits raw `bond_blocks`
directly from `R -> pair_matrix` data, with `source = target = 0` and without a
first-class symmetry/orbit identity. In practice this means:

- the direct `many_body_hr` route remains metadata-poor relative to the
  document-reader route
- the payload contract still treats raw `R`-resolved blocks as the primary bond
  object
- downstream stages must either infer family/orbit semantics late or accept a
  permanently weaker upstream contract

The desired end state is stronger than simply adding one more top-level map. The
direct `many_body_hr` route should be upgraded so that the primary bond object
is already symmetry-aware and canonicalized.

## Goal

Promote canonical symmetry-identified bond-orbit blocks to the primary
`CP^(N-1)` payload object for the direct `many_body_hr` route, while demoting raw
`R`-resolved HR blocks to provenance/debug status.

In the successful case, downstream consumers should receive a payload whose main
`bond_blocks` already encode:

- which directed bonds belong to the same symmetry orbit
- which representative bond defines that orbit
- which raw HR entries contributed to the canonical orbit block
- whether orbit-level matrix consistency checks passed

## Non-Goals

This design does not attempt to:

- redesign the low-level `parse_many_body_hr.py` text parser
- solve fully general multi-sublattice source/target recovery beyond the
  information actually available from the payload-building context
- infer bond families from pair-matrix numerical similarity
- replace space-group orbit classification with shell-distance heuristics
- remove all backward compatibility in one step for existing downstream
  consumers

The low-level parser remains responsible for reading `R -> matrix` data. The
new symmetry/orbit upgrade belongs at the payload-building layer where both HR
data and structure metadata are available.

## Core Design Choice

Adopt the aggressive `C` direction:

> The direct `many_body_hr` route should no longer treat raw `R`-resolved bond
> blocks as the semantic primary object. The primary object becomes a canonical
> bond-orbit block identified by symmetry.

Raw HR blocks still exist, but as provenance/debug data rather than as the main
bond contract consumed by classical, GSWT, simplify, and report stages.

This is intentionally stronger than simply adding a
`family_representative_map`. If raw `R` blocks remain the primary object, then
the route has not really been upgraded; it has only gained supplemental
metadata.

## Design

### 1. Canonical orbit-aware bond blocks become the primary contract

For the direct `many_body_hr` route, the payload should expose canonical
symmetry-identified orbit blocks as the main `bond_blocks` collection.

Each canonical block represents one directed-bond symmetry orbit rather than one
isolated raw HR entry. The payload should also preserve raw provenance, but not
as the semantic primary object.

Recommended payload split:

- `bond_blocks`
  - canonical orbit-aware blocks used by downstream consumers
- `raw_bond_blocks` or `source_hr_blocks`
  - original raw `R`-resolved entries retained only for provenance/debugging

### 2. Bond identity is geometric, not raw-`R` or matrix-based

The stable identity of a candidate bond is the directed triple:

- `source`
- `target`
- `translation`

Symmetry classification should be based on space-group action on those directed
triples, not on:

- raw `R` vectors alone
- pair-matrix equality
- shell distance alone

The existing reusable mechanism in
`translation-invariant-spin-model-simplifier/scripts/common/bond_orbits.py`
already provides the right foundation. It generates directed-bond orbits by
applying spglib symmetry operations to a representative bond.

### 3. Canonical orbit blocks are constructed in four steps

#### Step 1: Resolve magnetic-basis geometry

The payload-building layer must first resolve the structure information needed
for symmetry classification:

- `lattice_vectors`
- magnetic basis positions
- `symmetry_positions`
- `symmetry_types`

If these are not available in sufficiently trustworthy form, the route cannot
honestly claim full canonicalization.

#### Step 2: Form candidate directed bonds

Raw HR data should be lifted from pure `R -> pair_matrix` entries into candidate
directed-bond objects:

- `source`
- `target`
- `translation`
- `pair_matrix`

This design explicitly rejects a future where the direct route permanently hard
codes `source = target = 0` as if that were the full semantic identity of every
bond.

#### Step 3: Decompose candidates into symmetry orbits

For each candidate representative bond, use the structure-aware symmetry/orbit
machinery to generate its directed-bond orbit. Canonical blocks are then formed
by grouping all members that belong to the same orbit.

Each canonical block should carry:

- `orbit_id`
- `orbit_representative`
- `orbit_members`
- `orbit_size`

Family labels, if present, are naming/contract metadata layered on top of the
orbit identity rather than the defining classification rule.

#### Step 4: Attach matrices and provenance to the canonical block

After orbit identity is fixed geometrically, attach the HR matrix data to the
canonical block:

- choose the representative member's matrix as the canonical `pair_matrix`
- retain references to all contributing raw HR entries
- check whether the other orbit members remain contract-consistent with the
  representative under the current basis/convention assumptions

This gives each canonical block both a clean semantic identity and explicit
traceability back to the raw HR inputs.

### 4. Canonical block schema

The exact field names can still be tuned during implementation, but each
canonical block should contain at least:

- `family`
- `orbit_id`
- `orbit_representative`
- `orbit_members`
- `pair_matrix`
- `coordinate_convention`
- `matrix_consistency`
- `raw_block_refs`

And the top-level payload should include:

- `canonicalization_status`
- canonical bond blocks as the main `bond_blocks`
- raw provenance blocks under a separate debug/provenance key

### 5. Matrix data is attached to an orbit; it does not define the orbit

This is a key contract rule.

Orbit identity comes from symmetry acting on directed bonds. Matrix equality or
similarity is not the classifier. Matrix information is used afterwards for:

- canonical representative selection
- consistency checking
- diagnostics

If two bonds belong to the same geometric orbit but their attached matrices are
not contract-consistent, that is a diagnosable error state, not a reason to
silently split the orbit by numerical appearance.

## Failure And Downgrade Semantics

The route should use three explicit top-level statuses.

### `canonicalized`

Use when:

- structure/symmetry inputs are sufficient
- source/target/translation assignment is resolved
- raw blocks can be mapped to symmetry orbits
- orbit-level matrix consistency checks pass

In this state, the main `bond_blocks` are trustworthy canonical orbit blocks.

### `partial`

Use when:

- canonical orbit output is still useful
- but some orbit naming, block assignment, or matrix checks are incomplete or
  provisional

This state must remain visibly incomplete. The payload should include explicit
diagnostics such as:

- `unresolved_blocks`
- `inconsistent_orbits`
- `diagnostics`

### `unresolved`

Use when:

- structure/symmetry information is not sufficient for stable orbit generation
- source/target recovery fails
- raw blocks cannot be uniquely assigned
- orbit consistency breaks down too broadly to support a trustworthy canonical
  contract

In this state the route should not pretend success. It may retain
`raw_bond_blocks`, but it should not claim that canonical bond-orbit blocks have
been established.

## Compatibility Strategy

This design changes the primary meaning of `bond_blocks` for the direct
`many_body_hr` route, so compatibility must be staged carefully.

The first compatibility goal is not to migrate every consumer at once. It is to
ensure that at least one core downstream consumer can correctly interpret the
new canonical contract, either directly or through a focused compatibility
adapter.

The current shared realization helper,
`realize_pseudospin_bond_blocks.py`, should likely move from "infer/expand
representative-family blocks" toward "compatibility expansion for canonical
orbit-aware blocks", but the exact transition can remain incremental.

## Testing Strategy

The first RED tests should pin the contract, not broad workflow coverage.

### 1. Canonicalized success case

Write a failing test showing that, for a symmetry-resolvable direct
`many_body_hr` input, the primary `bond_blocks` are already canonical
orbit-aware blocks and the payload reports:

- `canonicalization_status = "canonicalized"`
- per-block `orbit_representative`
- per-block `orbit_members`
- per-block `coordinate_convention`

### 2. Orbit merge case

Write a failing test showing that multiple raw HR entries that are symmetry
equivalent merge into a smaller number of canonical orbit blocks, with explicit
provenance retained through `raw_block_refs`.

### 3. Honest downgrade case

Write a failing test showing that insufficient symmetry/structure information
does not produce a fake canonical success. The route must report either
`partial` or `unresolved` and include explicit diagnostics.

### 4. Downstream compatibility case

Write a failing test for at least one core downstream consumer, preferably the
classical model builder, proving that the new canonical bond-block contract is
either consumed directly or supported through a narrow compatibility layer.

## Expected Outcome

After this design is implemented, the direct `CP^(N-1)` `many_body_hr` route
will no longer be a permanently metadata-poor exception in the pipeline. It
will produce a canonical symmetry-aware bond contract whose primary bond objects
already reflect orbit identity, provenance, and diagnostics.

That puts the direct route and the document-reader route on a much closer
semantic footing and removes the need for downstream stages to treat raw
`R`-resolved bond blocks as the fundamental model object.
