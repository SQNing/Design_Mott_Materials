"""Phase A: research routing for sunny/quantum backends fails closed."""
import sys
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from research.adapters import capability_for


def spin_model():
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {"lattice_vectors": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                              "basis_sites": [{"site": 0, "position": [0, 0, 0]}]},
        "local_hilbert": {"classical_spaces": {
            "s0": {"kind": "unit_vector_sphere", "dimension": 3}}},
        "terms": [{"term_ref": "j1", "operator_family": "bilinear_exchange_matrix",
                   "arity": 2,
                   "cluster": [{"site": 0, "translation": [0, 0, 0]},
                               {"site": 0, "translation": [1, 0, 0]}],
                   "coefficient": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}],
    }


def cpn_model():
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {"lattice_vectors": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                              "basis_sites": [{"site": 0, "position": [0, 0, 0]}]},
        "local_hilbert": {"classical_spaces": {
            "s0": {"kind": "complex_projective_space", "dimension": 3}}},
        "terms": [{"term_ref": "p1", "operator_family": "pair_matrix", "arity": 2,
                   "cluster": [{"site": 0, "translation": [0, 0, 0]},
                               {"site": 0, "translation": [1, 0, 0]}],
                   "coefficient": [[0] * 9] * 9}],
    }


def _probe(available, command="julia", detail="fake probe"):
    return {"command": command if available else None, "available": available,
            "source": "test", "detail": detail}


class DeclaredBackendRoutingTests(unittest.TestCase):
    def test_dmrg_task_is_environment_gated(self):
        # Stage D: the DMRG route is connected but environment-gated.  When the
        # local Julia/ITensor environment is available the route is supported;
        # otherwise it fails closed with an explicit backend-not-connected
        # blocker and never silently falls back to another solver.
        cap = capability_for(spin_model(), "quantum_ground_state_dmrg", {})
        if cap["status"] == "supported":
            self.assertEqual(cap["solver_id"], "quantum-dmrg-itensor")
        else:
            self.assertEqual(cap["status"], "unsupported")
            self.assertTrue(
                cap["blocker"].startswith("backend-not-connected: julia-unavailable")
                or cap["blocker"].startswith(
                    "backend-not-connected: itensor-environment-not-instantiated"),
                cap["blocker"])

    def test_dmrg_task_fails_closed_without_julia(self):
        unavailable = {"available": False, "detail": "no julia on PATH"}
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=unavailable):
            cap = capability_for(spin_model(), "quantum_ground_state_dmrg", {})
        self.assertEqual(cap["status"], "unsupported")
        self.assertEqual(cap["blocker"],
                         "backend-not-connected: julia-unavailable (no julia on PATH)")

    def test_vmc_task_is_environment_gated(self):
        cap = capability_for(spin_model(), "quantum_ground_state_vmc", {})
        if cap["status"] == "supported":
            self.assertEqual(cap["solver_id"], "quantum-vmc-netket")
        else:
            self.assertEqual(cap["status"], "unsupported")
            self.assertTrue(
                cap["blocker"].startswith("backend-not-connected: netket-unavailable"),
                cap["blocker"])

    def test_vmc_task_fails_closed_without_netket(self):
        with mock.patch("quantum.vmc_driver._probe_netket",
                        return_value=(None, False, "venv missing")):
            cap = capability_for(spin_model(), "quantum_ground_state_vmc", {})
        self.assertEqual(cap["status"], "unsupported")
        self.assertEqual(cap["blocker"],
                         "backend-not-connected: netket-unavailable (venv missing)")

    def test_explicit_backend_alias_is_environment_gated(self):
        for backend in ("dmrg", "itensor", "mps"):
            cap = capability_for(spin_model(), "quantum_low_energy",
                                 {"backend": backend, "supercell_shape": [1, 1, 1], "spin": 0.5})
            if cap["status"] == "supported":
                self.assertEqual(cap["solver_id"], "quantum-dmrg-itensor", backend)
            else:
                self.assertTrue(cap["blocker"].startswith("backend-not-connected:"),
                                (backend, cap["blocker"]))
        for backend in ("vmc", "netket"):
            cap = capability_for(spin_model(), "quantum_low_energy",
                                 {"backend": backend, "supercell_shape": [1, 1, 1], "spin": 0.5})
            if cap["status"] == "supported":
                self.assertEqual(cap["solver_id"], "quantum-vmc-netket", backend)
            else:
                self.assertTrue(cap["blocker"].startswith("backend-not-connected:"),
                                (backend, cap["blocker"]))

    def test_explicit_backend_alias_fails_closed_without_environments(self):
        unavailable = {"available": False, "detail": "no julia on PATH"}
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=unavailable):
            for backend in ("dmrg", "itensor", "mps"):
                cap = capability_for(spin_model(), "quantum_low_energy",
                                     {"backend": backend, "supercell_shape": [1, 1, 1],
                                      "spin": 0.5})
                self.assertEqual(
                    cap["blocker"],
                    "backend-not-connected: julia-unavailable (no julia on PATH)",
                    backend)
        with mock.patch("quantum.vmc_driver._probe_netket",
                        return_value=(None, False, "venv missing")):
            for backend in ("vmc", "netket"):
                cap = capability_for(spin_model(), "quantum_low_energy",
                                     {"backend": backend, "supercell_shape": [1, 1, 1],
                                      "spin": 0.5})
                self.assertEqual(
                    cap["blocker"],
                    "backend-not-connected: netket-unavailable (venv missing)",
                    backend)

    def test_unknown_backend_fails_closed(self):
        cap = capability_for(spin_model(), "classical_ground_state", {"backend": "qmc"})
        self.assertEqual(cap["blocker"], "backend-not-connected: qmc")


