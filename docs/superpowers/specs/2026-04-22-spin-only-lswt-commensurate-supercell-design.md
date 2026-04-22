# Spin-Only LSWT Commensurate Supercell Design

## Context

The current spin-only Sunny LSWT path accepts a standardized classical state with
`site_frames`, but it still builds the Sunny system on a fixed `(1, 1, 1)`
supercell and applies dipoles only in the crystallographic cell. This is
correct for uniform `q = 0` order, but it is wrong for commensurate ordered
states whose classical contract carries a nonzero ordering wavevector.

The active FeI2 `V2b` rerun makes the mismatch explicit:

- the standardized classical state reports `ordering.q_vector = [0.0, 0.0, 0.5]`
- the LSWT payload still contains only one reference frame for one cell
- the Julia launcher still builds `Sunny.System(...; dims=(1, 1, 1))`
- Sunny therefore evaluates the wrong reference state and reports
  `Sunny.InstabilityError("Not an energy-minimum; wavevector q = [0, 0, 0] unstable.")`

The blocker is no longer environment setup or Julia launch. The blocker is that
the LSWT stage does not yet realize commensurate magnetic supercells from the
classical ordering contract.

## Goal

Add a minimal, explicit spin-only LSWT Phase 1 path that realizes commensurate
single-q order on a magnetic supercell before constructing Sunny
`SpinWaveTheory`, so that collinear states like FeI2 `q = (0, 0, 1/2)` are fed
to Sunny as the intended magnetic reference rather than as a forced uniform
single-cell state.

## Non-Goals

This phase does not attempt to solve every generalized ordered state:

- no incommensurate LSWT support
- no generic noncollinear spiral reconstruction from only `site_frames + q`
- no multi-q magnetic supercell support
- no redesign of the classical-state contract
- no document-reader orchestration changes beyond consuming the existing solver result

Those may become later phases if still needed.

## Phase 1 Scope

Phase 1 supports only the following LSWT input class:

- spin-only LSWT payloads built from `classical_state.site_frames`
- single crystallographic site per cell in the effective LSWT payload
- a commensurate single-q ordering vector
- a supercell phase pattern whose cell phases are all equivalent to either
  `0` or `π` modulo `2π`
- a reference state that is therefore representable by repeating the base
  frame direction with cell-dependent sign flips

This matches the active FeI2 failure mode.

## Design

### 1. Infer or read the magnetic supercell shape

The LSWT payload builder should resolve the magnetic supercell as follows:

1. Use `classical_state.supercell_shape` if present.
2. Else use `ordering.supercell_shape` if present.
3. Else, if `ordering.q_vector` is present and rationally commensurate, infer the
   minimal supercell from the rationalized wavevector denominators.
4. Else fall back to `[1, 1, 1]`.

This preserves existing contract precedence while allowing the FeI2 payload,
which currently carries only `q_vector`, to acquire the missing `[1, 1, 2]`
magnetic supercell.

### 2. Build explicit supercell reference frames

The payload builder should create a new explicit list of supercell-resolved
reference frames, one entry per `(cell, site)` in the magnetic supercell.

For Phase 1, the cell phase is

`phase(cell) = 2π q · cell`

and the allowed values are only:

- `0 mod 2π` -> keep the base frame direction
- `π mod 2π` -> flip the base frame direction

If any cell phase is neither `0` nor `π` within tolerance, payload
construction must fail with a clear LSWT payload error that explains the
current Phase 1 limit: the state requires a noncollinear spiral realization
rather than a collinear sign-flip supercell.

### 3. Preserve base-site metadata

The payload should still keep the crystallographic `positions`, `moments`, and
bond definitions in the existing format, but now add:

- `supercell_shape`
- `supercell_reference_frames`

This keeps the payload explicit and avoids overloading the old
`reference_frames` meaning.

### 4. Build Sunny on the magnetic supercell

The Julia LSWT launcher should:

- build `Sunny.System(...; dims=Tuple(payload.supercell_shape))`
- keep the existing bond loading logic
- set dipoles from `supercell_reference_frames` at the correct `(cell_x+1, cell_y+1, cell_z+1, site+1)` locations

This lets Sunny see the intended magnetic reference state instead of a single-cell
approximation.

## Error Handling

Phase 1 must fail early and clearly for unsupported states:

- incommensurate `q_vector`
- commensurate but non-collinear phase samples
- missing `site_frames`
- invalid supercell metadata

These should surface as Python payload-construction errors rather than opaque
Julia backend failures when possible.

## Testing Strategy

The work should be driven by tests in this order:

1. payload-builder test for FeI2-like `q = (0, 0, 1/2)` -> inferred
   `supercell_shape = [1, 1, 2]` and two supercell reference frames with
   opposite directions
2. payload-builder test that explicit standardized `supercell_shape` wins over
   inference
3. payload-builder test that a non-`0/π` commensurate phase pattern is rejected
4. Julia-driver-facing test that `run_linear_spin_wave` passes the new payload
   fields through to the launcher
5. real FeI2 rerun from saved `solver_result.json`

## Expected Outcome

After Phase 1, the FeI2 rerun should no longer fail because the LSWT code fed
Sunny a uniform one-cell state for a `q = (0, 0, 1/2)` order. The rerun may
still expose a later physics or model issue, but it should be a new blocker,
not the current reference-state mismatch.
