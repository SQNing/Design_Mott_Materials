# Independent Research Handbook

Scope: `translation-invariant-spin-model-simplifier` is the solver/thermodynamics
link in the chain. It lands an effective model, routes it to a legitimate
backend, and records evidence with explicit claim levels. It does **not** infer
missing physics and it never upgrades a finite-cell result to a thermodynamic
claim.

## 1. The contract you are holding

A run starts from one of these model representations:

- `lattice-term-contract/v1` or `canonical-hamiltonian/v1`: direct model input.
- free text / document input: normalized first; ambiguous physics becomes
  `needs_input`.
- `effective-model/v1`: inter-chain contract. Required fields:
  - `model`: the inner canonical/lattice-term model.
  - `provenance`: `dft_code`, `functional`, `u_j`, `projection_window`,
    `wannier_basis`, `date`.
  - `uncertainty`: energy/method uncertainty metadata.
  Missing provenance is a question, not a default.

Minimum request:

```json
{
  "model": {"schema_version": "canonical-hamiltonian/v1", "...": "..."},
  "question": "Ground state and low-energy scale of this effective model.",
  "requested_tasks": ["classical_ground_state", "quantum_low_energy"],
  "budget": {"max_solver_runs": 8, "max_wall_time_seconds": 1800, "max_memory_mb": 4096},
  "phase_parameters": {"J2_J1": 0.0}
}
```

`phase_parameters` is optional metadata used only by registry/phase-map
indexing; it does not change the Hamiltonian.

## 2. Standard workflow commands

```bash
python scripts/cli/research_workflow.py prepare --run-dir runs/demo --request request.json
python scripts/cli/research_workflow.py status  --run-dir runs/demo
python scripts/cli/research_workflow.py step    --run-dir runs/demo --action action.json --wait
python scripts/cli/research_workflow.py report  --run-dir runs/demo --output-dir runs/demo-report
```

A calculate action needs an idempotent `action_id`, a nonempty `reason`, and a
task name. Repeated identical actions return the same result instead of
rerunning the solver.

Useful tasks:

- `classical_ground_state`: classical fixed-length reference.
- `spin_wave_spectrum`: requires `reference_result` from a usable classical
  ground state.
- `quantum_low_energy`: ED for small Hilbert spaces, with sector controls.
- `quantum_thermodynamics`: FTLM/TPQ where connected.
- `quantum_ground_state_dmrg`: 1D chains and 2D strip geometry only.
- `quantum_ground_state_vmc`: variational upper bound; expect an energy above
  or near ED/DMRG, not below it.
- `classical_monte_carlo`: MC thermodynamics only when equilibration is
  certified; otherwise the result is explicitly not certified.

## 3. Read the evidence before reading the number

Every result separates three statuses:

- `execution_status`: `succeeded`, `reused`, `failed`, `interrupted`.
- `scientific_status`: `usable_within_scope`, `inconclusive`, `unsupported`.
- `claim_level`: `within_recorded_scope`, `stationary_reference`,
  `finite_cell_ground_state`, `thermodynamic_ground_state`.

Rules of thumb:

- `finite_cell_ground_state` is the ceiling for ED/DMRG/VMC finite clusters.
- DMRG convergence is certified per site (`variance/N`, `|ΔE|/N`) plus truncation
  discard; total variance is reported for provenance.
- VMC energy is an upper bound. If it disagrees with ED/DMRG beyond tolerance,
  the workflow reports `cross_method_inconsistent` rather than choosing one.
- MC enters comparisons only after equilibration is certified.

## 4. Common `needs_input` and the safe response

- `lattice_structure`, `local_hilbert`, `symmetry.operations`: supply explicit
  structure/symmetry; do not let the model guess.
- `hamiltonian_symmetry`: the Hamiltonian and symmetry record disagree; resolve
  the mismatch or explicitly repair only if you know why.
- `effective-model/v1` provenance: ask the upstream DFT link for the frozen
  fields. The interface is frozen before the data source is ready.

Use a `provide_input` action with `model_patch` for missing metadata, or with a
full revised `model` when the physics itself changed. Revising the model
invalidates stale references by model id.

## 5. Backend selection guide

- Tiny Hilbert space: use ED (`quantum_low_energy`) and keep sectors explicit.
- 1D large chains / narrow 2D strips: use DMRG. For Heisenberg-chain anchors,
  compare against finite-N Bethe references; the thermodynamic `1/4-ln2` value
  differs by the finite-size shift.
- 2D larger/frustrated clusters: VMC is the connected variational route; treat
  it as an upper bound and cross-check on the largest ED/DMRG-accessible cell.
- Finite temperature: FTLM/TPQ on quantum-accessible cells; MC only with
  equilibration certification.

If a backend environment is absent, the correct status is
`backend-not-connected`. There is no silent fallback.

## 6. Batch scans, registry, and phase maps

Batch file (JSON array or JSONL):

```json
[
  {"run_dir": "runs/scan/j2-0.0", "request": {"...": "...", "phase_parameters": {"J2_J1": 0.0}},
   "actions": [{"action_id": "ground", "type": "calculate", "task": "classical_ground_state",
                "reason": "scan point", "settings": {"supercell_shape": [4, 4, 1], "spin_length": 0.5}}]}
]
```

Commands:

```bash
python scripts/cli/research_batch.py --batch batch.json --registry runs/registry.jsonl --concurrency 2
python scripts/cli/research_registry.py list --registry runs/registry.jsonl --task classical_ground_state
python scripts/cli/research_registry.py phase-report --registry runs/registry.jsonl --output-dir runs/phase-map
```

The registry is append-only (`registry.jsonl`); readers keep the latest event
per `run_dir`. Cross-run cache reuse is keyed by model hash + task + settings +
reference + scoped code identity. A reused step has `solver_runs=0` and records
`reused_from_run_dir`.

## 7. Environment checklist

- Python: `numpy`, `scipy`, `spglib`, `matplotlib` for reports/plots.
- Sunny/Julia paths: `scripts/run_project_julia.sh` or `SPINFORGE_JULIA_CMD`.
- DMRG: `.julia-env-dmrg` with `ITensors`, `ITensorMPS`, `JSON3`.
- VMC: `.venv-netket` with `netket`/`jax`.
- Registry override: `SPINFORGE_RESEARCH_REGISTRY=/path/to/registry.jsonl`.

Verification commands live in `reference/environment.md`. If verification
fails, report the missing backend instead of downgrading silently.

## 8. One new-model end-to-end recipe

1. Land the model (`prepare`). If `needs_input`, answer only the recorded
   questions.
2. Establish a classical reference (`classical_ground_state`) and inspect
   `ground_state_evidence`.
3. Cross-check with the strongest affordable quantum backend (ED first, then
   DMRG/VMC within their honesty limits).
4. Add thermodynamics only after the ground-state claim is stable.
5. Record the run in the registry; batch scans should carry explicit
   `phase_parameters`.
6. Render `report` for the single run and `phase-report` for the scan. Read
   `claim_level` before quoting any number.
