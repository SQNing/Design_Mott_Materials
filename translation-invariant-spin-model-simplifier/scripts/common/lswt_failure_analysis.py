#!/usr/bin/env python3
import re


def _extract_wavevector(message):
    match = re.search(r"q\s*=\s*(\[[^\]]+\])", str(message))
    if not match:
        return None
    return match.group(1)


def summarize_lswt_failure(payload):
    lswt = payload.get("lswt", {}) if isinstance(payload, dict) else {}
    if not isinstance(lswt, dict):
        return None
    if lswt.get("status") != "error":
        return None

    error = lswt.get("error", {}) if isinstance(lswt.get("error"), dict) else {}
    code = str(error.get("code", ""))
    message = str(error.get("message", ""))
    wavevector = _extract_wavevector(message)

    if code == "backend-execution-failed" and "Instability at wavevector" in message:
        interpretation = "harmonic expansion around the supplied classical reference is unstable"
        if wavevector is not None:
            interpretation += f" near {wavevector}"
        likely_cause = "classical reference state is not a stable expansion point for the current Hamiltonian"
        next_steps = [
            "check whether the classical reference state should be revised before rerunning LSWT",
            "scan nearby ordering wavevectors or enlarge the ordering search before the next spin-wave pass",
            "compare the result with and without weak anisotropic terms to identify which couplings drive the instability",
        ]
        return {
            "interpretation": interpretation,
            "likely_cause": likely_cause,
            "next_steps": next_steps,
        }

    if code == "missing-sunny-package":
        return {
            "interpretation": "the requested LSWT backend could not run because the required Sunny.jl dependency is unavailable",
            "likely_cause": "runtime dependency is missing rather than the magnetic reference state being intrinsically unstable",
            "next_steps": [
                "install or enable the requested LSWT backend dependency before rerunning",
                "switch to an available backend if one matches the current payload",
                "preserve the classical diagnostics and report the LSWT result as unavailable rather than physically unstable",
            ],
        }

    return {
        "interpretation": "the LSWT stage failed before producing a usable dispersion result",
        "likely_cause": "backend execution stopped before a stable spin-wave result could be assembled",
        "next_steps": [
            "inspect the backend error message and stage inputs before rerunning",
            "confirm that the classical reference state and q-path are appropriate for the current model",
            "retry with a narrower diagnostic run to isolate whether the failure is physical or runtime-related",
        ],
    }
