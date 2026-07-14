"""Bounded, immutable schemas for literature evidence audit artifacts."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
import json
import math
import re
from types import MappingProxyType


class EvidenceSchemaError(ValueError):
    """Raised when literature evidence data violates its schema."""


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_EVIDENCE_MODES = frozenset(
    {"local_recompute", "local_source_parse", "projection_only"}
)
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
    if not isinstance(value, str) or not value.strip():
        raise EvidenceSchemaError(f"{field_name} must be a nonempty string")
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
        for field_name in (
            "canonical_observable_id",
            "benchmark_name",
            "subject",
            "system",
            "units",
        ):
            _identifier(getattr(self, field_name), field_name)
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
        _identifier(self.media_type, "media_type")
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
            "canonical_observable_id",
            "target_parser",
            "adapter",
        ):
            _identifier(getattr(self, field_name), field_name)
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
        normalization = self.normalization
        if not isinstance(normalization, Mapping):
            raise EvidenceSchemaError("normalization must be a structured mapping")
        kind = normalization.get("kind")
        has_rules = any(
            key in normalization and normalization[key]
            for key in ("rules", "executable", "fields", "operations")
        )
        if not isinstance(kind, str) or not kind.strip() or not has_rules:
            raise EvidenceSchemaError(
                "normalization requires a nonempty kind and executable or field rules"
            )
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


def _validated_names(names, field_name):
    result = list(names)
    for name in result:
        _identifier(name, field_name)
    return result


def validate_pre_run_bijection(registry_names, records):
    """Require one evidence record for every unique registry benchmark."""

    registry = _validated_names(registry_names, "registry_name")
    record_names = [record.benchmark_name for record in records]
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

    registry = _validated_names(registry_names, "registry_name")
    outcome_names = [outcome.benchmark_name for outcome in outcomes]
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
    for artifact, names in report_names_by_artifact.items():
        _identifier(artifact, "report artifact")
        report_names = _validated_names(names, f"{artifact} report name")
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
