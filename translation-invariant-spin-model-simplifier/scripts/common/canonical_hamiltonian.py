#!/usr/bin/env python3
"""Deterministic canonical representation for lattice Hamiltonians."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json

from common.bond_orbits import canonicalize_directed_bond


class CanonicalHamiltonianError(ValueError):
    """Raised when a lattice term cannot be compiled without guessing."""

    def __init__(self, code, detail=None):
        self.code = str(code)
        message = self.code if detail is None else f"{self.code}: {detail}"
        super().__init__(message)


def _site_index(value):
    text = str(value)
    if text.startswith("site:"):
        text = text.split(":", 1)[1]
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", value) from exc


def _translation(value):
    values = list(value or [0, 0, 0])
    if len(values) != 3:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", "translation-must-have-three-components")
    try:
        return [int(component) for component in values]
    except (TypeError, ValueError) as exc:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", value) from exc


def _normalized_cluster(cluster):
    records = []
    for entry in list(cluster or []):
        if not isinstance(entry, Mapping):
            raise CanonicalHamiltonianError("canonical-term-identity-unresolved", "cluster-entry-must-be-object")
        records.append(
            {
                "site": _site_index(entry.get("site", entry.get("site_ref"))),
                "translation": _translation(entry.get("translation")),
            }
        )
    if not records:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", "cluster-required")
    origin = records[0]["translation"]
    translated_by = [-int(component) for component in origin]
    normalized = [
        {
            "site": int(entry["site"]),
            "translation": [
                int(entry["translation"][axis] - origin[axis]) for axis in range(3)
            ],
        }
        for entry in records
    ]
    return normalized, translated_by


def _cluster_key(cluster):
    return tuple(
        (int(entry["site"]), tuple(int(component) for component in entry["translation"]))
        for entry in cluster
    )


def canonicalize_cluster(cluster, family):
    """Translate a cluster to the origin and apply declared simple equivalences."""

    normalized, translated_by = _normalized_cluster(cluster)
    permutation = list(range(len(normalized)))
    orientation_reversed = False

    if str(family) in {
        "bilinear_exchange_tensor",
        "bilinear_exchange_matrix",
        "pair_matrix",
        "biquadratic_exchange",
    } and len(normalized) == 2:
        source = normalized[0]["site"]
        target = normalized[1]["site"]
        relative = normalized[1]["translation"]
        directed = (source, target, tuple(relative))
        canonical = canonicalize_directed_bond(source, target, relative)
        if canonical != directed:
            reversed_cluster, reversed_translation = _normalized_cluster(list(reversed(cluster)))
            normalized = reversed_cluster
            translated_by = reversed_translation
            permutation = [1, 0]
            orientation_reversed = True

    return {
        "cluster": normalized,
        "permutation": permutation,
        "translated_by": translated_by,
        "orientation_reversed": orientation_reversed,
    }


def _parameter_value(parameters, reference):
    if reference not in parameters:
        raise CanonicalHamiltonianError("unresolved-parameter-ref", reference)
    record = parameters[reference]
    if not isinstance(record, Mapping):
        return record
    for key in ("value", "selected_value", "numeric_value"):
        if key in record:
            value = record[key]
            if isinstance(value, Mapping) and "value" in value:
                return value["value"]
            return value
    raise CanonicalHamiltonianError("unresolved-parameter-ref", reference)


def _resolve_scalar(value, parameters):
    if not isinstance(value, Mapping):
        return value
    kind = value.get("kind")
    if kind == "real":
        return float(value["value"])
    if kind == "complex":
        real = value.get("re", value.get("real", 0.0))
        imag = value.get("im", value.get("imag", 0.0))
        return complex(float(real), float(imag))
    if kind == "parameter_ref":
        return _resolve_scalar(_parameter_value(parameters, str(value.get("parameter_ref"))), parameters)
    return deepcopy(value)


def _resolve_matrix(matrix, parameters):
    if not isinstance(matrix, Mapping):
        return [[_resolve_scalar(entry, parameters) for entry in row] for row in list(matrix or [])]
    data = matrix.get("data", matrix.get("entries", []))
    rows = [[_resolve_scalar(entry, parameters) for entry in row] for row in list(data or [])]
    shape = list(matrix.get("shape") or [])
    if shape and shape != [len(rows), max((len(row) for row in rows), default=0)]:
        raise CanonicalHamiltonianError("matrix-shape-mismatch", f"declared {shape}")
    return rows


def _family_for_term(term):
    if term.get("operator_family"):
        return str(term["operator_family"])
    payload = term.get("payload") if isinstance(term.get("payload"), Mapping) else {}
    kind = str(payload.get("kind") or "")
    return {
        "bilinear_exchange_matrix": "bilinear_exchange_tensor",
        "exchange_tensor": "bilinear_exchange_tensor",
        "pair_matrix": "pair_matrix",
    }.get(kind, kind or str(term.get("operator_channel") or "generic_local_operator_tensor"))


def _cluster_for_term(term, arity_hint=None):
    if term.get("cluster"):
        return deepcopy(list(term["cluster"]))
    support = list(term.get("support_ref") or [])
    arity = int(term.get("arity", arity_hint or len(support)))
    if len(support) != arity:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", term.get("term_ref"))
    translations = list(term.get("translations") or [])
    if not translations:
        translations = [[0, 0, 0] for _ in support]
    if arity == 2 and term.get("translation") is not None:
        translations[1] = term.get("translation")
    return [
        {"site": _site_index(site_ref), "translation": _translation(translations[index])}
        for index, site_ref in enumerate(support)
    ]


def _coefficient_for_term(term, parameters):
    if "coefficient" in term:
        return _resolve_scalar(term["coefficient"], parameters)
    payload = term.get("payload") if isinstance(term.get("payload"), Mapping) else {}
    if "matrix" in payload:
        return _resolve_matrix(payload["matrix"], parameters)
    if "coefficient" in payload:
        return _resolve_scalar(payload["coefficient"], parameters)
    raise CanonicalHamiltonianError("canonical-term-coefficient-unresolved", term.get("term_ref"))


def _transpose_conjugate(matrix):
    rows = [list(row) for row in matrix]
    return [
        [complex(rows[col][row]).conjugate() for col in range(len(rows))]
        for row in range(len(rows[0]) if rows else 0)
    ]


def _compile_term(source, parameters, arity_hint=None):
    term = deepcopy(dict(source))
    family = _family_for_term(term)
    canonical = canonicalize_cluster(_cluster_for_term(term, arity_hint=arity_hint), family)
    coefficient = _coefficient_for_term(term, parameters)
    if canonical["orientation_reversed"] and isinstance(coefficient, list):
        coefficient = _transpose_conjugate(coefficient)
    orientation_sector = str(term.get("orientation_sector") or "default")
    compiled = {
        "term_ref": str(term.get("term_ref") or "term:unlabeled"),
        "arity": len(canonical["cluster"]),
        "cluster": canonical["cluster"],
        "operator_family": family,
        "coefficient": coefficient,
        "coordinate_convention": str(term.get("coordinate_convention") or "global_crystallographic"),
        "orientation_sector": orientation_sector,
        "permutation_action": deepcopy(term.get("permutation_action") or {}),
        "adjoint_action": deepcopy(term.get("adjoint_action") or {}),
        "operator_basis_ref": term.get("operator_basis_ref"),
        "attach_to": deepcopy(term.get("attach_to") or {}),
        "provenance": deepcopy(term.get("provenance") or {}),
    }
    if compiled["arity"] > 2:
        from common.operator_family_symmetry import canonicalize_family_term

        compiled = canonicalize_family_term(compiled)
    return compiled


def _bond_cluster(member):
    return [
        {"site": int(member.get("source", 0)), "translation": [0, 0, 0]},
        {
            "site": int(member.get("target", 0)),
            "translation": _translation(member.get("translation")),
        },
    ]


def _bond_orbit(payload, orbit_ref):
    lattice_structure = payload.get("lattice_structure") or {}
    matches = [
        orbit
        for orbit in list(lattice_structure.get("bond_orbits") or [])
        if isinstance(orbit, Mapping) and str(orbit.get("orbit_ref")) == str(orbit_ref)
    ]
    if len(matches) != 1:
        raise CanonicalHamiltonianError("unknown-bond-orbit-ref", orbit_ref)
    return matches[0]


def _operator_basis_kind(payload, term):
    registry = (payload.get("local_hilbert") or {}).get("operator_bases") or {}
    record = registry.get(term.get("operator_basis_ref"))
    return str(record.get("kind") or "") if isinstance(record, Mapping) else ""


def _compile_representative_bond_term(source, payload, parameters):
    attach_to = source.get("attach_to") if isinstance(source.get("attach_to"), Mapping) else {}
    orbit = _bond_orbit(payload, attach_to.get("orbit_ref"))
    representative = orbit.get("representative")
    if not isinstance(representative, Mapping):
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", source.get("term_ref"))

    seed_source = deepcopy(dict(source))
    seed_source["cluster"] = _bond_cluster(representative)
    seed = _compile_term(seed_source, parameters, arity_hint=2)
    if seed["operator_family"] not in {
        "bilinear_exchange_tensor",
        "bilinear_exchange_matrix",
    } or _operator_basis_kind(payload, seed) != "spin_vector":
        raise CanonicalHamiltonianError(
            "symmetry-representation-unavailable", seed.get("operator_basis_ref")
        )

    members = list(orbit.get("members") or [representative])
    member_keys = {
        _cluster_key(canonicalize_cluster(_bond_cluster(member), seed["operator_family"])["cluster"])
        for member in members
        if isinstance(member, Mapping)
    }
    operations = {
        str(operation.get("operation_ref") or ""): operation
        for operation in list((payload.get("symmetry") or {}).get("operations") or [])
        if isinstance(operation, Mapping)
    }
    if not operations:
        raise CanonicalHamiltonianError("structural-symmetry-unavailable")

    from common.hamiltonian_symmetry_action import transform_term

    expanded = {}
    for operation in operations.values():
        transformed = transform_term(seed, operation, payload.get("lattice_structure") or {})[0]
        key = _cluster_key(transformed["cluster"])
        if key in member_keys and key not in expanded:
            expanded[key] = transformed
    missing = sorted(member_keys.difference(expanded))
    if missing:
        raise CanonicalHamiltonianError("canonical-term-identity-unresolved", missing)
    return [expanded[key] for key in sorted(expanded)]


def compile_canonical_hamiltonian(payload):
    """Compile a lattice-term payload without changing the caller's mapping."""

    if not isinstance(payload, Mapping):
        raise CanonicalHamiltonianError("payload-must-be-object")
    attachments = payload.get("term_attachments")
    if not isinstance(attachments, Mapping):
        raise CanonicalHamiltonianError("term-attachments-must-be-object")
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), Mapping) else {}
    terms = []
    for collection, arity_hint in (
        ("site_terms", 1),
        ("bond_terms", 2),
        ("higher_body_terms", None),
    ):
        for source in list(attachments.get(collection) or []):
            attach_to = source.get("attach_to") if isinstance(source.get("attach_to"), Mapping) else {}
            if (
                collection == "bond_terms"
                and attach_to.get("kind") == "bond_orbit"
                and attach_to.get("orientation") == "representative"
            ):
                terms.extend(_compile_representative_bond_term(source, payload, parameters))
            else:
                terms.append(_compile_term(source, parameters, arity_hint=arity_hint))
    terms.sort(key=lambda term: (str(term["term_ref"]), canonical_term_key(term)))
    return {
        "schema_version": "canonical-hamiltonian/v1",
        "lattice_structure": deepcopy(payload.get("lattice_structure") or {}),
        "local_hilbert": deepcopy(payload.get("local_hilbert") or {}),
        "symmetry": deepcopy(payload.get("symmetry") or {}),
        "terms": terms,
        "source_schema_version": payload.get("schema_version"),
    }


