#!/usr/bin/env python3

CANONICAL_LOCAL_SPACE = "pseudospin_orbital"
CANONICAL_BASIS_ORDER = "orbital_major_spin_minor"
CANONICAL_PAIR_BASIS_ORDER = "site_i_major_site_j_minor"
CANONICAL_LOCAL_BASIS_KIND = "orbital_times_spin"
CANONICAL_MATRIX_CONSTRUCTION = "kron(orbital, spin)"
CANONICAL_PAIR_TENSOR_INDEX_ORDER = ["left_bra", "right_bra", "left_ket", "right_ket"]


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _validate_equal(field_name, actual, expected):
    if actual is None:
        return
    if actual != expected:
        raise ValueError(f"{field_name} must be {expected!r}, got {actual!r}")


def resolve_pseudospin_orbital_conventions(payload, *, require_local_space=False):
    payload = _mapping(payload)

    basis_semantics = _mapping(payload.get("basis_semantics"))
    local_space = basis_semantics.get("local_space")
    if require_local_space:
        _validate_equal("basis_semantics.local_space", local_space, CANONICAL_LOCAL_SPACE)

    basis_order = payload.get("basis_order", CANONICAL_BASIS_ORDER)
    _validate_equal("basis_order", basis_order, CANONICAL_BASIS_ORDER)

    pair_basis_order = payload.get("pair_basis_order", CANONICAL_PAIR_BASIS_ORDER)
    _validate_equal("pair_basis_order", pair_basis_order, CANONICAL_PAIR_BASIS_ORDER)

    retained_local_space = _mapping(payload.get("retained_local_space"))
    factorization = _mapping(retained_local_space.get("factorization"))
    _validate_equal(
        "retained_local_space.tensor_factor_order",
        retained_local_space.get("tensor_factor_order"),
        CANONICAL_BASIS_ORDER,
    )
    _validate_equal(
        "retained_local_space.factorization.kind",
        factorization.get("kind"),
        CANONICAL_LOCAL_BASIS_KIND,
    )
    if factorization.get("spin_dimension") is not None:
        _validate_equal("retained_local_space.factorization.spin_dimension", int(factorization["spin_dimension"]), 2)

    pair_operator_convention = _mapping(payload.get("pair_operator_convention"))
    _validate_equal(
        "pair_operator_convention.pair_basis_order",
        pair_operator_convention.get("pair_basis_order"),
        CANONICAL_PAIR_BASIS_ORDER,
    )
    tensor_view = _mapping(pair_operator_convention.get("tensor_view"))
    if tensor_view.get("index_order") is not None:
        actual_index_order = list(tensor_view.get("index_order"))
        if actual_index_order != CANONICAL_PAIR_TENSOR_INDEX_ORDER:
            raise ValueError(
                "pair_operator_convention.tensor_view.index_order must be "
                f"{CANONICAL_PAIR_TENSOR_INDEX_ORDER!r}, got {actual_index_order!r}"
            )

    operator_dictionary = _mapping(payload.get("operator_dictionary"))
    _validate_equal(
        "operator_dictionary.local_basis_kind",
        operator_dictionary.get("local_basis_kind"),
        CANONICAL_LOCAL_BASIS_KIND,
    )
    _validate_equal(
        "operator_dictionary.tensor_factor_order",
        operator_dictionary.get("tensor_factor_order"),
        CANONICAL_BASIS_ORDER,
    )
    local_operator_basis = _mapping(operator_dictionary.get("local_operator_basis"))
    _validate_equal(
        "operator_dictionary.local_operator_basis.matrix_construction",
        local_operator_basis.get("matrix_construction"),
        CANONICAL_MATRIX_CONSTRUCTION,
    )

    return {
        "local_space": CANONICAL_LOCAL_SPACE,
        "basis_order": CANONICAL_BASIS_ORDER,
        "pair_basis_order": CANONICAL_PAIR_BASIS_ORDER,
        "local_basis_kind": CANONICAL_LOCAL_BASIS_KIND,
        "matrix_construction": CANONICAL_MATRIX_CONSTRUCTION,
        "pair_tensor_index_order": list(CANONICAL_PAIR_TENSOR_INDEX_ORDER),
    }
