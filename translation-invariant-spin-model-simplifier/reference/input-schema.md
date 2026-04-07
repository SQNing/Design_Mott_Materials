# Input Schema

The normalized payload must contain:

- `system`
- `local_hilbert`
- `lattice`
- `local_term`
- `parameters`
- `symmetry_hints`
- `projection`
- `timeouts`
- `user_notes`
- `provenance`

`local_term.representation.kind` supports:

- `operator`
- `matrix`
- `natural_language`
- `many_body_hr`

Required content fields:

- `operator` -> `expression`
- `matrix` -> `matrix`
- `natural_language` -> `description`
- `many_body_hr` -> `structure_file` and `hamiltonian_file`

`support` must be provided for `operator` and `matrix` payloads and must be an iterable of integers, not a string-like value.

For `many_body_hr` payloads:

- `structure_file` must point to a crystal-structure file such as `POSCAR`
- `hamiltonian_file` must point to a Wannier-style `hr.dat` file
- the current semantics assume a local
  `pseudospin_orbital`
  space
- the basis order is fixed to
  `orbital_major_spin_minor`
  so the local basis is interpreted as
  `|up, orb1>, |down, orb1>, |up, orb2>, |down, orb2>, ...`

`natural_language` freeform input must be non-empty after trimming whitespace.

For `natural_language` payloads, `local_hilbert.dimension` is normalized from explicit spin notation when present, such as `spin-1/2` or `spin-1`.

Supported spin notation includes integer, half-integer, and `one-half` forms such as `spin-1`, `spin 2`, `spin-3/2`, `spin 3 / 2`, `spin 5/2`, `spin 5 / 2`, and `spin-one-half`.

Other explicit fractions such as `spin-2/3` or `spin-7/4` are rejected during normalization rather than coerced.
