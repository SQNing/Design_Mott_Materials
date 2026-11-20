"""Ground-state and spectral observables from sector ED eigenpairs.

All observables are evaluated on the ground-state vector of the primary
sector unless stated otherwise. The state is first expanded over the
sector's product-state basis (``psi_v = eigenvector[rep(v)] * c_v``), which
makes every observable a sparse-basis operation without ever touching the
full Hilbert space.

Emitted block follows schema ``observables/v1``; the report layer renders
these fields verbatim and backends must not invent report-side fields.
"""

from __future__ import annotations

import numpy as np

from quantum.ed_sectors import spin_digit_data, state_powers

OBSERVABLE_KINDS = ("gaps", "correlations", "structure_factor",
                    "entanglement", "level_statistics")


def _expand_ground_state(primary):
    sector = primary["sector"]
    vector = primary["eigenvectors"][:, 0]
    return vector[sector["rep_of"]] * sector["coeff"]


def _site_positions(system):
    """Fractional coordinates (primitive-cell units) of every site."""
    basis = system.payload["lattice_structure"]["basis_sites"]
    positions = np.array([site["position"] for site in basis], dtype=float)
    result = np.zeros((system.site_count, 3))
    for index, cell in enumerate(system.cells):
        result[index * system.basis_count:(index + 1) * system.basis_count] = \
            positions + cell
    return result


def _correlation_matrix(psi, states, codes, spin):
    """C_ij = <S_i . S_j> = <Sz_i Sz_j> + 1/2 <S+_i S-_j + S-_i S+_j>."""
    d, m, up, down = spin_digit_data(spin)
    powers = state_powers(states.shape[1], d)
    count = states.shape[1]
    S = float(spin)
    digits = states.astype(np.int16)  # signed arithmetic for ladder moves
    m_states = m[states]  # (M, N)
    matrix = np.zeros((count, count))
    sz_expect = m_states * np.abs(psi)[:, None] ** 2  # (M, N) contributions
    single = sz_expect.sum(axis=0)
    for i in range(count):
        zi = sz_expect[:, i]
        for j in range(i, count):
            if i == j:
                matrix[i, j] = S * (S + 1.0)
                continue
            value = float(np.dot(zi, m_states[:, j]))
            if True:
                # 1/2 (S+_i S-_j + S-_i S+_j): flip-flop expectation.
                for table_a, table_b, delta in ((up, down, 1), (down, up, -1)):
                    valid = ((digits[:, i] + delta < d) & (digits[:, i] + delta >= 0) &
                             (digits[:, j] - delta < d) & (digits[:, j] - delta >= 0))
                    index = np.flatnonzero(valid)
                    if not len(index):
                        continue
                    amp = 0.5 * table_a[states[index, i]] * table_b[states[index, j]]
                    vcodes = codes[index] + delta * powers[i] - delta * powers[j]
                    pos = np.searchsorted(codes, vcodes)
                    pos = np.minimum(pos, len(codes) - 1)
                    found = codes[pos] == vcodes
                    value += float(np.real(np.sum(
                        np.conj(psi[pos[found]]) * amp[found] * psi[index[found]])))
            matrix[i, j] = matrix[j, i] = value
    return matrix, single


def _structure_factor(correlations, positions, q_points):
    """S(q) = (1/N) sum_ij exp(i 2 pi q.(r_i - r_j)) <S_i.S_j>."""
    count = correlations.shape[0]
    q = np.asarray(q_points, dtype=float)
    phases = np.exp(2j * np.pi * (q @ positions.T))  # (Q, N)
    s_q = np.real(np.einsum("qi,ij,qj->q", phases.conj(), correlations, phases)) / count
    points = [{"q": q[k].tolist(), "s_q": float(s_q[k])} for k in range(len(q))]
    ordering = int(np.argmax(s_q)) if len(s_q) else None
    return {"definition": "S(q) = (1/N) sum_ij e^{i 2 pi q.(r_i-r_j)} <S_i.S_j>",
            "q_units": "primitive reciprocal lattice units",
            "positions_units": "primitive lattice vectors",
            "points": points,
            "ordering_q": points[ordering]["q"] if ordering is not None else None,
            "m2_ordering": float(s_q[ordering] / count) if ordering is not None else None,
            "m2_definition": "m^2(q) = S(q)/N at the ordering vector"}


def _default_q_points(system):
    shape = np.asarray(system.shape, dtype=float)
    points = []
    for cell in system.cells:
        points.append((cell / shape).tolist())
    return points


def _entanglement_entropy(psi, states, spin, cut_sites, max_memory_mb):
    d, _m, _up, _down = spin_digit_data(spin)
    count = states.shape[1]
    cut = sorted(set(int(v) for v in cut_sites))
    if not cut or cut[0] < 0 or cut[-1] >= count or len(cut) == count:
        raise ValueError("entanglement cut must be a nonempty proper subset of sites")
    rest = [i for i in range(count) if i not in cut]
    dim_a, dim_b = d ** len(cut), d ** len(rest)
    estimated = dim_a * dim_b * 16
    if estimated > float(max_memory_mb) * 1024 ** 2:
        raise ValueError(
            "entanglement density matrix reduction (%d bytes) exceeds max_memory_mb; "
            "choose a smaller cut" % estimated)
    rows = states[:, cut].astype(np.int64) @ (d ** np.arange(len(cut) - 1, -1, -1))
    cols = states[:, rest].astype(np.int64) @ (d ** np.arange(len(rest) - 1, -1, -1))
    reduced = np.zeros((dim_a, dim_b), dtype=complex)
    reduced[rows, cols] = psi
    singular = np.linalg.svd(reduced, compute_uv=False)
    probabilities = singular ** 2
    probabilities = probabilities[probabilities > 1e-15]
    entropy = float(-np.sum(probabilities * np.log2(probabilities)))
    return {"cut_sites": cut, "complement_sites": rest,
            "definition": "bipartite von Neumann entropy of the primary-sector ground state",
            "entropy_base": 2, "von_neumann_entropy": entropy,
            "schmidt_values_above_1e-8": int(np.count_nonzero(singular > 1e-8))}


