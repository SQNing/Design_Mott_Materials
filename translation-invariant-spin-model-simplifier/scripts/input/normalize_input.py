#!/usr/bin/env python3
import argparse
from copy import deepcopy
import json
import re
import sys
from datetime import datetime, timezone
from collections.abc import Iterable, Mapping
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from input.agent_fallback import apply_agent_inferred_patch, build_agent_inferred
    from input.agent_document_normalization_template import build_agent_document_normalization_template
    from input.document_input_protocol import (
        build_intermediate_record,
        build_intermediate_record_from_agent_normalized,
        detect_input_kind,
        expression_has_unresolved_parameters,
        land_intermediate_record,
    )
    from common.classical_bond_label_resolution import resolve_input_acceptance_classical_bond_label
    from common.lattice_structure_builder import build_lattice_structure, build_symmetry_record
    from common.onsite_terms import derive_canonical_onsite_terms_from_normalized_payload
    from common.rotating_frame_realization import resolve_rotating_frame_realization
    from common.term_attachment_builder import build_term_attachments
else:
    from .agent_fallback import apply_agent_inferred_patch, build_agent_inferred
    from .agent_document_normalization_template import build_agent_document_normalization_template
    from .document_input_protocol import (
        build_intermediate_record,
        build_intermediate_record_from_agent_normalized,
        detect_input_kind,
        expression_has_unresolved_parameters,
        land_intermediate_record,
    )
    from common.classical_bond_label_resolution import resolve_input_acceptance_classical_bond_label
    from common.lattice_structure_builder import build_lattice_structure, build_symmetry_record
    from common.onsite_terms import derive_canonical_onsite_terms_from_normalized_payload
    from common.rotating_frame_realization import resolve_rotating_frame_realization
    from common.term_attachment_builder import build_term_attachments


DEFAULT_TIMEOUTS = {
    "simplification_seconds": 600,
    "projection_seconds": 300,
    "classical_solver_seconds": 600,
}

SUPPORTED_REPRESENTATIONS = {"operator", "operator_channel_collection", "matrix", "natural_language", "many_body_hr"}
CANONICAL_SCHEMA_VERSION = "lattice-term-contract/v1"
LEGACY_CONTRACT_KEYS = {
    "bond_label",
    "classical_bond_label",
    "model_bond_label",
    "solver_bond_label",
    "selected_local_bond_bond_label",
    "bond_orbit_shell_map",
    "bond_orbit_representative_map",
    "multipole_class",
    "multipole_classes",
    "q_path_lattice_class",
    "adapter_bond_label",
    "input_bond_label",
}


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
        "label_to_bond_orbit_overrides": {},
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


def _as_mapping(value):
    return value if isinstance(value, Mapping) else {}


def _scrub_legacy_contract_keys(value):
    if isinstance(value, Mapping):
        return {
            key: _scrub_legacy_contract_keys(child)
            for key, child in value.items()
            if str(key) not in LEGACY_CONTRACT_KEYS
        }
    if isinstance(value, list):
        return [_scrub_legacy_contract_keys(item) for item in value]
    return value


def _basis_order_for_dimension(dimension):
    if int(dimension) == 2:
        return ["up", "down"]
    return [f"state:{index}" for index in range(int(dimension))]


def _local_dimension_from_payload(payload):
    local_hilbert = _as_mapping(payload.get("local_hilbert"))
    for key in ("dimension", "local_dimension", "local_dim"):
        value = local_hilbert.get(key) if key in local_hilbert else payload.get(key)
        if value is None:
            continue
        try:
            dimension = int(value)
        except (TypeError, ValueError):
            continue
        if dimension > 0:
            return dimension
    return 2


def _site_refs_from_support_ref(support_ref):
    if isinstance(support_ref, (str, bytes)) or not isinstance(support_ref, Iterable):
        return []
    refs = []
    for item in support_ref:
        text = str(item).strip()
        if text and text not in refs:
            refs.append(text)
    return refs


def _site_refs_from_numeric_support(support):
    if isinstance(support, (str, bytes)) or not isinstance(support, Iterable):
        return []
    refs = []
    for item in support:
        if isinstance(item, bool):
            continue
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        ref = f"site:{index}"
        if ref not in refs:
            refs.append(ref)
    return refs


def _append_unique(target, values):
    for value in values:
        text = str(value).strip()
        if text and text not in target:
            target.append(text)
    return target


def _document_record_from_payload(payload):
    record = payload.get("document_intermediate")
    return record if isinstance(record, Mapping) else {}


def _source_model_for_contract(payload):
    document_record = _document_record_from_payload(payload)
    if document_record:
        return deepcopy(document_record)

    hamiltonian_model = {}
    if isinstance(payload.get("bond_terms"), list):
        hamiltonian_model["bond_terms"] = deepcopy(payload.get("bond_terms"))
    elif isinstance(payload.get("hamiltonian_description"), Mapping):
        hamiltonian_model["operator_expression"] = payload["hamiltonian_description"].get("representation", {}).get("value", "")

    return {
        "source_document": {
            "source_kind": payload.get("provenance", {}).get("source_mode"),
            "source_path": payload.get("document_source_path"),
        },
        "lattice_model": deepcopy(payload.get("lattice")) if isinstance(payload.get("lattice"), Mapping) else {},
        "hamiltonian_model": hamiltonian_model,
        "parameter_registry": deepcopy(payload.get("parameters")) if isinstance(payload.get("parameters"), Mapping) else {},
    }


