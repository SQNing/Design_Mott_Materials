# Isolated Literature Recalculation Adapters Design

**Status:** User-approved design, first review findings resolved; ready for rereview

**Date:** 2026-08-11

**Parent specification:** `2026-07-14-fail-closed-literature-reproduction-evidence-design.md`

**Parent implementation plan:** `2026-07-15-fail-closed-literature-reproduction-evidence-implementation.md`, Task 7

## Outcome

Task 7 replaces in-process literature benchmark helper calls with a fail-closed
recalculation service. A strict local recomputation will mean that a fresh
process calculated the declared observable from answer-free model inputs inside
an allowlist-only filesystem and empty network namespace, that every project
and runtime dependency was fixed before unpredictable audit inputs were
generated, and that an independently implemented oracle accepted the result.

This task does not preserve a historical target count of local recomputations.
A benchmark remains `local_recompute` only when every selected field is produced
by a real calculation satisfying this design. A paper claim, material label,
candidate phase, integrability label, or other status assertion is routed
through `local_source_parse` unless an actual calculation proves that exact
observable. The final project objective remains 155 strict literature matches;
the split between recomputation and source parsing is an evidence result, not a
quota.

## Current State

The legacy runtime collector currently contains 21 `local_recompute` specs. It
calls each Python function directly in the audit process and records the
function name, parameters, and returned operand. A prior migration design lists
another 21 recomputation candidates, for a total candidate set of 42. Some of
those functions perform useful algebra, enumeration, integration, matrix, or
Fourier calculations. Others mix a calculation with a stored status label or
evaluate only a supplied candidate point.

The current structural validator can check that an execution trace is shaped
correctly and that its claimed result equals another operand. It cannot prove
that the helper was isolated from the registry, evidence records, source cache,
reports, parent environment, previous outputs, or network. It also does not
record a transitive dependency closure, an embedded-output scan, unpredictable
counterfactuals, or an independent scientific oracle.

A host probe on the target machine established the following implementation
preconditions:

- `unshare -Urnm` succeeds;
- the child has a root UID/GID mapping in a new user namespace;
- mount propagation can be made private;
- a separate network namespace can be created;
- `strace` version 4.24 is available;
- `/proc/sys/user/max_user_namespaces` is 15000.

These observations establish feasibility only. Production code must repeat the
full capability preflight for every fresh audit and must not trust this design-
time probe.

## Goals

Task 7 must provide all of the following:

1. a closed, typed adapter contract containing no expected result;
2. an exact, auditable scientific dependency closure for each adapter;
3. static rejection of forbidden imports, answer tables, embedded outputs, and
   undeclared dependencies;
4. code and runtime-resource hashes fixed before counterfactual generation;
5. unpredictable, reproducible-after-disclosure counterfactual inputs;
6. execution under a new user, mount, and network namespace;
7. a private, allowlist-only, read-only chroot with one declared input mount and
   one writable output mount;
8. a scrubbed environment, bounded resources, and no child process execution;
9. a complete `strace` file/network/process access record with fail-closed
   policy evaluation;
10. typed observable identity, result, units, uncertainty, convergence data,
    and backend diagnostics;
11. a separately bundled scientific oracle outside the adapter dependency
    closure;
12. an exact-set eligibility decision for every current or planned
    recomputation candidate; and
13. one complete independence bundle for every outcome that later claims
    `local_recompute`.

## Non-Goals

Task 7 does not fetch literature, parse source payloads, select registry
operands, compare a local result with a literature target, issue a final strict
verdict, generate reports, or migrate the 155 evidence records. Task 8 consumes
the adapter evidence and performs comparison and verdict assembly. Tasks 8A and
9 select production routes and migrate records.

Task 7 is not a general untrusted-code hosting service. The trusted computing
base includes the Linux kernel, namespace and mount utilities, `chroot`,
`strace`, the declared interpreter and numerical libraries, and the coordinator
and isolation implementation. Native-library exploitation, a compromised
kernel, or a malicious system administrator are outside scope. Adapter source
and transitive project helpers are treated as potentially answer-leaking and
must pass all controls in this design.

## Chosen Approach

The implementation uses native Linux namespaces and an ephemeral mount tree.
This is preferred over a container runtime because it has no image or daemon
dependency and directly satisfies the parent plan's `unshare`, private mount,
chroot, and `strace` requirements. It is preferred over a normal subprocess
because a subprocess alone cannot establish filesystem, environment, or network
noninterference.

There is no weakened fallback. If any required Linux capability, trace feature,
runtime resource, or policy check is unavailable, the API returns a structured
`strict_recomputation_unavailable` failure and does not execute an unisolated
adapter.

## Production Components

Task 7 adds three focused production modules and one test module under
`translation-invariant-spin-model-simplifier`:

### `scripts/validation/literature_evidence_adapters.py`

This module owns the closed adapter contracts, the candidate eligibility
catalog, scientific adapter wrappers, parameter-domain declarations, output
validators, and backend/convergence declarations. It does not load the
literature registry, evidence inventory, source cache, reports, or parsed source
operands.

Existing pure helpers may be named as extraction sources. They are never
imported as their original whole module inside the sandbox. The isolation layer
extracts only the selected function and its statically resolved scientific
dependencies into a minimal capsule. This permits reuse of an existing pure
calculation without mounting `literature_spin_model_benchmarks.py` or
`literature_runtime_evidence.py`, both of which contain unrelated benchmark and
evidence material.

### `scripts/validation/literature_evidence_adapter_oracles.py`

This module owns independent algebraic, dense-matrix, real-space/Fourier, and
convergence oracles. An oracle may share the JSON transport and type validators
with the runner, but it may not import an adapter, an extracted adapter helper,
or any scientific node in the adapter closure. The oracle module contains no
registry values or literature targets.

### `scripts/validation/literature_evidence_isolation.py`

This module owns capability preflight, AST closure construction, static policy
scanning, runtime-resource manifests, capsule emission, counterfactual
generation, namespace and mount setup, the minimal JSON worker, resource limits,
trace parsing, isolation attestation, oracle execution, and independence-bundle
validation.

The worker is emitted from a fixed function in this module into each capsule.
It is not a separately importable project package inside the chroot. The emitted
worker hash is part of the infrastructure manifest.

### `tests/test_literature_evidence_adapters.py`

This test module covers contracts, eligibility, dependency extraction, static
scans, ordering, capability preflight, mount topology, adversarial access,
counterfactuals, oracle separation, typed outputs, environment diagnostics, and
all failure paths. Production integration with source and registry operands
belongs to Task 8 and Task 8A tests.

## Closed Contracts

All mappings use JSON-compatible values, reject unknown keys, reject non-string
keys, and are copied into immutable structures before use. Floats must be finite;
booleans are not accepted where a numeric value is required. JSON encoding uses
UTF-8, sorted keys, compact separators, and `allow_nan=False`.

### Adapter definition

Each `AdapterDefinition` contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `adapter_id` | Stable lower-snake-case identifier, distinct from a benchmark name |
| `entry_symbol` | Exact project source module and function to extract |
| `observable_identity` | The identity of the calculation actually performed |
| `scientific_input_schema` | Closed names, scalar/container types, bounds, and shape constraints for model inputs and probes |
| `numerical_control_schema` | Closed names, types, bounds, and ordering rules for precision and convergence controls |
| `parameter_sources` | Per-input provenance requirements |
| `output_schema` | Closed result field names, types, shapes, and units |
| `backend_kind` | One of `analytic`, `enumeration`, `dense_ed`, `glt_fourier`, or `iterative_numeric` |
| `problem_size_policy` | One of `not_applicable`, `fixed_local`, or `scalable_same_observable`, with identity-bound size data |
| `runtime_requirements` | Interpreter, package, native library, or backend resources |
| `convergence_contract` | Exact, residual-bound, finite-size, quadrature, or iterative requirements |
| `counterfactual_domain` | Valid and invalid input-generation rules |
| `oracle_id` | One separately defined oracle |
| `resource_limits` | CPU time, wall time, address space, output bytes, file descriptors, and process count |

