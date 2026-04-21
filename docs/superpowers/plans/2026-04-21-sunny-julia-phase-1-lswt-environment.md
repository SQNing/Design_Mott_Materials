# Sunny Julia Phase 1 LSWT Environment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge the spin-only Sunny LSWT path onto one canonical Julia/Sunny environment, wire the LSWT launchers and reference docs to that environment, and prove the fix with the real FeI2 `V2b` downstream smoke.

**Architecture:** Phase 1 keeps scope narrow: only the spin-only LSWT path moves to the new canonical `.julia-env-v09` project while the local depot remains under `scripts/.julia-depot`. The Julia launcher becomes the single source of truth for repo-local project/depot paths, and the Python LSWT driver gains an explicit Julia-command resolution path so the repo can run against a newer Julia 1.12.x binary without hardcoding a machine-specific absolute path.

**Tech Stack:** Python 3, Julia 1.12.x, Sunny.jl 0.9.x, JSON3.jl, `pytest` / `unittest`, repo-local Julia project + depot, FeI2 downstream smoke artifacts

---

## Scope Lock

This plan executes Phase 1 only.

In scope:

- spin-only `run_sunny_lswt.jl`
- spin-only `linear_spin_wave_driver.py`
- one canonical repo-local Julia environment for LSWT
- LSWT-specific environment docs and regression tests
- local Julia 1.12.x provisioning for verification
- rerunning the real FeI2 `V2b` smoke

Out of scope:

- `run_sunny_sun_classical.jl`
- `run_sunny_sun_thermodynamics.jl`
- `run_sunny_sun_gswt.jl`
- pseudospin/SUN payload migrations
- broad Phase 2 Sunny-family cleanup

## File Map

**Create**

- `docs/superpowers/plans/2026-04-21-sunny-julia-phase-1-lswt-environment.md`
- `translation-invariant-spin-model-simplifier/.julia-env-v09/Project.toml`
- `translation-invariant-spin-model-simplifier/.julia-env-v09/Manifest.toml`
- `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`
- `translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py`

**Modify**

- `docs/superpowers/specs/2026-04-21-sunny-julia-phase-1-lswt-environment-design.md`
- `session-memory/sessions/design-mott-materials-2026-04-21-0342.md`
- `session-memory/index/design-mott-materials.md`
- `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`
- `translation-invariant-spin-model-simplifier/reference/environment.md`
- `translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py`

**Read For Context**

- `docs/test-reports/test-feature-20260421-171209.md`
- `docs/superpowers/specs/2026-04-21-sunny-julia-phase-1-lswt-environment-design.md`
- `translation-invariant-spin-model-simplifier/.julia-env-v06/Project.toml`
- `translation-invariant-spin-model-simplifier/.julia-env-v06/Manifest.toml`
- `translation-invariant-spin-model-simplifier/scripts/common/downstream_stage_execution.py`
- `translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py`
- `translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py`

### Task 1: Lock The Environment Drift With Red Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`
- Read: `translation-invariant-spin-model-simplifier/reference/environment.md`

- [ ] **Step 1: Write a failing launcher-path contract test**

Add a test that reads `run_sunny_lswt.jl` and asserts:

```python
self.assertIn('.julia-env-v09', content)
self.assertNotIn('scripts/.julia-env-v06', content)
self.assertIn('scripts/.julia-depot', content)
```

- [ ] **Step 2: Write a failing environment-doc contract test**

Add assertions that `reference/environment.md` documents:

```python
self.assertIn('Julia 1.12.x', content)
self.assertIn('`Sunny.jl 0.9.x`', content)
self.assertIn('.julia-env-v09', content)
self.assertIn('scripts/.julia-depot', content)
```

- [ ] **Step 3: Extend the existing skill-reference regression**

Update `test_skill_reference_docs.py` so it fails until the environment reference tracks:

```python
self.assertIn('`Sunny.jl 0.9.x`', content)
self.assertNotIn('`Sunny.jl 0.9.x`', content)
```

- [ ] **Step 4: Run the doc/launcher regression slice and verify it fails**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py \
  translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py -v
