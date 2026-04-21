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
    requested_family = _selected_family(simplification_payload)
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
