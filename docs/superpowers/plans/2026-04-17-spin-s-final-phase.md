# Spin-S Final Phase Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a broad, efficient spin-`S` operator-expression path that parses LaTeX-like and compact operator strings through one shared core, supports generic `n`-body monomials, and feeds the existing canonicalization and readable-block pipeline without collapsing supported inputs into `raw-operator`.

**Architecture:** The implementation will add a small operator-expression subsystem under `scripts/simplify/` with four layers: AST parsing, monomial normalization, sparse local expansion, and canonical-term bridging. `decompose_local_term.py` will become the entry point for this subsystem, while `canonicalize_terms.py`, `identify_readable_blocks.py`, and the existing report pipeline remain downstream consumers with only targeted compatibility updates for broader `n`-body inputs and residual preservation.

**Tech Stack:** Python 3, standard library `re` / `dataclasses`, existing `translation-invariant-spin-model-simplifier` simplify modules, pytest / unittest-style tests already used in the repo.

---

## File Structure

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_ast.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_parser.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_normalizer.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_sparse_expand.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`
- Test: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py`

## Responsibility Map

- `operator_expression_ast.py`
  Own the lightweight internal node types for scalar sums, products, coefficients, and site-tagged local operator factors.

- `operator_expression_parser.py`
  Parse supported LaTeX-like and compact programmatic operator strings into one shared AST.

- `operator_expression_normalizer.py`
  Convert AST expressions into sparse normalized monomials with explicit coefficient and factor metadata.

- `operator_expression_sparse_expand.py`
  Apply conservative local rewrite rules and sparse basis expansion so operator monomials become canonical factor labels without dense matrix construction.

- `decompose_local_term.py`
  Detect the new operator-expression route, call the parser/normalizer/expander stack, and return decomposition terms with source metadata instead of `raw-operator` when the expression is supported.

- `canonicalize_terms.py`
  Preserve stable ordering and metadata for broader `n`-body canonical labels without breaking the current one-body and two-body grouping behavior.

- `simplify_text_input.py`
  Remove the old projection gate for supported spin-`S` operator expressions while preserving clear `needs_input` behavior for truly unsupported syntax.

---

### Task 1: Add A Shared Operator AST And Compact-String Parser

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_ast.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_parser.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- compact factor parsing for `Sz@0`, `Sz@0 Sz@1`, and `Sp@0 Sm@1 Sz@2`
- compact sums with coefficients such as `0.5*Sz@0 Sz@1 + Jpm*Sp@0 Sm@1`
- site-tagged multipole parsing such as `T2_0@0 T2_c1@1`
- explicit parse failure for unsupported tokens instead of silent fallback

Example test shape:

```python
def test_parse_compact_three_body_product():
    ast = parse_operator_expression("Sp@0 Sm@1 Sz@2")
    assert ast.kind == "product"
    assert [factor.label for factor in ast.factors] == ["Sp", "Sm", "Sz"]
    assert [factor.site for factor in ast.factors] == [0, 1, 2]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py -q
```

Expected:
- import failure because the new parser modules do not exist yet

- [ ] **Step 3: Implement the minimal AST and compact parser**

Implement:
- lightweight node classes or dataclasses for coefficient, factor, product, and sum nodes
- a parser for compact `Label@site` products
- scalar coefficient handling for numeric and named parameters
- deterministic parse errors for unsupported tokens

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py -q
```

Expected:
- all parser tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_ast.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_parser.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add shared operator expression parser core"
```

---

### Task 2: Normalize LaTeX And Compact Expressions Into Shared Sparse Monomials

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py`
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_normalizer.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- `S_i^z S_j^z` and `Sz@0 Sz@1` normalize to the same monomial payload
- `S_i^+ S_j^- + S_i^- S_j^+` becomes two normalized monomials before later rewrites
- parameter names such as `Jzz` survive as coefficients until resolved
- repeated named sites map deterministically onto support positions `0`, `1`, `2`, ...

Example test shape:

```python
def test_latex_and_compact_bilinear_normalize_identically():
    left = normalize_operator_expression("S_i^z S_j^z")
    right = normalize_operator_expression("Sz@0 Sz@1")
    assert left == right
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py -q
```

Expected:
- missing normalization module or failing equality assertions

- [ ] **Step 3: Implement the shared normalization layer**

Implement:
- LaTeX token support for `S_i^x`, `S_i^y`, `S_i^z`, `S_i^+`, `S_i^-`
- site-symbol mapping from `i`, `j`, `k`, ... to local support indices
- monomial normalization with coefficient plus factor tuples
- stable output ordering so tests are deterministic

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py -q
```

