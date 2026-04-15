#!/usr/bin/env python3

import heapq
import itertools

from .progress import ProgressReporter


def _make_item(result):
    priority = float(result.get("_queue_priority", result["lower_bound"]))
    return (
        float(priority),
        float(result["lower_bound"]),
        next(_make_item.counter),
        result,
    )


_make_item.counter = itertools.count()


def _dominant_label(counter):
    if not counter:
        return None
    items = [(str(label), float(value)) for label, value in counter.items() if float(value) > 0.0]
    if not items:
        return None
    items.sort(key=lambda item: (-item[1], item[0]))
    return items[0][0]


def _online_focus(evaluated_results, split_axes, axis_names):
    axis_counts = {}
    for axis in split_axes:
        axis = int(axis)
        if 0 <= axis < len(axis_names):
            label = str(axis_names[axis])
        else:
            label = f"axis_{axis}"
        axis_counts[label] = axis_counts.get(label, 0.0) + 1.0

    channel_totals = {}
    branch_counts = {}
    for result in evaluated_results:
        branch_kind = result.get("branch_kind")
        if branch_kind is not None:
            branch_label = str(branch_kind)
            branch_counts[branch_label] = branch_counts.get(branch_label, 0.0) + 1.0
        for diagnostic in result.get("split_axis_diagnostics", []):
            channel_label = str(diagnostic.get("channel", "generic"))
            channel_totals[channel_label] = channel_totals.get(channel_label, 0.0) + float(
                diagnostic.get("projected_gap_reduction", 0.0)
            )

    return {
        "focus_axis": _dominant_label(axis_counts),
        "focus_channel": _dominant_label(channel_totals),
        "focus_branch": _dominant_label(branch_counts),
    }


def _channel_totals(evaluated_results):
    totals = {}
    for result in evaluated_results:
        for diagnostic in result.get("split_axis_diagnostics", []):
            channel_label = str(diagnostic.get("channel", "generic"))
            totals[channel_label] = totals.get(channel_label, 0.0) + float(
                diagnostic.get("projected_gap_reduction", 0.0)
            )
    return totals


def _axis_totals(evaluated_results, *, channel=None):
    totals = {}
    for result in evaluated_results:
        for diagnostic in result.get("split_axis_diagnostics", []):
            axis = int(diagnostic.get("axis", -1))
            if axis < 0:
                continue
            channel_label = str(diagnostic.get("channel", "generic"))
            if channel is not None and channel_label != str(channel):
                continue
            totals[axis] = totals.get(axis, 0.0) + float(
                diagnostic.get("projected_gap_reduction", 0.0)
            )
    return totals


def _local_channel_totals(result):
    totals = {}
    for diagnostic in result.get("split_axis_diagnostics", []):
        channel_label = str(diagnostic.get("channel", "generic"))
        totals[channel_label] = totals.get(channel_label, 0.0) + float(
            diagnostic.get("projected_gap_reduction", 0.0)
        )
    return totals


def _local_axis_total(result, axis, *, channel=None):
    total = 0.0
    for diagnostic in result.get("split_axis_diagnostics", []):
        if int(diagnostic.get("axis", -1)) != int(axis):
            continue
        channel_label = str(diagnostic.get("channel", "generic"))
        if channel is not None and channel_label != str(channel):
            continue
        total += float(diagnostic.get("projected_gap_reduction", 0.0))
    return float(total)


def _queue_priority_payload(result, evaluated_results):
    lower_bound = float(result["lower_bound"])
    upper_bound = float(result.get("upper_bound", lower_bound))
    diagnostics = result.get("split_axis_diagnostics")
    if not isinstance(diagnostics, (list, tuple)) or not diagnostics:
        return {
            "priority": float(lower_bound),
            "priority_bonus": 0.0,
            "channel_pressure": 0.0,
            "axis_pressure": 0.0,
            "dominant_channel": None,
            "dominant_axis": None,
        }

    history_channel_totals = _channel_totals(evaluated_results)
    dominant_channel = _dominant_label(history_channel_totals)
    if dominant_channel is None:
        return {
            "priority": float(lower_bound),
            "priority_bonus": 0.0,
            "channel_pressure": 0.0,
            "axis_pressure": 0.0,
            "dominant_channel": None,
            "dominant_axis": None,
        }

    history_axis_totals = _axis_totals(evaluated_results, channel=dominant_channel)
    dominant_axis = None
    if history_axis_totals:
        dominant_axis = max(
            history_axis_totals,
            key=lambda axis: (float(history_axis_totals[axis]), -int(axis)),
        )

    local_channel_totals = _local_channel_totals(result)
    local_total = float(sum(local_channel_totals.values()))
    local_dominant_channel_total = float(local_channel_totals.get(dominant_channel, 0.0))
    if local_total <= 0.0 or local_dominant_channel_total <= 0.0:
        return {
            "priority": float(lower_bound),
            "priority_bonus": 0.0,
            "channel_pressure": 0.0,
            "axis_pressure": 0.0,
            "dominant_channel": str(dominant_channel),
            "dominant_axis": int(dominant_axis) if dominant_axis is not None else None,
        }

    channel_alignment = local_dominant_channel_total / local_total
    axis_alignment = 0.0
    if dominant_axis is not None:
        axis_alignment = _local_axis_total(
            result,
            dominant_axis,
            channel=dominant_channel,
        ) / local_dominant_channel_total

    gap = max(0.0, upper_bound - lower_bound)
    channel_pressure = gap * (0.30 * channel_alignment)
    axis_pressure = gap * (0.25 * axis_alignment)
    priority_bonus = channel_pressure + axis_pressure
    return {
        "priority": float(lower_bound - priority_bonus),
        "priority_bonus": float(priority_bonus),
        "channel_pressure": float(channel_pressure),
        "axis_pressure": float(axis_pressure),
        "dominant_channel": str(dominant_channel),
        "dominant_axis": int(dominant_axis) if dominant_axis is not None else None,
    }


