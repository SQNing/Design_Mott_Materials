#!/usr/bin/env python3
import argparse
from copy import deepcopy
import json
import re
import sys
from datetime import datetime, timezone
from collections.abc import Iterable
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from input.agent_fallback import apply_agent_inferred_patch, build_agent_inferred
    from input.document_input_protocol import build_intermediate_record, detect_input_kind, land_intermediate_record
    from common.rotating_frame_realization import resolve_rotating_frame_realization
else:
    from .agent_fallback import apply_agent_inferred_patch, build_agent_inferred
    from .document_input_protocol import build_intermediate_record, detect_input_kind, land_intermediate_record
    from common.rotating_frame_realization import resolve_rotating_frame_realization


DEFAULT_TIMEOUTS = {
    "simplification_seconds": 600,
    "projection_seconds": 300,
    "classical_solver_seconds": 600,
}

SUPPORTED_REPRESENTATIONS = {"operator", "operator_family_collection", "matrix", "natural_language", "many_body_hr"}


def _default_lattice():
    return {"kind": "unspecified", "dimension": None, "unit_cell": []}


def _default_coordinate_convention():
    return {
        "status": "unspecified",
        "frame": "unspecified",
        "axis_labels": [],
        "axis_mapping": {},
        "resolved_frame": None,
        "resolved_axis_labels": [],
        "rotation_matrix": None,
        "family_overrides": {},
        "bond_overrides": {},
        "quantization_axis": None,
        "raw_description": "",
    }


def _default_magnetic_order():
    return {
        "status": "unspecified",
        "kind": "unspecified",
        "wavevector": [],
        "wavevector_units": None,
        "reference_frame": {
            "kind": "laboratory",
            "phase_origin": None,
        },
        "raw_description": "",
    }


def _default_rotating_frame():
    return {
        "status": "not-needed",
        "kind": "not-needed",
    }


def _default_rotating_frame_transform():
    return {
        "status": "not-needed",
        "kind": "not-needed",
    }


def _compile_rotating_frame(normalized):
    magnetic_order = dict(normalized.get("magnetic_order", _default_magnetic_order()))
    coordinate_convention = dict(normalized.get("coordinate_convention", _default_coordinate_convention()))
    if magnetic_order.get("kind") not in {"single_q_spiral", "single_q_helical", "single_q_order"}:
        return _default_rotating_frame(), _default_rotating_frame_transform(), None
    if magnetic_order.get("reference_frame", {}).get("kind") != "rotating":
        return _default_rotating_frame(), _default_rotating_frame_transform(), None

    wavevector = list(magnetic_order.get("wavevector") or [])
    if len(wavevector) != 3:
        return (
            _default_rotating_frame(),
            _default_rotating_frame_transform(),
            {
                "status": "needs_input",
                "id": "wavevector_selection",
                "question": "The single-Q magnetic order requires a propagation vector Q. Which wavevector should I use?",
            },
        )

    units = magnetic_order.get("wavevector_units")
    if units not in {"reciprocal_lattice_units", "cartesian_reciprocal"}:
        return (
            _default_rotating_frame(),
            _default_rotating_frame_transform(),
            {
                "status": "needs_input",
                "id": "wavevector_units_selection",
                "question": "The single-Q propagation vector Q was detected, but its basis/units are unspecified. Which convention should I use?",
                "options": ["reciprocal_lattice_units", "cartesian_reciprocal"],
            },
        )

    axis_labels = list(coordinate_convention.get("axis_labels") or [])
    resolved_axis_labels = list(coordinate_convention.get("resolved_axis_labels") or [])
    rotation_axis = (
        coordinate_convention.get("quantization_axis")
        or (resolved_axis_labels[2] if len(resolved_axis_labels) == 3 else None)
        or (axis_labels[2] if len(axis_labels) == 3 else None)
        or "z"
    )

    phase_rule = (
        "Q_dot_r_plus_phi_s"
        if magnetic_order.get("reference_frame", {}).get("phase_origin") == "Q_dot_r"
        else "unspecified_phase"
    )
    rotating_frame = {
        "status": "explicit",
        "kind": "single_q_rotating_frame",
        "source_order_kind": magnetic_order.get("kind"),
        "wavevector": wavevector,
        "wavevector_units": units,
        "phase_rule": phase_rule,
        "sublattice_phase_offsets": {},
        "rotation_axis": rotation_axis,
    }
    rotating_frame_transform = {
        "status": "explicit",
        "kind": "site_phase_rotation",
        "source_frame_kind": rotating_frame["kind"],
        "source_order_kind": magnetic_order.get("kind"),
        "wavevector": wavevector,
        "wavevector_units": units,
        "phase_rule": phase_rule,
        "phase_origin": magnetic_order.get("reference_frame", {}).get("phase_origin"),
        "sublattice_phase_offsets": {},
        "rotation_axis": rotation_axis,
    }

    return rotating_frame, rotating_frame_transform, None


