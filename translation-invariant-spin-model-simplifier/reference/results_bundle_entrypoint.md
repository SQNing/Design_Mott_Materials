# Results Bundle Entrypoint

This note documents the current high-level entrypoint for the
`translation-invariant-spin-model-simplifier` workflow:

`translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py`

The intended stage order is:

1. classical ground-state solve
2. thermodynamics
3. LSWT
4. report + plots

The script can now auto-populate missing stages before writing the final
bundle.

## Input contract

`scripts/cli/write_results_bundle.py` expects a **result-level payload**, not a bare
natural-language description.

In practice, the input should already include the report-facing metadata fields
used by `render_report.py`, for example:
used by `scripts/output/render_report.py`, for example:

- `normalized_model`
- `simplification`
- `canonical_model`
- `effective_model`
- `fidelity`
- `projection`

To auto-run the downstream stages, it should also include:

- `bonds` for the classical stage
- `classical` configuration
- optional `thermodynamics`
- optional `q_path` / `q_samples` for LSWT path construction

## Default behavior

By default, the script will:

1. run the classical stage if `classical_state` is missing and `bonds` are present
2. run thermodynamics if `thermodynamics_result` is missing and
   `thermodynamics.temperatures` is present
3. run LSWT if `lswt` is missing and a classical state is available
4. write:
   - `report.txt`
   - `bundle_manifest.json`
   - plots materialized by `scripts/output/render_plots.py`

This means the default command acts like a lightweight orchestrator for the
post-simplification workflow.

## Stage control flags

The entrypoint now exposes three stage-control flags:

- `--no-auto-classical`
- `--no-auto-thermodynamics`
- `--no-auto-lswt`

These only disable the **auto-population** of missing stages. If a result is
already present in the input payload, it is preserved.

## Example commands

### 1. Default automatic bundle generation

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py \
  translation-invariant-spin-model-simplifier/scripts/results_bundle_example.json \
  --output-dir ./results-bundle-example-out
```

This will try to auto-run:

- classical
- thermodynamics
- LSWT

before writing the final report and plots.

### 2. Skip LSWT auto-run

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py \
  translation-invariant-spin-model-simplifier/scripts/results_bundle_example.json \
  --output-dir ./results-bundle-example-out-no-lswt \
  --no-auto-lswt
```

This is useful when:

- the Sunny backend is not available
- you only want classical + thermodynamics + report/plots

### 3. Skip thermodynamics and LSWT auto-run

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/write_results_bundle.py \
  translation-invariant-spin-model-simplifier/scripts/results_bundle_example.json \
  --output-dir ./results-bundle-example-out-classical-only \
  --no-auto-thermodynamics \
  --no-auto-lswt
```

This keeps the bundle focused on the classical result and report/plot rendering.

## Manifest semantics

`bundle_manifest.json` now records stage-level summaries:

- `stages.classical.present`
- `stages.classical.auto_ran`
- `stages.classical.chosen_method`
- `stages.classical.requested_method`
- `stages.thermodynamics.present`
- `stages.thermodynamics.auto_ran`
- `stages.thermodynamics.temperature_count`
- `stages.lswt.present`
- `stages.lswt.auto_ran`
- `stages.lswt.status`
- `stages.lswt.backend`

This makes it possible to tell whether a stage result came from the input payload
or was populated by the bundle entrypoint itself.

## Failure behavior

If LSWT fails but classical plots succeed, the bundle usually reports
`status = partial`.

In that case:

- `report.txt` will still be written
- available plots will still be written
- the LSWT error should appear in both the report text and the plot manifest

This is the intended behavior: downstream diagnostics should remain available
even when the Sunny backend is missing or fails.
