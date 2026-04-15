# Sunny Pseudospin-Orbital Backends Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Sunny.jl`-backed classical minimization and selectable Sunny thermodynamics backends to the `many_body_hr -> pseudospin_orbital` pipeline, with explicit CLI options, hard-failure error handling, normalized artifacts, and tests.

**Architecture:** Reuse the existing `build_sun_gswt_classical_payload(parsed_payload)` model builder and the current Python-side diagnostic functions, then add two thin Python-to-Julia adapters modeled after the existing LSWT Sunny adapter: one for classical minimization and one for thermodynamics. Wire those adapters into `solve_pseudospin_orbital_pipeline.py` behind new `classical_method` and `thermodynamics_backend` options, and keep the repository-facing JSON artifacts stable by normalizing backend-specific results before they are written.

**Tech Stack:** Python 3, Julia, Sunny.jl, JSON3.jl, `unittest`, `pytest`

**Interpretation Note:** In this plan, `CP^(N-1)` refers to the retained local/classical variational manifold and payload semantics used by the pseudospin-orbital pipeline. It is not shorthand for the projected Hamiltonian being SU(`N`)-symmetric, and it should not be read as saying that optimization on `CP^(N-1)` is the same thing as imposing SU(`N`) symmetry constraints on the Hamiltonian.

**Manual / Literature Note:** Sunny's `:SUN` language should be read here as a coherent-state parametrization of an `N`-component local ray, with `N` set by the local Hilbert-space dimension. In other words, the local-state geometry matches `CP^(N-1)`, but this does not imply that the effective Hamiltonian is SU(`N`)-symmetric. What matters for this plan is compatibility with Sunny's coherent-state and two-site operator interface, including full pair-coupling matrices when supported by the backend.

---

### Task 1: Add the Sunny Classical Backend Adapter

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py`
- Create: `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl`
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py`
- Create: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py`
- Reference: `translation-invariant-spin-model-simplifier/scripts/lswt/sun_gswt_driver.py:13-153`
- Reference: `translation-invariant-spin-model-simplifier/scripts/lswt/run_sunny_sun_gswt.jl:3-194`
- Reference: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py:18-123`

- [ ] **Step 1: Write the failing Python driver contract tests**

```python
def test_driver_invokes_julia_classical_backend_and_parses_json(self):
    payload = {"payload_kind": "sunny_sun_classical", "supercell_shape": [2, 1, 1]}
    result = run_sunny_sun_classical(payload, julia_cmd="julia")
    self.assertEqual(result["status"], "ok")
    self.assertEqual(result["backend"]["solver"], "minimize_energy!")


def test_driver_reports_missing_julia_command(self):
    result = run_sunny_sun_classical({"payload_kind": "sunny_sun_classical"})
    self.assertEqual(result["status"], "error")
    self.assertEqual(result["error"]["code"], "missing-julia-command")
```

