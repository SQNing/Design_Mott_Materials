# FeI2 Document-Reader Classical Bridge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a contract-first bridge that turns a selected spin-only readable exchange block from the document-reader `effective_model.json` into solver-ready `bonds`, so FeI2 can reach a reproducible classical-solver smoke run without hand-written payload assembly.

**Architecture:** Introduce a dedicated builder that accepts the document-reader simplification payload, selects one supported readable spin-only block for the chosen family, reconstructs one canonical representative bond from lattice shell geometry, and emits a minimal classical payload with provenance. Integrate that builder into the document-reader pipeline behind explicit opt-in flags so the current simplification-only flow stays stable while FeI2 can optionally emit bridge artifacts and run the classical solver in the same command.

**Tech Stack:** Python 3, existing document-reader CLI, readable-block simplification output, classical solver layer, `unittest`/`pytest`

---

## Scope And Done-When

This plan is intentionally narrower than a full physics-product workflow.

Done means all of the following are true:

- A fresh FeI2 document-reader run with selected family `2a'` can automatically emit a solver payload JSON without any hand-edited bond matrix or translation vector.
- That emitted payload can be fed directly into `classical_solver_driver.run_classical_solver(...)` and produce the same class of successful smoke result we already observed manually.
- The bridge is reusable for the current readable spin-only bilinear block types that already carry enough information to become a `3x3` classical exchange matrix: `isotropic_exchange`, `xxz_exchange`, `symmetric_exchange_matrix`, and `exchange_tensor`.
- Unsupported cases fail explicitly with stable error messages instead of silently guessing.
- The document-reader pipeline can write bridge artifacts and, when requested, a solver result artifact in the same output directory.
- Targeted regression tests cover builder behavior, geometry recovery, failure modes, and the FeI2 end-to-end bridge path.

Not in scope for this slice:

- Expanding every shell into the full symmetry-equivalent bond set.
- General support for residual terms, multipolar terms, or mixed spin-orbital models.
- Automatic LSWT / GSWT / thermodynamics chaining from this new bridge.
- Solving `selected_local_bond_family="all"` as a combined multi-shell model.

## Chosen Approach

Use a small reusable bridge module plus a thin pipeline hook.

Why this approach:

- It keeps the hard part isolated: converting readable exchange blocks plus shell geometry into one minimal classical payload.
- It avoids bloating `run_document_reader_pipeline.py` with transformation logic that deserves its own tests.
- It gives us a useful end state quickly: FeI2 becomes one-command reproducible for the current classical smoke path, without pretending we have solved the full downstream product problem.

## File Map

**Create**

- `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`

**Modify**

- `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

**Read For Context While Implementing**

- `translation-invariant-spin-model-simplifier/scripts/simplify/assemble_effective_model.py`
- `translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py`
- `translation-invariant-spin-model-simplifier/scripts/common/lattice_geometry.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`
- `translation-invariant-spin-model-simplifier/tests/test_document_input_protocol.py`

### Task 1: Lock The Bridge Contract With Failing Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_document_input_protocol.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`

- [ ] **Step 1: Write the failing builder tests for the supported happy path**

Add tests that build a minimal simplification payload in-memory and assert:

```python
result = build_spin_only_solver_payload(
    {
        "normalized_model": {
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "2a'",
            "selected_coordinate_convention": "global_crystallographic",
            "lattice": {
                "kind": "trigonal",
                "dimension": 3,
                "cell_parameters": {
                    "a": 4.05012,
                    "b": 4.05012,
                    "c": 6.75214,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
                "family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}},
            },
            "local_hilbert": {"dimension": 3},
        },
        "effective_model": {
            "main": [
                {
                    "type": "xxz_exchange",
                    "family": "2a'",
                    "coefficient_xy": 0.068,
                    "coefficient_z": 0.073,
                }
            ]
        },
    }
)

assert result["status"] == "ok"
assert result["payload"]["bonds"][0]["matrix"] == [
    [0.068, 0.0, 0.0],
    [0.0, 0.068, 0.0],
    [0.0, 0.0, 0.073],
]
assert result["payload"]["bridge_metadata"]["selected_family"] == "2a'"
```

- [ ] **Step 2: Add failing tests for explicit rejection paths**

Cover at least these errors:

