import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.compile_local_term_to_matrix import compile_local_term_to_matrix
from simplify.decompose_local_term import decompose_local_term
from simplify.identify_readable_blocks import identify_readable_blocks
from simplify.local_matrix_record import build_local_matrix_record
from simplify.spin_multipole_basis import build_spin_multipole_basis


class SpinSPipelineTests(unittest.TestCase):
    def test_decompose_spin_one_local_matrix_returns_ranked_labels(self):
        basis = {entry["label"]: entry["matrix"] for entry in build_spin_multipole_basis(1)}
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "matrix",
                    "value": basis["T2_0"],
                },
            },
            "parameters": {},
        }

        result = decompose_local_term(normalized)

        self.assertEqual(result["mode"], "spin-multipole-basis")
        self.assertTrue(any(term["label"].startswith("T2_") for term in result["terms"]))

    def test_spin_one_operator_text_matrix_route_promotes_onsite_quadrupole_metadata(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0],
                "representation": {
                    "kind": "operator",
                    "value": "D*(Sz@0)^2",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"D": 2.165},
        }

        record = compile_local_term_to_matrix(normalized)
        decomposition = decompose_local_term({"local_term_record": record})
        canonical = canonicalize_terms({"decomposition": decomposition})

        self.assertEqual(decomposition["mode"], "spin-multipole-basis")
        self.assertTrue(canonical["one_body"])
        self.assertTrue(any(term.get("multipole_rank") == 2 for term in canonical["one_body"]))
        self.assertTrue(any(term.get("multipole_family") == "quadrupole" for term in canonical["one_body"]))

    def test_spin_one_compact_two_body_operator_matrix_route_promotes_dipole_metadata(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Jx * Sx@0 Sx@1 + Jy * Sy@0 Sy@1 + Jz * Sz@0 Sz@1",
                },
            },
            "coordinate_convention": {"frame": "global_xyz"},
            "parameters": {"Jx": 0.4, "Jy": 0.1, "Jz": -0.2},
            "selected_local_bond_family": "1",
        }

        record = compile_local_term_to_matrix(normalized)
        decomposition = decompose_local_term({"local_term_record": record})
        canonical = canonicalize_terms({"decomposition": decomposition})

        self.assertEqual(decomposition["mode"], "spin-multipole-basis")
        self.assertTrue(canonical["two_body"])
        self.assertTrue(any(term.get("multipole_rank") == 1 for term in canonical["two_body"]))
        self.assertTrue(any(term.get("multipole_family") == "dipole" for term in canonical["two_body"]))

    def test_canonicalize_ranked_spin_multipole_labels_and_keep_them_in_residual(self):
        model = {
            "terms": [
                {"label": "Sx@0 Sx@1", "coefficient": 1.0},
                {"label": "Sy@0 Sy@1", "coefficient": 1.0},
                {"label": "Sz@0 Sz@1", "coefficient": 1.0},
                {"label": "T2_0@0", "coefficient": 0.5},
                {"label": "T2_c1@0 T2_c1@1", "coefficient": 1.2},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)
        effective = assemble_effective_model(readable)

        self.assertEqual(canonical["one_body"][0]["multipole_rank"], 2)
        self.assertEqual(canonical["one_body"][0]["multipole_family"], "quadrupole")
        self.assertTrue(any(block["type"] == "isotropic_exchange" for block in readable["blocks"]))
        self.assertTrue(any(block["type"] == "quadrupole_coupling" for block in readable["blocks"]))
        residual_labels = {term["canonical_label"] for term in effective["residual"]}
        self.assertIn("T2_0@0", residual_labels)
        self.assertNotIn("T2_c1@0 T2_c1@1", residual_labels)

    def test_effective_model_summarizes_residual_multipoles_by_family_rank_and_body(self):
        readable = {
            "blocks": [],
            "residual_terms": [
                {
                    "canonical_label": "T2_0@0",
                    "coefficient": 0.5,
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "body_order": 1,
                    "relative_weight": 1.0,
                    "symmetry_annotations": [],
                },
                {
                    "canonical_label": "T2_c1@0 T2_c1@1",
                    "coefficient": 1.2,
                    "multipole_family": "quadrupole",
                    "multipole_rank": 2,
                    "body_order": 2,
                    "relative_weight": 1.0,
                    "symmetry_annotations": [],
                },
                {
                    "canonical_label": "T3_0@0 T3_0@1",
                    "coefficient": -0.8,
                    "multipole_family": "higher_multipole",
                    "multipole_rank": 3,
                    "body_order": 2,
                    "relative_weight": 1.0,
                    "symmetry_annotations": [],
                },
            ],
        }

        effective = assemble_effective_model(readable)

        summary = effective.get("residual_summary", [])
        self.assertEqual(len(summary), 3)
        self.assertEqual(summary[0]["multipole_family"], "quadrupole")
        self.assertEqual(summary[0]["multipole_rank"], 2)
        self.assertEqual(summary[0]["body_order"], 2)
        self.assertEqual(summary[0]["term_count"], 1)
        self.assertAlmostEqual(summary[0]["max_abs_coefficient"], 1.2)
        self.assertEqual(summary[-1]["multipole_rank"], 2)
        self.assertEqual(summary[-1]["body_order"], 1)

    def test_identify_readable_blocks_promotes_quadrupole_two_body_terms_to_generic_block(self):
        model = {
            "terms": [
                {"label": "T2_0@0 T2_0@1", "coefficient": 0.5},
                {"label": "T2_c1@0 T2_c1@1", "coefficient": 1.2},
                {"label": "T2_s1@0 T2_s1@1", "coefficient": -0.7},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)
        effective = assemble_effective_model(readable)

        quadrupole_blocks = [block for block in readable["blocks"] if block["type"] == "quadrupole_coupling"]
        self.assertEqual(len(quadrupole_blocks), 1)
        block = quadrupole_blocks[0]
        self.assertEqual(block["multipole_family"], "quadrupole")
        self.assertEqual(block["multipole_rank"], 2)
        self.assertEqual(block["body_order"], 2)
        self.assertEqual(block["physical_label"], "quadrupolar")
        self.assertEqual(block["physical_tendency"], "antiferroquadrupolar_like")
        self.assertEqual(block["dominant_channel_label"], "off-diagonal quadrupolar (Qzx/Qyz-like)")
        self.assertEqual(block["term_count"], 3)
        self.assertEqual(block["dominant_component"], "T2_c1:T2_c1")
        self.assertTrue(block["human_summary"].startswith("Quadrupolar two-body coupling"))
        self.assertIn("antiferroquadrupolar-like", block["human_summary"])
        self.assertIn("off-diagonal quadrupolar", block["human_summary"])
        self.assertTrue(any(entry["name"] == "T2_c1:T2_c1" for entry in block["human_parameters"]))
        self.assertIn(block, effective["main"])
        self.assertEqual(effective["residual"], [])

    def test_identify_readable_blocks_promotes_rank_three_two_body_terms_to_generic_multipole_block(self):
        model = {
            "terms": [
                {"label": "T3_0@0 T3_0@1", "coefficient": 0.9},
                {"label": "T3_c1@0 T3_s1@1", "coefficient": -0.6},
                {"label": "T3_s2@0 T3_c2@1", "coefficient": 0.4},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)
        effective = assemble_effective_model(readable)

        multipole_blocks = [block for block in readable["blocks"] if block["type"] == "higher_multipole_coupling"]
        self.assertEqual(len(multipole_blocks), 1)
        block = multipole_blocks[0]
        self.assertEqual(block["multipole_family"], "higher_multipole")
        self.assertEqual(block["multipole_rank"], 3)
        self.assertEqual(block["physical_label"], "octupolar")
        self.assertEqual(block["body_order"], 2)
        self.assertEqual(block["term_count"], 3)
        self.assertEqual(block["dominant_component"], "T3_0:T3_0")
        self.assertTrue(block["human_summary"].startswith("Octupolar two-body coupling"))
        self.assertIn(block, effective["main"])
        self.assertEqual(effective["residual"], [])

    def test_identify_readable_blocks_can_keep_exchange_and_dipole_multipole_views_together(self):
        model = {
            "terms": [
                {"label": "T1_x@0 T1_x@1", "coefficient": 0.2},
                {"label": "T1_y@0 T1_y@1", "coefficient": 0.2},
                {"label": "T1_z@0 T1_z@1", "coefficient": 0.5},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)

        xxz_blocks = [block for block in readable["blocks"] if block["type"] == "xxz_exchange"]
        self.assertEqual(len(xxz_blocks), 1)
        block = xxz_blocks[0]
        self.assertEqual(block["physical_parameter_view"]["view_kind"], "xxz_exchange_jxy_jz")
        additional_views = list(block.get("additional_physical_parameter_views") or [])
        self.assertEqual(len(additional_views), 1)
        self.assertEqual(additional_views[0]["view_kind"], "dipole_multipole_components")
        self.assertEqual(
            [entry["name"] for entry in additional_views[0]["parameters"]],
            ["T1_x:T1_x", "T1_y:T1_y", "T1_z:T1_z"],
        )

    def test_identify_readable_blocks_can_derive_dipole_view_from_spin_operator_source_terms(self):
        model = {
            "terms": [
                {"label": "Sx@0 Sx@1", "coefficient": -0.397},
                {"label": "Sy@0 Sy@1", "coefficient": -0.075},
                {"label": "Sz@0 Sz@1", "coefficient": -0.236},
                {"label": "Sy@0 Sz@1", "coefficient": -0.261},
                {"label": "Sz@0 Sy@1", "coefficient": -0.261},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)

        matrix_blocks = [block for block in readable["blocks"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        block = matrix_blocks[0]
        self.assertEqual(block["physical_parameter_view"]["view_kind"], "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm")
        additional_views = list(block.get("additional_physical_parameter_views") or [])
        self.assertEqual(len(additional_views), 1)
        self.assertEqual(additional_views[0]["view_kind"], "dipole_multipole_components")
        self.assertEqual(
            [entry["name"] for entry in additional_views[0]["parameters"]],
            ["T1_x:T1_x", "T1_y:T1_y", "T1_z:T1_z", "T1_y:T1_z", "T1_z:T1_y"],
        )

    def test_identify_readable_blocks_splits_mixed_rank_higher_multipoles_into_multiple_blocks(self):
        model = {
            "terms": [
                {"label": "T3_0@0 T3_0@1", "coefficient": 0.9},
                {"label": "T3_c1@0 T3_s1@1", "coefficient": -0.6},
                {"label": "T4_0@0 T4_0@1", "coefficient": 1.1},
                {"label": "T4_c1@0 T4_s1@1", "coefficient": 0.5},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)
        effective = assemble_effective_model(readable)

        multipole_blocks = [block for block in readable["blocks"] if block["type"] == "higher_multipole_coupling"]
        self.assertEqual(len(multipole_blocks), 2)
        self.assertEqual([block["multipole_rank"] for block in multipole_blocks], [4, 3])
        self.assertEqual([block["physical_label"] for block in multipole_blocks], ["hexadecapolar", "octupolar"])
        self.assertEqual(multipole_blocks[0]["dominant_component"], "T4_0:T4_0")
        self.assertEqual(multipole_blocks[1]["dominant_component"], "T3_0:T3_0")
        self.assertEqual(effective["residual"], [])

    def test_identify_readable_blocks_maps_rank_five_and_six_to_standard_terms(self):
        model = {
            "terms": [
                {"label": "T5_0@0 T5_0@1", "coefficient": 0.8},
                {"label": "T6_0@0 T6_0@1", "coefficient": 1.3},
            ]
        }

        canonical = canonicalize_terms(model)
        readable = identify_readable_blocks(canonical)

        multipole_blocks = [block for block in readable["blocks"] if block["type"] == "higher_multipole_coupling"]
        self.assertEqual([block["multipole_rank"] for block in multipole_blocks], [6, 5])
        self.assertEqual(
            [block["physical_label"] for block in multipole_blocks],
            ["hexacontatetrapolar", "dotriacontapolar"],
        )
        self.assertEqual(
            [block["physical_label_aliases"] for block in multipole_blocks],
            [["tetrahexacontapolar"], ["triakontadipolar"]],
        )
        self.assertTrue(multipole_blocks[0]["human_summary"].startswith("Hexacontatetrapolar two-body coupling"))
        self.assertTrue(multipole_blocks[1]["human_summary"].startswith("Dotriacontapolar two-body coupling"))

    def test_three_body_operator_string_enters_spin_s_pipeline_without_raw_operator(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": "Sp@0 Sm@1 Sz@2",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertTrue(canonical["three_body"])
        self.assertTrue(all(term["body_order"] == 3 for term in canonical["three_body"]))

    def test_latex_three_body_operator_string_enters_spin_s_pipeline_without_raw_operator(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": r"K_{ijk} S_i^z S_j^z S_k^z",
                },
            },
            "parameters": {"K_{ijk}": 0.5},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertEqual(len(canonical["three_body"]), 1)
        self.assertEqual(canonical["three_body"][0]["canonical_label"], "Sz@0 Sz@1 Sz@2")
        self.assertAlmostEqual(canonical["three_body"][0]["coefficient"], 0.5)

    def test_latex_parenthesized_three_body_operator_enters_spin_s_pipeline_without_raw_operator(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": r"\left(S_i^+ S_j^- + S_i^- S_j^+\right) S_k^z",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["three_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sx@1 Sz@2"], 2.0)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1 Sz@2"], 2.0)

    def test_latex_symbolic_coefficient_parenthesized_three_body_operator_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": r"K_{ijk}\left(S_i^+ S_j^- + S_i^- S_j^+\right) S_k^z",
                },
            },
            "parameters": {"K_{ijk}": 0.75},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["three_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sx@1 Sz@2"], 1.5)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1 Sz@2"], 1.5)

    def test_compact_grouped_sum_with_term_coefficients_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": "(J1*Sp@0 Sm@1 + J2*Sm@0 Sp@1) Sz@2",
                },
            },
            "parameters": {"J1": 1.0, "J2": 2.0},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["three_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sx@1 Sz@2"], 3.0)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1 Sz@2"], 3.0)
        self.assertAlmostEqual(by_label["Sx@0 Sy@1 Sz@2"], 1.0j)
        self.assertAlmostEqual(by_label["Sy@0 Sx@1 Sz@2"], -1.0j)

    def test_latex_grouped_sum_with_symbolic_coefficient_products_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": r"\left(J_1 S_i^+ + J_2 S_i^-\right)\left(A S_j^+ + B S_j^-\right) S_k^z",
                },
            },
            "parameters": {"J_1": 1.0, "J_2": 2.0, "A": 3.0, "B": 4.0},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["three_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sx@1 Sz@2"], 21.0)
        self.assertAlmostEqual(by_label["Sx@0 Sy@1 Sz@2"], -3.0j)
        self.assertAlmostEqual(by_label["Sy@0 Sx@1 Sz@2"], -7.0j)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1 Sz@2"], -1.0)

    def test_imaginary_unit_two_body_operator_string_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "-i*(Sp@0 Sm@1 - Sm@0 Sp@1)",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["two_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sy@1"], -2.0)
        self.assertAlmostEqual(by_label["Sy@0 Sx@1"], 2.0)

    def test_complex_literal_two_body_operator_string_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "1j*(Sp@0 Sm@1 - Sm@0 Sp@1)",
                },
            },
            "parameters": {},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["two_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sy@1"], 2.0)
        self.assertAlmostEqual(by_label["Sy@0 Sx@1"], -2.0)

    def test_hc_shorthand_bypasses_partial_cartesian_fast_path_and_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "J*Sx@0 Sy@1 + h.c.",
                },
            },
            "parameters": {"J": 1.0 + 1.0j},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["two_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertEqual(list(by_label), ["Sx@0 Sy@1"])
        self.assertAlmostEqual(by_label["Sx@0 Sy@1"], 2.0)

    def test_site_swap_shorthand_bypasses_partial_cartesian_fast_path_and_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "J*Sz@0 Sz@1 + (i<->j)",
                },
            },
            "parameters": {"J": 1.25},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["two_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertEqual(list(by_label), ["Sz@0 Sz@1"])
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], 2.5)

    def test_real_part_wrapper_bypasses_partial_fast_path_and_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1],
                "representation": {
                    "kind": "operator",
                    "value": "Re[J*Sp@0 Sz@1]",
                },
            },
            "parameters": {"J": 1.0 + 2.0j},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["two_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sz@1"], 1.0)
        self.assertAlmostEqual(by_label["Sy@0 Sz@1"], -2.0)

    def test_cyclic_permutation_shorthand_enters_spin_s_pipeline(self):
        normalized = {
            "local_hilbert": {"dimension": 3},
            "local_term": {
                "support": [0, 1, 2],
                "representation": {
                    "kind": "operator",
                    "value": "K*Sx@0 Sy@1 Sz@2 + cyclic perm.",
                },
            },
            "parameters": {"K": 0.5},
        }

        decomposition = decompose_local_term(normalized)
        canonical = canonicalize_terms({"decomposition": decomposition})
        by_label = {term["canonical_label"]: term["coefficient"] for term in canonical["three_body"]}

        self.assertEqual(decomposition["mode"], "operator-basis")
        self.assertFalse(any(term["label"] == "raw-operator" for term in decomposition["terms"]))
        self.assertAlmostEqual(by_label["Sx@0 Sy@1 Sz@2"], 0.5)
        self.assertAlmostEqual(by_label["Sz@0 Sx@1 Sy@2"], 0.5)
        self.assertAlmostEqual(by_label["Sy@0 Sz@1 Sx@2"], 0.5)

    def test_canonicalize_five_body_term_into_higher_body_bucket(self):
        canonical = canonicalize_terms(
            {
                "terms": [
                    {
                        "label": "Sz@0 Sz@1 Sz@2 Sz@3 Sz@4",
                        "coefficient": 1.0,
                    }
                ]
            }
        )

        self.assertEqual(len(canonical["higher_body"]), 1)
        self.assertEqual(canonical["higher_body"][0]["body_order"], 5)
        self.assertEqual(canonical["higher_body"][0]["support"], [0, 1, 2, 3, 4])

    def test_canonicalize_uses_distinct_sites_for_body_order(self):
        canonical = canonicalize_terms(
            {
                "terms": [
                    {
                        "label": "Sz@0 Sz@0 Sz@1 Sz@2 Sz@3",
                        "coefficient": 1.0,
                    }
                ]
            }
        )

        self.assertEqual(canonical["higher_body"], [])
        self.assertEqual(len(canonical["four_body"]), 1)
        self.assertEqual(canonical["four_body"][0]["body_order"], 4)
        self.assertEqual(canonical["four_body"][0]["support"], [0, 1, 2, 3])

    def test_local_matrix_record_backbone_can_enter_spin_s_pipeline(self):
        record = build_local_matrix_record(
            support=[0, 1],
            family="1",
            geometry_class="bond",
            coordinate_frame="global_xyz",
            local_basis_order=["m=1", "m=0", "m=-1"],
            tensor_product_order=[0, 1],
            matrix=[[0.0 for _ in range(9)] for _ in range(9)],
            provenance={
                "source_kind": "operator_text",
                "source_expression": "Sp@0 Sm@1",
                "parameter_map": {},
            },
        )

        decomposition = decompose_local_term({"local_term_record": record})
        canonical = canonicalize_terms({"decomposition": decomposition})

        self.assertEqual(decomposition["source_backbone"], "local_matrix_record")
        self.assertTrue(canonical["two_body"])

    def test_canonicalize_preserves_family_and_matrix_backbone_metadata(self):
        canonical = canonicalize_terms(
            {
                "decomposition": {
                    "mode": "operator-basis",
                    "source_backbone": "local_matrix_record",
                    "terms": [
                        {
                            "label": "Sx@0 Sx@1",
                            "coefficient": -0.161,
                            "family": "1",
                        },
                        {
                            "label": "Sz@0",
                            "coefficient": 2.165,
                            "source_geometry_class": "onsite",
                        },
                    ],
                }
            }
        )

        self.assertEqual(canonical["two_body"][0]["family"], "1")
        self.assertEqual(canonical["two_body"][0]["source_backbone"], "local_matrix_record")
        self.assertEqual(canonical["one_body"][0]["source_backbone"], "local_matrix_record")
        self.assertEqual(canonical["one_body"][0]["source_geometry_class"], "onsite")


if __name__ == "__main__":
    unittest.main()
