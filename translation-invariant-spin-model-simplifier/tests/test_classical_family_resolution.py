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

    def test_resolve_input_acceptance_classical_family_requests_selection_for_ambiguous_inputs(self):
        self.assertIsNotNone(family_resolution)

        resolution = family_resolution.resolve_input_acceptance_classical_family(
            payload={"representation": "natural_language"}
        )

        self.assertEqual(resolution["status"], "needs_input")
        self.assertEqual(resolution["interaction"]["id"], "classical_family_selection")
        self.assertEqual(sorted(resolution["interaction"]["options"]), ["cpn", "spin-only"])

    def test_resolve_input_acceptance_classical_family_preserves_intrinsic_many_body_hr_family(self):
        self.assertIsNotNone(family_resolution)

        resolution = family_resolution.resolve_input_acceptance_classical_family(
            payload={"representation": "many_body_hr"}
        )

        self.assertEqual(resolution["status"], "resolved")
        self.assertTrue(resolution["intrinsic"])
        self.assertEqual(resolution["classical_family"], "cpn")


if __name__ == "__main__":
    unittest.main()
