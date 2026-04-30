# Translation-Invariant Spin Model Simplifier

This directory is the stable expert-facing surface for the
`translation-invariant-spin-model-simplifier` skill.

## Stable Surface

- `SKILL.md`
  The top-level expert-facing contract for how the skill should behave.
- `reference/`
  Skill-facing routing, protocol, fallback, and environment documentation.
- `scripts/`
  Repository runtime entrypoints and implementation helpers used by the skill.
- `tests/`
  Minimal contract guardrails that keep the stable surface from drifting.

## Contract Guardrails

The stable surface is protected by lightweight documentation tests:

- `tests/test_skill_surface_docs.py`
- `tests/test_skill_reference_docs.py`

Those tests are intentionally small. They are here to guard the top-level
contract, reference layout, and stable expert-facing routing surface on `main`.
