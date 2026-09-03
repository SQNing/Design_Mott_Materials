# Lattice Structure And Term Attachment

The public reference contract treats `lattice_structure` as the primary
conceptual object for runnable normalized models.

Rather than centering the payload around a model `bond_label`, attach Hamiltonian
content directly to the resolved lattice description:

- site terms
- bond terms
- higher-body terms

## Attachment Model

`lattice_structure` should carry the reusable structural description needed to
interpret where terms live:

- unit cell and coordinate convention
- basis sites or retained local objects
- translation generators or shell metadata
- any bond, plaquette, cluster, or orbit labels required by attached terms

Hamiltonian terms should then be interpreted as attachments to that structure:

- site terms act on a single attached site or retained local object
- bond terms act on an attached pair together with any direction or shell label
- higher-body terms act on an attached tuple, cluster, plaquette, or orbit

## Representative And Explicit Terms

`attach_to.orientation = representative` means that the attached term is a
generator for the referenced structural orbit. The canonical compiler expands
the orbit and applies the operator-family symmetry action to every coefficient;
for an anisotropic physical-spin exchange tensor this rotates the full `3x3`
matrix and applies conjugate transpose when bond canonicalization reverses it.

Without representative metadata, a list of terms is complete and explicit.
Missing canonical coefficients are zeros, so missing symmetry partners cause a
strict validation failure. The compiler never infers representative intent from
the number of listed terms.

Physical spin uses the axial-vector action of the structural operation. A
pseudospin, orbital, or retained-local-space basis must provide its local
symmetry/adjoint representation. If that information is absent, orbit expansion
and repair stop with `symmetry-representation-unavailable`.

## Bond Label Compatibility

Legacy payloads may still expose `bond_label`, `model_bond_label`, `classical_bond_label`,
or adapter-bond_label metadata.

Treat those fields as legacy compatibility data used for route validation or
backward-compatible adapters, not as the primary conceptual object of the
public reference contract.