`observable_identity` is a closed mapping containing subject, system or
material, Hamiltonian, parameter regime, size or thermodynamic limit,
observable definition, units, and conditions. It describes the adapter's own
calculation and is not populated from the canonical registry specification at
runtime. Task 8 compares it field by field with that independent specification.

An adapter definition contains no source ID, source hash, target locator,
literature operand, registry selector, registry operand, expected result,
comparison result, comparison tolerance, verdict, report field, or benchmark
lookup table.

### Parameter provenance

Every scientific input has exactly one provenance record with one of these
kinds:

- `canonical_model_parameter`: an independently maintained model input path;
- `source_model_parameter`: an exact source span establishing a model input
  that is not the target observable or an invertible restatement of it;
- `universal_probe`: a dimensionless probe chosen independently of the target;
- `numerical_control`: a grid, size, bond dimension, cutoff, seed, tolerance, or
  iteration control that changes precision rather than the scientific answer.

A source-derived critical coupling used merely to invert into the registered
critical temperature is target-equivalent and therefore not a valid model
parameter. A candidate ordering vector supplied because it is the registered
answer is also invalid. Provenance validation occurs outside the sandbox, but
only the answer-free input values and numerical controls are mounted into it.

The input validator recursively rejects keys or tagged values associated with
expected, target, answer, result, registry, evidence, verdict, comparison,
comparison tolerance, source operand, or report content. It also rejects
additional fields, aliases, positional payloads, object instances, callables,
NaN, and infinity. A predeclared convergence control such as
`quadrature_absolute_threshold`, `eigensolver_residual_threshold`, or
`truncation_cutoff` is permitted only in `numerical_control_schema`. It is fixed
and hashed before execution, must not be populated from the registry comparator,
and is never passed as a scientific input.

### Trusted authority boundary

Task 7 consumes, but does not produce, one closed `AdapterAuthorityContext`.
This type is the sole boundary through which canonical identity, parameter
provenance, and forbidden-output fingerprints enter the isolation service. It
contains exactly:

- schema version, audit run ID, and benchmark name;
- producer ID and producer-code SHA-256;
- canonical observable ID, complete observable identity, canonical-spec path,
  and canonical-spec SHA-256;
- closed scientific inputs and one parameter-provenance record per input;
- closed numerical controls and their non-registry provenance;
- registry snapshot SHA-256 and independently resolved selector SHA-256;
- canonical forbidden-output fingerprints and the fingerprint algorithm
  version; and
- a canonical context SHA-256 covering every preceding field.

The context is not mounted wholesale. The isolation service structurally
validates and hashes it, uses its fingerprints only in the outer static scanner,
and writes only answer-free scientific inputs and numerical controls into worker
requests. Benchmark name, registry commitments, fingerprints, canonical
identity, and provenance records remain outside the chroot.

Task 8 is the only authoritative production producer. It may construct this
context only after its independent canonical-observable loader, evidence-record
loader, source/provenance validator, and registry selector have succeeded. Task
8 records the exact producer code hash and later proves that the context hash in
`AdapterExecutionEvidence` is the one it produced. Any other producer ID,
producer-code hash, context mutation, incomplete fingerprint set, or context
whose selected registry operand does not regenerate the fingerprints is a
strict failure.

Task 7 deliberately does not authenticate those upstream facts by loading the
registry or source cache itself. Its standalone tests use a test-only authority
producer that independently constructs canary operands and parameter provenance;
those contexts prove the isolation API and leakage scans, not a production
literature match. Consequently, Task 7 can report
`isolated_recomputation_succeeded`, but only Task 8 can turn that evidence into a
strict literature verdict. This producer/consumer split keeps registry and
source selection out of the isolation module without trusting unstructured
caller assertions.

### Worker request

One worker request contains only:

- a schema version;
- an opaque run nonce;
- the adapter ID;
- one closed set conforming to `scientific_input_schema`;
- one closed set conforming to `numerical_control_schema`; and
- the hash of the exact capsule expected to execute.

It does not contain the benchmark name, source ID, target value, registry value,
comparator, tolerance, oracle result, or final verdict. The adapter ID is safe
to expose because the code has already been frozen before the request and
contains exactly one scientific entry point.

### Local observable result

A successful adapter writes exactly one `LocalObservableResult` containing:

- schema version and adapter ID;
- capsule hash and request hash;
- the adapter's complete observable identity;
- a closed field map of local results;
- units for every numeric field;
- uncertainty data for every approximate field;
- raw convergence samples and residuals;
- backend diagnostics;
- deterministic operation counts or problem sizes where applicable; and
- worker start and finish monotonic timestamps.

For an exact analytic or exact-enumeration result, uncertainty is explicitly
zero and convergence has kind `exact`; the fields are not omitted. Approximate
results return raw estimates, controls, residuals, and error bounds. The outer
validator, not the adapter, derives the accepted convergence boolean.

The result may not contain a strict-match flag, expected value, comparison to a
literature target, or prose claim of correctness.

### Independence bundle

`AdapterExecutionEvidence` aggregates the following mandatory objects:

1. the authority-context hash plus structurally validated parameter values and
   provenance bindings, with upstream authenticity reserved for Task 8;
2. adapter source-node hashes and dependency graph;
3. emitted capsule, worker, and runtime-resource hashes;
4. static forbidden-import, embedded-output, lookup-table, and undeclared-
   dependency scan results;
5. the ordering trace proving hashes preceded random-input generation;
6. the run-level capability-preflight report and its hash;
7. per-process namespace, mount, environment, resource-limit, and chroot
   attestations;
8. canonical and counterfactual request/result hashes;
9. complete `strace` log hashes and evaluated access-policy results;
10. interpreter, package, native-library, BLAS/LAPACK, and applicable backend
    versions and hashes;
11. raw convergence data and the independently derived convergence decision;
12. oracle code/dependency hashes, outputs, residuals, and decision; and
13. a closed success or failure status with a machine-readable reason code.

Every later `local_recompute` outcome must carry this complete object. A pointer
to a run-level preflight is acceptable only when the outcome contains the
preflight hash and the manifest contains exactly one matching immutable report;
per-process runtime attestations and traces are never replaced by a shared
pointer.

## Recalculation Eligibility Gate

Eligibility is decided per complete registry selector, not per helper function.
A candidate is eligible only if all of the following are true:

1. every selected field is an observable actually calculated by the adapter;
2. the adapter calculation has the same complete observable identity as the
   future canonical specification;
3. scientific inputs are model inputs, not target-equivalent quantities;
4. the result varies correctly over unpredictable valid counterfactuals and
   rejects invalid counterfactuals;
5. no target value, categorical answer, candidate answer set, or benchmark
   table appears in the scientific dependency closure;
6. the independent oracle can validate the calculation without importing its
   implementation;
7. all applicable convergence evidence is available; and
8. the complete isolated execution succeeds.

A record mixing a calculable numeric field with a material label, phase label,
integrability label, or other source-only claim is not partially promoted. If
all selector fields cannot be independently recomputed, the whole record uses
`local_source_parse`, unless the evidence schema is explicitly redesigned in a
later approved specification to support multiple independently adjudicated
modes for one benchmark.

The implementation maintains an exact-set `ADAPTER_ELIGIBILITY` catalog for the
42 candidate benchmark IDs listed in the appendix. The appendix is normative:
it fixes the disposition and, for every eligible entry, the exact adapter and
oracle IDs. The catalog must equal that table field for field; an implementer
cannot satisfy acceptance by assigning a convenient reason to an undecided
candidate. Each entry is either:

- `eligible`, with one adapter ID and one oracle ID; or
- `source_parse_only`, with one closed reason code.

Allowed `source_parse_only` reason codes are:

