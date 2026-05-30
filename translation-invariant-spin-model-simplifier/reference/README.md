# References for `translation-invariant-spin-model-simplifier`

This directory stores the small skill-facing reference documents that the skill
entrypoint explicitly asks an agent to read. Keep this directory narrow so the
skill's required supporting material is obvious at a glance.

The retained reference files are:

- `agent-routing.md`
  Documents the current repository-specific routing decisions for input
  classes, agent-assisted landing, classical-bond_label resolution, backend
  selection, semantic conventions, and recommended entrypoints.
- `environment.md`
  Documents the baseline and optional environment dependencies for this skill,
  including Python, Sunny-backed Julia paths, plotting, PDF generation, and
  preflight checks the skill should ask the user about before execution.
- `input-schema.md`
  Documents the expected normalized payload structure, with
  `lattice_structure` as the primary conceptual object and legacy compatibility
  notes for older bond_label-oriented payloads.
- `lattice-structure-and-term-attachment.md`
  Documents how Hamiltonian content attaches to `lattice_structure` as site
  terms, bond terms, and higher-body terms.
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

## Scope

These files are skill-facing documentation, not a direct runtime dependency.

Historical plans and runtime entrypoint notes outside the files listed above
should not be treated as required reference material for this directory.
