# Translation-Invariant Spin Model Simplifier

This directory is the stable expert-facing surface for the
`translation-invariant-spin-model-simplifier` skill.

## Stable Surface

- `SKILL.md`: top-level expert-facing skill contract
- `reference/`: skill-facing routing, protocol, fallback, and environment docs
- `scripts/`: runtime entrypoints and implementation helpers
- `tests/`: minimal stable-surface contract tests

## Contract Guardrails

These are the minimal contract guardrails for the stable surface on `main`.

- `tests/test_skill_surface_docs.py`
- `tests/test_skill_reference_docs.py`
