#!/usr/bin/env python3
import math
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.bond_orbits import generate_noncull_directed_bond_orbit
    from common.classical_bond_label_resolution import resolve_classical_bond_label
    from common.lattice_geometry import enumerate_neighbor_shells, fractional_to_cartesian, resolve_lattice_vectors
else:
    from common.bond_orbits import generate_noncull_directed_bond_orbit
    from common.classical_bond_label_resolution import resolve_classical_bond_label
    from common.lattice_geometry import enumerate_neighbor_shells, fractional_to_cartesian, resolve_lattice_vectors


def _selected_bond_label(simplification_payload):
    normalized_model = simplification_payload.get("normalized_model", {})
    bond_label = str(normalized_model.get("selected_local_bond_bond_label") or "").strip()
    if not bond_label:
        raise ValueError("selected_local_bond_bond_label must be provided")
    return bond_label


def _bond_label_shell_metadata(normalized_model, bond_label):
    lattice = normalized_model.get("lattice", {})
    bond_label_shell_map = lattice.get("bond_label_shell_map", {}) if isinstance(lattice.get("bond_label_shell_map"), dict) else {}
    metadata = bond_label_shell_map.get(bond_label)
    if not isinstance(metadata, dict):
        raise ValueError(f"missing bond_label_shell_map metadata for bond_label {bond_label!r}")
    shell_index = int(metadata.get("shell_index") or 0)
    if shell_index <= 0:
        raise ValueError(f"invalid shell_index for bond_label {bond_label!r}")
    return lattice, metadata, shell_index


def _bond_label_representative_metadata(normalized_model, bond_label):
    lattice = normalized_model.get("lattice", {})
    representative_map = (
        lattice.get("bond_label_representative_map", {})
        if isinstance(lattice.get("bond_label_representative_map"), dict)
        else {}
    )
    metadata = representative_map.get(bond_label)
    if not isinstance(metadata, dict):
        return lattice, None
    required_fields = {"source", "target", "translation"}
    if not required_fields.issubset(metadata):
        raise ValueError(f"incomplete representative bond metadata for bond_label {bond_label!r}")
    return lattice, metadata


def _supported_block_type(block):
    return str(block.get("type") or "") in {
        "isotropic_exchange",
        "xxz_exchange",
        "symmetric_exchange_matrix",
        "exchange_tensor",
    }


def _bond_label_blocks_and_shell_summary(simplification_payload):
    effective_model = simplification_payload.get("effective_model", {})
    main_blocks = list(effective_model.get("main") or []) if isinstance(effective_model, dict) else []
    bond_label_blocks = {}
    shell_summary = {}
    for block in main_blocks:
        block_type = str(block.get("type") or "")
        bond_label = str(block.get("bond_label") or "").strip()
        if block_type == "shell_resolved_exchange":
            for shell in list(block.get("shells") or []):
                shell_bond_label = str(shell.get("bond_label") or "").strip()
                if shell_bond_label:
                    shell_summary[shell_bond_label] = dict(shell)
            continue
        if bond_label:
            bond_label_blocks[bond_label] = block
    return bond_label_blocks, shell_summary


def _validate_shell_summary_against_bond_label_blocks(bond_label_blocks, shell_summary):
    for bond_label, summary_entry in shell_summary.items():
        block = bond_label_blocks.get(bond_label)
        if block is None:
            continue
        summary_type = str(summary_entry.get("type") or "")
        block_type = str(block.get("type") or "")
        if summary_type and block_type and summary_type != block_type:
            raise ValueError(f"inconsistent shell summary for bond_label {bond_label!r}")


def _bond_label_sort_key(normalized_model, bond_label, shell_summary):
    _lattice, representative_metadata = _bond_label_representative_metadata(normalized_model, bond_label)
    if representative_metadata is not None:
        translation = tuple(int(component) for component in representative_metadata["translation"])
        return (0, translation, str(bond_label))

    _lattice, metadata, shell_index = _bond_label_shell_metadata(normalized_model, bond_label)
    summary_index = shell_summary.get(bond_label, {}).get("shell_index")
    if summary_index is not None and int(summary_index) != int(shell_index):
        raise ValueError(f"inconsistent shell summary ordering for bond_label {bond_label!r}")
    return (1, int(shell_index), str(bond_label))