def _level_statistics(values, window=None):
    values = np.sort(np.asarray(values, dtype=float))
    if window is not None:
        low, high = float(window[0]), float(window[1])
        if not (0.0 <= low < high <= 1.0):
            raise ValueError("level_statistics_window must satisfy 0 <= low < high <= 1")
        lo = int(np.floor(low * len(values)))
        hi = max(lo + 2, int(np.ceil(high * len(values))))
        values = values[lo:hi]
    gaps = np.diff(values)
    gaps = gaps[gaps > 1e-12]
    if len(gaps) < 2:
        return {"definition": "adjacent-gap ratio r_n = min(d_n,d_{n+1})/max(d_n,d_{n+1}) "
                              "within the primary sector (degenerate gaps excluded)",
                "count": int(len(gaps)), "mean_r": None,
                "note": "too few nondegenerate spacings"}
    ratios = np.minimum(gaps[:-1], gaps[1:]) / np.maximum(gaps[:-1], gaps[1:])
    return {"definition": "adjacent-gap ratio r_n = min(d_n,d_{n+1})/max(d_n,d_{n+1}) "
                          "within the primary sector (degenerate gaps excluded)",
            "count": int(len(ratios)), "mean_r": float(np.mean(ratios)),
            "window": list(window) if window is not None else None,
            "reference": {"poisson": 0.3863, "goe": 0.5307}}


def compute_observables(primary, system, spin, request,
                        compare_sectors=None, compare_results=None):
    kinds = list(request.get("observables") or [])
    unknown = sorted(set(kinds) - set(OBSERVABLE_KINDS))
    if unknown:
        raise ValueError("unknown ED observables: " + ",".join(unknown))
    values = primary["eigenvalues"]
    max_memory_mb = float(request.get("max_memory_mb", 512))
    static = {"energy": {"total": float(values[0]) if len(values) else None,
                         "per_site": float(values[0]) / system.site_count if len(values) else None}}
    if "gaps" in kinds:
        gaps = {"definition": "E[level] - E[0] within the primary sector",
                "excitation_gaps": [float(v - values[0]) for v in values[1:]]}
        sector_gaps = []
        for spec, outcome in zip(compare_sectors or [], compare_results or []):
            their = outcome["eigenvalues"]
            if len(their):
                sector_gaps.append({
                    "definition": "E0(compare sector) - E0(primary sector)",
                    "compare_sector": {"sz_total": spec.get("sz_total"),
                                       "momentum": spec.get("momentum")},
                    "value": float(their[0] - values[0])})
        if sector_gaps:
            gaps["sector_gaps"] = sector_gaps
        static["gaps"] = gaps
    psi = None
    if set(kinds) & {"correlations", "structure_factor", "entanglement"}:
        psi = _expand_ground_state(primary)
    if set(kinds) & {"correlations", "structure_factor"}:
        correlations, single = _correlation_matrix(
            psi, primary["states"], primary["codes"], spin)
        static["correlations"] = {
            "definition": "<S_i . S_j> (isotropic dot product)",
            "site_order": "cell-major, basis-minor",
            "matrix": [[float(v) for v in row] for row in correlations],
            "local_moment": {"definition": "<S^z_i>", "values": single.tolist()}}
    if "structure_factor" in kinds:
        q_points = request.get("q_points") or _default_q_points(system)
        static["structure_factor"] = _structure_factor(
            correlations, _site_positions(system), q_points)
    if "entanglement" in kinds:
        cut = request.get("entanglement_cut")
        if cut is None:
            cut = list(range(system.site_count // 2))
        static["entanglement"] = _entanglement_entropy(
            psi, primary["states"], spin, cut, max_memory_mb)
    if "level_statistics" in kinds:
        static["level_statistics"] = _level_statistics(
            values, window=request.get("level_statistics_window"))
    return {
        "schema_version": "observables/v1",
        "provenance": {
            "backend": "ed-sparse-sector",
            "cluster": {"supercell_shape": list(system.shape),
                        "site_count": system.site_count, "boundary": "periodic"},
            "sector": {"sz_total": request.get("sz_total"),
                       "momentum": request.get("momentum")},
            "convergence": {"converged": bool(primary["converged"]),
                            "max_residual_norm": max(primary["residuals"]) if primary["residuals"] else None},
            "state": "ground_state_of_primary_sector"},
        "static": static,
        "dynamic": {"status": "deferred",
                    "reason": "Lanczos continued-fraction spectral functions are a "
                              "later-phase item; this placeholder reserves the contract field."}}
