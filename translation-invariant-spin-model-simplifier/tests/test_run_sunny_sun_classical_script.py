import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "classical"
    / "run_sunny_sun_classical.jl"
)


class RunSunnySunClassicalScriptTests(unittest.TestCase):
    def test_script_uses_minimize_energy(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("minimize_energy!", source)

    def test_script_keeps_full_pair_operator(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("extract_parts=false", source)


if __name__ == "__main__":
    unittest.main()
