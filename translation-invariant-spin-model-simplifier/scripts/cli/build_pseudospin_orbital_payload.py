#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from input.parse_many_body_hr import parse_many_body_hr_file
from input.parse_poscar import parse_poscar_file
from simplify.project_pseudospin_orbital_basis import (
    build_local_basis_labels,
    infer_local_dimension_from_num_wann,
    project_two_site_bond_matrix,
    resolve_local_space_spec,
)


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _serialize_matrix(matrix):
    return [[_serialize_complex(value) for value in row] for row in matrix]


def _default_magnetic_site_payload():
    return {
        "magnetic_site_count": 1,
        "magnetic_sites": [
            {
                "index": 0,
                "label": "site0",
                "position": None,
                "kind": "assumed-single-sublattice",
            }
        ],
        "magnetic_site_metadata": {
            "site_pair_encoding": "assumed-single-sublattice-many_body_hr",
            "explanation": (
                "many_body_hr currently encodes only an R-resolved two-site block and does not "
                "explicitly specify source/target magnetic-sublattice labels; the current parser "
                "therefore defaults to a single-sublattice interpretation unless richer site-pair "
                "metadata is provided by a future upstream parser"
            ),
        },
    }


def _retained_local_space_payload(local_space_spec, local_basis_labels):
    factorization = {"kind": str(local_space_spec["kind"])}
    if local_space_spec["kind"] == "orbital_times_spin":
        factorization["orbital_count"] = int(local_space_spec["orbital_count"])
        factorization["spin_dimension"] = int(local_space_spec["spin_dimension"])
        payload = {
            "dimension": int(local_space_spec["local_dimension"]),
            "factorization": factorization,
            "tensor_factor_order": str(local_space_spec["basis_order"]),
            "basis_labels": list(local_basis_labels),
        }
        return payload

    factorization["multiplet_dimension"] = int(local_space_spec["local_dimension"])
    return {
        "dimension": int(local_space_spec["local_dimension"]),
        "factorization": factorization,
        "basis_labels": list(local_basis_labels),
    }


def _operator_dictionary_payload(local_space_spec, operator_basis_labels):
    local_operator_basis = {
        "matrix_construction": str(local_space_spec["matrix_construction"]),
        "operator_basis_labels": list(operator_basis_labels),
    }
    payload = {
        "local_basis_kind": str(local_space_spec["local_basis_kind"]),
        "local_operator_basis": local_operator_basis,
    }
    if local_space_spec["kind"] == "orbital_times_spin":
        payload["tensor_factor_order"] = str(local_space_spec["basis_order"])
        local_operator_basis.update(
            {
                "spin_basis": "tau_mu / sqrt(2)",
                "orbital_basis": "Lambda_A with Tr(Lambda_A Lambda_B) = delta_AB",
                "product_basis": "Gamma_A_mu = orbital_A ⊗ spin_mu",
            }
        )
    else:
        local_operator_basis["generator_basis"] = "Hermitian orthonormal basis on the retained local multiplet"
    return payload


def _inferred_payload(local_space_spec, num_wann):
    payload = {
        "local_dimension": int(local_space_spec["local_dimension"]),
        "two_site_dimension": int(num_wann),
        "site_count_assumption": 2,
    }
    if local_space_spec["kind"] == "orbital_times_spin":
        payload["orbital_count"] = int(local_space_spec["orbital_count"])
    else:
        payload["multiplet_dimension"] = int(local_space_spec["local_dimension"])
    return payload


def build_pseudospin_orbital_payload(poscar_path, hr_path, coefficient_tolerance=1e-10, local_space_mode="auto"):
    structure = parse_poscar_file(poscar_path)
    hamiltonian = parse_many_body_hr_file(hr_path)

    local_dimension = infer_local_dimension_from_num_wann(hamiltonian["num_wann"])
    local_space_spec = resolve_local_space_spec(local_dimension, local_space_mode=local_space_mode)
    magnetic_site_payload = _default_magnetic_site_payload()
    local_basis_labels = build_local_basis_labels(local_space_spec)

    bond_blocks = []
    operator_basis_labels = None
    for R in hamiltonian["R_vectors"]:
        projected = project_two_site_bond_matrix(
            hamiltonian["blocks_by_R"][R],
            coefficient_tolerance=coefficient_tolerance,
            local_space_mode=local_space_spec["mode"],
        )
        if operator_basis_labels is None:
            operator_basis_labels = list(projected["operator_basis"])
        bond_blocks.append(
            {
                "R": list(R),
                "source": 0,
                "target": 0,
                "matrix_shape": list(hamiltonian["blocks_by_R"][R].shape),
                "pair_matrix": _serialize_matrix(hamiltonian["blocks_by_R"][R]),
                "coefficients": [
                    {
                        "left_label": item["left_label"],
                        "right_label": item["right_label"],
                        "coefficient": _serialize_complex(item["coefficient"]),
                    }
                    for item in projected["coefficients"]
                ],
            }
        )

    return {
        "schema_version": 2,
        "input_mode": "many_body_hr",
        "basis_semantics": {
            "local_space": "pseudospin_orbital",
            "local_space_mode": str(local_space_spec["mode"]),
        },
        "basis_order": str(local_space_spec["basis_order"]),
        "pair_basis_order": str(local_space_spec["pair_basis_order"]),
        "local_basis_labels": local_basis_labels,
        "retained_local_space": _retained_local_space_payload(local_space_spec, local_basis_labels),
        "pair_operator_convention": {
            "representation": "pair_matrix",
            "pair_basis_order": str(local_space_spec["pair_basis_order"]),
            "tensor_view": {
                "kind": "K_ab_cd",
                "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
            },
        },
        "operator_dictionary": _operator_dictionary_payload(local_space_spec, operator_basis_labels or []),
        "structure": structure,
        "hamiltonian": {
            "comment": hamiltonian["comment"],
            "num_wann": hamiltonian["num_wann"],
            "nrpts": hamiltonian["nrpts"],
            "degeneracies": hamiltonian["degeneracies"],
        },
        "inferred": _inferred_payload(local_space_spec, hamiltonian["num_wann"]),
        **magnetic_site_payload,
        "bond_blocks": bond_blocks,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    parser.add_argument(
        "--local-space-mode",
        choices=["auto", "orbital-times-spin", "generic-multiplet"],
        default="auto",
    )
    args = parser.parse_args()

    payload = build_pseudospin_orbital_payload(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        coefficient_tolerance=float(args.coefficient_tolerance),
        local_space_mode=str(args.local_space_mode),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