def _finalize_normalized_payload(normalized):
    finalized = dict(normalized)
    rotating_frame, rotating_frame_transform, interaction = _compile_rotating_frame(finalized)
    finalized["rotating_frame"] = rotating_frame
    finalized["rotating_frame_transform"] = rotating_frame_transform
    rotating_frame_realization = resolve_rotating_frame_realization(finalized)
    if rotating_frame_realization is not None:
        finalized["rotating_frame_realization"] = rotating_frame_realization
    existing_interaction = finalized.get("interaction")
    if interaction is not None and not (
        isinstance(existing_interaction, dict) and existing_interaction.get("status") == "needs_input"
    ):
        finalized["interaction"] = interaction
    return finalized


def _copy_passthrough_fields(source, destination):
    for key in (
        "supercell_shape",
        "positions",
        "lattice_vectors",
        "rotating_frame",
        "rotating_frame_transform",
        "rotating_frame_realization",
        "quadratic_phase_dressing",
        "classical_state",
        "classical",
        "ordering",
        "document_intermediate",
        "document_source_text",
        "document_source_path",
        "selected_model_candidate",
        "selected_local_bond_family",
        "selected_coordinate_convention",
    ):
        if key in source:
            destination[key] = source[key]
    return destination


def _normalize_lattice_description(payload, legacy_lattice):
    lattice_description = payload.get("lattice_description")
    if lattice_description is None:
        return legacy_lattice
    if isinstance(lattice_description, str):
        text = lattice_description.strip()
        if not text:
            raise ValueError("lattice_description must be non-empty")
        return {"kind": "natural_language", "value": text}
    if not isinstance(lattice_description, dict):
        raise ValueError("lattice_description must be a mapping or string")
    return lattice_description


def _normalize_support(support):
    if isinstance(support, (str, bytes)) or not isinstance(support, Iterable):
        raise ValueError("support must be a sequence of integers")
    normalized = []
    for item in support:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("support must contain integers only")
        normalized.append(item)
    return normalized


def _require_representation_value(payload, representation):
    field_map = {
        "operator": "expression",
        "operator_family_collection": "expressions",
        "matrix": "matrix",
        "natural_language": "description",
    }
    field = field_map[representation]
    if field not in payload:
        raise ValueError(f"{representation} payload requires {field}")
    value = payload.get(field)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError(f"{representation} payload requires non-empty {field}")
        return value
    if value is None:
        raise ValueError(f"{representation} payload requires non-empty {field}")
    if hasattr(value, "__len__") and len(value) == 0:
        raise ValueError(f"{representation} payload requires non-empty {field}")
    return value


def _normalize_many_body_hr_representation(payload):
    structure_file = payload.get("structure_file")
    hamiltonian_file = payload.get("hamiltonian_file")
    if not structure_file:
        raise ValueError("many_body_hr payload requires structure_file")
    if not hamiltonian_file:
        raise ValueError("many_body_hr payload requires hamiltonian_file")

    return {
        "support": [],
        "representation": {
            "kind": "many_body_hr",
            "structure_file": str(structure_file),
            "hamiltonian_file": str(hamiltonian_file),
        },
        "basis_semantics": {
            "local_space": "pseudospin_orbital",
        },
        "basis_order": "orbital_major_spin_minor",
    }


def _extract_path_mention(text, filename):
    pattern = re.compile(
        rf"(?P<path>(?:~|/|\./|\.\./)?[A-Za-z0-9_./:+-]*{re.escape(filename)})\b"
    )
    matches = [match.group("path").rstrip(",;:") for match in pattern.finditer(text or "")]
    if not matches:
        return None
    return max(matches, key=len)


def _extract_generic_path_tokens(text):
    pattern = re.compile(
        r"(?P<path>(?:~|/|\./|\.\./)?[A-Za-z0-9_./:+-]+\.[A-Za-z0-9_+-]+|(?:~|/|\./|\.\./)?(?:POSCAR|CONTCAR)\b)"
    )
    return [match.group("path").rstrip(".,;:") for match in pattern.finditer(text or "")]