def _apply_queue_priority(result, evaluated_results):
    payload = _queue_priority_payload(result, evaluated_results)
    result["_queue_priority"] = float(payload["priority"])
    result["_queue_priority_details"] = dict(payload)
    return result


def _accumulate_priority_pressure(statistics, result, axis_names):
    details = result.get("_queue_priority_details", {})
    channel_pressure = float(details.get("channel_pressure", 0.0))
    axis_pressure = float(details.get("axis_pressure", 0.0))
    dominant_channel = details.get("dominant_channel")
    dominant_axis = details.get("dominant_axis")
    if channel_pressure > 0.0 and dominant_channel is not None:
        bucket = statistics["priority_pressure_by_channel"]
        bucket[str(dominant_channel)] = bucket.get(str(dominant_channel), 0.0) + channel_pressure
    if axis_pressure > 0.0 and dominant_axis is not None:
        if 0 <= int(dominant_axis) < len(axis_names):
            axis_name = str(axis_names[int(dominant_axis)])
        else:
            axis_name = f"axis_{int(dominant_axis)}"
        bucket = statistics["priority_pressure_by_axis"]
        bucket[axis_name] = bucket.get(axis_name, 0.0) + axis_pressure


def _rebuild_queue(queue, evaluated_results):
    previous_order = [item[2] for item in sorted(queue)]
    natural_order = [item[2] for item in sorted(queue, key=lambda item: (float(item[1]), int(item[2])))]
    rebuilt = []
    for _, _, sequence, result in queue:
        _apply_queue_priority(result, evaluated_results)
        rebuilt.append(
            (
                float(result["_queue_priority"]),
                float(result["lower_bound"]),
                sequence,
                result,
            )
        )
    heapq.heapify(rebuilt)
    rebuilt_order = [item[2] for item in sorted(rebuilt)]
    reordered = len(rebuilt_order) > 1 and (
        previous_order != rebuilt_order or rebuilt_order != natural_order
    )
    return rebuilt, reordered


def _channel_biased_scores(result, evaluated_results):
    scores = result.get("split_axis_scores")
    if not isinstance(scores, (list, tuple)) or not scores:
        return None
    diagnostics = result.get("split_axis_diagnostics")
    if not isinstance(diagnostics, (list, tuple)) or not diagnostics:
        return [float(score) for score in scores]
    totals = _channel_totals(evaluated_results)
    dominant_channel = _dominant_label(totals)
    total_weight = float(sum(totals.values()))
    if dominant_channel is None or total_weight <= 0.0:
        return [float(score) for score in scores]
    dominant_weight = float(totals.get(dominant_channel, 0.0))
    dominance_fraction = dominant_weight / total_weight
    axis_totals = _axis_totals(evaluated_results, channel=dominant_channel)
    dominant_axis = None
    dominant_axis_weight = 0.0
    if axis_totals:
        dominant_axis = max(
            axis_totals,
            key=lambda axis: (float(axis_totals[axis]), -int(axis)),
        )
        dominant_axis_weight = float(axis_totals[dominant_axis])
    dominant_channel_total = float(sum(axis_totals.values()))
    channel_by_axis = {}
    for diagnostic in diagnostics:
        axis = int(diagnostic.get("axis", -1))
        if axis < 0:
            continue
        channel_by_axis[axis] = str(diagnostic.get("channel", "generic"))
    biased = []
    for index, score in enumerate(scores):
        effective = float(score)
        if channel_by_axis.get(index) == dominant_channel:
            effective *= 1.0 + 0.35 * dominance_fraction
            if (
                dominant_axis is not None
                and int(index) == int(dominant_axis)
                and dominant_channel_total > 0.0
            ):
                effective *= 1.0 + 0.3 * (dominant_axis_weight / dominant_channel_total)
        biased.append(float(effective))
    return biased


