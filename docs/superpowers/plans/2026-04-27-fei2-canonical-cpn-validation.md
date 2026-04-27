# FeI2 Canonical CPN Validation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-tracked, test-first FeI2 canonical `cpn_pair_model` validation slice that proves the canonical fixture reproduces the expected ordered state and representative spectrum targets from the Sunny SU(3) FeI2 baseline.

**Architecture:** Start from one manual canonical `CP^2` fixture plus one reference snapshot file. Use the canonical payload and pipeline entry points already in the repo for ground-state validation, then route the same canonical model into the SUN-GSWT payload/driver path with the official FeI2 path encoded explicitly in test data. Keep the first regression narrow: one tracked fixture, one tracked reference snapshot, one focused validation test module, and only the minimal support code needed to make those tests deterministic.

**Tech Stack:** Python, JSON fixtures, `unittest`, existing canonical CPN builders, existing classical pipeline, existing SUN-GSWT payload/driver, `python -m pytest`

---

### Task 1: Add The FeI2 Canonical Fixture And Reference Snapshot

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_payload.json`
- Create: `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json`
- Create: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`

- [ ] **Step 1: Write the failing fixture-contract test**

Put the first test in `test_fei2_canonical_cpn_validation.py` and make it load the two JSON files that do not exist yet.

```python
import json
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.cpn_pair_model import validate_cpn_pair_model


FIXTURE_DIR = SKILL_ROOT / "tests" / "data"
PAYLOAD_PATH = FIXTURE_DIR / "fei2_canonical_cpn_payload.json"
REFERENCE_PATH = FIXTURE_DIR / "fei2_canonical_cpn_reference.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class FeI2CanonicalCpnValidationTests(unittest.TestCase):
    def test_fixture_is_canonical_cp2_model(self):
        payload = _load_json(PAYLOAD_PATH)
        reference = _load_json(REFERENCE_PATH)

        validate_cpn_pair_model(payload)

        self.assertEqual(payload["model_family"], "cpn_pair_model")
        self.assertEqual(payload["classical_family"], "cpn")
        self.assertEqual(payload["local_dimension"], 3)
        self.assertTrue(payload["bond_terms"])
        self.assertTrue(payload["onsite_terms"])
        self.assertEqual(reference["ordering"]["allowed_q_vectors"][0], [0.0, -0.25, 0.25])
```

- [ ] **Step 2: Run the new test and verify it fails**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k fixture_is_canonical_cp2_model`

Expected: FAIL because the new fixture files do not exist yet.

- [ ] **Step 3: Add the minimal canonical payload fixture and reference snapshot**

Populate `fei2_canonical_cpn_payload.json` with the first canonical FeI2 baseline:

- `schema_version = 1`
- `model_family = "cpn_pair_model"`
- `classical_family = "cpn"`
- `local_dimension = 3`
- explicit `structure`
- explicit `bond_terms`
- explicit `onsite_terms` carrying `D = 2.165`
- fixed `pair_basis_order = "site_i_major_site_j_minor"`

Populate `fei2_canonical_cpn_reference.json` with the first comparison metadata:

```json
{
  "ordering": {
    "supercell_shape": [1, 2, 4],
    "allowed_q_vectors": [
      [0.0, -0.25, 0.25],
      [0.25, 0.0, 0.25],
      [-0.25, 0.25, 0.25]
    ],
    "rounding_tolerance": 1e-6
  },
  "spectrum": {
    "path_labels": ["G", "M1", "M2", "K", "M2", "G"],
    "path_nodes": [
      [0.0, 0.0, 0.0],
      [1.0, 0.0, 0.0],
      [0.0, 1.0, 0.0],
      [0.5, 0.0, 0.0],
      [0.0, 1.0, 0.0],
      [0.0, 0.0, 0.0]
    ],
    "energy_tolerance_mev": 0.05,
    "node_samples": []
  }
}
```

- [ ] **Step 4: Run the fixture test and verify it passes**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k fixture_is_canonical_cp2_model`

Expected: PASS

- [ ] **Step 5: Commit the fixture scaffold**

```bash
git add \
  translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_payload.json \
  translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py
git commit -m "test: add FeI2 canonical CPN validation fixtures"
```

