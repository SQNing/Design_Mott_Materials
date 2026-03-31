# REVIEW

## Review Meta

- Skill: `translation-invariant-spin-model-simplifier`
- Review Scope: `Mainline implementation review state through Task 8`
- Review Mode: `Spec compliance followed by code-quality review per phase`
- Current Review Decision State: `Baseline implementation accepted previously, but a follow-up review found unresolved correctness issues in the current scope`
- Repository Status: `No local .git directory detected under the skill path`
- Environment Note: `numpy was unavailable during Task 3; pure-Python algebra was used there`
- Unknown reviewer/merge metadata: `TBD`

## Review Checklist

- [x] Task 1 scaffold existence verified
- [x] Task 1 metadata wording reviewed and aligned with scaffold scope
- [x] Task 2 normalization implementation reviewed for spec compliance
- [x] Task 2 normalization implementation reviewed for code quality
- [x] Task 3 decomposition implementation reviewed for spec compliance
- [x] Task 3 decomposition implementation reviewed for code quality
- [x] Current repository status and recent file changes captured
- [x] Recovery documents initialized
- [x] Task 4 review
- [x] Task 5 review
- [x] Task 6 review
- [x] Task 7 review
- [x] Task 8 review
- [x] Final end-to-end review

## Findings

- Task 1:
  - Initial scaffold was valid.
  - UI-facing wording in `agents/openai.yaml` overpromised solver behavior relative to the scaffold and was corrected.
  - Final Task 1 state had no blocking findings.
- Task 2:
  - The first normalization pass was under-validated.
  - Review-driven fixes were applied for required keys, stronger tests, representation-aware field selection, invalid representation rejection, missing-content rejection, malformed support rejection, freeform validation, CLI freeform routing, and natural-language spin-dimension inference.
  - Final Task 2 state had no blocking findings after the last review pass.
- Task 3:
  - Initial decomposition implementation was mathematically sound for the covered happy path, but review exposed correctness gaps around support labels, unsupported representation handling, shape validation, and non-Hermitian matrix behavior.
  - Those issues were fixed and the test suite was expanded.
  - Final Task 3 state had no Critical or Important findings in the last code-quality review.
- Current unresolved finding list:
  - `scripts/linear_spin_wave_driver.py` exact diagonalization silently ignores general `cluster_size` and `local_dim` inputs and always solves a spin-half dimer
  - `scripts/classical_solver_driver.py` thermodynamic observables are computed from cross-temperature aggregates instead of per-temperature fluctuation samples
  - `scripts/generate_simplifications.py` mislabels fully anisotropic `XYZ` models as `xxz`
  - `scripts/classical_solver_driver.py` CLI always runs the variational branch and omits thermodynamics, regardless of the advertised staged workflow
  - `scripts/run_sunny_lswt.jl` is currently a structured backend scaffold and does not yet construct full Sunny models from the LSWT payload