def _collect_bridgeable_bond_label_blocks(simplification_payload):
    normalized_model = simplification_payload.get("normalized_model", {})
    bond_label_blocks, shell_summary = _bond_label_blocks_and_shell_summary(simplification_payload)
    _validate_shell_summary_against_bond_label_blocks(bond_label_blocks, shell_summary)

    unsupported_families = sorted(
        bond_label for bond_label, block in bond_label_blocks.items() if not _supported_block_type(block)
    )
    if unsupported_families:
        raise ValueError(f"unsupported families in all mode: {unsupported_families}")

    families = sorted(bond_label_blocks.keys(), key=lambda bond_label: _bond_label_sort_key(normalized_model, bond_label, shell_summary))
    if not families:
        fallback_families = sorted(shell_summary.keys(), key=lambda bond_label: _bond_label_sort_key(normalized_model, bond_label, shell_summary))
        if fallback_families:
            families = fallback_families
            for bond_label in fallback_families:
                bond_label_blocks[bond_label] = dict(shell_summary[bond_label])

    if not families:
        raise ValueError("no bridgeable families found for all mode")

    return {
        "families": families,
        "bond_label_blocks": bond_label_blocks,
        "shell_summary": shell_summary,
        "input_precedence": "bond_label_blocks_over_shell_summary" if bond_label_blocks else "shell_summary_fallback",
    }


def _matching_readable_blocks(simplification_payload, bond_label):
    effective_model = simplification_payload.get("effective_model", {})
    main_blocks = list(effective_model.get("main") or []) if isinstance(effective_model, dict) else []
    matches = [block for block in main_blocks if str(block.get("bond_label") or "").strip() == bond_label]
    if not matches and len(main_blocks) == 1 and not str(main_blocks[0].get("bond_label") or "").strip():
        matches = [main_blocks[0]]
    if not matches:
        raise ValueError(f"no readable effective-model block found for bond_label {bond_label!r}")
    if len(matches) != 1:
        raise ValueError(f"multiple readable effective-model blocks found for bond_label {bond_label!r}")
    return matches[0]


def _exchange_matrix_from_block(block):
    block_type = str(block.get("type") or "")
    if block_type == "isotropic_exchange":
        value = float(block["coefficient"])
        return [
            [value, 0.0, 0.0],
            [0.0, value, 0.0],
            [0.0, 0.0, value],
        ]
    if block_type == "xxz_exchange":
        coefficient_xy = float(block["coefficient_xy"])
        coefficient_z = float(block["coefficient_z"])
        return [
            [coefficient_xy, 0.0, 0.0],
            [0.0, coefficient_xy, 0.0],
            [0.0, 0.0, coefficient_z],
        ]
    if block_type in {"symmetric_exchange_matrix", "exchange_tensor"}:
        matrix = list(block.get("resolved_matrix") or block.get("matrix") or [])
        if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
            raise ValueError(f"unsupported readable block matrix shape for type {block_type!r}")
        return [[float(value) for value in row] for row in matrix]
    raise ValueError(f"unsupported readable block for spin-only solver bridge: {block_type or 'unknown'}")


def _simplified_template_for_block(block):
    block_type = str(block.get("type") or "")
    if block_type == "isotropic_exchange":
        return "heisenberg"
    if block_type == "xxz_exchange":
        return "xxz"
    if block_type in {"symmetric_exchange_matrix", "exchange_tensor"}:
        return "generic"
    raise ValueError(f"unsupported readable block for spin-only solver bridge: {block_type or 'unknown'}")


def _distance(left, right):
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))


def _bond_distance(lattice, source, target, translation):
    lattice_vectors = resolve_lattice_vectors(lattice)
    positions = list(lattice.get("positions") or [[0.0, 0.0, 0.0]])
    source_position = positions[int(source)]
    target_position = [
        float(positions[int(target)][axis]) + float(translation[axis]) for axis in range(3)
    ]
    source_cart = fractional_to_cartesian([source_position], lattice_vectors)[0]
    target_cart = fractional_to_cartesian([target_position], lattice_vectors)[0]
    return _distance(source_cart, target_cart)


