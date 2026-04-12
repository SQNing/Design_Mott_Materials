#!/usr/bin/env python3
import math

import numpy as np

from lswt.single_q_z_harmonic_adapter import reconstruct_z_from_harmonics


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _deserialize_vector(serialized):
    return np.array([_complex_from_serialized(value) for value in serialized], dtype=complex)


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _deserialize_pair_matrix(serialized):
    return np.array(
        [[_complex_from_serialized(value) for value in row] for row in serialized],
        dtype=complex,
    )


def _pair_matrix_to_tensor(pair_matrix, local_dimension):
    return np.array(pair_matrix, dtype=complex).reshape(
        local_dimension,
        local_dimension,
        local_dimension,
        local_dimension,
    )


def _normalize(vector, *, tolerance=1e-12):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= tolerance:
        raise ValueError("vector norm must be nonzero")
    return vector / norm


def build_local_frame(reference_ray, *, tolerance=1e-12):
    reference_ray = _normalize(reference_ray, tolerance=tolerance)
    local_dimension = int(reference_ray.shape[0])
    columns = [reference_ray]

    for basis_index in range(local_dimension):
        candidate = np.zeros(local_dimension, dtype=complex)
        candidate[basis_index] = 1.0
        for column in columns:
            candidate = candidate - np.vdot(column, candidate) * column
        norm = float(np.linalg.norm(candidate))
        if norm > tolerance:
            columns.append(candidate / norm)
        if len(columns) == local_dimension:
            break

    if len(columns) != local_dimension:
        raise ValueError("failed to build a complete local orthonormal frame")
    return np.column_stack(columns)


def _phase_from_q_and_displacement(q_vector, displacement):
    return 2.0 * math.pi * sum(float(q_vector[axis]) * float(displacement[axis]) for axis in range(3))


def _wrap_phase(phase):
    wrapped = math.fmod(float(phase), 2.0 * math.pi)
    if wrapped < 0.0:
        wrapped += 2.0 * math.pi
    return wrapped


def _phase_grid(size):
    size = int(size)
    if size <= 0:
        raise ValueError("phase_grid_size must be positive")
    return [2.0 * math.pi * float(index) / float(size) for index in range(size)]


def _independent_dft_harmonics(sample_count):
    return [int(round(value)) for value in np.fft.fftfreq(int(sample_count)) * int(sample_count)]


def _deserialize_harmonics(serialized_harmonics):
    harmonics = {}
    for item in serialized_harmonics:
        harmonics[int(item["harmonic"])] = _deserialize_vector(item["vector"])
    if not harmonics:
        raise ValueError("single-q z-harmonic payload requires non-empty z_harmonics")
    return harmonics


def _serialize_harmonics(harmonics):
    return [
        {"harmonic": int(harmonic), "vector": _serialize_vector(harmonics[harmonic])}
        for harmonic in sorted(harmonics)
    ]


def _rotated_pair_tensor(pair_matrix, frame_left, frame_right):
    local_dimension = int(frame_left.shape[0])
    tensor = _pair_matrix_to_tensor(pair_matrix, local_dimension)
    return np.einsum(
        "ABCD,Aa,Bb,Cc,Dd->abcd",
        tensor,
        frame_left.conjugate(),
        frame_left,
        frame_right.conjugate(),
        frame_right,
        optimize=True,
    )


def _fourier_component(samples, phases, harmonic):
    coefficient = np.zeros_like(samples[0], dtype=complex)
    for sample, phase in zip(samples, phases):
        coefficient += np.exp(-1.0j * float(harmonic) * float(phase)) * sample
    return coefficient / float(len(phases))


def _reconstruct_harmonic_samples(harmonics, phases):
    samples = []
    for phase in phases:
        sample = np.zeros_like(next(iter(harmonics.values())), dtype=complex)
        for harmonic, coefficient in harmonics.items():
            sample += np.exp(1.0j * float(harmonic) * float(phase)) * coefficient
        samples.append(sample)
    return samples


def _positive_branches(eigenvalues, mode_count, *, tolerance=1e-8):
    stable_positive = [
        value
        for value in eigenvalues
        if float(np.real(value)) > tolerance and abs(float(np.imag(value))) <= tolerance
    ]
    stable_zero = [
        value
        for value in eigenvalues
        if abs(float(np.real(value))) <= tolerance and abs(float(np.imag(value))) <= tolerance
    ]
    stable_positive = sorted(
        stable_positive,
        key=lambda value: (float(np.real(value)), abs(float(np.imag(value)))),
    )
    stable_zero = sorted(stable_zero, key=lambda value: abs(float(np.imag(value))))
    return (stable_positive + stable_zero)[:mode_count]


