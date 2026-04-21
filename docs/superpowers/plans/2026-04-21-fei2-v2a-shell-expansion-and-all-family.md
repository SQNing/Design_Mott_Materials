# FeI2 V2a Shell Expansion And All-Family Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the current FeI2 spin-only bridge so it can expand one selected family into a full shell bond set and assemble `selected_local_bond_family = "all"` into one stable multi-family solver payload.

**Architecture:** Build V2a in two layers. First, add a reusable single-family shell-expansion helper that consumes authoritative per-family readable blocks and emits all canonical bond pairs for one shell. Second, add an all-family assembler that expands each supported family independently, uses `shell_resolved_exchange` only for ordering/validation help, and merges the expanded families into one aggregated payload without yet chaining downstream stages.

**Tech Stack:** Python 3, document-reader simplification payloads, shell geometry helpers, spin-only classical payload builders, `unittest`/`pytest`

---

## Scope Lock

This plan implements V2a only.

In scope:

- full shell expansion for one selected supported family
- `selected_local_bond_family = "all"` payload assembly
- explicit family ordering, metadata, and validation rules
- preservation of `effective_model` and `simplified_model` routing hints

Out of scope:

- automatic LSWT / GSWT / thermodynamics execution
- residual or multipolar bridge promotion
- mixed spin-orbital bridge support

## File Map

**Create**

- `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py`

**Modify**

- `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`
- `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

**Read For Context**

- `docs/superpowers/specs/2026-04-21-fei2-v2a-shell-expansion-and-all-family-design.md`
- `translation-invariant-spin-model-simplifier/scripts/simplify/assemble_effective_model.py`
- `translation-invariant-spin-model-simplifier/scripts/common/lattice_geometry.py`
- `translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`

### Task 1: Lock The V2a Contract With Failing Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`
- Read: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py`

- [ ] **Step 1: Write a failing test for single-family full-shell expansion**

Add a test that builds a selected-family FeI2-like simplification payload and asserts:

```python
result = build_spin_only_solver_payload(payload)

assert result["status"] == "ok"
assert result["payload"]["bridge_metadata"]["expansion_mode"] == "full_shell"
assert len(result["payload"]["bonds"]) > 1
assert {bond["family"] for bond in result["payload"]["bonds"]} == {"2a'"}
assert {bond["shell_index"] for bond in result["payload"]["bonds"]} == {6}
```

- [ ] **Step 2: Write a failing test for `selected_local_bond_family = "all"` assembly**

Add a test where `effective_model.main` contains two supported family-resolved readable blocks plus a `shell_resolved_exchange` summary, then assert:

```python
result = build_spin_only_solver_payload(payload)

assert result["status"] == "ok"
assert result["payload"]["bridge_metadata"]["expansion_mode"] == "all_families"
assert result["payload"]["bridge_metadata"]["family_order"] == ["1", "2"]
assert {bond["family"] for bond in result["payload"]["bonds"]} == {"1", "2"}
```

- [ ] **Step 3: Write a failing test for input precedence**

Add a test proving that when both per-family readable blocks and `shell_resolved_exchange` are present, the builder consumes the family-resolved blocks as authoritative and only uses the shell summary for ordering/validation.

Suggested assertion:

```python
assert result["payload"]["bridge_metadata"]["input_precedence"] == "family_blocks_over_shell_summary"
```

- [ ] **Step 4: Write a failing test for strict `all` rejection**

Add a test where one family is supported and another is `higher_multipole_coupling`, then assert:

```python
with self.assertRaisesRegex(ValueError, "unsupported families"):
    build_spin_only_solver_payload(payload)
```

- [ ] **Step 5: Run the V2a test file and verify it fails for missing behavior**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py -v
```

Expected: FAIL because V2a expansion/assembly behavior does not exist yet, not because of unrelated import or parser errors.

- [ ] **Step 6: Commit the red test baseline**

```bash
git add -f translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py
git commit -m "test: define FeI2 V2a shell expansion contract"
```

### Task 2: Implement Single-Family Full-Shell Expansion

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py`

- [ ] **Step 1: Add a helper that expands one shell into all canonical bond pairs**

Implement a helper like:

```python
def _expand_family_shell_bonds(lattice, shell_index, distance, matrix, family):
    ...
```

It should:

- enumerate the target shell with existing geometry helpers
- canonicalize and de-duplicate shell pairs
- emit one bond record per canonical pair
- attach `family`, `shell_index`, and `distance`

- [ ] **Step 2: Preserve V1 representative mode as a deliberate subset**

Refactor the current representative-pair logic so it can be expressed in terms of the expanded shell result:

```python
expanded = _expand_family_shell_bonds(...)
representative = expanded[0]
```

This keeps V1 and V2a on one geometry path instead of maintaining two separate shell-selection implementations.

- [ ] **Step 3: Update single-family payload metadata**

When a single family is expanded, emit:

```python
"bridge_metadata": {
    "bridge_kind": "document_reader_spin_only_shell_expanded",
    "expansion_mode": "full_shell",
    "selected_family": family,
    "block_type": block_type,
    "shell_index": shell_index,
    "pair_count": len(bonds),
}
```

- [ ] **Step 4: Run the single-family V2a test to verify it passes**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py -k full_shell -v
```

