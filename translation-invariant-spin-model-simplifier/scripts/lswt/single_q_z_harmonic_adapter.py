#!/usr/bin/env python3
import math
import numpy as np

from common.classical_contract_resolution import get_standardized_classical_state


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


def _harmonic_items(z_harmonics, *, site=0):
    if isinstance(z_harmonics, dict):
        if z_harmonics:
            first_value = next(iter(z_harmonics.values()))
            if isinstance(first_value, dict):
                z_harmonics = z_harmonics.get(int(site), {})
        return [(int(harmonic), np.array(vector, dtype=complex)) for harmonic, vector in z_harmonics.items()]

    items = []
    for item in z_harmonics:
        item_site = int(item.get("site", 0))
        if int(item_site) != int(site):
            continue
        items.append((int(item["harmonic"]), _deserialize_vector(item["vector"])))
    return items


def reconstruct_z_from_harmonics(z_harmonics, *, phase, site=0, normalize=False, tolerance=1e-12):
    items = _harmonic_items(z_harmonics, site=site)
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


def _canonical_classical_state(classical_state):
    standardized_state = get_standardized_classical_state(classical_state)
    if isinstance(standardized_state, dict):
        return standardized_state
    if isinstance(classical_state, dict):
        nested_state = classical_state.get("classical_state")
        if isinstance(nested_state, dict):
            return nested_state
    return classical_state


def _infer_site_count(model, classical_state):
    site_count = 1
    positions = list(model.get("positions", []))
    if positions:
        site_count = max(site_count, len(positions))

    canonical_state = _canonical_classical_state(classical_state)
    local_rays = list((canonical_state or {}).get("local_rays", []))
    if local_rays:
        site_count = max(site_count, max(int(item.get("site", 0)) for item in local_rays) + 1)
    return int(site_count)


def _resolve_site_ansatz(classical_state, site_count):
    canonical_state = _canonical_classical_state(classical_state)
    site_ansatz = classical_state.get("site_ansatz")
    if not (isinstance(site_ansatz, list) and site_ansatz):
        site_ansatz = canonical_state.get("site_ansatz")
    if isinstance(site_ansatz, list) and site_ansatz:
        resolved = {}
        for item in site_ansatz:
            site = int(item.get("site", 0))
            if site in resolved:
                raise ValueError(f"duplicate site_ansatz entry for site {site}")
            reference_ray = item.get("reference_ray")
            generator_matrix = item.get("generator_matrix")
            if reference_ray is None or generator_matrix is None:
                raise ValueError("site_ansatz entries require reference_ray and generator_matrix")
            resolved[site] = {
                "reference_ray": _normalize(_deserialize_vector(reference_ray)),
                "generator_matrix": _deserialize_matrix(generator_matrix),
            }
        missing = [site for site in range(int(site_count)) if site not in resolved]
        if missing:
            raise ValueError(f"site_ansatz missing entries for sites {missing}")
        return resolved, "explicit-site-ansatz"

    reference_ray = classical_state.get("reference_ray")
    generator_matrix = classical_state.get("generator_matrix")
    if reference_ray is None or generator_matrix is None:
        reference_ray = canonical_state.get("reference_ray")
        generator_matrix = canonical_state.get("generator_matrix")
    if reference_ray is None or generator_matrix is None:
        raise ValueError("single-q z-harmonic payload requires reference_ray and generator_matrix")

    shared_reference = _normalize(_deserialize_vector(reference_ray))
    shared_generator = _deserialize_matrix(generator_matrix)
    return (
        {
            site: {
                "reference_ray": np.array(shared_reference, dtype=complex),
                "generator_matrix": np.array(shared_generator, dtype=complex),
            }
            for site in range(int(site_count))
        },
        "shared-site-ansatz",
    )


def _site_ansatz_summary(site, reference_ray, generator_matrix, *, zero_tolerance=1e-14):
    reference_ray = np.array(reference_ray, dtype=complex)
    generator_matrix = np.array(generator_matrix, dtype=complex)
    generator_frobenius_norm = float(np.linalg.norm(generator_matrix))
    generator_hermitian_residual = float(
        np.linalg.norm(generator_matrix - generator_matrix.conjugate().T)
    )
    return {
        "site": int(site),
        "reference_ray": _serialize_vector(reference_ray),
        "reference_ray_norm": float(np.linalg.norm(reference_ray)),
        "generator_matrix": _serialize_matrix(generator_matrix),
        "generator_frobenius_norm": generator_frobenius_norm,
        "generator_is_zero": bool(generator_frobenius_norm <= float(zero_tolerance)),
        "generator_hermitian_residual_norm": generator_hermitian_residual,
    }


def _harmonic_weight_summary(harmonics):
    weights = {
        int(harmonic): float(np.linalg.norm(vector) ** 2)
        for harmonic, vector in harmonics.items()
    }
    dominant_harmonic = max(
        weights,
        key=lambda harmonic: (weights[harmonic], -abs(int(harmonic)), -int(harmonic)),
    )
    zero_harmonic_weight = float(weights.get(0, 0.0))
    total_weight = float(sum(weights.values()))
    return {
        "retained_harmonic_count": int(len(weights)),
        "retained_harmonic_weight": total_weight,
        "zero_harmonic_weight": zero_harmonic_weight,
        "nonzero_harmonic_weight": float(total_weight - zero_harmonic_weight),
        "dominant_harmonic": int(dominant_harmonic),
        "dominant_harmonic_weight": float(weights[dominant_harmonic]),
    }


