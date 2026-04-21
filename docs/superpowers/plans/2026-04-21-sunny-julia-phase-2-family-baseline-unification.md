# Sunny Julia Phase 2 Family Baseline Unification Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the remaining Sunny-family classical, thermodynamics, and SUN-GSWT launchers onto the canonical `.julia-env-v09` / `scripts/.julia-depot` / `DESIGN_MOTT_JULIA_CMD` baseline already established by Phase 1.

**Architecture:** Keep scope narrow and reuse the existing runtime surfaces. The three remaining Python adapters should mirror the Phase 1 LSWT Julia-command resolution order, and the three remaining Julia launchers should activate the same repo-local environment as `run_sunny_lswt.jl`. Focused contract tests should lock both behaviors so future drift is caught before downstream runs.

**Tech Stack:** Python 3, Julia 1.12.x, Sunny.jl 0.9.x, JSON3.jl, `pytest` / `unittest`, repo-local `.julia-env-v09`, repo-local `scripts/.julia-depot`

---

### Task 1: Lock Sunny-Family Python Julia Resolution In Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py`
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py`
- Reference: `translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py`

- [ ] **Step 1: Write the failing classical-driver override tests**

```python
def test_driver_prefers_environment_julia_override(self):
    with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
        result = run_sunny_sun_classical(payload)
    self.assertEqual(result["status"], "ok")


def test_driver_falls_back_to_plain_julia_without_override(self):
    with patch.dict("os.environ", {}, clear=True):
        result = run_sunny_sun_classical(payload)
    self.assertEqual(result["status"], "ok")
```

- [ ] **Step 2: Run the classical-driver tests to verify they fail for the right reason**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py -q`

Expected: FAIL because the current driver hardcodes `"julia"` and ignores `DESIGN_MOTT_JULIA_CMD`.

- [ ] **Step 3: Write the failing thermodynamics-driver override tests**

```python
def test_driver_prefers_environment_julia_override(self):
    with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
        result = run_sunny_sun_thermodynamics(payload)
    self.assertEqual(result["status"], "ok")
```

- [ ] **Step 4: Run the thermodynamics-driver tests to verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py -q`

Expected: FAIL because the current driver hardcodes `"julia"` and ignores `DESIGN_MOTT_JULIA_CMD`.

- [ ] **Step 5: Extend the existing GSWT driver tests with the same override contract**

```python
def test_driver_prefers_environment_julia_override(self):
    with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
        result = run_sun_gswt(payload)
    self.assertEqual(result["status"], "ok")
```

- [ ] **Step 6: Run the focused GSWT override tests to verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py -k "environment_julia_override or plain_julia_without_override" -q`

Expected: FAIL because the current driver still uses `"julia"` directly.

- [ ] **Step 7: Commit the red test slice once all three failures are demonstrated**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "test: lock sunny family julia command resolution"
```

### Task 2: Rewire The Remaining Python Drivers To Match Phase 1

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py`

- [ ] **Step 1: Implement the minimal Julia-command resolver in the classical driver**

```python
def _resolve_julia_cmd(julia_cmd=None):
    if julia_cmd not in {None, ""}:
        return str(julia_cmd)
    override = os.environ.get("DESIGN_MOTT_JULIA_CMD")
    if override:
        return override
    return "julia"
```

- [ ] **Step 2: Use the resolver in `run_sunny_sun_classical(...)`**

```python
resolved_julia_cmd = _resolve_julia_cmd(julia_cmd)
command = [resolved_julia_cmd, str(SUNNY_CLASSICAL_SCRIPT), str(payload_path)]
```

- [ ] **Step 3: Make the classical CLI entrypoint preserve env-based fallback**

```python
parser.add_argument("--julia-cmd")
print(json.dumps(run_sunny_sun_classical(payload, julia_cmd=args.julia_cmd), indent=2, sort_keys=True))
```

- [ ] **Step 4: Apply the same minimal resolver/update to the thermodynamics driver**

```python
def run_sunny_sun_thermodynamics(payload, julia_cmd=None, stream_progress=False):
    resolved_julia_cmd = _resolve_julia_cmd(julia_cmd)
```

