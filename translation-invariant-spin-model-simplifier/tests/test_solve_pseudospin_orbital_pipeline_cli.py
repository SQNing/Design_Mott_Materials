import io
import json
import itertools
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.solve_pseudospin_orbital_pipeline import _structural_supercell_schedule, solve_from_files


def _shape_cells(shape):
    return list(itertools.product(*(range(int(value)) for value in shape)))


def _shape_local_rays(shape, local_dimension=4):
    rays = []
    for cell in _shape_cells(shape):
        basis_index = int(sum(cell)) % max(1, int(local_dimension))
        vector = []
        for index in range(int(local_dimension)):
            vector.append({"real": 1.0 if index == basis_index else 0.0, "imag": 0.0})
        rays.append({"cell": [int(value) for value in cell], "vector": vector})
    return rays


def _mocked_sunny_classical_result(supercell_shape=(1, 1, 1), energy=-0.5):
    return {
        "status": "ok",
        "method": "sunny-cpn-minimize",
        "energy": float(energy),
        "supercell_shape": [int(value) for value in supercell_shape],
        "local_rays": _shape_local_rays(supercell_shape),
        "starts": 2,
        "seed": 3,
        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
    }


def _mocked_sunny_classical_result_nested_only(supercell_shape=(1, 1, 1), energy=-0.5):
    rays = _shape_local_rays(supercell_shape)
    return {
        "status": "ok",
        "method": "sunny-cpn-minimize",
        "energy": float(energy),
        "starts": 2,
        "seed": 3,
        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
        "classical_state": {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [int(value) for value in supercell_shape],
            "local_rays": rays,
            "ordering": {
                "kind": "commensurate-supercell",
                "supercell_shape": [int(value) for value in supercell_shape],
            },
        },
    }


def _mocked_sunny_classical_backend_for_payload(payload, *, converged_after_linear_size=2, nested=False):
    shape = tuple(int(value) for value in payload["supercell_shape"])
    linear_size = max(shape)
    energy = -0.5 if linear_size >= int(converged_after_linear_size) else -0.5
    if nested:
        return _mocked_sunny_classical_result_nested_only(supercell_shape=shape, energy=energy)
    return _mocked_sunny_classical_result(supercell_shape=shape, energy=energy)


def _mocked_sunny_diagnostics(
    shape,
    *,
    ordering_kind="uniform",
    dominant_ordering_q=None,
    max_residual_norm=1.0e-9,
):
    shape = [int(value) for value in shape]
    uniform = str(ordering_kind) == "uniform"
    return {
        "projector_diagnostics": {
            "ordering_kind": str(ordering_kind),
            "dominant_ordering_q": None if uniform else list(dominant_ordering_q or [0.0, 0.0, 0.0]),
            "dominant_ordering_weight": 0.0 if uniform else 1.0,
            "uniform_q_weight": 1.0 if uniform else 0.0,
            "grid_shape": list(shape),
            "components": [],
        },
        "stationarity": {
            "residual_definition": "test residual",
            "max_residual_norm": float(max_residual_norm),
            "mean_residual_norm": float(max_residual_norm),
            "sites": [],
        },
    }


def _with_backend_stationarity(result, *, max_residual_norm):
    payload = dict(result)
    payload["backend_stationarity"] = {
        "residual_definition": "backend gradient tangent residual",
        "max_residual_norm": float(max_residual_norm),
        "mean_residual_norm": float(max_residual_norm),
    }
    return payload


def _mocked_sunny_thermodynamics_result(method, *, include_dos=False):
    payload = {
        "status": "ok",
        "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": method},
        "thermodynamics_result": {
            "method": method,
            "backend": {"name": "Sunny.jl", "mode": "SUN", "sampler": method},
            "grid": [
                {
                    "temperature": 0.2,
                    "energy": -0.1,
                    "magnetization": 0.3,
                    "specific_heat": 0.4,
                    "susceptibility": 0.5,
                }
            ],
            "observables": {
                "energy": [-0.1],
                "magnetization": [0.3],
                "specific_heat": [0.4],
                "susceptibility": [0.5],
            },
            "uncertainties": {
                "energy": [0.01],
                "magnetization": [0.02],
                "specific_heat": [0.03],
                "susceptibility": [0.04],
            },
            "sampling": {"seed": 5},
            "reference": {"normalization": "per_spin"},
        },
    }
    if include_dos:
        payload["dos_result"] = {
            "energy_bins": [-1.0, -0.9],
            "log_density_of_states": [0.0, 0.1],
        }
    return payload


def _mocked_sunny_thermodynamics_result_flat(method, *, include_dos=False):
    nested = _mocked_sunny_thermodynamics_result(method, include_dos=include_dos)
    payload = {
        "status": "ok",
        "backend": dict(nested["backend"]),
        "payload_kind": "sunny_sun_thermodynamics",
        **dict(nested["thermodynamics_result"]),
    }
    if include_dos:
        payload["dos_result"] = dict(nested["dos_result"])
    return payload


def _mocked_gswt_result():
    return {
        "status": "ok",
        "backend": {"name": "Sunny.jl", "mode": "SUN"},
        "payload_kind": "sun_gswt_prototype",
        "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0]}],
    }


def _mocked_python_gswt_result():
    return {
        "status": "ok",
        "backend": {"name": "python-glswt", "implementation": "local-frame-quadratic-expansion"},
        "payload_kind": "python_glswt_local_rays",
        "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0]}],
    }


def _mocked_python_single_q_gswt_result():
    return {
        "status": "ok",
        "backend": {"name": "python-glswt", "implementation": "single-q-z-harmonic-sideband"},
        "payload_kind": "python_glswt_single_q_z_harmonic",
        "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0]}],
    }


