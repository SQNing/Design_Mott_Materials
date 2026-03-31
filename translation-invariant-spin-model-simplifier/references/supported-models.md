# Supported Models

First-version supported scope:

- translation-invariant periodic lattices
- one-site and multi-sublattice unit cells
- spin models that can be expressed as bilinear couplings after simplification
- small-cluster ED only when `local_dim ** cluster_size <= 256`

Unsupported or partial-support cases:

- arbitrary non-translation-invariant models
- generic many-body local operator algebras without an explicit spin mapping
- full nonlinear magnon interactions
