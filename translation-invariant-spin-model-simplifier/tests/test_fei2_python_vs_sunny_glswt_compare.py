import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lswt.fei2_python_vs_sunny_glswt_compare import compare_python_vs_sunny_case


class FeI2PythonVsSunnyGswtCompareTests(unittest.TestCase):
    def test_python_vs_sunny_compare_cli_bootstraps_import_path_for_direct_script_execution(self):
        script = REPO_ROOT / "scripts" / "lswt" / "fei2_python_vs_sunny_glswt_compare.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("--output-json", completed.stdout)

    def test_python_vs_sunny_compare_skips_cases_blocked_by_contract(self):
        sunny_result = {
            "status": "error",
            "error": {
                "code": "unsupported-reduced-single-q-sun-gswt",
                "message": "not explicitly periodic",
            },
        }

        summary = compare_python_vs_sunny_case(
            case_id="official-single-q",
            python_result={"status": "ok", "dispersion": []},
            sunny_result=sunny_result,
        )

        self.assertEqual(summary["comparison_status"], "skipped")
        self.assertEqual(summary["reason"], "sunny-contract-invalid")

    def test_python_vs_sunny_compare_reports_omega_min_and_softest_q(self):
        python_result = {
            "status": "ok",
            "diagnostics": {
                "dispersion": {
                    "omega_min": -0.1,
                    "omega_min_q_vector": [0.25, 0.0, 0.25],
                    "soft_mode_count": 1,
                }
            },
        }
        sunny_result = {
            "status": "ok",
            "diagnostics": {
                "dispersion": {
                    "omega_min": -0.08,
                    "omega_min_q_vector": [0.25, 0.0, 0.25],
                    "soft_mode_count": 1,
                }
            },
        }

        summary = compare_python_vs_sunny_case(
            case_id="python-abba",
            python_result=python_result,
            sunny_result=sunny_result,
        )

        self.assertEqual(summary["comparison_status"], "compared")
        self.assertEqual(summary["python"]["omega_min"], -0.1)
        self.assertEqual(summary["sunny"]["omega_min"], -0.08)
        self.assertIn(
            summary["difference_bucket"],
            {"state_difference", "backend_physics_difference", "match_or_near_match"},
        )


if __name__ == "__main__":
    unittest.main()
