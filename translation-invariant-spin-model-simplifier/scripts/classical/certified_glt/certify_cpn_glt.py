#!/usr/bin/env python3

from collections import Counter

from .branch_and_bound import run_branch_and_bound
from .heuristic_bridge import build_heuristic_seed
from .lift_certificate import classify_lift_result
from .progress import ProgressReporter
from .projector_certificate import certify_projector_collection
from .relaxed_bounds import build_search_box, evaluate_relaxed_box, refine_candidate_upper_bound
from .shell_certificate import build_shell_certificate


def _deserialize_complex(value):
    if isinstance(value, dict):
        return complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    return complex(value)


def _deserialize_projector_matrices(serialized):
    matrices = []
    for matrix in serialized or []:
        matrices.append([[_deserialize_complex(value) for value in row] for row in matrix])
    return matrices


def _dominant_key(counter_like):
    if not counter_like:
        return None
    items = list(counter_like.items())
    items = [item for item in items if float(item[1]) > 0.0]
    if not items:
        return None
    items.sort(key=lambda item: (-float(item[1]), str(item[0])))
    return str(items[0][0])


def _search_axis_names(search_result):
    best_box = search_result.get("best_box", {})
    names = best_box.get("box", {}).get("names")
    if names:
        return [str(name) for name in names]
    evaluated = search_result.get("evaluated_boxes", [])
    for entry in evaluated:
        names = entry.get("box", {}).get("names")
        if names:
            return [str(name) for name in names]
    return []


def _best_box_axis_window(best_box, target_axis):
    box_payload = dict(best_box.get("box", {}))
    names = list(box_payload.get("names", []))
    lower = list(box_payload.get("lower", []))
    upper = list(box_payload.get("upper", []))
    if target_axis in names:
        index = names.index(target_axis)
        return {
            "lower": float(lower[index]),
            "upper": float(upper[index]),
            "depth": int(box_payload.get("depth", 0)),
        }
    return {"depth": int(box_payload.get("depth", 0))}


def _base_action(shell_pressure_summary, best_box, heuristic_seed):
    summary = dict(shell_pressure_summary or {})
    best_box = dict(best_box or {})
    heuristic_seed = dict(heuristic_seed or {})
    target_axis = summary.get("dominant_axis") or summary.get("dominant_queue_pressure_axis")
    return {
        "blocking_reason": summary.get("dominant_blocking_reason"),
        "target_axis": target_axis,
        "target_box": _best_box_axis_window(best_box, target_axis) if target_axis else _best_box_axis_window(best_box, None),
        "seed_q_vector": list(heuristic_seed.get("q_vector", [0.0, 0.0, 0.0])),
        "seed_p_weights": list(heuristic_seed.get("p_weights", [1.0])),
    }


def _suggested_knobs(kind, *, target_axis=None):
    knobs = {
        "box_budget_multiplier": 1.5,
        "axis_refinement_factor": 1,
        "preferred_resolution": "generic",
    }
    if kind == "refine_log_p_axis":
        knobs.update(
            {
                "box_budget_multiplier": 2.0,
                "axis_refinement_factor": 2,
                "preferred_resolution": "log_p",
                "target_axis": target_axis,
            }
        )
    elif kind == "refine_q_axis":
        knobs.update(
            {
                "box_budget_multiplier": 2.0,
                "axis_refinement_factor": 2,
                "preferred_resolution": "nonzero_q",
                "target_axis": target_axis,
            }
        )
    elif kind == "increase_branch_resolution":
        knobs.update(
            {
                "box_budget_multiplier": 2.0,
                "axis_refinement_factor": 1,
                "preferred_resolution": "mixed_branch",
                "depth_increment": 1,
            }
        )
    elif kind == "certificate_already_tight":
        knobs.update(
            {
                "box_budget_multiplier": 1.0,
                "axis_refinement_factor": 1,
                "preferred_resolution": "none",
            }
        )
    return knobs


