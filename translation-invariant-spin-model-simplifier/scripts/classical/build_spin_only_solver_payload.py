#!/usr/bin/env python3
import math
from copy import deepcopy
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.lattice_geometry import enumerate_neighbor_shells, resolve_lattice_vectors
else:
    from common.lattice_geometry import enumerate_neighbor_shells, resolve_lattice_vectors


def _selected_family(simplification_payload):
    normalized_model = simplification_payload.get("normalized_model", {})
    family = str(normalized_model.get("selected_local_bond_family") or "").strip()
    if not family or family == "all":
        raise ValueError("selected_local_bond_family must name exactly one bridgeable family")
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
        matrix = list(block.get("matrix") or [])
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


def _expand_family_shell_bonds(lattice, shell_index, distance, matrix, family):
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
                "matrix": deepcopy(matrix),
            }
        )
    return bonds


def build_spin_only_solver_payload(simplification_payload):
    normalized_model = deepcopy(simplification_payload.get("normalized_model") or {})
    family = _selected_family(simplification_payload)
    lattice, shell_metadata, shell_index = _family_shell_metadata(normalized_model, family)
    block = _matching_readable_blocks(simplification_payload, family)
    matrix = _exchange_matrix_from_block(block)
    bonds = _expand_family_shell_bonds(
        lattice,
        shell_index=shell_index,
        distance=float(shell_metadata.get("distance")),
        matrix=matrix,
        family=family,
    )

    payload = {
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
    return {"status": "ok", "payload": payload}
