import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cli import solve_cpn_payload_pipeline
from cli import solve_pseudospin_orbital_pipeline
from cli import simplify_text_input
from cli.render_simplified_model_report import render_simplified_model_report
from cli.solve_pseudospin_orbital_pipeline import solve_from_parsed_payload


def _structured_matrix(matrix):
    matrix = np.asarray(matrix, dtype=float)
    return {"shape": list(matrix.shape), "data": matrix.tolist()}


def _asymmetric_lattice_term_payload():
    c4 = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=int)
    return {
        "schema_version": "lattice-term-contract/v1",
        "local_hilbert": {
            "operator_bases": {
                "operator-basis:spin": {"kind": "spin_vector", "labels": ["Sx", "Sy", "Sz"]}
            },
            "classical_spaces": {
                "classical-space:spin": {"kind": "unit_vector_sphere", "dimension": 3}
            },
        },
        "lattice_structure": {
            "lattice_vectors": np.eye(3).tolist(),
            "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
            "bond_orbits": [],
        },
        "symmetry": {
            "source": {"international_symbol": "P4", "number": 75},
            "operations": [
                {
                    "operation_ref": f"symop:c4^{power}",
                    "rotation": np.linalg.matrix_power(c4, power).tolist(),
                    "translation": [0.0, 0.0, 0.0],
                }
                for power in range(4)
            ],
            "unresolved": [],
        },
        "term_attachments": {
            "site_terms": [],
            "bond_terms": [
                {
                    "term_ref": "term:Jx",
                    "cluster": [
                        {"site": 0, "translation": [0, 0, 0]},
                        {"site": 0, "translation": [1, 0, 0]},
                    ],
                    "operator_basis_ref": "operator-basis:spin",
                    "operator_channel": "spin_exchange",
                    "payload": {
                        "kind": "bilinear_exchange_matrix",
                        "matrix": _structured_matrix(np.diag([1.0, 2.0, 3.0])),
                    },
                    "attach_to": {"kind": "explicit_cluster", "orientation": "explicit"},
                }
            ],
            "higher_body_terms": [],
            "term_sets": [],
        },
        "solver_request": {"task": "classical_ground_state", "symmetry_repair": False},
        "parameters": {},
    }


def test_strict_failure_returns_before_solver_core(tmp_path):
    with patch(
        "cli.solve_pseudospin_orbital_pipeline._solve_from_parsed_payload_core"
    ) as solver_core:
        result = solve_from_parsed_payload(
            _asymmetric_lattice_term_payload(),
            output_dir=tmp_path / "out",
            docs_dir=tmp_path / "docs",
            compile_pdf=False,
            symmetry_repair=False,
        )

    assert result["status"] == "error"
    assert result["completion"]["reason"] == "hamiltonian-symmetry-validation-failed"
    assert result["solver_execution"] == {"started": False, "backends_run": []}
    solver_core.assert_not_called()


def test_repair_routes_projected_model_and_binds_result_hash(tmp_path):
    with patch(
        "cli.solve_pseudospin_orbital_pipeline._solve_from_parsed_payload_core",
        return_value={"status": "ok", "solver": {"energy": -1.0}},
    ) as solver_core:
        result = solve_from_parsed_payload(
            _asymmetric_lattice_term_payload(),
            output_dir=tmp_path / "out",
            docs_dir=tmp_path / "docs",
            compile_pdf=False,
            symmetry_repair=True,
        )

    routed_model = solver_core.call_args.args[0]
    assert routed_model["schema_version"] == "canonical-hamiltonian/v1"
    assert len(routed_model["terms"]) == 2
    assert result["solver_model_hash"] == result["symmetry_validation_stamp"]["hamiltonian_hash"]
    assert result["warnings"][0]["code"] == "hamiltonian-symmetry-repaired"


def test_cpn_cli_forwards_symmetry_repair_flag(tmp_path, monkeypatch):
    parsed_path = tmp_path / "parsed.json"
    parsed_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "solve-cpn",
            "--parsed-payload",
            str(parsed_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--docs-dir",
            str(tmp_path / "docs"),
            "--symmetry-repair",
        ],
    )
    with patch.object(
        solve_cpn_payload_pipeline,
        "solve_from_parsed_payload",
        return_value={"status": "ok"},
    ) as solve:
        assert solve_cpn_payload_pipeline.main() == 0
    assert solve.call_args.kwargs["symmetry_repair"] is True


def test_poscar_hr_cli_forwards_symmetry_repair_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "solve-pseudospin",
            "--poscar",
            str(tmp_path / "POSCAR"),
            "--hr",
            str(tmp_path / "hr.dat"),
            "--output-dir",
            str(tmp_path / "out"),
            "--docs-dir",
            str(tmp_path / "docs"),
            "--symmetry-repair",
        ],
    )
    with patch.object(
        solve_pseudospin_orbital_pipeline,
        "solve_from_files",
        return_value={"status": "ok"},
    ) as solve:
        assert solve_pseudospin_orbital_pipeline.main() == 0
    assert solve.call_args.kwargs["symmetry_repair"] is True


def test_text_cli_forwards_symmetry_repair_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["simplify-text", "--freeform", "J*S0.S1", "--symmetry-repair"],
    )
    with patch.object(
        simplify_text_input,
        "run_text_simplification_pipeline",
        return_value={"status": "ok"},
    ) as simplify:
        assert simplify_text_input.main() == 0
    assert simplify.call_args.kwargs["symmetry_repair"] is True


def test_report_explains_strict_failure_and_repair_opt_in():
    markdown = render_simplified_model_report(
        {
            "status": "error",
            "stage": "hamiltonian_symmetry_gate",
            "completion": {"reason": "hamiltonian-symmetry-validation-failed"},
            "symmetry_validation": {
                "target_group": {"international_symbol": "P4", "operation_count": 4},
                "failed_operations": [{"operation_ref": "symop:c4"}],
                "input_hamiltonian_subgroup": {
                    "status": "verified-subgroup",
                    "operation_refs": ["symop:identity"],
                },
            },
            "hamiltonian_provenance": {
                "input_model": {"content_hash": "input-hash"},
                "solver_model": {"content_hash": "solver-hash"},
            },
            "warnings": [],
        }
    )

    assert "P4" in markdown
    assert "symop:c4" in markdown
    assert "input-hash" in markdown and "solver-hash" in markdown
    assert "--symmetry-repair" in markdown