def canonical_term_key(term):
    return (
        str(term.get("operator_family") or ""),
        _cluster_key(term.get("cluster") or []),
        str(term.get("operator_basis_ref") or ""),
        str(term.get("orientation_sector") or "default"),
    )


def _freeze(value):
    if isinstance(value, Mapping):
        return tuple((str(key), _freeze(child)) for key, child in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    if isinstance(value, complex):
        return ("complex", float(value.real), float(value.imag))
    if hasattr(value, "item"):
        return _freeze(value.item())
    return value


def coefficient_map(model):
    result = {}
    for term in list(model.get("terms") or []):
        key = canonical_term_key(term)
        coefficient = _freeze(term.get("coefficient"))
        if key in result:
            raise CanonicalHamiltonianError("duplicate-canonical-term-key", key)
        result[key] = coefficient
    return result


def _jsonable(value):
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    if isinstance(value, complex):
        return {"kind": "complex", "re": float(value.real), "im": float(value.imag)}
    if hasattr(value, "item"):
        return _jsonable(value.item())
    return value


def canonical_model_hash(model):
    physical_terms = []
    for term in list(model.get("terms") or []):
        physical_terms.append(
            {
                "arity": int(term.get("arity", 0)),
                "cluster": deepcopy(term.get("cluster") or []),
                "operator_family": term.get("operator_family"),
                "coefficient": deepcopy(term.get("coefficient")),
                "coordinate_convention": term.get("coordinate_convention"),
                "orientation_sector": term.get("orientation_sector"),
                "operator_basis_ref": term.get("operator_basis_ref"),
            }
        )
    physical_terms.sort(key=lambda term: json.dumps(_jsonable(term), sort_keys=True, separators=(",", ":")))
    payload = {
        "lattice_structure": model.get("lattice_structure") or {},
        "local_hilbert": model.get("local_hilbert") or {},
        "symmetry": model.get("symmetry") or {},
        "terms": physical_terms,
    }
    serialized = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