- Review state change:
  - `2026-03-31`: User explicitly resumed the mainline flow. Review tracking remains active, with Task 4 now the next review target.
  - `2026-03-31`: User indicated they were leaving and granted permissions in this context window, so review and implementation may continue autonomously in-session.
  - `2026-03-31`: Task 4 was temporarily blocked by an interrupted file-creation step before any Task 4 files were written. Review state remains pending for Task 4; a clean re-dispatch is required.
  - `2026-03-31`: Task 4 completed locally and was reviewed against the written plan. Targeted unit tests and a CLI smoke run both passed, and the generated output contained three candidates plus a recommended index as required.
  - `2026-03-31`: Final Task 4 review state had no blocking findings. Task 4 is accepted.
  - `2026-03-31`: Task 5 red-phase verification exposed a tool-environment interpreter mismatch rather than a business-code bug. In the skill directory, login-shell `python3` resolves to `/usr/bin/python3` without `numpy`; non-login-shell `python3` resolves to the Miniforge interpreter with `numpy` and `scipy`.
  - `2026-03-31`: A delegated Task 5 implementation attempt aborted before writing either owned file. Review state for Task 5 is unchanged: red test established, implementation still pending, and no partial code from the aborted worker needs cleanup.
  - `2026-03-31`: Task 5 completed locally. Unit tests and the required CLI smoke run both passed under the Miniforge interpreter path, and the output contained both `recommended_method` and `variational_result` as required.
  - `2026-03-31`: Final Task 5 review state had no blocking findings. Task 5 is accepted.
  - `2026-03-31`: Task 6 completed locally by extending `scripts/classical_solver_driver.py` with thermodynamics support and expanding `tests/test_classical_solver_driver.py`. The expanded test file passed under the Miniforge interpreter path.
  - `2026-03-31`: Final Task 6 review state had no blocking findings. Task 6 is accepted.
  - `2026-03-31`: Task 7 completed locally. `scripts/linear_spin_wave_driver.py` and the two supporting references landed, and the dedicated test file passed under the Miniforge interpreter path.
  - `2026-03-31`: Final Task 7 review state had no blocking findings. Task 7 is accepted.
  - `2026-03-31`: Task 8 completed locally. `scripts/render_report.py`, `references/fallback-rules.md`, the final `SKILL.md`, and regenerated `agents/openai.yaml` all landed, and the report test plus skill validator passed.
  - `2026-03-31`: Final Task 8 review state had no blocking findings. Task 8 is accepted.
  - `2026-03-31`: Final verification passed: the full test suite reported `31` passing tests, the skill validator reported `Skill is valid!`, and the staged helper smoke succeeded once the smoke harness was aligned with the existing script contracts.
  - `2026-03-31`: Final end-to-end review state had no blocking findings. The earlier smoke failures were test-harness contract mistakes, not business-code defects.
  - `2026-03-31`: Environment guidance refined after user follow-up: `python` in the skill directory resolves to `/opt/homebrew/Caskroom/miniforge/base/bin/python` and imports `numpy`, so it is also a valid shorthand for numerical verification in this workspace.
  - `2026-03-31`: Live skill use exposed a scope limitation after acceptance: `scripts/linear_spin_wave_driver.py` currently only supports a scalar exchange model. It does not yet cover the full anisotropic nearest-neighbor `XYZ` bond workflow end-to-end, so the skill presently has to stop after the classical stage or use an explicit approximation when that case appears.
  - `2026-03-31`: Live skill use also verified a manual Luttinger-Tisza workaround for the current nearest-neighbor square-lattice `XYZ` case. For the tested couplings, the LT minimum sits in the `y` channel at `(0, 0)`, giving a ferromagnetic `±y` state and resolving the classical order analytically even though no dedicated LT helper path exists yet for general anisotropic input.
  - `2026-03-31`: Live skill results were summarized into the Obsidian vault at `/Users/sqning/Documents/Obsidian Vault/2026-03-31-spin-model-simplifier-live-results.md` so the current worked example and its limitations are preserved outside the recovery docs.
  - `2026-03-31`: User requested a stable running-log target in Obsidian. Future calculation summaries for this workflow should append to `/Users/sqning/Documents/Obsidian Vault/2026-03-31-spin-model-simplifier-live-results.md` instead of creating new vault notes.
  - `2026-03-31`: The same Obsidian note was extended with an explicit interpretation section. It now records that the strongest current classical conclusion for the tested nearest-neighbor square-lattice `XYZ` case is a `y`-axis ferromagnet at `Q = (0, 0)`, while keeping the scalar-exchange spin-wave continuation labeled as an approximation.
  - `2026-03-31`: Follow-up code review after live use identified four unresolved correctness issues in the current implementation: exact diagonalization scope is overstated, thermodynamic observables are miscomputed, anisotropic `XYZ` models are misclassified as `xxz`, and the classical-driver CLI does not actually execute the staged workflow it advertises.
  - `2026-03-31`: Additional online research was incorporated into the skill docs. The LSW guidance now encodes the standard local-frame Holstein-Primakoff plus paraunitary-Bogoliubov pipeline and adds explicit open-source package guidance for SpinW and Sunny.jl. The updated skill still validates.
  - `2026-03-31`: Follow-up implementation for Sunny-backed LSWT orchestration landed on branch `codex/sunny-lswt`. The Python path now emits a structured `classical_state`, validates first-stage bilinear scope through `scripts/build_lswt_payload.py`, routes LSWT requests through a `Sunny.jl`-named backend path, and reports explicit partial-stop states when Julia or Sunny are unavailable.
  - `2026-03-31`: Fresh verification on the follow-up branch passed with `40` Python tests and `1` Julia-dependent skip under the current environment, confirming that the new orchestration layer did not break the existing tested workflow.

