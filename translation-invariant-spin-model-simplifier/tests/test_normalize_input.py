import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from input.normalize_input import normalize_freeform_text, normalize_input


class NormalizeInputTests(unittest.TestCase):
    @staticmethod
    def _write_minimal_aims_geometry(path):
        from ase import Atoms
        from ase.io import write

        atoms = Atoms("Ru", positions=[[0.0, 0.0, 0.0]], cell=[[4, 0, 0], [0, 4, 0], [0, 0, 6]], pbc=True)
        write(str(path), atoms, format="aims")

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
        self.assertEqual(landed_payload["interaction"]["id"], "local_bond_family_selection")
        self.assertEqual(sorted(landed_payload["interaction"]["options"]), ["0'", "1", "1'", "2", "2a'", "3"])
        self.assertEqual(landed_payload["document_intermediate"]["parameter_registry"]["D"], 2.165)

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

        self.assertEqual(normalized["interaction"]["id"], "local_bond_family_selection")
        self.assertEqual(sorted(normalized["interaction"]["options"]), ["0'", "1", "1'", "2", "2a'", "3"])
        self.assertEqual(normalized["document_intermediate"]["parameter_registry"]["D"], 2.165)

    def test_normalize_input_document_text_extracts_mev_units_into_system_metadata(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H_{ij}=J_1^{zz}S_i^zS_j^z.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236~\text{meV}
\end{equation}
\end{document}
"""
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/units_mev.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["system"]["units"], "meV")

    def test_normalize_input_document_text_extracts_ev_units_into_system_metadata(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H_{ij}=J_1^{zz}S_i^zS_j^z.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.000236~\text{eV}
\end{equation}
\end{document}
"""
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/units_ev.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["system"]["units"], "eV")

    def test_normalize_input_document_text_marks_units_unspecified_when_absent(self):
        fixture = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H_{ij}=J_1^{zz}S_i^zS_j^z.
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\end{document}
"""
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/units_unspecified.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["system"]["units"], "unspecified")

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

    def test_normalize_input_document_style_requests_agent_normalization_for_prose_only_hamiltonian(self):
        fixture = r"""
