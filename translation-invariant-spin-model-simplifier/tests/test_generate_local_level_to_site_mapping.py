import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.generate_local_level_to_site_mapping import main


class GenerateLocalLevelToSiteMappingTests(unittest.TestCase):
    def test_cli_emits_mapping_for_levels_per_site(self):
        stdout = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "generate_local_level_to_site_mapping.py",
                "--levels-per-site",
                "2,2",
            ],
        ):
            with redirect_stdout(stdout):
                exit_code = main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            payload["site_level_mapping"],
            [
                {"site": 0, "level_indexes": [0, 1]},
                {"site": 1, "level_indexes": [2, 3]},
            ],
        )

    def test_cli_rejects_non_positive_levels_per_site(self):
        with patch.object(
            sys,
            "argv",
            [
                "generate_local_level_to_site_mapping.py",
                "--levels-per-site",
                "2,0",
            ],
        ):
            with self.assertRaisesRegex(ValueError, "levels-per-site must contain positive integers only"):
                main()


if __name__ == "__main__":
    unittest.main()
