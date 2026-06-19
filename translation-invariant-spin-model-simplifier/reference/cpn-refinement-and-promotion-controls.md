# CP(N-1) Refinement And Promotion Controls

This note explains the workflow-level controls that affect magnetic-supercell discovery in the pseudospin-orbital `CP^(N-1)` solvers.

## Scope

These controls matter for the following classical methods:

- `sun-gswt-cpn`
- `cpn-local-ray-minimize`
- `sunny-cpn-minimize`

All three methods can use magnetic-supercell refinement after they produce a local-ray classical state. Only `sun-gswt-cpn` uses orchestration-layer auto-promotion.

## Shared Refinement Controls

### `--magnetic-supercell-max-candidate-components`

Default: `4`

This limits how many of the strongest nonzero projector Fourier components are turned into candidate magnetic supercells during refinement.

- Smaller values make refinement cheaper.
- Larger values explore more candidate orderings.

### `--magnetic-supercell-max-denominator`

Default: `16`

This controls the denominator cutoff used when rationalizing a candidate ordering wavevector `q` into a commensurate magnetic supercell.

- Smaller values are more conservative and may miss longer-period commensurate candidates.
- Larger values allow more complicated commensurate candidates but can increase search complexity.

If refinement diagnostics show no useful candidate even though the projector spectrum suggests a structured nonzero `q`, increasing this parameter is a reasonable next step.

## Promotion Controls

### `--supercell-promotion-policy`

Choices: `auto`, `none`

Default: `auto`

### `--supercell-promotion-shape NX NY NZ`

Default: `4 4 4`

These controls apply to `sun-gswt-cpn` only.

When `sun-gswt-cpn` is asked to solve `--supercell-shape 1 1 1`:

- `auto` means the workflow will also try the configured promotion shape and then compare final energy per site.
- `none` means the workflow stays on the requested shape and skips the extra promoted branch.

For `sun-gswt-cpn`, `--supercell-shape 1 1 1` with `--supercell-promotion-policy auto` does **not** mean “evaluate only `1x1x1`.” It means “start from `1x1x1`, but allow the workflow to try a conservative larger periodic branch.”

## Why `cpn-local-ray-minimize` And `sunny-cpn-minimize` Do Not Use Promotion

`cpn-local-ray-minimize` and `sunny-cpn-minimize` already have their own structural supercell search schedules driven by `max_linear_size` and convergence criteria.

Because of that:

- they do not use the `sun-gswt-cpn` orchestration-layer `1x1x1 -> promoted-shape` promotion step,
- and adding the same promotion logic on top would duplicate search work and make runtime behavior harder to interpret.

For these methods, the relevant search control is still `--max-linear-size`.

## Recommended FeI2 Pipeline Command

This is the recommended explicit command shape for the canonical FeI2 fixture workflow:

```bash
python scripts/cli/solve_pseudospin_orbital_pipeline.py \
  --poscar /path/to/POSCAR \
  --hr /path/to/VR_hr.dat \
  --output-dir /path/to/output \
  --docs-dir /path/to/output/docs \
  --classical-bond_label cpn \
  --classical-method sun-gswt-cpn \
  --supercell-shape 1 1 1 \
  --supercell-promotion-policy auto \
  --supercell-promotion-shape 4 4 4 \
  --magnetic-supercell-max-candidate-components 4 \
  --magnetic-supercell-max-denominator 16 \
  --gswt-backend python
```

If you are working from a canonical FeI2 payload fixture instead of raw
`POSCAR/hr.dat`, use a dedicated payload-wrapper workflow rather than the raw
structure-plus-`hr` entrypoint.

## Practical Tuning Order

When a `CP^(N-1)` case looks underfit:

1. First check whether the method is `sun-gswt-cpn` or a schedule-based local-ray method.
2. For `sun-gswt-cpn`, decide whether `supercell_promotion_policy=auto` is appropriate.
3. Increase `magnetic_supercell_max_candidate_components` if the dominant ordering could be hiding in lower-ranked projector peaks.
4. Increase `magnetic_supercell_max_denominator` if candidate commensurability looks too restrictive.
5. For `cpn-local-ray-minimize` or `sunny-cpn-minimize`, adjust `max_linear_size` before trying to imitate the `sun-gswt-cpn` promotion workflow.

## Regression Coverage

The current workflow regression coverage intentionally exercises three small
branch categories:

- a uniform `sun-gswt-cpn` smoke path with no accepted refinement,
- an accepted commensurate magnetic-supercell refinement path,
- and an `auto` routing path where diagnostic-only GLT falls back to `cpn-local-ray-minimize`.

## GLT Solver Mode Routing

The `cpn-generalized-lt` route has two user-facing solver-mode controls:

- `--glt-solver-mode`
- `--glt-certification-mode`

`--glt-solver-mode` has two choices: `fast` and `certified`.

Use `--glt-solver-mode fast` as the default route. It runs the direct
generalized-LT solver first and treats the result according to its reported
`solver_role`. This is the right choice when the user wants a quick lower bound,
seed candidate, or ordinary pipeline run and has not explicitly asked for proof
work.

Use `--glt-solver-mode certified` when the user explicitly asks for the
certified GLT path, proof-style GLT output, or a route that should skip the
direct fast solver and go straight to certification. In this mode, the workflow
directly runs the certified GLT path and then converts the certification summary
back into the standard solver result shape.

Interpret `--glt-certification-mode` only after the solver mode is clear:

- `--glt-certification-mode off` keeps `fast` mode on the direct solver only.
- `--glt-certification-mode auto` first runs the fast solver. If the fast result
  already reports `solver_role == "final"`, do not run the certifier. If it
  remains diagnostic-only, try certification with the fast result as the
  heuristic seed.
- `--glt-certification-mode required` means certification is mandatory and should
  enter the same certificate route as `--glt-solver-mode certified`.

In all modes, finality still comes from the result payload, not the flag name:
`solver_role == "final"` means the GLT route can be consumed as the final
classical branch. If `solver_role` remains `diagnostic-only`, report the GLT
result as a lower bound or seed and continue only through an explicit fallback or
completion route.

## How To Interpret GLT Results

For `cpn-generalized-lt`, do not decide from the method name alone whether the result is workflow-final.

- If `solver_role == "final"`, the GLT route has been promoted or certified strongly enough to be used as an ordinary final `CP^(N-1)` classical branch.
- If `solver_role` remains `diagnostic-only`, the GLT result is not a final classical branch and should be treated only as a lower bound or seed for fallback constrained minimization.

For a quick end-to-end sanity check after a run, use `reference/cpn-workflow-readiness-checklist.md`.
