#!/usr/bin/env python3

from common.fei2_official_sunny_reproduction import (
    OFFICIAL_FEI2_DOMAIN_ROTATIONS,
    OFFICIAL_FEI2_Q_PATH,
    OFFICIAL_FEI2_RESHAPE_MATRIX,
    OFFICIAL_FEI2_TARGET_Q,
    OFFICIAL_FEI2_WEBSITE_PAGE_URL,
    OFFICIAL_FEI2_WEBSITE_SCRIPT_URL,
)


_CONTRACT_ERROR_CODES = {
    "unsupported-reduced-single-q-sun-gswt",
    "unsupported-incommensurate-single-q-sun-gswt",
    "invalid-gswt-payload",
    "invalid-gswt-convention",
    "unsupported-gswt-payload",
    "unsupported-spin-half-pair-operator",
    "missing-gswt-payload",
}


def official_fei2_reference_metadata():
    return {
        "website_page_url": OFFICIAL_FEI2_WEBSITE_PAGE_URL,
        "website_script_url": OFFICIAL_FEI2_WEBSITE_SCRIPT_URL,
        "target_q": list(OFFICIAL_FEI2_TARGET_Q),
        "reshape_matrix": [list(row) for row in OFFICIAL_FEI2_RESHAPE_MATRIX],
        "q_path": [list(point) for point in OFFICIAL_FEI2_Q_PATH],
        "domain_rotations": [
            {"axis": list(axis), "angle": float(angle)}
            for axis, angle in OFFICIAL_FEI2_DOMAIN_ROTATIONS
        ],
    }


def dispersion_summary_from_result(result):
    diagnostics = result.get("diagnostics", {}) if isinstance(result, dict) else {}
    if not isinstance(diagnostics, dict):
        return {}
    dispersion = diagnostics.get("dispersion", {})
    if not isinstance(dispersion, dict):
        return {}
    summary = {}
    for key in ("omega_min", "omega_max", "omega_min_q_vector", "soft_mode_count", "soft_mode_q_points"):
        if key in dispersion:
            summary[key] = dispersion[key]
    return summary


def classify_fei2_sunny_glswt_result(case_id, result):
    result = result if isinstance(result, dict) else {}
    error = result.get("error", {}) if isinstance(result.get("error"), dict) else {}
    error_code = error.get("code")
    summary = {
        "case_id": str(case_id),
        "status": result.get("status"),
        "error_code": error_code,
    }
    summary.update(dispersion_summary_from_result(result))

    if result.get("status") == "ok":
        summary["category"] = "allowed_and_executed"
        return summary

    diagnostics = result.get("diagnostics", {}) if isinstance(result.get("diagnostics"), dict) else {}
    instability = diagnostics.get("instability", {}) if isinstance(diagnostics.get("instability"), dict) else {}
    if error_code == "backend-execution-failed" and instability:
        summary["category"] = "allowed_but_unstable"
        if instability.get("q_vector") is not None:
            summary["softest_q_vector"] = list(instability["q_vector"])
        return summary

    if error_code in _CONTRACT_ERROR_CODES:
        summary["category"] = "blocked_by_contract"
        return summary

    summary["category"] = "blocked_by_backend"
    return summary
