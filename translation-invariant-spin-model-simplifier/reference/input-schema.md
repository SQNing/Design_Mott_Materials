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

Required content fields:

- `operator` -> `expression`
- `matrix` -> `matrix`
- `natural_language` -> `description`

`support` must be provided for `operator` and `matrix` payloads and must be an iterable of integers, not a string-like value.

`natural_language` freeform input must be non-empty after trimming whitespace.

For `natural_language` payloads, `local_hilbert.dimension` is normalized from explicit spin notation when present, such as `spin-1/2` or `spin-1`.

Supported spin notation includes integer, half-integer, and `one-half` forms such as `spin-1`, `spin 2`, `spin-3/2`, `spin 3 / 2`, `spin 5/2`, `spin 5 / 2`, and `spin-one-half`.

Other explicit fractions such as `spin-2/3` or `spin-7/4` are rejected during normalization rather than coerced.
