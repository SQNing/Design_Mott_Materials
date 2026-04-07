#!/usr/bin/env python3
from simplify.assemble_effective_model import assemble_effective_model
from simplify.canonicalize_terms import canonicalize_terms
from simplify.generate_simplifications import generate_candidates
from simplify.identify_readable_blocks import identify_readable_blocks


def _serialize_coefficient(value):
    if abs(float(value.imag)) <= 1e-12:
        return float(value.real)
    return {"real": float(value.real), "imag": float(value.imag)}


def _decomposition_terms(parsed_payload):
    terms = []
    for block in parsed_payload.get("bond_blocks", []):
        for item in block.get("coefficients", []):
            terms.append(
                {
                    "label": f"{item['left_label']}@0 {item['right_label']}@1",
                    "coefficient": _serialize_coefficient(
                        complex(item["coefficient"]["real"], item["coefficient"]["imag"])
                    ),
                }
            )
    return terms


def simplify_pseudospin_orbital_payload(parsed_payload, low_weight_threshold=0.1):
    decomposition = {"terms": _decomposition_terms(parsed_payload)}
    canonical_model = canonicalize_terms({"decomposition": decomposition})
    readable_model = identify_readable_blocks(canonical_model)
    effective_model = assemble_effective_model(readable_model, low_weight_threshold=low_weight_threshold)
    simplification = generate_candidates({"effective_model": effective_model})
    return {
        "decomposition": decomposition,
        "canonical_model": canonical_model,
        "readable_model": readable_model,
        "effective_model": effective_model,
        "simplification": simplification,
    }
