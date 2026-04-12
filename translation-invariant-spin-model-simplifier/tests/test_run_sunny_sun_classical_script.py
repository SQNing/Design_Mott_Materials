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

    def test_script_exports_backend_stationarity_diagnostics(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("using LinearAlgebra", source)
        self.assertIn("energy_grad_coherents", source)
        self.assertIn("backend_stationarity", source)

    def test_script_emits_progress_logs_to_stderr(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("println(stderr,", source)
        self.assertIn("start $(start_index)/$(starts)", source)


if __name__ == "__main__":
    unittest.main()
