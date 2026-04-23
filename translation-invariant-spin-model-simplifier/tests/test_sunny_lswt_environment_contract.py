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

    def test_launcher_builds_p1_crystal_to_avoid_reimposing_space_group_symmetry(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertTrue('Crystal(latvecs, positions, 1;' in content or 'Crystal(latvecs, positions, "P1"' in content)

    def test_launcher_imports_linearalgebra_for_onsite_quadratic_forms(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("using LinearAlgebra", content)

    def test_launcher_does_not_lower_spin_cartesian_onsite_terms_with_dot_product_shortcut(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertNotIn("dot(S, onsite_matrix * S)", content)

    def test_launcher_supports_compact_single_q_reference_state_contract(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("single_q_reference_state", content)
        self.assertIn("rotation_axis", content)
        self.assertIn("reference_frames", content)

    def test_launcher_uses_spiral_spin_wave_theory_for_single_q_contracts(self):
        content = LSWT_LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("SpinWaveTheorySpiral", content)
        self.assertIn("single_q_reference_state", content)
        self.assertIn("k=", content)
        self.assertIn("axis=", content)


if __name__ == "__main__":
    unittest.main()
