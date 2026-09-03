# Canonical Hamiltonian Symmetry Gate Design

## 1. Purpose

This design introduces one canonical, solver-independent space-group gate for Hamiltonians. It consolidates existing repository capabilities instead of creating parallel bond-orbit, Fourier, LT, LSWT, or GSWT implementations.

The gate has two public modes:

- strict validation, the default: reject a Hamiltonian that does not satisfy the structural space group;
- opt-in repair: project the Hamiltonian onto the structural space group by finite-group averaging, revalidate it, and continue only if the repaired model passes.

The canonical representation supports arbitrary interaction arity from the start. Individual solvers may support only a subset of term families, but no solver may silently omit an unsupported term.

## 2. Existing Capabilities to Reuse

The implementation must reuse these existing components:

- `scripts/common/bond_orbits.py`: space-group generation of directed bond orbits;
- `scripts/common/lattice_structure_builder.py`: lattice structure, site/bond orbits, and structural symmetry records;
- `scripts/classical/build_spin_only_solver_payload.py`: the existing Cartesian axial-vector transformation, symmetry rotation of anisotropic 3-by-3 exchange matrices, and reverse-bond transpose behavior;
- `scripts/classical/lt_fourier_exchange.py`: the existing complex 3N-sub by 3N-sub Fourier exchange matrix;
- `scripts/classical/generalized_lt_solver.py`, `scripts/classical/cpn_generalized_lt_solver.py`, and `scripts/classical/certified_glt/`: existing generalized and certified GLT machinery;
- existing LSWT and SU(N) GSWT Python/Julia/Sunny adapters under `scripts/lswt/`.

The current canonical lattice-term and pseudospin realization paths copy a representative matrix to orbit members in cases where the legacy spin-only path rotates an anisotropic matrix. The new shared symmetry action removes that inconsistency. The simplified Fourier implementation in `scripts/common/model_analysis.py` must become an adapter to the existing LT Fourier kernel rather than grow into another physical backend.

## 3. Architecture

The user-facing data flow is:

```text
parsed model
    -> canonical input Hamiltonian
    -> canonical symmetry gate
       -> validate-only, or
       -> project and revalidate
    -> validated canonical Hamiltonian
    -> capability-checked solver adapters
       -> LT/classical
       -> LSWT
       -> GSWT
       -> later backends
```

### 3.1 Canonical Hamiltonian compiler

The compiler accepts legacy spin-only payloads, `lattice-term-contract/v1`, pseudospin/orbital blocks, and higher-body terms. It normalizes them without performing symmetry repair.

The output contains:

```yaml
canonical_hamiltonian:
  lattice: {}
  local_spaces: []
  terms: []
  coordinate_conventions: {}
  structural_symmetry: {}
symmetry_request:
  repair: false
  target:
    kind: structural_space_group
  absolute_tolerance: 1.0e-10
  relative_tolerance: 1.0e-8
```

Each canonical term records:

- a unique `term_ref`;
- its arity;
- an ordered site/translation cluster;
- its operator family and coefficient tensor;
- coordinate conventions and local frames;
- permutation, orientation, and adjoint rules;
- source provenance.

### 3.2 Shared symmetry action

One common module implements the action `g * term`. It owns no policy: it neither decides whether a model is symmetric nor whether repair is allowed.

It reuses the current geometric mapping and extracts the correct tensor transformation from the legacy spin-only builder into common code. Legacy and canonical callers both call the shared implementation.

### 3.3 Hamiltonian symmetry gate

The gate receives a canonical Hamiltonian and a symmetry request. It first performs structural validation: Hermiticity, complete term identity, valid local frames, and availability of all required local symmetry representations.

It then either:

```text
repair=false: validate -> pass or fail before solvers
repair=true:  group average -> validate -> pass or internal failure
```

There is no mode that silently reduces to a smaller Hamiltonian subgroup and continues.

### 3.4 Solver adapters

All public solver pipelines consume the validated canonical Hamiltonian. They may convert it to legacy backend payloads, but they may not regenerate, reinterpret, or independently guess the structural symmetry.

Low-level numerical functions remain callable for backward compatibility. User-facing pipelines enforce the symmetry gate and bind results to the hash of the validated solver model.

## 4. Canonical Terms and Arbitrary Arity

The common term schema is:

```yaml
term:
  term_ref: string
  arity: integer
  cluster:
    - site: integer
      translation: [integer, integer, integer]
  operator_family: string
  coefficient: object
  coordinate_convention: string
  permutation_action: object
  adjoint_action: object
  provenance: object
```

