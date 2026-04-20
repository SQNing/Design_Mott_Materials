#!/usr/bin/env python3


def infer_classical_state_semantics(classical_state):
    state = classical_state if isinstance(classical_state, dict) else {}
    site_frames = state.get("site_frames")
    local_rays = state.get("local_rays")
    state_kind = str(state.get("state_kind", "")).strip()
    manifold = str(state.get("manifold", "")).strip()

    has_site_frames = isinstance(site_frames, list) and bool(site_frames)
    has_local_rays = isinstance(local_rays, list) and bool(local_rays)
    is_local_ray = has_local_rays or state_kind == "local_rays" or manifold == "CP^(N-1)"

    if is_local_ray:
        return {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "supports_lswt": False,
            "supports_gswt": True,
            "supports_thermodynamics": True,
        }

    if has_site_frames:
        return {
            "state_kind": "spin_frames",
            "manifold": "spin-frame",
            "supports_lswt": True,
            "supports_gswt": False,
            "supports_thermodynamics": False,
        }

    return {
        "state_kind": "unknown",
        "manifold": manifold or None,
        "supports_lswt": False,
        "supports_gswt": False,
        "supports_thermodynamics": False,
    }


def build_downstream_compatibility(
    *,
    semantics=None,
    role="final",
    reason=None,
    thermodynamics_supported=False,
):
    role_name = str(role or "final")
    reason_text = str(reason) if reason is not None else None
    semantics_payload = semantics if isinstance(semantics, dict) else {}

    if role_name == "diagnostic":
        diagnostic_reason = reason_text or "diagnostic-result"
        return {
            "lswt": {"status": "blocked", "reason": diagnostic_reason},
            "gswt": {"status": "blocked", "reason": diagnostic_reason},
            "thermodynamics": {"status": "blocked", "reason": diagnostic_reason},
        }

    state_kind = semantics_payload.get("state_kind")

    if state_kind == "spin_frames":
        thermodynamics_status = "ready" if bool(thermodynamics_supported) else "review"
        thermodynamics_payload = {"status": thermodynamics_status}
        if thermodynamics_status == "review":
            thermodynamics_payload["reason"] = "requires-caller-confirmed-support"
        return {
            "lswt": {"status": "ready"},
            "gswt": {"status": "blocked", "reason": "requires-local-ray-cpn-state"},
            "thermodynamics": thermodynamics_payload,
        }

    if state_kind == "local_rays":
        return {
            "lswt": {"status": "blocked", "reason": "requires-spin-frame-site-frames"},
            "gswt": {"status": "ready"},
            "thermodynamics": {"status": "ready"},
        }

    return {
        "lswt": {"status": "blocked", "reason": "unrecognized-classical-state-semantics"},
        "gswt": {"status": "blocked", "reason": "unrecognized-classical-state-semantics"},
        "thermodynamics": {"status": "blocked", "reason": "unrecognized-classical-state-semantics"},
    }


def build_final_classical_state_result(
    classical_state,
    *,
    thermodynamics_supported=False,
    semantics=None,
    diagnostics=None,
):
    if not isinstance(classical_state, dict) or not classical_state:
        raise ValueError("final classical results require a non-empty classical_state mapping")

    semantics_payload = semantics if isinstance(semantics, dict) else infer_classical_state_semantics(classical_state)
    result = {
        "status": "ok",
        "role": "final",
        "classical_state": classical_state,
        "classical_state_semantics": semantics_payload,
        "downstream_compatibility": build_downstream_compatibility(
            semantics=semantics_payload,
            role="final",
            thermodynamics_supported=thermodynamics_supported,
        ),
    }
    if diagnostics is not None:
        result["diagnostics"] = diagnostics
    return result


def build_diagnostic_classical_result(
    *,
    reason,
    diagnostics=None,
    classical_state=None,
):
    reason_text = str(reason).strip() if reason is not None else ""
    if not reason_text:
        raise ValueError("diagnostic classical results require an explicit reason")

    result = {
        "status": "ok",
        "role": "diagnostic",
        "reason": reason_text,
        "downstream_compatibility": build_downstream_compatibility(
            role="diagnostic",
            reason=reason_text,
        ),
    }
    if classical_state is not None:
        result["classical_state"] = classical_state
    if diagnostics is not None:
        result["diagnostics"] = diagnostics
    return result
