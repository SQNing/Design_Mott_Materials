# Canonical Hamiltonian Symmetry Gate Completion Audit

## Audit scope

This audit maps Sections 2–13 of
`docs/superpowers/specs/2026-09-03-canonical-hamiltonian-symmetry-gate-design.md`
to implementation and remote verification evidence. The implementation baseline
is commit `12e2726`; the audited feature implementation is commit `d26f7e0` plus
this documentation-only completion record.

All executable tests were submitted through Slurm after `ssh login002`. No test
command was run in the local working environment.

## Section 2: reuse rather than parallel implementations

Status: satisfied.

- Representative bond data continue to come from the existing bond-orbit and
  lattice-structure records. `common.canonical_hamiltonian` expands declared
  representatives and does not infer representative intent from term count.
- `classical.build_spin_only_solver_payload` delegates its Cartesian/axial
  rotation to `common.hamiltonian_symmetry_action`; the compatibility wrapper is
  covered by `test_legacy_rotation_wrapper_uses_shared_axial_rotation`.
- `common.model_analysis` calls
  `classical.lt_fourier_exchange.fourier_exchange_matrix` for both legacy
  isotropic and canonical anisotropic paths. The call count and stale-stamp
  behavior are covered by `tests/test_hamiltonian_solver_routing.py`.
- Validated physical-spin models call the existing
  `classical.classical_solver_driver.run_classical_solver`. Validated retained
  local pair models are lowered back into the established CPN payload contract
  before the existing CPN/GSWT workflow is entered.

## Sections 3–4: architecture, canonical IR, and arbitrary arity

Status: satisfied for the initial gate delivery.

- `common.canonical_hamiltonian.compile_canonical_hamiltonian` produces a
  deterministic `canonical-hamiltonian/v1` model and preserves arbitrary-arity
  term records.
- `canonical_term_key`, `coefficient_map`, and `canonical_model_hash` provide the
  deterministic coefficient identity and content binding.
- `common.operator_family_symmetry` contains the generic tensor-leg action and
  registered adapters for physical spin, quadratic, bilinear, pair-matrix,
  biquadratic, scalar-chirality, and cyclic-ring families.
- Unknown or opaque actions fail with
  `symmetry-projection-unsupported-term`; they are not dropped.
- Evidence: `tests/test_canonical_hamiltonian.py`,
  `tests/test_operator_family_symmetry.py`, and
  `tests/test_hamiltonian_symmetry_completion.py`.

## Section 5: space-group action

Status: satisfied.

- `common.hamiltonian_symmetry_action.cartesian_rotation` performs the
  fractional-to-Cartesian conversion with metric validation.
- `axial_spin_rotation` applies `det(Q) Q` for physical spin.
- `map_cluster` maps site/cell pairs, including nonzero cell offsets.
- `transform_term` applies one local action to every tensor leg, uses
  `F_target^-1 D_g F_source` for local frames, and then applies the declared
  family canonicalization/permutation.
- Non-spin local spaces read explicit matrices from
  `local_hilbert.operator_bases[*].symmetry_actions`; no dimension-based axial
  guess is made.
- Representative pair matrices now use those declared actions as well as
  explicit pair terms (`73a1711`). Missing actions still fail with
  `symmetry-representation-unavailable`.
- Evidence includes proper/improper rotations, inversion, nonsymmorphic-like
  offsets, local frames, anisotropic exchange, non-spin tensor actions, DM
  projection, biquadratic orbits, chirality parity, and ring reversal.

## Section 6: representative versus explicit input semantics

Status: satisfied.

- `attach_to.orientation=representative` and its explicit orbit reference expand
  through the declared orbit.
- A plain explicit cluster list is treated as the complete Hamiltonian; absent
  partners are zero and therefore fail strict symmetry validation.
- `tests/test_hamiltonian_symmetry_pipeline.py` compares representative,
  complete-explicit, and stamped-adapter paths, including elementwise Fourier
  equality at three q points.

## Sections 7–8: validation and opt-in group-average repair

Status: satisfied.

- `common.hamiltonian_symmetry_gate.validate_hamiltonian_symmetry` compares the
  union of original and transformed canonical keys with the declared absolute
  and relative tolerances.
- The report records failed operations, missing partners, forbidden terms,
  maximum residuals, and a worst canonical key.