- [ ] **Step 2: Run the driver tests to verify they fail for the expected reason**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py -q`

Expected: FAIL because `classical.sunny_sun_classical_driver` does not exist yet.

- [ ] **Step 3: Write the failing Julia source-level guard tests**

```python
def test_classical_script_uses_minimize_energy(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn("minimize_energy!", source)


def test_classical_script_keeps_full_pair_operator(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn("extract_parts=false", source)
```

- [ ] **Step 4: Run the Julia source-level tests to verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py -q`

Expected: FAIL because `run_sunny_sun_classical.jl` does not exist yet.

- [ ] **Step 5: Implement the minimal Python adapter**

```python
SCRIPT_DIR = Path(__file__).resolve().parent
SUNNY_CLASSICAL_SCRIPT = SCRIPT_DIR / "run_sunny_sun_classical.jl"


def run_sunny_sun_classical(payload, julia_cmd="julia"):
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        payload_path = Path(handle.name)
    try:
        completed = subprocess.run(
            [julia_cmd, str(SUNNY_CLASSICAL_SCRIPT), str(payload_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return _error("missing-julia-command", str(exc), payload_kind=payload.get("payload_kind"))
    except subprocess.CalledProcessError as exc:
        return _error("backend-process-failed", (exc.stderr or "").strip() or str(exc), payload_kind=payload.get("payload_kind"))
    finally:
        payload_path.unlink(missing_ok=True)
    return json.loads(completed.stdout)
```

- [ ] **Step 6: Implement the minimal Julia classical backend**

```julia
sys = build_system(payload)
best_energy = Inf
best_state = nothing
for start in 1:starts
    randomize_spins!(sys)
    minimize_energy!(sys)
    E = energy(sys) / prod(size(sys.coherents)[1:3])
    if E < best_energy
        best_energy = E
        best_state = serialize_state(sys)
    end
end
emit_payload(Dict(
    "status" => "ok",
    "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN", "solver" => "minimize_energy!"),
    "method" => "sunny-cpn-minimize",
    "energy" => best_energy,
    "supercell_shape" => collect(supercell_shape),
    "local_rays" => best_state["local_rays"],
    "starts" => starts,
    "seed" => seed,
))
```

- [ ] **Step 7: Run the focused classical backend tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py -q`

Expected: PASS

- [ ] **Step 8: Commit the classical backend adapter slice**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py \
  translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl \
  translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add Sunny classical backend adapter"
```

### Task 2: Wire the Sunny Classical Method Into the Pseudospin-Orbital CLI

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py:26-279`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py:13-222`
- Reference: `translation-invariant-spin-model-simplifier/scripts/classical/build_sun_gswt_classical_payload.py:48-98`
- Reference: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_classical_solver.py:456-523`

- [ ] **Step 1: Add a failing CLI integration test for `sunny-cpn-minimize`**

```python
@patch("cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical")
def test_solve_from_files_supports_sunny_cpn_minimize_method(self, mocked_driver):
    mocked_driver.return_value = {
        "status": "ok",
        "method": "sunny-cpn-minimize",
        "energy": -0.5,
        "supercell_shape": [2, 1, 1],
        "local_rays": [
            {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0}]},
            {"cell": [1, 0, 0], "vector": [{"real": 0.0, "imag": 0.0}, {"real": 1.0, "imag": 0.0}]},
        ],
        "starts": 2,
        "seed": 3,
        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
    }
    manifest = solve_from_files(
        poscar_path=poscar_path,
        hr_path=hr_path,
        output_dir=tmpdir,
        docs_dir=docsdir,
        compile_pdf=False,
        classical_method="sunny-cpn-minimize",
        supercell_shape=(2, 1, 1),
        starts=2,
        seed=3,
    )
    self.assertEqual(manifest["solver"]["method"], "sunny-cpn-minimize")
```

- [ ] **Step 2: Run the single CLI test and verify it fails on unsupported method/signature**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py -k sunny_cpn_minimize -q`

Expected: FAIL because the CLI does not yet accept `sunny-cpn-minimize` or `supercell_shape`.

- [ ] **Step 3: Extend the CLI signature and argument parser**

```python
def solve_from_files(
    poscar_path,
    hr_path,
    output_dir,
    docs_dir,
    *,
    compile_pdf=True,
    coefficient_tolerance=1e-10,
    classical_method="restricted-product-state",
    supercell_shape=(1, 1, 1),
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    max_sweeps=200,
):
    elif classical_method == "sunny-cpn-minimize":
        classical_model = build_sun_gswt_classical_payload(parsed_payload)
        backend_result = run_sunny_sun_classical({
            "payload_kind": "sunny_sun_classical",
            "model": classical_model,
            "supercell_shape": list(supercell_shape),
            "starts": int(starts),
            "seed": int(seed),
        })
```

- [ ] **Step 4: Reuse existing diagnostics to normalize the Sunny result**

```python
state = {"shape": solver_result["supercell_shape"], "local_rays": solver_result["local_rays"]}
diagnostics = diagnose_sun_gswt_classical_state(classical_model, state)
solver_result = {
    **solver_result,
    "projector_diagnostics": diagnostics["projector_diagnostics"],
    "stationarity": diagnostics["stationarity"],
}
```