- `status_or_candidate_only`;
- `mixed_selector_contains_source_only_field`;
- `source_only_symbolic_or_categorical_field`;
- `target_equivalent_input`;
- `observable_identity_mismatch`;
- `no_independent_oracle`;
- `no_honest_convergence_evidence`; and
- `backend_unavailable_for_registered_limit`.

This catalog is migration metadata, not an authoritative verdict whitelist.
Task 8 still requires runtime evidence. Mutating a catalog label cannot produce
a strict result without a complete independence bundle.

Three previously ambiguous legacy shapes receive explicit treatment:

- `two_leg_ladder_strong_rung_exact_limit` currently returns a calculated rung
  gap together with an unselected extra `spin_ladder_material` helper field.
  The complete registry selector contains only `energy_per_rung` and
  `gap_to_triplet`; both are calculated by the two-spin rung Hamiltonian. The
  route is therefore `eligible`, the adapter capsule excludes the unselected
  material field, and closed output validation rejects that extra field.
- `triangular_nn_classical_120_reference` currently evaluates a supplied list
  containing the registered ordering vector and returns a selected phase label.
  Task 7 does not replace it with a global thermodynamic-limit minimizer; the
  normative disposition is `source_parse_only` with
  `status_or_candidate_only`.
- `cubic_ising_critical_temperature_reference` currently obtains `Tc/J` by
  inverting a supplied critical coupling. Because that coupling is an
  invertible restatement of the target rather than a model parameter, the
  normative disposition is `source_parse_only` with
  `target_equivalent_input`.

Other candidates are not presumed eligible merely because their current helper
returns the registered shape. The appendix chooses conservative source parsing
for formula-string, candidate-label, target-equivalent, or unsupported
thermodynamic-limit selectors and requires real replacement calculations for
the 29 entries it marks eligible. Parameterized tests apply the gate and exact
mapping to all 42 entries.

### Normative scientific implementations

The following methods are mandatory for the 29 eligible adapter/oracle pairs.
An existing helper may be extracted only when its transitive closure implements
the stated adapter method without extra selected status fields. Otherwise Task 7
adds an answer-free replacement calculation under the same adapter ID. An
implementation that merely returns the final analytic constant, phase label, or
boolean does not satisfy this table.

| Adapter ID | Backend | Required adapter calculation | Required independent oracle |
| --- | --- | --- | --- |
| `xxx_bethe_energy` | `analytic` | Evaluate the Bethe ground-state expression as a function of arbitrary positive exchange | Evaluate an independently coded alternating-series or integral representation with a certified tail bound |
| `square_ising_self_dual_tc` | `analytic` | Numerically solve the square-Ising self-duality equation for the positive critical coupling and invert the model temperature variable | Apply an independently rearranged Kramers-Wannier fixed-point residual and dual-temperature involution |
| `triangular_ising_af_entropy_quadrature` | `iterative_numeric` | Evaluate the Wannier entropy integral with declared quadrature refinements and error estimates | Evaluate an independently expanded convergent series with a bounded remainder |
| `xy_chain_bdg_boundaries` | `glt_fourier` | Construct the momentum-space Bogoliubov-de Gennes matrix and locate gap-closing conditions over answer-free fields and anisotropies | Diagonalize independently constructed dense momentum matrices and check determinant, particle-hole, and neighboring-gap invariants |
| `diamond_spiral_threshold_fourier` | `glt_fourier` | Construct the two-sublattice exchange kernel and derive the coupling at which its minima become a spiral surface | Compare direct real-space single-q energies and threshold-side minima using independently generated spin configurations |
| `spin_ice_tetrahedron_enumeration` | `enumeration` | Enumerate all sixteen Ising tetrahedron configurations and calculate energy and degeneracy sectors | Derive sectors independently from total charge squared and combinatorial multiplicities |
| `spin_ladder_rung_dense_ed` | `dense_ed` | Build and diagonalize the two-spin rung Hamiltonian, returning only singlet energy per rung and singlet-triplet gap | Evaluate analytic singlet/triplet projectors and their exact eigenvalues |
| `pauling_entropy_combinatorics` | `analytic` | Derive the Pauling entropy from the number of ice-rule tetrahedron states and shared-spin counting | Recompute the same asymptotic entropy using an independent finite-cluster combinatorial count and normalization |
| `uls_two_site_su3_matrix` | `dense_ed` | Build spin-1 bilinear and biquadratic matrices, solve the coefficient angle, and verify the two-site Hamiltonian is permutation-equivalent | Construct the SU(3) permutation and generator commutators independently and check all total-spin sectors |
| `aklt_projector_angle` | `analytic` | Expand the total-spin-two projector into bilinear/biquadratic coefficients and derive their angle | Reconstruct total-spin sectors from independent Clebsch-Gordan projectors and compare coefficient ratios |
| `compass_line_symmetry_matrix` | `dense_ed` | Build finite compass Hamiltonians and line-flip operators, then calculate every required commutator | Transform bond Pauli operators algebraically under independent line-flip strings and verify the symmetry action |
| `kitaev_field_majorana_mass` | `glt_fourier` | Construct the third-order Majorana mass from arbitrary nonzero field components and determine nonzero gap and odd Chern parity | Evaluate an independently coded two-band d-vector mass, gap minimum, and winding/Chern-sign invariant |
| `toric_code_stabilizer_rank` | `enumeration` | Construct the GF(2) stabilizer incidence matrix on a periodic torus and derive the ground-space dimension from its rank | Construct independent logical Wilson-loop pairs and their commutation algebra to derive the same degeneracy |
| `aklt_two_site_projector_ed` | `dense_ed` | Build the two-spin-one projector Hamiltonian and diagonalize its spin sectors and local VBS energy | Reconstruct the projector from independent Clebsch-Gordan sector polynomials and check eigenvalues and kernel |
| `blume_capel_level_crossing` | `enumeration` | Enumerate uniform spin-1 configurations with square-lattice bond counting and solve their zero-temperature energy crossing | Derive onsite and bond energies independently per site and verify both sides of the crossing |
| `checkerboard_plaquette_enumeration` | `enumeration` | Calculate the complete-graph crossed-plaquette energy over answer-free normalized spin configurations and minimize total spin | Use the independent total-spin-squared energy identity and explicit constraint residuals |
| `honeycomb_ising_star_triangle_tc` | `analytic` | Solve the honeycomb star-triangle critical equation for positive coupling | Transform independently to the dual triangular critical polynomial and verify reciprocal critical variables |
| `kagome_ising_af_entropy_quadrature` | `iterative_numeric` | Evaluate the kagome antiferromagnet entropy expression under successive quadrature refinements and establish a positive thermodynamic entropy | Use independent finite-width transfer counts to establish a positive lower bound and consistent limiting trend |
| `kagome_ising_star_triangle_tc` | `analytic` | Solve the kagome ferromagnet star-triangle critical equation | Verify an independently derived critical polynomial and transformation residual |
| `majumdar_ghosh_dimer_ed` | `dense_ed` | Build periodic J1-J2 chains at one half ratio, diagonalize more than one even size, and obtain energy density and translated ground-space degeneracy | Use the independent dimer-projector decomposition and translated covering states to check energy and rank |
| `ising_chain_transfer_matrix` | `analytic` | Construct the finite-temperature transfer matrix, derive both eigenvalues, and establish positive analytic separation for arbitrary finite inverse temperature | Derive the finite-size partition function independently and verify absence of a finite-temperature eigenvalue crossing |
| `pyrochlore_coulomb_fourier` | `glt_fourier` | Calculate the tetrahedron zero-sum minimum and transverse polarization tensor with directional pinch-point limits | Check the real-space divergence constraint and independently evaluate directional structure-factor limits |
| `shastry_sutherland_dimer_ed` | `dense_ed` | Construct an orthogonal-dimer cell Hamiltonian and calculate singlet-product energy per dimer and spin while verifying interdimer cancellation | Evaluate independent bond projectors on the product state and compare exact local expectations |
| `simple_cubic_j1_j2_fourier` | `glt_fourier` | Construct the simple-cubic Fourier exchange energy, minimize the Néel and collinear branches, and solve their crossing | Count first- and second-neighbor bonds in independent real-space configurations on both sides of the boundary |
| `spin1_single_ion_dense_ed` | `dense_ed` | Build and diagonalize the spin-one single-ion anisotropy matrix for arbitrary nonzero anisotropy | Enumerate independent magnetic quantum numbers and their squared eigenvalues and degeneracies |
| `fully_frustrated_ising_entropy_series` | `iterative_numeric` | Evaluate the fully frustrated square-Ising entropy series with successive truncations and a declared tail estimate, establishing macroscopic degeneracy | Use independent finite-width transfer matrices and normalized state counts to establish a positive limiting entropy |
| `tfim_bdg_critical_point` | `glt_fourier` | Construct the Jordan-Wigner BdG dispersion and locate its thermodynamic gap closing over arbitrary positive exchange | Apply independent duality and finite-chain parity-sector gap calculations with size scaling |
| `triangular_ising_star_triangle_tc` | `analytic` | Solve the triangular ferromagnet star-triangle critical equation | Verify the independently transformed honeycomb dual equation and critical-polynomial residual |
| `xx_chain_fermion_integral` | `iterative_numeric` | Integrate the occupied free-fermion dispersion with successive momentum refinements for arbitrary exchange | Diagonalize independent finite periodic XX chains at several sizes and extrapolate the energy density with a declared bound |

