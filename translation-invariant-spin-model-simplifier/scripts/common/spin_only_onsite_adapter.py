#!/usr/bin/env python3

from pathlib import Path
import sys

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.onsite_terms import canonicalize_onsite_terms
else:
    from .onsite_terms import canonicalize_onsite_terms


def lower_spin_only_onsite_terms(model, *, site_count=None):
    lowered = []
    for term in canonicalize_onsite_terms(model.get("onsite_terms", [])):
        if term["kind"] != "quadratic_spin_cartesian":
            raise ValueError(f"unsupported spin-only onsite term kind: {term['kind']!r}")
        scope = dict(term.get("site_scope", {}))
        if scope.get("kind") != "site":
            raise ValueError(f"unsupported spin-only onsite site_scope: {scope.get('kind')!r}")
        site = int(scope["site"])
        if site_count is not None and (site < 0 or site >= int(site_count)):
            raise ValueError("spin-only onsite term site falls outside the model site count")
        lowered.append({"site": site, "matrix": [list(row) for row in term["payload"]["matrix"]]})
    return lowered


def spin_only_onsite_matrices_by_site(model, *, site_count=None):
    if site_count is None:
        lowered = lower_spin_only_onsite_terms(model)
    else:
        lowered = lower_spin_only_onsite_terms(model, site_count=site_count)
    by_site = {}
    for term in lowered:
        matrix = np.array(term["matrix"], dtype=float)
        site = int(term["site"])
        if site in by_site:
            by_site[site] = by_site[site] + matrix
        else:
            by_site[site] = matrix
    return by_site