def _canonical_pair(pair):
    source = int(pair["source"])
    target = int(pair["target"])
    translation = tuple(int(component) for component in pair["translation"])
    inverse = tuple(-component for component in translation)
    for component in translation:
        if component > 0:
            return (source, target, translation)
        if component < 0:
            return (target, source, inverse)
    return min((source, target, translation), (target, source, inverse))


def _canonical_pair_with_orientation(source, target, translation):
    forward = (int(source), int(target), tuple(int(component) for component in translation))
    canonical = _canonical_pair({"source": source, "target": target, "translation": translation})
    return canonical, canonical != forward


def _site_numbers(lattice, site_count):
    types = list(lattice.get("types") or [])
    if len(types) != int(site_count):
        return [1] * int(site_count)
    labels = {}
    numbers = []
    for label in types:
        key = str(label)
        if key not in labels:
            labels[key] = len(labels) + 1
        numbers.append(labels[key])
    return numbers


def _cartesian_spin_rotation_from_fractional(lattice_vectors, rotation):
    basis = np.array(lattice_vectors, dtype=float).T
    cartesian = basis @ np.array(rotation, dtype=float) @ np.linalg.inv(basis)
    determinant = float(np.linalg.det(cartesian))
    # Spin components transform as an axial vector, so improper operations pick
    # up an extra minus sign relative to polar vectors.
    return cartesian if determinant >= 0.0 else -cartesian


def _position_to_site_and_offset(position, basis_positions, *, tolerance=1.0e-6):
    position = np.array(position, dtype=float)
    for site_index, basis in enumerate(basis_positions):
        delta = position - basis
        offset = np.rint(delta)
        if np.allclose(delta, offset, atol=tolerance):
            return int(site_index), tuple(int(value) for value in offset.tolist())
    raise ValueError(f"unable to resolve transformed position {position.tolist()} against basis positions")


def _transform_pair_by_symmetry(pair, rotation, translation, basis_positions):
    source, target, cell_offset = pair
    source_position = basis_positions[int(source)]
    target_position = basis_positions[int(target)] + np.array(cell_offset, dtype=float)
    transformed_source = np.array(rotation, dtype=float) @ source_position + np.array(translation, dtype=float)
    transformed_target = np.array(rotation, dtype=float) @ target_position + np.array(translation, dtype=float)
    source_site, source_offset = _position_to_site_and_offset(transformed_source, basis_positions)
    target_site, target_offset = _position_to_site_and_offset(transformed_target, basis_positions)
    transformed_offset = tuple(int(target_offset[axis] - source_offset[axis]) for axis in range(3))
    return source_site, target_site, transformed_offset


def _bond_score(source, target, translation):
    score = math.sqrt(
        sum((((float(translation[axis]) - 0.1) * weight) ** 2) for axis, weight in enumerate((0.07, 0.08, 0.09)))
    )
    score += 1.0e-2 * (int(source) + int(target))
    score += 1.0e-2 * (-1 if int(source) < int(target) else 1)
    return float(score)


def _select_representative_pair(canonical_pairs):
    return min(canonical_pairs, key=lambda item: _bond_score(item[0], item[1], item[2]))


def _serialize_clean_matrix(matrix, *, tolerance=1.0e-12):
    cleaned = []
    for row in np.array(matrix, dtype=float).tolist():
        cleaned.append([0.0 if abs(float(value)) <= tolerance else float(value) for value in row])
    return cleaned


