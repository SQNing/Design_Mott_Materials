# Isolated Literature Recalculation Adapters Design

**Status:** User-approved design, ready for independent specification review

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
| `input_schema` | Closed names, scalar/container types, bounds, and shape constraints |
| `parameter_sources` | Per-input provenance requirements |
| `output_schema` | Closed result field names, types, shapes, and units |
| `backend_kind` | One of `analytic`, `enumeration`, `dense_ed`, `glt_fourier`, or `iterative_numeric` |
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
tolerance, source operand, or report content. It also rejects additional fields,
aliases, positional payloads, object instances, callables, NaN, and infinity.

### Worker request

One worker request contains only:

- a schema version;
- an opaque run nonce;
- the adapter ID;
- one closed set of scientific inputs;
- one closed set of numerical controls; and
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

1. parameter values and independently validated provenance;
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
42 candidate benchmark IDs listed in the appendix. Each entry is either:

- `eligible`, with one adapter ID and one oracle ID; or
- `source_parse_only`, with one closed reason code.

Allowed `source_parse_only` reason codes are:

- `status_or_candidate_only`;
- `mixed_selector_contains_source_claim`;
- `target_equivalent_input`;
- `observable_identity_mismatch`;
- `no_independent_oracle`;
- `no_honest_convergence_evidence`; and
- `backend_unavailable_for_registered_limit`.

This catalog is migration metadata, not an authoritative verdict whitelist.
Task 8 still requires runtime evidence. Mutating a catalog label cannot produce
a strict result without a complete independence bundle.

Three known legacy shapes receive explicit treatment:

- `two_leg_ladder_strong_rung_exact_limit` currently returns a calculated rung
  gap together with `spin_ladder_material`. Because the material field is not
  established by the two-spin calculation, the existing mixed selector is
  `source_parse_only`.
- `triangular_nn_classical_120_reference` currently evaluates a supplied list
  containing the registered ordering vector. It is eligible only after being
  replaced by a genuine stationary-point or Brillouin-zone minimization that
  receives no candidate answer; otherwise it is `source_parse_only`.
- `cubic_ising_critical_temperature_reference` currently obtains `Tc/J` by
  inverting a supplied critical coupling. Because that coupling is an
  invertible restatement of the target rather than a model parameter, the
  existing route is `source_parse_only` unless replaced by an independent
  finite-size, series, or equivalent calculation of the registered limit.

Other candidates are not presumed eligible merely because their current helper
returns the registered shape. The parameterized eligibility tests apply the
same gate to all 42 entries.

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

The outer coordinator builds forbidden fingerprints from canonical registry
operands solely for rejection. Those fingerprints are never placed in the
capsule or request. Static scanning rejects:

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

The actual files opened at runtime, reconstructed from `strace`, must be a
subset of this pre-hashed manifest plus the capsule, input, and output paths.
No resource discovered only after execution is retrospectively accepted.

## Mandatory Event Ordering

The coordinator records an append-only sequence number for each stage. The
required order is:

1. validate the adapter definition and parameter-provenance schema;
2. construct and hash the scientific closure;
3. run all static scans;
4. construct and hash the runtime-resource closure;
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

The trusted setup process is launched with a clean environment and closed file
descriptors under `unshare -Urnm`. It makes mount propagation private, mounts a
new tmpfs root, creates only the declared mount points, performs bind mounts,
then remounts the root and every non-output mount read-only. The output bind is
the only writable filesystem visible to the worker.

The chroot has this logical layout:

| Path | Source and mode |
| --- | --- |
| `/runtime` | Pre-hashed interpreter, loader, standard library, declared packages, and native libraries; read-only |
| `/adapter` | One emitted scientific capsule and fixed worker; read-only, no device, no set-ID |
| `/input/request.json` | One regular request file bind-mounted read-only with no symlink components |
| `/output` | One newly created host run directory; writable, no device, no set-ID |

There is no project mount, parent/workspace mount, source-cache mount, evidence
mount, report mount, home directory, `/proc`, `/sys`, general `/dev`, host `/tmp`,
Git directory, or previous-run mount. If a backend requires temporary files,
its declared scratch subdirectory is inside `/output` and all scratch paths are
included in the evidence. A backend requiring an additional writable mount is
not strict-compatible under this design.

The setup process starts tracing only after mount construction. It then enters
the chroot, drops all capability sets, sets no-new-privileges, changes directory
to `/`, applies resource limits, and executes the exact pre-hashed interpreter
with isolated-mode flags. No setup descriptor other than standard streams is
inherited. Standard output and error are captured as bounded output artifacts;
the result itself is accepted only from `/output/result.json`.

All host output files use exclusive creation. After the worker exits, the
trusted setup process exclusively creates its namespace/mount attestation. If
the worker pre-creates a reserved attestation name, the run fails instead of
overwriting it.

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
- exact enumeration and dense ED: two random valid couplings or fields at each
  of two declared small system sizes, plus one invalid shape or size;
- GLT/Fourier adapters: three random valid couplings and two random momenta or
  configurations per coupling, including a real-space/Fourier identity check;
- iterative numerical adapters: one random valid model point and at least three
  progressively stronger numerical controls, plus one invalid control.

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

The oracle is bundled and hashed separately. Its scientific source nodes and
transitive scientific dependencies must have an empty intersection with the
adapter's scientific closure. The only shared code permitted is fixed transport,
canonical JSON validation, and isolation infrastructure, which is recorded in a
separate infrastructure closure rather than either scientific closure.

