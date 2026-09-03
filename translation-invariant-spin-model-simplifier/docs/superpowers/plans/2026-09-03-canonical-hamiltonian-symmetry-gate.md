# Canonical Hamiltonian Symmetry Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one canonical, arbitrary-arity Hamiltonian symmetry gate that validates strictly by default, optionally repairs by finite space-group averaging, and supplies a validated model to the existing solver stack without duplicating orbit or Fourier backends.

**Architecture:** Normalize lattice-term payloads into a deterministic coefficient map, apply structural operations through a shared geometry/operator action, and run either validate-only or project-and-revalidate before public solver routing. Extract the legacy axial-vector tensor rotation into this shared layer; preserve low-level solver APIs while enforcing a hash-bound validation stamp in public pipelines.

**Tech Stack:** Python 3, NumPy, SciPy, spglib, pytest, existing lattice-term contract and classical/LSWT/GSWT adapters, Slurm on `login002`.

## Global Constraints

- `symmetry_repair` is a boolean and defaults to `false` in every entry point.
- The first target is the structural space group; the implementation must never silently lower the target symmetry and continue.
- Strict validation failure stops before LT, classical, LSWT, or GSWT execution.
- Repair is the finite-group average of the complete canonical coefficient map and must pass a post-repair validation.
- Input files and input payloads remain unchanged; reports preserve input and solver-model hashes.
- Canonical terms support arbitrary arity. Unsupported operator actions or solver term families fail explicitly instead of being ignored.
- Reuse `bond_orbits.py`, `lattice_structure_builder.py`, `lt_fourier_exchange.py`, generalized/certified GLT, and existing LSWT/GSWT backends.
- Do not run pytest, doctest, unittest, build-time test commands, or executable test scripts locally.
- Every test invocation is submitted as a Slurm job after `ssh login002`; retain job ID, terminal state, exit code, and log path.
- Remote environment verified on 2026-09-03: default partition `regular`, Python 3.9.13, pytest 7.2.0, NumPy 1.23.5, SciPy 1.13.1, spglib 2.7.0, and the worktree is visible at the same absolute path.

## Remote Test Protocol

Use this exact pattern for every red/green verification, replacing the job name and pytest selector. The commands are executed from the development host, but pytest itself runs only inside the submitted Slurm job.

```bash
symmetry_worktree=/data/work/zhli/soft/Design_Mott_Materials/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier
symmetry_log_root=/data/work/zhli/job-logs/canonical-hamiltonian-symmetry
ssh login002 "mkdir -p '$symmetry_log_root'"
symmetry_job_id=$(ssh login002 "sbatch --parsable --partition=regular --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=4G --time=00:15:00 --job-name=<JOB_NAME> --chdir='$symmetry_worktree' --output='$symmetry_log_root/<JOB_NAME>-%j.out' --wrap='PYTHONPATH=scripts python3 -m pytest <PYTEST_SELECTOR> -v'")
ssh login002 "squeue -j '$symmetry_job_id' -h -o '%T'"
ssh login002 "sacct -j '$symmetry_job_id' --format=JobID,State,ExitCode,Elapsed -n -P"
ssh login002 "sed -n '1,260p' '$symmetry_log_root/<JOB_NAME>-$symmetry_job_id.out'"
```

If `sacct` has not recorded a terminal state, poll with a non-blocking `squeue` call. Do not run an interactive fallback test on `login002` or locally.

---

### Task 1: Deterministic Canonical Term and Coefficient Map

**Files:**
- Create: `scripts/common/canonical_hamiltonian.py`
- Create: `tests/test_canonical_hamiltonian.py`
- Modify: `scripts/common/lattice_term_contract.py`

**Interfaces:**
- Consumes: a validated `lattice-term-contract/v1` mapping and its `parameters` mapping.
- Produces: `compile_canonical_hamiltonian(payload: Mapping) -> dict`, `canonical_term_key(term: Mapping) -> tuple`, `canonicalize_cluster(cluster, family) -> dict`, `coefficient_map(model) -> dict`, and `canonical_model_hash(model) -> str`.

- [ ] **Step 1: Write failing schema and determinism tests**

Create fixtures for an explicit two-site term, an `attach_to.orientation=representative` term, and an arity-three oriented term. Assert that compilation does not mutate the input, makes the first cluster translation zero, preserves provenance, resolves structured real/complex coefficients, and produces the same hash after input-term reordering.

