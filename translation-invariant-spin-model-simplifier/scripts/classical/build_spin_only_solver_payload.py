#!/usr/bin/env python3
import math
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import spglib

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.classical_family_resolution import resolve_classical_family
    from common.lattice_geometry import enumerate_neighbor_shells, resolve_lattice_vectors
else:
    from common.classical_family_resolution import resolve_classical_family
    from common.lattice_geometry import enumerate_neighbor_shells, resolve_lattice_vectors


def _selected_family(simplification_payload):
    normalized_model = simplification_payload.get("normalized_model", {})
    family = str(normalized_model.get("selected_local_bond_family") or "").strip()
    if not family:
        raise ValueError("selected_local_bond_family must be provided")
    return family


def _family_shell_metadata(normalized_model, family):
    lattice = normalized_model.get("lattice", {})
    family_shell_map = lattice.get("family_shell_map", {}) if isinstance(lattice.get("family_shell_map"), dict) else {}
    metadata = family_shell_map.get(family)
    if not isinstance(metadata, dict):
        raise ValueError(f"missing family_shell_map metadata for family {family!r}")
    shell_index = int(metadata.get("shell_index") or 0)
    if shell_index <= 0:
        raise ValueError(f"invalid shell_index for family {family!r}")
    return lattice, metadata, shell_index


def _supported_block_type(block):
    return str(block.get("type") or "") in {
        "isotropic_exchange",
        "xxz_exchange",
        "symmetric_exchange_matrix",
        "exchange_tensor",
    }


def _family_blocks_and_shell_summary(simplification_payload):
    effective_model = simplification_payload.get("effective_model", {})
    main_blocks = list(effective_model.get("main") or []) if isinstance(effective_model, dict) else []
    family_blocks = {}
    shell_summary = {}
    for block in main_blocks:
        block_type = str(block.get("type") or "")
        family = str(block.get("family") or "").strip()
        if block_type == "shell_resolved_exchange":
            for shell in list(block.get("shells") or []):
                shell_family = str(shell.get("family") or "").strip()
                if shell_family:
                    shell_summary[shell_family] = dict(shell)
            continue
        if family:
            family_blocks[family] = block
    return family_blocks, shell_summary


def _validate_shell_summary_against_family_blocks(family_blocks, shell_summary):
    for family, summary_entry in shell_summary.items():
        block = family_blocks.get(family)
        if block is None:
            continue
        summary_type = str(summary_entry.get("type") or "")
        block_type = str(block.get("type") or "")
        if summary_type and block_type and summary_type != block_type:
            raise ValueError(f"inconsistent shell summary for family {family!r}")


def _family_sort_key(normalized_model, family, shell_summary):
    _lattice, metadata, shell_index = _family_shell_metadata(normalized_model, family)
    summary_index = shell_summary.get(family, {}).get("shell_index")
    if summary_index is not None and int(summary_index) != int(shell_index):
        raise ValueError(f"inconsistent shell summary ordering for family {family!r}")
    return (int(shell_index), str(family))


def _collect_bridgeable_family_blocks(simplification_payload):
    normalized_model = simplification_payload.get("normalized_model", {})
    family_blocks, shell_summary = _family_blocks_and_shell_summary(simplification_payload)
    _validate_shell_summary_against_family_blocks(family_blocks, shell_summary)

    unsupported_families = sorted(
        family for family, block in family_blocks.items() if not _supported_block_type(block)
    )
    if unsupported_families:
        raise ValueError(f"unsupported families in all mode: {unsupported_families}")

    families = sorted(family_blocks.keys(), key=lambda family: _family_sort_key(normalized_model, family, shell_summary))
    if not families:
        fallback_families = sorted(shell_summary.keys(), key=lambda family: _family_sort_key(normalized_model, family, shell_summary))
        if fallback_families:
            families = fallback_families
            for family in fallback_families:
                family_blocks[family] = dict(shell_summary[family])

    if not families:
        raise ValueError("no bridgeable families found for all mode")

    return {
        "families": families,
        "family_blocks": family_blocks,
        "shell_summary": shell_summary,
        "input_precedence": "family_blocks_over_shell_summary" if family_blocks else "shell_summary_fallback",
    }


def _matching_readable_blocks(simplification_payload, family):
    effective_model = simplification_payload.get("effective_model", {})
    main_blocks = list(effective_model.get("main") or []) if isinstance(effective_model, dict) else []
    matches = [block for block in main_blocks if str(block.get("family") or "").strip() == family]
    if not matches and len(main_blocks) == 1 and not str(main_blocks[0].get("family") or "").strip():
        matches = [main_blocks[0]]
    if not matches:
        raise ValueError(f"no readable effective-model block found for family {family!r}")
    if len(matches) != 1:
        raise ValueError(f"multiple readable effective-model blocks found for family {family!r}")
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