def _collect_site_refs(payload, source_model, lattice_structure):
    refs = []
    local_hilbert = _as_mapping(payload.get("local_hilbert"))
    for site in list(local_hilbert.get("sites") or []):
        if isinstance(site, Mapping):
            _append_unique(refs, [site.get("site_ref")])

    hamiltonian_model = _as_mapping(source_model.get("hamiltonian_model"))
    for term in list(hamiltonian_model.get("bond_terms") or []):
        if not isinstance(term, Mapping):
            continue
        _append_unique(refs, _site_refs_from_support_ref(term.get("support_ref")))
        if not term.get("support_ref"):
            source = term.get("source")
            target = term.get("target")
            if source is not None and target is not None:
                _append_unique(refs, _site_refs_from_numeric_support([source, target]))

    for key in ("local_term", "hamiltonian_description"):
        record = _as_mapping(payload.get(key))
        _append_unique(refs, _site_refs_from_numeric_support(record.get("support")))

    for site in list(_as_mapping(lattice_structure).get("basis_sites") or []):
        if isinstance(site, Mapping):
            _append_unique(refs, [site.get("site_ref")])

    for orbit in list(_as_mapping(lattice_structure).get("bond_orbits") or []):
        if not isinstance(orbit, Mapping):
            continue
        representative = _as_mapping(orbit.get("representative"))
        source = representative.get("source")
        target = representative.get("target")
        if source is not None and target is not None:
            _append_unique(refs, _site_refs_from_numeric_support([source, target]))

    if not refs:
        refs.append("site:0")
    return refs


def _canonical_local_hilbert(payload, source_model, lattice_structure):
    local_hilbert = _as_mapping(payload.get("local_hilbert"))
    if local_hilbert.get("sites") and local_hilbert.get("basis_registry"):
        return deepcopy(local_hilbert)

    dimension = _local_dimension_from_payload(payload)
    basis_ref = "basis:spin_s_half" if dimension == 2 else f"basis:local_dim_{dimension}"
    space_ref = "space:spin_s_half" if dimension == 2 else f"space:local_dim_{dimension}"
    operator_basis_ref = "op_basis:spin_cartesian" if dimension == 2 else f"op_basis:local_matrix_dim_{dimension}"
    classical_space_ref = "classical_space:spin_unit_vector" if dimension == 2 else f"classical_space:cp{dimension - 1}"
    site_refs = _collect_site_refs(payload, source_model, lattice_structure)

    basis_kind = "spin_multiplet" if dimension == 2 else "retained_local_basis"
    classical_space = (
        {"kind": "unit_vector_sphere", "dimension": 3}
        if dimension == 2
        else {"kind": "complex_projective_space", "dimension": dimension}
    )
    operator_basis = (
        {"kind": "spin_cartesian", "basis_order": ["Sx", "Sy", "Sz"]}
        if dimension == 2
        else {"kind": "dense_local_matrix_units", "dimension": dimension}
    )

    return {
        "sites": [
            {
                "site_ref": site_ref,
                "space_ref": space_ref,
                "basis_ref": basis_ref,
                "classical_space_ref": classical_space_ref,
                "operator_basis_refs": [operator_basis_ref],
            }
            for site_ref in site_refs
        ],
        "basis_registry": {
            basis_ref: {
                "kind": basis_kind,
                "dimension": dimension,
                "basis_order": _basis_order_for_dimension(dimension),
            }
        },
        "operator_bases": {
            operator_basis_ref: operator_basis,
        },
        "classical_spaces": {
            classical_space_ref: classical_space,
        },
    }


def _input_local_hilbert(payload, default_dimension):
    declared = payload.get("local_hilbert")
    if (
        isinstance(declared, Mapping)
        and declared.get("sites")
        and declared.get("basis_registry")
    ):
        return deepcopy(declared)
    return {"dimension": int(default_dimension), "uniform": True}


def _orbit_ref_from_term(term):
    attach_to = _as_mapping(term.get("attach_to")) if isinstance(term, Mapping) else {}
    return (
        attach_to.get("orbit_ref")
        or term.get("orbit_ref")
        or term.get("bond_orbit_ref")
        if isinstance(term, Mapping)
        else None
    )


