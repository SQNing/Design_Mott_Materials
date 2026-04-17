import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.simplify_text_input import run_text_simplification_pipeline


class SimplifyTextInputPipelineTests(unittest.TestCase):
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

    GENERIC_FAMILY_TWO_WITH_MULTI_MATRIX_FIXTURE = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_2} H_{ij}^{(2)} .
\end{equation}
\begin{align}
H_{ij}^{(2)}=\;&
J_2^{zz}S_i^zS_j^z
+
\frac{J_2^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_2^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right)
\nonumber\\
&-
\frac{iJ_2^{z\pm}}{2}
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
\mathcal J_{ij}^{(2)}=
\begin{pmatrix}
J_2^{xx} & 0 & 0 \\
0 & J_2^{yy} & J_2^{yz} \\
0 & J_2^{yz} & J_2^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.410
\end{equation}
\begin{equation}
J_1^{yy} = -0.130
\end{equation}
\begin{equation}
J_1^{yz} = -0.080
\end{equation}
\begin{equation}
J_1^{zz} = -0.250
\end{equation}
\begin{equation}
J_2^{xx} = -0.310
\end{equation}
\begin{equation}
J_2^{yy} = -0.110
\end{equation}
\begin{equation}
J_2^{yz} = 0.050
\end{equation}
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

    GENERIC_FAMILY_TWO_WITH_WRONG_MATRIX_FAMILY_FIXTURE = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=