Expected: PASS for the new single-family expansion behavior.

- [ ] **Step 5: Commit the single-family expansion slice**

```bash
git add translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py
git add -f translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py
git commit -m "feat: expand FeI2 bridge payloads to full shell bonds"
```

### Task 3: Implement All-Family Assembly

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py`

- [ ] **Step 1: Add authoritative family-block collection**

Implement a helper like:

```python
def _collect_bridgeable_family_blocks(simplification_payload):
    ...
```

It should:

- prefer family-resolved readable blocks from `effective_model.main`
- use `shell_resolved_exchange.shells` only for ordering and validation when present
- reject inconsistent family membership or block-type mismatches between the two sources

- [ ] **Step 2: Add stable family ordering**

Sort families by:

1. `shell_index`
2. `family` label

and store the final order in `bridge_metadata["family_order"]`.

- [ ] **Step 3: Expand each family independently and concatenate the results**

Implement an all-family path like:

```python
family_expansions = [_expand_one_family(...), ...]
bonds = [bond for expansion in family_expansions for bond in expansion["bonds"]]
```

and store per-family summaries:

```python
"family_summaries": [
    {
        "family": family,
        "shell_index": shell_index,
        "block_type": block_type,
        "pair_count": len(expansion["bonds"]),
    }
]
```

- [ ] **Step 4: Enforce strict rejection for unsupported families in `all` mode**

If any family in the authoritative readable input is unbridgeable, raise a stable error instead of silently dropping it.

- [ ] **Step 5: Run the all-family V2a tests to verify they pass**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py -k "all or precedence" -v
```

Expected: PASS for family ordering, aggregation, and strict rejection behavior.

- [ ] **Step 6: Commit the all-family assembly slice**

```bash
git add translation-invariant-spin-model-simplifier/scripts/classical/build_spin_only_solver_payload.py
git add -f translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py
git commit -m "feat: assemble all-family FeI2 shell-expanded payloads"
```

### Task 4: Document The V2a Contract

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md`

- [ ] **Step 1: Add V2a bridge notes to the protocol**

Document:

- single-family full-shell expansion
- `all` aggregation behavior
- family-block precedence over shell summary
- strict rejection of unsupported families in `all` mode

- [ ] **Step 2: Run a focused doc-adjacent regression slice**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_build_spin_only_solver_payload_v2a.py \
  translation-invariant-spin-model-simplifier/tests/test_document_input_protocol.py \
  translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py \
  -k "shell_resolved_exchange or selected_local_bond_family or build_spin_only_solver_payload" -v
```

Expected: PASS for the V1 builder tests, new V2a builder tests, and the existing shell-summary/document-family regressions that still define the readable-model surface.

- [ ] **Step 3: Commit the protocol update**

```bash
git add translation-invariant-spin-model-simplifier/reference/natural-language-input-protocol.md
git commit -m "docs: describe FeI2 V2a shell expansion bridge"
```

### Task 5: Verify The Real FeI2 V2a Payloads

**Files:**
- Read: `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/input.tex`

- [ ] **Step 1: Run a real single-family V2a smoke**

Run a real FeI2 document-reader invocation for `2a'` and inspect the emitted payload:

```bash
python - <<'PY'
...
result = run_document_reader_pipeline(
    text,
    source_path=str(source_path),
    selected_model_candidate='effective',
    selected_local_bond_family="2a'",
    selected_coordinate_convention='global_crystallographic',
    output_dir=output_dir,
    use_request_example_payload=True,
    emit_spin_only_solver_payload=True,
)
...
PY
```

Expected:

- `bridge_status == "ok"`
- expanded shell bond count greater than 1
- all emitted bonds carry family `2a'` and shell index `6`

- [ ] **Step 2: Run a real `all`-family V2a smoke**

Run the same path with:

```python
selected_local_bond_family="all"
```

Expected:

- `bridge_status == "ok"`
- payload contains multiple families when the readable model exposes them
- `bridge_metadata["family_order"]` is stable and shell-sorted

- [ ] **Step 3: Verify V2a completion against V2a criteria only**

Do not require LSWT / GSWT / thermodynamics success here.

Completion evidence for V2a is:

- shell-expanded single-family payloads are correct
- `all` payload assembly is correct
- strict unsupported-family handling is correct

## Final Acceptance Checklist

- [ ] Single-family V2a expands one shell into all canonical bond pairs.
- [ ] `all` mode assembles supported families in stable shell order.
- [ ] Per-family readable blocks are authoritative; shell summaries are used for ordering and validation only.
- [ ] Unsupported families in `all` mode fail explicitly.
- [ ] Routing hints remain present in the emitted payload.
- [ ] FeI2 real single-family and `all` payloads are reproducibly emitted.
