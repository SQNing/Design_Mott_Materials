# LT/GLT Generalization Roadmap

Date: 2026-04-21

## Purpose

This memo freezes the theory contract for the next LT/GLT implementation stage in
`Design_Mott_Materials`. It has two jobs:

1. lock the mathematical object that the spin-only LT/GLT code is allowed to
   diagonalize once anisotropic exchange, Dzyaloshinskii-Moriya (DM), and full
   exchange tensors are admitted
2. lock the promotion criteria that decide when a relaxed `CP^(N-1)` GLT result
   is already a final classical state and when it must remain a diagnostic seed

This document is intentionally implementation-facing. It does not try to be a
full derivation. Instead, it records the solver obligations that downstream code
must satisfy so we do not have to revisit the literature while editing solver
semantics.

## Source Check

Primary inputs reviewed for this memo:

- local note:
  `/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/docs/notes/theory/GLT/2026-04-12-cpn-glt-derived-from-lyons-kaplan-1960.tex`
- Lyons-Kaplan lineage anchor:
  https://journals.aps.org/pr/abstract/10.1103/PhysRev.126.540
- modern overview mentioning generalized LT / Lyons-Kaplan style weighted weak
  constraints:
  https://arxiv.org/abs/2205.01542
- modern worked discussion of strong versus weak constraints and generalized
  LT usage:
  https://scipost.org/SciPostPhys.15.2.040

Validated points used below:

- The Lyons-Kaplan generalization keeps a single weighted weak quadratic
  constraint; it does not replace the strong constraints by a new family of
  sitewise constraints.
- Strong-constraint satisfaction remains a separate exactness question after the
  relaxed minimum is found.
- In the `CP^(N-1)` setting, the physically correct quadratic variable is the
  local projector `Q = |z><z|`, not the gauge-dependent amplitude `z` itself.
- For `CP^(N-1)`, the relaxed solution becomes a final state only when the
  reconstructed local objects satisfy the physical projector conditions, or when
  an explicit certification / constrained-completion stage closes the gap.

The repo-specific serialization and status labels below are implementation
choices inferred from those sources plus the current code structure. They are
not claims that the literature uses the exact same payload names.

## Spin-Only Relaxed Kernel

### Exact object

For a translation-invariant spin-only model with `m` magnetic sublattices and a
full `3 x 3` exchange tensor `J_{alpha beta}^{ab}(R)`, the relaxed LT kernel is
the block-Hermitian matrix

`J_{alpha a, beta b}(q)`,

where:

- `alpha, beta` are sublattice indices
- `a, b in {x, y, z}` are spin-component indices
- the total kernel dimension is `3m x 3m`

The implementation contract is:

`J(q) = sum_R J(R) exp(-i q . R_eff)`

with one `3 x 3` block for each directed bond contribution. The precise phase
convention may follow the repository's bond-vector convention, but the final
assembled matrix must satisfy Hermiticity:

`J(q) = J(q)^dagger`

and inversion symmetry at the level implied by real-space couplings:

`J(-q) = J(q)^*`.

### Symmetric anisotropy and DM terms

The decomposition

`J = J_iso I + J_sym + J_DM`

is useful for interpretation only. It must not become three separate solver
paths.

- isotropic Heisenberg exchange is the special case where every block is a
  scalar multiple of the identity
- symmetric anisotropy lives in the symmetric traceless part of each `3 x 3`
  bond block
- DM exchange lives in the antisymmetric part and therefore contributes
  off-diagonal component mixing

Implementation consequence:

- `lt_fourier_exchange.py` must canonicalize every bond matrix into the same
  tensor path
- the current scalar-only isotropic code path should survive only as the
  isotropic special case of the tensor assembly, not as a separate solver
  branch

### Relaxed eigenproblem

The spin-only LT stage still minimizes the weakest quadratic relaxation by
diagonalizing the Fourier kernel. What changes is the meaning of the
eigenvectors:

- the current code treats the eigenvector as one complex amplitude per
  sublattice
- after tensor generalization, the eigenvector represents a complex mode over
  sublattice-spin components

So `lt_solver.py` must interpret the minimizing eigenspace as a component-aware
mode basis, not as a scalar-on-sublattice basis with an implicit spin plane.

## Spin-Only Strong-Constraint Ladder

The literature check does not support treating the relaxed LT minimum as a final
state by default once anisotropy is present. The strong constraints remain the
exact sitewise unit-length conditions and must be checked constructively after
the relaxed minimum is found.

The required ladder is:

1. `exact_relaxed_hit`
   A minimizing mode or minimizing-mode combination already reconstructs a
   real-space texture with sitewise unit norms inside tolerance.
2. `completed_from_shell`
   The minimizing eigenspace or minimizing shell does not give an exact hit
   immediately, but a constrained completion inside that active shell restores
   the strong constraints inside tolerance.
3. `requires_variational_polish`
   The relaxed shell still fails the sitewise strong constraints after explicit
   completion, so the LT/GLT result is only a lower-bound-guided seed for the
   existing variational solver.

