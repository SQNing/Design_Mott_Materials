"""Bounded, immutable schemas for literature evidence audit artifacts."""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
import json
import math
import re
from types import MappingProxyType


class EvidenceSchemaError(ValueError):
    """Raised when literature evidence data violates its schema."""


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_LOWER_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CALLABLE_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
    r":[A-Za-z_][A-Za-z0-9_]*$"
)
_EVIDENCE_MODES = frozenset(
    {"local_recompute", "local_source_parse", "projection_only"}
)
_NORMALIZATION_ROUTES = ("operations", "rules", "fields", "executable")
_NORMALIZATION_OPERATORS = frozenset(
    {
        "identity",
        "scale",
        "offset",
        "reciprocal",
        "select_field",
        "rename_field",
        "map_value",
        "negate",
        "require_equal",
    }
)
_OPERATOR_ARGUMENTS = {
    "identity": (frozenset(), frozenset()),
    "scale": (frozenset({"factor"}), frozenset()),
    "offset": (frozenset({"value"}), frozenset()),
    "reciprocal": (frozenset(), frozenset({"source_field"})),
    "select_field": (frozenset({"source_field"}), frozenset()),
    "rename_field": (
        frozenset({"source_field", "target_field"}),
        frozenset(),
    ),
    "map_value": (frozenset({"mapping"}), frozenset()),
    "negate": (frozenset(), frozenset({"source_field"})),
    "require_equal": (frozenset({"expected"}), frozenset({"source_field"})),
}
_REPORT_ARTIFACTS = frozenset({"csv", "markdown", "pdf"})
_FORBIDDEN_RECORD_KEYS = frozenset(
    {
        "target_observable",
        "target_excerpt",
        "parsed_target",
        "strict_literature_match",
        "strict_match",
        "pass",
        "verdict",
    }
)


def _identifier(value, field_name):
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise EvidenceSchemaError(f"{field_name} must be a safe nonempty identifier")
    return value


def _nonempty_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise EvidenceSchemaError(f"{field_name} must be a nonempty string")
    return value


def _lower_identifier(value, field_name):
    if not isinstance(value, str) or not _LOWER_IDENTIFIER_RE.fullmatch(value):
        raise EvidenceSchemaError(
            f"{field_name} must match ^[a-z][a-z0-9_]*$"
        )
    return value


def _schema_version(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EvidenceSchemaError("schema_version must be a nonempty string or integer")
    if isinstance(value, str) and not value.strip():
        raise EvidenceSchemaError("schema_version must be a nonempty string or integer")
    return value


def _freeze_json(value, field_name):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceSchemaError(f"{field_name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvidenceSchemaError(f"{field_name} contains a non-string mapping key")
            frozen[key] = _freeze_json(item, field_name)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, field_name) for item in value)
    raise EvidenceSchemaError(
        f"{field_name} contains unsupported JSON value {type(value).__name__}"
    )


def _structured(value, field_name):
    if not isinstance(value, Mapping):
        raise EvidenceSchemaError(f"{field_name} must be a structured mapping")
    return _freeze_json(value, field_name)


def _set_structured(instance, field_names):
    for field_name in field_names:
        object.__setattr__(
            instance,
            field_name,
            _structured(getattr(instance, field_name), field_name),
        )


def _validate_sha256(value, field_name):
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise EvidenceSchemaError(f"{field_name} must be a 64-character SHA-256 hex digest")


def _initialize(instance, args, kwargs, *, forbidden_extras=frozenset()):
    field_names = tuple(field.name for field in fields(instance))
    if len(args) > len(field_names):
        raise EvidenceSchemaError(
            f"too many positional fields for {type(instance).__name__}"
        )
    values = dict(zip(field_names, args))
    for name, value in kwargs.items():
        if name not in field_names:
            qualifier = "forbidden " if name in forbidden_extras else "unexpected "
            raise EvidenceSchemaError(f"{qualifier}field {name}")
        if name in values:
            raise EvidenceSchemaError(f"field {name} supplied more than once")
        values[name] = value
    missing = [name for name in field_names if name not in values]
    if missing:
        raise EvidenceSchemaError(f"missing required field {missing[0]}")
    for name in field_names:
        object.__setattr__(instance, name, values[name])
    instance.__post_init__()


@dataclass(frozen=True, init=False)
class CanonicalObservable:
    canonical_observable_id: str
    benchmark_name: str
    subject: str
    system: str
    hamiltonian: Mapping
    parameter_regime: Mapping
    size_or_limit: Mapping
    observable: Mapping
    representation: Mapping
    units: str
    conditions: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _lower_identifier(
            self.canonical_observable_id, "canonical_observable_id"
        )
        _identifier(self.benchmark_name, "benchmark_name")
        for field_name in ("subject", "system", "units"):
            _nonempty_text(getattr(self, field_name), field_name)
        _set_structured(
            self,
            (
                "hamiltonian",
                "parameter_regime",
                "size_or_limit",
                "observable",
                "representation",
                "conditions",
            ),
        )


