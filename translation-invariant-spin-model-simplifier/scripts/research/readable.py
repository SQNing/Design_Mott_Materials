"""Faithful readable views; the solver always receives the complete canonical model."""
from research.contracts import restore_complex


def faithful_view(model):
    from common.canonical_hamiltonian import pair_coefficient_representation
    from simplify.canonicalize_terms import canonicalize_terms
    from simplify.identify_readable_blocks import identify_readable_blocks
    from simplify.assemble_effective_model import assemble_effective_model
    view = {"view": "faithful-readable", "main": [], "low_weight": [], "residual": [],
            "terms": model.get("terms", []), "dropped_terms": [],
            "fidelity": {"assessment": "not_assessed", "reconstruction_error": None},
            "notes": ["Readable blocks are descriptions, not physical reductions.",
                      "Matrix-unit indices refer to the supplied local basis; no spin mapping is inferred."]}
    for term in model.get("terms", []):
        record = {"term_ref": term["term_ref"], "cluster": term["cluster"],
                  "coordinate_convention": term.get("coordinate_convention"),
                  "operator_family": term["operator_family"]}
        matrix = restore_complex(term["coefficient"])
        if term["operator_family"] in {"bilinear_exchange_matrix", "bilinear_exchange_tensor"}:
            labels = ("Sx", "Sy", "Sz")
            coefficients = [{"label": "%s@0 %s@1" % (labels[i], labels[j]), "coefficient": matrix[i][j]}
                            for i in range(3) for j in range(3) if matrix[i][j] != 0]
            canonical = canonicalize_terms({"terms": coefficients})
            readable = identify_readable_blocks(canonical)
            effective = assemble_effective_model(readable)
            for category in ("main", "low_weight", "residual"):
                for block in effective.get(category, []):
                    view[category].append({**record, "readable_block": block})
            if not any(effective.get(category) for category in ("main", "low_weight", "residual")):
                view["residual"].append({**record, "full_matrix": matrix})
        elif term["operator_family"] == "pair_matrix" and pair_coefficient_representation(term, model) != "full_pair_operator":
            view["residual"].append({**record, "coefficient_tensor": matrix,
                                      "interpretation": "coefficients in the declared local operator basis"})
        elif term["operator_family"] in {"pair_matrix", "local_operator_matrix"}:
            view["main"].append({**record, "readable_block": {
                "type": "retained_pair_operator" if term["arity"] == 2 else "retained_onsite_operator",
                "full_matrix": matrix,
                "matrix_elements": [{"bra": i, "ket": j, "coefficient": entry}
                                    for i, row in enumerate(matrix) for j, entry in enumerate(row) if entry != 0],
                "basis_order": "site_i_major_site_j_minor" if term["arity"] == 2 else "retained_state_index"}})
        else:
            view["residual"].append({**record, "full_canonical_term": term})
    return view
