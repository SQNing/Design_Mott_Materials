#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from common.canonicalize_pseudospin_bond_orbits import canonicalize_pseudospin_bond_blocks
from common.cpn_pair_model import normalize_cpn_pair_model
from common.infer_many_body_hr_pair_identity_from_structure import infer_many_body_hr_pair_identity_from_structure
from common.many_body_hr_orbital_to_atom_mapping import load_many_body_hr_orbital_to_atom_mapping
from common.many_body_hr_pair_identity_sidecar import load_many_body_hr_pair_identity_sidecar
from input.parse_many_body_hr import parse_many_body_hr_file
from input.parse_poscar import parse_poscar_file, parse_structure_file
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


def _serialize_raw_hr_entries(entries):
    serialized = []
    for entry in entries:
        serialized.append(
            {
                "row_index": int(entry["row_index"]),
                "R": [int(value) for value in entry["R"]],
                "m": int(entry["m"]),
                "n": int(entry["n"]),
                "value": _serialize_complex(entry["value"]),
            }
        )
    return serialized


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


def _explicit_magnetic_site_payload(structure, pair_records):
    positions = list(structure.get("positions", []))
    required_site_count = 0
    for record in pair_records:
        required_site_count = max(required_site_count, int(record["source"]) + 1, int(record["target"]) + 1)
    if positions:
        if len(positions) < required_site_count:
            raise ValueError("structure positions do not cover sidecar magnetic site indexes")
        magnetic_sites = [
            {
                "index": int(site_index),
                "label": f"site{site_index}",
                "position": [float(value) for value in positions[site_index]],
                "kind": "structure-site",
            }
            for site_index in range(required_site_count)
        ]
    else:
        magnetic_sites = [
            {
                "index": int(site_index),
                "label": f"site{site_index}",
                "position": None,
                "kind": "sidecar-site",
            }
            for site_index in range(required_site_count)
        ]

    return {
        "magnetic_site_count": int(required_site_count),
        "magnetic_sites": magnetic_sites,
        "magnetic_site_metadata": {
            "site_pair_encoding": "explicit-source-target",
            "coordinate_convention": "global_crystallographic",
            "pair_identity_provider": "sidecar",
        },
    }


def _retained_local_space_payload(local_space_spec, local_basis_labels, orbital_representation=None):
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
        if orbital_representation is not None:
            payload["orbital_representation"] = orbital_representation
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


def _load_structure_payload(structure_path):
    structure_path = Path(structure_path)
    lowered_name = structure_path.name.lower()
    if lowered_name in {"poscar", "contcar"} or structure_path.suffix.lower() == ".vasp":
        return parse_poscar_file(structure_path)
    return parse_structure_file(structure_path)


def _project_raw_bond_block(matrix, local_space_spec, coefficient_tolerance):
    projected = project_two_site_bond_matrix(
        matrix,
        coefficient_tolerance=coefficient_tolerance,
        local_space_mode=local_space_spec["mode"],
    )
    return {
        "operator_basis_labels": list(projected["operator_basis"]),
        "coefficients": [
            {
                "left_label": item["left_label"],
                "right_label": item["right_label"],
                "coefficient": _serialize_complex(item["coefficient"]),
            }
            for item in projected["coefficients"]
        ],
    }


def _build_pair_matrix_from_entry_refs(hamiltonian, entry_refs):
    matrix = hamiltonian["blocks_by_R"][tuple(hamiltonian["entries"][int(entry_refs[0])]["R"])].copy()
    matrix[:] = 0.0 + 0.0j
    entries = {int(entry["row_index"]): entry for entry in hamiltonian.get("entries", [])}
    for entry_ref in entry_refs:
        entry = entries[int(entry_ref)]
        matrix[int(entry["m"]), int(entry["n"])] = entry["value"]
    return matrix