def _suggested_run_config(current_run_config, suggested_knobs, *, target_axis=None):
    config = dict(current_run_config or {})
    box_budget = int(config.get("box_budget", 32))
    multiplier = float(suggested_knobs.get("box_budget_multiplier", 1.0))
    suggested_budget = max(box_budget, int(round(box_budget * multiplier)))
    return {
        "box_budget": int(suggested_budget),
        "tolerance": float(config.get("tolerance", 1.0e-3)),
        "shell_tolerance": float(config.get("shell_tolerance", 5.0e-2)),
        "supercell_cutoff": int(config.get("supercell_cutoff", 4)),
        "weight_bound": float(config.get("weight_bound", 1.0)),
        "focus_axis": target_axis,
        "preferred_resolution": str(suggested_knobs.get("preferred_resolution", "generic")),
        "axis_refinement_factor": int(suggested_knobs.get("axis_refinement_factor", 1)),
    }


def _suggested_python_call(run_config):
    config = dict(run_config or {})
    return "\n".join(
        [
            "from classical.certified_glt.certify_cpn_glt import certify_cpn_generalized_lt",
            "",
            "# Reuse your current model payload here.",
            "rerun_config = {",
            f"    'box_budget': {int(config.get('box_budget', 32))},",
            f"    'tolerance': {float(config.get('tolerance', 1.0e-3))!r},",
            f"    'shell_tolerance': {float(config.get('shell_tolerance', 5.0e-2))!r},",
            f"    'supercell_cutoff': {int(config.get('supercell_cutoff', 4))},",
            f"    'weight_bound': {float(config.get('weight_bound', 1.0))!r},",
            f"    'focus_axis': {config.get('focus_axis')!r},",
            f"    'preferred_resolution': {config.get('preferred_resolution')!r},",
            f"    'axis_refinement_factor': {int(config.get('axis_refinement_factor', 1))},",
            "}",
            "",
            "result = certify_cpn_generalized_lt(",
            "    model,",
            "    box_budget=rerun_config['box_budget'],",
            "    tolerance=rerun_config['tolerance'],",
            "    shell_tolerance=rerun_config['shell_tolerance'],",
            "    supercell_cutoff=rerun_config['supercell_cutoff'],",
            "    weight_bound=rerun_config['weight_bound'],",
            ")",
        ]
    )