@dataclass(frozen=True, init=False)
class SourceProvenance:
    source_id: str
    source_identity: Mapping
    bibliographic_metadata: Mapping
    retrieval_metadata: Mapping
    media_type: str
    raw_payload_sha256: str
    raw_payload_byte_length: int
    license_access_notes: Mapping
    citation_metadata_verification: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _identifier(self.source_id, "source_id")
        _nonempty_text(self.media_type, "media_type")
        _validate_sha256(self.raw_payload_sha256, "raw_payload_sha256")
        if (
            isinstance(self.raw_payload_byte_length, bool)
            or not isinstance(self.raw_payload_byte_length, int)
            or self.raw_payload_byte_length < 0
        ):
            raise EvidenceSchemaError(
                "raw_payload_byte_length must be a nonnegative integer"
            )
        _set_structured(
            self,
            (
                "source_identity",
                "bibliographic_metadata",
                "retrieval_metadata",
                "license_access_notes",
                "citation_metadata_verification",
            ),
        )


def _find_forbidden_key(value):
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FORBIDDEN_RECORD_KEYS:
                return key
            found = _find_forbidden_key(item)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _find_forbidden_key(item)
            if found:
                return found
    return None


def _normalization_error(detail):
    raise EvidenceSchemaError(f"normalization {detail}")


def _mapping_keys(value, path):
    non_string_keys = [key for key in value if not isinstance(key, str)]
    if non_string_keys:
        rendered = ", ".join(
            repr(key) for key in sorted(non_string_keys, key=repr)
        )
        _normalization_error(f"{path} has non-string keys: {rendered}")
    return set(value)


def _operator_name(step, path):
    operator_keys = [key for key in ("op", "operator") if key in step]
    if len(operator_keys) != 1:
        _normalization_error(f"{path} requires exactly one op or operator")
    operator = step[operator_keys[0]]
    if not isinstance(operator, str):
        _normalization_error(f"{path} op/operator must be a string")
    if operator not in _NORMALIZATION_OPERATORS:
        _normalization_error(f"{path} contains unsupported operator {operator!r}")
    return operator, operator_keys[0]


def _validate_operation_step(step, path):
    if not isinstance(step, Mapping):
        _normalization_error(f"{path} must be a mapping")
    step_keys = _mapping_keys(step, path)
    operator, operator_key = _operator_name(step, path)
    required, optional = _OPERATOR_ARGUMENTS[operator]
    argument_keys = step_keys - {operator_key}
    unknown = argument_keys - required - optional
    missing = required - argument_keys
    if unknown:
        _normalization_error(
            f"{path} operator {operator!r} has unrecognized arguments: "
            f"{', '.join(sorted(unknown))}"
        )
    if missing:
        _normalization_error(
            f"{path} operator {operator!r} is missing arguments: "
            f"{', '.join(sorted(missing))}"
        )
    for field_name in ("source_field", "target_field"):
        if field_name in step:
            _lower_identifier(
                step[field_name], f"normalization {path}.{field_name}"
            )
    for numeric_name in ("factor", "value"):
        if numeric_name in step:
            numeric = step[numeric_name]
            if (
                isinstance(numeric, bool)
                or not isinstance(numeric, (int, float))
                or not math.isfinite(numeric)
            ):
                _normalization_error(
                    f"{path}.{numeric_name} must be a finite number"
                )
    if "mapping" in step and (
        not isinstance(step["mapping"], Mapping) or not step["mapping"]
    ):
        _normalization_error(f"{path}.mapping must be a nonempty mapping")


def _validate_operation_route(route, route_name):
    if (
        not isinstance(route, Sequence)
        or isinstance(route, (str, bytes, bytearray))
        or not route
    ):
        _normalization_error(f"{route_name} must be a nonempty ordered sequence")
    for index, step in enumerate(route):
        _validate_operation_step(step, f"{route_name}[{index}]")


