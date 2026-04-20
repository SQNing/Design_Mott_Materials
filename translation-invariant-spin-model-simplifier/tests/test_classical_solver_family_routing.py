import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

try:
    from common import classical_solver_family_routing as routing  # noqa: E402
except ImportError:
    routing = None


class ClassicalSolverFamilyRoutingTests(unittest.TestCase):
    def test_resolve_spin_only_variational_metadata(self):
        self.assertIsNotNone(routing)

        metadata = routing.resolve_classical_solver_method("variational")

        self.assertEqual(metadata["solver_family"], "spin_only_explicit")
        self.assertEqual(metadata["role"], "final")
        self.assertEqual(metadata["standardized_method"], "spin-only-variational")

    def test_resolve_pseudospin_final_metadata(self):
        self.assertIsNotNone(routing)

        metadata = routing.resolve_classical_solver_method("cpn-local-ray-minimize")

        self.assertEqual(metadata["solver_family"], "retained_local_multiplet")
        self.assertEqual(metadata["role"], "final")
        self.assertEqual(metadata["standardized_method"], "pseudospin-cpn-local-ray-minimize")

    def test_resolve_pseudospin_diagnostic_metadata(self):
        self.assertIsNotNone(routing)

        metadata = routing.resolve_classical_solver_method("cpn-generalized-lt")

        self.assertEqual(metadata["solver_family"], "diagnostic_seed_only")
        self.assertEqual(metadata["role"], "diagnostic")
        self.assertEqual(metadata["standardized_method"], "pseudospin-cpn-generalized-lt")

    def test_resolve_specialized_ansatz_metadata(self):
        self.assertIsNotNone(routing)

        metadata = routing.resolve_classical_solver_method("sun-gswt-single-q")

        self.assertEqual(metadata["solver_family"], "specialized_classical_ansatz")
        self.assertEqual(metadata["role"], "specialized")
        self.assertEqual(metadata["standardized_method"], "pseudospin-sun-gswt-single-q")

    def test_unsupported_method_raises_stable_value_error(self):
        self.assertIsNotNone(routing)

        with self.assertRaisesRegex(ValueError, "unsupported classical solver method"):
            routing.resolve_classical_solver_method("made-up-method")


if __name__ == "__main__":
    unittest.main()
