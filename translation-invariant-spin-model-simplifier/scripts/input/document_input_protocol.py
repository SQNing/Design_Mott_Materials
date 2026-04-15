#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


def detect_input_kind(source_text: str, source_path: str | None = None) -> dict:
    text = source_text or ""
    if source_path and source_path.endswith(".tex"):
        return {"source_kind": "tex_document"}
    if "\\begin{equation}" in text or "\\section" in text:
        return {"source_kind": "tex_document"}
    if "$" in text or "\\[" in text:
        return {"source_kind": "latex_fragment"}
    return {"source_kind": "natural_language"}


def _extract_sections(source_text: str) -> dict:
    sections = {
        "structure_sections": [],
        "model_sections": [],
        "parameter_sections": [],
        "analysis_sections": [],
    }
    current_title = None
    current_lines = []

    def flush_current():
        nonlocal current_title, current_lines
        if current_title is None:
            current_lines = []
            return
        content = "\n".join(current_lines).strip()
        if not content:
            current_lines = []
            return
        lowered = current_title.lower()
        entry = {"title": current_title, "content": content}
        if "structure" in lowered or "crystal" in lowered:
            sections["structure_sections"].append(entry)
        elif "hamiltonian" in lowered or "exchange" in lowered:
            sections["model_sections"].append(entry)
        elif "parameter" in lowered:
            sections["parameter_sections"].append(entry)
        else:
            sections["analysis_sections"].append(entry)
        current_lines = []

    for line in text_lines(source_text):
        title_match = re.match(r"\\section\*\{([^}]*)\}", line.strip())
        if title_match:
            flush_current()
            current_title = title_match.group(1).strip()
            continue
        if current_title is not None:
            current_lines.append(line)

    flush_current()
    return sections


def text_lines(source_text: str) -> list[str]:
    return (source_text or "").splitlines()


def _extract_model_candidates(source_text: str) -> list[dict]:
    candidates = []
    if "Toy Hamiltonian" in source_text:
        candidates.append({"name": "toy", "role": "simplified", "source_span": "Toy Hamiltonian"})
    if "Effective Hamiltonian" in source_text:
        candidates.append({"name": "effective", "role": "main", "source_span": "Effective Hamiltonian"})
    if "Equivalent Exchange-Matrix Form" in source_text:
        candidates.append({"name": "matrix_form", "role": "equivalent_form", "source_span": "Equivalent Exchange-Matrix Form"})
    return candidates


def build_intermediate_record(source_text: str, source_path: str | None = None) -> dict:
    kind = detect_input_kind(source_text, source_path=source_path)
    sections = _extract_sections(source_text)
    candidates = _extract_model_candidates(source_text)
    ambiguities = []

    blocking_candidates = [candidate for candidate in candidates if candidate["role"] in {"main", "simplified"}]
    if len(blocking_candidates) > 1:
        ambiguities.append(
            {
                "id": "model_candidate_selection",
                "blocks_landing": True,
                "question": "Multiple Hamiltonian candidates were detected. Which one should I use?",
            }
        )

    return {
        "source_document": {
            "source_kind": kind["source_kind"],
            "source_path": source_path,
        },
        "document_sections": sections,
        "model_candidates": candidates,
        "system_context": {},
        "lattice_model": {},
        "hamiltonian_model": {},
        "parameter_registry": {},
        "ambiguities": ambiguities,
        "confidence_report": {},
        "unsupported_features": [],
    }


def land_intermediate_record(record: dict) -> dict:
    blocking = [entry for entry in record.get("ambiguities", []) if entry.get("blocks_landing")]
    if blocking:
        question = blocking[0]
        return {
            "interaction": {
                "status": "needs_input",
                "id": question["id"],
                "question": question["question"],
            },
            "unsupported_features": list(record.get("unsupported_features", [])),
        }

    expression = (
        record.get("hamiltonian_model", {}).get("operator_expression")
        or record.get("hamiltonian_model", {}).get("value")
        or ""
    )
    return {
        "representation": "operator",
        "support": [0, 1],
        "expression": expression,
        "parameters": dict(record.get("parameter_registry", {})),
        "user_notes": "Generated from document input protocol",
        "unsupported_features": list(record.get("unsupported_features", [])),
    }


def load_source_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
