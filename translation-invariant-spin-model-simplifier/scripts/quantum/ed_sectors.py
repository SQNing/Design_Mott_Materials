"""Symmetry-sector bases for finite-cluster exact diagonalization.

Basis states are digit arrays: site ``i`` holds digit ``d_i`` in ``[0, D)`` with
``D = 2S + 1`` and spin projection ``m_i = d_i - S``. A state code is the
base-``D`` integer with site 0 as the most significant digit, so the recursive
enumeration below yields codes in ascending order.

Two sector types are supported and compose:

- total ``Sz``: only states with ``sum(d_i) = sz_total + N*S``. Requesting it
  for a Hamiltonian that does not conserve total ``Sz`` is an explicit error
  (checked by the solver on the grouped pair matrices).
- translation momentum ``k = 2*pi*n_i/L_i`` on the periodic supercell. The
  sector basis uses symmetrized orbit representatives
  ``|r;k> = sum_v c_{r,v} |v>`` with ``c_{r,v} = sqrt(|stab(r)|/|G|) *
  exp(-i k.u(v))`` for ``v = T_{u(v)} r``. Representatives whose stabilizer
  has a nontrivial character at ``k`` are dropped (their symmetrized state
  vanishes). The Hamiltonian is assembled as the exact sandwich
  ``H_k[r,s] = sum_{v,w} conj(c_{r,v}) H_{v,w} c_{s,w}``, which needs no
  special-casing of stabilizers.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np


def spin_digit_data(spin):
    """(local_dim, m_of_digit, ladder_up, ladder_down) for the given spin."""
    S = float(spin)
    d = int(round(2 * S + 1))
    if S <= 0 or not np.isfinite(S) or abs(d - (2 * S + 1)) > 1e-12:
        raise ValueError("spin must be a positive integer or half-integer")
    m = np.arange(d, dtype=float) - S
    up = np.sqrt(np.maximum(0.0, (S - m) * (S + m + 1)))
    down = np.sqrt(np.maximum(0.0, (S + m) * (S - m + 1)))
    return d, m, up, down


def state_powers(site_count, local_dim):
    """Base-D place values with site 0 most significant."""
    return local_dim ** np.arange(site_count - 1, -1, -1, dtype=np.int64)


def _enumerate_blocks(n, d, total, cache):
    """All (M, n) digit arrays with entries in [0, d) and sum ``total``."""
    if total < 0 or total > (d - 1) * n:
        return np.zeros((0, n), dtype=np.uint8)
    key = (n, total)
    if key in cache:
        return cache[key]
    if n == 1:
        block = np.array([[total]], dtype=np.uint8)
    else:
        low = max(0, total - (d - 1) * (n - 1))
        high = min(d - 1, total)
        parts = []
        for v in range(low, high + 1):
            sub = _enumerate_blocks(n - 1, d, total - v, cache)
            if not len(sub):
                continue
            block = np.empty((len(sub), n), dtype=np.uint8)
            block[:, 0] = v
            block[:, 1:] = sub
            parts.append(block)
        block = (np.concatenate(parts) if parts else
                 np.zeros((0, n), dtype=np.uint8))
    cache[key] = block
    return block


def enumerate_states(site_count, spin, sz_total=None):
    """All product states (optionally in a total-Sz sector), code-sorted.

    Returns (states, codes): ``states`` is an ``(M, site_count)`` uint8 array
    of digits and ``codes`` the ascending int64 base-D codes.
    """
    d, _m, _up, _down = spin_digit_data(spin)
    if sz_total is None:
        total = None
    else:
        doubled = 2.0 * (float(sz_total) + site_count * float(spin))
        if abs(doubled - round(doubled)) > 1e-9:
            raise ValueError(
                "sz_total is incompatible with the cluster: "
                "2*(sz_total + site_count*spin) must be an integer")
        total = int(round(doubled)) // 2
        if abs(2 * total - doubled) > 1e-9 or total < 0 or total > site_count * (d - 1):
            raise ValueError("sz_total lies outside the attainable range for this cluster")
    if total is None:
        states = np.indices((d,) * site_count, dtype=np.uint8).reshape(site_count, -1).T
        # np.indices gives site 0 slowest-varying -> already code-sorted.
        states = np.ascontiguousarray(states)
    else:
        states = _enumerate_blocks(site_count, d, total, {})
    codes = (states.astype(np.int64) @ state_powers(site_count, d)
             if len(states) else np.zeros(0, dtype=np.int64))
    return states, codes


def translation_group(shape, basis_count):
    """Translation group of the periodic supercell.

    Returns (coords, perms): ``coords[g]`` is the integer cell translation of
    group element ``g``; ``perms[g]`` is the site permutation such that the
    translated state is ``state[perms[g]]`` (content at site ``i`` moves to the
    site ``j`` with ``perms[g][j] == i``).
    """
    shape = tuple(int(v) for v in shape)
    if len(shape) != 3 or any(v < 1 for v in shape):
        raise ValueError("supercell shape must be three positive integers")
    cells = np.array(list(np.ndindex(*shape)), dtype=np.int64)
    cell_count = len(cells)
    linear = {tuple(cell): index for index, cell in enumerate(cells)}
    coords, perms = [], []
    site_count = cell_count * basis_count
    for shift in cells:
        image = np.empty(site_count, dtype=np.int64)
        for index, cell in enumerate(cells):
            moved = linear[tuple((cell + shift) % np.array(shape))]
            for b in range(basis_count):
                image[moved * basis_count + b] = index * basis_count + b
        perm = np.empty(site_count, dtype=np.int64)
        perm[image] = np.arange(site_count)
        coords.append(shift)
        perms.append(perm)
    return np.asarray(coords), np.asarray(perms)


def momentum_phases(coords, shape, momentum):
    """Phase exp(i k.t) of each translation; k = 2*pi*momentum_i/L_i."""
    shape = np.asarray(shape, dtype=float)
    n = np.asarray(momentum, dtype=float)
    if n.shape != (3,):
        raise ValueError("momentum must be three integers n_i with k = 2*pi*n_i/L_i")
    if np.max(np.abs(n - np.round(n))) > 1e-9:
        raise ValueError("momentum must be three integers n_i with k = 2*pi*n_i/L_i")
    return np.exp(2j * np.pi * (coords @ (np.round(n) / shape)))


def momentum_sector(states, codes, perms, phases, chunk_size=200000):
    """Symmetrized momentum-sector basis over the given product states.

    Returns a dict with:
    - ``rep_of``: (M,) int32, representative row for each state, or -1 when
      the state's orbit is incompatible with the requested momentum;
    - ``coeff``: (M,) complex128, coefficient ``c_{r,v}`` of the state in its
      representative's symmetrized basis vector (0 for incompatible orbits);
    - ``rep_states``/``rep_codes``: (R, ...) the kept representatives;
    - ``stab_counts``: (R,) stabilizer sizes;
    - ``dimension``: R.
    """
    M, N = states.shape
    group_order = len(perms)
    d = int(states.max()) + 1 if M else 2
    powers = state_powers(N, d)
    permed_powers = powers[perms]  # (G, N)
    rep_code = np.empty(M, dtype=np.int64)
    gstar = np.empty(M, dtype=np.int64)
    for start in range(0, M, chunk_size):
        X = states[start:start + chunk_size].astype(np.int64)
        tcodes = X @ permed_powers.T  # (C, G)
        gstar[start:start + chunk_size] = np.argmin(tcodes, axis=1)
        rep_code[start:start + chunk_size] = tcodes[
            np.arange(len(X)), gstar[start:start + chunk_size]]
    unique_reps, rep_of = np.unique(rep_code, return_inverse=True)
    rep_rows = np.searchsorted(codes, unique_reps)
    rep_states = states[rep_rows].astype(np.int64)
    tcodes = rep_states @ permed_powers.T  # (R, G)
    stab_mask = tcodes == unique_reps[:, None]
    stab_counts = stab_mask.sum(axis=1)
    incompatible = (stab_mask & (np.abs(phases - 1.0) > 1e-9)[None, :]).any(axis=1)
    keep = ~incompatible
    kept_index = np.full(len(unique_reps), -1, dtype=np.int64)
    kept_index[np.flatnonzero(keep)] = np.arange(int(keep.sum()))
    rep_of = kept_index[rep_of].astype(np.int32)
    coeff = np.zeros(M, dtype=np.complex128)
    valid = rep_of >= 0
    index = np.flatnonzero(valid)
    # c_v = sqrt(|stab|/|G|) * exp(-i k.u(v)); with v = T_{-g*} r, u(v) = -g*.
    coeff[index] = (np.sqrt(stab_counts[keep][rep_of[index]] / group_order)
                    * phases[gstar[index]])
    return {"rep_of": rep_of, "coeff": coeff,
            "rep_states": states[rep_rows[keep]],
            "rep_codes": unique_reps[keep],
            "stab_counts": stab_counts[keep],
            "orbits_total": int(len(unique_reps)),
            "dimension": int(keep.sum())}


def trivial_sector(states):
    """No momentum resolution: every state is its own representative."""
    M = len(states)
    return {"rep_of": np.arange(M, dtype=np.int32),
            "coeff": np.ones(M, dtype=np.complex128),
            "rep_states": states, "rep_codes": None,
            "stab_counts": np.ones(M, dtype=np.int64),
            "orbits_total": int(M), "dimension": int(M)}