def _recommend_next_actions(shell_pressure_summary, best_box, heuristic_seed, current_run_config=None):
    summary = dict(shell_pressure_summary or {})
    dominant_channel = summary.get("dominant_channel")
    blocking_reason = summary.get("dominant_blocking_reason")
    target_axis = summary.get("dominant_axis") or summary.get("dominant_queue_pressure_axis")
    base = _base_action(summary, best_box, heuristic_seed)
    candidates = []

    if blocking_reason == "uniform_weight_uncertainty" and isinstance(target_axis, str) and target_axis.startswith("log_p"):
        candidates.append(
            {
                **base,
                "kind": "refine_log_p_axis",
                "message": f"Prioritize tighter weight-space subdivision around {target_axis}.",
                "suggested_knobs": _suggested_knobs("refine_log_p_axis", target_axis=target_axis),
            }
        )
    elif blocking_reason == "nonzero_q_dispersion_uncertainty" and isinstance(target_axis, str) and target_axis.startswith("q"):
        candidates.append(
            {
                **base,
                "kind": "refine_q_axis",
                "message": f"Prioritize finer nonzero-q resolution along {target_axis}.",
                "suggested_knobs": _suggested_knobs("refine_q_axis", target_axis=target_axis),
            }
        )
    elif blocking_reason == "mixed_branch_competition":
        candidates.append(
            {
                **base,
                "kind": "increase_branch_resolution",
                "message": "Prioritize additional branch-and-bound resolution where uniform and nonzero-q branches compete.",
                "suggested_knobs": _suggested_knobs("increase_branch_resolution", target_axis=target_axis),
            }
        )
    elif blocking_reason is None and dominant_channel is None:
        candidates.append(
            {
                **base,
                "kind": "certificate_already_tight",
                "message": "No dominant unresolved pressure remains; the current certificate is already tight.",
                "suggested_knobs": _suggested_knobs("certificate_already_tight", target_axis=target_axis),
            }
        )
    else:
        candidates.append(
            {
                **base,
                "kind": "inspect_generic_uncertainty",
                "message": "Inspect the dominant unresolved axis/channel and refine the corresponding search window.",
                "suggested_knobs": _suggested_knobs("inspect_generic_uncertainty", target_axis=target_axis),
            }
        )

    if dominant_channel == "uniform":
        candidates.append(
            {
                **base,
                "kind": "refine_log_p_axis",
                "message": "As a backup move, refine the dominant log-weight direction more aggressively.",
                "suggested_knobs": _suggested_knobs("refine_log_p_axis", target_axis=target_axis),
            }
        )
    if dominant_channel == "nonzero_q":
        candidates.append(
            {
                **base,
                "kind": "refine_q_axis",
                "message": "As a backup move, increase nonzero-q resolution around the dominant q direction.",
                "suggested_knobs": _suggested_knobs("refine_q_axis", target_axis=target_axis),
            }
        )
    if blocking_reason != "mixed_branch_competition":
        candidates.append(
            {
                **base,
                "kind": "increase_branch_resolution",
                "message": "As a fallback, allow deeper branch-and-bound refinement near the current best box.",
                "suggested_knobs": _suggested_knobs("increase_branch_resolution", target_axis=target_axis),
            }
        )
    candidates.append(
        {
            **base,
            "kind": "inspect_generic_uncertainty",
            "message": "Inspect the current best box diagnostics manually if automated refinement remains inconclusive.",
            "suggested_knobs": _suggested_knobs("inspect_generic_uncertainty", target_axis=target_axis),
        }
    )

    deduped = []
    seen = set()
    for candidate in candidates:
        key = (candidate["kind"], candidate.get("target_axis"))
        if key in seen:
            continue
        seen.add(key)
        candidate["suggested_run_config"] = _suggested_run_config(
            current_run_config,
            dict(candidate.get("suggested_knobs", {})),
            target_axis=candidate.get("target_axis"),
        )
        candidate["suggested_python_call"] = _suggested_python_call(
            dict(candidate["suggested_run_config"])
        )
        deduped.append(candidate)
    for index, candidate in enumerate(deduped, start=1):
        candidate["priority_rank"] = int(index)
    return deduped


def _recommend_next_action(shell_pressure_summary, best_box, heuristic_seed, current_run_config=None):
    actions = _recommend_next_actions(shell_pressure_summary, best_box, heuristic_seed, current_run_config)
    return dict(actions[0]) if actions else {
        "kind": "certificate_already_tight",
        "priority_rank": 1,
        "blocking_reason": None,
        "target_axis": None,
        "target_box": {"depth": 0},
        "seed_q_vector": [0.0, 0.0, 0.0],
        "seed_p_weights": [1.0],
        "message": "No unresolved action remains.",
        "suggested_knobs": _suggested_knobs("certificate_already_tight", target_axis=None),
        "suggested_run_config": _suggested_run_config(
            current_run_config,
            _suggested_knobs("certificate_already_tight", target_axis=None),
            target_axis=None,
        ),
        "suggested_python_call": _suggested_python_call(
            _suggested_run_config(
                current_run_config,
                _suggested_knobs("certificate_already_tight", target_axis=None),
                target_axis=None,
            )
        ),
    }


