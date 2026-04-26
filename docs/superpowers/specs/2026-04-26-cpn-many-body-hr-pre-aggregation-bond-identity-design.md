# CPN Many-Body-HR Pre-Aggregation Bond Identity Design

## Context

The direct `many_body_hr -> CP^(N-1)` route now has a first canonicalization
baseline for the single-sublattice-safe case:

- raw HR-derived blocks are preserved as provenance under `raw_bond_blocks`
- canonical `bond_blocks` can be formed from directed-bond symmetry orbits
- symmetry-equivalent raw blocks can merge into one canonical orbit-aware block
- downstream consumers can still expand canonical blocks through
  `realize_pseudospin_bond_blocks.py`

That baseline also revealed a hard limit for multisublattice inputs:

- the low-level direct route currently parses `many_body_hr` into `blocks_by_R`
- `build_pseudospin_orbital_payload.py` therefore starts from one aggregated
  matrix per `R`
- no explicit `(source, target)` identity survives that aggregation step

This matters because multisublattice symmetry classification is not defined on
bare `R` vectors. It is defined on directed bonds:

- `source`
- `target`
- `translation`

In a multisublattice lattice, different site pairs can legitimately share the
same `R` while belonging to different directed-bond orbits. Once they have been
collapsed into a single `R`-block object, conservative post-hoc recovery of
pair-level identity is generally no longer possible.

This means the previous narrow follow-on idea,
"recover unique multisublattice `(source, target)` from already-collapsed
`R`-blocks", is the wrong boundary for a conservative design.

The correct follow-on is earlier in the pipeline:

> preserve bond identity before `R`-level aggregation so multisublattice
> symmetry classification can act on directed bonds rather than on already
> collapsed `R` blocks

## Goal

Redesign the direct `many_body_hr` route so it preserves pre-aggregation
bond-level identity for each two-site contribution before the route collapses
everything into one block per `R`.

This should give the direct route a payload-building boundary where
multisublattice symmetry classification can operate on directed bonds
`(source, target, translation)` rather than on already-aggregated `R` blocks.

## Non-Goals

This follow-on does not attempt to:

- solve multisublattice classification by guessing from already-collapsed `R`
  blocks
- infer pair identity from pair-matrix numerical similarity
- redesign the full downstream canonical orbit contract that already exists
- solve arbitrary heuristic recovery from incomplete structure metadata
- finish all remaining direct-route cleanup in one pass

The scope is specifically about preserving the right object earlier, not about
doing broader inference later.

## Core Design Choice

Move the key identity boundary earlier:

> for multisublattice support, the direct `many_body_hr` route must preserve
> pre-aggregation bond identity before `blocks_by_R` becomes the primary model
> object

Equivalently:

- single-sublattice-safe canonicalization can continue from `R`-grouped data
- multisublattice-safe canonicalization requires bond-level identity prior to
  `R`-only aggregation

This follows directly from the symmetry object itself: space-group action
classifies directed bonds, not bare `R` blocks.

## Design

### 1. Distinguish two layers of direct-route data

The direct route should no longer jump straight from parsed HR text to one
payload collection of `bond_blocks`.

Instead it should expose two explicit internal layers:

1. `raw_hr_entries`
   - the finest-grained site-pair-resolved contributions available before
     aggregation
2. `raw_bond_blocks`
   - the current higher-level grouped form used as provenance/debug or as a
     legacy compatibility surface

This gives the multisublattice path a chance to classify directed bonds before
information is erased by grouping.

### 2. Preserve pre-aggregation identity in the parser-side contract

The current `parse_many_body_hr.py` output is too coarse:

- `R_vectors`
- `blocks_by_R`

The follow-on should extend that boundary, or add an adjacent helper directly
next to it, so the direct route can retain a more atomic representation of the
HR data before forming `blocks_by_R` as the only object.

The exact low-level shape can still be tuned, but it must preserve enough
identity to carry:

- site-pair slot or pair index identity
- `R`
- the matrix contribution or its equivalent block assignment

The critical rule is not the exact field names. The critical rule is that the
route must not irreversibly discard pair-level distinctions before the
multisublattice classifier has seen them.

