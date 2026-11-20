"""Phase A: quantum method routing gates must fail closed, never guess."""
import unittest

from common.quantum_method_routing import (
    DEFAULT_ED_MAX_DIMENSION, HARD_ED_MAX_DIMENSION,
    cluster_site_count, estimate_hilbert_dimension, local_quantum_dimension,
    quantum_method_stage_decision,
)


def spin_model():
    return {
        "lattice_structure": {"lattice_vectors": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                              "basis_sites": [{"site": 0}, {"site": 1}]},
        "local_hilbert": {"classical_spaces": {
            "a": {"kind": "unit_vector_sphere", "dimension": 3},
            "b": {"kind": "unit_vector_sphere", "dimension": 3}}},
    }


def cpn_model(dimension=3):
    return {
        "lattice_structure": {"lattice_vectors": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                              "basis_sites": [{"site": 0}]},
        "local_hilbert": {"classical_spaces": {
            "a": {"kind": "complex_projective_space", "dimension": dimension}}},
    }


class LocalQuantumDimensionTests(unittest.TestCase):
    def test_spin_dimension_comes_from_settings_spin(self):
        self.assertEqual(local_quantum_dimension(spin_model(), {"spin": 0.5}), 2)
        self.assertEqual(local_quantum_dimension(spin_model(), {"spin_length": 1.0}), 3)

    def test_sphere_manifold_dimension_is_not_quantum_dimension(self):
        self.assertIsNone(local_quantum_dimension(spin_model()))

    def test_cpn_retained_multiplet_count_is_quantum_dimension(self):
        self.assertEqual(local_quantum_dimension(cpn_model(3)), 3)
        self.assertEqual(local_quantum_dimension(cpn_model(4)), 4)

    def test_explicit_local_dim_wins(self):
        model = {**cpn_model(3), "local_dim": 5}
        self.assertEqual(local_quantum_dimension(model), 5)

    def test_model_spin_block(self):
        model = {**spin_model(), "quantum": {"spin": 1.5}}
        self.assertEqual(local_quantum_dimension(model), 4)


class ClusterSiteCountTests(unittest.TestCase):
    def test_supercell_times_basis(self):
        self.assertEqual(cluster_site_count(spin_model(), [2, 2, 1]), 8)

    def test_legacy_cluster_size_counts_total_sites(self):
        self.assertEqual(cluster_site_count({"cluster_size": 12, "local_dim": 2}), 12)

    def test_missing_shape_is_none(self):
        self.assertIsNone(cluster_site_count(spin_model()))

    def test_hilbert_estimate(self):
        self.assertEqual(estimate_hilbert_dimension(spin_model(), [2, 2, 1], {"spin": 0.5}),
                         float(2 ** 8))


class QuantumMethodDecisionTests(unittest.TestCase):
    def test_default_method_is_ed(self):
        decision = quantum_method_stage_decision(
            spin_model(), {"supercell_shape": [1, 1, 1], "spin": 0.5})
        self.assertEqual(decision["status"], "ok")
        self.assertEqual(decision["method"], "ed")
        self.assertEqual(decision["hilbert_dimension"], 4.0)

    def test_method_aliases(self):
        for alias in ("lanczos", "exact_diagonalization"):
            decision = quantum_method_stage_decision(
                spin_model(), {"supercell_shape": [1, 1, 1], "spin": 0.5, "quantum_method": alias})
            self.assertEqual(decision["status"], "ok", alias)

    def test_dmrg_and_vmc_fail_closed(self):
        for method, solver_id in (("dmrg", "quantum-dmrg-itensor"),
                                  ("itensor", "quantum-dmrg-itensor"),
                                  ("vmc", "quantum-vmc-netket"),
                                  ("netket", "quantum-vmc-netket")):
            decision = quantum_method_stage_decision(
                spin_model(), {"supercell_shape": [1, 1, 1], "spin": 0.5,
                               "quantum_method": method})
            self.assertEqual(decision["status"], "unsupported", method)
            self.assertIn("backend-not-connected", decision["blocker"])
            self.assertEqual(decision["declared_backend"], solver_id)

    def test_unknown_method_needs_input(self):
        decision = quantum_method_stage_decision(
            spin_model(), {"supercell_shape": [1, 1, 1], "spin": 0.5,
                           "quantum_method": "qmc"})
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "quantum_method")

    def test_oversized_ed_fails_closed_with_alternatives(self):
        decision = quantum_method_stage_decision(
            spin_model(), {"supercell_shape": [4, 4, 3], "spin": 0.5})
        self.assertEqual(decision["status"], "unsupported")
        self.assertEqual(decision["blocker"], "quantum-ed-dimension-exceeded")
        self.assertGreater(decision["hilbert_dimension"], DEFAULT_ED_MAX_DIMENSION)
        self.assertTrue(any("dmrg" in alt for alt in decision["alternatives"]))

    def test_hard_cap_overrides_user_limit(self):
        decision = quantum_method_stage_decision(
            spin_model(), {"supercell_shape": [3, 3, 3], "spin": 3.5,
                           "max_dimension": HARD_ED_MAX_DIMENSION * 4})
        self.assertEqual(decision["status"], "unsupported")
        self.assertEqual(decision["ed_max_dimension"], HARD_ED_MAX_DIMENSION)

    def test_missing_cluster_needs_input(self):
        decision = quantum_method_stage_decision(spin_model(), {"spin": 0.5})
        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "quantum_cluster")


if __name__ == "__main__":
    unittest.main()