`problem_size_policy` is normative and prevents a counterfactual from silently
changing observable identity:

- `fixed_local` applies exactly to
  `spin_ice_tetrahedron_enumeration`, `spin_ladder_rung_dense_ed`,
  `uls_two_site_su3_matrix`, `aklt_two_site_projector_ed`,
  `blume_capel_level_crossing`, `checkerboard_plaquette_enumeration`, and
  `spin1_single_ion_dense_ed`. Their one-site, two-site, tetrahedron, or
  plaquette size is part of the observable identity and never varies.
- `scalable_same_observable` applies exactly to
  `compass_line_symmetry_matrix`, `toric_code_stabilizer_rank`,
  `majumdar_ghosh_dimer_ed`, and `shastry_sutherland_dimer_ed`. Their declared
  finite sizes are separate realizations of the same symmetry, topology, or
  exact product-state observable and must agree under the adapter's size rule.
- `not_applicable` applies to the remaining eighteen eligible adapters. Their
  physical observable is analytic or already in the declared thermodynamic or
  Fourier limit; quadrature grids, momentum grids, series truncations, and
  iterative cutoffs are numerical controls rather than physical system sizes.

The implementation stores the fixed size or allowed scalable size sequence in
the adapter definition and tests exact-set equality for all 29 policies. A
planner may not reclassify a numerical grid refinement as a physical second
size, or introduce a second local Hilbert-space size to satisfy a generic test.

The adapter result may contain lower-level numeric diagnostics needed to prove a
selected boolean, but its computed operand contains exactly the complete
selector fields in the appendix. Boolean fields such as pinch points, SU(3)
symmetry, a field-opened gap, or macroscopic degeneracy are derived by the outer
adapter validator from the mandatory residual, spectrum, entropy, or topology
data; the scientific capsule does not return an unexamined status literal.

## Scientific Dependency Closure

The closure builder parses source files as AST without importing their modules.
It begins at one declared function and recursively resolves every loaded global
name to one of:

- a Python builtin on a closed allowlist;
- an explicitly allowed standard-library or numerical-package import;
- a function or class definition in an approved project source file; or
- an immutable scalar or small structural constant with a declared scientific
  purpose.

The builder includes only resolved nodes, preserves their dependency edges, and
emits a standalone module in deterministic topological order. It fails on an
unresolved name, cyclic value initialization, star import, import alias that
cannot be resolved, dynamic import, module mutation, mutable global, descriptor,
metaclass, decorator with side effects, closure over runtime objects, or any
form of source evaluation.

The following project modules and symbol families are forbidden as sandbox
imports or included assignments:

- literature benchmark registry objects, including
  `LITERATURE_STANDARD_RESULTS`;
- evidence schema records carrying target or comparison data;
- evidence inventory and record loaders;
- source-index, provisioning, cache, and parser loaders;
- audit, manifest, report, and PDF generators;
- Git, workspace, environment-discovery, and previous-output helpers; and
- any symbol matching the closed expected/target/result/verdict vocabulary.

The closure manifest records each original relative path, original raw-file
SHA-256, node kind and qualified name, exact source span hash, emitted-node hash,
dependency edges, deterministic bundle hash, and scanner version. The raw
source file is not mounted into the chroot.

### Embedded-output scan

The isolation coordinator consumes the canonical forbidden fingerprints from
the closed authority context solely for rejection. It validates their encoding,
algorithm version, uniqueness, and commitment hash but does not load the
registry. Task 8 regenerates the set from its independently selected registry
operand and authenticates completeness before any final strict verdict. The
fingerprints are never placed in the capsule or request. Static scanning rejects:

- a complete serialized registered operand;
- a mapping or sequence reproducing a registered field/value structure;
- registered categorical strings or phase/material labels;
- benchmark names coupled to literal return values;
- nontrivial high-precision numeric literals equal to registered outputs;
- branches selecting a literal result by adapter or benchmark identity; and
- lookup structures covering registered parameter/result pairs.

Small mathematical constants such as zero, one, two, one half, and signs cannot
be rejected solely because a registry field happens to equal them. They remain
subject to AST context checks, the ban on result lookup structures, randomized
counterfactual behavior, and the independent oracle. Categorical result strings
are not exempt; a route needing a paper-supplied category uses source parsing
unless the adapter returns a lower-level calculated quantity from which the
outer comparator derives the category.

### Runtime resource closure

Before counterfactual generation, the coordinator constructs a runtime-resource
manifest containing the exact interpreter binary, dynamic loader, native
libraries reported by `ldd`, required Python standard-library paths, declared
package files, and applicable backend executables or libraries. It records
resolved paths, file type, byte length, SHA-256 for regular files, distribution
name/version, and mount destination. Symlinks are resolved and both link and
target identities are recorded. A resource resolving into the project,
workspace parent, source cache, reports, user configuration, or an undeclared
package fails validation.

The runner never bind-mounts a mutable original runtime or package directory.
Before obtaining the random seed, it materializes every declared regular file
into a new file-level runtime snapshot under the exclusive run directory. Each
source is opened no-follow, checked with `fstat` before and after copying, and
copied to an exclusively created destination. The destination is flushed,
reopened no-follow, byte-compared, hashed, and assigned only its required read
or read/execute mode. Snapshot directories contain no writable or undeclared
entry and are made non-writable after construction. The manifest commits both
the original identity and exact snapshot file identity.

Private roots mount only these snapshot files at their declared logical
destinations; they do not mount original interpreter, library, standard-library,
or package paths. The coordinator retains directory FDs for the snapshot and,
after every adapter and oracle process has exited, reopens every file no-follow
and revalidates type, device/inode policy, byte length, mode, and SHA-256. Any
pre-copy race, post-copy mutation, missing file, replacement, or hash difference
invalidates all outcomes using that snapshot. This pre-seed snapshot plus post-
execution revalidation closes host-side read-only-bind drift for the stated
non-malicious-host threat model.

The actual snapshot files opened at runtime, reconstructed from `strace`, must
be a subset of this pre-hashed manifest plus the capsule, input, and output
paths. No resource discovered only after execution is retrospectively accepted.

## Mandatory Event Ordering

The coordinator records an append-only sequence number for each stage. The
required order is:

1. validate the adapter definition and parameter-provenance schema;
2. construct and hash the scientific closure;
3. run all static scans;
4. construct, materialize, byte-compare, and hash the runtime-resource snapshot;
5. emit and hash the adapter and oracle capsules;
6. freeze all code, dependency, scanner, and runtime hashes;
7. obtain 32 random bytes from the operating system;
8. derive counterfactual points with a versioned deterministic generator;
9. write each closed request by exclusive creation;
10. execute canonical and counterfactual processes;
11. execute the independent oracle processes;
12. evaluate convergence, isolation, and oracle evidence; and
13. disclose the random seed and hash the final evidence bundle.

Tests inject an event recorder and require these sequence relations. Wall-clock
timestamps are supplemental and cannot substitute for ordering. The disclosed
seed makes a completed run reproducible, while a fresh audit obtains a new seed
after newly freezing its hashes.

## Capability Preflight

Every fresh audit runs the same production preflight used by adapter execution.
The preflight creates a new, caller-scoped scratch directory using exclusive
creation and never overwrites a pre-existing path. Namespace mounts disappear
when their process exits. Host-side scratch artifacts are retained with their
run marker under the current file-safety policy; Task 7 performs no recursive or
implicit cleanup.

The preflight proves each of these properties with an executed probe:

1. `unshare -Urnm` creates distinct user, mount, and network namespace IDs;
2. the current user maps to root inside the user namespace without `sudo`;
3. `/` can be made recursively private in the mount namespace;
4. a tmpfs can be mounted as a new root;
5. a bind mount can be remounted read-only and a write attempt fails;
6. the assembled root can be remounted read-only while a nested output bind
   remains writable;
7. `chroot` can execute the declared interpreter in the assembled root;
8. all capabilities can be dropped after chroot and before worker execution;
9. an environment canary present in the parent is absent from the worker;
10. the new network namespace has no configured external interface or route and
    a bounded connection probe fails;
11. a host file canary outside the chroot is unreadable;
12. `strace` can follow the complete worker process, record file/network/process
    syscalls, preserve sufficiently long path strings, and expose directory-FD
    resolution needed for `openat` policy evaluation;
13. both a permitted read and a forbidden failed read appear in the trace; and
14. resource limits and no-new-privileges are observable in the child.

The report contains individual booleans, command paths, tool versions and
hashes, namespace identifiers, mount facts, probe result codes, trace hash, and
one closed overall status. Missing, malformed, contradictory, or partially
successful evidence sets `available=false`. The runner does not infer
availability from platform name or tool presence alone.

## Private Root and Mount Policy

The outer coordinator first creates a unique mode-0700 run directory using
exclusive creation. It contains three disjoint subdirectories: `supervisor`,
`input`, and `worker-output`. The coordinator opens and retains directory FDs
for all three, verifies their device/inode identities and absence of symlink
components, and never exposes the `supervisor` subdirectory to the worker.

The process topology is fixed:

```text
outer coordinator in the original namespaces
  `-- unshare -Urnm namespace supervisor
        |-- constructs and attests the private mount tree
        `-- strace tracer outside the chroot
              `-- fixed tracee launcher
                    `-- chroot, drop capabilities, set limits, exec worker
```

The namespace supervisor is trusted infrastructure. It is launched with a clean
environment and closed unrelated file descriptors, stays outside the chroot,
and remains alive until the tracer and tracee have exited. It makes mount
propagation private, mounts a new tmpfs root, creates only declared mount points,
performs bind mounts, then remounts the root and every non-output mount read-
only. The `worker-output` bind is the only writable filesystem visible to the
worker.

The chroot has this logical layout:

| Path | Source and mode |
| --- | --- |
| `/runtime` | Pre-seed snapshot of the interpreter, loader, standard library, declared packages, and native libraries; read-only |
| `/adapter` | One emitted scientific capsule and fixed worker; read-only, no device, no set-ID |
| `/input/request.json` | One regular request file bind-mounted read-only with no symlink components |
| `/output` | Only the new `worker-output` subdirectory; writable, no device, no set-ID |

There is no project mount, parent/workspace mount, source-cache mount, evidence
mount, report mount, home directory, `/proc`, `/sys`, general `/dev`, host `/tmp`,
Git directory, or previous-run mount. If a backend requires temporary files,
its declared scratch subdirectory is inside `/output` and all scratch paths are
included in the evidence. A backend requiring an additional writable mount is
not strict-compatible under this design.

After mount construction, the namespace supervisor launches a trusted tracer
that remains outside the chroot and writes its log to an exclusively created
regular file beneath the supervisor-only directory. The tracer launches one
fixed tracee. Only that tracee enters the chroot, drops all capability sets,
sets no-new-privileges, changes directory to `/`, applies resource limits, and
executes the exact pre-hashed interpreter with isolated-mode flags. The worker
inherits no supervisor, input-host, trace, attestation, or previous-output FD.
Standard output and error are drained through bounded pipes owned by the
supervisor and stored outside the worker-visible mount.

The namespace supervisor waits for the complete traced process tree, records
exit status, rechecks the namespace and mount facts, and then exclusively
creates the namespace/mount attestation beneath the supervisor-only directory.
The outer coordinator waits for the namespace supervisor before reading any
worker artifact. Trace logs and attestations are therefore never writable or
visible from `/output`.

The result is accepted only from the fixed basename `result.json` beneath the
coordinator's retained `worker-output` directory FD. After all worker processes
have exited, the coordinator opens that basename with `openat` using
`O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`, then validates with `fstat` that the
opened object is a regular file, has exactly one link, has the expected owner,
mode and device, and lies within the configured byte bound. It hashes and parses
bytes from that same FD without reopening a path. A symlink, hard link, FIFO,
device, socket, directory, unexpected owner/mode, changed directory identity,
or undeclared extra output fails the run. Declared backend scratch entries are
validated by the same no-follow, regular-file-or-directory allowlist rules and
can never substitute for `result.json`.

## Environment and Resource Policy

The outer launch begins with an empty environment and adds only fixed locale,
deterministic hash, and declared numerical-thread controls. User environment
variables, credentials, proxy configuration, Python path overrides, package
configuration, home-directory variables, and backend configuration are absent.
An adapter-specific environment addition is permitted only when its name and
value are part of the pre-hashed runtime manifest and contain no path outside
the chroot.

The worker may not fork, clone, spawn, or execute another process. CPU time,
wall time, address space, output size, open files, and process count are bounded
by the closed `resource_limits` declaration and global safety maxima. Timeout,
signal termination, output overflow, memory exhaustion, or limit mismatch is a
strict failure with no retry under weaker limits. A caller may start a new audit
with a newly declared, re-hashed limit when scientifically justified.

## Runtime Access Trace

`strace` follows the full worker process and records file, network, and process
syscalls with untruncated strings and directory-FD annotations. The parser is a
closed parser for the exact preflight-verified trace format; an unknown syscall
shape, unfinished/resumed mismatch, missing PID log, truncated path, or parse
error rejects the run.

The policy evaluates attempted access, not only successful access. A forbidden
`openat` that returns `ENOENT` is still an isolation violation. Allowed reads
are limited to the pre-hashed runtime closure, `/adapter`, and
`/input/request.json`. Allowed writes are limited to declared files beneath
`/output`. Any network syscall is forbidden. After the fixed startup execution
chain, any process-creation or execution syscall is forbidden.

The evaluator resolves absolute and relative paths, directory FDs, `.` and `..`,
symlinks, and renamed paths against the mount manifest. It rejects path-prefix
confusion such as `/runtime-extra` matching `/runtime`. It compares filesystem
identities where trace information permits and rejects any trace that cannot be
resolved without guessing.

Tests cover attempted access to the registry, canonical observable inventory,
evidence records, source cache, reports, protected WIP files, parent environment
canary, previous outputs, host filesystem canary, and network. Static rejection
and runtime chroot denial are tested separately so either control can fail
closed without being mistaken for proof of the other.

