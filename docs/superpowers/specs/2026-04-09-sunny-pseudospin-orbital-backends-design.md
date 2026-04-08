# Sunny Pseudospin-Orbital Backend Expansion Design

## Goal

Add `Sunny.jl`-backed classical ground-state and finite-temperature backends to the existing `many_body_hr -> pseudospin_orbital` pipeline, exposing them as explicit parallel options rather than replacing the current Python implementations.

This change is limited to the existing pseudospin-orbital path rooted at `translation-invariant-spin-model-simplifier/scripts/cli/solve_pseudospin_orbital_pipeline.py`.

## Current State

The repository already contains the key pieces needed for a Sunny-backed pseudospin-orbital workflow:

- `scripts/classical/build_sun_gswt_classical_payload.py` converts a parsed `many_body_hr` payload into a `CP^(N-1)` classical model with `pair_matrix` and `bond_tensors`.
- `scripts/classical/sun_gswt_classical_solver.py` provides Python implementations for `sun-gswt-cpn` and `sun-gswt-single-q`.
- `scripts/classical/sun_gswt_monte_carlo.py` provides a Python finite-temperature Monte Carlo sampler on the same manifold.
- `scripts/lswt/build_sun_gswt_payload.py`, `scripts/lswt/sun_gswt_driver.py`, and `scripts/lswt/run_sunny_sun_gswt.jl` already prove the repository can call `Sunny.jl` through a thin Python-to-Julia adapter.

The missing capability is not model construction. It is backend exposure and orchestration:

- there is no `Sunny.jl` classical minimizer available as a `classical_method`
- there is no `Sunny.jl` thermodynamics backend exposed from the pseudospin-orbital CLI
- there is no explicit error path that stops the run when `julia` or `Sunny.jl` is unavailable for these new backend choices

## Approved Scope

The following decisions are fixed for this design:

- Scope is only the `many_body_hr / pseudospin_orbital` chain.
- New Sunny capabilities are exposed as parallel options, not silent replacements.
- Missing `julia` or missing `Sunny.jl` must produce an explicit error and stop the run.
- Thermodynamics support should include multiple Sunny sampling strategies and allow the caller to choose based on the task:
  - `sunny-local-sampler`
  - `sunny-parallel-tempering`
  - `sunny-wang-landau`
- This change does not extend the generic spin-only classical pipeline in `scripts/classical/classical_solver_driver.py`.

## User-Facing Interface

### Classical Method

Extend `--classical-method` in `scripts/cli/solve_pseudospin_orbital_pipeline.py` with:

- `sunny-cpn-minimize`

Full first-release set:

- `restricted-product-state`
- `sun-gswt-cpn`
- `sun-gswt-single-q`
- `sunny-cpn-minimize`

`sunny-cpn-minimize` means:

- build the existing `sun_gswt_classical` model with `build_sun_gswt_classical_payload(...)`
- construct a Sunny `System(..., :SUN)`
- load the full two-site operator using the stored `pair_matrix` with `extract_parts=false`
- minimize the classical energy with `Sunny.minimize_energy!`
- return the best classical state in the repository's serialized `local_rays` format

### Supercell Control

Add:

- `--supercell-shape NX NY NZ`

Behavior:

- available to the pseudospin-orbital CLI regardless of classical method
- defaults to `1 1 1` if omitted
- strongly recommended for nontrivial ordered states
- used by both the Sunny classical minimizer and Sunny thermodynamics backends

### Thermodynamics Stage

Add a dedicated thermodynamics stage to the pseudospin-orbital CLI:

- `--run-thermodynamics`
- `--thermodynamics-backend`

Supported backend values:

- `sunny-local-sampler`
- `sunny-parallel-tempering`
- `sunny-wang-landau`

Default:

- if `--run-thermodynamics` is set and `--thermodynamics-backend` is omitted, default to `sunny-local-sampler`

Compatibility:

- thermodynamics remains pseudospin-orbital-only in this change
- thermodynamics may run after any classical method that yields a valid `CP^(N-1)` state with `local_rays` and a compatible `supercell_shape`
- if the available classical state does not match the requested thermodynamics supercell, the CLI must fail explicitly rather than silently reinitialize to a different cell

### Common Thermodynamics CLI Arguments

Add common thermodynamics arguments:

- `--temperatures T1 T2 ...`
- `--thermo-seed`
- `--thermo-sweeps`
- `--thermo-burn-in`
- `--thermo-measurement-interval`
- `--thermo-proposal`
- `--thermo-proposal-scale`

Recommended semantics:

- `--thermo-proposal` initially supports at least `delta`, `uniform`, and `flip`
- `delta` uses a Gaussian coherent-state perturbation and consumes `--thermo-proposal-scale`

### Parallel Tempering Arguments

Add backend-specific arguments:

- `--thermo-pt-temperatures T1 T2 ...`
- `--thermo-pt-exchange-interval`

Behavior:

- `sunny-parallel-tempering` uses `--thermo-pt-temperatures` as the replica temperature schedule
- `--temperatures` still defines the temperatures reported in the final normalized thermodynamics output
- if `--thermo-pt-temperatures` is omitted for `sunny-parallel-tempering`, fail with a clear validation error

### Wang-Landau Arguments

Add backend-specific arguments:

- `--thermo-wl-bounds EMIN EMAX`
- `--thermo-wl-bin-size`
- `--thermo-wl-windows`
- `--thermo-wl-overlap`
- `--thermo-wl-ln-f`
- `--thermo-wl-sweeps`

Behavior:

- `sunny-wang-landau` computes density-of-states data and reweights it onto the requested `--temperatures`
- incompatible or incomplete Wang-Landau argument sets must fail during CLI validation

### Argument Validation Rules

The CLI must reject incompatible combinations rather than ignoring them:

- thermodynamics-only arguments without `--run-thermodynamics`
- PT-only arguments with a non-PT backend
- WL-only arguments with a non-WL backend
- missing `--temperatures` when the chosen backend requires them
- missing PT schedule for `sunny-parallel-tempering`
- missing WL bounds or bin size for `sunny-wang-landau`

## Architecture

### Keep the Existing Model Builder

Do not add a second Sunny classical payload builder.

Reuse:

- `scripts/classical/build_sun_gswt_classical_payload.py`

Reasons:

- it already encodes the approved `many_body_hr -> CP^(N-1)` mapping
- it already preserves both `pair_matrix` and `bond_tensors`
- reusing one builder keeps Python and Sunny backends comparable on the same model definition

### New Files

Add the following focused files:

- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_classical_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/sunny_sun_thermodynamics_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_classical.jl`
- `translation-invariant-spin-model-simplifier/scripts/classical/run_sunny_sun_thermodynamics.jl`

Responsibilities:

- `sunny_sun_classical_driver.py`
  - serialize payload + runtime settings to temp JSON
  - invoke `julia run_sunny_sun_classical.jl`
  - parse backend JSON
  - normalize hard-failure errors
- `sunny_sun_thermodynamics_driver.py`
  - serialize payload + runtime settings to temp JSON
  - invoke `julia run_sunny_sun_thermodynamics.jl`
  - parse backend JSON
  - convert backend-native output into repository thermodynamics artifacts
- `run_sunny_sun_classical.jl`
  - build the Sunny `System`
  - set the pair couplings with `extract_parts=false`
  - initialize coherent states
  - perform repeated minimization starts and return the best state
- `run_sunny_sun_thermodynamics.jl`
  - build the Sunny `System`
  - initialize from the supplied classical state
  - run one of the approved sampling strategies
  - emit normalized backend output and backend-specific diagnostics

### Reuse Existing Diagnostics in Python

Do not reimplement projector and stationarity diagnostics in Julia for this change.

After the Sunny classical backend returns a serialized state, reuse:

- `diagnose_sun_gswt_classical_state(...)`

from `scripts/classical/sun_gswt_classical_solver.py`.

Reasons:

- keeps diagnostics consistent with the existing Python `sun-gswt-cpn` and `sun-gswt-single-q` outputs
- avoids duplicating delicate ordering analysis logic in a second language
- reduces risk while still allowing the actual minimization to run in Sunny

## Classical Ground-State Flow

For `classical_method = sunny-cpn-minimize`:

1. Build `parsed_payload`, `simplified_payload`, and `grouped_payload` as today.
2. Build `classical_model = build_sun_gswt_classical_payload(parsed_payload)`.
3. Package runtime settings:
   - `starts`
   - `seed`
   - `supercell_shape`
   - optional initial state if later needed
4. Call `sunny_sun_classical_driver.py`.
5. The Julia backend:
   - builds the `Crystal`
   - builds `System(crystal, supercell_shape, infos, :SUN)`
   - loads full pair operators using the stored `pair_matrix`
   - randomizes or initializes coherent states
   - runs repeated `minimize_energy!` starts
   - returns the best state and backend metadata
6. Python rehydrates the returned state and calls `diagnose_sun_gswt_classical_state(...)`.
7. The final `solver_result` is written in the same artifact location used by the current CLI.

The Sunny classical backend must preserve the full two-site operator instead of projecting it onto a narrower exchange form.

## Thermodynamics Flow

Thermodynamics is a post-classical stage on the same pseudospin-orbital branch.

### Shared Flow

1. Reuse the already built `classical_model`.
2. Reuse the resolved classical state as the thermodynamics initial condition.
3. Validate supercell compatibility before launching the backend.
4. Invoke `sunny_sun_thermodynamics_driver.py` with:
   - model
   - initial state
   - chosen backend
   - backend-specific settings
5. Write normalized thermodynamics artifacts into the pipeline output directory.

### Backend Semantics

#### `sunny-local-sampler`

Use Sunny `LocalSampler` for ordinary canonical finite-temperature scans.

This is the recommended default when:

- the model is not obviously glassy or strongly trapped
- the user wants a direct finite-temperature curve without density-of-states machinery

Expected output:

- temperature-ordered energy and magnetization statistics
- derived specific heat and susceptibility
- sampling metadata including proposal family and acceptance-like statistics when available

#### `sunny-parallel-tempering`

Use Sunny `ParallelTempering` for frustrated or rough energy landscapes.

This is recommended when:

- ordinary local sampling is likely to thermalize poorly
- the task prioritizes robust equilibration across a temperature ladder

Expected output:

- the same normalized `thermodynamics_result` shape as local sampling
- additional replica-exchange diagnostics

#### `sunny-wang-landau`

Use Sunny `WangLandau` or `ParallelWangLandau` to compute density-of-states information and reweight onto requested temperatures.

This is recommended when:

- the task prioritizes density of states, entropy, or free-energy reconstruction
- wide temperature reweighting is more important than a single direct canonical scan

Expected output:

- normalized `thermodynamics_result`
- additional `dos_result`
- window/bin metadata and convergence diagnostics

## Artifact Shapes

### Solver Result

Preserve the current `solver_result.json` structure as much as possible.

Required fields for the Sunny classical method:

- `method = "sunny-cpn-minimize"`
- `manifold = "CP^(N-1)"`
- `energy`
- `supercell_shape`
- `local_rays`
- `projector_diagnostics`
- `stationarity`
- `starts`
- `seed`
- `backend`

Recommended backend block:

```json
{
  "name": "Sunny.jl",
  "mode": "SUN",
  "solver": "minimize_energy!"
}
```

### Thermodynamics Result

Write:

- `thermodynamics_result.json`

Common top-level fields:

- `method`
- `backend`
- `grid`
- `observables`
- `uncertainties`
- `sampling`
- `reference`

For local sampling and parallel tempering, `grid` should at minimum contain:

- `temperature`
- `energy`
- `magnetization`
- `specific_heat`
- `susceptibility`

For Wang-Landau, `thermodynamics_result` should additionally include:

- `free_energy`
- `entropy`

The first implementation may compute some derived quantities in Python if the Julia backend naturally returns lower-level statistics or DOS data. The external artifact format should still match the repository's normalized thermodynamics structure.

### Density-of-States Artifact

When `thermodynamics_backend = sunny-wang-landau`, also write:

- `dos_result.json`

Minimum contents:

- energy bin centers
- `ln_g(E)` or equivalent normalized density-of-states representation
- window metadata
- merge metadata if multiple windows are used

## Error Handling

Sunny-backed options must fail loudly and early.

Required hard-failure cases:

- `julia` command missing
- backend process exits nonzero
- backend stdout is not valid JSON
- `Sunny.jl` unavailable in the active Julia environment
- unsupported payload shape for the Sunny adapter
- thermodynamics backend selected without compatible classical state or supercell
- incomplete backend-specific CLI arguments

The drivers should return explicit structured errors similar to the existing LSWT Sunny adapter, and the CLI should stop rather than falling back to Python implementations.

## Reporting

Update the pseudospin-orbital phase markdown emitted by `solve_pseudospin_orbital_pipeline.py` to include:

- selected classical backend
- selected thermodynamics backend
- thermodynamics artifact presence
- backend-specific notes

Additional reporting expectations:

- if Wang-Landau runs, mention that thermodynamic curves are DOS-reweighted rather than sampled directly at each temperature
- if parallel tempering runs, include exchange statistics in the phase note
- if Sunny is unavailable, surface the exact blocking reason in the manifest and user-facing error

## Testing

Follow repository test style: Python unit tests with mocked subprocess boundaries for Julia adapters, plus lightweight source-level checks for critical Julia API usage.

Required tests:

- `tests/test_sunny_sun_classical_driver.py`
  - success path
  - missing `julia`
  - backend process failure
  - invalid JSON
- `tests/test_run_sunny_sun_classical_script.py`
  - verifies `minimize_energy!` is used
  - verifies full pair coupling is loaded without unwanted part extraction
- `tests/test_sunny_sun_thermodynamics_driver.py`
  - success path for each backend family at the driver boundary
  - missing `julia`
  - backend process failure
  - invalid JSON
- `tests/test_run_sunny_sun_thermodynamics_script.py`
  - verifies `LocalSampler` support is present
  - verifies `ParallelTempering` support is present
  - verifies `WangLandau` or `ParallelWangLandau` support is present
- extend `tests/test_solve_pseudospin_orbital_pipeline_cli.py`
  - `classical_method="sunny-cpn-minimize"`
  - `run_thermodynamics + sunny-local-sampler`
  - `run_thermodynamics + sunny-parallel-tempering`
  - `run_thermodynamics + sunny-wang-landau`
  - artifact writing checks
  - phase note content checks

## Out of Scope

The following are intentionally excluded from this change:

- generic spin-only classical or thermodynamics backend expansion
- silent fallback from Sunny choices to Python choices
- replacing existing Python `sun-gswt-cpn` or `sun-gswt-single-q`
- introducing Langevin as a first-class `thermodynamics_backend` in the initial release

Langevin remains a valid future extension, but it is not part of the first explicit backend set defined in this design.

## Implementation Notes for Planning

This design should produce one implementation plan, not multiple independent plans, because all requested work is part of one bounded subsystem:

- the pseudospin-orbital CLI
- its Sunny backend adapters
- its tests and documentation

The work should be executed incrementally with TDD:

1. add the new CLI tests that define the new options and artifacts
2. add the driver tests
3. add the minimal drivers and Julia scripts
4. connect the CLI
5. update docs and reporting

