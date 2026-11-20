# spinforge

This repository currently includes the Codex skill [`translation-invariant-spin-model-simplifier`](translation-invariant-spin-model-simplifier), which simplifies periodic spin Hamiltonians and prepares them for classical and linear-spin-wave analysis.

Current classical-stage highlights:

- geometry-aware shell mapping from lattice parameters plus fractional magnetic-atom coordinates
- classical `variational` solving that expands the magnetic supercell until the energy density converges, with early stopping once consecutive scans stabilize and a default search cap of `6x6x6` in 3D
- first-stage Sunny-backed LSWT support for explicit bilinear spin models with a validated classical reference state
- `many_body_hr` pseudospin-orbital workflows can now expose `Sunny.jl` as a classical `CP^(N-1)`-manifold minimizer through `sunny-cpn-minimize`
- `many_body_hr` pseudospin-orbital workflows can now expose Sunny finite-temperature backends through `sunny-local-sampler`, `sunny-parallel-tempering`, and `sunny-wang-landau`

The current Sunny integrations therefore split into two separate routes:

- spin-only Sunny LSWT for explicit bilinear spin Hamiltonians with spin-frame classical references
- pseudospin-orbital Sunny `:SUN` / GSWT / thermodynamics routes for `many_body_hr` models on the local `CP^(N-1)` variational manifold

For the pseudospin-orbital route, the internal target contract is now the canonical
`cpn_pair_model` contract:

- `N` means the retained site-local energy-level count
- onsite terms are first-class canonical data
- two-site bond operators are always `N^2 x N^2` matrices on the site-local tensor-product space
- legacy `VR_hr.dat` / `many_body_hr` files are adapter formats into that canonical payload, not the
  conceptual model definition

## Quick Install

### Install Directly From GitHub In Codex

If you already have Codex and the built-in `$skill-installer` skill available, use:

```text
$skill-installer

Install from GitHub:
https://github.com/correlated-insulator-lab/spinforge/tree/main/translation-invariant-spin-model-simplifier
```

After installation, restart Codex so the new skill is discovered.

### Manual Install

Clone the repository and copy the skill into your local Codex skills directory:

```bash
git clone git@github.com:correlated-insulator-lab/spinforge.git
mkdir -p ~/.codex/skills
cp -R spinforge/translation-invariant-spin-model-simplifier ~/.codex/skills/
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

For `many_body_hr` pseudospin-orbital models, the current Sunny-backed options are aimed at the `CP^(N-1)` classical variational manifold built from the projected two-site bond operators:

- this is a statement about the classical-state manifold and payload semantics, not a claim that the projected Hamiltonian is automatically SU(`N`)-symmetric
- likewise, using Sunny `:SUN` coordinates here should be read as a local/classical parametrization choice, not as an assertion that solving on `CP^(N-1)` is equivalent to imposing SU(`N`) symmetry constraints on the Hamiltonian

- `sunny-cpn-minimize` performs Sunny `:SUN` classical energy minimization on the chosen magnetic supercell
- `sunny-local-sampler` performs direct finite-temperature sampling
- `sunny-parallel-tempering` is available for rough or frustrated energy landscapes
- `sunny-wang-landau` is available when density-of-states or entropy-style outputs matter more than a direct canonical scan

If one of these Sunny-backed options is requested but `julia` or `Sunny.jl` is unavailable, the current pseudospin-orbital pipeline now fails explicitly instead of silently falling back to the Python helpers.

For direct `many_body_hr -> CP^(N-1)` payload construction, the default parser
still only guarantees `matrix_entry` provenance. That means:

- without extra metadata, multisite inputs remain conservative and may stay
  unresolved because the direct HR route does not intrinsically encode explicit
  magnetic-site `source/target` identity
- the preferred automatic route is now:
  normalized structure + `local_level_to_site_mapping`
- if no level-to-site mapping is provided, the route honestly falls back to the
  current assumed single-sublattice interpretation
- if you already have an explicit `entry_refs -> (source, target, translation)`
  file, you can still bypass automatic inference with
  `--pair-identity-sidecar`

Preferred CLI example:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/build_pseudospin_orbital_payload.py \
  --poscar POSCAR \
  --hr VR_hr.dat \
  --local-level-to-site-mapping \
  translation-invariant-spin-model-simplifier/docs/local_level_to_site_mapping.example.json
```

The preferred auxiliary JSON is a local-level ownership map, not an
`orbital × spin` factorization. Minimal example:

```json
{
  "schema_version": 1,
  "site_level_mapping": [
    { "site": 0, "level_indexes": [0, 1] },
    { "site": 1, "level_indexes": [2, 3] }
  ]
}
```

You can generate a starter template with:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/generate_local_level_to_site_mapping.py \
  --levels-per-site 2,2
```

If you already have a structure file and want the tool to infer the site count,
you can provide a single repeated level count plus optional labels:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/generate_local_level_to_site_mapping.py \
  --structure POSCAR \
  --levels-per-site 2 \
  --site-labels A,B
```

Semantics:

- `site` is the site index in the normalized structure payload
- `level_indexes` are zero-based retained local levels in the `N`-level
  `CP^(N-1)` local space
- this does not require a specific `orbital × spin` interpretation

Current validation for the level-mapping route is intentionally strict:

- every referenced `site` must exist in the normalized structure
- every `level_index` must belong to exactly one site
- no required local level may be missing ownership

When a valid level-mapping file is present, the payload upgrades from:

- `identity_level = "matrix_entry"`

to:

- `identity_level = "site_pair"`
- `pair_identity_status = "available"`
- `pair_identity_provider = "structure+level-mapping"`
- `magnetic_site_metadata.site_pair_encoding = "explicit-source-target"`

If the level-mapping file is absent, the builder does not hard-fail; it keeps
the current single-sublattice fallback. If the level-mapping file is present
but invalid, the builder raises a validation error.

Explicit pair-identity sidecars remain supported as an advanced interface:

```bash
python translation-invariant-spin-model-simplifier/scripts/cli/build_pseudospin_orbital_payload.py \
  --poscar POSCAR \
  --hr VR_hr.dat \
  --pair-identity-sidecar pair_identity.json
```

The explicit sidecar is still a narrow JSON bridge from preserved HR
`entry_refs` to explicit directed bonds. Its top-level contract is:

```json
{
  "schema_version": 1,
  "pair_identity_provider": "sidecar",
  "site_pair_encoding": "explicit-source-target",
  "coordinate_convention": "global_crystallographic",
  "hr_binding": {
    "num_wann": 4,
    "nrpts": 1,
    "R_vectors": [[1, 0, 0]]
  },
  "pair_records": [
    {
      "source": 0,
      "target": 1,
      "translation": [1, 0, 0],
      "entry_refs": [0, 1, 2, 3]
    }
  ]
}
```

Current sidecar validation is also strict:

- `hr_binding` must match the parsed HR content
- every parsed HR row must be covered exactly once across `pair_records`
- `entry_refs` ownership must be unique
- every record must use one parser-side `R`
- record `translation` must match that parser-side `R`

For translation-invariant Heisenberg-like models, the current `variational` ground-state helper does not stay locked to a single crystallographic unit cell. It scans progressively larger magnetic supercells, tracks the energy per spin, and stops early when the result is converged, with a default search cap of `6x6x6` in 3D.