```python
def test_compile_canonical_hamiltonian_is_order_independent():
    left = compile_canonical_hamiltonian(lattice_term_payload(term_order=("x", "y")))
    right = compile_canonical_hamiltonian(lattice_term_payload(term_order=("y", "x")))
    assert coefficient_map(left) == coefficient_map(right)
    assert canonical_model_hash(left) == canonical_model_hash(right)


def test_oriented_three_body_term_keeps_orientation_sector():
    model = compile_canonical_hamiltonian(chirality_payload())
    term = model["terms"][0]
    assert term["arity"] == 3
    assert term["orientation_sector"] == "positive"
```

- [ ] **Step 2: Submit the remote red test**

Use the Remote Test Protocol with job name `sym-ir-red` and selector `tests/test_canonical_hamiltonian.py`. Expected terminal result: `FAILED`, with import or missing-function failures for `common.canonical_hamiltonian`.

- [ ] **Step 3: Implement the canonical IR**

Implement immutable-by-copy normalization. Canonical cluster translation subtracts the first site's cell vector. Family adapters, not generic sorting, decide allowed permutations. Serialize canonical keys to JSON-compatible lists for reports but use tuples internally.

```python
def compile_canonical_hamiltonian(payload: Mapping) -> dict:
    terms = []
    for collection, arity_hint in (
        ("site_terms", 1),
        ("bond_terms", 2),
        ("higher_body_terms", None),
    ):
        for source in payload["term_attachments"].get(collection, []):
            terms.append(_compile_term(source, payload, arity_hint=arity_hint))
    terms.sort(key=canonical_term_key)
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": deepcopy(payload["lattice_structure"]),
        "local_hilbert": deepcopy(payload["local_hilbert"]),
        "symmetry": deepcopy(payload["symmetry"]),
        "terms": terms,
        "source_schema_version": payload.get("schema_version"),
    }
```

Use canonical JSON with sorted keys and compact separators for SHA-256. Exclude runtime stamps but include every physical coefficient, cluster, operator family, frame, and symmetry operation in the hash.

- [ ] **Step 4: Extend contract validation for arbitrary arity metadata**

Validate that every `higher_body_term` has an integer `arity >= 3`, cluster length equal to arity, nonempty `operator_family`, `permutation_action`, and `adjoint_action`. Preserve existing accepted payloads by applying these requirements only when a higher-body term participates in the new symmetry gate.

- [ ] **Step 5: Submit the remote green test**

Use job name `sym-ir-green` and selector `tests/test_canonical_hamiltonian.py tests/test_lattice_structure_builder.py`. Expected: all selected tests pass.

- [ ] **Step 6: Commit the independently testable IR**

```bash
git add scripts/common/canonical_hamiltonian.py scripts/common/lattice_term_contract.py tests/test_canonical_hamiltonian.py
git commit -m "feat: add canonical Hamiltonian coefficient map"
```

### Task 2: Shared Space-Group Geometry and Spin Representation

**Files:**
- Create: `scripts/common/hamiltonian_symmetry_action.py`
- Create: `tests/test_hamiltonian_symmetry_action.py`
- Modify: `scripts/common/lattice_structure_builder.py`
- Modify: `scripts/classical/build_spin_only_solver_payload.py`

**Interfaces:**
- Consumes: canonical term records, lattice vectors, basis positions, structural operation records, and optional local frames/operator representations.
- Produces: `cartesian_rotation(lattice_vectors, fractional_rotation) -> np.ndarray`, `axial_spin_rotation(...) -> np.ndarray`, `map_cluster(operation, cluster, lattice_structure) -> list[dict]`, and `transform_term(term, operation, context) -> list[dict]`.

- [ ] **Step 1: Write failing proper/improper/local-frame tests**

Cover a proper 90-degree rotation, inversion, mirror, a two-sublattice mapping with a nonzero cell offset, and two distinct local frames.

```python
def test_global_anisotropic_tensor_rotates_with_axial_spin_action():
    transformed = transform_term(anisotropic_bond_term(), c4_operation(), square_context())
    expected = D @ J @ D.T
    np.testing.assert_allclose(transformed[0]["coefficient"], expected)


def test_local_frame_action_uses_source_and_target_frames():
    transformed = transform_term(local_frame_bond(), operation(), framed_context())
    np.testing.assert_allclose(transformed[0]["left_action"], np.linalg.inv(F1) @ D @ F0)
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-action-red` and selector `tests/test_hamiltonian_symmetry_action.py`. Expected: missing module/functions.

