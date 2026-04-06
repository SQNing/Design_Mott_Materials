# References for `translation-invariant-spin-model-simplifier`

This directory stores lightweight reference documents used by the skill layer of
`translation-invariant-spin-model-simplifier`.

These files are intended to clarify workflow expectations and input/fallback
contracts for the skill:

- `input-schema.md`
  Documents the expected normalized payload structure and the supported
  `local_term.representation.kind` variants.
- `fallback-rules.md`
  Documents how the skill should behave when user choices are missing, a model
  cannot be mapped cleanly to spin operators, or a requested solver/dependency
  is unavailable.

## Important scope note

These reference files are primarily skill-facing documentation. They are not
currently a hard runtime dependency of the Python or Julia scripts in this
directory.

In other words:

- the skill may instruct an agent to consult these files
- the scripts do not currently parse or load them automatically

If the implementation is later extended to enforce these contracts directly,
this directory should remain the canonical place for that human-readable
reference material.
