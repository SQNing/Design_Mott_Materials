import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = TEST_ROOT / "scripts"

SUNNY_FAMILY_SCRIPTS = [
    SCRIPTS_ROOT / "classical" / "run_sunny_sun_classical.jl",
    SCRIPTS_ROOT / "classical" / "run_sunny_sun_thermodynamics.jl",
    SCRIPTS_ROOT / "lswt" / "run_sunny_sun_gswt.jl",
]


class SunnyFamilyEnvironmentContractTests(unittest.TestCase):
    def test_remaining_sunny_family_launchers_use_phase1_project_baseline(self):
        for script_path in SUNNY_FAMILY_SCRIPTS:
            with self.subTest(script_path=script_path.name):
                source = script_path.read_text(encoding="utf-8")
                self.assertIn(".julia-env-v09", source)
                self.assertNotIn(".julia-env-v06", source)

    def test_remaining_sunny_family_launchers_continue_to_use_repo_local_depot(self):
        for script_path in SUNNY_FAMILY_SCRIPTS:
            with self.subTest(script_path=script_path.name):
                source = script_path.read_text(encoding="utf-8")
                self.assertIn('.julia-depot', source)


if __name__ == "__main__":
    unittest.main()
