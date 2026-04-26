#!/usr/bin/env python3


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _local_indexes_from_pair_basis_index(pair_basis_index, local_dimension):
    pair_basis_index = int(pair_basis_index)
    local_dimension = int(local_dimension)
    return pair_basis_index // local_dimension, pair_basis_index % local_dimension


def _orbital_index_from_local_index(local_index, local_space_spec):
    _require(
        str(local_space_spec.get("kind")) == "orbital_times_spin",
        "automatic structure inference currently requires orbital_times_spin local space",
    )
    spin_dimension = int(local_space_spec.get("spin_dimension", 0))
    _require(spin_dimension > 0, "spin_dimension must be positive")
    return int(local_index) // spin_dimension


def _pair_identity_for_entry(entry, mapping, local_space_spec):
    local_dimension = int(local_space_spec.get("local_dimension", 0))
    _require(local_dimension > 0, "local_dimension must be positive")
    owner_by_orbital = dict(mapping.get("orbital_owner_by_index") or {})

    left_bra, right_bra = _local_indexes_from_pair_basis_index(entry["m"], local_dimension)
    left_ket, right_ket = _local_indexes_from_pair_basis_index(entry["n"], local_dimension)
    source_bra = owner_by_orbital[_orbital_index_from_local_index(left_bra, local_space_spec)]
    target_bra = owner_by_orbital[_orbital_index_from_local_index(right_bra, local_space_spec)]
    source_ket = owner_by_orbital[_orbital_index_from_local_index(left_ket, local_space_spec)]
    target_ket = owner_by_orbital[_orbital_index_from_local_index(right_ket, local_space_spec)]

    _require(
        source_bra == source_ket and target_bra == target_ket,
        "cannot infer a unique site pair",
    )
    return int(source_bra), int(target_bra)


def infer_many_body_hr_pair_identity_from_structure(structure, hamiltonian, mapping, local_space_spec):
    pair_records = {}
    for entry in list(hamiltonian.get("entries") or []):
        source, target = _pair_identity_for_entry(entry, mapping, local_space_spec)
        translation = tuple(int(value) for value in entry["R"])
        key = (source, target, translation)
        pair_records.setdefault(key, []).append(int(entry["row_index"]))

    normalized_records = []
    for source, target, translation in sorted(pair_records):
        normalized_records.append(
            {
                "source": int(source),
                "target": int(target),
                "translation": [int(value) for value in translation],
                "entry_refs": sorted(pair_records[(source, target, translation)]),
            }
        )

    return {
        "schema_version": 1,
        "pair_identity_provider": "structure+orbital-mapping",
        "site_pair_encoding": "explicit-source-target",
        "coordinate_convention": "global_crystallographic",
        "hr_binding": {
            "num_wann": int(hamiltonian["num_wann"]),
            "nrpts": int(hamiltonian["nrpts"]),
            "R_vectors": [list(R) for R in hamiltonian["R_vectors"]],
            "comment": hamiltonian.get("comment"),
        },
        "pair_records": normalized_records,
    }
