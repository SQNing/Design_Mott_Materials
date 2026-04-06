import json
import sys
import tempfile
import unittest
from pathlib import Path
import math

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from build_lswt_payload import build_lswt_payload
from render_plots import _build_plot_payload, _default_structure_style


class PlottingAndKPathTests(unittest.TestCase):
    def test_default_classical_plot_style_uses_larger_markers_and_arrows(self):
        style = _default_structure_style()

        self.assertGreaterEqual(style["atom_size"], 260.0)
        self.assertGreaterEqual(style["arrow_length_factor"], 0.48)
        self.assertGreaterEqual(style["arrow_line_width"], 2.6)

    def test_build_lswt_payload_uses_hexagonal_default_path_for_kagome(self):
        model = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "sublattices": 3,
                "cell_parameters": {
                    "a": 6.0,
                    "b": 6.0,
                    "c": 10.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.5, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 1, "vector": [0, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                    {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                    {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            },
            "q_samples": 4,
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["path"]["labels"], ["G", "K", "M", "G"])

    def test_build_lswt_payload_uses_tetragonal_default_path(self):
        model = {
            "lattice": {
                "kind": "tetragonal",
                "dimension": 3,
                "sublattices": 1,
                "cell_parameters": {
                    "a": 4.0,
                    "b": 4.0,
                    "c": 7.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 90.0,
                },
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            },
            "q_samples": 4,
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["path"]["labels"], ["G", "X", "M", "G", "Z", "R", "A", "Z"])

    def test_build_lswt_payload_recovers_high_symmetry_labels_for_matching_explicit_path(self):
        model = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "sublattices": 3,
                "cell_parameters": {
                    "a": 6.0,
                    "b": 6.0,
                    "c": 10.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.5, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 1, "vector": [0, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}
                ],
            },
            "classical_state": {
                "site_frames": [
                    {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                    {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                    {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                ],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            },
            "q_path": [[0.0, 0.0, 0.0], [1.0 / 3.0, 1.0 / 3.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 0.0]],
            "q_samples": 4,
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["path"]["labels"], ["G", "K", "M", "G"])

    def test_build_plot_payload_marks_1d_chain_and_repeats_two_magnetic_cells(self):
        payload = {
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["classical_state"]["spatial_dimension"], 1)
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [2, 1, 1])
        self.assertEqual(plot_payload["classical_state"]["render_mode"], "chain")

    def test_build_plot_payload_marks_2d_and_uses_custom_magnetic_cell_multiplier(self):
        payload = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.5, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.5, 0.8660254037844386, 0.0], [0.0, 0.0, 8.0]],
            },
            "plot_options": {"commensurate_cells": [3, 4, 1]},
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                        {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["classical_state"]["spatial_dimension"], 2)
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [3, 4, 1])
        self.assertEqual(plot_payload["classical_state"]["render_mode"], "plane")

    def test_build_plot_payload_uses_correct_fractional_to_cartesian_positions_for_kagome(self):
        payload = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "cell_parameters": {
                    "a": 6.0,
                    "b": 6.0,
                    "c": 10.0,
                    "alpha": 90.0,
                    "beta": 90.0,
                    "gamma": 120.0,
                },
                "positions": [[0.5, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.0]],
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                        {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)
        expanded = plot_payload["classical_state"]["expanded_sites"]

        expected = [
            [3.0, 0.0, 0.0],
            [1.5, 2.598076211353316, 0.0],
            [-1.5, 2.598076211353316, 0.0],
        ]
        for site, target in zip(expanded[:3], expected):
            for got, want in zip(site["position"], target):
                self.assertAlmostEqual(got, want, places=6)

    def test_build_lswt_payload_transforms_default_path_to_user_square_convention(self):
        model = {
            "lattice": {
                "kind": "square",
                "dimension": 2,
                "lattice_vectors": [[0.0, 2.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 8.0]],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "simplified_model": {
                "template": "heisenberg",
                "bonds": [
                    {"source": 0, "target": 0, "vector": [1, 0, 0], "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]}
                ],
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
            },
            "q_samples": 4,
        }

        result = build_lswt_payload(model)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["payload"]["path"]["labels"], ["G", "X", "M", "G"])
        q_path = result["payload"]["q_path"]
        node_indices = result["payload"]["path"]["node_indices"]
        x_point = q_path[node_indices[1]]
        self.assertAlmostEqual(x_point[0], 0.0, places=6)
        self.assertAlmostEqual(x_point[1], 0.5, places=6)

    def test_build_plot_payload_uses_five_incommensurate_magnetic_cells_by_default_in_3d(self):
        payload = {
            "lattice": {
                "kind": "cubic",
                "dimension": 3,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "incommensurate", "q_vector": [0.23, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["classical_state"]["spatial_dimension"], 3)
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [5, 5, 5])
        self.assertEqual(plot_payload["classical_state"]["render_mode"], "structure")

    def test_build_plot_payload_uses_custom_incommensurate_magnetic_cell_multiplier(self):
        payload = {
            "lattice": {
                "kind": "cubic",
                "dimension": 3,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            },
            "plot_options": {"incommensurate_cells": [4, 3, 2]},
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "incommensurate", "q_vector": [0.23, 0.11, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [4, 3, 2])

    def test_build_plot_payload_accepts_custom_classical_style_overrides(self):
        payload = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.5, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.5, 0.8660254037844386, 0.0], [0.0, 0.0, 8.0]],
            },
            "plot_options": {
                "classical_style": {
                    "atom_size": 420.0,
                    "arrow_length_factor": 0.7,
                    "arrow_line_width": 3.4,
                }
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                        {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)
        style = plot_payload["classical_state"]["style"]

        self.assertEqual(style["atom_size"], 420.0)
        self.assertEqual(style["arrow_length_factor"], 0.7)
        self.assertEqual(style["arrow_line_width"], 3.4)

    def test_build_plot_payload_accepts_custom_classical_figure_size(self):
        payload = {
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.5, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.5, 0.8660254037844386, 0.0], [0.0, 0.0, 8.0]],
            },
            "plot_options": {
                "classical_figsize": [12.0, 9.0],
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [
                        {"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]},
                        {"site": 1, "spin_length": 0.5, "direction": [-0.5, 0.8660254037844386, 0.0]},
                        {"site": 2, "spin_length": 0.5, "direction": [-0.5, -0.8660254037844386, 0.0]},
                    ],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["classical_state"]["figure_size"], [12.0, 9.0])

    def test_build_plot_payload_accepts_custom_lswt_figure_size_and_style(self):
        payload = {
            "plot_options": {
                "lswt_figsize": [10.0, 5.0],
                "lswt_style": {
                    "line_width": 2.3,
                    "node_line_width": 1.4,
                },
            },
            "classical": {"chosen_method": "variational", "classical_state": {"site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}], "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]}}},
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "K", "M", "G"], "node_indices": [0, 8, 16, 24]},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0, 0.2], "omega": 0.0},
                        {"q": [0.5, 0.0, 0.0], "bands": [1.0, 1.2], "omega": 1.0},
                    ]
                },
            },
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["lswt_dispersion"]["figure_size"], [10.0, 5.0])
        self.assertEqual(plot_payload["lswt_dispersion"]["style"]["line_width"], 2.3)
        self.assertEqual(plot_payload["lswt_dispersion"]["style"]["node_line_width"], 1.4)

    def test_build_plot_payload_accepts_custom_thermodynamics_figure_size_and_style(self):
        payload = {
            "plot_options": {
                "thermodynamics_figsize": [11.0, 10.0],
                "thermodynamics_style": {
                    "line_width": 1.8,
                    "marker_size": 5.0,
                    "capsize": 4.0,
                },
            },
            "classical": {"chosen_method": "variational", "classical_state": {"site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}], "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]}}},
            "thermodynamics_result": {
                "grid": [
                    {"temperature": 0.5, "energy": -1.0, "free_energy": -1.0, "specific_heat": 0.0, "magnetization": 0.6, "susceptibility": 0.1, "entropy": 0.0},
                    {"temperature": 1.0, "energy": -0.8, "free_energy": -0.9, "specific_heat": 0.2, "magnetization": 0.2, "susceptibility": 0.3, "entropy": 0.1},
                ],
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["thermodynamics"]["figure_size"], [11.0, 10.0])
        self.assertEqual(plot_payload["thermodynamics"]["style"]["line_width"], 1.8)
        self.assertEqual(plot_payload["thermodynamics"]["style"]["marker_size"], 5.0)
        self.assertEqual(plot_payload["thermodynamics"]["style"]["capsize"], 4.0)


if __name__ == "__main__":
    unittest.main()