## Counterfactual Protocol

Each adapter definition provides a domain generator rather than a list of fixed
test points. The generator consumes the disclosed 256-bit seed only after all
code and runtime hashes are frozen. It emits canonical input separately from
counterfactuals and never receives a registry operand.

Minimum counterfactual coverage is:

- analytic adapters: three random valid parameter points and one invalid
  boundary point that must be rejected;
- `fixed_local` enumeration or dense ED: three random valid couplings, fields,
  anisotropies, overall scales, or basis/gauge transformations at the single
  identity-bound size, plus one invalid parameter or different-size shape that
  must be rejected;
- `scalable_same_observable` enumeration or dense ED: two random valid physical
  parameter points at each of two declared sizes, plus one invalid shape or
  disallowed size;
- GLT/Fourier adapters: three random valid couplings and two random momenta or
  configurations per coupling, including a real-space/Fourier identity check;
- iterative numerical adapters: one random valid model point and at least three
  progressively stronger numerical controls, plus one invalid control.

An analytic or fixed-local adapter with no continuous canonical model parameter
uses declared answer-free overall scales, unitary/orthogonal basis changes, or
gauge-equivalent representations whose invariants are checked by the oracle.
Those are counterfactual scientific probes, not changes to the observable's
physical size or target value.

Each point executes in a fresh chrooted worker process using the same frozen
capsule. This prevents cross-point mutable state. Domain generation enforces
distance from singular boundaries unless the adapter specifically declares a
boundary-limit test. Invalid points must fail with the declared validation
reason before scientific calculation; returning a plausible value is failure.

The outer validator checks declared metamorphic properties, dimensional scaling,
symmetries, bounds, or continuity in addition to the oracle. A constant result,
finite answer table, branch on a canonical point, or supplied candidate list
cannot pass this protocol unless it also implements the actual general
calculation.

## Independent Oracle Protocol

The oracle is bundled and hashed separately. Its project scientific source
nodes and transitive project scientific dependencies must have an empty
intersection with the adapter's scientific closure. Standard interpreter and
numerical-library files may be shared only as pre-hashed runtime resources; no
project formula, helper, constant, table, or scientific implementation may be
shared. Fixed transport, canonical JSON validation, and isolation infrastructure
are recorded in a separate infrastructure closure rather than either scientific
closure.

The oracle closure passes the same forbidden-import, unresolved-dependency,
embedded-output, categorical-answer, benchmark-table, and registry-fingerprint
scans as an adapter closure. Its code, runtime-resource manifest, and scanner
results are frozen before the random seed is obtained. A separately hashed
capsule is necessary but not sufficient: any static scan failure rejects the
oracle.

The oracle receives the same answer-free model inputs. It does not receive a
source operand, registry operand, comparator tolerance, or verdict. When an
invariant necessarily evaluates an adapter result, the outer coordinator places
that already validated result in a new typed oracle request after adapter
completion; it does not mount or expose the adapter output directory. The oracle
still cannot influence the adapter run. Oracle output is compared by the
coordinator under the adapter's declared numerical contract.

Every oracle point runs through the same isolation service in its own fresh
`unshare -Urnm` process, private read-only chroot, scrubbed environment, empty
network namespace, resource limits, supervisor-only `strace` log, and hardened
no-follow output ingestion. It receives no registry, source, report, environment
secret, previous-output path, or network capability. Its per-process namespace,
mount, trace, access-policy, environment, and output attestations are mandatory
parts of the independence bundle. An oracle does not inherit success merely
because the corresponding adapter isolation passed.

Required oracle families are:

- `analytic`: independently rearranged equations, limiting cases, scaling laws,
  or exact algebraic identities;
- `enumeration` and `dense_ed`: independently constructed dense matrices or
  configuration sums with Hermiticity, trace, degeneracy, and symmetry checks;
- `glt_fourier`: direct real-space energy or constraint evaluation compared with
  Fourier-kernel eigenvalues and reciprocal-space symmetries;
- `iterative_numeric`: residual norms, variational or rigorous bounds,
  finite-size/bond-dimension/cutoff sequences, and independently evaluated
  convergence envelopes.

An oracle that only compares with a copied expected number is invalid. Missing
oracle code, closure overlap, static-policy failure, isolation or access-policy
failure, result mismatch, excessive residual, or malformed oracle evidence makes
the adapter outcome non-strict.

## Backend and Convergence Evidence

Backend diagnostics record the interpreter implementation/version and binary
hash, used Python distributions and file hashes, NumPy/SciPy versions when
applicable, BLAS/LAPACK provider and loaded-library hashes, and exact TenPy,
Julia, or other backend versions and executable/package hashes when declared.
Unused optional backends are marked `not_applicable`, not omitted. A declared
backend that cannot be identified is unavailable.

Convergence is derived outside the adapter:

- exact algebra and enumeration require exact identities and zero declared
  uncertainty;
- floating analytic evaluation requires a residual or roundoff bound;
- quadrature requires at least two refinements and a bound or stable-difference
  rule declared before execution;
- dense ED requires Hermiticity and residual checks plus size honesty;
- GLT requires reciprocal-space resolution or analytic minimization evidence
  and direct-energy invariants;
- iterative numerics require raw control sequences, residuals, truncation data,
  and the declared convergence envelope.

A helper-returned `converged=true` flag is ignored. A calculation at a smaller
cluster, different limit, or representative point cannot pass the observable-
identity comparison even when numerically close.

## Failure Semantics

All errors are data, not promotions. The closed top-level statuses are:

- `isolated_recomputation_succeeded`;
- `strict_recomputation_unavailable`;
- `adapter_ineligible`;
- `input_rejected`;
- `dependency_rejected`;
- `isolation_failed`;
- `execution_failed`;
- `convergence_failed`; and
- `oracle_failed`.

Only `isolated_recomputation_succeeded` carries a successful independence
bundle, and Task 8 must still authenticate its authority context and compare it
with independently parsed literature and registry operands. Exceptions,
unavailable tools, malformed output, nonzero
exit status, timeout, signal, missing trace, unparseable trace, undeclared read,
network syscall, missing version, closure mismatch, non-convergence, and oracle
failure cannot be retried in a weaker mode or translated into success.

Failure objects include the stage, closed reason code, bounded diagnostic,
available hashes and attestations, and no scientific success flag. Diagnostics
must not copy environment values or source/registry contents.

## Test Design

Implementation follows test-driven development. Tests are organized into these
gates:

### Contract and eligibility tests

- reject unknown, missing, mutable, non-JSON, nonfinite, or wrongly typed fields;
- reject expected-output and target-equivalent parameters recursively;
- require exact candidate-set equality with the 42 appendix IDs;
- require the appendix's exact 29 eligible and 13 source-parse dispositions,
  complete selectors, adapter/oracle IDs, and reason codes;
- require the exact seven `fixed_local`, four `scalable_same_observable`, and
  eighteen `not_applicable` size-policy assignments;
- reject an authority context with an unknown producer, stale producer hash,
  stale canonical/registry/selector hash, incomplete fingerprints, mismatched
  context hash, or target-derived parameter provenance;
- prove worker requests contain none of the authority-only fields;
- prove status, candidate-only, mixed-selector, and target-equivalent examples
  have exactly the appendix's source-parse-only disposition;
- require every eligible entry to have one adapter, domain, convergence
  contract, and independent oracle.

### Closure and static-policy tests

- extract a known pure helper without mounting its containing registry module;
- hash every node and dependency edge deterministically;
- reject registry/evidence/source/report imports and global references;
- reject dynamic imports, reflection, evaluation, file/network/process APIs,
  mutable globals, unresolved dependencies, and import side effects;
- reject direct literals, structured operands, lookup tables, and transitive
  helper copies of registered outputs;
