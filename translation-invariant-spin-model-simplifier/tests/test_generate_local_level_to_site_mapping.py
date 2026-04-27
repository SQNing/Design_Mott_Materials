import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.generate_local_level_to_site_mapping import main


class GenerateLocalLevelToSiteMappingTests(unittest.TestCase):
    @staticmethod
    def _write_two_site_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "two-site lattice",
                    "1.0",
                    "1.0 0.0 0.0",
                    "0.0 1.0 0.0",
                    "0.0 0.0 1.0",
                    "Fe",
                    "2",
                    "Direct",
                    "0.0 0.0 0.0",
                    "0.5 0.0 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

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

    def test_cli_can_use_structure_to_repeat_single_level_count_and_attach_labels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            self._write_two_site_poscar(poscar_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "generate_local_level_to_site_mapping.py",
                    "--structure",
                    str(poscar_path),
                    "--levels-per-site",
                    "2",
                    "--site-labels",
                    "A,B",
                ],
            ):
                with redirect_stdout(stdout):
                    exit_code = main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["site_level_mapping"],
            [
                {"site": 0, "label": "A", "level_indexes": [0, 1]},
                {"site": 1, "label": "B", "level_indexes": [2, 3]},
            ],
        )

    def test_cli_rejects_site_label_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            self._write_two_site_poscar(poscar_path)
            with patch.object(
                sys,
                "argv",
                [
                    "generate_local_level_to_site_mapping.py",
                    "--structure",
                    str(poscar_path),
                    "--levels-per-site",
                    "2",
                    "--site-labels",
                    "A",
                ],
            ):
                with self.assertRaisesRegex(ValueError, "site-labels count must match site count"):
                    main()


if __name__ == "__main__":
    unittest.main()