- [ ] **Step 5: Add `--supercell-shape NX NY NZ` to the CLI parser**

```python
parser.add_argument("--supercell-shape", type=int, nargs=3, metavar=("NX", "NY", "NZ"), default=(1, 1, 1))
```

- [ ] **Step 6: Update phase-note output for the new classical backend**

```python
f"- classical_backend: {solver_result.get('backend', {}).get('name')}",
f"- classical_backend_solver: {solver_result.get('backend', {}).get('solver')}",
```

- [ ] **Step 7: Run the focused CLI classical tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py -k "sunny_cpn_minimize or sun_gswt" -q`

Expected: PASS

- [ ] **Step 8: Commit the CLI classical integration slice**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: expose Sunny classical method in pseudospin CLI"
```

### Task 3: Add the Sunny Thermodynamics Adapter and Backend Scripts

**Files:**
- Create: `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py`
- Create: `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl`
- Create: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py`
- Create: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py`
- Reference: `translation-invariant-spin-model-simplifier/scripts/classical/sun_gswt_monte_carlo.py:23-93`
- Reference: `translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py:461-638`
- Reference: `translation-invariant-spin-model-simplifier/scripts/.julia-depot/packages/Sunny/Jqv25/src/MonteCarlo/Samplers.jl:1-154`
- Reference: `translation-invariant-spin-model-simplifier/scripts/.julia-depot/packages/Sunny/Jqv25/src/MonteCarlo/ParallelTempering.jl:1-92`
- Reference: `translation-invariant-spin-model-simplifier/scripts/.julia-depot/packages/Sunny/Jqv25/src/MonteCarlo/WangLandau.jl:1-88`

- [ ] **Step 1: Write the failing thermodynamics driver tests for all three backend families**

```python
def test_driver_supports_local_sampler_backend(self):
    result = run_sunny_sun_thermodynamics({"backend_method": "sunny-local-sampler"}, julia_cmd="julia")
    self.assertEqual(result["backend"]["sampler"], "sunny-local-sampler")


def test_driver_supports_parallel_tempering_backend(self):
    result = run_sunny_sun_thermodynamics({"backend_method": "sunny-parallel-tempering"}, julia_cmd="julia")
    self.assertEqual(result["backend"]["sampler"], "sunny-parallel-tempering")


def test_driver_supports_wang_landau_backend(self):
    result = run_sunny_sun_thermodynamics({"backend_method": "sunny-wang-landau"}, julia_cmd="julia")
    self.assertEqual(result["backend"]["sampler"], "sunny-wang-landau")


def test_driver_reports_missing_julia_command(self):
    result = run_sunny_sun_thermodynamics({"backend_method": "sunny-local-sampler"})
    self.assertEqual(result["error"]["code"], "missing-julia-command")
```

- [ ] **Step 2: Run the thermodynamics driver tests and verify they fail because the module is missing**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py -q`

Expected: FAIL because `classical.sunny_sun_thermodynamics_driver` does not exist yet.

- [ ] **Step 3: Write the failing Julia source-level tests for the sampling backends**

```python
self.assertIn("LocalSampler", source)
self.assertIn("ParallelTempering", source)
self.assertTrue("WangLandau" in source or "ParallelWangLandau" in source)
```

- [ ] **Step 4: Run the Julia thermodynamics source-level tests and verify they fail**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py -q`

Expected: FAIL because `run_sunny_sun_thermodynamics.jl` does not exist yet.

- [ ] **Step 5: Implement the minimal thermodynamics driver**

```python
def run_sunny_sun_thermodynamics(payload, julia_cmd="julia"):
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        payload_path = Path(handle.name)
    try:
        completed = subprocess.run(
            [julia_cmd, str(SUNNY_THERMODYNAMICS_SCRIPT), str(payload_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return _error("missing-julia-command", str(exc), payload_kind=payload.get("payload_kind"))
    except subprocess.CalledProcessError as exc:
        return _error("backend-process-failed", (exc.stderr or "").strip() or str(exc), payload_kind=payload.get("payload_kind"))
    finally:
        payload_path.unlink(missing_ok=True)
    result = json.loads(completed.stdout)
    if result.get("status") != "ok":
        return result
    return normalize_sunny_thermodynamics_result(result)
```

