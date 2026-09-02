# Repository Workflow Boundary

## Product workflow

The product accepts a translation-invariant spin or pseudospin model. The
model may arrive as natural language, LaTeX, an operator expression, a local
matrix or tensor, a structured payload, a document-derived model, or a
structure-plus-Hamiltonian file pair.

Route product work through the generic model pipeline:

```text
model input
  -> normalize into the lattice_structure-centered model contract
  -> resolve or surface material physical ambiguities
  -> decompose local terms
  -> canonicalize the Hamiltonian
  -> identify readable blocks
  -> assemble H_main + H_low_weight + H_residual
  -> optionally route to a compatible classical, LSWT/GSWT, thermodynamic,
     or other solver backend
  -> report results, assumptions, fidelity, residuals, unsupported features,
     and blockers
```

This pipeline must operate from the supplied model and its physical
parameters. A model does not need to match a known paper, benchmark name, or
registered literature identifier. If the model is materially ambiguous, stop
with `interaction.status = needs_input`. If its representation or requested
analysis is unsupported, report that limitation explicitly instead of
substituting a literature result or a different physical model.

## Literature reproduction is a test workflow

Literature reproduction exists to test and audit the generic product workflow.
Its intended flow is:

```text
paper or literature claim
  -> agent extracts the model, conventions, parameters, observable, and claim
  -> extraction lands in the same generic model input contract
  -> the generic product workflow performs simplification and/or computation
  -> the test layer compares the independently produced result with the paper
     and, where appropriate, an independent oracle
  -> the audit reports matched, mismatched, inconclusive, or unsupported
```

Literature adapters and oracles belong to tests, validation, and audit
infrastructure:

- An adapter may translate a literature benchmark into the generic model or
  test-request schema and expose the computation under test.
- An oracle may independently verify a result by a scientifically distinct
  method.
- Neither is a required stage of the product workflow.

## Architectural prohibitions

- Do not route a product request by matching a literature model ID or paper ID.
- Do not make the product entrypoint depend on a literature adapter catalog or
  oracle catalog.
- Do not return a registered or hard-coded literature value as the computed
  result of a user-supplied model.
- Do not feed an expected literature answer into the model computation,
  simplification, solver selection, convergence decision, or uncertainty
  estimate.
- Do not implement one product solver per paper when the capability belongs in
  a reusable model representation or generic solver backend.
- Do not describe validation, isolation, counterfactual, adversarial, or
  literature-audit machinery as the user-facing scientific workflow.
- Do not let document or paper ingestion bypass the same ambiguity gates,
  canonical model contract, and unsupported-feature reporting used for other
  model inputs.

When changing literature-evidence code, state explicitly whether the change is
test/audit infrastructure or a reusable generic product capability. A reusable
capability must be connected through the generic model pipeline and must remain
usable for a model that has no literature registry entry.

## Source of truth

Use `SKILL.md` as the top-level product contract and the files under
`reference/` for input routing, normalization, ambiguity handling, backend
selection, fallback behavior, and environment requirements. Literature audit
reports and literature adapter/oracle registries are not the source of truth
for product workflow semantics.
