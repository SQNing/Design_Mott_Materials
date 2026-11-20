"""Routing-time Hilbert-space estimates and quantum-method selection gates.

The gates here decide, before any worker launches, whether a quantum task can
run on a connected backend. They never guess: an oversized exact-
diagonalization request stops with an explicit blocker naming the viable
alternatives, and declared-but-not-connected backends (DMRG, VMC) fail closed
with ``backend-not-connected``.
"""

from __future__ import annotations

from collections.abc import Mapping

# Default ARPACK dimension cap, mirroring quantum/ed_solver.py.
DEFAULT_ED_MAX_DIMENSION = 262144
# Absolute routing cap: even an explicit user override cannot route an ED job
# above this size; matrix-free storage does not remove exponential scaling.
HARD_ED_MAX_DIMENSION = 4194304

METHOD_ALIASES = {
    "ed": "ed",
    "exact_diagonalization": "ed",
    "lanczos": "ed",
    "arnoldi": "ed",
    "dmrg": "dmrg",
    "itensor": "dmrg",
    "mps": "dmrg",
    "vmc": "vmc",
    "netket": "vmc",
    "qvmc": "vmc",
}

NOT_CONNECTED_BACKENDS = {
    "dmrg": "quantum-dmrg-itensor",
    "vmc": "quantum-vmc-netket",
}


def _spin_local_dimension(model, settings=None):
    candidates = []
    quantum = model.get("quantum", {}) if isinstance(model, Mapping) else {}
    candidates.append(quantum.get("spin"))
    if isinstance(model, Mapping):
        candidates.append(model.get("spin"))
    if isinstance(settings, Mapping):
        candidates.append(settings.get("spin"))
        candidates.append(settings.get("spin_length"))
    for spin in candidates:
        if spin is None:
            continue
        try:
            dimension = int(round(2 * float(spin) + 1))
        except (TypeError, ValueError):
            continue
        if dimension >= 2:
            return dimension
    return None


def local_quantum_dimension(model, settings=None):
    """Uniform local Hilbert dimension, or None when it cannot be inferred.

    The classical-space ``dimension`` of a unit-vector sphere is a manifold
    dimension, not a quantum local dimension; spin routes must supply ``spin``
    (or ``spin_length``) through the model, quantum block, or settings.
    """
    explicit = model.get("local_dim") if isinstance(model, Mapping) else None
    if explicit is not None:
        try:
            dimension = int(explicit)
        except (TypeError, ValueError):
            return None
        return dimension if dimension >= 2 else None
    spaces = (model.get("local_hilbert", {}) or {}).get("classical_spaces", {})
    kinds = {str(record.get("kind")) for record in spaces.values()
             if isinstance(record, Mapping)}
    if kinds and kinds.issubset({"complex_projective_space"}):
        dimensions = set()
        for record in spaces.values():
            if isinstance(record, Mapping) and record.get("dimension") is not None:
                try:
                    dimensions.add(int(record["dimension"]))
                except (TypeError, ValueError):
                    return None
        if len(dimensions) == 1:
            dimension = dimensions.pop()
            return dimension if dimension >= 2 else None
        return None
    return _spin_local_dimension(model, settings)


def cluster_site_count(model, supercell_shape=None):
    """Total finite-cluster sites: basis sites times the supercell product."""
    shape = supercell_shape
    if shape is None and isinstance(model, Mapping) and isinstance(model.get("cluster_size"), int):
        # Legacy payloads: cluster_size already counts total sites.
        return int(model["cluster_size"])
    if shape is None:
        shape = (model.get("supercell", {}) or {}).get("shape")
    if isinstance(shape, int):
        cells = shape
    elif isinstance(shape, (list, tuple)) and shape:
        cells = 1
        for entry in shape:
            cells *= int(entry)
    else:
        return None
    basis = len((model.get("lattice_structure", {}) or {}).get("basis_sites", []))
    return cells * max(basis, 1)


def estimate_hilbert_dimension(model, supercell_shape=None, settings=None):
    local = local_quantum_dimension(model, settings)
    sites = cluster_site_count(model, supercell_shape)
    if local is None or sites is None or sites <= 0:
        return None
    if sites > 1024:  # avoid absurd integers; far beyond any ED/DMRG route
        return float("inf")
    return float(local) ** sites


def quantum_method_stage_decision(model, settings=None, method=None,
                                  ed_max_dimension=DEFAULT_ED_MAX_DIMENSION):
    """Decide the quantum solver route for a complete model.

    Returns one of:
    - {"status": "ok", "method": "ed", "hilbert_dimension": int, ...}
    - {"status": "needs_input", "question": {...}} when the method or the
      cluster definition is missing and no default applies;
    - {"status": "unsupported", "blocker": "backend-not-connected: ..."} for
      declared backends and oversized ED requests.
    """
    settings = settings if isinstance(settings, Mapping) else {}
    requested = method or settings.get("quantum_method") or settings.get("method") or "ed"
    canonical = METHOD_ALIASES.get(str(requested).strip().lower())
    if canonical is None:
        return {"status": "needs_input",
                "question": {"id": "quantum_method",
                             "prompt": ("Unknown quantum method %r. Choose one of "
                                        "ed (connected), dmrg or vmc (declared, not connected)."
                                        % requested)},
                "recommended": "ed", "options": ["ed", "dmrg", "vmc"]}
    if canonical in NOT_CONNECTED_BACKENDS:
        return {"status": "unsupported",
                "blocker": "backend-not-connected: " + NOT_CONNECTED_BACKENDS[canonical],
                "declared_backend": NOT_CONNECTED_BACKENDS[canonical],
                "alternatives": ["ed with a smaller cluster", "classical/LSWT routes already connected"]}
    shape = settings.get("supercell_shape")
    dimension = estimate_hilbert_dimension(model, shape, settings)
    if dimension is None:
        return {"status": "needs_input",
                "question": {"id": "quantum_cluster",
                             "prompt": ("Cannot infer the finite cluster (supercell shape and basis) or the "
                                        "uniform local Hilbert dimension. Supply supercell_shape and spin/local_dim.")}}
    limit = int(settings.get("max_dimension", ed_max_dimension))
    limit = min(limit, HARD_ED_MAX_DIMENSION)
    if dimension > limit:
        return {"status": "unsupported",
                "blocker": "quantum-ed-dimension-exceeded",
                "hilbert_dimension": dimension, "ed_max_dimension": limit,
                "alternatives": [
                    "reduce supercell_shape so local_dim**sites <= %d" % limit,
                    "dmrg (declared-not-connected: quantum-dmrg-itensor)",
                    "vmc (declared-not-connected: quantum-vmc-netket)"]}
    return {"status": "ok", "method": "ed", "hilbert_dimension": dimension,
            "ed_max_dimension": limit,
            "limitations": ["Exact finite-cluster diagonalization only; no thermodynamic-limit claim."]}
