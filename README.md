# Design_Mott_Materials

This repository currently includes the Codex skill [`translation-invariant-spin-model-simplifier`](/Users/sqning/soft/Design_Mott_Materials/translation-invariant-spin-model-simplifier), which simplifies periodic spin Hamiltonians and prepares them for classical and linear-spin-wave analysis.

Current classical-stage highlights:

- geometry-aware shell mapping from lattice parameters plus fractional magnetic-atom coordinates
- classical `variational` solving that expands the magnetic supercell until the energy density converges, with early stopping once consecutive scans stabilize and a default search cap of `6x6x6` in 3D
- first-stage Sunny-backed LSWT support for explicit bilinear spin models with a validated classical reference state
- thermodynamics output focused on energy, magnetization, specific heat, and susceptibility; absolute entropy/free energy are not yet calibrated in this first-stage classical workflow

## Quick Install

### Install Directly From GitHub In Codex

If you already have Codex and the built-in `$skill-installer` skill available, use:

```text
$skill-installer

Install from GitHub:
https://github.com/SQNing/Design_Mott_Materials/tree/main/translation-invariant-spin-model-simplifier
```

After installation, restart Codex so the new skill is discovered.

### Manual Install

Clone the repository and copy the skill into your local Codex skills directory:

```bash
git clone git@github.com:SQNing/Design_Mott_Materials.git
mkdir -p ~/.codex/skills
cp -R Design_Mott_Materials/translation-invariant-spin-model-simplifier ~/.codex/skills/
```

Optional validation:

```bash
python /path/to/codex/skills/.system/skill-creator/scripts/quick_validate.py \
  ~/.codex/skills/translation-invariant-spin-model-simplifier
```

## How To Use

Invoke it in Codex with:

```text
$translation-invariant-spin-model-simplifier
```

Then provide one of:

- an operator expression
- a local matrix or tensor
- a natural-language model description

The most reliable path right now is a controlled natural-language description that includes:

- lattice parameters
- fractional magnetic-atom coordinates
- how `J1`, `J2`, `J3`, ... map to distance shells when shell labels are used
- whether you want classical analysis only, or to continue to LSWT

The skill will then:

1. normalize and parse the model description
2. propose 2-3 simplified Hamiltonian forms and recommend one
3. ask for the next workflow decision when needed, such as the classical method or whether to continue to thermodynamics or LSWT
4. run the selected classical stage and report the magnetic structure, energy, and any scope limits

Current scope note: the optional exact-diagonalization helper is limited to spin-half dimers (`local_dim = 2`, `cluster_size = 2`). Larger local spaces or clusters are reported as unsupported rather than being approximated by the dimer solver.

For translation-invariant Heisenberg-like models, the current `variational` ground-state helper does not stay locked to a single crystallographic unit cell. It scans progressively larger magnetic supercells, tracks the energy per spin, and stops early when the result is converged, with a default search cap of `6x6x6` in 3D.
