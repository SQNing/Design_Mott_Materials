import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

try:
    from common import classical_family_resolution as family_resolution  # noqa: E402
except ImportError:
    family_resolution = None


class ClassicalFamilyResolutionTests(unittest.TestCase):
    def test_normalize_public_classical_family_labels(self):
        self.assertIsNotNone(family_resolution)

        self.assertEqual(family_resolution.normalize_classical_family_label("spin-only"), "spin-only")
        self.assertEqual(family_resolution.normalize_classical_family_label("spin_only"), "spin-only")
        self.assertEqual(family_resolution.normalize_classical_family_label("cpn"), "cpn")

    def test_resolve_classical_family_raises_when_no_explicit_family_is_present(self):
        self.assertIsNotNone(family_resolution)

        with self.assertRaisesRegex(ValueError, "missing-classical-family"):
            family_resolution.resolve_classical_family(
                requested_family=None,
                payload=None,
                bridge_metadata=None,
            )

    def test_resolve_classical_family_raises_when_explicit_sources_conflict(self):
        self.assertIsNotNone(family_resolution)

        with self.assertRaisesRegex(ValueError, "conflicting-classical-family"):
            family_resolution.resolve_classical_family(
                requested_family="spin-only",
                payload={"classical_family": "cpn"},
                bridge_metadata=None,
            )


if __name__ == "__main__":
    unittest.main()
