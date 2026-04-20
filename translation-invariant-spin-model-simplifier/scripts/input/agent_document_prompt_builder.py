import json

try:
    from input.agent_document_normalization_template import build_agent_document_normalization_template
except ImportError:  # pragma: no cover - package-relative fallback
    from .agent_document_normalization_template import build_agent_document_normalization_template


def _default_prompt_notes():
    template_bundle = build_agent_document_normalization_template()
    return list(template_bundle.get("prompt_notes") or [])


def _render_additional_guidance(prompt_notes):
    prompt_notes = list(prompt_notes or [])
    if not prompt_notes:
        return ""
    guidance_lines = "\n".join(f"- {note}" for note in prompt_notes)
    return f"\nAdditional guidance:\n{guidance_lines}\n"


def _priority_corrections_from_findings(verification_findings):
    selected_model_corrections = []
    selected_family_corrections = []
    parameter_conflict_corrections = []
    evidence_corrections = []
    general_corrections = []

    def add_correction(bucket, text):
        if text and text not in bucket:
            bucket.append(text)

    for finding in list(verification_findings or []):
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("id") or "").strip()
        if finding_id == "selected_model_candidate_conflict":
            candidate = str(finding.get("selected_model_candidate") or "").strip()
            if candidate:
                add_correction(
                    selected_model_corrections,
                    f"Restore selected model candidate {candidate}.",
                )
        elif finding_id == "selected_local_bond_family_missing_in_matrix_form":
            family = str(finding.get("selected_local_bond_family") or "").strip()
            if family:
                add_correction(
                    selected_family_corrections,
                    f"Restore selected local bond family {family} in matrix_form."
                )
        elif finding_id == "selected_local_bond_family_missing_in_effective_candidate":
            family = str(finding.get("selected_local_bond_family") or "").strip()
            if family:
                add_correction(
                    selected_family_corrections,
                    f"Restore selected local bond family {family} in the effective candidate."
                )
        elif finding_id == "parameter_registry_selected_value_conflict":
            parameter = str(finding.get("parameter") or "").strip()
            if parameter:
                add_correction(
                    parameter_conflict_corrections,
                    f"Resolve the value/evidence conflict for parameter {parameter}.",
                )
        elif finding_id == "parameter_registry_selected_unit_conflict":
            parameter = str(finding.get("parameter") or "").strip()
            if parameter:
                add_correction(
                    parameter_conflict_corrections,
                    f"Resolve the unit/evidence conflict for parameter {parameter}.",
                )
        elif finding_id == "parameter_registry_value_conflict":
            parameter = str(finding.get("parameter") or "").strip()
            if parameter:
                add_correction(
                    parameter_conflict_corrections,
                    f"Resolve conflicting evidence values for parameter {parameter}.",
                )
        elif finding_id == "parameter_registry_unit_conflict":
            parameter = str(finding.get("parameter") or "").strip()
            if parameter:
                add_correction(
                    parameter_conflict_corrections,
                    f"Resolve conflicting evidence units for parameter {parameter}.",
                )
        elif finding_id == "parameter_entry_missing_evidence":
            parameter = str(finding.get("parameter") or "").strip()
            if parameter:
                add_correction(
                    evidence_corrections,
                    f"Add explicit evidence_refs for parameter {parameter}.",
                )
        elif finding_id == "parameter_registry_missing_evidence":
            add_correction(
                evidence_corrections,
                "Add explicit evidence_refs for the kept parameter registry entries.",
            )
        elif finding_id == "candidate_model_entry_missing_evidence":
            candidate = str(finding.get("candidate_model") or "").strip()
            family = str(finding.get("family") or "").strip()
            if candidate and family:
                add_correction(
                    evidence_corrections,
                    f"Add explicit evidence_refs for {candidate} family {family}.",
                )
            elif candidate:
                add_correction(
                    evidence_corrections,
                    f"Add explicit evidence_refs for candidate model {candidate}.",
                )
        elif finding_id == "candidate_model_missing_evidence":
            candidate = str(finding.get("candidate_model") or "").strip()
            if candidate:
                add_correction(
                    evidence_corrections,
                    f"Add explicit evidence_refs for candidate model {candidate}.",
                )
        elif finding_id == "candidate_models_missing_evidence":
            add_correction(
                evidence_corrections,
                "Add explicit evidence_refs for the kept candidate model entries.",
            )
        elif finding_id == "candidate_models_gamma_family_missing_matrix_support":
            family = str(finding.get("family") or "").strip()
            if family:
                add_correction(
                    general_corrections,
                    f"Remove unsupported gamma/bond-phase content for family {family} or add matching matrix_form support."
                )
    return (
        selected_model_corrections
        + selected_family_corrections
        + parameter_conflict_corrections
        + evidence_corrections
        + general_corrections
    )


