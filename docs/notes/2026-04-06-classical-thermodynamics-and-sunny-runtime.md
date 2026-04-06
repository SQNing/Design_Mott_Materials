# Classical Thermodynamics and Sunny Runtime Notes

## Scope

This note documents two follow-up changes to the `translation-invariant-spin-model-simplifier` workflow:

1. The classical Monte Carlo thermodynamics path now computes thermodynamic quantities with fluctuation formulas and thermodynamic integration instead of placeholder expressions.
2. The Sunny-backed LSWT runner now uses a repository-local Julia runtime layout so that the contract test can run reproducibly on the current machine.

The implementation lives primarily in:

- `translation-invariant-spin-model-simplifier/scripts/classical_solver_driver.py`
- `translation-invariant-spin-model-simplifier/scripts/render_report.py`
- `translation-invariant-spin-model-simplifier/scripts/render_plots.py`
- `translation-invariant-spin-model-simplifier/scripts/run_sunny_lswt.jl`

## Classical Thermodynamics Changes

### 1. Sampling model

The classical solver still uses local Metropolis updates, but a "sweep" is now defined as one attempted local update per spin on average. This is closer to the standard Monte Carlo convention than the previous implementation, which effectively performed one trial move per sweep.

### 2. Per-temperature observables

At each temperature, the solver now accumulates post-burn-in samples of:

- energy per spin
- magnetization per spin projected onto a chosen field direction

From these samples it computes:

- `energy`
- `magnetization`
- `specific_heat`
- `susceptibility`
- `free_energy`
- `entropy`

The heat capacity and susceptibility now use fluctuation formulas:

- `C = beta^2 * N * var(e)`
- `chi = beta * N * var(m)`

where `e` and `m` are per-spin observables.

### 3. Free energy and entropy

`free_energy` and `entropy` are no longer placeholder values. They are reconstructed by thermodynamic integration using:

- a high-temperature entropy reference
- an infinite-temperature energy reference

The helper `infer_high_temperature_energy_per_spin()` supplies a default infinite-temperature energy estimate for the current bond model.

### 4. Uncertainty and autocorrelation metadata

The thermodynamics result now includes:

- `uncertainties`
- `autocorrelation`
- `sampling`

`uncertainties` stores simple standard-error estimates for all thermodynamic observables. The current implementation uses an integrated autocorrelation time estimate to inflate the mean standard errors.

`autocorrelation` currently reports:

- energy integrated autocorrelation time
- magnetization integrated autocorrelation time

`sampling` records the thermodynamics run policy, including:

- `scan_order`
- `reuse_configuration`
- `sweeps`
- `burn_in`
- `measurement_interval`

### 5. Temperature scan policy

The thermodynamics input can now control temperature traversal order:

- `as_given`
- `ascending`
- `descending`

This is useful when warm-starting configurations across neighboring temperatures.

### 6. Output contract

If the input payload contains:

```json
{
  "thermodynamics": {
    "temperatures": [0.25, 0.5, 1.0]
  }
}
```

the solver now attaches:

```json
{
  "thermodynamics_result": {
    "grid": [...],
    "observables": {...},
    "uncertainties": {...},
    "autocorrelation": {...},
    "reference": {...},
    "sampling": {...}
  }
}
```

The `variational_result` output remains intact, so this is an additive change to the classical solver payload.

## Reporting and Plotting Changes

### 1. Text report

`render_report.py` now emits a `Classical thermodynamics` section when `thermodynamics_result` is present. The section includes:

- normalization and high-temperature reference information
- the temperature scan policy
- per-temperature values for energy, free energy, specific heat, magnetization, susceptibility, and entropy
- per-temperature uncertainties
- per-temperature autocorrelation summaries

### 2. Plot bundle

`render_plots.py` now creates `thermodynamics.png` whenever `thermodynamics_result.grid` is available.

The plot includes six panels:

- energy
- free energy
- specific heat
- magnetization
- susceptibility
- entropy

If uncertainty arrays are present, the plot uses error bars instead of plain lines.

As a result, `write_results_bundle.py` will now include this plot in the output bundle automatically.

## Sunny Runtime Notes

### 1. Why a local Julia environment was needed

The machine already had Julia `1.9.0`, but the globally active Julia package environment did not provide a compatible combination of:

- `JSON3`
- `Sunny`
- a Sunny version that exposes `SpinWaveTheory`

The registry-backed Sunny version available from the old global environment was `0.4.2`, which does not match the LSWT API expected by the runner.

To make the LSWT contract test pass reproducibly, the runner now uses repository-local Julia state.

### 2. Local runtime layout

The repository now relies on these local-only directories:

- `translation-invariant-spin-model-simplifier/.julia-depot/`
- `translation-invariant-spin-model-simplifier/.julia-env-v06/`
- `translation-invariant-spin-model-simplifier/.vendor/Sunny-v0.6.0/`

These paths are intentionally excluded through `.git/info/exclude`, so they remain local to the machine and are not added to version control.

### 3. Runner behavior

`run_sunny_lswt.jl` now:

1. rewrites `DEPOT_PATH` to the repository-local depot if present
2. activates the repository-local Julia project if present
3. loads `JSON3`
4. loads `Sunny`
5. constructs the LSWT system using the `Sunny v0.6.0` API

The runner was also updated for API compatibility:

- use `SpinInfo` instead of the earlier `Moment` assumption
- use `System(crystal, (1,1,1), infos, :dipole)`
- use `set_dipole!` for the classical reference state
- call `SpinWaveTheory(sys)` without the unsupported `measure=nothing` keyword
- unpack `dispersion()` output with the correct axis order

## Verification Summary

The following verification steps were run after these changes:

- focused Sunny LSWT contract test
- focused classical thermodynamics tests
- focused report/plot/bundle tests
- full test suite for `translation-invariant-spin-model-simplifier/tests`

At the time of writing, the full suite completed with:

- `98 passed`

## Remaining Caveats

- The uncertainty estimates are intentionally lightweight and are suitable as practical diagnostics, not as a final production-quality statistical analysis package.
- The integrated autocorrelation time estimate is a simple positive-tail truncation rule. It is serviceable for monitoring, but more sophisticated windowing could be added later.
- The local Julia environment is a machine-local runtime convenience. It is intentionally not committed.