## Risks

- Scientific dependency risk:
  - Numerical-task verification currently depends on which interpreter the tool launches. In this environment, login-shell `python3` inside the skill directory points at `/usr/bin/python3` without `numpy`, while non-login-shell `python3` points at the Miniforge interpreter with `numpy` and `scipy`.
- Repository hygiene risk:
  - The skill path is not inside a local git repository, so commit-based checkpoints, diff-based recovery, and SHA-based review references are unavailable.
- Review continuity risk:
  - If business-code work resumes without updating these recovery docs after each phase, the recovery trail will drift.
- Residual risks:
  - Numerical verification in this tool environment still depends on using `python`, the Miniforge interpreter path, or a non-login shell because login-shell `python3` inside the skill directory resolves to `/usr/bin/python3` without `numpy`.
  - The current LSW implementation is narrower than the skill’s broader simplification/classical scope: the Python side now validates and orchestrates Sunny-backed LSWT for explicit bilinear scope, but the Julia backend is still a scaffold rather than a fully implemented Sunny model-construction pipeline.
  - Classical LT support for anisotropic cases is currently ad hoc and analytical for simple cases like nearest-neighbor square-lattice `XYZ`; it is not yet encoded as a general helper path in the skill scripts.
  - The current review state is no longer “fully clear at claimed scope”: the follow-up findings above should be resolved before treating the solver paths as broadly reliable.

## Decision

Current decision: `The baseline scaffold remains partially working with known gaps, and the new Sunny-backed follow-up improves scope handling and reporting but is not yet a complete end-to-end LSWT backend because the Julia runner is still a scaffold.`

## Follow-ups

- Update `WORKLOG.md` and `REVIEW.md` after each completed phase or any significant state change.
- On the next mainline coding round, record whether dependency installation is required before Task 4 or later numeric tasks.
- Preserve the current rule: do not redo completed work; only record accepted state and advance from the latest completed phase.
- Final verification is closed. Next follow-up, if any, should start from the accepted state recorded here without redoing completed work.
- If escalated execution becomes necessary later in this same context window, proceed using the user’s stated permission without blocking the mainline review flow.
- If LSW support for anisotropic `XYZ` bond models is requested later, treat it as a new implementation follow-up rather than assuming the current helper already covers that case.
- Preserve the user’s current logging preference: append future worked-example summaries to the existing Obsidian note rather than creating a new note per calculation.
- If reusable LT support for fully anisotropic cases is requested later, treat that as a new implementation follow-up rather than assuming the current helper scripts already provide it.
- If corrective work is requested next, prioritize: 1) fix ED scope handling, 2) fix thermodynamic observable formulas, 3) fix anisotropic template classification, 4) make the classical-driver CLI honor the advertised workflow.
- If a future run needs a stronger LSWT path before the in-skill scripts are fixed, prefer SpinW or Sunny.jl according to the new `references/lsw-packages.md` guidance.
- Complete the remaining Sunny implementation by replacing the current Julia scaffold with actual system construction, classical-state injection, and LSWT evaluation.
- Live use already reproduced the template-classification bug on a mixed-`xz` random bond example, so that issue is no longer only theoretical.
- Live use also confirmed that the current `variational` helper can recover the expected one-sublattice minimum for the pruned mixed-`xz` example, but the associated thermodynamic outputs remain subject to the already-recorded thermodynamics correctness finding.
- Live use then showed that the same one-sublattice variational result is not the true global classical minimum: a direct Luttinger-Tisza analysis found a lower `y`-axis Néel state at `Q = (pi, pi)`. This is a concrete correctness gap in the current classical solver scope, not just a documentation limitation.
- The mixed-`xz` test case now has a saved plot artifact in the Obsidian vault summarizing the LT landscape, the constrained-vs-corrected energy comparison, and the current helper thermodynamic outputs.
- The same test case now also has a presentation-oriented plot artifact showing the corrected `y`-axis Néel pattern and ordering vector `Q = (pi, pi)`.
