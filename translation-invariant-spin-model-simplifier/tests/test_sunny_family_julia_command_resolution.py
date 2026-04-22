import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical import sunny_sun_classical_driver as classical_driver
from classical import sunny_sun_thermodynamics_driver as thermodynamics_driver
from lswt import sun_gswt_driver as gswt_driver


def _completed_stdout(payload):
    class Completed:
        stdout = json.dumps(payload)

    return Completed()


def _classical_payload():
    return {
        "payload_kind": "sunny_sun_classical",
        "backend": "Sunny.jl",
    }


def _thermodynamics_payload():
    return {
        "payload_kind": "sunny_sun_thermodynamics",
        "backend": "Sunny.jl",
    }


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _gswt_payload():
    return {
        "payload_version": 2,
        "backend": "Sunny.jl",
        "mode": "SUN",
        "payload_kind": "sun_gswt_prototype",
        "basis_order": "orbital_major_spin_minor",
        "local_dimension": 2,
        "orbital_count": 1,
        "pair_basis_order": "site_i_major_site_j_minor",
        "local_basis_labels": ["up", "down"],
        "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "positions": [[0.0, 0.0, 0.0]],
        "pair_couplings": [
            {
                "R": [1, 0, 0],
                "pair_matrix": [
                    [_serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(1.0), _serialize_complex(0.0), _serialize_complex(0.0)],
                    [_serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(0.0), _serialize_complex(1.0)],
                ],
                "tensor_shape": [2, 2, 2, 2],
            }
        ],
        "initial_local_rays": [
            {"cell": [0, 0, 0], "vector": [_serialize_complex(1.0), _serialize_complex(0.0)]},
        ],
        "classical_reference": {
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "frame_construction": "first-column-is-reference-ray",
        },
        "supercell_shape": [1, 1, 1],
        "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
    }


class SunnyFamilyJuliaCommandResolutionTests(unittest.TestCase):
    def test_classical_driver_prefers_environment_julia_override(self):
        payload = _classical_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_classical.jl"))
            backend_payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            self.assertEqual(backend_payload["payload_kind"], "sunny_sun_classical")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=fake_run):
                result = classical_driver.run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "ok")

    def test_classical_driver_falls_back_to_plain_julia_without_override(self):
        payload = _classical_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {}, clear=True):
            with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=fake_run):
                result = classical_driver.run_sunny_sun_classical(payload)

        self.assertEqual(result["status"], "ok")

    def test_classical_cli_entrypoint_preserves_environment_julia_override(self):
        payload = _classical_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch.object(classical_driver, "_load_payload", return_value=payload):
                with patch("classical.sunny_sun_classical_driver.subprocess.run", side_effect=fake_run):
                    with patch.object(sys, "argv", ["sunny_sun_classical_driver.py"]):
                        self.assertEqual(classical_driver.main(), 0)

    def test_thermodynamics_driver_prefers_environment_julia_override(self):
        payload = _thermodynamics_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_thermodynamics.jl"))
            backend_payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            self.assertEqual(backend_payload["payload_kind"], "sunny_sun_thermodynamics")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=fake_run):
                result = thermodynamics_driver.run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "ok")

    def test_thermodynamics_driver_falls_back_to_plain_julia_without_override(self):
        payload = _thermodynamics_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "julia")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {}, clear=True):
            with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=fake_run):
                result = thermodynamics_driver.run_sunny_sun_thermodynamics(payload)

        self.assertEqual(result["status"], "ok")

    def test_thermodynamics_cli_entrypoint_preserves_environment_julia_override(self):
        payload = _thermodynamics_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            return _completed_stdout({"status": "ok", "backend": {"name": "Sunny.jl", "mode": "SUN"}})

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch.object(thermodynamics_driver, "_load_payload", return_value=payload):
                with patch("classical.sunny_sun_thermodynamics_driver.subprocess.run", side_effect=fake_run):
                    with patch.object(sys, "argv", ["sunny_sun_thermodynamics_driver.py"]):
                        self.assertEqual(thermodynamics_driver.main(), 0)

    def test_gswt_driver_prefers_environment_julia_override(self):
        payload = _gswt_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            self.assertTrue(command[1].endswith("run_sunny_sun_gswt.jl"))
            backend_payload = json.loads(Path(command[2]).read_text(encoding="utf-8"))
            self.assertEqual(backend_payload["payload_kind"], "sun_gswt_prototype")
            return _completed_stdout(
                {
                    "status": "ok",
                    "backend": {"name": "Sunny.jl", "mode": "SUN"},
                    "payload_kind": "sun_gswt_prototype",
                    "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0}],
                }
            )

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch("lswt.sun_gswt_driver.subprocess.run", side_effect=fake_run):
                result = gswt_driver.run_sun_gswt(payload)

        self.assertEqual(result["status"], "ok")

    def test_gswt_driver_prefers_repo_wrapper_without_override(self):
        payload = _gswt_payload()

        def fake_run(command, check, capture_output, text):
            self.assertTrue(command[0].endswith("run_project_julia.sh"))
            return _completed_stdout(
                {
                    "status": "ok",
                    "backend": {"name": "Sunny.jl", "mode": "SUN"},
                    "payload_kind": "sun_gswt_prototype",
                    "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0}],
                }
            )

        with patch.dict("os.environ", {}, clear=True):
            with patch("lswt.sun_gswt_driver.subprocess.run", side_effect=fake_run):
                result = gswt_driver.run_sun_gswt(payload)

        self.assertEqual(result["status"], "ok")

    def test_gswt_cli_entrypoint_preserves_environment_julia_override(self):
        payload = _gswt_payload()

        def fake_run(command, check, capture_output, text):
            self.assertEqual(command[0], "/tmp/julia-1.12/bin/julia")
            return _completed_stdout(
                {
                    "status": "ok",
                    "backend": {"name": "Sunny.jl", "mode": "SUN"},
                    "payload_kind": "sun_gswt_prototype",
                    "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0}],
                }
            )

        with patch.dict("os.environ", {"DESIGN_MOTT_JULIA_CMD": "/tmp/julia-1.12/bin/julia"}, clear=False):
            with patch.object(gswt_driver, "_load_payload", return_value=payload):
                with patch("lswt.sun_gswt_driver.subprocess.run", side_effect=fake_run):
                    with patch.object(sys, "argv", ["sun_gswt_driver.py"]):
                        self.assertEqual(gswt_driver.main(), 0)


if __name__ == "__main__":
    unittest.main()
