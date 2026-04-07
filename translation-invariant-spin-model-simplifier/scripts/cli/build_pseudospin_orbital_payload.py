#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from input.parse_many_body_hr import parse_many_body_hr_file
from input.parse_poscar import parse_poscar_file
from simplify.project_pseudospin_orbital_basis import (
    infer_local_dimension_from_num_wann,
    infer_orbital_count,
    project_two_site_bond_matrix,
)


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def build_pseudospin_orbital_payload(poscar_path, hr_path, coefficient_tolerance=1e-10):
    structure = parse_poscar_file(poscar_path)
    hamiltonian = parse_many_body_hr_file(hr_path)

    local_dimension = infer_local_dimension_from_num_wann(hamiltonian["num_wann"])
    orbital_count = infer_orbital_count(local_dimension)

    bond_blocks = []
    for R in hamiltonian["R_vectors"]:
        projected = project_two_site_bond_matrix(
            hamiltonian["blocks_by_R"][R],
            orbital_count=orbital_count,
            coefficient_tolerance=coefficient_tolerance,
        )
        bond_blocks.append(
            {
                "R": list(R),
                "matrix_shape": list(hamiltonian["blocks_by_R"][R].shape),
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
        "input_mode": "many_body_hr",
        "basis_semantics": {
            "local_space": "pseudospin_orbital",
        },
        "basis_order": "orbital_major_spin_minor",
        "structure": structure,
        "hamiltonian": {
            "comment": hamiltonian["comment"],
            "num_wann": hamiltonian["num_wann"],
            "nrpts": hamiltonian["nrpts"],
            "degeneracies": hamiltonian["degeneracies"],
        },
        "inferred": {
            "local_dimension": local_dimension,
            "orbital_count": orbital_count,
            "two_site_dimension": hamiltonian["num_wann"],
            "site_count_assumption": 2,
        },
        "bond_blocks": bond_blocks,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    args = parser.parse_args()

    payload = build_pseudospin_orbital_payload(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        coefficient_tolerance=float(args.coefficient_tolerance),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
