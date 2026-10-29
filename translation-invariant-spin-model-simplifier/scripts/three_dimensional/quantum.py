"""Matrix-free finite-cluster spin diagonalization, using SciPy ARPACK."""

import numpy as np
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigsh

from three_dimensional.quantum_operators import pair_operator, spin_operators


def quantum_low_energy(system, request):
    operators = spin_operators(request["spin"])
    local_dimension = operators.shape[1]
    dimension = local_dimension ** system.site_count
    count = int(request.get("eigenvalues", 2))
    if count < 1 or count >= dimension - 1:
        raise ValueError("ARPACK requires 1 <= eigenvalues < Hilbert dimension - 1")
    if dimension > int(request.get("max_dimension", 262144)):
        raise ValueError("Hilbert dimension exceeds max_dimension; matrix-free storage does not remove exponential scaling")
    grouped = {}
    for source, target, matrix in zip(system.source, system.target, system.matrices):
        source, target = int(source), int(target)
        if source == target:
            raise ValueError("quantum periodic images collapse onto one site; enlarge the supercell")
        if source > target:
            source, target, matrix = target, source, matrix.T
        key = (source, target)
        grouped[key] = grouped.get(key, np.zeros((3, 3))) + matrix
    pair_terms = [(key, pair_operator(matrix, operators)) for key, matrix in grouped.items()]
    real = all(np.max(np.abs(matrix.imag)) < 1e-14 for _key, matrix in pair_terms)
    dtype = np.dtype(float if real else complex)
    if real:
        pair_terms = [(key, matrix.real) for key, matrix in pair_terms]
    ncv = min(dimension, 20)
    estimated_bytes = int((3 * ncv + 2 * count + 12) * dimension * dtype.itemsize)
    if estimated_bytes > float(request.get("max_memory_mb", 512)) * 1024 ** 2:
        raise ValueError("estimated Krylov workspace exceeds max_memory_mb")
    tensor_shape = (local_dimension,) * system.site_count
    products = 0

    def matvec(vector):
        nonlocal products
        products += 1
        tensor = np.asarray(vector).reshape(tensor_shape)
        result = np.zeros(tensor_shape, dtype=np.result_type(dtype, tensor.dtype))
        for (source, target), matrix in pair_terms:
            moved = np.moveaxis(tensor, (source, target), (0, 1))
            applied = (matrix @ moved.reshape((local_dimension ** 2, -1))).reshape(moved.shape)
            result += np.moveaxis(applied, (0, 1), (source, target))
        return result.ravel()

    rng = np.random.default_rng(int(request.get("seed", 0)))
    tolerance = float(request.get("tolerance", 1e-10))
    converged = True
    # A single Krylov start need not span an exactly degenerate eigenspace.
    # Positive projector deflation lifts each locked eigenvector above the full
    # spectrum; an independent next start can then recover its degenerate peers.
    spectral_radius_bound = sum(float(np.max(np.abs(np.linalg.eigvalsh(matrix))))
                                for _key, matrix in pair_terms)
    shift = 2 * spectral_radius_bound + 1.0
    locked = np.empty((dimension, 0), dtype=dtype)
    values = []
    for _index in range(count):
        def deflated_matvec(vector):
            return matvec(vector) + shift * (locked @ (locked.conjugate().T @ vector))

        linear_operator = LinearOperator((dimension, dimension), matvec=deflated_matvec,
                                         rmatvec=deflated_matvec, dtype=dtype)
        initial = rng.normal(size=dimension)
        if not real:
            initial = initial + 1j * rng.normal(size=dimension)
        initial = initial - locked @ (locked.conjugate().T @ initial)
        try:
            _energies, states = eigsh(linear_operator, k=1, which="SA", v0=initial,
                                     ncv=ncv, tol=tolerance,
                                     maxiter=int(request.get("maxiter", 1000)))
        except ArpackNoConvergence:
            converged = False
            break
        vector = states[:, 0]
        vector -= locked @ (locked.conjugate().T @ vector)
        vector /= np.linalg.norm(vector)
        values.append(float(np.vdot(vector, matvec(vector)).real))
        locked = np.column_stack((locked, vector))
    vectors = locked
    order = np.argsort(values)
    values, vectors = np.asarray(values)[order], np.asarray(vectors)[:, order]
    residuals = [float(np.linalg.norm(matvec(vector) - energy * vector))
                 for energy, vector in zip(values, vectors.T)]
    residual_limit = max(1e-8, 10 * tolerance * max(1.0, float(np.max(np.abs(values))) if len(values) else 1.0))
    converged = converged and len(values) == count and all(value <= residual_limit for value in residuals)
    return {
        "status": "ok" if converged else "inconclusive",
        "method": "matrix-free-ARPACK-Lanczos" if real else "matrix-free-ARPACK-complex-Arnoldi",
        "spin": float(request["spin"]), "supercell_shape": list(system.shape),
        "site_count": system.site_count, "hilbert_dimension": dimension,
        "eigenvalues": values.real.tolist(), "residual_norms": residuals,
        "energy_per_site": float(values[0].real) / system.site_count if len(values) else None,
        "converged": bool(converged), "matrix_vector_products": products,
        "degeneracy_handling": "sequential-independent-start-positive-projector-deflation",
        "eigenvector_orthogonality_error": float(np.linalg.norm(vectors.conjugate().T @ vectors - np.eye(len(values)))),
        "dense_hamiltonian_allocated": False, "estimated_workspace_bytes": estimated_bytes,
        "boundary": "periodic", "seed": int(request.get("seed", 0)),
        "limitations": ["Exact finite-cluster Hamiltonian; iterative eigenpairs have the reported residuals.",
                        "No thermodynamic-limit claim, no QMC, and no symmetry-sector compression.",
                        "Hilbert-space vectors still grow exponentially with site count."],
    }