A canonical key includes the operator family, canonical cluster, operator indices, and orientation sector. A bond is an arity-two cluster, not a separate incompatible storage system.

The generic local-operator tensor representation is

\[
h_C = \sum_{\mu_1\ldots\mu_k}
T^{(C)}_{\mu_1\ldots\mu_k}
O^{\mu_1}_{a_1}\cdots O^{\mu_k}_{a_k}.
\]

If the local operator representations are known, the same machinery supports any arity. Unsupported opaque terms fail the gate rather than being ignored.

Initial built-in operator families are:

- spin vector;
- quadratic spin tensor;
- general bilinear exchange tensor;
- biquadratic exchange;
- scalar chirality;
- cyclic ring exchange;
- generic local-operator tensor with explicit symmetry and permutation metadata.

Compact invariant families may remain compact, but they must have an unambiguous mapping to the generic operator representation.

## 5. Space-Group Action

Let a target operation be

\[
g=\{R_g\mid\boldsymbol\tau_g\}.
\]

For a primitive-cell site at `r_a`, determine the mapped site and cell offset from

\[
R_g\mathbf r_a+\boldsymbol\tau_g
=\mathbf r_{g(a)}+\mathbf L_{g,a}.
\]

For a cluster

\[
C=[(a_1,\mathbf L_1),\ldots,(a_k,\mathbf L_k)],
\]

the mapped cluster is

\[
gC=[(g(a_1),R_g\mathbf L_1+\mathbf L_{g,a_1}),\ldots].
\]

After mapping, translate and reorder the cluster into its family-specific canonical form. Every canonicalization permutation also acts on tensor indices and orientation metadata.

### 5.1 Physical spin

Convert the fractional-coordinate rotation to a Cartesian orthogonal matrix `Q_g`. Physical spin is an axial vector, so its global Cartesian representation is

\[
D_g=\det(Q_g)Q_g.
\]

For site-local frames `F_a`, use

\[
D^{\mathrm{local}}_{g,a}=F_{g(a)}^{-1}D_gF_a.
\]

The current placeholder local-frame action `preserve` is not sufficient for tensor validation.

Pseudospin and orbital degrees of freedom must supply their own local representation `rho_a(g)` or the corresponding adjoint representation in the chosen operator basis. The system must not guess that they transform as physical axial vectors.

### 5.2 Onsite and bilinear terms

For onsite quadratic anisotropy,

\[
A_{g(a)}=D_{g,a}A_aD_{g,a}^{\mathsf T}.
\]

For a bilinear term,

\[
h_{ab}(\mathbf L)=
\mathbf S_{a,\mathbf0}^{\mathsf T}J_{ab}(\mathbf L)
\mathbf S_{b,\mathbf L},
\]

the mapped tensor is

