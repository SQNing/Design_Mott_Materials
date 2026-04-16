"""Focused helper for agent-assisted natural-language fallback proposals.

This module intentionally stops short of integration with the main normalization
pipeline. It provides a narrow proposal surface that higher-level callers can
adopt later once the policy boundary is approved.
"""

from __future__ import annotations

from copy import deepcopy
import re

STRUCTURE_EXTENSIONS = (
    ".cif",
    ".cell",
    ".gen",
    ".stru",
    ".res",
    ".pdb",
    ".xyz",
    ".vasp",
    ".xsf",
)
STRUCTURE_BASENAMES = ("poscar", "contcar", "geometry.in")
HR_FILENAME_PATTERN = re.compile(r"\b[\w./-]*hr[\w.-]*\.dat\b", re.IGNORECASE)
TOKEN_PATH_PATTERN = re.compile(r"\b[\w./-]+\b")

AGENT_INFERRED_FIELDS = frozenset({"input_family", "structure_file", "hamiltonian_file"})
PIPELINE_PATCH_FIELDS = frozenset({"representation", "structure_file", "hamiltonian_file"})
HARD_GATE_FIELDS = frozenset({"coordinate_convention"})
UNSUPPORTED_EVEN_WITH_AGENT = frozenset(
    {
        "bond_phase_convention",
        "multiple_competing_models",
        "ambiguous_lattice_interpretation",
    }
)

ROLE_LABELS = {
    "structure_path_hint": "structure file",
    "model_keyword": "model keyword",
    "hr_path_hint": "Hamiltonian file",
}


def render_recognized_items(source_spans, extracted_evidence):
    """Render a user-facing view of already-recognized evidence."""

    rendered = []
    for item in list(source_spans or []) + list(extracted_evidence or []):
        text = (item or {}).get("text", "")
        role = (item or {}).get("role", "")
        if not text:
            continue
        label = ROLE_LABELS.get(role, role.replace("_", " ").strip() or "recognized item")
        rendered.append(f"{label}: {text}")
    return rendered


def build_agent_inferred(source_text, intermediate_record, normalization_context):
    """Build a focused agent proposal without mutating the normalization path."""

    source_text = (source_text or "").strip()
    intermediate_record = intermediate_record or {}
    normalization_context = normalization_context or {}

    structure_files = _extract_structure_files(source_text)
    hamiltonian_files = _extract_hr_files(source_text)
    structure_file = structure_files[0] if len(structure_files) == 1 else None
    hamiltonian_file = hamiltonian_files[0] if len(hamiltonian_files) == 1 else None
    model_candidates = list(intermediate_record.get("model_candidates") or [])
    blocking_ambiguities = [
        entry
        for entry in list(intermediate_record.get("ambiguities") or [])
        if (entry or {}).get("blocks_landing")
    ]
    selected_coordinate_convention = normalization_context.get("selected_coordinate_convention")
    selected_local_bond_family = normalization_context.get("selected_local_bond_family")

    source_spans = []
    extracted_evidence = []
    inferred_fields = {}
    unresolved_items = []
    unsupported_even_with_agent = []

    for candidate in structure_files:
        source_spans.append({"text": candidate, "role": "structure_path_hint"})
    for candidate in hamiltonian_files:
        source_spans.append({"text": candidate, "role": "hr_path_hint"})

    if structure_file:
        inferred_fields["structure_file"] = structure_file
    if hamiltonian_file:
        inferred_fields["hamiltonian_file"] = hamiltonian_file
    if model_candidates:
        extracted_evidence.append(
            {"text": model_candidates[0].get("name", "unknown"), "role": "model_keyword"}
        )

    if structure_file and hamiltonian_file:
        inferred_fields["input_family"] = "many_body_hr"

    unresolved_items.extend(_blocking_unresolved_items(blocking_ambiguities))

    if len(model_candidates) > 1:
        unresolved_items.append(
            {
                "field": "model_candidate",
                "reason": "Multiple model candidates are present, so the landing is not unique.",
                "policy": "needs_unique_interpretation",
            }
        )

    if len(structure_files) > 1:
        unresolved_items.append(
            {
                "field": "structure_file",
                "reason": "Multiple plausible structure files were recognized in the source text.",
                "policy": "needs_unique_interpretation",
            }
        )

    if len(hamiltonian_files) > 1:
        unresolved_items.append(
            {
                "field": "hamiltonian_file",
                "reason": "Multiple plausible hr-style Hamiltonian files were recognized in the source text.",
                "policy": "needs_unique_interpretation",
            }
        )

    confidence_level = _classify_confidence(
        source_text=source_text,
        model_candidates=model_candidates,
        structure_file=structure_file,
        hamiltonian_file=hamiltonian_file,
        unresolved_items=unresolved_items,
    )

    if selected_local_bond_family and not selected_coordinate_convention:
        unresolved_items.append(
            {
                "field": "coordinate_convention",
                "reason": (
                    "A selected local bond family requires an explicit coordinate "
                    "convention before landing."
                ),
                "policy": "hard_gate",
            }
        )

    status = "proposed"
    if confidence_level == "low":
        status = "rejected"

    landing_readiness = _classify_landing_readiness(
        status=status,
        inferred_fields=inferred_fields,
        unresolved_items=unresolved_items,
        unsupported_even_with_agent=unsupported_even_with_agent,
    )

    recognized_items = render_recognized_items(source_spans, extracted_evidence)
    user_explanation = {
        "recognized": recognized_items,
        "summary": _build_user_summary(
            status=status,
            landing_readiness=landing_readiness,
            confidence_level=confidence_level,
            inferred_fields=inferred_fields,
            unresolved_items=unresolved_items,
        ),
    }

    return {
        "landing_readiness": landing_readiness,
        "agent_inferred": {
            "status": status,
            "confidence": {
                "level": confidence_level,
                "reason": _confidence_reason(
                    confidence_level=confidence_level,
                    inferred_fields=inferred_fields,
                    model_candidates=model_candidates,
                ),
            },
            "inferred_fields": inferred_fields,
            "recognized_items": recognized_items,
            "user_explanation": user_explanation,
            "source_spans": source_spans,
            "extracted_evidence": extracted_evidence,
            "field_policy_boundary": {
                "agent_inferred_fields": sorted(AGENT_INFERRED_FIELDS),
                "pipeline_patch_fields": sorted(PIPELINE_PATCH_FIELDS),
                "hard_gate_fields": sorted(HARD_GATE_FIELDS),
                "unsupported_even_with_agent": sorted(UNSUPPORTED_EVEN_WITH_AGENT),
            },
            "unresolved_items": unresolved_items,
            "unsupported_even_with_agent": unsupported_even_with_agent,
        },
    }