def _dispersion_diagnostics(dispersion, *, soft_mode_tolerance=-1e-8):
    if not dispersion:
        return {
            "omega_min": None,
            "omega_max": None,
            "omega_min_q_vector": None,
            "soft_mode_count": 0,
            "soft_mode_q_points": [],
        }

    omega_min = None
    omega_max = None
    omega_min_q = None
    soft_mode_q_points = []
    for point in dispersion:
        bands = [float(value) for value in point.get("bands", [])]
        if not bands:
            continue
        point_min = min(bands)
        point_max = max(bands)
        if omega_min is None or point_min < omega_min:
            omega_min = point_min
            omega_min_q = list(point.get("q", []))
        if omega_max is None or point_max > omega_max:
            omega_max = point_max
        if point_min < soft_mode_tolerance:
            soft_mode_q_points.append(list(point.get("q", [])))
    return {
        "omega_min": omega_min,
        "omega_max": omega_max,
        "omega_min_q_vector": omega_min_q,
        "soft_mode_threshold": float(soft_mode_tolerance),
        "soft_mode_count": int(len(soft_mode_q_points)),
        "soft_mode_q_points": soft_mode_q_points,
    }


def _phase_stationarity_diagnostics(linear_dag, linear_ann, phases, *, tolerance=1e-8):
    entries = []
    max_norm = 0.0
    for phase, dag_sample, ann_sample in zip(phases, linear_dag, linear_ann):
        dag_norm = float(np.linalg.norm(dag_sample))
        ann_norm = float(np.linalg.norm(ann_sample))
        residual_norm = max(dag_norm, ann_norm)
        max_norm = max(max_norm, residual_norm)
        entries.append(
            {
                "phase_over_2pi": float(phase / (2.0 * math.pi)),
                "creation_linear_norm": dag_norm,
                "annihilation_linear_norm": ann_norm,
                "linear_term_norm": residual_norm,
            }
        )
    return {
        "scope": "full-local-tangent",
        "sampling_kind": "phase_grid",
        "phase_grid_size": int(len(phases)),
        "tolerance": float(tolerance),
        "linear_term_max_norm": max_norm,
        "linear_term_mean_norm": float(
            sum(entry["linear_term_norm"] for entry in entries) / len(entries)
        )
        if entries
        else 0.0,
        "is_stationary": bool(max_norm <= tolerance),
        "phases": entries,
    }


def _solve_dispersion_for_reference(active_payload, active_terms, sidebands, *, eigenvalue_tolerance):
    mode_count = int(len(sidebands) * active_terms["excited_dimension"])
    dispersion = []
    max_antihermitian_norm = 0.0
    max_pair_asymmetry_norm = 0.0
    max_complex_eigenvalue_count = 0

    for q_point in active_payload.get("q_path", []):
        normal, pair = _assemble_single_q_k_blocks(active_terms, q_point, sidebands)
        max_antihermitian_norm = max(
            max_antihermitian_norm,
            float(np.linalg.norm(normal - normal.conjugate().T)),
        )
        max_pair_asymmetry_norm = max(
            max_pair_asymmetry_norm,
            float(np.linalg.norm(pair - pair.T)),
        )

        dynamical_matrix = np.block(
            [
                [normal, pair],
                [-pair.conjugate(), -normal.conjugate()],
            ]
        )
        eigenvalues = np.linalg.eigvals(dynamical_matrix)
        max_complex_eigenvalue_count = max(
            max_complex_eigenvalue_count,
            int(sum(abs(float(np.imag(value))) > eigenvalue_tolerance for value in eigenvalues)),
        )
        positive = _positive_branches(eigenvalues, mode_count, tolerance=eigenvalue_tolerance)
        bands = [float(np.real(value)) for value in positive]
        dispersion.append(
            {
                "q": [float(value) for value in q_point],
                "bands": bands,
                "omega": float(min(bands)) if bands else None,
            }
        )

    return {
        "dispersion": dispersion,
        "bogoliubov": {
            "mode_count": int(mode_count),
            "sideband_count": int(len(sidebands)),
            "sideband_cutoff": int(max(abs(sideband) for sideband in sidebands)) if sidebands else 0,
            "max_A_antihermitian_norm": max_antihermitian_norm,
            "max_B_asymmetry_norm": max_pair_asymmetry_norm,
            "max_complex_eigenvalue_count": int(max_complex_eigenvalue_count),
        },
    }


