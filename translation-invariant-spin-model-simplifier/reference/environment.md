# Environment Reference for `translation-invariant-spin-model-simplifier`

This document is the skill-facing source of truth for environment readiness.
Before choosing a solver path, the skill should read this file and ask the user
which required and optional dependencies are already installed.

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

Verification:

```bash
python3 - <<'PY'
import numpy
import scipy
print("numpy", numpy.__version__)
print("scipy", scipy.__version__)
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
- local Julia project at `scripts/.julia-env-v06`
- local Julia depot at `scripts/.julia-depot`
- Julia packages in that project, especially:
  - `Sunny`
  - `JSON3`

Current expected Sunny line:

- `Sunny.jl 0.9.x`

Verification:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
julia --project="$PWD/scripts/.julia-env-v06" -e 'using JSON3, Sunny; println("OK")'
```

If the project or depot is not yet instantiated:

```bash
cd /path/to/translation-invariant-spin-model-simplifier
JULIA_DEPOT_PATH="$PWD/scripts/.julia-depot" \
julia --project="$PWD/scripts/.julia-env-v06" -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

If missing:

- The skill may still use Python-only classical and simplification paths.
- Any requested Sunny backend should be reported as unavailable, not silently
  downgraded unless the user agrees to an alternative.

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
  The Julia project/depot has not been instantiated for the local Sunny
  backend.
- `pdflatex failed` or `pdflatex` not found
  Meaning:
  PDF output was requested without a working TeX installation.
- `FileNotFoundError` for `POSCAR`, `hr.dat`, or output directories
  Meaning:
  The file-backed workflow was selected before input/output paths were checked.

## Skill preflight checklist

Before execution, the skill should ask the user for a quick environment status:

- Is `python3` available in the workspace environment?
- Are `numpy` and `scipy` installed?
- Is plotting needed, and if so is `matplotlib` installed?
- Is a Sunny-backed backend requested, and if so is `julia` plus the local
  Julia project already instantiated?
- Is PDF output required, and if so is `pdflatex` installed?
- Are all required input files already present?