def _threefold_triangular_family_matrices(canonical_pairs, matrix):
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


def _expanded_pair_matrices(lattice, canonical_pairs, matrix, family, block_type, selected_coordinate_convention):
    if (
        str(selected_coordinate_convention or "") != "global_crystallographic"
        or str(block_type or "") not in {"symmetric_exchange_matrix", "exchange_tensor"}
        or len(canonical_pairs) <= 1
    ):
        return {pair: deepcopy(matrix) for pair in canonical_pairs}

    threefold_matrices = _threefold_triangular_family_matrices(canonical_pairs, matrix)
    if threefold_matrices is not None:
        return threefold_matrices

    representative_pair = _select_representative_pair(canonical_pairs)
    rotated = _symmetry_rotated_matrices_for_pairs(lattice, canonical_pairs, representative_pair, matrix)
    if not rotated:
        return {pair: deepcopy(matrix) for pair in canonical_pairs}
    missing = [pair for pair in canonical_pairs if pair not in rotated]
    if missing:
        raise ValueError(f"missing symmetry-transformed matrices for family {family!r}: {missing!r}")
    return rotated


def _expand_family_shell_bonds(lattice, shell_index, distance, matrix, family, *, block_type="", selected_coordinate_convention=""):
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
        family,
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
                "family": family,
                "matrix": deepcopy(matrices_by_pair[(source, target, translation)]),
            }
        )
    return bonds


def build_spin_only_solver_payload(simplification_payload):
    family_resolution = resolve_classical_family(payload=simplification_payload)
    if family_resolution["classical_family"] != "spin-only":
        raise ValueError(
            "incompatible-classical-family: "
            f"spin-only bridge builder requires spin-only family, got {family_resolution['classical_family']}"
        )
    normalized_model = deepcopy(simplification_payload.get("normalized_model") or {})
    requested_family = _selected_family(simplification_payload)
    selected_coordinate_convention = normalized_model.get("selected_coordinate_convention")
    onsite_terms = deepcopy(
        normalized_model.get("onsite_terms")
        or (simplification_payload.get("effective_model") or {}).get("onsite_terms")
        or []
    )
    if requested_family == "all":
        collected = _collect_bridgeable_family_blocks(simplification_payload)
        families = collected["families"]
        all_bonds = []
        family_summaries = []
        first_template = None
        template_consistent = True
        for family in families:
            lattice, shell_metadata, shell_index = _family_shell_metadata(normalized_model, family)
            block = dict(collected["family_blocks"][family])
            block.setdefault("family", family)
            matrix = _exchange_matrix_from_block(block)
            expanded_bonds = _expand_family_shell_bonds(
                lattice,
                shell_index=shell_index,
                distance=float(shell_metadata.get("distance")),
                matrix=matrix,
                family=family,
                block_type=str(block.get("type") or ""),
                selected_coordinate_convention=selected_coordinate_convention,
            )
            all_bonds.extend(expanded_bonds)
            family_summaries.append(
                {
                    "family": family,
                    "shell_index": int(shell_index),
                    "block_type": str(block.get("type") or ""),
                    "pair_count": len(expanded_bonds),
                }
            )
            template = _simplified_template_for_block(block)
            if first_template is None:
                first_template = template
            elif first_template != template:
                template_consistent = False

        payload = {
            "classical_family": family_resolution["classical_family"],
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
                "bridge_kind": "document_reader_spin_only_all_family_assembled",
                "expansion_mode": "all_families",
                "selected_families": list(families),
                "family_order": list(families),
                "family_summaries": family_summaries,
                "input_precedence": collected["input_precedence"],
            },
        }
        if onsite_terms:
            payload["onsite_terms"] = onsite_terms
        return {"status": "ok", "payload": payload}

    family = requested_family
    lattice, shell_metadata, shell_index = _family_shell_metadata(normalized_model, family)
    block = _matching_readable_blocks(simplification_payload, family)
    matrix = _exchange_matrix_from_block(block)
    bonds = _expand_family_shell_bonds(
        lattice,
        shell_index=shell_index,
        distance=float(shell_metadata.get("distance")),
        matrix=matrix,
        family=family,
        block_type=str(block.get("type") or ""),
        selected_coordinate_convention=selected_coordinate_convention,
    )

    payload = {
        "classical_family": family_resolution["classical_family"],
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
            "expansion_mode": "full_shell",
            "selected_family": family,
            "block_type": str(block.get("type") or ""),
            "shell_index": int(shell_index),
            "pair_count": len(bonds),
        },
    }
    if onsite_terms:
        payload["onsite_terms"] = onsite_terms
    return {"status": "ok", "payload": payload}