def _build_bond_blocks_from_pair_records(hamiltonian, pair_records, local_space_spec, coefficient_tolerance):
    bond_blocks = []
    operator_basis_labels = None
    for record in pair_records:
        pair_matrix = _build_pair_matrix_from_entry_refs(hamiltonian, record["entry_refs"])
        projected = _project_raw_bond_block(pair_matrix, local_space_spec, coefficient_tolerance)
        if operator_basis_labels is None:
            operator_basis_labels = list(projected["operator_basis_labels"])
        bond_blocks.append(
            {
                "R": [int(value) for value in record["translation"]],
                "source": int(record["source"]),
                "target": int(record["target"]),
                "entry_refs": [int(value) for value in record["entry_refs"]],
                "matrix_shape": list(pair_matrix.shape),
                "pair_matrix": _serialize_matrix(pair_matrix),
                "coefficients": list(projected["coefficients"]),
            }
        )
    return bond_blocks, operator_basis_labels


def _canonical_bond_terms_from_blocks(bond_blocks):
    bond_terms = []
    for block in list(bond_blocks or []):
        term = {
            "source": int(block.get("source", 0)),
            "target": int(block.get("target", 0)),
            "translation": [int(value) for value in block["R"]],
            "matrix_shape": list(block["matrix_shape"]),
            "pair_matrix": block["pair_matrix"],
        }
        for optional_key in ("bond_label", "orbit", "orbit_members", "diagnostics", "entry_refs", "coefficients"):
            if optional_key in block:
                term[optional_key] = block[optional_key]
        bond_terms.append(term)
    return bond_terms


