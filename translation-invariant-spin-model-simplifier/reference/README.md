# References for `translation-invariant-spin-model-simplifier`

This directory stores the small skill-facing reference documents that the skill
entrypoint explicitly asks an agent to read. Keep this directory narrow so the
skill's required supporting material is obvious at a glance.

The retained reference files are:

- `agent-routing.md`
  Documents the current repository-specific routing decisions for input
  classes, agent-assisted landing, classical-family resolution, backend
  selection, semantic conventions, and recommended entrypoints.
- `environment.md`
  Documents the baseline and optional environment dependencies for this skill,
  including Python, Sunny-backed Julia paths, plotting, PDF generation, and
  preflight checks the skill should ask the user about before execution.
- `input-schema.md`
  Documents the expected normalized payload structure and the supported
  `local_term.representation.kind` variants.
- `natural-language-input-protocol.md`
  Defines the upstream extraction protocol for natural-language, LaTeX, and
  document-style inputs before they are normalized into runnable payloads.
- `fallback-rules.md`
  Documents how the skill should behave when user choices are missing, a model
  cannot be mapped cleanly to spin operators, or a requested solver/dependency
  is unavailable.
- `cpn-refinement-and-promotion-controls.md`
  User-facing workflow note for the shared magnetic-supercell refinement knobs,
  `sun-gswt-cpn` promotion scope, and GLT result interpretation.
- `cpn-pair-model-schema.md`
  User-facing schema note for the canonical `cpn_pair_model` payload contract.
- `cpn-workflow-readiness-checklist.md`
  User-facing smoke checklist for deciding whether a `CP^(N-1)` workflow result
  is ready to trust or needs further validation.

## Important scope note

These reference files are primarily skill-facing documentation. They are not
currently a hard runtime dependency of the Python or Julia scripts in this
directory.

In other words:

- the skill may instruct an agent to consult these files
- the scripts do not currently parse or load them automatically

Historical plans and runtime entrypoint notes outside the files listed above
should not be treated as required reference material for this directory.