def _mocked_single_q_convergence_result():
    return {
        "status": "ok",
        "analysis_kind": "single_q_z_harmonic_convergence",
        "reference_parameters": {
            "phase_grid_size": 32,
            "z_harmonic_cutoff": 1,
            "sideband_cutoff": 2,
            "z_harmonic_reference_mode": "input",
        },
        "reference_metrics": {
            "omega_min": 0.05,
            "omega_min_q_vector": [0.13, 0.0, 0.0],
            "retained_linear_term_max_norm": 1.0e-7,
            "discarded_linear_term_max_norm": 2.0e-5,
            "full_tangent_linear_term_max_norm": 1.0e-4,
        },
        "phase_grid_scan": [
            {
                "phase_grid_size": 16,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 2,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.07,
                "omega_min_delta_vs_reference": 0.02,
                "max_band_delta_vs_reference": 0.03,
                "retained_linear_term_max_norm": 3.0e-7,
                "discarded_linear_term_max_norm": 4.0e-5,
                "full_tangent_linear_term_max_norm": 2.0e-4,
            },
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 2,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.05,
                "omega_min_delta_vs_reference": 0.0,
                "max_band_delta_vs_reference": 0.0,
                "retained_linear_term_max_norm": 1.0e-7,
                "discarded_linear_term_max_norm": 2.0e-5,
                "full_tangent_linear_term_max_norm": 1.0e-4,
            },
        ],
        "z_harmonic_cutoff_scan": [
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 0,
                "sideband_cutoff": 2,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.09,
                "omega_min_delta_vs_reference": 0.04,
                "max_band_delta_vs_reference": 0.05,
                "retained_linear_term_max_norm": 5.0e-6,
                "discarded_linear_term_max_norm": 7.0e-5,
                "full_tangent_linear_term_max_norm": 3.0e-4,
            },
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 2,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.05,
                "omega_min_delta_vs_reference": 0.0,
                "max_band_delta_vs_reference": 0.0,
                "retained_linear_term_max_norm": 1.0e-7,
                "discarded_linear_term_max_norm": 2.0e-5,
                "full_tangent_linear_term_max_norm": 1.0e-4,
            },
        ],
        "sideband_cutoff_scan": [
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 1,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.06,
                "omega_min_delta_vs_reference": 0.01,
                "max_band_delta_vs_reference": 0.015,
                "retained_linear_term_max_norm": 2.0e-7,
                "discarded_linear_term_max_norm": 2.5e-5,
                "full_tangent_linear_term_max_norm": 1.1e-4,
            },
            {
                "phase_grid_size": 32,
                "z_harmonic_cutoff": 1,
                "sideband_cutoff": 2,
                "resolved_reference_mode": "input",
                "reference_dispersion_recomputed": False,
                "omega_min": 0.05,
                "omega_min_delta_vs_reference": 0.0,
                "max_band_delta_vs_reference": 0.0,
                "retained_linear_term_max_norm": 1.0e-7,
                "discarded_linear_term_max_norm": 2.0e-5,
                "full_tangent_linear_term_max_norm": 1.0e-4,
            },
        ],
    }


