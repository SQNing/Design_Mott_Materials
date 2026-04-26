# CPN Many-Body-HR Multisublattice Site-Pair Recovery Design

## Context

The direct `many_body_hr -> CP^(N-1)` route now has a first canonicalization
baseline:

- `build_pseudospin_orbital_payload.py` emits canonical `bond_blocks`
- raw HR-derived blocks are preserved as provenance under `raw_bond_blocks`
- symmetry-equivalent raw blocks can merge into one canonical orbit-aware block
- downstream consumers can still expand canonical blocks through
  `realize_pseudospin_bond_blocks.py`

That baseline intentionally stops short of one important problem:
multi-sublattice site-pair recovery.

Today the direct route still assumes:

- `source = 0`
- `target = 0`
- `site_pair_encoding = "assumed-single-sublattice-many_body_hr"`

and it explicitly downgrades multi-site structures to `unresolved`. This is the
correct conservative behavior for the current contract, but it means the direct
route still cannot canonicalize many legitimate multisublattice inputs even when
the structure may contain enough information to recover a unique site pair.

The next follow-on should therefore remain narrow:

> upgrade the direct `many_body_hr` route only for the subset of
> multisublattice inputs where `(source, target, translation)` can be recovered
> without ambiguity

This design does **not** pursue inference-heavy or heuristic recovery.

## Goal

Extend the direct `many_body_hr` route so that multisublattice inputs can be
promoted from blanket `unresolved` status to `canonicalized` status **only**
when the site pair for each raw HR block can be recovered uniquely from
`structure + many_body_hr` geometry.

When unique recovery is not possible, the route should remain explicit and
diagnostic-rich:

- no fake `canonicalized` success
- no guessed `source` / `target`
- specific unresolved reasons instead of one generic failure bucket

## Non-Goals

This follow-on does not attempt to:

- infer site pairs heuristically when multiple plausible candidates exist
- redesign the low-level `parse_many_body_hr.py` text parser
- broaden the contract to support speculative multisublattice matching
- solve all remaining direct-route/downstream cleanup in one pass
- change orbit identity to be matrix-driven instead of geometry-driven

The scope is deliberately constrained to conservative, provably unique recovery.

## Core Design Choice

Adopt the conservative success criterion:

> a multisublattice raw HR block may be upgraded only when the candidate set of
> geometry-consistent `(source, target, translation)` assignments has size
> exactly one and remains orbit-consistent downstream.

If the candidate set is empty or has more than one member, the block stays
unresolved.

This means the route will prefer explicit failure over overconfident inference.

## Design

### 1. Treat site-pair recovery as a candidate-enumeration problem

For each raw HR block, the direct route should not jump directly from `R` to a
single site pair. Instead it should:

1. enumerate all geometry-consistent `(source, target, translation)` candidates
2. evaluate whether that candidate set is uniquely resolved
3. pass only uniquely resolved blocks into orbit canonicalization

This keeps the success criterion mechanical and testable.

### 2. Inputs available to the recovery stage

The recovery stage lives at payload-build time, where both HR data and structure
metadata are available. For each raw block it may use:

- `structure.lattice_vectors`
- magnetic basis positions
- symmetry positions/types when available
- raw HR block `R`
- the fact that the route is building a two-site pseudospin/orbital payload

It should **not** use pair-matrix numerical similarity as a primary site-pair
classifier.

### 3. Candidate enumeration rule

For each raw block and for each ordered pair of magnetic basis sites `(i, j)`,
construct the candidate directed bond:

- `source = i`
- `target = j`
- `translation = T`

where `T` is valid only if the translated target position produces the same
geometric bond displacement represented by the raw block under the direct-route
coordinate convention.

The critical rule is:

> all geometry-consistent candidates must be enumerated before any attempt is
> made to declare success

This prevents the implementation from silently treating the first plausible
match as the true one.

### 4. Uniqueness rule

A raw block is considered successfully recovered only when:

- the candidate set size is exactly `1`
- the unique candidate remains stable when fed into orbit decomposition
- the resulting orbit assignment does not create conflicting membership with
  other raw HR blocks

