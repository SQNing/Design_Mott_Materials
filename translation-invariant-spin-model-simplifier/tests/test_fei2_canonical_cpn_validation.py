import json
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from common.cpn_pair_model import validate_cpn_pair_model


FIXTURE_DIR = SKILL_ROOT / "tests" / "data"
PAYLOAD_PATH = FIXTURE_DIR / "fei2_canonical_cpn_payload.json"
REFERENCE_PATH = FIXTURE_DIR / "fei2_canonical_cpn_reference.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class FeI2CanonicalCpnValidationTests(unittest.TestCase):
    def test_fixture_is_canonical_cp2_model(self):
        payload = _load_json(PAYLOAD_PATH)
        reference = _load_json(REFERENCE_PATH)

        validate_cpn_pair_model(payload)

        self.assertEqual(payload["model_family"], "cpn_pair_model")
        self.assertEqual(payload["classical_family"], "cpn")
        self.assertEqual(payload["local_dimension"], 3)
        self.assertTrue(payload["bond_terms"])
        self.assertTrue(payload["onsite_terms"])
        self.assertEqual(reference["ordering"]["allowed_q_vectors"][0], [0.0, -0.25, 0.25])


if __name__ == "__main__":
    unittest.main()
