#!/usr/bin/env python3

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from classical.classical_solver_driver import choose_method
else:
    from .classical_solver_driver import choose_method


def _get_classical_state_result(model):
    if not isinstance(model, dict):
        return {}
    classical_state_result = model.get("classical_state_result")
    if isinstance(classical_state_result, dict):
        return classical_state_result
    classical = model.get("classical", {})
    if isinstance(classical, dict):
        classical_state_result = classical.get("classical_state_result")
        if isinstance(classical_state_result, dict):
            return classical_state_result
    return {}


def _needs_input(question_id, prompt, recommended=None, options=None):
    payload = {
        "status": "needs_input",
        "question": {
            "id": question_id,
            "prompt": prompt,
        },
    }
    if recommended is not None:
        payload["recommended"] = recommended
    if options is not None:
        payload["question"]["options"] = list(options)
    return payload


def lswt_stability_precheck(model):
    classical = model.get("classical", {}) if isinstance(model, dict) else {}
    classical_state_result = _get_classical_state_result(model)
    effective_model = model.get("effective_model", {}) if isinstance(model, dict) else {}
    low_weight = effective_model.get("low_weight", []) if isinstance(effective_model, dict) else []
    chosen_method = classical_state_result.get("method", classical.get("chosen_method"))

    signals = []
    if chosen_method in {
        "luttinger-tisza",
        "generalized-lt",
        "spin-only-luttinger-tisza",
        "spin-only-generalized-lt",
    }:
        signals.append(f"classical_method={chosen_method}")
    if low_weight:
        signals.append("low_weight_terms_present")
        for term in low_weight:
            label = str(term.get("canonical_label", ""))
            if "Sx@" in label and "Sz@" in label:
                signals.append(f"cross_axis_term={label}")
                break
    if model.get("lt_result") or model.get("generalized_lt_result"):
        signals.append("lt_family_reference_state")

    if signals:
        return {
            "status": "warn",
            "summary": (
                "LSWT will proceed from a classical reference that may be fragile because weak anisotropy or "
                "LT-family reference-state assumptions are still visible in the current model."
            ),
            "signals": signals,
        }
    return {"status": "ok", "summary": "", "signals": []}


def classical_stage_decision(model, user_choice=None, timed_out=False, allow_auto_select=False):
    choice = choose_method(
        model,
        user_choice=user_choice,
        timed_out=timed_out if allow_auto_select else False,
        allow_auto_select=allow_auto_select,
    )
    if choice.get("method") is None:
        recommended = choice.get("recommended")
        return _needs_input(
            "classical_method",
            f"Choose the classical ground-state solver. Recommended: {recommended}.",
            recommended=recommended,
            options=["luttinger-tisza", "generalized-lt", "variational"],
        )
    return {
        "status": "ok",
        "method": choice["method"],
        "recommended": choose_method(model, user_choice=None, timed_out=False).get("recommended", choice["method"]),
        "auto_selected": bool(choice.get("auto_selected", False)),
    }


def thermodynamics_stage_decision(run_thermodynamics=None):
    if run_thermodynamics is None:
        return _needs_input(
            "run_thermodynamics",
            "Run the finite-temperature classical thermodynamics stage after the ground-state solve?",
            recommended=False,
            options=[False, True],
        )
    return {"status": "ok", "enabled": bool(run_thermodynamics)}


def linear_spin_wave_stage_decision(model, run_lswt=None, q_path_mode=None):
    if run_lswt is None:
        return _needs_input(
            "run_lswt",
            "Continue to the linear spin-wave stage after the classical result?",
            recommended=True,
            options=[True, False],
        )
    if not run_lswt:
        return {"status": "ok", "enabled": False}

    classical_state_result = _get_classical_state_result(model)
    downstream_compatibility = (
        classical_state_result.get("downstream_compatibility", {})
        if isinstance(classical_state_result, dict)
        else {}
    )
    lswt_compatibility = downstream_compatibility.get("lswt", {}) if isinstance(downstream_compatibility, dict) else {}
    if lswt_compatibility.get("status") == "blocked":
        return {
            "status": "blocked",
            "enabled": False,
            "reason": lswt_compatibility.get("reason"),
            "method": classical_state_result.get("method"),
        }

    precheck = lswt_stability_precheck(model)
    if precheck.get("status") == "warn":
        signal_text = ", ".join(precheck.get("signals", []))
        return _needs_input(
            "lswt_stability_precheck",
            (
                "Stability precheck raised concerns before LSWT. "
                f"{precheck.get('summary', '')} "
                f"Signals: {signal_text}. "
                "Continue anyway, or stop and review the classical result first?"
            ).strip(),
            recommended="continue",
            options=["continue", "stop"],
        )

    explicit_q_path = model.get("q_path", [])
    if explicit_q_path:
        return {"status": "ok", "enabled": True, "q_path_mode": "user-specified"}
    if q_path_mode is None:
        return _needs_input(
            "lswt_q_path_mode",
            "No LSWT q-path was provided. Use the automatically generated high-symmetry path or stop and provide one explicitly?",
            recommended="auto",
            options=["auto", "user-specified"],
        )
    return {"status": "ok", "enabled": True, "q_path_mode": q_path_mode}


def exact_diagonalization_stage_decision(model, run_exact_diagonalization=None):
    if "cluster_size" not in model or "local_dim" not in model:
        return {"status": "ok", "enabled": False, "available": False}
    if run_exact_diagonalization is None:
        return _needs_input(
            "run_exact_diagonalization",
            "A small-cluster exact-diagonalization branch is available for this payload. Run it after LSWT?",
            recommended=False,
            options=[False, True],
        )
    return {"status": "ok", "enabled": bool(run_exact_diagonalization), "available": True}
