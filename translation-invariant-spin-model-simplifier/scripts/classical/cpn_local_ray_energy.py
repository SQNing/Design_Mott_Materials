#!/usr/bin/env python3

import numpy as np

from common.pseudospin_orbital_conventions import resolve_pseudospin_orbital_conventions


def complex_from_serialized(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def serialize_complex(value):
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def deserialize_vector(serialized):
    return np.array([complex_from_serialized(value) for value in serialized], dtype=complex)


def serialize_vector(vector):
    return [serialize_complex(value) for value in vector]


def deserialize_tensor(serialized):
    local_dimension = len(serialized)
    tensor = np.zeros((local_dimension, local_dimension, local_dimension, local_dimension), dtype=complex)
    for a in range(local_dimension):
        for b in range(local_dimension):
            for c in range(local_dimension):
                for d in range(local_dimension):
                    tensor[a, b, c, d] = complex_from_serialized(serialized[a][b][c][d])
    return tensor


def unit_norm_ray(vector):
    vector = np.array(vector, dtype=complex)
    norm = float(np.linalg.norm(vector))
    if norm <= 1.0e-14:
        raise ValueError("local ray must not be the zero vector")
    return vector / norm


def normalized_ray(vector):
    vector = unit_norm_ray(vector)
    for value in vector:
        if abs(value) > 1.0e-12:
            vector = vector / (value / abs(value))
            break
    return vector


def mod_index(index, shape):
    return tuple(int(index[axis]) % int(shape[axis]) for axis in range(3))


def magnetic_site_count(model):
    return max(1, int(model.get("magnetic_site_count", 1)))


def local_dimension(model):
    return int(model["local_dimension"])


def state_array_from_model(model, supercell_shape, seed):
    shape = tuple(int(value) for value in supercell_shape)
    site_count = magnetic_site_count(model)
    dim = local_dimension(model)
    rng = np.random.default_rng(seed)
    state = np.zeros(shape + (site_count, dim), dtype=complex)
    for cell_index in np.ndindex(shape):
        for site_index in range(site_count):
            vector = rng.normal(size=dim) + 1.0j * rng.normal(size=dim)
            state[cell_index + (site_index,)] = unit_norm_ray(vector)
    return state


def tiled_state_array(previous_state, new_shape):
    new_shape = tuple(int(value) for value in new_shape)
    site_count = int(previous_state.shape[3])
    dim = int(previous_state.shape[4])
    tiled = np.zeros(new_shape + (site_count, dim), dtype=complex)
    old_shape = previous_state.shape[:3]
    for cell_index in np.ndindex(new_shape):
        source = tuple(int(cell_index[axis]) % int(old_shape[axis]) for axis in range(3))
        tiled[cell_index] = previous_state[source]
    return tiled


def state_array_from_serialized(state):
    shape = tuple(int(value) for value in state["shape"])
    rays = state.get("local_rays", [])
    if not rays:
        raise ValueError("serialized local-ray state must contain local_rays")
    dim = len(rays[0]["vector"])
    site_count = max(1, max(int(item.get("site", 0)) for item in rays) + 1)
    array = np.zeros(shape + (site_count, dim), dtype=complex)
    for item in rays:
        cell = tuple(int(value) for value in item["cell"])
        site = int(item.get("site", 0))
        array[cell + (site,)] = normalized_ray(deserialize_vector(item["vector"]))
    return array


def serialize_state_array(state_array):
    shape = list(state_array.shape[:3])
    site_count = int(state_array.shape[3])
    rays = []
    for cell_index in np.ndindex(tuple(shape)):
        for site_index in range(site_count):
            entry = {
                "cell": [int(value) for value in cell_index],
                "vector": serialize_vector(normalized_ray(state_array[cell_index + (site_index,)])),
            }
            if site_count > 1:
                entry["site"] = int(site_index)
            rays.append(entry)
    return {"shape": shape, "local_rays": rays}


def bond_energy(tensor, left_vector, right_vector):
    return complex(
        np.einsum(
            "abcd,a,b,c,d",
            tensor,
            np.conjugate(left_vector),
            left_vector,
            np.conjugate(right_vector),
            right_vector,
            optimize=True,
        )
    )


def evaluate_cpn_local_ray_energy(model, state_array):
    energy = 0.0 + 0.0j
    cell_shape = state_array.shape[:3]
    for cell_index in np.ndindex(cell_shape):
        for bond in model.get("bond_tensors", []):
            tensor = deserialize_tensor(bond["tensor"])
            source = int(bond.get("source", 0))
            target = int(bond.get("target", 0))
            R = tuple(int(value) for value in bond["R"])
            right_index = mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), cell_shape)
            left_vector = state_array[cell_index + (source,)]
            right_vector = state_array[right_index + (target,)]
            energy += bond_energy(tensor, left_vector, right_vector)
    return float(np.real(energy) / float(np.prod(cell_shape)))