### Task 2: Add The Ground-State End-To-End Regression

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json`
- Test: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`

- [ ] **Step 1: Write the failing ground-state regression through the canonical pipeline**

Extend the test file with a helper that normalizes q-vectors and checks symmetry-equivalent matches, then add a ground-state test that enters through `solve_from_parsed_payload`.

```python
from cli.solve_pseudospin_orbital_pipeline import solve_from_parsed_payload


def _rounded_q(vector, digits=6):
    return [round(float(value), digits) for value in vector]


def _matches_any_allowed_q(actual_q, allowed_q_vectors, digits=6):
    rounded_actual = _rounded_q(actual_q, digits=digits)
    return any(rounded_actual == _rounded_q(candidate, digits=digits) for candidate in allowed_q_vectors)


class FeI2CanonicalCpnValidationTests(unittest.TestCase):
    def test_ground_state_matches_sunny_fei2_ordering_manifold(self):
        payload = _load_json(PAYLOAD_PATH)
        reference = _load_json(REFERENCE_PATH)

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = solve_from_parsed_payload(
                payload,
                output_dir=Path(tmpdir) / "out",
                docs_dir=Path(tmpdir) / "docs",
                compile_pdf=False,
                classical_method="cpn-generalized-lt",
                run_gswt=False,
            )

            result_payload = _load_json(Path(manifest["artifacts"]["result_payload"]))

        final_state = result_payload["solver"]["classical_state_result"]["classical_state"]
        ordering = final_state["ordering"]
        self.assertTrue(
            _matches_any_allowed_q(
                ordering["q_vector"],
                reference["ordering"]["allowed_q_vectors"],
            )
        )
```

- [ ] **Step 2: Run the ground-state test and verify it fails**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k ground_state_matches_sunny_fei2_ordering_manifold`

Expected: FAIL because either the fixture, the supercell expectations, or the result-path assumptions are not yet aligned with the actual pipeline output.

- [ ] **Step 3: Make the minimal changes needed for deterministic ground-state comparison**

Adjust only what the failure shows is missing:

- if the fixture needs extra retained-local-space metadata, add it to `fei2_canonical_cpn_payload.json`
- if the test should read the final state from a different manifest key, fix the test helper
- if the pipeline does not preserve ordering metadata for this route, make the smallest change in:
  - `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`
  - or `translation-invariant-spin-model-simplifier/scripts/common/classical_output_compatibility.py`
  so the final classical state's `ordering.q_vector` and `ordering.supercell_shape` survive into the result payload

Minimal compatibility target:

```python
ordering = final_state.get("ordering", {})
self.assertIn("q_vector", ordering)
self.assertIn("supercell_shape", ordering)
```

- [ ] **Step 4: Re-run the ground-state test and verify it passes**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k ground_state_matches_sunny_fei2_ordering_manifold`

Expected: PASS

- [ ] **Step 5: Commit the ground-state regression**

```bash
git add \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py \
  translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json \
  translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/scripts/common/classical_output_compatibility.py
git commit -m "test: validate FeI2 canonical ground state"
```