- [ ] **Step 3: Extract Cartesian axial rotation without duplicating it**

Move the numerical logic currently implemented by `_cartesian_spin_rotation_from_fractional` to the common module. Keep a private compatibility wrapper in `build_spin_only_solver_payload.py` if existing callers or tests import the old private name.

```python
def axial_spin_rotation(lattice_vectors, fractional_rotation):
    q = cartesian_rotation(lattice_vectors, fractional_rotation)
    return float(np.linalg.det(q)) * q
```

Use a polar/SVD cleanup only to remove floating roundoff from the Cartesian orthogonal matrix; reject a genuinely non-orthogonal result.

- [ ] **Step 4: Implement exact site and cluster mapping**

Reuse the same spglib-derived operations and basis matching tolerance as `bond_orbits.py`. Return mapped site indexes plus integer translations. Fail with `canonical-term-identity-unresolved` when a magnetic site does not map into the magnetic basis.

- [ ] **Step 5: Implement onsite and bilinear transformations**

For global physical spin use `D_left @ J @ D_right.T`; for reverse canonical orientation apply conjugate transpose. For local frames use `inv(F_mapped) @ D @ F_source` on each tensor leg.

- [ ] **Step 6: Make the legacy builder call the shared implementation**

Replace its independent axial-rotation body and symmetry-rotated-matrix loop with calls into `hamiltonian_symmetry_action.py`. Preserve output schemas and bond ordering so symmetric legacy payloads are regression-stable.

- [ ] **Step 7: Submit remote green and regression tests**

Use job name `sym-action-green` and selector `tests/test_hamiltonian_symmetry_action.py tests/test_lattice_structure_builder.py tests/test_literature_generic_workflow.py`. Expected: all selected tests pass.

- [ ] **Step 8: Commit shared symmetry action**

```bash
git add scripts/common/hamiltonian_symmetry_action.py scripts/common/lattice_structure_builder.py scripts/classical/build_spin_only_solver_payload.py tests/test_hamiltonian_symmetry_action.py
git commit -m "refactor: share space-group tensor transformations"
```

### Task 3: Arbitrary-Arity Operator-Family Actions

**Files:**
- Create: `scripts/common/operator_family_symmetry.py`
- Create: `tests/test_operator_family_symmetry.py`
- Modify: `scripts/common/hamiltonian_symmetry_action.py`
- Modify: `scripts/common/canonical_hamiltonian.py`

**Interfaces:**
- Consumes: operator-family name, local adjoint matrices, mapped cluster permutation, coefficient tensor, and adjoint metadata.
- Produces: `registered_operator_families() -> dict`, `transform_operator_coefficient(term, leg_actions, permutation) -> object`, and family-specific canonicalization metadata.

- [ ] **Step 1: Write failing arbitrary-arity and permutation tests**

Cover generic rank-k tensor leg actions with `numpy.einsum`, compact biquadratic invariance, scalar-chirality permutation parity, and cyclic ring reversal.

```python
def test_scalar_chirality_changes_sign_under_odd_permutation():
    result = canonicalize_family_term(chirality_term((0, 2, 1)))
    assert result["coefficient"] == -chirality_term((0, 1, 2))["coefficient"]


def test_group_action_composes_for_generic_four_body_tensor():
    sequential = transform_term(transform_term(term, g2, ctx)[0], g1, ctx)
    composed = transform_term(term, compose(g1, g2), ctx)
    assert_coefficients_close(sequential, composed)
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-family-red` and selector `tests/test_operator_family_symmetry.py`. Expected: missing family registry and transformations.

- [ ] **Step 3: Implement the registry and generic tensor action**

Each family record declares allowed cluster permutations, coefficient action, orientation sectors, adjoint action, and supported coordinate conventions. Unknown families raise `symmetry-projection-unsupported-term`.

```python
@dataclass(frozen=True)
class OperatorFamilyAction:
    name: str
    canonicalize: Callable[[dict], dict]
    transform_coefficient: Callable[[dict, Sequence[np.ndarray], Sequence[int]], object]
    adjoint: Callable[[dict], dict]
```

The generic tensor action applies one representation matrix per operator index and then the canonicalization permutation. It must support real and complex tensors.

