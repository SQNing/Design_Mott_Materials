#!/usr/bin/env python3
import math
import numpy as np


def _complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _deserialize_vector(serialized):
    return np.array([_complex_from_serialized(value) for value in serialized], dtype=complex)


def _deserialize_matrix(serialized):
    return np.array(
        [[_complex_from_serialized(value) for value in row] for row in serialized],
        dtype=complex,
    )


def _serialize_vector(vector):
    return [_serialize_complex(value) for value in vector]


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


def _normalize(vector, *, tolerance=1e-12):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= tolerance:
        raise ValueError("vector norm must be nonzero")
    return vector / norm


def _single_q_unitary(generator_matrix, phase):
    generator_matrix = np.array(generator_matrix, dtype=complex)
    if float(np.linalg.norm(generator_matrix)) <= 1e-14:
        return np.eye(generator_matrix.shape[0], dtype=complex)
    eigenvalues, eigenvectors = np.linalg.eigh(generator_matrix)
    return eigenvectors @ np.diag(np.exp(1.0j * float(phase) * eigenvalues)) @ eigenvectors.conjugate().T


def _phase_grid(size):
    size = int(size)
    if size <= 0:
        raise ValueError("phase_grid_size must be positive")
    return [2.0 * math.pi * float(index) / float(size) for index in range(size)]


def _harmonic_items(z_harmonics):
    if isinstance(z_harmonics, dict):
        return [(int(harmonic), np.array(vector, dtype=complex)) for harmonic, vector in z_harmonics.items()]

    items = []
    for item in z_harmonics:
        items.append((int(item["harmonic"]), _deserialize_vector(item["vector"])))
    return items


def reconstruct_z_from_harmonics(z_harmonics, *, phase, normalize=False, tolerance=1e-12):
    items = _harmonic_items(z_harmonics)
    if not items:
        raise ValueError("z_harmonics must not be empty")

    local_dimension = int(items[0][1].shape[0])
    reconstructed = np.zeros(local_dimension, dtype=complex)
    for harmonic, vector in items:
        reconstructed += np.exp(1.0j * float(harmonic) * float(phase)) * vector

    if normalize:
        return _normalize(reconstructed, tolerance=tolerance)
    return reconstructed


def _extract_truncated_harmonics(z_samples, phases, cutoff):
    cutoff = int(cutoff)
    sample_count = len(phases)
    local_dimension = int(z_samples[0].shape[0])
    harmonics = {}
    for harmonic in range(-cutoff, cutoff + 1):
        coefficient = np.zeros(local_dimension, dtype=complex)
        for sample, phase in zip(z_samples, phases):
            coefficient += np.exp(-1.0j * float(harmonic) * float(phase)) * sample
        harmonics[harmonic] = coefficient / float(sample_count)
    return harmonics


def build_single_q_z_harmonic_payload(
    model,
    *,
    classical_state,
    z_harmonic_cutoff=1,
    phase_grid_size=64,
    sideband_cutoff=2,
):
    if not isinstance(classical_state, dict):
        raise ValueError("classical_state must be a dictionary")

    ordering = classical_state.get("ordering", {})
    ansatz = classical_state.get("ansatz", ordering.get("ansatz"))
    if ansatz != "single-q-unitary-ray":
        raise ValueError("single-q z-harmonic payload requires ansatz='single-q-unitary-ray'")

    q_vector = classical_state.get("q_vector", ordering.get("q_vector"))
    if q_vector is None:
        raise ValueError("single-q z-harmonic payload requires q_vector")

    reference_ray = classical_state.get("reference_ray")
    generator_matrix = classical_state.get("generator_matrix")
    if reference_ray is None or generator_matrix is None:
        raise ValueError("single-q z-harmonic payload requires reference_ray and generator_matrix")

    reference_ray = _normalize(_deserialize_vector(reference_ray))
    generator_matrix = _deserialize_matrix(generator_matrix)
    phases = _phase_grid(phase_grid_size)
    z_samples = [
        _normalize(_single_q_unitary(generator_matrix, phase) @ reference_ray)
        for phase in phases
    ]

    z_harmonics = _extract_truncated_harmonics(z_samples, phases, z_harmonic_cutoff)
    reconstructed = [
        reconstruct_z_from_harmonics(z_harmonics, phase=phase)
        for phase in phases
    ]

    reconstruction_errors = [
        float(np.linalg.norm(reconstructed_sample - exact_sample))
        for reconstructed_sample, exact_sample in zip(reconstructed, z_samples)
    ]
    norm_errors = [
        abs(float(np.linalg.norm(reconstructed_sample)) - 1.0)
        for reconstructed_sample in reconstructed
    ]

    return {
        "payload_version": 1,
        "backend": "python",
        "mode": "GLSWT",
        "payload_kind": "python_glswt_single_q_z_harmonic",
        "local_dimension": int(model.get("local_dimension", reference_ray.shape[0])),
        "q_vector": [float(value) for value in q_vector],
        "z_harmonic_cutoff": int(z_harmonic_cutoff),
        "z_harmonics": [
            {
                "harmonic": int(harmonic),
                "vector": _serialize_vector(z_harmonics[harmonic]),
            }
            for harmonic in range(-int(z_harmonic_cutoff), int(z_harmonic_cutoff) + 1)
        ],
        "phase_grid_size": int(phase_grid_size),
        "sideband_cutoff": int(sideband_cutoff),
        "source_classical_ansatz": str(ansatz),
        "source_reference_ray": _serialize_vector(reference_ray),
        "source_generator_matrix": _serialize_matrix(generator_matrix),
        "restricted_ansatz_stationarity": dict(classical_state.get("ansatz_stationarity", {})),
        "ordering": {"ansatz": str(ansatz), "q_vector": [float(value) for value in q_vector]},
        "harmonic_diagnostics": {
            "max_reconstruction_error": max(reconstruction_errors) if reconstruction_errors else 0.0,
            "mean_reconstruction_error": float(np.mean(reconstruction_errors)) if reconstruction_errors else 0.0,
            "max_norm_error": max(norm_errors) if norm_errors else 0.0,
            "mean_norm_error": float(np.mean(norm_errors)) if norm_errors else 0.0,
            "phase_grid_size": int(phase_grid_size),
        },
    }