- Passing operations are reported as a Hamiltonian subgroup only after the
  discrete operation table passes identity, closure, multiplication, and inverse
  checks; otherwise they remain candidate operations.
- Prechecks reject unresolved structure/identity, missing representations, and
  non-Hermitian onsite, pair, ring, scalar, and self-site bilinear records.
- `project_hamiltonian_symmetry` averages the complete coefficient map over the
  finite structural group, cleans only numerical residuals, and revalidates.
- Tests cover missing-partner addition, inconsistent-partner averaging,
  forbidden DM-component removal, invariance, idempotence, Hermiticity, and
  input immutability/order independence.

## Section 9: public behavior and failure semantics

Status: satisfied for canonical user-facing model routes.

- `symmetry_repair` defaults to the boolean `false`; non-booleans are rejected.
- `--symmetry-repair` is forwarded by the CPN payload, POSCAR/HR, and text CLIs.
- Strict failure returns
  `hamiltonian-symmetry-validation-failed`,
  `stopping_condition=pre-solver-symmetry-gate`, and
  `solver_execution.started=false` before the solver core is called.
- Material repair emits `hamiltonian-symmetry-repaired`; an already-symmetric
  projection is informational and does not emit that warning.
- No diagnostic subgroup is substituted for the target structural group.
- Low-level numerical functions and already-landed legacy payload APIs remain
  callable for backward compatibility, as required by Section 3.4. The enforced
  public gate begins once a complete `lattice-term-contract/v1` structure,
  symmetry table, terms, and local representations have been declared. A legacy
  payload that cannot supply those facts is not silently assigned a symmetry
  representation.

## Section 10: reports, hashes, stamps, and provenance

Status: satisfied.

- Gate results preserve separate input-model and solver-model hashes and
  canonical references.
- Provenance records the target group, operation count, algorithm version,
  tolerances, repair request, and downstream model reference.
- Repair reports classify added, modified, zeroed, and unchanged coefficients
  and include maximum/L2 changes plus before/after validation.
- `require_current_symmetry_stamp` rejects any physical model mutation.
- Physical-spin and retained-local adapters propagate the same validated hash;
  the latter is implemented by
  `_validated_canonical_retained_payload` (`d87586f`).

## Section 11: solver capability boundaries

Status: satisfied for the initial adapters.

- `common.solver_capability_registry` checks every canonical term family and body
  order before routing.
- Unsupported complete term sets return `solver-capability-mismatch` with term
  references/families; no higher-body term is discarded to make a bilinear
  solver run.
- Physical-spin bilinear models route to the existing classical/Fourier stack.
- Pair-matrix models with explicit symmetry representations route through the
  validated CPN adapter; a repaired pair model, not the input coefficients, is
  what the CPN core receives.
- GLT certification remains explicitly a certificate for the declared relaxed
  objective, not a fixed-spin-length certificate.

## Section 12: test evidence

### Red/green and focused jobs

The retained logs are under
`/data/work/zhli/job-logs/canonical-hamiltonian-symmetry/`.

- `479114`: Task-5 red, six expected failures.
- `479131`: Task-5 green, 55 passed, `COMPLETED/0:0`.
- `479153` / `479163`: Task-6 red/green; green 23 passed.
- `479166` / `479175`: Task-7 red/green; green 31 passed.
- `479188` / `479192`: completion red/green; green 34 passed.
- `479194` / `479196`: provenance red/green; green 45 passed.
- `479198` / `479199`: public physical-spin route red/green; green 17 passed.
- `479203`: first CLI smoke failed before execution because `SLURM_TMPDIR` was
  absent; this was an environment-script failure, not a product-test result.
- `479206`: corrected strict/repair CLI smoke, `COMPLETED/0:0`; it observed the
  strict reason, repair warning, backend invocation, and solver-model hash.
- `479209`: documentation/path suite, 19 passed, `COMPLETED/0:0`.
- `479211`: earlier focused feature suite, 101 passed, `COMPLETED/0:0`.
- `479233` / `479237`: declared pseudospin representative action red/green;
  green 29 passed, `COMPLETED/0:0`.
- `479244` / `479248`: canonical retained-local routing red/green; green 22
  passed, `COMPLETED/0:0`.
- `479265`: repaired retained-local CPN routing, 8 passed, `COMPLETED/0:0`.
- `479267`: final focused suite at `d26f7e0`, 92 passed with 30 warnings,
  `COMPLETED/0:0`.