def _validate_fields_route(route):
    if not isinstance(route, Mapping) or not route:
        _normalization_error("fields must be a nonempty mapping")
    _mapping_keys(route, "fields")
    for output_field, spec in route.items():
        _lower_identifier(output_field, "normalization output field")
        spec_path = f"fields.{output_field}"
        if not isinstance(spec, Mapping):
            _normalization_error(f"{spec_path} must be a mapping")
        spec_keys = _mapping_keys(spec, spec_path)
        unknown = spec_keys - {"source_field", "operation"}
        if unknown:
            _normalization_error(
                f"{spec_path} has unrecognized keys: {', '.join(sorted(unknown))}"
            )
        if "source_field" not in spec:
            _normalization_error(f"{spec_path} requires source_field")
        _lower_identifier(spec["source_field"], "normalization source_field")
        if "operation" not in spec:
            _normalization_error(f"{spec_path} requires operation")
        _validate_operation_step(spec["operation"], f"{spec_path}.operation")


def _validate_executable_route(route):
    if not isinstance(route, Mapping):
        _normalization_error("executable must be a mapping")
    unknown = _mapping_keys(route, "executable") - {"callable", "version"}
    if unknown:
        _normalization_error(
            f"executable has unrecognized keys: {', '.join(sorted(unknown))}"
        )
    callable_ref = route.get("callable")
    if not isinstance(callable_ref, str) or not _CALLABLE_RE.fullmatch(callable_ref):
        _normalization_error("executable callable must match module.path:function_name")
    if "version" in route and (
        isinstance(route["version"], bool)
        or not isinstance(route["version"], int)
        or route["version"] <= 0
    ):
        _normalization_error("executable version must be a positive integer")


def _validate_normalization(normalization):
    """Validate one closed normalization route.

    ``operations`` and ``rules`` contain typed operator steps; ``fields`` maps
    output identifiers to source-field specs; ``executable`` names a versioned
    Python callable. No free-form description keys are part of the grammar.
    """

    if not isinstance(normalization, Mapping):
        _normalization_error("must be a structured mapping")
    unknown = _mapping_keys(normalization, "root") - {
        "kind",
        *_NORMALIZATION_ROUTES,
    }
    if unknown:
        _normalization_error(
            f"has unrecognized keys: {', '.join(sorted(unknown))}"
        )
    _lower_identifier(normalization.get("kind"), "normalization kind")
    routes = [route for route in _NORMALIZATION_ROUTES if route in normalization]
    if len(routes) != 1:
        _normalization_error("requires exactly one structured route")
    route_name = routes[0]
    route = normalization[route_name]
    if route_name in ("operations", "rules"):
        _validate_operation_route(route, route_name)
    elif route_name == "fields":
        _validate_fields_route(route)
    else:
        _validate_executable_route(route)


@dataclass(frozen=True, init=False)
class EvidenceRecord:
    schema_version: object
    benchmark_name: str
    evidence_mode: str
    source_id: str
    source_sha256: str
    registry_selector: Mapping
    canonical_observable_id: str
    target_locator: Mapping
    target_parser: str
    normalization: Mapping
    adapter: str
    adapter_parameters: Mapping
    convergence: Mapping
    comparison: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(
            self, args, kwargs, forbidden_extras=_FORBIDDEN_RECORD_KEYS
        )

    def __post_init__(self):
        _schema_version(self.schema_version)
        for field_name in (
            "benchmark_name",
            "source_id",
            "target_parser",
            "adapter",
        ):
            _identifier(getattr(self, field_name), field_name)
        _lower_identifier(
            self.canonical_observable_id, "canonical_observable_id"
        )
        if self.evidence_mode not in _EVIDENCE_MODES:
            raise EvidenceSchemaError(
                "evidence_mode must be one of local_recompute, local_source_parse, "
                "projection_only"
            )
        _validate_sha256(self.source_sha256, "source_sha256")
        structured_fields = (
            "registry_selector",
            "target_locator",
            "normalization",
            "adapter_parameters",
            "convergence",
            "comparison",
        )
        for field_name in structured_fields:
            value = getattr(self, field_name)
            forbidden = _find_forbidden_key(value)
            if forbidden:
                raise EvidenceSchemaError(
                    f"{field_name} contains forbidden field {forbidden}"
                )
        _validate_normalization(self.normalization)
        _set_structured(self, structured_fields)


@dataclass(frozen=True, init=False)
class ExtractionTrace:
    benchmark_name: str
    payload: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _identifier(self.benchmark_name, "benchmark_name")
        object.__setattr__(self, "payload", _structured(self.payload, "payload"))


@dataclass(frozen=True, init=False)
class AdapterTrace:
    benchmark_name: str
    payload: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _identifier(self.benchmark_name, "benchmark_name")
        object.__setattr__(self, "payload", _structured(self.payload, "payload"))


@dataclass(frozen=True, init=False)
class ComparisonTrace:
    benchmark_name: str
    payload: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _identifier(self.benchmark_name, "benchmark_name")
        object.__setattr__(self, "payload", _structured(self.payload, "payload"))


