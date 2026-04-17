# Spin-S Final Phase Design

## Goal

Push the `translation-invariant-spin-model-simplifier` spin-`S` path to a final-phase architecture that can accept broad operator-style inputs, normalize them through one shared internal representation, expand them into local spin-`S` multipole terms when needed, and classify readable physical blocks when possible without depending on fragile, case-by-case string rules.

The immediate target is not prettier output. The target is broad, robust coverage:

- one shared parsing core for LaTeX-like expressions and compact programmatic operator strings
- support for generic `n`-body operator monomials, not only one-body or two-body cases
- graceful fallback to canonical residual structure when an expression cannot be mapped into a named readable block
- compatibility with the existing matrix-based and multipole-based paths instead of replacing them

## Current State

The repository already supports several important spin-`S` building blocks:

- local spin-multipole basis generation in `scripts/simplify/spin_multipole_basis.py`
- matrix-based decomposition into ranked multipole labels in `scripts/simplify/decompose_local_term.py`
- canonicalization and readable-block promotion for some multipolar couplings
- residual summaries that preserve unmatched higher-rank structure

This means spin-`S` is no longer blocked at the old "basis only" phase. The remaining gap is the operator-expression route.

The clearest recorded failure is the FeI2 validation result in:

- `run/codex/spin-effective-Hamiltonian/FeI2/results/spin_s_fei2_validation_20260416-205402.md`

There the effective-model operator text was accepted as an `operator` representation, but decomposition fell back to a single `raw-operator` term, which then failed canonicalization with:

- `ValueError: unsupported factor label: raw-operator`

In other words, the main blocker is not spin-`S` algebra itself. The blocker is that the current operator parser only recognizes a narrow set of hard-coded bilinear patterns and has no general intermediate representation for broader operator products.

## User-Approved Scope

The approved direction for this work is:

- prioritize broad generality over polished output formatting
- keep the implementation lightweight and efficient rather than turning it into a full CAS
- support both LaTeX/operator-style expressions and compact programmatic operator strings
- route both syntaxes through a shared parser core
- preserve and extend readable physical-block classification when possible
- support `n`-body operator terms, not just two-body interactions
- keep unknown or partially matched structure as canonical residual terms instead of failing or silently dropping information

## Non-Goals

This final-phase design deliberately does not attempt:

- a full symbolic algebra system
- arbitrary symbolic simplification of mathematically equivalent but structurally unrelated expressions
- automatic invention of new physics-facing names for every possible `n`-body multipole combination
- a major redesign of the report renderer
- replacing the existing matrix/tensor decomposition path

The first implementation should stay honest: broad parsing and canonicalization first, readable labeling second.

## Design Overview

### 1. Shared Operator Front End

Add a shared operator front end that converts both supported text forms into one AST:

- LaTeX-like forms such as `S_i^z S_j^z`, `S_i^+ S_j^-`, `Q_i^{xy} Q_j^{xy}`
- compact programmatic forms such as `Sz@0 Sz@1`, `Sp@0 Sm@1`, `T2_0@0 T2_c1@1`, or higher-body products

The parser only needs a bounded operator grammar:

- scalar coefficients
- sums and differences
- products
- parenthesized groups
- site-tagged local operator factors
- common spin aliases such as `Sx`, `Sy`, `Sz`, `S+`, `S-`
- multipole labels such as `T2_0`, `T3_c1`, `T4_s2`

This front end should be syntax-oriented, not physics-oriented. It should parse the expression faithfully before any readable-block interpretation is attempted.

### 2. Normalized Monomial Core

After parsing, each expression should be normalized into a sum of monomials with explicit metadata. Each monomial should contain:

- a scalar coefficient
- an ordered tuple of local operator factors
- per-factor fields such as:
  - `site`
  - `family` such as `spin_cartesian`, `spin_ladder`, `multipole`
  - `label`
  - optional rank / component metadata when available

Example normalized monomial shape:

```json
{
  "coefficient": 0.5,
  "factors": [
    {"site": 0, "family": "spin_ladder", "label": "Sp"},
    {"site": 1, "family": "spin_ladder", "label": "Sm"},
    {"site": 2, "family": "spin_cartesian", "label": "Sz"}
  ]
}
```

This monomial layer becomes the real internal source of truth for text-originating operator input, just as canonicalized factor labels are already the source of truth downstream.

### 3. Rule-Based Local Rewrite Layer

Before basis expansion, monomials should pass through a rule-based normalization layer that performs a small set of high-value rewrites:

- convert syntax aliases onto one standard vocabulary
- rewrite known ladder combinations into Cartesian spin components when that mapping is exact and local
- preserve explicit multipole labels if they are already present
- sort commuting factors into a stable canonical order when safe
- merge identical monomials by coefficient

This layer should be intentionally conservative. It should only apply rewrites that are local, exact, and easy to audit.

### 4. Sparse Basis Expansion For Spin-S

Once monomials are normalized, each local factor should be mapped into a site-local operator basis:

- spin-1/2 style Cartesian factors map directly to the known spin basis
- higher-spin local operators can map through the existing spin multipole basis
- already-named multipole factors can pass through without re-expansion

For products, expansion should stay sparse:

- expand only the local factors that need rewriting
- distribute products only as far as needed to produce canonical operator monomials
- merge terms immediately after each local expansion step

The key design requirement is that the parser should support broad `n`-body expressions without requiring dense matrix construction for every text input.

### 5. Canonical Term Bridge

The output of sparse expansion should be converted into the existing canonical term format used by:

- `canonicalize_terms.py`
- `identify_readable_blocks.py`
- `assemble_effective_model.py`

This bridge should preserve:

