# Natural-Language Document Input Protocol Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a protocol-driven natural-language and document-input front end so the skill can accept freeform text, LaTeX fragments, and `.tex`-style paper inputs, build a structured intermediate extraction record, and land into current runnable payloads when the extracted model is unambiguous.

**Architecture:** Keep `SKILL.md` as the single top-level entrypoint, but add one new skill-facing reference contract plus one focused Python helper module for document-input extraction and landing. The implementation should lock the new contract with tests first, then add the reference docs, then implement a small extraction/landing layer that keeps current downstream simplifier scripts unchanged as much as possible.

**Tech Stack:** Python 3, `unittest`/`pytest`, existing `scripts/input/` modules, skill-facing Markdown docs under `reference/`, regression fixtures under `tests/`

---

## File Structure

**Create:**
- `reference/natural-language-input-protocol.md`
- `scripts/input/document_input_protocol.py`
- `tests/test_document_input_protocol.py`
- `tests/data/fei2_document_input.tex`

**Modify:**
- `SKILL.md`
- `reference/README.md`
- `scripts/input/__init__.py`
- `scripts/input/normalize_input.py`
- `tests/test_normalize_input.py`
- `tests/test_skill_reference_docs.py`

**Why these files:**
- `reference/natural-language-input-protocol.md` becomes the skill-facing contract for broad text inputs.
- `scripts/input/document_input_protocol.py` owns detection, section segmentation, candidate extraction, ambiguity reporting, and payload landing for document-style inputs.
- `scripts/input/normalize_input.py` remains the canonical payload-normalization entrypoint, but learns how to accept the new extraction result without reimplementing the whole protocol inline.
- `tests/test_document_input_protocol.py` captures broad-input regression behavior at the Python API level.
- `tests/data/fei2_document_input.tex` gives the suite a stable paper-style fixture independent of a user workspace path.
- `tests/test_skill_reference_docs.py` must be updated because the retained `reference/` file set is currently hard-coded.

### Task 1: Lock the Reference-Contract and Broad-Input Expectations with Tests

**Files:**
- Create: `tests/test_document_input_protocol.py`
- Create: `tests/data/fei2_document_input.tex`
- Modify: `tests/test_skill_reference_docs.py`
- Test: `tests/test_document_input_protocol.py`
- Test: `tests/test_skill_reference_docs.py`

- [ ] **Step 1: Write the failing protocol tests**

```python
class DocumentInputProtocolTests(unittest.TestCase):
    def test_detect_input_kind_marks_tex_documents(self):
        result = detect_input_kind(
            source_text="\\section*{Effective Hamiltonian}\\n\\begin{equation}H=..."
        )
        self.assertEqual(result["source_kind"], "tex_document")

    def test_extract_intermediate_record_separates_multiple_model_candidates(self):
        fixture = Path("tests/data/fei2_document_input.tex").read_text(encoding="utf-8")
        record = build_intermediate_record(source_text=fixture, source_path="tests/data/fei2_document_input.tex")
        self.assertEqual([c["name"] for c in record["model_candidates"]], ["toy", "effective", "matrix_form"])
        self.assertTrue(record["ambiguities"])

    def test_land_selected_candidate_to_payload_preserves_unsupported_features(self):
        record = {... "selected_model_candidate": "effective", ...}
        landed = land_intermediate_record(record)
        self.assertEqual(landed["representation"], "operator")
        self.assertIn("unsupported_features", landed)
```

- [ ] **Step 2: Update the reference-doc contract test to expect the new protocol file**

```python
EXPECTED_REFERENCE_FILES = {
    "README.md",
    "environment.md",
    "fallback-rules.md",
    "input-schema.md",
    "natural-language-input-protocol.md",
}

EXPECTED_SKILL_REFERENCES = {
    "reference/environment.md",
    "reference/fallback-rules.md",
    "reference/input-schema.md",
    "reference/natural-language-input-protocol.md",
}
```

- [ ] **Step 3: Run the new tests to verify they fail before implementation**

Run: `python3 -m pytest tests/test_document_input_protocol.py tests/test_skill_reference_docs.py -q`
Expected: FAIL because the new protocol module, fixture-backed extraction behavior, and reference file do not exist yet.

- [ ] **Step 4: Commit the failing-test baseline**

```bash
git add -f tests/test_document_input_protocol.py tests/data/fei2_document_input.tex tests/test_skill_reference_docs.py docs/superpowers/plans/2026-04-16-natural-language-document-input-protocol.md
git commit -m "test: cover document input protocol contract"
```

### Task 2: Add the Skill-Facing Protocol Reference and Wire the Main Skill to It

**Files:**
- Create: `reference/natural-language-input-protocol.md`
- Modify: `reference/README.md`
- Modify: `SKILL.md`
- Test: `tests/test_skill_reference_docs.py`

- [ ] **Step 1: Write the new protocol reference document**