def _truncated_z_harmonic_stationarity_diagnostics(
    linear_dag,
    linear_ann,
    phases,
    *,
    harmonic_cutoff,
    tolerance=1e-8,
):
    harmonic_cutoff = max(0, int(harmonic_cutoff))
    full_harmonics = _independent_dft_harmonics(len(phases))
    retained_harmonics = [harmonic for harmonic in full_harmonics if abs(int(harmonic)) <= harmonic_cutoff]
    discarded_harmonics = [harmonic for harmonic in full_harmonics if abs(int(harmonic)) > harmonic_cutoff]
    entries = []
    max_norm = 0.0

    for harmonic in retained_harmonics:
        dag_component = _fourier_component(linear_dag, phases, harmonic)
        ann_component = _fourier_component(linear_ann, phases, harmonic)
        dag_norm = float(np.linalg.norm(dag_component))
        ann_norm = float(np.linalg.norm(ann_component))
        residual_norm = max(dag_norm, ann_norm)
        max_norm = max(max_norm, residual_norm)
        entries.append(
            {
                "harmonic": int(harmonic),
                "creation_linear_norm": dag_norm,
                "annihilation_linear_norm": ann_norm,
                "linear_term_norm": residual_norm,
            }
        )

    discarded_entries = []
    discarded_max_norm = 0.0
    for harmonic in discarded_harmonics:
        dag_component = _fourier_component(linear_dag, phases, harmonic)
        ann_component = _fourier_component(linear_ann, phases, harmonic)
        dag_norm = float(np.linalg.norm(dag_component))
        ann_norm = float(np.linalg.norm(ann_component))
        residual_norm = max(dag_norm, ann_norm)
        discarded_max_norm = max(discarded_max_norm, residual_norm)
        discarded_entries.append(
            {
                "harmonic": int(harmonic),
                "creation_linear_norm": dag_norm,
                "annihilation_linear_norm": ann_norm,
                "linear_term_norm": residual_norm,
            }
        )

    return {
        "scope": "truncated-z-harmonic-manifold",
        "projection_kind": "phase-fourier-retained-harmonics",
        "harmonic_cutoff": int(harmonic_cutoff),
        "phase_grid_size": int(len(phases)),
        "full_dft_harmonic_count": int(len(full_harmonics)),
        "retained_harmonic_count": int(len(retained_harmonics)),
        "discarded_harmonic_count": int(len(discarded_harmonics)),
        "tolerance": float(tolerance),
        "linear_term_max_norm": max_norm,
        "linear_term_mean_norm": float(
            sum(entry["linear_term_norm"] for entry in entries) / len(entries)
        )
        if entries
        else 0.0,
        "discarded_linear_term_max_norm": discarded_max_norm,
        "discarded_linear_term_mean_norm": float(
            sum(entry["linear_term_norm"] for entry in discarded_entries) / len(discarded_entries)
        )
        if discarded_entries
        else 0.0,
        "is_stationary": bool(max_norm <= tolerance),
        "harmonics": entries,
        "discarded_harmonics": discarded_entries,
    }