```

Expected: FAIL because the launcher and docs still point at the old environment story.

- [ ] **Step 5: Commit the red-test baseline**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py
git add translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py
git commit -m "test: define sunny lswt environment contract"
```

### Task 2: Lock Julia Command Resolution With A Driver Red Test

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`
- Read: `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`

- [ ] **Step 1: Write a failing test for explicit Julia-command override**

Add a test that sets:

```python
os.environ["DESIGN_MOTT_JULIA_CMD"] = "/tmp/julia-1.12/bin/julia"
```

patches `subprocess.run`, and asserts the driver invokes:

```python
self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
self.assertTrue(command[1].endswith("run_sunny_lswt.jl"))
```

- [ ] **Step 2: Write a failing test for fallback behavior**

Add a second test proving that without the env override the driver still falls back to:

```python
self.assertEqual(command[0], "julia")
```

- [ ] **Step 3: Run the new driver regression slice and verify it fails**

Run:

```bash
python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py -v
```

Expected: FAIL because the current driver ignores the repo-level Julia override.

- [ ] **Step 4: Commit the driver red-test baseline**

```bash
git add translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py
git commit -m "test: define lswt julia command resolution"
```

### Task 3: Introduce The Canonical `.julia-env-v09` And Rewire LSWT Launchers

**Files:**
- Create: `translation-invariant-spin-model-simplifier/.julia-env-v09/Project.toml`
- Create: `translation-invariant-spin-model-simplifier/.julia-env-v09/Manifest.toml`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`

- [ ] **Step 1: Add the new Julia project metadata**

Create `Project.toml` with at least:

```toml
[deps]
JSON3 = "0f8b85d8-7281-11e9-16c2-39a750bddbf1"
Sunny = "2b4a2ac8-8f8b-43e8-abf4-3cb0c45e8736"
```

The manifest should be generated from a real instantiate step against the current Sunny release line.

- [ ] **Step 2: Repoint the Julia launcher to the canonical project**

Update `run_sunny_lswt.jl` so it resolves:

```julia
const LOCAL_DEPOT = normpath(joinpath(SCRIPT_DIR, "..", ".julia-depot"))
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", "..", ".julia-env-v09"))
```

and keeps the local-project activation before `using JSON3` / `using Sunny`.

- [ ] **Step 3: Add deterministic Julia-command resolution in the Python driver**

Implement a small helper such as:

```python
def _resolve_julia_cmd(julia_cmd=None):
    if julia_cmd not in {None, ""}:
        return str(julia_cmd)
    override = os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if override:
        return override
    return "julia"
```

and use it inside `run_linear_spin_wave(...)`.

- [ ] **Step 4: Run the focused regression slice to green**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py \
  translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py -v
```

Expected: PASS for launcher path alignment, Julia-command resolution, and version-line checks.

- [ ] **Step 5: Commit the canonical LSWT environment slice**

Use forced adds because `.julia-env-v09` is ignored by pattern:

```bash
git add translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_lswt.jl
git add translation-invariant-spin-model-simplifier/scripts/lswt/linear_spin_wave_driver.py
git add -f translation-invariant-spin-model-simplifier/.julia-env-v09/Project.toml
git add -f translation-invariant-spin-model-simplifier/.julia-env-v09/Manifest.toml
git add translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py
git add translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py
git add translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py
git commit -m "feat: align sunny lswt with canonical julia env"
```

### Task 4: Update The Environment Reference

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/reference/environment.md`
- Test: `translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py`
- Test: `translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py`

- [ ] **Step 1: Rewrite the LSWT environment section**

Document the Phase 1 truth explicitly:

- Julia 1.12.x expected for current LSWT verification
- Sunny.jl 0.9.x expected
- local project at `.julia-env-v09`
- local depot at `scripts/.julia-depot`
- `DESIGN_MOTT_JULIA_CMD` as the optional override for non-default Julia binaries

- [ ] **Step 2: Add exact verification and instantiate commands**

Document commands in the form:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
DESIGN_MOTT_JULIA_CMD=/path/to/julia \
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
/path/to/julia --project="$PWD/.julia-env-v09" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

and:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
/path/to/julia --project="$PWD/.julia-env-v09" -e 'using JSON3, Sunny; println("OK")'
```

- [ ] **Step 3: Re-run the doc/launcher regression slice**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py \
  translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py -v
```

Expected: PASS with no lingering `.julia-env-v06` / `Sunny.jl 0.9.x` story in the Phase 1 docs.

- [ ] **Step 4: Commit the environment-reference update**

```bash
git add translation-invariant-spin-model-simplifier/reference/environment.md
git add translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py
git add translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py
git commit -m "docs: refresh sunny lswt environment reference"
```

### Task 5: Provision Julia 1.12.x And Instantiate The LSWT Environment

**Files:**
- Create/refresh outside repo for verification: `/data/work/zhli/soft/julia-1.12.6/`
- Use: `translation-invariant-spin-model-simplifier/.julia-env-v09/Project.toml`
- Use: `translation-invariant-spin-model-simplifier/.julia-env-v09/Manifest.toml`

- [ ] **Step 1: Provision the current Julia 1.12.x binary if absent**

Install the official generic Linux x86_64 build under:

```bash
/data/work/zhli/soft/julia-1.12.6
```

and verify:

```bash
/data/work/zhli/soft/julia-1.12.6/bin/julia --version
```

Expected: `julia version 1.12.6`

- [ ] **Step 2: Instantiate and precompile the new repo-local LSWT environment**

Run:

```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
/data/work/zhli/soft/julia-1.12.6/bin/julia --project="$PWD/.julia-env-v09" \
  -e 'using Pkg; Pkg.instantiate(); Pkg.precompile(); using JSON3, Sunny; println(Pkg.project().path)'
```

Expected: instantiate + precompile succeed and `using JSON3, Sunny` works from `.julia-env-v09`.

- [ ] **Step 3: Sanity-check the LSWT Julia launcher directly**

Run:

```bash
cd /data/work/zhli/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier
DESIGN_MOTT_JULIA_CMD=/data/work/zhli/soft/julia-1.12.6/bin/julia \
python3 scripts/lswt/linear_spin_wave_driver.py scripts/plot_payload.json
```

Expected: a JSON result with either `status="ok"` or a narrower backend/runtime failure that is no longer `missing-sunny-package`.

- [ ] **Step 4: Commit the refreshed manifest if it changed after instantiate**

```bash
git add -f translation-invariant-spin-model-simplifier/.julia-env-v09/Manifest.toml
git commit -m "build: instantiate sunny lswt julia environment"
```

### Task 6: Re-run FeI2 Verification On The New Environment

**Files:**
- Use: `docs/test-reports/test-feature-20260421-171209.md`
- Write fresh report under: `docs/test-reports/`
- Write external artifacts under: `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/results/`

- [ ] **Step 1: Re-run the focused merged regression slice**

Run:

```bash
python -m pytest \
  translation-invariant-spin-model-simplifier/tests/test_document_reader_downstream_orchestration.py \
  translation-invariant-spin-model-simplifier/tests/test_run_document_reader_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_downstream_stage_execution.py \
  translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py \
  translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Re-run the real FeI2 `V2b` downstream smoke with Julia 1.12.6**

Use the same real-input pattern as the earlier successful bridge run, but set:

```bash
DESIGN_MOTT_JULIA_CMD=/data/work/zhli/soft/julia-1.12.6/bin/julia
```

Expected artifact checks:

- `classical/downstream_routes.json`
- `classical/downstream_results.json`
- `classical/downstream_summary.json`

Expected behavioral improvement:

- `lswt` remains `ready`
- LSWT no longer fails with `missing-sunny-package`

- [ ] **Step 3: Write the new feature report**

Record:

- the Julia version used
- the Sunny line resolved in `.julia-env-v09`
- whether LSWT now succeeds
- any remaining narrower runtime issue if success is not yet complete

- [ ] **Step 4: Commit the Phase 1 verification artifacts**

```bash
git add docs/test-reports/<new-report>.md
git commit -m "test: verify sunny lswt phase 1 environment"
```