def _render_priority_corrections(priority_corrections):
    priority_corrections = list(priority_corrections or [])
    if not priority_corrections:
        return ""
    correction_lines = "\n".join(f"- {item}" for item in priority_corrections)
    return f"Priority corrections:\n{correction_lines}\n\n"


def build_agent_document_prompt_bundle(source_text, request):
    request = dict(request or {})
    return {
        "source_text": str(source_text or ""),
        "request": request,
        "instructions": {
            "output_format": "json_only",
            "target_schema": request.get("target_schema", "agent_normalized_document"),
            "template_version": request.get("template_version"),
        },
    }


def render_agent_document_prompt(source_text, request):
    bundle = build_agent_document_prompt_bundle(source_text, request)
    request_json = json.dumps(bundle["request"], indent=2, sort_keys=True)
    source_block = str(source_text or "").strip()
    guidance_block = _render_additional_guidance((request or {}).get("prompt_notes"))
    return (
        "You are converting a physics paper fragment into a constrained JSON record.\n\n"
        "Return only valid JSON.\n"
        "Do not include markdown fences.\n"
        "Do not invent physics that is not supported by the source.\n"
        "If something is ambiguous, keep it in unresolved_items instead of guessing.\n\n"
        "Use this request object as the contract:\n"
        f"{request_json}\n\n"
        f"{guidance_block}\n"
        "Source document:\n"
        f"{source_block}\n"
    )


def build_agent_document_followup_prompt_bundle(
    source_text,
    current_agent_normalized_document,
    verification_report,
    *,
    selection_context=None,
    prompt_notes=None,
):
    verification_report = dict(verification_report or {})
    selection_context = dict(selection_context or {})
    prompt_notes = list(prompt_notes or _default_prompt_notes())
    verification_findings = list(verification_report.get("findings", []))
    return {
        "source_text": str(source_text or ""),
        "current_agent_normalized_document": current_agent_normalized_document or {},
        "verification_findings": verification_findings,
        "selection_context": selection_context,
        "prompt_notes": prompt_notes,
        "priority_corrections": _priority_corrections_from_findings(verification_findings),
        "instructions": {
            "task": "revise_existing_agent_normalized_document",
            "output_format": "json_only",
            "preserve_valid_content": True,
        },
    }


def render_agent_document_followup_prompt(
    source_text,
    current_agent_normalized_document,
    verification_report,
    *,
    selection_context=None,
    prompt_notes=None,
):
    bundle = build_agent_document_followup_prompt_bundle(
        source_text,
        current_agent_normalized_document,
        verification_report,
        selection_context=selection_context,
        prompt_notes=prompt_notes,
    )
    findings_json = json.dumps(bundle["verification_findings"], indent=2, sort_keys=True)
    current_json = json.dumps(bundle["current_agent_normalized_document"], indent=2, sort_keys=True)
    source_block = str(source_text or "").strip()
    selection_context_json = json.dumps(bundle["selection_context"], indent=2, sort_keys=True)
    selection_block = ""
    if bundle["selection_context"]:
        selection_block = f"Selection context:\n{selection_context_json}\n\n"
    guidance_block = _render_additional_guidance(bundle.get("prompt_notes"))
    priority_corrections_block = _render_priority_corrections(bundle.get("priority_corrections"))
    return (
        "You are revising an existing agent_normalized_document after verification found conflicts.\n\n"
        "Return only valid JSON.\n"
        "Do not include markdown fences.\n"
        "Preserve any existing fields that are still supported by the source.\n"
        "Only change the parts needed to resolve the findings below.\n"
        "If a conflict cannot be resolved from the source, keep it in unresolved_items.\n\n"
        f"{guidance_block}\n"
        f"{selection_block}"
        f"{priority_corrections_block}"
        "Verifier findings:\n"
        f"{findings_json}\n\n"
        "current agent_normalized_document:\n"
        f"{current_json}\n\n"
        "Source document:\n"
        f"{source_block}\n"
    )
