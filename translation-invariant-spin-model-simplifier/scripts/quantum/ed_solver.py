"""Sector-aware sparse exact diagonalization for finite spin clusters.

Replaces the legacy full-basis matrix-free ARPACK path. The Hamiltonian is
assembled as a sparse matrix in the requested symmetry sector (total Sz,
translation momentum, both, or neither) and the lowest eigenpairs are computed
with ARPACK (or a dense eigensolver for small sector dimensions).

Result schema keeps the legacy fields (``eigenvalues``, ``residual_norms``,
``hilbert_dimension``, ``energy_per_site``, ``converged``,
``dense_hamiltonian_allocated``) and adds a ``sector`` block plus an optional
``observables`` block (schema ``observables/v1``) and ``compare_sectors``.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse
import scipy.sparse.linalg

from quantum.ed_sectors import (enumerate_states, momentum_phases, momentum_sector,
                                spin_digit_data, state_powers, translation_group,
                                trivial_sector)

# Ladder basis change: S^x = (S+ + S-)/2, S^y = (S+ - S-)/(2i), S^z diagonal.
# Rows (x, y, z), columns (+, -, z).
_LADDER_TRANSFORM = np.array([[0.5, 0.5, 0.0],
                              [-0.5j, 0.5j, 0.0],
                              [0.0, 0.0, 1.0]], dtype=complex)
# (digit_delta_a, digit_delta_b, delta_sz) for ladder term types (+,-,z).
_TERM_DELTA = {"+": (1, 1), "-": (-1, -1), "z": (0, 0)}
_DENSE_SECTOR_LIMIT = 1024
_TRIPLET_FLUSH = 8_000_000


def _grouped_bonds(system):
    """Sum pair matrices per unordered site pair, as the legacy solver did."""
    grouped = {}
    for source, target, matrix in zip(system.source, system.target, system.matrices):
        source, target = int(source), int(target)
        if source == target:
            raise ValueError("quantum periodic images collapse onto one site; enlarge the supercell")
        if source > target:
            source, target, matrix = target, source, matrix.T
        grouped[(source, target)] = grouped.get((source, target), np.zeros((3, 3))) + matrix
    return grouped


def _ladder_decomposition(matrix):
    """Pair matrix M_ab S^a_i S^b_j -> ladder coefficients K_ab O^a_i O^b_j."""
    K = _LADDER_TRANSFORM.T @ np.asarray(matrix, dtype=complex) @ _LADDER_TRANSFORM
    labels = ("+", "-", "z")
    terms = {}
    for a, la in enumerate(labels):
        for b, lb in enumerate(labels):
            coefficient = K[a, b]
            if abs(coefficient) > 1e-14:
                terms[la + lb] = coefficient
    return terms


def _check_u1_conservation(grouped):
    """Total Sz is conserved iff every grouped bond is of XXZ+DM_z form."""
    for (i, j), matrix in grouped.items():
        K = _LADDER_TRANSFORM.T @ np.asarray(matrix, dtype=complex) @ _LADDER_TRANSFORM
        off = [K[a, b] for a in range(3) for b in range(3)
               if (a, b) not in {(0, 1), (1, 0), (2, 2)}]
        if max((abs(v) for v in off), default=0.0) > 1e-10:
            raise ValueError(
                "sz_total sector requested but bond %s does not conserve total Sz "
                "(requires Jxx==Jyy, Jxy==-Jyx and zero xz/yz components); "
                "rerun without sz_total (momentum-only or full basis)" % ((i, j),))


class _SectorHamiltonianBuilder:
    """Chunked sparse assembly of H_k = C H C† in the sector basis."""

    def __init__(self, states, codes, sector, bond_terms, tables, powers):
        self.states, self.codes, self.sector = states, codes, sector
        self.bond_terms, self.tables, self.powers = bond_terms, tables, powers
        self.dimension = sector["dimension"]
        self._rows, self._cols, self._data = [], [], []
        self._buffered = 0
        self._flushed = []

    def _emit(self, rows, cols, data):
        self._rows.append(rows)
        self._cols.append(cols)
        self._data.append(data)
        self._buffered += len(data)
        if self._buffered >= _TRIPLET_FLUSH:
            self._flush()

    def _flush(self):
        if not self._buffered:
            return
        rows = np.concatenate(self._rows)
        cols = np.concatenate(self._cols)
        data = np.concatenate(self._data)
        order = np.lexsort((cols, rows))
        rows, cols, data = rows[order], cols[order], data[order]
        bounds = np.flatnonzero(np.diff(rows.astype(np.int64) * self.dimension + cols)) + 1
        starts = np.concatenate(([0], bounds))
        reduced = np.add.reduceat(data, starts)
        self._flushed.append(scipy.sparse.csr_array(
            (reduced, (rows[starts], cols[starts])),
            shape=(self.dimension, self.dimension)))
        self._rows, self._cols, self._data = [], [], []
        self._buffered = 0

    def build(self, chunk_size=100000):
        states, codes = self.states, self.codes
        sector, tables, powers = self.sector, self.tables, self.powers
        rep_of, coeff = sector["rep_of"], sector["coeff"]
        diagonal = np.zeros(len(states), dtype=complex)
        flips = []  # (i, j, delta_code, coefficient, amp_a_table, amp_b_table, da, db)
        for (i, j), terms in self.bond_terms:
            for label, coefficient in terms.items():
                da, db = _TERM_DELTA[label[0]][0], _TERM_DELTA[label[1]][0]
                if label == "zz":
                    diagonal += coefficient * tables["z"][states[:, i]] * tables["z"][states[:, j]]
                else:
                    flips.append((i, j, coefficient, label[0], label[1], da, db))
        for start in range(0, len(states), chunk_size):
            stop = min(start + chunk_size, len(states))
            X = states[start:stop].astype(np.int16)
            chunk_codes = codes[start:stop]
            chunk_index = np.arange(start, stop)
            cols = rep_of[chunk_index]
            active = cols >= 0  # states of momentum-incompatible orbits carry no weight
            self._emit(cols[active].astype(np.int64), cols[active].astype(np.int64),
                       (diagonal[start:stop][active] * np.abs(coeff[chunk_index][active]) ** 2))
            for i, j, coefficient, la, lb, da, db in flips:
                da_d, db_d = _TERM_DELTA[la][0], _TERM_DELTA[lb][0]
                valid = ((X[:, i] + da_d >= 0) & (X[:, i] + da_d < len(tables[la])) &
                         (X[:, j] + db_d >= 0) & (X[:, j] + db_d < len(tables[lb])))
                index = chunk_index[np.flatnonzero(valid)]
                if not len(index):
                    continue
                amp = (coefficient * tables[la][states[index, i]] *
                       tables[lb][states[index, j]])
                vcodes = codes[index] + da_d * powers[i] + db_d * powers[j]
                pos = np.searchsorted(codes, vcodes)
                pos = np.minimum(pos, len(codes) - 1)
                found = codes[pos] == vcodes
                index, pos, amp = index[found], pos[found], amp[found]
                rows = rep_of[pos]
                good = (rows >= 0) & (rep_of[index] >= 0)
                if not np.any(good):
                    continue
                rows, index, pos, amp = rows[good], index[good], pos[good], amp[good]
                data = amp * np.conj(coeff[pos]) * coeff[index]
                self._emit(rows.astype(np.int64), rep_of[index].astype(np.int64), data)
        self._flush()
        result = self._flushed[0]
        for block in self._flushed[1:]:
            result = result + block
        result.sum_duplicates()
        return result.tocsr()


def _assemble_sector(system, spin, sz_total, momentum, max_memory_mb, chunk_size=100000):
    """Build (H, states, sector) for one (sz_total, momentum) sector."""
    d, m, up, down = spin_digit_data(spin)
    grouped = _grouped_bonds(system)
    if sz_total is not None:
        _check_u1_conservation(grouped)
    states, codes = enumerate_states(system.site_count, spin, sz_total)
    powers = state_powers(system.site_count, d)
    if momentum is None:
        sector = trivial_sector(states)
        group_order = 1
    else:
        coords, perms = translation_group(system.shape, system.basis_count)
        phases = momentum_phases(coords, system.shape, momentum)
        sector = momentum_sector(states, codes, perms, phases)
        group_order = len(perms)
    bond_terms = [((i, j), _ladder_decomposition(matrix))
                  for (i, j), matrix in sorted(grouped.items())]
    off_diagonal = sum(len([t for t in terms if t != "zz"]) for _b, terms in bond_terms)
    nnz_bound = len(states) * (1 + off_diagonal)
    estimated_bytes = int(nnz_bound * 24 + sector["dimension"] * 16 * 40)
    if estimated_bytes > float(max_memory_mb) * 1024 ** 2:
        raise ValueError(
            "estimated sparse assembly workspace (%d bytes) exceeds max_memory_mb; "
            "reduce the cluster or raise the memory budget" % estimated_bytes)
    tables = {"+": up, "-": down, "z": m}
    builder = _SectorHamiltonianBuilder(states, codes, sector, bond_terms, tables, powers)
    hamiltonian = builder.build(chunk_size=chunk_size)
    return hamiltonian, states, codes, sector, group_order, estimated_bytes


def _lowest_eigenpairs(hamiltonian, count, tolerance, maxiter, seed):
    dimension = hamiltonian.shape[0]
    if count < 1:
        raise ValueError("eigenvalues must request at least one level")
    if dimension <= _DENSE_SECTOR_LIMIT:
        dense = hamiltonian.toarray()
        values, vectors = scipy.linalg.eigh(
            dense, subset_by_index=[0, min(count, dimension) - 1])
        return values, vectors, "dense-lapack", 0
    if count >= dimension - 2:
        raise ValueError("ARPACK requires 1 <= eigenvalues < sector dimension - 2")
    products = 0

    def matvec(vector):
        nonlocal products
        products += 1
        return hamiltonian @ vector

    operator = scipy.sparse.linalg.LinearOperator(
        hamiltonian.shape, matvec=matvec, dtype=hamiltonian.dtype)
    rng = np.random.default_rng(int(seed))
    ncv = min(dimension, max(2 * count + 1, 20))
    try:
        values, vectors = scipy.sparse.linalg.eigsh(
            operator, k=count, which="SA", v0=rng.normal(size=dimension),
            ncv=ncv, tol=tolerance, maxiter=maxiter)
    except scipy.sparse.linalg.ArpackNoConvergence as error:
        if error.eigenvalues is None or not len(error.eigenvalues):
            return np.zeros(0), np.zeros((dimension, 0)), "arpack-lanczos", products
        order = np.argsort(error.eigenvalues)
        return (np.asarray(error.eigenvalues)[order],
                np.asarray(error.eigenvectors)[:, order], "arpack-lanczos", products)
    order = np.argsort(values)
    return values[order], vectors[:, order], "arpack-lanczos", products


def _sector_result(system, spin, sz_total, momentum, count, request):
    tolerance = float(request.get("tolerance", 1e-10))
    maxiter = int(request.get("maxiter", 1000))
    seed = int(request.get("seed", 0))
    max_memory_mb = float(request.get("max_memory_mb", 512))
    hamiltonian, states, codes, sector, group_order, estimated = _assemble_sector(
        system, spin, sz_total, momentum, max_memory_mb,
        chunk_size=int(request.get("assembly_chunk_size", 100000)))
    dimension = sector["dimension"]
    values, vectors, method, products = _lowest_eigenpairs(
        hamiltonian, min(count, dimension), tolerance, maxiter, seed)
    residuals = [float(np.linalg.norm(hamiltonian @ vectors[:, k] - values[k] * vectors[:, k]))
                 for k in range(vectors.shape[1])]
    residual_limit = max(1e-8, 10 * tolerance * max(1.0, float(np.max(np.abs(values)))
                                                    if len(values) else 1.0))
    converged = (len(values) == min(count, dimension) and
                 all(value <= residual_limit for value in residuals))
    orthogonality = float(np.linalg.norm(
        vectors.conj().T @ vectors - np.eye(vectors.shape[1]))) if vectors.shape[1] else 0.0
    return {"hamiltonian": hamiltonian, "states": states, "codes": codes, "sector": sector,
            "eigenvalues": values, "eigenvectors": vectors, "residuals": residuals,
            "converged": converged, "method": method,
            "matrix_vector_products": products, "orthogonality": orthogonality,
            "group_order": group_order, "estimated_bytes": estimated,
            "sz_basis_dimension": len(states)}


def _public_sector_block(result, sz_total, momentum, site_count, local_dim):
    sector = result["sector"]
    parts = []
    if sz_total is not None:
        parts.append("sz")
    if momentum is not None:
        parts.append("momentum")
    return {"sz_total": sz_total, "momentum": momentum,
            "basis_kind": "+".join(parts) or "full",
            "sector_dimension": sector["dimension"],
            "sz_basis_dimension": result["sz_basis_dimension"],
            "hilbert_dimension": int(local_dim) ** int(site_count),
            "translation_group_order": result["group_order"],
            "translation_orbits": sector["orbits_total"],
            "incompatible_orbits_dropped": sector["orbits_total"] - sector["dimension"]}


def solve_quantum_low_energy(system, request):
    """Finite-cluster ED with optional Sz/momentum sectors and observables."""
    from quantum.ed_observables import compute_observables
    spin = float(request["spin"])
    d, _m, _up, _down = spin_digit_data(spin)
    count = int(request.get("eigenvalues", 2))
    sz_total = request.get("sz_total")
    momentum = request.get("momentum")
    if momentum is not None:
        momentum = [int(round(float(v))) for v in momentum]
        if len(momentum) != 3:
            raise ValueError("momentum must be three integers n_i with k = 2*pi*n_i/L_i")
    primary = _sector_result(system, spin, sz_total, momentum, count, request)
    values = primary["eigenvalues"]
    converged = primary["converged"]
    sector_block = _public_sector_block(primary, sz_total, momentum,
                                        system.site_count, d)
    compare = []
    for extra in request.get("compare_sectors", []) or []:
        extra_sz = extra.get("sz_total")
        extra_k = extra.get("momentum")
        if extra_k is not None:
            extra_k = [int(round(float(v))) for v in extra_k]
        outcome = _sector_result(system, spin, extra_sz, extra_k, count, request)
        converged = converged and outcome["converged"]
        compare.append({"sector": _public_sector_block(outcome, extra_sz, extra_k,
                                                       system.site_count, d),
                        "eigenvalues": [float(v) for v in outcome["eigenvalues"]],
                        "residual_norms": outcome["residuals"],
                        "converged": bool(outcome["converged"])})
    observables = None
    requested = request.get("observables") or []
    compare_results = None
    if requested:
        observables = compute_observables(
            primary, system, spin, request,
            compare_sectors=request.get("compare_sectors") or [],
            compare_results=compare)
    return {
        "status": "ok" if converged else "inconclusive",
        "method": "sparse-sector-" + primary["method"],
        "spin": spin, "supercell_shape": list(system.shape),
        "site_count": system.site_count,
        "sector": sector_block,
        "hilbert_dimension": sector_block["hilbert_dimension"],
        "eigenvalues": [float(v) for v in values],
        "residual_norms": primary["residuals"],
        "energy_per_site": float(values[0]) / system.site_count if len(values) else None,
        "converged": bool(converged),
        "matrix_vector_products": primary["matrix_vector_products"],
        "eigenvector_orthogonality_error": primary["orthogonality"],
        "compare_sectors": compare,
        "observables": observables,
        # Legacy flag: no dense matrix over the full Hilbert space is ever
        # allocated; small sector matrices are flagged by the method string.
        "dense_hamiltonian_allocated": False,
        "sector_dense_diagonalized": bool(primary["method"] == "dense-lapack"),
        "estimated_workspace_bytes": primary["estimated_bytes"],
        "boundary": "periodic", "seed": int(request.get("seed", 0)),
        "limitations": [
            "Exact eigenpairs of the finite periodic cluster in the reported symmetry "
            "sector; no thermodynamic-limit claim.",
            "Momentum labels refer to the supercell translation group "
            "k = 2*pi*n_i/L_i.",
            "Observables are evaluated on the ground state of the primary sector "
            "unless stated otherwise."],
    }