\documentclass[11pt]{article}
\begin{document}
\section*{Effective Hamiltonian}
The effective Hamiltonian contains anisotropic spin interactions discussed in the main text.
\end{document}
"""
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/prose_only_effective.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "agent_document_normalization")
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")
        self.assertEqual(normalized["agent_normalization_request"]["target_schema"], "agent_normalized_document")
        self.assertEqual(normalized["agent_normalization_request"]["source_kind"], "tex_document")
        self.assertEqual(normalized["agent_normalization_request"]["selection_context"]["selected_model_candidate"], "effective")
        self.assertEqual(normalized["agent_normalization_request"]["template_version"], "v1")
        self.assertIn("candidate_models", normalized["agent_normalization_request"]["template"])
        self.assertIn("effective", normalized["agent_normalization_request"]["example_payload"]["candidate_models"])
        self.assertEqual(
            normalized["agent_normalization_request"]["example_payload"]["model_candidates"][0]["name"],
            "effective",
        )

    def test_normalize_input_document_style_selection_gate_does_not_force_agent_normalization(self):
        fixture = (SKILL_ROOT / "tests" / "data" / "fei2_document_input.tex").read_text(encoding="utf-8")
        payload = {
            "representation": "natural_language",
            "description": fixture,
            "source_path": "tests/data/fei2_document_input.tex",
            "selected_model_candidate": "effective",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["id"], "local_bond_family_selection")
        self.assertNotIn("agent_normalization_request", normalized)

    def test_many_body_hr_representation_is_accepted_with_required_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            structure_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "VR_hr.dat"
            self._write_minimal_poscar(structure_path)
            self._write_minimal_many_body_hr(hr_path)
            payload = {
                "representation": "many_body_hr",
                "structure_file": str(structure_path),
                "hamiltonian_file": str(hr_path),
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

    def test_normalize_freeform_text_auto_routes_poscar_and_vr_hr_paths_to_many_body_hr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            structure_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "VR_hr.dat"
            self._write_minimal_poscar(structure_path)
            self._write_minimal_many_body_hr(hr_path)
            text = (
                f"Please use POSCAR at {structure_path} "
                f"and VR_hr.dat at {hr_path}."
            )

            normalized = normalize_freeform_text(text)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["structure_file"],
            str(structure_path),
        )
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            str(hr_path),
        )
        self.assertEqual(normalized["basis_semantics"]["local_space"], "pseudospin_orbital")

    def test_normalize_input_natural_language_auto_routes_poscar_and_vr_hr_paths_to_many_body_hr(self):
        payload = {
            "representation": "natural_language",
            "description": (
                "Structure file is ./POSCAR and the many-body hopping file is "
                "./VR_hr.dat for this run."
            ),
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["structure_file"], "./POSCAR")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["hamiltonian_file"], "./VR_hr.dat")

    def test_normalize_freeform_text_routes_cif_and_wannier_hr_dat_to_many_body_hr(self):
        text = (
            "Use structure file ./structure.cif and hopping file ./wannier90_hr.dat "
            "for the many-body hr workflow."
        )

        normalized = normalize_freeform_text(text)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["structure_file"], "./structure.cif")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            "./wannier90_hr.dat",
        )

    def test_normalize_input_natural_language_routes_any_hr_named_file_when_structure_role_is_explicit(self):
        payload = {
            "representation": "natural_language",
            "description": (
                "structure file: ./FI2.dat ; hr file: ./exchange_hr_sparse.dat"
            ),
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["structure_file"], "./FI2.dat")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            "./exchange_hr_sparse.dat",
        )

    def test_normalize_freeform_text_routes_cell_and_h_r_dat_without_explicit_roles(self):
        text = "Use ./model.cell together with ./H_R.dat for this run."

        normalized = normalize_freeform_text(text)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["structure_file"], "./model.cell")
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["hamiltonian_file"], "./H_R.dat")

    def test_normalize_freeform_text_routes_geometry_in_and_h_r_dat_without_explicit_roles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            geometry_path = Path(tmpdir) / "geometry.in"
            self._write_minimal_aims_geometry(geometry_path)
            text = f"Use {geometry_path} together with ./H_R.dat for this run."

            normalized = normalize_freeform_text(text)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["structure_file"],
            str(geometry_path),
        )
        self.assertEqual(normalized["hamiltonian_description"]["representation"]["hamiltonian_file"], "./H_R.dat")

    def test_normalize_freeform_text_routes_directory_path_to_discovered_many_body_hr_pair(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = Path(tmpdir)
            structure_path = case_dir / "POSCAR"
            hr_path = case_dir / "VR_hr.dat"
            self._write_minimal_poscar(structure_path)
            self._write_minimal_many_body_hr(hr_path)

            normalized = normalize_freeform_text(f"Use {case_dir} as the many-body hr input directory.")

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "many_body_hr")
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["structure_file"],
            str(structure_path),
        )
        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["hamiltonian_file"],
            str(hr_path),
        )

    def test_normalize_input_natural_language_does_not_route_hr_file_without_structure_role(self):
        payload = {
            "representation": "natural_language",
            "description": "please use ./exchange_hr_sparse.dat for this model",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "natural_language")
        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "structure_file_selection")

    def test_normalize_input_natural_language_requests_hr_file_when_only_structure_file_is_given(self):
        payload = {
            "representation": "natural_language",
            "description": "please use structure file ./structure.cif for this model",
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "natural_language")
        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "hamiltonian_hr_file_selection")

    def test_normalize_freeform_text_prefers_document_path_over_helper_many_body_acceptance(self):
        text = r"""
