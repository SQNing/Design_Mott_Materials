# Plot Options Reference

This note documents the currently supported `plot_options` fields consumed by
`translation-invariant-spin-model-simplifier/scripts/render_plots.py`.

These options are optional. If omitted, the plotting pipeline falls back to its
default behavior.

## Top-level location

`plot_options` is expected at the top level of the plotting payload:

```json
{
  "plot_options": {
    "...": "..."
  }
}
```

## Supported fields

### 1. `commensurate_cells`

Controls how many **magnetic unit cells** are shown when the ordering is marked
as `commensurate`.

Accepted forms:

- single integer
- explicit three-component list

Examples:

```json
{
  "plot_options": {
    "commensurate_cells": 3
  }
}
```

```json
{
  "plot_options": {
    "commensurate_cells": [3, 4, 1]
  }
}
```

Default behavior:

- `1D`: `2 x 1 x 1`
- `2D`: `2 x 2 x 1`
- `3D`: `2 x 2 x 2`

### 2. `incommensurate_cells`

Controls how many **magnetic unit cells** are shown when the ordering is marked
as `incommensurate`.

Accepted forms:

- single integer
- explicit three-component list

Examples:

```json
{
  "plot_options": {
    "incommensurate_cells": 5
  }
}
```

```json
{
  "plot_options": {
    "incommensurate_cells": [4, 3, 2]
  }
}
```

Default behavior:

- `1D`: `5 x 1 x 1`
- `2D`: `5 x 5 x 1`
- `3D`: `5 x 5 x 5`

### 3. `classical_figsize`

Overrides the matplotlib figure size used for the classical ground-state plot.

Accepted form:

- two-component list `[width, height]`

Example:

```json
{
  "plot_options": {
    "classical_figsize": [12.5, 11.0]
  }
}
```

Current defaults:

- `chain`: `[10.5, 4.2]`
- `plane`: `[9.2, 8.2]`
- `structure`: `[9.8, 6.8]`

### 4. `classical_style`

Overrides stylistic parameters for the classical ground-state plot.

Currently useful keys include:

- `atom_size`
- `arrow_length_factor`
- `arrow_line_width`
- `atom_fill`
- `atom_edge_width`
- `spin_color`

Example:

```json
{
  "plot_options": {
    "classical_style": {
      "atom_size": 520.0,
      "arrow_length_factor": 0.72,
      "arrow_line_width": 3.3
    }
  }
}
```

Current defaults:

```json
{
  "atom_fill": "#c9c9c9",
  "atom_edge_width": 2.2,
  "atom_size": 300.0,
  "spin_color": "#d00000",
  "arrow_length_factor": 0.52,
  "arrow_line_width": 2.8
}
```

## Minimal example

```json
{
  "plot_options": {
    "commensurate_cells": [3, 4, 1],
    "classical_figsize": [12.5, 11.0],
    "classical_style": {
      "atom_size": 520.0,
      "arrow_length_factor": 0.72,
      "arrow_line_width": 3.3
    }
  }
}
```

## Scope note

These options currently affect the **classical ground-state plot** only.

They do not currently change:

- LSWT dispersion figure size
- thermodynamics figure size
- LSWT line widths or color scheme