def _extract_directory_path_tokens(text):
    pattern = re.compile(
        r"(?P<path>(?:~|/|\./|\.\./)[A-Za-z0-9_./:+-]*[A-Za-z0-9_+-])"
    )
    matches = []
    for match in pattern.finditer(text or ""):
        candidate = match.group("path").rstrip(".,;:")
        path = Path(candidate).expanduser()
        if path.exists() and path.is_dir():
            matches.append(str(path))
    return matches


def _extract_explicit_role_path(text, role_patterns):
    path_pattern = r"(?P<path>(?:~|/|\./|\.\./)?[A-Za-z0-9_./:+-]+)"
    matches = []
    for role_pattern in role_patterns:
        pattern = re.compile(
            rf"(?i)\b(?:{role_pattern})\b\s*(?:is|=|:)?\s*{path_pattern}"
        )
        matches.extend(match.group("path").rstrip(".,;:") for match in pattern.finditer(text or ""))
    if not matches:
        return None
    return max(matches, key=len)


def _looks_like_structure_file(path):
    lowered = Path(path).name.lower()
    return (
        lowered in {"poscar", "contcar", "geometry.in", "structure.in"}
        or lowered.endswith(".cif")
        or lowered.endswith(".cell")
        or lowered.endswith(".gen")
        or lowered.endswith(".stru")
        or lowered.endswith(".res")
        or lowered.endswith(".pdb")
        or lowered.endswith(".xyz")
        or lowered.endswith(".vasp")
        or lowered.endswith(".xsf")
    )


def _looks_like_hr_file(path):
    lowered = Path(path).name.lower()
    return "hr" in lowered or re.search(r"(?:^|[_\-.])h[_\-.]*r(?:[_\-.]|$)", lowered) is not None


def _structure_candidate_rank(path):
    lowered = Path(path).name.lower()
    if lowered == "poscar":
        return (100, -len(str(path)))
    if lowered == "contcar":
        return (95, -len(str(path)))
    if lowered == "geometry.in":
        return (93, -len(str(path)))
    if lowered == "structure.in":
        return (92, -len(str(path)))
    if lowered.endswith(".vasp"):
        return (90, -len(str(path)))
    if lowered.endswith(".cif"):
        return (85, -len(str(path)))
    if lowered.endswith(".cell"):
        return (82, -len(str(path)))
    if lowered.endswith(".xsf"):
        return (80, -len(str(path)))
    if lowered.endswith(".gen"):
        return (78, -len(str(path)))
    if lowered.endswith(".res"):
        return (76, -len(str(path)))
    if lowered.endswith(".stru"):
        return (74, -len(str(path)))
    if lowered.endswith(".xyz"):
        return (70, -len(str(path)))
    if lowered.endswith(".pdb"):
        return (68, -len(str(path)))
    return (0, -len(str(path)))


def _hr_candidate_rank(path):
    lowered = Path(path).name.lower()
    if lowered == "vr_hr.dat":
        return (100, -len(str(path)))
    if lowered == "wannier90_hr.dat":
        return (96, -len(str(path)))
    if lowered == "h_r.dat":
        return (94, -len(str(path)))
    if "vr_hr" in lowered:
        return (90, -len(str(path)))
    if "wannier" in lowered and "hr" in lowered:
        return (88, -len(str(path)))
    if _looks_like_hr_file(path):
        return (75, -len(str(path)))
    return (0, -len(str(path)))