def _augment_lattice_structure_with_term_orbits(lattice_structure, source_model):
    lattice_structure = deepcopy(lattice_structure) if isinstance(lattice_structure, Mapping) else {}
    bond_orbits = list(lattice_structure.get("bond_orbits") or [])
    known_refs = {str(orbit.get("orbit_ref") or orbit.get("bond_orbit_ref")) for orbit in bond_orbits if isinstance(orbit, Mapping)}
    hamiltonian_model = _as_mapping(source_model.get("hamiltonian_model"))
    for term in list(hamiltonian_model.get("bond_terms") or []):
        if not isinstance(term, Mapping):
            continue
        orbit_ref = _orbit_ref_from_term(term)
        if not orbit_ref or str(orbit_ref) in known_refs:
            continue
        source = term.get("source", 0)
        target = term.get("target", 1)
        translation = list(term.get("translation") or [0, 0, 0])
        bond_orbits.append(
            {
                "orbit_ref": str(orbit_ref),
                "kind": "pair",
                "directed": True,
                "orientation_convention": "source_to_target",
                "source_labels": [str(term.get("source_label") or term.get("document_label") or term.get("bond_ref") or orbit_ref)],
                "shell": term.get("shell"),
                "representative": {
                    "source": int(source),
                    "target": int(target),
                    "translation": [int(component) for component in translation],
                },
                "members": [
                    {
                        "source": int(source),
                        "target": int(target),
                        "translation": [int(component) for component in translation],
                        "generated_by_operation_ref": "symmetry-operation:identity",
                    }
                ],
                "reverse_orientation": {
                    "kind": "transpose_and_swap",
                    "source_target_swap": True,
                    "transpose": True,
                    "translation": [-int(component) for component in translation],
                },
                "selection_aliases": [str(orbit_ref)],
            }
        )
        known_refs.add(str(orbit_ref))
    lattice_structure["bond_orbits"] = bond_orbits
    return lattice_structure


def _canonical_parameters(payload, source_model):
    parameters = payload.get("parameters")
    if isinstance(parameters, Mapping):
        return deepcopy(parameters)
    registry = source_model.get("parameter_registry")
    if isinstance(registry, Mapping):
        return deepcopy(registry)
    return {}


def _canonical_provenance(payload, source_model):
    provenance = deepcopy(payload.get("provenance")) if isinstance(payload.get("provenance"), Mapping) else {}
    sources = list(provenance.get("sources") or [])
    source_document = _as_mapping(source_model.get("source_document"))
    source_kind = source_document.get("source_kind") or provenance.get("source_mode")
    source_path = source_document.get("source_path") or payload.get("document_source_path")
    if source_kind or source_path:
        sources.append(
            {
                "source_kind": source_kind,
                "source_path": source_path,
            }
        )
    if sources:
        provenance["sources"] = sources
    if "parsed_at" not in provenance:
        provenance["parsed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return provenance


def _canonical_solver_request(term_attachments, payload, lattice_structure):
    symmetry_repair = payload.get("symmetry_repair", False)
    if not isinstance(symmetry_repair, bool):
        raise ValueError("invalid-symmetry-repair-flag")
    term_sets = list(_as_mapping(term_attachments).get("term_sets") or [])
    selected_term_set_ref = term_sets[0].get("term_set_ref") if term_sets else None
    selected_bond_orbit_refs = []
    for term_set in term_sets[:1]:
        _append_unique(selected_bond_orbit_refs, term_set.get("bond_orbit_refs") or [])

    return {
        "task": payload.get("solver_task") or "classical_ground_state",
        "preferred_methods": list(payload.get("preferred_solver_methods") or ["auto"]),
        "outputs": list(payload.get("requested_outputs") or ["classical_state"]),
        "selected_term_set_ref": selected_term_set_ref,
        "selected_term_refs": [],
        "selected_bond_orbit_refs": selected_bond_orbit_refs,
        "selection_policy": "term_set_then_explicit_refs",
        "symmetry_repair": symmetry_repair,
    }


def _canonical_contract_overlay(payload):
    source_model = _source_model_for_contract(payload)
    lattice_structure = (
        deepcopy(source_model.get("lattice_structure"))
        if isinstance(source_model.get("lattice_structure"), Mapping)
        else build_lattice_structure(source_model)
    )
    lattice_structure = _augment_lattice_structure_with_term_orbits(lattice_structure, source_model)
    symmetry = (
        deepcopy(source_model.get("symmetry"))
        if isinstance(source_model.get("symmetry"), Mapping)
        else build_symmetry_record(source_model)
    )
    local_hilbert = _canonical_local_hilbert(payload, source_model, lattice_structure)
    term_attachments = build_term_attachments(source_model, lattice_structure, local_hilbert)

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "local_hilbert": local_hilbert,
        "lattice_structure": lattice_structure,
        "symmetry": symmetry,
        "term_attachments": term_attachments,
        "solver_request": _canonical_solver_request(term_attachments, payload, lattice_structure),
        "parameters": _canonical_parameters(payload, source_model),
        "provenance": _canonical_provenance(payload, source_model),
    }


def _finalize_normalized_payload(normalized):
    finalized = dict(normalized)
    onsite_terms = derive_canonical_onsite_terms_from_normalized_payload(finalized)
    if onsite_terms:
        finalized["onsite_terms"] = onsite_terms
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
    finalized.update(_canonical_contract_overlay(finalized))
    return _scrub_legacy_contract_keys(finalized)


def _copy_passthrough_fields(source, destination):
    for key in (
        "classical_bond_label",
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
        "onsite_terms",
        "document_intermediate",
        "document_source_text",
        "document_source_path",
        "selected_model_candidate",
        "selected_local_bond_bond_label",
        "bond_terms",
        "explicit_bond_graph",
        "selected_coordinate_convention",
        "agent_normalization_request",
        "symmetry_repair",
    ):
        if key in source:
            destination[key] = source[key]
    return destination


