# Two-Body Local Matrix Backbone Design

## Goal

Refocus the `translation-invariant-spin-model-simplifier` spin-model pipeline around a stable internal backbone for one-body and two-body local terms:

- extract local onsite and two-site interaction candidates from documents, natural-language, LaTeX, or compact operator inputs
- compile those candidates into a uniform `local_matrix_record`
- perform deterministic matrix-based decomposition from that record into canonical operator terms
- interpret the resulting decomposition into readable physical parameters when possible
- preserve unmatched structure as canonical residual terms rather than collapsing back to opaque raw text

The current implementation phase explicitly targets:

- `body_order = 1`
- `body_order = 2`

The design must leave a clean schema-level extension path for future `body_order > 2` support without pretending it is already implemented.

## Why This Design

The current system already has a useful operator-expression path, but the user-approved direction has shifted toward a more stable core:

- organize local interactions by family / shell / support
- treat the local matrix as the main internal object
- let different input styles compile into the same matrix-backed representation
- derive physical parameters such as exchange tensors, DM terms, Kitaev / Gamma forms, or `Jzz/Jpm/Jpmpm/Jzpm` from the decomposed matrix rather than from ad hoc text rules

This is especially well aligned with the current FeI2 effective Hamiltonian input, which contains:

- onsite anisotropy `-D \sum_i (S_i^z)^2`
- family-resolved two-body exchanges
- no explicit multispin terms in the current document payload

## Current-State Constraint

The current FeI2 source at:

- `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/input.tex`

contains:

- one-body single-ion anisotropy
- two-body family-resolved exchange interactions
- nearest-neighbor anisotropic two-body terms with `J_1^{zz}`, `J_1^{\pm}`, `J_1^{\pm\pm}`, and `J_1^{z\pm}`
- no explicit three-body or four-body interaction terms

That makes FeI2 an ideal first regression target for a one-body + two-body matrix backbone.

## Scope

### In Scope For This Phase

- one-body local terms
- two-body local terms
- family-resolved and shell-resolved local term handling
- matrix compilation from:
  - document / natural-language extraction payloads
  - LaTeX operator expressions
  - compact operator strings
  - direct matrix-form inputs
- matrix-based decomposition into canonical terms
- readable interpretation of common one-body and two-body physical terms
- explicit residual handling for terms that are decomposed but not yet mapped to a high-confidence readable label

### Explicitly Out Of Scope For This Phase

- full implementation of three-body and higher-body local terms
- automatic reduction of multispin terms into effective two-body models
- pretending unsupported multispin terms are already handled by the two-body backbone

## Core Internal Object

The new main internal representation should be a support-resolved local matrix object:

```json
{
  "support": [0, 1],
  "body_order": 2,
  "family": "1",
  "geometry_class": "bond",
  "coordinate_frame": "global_xyz",
  "local_basis_order": ["m=1", "m=0", "m=-1"],
  "tensor_product_order": [0, 1],
  "representation": {
    "kind": "matrix",
    "value": [[0.0, 0.0], [0.0, 0.0]]
  },
  "provenance": {
    "source_kind": "operator_text",
    "source_expression": "J_1^{zz} S_i^z S_j^z + ...",
    "parameter_map": {}
  }
}
```

This document calls the object a `local_matrix_record`.

### Required Fields

- `support`
  Ordered list of local support positions used by the repeated local term.

- `body_order`
  Number of support sites. For this phase, only `1` and `2` are fully supported.

- `family`
  Family / shell / user-facing local bond label when applicable, for example `1`, `2`, `0'`, `1'`, `2a'`.

- `geometry_class`
  Current values:
  - `onsite`
  - `bond`

  Future values may include:
  - `cluster`
  - `triangle`
  - `plaquette`

- `coordinate_frame`
  Explicit frame used by the matrix and later physical interpretation.

- `local_basis_order`
  The one-site basis order used to compile and interpret the matrix.

- `tensor_product_order`
  Explicit order of support sites in the tensor-product basis.

- `representation`
  In this phase the authoritative path is `{"kind": "matrix", ...}`.

- `provenance`
  The matrix must remember where it came from so later reporting can stay honest and interpretable.

### Phase Boundary Rule

If `body_order > 2`, the schema may still represent the object, but the current compiler / decomposer path must not pretend full support. It should instead return an explicit unsupported or needs-input result.

## Four-Layer Architecture

### 1. Input Extraction Layer

Responsibilities:

- find candidate local terms in document, natural-language, LaTeX, or structured inputs
- identify whether a candidate is:
  - onsite
  - two-site
  - unresolved
- identify family / shell labels
- extract parameters and coordinate conventions
- preserve ambiguity when extraction is not safe

This layer is allowed to be more flexible and text-oriented. It is not the final algebraic source of truth.

### 2. Matrix Compiler Layer

Responsibilities:

- take an extracted local term candidate
- compile it into a `local_matrix_record`
- fix:
  - support order
  - local basis order
  - tensor-product order
  - coordinate frame
  - family label
- convert supported operator expressions into an explicit onsite or two-site matrix

This is the new core backbone.

The current operator parser / normalizer / sparse-expansion code should become compiler helpers rather than the final main IR.

### 3. Matrix Decomposer Layer

Responsibilities:

- accept a `local_matrix_record`
- decompose it deterministically into canonical operator terms
- preserve metadata needed downstream:
  - `body_order`
  - `family`
  - basis / frame provenance
  - multipole rank / family when inferable

