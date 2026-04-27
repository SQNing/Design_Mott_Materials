# Canonical CPN Pair-Model Schema

## Summary

The canonical `cpn_pair_model` payload describes a site-local `CP^(N-1)` model directly.

- `N` means the retained site-local energy-level count.
- onsite operators are `N x N`
- bond operators are `N^2 x N^2` on `C^N \otimes C^N`
- `many_body_hr` is a legacy import/export format, not the conceptual model family

## Required Top-Level Fields

- `schema_version`
- `model_family = "cpn_pair_model"`
- `classical_family = "cpn"`
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
  "model_family": "cpn_pair_model",
  "classical_family": "cpn",
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

## Legacy Adapter Example

A legacy `VR_hr.dat` import may still report:

- `input_mode = "many_body_hr"`
- `raw_hr_entries`
- `raw_bond_blocks`
- `bond_blocks`

But those are compatibility/provenance views layered around the canonical contract. The normalized
payload should still expose:

- `model_family = "cpn_pair_model"`
- `local_dimension = N`
- canonical `bond_terms`
- canonical `pair_operator_convention`

Legacy importers should preserve explicit `source`, `target`, and `translation` semantics in
canonical `bond_terms`, even when additional orbit metadata or representative compression is also
present.
