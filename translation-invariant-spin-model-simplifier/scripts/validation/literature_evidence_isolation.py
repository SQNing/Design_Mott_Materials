"""Closed transport and evidence contracts for isolated recalculation.

This Task 4 module validates caller-authored data and projects answer-free
worker requests.  It performs no filesystem, registry, source-cache, network,
process, capsule, or scientific operation at import time or during validation.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType
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
    "build_scientific_closure",
    "build_scientific_policy_commitment",
    "build_infrastructure_closure",
    "assert_disjoint_scientific_closures",
    "assert_complete_dependency_partition",
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


_AST_CLOSURE_VERSION = "deterministic_ast_closure_v1"
_POLICY_STRUCTURE_SCAN_VERSION = "task5_policy_structure_scan_v1"
_AST_NODE_FIELDS = frozenset(
    {
        "relative_path",
        "raw_file_sha256",
        "node_kind",
        "qualified_name",
        "source_span_sha256",
        "emitted_node_sha256",
        "dependency_edges",
        "scanner_version",
    }
)
_AST_NODE_KINDS = frozenset(
    {"import", "immutable_constant", "function", "class"}
)
_ENTRY_SYMBOL_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
    r":[A-Za-z_][A-Za-z0-9_]*$"
)
_QUALIFIED_NODE_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)
_SAFE_AST_BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "bytes",
        "complex",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "frozenset",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "object",
        "pow",
        "range",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
    }
)
_SAFE_EXTERNAL_IMPORT_PREFIXES = (
    "cmath",
    "decimal",
    "fractions",
    "functools",
    "itertools",
    "math",
    "numpy",
    "operator",
    "scipy",
    "statistics",
)
_FORBIDDEN_DYNAMIC_CALLS = frozenset(
    {
        "__import__",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "hasattr",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)
_COMMITTED_DATA_TARGETS = {
    "ADAPTER_ELIGIBILITY": (
        "committed_data:validation.literature_evidence_adapters."
        "ADAPTER_ELIGIBILITY"
    ),
    "ADAPTER_DEFINITIONS": (
        "committed_data:validation.literature_evidence_adapters."
        "ADAPTER_DEFINITIONS"
    ),
    "ORACLE_DEFINITIONS": (
        "committed_data:"
        "validation.literature_evidence_adapter_oracles."
        "ORACLE_DEFINITIONS"
    ),
}
_COMMITTED_DATA_EDGES = frozenset(_COMMITTED_DATA_TARGETS.values())
_COMMITTED_DATA_OWNERS = {
    (
        "validation.literature_evidence_adapters",
        "ADAPTER_ELIGIBILITY",
    ): _COMMITTED_DATA_TARGETS["ADAPTER_ELIGIBILITY"],
    (
        "validation.literature_evidence_adapters",
        "ADAPTER_DEFINITIONS",
    ): _COMMITTED_DATA_TARGETS["ADAPTER_DEFINITIONS"],
    (
        "validation.literature_evidence_adapter_oracles",
        "ORACLE_DEFINITIONS",
    ): _COMMITTED_DATA_TARGETS["ORACLE_DEFINITIONS"],
}
_BARE_COMMITTED_DATA_USERS = {
    (
        "validation.literature_evidence_isolation."
        "_run_isolated_recomputation_core",
        name,
    ): destination
    for name, destination in _COMMITTED_DATA_TARGETS.items()
}
_COMMITTED_DATA_ROOT = (
    "validation.literature_evidence_isolation."
    "_run_isolated_recomputation_core"
)
_EXPECTED_COMMITTED_DATA_EDGES = frozenset(
    (_COMMITTED_DATA_ROOT, destination)
    for destination in _COMMITTED_DATA_EDGES
)


@dataclass(frozen=True)
class _AstSourceNode:
    module_name: str
    relative_path: str
    raw_file_sha256: str
    node: ast.AST
    node_kind: str
    qualified_name: str
    bound_names: tuple[str, ...]
    source_span: bytes
    import_module: str | None = None


@dataclass(frozen=True)
class _ProjectSymbolImport:
    target_module: str
    target_symbol: str
    local_name: str


@dataclass(frozen=True)
class _ProjectModuleImport:
    target_module: str
    local_name: str


@dataclass
class _AstModuleIndex:
    module_name: str
    relative_path: str
    raw_bytes: bytes
    raw_file_sha256: str
    bindings: dict[str, object]


@dataclass(frozen=True)
class _ResolvedAstNode:
    source: _AstSourceNode
    dependencies: tuple[str, ...]


def _assert_no_symlink_components(path: Path, field_name: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    try:
        for component in absolute.parts[1:]:
            current /= component
            if current.is_symlink():
                raise _ContractError(
                    f"{field_name} cannot contain a symlink component"
                )
    except OSError as error:
        raise _ContractError(
            f"{field_name} cannot be inspected without following symlinks"
        ) from error


def _normalize_source_roots(source_roots: object) -> tuple[Path, ...]:
    if type(source_roots) is not tuple or not source_roots:
        raise _ContractError("source_roots must be a nonempty exact tuple")
    normalized = []
    for index, item in enumerate(source_roots):
        if not isinstance(item, (str, Path)):
            raise _ContractError(
                f"source_roots[{index}] must be a filesystem path"
            )
        supplied_root = Path(item)
        _assert_no_symlink_components(
            supplied_root, f"source_roots[{index}]"
        )
        try:
            root = supplied_root.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise _ContractError(
                f"source_roots[{index}] cannot be resolved"
            ) from error
        if not root.is_dir():
            raise _ContractError(
                f"source_roots[{index}] must resolve to a directory"
            )
        normalized.append(root)
    if len(set(normalized)) != len(normalized):
        raise _ContractError("source_roots contains a duplicate")
    return tuple(normalized)


def _validate_entry_symbol(value: object) -> tuple[str, str]:
    if type(value) is not str or _ENTRY_SYMBOL_PATTERN.fullmatch(value) is None:
        raise _ContractError(
            "entry_symbol must be an exact fully qualified module:function"
        )
    module_name, symbol_name = value.split(":", 1)
    return module_name, symbol_name


def _scientific_module_role(module_name: str) -> str | None:
    leaf = module_name.rsplit(".", 1)[-1]
    is_oracle = (
        "adapter_oracles" in leaf
        or leaf == "oracles"
        or leaf.endswith("_oracles")
    )
    if is_oracle:
        return "oracle"
    if leaf == "adapters" or leaf.endswith("_adapters"):
        return "adapter"
    return None


def _require_scientific_module_role(module_name: str, role: str) -> None:
    module_role = _scientific_module_role(module_name)
    if module_role is not None and module_role != role:
        raise _ContractError(
            f"{role} scientific closure cannot contain "
            f"{module_role}-module nodes"
        )


def _normalized_emitted_node(source_span: bytes) -> bytes:
    normalized = source_span.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return normalized.rstrip(b"\n") + b"\n"


def _node_source_span(raw_bytes: bytes, node: ast.AST) -> bytes:
    if not all(
        hasattr(node, attribute)
        for attribute in ("lineno", "col_offset", "end_lineno", "end_col_offset")
    ):
        raise _ContractError("AST node has no exact source span")
    lines = raw_bytes.splitlines(keepends=True)
    start_line = node.lineno - 1
    end_line = node.end_lineno - 1
    if (
        start_line < 0
        or end_line < start_line
        or end_line >= len(lines)
    ):
        raise _ContractError("AST node source span lies outside the raw file")
    line_offsets = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)
    start = line_offsets[start_line] + node.col_offset
    end = line_offsets[end_line] + node.end_col_offset
    if end <= start or end > len(raw_bytes):
        raise _ContractError("AST node has an empty or invalid source span")
    return raw_bytes[start:end]


def _resolve_relative_import(
    current_module: str,
    imported_module: str | None,
    level: int,
) -> str:
    if level == 0:
        if not imported_module:
            raise _ContractError("import has no resolvable module")
        return imported_module
    package_parts = current_module.split(".")[:-1]
    if level > len(package_parts):
        raise _ContractError("relative import escapes its source package")
    retained = package_parts[: len(package_parts) - level + 1]
    if imported_module:
        retained.extend(imported_module.split("."))
    if not retained:
        raise _ContractError("relative import has no resolvable module")
    return ".".join(retained)


class _AstClosureResolver:
    def __init__(
        self,
        source_roots: tuple[Path, ...],
        *,
        role: str,
    ) -> None:
        self.source_roots = source_roots
        self.role = role
        self.module_cache: dict[str, _AstModuleIndex] = {}
        self.resolved: dict[str, _ResolvedAstNode] = {}
        self.visiting: list[str] = []

    def _find_module_path(
        self, module_name: str, *, required: bool
    ) -> tuple[Path, Path] | None:
        relative_path = Path(*module_name.split(".")).with_suffix(".py")
        matches = []
        for root in self.source_roots:
            candidate = root / relative_path
            current = root
            for component in relative_path.parts:
                current /= component
                if current.is_symlink():
                    raise _ContractError(
                        f"source module {module_name} has a symlinked path"
                    )
            if candidate.is_file():
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                except (OSError, RuntimeError, ValueError) as error:
                    raise _ContractError(
                        f"source module {module_name} escapes its source root"
                    ) from error
                if candidate.is_symlink():
                    raise _ContractError(
                        f"source module {module_name} cannot be a symlink"
                    )
                matches.append((candidate, root))
        if len(matches) > 1:
            raise _ContractError(
                f"source module {module_name} is ambiguous across source_roots"
            )
        if not matches:
            if required:
                raise _ContractError(
                    f"source module {module_name} cannot be resolved"
                )
            return None
        return matches[0]

    def _is_project_module(self, module_name: str) -> bool:
        return self._find_module_path(module_name, required=False) is not None

    def _check_module_role(self, module_name: str) -> None:
        if self.role == "infrastructure":
            return
        _require_scientific_module_role(module_name, self.role)

    def _add_binding(
        self,
        bindings: dict[str, object],
        name: str,
        value: object,
        module_name: str,
    ) -> None:
        if name in bindings:
            raise _ContractError(
                f"source module {module_name} redefines global {name}"
            )
        bindings[name] = value

    def _source_node(
        self,
        *,
        module_name: str,
        relative_path: str,
        raw_bytes: bytes,
        raw_file_sha256: str,
        node: ast.AST,
        node_kind: str,
        qualified_name: str,
        bound_names: tuple[str, ...],
        import_module: str | None = None,
    ) -> _AstSourceNode:
        return _AstSourceNode(
            module_name=module_name,
            relative_path=relative_path,
            raw_file_sha256=raw_file_sha256,
            node=node,
            node_kind=node_kind,
            qualified_name=qualified_name,
            bound_names=bound_names,
            source_span=_node_source_span(raw_bytes, node),
            import_module=import_module,
        )

    def _index_import(
        self,
        module_name: str,
        relative_path: str,
        raw_bytes: bytes,
        raw_file_sha256: str,
        node: ast.Import | ast.ImportFrom,
        bindings: dict[str, object],
    ) -> None:
        if isinstance(node, ast.Import) and len(node.names) != 1:
            raise _ContractError(
                "multi-alias import cannot be statically emitted"
            )
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "*" for alias in node.names
        ):
            raise _ContractError("star import is forbidden in a closure source")
        if isinstance(node, ast.ImportFrom):
            target_module = _resolve_relative_import(
                module_name, node.module, node.level
            )
            if self._is_project_module(target_module):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    if local_name != alias.name:
                        raise _ContractError(
                            "project import alias cannot be statically emitted"
                        )
                    self._add_binding(
                        bindings,
                        local_name,
                        _ProjectSymbolImport(
                            target_module, alias.name, local_name
                        ),
                        module_name,
                    )
                return
            if len(node.names) != 1:
                raise _ContractError(
                    "multi-alias external ImportFrom cannot be "
                    "statically emitted"
                )
            local_names = tuple(
                alias.asname or alias.name for alias in node.names
            )
            qualified_name = (
                f"{module_name}.{local_names[0]}"
                if len(local_names) == 1
                else (
                    f"{module_name}.__import_{node.lineno}_"
                    f"{node.col_offset}"
                )
            )
            source_node = self._source_node(
                module_name=module_name,
                relative_path=relative_path,
                raw_bytes=raw_bytes,
                raw_file_sha256=raw_file_sha256,
                node=node,
                node_kind="import",
                qualified_name=qualified_name,
                bound_names=local_names,
                import_module=target_module,
            )
            for local_name in local_names:
                self._add_binding(
                    bindings, local_name, source_node, module_name
                )
            return
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", 1)[0]
            if self._is_project_module(alias.name):
                self._add_binding(
                    bindings,
                    local_name,
                    _ProjectModuleImport(alias.name, local_name),
                    module_name,
                )
                continue
            source_node = self._source_node(
                module_name=module_name,
                relative_path=relative_path,
                raw_bytes=raw_bytes,
                raw_file_sha256=raw_file_sha256,
                node=node,
                node_kind="import",
                qualified_name=f"{module_name}.{local_name}",
                bound_names=(local_name,),
                import_module=alias.name,
            )
            self._add_binding(
                bindings, local_name, source_node, module_name
            )

    def _load_module(self, module_name: str) -> _AstModuleIndex:
        if module_name in self.module_cache:
            return self.module_cache[module_name]
        self._check_module_role(module_name)
        located = self._find_module_path(module_name, required=True)
        if located is None:
            raise _ContractError(
                f"source module {module_name} cannot be resolved"
            )
        source_path, source_root = located
        try:
            raw_bytes = source_path.read_bytes()
            source = raw_bytes.decode("utf-8")
            tree = ast.parse(source, filename=str(source_path), mode="exec")
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as error:
            raise _ContractError(
                f"source module {module_name} cannot be parsed as UTF-8 Python"
            ) from error
        relative_path = source_path.relative_to(source_root).as_posix()
        raw_file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        bindings: dict[str, object] = {}
        for statement in tree.body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                self._index_import(
                    module_name,
                    relative_path,
                    raw_bytes,
                    raw_file_sha256,
                    statement,
                    bindings,
                )
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                source_node = self._source_node(
                    module_name=module_name,
                    relative_path=relative_path,
                    raw_bytes=raw_bytes,
                    raw_file_sha256=raw_file_sha256,
                    node=statement,
                    node_kind="function",
                    qualified_name=f"{module_name}.{statement.name}",
                    bound_names=(statement.name,),
                )
                self._add_binding(
                    bindings, statement.name, source_node, module_name
                )
                continue
            if isinstance(statement, ast.ClassDef):
                source_node = self._source_node(
                    module_name=module_name,
                    relative_path=relative_path,
                    raw_bytes=raw_bytes,
                    raw_file_sha256=raw_file_sha256,
                    node=statement,
                    node_kind="class",
                    qualified_name=f"{module_name}.{statement.name}",
                    bound_names=(statement.name,),
                )
                self._add_binding(
                    bindings, statement.name, source_node, module_name
                )
                continue
            assignment_name = None
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                assignment_name = statement.targets[0].id
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.value is not None
            ):
                assignment_name = statement.target.id
            if assignment_name is not None:
                source_node = self._source_node(
                    module_name=module_name,
                    relative_path=relative_path,
                    raw_bytes=raw_bytes,
                    raw_file_sha256=raw_file_sha256,
                    node=statement,
                    node_kind="immutable_constant",
                    qualified_name=f"{module_name}.{assignment_name}",
                    bound_names=(assignment_name,),
                )
                self._add_binding(
                    bindings, assignment_name, source_node, module_name
                )
                continue
            if (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and type(statement.value.value) is str
            ):
                continue
            if isinstance(statement, (ast.AugAssign, ast.Delete)):
                raise _ContractError(
                    f"source module {module_name} mutates module state"
                )
            raise _ContractError(
                f"source module {module_name} has unsupported top-level code"
            )
        indexed = _AstModuleIndex(
            module_name=module_name,
            relative_path=relative_path,
            raw_bytes=raw_bytes,
            raw_file_sha256=raw_file_sha256,
            bindings=bindings,
        )
        self.module_cache[module_name] = indexed
        return indexed

    def _validate_external_import(self, source: _AstSourceNode) -> None:
        module_name = source.import_module or ""
        if not any(
            module_name == prefix or module_name.startswith(prefix + ".")
            for prefix in _SAFE_EXTERNAL_IMPORT_PREFIXES
        ):
            raise _ContractError(
                f"external import {module_name} is not approved"
            )

    def _validate_no_dynamic_constructs(self, node: ast.AST) -> None:
        for candidate in ast.walk(node):
            if isinstance(
                candidate,
                (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
            ):
                raise _ContractError(
                    "comprehension scope cannot be statically emitted"
                )
            if candidate is not node and isinstance(
                candidate,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                raise _ContractError(
                    "runtime closure or nested definition is forbidden"
                )
            if isinstance(
                candidate,
                (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await),
            ):
                raise _ContractError(
                    "runtime closure or mutable runtime state is forbidden"
                )
            if isinstance(candidate, (ast.Import, ast.ImportFrom)):
                raise _ContractError("imports must be top-level and static")
            if isinstance(candidate, ast.Call):
                if (
                    isinstance(candidate.func, ast.Name)
                    and candidate.func.id in _FORBIDDEN_DYNAMIC_CALLS
                ):
                    raise _ContractError(
                        "dynamic resolution or source evaluation is forbidden"
                    )
                if isinstance(candidate.func, ast.Attribute) and (
                    candidate.func.attr
                    in {"import_module", "reload", "eval", "exec"}
                ):
                    raise _ContractError(
                        "dynamic resolution or source evaluation is forbidden"
                    )

    def _function_loaded_globals(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> set[str]:
        if isinstance(node, ast.AsyncFunctionDef):
            raise _ContractError("asynchronous scientific functions are forbidden")
        if node.decorator_list:
            raise _ContractError("function decorators are forbidden")
        self._validate_no_dynamic_constructs(node)
        local_names = {
            argument.arg
            for argument in (
                tuple(node.args.posonlyargs)
                + tuple(node.args.args)
                + tuple(node.args.kwonlyargs)
            )
        }
        if node.args.vararg is not None:
            local_names.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            local_names.add(node.args.kwarg.arg)
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Name) and isinstance(
                candidate.ctx, (ast.Store, ast.Del)
            ):
                local_names.add(candidate.id)
            if isinstance(candidate, ast.ExceptHandler) and candidate.name:
                local_names.add(candidate.name)
        return {
            candidate.id
            for candidate in ast.walk(node)
            if isinstance(candidate, ast.Name)
            and isinstance(candidate.ctx, ast.Load)
            and candidate.id not in local_names
        }

    def _validate_immutable_expression(self, value: ast.AST) -> None:
        allowed = (
            ast.BinOp,
            ast.BoolOp,
            ast.Compare,
            ast.Constant,
            ast.Expr,
            ast.IfExp,
            ast.Load,
            ast.Name,
            ast.Slice,
            ast.Subscript,
            ast.Tuple,
            ast.UnaryOp,
        )
        nodes = tuple(ast.walk(value))
        if len(nodes) > 256 or any(
            not isinstance(candidate, allowed + (ast.operator, ast.boolop, ast.cmpop, ast.unaryop))
            for candidate in nodes
        ):
            raise _ContractError(
                "mutable global or unsupported constant initializer"
            )
        for candidate in nodes:
            if isinstance(candidate, ast.Constant) and type(
                candidate.value
            ) not in (type(None), bool, int, float, complex, str, bytes):
                raise _ContractError("constant initializer is not immutable")

    def _constant_loaded_globals(self, source: _AstSourceNode) -> set[str]:
        node = source.node
        value = node.value
        self._validate_immutable_expression(value)
        return {
            candidate.id
            for candidate in ast.walk(value)
            if isinstance(candidate, ast.Name)
            and isinstance(candidate.ctx, ast.Load)
        }

    def _class_loaded_globals(self, node: ast.ClassDef) -> set[str]:
        if node.decorator_list or node.keywords:
            raise _ContractError(
                "decorated, keyword, or metaclass class is forbidden"
            )
        if len(node.bases) > 1 or (
            node.bases
            and not (
                isinstance(node.bases[0], ast.Name)
                and node.bases[0].id == "object"
            )
        ):
            raise _ContractError(
                "computed, nontrivial, or metaclass base is forbidden"
            )
        loaded = set()
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if statement.name in {
                    "__get__",
                    "__set__",
                    "__delete__",
                    "__init_subclass__",
                    "__set_name__",
                }:
                    raise _ContractError(
                        "descriptor or definition-time class hook is forbidden"
                    )
                loaded.update(self._function_loaded_globals(statement))
                continue
            if (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and type(statement.value.value) is str
            ) or isinstance(statement, ast.Pass):
                continue
            value = None
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                value = statement.value
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.value is not None
            ):
                value = statement.value
            if value is None:
                raise _ContractError("class contains unsupported descriptor state")
            self._validate_immutable_expression(value)
            loaded.update(
                candidate.id
                for candidate in ast.walk(value)
                if isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, ast.Load)
            )
        return loaded

    def _loaded_globals(self, source: _AstSourceNode) -> set[str]:
        if source.node_kind == "import":
            self._validate_external_import(source)
            return set()
        if source.node_kind == "immutable_constant":
            return self._constant_loaded_globals(source)
        if source.node_kind == "function":
            return self._function_loaded_globals(source.node)
        if source.node_kind == "class":
            return self._class_loaded_globals(source.node)
        raise _ContractError("AST source node has unknown kind")

    def _resolve_binding(
        self,
        module_name: str,
        global_name: str,
        *,
        source_qualified_name: str | None = None,
    ) -> str | None:
        module = self._load_module(module_name)
        try:
            binding = module.bindings[global_name]
        except KeyError as error:
            if global_name in _SAFE_AST_BUILTINS:
                return None
            committed_destination = _BARE_COMMITTED_DATA_USERS.get(
                (source_qualified_name, global_name)
            )
            if self.role == "infrastructure" and (
                committed_destination is not None
            ):
                return committed_destination
            raise _ContractError(
                f"unresolved global dependency {module_name}.{global_name}"
            ) from error
        if isinstance(binding, _ProjectSymbolImport):
            if binding.local_name != binding.target_symbol:
                raise _ContractError(
                    "project import alias cannot be statically resolved"
                )
            committed_destination = _COMMITTED_DATA_OWNERS.get(
                (binding.target_module, binding.target_symbol)
            )
            if self.role == "infrastructure" and (
                committed_destination is not None
            ):
                return committed_destination
            return self.resolve_symbol(binding.target_module, binding.target_symbol)
        if isinstance(binding, _ProjectModuleImport):
            raise _ContractError(
                "project module alias cannot be statically resolved"
            )
        if not isinstance(binding, _AstSourceNode):
            raise _ContractError("global dependency has an unknown binding")
        return self._resolve_node(binding)

    def _resolve_node(self, source: _AstSourceNode) -> str:
        qualified_name = source.qualified_name
        if qualified_name in self.resolved:
            return qualified_name
        if qualified_name in self.visiting:
            cycle = " -> ".join(self.visiting + [qualified_name])
            raise _ContractError(f"cyclic initializer or dependency: {cycle}")
        self._check_module_role(source.module_name)
        self.visiting.append(qualified_name)
        try:
            dependencies = []
            for global_name in sorted(self._loaded_globals(source)):
                resolved_name = self._resolve_binding(
                    source.module_name,
                    global_name,
                    source_qualified_name=source.qualified_name,
                )
                if resolved_name is not None:
                    dependencies.append(resolved_name)
            if len(set(dependencies)) != len(dependencies):
                raise _ContractError("AST node has duplicate dependency edges")
            self.resolved[qualified_name] = _ResolvedAstNode(
                source=source,
                dependencies=tuple(sorted(dependencies)),
            )
        finally:
            self.visiting.pop()
        return qualified_name

    def resolve_symbol(self, module_name: str, symbol_name: str) -> str:
        resolved = self._resolve_binding(module_name, symbol_name)
        if resolved is None or resolved.startswith("committed_data:"):
            raise _ContractError("entry/root symbol must resolve to source code")
        return resolved


def _topological_resolved_nodes(
    resolved: Mapping[str, _ResolvedAstNode],
) -> tuple[_ResolvedAstNode, ...]:
    pending = set(resolved)
    ordered = []
    priority = {
        "import": 0,
        "immutable_constant": 1,
        "class": 2,
        "function": 3,
    }
    while pending:
        ready = [
            resolved[name]
            for name in pending
            if not (
                set(resolved[name].dependencies) & pending
            )
        ]
        if not ready:
            raise _ContractError("closure dependency graph contains a cycle")
        ready.sort(
            key=lambda item: (
                priority[item.source.node_kind],
                item.source.qualified_name,
            )
        )
        for item in ready:
            ordered.append(item)
            pending.remove(item.source.qualified_name)
    return tuple(ordered)


def _assert_no_emitted_binding_collisions(
    resolved: Mapping[str, _ResolvedAstNode],
) -> None:
    emitted_bindings = {}
    for qualified_name, item in resolved.items():
        for bound_name in item.source.bound_names:
            previous = emitted_bindings.get(bound_name)
            if previous is not None and previous != qualified_name:
                raise _ContractError(
                    "cross-module emitted binding collision for "
                    f"{bound_name}"
                )
            emitted_bindings[bound_name] = qualified_name


def _manifest_from_resolved(
    resolved: Mapping[str, _ResolvedAstNode],
) -> tuple[tuple[_FrozenJsonObject, ...], tuple[tuple[str, str], ...], bytes]:
    ordered = _topological_resolved_nodes(resolved)
    manifests = []
    emitted_nodes = []
    all_edges = []
    for item in ordered:
        source = item.source
        emitted_node = _normalized_emitted_node(source.source_span)
        edges = tuple(
            (source.qualified_name, dependency)
            for dependency in item.dependencies
        )
        all_edges.extend(edges)
        manifests.append(
            _snapshot_json(
                {
                    "relative_path": source.relative_path,
                    "raw_file_sha256": source.raw_file_sha256,
                    "node_kind": source.node_kind,
                    "qualified_name": source.qualified_name,
                    "source_span_sha256": hashlib.sha256(
                        source.source_span
                    ).hexdigest(),
                    "emitted_node_sha256": hashlib.sha256(
                        emitted_node
                    ).hexdigest(),
                    "dependency_edges": edges,
                    "scanner_version": _AST_CLOSURE_VERSION,
                },
                "closure_node",
            )
        )
        emitted_nodes.append(emitted_node)
    emitted_source = b"\n".join(emitted_nodes)
    return tuple(manifests), tuple(all_edges), emitted_source


def _validate_ast_node_manifest(
    value: object, field_name: str
) -> _FrozenJsonObject:
    node = _exact_keys(value, _AST_NODE_FIELDS, field_name)
    relative_path = _require_text(
        node["relative_path"], f"{field_name}.relative_path"
    )
    parsed_path = PurePosixPath(relative_path)
    if (
        parsed_path.is_absolute()
        or ".." in parsed_path.parts
        or str(parsed_path) != relative_path
    ):
        raise _ContractError(
            f"{field_name}.relative_path must be normalized and relative"
        )
    _require_sha256(
        node["raw_file_sha256"], f"{field_name}.raw_file_sha256"
    )
    if node["node_kind"] not in _AST_NODE_KINDS:
        raise _ContractError(f"{field_name}.node_kind is not closed")
    qualified_name = _require_text(
        node["qualified_name"], f"{field_name}.qualified_name"
    )
    if _QUALIFIED_NODE_PATTERN.fullmatch(qualified_name) is None:
        raise _ContractError(
            f"{field_name}.qualified_name must be fully qualified"
        )
    _require_sha256(
        node["source_span_sha256"],
        f"{field_name}.source_span_sha256",
    )
    _require_sha256(
        node["emitted_node_sha256"],
        f"{field_name}.emitted_node_sha256",
    )
    edges = _require_edge_tuple(
        node["dependency_edges"], f"{field_name}.dependency_edges"
    )
    if any(source != qualified_name for source, _destination in edges):
        raise _ContractError(
            f"{field_name}.dependency_edges has a foreign source"
        )
    if node["scanner_version"] != _AST_CLOSURE_VERSION:
        raise _ContractError(f"{field_name}.scanner_version is unknown")
    return node


def _validate_manifest_graph(
    manifests: tuple[_FrozenJsonObject, ...],
    *,
    allow_committed_data: bool,
) -> None:
    by_name = {node["qualified_name"]: node for node in manifests}
    if len(by_name) != len(manifests):
        raise _ContractError("closure manifest contains duplicate nodes")
    raw_hash_by_path = {}
    all_edges = []
    for node in manifests:
        qualified_name = node["qualified_name"]
        module_name = qualified_name.rsplit(".", 1)[0]
        expected_path = module_name.replace(".", "/") + ".py"
        if node["relative_path"] != expected_path:
            raise _ContractError(
                "closure node path does not match its qualified module"
            )
        previous_raw_hash = raw_hash_by_path.setdefault(
            node["relative_path"], node["raw_file_sha256"]
        )
        if previous_raw_hash != node["raw_file_sha256"]:
            raise _ContractError(
                "closure nodes from one file disagree on raw file hash"
            )
        edges = node["dependency_edges"]
        if edges != tuple(sorted(edges)) or len(set(edges)) != len(edges):
            raise _ContractError(
                "closure node dependency edges are not canonical"
            )
        for _source, destination in edges:
            if destination in by_name:
                continue
            if (
                allow_committed_data
                and destination in _COMMITTED_DATA_EDGES
            ):
                continue
            raise _ContractError(
                "closure dependency edge has an uncommitted destination"
            )
        all_edges.extend(edges)
    if len(set(all_edges)) != len(all_edges):
        raise _ContractError("closure contains duplicate dependency edges")

    priority = {
        "import": 0,
        "immutable_constant": 1,
        "class": 2,
        "function": 3,
    }
    pending = set(by_name)
    expected_order = []
    while pending:
        ready = [
            by_name[name]
            for name in pending
            if not {
                destination
                for _source, destination in by_name[name][
                    "dependency_edges"
                ]
                if destination in by_name
            }
            & pending
        ]
        if not ready:
            raise _ContractError("closure manifest dependency graph is cyclic")
        ready.sort(
            key=lambda node: (
                priority[node["node_kind"]],
                node["qualified_name"],
            )
        )
        for node in ready:
            qualified_name = node["qualified_name"]
            expected_order.append(qualified_name)
            pending.remove(qualified_name)
    supplied_order = tuple(node["qualified_name"] for node in manifests)
    if supplied_order != tuple(expected_order):
        raise _ContractError("closure manifest node ordering is not canonical")


def _validate_exact_manifest_reachability(
    manifests: tuple[_FrozenJsonObject, ...],
    roots: tuple[str, ...],
    field_name: str,
) -> None:
    by_name = {node["qualified_name"]: node for node in manifests}
    reachable = set()
    pending = list(roots)
    while pending:
        qualified_name = pending.pop()
        if qualified_name in reachable:
            continue
        try:
            node = by_name[qualified_name]
        except KeyError as error:
            raise _ContractError(
                f"{field_name} is missing a reachability root"
            ) from error
        reachable.add(qualified_name)
        pending.extend(
            destination
            for _source, destination in node["dependency_edges"]
            if destination in by_name
        )
    if reachable != set(by_name):
        raise _ContractError(
            f"{field_name} contains a disconnected or unreachable node"
        )


def _validate_scientific_closure_record(
    value: object, *, expected_role: str | None = None
) -> ScientificClosure:
    if type(value) is not ScientificClosure:
        raise _ContractError("closure must be an exact ScientificClosure")
    closure = ScientificClosure(
        value.schema_version,
        value.role,
        value.entry_symbol,
        value.nodes,
        value.dependency_edges,
        value.emitted_source_sha256,
        value.bundle_sha256,
    )
    if expected_role is not None and closure.role != expected_role:
        raise _ContractError("scientific closure role mismatch")
    module_name, symbol_name = _validate_entry_symbol(closure.entry_symbol)
    manifests = tuple(
        _validate_ast_node_manifest(node, f"nodes[{index}]")
        for index, node in enumerate(closure.nodes)
    )
    qualified_names = tuple(
        node["qualified_name"] for node in manifests
    )
    if len(set(qualified_names)) != len(qualified_names):
        raise _ContractError("scientific closure has duplicate nodes")
    _validate_manifest_graph(manifests, allow_committed_data=False)
    entry_name = f"{module_name}.{symbol_name}"
    if entry_name not in qualified_names:
        raise _ContractError("scientific closure does not contain its entry")
    by_name = {node["qualified_name"]: node for node in manifests}
    if by_name[entry_name]["node_kind"] != "function":
        raise _ContractError("scientific closure entry must be a function")
    for node in manifests:
        node_module = node["qualified_name"].rsplit(".", 1)[0]
        _require_scientific_module_role(node_module, closure.role)
    _validate_exact_manifest_reachability(
        manifests, (entry_name,), "scientific closure"
    )
    flattened_edges = tuple(
        edge for node in manifests for edge in node["dependency_edges"]
    )
    if flattened_edges != closure.dependency_edges:
        raise _ContractError(
            "scientific closure node edges do not match closure edges"
        )
    expected_bundle_sha256 = _canonical_sha256(
        {
            "schema_version": closure.schema_version,
            "role": closure.role,
            "entry_symbol": closure.entry_symbol,
            "nodes": closure.nodes,
            "dependency_edges": closure.dependency_edges,
            "emitted_source_sha256": closure.emitted_source_sha256,
            "builder_version": _AST_CLOSURE_VERSION,
        }
    )
    if closure.bundle_sha256 != expected_bundle_sha256:
        raise _ContractError("scientific closure bundle hash mismatch")
    return closure


def _validate_infrastructure_closure_record(
    value: object,
) -> InfrastructureClosure:
    if type(value) is not InfrastructureClosure:
        raise _ContractError(
            "infrastructure_closure must be an exact InfrastructureClosure"
        )
    closure = InfrastructureClosure(
        value.schema_version,
        value.roots,
        value.nodes,
        value.dependency_edges,
        value.purpose_bindings,
        value.bundle_sha256,
    )
    manifests = tuple(
        _validate_ast_node_manifest(node, f"nodes[{index}]")
        for index, node in enumerate(closure.nodes)
    )
    qualified_names = tuple(
        node["qualified_name"] for node in manifests
    )
    if len(set(qualified_names)) != len(qualified_names):
        raise _ContractError("infrastructure closure has duplicate nodes")
    _validate_manifest_graph(manifests, allow_committed_data=True)
    flattened_edges = tuple(
        edge for node in manifests for edge in node["dependency_edges"]
    )
    if flattened_edges != closure.dependency_edges:
        raise _ContractError(
            "infrastructure node edges do not match closure edges"
        )
    if closure.roots != _EXPECTED_INFRASTRUCTURE_ROOTS:
        raise _ContractError("infrastructure closure root set mismatch")
    if _canonical_bytes(closure.purpose_bindings) != _canonical_bytes(
        _INFRASTRUCTURE_PURPOSE_BINDINGS
    ):
        raise _ContractError(
            "infrastructure closure purpose bindings mismatch"
        )
    if not set(closure.roots) <= set(qualified_names):
        raise _ContractError("infrastructure closure is missing a root node")
    by_name = {node["qualified_name"]: node for node in manifests}
    if any(by_name[root]["node_kind"] != "function" for root in closure.roots):
        raise _ContractError("every infrastructure root must be a function")
    _validate_exact_manifest_reachability(
        manifests, closure.roots, "infrastructure closure"
    )
    _reject_scientific_infrastructure_nodes(manifests)
    committed_edges = {
        (source, destination)
        for source, destination in closure.dependency_edges
        if destination.startswith("committed_data:")
    }
    if committed_edges != _EXPECTED_COMMITTED_DATA_EDGES:
        raise _ContractError(
            "infrastructure closure committed-data edge set mismatch"
        )
    expected_bundle_sha256 = _canonical_sha256(
        {
            "schema_version": closure.schema_version,
            "roots": closure.roots,
            "nodes": closure.nodes,
            "dependency_edges": closure.dependency_edges,
            "purpose_bindings": closure.purpose_bindings,
            "builder_version": _AST_CLOSURE_VERSION,
        }
    )
    if closure.bundle_sha256 != expected_bundle_sha256:
        raise _ContractError("infrastructure closure bundle hash mismatch")
    return closure


def build_scientific_closure(entry_symbol, *, role, source_roots):
    """Build one deterministic scientific AST closure without importing it."""

    normalized_role = _require_role(role)
    module_name, symbol_name = _validate_entry_symbol(entry_symbol)
    roots = _normalize_source_roots(source_roots)
    resolver = _AstClosureResolver(roots, role=normalized_role)
    resolved_entry = resolver.resolve_symbol(module_name, symbol_name)
    if resolved_entry != f"{module_name}.{symbol_name}":
        raise _ContractError("entry symbol cannot be an imported alias")
    if resolver.resolved[resolved_entry].source.node_kind != "function":
        raise _ContractError("scientific closure entry must be a function")
    _assert_no_emitted_binding_collisions(resolver.resolved)
    nodes, dependency_edges, emitted_source = _manifest_from_resolved(
        resolver.resolved
    )
    emitted_source_sha256 = hashlib.sha256(emitted_source).hexdigest()
    bundle_payload = {
        "schema_version": "scientific_closure_v1",
        "role": normalized_role,
        "entry_symbol": entry_symbol,
        "nodes": nodes,
        "dependency_edges": dependency_edges,
        "emitted_source_sha256": emitted_source_sha256,
        "builder_version": _AST_CLOSURE_VERSION,
    }
    closure = ScientificClosure(
        schema_version="scientific_closure_v1",
        role=normalized_role,
        entry_symbol=entry_symbol,
        nodes=nodes,
        dependency_edges=dependency_edges,
        emitted_source_sha256=emitted_source_sha256,
        bundle_sha256=_canonical_sha256(bundle_payload),
    )
    return _validate_scientific_closure_record(
        closure, expected_role=normalized_role
    )


def assert_disjoint_scientific_closures(
    adapter_closure, oracle_closure
):
    """Fail when adapter and oracle share a project scientific source node."""

    adapter = _validate_scientific_closure_record(
        adapter_closure, expected_role="adapter"
    )
    oracle = _validate_scientific_closure_record(
        oracle_closure, expected_role="oracle"
    )
    adapter_names = {
        node["qualified_name"] for node in adapter.nodes
    }
    oracle_names = {node["qualified_name"] for node in oracle.nodes}
    adapter_spans = {
        node["source_span_sha256"] for node in adapter.nodes
    }
    oracle_spans = {
        node["source_span_sha256"] for node in oracle.nodes
    }
    if adapter_names & oracle_names or adapter_spans & oracle_spans:
        raise _ContractError(
            "adapter and oracle scientific closures overlap or share a node"
        )


_INFRASTRUCTURE_MODULES = {
    "adapters": "validation.literature_evidence_adapters",
    "oracles": "validation.literature_evidence_adapter_oracles",
    "isolation": "validation.literature_evidence_isolation",
}
_INFRASTRUCTURE_PURPOSE_NAMES = {
    "canonical_transport": (
        "freeze_json",
        "thaw_json",
        "canonical_json_bytes",
        "canonical_sha256",
    ),
    "contract_validation": (
        "validate_adapter_definition",
        "validate_oracle_definition",
        "validate_scientific_inputs",
        "validate_numerical_controls",
        "validate_local_observable_result",
        "validate_authority_context",
        "make_worker_request",
        "validate_failure",
    ),
    "closure_and_policy_transport": (
        "build_scientific_closure",
        "build_scientific_policy_commitment",
        "build_infrastructure_closure",
        "scan_scientific_closure",
        "emit_scientific_capsule",
        "emit_fixed_worker",
        "assert_complete_dependency_partition",
    ),
    "runtime_resource_integrity": (
        "discover_runtime_resources",
        "build_runtime_snapshot",
        "revalidate_runtime_snapshot",
    ),
    "event_and_counterfactual_transport": (
        "record_and_freeze_hashes",
        "acquire_run_seed",
        "derive_counterfactual_points",
        "write_worker_request_exclusive",
    ),
    "capability_isolation_transport": (
        "run_capability_preflight",
        "create_run_directories",
        "construct_private_root",
        "run_namespace_supervisor",
        "launch_traced_tracee",
        "apply_tracee_security_policy",
        "validate_process_attestation",
    ),
    "trace_and_output_transport": (
        "evaluate_strace",
        "ingest_worker_output",
    ),
    "proof_adjudication_transport": (
        "collect_backend_diagnostics",
        "interpret_output_proofs",
        "derive_convergence_decision",
        "derive_oracle_decision",
    ),
    "coordinator_transport": (
        "validate_adapter_execution_evidence",
        "_run_isolated_recomputation_core",
        "run_isolated_recomputation",
    ),
}
_ADAPTER_INFRASTRUCTURE_NAMES = frozenset(
    {
        "freeze_json",
        "thaw_json",
        "canonical_json_bytes",
        "canonical_sha256",
        "validate_adapter_definition",
        "validate_scientific_inputs",
        "validate_numerical_controls",
        "validate_local_observable_result",
    }
)
_ORACLE_INFRASTRUCTURE_NAMES = frozenset({"validate_oracle_definition"})


def _infrastructure_module_for_root(root_name: str) -> str:
    if root_name in _ADAPTER_INFRASTRUCTURE_NAMES:
        return _INFRASTRUCTURE_MODULES["adapters"]
    if root_name in _ORACLE_INFRASTRUCTURE_NAMES:
        return _INFRASTRUCTURE_MODULES["oracles"]
    return _INFRASTRUCTURE_MODULES["isolation"]


_INFRASTRUCTURE_PURPOSE_BINDINGS = {
    f"{_infrastructure_module_for_root(root_name)}.{root_name}": purpose
    for purpose, root_names in _INFRASTRUCTURE_PURPOSE_NAMES.items()
    for root_name in root_names
}
_EXPECTED_INFRASTRUCTURE_ROOTS = tuple(
    sorted(_INFRASTRUCTURE_PURPOSE_BINDINGS)
)
_INFRASTRUCTURE_FORBIDDEN_HELPER_TOKENS = frozenset(
    {
        "answer",
        "coupling",
        "energy",
        "equation",
        "exchange",
        "formula",
        "hamiltonian",
        "magnetization",
        "model",
        "observable",
        "phase",
        "result",
        "scientific",
        "spectrum",
    }
)


def _lexical_tokens(value: str) -> set[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return {
        token.lower()
        for token in re.findall(
            r"[A-Za-z0-9]+", separated.replace("_", " ")
        )
    }


def _infrastructure_name_tokens(qualified_name: str) -> set[str]:
    leaf = qualified_name.rsplit(".", 1)[-1]
    return _lexical_tokens(leaf)


def _reject_scientific_infrastructure_nodes(
    nodes: tuple[_FrozenJsonObject, ...]
) -> None:
    expected = set(_EXPECTED_INFRASTRUCTURE_ROOTS)
    for node in nodes:
        qualified_name = node["qualified_name"]
        if qualified_name in expected:
            continue
        if _infrastructure_name_tokens(qualified_name) & (
            _INFRASTRUCTURE_FORBIDDEN_HELPER_TOKENS
        ):
            raise _ContractError(
                "infrastructure closure contains a scientific or result "
                "derivation helper"
            )


def _scan_infrastructure_ast_content(
    resolved: Mapping[str, _ResolvedAstNode],
) -> None:
    for item in resolved.values():
        tokens = set()
        for candidate in ast.walk(item.source.node):
            if isinstance(candidate, ast.BinOp):
                raise _ContractError(
                    "infrastructure closure contains a scientific equation"
                )
            if isinstance(candidate, (ast.Assign, ast.AnnAssign)):
                assigned_value = candidate.value
                if (
                    isinstance(assigned_value, ast.Constant)
                    and type(assigned_value.value) in (float, complex)
                ):
                    raise _ContractError(
                        "infrastructure closure contains a scientific constant"
                    )
            authored_value = None
            if isinstance(candidate, ast.Name):
                authored_value = candidate.id
            elif isinstance(candidate, ast.Attribute):
                authored_value = candidate.attr
            elif isinstance(candidate, ast.Constant) and isinstance(
                candidate.value, (str, bytes)
            ):
                if type(candidate.value) is bytes:
                    authored_value = candidate.value.decode(
                        "utf-8", errors="ignore"
                    )
                else:
                    authored_value = candidate.value
            if authored_value is not None:
                tokens.update(_lexical_tokens(authored_value))
        if tokens & _INFRASTRUCTURE_FORBIDDEN_HELPER_TOKENS:
            raise _ContractError(
                "infrastructure AST contains scientific or result content"
            )
        if (
            {"adapter", "definition"} <= tokens
            or {"oracle", "definition"} <= tokens
        ):
            raise _ContractError(
                "infrastructure AST contains a scientific definition"
            )
        if {"policy", "bytes"} <= tokens:
            raise _ContractError(
                "infrastructure AST contains scientific policy bytes"
            )


def build_infrastructure_closure(*, source_roots):
    """Build the exact planned transport/isolation dependency closure."""

    roots = _normalize_source_roots(source_roots)
    resolver = _AstClosureResolver(roots, role="infrastructure")
    for qualified_root in _EXPECTED_INFRASTRUCTURE_ROOTS:
        module_name, root_name = qualified_root.rsplit(".", 1)
        resolved_root = resolver.resolve_symbol(module_name, root_name)
        if resolved_root != qualified_root:
            raise _ContractError(
                f"infrastructure root {qualified_root} resolves by alias"
            )
        if resolver.resolved[resolved_root].source.node_kind != "function":
            raise _ContractError(
                f"infrastructure root {qualified_root} must be a function"
            )
    _scan_infrastructure_ast_content(resolver.resolved)
    nodes, dependency_edges, _emitted_source = _manifest_from_resolved(
        resolver.resolved
    )
    _reject_scientific_infrastructure_nodes(nodes)
    purpose_bindings = _snapshot_json(
        _INFRASTRUCTURE_PURPOSE_BINDINGS,
        "infrastructure purpose bindings",
    )
    bundle_payload = {
        "schema_version": "infrastructure_closure_v1",
        "roots": _EXPECTED_INFRASTRUCTURE_ROOTS,
        "nodes": nodes,
        "dependency_edges": dependency_edges,
        "purpose_bindings": purpose_bindings,
        "builder_version": _AST_CLOSURE_VERSION,
    }
    closure = InfrastructureClosure(
        schema_version="infrastructure_closure_v1",
        roots=_EXPECTED_INFRASTRUCTURE_ROOTS,
        nodes=nodes,
        dependency_edges=dependency_edges,
        purpose_bindings=purpose_bindings,
        bundle_sha256=_canonical_sha256(bundle_payload),
    )
    return _validate_infrastructure_closure_record(closure)


def _scan_policy_forbidden_structures(value: object, field_name: str) -> None:
    if type(value) is _FrozenJsonObject:
        for key, item in value._items:
            tokens = {
                token.lower()
                for token in re.findall(
                    r"[A-Za-z0-9]+", key.replace("_", " ")
                )
            }
            if tokens & {"fingerprint", "fingerprints", "lookup", "categorical"}:
                raise _ContractError(
                    f"{field_name} contains a forbidden policy structure"
                )
            if tokens & {"derivation", "expression", "formula"}:
                raise _ContractError(
                    f"{field_name} contains an arbitrary derivation expression"
                )
            if "branch" in tokens:
                raise _ContractError(
                    f"{field_name} contains a benchmark or adapter branch"
                )
            if {"adapter", "id", "branch"} <= tokens:
                raise _ContractError(
                    f"{field_name} contains an adapter-ID branch"
                )
            if {"proof", "kind"} <= tokens and (
                type(item) is not str
                or item not in _adapters.OUTPUT_PROOF_KINDS
            ):
                raise _ContractError(
                    f"{field_name} contains an unknown proof kind"
                )
            _scan_policy_forbidden_structures(
                item, f"{field_name}.{key}"
            )
        return
    if type(value) is tuple:
        for index, item in enumerate(value):
            _scan_policy_forbidden_structures(
                item, f"{field_name}[{index}]"
            )
        return
    if type(value) is str:
        normalized = value.strip().lower()
        categorical_answer_literals = frozenset(
            {
                "ordered_phase",
                "disordered_phase",
                "ferromagnetic_phase",
                "antiferromagnetic_phase",
                "topological_phase",
                "critical_phase",
            }
        )
        normalized_literal = re.sub(r"[\s-]+", "_", normalized)
        if normalized_literal in categorical_answer_literals:
            raise _ContractError(
                f"{field_name} contains a categorical answer literal"
            )
        if any(
            marker in normalized
            for marker in (
                "lambda ",
                "eval(",
                "exec(",
                "compile(",
                "__import__",
                "importlib.",
            )
        ):
            raise _ContractError(
                f"{field_name} contains an arbitrary expression"
            )


def _task5_policy_structure_scan_sha256(
    *,
    role: str,
    canonical_definition_sha256: str,
    entry_closure_sha256: str,
) -> str:
    return _canonical_sha256(
        {
            "schema_version": _POLICY_STRUCTURE_SCAN_VERSION,
            "role": role,
            "canonical_definition_sha256": canonical_definition_sha256,
            "entry_closure_sha256": entry_closure_sha256,
            "checks": {
                "canonical_definition_valid": True,
                "role_and_entry_bound": True,
                "proof_bindings_closed": True,
                "domain_policy_closed": True,
                "size_policy_closed": True,
                "convergence_policy_closed": True,
                "forbidden_structures_absent": True,
            },
        }
    )


def _validate_task5_policy_commitment(
    value: object,
    closure: ScientificClosure,
    *,
    expected_role: str,
) -> ScientificPolicyCommitment:
    if type(value) is not ScientificPolicyCommitment:
        raise _ContractError(
            f"{expected_role} policy must be an exact "
            "ScientificPolicyCommitment"
        )
    policy = ScientificPolicyCommitment(
        **{
            field.name: getattr(value, field.name)
            for field in fields(ScientificPolicyCommitment)
        }
    )
    if (
        policy.role != expected_role
        or policy.entry_closure_sha256 != closure.bundle_sha256
    ):
        raise _ContractError(
            f"{expected_role} policy does not bind its scientific closure"
        )
    expected_scan_sha256 = _task5_policy_structure_scan_sha256(
        role=expected_role,
        canonical_definition_sha256=policy.canonical_definition_sha256,
        entry_closure_sha256=closure.bundle_sha256,
    )
    if policy.static_scan_sha256 != expected_scan_sha256:
        raise _ContractError(
            f"{expected_role} policy has an invalid Task 5 structure scan"
        )
    return policy


def _definition_catalog_sha256(catalog: object, *, role: str) -> str:
    if type(catalog) is not MappingProxyType:
        raise _ContractError(
            f"{role} definition catalog must be an exact immutable mapping"
        )
    catalog_keys = tuple(catalog)
    for index, key in enumerate(catalog_keys):
        _identifier(key, f"{role} definition catalog key[{index}]")
    canonical_catalog = {}
    for key in sorted(catalog_keys):
        definition = catalog[key]
        if role == "adapter":
            validated = _validate_adapter_definition(definition)
            definition_id = validated.adapter_id
            payload = _adapters.adapter_definition_to_frozen_json(
                validated
            )
            round_tripped = (
                _adapters.adapter_definition_from_frozen_json(payload)
            )
            reencoded = _adapters.adapter_definition_to_frozen_json(
                round_tripped
            )
        else:
            validated = _oracles.validate_oracle_definition(definition)
            definition_id = validated.oracle_id
            payload = _oracles.oracle_definition_to_frozen_json(validated)
            round_tripped = (
                _oracles.oracle_definition_from_frozen_json(payload)
            )
            reencoded = _oracles.oracle_definition_to_frozen_json(
                round_tripped
            )
        if key != definition_id:
            raise _ContractError(
                f"{role} definition catalog key does not match definition ID"
            )
        if _canonical_bytes(payload) != _canonical_bytes(reencoded):
            raise _ContractError(
                f"{role} definition catalog has a noncanonical record"
            )
        canonical_catalog[key] = payload
    return _canonical_sha256(canonical_catalog)


def build_scientific_policy_commitment(definition, closure, *, role):
    """Bind a closed definition to its closure and Task 5 structural scan."""

    normalized_role = _require_role(role)
    validated_closure = _validate_scientific_closure_record(
        closure, expected_role=normalized_role
    )
    if normalized_role == "adapter":
        supplied = _validate_adapter_definition(definition)
        try:
            canonical_definition = _adapters.get_adapter_definition(
                supplied.adapter_id
            )
        except _ContractError as error:
            raise _ContractError(
                "adapter definition is absent from the canonical catalog"
            ) from error
        supplied_bytes = _canonical_bytes(
            _adapters.adapter_definition_to_frozen_json(supplied)
        )
        canonical_payload = (
            _adapters.adapter_definition_to_frozen_json(
                canonical_definition
            )
        )
        canonical_bytes = _canonical_bytes(canonical_payload)
        if supplied_bytes != canonical_bytes:
            raise _ContractError(
                "adapter definition does not match the canonical catalog"
            )
        definition_id = canonical_definition.adapter_id
        definition_entry = canonical_definition.entry_symbol
        (
            proof_bindings,
            domain_sha256,
            size_policy_sha256,
            convergence_sha256,
            eligibility_row_sha256,
            eligibility_catalog_sha256,
        ) = _adapter_policy_derivations(canonical_definition)
    else:
        canonical_definition = _oracles.validate_oracle_definition(definition)
        canonical_payload = _oracles.oracle_definition_to_frozen_json(
            canonical_definition
        )
        canonical_bytes = _canonical_bytes(canonical_payload)
        definition_id = canonical_definition.oracle_id
        definition_entry = canonical_definition.entry_symbol
        (
            proof_bindings,
            domain_sha256,
            size_policy_sha256,
            convergence_sha256,
        ) = _oracle_policy_derivations(canonical_definition)
        eligibility_row_sha256 = None
        eligibility_catalog_sha256 = None
    if validated_closure.entry_symbol != definition_entry:
        raise _ContractError(
            "definition entry_symbol does not match scientific closure entry"
        )
    _scan_policy_forbidden_structures(
        canonical_payload, "canonical_definition"
    )
    canonical_definition_sha256 = hashlib.sha256(
        canonical_bytes
    ).hexdigest()
    values = {
        "schema_version": "scientific_policy_commitment_v1",
        "role": normalized_role,
        "definition_id": definition_id,
        "canonical_definition_bytes": canonical_bytes,
        "canonical_definition_sha256": canonical_definition_sha256,
        "eligibility_row_sha256": eligibility_row_sha256,
        "eligibility_catalog_sha256": eligibility_catalog_sha256,
        "entry_closure_sha256": validated_closure.bundle_sha256,
        "output_or_invariant_proof_bindings": proof_bindings,
        "domain_sha256": domain_sha256,
        "size_policy_sha256": size_policy_sha256,
        "convergence_sha256": convergence_sha256,
        "static_scan_sha256": _task5_policy_structure_scan_sha256(
            role=normalized_role,
            canonical_definition_sha256=canonical_definition_sha256,
            entry_closure_sha256=validated_closure.bundle_sha256,
        ),
    }
    values["combined_sha256"] = scientific_policy_combined_sha256(values)
    return ScientificPolicyCommitment(**values)


def assert_complete_dependency_partition(
    adapter_closure,
    adapter_policy_commitment,
    oracle_closure,
    oracle_policy_commitment,
    infrastructure_closure,
    *,
    referenced_project_nodes,
):
    """Require every referenced project node to have one committed owner."""

    adapter = _validate_scientific_closure_record(
        adapter_closure, expected_role="adapter"
    )
    oracle = _validate_scientific_closure_record(
        oracle_closure, expected_role="oracle"
    )
    assert_disjoint_scientific_closures(adapter, oracle)
    adapter_policy = _validate_task5_policy_commitment(
        adapter_policy_commitment,
        adapter,
        expected_role="adapter",
    )
    oracle_policy = _validate_task5_policy_commitment(
        oracle_policy_commitment,
        oracle,
        expected_role="oracle",
    )
    infrastructure = _validate_infrastructure_closure_record(
        infrastructure_closure
    )
    adapter_definition_catalog_sha256 = _definition_catalog_sha256(
        _adapters.ADAPTER_DEFINITIONS, role="adapter"
    )
    oracle_definition_catalog_sha256 = _definition_catalog_sha256(
        _oracles.ORACLE_DEFINITIONS, role="oracle"
    )
    if type(referenced_project_nodes) is not tuple:
        raise _ContractError(
            "referenced_project_nodes must be an exact tuple"
        )
    referenced = tuple(
        _require_text(item, f"referenced_project_nodes[{index}]")
        for index, item in enumerate(referenced_project_nodes)
    )
    if len(set(referenced)) != len(referenced):
        raise _ContractError("referenced_project_nodes contains a duplicate")
    if referenced != tuple(sorted(referenced)):
        raise _ContractError(
            "referenced_project_nodes must use canonical ordering"
        )
    if any(
        any(marker in item for marker in ("*", "<dynamic>", "__import__"))
        for item in referenced
    ):
        raise _ContractError("dynamically resolved project node is forbidden")
    occurrences: dict[str, int] = {}
    for owned_closure in (adapter, oracle, infrastructure):
        for node in owned_closure.nodes:
            qualified_name = node["qualified_name"]
            occurrences[qualified_name] = occurrences.get(qualified_name, 0) + 1
    duplicates = {
        name for name, count in occurrences.items() if count != 1
    }
    if duplicates:
        raise _ContractError(
            "project source node is multiply classified in dependency partition"
        )
    if set(referenced) != set(occurrences):
        raise _ContractError(
            "dependency partition has a missing or extra project source node"
        )
    ordinary_nodes = set(occurrences)
    for owned_closure in (adapter, oracle, infrastructure):
        for source, destination in owned_closure.dependency_edges:
            if destination.startswith("committed_data:"):
                if (
                    owned_closure is not infrastructure
                    or destination not in _COMMITTED_DATA_EDGES
                ):
                    raise _ContractError(
                        "dependency partition contains an uncommitted data edge"
                    )
            elif destination not in ordinary_nodes:
                raise _ContractError(
                    "dependency partition edge resolves outside committed nodes"
                )
            if source not in ordinary_nodes:
                raise _ContractError(
                    "dependency partition edge has an unknown source"
                )
    commitment_payload = {
        "schema_version": "complete_dependency_partition_v1",
        "referenced_project_nodes": referenced,
        "adapter_closure_sha256": adapter.bundle_sha256,
        "adapter_policy_sha256": adapter_policy.combined_sha256,
        "oracle_closure_sha256": oracle.bundle_sha256,
        "oracle_policy_sha256": oracle_policy.combined_sha256,
        "infrastructure_closure_sha256": infrastructure.bundle_sha256,
        "committed_data": {
            _COMMITTED_DATA_TARGETS["ADAPTER_ELIGIBILITY"]: (
                adapter_policy.eligibility_catalog_sha256
            ),
            _COMMITTED_DATA_TARGETS["ADAPTER_DEFINITIONS"]: (
                adapter_definition_catalog_sha256
            ),
            _COMMITTED_DATA_TARGETS["ORACLE_DEFINITIONS"]: (
                oracle_definition_catalog_sha256
            ),
        },
    }
    return _canonical_sha256(commitment_payload)


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