- [ ] **Step 4: Implement compact physical families**

Implement spin-vector, quadratic-spin-tensor, bilinear-exchange, biquadratic, scalar-chirality, and cyclic-ring records. The compact families must round-trip to deterministic canonical coefficients; no solver expansion occurs here.

- [ ] **Step 5: Submit the remote green test**

Use job name `sym-family-green` and selector `tests/test_operator_family_symmetry.py tests/test_canonical_hamiltonian.py tests/test_hamiltonian_symmetry_action.py`. Expected: all selected tests pass.

- [ ] **Step 6: Commit arbitrary-arity actions**

```bash
git add scripts/common/operator_family_symmetry.py scripts/common/hamiltonian_symmetry_action.py scripts/common/canonical_hamiltonian.py tests/test_operator_family_symmetry.py
git commit -m "feat: add many-body symmetry actions"
```

### Task 4: Strict Validation, Diagnostic Subgroup, and Group-Average Repair

**Files:**
- Create: `scripts/common/hamiltonian_symmetry_gate.py`
- Create: `tests/test_hamiltonian_symmetry_gate.py`

**Interfaces:**
- Consumes: `canonical-hamiltonian/v1` and `SymmetryGateRequest`.
- Produces: `validate_hamiltonian_symmetry(model, request) -> dict`, `project_hamiltonian_symmetry(model, request) -> dict`, and `run_hamiltonian_symmetry_gate(model, request) -> dict`.

- [ ] **Step 1: Write failing strict/no-op/repair tests**

Test symmetric pass, asymmetric strict failure, missing orbit partner, inconsistent partner, forbidden DM component, unknown structural symmetry, missing pseudospin representation, post-repair validation, and input immutability.

```python
def test_strict_failure_blocks_with_diagnostics():
    result = run_hamiltonian_symmetry_gate(broken_model(), SymmetryGateRequest(repair=False))
    assert result["status"] == "error"
    assert result["completion"]["reason"] == "hamiltonian-symmetry-validation-failed"
    assert result["solver_execution"] == {"started": False, "backends_run": []}
    assert result["symmetry_validation"]["failed_operations"]


def test_projection_is_invariant_and_idempotent():
    repaired = run_hamiltonian_symmetry_gate(broken_model(), SymmetryGateRequest(repair=True))
    second = run_hamiltonian_symmetry_gate(repaired["solver_model"], SymmetryGateRequest(repair=True))
    assert coefficient_map(repaired["solver_model"]) == coefficient_map(second["solver_model"])
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-gate-red` and selector `tests/test_hamiltonian_symmetry_gate.py`. Expected: missing gate module/functions.

- [ ] **Step 3: Implement request and error contracts**

```python
@dataclass(frozen=True)
class SymmetryGateRequest:
    repair: bool = False
    absolute_tolerance: float = 1.0e-10
    relative_tolerance: float = 1.0e-8
    cleanup_tolerance: float = 1.0e-12
```

Define `HamiltonianSymmetryError(code, report)` for structural-symmetry, representation, Hermiticity, identity, unsupported-term, validation, and postcheck failures. The public result serializes errors instead of exposing an unstructured traceback.

- [ ] **Step 4: Implement complete coefficient-map validation**

Transform the whole model under each operation, union original and transformed keys, treat missing coefficients as zero, and calculate infinity/Frobenius residuals. Store the worst key, source term, transformed value, missing partners, and forbidden components.

- [ ] **Step 5: Verify the diagnostic subgroup**

Build a multiplication table over the discrete structural operations by matching composed rotations/translations modulo lattice translations. Call passing operations a subgroup only when identity, closure, and inverses are verified; otherwise return `candidate-operations-only`.

- [ ] **Step 6: Implement finite-group averaging**

Accumulate every transformed full coefficient map, divide by the operation count, apply cleanup tolerance, preserve Hermiticity, calculate added/modified/zeroed/unchanged changes, and re-run validation. Set `status=repaired` only when the input failed and coefficients materially changed; otherwise `already-symmetric`.

- [ ] **Step 7: Add deterministic hashes and validation stamp**

Bind input hash, solver hash, target group hash, tolerances, and repaired state. Include `hamiltonian-symmetry-repaired` only for material repair. A helper `require_current_symmetry_stamp(model, stamp)` rejects hash mismatch.

- [ ] **Step 8: Submit remote green/property tests**

