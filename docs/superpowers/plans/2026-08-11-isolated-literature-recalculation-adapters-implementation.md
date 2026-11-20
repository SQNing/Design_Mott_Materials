# Isolated Literature Recalculation Adapters Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the fail-closed Task 7 recalculation service, including the exact 42-candidate eligibility catalog, 29 answer-free scientific adapters, 29 independently implemented oracles, Linux namespace isolation, complete runtime tracing, and independently checkable evidence bundles.

**Architecture:** Keep scientific code, oracle code, and trusted isolation infrastructure in three additive modules with no edits to the legacy collector. The coordinator freezes AST-derived scientific closures and a file-level runtime snapshot before generating unpredictable inputs, then runs every adapter and oracle point in a fresh `unshare -Urnm` namespace through an external tracer and hardened output reader. Task 7 validates structural authority, isolation, convergence, and oracle evidence but never loads literature targets and never issues a strict literature verdict; Task 8 remains the only production authority and comparator.

**Tech Stack:** Python 3 standard library (`ast`, `dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `resource`, `secrets`, `stat`, `subprocess`), NumPy/SciPy only when declared and snapshotted, Linux `unshare`/`mount`/`chroot`/`setpriv`/`strace`, pytest, flake8, Git.

---

## Scope and non-negotiable boundaries

This plan implements the user-approved design at
`docs/superpowers/specs/2026-08-11-isolated-literature-recalculation-adapters-design.md`.
The design is normative whenever this plan is silent. In particular:

- Task 7 returns `isolated_recomputation_succeeded`, never
  `strict_literature_match`.
- Task 7 never imports or reads the literature registry, evidence inventory,
  source cache, canonical observable files, reports, Git metadata, or prior
  outputs.
- The worker request never contains a benchmark name, source identity,
  expected/target/registry operand, comparator, tolerance, oracle answer, or
  verdict.
- Every adapter and every oracle gets a separate capsule, process, namespace,
  chroot, trace, attestation, and hardened output ingestion.
- There is no non-isolated fallback. A missing capability is a structured
  `strict_recomputation_unavailable` result.
- The 42 dispositions, 29 adapter/oracle pairs, 13 source-parse reasons, and
  7/4/18 size-policy split are exact sets, not quotas.
- Existing direct-call runtime evidence remains non-authoritative until Task 8.
- Do not edit the two legacy scientific modules merely to make extraction
  convenient. New answer-free entry points live in the new adapter/oracle
  modules.

The following pre-existing user-owned WIP must remain unstaged and byte-identical:

- `translation-invariant-spin-model-simplifier/reports/generate_literature_reproduction_audit_pdf.py`
- `translation-invariant-spin-model-simplifier/tests/test_literature_reproduction_audit_pdf.py`
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.csv`
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit.md`
- `translation-invariant-spin-model-simplifier/reports/literature_reproduction_audit_43_of_155.pdf`
- `translation-invariant-spin-model-simplifier/reports/remaining_strict_reproduction_gaps.md`

Do not delete, truncate, move, clean, or overwrite any existing file. All Task 7
production/test paths are additive. Run directories and retained diagnostic
artifacts use exclusive creation and are not automatically cleaned.

## Locked file map

Create exactly these production and test files:

- `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
  owns recursive immutable JSON values, closed adapter/domain/convergence
  contracts, the exact eligibility catalog, all 29 answer-free adapter entry
  points, and adapter definitions.
- `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
  owns all 29 independent oracle entry points and oracle definitions. It may
  share only fixed transport/validation infrastructure, never scientific
  functions, constants, formulas, or tables with the adapter module.
- `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
  owns authority-context validation, AST closure building, static scans,
  a separately classified and hashed transport/isolation infrastructure
  closure,
  fingerprint rejection, runtime-resource discovery/snapshot/revalidation,
  counterfactual generation, capability preflight, capsule/worker emission,
  namespace supervision, tracing, hardened output ingestion, convergence/oracle
  adjudication, and evidence/failure objects.
- `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`
  owns all Task 7 unit, integration, scientific, adversarial, and acceptance
  tests, including a test-only authority producer and synthetic attack modules.

Do not modify the following in Task 7:

- `scripts/validation/literature_runtime_evidence.py`
- `scripts/validation/literature_spin_model_benchmarks.py`
- any registry, evidence, source-cache, report, or PDF file
- any existing test module

If implementation reveals that one of those edits is unavoidable, stop and
amend the approved design and this plan before touching it.

## Command conventions and commit gate

Unless a step says otherwise, run Git commands from the worktree root:

```text
/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit
```

Run Python commands from:

```text
/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier
```

Every pytest invocation must use `PYTHONDONTWRITEBYTECODE=1` and
`-p no:cacheprovider`. Never create `.pytest_cache` or repository `__pycache__`
directories. For compilation, create a fresh retained external directory with
`mktemp -d /tmp/task7-pycache.XXXXXXXX` and set `PYTHONPYCACHEPREFIX` to the
printed path.

Before and after every commit and every external review, run this exact
protected-baseline command from the worktree root:

```bash
sed -n '174,306p' docs/superpowers/plans/2026-07-15-fail-closed-literature-reproduction-evidence-implementation.md | sed '/^```/d' | bash
```

Expected output:

```json
{"allowed_targets": [], "baseline_entries_verified": 471, "baseline_roots_verified": 143, "protected_files_verified": 6}
```

The reviewed worktree already contains eleven ignored, user-owned
`__pycache__` directories with 178 total directory/file entries. They cannot be
deleted or treated as a Task 7 failure. Before and after every implementation
commit and every external review, run this exact read-only cache-preservation
command from the worktree root; it rejects any new, missing, or modified cache
entry:

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
import hashlib
import json
import os
import stat
from pathlib import Path

root = Path("translation-invariant-spin-model-simplifier")
cache_dirs = sorted(
    path
    for path in root.rglob("*")
    if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}
)
entries = []
for base in cache_dirs:
    for path in [base, *sorted(base.rglob("*"))]:
        status = path.lstat()
        relative = path.as_posix()
        if stat.S_ISREG(status.st_mode):
            payload = path.read_bytes()
            row = [
                relative,
                "regular",
                status.st_mode & 0o7777,
                len(payload),
                hashlib.sha256(payload).hexdigest(),
            ]
        elif stat.S_ISDIR(status.st_mode):
            row = [relative, "directory", status.st_mode & 0o7777, None, None]
        elif stat.S_ISLNK(status.st_mode):
            row = [
                relative,
                "symlink",
                status.st_mode & 0o7777,
                None,
                os.readlink(path),
            ]
        else:
            row = [relative, "other", status.st_mode & 0o7777, None, None]
        entries.append(row)
manifest = json.dumps(
    entries, sort_keys=True, separators=(",", ":")
).encode("utf-8")
actual = {
    "cache_dirs": len(cache_dirs),
    "entries": len(entries),
    "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
}
expected = {
    "cache_dirs": 11,
    "entries": 178,
    "manifest_sha256": (
        "f66b98ea9404df076be51bd2e219f8fbf7a82e419c4fc4f27c32e6177789f620"
    ),
}
if actual != expected:
    raise SystemExit(f"repository cache baseline mismatch: {actual}")
print(json.dumps(actual, sort_keys=True))
PY
```

Expected output:

```json
{"cache_dirs": 11, "entries": 178, "manifest_sha256": "f66b98ea9404df076be51bd2e219f8fbf7a82e419c4fc4f27c32e6177789f620"}
```

Before every commit, also run:

```bash
git diff --check
git status --short
git diff --cached --name-status
```

The cached path list must contain only the exact files named by that task. Stage
with exact paths; never use `git add .`, `git add -A`, or a broad force-add.

Immediately before Task 1, require the reviewed plan to be the tip commit and
record that commit as the implementation boundary:

```bash
task7_implementation_base="$(
  git log -1 --format=%H -- \
    docs/superpowers/plans/2026-08-11-isolated-literature-recalculation-adapters-implementation.md
)"
test -n "$task7_implementation_base"
test "$(git rev-parse HEAD)" = "$task7_implementation_base"
git show --no-patch --oneline "$task7_implementation_base"
```

Do not hard-code an earlier plan commit: review amendments are part of the
reviewed documentation range, not implementation. The final scope gate
recomputes the last commit touching this plan and requires that no implementation
commit modified it.

## Public API and data-flow map

The implementation must expose these stable entry points:

```python
# literature_evidence_adapters.py
ADAPTER_ELIGIBILITY: Mapping[str, EligibilityDecision]
ADAPTER_DEFINITIONS: Mapping[str, AdapterDefinition]
get_adapter_definition(adapter_id: str) -> AdapterDefinition
validate_scientific_inputs(definition, values) -> FrozenJsonObject
validate_numerical_controls(definition, values) -> FrozenJsonObject
validate_local_observable_result(definition, value) -> FrozenJsonObject

# literature_evidence_adapter_oracles.py
ORACLE_DEFINITIONS: Mapping[str, OracleDefinition]
get_oracle_definition(oracle_id: str) -> OracleDefinition

# literature_evidence_isolation.py
validate_authority_context(value, *, allow_test_producer=False) -> AdapterAuthorityContext
build_scientific_closure(entry_symbol, *, role, source_roots) -> ScientificClosure
build_scientific_policy_commitment(definition, closure, *, role) -> ScientificPolicyCommitment
build_infrastructure_closure(*, source_roots) -> InfrastructureClosure
scan_scientific_closure(closure, *, forbidden_fingerprints) -> StaticScanReport
build_runtime_snapshot(requirements, *, run_directory, event_recorder) -> RuntimeSnapshot
run_capability_preflight(*, scratch_parent) -> CapabilityPreflightReport
derive_counterfactual_points(definition, seed) -> tuple[CounterfactualPoint, ...]
evaluate_strace(trace_bytes, mount_manifest) -> TracePolicyReport
run_isolated_recomputation(adapter_id, authority_context, *, run_parent) -> AdapterRunOutcome
```

The only successful flow is:

```text
validated AdapterAuthorityContext
  -> adapter definition + exact eligibility decision
  -> canonical adapter/oracle definitions + scientific execution closures
  -> adapter/oracle scientific-policy commitments + complete infrastructure closure
  -> disjoint dependency partition, independent static scans, and hashes
  -> immutable runtime snapshot
  -> fresh capability preflight and infrastructure-command hashes
  -> freeze every code/scanner/resource/preflight hash
  -> acquire 32 random bytes and derive points
  -> fresh isolated adapter process per point
  -> fresh isolated oracle process per point
  -> trace/output/isolation validation
  -> outer convergence + oracle decisions
  -> seed disclosure + closed AdapterExecutionEvidence
  -> isolated_recomputation_succeeded
```

Any failed arrow returns one closed failure object and cannot retry through an
unisolated or weakened path.

### Task 1: Add immutable closed contracts and canonical JSON

**Files:**

- Create: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Create: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED tests for recursive JSON closure and exact keys**

Add tests named:

```python
def test_freeze_json_rejects_non_string_keys_unknown_objects_and_nonfinite_numbers(): ...
def test_freeze_json_recursively_prevents_mutation(): ...
def test_canonical_json_is_sorted_compact_utf8_and_rejects_nan(): ...
def test_adapter_definition_rejects_missing_unknown_and_mutable_fields(): ...
def test_schema_rejects_bool_where_numeric_is_required(): ...
```

Use nested dictionaries/lists and prove that mutation of caller-owned inputs
after construction cannot change the frozen value or its SHA-256.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q
```

Expected: collection fails because `validation.literature_evidence_adapters`
does not exist.

- [ ] **Step 3: Implement the canonical JSON primitives**

Implement `AdapterContractError`, `FrozenJsonObject`, `freeze_json`,
`thaw_json`, `canonical_json_bytes`, `canonical_sha256`,
`require_exact_keys`, `require_identifier`, and finite-number/type validators.
`freeze_json` must recursively convert mappings to an immutable mapping wrapper
and lists to tuples; it must reject bytes, sets, custom objects, callables,
non-string mapping keys, NaN, infinity, and booleans in numeric slots.

Use explicit schema objects rather than callable validators:

```python
@dataclass(frozen=True)
class ValueSchema:
    kind: str                 # boolean|integer|number|string|list|object
    required: bool
    lower: float | None
    upper: float | None
    item_schema: "ValueSchema | None"
    properties: tuple[tuple[str, "ValueSchema"], ...]
    units: str
```

- [ ] **Step 4: Implement the closed definition records**

Add frozen dataclasses for `ParameterSource`, `CounterfactualDomain`,
`ConvergenceContract`, `ProblemSizePolicy`, `RuntimeRequirements`,
`ResourceLimits`, `AdapterDefinition`, and `EligibilityDecision`. Validate the
exact `AdapterDefinition` fields from the design; reject unknown backend kinds,
size policies, provenance kinds, convergence kinds, and source-parse reasons.
Do not add a target, expected result, registry selector operand, comparison,
tolerance, verdict, or source field.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all Task 1 tests pass.

- [ ] **Step 6: Commit Task 1**

Run the protected baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add closed literature adapter contracts"
```

Run the protected baseline again.

### Task 2: Lock the exact 42-candidate eligibility catalog

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Add the independent expected table to tests**

Define `EXPECTED_ELIGIBILITY` in the test module, transcribed independently
from the design appendix, as tuples of:

```python
(benchmark_name, selector_fields, disposition, adapter_id, oracle_id, reason)
```

Do not generate this fixture from production constants. Add tests named:

```python
def test_eligibility_catalog_matches_all_42_normative_rows_field_for_field(): ...
def test_eligibility_catalog_has_exact_29_eligible_and_13_source_parse_rows(): ...
def test_source_parse_rows_cannot_resolve_an_adapter(): ...
def test_candidate_sources_union_matches_normative_catalog(): ...
```

The last test must independently extract the 21 current collector candidates
from the legacy `specs` literal with AST and combine them with the 21 migration
candidate IDs in the approved design appendix. It may read source text in the
outer test process; production Task 7 code must not.

- [ ] **Step 2: Verify RED**

Run:

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'eligibility or candidate_sources'
```

Expected: failures because `ADAPTER_ELIGIBILITY` is absent.

- [ ] **Step 3: Implement the exact production catalog**

Add every appendix row verbatim. Eligible rows carry their exact selector,
adapter ID, and oracle ID; source-only rows carry their exact selector and one
of these exact reasons:

```python
SOURCE_PARSE_ONLY_REASONS = frozenset({
    "status_or_candidate_only",
    "mixed_selector_contains_source_only_field",
    "source_only_symbolic_or_categorical_field",
    "target_equivalent_input",
    "observable_identity_mismatch",
    "no_independent_oracle",
    "no_honest_convergence_evidence",
    "backend_unavailable_for_registered_limit",
})
```

Construct the mapping through a duplicate-detecting builder and expose it as an
immutable mapping. A typo, duplicate, missing, or additional benchmark must
fail module construction or validation.

- [ ] **Step 4: Add explicit regression assertions for the three ambiguous rows**

Assert that the ladder selector is exactly
`("energy_per_rung", "gap_to_triplet")`; triangular 120-degree order is
`source_parse_only/status_or_candidate_only`; and cubic Ising Tc is
`source_parse_only/target_equivalent_input`.

- [ ] **Step 5: Verify GREEN and commit**

Run the focused command, then the whole Task 7 test module. Run the protected
baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: lock literature recalculation eligibility"
```

Run the protected baseline again.

### Task 3: Define all 29 adapter metadata contracts and size policies

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED exact-set definition tests**

Add independent test sets for:

```python
FIXED_LOCAL = {
    "spin_ice_tetrahedron_enumeration", "spin_ladder_rung_dense_ed",
    "uls_two_site_su3_matrix", "aklt_two_site_projector_ed",
    "blume_capel_level_crossing", "checkerboard_plaquette_enumeration",
    "spin1_single_ion_dense_ed",
}
SCALABLE = {
    "compass_line_symmetry_matrix", "toric_code_stabilizer_rank",
    "majumdar_ghosh_dimer_ed", "shastry_sutherland_dimer_ed",
}
EXPECTED_SIZE_DATA = {
    "spin_ice_tetrahedron_enumeration": {"spin_count": 4, "tetrahedra": 1},
    "spin_ladder_rung_dense_ed": {"spin_count": 2, "rungs": 1},
    "uls_two_site_su3_matrix": {"spin_count": 2, "spin_quantum_number": 1},
    "aklt_two_site_projector_ed": {"spin_count": 2, "spin_quantum_number": 1},
    "blume_capel_level_crossing": {
        "unit_cell_sites": 1, "coordination_number": 4,
    },
    "checkerboard_plaquette_enumeration": {
        "spin_count": 4, "crossed_plaquettes": 1,
    },
    "spin1_single_ion_dense_ed": {"spin_count": 1, "spin_quantum_number": 1},
    "compass_line_symmetry_matrix": {
        "lattice_shapes": ((2, 2), (2, 3)), "boundary_conditions": "open",
    },
    "toric_code_stabilizer_rank": {
        "lattice_shapes": ((2, 2), (3, 3)), "boundary_conditions": "periodic",
    },
    "majumdar_ghosh_dimer_ed": {
        "periodic_chain_lengths": (8, 10), "boundary_conditions": "periodic",
    },
    "shastry_sutherland_dimer_ed": {
        "orthogonal_dimer_counts": (2, 4),
        "spin_counts": (4, 8),
        "boundary_conditions": "open_linked_cells",
    },
}
```

The complement among the 29 must be exactly 18 `not_applicable` definitions.
The independent test fixture must compare `EXPECTED_SIZE_DATA` field for field
with production metadata; it may not derive expected sizes from the production
mapping. Test one-to-one catalog/definition/oracle-ID linkage, exact output selector
fields, a nonempty complete `observable_identity`, one provenance record per
scientific input, closed controls, one counterfactual domain, one convergence
contract, runtime requirements, and bounded resource limits.

- [ ] **Step 2: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'definition or size_policy or provenance'
```

Expected: failures because `ADAPTER_DEFINITIONS` is absent.

- [ ] **Step 3: Add a duplicate-detecting definition builder**

Each entry symbol must be a fully qualified source symbol in the new adapter
module, e.g.:

```python
entry_symbol=(
    "validation.literature_evidence_adapters:adapter_xxx_bethe_energy"
)
```

`observable_identity` must contain exactly `subject`, `system_or_material`,
`hamiltonian`, `parameter_regime`, `size_or_limit`, `observable_definition`,
`units`, and `conditions`. It is authored locally and is never populated from a
registry value at runtime.

- [ ] **Step 4: Populate complete metadata for every eligible adapter**

Use the normative backend/method table from the design. Bind every scientific
input to exactly one provenance kind. Put grids, sizes used only for numerical
accuracy, quadrature thresholds, residual thresholds, and truncations in the
numerical-control schema, not scientific inputs. Put identity-bound fixed sizes
in `ProblemSizePolicy.fixed_sizes` and the exact same-observable sequences in
`ProblemSizePolicy.allowed_sizes`, using exactly the eleven entries and values
in `EXPECTED_SIZE_DATA`. These sizes are scientific identity/realization data;
do not replace them with numerical grids or an implementer-selected sequence.

For every output field, make `output_schema` bind its exact type/shape/units to
one raw calculated field and one of this exact generic proof-kind set:

```python
OUTPUT_PROOF_KINDS = frozenset({
    "direct_exact_value",
    "bounded_numeric_value",
    "grouped_exact_sequence",
    "rank_derived_integer",
    "all_residuals_within_bound_boolean",
    "positive_lower_bound_boolean",
    "positive_gap_and_odd_parity_boolean",
    "directional_limits_differ_boolean",
    "no_finite_crossing_boolean",
    "no_finite_crossing_zero_limit",
})
```

These generic mechanisms contain
no expected value, benchmark branch, formula table, or arbitrary expression.
All method-specific formulas stay in the adapter entry closure. The generic
proof interpreter belongs to the complete infrastructure closure and may not
branch on adapter ID. The entire canonical `AdapterDefinition`, including
observable identity, all schemas, provenance requirements, runtime/resource
requirements, size policy, counterfactual domain, convergence contract, output
proof bindings, oracle ID, and limits, becomes part of the adapter-side
scientific-policy commitment in Task 5, together with the exact canonical
`EligibilityDecision` row and whole-catalog hash.

Do not implement science with placeholder constants in this task. Entry symbols
may resolve only after Tasks 13–16; metadata validation must not execute them.

- [ ] **Step 5: Add forbidden-vocabulary recursion tests**

Parameterized tests must reject forbidden tokens at any nesting depth and in
tagged aliases. Match normalized tokens for `expected`, `target`, `answer`,
`result`, `registry`, `evidence`, `verdict`, `comparison`, `tolerance`,
`source_operand`, and `report`. Confirm that declared numerical names such as
`quadrature_absolute_threshold` are allowed only in the numerical-control
schema.

- [ ] **Step 6: Verify GREEN and commit**

Run the whole Task 7 test module. Run the protected baseline and commit gate,
then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: define literature adapter metadata"
```

Run the protected baseline again.

### Task 4: Add authority-context, request, result, and failure contracts

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Create: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Create: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED tests for the authority boundary**

Add a test-only producer that creates canary model inputs, provenance records,
canonical/registry/selector commitments, and forbidden fingerprints without
importing production registry data. Tests must independently mutate producer
ID/hash, canonical-spec hash, registry hash, selector hash, fingerprint set,
parameter provenance, and context hash and require rejection.

Use these tests:

```python
def test_authority_context_requires_exact_closed_fields_and_hash(): ...
@pytest.mark.parametrize("mutation", AUTHORITY_MUTATIONS)
def test_authority_context_rejects_stale_or_incomplete_commitments(mutation): ...
def test_production_validation_rejects_test_authority_producer(): ...
def test_target_equivalent_parameter_provenance_is_rejected(): ...
```

- [ ] **Step 2: Write RED request/result/failure tests**

Assert that a worker request contains only schema version, opaque nonce,
adapter ID, scientific inputs, numerical controls, and capsule hash. Recursively
search serialized request bytes for authority-only canaries. Assert exact local
results contain identity, fields, units, uncertainty, convergence, diagnostics,
operation counts/sizes, and monotonic timestamps but no success/verdict or
literature comparison. Assert failures have closed status/stage/reason/bounded
diagnostic and cannot carry a success bundle.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'authority or worker_request or local_observable or failure_contract'
```

Expected: import or symbol failures.

- [ ] **Step 4: Implement the closed isolation records**

Add frozen records and exact validators for:

```python
AdapterAuthorityContext, WorkerRequest, LocalObservableResult,
ScientificClosure, ScientificPolicyCommitment, InfrastructureClosure,
StaticScanReport, RuntimeResourceManifest,
RuntimeSnapshot, CapabilityPreflightReport, ProcessAttestation,
TracePolicyReport, PointExecutionEvidence, ConvergenceDecision,
OracleDecision, AdapterExecutionEvidence, AdapterRunFailure,
AdapterRunOutcome, EventRecord
```

Define the closed `OracleDefinition` contract and an initially empty immutable
`ORACLE_DEFINITIONS` mapping in the oracle module. It contains oracle ID, entry
symbol, input/result schemas, runtime requirements, convergence/invariant
contract, and resource limits, but no scientific implementation or expected
answer. Task 13 fills the mapping and entry points. This early contract lets
Task 12 build a real synthetic oracle definition without inventing a parallel
test-only shape.

Canonical definition serialization is a first-class commitment, not ordinary
transport metadata. `ScientificPolicyCommitment` records role, ID, canonical
definition bytes/hash, the adapter eligibility-row/catalog hashes when
applicable, entry-closure hash, exact output/invariant proof bindings,
domain/size/convergence hashes, static-scan report hash, and one combined hash.
Unknown definition fields or noncanonical bytes fail before capsule emission.

The context validator may structurally accept the closed producer ID
`task8_canonical_authority_v1`; tests may opt into the separate
`task7_test_authority_v1` ID explicitly. This opt-in must never be the default.
Context hashing covers all fields except the stored context hash itself.

- [ ] **Step 5: Implement request projection and result validation**

`make_worker_request` in the isolation module must project only answer-free
inputs/controls and must not accept arbitrary extra request metadata.
`validate_local_observable_result` belongs in the adapter module, as promised
by the locked public API; it must check adapter ID, capsule/request hashes,
exact output fields and units,
finite values, uncertainty for approximate fields, raw convergence evidence,
backend diagnostics, and monotonic timestamp ordering.

- [ ] **Step 6: Verify GREEN and commit**

Run the focused and full Task 7 tests. Run the protected baseline and commit
gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add isolated recalculation evidence contracts"
```

Run the protected baseline again.

### Task 5: Build deterministic AST scientific closures

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Create RED synthetic-module fixtures in the test run directory**

Fixtures must cover a pure entry point with a transitive helper/import/constant,
a changed helper, an unresolved global, cyclic initializer, star import,
dynamic import, mutable global, decorator side effect, descriptor/metaclass,
module mutation, runtime closure, and source evaluation. Create fixtures under
`tmp_path` with exclusive writes; do not add fixture files to the repository.
Add a fixture that tries to classify a formula/result-derivation helper as
transport infrastructure and require rejection.

- [ ] **Step 2: Add closure-manifest assertions**

Test that the emitted closure includes only statically resolved nodes and
records for each node: original relative path, raw-file SHA-256, node kind,
qualified name, source-span SHA-256, emitted-node SHA-256, dependency edges,
scanner version, and deterministic bundle hash. Extract a known pure synthetic
helper while proving an unrelated registry-like assignment in the same source
file is absent from emitted bytes.

Independently test `build_infrastructure_closure`. Lock an independent test
fixture containing the complete trusted root-symbol set, not a set imported
from production. The final set covers all of these categories and every
transitive project dependency:

- canonical JSON, recursive immutability, and closed contract validators;
- authority validation, worker/request/result transport, and failure shaping;
- AST closure construction, policy construction, static/fingerprint scanners,
  capsule and fixed-worker emission;
- runtime-resource discovery, no-follow snapshot copy, hashing, and post-run
  revalidation;
- event ordering, OS randomness acquisition, deterministic counterfactual
  generation, request creation, and metamorphic checks;
- capability-preflight orchestration, command identity/version/hash checks, and
  preflight report validation;
- run-directory/dirfd validation, mount-tree construction, namespace supervisor,
  tracer, tracee launcher, chroot, capability/no-new-privilege/resource-limit/
  environment/mount attestation, and bounded pipe handling;
- strace invocation/parsing/access adjudication and descriptor-pinned output/
  scratch ingestion;
- backend/environment diagnostics, generic proof interpreter, convergence and
  oracle adjudication;
- coordinator state machine, dependency partition enforcement, snapshot final
  validation, seed disclosure, evidence validation, and canonical final hashing.

The independent fixture hard-codes these concrete root names (module prefixes
omitted here only for readability):

```python
EXPECTED_INFRASTRUCTURE_ROOTS = {
    "freeze_json", "thaw_json", "canonical_json_bytes", "canonical_sha256",
    "validate_adapter_definition", "validate_oracle_definition",
    "validate_scientific_inputs", "validate_numerical_controls",
    "validate_local_observable_result", "validate_authority_context",
    "make_worker_request", "validate_failure",
    "build_scientific_closure", "build_scientific_policy_commitment",
    "build_infrastructure_closure", "scan_scientific_closure",
    "discover_runtime_resources", "build_runtime_snapshot",
    "revalidate_runtime_snapshot", "record_and_freeze_hashes",
    "acquire_run_seed", "derive_counterfactual_points",
    "write_worker_request_exclusive", "run_capability_preflight",
    "emit_scientific_capsule", "emit_fixed_worker",
    "create_run_directories", "construct_private_root",
    "run_namespace_supervisor", "launch_traced_tracee",
    "apply_tracee_security_policy", "validate_process_attestation",
    "evaluate_strace", "ingest_worker_output",
    "collect_backend_diagnostics", "interpret_output_proofs",
    "derive_convergence_decision", "derive_oracle_decision",
    "assert_complete_dependency_partition",
    "validate_adapter_execution_evidence",
    "_run_isolated_recomputation_core", "run_isolated_recomputation",
}
```

The test fixture stores fully qualified module/symbol pairs so same-named roots
cannot alias. A later task may split a root only by amending this independent
set and proving that all replacements are included; it may never silently add
an uncommitted success-determining helper.

The fixture names the concrete root functions introduced across Tasks 4–12.
Task 5 tests the builder against synthetic implementations of the full root set;
each later infrastructure task adds its concrete root and a category-level
closure test. Task 12 requires every named production root to resolve, no extra
root to exist, and the full transitive union to be closed before its successful
synthetic run. Thus Task 5 does not require future functions to exist early.

The manifest records the same node/span/edge/hash data as a scientific closure
plus an exact closed purpose tag per root. It rejects model Hamiltonians,
scientific equations/constants, adapter/oracle definitions or policy bytes,
method-specific result derivations, and any caller-designated extra root.

Also build synthetic adapter/oracle `ScientificPolicyCommitment` objects. Prove
that changing any canonical definition field, counterfactual rule, size,
convergence threshold, output/invariant proof binding, runtime requirement,
resource limit, oracle ID, or entry-closure node changes the combined hash.
Reject target fingerprints, benchmark/result lookup structures, categorical
answer literals, arbitrary expressions, adapter-ID branches, unknown proof
kinds, and noncanonical encodings in either role.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'scientific_closure or infrastructure_closure or unresolved_dependency or transitive_hash'
```

- [ ] **Step 4: Implement source-only AST resolution**

Parse files with `ast.parse` without importing them. Index top-level imports,
functions, classes, and immutable scalar/small-structure assignments. Walk each
loaded global recursively and classify it as a closed builtin, approved import,
approved project definition, or declared immutable constant. Reject every
unsupported construct before emission.

Emit imports and nodes in deterministic topological order. Normalize only line
endings and generated transport scaffolding; preserve node semantics. Hash raw
source spans before emission and emitted nodes afterward. Never mount the raw
source file.

- [ ] **Step 5: Enforce adapter/oracle role separation**

`build_scientific_closure(..., role="adapter")` must reject oracle-module
scientific nodes; the oracle role must reject adapter-module scientific nodes.
Add `assert_disjoint_scientific_closures` comparing qualified source nodes and
span hashes. Shared scientific nodes are never allowed. Any shared node must be
present in the separately built `InfrastructureClosure`, carry one allowed
infrastructure-purpose tag, pass its own forbidden-vocabulary/dependency scan,
and be absent from both scientific-node manifests. Hash the infrastructure
closure and scanner report independently; changing one transport/isolation
node must change its closure hash and later the final evidence hash.

Add `assert_complete_dependency_partition`. For one run, every project source
node used or referenced by the adapter capsule, oracle capsule, outer policies,
counterfactual/convergence/oracle decisions, or coordinator/isolation path must
occur exactly once in the adapter execution closure, adapter policy commitment,
oracle execution closure, oracle policy commitment, or infrastructure closure.
Only pre-hashed external interpreter/library resources are outside this project
partition. Missing, multiply classified, dynamically resolved, or uncommitted
nodes fail before the random seed is acquired.

When an infrastructure root looks up `ADAPTER_ELIGIBILITY`,
`ADAPTER_DEFINITIONS`, or `ORACLE_DEFINITIONS`, the closure graph records a
typed edge to the already canonicalized catalog/policy commitment instead of
silently absorbing or ignoring the concrete scientific mapping assignment.
Those three immutable mappings are the only permitted committed-data edges;
every other loaded project global must resolve to a source node in exactly one
closure. Changing a row, definition, or mapping membership therefore changes
the frozen catalog/policy/partition hash without misclassifying scientific data
as infrastructure.

- [ ] **Step 6: Verify GREEN and commit**

Run focused tests and the full Task 7 module. Run the protected baseline and
commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: bind scientific and infrastructure closures"
```

Run the protected baseline again.

### Task 6: Enforce static imports, dependency, and embedded-output policy

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED mutation tests for every forbidden source class**

Independently inject registry/evidence/source/report imports, environment/Git
discovery, dynamic import, `eval`/`exec`, reflection, file/network/process APIs,
undeclared native-library access, benchmark-name branching, exact categorical
canaries, high-precision numeric fingerprints, whole serialized operands,
field/value structures, parameter/result lookup tables, and a transitive helper
copy. Repeat each applicable mutation with `role="oracle"`. For the
infrastructure closure, inject a scientific equation, Hamiltonian builder,
method-specific or adapter-ID result-field derivation, adapter/oracle
definition, and undeclared root; each
must fail the infrastructure-purpose scan rather than being exempted.
Mutate canonical adapter/oracle definition bytes independently with a target
numeric/string fingerprint, benchmark-conditioned proof binding, answer table,
fixed canonical point list, arbitrary derivation expression, weakened domain,
or post-hoc convergence threshold and require its scientific-policy scan to
reject the definition before hashing succeeds.

- [ ] **Step 2: Write RED false-positive controls**

Prove that mathematical literals `-2, -1, -0.5, 0, 0.5, 1, 2`, loop bounds,
matrix indices, and dimensions are not rejected solely due to numeric value.
They remain rejectable when used in answer lookup structures or literal-return
branches.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'static_scan or embedded_output or forbidden_import or lookup_table'
```

- [ ] **Step 4: Implement closed static scans**

Add explicit allowlists for safe builtins, standard-library symbols, and
declared numerical-package imports. Add explicit forbidden module/symbol/token
vocabularies. Scan raw AST, closure graph, literal context, emitted bytes, and
canonical forbidden fingerprints for adapter, oracle, and infrastructure
roles. Scan the infrastructure closure additionally under its narrower exact-root/purpose policy and bind
its report to the same scanner implementation/version. Scan canonical
`AdapterDefinition`/`OracleDefinition` bytes and every nested domain, size,
schema, proof, convergence, runtime, and resource object as the corresponding
role's scientific policy; bind that scan report and canonical-definition hash
into `ScientificPolicyCommitment`. Fingerprints are validated outside the
capsule and never emitted or mounted.

The report must contain scanner version/hash, every check with a boolean and
bounded reason, scanned closure hash, fingerprint commitment, and closed pass
status. It must not echo forbidden operands in diagnostics.

- [ ] **Step 5: Verify GREEN and commit**

Run focused tests and the full Task 7 module. Run the protected baseline and
commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: reject scientific answer leakage"
```

Run the protected baseline again.

### Task 7: Discover, snapshot, and revalidate the runtime resource closure

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED discovery and manifest tests**

With injected command/file probes, require discovery of the exact interpreter,
dynamic loader, every regular file reported by `ldd`, imported standard-library
files, declared distribution files, and declared backend resources. Assert that
each manifest row records logical mount destination, original resolved path,
link identity when applicable, file type, size, mode, SHA-256, distribution and
version, and purpose. Reject a resource under the project, worktree parent,
source cache, reports, user configuration, or an undeclared package.

- [ ] **Step 2: Write RED snapshot/TOCTOU tests**

Tests must independently:

- replace or mutate the original between pre- and post-copy `fstat`;
- short-read or alter bytes during copying;
- replace, chmod, hard-link, or mutate a snapshot after hashing;
- add an undeclared snapshot entry;
- change only the original after a valid snapshot and prove the snapshot stays
  valid and contains the original frozen bytes.

Retain directory FDs in the returned object and make tests revalidate through
those FDs, not through a path reopened later.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'runtime_resource or runtime_snapshot or snapshot_toctou'
```

- [ ] **Step 4: Implement resource discovery**

Resolve the interpreter from `sys.executable`, parse `ldd` output without shell
evaluation, use `sysconfig` and module specs for only the declared standard
library, and use `importlib.metadata` for only declared distributions. Resolve
symlinks component by component while recording link and target identities.
Do not accept a directory as shorthand for its contents; expand to an exact
file list before hashing.

- [ ] **Step 5: Implement file-level immutable snapshot construction**

Create the run directory and snapshot paths exclusively at mode 0700. For each
source use parent directory FDs plus `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, verify
regular type and `fstat` before/after copying, create the destination with
`O_CREAT|O_EXCL|O_NOFOLLOW`, stream bytes with a fixed buffer, `fsync`, reopen
no-follow, byte-compare and hash. Set only the required read or read/execute
mode. Make directories non-writable after population.

`RuntimeSnapshot.revalidate()` must use retained dirfds, exact basename sets,
and no-follow opens to recheck type, device/inode policy, link count, length,
mode, and hash after all child processes exit.

- [ ] **Step 6: Record event-order hooks and verify GREEN**

Record discovery, source validation, copy, byte comparison, manifest hash, and
snapshot freeze events. Run focused tests and the full Task 7 module.

- [ ] **Step 7: Commit Task 7**

Run the protected baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: freeze recalculation runtime resources"
```

Run the protected baseline again.

### Task 8: Generate post-freeze counterfactuals and enforce event ordering

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED ordering tests**

Inject an event recorder and a random-byte provider. Require the exact partial
order. Until Task 9 implements the executed host preflight, this ordering unit
test injects a structurally valid, freshly nonce-bound synthetic
`CapabilityPreflightReport` plus exact synthetic command hashes through the
internal event-test fixture; production `run_capability_preflight` is never
stubbed in an integration or acceptance test:

```text
definition/provenance validation
< adapter and oracle closure hashes
< canonical adapter/oracle definition and scientific-policy commitment hashes
< complete infrastructure closure/scan and dependency-partition hashes
< runtime snapshot materialized/compared/hashed
< adapter/oracle/worker capsule hashes
< fresh capability-preflight report, report hash, and every infrastructure-command hash
< frozen-hashes event
< 32-byte random acquisition
< point derivation
< exclusive request writes
< adapter executions
< oracle executions
< convergence/isolation/oracle decisions
< seed disclosure and final evidence hash
```

Force random acquisition at each earlier hook and require a hard failure.
Also mutate one definition/domain/size/output proof/convergence rule, preflight
result, external-command identity/hash, dependency-partition commitment, or
infrastructure-closure hash after the frozen event and require the run to fail
before point derivation. A cached design-time preflight cannot satisfy this
ordering test.

- [ ] **Step 2: Write RED generator tests for every backend/size family**

Assert exact minimum coverage:

- analytic: canonical plus three random valid model points and one invalid
  boundary;
- fixed-local enumeration/dense ED: three random valid coupling/field/scale or
  basis/gauge points at the one identity-bound size, plus one invalid parameter
  or different size rejected before science;
- scalable enumeration/dense ED: two valid physical points at each of exactly
  two declared same-observable sizes, plus one disallowed size/shape;
- GLT/Fourier: three couplings and two momenta/configurations per coupling plus
  a real/Fourier invariant;
- iterative: one random model point with at least three strictly stronger
  controls plus one invalid control.

Parameterized tests must cover all 29 definitions, not only one representative.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'event_order or counterfactual or disclosed_seed or size_identity'
```

- [ ] **Step 4: Implement a versioned deterministic generator**

Use an HMAC/SHA-256 counter-mode stream derived from the 256-bit run seed,
adapter ID, domain version, point kind, and point index. Convert bounded integers
to floats without global PRNG state. Domain objects must generate inputs from
answer-free bounds and declarative transforms; they may not contain fixed
canonical output values or candidate-answer lists.

Return typed `CounterfactualPoint` records with `canonical`, `valid`, or
`invalid` kind, scientific inputs, controls, expected validation outcome (only
for invalid-input reason, never a scientific answer), and metamorphic relation
metadata.

- [ ] **Step 5: Enforce fresh-process and constant/branch rejection metadata**

Assign a distinct run nonce per point. Add validators for scaling, symmetry,
continuity, bounds, basis/gauge invariance, and real/Fourier identities. The
outer coordinator later uses them to reject a constant scientific operand or a
canonical-point branch.

- [ ] **Step 6: Verify GREEN and commit**

Run focused and full Task 7 tests. Run the protected baseline and commit gate,
then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: derive post-freeze counterfactual probes"
```

Run the protected baseline again.

### Task 9: Implement fail-closed production capability preflight

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED injected-failure tests for all fourteen probes**

Model each capability check as a separately reported executed probe. With an
injected runner, fail each check in turn and assert `available is False`, the
exact closed reason code, available evidence hashes, a bounded diagnostic, and
zero adapter execution attempts. Missing, malformed, or contradictory probe
output must also be unavailable.

- [ ] **Step 2: Add a real positive-host test with no skip path**

Add `test_production_capability_preflight_succeeds_on_designated_host`. It must
execute, not merely inspect command presence. It verifies distinct user/mount/
network namespace IDs, root mapping without sudo, private mounts, tmpfs,
read-only bind behavior, read-only root with writable nested output, chrooted
interpreter execution, all capability sets dropped, parent environment canary
absence, empty external network/route, host canary denial, complete strace
behavior including failed access, resource limits, and no-new-privileges.

Do not decorate this test with `skipif`; on an unsupported host it fails with
the structured report, which is required by Task 7 acceptance.

- [ ] **Step 3: Verify RED unit tests first**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'preflight and not production_capability'
```

- [ ] **Step 4: Implement the preflight probe program**

Create a unique retained scratch directory exclusively. Launch `unshare -Urnm`
with an empty environment plus fixed locale/hash controls. Inside, make `/`
private, construct a tmpfs root, bind/remount the required probes, launch a
traced chroot child, drop capabilities with `setpriv` or the pre-hashed
equivalent, set limits and no-new-privileges, and write a closed attestation.
Never use sudo and never fall back.

Resolve and hash every external command before execution. Store command paths,
versions/hashes, namespace IDs, mount facts, result codes, trace hash, and all
fourteen booleans in `CapabilityPreflightReport`.

- [ ] **Step 5: Run the real positive preflight test**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py::test_production_capability_preflight_succeeds_on_designated_host -vv
```

Expected: `1 passed`; no skips or xfails.

Also attach the real report to the event recorder with a random-provider canary
and prove all fourteen probe results, command hashes, and the report hash are
recorded before any random-byte call. Mutating or reusing the report under a
different audit-run nonce must fail.

- [ ] **Step 6: Run the full Task 7 module and commit**

Run the protected baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: preflight isolated recalculation capabilities"
```

Run the protected baseline again.

### Task 10: Emit the fixed worker and build the namespace supervisor topology

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED worker/capsule tests**

Assert deterministic adapter and oracle capsule bytes, a separately hashed
fixed worker, isolated-mode interpreter flags, exact request-hash/capsule-hash
checks, exclusive creation of `result.json`, closed stdout/stderr behavior, and
no imports outside the emitted capsule/runtime. Prove the worker cannot see the
authority context or forbidden fingerprints.

- [ ] **Step 2: Write RED mount/topology tests using an injected command runner**

Require the exact process tree:

```text
outer coordinator
  -> unshare -Urnm namespace supervisor (persists)
     -> external strace tracer
        -> fixed tracee launcher
           -> chroot + cap drop + limits + worker exec
```

Assert the supervisor stays alive until tracer/tracee exit, remains outside the
chroot, receives no unrelated FDs, and alone can write trace/attestation.
Assert the worker-visible root contains exactly `/runtime`, `/adapter`,
`/input/request.json`, and `/output`, with only `/output` writable.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'worker_capsule or namespace_supervisor or mount_manifest'
```

- [ ] **Step 4: Implement fixed worker and launcher emission**

Emit source from fixed infrastructure functions, not caller strings. The worker
reads exactly `/input/request.json`, imports the single scientific entry point
from `/adapter`, calculates once, validates transport shape, and creates exactly
`/output/result.json`. The tracee launcher performs chroot, `chdir("/")`, limit
setting, capability drop, no-new-privileges, FD closure, and exact interpreter
exec in that order.

- [ ] **Step 5: Implement the persistent supervisor**

Create a mode-0700 run directory with disjoint `supervisor`, `input`, and
`worker-output` directories and retain their dirfds/device/inode identities.
The supervisor creates a private tmpfs root, exact mount points, file-level
snapshot binds, capsule/worker binds, the single request bind, and output bind;
then remounts root and every non-output mount read-only with `nodev,nosuid`.
There is no `/proc`, `/sys`, general `/dev`, home, host `/tmp`, project,
workspace, cache, evidence, report, Git, or prior-run mount.

Use an empty launch environment plus fixed locale, hash seed, and declared
thread controls. Drain stdout/stderr to bounded supervisor-owned pipes. After
process exit, re-attest namespace/mount facts and exclusively write the closed
attestation outside the worker mount.

- [ ] **Step 6: Add one real canary execution**

Use a synthetic answer-free arithmetic capsule and prove it runs in the exact
topology, sees no parent environment canary, cannot read a host canary, has no
external network route, and writes one valid output.

- [ ] **Step 7: Verify GREEN and commit**

Run focused and full Task 7 tests. Run the protected baseline and commit gate,
then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: run scientific capsules in private roots"
```

Run the protected baseline again.

### Task 11: Parse complete traces and harden output ingestion

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED closed-strace-parser tests**

Use recorded synthetic lines for absolute/relative `openat`, directory FDs,
renames, symlinks, `.`/`..`, failed accesses, unfinished/resumed syscalls,
per-PID logs, network syscalls, clone/fork/exec, native-library loads, and
truncated strings. Reject unknown forms, missing PID logs, unresolved paths,
prefix confusion (`/runtime-extra`), malformed continuation pairs, and any
forbidden attempted access even when it returns `ENOENT`.

- [ ] **Step 2: Write RED runtime attack tests**

In separate real isolated runs, attempt registry, canonical-spec, evidence,
source-cache, report, protected-WIP, parent, previous-output, environment-secret,
network, symlink escape, directory-FD escape, relative escape, subprocess, and
undeclared native-library access. Tests must distinguish static rejection from
runtime denial and require both to fail closed when reached.

Repeat registry/report, environment, network, previous-output, and malformed
trace attacks through an oracle capsule.

- [ ] **Step 3: Write RED descriptor-pinned output tests**

Independently substitute `result.json` with a symlink, hard link, FIFO, Unix
socket, directory, wrong-mode file, wrong-owner file, oversized file, replaced
directory, and an undeclared extra output. Also mutate output after open and
prove hashing/parsing uses the same FD. No test may block on FIFO/socket input.

- [ ] **Step 4: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'strace or runtime_attack or result_ingestion or output_substitution'
```

- [ ] **Step 5: Implement trace parsing and policy evaluation**

Invoke preflight-verified `strace` with follow-forks, untruncated strings,
file/network/process syscall classes, per-PID output, and directory-FD details.
The closed parser reconstructs attempted paths and identities against the mount
manifest. Reads are limited to the frozen runtime, adapter capsule, and one
request; writes are limited to declared `/output` entries. All network syscalls
and all post-launch process creation/exec are forbidden.

Hash raw traces before parsing. Store all allowed/denied attempts in bounded,
typed records without leaking host secrets. Missing, altered, truncated,
unparseable, or policy-violating traces are `isolation_failed`.

- [ ] **Step 6: Implement same-FD output ingestion**

After every process exits, verify the retained output-directory identity and
exact entry set. Open `result.json` relative to the retained dirfd with
`O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`. Use `fstat` to require regular file,
one link, expected uid/gid/mode/device, and byte bound. Read, hash, UTF-8 decode,
and JSON-parse from that same FD. Validate declared scratch entries with the
same no-follow exact-name policy.

- [ ] **Step 7: Verify GREEN and commit**

Run focused and full Task 7 tests, including real attacks. Run the protected
baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: enforce traced recalculation access policy"
```

Run the protected baseline again.

### Task 12: Compose the fail-closed coordinator and evidence bundle

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

- [ ] **Step 1: Write RED stage/failure matrix tests**

At this point the Task 4 oracle contract module exists, but its production
mapping is empty and none of the 29 scientific adapter/oracle implementations
exist yet. Define one answer-free synthetic adapter and one independently
implemented synthetic oracle as source files created exclusively under
`tmp_path`. Build a closed test-only `EligibilityDecision` plus
`AdapterDefinition`/`OracleDefinition` objects and pass them only to a
module-private coordinator core through a
`TestCoordinatorHarness` in the test module. The pair must pass the real AST,
static, snapshot, namespace, trace, output, convergence, and independence
controls; it contains no expected output fixture.

The production API keeps the locked three-argument signature. It lazily binds
the immutable production adapter/oracle mappings and source roots, and it does
not accept a resolver, definition, source root, service override, test flag, or
harness. Add tests proving callers cannot activate the private seam through
`run_isolated_recomputation`. The isolation module may import the closed Task 4
oracle contract, but it must not assume a production mapping entry or resolve a
scientific oracle symbol during Tasks 4–12.

Inject a failure at definition, authority, eligibility, closure, static scan,
scientific-policy commitment, infrastructure-root resolution, dependency
partition, snapshot, preflight, seed generation, request write, mount, worker launch,
timeout/signal/nonzero exit, trace, output, result validation, convergence,
oracle closure/isolation/output/decision, snapshot revalidation, and final
bundle hashing. Assert the exact top-level status/stage/reason and prove no
later stage or weaker retry executes.

Top-level statuses must be exactly:

```python
{
    "isolated_recomputation_succeeded",
    "strict_recomputation_unavailable",
    "adapter_ineligible",
    "input_rejected",
    "dependency_rejected",
    "isolation_failed",
    "execution_failed",
    "convergence_failed",
    "oracle_failed",
}
```

- [ ] **Step 2: Write RED evidence completeness tests**

Require the successful bundle to carry: authority-context hash and validated
input/provenance bindings; canonical eligibility row/catalog and adapter/oracle
definition bytes and hashes;
adapter/oracle execution source nodes and disjoint graphs; both complete
scientific-policy commitments and scan reports; the complete separately
classified infrastructure root list, transitive source-node manifest, purpose
tags, closure hash, static report, and dependency-partition hash;
capsule/worker/runtime hashes; ordering trace;
preflight hash/report reference; per-process namespace/mount/environment/limit/
chroot attestations; every request/result/trace hash; complete access-policy
reports; interpreter/distribution/native/BLAS/backend identities; raw
convergence data/decision; oracle hashes/outputs/residuals/decision; disclosed
seed; closed status; and final canonical bundle hash.

Mutate or omit each field independently and require bundle validation failure.
Move a scientific derivation node into the infrastructure manifest, introduce
an uncommitted shared node, or change an infrastructure node/purpose/hash and
require rejection.
Also mutate any adapter/oracle definition, domain, physical-size rule, output
proof binding, convergence/invariant rule, or scientific-policy hash and require
rejection without reusing prior static-scan evidence.

- [ ] **Step 3: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'coordinator_failure or evidence_bundle or unavailable_without_fallback'
```

- [ ] **Step 4: Implement `run_isolated_recomputation` as an explicit state machine**

Implement a module-private `_run_isolated_recomputation_core` whose dependency
bundle is a closed internal record accepted only by the test harness and the
production wrapper. The test harness constructs it from the synthetic pair;
the public wrapper constructs it internally from production immutable mappings
including the exact eligibility catalog and refuses all injection-shaped
arguments. The synthetic eligibility row is never added to
`ADAPTER_ELIGIBILITY` and cannot be selected by the public wrapper. This seam exists only to exercise
the full coordinator before Tasks 13–16 and is not serialized, mounted, or
exposed as production authority.

Do not catch all exceptions and relabel them generically. Each transition maps
expected errors to one closed reason. Bound diagnostics by byte count and strip
environment/source/registry content. Ineligible catalog rows return before
closure building. Invalid points fail validation before scientific execution.

Run adapter points first, validate them, then build typed oracle requests that
contain only answer-free inputs and the already validated local result fields
needed for invariants. Never mount the adapter output directory into an oracle
root. Revalidate the runtime snapshot after every adapter and oracle process has
exited and before success.

Build and scan both canonical scientific-policy commitments and the complete
infrastructure closure separately from the scientific execution closures.
Resolve every independent-test-fixture infrastructure root named in Task 5 and
all of its transitive project nodes. Require the full project dependency
partition to be exact and disjoint, hash definitions, policies, nodes, edges,
purposes, scans, and partition, and include the commitments in every successful
or sufficiently advanced failure outcome. Run the fresh capability
preflight and hash its report plus every command identity before the
frozen-hashes event and before random-byte acquisition.

- [ ] **Step 5: Implement outer convergence and oracle decisions**

Ignore helper-returned `converged` booleans. Derive exact, residual, quadrature,
dense-ED, GLT, finite-size, and iterative decisions from definition contracts
and raw samples. Require oracle project-scientific closure disjointness, its own
static scan/isolation/trace evidence, and contract-specific residual/bound
acceptance for every point.

Use one fully infrastructure-hashed generic proof interpreter for outer selected
fields. It consumes only the frozen output/invariant proof bindings and raw
certificates, supports the closed proof-kind set, and cannot dispatch on
adapter/benchmark ID or evaluate arbitrary expressions. Every method-specific
formula or certificate construction remains in that role's scientific entry
closure; changing either code or policy changes the frozen commitment.

- [ ] **Step 6: Implement final seed disclosure and evidence hashing**

Disclose the seed only after all decisions. Canonically hash the entire bundle
except its stored final hash, store it, freeze the object, and revalidate it.
Successful Task 7 output contains no literature comparison and no strict-match
flag.
The final hash covers adapter/oracle definition bytes, both scientific-policy
commitments, the complete infrastructure closure/scan, and the exact dependency
partition in addition to all runtime evidence.

- [ ] **Step 7: Verify GREEN and commit**

Run focused and full Task 7 tests. At this stage GREEN means the synthetic pair
exercises the complete private core; the public production wrapper must return
a closed dependency/unavailable failure until Tasks 13–16 supply its mappings,
and it must never fall back or report success. Run the protected baseline and commit gate,
then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: assemble isolated recalculation evidence"
```

Run the protected baseline again.

### Task 13: Implement analytic and exact-enumeration adapters with independent oracles

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

This task implements these exact 12 pairs:

| Adapter | Oracle | Selected fields |
| --- | --- | --- |
| `xxx_bethe_energy` | `xxx_bethe_integral_oracle` | `energy_per_site` |
| `square_ising_self_dual_tc` | `square_ising_duality_residual_oracle` | `tc_over_j` |
| `pauling_entropy_combinatorics` | `pauling_cluster_count_oracle` | `pauling_entropy_per_spin` |
| `aklt_projector_angle` | `aklt_two_spin_spectrum_oracle` | `aklt_tan_theta`, `theta_radians` |
| `honeycomb_ising_star_triangle_tc` | `honeycomb_ising_critical_polynomial_oracle` | `tc_over_j` |
| `kagome_ising_star_triangle_tc` | `kagome_ising_critical_polynomial_oracle` | `tc_over_j` |
| `ising_chain_transfer_matrix` | `ising_chain_partition_analytic_oracle` | `finite_temperature_transition`, `tc_over_j` |
| `triangular_ising_star_triangle_tc` | `triangular_ising_critical_polynomial_oracle` | `tc_over_j` |
| `spin_ice_tetrahedron_enumeration` | `spin_ice_tetrahedron_matrix_oracle` | four energy/degeneracy fields |
| `toric_code_stabilizer_rank` | `toric_code_logical_loop_oracle` | `torus_ground_state_degeneracy` |
| `blume_capel_level_crossing` | `blume_capel_configuration_oracle` | `square_lattice_d_over_j_crossing` |
| `checkerboard_plaquette_enumeration` | `checkerboard_total_spin_oracle` | `zero_total_spin_per_crossed_plaquette` |

- [ ] **Step 1: Write RED per-pair scientific tests**

For every row, test the canonical model point, all generated valid
counterfactuals, the invalid point, dimensional scaling or symmetry, exact
selected-field set, raw diagnostics, and independent oracle. Also test that
scientific adapter/oracle closures are disjoint and pass both static scans.

Use one parameterized entry point so a missing row cannot be skipped:

```python
@pytest.mark.parametrize("adapter_id,oracle_id", ANALYTIC_ENUMERATION_PAIRS)
def test_analytic_and_enumeration_pair_calculates_and_oracle_accepts(
    adapter_id, oracle_id, test_authority_context, tmp_path
): ...
```

Add mutation tests that replace each adapter result with a constant, canonical-
point branch, or copied categorical boolean and require counterfactual/static/
oracle rejection.

- [ ] **Step 2: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'analytic_and_enumeration or analytic_enum_mutation'
```

Expected: the oracle mapping is still empty and all production scientific entry
points are missing.

- [ ] **Step 3: Implement the eight analytic adapters without answer literals**

Implement the following actual calculations and return their raw equation,
root, residual, scaling, and uncertainty diagnostics. Selector booleans are
derived by the outer validator from raw diagnostics; the capsule must not
return an unexamined status literal.

1. `xxx_bethe_energy`: derive the Bethe root-density expression and evaluate
   `J*(1/4-log(2))` with the declared standard logarithm for arbitrary positive
   exchange, not by returning a decimal benchmark or the oracle's series/
   integral. Report absolute-energy scaling and a roundoff bound.
2. `square_ising_self_dual_tc`: bracket and solve
   `sinh(2*K_c) - 1 = 0` on the positive branch, then compute physical
   temperature from arbitrary positive exchange. Report bracket history,
   residual, and dual-temperature check.
3. `pauling_entropy_combinatorics`: count the six ice-rule assignments among
   all two-state tetrahedron assignments and derive the shared-spin asymptotic
   multiplicity before taking log per spin. Report counts and normalization,
   not a stored entropy decimal.
4. `aklt_projector_angle`: construct the spin-one `S_i.S_j` eigenvalues for
   total spin 0, 1, 2, interpolate the spin-two projector polynomial, and derive
   the biquadratic/bilinear ratio and `atan2` angle.
5. `honeycomb_ising_star_triangle_tc`: solve the positive honeycomb
   star-triangle residual `sinh(2*K_c)-sqrt(3)=0` and invert to temperature.
6. `kagome_ising_star_triangle_tc`: solve the physical positive branch of the
   kagome star-triangle equation in an exponential variable and report both the
   original and transformed residuals. Do not seed the solver with the
   registered root.
7. `ising_chain_transfer_matrix`: construct the 2x2 transfer matrix at arbitrary
   finite positive beta/exchange, compute both eigenvalues across random probes,
   and establish positive separation for all finite probes. The outer validator
   derives `finite_temperature_transition=False` and `tc_over_j=0` only from the
   analytic separation/limit evidence.
8. `triangular_ising_star_triangle_tc`: solve the positive triangular
   star-triangle equation and invert to temperature, reporting bracket and
   critical-polynomial residuals.

- [ ] **Step 4: Implement four exact enumeration adapters**

1. `spin_ice_tetrahedron_enumeration`: enumerate all 16 Ising assignments,
   calculate six pair energies from the Hamiltonian, group by total charge, and
   derive the three selected sector energies and zero-charge degeneracy from the
   groups.
2. `toric_code_stabilizer_rank`: for each declared periodic size, build vertex
   and plaquette GF(2) incidence rows, perform explicit row reduction, and derive
   `2 ** (n_qubits-rank)`; verify the declared same-observable size sequence.
3. `blume_capel_level_crossing`: enumerate all uniform spin-one local states and
   square-lattice bond incidences for arbitrary positive exchange, construct
   energy lines in anisotropy, and solve the ordered/zero envelope crossing.
4. `checkerboard_plaquette_enumeration`: enumerate a declarative set of
   normalized four-spin configurations and a complete-graph bond matrix,
   calculate every pair energy and total-spin norm, and use an exact lower-bound
   certificate from the interaction-matrix spectrum to prove the minimizing
   configurations have zero total spin. The adapter must not call the oracle's
   total-spin-squared identity.

- [ ] **Step 5: Implement all 12 genuinely independent oracles**

Populate the Task 4 `OracleDefinition` contract and immutable
duplicate-detecting `ORACLE_DEFINITIONS` mapping with these twelve rows. Implement:

- XXX via an alternating-series or Fermi-integral representation with a
  certified tail bound;
- square Ising via the rearranged Kramers-Wannier map and involution;
- Pauling via explicit finite Husimi-tree/shared-spin cluster counts at multiple
  depths and normalized limiting trend;
- AKLT angle via independently constructed spin-one matrices/Clebsch-Gordan
  sector projectors;
- honeycomb and triangular Ising by transforming into one another's dual
  critical equation;
- kagome Ising by eliminating radicals into an independent critical polynomial
  and choosing the physical branch;
- one-dimensional Ising via independently enumerated finite-size partition
  functions and absence of eigenvalue crossing;
- spin ice via total-charge squared plus binomial sector multiplicities;
- toric code via logical Wilson-loop pairs and their GF(2) commutation algebra;
- Blume-Capel via independent onsite/bond energy-per-site lines;
- checkerboard via the independent
  `sum_{i<j} S_i.S_j=(|sum_i S_i|^2-sum_i|S_i|^2)/2` identity.

No oracle imports an adapter scientific symbol or copies its helper, formula
function, or constant assignment.

- [ ] **Step 6: Add contract-specific outer derivation/convergence rules**

The outer validator converts raw numeric certificates into exact selected
operands and records the derivation. It requires zero uncertainty for integer,
GF(2), and exact enumeration results; a declared residual/roundoff bound for
root solves; exact sizes for fixed-local rows; and all declared scalable sizes
for toric code. It rejects helper-provided `converged=True` without raw proof.
Populate only closed generic proof kinds/bindings in each canonical definition;
do not add an adapter-ID branch or method-specific formula to the outer
interpreter. Rebuild, scan, and freeze all twelve adapter/oracle
`ScientificPolicyCommitment` objects before their first production-style run.

- [ ] **Step 7: Run focused real isolation tests**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'analytic_and_enumeration or analytic_enum_mutation' -vv
```

Expected: every pair and mutation test passes with no skips.

- [ ] **Step 8: Commit Task 13**

Run the full Task 7 module, protected baseline, and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add exact recalculation adapter families"
```

Run the protected baseline again.

### Task 14: Implement all seven dense-ED adapters and matrix-independent oracles

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

Implement exactly:

| Adapter | Oracle | Size policy | Selected fields |
| --- | --- | --- | --- |
| `spin_ladder_rung_dense_ed` | `spin_ladder_analytic_rung_oracle` | fixed local | `energy_per_rung`, `gap_to_triplet` |
| `uls_two_site_su3_matrix` | `uls_permutation_commutator_oracle` | fixed local | `theta_radians`, `su3_symmetric` |
| `compass_line_symmetry_matrix` | `compass_spin_flip_oracle` | scalable | `has_line_flip_symmetries` |
| `aklt_two_site_projector_ed` | `aklt_clebsch_gordan_oracle` | fixed local | `two_site_projector_eigenvalues`, `vbs_ground_energy` |
| `majumdar_ghosh_dimer_ed` | `majumdar_ghosh_projector_oracle` | scalable | `energy_per_site`, `degenerate_dimer_coverings` |
| `shastry_sutherland_dimer_ed` | `shastry_sutherland_bond_oracle` | scalable | `energy_per_dimer`, `energy_per_spin` |
| `spin1_single_ion_dense_ed` | `spin1_m_quantum_number_oracle` | fixed local | `levels`, `degeneracies` |

- [ ] **Step 1: Write RED all-pair matrix tests**

For every row require Hermiticity norm, normalized eigenvectors, raw eigenpair
residuals, trace/dimension diagnostics, exact size honesty, basis/unitary
counterfactual invariance, selected output fields, isolated oracle agreement,
and complete per-point evidence. Inject non-Hermitian, wrong-size, truncated-
spectrum, stale-residual, copied-eigensystem, and constant-status mutations.

- [ ] **Step 2: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'dense_ed_pair or dense_ed_mutation'
```

- [ ] **Step 3: Implement reusable answer-free spin-matrix primitives**

Inside the adapter closure, construct spin matrices algorithmically from
raising/lowering coefficients for arbitrary declared spin, then Kronecker
operators and bond Hamiltonians. Do not store final spectra. Include only these
transitive primitives in each emitted capsule. Use `numpy.linalg.eigh` only
when NumPy is declared/snapshotted; otherwise use the declared SciPy driver and
record it.

- [ ] **Step 4: Implement the seven adapter calculations**

1. Ladder: diagonalize `J_rung S1.S2` for two spin halves; group singlet/triplet
   by `S_total^2`; return raw lowest energy and sector gap only. Exclude the
   legacy `spin_ladder_material` field entirely.
2. ULS: build spin-one bilinear/biquadratic matrices, solve for the coefficient
   angle where the shifted Hamiltonian is permutation-equivalent, construct
   total generators, and report permutation residual and every commutator norm.
3. Compass: on the declared open 2x2 and 2x3 rectangles, build horizontal
   X-bond and vertical Y-bond Hamiltonians and every corresponding column-X and
   row-Y line-flip matrix; calculate all commutator norms.
4. AKLT: build two spin-one `S_total^2`, derive the spin-two spectral projector,
   diagonalize it, and calculate its kernel/local VBS energy.
5. Majumdar-Ghosh: construct periodic spin-half J1-J2 Hamiltonians at one-half
   ratio for more than one declared even size, resolve the low spectrum, energy
   density, and overlap rank of two translated dimer coverings.
6. Shastry-Sutherland: construct the declared open linked-cell realizations
   with exactly two/four orthogonal dimers and four/eight spins. Generate each
   dimer/interdimer bond once from the cell incidence rule, diagonalize/check
   the tensor product of singlets, and calculate paired interdimer cancellation
   plus per-dimer/per-spin normalization.
7. Single-ion: construct `D*(S_z)^2` for arbitrary nonzero positive/negative
   anisotropy, diagonalize, group numerically equal levels, and report
   degeneracies.

- [ ] **Step 5: Implement independent matrix oracles**

Use analytic singlet/triplet projectors for ladder; independently constructed
SU(3) permutation/generator matrices for ULS; Pauli-string conjugation parity
without dense commutators for compass; Clebsch-Gordan sector polynomials for
AKLT; local three-site projector decomposition plus explicitly constructed
dimer covering vectors for Majumdar-Ghosh; bond-projector expectations on a
separately assembled product state for Shastry-Sutherland; and direct magnetic
quantum-number enumeration for single-ion levels.

Oracle helper graphs must not intersect adapter helper graphs. Test this at the
source-node and span-hash levels.

- [ ] **Step 6: Derive dense-ED convergence outside workers**

Require Hermiticity norm, maximum eigenpair residual, orthogonality residual,
declared eigensolver identity, exact matrix dimension, and size-policy evidence.
For scalable rows require every declared size and cross-size invariant; for
fixed-local rows reject even a scientifically plausible second physical size as
`observable_identity_mismatch`.
Express those decisions through canonical convergence/proof bindings interpreted
by the generic infrastructure root; matrix construction, sector grouping, and
method-specific predicates stay inside the disjoint adapter/oracle scientific
closures. Rebuild and freeze each pair's policy commitments before randomness.

- [ ] **Step 7: Verify GREEN and commit**

Run focused tests with `-vv`, then the full Task 7 module. Run the protected
baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add dense ed recalculation adapters"
```

Run the protected baseline again.

### Task 15: Implement all six GLT/Fourier adapters and real-space oracles

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

Implement exactly:

| Adapter | Oracle | Selected fields |
| --- | --- | --- |
| `xy_chain_bdg_boundaries` | `xy_chain_dense_bdg_oracle` | `ising_critical_field`, `anisotropy_transition_gamma` |
| `diamond_spiral_threshold_fourier` | `diamond_real_space_threshold_oracle` | `spiral_surface_for_j2_over_j1_gt` |
| `kitaev_field_majorana_mass` | `kitaev_two_band_chern_oracle` | `field_opens_non_abelian_gap` |
| `pyrochlore_coulomb_fourier` | `pyrochlore_real_space_constraint_oracle` | `zero_total_spin_per_tetrahedron`, `pinch_points` |
| `simple_cubic_j1_j2_fourier` | `simple_cubic_real_space_energy_oracle` | `neel_to_collinear_boundary_j2_over_j1` |
| `tfim_bdg_critical_point` | `tfim_duality_gap_oracle` | `critical_field_over_exchange` |

- [ ] **Step 1: Write RED Fourier-pair tests and attacks**

For all six require three random couplings, two momenta/configurations per
coupling, reciprocal symmetry, raw eigenvalues/minima/gaps, real/Fourier
identity checks, grid or analytic minimization evidence, isolated oracle
agreement, and complete bundles. Reject supplied candidate wavevectors,
registered-root seeding, insufficient momentum resolution, a single
representative point, missing neighboring gaps, constant booleans, and copied
oracle kernels.

- [ ] **Step 2: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'fourier_pair or fourier_attack'
```

- [ ] **Step 3: Implement each Fourier calculation from model inputs**

1. XY chain: construct the 2x2 BdG matrix from arbitrary exchange, field,
   anisotropy, and momentum; scan/refine gap minima and locate field and
   anisotropy gap-closing manifolds. Return raw determinants, particle-hole
   residuals, minima, and neighboring gaps.
2. Diamond J1-J2: construct the two-sublattice exchange kernel from lattice
   phase factors, diagonalize the lower band, derive the interior-minimum onset
   analytically from the allowed structure-factor range, and confirm it with
   random momentum searches on both sides. Do not accept a candidate-q list.
3. Kitaev field: construct the third-order Majorana mass from arbitrary nonzero
   field components/exchange, build the two-band d-vector Hamiltonian on a
   momentum mesh, calculate gap minimum and discrete winding/Chern parity. The
   outer validator derives the selected boolean from nonzero gap and odd parity.
4. Pyrochlore: build the Fourier constraint/projector matrix, calculate its
   flat/transverse modes and polarization tensor, and approach a pinch point
   along at least two independently generated directions. Also report a
   tetrahedron zero-sum residual.
5. Simple cubic J1-J2: construct
   `J(q)=2 J1(sum cos q_i)+4 J2(sum cos q_i cos q_j)`, minimize the Néel and
   collinear branches, solve their crossing, and verify random grid points on
   both sides.
6. TFIM: construct the Jordan-Wigner BdG matrix and dispersion for arbitrary
   positive exchange/field, minimize over momentum, bracket/refine the unique
   thermodynamic gap closing, and record neighboring gaps and scaling.

- [ ] **Step 4: Implement independent real-space/dense oracles**

XY uses independently assembled finite real-space BdG matrices and determinant/
particle-hole invariants; diamond uses direct real-space single-q spin energies;
Kitaev uses an independently parameterized d-vector mass and plaquette Berry
phase; pyrochlore uses explicit tetrahedron divergence constraints and
directional structure factors; simple cubic counts first/second-neighbor bonds
in Néel and collinear configurations; TFIM uses Kramers-Wannier duality plus
finite-chain parity-sector gaps at multiple sizes.

- [ ] **Step 5: Add GLT convergence adjudication**

Require analytic stationary-point proof or declared nested grids with raw
minimum sequences and a resolution bound, reciprocal-space symmetry residuals,
direct-energy invariants, and all required directional limits. A numerically
close result at a representative point fails.
Commit these requirements canonically in each definition and policy scan. The
outer generic interpreter may apply closed residual/bound/parity proof kinds but
may not contain a Fourier-adapter ID switch, lattice formula, candidate q, or
selected-field literal outside the scientific closures.

- [ ] **Step 6: Verify GREEN and commit**

Run focused real isolation tests with `-vv`, then the full Task 7 module. Run the
protected baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add fourier recalculation adapters"
```

Run the protected baseline again.

### Task 16: Implement all four iterative-numeric adapters and independent convergence oracles

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`

Implement exactly:

| Adapter | Oracle | Selected fields |
| --- | --- | --- |
| `triangular_ising_af_entropy_quadrature` | `triangular_ising_af_entropy_series_oracle` | `residual_entropy_per_spin` |
| `kagome_ising_af_entropy_quadrature` | `kagome_ising_af_transfer_count_oracle` | `macroscopic_ground_state_degeneracy` |
| `fully_frustrated_ising_entropy_series` | `fully_frustrated_ising_transfer_oracle` | `macroscopic_ground_state_degeneracy` |
| `xx_chain_fermion_integral` | `xx_chain_dense_ed_extrapolation_oracle` | `energy_per_site` |

- [ ] **Step 1: Write RED refinement/convergence tests**

For every row require one random valid model point, at least three progressively
stronger declared controls, raw estimates at every refinement, an a priori
bound or declared stable-difference envelope, and independent oracle trend/
bound agreement. Reject repeated controls, unordered controls, one-shot values,
discarded raw samples, post-hoc thresholds, false `converged` flags, positive-
entropy booleans without a lower bound, and an oracle that copies the same
series/integrand.

- [ ] **Step 2: Verify RED**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'iterative_pair or iterative_convergence_attack'
```

- [ ] **Step 3: Implement the four refinement calculations**

1. Triangular AF Ising: composite Simpson evaluation of
   `(2/pi) integral_0^(pi/3) log(2 cos(w)) dw` at nested even interval counts;
   report all estimates and the declared Richardson/stable-difference bound.
2. Kagome AF Ising: periodic midpoint quadrature of the two-angle
   Kano-Naya logarithmic expression at nested even grids; report positivity of
   every logarithm argument, raw entropy estimates, and a positive lower bound.
   The outer validator derives macroscopic degeneracy from the bound.
3. Fully frustrated square Ising: evaluate the alternating Catalan-type entropy
   series at nested truncations, report alternating-remainder bounds, and derive
   a strictly positive lower entropy bound without returning a status literal.
4. XX chain: integrate the occupied Jordan-Wigner dispersion on nested momentum
   grids for arbitrary exchange; report raw sums, endpoint treatment, and a
   quadrature/discretization bound rather than using `-J/pi` as the adapter
   implementation.

- [ ] **Step 4: Implement independent iterative oracles**

Triangular entropy uses a separately derived Fourier/alternating series with
certified remainder; kagome entropy uses finite-width transfer matrices and
normalized ground-state counts; fully frustrated entropy uses independently
constructed finite-width transfer matrices with sector/twist handling; XX uses
finite periodic spin/fermion Hamiltonians at several sizes and bounded
energy-density extrapolation. Oracle code must not import or duplicate adapter
integrands, series helpers, or quadrature routines.

- [ ] **Step 5: Implement outer iterative convergence decisions**

Check strict control ordering, minimum sample count, all raw samples, finite
values, declared error-bound formula, final bound below the pre-frozen
threshold, oracle envelope overlap, and metamorphic exchange scaling. Positive
boolean outputs are derived only from certified lower bounds.
The nested control sequence, thresholds, proof bindings, and oracle invariant
contract are canonical scientific-policy bytes frozen before the seed. The
generic interpreter contains no adapter-ID dispatch or method-specific series/
integrand; those remain in the separately scanned scientific closures.

- [ ] **Step 6: Verify GREEN and commit**

Run focused real isolation tests with `-vv`, then the full Task 7 module. Run the
protected baseline and commit gate, then:

```bash
git add translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "feat: add converged numeric recalculation adapters"
```

Run the protected baseline again.

### Task 17: Exercise the exact 29/13 production matrix end to end

**Files:**

- Modify: `translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py`
- Modify only if a RED acceptance test exposes a defect:
  `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapters.py`
- Modify only if a RED acceptance test exposes a defect:
  `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_adapter_oracles.py`
- Modify only if a RED acceptance test exposes a defect:
  `translation-invariant-spin-model-simplifier/scripts/validation/literature_evidence_isolation.py`

- [ ] **Step 1: Add the full eligible production-matrix test**

Parameterize all 29 exact eligible rows from the independent test fixture. For
each, build a structurally valid test authority context with canary literature
fingerprints kept outside the worker, run canonical plus mandatory
counterfactual points through real production isolation, and require:

- `isolated_recomputation_succeeded`;
- exact adapter/oracle/selector identity;
- one fresh process/namespace/trace per adapter and oracle point;
- exact field map, units, uncertainty, raw convergence, backend diagnostics;
- disjoint scientific execution closures, canonical adapter/oracle definitions,
  two passing scientific-policy scans/commitments, and the complete hashed
  infrastructure closure/dependency partition;
- post-execution snapshot revalidation;
- complete evidence validation and reproducible disclosed seed;
- no expected-output fixture or authority-only value in capsule/request/mounts;
- no Task 7 strict-match or literature-comparison field.

Name the test:

```python
@pytest.mark.parametrize("row", EXPECTED_ELIGIBLE_ROWS, ids=lambda row: row.adapter_id)
def test_every_eligible_adapter_produces_complete_isolated_evidence(row, tmp_path): ...
```

- [ ] **Step 2: Add the full source-parse-only anti-promotion test**

Parameterize all 13 exact rows. Calling the coordinator must return
`adapter_ineligible` with the mandated closed reason before closure, snapshot,
seed, or execution. Mutation of the production catalog in a test-local copy
must not bypass the absence of a definition/oracle/evidence bundle.

- [ ] **Step 3: Add exact aggregate and zero-skip assertions**

Independently assert 42 unique benchmark IDs, 29 unique eligible adapter IDs,
29 unique oracle IDs, 13 exact source-only reasons, and exact 7/4/18 size-policy
membership. Use pytest's terminal report hook or a subprocess invocation to
prove mandatory preflight/isolation/matrix tests have zero skipped and zero
xfailed outcomes.

- [ ] **Step 4: Run acceptance tests and expect GREEN**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q -k 'every_eligible or source_parse_only or aggregate or mandatory_tests_have_zero_skips' -vv
```

Expected: all selected tests pass, with `0 skipped` and `0 xfailed`.

- [ ] **Step 5: Run the complete Task 7 module**

```bash
cd translation-invariant-spin-model-simplifier
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q
```

Expected: PASS, no skipped mandatory isolation tests.

- [ ] **Step 6: Commit the acceptance matrix**

Run the protected baseline and commit gate. Stage the test plus only production
files actually changed in response to a failing acceptance test. Confirm the
cached path list explicitly, then:

```bash
git add translation-invariant-spin-model-simplifier/tests/test_literature_evidence_adapters.py
git commit -m "test: cover every isolated recalculation route"
```

If a production file changed, add its exact path to the `git add` command and
record why in the implementation checkpoint. Run the protected baseline again.

### Task 18: Run complete verification and independent non-Fast reviews

**Files:**

- No planned file edits. Any review fix returns to the owning earlier task,
  begins with a new failing regression test, and receives its own exact-path
  commit.

- [ ] **Step 1: Re-run the protected baseline before verification**

From the worktree root:

```bash
sed -n '174,306p' docs/superpowers/plans/2026-07-15-fail-closed-literature-reproduction-evidence-implementation.md | sed '/^```/d' | bash
```

Require the exact 471/143/6 JSON result and no allowed source-cache targets.

- [ ] **Step 2: Compile all four Task 7 files into a retained external cache**

From the project root:

```bash
task7_pycache="$(mktemp -d /tmp/literature-evidence-task7-pycache.XXXXXXXX)"
realpath -- "$task7_pycache"
PYTHONPYCACHEPREFIX="$task7_pycache" PYTHONDONTWRITEBYTECODE=1 \
  python -m py_compile \
    scripts/validation/literature_evidence_adapters.py \
    scripts/validation/literature_evidence_adapter_oracles.py \
    scripts/validation/literature_evidence_isolation.py \
    tests/test_literature_evidence_adapters.py
```

Expected: exit 0, printed retained `/tmp` path, and no repository bytecode.

- [ ] **Step 3: Run focused lint**

```bash
PYTHONDONTWRITEBYTECODE=1 python -m flake8 \
  scripts/validation/literature_evidence_adapters.py \
  scripts/validation/literature_evidence_adapter_oracles.py \
  scripts/validation/literature_evidence_isolation.py \
  tests/test_literature_evidence_adapters.py \
  --select=E9,F63,F7,F82
```

Expected: exit 0 with no output.

- [ ] **Step 4: Run the full Task 7 suite with mandatory real isolation**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts \
  python -m pytest -p no:cacheprovider tests/test_literature_evidence_adapters.py -q
```

Expected: PASS with zero skipped/xfail mandatory tests, all 29 successful
production-style evidence bundles, and all adversarial cases rejected.

- [ ] **Step 5: Run all relevant regressions in a clean process**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts \
  python -m pytest -p no:cacheprovider -q \
    tests/test_literature_evidence_schema.py \
    tests/test_literature_evidence_sources.py \
    tests/test_literature_evidence_inventory.py \
    tests/test_literature_evidence_parsers.py \
    tests/test_literature_spin_model_crosschecks.py \
    tests/test_literature_runtime_evidence.py \
    tests/test_literature_reproduction_audit.py
```

Expected: PASS. The protected user-owned PDF test is intentionally excluded and
must remain byte-identical.

- [ ] **Step 6: Inspect repository hygiene and exact commit scopes**

From the worktree root:

```bash
git diff --check
git status --short
task7_implementation_base="$(
  git log -1 --format=%H -- \
    docs/superpowers/plans/2026-08-11-isolated-literature-recalculation-adapters-implementation.md
)"
test -n "$task7_implementation_base"
git log --oneline --name-status 3bc8704^.."$task7_implementation_base"
git log --oneline --name-status "$task7_implementation_base"..HEAD
```

Then run the exact read-only repository-cache preservation command in
“Command conventions and commit gate.” Expected: the pinned 11 directories,
178 entries, and SHA-256
`f66b98ea9404df076be51bd2e219f8fbf7a82e419c4fc4f27c32e6177789f620`.

Expected: no diff-check errors; only the six known protected WIP paths remain in
status. The first log range contains only the reviewed specification path and
this implementation-plan path across specification/plan commits; the second
range contains only the three new production modules and one new test module
across Task 7 implementation commits. The plan path must not occur in the
second range. No repository cache entry is added,
removed, or changed; the eleven pre-existing ignored directories remain.

- [ ] **Step 7: Dispatch an independent specification-compliance reviewer**

Use a fresh subagent configured explicitly as `gpt-5.6-sol` with
`reasoning_effort=xhigh`; Fast mode is forbidden. Provide only the design spec,
implementation plan, Task 7 commit range, four Task 7 paths, and verification
outputs. Ask it to check every acceptance criterion, exact 42/29/13 and 7/4/18
mapping, all security controls, real scientific methods, oracle independence,
complete infrastructure-root/dependency-partition coverage, frozen canonical
scientific-policy commitments and generic proof interpretation, and the Task8
authority boundary. It is read-only.

If it finds a blocking issue, add a RED regression, implement the narrow fix,
run affected/full tests, commit exact paths, rerun baseline, and redispatch a
fresh whole-scope spec reviewer. Do not accept a count-only or sampled review.

- [ ] **Step 8: Dispatch an independent code-quality/security reviewer**

Only after spec approval, use another fresh explicit `gpt-5.6-sol`, xhigh,
non-Fast subagent. Review the full diff for correctness, fail-closed behavior,
namespace/tracer lifecycle, TOCTOU/path/FD handling, resource limits, trace
parser completeness, numerical stability, scientific independence, test
strength, and maintainability. Resolve blocking issues by the same RED/fix/
verify/exact-commit loop and obtain final approval.

- [ ] **Step 9: Run the final immutable gate**

After both approvals, rerun Steps 1, 3, 4, 5, and 6. Then run:

```bash
git diff --cached --name-status
git status --short
```

Expected: empty index; only the six protected WIP paths are reported; protected
baseline still reports 471 entries, 143 roots, and six files.

- [ ] **Step 10: Record the Task 7 handoff without overclaiming**

Report commits, exact test counts, preflight evidence, 29 successful adapter
bundles, 13 enforced source-parse-only rows, regression results, and both review
approvals. State explicitly that Task 7 proves isolated local recalculation
evidence only; Task 8 must authenticate `AdapterAuthorityContext`, independently
compare source/registry/local operands, and issue any strict literature verdict.

## Execution discipline

Implementation uses `superpowers:subagent-driven-development`. Each numbered
task gets a fresh implementation subagent followed by a specification-compliance
review and then a code-quality review before moving to the next task. Every
subagent is explicitly launched as `gpt-5.6-sol` with
`reasoning_effort=xhigh`; **Fast mode is forbidden for all implementers and
reviewers**. Agents receive precise task context rather than inherited session
history and may edit only the task's listed paths.

Every implementation task follows `superpowers:test-driven-development`: write
the named failing test, run it and inspect the intended failure, implement the
minimum real behavior, rerun focused tests, then run the full Task 7 module.
Before any claim that a task or Task 7 is complete, apply
`superpowers:verification-before-completion` and cite fresh command output.

Do not begin Task 8 in the same commit as Task 7. The accepted Task 7 evidence
API is the reviewed handoff boundary for the separate Task 8 design and plan.
