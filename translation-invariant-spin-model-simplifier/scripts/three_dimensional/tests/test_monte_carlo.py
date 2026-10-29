import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_workflow import cubic_model


def test_periodic_dimer_sampling_uses_extensive_acceptance_energy():
    # In a 2x1x1 cubic torus: H=2 S0.S1+4 for unit spins. Integrating their
    # relative angle gives E/site=2+1/x-coth(x), x=2/T, and C/site below.
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(), {
        "task": "classical_monte_carlo", "supercell_shape": [2, 1, 1],
        "spin_length": 1.0, "temperatures": [0.8],
        "burn_in": 1500, "sweeps": 15000, "seed": 317,
    })
    assert result["status"] == "ok"
    row = result["calculation"]["grid"][0]
    x = 2 / 0.8
    expected = 2 + 1 / x - 1 / np.tanh(x)
    assert abs(row["energy_per_site"] - expected) < max(0.025, 5 * row["energy_stderr"])
    assert row["heat_capacity_per_site"] == pytest.approx(0.5 * (1 - x ** 2 / np.sinh(x) ** 2), abs=0.035)
    assert row["energy_effective_samples"] < row["samples"]


def test_finite_size_runs_preserve_cubic_volumes_and_observable_definitions():
    from three_dimensional.workflow import run_three_dimensional_workflow
    result = run_three_dimensional_workflow(cubic_model(-1.0), {
        "task": "classical_finite_size", "supercell_shapes": [[2, 2, 2], [3, 3, 3]],
        "spin_length": 1.0, "temperatures": [0.7, 3.0],
        "burn_in": 150, "sweeps": 500, "seed": 44,
    })
    assert result["status"] == "ok"
    runs = result["calculation"]["sizes"]
    assert [run["site_count"] for run in runs] == [8, 27]
    for run in runs:
        assert run["grid"][0]["order_parameter_squared"] > run["grid"][1]["order_parameter_squared"]
        for point in run["grid"]:
            assert point["binder_cumulant"] == pytest.approx(1 - point["binder_ratio"] / 3)
    assert result["calculation"]["critical_temperature_certified"] is False
