#!/usr/bin/env python3


class LocalMatrixRecordError(ValueError):
    pass


def _ensure_required(name, value):
    if value is None:
        raise LocalMatrixRecordError(f"missing required field: {name}")


def build_local_matrix_record(
    *,
    support,
    family=None,
    body_order=None,
    geometry_class=None,
    coordinate_frame=None,
    local_basis_order=None,
    tensor_product_order=None,
    matrix=None,
    provenance=None,
):
    _ensure_required("support", support)
    _ensure_required("geometry_class", geometry_class)
    _ensure_required("coordinate_frame", coordinate_frame)
    _ensure_required("local_basis_order", local_basis_order)
    _ensure_required("tensor_product_order", tensor_product_order)
    _ensure_required("matrix", matrix)
    _ensure_required("provenance", provenance)

    support_list = list(support)
    resolved_body_order = len(support_list) if body_order is None else int(body_order)
    if resolved_body_order != len(support_list):
        raise LocalMatrixRecordError("body_order must match support size")
    if resolved_body_order > 2:
        raise LocalMatrixRecordError("current phase only supports body_order <= 2")
    if resolved_body_order == 2 and family is None:
        raise LocalMatrixRecordError("family is required for two-body local matrix records")

    return {
        "support": support_list,
        "body_order": resolved_body_order,
        "family": family,
        "geometry_class": str(geometry_class),
        "coordinate_frame": str(coordinate_frame),
        "local_basis_order": list(local_basis_order),
        "tensor_product_order": list(tensor_product_order),
        "representation": {
            "kind": "matrix",
            "value": matrix,
        },
        "provenance": dict(provenance),
    }
