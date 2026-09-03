#!/usr/bin/env python3
"""Strict validation and opt-in group-average repair for Hamiltonians."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

import numpy as np

from common.canonical_hamiltonian import (
    CanonicalHamiltonianError,
    canonical_model_hash,
    canonical_term_key,
)
from common.hamiltonian_symmetry_action import transform_term


class HamiltonianSymmetryError(ValueError):
    def __init__(self, code, report=None):
        self.code = str(code)
        self.report = deepcopy(report) if isinstance(report, Mapping) else report
        super().__init__(self.code)


@dataclass(frozen=True)
class SymmetryGateRequest:
    repair: bool = False
    absolute_tolerance: float = 1.0e-10
    relative_tolerance: float = 1.0e-8
    cleanup_tolerance: float = 1.0e-12

    def __post_init__(self):
        if not isinstance(self.repair, bool):
            raise HamiltonianSymmetryError("invalid-symmetry-repair-flag")
        for name in ("absolute_tolerance", "relative_tolerance", "cleanup_tolerance"):
            if float(getattr(self, name)) < 0.0:
                raise HamiltonianSymmetryError("invalid-symmetry-tolerance")


def _operations(model):
    symmetry = model.get("symmetry") if isinstance(model, Mapping) else {}
    operations = list(symmetry.get("operations") or []) if isinstance(symmetry, Mapping) else []
    if not operations or (isinstance(symmetry, Mapping) and symmetry.get("unresolved")):
        raise HamiltonianSymmetryError("structural-symmetry-unavailable")
    return operations


def _target_group(model, operations):
    source = model.get("symmetry", {}).get("source", {})
    source = source if isinstance(source, Mapping) else {}
    return {
        "kind": "structural_space_group",
        "international_symbol": source.get("international_symbol"),
        "number": source.get("number"),
        "operation_count": len(operations),
        "operation_refs": [str(operation.get("operation_ref") or "") for operation in operations],
    }


def _as_array(coefficient):
    if isinstance(coefficient, Mapping):
        keys = sorted(coefficient)
        return np.asarray([complex(coefficient[key]) for key in keys], dtype=complex)
    return np.asarray(coefficient, dtype=complex)


def _zero_like(coefficient):
    if isinstance(coefficient, Mapping):
        return {key: 0.0 for key in coefficient}
    return np.zeros_like(_as_array(coefficient), dtype=complex)


def _add(left, right):
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        left = left if isinstance(left, Mapping) else {}
        right = right if isinstance(right, Mapping) else {}
        return {
            key: complex(left.get(key, 0.0)) + complex(right.get(key, 0.0))
            for key in sorted(set(left).union(right))
        }
    return _as_array(left) + _as_array(right)


def _scale(value, factor):
    if isinstance(value, Mapping):
        return {key: complex(child) * factor for key, child in value.items()}
    return _as_array(value) * factor


def _difference(left, right):
    return _add(left, _scale(right, -1.0))


def _norms(value):
    array = _as_array(value).reshape(-1)
    if array.size == 0:
        return 0.0, 0.0
    return float(np.max(np.abs(array))), float(np.linalg.norm(array))


def _clean(value, tolerance):
    if isinstance(value, Mapping):
        return {key: _clean(child, tolerance) for key, child in value.items()}
    array = _as_array(value)
    array.real[np.abs(array.real) <= tolerance] = 0.0
    array.imag[np.abs(array.imag) <= tolerance] = 0.0

    def scalar(child):
        child = complex(child)
        return float(child.real) if child.imag == 0.0 else child

    if array.ndim == 0:
        return scalar(array.item())

    def nested(child):
        if isinstance(child, list):
            return [nested(entry) for entry in child]
        return scalar(child)

    return nested(array.tolist())


def _key_payload(key):
    return json.loads(json.dumps(key))


def _aggregate_terms(terms):
    coefficients = {}
    templates = {}
    refs = {}
    for term in terms:
        key = canonical_term_key(term)
        coefficient = term.get("coefficient")
        if key in coefficients:
            coefficients[key] = _add(coefficients[key], coefficient)
            refs[key].append(str(term.get("term_ref") or ""))
        else:
            coefficients[key] = deepcopy(coefficient)
            templates[key] = deepcopy(term)
            refs[key] = [str(term.get("term_ref") or "")]
    return coefficients, templates, refs


def _transform_terms(model, operation):
    transformed = []
    for term in list(model.get("terms") or []):
        transformed.extend(transform_term(term, operation, model["lattice_structure"]))
    return transformed


def _operation_residual(model, operation, request, original_coefficients, original_refs):
    transformed_terms = _transform_terms(model, operation)
    transformed_coefficients, _templates, transformed_refs = _aggregate_terms(transformed_terms)
    union = sorted(set(original_coefficients).union(transformed_coefficients), key=repr)
    max_absolute = 0.0
    frobenius_sq = 0.0
    worst = None
    missing = []
    for key in union:
        left = original_coefficients.get(key)
        right = transformed_coefficients.get(key)
        if left is None:
            left = _zero_like(right)
            missing.append(
                {
                    "operation_ref": str(operation.get("operation_ref") or ""),
                    "expected_canonical_key": _key_payload(key),
                    "source_term_refs": transformed_refs.get(key, []),
                }
            )
        if right is None:
            right = _zero_like(left)
            missing.append(
                {
                    "operation_ref": str(operation.get("operation_ref") or ""),
                    "expected_canonical_key": _key_payload(key),
                    "source_term_refs": original_refs.get(key, []),
                }
            )
        difference = _difference(left, right)
        absolute, frobenius = _norms(difference)
        scale = max(_norms(left)[0], _norms(right)[0])
        threshold = float(request.absolute_tolerance) + float(request.relative_tolerance) * scale
        frobenius_sq += frobenius * frobenius
        if worst is None or absolute > max_absolute:
            max_absolute = absolute
            worst = {
                "canonical_key": _key_payload(key),
                "source_term_refs": original_refs.get(key, []),
                "transformed_term_refs": transformed_refs.get(key, []),
                "absolute_residual": absolute,
                "relative_residual": absolute / max(scale, float(request.absolute_tolerance), 1.0e-300),
                "threshold": threshold,
            }
    scale = max(
        [_norms(value)[0] for value in original_coefficients.values()]
        + [_norms(value)[0] for value in transformed_coefficients.values()]
        + [0.0]
    )
    allowed = float(request.absolute_tolerance) + float(request.relative_tolerance) * scale
    return {
        "operation_ref": str(operation.get("operation_ref") or ""),
        "passed": bool(max_absolute <= allowed),
        "max_absolute_residual": float(max_absolute),
        "max_relative_residual": float(max_absolute / max(scale, float(request.absolute_tolerance), 1.0e-300)),
        "frobenius_residual": float(np.sqrt(frobenius_sq)),
        "allowed_residual": float(allowed),
        "worst_term": worst,
        "missing_symmetry_partners": missing,
    }


def _operation_match(rotation, translation, candidate, *, tolerance=1.0e-8):
    if not np.array_equal(np.rint(rotation).astype(int), np.rint(candidate["rotation"]).astype(int)):
        return False
    delta = np.asarray(translation, dtype=float) - np.asarray(candidate.get("translation", [0, 0, 0]), dtype=float)
    return bool(np.allclose(delta, np.rint(delta), atol=tolerance, rtol=0.0))


def _compose(left, right):
    left_rotation = np.asarray(left["rotation"], dtype=int)
    right_rotation = np.asarray(right["rotation"], dtype=int)
    left_translation = np.asarray(left.get("translation", [0, 0, 0]), dtype=float)
    right_translation = np.asarray(right.get("translation", [0, 0, 0]), dtype=float)
    return left_rotation @ right_rotation, left_rotation @ right_translation + left_translation


def _diagnostic_subgroup(operations, passing_refs):
    passing = [operation for operation in operations if str(operation.get("operation_ref") or "") in passing_refs]
    identity_refs = [
        str(operation.get("operation_ref") or "")
        for operation in passing
        if _operation_match(np.eye(3, dtype=int), np.zeros(3), operation)
    ]
    closed = bool(identity_refs)
    for left in passing:
        for right in passing:
            rotation, translation = _compose(left, right)
            if not any(_operation_match(rotation, translation, candidate) for candidate in passing):
                closed = False
                break
        if not closed:
            break
    if closed:
        for operation in passing:
            has_inverse = False
            for candidate in passing:
                rotation, translation = _compose(operation, candidate)
                if any(
                    _operation_match(rotation, translation, identity)
                    for identity in passing
                    if str(identity.get("operation_ref") or "") in identity_refs
                ):
                    has_inverse = True
                    break
            if not has_inverse:
                closed = False
                break
    return {
        "status": "verified-subgroup" if closed else "candidate-operations-only",
        "operation_refs": [str(operation.get("operation_ref") or "") for operation in passing],
        "operation_count": len(passing),
    }


def validate_hamiltonian_symmetry(model, request=None):
    request = request or SymmetryGateRequest()
    operations = _operations(model)
    original_coefficients, _templates, original_refs = _aggregate_terms(model.get("terms") or [])
    operation_reports = []
    for operation in operations:
        try:
            operation_reports.append(
                _operation_residual(model, operation, request, original_coefficients, original_refs)
            )
        except CanonicalHamiltonianError as exc:
            raise HamiltonianSymmetryError(exc.code) from exc
    failed = [report for report in operation_reports if not report["passed"]]
    passing_refs = {
        report["operation_ref"] for report in operation_reports if report["passed"]
    }
    missing = []
    for report in failed:
        missing.extend(report["missing_symmetry_partners"])
    return {
        "status": "passed" if not failed else "failed",
        "target_group": _target_group(model, operations),
        "operation_reports": operation_reports,
        "failed_operations": failed,
        "missing_symmetry_partners": missing,
        "max_absolute_residual": max(
            [report["max_absolute_residual"] for report in operation_reports] + [0.0]
        ),
        "max_relative_residual": max(
            [report["max_relative_residual"] for report in operation_reports] + [0.0]
        ),
        "input_hamiltonian_subgroup": _diagnostic_subgroup(operations, passing_refs),
    }


def _stable_generated_ref(key):
    digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]
    return f"symmetry-generated:{digest}"


def _change_report(before, after, request):
    before_coefficients, _before_templates, _before_refs = _aggregate_terms(before.get("terms") or [])
    after_coefficients, _after_templates, _after_refs = _aggregate_terms(after.get("terms") or [])
    added = []
    modified = []
    zeroed = []
    unchanged = []
    max_absolute = 0.0
    total_sq = 0.0
    input_scale = max([_norms(value)[0] for value in before_coefficients.values()] + [0.0])
    for key in sorted(set(before_coefficients).union(after_coefficients), key=repr):
        old = before_coefficients.get(key)
        new = after_coefficients.get(key)
        old_norm = 0.0 if old is None else _norms(old)[0]
        new_norm = 0.0 if new is None else _norms(new)[0]
        if old is None:
            difference = new
            bucket = added
        elif new is None or new_norm <= request.cleanup_tolerance:
            difference = old
            bucket = zeroed
        else:
            difference = _difference(new, old)
            absolute = _norms(difference)[0]
            bucket = unchanged if absolute <= request.cleanup_tolerance else modified
        absolute, frobenius = _norms(difference)
        max_absolute = max(max_absolute, absolute)
        total_sq += frobenius * frobenius
        bucket.append({"canonical_key": _key_payload(key), "absolute_change": float(absolute)})
    return {
        "added_terms": added,
        "modified_terms": modified,
        "zeroed_components": zeroed,
        "unchanged_terms": unchanged,
        "max_absolute_change": float(max_absolute),
        "max_relative_change": float(max_absolute / max(input_scale, request.absolute_tolerance, 1.0e-300)),
        "l2_change": float(np.sqrt(total_sq)),
    }


def project_hamiltonian_symmetry(model, request=None):
    request = request or SymmetryGateRequest(repair=True)
    operations = _operations(model)
    input_coefficients, input_templates, _input_refs = _aggregate_terms(model.get("terms") or [])
    summed = {}
    templates = {}
    for operation in operations:
        try:
            transformed = _transform_terms(model, operation)
        except CanonicalHamiltonianError as exc:
            raise HamiltonianSymmetryError(exc.code) from exc
        coefficients, transformed_templates, _refs = _aggregate_terms(transformed)
        for key, coefficient in coefficients.items():
            summed[key] = _add(summed[key], coefficient) if key in summed else deepcopy(coefficient)
            templates.setdefault(key, deepcopy(transformed_templates[key]))

    repaired_terms = []
    for key in sorted(summed, key=repr):
        coefficient = _clean(_scale(summed[key], 1.0 / float(len(operations))), request.cleanup_tolerance)
        if _norms(coefficient)[0] <= request.cleanup_tolerance:
            continue
        template = deepcopy(input_templates.get(key, templates[key]))
        template.pop("symmetry_action", None)
        template.pop("canonicalization", None)
        template["coefficient"] = coefficient
        if key not in input_coefficients:
            template["term_ref"] = _stable_generated_ref(key)
            template["provenance"] = {
                "generated_by": "finite-group-average",
                "source_term_ref": templates[key].get("term_ref"),
            }
        repaired_terms.append(template)

    repaired = deepcopy(model)
    repaired["terms"] = repaired_terms
    changes = _change_report(model, repaired, request)
    validation = validate_hamiltonian_symmetry(repaired, request)
    if validation["status"] != "passed":
        raise HamiltonianSymmetryError("symmetry-repair-postcheck-failed", validation)
    material = changes["max_absolute_change"] > request.cleanup_tolerance
    return {
        "solver_model": repaired,
        "report": {
            "status": "repaired" if material else "already-symmetric",
            "requested": True,
            "target_group": validation["target_group"],
            "projection": {
                "method": "finite-group-average",
                "operation_count": len(operations),
                "normalization": f"1/{len(operations)}",
            },
            "changes": changes,
            "validation_after": validation,
        },
    }


def _group_hash(target_group, operations):
    payload = {
        "target_group": target_group,
        "operations": operations,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validation_stamp(model, validation, request, repaired):
    operations = _operations(model)
    return {
        "status": "passed",
        "target_group_hash": _group_hash(validation["target_group"], operations),
        "hamiltonian_hash": canonical_model_hash(model),
        "absolute_tolerance": float(request.absolute_tolerance),
        "relative_tolerance": float(request.relative_tolerance),
        "repaired": bool(repaired),
    }


def require_current_symmetry_stamp(model, stamp):
    if not isinstance(stamp, Mapping) or stamp.get("status") != "passed":
        raise HamiltonianSymmetryError("symmetry-validation-stamp-missing")
    if str(stamp.get("hamiltonian_hash") or "") != canonical_model_hash(model):
        raise HamiltonianSymmetryError("symmetry-validation-stamp-stale")
    return stamp


def _failure(code, validation=None):
    result = {
        "status": "error",
        "completion": {
            "status": "failed",
            "reason": str(code),
            "stopping_condition": "pre-solver-symmetry-gate",
        },
        "solver_execution": {"started": False, "backends_run": []},
        "warnings": [],
    }
    if validation is not None:
        result["symmetry_validation"] = validation
    return result


def run_hamiltonian_symmetry_gate(model, request=None):
    request = request or SymmetryGateRequest()
    input_hash = canonical_model_hash(model)
    try:
        validation_before = validate_hamiltonian_symmetry(model, request)
        if not request.repair:
            if validation_before["status"] != "passed":
                return _failure("hamiltonian-symmetry-validation-failed", validation_before)
            solver_model = deepcopy(model)
            return {
                "status": "ok",
                "completion": {"status": "passed", "reason": None, "stopping_condition": "symmetry-validated"},
                "solver_model": solver_model,
                "symmetry_validation": validation_before,
                "symmetry_validation_stamp": _validation_stamp(
                    solver_model, validation_before, request, repaired=False
                ),
                "hamiltonian_provenance": {
                    "input_model": {"content_hash": input_hash},
                    "solver_model": {"content_hash": canonical_model_hash(solver_model)},
                },
                "warnings": [],
            }

        projection = project_hamiltonian_symmetry(model, request)
        solver_model = projection["solver_model"]
        report = projection["report"]
        report["validation_before"] = validation_before
        warnings = []
        if report["status"] == "repaired":
            warnings.append(
                {
                    "code": "hamiltonian-symmetry-repaired",
                    "message": "The input Hamiltonian was projected onto the structural space group before solver execution.",
                }
            )
        validation_after = report["validation_after"]
        return {
            "status": "ok",
            "completion": {"status": "passed", "reason": None, "stopping_condition": "symmetry-repaired-and-validated"},
            "solver_model": solver_model,
            "symmetry_validation": validation_after,
            "symmetry_repair_report": report,
            "symmetry_validation_stamp": _validation_stamp(
                solver_model, validation_after, request, repaired=report["status"] == "repaired"
            ),
            "hamiltonian_provenance": {
                "input_model": {"content_hash": input_hash},
                "solver_model": {"content_hash": canonical_model_hash(solver_model)},
                "symmetry_operation": {
                    "repair_requested": True,
                    "algorithm_version": "finite-group-average/v1",
                },
            },
            "warnings": warnings,
        }
    except HamiltonianSymmetryError as exc:
        return _failure(exc.code, exc.report)
    except CanonicalHamiltonianError as exc:
        return _failure(exc.code)