If the candidate set size is `0` or `>1`, or if orbit consistency later breaks,
the block must not be promoted to resolved status.

### 5. Failure partitioning

This follow-on should replace the current one-bucket multisublattice unresolved
diagnostic with more specific reasons:

- `no-candidate-site-pair`
- `multiple-candidate-site-pairs`
- `orbit-membership-ambiguous`
- `orbit-closure-failed`

These reasons should appear in diagnostics so tests and future debugging can
distinguish geometric failure from orbit-level failure.

### 6. Contract-layer placement

This recovery should happen at payload-build time, not in the bare HR parser and
not in the downstream compatibility helper.

Recommended split:

- `build_pseudospin_orbital_payload.py`
  - builds raw HR-derived blocks
  - runs site-pair candidate enumeration
  - annotates each raw block with recovery status
- `canonicalize_pseudospin_bond_orbits.py`
  - consumes only uniquely recovered site-pair blocks for canonicalization
  - aggregates unresolved diagnostics for the rest

This keeps responsibilities clean:

- payload builder: site-pair recovery
- canonicalizer: orbit decomposition
- downstream helper: compatibility expansion

### 7. Minimal contract changes

This follow-on should not introduce a large new schema. It only needs a small
set of additional fields.

For raw/provenance blocks:

- `site_pair_resolution`
- `candidate_site_pairs` when unresolved

For the top-level payload:

- `canonicalization_status`
- `diagnostics`

Canonical blocks may continue using the fields already introduced in the first
baseline:

- `orbit_id`
- `orbit_representative`
- `orbit_members`
- `raw_block_refs`

## Status Semantics

### `canonicalized`

Use only when all raw blocks relevant to the produced canonical blocks have
uniquely recovered site pairs and passed orbit-level checks.

### `partial`

This follow-on may use `partial` if the implementation later chooses to allow a
mixed payload containing both canonicalized and unresolved subsets. However, the
first pass does not need to force that behavior unless it naturally falls out of
the implementation.

### `unresolved`

Use when the route cannot honestly recover unique site pairs for the multisite
input under the conservative rule.

For this design, `unresolved` remains the correct result whenever ambiguity
persists.

## Testing Strategy

The first RED tests should focus on the new conservative recovery behavior.

### 1. Unique multisublattice recovery success

Add a failing test where a multisublattice structure and raw HR block produce
exactly one geometry-consistent `(source, target, translation)` candidate.

Assert that:

- the raw block gets `site_pair_resolution = "unique"`
- canonicalization proceeds
- the final payload reports `canonicalization_status = "canonicalized"`

### 2. Multiple-candidate unresolved case

Add a failing test where more than one candidate site pair is geometry-consistent.

Assert that:

- no guessed `source` / `target` is emitted as authoritative
- diagnostics record `multiple-candidate-site-pairs`
- the payload remains `unresolved`

### 3. No-candidate unresolved case

Add a failing test where no site-pair candidate is geometry-consistent.

Assert that:

- diagnostics record `no-candidate-site-pair`
- the payload remains `unresolved`

### 4. Orbit-level ambiguity case

Add a failing test where a unique local candidate exists but orbit assignment
cannot remain uniquely consistent.

Assert that:

- diagnostics record `orbit-membership-ambiguous` or `orbit-closure-failed`
- the route does not promote the block to canonicalized success

### 5. Downstream compatibility preservation

Retain at least one focused downstream test proving that once multisublattice
recovery succeeds, the resulting canonical blocks still expand correctly through
`realize_pseudospin_bond_blocks.py`.

## Expected Outcome

After this follow-on, the direct `many_body_hr` route will no longer treat all
multisublattice inputs as equally hopeless. Instead it will:

- canonicalize the subset that can be recovered without ambiguity
- keep the rest unresolved with specific reasons
- preserve a clean, conservative contract boundary

This provides a principled bridge between the current single-sublattice-safe
baseline and any future, broader multisublattice support.