class QuantumGateRoutingTests(unittest.TestCase):
    def test_ed_within_limits_supported(self):
        cap = capability_for(spin_model(), "quantum_low_energy",
                             {"supercell_shape": [2, 1, 1], "spin": 0.5})
        self.assertEqual(cap["status"], "supported")
        self.assertEqual(cap["solver_id"], "periodic-spin-python")

    def test_ed_oversized_blocked_at_routing(self):
        cap = capability_for(spin_model(), "quantum_low_energy",
                             {"supercell_shape": [4, 4, 4], "spin": 0.5})
        self.assertEqual(cap["status"], "unsupported")
        self.assertEqual(cap["blocker"], "quantum-ed-dimension-exceeded")

    def test_ed_without_spin_needs_input(self):
        cap = capability_for(spin_model(), "quantum_low_energy",
                             {"supercell_shape": [2, 1, 1]})
        self.assertEqual(cap["status"], "unsupported")
        self.assertEqual(cap["blocker"], "quantum_cluster")

    def test_quantum_on_cpn_model_explicitly_not_connected(self):
        cap = capability_for(cpn_model(), "quantum_low_energy",
                             {"supercell_shape": [1, 1, 1]})
        self.assertEqual(cap["status"], "unsupported")
        self.assertIn("retained local multiplets", cap["blocker"])


class SunnyRoutingTests(unittest.TestCase):
    def test_sunny_rejects_spin_only_model(self):
        cap = capability_for(spin_model(), "classical_ground_state", {"backend": "sunny"})
        self.assertEqual(cap["status"], "unsupported")
        self.assertIn("CP^(N-1)", cap["blocker"])

    def test_sunny_rejects_unconnected_task(self):
        cap = capability_for(cpn_model(), "spin_wave_spectrum", {"backend": "sunny"})
        self.assertEqual(cap["status"], "unsupported")
        self.assertIn("classical_ground_state", cap["blocker"])

    def test_sunny_without_julia_fails_closed(self):
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(False, detail="no julia anywhere")):
            cap = capability_for(cpn_model(), "classical_ground_state", {"backend": "sunny"})
        self.assertEqual(cap["status"], "unsupported")
        self.assertIn("backend-not-connected: julia-unavailable", cap["blocker"])
        self.assertIn("no julia anywhere", cap["blocker"])

    def test_sunny_classical_with_julia_supported(self):
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(True)):
            cap = capability_for(cpn_model(), "classical_ground_state", {"backend": "sunny"})
        self.assertEqual(cap["status"], "supported")
        self.assertEqual(cap["solver_id"], "sunny-sun-classical")
        self.assertEqual(cap["connection"], "environment-gated")

    def test_sunny_thermodynamics_with_julia_supported(self):
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(True)):
            cap = capability_for(cpn_model(), "classical_monte_carlo", {"backend": "sunny"})
        self.assertEqual(cap["solver_id"], "sunny-sun-thermodynamics")