def _discover_many_body_hr_paths_in_directory(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return None
    entries = [entry for entry in directory.iterdir() if entry.is_file()]
    structure_candidates = [entry for entry in entries if _looks_like_structure_file(entry)]
    hr_candidates = [entry for entry in entries if _looks_like_hr_file(entry)]
    structure_file = None
    hamiltonian_file = None
    if structure_candidates:
        structure_file = str(max(structure_candidates, key=_structure_candidate_rank))
    if hr_candidates:
        hamiltonian_file = str(max(hr_candidates, key=_hr_candidate_rank))
    if structure_file is None and hamiltonian_file is None:
        return None
    return {
        "structure_file": structure_file,
        "hamiltonian_file": hamiltonian_file,
    }


def _detect_many_body_hr_file_candidates(text):
    structure_file = (
        _extract_explicit_role_path(
            text,
            role_patterns=(
                "structure file",
                "structure path",
                "structural file",
                "crystal file",
                "cif file",
            ),
        )
        or _extract_path_mention(text, "POSCAR")
        or _extract_path_mention(text, "CONTCAR")
    )
    hamiltonian_file = (
        _extract_explicit_role_path(
            text,
            role_patterns=(
                "hr file",
                "hr path",
                "hamiltonian file",
                "hamiltonian path",
                "hopping file",
                "hopping path",
                "wannier(?:90)?(?:_?hr)? file",
            ),
        )
        or _extract_path_mention(text, "VR_hr.dat")
    )

    generic_paths = _extract_generic_path_tokens(text)
    if structure_file is None:
        structure_candidates = [path for path in generic_paths if _looks_like_structure_file(path)]
        if structure_candidates:
            structure_file = max(structure_candidates, key=len)
    if hamiltonian_file is None:
        hr_candidates = [path for path in generic_paths if _looks_like_hr_file(path)]
        if hr_candidates:
            hamiltonian_file = max(hr_candidates, key=len)

    discovered_from_directories = [
        discovery
        for directory in _extract_directory_path_tokens(text)
        for discovery in [_discover_many_body_hr_paths_in_directory(directory)]
        if discovery is not None
    ]
    if structure_file is None:
        structure_candidates = [
            discovery["structure_file"]
            for discovery in discovered_from_directories
            if discovery.get("structure_file")
        ]
        if structure_candidates:
            structure_file = max(structure_candidates, key=_structure_candidate_rank)
    if hamiltonian_file is None:
        hr_candidates = [
            discovery["hamiltonian_file"]
            for discovery in discovered_from_directories
            if discovery.get("hamiltonian_file")
        ]
        if hr_candidates:
            hamiltonian_file = max(hr_candidates, key=_hr_candidate_rank)

    return {
        "structure_file": structure_file,
        "hamiltonian_file": hamiltonian_file,
    }


def _extract_many_body_hr_paths_from_text(text):
    detected = _detect_many_body_hr_file_candidates(text)
    structure_file = detected["structure_file"]
    hamiltonian_file = detected["hamiltonian_file"]

    if not structure_file or not hamiltonian_file:
        return None
    return {
        "structure_file": structure_file,
        "hamiltonian_file": hamiltonian_file,
    }


def _inspect_many_body_hr_text(text):
    detected = _detect_many_body_hr_file_candidates(text)
    structure_file = detected["structure_file"]
    hamiltonian_file = detected["hamiltonian_file"]

    if structure_file and hamiltonian_file:
        return {
            "status": "ready",
            "structure_file": structure_file,
            "hamiltonian_file": hamiltonian_file,
        }
    if hamiltonian_file:
        return {
            "status": "needs_input",
            "missing": "structure_file",
            "detected": {"hamiltonian_file": hamiltonian_file},
            "interaction": {
                "status": "needs_input",
                "id": "structure_file_selection",
                "question": "I found an hr-style Hamiltonian file path, but not a matching structure file path. Which structure file should I use?",
            },
        }
    if structure_file:
        return {
            "status": "needs_input",
            "missing": "hamiltonian_file",
            "detected": {"structure_file": structure_file},
            "interaction": {
                "status": "needs_input",
                "id": "hamiltonian_hr_file_selection",
                "question": "I found a structure file path, but not a matching hr-style Hamiltonian file path. Which hr file should I use?",
            },
        }
    return None


def _normalize_routed_many_body_hr_text(text, *, source_mode, passthrough=None):
    inspected = _inspect_many_body_hr_text(text)
    if inspected is None or inspected.get("status") != "ready":
        return None

    routed_payload = dict(passthrough or {})
    routed_payload.update(
        {
            "representation": "many_body_hr",
            "structure_file": inspected["structure_file"],
            "hamiltonian_file": inspected["hamiltonian_file"],
            "user_notes": routed_payload.get("user_notes", text),
            "source_mode": routed_payload.get("source_mode", source_mode),
        }
    )
    return normalize_input(routed_payload)


def _infer_local_dimension_from_text(text, default=2):
    lowered = (text or "").lower()
    if re.search(r"\bspin[-\s]*one[-\s]*half\b", lowered):
        return 2
    fraction_match = re.search(r"\bspin(?:[-\s]+)?(?P<num>\d+)\s*/\s*(?P<den>\d+)\b", lowered)
    if fraction_match:
        if fraction_match.group("den") != "2":
            raise ValueError("unsupported explicit spin fraction")
        return int(fraction_match.group("num")) + 1
    match = re.search(r"\bspin(?:[-\s]+)?(?P<spin>\d+)\b", lowered)
    if match:
        return int(match.group("spin")) * 2 + 1
    return default


def _natural_language_base_payload(text, *, local_dimension, user_notes, source_mode):
    lattice_description = {"kind": "natural_language", "value": text}
    hamiltonian_description = {
        "support": [],
        "representation": {"kind": "natural_language", "value": text},
    }
    return {
        "system": {"name": "", "units": "arb."},
        "local_hilbert": {"dimension": int(local_dimension), "uniform": True},
        "lattice": _default_lattice(),
        "lattice_description": lattice_description,
        "local_term": dict(hamiltonian_description),
        "hamiltonian_description": hamiltonian_description,
        "parameters": {},
        "symmetry_hints": [],
        "user_required_symmetries": [],
        "allowed_breaking": [],
        "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
        "timeouts": dict(DEFAULT_TIMEOUTS),
        "user_notes": user_notes,
        "coordinate_convention": _default_coordinate_convention(),
        "magnetic_order": _default_magnetic_order(),
        "provenance": {
            "source_mode": source_mode,
            "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }


def _natural_language_many_body_hr_needs_input_payload(
    text,
    *,
    local_dimension,
    user_notes,
    source_mode,
    route_hint,
):
    normalized = _natural_language_base_payload(
        text,
        local_dimension=local_dimension,
        user_notes=user_notes,
        source_mode=source_mode,
    )
    normalized["interaction"] = dict(route_hint.get("interaction", {}))
    normalized["many_body_hr_route_hint"] = {
        "status": route_hint.get("status"),
        "missing": route_hint.get("missing"),
        "detected": dict(route_hint.get("detected", {})),
    }
    return _finalize_normalized_payload(normalized)


def _preserve_textual_path_spelling(text, path):
    candidate = str(path or "")
    if not candidate:
        return candidate
    mentioned = _extract_path_mention(text, Path(candidate).name)
    if mentioned:
        return mentioned
    return candidate


def _normalize_ready_many_body_hr_hint(text, *, source_mode, user_notes, route_hint, passthrough=None):
    routed_payload = dict(passthrough or {})
    routed_payload.update(
        {
            "representation": "many_body_hr",
            "structure_file": _preserve_textual_path_spelling(text, route_hint["structure_file"]),
            "hamiltonian_file": _preserve_textual_path_spelling(text, route_hint["hamiltonian_file"]),
            "user_notes": user_notes,
            "source_mode": source_mode,
        }
    )
    return normalize_input(routed_payload)


def _document_lattice_text(record, fallback_text):
    sections = record.get("document_sections", {})
    structure_sections = sections.get("structure_sections", [])
    snippets = []
    for section in structure_sections:
        content = str(section.get("content") or "").strip()
        if content:
            snippets.append(content)
    if snippets:
        return "\n\n".join(snippets)
    return fallback_text


def _build_agent_fallback_proposal(
    text,
    *,
    record,
    selected_coordinate_convention=None,
    selected_local_bond_family=None,
):
    return build_agent_inferred(
        source_text=text,
        intermediate_record=record,
        normalization_context={
            "selected_coordinate_convention": selected_coordinate_convention,
            "selected_local_bond_family": selected_local_bond_family,
        },
    )


def _can_accept_helper_many_body_route(record, proposal):
    return bool(
        proposal.get("landing_readiness") == "agent_proposed_ok"
        and list((record or {}).get("model_candidates") or [])
    )


def _apply_agent_metadata(normalized, *, landed=None, proposal=None, accepted=False):
    if landed is not None and landed.get("landing_readiness") is not None:
        normalized["landing_readiness"] = landed["landing_readiness"]

    source_agent = None
    if proposal is not None:
        source_agent = deepcopy(proposal.get("agent_inferred", {}))
        if source_agent and accepted:
            source_agent["status"] = "accepted"
        if proposal.get("landing_readiness") is not None:
            normalized["landing_readiness"] = proposal["landing_readiness"]
    elif landed is not None and landed.get("agent_inferred") is not None:
        source_agent = deepcopy(landed.get("agent_inferred", {}))

    if source_agent:
        normalized["agent_inferred"] = source_agent
    if landed is not None and "unsupported_features" in landed:
        normalized["unsupported_features"] = list(landed.get("unsupported_features", []))
    return normalized


def _normalize_document_style_natural_language(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_family=None,
    selected_coordinate_convention=None,
    local_dimension,
    source_mode,
):
    record = build_intermediate_record(
        source_text=text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
    )
    lattice_text = _document_lattice_text(record, text)
    landed = land_intermediate_record(record)
    if landed.get("interaction", {}).get("status") == "needs_input":
        normalized = _natural_language_base_payload(
            text,
            local_dimension=local_dimension,
            user_notes=text,
            source_mode=source_mode,
        )
        normalized["lattice_description"] = {"kind": "natural_language", "value": lattice_text}
        normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
        normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
        normalized["interaction"] = landed["interaction"]
        normalized["unsupported_features"] = list(landed.get("unsupported_features", []))
        normalized["document_intermediate"] = record
        _apply_agent_metadata(normalized, landed=landed)
        return _finalize_normalized_payload(normalized)

    return normalize_input(
        (
            {
            "representation": landed["representation"],
            "support": list(landed.get("support", [])),
            "expression": landed.get("expression", ""),
            "lattice_description": {"kind": "natural_language", "value": lattice_text},
            "parameters": dict(landed.get("parameters", {})),
            "coordinate_convention": dict(landed.get("coordinate_convention", {})),
            "magnetic_order": dict(landed.get("magnetic_order", {})),
            "user_notes": landed.get("user_notes", text),
            "unsupported_features": list(landed.get("unsupported_features", [])),
            "source_mode": source_mode,
            "document_intermediate": record,
            "document_source_text": text,
            "document_source_path": source_path,
            "selected_model_candidate": selected_model_candidate,
            "selected_local_bond_family": selected_local_bond_family,
            "selected_coordinate_convention": selected_coordinate_convention,
            }
            if landed["representation"] != "operator_family_collection"
            else {
                "representation": landed["representation"],
                "support": list(landed.get("support", [])),
                "expressions": list(landed.get("expressions", [])),
                "lattice_description": {"kind": "natural_language", "value": lattice_text},
                "parameters": dict(landed.get("parameters", {})),
                "coordinate_convention": dict(landed.get("coordinate_convention", {})),
                "magnetic_order": dict(landed.get("magnetic_order", {})),
                "user_notes": landed.get("user_notes", text),
                "unsupported_features": list(landed.get("unsupported_features", [])),
                "source_mode": source_mode,
                "document_intermediate": record,
                "document_source_text": text,
                "document_source_path": source_path,
                "selected_model_candidate": selected_model_candidate,
                "selected_local_bond_family": selected_local_bond_family,
                "selected_coordinate_convention": selected_coordinate_convention,
            }
        )
    )
def normalize_freeform_text(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_family=None,
    selected_coordinate_convention=None,
):
    text = (text or "").strip()
    if not text:
        raise ValueError("freeform input must be non-empty")
    route_hint = _inspect_many_body_hr_text(text)
    record = build_intermediate_record(
        source_text=text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_family=selected_local_bond_family,
        selected_coordinate_convention=selected_coordinate_convention,
    )
    proposal = _build_agent_fallback_proposal(
        text,
        record=record,
        selected_coordinate_convention=selected_coordinate_convention,
        selected_local_bond_family=selected_local_bond_family,
    )
    if _can_accept_helper_many_body_route(record, proposal):
        patched_payload = apply_agent_inferred_patch(
            {
                "representation": "natural_language",
                "description": text,
                "source_path": source_path,
                "selected_model_candidate": selected_model_candidate,
                "selected_local_bond_family": selected_local_bond_family,
                "selected_coordinate_convention": selected_coordinate_convention,
                "user_notes": text,
                "source_mode": "freeform",
            },
            proposal,
        )
        normalized = normalize_input(patched_payload)
        _apply_agent_metadata(normalized, proposal=proposal, accepted=True)
        return normalized
    if route_hint is not None and route_hint.get("status") == "needs_input":
        return _natural_language_many_body_hr_needs_input_payload(
            text,
            local_dimension=_infer_local_dimension_from_text(text),
            user_notes=text,
            source_mode="freeform",
            route_hint=route_hint,
        )
    detected_kind = detect_input_kind(text, source_path=source_path).get("source_kind")
    local_dimension = _infer_local_dimension_from_text(text)
    if detected_kind == "tex_document":
        return _normalize_document_style_natural_language(
            text,
            source_path=source_path,
            selected_model_candidate=selected_model_candidate,
            selected_local_bond_family=selected_local_bond_family,
            selected_coordinate_convention=selected_coordinate_convention,
            local_dimension=local_dimension,
            source_mode="freeform",
        )
    if route_hint is not None and route_hint.get("status") == "ready":
        return _normalize_ready_many_body_hr_hint(
            text,
            source_mode="freeform",
            user_notes=text,
            route_hint=route_hint,
        )
    landed = land_intermediate_record(record)
    normalized = _natural_language_base_payload(
        text,
        local_dimension=local_dimension,
        user_notes=text,
        source_mode="freeform",
    )
    if landed.get("interaction", {}).get("status") == "needs_input" or landed.get("agent_inferred") is not None:
        normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
        normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
        if landed.get("interaction") is not None:
            normalized["interaction"] = landed["interaction"]
        normalized["document_intermediate"] = record
        _apply_agent_metadata(normalized, landed=landed)
        return _finalize_normalized_payload(normalized)
    return normalized


def normalize_input(payload):
    representation = payload.get("representation", "operator")
    if representation not in SUPPORTED_REPRESENTATIONS:
        raise ValueError("unsupported representation")
    if representation == "natural_language":
        description = _require_representation_value(payload, representation)
        source_path = payload.get("source_path")
        selected_model_candidate = payload.get("selected_model_candidate")
        selected_local_bond_family = payload.get("selected_local_bond_family")
        selected_coordinate_convention = payload.get("selected_coordinate_convention")
        route_hint = _inspect_many_body_hr_text(description)
        if payload.get("document_intermediate") is not None:
            landed = land_intermediate_record(payload["document_intermediate"])
            if landed.get("interaction", {}).get("status") == "needs_input":
                normalized = normalize_freeform_text(
                    description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_family=selected_local_bond_family,
                    selected_coordinate_convention=selected_coordinate_convention,
                )
                normalized["coordinate_convention"] = dict(
                    landed.get("coordinate_convention", normalized.get("coordinate_convention", _default_coordinate_convention()))
                )
                normalized["magnetic_order"] = dict(
                    landed.get("magnetic_order", normalized.get("magnetic_order", _default_magnetic_order()))
                )
                normalized["interaction"] = landed["interaction"]
                normalized["unsupported_features"] = list(landed.get("unsupported_features", []))
                _apply_agent_metadata(normalized, landed=landed)
                return _finalize_normalized_payload(normalized)
            payload = {
                **payload,
                **landed,
                "representation": landed["representation"],
            }
            representation = payload["representation"]
        else:
            detected_kind = detect_input_kind(description, source_path=source_path).get("source_kind")
            if detected_kind == "tex_document":
                return _normalize_document_style_natural_language(
                    description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_family=selected_local_bond_family,
                    selected_coordinate_convention=selected_coordinate_convention,
                    local_dimension=int(payload.get("local_dim", 2)),
                    source_mode=payload.get("source_mode", representation),
                )
            record = build_intermediate_record(
                source_text=description,
                source_path=source_path,
                selected_model_candidate=selected_model_candidate,
                selected_local_bond_family=selected_local_bond_family,
                selected_coordinate_convention=selected_coordinate_convention,
            )
            proposal = _build_agent_fallback_proposal(
                description,
                record=record,
                selected_coordinate_convention=selected_coordinate_convention,
                selected_local_bond_family=selected_local_bond_family,
            )
            if _can_accept_helper_many_body_route(record, proposal):
                patched_payload = apply_agent_inferred_patch(payload, proposal)
                normalized = normalize_input(patched_payload)
                _apply_agent_metadata(normalized, proposal=proposal, accepted=True)
                return normalized
            if route_hint is not None and route_hint.get("status") == "needs_input":
                user_notes = payload.get("user_notes", "") or description
                return _natural_language_many_body_hr_needs_input_payload(
                    description,
                    local_dimension=int(payload.get("local_dim", 2)),
                    user_notes=user_notes,
                    source_mode=payload.get("source_mode", representation),
                    route_hint=route_hint,
                )
            if route_hint is not None and route_hint.get("status") == "ready":
                return _normalize_ready_many_body_hr_hint(
                    description,
                    source_mode=payload.get("source_mode", representation),
                    user_notes=payload.get("user_notes", "") or description,
                    route_hint=route_hint,
                    passthrough={
                        key: value
                        for key, value in payload.items()
                        if key not in {"representation", "description"}
                    },
                )
            record = build_intermediate_record(
                source_text=description,
                source_path=source_path,
                selected_model_candidate=selected_model_candidate,
                selected_local_bond_family=selected_local_bond_family,
                selected_coordinate_convention=selected_coordinate_convention,
            )
            landed = land_intermediate_record(record)
            if landed.get("interaction", {}).get("status") == "needs_input" or landed.get("agent_inferred") is not None:
                normalized = _natural_language_base_payload(
                    description,
                    local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                    user_notes=payload.get("user_notes", "") or description,
                    source_mode=payload.get("source_mode", representation),
                )
                normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
                normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
                if landed.get("interaction") is not None:
                    normalized["interaction"] = landed["interaction"]
                normalized["document_intermediate"] = record
                _apply_agent_metadata(normalized, landed=landed)
                return _finalize_normalized_payload(normalized)
    if representation == "many_body_hr":
        legacy_lattice = payload.get("lattice", _default_lattice())
        lattice_description = _normalize_lattice_description(payload, legacy_lattice)
        hamiltonian_description = _normalize_many_body_hr_representation(payload)
        user_notes = payload.get("user_notes", "")
        return {
            **_finalize_normalized_payload(
                _copy_passthrough_fields(
                    payload,
                    {
            "system": {"name": payload.get("name", ""), "units": payload.get("units", "arb.")},
            "local_hilbert": {"dimension": int(payload.get("local_dim", 4)), "uniform": True},
            "lattice": legacy_lattice,
            "lattice_description": lattice_description,
            "local_term": dict(hamiltonian_description),
            "hamiltonian_description": hamiltonian_description,
            "parameters": payload.get("parameters", {}),
            "symmetry_hints": payload.get("symmetry_hints", []),
            "user_required_symmetries": payload.get("user_required_symmetries", []),
            "allowed_breaking": payload.get("allowed_breaking", []),
            "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
            "timeouts": dict(DEFAULT_TIMEOUTS),
            "user_notes": user_notes,
            "coordinate_convention": dict(payload.get("coordinate_convention", _default_coordinate_convention())),
            "magnetic_order": dict(payload.get("magnetic_order", _default_magnetic_order())),
            "basis_semantics": dict(hamiltonian_description["basis_semantics"]),
            "basis_order": hamiltonian_description["basis_order"],
            "provenance": {
                "source_mode": payload.get("source_mode", representation),
                "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "interaction": payload.get("interaction"),
                    },
                )
            )
        }
    support = payload.get("support", [])
    support = _normalize_support(support)
    if not support and representation != "natural_language":
        raise ValueError("support must be supplied for operator or matrix inputs")
    value = _require_representation_value(payload, representation)
    local_dimension = int(payload.get("local_dim", 2))
    user_notes = payload.get("user_notes", "")
    if representation == "natural_language":
        local_dimension = _infer_local_dimension_from_text(value, local_dimension)
        if not user_notes:
            user_notes = value
    legacy_lattice = payload.get("lattice", _default_lattice())
    lattice_description = _normalize_lattice_description(payload, legacy_lattice)
    hamiltonian_description = {
        "support": support,
        "representation": {
            "kind": representation,
            "value": value,
        },
    }
    coordinate_convention = dict(payload.get("coordinate_convention", _default_coordinate_convention()))
    magnetic_order = dict(payload.get("magnetic_order", _default_magnetic_order()))
    return _finalize_normalized_payload(_copy_passthrough_fields(payload, {
        "system": {"name": payload.get("name", ""), "units": payload.get("units", "arb.")},
        "local_hilbert": {"dimension": local_dimension, "uniform": True},
        "lattice": legacy_lattice,
        "lattice_description": lattice_description,
        "local_term": dict(hamiltonian_description),
        "hamiltonian_description": hamiltonian_description,
        "parameters": payload.get("parameters", {}),
        "symmetry_hints": payload.get("symmetry_hints", []),
        "user_required_symmetries": payload.get("user_required_symmetries", []),
        "allowed_breaking": payload.get("allowed_breaking", []),
        "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
        "timeouts": dict(DEFAULT_TIMEOUTS),
        "user_notes": user_notes,
        "coordinate_convention": coordinate_convention,
        "magnetic_order": magnetic_order,
        "unsupported_features": list(payload.get("unsupported_features", [])),
        "provenance": {
            "source_mode": payload.get("source_mode", representation),
            "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "interaction": payload.get("interaction"),
    }))


def _load_payload(path):
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--freeform", default=None)
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-family", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    args = parser.parse_args()
    if args.freeform is not None:
        print(
            json.dumps(
                normalize_freeform_text(
                    args.freeform,
                    source_path=args.source_path,
                    selected_model_candidate=args.selected_model_candidate,
                    selected_local_bond_family=args.selected_local_bond_family,
                    selected_coordinate_convention=args.selected_coordinate_convention,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    payload = _load_payload(args.input) if args.input else json.load(sys.stdin)
    print(json.dumps(normalize_input(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
