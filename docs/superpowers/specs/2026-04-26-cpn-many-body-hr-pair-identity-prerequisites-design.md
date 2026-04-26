# CPN Many-Body-HR Pair Identity Prerequisites Design

## Context

The direct `many_body_hr -> CP^(N-1)` route recently gained a first
pre-aggregation identity layer:

- `parse_many_body_hr.py` now preserves finer-grained `entries`
- those entries retain per-row identity such as:
  - `row_index`
  - `R`
  - `m`
  - `n`
  - `value`
- `build_pseudospin_orbital_payload.py` now exposes:
  - `raw_hr_entries`
  - `entry_refs` on `raw_bond_blocks`

Those changes are useful and should stay. They establish that the direct route
no longer relies *only* on already-grouped `blocks_by_R` as its earliest
recoverable object.

However, this new identity layer is still not the right object for conservative
multisublattice symmetry classification.

Why not:

- the preserved entries are still matrix-element identity, not bond-pair identity
- they tell us which matrix slot contributed, but not which directed bond
  `(source, target, translation)` that slot belongs to
- multisublattice symmetry partition acts on directed bonds, not on:
  - bare `R`
  - or matrix-entry coordinates `(m, n)` alone

So the earlier corrected follow-on,
"preserve pre-aggregation bond identity before `R` collapse," was a step in the
right direction but still too optimistic at the current parser boundary.

What we actually have now is:

> pre-aggregation matrix-entry identity preservation

What we still do **not** have is:

> pre-aggregation pair identity preservation

That distinction matters enough that it needs its own design.

## Goal

Define the missing prerequisites for moving from preserved matrix-entry identity
to preserved bond-pair identity in the direct `many_body_hr` route.

The purpose of this follow-on is not to fake multisublattice orbit
classification from the wrong object. Its purpose is to specify what upstream
contract change is required before conservative directed-bond classification can
honestly happen.

## Non-Goals

This design does not attempt to:

- classify multisublattice directed-bond orbits from the current `entries`
  alone
- infer `(source, target)` from matrix-entry indices `(m, n)` without an
  explicit physical mapping
- claim that pre-aggregation matrix entries are already sufficient for bond
  identity
- redesign the downstream canonical orbit contract that is already working for
  the single-sublattice-safe baseline

The scope is specifically about identifying the next missing upstream contract
piece.

## Core Design Choice

Separate three layers explicitly:

1. `R`-grouped block identity
2. matrix-entry identity
3. bond-pair identity

The first two are now available. The third is not.

The crucial conclusion is:

> conservative multisublattice symmetry classification must wait until the
> direct route preserves pair identity, not merely matrix-entry identity

This prevents the project from overclaiming what the current parser-side data
can support.

## Design

### 1. Recognize matrix-entry identity as an intermediate success, not the final object

The recently landed `entries` layer is still valuable:

- it preserves provenance before full `R` aggregation
- it makes later contract upgrades possible
- it lets payloads link canonical or raw blocks back to concrete HR rows

But it is still an intermediate layer.

It answers:

- which file row contributed?
- which `R` did it belong to?
- which local matrix slot `(m, n)` did it fill?

It does **not** answer:

- which physical site pair did this contribution represent?
- which directed bond orbit should it belong to in a multisublattice lattice?

### 2. The missing object is a pair-identity-bearing upstream contract

Before conservative multisublattice classification can proceed, the direct route
needs access to a richer object that can preserve or derive something like:

- `source_site_index`
- `target_site_index`
- `translation`
- or an equivalent upstream pair label that can be mapped to that triple

The exact origin of this richer identity is still open, but one of the
following must become true:

- the low-level input itself carries pair identity
- an adjacent upstream artifact maps retained-basis matrix slots onto explicit
  site-pair structure
- a deterministic and formally justified bridge exists between matrix-entry
  indices and pair identity

Without one of those, pair identity does not exist in the current contract in a
conservative sense.

### 3. Do not overload `(m, n)` with physical meaning it does not currently have

A major risk is to look at the preserved matrix-entry indices and pretend they
already encode physical site-pair structure.

This design explicitly rejects that shortcut unless an upstream contract proves
it.

Why:

- `(m, n)` indexes matrix slots in the Wannier/retained basis representation
- that is not automatically the same thing as magnetic-sublattice pair identity
- forcing that interpretation without a declared mapping would create fragile,
  hidden assumptions

If a future bridge between `(m, n)` and bond-pair structure is introduced, it
must be explicit, documented, and tested.

### 4. The next real follow-on is upstream contract discovery or introduction

So the next honest engineering target is not:

- "finish multisublattice orbit classification"

It is:

- "identify or introduce the upstream contract that preserves physical pair identity"

That follow-on may involve:

- discovering that another existing file/artifact already carries the missing
  site-pair mapping
- teaching the parser-side boundary to read a richer upstream representation
- defining a new explicit sidecar metadata surface

Only after that should a new multisublattice directed-bond classification plan
be written.

### 5. Keep the current baseline and current corrected artifacts

This design does not invalidate the already landed work:

- parser-side `entries`
- payload-level `raw_hr_entries`
- `entry_refs`
- canonical orbit baseline for the single-sublattice-safe case

Those should remain in place. They are the correct substrate for the next real
contract upgrade.

The key correction is conceptual:

- do not confuse "kept matrix-entry identity" with "kept pair identity"

## Consequences For Existing Specs And Plans

The earlier corrected follow-on spec and plan about
pre-aggregation bond identity preservation were directionally better than the
older post-hoc site-pair-recovery idea, but they still reached one step too far.

They assumed that preserving a finer-grained parser-side object would be enough
to support directed-bond classification.

This design supersedes that assumption.

What remains valid from those documents:

- information must be preserved earlier than `blocks_by_R`
- bare `R` is not the right multisublattice symmetry object
- conservative classification must avoid guessing

What changes:

- the newly preserved parser-side object is now recognized as matrix-entry
  identity, not pair identity
- the next plan should target upstream pair-identity prerequisites rather than
  premature orbit classification

## Testing Strategy

The next RED tests should target honesty of the boundary, not fake
multisublattice success.

### 1. Boundary-honesty test

Add or keep a test proving that the direct route preserves `entries` /
`raw_hr_entries`, but does **not** yet claim multisublattice directed-bond
classification from them.

### 2. Pair-identity-missing diagnostic test

Add a test for a multisublattice input asserting that diagnostics can
distinguish:

- "matrix-entry identity preserved"
- from
- "pair identity still unavailable"

The exact phrasing can change, but the contract should no longer hide this
distinction.

### 3. Future-bridge placeholder test

Add a narrow failing test only when an actual upstream pair-identity-bearing
artifact or mapping is identified.

Do **not** write a fake multisublattice orbit-classification RED test before the
necessary upstream contract exists.

## Expected Outcome

After this design is adopted, the project will have a more honest and more
stable roadmap:

- current landed work is recognized as successful preservation of matrix-entry
  provenance
- the remaining blocker is correctly identified as missing pair identity
- the next follow-on can focus on upstream contract discovery/introduction
  instead of trying to over-infer from the wrong object

This keeps the multisublattice story technically coherent and avoids writing
tests or code that pretend the current parser boundary knows more physics than
it actually does.