def _summarize_search(search_result):
    statistics = dict(search_result.get("statistics", {}))
    axis_names = _search_axis_names(search_result)
    split_axes = [int(axis) for axis in statistics.get("split_axes", [])]
    axis_split_counts = Counter()
    for axis in split_axes:
        if 0 <= axis < len(axis_names):
            axis_split_counts[axis_names[axis]] += 1
        else:
            axis_split_counts[f"axis_{axis}"] += 1

    axis_gap_reduction_totals = Counter()
    channel_gap_reduction_totals = Counter()
    branch_kind_counts = Counter()
    priority_pressure_by_axis = Counter(
        {
            str(name): float(value)
            for name, value in statistics.get("priority_pressure_by_axis", {}).items()
        }
    )
    priority_pressure_by_channel = Counter(
        {
            str(name): float(value)
            for name, value in statistics.get("priority_pressure_by_channel", {}).items()
        }
    )
    evaluated_boxes = list(search_result.get("evaluated_boxes", []))
    for entry in evaluated_boxes:
        branch_kind = entry.get("branch_kind")
        if branch_kind is not None:
            branch_kind_counts[str(branch_kind)] += 1
        for diagnostic in entry.get("split_axis_diagnostics", []):
            axis_name = str(
                diagnostic.get(
                    "name",
                    f"axis_{int(diagnostic.get('axis', -1))}",
                )
            )
            projected_gap_reduction = float(
                diagnostic.get("projected_gap_reduction", 0.0)
            )
            axis_gap_reduction_totals[axis_name] += projected_gap_reduction
            channel_name = str(diagnostic.get("channel", "generic"))
            channel_gap_reduction_totals[channel_name] += projected_gap_reduction

    return {
        "status": str(search_result.get("status", "inconclusive")),
        "stopping_reason": str(search_result.get("stopping_reason", "unknown")),
        "processed_boxes": int(statistics.get("processed_boxes", 0)),
        "pruned_boxes": int(statistics.get("pruned_boxes", 0)),
        "retained_boxes": int(statistics.get("retained_boxes", 0)),
        "split_boxes": int(statistics.get("split_boxes", 0)),
        "max_queue_size": int(statistics.get("max_queue_size", 0)),
        "queue_reorders_triggered": int(statistics.get("queue_reorders_triggered", 0)),
        "evaluated_boxes": int(len(evaluated_boxes)),
        "frontier_boxes": int(len(search_result.get("boxes", []))),
        "axis_split_counts": {
            str(name): int(count)
            for name, count in sorted(axis_split_counts.items())
        },
        "dominant_split_axis": _dominant_key(axis_split_counts),
        "axis_gap_reduction_totals": {
            str(name): float(value)
            for name, value in sorted(axis_gap_reduction_totals.items())
        },
        "dominant_gap_axis": _dominant_key(axis_gap_reduction_totals),
        "channel_gap_reduction_totals": {
            str(name): float(value)
            for name, value in sorted(channel_gap_reduction_totals.items())
        },
        "dominant_gap_channel": _dominant_key(channel_gap_reduction_totals),
        "priority_pressure_by_axis": {
            str(name): float(value)
            for name, value in sorted(priority_pressure_by_axis.items())
        },
        "dominant_queue_pressure_axis": _dominant_key(priority_pressure_by_axis),
        "priority_pressure_by_channel": {
            str(name): float(value)
            for name, value in sorted(priority_pressure_by_channel.items())
        },
        "dominant_queue_pressure_channel": _dominant_key(priority_pressure_by_channel),
        "branch_kind_counts": {
            str(name): int(count)
            for name, count in sorted(branch_kind_counts.items())
        },
        "dominant_branch_kind": _dominant_key(branch_kind_counts),
    }