- [ ] **Step 6: Implement the Julia thermodynamics script with backend dispatch**

```julia
if backend == "sunny-local-sampler"
    sampler = LocalSampler(; kT=kT, nsweeps=1.0, propose=proposal_fn)
elseif backend == "sunny-parallel-tempering"
    ensemble = ParallelTempering(sys, LocalSampler(; kT=kT_sched[1], propose=proposal_fn), kT_sched)
elseif backend == "sunny-wang-landau"
    wl = WangLandau(; sys=clone_system(sys), bin_size=bin_size, bounds=bounds, propose=proposal_fn, ln_f=ln_f)
end
```

- [ ] **Step 7: Normalize thermodynamics output into repository shape**

```python
{
    "method": result["backend_method"],
    "backend": result["backend"],
    "grid": normalized_grid,
    "observables": {
        "energy": [item["energy"] for item in normalized_grid],
        "magnetization": [item["magnetization"] for item in normalized_grid],
        "specific_heat": [item["specific_heat"] for item in normalized_grid],
        "susceptibility": [item["susceptibility"] for item in normalized_grid],
    },
    "uncertainties": {
        "energy": [item.get("energy_stderr", 0.0) for item in normalized_grid],
        "magnetization": [item.get("magnetization_stderr", 0.0) for item in normalized_grid],
        "specific_heat": [item.get("specific_heat_stderr", 0.0) for item in normalized_grid],
        "susceptibility": [item.get("susceptibility_stderr", 0.0) for item in normalized_grid],
    },
    "sampling": {
        "backend_method": result["backend_method"],
        "seed": result["sampling"]["seed"],
    },
    "reference": {"normalization": "per_spin"},
}
```

- [ ] **Step 8: Run the focused thermodynamics backend tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py -q`

Expected: PASS

- [ ] **Step 9: Commit the thermodynamics adapter slice**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py \
  translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl \
  translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py \
  translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add Sunny thermodynamics backend adapter"
```

### Task 4: Integrate Thermodynamics Into the Pseudospin-Orbital CLI

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py:26-279`
- Modify: `translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py:13-222`
- Test: `translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py`

- [ ] **Step 1: Add failing CLI tests for thermodynamics backends**

```python
def test_solve_from_files_supports_sunny_local_sampler_thermodynamics(self):
    manifest = solve_from_files(
        poscar_path=poscar_path,
        hr_path=hr_path,
        output_dir=tmpdir,
        docs_dir=docsdir,
        compile_pdf=False,
        classical_method="sunny-cpn-minimize",
        supercell_shape=(1, 1, 1),
        run_thermodynamics=True,
        thermodynamics_backend="sunny-local-sampler",
        temperatures=[0.2, 0.4],
    )
    self.assertIn("thermodynamics_result", manifest["artifacts"])


def test_solve_from_files_supports_sunny_parallel_tempering_thermodynamics(self):
    manifest = solve_from_files(
        poscar_path=poscar_path,
        hr_path=hr_path,
        output_dir=tmpdir,
        docs_dir=docsdir,
        compile_pdf=False,
        classical_method="sunny-cpn-minimize",
        supercell_shape=(1, 1, 1),
        run_thermodynamics=True,
        thermodynamics_backend="sunny-parallel-tempering",
        temperatures=[0.2, 0.4],
        thermo_pt_temperatures=[0.2, 0.4, 0.8],
    )
    self.assertIn("thermodynamics_result", manifest["artifacts"])


def test_solve_from_files_supports_sunny_wang_landau_thermodynamics(self):
    manifest = solve_from_files(
        poscar_path=poscar_path,
        hr_path=hr_path,
        output_dir=tmpdir,
        docs_dir=docsdir,
        compile_pdf=False,
        classical_method="sunny-cpn-minimize",
        supercell_shape=(1, 1, 1),
        run_thermodynamics=True,
        thermodynamics_backend="sunny-wang-landau",
        temperatures=[0.2, 0.4],
        thermo_wl_bounds=[-2.0, 0.0],
        thermo_wl_bin_size=0.05,
    )
    self.assertIn("dos_result", manifest["artifacts"])