@dataclass(frozen=True, init=False)
class AuditOutcome:
    benchmark_name: str
    payload: Mapping

    def __init__(self, *args, **kwargs):
        _initialize(self, args, kwargs)

    def __post_init__(self):
        _identifier(self.benchmark_name, "benchmark_name")
        object.__setattr__(self, "payload", _structured(self.payload, "payload"))


def _plain_json(value, field_name="value"):
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain_json(getattr(value, field.name), field.name)
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvidenceSchemaError(
                    f"{field_name} contains a non-string mapping key"
                )
            result[key] = _plain_json(item, field_name)
        return result
    if isinstance(value, (list, tuple)):
        return [_plain_json(item, field_name) for item in value]
    return _freeze_json(value, field_name)


def canonical_json_bytes(value):
    """Return deterministic UTF-8 JSON bytes for supported structured values."""

    plain = _plain_json(value)
    return json.dumps(
        plain,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _duplicates(names):
    return sorted(name for name, count in Counter(names).items() if count > 1)


def _name_diagnostics(expected, actual, *, actual_label, missing_label, orphan_label):
    diagnostics = []
    duplicates = _duplicates(actual)
    if duplicates:
        diagnostics.append(f"duplicate {actual_label}: {', '.join(duplicates)}")
    missing = sorted(set(expected) - set(actual))
    if missing:
        diagnostics.append(f"missing {missing_label}: {', '.join(missing)}")
    orphan = sorted(set(actual) - set(expected))
    if orphan:
        diagnostics.append(f"orphan {orphan_label}: {', '.join(orphan)}")
    return diagnostics


def _ordered_collection(values, field_name):
    if (
        isinstance(values, (str, bytes, bytearray, Mapping, set, frozenset))
        or not isinstance(values, Iterable)
    ):
        raise EvidenceSchemaError(
            f"{field_name} must be an ordered duplicate-preserving iterable"
        )
    return list(values)


def _validated_names(names, collection_name, field_name):
    result = _ordered_collection(names, collection_name)
    for name in result:
        _identifier(name, field_name)
    return result


def validate_pre_run_bijection(registry_names, records):
    """Require one evidence record for every unique registry benchmark."""

    registry = _validated_names(registry_names, "registry_names", "registry_name")
    record_items = _ordered_collection(records, "records")
    record_names = [record.benchmark_name for record in record_items]
    diagnostics = []
    duplicate_registry = _duplicates(registry)
    if duplicate_registry:
        diagnostics.append(
            f"duplicate registry names: {', '.join(duplicate_registry)}"
        )
    diagnostics.extend(
        _name_diagnostics(
            registry,
            record_names,
            actual_label="evidence record names",
            missing_label="evidence records",
            orphan_label="evidence records",
        )
    )
    if diagnostics:
        raise EvidenceSchemaError("; ".join(diagnostics))


def validate_post_run_bijection(
    registry_names, outcomes, report_names_by_artifact
):
    """Require outcomes and each report artifact to exactly cover the registry."""

    registry = _validated_names(registry_names, "registry_names", "registry_name")
    outcome_items = _ordered_collection(outcomes, "outcomes")
    outcome_names = [outcome.benchmark_name for outcome in outcome_items]
    diagnostics = []
    duplicate_registry = _duplicates(registry)
    if duplicate_registry:
        diagnostics.append(
            f"duplicate registry names: {', '.join(duplicate_registry)}"
        )
    diagnostics.extend(
        _name_diagnostics(
            registry,
            outcome_names,
            actual_label="outcome names",
            missing_label="outcomes",
            orphan_label="outcomes",
        )
    )
    if not isinstance(report_names_by_artifact, Mapping):
        raise EvidenceSchemaError("report_names_by_artifact must be a mapping")
    artifact_names = set(report_names_by_artifact)
    if artifact_names != _REPORT_ARTIFACTS:
        missing = sorted(_REPORT_ARTIFACTS - artifact_names)
        extra = sorted(
            artifact_names - _REPORT_ARTIFACTS,
            key=lambda artifact: repr(artifact),
        )
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(repr(name) for name in extra)}")
        raise EvidenceSchemaError(
            f"report artifacts must be exactly csv, markdown, pdf ({'; '.join(details)})"
        )
    for artifact in ("csv", "markdown", "pdf"):
        report_names = _validated_names(
            report_names_by_artifact[artifact],
            f"{artifact} report names",
            f"{artifact} report name",
        )
        diagnostics.extend(
            _name_diagnostics(
                registry,
                report_names,
                actual_label=f"{artifact} report names",
                missing_label=f"{artifact} report names",
                orphan_label=f"{artifact} report names",
            )
        )
    if diagnostics:
        raise EvidenceSchemaError("; ".join(diagnostics))
