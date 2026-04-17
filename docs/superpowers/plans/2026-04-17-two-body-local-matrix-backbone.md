# Two-Body Local Matrix Backbone Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the spin-model simplifier around a one-body and two-body `local_matrix_record` backbone so document, natural-language, operator-text, and matrix-form inputs compile into family-resolved local matrices that can be decomposed deterministically and interpreted into common physical terms such as exchange tensors, DM, and `Jzz/Jpm/Jpmpm/Jzpm`.

**Architecture:** The implementation will add a new matrix-compiler layer between current extraction/orchestration code and the existing simplification backend. Operator-text helpers remain in the repo but are repositioned as compiler front-end tools; `decompose_local_term.py` becomes matrix-first, and readable interpretation grows from the decomposed matrix rather than from text-template matching alone.

**Tech Stack:** Python 3, standard library `dataclasses` / `json` / `re`, existing simplifier scripts, pytest / unittest-style tests already used in the repo.

---

## File Structure

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/local_matrix_record.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_local_term_to_matrix.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_operator_bond_to_matrix.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_onsite_term_to_matrix.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py`

## Responsibility Map

- `local_matrix_record.py`
  Define and validate the canonical schema for one-body and two-body local matrix records. This file owns the record shape, required metadata, and phase-boundary checks for unsupported `body_order > 2`.

- `compile_local_term_to_matrix.py`
  Provide the single matrix-compiler entry point that turns extracted local-term candidates into `local_matrix_record` objects.

- `compile_operator_bond_to_matrix.py`
  Compile supported two-body operator-text candidates into fixed-basis bond matrices, using existing operator parser / normalizer helpers as front-end utilities rather than as the final IR.

- `compile_onsite_term_to_matrix.py`
  Compile onsite one-body candidates such as `D(S^z)^2` and future onsite anisotropy forms into one-site local matrices.

- `decompose_local_term.py`
  Become matrix-first. Existing direct operator parsing remains as a compatibility path only when routed through the new compiler contract.

- `canonicalize_terms.py`
  Preserve `local_matrix_record` metadata such as `family`, `body_order`, and decomposition provenance in the canonical output.

- `identify_readable_blocks.py`
  Interpret decomposed two-body bilinear terms by matrix structure first, including symmetric tensor, DM, and literature-specific anisotropic parameterizations, while leaving unrecognized decomposed structure in residual form.

- `simplify_text_input.py`
  Orchestrate extraction -> matrix compilation -> matrix decomposition -> readable interpretation without sending supported two-body models back to the old projection gate.

---

### Task 1: Define The Local Matrix Record Schema

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/local_matrix_record.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- valid onsite record creation with `support=[0]`, `body_order=1`, and `geometry_class="onsite"`
- valid two-body record creation with `support=[0,1]`, `body_order=2`, `geometry_class="bond"`, family metadata, basis order, and tensor-product order
- rejection of records with missing required fields
- rejection of records whose `body_order` does not match support size
- explicit phase-boundary failure for `body_order > 2`

Example test shape:

```python
def test_build_two_body_local_matrix_record():
    record = build_local_matrix_record(
        support=[0, 1],
        family="1",
        geometry_class="bond",
        coordinate_frame="global_xyz",
        local_basis_order=["m=1", "m=0", "m=-1"],
        tensor_product_order=[0, 1],
        matrix=[[0.0] * 9 for _ in range(9)],
    )
    assert record["body_order"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py -q
```

Expected:
- import failure because the new schema module does not exist yet

- [ ] **Step 3: Write minimal implementation**

Implement:
- a builder / validator for `local_matrix_record`
- required-field checks
- support-size and body-order consistency checks
- a current-phase guard that rejects `body_order > 2`

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py -q
```

Expected:
- all record-schema tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/local_matrix_record.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add local matrix record schema"
```

---

### Task 2: Add Onsite And Two-Body Matrix Compiler Entry Points

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_local_term_to_matrix.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_operator_bond_to_matrix.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/compile_onsite_term_to_matrix.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- compiling a direct matrix-form two-body candidate into a valid `local_matrix_record`
- compiling `D(Sz@0)^2` or equivalent onsite anisotropy text into a one-body local matrix
- compiling FeI2-style family-1 operator text into a two-body matrix record with the correct family metadata
- preserving `source_kind`, `source_expression`, and parameter provenance
- returning explicit unsupported / needs-input behavior for a candidate that clearly has `body_order > 2`

Example test shape:

```python
def test_compile_family_resolved_operator_text_to_bond_matrix():
    record = compile_local_term_to_matrix(candidate)
    assert record["family"] == "1"
    assert record["body_order"] == 2
    assert record["representation"]["kind"] == "matrix"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py -q
```

Expected:
- missing compiler modules or failing matrix-compiler assertions

- [ ] **Step 3: Write minimal implementation**

Implement:
- a top-level compiler dispatch for onsite vs two-body candidates
- onsite matrix compilation for current single-ion anisotropy coverage
- two-body operator-text compilation into fixed-basis bond matrices using existing parser / normalizer helpers as front-end tools
- provenance metadata preservation in the returned record

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py -q
```

Expected:
- all local-matrix compiler tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/compile_local_term_to_matrix.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/compile_operator_bond_to_matrix.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/compile_onsite_term_to_matrix.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: compile onsite and bond terms to local matrices"
```

---

### Task 3: Make Decomposition Matrix-First

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- `decompose_local_term()` accepts a `local_matrix_record` and decomposes it without needing raw operator parsing
- FeI2 family-1 operator text reaches decomposition through the matrix compiler rather than the old raw-operator fallback
- onsite anisotropy can be decomposed from a one-body matrix record
- unsupported `body_order > 2` is rejected honestly

Example test shape:

```python
def test_decompose_local_matrix_record_without_raw_operator():
    record = build_local_matrix_record(...)
    result = decompose_local_term({"local_term_record": record})
    assert result["mode"] == "spin-multipole-basis"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- decomposition still depends on old representation handling or fails to preserve matrix-record metadata

- [ ] **Step 3: Write minimal implementation**

Implement:
- matrix-record detection in `decompose_local_term.py`
- matrix-first decomposition path for one-body and two-body records
- compatibility fallback for older direct inputs by compiling them into local matrix records first
- metadata propagation into decomposition terms

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- all decomposition and spin-S pipeline tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: make local-term decomposition matrix-first"
```

---

### Task 4: Preserve Matrix Metadata Through Canonicalization

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`

- [ ] **Step 1: Write the failing test**

Cover at least:
- canonical terms preserve `family`
- canonical terms preserve one-body vs two-body support correctly
- canonical terms retain enough provenance to distinguish onsite from bond-derived decomposition

Example test shape:

```python
def test_canonicalize_preserves_family_from_matrix_backbone():
    canonical = canonicalize_terms({"decomposition": decomposition})
    assert canonical["two_body"][0]["family"] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- missing family / provenance preservation in canonical output

- [ ] **Step 3: Write minimal implementation**

Implement:
- propagation of matrix-record provenance fields needed by downstream readable interpretation
- no regression for current body-order grouping and higher-body guards

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- canonicalization tests pass with matrix-metadata preservation

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: preserve matrix backbone metadata in canonical terms"
```

---

### Task 5: Extend Bilinear Interpretation To Exchange Tensor, DM, And Literature-Specific Forms

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- decomposition of a general bilinear two-body kernel into:
  - isotropic part
  - symmetric exchange tensor part
  - antisymmetric DM part
- readable interpretation for DM-bearing matrices
- continued readable interpretation for existing `Jzz/Jpm/Jpmpm/Jzpm` and XXZ cases
- residual preservation for decomposed but not-yet-pretty two-site structures such as biquadratic or multipolar channels

Example test shape:

```python
def test_identify_readable_blocks_reports_dm_vector_from_antisymmetric_exchange():
    readable = identify_readable_blocks(canonical_model)
    dm_blocks = [block for block in readable["blocks"] if block["type"] == "exchange_tensor_plus_dm"]
    assert dm_blocks[0]["dm_vector"] == [0.0, 0.0, 0.2]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- readable bilinear interpretation does not yet surface the matrix-derived DM / tensor decomposition cleanly

- [ ] **Step 3: Write minimal implementation**

Implement:
- a matrix-driven bilinear interpretation order
- DM extraction from the antisymmetric bilinear sector
- readable block support for general tensor plus DM
- preservation of current literature-specific forms where the matrix pattern maps cleanly

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- readable physics tests pass for tensor, DM, and literature-specific cases

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: interpret bilinear matrices as tensor and DM physics"
```

---

### Task 6: Route The Text Pipeline Through The Matrix Backbone

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- FeI2 family-1 operator-only input lands through the matrix backbone and reaches `status == "ok"`
- matrix-form input lands through the same backbone
- all-family family-resolved output preserves family labels through matrix compilation and decomposition
- unsupported higher-body terms return explicit unsupported / needs-input status instead of being miscompiled as bonds

Example test shape:

```python
def test_pipeline_lands_fei2_operator_family_through_local_matrix_backbone():
    result = run_text_simplification_pipeline(...)
    assert result["status"] == "ok"
    assert result["decomposition"]["source_backbone"] == "local_matrix_record"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py -q
```

Expected:
- the text pipeline still treats the compiler layer as an implementation detail rather than the main backbone

- [ ] **Step 3: Write minimal implementation**

Implement:
- pipeline routing through the matrix compiler before decomposition for one-body and two-body supported paths
- backbone metadata in result payloads where useful for debugging and reporting
- preservation of current family selection / all-family behavior

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py -q
```

Expected:
- text pipeline regression tests pass through the matrix backbone

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: route text simplification through local matrix backbone"
```

---

### Task 7: Update The Skill Contract And Run The Focused Verification Bundle

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- `SKILL.md` now documents the `local_matrix_record` backbone
- the contract explicitly says the current phase fully supports one-body and two-body local matrices
- the contract explicitly says multispin support is schema-only / future-facing
- the contract names DM and general exchange tensor interpretation as supported two-body readable categories

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- contract expectations fail until docs are updated

- [ ] **Step 3: Write minimal implementation**

Update `SKILL.md` so it matches the shipped backbone:
- extraction layer + matrix compiler + matrix-first decomposition
- one-body and two-body support
- DM / tensor / literature-specific anisotropic two-body readout
- explicit future support boundary for higher-body terms

- [ ] **Step 4: Run the focused verification bundle**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_local_matrix_record.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_compile_local_term_to_matrix.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- all focused local-matrix backbone tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/SKILL.md
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "docs: finalize local matrix backbone contract"
```

---

## Execution Notes

- Keep the current operator-expression helpers, but treat them as compiler front-end tools rather than the final main IR.
- Do not silently reduce `body_order > 2` terms to fake bonds.
- Prefer matrix-first decomposition and matrix-driven physics interpretation over further text-template branching.
- Preserve family labels and provenance end-to-end; they are a primary user-facing data dimension for shell-resolved comparisons.