### Task 3: Add An Explicit Official FeI2 Spectrum Path Contract

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`

- [ ] **Step 1: Write a failing payload-level test for an explicit FeI2 path override**

Add a focused test in `test_build_sun_gswt_payload.py` that proves the payload builder can export the official FeI2 path instead of always using the default high-symmetry path.

```python
def test_build_payload_accepts_explicit_fei2_reference_path_override(self):
    model = {
        "model_type": "sun_gswt_classical",
        "classical_manifold": "CP^(N-1)",
        "local_dimension": 3,
        "pair_basis_order": "site_i_major_site_j_minor",
        "local_basis_labels": ["m=1", "m=0", "m=-1"],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "positions": [[0.0, 0.0, 0.0]],
        "bond_tensors": [
            {
                "R": [1, 0, 0],
                "tensor_shape": [3, 3, 3, 3],
                "pair_matrix": [
                    [_serialize_complex(1.0 if row == col else 0.0) for col in range(9)]
                    for row in range(9)
                ],
                "tensor": _permutation_tensor(3),
            }
        ],
        "spectrum_path_override": {
            "labels": ["G", "M1", "M2", "K", "M2", "G"],
            "nodes": [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.5, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            "samples_per_segment": 8,
        },
    }
    classical_state = {
        "manifold": "CP^(N-1)",
        "supercell_shape": [1, 2, 4],
        "local_rays": [
            {
                "cell": [0, 0, 0],
                "vector": [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
            }
        ],
    }

    payload = build_sun_gswt_payload(model, classical_state=classical_state)

    self.assertEqual(payload["path"]["labels"], ["G", "M1", "M2", "K", "M2", "G"])
    self.assertEqual(payload["q_path"][0], [0.0, 0.0, 0.0])
```

- [ ] **Step 2: Run the payload-level test and verify it fails**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py -k explicit_fei2_reference_path_override`

Expected: FAIL because `build_sun_gswt_payload.py` currently always resolves the default path internally.

- [ ] **Step 3: Implement the minimal explicit-path override in `build_sun_gswt_payload.py`**

Add one narrow override path rather than redesigning the whole builder API:

```python
def _resolve_explicit_q_path(path_override):
    nodes = [[float(component) for component in node] for node in path_override["nodes"]]
    labels = [str(label) for label in path_override["labels"]]
    samples_per_segment = int(path_override.get("samples_per_segment", 32))
    q_path, node_indices = _interpolate_q_path(nodes, samples_per_segment=samples_per_segment)
    return {"q_path": q_path, "path": {"labels": labels, "node_indices": node_indices}}


def _resolve_q_path_summary(model):
    path_override = model.get("spectrum_path_override")
    if isinstance(path_override, dict):
        return _resolve_explicit_q_path(path_override)
    return _resolve_default_q_path(model)
```

Then switch `build_sun_gswt_payload()` from `_resolve_default_q_path(adapted_model)` to `_resolve_q_path_summary(adapted_model)`.

- [ ] **Step 4: Extend the FeI2 validation test to assert the official path is used**

In `test_fei2_canonical_cpn_validation.py`, build the SUN-GSWT payload from the canonical fixture plus the reference path and assert the exported labels and node endpoints match the reference JSON exactly.

```python
self.assertEqual(gswt_payload["path"]["labels"], reference["spectrum"]["path_labels"])
self.assertEqual(gswt_payload["q_path"][0], reference["spectrum"]["path_nodes"][0])
self.assertEqual(gswt_payload["q_path"][-1], reference["spectrum"]["path_nodes"][-1])
```

- [ ] **Step 5: Re-run the path tests and verify they pass**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k 'explicit_fei2_reference_path_override or official_path'`

Expected: PASS

- [ ] **Step 6: Commit the explicit-path support**

```bash
git add \
  translation-invariant-spin-model-simplifier/scripts/lswt/build_sun_gswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py \
  translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json
git commit -m "feat: add explicit FeI2 GSWT path override"
```

### Task 4: Add The Representative Spectrum Regression

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py`

- [ ] **Step 1: Write the failing representative-spectrum regression**

Add a test that:

1. loads the canonical fixture
2. runs the ground-state route
3. builds the SUN-GSWT payload using the explicit official path
4. runs `run_sun_gswt(...)`
5. compares representative node energies against the reference snapshot

```python
from classical.build_sun_gswt_classical_payload import build_sun_gswt_classical_payload
from lswt.build_sun_gswt_payload import build_sun_gswt_payload
from lswt.sun_gswt_driver import run_sun_gswt


def _representative_band_table(gswt_result):
    table = {}
    for entry in gswt_result["dispersion"]:
        key = tuple(round(float(value), 6) for value in entry["q"])
        table[key] = [float(value) for value in entry.get("bands", [])]
    return table


class FeI2CanonicalCpnValidationTests(unittest.TestCase):
    def test_spectrum_matches_representative_sunny_fei2_nodes(self):
        payload = _load_json(PAYLOAD_PATH)
        reference = _load_json(REFERENCE_PATH)

        classical_model = build_sun_gswt_classical_payload(payload)
        classical_state = self._solve_ground_state(payload)
        classical_model["spectrum_path_override"] = {
            "labels": reference["spectrum"]["path_labels"],
            "nodes": reference["spectrum"]["path_nodes"],
            "samples_per_segment": 8,
        }
        gswt_payload = build_sun_gswt_payload(classical_model, classical_state=classical_state)
        gswt_result = run_sun_gswt(gswt_payload)

        self.assertEqual(gswt_result["status"], "ok")
        table = _representative_band_table(gswt_result)
        for sample in reference["spectrum"]["node_samples"]:
            q_key = tuple(sample["q"])
            actual = table[q_key]
            self.assertEqual(len(actual), sample["branch_count"])
            self.assertAlmostEqual(actual[sample["band_index"]], sample["energy_mev"], places=2)
```

- [ ] **Step 2: Run the spectrum test and verify it fails**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py -k spectrum_matches_representative_sunny_fei2_nodes`

Expected: FAIL because the reference node table is not filled in yet and the builder/driver path may still need small alignment fixes.

- [ ] **Step 3: Fill the reference snapshot with the smallest stable comparison table**

Update `fei2_canonical_cpn_reference.json` with:

- `branch_count`
- `q`
- `band_index`
- `energy_mev`

for a small number of node samples taken from the official Sunny FeI2 comparison path. Keep the first table intentionally small, for example:

```json
"node_samples": [
  {"q": [0.0, 0.0, 0.0], "branch_count": 8, "band_index": 0, "energy_mev": 0.00},
  {"q": [1.0, 0.0, 0.0], "branch_count": 8, "band_index": 0, "energy_mev": 1.23},
  {"q": [0.0, 1.0, 0.0], "branch_count": 8, "band_index": 1, "energy_mev": 2.34}
]
```

Extract the numeric values from the approved Sunny FeI2 baseline before committing the snapshot file. Do not invent, interpolate, or eyeball them from a rendered plot.

- [ ] **Step 4: Add one driver-level regression for path metadata preservation**

Extend `test_run_sun_gswt_driver.py` with a narrow unit test that confirms the driver keeps the explicit path labels and node metadata in the successful result.

```python
def test_driver_preserves_explicit_fei2_path_metadata(self):
    payload = _valid_gswt_payload(local_dimension=3)
    payload["path"] = {"labels": ["G", "M1", "M2", "K", "M2", "G"], "node_indices": [0, 8, 16, 24, 32, 40]}
    payload["q_path"] = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]

    class Completed:
        stdout = json.dumps({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}, "payload_kind": "sun_gswt_prototype", "dispersion": []})

    with patch("lswt.sun_gswt_driver.subprocess.run", return_value=Completed()):
        result = run_sun_gswt(payload)

    self.assertEqual(result["path"]["labels"], ["G", "M1", "M2", "K", "M2", "G"])
