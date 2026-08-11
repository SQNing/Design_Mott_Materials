"""Closed transport and evidence contracts for isolated recalculation.

This Task 4 module validates caller-authored data and projects answer-free
worker requests.  It performs no filesystem, registry, source-cache, network,
process, capsule, or scientific operation at import time or during validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import PurePosixPath
from validation import literature_evidence_adapters as _adapters
from validation import literature_evidence_adapter_oracles as _oracles
from validation.literature_evidence_adapters import (
    AdapterContractError as _ContractError,
    AdapterDefinition as _AdapterDefinition,
    FrozenJsonObject as _FrozenJsonObject,
    _CONVERGENCE_KINDS as _ADAPTER_CONVERGENCE_KINDS,
    _OBSERVABLE_IDENTITY_KEYS as _ADAPTER_OBSERVABLE_IDENTITY_KEYS,
    _initialize_closed as _initialize_contract,
    _require_json_integer_magnitude as _require_json_integer,
    _require_nonempty_string as _require_text,
    _require_string_tuple as _require_text_tuple,
    _require_tuple as _require_exact_tuple,
    _seal_contract as _seal_contract,
    _snapshot_json_mapping as _snapshot_json,
    canonical_json_bytes as _canonical_bytes,
    canonical_sha256 as _canonical_sha256,
    require_exact_keys as _exact_keys,
    require_identifier as _identifier,
    validate_adapter_definition as _validate_adapter_definition,
    validate_numerical_controls as _validate_controls,
    validate_scientific_inputs as _validate_inputs,
)


__all__ = (
    "AdapterAuthorityContext",
    "WorkerRequest",
    "ScientificClosure",
    "ScientificPolicyCommitment",
    "InfrastructureClosure",
    "StaticScanReport",
    "RuntimeResourceManifest",
    "RuntimeSnapshot",
    "CapabilityPreflightReport",
    "ProcessAttestation",
    "TracePolicyReport",
    "PointExecutionEvidence",
    "ConvergenceDecision",
    "OracleDecision",
    "AdapterExecutionEvidence",
    "AdapterRunFailure",
    "AdapterRunOutcome",
    "EventRecord",
    "FAILURE_STATUSES",
    "FAILURE_STAGES",
    "FAILURE_REASON_CODES",
    "validate_authority_context",
    "make_worker_request",
    "scientific_policy_combined_sha256",
    "validate_failure",
)


_SHA256_HEX_LENGTH = 64
_AUTHORITY_SCHEMA_VERSION = "adapter_authority_context_v1"
_WORKER_REQUEST_SCHEMA_VERSION = "worker_request_v1"
_PRODUCTION_AUTHORITY_PRODUCER = "task8_canonical_authority_v1"
_TEST_AUTHORITY_PRODUCER = "task7_test_authority_v1"
_AUTHORITY_PRODUCERS = frozenset(
    {_PRODUCTION_AUTHORITY_PRODUCER, _TEST_AUTHORITY_PRODUCER}
)
_FINGERPRINT_ALGORITHM_VERSION = "canonical_json_sha256_v1"
_ROLES = frozenset({"adapter", "oracle"})


def _require_sha256(value: object, field_name: str) -> str:
    if (
        type(value) is not str
        or len(value) != _SHA256_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _ContractError(
            f"{field_name} must be a lowercase SHA-256 hex digest"
        )
    return value


def _require_optional_sha256(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_sha256(value, field_name)


def _require_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise _ContractError(f"{field_name} must be a boolean")
    return value


def _require_nonnegative_integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise _ContractError(
            f"{field_name} must be a nonnegative integer"
        )
    _require_json_integer(value, field_name)
    if value < 0:
        raise _ContractError(
            f"{field_name} must be a nonnegative integer"
        )
    return value


def _require_role(value: object, field_name: str = "role") -> str:
    if type(value) is not str or value not in _ROLES:
        raise _ContractError(f"{field_name} must be adapter or oracle")
    return value


def _snapshot_mapping_tuple(value: object, field_name: str) -> tuple:
    items = _require_exact_tuple(value, field_name)
    return tuple(
        _snapshot_json(item, f"{field_name}[{index}]")
        for index, item in enumerate(items)
    )


def _snapshot_sha256_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _require_exact_tuple(value, field_name)
    return tuple(
        _require_sha256(item, f"{field_name}[{index}]")
        for index, item in enumerate(items)
    )


def _record_field_names(record_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(record_type))


def _mapping_or_exact_record_values(
    value: object,
    record_type: type,
    field_name: str,
) -> dict[str, object]:
    names = _record_field_names(record_type)
    if type(value) is record_type:
        try:
            return {name: getattr(value, name) for name in names}
        except _ContractError:
            raise
        except Exception as error:
            raise _ContractError(
                f"{field_name} attribute extraction failed"
            ) from error
    if isinstance(value, Mapping):
        snapshot = _exact_keys(value, names, field_name)
        return {name: snapshot[name] for name in names}
    raise _ContractError(
        f"{field_name} must be a mapping or exact {record_type.__name__}"
    )


def _normalize_record_error(field_name: str, constructor):
    try:
        return constructor()
    except _ContractError:
        raise
    except Exception as error:
        raise _ContractError(
            f"{field_name} validation failed"
        ) from error


def _record_to_frozen_json(
    value: object, record_type: type
) -> _FrozenJsonObject:
    if type(value) is not record_type:
        raise _ContractError(
            f"value must be an exact {record_type.__name__}"
        )
    raw_values = _mapping_or_exact_record_values(
        value, record_type, record_type.__name__
    )
    return _snapshot_json(
        raw_values,
        record_type.__name__,
    )


def _validate_parameter_provenance(
    scientific_inputs: _FrozenJsonObject,
    provenance: _FrozenJsonObject,
) -> None:
    if set(scientific_inputs) != set(provenance):
        raise _ContractError(
            "parameter_provenance must bind every scientific input "
            "exactly once"
        )
    allowed_kinds = {
        "canonical_model_parameter",
        "source_model_parameter",
        "universal_probe",
    }
    expected = (
        "kind",
        "requirement",
        "locator",
        "commitment_sha256",
        "target_equivalent",
    )
    for parameter_name in provenance:
        record = _exact_keys(
            provenance[parameter_name],
            expected,
            f"parameter_provenance.{parameter_name}",
        )
        if record["kind"] not in allowed_kinds:
            raise _ContractError(
                "parameter provenance has an unknown kind"
            )
        kind = record["kind"]
        requirement = _validate_parameter_requirement(
            kind,
            record["requirement"],
            f"parameter_provenance.{parameter_name}.requirement",
        )
        locator = _validate_parameter_locator(
            kind,
            requirement,
            record["locator"],
            f"parameter_provenance.{parameter_name}.locator",
        )
        commitment_sha256 = _require_sha256(
            record["commitment_sha256"],
            f"parameter_provenance.{parameter_name}.commitment_sha256",
        )
        if (
            kind == "source_model_parameter"
            and commitment_sha256 != _canonical_sha256(locator)
        ):
            raise _ContractError(
                "source-model provenance commitment must equal the "
                "canonical locator hash"
            )
        if record["target_equivalent"] is not False:
            raise _ContractError(
                "target-equivalent parameter provenance is forbidden"
            )


def _require_nonempty_path(value: object, field_name: str) -> tuple[str, ...]:
    path = _require_exact_tuple(value, field_name)
    if not path:
        raise _ContractError(f"{field_name} must be nonempty")
    for index, component in enumerate(path):
        _require_text(component, f"{field_name}[{index}]")
    return path


def _validate_parameter_requirement(
    kind: str,
    value: object,
    field_name: str,
) -> _FrozenJsonObject:
    if kind == "canonical_model_parameter":
        requirement = _exact_keys(
            value, ("canonical_path", "physical_role"), field_name
        )
        _require_nonempty_path(
            requirement["canonical_path"], f"{field_name}.canonical_path"
        )
        _require_text(
            requirement["physical_role"], f"{field_name}.physical_role"
        )
        return requirement
    if kind == "source_model_parameter":
        requirement = _exact_keys(
            value, ("source_path", "physical_role"), field_name
        )
        _require_nonempty_path(
            requirement["source_path"], f"{field_name}.source_path"
        )
        _require_text(
            requirement["physical_role"], f"{field_name}.physical_role"
        )
        return requirement
    if kind == "universal_probe":
        requirement = _exact_keys(
            value, ("probe_role",), field_name
        )
        _require_text(
            requirement["probe_role"], f"{field_name}.probe_role"
        )
        return requirement
    raise _ContractError("parameter provenance has an unknown kind")


def _validate_parameter_locator(
    kind: str,
    requirement: _FrozenJsonObject,
    value: object,
    field_name: str,
) -> _FrozenJsonObject:
    if kind == "canonical_model_parameter":
        locator = _exact_keys(value, ("kind", "path"), field_name)
        if locator["kind"] != "canonical_spec_path":
            raise _ContractError(
                f"{field_name}.kind must be canonical_spec_path"
            )
        path = _require_nonempty_path(locator["path"], f"{field_name}.path")
        if path != requirement["canonical_path"]:
            raise _ContractError(
                f"{field_name}.path must match canonical requirement"
            )
        return locator
    if kind == "source_model_parameter":
        locator = _exact_keys(
            value,
            (
                "kind",
                "source_id",
                "source_sha256",
                "path",
                "coordinate_space",
                "coordinate_view_sha256",
                "byte_start",
                "byte_end",
                "span_sha256",
            ),
            field_name,
        )
        if locator["kind"] != "source_model_span":
            raise _ContractError(
                f"{field_name}.kind must be source_model_span"
            )
        _require_text(
            locator["source_id"], f"{field_name}.source_id"
        )
        _require_sha256(
            locator["source_sha256"], f"{field_name}.source_sha256"
        )
        path = _require_nonempty_path(locator["path"], f"{field_name}.path")
        if path != requirement["source_path"]:
            raise _ContractError(
                f"{field_name}.path must match source requirement"
            )
        if locator["coordinate_space"] != "verified_extracted_text_utf8":
            raise _ContractError(
                f"{field_name}.coordinate_space must be "
                "verified_extracted_text_utf8"
            )
        _require_sha256(
            locator["coordinate_view_sha256"],
            f"{field_name}.coordinate_view_sha256",
        )
        byte_start = _require_nonnegative_integer(
            locator["byte_start"], f"{field_name}.byte_start"
        )
        byte_end = _require_nonnegative_integer(
            locator["byte_end"], f"{field_name}.byte_end"
        )
        if byte_end <= byte_start:
            raise _ContractError(
                f"{field_name}.byte_end must be greater than byte_start "
                "for a nonempty source span"
            )
        _require_sha256(
            locator["span_sha256"], f"{field_name}.span_sha256"
        )
        return locator
    locator = _exact_keys(value, ("kind", "probe_id"), field_name)
    if locator["kind"] != "universal_probe":
        raise _ContractError(
            f"{field_name}.kind must be universal_probe"
        )
    _require_text(locator["probe_id"], f"{field_name}.probe_id")
    return locator


def _validate_numerical_control_provenance(
    numerical_controls: _FrozenJsonObject,
    provenance: _FrozenJsonObject,
) -> None:
    if set(numerical_controls) != set(provenance):
        raise _ContractError(
            "numerical_control_provenance must bind every control exactly once"
        )
    expected = (
        "kind",
        "locator",
        "commitment_sha256",
        "registry_independent",
    )
    for control_name in provenance:
        record = _exact_keys(
            provenance[control_name],
            expected,
            f"numerical_control_provenance.{control_name}",
        )
        if record["kind"] != "numerical_control":
            raise _ContractError(
                "numerical control provenance has an unknown kind"
            )
        _require_text(
            record["locator"],
            f"numerical_control_provenance.{control_name}.locator",
        )
        _require_sha256(
            record["commitment_sha256"],
            f"numerical_control_provenance.{control_name}.commitment_sha256",
        )
        if record["registry_independent"] is not True:
            raise _ContractError(
                "numerical control provenance must be registry independent"
            )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterAuthorityContext:
    schema_version: str
    audit_run_id: str
    benchmark_name: str
    producer_id: str
    producer_code_sha256: str
    canonical_observable_id: str
    observable_identity: _FrozenJsonObject
    canonical_spec_path: str
    canonical_spec_sha256: str
    scientific_inputs: _FrozenJsonObject
    parameter_provenance: _FrozenJsonObject
    numerical_controls: _FrozenJsonObject
    numerical_control_provenance: _FrozenJsonObject
    registry_snapshot_sha256: str
    selector_sha256: str
    forbidden_output_fingerprints: tuple[str, ...]
    fingerprint_algorithm_version: str
    context_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, AdapterAuthorityContext)

    def __post_init__(self) -> None:
        if self.schema_version != _AUTHORITY_SCHEMA_VERSION:
            raise _ContractError(
                "AdapterAuthorityContext has an unknown schema_version"
            )
        _require_text(self.audit_run_id, "audit_run_id")
        _require_text(self.benchmark_name, "benchmark_name")
        if self.producer_id not in _AUTHORITY_PRODUCERS:
            raise _ContractError(
                "authority context has an unknown producer"
            )
        _require_sha256(self.producer_code_sha256, "producer_code_sha256")
        _require_text(
            self.canonical_observable_id, "canonical_observable_id"
        )
        observable_identity = _exact_keys(
            _snapshot_json(
                self.observable_identity, "observable_identity"
            ),
            _ADAPTER_OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        canonical_spec_path = _require_text(
            self.canonical_spec_path, "canonical_spec_path"
        )
        parsed_path = PurePosixPath(canonical_spec_path)
        if (
            parsed_path.is_absolute()
            or ".." in parsed_path.parts
            or canonical_spec_path == "."
            or str(parsed_path) != canonical_spec_path
        ):
            raise _ContractError(
                "canonical_spec_path must be a relative normalized path"
            )
        _require_sha256(self.canonical_spec_sha256, "canonical_spec_sha256")
        scientific_inputs = _snapshot_json(
            self.scientific_inputs, "scientific_inputs"
        )
        parameter_provenance = _snapshot_json(
            self.parameter_provenance, "parameter_provenance"
        )
        numerical_controls = _snapshot_json(
            self.numerical_controls, "numerical_controls"
        )
        numerical_control_provenance = _snapshot_json(
            self.numerical_control_provenance,
            "numerical_control_provenance",
        )
        _validate_parameter_provenance(
            scientific_inputs, parameter_provenance
        )
        _validate_numerical_control_provenance(
            numerical_controls, numerical_control_provenance
        )
        _require_sha256(
            self.registry_snapshot_sha256, "registry_snapshot_sha256"
        )
        _require_sha256(self.selector_sha256, "selector_sha256")
        fingerprints = _snapshot_sha256_tuple(
            self.forbidden_output_fingerprints,
            "forbidden_output_fingerprints",
        )
        if not fingerprints:
            raise _ContractError(
                "forbidden_output_fingerprints must be nonempty"
            )
        if len(set(fingerprints)) != len(fingerprints):
            raise _ContractError(
                "forbidden_output_fingerprints contains a duplicate"
            )
        if fingerprints != tuple(sorted(fingerprints)):
            raise _ContractError(
                "forbidden_output_fingerprints must use canonical ordering"
            )
        if (
            self.fingerprint_algorithm_version
            != _FINGERPRINT_ALGORITHM_VERSION
        ):
            raise _ContractError("unknown fingerprint algorithm version")
        _require_sha256(self.context_sha256, "context_sha256")
        object.__setattr__(self, "observable_identity", observable_identity)
        object.__setattr__(self, "scientific_inputs", scientific_inputs)
        object.__setattr__(
            self, "parameter_provenance", parameter_provenance
        )
        object.__setattr__(self, "numerical_controls", numerical_controls)
        object.__setattr__(
            self,
            "numerical_control_provenance",
            numerical_control_provenance,
        )
        object.__setattr__(
            self, "forbidden_output_fingerprints", fingerprints
        )
        if self.context_sha256 != self.calculated_context_sha256():
            raise _ContractError("authority context hash mismatch")

    def calculated_context_sha256(self) -> str:
        payload = _mapping_or_exact_record_values(
            self,
            AdapterAuthorityContext,
            "authority_context",
        )
        payload.pop("context_sha256")
        return _canonical_sha256(payload)

    def to_frozen_json(self) -> _FrozenJsonObject:
        revalidated = _snapshot_authority_context(self)
        return _record_to_frozen_json(
            revalidated, AdapterAuthorityContext
        )


def _snapshot_authority_context(value: object) -> AdapterAuthorityContext:
    raw_values = _mapping_or_exact_record_values(
        value, AdapterAuthorityContext, "authority_context"
    )
    return _normalize_record_error(
        "authority_context", lambda: AdapterAuthorityContext(**raw_values)
    )


def validate_authority_context(
    value: object,
    *,
    allow_test_producer: bool = False,
) -> AdapterAuthorityContext:
    """Validate authority structure without authenticating upstream I/O."""

    if type(allow_test_producer) is not bool:
        raise _ContractError("allow_test_producer must be a boolean")
    context = _snapshot_authority_context(value)
    if (
        context.producer_id == _TEST_AUTHORITY_PRODUCER
        and not allow_test_producer
    ):
        raise _ContractError(
            "test authority producer requires explicit test-only opt-in"
        )
    return context


@_seal_contract
@dataclass(frozen=True, init=False)
class WorkerRequest:
    schema_version: str
    opaque_run_nonce: str
    adapter_id: str
    scientific_inputs: _FrozenJsonObject
    numerical_controls: _FrozenJsonObject
    capsule_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, WorkerRequest)

    def __post_init__(self) -> None:
        if self.schema_version != _WORKER_REQUEST_SCHEMA_VERSION:
            raise _ContractError(
                "WorkerRequest has an unknown schema_version"
            )
        nonce = _require_text(
            self.opaque_run_nonce, "opaque_run_nonce"
        )
        if len(nonce.encode("utf-8")) > 256:
            raise _ContractError("opaque_run_nonce is too long")
        _identifier(self.adapter_id, "adapter_id")
        try:
            canonical_definition = _adapters.get_adapter_definition(
                self.adapter_id
            )
        except _ContractError as error:
            raise _ContractError(
                "WorkerRequest adapter_id is not in the canonical catalog"
            ) from error
        scientific_inputs = _validate_inputs(
            canonical_definition, self.scientific_inputs
        )
        numerical_controls = _validate_controls(
            canonical_definition, self.numerical_controls
        )
        _require_sha256(self.capsule_sha256, "capsule_sha256")
        object.__setattr__(self, "scientific_inputs", scientific_inputs)
        object.__setattr__(self, "numerical_controls", numerical_controls)

    def to_frozen_json(self) -> _FrozenJsonObject:
        raw_values = _mapping_or_exact_record_values(
            self, WorkerRequest, "worker_request"
        )
        revalidated = _normalize_record_error(
            "worker_request", lambda: WorkerRequest(**raw_values)
        )
        return _record_to_frozen_json(revalidated, WorkerRequest)


def _validate_definition_parameter_provenance(
    definition: _AdapterDefinition,
    context: AdapterAuthorityContext,
) -> None:
    expected_sources = {
        source.parameter_name: source
        for source in definition.parameter_sources
    }
    if set(expected_sources) != set(context.parameter_provenance):
        raise _ContractError(
            "parameter provenance does not bind canonical definition inputs"
        )
    for parameter_name, source in expected_sources.items():
        provenance = context.parameter_provenance[parameter_name]
        if provenance["kind"] != source.kind:
            raise _ContractError(
                f"parameter provenance kind mismatch for {parameter_name}"
            )
        if _canonical_bytes(
            provenance["requirement"]
        ) != _canonical_bytes(source.details):
            raise _ContractError(
                "parameter provenance requirement mismatch for "
                f"{parameter_name}"
            )


def make_worker_request(
    definition: _AdapterDefinition,
    authority_context: AdapterAuthorityContext,
    *,
    opaque_run_nonce: str,
    capsule_sha256: str,
    allow_test_producer: bool = False,
    **extra_metadata: object,
) -> WorkerRequest:
    """Project only answer-free model inputs and controls into a request."""

    if extra_metadata:
        raise _ContractError("worker request contains extra metadata")
    if type(allow_test_producer) is not bool:
        raise _ContractError("allow_test_producer must be a boolean")
    supplied_definition = _validate_adapter_definition(definition)
    try:
        validated_definition = _adapters.get_adapter_definition(
            supplied_definition.adapter_id
        )
    except _ContractError as error:
        raise _ContractError(
            "worker request requires a canonical adapter definition"
        ) from error
    if _canonical_bytes(
        _adapters.adapter_definition_to_frozen_json(supplied_definition)
    ) != _canonical_bytes(
        _adapters.adapter_definition_to_frozen_json(validated_definition)
    ):
        raise _ContractError(
            "detached adapter definition does not match canonical catalog"
        )
    if type(authority_context) is not AdapterAuthorityContext:
        raise _ContractError(
            "authority_context must be a validated exact record"
        )
    context = validate_authority_context(
        authority_context,
        allow_test_producer=allow_test_producer,
    )
    _validate_definition_parameter_provenance(
        validated_definition, context
    )
    scientific_inputs = _validate_inputs(
        validated_definition, context.scientific_inputs
    )
    numerical_controls = _validate_controls(
        validated_definition, context.numerical_controls
    )
    return WorkerRequest(
        schema_version=_WORKER_REQUEST_SCHEMA_VERSION,
        opaque_run_nonce=opaque_run_nonce,
        adapter_id=validated_definition.adapter_id,
        scientific_inputs=scientific_inputs,
        numerical_controls=numerical_controls,
        capsule_sha256=capsule_sha256,
    )


def _require_entry_symbol(value: object, field_name: str) -> str:
    text = _require_text(value, field_name)
    if ":" not in text:
        raise _ContractError(
            f"{field_name} must contain module:function"
        )
    return text


def _require_edge_tuple(value: object, field_name: str) -> tuple:
    items = _require_exact_tuple(value, field_name)
    normalized = []
    for index, item in enumerate(items):
        if type(item) is not tuple or len(item) != 2:
            raise _ContractError(
                f"{field_name}[{index}] must be an exact edge pair"
            )
        source, destination = item
        normalized.append(
            (
                _require_text(source, f"{field_name}[{index}][0]"),
                _require_text(
                    destination, f"{field_name}[{index}][1]"
                ),
            )
        )
    if len(set(normalized)) != len(normalized):
        raise _ContractError(f"{field_name} contains a duplicate edge")
    return tuple(normalized)


@_seal_contract
@dataclass(frozen=True, init=False)
class ScientificClosure:
    schema_version: str
    role: str
    entry_symbol: str
    nodes: tuple[_FrozenJsonObject, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    emitted_source_sha256: str
    bundle_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, ScientificClosure)

    def __post_init__(self) -> None:
        if self.schema_version != "scientific_closure_v1":
            raise _ContractError(
                "ScientificClosure has unknown schema_version"
            )
        _require_role(self.role)
        _require_entry_symbol(self.entry_symbol, "entry_symbol")
        object.__setattr__(
            self, "nodes", _snapshot_mapping_tuple(self.nodes, "nodes")
        )
        object.__setattr__(
            self,
            "dependency_edges",
            _require_edge_tuple(self.dependency_edges, "dependency_edges"),
        )
        _require_sha256(self.emitted_source_sha256, "emitted_source_sha256")
        _require_sha256(self.bundle_sha256, "bundle_sha256")


_ADAPTER_DEFINITION_FIELDS = frozenset(
    {
        "adapter_id",
        "entry_symbol",
        "observable_identity",
        "scientific_input_schema",
        "numerical_control_schema",
        "parameter_sources",
        "output_schema",
        "backend_kind",
        "problem_size_policy",
        "runtime_requirements",
        "convergence_contract",
        "counterfactual_domain",
        "oracle_id",
        "resource_limits",
    }
)
_ORACLE_DEFINITION_FIELDS = frozenset(
    {
        "oracle_id",
        "entry_symbol",
        "input_schema",
        "result_schema",
        "runtime_requirements",
        "convergence_invariant_contract",
        "resource_limits",
    }
)


def _parse_canonical_definition_bytes(value: object, role: str) -> object:
    if type(value) is not bytes:
        raise _ContractError(
            "canonical_definition_bytes must be exact bytes"
        )
    if len(value) > 1_048_576:
        raise _ContractError("canonical_definition_bytes is oversized")
    try:
        decoded = value.decode("utf-8")
        parsed = json.loads(
            decoded,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {token}")
            ),
        )
    except (
        UnicodeDecodeError,
        ValueError,
        TypeError,
        RecursionError,
    ) as error:
        raise _ContractError(
            "canonical_definition_bytes is not canonical JSON"
        ) from error
    if _canonical_bytes(parsed) != value:
        raise _ContractError(
            "canonical_definition_bytes is noncanonical"
        )
    frozen = _snapshot_json(parsed, "canonical_definition")
    if role == "adapter":
        definition = _adapters.adapter_definition_from_frozen_json(frozen)
        rebuilt = _adapters.adapter_definition_to_frozen_json(definition)
    else:
        definition = _oracles.oracle_definition_from_frozen_json(frozen)
        rebuilt = _oracles.oracle_definition_to_frozen_json(definition)
    if _canonical_bytes(rebuilt) != value:
        raise _ContractError(
            "canonical definition bytes do not round-trip exactly"
        )
    return definition


_POLICY_NOT_APPLICABLE = _FrozenJsonObject({"kind": "not_applicable"})


def _adapter_policy_derivations(
    definition: _AdapterDefinition,
) -> tuple[object, str, str, str, str, str]:
    payload = _adapters.adapter_definition_to_frozen_json(definition)
    matching_rows = tuple(
        benchmark_id
        for benchmark_id, decision in _adapters.ADAPTER_ELIGIBILITY.items()
        if decision.adapter_id == definition.adapter_id
    )
    if len(matching_rows) != 1:
        raise _ContractError(
            "adapter definition must resolve exactly one eligibility row"
        )
    benchmark_id = matching_rows[0]
    return (
        payload["output_schema"],
        _canonical_sha256(payload["counterfactual_domain"]),
        _canonical_sha256(payload["problem_size_policy"]),
        _canonical_sha256(payload["convergence_contract"]),
        _canonical_sha256(
            _adapters.adapter_eligibility_row_to_frozen_json(benchmark_id)
        ),
        _canonical_sha256(
            _adapters.adapter_eligibility_catalog_to_frozen_json()
        ),
    )


def _oracle_policy_derivations(
    definition: _oracles.OracleDefinition,
) -> tuple[object, str, str, str]:
    payload = _oracles.oracle_definition_to_frozen_json(definition)
    bindings = {
        "result_schema": payload["result_schema"],
        "convergence_invariant_contract": (
            payload["convergence_invariant_contract"]
        ),
    }
    not_applicable_sha256 = _canonical_sha256(_POLICY_NOT_APPLICABLE)
    return (
        bindings,
        not_applicable_sha256,
        not_applicable_sha256,
        _canonical_sha256(payload["convergence_invariant_contract"]),
    )


_SCIENTIFIC_POLICY_FIELDS = (
    "schema_version",
    "role",
    "definition_id",
    "canonical_definition_bytes",
    "canonical_definition_sha256",
    "eligibility_row_sha256",
    "eligibility_catalog_sha256",
    "entry_closure_sha256",
    "output_or_invariant_proof_bindings",
    "domain_sha256",
    "size_policy_sha256",
    "convergence_sha256",
    "static_scan_sha256",
    "combined_sha256",
)


def scientific_policy_combined_sha256(value: Mapping[str, object]) -> str:
    """Hash a canonical policy payload, excluding its stored combined hash."""

    if not isinstance(value, Mapping):
        raise _ContractError(
            "scientific policy commitment must be a mapping"
        )
    allowed = set(_SCIENTIFIC_POLICY_FIELDS)
    actual = set(value)
    if not actual <= allowed or not (allowed - {"combined_sha256"}) <= actual:
        raise _ContractError(
            "scientific policy commitment has unknown or missing fields"
        )
    payload = {}
    for key in _SCIENTIFIC_POLICY_FIELDS:
        if key == "combined_sha256" or key not in value:
            continue
        item = value[key]
        if key == "canonical_definition_bytes":
            if type(item) is not bytes:
                raise _ContractError(
                    "canonical_definition_bytes must be exact bytes"
                )
            try:
                item = item.decode("utf-8")
            except UnicodeDecodeError as error:
                raise _ContractError(
                    "canonical_definition_bytes must be UTF-8"
                ) from error
        payload[key] = item
    return _canonical_sha256(payload)


@_seal_contract
@dataclass(frozen=True, init=False)
class ScientificPolicyCommitment:
    schema_version: str
    role: str
    definition_id: str
    canonical_definition_bytes: bytes
    canonical_definition_sha256: str
    eligibility_row_sha256: str | None
    eligibility_catalog_sha256: str | None
    entry_closure_sha256: str
    output_or_invariant_proof_bindings: _FrozenJsonObject
    domain_sha256: str
    size_policy_sha256: str
    convergence_sha256: str
    static_scan_sha256: str
    combined_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, ScientificPolicyCommitment)

    def __post_init__(self) -> None:
        if self.schema_version != "scientific_policy_commitment_v1":
            raise _ContractError(
                "ScientificPolicyCommitment has unknown schema_version"
            )
        role = _require_role(self.role)
        _identifier(self.definition_id, "definition_id")
        canonical_definition = _parse_canonical_definition_bytes(
            self.canonical_definition_bytes, role
        )
        identifier_field = "adapter_id" if role == "adapter" else "oracle_id"
        if (
            getattr(canonical_definition, identifier_field)
            != self.definition_id
        ):
            raise _ContractError(
                "definition_id does not match canonical definition bytes"
            )
        policy_definition = canonical_definition
        if role == "adapter":
            try:
                catalog_definition = _adapters.get_adapter_definition(
                    self.definition_id
                )
            except _ContractError as error:
                raise _ContractError(
                    "adapter policy definition is absent from the "
                    "canonical catalog"
                ) from error
            catalog_definition_bytes = _canonical_bytes(
                _adapters.adapter_definition_to_frozen_json(
                    catalog_definition
                )
            )
            if self.canonical_definition_bytes != catalog_definition_bytes:
                raise _ContractError(
                    "adapter policy canonical definition bytes do not "
                    "match the canonical catalog"
                )
            policy_definition = catalog_definition
        expected_definition_hash = hashlib.sha256(
            self.canonical_definition_bytes
        ).hexdigest()
        if self.canonical_definition_sha256 != expected_definition_hash:
            raise _ContractError("canonical definition hash mismatch")
        if role == "adapter":
            _require_sha256(
                self.eligibility_row_sha256, "eligibility_row_sha256"
            )
            _require_sha256(
                self.eligibility_catalog_sha256,
                "eligibility_catalog_sha256",
            )
        elif (
            self.eligibility_row_sha256 is not None
            or self.eligibility_catalog_sha256 is not None
        ):
            raise _ContractError(
                "oracle policy cannot contain adapter eligibility hashes"
            )
        for field_name in (
            "entry_closure_sha256",
            "domain_sha256",
            "size_policy_sha256",
            "convergence_sha256",
            "static_scan_sha256",
            "combined_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        bindings = _snapshot_json(
            self.output_or_invariant_proof_bindings,
            "output_or_invariant_proof_bindings",
        )
        if not bindings:
            raise _ContractError(
                "output_or_invariant_proof_bindings must be nonempty"
            )
        object.__setattr__(
            self, "output_or_invariant_proof_bindings", bindings
        )
        if role == "adapter":
            (
                expected_bindings,
                expected_domain,
                expected_size_policy,
                expected_convergence,
                expected_eligibility_row,
                expected_eligibility_catalog,
            ) = _adapter_policy_derivations(policy_definition)
            if _canonical_bytes(bindings) != _canonical_bytes(
                expected_bindings
            ):
                raise _ContractError(
                    "output proof bindings mismatch canonical definition"
                )
            if self.eligibility_row_sha256 != expected_eligibility_row:
                raise _ContractError(
                    "eligibility row hash mismatch closed catalog"
                )
            if (
                self.eligibility_catalog_sha256
                != expected_eligibility_catalog
            ):
                raise _ContractError(
                    "eligibility catalog hash mismatch closed catalog"
                )
        else:
            (
                expected_bindings,
                expected_domain,
                expected_size_policy,
                expected_convergence,
            ) = _oracle_policy_derivations(canonical_definition)
            if _canonical_bytes(bindings) != _canonical_bytes(
                expected_bindings
            ):
                raise _ContractError(
                    "oracle invariant proof bindings mismatch definition"
                )
        if self.domain_sha256 != expected_domain:
            raise _ContractError("domain hash mismatch definition")
        if self.size_policy_sha256 != expected_size_policy:
            raise _ContractError(
                "size policy hash mismatch definition"
            )
        if self.convergence_sha256 != expected_convergence:
            raise _ContractError(
                "convergence hash mismatch definition"
            )
        calculated = scientific_policy_combined_sha256(
            {
                field.name: getattr(self, field.name)
                for field in fields(ScientificPolicyCommitment)
            }
        )
        if self.combined_sha256 != calculated:
            raise _ContractError(
                "scientific policy combined hash mismatch"
            )


@_seal_contract
@dataclass(frozen=True, init=False)
class InfrastructureClosure:
    schema_version: str
    roots: tuple[str, ...]
    nodes: tuple[_FrozenJsonObject, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    purpose_bindings: _FrozenJsonObject
    bundle_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, InfrastructureClosure)

    def __post_init__(self) -> None:
        if self.schema_version != "infrastructure_closure_v1":
            raise _ContractError(
                "InfrastructureClosure has unknown schema_version"
            )
        roots = _require_text_tuple(self.roots, "roots")
        object.__setattr__(self, "roots", tuple(roots))
        object.__setattr__(
            self, "nodes", _snapshot_mapping_tuple(self.nodes, "nodes")
        )
        object.__setattr__(
            self,
            "dependency_edges",
            _require_edge_tuple(self.dependency_edges, "dependency_edges"),
        )
        object.__setattr__(
            self,
            "purpose_bindings",
            _snapshot_json(self.purpose_bindings, "purpose_bindings"),
        )
        _require_sha256(self.bundle_sha256, "bundle_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class StaticScanReport:
    schema_version: str
    role: str
    scanner_version: str
    scanner_sha256: str
    scanned_closure_sha256: str
    fingerprint_commitment_sha256: str
    checks: _FrozenJsonObject
    passed: bool
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, StaticScanReport)

    def __post_init__(self) -> None:
        if self.schema_version != "static_scan_report_v1":
            raise _ContractError(
                "StaticScanReport has unknown schema_version"
            )
        if self.role not in {"adapter", "oracle", "infrastructure"}:
            raise _ContractError("StaticScanReport has unknown role")
        _require_text(self.scanner_version, "scanner_version")
        for field_name in (
            "scanner_sha256",
            "scanned_closure_sha256",
            "fingerprint_commitment_sha256",
            "report_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        object.__setattr__(
            self, "checks", _snapshot_json(self.checks, "checks")
        )
        _require_bool(self.passed, "passed")


@_seal_contract
@dataclass(frozen=True, init=False)
class RuntimeResourceManifest:
    schema_version: str
    resources: tuple[_FrozenJsonObject, ...]
    manifest_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, RuntimeResourceManifest)

    def __post_init__(self) -> None:
        if self.schema_version != "runtime_resource_manifest_v1":
            raise _ContractError(
                "RuntimeResourceManifest has unknown schema_version"
            )
        object.__setattr__(
            self,
            "resources",
            _snapshot_mapping_tuple(self.resources, "resources"),
        )
        _require_sha256(self.manifest_sha256, "manifest_sha256")


def _snapshot_runtime_manifest(value: object) -> RuntimeResourceManifest:
    if type(value) is not RuntimeResourceManifest:
        raise _ContractError(
            "manifest must be an exact RuntimeResourceManifest"
        )
    return RuntimeResourceManifest(
        value.schema_version, value.resources, value.manifest_sha256
    )


@_seal_contract
@dataclass(frozen=True, init=False)
class RuntimeSnapshot:
    schema_version: str
    manifest: RuntimeResourceManifest
    snapshot_root: str
    directory_identities: tuple[_FrozenJsonObject, ...]
    snapshot_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, RuntimeSnapshot)

    def __post_init__(self) -> None:
        if self.schema_version != "runtime_snapshot_v1":
            raise _ContractError(
                "RuntimeSnapshot has unknown schema_version"
            )
        object.__setattr__(
            self, "manifest", _snapshot_runtime_manifest(self.manifest)
        )
        _require_text(self.snapshot_root, "snapshot_root")
        object.__setattr__(
            self,
            "directory_identities",
            _snapshot_mapping_tuple(
                self.directory_identities, "directory_identities"
            ),
        )
        _require_sha256(self.snapshot_sha256, "snapshot_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class CapabilityPreflightReport:
    schema_version: str
    audit_run_id: str
    available: bool
    checks: _FrozenJsonObject
    command_identities: _FrozenJsonObject
    namespace_identifiers: _FrozenJsonObject
    mount_facts: _FrozenJsonObject
    probe_result_codes: _FrozenJsonObject
    trace_sha256: str
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, CapabilityPreflightReport)

    def __post_init__(self) -> None:
        if self.schema_version != "capability_preflight_report_v1":
            raise _ContractError(
                "CapabilityPreflightReport has unknown schema_version"
            )
        _require_text(self.audit_run_id, "audit_run_id")
        _require_bool(self.available, "available")
        for field_name in (
            "checks",
            "command_identities",
            "namespace_identifiers",
            "mount_facts",
            "probe_result_codes",
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_json(getattr(self, field_name), field_name),
            )
        _require_sha256(self.trace_sha256, "trace_sha256")
        _require_sha256(self.report_sha256, "report_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class ProcessAttestation:
    schema_version: str
    process_role: str
    point_id: str
    namespace_identifiers: _FrozenJsonObject
    mount_facts: _FrozenJsonObject
    environment_facts: _FrozenJsonObject
    resource_limit_facts: _FrozenJsonObject
    chroot_facts: _FrozenJsonObject
    attestation_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, ProcessAttestation)

    def __post_init__(self) -> None:
        if self.schema_version != "process_attestation_v1":
            raise _ContractError(
                "ProcessAttestation has unknown schema_version"
            )
        _require_role(self.process_role, "process_role")
        _require_text(self.point_id, "point_id")
        for field_name in (
            "namespace_identifiers",
            "mount_facts",
            "environment_facts",
            "resource_limit_facts",
            "chroot_facts",
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_json(getattr(self, field_name), field_name),
            )
        _require_sha256(self.attestation_sha256, "attestation_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class TracePolicyReport:
    schema_version: str
    trace_sha256: str
    attempted_accesses: tuple[_FrozenJsonObject, ...]
    violations: tuple[_FrozenJsonObject, ...]
    passed: bool
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, TracePolicyReport)

    def __post_init__(self) -> None:
        if self.schema_version != "trace_policy_report_v1":
            raise _ContractError(
                "TracePolicyReport has unknown schema_version"
            )
        _require_sha256(self.trace_sha256, "trace_sha256")
        object.__setattr__(
            self,
            "attempted_accesses",
            _snapshot_mapping_tuple(
                self.attempted_accesses, "attempted_accesses"
            ),
        )
        object.__setattr__(
            self,
            "violations",
            _snapshot_mapping_tuple(self.violations, "violations"),
        )
        _require_bool(self.passed, "passed")
        _require_sha256(self.report_sha256, "report_sha256")


def _snapshot_process_attestation(value: object) -> ProcessAttestation:
    if type(value) is not ProcessAttestation:
        raise _ContractError(
            "process_attestation must be an exact ProcessAttestation"
        )
    return ProcessAttestation(
        **{
            name: getattr(value, name)
            for name in _record_field_names(type(value))
        }
    )


def _snapshot_trace_policy_report(value: object) -> TracePolicyReport:
    if type(value) is not TracePolicyReport:
        raise _ContractError(
            "trace_policy_report must be an exact TracePolicyReport"
        )
    return TracePolicyReport(
        **{
            name: getattr(value, name)
            for name in _record_field_names(type(value))
        }
    )


@_seal_contract
@dataclass(frozen=True, init=False)
class PointExecutionEvidence:
    schema_version: str
    point_id: str
    request_sha256: str
    result_sha256: str
    trace_policy_report: TracePolicyReport
    process_attestation: ProcessAttestation
    backend_diagnostics: _FrozenJsonObject
    exit_status: int
    execution_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, PointExecutionEvidence)

    def __post_init__(self) -> None:
        if self.schema_version != "point_execution_evidence_v1":
            raise _ContractError(
                "PointExecutionEvidence has unknown schema_version"
            )
        _require_text(self.point_id, "point_id")
        _require_sha256(self.request_sha256, "request_sha256")
        _require_sha256(self.result_sha256, "result_sha256")
        object.__setattr__(
            self,
            "trace_policy_report",
            _snapshot_trace_policy_report(self.trace_policy_report),
        )
        object.__setattr__(
            self,
            "process_attestation",
            _snapshot_process_attestation(self.process_attestation),
        )
        object.__setattr__(
            self,
            "backend_diagnostics",
            _snapshot_json(
                self.backend_diagnostics, "backend_diagnostics"
            ),
        )
        _require_nonnegative_integer(self.exit_status, "exit_status")
        _require_sha256(self.execution_sha256, "execution_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class ConvergenceDecision:
    schema_version: str
    kind: str
    accepted: bool
    raw_evidence_sha256: str
    reason_code: str
    decision_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, ConvergenceDecision)

    def __post_init__(self) -> None:
        if self.schema_version != "convergence_decision_v1":
            raise _ContractError(
                "ConvergenceDecision has unknown schema_version"
            )
        if self.kind not in _ADAPTER_CONVERGENCE_KINDS:
            raise _ContractError("ConvergenceDecision has unknown kind")
        _require_bool(self.accepted, "accepted")
        _require_sha256(self.raw_evidence_sha256, "raw_evidence_sha256")
        _identifier(self.reason_code, "reason_code")
        _require_sha256(self.decision_sha256, "decision_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class OracleDecision:
    schema_version: str
    oracle_id: str
    accepted: bool
    oracle_execution_evidence_hashes: tuple[str, ...]
    residuals: _FrozenJsonObject
    invariants: _FrozenJsonObject
    reason_code: str
    decision_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, OracleDecision)

    def __post_init__(self) -> None:
        if self.schema_version != "oracle_decision_v1":
            raise _ContractError(
                "OracleDecision has unknown schema_version"
            )
        _identifier(self.oracle_id, "oracle_id")
        _require_bool(self.accepted, "accepted")
        object.__setattr__(
            self,
            "oracle_execution_evidence_hashes",
            _snapshot_sha256_tuple(
                self.oracle_execution_evidence_hashes,
                "oracle_execution_evidence_hashes",
            ),
        )
        object.__setattr__(
            self,
            "residuals",
            _snapshot_json(self.residuals, "residuals"),
        )
        object.__setattr__(
            self,
            "invariants",
            _snapshot_json(self.invariants, "invariants"),
        )
        _identifier(self.reason_code, "reason_code")
        _require_sha256(self.decision_sha256, "decision_sha256")


def _snapshot_exact_record(value: object, record_type: type, field_name: str):
    if type(value) is not record_type:
        raise _ContractError(
            f"{field_name} must be an exact {record_type.__name__}"
        )
    return record_type(
        **{
            name: getattr(value, name)
            for name in _record_field_names(record_type)
        }
    )


@_seal_contract
@dataclass(frozen=True, init=False)
class EventRecord:
    sequence_number: int
    event_name: str
    details: _FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, EventRecord)

    def __post_init__(self) -> None:
        _require_nonnegative_integer(self.sequence_number, "sequence_number")
        _identifier(self.event_name, "event_name")
        object.__setattr__(
            self, "details", _snapshot_json(self.details, "details")
        )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterExecutionEvidence:
    schema_version: str
    status: str
    authority_context_sha256: str
    validated_inputs_and_provenance: _FrozenJsonObject
    eligibility_commitments: _FrozenJsonObject
    adapter_policy_commitment: ScientificPolicyCommitment
    oracle_policy_commitment: ScientificPolicyCommitment
    adapter_scientific_closure: ScientificClosure
    oracle_scientific_closure: ScientificClosure
    infrastructure_closure: InfrastructureClosure
    static_scan_reports: tuple[StaticScanReport, ...]
    runtime_snapshot: RuntimeSnapshot
    ordering_events: tuple[EventRecord, ...]
    capability_preflight_sha256: str
    point_executions: tuple[PointExecutionEvidence, ...]
    convergence_decision: ConvergenceDecision
    oracle_decision: OracleDecision
    disclosed_seed_hex: str
    bundle_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, AdapterExecutionEvidence)

    def __post_init__(self) -> None:
        if self.schema_version != "adapter_execution_evidence_v1":
            raise _ContractError(
                "AdapterExecutionEvidence has unknown schema_version"
            )
        if self.status != "isolated_recomputation_succeeded":
            raise _ContractError(
                "AdapterExecutionEvidence carries only isolated success"
            )
        _require_sha256(
            self.authority_context_sha256, "authority_context_sha256"
        )
        for field_name in (
            "validated_inputs_and_provenance",
            "eligibility_commitments",
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_json(getattr(self, field_name), field_name),
            )
        for field_name, record_type in (
            ("adapter_policy_commitment", ScientificPolicyCommitment),
            ("oracle_policy_commitment", ScientificPolicyCommitment),
            ("adapter_scientific_closure", ScientificClosure),
            ("oracle_scientific_closure", ScientificClosure),
            ("infrastructure_closure", InfrastructureClosure),
            ("runtime_snapshot", RuntimeSnapshot),
            ("convergence_decision", ConvergenceDecision),
            ("oracle_decision", OracleDecision),
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_exact_record(
                    getattr(self, field_name), record_type, field_name
                ),
            )
        scans = _require_exact_tuple(
            self.static_scan_reports, "static_scan_reports"
        )
        object.__setattr__(
            self,
            "static_scan_reports",
            tuple(
                _snapshot_exact_record(item, StaticScanReport, "scan_report")
                for item in scans
            ),
        )
        events = _require_exact_tuple(self.ordering_events, "ordering_events")
        object.__setattr__(
            self,
            "ordering_events",
            tuple(
                _snapshot_exact_record(item, EventRecord, "event")
                for item in events
            ),
        )
        points = _require_exact_tuple(
            self.point_executions, "point_executions"
        )
        object.__setattr__(
            self,
            "point_executions",
            tuple(
                _snapshot_exact_record(
                    item, PointExecutionEvidence, "point_execution"
                )
                for item in points
            ),
        )
        _require_sha256(
            self.capability_preflight_sha256,
            "capability_preflight_sha256",
        )
        if (
            type(self.disclosed_seed_hex) is not str
            or len(self.disclosed_seed_hex) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.disclosed_seed_hex
            )
        ):
            raise _ContractError(
                "disclosed_seed_hex must encode exactly 32 bytes"
            )
        _require_sha256(self.bundle_sha256, "bundle_sha256")


FAILURE_STATUSES = frozenset(
    {
        "strict_recomputation_unavailable",
        "adapter_ineligible",
        "input_rejected",
        "dependency_rejected",
        "isolation_failed",
        "execution_failed",
        "convergence_failed",
        "oracle_failed",
    }
)
FAILURE_STAGES = frozenset(
    {
        "definition_validation",
        "authority_validation",
        "eligibility_validation",
        "scientific_input_validation",
        "numerical_control_validation",
        "scientific_closure",
        "static_scan",
        "scientific_policy_commitment",
        "infrastructure_closure",
        "dependency_partition",
        "runtime_snapshot",
        "capability_preflight",
        "seed_generation",
        "request_write",
        "isolation_setup",
        "worker_execution",
        "trace_policy",
        "output_ingestion",
        "result_validation",
        "convergence",
        "oracle_closure",
        "oracle_isolation",
        "oracle_output",
        "oracle_decision",
        "runtime_snapshot_revalidation",
        "evidence_finalization",
    }
)
FAILURE_REASON_CODES = frozenset(
    {
        "unknown_adapter",
        "authority_context_rejected",
        "adapter_source_parse_only",
        "scientific_input_rejected",
        "numerical_control_rejected",
        "dependency_policy_rejected",
        "scientific_policy_rejected",
        "infrastructure_dependency_rejected",
        "runtime_resource_unavailable",
        "capability_preflight_failed",
        "seed_generation_failed",
        "request_write_failed",
        "namespace_setup_failed",
        "worker_timeout",
        "worker_signaled",
        "worker_nonzero_exit",
        "trace_missing",
        "trace_policy_violation",
        "worker_output_rejected",
        "local_result_rejected",
        "convergence_contract_failed",
        "oracle_dependency_rejected",
        "oracle_isolation_failed",
        "oracle_output_rejected",
        "oracle_invariant_failed",
        "runtime_snapshot_changed",
        "evidence_hash_failed",
    }
)
_FAILURE_DIAGNOSTIC_MAX_BYTES = 1024
_FAILURE_DIAGNOSTICS = {
    "unknown_adapter": "adapter identifier is not declared",
    "authority_context_rejected": "authority context validation failed",
    "adapter_source_parse_only": "adapter is not eligible for recalculation",
    "scientific_input_rejected": "scientific input validation failed",
    "numerical_control_rejected": "numerical control validation failed",
    "dependency_policy_rejected": "dependency policy validation failed",
    "scientific_policy_rejected": "scientific policy validation failed",
    "infrastructure_dependency_rejected": (
        "infrastructure dependency validation failed"
    ),
    "runtime_resource_unavailable": "required runtime resource is unavailable",
    "capability_preflight_failed": "capability preflight failed",
    "seed_generation_failed": "seed generation failed",
    "request_write_failed": "worker request write failed",
    "namespace_setup_failed": "isolation namespace setup failed",
    "worker_timeout": "worker exceeded the declared wall-time limit",
    "worker_signaled": "worker terminated by signal",
    "worker_nonzero_exit": "worker returned a nonzero exit status",
    "trace_missing": "required execution trace is unavailable",
    "trace_policy_violation": "execution trace violated isolation policy",
    "worker_output_rejected": "worker output validation failed",
    "local_result_rejected": "local result validation failed",
    "convergence_contract_failed": "convergence contract validation failed",
    "oracle_dependency_rejected": "oracle dependency validation failed",
    "oracle_isolation_failed": "oracle isolation failed",
    "oracle_output_rejected": "oracle output validation failed",
    "oracle_invariant_failed": "oracle invariant validation failed",
    "runtime_snapshot_changed": "runtime snapshot changed during execution",
    "evidence_hash_failed": "evidence hash validation failed",
}
_FAILURE_HASH_FIELDS = frozenset(
    {
        "authority_context_sha256",
        "capsule_sha256",
        "request_sha256",
        "scientific_closure_sha256",
        "scientific_policy_sha256",
        "infrastructure_closure_sha256",
        "runtime_snapshot_sha256",
        "capability_preflight_sha256",
        "trace_sha256",
        "worker_output_sha256",
        "local_result_sha256",
        "oracle_output_sha256",
    }
)
_FAILURE_ATTESTATION_FIELDS = frozenset(
    {
        "authority_validated",
        "eligibility_validated",
        "scientific_closure_created",
        "scientific_policy_committed",
        "infrastructure_closure_created",
        "runtime_snapshot_created",
        "capability_preflight_completed",
        "request_written",
        "namespace_created",
        "resource_limits_applied",
        "worker_started",
        "trace_collected",
        "worker_output_captured",
        "local_result_validated",
        "oracle_started",
        "oracle_output_captured",
        "runtime_snapshot_revalidated",
    }
)


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterRunFailure:
    schema_version: str
    status: str
    stage: str
    reason_code: str
    diagnostic: str
    available_hashes: _FrozenJsonObject
    available_attestations: _FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, AdapterRunFailure)

    def __post_init__(self) -> None:
        if self.schema_version != "adapter_run_failure_v1":
            raise _ContractError(
                "AdapterRunFailure has unknown schema_version"
            )
        if self.status not in FAILURE_STATUSES:
            raise _ContractError("failure status is not closed")
        if self.stage not in FAILURE_STAGES:
            raise _ContractError("failure stage is not closed")
        if self.reason_code not in FAILURE_REASON_CODES:
            raise _ContractError("failure reason_code is not closed")
        diagnostic = _require_text(self.diagnostic, "diagnostic")
        if len(diagnostic.encode("utf-8")) > _FAILURE_DIAGNOSTIC_MAX_BYTES:
            raise _ContractError("failure diagnostic is oversized")
        if diagnostic != _FAILURE_DIAGNOSTICS[self.reason_code]:
            raise _ContractError(
                "failure diagnostic does not match the closed reason template"
            )
        available_hashes = _snapshot_json(
            self.available_hashes, "available_hashes"
        )
        for name, digest in available_hashes._items:
            if name not in _FAILURE_HASH_FIELDS:
                raise _ContractError(
                    f"available_hashes contains unknown field {name}"
                )
            _require_sha256(digest, f"available_hashes.{name}")
        available_attestations = _snapshot_json(
            self.available_attestations, "available_attestations"
        )
        for name, attestation in available_attestations._items:
            if name not in _FAILURE_ATTESTATION_FIELDS:
                raise _ContractError(
                    f"available_attestations contains unknown field {name}"
                )
            _require_bool(
                attestation, f"available_attestations.{name}"
            )
        object.__setattr__(self, "available_hashes", available_hashes)
        object.__setattr__(
            self, "available_attestations", available_attestations
        )


def validate_failure(value: object) -> AdapterRunFailure:
    """Return a fresh, bounded failure object with no success material."""

    raw_values = _mapping_or_exact_record_values(
        value, AdapterRunFailure, "failure"
    )
    return _normalize_record_error(
        "failure", lambda: AdapterRunFailure(**raw_values)
    )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterRunOutcome:
    status: str
    evidence: AdapterExecutionEvidence | None
    failure: AdapterRunFailure | None

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, AdapterRunOutcome)

    def __post_init__(self) -> None:
        if self.status == "isolated_recomputation_succeeded":
            if type(self.evidence) is not AdapterExecutionEvidence:
                raise _ContractError(
                    "successful outcome requires evidence"
                )
            if self.failure is not None:
                raise _ContractError(
                    "successful outcome cannot carry failure"
                )
            object.__setattr__(
                self,
                "evidence",
                _snapshot_exact_record(
                    self.evidence, AdapterExecutionEvidence, "evidence"
                ),
            )
        elif self.status in FAILURE_STATUSES:
            if self.evidence is not None:
                raise _ContractError(
                    "failed outcome cannot carry evidence"
                )
            if type(self.failure) is not AdapterRunFailure:
                raise _ContractError("failed outcome requires failure")
            failure = validate_failure(self.failure)
            if failure.status != self.status:
                raise _ContractError(
                    "outcome status does not match failure status"
                )
            object.__setattr__(self, "failure", failure)
        else:
            raise _ContractError("AdapterRunOutcome has unknown status")
