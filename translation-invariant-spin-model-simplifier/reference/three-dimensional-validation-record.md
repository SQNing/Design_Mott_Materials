# 3D workflow: computed validation record

Date: 2026-09-12. Environment: Python 3.9.13, NumPy 1.23.5, SciPy 1.13.1;
`OPENBLAS_NUM_THREADS=1`, bytecode and pytest cache disabled.
Base commit: `98ff48c762600b3a6d5e1a075855aa5b74a9974d`.

This is a validation artifact, not an input to the solver. Production code never
reads this document. Models and parameters are independently supplied to the
calculation; expectations appear only in the test/validation layer.

## Numerical results

| Calculation | Actual computed result | Independent check / scope |
| --- | --- | --- |
| Cubic J=1 Fourier, q=Gamma and R | eigenvalues `[6,6,6]` and `[-6,-6,-6]` | Three positive nearest-neighbor directions plus their Fourier adjoints |
| Cubic FM and AF, S=1/2, 2x2x2 classical cell | E/cell = -0.75, finite-cell LT gap = 0 | Fixed-length real-space minimum, not just an LT eigenvector |
| Automatic AF classical reference in CLI example | stationarity max norm `9.02e-14` | Requested `1e-9`; energy -0.75 |
| Spin-1/2 cubic FM magnons at Gamma, X, R | energies 0, 2, 6 | Independent one-magnon dispersion; zero-point energy = 0 |
| Spin-1 cubic FM GSWT at Gamma, X, R | sorted bands `[0,12]`, `[4,12]`, `[12,12]` | Retains both excited local modes |
| Cubic AF, S=1/2 zero-point correction | `-0.1457028725858268` per primitive cell | 6x6x6 midpoint mesh in the 2x2x2 magnetic-cell BZ; NOT a mesh-limit claim |
| Cubic AF, 8-site quantum torus | lowest levels `-9.64017874875, -8, -8, -8` | Independently assembled 256x256 dense Pauli Hamiltonian; includes triplet multiplicity |
| Cubic FM, 16-site 2x2x4 quantum torus | two lowest levels `-12, -12` | Dimension 65,536; residuals `2.66e-11, 2.53e-10`; no dense many-body matrix |
| Cubic AF, 16-site 2x2x4 quantum torus | `-17.709059172688544, -16.62327136961885` | Dimension 65,536; residuals `1.06e-11, 4.15e-12`; finite-cluster calculation, not a literature thermodynamic value |
| One dipole in cubic cell of side 3 | tin-foil E=`-2*pi/81`; vacuum-sphere E=0 | Verifies surface convention and self term |
| Two-dipole Ewald CLI example | E=`0.10013344215430153` | Increasing both cutoffs by 1.25 changes E by `1.11e-16`; empirical convergence only |
| Periodic classical 2x1x1 torus, S=1, T=0.8 | E/site=`1.3981350 +/- 0.0049712`; C/site=`0.4326491 +/- 0.0082773` | Exact angular-integral comparison in test; 15000 measured sweeps, energy effective samples ~5603; statistical estimates, no equilibration certificate |

The tensor/DM test additionally compares a 9x9 Fourier matrix spectrum to an
independent Bloch projection of a 144x144 real-space Hessian on a triclinic,
three-sublattice lattice. A separate complex-DM quantum test compares to an
independent three-site dense Pauli construction. Ewald tests compare splitting
parameters and a finite-difference moment gradient in a triclinic cell.

The small MC finite-size test uses 2x2x2 and 3x3x3 cells, checks volume and
observable conventions and temperature trends, and explicitly does not certify
a critical temperature. The longer example uses 2x2x2 and 4x4x4 cells.

An additional AF zero-point mesh comparison with an explicit Neel reference
gave `-0.14555406208797614` (4^3), `-0.14570287258582693` (6^3), and
`-0.14573270334491115` (10^3) per primitive cell. These are magnetic-BZ midpoint
meshes, not an extrapolation; all three are labelled `converged_in_mesh: false`.

## Tests and review

Final combined regression: **131 passed, 0 failed, 806 warnings in 76.94 s**.
The new package alone passed **20 tests in 16.05 s**. The warnings originate in
the existing matplotlib/pyparsing and spglib dependency paths; they were not
suppressed or changed as part of this work.

Final regression command:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 python -B -m pytest -q -p no:cacheprovider \
  tests/test_canonical_hamiltonian.py \
  tests/test_hamiltonian_symmetry_action.py \
  tests/test_hamiltonian_symmetry_gate.py \
  tests/test_hamiltonian_symmetry_pipeline.py \
  tests/test_hamiltonian_symmetry_cli.py \
  tests/test_hamiltonian_solver_routing.py \
  tests/test_hamiltonian_symmetry_completion.py \
  tests/test_generic_model_analysis.py \
  tests/test_literature_generic_workflow.py \
  scripts/three_dimensional/tests
```

Review was performed locally because the available subagent interface cannot
explicitly enforce the user's non-Fast requirement. No subagents were started.
The review caught and repaired missing degenerate states, local/global reference
frame mismatch and premature energy-based optimizer stopping. No pre-existing
source, documentation, ignore rules, user data, git index or branch state changed.

## Not claimed

- No arbitrary-paper automated reproduction, and no new literature claim marked
  as reproduced. The existing literature backlog is separate.
- No exact thermodynamic-limit solution of arbitrary 3D quantum Hamiltonians.
- No supported-term truncation, QMC/tensor-network implementation, or treatment
  of every onsite/higher-body Hamiltonian in this new spin-bond route.
- No automatic coupling of Ewald dipoles into the exchange-only solvers.
- No certified critical temperature/exponents from the short MC checks.
- No merging, staging, committing, or replacement of the old public entry points.
