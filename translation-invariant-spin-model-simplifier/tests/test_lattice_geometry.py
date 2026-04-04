import math
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lattice_geometry import (
    build_isotropic_heisenberg_bonds_from_parameters,
    enumerate_neighbor_shells,
    fractional_to_cartesian,
    resolve_lattice_vectors,
)


class LatticeGeometryTests(unittest.TestCase):
    def test_resolve_lattice_vectors_builds_orthorhombic_cell_from_cell_parameters(self):
        lattice = {
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            }
        }
        vectors = resolve_lattice_vectors(lattice)
        self.assertEqual(len(vectors), 3)
        self.assertAlmostEqual(vectors[0][0], 3.0, places=9)
        self.assertAlmostEqual(vectors[1][1], 8.0, places=9)
        self.assertAlmostEqual(vectors[2][2], 8.0, places=9)

    def test_fractional_to_cartesian_uses_resolved_vectors(self):
        lattice = {
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            }
        }
        vectors = resolve_lattice_vectors(lattice)
        positions = fractional_to_cartesian([[0.5, 0.25, 0.0]], vectors)
        self.assertEqual(len(positions), 1)
        self.assertAlmostEqual(positions[0][0], 1.5, places=9)
        self.assertAlmostEqual(positions[0][1], 2.0, places=9)
        self.assertAlmostEqual(positions[0][2], 0.0, places=9)

    def test_enumerate_neighbor_shells_orders_single_site_orthorhombic_shells_by_distance(self):
        lattice = {
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            },
            "positions": [[0.0, 0.0, 0.0]],
        }
        vectors = resolve_lattice_vectors(lattice)
        shells = enumerate_neighbor_shells(vectors, lattice["positions"], shell_count=3, max_translation=3)
        self.assertEqual(len(shells), 3)
        self.assertAlmostEqual(shells[0]["distance"], 3.0, places=9)
        self.assertEqual(sorted(item["translation"] for item in shells[0]["pairs"]), [(-1, 0, 0), (1, 0, 0)])
        self.assertAlmostEqual(shells[1]["distance"], 6.0, places=9)
        self.assertEqual(sorted(item["translation"] for item in shells[1]["pairs"]), [(-2, 0, 0), (2, 0, 0)])
        self.assertAlmostEqual(shells[2]["distance"], 8.0, places=9)
        self.assertEqual(
            sorted(item["translation"] for item in shells[2]["pairs"]),
            [(0, -1, 0), (0, 0, -1), (0, 0, 1), (0, 1, 0)],
        )

    def test_build_isotropic_heisenberg_bonds_maps_j_parameters_to_distance_shells(self):
        lattice = {
            "kind": "orthorhombic",
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            },
            "positions": [[0.0, 0.0, 0.0]],
        }
        parameters = {"J1": -1.0, "J2": 2.0, "J3": 0.5}
        bonds, shell_map = build_isotropic_heisenberg_bonds_from_parameters(lattice, parameters, max_shell=3, max_translation=3)
        self.assertEqual(len(shell_map), 3)
        self.assertAlmostEqual(shell_map["J1"]["distance"], 3.0, places=9)
        self.assertAlmostEqual(shell_map["J2"]["distance"], 6.0, places=9)
        self.assertAlmostEqual(shell_map["J3"]["distance"], 8.0, places=9)
        j1_vectors = sorted(tuple(bond["vector"]) for bond in bonds if bond["shell_label"] == "J1")
        j2_vectors = sorted(tuple(bond["vector"]) for bond in bonds if bond["shell_label"] == "J2")
        j3_vectors = sorted(tuple(bond["vector"]) for bond in bonds if bond["shell_label"] == "J3")
        self.assertEqual(j1_vectors, [(1, 0, 0)])
        self.assertEqual(j2_vectors, [(2, 0, 0)])
        self.assertEqual(j3_vectors, [(0, 0, 1), (0, 1, 0)])

    def test_build_isotropic_heisenberg_bonds_skips_missing_shell_parameters(self):
        lattice = {
            "kind": "orthorhombic",
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            },
            "positions": [[0.0, 0.0, 0.0]],
        }
        bonds, shell_map = build_isotropic_heisenberg_bonds_from_parameters(lattice, {"J2": 2.0}, max_shell=3, max_translation=3)
        self.assertEqual(list(shell_map.keys()), ["J2"])
        self.assertTrue(all(bond["shell_label"] == "J2" for bond in bonds))
        self.assertEqual(sorted(tuple(bond["vector"]) for bond in bonds), [(2, 0, 0)])

    def test_build_isotropic_heisenberg_bonds_respects_explicit_shell_map_overrides(self):
        lattice = {
            "kind": "orthorhombic",
            "cell_parameters": {
                "a": 3.0,
                "b": 8.0,
                "c": 8.0,
                "alpha": 90.0,
                "beta": 90.0,
                "gamma": 90.0,
            },
            "positions": [[0.0, 0.0, 0.0]],
        }
        parameters = {"J1": -1.0, "J2": 2.0}
        bonds, shell_map = build_isotropic_heisenberg_bonds_from_parameters(
            lattice,
            parameters,
            max_shell=3,
            max_translation=3,
            shell_map_override={"J1": 1, "J2": 3},
        )
        self.assertAlmostEqual(shell_map["J1"]["distance"], 3.0, places=9)
        self.assertAlmostEqual(shell_map["J2"]["distance"], 8.0, places=9)
        self.assertEqual(
            sorted(tuple(bond["vector"]) for bond in bonds if bond["shell_label"] == "J2"),
            [(0, 0, 1), (0, 1, 0)],
        )


if __name__ == "__main__":
    unittest.main()
