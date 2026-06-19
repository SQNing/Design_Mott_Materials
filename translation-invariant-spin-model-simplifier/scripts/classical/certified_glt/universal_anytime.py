#!/usr/bin/env python3

from copy import deepcopy
from numbers import Number

_VALID_MODES = {"fast", "certified", "anytime"}
_VALID_PROOF_STRATEGIES = {"proof_only", "candidate_assisted", "auto"}
_VALID_EXECUTION_PATHS = {"not_started", "fast_only", "proof_only", "candidate_assisted"}


def _jsonify(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, dict):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(item) for item in value]
    if hasattr(value, "tolist") and not isinstance(value, (bytes, bytearray, str)):
        try:
            return _jsonify(value.tolist())
        except Exception:
            pass
    if hasattr(value, "item") and callable(value.item):
        try:
            item = value.item()
        except Exception:
            item = None
        else:
            if item is not value:
                return _jsonify(item)
    return deepcopy(value)


def _coerce_string(value, *, allow_none=False):
    if value is None:
        if allow_none:
            return None
        raise ValueError("string value is required")
    text = str(value).strip()
    if not text:
        if allow_none:
            return None
        raise ValueError("string value is required")
    return text


def _coerce_optional_number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("numeric values must not be booleans")
    if isinstance(value, Number):
        return float(value)
    return float(value)