\[
J_{g(a)g(b)}(\mathbf L')=
D_{g,a}J_{ab}(\mathbf L)D_{g,b}^{\mathsf T}.
\]

If canonicalization reverses the bond,

\[
J_{ba}(-\mathbf L)=J_{ab}(\mathbf L)^\dagger,
\]

which is a transpose for real classical exchange matrices. Transforming the full matrix handles symmetric exchange and its antisymmetric DM sector consistently.

### 5.3 Higher-body terms

For an operator basis transformation

\[
U_gO_a^\mu U_g^{-1}
=\sum_\nu M^{(g,a)}_{\nu\mu}O_{g(a)}^\nu,
\]

the coupling tensor transforms on every leg:

\[
T'_{\nu_1\ldots\nu_k}
=\sum_{\mu_1\ldots\mu_k}
M^{(g,a_1)}_{\nu_1\mu_1}\cdots
M^{(g,a_k)}_{\nu_k\mu_k}
T_{\mu_1\ldots\mu_k}.
\]

Then apply the family-specific cluster permutation. Scalar chirality changes sign under odd site permutations. An oriented cyclic exchange maps reversal to the inverse cycle or Hermitian-conjugate sector. Generic many-body terms canonicalize only under explicitly declared equivalences.

## 6. Input Semantics

Existing explicit representative markers retain their established meaning. These include `orbit_ref`, `bond_orbit_representative_map`, canonical `attach_to.orbit_ref`, and explicit representative-cluster metadata. The compiler expands such a representative using the existing orbit generator before the gate.

A plain list without representative metadata is a complete explicit Hamiltonian. Unlisted canonical coefficients are zero. The system does not infer representative intent merely because only one bond or cluster is present.

## 7. Validation

Represent the canonical Hamiltonian as

\[
H=\sum_\kappa C_\kappa O_\kappa.
\]

For each target operation, construct the complete transformed coefficient map and compare

\[
\Delta_g=H-gH.
\]

An operation passes when

\[
\|\Delta_g\|_\infty
\leq
\epsilon_{\mathrm{abs}}+
\epsilon_{\mathrm{rel}}
\max(\|H\|_\infty,\|gH\|_\infty).
\]

The result also records a Frobenius norm, the worst term, and the worst component.

Hermiticity, site identity, coordinate conventions, magnetic-site closure under the structural group, and required local representations are validated before the group comparison. Symmetry repair does not repair an intrinsically non-Hermitian or semantically unresolved input.

Operations that individually pass are used for diagnostics. They are called an inferred Hamiltonian subgroup only after closure, identity, multiplication, and inverse checks pass within the discrete structural operation table. Otherwise the report says `candidate-operations-only`.

## 8. Optional Group-Average Repair

The only public repair switch is:

```yaml
symmetry_repair: false
```

The CLI spelling is `--symmetry-repair`; Python and serialized requests use the boolean field. The default is identical across all entry points.

When true, project the full coefficient map:

\[
H_{\mathrm{sym}}=
\mathcal P_G(H)=
\frac{1}{|G_{\mathrm{target}}|}
\sum_{g\in G_{\mathrm{target}}}gH.
\]

Implementation steps are:

1. Treat every absent canonical coefficient as zero.
2. Transform the full Hamiltonian under every target operation.
3. Accumulate by canonical term key.
4. Divide by the group order.
5. Remove only numerical residual coefficients below the declared cleanup tolerance.
6. Recheck Hermiticity.
7. Run the full symmetry validation again.

This naturally adds missing partners, averages inconsistent partners, and zeroes forbidden tensor components. It does not modify the user's source file. The original and projected canonical models both remain available through provenance.

Projection must be invariant and idempotent:

\[
g\mathcal P_G(H)=\mathcal P_G(H),\qquad
\mathcal P_G^2(H)=\mathcal P_G(H).
\]

## 9. Public Behavior and Failure Semantics

| Symmetric input | Repair flag | Result |
|---|---:|---|
| yes | false | pass unchanged |
| no | false | fail before every solver |
| yes | true | no-op projection, revalidate, continue |
| no | true | project, revalidate, continue |
| unknown structural group | either | fail |
| unavailable required local representation | either | fail |
| non-Hermitian or unresolved term identity | either | fail |
| failed post-repair validation | true | internal failure |

Validate-only failure returns:

```yaml
status: error
completion:
  status: failed
  reason: hamiltonian-symmetry-validation-failed
  stopping_condition: pre-solver-symmetry-gate
solver_execution:
  started: false
  backends_run: []
```

There is no automatic continuation with a reduced group.

A successful material repair adds a structured warning:

```yaml
warnings:
  - code: hamiltonian-symmetry-repaired
    message: The input Hamiltonian was projected onto the structural space group before solver execution.
```

If repair was requested but the model was already symmetric, record `already-symmetric` as informational provenance without a warning.

Required error codes are:

- `structural-symmetry-unavailable`;
- `symmetry-representation-unavailable`;
- `hamiltonian-not-hermitian`;
- `canonical-term-identity-unresolved`;
- `hamiltonian-symmetry-validation-failed`;
- `symmetry-projection-unsupported-term`;
- `symmetry-repair-postcheck-failed`;
- `solver-capability-mismatch`.

## 10. Reports and Provenance

Validation failure reports include the target group, verified diagnostic subgroup when available, failed operations, missing partners, forbidden terms, maximum absolute and relative residuals, and the first/worst offending canonical key and source term.

Repair reports contain:

```yaml
symmetry_repair_report:
  status: repaired | already-symmetric
  requested: true
  target_group: {}
  validation_before: {}
  projection:
    method: finite-group-average
    operation_count: integer
  changes:
    added_terms: []
    modified_terms: []
    zeroed_components: []
    unchanged_terms: []
    max_absolute_change: number
    max_relative_change: number
    l2_change: number
  validation_after:
    status: passed
  downstream_model_ref: string
```

For each coefficient,

\[
\Delta C_\kappa=C_{\kappa,\mathrm{repaired}}-C_{\kappa,\mathrm{input}}.
\]

Changes are classified as added, modified, zeroed, or unchanged. Reports preserve both canonical model hashes:

```yaml
hamiltonian_provenance:
  input_model:
    content_hash: string
    canonical_model_ref: string
  symmetry_operation:
    repair_requested: boolean
    target_group: object
    algorithm_version: string
    tolerance: object
  solver_model:
    content_hash: string
    canonical_model_ref: string
```

Every solver result refers to the solver-model hash. A validation stamp binds the target group, Hamiltonian hash, tolerances, and repair state. Any later Hamiltonian mutation invalidates the stamp and requires revalidation.

## 11. Solver Capability Boundaries

Passing the symmetry gate does not imply that a selected solver supports every term.

| Term family | Symmetry gate | Bilinear Fourier/LT | LSWT | GSWT | Real-space classical |
|---|---:|---:|---:|---:|---:|
| onsite field/anisotropy | yes | existing capability | adapter | adapter | later unification |
| bilinear 3-by-3 exchange | yes | yes | yes | yes | later unification |
| biquadratic | yes | not direct | capability-based | preferred | later |
| scalar chirality | yes | no | later | later | later |
| ring exchange | yes | no | later | later | later |
| generic higher-body tensor | with representation | no | capability-based | capability-based | capability-based |

A backend must reject an unsupported complete Hamiltonian with `solver-capability-mismatch`. It must never discard unsupported terms and solve a projection without explicit user authorization.

The present certified GLT branch-and-bound certifies its GLT/CP(N-1) relaxed objective over its declared q and weight domain. It is not by itself a certificate for the original fixed-length classical-spin problem. That promotion requires a feasible-state upper bound and a relaxed lower bound whose gap closes within tolerance.

## 12. Tests

### 12.1 Algebraic properties

Property tests cover:

- identity: `e * h = h`;
- composition: `g1 * (g2 * h) = (g1 g2) * h`;
- inverse: `g^-1 * (g * h) = h`;
- group-average invariance;
- projection idempotence;
- preservation of Hermiticity;
- equivariance of canonicalization;
- independence from input term order.

### 12.2 Physical regression cases

Required cases are:

- isotropic Heisenberg exchange is unchanged;
- a non-diagonal anisotropic exchange tensor is rotated rather than copied;
- a DM tensor transforms correctly under improper operations and forbidden components project to zero;
- nonsymmorphic operations correctly change sublattice and cell translation;
- site-local frames use `F_target^-1 D_g F_source`;
- a missing explicit orbit partner fails in strict mode and is added in repair mode;
- inconsistent equivalent bonds fail strictly and average under repair;
- biquadratic exchange generates a complete invariant orbit;
- scalar chirality changes sign under odd permutations;
- cyclic ring exchange handles cyclic relabeling and orientation reversal.

### 12.3 Pipeline integration

End-to-end tests prove:

1. Legacy, canonical lattice-term, and pseudospin paths produce the same canonical coefficient map for the same bilinear model.
2. Their validation results agree.
3. Their Fourier matrices agree elementwise at multiple random q points.
4. A failed gate invokes no LT, classical, LSWT, or GSWT backend.
5. A repaired model is the model hashed and consumed by every downstream backend.
6. Higher-body terms are never silently omitted by bilinear solvers.
7. Source files remain unchanged.
8. Input model, repaired model, and report serialize and replay deterministically.
9. Existing symmetric legacy inputs retain their numerical results.

### 12.4 Test execution environment

No test command is run in the local working environment. Verification must be submitted after logging into the cluster front end:

```text
ssh login002
```

The implementation plan must first inspect and reuse the repository's established scheduler/job-submission conventions. Tests run in submitted jobs, not interactively on `login002`, unless the repository documentation explicitly establishes a different permitted workflow. Job IDs, submission commands, terminal states, exit codes, and captured test summaries are retained as verification evidence.

## 13. Initial Delivery Scope

The first implementation is complete only when:

- the three principal input routes use the same symmetry action;
- strict validation is the default and blocks all solvers on failure;
- `symmetry_repair=true` performs complete group averaging and post-validation;
- onsite, bilinear, and arbitrary-arity generic operator tensors pass through the same gate;
- tested adapters exist for biquadratic, scalar chirality, and cyclic ring exchange;
- the existing 3N-sub Fourier kernel is reused;
- unsupported solvers do not truncate the Hamiltonian;
- reports, hashes, and provenance follow this contract;
- remote property, physical regression, integration, and non-regression test jobs pass.

Later projects build on this gate in dependency order:

1. fixed-spin-length recovery and real-space classical optimization;
2. unified LSWT/GSWT routing;
3. long-range dipolar Ewald;
4. three-dimensional classical Monte Carlo and finite-size scaling;
5. sparse Lanczos, QMC, and tensor-network backends.
