"""MPO compiler: canonical periodic spin model -> ITensor OpSum JSON spec.

Shared stage D/E asset. Input is the same ``PeriodicSpinSystem`` the ED
backend consumes (bilinear 3x3 exchange bonds on a periodic supercell), so
every backend sees an identical Hamiltonian. Output is a versioned JSON
document (``spinforge-opsum/v1``) consumed by the Julia DMRG driver; the
spec carries an explicit 1D MPS site ordering so 2D strip geometries get a
deterministic snake path.

Scope (honest): spin-vector models with bilinear 3x3 exchange, any
half-integer spin S. Pseudospin local_dim=N N^2xN^2 pair tensors are NOT
compiled here (declared-not-connected until a pseudospin OpSum route is
designed).
"""

import math

import numpy as np

from quantum.ed_solver import _check_u1_conservation, _grouped_bonds

_OPSUM_FORMAT = "spinforge-opsum/v1"
_SPINS = ("Sx", "Sy", "Sz")


def mps_site_order(system):
    """Deterministic 1D MPS ordering of the periodic supercell.

    1D shapes use the natural cell order. 2D strips (shape[2] == 1) use a
    snake path along the shorter in-plane direction: bonds stay as short as
    possible in MPS distance, which is what DMRG needs for 2D. 3D shapes are
    rejected (stage D promises chains and strips only).

    Returns (order, geometry) where order[mps_index] = system site index.
    """
    lx, ly, lz = (int(v) for v in system.shape)
    basis = system.basis_count
    cells = np.asarray(system.cells)
    if lz != 1:
        raise ValueError(
            "DMRG backend supports 1D chains and 2D strips (shape[2] == 1); "
            "shape %s is out of scope" % (list(system.shape),))
    if lx == 1 and ly == 1:
        raise ValueError("supercell shape %s has one site; DMRG is pointless"
                         % (list(system.shape),))
    if ly == 1:
        order = np.arange(system.site_count, dtype=int)
        return order, "chain"
    # Snake: walk x columns; within a column walk y back and forth.
    order = []
    cell_of = {tuple(int(v) for v in cell): idx for idx, cell in enumerate(cells)}
    for x in range(lx):
        ys = range(ly) if x % 2 == 0 else range(ly - 1, -1, -1)
        for y in ys:
            cell = cell_of[(x, y, 0)]
            order.extend(range(cell * basis, (cell + 1) * basis))
    return np.asarray(order, dtype=int), "strip"


def compile_opsum(system, spin, request=None):
    """Compile to the spinforge-opsum/v1 JSON document.

    ``request`` keys: none required; reserved for future onsite fields.
    Raises ValueError on out-of-scope input (fail-closed, caller maps to
    invalid_request).
    """
    d = int(round(2 * float(spin) + 1))
    if d < 2 or abs(d - (2 * float(spin) + 1)) > 1e-12:
        raise ValueError("spin must be a positive integer or half-integer")
    grouped = _grouped_bonds(system)
    try:
        _check_u1_conservation(grouped)
        conserve_sz = True
    except ValueError:
        conserve_sz = False

    order, geometry = mps_site_order(system)
    mps_of = np.empty(system.site_count, dtype=int)
    mps_of[order] = np.arange(system.site_count)

    bonds = []
    for (i, j), matrix in sorted(grouped.items(), key=lambda kv: kv[0]):
        matrix = np.asarray(matrix, dtype=float)
        terms = []
        for a in range(3):
            for b in range(3):
                coefficient = float(matrix[a, b])
                if abs(coefficient) > 1e-14:
                    terms.append([_SPINS[a], _SPINS[b], coefficient])
        if terms:
            bonds.append({"source": int(mps_of[i]), "target": int(mps_of[j]),
                          "terms": terms})
    bonds.sort(key=lambda bond: (min(bond["source"], bond["target"]),
                                 max(bond["source"], bond["target"])))
    max_range = max((abs(b["target"] - b["source"]) for b in bonds), default=0)
    return {
        "format": _OPSUM_FORMAT,
        "site_count": system.site_count,
        "spin": float(spin),
        "local_dim": d,
        "geometry": geometry,
        "supercell_shape": [int(v) for v in system.shape],
        "conserve_sz": conserve_sz,
        "mps_order": [int(v) for v in order],
        "max_bond_range": max_range,
        "bonds": bonds,
    }