```python
with self.assertRaisesRegex(ValueError, "selected_local_bond_family"):
    build_spin_only_solver_payload({"normalized_model": {"selected_local_bond_family": "all"}})

with self.assertRaisesRegex(ValueError, "unsupported readable block"):
    build_spin_only_solver_payload(
        {
            "normalized_model": {"selected_local_bond_family": "2a'", "lattice": {"family_shell_map": {"2a'": {"shell_index": 6, "distance": 9.736622}}}},
            "effective_model": {"main": [{"type": "higher_multipole_coupling", "family": "2a'"}]},
        }
    )
```

- [ ] **Step 3: Run the new test file to verify it fails for the right reason**

Run: `pytest translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py -v`

Expected: FAIL with an import error or missing builder function, not with unrelated parser errors.

- [ ] **Step 4: Capture one FeI2-facing pipeline expectation before implementation**

Add a failing regression in `test_run_document_reader_pipeline.py` asserting that an opt-in bridge run writes:

```python
output_dir / "classical" / "solver_payload.json"
output_dir / "classical" / "solver_result.json"
```

and that the final result records bridge metadata without breaking the existing simplification artifacts.

- [ ] **Step 5: Commit the red test baseline**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py \
        translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py
git commit -m "test: define FeI2 document-reader classical bridge contract"
```

### Task 2: Implement The Spin-Only Builder

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/common/lattice_geometry.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/simplify/assemble_effective_model.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`

- [ ] **Step 1: Implement block selection and scope checks**

Write a builder with a narrow public entry point:

```python
def build_spin_only_solver_payload(simplification_payload):
    ...
```

It should:

- read `normalized_model.selected_local_bond_family`
- reject missing family or `all`
- select exactly one `effective_model.main` block matching that family
- reject zero-match or multi-match ambiguity
- reject unsupported block types with stable messages

- [ ] **Step 2: Implement readable-block to `3x3` exchange matrix conversion**

Support these mappings:

```python
if block["type"] == "isotropic_exchange":
    matrix = [[J, 0.0, 0.0], [0.0, J, 0.0], [0.0, 0.0, J]]
elif block["type"] == "xxz_exchange":
    matrix = [[Jxy, 0.0, 0.0], [0.0, Jxy, 0.0], [0.0, 0.0, Jz]]
elif block["type"] in {"symmetric_exchange_matrix", "exchange_tensor"}:
    matrix = [[float(value) for value in row] for row in block["matrix"]]
else:
    raise ValueError("unsupported readable block for spin-only solver bridge")
```

- [ ] **Step 3: Implement minimal shell-geometry recovery**

Use `family_shell_map` plus `common.lattice_geometry.enumerate_neighbor_shells(...)` to recover one canonical representative pair:

```python
shells = enumerate_neighbor_shells(
    resolve_lattice_vectors(lattice),
    lattice.get("positions") or [[0.0, 0.0, 0.0]],
    shell_count=target_shell_index,
    max_translation=3,
)
shell = shells[target_shell_index - 1]
pair = choose_canonical_pair(shell["pairs"])
```

`choose_canonical_pair(...)` should be implemented locally in the new module and should pick the lexicographically stable forward translation, so FeI2 gets a deterministic representative bond instead of a guessed one-off vector.

- [ ] **Step 4: Assemble the emitted payload and provenance**

Return a contract like:

```python
{
    "status": "ok",
    "payload": {
        "lattice": normalized_model["lattice"],
        "normalized_model": normalized_model,
        "bonds": [
            {
                "source": 0,
                "target": 0,
                "vector": [1, -1, 1],
                "distance": 9.736622,
                "matrix": [[...], [...], [...]],
                "family": "2a'",
            }
        ],
        "classical": {"method": "auto"},
        "bridge_metadata": {
            "bridge_kind": "document_reader_spin_only_minimal",
            "selected_family": "2a'",
            "block_type": "xxz_exchange",
            "shell_index": 6,
        },
    },
}
```

- [ ] **Step 5: Run the builder tests until green, then commit**

Run: `pytest translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py -v`

Expected: PASS for supported mappings and stable FAIL/PASS behavior for rejection cases.

```bash
git add translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py \
        translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py
git commit -m "feat: add spin-only solver payload bridge from readable exchange blocks"
```

