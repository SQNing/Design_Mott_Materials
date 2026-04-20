#!/usr/bin/env python3

from common.classical_contract_resolution import (
    get_classical_state_result,
    get_downstream_stage_compatibility,
    get_standardized_classical_state,
)


_SUPPORTED_STAGES = {"lswt", "gswt", "thermodynamics"}


def _ensure_supported_stage(stage_name):
    stage_name = str(stage_name)
    if stage_name not in _SUPPORTED_STAGES:
        raise ValueError(f"unsupported downstream stage: {stage_name}")
    return stage_name


def _has_spin_frame_state(payload):
    classical_state = get_standardized_classical_state(payload, prefer_nested_legacy=True)
    site_frames = classical_state.get("site_frames") if isinstance(classical_state, dict) else None
    return isinstance(site_frames, list) and bool(site_frames)


def _has_bonds(payload):
    bonds = payload.get("bonds") if isinstance(payload, dict) else None
    return bool(bonds)


def _thermodynamics_settings(payload):
    thermodynamics = payload.get("thermodynamics") if isinstance(payload, dict) else None
    return thermodynamics if isinstance(thermodynamics, dict) else {}


def _stable_backend_hint(stage_name, recommended_backend, payload):
    stage_name = str(stage_name)
    recommended_backend = None if recommended_backend is None else str(recommended_backend)

    if stage_name == "lswt":
        return "linear_spin_wave"

    if stage_name == "gswt":
        if recommended_backend in {"python", "python_glswt"}:
            return "python_glswt"
        if recommended_backend in {"sunny", "sun_gswt", "sunny_gswt"}:
            return "sun_gswt"
        gswt_payload = payload.get("gswt_payload") if isinstance(payload, dict) else None
        if isinstance(gswt_payload, dict):
            payload_kind = str(gswt_payload.get("payload_kind"))
            if payload_kind in {"python_glswt_local_rays", "python_glswt_single_q_z_harmonic"}:
                return "python_glswt"
            return "sun_gswt"
        return None

    if recommended_backend in {
        "sunny-local-sampler",
        "sunny-parallel-tempering",
        "sunny-wang-landau",
        "sunny_thermodynamics",
    }:
        return "sunny_thermodynamics"
    if recommended_backend == "spin_only_thermodynamics":
        return "spin_only_thermodynamics"

    thermodynamics_payload = payload.get("thermodynamics_payload") if isinstance(payload, dict) else None
    if isinstance(thermodynamics_payload, dict):
        return "sunny_thermodynamics"

    thermodynamics = _thermodynamics_settings(payload)
    backend_method = thermodynamics.get("backend_method")
    if backend_method is not None and str(backend_method).startswith("sunny-"):
        return "sunny_thermodynamics"

    classical_state = get_standardized_classical_state(payload, prefer_nested_legacy=True)
    if isinstance(classical_state, dict):
        state_kind = str(classical_state.get("state_kind", "")).strip()
        manifold = str(classical_state.get("manifold", "")).strip()
        if state_kind == "local_rays" or manifold == "CP^(N-1)":
            return "sunny_thermodynamics"
        if isinstance(classical_state.get("site_frames"), list) and classical_state.get("site_frames"):
            return "spin_only_thermodynamics"

    return "spin_only_thermodynamics"


def _legacy_stage_route(payload, stage_name):
    if stage_name == "lswt":
        if _has_spin_frame_state(payload):
            return {
                "status": "ready",
                "enabled": True,
                "source": "legacy-fallback",
                "recommended_backend": "linear_spin_wave",
            }
        return {
            "status": "blocked",
            "enabled": False,
            "source": "legacy-fallback",
            "reason": "missing-spin-frame-site-frames",
            "recommended_backend": "linear_spin_wave",
        }

    if stage_name == "gswt":
        gswt_payload = payload.get("gswt_payload") if isinstance(payload, dict) else None
        if isinstance(gswt_payload, dict):
            return {
                "status": "ready",
                "enabled": True,
                "source": "legacy-fallback",
                "recommended_backend": _stable_backend_hint("gswt", None, payload),
            }
        return {"status": "blocked", "enabled": False, "source": "legacy-fallback", "reason": "missing-gswt-payload"}

    thermodynamics = _thermodynamics_settings(payload)
    if _has_bonds(payload) and thermodynamics.get("temperatures"):
        return {
            "status": "ready",
            "enabled": True,
            "source": "legacy-fallback",
            "recommended_backend": _stable_backend_hint("thermodynamics", thermodynamics.get("backend_method"), payload),
        }
    return {
        "status": "blocked",
        "enabled": False,
        "source": "legacy-fallback",
        "reason": "missing-thermodynamics-inputs",
    }


def resolve_downstream_stage_route(payload, stage_name):
    stage_name = _ensure_supported_stage(stage_name)
    classical_state_result = get_classical_state_result(payload) or {}
    stage_compatibility = get_downstream_stage_compatibility(payload, stage_name)
    if isinstance(stage_compatibility, dict):
        route = {
            "status": str(stage_compatibility.get("status")),
            "enabled": str(stage_compatibility.get("status")) in {"ready", "review"},
            "source": "standardized-contract",
            "reason": stage_compatibility.get("reason"),
            "recommended_backend": _stable_backend_hint(stage_name, stage_compatibility.get("recommended_backend"), payload),
            "method": classical_state_result.get("method"),
            "role": classical_state_result.get("role"),
            "solver_family": classical_state_result.get("solver_family"),
        }
        return route

    return _legacy_stage_route(payload, stage_name)


def downstream_stage_enabled(payload, stage_name):
    return bool(resolve_downstream_stage_route(payload, stage_name).get("enabled"))


def downstream_stage_backend_hint(payload, stage_name):
    return resolve_downstream_stage_route(payload, stage_name).get("recommended_backend")
