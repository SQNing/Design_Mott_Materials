"""Independent checks of periodic dipolar energy conventions."""

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_cubic_one_dipole_has_correct_surface_and_self_terms():
    # A missing self term breaks alpha invariance; a wrong k=0 convention
    # breaks the known spherical sum (zero for a uniformly magnetized cube).
    from three_dimensional.workflow import run_three_dimensional_workflow
    geometry = {"lattice_vectors": (3 * np.eye(3)).tolist(),
                "fractional_positions": [[0, 0, 0]], "moments": [[0, 0, 1]]}
    common = {"task": "dipolar_ewald", "alpha": 0.9,
              "real_cutoff": 9.0, "reciprocal_cutoff": 12.0}
    tin = run_three_dimensional_workflow(geometry, {**common, "boundary": "tin_foil"})
    vacuum = run_three_dimensional_workflow(geometry, {**common, "boundary": "vacuum_sphere"})
    assert tin["status"] == vacuum["status"] == "ok"
    assert tin["calculation"]["energy_total"] == pytest.approx(-2 * np.pi / 81, abs=1e-10)
    assert vacuum["calculation"]["energy_total"] == pytest.approx(0.0, abs=1e-10)


def test_triclinic_ewald_alpha_invariance_and_moment_gradient():
    from three_dimensional.ewald import dipolar_ewald
    geometry = {"lattice_vectors": [[3.0, 0, 0], [0.4, 2.9, 0], [0.2, 0.3, 3.1]],
                "fractional_positions": [[0.1, 0.2, 0.3], [0.6, 0.4, 0.8]],
                "moments": [[0.2, -0.3, 0.7], [-0.5, 0.1, -0.4]]}
    request = {"alpha": 0.75, "real_cutoff": 10.0,
               "reciprocal_cutoff": 13.0, "boundary": "vacuum_sphere"}
    first = dipolar_ewald(geometry, request)
    second = dipolar_ewald(geometry, {**request, "alpha": 1.1})
    assert first["energy_total"] == pytest.approx(second["energy_total"], abs=1e-11)
    moments = np.array(geometry["moments"])
    delta = np.zeros_like(moments)
    delta[1, 2] = 1e-5
    plus = dipolar_ewald({**geometry, "moments": (moments + delta).tolist()}, request)
    minus = dipolar_ewald({**geometry, "moments": (moments - delta).tolist()}, request)
    numerical = (plus["energy_total"] - minus["energy_total"]) / 2e-5
    assert first["moment_gradient"][1][2] == pytest.approx(numerical, abs=1e-10)