```md
# Natural-Language Input Protocol

## Scope
- freeform natural language
- LaTeX fragments
- partial/full `.tex` documents

## Intermediate Extraction Schema
- source_document
- document_sections
- model_candidates
- system_context
- lattice_model
- hamiltonian_model
- parameter_registry
- ambiguities
- confidence_report
- unsupported_features
```

- [ ] **Step 2: Update the retained-reference README**

```md
- `natural-language-input-protocol.md`
  Defines the upstream extraction protocol for natural-language, LaTeX,
  and document-style inputs before they are normalized into runnable payloads.
```

- [ ] **Step 3: Update `SKILL.md` to require protocol-first handling for broad text inputs**

```md
3. If the input is natural-language, LaTeX, or a document-style source, read
   `reference/natural-language-input-protocol.md` and construct an intermediate
   extraction record before normalization.
4. Normalize the raw model with `scripts/input/normalize_input.py`.
```

- [ ] **Step 4: Run the doc-contract suite**

Run: `python3 -m pytest tests/test_skill_reference_docs.py -q`
Expected: PASS

- [ ] **Step 5: Commit the reference-layer changes**

```bash
git add -f reference/natural-language-input-protocol.md SKILL.md reference/README.md tests/test_skill_reference_docs.py
git commit -m "docs: add natural-language document input protocol"
```

### Task 3: Implement a Focused Document-Input Extraction Module

**Files:**
- Create: `scripts/input/document_input_protocol.py`
- Modify: `scripts/input/__init__.py`
- Modify: `tests/test_document_input_protocol.py`
- Test: `tests/test_document_input_protocol.py`

- [ ] **Step 1: Implement input-kind detection and section segmentation**

```python
def detect_input_kind(source_text: str, source_path: str | None = None) -> dict:
    lowered = (source_text or "").lower()
    if source_path and source_path.endswith(".tex"):
        return {"source_kind": "tex_document"}
    if "\\begin{equation}" in source_text or "\\section" in source_text:
        return {"source_kind": "tex_document"}
    if "$" in source_text or "\\[" in source_text:
        return {"source_kind": "latex_fragment"}
    return {"source_kind": "natural_language"}


def segment_document_sections(source_text: str) -> dict:
    return {
        "structure_sections": [...],
        "model_sections": [...],
        "parameter_sections": [...],
        "analysis_sections": [...],
    }
```

- [ ] **Step 2: Implement model-candidate extraction for the first supported slice**

```python
def extract_model_candidates(source_text: str) -> list[dict]:
    candidates = []
    if "Toy Hamiltonian" in source_text:
        candidates.append({"name": "toy", "role": "simplified", "source_span": "Toy Hamiltonian"})
    if "Effective Hamiltonian" in source_text:
        candidates.append({"name": "effective", "role": "main", "source_span": "Effective Hamiltonian"})
    if "Equivalent Exchange-Matrix Form" in source_text:
        candidates.append({"name": "matrix_form", "role": "equivalent_form", "source_span": "Equivalent Exchange-Matrix Form"})
    return candidates
```

- [ ] **Step 3: Implement intermediate-record construction with explicit ambiguity capture**

```python
def build_intermediate_record(source_text: str, source_path: str | None = None) -> dict:
    sections = segment_document_sections(source_text)
    candidates = extract_model_candidates(source_text)
    ambiguities = []
    if len([c for c in candidates if c["role"] in {"main", "simplified"}]) > 1:
        ambiguities.append({
            "id": "model_candidate_selection",
            "blocks_landing": True,
            "question": "Multiple Hamiltonian candidates were detected. Which one should I use?",
        })
    return {
        "source_document": {...},
        "document_sections": sections,
        "model_candidates": candidates,
        "ambiguities": ambiguities,
        "unsupported_features": [],
    }
```

- [ ] **Step 4: Export the new module at the package boundary**

```python
from .document_input_protocol import (
    build_intermediate_record,
    detect_input_kind,
    land_intermediate_record,
)
```

- [ ] **Step 5: Run the focused extraction tests**

Run: `python3 -m pytest tests/test_document_input_protocol.py -q`
Expected: PASS on input-kind detection and intermediate-record extraction tests; landing-specific tests may still fail until Task 4.

- [ ] **Step 6: Commit the extraction module**

```bash
git add -f scripts/input/document_input_protocol.py scripts/input/__init__.py tests/test_document_input_protocol.py tests/data/fei2_document_input.tex
git commit -m "feat: add document input extraction protocol module"
```

### Task 4: Land the Intermediate Record into Current Payloads Through `normalize_input.py`

**Files:**
- Modify: `scripts/input/document_input_protocol.py`
- Modify: `scripts/input/normalize_input.py`
- Modify: `tests/test_document_input_protocol.py`
- Modify: `tests/test_normalize_input.py`
- Test: `tests/test_document_input_protocol.py`
- Test: `tests/test_normalize_input.py`