def _coerce_optional_integer(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("integer values must not be booleans")
    return int(value)


def _normalize_mode(mode):
    resolved = _coerce_string(mode).lower()
    if resolved not in _VALID_MODES:
        raise ValueError(f"unsupported mode: {mode!r}")
    return resolved


def _normalize_proof_strategy(mode, strategy):
    if strategy is None:
        if mode == "certified":
            raise ValueError("routing.proof_strategy is required for mode=certified")
        if mode == "anytime":
            return "auto"
        return None

    resolved = _coerce_string(strategy).lower()
    if resolved not in _VALID_PROOF_STRATEGIES:
        raise ValueError(f"unsupported proof_strategy: {strategy!r}")
    if mode == "certified" and resolved == "auto":
        raise ValueError("routing.proof_strategy=auto is only valid for mode=anytime")
    if mode == "fast":
        return resolved
    return resolved


def _normalize_budget(budget):
    if not isinstance(budget, dict):
        raise ValueError("budget must be a mapping")
    normalized = {
        "wall_time_sec": _coerce_optional_number(budget.get("wall_time_sec")),
        "box_budget": _coerce_optional_integer(budget.get("box_budget")),
        "candidate_starts": _coerce_optional_integer(budget.get("candidate_starts")),
        "fast_iterations": _coerce_optional_integer(budget.get("fast_iterations")),
    }
    if all(value is None for value in normalized.values()):
        raise ValueError("budget requires at least one non-null limit")
    return normalized


def _normalize_thresholds(thresholds):
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be a mapping")
    return {
        "gap_tolerance": _coerce_optional_number(thresholds.get("gap_tolerance")),
        "stationarity_tolerance": _coerce_optional_number(thresholds.get("stationarity_tolerance")),
        "energy_tolerance": _coerce_optional_number(thresholds.get("energy_tolerance")),
    }


def _normalize_compiler_payload(compiler_payload):
    if not isinstance(compiler_payload, dict) or not compiler_payload:
        raise ValueError("compiler payload must be a non-empty mapping")
    return _jsonify(compiler_payload)


def _capability_bool(capabilities, name):
    return bool(capabilities.get(name, False))


def _select_backend(requested_backend, preferred_backend, capabilities, *, family):
    if requested_backend is not None:
        backend = _coerce_string(requested_backend, allow_none=True)
        if backend is not None:
            return backend
    if preferred_backend is not None:
        backend = _coerce_string(preferred_backend, allow_none=True)
        if backend is not None:
            return backend

    if family == "fast":
        if _capability_bool(capabilities, "supports_q_optimization"):
            return "cpn-generalized-lt"
        if _capability_bool(capabilities, "supports_cp_manifold"):
            return "cpn-local-ray-minimize"
        return "generic-fast"
    if family == "proof":
        if _capability_bool(capabilities, "supports_interval_bounds"):
            return "interval-branch-and-bound"
        if _capability_bool(capabilities, "supports_sos_bounds"):
            return "moment-sdp-hierarchy"
        return "generic-proof"
    raise ValueError(f"unsupported backend family: {family!r}")


def normalize_universal_anytime_request(request, *, compiler_payload=None, compiler_normalized=None):
    if not isinstance(request, dict):
        raise ValueError("request must be a mapping")

    compiler_source = compiler_payload if compiler_payload is not None else compiler_normalized
    if compiler_source is None:
        compiler_source = request.get("compiler_payload")
    if compiler_source is None:
        compiler_source = request.get("compiler")
    compiler_payload = _normalize_compiler_payload(compiler_source)

    mode = _normalize_mode(request.get("mode"))
    seed = int(request.get("seed", 0))
    budget = _normalize_budget(request.get("budget"))
    thresholds = _normalize_thresholds(request.get("thresholds"))

    routing_request = request.get("routing", {})
    if not isinstance(routing_request, dict):
        raise ValueError("routing must be a mapping")

    requested_fast_backend = _coerce_string(routing_request.get("fast_backend"), allow_none=True)
    requested_proof_backend = _coerce_string(routing_request.get("proof_backend"), allow_none=True)
    requested_proof_strategy = _normalize_proof_strategy(mode, routing_request.get("proof_strategy"))

    capabilities = _jsonify(compiler_payload.get("capabilities", {}))
    solver_hints = _jsonify(compiler_payload.get("solver_hints", {}))

    fast_backend = _select_backend(
        requested_fast_backend,
        solver_hints.get("preferred_fast_backend"),
        capabilities,
        family="fast",
    )
    proof_backend = _select_backend(
        requested_proof_backend,
        solver_hints.get("preferred_proof_backend"),
        capabilities,
        family="proof",
    )

    effective_proof_strategy = None
    if mode == "fast":
        effective_proof_strategy = None
    elif mode == "certified":
        effective_proof_strategy = requested_proof_strategy
    elif mode == "anytime":
        effective_proof_strategy = requested_proof_strategy or "auto"

    normalized = {
        "mode": mode,
        "requested_mode": mode,
        "seed": seed,
        "budget": budget,
        "thresholds": thresholds,
        "routing": {
            "fast_backend": fast_backend,
            "proof_backend": proof_backend,
            "proof_strategy": effective_proof_strategy,
        },
        "requested_proof_strategy": requested_proof_strategy,
        "requested_routing": _jsonify(routing_request),
        "compiler_payload": _jsonify(compiler_payload),
        "canonical_model": _jsonify(compiler_payload.get("canonical_model")),
        "capabilities": capabilities,
        "objective_oracle": _jsonify(compiler_payload.get("objective_oracle")),
        "structure_summary": _jsonify(compiler_payload.get("structure_summary")),
        "solver_hints": solver_hints,
        "compiler_version": str(compiler_payload.get("compiler_version", "unknown")),
    }
    return normalized


def resolve_execution_path(request, *, candidate_available=None):
    if not isinstance(request, dict):
        raise ValueError("request must be a mapping")

    mode = _normalize_mode(request.get("mode", request.get("requested_mode")))
    routing = request.get("routing", {}) if isinstance(request.get("routing"), dict) else {}
    proof_strategy = routing.get("proof_strategy")

    actual_path = None
    if mode == "fast":
        actual_path = "fast_only"
    elif mode == "certified":
        if proof_strategy == "candidate_assisted":
            actual_path = "candidate_assisted" if candidate_available is not False else "proof_only"
        else:
            actual_path = "proof_only"
    elif mode == "anytime":
        if proof_strategy == "proof_only":
            actual_path = "proof_only"
        elif candidate_available is False:
            actual_path = "proof_only"
        elif proof_strategy in {"auto", "candidate_assisted"}:
            actual_path = "candidate_assisted"
        else:
            actual_path = "proof_only"

    if actual_path not in _VALID_EXECUTION_PATHS:
        raise ValueError(f"unsupported execution path: {actual_path!r}")

    return {
        "requested_mode": mode,
        "requested_proof_strategy": request.get("requested_proof_strategy"),
        "execution_family": actual_path,
        "execution_path": actual_path,
        "fast_backend": routing.get("fast_backend"),
        "proof_backend": routing.get("proof_backend"),
    }


def build_completion(
    *,
    execution_path,
    status,
    reason=None,
    stopping_condition=None,
    budget_used=None,
    budget_remaining=None,
):
    execution_path = _coerce_string(execution_path)
    if execution_path not in _VALID_EXECUTION_PATHS:
        raise ValueError(f"unsupported execution path: {execution_path!r}")

    completion_status = _coerce_string(status).lower()
    if completion_status not in {"final", "partial", "failed"}:
        raise ValueError(f"unsupported completion status: {status!r}")

    used = _jsonify(budget_used if budget_used is not None else {})
    if not isinstance(used, dict):
        raise ValueError("budget_used must be a mapping when provided")
    used = {
        "wall_time_sec": used.get("wall_time_sec"),
        "elapsed_wall_time_sec": used.get("elapsed_wall_time_sec"),
        "box_budget": used.get("box_budget"),
        "candidate_starts": used.get("candidate_starts"),
        "fast_iterations": used.get("fast_iterations"),
    }

    remaining = None
    if budget_remaining is not None:
        remaining_json = _jsonify(budget_remaining)
        if not isinstance(remaining_json, dict):
            raise ValueError("budget_remaining must be a mapping when provided")
        remaining = {
            "wall_time_sec": remaining_json.get("wall_time_sec"),
            "box_budget": remaining_json.get("box_budget"),
            "candidate_starts": remaining_json.get("candidate_starts"),
            "fast_iterations": remaining_json.get("fast_iterations"),
        }

    return {
        "status": completion_status,
        "reason": _coerce_string(reason, allow_none=True),
        "stopping_condition": _coerce_string(stopping_condition, allow_none=True),
        "budget_used": used,
        "budget_remaining": remaining,
        "execution_path": execution_path,
    }


def _default_certificate():
    return {
        "status": "failed",
        "lower_bound": None,
        "upper_bound": None,
        "gap": None,
        "coverage": {
            "processed_boxes": 0,
            "pruned_boxes": 0,
            "retained_boxes": 0,
            "split_boxes": 0,
            "max_queue_size": 0,
            "frontier_size": 0,
            "frontier": [],
            "global_lower_bound": None,
            "global_upper_bound": None,
        },
        "proof_trace": None,
    }


def _normalize_certificate(certificate, *, candidate=None, status="ok"):
    normalized = _default_certificate()
    if certificate is not None:
        payload = _jsonify(certificate)
        if not isinstance(payload, dict):
            raise ValueError("certificate must be a mapping when provided")
        normalized.update({key: payload.get(key, normalized.get(key)) for key in normalized.keys()})
        coverage = dict(_default_certificate()["coverage"])
        coverage.update(_jsonify(payload.get("coverage", {})) if isinstance(payload.get("coverage"), dict) else {})
        normalized["coverage"] = coverage
        if payload.get("proof_trace") is not None:
            normalized["proof_trace"] = _jsonify(payload.get("proof_trace"))

    if candidate is not None and normalized.get("status") in {None, "failed"}:
        coverage = dict(normalized.get("coverage", {}))
        proof_trace = normalized.get("proof_trace")
        has_proof_evidence = bool(
            proof_trace
            or int(coverage.get("frontier_size", 0) or 0) > 0
            or bool(coverage.get("frontier"))
        )
        if not has_proof_evidence:
            normalized["status"] = "upper_bound_only"
            normalized["upper_bound"] = float(candidate.get("energy"))

    if normalized.get("status") == "upper_bound_only" and normalized.get("upper_bound") is None and candidate is not None:
        normalized["upper_bound"] = float(candidate.get("energy"))

    if normalized.get("status") == "failed" and candidate is not None:
        coverage = dict(normalized.get("coverage", {}))
        proof_trace = normalized.get("proof_trace")
        has_proof_evidence = bool(
            proof_trace
            or int(coverage.get("frontier_size", 0) or 0) > 0
            or bool(coverage.get("frontier"))
        )
        if not has_proof_evidence:
            normalized["status"] = "upper_bound_only"
            normalized["upper_bound"] = float(candidate.get("energy"))

    lower_bound = normalized.get("lower_bound")
    upper_bound = normalized.get("upper_bound")
    if lower_bound is not None and upper_bound is not None:
        normalized["gap"] = float(upper_bound) - float(lower_bound)
    elif normalized.get("status") == "upper_bound_only":
        normalized["gap"] = None
    elif normalized.get("status") == "lower_bound_only":
        normalized["gap"] = None
    elif normalized.get("status") == "failed":
        normalized["gap"] = None

    coverage = normalized.get("coverage", {})
    if isinstance(coverage, dict):
        coverage.setdefault("processed_boxes", 0)
        coverage.setdefault("pruned_boxes", 0)
        coverage.setdefault("retained_boxes", 0)
        coverage.setdefault("split_boxes", 0)
        coverage.setdefault("max_queue_size", 0)
        coverage.setdefault("frontier", [])
        coverage.setdefault("frontier_size", len(coverage.get("frontier", [])))
        coverage.setdefault("global_lower_bound", lower_bound)
        coverage.setdefault("global_upper_bound", upper_bound)
        normalized["coverage"] = coverage

    if normalized.get("status") == "failed" and status == "error" and normalized.get("proof_trace") is None:
        normalized["proof_trace"] = None

    if normalized.get("status") == "certified":
        coverage = normalized.get("coverage", {})
        if isinstance(coverage, dict):
            lower = coverage.get("global_lower_bound", normalized.get("lower_bound"))
            upper = coverage.get("global_upper_bound", normalized.get("upper_bound"))
            if lower is not None and upper is not None:
                normalized["gap"] = float(upper) - float(lower)

    return normalized


def _infer_completion_status(candidate, certificate, status, proof_trace=None):
    if status == "error":
        return "failed"

    certificate_status = str(certificate.get("status", "failed")) if isinstance(certificate, dict) else "failed"
    lower_bound = certificate.get("lower_bound") if isinstance(certificate, dict) else None
    upper_bound = certificate.get("upper_bound") if isinstance(certificate, dict) else None
    proof_trace = proof_trace if proof_trace is not None else (certificate.get("proof_trace") if isinstance(certificate, dict) else None)
    coverage = certificate.get("coverage", {}) if isinstance(certificate, dict) else {}
    has_frontier = bool(coverage.get("frontier"))

    if certificate_status == "certified":
        return "final"
    if lower_bound is not None and upper_bound is not None:
        return "partial"
    if certificate_status in {"partial", "upper_bound_only", "lower_bound_only"}:
        return "partial"
    if proof_trace is not None and (proof_trace.get("status") in {"partial", "complete"} or has_frontier):
        return "partial"
    if candidate is not None and certificate_status == "failed":
        return "partial"
    return "failed"


def build_provenance(request, *, execution_path):
    if not isinstance(request, dict):
        raise ValueError("request must be a mapping")
    execution_path = _coerce_string(execution_path)
    if execution_path not in _VALID_EXECUTION_PATHS:
        raise ValueError(f"unsupported execution path: {execution_path!r}")

    routing = request.get("routing", {})
    compiler_payload = request.get("compiler_payload", {})
    if not isinstance(routing, dict):
        routing = {}
    if not isinstance(compiler_payload, dict):
        compiler_payload = {}
    capabilities = _jsonify(request.get("capabilities", compiler_payload.get("capabilities", {})))
    budget = _jsonify(request.get("budget", {}))

    fast_backend = routing.get("fast_backend") if execution_path in {"fast_only", "candidate_assisted"} else None
    proof_backend = routing.get("proof_backend") if execution_path in {"proof_only", "candidate_assisted"} else None

    return {
        "requested_mode": request.get("requested_mode", request.get("mode")),
        "requested_proof_strategy": request.get("requested_proof_strategy"),
        "execution_path": execution_path,
        "fast_backend": fast_backend,
        "proof_backend": proof_backend,
        "compiler_version": str(request.get("compiler_version", compiler_payload.get("compiler_version", "unknown"))),
        "seed": int(request.get("seed", 0)),
        "capabilities": capabilities,
        "budget": budget,
    }


def _skeleton_response(status="ok"):
    response_status = _coerce_string(status).lower()
    if response_status not in {"ok", "error"}:
        raise ValueError(f"unsupported response status: {status!r}")
    return response_status


def build_universal_anytime_response(
    request,
    *,
    candidate=None,
    certificate=None,
    status="ok",
    errors=None,
    warnings=None,
    execution_path=None,
    completion=None,
    provenance=None,
    compiler_payload=None,
):
    normalized_request = request
    if isinstance(request, dict) and (
        "compiler_payload" not in request
        and "capabilities" not in request
        and "requested_mode" not in request
        and "mode" in request
    ):
        normalized_request = normalize_universal_anytime_request(
            request,
            compiler_payload=compiler_payload,
        )
    elif not isinstance(request, dict):
        raise ValueError("request must be a mapping")

    response_status = _skeleton_response(status)
    candidate_payload = _jsonify(candidate) if candidate is not None else None
    if candidate_payload is not None and not isinstance(candidate_payload, dict):
        raise ValueError("candidate must be a mapping when provided")

    certificate_payload = _normalize_certificate(certificate, candidate=candidate_payload, status=response_status)

    if response_status == "error":
        if certificate_payload.get("status") == "certified":
            certificate_payload["status"] = "failed"
        if execution_path is None:
            execution_path = "not_started"

    if execution_path is None:
        candidate_available = candidate_payload is not None
        execution_path = resolve_execution_path(normalized_request, candidate_available=candidate_available)["execution_path"]
    else:
        execution_path = _coerce_string(execution_path)
        if execution_path not in _VALID_EXECUTION_PATHS:
            raise ValueError(f"unsupported execution path: {execution_path!r}")

    if response_status == "error":
        execution_path = "not_started"

    if provenance is None:
        provenance_payload = build_provenance(normalized_request, execution_path=execution_path)
    else:
        provenance_payload = _jsonify(provenance)
        if not isinstance(provenance_payload, dict):
            raise ValueError("provenance must be a mapping when provided")
        provenance_payload["requested_mode"] = normalized_request.get("requested_mode", normalized_request.get("mode"))
        provenance_payload["requested_proof_strategy"] = normalized_request.get("requested_proof_strategy")
        provenance_payload["execution_path"] = execution_path
        provenance_payload["fast_backend"] = (
            normalized_request.get("routing", {}).get("fast_backend")
            if execution_path in {"fast_only", "candidate_assisted"}
            else None
        )
        provenance_payload["proof_backend"] = (
            normalized_request.get("routing", {}).get("proof_backend")
            if execution_path in {"proof_only", "candidate_assisted"}
            else None
        )
        provenance_payload["compiler_version"] = str(
            normalized_request.get("compiler_version", provenance_payload.get("compiler_version", "unknown"))
        )
        provenance_payload["seed"] = int(normalized_request.get("seed", provenance_payload.get("seed", 0)))
        provenance_payload["capabilities"] = _jsonify(
            normalized_request.get("capabilities", provenance_payload.get("capabilities", {}))
        )
        provenance_payload["budget"] = _jsonify(normalized_request.get("budget", provenance_payload.get("budget", {})))

    if completion is None:
        completion_status = _infer_completion_status(candidate_payload, certificate_payload, response_status)
        if response_status == "error":
            completion_status = "failed"
        elif completion_status == "partial" and certificate_payload.get("status") == "certified":
            completion_status = "final"
        completion_payload = build_completion(
            execution_path=execution_path,
            status=completion_status,
            reason="fatal_error" if response_status == "error" else None,
            stopping_condition="fatal_error" if response_status == "error" else None,
            budget_used=normalized_request.get("budget"),
            budget_remaining=None,
        )
    else:
        completion_payload = _jsonify(completion)
        if not isinstance(completion_payload, dict):
            raise ValueError("completion must be a mapping when provided")
        completion_payload["execution_path"] = execution_path
        if response_status == "error":
            completion_payload["status"] = "failed"
            completion_payload["reason"] = completion_payload.get("reason") or "fatal_error"
            completion_payload["stopping_condition"] = completion_payload.get("stopping_condition") or "fatal_error"

    error_list = None
    if errors is not None:
        error_list = _jsonify(errors)
        if isinstance(error_list, str):
            error_list = [error_list]
        if not isinstance(error_list, list):
            raise ValueError("errors must be a list, tuple, or string when provided")
        error_list = [item for item in error_list if item is not None]
    if response_status == "error" and not error_list:
        error_list = ["fatal_error"]

    warning_list = None
    if warnings is not None:
        warning_list = _jsonify(warnings)
        if isinstance(warning_list, str):
            warning_list = [warning_list]
        if not isinstance(warning_list, list):
            raise ValueError("warnings must be a list, tuple, or string when provided")
        warning_list = [item for item in warning_list if item is not None]

    response = {
        "status": response_status,
        "completion": completion_payload,
        "candidate": candidate_payload,
        "certificate": certificate_payload,
        "provenance": provenance_payload,
        "errors": error_list,
        "warnings": warning_list,
    }

    if response_status == "ok" and response["certificate"] is None:
        response["certificate"] = _default_certificate()
    if response_status == "ok" and response["completion"] is None:
        response["completion"] = build_completion(
            execution_path=execution_path,
            status="failed",
            reason=None,
            stopping_condition=None,
            budget_used=normalized_request.get("budget"),
            budget_remaining=None,
        )

    return response

