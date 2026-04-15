import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "classical"
    / "run_sunny_sun_thermodynamics.jl"
)


class RunSunnySunThermodynamicsScriptTests(unittest.TestCase):
    def test_script_supports_local_sampler(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("LocalSampler", source)

    def test_script_supports_parallel_tempering(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("ParallelTempering", source)

    def test_script_supports_wang_landau(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertTrue("WangLandau" in source or "ParallelWangLandau" in source)

    def test_wang_landau_dos_result_accepts_windows_metadata(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('dos_result = Dict{String, Any}(', source)
        self.assertIn('dos_result["windows"] = [collect(bounds)]', source)

    def test_script_emits_progress_logs_to_stderr(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("println(stderr,", source)
        self.assertIn("[sunny-thermo]", source)

    def test_script_builds_p1_crystal_to_avoid_reimposing_space_group_symmetry(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertTrue('Crystal(latvecs, positions, 1;' in source or 'Crystal(latvecs, positions, "P1"' in source)


if __name__ == "__main__":
    unittest.main()
