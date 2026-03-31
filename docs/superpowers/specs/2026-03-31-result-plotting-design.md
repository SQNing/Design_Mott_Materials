# Result Plotting Design

## Context

The `translation-invariant-spin-model-simplifier` skill can now carry a first-stage bilinear spin workflow through simplification, classical solving, and Sunny-backed LSWT execution for at least a minimal verified example. The current outputs are still primarily textual or JSON-like. Users now want result visualization, specifically:

- linear spin-wave dispersion plots
- classical ground-state configuration plots

The plotting workflow must both:

- generate image files automatically
- preserve machine-readable plot inputs so the same figures can be regenerated or restyled later

## Goal

Add a first-stage plotting pipeline that automatically produces plot image files and a reusable plotting payload from completed classical plus LSWT results.

## Recommended Approach

Add a dedicated Python plotting script instead of embedding plotting into the report renderer.

Why:

- report generation and plotting have different responsibilities
- plotting will expand over time and should remain independently testable
- re-rendering plots should not require re-running the whole reporting step
- Python is already the orchestration layer, and `matplotlib` is a natural fit for both dispersion curves and arrow-style spin configuration plots

## Scope

First-stage supported plots:

- `lswt_dispersion.png`
- `classical_state.png`
- `plot_payload.json`

First-stage non-goals:

- publication-grade high-symmetry path labeling
- full crystallographic embedding for arbitrary lattices
- interactive plotting
- heatmaps, structure factors, or thermodynamic figures

## Output Layout

For a given run directory, the plotting stage should create:

- `plot_payload.json`
- `lswt_dispersion.png`
- `classical_state.png`

These outputs should live alongside the run report, not inside temporary directories that disappear after execution.

## Data Flow

The plotting stage should consume the assembled run payload after classical and LSWT execution:

`classical -> lswt -> assembled result payload -> render_plots.py -> PNG files + plot_payload.json -> render_report.py references outputs`

The plotting layer should not recalculate physics. It should only transform existing result data into visualization-ready structures and figures.

## Plot Payload Contract

The plotting script should emit a normalized `plot_payload.json` containing:

### Metadata

- `model_name`
- `generated_at`
- `backend`
- `classical_method`
- `lswt_status`

### Classical Plot Section

- `site_frames`
- `ordering`
- `site_labels`
- optional `layout_hint`

### LSWT Plot Section

- `dispersion`
- `band_count`
- `q_points`
- `q_labels` or `q_indices`
- `omega_min`
- `omega_max`

This payload is the durable source for re-rendering plots later with different styles.

## Figure Designs

### LSWT Dispersion Plot

First-stage design:

- x-axis: q-point index
- y-axis: `omega`
- one line per magnon band
- title includes backend and model name when available

Design rationale:

- robust to generic q-paths without needing full symmetry labeling
- works immediately with the current Sunny return format
- easy to test deterministically

### Classical Ground-State Plot

First-stage design:

- x-axis: site order in `classical_state.site_frames`
- each site rendered as an arrow
- arrow direction encodes spin direction projected into a simple 2D view
- title includes ordering vector and classical method when available

Design rationale:

- stable for one-sublattice and small multi-site examples
- avoids premature dependence on full geometric embedding
- still communicates the ordered-state pattern clearly

## Failure Behavior

The plotting stage must degrade gracefully:

- if `classical_state` is present, `classical_state.png` should still be produced even when LSWT failed
- if LSWT is missing or failed, `plot_payload.json` should record that status
- `lswt_dispersion.png` may be skipped, but the skip reason must be explicit and machine-readable

The plotting script should return structured metadata indicating:

- which plots were generated
- which plots were skipped
- why any plot was skipped

## Integration Strategy

Add a new plotting step rather than hiding plotting inside reporting:

- `scripts/render_plots.py` generates images and the plot payload
- `scripts/render_report.py` references the produced image paths and summarizes whether plotting succeeded

This keeps plotting optional, composable, and testable.

## Testing Strategy

### Unit Tests

Add tests for:

- generating `plot_payload.json` from a minimal successful result payload
- generating `lswt_dispersion.png` for a minimal Sunny-backed success case
- generating `classical_state.png` from `classical_state.site_frames`
- partial success behavior when LSWT failed but classical data exists

### End-to-End Plot Test

Use the verified minimal ferromagnetic Heisenberg Sunny example and assert:

- `plot_payload.json` exists
- `lswt_dispersion.png` exists and is non-empty
- `classical_state.png` exists and is non-empty

## Recommendation

Proceed with a dedicated `render_plots.py` script that automatically writes `PNG` figures plus a reusable `plot_payload.json`, and integrate it as a separate stage adjacent to report rendering.
