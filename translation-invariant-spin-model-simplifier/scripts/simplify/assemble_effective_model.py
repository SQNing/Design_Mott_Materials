#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _shell_sort_key(label, shell_index=None):
    if shell_index is not None:
        try:
            return (0, int(shell_index), str(label))
        except (TypeError, ValueError):
            pass
    text = str(label)
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return (0, int(digits), text)
    return (1, text)


def _derive_physical_parameter_view(block):
    physical_label = block.get("physical_label")
    parameters = list(block.get("human_parameters") or [])
    parameter_names = [entry.get("name") for entry in parameters]

    if block.get("physical_parameter_view"):
        return dict(block.get("physical_parameter_view"))

    if parameter_names == ["Jzz", "Jpm", "Jpmpm", "Jzpm"]:
        return {
            "view_kind": "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm",
            "parameters": list(parameters),
            "physical_label": physical_label or "anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm)",
        }

    if block.get("type") == "xxz_exchange" and parameter_names == ["Jxy", "Jz"]:
        return {
            "view_kind": "xxz_exchange_jxy_jz",
            "parameters": list(parameters),
            "physical_label": physical_label or "xxz exchange",
        }

    if block.get("type") == "exchange_tensor":
        parameter_by_name = {entry.get("name"): entry for entry in parameters if entry.get("name")}
        ordered_parameters = []
        if "Jiso" in parameter_by_name:
            ordered_parameters.append(parameter_by_name["Jiso"])
        for name in ("Gamma_xy", "Gamma_xz", "Gamma_yz"):
            if name in parameter_by_name:
                ordered_parameters.append(parameter_by_name[name])
        for name in ("Dx", "Dy", "Dz"):
            if name in parameter_by_name:
                ordered_parameters.append(parameter_by_name[name])
        if "Jiso" in parameter_by_name and len(ordered_parameters) >= 4:
            return {
                "view_kind": "exchange_tensor_jiso_gamma_dm",
                "parameters": ordered_parameters,
                "physical_label": physical_label or "general exchange tensor (Jiso/Gamma/DM)",
            }

    if block.get("type") == "symmetric_exchange_matrix":
        parameter_by_name = {entry.get("name"): entry for entry in parameters if entry.get("name")}
        ordered_parameters = []
        if "Jiso" in parameter_by_name:
            ordered_parameters.append(parameter_by_name["Jiso"])
        for name in ("Gamma_xy", "Gamma_xz", "Gamma_yz"):
            if name in parameter_by_name:
                ordered_parameters.append(parameter_by_name[name])
        if "Jiso" in parameter_by_name and len(ordered_parameters) >= 2:
            return {
                "view_kind": "symmetric_exchange_matrix_jiso_gamma",
                "parameters": ordered_parameters,
                "physical_label": physical_label or "symmetric exchange matrix (Jiso/Gamma)",
            }

    if block.get("type") == "quadrupole_coupling" and parameters:
        return {
            "view_kind": "quadrupole_coupling_components",
            "parameters": list(parameters),
            "physical_label": physical_label or "quadrupolar coupling components",
        }

    if block.get("type") == "higher_multipole_coupling" and parameters:
        rank = block.get("multipole_rank")
        if rank is not None:
            return {
                "view_kind": f"higher_multipole_coupling_rank_{rank}_components",
                "parameters": list(parameters),
                "physical_label": physical_label or f"rank-{rank} multipole coupling components",
            }

    return None


def _shell_entry(block):
    entry = {
        "family": block.get("family"),
        "type": block.get("type"),
    }
    if block.get("type") == "xxz_exchange":
        entry["coefficient_xy"] = block.get("coefficient_xy")
        entry["coefficient_z"] = block.get("coefficient_z")
    elif block.get("type") in {"isotropic_exchange", "dm_like", "pseudospin_exchange", "orbital_exchange"}:
        entry["coefficient"] = block.get("coefficient")
    elif block.get("type") in {"symmetric_exchange_matrix", "exchange_tensor"}:
        entry["matrix"] = block.get("matrix")
    elif block.get("type") in {"quadrupole_coupling", "higher_multipole_coupling"}:
        pass
    else:
        return None
    for optional_key in (
        "shell_index",
        "distance",
        "shell_label",
        "coordinate_frame",
        "axis_labels",
        "planar_axes",
        "longitudinal_axis",
        "physical_label",
        "physical_label_aliases",
        "physical_tendency",
        "dominant_channel_label",
        "physical_parameter_view",
        "additional_physical_parameter_views",
        "human_summary",
        "human_parameters",
        "matrix_axes",
        "resolved_coordinate_frame",
        "resolved_axis_labels",
        "resolved_planar_axes",
        "resolved_longitudinal_axis",
        "resolved_matrix_axes",
        "resolved_matrix",
        "multipole_family",
        "multipole_rank",
        "term_count",
        "dominant_component",
        "dominant_coefficient",
        "components",
    ):
        if optional_key in block:
            entry[optional_key] = block.get(optional_key)
    derived_view = _derive_physical_parameter_view(block)
    if derived_view is not None and "physical_parameter_view" not in entry:
        entry["physical_parameter_view"] = derived_view
    if derived_view is not None and "physical_label" not in entry:
        entry["physical_label"] = derived_view.get("physical_label")
    return entry


