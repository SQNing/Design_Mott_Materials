# Recommended LSW Method

When a classical ground state is already known, the default method to solve linear spin wave theory should be:

1. rotate every spin into a local frame aligned with its classical ordered moment
2. for single-`Q` incommensurate states, include the additional rotating-frame transformation associated with the ordering wave vector
3. apply the Holstein-Primakoff expansion in the local frames and keep terms only up to quadratic order in the bosons
4. Fourier transform over the magnetic unit cell to obtain the bosonic quadratic Hamiltonian or dynamical matrix at each momentum
5. diagonalize that quadratic bosonic problem with a paraunitary Bogoliubov method
6. if the quadratic form has zero or soft modes, use a zero-mode-capable extension of the same bosonic diagonalization machinery

Why this is the recommended default:

- it is the standard general-purpose LSWT route for collinear, coplanar, and noncollinear ordered states once the classical order is known
- it handles anisotropic bilinear spin models naturally through the local-frame rotation
- it separates the classical-ground-state problem from the harmonic fluctuation problem cleanly

Scalable fallback:

- if the magnetic unit cell is large enough that full diagonalization becomes the bottleneck, prefer sparse or kernel-polynomial approaches for dynamical correlations instead of dense diagonalization
- if the current helper scripts are too narrow for the model, check `references/lsw-packages.md` and prefer an established package rather than forcing an uncontrolled simplification

Current skill implication:

- when extending or revising the solver, treat this local-frame Holstein-Primakoff plus paraunitary-Bogoliubov pipeline as the target architecture for anisotropic bilinear models with a provided classical ground state
- do not collapse a fully anisotropic model to an effective scalar exchange unless you explicitly label that step as an approximation
- when package support is acceptable, prefer a mature open-source implementation of this pipeline before inventing a weaker in-skill workaround

Method basis:

- S. Toth and B. Lake, *Linear spin wave theory for single-Q incommensurate magnetic structures*, J. Phys.: Condens. Matter 27, 166002 (2015), doi: `10.1088/0953-8984/27/16/166002`
- J. H. P. Colpa, *Diagonalization of the quadratic boson hamiltonian*, Physica A 93, 327-353 (1978), doi: `10.1016/0378-4371(78)90160-7`
- J. H. P. Colpa, *Diagonalization of the quadratic boson Hamiltonian with zero modes*, Physica A 134, 377-416 (1986), doi: `10.1016/0378-4371(86)90056-7`
- H. Lane et al., *Kernel polynomial method for linear spin wave theory*, SciPost Phys. 17, 145 (2024), doi: `10.21468/SciPostPhys.17.5.145`
