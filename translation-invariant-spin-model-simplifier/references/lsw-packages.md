# Open-Source LSW Packages

When the problem is larger or more anisotropic than the in-skill helper scripts can handle cleanly, prefer an established open-source package instead of forcing a weak in-house approximation.

## Recommended Packages

### SpinW

Use SpinW first when you want a mature traditional LSWT workflow and MATLAB is acceptable.

Why it is useful:

- it is built around classical magnetic structures plus linear spin wave theory
- it supports general quadratic exchange interactions, single-ion anisotropy, magnetic field, and rotating-frame treatment of incommensurate single-`k` order
- the official `spinw.spinwave` documentation states that it can solve any single-`k` magnetic structure exactly and multi-`k` approximately

Best fit:

- bilinear spin Hamiltonians
- anisotropic exchange tensors, DM terms, single-ion anisotropy
- collinear, noncollinear, and single-`Q` incommensurate ordered states
- users who are comfortable with MATLAB

Primary or official sources:

- SpinW official docs: `https://spinw.org/spinwdoc/`
- `spinw.spinwave` docs: `https://spinw.org/spinwdoc/spinw_spinwave`
- S. Toth and B. Lake, *Linear spin wave theory for single-Q incommensurate magnetic structures*, J. Phys.: Condens. Matter 27, 166002 (2015), doi: `10.1088/0953-8984/27/16/166002`

### Sunny.jl

Use Sunny.jl when Julia is acceptable and you want a more modern open-source stack, especially for larger cells, richer anisotropy, or a path that connects LSWT with classical or semiclassical dynamics.

Why it is useful:

- the official docs describe low-temperature linear spin wave theory support
- the package highlights support for incommensurate spiral order
- the current project materials describe linear-scaling spin wave capability for large magnetic cells

Best fit:

- anisotropic or complex spin models where a Julia workflow is acceptable
- cases where you may later want classical dynamics, finite-temperature dynamics, or scalable structure-factor calculations
- large magnetic cells where iterative methods matter

Primary or official sources:

- Sunny docs: `https://sunnysuite.github.io/Sunny.jl/dev/`
- Sunny GitHub: `https://github.com/SunnySuite/Sunny.jl`
- D. Dahlbom et al., *Sunny.jl: A Julia Package for Spin Dynamics*, JOSS 10, 8138 (2025), doi: `10.21105/joss.08138`
- H. Lane et al., *Kernel polynomial method for linear spin wave theory*, SciPost Phys. 17, 145 (2024), doi: `10.21468/SciPostPhys.17.5.145`

## Package Selection Rule For This Skill

- prefer `SpinW` for standard traditional LSWT around a known classical ground state when MATLAB is available
- prefer `Sunny.jl` when Julia is available and you need scalable or more modern LSWT tooling, or expect to move beyond simple harmonic spin waves
- use the in-skill helper scripts only for small pedagogical cases, tests, and tightly scoped workflows where their known limitations are acceptable

## Reporting Rule

When you choose one of these packages during a skill run:

- state explicitly which package is being recommended or used
- explain why it is preferred over the in-skill helper scripts for the current model
- state whether the package-backed result is exact at the LSWT level for the given magnetic structure, approximate, or being proposed as a fallback path only