def _single_truncated_z_harmonic_local_refinement_step(payload, terms, current_diagnostics, *, tolerance=1e-8):
    retained_entries = list(current_diagnostics.get("harmonics", []))
    retained_harmonics = [int(entry["harmonic"]) for entry in retained_entries]
    if not retained_harmonics:
        return {
            "status": "skipped",
            "reason": "no-retained-harmonics",
        }

    current_norm = float(current_diagnostics.get("linear_term_max_norm", 0.0))
    phases = list(terms["phases"])
    z_harmonics = _deserialize_harmonics(payload.get("z_harmonics", []))
    frame_for_phase = _frame_cache(z_harmonics)
    z_samples = [reconstruct_z_from_harmonics(z_harmonics, phase=phase, normalize=True) for phase in phases]
    gradient_samples = [
        0.5 * (np.array(dag_sample, dtype=complex) + np.conjugate(np.array(ann_sample, dtype=complex)))
        for dag_sample, ann_sample in zip(terms["linear_dag"], terms["linear_ann"])
    ]
    retained_gradient_harmonics = {
        harmonic: _fourier_component(gradient_samples, phases, harmonic)
        for harmonic in retained_harmonics
    }
    retained_gradient_samples = _reconstruct_harmonic_samples(retained_gradient_harmonics, phases)

    best_step = 0.0
    best_payload = dict(payload)
    best_terms = terms
    best_diagnostics = current_diagnostics
    step_candidates = [1.0, -1.0, 0.5, -0.5, 0.25, -0.25, 0.1, -0.1, 0.05, -0.05, 0.02, -0.02]

    for step_size in step_candidates:
        candidate_samples = []
        for phase, z_sample, retained_gradient in zip(phases, z_samples, retained_gradient_samples):
            tangent = frame_for_phase(phase)[:, 1:]
            delta = -float(step_size) * (tangent @ retained_gradient)
            candidate_samples.append(_normalize(z_sample + delta))

        candidate_harmonics = {
            harmonic: _fourier_component(candidate_samples, phases, harmonic)
            for harmonic in retained_harmonics
        }
        candidate_payload = dict(payload)
        candidate_payload["z_harmonics"] = _serialize_harmonics(candidate_harmonics)
        candidate_terms = _phase_resolved_terms(candidate_payload)
        candidate_diagnostics = _truncated_z_harmonic_stationarity_diagnostics(
            candidate_terms["linear_dag"],
            candidate_terms["linear_ann"],
            candidate_terms["phases"],
            harmonic_cutoff=int(payload.get("z_harmonic_cutoff", 0)),
            tolerance=tolerance,
        )
        if float(candidate_diagnostics.get("linear_term_max_norm", np.inf)) < float(
            best_diagnostics.get("linear_term_max_norm", np.inf)
        ):
            best_step = float(step_size)
            best_payload = candidate_payload
            best_terms = candidate_terms
            best_diagnostics = candidate_diagnostics

    improved = float(best_diagnostics.get("linear_term_max_norm", np.inf)) + 1e-18 < current_norm
    return {
        "status": "improved" if improved else "not-improved",
        "selected_step_size": float(best_step),
        "candidate_step_count": int(len(step_candidates)),
        "refined_payload": best_payload,
        "refined_terms": best_terms,
        "refined_diagnostics": best_diagnostics,
    }


def _truncated_z_harmonic_local_refinement(payload, terms, current_diagnostics, *, tolerance=1e-8):
    initial_norm = float(current_diagnostics.get("linear_term_max_norm", 0.0))
    initial_discarded_norm = float(current_diagnostics.get("discarded_linear_term_max_norm", 0.0))
    if initial_norm <= tolerance:
        return {
            "status": "not-needed",
            "selected_step_size": 0.0,
            "iteration_count": 0,
            "step_history": [],
            "initial_retained_linear_term_max_norm": initial_norm,
            "refined_retained_linear_term_max_norm": initial_norm,
            "initial_discarded_linear_term_max_norm": initial_discarded_norm,
            "refined_discarded_linear_term_max_norm": initial_discarded_norm,
            "candidate_step_count": 0,
            "converged": True,
            "_refined_payload": dict(payload),
            "_refined_terms": terms,
            "_refined_truncated_z_harmonic_stationarity": current_diagnostics,
        }

    max_iterations = max(1, int(payload.get("truncated_z_harmonic_refinement_max_iterations", 8)))
    current_payload = dict(payload)
    current_terms = terms
    working_diagnostics = current_diagnostics
    step_history = []
    last_selected_step = 0.0
    last_candidate_count = 0

    for _ in range(max_iterations):
        step_result = _single_truncated_z_harmonic_local_refinement_step(
            current_payload,
            current_terms,
            working_diagnostics,
            tolerance=tolerance,
        )
        last_candidate_count = int(step_result.get("candidate_step_count", 0))
        if step_result.get("status") != "improved":
            break
        last_selected_step = float(step_result.get("selected_step_size", 0.0))
        step_history.append(last_selected_step)
        current_payload = step_result["refined_payload"]
        current_terms = step_result["refined_terms"]
        working_diagnostics = step_result["refined_diagnostics"]
        if float(working_diagnostics.get("linear_term_max_norm", np.inf)) <= tolerance:
            break

    iteration_count = int(len(step_history))
    improved = float(working_diagnostics.get("linear_term_max_norm", np.inf)) + 1e-18 < initial_norm
    return {
        "status": "improved" if improved else "not-improved",
        "selected_step_size": float(last_selected_step),
        "iteration_count": iteration_count,
        "step_history": [float(value) for value in step_history],
        "initial_retained_linear_term_max_norm": initial_norm,
        "refined_retained_linear_term_max_norm": float(working_diagnostics.get("linear_term_max_norm", initial_norm)),
        "initial_discarded_linear_term_max_norm": initial_discarded_norm,
        "refined_discarded_linear_term_max_norm": float(
            working_diagnostics.get("discarded_linear_term_max_norm", initial_discarded_norm)
        ),
        "candidate_step_count": int(last_candidate_count),
        "converged": bool(float(working_diagnostics.get("linear_term_max_norm", np.inf)) <= tolerance),
        "_refined_payload": current_payload,
        "_refined_terms": current_terms,
        "_refined_truncated_z_harmonic_stationarity": working_diagnostics,
    }


