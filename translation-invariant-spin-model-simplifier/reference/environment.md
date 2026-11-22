# Environment Reference for `translation-invariant-spin-model-simplifier`

This document is the skill-facing source of truth for environment readiness.
Before choosing a solver path, read this file and probe the current runtime.
Ask the user only about execution constraints or missing information that cannot
be obtained from the environment.

## How the skill should use this document

1. Confirm the user's intended path:
   - simplification only
   - classical solver
   - LSWT / GSWT
   - Sunny-backed pseudospin-orbital backends
   - report generation with PDF output
2. Check baseline dependencies first.
3. Check the optional backend-specific dependencies for the requested path.
4. If a requested backend is missing required tools, stop and tell the user what
   is missing before pretending the backend can run.

## Required baseline environment

These are the baseline requirements the skill should assume for normal use.

### Python runtime

- `python3`
  Purpose:
  Runs the normalization, parsing, simplification, classical-driver, CLI, and
  report-writing scripts.
- Recommended version:
  Python 3.10 or newer.

Verification:

```bash
python3 --version
```

### Core Python packages

- `numpy`
  Purpose:
  Used throughout the classical, LSWT, pseudospin-orbital, and adapter code.
- `scipy`
  Purpose:
  Used by optimization and linear-algebra paths in classical and certified-GLT
  solvers.
- `spglib`
  Purpose:
  Lattice symmetry detection for `build_symmetry_record` and the spin-only
  solver payload. Without it, symmetry falls back to identity only, which
  silently weakens the symmetry gate — treat it as required, not optional.
- `matplotlib`
  Purpose:
  Plot rendering (`scripts/output/render_plots.py`); CLI pipelines import it
  eagerly, so its absence breaks collection of several test modules.

Verification:

```bash
python3 - <<'PY'
import numpy
import scipy
import spglib
print("numpy", numpy.__version__)
print("scipy", scipy.__version__)
print("spglib", spglib.__version__)
PY
```

### Repository-local Python imports

The scripts expect to run from this repository checkout so imports like
`common.*`, `classical.*`, `lswt.*`, `simplify.*`, and `output.*` resolve
correctly.

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
python3 scripts/input/normalize_input.py --help
```

## Optional backend environments

These dependencies are only required for certain execution paths.

### Optional: plotting support

- `matplotlib`
  Purpose:
  Needed for plotting-oriented workflows and some report/plot helper paths.

Verification:

```bash
python3 - <<'PY'
import matplotlib
print(matplotlib.__version__)
PY
```

If missing:

- Text/JSON workflows can still run.
- Plot-generation steps should be treated as unavailable until installed.

### Optional: Sunny-backed Julia backends

Required when the user asks for:

- spin-only Sunny LSWT
- Sunny pseudospin-orbital `:SUN` classical minimization
- Sunny pseudospin-orbital thermodynamics
- Sunny-backed SUN/GSWT prototype paths

Required tools:

- `julia`
- local Julia project at `.julia-env-v09`
- local Julia depot at `scripts/.julia-depot`
- Julia packages in that project, especially:
  - `Sunny`
  - `JSON3`

Shared launcher baseline:

- All checked-in Sunny-bond_label launchers in this repository now share the same
  repo-local `.julia-env-v09` project and `scripts/.julia-depot` depot.
- This includes the spin-only LSWT launcher plus the Sunny pseudospin-orbital
  classical, thermodynamics, and SUN-GSWT launchers.

Recommended version line for current LSWT verification:

- Julia 1.12.x

Current expected Sunny line:

- `Sunny.jl 0.9.x`

Julia resolution order (all Sunny/LSWT drivers and the research adapter share
`scripts/common/julia_environment.py`):

1. an explicit `julia_cmd` argument passed to the driver,
2. `SPINFORGE_JULIA_CMD` (see below),
3. the repo-local wrapper `scripts/run_project_julia.sh`, but only when its
   configured interpreter (`SPINFORGE_JULIA_BIN`, default
   `/data/work/zhli/soft/julia-1.12.6/bin/julia`) is executable,
4. `julia` on `PATH`.

When none is available, research-workflow `calculate` actions for Sunny
backends stop with `backend-not-connected: julia-unavailable` — there is no
silent fallback to the Python backends.

Optional override:

- `SPINFORGE_JULIA_CMD`
  Purpose:
  Lets the Python-side Sunny drivers use a specific Julia binary when `julia`
  on `PATH` is older than the expected 1.12.x line.
  This override applies to:
  - the spin-only LSWT Python driver
  - the Sunny pseudospin-orbital classical driver
  - the Sunny pseudospin-orbital thermodynamics driver
  - the Sunny SUN-GSWT Python driver
- `SPINFORGE_JULIA_BIN`
  Purpose:
  Overrides the interpreter path used by `scripts/run_project_julia.sh`
  (default `/data/work/zhli/soft/julia-1.12.6/bin/julia`), so the wrapper works
  on machines where Julia 1.12.x lives elsewhere.

Legacy aliases from the pre-rename checkout are still honored:
`DESIGN_MOTT_JULIA_CMD`, `DESIGN_MOTT_JULIA_BIN`, `DESIGN_MOTT_JULIA_DEPOT`
(the `SPINFORGE_*` names take precedence).

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
/path/to/julia --project="$PWD/.julia-env-v09" -e 'using JSON3, Sunny; println("OK")'
```

If the project or depot is not yet instantiated:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
/path/to/julia --project="$PWD/.julia-env-v09" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