```

- [ ] **Step 5: Re-run the spectrum slice and verify it passes**

Run: `python -m pytest -q translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py -k 'spectrum_matches_representative_sunny_fei2_nodes or explicit_fei2_path_metadata'`

Expected: PASS

- [ ] **Step 6: Commit the spectrum regression**

```bash
git add \
  translation-invariant-spin-model-simplifier/tests/data/fei2_canonical_cpn_reference.json \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py
git commit -m "test: validate FeI2 canonical spectrum references"
```

### Task 5: Run The Full Validation Sweep And Stabilize The Slice

**Files:**
- Modify: none unless a verification failure exposes a missing compatibility fix

- [ ] **Step 1: Run the focused FeI2 validation tests**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py \
  translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py
```

Expected: PASS

- [ ] **Step 2: Run the adjacent canonical CPN regression slice**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_cpn_pair_model_fei2_bridge.py \
  translation-invariant-spin-model-simplifier/tests/test_build_sun_gswt_classical_payload.py \
  translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_build_python_glswt_payload.py
```

Expected: PASS

- [ ] **Step 3: If the environment supports Sunny backend execution, run the live driver regression once**

Run:

```bash
python -m pytest -q \
  translation-invariant-spin-model-simplifier/tests/test_fei2_canonical_cpn_validation.py \
  -k spectrum_matches_representative_sunny_fei2_nodes -v
```

Expected: PASS with a live `run_sun_gswt(...)` execution path. If the local Julia/Sunny environment is unavailable, record the exact skip or failure mode before changing code.

- [ ] **Step 4: Commit any final verification-only adjustments**

```bash
git add -A
git commit -m "test: finalize FeI2 canonical CPN validation"
```