def _resolved_split_axis(result, box, *, evaluated_results=None):
    split_axis_hint = result.get("split_axis_hint")
    if split_axis_hint is not None:
        return int(split_axis_hint)
    biased_scores = _channel_biased_scores(result, evaluated_results or [])
    if biased_scores:
        return max(range(len(biased_scores)), key=lambda index: (float(biased_scores[index]), -index))
    return box.widest_dimension()


def run_branch_and_bound(
    evaluator,
    root_box,
    *,
    tolerance=1.0e-3,
    box_budget=64,
    reporter=None,
    stage="branch-and-bound",
):
    reporter = reporter or ProgressReporter()
    axis_names = list(getattr(root_box, "names", []))
    statistics = {
        "processed_boxes": 0,
        "pruned_boxes": 0,
        "retained_boxes": 0,
        "split_boxes": 0,
        "max_queue_size": 0,
        "split_axes": [],
        "queue_reorders_triggered": 0,
        "priority_pressure_by_axis": {},
        "priority_pressure_by_channel": {},
    }
    queue = []
    root_result = dict(evaluator(root_box))
    _apply_queue_priority(root_result, [root_result])
    _accumulate_priority_pressure(statistics, root_result, axis_names)
    heapq.heappush(queue, _make_item(root_result))
    statistics["max_queue_size"] = max(statistics["max_queue_size"], len(queue))
    global_upper = float(root_result["upper_bound"])
    best_box = dict(root_result)
    completed_boxes = []
    active_results = [root_result]

    while queue and statistics["processed_boxes"] < int(box_budget):
        _, _, _, result = heapq.heappop(queue)
        statistics["processed_boxes"] += 1
        current_lower = float(result["lower_bound"])
        current_upper = float(result["upper_bound"])
        if current_upper < global_upper:
            global_upper = current_upper
            best_box = dict(result)
        if current_lower > global_upper + float(tolerance):
            statistics["pruned_boxes"] += 1
            completed_boxes.append({**result, "status": "pruned"})
            focus = _online_focus(active_results, statistics["split_axes"], axis_names)
            reporter.emit(
                stage=stage,
                processed=statistics["processed_boxes"],
                queued=len(queue),
                lower_bound=current_lower,
                upper_bound=global_upper,
                depth=result["box"].get("depth", 0),
                reason="pruned",
                **focus,
            )
            continue

        if current_upper - current_lower <= float(tolerance):
            statistics["retained_boxes"] += 1
            completed_boxes.append({**result, "status": "retained"})
            focus = _online_focus(active_results, statistics["split_axes"], axis_names)
            reporter.emit(
                stage=stage,
                processed=statistics["processed_boxes"],
                queued=len(queue),
                lower_bound=current_lower,
                upper_bound=global_upper,
                depth=result["box"].get("depth", 0),
                reason="retained",
                **focus,
            )
            continue

        from .boxes import ParameterBox

        box = ParameterBox(**result["box"])
        split_axis = _resolved_split_axis(result, box, evaluated_results=active_results)
        left, right = box.split(axis=split_axis)
        statistics["split_boxes"] += 1
        statistics["split_axes"].append(int(split_axis))
        focus = _online_focus(active_results, statistics["split_axes"], axis_names)
        reporter.emit(
            stage=stage,
            processed=statistics["processed_boxes"],
            queued=len(queue),
            lower_bound=current_lower,
            upper_bound=global_upper,
            depth=result["box"].get("depth", 0),
            reason="split",
            **focus,
        )
        for child in (left, right):
            child_result = dict(evaluator(child))
            _apply_queue_priority(child_result, active_results)
            _accumulate_priority_pressure(statistics, child_result, axis_names)
            heapq.heappush(queue, _make_item(child_result))
            active_results.append(child_result)
            statistics["max_queue_size"] = max(statistics["max_queue_size"], len(queue))
        queue, reordered = _rebuild_queue(queue, active_results)
        if reordered:
            statistics["queue_reorders_triggered"] += 1
        for _, _, _, queued_result in queue:
            _accumulate_priority_pressure(statistics, queued_result, axis_names)

    frontier = [
        item[3] for item in queue
    ] + [entry for entry in completed_boxes if entry.get("status") == "retained"]
    if frontier:
        global_lower = min(float(entry["lower_bound"]) for entry in frontier)
    else:
        global_lower = float(best_box["lower_bound"])

    if queue:
        stopping_reason = "box_budget_reached"
    elif global_upper - global_lower <= float(tolerance):
        stopping_reason = "gap_within_tolerance"
    else:
        stopping_reason = "search_exhausted"

    return {
        "global_lower_bound": float(global_lower),
        "global_upper_bound": float(global_upper),
        "best_box": dict(best_box),
        "evaluated_boxes": [dict(entry) for entry in active_results],
        "boxes": list(completed_boxes) + [item[3] for item in queue],
        "statistics": statistics,
        "status": "certified" if global_upper - global_lower <= float(tolerance) else "inconclusive",
        "stopping_reason": stopping_reason,
    }
