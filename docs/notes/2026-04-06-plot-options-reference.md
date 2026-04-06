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

### 5. `lswt_figsize`

Overrides the matplotlib figure size used for the LSWT dispersion plot.

Accepted form:

- two-component list `[width, height]`

Example:

```json
{
  "plot_options": {
    "lswt_figsize": [10.5, 6.0]
  }
}
```

Current default:

- `[7.0, 4.5]`

### 6. `lswt_style`

Overrides stylistic parameters for the LSWT dispersion plot.

Currently useful keys include:

- `line_width`
- `node_line_width`
- `node_alpha`
- `grid_alpha`

Example:

```json
{
  "plot_options": {
    "lswt_style": {
      "line_width": 2.1,
      "node_line_width": 1.3,
      "node_alpha": 0.85
    }
  }
}
```

Current defaults:

```json
{
  "line_width": 1.5,
  "node_line_width": 0.8,
  "node_alpha": 0.7,
  "grid_alpha": 0.25
}
```

### 7. `thermodynamics_figsize`

Overrides the matplotlib figure size used for the thermodynamics plot.

Accepted form:

- two-component list `[width, height]`

Example:

```json
{
  "plot_options": {
    "thermodynamics_figsize": [12.0, 10.5]
  }
}
```

Current default:

- `[9.0, 9.0]`

### 8. `thermodynamics_style`

Overrides stylistic parameters for the thermodynamics plot.

Currently useful keys include:

- `line_width`
- `marker_size`
- `capsize`
- `grid_alpha`

Example:

```json
{
  "plot_options": {
    "thermodynamics_style": {
      "line_width": 1.9,
      "marker_size": 5.0,
      "capsize": 4.0
    }
  }
}
```

Current defaults:

```json
{
  "line_width": 1.6,
  "marker_size": 4.0,
  "capsize": 3.0,
  "grid_alpha": 0.25
}
```

## Expanded example

```json
{
  "plot_options": {
    "commensurate_cells": [3, 4, 1],
    "classical_figsize": [12.5, 11.0],
    "classical_style": {
      "atom_size": 520.0,
      "arrow_length_factor": 0.72,
      "arrow_line_width": 3.3
    },
    "lswt_figsize": [10.5, 6.0],
    "lswt_style": {
      "line_width": 2.1,
      "node_line_width": 1.3,
      "node_alpha": 0.85
    },
    "thermodynamics_figsize": [12.0, 10.5],
    "thermodynamics_style": {
      "line_width": 1.9,
      "marker_size": 5.0,
      "capsize": 4.0
    }
  }
}
```

## Scope note

These options currently affect:

- classical ground-state plot
- LSWT dispersion plot
- thermodynamics plot
