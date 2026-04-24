import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli import solve_cpn_payload_pipeline  # noqa: E402


class SolveCpnPayloadPipelineCliTests(unittest.TestCase):
    def test_cli_loads_json_payload_and_delegates_to_solver(self):
        payload = {
            "classical_family": "cpn",
            "basis_semantics": {"local_space": "pseudospin_orbital"},
            "basis_order": "retained_state_index",
            "pair_basis_order": "site_i_major_site_j_minor",
            "local_basis_labels": ["state_1", "state_2"],
            "structure": {
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "inferred": {"local_dimension": 2, "multiplet_dimension": 2, "two_site_dimension": 4},
            "retained_local_space": {"dimension": 2, "factorization": {"kind": "generic_multiplet", "multiplet_dimension": 2}},
            "bond_blocks": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            payload_path = Path(tmpdir) / "payload.json"
            output_dir = Path(tmpdir) / "out"
            docs_dir = Path(tmpdir) / "docs"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            captured = {}

            def _capture_call(parsed_payload, **kwargs):
                captured["parsed_payload"] = parsed_payload
                captured["kwargs"] = kwargs
                return {"status": "ok", "solver": {"classical_state_result": {"role": "final"}}}

            with patch.object(
                solve_cpn_payload_pipeline,
                "solve_from_parsed_payload",
                side_effect=_capture_call,
            ), patch.object(sys, "argv", [
                "solve_cpn_payload_pipeline.py",
                "--parsed-payload", str(payload_path),
                "--output-dir", str(output_dir),
                "--docs-dir", str(docs_dir),
                "--classical-family", "cpn",
                "--classical-method", "cpn-generalized-lt",
                "--no-gswt",
                "--no-pdf",
            ]):
                rc = solve_cpn_payload_pipeline.main()

        self.assertEqual(rc, 0)
        self.assertEqual(captured["parsed_payload"]["classical_family"], "cpn")
        self.assertEqual(captured["kwargs"]["classical_family"], "cpn")
        self.assertEqual(captured["kwargs"]["classical_method"], "cpn-generalized-lt")


if __name__ == "__main__":
    unittest.main()
