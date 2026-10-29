# Three-dimensional spin-model calculations

This is an **additive, model-driven entry point**. It accepts a Hamiltonian and a
calculation request, computes the requested quantities, and reports the numerical
scope and limitations. There are no paper IDs, literature answers, adapter
registries keyed by publications, or expected-result tables in this calculation
path. The existing document/agent normalization and readable-model workflow is
still upstream; this entry point is not an arbitrary-paper reproduction agent.

## What is supported

The finite-range Hamiltonian is

`H = sum_R sum_b S_(R,s_b)^T J_b S_(R+delta_b,t_b)`.

Each listed bond is counted once per primitive cell. Do not list a bond and its
reverse unless you intend two contributions. The periodic finite-cell realization
retains distinct image bonds even when a small supercell gives them the same
endpoints. A length-two cubic direction therefore has two bonds between its two
sites; it is not the open-boundary cube graph.

`J_b` may be any real 3 by 3 exchange tensor, including symmetric anisotropy and
antisymmetric DM exchange. Multiple magnetic sublattices and arbitrary integer
cell translations are supported. The lattice can be nonorthogonal. Neither the
Fourier kernel nor the finite-cell kernels assume one or two spatial dimensions.

| Request task | Actual calculation | Meaning and main limit |
| --- | --- | --- |
| `fourier_exchange_spectrum` | Shared 3N by 3N exchange Fourier matrix at supplied q points | Eigenvalues, eigenvectors and projectors; a sampled spectrum, not a ground-state proof |
| `classical_ground_state` | Fixed-length, multistart real-space L-BFGS-B on a periodic supercell | Energy, spins, stationarity, finite-cell LT bound and gap; not an infinite-system certificate |
| `spin_wave_spectrum` | Existing Python local-ray quadratic/GSWT kernel | Harmonic bands and stability about a supplied or optimized reference; optional zero-point BZ quadrature |
| `classical_monte_carlo` | Classical sphere Metropolis sampling using **total** energy differences | Energy, specific heat, susceptibility, order parameter, Binder data and statistical-error estimates |
| `classical_finite_size` | The same MC calculation on multiple requested supercells | Comparable size-resolved observables and descriptive Binder-crossing candidates; no automatic Tc/exponent claim |
| `quantum_low_energy` | Matrix-free finite-cluster quantum eigenproblem | Low eigenvalues and residuals; no dense many-body Hamiltonian, but vectors still scale exponentially |
| `dipolar_ewald` | Periodic 3D point-dipole energy and moment gradient | Separate geometry/moment calculation with explicit boundary and cutoff comparison; see below |

The new spin-bond route currently accepts retained terms of family
`bilinear_exchange_tensor` or `bilinear_exchange_matrix`. It does **not** silently
drop onsite fields/anisotropy, biquadratic, ring, chirality, generic retained-local
pair operators, or other higher-body terms to fit this capability. Such inputs
stop with an unsupported/capability error; other existing repository backends may
support some of them. This is not a claim of solving arbitrary 3D quantum models.

## Input and symmetry

Run from the `translation-invariant-spin-model-simplifier` directory:

```bash
python -B scripts/three_dimensional/workflow.py input.json
```

Alternatively supply JSON on stdin. The process prints JSON on stdout and does
not write or replace input/result files. A non-ok result has a nonzero exit code.

```json
{
  "model": {
    "schema_version": "lattice-term-contract/v1",
    "lattice_structure": {},
    "local_hilbert": {},
    "symmetry": {},
    "term_attachments": {}
  },
  "request": {
    "task": "classical_ground_state",
    "supercell_shape": [2, 2, 2],
    "spin_length": 0.5,
    "starts": 8,
    "seed": 42
  }
}
```

The empty objects above indicate where the normal upstream lattice-term contract
goes; they are not a runnable model. Use the example generator below for complete
inputs. `canonical-hamiltonian/v1` input is also accepted. Lattice-term input is
compiled with the existing canonical compiler before symmetry validation.

The full supplied structural space group is checked before any spin solver runs.
The caller/upstream normalization must supply the actual structural group; this
entry point does not discover a space group or replace a failing group with a
smaller Hamiltonian subgroup. `request.symmetry_repair: true` explicitly enables
the existing group-average repair. Repair warnings, original/solver hashes and
the change report are returned. The default is strict validation without repair.