- `body_order`
- multipole family / rank metadata
- support set and per-site factor labels
- source annotations indicating whether a term came from direct text parsing, local rewrite, or matrix decomposition

The current downstream pipeline should need only minimal changes if this bridge is designed cleanly.

### 6. Readable-Block Classification With Residual Fallback

Readable physical-block classification remains a separate layer after canonicalization.

The classification policy should be:

- if a canonical pattern matches an existing readable block, promote it
- if a family/rank/body-order pattern is recognizable in a generic way, emit a generic readable block such as quadrupolar or octupolar coupling
- if no readable mapping is trustworthy, keep the term in residual form with canonical labels and metadata

This keeps the system broad without pretending to understand more than it does.

## Parsing Model

### Supported Input Forms

The front end should treat the following as first-class:

- compact canonical strings:
  - `Sx@0`
  - `Sz@0 Sz@1`
  - `Sp@0 Sm@1 Sz@2`
  - `T2_0@0 T2_c1@1`
- LaTeX-like spin products:
  - `S_i^z S_j^z`
  - `S_i^+ S_j^- + S_i^- S_j^+`
  - parenthesized sums multiplied by coefficients
- mixed sums of supported local factors across arbitrary site counts

The initial release does not need full free-index tensor algebra. It only needs to parse concrete monomials and sums of monomials.

### Site Handling

Site tags should be normalized onto integer site indices in the internal AST. For document-style expressions:

- `i`, `j`, `k`, ... map onto local support positions `0`, `1`, `2`, ...
- repeated named sites inside one monomial must stay distinct and stable
- the support size is inferred from the distinct sites appearing in the parsed monomial

This keeps parsing local to the repeated interaction term and consistent with the existing translation-invariant local-term model.

### Coefficients

Coefficient handling should support:

- numeric scalars
- named parameters from the normalized payload
- simple products with rational prefactors
- explicit imaginary-unit prefactors when already used by the current bilinear parser

The implementation should reject unsupported coefficient syntax early and clearly, rather than silently demoting the entire expression to `raw-operator`.

## n-Body Support

`n`-body support should be native at the normalized-monomial layer.

That means:

- any monomial may have any number of local factors
- repeated factors on the same site are allowed in the AST
- `body_order` should be derived from the number of distinct sites after normalization
- readable-block classification may still only recognize selected lower-body families in the first release

This is a crucial distinction:

- parsing and canonicalization should be broad
- readable naming may remain partial

An unrecognized four-body or six-body term should survive as a clean canonical residual term, not collapse to an opaque raw string.

## Efficiency Strategy

The implementation should prefer cheap structure-preserving operations:

- parse once into AST
- normalize into sparse monomials
- apply small exact rewrite rules
- perform local sparse expansion only where needed
- merge aggressively after each expansion stage

Avoid:

- dense matrix construction for every operator string
- whole-expression symbolic simplification
- repeated stringify/parse cycles

The matrix path should remain available as a fallback for inputs that are already supplied as matrices or tensors. The new operator path should not force everything through matrices.

## Integration Plan

### New Internal Units

The architecture should introduce focused units, likely under `scripts/simplify/`, for:

- operator AST nodes and parsing
- normalization from AST to monomials
- local rewrite rules
- sparse expansion into canonical factor labels

These units should feed the existing:

- `decompose_local_term.py`
- `canonicalize_terms.py`
- `identify_readable_blocks.py`

### Minimal Downstream Changes

Downstream modules should be updated only where needed to:

- accept canonical terms produced from broader text parsing
- preserve `body_order > 2`
- surface residual higher-body structure without error
- keep existing readable-block behavior for known one-body and two-body patterns

### Backward Compatibility

Existing supported cases must keep working:

- matrix/tensor decomposition
- already-supported compact operator-basis strings
- FeI2 reporting paths that currently rely on matrix fallback

The new operator route should reduce the need for matrix fallback, but not remove it.

## Testing Strategy

The implementation should be driven by tests that prove broadness rather than one-off patches.

Required coverage includes:

- LaTeX-like and compact-string inputs that normalize to the same canonical terms
- `n`-body operator monomials surviving parsing, canonicalization, and residual assembly
- known bilinear cases continuing to map into readable blocks
- higher-rank multipole terms remaining compatible with current readable-block promotion
- unsupported syntax failing clearly at the parser boundary rather than at late canonicalization
- FeI2 operator-route regressions no longer collapsing into `raw-operator` for supported effective-model terms

## Success Criteria

This work should count as "spin-S final phase reached" when all of the following are true:

- text-originating spin-`S` operator input no longer depends on ad hoc bilinear regexes as the only non-matrix path
- supported LaTeX and compact operator strings share one normalization core
- generic `n`-body operator terms can enter canonicalization and survive into residual output
- readable-block extraction still works for the known two-body and multipole families
- unsupported text patterns fail explicitly and locally, without late `raw-operator` canonicalization crashes

## Risks And Guardrails

Main risks:

- overbuilding a symbolic engine that the project does not need
- introducing broad parsing but unstable canonical labels
- accidentally breaking the existing matrix-based pipeline

Guardrails:

- keep the grammar intentionally small
- make normalization rules explicit and test-driven
- preserve a canonical residual path for everything not yet readable
- treat output-format changes as secondary and optional

## Recommended First Slice

The first implementation slice should focus on one narrow but general backbone:

1. parse compact strings and LaTeX-like bilinear / multilinear products into one AST
2. normalize to monomials with site-tagged factors
3. convert supported spin aliases into canonical local factor labels
4. hand those labels into the existing canonicalization pipeline
5. verify that supported FeI2 operator terms no longer degrade to `raw-operator`

Once that backbone is stable, broader multipole and higher-body classification can be layered on without changing the core representation.
