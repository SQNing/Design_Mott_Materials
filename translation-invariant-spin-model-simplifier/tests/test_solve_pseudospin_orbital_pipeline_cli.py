import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.solve_pseudospin_orbital_pipeline import solve_from_files


def _mocked_sunny_classical_result():
    return {
        "status": "ok",
        "method": "sunny-cpn-minimize",
        "energy": -0.5,
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
            },
        ],
        "starts": 2,
        "seed": 3,
        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
    }


def _mocked_sunny_classical_result_nested_only():
    rays = [
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
                {"real": 1.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
                {"real": 0.0, "imag": 0.0},
            ],
        },
    ]
    return {
        "status": "ok",
        "method": "sunny-cpn-minimize",
        "energy": -0.5,
        "starts": 2,
        "seed": 3,
        "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
        "classical_state": {
            "schema_version": 1,
            "state_kind": "local_rays",
            "manifold": "CP^(N-1)",
            "basis_order": "orbital_major_spin_minor",
            "pair_basis_order": "site_i_major_site_j_minor",
            "supercell_shape": [2, 1, 1],
            "local_rays": rays,
            "ordering": {
                "kind": "commensurate-supercell",
                "supercell_shape": [2, 1, 1],
            },
        },
    }


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


def _mocked_gswt_result():
    return {
        "status": "ok",
        "backend": {"name": "Sunny.jl", "mode": "SUN"},
        "payload_kind": "sun_gswt_prototype",
        "dispersion": [{"q": [0.0, 0.0, 0.0], "bands": [0.0]}],
    }


class SolvePseudoSpinOrbitalPipelineCLITests(unittest.TestCase):
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
                        {"real": 1.0, "imag": 0.0},
                        {"real": 0.0, "imag": 0.0},
                        {"real": 0.0, "imag": 0.0},
                    ],
                },
            ],
            "starts": 2,
            "seed": 3,
            "backend": {"name": "Sunny.jl", "mode": "SUN", "solver": "minimize_energy!"},
        }

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            return_value=mocked_solver_result,
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
            self.assertTrue((Path(tmpdir) / "classical_model.json").exists())
            note_text = sorted(Path(docsdir).glob("*solver-phase.md"))[-1].read_text(encoding="utf-8")
            self.assertIn("method: sunny-cpn-minimize", note_text)

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
            return_value=_mocked_sunny_classical_result_nested_only(),
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
            return_value=_mocked_sunny_classical_result(),
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

    def test_solve_from_files_accepts_nested_canonical_classical_state_for_diagnostics_and_thermodynamics(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        def fake_thermodynamics_driver(payload):
            self.assertEqual(payload["initial_state"]["shape"], [2, 1, 1])
            self.assertEqual(len(payload["initial_state"]["local_rays"]), 2)
            return _mocked_sunny_thermodynamics_result("sunny-local-sampler")

        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as docsdir, patch(
            "output.render_pseudospin_orbital_report.subprocess.run"
        ), patch(
            "cli.solve_pseudospin_orbital_pipeline.run_sunny_sun_classical",
            return_value=_mocked_sunny_classical_result_nested_only(),
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
            return_value=_mocked_sunny_classical_result(),
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
            return_value=_mocked_sunny_classical_result(),
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