def effective_local_matrix(model, state_array, cell_index, site_index):
    dim = local_dimension(model)
    matrix = np.zeros((dim, dim), dtype=complex)
    cell_shape = state_array.shape[:3]
    for bond in model.get("bond_tensors", []):
        tensor = deserialize_tensor(bond["tensor"])
        source = int(bond.get("source", 0))
        target = int(bond.get("target", 0))
        R = tuple(int(value) for value in bond["R"])

        if int(site_index) == source:
            right_index = mod_index(tuple(cell_index[axis] + R[axis] for axis in range(3)), cell_shape)
            partner = state_array[right_index + (target,)]
            matrix += np.einsum("abcd,c,d->ab", tensor, np.conjugate(partner), partner, optimize=True)

        if int(site_index) == target:
            left_index = mod_index(tuple(cell_index[axis] - R[axis] for axis in range(3)), cell_shape)
            partner = state_array[left_index + (source,)]
            matrix += np.einsum("cdab,c,d->ab", tensor, np.conjugate(partner), partner, optimize=True)

    return 0.5 * (matrix + matrix.conjugate().T)


def sweep_local_ray_state(model, state_array):
    max_change = 0.0
    for cell_index in np.ndindex(state_array.shape[:3]):
        for site_index in range(state_array.shape[3]):
            matrix = effective_local_matrix(model, state_array, cell_index, site_index)
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            updated = normalized_ray(eigenvectors[:, int(np.argmin(eigenvalues))])
            previous = state_array[cell_index + (site_index,)]
            max_change = max(
                max_change,
                float(
                    min(
                        np.linalg.norm(updated - previous),
                        np.linalg.norm(updated + previous),
                    )
                ),
            )
            state_array[cell_index + (site_index,)] = updated
    return state_array, float(max_change)


def projector_fourier_diagnostics(state_array):
    shape = tuple(int(value) for value in state_array.shape[:3])
    cell_count = int(np.prod(shape))
    site_count = int(state_array.shape[3])
    dim = int(state_array.shape[4])

    components = []
    uniform_weight = 0.0
    dominant_q = None
    dominant_weight = -1.0

    for q_index in np.ndindex(shape):
        q = [float(q_index[axis]) / float(shape[axis]) for axis in range(3)]
        weight = 0.0
        serialized_by_site = []
        for site_index in range(site_count):
            matrix = np.zeros((dim, dim), dtype=complex)
            for cell_index in np.ndindex(shape):
                phase = np.exp(
                    -2.0j * np.pi * sum(float(q[axis]) * float(cell_index[axis]) for axis in range(3))
                )
                vector = state_array[cell_index + (site_index,)]
                matrix += phase * np.outer(vector, np.conjugate(vector))
            matrix /= float(cell_count)
            weight += float(np.real(np.sum(np.abs(matrix) ** 2)))
            serialized_by_site.append({"site": int(site_index), "matrix": [[serialize_complex(v) for v in row] for row in matrix]})

        is_zero_q = all(abs(value) <= 1.0e-12 for value in q)
        if is_zero_q:
            uniform_weight = float(weight)
        elif weight > dominant_weight + 1.0e-14:
            dominant_q = list(q)
            dominant_weight = float(weight)
        components.append(
            {
                "q": list(q),
                "weight": float(weight),
                "is_zero_q": bool(is_zero_q),
                "projectors_by_site": serialized_by_site,
            }
        )

    ordering_kind = "uniform"
    if dominant_weight > 1.0e-10:
        ordering_kind = "commensurate-supercell"

    return {
        "grid_shape": list(shape),
        "components": components,
        "uniform_q_weight": float(uniform_weight),
        "dominant_ordering_q": dominant_q,
        "dominant_ordering_weight": float(max(0.0, dominant_weight)),
        "ordering_kind": ordering_kind,
    }


def stationarity_summary(model, state_array):
    residuals = []
    norms = []
    for cell_index in np.ndindex(state_array.shape[:3]):
        for site_index in range(state_array.shape[3]):
            vector = state_array[cell_index + (site_index,)]
            matrix = effective_local_matrix(model, state_array, cell_index, site_index)
            lagrange_multiplier = complex(np.vdot(vector, matrix @ vector))
            residual = matrix @ vector - lagrange_multiplier * vector
            residual_norm = float(np.linalg.norm(residual))
            norms.append(residual_norm)
            residuals.append(
                {
                    "cell": [int(value) for value in cell_index],
                    "site": int(site_index),
                    "lagrange_multiplier": serialize_complex(lagrange_multiplier),
                    "residual_norm": residual_norm,
                    "residual_vector": serialize_vector(residual),
                }
            )

    return {
        "residual_definition": "r_i = H_i^eff z_i - (z_i^dagger H_i^eff z_i) z_i, measured in Euclidean norm",
        "max_residual_norm": float(max(norms) if norms else 0.0),
        "mean_residual_norm": float(sum(norms) / len(norms) if norms else 0.0),
        "sites": residuals,
    }


def canonical_classical_state(model, state_array, diagnostics):
    conventions = resolve_pseudospin_orbital_conventions(model)
    serialized = serialize_state_array(state_array)
    ordering = {
        "kind": diagnostics["projector_diagnostics"].get("ordering_kind"),
        "q_vector": diagnostics["projector_diagnostics"].get("dominant_ordering_q"),
        "supercell_shape": list(serialized["shape"]),
    }
    return {
        "schema_version": 1,
        "state_kind": "local_rays",
        "manifold": "CP^(N-1)",
        "basis_order": conventions["basis_order"],
        "pair_basis_order": conventions["pair_basis_order"],
        "supercell_shape": list(serialized["shape"]),
        "local_rays": list(serialized["local_rays"]),
        "ordering": ordering,
    }