- [ ] **Step 5: Apply the same minimal resolver/update to the GSWT driver**

```python
def run_sun_gswt(payload, julia_cmd=None):
    resolved_julia_cmd = _resolve_julia_cmd(julia_cmd)
```

- [ ] **Step 6: Run the focused driver regression slice**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py -q`

Expected: PASS

- [ ] **Step 7: Commit the Python driver unification**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py \
  translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py \
  translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: unify sunny family julia command resolution"
```

### Task 3: Lock The Remaining Julia Launcher Paths In Tests

**Files:**
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py`

- [ ] **Step 1: Write the failing launcher-path contract tests**

```python
def test_remaining_sunny_launchers_use_phase1_project_baseline(self):
    for script_path in SCRIPT_PATHS:
        content = script_path.read_text(encoding="utf-8")
        self.assertIn(".julia-env-v09", content)
        self.assertNotIn(".julia-env-v06", content)
```

- [ ] **Step 2: Run the launcher-path contract tests to verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py -q`

Expected: FAIL because the three remaining launchers still reference `.julia-env-v06`.

- [ ] **Step 3: Extend the GSWT source test so it also locks the new project path**

```python
def test_script_uses_phase1_environment_baseline(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn(".julia-env-v09", source)
    self.assertNotIn(".julia-env-v06", source)
```

- [ ] **Step 4: Run the focused source-level slice and verify the red state**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py -q`

Expected: FAIL because the launcher paths are still stale.

- [ ] **Step 5: Commit the red launcher-path tests**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "test: lock sunny family launcher environment paths"
```

### Task 4: Rewire The Remaining Julia Launchers To `.julia-env-v09`

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl`
- Modify: `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl`
- Modify: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_sun_gswt.jl`

- [ ] **Step 1: Update the classical launcher project path**

```julia
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", "..", ".julia-env-v09"))
```

- [ ] **Step 2: Update the thermodynamics launcher project path**

```julia
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", "..", ".julia-env-v09"))
```

- [ ] **Step 3: Update the GSWT launcher project path**

```julia
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", "..", ".julia-env-v09"))
```

- [ ] **Step 4: Re-run the source-level launcher tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py -q`

Expected: PASS

- [ ] **Step 5: Commit the launcher-path migration**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl \
  translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl \
  translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_sun_gswt.jl
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: migrate remaining sunny launchers to v09 env"
```

### Task 5: Refresh Docs, Re-run Focused Verification, And Record The Result

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/reference/environment.md`
- Modify: `session-memory/sessions/design-mott-materials-2026-04-21-0342.md`
- Modify: `session-memory/index/design-mott-materials.md`

- [ ] **Step 1: Update the environment reference to describe the shared Sunny-family baseline explicitly**

```markdown
- All checked-in Sunny-family launchers now share the same repo-local
  `.julia-env-v09` project and `scripts/.julia-depot` depot.
- `DESIGN_MOTT_JULIA_CMD` applies to the spin-only LSWT driver and the
  Sunny-family pseudospin-orbital drivers.
```

- [ ] **Step 2: Run the focused Sunny-family regression slice**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sun_gswt_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_gswt_script.py translation-invariant-spin-model-simplifier/tests/test_sunny_family_environment_contract.py translation-invariant-spin-model-simplifier/tests/test_run_linear_spin_wave_driver.py translation-invariant-spin-model-simplifier/tests/test_sunny_lswt_environment_contract.py translation-invariant-spin-model-simplifier/tests/test_downstream_stage_execution.py translation-invariant-spin-model-simplifier/tests/test_skill_reference_docs.py -q`

Expected: PASS

- [ ] **Step 3: Append the Phase 2 result to session memory and refresh the project index**

```text
Record that the remaining Sunny-family launchers and drivers now share the
Phase 1 `.julia-env-v09` / `DESIGN_MOTT_JULIA_CMD` baseline.
```

- [ ] **Step 4: Commit docs + session-memory state**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/reference/environment.md
git -C /data/work/zhli/soft/Design_Mott_Materials add -f \
  session-memory/sessions/design-mott-materials-2026-04-21-0342.md \
  session-memory/index/design-mott-materials.md
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "docs: record sunny phase2 family baseline"
```
