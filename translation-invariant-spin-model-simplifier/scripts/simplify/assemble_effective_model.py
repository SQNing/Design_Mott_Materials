#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _shell_sort_key(label):
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
    else:
        return None
    for optional_key in (
        "coordinate_frame",
        "axis_labels",
        "planar_axes",
        "longitudinal_axis",
        "physical_label",
        "physical_label_aliases",
        "physical_tendency",
        "dominant_channel_label",
        "physical_parameter_view",
        "human_summary",
        "human_parameters",
        "matrix_axes",
        "resolved_coordinate_frame",
        "resolved_axis_labels",
        "resolved_planar_axes",
        "resolved_longitudinal_axis",
        "resolved_matrix_axes",
        "resolved_matrix",
    ):
        if optional_key in block:
            entry[optional_key] = block.get(optional_key)
    derived_view = _derive_physical_parameter_view(block)
    if derived_view is not None and "physical_parameter_view" not in entry:
        entry["physical_parameter_view"] = derived_view
    if derived_view is not None and "physical_label" not in entry:
        entry["physical_label"] = derived_view.get("physical_label")
    return entry


def _shell_resolved_exchange_block(blocks):
    shell_entries = []
    for block in blocks:
        family = block.get("family")
        if family is None:
            continue
        entry = _shell_entry(block)
        if entry is not None:
            shell_entries.append(entry)
    if len(shell_entries) < 2:
        return None
    shell_entries.sort(key=lambda item: _shell_sort_key(item["family"]))
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