This layer should become the main purpose of `decompose_local_term.py`.

### 4. Physics Interpreter Layer

Responsibilities:

- identify high-confidence physical interpretations of the canonical decomposition
- report:
  - readable blocks
  - family-resolved summaries
  - canonical residual terms

This layer must never silently drop decomposed structure merely because no pretty label exists yet.

## Supported Physics Classes For This Phase

### Tier A: Standard Readable Support

These should be treated as first-class readable physical categories for one-body and two-body terms.

#### One-Body

- Zeeman / `g`-tensor coupling
- single-ion anisotropy
- general onsite quadratic anisotropy tensor

#### Two-Body Bilinear

- isotropic Heisenberg exchange
- XXZ / XYZ exchange
- full symmetric exchange tensor
- DM interaction
- Kitaev interaction
- symmetric off-diagonal `Gamma` / `Gamma'`
- literature-specific local-axis anisotropic exchange forms such as:
  - `Jzz`
  - `Jpm`
  - `Jpmpm`
  - `Jzpm`

### Tier B: Canonical Support With Residual-First Readout Allowed

These should already be decomposable and survivable in canonical form during this phase, even if their readable naming remains more generic.

- biquadratic exchange
- two-site quadrupolar coupling
- more general two-site multipolar couplings
- dipole-dipole interaction
- pseudo-dipolar or compass-like cases not yet given a custom readable label

### Tier C: Schema And Failure-Path Only

These are explicitly not fully implemented in this phase.

- scalar spin chirality
- three-spin interactions
- four-spin cyclic / ring exchange
- general multispin cluster terms

## Bilinear Interpretation Strategy

The readable layer should not rely on text-template recognition as its main truth source.

For two-body bilinear terms, the recommended interpretation order is:

1. extract the general bilinear exchange kernel from the decomposed two-body matrix
2. split it into:
   - isotropic part
   - symmetric traceless part
   - antisymmetric part
3. interpret the antisymmetric part as DM
4. interpret special frame- or convention-dependent cases as:
   - XXZ / XYZ
   - Kitaev / `Gamma` / `Gamma'`
   - `Jzz/Jpm/Jpmpm/Jzpm`

This keeps the matrix as the source of truth while still surfacing user-facing physics when justified.

## Family / Shell Handling

Family is a first-class dimension, not just an input-time filter.

The pipeline must support:

- selected single family
- all-family expansion with family tags preserved downstream
- unresolved family interpretation returning `needs_input`

Family metadata should survive through:

- extraction
- matrix compilation
- decomposition
- canonicalization
- readable interpretation
- residual summaries

## Failure Strategy

The new architecture must fail honestly and locally.

### Case 1: Cannot Safely Compile To Matrix

Examples:

- basis order unresolved
- coordinate frame unresolved
- phase convention unresolved

Required behavior:

- return `needs_input`
- do not invent a matrix

### Case 2: Matrix Compiles But Readable Meaning Is Incomplete

Examples:

- decomposed terms exist
- no current readable block cleanly matches

Required behavior:

- keep canonical decomposition
- keep canonical residual structure
- do not demote to opaque raw text

### Case 3: Higher-Body Term Appears

Examples:

- explicit three-site or four-site support

Required behavior:

- schema may represent it
- current phase returns explicit unsupported or needs-input status
- do not silently reduce it to a false two-body object

## Migration Plan For Existing Modules

### Modules To Keep As Extraction / Orchestration

- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/input/normalize_input.py`
- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/cli/simplify_text_input.py`

### Modules To Reposition As Compiler Helpers

- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_parser.py`
- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_normalizer.py`
- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/operator_expression_sparse_expand.py`

These should be treated as front-end helpers for compiling supported operator text into matrices, not as the final backbone.

### Module To Recenter Around Matrix Decomposition

- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/decompose_local_term.py`

### Modules To Keep As Downstream Consumers

- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/canonicalize_terms.py`
- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/identify_readable_blocks.py`
- `/data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier/scripts/simplify/assemble_effective_model.py`

## Acceptance Criteria

This design should count as implemented for the current phase only when all of the following hold.

### Input Coverage

Supported one-body and two-body local terms can be compiled from:

- document operator text
- document matrix-form text
- natural-language-extracted structured payloads
- compact operator strings

### Family Coverage

Supported family labels survive through the whole pipeline, including:

- `1`
- `2`
- `3`
- `0'`
- `1'`
- `2a'`

### Physics Coverage

Readable support exists for:

- single-ion anisotropy
- Zeeman / `g`-tensor
- Heisenberg
- XXZ / XYZ
- general exchange tensor
- DM
- Kitaev / `Gamma` / `Gamma'`
- `Jzz/Jpm/Jpmpm/Jzpm`

Canonical support without data loss exists for:

- biquadratic exchange
- two-site multipolar couplings

### Honest Failure Coverage

- unresolved matrix compilation returns `needs_input`
- unsupported higher-body terms do not masquerade as two-body
- unsupported readable interpretation does not collapse canonical structure into opaque fallback

## Recommended Immediate Next Plan

The next implementation plan should proceed in this order:

1. define the `local_matrix_record` schema and compiler contract
2. add a two-body matrix compiler for operator-text and matrix-form inputs
3. recenter `decompose_local_term.py` around matrix decomposition
4. extend readable bilinear interpretation to include DM and general exchange tensor decomposition
5. preserve residual support for biquadratic and multipolar two-site terms