def _rotation_about_z(angle_radians):
    cosine = math.cos(float(angle_radians))
    sine = math.sin(float(angle_radians))
    return np.array(
        [
            [cosine, -sine, 0.0],
            [sine, cosine, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def _threefold_triangular_bond_label_matrices(canonical_pairs, matrix):
    sources = {pair[0] for pair in canonical_pairs}
    targets = {pair[1] for pair in canonical_pairs}
    translations = {pair[2] for pair in canonical_pairs}
    if len(canonical_pairs) != 3 or len(sources) != 1 or len(targets) != 1:
        return None
    if translations != {(1, 0, 0), (0, 1, 0), (1, 1, 0)}:
        return None

    angle_by_pair = {
        (next(iter(sources)), next(iter(targets)), (1, 0, 0)): 0.0,
        (next(iter(sources)), next(iter(targets)), (0, 1, 0)): 2.0 * math.pi / 3.0,
        (next(iter(sources)), next(iter(targets)), (1, 1, 0)): -2.0 * math.pi / 3.0,
    }
    matrix_array = np.array(matrix, dtype=float)
    return {
        pair: _serialize_clean_matrix(_rotation_about_z(angle_by_pair[pair]) @ matrix_array @ _rotation_about_z(angle_by_pair[pair]).T)
        for pair in canonical_pairs
    }


def _symmetry_rotated_matrices_for_pairs(lattice, canonical_pairs, representative_pair, matrix):
    import spglib

    basis_positions = np.array(lattice.get("positions") or [[0.0, 0.0, 0.0]], dtype=float)
    lattice_vectors = resolve_lattice_vectors(lattice)
    numbers = _site_numbers(lattice, len(basis_positions))
    symmetry = spglib.get_symmetry((np.array(lattice_vectors, dtype=float), basis_positions, numbers), symprec=1.0e-5)
    if not symmetry:
        return {}

    target_pairs = set(canonical_pairs)
    matrix_array = np.array(matrix, dtype=float)
    rotated = {}
    for rotation, translation in zip(symmetry["rotations"], symmetry["translations"]):
        transformed = _transform_pair_by_symmetry(representative_pair, rotation, translation, basis_positions)
        canonical_pair, reversed_orientation = _canonical_pair_with_orientation(*transformed)
        if canonical_pair not in target_pairs or canonical_pair in rotated:
            continue
        rotation_cart = _cartesian_spin_rotation_from_fractional(lattice_vectors, rotation)
        rotated_matrix = rotation_cart @ matrix_array @ rotation_cart.T
        if reversed_orientation:
            rotated_matrix = rotated_matrix.T
        rotated[canonical_pair] = _serialize_clean_matrix(rotated_matrix)
    return rotated


def _expanded_pair_matrices(lattice, canonical_pairs, matrix, bond_label, block_type, selected_coordinate_convention):
    if (
        str(selected_coordinate_convention or "") != "global_crystallographic"
        or str(block_type or "") not in {"symmetric_exchange_matrix", "exchange_tensor"}
        or len(canonical_pairs) <= 1
    ):
        return {pair: deepcopy(matrix) for pair in canonical_pairs}

    threefold_matrices = _threefold_triangular_bond_label_matrices(canonical_pairs, matrix)
    if threefold_matrices is not None:
        return threefold_matrices

    representative_pair = _select_representative_pair(canonical_pairs)
    rotated = _symmetry_rotated_matrices_for_pairs(lattice, canonical_pairs, representative_pair, matrix)
    if not rotated:
        return {pair: deepcopy(matrix) for pair in canonical_pairs}
    missing = [pair for pair in canonical_pairs if pair not in rotated]
    if missing:
        raise ValueError(f"missing symmetry-transformed matrices for bond_label {bond_label!r}: {missing!r}")
    return rotated


def _expand_bond_label_representative_bonds(
    lattice,
    representative_metadata,
    matrix,
    bond_label,
    *,
    block_type="",
    selected_coordinate_convention="",
    shell_index=None,
    distance=None,
):
    orbit = generate_noncull_directed_bond_orbit(
        lattice,
        representative_bond=representative_metadata,
    )
    canonical_pairs = [
        (
            int(member["source"]),
            int(member["target"]),
            tuple(int(component) for component in member["translation"]),
        )
        for member in orbit["members"]
    ]
    matrices_by_pair = _expanded_pair_matrices(
        lattice,
        canonical_pairs,
        matrix,
        bond_label,
        block_type,
        selected_coordinate_convention,
    )
    bonds = []
    for source, target, translation in canonical_pairs:
        bonds.append(
            {
                "source": int(source),
                "target": int(target),
                "vector": list(translation),
                "distance": float(distance) if distance is not None else _bond_distance(lattice, source, target, translation),
                "shell_index": int(shell_index) if shell_index is not None else None,
                "bond_label": bond_label,
                "matrix": deepcopy(matrices_by_pair[(source, target, translation)]),
            }
        )
    return bonds


def _expand_bond_label_shell_bonds(lattice, shell_index, distance, matrix, bond_label, *, block_type="", selected_coordinate_convention=""):
    lattice_vectors = resolve_lattice_vectors(lattice)
    positions = lattice.get("positions") or [[0.0, 0.0, 0.0]]
    shells = enumerate_neighbor_shells(
        lattice_vectors,
        positions,
        shell_count=int(shell_index),
        max_translation=3,
    )
    if len(shells) < int(shell_index):
        raise ValueError(f"unable to enumerate shell {shell_index}")
    shell = shells[int(shell_index) - 1]
    target_distance = float(distance)
    if abs(float(shell.get("distance", 0.0)) - target_distance) > 1.0e-6:
        raise ValueError(
            f"shell {shell_index} distance mismatch: enumerated {shell.get('distance')} vs metadata {target_distance}"
        )

    canonical_pairs = sorted({_canonical_pair(pair) for pair in shell.get("pairs", [])}, key=lambda item: item[2])
    if not canonical_pairs:
        raise ValueError(f"shell {shell_index} has no bridgeable representative pairs")
    matrices_by_pair = _expanded_pair_matrices(
        lattice,
        canonical_pairs,
        matrix,
        bond_label,
        block_type,
        selected_coordinate_convention,
    )
    bonds = []
    for source, target, translation in canonical_pairs:
        bonds.append(
            {
                "source": int(source),
                "target": int(target),
                "vector": list(translation),
                "distance": float(target_distance),
                "shell_index": int(shell_index),
                "bond_label": bond_label,
                "matrix": deepcopy(matrices_by_pair[(source, target, translation)]),
            }
        )
    return bonds


def _is_lattice_term_payload(payload):
    return isinstance(payload, dict) and payload.get("schema_version") == "lattice-term-contract/v1"


def _canonical_classical_space_kinds(payload):
    local_hilbert = payload.get("local_hilbert", {}) if isinstance(payload, dict) else {}
    classical_spaces = local_hilbert.get("classical_spaces", {}) if isinstance(local_hilbert, dict) else {}
    return {
        str(record.get("kind"))
        for record in classical_spaces.values()
        if isinstance(record, dict) and record.get("kind") is not None
    }


def _canonical_local_dimension(payload):
    local_hilbert = payload.get("local_hilbert", {}) if isinstance(payload, dict) else {}
    basis_registry = local_hilbert.get("basis_registry", {}) if isinstance(local_hilbert, dict) else {}
    for basis in basis_registry.values():
        if not isinstance(basis, dict):
            continue
        try:
            dimension = int(basis.get("dimension"))
        except (TypeError, ValueError):
            continue
        if dimension > 0:
            return dimension
    return None


def _canonical_bond_orbits_by_ref(payload):
    lattice_structure = payload.get("lattice_structure", {}) if isinstance(payload, dict) else {}
    return {
        str(orbit.get("orbit_ref")): orbit
        for orbit in list(lattice_structure.get("bond_orbits") or [])
        if isinstance(orbit, dict) and orbit.get("orbit_ref") is not None
    }


def _canonical_selected_term_refs(payload):
    solver_request = payload.get("solver_request", {}) if isinstance(payload, dict) else {}
    term_attachments = payload.get("term_attachments", {}) if isinstance(payload, dict) else {}
    selected_term_refs = {str(ref) for ref in list(solver_request.get("selected_term_refs") or [])}
    selected_orbit_refs = {str(ref) for ref in list(solver_request.get("selected_bond_orbit_refs") or [])}
    selected_term_set_ref = solver_request.get("selected_term_set_ref")
    if selected_term_set_ref:
        for term_set in list(term_attachments.get("term_sets") or []):
            if not isinstance(term_set, dict) or str(term_set.get("term_set_ref")) != str(selected_term_set_ref):
                continue
            selected_term_refs.update(str(ref) for ref in list(term_set.get("term_refs") or []))
            selected_orbit_refs.update(str(ref) for ref in list(term_set.get("bond_orbit_refs") or []))
            break
    return selected_term_refs, selected_orbit_refs


def _canonical_scalar_to_float(value, parameters):
    if isinstance(value, dict):
        kind = value.get("kind")
        if kind == "real":
            return float(value.get("value", 0.0))
        if kind == "complex":
            imaginary = float(value.get("im", 0.0))
            if abs(imaginary) > 1.0e-12:
                raise ValueError("spin-only exchange matrices must be real")
            return float(value.get("re", 0.0))
        if kind == "parameter_ref":
            ref = str(value.get("parameter_ref") or "")
            key = ref.split("param:", 1)[1] if ref.startswith("param:") else ref
            if ref in parameters:
                return float(parameters[ref])
            if key in parameters:
                return float(parameters[key])
            raise ValueError(f"unbound parameter reference in exchange matrix: {ref}")
    return float(value)


def _canonical_matrix_to_float_rows(matrix, parameters):
    rows = matrix.get("data") if isinstance(matrix, dict) else None
    if rows is None and isinstance(matrix, dict):
        rows = matrix.get("entries")
    if rows is None:
        rows = matrix
    rows = list(rows or [])
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError("spin-only exchange matrix must have shape 3x3")
    return [[_canonical_scalar_to_float(value, parameters) for value in row] for row in rows]


def _canonical_selected_bond_terms(payload):
    term_attachments = payload.get("term_attachments", {}) if isinstance(payload, dict) else {}
    bond_terms = [term for term in list(term_attachments.get("bond_terms") or []) if isinstance(term, dict)]
    selected_term_refs, selected_orbit_refs = _canonical_selected_term_refs(payload)
    if not selected_term_refs and not selected_orbit_refs:
        return bond_terms
    selected = []
    for term in bond_terms:
        attach_to = term.get("attach_to", {}) if isinstance(term.get("attach_to"), dict) else {}
        term_ref = str(term.get("term_ref") or "")
        orbit_ref = str(attach_to.get("orbit_ref") or "")
        if term_ref in selected_term_refs or orbit_ref in selected_orbit_refs:
            selected.append(term)
    return selected


def _canonical_spin_only_solver_payload(payload):
    if "unit_vector_sphere" not in _canonical_classical_space_kinds(payload):
        raise ValueError("unsupported-classical-space: spin-only builder requires unit_vector_sphere")

    parameters = payload.get("parameters", {}) if isinstance(payload.get("parameters"), dict) else {}
    orbit_by_ref = _canonical_bond_orbits_by_ref(payload)
    selected_terms = _canonical_selected_bond_terms(payload)
    if not selected_terms:
        raise ValueError("no canonical spin bond terms selected")

    bonds = []
    term_summaries = []
    for term in selected_terms:
        term_payload = term.get("payload", {}) if isinstance(term.get("payload"), dict) else {}
        if term_payload.get("kind") != "bilinear_exchange_matrix":
            raise ValueError(f"unsupported-term-payload: {term_payload.get('kind')}")
        matrix = _canonical_matrix_to_float_rows(term_payload.get("matrix", {}), parameters)
        attach_to = term.get("attach_to", {}) if isinstance(term.get("attach_to"), dict) else {}
        orbit_ref = str(attach_to.get("orbit_ref") or "")
        orbit = orbit_by_ref.get(orbit_ref)
        if not isinstance(orbit, dict):
            raise ValueError(f"unknown-bond-orbit-ref: {orbit_ref}")
        members = list(orbit.get("members") or [])
        if not members and isinstance(orbit.get("representative"), dict):
            members = [orbit["representative"]]
        for member in members:
            if not isinstance(member, dict):
                continue
            bonds.append(
                {
                    "source": int(member.get("source", 0)),
                    "target": int(member.get("target", 0)),
                    "vector": [int(component) for component in list(member.get("translation") or [0, 0, 0])],
                    "distance": float(member.get("distance", orbit.get("distance", 0.0)) or 0.0),
                    "shell_index": int(orbit.get("shell")) if orbit.get("shell") is not None else None,
                    "term_ref": str(term.get("term_ref") or ""),
                    "bond_orbit_ref": orbit_ref,
                    "matrix": deepcopy(matrix),
                }
            )
        term_summaries.append(
            {
                "term_ref": str(term.get("term_ref") or ""),
                "bond_orbit_ref": orbit_ref,
                "member_count": len(members),
            }
        )

    return {
        "status": "ok",
        "payload": {
            "schema_version": payload.get("schema_version"),
            "lattice_structure": deepcopy(payload.get("lattice_structure") or {}),
            "local_hilbert": deepcopy(payload.get("local_hilbert") or {}),
            "local_dim": _canonical_local_dimension(payload),
            "normalized_model": deepcopy(payload),
            "simplified_model": {"template": "generic"},
            "bonds": bonds,
            "classical": {"method": "auto"},
            "bridge_metadata": {
                "bridge_kind": "canonical_lattice_term_spin_only",
                "selection_policy": (payload.get("solver_request") or {}).get("selection_policy"),
                "term_summaries": term_summaries,
            },
        },
    }


def build_spin_only_solver_payload(simplification_payload):
    if _is_lattice_term_payload(simplification_payload):
        return _canonical_spin_only_solver_payload(simplification_payload)

    bond_label_resolution = resolve_classical_bond_label(payload=simplification_payload)
    if bond_label_resolution["classical_bond_label"] != "spin-only":
        raise ValueError(
            "incompatible-classical-bond_label: "
            f"spin-only bridge builder requires spin-only bond_label, got {bond_label_resolution['classical_bond_label']}"
        )
    normalized_model = deepcopy(simplification_payload.get("normalized_model") or {})
    requested_bond_label = _selected_bond_label(simplification_payload)
    selected_coordinate_convention = normalized_model.get("selected_coordinate_convention")
    onsite_terms = deepcopy(
        normalized_model.get("onsite_terms")
        or (simplification_payload.get("effective_model") or {}).get("onsite_terms")
        or []
    )
    if requested_bond_label == "all":
        collected = _collect_bridgeable_bond_label_blocks(simplification_payload)
        families = collected["families"]
        all_bonds = []
        bond_label_summaries = []
        first_template = None
        template_consistent = True
        for bond_label in families:
            lattice, representative_metadata = _bond_label_representative_metadata(normalized_model, bond_label)
            shell_metadata = None
            shell_index = None
            if representative_metadata is None:
                lattice, shell_metadata, shell_index = _bond_label_shell_metadata(normalized_model, bond_label)
            else:
                bond_label_shell_map = lattice.get("bond_label_shell_map", {}) if isinstance(lattice.get("bond_label_shell_map"), dict) else {}
                shell_metadata = bond_label_shell_map.get(bond_label, {})
                shell_index = shell_metadata.get("shell_index")
            block = dict(collected["bond_label_blocks"][bond_label])
            block.setdefault("bond_label", bond_label)
            matrix = _exchange_matrix_from_block(block)
            if representative_metadata is not None:
                expanded_bonds = _expand_bond_label_representative_bonds(
                    lattice,
                    representative_metadata=representative_metadata,
                    matrix=matrix,
                    bond_label=bond_label,
                    block_type=str(block.get("type") or ""),
                    selected_coordinate_convention=selected_coordinate_convention,
                    shell_index=shell_index,
                    distance=shell_metadata.get("distance") if isinstance(shell_metadata, dict) else None,
                )
                bond_label_expansion_mode = "representative_orbit"
            else:
                expanded_bonds = _expand_bond_label_shell_bonds(
                    lattice,
                    shell_index=shell_index,
                    distance=float(shell_metadata.get("distance")),
                    matrix=matrix,
                    bond_label=bond_label,
                    block_type=str(block.get("type") or ""),
                    selected_coordinate_convention=selected_coordinate_convention,
                )
                bond_label_expansion_mode = "full_shell"
            all_bonds.extend(expanded_bonds)
            bond_label_summaries.append(
                {
                    "bond_label": bond_label,
                    "shell_index": int(shell_index) if shell_index is not None else None,
                    "block_type": str(block.get("type") or ""),
                    "pair_count": len(expanded_bonds),
                    "expansion_mode": bond_label_expansion_mode,
                }
            )
            template = _simplified_template_for_block(block)
            if first_template is None:
                first_template = template
            elif first_template != template:
                template_consistent = False

        payload = {
            "classical_bond_label": bond_label_resolution["classical_bond_label"],
            "lattice": deepcopy(normalized_model.get("lattice") or {}),
            "local_dim": normalized_model.get("local_hilbert", {}).get("dimension"),
            "normalized_model": normalized_model,
            "effective_model": deepcopy(simplification_payload.get("effective_model") or {}),
            "simplified_model": {
                "template": first_template if template_consistent and first_template is not None else "generic",
            },
            "bonds": all_bonds,
            "classical": {"method": "auto"},
            "bridge_metadata": {
                "bridge_kind": "document_reader_spin_only_all_bond_label_assembled",
                "expansion_mode": "all_families",
                "selected_families": list(families),
                "bond_label_order": list(families),
                "bond_label_summaries": bond_label_summaries,
                "input_precedence": collected["input_precedence"],
            },
        }
        if onsite_terms:
            payload["onsite_terms"] = onsite_terms
        return {"status": "ok", "payload": payload}

    bond_label = requested_bond_label
    lattice, representative_metadata = _bond_label_representative_metadata(normalized_model, bond_label)
    shell_metadata = None
    shell_index = None
    if representative_metadata is None:
        lattice, shell_metadata, shell_index = _bond_label_shell_metadata(normalized_model, bond_label)
    else:
        bond_label_shell_map = lattice.get("bond_label_shell_map", {}) if isinstance(lattice.get("bond_label_shell_map"), dict) else {}
        shell_metadata = bond_label_shell_map.get(bond_label, {})
        shell_index = shell_metadata.get("shell_index")
    block = _matching_readable_blocks(simplification_payload, bond_label)
    matrix = _exchange_matrix_from_block(block)
    if representative_metadata is not None:
        bonds = _expand_bond_label_representative_bonds(
            lattice,
            representative_metadata=representative_metadata,
            matrix=matrix,
            bond_label=bond_label,
            block_type=str(block.get("type") or ""),
            selected_coordinate_convention=selected_coordinate_convention,
            shell_index=shell_index,
            distance=shell_metadata.get("distance") if isinstance(shell_metadata, dict) else None,
        )
        expansion_mode = "representative_orbit"
    else:
        bonds = _expand_bond_label_shell_bonds(
            lattice,
            shell_index=shell_index,
            distance=float(shell_metadata.get("distance")),
            matrix=matrix,
            bond_label=bond_label,
            block_type=str(block.get("type") or ""),
            selected_coordinate_convention=selected_coordinate_convention,
        )
        expansion_mode = "full_shell"

    payload = {
        "classical_bond_label": bond_label_resolution["classical_bond_label"],
        "lattice": deepcopy(lattice),
        "local_dim": normalized_model.get("local_hilbert", {}).get("dimension"),
        "normalized_model": normalized_model,
        "effective_model": deepcopy(simplification_payload.get("effective_model") or {}),
        "simplified_model": {
            "template": _simplified_template_for_block(block),
        },
        "bonds": bonds,
        "classical": {"method": "auto"},
        "bridge_metadata": {
            "bridge_kind": "document_reader_spin_only_shell_expanded",
            "expansion_mode": expansion_mode,
            "selected_bond_label": bond_label,
            "block_type": str(block.get("type") or ""),
            "shell_index": int(shell_index) if shell_index is not None else None,
            "pair_count": len(bonds),
        },
    }
    if onsite_terms:
        payload["onsite_terms"] = onsite_terms
    return {"status": "ok", "payload": payload}
