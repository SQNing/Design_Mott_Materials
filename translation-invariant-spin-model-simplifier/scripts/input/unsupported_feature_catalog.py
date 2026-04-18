#!/usr/bin/env python3

UNSUPPORTED_FEATURE_DETAILS = {
    "document_level_lattice_sum_notation": {
        "label": "document-level lattice-sum notation",
        "description": "document-level lattice sums such as \\sum_{<i,j>} or H_{ij}^{(n)} placeholders",
    },
    "bond_dependent_phase_gamma_terms": {
        "label": "bond-dependent phase factors",
        "description": "bond-dependent phase factors such as gamma_{ij} or gamma_{ij}^*",
    },
    "scalar_spin_chirality_terms": {
        "label": "scalar spin chirality terms",
        "description": "three-spin scalar chirality terms such as S_i·(S_j×S_k)",
    },
    "three_spin_chirality_terms": {
        "label": "three-spin chirality terms",
        "description": "three-spin chirality interactions that cannot yet land in the current payload families",
    },
    "operator_expression_decomposition_pending": {
        "label": "operator expressions outside the current decomposition route",
        "description": "operator expressions that still need projection or truncation before they can enter the explicit spin basis",
    },
}


def unsupported_feature_detail(feature):
    detail = UNSUPPORTED_FEATURE_DETAILS.get(str(feature), {})
    label = detail.get("label") or str(feature).replace("_", " ")
    description = detail.get("description") or label
    return {
        "feature": str(feature),
        "label": label,
        "description": description,
    }


def unsupported_feature_details(features):
    return [unsupported_feature_detail(feature) for feature in list(features or [])]
