#!/usr/bin/env python3

from copy import deepcopy


def _require_dict(payload):
    if not isinstance(payload, dict):
        raise ValueError("cpn-pair-model-payload-must-be-dict")


def _matrix_shape(matrix):
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    return [rows, cols]


def _validate_serialized_matrix(matrix, *, expected_shape, error_code):
    if not isinstance(matrix, list):
        raise ValueError(error_code)
    actual_shape = _matrix_shape(matrix)
    if actual_shape != list(expected_shape):
        raise ValueError(error_code)


def _structured_complex(value):
    if isinstance(value, dict) and value.get("kind") == "complex":
        return dict(value)
    if isinstance(value, dict):
        return {
            "kind": "complex",
            "re": float(value.get("real", value.get("re", 0.0))),
            "im": float(value.get("imag", value.get("im", 0.0))),
        }
    return {"kind": "complex", "re": float(value), "im": 0.0}


def _structured_pair_matrix(matrix):
    rows = list(matrix or [])
    return {
        "storage": "dense",
        "shape": [len(rows), len(rows[0]) if rows else 0],
        "scalar_type": "complex_parameter_expression",
        "data": [[_structured_complex(value) for value in row] for row in rows],
    }


def _retained_local_hilbert(payload):
    local_dimension = int(payload.get("local_dimension", 0))
    basis_labels = list(payload.get("local_basis_labels") or [f"state:{index}" for index in range(local_dimension)])
    basis_semantics = dict(payload.get("basis_semantics") or {})
    return {
        "sites": [
            {
                "site_ref": "site:0",
                "space_ref": "space:retained_local",
                "basis_ref": "basis:retained_local",
                "classical_space_ref": "classical_space:cpn_local_ray",
                "operator_basis_refs": ["op_basis:retained_local_matrix"],
            },
            {
                "site_ref": "site:1",
                "space_ref": "space:retained_local",
                "basis_ref": "basis:retained_local",
                "classical_space_ref": "classical_space:cpn_local_ray",
                "operator_basis_refs": ["op_basis:retained_local_matrix"],
            },
        ],
        "basis_registry": {
            "basis:retained_local": {
                "kind": "retained_local_basis",
                "dimension": local_dimension,
                "basis_order": basis_labels,
                "basis_semantics": basis_semantics,
            }
        },
        "operator_bases": {
            "op_basis:retained_local_matrix": {
                "kind": "dense_local_matrix_units",
                "dimension": local_dimension,
            }
        },
        "classical_spaces": {
            "classical_space:cpn_local_ray": {
                "kind": "complex_projective_space",
                "dimension": local_dimension,
            }
        },
    }


def _orbit_ref_for_bond_term(index):
    return f"bond_orbit:retained_pair_{index}"


def _lattice_structure_from_bond_terms(bond_terms):
    bond_orbits = []
    for index, term in enumerate(list(bond_terms or [])):
        translation = [int(value) for value in list(term.get("translation") or [0, 0, 0])]
        source = int(term.get("source", 0))
        target = int(term.get("target", 0))
        bond_orbits.append(
            {
                "orbit_ref": _orbit_ref_for_bond_term(index),
                "kind": "pair",
                "directed": True,
                "representative": {"source": source, "target": target, "translation": translation},
                "members": [{"source": source, "target": target, "translation": translation}],
                "source_labels": [str(term.get("orbit", _orbit_ref_for_bond_term(index)))],
                "reverse_orientation": {
                    "kind": "swap_tensor_factors_then_adjoint",
                    "source_target_swap": True,
                    "translation": [-component for component in translation],
                },
            }
        )
    return {
        "basis_sites": [{"site_ref": "site:0"}, {"site_ref": "site:1"}],
        "bond_orbits": bond_orbits,
        "higher_body_orbits": [],
    }


def _term_attachments_from_bond_terms(payload):
    local_basis_refs = ["basis:retained_local", "basis:retained_local"]
    bond_terms = []
    candidate_terms = []
    for index, term in enumerate(list(payload.get("bond_terms") or [])):
        term_ref = f"term:retained_pair_{index}"
        orbit_ref = _orbit_ref_for_bond_term(index)
        attachment = {
            "term_ref": term_ref,
            "support_ref": [f"site:{int(term.get('source', 0))}", f"site:{int(term.get('target', 0))}"],
            "attach_to": {"kind": "bond_orbit", "orbit_ref": orbit_ref, "orientation": "representative"},
            "operator_basis_ref": "op_basis:retained_local_matrix",
            "channel_kind": "two_body",
            "operator_channel": "pair_matrix",
            "readable_block_kind": "pair_matrix",
            "payload": {
                "kind": "pair_matrix",
                "local_basis_refs": list(local_basis_refs),
                "tensor_product_order": {
                    "kind": "left_major_right_minor",
                    "left_site_role": "source",
                    "right_site_role": "target",
                },
                "pair_identity": {
                    "status": "verified",
                    "provider": str(payload.get("pair_identity_provider") or "many_body_hr_pair_identity_sidecar"),
                    "basis_order_status": "matched",
                },
                "matrix": _structured_pair_matrix(term.get("pair_matrix")),
                "orientation_transform": "swap_tensor_factors_then_adjoint",
            },
            "provenance": {"entry_refs": list(term.get("entry_refs") or [])},
        }
        bond_terms.append(attachment)
        candidate_terms.append(deepcopy(attachment))
    term_refs = [term["term_ref"] for term in bond_terms]
    orbit_refs = [term["attach_to"]["orbit_ref"] for term in bond_terms]
    return {
        "site_terms": [],
        "bond_terms": bond_terms,
        "higher_body_terms": [],
        "candidate_terms": candidate_terms,
        "term_sets": [
            {
                "term_set_ref": "term_set:all_retained_local_pair_matrices",
                "selection_mode": "all_compatible",
                "term_refs": term_refs,
                "bond_orbit_refs": orbit_refs,
            }
        ]
        if bond_terms
        else [],
    }


