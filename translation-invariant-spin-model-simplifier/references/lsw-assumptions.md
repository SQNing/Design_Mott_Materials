# LSW Assumptions

The first implementation supports linear spin-wave outputs around a translation-invariant reference state.

- start from a user-approved simplified spin Hamiltonian
- if a classical ground state is already known, prefer the method described in `references/lsw-method.md`
- if the current helper cannot cover the model faithfully, consult `references/lsw-packages.md`
- require an explicit spin representation before building magnons
- report harmonic thermodynamics only where the quadratic approximation is meaningful
- state clearly when the model falls outside the implemented bilinear scope
- distinguish clearly between the recommended general LSWT method and the narrower scope of the current implementation