def _serialize_site_harmonics(site_harmonics, cutoff):
    serialized = []
    for site in sorted(site_harmonics):
        harmonics = dict(site_harmonics[site])
        for harmonic in range(-int(cutoff), int(cutoff) + 1):
            serialized.append(
                {
                    "site": int(site),
                    "harmonic": int(harmonic),
                    "vector": _serialize_vector(harmonics[harmonic]),
                }
            )
    return serialized


def _serialize_source_site_ansatz(site_ansatz):
    serialized = []
    for site in sorted(site_ansatz):
        item = site_ansatz[site]
        serialized.append(
            _site_ansatz_summary(
                site,
                np.array(item["reference_ray"], dtype=complex),
                np.array(item["generator_matrix"], dtype=complex),
            )
        )
    return serialized


def _top_level_source_reference_metadata(site_reference_mode):
    if str(site_reference_mode) == "shared-site-ansatz":
        return {
            "source_reference_scope": "shared-all-sites",
            "source_reference_site": 0,
        }
    return {
        "source_reference_scope": "representative-site-only",
        "source_reference_site": 0,
    }


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

    canonical_state = _canonical_classical_state(classical_state)
    ordering = classical_state.get("ordering", canonical_state.get("ordering", {}))
    ansatz = classical_state.get("ansatz", canonical_state.get("ansatz", ordering.get("ansatz")))
    if ansatz != "single-q-unitary-ray":
        raise ValueError("single-q z-harmonic payload requires ansatz='single-q-unitary-ray'")

    q_vector = classical_state.get("q_vector", canonical_state.get("q_vector", ordering.get("q_vector")))
    if q_vector is None:
        raise ValueError("single-q z-harmonic payload requires q_vector")

    site_count = _infer_site_count(model, classical_state)
    site_ansatz, site_reference_mode = _resolve_site_ansatz(classical_state, site_count)
    phases = _phase_grid(phase_grid_size)
    site_harmonics = {}
    site_diagnostics = []
    first_site_reference = None
    first_site_generator = None

    for site in range(int(site_count)):
        reference_ray = np.array(site_ansatz[site]["reference_ray"], dtype=complex)
        generator_matrix = np.array(site_ansatz[site]["generator_matrix"], dtype=complex)
        if first_site_reference is None:
            first_site_reference = np.array(reference_ray, dtype=complex)
            first_site_generator = np.array(generator_matrix, dtype=complex)

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
        site_harmonics[int(site)] = z_harmonics
        site_diagnostics.append(
            {
                "site": int(site),
                "max_reconstruction_error": max(reconstruction_errors) if reconstruction_errors else 0.0,
                "mean_reconstruction_error": float(np.mean(reconstruction_errors)) if reconstruction_errors else 0.0,
                "max_norm_error": max(norm_errors) if norm_errors else 0.0,
                "mean_norm_error": float(np.mean(norm_errors)) if norm_errors else 0.0,
                **_harmonic_weight_summary(z_harmonics),
            }
        )

    return {
        "payload_version": 1,
        "backend": "python",
        "mode": "GLSWT",
        "payload_kind": "python_glswt_single_q_z_harmonic",
        "local_dimension": int(model.get("local_dimension", first_site_reference.shape[0])),
        "site_count": int(site_count),
        "q_vector": [float(value) for value in q_vector],
        "z_harmonic_cutoff": int(z_harmonic_cutoff),
        "z_harmonics": _serialize_site_harmonics(site_harmonics, z_harmonic_cutoff),
        "phase_grid_size": int(phase_grid_size),
        "sideband_cutoff": int(sideband_cutoff),
        "source_classical_ansatz": str(ansatz),
        "site_reference_mode": str(site_reference_mode),
        "source_site_ansatz": _serialize_source_site_ansatz(site_ansatz),
        "source_reference_ray": _serialize_vector(first_site_reference),
        "source_generator_matrix": _serialize_matrix(first_site_generator),
        **_top_level_source_reference_metadata(site_reference_mode),
        "restricted_ansatz_stationarity": dict(classical_state.get("ansatz_stationarity", {})),
        "ordering": {"ansatz": str(ansatz), "q_vector": [float(value) for value in q_vector]},
        "harmonic_diagnostics": {
            "site_count": int(site_count),
            "site_reference_mode": str(site_reference_mode),
            "max_reconstruction_error": max((item["max_reconstruction_error"] for item in site_diagnostics), default=0.0),
            "mean_reconstruction_error": float(np.mean([item["mean_reconstruction_error"] for item in site_diagnostics])) if site_diagnostics else 0.0,
            "max_norm_error": max((item["max_norm_error"] for item in site_diagnostics), default=0.0),
            "mean_norm_error": float(np.mean([item["mean_norm_error"] for item in site_diagnostics])) if site_diagnostics else 0.0,
            "phase_grid_size": int(phase_grid_size),
            "sites": site_diagnostics,
        },
    }