def certify_cpn_generalized_lt(
    model,
    *,
    heuristic_result=None,
    reporter=None,
    box_budget=32,
    tolerance=1.0e-3,
    shell_tolerance=5.0e-2,
    supercell_cutoff=4,
    weight_bound=1.0,
    seed=0,
    starts=1,
):
    reporter = reporter or ProgressReporter()
    current_run_config = {
        "box_budget": int(box_budget),
        "tolerance": float(tolerance),
        "shell_tolerance": float(shell_tolerance),
        "supercell_cutoff": int(supercell_cutoff),
        "weight_bound": float(weight_bound),
    }
    reporter.emit(stage="heuristic-seed", processed=0, queued=0, reason="start")
    heuristic_seed = build_heuristic_seed(
        model,
        heuristic_result=heuristic_result,
        seed=seed,
        starts=starts,
    )
    heuristic_seed["refinement"] = refine_candidate_upper_bound(model, heuristic_seed)
    heuristic_seed["energy_upper_bound"] = min(
        float(heuristic_seed["energy_upper_bound"]),
        float(heuristic_seed["refinement"]["energy_upper_bound"]),
    )
    heuristic_seed["q_vector"] = list(heuristic_seed["refinement"]["q_vector"])
    heuristic_seed["p_weights"] = list(heuristic_seed["refinement"]["p_weights"])

    root_box = build_search_box(model, weight_bound=weight_bound)
    reporter.emit(stage="relaxed-bound", processed=0, queued=1, reason="start")
    search_result = run_branch_and_bound(
        lambda box: evaluate_relaxed_box(model, box, heuristic_seed=heuristic_seed),
        root_box,
        tolerance=tolerance,
        box_budget=box_budget,
        reporter=reporter,
    )
    relaxed_certificate = {
        "status": search_result["status"],
        "lower_bound": float(search_result["global_lower_bound"]),
        "upper_bound": float(search_result["global_upper_bound"]),
        "gap": float(search_result["global_upper_bound"] - search_result["global_lower_bound"]),
        "statistics": dict(search_result["statistics"]),
        "best_box": dict(search_result["best_box"]),
    }

    reporter.emit(
        stage="shell-certificate",
        processed=search_result["statistics"]["processed_boxes"],
        queued=0,
        lower_bound=search_result["global_lower_bound"],
        upper_bound=search_result["global_upper_bound"],
        reason="start",
    )
    shell_certificate = build_shell_certificate(search_result, shell_tolerance=shell_tolerance)
    next_best_actions = _recommend_next_actions(
        shell_certificate.get("unresolved_pressure_summary", {}),
        search_result.get("best_box", {}),
        heuristic_seed,
        current_run_config,
    )
    next_best_action = _recommend_next_action(
        shell_certificate.get("unresolved_pressure_summary", {}),
        search_result.get("best_box", {}),
        heuristic_seed,
        current_run_config,
    )
    shell_certificate["unresolved_pressure_summary"]["next_best_action"] = dict(next_best_action)
    shell_certificate["unresolved_pressure_summary"]["next_best_actions"] = [dict(item) for item in next_best_actions]

    raw_result = heuristic_seed.get("raw_result", {})
    matrices = _deserialize_projector_matrices(
        raw_result.get("reconstructed_projector", {}).get("matrix", [])
    )
    reporter.emit(stage="projector-certificate", processed=0, queued=0, reason="start")
    projector_certificate = certify_projector_collection(matrices, tolerance=tolerance)
    projector_exact = (
        projector_certificate.get("status") == "certified"
        or bool(raw_result.get("projector_exactness", {}).get("is_exact_projector_solution", False))
    )

    reporter.emit(stage="lift-certificate", processed=0, queued=0, reason="start")
    commensurate_refuted = bool(
        shell_certificate.get("status") == "certified" and not projector_exact
    )
    lift_certificate = classify_lift_result(
        q_vector=heuristic_seed.get("q_vector", [0.0, 0.0, 0.0]),
        supercell_cutoff=supercell_cutoff,
        projector_exact=projector_exact,
        commensurate_refuted=commensurate_refuted,
        shell_pressure_summary=shell_certificate.get("unresolved_pressure_summary", {}),
    )

    reporter.emit(
        stage="certified-glt-complete",
        processed=search_result["statistics"]["processed_boxes"],
        queued=0,
        lower_bound=search_result["global_lower_bound"],
        upper_bound=search_result["global_upper_bound"],
        reason="done",
    )
    return {
        "heuristic_seed": heuristic_seed,
        "relaxed_global_bound": relaxed_certificate,
        "lowest_shell_certificate": shell_certificate,
        "commensurate_lift_certificate": lift_certificate,
        "projector_exactness_certificate": projector_certificate,
        "search_summary": _summarize_search(search_result),
        "next_best_action": next_best_action,
        "next_best_actions": [dict(item) for item in next_best_actions],
    }