def _shell_entry_priority(entry):
    block_type = entry.get("type")
    if block_type in {
        "isotropic_exchange",
        "xxz_exchange",
        "dm_like",
        "pseudospin_exchange",
        "orbital_exchange",
        "symmetric_exchange_matrix",
        "exchange_tensor",
    }:
        return 0
    if block_type == "quadrupole_coupling":
        return 1
    if block_type == "higher_multipole_coupling":
        return 2
    return 99


def _append_secondary_views(target, candidate_views, seen_view_kinds):
    for view in list(candidate_views or []):
        if not isinstance(view, dict):
            continue
        view_kind = view.get("view_kind")
        if not view_kind or view_kind in seen_view_kinds:
            continue
        target.append(view)
        seen_view_kinds.add(view_kind)


def _merge_shell_family_entries(entries):
    ordered_entries = list(entries)
    ordered_entries.sort(key=_shell_entry_priority)
    primary = dict(ordered_entries[0])
    additional_views = list(primary.get("additional_physical_parameter_views") or [])
    seen_view_kinds = {
        view.get("view_kind")
        for view in additional_views
        if isinstance(view, dict) and view.get("view_kind")
    }

    for entry in ordered_entries[1:]:
        physical_view = entry.get("physical_parameter_view")
        if isinstance(physical_view, dict):
            _append_secondary_views(additional_views, [physical_view], seen_view_kinds)
        _append_secondary_views(
            additional_views,
            entry.get("additional_physical_parameter_views") or [],
            seen_view_kinds,
        )

    if additional_views:
        primary["additional_physical_parameter_views"] = additional_views
    return primary


def _shell_resolved_exchange_block(blocks):
    family_entries = defaultdict(list)
    for block in blocks:
        family = block.get("family")
        if family is None:
            continue
        entry = _shell_entry(block)
        if entry is not None:
            family_entries[family].append(entry)

    shell_entries = [_merge_shell_family_entries(entries) for entries in family_entries.values()]
    if len(shell_entries) < 2:
        return None
    shell_entries.sort(key=lambda item: _shell_sort_key(item["family"], item.get("shell_index")))
    return {
        "type": "shell_resolved_exchange",
        "shells": shell_entries,
        "source_terms": list(blocks),
    }


def _summarize_terms_by_multipole(terms):
    grouped = defaultdict(list)
    for term in terms:
        family = term.get("multipole_family") or term.get("family") or "unspecified"
        rank = term.get("multipole_rank")
        body_order = term.get("body_order")
        grouped[(family, rank, body_order)].append(term)

    summary = []
    for (family, rank, body_order), grouped_terms in grouped.items():
        max_abs = max(abs(term.get("coefficient", 0.0)) for term in grouped_terms)
        summary.append(
            {
                "multipole_family": family,
                "multipole_rank": rank,
                "body_order": body_order,
                "term_count": len(grouped_terms),
                "max_abs_coefficient": max_abs,
            }
        )

    summary.sort(
        key=lambda entry: (
            -entry.get("max_abs_coefficient", 0.0),
            -(entry.get("body_order") or 0),
            -(entry.get("multipole_rank") or 0),
            str(entry.get("multipole_family") or ""),
        )
    )
    return summary


def assemble_effective_model(readable_model, low_weight_threshold=0.1):
    main_blocks = list(readable_model.get("blocks", []))
    shell_block = _shell_resolved_exchange_block(main_blocks)
    if shell_block is not None:
        main_blocks = list(main_blocks) + [shell_block]

    assembled = {
        "main": main_blocks,
        "low_weight": [],
        "residual": [],
        "residual_summary": [],
        "low_weight_summary": [],
    }

    for term in readable_model.get("residual_terms", []):
        if term.get("relative_weight", 0.0) < low_weight_threshold:
            flagged = dict(term)
            if term.get("symmetry_annotations"):
                flagged["warning"] = (
                    "Low-weight term carries symmetry-breaking annotations: "
                    + ", ".join(term["symmetry_annotations"])
                )
            assembled["low_weight"].append(flagged)
        else:
            assembled["residual"].append(term)

    assembled["residual_summary"] = _summarize_terms_by_multipole(assembled["residual"])
    assembled["low_weight_summary"] = _summarize_terms_by_multipole(assembled["low_weight"])

    return assembled


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(assemble_effective_model(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
