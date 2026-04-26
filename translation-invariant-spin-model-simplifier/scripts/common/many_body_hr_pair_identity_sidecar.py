#!/usr/bin/env python3
import json
from pathlib import Path


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _normalized_r_vectors(vectors):
    return [tuple(int(value) for value in vector) for vector in list(vectors or [])]


def _normalized_entry_refs(entry_refs):
    return [int(value) for value in list(entry_refs or [])]


def validate_many_body_hr_pair_identity_sidecar(sidecar, hamiltonian):
    _require(int(sidecar.get("schema_version", -1)) == 1, "sidecar schema_version must be 1")
    _require(
        sidecar.get("pair_identity_provider") == "sidecar",
        "pair_identity_provider must be 'sidecar'",
    )
    _require(
        sidecar.get("site_pair_encoding") == "explicit-source-target",
        "site_pair_encoding must be 'explicit-source-target'",
    )
    _require(
        sidecar.get("coordinate_convention") == "global_crystallographic",
        "coordinate_convention must be 'global_crystallographic'",
    )

    hr_binding = dict(sidecar.get("hr_binding") or {})
    _require(int(hr_binding.get("num_wann", -1)) == int(hamiltonian["num_wann"]), "hr_binding.num_wann mismatch")
    _require(int(hr_binding.get("nrpts", -1)) == int(hamiltonian["nrpts"]), "hr_binding.nrpts mismatch")
    _require(
        _normalized_r_vectors(hr_binding.get("R_vectors")) == [tuple(R) for R in hamiltonian["R_vectors"]],
        "hr_binding.R_vectors mismatch",
    )

    entries_by_row_index = {int(entry["row_index"]): dict(entry) for entry in hamiltonian.get("entries", [])}
    expected_row_indexes = set(entries_by_row_index)

    normalized_records = []
    seen_entry_refs = set()
    duplicate_entry_refs = set()
    covered_entry_refs = set()
    for record in list(sidecar.get("pair_records") or []):
        entry_refs = _normalized_entry_refs(record.get("entry_refs"))
        _require(entry_refs, "pair_record.entry_refs must be non-empty")
        for entry_ref in entry_refs:
            _require(entry_ref in entries_by_row_index, f"unknown sidecar entry_ref: {entry_ref}")
            if entry_ref in seen_entry_refs:
                duplicate_entry_refs.add(entry_ref)
            seen_entry_refs.add(entry_ref)
            covered_entry_refs.add(entry_ref)

        referenced_R_values = {tuple(entries_by_row_index[entry_ref]["R"]) for entry_ref in entry_refs}
        _require(len(referenced_R_values) == 1, "pair_record mixes parser entries from multiple R values")
        parser_R = next(iter(referenced_R_values))
        translation = tuple(int(value) for value in list(record.get("translation") or []))
        _require(translation == parser_R, "translation does not match parser R")

        normalized_records.append(
            {
                "source": int(record.get("source", 0)),
                "target": int(record.get("target", 0)),
                "translation": [int(value) for value in translation],
                "entry_refs": entry_refs,
            }
        )

    _require(not duplicate_entry_refs, "duplicate sidecar entry_ref ownership")
    missing_entry_refs = sorted(expected_row_indexes - covered_entry_refs)
    _require(not missing_entry_refs, f"missing sidecar coverage for entry_refs: {missing_entry_refs}")
    unexpected_entry_refs = sorted(covered_entry_refs - expected_row_indexes)
    _require(not unexpected_entry_refs, f"unknown sidecar entry_refs: {unexpected_entry_refs}")

    return {
        "schema_version": 1,
        "pair_identity_provider": "sidecar",
        "site_pair_encoding": "explicit-source-target",
        "coordinate_convention": "global_crystallographic",
        "hr_binding": {
            "num_wann": int(hamiltonian["num_wann"]),
            "nrpts": int(hamiltonian["nrpts"]),
            "R_vectors": [list(R) for R in hamiltonian["R_vectors"]],
            "comment": hr_binding.get("comment"),
        },
        "pair_records": normalized_records,
    }


def load_many_body_hr_pair_identity_sidecar(sidecar_path, hamiltonian):
    sidecar_path = Path(sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    return validate_many_body_hr_pair_identity_sidecar(sidecar, hamiltonian)
