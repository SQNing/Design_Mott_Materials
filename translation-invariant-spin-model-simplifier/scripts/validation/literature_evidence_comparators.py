"""Pure, structured comparisons for explicit literature and candidate operands."""

from collections.abc import Mapping
from decimal import Decimal, localcontext
import math

from validation.literature_evidence_schema import ComparisonTrace, EvidenceSchemaError


class ObservableComparisonError(ValueError):
    """Raised when a comparison request or operand is malformed."""


_KINDS = frozenset(
    {"exact", "absolute", "relative", "interval", "set", "sequence", "typed_claim"}
)
_CONFIG_KEYS = {
    "exact": frozenset({"kind"}),
    "absolute": frozenset({"kind", "tolerance"}),
    "relative": frozenset({"kind", "tolerance", "absolute_tolerance"}),
    "interval": frozenset({"kind"}),
    "set": frozenset({"kind"}),
    "sequence": frozenset({"kind"}),
    "typed_claim": frozenset({"kind"}),
}
_NUMERIC_KINDS = frozenset({"absolute", "relative"})
_ENVELOPE_KEYS = frozenset({"value", "units"})
_INTERVAL_KEYS = frozenset(
    {"lower", "upper", "lower_inclusive", "upper_inclusive"}
)


def _finite_nonnegative(value, field_name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ObservableComparisonError(
            f"{field_name} must be a finite nonnegative number"
        )
    return value


def _finite_numeric(value, field_name="numeric operand"):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ObservableComparisonError(f"{field_name} must be a finite numeric scalar")
    return value


def _validate_comparison(comparison):
    if not isinstance(comparison, Mapping):
        raise ObservableComparisonError("comparison config must be a mapping")
    non_string_keys = [key for key in comparison if not isinstance(key, str)]
    if non_string_keys:
        raise ObservableComparisonError("comparison config keys must be strings")
    kind = comparison.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ObservableComparisonError("comparison kind is required")
    if kind not in _KINDS:
        raise ObservableComparisonError(f"unsupported comparison kind {kind!r}")
    actual_keys = set(comparison)
    allowed_keys = _CONFIG_KEYS[kind]
    unknown = actual_keys - allowed_keys
    if unknown:
        raise ObservableComparisonError(
            f"comparison config for {kind!r} has unsupported keys: "
            f"{', '.join(sorted(unknown))}"
        )
    if kind in _NUMERIC_KINDS and "tolerance" not in comparison:
        raise ObservableComparisonError(
            f"comparison config for {kind!r} requires tolerance"
        )
    if "tolerance" in comparison:
        _finite_nonnegative(comparison["tolerance"], "tolerance")
    if "absolute_tolerance" in comparison:
        _finite_nonnegative(
            comparison["absolute_tolerance"], "absolute_tolerance"
        )
    return kind, dict(comparison)


def _looks_enveloped(value):
    return isinstance(value, Mapping) and bool(set(value) & _ENVELOPE_KEYS)


def _unwrap_operands(literature_operand, candidate_operand):
    literature_enveloped = _looks_enveloped(literature_operand)
    candidate_enveloped = _looks_enveloped(candidate_operand)
    if literature_enveloped != candidate_enveloped:
        raise ObservableComparisonError(
            "operand envelope must be supplied for both operands or neither"
        )
    if not literature_enveloped:
        return literature_operand, candidate_operand, None, None

    for label, operand in (
        ("literature", literature_operand),
        ("candidate", candidate_operand),
    ):
        if set(operand) != _ENVELOPE_KEYS:
            raise ObservableComparisonError(
                f"{label} operand envelope must contain exactly value and units"
            )
        units = operand["units"]
        if not isinstance(units, str) or not units.strip():
            raise ObservableComparisonError(
                f"{label} operand envelope units must be a nonempty string"
            )
    return (
        literature_operand["value"],
        candidate_operand["value"],
        literature_operand["units"],
        candidate_operand["units"],
    )


def _validate_json(value, field_name):
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ObservableComparisonError(f"{field_name} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ObservableComparisonError(
                    f"{field_name} contains a non-string mapping key"
                )
            _validate_json(item, field_name)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json(item, field_name)
        return
    raise ObservableComparisonError(
        f"{field_name} contains unsupported value {type(value).__name__}"
    )


def _type_aware_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _type_aware_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _type_aware_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _format_number(value):
    return format(value, ".15g")


def _decimal(value):
    return Decimal(str(value))


def _absolute_errors(literature, candidate, uncertainty):
    with localcontext() as context:
        context.prec = 50
        raw_error = abs(_decimal(candidate) - _decimal(literature))
        conservative_error = raw_error + _decimal(uncertainty)
    return raw_error, conservative_error


def _trace(
    *,
    benchmark_name,
    comparison,
    original_literature_operand,
    original_candidate_operand,
    literature_value,
    candidate_value,
    units,
    error,
    tolerance,
    local_uncertainty,
    matched,
    reason,
):
    try:
        return ComparisonTrace(
            benchmark_name=benchmark_name,
            payload={
                "original_literature_operand": original_literature_operand,
                "original_candidate_operand": original_candidate_operand,
                "literature_value": literature_value,
                "candidate_value": candidate_value,
                "units": units,
                "comparison": comparison,
                "error": error,
                "tolerance": tolerance,
                "local_uncertainty": local_uncertainty,
                "matched": matched,
                "reason": reason,
            },
        )
    except EvidenceSchemaError as error:
        raise ObservableComparisonError(str(error)) from error


def _exact(literature, candidate):
    scalar_types = (type(None), str, bool, int, float)
    if type(literature) not in scalar_types or type(candidate) not in scalar_types:
        raise ObservableComparisonError("exact operands must be JSON scalar values")
    _validate_json(literature, "literature operand")
    _validate_json(candidate, "candidate operand")
    matched = _type_aware_equal(literature, candidate)
    if matched:
        return matched, None, None, "exact values match"
    if type(literature) is not type(candidate):
        reason = (
            "exact value type mismatch: literature is "
            f"{type(literature).__name__}, candidate is {type(candidate).__name__}"
        )
    else:
        reason = "exact values differ"
    return matched, None, None, reason


def _absolute(literature, candidate, tolerance, uncertainty):
    _finite_numeric(literature, "literature numeric operand")
    _finite_numeric(candidate, "candidate numeric operand")
    raw_error, conservative_error = _absolute_errors(
        literature, candidate, uncertainty
    )
    matched = conservative_error <= _decimal(tolerance)
    relation = "is within" if matched else "exceeds"
    reason = (
        f"absolute error {_format_number(float(raw_error))}"
        f" plus local uncertainty {_format_number(uncertainty)} "
        f"{relation} tolerance "
        f"{_format_number(tolerance)}"
    )
    return matched, float(raw_error), tolerance, reason


def _relative(literature, candidate, comparison, uncertainty):
    _finite_numeric(literature, "literature numeric operand")
    _finite_numeric(candidate, "candidate numeric operand")
    if literature == 0:
        if "absolute_tolerance" not in comparison:
            return False, None, comparison["tolerance"], (
                "relative comparison fails closed because the literature value is zero "
                "and no absolute_tolerance fallback was provided"
            )
        matched, error, tolerance, absolute_reason = _absolute(
            literature,
            candidate,
            comparison["absolute_tolerance"],
            uncertainty,
        )
        return matched, error, tolerance, f"absolute fallback: {absolute_reason}"
    with localcontext() as context:
        context.prec = 50
        denominator = abs(_decimal(literature))
        absolute_error = abs(_decimal(candidate) - _decimal(literature))
        error = absolute_error / denominator
        conservative_error = (absolute_error + _decimal(uncertainty)) / denominator
    tolerance = comparison["tolerance"]
    matched = conservative_error <= _decimal(tolerance)
    relation = "is within" if matched else "exceeds"
    reason = (
        f"relative error {_format_number(float(error))} plus absolute local uncertainty "
        f"{_format_number(uncertainty)} {relation} tolerance "
        f"{_format_number(tolerance)}"
    )
    return matched, float(error), tolerance, reason


def _interval(literature, candidate):
    if not isinstance(literature, Mapping):
        raise ObservableComparisonError("literature interval must be a mapping")
    if set(literature) != _INTERVAL_KEYS:
        raise ObservableComparisonError(
            "literature interval must contain exactly lower, upper, "
            "lower_inclusive, and upper_inclusive"
        )
    lower = _finite_numeric(literature["lower"], "interval lower endpoint")
    upper = _finite_numeric(literature["upper"], "interval upper endpoint")
    if lower > upper:
        raise ObservableComparisonError("literature interval lower must not exceed upper")
    for key in ("lower_inclusive", "upper_inclusive"):
        if type(literature[key]) is not bool:
            raise ObservableComparisonError(f"interval {key} must be boolean")
    candidate = _finite_numeric(candidate, "candidate numeric operand")
    lower_ok = candidate >= lower if literature["lower_inclusive"] else candidate > lower
    upper_ok = candidate <= upper if literature["upper_inclusive"] else candidate < upper
    matched = lower_ok and upper_ok
    lower_bracket = "[" if literature["lower_inclusive"] else "("
    upper_bracket = "]" if literature["upper_inclusive"] else ")"
    location = "within" if matched else "outside"
    reason = (
        f"candidate {_format_number(candidate)} is {location} interval "
        f"{lower_bracket}{_format_number(lower)}, {_format_number(upper)}{upper_bracket}"
    )
    return matched, None, None, reason


def _set_token(value):
    return type(value).__name__, value


def _validated_set_operand(value, label):
    if not isinstance(value, (list, tuple)):
        raise ObservableComparisonError(f"{label} set operand must be a list or tuple")
    tokens = []
    seen = set()
    for item in value:
        if isinstance(item, (Mapping, list, tuple)):
            raise ObservableComparisonError(
                f"{label} set operand contains nested or unhashable set element"
            )
        _validate_json(item, f"{label} set operand")
        token = _set_token(item)
        if token in seen:
            raise ObservableComparisonError(f"{label} set operand contains duplicate elements")
        seen.add(token)
        tokens.append(token)
    return set(tokens)


def _render_set_tokens(tokens):
    return ", ".join(
        f"{type_name}:{value!r}" for type_name, value in sorted(tokens, key=repr)
    )


def _set_compare(literature, candidate):
    literature_set = _validated_set_operand(literature, "literature")
    candidate_set = _validated_set_operand(candidate, "candidate")
    missing = literature_set - candidate_set
    extra = candidate_set - literature_set
    matched = not missing and not extra
    if matched:
        reason = "unordered exact sets match"
    else:
        details = []
        if missing:
            details.append(f"missing elements: {_render_set_tokens(missing)}")
        if extra:
            details.append(f"extra elements: {_render_set_tokens(extra)}")
        reason = "; ".join(details)
    return matched, None, None, reason


def _sequence(literature, candidate):
    for label, value in (("literature", literature), ("candidate", candidate)):
        if not isinstance(value, (list, tuple)):
            raise ObservableComparisonError(
                f"{label} sequence operand must be a list or tuple; strings are scalars"
            )
        _validate_json(value, f"{label} sequence operand")
    if len(literature) != len(candidate):
        return False, None, None, (
            f"sequence length mismatch: literature has {len(literature)}, "
            f"candidate has {len(candidate)}"
        )
    mismatches = [
        index
        for index, (left, right) in enumerate(zip(literature, candidate))
        if not _type_aware_equal(left, right)
    ]
    if mismatches:
        rendered = ", ".join(str(index) for index in mismatches)
        return False, None, None, f"sequence mismatch at index {rendered}"
    return True, None, None, "ordered exact sequences match"


def _typed_claim(literature, candidate):
    for label, value in (("literature", literature), ("candidate", candidate)):
        if not isinstance(value, Mapping):
            raise ObservableComparisonError(f"{label} typed claim must be a mapping")
        try:
            _validate_json(value, f"{label} typed claim")
        except ObservableComparisonError as error:
            raise ObservableComparisonError(f"malformed {label} typed claim: {error}") from error
    literature_keys = set(literature)
    candidate_keys = set(candidate)
    missing = sorted(literature_keys - candidate_keys)
    extra = sorted(candidate_keys - literature_keys)
    mismatched = sorted(
        key
        for key in literature_keys & candidate_keys
        if not _type_aware_equal(literature[key], candidate[key])
    )
    if not missing and not extra and not mismatched:
        return True, None, None, "typed claim keys and values match exactly"
    details = []
    if missing:
        details.append(f"missing fields: {', '.join(missing)}")
    if extra:
        details.append(f"extra fields: {', '.join(extra)}")
    if mismatched:
        details.append(f"mismatched fields: {', '.join(mismatched)}")
    return False, None, None, "; ".join(details)


def compare_observables(
    *,
    benchmark_name,
    comparison,
    literature_operand,
    candidate_operand,
    local_uncertainty=None,
):
    """Compare two explicit operands and return an immutable diagnostic trace."""

    kind, comparison_config = _validate_comparison(comparison)
    if local_uncertainty is not None:
        _finite_nonnegative(local_uncertainty, "local uncertainty")
        if kind not in _NUMERIC_KINDS:
            raise ObservableComparisonError(
                f"local uncertainty is not supported for {kind!r} comparisons"
            )
    uncertainty = 0 if local_uncertainty is None else local_uncertainty
    literature, candidate, literature_units, candidate_units = _unwrap_operands(
        literature_operand, candidate_operand
    )

    if literature_units is not None and literature_units != candidate_units:
        _validate_json(literature, "literature operand")
        _validate_json(candidate, "candidate operand")
        return _trace(
            benchmark_name=benchmark_name,
            comparison=comparison_config,
            original_literature_operand=literature_operand,
            original_candidate_operand=candidate_operand,
            literature_value=literature,
            candidate_value=candidate,
            units={"literature": literature_units, "candidate": candidate_units},
            error=None,
            tolerance=comparison_config.get("tolerance"),
            local_uncertainty=local_uncertainty,
            matched=False,
            reason=(
                f"unit mismatch: literature uses {literature_units!r}, "
                f"candidate uses {candidate_units!r}"
            ),
        )

    if kind == "exact":
        outcome = _exact(literature, candidate)
    elif kind == "absolute":
        outcome = _absolute(
            literature, candidate, comparison_config["tolerance"], uncertainty
        )
    elif kind == "relative":
        outcome = _relative(literature, candidate, comparison_config, uncertainty)
    elif kind == "interval":
        outcome = _interval(literature, candidate)
    elif kind == "set":
        outcome = _set_compare(literature, candidate)
    elif kind == "sequence":
        outcome = _sequence(literature, candidate)
    else:
        outcome = _typed_claim(literature, candidate)

    matched, error, tolerance, reason = outcome
    return _trace(
        benchmark_name=benchmark_name,
        comparison=comparison_config,
        original_literature_operand=literature_operand,
        original_candidate_operand=candidate_operand,
        literature_value=literature,
        candidate_value=candidate,
        units=literature_units,
        error=error,
        tolerance=tolerance,
        local_uncertainty=local_uncertainty,
        matched=matched,
        reason=reason,
    )