- prove changing one transitive helper changes the closure and capsule hashes;
- prove an oracle scientific node cannot enter the adapter closure;
- apply every forbidden-import, registry-fingerprint, embedded-output, and
  undeclared-dependency mutation independently to an oracle capsule and require
  rejection;
- mutate an original runtime file during snapshot construction, mutate or
  replace a snapshot file after hashing, and require rejection; mutate an
  original path only after a valid snapshot and prove the worker still opens the
  unchanged snapshot rather than the original.

### Ordering and counterfactual tests

- prove every code/runtime hash event precedes random-byte acquisition;
- prove a fixed disclosed seed reproduces points while a fresh seed changes
  them;
- prove each backend family receives its required minimum point set;
- prove fixed-local adapters never execute a second valid physical size and
  reject one as an identity mismatch, while scalable adapters execute exactly
  the declared same-observable size sequence;
- reject constants, canonical-point branches, supplied candidate lists, and
  invalid-point acceptance;
- require one fresh isolated process and trace per point.

### Capability and isolation tests

- execute the full positive preflight on the target Linux host;
- independently force each capability check to fail and assert structured
  unavailability with no fallback execution;
- prove the private root contains exactly the allowed mount classes;
- prove root, runtime, adapter, and input are read-only and output alone is
  writable;
- prove chroot, capability dropping, no-new-privileges, resource limits, clean
  environment, distinct namespaces, and empty network namespace;
- prove missing or malformed attestation invalidates the run;
- replace `result.json` independently with a symlink, hard link, FIFO, socket,
  directory, wrong-mode file, oversized file, and undeclared extra output and
  require rejection through descriptor-pinned no-follow ingestion.

### Adversarial information-flow tests

- attempt reads of registry, canonical specifications, records, source cache,
  reports, protected WIP, parent files, and previous outputs;
- attempt environment-secret access;
- attempt network socket and connection use;
- attempt symlink, relative-path, directory-FD, and prefix-confusion escapes;
- attempt subprocess creation and undeclared native-library loading;
- require rejection for both successful and failed forbidden syscalls;
- mutate, truncate, omit, or make a trace unparsable and require failure;
- repeat registry/source/report, environment-secret, network, previous-output,
  symlink-output, and malformed-trace attacks against an oracle process rather
  than inferring oracle isolation from adapter tests.

### Scientific and evidence-bundle tests

- exercise at least one real analytic, dense-ED or exact-enumeration,
  GLT/Fourier, and iterative-numeric adapter shape;
- require typed identity, units, uncertainty, raw convergence, and diagnostics;
- require independent oracles, empty project-scientific-closure intersection,
  complete oracle static scans, and complete per-oracle isolation evidence;
- require exact, residual, quadrature, finite-size, and iterative convergence
  decisions where applicable;
- parameterize every eligible production adapter and require the complete
  independence bundle;
- parameterize every source-parse-only candidate and prove no isolated success
  object can promote it.

On a host lacking a capability, unit and negative tests still require the
correct unavailable result. The Task 7 acceptance run on the designated target
host additionally requires the positive production preflight and real isolated
adapter tests to execute; skipping those tests is not Task 7 completion.

## Task 7 Acceptance Criteria

Task 7 is complete only when all of the following are true:

1. the three production modules and adapter test module exist;
2. the eligibility catalog exactly matches all 42 normative appendix rows,
   including 29 eligible and 13 source-parse-only dispositions, selectors,
   adapter/oracle IDs, reason codes, and the exact 7/4/18 problem-size policies,
   with no missing, duplicate, or extra ID;
3. every one of the 29 eligible candidates has the required real adapter,
   answer-free input contract, counterfactual domain, convergence contract, and
   separate oracle;
4. every one of the 13 ineligible candidates has its mandated source-parse-only
   reason and cannot produce an isolated adapter success;
5. full positive capability preflight succeeds on the designated host;
6. all static leakage, namespace, filesystem, environment, network, process,
   trace, runtime-snapshot TOCTOU, counterfactual, and oracle adversarial tests
   pass;
7. every eligible production adapter produces a complete independence bundle
   bound to one structurally valid authority-context hash, while tests prove
   only Task 8's authenticated producer can later support a strict verdict;
8. no test fixture containing an expected output is mounted into a successful
   production-style worker;
9. `python -m pytest tests/test_literature_evidence_adapters.py -q` passes
   without skipped mandatory isolation tests;
10. relevant schema, inventory, source, parser, comparator, runtime, and audit
    regression suites still pass;
11. `git diff --check`, focused lint/compile checks, protected-file hash checks,
    and exact commit-path checks pass; and
12. an independent non-Fast specification review and subsequent implementation
    review find no blocking issue.

Task 7 passing does not establish a literature match by itself. Task 8 must
consume this evidence through the fail-closed auditor, and Tasks 8A and 9 must
prove the production matrix and all 155 records.

## Compatibility and Migration Boundary

The legacy `collect_runtime_evidence` path remains non-authoritative until Task
8 replaces it. Task 7 may wrap or extract existing pure helpers, but it must not
make the legacy direct-call trace appear isolated. Old execution records lacking
the complete new evidence object remain structurally insufficient for strict
recomputation.

Task 8 integrates `AdapterExecutionEvidence`, compares its local operand and
observable identity with independent source and registry operands, and removes
whitelist promotion. Task 9 uses the eligibility catalog when choosing each
record's mode. Reclassification from recompute to source parse is expected and
does not weaken the final standard because the source parser still has to prove
the exact literature claim from authoritative bytes.

## File and Worktree Safety

All Task 7 production and test files are additive unless a later approved plan
explicitly identifies a narrowly required pure-helper edit. New run and output
paths use exclusive creation. Task 7 does not delete, truncate, move, overwrite,
or clean project files, caches, generated reports, or untracked artifacts.

The following pre-existing user-owned WIP remains outside Task 7 and must stay
unstaged and byte-identical throughout its commits:

