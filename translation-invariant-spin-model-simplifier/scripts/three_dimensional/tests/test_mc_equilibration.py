"""Monte Carlo equilibration certification tests (stage C, fix G4)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_workflow import cubic_model

from three_dimensional.workflow import run_three_dimensional_workflow


def _run(sweeps=20000, burn_in=2000, seed=317, **extra):
    request = {"task": "classical_monte_carlo", "supercell_shape": [2, 1, 1],
               "spin_length": 1.0, "temperatures": [0.8],
               "burn_in": burn_in, "sweeps": sweeps, "seed": seed}
    request.update(extra)
    result = run_three_dimensional_workflow(cubic_model(), request)
    assert result["status"] == "ok"
    return result["calculation"]


def test_long_run_certifies_equilibration():
    calc = _run(sweeps=20000, burn_in=2000)
    row = calc["grid"][0]
    assert "equilibration" in row
    block = row["equilibration"]
    assert block["z_energy"] <= block["z_limit"]
    assert block["z_order"] <= block["z_limit"]
    assert block["span_tau_lengths"] >= block["min_tau_lengths"]
    assert block["certified"] is True
    assert calc["sampling"]["equilibration_verified"] is True
    assert "equilibration_status" not in calc


def test_undersampled_run_reports_not_certified():
    # Deliberately short: a handful of correlation times at best.
    calc = _run(sweeps=40, burn_in=5)
    row = calc["grid"][0]
    block = row["equilibration"]
    assert block["certified"] is False
    assert block["failure_reasons"]
    assert calc["sampling"]["equilibration_verified"] is False
    assert calc["equilibration_status"] == "equilibration_not_certified"


def test_second_chain_is_independent_but_consistent():
    # Same seed reruns must reproduce chain 1 exactly while chain 2 differs.
    calc_a = _run(sweeps=2000, burn_in=200, seed=77)
    calc_b = _run(sweeps=2000, burn_in=200, seed=77)
    row_a, row_b = calc_a["grid"][0], calc_b["grid"][0]
    assert row_a["energy_per_site"] == pytest.approx(row_b["energy_per_site"], abs=0.0)
    assert row_a["equilibration"]["second_chain_seed"] == row_b["equilibration"]["second_chain_seed"]


def test_thermodynamics_v1_block_attached():
    calc = _run(sweeps=2000, burn_in=200)
    block = calc["thermodynamics_v1"]
    assert block["schema_version"] == "thermodynamics/v1"
    assert block["source"] == "classical_mc"
    assert len(block["grid"]) == 1
    entry = block["grid"][0]
    assert entry["energy_per_site"]["value"] == pytest.approx(
        calc["grid"][0]["energy_per_site"])
    assert entry["entropy_per_site"]["value"] is None
    assert "equilibration_certified" in block


def test_certification_can_be_disabled():
    calc = _run(sweeps=2000, burn_in=200, certify_equilibration=False)
    assert "equilibration" not in calc["grid"][0]
    assert calc["sampling"]["equilibration_verified"] is False
