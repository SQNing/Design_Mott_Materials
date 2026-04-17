import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
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