class SunnyCalculationTests(unittest.TestCase):
    def _inputs(self, settings):
        return {"task": "classical_ground_state", "model": cpn_model(),
                "settings": {"backend": "sunny", **settings},
                "capability": {"solver_id": "sunny-sun-classical"},
                "reference": None, "result_id": "t1", "model_id": "m1",
                "code_identity": {}}

    def test_missing_julia_returns_unsupported_blocker(self):
        from research.adapters import run_calculation
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(False, detail="gone")):
            result = run_calculation(self._inputs({"supercell_shape": [1, 1, 1]}))
        self.assertEqual(result["execution_status"], "succeeded")
        self.assertEqual(result["scientific_status"], "unsupported")
        self.assertIn("julia-unavailable", result["blocker"])

    def test_supercell_shape_validated(self):
        from research.adapters import run_calculation
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(True)):
            with self.assertRaises(ValueError):
                run_calculation(self._inputs({"supercell_shape": [2, 2]}))
            with self.assertRaises(ValueError):
                run_calculation(self._inputs({}))

    def test_successful_backend_maps_to_calculation(self):
        from research.adapters import run_calculation
        backend_result = {
            "status": "ok", "method": "sunny-cpn-minimize",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "energy": -3.25, "supercell_shape": [1, 1, 1], "starts": 8, "seed": 0,
            "local_rays": [[{"real": 1.0, "imag": 0.0}, {"real": 0.0, "imag": 0.0},
                            {"real": 0.0, "imag": 0.0}]],
            "backend_stationarity": {"max_gradient": 1e-9},
        }
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(True)), \
             mock.patch("classical.sunny_sun_classical_driver.run_sunny_sun_classical",
                        return_value=backend_result) as driver:
            result = run_calculation(self._inputs({"supercell_shape": [1, 1, 1]}))
        driver.assert_called_once()
        payload = driver.call_args[0][0]
        self.assertEqual(payload["payload_kind"], "sunny_sun_classical")
        self.assertEqual(payload["model"]["classical_manifold"], "CP^(N-1)")
        self.assertEqual(result["scientific_status"], "usable_within_scope")
        calculation = result["calculation"]
        self.assertEqual(calculation["energy"], -3.25)
        self.assertEqual(calculation["method"], "sunny-cpn-minimize")
        self.assertEqual(calculation["classical_state"]["kind"], "local_rays")
        evidence = calculation["ground_state_evidence"]
        self.assertEqual(evidence["infinite_lattice_status"], "not_certified")

    def test_thermodynamics_unwraps_nested_backend_result(self):
        from research.adapters import run_calculation
        backend_result = {
            "status": "ok", "payload_kind": "sunny_sun_thermodynamics",
            "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": "sunny-local-sampler"},
            "thermodynamics_result": {
                "grid": [{"temperature": 1.0, "energy": -1.0, "heat_capacity": 0.2,
                          "magnetization": 0.1, "effective_sample_warning": True}],
                "observables": {"energy": [-1.0], "heat_capacity": [0.2],
                                "magnetization": [0.1]},
            },
        }
        inputs = {"task": "classical_monte_carlo", "model": cpn_model(),
                  "settings": {"backend": "sunny", "supercell_shape": [1, 1, 1],
                               "temperatures": [1.0]},
                  "capability": {"solver_id": "sunny-sun-thermodynamics"},
                  "reference": None, "result_id": "t2", "model_id": "m1",
                  "code_identity": {}}
        with mock.patch("research.adapters.probe_julia_environment",
                        return_value=_probe(True)), \
             mock.patch("classical.sunny_sun_thermodynamics_driver.run_sunny_sun_thermodynamics",
                        return_value=backend_result):
            result = run_calculation(inputs)
        calculation = result["calculation"]
        self.assertEqual(calculation["grid"][0]["temperature"], 1.0)
        self.assertEqual(calculation["observables"]["heat_capacity"], [0.2])
        self.assertEqual(result["scientific_status"], "inconclusive")
        diagnostics = {d["kind"]: d for d in result["diagnostics"]}
        self.assertFalse(diagnostics["effective_samples"]["satisfied"])
        self.assertFalse(diagnostics["equilibration"]["satisfied"])


if __name__ == "__main__":
    unittest.main()
