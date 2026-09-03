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

## Hamiltonian Symmetry Gate

Runnable canonical Hamiltonians are checked against the structural space group
before a public solver starts. Strict validation is the default. If a complete
explicit Hamiltonian omits a symmetry partner or contains inconsistent
coefficients, the result stops with
`hamiltonian-symmetry-validation-failed` and `solver_execution.started=false`.
The diagnostic Hamiltonian subgroup is reported, but it is never substituted
for the structural target group automatically.

Use `symmetry_repair: true` in a structured request, or
`--symmetry-repair` in the solver/text CLIs, to request finite-group averaging.
Repair adds, averages, or removes canonical coefficients as required, then
revalidates the projected model. The input file and input payload are unchanged;
the report records separate input-model and solver-model hashes and emits
`hamiltonian-symmetry-repaired` when a material change was made.

Representative markers such as
`attach_to.orientation: representative` generate a complete symmetry orbit.
A plain term list is instead interpreted literally as the complete Hamiltonian.
Physical spin tensors use the axial-vector space-group action. Pseudospin and
orbital terms must provide their own symmetry representation; the code does not
guess one from matrix dimension. Solvers also inspect the complete term set, so
a bilinear backend rejects unsupported biquadratic, chirality, ring, or generic
higher-body terms with `solver-capability-mismatch` instead of dropping them.
