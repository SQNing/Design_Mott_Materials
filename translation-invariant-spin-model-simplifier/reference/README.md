# References for `translation-invariant-spin-model-simplifier`

This directory stores the small skill-facing reference documents that the skill
entrypoint explicitly asks an agent to read. Keep this directory narrow so the
skill's required supporting material is obvious at a glance.

The retained reference files are:

- `environment.md`
  Documents the baseline and optional environment dependencies for this skill,
  including Python, Sunny-backed Julia paths, plotting, PDF generation, and
  preflight checks the skill should ask the user about before execution.
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

Historical plans, status notes, and runtime entrypoint notes are outside the
tracked skill-facing reference set and should not be treated as required
reference material for this directory.