def _mocked_single_q_classical_result():
    return {
        "method": "sun-gswt-classical-single-q",
        "ansatz": "single-q-unitary-ray",
        "manifold": "CP^(N-1)",
        "energy": -0.75,
        "starts": 2,
        "seed": 5,
        "q_vector": [0.2, 0.0, 0.0],
        "reference_ray": [
            {"real": 1.0, "imag": 0.0},
            {"real": 1.0, "imag": 0.0},
            {"real": 0.0, "imag": 0.0},
            {"real": 0.0, "imag": 0.0},
        ],
        "generator_matrix": [
            [
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
            [
                {"real": 0.0, "imag": 0.0},
                {"real": 1.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
            [
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
            [
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
        ],
        "classical_state": {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [5, 1, 1],
            "local_rays": [
                {
                    "cell": [0, 0, 0],
                    "vector": [
                        {"real": 1.0, "imag": 0.0},
                        {"real": 1.0, "imag": 0.0},
                        {"real": 0.0, "imag": 0.0},
                        {"real": 0.0, "imag": 0.0},
                    ],
                }
            ],
            "ordering": {"ansatz": "single-q-unitary-ray", "q_vector": [0.2, 0.0, 0.0]},
        },
    }


class SolvePseudoSpinOrbitalPipelineCLITests(unittest.TestCase):
    def test_structural_supercell_schedule_grows_with_structural_dimension(self):
        self.assertEqual(
            list(_structural_supercell_schedule(1, 3, start_linear_size=1)),
            [(1, 1, 1), (2, 1, 1), (3, 1, 1)],
        )
        self.assertEqual(
            list(_structural_supercell_schedule(2, 3, start_linear_size=1)),
            [(1, 1, 1), (2, 2, 1), (3, 3, 1)],
        )
        self.assertEqual(
            list(_structural_supercell_schedule(3, 3, start_linear_size=1)),
            [(1, 1, 1), (2, 2, 2), (3, 3, 3)],
        )

    def test_structural_supercell_schedule_can_run_without_upper_bound(self):
        self.assertEqual(
            list(itertools.islice(_structural_supercell_schedule(1, 0, start_linear_size=2), 4)),
            [(2, 1, 1), (3, 1, 1), (4, 1, 1), (5, 1, 1)],
        )
        self.assertEqual(
            list(itertools.islice(_structural_supercell_schedule(2, -1, start_linear_size=2), 3)),
            [(2, 2, 1), (3, 3, 1), (4, 4, 1)],
        )

    def test_solve_from_files_writes_reports_solver_outputs_and_stage_markdown(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "variational-pseudospin-orbital",
            "energy": -1.23,
            "state": {
                "left": {"spin": [0.0, 0.0, 1.0], "orbital": [1.0, 0.0, 0.0]},
                "right": {"spin": [0.0, 0.0, -1.0], "orbital": [1.0, 0.0, 0.0]},
            },
            "starts": 3,
            "seed": 7,
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_pseudospin_orbital_variational",
            return_value=mocked_solver_result,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=True,
                starts=3,
                seed=7,
            )
            output_dir = Path(tmpdir)
            docs_dir = Path(docsdir)

            self.assertTrue((output_dir / "human_friendly_report.txt").exists())
            self.assertTrue((output_dir / "full_coefficients_report.txt").exists())
            self.assertTrue((output_dir / "classical_model.json").exists())
            self.assertTrue((output_dir / "solver_result.json").exists())
            notes = sorted(docs_dir.glob("*solver-phase.md"))
            self.assertTrue(notes)

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "variational-pseudospin-orbital")
            self.assertEqual(manifest["solver"]["energy"], -1.23)

    def test_solve_from_files_supports_sun_gswt_cpn_method(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "sun-gswt-classical-variational",
            "manifold": "CP^(N-1)",
            "energy": -0.5,
            "supercell_shape": [1, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}]},
            ],
            "projector_diagnostics": {
                "ordering_kind": "uniform",
                "uniform_q_weight": 1.0,
                "dominant_ordering_q": None,
                "dominant_ordering_weight": 0.0,
                "components": [],
                "grid_shape": [1, 1, 1],
            },
            "stationarity": {
                "residual_definition": "r_i = M_i[Q] z_i - (z_i^dagger M_i[Q] z_i) z_i, measured in Euclidean norm",
                "max_residual_norm": 0.0,
                "mean_residual_norm": 0.0,
                "sites": [],
            },
            "starts": 2,
            "seed": 3,
        }
        mocked_gswt_result = {
            "status": "stub",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "payload_kind": "sun_gswt_prototype",
            "ordering": {
                "ansatz": "single-q-unitary-ray",
                "compatibility_with_supercell": {"kind": "incommensurate"},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_sun_gswt_classical_ground_state",
            return_value=mocked_solver_result,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=mocked_gswt_result,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=True,
                classical_method="sun-gswt-cpn",
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "sun-gswt-classical-variational")
            self.assertTrue((Path(tmpdir) / "classical_model.json").exists())
            self.assertTrue((Path(tmpdir) / "gswt_payload.json").exists())
            self.assertTrue((Path(tmpdir) / "gswt_result.json").exists())
            notes = sorted(Path(docsdir).glob("*solver-phase.md"))
            self.assertTrue(notes)
            note_text = notes[-1].read_text(encoding="utf-8")
            self.assertIn("projector_ordering_kind", note_text)
            self.assertIn("stationarity_max_residual_norm", note_text)
            self.assertIn("uniform magnetic-cell ansatz", note_text)
            self.assertIn("gswt_status", note_text)

    def test_solve_from_files_supports_sun_gswt_single_q_method(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "sun-gswt-classical-single-q",
            "ansatz": "single-q-unitary-ray",
            "manifold": "CP^(N-1)",
            "energy": -0.75,
            "q_vector": [0.5, 0.0, 0.0],
            "supercell_shape": [2, 1, 1],
            "local_rays": [
                {"cell": [0, 0, 0], "vector": [{"real": 1.0, "imag": 0.0}]},
                {"cell": [1, 0, 0], "vector": [{"real": 0.0, "imag": 0.0}]},
            ],
            "projector_diagnostics": {
                "ordering_kind": "commensurate-supercell",
                "uniform_q_weight": 0.5,
                "dominant_ordering_q": [0.5, 0.0, 0.0],
                "dominant_ordering_weight": 0.5,
                "components": [],
                "grid_shape": [2, 1, 1],
            },
            "stationarity": {
                "residual_definition": "r_i = M_i[Q] z_i - (z_i^dagger M_i[Q] z_i) z_i, measured in Euclidean norm",
                "max_residual_norm": 0.0,
                "mean_residual_norm": 0.0,
                "sites": [],
            },
            "ansatz_stationarity": {
                "best_objective": -0.75,
                "optimizer_success": True,
                "optimizer_method": "L-BFGS-B",
                "optimization_mode": "direct-joint",
                "optimizer_nit": 10,
                "optimizer_nfev": 100,
            },
            "starts": 2,
            "seed": 5,
        }
        mocked_gswt_result = {
            "status": "stub",
            "backend": {"name": "Sunny.jl", "mode": "SUN"},
            "payload_kind": "sun_gswt_prototype",
            "ordering": {
                "ansatz": "single-q-unitary-ray",
                "compatibility_with_supercell": {"kind": "incommensurate"},
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_sun_gswt_single_q_ground_state",
            return_value=mocked_solver_result,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=mocked_gswt_result,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=True,
                classical_method="sun-gswt-single-q",
                starts=2,
                seed=5,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "sun-gswt-classical-single-q")
            self.assertTrue((Path(tmpdir) / "gswt_payload.json").exists())
            self.assertTrue((Path(tmpdir) / "gswt_result.json").exists())
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("projector_dominant_ordering_q: [0.5, 0.0, 0.0]", note_text)
            self.assertIn("ansatz_optimizer_method: L-BFGS-B", note_text)
            self.assertIn("single-q direct joint optimization", note_text)
            self.assertIn("gswt_status", note_text)
            self.assertIn("gswt_ordering_compatibility_kind: incommensurate", note_text)

    def test_solve_from_files_supports_sunny_cpn_minimize_method(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "status": "ok",
            "method": "sunny-cpn-minimize",
            "energy": -0.5,
            "supercell_shape": [2, 2, 2],
            "local_rays": _shape_local_rays((2, 2, 2)),
            "starts": 2,
            "seed": 3,
            "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
            "convergence": {
                "energy_converged": True,
                "history": [
                    {"shape": [1, 1, 1], "energy": -0.5, "starts": 2, "seed": 3},
                    {"shape": [2, 2, 2], "energy": -0.5, "starts": 2, "seed": 3},
                ],
                "energy_tolerance": 1.0e-6,
                "repeats_required": 2,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: mocked_solver_result if payload["supercell_shape"] == [2, 2, 2] else _mocked_sunny_classical_result(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(state["shape"]),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "sunny-cpn-minimize")
            self.assertEqual(manifest["solver"]["energy"], -0.5)
            self.assertEqual(manifest["solver"]["supercell_shape"], [2, 2, 2])
            self.assertEqual(manifest["solver"]["convergence"]["history"][-1]["shape"], [2, 2, 2])
            self.assertTrue((Path(tmpdir) / "classical_model.json").exists())
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("method: sunny-cpn-minimize", note_text)

    def test_solve_from_files_supports_cpn_local_ray_minimize_method(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "cpn-local-ray-minimize",
            "manifold": "CP^(N-1)",
            "energy": -0.75,
            "supercell_shape": [1, 1, 1],
            "local_rays": _shape_local_rays((1, 1, 1)),
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": _shape_local_rays((1, 1, 1)),
                "ordering": {"kind": "uniform", "supercell_shape": [1, 1, 1]},
            },
            "projector_diagnostics": {
                "ordering_kind": "uniform",
                "uniform_q_weight": 1.0,
                "dominant_ordering_q": None,
                "dominant_ordering_weight": 0.0,
                "components": [],
                "grid_shape": [1, 1, 1],
            },
            "stationarity": {
                "residual_definition": "test residual",
                "max_residual_norm": 0.0,
                "mean_residual_norm": 0.0,
                "sites": [],
            },
            "convergence": {
                "energy_converged": True,
                "history": [{"shape": [1, 1, 1], "energy": -0.75, "best_start_source": "random", "max_local_change": 0.0}],
                "energy_tolerance": 1.0e-6,
                "repeats_required": 1,
            },
            "starts": 2,
            "seed": 3,
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_local_ray_ground_state",
            return_value=mocked_solver_result,
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="cpn-local-ray-minimize",
                run_gswt=False,
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "cpn-local-ray-minimize")
            self.assertEqual(manifest["solver"]["energy"], -0.75)
            self.assertEqual(manifest["solver"]["supercell_shape"], [1, 1, 1])
            self.assertTrue((Path(tmpdir) / "classical_model.json").exists())
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("method: cpn-local-ray-minimize", note_text)

    def test_cpn_local_ray_minimize_uses_exact_glt_seed_as_initial_state(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_calls = []
        mocked_glt = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "q_vector": [0.5, 0.0, 0.0],
            "projector_exactness": {"is_exact_projector_solution": True},
            "seed_candidate": {
                "kind": "commensurate-exact-projector-seed",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": _shape_local_rays((2, 1, 1)),
                    "ordering": {"kind": "commensurate-single-q", "supercell_shape": [2, 1, 1]},
                },
            },
        }

        def fake_local_ray_solver(_model, **kwargs):
            serializable_kwargs = {key: value for key, value in kwargs.items() if key != "progress_callback"}
            observed_calls.append(json.loads(json.dumps(serializable_kwargs)))
            return {
                "method": "cpn-local-ray-minimize",
                "manifold": "CP^(N-1)",
                "energy": -0.8,
                "supercell_shape": [2, 1, 1],
                "local_rays": _shape_local_rays((2, 1, 1)),
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": _shape_local_rays((2, 1, 1)),
                    "ordering": {"kind": "commensurate-single-q", "supercell_shape": [2, 1, 1]},
                },
                "projector_diagnostics": {
                    "ordering_kind": "commensurate-supercell",
                    "uniform_q_weight": 0.0,
                    "dominant_ordering_q": [0.5, 0.0, 0.0],
                    "dominant_ordering_weight": 1.0,
                    "components": [],
                    "grid_shape": [2, 1, 1],
                },
                "stationarity": {
                    "residual_definition": "test residual",
                    "max_residual_norm": 0.0,
                    "mean_residual_norm": 0.0,
                    "sites": [],
                },
                "convergence": {
                    "energy_converged": True,
                    "history": [{"shape": [2, 1, 1], "energy": -0.8, "best_start_source": "glt-seed", "max_local_change": 0.0}],
                    "energy_tolerance": 1.0e-6,
                    "repeats_required": 1,
                },
                "starts": 2,
                "seed": 3,
            }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=mocked_glt,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_local_ray_ground_state",
            side_effect=fake_local_ray_solver,
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="cpn-local-ray-minimize",
                run_gswt=False,
                starts=2,
                seed=3,
            )

        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(len(observed_calls), 1)
        self.assertEqual(observed_calls[0]["initial_state"]["shape"], [2, 1, 1])
        self.assertEqual(len(observed_calls[0]["initial_state"]["local_rays"]), 2)
        self.assertEqual(manifest["solver"]["glt_preconditioner_diagnostic"]["method"], "cpn-generalized-lt")
        self.assertEqual(manifest["solver"]["glt_preconditioner"]["source"], "seed_candidate")

    def test_cpn_local_ray_minimize_writes_checkpoint_updates_to_output_dir(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        running_result = {
            "method": "cpn-local-ray-minimize",
            "manifold": "CP^(N-1)",
            "energy": -0.7,
            "supercell_shape": [1, 1, 1],
            "local_rays": _shape_local_rays((1, 1, 1)),
            "classical_state": {
                "schema_version": 1,
                "state_kind": "local_rays",
                "manifold": "CP^(N-1)",
                "basis_order": "orbital_major_spin_minor",
                "pair_basis_order": "site_i_major_site_j_minor",
                "supercell_shape": [1, 1, 1],
                "local_rays": _shape_local_rays((1, 1, 1)),
                "ordering": {"kind": "uniform", "supercell_shape": [1, 1, 1]},
            },
            "projector_diagnostics": {
                "ordering_kind": "uniform",
                "uniform_q_weight": 1.0,
                "dominant_ordering_q": None,
                "dominant_ordering_weight": 0.0,
                "components": [],
                "grid_shape": [1, 1, 1],
            },
            "stationarity": {
                "residual_definition": "test residual",
                "max_residual_norm": 0.0,
                "mean_residual_norm": 0.0,
                "sites": [],
            },
            "convergence": {
                "energy_converged": False,
                "history": [{"shape": [1, 1, 1], "energy": -0.7, "best_start_source": "random", "max_local_change": 0.0}],
                "energy_tolerance": 1.0e-6,
                "repeats_required": 1,
                "search_mode": "bounded",
                "max_linear_size": 2,
                "stopped_reason": "running",
            },
            "starts": 2,
            "seed": 3,
        }
        completed_result = {
            **running_result,
            "energy": -0.8,
            "supercell_shape": [2, 1, 1],
            "local_rays": _shape_local_rays((2, 1, 1)),
            "classical_state": {
                **running_result["classical_state"],
                "supercell_shape": [2, 1, 1],
                "local_rays": _shape_local_rays((2, 1, 1)),
                "ordering": {"kind": "commensurate-supercell", "supercell_shape": [2, 1, 1]},
            },
            "projector_diagnostics": {
                "ordering_kind": "commensurate-supercell",
                "uniform_q_weight": 0.0,
                "dominant_ordering_q": [0.5, 0.0, 0.0],
                "dominant_ordering_weight": 1.0,
                "components": [],
                "grid_shape": [2, 1, 1],
            },
            "convergence": {
                "energy_converged": True,
                "history": [
                    {"shape": [1, 1, 1], "energy": -0.7, "best_start_source": "random", "max_local_change": 0.0},
                    {"shape": [2, 1, 1], "energy": -0.8, "best_start_source": "tiled-previous", "max_local_change": 0.0},
                ],
                "energy_tolerance": 1.0e-6,
                "repeats_required": 1,
                "search_mode": "bounded",
                "max_linear_size": 2,
                "stopped_reason": "converged",
            },
        }

        def fake_local_ray_solver(_model, **kwargs):
            progress_callback = kwargs["progress_callback"]
            progress_callback(
                {
                    "status": "running",
                    "iteration": 1,
                    "stable_count": 0,
                    "repeats_required": 1,
                    "result": running_result,
                }
            )
            progress_callback(
                {
                    "status": "completed",
                    "iteration": 2,
                    "stable_count": 1,
                    "repeats_required": 1,
                    "result": completed_result,
                }
            )
            return completed_result

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_local_ray_ground_state",
            side_effect=fake_local_ray_solver,
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="cpn-local-ray-minimize",
                run_gswt=False,
                starts=2,
                seed=3,
                max_linear_size=2,
            )

            checkpoint_path = Path(tmpdir) / "classical_checkpoint.json"
            self.assertTrue(checkpoint_path.exists())
            checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_payload["status"], "completed")
            self.assertEqual(checkpoint_payload["result"]["supercell_shape"], [2, 1, 1])
            self.assertEqual(manifest["artifacts"]["classical_checkpoint"], str(checkpoint_path))

    def test_sunny_cpn_minimize_uses_exact_glt_seed_as_initial_local_rays(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []
        mocked_glt = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "q_vector": [0.5, 0.0, 0.0],
            "projector_exactness": {"is_exact_projector_solution": True},
            "seed_candidate": {
                "kind": "commensurate-exact-projector-seed",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": _shape_local_rays((2, 1, 1)),
                    "ordering": {"kind": "commensurate-single-q", "supercell_shape": [2, 1, 1]},
                },
            },
        }

        def fake_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            return _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"]))

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=mocked_glt,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(state["shape"]),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
            )

        self.assertEqual(manifest["status"], "ok")
        self.assertGreaterEqual(len(observed_payloads), 1)
        self.assertIn("initial_local_rays", observed_payloads[0])
        self.assertGreaterEqual(max(observed_payloads[0]["supercell_shape"]), 2)
        self.assertEqual(len(observed_payloads[0]["initial_local_rays"]), 8)

    def test_sunny_cpn_minimize_falls_back_to_relaxed_shell_reconstruction_seed(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []
        mocked_glt = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "q_vector": [0.5, 0.0, 0.0],
            "projector_exactness": {"is_exact_projector_solution": False},
            "reconstruction": {
                "status": "approximate",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
                    "supercell_shape": [2, 1, 1],
                    "local_rays": _shape_local_rays((2, 1, 1)),
                    "ordering": {"kind": "commensurate-single-q", "supercell_shape": [2, 1, 1]},
                },
            },
        }

        def fake_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            return _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"]))

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=mocked_glt,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(state["shape"]),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
            )

        self.assertEqual(manifest["status"], "ok")
        self.assertGreaterEqual(len(observed_payloads), 1)
        self.assertIn("initial_local_rays", observed_payloads[0])
        self.assertEqual(len(observed_payloads[0]["initial_local_rays"]), 8)

    def test_solve_from_files_treats_cpn_generalized_lt_as_diagnostic_only_even_with_exact_uniform_seed(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "manifold": "CP^(N-1)",
            "energy": -1.0,
            "q_vector": [0.0, 0.0, 0.0],
            "relaxed_lt": {
                "q_seed": [0.0, 0.0, 0.0],
                "lower_bound": -1.0,
                "mesh_shape": [17, 17, 17],
                "sample_count": 4913,
            },
            "projector_exactness": {
                "trace_residual": 0.0,
                "hermiticity_residual": 0.0,
                "negativity_residual": 0.0,
                "purity_residual": 0.0,
                "rank_one_residual": 0.0,
                "is_exact_projector_solution": True,
            },
            "seed_candidate": {
                "kind": "uniform-exact-projector-seed",
                "classical_state": {
                    "schema_version": 1,
                    "state_kind": "local_rays",
                    "manifold": "CP^(N-1)",
                    "basis_order": "orbital_major_spin_minor",
                    "pair_basis_order": "site_i_major_site_j_minor",
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
                    "ordering": {"kind": "uniform", "supercell_shape": [1, 1, 1]},
                },
                "projector_diagnostics": {
                    "ordering_kind": "uniform",
                    "uniform_q_weight": 1.0,
                    "dominant_ordering_q": None,
                    "dominant_ordering_weight": 0.0,
                    "components": [],
                    "grid_shape": [1, 1, 1],
                },
                "stationarity": {
                    "residual_definition": "r_i = M_i[Q] z_i - (z_i^dagger M_i[Q] z_i) z_i, measured in Euclidean norm",
                    "max_residual_norm": 0.0,
                    "mean_residual_norm": 0.0,
                    "sites": [],
                },
            },
            "starts": 1,
            "seed": 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=mocked_solver_result,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            side_effect=AssertionError("Diagnostic-only GLT should not auto-run GSWT"),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="cpn-generalized-lt",
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "cpn-generalized-lt")
            self.assertEqual(manifest["solver"]["solver_role"], "diagnostic-only")
            self.assertEqual(manifest["solver"]["relaxed_lt"]["q_seed"], [0.0, 0.0, 0.0])
            self.assertTrue((Path(tmpdir) / "classical_model.json").exists())
            self.assertFalse((Path(tmpdir) / "gswt_payload.json").exists())
            result_payload = json.loads((Path(tmpdir) / "result_payload.json").read_text(encoding="utf-8"))
            self.assertNotIn("classical_state", result_payload)
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("method: cpn-generalized-lt", note_text)
            self.assertIn("relaxed_lt_lower_bound: -1.0", note_text)
            self.assertIn("gswt_payload_written: False", note_text)
            self.assertIn("diagnostic-only", note_text)

    def test_solve_from_files_skips_gswt_when_cpn_generalized_lt_has_no_exact_projector_state(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_solver_result = {
            "method": "cpn-generalized-lt",
            "solver_role": "diagnostic-only",
            "manifold": "CP^(N-1)",
            "energy": -0.8,
            "q_vector": [0.5, 0.0, 0.0],
            "relaxed_lt": {
                "q_seed": [0.5, 0.0, 0.0],
                "lower_bound": -0.8,
                "mesh_shape": [17, 1, 1],
                "sample_count": 17,
            },
            "projector_exactness": {
                "trace_residual": 0.0,
                "hermiticity_residual": 0.0,
                "negativity_residual": 0.0,
                "purity_residual": 1.0e-2,
                "rank_one_residual": 1.0e-2,
                "is_exact_projector_solution": False,
            },
            "starts": 1,
            "seed": 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_cpn_generalized_lt_ground_state",
            return_value=mocked_solver_result,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            side_effect=AssertionError("GSWT should not run without an exact classical_state"),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="cpn-generalized-lt",
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "cpn-generalized-lt")
            self.assertEqual(manifest["solver"]["solver_role"], "diagnostic-only")
            self.assertFalse((Path(tmpdir) / "gswt_payload.json").exists())
            result_payload = json.loads((Path(tmpdir) / "result_payload.json").read_text(encoding="utf-8"))
            self.assertNotIn("classical_state", result_payload)
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("method: cpn-generalized-lt", note_text)
            self.assertIn("gswt_payload_written: False", note_text)
            self.assertIn("diagnostic-only", note_text)

    def test_solve_from_files_auto_expands_sunny_cpn_minimize_until_energy_converges(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []

        def fake_sunny_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            shape = tuple(int(value) for value in payload["supercell_shape"])
            linear_size = max(shape)
            return _mocked_sunny_classical_result(supercell_shape=shape, energy=-0.5 if linear_size >= 2 else -0.5)

        def fake_diagnostics(_model, state):
            shape = list(state["shape"])
            return {
                "projector_diagnostics": {
                    "ordering_kind": "uniform",
                    "dominant_ordering_q": None,
                    "dominant_ordering_weight": 0.0,
                    "uniform_q_weight": 1.0,
                    "grid_shape": list(shape),
                    "components": [],
                },
                "stationarity": {
                    "residual_definition": "test residual",
                    "max_residual_norm": 1.0e-8,
                    "mean_residual_norm": 1.0e-8,
                    "sites": [],
                },
            }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_sunny_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=fake_diagnostics,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
                max_linear_size=4,
                convergence_repeats=2,
            )

        self.assertEqual([item["supercell_shape"] for item in observed_payloads], [[1, 1, 1], [2, 2, 2]])
        self.assertNotIn("initial_local_rays", observed_payloads[0])
        self.assertEqual(len(observed_payloads[1]["initial_local_rays"]), 8)
        self.assertEqual(manifest["solver"]["supercell_shape"], [2, 2, 2])
        self.assertTrue(manifest["solver"]["convergence"]["energy_converged"])
        self.assertEqual(
            [item["shape"] for item in manifest["solver"]["convergence"]["history"]],
            [[1, 1, 1], [2, 2, 2]],
        )

    def test_solve_from_files_emits_unified_sunny_pseudospin_orbital_progress_messages(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload, **_kwargs: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(
                state["shape"],
                ordering_kind="commensurate-supercell",
                dominant_ordering_q=[0.0, 0.0, 0.0],
            ),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-local-sampler"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ), patch("sys.stderr", new_callable=io.StringIO) as fake_stderr:
            solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-local-sampler",
                temperatures=[0.2, 0.4],
            )

        progress = fake_stderr.getvalue()
        self.assertIn("Starting Sunny pseudospin-orbital CP^(N-1) classical minimization", progress)
        self.assertIn("Sunny pseudospin-orbital SUN classical convergence", progress)
        self.assertIn("Starting Sunny pseudospin-orbital thermodynamics", progress)
        self.assertIn("Finished Sunny pseudospin-orbital thermodynamics", progress)

    def test_solve_from_files_uses_unified_error_message_when_sunny_thermodynamics_lacks_cpn_state(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Sunny pseudospin-orbital thermodynamics requires a CP\\^\\(N-1\\) classical state",
            ):
                solve_from_files(
                    poscar_path=poscar_path,
                    hr_path=hr_path,
                    output_dir=tmpdir,
                    docs_dir=docsdir,
                    compile_pdf=False,
                    classical_method="restricted-product-state",
                    run_thermodynamics=True,
                    thermodynamics_backend="sunny-local-sampler",
                    temperatures=[0.2],
                )

    def test_solve_from_files_auto_expands_without_upper_bound_until_energy_converges(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []

        def fake_sunny_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            shape = tuple(int(value) for value in payload["supercell_shape"])
            linear_size = max(shape)
            energy = -0.6 if linear_size >= 3 else -1.0 + 0.1 * linear_size
            return _mocked_sunny_classical_result(supercell_shape=shape, energy=energy)

        def fake_diagnostics(_model, state):
            return _mocked_sunny_diagnostics(state["shape"], ordering_kind="uniform", dominant_ordering_q=None, max_residual_norm=1.0e-8)

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_sunny_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=fake_diagnostics,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
                max_linear_size=0,
                convergence_repeats=2,
            )

        self.assertEqual(
            [item["supercell_shape"] for item in observed_payloads],
            [[1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]],
        )
        self.assertEqual(manifest["solver"]["supercell_shape"], [4, 4, 4])
        self.assertTrue(manifest["solver"]["convergence"]["energy_converged"])
        self.assertEqual(manifest["solver"]["convergence"]["search_mode"], "until-converged")
        self.assertEqual(manifest["solver"]["convergence"]["stopped_reason"], "converged")
        self.assertIsNone(manifest["solver"]["convergence"]["max_linear_size"])
        self.assertEqual(
            [item["shape"] for item in manifest["solver"]["convergence"]["history"]],
            [[1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]],
        )

    def test_solve_from_files_requires_stationarity_before_declaring_sunny_convergence(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []

        def fake_sunny_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            shape = tuple(int(value) for value in payload["supercell_shape"])
            return _mocked_sunny_classical_result_nested_only(supercell_shape=shape, energy=-0.5)

        def fake_diagnostics(_model, state):
            shape = list(state["shape"])
            residual = 1.0e-2 if shape in ([1, 1, 1], [2, 2, 2]) else 1.0e-8
            ordering_kind = "uniform" if shape == [1, 1, 1] else "commensurate-supercell"
            return {
                "projector_diagnostics": {
                    "ordering_kind": ordering_kind,
                    "dominant_ordering_q": [0.5, 0.0, 0.0] if ordering_kind != "uniform" else None,
                    "dominant_ordering_weight": 1.0 if ordering_kind != "uniform" else 0.0,
                    "uniform_q_weight": 1.0 if ordering_kind == "uniform" else 0.1,
                    "grid_shape": list(shape),
                    "components": [],
                },
                "stationarity": {
                    "residual_definition": "test residual",
                    "max_residual_norm": residual,
                    "mean_residual_norm": residual,
                    "sites": [],
                },
            }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_sunny_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=fake_diagnostics,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
                max_linear_size=4,
                convergence_repeats=2,
            )

        self.assertEqual(
            [item["supercell_shape"] for item in observed_payloads],
            [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
        )
        self.assertEqual(manifest["solver"]["supercell_shape"], [3, 3, 3])
        self.assertTrue(manifest["solver"]["convergence"]["energy_converged"])
        self.assertTrue(manifest["solver"]["convergence"]["history"][-1]["stationarity_converged"])
        self.assertEqual(
            [item["shape"] for item in manifest["solver"]["convergence"]["history"]],
            [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
        )

    def test_solve_from_files_prefers_backend_stationarity_for_sunny_convergence(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        observed_payloads = []

        def fake_sunny_backend(payload):
            observed_payloads.append(json.loads(json.dumps(payload)))
            shape = tuple(int(value) for value in payload["supercell_shape"])
            return _with_backend_stationarity(
                _mocked_sunny_classical_result_nested_only(supercell_shape=shape, energy=-0.5),
                max_residual_norm=1.0e-8,
            )

        def fake_diagnostics(_model, state):
            return _mocked_sunny_diagnostics(
                state["shape"],
                ordering_kind="uniform",
                dominant_ordering_q=None,
                max_residual_norm=1.0e-2,
            )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=fake_sunny_backend,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=fake_diagnostics,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
                max_linear_size=4,
                convergence_repeats=2,
            )

        self.assertEqual([item["supercell_shape"] for item in observed_payloads], [[1, 1, 1], [2, 2, 2]])
        self.assertEqual(manifest["solver"]["supercell_shape"], [2, 2, 2])
        self.assertEqual(
            [item["shape"] for item in manifest["solver"]["convergence"]["history"]],
            [[1, 1, 1], [2, 2, 2]],
        )

    def test_solve_from_files_routes_sunny_cpn_minimize_into_gswt_handoff(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        mocked_gswt_result = {
            **_mocked_gswt_result(),
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=mocked_gswt_result,
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertTrue((Path(tmpdir) / "gswt_payload.json").exists())
            self.assertTrue((Path(tmpdir) / "gswt_result.json").exists())
            self.assertEqual(manifest["solver"]["gswt"]["status"], "ok")
            self.assertEqual(manifest["solver"]["gswt"]["payload_kind"], "sun_gswt_prototype")

    def test_solve_from_files_supports_python_gswt_backend_for_sunny_cpn_minimize(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_python_glswt_driver",
            return_value=_mocked_python_gswt_result(),
            create=True,
        ) as python_glswt_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            create=True,
        ) as sunny_gswt_mock:
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                gswt_backend="python",
                starts=2,
                seed=3,
            )

            python_glswt_mock.assert_called_once()
            sunny_gswt_mock.assert_not_called()
            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["gswt"]["backend"]["name"], "python-glswt")
            self.assertEqual(manifest["solver"]["gswt"]["payload_kind"], "python_glswt_local_rays")
            gswt_payload = json.loads((Path(tmpdir) / "gswt_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(gswt_payload["payload_kind"], "python_glswt_local_rays")
            self.assertTrue((Path(tmpdir) / "gswt_result.json").exists())

    def test_solve_from_files_supports_python_gswt_backend_for_sun_gswt_single_q(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_sun_gswt_single_q_ground_state",
            return_value=_mocked_single_q_classical_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_python_glswt_driver",
            return_value=_mocked_python_single_q_gswt_result(),
            create=True,
        ) as python_glswt_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            create=True,
        ) as sunny_gswt_mock:
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sun-gswt-single-q",
                gswt_backend="python",
                starts=2,
                seed=5,
            )

            python_glswt_mock.assert_called_once()
            sunny_gswt_mock.assert_not_called()
            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["gswt"]["backend"]["name"], "python-glswt")
            self.assertEqual(manifest["solver"]["gswt"]["payload_kind"], "python_glswt_single_q_z_harmonic")
            gswt_payload = json.loads((Path(tmpdir) / "gswt_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(gswt_payload["payload_kind"], "python_glswt_single_q_z_harmonic")
            self.assertEqual(gswt_payload["q_vector"], [0.2, 0.0, 0.0])

    def test_solve_from_files_passes_single_q_reference_mode_into_python_payload(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_sun_gswt_single_q_ground_state",
            return_value=_mocked_single_q_classical_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_python_glswt_driver",
            return_value=_mocked_python_single_q_gswt_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sun-gswt-single-q",
                gswt_backend="python",
                z_harmonic_reference_mode="refined-retained-local",
                starts=2,
                seed=5,
            )

            self.assertEqual(manifest["status"], "ok")
            gswt_payload = json.loads((Path(tmpdir) / "gswt_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(gswt_payload["z_harmonic_reference_mode"], "refined-retained-local")

    def test_solve_from_files_writes_single_q_convergence_artifacts_for_python_backend(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.solve_sun_gswt_single_q_ground_state",
            return_value=_mocked_single_q_classical_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_python_glswt_driver",
            return_value=_mocked_python_single_q_gswt_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_single_q_z_harmonic_convergence_driver",
            return_value=_mocked_single_q_convergence_result(),
            create=True,
        ) as convergence_mock, patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sun-gswt-single-q",
                gswt_backend="python",
                starts=2,
                seed=5,
            )

            convergence_mock.assert_called_once()
            output_dir = Path(tmpdir)
            self.assertTrue((output_dir / "single_q_convergence.json").exists())
            self.assertTrue((output_dir / "single_q_convergence_summary.md").exists())
            convergence_result = json.loads(
                (output_dir / "single_q_convergence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                convergence_result["analysis_kind"],
                "single_q_z_harmonic_convergence",
            )
            summary_text = (output_dir / "single_q_convergence_summary.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Single-Q Z-Harmonic Convergence Summary", summary_text)
            self.assertIn("reference phase_grid_size: 32", summary_text)
            report_text = (output_dir / "report.txt").read_text(encoding="utf-8")
            self.assertIn("Single-Q Z-Harmonic Convergence:", report_text)
            self.assertIn("reference_phase_grid_size=32", report_text)
            self.assertEqual(
                manifest["artifacts"]["single_q_convergence"],
                str(output_dir / "single_q_convergence.json"),
            )
            self.assertEqual(
                manifest["artifacts"]["single_q_convergence_summary"],
                str(output_dir / "single_q_convergence_summary.md"),
            )
            result_payload = json.loads((output_dir / "result_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(
                result_payload["single_q_convergence"]["analysis_kind"],
                "single_q_z_harmonic_convergence",
            )

    def test_solve_from_files_materializes_result_payload_and_bundle_for_sunny_cpn_pipeline(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        def fake_write_results_bundle(payload, output_dir, **kwargs):
            output_dir = Path(output_dir)
            self.assertEqual(payload["classical"]["classical_state"]["state_kind"], "local_rays")
            self.assertEqual(payload["classical_state"]["manifold"], "CP^(N-1)")
            self.assertEqual(payload["gswt"]["status"], "ok")
            self.assertFalse(kwargs["run_missing_classical"])
            self.assertFalse(kwargs["run_missing_thermodynamics"])
            self.assertFalse(kwargs["run_missing_gswt"])
            self.assertFalse(kwargs["run_missing_lswt"])
            (output_dir / "bundle_manifest.json").write_text(
                json.dumps({"status": "partial", "plots": {"plots": {}}}),
                encoding="utf-8",
            )
            (output_dir / "report.txt").write_text("bundle report", encoding="utf-8")
            (output_dir / "plot_payload.json").write_text(
                json.dumps({"schema": "plot_payload"}),
                encoding="utf-8",
            )
            return {"status": "partial", "plots": {"plots": {}}}

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            return_value=_mocked_sunny_classical_result_nested_only(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.write_results_bundle",
            side_effect=fake_write_results_bundle,
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                starts=2,
                seed=3,
            )

            output_dir = Path(tmpdir)
            result_payload = json.loads((output_dir / "result_payload.json").read_text(encoding="utf-8"))
            self.assertEqual(result_payload["classical"]["classical_state"]["state_kind"], "local_rays")
            self.assertEqual(result_payload["gswt"]["status"], "ok")
            self.assertEqual(result_payload["lattice"]["dimension"], 3)
            self.assertEqual(result_payload["lattice"]["interaction_dimension"], 3)
            self.assertEqual(manifest["bundle"]["status"], "partial")
            self.assertEqual(manifest["artifacts"]["result_payload"], str(output_dir / "result_payload.json"))
            self.assertEqual(manifest["artifacts"]["bundle_manifest"], str(output_dir / "bundle_manifest.json"))
            self.assertEqual(manifest["artifacts"]["bundle_report"], str(output_dir / "report.txt"))

    def test_solve_from_files_supports_sunny_local_sampler_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-local-sampler"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-local-sampler",
                temperatures=[0.2, 0.4],
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertTrue((Path(tmpdir) / "thermodynamics_result.json").exists())
            self.assertIsNotNone(manifest["artifacts"]["thermodynamics_result"])
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("## Pseudospin-Orbital Thermodynamics", note_text)
            self.assertIn("thermodynamics_backend: sunny-local-sampler", note_text)
            self.assertIn("spin-only Sunny thermodynamics or LSWT chain", note_text)

    def test_solve_from_files_applies_smoke_thermodynamics_profile_defaults(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        def fake_thermodynamics_driver(payload):
            self.assertEqual(payload["backend_method"], "sunny-local-sampler")
            self.assertEqual(payload["profile"], "smoke")
            self.assertEqual(payload["sweeps"], 10)
            self.assertEqual(payload["burn_in"], 5)
            self.assertEqual(payload["measurement_interval"], 1)
            self.assertAlmostEqual(payload["proposal_scale"], 0.1, places=8)
            return _mocked_sunny_thermodynamics_result("sunny-local-sampler")

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(
                state["shape"],
                ordering_kind="commensurate-supercell",
                dominant_ordering_q=[0.0, 0.0, 0.0],
            ),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            side_effect=fake_thermodynamics_driver,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermo_profile="smoke",
                temperatures=[0.2, 0.4],
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertTrue((Path(tmpdir) / "thermodynamics_result.json").exists())
            self.assertIsNotNone(manifest["artifacts"]["thermodynamics_result"])

    def test_solve_from_files_records_resolved_thermodynamics_configuration_in_result_payload(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-local-sampler"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermo_profile="smoke",
                temperatures=[0.2, 0.4],
            )

            result_payload = json.loads(
                Path(manifest["artifacts"]["result_payload"]).read_text(encoding="utf-8")
            )

            self.assertEqual(result_payload["thermodynamics"]["profile"], "smoke")
            self.assertEqual(result_payload["thermodynamics"]["backend_method"], "sunny-local-sampler")
            self.assertEqual(result_payload["thermodynamics"]["temperatures"], [0.2, 0.4])
            self.assertEqual(result_payload["thermodynamics"]["sweeps"], 10)
            self.assertEqual(result_payload["thermodynamics"]["burn_in"], 5)
            self.assertEqual(result_payload["thermodynamics"]["measurement_interval"], 1)
            self.assertEqual(result_payload["thermodynamics_result"]["configuration"]["profile"], "smoke")
            self.assertEqual(
                result_payload["thermodynamics_result"]["configuration"]["proposal"],
                "delta",
            )
            self.assertAlmostEqual(
                result_payload["thermodynamics_result"]["configuration"]["proposal_scale"],
                0.1,
                places=8,
            )

    def test_solve_from_files_accepts_flat_thermodynamics_backend_result_shape(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(
                state["shape"],
                ordering_kind="commensurate-supercell",
                dominant_ordering_q=[0.0, 0.0, 0.0],
            ),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result_flat("sunny-local-sampler"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermo_profile="smoke",
                temperatures=[0.2, 0.4],
            )

            thermo_path = Path(manifest["artifacts"]["thermodynamics_result"])
            self.assertTrue(thermo_path.exists())
            thermodynamics_result = json.loads(thermo_path.read_text(encoding="utf-8"))
            self.assertEqual(thermodynamics_result["method"], "sunny-local-sampler")
            self.assertEqual(thermodynamics_result["configuration"]["profile"], "smoke")
            self.assertEqual(len(thermodynamics_result["grid"]), 1)

    def test_solve_from_files_can_skip_gswt_when_running_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-local-sampler"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            side_effect=AssertionError("GSWT should be skipped"),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermo_profile="smoke",
                temperatures=[0.2],
                run_gswt=False,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertIsNone(manifest["artifacts"]["gswt_payload"])
            self.assertIsNone(manifest["artifacts"]["gswt_result"])
            self.assertFalse(manifest["bundle"]["stages"]["gswt"]["present"])
            self.assertTrue((Path(tmpdir) / "thermodynamics_result.json").exists())

    def test_solve_from_files_accepts_nested_canonical_classical_state_for_diagnostics_and_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        def fake_thermodynamics_driver(payload):
            self.assertEqual(payload["initial_state"]["shape"], [2, 2, 2])
            self.assertEqual(len(payload["initial_state"]["local_rays"]), 8)
            return _mocked_sunny_thermodynamics_result("sunny-local-sampler")

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result_nested_only(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.diagnose_sun_gswt_classical_state",
            side_effect=lambda _model, state: _mocked_sunny_diagnostics(
                state["shape"],
                ordering_kind="commensurate-supercell",
                dominant_ordering_q=[0.0, 0.0, 0.0],
            ),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            side_effect=fake_thermodynamics_driver,
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-local-sampler",
                temperatures=[0.2, 0.4],
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertEqual(manifest["solver"]["method"], "sunny-cpn-minimize")
            self.assertEqual(manifest["solver"]["classical_state"]["schema_version"], 1)
            self.assertEqual(manifest["solver"]["projector_diagnostics"]["ordering_kind"], "commensurate-supercell")
            self.assertLess(manifest["solver"]["stationarity"]["max_residual_norm"], 1e-8)

    def test_solve_from_files_supports_sunny_parallel_tempering_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-parallel-tempering"),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-parallel-tempering",
                temperatures=[0.2, 0.4, 0.8],
                thermo_pt_temperatures=[0.2, 0.4, 0.8],
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertTrue((Path(tmpdir) / "thermodynamics_result.json").exists())

    def test_solve_from_files_supports_sunny_wang_landau_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            side_effect=lambda payload: _mocked_sunny_classical_result(tuple(payload["supercell_shape"])),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_thermodynamics",
            return_value=_mocked_sunny_thermodynamics_result("sunny-wang-landau", include_dos=True),
            create=True,
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sun_gswt",
            return_value=_mocked_gswt_result(),
            create=True,
        ):
            manifest = solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir=tmpdir,
                docs_dir=docsdir,
                compile_pdf=False,
                classical_method="sunny-cpn-minimize",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-wang-landau",
                temperatures=[0.2, 0.4],
                thermo_wl_bounds=[-2.0, 0.0],
                thermo_wl_bin_size=0.05,
            )

            self.assertEqual(manifest["status"], "ok")
            self.assertTrue((Path(tmpdir) / "dos_result.json").exists())
            self.assertIsNotNone(manifest["artifacts"]["dos_result"])

    def test_rejects_restricted_product_state_for_sunny_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        with self.assertRaisesRegex(ValueError, "CP\\^\\(N-1\\) classical state"):
            solve_from_files(
                poscar_path=poscar_path,
                hr_path=hr_path,
                output_dir="/tmp/ignored-output",
                docs_dir="/tmp/ignored-docs",
                compile_pdf=False,
                classical_method="restricted-product-state",
                run_thermodynamics=True,
                thermodynamics_backend="sunny-local-sampler",
                temperatures=[0.2, 0.4],
            )


if __name__ == "__main__":
    unittest.main()
