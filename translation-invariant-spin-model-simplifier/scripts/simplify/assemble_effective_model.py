#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def _load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _shell_sort_key(label):
    text = str(label)
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return (0, int(digits), text)
    return (1, text)


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


def assemble_effective_model(readable_model, low_weight_threshold=0.1):
    main_blocks = list(readable_model.get("blocks", []))
    shell_block = _shell_resolved_exchange_block(main_blocks)
    if shell_block is not None:
        main_blocks = list(main_blocks) + [shell_block]

    assembled = {
        "main": main_blocks,
        "low_weight": [],
        "residual": [],
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

    return assembled


def main():
    payload = _load_payload(sys.argv[1]) if len(sys.argv) > 1 else json.load(sys.stdin)
    print(json.dumps(assemble_effective_model(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
