# Supported Models

First-version supported scope:

- translation-invariant periodic lattices
- one-site and multi-sublattice unit cells
- spin models that can be expressed as bilinear couplings after simplification
- explicit bilinear spin models that can be passed to a `Sunny.jl` backend together with a classical reference state
- small-cluster ED only when `local_dim ** cluster_size <= 256`

Recommended solver architecture beyond the current implementation:

- for a given classical ground state, use local-frame Holstein-Primakoff expansion plus paraunitary Bogoliubov diagonalization as described in `references/lsw-method.md`
- for very large magnetic unit cells, use scalable sparse or kernel-polynomial approaches instead of dense full diagonalization

Unsupported or partial-support cases:

- arbitrary non-translation-invariant models
- generic many-body local operator algebras without an explicit spin mapping
- higher-body spin interactions outside the current bilinear-plus-onsite payload builder
- full nonlinear magnon interactions
- cases where the classical reference state is missing or invalid for LSWT handoff
- environments where Julia or `Sunny.jl` are unavailable
