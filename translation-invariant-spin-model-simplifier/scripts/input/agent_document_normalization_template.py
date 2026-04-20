from copy import deepcopy


TEMPLATE_VERSION = "v1"


_TEMPLATE = {
    "source_document": {
        "source_kind": "agent_normalized_document",
        "source_path": "<copy-from-input-if-known>",
    },
    "model_candidates": [
        {"name": "<candidate-name>", "role": "<main|simplified|equivalent_form>"},
    ],
    "candidate_models": {
        "<candidate-name>": {
            "operator_expression": "<optional-single-expression>",
            "evidence_refs": ["<evidence-id>"],
            "confidence": "<low|medium|high>",
            "extraction_method": "<equation_block|table|prose|matrix_bridge>",
            "local_bond_candidates": [
                {
                    "family": "<family-label>",
                    "expression": "<bond-local operator expression>",
                    "evidence_refs": ["<evidence-id>"],
                },
            ],
            "matrix_form": False,
            "matrix_form_candidates": [
                {
                    "family": "<family-label>",
                    "expression": "<matrix-derived operator expression>",
                    "evidence_refs": ["<evidence-id>"],
                    "matrix": [
                        ["<xx>", "<xy>", "<xz>"],
                        ["<yx>", "<yy>", "<yz>"],
                        ["<zx>", "<zy>", "<zz>"],
                    ],
                },
            ],
        },
    },
    "parameter_registry": {
        "<parameter-name>": {
            "value": "<numeric-or-symbolic-value>",
            "units": "<optional-units>",
            "evidence_refs": ["<evidence-id>"],
            "confidence": "<low|medium|high>",
            "extraction_method": "<parameter_table|equation|prose>",
            "evidence_values": [
                {"evidence_ref": "<evidence-id>", "value": "<observed-value>", "units": "<observed-units>"},
            ],
        },
    },
    "system_context": {
        "coordinate_convention": {
            "status": "<unspecified|selected|explicit>",
            "frame": "<global_cartesian|global_crystallographic|local_bond|unspecified>",
            "axis_labels": ["x", "y", "z"],
        },
        "magnetic_order": {
            "status": "unspecified",
            "kind": "unspecified",
            "wavevector": [],
            "wavevector_units": None,
        },
        "coefficient_units": "<optional-units>",
    },
    "lattice_model": {},
    "evidence_items": [
        {"id": "<evidence-id>", "kind": "<equation|table_cell|prose>", "text": "<quoted source text>"},
    ],
    "unresolved_items": [
        {
            "field": "<field-name>",
            "reason": "<what is still ambiguous>",
            "policy": "<hard_gate|needs_unique_interpretation>",
        },
    ],
    "unsupported_features": [],
}


_EXAMPLE_PAYLOAD = {
    "source_document": {
        "source_kind": "agent_normalized_document",
        "source_path": "paper.tex",
    },
    "model_candidates": [
        {"name": "effective", "role": "main"},
        {"name": "matrix_form", "role": "equivalent_form"},
        {"name": "onsite_anisotropy", "role": "equivalent_form"},
    ],
    "candidate_models": {
        "effective": {
            "evidence_refs": ["eq1"],
            "confidence": "high",
            "extraction_method": "equation_block",
            "local_bond_candidates": [
                {
                    "family": "1",
                    "expression": "J_1^{zz} * Sz@0 Sz@1",
                    "evidence_refs": ["eq1"],
                }
            ]
        },
        "matrix_form": {
            "matrix_form": True,
            "local_bond_candidates": [
                {
                    "family": "1",
                    "expression": (
                        "J_1^{xx} * Sx@0 Sx@1 + J_1^{yy} * Sy@0 Sy@1 + "
                        "J_1^{zz} * Sz@0 Sz@1"
                    ),
                    "evidence_refs": ["eq2"],
                    "matrix": [
                        ["J_1^{xx}", "0", "0"],
                        ["0", "J_1^{yy}", "0"],
                        ["0", "0", "J_1^{zz}"],
                    ],
                }
            ],
        },
        "onsite_anisotropy": {
            "operator_expression": "D * (Sz@0)^2 + B_4^0 * (Sz@0)^4",
            "evidence_refs": ["eq3"],
            "confidence": "high",
            "extraction_method": "equation_block",
        },
    },
    "parameter_registry": {
        "D": {"value": 0.42, "evidence_refs": ["eq3"], "confidence": "high", "extraction_method": "equation"},
        "B_4^0": {"value": -0.018, "evidence_refs": ["eq3"], "confidence": "high", "extraction_method": "equation"},
        "J_1^{xx}": {"value": -0.397, "evidence_refs": ["tbl1"], "confidence": "high", "extraction_method": "parameter_table"},
        "J_1^{yy}": {"value": -0.075, "evidence_refs": ["tbl1"], "confidence": "high", "extraction_method": "parameter_table"},
        "J_1^{zz}": {"value": -0.236, "evidence_refs": ["tbl1"], "confidence": "high", "extraction_method": "parameter_table"},
    },
    "system_context": {
        "coordinate_convention": {
            "status": "selected",
            "frame": "global_cartesian",
            "axis_labels": ["x", "y", "z"],
        },
        "magnetic_order": {
            "status": "unspecified",
            "kind": "unspecified",
            "wavevector": [],
            "wavevector_units": None,
        },
        "coefficient_units": "meV",
    },
    "lattice_model": {},
    "evidence_items": [
        {"id": "eq1", "kind": "equation", "text": "H_{ij}^{(1)} = J_1^{zz} S_i^z S_j^z"},
        {"id": "eq2", "kind": "equation", "text": "\\mathcal J_{ij}^{(1)} = \\mathrm{diag}(J_1^{xx}, J_1^{yy}, J_1^{zz})"},
        {"id": "eq3", "kind": "equation", "text": "H_i = D (\\hat{S}_i^z)^2 + B_4^0 (\\mathbf{S}_{i}^{z})^4"},
        {"id": "tbl1", "kind": "table_cell", "text": "J_1^{xx}, J_1^{yy}, J_1^{zz} values in meV"},
    ],
    "unresolved_items": [],
    "unsupported_features": [],
}


_PROMPT_NOTES = [
    "Read the document as a physics paper, not as executable code.",
    "Do not invent Hamiltonian terms that are not supported by the source.",
    "Keep competing named models separate in candidate_models instead of merging them.",
    "Use operator expressions only when the paper gives a trustworthy local bond or onsite form.",
    "Use higher-power onsite operator_expression entries for trustworthy single-site terms such as D * (Sz@0)^2, C * (Sz@0)^3, or B_4^0 * (Sz@0)^4 instead of forcing them into local_bond_candidates.",
    "Reserve local_bond_candidates for bond-local terms; use operator_expression for standalone onsite one-body or crystal-field expressions.",
    "Treat notation variants \\hat{S}, \\mathbf{S}, \\bm{S}, S_{i}, and braced axis superscripts like S_i^{z} as the same spin-component operator when the source meaning is unchanged.",
    "If something is still ambiguous, put it in unresolved_items instead of guessing.",
    "Use fixed orthogonal spin-component labels x,y,z for exchange-component subscripts in the returned model content.",
]


def build_agent_document_normalization_template():
    return {
        "template_version": TEMPLATE_VERSION,
        "template": deepcopy(_TEMPLATE),
        "example_payload": deepcopy(_EXAMPLE_PAYLOAD),
        "prompt_notes": list(_PROMPT_NOTES),
    }
