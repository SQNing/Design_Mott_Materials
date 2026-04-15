#!/usr/bin/env python3

from fractions import Fraction


def _rationalize_component(value, cutoff, *, tolerance=1.0e-14, detection_denominator=64):
    normalized = float(value) % 1.0
    if abs(normalized) <= tolerance or abs(normalized - 1.0) <= tolerance:
        return {"value": 0.0, "denominator": 1, "rational": True, "within_cutoff": True}
    fraction = Fraction(normalized).limit_denominator(int(max(1, detection_denominator)))
    reduced = float(fraction)
    if abs(reduced - normalized) <= tolerance:
        denominator = int(fraction.denominator)
        return {
            "value": reduced,
            "denominator": denominator,
            "rational": True,
            "within_cutoff": bool(denominator <= int(supercell_cutoff := max(1, cutoff))),
        }
    return {"value": normalized, "denominator": None, "rational": False, "within_cutoff": False}


def classify_lift_result(
    *,
    q_vector,
    supercell_cutoff,
    projector_exact,
    commensurate_refuted,
    shell_pressure_summary=None,
):
    rationalized = [_rationalize_component(component, supercell_cutoff) for component in q_vector]
    all_rational = all(item["rational"] for item in rationalized)
    exact_commensurate = all(
        item["rational"] and bool(item.get("within_cutoff"))
        for item in rationalized
    )
    if projector_exact and exact_commensurate:
        status = "commensurate_certified"
    elif commensurate_refuted:
        if all_rational:
            status = "commensurate_refuted_up_to_cutoff"
        else:
            status = "incommensurate_supported"
    else:
        status = "inconclusive"
    return {
        "status": status,
        "q_vector": list(q_vector),
        "supercell_cutoff": int(supercell_cutoff),
        "projector_exact": bool(projector_exact),
        "commensurate_refuted": bool(commensurate_refuted),
        "rationalized_q": rationalized,
        "shell_pressure_summary": dict(shell_pressure_summary or {}),
    }
