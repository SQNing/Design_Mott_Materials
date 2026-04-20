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
- the default retained-local-space mode is the legacy
  `orbital-times-spin`
  interpretation with basis order
  `orbital_major_spin_minor`
  so the local basis is interpreted as
  `|up, orb1>, |down, orb1>, |up, orb2>, |down, orb2>, ...`
- an explicit
  `generic-multiplet`
  retained-local-space mode is also supported; in that branch the local basis order is
  `retained_state_index`
  and the basis labels are generic retained-state labels such as
  `state_1`, `state_2`, ...
- when the retained local space is even-dimensional but does not physically factorize into
  `orbital x spin(2)`, callers should use the explicit
  `generic-multiplet`
  mode instead of relying on dimension-based inference

`natural_language` freeform input must be non-empty after trimming whitespace.

For `natural_language` payloads, `local_hilbert.dimension` is normalized from explicit spin notation when present, such as `spin-1/2` or `spin-1`.

Document-style text inputs such as LaTeX notes and `.tex` sources still enter through the
`natural_language` representation rather than a separate top-level representation kind.

`natural_language` payloads may also carry an optional
`agent_normalized_document`
object when an upstream agent has already converted a paper-style Hamiltonian into a structured
intermediate form.

This object is not a separate public representation kind; it is a constrained helper input that is
translated into the same
`document_intermediate`
landing path used by deterministic document extraction.

For document-style `natural_language` inputs that are detected as paper/LaTeX sources but do not
yet produce a trustworthy runnable operator payload, normalization may return an optional
`agent_normalization_request`
object together with
`interaction.status = needs_input`.
This signals that the next recommended step is to call an upstream agent to convert the document
into the constrained
`agent_normalized_document`
schema rather than continuing with raw document parsing.

That request may include:

- `template_version`
- `template`
- `example_payload`
- `prompt_notes`

so that the upstream agent can return a fixed JSON contract rather than inventing a new shape.

The formal end-to-end document reader entrypoint is
`scripts/cli/run_document_reader_pipeline.py`.
That driver runs document orchestration first and, once a trustworthy
`normalized_model`
has landed, continues directly from that landed payload into the shared simplification/report
pipeline rather than re-running freeform normalization on the raw source text.

For these document-style `natural_language` inputs:

- callers may provide `source_path` to improve source-kind detection
- normalization may return `interaction.status = needs_input` when multiple Hamiltonian candidates
  are present
- callers may then resubmit the same text with `selected_model_candidate`
- after that selection, normalization may land the text into an `operator` payload if the selected
  document candidate can be represented faithfully

For these optional
`agent_normalized_document`
objects, the most useful fields are:

- `source_document`
- `model_candidates`
- `candidate_models`
- `hamiltonian_model`
- `parameter_registry`
- `system_context`
- `lattice_model`
- `unresolved_items`
- `unsupported_features`

Within
`hamiltonian_model`,
callers may provide:

- `operator_expression`
- `local_bond_candidates`
- `matrix_form`
- `matrix_form_candidates`

Within
`candidate_models`,
callers may provide candidate-scoped model payloads keyed by names such as
`effective`
or
`matrix_form`.
This is the preferred shape when the source paper presents multiple named Hamiltonian candidates
that should remain distinct until
`selected_model_candidate`
is chosen.

For evidence-backed
`parameter_registry`
entries, callers may use rich parameter objects rather than bare scalar values.
The current verifier understands at least:

- `value`
- `units`
- `evidence_refs`
- `confidence`
- `extraction_method`
- `evidence_values`

where
`evidence_values`
is a list of per-evidence observations such as `{evidence_ref, value, units}`.
This is the preferred shape when the same parameter is extracted from multiple equations, tables, or
supplementary sources and the system should detect conflicts instead of silently overwriting them.

If the agent-normalized object is still incomplete, keep the missing or hard-gated choices in
`unresolved_items`
instead of fabricating a final landing. Normalization will preserve that state as
`interaction.status = needs_input`.

If the landed document metadata carries a verifier result such as
`verification_report.status = needs_review`,
that review state should remain visible in downstream pipeline outputs but does not by itself turn
the document-reader path into a hard failure.

Supported spin notation includes integer, half-integer, and `one-half` forms such as `spin-1`, `spin 2`, `spin-3/2`, `spin 3 / 2`, `spin 5/2`, `spin 5 / 2`, and `spin-one-half`.

Other explicit fractions such as `spin-2/3` or `spin-7/4` are rejected during normalization rather than coerced.