def test_rejects_restricted_product_state_for_sunny_thermodynamics(self):
    with self.assertRaisesRegex(ValueError, "CP\\^\\(N-1\\) classical state"):
        solve_from_files(
            poscar_path=poscar_path,
            hr_path=hr_path,
            output_dir=tmpdir,
            docs_dir=docsdir,
            compile_pdf=False,
            classical_method="restricted-product-state",
            run_thermodynamics=True,
            thermodynamics_backend="sunny-local-sampler",
            temperatures=[0.2, 0.4],
        )
```

- [ ] **Step 2: Run the thermodynamics CLI tests to verify they fail on missing options/behavior**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py -k "thermodynamics or wang_landau or parallel_tempering" -q`

Expected: FAIL because the CLI has no thermodynamics stage yet.

- [ ] **Step 3: Extend `solve_from_files` with thermodynamics arguments**

```python
def solve_from_files(
    poscar_path,
    hr_path,
    output_dir,
    docs_dir,
    *,
    compile_pdf=True,
    coefficient_tolerance=1e-10,
    classical_method="restricted-product-state",
    supercell_shape=(1, 1, 1),
    starts=16,
    seed=0,
    max_linear_size=5,
    convergence_repeats=2,
    max_sweeps=200,
    run_thermodynamics=False,
    thermodynamics_backend=None,
    temperatures=None,
    thermo_seed=0,
    thermo_sweeps=100,
    thermo_burn_in=50,
    thermo_measurement_interval=1,
    thermo_proposal="delta",
    thermo_proposal_scale=0.2,
    thermo_pt_temperatures=None,
    thermo_pt_exchange_interval=1,
    thermo_wl_bounds=None,
    thermo_wl_bin_size=None,
    thermo_wl_windows=None,
    thermo_wl_overlap=None,
    thermo_wl_ln_f=1.0,
    thermo_wl_sweeps=100,
):
```

- [ ] **Step 4: Add validation helpers before backend execution**

```python
if run_thermodynamics and classical_method == "restricted-product-state":
    raise ValueError("Sunny thermodynamics requires a CP^(N-1) classical state")
if thermodynamics_backend == "sunny-parallel-tempering" and not thermo_pt_temperatures:
    raise ValueError("sunny-parallel-tempering requires --thermo-pt-temperatures")
if thermodynamics_backend == "sunny-parallel-tempering" and temperatures and list(temperatures) != list(thermo_pt_temperatures):
    raise ValueError("for sunny-parallel-tempering, --temperatures must match --thermo-pt-temperatures")
```

- [ ] **Step 5: Persist thermodynamics artifacts**

```python
thermodynamics_result_path = output_dir / "thermodynamics_result.json"
dos_result_path = output_dir / "dos_result.json"
thermodynamics_result_path.write_text(json.dumps(thermodynamics_result, indent=2, sort_keys=True), encoding="utf-8")
if dos_result is not None:
    dos_result_path.write_text(json.dumps(dos_result, indent=2, sort_keys=True), encoding="utf-8")
artifacts["thermodynamics_result"] = str(thermodynamics_result_path)
artifacts["dos_result"] = str(dos_result_path) if dos_result is not None else None
```

- [ ] **Step 6: Extend the phase-note summary**

```python
f"- thermodynamics_backend: {thermodynamics_backend}",
f"- thermodynamics_present: {bool(thermodynamics_result)}",
f"- thermodynamics_method: {thermodynamics_result.get('method') if thermodynamics_result else None}",
f"- dos_present: {bool(dos_result)}",
```

- [ ] **Step 7: Add CLI parser arguments**

