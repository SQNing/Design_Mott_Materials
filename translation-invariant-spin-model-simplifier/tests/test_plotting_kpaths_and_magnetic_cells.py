import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import math

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from lswt.build_lswt_payload import build_lswt_payload
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


if __name__ == "__main__":
    unittest.main()