Implementation consequences:

- exactness must be tested on reconstructed real-space spins, not only on
  eigenvalue degeneracy or shell multiplicity
- shell mixing is an allowed constructive step, not a failure mode
- residual reporting must include a quantitative site-norm defect, not just a
  boolean flag
- variational polish should start from the best constrained-completion seed, not
  from a fresh random state

## Spin-Only Generalized LT

The Lyons-Kaplan generalization remains a weighted single-constraint relaxation.
For the spin-only tensor problem this means:

- the weighted relaxation acts on the same `3m x 3m` component-resolved kernel
- sublattice weights modify the weak-constraint metric, not the physical strong
  constraints
- the output must still expose the active minimizing `q`, eigenspace, and
  enough shell information to drive the strong-constraint ladder above

Implementation consequence:

- `generalized_lt_solver.py` must become tensor-kernel aware without collapsing
  back to scalar sublattice amplitudes

## `CP^(N-1)` Relaxation Object

The local note fixes the core promotion rule: the physically correct quadratic
object is the local projector

`Q_i = |z_i><z_i|`,

not the gauge-dependent spinor `z_i`.

The relaxed projector GLT problem may use projector components or an equivalent
adjoint basis, but final-state promotion is allowed only after reconstructing
candidate local projectors and checking the physical conditions:

- Hermiticity
- trace-one normalization
- positivity
- rank-one / idempotency exactness

The quadratic weak constraint in the projector language only preserves a global
weighted Frobenius-norm consequence of those local conditions. It therefore does
not by itself justify final classical-state output.

## `CP^(N-1)` Promotion Ladder

The required promotion ladder is:

1. `exact_projector_solution`
   The relaxed minimum reconstructs local projectors that already satisfy the
   physical projector conditions throughout the relevant real-space lift.
2. `certified_commensurate_lift`
   The relaxed minimum is not obviously exact from raw reconstruction alone, but
   the certification stage closes the gap strongly enough to prove a physical
   commensurate lift or projector exactness.
3. `completed_on_cpn_manifold`
   The relaxed solution provides a shell or seed that can be completed on the
   product `CP^(N-1)` manifold to an admissible classical state inside
   tolerance.
4. `diagnostic_seed_only`
   None of the three promotion paths succeeds, so the result remains a
   lower-bound diagnostic / seed and must not advertise downstream readiness as
   a final classical solver output.

Implementation consequences:

- `cpn_generalized_lt_solver.py` must expose promotion-relevant diagnostics
  rather than returning only a bound plus one diagnostic reconstruction
- `certify_cpn_glt.py` must feed exactness and gap information into the
  promotion decision instead of living as a detached afterthought
- a new finalization layer should own the final decision about whether the
  returned payload is a true `classical_state_result` or a diagnostic seed

## Solver-Semantics Freeze

The next implementation stage must preserve these semantics:

- spin-only LT/GLT becomes tensor-general, but never claims finality without the
  strong-constraint ladder
- `CP^(N-1)` GLT becomes conditionally final, but only through projector
  exactness, certification, or explicit constrained completion
- failure to promote is not an exception; it is a legitimate solver outcome that
  must still serialize useful lower-bound and seed information

The downstream solver-family routing should therefore distinguish:

- relaxed lower-bound solvers
- conditionally final solvers
- fully final solvers

without hiding which promotion stage actually succeeded.

## Implementation Obligations

The code tasks that follow from this memo are mandatory:

1. `lt_fourier_exchange.py` must assemble a Hermitian `3m x 3m` Fourier kernel
   from arbitrary real `3 x 3` bond tensors, including isotropic, symmetric
   anisotropic, and antisymmetric DM contributions.
2. `lt_solver.py` must serialize minimizing modes as component-resolved objects
   and expose enough data for exactness testing beyond a single scalar amplitude
   list.
3. `lt_tensor_constraint_completion.py` and
   `lt_constraint_recovery.py` must implement the three-stage spin-only
   strong-constraint ladder:
   `exact_relaxed_hit`, `completed_from_shell`, and
   `requires_variational_polish`.
4. `generalized_lt_solver.py` must operate on the tensor kernel with the same
   weighted weak-constraint semantics as Lyons-Kaplan, while exposing shell
   diagnostics needed for completion.
5. `cpn_generalized_lt_solver.py`, `cpn_glt_reconstruction.py`, and
   `certified_glt/certify_cpn_glt.py` must produce promotion inputs rich enough
   for exactness, certified lift, and constrained completion decisions.
6. `cpn_glt_finalization.py` must own the finalization contract for
   `CP^(N-1)` GLT and decide whether the output is a final classical result or a
   diagnostic seed.
7. `solve_pseudospin_orbital_pipeline.py` and
   `common/classical_solver_family_routing.py` must surface the difference
   between conditionally final and diagnostic-only LT/GLT outcomes instead of
   treating every `cpn-generalized-lt` result as automatically diagnostic or
   automatically final.

If a later implementation idea violates any item above, this memo takes
precedence unless the theory contract is revised explicitly.