\sum_{\langle i,j\rangle_2} H_{ij}^{(2)} .
\end{equation}
\begin{align}
H_{ij}^{(2)}=\;&
J_2^{zz}S_i^zS_j^z
+
\frac{J_2^{\pm}}{2}(S_i^+S_j^-+S_i^-S_j^+)
+
\frac{J_2^{\pm\pm}}{2}
\left(
\gamma_{ij}S_i^+S_j^+
+
\gamma_{ij}^\ast S_i^-S_j^-
\right)
\nonumber\\
&-
\frac{iJ_2^{z\pm}}{2}
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
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.410
\end{equation}
\begin{equation}
J_1^{yy} = -0.130
\end{equation}
\begin{equation}
J_1^{yz} = -0.080
\end{equation}
\begin{equation}
J_1^{zz} = -0.250
\end{equation}
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

    @staticmethod
    def _write_minimal_cif(path):
        path.write_text(
            "\n".join(
                [
                    "data_test",
                    "_symmetry_space_group_name_H-M 'P 1'",
                    "_cell_length_a 4.0",
                    "_cell_length_b 4.0",
                    "_cell_length_c 6.0",
                    "_cell_angle_alpha 90",
                    "_cell_angle_beta 90",
                    "_cell_angle_gamma 120",
                    "loop_",
                    "_atom_site_label",
                    "_atom_site_type_symbol",
                    "_atom_site_fract_x",
                    "_atom_site_fract_y",
                    "_atom_site_fract_z",
                    "Ru1 Ru 0 0 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_xsf(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        write(str(path), atoms, format="xsf")

    @staticmethod
    def _write_minimal_cell(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"Generating CASTEP keywords JSON file.*", category=UserWarning)
            warnings.filterwarnings(
                "ignore",
                message=r"Could not determine the version of your CASTEP binary.*",
                category=UserWarning,
            )
            write(str(path), atoms, format="castep-cell")

    @staticmethod
    def _write_minimal_gen(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        write(str(path), atoms, format="gen")

    @staticmethod
    def _write_minimal_res(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        write(str(path), atoms, format="res")

    @staticmethod
    def _write_minimal_pdb(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]])
        write(str(path), atoms, format="proteindatabank")

    @staticmethod
    def _write_minimal_aims_geometry(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        write(str(path), atoms, format="aims")

    @staticmethod
    def _write_minimal_xyz(path):
        path.write_text(
            "\n".join(
                [
                    "1",
                    "",
                    "Ru 0.0 0.0 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "Ru",
                    "1.0",
                    "4.0 0.0 0.0",
                    "0.0 4.0 0.0",
                    "0.0 0.0 6.0",
                    "Ru",
                    "1",
                    "Direct",
                    "0.0 0.0 0.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_many_body_hr(path):
        lines = [
            "minimal hr fixture",
            "4",
            "1",
            "1",
        ]
        for left in range(1, 5):
            for right in range(1, 5):
                value = "1.0" if left == right else "0.0"
                lines.append(f"0 0 0 {left} {right} {value} 0.0")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.assertEqual(
            result["normalized_model"]["hamiltonian_description"]["representation"]["structure_file"],
            str(structure_path),
        )
        self.assertEqual(
            result["normalized_model"]["hamiltonian_description"]["representation"]["hamiltonian_file"],
            str(hr_path),
        )
        self.assertTrue(result["decomposition"]["terms"])

    def test_pipeline_surfaces_document_model_candidate_selection_from_unified_text_entry(self):
        fixture_path = SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex"
        fixture = fixture_path.read_text(encoding="utf-8")

        result = run_text_simplification_pipeline(fixture, source_path=str(fixture_path))

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(result["stage"], "normalize_input")

    def test_pipeline_returns_explicit_projection_gate_when_operator_expression_cannot_yet_be_decomposed(self):
        fixture_path = SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex"
        fixture = fixture_path.read_text(encoding="utf-8")

        result = run_text_simplification_pipeline(
            fixture,
            source_path=str(fixture_path),
            selected_model_candidate="effective",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["stage"], "decompose_local_term")
        self.assertEqual(result["interaction"]["id"], "projection_or_truncate")
        self.assertIn("project or truncate", result["interaction"]["question"].lower())
        self.assertIn("operator_expression_decomposition_pending", result["unsupported_features"])

    def test_pipeline_lands_fei2_family_one_document_path_after_family_selection(self):
        result = run_text_simplification_pipeline(
            self.FEI2_FAMILY_ONE_WITH_MATRIX_FIXTURE,
            source_path="tests/data/fei2_family_one.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="1",
            selected_coordinate_convention="global_crystallographic",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertTrue(result["canonical_model"]["two_body"])
        self.assertTrue(result["effective_model"]["main"])
        self.assertNotIn("interaction", result)
        matrix_blocks = [
            block
            for block in result["effective_model"]["main"]
            if block["type"] in {"symmetric_exchange_matrix", "exchange_tensor"}
        ]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["matrix"], [[-0.397, 0.0, 0.0], [0.0, -0.07499999999999998, -0.261], [0.0, -0.261, -0.236]])
        self.assertEqual(matrix_blocks[0]["matrix_axes"], ["a", "b", "c"])
        self.assertIn("human_summary", matrix_blocks[0])
        self.assertEqual(
            matrix_blocks[0]["physical_label"],
            "anisotropic spin exchange (Jzz/Jpm/Jpmpm/Jzpm)",
        )
        self.assertIn("Jzz", matrix_blocks[0]["human_summary"])
        self.assertIn("Jpm", matrix_blocks[0]["human_summary"])
        self.assertIn("Jpmpm", matrix_blocks[0]["human_summary"])
        self.assertIn("Jzpm", matrix_blocks[0]["human_summary"])
        self.assertIn("axes (x, y, z)", matrix_blocks[0]["human_summary"])
        parameter_names = [entry["name"] for entry in matrix_blocks[0]["human_parameters"]]
        self.assertEqual(parameter_names, ["Jzz", "Jpm", "Jpmpm", "Jzpm"])
        parameter_values = {entry["name"]: entry["value"] for entry in matrix_blocks[0]["human_parameters"]}
        self.assertAlmostEqual(parameter_values["Jzz"], -0.236)
        self.assertAlmostEqual(parameter_values["Jpm"], -0.236)
        self.assertAlmostEqual(parameter_values["Jpmpm"], -0.161)
        self.assertAlmostEqual(parameter_values["Jzpm"], -0.261)

    def test_pipeline_lands_fei2_family_one_operator_path_after_family_selection(self):
        result = run_text_simplification_pipeline(
            self.FEI2_FAMILY_ONE_FIXTURE,
            source_path="tests/data/fei2_family_one_operator_only.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="1",
            selected_coordinate_convention="global_crystallographic",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["decomposition"]["mode"], "operator-basis")
        self.assertEqual(result["decomposition"]["source_backbone"], "local_matrix_record")
        self.assertEqual(result["local_term_record"]["body_order"], 2)
        self.assertEqual(result["local_term_record"]["family"], "1")
        self.assertNotIn("interaction", result)
        by_label = {
            term["canonical_label"]: term["coefficient"]
            for term in result["canonical_model"]["two_body"]
        }
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.397)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.075)
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(by_label["Sy@0 Sz@1"], -0.261)
        self.assertAlmostEqual(by_label["Sz@0 Sy@1"], -0.261)

    def test_pipeline_completes_for_document_with_explicit_local_bond_operator_subset(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
        \section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes. The local z axis is along c.
\section*{Effective Hamiltonian}
\begin{align}
H_{ij}=\;&
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

        result = run_text_simplification_pipeline(fixture, source_path="tests/data/local_bond_subset.tex")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertTrue(result["canonical_model"]["two_body"])
        self.assertTrue(result["simplification"]["candidates"])
        xxz_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "xxz_exchange"]
        self.assertEqual(len(xxz_blocks), 1)
        self.assertEqual(xxz_blocks[0]["coordinate_frame"], "global_crystallographic")
        self.assertEqual(xxz_blocks[0]["axis_labels"], ["a", "b", "c"])
        self.assertEqual(xxz_blocks[0]["planar_axes"], ["a", "b"])
        self.assertEqual(xxz_blocks[0]["longitudinal_axis"], "c")
        self.assertIn("human_summary", xxz_blocks[0])
        self.assertIn("Jxy = -0.161 on (x, y)", xxz_blocks[0]["human_summary"])
        self.assertIn("Jz = -0.236 on z", xxz_blocks[0]["human_summary"])
        self.assertIn("planar", xxz_blocks[0]["human_summary"].lower())
        self.assertIn("longitudinal", xxz_blocks[0]["human_summary"].lower())
        self.assertIn("easy-axis-like", xxz_blocks[0]["human_summary"].lower())
        parameter_names = [entry["name"] for entry in xxz_blocks[0]["human_parameters"]]
        self.assertEqual(parameter_names, ["Jxy", "Jz"])

    def test_pipeline_preserves_single_q_rotating_frame_context_from_unified_text_entry(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Magnetic Order}
The ordered state is a single-Q spiral with propagation vector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$ in reciprocal lattice units. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/single_q_rotating_frame.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["normalized_model"]["magnetic_order"]["kind"], "single_q_spiral")
        self.assertEqual(result["normalized_model"]["magnetic_order"]["wavevector"], [0.25, 0.0, 0.25])
        self.assertEqual(result["normalized_model"]["magnetic_order"]["reference_frame"]["kind"], "rotating")
        self.assertEqual(result["normalized_model"]["rotating_frame"]["kind"], "single_q_rotating_frame")
        self.assertEqual(result["normalized_model"]["rotating_frame"]["rotation_axis"], "c")
        self.assertEqual(result["normalized_model"]["rotating_frame_transform"]["kind"], "site_phase_rotation")
        self.assertEqual(result["normalized_model"]["rotating_frame_transform"]["wavevector"], [0.25, 0.0, 0.25])
        self.assertEqual(result["normalized_model"]["rotating_frame_transform"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(result["effective_model"]["rotating_frame_transform"]["kind"], "site_phase_rotation")
        self.assertEqual(result["effective_model"]["rotating_frame_transform"]["phase_rule"], "Q_dot_r_plus_phi_s")

    def test_pipeline_requests_wavevector_units_for_single_q_rotating_frame_when_unspecified(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Magnetic Order}
The ordered state is a single-Q spiral with propagation vector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/single_q_rotating_frame_units_unspecified.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["stage"], "normalize_input")
        self.assertEqual(result["interaction"]["id"], "wavevector_units_selection")

    def test_pipeline_infers_reciprocal_lattice_units_for_single_q_from_hkl_context(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The reciprocal lattice basis vectors are denoted by $\mathbf b_1,\mathbf b_2,\mathbf b_3$.
\section*{Magnetic Order}
The ordered state is a single-Q spiral with ordering wavevector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$ in the $(h,k,l)$ basis. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/single_q_hkl_basis.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["normalized_model"]["magnetic_order"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(result["normalized_model"]["rotating_frame"]["kind"], "single_q_rotating_frame")

    def test_pipeline_completes_for_document_with_global_sum_and_explicit_local_bond_definition(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(fixture, source_path="tests/data/summed_effective_model.tex")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        by_label = {term["canonical_label"]: term["coefficient"] for term in result["canonical_model"]["two_body"]}
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.161)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.161)

    def test_pipeline_surfaces_family_selection_for_family_indexed_effective_template(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(fixture, source_path="tests/data/family_indexed_effective_model.tex")

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["stage"], "normalize_input")
        self.assertEqual(result["interaction"]["id"], "local_bond_family_selection")

    def test_pipeline_completes_for_selected_family_from_family_indexed_effective_template(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_local_bond_family="2",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        by_label = {term["canonical_label"]: term["coefficient"] for term in result["canonical_model"]["two_body"]}
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], 0.052)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], 0.017)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], 0.017)

    def test_pipeline_can_retain_all_local_bond_families_in_canonical_and_effective_models(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_local_bond_family="all",
        )

        self.assertEqual(result["status"], "ok")
        canonical_two_body = result["canonical_model"]["two_body"]
        self.assertEqual(len(canonical_two_body), 6)
        self.assertEqual({term.get("family") for term in canonical_two_body}, {"1", "2"})
        family_one = {term["canonical_label"]: term["coefficient"] for term in canonical_two_body if term.get("family") == "1"}
        family_two = {term["canonical_label"]: term["coefficient"] for term in canonical_two_body if term.get("family") == "2"}
        self.assertAlmostEqual(family_one["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(family_two["Sz@0 Sz@1"], 0.052)
        effective_families = {
            entry.get("family")
            for entry in result["effective_model"]["main"] + result["effective_model"]["residual"]
            if entry.get("family") is not None
        }
        self.assertEqual(effective_families, {"1", "2"})

    def test_pipeline_promotes_all_families_to_family_resolved_xxz_blocks(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_local_bond_family="all",
        )

        xxz_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "xxz_exchange"]
        self.assertEqual(len(xxz_blocks), 2)
        self.assertEqual({block.get("family") for block in xxz_blocks}, {"1", "2"})
        by_family = {block["family"]: block for block in xxz_blocks}
        self.assertAlmostEqual(by_family["1"]["coefficient_xy"], -0.161)
        self.assertAlmostEqual(by_family["1"]["coefficient_z"], -0.236)
        self.assertAlmostEqual(by_family["2"]["coefficient_xy"], 0.017)
        self.assertAlmostEqual(by_family["2"]["coefficient_z"], 0.052)
        self.assertFalse(result["effective_model"]["residual"])

    def test_pipeline_adds_shell_resolved_exchange_summary_for_all_families(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/family_indexed_effective_model.tex",
            selected_local_bond_family="all",
        )

        shell_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shell_block = shell_blocks[0]
        self.assertEqual([entry["family"] for entry in shell_block["shells"]], ["1", "2"])
        self.assertAlmostEqual(shell_block["shells"][0]["coefficient_xy"], -0.161)
        self.assertAlmostEqual(shell_block["shells"][0]["coefficient_z"], -0.236)
        self.assertAlmostEqual(shell_block["shells"][1]["coefficient_xy"], 0.017)
        self.assertAlmostEqual(shell_block["shells"][1]["coefficient_z"], 0.052)

    def test_pipeline_all_families_can_mix_matrix_fallback_and_xxz_shell_summary(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes. The local z axis is along c.
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
\begin{equation}
J_2^{zz} = 0.052
\end{equation}
\begin{equation}
J_2^{\pm} = 0.017
\end{equation}
\begin{equation}
J_3^{zz} = 0.211
\end{equation}
\begin{equation}
J_3^{\pm} = 0.166
\end{equation}
\end{document}
"""

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/mixed_family_fallback_and_xxz.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="all",
            selected_coordinate_convention="global_crystallographic",
        )

        self.assertEqual(result["status"], "ok")
        shell_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shells = shell_blocks[0]["shells"]
        by_family = {entry["family"]: entry for entry in shells}
        self.assertEqual(set(by_family), {"1", "2", "3"})
        self.assertEqual(
            by_family["1"]["physical_parameter_view"]["view_kind"],
            "anisotropic_spin_exchange_jzz_jpm_jpmpm_jzpm",
        )
        self.assertEqual(
            [entry["name"] for entry in by_family["1"]["physical_parameter_view"]["parameters"]],
            ["Jzz", "Jpm", "Jpmpm", "Jzpm"],
        )
        self.assertEqual(
            by_family["2"]["physical_parameter_view"]["view_kind"],
            "xxz_exchange_jxy_jz",
        )
        self.assertEqual(
            [entry["name"] for entry in by_family["2"]["physical_parameter_view"]["parameters"]],
            ["Jxy", "Jz"],
        )
        self.assertEqual(
            by_family["3"]["physical_parameter_view"]["view_kind"],
            "xxz_exchange_jxy_jz",
        )

    def test_pipeline_adds_isotropic_shell_summary_when_all_families_are_isotropic(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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
J_1^{zz} = -0.150
\end{equation}
\begin{equation}
J_1^{\pm} = -0.150
\end{equation}
\begin{equation}
J_2^{zz} = 0.030
\end{equation}
\begin{equation}
J_2^{\pm} = 0.030
\end{equation}
\end{document}
"""

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/isotropic_family_indexed_effective_model.tex",
            selected_local_bond_family="all",
        )

        isotropic_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "isotropic_exchange"]
        self.assertEqual(len(isotropic_blocks), 2)
        shell_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "shell_resolved_exchange"]
        self.assertEqual(len(shell_blocks), 1)
        shell_block = shell_blocks[0]
        self.assertEqual([entry["type"] for entry in shell_block["shells"]], ["isotropic_exchange", "isotropic_exchange"])
        self.assertAlmostEqual(shell_block["shells"][0]["coefficient"], -0.150)
        self.assertAlmostEqual(shell_block["shells"][1]["coefficient"], 0.030)

    def test_pipeline_surfaces_family_selection_for_mixed_explicit_and_family_indexed_effective_model(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/mixed_family_effective_model.tex",
            selected_model_candidate="effective",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["stage"], "normalize_input")
        self.assertEqual(result["interaction"]["id"], "local_bond_family_selection")
        self.assertEqual(sorted(result["interaction"]["options"]), ["1", "2", "3"])

    def test_pipeline_completes_for_selected_nonnearest_family_from_mixed_effective_model(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/mixed_family_effective_model.tex",
            selected_model_candidate="effective",
            selected_local_bond_family="2",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        by_label = {term["canonical_label"]: term["coefficient"] for term in result["canonical_model"]["two_body"]}
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], 0.052)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], 0.017)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], 0.017)

    def test_pipeline_completes_for_selected_prime_family_from_effective_template(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/prime_family_effective_model.tex",
            selected_local_bond_family="2a'",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        by_label = {term["canonical_label"]: term["coefficient"] for term in result["canonical_model"]["two_body"]}
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], 0.073)
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], 0.068)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], 0.068)

    def test_pipeline_completes_for_selected_exchange_matrix_form(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_input.tex",
            selected_model_candidate="matrix_form",
            selected_coordinate_convention="global_crystallographic",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["decomposition"]["source_backbone"], "local_matrix_record")
        self.assertEqual(result["local_term_record"]["body_order"], 2)
        by_label = {term["canonical_label"]: term["coefficient"] for term in result["canonical_model"]["two_body"]}
        self.assertAlmostEqual(by_label["Sx@0 Sx@1"], -0.200)
        self.assertAlmostEqual(by_label["Sy@0 Sy@1"], -0.180)
        self.assertAlmostEqual(by_label["Sz@0 Sz@1"], -0.236)
        self.assertAlmostEqual(by_label["Sy@0 Sz@1"], 0.040)
        self.assertAlmostEqual(by_label["Sz@0 Sy@1"], 0.040)
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["matrix"][1][2], 0.040)
        self.assertEqual(matrix_blocks[0]["coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["matrix_axes"], ["a", "b", "c"])

    def test_pipeline_requests_coordinate_convention_for_anisotropic_matrix_form_when_unspecified(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_input.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["stage"], "normalize_input")
        self.assertEqual(result["interaction"]["id"], "coordinate_convention_selection")

    def test_pipeline_completes_for_selected_general_exchange_tensor_form(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Crystal Structure}
The magnetic ions form triangular layers.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & J_1^{xy} & J_1^{xz} \\
J_1^{yx} & J_1^{yy} & J_1^{yz} \\
J_1^{zx} & J_1^{zy} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{xx} = -0.200
\end{equation}
\begin{equation}
J_1^{xy} = 0.010
\end{equation}
\begin{equation}
J_1^{xz} = -0.030
\end{equation}
\begin{equation}
J_1^{yx} = -0.020
\end{equation}
\begin{equation}
J_1^{yy} = -0.180
\end{equation}
\begin{equation}
J_1^{yz} = 0.040
\end{equation}
\begin{equation}
J_1^{zx} = 0.050
\end{equation}
\begin{equation}
J_1^{zy} = 0.060
\end{equation}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/general_exchange_tensor_input.tex",
            selected_model_candidate="matrix_form",
            selected_coordinate_convention="global_crystallographic",
        )

        self.assertEqual(result["status"], "ok")
        tensor_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "exchange_tensor"]
        self.assertEqual(len(tensor_blocks), 1)
        matrix = tensor_blocks[0]["matrix"]
        self.assertAlmostEqual(matrix[0][1], 0.010)
        self.assertAlmostEqual(matrix[1][0], -0.020)
        self.assertAlmostEqual(matrix[2][0], 0.050)
        self.assertAlmostEqual(matrix[2][1], 0.060)
        self.assertEqual(tensor_blocks[0]["coordinate_frame"], "global_crystallographic")
        self.assertEqual(tensor_blocks[0]["matrix_axes"], ["a", "b", "c"])

    def test_pipeline_preserves_explicit_coordinate_convention_metadata(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes. The local z axis is along c.
\section*{Crystal Structure}
The magnetic ions form triangular layers.
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_with_axes.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["normalized_model"]["coordinate_convention"]["frame"], "global_crystallographic")
        self.assertEqual(result["normalized_model"]["coordinate_convention"]["axis_labels"], ["a", "b", "c"])
        self.assertEqual(result["effective_model"]["coordinate_convention"]["quantization_axis"], "c")

    def test_pipeline_resolves_local_axis_mapping_for_matrix_form_blocks(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_local_axes.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["coordinate_frame"], "local_bond")
        self.assertEqual(matrix_blocks[0]["matrix_axes"], ["x", "y", "z"])
        self.assertEqual(matrix_blocks[0]["resolved_coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])

    def test_pipeline_rotates_exchange_matrix_into_resolved_axes_when_rotation_matrix_is_given(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_rotation_axes.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["resolved_coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_pipeline_rotates_exchange_matrix_into_resolved_axes_when_direction_cosine_table_is_given(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_direction_cosine_table.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["resolved_coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_pipeline_rotates_exchange_matrix_into_resolved_axes_when_textual_direction_cosines_are_given(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_direction_cosine_text.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        self.assertEqual(matrix_blocks[0]["resolved_coordinate_frame"], "global_crystallographic")
        self.assertEqual(matrix_blocks[0]["resolved_matrix_axes"], ["a", "b", "c"])
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_pipeline_rotates_exchange_matrix_into_resolved_axes_when_direction_cosine_table_is_transposed(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_direction_cosine_table_transposed.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_pipeline_rotates_exchange_matrix_into_resolved_axes_when_hat_axis_vectors_are_given(self):
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

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_hat_axis_vectors.tex",
            selected_model_candidate="matrix_form",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = [block for block in result["effective_model"]["main"] if block["type"] == "symmetric_exchange_matrix"]
        self.assertEqual(len(matrix_blocks), 1)
        resolved = matrix_blocks[0]["resolved_matrix"]
        self.assertEqual(resolved[0][0], -0.180)
        self.assertEqual(resolved[1][1], -0.200)
        self.assertEqual(resolved[0][2], 0.040)
        self.assertEqual(resolved[2][0], 0.040)

    def test_pipeline_applies_family_resolved_local_frames_for_all_matrix_families(self):
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
\begin{equation}
J_2^{xx} = 0.120
\end{equation}
\begin{equation}
J_2^{yy} = 0.050
\end{equation}
\begin{equation}
J_2^{yz} = -0.020
\end{equation}
\begin{equation}
J_2^{zz} = 0.090
\end{equation}
\end{document}
"""

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_family_local_frames.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="all",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = {
            block["family"]: block
            for block in result["effective_model"]["main"]
            if block["type"] == "symmetric_exchange_matrix"
        }
        self.assertEqual(set(matrix_blocks), {"1", "2"})
        self.assertEqual(matrix_blocks["1"]["resolved_matrix"][0][0], -0.200)
        self.assertEqual(matrix_blocks["1"]["resolved_matrix"][1][1], -0.180)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][0][0], 0.050)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][1][1], 0.120)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][0][2], -0.020)
        self.assertEqual(matrix_blocks["2"]["resolved_matrix"][2][0], -0.020)

    def test_pipeline_applies_bond_resolved_local_frames_for_all_matrix_families(self):
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
\section*{Parameters}
\begin{equation}
J_x^{xx} = -0.200
\end{equation}
\begin{equation}
J_x^{yy} = -0.180
\end{equation}
\begin{equation}
J_x^{yz} = 0.040
\end{equation}
\begin{equation}
J_x^{zz} = -0.236
\end{equation}
\begin{equation}
J_y^{xx} = 0.120
\end{equation}
\begin{equation}
J_y^{yy} = 0.050
\end{equation}
\begin{equation}
J_y^{yz} = -0.020
\end{equation}
\begin{equation}
J_y^{zz} = 0.090
\end{equation}
\end{document}
"""

        result = run_text_simplification_pipeline(
            fixture,
            source_path="tests/data/matrix_form_bond_local_frames.tex",
            selected_model_candidate="matrix_form",
            selected_local_bond_family="all",
        )

        self.assertEqual(result["status"], "ok")
        matrix_blocks = {
            block["family"]: block
            for block in result["effective_model"]["main"]
            if block["type"] == "symmetric_exchange_matrix"
        }
        self.assertEqual(set(matrix_blocks), {"x", "y"})
        self.assertEqual(matrix_blocks["x"]["resolved_matrix"][0][0], -0.200)
        self.assertEqual(matrix_blocks["x"]["resolved_matrix"][1][1], -0.180)
        self.assertEqual(matrix_blocks["y"]["resolved_matrix"][0][0], 0.050)
        self.assertEqual(matrix_blocks["y"]["resolved_matrix"][1][1], 0.120)

    def test_run_text_simplification_pipeline_surfaces_user_explanation_for_blocked_agent_inference(self):
        result = run_text_simplification_pipeline(
            "use the effective Hamiltonian family 1 terms",
            selected_model_candidate="effective",
            selected_local_bond_family="1",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertIn("recognized", result["agent_inferred"]["user_explanation"])
        self.assertIn(
            "coordinate convention",
            result["agent_inferred"]["user_explanation"]["summary"].lower(),
        )

    def test_run_text_simplification_pipeline_surfaces_unsupported_even_with_agent(self):
        result = run_text_simplification_pipeline(
            "use the effective Hamiltonian with a scalar spin chirality term K S_i·(S_j×S_k)",
            selected_model_candidate="effective",
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertTrue(result["unsupported_features"])
        self.assertTrue(result["agent_inferred"]["user_explanation"]["summary"])

    def test_run_text_simplification_pipeline_uses_public_agent_inferred_view_on_ok(self):
        normalized_model = {
            "interaction": None,
            "landing_readiness": "agent_proposed_ok",
            "agent_inferred": {
                "confidence": {"level": "high", "reason": "recognized pair"},
                "recognized_items": ["structure file: structure.cif"],
                "assumptions": ["treated the cited files as the intended pair"],
                "unresolved_items": [],
                "user_explanation": {
                    "recognized": ["structure file: structure.cif"],
                    "summary": "The helper recognized the intended file pair.",
                },
                "inferred_fields": {"structure_file": "structure.cif"},
                "field_policy_boundary": {"agent_inferred_fields": ["structure_file"]},
            },
            "lattice_description": {"kind": "unspecified", "value": ""},
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "coordinate_convention": {},
            "rotating_frame_transform": {},
            "unsupported_features": [],
        }
        with patch("cli.simplify_text_input.normalize_freeform_text", return_value=normalized_model):
            with patch("cli.simplify_text_input.parse_lattice_description", return_value={"kind": "unspecified"}):
                with patch("cli.simplify_text_input.decompose_local_term", return_value={"mode": "supported", "terms": []}):
                    with patch("cli.simplify_text_input.infer_symmetries", return_value={"status": "ok"}):
                        with patch("cli.simplify_text_input.canonicalize_terms", return_value={"terms": []}):
                            with patch("cli.simplify_text_input.identify_readable_blocks", return_value={"main": []}):
                                with patch("cli.simplify_text_input.assemble_effective_model", return_value={"main": []}):
                                    with patch("cli.simplify_text_input.score_fidelity", return_value={"score": 1.0}):
                                        with patch("cli.simplify_text_input.generate_candidates", return_value={"candidates": []}):
                                            result = run_text_simplification_pipeline("placeholder")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            set(result["agent_inferred"]),
            {
                "confidence",
                "recognized_items",
                "assumptions",
                "unresolved_items",
                "user_explanation",
            },
        )
        self.assertEqual(
            result["agent_inferred"]["assumptions"],
            ["treated the cited files as the intended pair"],
        )
        self.assertNotIn("field_policy_boundary", result["agent_inferred"])

    def test_run_text_simplification_pipeline_omits_agent_inferred_when_fallback_not_material(self):
        normalized_model = {
            "interaction": None,
            "agent_inferred": {
                "confidence": {"level": "medium", "reason": "recognized a keyword"},
                "recognized_items": ["model keyword: effective"],
                "assumptions": ["keyword match only"],
                "unresolved_items": [],
                "user_explanation": {
                    "recognized": ["model keyword: effective"],
                    "summary": "The helper recognized a keyword.",
                },
                "inferred_fields": {},
                "unsupported_even_with_agent": [],
            },
            "lattice_description": {"kind": "unspecified", "value": ""},
            "user_required_symmetries": [],
            "allowed_breaking": [],
            "coordinate_convention": {},
            "rotating_frame_transform": {},
            "unsupported_features": [],
        }
        with patch("cli.simplify_text_input.normalize_freeform_text", return_value=normalized_model):
            with patch("cli.simplify_text_input.parse_lattice_description", return_value={"kind": "unspecified"}):
                with patch("cli.simplify_text_input.decompose_local_term", return_value={"mode": "supported", "terms": []}):
                    with patch("cli.simplify_text_input.infer_symmetries", return_value={"status": "ok"}):
                        with patch("cli.simplify_text_input.canonicalize_terms", return_value={"terms": []}):
                            with patch("cli.simplify_text_input.identify_readable_blocks", return_value={"main": []}):
                                with patch("cli.simplify_text_input.assemble_effective_model", return_value={"main": []}):
                                    with patch("cli.simplify_text_input.score_fidelity", return_value={"score": 1.0}):
                                        with patch("cli.simplify_text_input.generate_candidates", return_value={"candidates": []}):
                                            result = run_text_simplification_pipeline("placeholder")

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("agent_inferred", result)


if __name__ == "__main__":
    unittest.main()
