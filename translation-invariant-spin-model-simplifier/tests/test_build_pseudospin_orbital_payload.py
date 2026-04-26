import sys
import tempfile
import unittest
import warnings
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli.build_pseudospin_orbital_payload import build_pseudospin_orbital_payload


class BuildPseudoSpinOrbitalPayloadTests(unittest.TestCase):
    @staticmethod
    def _write_minimal_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "minimal triangular one-site lattice",
                    "1.0",
                    "1.0 0.0 0.0",
                    "0.5 0.8660254037844386 0.0",
                    "0.0 0.0 8.0",
                    "Fe",
                    "1",
                    "Direct",
                    "0.0 0.0 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_two_site_poscar(path):
        path.write_text(
            "\n".join(
                [
                    "two-site triangular lattice",
                    "1.0",
                    "1.0 0.0 0.0",
                    "0.5 0.8660254037844386 0.0",
                    "0.0 0.0 8.0",
                    "Fe",
                    "2",
                    "Direct",
                    "0.0 0.0 0.0",
                    "0.3333333333333333 0.6666666666666666 0.0",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_minimal_many_body_hr(path, R_vectors=((1, 0, 0),)):
        rows = []
        for rx, ry, rz in R_vectors:
            for m in range(1, 5):
                for n in range(1, 5):
                    value = 1.0 if m == n else 0.0
                    rows.append(
                        f"    {rx}    {ry}    {rz}    {m}    {n}    {value:.15f}    0.000000000000000"
                    )
        path.write_text(
            "\n".join(
                [
                    "minimal wannier_hr.dat",
                    "4",
                    str(len(tuple(R_vectors))),
                    " ".join(["1"] * len(tuple(R_vectors))),
                    *rows,
                    "",
                ]
            ),
            encoding="utf-8",
        )

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

    def test_build_pseudospin_orbital_payload_reads_current_example(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["classical_family"], "cpn")
        self.assertEqual(payload["basis_semantics"]["local_space"], "pseudospin_orbital")
        self.assertEqual(payload["basis_semantics"]["local_space_mode"], "generic-multiplet")
        self.assertEqual(payload["basis_order"], "retained_state_index")
        self.assertEqual(payload["pair_basis_order"], "site_i_major_site_j_minor")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["hamiltonian"]["num_wann"], 16)
        self.assertGreater(payload["hamiltonian"]["nrpts"], 0)
        self.assertEqual(payload["inferred"]["local_dimension"], 4)
        self.assertEqual(payload["inferred"]["multiplet_dimension"], 4)
        self.assertEqual(payload["inferred"]["two_site_dimension"], 16)
        self.assertEqual(payload["inferred"]["site_count_assumption"], 2)
        self.assertEqual(payload["magnetic_site_count"], 1)
        self.assertEqual(payload["magnetic_sites"][0]["index"], 0)
        self.assertEqual(payload["magnetic_sites"][0]["label"], "site0")
        self.assertEqual(
            payload["magnetic_site_metadata"]["site_pair_encoding"],
            "assumed-single-sublattice-many_body_hr",
        )
        self.assertEqual(payload["retained_local_space"]["dimension"], 4)
        self.assertEqual(payload["retained_local_space"]["factorization"]["kind"], "generic_multiplet")
        self.assertEqual(payload["retained_local_space"]["factorization"]["multiplet_dimension"], 4)
        self.assertNotIn("tensor_factor_order", payload["retained_local_space"])
        self.assertEqual(payload["retained_local_space"]["basis_labels"], payload["local_basis_labels"])
        self.assertEqual(payload["pair_operator_convention"]["pair_basis_order"], "site_i_major_site_j_minor")
        self.assertEqual(
            payload["pair_operator_convention"]["tensor_view"]["index_order"],
            ["left_bra", "right_bra", "left_ket", "right_ket"],
        )
        self.assertEqual(payload["operator_dictionary"]["local_basis_kind"], "generic_multiplet")
        self.assertNotIn("tensor_factor_order", payload["operator_dictionary"])
        self.assertEqual(
            payload["operator_dictionary"]["local_operator_basis"]["matrix_construction"],
            "local_generator_basis",
        )
        self.assertTrue(payload["bond_blocks"])
        self.assertEqual(payload["canonicalization_status"], "canonicalized")

        first_block = payload["bond_blocks"][0]
        self.assertEqual(len(payload["raw_bond_blocks"]), payload["hamiltonian"]["nrpts"])
        self.assertLessEqual(len(payload["bond_blocks"]), len(payload["raw_bond_blocks"]))
        self.assertEqual(len(first_block["R"]), 3)
        self.assertEqual(first_block["source"], 0)
        self.assertEqual(first_block["target"], 0)
        self.assertEqual(first_block["matrix_shape"], [16, 16])
        self.assertGreater(len(first_block["coefficients"]), 0)

    def test_build_pseudospin_orbital_payload_explicit_auto_keeps_legacy_even_dim_factorization(self):
        poscar_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/POSCAR"
        )
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )

        payload = build_pseudospin_orbital_payload(
            poscar_path=poscar_path,
            hr_path=hr_path,
            local_space_mode="auto",
        )

        self.assertEqual(payload["basis_semantics"]["local_space_mode"], "orbital-times-spin")
        self.assertEqual(payload["basis_order"], "orbital_major_spin_minor")
        self.assertEqual(payload["inferred"]["orbital_count"], 2)
        self.assertEqual(payload["retained_local_space"]["factorization"]["kind"], "orbital_times_spin")
        self.assertEqual(payload["operator_dictionary"]["local_basis_kind"], "orbital_times_spin")

    def test_build_pseudospin_orbital_payload_reads_cif_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cif_path = Path(tmpdir) / "structure.cif"
            self._write_minimal_cif(cif_path)

            payload = build_pseudospin_orbital_payload(poscar_path=cif_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "fractional")
        self.assertEqual(payload["structure"]["source_format"], "cif")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)

    def test_build_pseudospin_orbital_payload_canonicalized_many_body_hr_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_minimal_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path)

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["canonicalization_status"], "canonicalized")
        self.assertIn("raw_bond_blocks", payload)
        self.assertTrue(payload["raw_bond_blocks"])
        self.assertTrue(payload["bond_blocks"])

        first_block = payload["bond_blocks"][0]
        self.assertIn("orbit_id", first_block)
        self.assertIn("orbit_representative", first_block)
        self.assertIn("orbit_members", first_block)
        self.assertIn("coordinate_convention", first_block)

    def test_build_pseudospin_orbital_payload_orbit_merge_preserves_raw_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_minimal_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0), (0, 1, 0)))

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["canonicalization_status"], "canonicalized")
        self.assertEqual(len(payload["raw_bond_blocks"]), 2)
        self.assertEqual(len(payload["bond_blocks"]), 1)
        self.assertEqual(payload["bond_blocks"][0]["raw_block_refs"], [0, 1])
        self.assertEqual(
            {
                tuple(member["translation"])
                for member in payload["bond_blocks"][0]["orbit_members"]
            },
            {
                (1, 0, 0),
                (0, 1, 0),
                (1, -1, 0),
            },
        )

    def test_build_pseudospin_orbital_payload_unresolved_when_multisite_structure_lacks_site_pair_assignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_two_site_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0),))

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["canonicalization_status"], "unresolved")
        self.assertIn("diagnostics", payload)
        self.assertIn("unresolved_blocks", payload["diagnostics"])
        self.assertEqual(payload["diagnostics"]["unresolved_blocks"], [0])

    def test_build_pseudospin_orbital_payload_reports_pair_identity_missing_for_multisite_direct_route(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_two_site_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0),))

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["identity_level"], "matrix_entry")
        self.assertEqual(payload["pair_identity_status"], "unavailable")
        self.assertTrue(payload["raw_hr_entries"])
        self.assertEqual(
            payload["diagnostics"]["reason"],
            "pair-identity-unavailable-for-multisite-direct-route",
        )

    def test_build_pseudospin_orbital_payload_canonicalizer_boundary_reports_pair_identity_blocker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_two_site_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0),))

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertEqual(payload["canonicalization_status"], "unresolved")
        self.assertEqual(payload["pair_identity_status"], "unavailable")
        self.assertIn("diagnostics", payload)
        self.assertEqual(
            payload["diagnostics"]["identity_blocker"],
            "pair-identity-unavailable",
        )

    def test_build_pseudospin_orbital_payload_preserves_pre_aggregation_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            poscar_path = Path(tmpdir) / "POSCAR"
            hr_path = Path(tmpdir) / "wannier_hr.dat"
            self._write_minimal_poscar(poscar_path)
            self._write_minimal_many_body_hr(hr_path, R_vectors=((1, 0, 0),))

            payload = build_pseudospin_orbital_payload(poscar_path=poscar_path, hr_path=hr_path)

        self.assertIn("raw_hr_entries", payload)
        self.assertEqual(len(payload["raw_hr_entries"]), 16)
        first_entry = payload["raw_hr_entries"][0]
        self.assertIn("row_index", first_entry)
        self.assertIn("R", first_entry)

        first_raw_block = payload["raw_bond_blocks"][0]
        self.assertIn("entry_refs", first_raw_block)
        self.assertEqual(len(first_raw_block["entry_refs"]), 16)

    def test_build_pseudospin_orbital_payload_reads_xsf_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            xsf_path = Path(tmpdir) / "structure.xsf"
            self._write_minimal_xsf(xsf_path)

            payload = build_pseudospin_orbital_payload(poscar_path=xsf_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "fractional")
        self.assertEqual(payload["structure"]["source_format"], "xsf")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)

    def test_build_pseudospin_orbital_payload_reads_xyz_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            xyz_path = Path(tmpdir) / "structure.xyz"
            self._write_minimal_xyz(xyz_path)

            payload = build_pseudospin_orbital_payload(poscar_path=xyz_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "cartesian")
        self.assertEqual(payload["structure"]["source_format"], "xyz")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)

    def test_build_pseudospin_orbital_payload_reads_cell_structure_file_without_castep_warnings(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cell_path = Path(tmpdir) / "structure.cell"
            self._write_minimal_cell(cell_path)

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                payload = build_pseudospin_orbital_payload(poscar_path=cell_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["source_format"], "cell")
        self.assertEqual(
            [str(item.message) for item in caught if "CASTEP" in str(item.message) or "read_cell" in str(item.message)],
            [],
        )

    def test_build_pseudospin_orbital_payload_reads_gen_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            gen_path = Path(tmpdir) / "structure.gen"
            self._write_minimal_gen(gen_path)

            payload = build_pseudospin_orbital_payload(poscar_path=gen_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "fractional")
        self.assertEqual(payload["structure"]["source_format"], "gen")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)

    def test_build_pseudospin_orbital_payload_reads_res_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            res_path = Path(tmpdir) / "structure.res"
            self._write_minimal_res(res_path)

            payload = build_pseudospin_orbital_payload(poscar_path=res_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "fractional")
        self.assertEqual(payload["structure"]["source_format"], "res")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)

    def test_build_pseudospin_orbital_payload_reads_pdb_structure_file(self):
        hr_path = Path(
            "/data/work/zhli/run/codex/spin-effective-Hamiltonian/U2.0J0.0-not-mix/VR_hr.dat"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pdb_path = Path(tmpdir) / "structure.pdb"
            self._write_minimal_pdb(pdb_path)

            payload = build_pseudospin_orbital_payload(poscar_path=pdb_path, hr_path=hr_path)

        self.assertEqual(payload["input_mode"], "many_body_hr")
        self.assertEqual(payload["structure"]["species"], ["Ru"])
        self.assertEqual(payload["structure"]["counts"], [1])
        self.assertEqual(payload["structure"]["coordinate_mode"], "cartesian")
        self.assertEqual(payload["structure"]["source_format"], "pdb")
        self.assertEqual(len(payload["structure"]["lattice_vectors"]), 3)
        self.assertEqual(len(payload["structure"]["positions"]), 1)


if __name__ == "__main__":
    unittest.main()