def _frame_cache(z_harmonics):
    cache = {}

    def get_frame(phase):
        wrapped = _wrap_phase(phase)
        key = round(wrapped, 12)
        if key not in cache:
            ray = reconstruct_z_from_harmonics(z_harmonics, phase=wrapped, normalize=True)
            cache[key] = build_local_frame(ray)
        return cache[key]

    return get_frame


def _phase_resolved_terms(payload):
    local_dimension = int(payload["local_dimension"])
    excited_dimension = local_dimension - 1
    if excited_dimension <= 0:
        raise ValueError("single-q GLSWT requires local_dimension >= 2")

    phases = _phase_grid(int(payload.get("phase_grid_size", 64)))
    q_vector = [float(value) for value in payload.get("q_vector", [0.0, 0.0, 0.0])]
    z_harmonics = _deserialize_harmonics(payload.get("z_harmonics", []))
    pair_couplings = list(payload.get("pair_couplings", []))
    identity = np.eye(excited_dimension, dtype=complex)
    get_frame = _frame_cache(z_harmonics)

    linear_dag = [np.zeros(excited_dimension, dtype=complex) for _ in phases]
    linear_ann = [np.zeros(excited_dimension, dtype=complex) for _ in phases]
    onsite = [np.zeros((excited_dimension, excited_dimension), dtype=complex) for _ in phases]
    hop_plus = {}
    hop_minus = {}
    pair_plus = {}

    for coupling in pair_couplings:
        displacement = tuple(int(value) for value in coupling.get("R", [0, 0, 0]))
        pair_matrix = _deserialize_pair_matrix(coupling["pair_matrix"])
        delta_phase = _phase_from_q_and_displacement(q_vector, displacement)
        hop_plus[displacement] = [np.zeros((excited_dimension, excited_dimension), dtype=complex) for _ in phases]
        hop_minus[displacement] = [np.zeros((excited_dimension, excited_dimension), dtype=complex) for _ in phases]
        pair_plus[displacement] = [np.zeros((excited_dimension, excited_dimension), dtype=complex) for _ in phases]

        for index, phase in enumerate(phases):
            source_frame = get_frame(phase)
            target_frame = get_frame(phase + delta_phase)
            previous_frame = get_frame(phase - delta_phase)

            rotated_fwd = _rotated_pair_tensor(pair_matrix, source_frame, target_frame)
            rotated_prev = _rotated_pair_tensor(pair_matrix, previous_frame, source_frame)

            e00_fwd = complex(rotated_fwd[0, 0, 0, 0])
            e00_prev = complex(rotated_prev[0, 0, 0, 0])

            linear_dag[index] += rotated_fwd[1:, 0, 0, 0] + rotated_prev[0, 0, 1:, 0]
            linear_ann[index] += rotated_fwd[0, 1:, 0, 0] + rotated_prev[0, 0, 0, 1:]
            onsite[index] += rotated_fwd[1:, 1:, 0, 0] - e00_fwd * identity
            onsite[index] += rotated_prev[0, 0, 1:, 1:] - e00_prev * identity
            hop_plus[displacement][index] += rotated_fwd[1:, 0, 0, 1:]
            hop_minus[displacement][index] += np.transpose(rotated_prev[0, 1:, 1:, 0])
            pair_plus[displacement][index] += rotated_fwd[1:, 0, 1:, 0]

    return {
        "excited_dimension": int(excited_dimension),
        "phases": phases,
        "q_vector": q_vector,
        "linear_dag": linear_dag,
        "linear_ann": linear_ann,
        "onsite": onsite,
        "hop_plus": hop_plus,
        "hop_minus": hop_minus,
        "pair_plus": pair_plus,
    }