```python
parser.add_argument("--run-thermodynamics", action="store_true")
parser.add_argument("--thermodynamics-backend", choices=["sunny-local-sampler", "sunny-parallel-tempering", "sunny-wang-landau"])
parser.add_argument("--temperatures", type=float, nargs="+")
parser.add_argument("--thermo-pt-temperatures", type=float, nargs="+")
parser.add_argument("--thermo-pt-exchange-interval", type=int, default=1)
parser.add_argument("--thermo-wl-bounds", type=float, nargs=2)
parser.add_argument("--thermo-wl-bin-size", type=float)
parser.add_argument("--thermo-wl-windows", type=int)
parser.add_argument("--thermo-wl-overlap", type=float)
parser.add_argument("--thermo-wl-ln-f", type=float, default=1.0)
parser.add_argument("--thermo-wl-sweeps", type=int, default=100)
```

- [ ] **Step 8: Run the focused thermodynamics CLI tests**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py -q`

Expected: PASS

- [ ] **Step 9: Commit the thermodynamics CLI integration slice**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add \
  translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "feat: add Sunny thermodynamics options to pseudospin CLI"
```

### Task 5: Update User-Facing Docs and Run End-to-End Verification

**Files:**
- Modify: `translation-invariant-spin-model-simplifier/SKILL.md`
- Modify: `README.md`
- Optional Modify: `translation-invariant-spin-model-simplifier/reference/results_bundle_entrypoint.md`
- Verify: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py`
- Verify: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py`
- Verify: `translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py`
- Verify: `translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py`
- Verify: `translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py`

- [ ] **Step 1: Add a failing documentation assertion if needed**

```python
self.assertIn("sunny-cpn-minimize", skill_text)
self.assertIn("sunny-local-sampler", readme_text)
```

- [ ] **Step 2: Run the documentation-focused checks if you added them**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests -k "readme or skill" -q`

Expected: FAIL only if explicit doc assertion tests were added first.

- [ ] **Step 3: Update `SKILL.md` to mention the new backend choices**

```markdown
- present `sunny-cpn-minimize` as a Sunny-backed classical option for `many_body_hr` pseudospin-orbital models
- allow Sunny thermodynamics through `sunny-local-sampler`, `sunny-parallel-tempering`, and `sunny-wang-landau`
- fail explicitly when Sunny-backed options are requested but `julia` or `Sunny.jl` is unavailable
```

- [ ] **Step 4: Update the root `README.md` with the new pseudospin-orbital backend matrix**

```markdown
- `sunny-cpn-minimize` for classical minimization on the retained `CP^(N-1)` variational manifold over a chosen magnetic supercell
- `sunny-local-sampler`, `sunny-parallel-tempering`, and `sunny-wang-landau` for finite-temperature pseudospin-orbital studies on the same manifold/payload semantics
```

- [ ] **Step 5: Run the full targeted verification suite**

Run: `python -m pytest translation-invariant-spin-model-simplifier/tests/test_sunny_sun_classical_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_classical_script.py translation-invariant-spin-model-simplifier/tests/test_sunny_sun_thermodynamics_driver.py translation-invariant-spin-model-simplifier/tests/test_run_sunny_sun_thermodynamics_script.py translation-invariant-spin-model-simplifier/tests/test_solve_pseudospin_orbital_pipeline_cli.py -q`

Expected: PASS

- [ ] **Step 6: Run one CLI smoke test without PDF generation**

Run:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py \
  --poscar /data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR \
  --hr /data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat \
  --output-dir /tmp/pseudospin-sunny-smoke \
  --docs-dir /tmp/pseudospin-sunny-smoke-docs \
  --no-pdf \
  --classical-method sunny-cpn-minimize \
  --supercell-shape 1 1 1
```

Expected: JSON manifest with `"status": "ok"` if `julia` and `Sunny.jl` are available; otherwise an explicit structured error that confirms the new failure path is working.

- [ ] **Step 7: Commit the docs and verification slice**

```bash
git -C /data/work/zhli/soft/Design_Mott_Materials add README.md translation-invariant-spin-model-simplifier/SKILL.md
git -C /data/work/zhli/soft/Design_Mott_Materials commit -m "docs: document Sunny pseudospin-orbital backends"
```
