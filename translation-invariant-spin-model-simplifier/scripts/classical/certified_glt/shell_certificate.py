#!/usr/bin/env python3


def _dominant_key(mapping):
    if not mapping:
        return None
    items = [(str(key), float(value)) for key, value in mapping.items() if float(value) > 0.0]
    if not items:
        return None
    items.sort(key=lambda item: (-item[1], item[0]))
    return items[0][0]


def _dominant_channel_for_entry(entry):
    channel_totals = {}
    for diagnostic in entry.get("split_axis_diagnostics", []):
        channel_name = str(diagnostic.get("channel", "generic"))
        projected_gap_reduction = float(diagnostic.get("projected_gap_reduction", 0.0))
        channel_totals[channel_name] = channel_totals.get(channel_name, 0.0) + projected_gap_reduction
    return _dominant_key(channel_totals)


def _blocking_reason_for_entry(entry):
    branch_kind = str(entry.get("branch_kind", "generic"))
    dominant_channel = _dominant_channel_for_entry(entry)
    if branch_kind == "mixed":
        return "mixed_branch_competition"
    if dominant_channel == "uniform":
        return "uniform_weight_uncertainty"
    if dominant_channel == "nonzero_q":
        return "nonzero_q_dispersion_uncertainty"
    return "generic_uncertainty"


def _unresolved_pressure_summary(unresolved_entries, statistics):
    unresolved_axis = {}
    unresolved_channel = {}
    blocking_reason_counts = {}
    for entry in unresolved_entries:
        blocking_reason = _blocking_reason_for_entry(entry)
        blocking_reason_counts[blocking_reason] = blocking_reason_counts.get(blocking_reason, 0.0) + 1.0
        for diagnostic in entry.get("split_axis_diagnostics", []):
            axis_name = str(
                diagnostic.get(
                    "name",
                    f"axis_{int(diagnostic.get('axis', -1))}",
                )
            )
            channel_name = str(diagnostic.get("channel", "generic"))
            projected_gap_reduction = float(diagnostic.get("projected_gap_reduction", 0.0))
            unresolved_axis[axis_name] = unresolved_axis.get(axis_name, 0.0) + projected_gap_reduction
            unresolved_channel[channel_name] = unresolved_channel.get(channel_name, 0.0) + projected_gap_reduction

    priority_axis = {
        str(name): float(value)
        for name, value in dict(statistics.get("priority_pressure_by_axis", {})).items()
    }
    priority_channel = {
        str(name): float(value)
        for name, value in dict(statistics.get("priority_pressure_by_channel", {})).items()
    }
    dominant_axis = _dominant_key(unresolved_axis) or _dominant_key(priority_axis)
    dominant_channel = _dominant_key(unresolved_channel) or _dominant_key(priority_channel)
    return {
        "dominant_axis": dominant_axis,
        "dominant_channel": dominant_channel,
        "unresolved_gap_pressure_by_axis": {
            str(name): float(value) for name, value in sorted(unresolved_axis.items())
        },
        "unresolved_gap_pressure_by_channel": {
            str(name): float(value) for name, value in sorted(unresolved_channel.items())
        },
        "priority_pressure_by_axis": {
            str(name): float(value) for name, value in sorted(priority_axis.items())
        },
        "priority_pressure_by_channel": {
            str(name): float(value) for name, value in sorted(priority_channel.items())
        },
        "blocking_reason_counts": {
            str(name): int(value) for name, value in sorted(blocking_reason_counts.items())
        },
        "dominant_blocking_reason": _dominant_key(blocking_reason_counts),
        "queue_reorders_triggered": int(statistics.get("queue_reorders_triggered", 0)),
    }


def build_shell_certificate(search_result, *, shell_tolerance=5.0e-2):
    window = float(search_result["global_upper_bound"]) + float(shell_tolerance)
    cover_boxes = []
    excluded_boxes = []
    unresolved_boxes = []
    unresolved_entries = []
    unresolved_box_diagnostics = []
    for entry in search_result.get("boxes", []):
        lower = float(entry["lower_bound"])
        upper = float(entry["upper_bound"])
        payload = dict(entry.get("box", {}))
        if upper <= window:
            cover_boxes.append(payload)
        elif lower > window:
            excluded_boxes.append(payload)
        else:
            unresolved_boxes.append(payload)
            entry_payload = dict(entry)
            unresolved_entries.append(entry_payload)
            unresolved_box_diagnostics.append(
                {
                    "box": payload,
                    "branch_kind": entry_payload.get("branch_kind"),
                    "blocking_reason": _blocking_reason_for_entry(entry_payload),
                }
            )
    status = "certified" if cover_boxes or excluded_boxes else "inconclusive"
    return {
        "status": status,
        "shell_tolerance": float(shell_tolerance),
        "cover_boxes": cover_boxes,
        "excluded_boxes": excluded_boxes,
        "unresolved_boxes": unresolved_boxes,
        "unresolved_box_diagnostics": unresolved_box_diagnostics,
        "unresolved_pressure_summary": _unresolved_pressure_summary(
            unresolved_entries,
            dict(search_result.get("statistics", {})),
        ),
    }
