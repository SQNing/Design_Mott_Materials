import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from classical.lt_fourier_exchange import fourier_exchange_matrix
from classical.build_spin_only_solver_payload import build_spin_only_solver_payload
from common.canonical_hamiltonian import canonical_model_hash
from common.hamiltonian_symmetry_gate import require_current_symmetry_stamp
from common.model_analysis import run_model_analysis
from common.solver_capability_registry import SolverCapabilityError, select_solver_capability


def _canonical_model(terms):
    model = {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": {
            "lattice_vectors": np.eye(3).tolist(),
            "basis_sites": [{"site_ref": "site:0", "position": [0.0, 0.0, 0.0]}],
        },
        "local_hilbert": {
            "classical_spaces": {
                "classical-space:spin": {"kind": "unit_vector_sphere", "dimension": 3}
            }
        },
        "symmetry": {
            "operations": [
                {
                    "operation_ref": "symop:identity",
                    "rotation": np.eye(3, dtype=int).tolist(),
                    "translation": [0.0, 0.0, 0.0],
                }
            ],
            "unresolved": [],
        },
        "terms": terms,
    }
    return model


def _stamp(model):
    return {
        "status": "passed",
        "hamiltonian_hash": canonical_model_hash(model),
    }


def test_bilinear_solver_rejects_validated_ring_exchange_without_truncation():
    model = _canonical_model(
        [
            {
                "term_ref": "term:ring",
                "arity": 4,
                "cluster": [
                    {"site": 0, "translation": translation}
                    for translation in ([0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0])
                ],
                "operator_family": "cyclic_ring_exchange",
                "coefficient": {"forward": 1.0, "inverse": 1.0},
            }
        ]
    )

    with pytest.raises(SolverCapabilityError, match="solver-capability-mismatch") as error:
        select_solver_capability(model)

    assert error.value.code == "solver-capability-mismatch"
    assert "term:ring" in str(error.value)
    assert "cyclic_ring_exchange" in str(error.value)


def test_tensor_fourier_analysis_reuses_existing_kernel_for_every_q():
    model = _canonical_model(
        [
            {
                "term_ref": "term:J",
                "arity": 2,
                "cluster": [
                    {"site": 0, "translation": [0, 0, 0]},
                    {"site": 0, "translation": [1, 0, 0]},
                ],
                "operator_family": "bilinear_exchange_tensor",
                "coefficient": np.diag([1.0, 2.0, 3.0]).tolist(),
                "coordinate_convention": "global_crystallographic",
                "orientation_sector": "default",
                "operator_basis_ref": "operator-basis:spin",
            }
        ]
    )
    q_points = [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]

    with patch(
        "common.model_analysis.fourier_exchange_matrix",
        wraps=fourier_exchange_matrix,
    ) as kernel:
        result = run_model_analysis(
            {
                "status": "ok",
                "solver_model": model,
                "symmetry_validation_stamp": _stamp(model),
            },
            {
                "task": "fourier_exchange_spectrum",
                "reduced_momenta": q_points,
                "observable": "exchange_eigenvalues",
            },
        )

    assert result["status"] == "ok"
    assert kernel.call_count == len(q_points)
    assert result["matrix_size"] == 3
    assert result["backend"]["function"] == "classical.lt_fourier_exchange.fourier_exchange_matrix"
    assert result["spectra"][0]["eigenvalues"] == pytest.approx([2.0, 4.0, 6.0])
    assert result["spectra"][1]["eigenvalues"] == pytest.approx([-6.0, -4.0, -2.0])


def test_fourier_analysis_rejects_stale_symmetry_stamp_before_kernel():
    model = _canonical_model([])
    stale = {"status": "passed", "hamiltonian_hash": "stale"}

    with patch("common.model_analysis.fourier_exchange_matrix") as kernel:
        with pytest.raises(Exception, match="symmetry-validation-stamp-stale"):
            run_model_analysis(
                {"status": "ok", "solver_model": model, "symmetry_validation_stamp": stale},
                {"task": "fourier_exchange_spectrum", "reduced_momenta": [[0.0, 0.0, 0.0]]},
            )
    kernel.assert_not_called()
    with pytest.raises(Exception, match="symmetry-validation-stamp-stale"):
        require_current_symmetry_stamp(model, stale)


def test_spin_solver_adapter_requires_current_stamp_for_canonical_model():
    model = _canonical_model(
        [
            {
                "term_ref": "term:J",
                "arity": 2,
                "cluster": [
                    {"site": 0, "translation": [0, 0, 0]},
                    {"site": 0, "translation": [1, 0, 0]},
                ],
                "operator_family": "bilinear_exchange_tensor",
                "coefficient": np.eye(3).tolist(),
            }
        ]
    )

    result = build_spin_only_solver_payload(
        {"solver_model": model, "symmetry_validation_stamp": _stamp(model)}
    )
    assert result["payload"]["bonds"] == [
        {
            "source": 0,
            "target": 0,
            "vector": [1, 0, 0],
            "term_ref": "term:J",
            "matrix": np.eye(3).tolist(),
        }
    ]
    assert result["payload"]["solver_model_hash"] == canonical_model_hash(model)

    with pytest.raises(Exception, match="symmetry-validation-stamp-stale"):
        build_spin_only_solver_payload(
            {
                "solver_model": model,
                "symmetry_validation_stamp": {"status": "passed", "hamiltonian_hash": "stale"},
            }
        )
