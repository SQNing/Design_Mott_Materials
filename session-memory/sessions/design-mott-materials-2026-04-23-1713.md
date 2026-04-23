# design-mott-materials Session Note

- Project: Design_Mott_Materials / translation-invariant-spin-model-simplifier
- Started: 2026-04-23 17:13 Asia/Shanghai
- Session Thread: unknown
- Workdir: /data/work/zhli/soft/Design_Mott_Materials
- Previous Note: sessions/design-mott-materials-2026-04-22-1515.md

## Session Summary

Continued the FeI2 spin-only classical workflow investigation after confirming that fixed `4x4x4` local-sweep variational did not reproduce Sunny dipole's `[1/4, 0, 1/4]` dominant branch. Added a new opt-in spin-only variational mode, `lt-single-q-cosine`, which uses the LT mode as fixed Cartesian amplitudes and minimizes the direct magnetic-supercell energy over global `Q` plus per-site/per-component phases `phi_{ia}` with `L-BFGS-B`. The mode is tested and smoke-tested on the FeI2 all-family payload.

## Turn Log

### 2026-04-23 17:13

- User intent: Implement the proposed LT-seeded ansatz route: use LT `Q` as initial output, update `Q_i` and `phi_{ia}`, and minimize energy per magnetic unit cell.
- Keywords: FeI2, LT seed, single-q cosine ansatz, Q optimization, component phases, L-BFGS-B, spin-only variational
- Key result: Added `variational.mode = "lt-single-q-cosine"` in `classical_solver_driver.py`, including LT-mode amplitude extraction, direct `Q + phi_{ia}` objective, `L-BFGS-B` optimization, explicit ordering contract, and tests proving the ansatz can optimize `Q` away from a deliberately wrong LT seed on a simple AF chain. A FeI2 smoke run with `max_linear_size=4`, `starts=2`, `maxiter=80` completed with `Q ~= [0.5, 0.129787, 0.5]` and energy `-2.064051811224947`, so the route is wired but does not yet reproduce Sunny dipole's `[1/4, 0, 1/4]`.
- Files/paths: translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/run_fei2_lt_single_q_cosine4.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/smoke_test/run_summary.json
- Next focus: Decide whether to relax fixed LT amplitudes, add analytic gradients/performance improvements, or seed directly around Sunny's `[1/4, 0, 1/4]` branch to diagnose whether the mismatch is ansatz restriction or optimizer basin.

### 2026-04-23 17:22

- User intent: Pointed out that the `Q_i, phi_{ia}` minimization should use analytic derivatives rather than SciPy finite differences.
- Keywords: analytic gradient, L-BFGS-B, Q derivative, phase derivative, FeI2 smoke, performance
- Key result: Added `_single_q_cosine_value_and_gradient()` with finite-difference regression coverage, changed the ansatz optimizer to `minimize(..., jac=True)`, and tagged output metadata with `gradient_mode = "analytic"`. The same FeI2 smoke settings now complete with `optimizer_nfev = 92` instead of the earlier finite-difference `574`, giving `Q ~= [0.499996, 0.129938, 0.499999]` and energy `-2.0640517318355713`.
- Files/paths: translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/smoke_test_grad/run_summary.json
- Next focus: With gradient cost reduced, run higher-start/higher-maxiter FeI2 ansatz jobs or change ansatz geometry toward explicit norm constraints / relaxed amplitudes.

### 2026-04-23 17:33

- User intent: Asked to confirm whether the variational energy is computed correctly and whether edge atoms in the supercell use periodic or open boundary conditions.
- Keywords: FeI2, periodic boundary, open boundary check, supercell energy, energy normalization
- Key result: Verified directly from code and by recomputation that `_supercell_energy_per_cell()` uses periodic boundary conditions through `_cell_mod(cell + bond_vector, shape)`. Recomputing the `job77922` `4x4x4` state gives exactly the reported `-2.7964826604240742`; an open-boundary counterpart for the same state gives `-2.4153772069814745`, confirming the reported value is a PBC energy per primitive cell.
- Files/paths: translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/results/run_20260423-172737_job77922/classical/solver_result.json
- Next focus: If the low `Q ~= [1/4,0,0]` energy is suspicious, inspect ansatz norm projection / explicit constraint handling rather than boundary conditions.

### 2026-04-23 17:45

- User intent: Approved checking whether the low variational energy is an artifact of the `S = u / |u|` projection.
- Keywords: projection artifact, raw norm, strong constraint, FeI2, exact LT seed, variational diagnostics
- Key result: Re-ran the same `starts=64,maxiter=400,seed=0` optimizer using the exact `lt_result` saved in `job77922` and reproduced the reported best branch exactly: `Q ~= [1/4,0,0]`, energy `-2.7964826604240742`, start `12`. Raw ansatz diagnostics show the branch is singular/pathological for the intended cosine strong constraint: 32 of 64 sites have `|u| < 1e-6`, the minimum raw norm is `7.611e-8`, the maximum raw norm is `sqrt(2)`, and `max_abs_norm_minus_1 ~= 1.0`; therefore the low energy is enabled by projection through nearly zero raw vectors rather than by a valid fixed-amplitude cosine state satisfying `|u(R)|=1`.
- Files/paths: translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/projection_diagnostic_exact_lt_job77922.json; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/results/run_20260423-172737_job77922/classical/solver_result.json
- Next focus: Replace the projection objective with an explicit strong-constraint treatment, likely penalty or constrained optimization on `|u(R,a)|^2 = 1`, before trusting energies from the `lt-single-q-cosine` branch.

### 2026-04-23 18:35

