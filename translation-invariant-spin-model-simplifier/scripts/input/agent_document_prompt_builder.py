import json


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
    return (
        "You are converting a physics paper fragment into a constrained JSON record.\n\n"
        "Return only valid JSON.\n"
        "Do not include markdown fences.\n"
        "Do not invent physics that is not supported by the source.\n"
        "If something is ambiguous, keep it in unresolved_items instead of guessing.\n\n"
        "Use this request object as the contract:\n"
        f"{request_json}\n\n"
        "Source document:\n"
        f"{source_block}\n"
    )


def build_agent_document_followup_prompt_bundle(source_text, current_agent_normalized_document, verification_report):
    verification_report = dict(verification_report or {})
    return {
        "source_text": str(source_text or ""),
        "current_agent_normalized_document": current_agent_normalized_document or {},
        "verification_findings": list(verification_report.get("findings", [])),
        "instructions": {
            "task": "revise_existing_agent_normalized_document",
            "output_format": "json_only",
            "preserve_valid_content": True,
        },
    }


def render_agent_document_followup_prompt(source_text, current_agent_normalized_document, verification_report):
    bundle = build_agent_document_followup_prompt_bundle(
        source_text,
        current_agent_normalized_document,
        verification_report,
    )
    findings_json = json.dumps(bundle["verification_findings"], indent=2, sort_keys=True)
    current_json = json.dumps(bundle["current_agent_normalized_document"], indent=2, sort_keys=True)
    source_block = str(source_text or "").strip()
    return (
        "You are revising an existing agent_normalized_document after verification found conflicts.\n\n"
        "Return only valid JSON.\n"
        "Do not include markdown fences.\n"
        "Preserve any existing fields that are still supported by the source.\n"
        "Only change the parts needed to resolve the findings below.\n"
        "If a conflict cannot be resolved from the source, keep it in unresolved_items.\n\n"
        "Verifier findings:\n"
        f"{findings_json}\n\n"
        "current agent_normalized_document:\n"
        f"{current_json}\n\n"
        "Source document:\n"
        f"{source_block}\n"
    )
