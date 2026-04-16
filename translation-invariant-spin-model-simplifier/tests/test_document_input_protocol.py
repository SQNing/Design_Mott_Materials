import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.document_input_protocol import (
    build_intermediate_record,
    detect_input_kind,
    land_intermediate_record,
)


class DocumentInputProtocolTests(unittest.TestCase):
    FEI2_FAMILY_ONE_FIXTURE = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}H_{ij}^{(1)}
\;+\!
\sum_{n\in\{2,3,0',1',2a'\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right]
-D\sum_i (S_i^z)^2 .
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right)
\nonumber\\
&-
\frac{iJ_1^{z\pm}}{2}
\left[
(\gamma_{ij}^\ast S_i^+-\gamma_{ij}S_i^-)S_j^z
+
S_i^z(\gamma_{ij}^\ast S_j^+-\gamma_{ij}S_j^-)
\right].
\end{align}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm\pm} = -0.161
\end{equation}
\begin{equation}
J_1^{z\pm} = -0.261
\end{equation}
\end{document}
"""

    FEI2_FAMILY_ONE_WITH_MATRIX_FIXTURE = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}H_{ij}^{(1)} .
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right)
\nonumber\\
&-
\frac{iJ_1^{z\pm}}{2}
\left[
(\gamma_{ij}^\ast S_i^+-\gamma_{ij}S_i^-)S_j^z
+
S_i^z(\gamma_{ij}^\ast S_j^+-\gamma_{ij}S_j^-)
\right].
\end{align}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\begin{equation}
J_1^{xx}=J_1^{\pm}+J_1^{\pm\pm},\qquad
J_1^{yy}=J_1^{\pm}-J_1^{\pm\pm},\qquad
J_1^{yz}=J_1^{z\pm}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm\pm} = -0.161
\end{equation}
\begin{equation}
J_1^{z\pm} = -0.261
\end{equation}
\end{document}
"""

    def test_detect_input_kind_marks_tex_documents(self):
        result = detect_input_kind(
            source_text="\\section*{Effective Hamiltonian}\n\\begin{equation}H=...",
        )

        self.assertEqual(result["source_kind"], "tex_document")

    def test_extract_intermediate_record_separates_multiple_model_candidates(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
        )

        self.assertEqual(
            [candidate["name"] for candidate in record["model_candidates"]],
            ["toy", "effective", "matrix_form"],
        )
        self.assertTrue(record["ambiguities"])

    def test_land_selected_candidate_to_payload_preserves_unsupported_features(self):
        record = {
            "source_document": {"source_kind": "tex_document"},
            "selected_model_candidate": "effective",
            "model_candidates": [
                {"name": "effective", "role": "main"},
            ],
            "hamiltonian_model": {
                "operator_expression": "J * Sz@0 Sz@1 - D * Sz@0 Sz@0",
            },
            "parameter_registry": {"J": -0.236, "D": 2.165},
            "ambiguities": [],
            "unsupported_features": ["matrix_form_metadata"],
        }

        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("unsupported_features", landed)
        self.assertIn("matrix_form_metadata", landed["unsupported_features"])

    def test_fei2_style_fixture_requires_model_selection_before_landing(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "model_candidate_selection")

    def test_selected_model_candidate_allows_multi_model_document_to_land(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
            selected_model_candidate="effective",
        )
        record["hamiltonian_model"] = {"operator_expression": "J1zz * Sz@0 Sz@1"}
        record["parameter_registry"] = {"J1zz": -0.236}

        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertEqual(landed["expression"], "J1zz * Sz@0 Sz@1")

    def test_selected_matrix_form_candidate_bypasses_primary_model_selection_ambiguity(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertFalse(record["ambiguities"])

    def test_selected_effective_candidate_extracts_expression_and_parameters_from_document(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Toy Hamiltonian}
\begin{equation}
H_{\mathrm{toy}}=J\sum_{\langle i,j\rangle}\bm S_i\cdot\bm S_j-D\sum_i (S_i^z)^2.
\end{equation}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}J_1^{zz}S_i^zS_j^z
-D\sum_i (S_i^z)^2 .
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+).
\end{align}
\section*{Parameters}
\begin{table}[h]
\centering
\begin{tabular}{ccc}
\toprule
Parameter & $J_1^{zz}$ & $J_1^{\pm}$ \\
\midrule
Value (meV) & $-0.236$ & $-0.161$ \\
\bottomrule
\end{tabular}
\end{table}
\begin{equation}
D = 2.165 \pm 0.101~\text{meV}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/fei2_document_input.tex",
            selected_model_candidate="effective",
        )
        landed = land_intermediate_record(record)

        self.assertIn("J_1^{zz}S_i^zS_j^z", record["hamiltonian_model"]["local_bond_candidates"][0]["expression"])
        self.assertEqual(record["parameter_registry"]["J_1^{zz}"], -0.236)
        self.assertEqual(record["parameter_registry"]["J_1^{\\pm}"], -0.161)
        self.assertEqual(record["parameter_registry"]["D"], 2.165)
        self.assertIn("J_1^{zz}S_i^zS_j^z", landed["expression"])
        self.assertEqual(landed["parameters"]["D"], 2.165)

    def test_selected_family_one_preserves_bond_phase_unsupported_features(self):
        record = build_intermediate_record(
            source_text=self.FEI2_FAMILY_ONE_FIXTURE,
            source_path="tests/data/fei2_family_one_fixture.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="1",
        )

        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("bond_dependent_phase_gamma_terms", landed["unsupported_features"])
        self.assertIn("double_raising_lowering_exchange_terms", landed["unsupported_features"])
        self.assertIn("zpm_offdiagonal_exchange_terms", landed["unsupported_features"])

    def test_matrix_form_candidate_derives_exchange_parameters_from_effective_relations(self):
        record = build_intermediate_record(
            source_text=self.FEI2_FAMILY_ONE_WITH_MATRIX_FIXTURE,
            source_path="tests/data/fei2_family_one_with_matrix_fixture.tex",
            selected_model_candidate="matrix_form",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertAlmostEqual(landed["parameters"]["J_1^{xx}"], -0.397)
        self.assertAlmostEqual(landed["parameters"]["J_1^{yy}"], -0.075)
        self.assertAlmostEqual(landed["parameters"]["J_1^{yz}"], -0.261)
        self.assertIn("J_1^{xx} * Sx@0 Sx@1", landed["expression"])

    def test_matrix_form_candidate_derives_exchange_parameters_from_fractional_and_parenthesized_relations(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(2)}=
\begin{pmatrix}
J_2^{xx} & 0 & 0 \\
0 & J_2^{yy} & J_2^{yz} \\
0 & J_2^{yz} & J_2^{zz}
\end{pmatrix}.
\end{equation}
\begin{equation}
J_2^{xx}=\frac{1}{2}(J_2^{\pm}+J_2^{\pm\pm}),\qquad
J_2^{yy}=(J_2^{\pm}-J_2^{\pm\pm}),\qquad
J_2^{yz}=-2J_2^{z\pm}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_2^{zz} = -0.220
\end{equation}
\begin{equation}
J_2^{\pm} = -0.200
\end{equation}
\begin{equation}
J_2^{\pm\pm} = -0.100
\end{equation}
\begin{equation}
J_2^{z\pm} = 0.050
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_fraction_parentheses_fixture.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="2",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertAlmostEqual(landed["parameters"]["J_2^{xx}"], -0.150)
        self.assertAlmostEqual(landed["parameters"]["J_2^{yy}"], -0.100)
        self.assertAlmostEqual(landed["parameters"]["J_2^{yz}"], -0.100)
        self.assertIn("J_2^{xx} * Sx@0 Sx@1", landed["expression"])

    def test_matrix_form_candidate_derives_exchange_parameters_from_tfrac_dfrac_and_explicit_multiplication(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(3)}=
\begin{pmatrix}
J_3^{xx} & 0 & 0 \\
0 & J_3^{yy} & J_3^{yz} \\
0 & J_3^{yz} & J_3^{zz}
\end{pmatrix}.
\end{equation}
\begin{equation}
J_3^{xx}=\tfrac{3}{2}\left(J_3^{\pm}-0.5\cdot J_3^{\pm\pm}\right),\qquad
J_3^{yy}=0.25\times\left(J_3^{\pm}+J_3^{\pm\pm}\right),\qquad
J_3^{yz}=\dfrac{J_3^{z\pm}}{2}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_3^{zz} = -0.210
\end{equation}
\begin{equation}
J_3^{\pm} = 0.160
\end{equation}
\begin{equation}
J_3^{\pm\pm} = -0.080
\end{equation}
\begin{equation}
J_3^{z\pm} = 0.120
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_tfrac_dfrac_fixture.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="3",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertAlmostEqual(landed["parameters"]["J_3^{xx}"], 0.300)
        self.assertAlmostEqual(landed["parameters"]["J_3^{yy}"], 0.020)
        self.assertAlmostEqual(landed["parameters"]["J_3^{yz}"], 0.060)
        self.assertIn("J_3^{xx} * Sx@0 Sx@1", landed["expression"])

    def test_matrix_form_candidate_derives_exchange_parameters_from_align_environment_relations(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(4)}=
\begin{pmatrix}
J_4^{xx} & 0 & 0 \\
0 & J_4^{yy} & J_4^{yz} \\
0 & J_4^{yz} & J_4^{zz}
\end{pmatrix}.
\end{equation}
\begin{align}
J_4^{xx} &= \frac{1}{2}\left(J_4^{\pm}+J_4^{\pm\pm}\right), \nonumber\\
J_4^{yy} &= \left(J_4^{\pm}-J_4^{\pm\pm}\right), \\
J_4^{yz} &= -2 J_4^{z\pm}.
\end{align}
\section*{Parameters}
\begin{equation}
J_4^{zz} = -0.190
\end{equation}
\begin{equation}
J_4^{\pm} = 0.140
\end{equation}
\begin{equation}
J_4^{\pm\pm} = 0.020
\end{equation}
\begin{equation}
J_4^{z\pm} = -0.030
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_align_fixture.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="4",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertAlmostEqual(landed["parameters"]["J_4^{xx}"], 0.080)
        self.assertAlmostEqual(landed["parameters"]["J_4^{yy}"], 0.120)
        self.assertAlmostEqual(landed["parameters"]["J_4^{yz}"], 0.060)
        self.assertIn("J_4^{xx} * Sx@0 Sx@1", landed["expression"])

    def test_document_protocol_extracts_single_q_rotating_frame_context(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Magnetic Order}
The ordered state is a single-Q spiral with propagation vector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$ in reciprocal lattice units. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Effective Hamiltonian}
\begin{equation}
H=J S_i^z S_j^z.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/single_q_rotating_frame.tex",
            selected_model_candidate="effective",
        )

        order = record["system_context"]["magnetic_order"]
        self.assertEqual(order["status"], "explicit")
        self.assertEqual(order["kind"], "single_q_spiral")
        self.assertEqual(order["wavevector"], [0.25, 0.0, 0.25])
        self.assertEqual(order["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(order["reference_frame"]["kind"], "rotating")
        self.assertEqual(order["reference_frame"]["phase_origin"], "Q_dot_r")

    def test_document_protocol_infers_reciprocal_lattice_units_for_single_q_from_hkl_context(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The reciprocal lattice basis vectors are denoted by $\mathbf b_1,\mathbf b_2,\mathbf b_3$.
\section*{Magnetic Order}
The ordered state is a single-Q spiral with ordering wavevector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$ in the $(h,k,l)$ basis. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Effective Hamiltonian}
\begin{equation}
H=J S_i^z S_j^z.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/single_q_hkl_basis.tex",
            selected_model_candidate="effective",
        )

        order = record["system_context"]["magnetic_order"]
        self.assertEqual(order["wavevector_units"], "reciprocal_lattice_units")

    def test_selected_matrix_form_candidate_extracts_operator_basis_expression_from_exchange_matrix(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.200
\end{equation}
\begin{equation}
J_1^{yy} = -0.180
\end{equation}
\begin{equation}
J_1^{yz} = 0.040
\end{equation}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_input.tex",
            selected_model_candidate="matrix_form",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertEqual(landed["coordinate_convention"]["status"], "selected")
        self.assertEqual(landed["coordinate_convention"]["frame"], "global_crystallographic")
        self.assertIn("J_1^{xx} * Sx@0 Sx@1", landed["expression"])
        self.assertIn("J_1^{yy} * Sy@0 Sy@1", landed["expression"])
        self.assertIn("J_1^{zz} * Sz@0 Sz@1", landed["expression"])
        self.assertIn("J_1^{yz} * Sy@0 Sz@1", landed["expression"])
        self.assertIn("J_1^{yz} * Sz@0 Sy@1", landed["expression"])

    def test_selected_matrix_form_candidate_accepts_bmatrix_environment(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(5)}=
\begin{bmatrix}
J_5^{xx} & 0 & 0 \\
0 & J_5^{yy} & J_5^{yz} \\
0 & J_5^{yz} & J_5^{zz}
\end{bmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_5^{xx} = -0.300
\end{equation}
\begin{equation}
J_5^{yy} = -0.120
\end{equation}
\begin{equation}
J_5^{yz} = 0.055
\end{equation}
\begin{equation}
J_5^{zz} = -0.210
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_bmatrix_input.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="5",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("J_5^{xx} * Sx@0 Sx@1", landed["expression"])
        self.assertIn("J_5^{yy} * Sy@0 Sy@1", landed["expression"])
        self.assertIn("J_5^{yz} * Sy@0 Sz@1", landed["expression"])

    def test_document_protocol_extracts_rotation_matrix_from_Bmatrix_environment(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. The local axes are related to the global crystallographic a,b,c axes by the rotation matrix
\begin{equation}
R=
\begin{Bmatrix}
0 & 1 & 0 \\
1 & 0 & 0 \\
0 & 0 & 1
\end{Bmatrix}
\end{equation}
such that $(S^x,S^y,S^z)^T = R (S^a,S^b,S^c)^T$.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_rotation_bmatrix.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_selected_matrix_form_candidate_requests_coordinate_convention_when_anisotropic_and_unspecified(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.200
\end{equation}
\begin{equation}
J_1^{yy} = -0.180
\end{equation}
\begin{equation}
J_1^{yz} = 0.040
\end{equation}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_input.tex",
            selected_model_candidate="matrix_form",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "coordinate_convention_selection")

    def test_document_protocol_extracts_explicit_coordinate_convention_metadata(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes. The local z axis is along c.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.200
\end{equation}
\begin{equation}
J_1^{yy} = -0.180
\end{equation}
\begin{equation}
J_1^{yz} = 0.040
\end{equation}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_with_axes.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "global_crystallographic")
        self.assertEqual(convention["axis_labels"], ["a", "b", "c"])
        self.assertEqual(convention["quantization_axis"], "c")

    def test_document_protocol_extracts_local_axis_mapping_to_global_crystallographic(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. The local x axis is along a, the local y axis is along b, and the local z axis is along c.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_local_axes.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["axis_labels"], ["x", "y", "z"])
        self.assertEqual(convention["axis_mapping"], {"x": "a", "y": "b", "z": "c"})
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["quantization_axis"], "c")

    def test_document_protocol_extracts_explicit_local_to_global_rotation_matrix(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. The local axes are related to the global crystallographic a,b,c axes by the rotation matrix
\begin{equation}
R=
\begin{pmatrix}
0 & 1 & 0 \\
1 & 0 & 0 \\
0 & 0 & 1
\end{pmatrix}
\end{equation}
such that $(S^x,S^y,S^z)^T = R (S^a,S^b,S^c)^T$.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_rotation_axes.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["axis_labels"], ["x", "y", "z"])
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_rotation_matrix_from_direction_cosine_table(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. The direction cosines of the local axes in the global crystallographic a,b,c basis are
\begin{tabular}{c|ccc}
 & a & b & c \\
x & 0 & 1 & 0 \\
y & 1 & 0 & 0 \\
z & 0 & 0 & 1 \\
\end{tabular}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_direction_cosine_table.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_rotation_matrix_from_textual_direction_cosines(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. In the global crystallographic a,b,c basis, the local x axis has direction cosines (0,1,0), the local y axis has direction cosines (1,0,0), and the local z axis has direction cosines (0,0,1).
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_direction_cosine_text.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_rotation_matrix_from_transposed_direction_cosine_table(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. The direction cosines of the global crystallographic a,b,c axes resolved along the local x,y,z axes are
\begin{tabular}{c|ccc}
 & x & y & z \\
a & 0 & 1 & 0 \\
b & 1 & 0 & 0 \\
c & 0 & 0 & 1 \\
\end{tabular}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_direction_cosine_table_transposed.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_rotation_matrix_from_compact_hat_axis_vectors(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the local bond frame. In the global crystallographic a,b,c basis, \hat{x}=(0,1,0), \hat{y}=(1,0,0), \hat{z}=(0,0,1).
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_hat_axis_vectors.tex",
            selected_model_candidate="matrix_form",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertEqual(convention["status"], "explicit")
        self.assertEqual(convention["frame"], "local_bond")
        self.assertEqual(convention["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_family_resolved_local_coordinate_conventions(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
For bond family 1, spin components are expressed in the local bond frame. The local x axis is along a, the local y axis is along b, and the local z axis is along c.

For bond family 2, spin components are expressed in the local bond frame. In the global crystallographic a,b,c basis, the local x axis has direction cosines (0,1,0), the local y axis has direction cosines (1,0,0), and the local z axis has direction cosines (0,0,1).
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\begin{equation}
\mathcal J_{ij}^{(2)}=
\begin{pmatrix}
J_2^{xx} & 0 & 0 \\
0 & J_2^{yy} & J_2^{yz} \\
0 & J_2^{yz} & J_2^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_family_local_frames.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="all",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertIn("family_overrides", convention)
        self.assertEqual(convention["family_overrides"]["1"]["frame"], "local_bond")
        self.assertEqual(convention["family_overrides"]["1"]["resolved_frame"], "global_crystallographic")
        self.assertEqual(convention["family_overrides"]["1"]["axis_mapping"], {"x": "a", "y": "b", "z": "c"})
        self.assertEqual(
            convention["family_overrides"]["1"]["rotation_matrix"],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )
        self.assertEqual(convention["family_overrides"]["2"]["frame"], "local_bond")
        self.assertEqual(convention["family_overrides"]["2"]["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["family_overrides"]["2"]["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_document_protocol_extracts_bond_resolved_local_coordinate_conventions(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
For x bond, spin components are expressed in the local bond frame. The local x axis is along a, the local y axis is along b, and the local z axis is along c.

For y bond, spin components are expressed in the local bond frame. In the global crystallographic a,b,c basis, the local x axis has direction cosines (0,1,0), the local y axis has direction cosines (1,0,0), and the local z axis has direction cosines (0,0,1).
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(x)}=
\begin{pmatrix}
J_x^{xx} & 0 & 0 \\
0 & J_x^{yy} & J_x^{yz} \\
0 & J_x^{yz} & J_x^{zz}
\end{pmatrix}.
\end{equation}
\begin{equation}
\mathcal J_{ij}^{(y)}=
\begin{pmatrix}
J_y^{xx} & 0 & 0 \\
0 & J_y^{yy} & J_y^{yz} \\
0 & J_y^{yz} & J_y^{zz}
\end{pmatrix}.
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_bond_local_frames.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="all",
        )

        convention = record["system_context"]["coordinate_convention"]
        self.assertIn("bond_overrides", convention)
        self.assertEqual(convention["bond_overrides"]["x"]["resolved_frame"], "global_crystallographic")
        self.assertEqual(
            convention["bond_overrides"]["x"]["rotation_matrix"],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )
        self.assertEqual(convention["bond_overrides"]["y"]["resolved_axis_labels"], ["a", "b", "c"])
        self.assertEqual(
            convention["bond_overrides"]["y"]["rotation_matrix"],
            [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        )

    def test_selected_matrix_form_candidate_can_land_when_coordinate_convention_is_provided_explicitly(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.200
\end{equation}
\begin{equation}
J_1^{yy} = -0.180
\end{equation}
\begin{equation}
J_1^{yz} = 0.040
\end{equation}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/matrix_form_input.tex",
            selected_model_candidate="matrix_form",
            selected_coordinate_convention="global_crystallographic",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertEqual(landed["coordinate_convention"]["status"], "selected")
        self.assertEqual(landed["coordinate_convention"]["frame"], "global_crystallographic")

    def test_selected_effective_candidate_prefers_explicit_local_bond_definition_over_global_sum(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}H_{ij}^{(1)}.
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+).
\end{align}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.161
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/summed_effective_model.tex",
            selected_model_candidate="effective",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertNotIn(r"\sum_{\langle i,j\rangle_1}", landed["expression"])
        self.assertIn("J_1^{zz}S_i^zS_j^z", landed["expression"])
        self.assertIn(r"\frac{J_1^{\pm}}{2}", landed["expression"])
        self.assertEqual(landed["parameters"]["J_1^{zz}"], -0.236)

    def test_family_indexed_effective_template_requests_local_bond_family_selection(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{n\in\{1,2\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right].
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.161
\end{equation}
\begin{equation}
J_2^{zz} = 0.052
\end{equation}
\begin{equation}
J_2^{\pm} = 0.017
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_model_candidate="effective",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "local_bond_family_selection")
        self.assertIn("family", landed["interaction"]["question"].lower())

    def test_family_indexed_effective_template_lands_selected_local_bond_family(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{n\in\{1,2\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right].
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.161
\end{equation}
\begin{equation}
J_2^{zz} = 0.052
\end{equation}
\begin{equation}
J_2^{\pm} = 0.017
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="2",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("J_2^{zz}S_i^zS_j^z", landed["expression"])
        self.assertIn(r"\frac{J_2^{\pm}}{2}", landed["expression"])
        self.assertNotIn("J_1^{zz}", landed["expression"])

    def test_mixed_explicit_and_family_indexed_effective_model_requests_local_bond_family_selection(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}H_{ij}^{(1)}
\;+\!
\sum_{n\in\{2,3\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right].
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right).
\end{align}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.161
\end{equation}
\begin{equation}
J_1^{\pm\pm} = -0.261
\end{equation}
\begin{equation}
J_2^{zz} = 0.052
\end{equation}
\begin{equation}
J_2^{\pm} = 0.017
\end{equation}
\begin{equation}
J_3^{zz} = 0.101
\end{equation}
\begin{equation}
J_3^{\pm} = 0.023
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/mixed_family_effective_model.tex",
            selected_model_candidate="effective",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "local_bond_family_selection")
        self.assertEqual(sorted(landed["interaction"]["options"]), ["1", "2", "3"])

    def test_mixed_explicit_and_family_indexed_effective_model_lands_selected_nonnearest_family(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_1}H_{ij}^{(1)}
\;+\!
\sum_{n\in\{2,3\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right].
\end{equation}
\begin{align}
H_{ij}^{(1)}=\;&
J_1^{zz}S_i^zS_j^z
+
\frac{J_1^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_1^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right).
\end{align}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
J_1^{\pm} = -0.161
\end{equation}
\begin{equation}
J_1^{\pm\pm} = -0.261
\end{equation}
\begin{equation}
J_2^{zz} = 0.052
\end{equation}
\begin{equation}
J_2^{\pm} = 0.017
\end{equation}
\begin{equation}
J_3^{zz} = 0.101
\end{equation}
\begin{equation}
J_3^{\pm} = 0.023
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/mixed_family_effective_model.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="2",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("J_2^{zz}S_i^zS_j^z", landed["expression"])
        self.assertIn(r"\frac{J_2^{\pm}}{2}", landed["expression"])
        self.assertNotIn(r"J_1^{\pm\pm}", landed["expression"])

    def test_family_indexed_effective_template_supports_prime_family_labels(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{n\in\{0',1',2a'\}}
\sum_{\langle i,j\rangle_n}
\left[
J_n^{zz}S_i^zS_j^z
+
\frac{J_n^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
\right].
\end{equation}
\section*{Parameters}
\begin{equation}
J_{0'}^{zz} = -0.036
\end{equation}
\begin{equation}
J_{0'}^{\pm} = 0.037
\end{equation}
\begin{equation}
J_{1'}^{zz} = 0.051
\end{equation}
\begin{equation}
J_{1'}^{\pm} = 0.013
\end{equation}
\begin{equation}
J_{2a'}^{zz} = 0.073
\end{equation}
\begin{equation}
J_{2a'}^{\pm} = 0.068
\end{equation}
\end{document}
"""

        record = build_intermediate_record(
            source_text=fixture,
            source_path="tests/data/prime_family_effective_model.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="2a'",
        )
        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertIn("J_{2a'}^{zz}S_i^zS_j^z", landed["expression"])
        self.assertIn(r"\frac{J_{2a'}^{\pm}}{2}", landed["expression"])
        self.assertNotIn(r"J_{0'}^{zz}", landed["expression"])

    def test_single_primary_candidate_lands_without_selected_model_candidate(self):
        record = {
            "source_document": {"source_kind": "natural_language"},
            "model_candidates": [
                {"name": "effective", "role": "main"},
                {"name": "matrix_form", "role": "equivalent_form"},
            ],
            "hamiltonian_model": {"operator_expression": "J * Sz@0 Sz@1"},
            "parameter_registry": {"J": -0.236},
            "ambiguities": [],
            "unsupported_features": [],
        }

        landed = land_intermediate_record(record)

        self.assertEqual(landed["representation"], "operator")
        self.assertEqual(landed["parameters"], {"J": -0.236})

    def test_land_intermediate_record_returns_agent_inferred_when_safe_fields_are_missing(self):
        record = build_intermediate_record(
            source_text="use structure.cif and wannier90_hr.dat for the effective Hamiltonian",
            source_path=None,
            selected_model_candidate=None,
        )

        landed = land_intermediate_record(record)

        self.assertEqual(landed["agent_inferred"]["status"], "proposed")
        self.assertEqual(landed["landing_readiness"], "agent_proposed_needs_input")

    def test_land_intermediate_record_uses_canonical_missing_hamiltonian_hr_interaction_id(self):
        record = build_intermediate_record(
            source_text="use structure file ./structure.cif for the effective Hamiltonian",
            source_path=None,
            selected_model_candidate="effective",
        )

        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(landed["interaction"]["id"], "hamiltonian_hr_file_selection")
        self.assertEqual(
            landed["agent_inferred"]["unresolved_items"][0]["field"],
            "hamiltonian_file",
        )

    def test_land_intermediate_record_preserves_needs_input_for_material_ambiguity(self):
        record = build_intermediate_record(
            source_text="family 1 effective Hamiltonian on Fe sites",
            source_path=None,
            selected_model_candidate="effective",
            selected_local_bond_family="1",
        )

        landed = land_intermediate_record(record)

        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertEqual(
            landed["agent_inferred"]["unresolved_items"][0]["field"],
            "coordinate_convention",
        )

    def test_land_intermediate_record_surfaces_unsupported_even_with_agent(self):
        record = build_intermediate_record(
            source_text="use the effective Hamiltonian with a three-spin chirality term K S_i·(S_j×S_k)",
            source_path=None,
            selected_model_candidate="effective",
        )

        landed = land_intermediate_record(record)

        self.assertEqual(landed["landing_readiness"], "unsupported_even_with_agent")
        self.assertEqual(landed["interaction"]["status"], "needs_input")
        self.assertTrue(landed["unsupported_features"])
        self.assertTrue(landed["agent_inferred"]["user_explanation"]["summary"])


if __name__ == "__main__":
    unittest.main()