def _attach_lattice_term_contract(normalized):
    bond_terms = list(normalized.get("bond_terms") or [])
    normalized["schema_version"] = "lattice-term-contract/v1"
    normalized["local_hilbert"] = _retained_local_hilbert(normalized)
    normalized["lattice_structure"] = _lattice_structure_from_bond_terms(bond_terms)
    normalized["symmetry"] = {"operations": [], "spin_space_rotations": [], "local_frame_actions": []}
    normalized["term_attachments"] = _term_attachments_from_bond_terms(normalized)
    normalized["solver_request"] = {
        "task": "classical_ground_state",
        "preferred_methods": ["auto"],
        "outputs": ["classical_state"],
        "selected_term_set_ref": (
            normalized["term_attachments"]["term_sets"][0]["term_set_ref"]
            if normalized["term_attachments"]["term_sets"]
            else None
        ),
        "selected_term_refs": [],
        "selected_bond_orbit_refs": [],
        "selection_policy": "term_set_then_explicit_refs",
    }
    normalized.setdefault("parameters", {})
    normalized.setdefault("provenance", {})
    return normalized


def normalize_cpn_pair_model(payload):
    _require_dict(payload)
    normalized = deepcopy(payload)
    normalized.setdefault("schema_version", 1)
    normalized.setdefault("model_bond_label", "cpn_pair_model")
    normalized.setdefault("classical_bond_label", "cpn")
    normalized.setdefault("onsite_terms", [])
    normalized.setdefault("bond_terms", [])
    normalized.setdefault("pair_operator_convention", {})
    normalized["pair_operator_convention"].setdefault("representation", "pair_matrix")
    normalized["pair_operator_convention"].setdefault("pair_basis_order", "site_i_major_site_j_minor")
    normalized["pair_operator_convention"].setdefault(
        "tensor_view",
        {
            "kind": "K_ab_cd",
            "index_order": ["left_bra", "right_bra", "left_ket", "right_ket"],
        },
    )
    normalized.setdefault("provenance", {})
    return _attach_lattice_term_contract(normalized)


def validate_cpn_pair_model(payload):
    _require_dict(payload)
    if str(payload.get("model_bond_label")) != "cpn_pair_model":
        raise ValueError("unsupported-model-bond_label")
    if str(payload.get("classical_bond_label")) != "cpn":
        raise ValueError("unsupported-classical-bond_label")

    local_dimension = int(payload.get("local_dimension", 0))
    if local_dimension <= 0:
        raise ValueError("invalid-local-dimension")

    pair_operator_convention = dict(payload.get("pair_operator_convention") or {})
    if str(pair_operator_convention.get("pair_basis_order")) != "site_i_major_site_j_minor":
        raise ValueError("unsupported-pair-basis-order")

    bond_terms = list(payload.get("bond_terms") or [])
    expected_pair_shape = [local_dimension * local_dimension, local_dimension * local_dimension]
    for term in bond_terms:
        if not isinstance(term, dict):
            raise ValueError("bond-term-must-be-dict")
        if "source" not in term or "target" not in term or "translation" not in term:
            raise ValueError("bond-term-missing-site-identity")
        translation = list(term.get("translation") or [])
        if len(translation) != 3:
            raise ValueError("bond-term-translation-must-have-length-3")
        matrix_shape = list(term.get("matrix_shape") or [])
        if matrix_shape and matrix_shape != expected_pair_shape:
            raise ValueError("pair-matrix-dimension-mismatch")
        _validate_serialized_matrix(
            term.get("pair_matrix"),
            expected_shape=expected_pair_shape,
            error_code="pair-matrix-dimension-mismatch",
        )

    onsite_terms = list(payload.get("onsite_terms") or [])
    for term in onsite_terms:
        if not isinstance(term, dict):
            raise ValueError("onsite-term-must-be-dict")
        if term.get("kind") != "local_operator_matrix":
            continue
        matrix = term.get("payload", {}).get("matrix")
        _validate_serialized_matrix(
            matrix,
            expected_shape=[local_dimension, local_dimension],
            error_code="onsite-matrix-dimension-mismatch",
        )

    return payload