The oracle receives the same answer-free model inputs. It does not receive a
source operand, registry operand, comparator tolerance, or verdict. When an
invariant necessarily evaluates an adapter result, the outer coordinator places
that result in a separate closed oracle request after adapter completion; the
oracle still cannot influence the adapter run. Oracle output is compared by the
coordinator under the adapter's declared numerical contract.

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
oracle code, closure overlap, result mismatch, excessive residual, or malformed
oracle evidence makes the adapter outcome non-strict.

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

- `strict_recomputation_succeeded`;
- `strict_recomputation_unavailable`;
- `adapter_ineligible`;
- `input_rejected`;
- `dependency_rejected`;
- `isolation_failed`;
- `execution_failed`;
- `convergence_failed`; and
- `oracle_failed`.

Only `strict_recomputation_succeeded` carries a successful independence bundle,
and Task 8 must still compare it with independently parsed literature and
registry operands. Exceptions, unavailable tools, malformed output, nonzero
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
- require exactly one closed eligibility decision per candidate;
- prove status, candidate-only, mixed-selector, and target-equivalent examples
  cannot be labeled eligible without a replacement calculation;
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
- prove an oracle scientific node cannot enter the adapter closure.

### Ordering and counterfactual tests

- prove every code/runtime hash event precedes random-byte acquisition;
- prove a fixed disclosed seed reproduces points while a fresh seed changes
  them;
- prove each backend family receives its required minimum point set;
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
- prove missing or malformed attestation invalidates the run.

### Adversarial information-flow tests

- attempt reads of registry, canonical specifications, records, source cache,
  reports, protected WIP, parent files, and previous outputs;
- attempt environment-secret access;
- attempt network socket and connection use;
- attempt symlink, relative-path, directory-FD, and prefix-confusion escapes;
- attempt subprocess creation and undeclared native-library loading;
- require rejection for both successful and failed forbidden syscalls;
- mutate, truncate, omit, or make a trace unparsable and require failure.

### Scientific and evidence-bundle tests

- exercise at least one real analytic, dense-ED or exact-enumeration,
  GLT/Fourier, and iterative-numeric adapter shape;
- require typed identity, units, uncertainty, raw convergence, and diagnostics;
- require independent oracles and empty scientific-closure intersection;
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
2. the eligibility catalog covers exactly the 42 appendix candidates with no
   missing, duplicate, or extra ID;
3. every eligible candidate has a real adapter, answer-free input contract,
   counterfactual domain, convergence contract, and separate oracle;
4. every ineligible candidate has one closed source-parse-only reason and
   cannot produce a strict adapter result;
5. full positive capability preflight succeeds on the designated host;
6. all static leakage, namespace, filesystem, environment, network, process,
   trace, counterfactual, and oracle adversarial tests pass;
7. every eligible production adapter produces a complete independence bundle;
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

## Appendix: Exact Recalculation Candidate Set

The eligibility catalog covers exactly these 42 benchmark IDs. The first group
is registered by the legacy runtime collector; the second group comes from the
approved 155-record migration design. Group membership has no bearing on final
eligibility.

### Legacy collector candidates

1. `xxx_spin_half_chain_bethe_ground_state`
2. `one_dimensional_classical_ising_correlation_length`
3. `two_dimensional_square_ising_onsager_tc`
4. `two_dimensional_square_ising_spontaneous_magnetization`
5. `square_potts_exact_critical_point`
6. `triangular_ising_antiferromagnet_residual_entropy`
7. `xy_spin_half_chain_anisotropic_critical_line`
8. `diamond_j1_j2_spiral_surface_reference`
9. `spin_ice_tetrahedron_nn_ice_rule`
10. `square_j1_j3_classical_lifshitz_reference`
11. `two_leg_ladder_strong_rung_exact_limit`
12. `square_ashkin_teller_exact_critical_line`
13. `pyrochlore_dipolar_spin_ice_pauling_entropy`
14. `two_dimensional_xy_bkt_universal_jump`
15. `uimin_lai_sutherland_spin1_su3_point`
16. `bilinear_biquadratic_spin1_chain_aklt_angle`
17. `square_compass_model_directional_exchange_degeneracy`
18. `kitaev_honeycomb_abelian_nonabelian_field_gap_reference`
19. `square_toric_code_exact_topological_degeneracy`
20. `triangular_nn_classical_120_reference`
21. `aklt_spin1_chain_projector_ground_state`

### Migration-design candidates

1. `blume_capel_spin1_zero_temperature_level_crossing`
2. `checkerboard_heisenberg_afm_planar_pyrochlore_reference`
3. `cubic_ising_critical_temperature_reference`
4. `fcc_j1_j2_heisenberg_type_order_reference`
5. `honeycomb_ising_ferromagnet_exact_tc`
6. `honeycomb_j1_j2_spiral_ring_reference`
7. `kagome_ising_antiferromagnet_residual_entropy_reference`
8. `kagome_ising_ferromagnet_exact_tc`
9. `majundar_ghosh_chain_exact_dimer_point`
10. `one_dimensional_classical_ising_no_finite_t_transition`
11. `pyrochlore_heisenberg_afm_coulomb_phase_reference`
12. `shastry_sutherland_exact_dimer_product`
13. `simple_cubic_j1_j2_collinear_reference`
14. `single_ion_spin1_anisotropy_levels`
15. `square_fully_frustrated_ising_residual_entropy_reference`
16. `takhtajan_babujian_spin1_critical_point`
17. `transverse_field_ising_chain_critical_point`
18. `transverse_field_ising_chain_gap`
19. `triangular_ising_ferromagnet_exact_tc`
20. `xx_spin_half_chain_free_fermion_energy`
21. `xxz_spin_half_chain_phase_boundaries`

The implementation test obtains both source sets independently and requires
their union to equal this appendix and `ADAPTER_ELIGIBILITY`. An aggregate count
without identity-level equality is insufficient.
