#!/usr/bin/env python3

from classical.classical_solver_driver import estimate_thermodynamics
from classical.sunny_sun_thermodynamics_driver import run_sunny_sun_thermodynamics
from common.downstream_stage_routing import resolve_downstream_stage_route
from lswt.linear_spin_wave_driver import run_linear_spin_wave
from lswt.python_glswt_driver import run_python_glswt_driver
from lswt.sun_gswt_driver import run_sun_gswt


def _thermodynamics_settings(payload):
    thermodynamics = payload.get("thermodynamics") if isinstance(payload, dict) else None
    return thermodynamics if isinstance(thermodynamics, dict) else {}


def _execute_spin_only_thermodynamics(payload):
    thermodynamics = _thermodynamics_settings(payload)
    return estimate_thermodynamics(
        payload,
        thermodynamics["temperatures"],
        sweeps=int(thermodynamics.get("sweeps", 100)),
        burn_in=int(thermodynamics.get("burn_in", 50)),
        seed=int(thermodynamics.get("seed", 0)),
        measurement_interval=int(thermodynamics.get("measurement_interval", 1)),
        field_direction=thermodynamics.get("field_direction"),
        high_temperature_entropy=float(thermodynamics.get("high_temperature_entropy", 0.0)),
        energy_infinite_temperature=thermodynamics.get("energy_infinite_temperature"),
        scan_order=str(thermodynamics.get("scan_order", "as_given")),
        reuse_configuration=bool(thermodynamics.get("reuse_configuration", True)),
    )


def select_downstream_backend(payload, stage_name):
    route = resolve_downstream_stage_route(payload, stage_name)
    backend = route.get("recommended_backend")
    if backend is not None:
        return str(backend)
    raise ValueError(f"no backend available for downstream stage: {stage_name}")


def execute_downstream_stage(payload, stage_name):
    route = resolve_downstream_stage_route(payload, stage_name)
    if not route.get("enabled"):
        reason = route.get("reason") or "route is blocked"
        raise ValueError(f"{stage_name} stage is blocked: {reason}")

    backend = select_downstream_backend(payload, stage_name)

    if backend == "linear_spin_wave":
        return run_linear_spin_wave(payload)

    if backend == "python_glswt":
        gswt_payload = payload.get("gswt_payload")
        if not isinstance(gswt_payload, dict):
            raise ValueError("gswt stage requires a gswt_payload for the python backend")
        return run_python_glswt_driver(gswt_payload)

    if backend == "sun_gswt":
        return run_sun_gswt(payload)

    if backend == "spin_only_thermodynamics":
        return _execute_spin_only_thermodynamics(payload)

    if backend == "sunny_thermodynamics":
        return run_sunny_sun_thermodynamics(payload)

    raise ValueError(f"unsupported downstream backend: {backend}")
