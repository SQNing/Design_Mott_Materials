#!/usr/bin/env python3

from pathlib import Path
import sys

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.onsite_terms import canonicalize_onsite_terms, linear_spin_cartesian_operator_matrix
else:
    from .onsite_terms import canonicalize_onsite_terms, linear_spin_cartesian_operator_matrix


def lower_spin_only_onsite_terms(model, *, site_count=None):
    lowered = []
    for term in canonicalize_onsite_terms(model.get("onsite_terms", [])):
        kind = term["kind"]
        if kind not in {"quadratic_spin_cartesian", "linear_spin_cartesian"}:
            raise ValueError(f"unsupported spin-only onsite term kind: {term['kind']!r}")
        scope = dict(term.get("site_scope", {}))
        if scope.get("kind") != "site":
            raise ValueError(f"unsupported spin-only onsite site_scope: {scope.get('kind')!r}")
        site = int(scope["site"])
        if site_count is not None and (site < 0 or site >= int(site_count)):
            raise ValueError("spin-only onsite term site falls outside the model site count")
        if kind == "quadratic_spin_cartesian":
            lowered.append({"kind": kind, "site": site, "matrix": [list(row) for row in term["payload"]["matrix"]]})
        else:
            lowered.append({"kind": kind, "site": site, "vector": [float(value) for value in term["payload"]["vector"]]})
    return lowered


def spin_only_onsite_matrices_by_site(model, *, site_count=None):
    lowered = lower_spin_only_onsite_terms(model, site_count=site_count)
    by_site = {}
    for term in lowered:
        if term["kind"] != "quadratic_spin_cartesian":
            continue
        matrix = np.array(term["matrix"], dtype=float)
        site = int(term["site"])
        if site in by_site:
            by_site[site] = by_site[site] + matrix
        else:
            by_site[site] = matrix
    return by_site


def spin_only_onsite_field_vectors_by_site(model, *, site_count=None):
    lowered = lower_spin_only_onsite_terms(model, site_count=site_count)
    by_site = {}
    for term in lowered:
        if term["kind"] != "linear_spin_cartesian":
            continue
        vector = np.array(term["vector"], dtype=float)
        site = int(term["site"])
        if site in by_site:
            by_site[site] = by_site[site] + vector
        else:
            by_site[site] = vector
    return by_site


def spin_only_onsite_operator_matrices_by_site(model, *, local_dimension, site_count=None):
    lowered = lower_spin_only_onsite_terms(model, site_count=site_count)
    by_site = {}
    for term in lowered:
        site = int(term["site"])
        if term["kind"] == "quadratic_spin_cartesian":
            matrix = np.array(term["matrix"], dtype=complex)
        elif term["kind"] == "linear_spin_cartesian":
            if local_dimension is None:
                raise ValueError("linear spin-only onsite terms require local_dimension")
            matrix = np.array(
                linear_spin_cartesian_operator_matrix(term["vector"], local_dimension=local_dimension),
                dtype=complex,
            )
        else:
            continue
        if site in by_site:
            by_site[site] = by_site[site] + matrix
        else:
            by_site[site] = matrix
    return by_site
