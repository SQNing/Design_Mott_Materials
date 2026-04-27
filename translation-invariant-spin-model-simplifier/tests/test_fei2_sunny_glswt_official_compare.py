import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lswt.fei2_sunny_glswt_official_compare import run_official_compare


class FeI2SunnyGswtOfficialCompareTests(unittest.TestCase):
    def test_official_compare_cli_bootstraps_import_path_for_direct_script_execution(self):
        script = REPO_ROOT / "scripts" / "lswt" / "fei2_sunny_glswt_official_compare.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("--output-json", completed.stdout)

    def test_official_compare_writes_categorized_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "summary.json"
            output_markdown = Path(tmpdir) / "summary.md"

            with patch(
                "lswt.fei2_sunny_glswt_official_compare.run_sun_gswt",
                return_value={
                    "status": "ok",
                    "backend": {"name": "Sunny.jl", "mode": "SUN"},
                    "payload_kind": "sun_gswt_prototype",
                    "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0}],
                    "diagnostics": {"dispersion": {"omega_min": 0.0, "omega_min_q_vector": [0.0, 0.0, 0.0], "soft_mode_count": 0}},
                },
            ):
                run_official_compare(
                    output_json=output_json,
                    output_markdown=output_markdown,
                    cases=[{"case_id": "official-reshaped", "source": "official", "gswt_payload": {"payload_kind": "sun_gswt_prototype"}}],
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertIn("official_reference", payload)
            self.assertEqual(payload["cases"][0]["case_id"], "official-reshaped")
            self.assertIn(
                payload["cases"][0]["category"],
                {
                    "allowed_and_executed",
                    "allowed_but_unstable",
                    "blocked_by_contract",
                    "blocked_by_backend",
                },
            )
            self.assertTrue(output_markdown.is_file())


if __name__ == "__main__":
    unittest.main()
