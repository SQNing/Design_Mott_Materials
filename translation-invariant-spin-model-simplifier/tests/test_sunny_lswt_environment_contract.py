import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LSWT_LAUNCHER = PROJECT_ROOT / "scripts" / "lswt" / "run_sunny_lswt.jl"
ENVIRONMENT_REFERENCE = PROJECT_ROOT / "reference" / "environment.md"


class SunnyLswtEnvironmentContractTests(unittest.TestCase):
    def test_launcher_points_to_canonical_v09_project(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertIn(".julia-env-v09", content)
        self.assertNotIn("scripts/.julia-env-v06", content)
        self.assertIn('joinpath(SCRIPT_DIR, "..", ".julia-depot")', content)

    def test_environment_reference_matches_phase1_contract(self):
        content = ENVIRONMENT_REFERENCE.read_text(encoding="utf-8")

        self.assertIn("Julia 1.12.x", content)
        self.assertIn("`Sunny.jl 0.9.x`", content)
        self.assertIn(".julia-env-v09", content)
        self.assertIn("scripts/.julia-depot", content)


if __name__ == "__main__":
    unittest.main()