### 3. Multisublattice symmetry classification acts on directed bonds

Once pre-aggregation identity is available, the payload-building layer can
construct candidate directed bonds:

- `source`
- `target`
- `translation`

and classify them by symmetry using the existing orbit machinery in
`scripts/common/bond_orbits.py`.

This is the correct place for multisublattice symmetry partitioning.

For multisublattice inputs, the route should therefore:

1. start from pre-aggregation bond-level entries
2. assign or preserve candidate directed-bond identity
3. classify by directed-bond orbit
4. only then aggregate to canonical orbit-aware blocks

### 4. Do not use bare `R` as the multisublattice family object

This follow-on should explicitly reject the old accidental assumption:

> one `R` implies one bond family

That is only safely true in special single-sublattice-like situations.

For multisublattice lattices, the route must allow:

- multiple distinct directed-bond identities sharing the same `R`
- different orbits sharing the same `R`
- symmetry partitioning that depends on `(source, target, translation)` rather
  than on `R` alone

### 5. Keep the current canonicalizer, but feed it better objects

The new work should avoid rewriting the entire canonicalization layer if
possible.

Preferred architecture:

- earlier layer preserves pre-aggregation bond identity
- payload builder constructs directed-bond candidates from that richer object
- `canonicalize_pseudospin_bond_orbits.py` consumes those directed-bond-aware
  raw blocks

This keeps the largest conceptual change at the right boundary: before
information collapse, not after.

### 6. Minimal contract impact

The first implementation pass should add only the minimum new surfaces needed to
preserve pre-aggregation identity.

Likely new or revised surfaces:

- parser-side or parser-adjacent entry list before `blocks_by_R`
- payload-builder access to that entry list
- provenance on canonical blocks linking back to those finer-grained entries

The route does not need to delete `blocks_by_R`. It only needs to stop treating
that grouped object as the earliest recoverable truth.

## Consequences For The Previous Follow-On

The earlier multisublattice site-pair-recovery spec assumed that conservative
pair recovery could happen after the route had already collapsed to one block
per `R`.

This design supersedes that assumption.

What remains valid from the earlier thinking:

- multisublattice symmetry classification must remain conservative
- diagnostics must distinguish different failure modes
- no guessed `source` / `target` should be emitted as authoritative

What changes:

- the decisive follow-on boundary is now earlier
- the key implementation task is identity preservation before aggregation
- post-hoc recovery from fully collapsed `R` blocks is no longer the primary
  plan target

## Testing Strategy

The first RED tests should prove that the route preserves finer-grained identity
before `R`-aggregation and uses it in multisublattice classification.

### 1. Parser-side or parser-adjacent pre-aggregation identity test

Add a failing test showing that the direct route can retain a list of
pre-aggregation HR entries rather than only `blocks_by_R`.

Assert that:

- entries preserve `R`
- entries preserve enough pair-level identity to remain distinguishable before
  aggregation

### 2. Same-`R`, different-pair distinction test

Add a failing test for a synthetic multisublattice example where two distinct
directed-bond candidates share the same `R`.

Assert that:

- they remain separate before canonical orbit aggregation
- the route does not prematurely merge them just because `R` matches

### 3. Directed-bond-orbit classification test

Add a failing test proving that multisublattice classification uses
`(source, target, translation)` rather than just `R`.

Assert that:

- canonicalization distinguishes different directed-bond orbits even when `R`
  is shared
- provenance links canonical blocks back to the finer-grained pre-aggregation
  entries

### 4. Legacy single-sublattice compatibility test

Retain or add a failing test proving that the current single-sublattice-safe
baseline still works after introducing the richer pre-aggregation layer.

## Expected Outcome

After this follow-on, the direct `many_body_hr` route will stop treating
`blocks_by_R` as the earliest trustworthy object for all cases.

Instead it will:

- preserve finer-grained bond identity before aggregation
- enable conservative multisublattice symmetry classification on directed bonds
- keep the current canonical orbit contract as the downstream target
- avoid the impossible task of reconstructing lost pair identity from already
  collapsed `R` blocks

This establishes the correct foundation for any future multisublattice
canonicalization work.