def _assemble_single_q_k_blocks(terms, q_point, sidebands):
    q_point = [float(value) for value in q_point]
    q_vector = [float(value) for value in terms["q_vector"]]
    phases = terms["phases"]
    excited_dimension = int(terms["excited_dimension"])
    mode_count = int(len(sidebands) * excited_dimension)
    normal = np.zeros((mode_count, mode_count), dtype=complex)
    pair = np.zeros((mode_count, mode_count), dtype=complex)

    onsite_cache = {}
    hop_plus_cache = {}
    hop_minus_cache = {}
    pair_cache = {}

    for row_band, m in enumerate(sidebands):
        row = slice(row_band * excited_dimension, (row_band + 1) * excited_dimension)
        for col_band, n in enumerate(sidebands):
            col = slice(col_band * excited_dimension, (col_band + 1) * excited_dimension)

            normal_harmonic = int(m - n)
            if normal_harmonic not in onsite_cache:
                onsite_cache[normal_harmonic] = _fourier_component(terms["onsite"], phases, normal_harmonic)
            normal_block = np.array(onsite_cache[normal_harmonic], dtype=complex)

            for displacement, samples in terms["hop_plus"].items():
                cache_key = (displacement, normal_harmonic)
                if cache_key not in hop_plus_cache:
                    hop_plus_cache[cache_key] = _fourier_component(samples, phases, normal_harmonic)
                phase_factor = np.exp(
                    2.0j
                    * math.pi
                    * sum((float(q_point[axis]) + float(n) * float(q_vector[axis])) * float(displacement[axis]) for axis in range(3))
                )
                normal_block += phase_factor * hop_plus_cache[cache_key]

            for displacement, samples in terms["hop_minus"].items():
                cache_key = (displacement, normal_harmonic)
                if cache_key not in hop_minus_cache:
                    hop_minus_cache[cache_key] = _fourier_component(samples, phases, normal_harmonic)
                phase_factor = np.exp(
                    -2.0j
                    * math.pi
                    * sum((float(q_point[axis]) + float(n) * float(q_vector[axis])) * float(displacement[axis]) for axis in range(3))
                )
                normal_block += phase_factor * hop_minus_cache[cache_key]

            pair_harmonic = int(m + n)
            pair_block = np.zeros((excited_dimension, excited_dimension), dtype=complex)
            for displacement, samples in terms["pair_plus"].items():
                cache_key = (displacement, pair_harmonic)
                if cache_key not in pair_cache:
                    pair_cache[cache_key] = _fourier_component(samples, phases, pair_harmonic)
                phase_factor = np.exp(
                    2.0j
                    * math.pi
                    * sum((float(q_point[axis]) - float(n) * float(q_vector[axis])) * float(displacement[axis]) for axis in range(3))
                )
                pair_block += phase_factor * pair_cache[cache_key]

            normal[row, col] = normal_block
            pair[row, col] = pair_block

    normal = 0.5 * (normal + normal.conjugate().T)
    pair = 0.5 * (pair + pair.T)
    return normal, pair


