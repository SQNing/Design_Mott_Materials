#!/usr/bin/env python3

from common.downstream_stage_execution import execute_downstream_stage
from common.downstream_stage_routing import resolve_downstream_stage_route


_SUPPORTED_STAGES = ("lswt", "gswt", "thermodynamics")


def _thermodynamics_has_inputs(payload):
    thermodynamics = payload.get("thermodynamics") if isinstance(payload, dict) else None
    temperatures = thermodynamics.get("temperatures") if isinstance(thermodynamics, dict) else None
    return bool(temperatures)


def _has_gswt_payload(payload):
    return isinstance(payload.get("gswt_payload"), dict) if isinstance(payload, dict) else False


def _should_execute_lswt(route):
    return str(route.get("status")) == "ready"


def _should_execute_gswt(route, payload):
    return str(route.get("status")) == "ready" and _has_gswt_payload(payload)


def _should_execute_thermodynamics(route, payload, allow_review_execution):
    status = str(route.get("status"))
    if status == "review" and not allow_review_execution:
        return False
    if status != "ready":
        return status == "review" and allow_review_execution and _thermodynamics_has_inputs(payload)
    return _thermodynamics_has_inputs(payload)


def _execution_decision(stage_name, route, payload, allow_review_execution):
    status = str(route.get("status"))

    if stage_name == "lswt":
        return ("execute", None) if _should_execute_lswt(route) else ("blocked_route", route.get("reason"))

    if stage_name == "gswt":
        if status != "ready":
            return ("blocked_route", route.get("reason"))
        if not _has_gswt_payload(payload):
            return ("blocked_missing_inputs", "missing-gswt-payload")
        return ("execute", None)

    if status == "review" and not allow_review_execution:
        return ("skipped_review", route.get("reason"))
    if status not in {"ready", "review"}:
        return ("blocked_route", route.get("reason"))
    if not _thermodynamics_has_inputs(payload):
        return ("blocked_missing_inputs", "missing-thermodynamics-inputs")
    return ("execute", None)


def _summarize_stage(stage_name, route, execution_decision, reason=None, backend_selected=None):
    summary = {
        "stage_name": stage_name,
        "route_status": route.get("status"),
        "execution_decision": execution_decision,
        "recommended_backend": route.get("recommended_backend"),
    }
    if reason is not None:
        summary["reason"] = reason
    if backend_selected is not None:
        summary["backend_selected"] = backend_selected
    return summary


def _rollup_status(stage_summaries, downstream_results):
    if any(result.get("status") == "error" for result in downstream_results.values()):
        return "error"

    executed = any(summary.get("execution_decision") == "executed" for summary in stage_summaries.values())
    skipped = any(summary.get("execution_decision") != "executed" for summary in stage_summaries.values())

    if executed and skipped:
        return "partial"
    if executed:
        return "ok"
    if skipped:
        return "blocked"
    return "not_requested"


def orchestrate_document_reader_downstream(payload, *, allow_review_execution=False):
    downstream_routes = {}
    downstream_results = {}
    downstream_summary = {}

    for stage_name in _SUPPORTED_STAGES:
        route = dict(resolve_downstream_stage_route(payload, stage_name))
        downstream_routes[stage_name] = route
        decision, reason = _execution_decision(stage_name, route, payload, allow_review_execution)

        if decision == "execute":
            try:
                stage_result = execute_downstream_stage(payload, stage_name)
            except Exception as exc:
                downstream_results[stage_name] = {"status": "error", "message": str(exc)}
                downstream_summary[stage_name] = _summarize_stage(
                    stage_name,
                    route,
                    execution_decision="error",
                    reason=str(exc),
                )
                continue

            downstream_results[stage_name] = dict(stage_result)
            downstream_summary[stage_name] = _summarize_stage(
                stage_name,
                route,
                execution_decision="executed",
                backend_selected=route.get("recommended_backend"),
            )
            continue

        downstream_summary[stage_name] = _summarize_stage(
            stage_name,
            route,
            execution_decision=decision,
            reason=reason,
        )

    return {
        "downstream_status": _rollup_status(downstream_summary, downstream_results),
        "downstream_routes": downstream_routes,
        "downstream_results": downstream_results,
        "downstream_summary": downstream_summary,
    }
