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


if __name__ == "__main__":
    unittest.main()
