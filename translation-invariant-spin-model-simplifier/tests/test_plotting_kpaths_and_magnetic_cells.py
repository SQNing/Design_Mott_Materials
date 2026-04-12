import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import math
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_lswt_payload import build_lswt_payload, infer_spatial_dimension
from output.render_plots import _build_plot_payload, _default_structure_style, render_plots


class PlottingAndKPathTests(unittest.TestCase):
    def test_scripts_top_level_is_reserved_for_stage_dirs_and_examples(self):
        scripts_root = SKILL_ROOT / "scripts"
        top_level_files = sorted(path.name for path in scripts_root.iterdir() if path.is_file())

        self.assertEqual(top_level_files, ["plot_payload.json", "results_bundle_example.json"])

    def test_common_and_output_stage_modules_are_importable(self):
        common_lattice_geometry = importlib.import_module("common.lattice_geometry")
        common_bravais_kpaths = importlib.import_module("common.bravais_kpaths")
        output_render_plots = importlib.import_module("output.render_plots")
        output_render_report = importlib.import_module("output.render_report")

        self.assertTrue(hasattr(common_lattice_geometry, "resolve_lattice_vectors"))
        self.assertTrue(hasattr(common_bravais_kpaths, "default_high_symmetry_path"))
        self.assertTrue(hasattr(output_render_plots, "render_plots"))
        self.assertTrue(hasattr(output_render_report, "render_text"))

    def test_input_and_simplify_stage_modules_are_importable(self):
        input_normalize = importlib.import_module("input.normalize_input")
        input_parse_lattice = importlib.import_module("input.parse_lattice_description")
        simplify_canonicalize = importlib.import_module("simplify.canonicalize_terms")
        simplify_assemble = importlib.import_module("simplify.assemble_effective_model")

        legacy_normalize = importlib.import_module("legacy.normalize_input")
        legacy_parse_lattice = importlib.import_module("legacy.parse_lattice_description")
        legacy_canonicalize = importlib.import_module("legacy.canonicalize_terms")
        legacy_assemble = importlib.import_module("legacy.assemble_effective_model")

        self.assertTrue(hasattr(input_normalize, "normalize_input"))
        self.assertTrue(hasattr(input_parse_lattice, "parse_lattice_description"))
        self.assertTrue(hasattr(simplify_canonicalize, "canonicalize_terms"))
        self.assertTrue(hasattr(simplify_assemble, "assemble_effective_model"))

        self.assertTrue(hasattr(legacy_normalize, "normalize_input"))
        self.assertTrue(hasattr(legacy_parse_lattice, "parse_lattice_description"))
        self.assertTrue(hasattr(legacy_canonicalize, "canonicalize_terms"))
        self.assertTrue(hasattr(legacy_assemble, "assemble_effective_model"))

    def test_classical_lswt_and_cli_stage_modules_are_importable(self):
        classical_driver = importlib.import_module("classical.classical_solver_driver")
        classical_decisions = importlib.import_module("classical.decision_gates")
        classical_lt = importlib.import_module("classical.lt_solver")
        lswt_payload = importlib.import_module("lswt.build_lswt_payload")
        lswt_driver = importlib.import_module("lswt.linear_spin_wave_driver")
        cli_bundle = importlib.import_module("cli.write_results_bundle")

        legacy_classical_driver = importlib.import_module("legacy.classical_solver_driver")
        legacy_lswt_driver = importlib.import_module("legacy.linear_spin_wave_driver")
        legacy_bundle = importlib.import_module("legacy.write_results_bundle")

        self.assertTrue(hasattr(classical_driver, "run_classical_solver"))
        self.assertTrue(hasattr(classical_decisions, "classical_stage_decision"))
        self.assertTrue(hasattr(classical_lt, "find_lt_ground_state"))
        self.assertTrue(hasattr(lswt_payload, "build_lswt_payload"))
        self.assertTrue(hasattr(lswt_driver, "run_linear_spin_wave"))
        self.assertTrue(hasattr(cli_bundle, "write_results_bundle"))

        self.assertTrue(hasattr(legacy_classical_driver, "run_classical_solver"))
        self.assertTrue(hasattr(legacy_lswt_driver, "run_linear_spin_wave"))
        self.assertTrue(hasattr(legacy_bundle, "write_results_bundle"))

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

    def test_infer_spatial_dimension_uses_full_rank_lattice_vectors_when_positions_and_bonds_are_silent(self):
        lattice = {
            "positions": [[0.0, 0.0, 0.0]],
            "lattice_vectors": [
                [2.868555068971266, 1.6561610412558259, 9.511033376066669],
                [-2.868555068971266, 1.6561610412558259, 9.511033376066669],
                [0.0, -3.3123220825116513, 9.511033376066669],
            ],
        }

        self.assertEqual(infer_spatial_dimension(lattice, bonds=[]), 3)

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

    def test_build_plot_payload_adds_summary_lines_for_lswt_and_thermodynamics_products(self):
        payload = {
            "classical": {"chosen_method": "sunny-cpn-minimize", "classical_state": {"site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}], "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]}}},
            "gswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "diagnostics": {
                    "instability": {
                        "kind": "wavevector-instability",
                        "q_vector": [0.25, 0.0, 0.0],
                        "nearest_q_path_kind": "path-segment-sample",
                        "nearest_path_segment_label": "G-X",
                    }
                },
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0, 0.2], "omega": 0.0},
                        {"q": [0.5, 0.0, 0.0], "bands": [1.0, 1.2], "omega": 1.0},
                    ]
                },
            },
            "thermodynamics": {
                "profile": "smoke",
                "backend_method": "sunny-local-sampler",
                "temperatures": [0.2, 0.4],
                "sweeps": 10,
                "burn_in": 5,
                "measurement_interval": 1,
                "proposal": "delta",
                "proposal_scale": 0.1,
            },
            "thermodynamics_result": {
                "method": "sunny-local-sampler",
                "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": "sunny-local-sampler"},
                "configuration": {
                    "profile": "smoke",
                    "backend_method": "sunny-local-sampler",
                    "sweeps": 10,
                    "burn_in": 5,
                    "measurement_interval": 1,
                },
                "grid": [
                    {"temperature": 0.2, "energy": -0.1, "free_energy": -0.1, "specific_heat": 0.4, "magnetization": 0.3, "susceptibility": 0.5, "entropy": 0.0}
                ],
            },
        }

        plot_payload = _build_plot_payload(payload)

        self.assertIn("LSWT backend=Sunny.jl", plot_payload["lswt_dispersion"]["summary_lines"][0])
        self.assertTrue(
            any("GSWT: harmonic instability near path segment G-X" in line for line in plot_payload["lswt_dispersion"]["summary_lines"])
        )
        self.assertTrue(
            any("profile=smoke" in line for line in plot_payload["thermodynamics"]["summary_lines"])
        )
        self.assertTrue(
            any("sweeps=10" in line and "burn_in=5" in line for line in plot_payload["thermodynamics"]["summary_lines"])
        )

    def test_build_plot_payload_adds_gswt_diagnostics_section_for_instability(self):
        payload = {
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "gswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "path": {"labels": ["G", "X", "S"], "node_indices": [0, 32, 64]},
                "diagnostics": {
                    "instability": {
                        "kind": "wavevector-instability",
                        "q_vector": [0.22, -0.06, -0.16],
                        "nearest_q_path_index": 63,
                        "nearest_q_path_kind": "path-segment-sample",
                        "nearest_q_path_distance": 0.0,
                        "nearest_path_segment_label": "X-S",
                    }
                },
                "error": {
                    "code": "backend-execution-failed",
                    "message": "Instability at wavevector q = [0.22, -0.06, -0.16]",
                },
            },
            "lswt": {"status": "missing", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertEqual(plot_payload["gswt_diagnostics"]["status"], "error")
        self.assertEqual(plot_payload["gswt_diagnostics"]["instability"]["nearest_path_segment_label"], "X-S")
        self.assertTrue(
            any("harmonic instability near path segment X-S" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )

    def test_build_plot_payload_summarizes_python_gswt_stationarity_and_bogoliubov_diagnostics(self):
        payload = {
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "gswt": {
                "status": "ok",
                "backend": {"name": "python-glswt", "implementation": "local-frame-quadratic-expansion"},
                "payload_kind": "python_glswt_local_rays",
                "dispersion": [
                    {"q": [0.0, 0.0, 0.0], "bands": [0.0, 0.4], "omega": 0.0},
                    {"q": [0.5, 0.0, 0.0], "bands": [1.0, 1.4], "omega": 1.0},
                ],
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "diagnostics": {
                    "dispersion": {"omega_min": 0.0, "soft_mode_count": 0},
                    "stationarity": {"is_stationary": True, "linear_term_max_norm": 2.5e-10},
                    "bogoliubov": {"mode_count": 6, "max_complex_eigenvalue_count": 0},
                },
            },
            "lswt": {"status": "missing", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertTrue(
            any("GSWT backend=python-glswt status=ok" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("stationary=True" in line and "linear_term_max_norm=2.5e-10" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("mode_count=6" in line and "max_complex_eigenvalue_count=0" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )

    def test_build_plot_payload_summarizes_single_q_z_harmonic_diagnostics(self):
        payload = {
            "classical": {
                "chosen_method": "sun-gswt-single-q",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [0.0, 0.0, 1.0]}],
                    "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
                },
            },
            "gswt": {
                "status": "ok",
                "backend": {"name": "python-glswt", "implementation": "single-q-z-harmonic-sideband"},
                "payload_kind": "python_glswt_single_q_z_harmonic",
                "z_harmonic_reference_mode": "refined-retained-local",
                "reference_dispersions": {
                    "input": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.125, 0.4], "omega": 0.125},
                        {"q": [0.13, 0.0, 0.0], "bands": [0.25, 0.5], "omega": 0.25},
                    ],
                    "refined-retained-local": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0625, 0.4], "omega": 0.0625},
                        {"q": [0.13, 0.0, 0.0], "bands": [0.1875, 0.5], "omega": 0.1875},
                    ],
                },
                "z_harmonic_cutoff": 1,
                "phase_grid_size": 32,
                "sideband_cutoff": 2,
                "dispersion": [
                    {"q": [0.0, 0.0, 0.0], "bands": [0.1, 0.4], "omega": 0.1},
                    {"q": [0.13, 0.0, 0.0], "bands": [0.2, 0.5], "omega": 0.2},
                ],
                "path": {"labels": ["G", "Q"], "node_indices": [0, 1]},
                "diagnostics": {
                    "reference_selection": {
                        "requested_mode": "refined-retained-local",
                        "resolved_mode": "refined-retained-local",
                        "dispersion_recomputed": True,
                        "input_retained_linear_term_max_norm": 2.0e-4,
                        "selected_retained_linear_term_max_norm": 5.0e-5,
                    },
                    "restricted_ansatz_stationarity": {
                        "best_objective": -0.75,
                        "optimizer_success": True,
                        "optimizer_method": "L-BFGS-B",
                        "optimization_mode": "direct-joint",
                    },
                    "harmonic": {
                        "phase_grid_size": 32,
                        "max_reconstruction_error": 1.0e-9,
                        "max_norm_error": 2.0e-9,
                    },
                    "stationarity": {
                        "scope": "full-local-tangent",
                        "sampling_kind": "phase_grid",
                        "is_stationary": False,
                        "linear_term_max_norm": 1.2e-4,
                    },
                    "truncated_z_harmonic_stationarity": {
                        "scope": "truncated-z-harmonic-manifold",
                        "projection_kind": "phase-fourier-retained-harmonics",
                        "harmonic_cutoff": 1,
                        "phase_grid_size": 32,
                        "full_dft_harmonic_count": 32,
                        "discarded_harmonic_count": 29,
                        "is_stationary": True,
                        "linear_term_max_norm": 2.0e-8,
                        "discarded_linear_term_max_norm": 3.0e-5,
                    },
                    "truncated_z_harmonic_local_refinement": {
                        "status": "improved",
                        "selected_step_size": 0.25,
                        "iteration_count": 3,
                        "step_history": [0.5, 0.25, -0.1],
                        "initial_retained_linear_term_max_norm": 2.0e-4,
                        "refined_retained_linear_term_max_norm": 5.0e-5,
                    },
                    "bogoliubov": {
                        "mode_count": 5,
                        "sideband_cutoff": 2,
                        "max_complex_eigenvalue_count": 0,
                    },
                },
            },
            "single_q_convergence": {
                "status": "ok",
                "analysis_kind": "single_q_z_harmonic_convergence",
                "reference_parameters": {
                    "phase_grid_size": 32,
                    "z_harmonic_cutoff": 1,
                    "sideband_cutoff": 2,
                    "z_harmonic_reference_mode": "refined-retained-local",
                },
                "reference_metrics": {
                    "omega_min": 0.05,
                    "omega_min_q_vector": [0.13, 0.0, 0.0],
                },
                "phase_grid_scan": [
                    {
                        "phase_grid_size": 16,
                        "omega_min": 0.07,
                        "omega_min_delta_vs_reference": 0.02,
                        "max_band_delta_vs_reference": 0.03,
                        "retained_linear_term_max_norm": 3.0e-7,
                        "full_tangent_linear_term_max_norm": 2.0e-4,
                    }
                ],
                "z_harmonic_cutoff_scan": [],
                "sideband_cutoff_scan": [],
            },
            "lswt": {"status": "missing", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(payload)

        self.assertTrue(
            any("z_harmonic_cutoff=1" in line and "sideband_cutoff=2" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("sampling_kind=phase_grid" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("restricted_ansatz" in line and "optimization_mode=direct-joint" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("truncated_z_harmonic" in line and "harmonic_cutoff=1" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("discarded_harmonic_count=29" in line and "discarded_linear_term_max_norm=3e-05" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("local_refinement" in line and "selected_step_size=0.25" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("iteration_count=3" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any("requested_mode=refined-retained-local" in line and "resolved_mode=refined-retained-local" in line for line in plot_payload["gswt_diagnostics"]["summary_lines"])
        )
        self.assertTrue(
            any(
                "reference_dispersion_comparison" in line
                and "input_omega_min=0.125" in line
                and "selected_omega_min=0.0625" in line
                and "delta_omega_min=-0.0625" in line
                for line in plot_payload["gswt_diagnostics"]["summary_lines"]
            )
        )
        self.assertTrue(
            any(
                "single_q_convergence" in line
                and "reference_phase_grid_size=32" in line
                and "reference_omega_min=0.05" in line
                for line in plot_payload["gswt_diagnostics"]["summary_lines"]
            )
        )

    def test_render_plots_accepts_prebuilt_plot_payload_directly(self):
        plot_payload = {
            "metadata": {
                "model_name": "template-demo",
                "backend": "Sunny.jl",
                "classical_method": "variational",
                "lswt_status": "ok",
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "magnetic_periods": [1, 1, 1],
                "repeat_cells": [2, 1, 1],
                "spatial_dimension": 1,
                "expanded_sites": [
                    {
                        "basis_index": 0,
                        "label": "Atom 0",
                        "position": [0.0, 0.0, 0.0],
                        "direction": [1.0, 0.0, 0.0],
                        "display_direction": [1.0, 0.0, 0.0],
                        "color": "#1f77b4",
                    }
                ],
                "basis_legend": [{"basis_index": 0, "label": "Atom 0", "color": "#1f77b4"}],
                "unit_cell_segments": [],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "render_mode": "chain",
                "view": {"projection": "chain"},
                "style": _default_structure_style(),
                "figure_size": [10.5, 4.2],
                "display_rotation": {"kind": "global", "source_direction": [0.0, 0.0, 1.0], "target_direction": [0.0, 0.0, 1.0]},
                "lattice_labels": [],
            },
            "lswt_dispersion": {
                "dispersion": [
                    {"q": [0.0, 0.0, 0.0], "bands": [0.0, 0.2], "omega": 0.0},
                    {"q": [0.5, 0.0, 0.0], "bands": [1.0, 1.2], "omega": 1.0},
                ],
                "band_count": 2,
                "q_points": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                "omega_min": 0.0,
                "omega_max": 1.0,
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "figure_size": [7.0, 4.5],
                "style": {"line_width": 1.5, "node_line_width": 0.8, "node_alpha": 0.7, "grid_alpha": 0.25},
            },
            "thermodynamics": {
                "grid": [
                    {"temperature": 0.5, "energy": -1.0, "free_energy": -1.0, "specific_heat": 0.0, "magnetization": 0.6, "susceptibility": 0.1, "entropy": 0.0},
                    {"temperature": 1.0, "energy": -0.8, "free_energy": -0.9, "specific_heat": 0.2, "magnetization": 0.2, "susceptibility": 0.3, "entropy": 0.1},
                ],
                "figure_size": [9.0, 9.0],
                "style": {"line_width": 1.6, "marker_size": 4.0, "capsize": 3.0, "grid_alpha": 0.25},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(plot_payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            self.assertEqual(result["status"], "ok")
            self.assertTrue((output_dir / "plot_payload.json").exists())
            self.assertTrue((output_dir / "classical_state.png").exists())
            self.assertTrue((output_dir / "lswt_dispersion.png").exists())
            self.assertTrue((output_dir / "thermodynamics.png").exists())

    def test_render_plots_writes_gswt_diagnostics_plot_when_instability_is_present(self):
        raw_payload = {
            "model_name": "gswt-instability-demo",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "gswt": {
                "status": "error",
                "backend": {"name": "Sunny.jl", "mode": "SUN"},
                "path": {"labels": ["G", "X", "S"], "node_indices": [0, 32, 64]},
                "diagnostics": {
                    "instability": {
                        "kind": "wavevector-instability",
                        "q_vector": [0.22, -0.06, -0.16],
                        "nearest_q_path_index": 63,
                        "nearest_q_path_kind": "path-segment-sample",
                        "nearest_q_path_distance": 0.0,
                        "nearest_path_segment_label": "X-S",
                    }
                },
                "error": {
                    "code": "backend-execution-failed",
                    "message": "Instability at wavevector q = [0.22, -0.06, -0.16]",
                },
            },
            "lswt": {"status": "missing", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(raw_payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            plot_payload = json.loads((output_dir / "plot_payload.json").read_text(encoding="utf-8"))

            self.assertEqual(result["plots"]["gswt_diagnostics"]["status"], "ok")
            self.assertTrue((output_dir / "gswt_diagnostics.png").exists())
            self.assertEqual(plot_payload["gswt_diagnostics"]["instability"]["nearest_path_segment_label"], "X-S")

    def test_render_plots_passes_summary_lines_into_dispersion_and_thermodynamics_renderers(self):
        plot_payload = {
            "metadata": {
                "model_name": "summary-forwarding-demo",
                "backend": "Sunny.jl",
                "classical_method": "variational",
                "lswt_status": "ok",
            },
            "classical_state": {"site_frames": [], "expanded_sites": []},
            "lswt_dispersion": {
                "dispersion": [
                    {"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0},
                    {"q": [0.5, 0.0, 0.0], "bands": [1.0], "omega": 1.0},
                ],
                "band_count": 1,
                "q_points": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                "omega_min": 0.0,
                "omega_max": 1.0,
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "summary_lines": ["LSWT backend=Sunny.jl", "GSWT: harmonic instability near path segment G-X"],
                "figure_size": [7.0, 4.5],
                "style": {"line_width": 1.5, "node_line_width": 0.8, "node_alpha": 0.7, "grid_alpha": 0.25},
            },
            "thermodynamics": {
                "grid": [
                    {"temperature": 0.5, "energy": -1.0, "free_energy": -1.0, "specific_heat": 0.0, "magnetization": 0.6, "susceptibility": 0.1, "entropy": 0.0},
                ],
                "summary_lines": ["profile=smoke backend=sunny-local-sampler", "sweeps=10 burn_in=5 measurement_interval=1"],
                "figure_size": [9.0, 9.0],
                "style": {"line_width": 1.6, "marker_size": 4.0, "capsize": 3.0, "grid_alpha": 0.25},
            },
        }

        captured = {}

        def fake_render_dispersion(dispersion, path_metadata, output_path, figure_size=None, style=None, summary_lines=None):
            captured["dispersion_summary_lines"] = list(summary_lines or [])
            Path(output_path).write_text("dispersion", encoding="utf-8")

        def fake_render_thermodynamics(thermodynamics_grid, output_path, uncertainties=None, figure_size=None, style=None, summary_lines=None):
            captured["thermodynamics_summary_lines"] = list(summary_lines or [])
            Path(output_path).write_text("thermo", encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "output.render_plots._render_dispersion_with_path",
            side_effect=fake_render_dispersion,
        ), patch(
            "output.render_plots._render_thermodynamics",
            side_effect=fake_render_thermodynamics,
        ):
            result = render_plots(plot_payload, output_dir=tmpdir)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(captured["dispersion_summary_lines"][0], "LSWT backend=Sunny.jl")
        self.assertIn("profile=smoke", captured["thermodynamics_summary_lines"][0])

    def test_render_plots_materializes_default_plot_payload_next_to_input(self):
        raw_payload = {
            "model_name": "materialize-demo",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "variational",
                "classical_state": {
                    "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
                    "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                },
            },
            "lswt": {
                "status": "ok",
                "backend": {"name": "Sunny.jl"},
                "path": {"labels": ["G", "X"], "node_indices": [0, 1]},
                "linear_spin_wave": {
                    "dispersion": [
                        {"q": [0.0, 0.0, 0.0], "bands": [0.0], "omega": 0.0},
                        {"q": [0.5, 0.0, 0.0], "bands": [1.0], "omega": 1.0},
                    ]
                },
            },
            "thermodynamics_result": {
                "grid": [
                    {"temperature": 0.5, "energy": -1.0, "free_energy": -1.0, "specific_heat": 0.0, "magnetization": 0.6, "susceptibility": 0.1, "entropy": 0.0},
                    {"temperature": 1.0, "energy": -0.8, "free_energy": -0.9, "specific_heat": 0.2, "magnetization": 0.2, "susceptibility": 0.3, "entropy": 0.1},
                ],
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "result_payload.json"
            input_path.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")
            from output.render_plots import _load_or_materialize_plot_payload

            plot_payload = _load_or_materialize_plot_payload(str(input_path))

            materialized = Path(tmpdir) / "plot_payload.json"
            self.assertTrue(materialized.exists())
            self.assertEqual(plot_payload["classical_state"]["render_mode"], "chain")
            self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [2, 1, 1])

    def test_render_plots_renders_cpn_local_ray_state_via_local_observables(self):
        raw_payload = {
            "model_name": "cpn-local-ray-demo",
            "basis_order": "orbital_major_spin_minor",
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2"],
            "retained_local_space": {
                "dimension": 4,
                "factorization": {"kind": "orbital_times_spin", "orbital_count": 2, "spin_dimension": 2},
                "tensor_factor_order": "orbital_major_spin_minor",
            },
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        },
                        {
                            "cell": [1, 0, 0],
                            "vector": [
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 1.0, "imag": 0.0},
                            ],
                        },
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(raw_payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            plot_payload = json.loads((output_dir / "plot_payload.json").read_text(encoding="utf-8"))

            self.assertEqual(result["plots"]["classical_state"]["status"], "ok")
            self.assertTrue((output_dir / "classical_state.png").exists())
            self.assertEqual(plot_payload["classical_state"]["state_kind"], "local_rays")
            self.assertEqual(plot_payload["classical_state"]["manifold"], "CP^(N-1)")
            self.assertEqual(plot_payload["classical_state"]["supercell_shape"], [2, 1, 1])
            self.assertEqual(plot_payload["classical_state"]["local_ray_count"], 2)
            self.assertEqual(plot_payload["classical_state"]["observable_mode"], "cpn_local_observables")
            self.assertEqual(len(plot_payload["classical_state"]["local_observables"]), 2)
            self.assertEqual(plot_payload["classical_state"]["local_observables"][0]["dominant_orbital_index"], 0)
            self.assertEqual(plot_payload["classical_state"]["local_observables"][1]["dominant_orbital_index"], 1)
            self.assertGreater(plot_payload["classical_state"]["local_observables"][0]["spin_polarization_norm"], 0.49)

    def test_build_plot_payload_adds_classical_summary_lines(self):
        raw_payload = {
            "model_name": "cpn-classical-summary-demo",
            "basis_order": "orbital_major_spin_minor",
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2"],
            "retained_local_space": {
                "dimension": 4,
                "factorization": {"kind": "orbital_times_spin", "orbital_count": 2, "spin_dimension": 2},
                "tensor_factor_order": "orbital_major_spin_minor",
            },
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        },
                        {
                            "cell": [1, 0, 0],
                            "vector": [
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        },
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(raw_payload)

        summary_lines = plot_payload["classical_state"]["summary_lines"]
        self.assertIn("method=sunny-cpn-minimize", summary_lines[0])
        self.assertTrue(any("manifold=CP^(N-1)" in line for line in summary_lines))
        self.assertTrue(any("local_dimension=4" in line and "orbital_count=2" in line for line in summary_lines))
        self.assertTrue(any("q_vector=[0.5, 0.0, 0.0]" in line for line in summary_lines))

    def test_render_plots_tiles_commensurate_cpn_local_rays_by_two_magnetic_cells_in_1d(self):
        raw_payload = {
            "model_name": "cpn-commensurate-repeat-demo",
            "basis_order": "orbital_major_spin_minor",
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2"],
            "retained_local_space": {
                "dimension": 4,
                "factorization": {"kind": "orbital_times_spin", "orbital_count": 2, "spin_dimension": 2},
                "tensor_factor_order": "orbital_major_spin_minor",
            },
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        },
                        {
                            "cell": [1, 0, 0],
                            "vector": [
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 1.0, "imag": 0.0},
                            ],
                        },
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.5, 0.0, 0.0],
                        "supercell_shape": [2, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(raw_payload)

        self.assertEqual(plot_payload["classical_state"]["supercell_shape"], [2, 1, 1])
        self.assertEqual(plot_payload["classical_state"]["magnetic_repeat_cells"], [2, 1, 1])
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [4, 1, 1])
        self.assertEqual(len(plot_payload["classical_state"]["expanded_sites"]), 4)

    def test_render_plots_tiles_incommensurate_cpn_local_rays_by_five_magnetic_cells_in_2d(self):
        raw_payload = {
            "model_name": "cpn-incommensurate-repeat-demo",
            "basis_order": "orbital_major_spin_minor",
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2"],
            "retained_local_space": {
                "dimension": 4,
                "factorization": {"kind": "orbital_times_spin", "orbital_count": 2, "spin_dimension": 2},
                "tensor_factor_order": "orbital_major_spin_minor",
            },
            "lattice": {
                "kind": "kagome",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.5, 0.8660254037844386, 0.0], [0.0, 0.0, 8.0]],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        }
                    ],
                    "ordering": {
                        "kind": "incommensurate",
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.37, 0.11, 0.0],
                        "supercell_shape": [1, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(raw_payload)

        self.assertEqual(plot_payload["classical_state"]["magnetic_repeat_cells"], [5, 5, 1])
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [5, 5, 1])
        self.assertEqual(len(plot_payload["classical_state"]["expanded_sites"]), 25)

    def test_render_plots_treats_full_rank_cpn_lattice_as_3d_and_tiles_two_magnetic_cells(self):
        raw_payload = {
            "model_name": "cpn-3d-rank-demo",
            "basis_order": "orbital_major_spin_minor",
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2"],
            "retained_local_space": {
                "dimension": 4,
                "factorization": {"kind": "orbital_times_spin", "orbital_count": 2, "spin_dimension": 2},
                "tensor_factor_order": "orbital_major_spin_minor",
            },
            "lattice": {
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [2.868555068971266, 1.6561610412558259, 9.511033376066669],
                    [-2.868555068971266, 1.6561610412558259, 9.511033376066669],
                    [0.0, -3.3123220825116513, 9.511033376066669],
                ],
            },
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 1.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        }
                    ],
                    "ordering": {
                        "kind": "commensurate",
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.0, 0.0, 0.0],
                        "supercell_shape": [1, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        plot_payload = _build_plot_payload(raw_payload)

        self.assertEqual(plot_payload["classical_state"]["spatial_dimension"], 3)
        self.assertEqual(plot_payload["classical_state"]["magnetic_repeat_cells"], [2, 2, 2])
        self.assertEqual(plot_payload["classical_state"]["repeat_cells"], [2, 2, 2])
        self.assertEqual(plot_payload["classical_state"]["render_mode"], "structure")

    def test_render_plots_skips_classical_state_when_reference_state_is_missing(self):
        raw_payload = {
            "model_name": "missing-classical-demo",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(raw_payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            plot_payload = json.loads((output_dir / "plot_payload.json").read_text(encoding="utf-8"))

            self.assertEqual(result["plots"]["classical_state"]["status"], "skipped")
            self.assertIn("classical reference state", result["plots"]["classical_state"]["reason"])
            self.assertEqual(plot_payload["classical_state"]["site_frames"], [])
            self.assertIn("classical reference state", plot_payload["classical_state"]["plot_reason"])

    def test_render_plots_draws_classical_summary_box_when_summary_lines_exist(self):
        plot_payload = {
            "metadata": {
                "model_name": "classical-summary-forwarding-demo",
                "backend": "Sunny.jl",
                "classical_method": "sunny-cpn-minimize",
                "lswt_status": "missing",
            },
            "classical_state": {
                "site_frames": [{"site": 0, "spin_length": 0.5, "direction": [1.0, 0.0, 0.0]}],
                "ordering": {"kind": "commensurate", "q_vector": [0.0, 0.0, 0.0]},
                "magnetic_periods": [1, 1, 1],
                "repeat_cells": [2, 1, 1],
                "spatial_dimension": 1,
                "summary_lines": ["method=sunny-cpn-minimize render_mode=chain spatial_dimension=1"],
                "expanded_sites": [
                    {
                        "basis_index": 0,
                        "label": "Atom 0",
                        "position": [0.0, 0.0, 0.0],
                        "direction": [1.0, 0.0, 0.0],
                        "display_direction": [1.0, 0.0, 0.0],
                        "color": "#1f77b4",
                    }
                ],
                "basis_legend": [{"basis_index": 0, "label": "Atom 0", "color": "#1f77b4"}],
                "unit_cell_segments": [],
                "lattice_vectors": [[1.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
                "render_mode": "chain",
                "view": {"projection": "chain"},
                "style": _default_structure_style(),
                "figure_size": [10.5, 4.2],
                "display_rotation": {"kind": "global", "source_direction": [0.0, 0.0, 1.0], "target_direction": [0.0, 0.0, 1.0]},
                "lattice_labels": [],
            },
            "lswt_dispersion": {"dispersion": [], "path": {}, "summary_lines": []},
            "thermodynamics": {"grid": [], "summary_lines": []},
        }

        captured = []

        def fake_draw_figure_summary(fig, summary_lines, *, y_top=0.95):
            captured.append(list(summary_lines or []))
            return False

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "output.render_plots._draw_figure_summary",
            side_effect=fake_draw_figure_summary,
        ):
            result = render_plots(plot_payload, output_dir=tmpdir)

        self.assertEqual(result["plots"]["classical_state"]["status"], "ok")
        self.assertEqual(captured[0][0], "method=sunny-cpn-minimize render_mode=chain spatial_dimension=1")

    def test_render_plots_adds_general_norb_cpn_observable_metadata(self):
        raw_payload = {
            "model_name": "cpn-norb3-demo",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [[2.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
            },
            "retained_local_space": {"dimension": 6, "factorization": {"orbital_count": 3}},
            "local_basis_labels": ["up_orb1", "down_orb1", "up_orb2", "down_orb2", "up_orb3", "down_orb3"],
            "classical": {
                "chosen_method": "sunny-cpn-minimize",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "supercell_shape": [1, 1, 1],
                    "local_rays": [
                        {
                            "cell": [0, 0, 0],
                            "vector": [
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.2, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                                {"real": 0.98, "imag": 0.0},
                                {"real": 0.0, "imag": 0.0},
                            ],
                        }
                    ],
                    "ordering": {
                        "ansatz": "single-q-unitary-ray",
                        "q_vector": [0.0, 0.0, 0.0],
                        "supercell_shape": [1, 1, 1],
                    },
                },
            },
            "lswt": {"status": "error", "backend": {"name": "Sunny.jl"}, "error": {"code": "missing", "message": "x"}},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = render_plots(raw_payload, output_dir=tmpdir)
            output_dir = Path(tmpdir)
            plot_payload = json.loads((output_dir / "plot_payload.json").read_text(encoding="utf-8"))

            self.assertEqual(result["plots"]["classical_state"]["status"], "ok")
            self.assertEqual(plot_payload["classical_state"]["orbital_count"], 3)
            self.assertEqual(plot_payload["classical_state"]["legend_title"], "Dominant Orbital")
            self.assertEqual(len(plot_payload["classical_state"]["orbital_legend"]), 3)
            self.assertEqual(
                plot_payload["classical_state"]["local_observables"][0]["orbital_weight_map"]["orb3"],
                plot_payload["classical_state"]["local_observables"][0]["dominant_orbital_weight"],
            )
            self.assertIn("orb3", plot_payload["classical_state"]["expanded_sites"][0]["annotation"])


if __name__ == "__main__":
    unittest.main()
