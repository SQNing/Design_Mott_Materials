from copy import deepcopy
import re


def _copy_sequence_of_mappings(value):
    copied = []
    for entry in list(value or []):
        if isinstance(entry, dict):
            copied.append(deepcopy(entry))
    return copied


def _copy_named_mapping_of_mappings(value):
    copied = {}
    if not isinstance(value, dict):
        return copied
    for key, entry in value.items():
        if isinstance(entry, dict):
            copied[str(key)] = deepcopy(entry)
    return copied


def _candidate_models_have_evidence(candidate_models):
    for _, model in candidate_models.items():
        if list(model.get("evidence_refs") or []):
            return True
        for entry in list(model.get("local_bond_candidates") or []):
            if isinstance(entry, dict) and list(entry.get("evidence_refs") or []):
                return True
        for entry in list(model.get("matrix_form_candidates") or []):
            if isinstance(entry, dict) and list(entry.get("evidence_refs") or []):
                return True
    return False


def _parameter_entries_have_evidence(parameter_registry):
    found_rich_entry = False
    for _, value in dict(parameter_registry or {}).items():
        if isinstance(value, dict):
            found_rich_entry = True
            if list(value.get("evidence_refs") or []):
                return True
    return False if found_rich_entry else False


def _normalized_units(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _values_match(left, right):
    try:
        return abs(float(left) - float(right)) <= 1.0e-12
    except (TypeError, ValueError):
        return str(left).strip() == str(right).strip()


def _parameter_conflict_findings(parameter_registry):
    findings = []
    for parameter, value in dict(parameter_registry or {}).items():
        if not isinstance(value, dict):
            continue
        evidence_values = [entry for entry in list(value.get("evidence_values") or []) if isinstance(entry, dict)]
        if len(evidence_values) < 2:
            continue

        units = {str(entry.get("units")).strip() for entry in evidence_values if entry.get("units") is not None}
        if len(units) > 1:
            findings.append(
                {
                    "id": "parameter_registry_unit_conflict",
                    "severity": "warning",
                    "parameter": str(parameter),
                    "message": (
                        f"Parameter {parameter} has conflicting units across evidence entries: "
                        + ", ".join(sorted(units))
                        + "."
                    ),
                }
            )

        comparable_entries = [entry for entry in evidence_values if entry.get("value") is not None]
        if len(comparable_entries) < 2:
            continue
        comparable_units = {
            str(entry.get("units")).strip()
            for entry in comparable_entries
            if entry.get("units") is not None
        }
        if len(comparable_units) > 1:
            continue

        values = []
        all_numeric = True
        for entry in comparable_entries:
            raw = entry.get("value")
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                all_numeric = False
                values.append(raw)
        if all_numeric:
            if max(values) - min(values) > 1.0e-12:
                findings.append(
                    {
                        "id": "parameter_registry_value_conflict",
                        "severity": "warning",
                        "parameter": str(parameter),
                        "message": (
                            f"Parameter {parameter} has conflicting numeric values across evidence entries."
                        ),
                    }
                )
        else:
            normalized = {str(item).strip() for item in values}
            if len(normalized) > 1:
                findings.append(
                    {
                        "id": "parameter_registry_value_conflict",
                        "severity": "warning",
                        "parameter": str(parameter),
                        "message": (
                            f"Parameter {parameter} has conflicting non-numeric values across evidence entries."
                        ),
                    }
                )
    return findings


def _parameter_selected_value_conflict_findings(parameter_registry):
    findings = []
    for parameter, value in dict(parameter_registry or {}).items():
        if not isinstance(value, dict):
            continue
        selected_value = value.get("value")
        selected_units = _normalized_units(value.get("units"))
        if selected_value is None:
            continue

        evidence_values = [entry for entry in list(value.get("evidence_values") or []) if isinstance(entry, dict)]
        unit_conflict_reported = False
        value_conflict_reported = False
        for entry in evidence_values:
            evidence_ref = str(entry.get("evidence_ref") or "").strip() or None
            evidence_units = _normalized_units(entry.get("units"))
            evidence_value = entry.get("value")
            if (
                not unit_conflict_reported
                and selected_units is not None
                and evidence_units is not None
                and selected_units != evidence_units
            ):
                findings.append(
                    {
                        "id": "parameter_registry_selected_unit_conflict",
                        "severity": "warning",
                        "parameter": str(parameter),
                        "evidence_ref": evidence_ref,
                        "message": (
                            f"Parameter {parameter} uses units {selected_units}, but evidence"
                            f"{' ' + evidence_ref if evidence_ref else ''} reports {evidence_units}."
                        ),
                    }
                )
                unit_conflict_reported = True
            if value_conflict_reported or evidence_value is None:
                continue
            if (
                selected_units is not None
                and evidence_units is not None
                and selected_units != evidence_units
            ):
                continue
            if not _values_match(selected_value, evidence_value):
                findings.append(
                    {
                        "id": "parameter_registry_selected_value_conflict",
                        "severity": "warning",
                        "parameter": str(parameter),
                        "evidence_ref": evidence_ref,
                        "message": (
                            f"Parameter {parameter} uses value {selected_value}, but evidence"
                            f"{' ' + evidence_ref if evidence_ref else ''} reports {evidence_value}."
                        ),
                    }
                )
                value_conflict_reported = True
    return findings


def _has_gamma_phase_marker(expression):
    return re.search(r"(?:\\gamma|gamma)_\{ij\}", str(expression or "")) is not None


def _candidate_model_consistency_findings(candidate_models):
    findings = []
    effective = candidate_models.get("effective", {}) if isinstance(candidate_models, dict) else {}
    matrix_form = candidate_models.get("matrix_form", {}) if isinstance(candidate_models, dict) else {}
    effective_families = {
        str(entry.get("family"))
        for entry in list(effective.get("local_bond_candidates") or [])
        if isinstance(entry, dict) and entry.get("family") is not None
    }
    matrix_families = {
        str(entry.get("family"))
        for entry in list(matrix_form.get("local_bond_candidates") or [])
        if isinstance(entry, dict) and entry.get("family") is not None
    }

    missing_families = sorted(family for family in effective_families if family not in matrix_families)
    for family in missing_families:
        findings.append(
            {
                "id": "candidate_models_family_missing_in_matrix_form",
                "severity": "warning",
                "family": family,
                "message": (
                    f"Effective candidate contains family {family}, but matrix_form does not provide a matching family."
                ),
            }
        )

    for entry in list(effective.get("local_bond_candidates") or []):
        if not isinstance(entry, dict):
            continue
        family = entry.get("family")
        if family is None:
            continue
        family = str(family)
        if _has_gamma_phase_marker(entry.get("expression")) and family not in matrix_families:
            findings.append(
                {
                    "id": "candidate_models_gamma_family_missing_matrix_support",
                    "severity": "warning",
                    "family": family,
                    "message": (
                        f"Effective candidate family {family} uses gamma/bond-phase structure, "
                        "but matrix_form does not provide matching support for matrix fallback."
                    ),
                }
            )
    return findings


def _selected_local_bond_family_findings(candidate_models, selected_local_bond_family):
    findings = []
    selected_family = str(selected_local_bond_family or "").strip()
    if not selected_family or not isinstance(candidate_models, dict):
        return findings

    effective = candidate_models.get("effective", {})
    matrix_form = candidate_models.get("matrix_form", {})
    effective_families = {
        str(entry.get("family"))
        for entry in list(effective.get("local_bond_candidates") or [])
        if isinstance(entry, dict) and entry.get("family") is not None
    }
    matrix_families = {
        str(entry.get("family"))
        for entry in list(matrix_form.get("local_bond_candidates") or [])
        if isinstance(entry, dict) and entry.get("family") is not None
    }

    if effective_families and selected_family not in effective_families:
        findings.append(
            {
                "id": "selected_local_bond_family_missing_in_effective_candidate",
                "severity": "warning",
                "selected_local_bond_family": selected_family,
                "message": (
                    f"Selected local bond family {selected_family} is not present in the effective candidate."
                ),
            }
        )

    if matrix_families and selected_family not in matrix_families:
        findings.append(
            {
                "id": "selected_local_bond_family_missing_in_matrix_form",
                "severity": "warning",
                "selected_local_bond_family": selected_family,
                "message": (
                    f"Selected local bond family {selected_family} is not present in matrix_form."
                ),
            }
        )

    return findings


def _parameter_missing_evidence_findings(parameter_registry):
    findings = []
    for parameter, value in dict(parameter_registry or {}).items():
        if not isinstance(value, dict):
            continue
        if list(value.get("evidence_refs") or []):
            continue
        findings.append(
            {
                "id": "parameter_entry_missing_evidence",
                "severity": "warning",
                "parameter": str(parameter),
                "message": f"Parameter {parameter} is missing explicit evidence_refs.",
            }
        )
    return findings


def _candidate_model_entry_missing_evidence_findings(candidate_models):
    findings = []
    for candidate_name, model in dict(candidate_models or {}).items():
        if not isinstance(model, dict):
            continue
        candidate_name = str(candidate_name)
        if (
            any(model.get(field) is not None for field in ("operator_expression", "value"))
            and not list(model.get("evidence_refs") or [])
        ):
            findings.append(
                {
                    "id": "candidate_model_missing_evidence",
                    "severity": "warning",
                    "candidate_model": candidate_name,
                    "message": f"Candidate model {candidate_name} is missing explicit evidence_refs.",
                }
            )
        for collection_name in ("local_bond_candidates", "matrix_form_candidates"):
            for entry in list(model.get(collection_name) or []):
                if not isinstance(entry, dict):
                    continue
                if list(entry.get("evidence_refs") or []):
                    continue
                finding = {
                    "id": "candidate_model_entry_missing_evidence",
                    "severity": "warning",
                    "candidate_model": candidate_name,
                    "message": f"Candidate model {candidate_name} has an entry without explicit evidence_refs.",
                }
                family = entry.get("family")
                if family is not None:
                    finding["family"] = str(family)
                    finding["message"] = (
                        f"Candidate model {candidate_name} family {family} is missing explicit evidence_refs."
                    )
                findings.append(finding)
    return findings


def _selected_model_candidate_findings(agent_normalized_document, selected_model_candidate):
    selected_name = str(selected_model_candidate or "").strip()
    if not selected_name:
        return []
    agent_selected = str((agent_normalized_document or {}).get("selected_model_candidate") or "").strip()
    if not agent_selected or agent_selected == selected_name:
        return []
    return [
        {
            "id": "selected_model_candidate_conflict",
            "severity": "warning",
            "selected_model_candidate": selected_name,
            "agent_selected_model_candidate": agent_selected,
            "message": (
                f"Selected model candidate should be {selected_name}, but the agent marked {agent_selected}."
            ),
        }
    ]


def verify_agent_normalized_document(
    agent_normalized_document,
    *,
    selected_model_candidate=None,
    selected_local_bond_family=None,
):
    document = agent_normalized_document or {}
    evidence_items = _copy_sequence_of_mappings(document.get("evidence_items"))
    candidate_models = _copy_named_mapping_of_mappings(document.get("candidate_models"))
    parameter_registry = dict(document.get("parameter_registry") or {})

    findings = []
    parameter_entries_have_evidence = _parameter_entries_have_evidence(parameter_registry)
    candidate_models_have_evidence = _candidate_models_have_evidence(candidate_models)
    findings.extend(_selected_model_candidate_findings(document, selected_model_candidate))
    findings.extend(_parameter_conflict_findings(parameter_registry))
    findings.extend(_parameter_selected_value_conflict_findings(parameter_registry))
    findings.extend(_candidate_model_consistency_findings(candidate_models))
    findings.extend(
        _selected_local_bond_family_findings(
            candidate_models,
            selected_local_bond_family,
        )
    )
    findings.extend(_parameter_missing_evidence_findings(parameter_registry))
    findings.extend(_candidate_model_entry_missing_evidence_findings(candidate_models))

    if parameter_registry and not parameter_entries_have_evidence:
        findings.append(
            {
                "id": "parameter_registry_missing_evidence",
                "severity": "warning",
                "message": "Parameter registry entries do not yet carry explicit evidence references.",
            }
        )
    if candidate_models and not candidate_models_have_evidence:
        findings.append(
            {
                "id": "candidate_models_missing_evidence",
                "severity": "warning",
                "message": "Candidate model entries do not yet carry explicit evidence references.",
            }
        )

    return {
        "status": "ok" if not findings else "needs_review",
        "findings": findings,
        "coverage": {
            "evidence_item_count": len(evidence_items),
            "parameter_entries_have_evidence": parameter_entries_have_evidence,
            "candidate_models_have_evidence": candidate_models_have_evidence,
        },
    }