- User intent: Requested using an explicit constrained optimizer instead of projection or penalty.
- Keywords: explicit constraints, trust-constr, strong constraint, FeI2, raw norm, Sunny comparison
- Key result: Replaced the `lt-single-q-cosine` projection objective with raw-cosine energy plus explicit nonlinear equality constraints `|u(R,a)|^2 = 1` using SciPy `trust-constr`, analytic objective gradient, analytic constraint Jacobian, feasibility-first multi-start selection, and a deterministic uniform feasible seed. Focused tests pass (`33 passed, 2 expected SciPy warnings`). A full FeI2 constrained batch `job77932` with `starts=64,maxiter=400` converged to a feasible state: constraint violation `7.23e-9`, raw norms in `[0.9999999991, 1.0000000011]`, energy `-2.0010584220512966`, and `Q ~= [1/2,1/4,0]`; therefore the old `-2.796` branch was indeed a projection artifact, but the fixed-LT-amplitude explicit-constraint ansatz still does not reproduce Sunny dipole `[1/4,0,1/4]` or energy `-2.65953`.
- Files/paths: translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-lt-single-q-cosine4/results/run_20260423-181837_job77932/run_summary.json
- Next focus: The fixed LT amplitudes are likely too restrictive; next viable route is to include amplitude variables with explicit `|u|=1` constraints, or seed/compare Sunny's `[1/4,0,1/4]` pattern directly inside the same constrained objective.

### 2026-04-23 19:15

- User intent: Resumed from the latest FeI2 note, asked to "release A and continue", then approved the recommended next design path.
- Keywords: session memory, FeI2, path A, single-q harmonic ansatz, c-s parametrization, strong constraints
- Key result: Reconciled the current workspace with the active project note and clarified that the real remaining restriction is the `A cos(Q·r + phi)` single-harmonic parametrization, not merely whether amplitudes are optimization variables. Proposed three continuation routes and the user approved the recommended one: a new `lt-single-q-harmonic` variational mode using per-site Cartesian `c_i cos(Q·r) + s_i sin(Q·r)` coefficients, retaining direct supercell energy minimization and explicit `|u_i(R)|^2 = 1` constraints. The design now fixes the intended next implementation slice before any code changes.
- Files/paths: session-memory/sessions/design-mott-materials-2026-04-23-1713.md; translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py
- Next focus: Finish the last design section, then write the spec/plan and implement the new harmonic mode with test-first coverage.

### 2026-04-23 19:30

- User intent: Approved the final design section and asked to continue.
- Keywords: spec write, single-q harmonic, FeI2, approved design, next plan
- Key result: Wrote the approved design spec for the new `lt-single-q-harmonic` constrained variational mode, covering motivation, `c/s` harmonic parametrization, LT seeding, direct objective plus explicit `|u_i(R)|^2=1` constraints, analytic derivatives, contract preservation, and focused TDD coverage. The next gate is user review of the written spec before moving to the implementation plan.
- Files/paths: translation-invariant-spin-model-simplifier/docs/superpowers/specs/2026-04-23-single-q-harmonic-variational-design.md
- Next focus: Wait for user review of the written spec, then create the implementation plan.

### 2026-04-23 19:34

- User intent: Approved the written spec and asked to continue into planning.
- Keywords: writing plans, implementation plan, single-q harmonic, TDD, FeI2
- Key result: Wrote the implementation plan for `lt-single-q-harmonic`, keeping the work scoped to `classical_solver_driver.py` plus `test_classical_solver_driver.py` and decomposing execution into routing, derivative helpers, constrained solver completion, and focused regression/A-B comparison tasks. Per the current session constraints, the plan was reviewed locally against the spec instead of dispatching a subagent reviewer.
- Files/paths: translation-invariant-spin-model-simplifier/docs/superpowers/plans/2026-04-23-single-q-harmonic-variational.md
- Next focus: Wait for the user's go-ahead to execute the plan.

### 2026-04-23 19:55

- User intent: Approved executing the plan.
- Keywords: TDD, lt-single-q-harmonic, trust-constr, analytic derivatives, FeI2 A/B smoke
- Key result: Implemented the new `lt-single-q-harmonic` variational route in `classical_solver_driver.py`: LT complex modes now seed Cartesian harmonic coefficients `c_i,s_i`, raw states use `u_i(R)=c_i cos(Q·r)+s_i sin(Q·r)`, objective gradients and constraint Jacobians are analytic, and the full route uses `trust-constr` with explicit `|u_i(R)|^2=1` constraints and harmonic diagnostics. Focused tests pass: `test_classical_solver_driver.py` (`22 passed`), `test_lt_solver.py` (`2 passed`), `test_generalized_lt_solver.py` (`3 passed`), and `test_lt_tensor_constraint_completion.py` (`11 passed`). A small FeI2 A/B smoke at `starts=4,maxiter=120,max_linear_size=4` produced a feasible harmonic state with `Q ~= [0.5,0.1638358664,0.5]`, energy `0.0301063784`, constraint violation `4.42e-9`, and raw norm residual `2.21e-9`, but hit the iteration limit (`optimizer_success=false`), so it is a reachability/comparability smoke rather than a converged physics result.
- Files/paths: translation-invariant-spin-model-simplifier/scripts/classical/classical_solver_driver.py; translation-invariant-spin-model-simplifier/tests/test_classical_solver_driver.py; translation-invariant-spin-model-simplifier/tmp/fei2-workflow-2026-04-23/run-effective-all-families-single-q-harmonic-ab-smoke/comparison_summary.json
- Next focus: If continuing the FeI2 investigation, rerun harmonic with larger `maxiter/starts` and compare against the best constrained cosine job rather than the small-budget smoke.