Use job name `sym-gate-green` and selector `tests/test_hamiltonian_symmetry_gate.py tests/test_operator_family_symmetry.py tests/test_hamiltonian_symmetry_action.py`. Expected: all selected tests pass, including identity, composition, inverse, invariance, idempotence, Hermiticity, and input-order properties.

- [ ] **Step 9: Commit the gate**

```bash
git add scripts/common/hamiltonian_symmetry_gate.py tests/test_hamiltonian_symmetry_gate.py
git commit -m "feat: validate and repair Hamiltonian symmetry"
```

### Task 5: Canonical Contract and Input-Pipeline Integration

**Files:**
- Modify: `scripts/input/normalize_input.py`
- Modify: `scripts/common/lattice_term_contract.py`
- Modify: `scripts/common/term_attachment_builder.py`
- Modify: `scripts/common/realize_pseudospin_bond_blocks.py`
- Modify: `scripts/common/canonicalize_pseudospin_bond_orbits.py`
- Create: `tests/test_hamiltonian_symmetry_pipeline.py`
- Modify: `tests/test_normalize_input.py`

**Interfaces:**
- Consumes: all current generic-model inputs and existing representative markers.
- Produces: canonical request field `solver_request.symmetry_repair`, the gate result, and one validated canonical model used by downstream routing.

- [ ] **Step 1: Write failing normalization and path-equivalence tests**

Assert default false, explicit true preservation, representative expansion semantics, explicit missing-partner semantics, and equivalent coefficient maps from legacy/canonical/pseudospin inputs.

```python
def test_normalization_defaults_symmetry_repair_to_false():
    payload = normalize_input(minimal_source_model())
    assert payload["solver_request"]["symmetry_repair"] is False


def test_three_input_paths_compile_to_same_rotated_exchange_orbit():
    models = [compile_path(source) for source in equivalent_input_paths()]
    assert coefficient_map(models[0]) == coefficient_map(models[1]) == coefficient_map(models[2])
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-pipeline-red` and selector `tests/test_hamiltonian_symmetry_pipeline.py tests/test_normalize_input.py`. Expected: new symmetry fields/path equivalence fail.

- [ ] **Step 3: Add the canonical request field**

Update `_canonical_solver_request` to emit `symmetry_repair=False` unless explicitly provided. Reject non-boolean values with `invalid-symmetry-repair-flag`. Preserve the tolerance defaults from the spec.

- [ ] **Step 4: Preserve representative versus explicit semantics**

Keep current `attach_to.orientation=representative` and orbit-map inputs as explicit expansion requests. Plain term lists remain complete explicit Hamiltonians. Do not infer intent from term count.

- [ ] **Step 5: Route pseudospin realization through shared transformations**

Replace matrix-copy orbit expansion when a valid operator representation is available. For pair matrices without a declared pseudospin action, return `symmetry-representation-unavailable`; do not assume physical-spin axial behavior.

- [ ] **Step 6: Submit remote green integration tests**

Use job name `sym-pipeline-green` and selector `tests/test_hamiltonian_symmetry_pipeline.py tests/test_normalize_input.py tests/test_lattice_structure_builder.py tests/test_literature_generic_workflow.py`. Expected: all selected tests pass.

- [ ] **Step 7: Commit pipeline integration**

```bash
git add scripts/input/normalize_input.py scripts/common/lattice_term_contract.py scripts/common/term_attachment_builder.py scripts/common/realize_pseudospin_bond_blocks.py scripts/common/canonicalize_pseudospin_bond_orbits.py tests/test_hamiltonian_symmetry_pipeline.py tests/test_normalize_input.py
git commit -m "feat: gate canonical models on space-group symmetry"
```

### Task 6: CLI Flag, Pre-Solver Blocking, and Result Provenance

**Files:**
- Modify: `scripts/cli/solve_pseudospin_orbital_pipeline.py`
- Modify: `scripts/cli/solve_cpn_payload_pipeline.py`
- Modify: `scripts/cli/simplify_text_input.py`
- Modify: `scripts/cli/render_simplified_model_report.py`
- Create: `tests/test_hamiltonian_symmetry_cli.py`
- Modify: `tests/test_glt_solver_mode_selection.py`

**Interfaces:**
- Consumes: CLI `--symmetry-repair` or Python `symmetry_repair: bool`.
- Produces: strict failure before solver mocks, repaired-model routing, structured warning/report, and model-hash-bound solver results.

