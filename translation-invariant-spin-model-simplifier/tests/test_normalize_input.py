import json
import subprocess
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.normalize_input import normalize_freeform_text, normalize_input


class NormalizeInputTests(unittest.TestCase):
    def test_normalize_input_cli_freeform_tex_supports_candidate_selection_contract(self):
        fixture_path = SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex"
        script_path = SKILL_ROOT / "scripts" / "input" / "normalize_input.py"
        fixture = fixture_path.read_text(encoding="utf-8")

        needs_input = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--freeform",
                fixture,
                "--source-path",
                str(fixture_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        needs_input_payload = json.loads(needs_input.stdout)

        landed = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--freeform",
                fixture,
                "--source-path",
                str(fixture_path),
                "--selected-model-candidate",
                "effective",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        landed_payload = json.loads(landed.stdout)

        self.assertEqual(needs_input_payload["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(landed_payload["local_term"]["representation"]["kind"], "operator")
        self.assertEqual(landed_payload["parameters"]["D"], 2.165)

    def test_normalize_freeform_text_detects_tex_document_and_returns_needs_input(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")

        normalized = normalize_freeform_text(
            fixture,
            source_path="tests/data/fei2_document_input.tex",
        )

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")

    def test_normalize_input_natural_language_text_can_land_selected_tex_model_without_manual_document_intermediate(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/fei2_document_input.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertIn("J_n^{zz}S_i^zS_j^z", normalized["local_term"]["representation"]["value"])
        self.assertEqual(normalized["parameters"]["D"], 2.165)

    def test_normalize_input_preserves_explicit_coordinate_convention_from_document_text(self):
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/matrix_form_with_axes.tex",
            "selected_model_candidate": "matrix_form",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["coordinate_convention"]["status"], "explicit")
        self.assertEqual(normalized["coordinate_convention"]["frame"], "global_crystallographic")
        self.assertEqual(normalized["coordinate_convention"]["axis_labels"], ["a", "b", "c"])
        self.assertEqual(normalized["coordinate_convention"]["quantization_axis"], "c")

    def test_normalize_input_preserves_single_q_rotating_frame_context_from_document_text(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Magnetic Order}
The ordered state is a single-Q spiral with propagation vector $\mathbf Q=(\frac{1}{4},0,\frac{1}{4})$ in reciprocal lattice units. A rotating reference frame is used so that the spin direction advances with phase $\mathbf Q\cdot\mathbf r_n$.
\section*{Equivalent Exchange-Matrix Form}
\begin{equation}
\mathcal J_{ij}^{(1)}=
\begin{pmatrix}
J_1^{xx} & 0 & 0 \\
0 & J_1^{yy} & J_1^{yz} \\
0 & J_1^{yz} & J_1^{zz}
\end{pmatrix}.
\end{equation}
\section*{Coordinate Convention}
Spin components are expressed in the global crystallographic a,b,c axes.
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/single_q_rotating_frame.tex",
            "selected_model_candidate": "matrix_form",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["magnetic_order"]["kind"], "single_q_spiral")
        self.assertEqual(normalized["magnetic_order"]["wavevector"], [0.25, 0.0, 0.25])
        self.assertEqual(normalized["magnetic_order"]["reference_frame"]["kind"], "rotating")
        self.assertEqual(normalized["rotating_frame"]["kind"], "single_q_rotating_frame")
        self.assertEqual(normalized["rotating_frame"]["wavevector"], [0.25, 0.0, 0.25])
        self.assertEqual(normalized["rotating_frame"]["phase_rule"], "Q_dot_r_plus_phi_s")
        self.assertEqual(normalized["rotating_frame"]["rotation_axis"], "c")
        self.assertEqual(normalized["rotating_frame_transform"]["kind"], "site_phase_rotation")
        self.assertEqual(normalized["rotating_frame_transform"]["phase_rule"], "Q_dot_r_plus_phi_s")
        self.assertEqual(normalized["rotating_frame_transform"]["rotation_axis"], "c")
        self.assertEqual(normalized["rotating_frame_transform"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(normalized["rotating_frame_transform"]["sublattice_phase_offsets"], {})
        self.assertEqual(normalized["rotating_frame_realization"]["kind"], "single_q_site_phase_rotation")
        self.assertEqual(normalized["rotating_frame_realization"]["source_transform_kind"], "site_phase_rotation")
        self.assertEqual(
            normalized["rotating_frame_realization"]["phase_coordinate_semantics"],
            "fractional_direct_positions_with_two_pi_factor",
        )
        self.assertEqual(normalized["rotating_frame_realization"]["wavevector_units"], "reciprocal_lattice_units")

    def test_normalize_input_preserves_explicit_composite_rotating_frame_realization(self):
        payload = {
            "representation": "operator",
            "support": [0, 1],
            "expression": "J * Sz_i * Sz_j",
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "positions": [[0.0, 0.0, 0.0]],
            },
            "supercell_shape": [2, 1, 1],
            "rotating_frame_realization": {
                "status": "explicit",
                "kind": "composite_site_phase_rotation",
                "composition_rule": "sum_site_phases",
                "components": [
                    {
                        "wavevector": [0.25, 0.0, 0.0],
                        "wavevector_units": "reciprocal_lattice_units",
                        "phase_rule": "Q_dot_r_plus_phi_s",
                        "rotation_axis": "z",
                        "site_phase_offsets": {},
                        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                    },
                    {
                        "wavevector": [0.125, 0.0, 0.0],
                        "wavevector_units": "reciprocal_lattice_units",
                        "phase_rule": "Q_dot_r_plus_phi_s",
                        "rotation_axis": "z",
                        "site_phase_offsets": {},
                        "phase_coordinate_semantics": "fractional_direct_positions_with_two_pi_factor",
                    },
                ],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["rotating_frame_realization"]["kind"], "composite_site_phase_rotation")
        self.assertEqual(normalized["rotating_frame_realization"]["component_count"], 2)
        self.assertEqual(normalized["rotating_frame_realization"]["composition_rule"], "sum_site_phases")
        self.assertAlmostEqual(normalized["rotating_frame_realization"]["supercell_site_phases"][1]["phase"], 0.75 * 3.141592653589793)

    def test_normalize_input_requests_wavevector_units_for_single_q_rotating_frame_when_unspecified(self):
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/single_q_rotating_frame_units_unspecified.tex",
            "selected_model_candidate": "matrix_form",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["id"], "wavevector_units_selection")

    def test_normalize_input_infers_reciprocal_lattice_units_for_single_q_from_hkl_context(self):
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/single_q_hkl_basis.tex",
            "selected_model_candidate": "matrix_form",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"], None)
        self.assertEqual(normalized["magnetic_order"]["wavevector_units"], "reciprocal_lattice_units")
        self.assertEqual(normalized["rotating_frame"]["kind"], "single_q_rotating_frame")

    def test_normalize_input_requests_coordinate_convention_for_anisotropic_matrix_form_when_unspecified(self):
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/matrix_form_input.tex",
            "selected_model_candidate": "matrix_form",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["id"], "coordinate_convention_selection")

    def test_normalize_input_accepts_selected_coordinate_convention_for_anisotropic_matrix_form(self):
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
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/matrix_form_input.tex",
            "selected_model_candidate": "matrix_form",
            "selected_coordinate_convention": "global_crystallographic",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["coordinate_convention"]["status"], "selected")
        self.assertEqual(normalized["coordinate_convention"]["frame"], "global_crystallographic")

    def test_normalize_input_document_style_needs_input_respects_explicit_local_dim(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/fei2_document_input.tex",
            "local_dim": 6,
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(normalized["local_hilbert"]["dimension"], 6)

    def test_many_body_hr_representation_is_accepted_with_required_paths(self):
        payload = {
            "representation": "many_body_hr",
            "structure_file": "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR",
            "hamiltonian_file": "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["structure_file"],
            payload["structure_file"],
        )
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            payload["hamiltonian_file"],
        )
        self.assertEqual(normalized["basis_semantics"]["local_space"], "pseudospin_orbital")
        self.assertEqual(normalized["basis_order"], "orbital_major_spin_minor")

    def test_many_body_hr_requires_structure_and_hamiltonian_paths(self):
        with self.assertRaises(ValueError):
            normalize_input({"representation": "many_body_hr", "structure_file": "POSCAR"})

        with self.assertRaises(ValueError):
            normalize_input({"representation": "many_body_hr", "hamiltonian_file": "VR_hr.dat"})

    def test_existing_operator_input_path_still_works(self):
        payload = {
            "representation": "operator",
            "support": [0, 1],
            "expression": "J * Sx@0 Sx@1",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["hamiltonian_description"]["support"], [0, 1])

    def test_normalize_input_accepts_document_intermediate_that_lands_to_operator(self):
        payload = {
            "representation": "natural_language",
            "description": "Effective Hamiltonian text",
            "document_intermediate": {
                "source_document": {"source_kind": "tex_document"},
                "model_candidates": [{"name": "effective", "role": "main"}],
                "hamiltonian_model": {"operator_expression": "J * Sz@0 Sz@1"},
                "parameter_registry": {"J": -0.236},
                "ambiguities": [],
                "unsupported_features": ["matrix_form_metadata"],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["local_term"]["representation"]["value"], "J * Sz@0 Sz@1")
        self.assertEqual(normalized["local_term"]["support"], [0, 1])
        self.assertEqual(normalized["parameters"], {"J": -0.236})

    def test_normalize_input_preserves_needs_input_from_document_intermediate(self):
        payload = {
            "representation": "natural_language",
            "description": "Toy plus effective Hamiltonian",
            "document_intermediate": {
                "source_document": {"source_kind": "tex_document"},
                "model_candidates": [
                    {"name": "toy", "role": "simplified"},
                    {"name": "effective", "role": "main"},
                ],
                "ambiguities": [
                    {
                        "id": "model_candidate_selection",
                        "blocks_landing": True,
                        "question": "Multiple Hamiltonian candidates were detected. Which one should I use?",
                    }
                ],
                "unsupported_features": ["matrix_form_metadata"],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "model_candidate_selection")
        self.assertEqual(normalized["unsupported_features"], ["matrix_form_metadata"])
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")


if __name__ == "__main__":
    unittest.main()