Use structure.cif and wannier90_hr.dat for the effective Hamiltonian.
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section*{Effective Hamiltonian}
\begin{equation}
H=J_1^{zz}S_i^zS_j^z-D\sum_i (S_i^z)^2 .
\end{equation}
\section*{Parameters}
\begin{equation}
J_1^{zz} = -0.236
\end{equation}
\begin{equation}
D = 2.165
\end{equation}
\end{document}
"""

        normalized = normalize_freeform_text(
            text,
            source_path="tests/data/single_effective_document_with_paths.tex",
        )

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "operator")
        self.assertIn("J_1^{zz}S_i^zS_j^z", normalized["hamiltonian_description"]["representation"]["value"])
        self.assertEqual(normalized["parameters"]["D"], 2.165)
        self.assertIn("document_intermediate", normalized)

    def test_normalize_freeform_text_requests_canonical_hamiltonian_hr_file_selection_id(self):
        normalized = normalize_freeform_text(
            "please use structure file ./structure.cif for the effective Hamiltonian"
        )

        self.assertEqual(normalized["hamiltonian_description"]["representation"]["kind"], "natural_language")
        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "hamiltonian_hr_file_selection")

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

    def test_normalize_input_accepts_agent_normalized_document_that_lands_to_operator(self):
        payload = {
            "representation": "natural_language",
            "description": "Agent-normalized literature record",
            "agent_normalized_document": {
                "source_document": {"source_kind": "agent_normalized_document"},
                "model_candidates": [{"name": "effective", "role": "main"}],
                "hamiltonian_model": {
                    "local_bond_candidates": [
                        {"family": "1", "expression": "J1zz * Sz@0 Sz@1"}
                    ]
                },
                "parameter_registry": {"J1zz": -0.236},
                "system_context": {
                    "coordinate_convention": {
                        "status": "selected",
                        "frame": "global_cartesian",
                        "axis_labels": ["x", "y", "z"],
                    }
                },
                "unsupported_features": [],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertEqual(normalized["local_term"]["representation"]["value"], "J1zz * Sz@0 Sz@1")
        self.assertEqual(normalized["parameters"], {"J1zz": -0.236})
        self.assertEqual(normalized["coordinate_convention"]["frame"], "global_cartesian")
        self.assertEqual(
            normalized["document_intermediate"]["source_document"]["source_kind"],
            "agent_normalized_document",
        )

    def test_normalize_input_preserves_needs_input_from_agent_normalized_document(self):
        payload = {
            "representation": "natural_language",
            "description": "Agent-normalized anisotropic matrix record",
            "agent_normalized_document": {
                "source_document": {"source_kind": "agent_normalized_document"},
                "model_candidates": [{"name": "matrix_form", "role": "main"}],
                "hamiltonian_model": {
                    "matrix_form": True,
                    "local_bond_candidates": [
                        {
                            "family": "1",
                            "expression": (
                                "Jxx * Sx@0 Sx@1 + Jyy * Sy@0 Sy@1 + "
                                "Jyz * Sy@0 Sz@1 + Jyz * Sz@0 Sy@1 + Jzz * Sz@0 Sz@1"
                            ),
                            "matrix": [
                                ["Jxx", "0", "0"],
                                ["0", "Jyy", "Jyz"],
                                ["0", "Jyz", "Jzz"],
                            ],
                        }
                    ],
                },
                "parameter_registry": {
                    "Jxx": -0.200,
                    "Jyy": -0.180,
                    "Jyz": 0.040,
                    "Jzz": -0.236,
                },
                "unresolved_items": [
                    {
                        "field": "coordinate_convention",
                        "reason": (
                            "The agent recognized an anisotropic exchange matrix, "
                            "but the coordinate convention still needs user confirmation."
                        ),
                        "policy": "hard_gate",
                    }
                ],
                "unsupported_features": ["matrix_form_metadata"],
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["interaction"]["id"], "coordinate_convention_selection")
        self.assertEqual(normalized["unsupported_features"], ["matrix_form_metadata"])
        self.assertEqual(normalized["local_term"]["representation"]["kind"], "natural_language")

    def test_normalize_input_agent_normalized_candidate_models_support_effective_matrix_hybrid(self):
        payload = {
            "representation": "natural_language",
            "description": "Agent-normalized hybrid effective plus matrix-form record",
            "selected_model_candidate": "effective",
            "selected_local_bond_family": "1",
            "selected_coordinate_convention": "global_cartesian",
            "agent_normalized_document": {
                "model_candidates": [
                    {"name": "effective", "role": "main"},
                    {"name": "matrix_form", "role": "equivalent_form"},
                ],
                "candidate_models": {
                    "effective": {
                        "local_bond_candidates": [
                            {
                                "family": "1",
                                "expression": (
                                    "J_1^{zz}S_i^zS_j^z + "
                                    "\\frac{J_1^{\\pm\\pm}}{2}(\\gamma_{ij}S_i^+S_j^+ + "
                                    "\\gamma_{ij}^\\ast S_i^-S_j^-)"
                                ),
                            },
                            {"family": "2", "expression": "J_2^{zz} * Sz@0 Sz@1"},
                        ]
                    },
                    "matrix_form": {
                        "matrix_form": True,
                        "local_bond_candidates": [
                            {
                                "family": "1",
                                "expression": (
                                    "J_1^{xx} * Sx@0 Sx@1 + J_1^{yy} * Sy@0 Sy@1 + "
                                    "J_1^{yz} * Sy@0 Sz@1 + J_1^{yz} * Sz@0 Sy@1 + "
                                    "J_1^{zz} * Sz@0 Sz@1"
                                ),
                                "matrix": [
                                    ["J_1^{xx}", "0", "0"],
                                    ["0", "J_1^{yy}", "J_1^{yz}"],
                                    ["0", "J_1^{yz}", "J_1^{zz}"],
                                ],
                            }
                        ],
                    },
                },
                "parameter_registry": {
                    "J_1^{xx}": -0.397,
                    "J_1^{yy}": -0.075,
                    "J_1^{yz}": -0.261,
                    "J_1^{zz}": -0.236,
                },
            },
        }

        normalized = normalize_input(payload)

        self.assertEqual(normalized["local_term"]["representation"]["kind"], "operator")
        self.assertIn("J_1^{xx} * Sx@0 Sx@1", normalized["local_term"]["representation"]["value"])
        self.assertEqual(normalized["unsupported_features"], [])
        self.assertEqual(normalized["document_intermediate"]["selected_model_candidate"], "effective")

    def test_normalize_freeform_text_commits_only_accepted_agent_inferred_fields(self):
        normalized = normalize_freeform_text(
            "structure.cif + wannier90_hr.dat for the effective Hamiltonian"
        )

        self.assertEqual(
            normalized["hamiltonian_description"]["representation"]["kind"],
            "many_body_hr",
        )
        self.assertEqual(normalized["agent_inferred"]["status"], "accepted")

    def test_normalize_freeform_text_keeps_hard_gate_as_needs_input(self):
        normalized = normalize_freeform_text(
            "use the effective Hamiltonian family 1 terms",
            selected_model_candidate="effective",
            selected_local_bond_family="1",
        )

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["agent_inferred"]["status"], "proposed")

    def test_normalize_freeform_text_keeps_low_confidence_fallback_non_landing(self):
        normalized = normalize_freeform_text(
            "maybe some layered anisotropic model, not sure of the exact Hamiltonian"
        )

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertEqual(normalized["agent_inferred"]["status"], "rejected")
        self.assertEqual(normalized["landing_readiness"], "agent_proposed_needs_input")

    def test_normalize_freeform_text_surfaces_unsupported_even_with_agent(self):
        normalized = normalize_freeform_text(
            "use the effective Hamiltonian with a scalar spin chirality term K S_i·(S_j×S_k)",
            selected_model_candidate="effective",
        )

        self.assertEqual(normalized["interaction"]["status"], "needs_input")
        self.assertTrue(normalized["unsupported_features"])
        self.assertTrue(normalized["agent_inferred"]["user_explanation"]["summary"])


if __name__ == "__main__":
    unittest.main()