- [ ] **Step 1: Write failing parser and solver-block tests**

```python
def test_cli_defaults_to_strict_symmetry_validation():
    args = parse_args(["--parsed-payload", "model.json", "--output-dir", "out"])
    assert args.symmetry_repair is False


def test_strict_failure_invokes_no_solver(monkeypatch):
    solver = monkeypatch_solver(monkeypatch)
    result = solve_from_parsed_payload(asymmetric_payload(), symmetry_repair=False)
    assert result["completion"]["reason"] == "hamiltonian-symmetry-validation-failed"
    solver.assert_not_called()
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-cli-red` and selector `tests/test_hamiltonian_symmetry_cli.py tests/test_glt_solver_mode_selection.py`. Expected: missing flag and gate calls.

- [ ] **Step 3: Add one consistent public flag**

Add `parser.add_argument("--symmetry-repair", action="store_true")` to relevant solver entry points and pass it unchanged into normalized `solver_request`. Do not add a conflicting default-on alias.

- [ ] **Step 4: Place the gate before all solver selection/execution**

Compile, gate, and only then call `select_solver_capability` or direct solver helpers. Return structured failure without invoking classical, GLT, LSWT, GSWT, or thermodynamic runners.

- [ ] **Step 5: Bind reports and warnings to the solver model**

Render target group, diagnostic subgroup, failed operations, repair changes, input hash, solver hash, and the `--symmetry-repair` suggestion. Every downstream result stores `solver_model_hash` from the validation stamp.

- [ ] **Step 6: Submit remote green CLI tests**

Use job name `sym-cli-green` and selector `tests/test_hamiltonian_symmetry_cli.py tests/test_glt_solver_mode_selection.py tests/test_human_input_fallback_wrappers.py`. Expected: all selected tests pass.

- [ ] **Step 7: Commit public workflow integration**

```bash
git add scripts/cli/solve_pseudospin_orbital_pipeline.py scripts/cli/solve_cpn_payload_pipeline.py scripts/cli/simplify_text_input.py scripts/cli/render_simplified_model_report.py tests/test_hamiltonian_symmetry_cli.py tests/test_glt_solver_mode_selection.py
git commit -m "feat: expose strict Hamiltonian symmetry gate"
```

### Task 7: Solver Capability Enforcement and Fourier Reuse

**Files:**
- Modify: `scripts/common/solver_capability_registry.py`
- Modify: `scripts/common/model_analysis.py`
- Modify: `scripts/classical/build_spin_only_solver_payload.py`
- Create: `tests/test_hamiltonian_solver_routing.py`
- Modify: `tests/test_generic_model_analysis.py`

**Interfaces:**
- Consumes: validated canonical model plus validation stamp.
- Produces: explicit `solver-capability-mismatch` for unsupported complete term sets and bilinear Fourier analysis through `classical.lt_fourier_exchange.fourier_exchange_matrix`.

- [ ] **Step 1: Write failing no-truncation and Fourier-equivalence tests**

```python
def test_bilinear_solver_rejects_validated_ring_exchange():
    with pytest.raises(SolverCapabilityError, match="solver-capability-mismatch"):
        select_solver_capability(validated_ring_model())


def test_model_analysis_uses_existing_tensor_fourier_kernel(monkeypatch):
    kernel = monkeypatch_existing_fourier_kernel(monkeypatch)
    run_model_analysis(anisotropic_model(), fourier_request())
    assert kernel.call_count == len(fourier_request()["q_points"])
```

- [ ] **Step 2: Submit the remote red test**

Use job name `sym-route-red` and selector `tests/test_hamiltonian_solver_routing.py tests/test_generic_model_analysis.py`. Expected: capability code mismatch and simplified Fourier path still bypassing the existing kernel.

- [ ] **Step 3: Enforce complete-term-set capability checks**

Check body order and every `payload.kind`. Replace ambiguous `unsupported-term-payload`/`no-solver-capability` outcomes for a validated but unsupported Hamiltonian with `solver-capability-mismatch` plus unsupported term refs and families.

- [ ] **Step 4: Adapt model analysis to the existing Fourier kernel**

Compile bilinear canonical terms into the established spin-only `bonds` payload and call `fourier_exchange_matrix` for each requested q. Preserve existing scalar-analysis response fields while adding `matrix_size`, tensor eigenvectors/projectors, and backend provenance. Do not duplicate phase or Hermitian-completion logic.