If missing:

- The skill may still use Python-only classical and simplification paths.
- Any requested Sunny backend should be reported as unavailable, not silently
  downgraded unless the user agrees to an alternative.

Example blocked Sunny-backed message:

```text
This request was routed through the retained-local-multiplet `many_body_hr`
path with default `generic-multiplet` / `CP^(N-1)` semantics, and the requested Sunny-backed execution could not proceed because `Julia` and/or `Sunny.jl` is
unavailable in the current environment.
```

Example opt-in alternative-backend message:

```text
The requested Sunny-backed execution is unavailable in the current environment.
If you want to continue, I can switch to an available Python-side classical or
simplification route instead, but that is an explicit alternative backend path
rather than the same Sunny-backed workflow.
```

### Optional: ITensor DMRG backend

Required when the user asks for `quantum_ground_state_dmrg` (1D chains or 2D
strip geometry beyond ED reach).

Required tools:

- `julia` (same resolution order as the Sunny backends above)
- local Julia project at `.julia-env-dmrg` with `Manifest.toml`
- Julia packages in that project: `ITensors`, `ITensorMPS`, `JSON3`

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
/path/to/julia --project="$PWD/.julia-env-dmrg" \
  --startup-file=no --history-file=no --compiled-modules=no --pkgimages=no \
  -e 'using JSON3, ITensors, ITensorMPS; println("OK")'
```

If the project is not instantiated:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
/path/to/julia --project="$PWD/.julia-env-dmrg" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

If missing: return `backend-not-connected` for the DMRG task. Do not fall back
to ED or VMC silently.

### Optional: netket VMC backend

Required when the user asks for `quantum_ground_state_vmc`.

Required tools:

- repository-local virtualenv at `.venv-netket`
- Python packages in that venv: `netket`, `jax`, `numpy`

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
.venv-netket/bin/python - <<'PY'
import jax
import netket
print("netket", netket.__version__, "jax", jax.__version__)
PY
```

If missing: return `backend-not-connected` for the VMC task. Do not fall back
to ED or DMRG silently.

### Optional: Python GSWT backend

Required when the user asks for the Python-only GSWT path rather than Sunny.

Required tools:

- baseline Python environment
- `numpy`

Recommended:

- `scipy`

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
python3 scripts/lswt/python_glswt_driver.py --help
```

### Optional: PDF report compilation

Required only when `compile_pdf=True` or when the user explicitly wants PDF
reports from the LaTeX report writers.

Required tool:

- `pdflatex`

Verification:

```bash
pdflatex --version
```

If missing:

- `.txt` and `.tex` report outputs can still be generated.
- PDF compilation should be reported as unavailable or skipped.

## Input-file expectations

These are not packages, but the skill should still confirm they exist before
starting file-backed workflows.

- For `many_body_hr` workflows:
  - `POSCAR`
  - `hr.dat` or equivalent tight-binding / effective-Hamiltonian file
- For CLI file-driven solver workflows:
  - readable input file paths
  - writable output directory

Verification:

```bash
test -f /path/to/POSCAR
test -f /path/to/hr.dat
test -d /path/to/output-dir
```

## Common failure symptoms

- `ImportError` / `ModuleNotFoundError: numpy` or `scipy`
  Meaning:
  The core Python scientific stack is incomplete.
- `missing-julia-command`
  Meaning:
  `julia` is not installed or not on `PATH`.
- `missing-sunny-package` or `missing-json3-package`
  Meaning:
  The Phase 1 LSWT Julia project/depot has not been instantiated for the local
  Sunny backend.
- `pdflatex failed` or `pdflatex` not found
  Meaning:
  PDF output was requested without a working TeX installation.
- `FileNotFoundError` for `POSCAR`, `hr.dat`, or output directories
  Meaning:
  The file-backed workflow was selected before input/output paths were checked.

## Skill preflight checklist

Before execution, inspect the following environment facts:

- Is `python3` available in the workspace environment?
- Are `numpy` and `scipy` installed?
- Is plotting needed, and if so is `matplotlib` installed?
- Is a Sunny-backed backend requested, and if so is `julia` plus the local
  Julia project already instantiated?
- If LSWT needs a newer Julia than the default `julia` on `PATH`, what should
  `SPINFORGE_JULIA_CMD` point to?
- Is PDF output required, and if so is `pdflatex` installed?
- Are all required input files already present?
## Recommended Julia launcher

Use the repo wrapper at `translation-invariant-spin-model-simplifier/scripts/run_project_julia.sh`
as the default Julia entry point for all Sunny-bond_label drivers on this machine.

It pins the checked-in Julia baseline and disables the precompile / pkgimage path
that currently fails in this environment during `REPL`-related precompilation
with `grantpt failed`.

Recommended shell export:

```bash
export SPINFORGE_JULIA_CMD=/data/work/zhli/soft/spinforge/translation-invariant-spin-model-simplifier/scripts/run_project_julia.sh
```

The wrapper currently applies:

- Julia binary: `/data/work/zhli/soft/julia-1.12.6/bin/julia`
- project: `translation-invariant-spin-model-simplifier/.julia-env-v09`
- depot: `translation-invariant-spin-model-simplifier/scripts/.julia-depot`
- flags: `--startup-file=no --history-file=no --compiled-modules=no --pkgimages=no`

This is the supported workaround until the local Julia runtime can complete a
clean `Pkg.precompile()` run in a normal PTY-backed shell.
