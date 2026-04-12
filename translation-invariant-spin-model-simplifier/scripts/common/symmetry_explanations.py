#!/usr/bin/env python3


def _format_symmetry_list(symmetries):
    return ", ".join(symmetries) if symmetries else "none"


def _cross_axis_labels(payload):
    labels = []
    canonical_model = payload.get("canonical_model", {}) if isinstance(payload, dict) else {}
    for term in canonical_model.get("two_body", []):
        label = str(term.get("canonical_label", ""))
        if label in {"Sx@0 Sz@1", "Sz@0 Sx@1", "Sx@1 Sz@0", "Sz@1 Sx@0"}:
            labels.append(label)
    for term in payload.get("effective_model", {}).get("low_weight", []):
        label = str(term.get("canonical_label", ""))
        if label and label not in labels and "Sx@" in label and "Sz@" in label:
            labels.append(label)
    return labels


def summarize_symmetry_interpretation(payload):
    detected = list(payload.get("detected_symmetries", [])) if isinstance(payload, dict) else []
    lines = []
    lines.append(f"detected={_format_symmetry_list(detected)}")

    ruled_out = []
    reasons = []
    cross_axis_labels = _cross_axis_labels(payload)
    if cross_axis_labels:
        ruled_out.extend(["su2_spin", "u1_spin"])
        reasons.append(
            f"cross-axis coupling {cross_axis_labels[0]} remains in the model, so spin-rotation symmetries are treated as broken"
        )

    if ruled_out:
        lines.append(f"ruled_out={_format_symmetry_list(ruled_out)}")
    if reasons:
        lines.extend(reasons)
    return lines