- [ ] **Step 5: Require a current stamp in public adapters**

Public adapters validate the model hash against the stamp before routing. Private low-level numerical functions remain callable without a stamp for backward compatibility.

- [ ] **Step 6: Submit remote green routing tests**

Use job name `sym-route-green` and selector `tests/test_hamiltonian_solver_routing.py tests/test_generic_model_analysis.py tests/test_hamiltonian_symmetry_pipeline.py`. Expected: all selected tests pass.

- [ ] **Step 7: Commit solver routing and reuse**

```bash
git add scripts/common/solver_capability_registry.py scripts/common/model_analysis.py scripts/classical/build_spin_only_solver_payload.py tests/test_hamiltonian_solver_routing.py tests/test_generic_model_analysis.py
git commit -m "refactor: route validated models to existing Fourier backend"
```

### Task 8: Remote Regression Suite, Documentation, and Completion Audit

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `reference/` files that document structured input and solver routing, selected by `rg -n "solver_request|classical_ground_state|symmetry" reference SKILL.md`
- Modify: `session-memory/sessions/canonical-hamiltonian-symmetry-2026-09-03-1311.md` locally (ignored project memory)
- Modify: `session-memory/index/canonical-hamiltonian-symmetry.md` locally (ignored project memory)

**Interfaces:**
- Consumes: completed implementation and all prior remote job evidence.
- Produces: documented flag/error semantics, full remote verification evidence, and a requirement-by-requirement completion audit.

- [ ] **Step 1: Document strict default and opt-in repair**

Add examples showing default failure, `--symmetry-repair`, the fact that input files are unchanged, the repaired-model warning, and `solver-capability-mismatch` for unsupported higher-body terms. State that physical pseudospin/orbital representations must be supplied and are not guessed.

- [ ] **Step 2: Submit the focused feature suite**

Use job name `sym-feature-full` and selector:

```text
tests/test_canonical_hamiltonian.py
tests/test_hamiltonian_symmetry_action.py
tests/test_operator_family_symmetry.py
tests/test_hamiltonian_symmetry_gate.py
tests/test_hamiltonian_symmetry_pipeline.py
tests/test_hamiltonian_symmetry_cli.py
tests/test_hamiltonian_solver_routing.py
tests/test_lattice_structure_builder.py
tests/test_normalize_input.py
tests/test_generic_model_analysis.py
tests/test_glt_solver_mode_selection.py
```

Expected: all selected tests pass with Slurm state `COMPLETED` and exit code `0:0`.

- [ ] **Step 3: Submit the full repository suite**

Use job name `sym-repo-full`, `--time=03:00:00`, `--mem=12G`, and selector `tests`. Expected: all tests pass. If pre-existing failures remain, verify them against the checkpoint baseline, report them separately, and do not claim a fully green repository. Any new or changed failure is a regression and must be fixed before completion.

- [ ] **Step 4: Run a remote CLI smoke job**

Submit a job that creates temporary input/output only inside `$SLURM_TMPDIR`, runs one asymmetric input in strict mode and verifies nonzero/structured failure, then runs it with `--symmetry-repair` and verifies the repaired warning plus solver-model hash. The job must not modify a repository input fixture.

- [ ] **Step 5: Audit every spec requirement against evidence**

Record, for each requirement in Sections 2–13 of the design spec, the implementing file/function and the remote test/job proving it. Treat missing evidence as incomplete work. Explicitly distinguish GLT-relaxation certification from fixed-length classical certification.

- [ ] **Step 6: Update session project memory**

Append a compressed entry with commit IDs, changed core paths, remote Slurm job IDs/states/logs, remaining known baseline failures, and next focus. Refresh the index to keep only the latest five sessions.

- [ ] **Step 7: Verify diff and commit documentation**

Run non-test repository checks locally only for VCS state:

```bash
git diff --check
git status --short
```

Then commit documentation and any final verified fixes:

```bash
git add README.md SKILL.md reference tests scripts
git commit -m "docs: describe Hamiltonian symmetry validation"
```

- [ ] **Step 8: Final branch audit**

Verify the exact commit list, clean tracked worktree, remote job evidence, and absence of required work. Do not mark the goal complete unless every explicit requirement is implemented and supported by current authoritative evidence.
