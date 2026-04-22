# Spin-Only LSWT Single-Q Rotating-Frame Phase 2 Design

## Context

Phase 1 for spin-only Sunny LSWT is now complete: the LSWT path can infer a
commensurate magnetic supercell and expand explicit `supercell_reference_frames`
for collinear `0/π` single-q order. This was enough to unblock the active FeI2
`q = (0, 0, 1/2)` case and produce a real LSWT dispersion.

However, the current implementation is intentionally narrow. It only accepts
cell phases that are equivalent to either `0` or `π`, and it rejects
commensurate single-q states that require a genuine phase rotation between
magnetic cells.

The important observation is that the codebase already carries the right
metadata for the broader case:

- `rotating_frame_transform`
- `rotating_frame_realization.supercell_site_phases`
- `quadratic_phase_dressing`

Those are already preserved in spin-only LSWT payloads, but the current LSWT
builder uses them only as diagnostics/metadata and not as the source of the
actual reference-frame texture.

## Goal

Extend the spin-only Sunny LSWT path so that commensurate single-q rotating-frame
metadata can be converted into explicit `supercell_reference_frames` with
arbitrary phase angles, not just `0/π` sign flips.

This phase should let the LSWT path support general commensurate single-q
spiral/noncollinear order whenever the classical contract provides enough
rotating-frame information to reconstruct the real-space spin texture.

## Non-Goals

This phase does not attempt to solve:

- incommensurate LSWT
- multi-q LSWT
- arbitrary user-defined local coordinate frames unrelated to single-q rotation
- Sunny-side gauge transformations for quadratic bosonic Hamiltonians

Those remain separate follow-on problems.

## Design

### 1. Prefer explicit rotating-frame realization over the Phase 1 sign-flip shortcut

When the LSWT payload builder sees:

- `rotating_frame_realization.supercell_site_phases`
- a resolvable rotation axis
- a commensurate `supercell_shape`

it should build `supercell_reference_frames` from those explicit phase samples,
rather than from the Phase 1 `0/π` phase classifier.

Phase 1 sign-flip expansion stays as a fallback for the simple collinear case.

### 2. Reconstruct per-cell spin directions by axis-angle rotation

For each base site frame:

- take the base direction from `classical_state.site_frames[*].direction`
- read the phase for `(cell, site)` from `supercell_site_phases`
- rotate the base direction by that phase around the declared rotation axis

The result becomes the explicit `direction` stored in
`supercell_reference_frames`.

This means the LSWT runner still consumes only explicit real-space directions;
the extra complexity remains in Python payload construction.

### 3. Resolve rotation axes explicitly

Phase 2 must support at least:

- `"x"`, `"y"`, `"z"`
- crystallographic aliases such as `"a"`, `"b"`, `"c"`

For the immediate first pass, these aliases can map onto the Cartesian lattice
basis used by the current effective-model conventions. If the model later
requires arbitrary rotated axes, that should become a separate phase.

### 4. Preserve payload transparency

The LSWT payload should continue to include:

- `rotating_frame_transform`
- `rotating_frame_realization`
- `quadratic_phase_dressing`
- `supercell_reference_frames`

The runner should not need to infer phases from metadata. It should still
consume already-expanded explicit spin directions.

## Error Handling

Phase 2 should fail early when:

- the rotating-frame realization exists but lacks usable `supercell_site_phases`
- the rotation axis cannot be resolved
- phase entries do not cover every `(cell, site)` required by the supercell
- the realization is inconsistent with the requested supercell

These should surface as LSWT payload-construction errors, not opaque Julia
exceptions.

## Testing Strategy

1. payload-builder test for a commensurate `q = 1/4` single-q rotating-frame
   case whose supercell directions rotate continuously rather than just flip sign
2. payload-builder test that Phase 1 sign-flip fallback still works when no
   rotating-frame realization is available
3. payload-builder test that missing/partial phase samples are rejected
4. real or synthetic LSWT driver test that the explicit rotated
   `supercell_reference_frames` are written to the launcher payload

## Expected Outcome

After Phase 2, the spin-only LSWT path will support both:

- collinear commensurate single-q order via Phase 1 sign-flip expansion
- noncollinear commensurate single-q order via rotating-frame phase realization

without changing the existing classical contract surface.
