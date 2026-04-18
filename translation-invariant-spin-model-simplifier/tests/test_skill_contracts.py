import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = SKILL_ROOT / "SKILL.md"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import legacy.normalize_input as legacy_normalize_input
from input import normalize_freeform_text, normalize_input
from input.natural_language_parser import parse_controlled_natural_language
from input.parse_lattice_description import parse_lattice_description
from classical.decision_gates import linear_spin_wave_stage_decision
from cli.render_simplified_model_report import render_simplified_model_report
from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.identify_readable_blocks import identify_readable_blocks
from simplify.infer_symmetries import infer_symmetries


class SkillContractTests(unittest.TestCase):
    def test_skill_mentions_shared_operator_parsing_and_n_body_residual_fallback(self):
        text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("shared parser core", text)
        self.assertIn("n-body", text)
        self.assertIn("canonical residual", text)

    def test_skill_mentions_local_matrix_backbone_and_two_body_scope(self):
        text = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("local_matrix_record", text)
        self.assertIn("body_order <= 2", text)
        self.assertIn("DM", text)

    def test_legacy_normalize_input_wrapper_exposes_unified_input_entry_points(self):
        self.assertTrue(hasattr(legacy_normalize_input, "normalize_input"))
        self.assertTrue(hasattr(legacy_normalize_input, "normalize_freeform_text"))
        self.assertTrue(hasattr(legacy_normalize_input, "main"))

    def test_input_package_exposes_unified_document_candidate_selection_contract(self):
        fixture_path = SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex"
        fixture = fixture_path.read_text(encoding="utf-8")

        needs_input = normalize_freeform_text(fixture, source_path=str(fixture_path))
        landed = normalize_input(
            {
                "representation": "natural_language",
                "description": fixture,
                "source_path": str(fixture_path),
                "selected_model_candidate": "effective",
            }
        )

        self.assertEqual(needs_input["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(landed["interaction"]["id"], "local_bond_family_selection")
        self.assertEqual(sorted(landed["interaction"]["options"]), ["0'", "1", "1'", "2", "2a'", "3"])
        self.assertEqual(landed["document_intermediate"]["parameter_registry"]["D"], 2.165)

    def test_canonicalize_terms_accepts_direct_decomposition_payload(self):
        decomposition = {
            "mode": "spin-half-basis",
            "terms": [
                {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                {"label": "Sz@0 Sz@1", "coefficient": 1.0},
                {"label": "Sx@0 Sz@1", "coefficient": 0.05},
            ],
        }

        canonical = canonicalize_terms(decomposition)

        self.assertEqual(len(canonical["two_body"]), 4)
        self.assertEqual(canonical["two_body"][0]["canonical_label"], "Sx@0 Sx@1")
        self.assertEqual(canonical["two_body"][-1]["canonical_label"], "Sx@0 Sz@1")

    def test_canonicalize_terms_preserves_distinct_local_bond_families(self):
        decomposition = {
            "mode": "operator-basis",
            "terms": [
                {"label": "Sx@0 Sx@1", "coefficient": -0.161, "family": "1"},
                {"label": "Sy@0 Sy@1", "coefficient": -0.161, "family": "1"},
                {"label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "1"},
                {"label": "Sx@0 Sx@1", "coefficient": 0.017, "family": "2"},
                {"label": "Sy@0 Sy@1", "coefficient": 0.017, "family": "2"},
                {"label": "Sz@0 Sz@1", "coefficient": 0.052, "family": "2"},
            ],
        }

        canonical = canonicalize_terms(decomposition)

        family_one = [term for term in canonical["two_body"] if term.get("family") == "1"]
        family_two = [term for term in canonical["two_body"] if term.get("family") == "2"]
        self.assertEqual(len(family_one), 3)
        self.assertEqual(len(family_two), 3)
        self.assertNotEqual(
            {term["canonical_label"]: term["coefficient"] for term in family_one},
            {term["canonical_label"]: term["coefficient"] for term in family_two},
        )

    def test_identify_readable_blocks_recognizes_family_resolved_xxz_exchange(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.161, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.161, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sx@1", "coefficient": 0.017, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": 0.017, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": 0.052, "family": "2", "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        xxz_blocks = [block for block in readable["blocks"] if block["type"] == "xxz_exchange"]
        self.assertEqual(len(xxz_blocks), 2)
        self.assertEqual({block.get("family") for block in xxz_blocks}, {"1", "2"})
        self.assertFalse(readable["residual_terms"])

    def test_identify_readable_blocks_annotates_xxz_axes_from_coordinate_convention(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.161, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.161, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "explicit",
                "frame": "global_crystallographic",
                "axis_labels": ["a", "b", "c"],
                "quantization_axis": "c",
            },
        )

        xxz_blocks = [block for block in readable["blocks"] if block["type"] == "xxz_exchange"]
        self.assertEqual(len(xxz_blocks), 1)
        self.assertEqual(xxz_blocks[0]["coordinate_frame"], "global_crystallographic")
        self.assertEqual(xxz_blocks[0]["axis_labels"], ["a", "b", "c"])
        self.assertEqual(xxz_blocks[0]["planar_axes"], ["a", "b"])
        self.assertEqual(xxz_blocks[0]["longitudinal_axis"], "c")

    def test_identify_readable_blocks_recognizes_general_exchange_tensor(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sy@1", "coefficient": 0.010, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sz@1", "coefficient": -0.030, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sx@1", "coefficient": -0.020, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sx@1", "coefficient": 0.050, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.060, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "1", "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        tensor_blocks = [block for block in readable["blocks"] if block["type"] == "exchange_tensor"]
        self.assertEqual(len(tensor_blocks), 1)
        self.assertEqual(tensor_blocks[0]["family"], "1")
        self.assertEqual(tensor_blocks[0]["matrix"][0][1], 0.010)
        self.assertEqual(tensor_blocks[0]["matrix"][1][0], -0.020)
        self.assertEqual(tensor_blocks[0]["matrix"][2][1], 0.060)
        self.assertAlmostEqual(tensor_blocks[0]["dm_vector"][0], -0.01)
        self.assertAlmostEqual(tensor_blocks[0]["dm_vector"][1], 0.04)
        self.assertAlmostEqual(tensor_blocks[0]["dm_vector"][2], 0.015)
        self.assertIn("DM", tensor_blocks[0]["human_summary"])
        parameter_names = [entry["name"] for entry in tensor_blocks[0]["human_parameters"]]
        self.assertIn("Dx", parameter_names)
        self.assertIn("Dy", parameter_names)
        self.assertIn("Dz", parameter_names)
        self.assertFalse(readable["residual_terms"])

    def test_identify_readable_blocks_decomposes_exchange_tensor_into_symmetric_and_dm_parts(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sy@1", "coefficient": 0.010, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sz@1", "coefficient": -0.030, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sx@1", "coefficient": -0.020, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sx@1", "coefficient": 0.050, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.060, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "1", "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        tensor_blocks = [block for block in readable["blocks"] if block["type"] == "exchange_tensor"]
        self.assertEqual(len(tensor_blocks), 1)
        tensor = tensor_blocks[0]
        self.assertAlmostEqual(tensor["isotropic_exchange"], (-0.200 - 0.180 - 0.236) / 3.0)
        self.assertEqual(tensor["symmetric_matrix"][0][0], -0.200)
        self.assertAlmostEqual(tensor["symmetric_matrix"][0][1], -0.005)
        self.assertAlmostEqual(tensor["symmetric_matrix"][0][2], 0.010)
        self.assertAlmostEqual(tensor["symmetric_matrix"][1][2], 0.050)
        self.assertAlmostEqual(tensor["antisymmetric_matrix"][0][1], 0.015)
        self.assertAlmostEqual(tensor["antisymmetric_matrix"][1][0], -0.015)
        self.assertAlmostEqual(tensor["antisymmetric_matrix"][0][2], -0.040)
        self.assertAlmostEqual(tensor["antisymmetric_matrix"][2][0], 0.040)
        gamma_parameters = tensor["symmetric_offdiagonal_parameters"]
        self.assertEqual([entry["name"] for entry in gamma_parameters], ["Gamma_xy", "Gamma_xz", "Gamma_yz"])
        self.assertAlmostEqual(gamma_parameters[0]["value"], -0.005)
        self.assertAlmostEqual(gamma_parameters[1]["value"], 0.010)
        self.assertAlmostEqual(gamma_parameters[2]["value"], 0.050)
        self.assertEqual(
            [entry["name"] for entry in tensor["physical_parameter_view"]["parameters"]],
            ["Jiso", "Gamma_xy", "Gamma_xz", "Gamma_yz", "Dx", "Dy", "Dz"],
        )
        self.assertEqual(tensor["physical_parameter_view"]["view_kind"], "exchange_tensor_jiso_gamma_dm")
        self.assertIn("symmetric exchange", tensor["human_summary"].lower())

    def test_identify_readable_blocks_annotates_exchange_tensor_axes_from_coordinate_convention(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sy@1", "coefficient": 0.010, "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sz@1", "coefficient": -0.030, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sx@1", "coefficient": -0.020, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sx@1", "coefficient": 0.050, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.060, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "selected",
                "frame": "global_crystallographic",
                "axis_labels": ["a", "b", "c"],
                "quantization_axis": None,
            },
        )

        tensor_blocks = [block for block in readable["blocks"] if block["type"] == "exchange_tensor"]
        self.assertEqual(len(tensor_blocks), 1)
        self.assertEqual(tensor_blocks[0]["coordinate_frame"], "global_crystallographic")
        self.assertEqual(tensor_blocks[0]["matrix_axes"], ["a", "b", "c"])

    def test_identify_readable_blocks_resolves_local_axis_mapping_to_global_axes(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "explicit",
                "frame": "local_bond",
                "axis_labels": ["x", "y", "z"],
                "axis_mapping": {"x": "a", "y": "b", "z": "c"},
                "resolved_frame": "global_crystallographic",
                "quantization_axis": "c",
            },
        )

        matrix_blocks = [block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["coordinate_frame"], "local_bond")
        self.assertEqual(matrix_blocks[0]["matrix_axes"], ["x", "y", "z"])
        self.assertEqual(matrix_blocks[0]["resolved_coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])

    def test_identify_readable_blocks_rotates_symmetric_exchange_matrix_into_resolved_axes(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "explicit",
                "frame": "local_bond",
                "axis_labels": ["x", "y", "z"],
                "resolved_frame": "global_crystallographic",
                "resolved_axis_labels": ["a", "b", "c"],
                "rotation_matrix": [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            },
        )

        matrix_blocks = [block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_identify_readable_blocks_surfaces_gamma_parameters_for_symmetric_exchange_matrix(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sy@1", "coefficient": 0.030, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sx@1", "coefficient": 0.030, "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sz@1", "coefficient": -0.020, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sx@1", "coefficient": -0.020, "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.040, "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        matrix_blocks = [block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        block = matrix_blocks[0]
        gamma_parameters = block["symmetric_offdiagonal_parameters"]
        self.assertEqual([entry["name"] for entry in gamma_parameters], ["Gamma_xy", "Gamma_xz", "Gamma_yz"])
        self.assertAlmostEqual(gamma_parameters[0]["value"], 0.030)
        self.assertAlmostEqual(gamma_parameters[1]["value"], -0.020)
        self.assertAlmostEqual(gamma_parameters[2]["value"], 0.040)
        human_parameter_names = [entry["name"] for entry in block["human_parameters"]]
        self.assertIn("Gamma_xy", human_parameter_names)
        self.assertIn("Gamma_xz", human_parameter_names)
        self.assertIn("Gamma_yz", human_parameter_names)
        self.assertEqual(block["physical_parameter_view"]["view_kind"], "symmetric_exchange_matrix_jiso_gamma")
        self.assertEqual(
            [entry["name"] for entry in block["physical_parameter_view"]["parameters"]],
            ["Jiso", "Gamma_xy", "Gamma_xz", "Gamma_yz"],
        )
        self.assertIn("symmetric off-diagonal", block["human_summary"].lower())

    def test_identify_readable_blocks_builds_quadrupole_physical_parameter_view(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {
                    "canonical_label": "T2_0@0 T2_0@1",
                    "coefficient": -0.200,
                    "relative_weight": 1.0,
                    "body_order": 2,
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "family": "1",
                },
                {
                    "canonical_label": "T2_c1@0 T2_c1@1",
                    "coefficient": 0.080,
                    "relative_weight": 1.0,
                    "body_order": 2,
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "family": "1",
                },
                {
                    "canonical_label": "T2_s2@0 T2_s2@1",
                    "coefficient": -0.050,
                    "relative_weight": 1.0,
                    "body_order": 2,
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "family": "1",
                },
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        blocks = [block for block in readable["blocks"] if block["type"] == "quadrupole_coupling"]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block["physical_parameter_view"]["view_kind"], "quadrupole_coupling_components")
        self.assertEqual(
            [entry["name"] for entry in block["physical_parameter_view"]["parameters"]],
            ["T2_0:T2_0", "T2_c1:T2_c1", "T2_s2:T2_s2"],
        )
        self.assertIn("quadrupolar", block["physical_parameter_view"]["physical_label"])

    def test_identify_readable_blocks_builds_higher_multipole_physical_parameter_view(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {
                    "canonical_label": "O3_a@0 O3_a@1",
                    "coefficient": -0.120,
                    "relative_weight": 1.0,
                    "body_order": 2,
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "family": "1",
                },
                {
                    "canonical_label": "O3_b@0 O3_b@1",
                    "coefficient": 0.070,
                    "relative_weight": 1.0,
                    "body_order": 2,
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "family": "1",
                },
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(canonical_model)

        blocks = [block for block in readable["blocks"] if block["type"] == "higher_multipole_coupling"]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block["physical_parameter_view"]["view_kind"], "higher_multipole_coupling_rank_3_components")
        self.assertEqual(
            [entry["name"] for entry in block["physical_parameter_view"]["parameters"]],
            ["O3_a:O3_a", "O3_b:O3_b"],
        )
        self.assertIn("octupolar", block["physical_parameter_view"]["physical_label"])

    def test_identify_readable_blocks_applies_family_resolved_coordinate_conventions(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.040, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "1", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sx@1", "coefficient": 0.120, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": 0.050, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": -0.020, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": -0.020, "family": "2", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": 0.090, "family": "2", "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "explicit",
                "frame": "unspecified",
                "axis_labels": [],
                "family_overrides": {
                    "1": {
                        "status": "explicit",
                        "frame": "local_bond",
                        "axis_labels": ["x", "y", "z"],
                        "resolved_frame": "global_crystallographic",
                        "resolved_axis_labels": ["a", "b", "c"],
                        "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    },
                    "2": {
                        "status": "explicit",
                        "frame": "local_bond",
                        "axis_labels": ["x", "y", "z"],
                        "resolved_frame": "global_crystallographic",
                        "resolved_axis_labels": ["a", "b", "c"],
                        "rotation_matrix": [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
                    },
                },
            },
        )

        matrix_blocks = {block["family"]: block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"}
        self.assertEqual(set(matrix_blocks), {"1", "2"})
        self.assertEqual(matrix_blocks["1"]["resolved_matrix"][0][0], -0.200)
        self.assertEqual(matrix_blocks["1"]["resolved_matrix"][1][1], -0.180)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][0][0], 0.050)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][1][1], 0.120)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][0][2], -0.020)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][2][0], -0.020)

    def test_identify_readable_blocks_applies_bond_resolved_coordinate_conventions(self):
        canonical_model = {
            "one_body": [],
            "two_body": [
                {"canonical_label": "Sx@0 Sx@1", "coefficient": -0.200, "family": "x", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": -0.180, "family": "x", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": 0.040, "family": "x", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": 0.040, "family": "x", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": -0.236, "family": "x", "relative_weight": 1.0},
                {"canonical_label": "Sx@0 Sx@1", "coefficient": 0.120, "family": "y", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sy@1", "coefficient": 0.050, "family": "y", "relative_weight": 1.0},
                {"canonical_label": "Sy@0 Sz@1", "coefficient": -0.020, "family": "y", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sy@1", "coefficient": -0.020, "family": "y", "relative_weight": 1.0},
                {"canonical_label": "Sz@0 Sz@1", "coefficient": 0.090, "family": "y", "relative_weight": 1.0},
            ],
            "three_body": [],
            "four_body": [],
            "higher_body": [],
        }

        readable = identify_readable_blocks(
            canonical_model,
            coordinate_convention={
                "status": "explicit",
                "frame": "unspecified",
                "axis_labels": [],
                "bond_overrides": {
                    "x": {
                        "status": "explicit",
                        "frame": "local_bond",
                        "axis_labels": ["x", "y", "z"],
                        "resolved_frame": "global_crystallographic",
                        "resolved_axis_labels": ["a", "b", "c"],
                        "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                    },
                    "y": {
                        "status": "explicit",
                        "frame": "local_bond",
                        "axis_labels": ["x", "y", "z"],
                        "resolved_frame": "global_crystallographic",
                        "resolved_axis_labels": ["a", "b", "c"],
                        "rotation_matrix": [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
                    },
                },
            },
        )

        matrix_blocks = {block["family"]: block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"}
        self.assertEqual(set(matrix_blocks), {"x", "y"})
        self.assertEqual(matrix_blocks["x"]["resolved_matrix"][0][0], -0.200)
        self.assertEqual(matrix_blocks["x"]["resolved_matrix"][1][1], -0.180)
        self.assertEqual(matrix_blocks["y"]["resolved_matrix"][0][0], 0.050)
        self.assertEqual(matrix_blocks["y"]["resolved_matrix"][1][1], 0.120)

    def test_assemble_effective_model_adds_shell_resolved_exchange_summary(self):
        readable_model = {
            "blocks": [
                {"type": "xxz_exchange", "family": "1", "coefficient_xy": -0.161, "coefficient_z": -0.236},
                {"type": "xxz_exchange", "family": "2", "coefficient_xy": 0.017, "coefficient_z": 0.052},
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shell_block = shell_blocks[0]
        self.assertEqual([entry["family"] for entry in shell_block["shells"]], ["1", "2"])
        self.assertAlmostEqual(shell_block["shells"][0]["coefficient_xy"], -0.161)
        self.assertAlmostEqual(shell_block["shells"][1]["coefficient_z"], 0.052)

    def test_assemble_effective_model_shell_summary_accepts_common_exchange_block_types(self):
        readable_model = {
            "blocks": [
                {"type": "isotropic_exchange", "family": "1", "coefficient": -0.5},
                {"type": "dm_like", "family": "2", "coefficient": 0.12},
                {"type": "pseudospin_exchange", "family": "3", "coefficient": 0.8},
                {"type": "orbital_exchange", "family": "4", "coefficient": -0.3},
                {
                    "type": "symmetric_exchange_matrix",
                    "family": "5",
                    "matrix": [[-0.2, 0.0, 0.0], [0.0, -0.18, 0.04], [0.0, 0.04, -0.236]],
                },
                {
                    "type": "exchange_tensor",
                    "family": "6",
                    "matrix": [[-0.2, 0.01, -0.03], [-0.02, -0.18, 0.04], [0.05, 0.06, -0.236]],
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = shell_blocks[0]["shells"]
        self.assertEqual([entry["family"] for entry in shells], ["1", "2", "3", "4", "5", "6"])
        self.assertEqual(
            [entry["type"] for entry in shells],
            ["isotropic_exchange", "dm_like", "pseudospin_exchange", "orbital_exchange", "symmetric_exchange_matrix", "exchange_tensor"],
        )
        self.assertAlmostEqual(shells[0]["coefficient"], -0.5)
        self.assertAlmostEqual(shells[1]["coefficient"], 0.12)
        self.assertAlmostEqual(shells[2]["coefficient"], 0.8)
        self.assertAlmostEqual(shells[3]["coefficient"], -0.3)
        self.assertEqual(shells[4]["matrix"][1][2], 0.04)
        self.assertEqual(shells[5]["matrix"][0][1], 0.01)

    def test_assemble_effective_model_shell_summary_preserves_physical_parameter_views(self):
        readable_model = {
            "blocks": [
                {
                    "type": "symmetric_exchange_matrix",
                    "family": "1",
                    "physical_label": "anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm)",
                    "human_parameters": [
                        {"name": "Jzz", "value": -0.236, "kind": "longitudinal"},
                        {"name": "Jpm", "value": -0.236, "kind": "planar_average"},
                        {"name": "Jpmpm", "value": -0.161, "kind": "planar_anisotropy"},
                        {"name": "Jzpm", "value": -0.261, "kind": "offdiagonal_mixing"},
                    ],
                    "physical_parameter_view": {
                        "view_kind": "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm",
                        "parameters": [
                            {"name": "Jzz", "value": -0.236, "kind": "longitudinal"},
                            {"name": "Jpm", "value": -0.236, "kind": "planar_average"},
                            {"name": "Jpmpm", "value": -0.161, "kind": "planar_anisotropy"},
                            {"name": "Jzpm", "value": -0.261, "kind": "offdiagonal_mixing"},
                        ],
                    },
                },
                {
                    "type": "symmetric_exchange_matrix",
                    "family": "2",
                    "physical_label": "anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm)",
                    "human_parameters": [
                        {"name": "Jzz", "value": 0.113, "kind": "longitudinal"},
                        {"name": "Jpm", "value": 0.026, "kind": "planar_average"},
                        {"name": "Jpmpm", "value": 0.0, "kind": "planar_anisotropy"},
                        {"name": "Jzpm", "value": 0.0, "kind": "offdiagonal_mixing"},
                    ],
                    "physical_parameter_view": {
                        "view_kind": "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm",
                        "parameters": [
                            {"name": "Jzz", "value": 0.113, "kind": "longitudinal"},
                            {"name": "Jpm", "value": 0.026, "kind": "planar_average"},
                            {"name": "Jpmpm", "value": 0.0, "kind": "planar_anisotropy"},
                            {"name": "Jzpm", "value": 0.0, "kind": "offdiagonal_mixing"},
                        ],
                    },
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = shell_blocks[0]["shells"]
        self.assertEqual(shells[0]["physical_parameter_view"]["view_kind"], "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm")
        self.assertEqual(
            [entry["name"] for entry in shells[0]["physical_parameter_view"]["parameters"]],
            ["Jzz", "Jpm", "Jpmpm", "Jzpm"],
        )
        self.assertAlmostEqual(shells[1]["physical_parameter_view"]["parameters"][0]["value"], 0.113)

    def test_assemble_effective_model_derives_exchange_tensor_physical_parameter_view(self):
        readable_model = {
            "blocks": [
                {
                    "type": "exchange_tensor",
                    "family": "1",
                    "matrix": [[-0.2, 0.01, -0.03], [-0.02, -0.18, 0.04], [0.05, 0.06, -0.236]],
                    "human_parameters": [
                        {"name": "Jxx", "value": -0.2, "kind": "diagonal"},
                        {"name": "Jyy", "value": -0.18, "kind": "diagonal"},
                        {"name": "Jzz", "value": -0.236, "kind": "diagonal"},
                        {"name": "Jxy", "value": [0.01, -0.02], "kind": "offdiagonal"},
                        {"name": "Jxz", "value": [-0.03, 0.05], "kind": "offdiagonal"},
                        {"name": "Jyz", "value": [0.04, 0.06], "kind": "offdiagonal"},
                        {"name": "Jiso", "value": -0.20533333333333334, "kind": "isotropic"},
                        {"name": "Gamma_xy", "value": -0.005, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_xz", "value": 0.01, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_yz", "value": 0.05, "kind": "symmetric_offdiagonal"},
                        {"name": "Dx", "value": -0.01, "kind": "dm"},
                        {"name": "Dy", "value": 0.04, "kind": "dm"},
                        {"name": "Dz", "value": 0.015, "kind": "dm"},
                    ],
                },
                {
                    "type": "exchange_tensor",
                    "family": "2",
                    "matrix": [[-0.1, 0.0, 0.02], [0.03, -0.11, 0.0], [-0.01, 0.04, -0.12]],
                    "human_parameters": [
                        {"name": "Jxx", "value": -0.1, "kind": "diagonal"},
                        {"name": "Jyy", "value": -0.11, "kind": "diagonal"},
                        {"name": "Jzz", "value": -0.12, "kind": "diagonal"},
                        {"name": "Jxz", "value": [0.02, -0.01], "kind": "offdiagonal"},
                        {"name": "Jxy", "value": [0.0, 0.03], "kind": "offdiagonal"},
                        {"name": "Jyz", "value": [0.0, 0.04], "kind": "offdiagonal"},
                        {"name": "Jiso", "value": -0.11, "kind": "isotropic"},
                        {"name": "Gamma_xz", "value": 0.005, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_xy", "value": 0.015, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_yz", "value": 0.02, "kind": "symmetric_offdiagonal"},
                        {"name": "Dx", "value": -0.02, "kind": "dm"},
                        {"name": "Dy", "value": -0.015, "kind": "dm"},
                        {"name": "Dz", "value": -0.015, "kind": "dm"},
                    ],
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = shell_blocks[0]["shells"]
        self.assertEqual(shells[0]["physical_parameter_view"]["view_kind"], "exchange_tensor_jiso_gamma_dm")
        self.assertEqual(
            [entry["name"] for entry in shells[0]["physical_parameter_view"]["parameters"]],
            ["Jiso", "Gamma_xy", "Gamma_xz", "Gamma_yz", "Dx", "Dy", "Dz"],
        )
        self.assertAlmostEqual(shells[1]["physical_parameter_view"]["parameters"][0]["value"], -0.11)

    def test_assemble_effective_model_derives_symmetric_exchange_physical_parameter_view(self):
        readable_model = {
            "blocks": [
                {
                    "type": "symmetric_exchange_matrix",
                    "family": "1",
                    "matrix": [[-0.2, 0.03, -0.02], [0.03, -0.18, 0.04], [-0.02, 0.04, -0.236]],
                    "human_parameters": [
                        {"name": "Jxx", "value": -0.2, "kind": "diagonal"},
                        {"name": "Jyy", "value": -0.18, "kind": "diagonal"},
                        {"name": "Jzz", "value": -0.236, "kind": "diagonal"},
                        {"name": "Gamma_xy", "value": 0.03, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_xz", "value": -0.02, "kind": "symmetric_offdiagonal"},
                        {"name": "Gamma_yz", "value": 0.04, "kind": "symmetric_offdiagonal"},
                        {"name": "Jiso", "value": -0.20533333333333334, "kind": "isotropic"},
                    ],
                },
                {
                    "type": "symmetric_exchange_matrix",
                    "family": "2",
                    "matrix": [[0.1, 0.0, 0.05], [0.0, 0.12, 0.0], [0.05, 0.0, 0.14]],
                    "human_parameters": [
                        {"name": "Jxx", "value": 0.1, "kind": "diagonal"},
                        {"name": "Jyy", "value": 0.12, "kind": "diagonal"},
                        {"name": "Jzz", "value": 0.14, "kind": "diagonal"},
                        {"name": "Gamma_xz", "value": 0.05, "kind": "symmetric_offdiagonal"},
                        {"name": "Jiso", "value": 0.12, "kind": "isotropic"},
                    ],
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = shell_blocks[0]["shells"]
        self.assertEqual(shells[0]["physical_parameter_view"]["view_kind"], "symmetric_exchange_matrix_jiso_gamma")
        self.assertEqual(
            [entry["name"] for entry in shells[0]["physical_parameter_view"]["parameters"]],
            ["Jiso", "Gamma_xy", "Gamma_xz", "Gamma_yz"],
        )
        self.assertEqual(
            [entry["name"] for entry in shells[1]["physical_parameter_view"]["parameters"]],
            ["Jiso", "Gamma_xz"],
        )

    def test_assemble_effective_model_derives_multipole_physical_parameter_views(self):
        readable_model = {
            "blocks": [
                {
                    "type": "quadrupole_coupling",
                    "family": "1",
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "human_parameters": [
                        {"name": "T2_0:T2_0", "value": -0.200, "kind": "quadrupole_component"},
                        {"name": "T2_c1:T2_c1", "value": 0.080, "kind": "quadrupole_component"},
                    ],
                },
                {
                    "type": "quadrupole_coupling",
                    "family": "2",
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "human_parameters": [
                        {"name": "T2_0:T2_0", "value": -0.150, "kind": "quadrupole_component"},
                        {"name": "T2_s2:T2_s2", "value": 0.040, "kind": "quadrupole_component"},
                    ],
                },
                {
                    "type": "higher_multipole_coupling",
                    "family": "3",
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "human_parameters": [
                        {"name": "O3_a:O3_a", "value": -0.120, "kind": "higher_multipole_component"},
                        {"name": "O3_b:O3_b", "value": 0.070, "kind": "higher_multipole_component"},
                    ],
                },
                {
                    "type": "higher_multipole_coupling",
                    "family": "4",
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "human_parameters": [
                        {"name": "O3_a:O3_a", "value": -0.090, "kind": "higher_multipole_component"},
                    ],
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = {entry["family"]: entry for entry in shell_blocks[0]["shells"]}
        self.assertEqual(shells["1"]["physical_parameter_view"]["view_kind"], "quadrupole_coupling_components")
        self.assertEqual(shells["3"]["physical_parameter_view"]["view_kind"], "higher_multipole_coupling_rank_3_components")
        self.assertEqual(
            [entry["name"] for entry in shells["1"]["physical_parameter_view"]["parameters"]],
            ["T2_0:T2_0", "T2_c1:T2_c1"],
        )
        self.assertEqual(
            [entry["name"] for entry in shells["3"]["physical_parameter_view"]["parameters"]],
            ["O3_a:O3_a", "O3_b:O3_b"],
        )

    def test_assemble_effective_model_merges_same_family_multipole_views_into_exchange_shell(self):
        readable_model = {
            "blocks": [
                {
                    "type": "xxz_exchange",
                    "family": "1",
                    "coefficient_xy": 0.2,
                    "coefficient_z": 0.5,
                    "physical_parameter_view": {
                        "view_kind": "xxz_exchange_jxy_jz",
                        "physical_label": "xxz exchange",
                        "parameters": [
                            {"name": "Jxy", "value": 0.2, "kind": "planar"},
                            {"name": "Jz", "value": 0.5, "kind": "longitudinal"},
                        ],
                    },
                    "additional_physical_parameter_views": [
                        {
                            "view_kind": "dipole_multipole_components",
                            "physical_label": "dipole multipole components",
                            "parameters": [
                                {"name": "T1_x:T1_x", "value": 0.2, "kind": "dipole_component"},
                                {"name": "T1_y:T1_y", "value": 0.2, "kind": "dipole_component"},
                                {"name": "T1_z:T1_z", "value": 0.5, "kind": "dipole_component"},
                            ],
                        }
                    ],
                },
                {
                    "type": "quadrupole_coupling",
                    "family": "1",
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "physical_parameter_view": {
                        "view_kind": "quadrupole_coupling_components",
                        "physical_label": "quadrupolar coupling components",
                        "parameters": [
                            {"name": "T2_0:T2_0", "value": -0.150, "kind": "quadrupole_component"},
                            {"name": "T2_c1:T2_c1", "value": 0.040, "kind": "quadrupole_component"},
                        ],
                    },
                },
                {
                    "type": "higher_multipole_coupling",
                    "family": "1",
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "physical_parameter_view": {
                        "view_kind": "higher_multipole_coupling_rank_3_components",
                        "physical_label": "octupolar coupling components",
                        "parameters": [
                            {"name": "O3_a:O3_a", "value": -0.120, "kind": "higher_multipole_component"},
                        ],
                    },
                },
                {
                    "type": "xxz_exchange",
                    "family": "2",
                    "coefficient_xy": 0.1,
                    "coefficient_z": 0.3,
                    "physical_parameter_view": {
                        "view_kind": "xxz_exchange_jxy_jz",
                        "physical_label": "xxz exchange",
                        "parameters": [
                            {"name": "Jxy", "value": 0.1, "kind": "planar"},
                            {"name": "Jz", "value": 0.3, "kind": "longitudinal"},
                        ],
                    },
                },
            ],
            "residual_terms": [],
        }

        effective = assemble_effective_model(readable_model)

        shell_blocks = [block for block in effective["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = {entry["family"]: entry for entry in shell_blocks[0]["shells"]}
        self.assertEqual(list(shells), ["1", "2"])
        self.assertEqual(shells["1"]["type"], "xxz_exchange")
        self.assertEqual(shells["1"]["physical_parameter_view"]["view_kind"], "xxz_exchange_jxy_jz")
        additional_views = list(shells["1"].get("additional_physical_parameter_views") or [])
        self.assertEqual(
            [view["view_kind"] for view in additional_views],
            [
                "dipole_multipole_components",
                "quadrupole_coupling_components",
                "higher_multipole_coupling_rank_3_components",
            ],
        )
        self.assertEqual(shells["2"].get("additional_physical_parameter_views"), None)

    def test_render_simplified_model_report_unions_shell_parameter_columns_within_view_kind(self):
        payload = {
            "status": "ok",
            "stage": "complete",
            "effective_model": {
                "main": [
                    {
                        "type": "shell_resolved_exchange",
                        "shells": [
                            {
                                "family": "1",
                                "type": "symmetric_exchange_matrix",
                                "physical_parameter_view": {
                                    "view_kind": "symmetric_exchange_matrix_jiso_gamma",
                                    "physical_label": "symmetric exchange matrix (Jiso/Gamma)",
                                    "parameters": [
                                        {"name": "Jiso", "value": -0.20533333333333334, "kind": "isotropic"},
                                        {"name": "Gamma_xz", "value": -0.020, "kind": "symmetric_offdiagonal"},
                                    ],
                                },
                            },
                            {
                                "family": "2",
                                "type": "symmetric_exchange_matrix",
                                "physical_parameter_view": {
                                    "view_kind": "symmetric_exchange_matrix_jiso_gamma",
                                    "physical_label": "symmetric exchange matrix (Jiso/Gamma)",
                                    "parameters": [
                                        {"name": "Jiso", "value": 0.120, "kind": "isotropic"},
                                        {"name": "Gamma_xy", "value": 0.030, "kind": "symmetric_offdiagonal"},
                                        {"name": "Gamma_xz", "value": 0.010, "kind": "symmetric_offdiagonal"},
                                        {"name": "Gamma_yz", "value": 0.040, "kind": "symmetric_offdiagonal"},
                                    ],
                                },
                            },
                        ],
                    }
                ],
                "residual_summary": [],
                "residual": [],
                "low_weight_summary": [],
                "low_weight": [],
            },
        }

        report = render_simplified_model_report(payload, title="Shell Summary Test")

        self.assertIn("## Shell-Resolved Physical Summary", report)
        self.assertIn("### symmetric exchange matrix (Jiso/Gamma)", report)
        self.assertIn("| Family", report)
        self.assertIn("Jiso", report)
        self.assertIn("Gamma_xy", report)
        self.assertIn("Gamma_xz", report)
        self.assertIn("Gamma_yz", report)

    def test_render_simplified_model_report_renders_multipole_shell_summaries(self):
        payload = {
            "status": "ok",
            "stage": "complete",
            "effective_model": {
                "main": [
                    {
                        "type": "shell_resolved_exchange",
                        "shells": [
                            {
                                "family": "1",
                                "type": "quadrupole_coupling",
                                "physical_parameter_view": {
                                    "view_kind": "quadrupole_coupling_components",
                                    "physical_label": "quadrupolar coupling components",
                                    "parameters": [
                                        {"name": "T2_0:T2_0", "value": -0.200, "kind": "quadrupole_component"},
                                        {"name": "T2_c1:T2_c1", "value": 0.080, "kind": "quadrupole_component"},
                                    ],
                                },
                            },
                            {
                                "family": "2",
                                "type": "quadrupole_coupling",
                                "physical_parameter_view": {
                                    "view_kind": "quadrupole_coupling_components",
                                    "physical_label": "quadrupolar coupling components",
                                    "parameters": [
                                        {"name": "T2_0:T2_0", "value": -0.150, "kind": "quadrupole_component"},
                                        {"name": "T2_s2:T2_s2", "value": 0.040, "kind": "quadrupole_component"},
                                    ],
                                },
                            },
                            {
                                "family": "3",
                                "type": "higher_multipole_coupling",
                                "physical_parameter_view": {
                                    "view_kind": "higher_multipole_coupling_rank_3_components",
                                    "physical_label": "octupolar coupling components",
                                    "parameters": [
                                        {"name": "O3_a:O3_a", "value": -0.120, "kind": "higher_multipole_component"},
                                        {"name": "O3_b:O3_b", "value": 0.070, "kind": "higher_multipole_component"},
                                    ],
                                },
                            },
                            {
                                "family": "4",
                                "type": "higher_multipole_coupling",
                                "physical_parameter_view": {
                                    "view_kind": "higher_multipole_coupling_rank_3_components",
                                    "physical_label": "octupolar coupling components",
                                    "parameters": [
                                        {"name": "O3_a:O3_a", "value": -0.090, "kind": "higher_multipole_component"},
                                    ],
                                },
                            },
                        ],
                    }
                ],
                "residual_summary": [],
                "residual": [],
                "low_weight_summary": [],
                "low_weight": [],
            },
        }

        report = render_simplified_model_report(payload, title="Multipole Summary Test")

        self.assertIn("### quadrupolar coupling components", report)
        self.assertIn("T2_0:T2_0", report)
        self.assertIn("T2_c1:T2_c1", report)
        self.assertIn("T2_s2:T2_s2", report)
        self.assertIn("### octupolar coupling components", report)
        self.assertIn("O3_a:O3_a", report)
        self.assertIn("O3_b:O3_b", report)

    def test_render_simplified_model_report_renders_secondary_shell_views(self):
        payload = {
            "status": "ok",
            "stage": "complete",
            "effective_model": {
                "main": [
                    {
                        "type": "shell_resolved_exchange",
                        "shells": [
                            {
                                "family": "1",
                                "type": "xxz_exchange",
                                "physical_parameter_view": {
                                    "view_kind": "xxz_exchange_jxy_jz",
                                    "physical_label": "xxz exchange",
                                    "parameters": [
                                        {"name": "Jxy", "value": 0.2, "kind": "planar"},
                                        {"name": "Jz", "value": 0.5, "kind": "longitudinal"},
                                    ],
                                },
                                "additional_physical_parameter_views": [
                                    {
                                        "view_kind": "dipole_multipole_components",
                                        "physical_label": "dipole multipole components",
                                        "parameters": [
                                            {"name": "T1_x:T1_x", "value": 0.2, "kind": "dipole_component"},
                                            {"name": "T1_y:T1_y", "value": 0.2, "kind": "dipole_component"},
                                            {"name": "T1_z:T1_z", "value": 0.5, "kind": "dipole_component"},
                                        ],
                                    }
                                ],
                            },
                            {
                                "family": "2",
                                "type": "xxz_exchange",
                                "physical_parameter_view": {
                                    "view_kind": "xxz_exchange_jxy_jz",
                                    "physical_label": "xxz exchange",
                                    "parameters": [
                                        {"name": "Jxy", "value": 0.1, "kind": "planar"},
                                        {"name": "Jz", "value": 0.3, "kind": "longitudinal"},
                                    ],
                                },
                                "additional_physical_parameter_views": [
                                    {
                                        "view_kind": "dipole_multipole_components",
                                        "physical_label": "dipole multipole components",
                                        "parameters": [
                                            {"name": "T1_x:T1_x", "value": 0.1, "kind": "dipole_component"},
                                            {"name": "T1_z:T1_z", "value": 0.3, "kind": "dipole_component"},
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                ],
                "residual_summary": [],
                "residual": [],
                "low_weight_summary": [],
                "low_weight": [],
            },
        }

        report = render_simplified_model_report(payload, title="Dual View Test")

        self.assertIn("### xxz exchange", report)
        self.assertIn("### dipole multipole components", report)
        self.assertIn("T1_x:T1_x", report)
        self.assertIn("T1_y:T1_y", report)
        self.assertIn("T1_z:T1_z", report)

    def test_parse_controlled_natural_language_merges_hexagonal_and_exchange_mapping_ambiguity(self):
        result = parse_controlled_natural_language(
            "Spin-1/2 J1-J2 model on a hexagonal lattice with two magnetic sites per unit cell; please run spin-wave analysis after simplification."
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["question"]["id"], "lattice_and_exchange_mapping")
        self.assertIn("hexagonal lattice", result["question"]["prompt"])
        self.assertIn("J1/J2", result["question"]["prompt"])

    def test_parse_lattice_description_uses_same_combined_ambiguity_contract(self):
        result = parse_lattice_description(
            {
                "kind": "natural_language",
                "value": "Spin-1/2 J1-J2 model on a hexagonal lattice with two magnetic sites per unit cell; please run spin-wave analysis after simplification.",
            }
        )

        self.assertEqual(result["interaction"]["status"], "needs_input")
        self.assertEqual(result["interaction"]["id"], "lattice_and_exchange_mapping")
        self.assertIn("hexagonal lattice", result["interaction"]["question"])
        self.assertIn("J1/J2", result["interaction"]["question"])

    def test_infer_symmetries_does_not_report_su2_when_cross_anisotropy_is_present(self):
        model = {
            "decomposition": {
                "terms": [
                    {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                    {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                    {"label": "Sz@0 Sz@1", "coefficient": 1.0},
                    {"label": "Sx@0 Sz@1", "coefficient": 0.05},
                ]
            },
            "user_required_symmetries": [],
            "allowed_breaking": [],
        }

        inferred = infer_symmetries(model)

        self.assertNotIn("su2_spin", inferred["detected_symmetries"])
        self.assertNotIn("u1_spin", inferred["detected_symmetries"])

    def test_linear_spin_wave_stage_decision_adds_stability_precheck_confirmation_when_risk_signals_exist(self):
        model = {
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "classical": {"chosen_method": "luttinger-tisza"},
            "effective_model": {
                "main": [{"type": "isotropic_exchange", "coefficient": 1.0}],
                "low_weight": [{"canonical_label": "Sx@0 Sz@1", "coefficient": 0.05}],
                "residual": [],
            },
            "lt_result": {"q": [0.5, 0.0, 0.0], "lowest_eigenvalue": -2.0},
        }

        decision = linear_spin_wave_stage_decision(model, run_lswt=True)

        self.assertEqual(decision["status"], "needs_input")
        self.assertEqual(decision["question"]["id"], "lswt_stability_precheck")
        self.assertIn("Stability precheck raised concerns", decision["question"]["prompt"])
        self.assertIn("classical_method=luttinger-tisza", decision["question"]["prompt"])
        self.assertIn("low_weight_terms_present", decision["question"]["prompt"])
        self.assertIn("cross_axis_term=Sx@0 Sz@1", decision["question"]["prompt"])
        self.assertEqual(decision["recommended"], "continue")
        self.assertEqual(decision["question"]["options"], ["continue", "stop"])

    def test_linear_spin_wave_stage_decision_skips_precheck_confirmation_when_no_risk_signals_exist(self):
        model = {
            "q_path": [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            "classical": {"chosen_method": "variational"},
            "effective_model": {
                "main": [{"type": "isotropic_exchange", "coefficient": 1.0}],
                "low_weight": [],
                "residual": [],
            },
        }

        decision = linear_spin_wave_stage_decision(model, run_lswt=True)

        self.assertEqual(decision["status"], "ok")
        self.assertTrue(decision["enabled"])
        self.assertEqual(decision["q_path_mode"], "user-specified")


if __name__ == "__main__":
    unittest.main()