def _attach_classical_bond_label_resolution(payload, bond_label_gate):
    if not isinstance(bond_label_gate, dict) or bond_label_gate.get("status") != "resolved":
        return payload
    payload["classical_bond_label"] = bond_label_gate["classical_bond_label"]
    return payload


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
        "operator_channel_collection": "expressions",
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
    pair_identity_mode = payload.get("pair_identity_mode")
    local_level_to_site_mapping_file = payload.get("local_level_to_site_mapping_file")
    if not structure_file:
        raise ValueError("many_body_hr payload requires structure_file")
    if not hamiltonian_file:
        raise ValueError("many_body_hr payload requires hamiltonian_file")

    representation = {
        "kind": "many_body_hr",
        "structure_file": str(structure_file),
        "hamiltonian_file": str(hamiltonian_file),
    }
    if pair_identity_mode is not None:
        representation["pair_identity_mode"] = str(pair_identity_mode)
    if local_level_to_site_mapping_file is not None:
        representation["local_level_to_site_mapping_file"] = str(local_level_to_site_mapping_file)
    return {
        "model_bond_label": "cpn_pair_model",
        "adapter_bond_label": "many_body_hr",
        "adapter_role": "legacy_storage_input",
        "support": [],
        "representation": representation,
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


def _natural_language_base_payload(text, *, local_dimension, user_notes, source_mode, system_units="arb."):
    lattice_description = {"kind": "natural_language", "value": text}
    hamiltonian_description = {
        "support": [],
        "representation": {"kind": "natural_language", "value": text},
    }
    return {
        "system": {"name": "", "units": system_units},
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


def _human_readable_agent_fallback_payload(
    text,
    *,
    record,
    landed,
    local_dimension,
    source_mode,
    system_units="unspecified",
):
    proposal = _build_agent_fallback_proposal(
        text,
        record=record,
        selected_coordinate_convention=(record or {}).get("selected_coordinate_convention"),
        selected_local_bond_bond_label=(record or {}).get("selected_local_bond_bond_label"),
    )
    normalized = _natural_language_base_payload(
        text,
        local_dimension=local_dimension,
        user_notes=text,
        source_mode=source_mode,
        system_units=system_units,
    )
    normalized["coordinate_convention"] = dict(
        landed.get("coordinate_convention", _default_coordinate_convention())
    )
    normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
    normalized["interaction"] = {
        "status": "needs_input",
        "id": "agent_fallback_review",
        "question": (
            "The input was recognized as human-readable but could not be landed safely "
            "without agent assistance."
        ),
    }
    normalized["document_intermediate"] = record
    normalized["agent_normalization_request"] = {
        "status": "recommended",
        "id": "agent_document_normalization",
        "stage": "document_ingestion",
        "source_kind": "natural_language",
        "reason": "The input was recognized as human-readable but not yet script-consumable.",
        "target_schema": "agent_normalized_document",
        "prompt_notes": "Translate the readable input into the repository's constrained structured intermediate form.",
    }
    _apply_agent_metadata(normalized, proposal=proposal, accepted=False)
    return _finalize_normalized_payload(normalized)


def _landed_human_readable_input_needs_agent(record, landed, description):
    if not isinstance(landed, dict):
        return False
    if landed.get("interaction", {}).get("status") == "needs_input":
        return True
    if landed.get("agent_inferred") is not None:
        return True
    if _looks_like_spin_operator_expression(description):
        representation = str(landed.get("representation", ""))
        if representation == "operator":
            expression = str(landed.get("expression", "") or "").strip()
            if not expression:
                return True
    return False


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


def _document_structured_lattice(record):
    lattice_model = record.get("lattice_model", {}) if isinstance(record, dict) else {}
    if not isinstance(lattice_model, dict) or not lattice_model:
        return None
    return deepcopy(lattice_model)


def _build_agent_fallback_proposal(
    text,
    *,
    record,
    selected_coordinate_convention=None,
    selected_local_bond_bond_label=None,
):
    return build_agent_inferred(
        source_text=text,
        intermediate_record=record,
        normalization_context={
            "selected_coordinate_convention": selected_coordinate_convention,
            "selected_local_bond_bond_label": selected_local_bond_bond_label,
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


def _looks_like_spin_operator_expression(text):
    expression = str(text or "").strip()
    if not expression:
        return False
    return re.search(
        r"(?:S[xyzpm]@\s*-?\d+|S_[A-Za-z]\^[xyz\+\-]|\\gamma_\{ij\}|gamma_\{ij\}|\\sum_|J_[^\\s=]+)",
        expression,
    ) is not None


def _document_interaction_is_simple_user_selection(interaction):
    if not isinstance(interaction, dict):
        return False
    return interaction.get("id") in {
        "model_candidate_selection",
        "bond_orbit_selection",
        "coordinate_convention_selection",
        "wavevector_selection",
        "wavevector_units_selection",
    }


def _should_request_agent_human_input(record, landed):
    interaction = (landed or {}).get("interaction")
    if isinstance(interaction, dict) and interaction.get("status") == "needs_input":
        return not _document_interaction_is_simple_user_selection(interaction)
    representation = (landed or {}).get("representation")
    if representation == "operator":
        if expression_has_unresolved_parameters(
            (landed or {}).get("expression", ""),
            (landed or {}).get("parameters", {}),
        ):
            return True
        return not _looks_like_spin_operator_expression((landed or {}).get("expression", ""))
    if representation == "operator_channel_collection":
        expressions = list((landed or {}).get("expressions", []))
        if not expressions:
            return True
        for entry in expressions:
            if expression_has_unresolved_parameters(
                (entry or {}).get("expression", ""),
                (landed or {}).get("parameters", {}),
            ):
                return True
            if not _looks_like_spin_operator_expression((entry or {}).get("expression", "")):
                return True
    return False


def _should_request_agent_normalization(record, landed):
    source_kind = ((record or {}).get("source_document") or {}).get("source_kind")
    if source_kind != "tex_document":
        return _should_request_agent_human_input(record, landed)
    return _should_request_agent_human_input(record, landed)


def _should_request_agent_document_normalization(record, landed):
    return _should_request_agent_normalization(record, landed)


def _build_agent_document_normalization_request(record, landed):
    interaction = (landed or {}).get("interaction")
    model_candidates = [
        candidate.get("name")
        for candidate in list((record or {}).get("model_candidates") or [])
        if isinstance(candidate, dict) and candidate.get("name")
    ]
    blocking_reason = (
        interaction.get("question")
        if isinstance(interaction, dict) and interaction.get("status") == "needs_input"
        else (
            "The document was parsed as a paper-style source, but deterministic extraction did not "
            "produce a trustworthy runnable spin-operator expression."
        )
    )
    template_bundle = build_agent_document_normalization_template()
    return {
        "status": "recommended",
        "id": "agent_document_normalization",
        "stage": "document_ingestion",
        "source_kind": "tex_document",
        "reason": blocking_reason,
        "target_schema": "agent_normalized_document",
        "template_version": template_bundle["template_version"],
        "template": template_bundle["template"],
        "example_payload": template_bundle["example_payload"],
        "prompt_notes": template_bundle["prompt_notes"],
        "preferred_output_fields": [
            "source_document",
            "model_candidates",
            "candidate_models",
            "parameter_registry",
            "system_context",
            "lattice_model",
            "unresolved_items",
            "unsupported_features",
        ],
        "selection_context": {
            "selected_model_candidate": (record or {}).get("selected_model_candidate"),
            "selected_local_bond_bond_label": (record or {}).get("selected_local_bond_bond_label"),
            "selected_coordinate_convention": (record or {}).get("selected_coordinate_convention"),
        },
        "deterministic_hints": {
            "model_candidates": model_candidates,
            "unsupported_features": list((record or {}).get("unsupported_features", [])),
            "current_interaction_id": interaction.get("id") if isinstance(interaction, dict) else None,
        },
    }


def _normalize_document_style_natural_language(
    text,
    *,
    source_path=None,
    selected_model_candidate=None,
    selected_local_bond_bond_label=None,
    selected_coordinate_convention=None,
    local_dimension,
    source_mode,
):
    def _document_system_units(document_record):
        return (
            document_record.get("system_context", {}).get("coefficient_units")
            if isinstance(document_record, dict)
            else None
        ) or "unspecified"

    record = build_intermediate_record(
        source_text=text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_bond_label=selected_local_bond_bond_label,
        selected_coordinate_convention=selected_coordinate_convention,
    )
    lattice_text = _document_lattice_text(record, text)
    structured_lattice = _document_structured_lattice(record)
    lattice_description_payload = structured_lattice or {"kind": "natural_language", "value": lattice_text}
    legacy_lattice = structured_lattice or _default_lattice()
    landed = land_intermediate_record(record)
    if _should_request_agent_document_normalization(record, landed):
        request = _build_agent_document_normalization_request(record, landed)
        normalized = _natural_language_base_payload(
            text,
            local_dimension=local_dimension,
            user_notes=text,
            source_mode=source_mode,
            system_units=_document_system_units(record),
        )
        normalized["lattice"] = legacy_lattice
        normalized["lattice_description"] = lattice_description_payload
        normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
        normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
        normalized["interaction"] = {
            "status": "needs_input",
            "id": request["id"],
            "question": request["reason"],
        }
        normalized["unsupported_features"] = list(landed.get("unsupported_features", []))
        normalized["document_intermediate"] = record
        normalized["agent_normalization_request"] = request
        _apply_agent_metadata(normalized, landed=landed)
        return _finalize_normalized_payload(normalized)
    if landed.get("interaction", {}).get("status") == "needs_input":
        normalized = _natural_language_base_payload(
            text,
            local_dimension=local_dimension,
            user_notes=text,
            source_mode=source_mode,
            system_units=_document_system_units(record),
        )
        normalized["lattice"] = legacy_lattice
        normalized["lattice_description"] = lattice_description_payload
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
            "local_dim": int(local_dimension),
            "support": list(landed.get("support", [])),
            "expression": landed.get("expression", ""),
            "lattice": legacy_lattice,
            "lattice_description": lattice_description_payload,
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
            "selected_local_bond_bond_label": selected_local_bond_bond_label,
            "selected_coordinate_convention": selected_coordinate_convention,
            "units": _document_system_units(record),
            }
            if landed["representation"] != "operator_channel_collection"
            else {
                "representation": landed["representation"],
                "local_dim": int(local_dimension),
                "support": list(landed.get("support", [])),
                "expressions": list(landed.get("expressions", [])),
                "lattice": legacy_lattice,
                "lattice_description": lattice_description_payload,
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
                "selected_local_bond_bond_label": selected_local_bond_bond_label,
                "selected_coordinate_convention": selected_coordinate_convention,
                "units": _document_system_units(record),
            }
        )
    )
def normalize_freeform_text(
    text,
    *,
    source_path=None,
    selected_classical_bond_label=None,
    selected_model_candidate=None,
    selected_local_bond_bond_label=None,
    selected_coordinate_convention=None,
):
    text = (text or "").strip()
    if not text:
        raise ValueError("freeform input must be non-empty")
    detected_kind = detect_input_kind(text, source_path=source_path).get("source_kind")
    local_dimension = _infer_local_dimension_from_text(text)
    if detected_kind == "tex_document":
        return _normalize_document_style_natural_language(
            text,
            source_path=source_path,
            selected_model_candidate=selected_model_candidate,
            selected_local_bond_bond_label=selected_local_bond_bond_label,
            selected_coordinate_convention=selected_coordinate_convention,
            local_dimension=local_dimension,
            source_mode="freeform",
        )
    route_hint = _inspect_many_body_hr_text(text)
    if route_hint is not None and route_hint.get("status") == "needs_input":
        return _natural_language_many_body_hr_needs_input_payload(
            text,
            local_dimension=_infer_local_dimension_from_text(text),
            user_notes=text,
            source_mode="freeform",
            route_hint=route_hint,
        )
    if route_hint is not None and route_hint.get("status") == "ready":
        return _normalize_ready_many_body_hr_hint(
            text,
            source_mode="freeform",
            user_notes=text,
            route_hint=route_hint,
        )
    record = build_intermediate_record(
        source_text=text,
        source_path=source_path,
        selected_model_candidate=selected_model_candidate,
        selected_local_bond_bond_label=selected_local_bond_bond_label,
        selected_coordinate_convention=selected_coordinate_convention,
    )
    proposal = _build_agent_fallback_proposal(
        text,
        record=record,
        selected_coordinate_convention=selected_coordinate_convention,
        selected_local_bond_bond_label=selected_local_bond_bond_label,
    )
    if _can_accept_helper_many_body_route(record, proposal):
        patched_payload = apply_agent_inferred_patch(
            {
                "representation": "natural_language",
                "description": text,
                "source_path": source_path,
                "classical_bond_label": selected_classical_bond_label,
                "selected_model_candidate": selected_model_candidate,
                "selected_local_bond_bond_label": selected_local_bond_bond_label,
                "selected_coordinate_convention": selected_coordinate_convention,
                "user_notes": text,
                "source_mode": "freeform",
            },
            proposal,
        )
        normalized = normalize_input(patched_payload)
        _apply_agent_metadata(normalized, proposal=proposal, accepted=True)
        return normalized
    landed = land_intermediate_record(record)
    if _landed_human_readable_input_needs_agent(record, landed, text):
        return _human_readable_agent_fallback_payload(
            text,
            record=record,
            landed=landed,
            local_dimension=local_dimension,
            source_mode="freeform",
        )
    normalized = _natural_language_base_payload(
        text,
        local_dimension=local_dimension,
        user_notes=text,
        source_mode="freeform",
    )
    bond_label_gate = resolve_input_acceptance_classical_bond_label(
        payload={
            "representation": "natural_language",
            "classical_bond_label": selected_classical_bond_label,
        }
    )
    if landed.get("interaction", {}).get("status") == "needs_input" or landed.get("agent_inferred") is not None:
        _attach_classical_bond_label_resolution(normalized, bond_label_gate)
        normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
        normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
        if landed.get("interaction") is not None:
            normalized["interaction"] = landed["interaction"]
        normalized["document_intermediate"] = record
        _apply_agent_metadata(normalized, landed=landed)
        return _finalize_normalized_payload(normalized)
    if bond_label_gate.get("status") == "needs_input":
        normalized["interaction"] = dict(bond_label_gate["interaction"])
        return _finalize_normalized_payload(normalized)
    _attach_classical_bond_label_resolution(normalized, bond_label_gate)
    return _finalize_normalized_payload(normalized)


def _normalize_input_impl(payload):
    representation = payload.get("representation", "operator")
    if representation not in SUPPORTED_REPRESENTATIONS:
        raise ValueError("unsupported representation")
    if representation == "natural_language":
        if payload.get("agent_normalized_document") is not None and payload.get("document_intermediate") is None:
            payload = {
                **payload,
                "document_intermediate": build_intermediate_record_from_agent_normalized(
                    payload.get("agent_normalized_document", {}),
                    source_text=str(payload.get("description", "") or ""),
                    source_path=payload.get("source_path"),
                    selected_model_candidate=payload.get("selected_model_candidate"),
                    selected_local_bond_bond_label=payload.get("selected_local_bond_bond_label"),
                    selected_coordinate_convention=payload.get("selected_coordinate_convention"),
                ),
            }
        description = _require_representation_value(payload, representation)
        source_path = payload.get("source_path")
        selected_model_candidate = payload.get("selected_model_candidate")
        selected_local_bond_bond_label = payload.get("selected_local_bond_bond_label")
        selected_coordinate_convention = payload.get("selected_coordinate_convention")
        selected_classical_bond_label = payload.get("classical_bond_label")
        route_hint = _inspect_many_body_hr_text(description)
        if payload.get("document_intermediate") is not None:
            document_record = payload["document_intermediate"]
            landed = land_intermediate_record(document_record)
            if landed.get("interaction", {}).get("status") == "needs_input":
                normalized = normalize_freeform_text(
                    description,
                    source_path=source_path,
                    selected_classical_bond_label=selected_classical_bond_label,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_bond_label=selected_local_bond_bond_label,
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
            inferred_local_dimension = _infer_local_dimension_from_text(
                description,
                int(payload.get("local_dim", 2)),
            )
            structured_lattice = _document_structured_lattice(document_record)
            lattice_description_payload = payload.get("lattice_description")
            if lattice_description_payload is None:
                lattice_description_payload = (
                    structured_lattice
                    or {
                        "kind": "natural_language",
                        "value": _document_lattice_text(document_record, description),
                    }
                )
            payload = {
                **payload,
                **landed,
                "representation": landed["representation"],
                "local_dim": inferred_local_dimension,
                "lattice": structured_lattice or payload.get("lattice"),
                "lattice_description": lattice_description_payload,
            }
            representation = payload["representation"]
        else:
            detected_kind = detect_input_kind(description, source_path=source_path).get("source_kind")
            if detected_kind == "tex_document":
                inferred_local_dimension = _infer_local_dimension_from_text(
                    description,
                    int(payload.get("local_dim", 2)),
                )
                return _normalize_document_style_natural_language(
                    description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_bond_label=selected_local_bond_bond_label,
                    selected_coordinate_convention=selected_coordinate_convention,
                    local_dimension=inferred_local_dimension,
                    source_mode=payload.get("source_mode", representation),
                )
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
            if _looks_like_spin_operator_expression(description):
                record = build_intermediate_record(
                    source_text=description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_bond_label=selected_local_bond_bond_label,
                    selected_coordinate_convention=selected_coordinate_convention,
                )
                landed = land_intermediate_record(record)
                return _human_readable_agent_fallback_payload(
                    description,
                    record=record,
                    landed=landed,
                    local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                    source_mode=payload.get("source_mode", representation),
                )
            bond_label_gate = resolve_input_acceptance_classical_bond_label(payload=payload)
            if bond_label_gate.get("status") == "needs_input":
                record = build_intermediate_record(
                    source_text=description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_bond_label=selected_local_bond_bond_label,
                    selected_coordinate_convention=selected_coordinate_convention,
                )
                landed = land_intermediate_record(record)
                if _landed_human_readable_input_needs_agent(record, landed, description):
                    return _human_readable_agent_fallback_payload(
                        description,
                        record=record,
                        landed=landed,
                        local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                        source_mode=payload.get("source_mode", representation),
                    )
                if _looks_like_spin_operator_expression(description):
                    return _human_readable_agent_fallback_payload(
                        description,
                        record=record,
                        landed=landed,
                        local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                        source_mode=payload.get("source_mode", representation),
                    )
                normalized = _natural_language_base_payload(
                    description,
                    local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                    user_notes=payload.get("user_notes", "") or description,
                    source_mode=payload.get("source_mode", representation),
                )
                normalized["interaction"] = dict(bond_label_gate["interaction"])
                return _finalize_normalized_payload(normalized)
            if _looks_like_spin_operator_expression(description):
                record = build_intermediate_record(
                    source_text=description,
                    source_path=source_path,
                    selected_model_candidate=selected_model_candidate,
                    selected_local_bond_bond_label=selected_local_bond_bond_label,
                    selected_coordinate_convention=selected_coordinate_convention,
                )
                landed = land_intermediate_record(record)
                landed_expression = str(landed.get("expression", "") or "").strip()
                if landed.get("representation") == "operator" and not landed_expression:
                    return _human_readable_agent_fallback_payload(
                        description,
                        record=record,
                        landed=landed,
                        local_dimension=_infer_local_dimension_from_text(description, int(payload.get("local_dim", 2))),
                        source_mode=payload.get("source_mode", representation),
                    )
            record = build_intermediate_record(
                source_text=description,
                source_path=source_path,
                selected_model_candidate=selected_model_candidate,
                selected_local_bond_bond_label=selected_local_bond_bond_label,
                selected_coordinate_convention=selected_coordinate_convention,
            )
            proposal = _build_agent_fallback_proposal(
                description,
                record=record,
                selected_coordinate_convention=selected_coordinate_convention,
                selected_local_bond_bond_label=selected_local_bond_bond_label,
            )
            if _can_accept_helper_many_body_route(record, proposal):
                patched_payload = apply_agent_inferred_patch(payload, proposal)
                normalized = normalize_input(patched_payload)
                _apply_agent_metadata(normalized, proposal=proposal, accepted=True)
                return normalized
            record = build_intermediate_record(
                source_text=description,
                source_path=source_path,
                selected_model_candidate=selected_model_candidate,
                selected_local_bond_bond_label=selected_local_bond_bond_label,
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
                _attach_classical_bond_label_resolution(normalized, bond_label_gate)
                normalized["coordinate_convention"] = dict(landed.get("coordinate_convention", _default_coordinate_convention()))
                normalized["magnetic_order"] = dict(landed.get("magnetic_order", _default_magnetic_order()))
                if landed.get("interaction") is not None:
                    normalized["interaction"] = landed["interaction"]
                normalized["document_intermediate"] = record
                _apply_agent_metadata(normalized, landed=landed)
                return _finalize_normalized_payload(normalized)
    if representation == "many_body_hr":
        bond_label_gate = resolve_input_acceptance_classical_bond_label(payload=payload)
        legacy_lattice = payload.get("lattice", _default_lattice())
        lattice_description = _normalize_lattice_description(payload, legacy_lattice)
        hamiltonian_description = _normalize_many_body_hr_representation(payload)
        user_notes = payload.get("user_notes", "")
        return {
            **_finalize_normalized_payload(
                _attach_classical_bond_label_resolution(
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
                    ),
                    bond_label_gate,
                )
            )
        }
    should_gate_direct_structured_input = (
        representation in {"operator", "operator_channel_collection", "matrix"}
        and payload.get("document_intermediate") is None
        and payload.get("source_mode", representation) == representation
    )
    bond_label_gate = (
        resolve_input_acceptance_classical_bond_label(payload=payload)
        if should_gate_direct_structured_input
        else {"status": "unresolved", "interaction": None}
    )
    if bond_label_gate.get("status") == "needs_input":
        value = _require_representation_value(payload, representation)
        return _finalize_normalized_payload({
            "system": {"name": payload.get("name", ""), "units": payload.get("units", "arb.")},
            "local_hilbert": _input_local_hilbert(
                payload, payload.get("local_dim", 2)
            ),
            "lattice": payload.get("lattice", _default_lattice()),
            "lattice_description": _normalize_lattice_description(payload, payload.get("lattice", _default_lattice())),
            "local_term": {
                "support": payload.get("support", []),
                "representation": {"kind": representation, "value": value},
            },
            "hamiltonian_description": {
                "support": payload.get("support", []),
                "representation": {"kind": representation, "value": value},
            },
            "parameters": payload.get("parameters", {}),
            "symmetry_hints": payload.get("symmetry_hints", []),
            "user_required_symmetries": payload.get("user_required_symmetries", []),
            "allowed_breaking": payload.get("allowed_breaking", []),
            "projection": {"status": "not-needed", "heuristic": ["low-energy", "symmetry", "template"]},
            "timeouts": dict(DEFAULT_TIMEOUTS),
            "user_notes": payload.get("user_notes", "") or (value if representation == "natural_language" else ""),
            "coordinate_convention": dict(payload.get("coordinate_convention", _default_coordinate_convention())),
            "magnetic_order": dict(payload.get("magnetic_order", _default_magnetic_order())),
            "unsupported_features": list(payload.get("unsupported_features", [])),
            "provenance": {
                "source_mode": payload.get("source_mode", representation),
                "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "interaction": dict(bond_label_gate["interaction"]),
        })
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
    return _finalize_normalized_payload(
        _attach_classical_bond_label_resolution(
            _copy_passthrough_fields(payload, {
                "system": {"name": payload.get("name", ""), "units": payload.get("units", "arb.")},
                "local_hilbert": _input_local_hilbert(
                    payload, local_dimension
                ),
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
            }),
            bond_label_gate,
        )
    )


def normalize_input(payload):
    symmetry_repair = payload.get("symmetry_repair", False)
    if not isinstance(symmetry_repair, bool):
        raise ValueError("invalid-symmetry-repair-flag")
    normalized = _normalize_input_impl(payload)
    solver_request = normalized.get("solver_request")
    if not isinstance(solver_request, dict):
        raise ValueError("canonical-solver-request-unavailable")
    solver_request["symmetry_repair"] = symmetry_repair
    return normalized


def _load_payload(path):
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?")
    parser.add_argument("--freeform", default=None)
    parser.add_argument("--source-path", default=None)
    parser.add_argument("--selected-classical-bond_label", default=None)
    parser.add_argument("--selected-model-candidate", default=None)
    parser.add_argument("--selected-local-bond-bond_label", default=None)
    parser.add_argument("--selected-coordinate-convention", default=None)
    args = parser.parse_args()
    if args.freeform is not None:
        print(
            json.dumps(
                normalize_freeform_text(
                    args.freeform,
                    source_path=args.source_path,
                    selected_classical_bond_label=args.selected_classical_bond_label,
                    selected_model_candidate=args.selected_model_candidate,
                    selected_local_bond_bond_label=args.selected_local_bond_bond_label,
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