### Task 3: Hook The Builder Into The Document-Reader Pipeline

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py`

- [ ] **Step 1: Add explicit opt-in pipeline controls**

Extend `run_document_reader_pipeline(...)` and the CLI parser with flags such as:

```python
emit_spin_only_solver_payload=False,
run_spin_only_classical_solver=False,
```

The pipeline must stay simplification-only by default.

- [ ] **Step 2: Write bridge artifacts only after simplification succeeds**

When the new emit flag is true:

- call `build_spin_only_solver_payload(result)`
- create `output_dir / "classical"`
- write `solver_payload.json`
- attach bridge artifact paths into the returned top-level `artifacts`

- [ ] **Step 3: Add optional solver execution**

When `run_spin_only_classical_solver` is true:

```python
solver_payload = bridge_result["payload"]
solver_result = run_classical_solver(deepcopy(solver_payload))
```

Write `classical/solver_result.json` and return lightweight summary fields such as chosen method, role, and ordering vector in the final pipeline result.

- [ ] **Step 4: Make pipeline failures explicit and non-destructive**

If simplification succeeds but bridge construction fails, return a partial bridge status in artifacts instead of corrupting the simplification success result. The final result should still preserve:

- `status == "ok"` for the simplification portion
- a bridge-specific error section
- all pre-existing simplification artifacts

Only the optional bridge stage should fail, not the base document-reader path.

- [ ] **Step 5: Run targeted pipeline tests and commit**

Run: `pytest translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py -v`

Expected: existing FeI2 document-reader regressions remain green, and the new bridge regression writes the expected `classical/` artifacts.

```bash
git add translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py \
        translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py
git commit -m "feat: wire FeI2 classical bridge into document-reader pipeline"
```

### Task 4: Verify The Real FeI2 Path And Document The New Contract

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`
- Read: `translation-invariant-spin-model-simplifier/tests/data/fei2_document_input.tex`
- Verify: external fixture path `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/input.tex`

- [ ] **Step 1: Add a focused protocol note for the new bridge stage**

Document:

- required selected family
- supported readable block types
- emitted artifacts
- explicit non-goals for this first bridge

- [ ] **Step 2: Run the minimal targeted regression slice**

Run:

```bash
pytest \
  translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_document_input_protocol.py -v
```

Expected: PASS with no regressions in the existing FeI2 family-selection path.

- [ ] **Step 3: Run the real FeI2 bridge smoke command**

Run a real CLI smoke invocation against the external FeI2 fixture with the new flags enabled, using:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/run_document_reader_pipeline.py \
  --freeform "$(cat /data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/input.tex)" \
  --source-path /data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/input.tex \
  --selected-model-candidate effective \
  --selected-local-bond-family "2a'" \
  --selected-coordinate-convention global_crystallographic \
  --output-dir /data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/fei2_document_reader_bridge_smoke_<timestamp> \
  --use-request-example-payload \
  --emit-spin-only-solver-payload \
  --run-spin-only-classical-solver
```

Expected artifacts:

- `document_orchestration/final_result.json`
- `simplification/effective_model.json`
- `classical/solver_payload.json`
- `classical/solver_result.json`
- `final_pipeline_result.json`

- [ ] **Step 4: Check the real acceptance conditions**

Verify in the produced solver result:

- auto-routing chooses a spin-only method
- the final classical state role is `final`
- the strong-constraint residual is zero or within the existing LT acceptance tolerance
- the reported ordering vector is populated

This is the completion bar for this slice. Stop here even if LSWT/thermodynamics could be chained later.

- [ ] **Step 5: Commit docs and verification-backed finish**

```bash
git add translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md
git commit -m "docs: document FeI2 document-reader classical bridge"
```

## Final Acceptance Checklist

- [ ] No existing document-reader-only FeI2 tests regressed.
- [ ] A new builder unit test suite covers supported block mappings and hard failures.
- [ ] The pipeline can emit a deterministic minimal solver payload for FeI2 family `2a'`.
- [ ] The pipeline can optionally run the classical solver and persist its result artifact.
- [ ] The real external FeI2 fixture reproduces the classical smoke success path without manual payload editing.
- [ ] Documentation states clearly that this is a minimal selected-family bridge, not a full multi-shell physics workflow.