Expected:
- parser and normalization tests pass together

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_normalizer.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: normalize latex and compact spin expressions"
```

---

### Task 3: Add Sparse Local Rewrite And Expand The Decomposition Path

**Files:**
- Create: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_sparse_expand.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- ladder bilinear input expands into canonical spin-component terms instead of `raw-operator`
- already-named multipole factors such as `T2_0@0 T2_c1@1` pass through cleanly
- compact three-body input such as `Sp@0 Sm@1 Sz@2` becomes decomposition terms with `body_order` implied downstream
- unsupported syntax still returns a controlled operator fallback rather than crashing

Example test shape:

```python
def test_decompose_supported_three_body_operator_string_without_raw_operator():
    normalized = {
        "local_hilbert": {"dimension": 3},
        "local_term": {
            "support": [0, 1, 2],
            "representation": {"kind": "operator", "value": "Sp@0 Sm@1 Sz@2"},
        },
        "parameters": {},
    }
    result = decompose_local_term(normalized)
    assert result["mode"] == "operator-basis"
    assert all(term["label"] != "raw-operator" for term in result["terms"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- failing decomposition assertions or missing sparse expansion helpers

- [ ] **Step 3: Implement the sparse expansion route**

Implement:
- conservative ladder-to-Cartesian rewrites where the mapping is exact
- sparse term distribution and immediate merge of identical canonical products
- multipole pass-through for already-canonical local labels
- integration into `decompose_local_term.py` before the old `raw-operator` fallback

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- all decomposition and spin-`S` pipeline tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_sparse_expand.py \
  translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py \
  translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: route spin-S operator expressions through sparse expansion"
```

---

### Task 4: Preserve Canonical n-Body Terms And Residual Structure

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- canonicalization groups five-body and higher terms under `higher_body`
- `body_order` is derived from distinct support sites, not raw factor count
- mixed multipole higher-body terms retain family/rank metadata when inferable
- residual summaries survive for unclassified higher-body terms

Example test shape:

```python
def test_canonicalize_five_body_term_into_higher_body_bucket():
    canonical = canonicalize_terms({
        "terms": [{"label": "Sz@0 Sz@1 Sz@2 Sz@3 Sz@4", "coefficient": 1.0}]
    })
    assert canonical["higher_body"][0]["body_order"] == 5
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- missing or incorrect higher-body canonical metadata

- [ ] **Step 3: Implement the minimal canonicalization updates**

Implement:
- stable support de-duplication for repeated-site products
- `higher_body` metadata preservation
- no regression for current one-body through four-body buckets

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py -q
```

Expected:
- all spin-`S` pipeline tests pass, including higher-body cases

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py \
  translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: preserve canonical higher-body spin-S terms"
```

---

### Task 5: Land The FeI2 Operator Route Without The Old Projection Gate

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- supported FeI2 effective-model operator text no longer returns `projection_or_truncate`
- the pipeline reaches `status == "ok"` when the selected effective operator family is supported
- canonical output contains non-empty two-body terms from operator parsing, not only matrix fallback
- unsupported operator syntax still surfaces a controlled `needs_input` result

Example test shape:

```python
def test_pipeline_lands_fei2_operator_path_without_projection_gate():
    result = run_text_simplification_pipeline(
        fixture,
        source_path="tests/data/fei2_document_input.tex",
        selected_model_candidate="effective",
        selected_local_bond_family="1",
    )
    assert result["status"] == "ok"
    assert result["decomposition"]["mode"] == "operator-basis"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py -q
```

Expected:
- the old projection gate still fires for supported FeI2 operator expressions

- [ ] **Step 3: Update the text pipeline gatekeeping**

Implement:
- success path for supported operator-expression decomposition
- keep the projection gate only for syntax the new parser still does not support
- preserve current matrix fallback behavior when the selected input path actually provides matrices

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py -q
```

Expected:
- FeI2 operator-route regression tests pass

- [ ] **Step 5: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py \
  translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: land supported spin-S operator text path"
```

---

### Task 6: Document The Final Spin-S Contract And Run The Focused Verification Bundle

**Files:**
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/SKILL.md`
- Modify: `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py`

- [ ] **Step 1: Write the failing tests**

Cover at least:
- the skill contract now describes shared operator parsing, `n`-body support, and residual fallback honestly
- it no longer describes supported operator decomposition as pending for the covered spin-`S` route

Example test shape:

```python
def test_skill_mentions_shared_operator_parsing_and_n_body_support():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "shared parser core" in text
    assert "n-body" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
python -m pytest /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- contract assertions fail until docs are updated

- [ ] **Step 3: Update the skill contract and run the focused verification bundle**

Update `SKILL.md` so it reflects:
- shared LaTeX plus compact operator parsing
- sparse expansion into canonical spin-`S` terms
- broad `n`-body support with readable-block classification when available and residual fallback otherwise

Then run:

```bash
python -m pytest \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_operator_expression_parser.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_decompose_local_term.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_spin_s_pipeline.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py \
  /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py -q
```

Expected:
- all focused spin-`S` parser / pipeline / contract tests pass

- [ ] **Step 4: Commit**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/SKILL.md \
  translation-invariant-spin-model-simplifier/tests/test_skill_contracts.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "docs: finalize spin-S operator simplifier contract"
```

---

## Execution Notes

- Keep changes compatible with the current matrix and tensor decomposition route.
- Do not remove the old projection gate until the supported operator path is covered by tests.
- Prefer narrow, explicit rewrite rules over broad symbolic simplification.
- When a term is parsed successfully but not readable physically, preserve it as canonical residual structure.
- Respect the existing local uncommitted edits in:
  - `translation-invariant-spin-model-simplifier/SKILL.md`
  - `translation-invariant-spin-model-simplifier/scripts/cli/render_simplified_model_report.py`
  - `translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py`
  - `translation-invariant-spin-model-simplifier/tests/test_simplify_text_input_pipeline.py`
