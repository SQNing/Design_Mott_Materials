# Canonical CPN Pair-Model Schema

## Summary

The canonical `cpn_pair_model` payload describes a site-local `CP^(N-1)` model directly.

- `N` means the retained site-local energy-level count.
- onsite operators are `N x N`
- bond operators are `N^2 x N^2` on `C^N \otimes C^N`
- `many_body_hr` is a legacy import/export format, not the conceptual model bond_label

## Required Top-Level Fields

- `schema_version`
- `model_bond_label = "cpn_pair_model"`
- `classical_bond_label = "cpn"`
- `local_dimension`
- `structure`
- `pair_operator_convention`
- `bond_terms`

## Pair Operator Convention

Current canonical convention:

- `representation = "pair_matrix"`
- `pair_basis_order = "site_i_major_site_j_minor"`
- `tensor_view.kind = "K_ab_cd"`
- `tensor_view.index_order = ["left_bra", "right_bra", "left_ket", "right_ket"]`

## Minimal Example

```json
{
  "schema_version": 1,
  "model_bond_label": "cpn_pair_model",
  "classical_bond_label": "cpn",
  "local_dimension": 3,
  "structure": {
    "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]],
    "positions": [[0.0, 0.0, 0.0]]
  },
  "pair_operator_convention": {
    "representation": "pair_matrix",
    "pair_basis_order": "site_i_major_site_j_minor",
    "tensor_view": {
      "kind": "K_ab_cd",
      "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"]
    }
  },
  "bond_terms": [
    {
      "source": 0,
      "target": 0,
      "translation": [1, 0, 0],
      "matrix_shape": [9, 9],
      "pair_matrix": "serialized complex 9x9 matrix omitted here for brevity"
    }
  ],
  "onsite_terms": []
}
```

## Symmetry Declaration

`normalize_cpn_pair_model` always writes `symmetry.operations`,
`local_hilbert.operator_bases["op_basis:retained_local_matrix"].symmetry_actions`
and a `symmetry_synthesis` summary. Three modes are possible:

- `declared`: the payload already carried more than the identity, and every
  operation had a declared matrix-unit action. The declaration is authoritative
  and is preserved verbatim.
- `derived-from-lattice`: the cell and the magnetic basis were sufficient, so
  the crystal space group was taken from spglib, each operation was given the
  matrix-unit action implied by the retained local space, and every operation
  was re-checked against the declared `bond_terms`. Only operations that
  reproduce the declared pair matrices are kept.
- `identity-only`: nothing stronger could be certified. This is the floor, not
  an error.

A declaration that only repeats the identity carries no information and is
treated as absent, so re-normalizing a payload is a fixed point and an older
payload can still be upgraded.

The local action is `kron(U, conj(U))` on the vectorized matrix units, where `U`
is the local basis rotation. `U` is the axial rotation of the operation in the
standard `|S, m>` basis when `retained_local_space.factorization.kind` is
`generic_multiplet` or is `orbital_times_spin` with `orbital_count == 1`, and the
identity when `local_dimension == 1`.

When several orbitals are retained per site the orbital factor has to be
declared, because a rotation mixes orbitals in a way that cannot be inferred
from their number. `retained_local_space.orbital_representation` carries it in
exactly one of two encodings:

```json
"orbital_representation": {
  "convention": "real_spherical_harmonics",
  "characters": ["d_z2", "d_xz", "d_yz", "d_xy", "d_x2-y2"],
  "quantization_axis": [0.0, 0.0, 1.0]
}
```

```json
"orbital_representation": {
  "convention": "generator_matrices",
  "generators": [
    {"rotation": [[0, -1, 0], [1, 0, 0], [0, 0, 1]], "matrix": [[...]]}
  ]
}
```

`characters` names the real orbital on every retained level in basis order
(`s`, `p_x`, `p_y`, `p_z`, `d_z2`, `d_xz`, `d_yz`, `d_xy`, `d_x2-y2`). The
action is derived from the polynomial form of those functions, so the only
convention that matters is `d_z2 = 2z^2 - x^2 - y^2` and its siblings; a mixed
set of degrees acts block-diagonally. `quantization_axis` defaults to the
Cartesian `z` axis of `structure.lattice_vectors`, and an explicit `z` axis is
identical to leaving it out.

`generators` declares the action of a few operations directly, in the same
fractional-rotation convention as `symmetry.operations[].rotation`, and the
group is closed from them. Use it when the retained functions are Wannier
hybrids rather than pure harmonics. Operations the declared generators do not
cover are simply not candidates.

`build_pseudospin_orbital_payload` takes the record from the level-to-site
mapping sidecar (`--local-level-to-site-mapping`), which validates it against
the local space before the payload is built: the character count must equal
`orbital_count`, generator matrices must be unitary and of the orbital size, and
a record is rejected for a `generic_multiplet` local space. The mapping sidecar
may be passed together with a pair-identity sidecar, in which case it only
contributes the representation. A malformed record raises instead of degrading,
because a broken declaration is a producer bug rather than a model without
symmetry.

With a declared representation the payload can certify an orbital-selective
model: exchange that couples only the three `t2g` orbitals certifies all 48
cubic operations, exchange on a single orbital certifies the 16 that stabilise
it, and the same payload without a representation stays `identity-only`.
Because every derived operation is verified against the terms, the declared
group is exactly the part of the crystal group the written model realises. An
isotropic Heisenberg model on a cubic cell certifies all 48 operations, an XXZ
model certifies the 16 tetragonal ones, and an XYZ model the 8 orthorhombic
ones.

## Legacy Adapter Example

A legacy `VR_hr.dat` import may still report:

- `input_mode = "many_body_hr"`
- `raw_hr_entries`
- `raw_bond_blocks`
- `bond_blocks`

But those are compatibility/provenance views layered around the canonical contract. The normalized
payload should still expose:

- `model_bond_label = "cpn_pair_model"`
- `local_dimension = N`
- canonical `bond_terms`
- canonical `pair_operator_convention`

Legacy importers should preserve explicit `source`, `target`, and `translation` semantics in
canonical `bond_terms`, even when additional orbit metadata or representative compression is also
present.
