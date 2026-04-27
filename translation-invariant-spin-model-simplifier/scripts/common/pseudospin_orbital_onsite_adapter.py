#!/usr/bin/env python3

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.onsite_terms import canonicalize_onsite_terms
else:
    from .onsite_terms import canonicalize_onsite_terms


def lower_pseudospin_orbital_onsite_terms(model, *, local_dimension):
    lowered = []
    onsite_terms = model.get("onsite_terms", [])
    if onsite_terms and all(isinstance(term, dict) and "site" in term and "matrix" in term for term in onsite_terms):
        for term in onsite_terms:
            matrix = [list(row) for row in term["matrix"]]
            lowered.append(
                {
                    "site": int(term["site"]),
                    "matrix_shape": [len(matrix), len(matrix[0]) if matrix else 0],
                    "matrix": matrix,
                }
            )
        return lowered

    for term in canonicalize_onsite_terms(onsite_terms, local_dimension=local_dimension):
        if term["kind"] != "local_operator_matrix":
            raise ValueError(f"unsupported pseudospin-orbital onsite term kind: {term['kind']!r}")
        scope = dict(term.get("site_scope", {}))
        if scope.get("kind") != "site":
            raise ValueError(f"unsupported pseudospin-orbital onsite site_scope: {scope.get('kind')!r}")
        matrix = [list(row) for row in term["payload"]["matrix"]]
        lowered.append(
            {
                "site": int(scope["site"]),
                "matrix_shape": [len(matrix), len(matrix[0]) if matrix else 0],
                "matrix": matrix,
            }
        )
    return lowered
