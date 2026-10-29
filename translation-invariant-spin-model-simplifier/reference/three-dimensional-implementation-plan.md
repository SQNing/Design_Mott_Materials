# Three-dimensional model workflow — implementation plan

Date: 2026-09-12. User approved continuing the 3D capability work to completion.

## Contract and scope

Input is a Hamiltonian and a calculation request, never a paper identifier or an
expected answer. Existing symmetry validation remains mandatory; unsupported
retained terms are not discarded. Classical minima, harmonic approximations,
finite-temperature sampling and finite-cluster quantum eigenstates are different
calculations and must be labelled accordingly. None constitutes a universal
exact solution of an arbitrary infinite three-dimensional quantum model.

Preserve all pre-existing files. Implement the additive entry point
`scripts/three_dimensional/workflow.py` and adjacent modules and physical tests.
Reuse the existing Fourier and local-ray quadratic-expansion kernels. Public
inputs use the canonical Hamiltonian produced by the normal model workflow.
Explicit geometry/moment input is also supported for the dipolar Ewald task.

## Milestones

- [x] 1. Validated canonical model -> 3N tensor Fourier spectrum, including DM;
  establish conventions with an independent finite real-space Hamiltonian.
- [x] 2. Fixed-length real-space classical optimization on a requested periodic
  supercell; report stationarity and finite-cell LT lower-bound gap separately.
- [x] 3. Connect the existing Python local-ray GSWT backend; return 3D spectra,
  stability and a Brillouin-zone quadrature zero-point energy correction.
- [x] 4. Periodic 3D dipolar Ewald energy and gradient with explicit surface
  convention, real/reciprocal cutoffs, self term and convergence comparison.
- [x] 5. Periodic classical Monte Carlo with correct extensive acceptance energy,
  autocorrelation-aware estimates, heat capacity, order parameter/Binder data
  and multi-size comparisons. No automatic claim of a critical temperature.
- [x] 6. Matrix-free finite-cluster quantum eigensolver using SciPy ARPACK;
  return low eigenvalues, residuals and explicit memory/size limitations.
- [x] 7. End-to-end runnable examples, physical regression checks, usage and
  capability/limitation documentation, and final verification.

## Verification

Tests live next to the new package to avoid modifying the repository's existing
test-directory ignore policy. Run with `python -B -m pytest -p no:cacheprovider
scripts/three_dimensional/tests`. Write and run each physical test before the
implementation it exercises. Relevant existing routing/symmetry tests must still
pass. Do not create a large defensive or adversarial testing project.

Physical checks: tensor Fourier versus independently assembled periodic Hessian;
cubic ferro/antiferromagnetic energies and spin lengths; cubic ferromagnetic
magnon spectrum and AF harmonic zero-point energy; Ewald splitting-parameter
invariance, surface term and numerical gradient; MC small-cell quadrature and
finite-size observables; matrix-free quantum spectrum versus independent dense
Kronecker construction, followed by a cluster beyond the former dense limit.

Implementation is not complete merely when tests pass: user-facing commands,
assumptions, limits and a reproducible computed-results record are required.

## Review notes

The existing Fourier, local-ray quadratic expansion, spin representation,
autocorrelation and local-field refinement kernels are reused. The new route
also accepts upstream `lattice-term-contract/v1` input directly. Review exposed
and resolved three physical/integration issues: missing degenerate Lanczos
states (projector deflation), local/global spin-frame mismatch (explicit rotation),
and energy-based optimizer stopping before tight stationarity (existing local
field polishing). Repair warnings and unsupported retained terms remain visible.

The Ewald milestone is an independent energy/gradient capability, not automatic
addition of a dipolar term to every other solver. No literature claim statuses
are promoted by this work. No pre-existing files, branch state or index entries
are changed.

Final verification: 131 tests passed (20 new 3D tests), 806 existing dependency
deprecation warnings, zero failures. See `three-dimensional-validation-record.md`
for the command, numeric results and explicit scope limits.