### Full-repository comparison

The original full-suite jobs `479033`, `479180`, `479212`, `479241`, and
`479249` were superseded because their source worktree changed after submission
or their fixed feature snapshot preceded the final fixes. They were cancelled
rather than cited as final evidence.

Authoritative comparison jobs use separate detached worktrees:

- baseline `12e2726`:
  `/data/work/zhli/soft/Design_Mott_Materials/.worktrees/symmetry-baseline-12e2726`;
- feature `d26f7e0`:
  `/data/work/zhli/soft/Design_Mott_Materials/.worktrees/symmetry-final-d26f7e0`.

The monolithic baseline job `479242` finished with Slurm state `FAILED`, exit
code `1:0`, and the complete pytest summary
`148 failed, 6956 passed, 96 skipped, 816 warnings` in 2:48:27. The state is
`FAILED` because pytest found the pre-existing failures, not because Slurm or the
test harness failed. The monolithic final job `479266` reached the three-hour
limit at about the same slow evidence-adapter region and ended `TIMEOUT`; it is
not used alone as completion evidence.

To obtain complete, terminal coverage without raising the scheduler time limit,
the suite was partitioned by whole test files and, for the one very slow file,
by 8 mutually exclusive sets of test-function names. The partitions cover all
7,256 tests collected at `d26f7e0` exactly once:

- `test_literature_evidence_adapters.py`: jobs `479540`–`479556`, eight paired
  baseline/feature partitions. Totals on each side were 83 failed and 2,610
  passed. Each pair had identical failure-list SHA-256; the eight hashes were
  `c7e52d2b...c9c938e`, `b3080591...e6291d7`,
  `e7e4a745...e1e6f93`, `006e6aaa...f80a824`, the empty-list hash
  `e3b0c442...b855`, `cfe3007d...7d82375`,
  `18bd2765...a98148d1e`, and `cba7f2f2...40173a8`.
- `test_literature_evidence_sources.py`: jobs `479537`/`479536`; both had
  61 failed and 1,778 passed, with identical failure-list hash
  `e77fe690...de99c5`.
- All tests excluding those first two files: jobs `479515`/`479516`; both had
  the same four failures. The failure-list hash was identical:
  `0eaee385...8ba375`. Baseline/feature pass counts were 2,568/2,624, with
  96 skipped on each side.
- After additionally excluding the two files containing those four known
  failures, jobs `479530`/`479531` were fully green: baseline
  `2377 passed, 96 skipped`; feature `2433 passed, 96 skipped`, both
  `COMPLETED/0:0`.

The complete partition reconstruction is therefore:

| Snapshot | Failed | Passed | Skipped | Collected |
|---|---:|---:|---:|---:|
| baseline `12e2726` | 148 | 6,956 | 96 | 7,200 |
| feature `d26f7e0` | 148 | 7,012 | 96 | 7,256 |

The 148 failure node IDs are identical between snapshots. The feature adds 56
passing tests and no failing test. The repository as a whole is **not green**;
its pre-existing failures are reported separately and are not attributed to the
Hamiltonian symmetry implementation.

## Section 13: initial delivery and roadmap boundary

Status: initial symmetry-gate delivery satisfied. The final full-suite
non-regression comparison above proves that it adds no failure relative to the
fixed baseline, while preserving the explicit fact that the repository baseline
itself is not fully green.

Delivered now:

- common canonical symmetry action for spin and explicitly represented local
  operator spaces;
- strict-by-default pre-solver validation;
- explicit finite-group-average repair and postcheck;
- onsite, bilinear, pair-matrix, and generic arbitrary-arity gate support;
- tested biquadratic, scalar-chirality, and cyclic-ring adapters;
- existing 3N-sub Fourier reuse;
- complete-term solver capability rejection;
- hashes, stamps, reports, warnings, and provenance.

Not claimed by this delivery, and deliberately left for later dependency-ordered
projects:

1. fixed-spin-length recovery and unified real-space classical optimization;
2. unified LSWT/GSWT routing beyond the existing CPN workflow adapters;
3. long-range dipolar Ewald summation;
4. three-dimensional classical Monte Carlo and finite-size scaling;
5. sparse Lanczos, QMC, and tensor-network backends.
