import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lswt.fei2_sunny_glswt_cases import classify_fei2_sunny_glswt_result


class FeI2SunnyGswtCasesTests(unittest.TestCase):
    def test_classify_contract_block_from_preflight_error(self):
        result = {
            "status": "error",
            "error": {
                "code": "unsupported-reduced-single-q-sun-gswt",
                "message": "reduced single-q state is not explicitly realized",
            },
        }

        summary = classify_fei2_sunny_glswt_result("official-single-q", result)

        self.assertEqual(summary["case_id"], "official-single-q")
        self.assertEqual(summary["category"], "blocked_by_contract")
        self.assertEqual(summary["error_code"], "unsupported-reduced-single-q-sun-gswt")

    def test_classify_backend_instability_as_allowed_but_unstable(self):
        result = {
            "status": "error",
            "error": {
                "code": "backend-execution-failed",
                "message": "Instability at wavevector q = [0.25, 0.0, 0.25]",
            },
            "diagnostics": {"instability": {"q_vector": [0.25, 0.0, 0.25]}},
        }

        summary = classify_fei2_sunny_glswt_result("python-abba", result)

        self.assertEqual(summary["case_id"], "python-abba")
        self.assertEqual(summary["category"], "allowed_but_unstable")
        self.assertEqual(summary["softest_q_vector"], [0.25, 0.0, 0.25])


if __name__ == "__main__":
    unittest.main()
