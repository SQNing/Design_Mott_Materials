#!/usr/bin/env python3
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simplify.compile_onsite_term_to_matrix import compile_onsite_term_to_matrix
    from simplify.compile_operator_bond_to_matrix import compile_operator_bond_to_matrix
    from simplify.local_matrix_record import LocalMatrixRecordError, build_local_matrix_record
else:
    from .compile_onsite_term_to_matrix import compile_onsite_term_to_matrix
    from .compile_operator_bond_to_matrix import compile_operator_bond_to_matrix
    from .local_matrix_record import LocalMatrixRecordError, build_local_matrix_record


class LocalMatrixCompilationError(ValueError):
    pass


def _coordinate_frame(normalized):
    convention = dict(normalized.get("coordinate_convention", {}))
    return convention.get("frame") or "unspecified"


def _local_basis_order(local_dimension):
    spin = (int(local_dimension) - 1) / 2
    values = [spin - index for index in range(int(local_dimension))]
    formatted = []
    for value in values:
        if float(value).is_integer():
            formatted.append(f"m={int(value)}")
        else:
            formatted.append(f"m={value}")
    return formatted


def compile_local_term_to_matrix(normalized):
    support = list(normalized["local_term"]["support"])
    representation = normalized["local_term"]["representation"]
    local_dimension = int(normalized["local_hilbert"]["dimension"])
    parameters = dict(normalized.get("parameters", {}))
    coordinate_frame = _coordinate_frame(normalized)

    if len(support) > 2:
        raise LocalMatrixCompilationError("current phase only supports body_order <= 2")

    try:
        if representation["kind"] == "matrix":
            matrix = representation["value"]
        elif representation["kind"] == "operator" and len(support) == 1:
            matrix = compile_onsite_term_to_matrix(
                representation["value"],
                local_dimension=local_dimension,
                parameters=parameters,
            )
        elif representation["kind"] == "operator" and len(support) == 2:
            matrix = compile_operator_bond_to_matrix(
                representation["value"],
                local_dimension=local_dimension,
                parameters=parameters,
            )
        else:
            raise LocalMatrixCompilationError("unsupported local-term representation for matrix compilation")

        record = build_local_matrix_record(
            support=support,
            family=normalized.get("selected_local_bond_family") if len(support) == 2 else None,
            geometry_class="bond" if len(support) == 2 else "onsite",
            coordinate_frame=coordinate_frame,
            local_basis_order=_local_basis_order(local_dimension),
            tensor_product_order=support,
            matrix=matrix,
            provenance={
                "source_kind": "operator_text" if representation["kind"] == "operator" else "matrix_form",
                "source_expression": representation.get("value"),
                "parameter_map": parameters,
            },
        )
    except LocalMatrixRecordError as exc:
        raise LocalMatrixCompilationError(str(exc)) from exc
    except ValueError as exc:
        raise LocalMatrixCompilationError(str(exc)) from exc

    return record