For the spin-bond bridge, declare the `unit_vector_sphere` classical space and
physical `spin_vector` operator basis. These distinguish spin-only semantics from
a general CP(N-1) retained-local problem. Classical `spin_length` and quantum
`spin` are explicit separate inputs; the latter is an integer or half-integer.

For real-space/quantum/GSWT calculations, coefficients in `local_frames` are
converted as `J_global = R_source J_local R_target^T`. Local frame matrices must
be proper orthogonal rotations. Supplied and returned real spin directions are
in global Cartesian axes. Fourier eigenvectors remain in the input site's spin
component basis, which is explicitly labelled in the result.
The Fourier kernel uses `exp(-2 pi i q.delta_cell)` without basis-position phases;
its eigenvectors are in this unit-cell Bloch gauge. Eigenvalues are independent
of an equivalent basis-phase gauge change.

## Runnable examples

These generators contain **only model inputs and numerical settings**, not
expected answers. All pipelines below calculate their output afresh.

```bash
# Fixed-length classical antiferromagnet.
python -B scripts/three_dimensional/examples.py cubic-af \
  | python -B scripts/three_dimensional/workflow.py

# Classical optimization -> reference rays -> 3D GSWT and zero-point energy.
python -B scripts/three_dimensional/examples.py cubic-af --task spin_wave_spectrum \
  | python -B scripts/three_dimensional/workflow.py

# 16 spin-1/2 sites, Hilbert-space dimension 65,536.
python -B scripts/three_dimensional/examples.py cubic-af --task quantum_low_energy \
  | python -B scripts/three_dimensional/workflow.py

# Independent periodic Ewald energy/gradient task.
python -B scripts/three_dimensional/examples.py dipoles \
  | python -B scripts/three_dimensional/workflow.py

# Longer sampling run: L=2 and L=4 cubic supercells.
python -B scripts/three_dimensional/examples.py cubic-fm --task classical_finite_size \
  | python -B scripts/three_dimensional/workflow.py
```

For reproducible small-matrix timing, setting `OPENBLAS_NUM_THREADS=1` for these
Python commands can help. This is a numerical-library setting, unrelated to
agent/subagent model speed.

## Interpreting results

### Classical minimization and Fourier

`supercell_shape` contains three positive integers. Spins are serialized in
lexicographic cell order (last cell coordinate varies fastest), then basis-site
order. `initial_spins` is optional; otherwise starts are random. `maxiter`,
`stationarity_tolerance`, `starts` and `seed` control the search. For bonds with
distinct finite-cell endpoints, the existing exact local-field sweep polishes
the L-BFGS result so roundoff in total energy does not prematurely stop a tight
stationarity request. Self-image quadratic terms are not polished this way.

The reported LT bound uses **all commensurate q values of that finite supercell**:
`E_bound/cell = N_basis * spin_length^2 * min_q lambda_min[J(q)] / 2`.
A gap near zero checks the optimized state against this finite-cell bound.
A converged stationary point with a positive gap is still only a candidate
minimum. Neither result establishes the infinite-lattice phase diagram.

### GSWT

Supply `spin`, `supercell_shape`, `reduced_momenta`, and optionally
`reference_spins`. Reference magnitudes specify directions only; the quantum spin
representation sets their physical length. If no reference is supplied, the
fixed-length optimizer runs first. `zero_point_mesh: [nx, ny, nz]` requests a
midpoint quadrature of the **magnetic** Brillouin zone. Input/output path momenta
are in primitive reciprocal-lattice units, with the `2 pi` convention.