- [ ] **Step 1: Add landing helpers that either produce a payload or a blocking interaction**

```python
def land_intermediate_record(record: dict) -> dict:
    blocking = [entry for entry in record.get("ambiguities", []) if entry.get("blocks_landing")]
    if blocking:
        question = blocking[0]
        return {
            "interaction": {
                "status": "needs_input",
                "id": question["id"],
                "question": question["question"],
            }
        }

    return {
        "representation": "operator",
        "support": [0, 1],
        "expression": record["hamiltonian_model"]["operator_expression"],
        "parameters": record.get("parameter_registry", {}),
        "user_notes": "Generated from document input protocol",
        "unsupported_features": record.get("unsupported_features", []),
    }
```

- [ ] **Step 2: Teach `normalize_input.py` to accept a pre-extracted document record**

```python
if payload.get("representation") == "natural_language" and payload.get("document_intermediate"):
    landed = land_intermediate_record(payload["document_intermediate"])
    if landed.get("interaction", {}).get("status") == "needs_input":
        normalized = normalize_freeform_text(payload["description"])
        normalized["interaction"] = landed["interaction"]
        normalized["unsupported_features"] = landed.get("unsupported_features", [])
        return normalized
    payload = {**payload, **landed}
```

- [ ] **Step 3: Add normalization tests for both landing and blocking branches**

```python
def test_normalize_input_accepts_document_intermediate_that_lands_to_operator(self):
    payload = {
        "representation": "natural_language",
        "description": "Effective Hamiltonian text",
        "document_intermediate": {... "ambiguities": [] ...},
    }
    normalized = normalize_input(payload)
    self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")


def test_normalize_input_preserves_needs_input_from_document_intermediate(self):
    payload = {
        "representation": "natural_language",
        "description": "Toy plus effective Hamiltonian",
        "document_intermediate": {... "ambiguities": [{"blocks_landing": True, ...}] ...},
    }
    normalized = normalize_input(payload)
    self.assertEqual(normalized["interaction"]["status"], "needs_input")
```

- [ ] **Step 4: Run the focused normalization suites**

Run: `python3 -m pytest tests/test_document_input_protocol.py tests/test_normalize_input.py -q`
Expected: PASS

- [ ] **Step 5: Commit the landing integration**

```bash
git add -f scripts/input/document_input_protocol.py scripts/input/normalize_input.py tests/test_document_input_protocol.py tests/test_normalize_input.py
git commit -m "feat: land document input extraction into normalized payloads"
```

### Task 5: Add a Worked Example and Run the Verification Sweep

**Files:**
- Modify: `reference/natural-language-input-protocol.md`
- Modify: `tests/test_document_input_protocol.py`
- Test: `tests/test_document_input_protocol.py`
- Test: `tests/test_skill_reference_docs.py`
- Test: `tests/test_normalize_input.py`
- Test: `tests/test_skill_contracts.py`

- [ ] **Step 1: Add a compact worked example based on the FeI2-style document workflow**

```md
## Worked Example: FeI2-style `.tex` Input

- detect `toy`, `effective`, and `matrix_form` candidates
- stop with `model_candidate_selection` until the user selects `effective`
- bind the parameter table into `parameter_registry`
- land to `operator` payload while carrying unmatched matrix-form notes in
  `unsupported_features`
```

- [ ] **Step 2: Add one example-backed regression assertion**

```python
def test_fei2_style_fixture_requires_model_selection_before_landing(self):
    fixture = Path("tests/data/fei2_document_input.tex").read_text(encoding="utf-8")
    record = build_intermediate_record(source_text=fixture, source_path="tests/data/fei2_document_input.tex")
    landed = land_intermediate_record(record)
    self.assertEqual(landed["interaction"]["id"], "model_candidate_selection")
```

- [ ] **Step 3: Run the full focused verification sweep**

Run: `python3 -m pytest tests/test_document_input_protocol.py tests/test_normalize_input.py tests/test_skill_reference_docs.py tests/test_skill_contracts.py -q`
Expected: PASS

- [ ] **Step 4: Run one adjacent parsing suite for regression coverage**

Run: `python3 -m pytest tests/test_parse_poscar.py tests/test_parse_many_body_hr.py -q`
Expected: PASS

- [ ] **Step 5: Commit the final verification slice**

```bash
git add -f reference/natural-language-input-protocol.md tests/test_document_input_protocol.py tests/test_normalize_input.py
git commit -m "test: verify document input protocol workflow"
```

## Residual Risks

- The first implementation slice should aim for explicit candidate separation and payload landing,
  not full symbolic parsing of arbitrary LaTeX Hamiltonians.
- The new module should stay honest about unsupported features rather than forcing every extracted
  document into a runnable payload.
- Broad document support will still depend on the quality of section extraction heuristics, so the
  first pass should focus on stability for representative `.tex` inputs rather than exhaustive
  paper coverage.