def build_pseudospin_orbital_payload(
    poscar_path,
    hr_path,
    coefficient_tolerance=1e-10,
    local_space_mode="generic-multiplet",
    pair_identity_sidecar_path=None,
    local_level_to_site_mapping_path=None,
):
    structure = _load_structure_payload(poscar_path)
    hamiltonian = parse_many_body_hr_file(hr_path)

    local_dimension = infer_local_dimension_from_num_wann(hamiltonian["num_wann"])
    local_space_spec = resolve_local_space_spec(local_dimension, local_space_mode=local_space_mode)
    local_basis_labels = build_local_basis_labels(local_space_spec)
    raw_hr_entries = list(hamiltonian.get("entries", []))

    bond_blocks = []
    operator_basis_labels = None
    mapping = None
    orbital_representation = None
    if local_level_to_site_mapping_path is not None:
        mapping = load_many_body_hr_orbital_to_atom_mapping(
            mapping_path=local_level_to_site_mapping_path,
            structure=structure,
            local_space_spec=local_space_spec,
        )
        orbital_representation = mapping.get("orbital_representation")

    if pair_identity_sidecar_path is not None:
        sidecar = load_many_body_hr_pair_identity_sidecar(
            sidecar_path=pair_identity_sidecar_path,
            hamiltonian=hamiltonian,
        )
        magnetic_site_payload = _explicit_magnetic_site_payload(structure, sidecar["pair_records"])
        bond_blocks, operator_basis_labels = _build_bond_blocks_from_pair_records(
            hamiltonian,
            sidecar["pair_records"],
            local_space_spec,
            coefficient_tolerance,
        )
        identity_level = "site_pair"
        pair_identity_status = "available"
        pair_identity_provider = "sidecar"
        pair_identity_source = "sidecar"
    elif mapping is not None:
        active_hamiltonian = {
            **hamiltonian,
            "entries": [
                entry
                for entry in list(hamiltonian.get("entries") or [])
                if abs(entry["value"]) > 0.0
            ],
        }
        inferred_pair_identity = infer_many_body_hr_pair_identity_from_structure(
            structure=structure,
            hamiltonian=active_hamiltonian,
            mapping=mapping,
            local_space_spec=local_space_spec,
        )
        magnetic_site_payload = _explicit_magnetic_site_payload(structure, inferred_pair_identity["pair_records"])
        bond_blocks, operator_basis_labels = _build_bond_blocks_from_pair_records(
            hamiltonian,
            inferred_pair_identity["pair_records"],
            local_space_spec,
            coefficient_tolerance,
        )
        identity_level = "site_pair"
        pair_identity_status = "available"
        pair_identity_provider = "structure+level-mapping"
        pair_identity_source = "structure+level-mapping"
    else:
        magnetic_site_payload = _default_magnetic_site_payload()
        entries_by_R = {}
        for entry in raw_hr_entries:
            entries_by_R.setdefault(tuple(entry["R"]), []).append(int(entry["row_index"]))

        for R in hamiltonian["R_vectors"]:
            pair_matrix = hamiltonian["blocks_by_R"][R]
            projected = _project_raw_bond_block(pair_matrix, local_space_spec, coefficient_tolerance)
            if operator_basis_labels is None:
                operator_basis_labels = list(projected["operator_basis_labels"])
            bond_blocks.append(
                {
                    "R": list(R),
                    "source": 0,
                    "target": 0,
                    "entry_refs": list(entries_by_R.get(tuple(R), [])),
                    "matrix_shape": list(pair_matrix.shape),
                    "pair_matrix": _serialize_matrix(pair_matrix),
                    "coefficients": list(projected["coefficients"]),
                }
            )
        identity_level = str(hamiltonian.get("identity_level", "unknown"))
        pair_identity_status = "available" if hamiltonian.get("pair_identity_available") else "unavailable"
        pair_identity_provider = None
        pair_identity_source = "available" if hamiltonian.get("pair_identity_available") else "unavailable"

    canonicalized = canonicalize_pseudospin_bond_blocks(structure, magnetic_site_payload, bond_blocks)

    payload = {
        "schema_version": 2,
        "model_bond_label": "cpn_pair_model",
        "input_mode": "many_body_hr",
        "classical_bond_label": "cpn",
        "local_dimension": int(local_space_spec["local_dimension"]),
        "identity_level": str(identity_level),
        "pair_identity_status": str(pair_identity_status),
        "pair_identity_provider": pair_identity_provider,
        "pair_identity_source": str(pair_identity_source),
        "basis_semantics": {
            "local_space": "pseudospin_orbital",
            "local_space_mode": str(local_space_spec["mode"]),
        },
        "basis_order": str(local_space_spec["basis_order"]),
        "pair_basis_order": str(local_space_spec["pair_basis_order"]),
        "local_basis_labels": local_basis_labels,
        "retained_local_space": _retained_local_space_payload(
            local_space_spec, local_basis_labels, orbital_representation
        ),
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
        "raw_hr_entries": _serialize_raw_hr_entries(raw_hr_entries),
        "canonicalization_status": canonicalized["canonicalization_status"],
        "raw_bond_blocks": canonicalized["raw_bond_blocks"],
        "bond_blocks": canonicalized["bond_blocks"],
        "bond_terms": _canonical_bond_terms_from_blocks(canonicalized["bond_blocks"]),
        "onsite_terms": [],
    }
    if "diagnostics" in canonicalized:
        payload["diagnostics"] = canonicalized["diagnostics"]
    return normalize_cpn_pair_model(payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poscar", required=True)
    parser.add_argument("--hr", required=True)
    parser.add_argument("--coefficient-tolerance", type=float, default=1e-10)
    parser.add_argument(
        "--local-space-mode",
        choices=["auto", "orbital-times-spin", "generic-multiplet"],
        default="generic-multiplet",
    )
    parser.add_argument("--pair-identity-sidecar")
    parser.add_argument("--local-level-to-site-mapping")
    args = parser.parse_args()

    payload = build_pseudospin_orbital_payload(
        poscar_path=Path(args.poscar),
        hr_path=Path(args.hr),
        coefficient_tolerance=float(args.coefficient_tolerance),
        local_space_mode=str(args.local_space_mode),
        pair_identity_sidecar_path=Path(args.pair_identity_sidecar) if args.pair_identity_sidecar else None,
        local_level_to_site_mapping_path=Path(args.local_level_to_site_mapping)
        if args.local_level_to_site_mapping
        else None,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
