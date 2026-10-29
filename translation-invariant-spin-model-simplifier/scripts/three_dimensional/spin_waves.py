"""3D spin-coherent-reference GSWT using the repository's quadratic kernel."""

import numpy as np

from common.model_analysis import _complex_payload
from lswt.python_glswt_solver import (
    _assemble_k_blocks, _bdg_hamiltonian_from_blocks, _dynamical_matrix_from_blocks,
    _positive_branches, _quadratic_terms, _stationarity_diagnostics,
    solve_python_glswt,
)
from three_dimensional.quantum_operators import spin_operators, pair_operator
from three_dimensional.spin_system import minimize_fixed_length, supercell_shape


def spin_wave_spectrum(system, request):
    operators = spin_operators(request["spin"])
    spin = float(request["spin"])
    reference = request.get("reference_spins")
    classical = None
    if reference is None:
        classical = minimize_fixed_length(system, {**request, "spin_length": spin})
        reference = classical["spins"]
    reference = np.asarray(reference, dtype=float).reshape((system.site_count, 3))
    norms = np.linalg.norm(reference, axis=1)
    if not np.all(np.isfinite(reference)) or np.any(norms <= 1e-14):
        raise ValueError("reference_spins must specify a nonzero finite direction at every site")
    rays = []
    for index, direction in enumerate(reference / norms[:, None]):
        ray = np.linalg.eigh(np.einsum("a,aij->ij", direction, operators))[1][:, -1]
        rays.append({"cell": system.cells[index // system.basis_count].tolist(),
                     "site": index % system.basis_count, "vector": _complex_payload(ray)})
    q_path = np.asarray(request["reduced_momenta"], dtype=float)
    if q_path.ndim != 2 or q_path.shape[1] != 3 or not len(q_path) or not np.all(np.isfinite(q_path)):
        raise ValueError("reduced_momenta must be a nonempty list of finite 3D momenta")
    payload = {
        "payload_kind": "python_glswt_local_rays", "local_dimension": operators.shape[1],
        "supercell_shape": list(system.shape), "initial_local_rays": rays,
        "q_path": (q_path * np.array(system.shape)).tolist(),
        "q_path_coordinates": "magnetic_supercell_reciprocal_basis",
        "pair_couplings": [
            {"source": bond["source"], "target": bond["target"], "R": bond["vector"],
             "pair_matrix": _complex_payload(pair_operator(np.array(bond["matrix"]), operators))}
            for bond in system.payload["bonds"]
        ],
    }
    tolerance = float(request.get("stability_tolerance", 1e-7))
    result = solve_python_glswt(payload, stationarity_tolerance=tolerance,
                                eigenvalue_tolerance=tolerance)
    for record, q in zip(result["dispersion"], q_path):
        record["q"] = q.tolist()
    terms = _quadratic_terms(payload)
    stationarity = _stationarity_diagnostics(terms, tolerance=tolerance)
    result["stability"] = {"is_stationary": stationarity["is_stationary"],
                           "linear_term_max_norm": stationarity["linear_term_max_norm"],
                           "minimum_bdg_hessian_eigenvalue": None,
                           "maximum_imaginary_frequency": 0.0,
                           "scope": "requested q points and zero-point quadrature only"}
    stable = bool(stationarity["is_stationary"])

    def spectrum_and_offset(q):
        nonlocal stable
        normal, pair, hole = _assemble_k_blocks(terms, q)
        hessian = _bdg_hamiltonian_from_blocks(normal, pair, hole)
        minimum = float(np.linalg.eigvalsh(hessian)[0])
        eigenvalues = np.linalg.eigvals(_dynamical_matrix_from_blocks(normal, pair, hole))
        imaginary = float(np.max(np.abs(eigenvalues.imag)))
        frequencies = _positive_branches(eigenvalues, len(normal), tolerance=tolerance)
        previous = result["stability"]["minimum_bdg_hessian_eigenvalue"]
        result["stability"]["minimum_bdg_hessian_eigenvalue"] = minimum if previous is None else min(previous, minimum)
        result["stability"]["maximum_imaginary_frequency"] = max(
            result["stability"]["maximum_imaginary_frequency"], imaginary)
        if minimum < -tolerance or imaginary > tolerance or len(frequencies) != len(normal):
            stable = False
            return None
        return 0.5 * (float(np.sum(np.real(frequencies))) - float(np.trace(normal).real))

    for q in payload["q_path"]:
        spectrum_and_offset(q)
    if request.get("zero_point_mesh") is not None:
        mesh = supercell_shape(request["zero_point_mesh"])
        offsets = [spectrum_and_offset((np.array(index) + 0.5) / np.array(mesh))
                   for index in np.ndindex(mesh)]
        result["zero_point"] = {
            "status": "ok" if stable else "inconclusive",
            "energy_per_primitive_cell": float(np.mean(offsets)) / system.cell_count if stable else None,
            "magnetic_bz_mesh": list(mesh), "quadrature": "uniform-midpoint",
            "samples": len(offsets), "converged_in_mesh": False,
            "formula": "mean_q[(sum_n omega_n(q) - Tr A(q))/2] / primitive_cells_in_magnetic_cell",
        }
    result["status"] = "ok" if stable else "inconclusive"
    result["method"] = "spin-coherent-reference-generalized-linear-spin-wave"
    result["momentum_coordinates"] = "primitive-reciprocal-lattice-units"
    result["supercell_shape"] = list(system.shape)
    result["spin"] = spin
    result["limitations"] = [
        "Harmonic approximation about the supplied or numerically optimized reference.",
        "For S > 1/2 all 2S local excited modes are retained (GSWT, not a one-mode LSWT truncation).",
        "Zero-point energy is a finite BZ quadrature, not an exact many-body energy.",
    ]
    if classical is not None:
        result["classical_optimization"] = classical
    return result