def solve_single_q_z_harmonic_glswt(payload, *, stationarity_tolerance=1e-8, eigenvalue_tolerance=1e-8):
    terms = _phase_resolved_terms(payload)
    input_stationarity = _phase_stationarity_diagnostics(
        terms["linear_dag"],
        terms["linear_ann"],
        terms["phases"],
        tolerance=stationarity_tolerance,
    )
    sideband_cutoff = int(payload.get("sideband_cutoff", 0))
    q_vector = [float(value) for value in payload.get("q_vector", [0.0, 0.0, 0.0])]
    if max(abs(value) for value in q_vector) <= 1e-12:
        sidebands = [0]
    else:
        sidebands = list(range(-sideband_cutoff, sideband_cutoff + 1))

    input_truncated_z_harmonic_stationarity = _truncated_z_harmonic_stationarity_diagnostics(
        terms["linear_dag"],
        terms["linear_ann"],
        terms["phases"],
        harmonic_cutoff=int(payload.get("z_harmonic_cutoff", 0)),
        tolerance=stationarity_tolerance,
    )
    truncated_z_harmonic_local_refinement = _truncated_z_harmonic_local_refinement(
        payload,
        terms,
        input_truncated_z_harmonic_stationarity,
        tolerance=stationarity_tolerance,
    )
    refined_payload = truncated_z_harmonic_local_refinement.pop("_refined_payload")
    refined_terms = truncated_z_harmonic_local_refinement.pop("_refined_terms")
    refined_truncated_z_harmonic_stationarity = truncated_z_harmonic_local_refinement.pop(
        "_refined_truncated_z_harmonic_stationarity"
    )

    requested_reference_mode = str(payload.get("z_harmonic_reference_mode", "input"))
    resolved_reference_mode = "input"
    active_payload = payload
    active_terms = terms
    active_truncated_z_harmonic_stationarity = input_truncated_z_harmonic_stationarity
    if (
        requested_reference_mode == "refined-retained-local"
        and truncated_z_harmonic_local_refinement.get("status") == "improved"
    ):
        resolved_reference_mode = "refined-retained-local"
        active_payload = refined_payload
        active_terms = refined_terms
        active_truncated_z_harmonic_stationarity = refined_truncated_z_harmonic_stationarity

    reference_dispersions = {
        "input": _solve_dispersion_for_reference(
            payload,
            terms,
            sidebands,
            eigenvalue_tolerance=eigenvalue_tolerance,
        )
    }
    if resolved_reference_mode == "refined-retained-local":
        reference_dispersions["refined-retained-local"] = _solve_dispersion_for_reference(
            refined_payload,
            refined_terms,
            sidebands,
            eigenvalue_tolerance=eigenvalue_tolerance,
        )

    active_dispersion_result = reference_dispersions[resolved_reference_mode]
    dispersion = active_dispersion_result["dispersion"]

    stationarity = _phase_stationarity_diagnostics(
        active_terms["linear_dag"],
        active_terms["linear_ann"],
        active_terms["phases"],
        tolerance=stationarity_tolerance,
    )
    reference_selection = {
        "requested_mode": requested_reference_mode,
        "resolved_mode": resolved_reference_mode,
        "dispersion_recomputed": bool(resolved_reference_mode != "input"),
        "refinement_status": str(truncated_z_harmonic_local_refinement.get("status", "n/a")),
        "input_retained_linear_term_max_norm": float(
            input_truncated_z_harmonic_stationarity.get("linear_term_max_norm", 0.0)
        ),
        "selected_retained_linear_term_max_norm": float(
            active_truncated_z_harmonic_stationarity.get("linear_term_max_norm", 0.0)
        ),
        "input_full_tangent_linear_term_max_norm": float(input_stationarity.get("linear_term_max_norm", 0.0)),
        "selected_full_tangent_linear_term_max_norm": float(stationarity.get("linear_term_max_norm", 0.0)),
    }
    return {
        "status": "ok",
        "backend": {"name": "python-glswt", "implementation": "single-q-z-harmonic-sideband"},
        "payload_kind": str(payload.get("payload_kind", "python_glswt_single_q_z_harmonic")),
        "dispersion": dispersion,
        "reference_dispersions": {
            mode: result["dispersion"] for mode, result in reference_dispersions.items()
        },
        "path": dict(payload.get("path", {})),
        "classical_reference": dict(payload.get("classical_reference", {})),
        "ordering": dict(payload.get("ordering", {})),
        "z_harmonic_reference_mode": requested_reference_mode,
        "diagnostics": {
            "reference_selection": reference_selection,
            "restricted_ansatz_stationarity": dict(payload.get("restricted_ansatz_stationarity", {})),
            "truncated_z_harmonic_stationarity": active_truncated_z_harmonic_stationarity,
            "truncated_z_harmonic_local_refinement": truncated_z_harmonic_local_refinement,
            "stationarity": stationarity,
            "dispersion": _dispersion_diagnostics(dispersion),
            "harmonic": dict(payload.get("harmonic_diagnostics", {})),
            "bogoliubov": active_dispersion_result["bogoliubov"],
        },
    }
