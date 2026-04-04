#!/usr/bin/env python3

from classical_solver_driver import choose_method


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
            options=["luttinger-tisza", "variational"],
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
