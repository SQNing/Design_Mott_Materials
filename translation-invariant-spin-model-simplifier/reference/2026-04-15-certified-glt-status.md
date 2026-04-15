# Certified GLT Status Note

This note records the current state of the additive `certified_glt` work in
`translation-invariant-spin-model-simplifier` as of 2026-04-15.

It is a stage summary, not a new design spec. The canonical design and plan
documents remain:

- `../docs/superpowers/specs/2026-04-14-certified-cpn-glt-design.md`
- `../docs/superpowers/plans/2026-04-14-certified-cpn-glt.md`

## What Exists Now

The repository now contains a standalone certification-oriented subsystem under:

- `scripts/classical/certified_glt/`
- `scripts/classical/certified_glt_driver.py`

The implementation is intentionally additive. It does not replace the existing
heuristic `CP^(N-1)` generalized LT solver. Instead, it reuses heuristic seeds
for candidate discovery and layers on structured certification-oriented output.

The current package includes:

- parameter boxes and minimal interval helpers
- progress reporting for long-running certification stages
- heuristic-to-certifier seed normalization
- conservative relaxed-bound evaluation
- branch-and-bound search with telemetry
- shell certificate assembly
- projector exactness certificate assembly
- cutoff-limited commensurate lift / incommensurate-support logic
- top-level structured result assembly

## What The Top-Level Certifier Returns

`certify_cpn_generalized_lt(...)` currently returns a structured payload with:

- `heuristic_seed`
- `relaxed_global_bound`
- `lowest_shell_certificate`
- `commensurate_lift_certificate`
- `projector_exactness_certificate`
- `search_summary`
- `next_best_action`
- `next_best_actions`

The search summary already includes branch-and-bound telemetry useful for later
analysis and reruns, for example:

- processed / split / pruned box counts
- split-axis counts
- gap-channel pressure summaries
- queue-priority pressure summaries
- dominant axes / channels / branch kinds

The shell and lift layers also expose unresolved-pressure summaries so the
driver can point to the most useful next action instead of only returning
`inconclusive`.

## What Is Strict Versus What Is Operational

The current implementation is strongest when read in two layers.

### Layer A: Conservative Certification Core

These parts are intended to remain conservative and should be interpreted as
the main certification logic:

- relaxed global lower-bound search over boxed parameter domains
- shell exclusion / retention derived from bounded search records
- cutoff-dependent commensurate lifting statements
- bounded projector exactness residual checks
- conservative reporting of `incommensurate_supported` only under explicit
  cutoff and tolerance assumptions

### Layer B: Operational Workflow Support

These parts do not make the physics claim stronger. They make the workflow more
reproducible, inspectable, and schedulable:

- progress lines printed by newly added long-running code
- rerun recommendation payloads
- bundle generation
- one-command reproduction scripts
- machine-readable reproduction command templates
- compact next-action scheduling summaries

This distinction matters. The operational files help continue the search, but
they are not themselves new proofs.

## Important Honesty Constraints

The current implementation should still be described conservatively.

What it does support:

- bounded certification of relaxed lower bounds
- shell-cover style reasoning over retained / excluded boxes
- cutoff-limited commensurate feasibility or rejection
- projector exactness residual certification
- cutoff-dependent support for an incommensurate interpretation

What it does not yet support:

- an unconditional proof of the true unrestricted incommensurate ground state
- a proof over arbitrarily large commensurate supercells
- an exact analytic description of the continuous lowest-shell manifold
- replacing all heuristic upper-bound discovery with a proof-complete global
  optimizer

In particular, `incommensurate_supported` should still be read as:

- the relaxed shell remains credible
- commensurate explanations up to the configured cutoff were not certified
- the strongest certified interpretation, under the stated cutoff and
  tolerance, supports an incommensurate reading

It must not be paraphrased as a full mathematical proof of incommensurability.

## Driver And Bundle Workflow

`scripts/classical/certified_glt_driver.py` now supports:

- direct runs from an input payload
- optional output to a JSON result file
- optional output to a bundle directory
- reruns driven by a prior bundle's `rerun_suggestions.json`
- candidate selection via `--candidate-rank`

The bundle directory currently contains:

- `input_model.json`
  The serialized model used for this run.
- `certified_glt_result.json`
  The full structured result returned by the top-level certifier.
- `next_best_actions.json`
  The ranked list of next actions.
- `rerun_suggestions.json`
  The primary action plus candidate actions for later reruns.
- `applied_run_config.json`
  The actual run configuration used by the driver for this run.
- `reproduce.sh`
  A human-facing reproduction entrypoint.
- `reproduce_command.json`
  A machine-readable reproduction command template payload.
- `next_action_summary.json`
  A compact scheduler-facing summary of primary and candidate actions.
- `summary.json`
  A compact human/machine summary of statuses and applied run config.
- `README.txt`
  A short human-readable bundle summary.
- `bundle_manifest.json`
  The file index for the bundle.

## Current Reproduction Semantics

The bundle now supports two natural workflows.

### 1. Reproduce The Same Run

Human-facing:

```bash
bash reproduce.sh /path/to/output-dir
```

Machine-facing:

- use `reproduce_command.json`
- command key: `reproduce_current_run`

### 2. Launch A Suggestion-Driven Next Rerun

Human-facing:

```bash
bash reproduce.sh /path/to/output-dir --candidate-rank 2
```

Machine-facing:

- use `reproduce_command.json`
- command key: `rerun_from_suggestions_template`
- fill in `<candidate_rank>` and `<output_dir>`

This means a bundle is no longer just a frozen result artifact. It is also a
small, self-describing continuation unit for later search.

## Current Test State

At the end of this stage, the targeted verification that was exercised during
development was:

```bash
python -m pytest tests/test_certified_glt_driver.py -q
python -m pytest tests/test_certified_glt_boxes.py tests/test_certified_glt_relaxed_bounds.py tests/test_certified_glt_branch_and_bound.py tests/test_certified_glt_shell_certificate.py tests/test_certified_glt_projector_certificate.py tests/test_certified_glt_incommensurate.py tests/test_certify_cpn_glt.py tests/test_certified_glt_driver.py -q
python -m pytest tests/test_cpn_generalized_lt_solver.py -q
```

The latest observed outcomes during this stage were:

- `tests/test_certified_glt_driver.py`: 10 passed
- certified GLT related regression set: 58 passed
- `tests/test_cpn_generalized_lt_solver.py`: 5 passed

These counts are only a stage snapshot. Future edits may change them.

## Recommended Reading Order

For someone picking up this work later, the fastest path is:

1. Read this status note.
2. Read the design spec in `../docs/superpowers/specs/2026-04-14-certified-cpn-glt-design.md`.
3. Read the implementation plan in `../docs/superpowers/plans/2026-04-14-certified-cpn-glt.md`.
4. Inspect `scripts/classical/certified_glt/certify_cpn_glt.py`.
5. Inspect `scripts/classical/certified_glt_driver.py`.
6. Inspect `tests/test_certified_glt_driver.py`.

## Recommended Next Step

The next high-value addition is not another bundle file. The bundle metadata is
already rich enough for manual and semi-automatic continuation.

The most useful next step is likely an external aggregator script that scans a
set of bundle directories, reads `next_action_summary.json`, and prioritizes
which reruns to launch next based on:

- blocking reason
- suggested box budget
- candidate-action type
- overall certification status

That would turn the current single-bundle workflow into a practical batch
triage workflow without changing the underlying certification semantics.