- `translation-invariant-spin-model-simplifier/reports/generate_literature_reproduction_audit_pdf.py`;
- `translation-invariant-spin-model-simplifier/tests/test_literature_reproduction_audit_pdf.py`;
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.csv`;
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.md`;
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit_43_of_155.pdf`; and
- `translation-invariant-spin-model-simplifier/reports/remaining_strict_reproduction_gaps.md`.

Before and after every Task 7 commit, the existing protected-baseline verifier
is run with no allowed source-cache targets. A commit is rejected if it contains
any path outside the reviewed Task 7 scope.

## Appendix: Normative Candidate Dispositions

The eligibility catalog covers exactly these 42 benchmark IDs. The first table
is registered by the legacy runtime collector; the second comes from the
approved 155-record migration design. The selector column is the complete
current registry selector. `eligible` rows must use the exact adapter and oracle
IDs shown. `source_parse_only` rows must use the exact reason shown and have no
adapter or oracle ID. These are implementation requirements, not examples.

### Legacy collector candidates

| Benchmark | Complete selector fields | Disposition | Adapter ID | Oracle ID | Source-parse reason |
| --- | --- | --- | --- | --- | --- |
| `xxx_spin_half_chain_bethe_ground_state` | `energy_per_site` | `eligible` | `xxx_bethe_energy` | `xxx_bethe_integral_oracle` | — |
| `one_dimensional_classical_ising_correlation_length` | `formula`, `correlation_length_beta_1_j_1` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `two_dimensional_square_ising_onsager_tc` | `tc_over_j` | `eligible` | `square_ising_self_dual_tc` | `square_ising_duality_residual_oracle` | — |
| `two_dimensional_square_ising_spontaneous_magnetization` | `formula`, `magnetization_beta_0_6_j_1` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `square_potts_exact_critical_point` | `critical_beta_j`, `continuous_for_q_le_4` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `triangular_ising_antiferromagnet_residual_entropy` | `residual_entropy_per_spin` | `eligible` | `triangular_ising_af_entropy_quadrature` | `triangular_ising_af_entropy_series_oracle` | — |
| `xy_spin_half_chain_anisotropic_critical_line` | `ising_critical_field`, `anisotropy_transition_gamma` | `eligible` | `xy_chain_bdg_boundaries` | `xy_chain_dense_bdg_oracle` | — |
| `diamond_j1_j2_spiral_surface_reference` | `spiral_surface_for_j2_over_j1_gt` | `eligible` | `diamond_spiral_threshold_fourier` | `diamond_real_space_threshold_oracle` | — |
| `spin_ice_tetrahedron_nn_ice_rule` | `two_in_two_out_energy`, `three_in_one_out_energy`, `all_in_all_out_energy`, `two_in_two_out_degeneracy` | `eligible` | `spin_ice_tetrahedron_enumeration` | `spin_ice_tetrahedron_matrix_oracle` | — |
| `square_j1_j3_classical_lifshitz_reference` | `spiral_condition` | `source_parse_only` | — | — | `source_only_symbolic_or_categorical_field` |
| `two_leg_ladder_strong_rung_exact_limit` | `energy_per_rung`, `gap_to_triplet` | `eligible` | `spin_ladder_rung_dense_ed` | `spin_ladder_analytic_rung_oracle` | — |
| `square_ashkin_teller_exact_critical_line` | `has_exact_critical_line` | `source_parse_only` | — | — | `status_or_candidate_only` |
| `pyrochlore_dipolar_spin_ice_pauling_entropy` | `pauling_entropy_per_spin` | `eligible` | `pauling_entropy_combinatorics` | `pauling_cluster_count_oracle` | — |
| `two_dimensional_xy_bkt_universal_jump` | `formula`, `helicity_modulus_at_t_1` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `uimin_lai_sutherland_spin1_su3_point` | `theta_radians`, `su3_symmetric` | `eligible` | `uls_two_site_su3_matrix` | `uls_permutation_commutator_oracle` | — |
| `bilinear_biquadratic_spin1_chain_aklt_angle` | `aklt_tan_theta`, `theta_radians` | `eligible` | `aklt_projector_angle` | `aklt_two_spin_spectrum_oracle` | — |
| `square_compass_model_directional_exchange_degeneracy` | `has_line_flip_symmetries` | `eligible` | `compass_line_symmetry_matrix` | `compass_spin_flip_oracle` | — |
| `kitaev_honeycomb_abelian_nonabelian_field_gap_reference` | `field_opens_non_abelian_gap` | `eligible` | `kitaev_field_majorana_mass` | `kitaev_two_band_chern_oracle` | — |
| `square_toric_code_exact_topological_degeneracy` | `torus_ground_state_degeneracy` | `eligible` | `toric_code_stabilizer_rank` | `toric_code_logical_loop_oracle` | — |
| `triangular_nn_classical_120_reference` | `order`, `q_reciprocal` | `source_parse_only` | — | — | `status_or_candidate_only` |
| `aklt_spin1_chain_projector_ground_state` | `two_site_projector_eigenvalues`, `vbs_ground_energy` | `eligible` | `aklt_two_site_projector_ed` | `aklt_clebsch_gordan_oracle` | — |

### Migration-design candidates

| Benchmark | Complete selector fields | Disposition | Adapter ID | Oracle ID | Source-parse reason |
| --- | --- | --- | --- | --- | --- |
| `blume_capel_spin1_zero_temperature_level_crossing` | `square_lattice_d_over_j_crossing` | `eligible` | `blume_capel_level_crossing` | `blume_capel_configuration_oracle` | — |
| `checkerboard_heisenberg_afm_planar_pyrochlore_reference` | `zero_total_spin_per_crossed_plaquette` | `eligible` | `checkerboard_plaquette_enumeration` | `checkerboard_total_spin_oracle` | — |
| `cubic_ising_critical_temperature_reference` | `tc_over_j` | `source_parse_only` | — | — | `target_equivalent_input` |
| `fcc_j1_j2_heisenberg_type_order_reference` | `common_orders` | `source_parse_only` | — | — | `status_or_candidate_only` |
| `honeycomb_ising_ferromagnet_exact_tc` | `tc_over_j` | `eligible` | `honeycomb_ising_star_triangle_tc` | `honeycomb_ising_critical_polynomial_oracle` | — |
| `honeycomb_j1_j2_spiral_ring_reference` | `ring_condition` | `source_parse_only` | — | — | `source_only_symbolic_or_categorical_field` |
| `kagome_ising_antiferromagnet_residual_entropy_reference` | `macroscopic_ground_state_degeneracy` | `eligible` | `kagome_ising_af_entropy_quadrature` | `kagome_ising_af_transfer_count_oracle` | — |
| `kagome_ising_ferromagnet_exact_tc` | `tc_over_j` | `eligible` | `kagome_ising_star_triangle_tc` | `kagome_ising_critical_polynomial_oracle` | — |
| `majundar_ghosh_chain_exact_dimer_point` | `energy_per_site`, `degenerate_dimer_coverings` | `eligible` | `majumdar_ghosh_dimer_ed` | `majumdar_ghosh_projector_oracle` | — |
| `one_dimensional_classical_ising_no_finite_t_transition` | `finite_temperature_transition`, `tc_over_j` | `eligible` | `ising_chain_transfer_matrix` | `ising_chain_partition_analytic_oracle` | — |
| `pyrochlore_heisenberg_afm_coulomb_phase_reference` | `zero_total_spin_per_tetrahedron`, `pinch_points` | `eligible` | `pyrochlore_coulomb_fourier` | `pyrochlore_real_space_constraint_oracle` | — |
| `shastry_sutherland_exact_dimer_product` | `energy_per_dimer`, `energy_per_spin` | `eligible` | `shastry_sutherland_dimer_ed` | `shastry_sutherland_bond_oracle` | — |
| `simple_cubic_j1_j2_collinear_reference` | `neel_to_collinear_boundary_j2_over_j1` | `eligible` | `simple_cubic_j1_j2_fourier` | `simple_cubic_real_space_energy_oracle` | — |
| `single_ion_spin1_anisotropy_levels` | `levels`, `degeneracies` | `eligible` | `spin1_single_ion_dense_ed` | `spin1_m_quantum_number_oracle` | — |
| `square_fully_frustrated_ising_residual_entropy_reference` | `macroscopic_ground_state_degeneracy` | `eligible` | `fully_frustrated_ising_entropy_series` | `fully_frustrated_ising_transfer_oracle` | — |
| `takhtajan_babujian_spin1_critical_point` | `theta_radians`, `is_integrable` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `transverse_field_ising_chain_critical_point` | `critical_field_over_exchange` | `eligible` | `tfim_bdg_critical_point` | `tfim_duality_gap_oracle` | — |
| `transverse_field_ising_chain_gap` | `gap_formula`, `gap_formula_at_g_0_6` | `source_parse_only` | — | — | `mixed_selector_contains_source_only_field` |
| `triangular_ising_ferromagnet_exact_tc` | `tc_over_j` | `eligible` | `triangular_ising_star_triangle_tc` | `triangular_ising_critical_polynomial_oracle` | — |
| `xx_spin_half_chain_free_fermion_energy` | `energy_per_site` | `eligible` | `xx_chain_fermion_integral` | `xx_chain_dense_ed_extrapolation_oracle` | — |
| `xxz_spin_half_chain_phase_boundaries` | `ferromagnetic_boundary_delta`, `neel_boundary_delta`, `gapless_interval` | `source_parse_only` | — | — | `backend_unavailable_for_registered_limit` |

The implementation test obtains both candidate source sets independently and
requires their union to equal these tables and `ADAPTER_ELIGIBILITY`. It also
requires exactly 29 `eligible` and 13 `source_parse_only` dispositions, exact
selector-field equality, exact adapter/oracle IDs for eligible rows, and exact
reason equality for source-parse rows. Aggregate counts without identity-level
and field-level equality are insufficient.