def apply_agent_inferred_patch(normalized_payload, proposal):
    """Apply inferred agent fields to a normalized payload copy."""

    patched = deepcopy(normalized_payload or {})
    inferred_fields = ((proposal or {}).get("agent_inferred") or {}).get("inferred_fields", {})
    landing_readiness = (proposal or {}).get("landing_readiness")

    if landing_readiness == "agent_proposed_ok" and inferred_fields.get("input_family") == "many_body_hr":
        patched["representation"] = "many_body_hr"
    for field in ("structure_file", "hamiltonian_file"):
        if field in inferred_fields:
            patched[field] = inferred_fields[field]
    return patched


def _extract_structure_files(source_text):
    candidates = []
    lowered = source_text.lower()
    for basename in STRUCTURE_BASENAMES:
        if basename in lowered:
            for token in TOKEN_PATH_PATTERN.findall(source_text):
                if token.lower().endswith(basename):
                    _append_unique(candidates, token)
            if not candidates:
                _append_unique(candidates, basename)

    for token in TOKEN_PATH_PATTERN.findall(source_text):
        lowered_token = token.lower()
        if lowered_token.endswith(STRUCTURE_EXTENSIONS):
            _append_unique(candidates, token)
    return candidates


def _extract_hr_files(source_text):
    candidates = []
    for match in HR_FILENAME_PATTERN.finditer(source_text):
        _append_unique(candidates, match.group(0))
    return candidates


def _classify_confidence(source_text, model_candidates, structure_file, hamiltonian_file, unresolved_items):
    if unresolved_items:
        return "medium"
    if structure_file and hamiltonian_file:
        return "high"
    if _is_vague_dialogue(source_text) and not model_candidates:
        return "low"
    if model_candidates:
        return "medium"
    return "low"


def _classify_landing_readiness(
    *,
    status,
    inferred_fields,
    unresolved_items,
    unsupported_even_with_agent,
):
    if unsupported_even_with_agent:
        return "unsupported_even_with_agent"
    if status != "proposed":
        return "agent_proposed_needs_input"
    if unresolved_items:
        return "agent_proposed_needs_input"
    if inferred_fields.get("input_family") == "many_body_hr":
        return "agent_proposed_ok"
    return "agent_proposed_needs_input"


def _is_vague_dialogue(source_text):
    lowered = source_text.lower()
    vague_markers = (
        "maybe",
        "something like",
        "some ",
        "kind of",
        "sort of",
    )
    return any(marker in lowered for marker in vague_markers)


def _confidence_reason(*, confidence_level, inferred_fields, model_candidates):
    if confidence_level == "high":
        return "Both structure and hr-style Hamiltonian files were recognized directly."
    if confidence_level == "medium":
        if model_candidates:
            return "A model keyword was recognized, but landing still depends on missing inputs."
        return "Some actionable evidence was recognized, but the route is still incomplete."
    if inferred_fields:
        return "Recognized evidence was incomplete or blocked by a hard-gated field."
    return "The request stays too vague for a safe landing proposal."


def _build_user_summary(
    *,
    status,
    landing_readiness,
    confidence_level,
    inferred_fields,
    unresolved_items,
):
    if landing_readiness == "agent_proposed_ok":
        return (
            "The helper found a safe structure/hr file pair and can propose a "
            f"{inferred_fields.get('input_family', 'supported')} landing."
        )
    if unresolved_items:
        fields = ", ".join(item["field"] for item in unresolved_items)
        return f"The helper found a possible route, but it still needs: {fields}."
    if status == "rejected":
        return f"The helper rejected the proposal because confidence is {confidence_level}."
    return "The helper found some evidence, but not enough to land safely yet."


def _blocking_unresolved_items(blocking_ambiguities):
    unresolved_items = []
    for entry in blocking_ambiguities:
        unresolved_items.append(
            {
                "field": (entry or {}).get("field") or (entry or {}).get("id") or "ambiguity",
                "reason": (entry or {}).get("question")
                or (entry or {}).get("reason")
                or "A blocking ambiguity remains unresolved.",
                "policy": "blocking_ambiguity",
            }
        )
    return unresolved_items


def _append_unique(items, value):
    if value and value not in items:
        items.append(value)