For S=1/2, this spin-only local-ray expansion agrees with LSWT. For S>1/2 it retains
all 2S excited local states: it is GSWT, not a one-magnon truncation. The zero-point
correction is `mean_q[(sum_n omega_n - Tr A)/2] / N_primitive_cells_in_magnetic_cell`.
It is not the complete quantum ground-state energy. Nonstationary references,
negative quadratic Hessians or complex frequencies yield an inconclusive result.
Stability is checked only at requested path and quadrature points. Repeat with
larger meshes and magnetic cells before a thermodynamic conclusion. The use of a
bosonic quadratic/Bogoliubov problem follows the standard spin-wave treatment;
see the [SpinW methodological lecture](https://spinw.org/Ispra2019/Ispra2019.pdf).

### Monte Carlo and finite-size data

Required fields: `spin_length`, `temperatures`, and either `supercell_shape` or
`supercell_shapes`. Temperatures are in model energy units with k_B=1.
`burn_in`, `sweeps`, `measurement_interval` and `seed` are configurable.
Each temperature starts from a new random configuration. `order_momentum`
selects the measured Fourier order parameter (default q=0); choose a commensurate
q and compatible supercells for finite-size comparisons.

The output defines its conventions: `M(q)=sum_i exp(2pi i q.r_i) S_i / N`,
`binder_ratio=<|M|^4>/<|M|^2>^2`, `binder_cumulant=1-binder_ratio/3`.
This is an explicitly stated radial convention, not the normalized O(3) Binder
parameter. Susceptibility is the Cartesian-component average of uniform
magnetization fluctuations. Energy/order means use autocorrelation-aware errors;
heat capacity and Binder errors use block jackknife. These are estimates, not
proof of equilibration. Local updates may mix poorly in frustrated/critical
systems. Longer independent runs and a genuine scaling fit are still needed to
claim a transition; compare [ALPS autocorrelation guidance](https://alps.comp-phys.org/tutorials/mcs/mc01a/)
and [finite-size tutorials](https://alps.comp-phys.org/zh-cn/tutorials/mcs/mc07/).

### Quantum finite clusters

Required: `spin` and `supercell_shape`; optional `eigenvalues` (default 2),
`tolerance`, `maxiter`, `seed`, `max_dimension` (default 262144) and
`max_memory_mb` (Krylov workspace budget, default 512). The estimate is not a hard
process-RSS limit; local pair operators and Python/BLAS overhead also consume
memory. The local pair operators are dense even though the many-body Hamiltonian
is matrix-free. Large-S calculations can therefore be expensive too.

ARPACK is used through SciPy's [matrix-free eigenproblem interface](https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.linalg.eigsh.html).
Independent starts with positive-projector deflation recover successive states,
including members of degenerate multiplets that one Krylov start can miss.
Original-Hamiltonian residuals and eigenvector orthogonality are returned. Real
Hamiltonians use Lanczos; complex DM Hamiltonians use SciPy's complex Arnoldi
path. There is no assumed Sz conservation or symmetry-sector compression. A
supercell that identifies both ends of a quantum bond with one site is rejected;
enlarge it. This is neither QMC nor a thermodynamic-limit quantum solver.

### Ewald is a separate, explicit dipolar task

For `dipolar_ewald`, `model` contains `lattice_vectors` (rows),
`fractional_positions` and `moments`, not a canonical exchange Hamiltonian.
Required request fields are `alpha`, `real_cutoff`, `reciprocal_cutoff` and
`boundary`. `prefactor` defaults to 1; the caller supplies physical units such as
mu_0/(4pi). Reciprocal cutoffs use actual inverse-length wavevectors including
2 pi. Boundaries are `tin_foil` (zero surface term) or `vacuum_sphere` (spherical
vacuum surface term). Real, reciprocal, self and surface contributions are
reported separately, with `moment_gradient=dE/d(moment)`, not positional forces.
The energy formula follows [Wang and Holm, Eqs. (2)-(8)](https://arxiv.org/pdf/cond-mat/0107064).

Both cutoffs are increased by `cutoff_comparison_factor` (default 1.25) for an
empirical energy/gradient comparison. It is not a rigorous error bound. No slab
or wire boundary is implemented. **This Ewald term is not automatically added to
the exchange-only minimizer, GSWT, MC or quantum Hamiltonian.** Coupled exchange
plus long-range-dipolar solving remains a separate integration task.

## Verification and change scope

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  python -B -m pytest -q -p no:cacheprovider scripts/three_dimensional/tests
```

These are physical tests, including an independent real-space Fourier Hessian,
dense quantum tensor products, classical angular integration, 3D magnon and
zero-point formulas, and Ewald surface/splitting/gradient checks. They are not
stored production answers. See `three-dimensional-validation-record.md` for the
verified numerical record and full regression command.

All implementation, examples, tests and documentation are new files. Existing
solver files, AGENTS.md, ignore rules and legacy workflows were not overwritten.
The new entry point must currently be invoked explicitly; it has not replaced
every older public solver route or completed the literature-validation backlog.
