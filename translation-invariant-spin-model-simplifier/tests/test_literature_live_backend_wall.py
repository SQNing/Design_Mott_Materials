"""Tests for the live literature benchmark wall (G1)."""

import os
from pathlib import Path
import sys
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validation import literature_live_backend_wall as wall

_BENCHMARK_ON = (os.environ.get("SPINFORGE_BENCHMARK") == "1"
                 or os.environ.get("DMM_BENCHMARK") == "1")


def _dmrg_ok_runner(energy):
    def runner(model, request):
        return {"status": "ok",
                "calculation": {"energy": energy, "converged": True}}
    return runner


class LiveWallRegistryTests(unittest.TestCase):
    def test_bindings_reference_existing_registry_entries(self):
        from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS
        names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
        for binding in wall.LIVE_WALL_BINDINGS:
            self.assertIn(binding.name, names)

    def test_bindings_match_registry_backend_tags(self):
        expected = {
            "xxx_spin_half_chain_bethe_ground_state": "bethe_or_extrapolated_ed",
            "triangular_heisenberg_spin_half_energy_reference": "dmrg_or_vmc",
        }
        for binding in wall.LIVE_WALL_BINDINGS:
            entry = wall._ENTRIES[binding.name]
            self.assertEqual(entry["backend_needed"], expected[binding.name])

    def test_bethe_solver_recovers_exact_references(self):
        self.assertAlmostEqual(wall.bethe_ground_state_energy(4), -2.0, places=10)
        self.assertAlmostEqual(
            wall.bethe_ground_state_energy(100), -44.32295707509192, places=12)

    def test_gated_bindings_skip_cleanly_when_wall_disabled(self):
        report = wall.evaluate_live_wall(include_gated=False)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["alarms"], [])
        self.assertTrue(all(row["status"] == "skipped-gated" for row in report["rows"]))


class LiveWallFakeRunnerTests(unittest.TestCase):
    def test_dmrg_binding_passes_at_finite_n_bethe(self):
        reference = wall.bethe_ground_state_energy(100)
        entry = wall._ENTRIES["xxx_spin_half_chain_bethe_ground_state"]
        row = wall._check_dmrg_xxx_chain_bethe(entry, _dmrg_ok_runner(reference))
        self.assertEqual(row.status, "pass")
        self.assertAlmostEqual(row.measured, reference, places=12)

    def test_dmrg_binding_fails_and_alarms_on_energy_regression(self):
        reference = wall.bethe_ground_state_energy(100)
        entry = wall._ENTRIES["xxx_spin_half_chain_bethe_ground_state"]
        row = wall._check_dmrg_xxx_chain_bethe(entry, _dmrg_ok_runner(reference * 0.99))
        self.assertEqual(row.status, "fail")

        def fake_runner(model, request):
            if request["task"] == "quantum_ground_state_dmrg":
                return {"status": "ok",
                        "calculation": {"energy": reference * 0.99, "converged": True}}
            return {"status": "ok",
                    "calculation": {"energy": wall.TRIANGULAR_N12_ED_ENERGY}}
        report = wall.evaluate_live_wall(include_gated=True, runner=fake_runner)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("xxx_spin_half_chain_bethe" in alarm
                            for alarm in report["alarms"]))

    def test_dmrg_binding_fails_when_not_converged(self):
        entry = wall._ENTRIES["xxx_spin_half_chain_bethe_ground_state"]

        def runner(model, request):
            return {"status": "inconclusive",
                    "calculation": {"energy": -44.3, "converged": False,
                                    "blocker": "variance-not-certified"}}
        row = wall._check_dmrg_xxx_chain_bethe(entry, runner)
        self.assertEqual(row.status, "fail")
        self.assertIn("variance-not-certified", row.detail)

    def test_backend_not_connected_skips_without_alarm(self):
        def runner(model, request):
            return {"status": "backend-not-connected", "blocker": "no julia"}
        report = wall.evaluate_live_wall(include_gated=True, runner=runner)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["alarms"], [])
        self.assertTrue(all(row["status"] == "backend-not-connected"
                            for row in report["rows"]))

    def test_vmc_binding_rejects_variational_principle_violation(self):
        entry = wall._ENTRIES["triangular_heisenberg_spin_half_energy_reference"]

        def runner(model, request):
            return {"status": "ok",
                    "calculation": {"energy": wall.TRIANGULAR_N12_ED_ENERGY * 1.01}}
        row = wall._check_vmc_triangular_energy(entry, runner)
        self.assertEqual(row.status, "fail")
        self.assertIn("variational principle", row.detail)

    def test_vmc_binding_passes_within_tolerance(self):
        entry = wall._ENTRIES["triangular_heisenberg_spin_half_energy_reference"]

        def runner(model, request):
            return {"status": "ok",
                    "calculation": {"energy": wall.TRIANGULAR_N12_ED_ENERGY * 0.99}}
        row = wall._check_vmc_triangular_energy(entry, runner)
        self.assertEqual(row.status, "pass")


@unittest.skipUnless(_BENCHMARK_ON, "benchmark wall; run with SPINFORGE_BENCHMARK=1")
class LiveWallBenchmarkTests(unittest.TestCase):
    def test_live_wall_passes_with_real_backends(self):
        report = wall.evaluate_live_wall(include_gated=True)
        failing = [row for row in report["rows"]
                   if row["status"] not in {"pass", "backend-not-connected"}]
        self.assertEqual(failing, [], report["alarms"])
        self.assertEqual(report["alarms"], [])


if __name__ == "__main__":
    unittest.main()
