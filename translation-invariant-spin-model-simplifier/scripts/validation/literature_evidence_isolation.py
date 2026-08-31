"""Closed transport and evidence contracts for isolated recalculation.

This Task 4 module validates caller-authored data and projects answer-free
worker requests.  It performs no filesystem, registry, source-cache, network,
process, capsule, or scientific operation at import time or during validation.
"""

from __future__ import annotations

import ast
import builtins as _builtins
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, fields
import dis
from enum import Enum, IntFlag
import gc
import hashlib
import hmac
import importlib.metadata as _importlib_metadata
import json
import math
import os
import posixpath
from pathlib import Path, PurePath, PurePosixPath
import re
import shutil
import stat
import string
import subprocess
import sys
import sysconfig
import time
import weakref
from types import (
    BuiltinFunctionType,
    ClassMethodDescriptorType,
    CodeType,
    FunctionType,
    GetSetDescriptorType,
    MappingProxyType,
    MemberDescriptorType,
    MethodDescriptorType,
    MethodWrapperType,
    ModuleType,
    WrapperDescriptorType,
)
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
    "CounterfactualPoint",
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
    "write_worker_request_exclusive",
    "build_scientific_closure",
    "build_scientific_result_contract",
    "emit_scientific_capsule",
    "emit_fixed_worker",
    "emit_tracee_launcher",
    "build_scientific_policy_commitment",
    "build_infrastructure_closure",
    "scan_scientific_closure",
    "discover_runtime_resources",
    "build_runtime_snapshot",
    "revalidate_runtime_snapshot",
    "run_capability_preflight",
    "create_run_directories",
    "construct_private_root",
    "apply_tracee_security_policy",
    "run_namespace_supervisor",
    "launch_traced_tracee",
    "validate_process_attestation",
    "evaluate_strace",
    "ingest_worker_output",
    "collect_backend_diagnostics",
    "interpret_output_proofs",
    "derive_convergence_decision",
    "derive_oracle_decision",
    "record_and_freeze_hashes",
    "acquire_run_seed",
    "derive_counterfactual_points",
    "assert_disjoint_scientific_closures",
    "assert_complete_dependency_partition",
    "scientific_policy_combined_sha256",
    "validate_failure",
    "validate_adapter_execution_evidence",
    "run_isolated_recomputation",
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


_ORACLE_WORKER_REQUEST_TOKEN = object()


@_seal_contract
@dataclass(frozen=True, init=False)
class _OracleWorkerRequest:
    schema_version: str
    opaque_run_nonce: str
    adapter_id: str
    scientific_inputs: _FrozenJsonObject
    numerical_controls: _FrozenJsonObject
    capsule_sha256: str

    def __init__(
        self,
        *,
        schema_version,
        opaque_run_nonce,
        adapter_id,
        scientific_inputs,
        numerical_controls,
        capsule_sha256,
        authorization=None,
    ):
        if authorization is not _ORACLE_WORKER_REQUEST_TOKEN:
            raise _ContractError(
                "oracle worker request construction is unauthorized"
            )
        for name, value in (
            ("schema_version", schema_version),
            ("opaque_run_nonce", opaque_run_nonce),
            ("adapter_id", adapter_id),
            ("scientific_inputs", scientific_inputs),
            ("numerical_controls", numerical_controls),
            ("capsule_sha256", capsule_sha256),
        ):
            object.__setattr__(self, name, value)
        self.__post_init__()

    def __post_init__(self):
        if self.schema_version != _WORKER_REQUEST_SCHEMA_VERSION:
            raise _ContractError(
                "oracle worker request has an unknown schema_version"
            )
        nonce = _require_text(self.opaque_run_nonce, "opaque_run_nonce")
        if len(nonce.encode("utf-8")) > 256:
            raise _ContractError("opaque_run_nonce is too long")
        _identifier(self.adapter_id, "oracle_id")
        object.__setattr__(
            self,
            "scientific_inputs",
            _snapshot_json(self.scientific_inputs, "scientific_inputs"),
        )
        object.__setattr__(
            self,
            "numerical_controls",
            _snapshot_json(self.numerical_controls, "numerical_controls"),
        )
        _require_sha256(self.capsule_sha256, "capsule_sha256")

    def to_frozen_json(self):
        try:
            namespace = object.__getattribute__(self, "__dict__")
        except (AttributeError, TypeError) as error:
            raise _ContractError(
                "oracle worker request storage is unavailable"
            ) from error
        names = _record_field_names(_OracleWorkerRequest)
        if type(namespace) is not dict or set(namespace) != set(names):
            raise _ContractError("oracle worker request storage is not exact")
        return _snapshot_json(
            {name: namespace[name] for name in names},
            "oracle worker request",
        )


def _make_oracle_worker_request(
    definition,
    *,
    opaque_run_nonce,
    scientific_inputs,
    numerical_controls,
    capsule_sha256,
):
    validated = _oracles.validate_oracle_definition(definition)
    inputs = _snapshot_json(scientific_inputs, "oracle scientific inputs")
    _adapters._validate_value_against_schema(
        validated.input_schema, inputs, "oracle scientific inputs"
    )
    controls = _snapshot_json(
        numerical_controls, "oracle numerical controls"
    )
    return _OracleWorkerRequest(
        schema_version=_WORKER_REQUEST_SCHEMA_VERSION,
        opaque_run_nonce=opaque_run_nonce,
        adapter_id=validated.oracle_id,
        scientific_inputs=inputs,
        numerical_controls=controls,
        capsule_sha256=capsule_sha256,
        authorization=_ORACLE_WORKER_REQUEST_TOKEN,
    )


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


def write_worker_request_exclusive(request, *, directory):
    """Write one canonical answer-free request without replacement."""

    if type(request) is WorkerRequest:
        validated = WorkerRequest(
            **{
                field.name: getattr(request, field.name)
                for field in fields(WorkerRequest)
            }
        )
    elif type(request) is _OracleWorkerRequest:
        validated = request
    else:
        raise _ContractError("request must be an exact worker request")
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise _ContractError("request directory must be an absolute Path")
    payload = _canonical_bytes(validated.to_frozen_json())
    directory_fd = None
    request_fd = None
    try:
        directory_fd = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        directory_status = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_status.st_mode):
            raise _ContractError("request directory is not a directory")
        request_fd = os.open(
            "request.json",
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        offset = 0
        while offset < len(payload):
            written = os.write(request_fd, payload[offset:])
            if written <= 0:
                raise _ContractError("worker request write failed")
            offset += written
        os.fsync(request_fd)
    except _ContractError:
        raise
    except OSError as error:
        raise _ContractError(
            "worker request exclusive creation failed"
        ) from error
    finally:
        if request_fd is not None:
            os.close(request_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    return directory / "request.json"


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
_STATIC_SCANNER_VERSION = "scientific_static_scan_v3"
_STATIC_CONSTANT_EVALUATOR_VERSION = "bounded_constant_expression_v2"
_POLICY_STRUCTURE_SCAN_VERSION = "scientific_definition_policy_scan_v2"
_STATIC_SCAN_NODE_LIMIT = 16_384
_STATIC_SCAN_DEPTH_LIMIT = 256
_STATIC_SCAN_LITERAL_BYTES_LIMIT = 1_048_576
_STATIC_SCAN_SOURCE_FILE_BYTES_LIMIT = 16_777_216
_STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT = 1_048_576
_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT = 16_777_216
_STATIC_SCAN_FINGERPRINT_COUNT_LIMIT = 256
_STATIC_SCAN_LOOKUP_ENTRY_LIMIT = 256
_STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT = 65_536
_STATIC_SCAN_AGGREGATE_AST_DEPTH_LIMIT = 256
_STATIC_SCAN_INTEGER_BITS_LIMIT = 4_096
_STATIC_SCAN_FORMAT_WIDTH_LIMIT = 4_096
_STATIC_SCAN_CHECK_LIMIT = 64
_STATIC_SCAN_REASON_BYTES_LIMIT = 160
_STATIC_SCANNER_COMMITMENT_NODE_LIMIT = 131_072
_STATIC_SCANNER_COMMITMENT_EDGE_LIMIT = 262_144
_STATIC_SCANNER_COMMITMENT_ATTRIBUTE_LIMIT = 131_072
_STATIC_SCANNER_COMMITMENT_DEPTH_LIMIT = 512
_STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT = 16_777_216
_STATIC_SCANNER_COMMITMENT_INTEGER_BITS_LIMIT = 65_536
_STATIC_SCANNER_COMMITMENT_MATERIAL_BYTES_LIMIT = 33_554_432
_STATIC_SCAN_COMMON_CHECKS = frozenset(
    {
        "raw_ast_closed",
        "dependency_graph_closed",
        "imports_closed",
        "capabilities_closed",
        "literal_context_closed",
        "emitted_bytes_closed",
        "fingerprints_absent",
        "role_policy_closed",
    }
)
_STATIC_SCAN_INFRASTRUCTURE_CHECK = "infrastructure_purpose_closed"
_STATIC_SCANNER_SHA256 = _canonical_sha256(
    {
        "scanner_version": _STATIC_SCANNER_VERSION,
        "constant_evaluator_version": _STATIC_CONSTANT_EVALUATOR_VERSION,
        "ast_closure_version": _AST_CLOSURE_VERSION,
        "policy_structure_version": _POLICY_STRUCTURE_SCAN_VERSION,
        "limits": {
            "node_count": _STATIC_SCAN_NODE_LIMIT,
            "ast_depth": _STATIC_SCAN_DEPTH_LIMIT,
            "literal_bytes": _STATIC_SCAN_LITERAL_BYTES_LIMIT,
            "evaluated_output_bytes": (
                _STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT
            ),
            "aggregate_material_bytes": (
                _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT
            ),
            "fingerprint_count": _STATIC_SCAN_FINGERPRINT_COUNT_LIMIT,
            "lookup_entries": _STATIC_SCAN_LOOKUP_ENTRY_LIMIT,
            "aggregate_ast_nodes": _STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT,
            "aggregate_ast_depth": _STATIC_SCAN_AGGREGATE_AST_DEPTH_LIMIT,
            "integer_bits": _STATIC_SCAN_INTEGER_BITS_LIMIT,
            "format_width": _STATIC_SCAN_FORMAT_WIDTH_LIMIT,
            "check_count": _STATIC_SCAN_CHECK_LIMIT,
            "reason_bytes": _STATIC_SCAN_REASON_BYTES_LIMIT,
        },
    }
)
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
_CASE_BOUNDARY_PATTERN = re.compile(r"([a-z0-9])([A-Z])")
_ASCII_ALNUM_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
_LOWER_POLICY_TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9]*")
_NON_DECIMAL_DIGIT_PATTERN = re.compile(r"[^0-9]")
_WHITESPACE_OR_HYPHEN_PATTERN = re.compile(r"[\s-]+")
_DECIMAL_DIGIT_SEQUENCE_PATTERN = re.compile(r"[0-9]+")
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
_SAFE_AST_ANNOTATION_BUILTINS = frozenset(
    {
        "bool",
        "bytes",
        "complex",
        "dict",
        "float",
        "frozenset",
        "int",
        "list",
        "object",
        "set",
        "str",
        "tuple",
        "type",
    }
)
_AST_BINDING_RUNTIME = "runtime"
_AST_BINDING_IMMUTABLE = "immutable"
_AST_BINDING_ANNOTATION = "annotation"
_SAFE_EXTERNAL_IMPORT_PREFIXES = (
    "decimal",
    "math",
    "numpy",
    "scipy",
    "string",
)
_SAFE_EXTERNAL_IMPORT_MODULES = frozenset(
    {
        "decimal",
        "math",
        "numpy",
        "numpy.fft",
        "numpy.linalg",
        "numpy.polynomial",
        "numpy.typing",
        "scipy",
        "scipy.fft",
        "scipy.integrate",
        "scipy.interpolate",
        "scipy.linalg",
        "scipy.optimize",
        "scipy.signal",
        "scipy.sparse",
        "scipy.sparse.linalg",
        "scipy.spatial",
        "scipy.special",
        "scipy.stats",
        "string",
    }
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
    future_annotations: _AstSourceNode | None


@dataclass(frozen=True)
class _ResolvedAstNode:
    source: _AstSourceNode
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class _StaticScanNodeMaterial:
    qualified_name: str
    raw_source_span: bytes
    emitted_node: bytes


@dataclass(frozen=True)
class _StaticScanMaterial:
    closure_bundle_sha256: str
    nodes: tuple[_StaticScanNodeMaterial, ...]
    emitted_source: bytes
    emitted_source_sha256: str


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


_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES = (
    ("reports", "generate_literature_reproduction_audit_pdf"),
    ("validation", "fetch_literature_evidence_sources"),
    ("validation", "literature_benchmark_registry"),
    ("validation", "literature_evidence_comparators"),
    ("validation", "literature_evidence_inventory"),
    ("validation", "literature_evidence_parsers"),
    ("validation", "literature_evidence_record_loader"),
    ("validation", "literature_evidence_schema"),
    ("validation", "literature_evidence_sources"),
    ("validation", "literature_reproduction_audit"),
    ("validation", "literature_reproduction_manifest"),
    ("validation", "literature_reproduction_report"),
    ("validation", "literature_runtime_evidence"),
    ("validation", "literature_source_cache"),
    ("validation", "literature_source_index"),
    ("validation", "literature_source_provisioning"),
    ("validation", "literature_spin_model_benchmarks"),
    ("validation", "verify_literature_reproduction_manifest"),
)
_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS = (
    ("environment", "discovery"),
    ("environment", "helper"),
    ("environment", "helpers"),
    ("expected",),
    ("git",),
    ("previous", "output"),
    ("result",),
    ("target",),
    ("verdict",),
    ("workspace", "discovery"),
    ("workspace", "helper"),
    ("workspace", "helpers"),
)
_FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_CONTIGUOUS_PATTERNS = frozenset(
    {
        ("previous", "output"),
    }
)


def _forbidden_scientific_project_module_manifest(
) -> list[list[str]]:
    prefixes = _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES
    if (
        type(prefixes) is not tuple
        or prefixes != tuple(sorted(prefixes))
        or len(prefixes) != len(set(prefixes))
    ):
        raise _ContractError(
            "forbidden scientific project module policy is not canonical"
        )
    for prefix in prefixes:
        if (
            type(prefix) is not tuple
            or not prefix
            or any(
                type(component) is not str
                or not component
                or not component.isidentifier()
                for component in prefix
            )
        ):
            raise _ContractError(
                "forbidden scientific project module prefix is not exact"
            )
    for index, prefix in enumerate(prefixes):
        for other in prefixes[index + 1 :]:
            if other[: len(prefix)] == prefix:
                raise _ContractError(
                    "forbidden scientific project module prefix is "
                    "redundant"
                )
    return [list(prefix) for prefix in prefixes]


def _forbidden_scientific_project_module_token_manifest(
) -> list[dict[str, object]]:
    patterns = _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS
    contiguous = (
        _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_CONTIGUOUS_PATTERNS
    )
    if (
        type(patterns) is not tuple
        or patterns != tuple(sorted(patterns))
        or len(patterns) != len(set(patterns))
        or type(contiguous) is not frozenset
        or not contiguous <= set(patterns)
    ):
        raise _ContractError(
            "forbidden scientific project module token policy is not "
            "canonical"
        )
    for pattern in patterns:
        if (
            type(pattern) is not tuple
            or not pattern
            or len(pattern) > 2
            or len(pattern) != len(set(pattern))
            or any(
                type(token) is not str
                or not token
                or token != token.lower()
                or _LOWER_POLICY_TOKEN_PATTERN.fullmatch(token) is None
                for token in pattern
            )
        ):
            raise _ContractError(
                "forbidden scientific project module token pattern is "
                "not exact"
            )
    return [
        {
            "tokens": list(pattern),
            "match": (
                "contiguous_sequence"
                if pattern in contiguous
                else "same_leaf_tokens"
            ),
        }
        for pattern in patterns
    ]


def _case_preserving_module_component_tokens(
    component: str,
) -> tuple[str, ...]:
    separated = _CASE_BOUNDARY_PATTERN.sub(r"\1 \2", component)
    return tuple(
        _ASCII_ALNUM_TOKEN_PATTERN.findall(
            separated.replace("_", " ")
        )
    )


def _scientific_project_module_is_forbidden(module_name: str) -> bool:
    if type(module_name) is not str or not module_name:
        raise _ContractError(
            "scientific project module name must be exact"
        )
    components = tuple(module_name.split("."))
    if any(not component or not component.isidentifier() for component in components):
        raise _ContractError(
            "scientific project module components must be identifiers"
        )
    _forbidden_scientific_project_module_manifest()
    _forbidden_scientific_project_module_token_manifest()
    if any(
        components[: len(prefix)] == prefix
        for prefix in _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_PREFIXES
    ):
        return True
    for component in components:
        tokens = _case_preserving_module_component_tokens(component)
        token_set = set(tokens)
        for pattern in _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_TOKEN_PATTERNS:
            if pattern in (
                _FORBIDDEN_SCIENTIFIC_PROJECT_MODULE_CONTIGUOUS_PATTERNS
            ):
                if any(
                    tokens[index : index + len(pattern)] == pattern
                    for index in range(len(tokens) - len(pattern) + 1)
                ):
                    return True
            elif set(pattern) <= token_set:
                return True
    return False


def _require_scientific_project_module_allowed(module_name: str) -> None:
    if _scientific_project_module_is_forbidden(module_name):
        raise _ContractError(
            "scientific closure contains a forbidden project module family"
        )


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
    _require_scientific_project_module_allowed(module_name)
    module_role = _scientific_module_role(module_name)
    if module_role is not None and module_role != role:
        raise _ContractError(
            f"{role} scientific closure cannot contain "
            f"{module_role}-module nodes"
        )


def _normalized_emitted_node(source_span: bytes) -> bytes:
    if type(source_span) is not bytes:
        raise _ContractError(
            "static scan emitted normalization requires exact bytes"
        )
    projected_size = len(source_span) + (
        not source_span.endswith((b"\n", b"\r"))
    )
    if projected_size > _STATIC_SCAN_LITERAL_BYTES_LIMIT:
        raise _ContractError(
            "static scan emitted normalization exceeds the byte bound"
        )
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


def _bounded_read_python_source(
    source_root: Path,
    relative_path: Path,
    module_name: str,
) -> bytes:
    byte_limit = min(
        _STATIC_SCAN_SOURCE_FILE_BYTES_LIMIT,
        _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT,
    )
    if (
        not isinstance(source_root, Path)
        or not source_root.is_absolute()
        or not isinstance(relative_path, Path)
        or relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise _ContractError(
            f"source module {module_name} has an unsafe relative path"
        )
    try:
        directory_flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | os.O_CLOEXEC
        )
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    except AttributeError as error:
        raise _ContractError(
            f"source module {module_name} requires safe descriptor flags"
        ) from error
    directory_descriptor = None
    descriptor = None
    try:
        directory_descriptor = os.open(source_root.anchor, directory_flags)
        directory_components = (
            source_root.parts[1:] + relative_path.parts[:-1]
        )
        for component in directory_components:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        descriptor = os.open(
            relative_path.parts[-1],
            file_flags,
            dir_fd=directory_descriptor,
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise _ContractError(
                f"source module {module_name} is not a regular file"
            )
        if before.st_size < 0 or before.st_size > byte_limit:
            raise _ContractError(
                f"source module {module_name} exceeds the file byte bound"
            )
        chunks = []
        total = 0
        read_count = 0
        read_count_limit = (byte_limit + 65_535) // 65_536 + 1
        while True:
            read_count += 1
            if read_count > read_count_limit:
                raise _ContractError(
                    f"source module {module_name} exceeds the read bound"
                )
            remaining = byte_limit + 1 - total
            if remaining <= 0:
                raise _ContractError(
                    f"source module {module_name} exceeds the file byte bound"
                )
            chunk = os.read(descriptor, min(65_536, remaining))
            if type(chunk) is not bytes:
                raise _ContractError(
                    f"source module {module_name} returned an unsafe read"
                )
            if not chunk:
                break
            total += len(chunk)
            chunks.append(chunk)
        after = os.fstat(descriptor)
        before_signature = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mode,
            before.st_nlink,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_signature = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mode,
            after.st_nlink,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if (
            before_signature != after_signature
            or total != before.st_size
        ):
            raise _ContractError(
                f"source module {module_name} changed during bounded read"
            )
        raw_bytes = b"".join(chunks)
        os.lseek(descriptor, 0, os.SEEK_SET)
        verification_digest = hashlib.sha256()
        verification_total = 0
        verification_read_count = 0
        while True:
            verification_read_count += 1
            if verification_read_count > read_count_limit:
                raise _ContractError(
                    f"source module {module_name} exceeds the read bound"
                )
            remaining = byte_limit + 1 - verification_total
            if remaining <= 0:
                raise _ContractError(
                    f"source module {module_name} exceeds the file byte bound"
                )
            chunk = os.read(descriptor, min(65_536, remaining))
            if type(chunk) is not bytes:
                raise _ContractError(
                    f"source module {module_name} returned an unsafe read"
                )
            if not chunk:
                break
            verification_total += len(chunk)
            verification_digest.update(chunk)
        verified = os.fstat(descriptor)
        verified_signature = (
            verified.st_dev,
            verified.st_ino,
            verified.st_size,
            verified.st_mode,
            verified.st_nlink,
            verified.st_mtime_ns,
            verified.st_ctime_ns,
        )
        if (
            after_signature != verified_signature
            or verification_total != total
            or verification_digest.digest()
            != hashlib.sha256(raw_bytes).digest()
        ):
            raise _ContractError(
                f"source module {module_name} changed during bounded read"
            )
        return raw_bytes
    except _ContractError:
        raise
    except (OSError, TypeError, NotImplementedError) as error:
        raise _ContractError(
            f"source module {module_name} cannot be read safely"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory_descriptor is not None:
            os.close(directory_descriptor)


def _bounded_parse_utf8_python(
    raw_bytes: bytes,
    *,
    byte_limit: int,
    field_name: str,
    filename: str = "<static-scan>",
) -> ast.Module:
    if type(raw_bytes) is not bytes or len(raw_bytes) > byte_limit:
        raise _ContractError(f"{field_name} exceeds the byte bound")
    try:
        source = raw_bytes.decode("utf-8")
        return ast.parse(source, filename=filename, mode="exec")
    except (
        UnicodeDecodeError,
        SyntaxError,
        ValueError,
        RecursionError,
    ) as error:
        raise _ContractError(
            f"{field_name} cannot be parsed as bounded UTF-8 Python"
        ) from error


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
        self.external_import_usage: dict[str, set[str]] = {}
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
                self._check_module_role(target_module)
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
                self._check_module_role(alias.name)
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
            relative_source_path = source_path.relative_to(source_root)
            raw_bytes = _bounded_read_python_source(
                source_root, relative_source_path, module_name
            )
            tree = _bounded_parse_utf8_python(
                raw_bytes,
                byte_limit=min(
                    _STATIC_SCAN_SOURCE_FILE_BYTES_LIMIT,
                    _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT,
                ),
                field_name=f"source module {module_name}",
                filename=str(source_path),
            )
        except _ContractError:
            raise
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as error:
            raise _ContractError(
                f"source module {module_name} cannot be parsed as UTF-8 Python"
            ) from error
        relative_path = source_path.relative_to(source_root).as_posix()
        raw_file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        bindings: dict[str, object] = {}
        future_annotations = None
        for statement in tree.body:
            if (
                isinstance(statement, ast.ImportFrom)
                and statement.module == "__future__"
            ):
                if not (
                    statement.level == 0
                    and len(statement.names) == 1
                    and statement.names[0].name == "annotations"
                    and statement.names[0].asname is None
                    and future_annotations is None
                ):
                    raise _ContractError(
                        "only one exact future annotations import is supported"
                    )
                future_annotations = self._source_node(
                    module_name=module_name,
                    relative_path=relative_path,
                    raw_bytes=raw_bytes,
                    raw_file_sha256=raw_file_sha256,
                    node=statement,
                    node_kind="import",
                    qualified_name=(
                        f"{module_name}.__future_annotations__"
                    ),
                    bound_names=(),
                    import_module="__future__",
                )
                continue
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
        if "__future_annotations__" in bindings:
            raise _ContractError(
                f"source module {module_name} redefines reserved "
                "future binding"
            )
        indexed = _AstModuleIndex(
            module_name=module_name,
            relative_path=relative_path,
            raw_bytes=raw_bytes,
            raw_file_sha256=raw_file_sha256,
            bindings=bindings,
            future_annotations=future_annotations,
        )
        self.module_cache[module_name] = indexed
        return indexed

    def _validate_external_import(self, source: _AstSourceNode) -> None:
        module_name = source.import_module or ""
        if module_name == "__future__":
            if not (
                isinstance(source.node, ast.ImportFrom)
                and source.node.module == "__future__"
                and source.node.level == 0
                and len(source.node.names) == 1
                and source.node.names[0].name == "annotations"
                and source.node.names[0].asname is None
                and source.bound_names == ()
                and source.qualified_name.endswith(
                    ".__future_annotations__"
                )
            ):
                raise _ContractError(
                    "future import is not the approved annotations import"
                )
            return
        if module_name not in _SAFE_EXTERNAL_IMPORT_MODULES:
            raise _ContractError(
                f"external import {module_name} is not approved"
            )
        if isinstance(source.node, ast.ImportFrom):
            for alias in source.node.names:
                symbol_path = (
                    *module_name.split("."),
                    alias.name,
                )
                if _static_forbidden_capability_path(
                    tuple(part.lower() for part in symbol_path)
                ):
                    raise _ContractError(
                        "external import requests an unapproved file "
                        "capability"
                    )
                if not _static_safe_external_import_symbol(symbol_path):
                    raise _ContractError(
                        "external import requests an unapproved symbol"
                    )
        elif isinstance(source.node, ast.Import):
            for alias in source.node.names:
                if not _static_external_module_has_safe_descendant(
                    alias.name
                ):
                    raise _ContractError(
                        "external import module has no approved symbols"
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

    @staticmethod
    def _record_loaded_globals(
        loaded: dict[str, set[str]],
        names: Iterable[str],
        requirement: str,
    ) -> None:
        for name in names:
            loaded.setdefault(name, set()).add(requirement)

    def _function_loaded_globals(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        future_annotations: bool,
        prebinding_global_names: frozenset[str] = frozenset(),
    ) -> dict[str, set[str]]:
        if isinstance(node, ast.AsyncFunctionDef):
            raise _ContractError("asynchronous scientific functions are forbidden")
        if node.decorator_list:
            raise _ContractError("function decorators are forbidden")
        if getattr(node, "type_params", ()):
            raise _ContractError(
                "function type parameters are unsupported definition-time state"
            )
        self._validate_no_dynamic_constructs(node)
        arguments = (
            tuple(node.args.posonlyargs)
            + tuple(node.args.args)
            + tuple(node.args.kwonlyargs)
        )
        default_expressions = list(node.args.defaults)
        default_expressions.extend(
            default
            for default in node.args.kw_defaults
            if default is not None
        )
        annotation_expressions = [
            argument.annotation
            for argument in arguments
            if argument.annotation is not None
        ]
        for argument in (node.args.vararg, node.args.kwarg):
            if argument is not None and argument.annotation is not None:
                annotation_expressions.append(argument.annotation)
        if node.returns is not None:
            annotation_expressions.append(node.returns)
        loaded: dict[str, set[str]] = {}
        self._record_loaded_globals(
            loaded,
            self._immutable_expression_loaded_globals(
                *default_expressions
            ),
            _AST_BINDING_IMMUTABLE,
        )
        if not future_annotations:
            for annotation in annotation_expressions:
                self._validate_annotation_expression(annotation)
                self._record_loaded_globals(
                    loaded,
                    (
                        candidate.id
                        for candidate in ast.walk(annotation)
                        if isinstance(candidate, ast.Name)
                        and isinstance(candidate.ctx, ast.Load)
                    ),
                    _AST_BINDING_ANNOTATION,
                )
        local_names = {
            argument.arg
            for argument in arguments
        }
        if node.args.vararg is not None:
            local_names.add(node.args.vararg.arg)
        if node.args.kwarg is not None:
            local_names.add(node.args.kwarg.arg)
        statement_order_bound_names = set(local_names)
        loaded_before_local_binding = set()
        for statement in node.body:
            statement_nodes = tuple(ast.walk(statement))
            loaded_before_local_binding.update(
                candidate.id
                for candidate in statement_nodes
                if isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, ast.Load)
                and candidate.id not in statement_order_bound_names
            )
            statement_order_bound_names.update(
                candidate.id
                for candidate in statement_nodes
                if isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, (ast.Store, ast.Del))
            )
            statement_order_bound_names.update(
                candidate.name
                for candidate in statement_nodes
                if isinstance(candidate, ast.ExceptHandler)
                and candidate.name
            )
        body_nodes = tuple(
            candidate
            for statement in node.body
            for candidate in ast.walk(statement)
        )
        for candidate in body_nodes:
            if isinstance(candidate, ast.Name) and isinstance(
                candidate.ctx, (ast.Store, ast.Del)
            ):
                local_names.add(candidate.id)
            if isinstance(candidate, ast.ExceptHandler) and candidate.name:
                local_names.add(candidate.name)
        self._record_loaded_globals(
            loaded,
            (
                candidate.id
                for candidate in body_nodes
                if isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, ast.Load)
                and (
                    candidate.id not in local_names
                    or candidate.id
                    in (
                        loaded_before_local_binding
                        & prebinding_global_names
                    )
                )
            ),
            _AST_BINDING_RUNTIME,
        )
        return loaded

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

    def _immutable_expression_loaded_globals(
        self, *values: ast.AST
    ) -> set[str]:
        loaded = set()
        for value in values:
            self._validate_immutable_expression(value)
            loaded.update(
                candidate.id
                for candidate in ast.walk(value)
                if isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, ast.Load)
            )
        return loaded

    def _validate_annotation_expression(self, value: ast.AST) -> None:
        if not isinstance(value, (ast.Constant, ast.Name)):
            raise _ContractError(
                "unsupported annotation; expected a simple approved "
                "builtin type"
            )
        nodes = tuple(ast.walk(value))
        if any(
            not isinstance(candidate, (ast.Constant, ast.Load, ast.Name))
            for candidate in nodes
        ):
            raise _ContractError(
                "unsupported annotation; expected a simple approved "
                "builtin type"
            )
        if isinstance(value, ast.Constant) and type(value.value) not in (
            type(None),
            str,
        ):
            raise _ContractError(
                "unsupported annotation constant; expected a string or None"
            )

    def _constant_loaded_globals(
        self,
        source: _AstSourceNode,
        *,
        future_annotations: bool,
    ) -> dict[str, set[str]]:
        node = source.node
        loaded: dict[str, set[str]] = {}
        self._record_loaded_globals(
            loaded,
            self._immutable_expression_loaded_globals(node.value),
            _AST_BINDING_IMMUTABLE,
        )
        if isinstance(node, ast.AnnAssign) and not future_annotations:
            self._validate_annotation_expression(node.annotation)
            self._record_loaded_globals(
                loaded,
                (
                    candidate.id
                    for candidate in ast.walk(node.annotation)
                    if isinstance(candidate, ast.Name)
                    and isinstance(candidate.ctx, ast.Load)
                ),
                _AST_BINDING_ANNOTATION,
            )
        return loaded

    def _class_loaded_globals(
        self,
        node: ast.ClassDef,
        *,
        future_annotations: bool,
    ) -> dict[str, set[str]]:
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
        loaded: dict[str, set[str]] = {}
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if statement.name in {
                    "__get__",
                    "__set__",
                    "__delete__",
                    "__init_subclass__",
                    "__set_name__",
                    "__class_getitem__",
                }:
                    raise _ContractError(
                        "descriptor or definition-time class hook is forbidden"
                    )
                method_loaded = self._function_loaded_globals(
                    statement,
                    future_annotations=future_annotations,
                )
                for name, requirements in method_loaded.items():
                    loaded.setdefault(name, set()).update(requirements)
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
            self._record_loaded_globals(
                loaded,
                self._immutable_expression_loaded_globals(value),
                _AST_BINDING_IMMUTABLE,
            )
            if isinstance(statement, ast.AnnAssign) and not future_annotations:
                self._validate_annotation_expression(statement.annotation)
                self._record_loaded_globals(
                    loaded,
                    (
                        candidate.id
                        for candidate in ast.walk(statement.annotation)
                        if isinstance(candidate, ast.Name)
                        and isinstance(candidate.ctx, ast.Load)
                    ),
                    _AST_BINDING_ANNOTATION,
                )
        return loaded

    def _loaded_globals(
        self, source: _AstSourceNode
    ) -> dict[str, set[str]]:
        if source.node_kind == "import":
            self._validate_external_import(source)
            return {}
        module = self._load_module(source.module_name)
        future_annotations = module.future_annotations is not None
        if source.node_kind == "immutable_constant":
            return self._constant_loaded_globals(
                source,
                future_annotations=future_annotations,
            )
        if source.node_kind == "function":
            prebinding_global_names = frozenset(
                name
                for name, binding in module.bindings.items()
                if isinstance(binding, _AstSourceNode)
                and binding.node_kind == "import"
                and binding.import_module != "__future__"
            )
            return self._function_loaded_globals(
                source.node,
                future_annotations=future_annotations,
                prebinding_global_names=prebinding_global_names,
            )
        if source.node_kind == "class":
            return self._class_loaded_globals(
                source.node,
                future_annotations=future_annotations,
            )
        raise _ContractError("AST source node has unknown kind")

    def _resolve_binding(
        self,
        module_name: str,
        global_name: str,
        *,
        requirements: frozenset[str],
        source_qualified_name: str | None = None,
        explicit_project_export: bool = False,
        project_import_chain: tuple[tuple[str, str], ...] = (),
    ) -> str | None:
        if not requirements or not requirements <= {
            _AST_BINDING_RUNTIME,
            _AST_BINDING_IMMUTABLE,
            _AST_BINDING_ANNOTATION,
        }:
            raise _ContractError("global binding requirements are invalid")
        module = self._load_module(module_name)
        try:
            binding = module.bindings[global_name]
        except KeyError as error:
            if explicit_project_export:
                raise _ContractError(
                    "unresolved explicit project import "
                    f"{module_name}.{global_name}"
                ) from error
            if _AST_BINDING_IMMUTABLE in requirements:
                raise _ContractError(
                    "immutable initializer cannot use a runtime "
                    "builtin binding "
                    f"{global_name}"
                ) from error
            if _AST_BINDING_ANNOTATION in requirements:
                if global_name in _SAFE_AST_ANNOTATION_BUILTINS:
                    return None
                raise _ContractError(
                    "annotation is not an approved builtin type "
                    f"{global_name}"
                ) from error
            if (
                requirements == frozenset({_AST_BINDING_RUNTIME})
                and global_name in _SAFE_AST_BUILTINS
            ):
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
            target_binding = (
                binding.target_module,
                binding.target_symbol,
            )
            if target_binding in project_import_chain:
                cycle = " -> ".join(
                    f"{target_module}.{target_symbol}"
                    for target_module, target_symbol in (
                        project_import_chain + (target_binding,)
                    )
                )
                raise _ContractError(
                    f"cyclic project import binding: {cycle}"
                )
            committed_destination = _COMMITTED_DATA_OWNERS.get(
                target_binding
            )
            if (
                self.role == "infrastructure"
                and requirements
                == frozenset({_AST_BINDING_RUNTIME})
                and committed_destination is not None
            ):
                target_module = self._load_module(
                    binding.target_module
                )
                owner_binding = target_module.bindings.get(
                    binding.target_symbol
                )
                if (
                    isinstance(owner_binding, _AstSourceNode)
                    and owner_binding.node_kind == "immutable_constant"
                    and owner_binding.qualified_name
                    == (
                        f"{binding.target_module}."
                        f"{binding.target_symbol}"
                    )
                ):
                    return committed_destination
            return self._resolve_binding(
                binding.target_module,
                binding.target_symbol,
                requirements=requirements,
                source_qualified_name=source_qualified_name,
                explicit_project_export=True,
                project_import_chain=(
                    project_import_chain + (target_binding,)
                ),
            )
        if _AST_BINDING_ANNOTATION in requirements:
            raise _ContractError(
                "annotation cannot use a project binding; only "
                "approved builtin types are supported"
            )
        if _AST_BINDING_IMMUTABLE in requirements and not (
            isinstance(binding, _AstSourceNode)
            and binding.node_kind == "immutable_constant"
        ):
            raise _ContractError(
                "immutable initializer cannot use a runtime, callable, class, "
                "or import binding"
            )
        if isinstance(binding, _ProjectModuleImport):
            raise _ContractError(
                "project module alias cannot be statically resolved"
            )
        if not isinstance(binding, _AstSourceNode):
            raise _ContractError("global dependency has an unknown binding")
        if binding.node_kind == "import" and isinstance(
            binding.node, ast.ImportFrom
        ):
            self.external_import_usage.setdefault(
                binding.qualified_name, set()
            ).add(global_name)
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
            module = self._load_module(source.module_name)
            if (
                module.future_annotations is not None
                and module.future_annotations.qualified_name
                != qualified_name
            ):
                dependencies.append(
                    self._resolve_node(module.future_annotations)
                )
            for global_name, requirements in sorted(
                self._loaded_globals(source).items()
            ):
                resolved_name = self._resolve_binding(
                    source.module_name,
                    global_name,
                    requirements=frozenset(requirements),
                    source_qualified_name=source.qualified_name,
                )
                if resolved_name is not None:
                    if resolved_name in dependencies:
                        resolved_item = self.resolved.get(resolved_name)
                        if not (
                            resolved_item is not None
                            and isinstance(
                                resolved_item.source.node, ast.ImportFrom
                            )
                            and len(resolved_item.source.bound_names) > 1
                        ):
                            raise _ContractError(
                                "AST node has duplicate dependency edges"
                            )
                        continue
                    dependencies.append(resolved_name)
            self.resolved[qualified_name] = _ResolvedAstNode(
                source=source,
                dependencies=tuple(sorted(dependencies)),
            )
        finally:
            self.visiting.pop()
        return qualified_name

    def resolve_symbol(self, module_name: str, symbol_name: str) -> str:
        resolved = self._resolve_binding(
            module_name,
            symbol_name,
            requirements=frozenset({_AST_BINDING_RUNTIME}),
        )
        if resolved is None or resolved.startswith("committed_data:"):
            raise _ContractError("entry/root symbol must resolve to source code")
        return resolved

    def validate_future_annotation_modes(self) -> None:
        source_modules = {
            item.source.module_name for item in self.resolved.values()
        }
        modes = {
            self._load_module(module_name).future_annotations is not None
            for module_name in source_modules
        }
        if len(modes) > 1:
            raise _ContractError(
                "mixed future annotation semantics cannot be preserved in one "
                "emitted capsule"
            )

    def validate_external_import_usage(self) -> None:
        for qualified_name, item in self.resolved.items():
            source = item.source
            if not isinstance(source.node, ast.ImportFrom):
                continue
            used_names = self.external_import_usage.get(
                qualified_name, set()
            )
            expected_names = set(source.bound_names)
            if used_names != expected_names:
                missing_names = sorted(expected_names - used_names)
                raise _ContractError(
                    "external import-from statement has unused bound name "
                    f"{missing_names[0]}"
                )


def _ast_node_ordering_key(
    node_kind: str, qualified_name: str
) -> tuple[int, str]:
    if (
        node_kind == "import"
        and qualified_name.endswith(".__future_annotations__")
    ):
        return (-1, qualified_name)
    priority = {
        "import": 0,
        "immutable_constant": 1,
        "class": 2,
        "function": 3,
    }
    return (priority[node_kind], qualified_name)


def _topological_resolved_nodes(
    resolved: Mapping[str, _ResolvedAstNode],
) -> tuple[_ResolvedAstNode, ...]:
    pending = set(resolved)
    ordered = []
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
            key=lambda item: _ast_node_ordering_key(
                item.source.node_kind,
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


def _preflight_static_material_totals(
    raw_bytes: int,
    emitted_bytes: int,
) -> None:
    if (
        raw_bytes > _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT
        or emitted_bytes > _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT
    ):
        raise _ContractError(
            "static scan aggregate raw or emitted material exceeds the "
            "byte bound"
        )


def _manifest_from_resolved(
    resolved: Mapping[str, _ResolvedAstNode],
) -> tuple[tuple[_FrozenJsonObject, ...], tuple[tuple[str, str], ...], bytes]:
    ordered = _topological_resolved_nodes(resolved)
    manifests = []
    emitted_nodes = []
    all_edges = []
    raw_bytes = 0
    emitted_bytes = 0
    for item in ordered:
        source = item.source
        if len(source.source_span) > _STATIC_SCAN_LITERAL_BYTES_LIMIT:
            raise _ContractError(
                "static scan raw source span exceeds the byte bound"
            )
        raw_bytes += len(source.source_span)
        _preflight_static_material_totals(raw_bytes, emitted_bytes)
        emitted_node = _normalized_emitted_node(source.source_span)
        if len(emitted_node) > _STATIC_SCAN_LITERAL_BYTES_LIMIT:
            raise _ContractError(
                "static scan emitted node exceeds the byte bound"
            )
        emitted_bytes += len(emitted_node) + bool(emitted_nodes)
        _preflight_static_material_totals(raw_bytes, emitted_bytes)
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


def _static_scan_material_from_resolved(
    resolved: Mapping[str, _ResolvedAstNode],
    *,
    closure_bundle_sha256: str,
) -> _StaticScanMaterial:
    ordered = _topological_resolved_nodes(resolved)
    nodes = []
    raw_bytes = 0
    emitted_bytes = 0
    for item in ordered:
        node = _StaticScanNodeMaterial(
            qualified_name=item.source.qualified_name,
            raw_source_span=bytes(item.source.source_span),
            emitted_node=_normalized_emitted_node(
                item.source.source_span
            ),
        )
        raw_bytes += len(node.raw_source_span)
        emitted_bytes += len(node.emitted_node) + bool(nodes)
        _preflight_static_material_totals(raw_bytes, emitted_bytes)
        nodes.append(node)
    nodes = tuple(nodes)
    emitted_source = b"\n".join(
        item.emitted_node for item in nodes
    )
    return _StaticScanMaterial(
        closure_bundle_sha256=closure_bundle_sha256,
        nodes=nodes,
        emitted_source=emitted_source,
        emitted_source_sha256=hashlib.sha256(
            emitted_source
        ).hexdigest(),
    )


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
    scientific_role: str | None = None,
) -> None:
    by_name = {node["qualified_name"]: node for node in manifests}
    if len(by_name) != len(manifests):
        raise _ContractError("closure manifest contains duplicate nodes")
    raw_hash_by_path = {}
    all_edges = []
    for node in manifests:
        qualified_name = node["qualified_name"]
        module_name = qualified_name.rsplit(".", 1)[0]
        if scientific_role is not None:
            _require_scientific_module_role(
                module_name, scientific_role
            )
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
            key=lambda node: _ast_node_ordering_key(
                node["node_kind"],
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
    _validate_manifest_graph(
        manifests,
        allow_committed_data=False,
        scientific_role=closure.role,
    )
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
    resolver.validate_future_annotation_modes()
    resolver.validate_external_import_usage()
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
    validated = _validate_scientific_closure_record(
        closure, expected_role=normalized_role
    )
    material = _static_scan_material_from_resolved(
        resolver.resolved,
        closure_bundle_sha256=validated.bundle_sha256,
    )
    object.__setattr__(validated, "_static_scan_material", material)
    return validated


def build_scientific_result_contract(definition, runtime_snapshot):
    """Bind answer-free result metadata to one retained runtime snapshot."""

    canonical_definition = _validate_adapter_definition(definition)
    if type(runtime_snapshot) is not RuntimeSnapshot:
        raise _ContractError("scientific result contract requires a runtime snapshot")
    manifest = _validated_runtime_manifest(runtime_snapshot.manifest)
    interpreter_rows = tuple(
        row for row in manifest.resources if row["purpose"] == "interpreter"
    )
    if len(interpreter_rows) != 1:
        raise _ContractError("runtime snapshot requires one interpreter")
    interpreter = interpreter_rows[0]
    package_identities = {}
    for name in canonical_definition.runtime_requirements.packages:
        rows = tuple(
            row
            for row in manifest.resources
            if row["purpose"] == "declared_distribution_file"
            and row["distribution"] == name
        )
        if not rows:
            raise _ContractError("runtime snapshot lacks a declared package")
        versions = {row["version"] for row in rows}
        if len(versions) != 1:
            raise _ContractError("runtime package versions are inconsistent")
        package_identities[name] = {
            "version": next(iter(versions)),
            "binary_sha256": _canonical_sha256(
                tuple(sorted(row["sha256"] for row in rows))
            ),
        }
    native_rows = tuple(
        row
        for row in manifest.resources
        if row["purpose"] == "declared_native_library"
    )
    native_identities = {}
    if len(native_rows) != len(
        canonical_definition.runtime_requirements.native_libraries
    ):
        raise _ContractError("runtime snapshot native-library set is incomplete")
    for name, row in zip(
        canonical_definition.runtime_requirements.native_libraries,
        native_rows,
    ):
        native_identities[name] = {
            "version": "manifest-sha256-v1",
            "binary_sha256": row["sha256"],
        }
    diagnostics = {
        "backend_kind": canonical_definition.backend_kind,
        "interpreter_implementation": sys.implementation.name,
        "interpreter_version": sys.version.split()[0],
        "interpreter_binary_sha256": interpreter["sha256"],
        "packages": package_identities,
        "native_libraries": native_identities,
        "numerical_backend": {
            "name": "not_applicable",
            "version": None,
            "binary_sha256": None,
            "applicability": "not_applicable",
        },
        "backend_resources": {
            name: {"applicability": "used"}
            for name in canonical_definition.runtime_requirements.backend_resources
        },
    }
    body = {
        "schema_version": "scientific_result_contract_v1",
        "adapter_id": canonical_definition.adapter_id,
        "entry_symbol": canonical_definition.entry_symbol,
        "observable_identity": _adapters.thaw_json(
            canonical_definition.observable_identity
        ),
        "units": {
            selector: binding.value_schema.units
            for selector, binding in canonical_definition.output_schema
        },
        "backend_diagnostics": diagnostics,
    }
    body["contract_sha256"] = _canonical_sha256(body)
    return _snapshot_json(body, "scientific result contract")


def emit_scientific_capsule(closure, *, result_contract=None):
    """Emit one role-bound capsule from builder-retained source material."""

    validated = _validate_scientific_closure_record(closure)
    try:
        storage = object.__getattribute__(closure, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(
            "scientific capsule closure storage is unavailable"
        ) from error
    material = storage.get("_static_scan_material")
    if type(material) is not _StaticScanMaterial:
        raise _ContractError(
            "scientific capsule requires builder-retained source material"
        )
    if (
        material.closure_bundle_sha256 != validated.bundle_sha256
        or material.emitted_source_sha256
        != validated.emitted_source_sha256
        or hashlib.sha256(material.emitted_source).hexdigest()
        != validated.emitted_source_sha256
    ):
        raise _ContractError("scientific capsule source material mismatch")
    _module_name, entry_name = _validate_entry_symbol(
        validated.entry_symbol
    )
    reserved = {
        "__literature_capsule_schema__",
        "__literature_capsule_role__",
        "__literature_result_contract__",
        "__literature_scientific_calculate__",
        "__literature_scientific_entry__",
    }
    if any(
        node["qualified_name"].rsplit(".", 1)[1] in reserved
        for node in validated.nodes
    ):
        raise _ContractError("scientific capsule has a reserved binding")
    if result_contract is None:
        contract_source = "None"
    else:
        contract = _exact_keys(
            result_contract,
            (
                "schema_version",
                "adapter_id",
                "entry_symbol",
                "observable_identity",
                "units",
                "backend_diagnostics",
                "contract_sha256",
            ),
            "scientific result contract",
        )
        contract_body = {
            key: contract[key]
            for key in contract
            if key != "contract_sha256"
        }
        if (
            validated.role != "adapter"
            or contract["schema_version"] != "scientific_result_contract_v1"
            or contract["entry_symbol"] != validated.entry_symbol
            or contract["contract_sha256"] != _canonical_sha256(contract_body)
        ):
            raise _ContractError("scientific result contract is not bound")
        contract_source = repr(_adapters.thaw_json(contract))
    trailer = (
        "\n\n__literature_capsule_schema__ = "
        '"scientific_capsule_v1"\n'
        "__literature_capsule_role__ = "
        + json.dumps(validated.role)
        + "\n__literature_result_contract__ = "
        + contract_source
        + "\n__literature_scientific_calculate__ = "
        + entry_name
        + "\n\ndef __literature_scientific_entry__(scientific_inputs, "
        "numerical_controls):\n"
        "    calculation = __literature_scientific_calculate__(\n"
        "        scientific_inputs, numerical_controls\n"
        "    )\n"
        "    contract = __literature_result_contract__\n"
        "    if contract is None or calculation.get('schema_version') != "
        "'scientific_calculation_v1':\n"
        "        return calculation\n"
        "    convergence = dict(calculation['raw_convergence_evidence'])\n"
        "    convergence['certificate'] = {\n"
        "        'kind': convergence['kind'] + '_certificate',\n"
        "        'proof_inputs': calculation.get('proof_inputs', {}),\n"
        "        'certificate_sha256': contract['contract_sha256'],\n"
        "    }\n"
        "    return {\n"
        "        'schema_version': 'scientific_result_body_v1',\n"
        "        'observable_identity': contract['observable_identity'],\n"
        "        'fields': calculation['fields'],\n"
        "        'units': contract['units'],\n"
        "        'uncertainty': calculation['uncertainty'],\n"
        "        'raw_convergence_evidence': convergence,\n"
        "        'backend_diagnostics': contract['backend_diagnostics'],\n"
        "        'operation_counts_or_sizes': "
        "calculation['operation_counts_or_sizes'],\n"
        "    }\n"
        + "\n"
    ).encode("utf-8")
    return material.emitted_source + trailer


def emit_fixed_worker():
    """Return the fixed, caller-independent worker program bytes."""

    source = '''import json
import os
import stat

_REQUEST_PATH = "/input/request.json"
_CAPSULE_PATH = "/adapter/scientific_capsule.py"
_RESULT_PATH = "/output/result.json"
_INPUT_LIMIT = 1048576
_CAPSULE_LIMIT = 16777216
_RESULT_LIMIT = 16777216
_SHA256_INITIAL = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)
_SHA256_ROUND = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)


def _rotate_right(value, count):
    return ((value >> count) | (value << (32 - count))) & 0xFFFFFFFF


def _sha256(payload):
    length = len(payload)
    padded = payload + b"\\x80"
    padded += b"\\x00" * ((55 - length) % 64)
    padded += (length * 8).to_bytes(8, "big")
    state = list(_SHA256_INITIAL)
    for offset in range(0, len(padded), 64):
        block = padded[offset:offset + 64]
        words = [
            int.from_bytes(block[index:index + 4], "big")
            for index in range(0, 64, 4)
        ]
        for index in range(16, 64):
            left = words[index - 15]
            right = words[index - 2]
            sigma0 = (
                _rotate_right(left, 7)
                ^ _rotate_right(left, 18)
                ^ (left >> 3)
            )
            sigma1 = (
                _rotate_right(right, 17)
                ^ _rotate_right(right, 19)
                ^ (right >> 10)
            )
            words.append(
                (words[index - 16] + sigma0 + words[index - 7] + sigma1)
                & 0xFFFFFFFF
            )
        working = list(state)
        for index in range(64):
            a, b, c, d, e, f, g, h = working
            sum1 = (
                _rotate_right(e, 6)
                ^ _rotate_right(e, 11)
                ^ _rotate_right(e, 25)
            )
            choose = (e & f) ^ ((~e) & g)
            temporary1 = (
                h + sum1 + choose + _SHA256_ROUND[index] + words[index]
            ) & 0xFFFFFFFF
            sum0 = (
                _rotate_right(a, 2)
                ^ _rotate_right(a, 13)
                ^ _rotate_right(a, 22)
            )
            majority = (a & b) ^ (a & c) ^ (b & c)
            temporary2 = (sum0 + majority) & 0xFFFFFFFF
            working = [
                (temporary1 + temporary2) & 0xFFFFFFFF,
                a, b, c, (d + temporary1) & 0xFFFFFFFF, e, f, g,
            ]
        state = [
            (current + addition) & 0xFFFFFFFF
            for current, addition in zip(state, working)
        ]
    return b"".join(value.to_bytes(4, "big") for value in state)


def _canonical_json_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _read_stable_regular(path, limit):
    descriptor = os.open(
        path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > limit
        ):
            raise RuntimeError("worker input is not a bounded regular file")
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1048576))
            if not chunk:
                raise RuntimeError("worker input ended early")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise RuntimeError("worker input grew while reading")
        after = os.fstat(descriptor)
        identity = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_nlink,
            item.st_size,
            item.st_mode,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        if identity(before) != identity(after):
            raise RuntimeError("worker input changed while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _require_json_value(value, depth=0):
    if depth > 128:
        raise RuntimeError("worker result exceeds the JSON depth bound")
    if value is None or type(value) in (bool, str):
        return
    if type(value) is int:
        if value.bit_length() > 4096:
            raise RuntimeError("worker result integer is oversized")
        return
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise RuntimeError("worker result contains a nonfinite number")
        return
    if type(value) is list:
        for item in value:
            _require_json_value(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise RuntimeError("worker result key is not text")
            _require_json_value(item, depth + 1)
        return
    raise RuntimeError("worker result contains a non-JSON value")


def _parse_request(request_bytes):
    try:
        request_text = request_bytes.decode("utf-8")
        request = json.loads(
            request_text,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(token)
            ),
        )
    except (UnicodeDecodeError, ValueError, TypeError) as error:
        raise RuntimeError("worker request is malformed") from error
    if type(request) is not dict or set(request) != {
        "schema_version",
        "opaque_run_nonce",
        "adapter_id",
        "scientific_inputs",
        "numerical_controls",
        "capsule_sha256",
    }:
        raise RuntimeError("worker request has non-closed fields")
    if _canonical_json_bytes(request) != request_bytes:
        raise RuntimeError("worker request is not canonical JSON")
    if request["schema_version"] != "worker_request_v1":
        raise RuntimeError("worker request schema is unknown")
    if (
        type(request["opaque_run_nonce"]) is not str
        or not request["opaque_run_nonce"]
        or len(request["opaque_run_nonce"].encode("utf-8")) > 256
        or type(request["adapter_id"]) is not str
        or not request["adapter_id"]
        or type(request["scientific_inputs"]) is not dict
        or type(request["numerical_controls"]) is not dict
        or type(request["capsule_sha256"]) is not str
        or len(request["capsule_sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in request["capsule_sha256"]
        )
    ):
        raise RuntimeError("worker request field is malformed")
    _require_json_value(request)
    return request


def _write_result_exclusive(payload):
    if len(payload) > _RESULT_LIMIT:
        raise RuntimeError("worker result exceeds the byte bound")
    descriptor = os.open(
        _RESULT_PATH,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
    )
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise RuntimeError("worker result write failed")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fixed_worker_main():
    request_bytes = _read_stable_regular(_REQUEST_PATH, _INPUT_LIMIT)
    request = _parse_request(request_bytes)
    capsule_bytes = _read_stable_regular(_CAPSULE_PATH, _CAPSULE_LIMIT)
    capsule_sha256 = _sha256(capsule_bytes).hex()
    if capsule_sha256 != request["capsule_sha256"]:
        raise RuntimeError("worker capsule hash mismatch")
    capsule_namespace = {"__name__": "scientific_capsule"}
    exec(
        compile(capsule_bytes, _CAPSULE_PATH, "exec"),
        capsule_namespace,
    )
    if (
        capsule_namespace.get("__literature_capsule_schema__")
        != "scientific_capsule_v1"
        or capsule_namespace.get("__literature_capsule_role__")
        not in {"adapter", "oracle"}
        or not callable(
            capsule_namespace.get("__literature_scientific_entry__")
        )
    ):
        raise RuntimeError("worker capsule metadata is malformed")
    worker_started_monotonic_ns = int(os.times().elapsed * 1000000000)
    scientific_result = capsule_namespace["__literature_scientific_entry__"](
        request["scientific_inputs"], request["numerical_controls"]
    )
    worker_finished_monotonic_ns = int(os.times().elapsed * 1000000000)
    if type(scientific_result) is not dict:
        raise RuntimeError("worker local result must be an exact mapping")
    if scientific_result.get("schema_version") == "scientific_result_body_v1":
        if set(scientific_result) != {
            "schema_version",
            "observable_identity",
            "fields",
            "units",
            "uncertainty",
            "raw_convergence_evidence",
            "backend_diagnostics",
            "operation_counts_or_sizes",
        }:
            raise RuntimeError("scientific result body is not closed")
        local_result = {
            "schema_version": "local_observable_result_v1",
            "adapter_id": request["adapter_id"],
            "capsule_sha256": capsule_sha256,
            "request_sha256": _sha256(request_bytes).hex(),
            "observable_identity": scientific_result["observable_identity"],
            "fields": scientific_result["fields"],
            "units": scientific_result["units"],
            "uncertainty": scientific_result["uncertainty"],
            "raw_convergence_evidence": scientific_result[
                "raw_convergence_evidence"
            ],
            "backend_diagnostics": scientific_result[
                "backend_diagnostics"
            ],
            "operation_counts_or_sizes": scientific_result[
                "operation_counts_or_sizes"
            ],
            "worker_started_monotonic_ns": worker_started_monotonic_ns,
            "worker_finished_monotonic_ns": worker_finished_monotonic_ns,
        }
    else:
        local_result = scientific_result
    _require_json_value(local_result)
    result = {
        "schema_version": "worker_result_transport_v1",
        "adapter_id": request["adapter_id"],
        "capsule_sha256": capsule_sha256,
        "request_sha256": _sha256(request_bytes).hex(),
        "local_result": local_result,
    }
    _write_result_exclusive(_canonical_json_bytes(result))


if __name__ == "__main__":
    _fixed_worker_main()
'''
    return source.encode("utf-8")


def emit_tracee_launcher():
    """Return the fixed launcher that applies tracee policy then re-execs."""

    source = r'''import ctypes
import json
import os
import resource
import sys

_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}
_BOOTSTRAP = r"""
import ctypes
import json
import os
import resource

worker_arguments = __import__("sys").argv
ready_fd = int(worker_arguments[1])
proceed_fd = int(worker_arguments[2])
host_canary_path = worker_arguments[3]
os.environ.pop("LD_LIBRARY_PATH", None)

class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

class Data(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]

libc = ctypes.CDLL(None, use_errno=True)
header = Header(0x20080522, 0)
data = (Data * 2)()
capget_code = libc.capget(ctypes.byref(header), ctypes.byref(data))
bounding = []
ambient = []
for capability in range(64):
    bounded = libc.prctl(23, capability, 0, 0, 0)
    if bounded >= 0:
        bounding.append(bounded)
    ambient_value = libc.prctl(47, 2, capability, 0, 0)
    if ambient_value >= 0:
        ambient.append(ambient_value)
no_new_privileges = libc.prctl(39, 0, 0, 0, 0)
open_limit = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
inherited = []
for descriptor in range(3, min(open_limit, 4096)):
    try:
        os.fstat(descriptor)
    except OSError:
        continue
    inherited.append(descriptor)
host_errno = 0
try:
    os.open(host_canary_path, os.O_RDONLY)
except OSError as error:
    host_errno = error.errno
facts = {
    "ambient_values": ambient,
    "bounding_values": bounding,
    "capability_words": [
        [item.effective, item.permitted, item.inheritable]
        for item in data
    ],
    "capget_code": capget_code,
    "current_directory": os.getcwd(),
    "environment_keys": sorted(os.environ),
    "host_canary_errno": host_errno,
    "inherited_fds": inherited,
    "no_new_privileges": no_new_privileges,
    "resource_limits": {
        "address_space": list(resource.getrlimit(resource.RLIMIT_AS)),
        "core": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "cpu": list(resource.getrlimit(resource.RLIMIT_CPU)),
        "file_size": list(resource.getrlimit(resource.RLIMIT_FSIZE)),
        "open_files": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
        "processes": list(resource.getrlimit(resource.RLIMIT_NPROC)),
    },
    "visible_top_level": sorted(os.listdir("/")),
}
payload = json.dumps(
    facts, sort_keys=True, separators=(",", ":")
).encode("utf-8") + b"\n"
if os.write(ready_fd, payload) != len(payload):
    raise RuntimeError("bootstrap readiness write was short")
if os.read(proceed_fd, 1) != b"G":
    raise RuntimeError("bootstrap release token is malformed")
os.close(ready_fd)
os.close(proceed_fd)
worker_globals = {
    "__name__": "__main__",
    "__file__": "/adapter/fixed_worker.py",
    "__package__": None,
}
worker_fd = os.open(
    "/adapter/fixed_worker.py",
    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
)
try:
    worker_source = b""
    while True:
        chunk = os.read(worker_fd, 1048576)
        if not chunk:
            break
        worker_source += chunk
finally:
    os.close(worker_fd)
try:
    exec(
        compile(worker_source, "/adapter/fixed_worker.py", "exec"),
        worker_globals,
        worker_globals,
    )
except BaseException:
    os._exit(1)
"""


class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]


class Data(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]


if len(sys.argv) != 9:
    raise RuntimeError("launcher arguments are not closed")
root, loader, interpreter = sys.argv[1:4]
ready_fd = int(sys.argv[4])
proceed_fd = int(sys.argv[5])
close_fds = json.loads(sys.argv[6])
limits = json.loads(sys.argv[7])
host_canary_path = sys.argv[8]
launcher_environment = dict(_ENVIRONMENT)
launcher_environment["PYTHONHOME"] = root + "/runtime"
launcher_environment["LD_LIBRARY_PATH"] = root + "/runtime/native"
if os.environ != launcher_environment:
    raise RuntimeError("launcher environment is not closed")
os.environ.clear()
os.environ.update(_ENVIRONMENT)
if (
    type(close_fds) is not list
    or any(type(item) is not int or item < 3 for item in close_fds)
    or close_fds != sorted(set(close_fds))
    or type(limits) is not dict
    or set(limits) != {
        "address_space_bytes", "cpu_seconds", "file_descriptors",
        "output_bytes", "process_count", "wall_seconds",
    }
):
    raise RuntimeError("launcher policy is malformed")

os.chroot(root)
os.chdir("/")
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(
    resource.RLIMIT_CPU, (limits["cpu_seconds"], limits["cpu_seconds"])
)
resource.setrlimit(
    resource.RLIMIT_AS,
    (limits["address_space_bytes"], limits["address_space_bytes"]),
)
resource.setrlimit(
    resource.RLIMIT_FSIZE, (limits["output_bytes"], limits["output_bytes"])
)
resource.setrlimit(
    resource.RLIMIT_NOFILE,
    (limits["file_descriptors"], limits["file_descriptors"]),
)
resource.setrlimit(
    resource.RLIMIT_NPROC, (limits["process_count"], limits["process_count"])
)
libc = ctypes.CDLL(None, use_errno=True)
for capability in range(64):
    result = libc.prctl(24, capability, 0, 0, 0)
    if result != 0 and ctypes.get_errno() != 22:
        raise OSError(ctypes.get_errno(), "bounding capability drop failed")
if libc.prctl(47, 4, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "ambient capability clear failed")
header = Header(0x20080522, 0)
data = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
    raise OSError(ctypes.get_errno(), "capability set clear failed")
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "no-new-privileges failed")
for descriptor in close_fds:
    if descriptor not in (ready_fd, proceed_fd):
        try:
            os.close(descriptor)
        except OSError:
            pass
os.set_inheritable(ready_fd, True)
os.set_inheritable(proceed_fd, True)
argv = (
    interpreter,
    "-I", "-S", "-B", "-c", _BOOTSTRAP,
    str(ready_fd), str(proceed_fd), host_canary_path,
)
exec_environment = dict(_ENVIRONMENT)
exec_environment["LD_LIBRARY_PATH"] = "/runtime/native"
os.execve(interpreter, argv, exec_environment)
'''
    return source.encode("utf-8")


@dataclass(frozen=True)
class _RunDirectories:
    run_directory: str
    supervisor_directory: str
    input_directory: str
    worker_output_directory: str
    directory_fds: MappingProxyType
    directory_identities: _FrozenJsonObject
    _owned_fds: list[int]


def create_run_directories(*, scratch_parent, audit_run_id):
    """Exclusively create and retain the three host-side run directories."""

    _require_text(audit_run_id, "audit_run_id")
    try:
        parent = Path(scratch_parent).resolve(strict=True)
        parent_status = parent.stat()
    except OSError as error:
        raise _ContractError("run scratch parent is unavailable") from error
    if not stat.S_ISDIR(parent_status.st_mode):
        raise _ContractError("run scratch parent must be a directory")
    run_directory = None
    for counter in range(128):
        material = (
            audit_run_id.encode("utf-8")
            + b"\0"
            + str(os.getpid()).encode("ascii")
            + b"\0"
            + str(time.monotonic_ns()).encode("ascii")
            + b"\0"
            + str(counter).encode("ascii")
        )
        candidate = parent / (
            "isolated-recalculation-" + hashlib.sha256(material).hexdigest()
        )
        try:
            os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        except OSError as error:
            raise _ContractError(
                "run directory exclusive creation failed"
            ) from error
        run_directory = candidate
        break
    if run_directory is None:
        raise _ContractError("run directory uniqueness exhausted")
    directories = {}
    descriptors = {}
    identities = {}
    owned = []
    try:
        for name in ("supervisor", "input", "worker-output"):
            path = run_directory / name
            os.mkdir(path, 0o700)
            descriptor = os.open(
                path,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
            )
            owned.append(descriptor)
            status = os.fstat(descriptor)
            path_status = path.lstat()
            if (
                not stat.S_ISDIR(status.st_mode)
                or stat.S_IMODE(status.st_mode) != 0o700
                or (status.st_dev, status.st_ino)
                != (path_status.st_dev, path_status.st_ino)
            ):
                raise _ContractError("run subdirectory identity mismatch")
            directories[name] = str(path)
            descriptors[name] = descriptor
            identities[name] = (status.st_dev, status.st_ino)
    except (OSError, _ContractError) as error:
        for descriptor in owned:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if isinstance(error, _ContractError):
            raise
        raise _ContractError("run subdirectory creation failed") from error
    return _RunDirectories(
        run_directory=str(run_directory),
        supervisor_directory=directories["supervisor"],
        input_directory=directories["input"],
        worker_output_directory=directories["worker-output"],
        directory_fds=MappingProxyType(dict(descriptors)),
        directory_identities=_snapshot_json(
            identities, "run directory identities"
        ),
        _owned_fds=owned,
    )


def _task10_stable_file_mount_row(path, logical_path):
    descriptor = None
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise _ContractError("mount source must be a single-link file")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        identity = lambda item: (
            item.st_dev,
            item.st_ino,
            item.st_nlink,
            item.st_size,
            item.st_mode,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        if identity(before) != identity(after) or total != before.st_size:
            raise _ContractError("mount source changed while hashing")
        return {
            "logical_path": logical_path,
            "source_path": str(path),
            "source_kind": "regular",
            "source_device": before.st_dev,
            "source_inode": before.st_ino,
            "source_size": before.st_size,
            "source_mode": stat.S_IMODE(before.st_mode),
            "source_sha256": digest.hexdigest(),
            "read_only": True,
            "nodev": True,
            "nosuid": True,
        }
    except _ContractError:
        raise
    except OSError as error:
        raise _ContractError("mount source cannot be audited") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _build_private_root_mount_manifest(
    layout,
    runtime_snapshot,
    *,
    capsule_path,
    worker_path,
    request_path,
):
    if type(layout) is not _RunDirectories:
        raise _ContractError("mount manifest requires an authentic run layout")
    if type(runtime_snapshot) is not RuntimeSnapshot:
        raise _ContractError("mount manifest requires an exact runtime snapshot")
    try:
        namespace = object.__getattribute__(runtime_snapshot, "__dict__")
        state = dict.__getitem__(namespace, "_retained_runtime_state")
    except (AttributeError, KeyError, TypeError) as error:
        raise _ContractError(
            "runtime snapshot has no retained mount authority"
        ) from error
    if (
        type(state) is not _RetainedRuntimeSnapshotState
        or object.__getattribute__(state, "token")
        is not _RUNTIME_RETAINED_STATE_TOKEN
        or object.__getattribute__(state, "owner_ref")() is not runtime_snapshot
        or not object.__getattribute__(state, "finalizer").alive
    ):
        raise _ContractError("runtime snapshot mount authority is invalid")
    root_fd = object.__getattribute__(state, "root_fd")
    root_identity = object.__getattribute__(state, "root_identity")
    files = object.__getattribute__(state, "files")
    try:
        root_status = os.fstat(root_fd)
    except OSError as error:
        raise _ContractError("runtime snapshot mount authority is closed") from error
    if (
        not stat.S_ISDIR(root_status.st_mode)
        or root_status.st_dev != root_identity["device"]
        or root_status.st_ino != root_identity["inode"]
    ):
        raise _ContractError("runtime snapshot mount authority changed")

    expected_paths = {
        "scientific_capsule.py": (
            Path(capsule_path),
            Path(layout.supervisor_directory),
            "/adapter/scientific_capsule.py",
        ),
        "fixed_worker.py": (
            Path(worker_path),
            Path(layout.supervisor_directory),
            "/adapter/fixed_worker.py",
        ),
        "request.json": (
            Path(request_path),
            Path(layout.input_directory),
            "/input/request.json",
        ),
    }
    rows = []
    for expected_name, (path, parent, logical_path) in expected_paths.items():
        if (
            not path.is_absolute()
            or path.name != expected_name
            or path.parent != parent
        ):
            raise _ContractError("mount source path is outside its retained class")
        rows.append(_task10_stable_file_mount_row(path, logical_path))

    manifest_rows = {
        row["logical_destination"]: row
        for row in runtime_snapshot.manifest.resources
        if row["file_type"] == "regular"
    }
    runtime_logical_paths = set()
    mounted_runtime_rows = {}
    for file_row in files:
        basename = file_row["basename"]
        logical_path = file_row["logical_destination"]
        if (
            type(basename) is not str
            or type(logical_path) is not str
            or not logical_path.startswith("/runtime/")
            or logical_path in runtime_logical_paths
        ):
            raise _ContractError("runtime snapshot mount row is malformed")
        runtime_logical_paths.add(logical_path)
        pinned_path = Path(f"/proc/self/fd/{root_fd}/{basename}")
        row = _task10_stable_file_mount_row(pinned_path, logical_path)
        if (
            row["source_device"] != file_row["device"]
            or row["source_inode"] != file_row["inode"]
            or row["source_size"] != file_row["size"]
            or row["source_mode"] != file_row["mode"]
            or row["source_sha256"] != file_row["sha256"]
        ):
            raise _ContractError("runtime snapshot mount file changed")
        rows.append(row)
        mounted_runtime_rows[logical_path] = row

    if set(mounted_runtime_rows) != set(manifest_rows):
        raise _ContractError("runtime snapshot manifest/file set changed")
    aliases = {}
    stdlib_version = None
    runtime_loader_path = None
    for logical_path, mount_row in mounted_runtime_rows.items():
        manifest_row = manifest_rows[logical_path]
        purpose = manifest_row["purpose"]
        candidate_aliases = []
        if purpose == "imported_standard_library":
            prefix = "/runtime/stdlib/"
            if not logical_path.startswith(prefix):
                raise _ContractError("runtime stdlib destination is malformed")
            relative = PurePosixPath(logical_path[len(prefix):])
            resolved = PurePosixPath(manifest_row["resolved_path"])
            if tuple(resolved.parts[-len(relative.parts):]) != relative.parts:
                raise _ContractError("runtime stdlib source layout changed")
            source_prefix = resolved.parts[:-len(relative.parts)]
            if (
                not source_prefix
                or re.fullmatch(r"python[0-9]+\.[0-9]+", source_prefix[-1])
                is None
            ):
                raise _ContractError("runtime stdlib version is not closed")
            version = source_prefix[-1]
            if stdlib_version is None:
                stdlib_version = version
            elif stdlib_version != version:
                raise _ContractError("runtime stdlib versions are ambiguous")
            candidate_aliases.append(
                "/runtime/lib/" + version + "/" + relative.as_posix()
            )
        if purpose in {"dynamic_loader", "dynamic_library"}:
            resolved_path = manifest_row["resolved_path"]
            resolved_alias = (
                "/runtime/native/" + PurePosixPath(resolved_path).name
            )
            candidate_aliases.append(resolved_alias)
            if purpose == "dynamic_loader":
                if runtime_loader_path is not None:
                    raise _ContractError("runtime loader is ambiguous")
                runtime_loader_path = resolved_alias
            for link in manifest_row["link_identity"]:
                if link["target_path"] == resolved_path:
                    link_name = PurePosixPath(link["path"]).name
                    if link_name != PurePosixPath(resolved_path).name:
                        candidate_aliases.append(
                            "/runtime/native/" + link_name
                        )
        for alias in candidate_aliases:
            existing = aliases.get(alias)
            if existing is not None and (
                existing["source_device"],
                existing["source_inode"],
                existing["source_sha256"],
            ) != (
                mount_row["source_device"],
                mount_row["source_inode"],
                mount_row["source_sha256"],
            ):
                raise _ContractError("runtime executable alias is ambiguous")
            alias_row = dict(mount_row)
            alias_row["logical_path"] = alias
            aliases[alias] = alias_row
    rows.extend(aliases.values())

    output_fd = layout.directory_fds["worker-output"]
    output_status = os.fstat(output_fd)
    output_identity = tuple(layout.directory_identities["worker-output"])
    if (output_status.st_dev, output_status.st_ino) != output_identity:
        raise _ContractError("worker output mount authority changed")
    rows.append(
        {
            "logical_path": "/output",
            "source_path": layout.worker_output_directory,
            "source_kind": "directory",
            "source_device": output_status.st_dev,
            "source_inode": output_status.st_ino,
            "source_size": None,
            "source_mode": stat.S_IMODE(output_status.st_mode),
            "source_sha256": None,
            "read_only": False,
            "nodev": True,
            "nosuid": True,
        }
    )
    rows.sort(key=lambda row: row["logical_path"])
    if len({row["logical_path"] for row in rows}) != len(rows):
        raise _ContractError("private root mount manifest has a duplicate path")
    return _snapshot_json(
        {
            "schema_version": "private_root_mount_manifest_v1",
            "mounts": tuple(rows),
            "runtime_interpreter_path": "/runtime/bin/python3",
            "runtime_loader_path": runtime_loader_path,
        },
        "private root mount manifest",
    )


def apply_tracee_security_policy(
    resource_limits,
    *,
    private_root,
    inherited_fds,
    interpreter_path,
):
    """Build the single closed tracee security-operation sequence."""

    if type(resource_limits) is not _adapters.ResourceLimits:
        raise _ContractError("resource_limits must be exact ResourceLimits")
    limits = _adapters.ResourceLimits(
        **{
            field.name: getattr(resource_limits, field.name)
            for field in fields(_adapters.ResourceLimits)
        }
    )
    root = _require_text(private_root, "private_root")
    parsed_root = PurePosixPath(root)
    if (
        not parsed_root.is_absolute()
        or ".." in parsed_root.parts
        or str(parsed_root) != root
        or root == "/"
    ):
        raise _ContractError("private_root must be normalized and absolute")
    descriptors = _require_exact_tuple(inherited_fds, "inherited_fds")
    if (
        any(type(descriptor) is not int or descriptor < 3 for descriptor in descriptors)
        or descriptors != tuple(sorted(descriptors))
        or len(set(descriptors)) != len(descriptors)
    ):
        raise _ContractError("inherited_fds must be canonical descriptors")
    interpreter = _require_text(interpreter_path, "interpreter_path")
    if interpreter != "/runtime/bin/python3":
        raise _ContractError("interpreter_path must be /runtime/bin/python3")
    return _snapshot_json(
        {
            "schema_version": "tracee_security_plan_v1",
            "operations": (
                {"operation": "chroot", "path": root},
                {"operation": "chdir", "path": "/"},
                {
                    "operation": "set_limits",
                    "cpu_seconds": limits.cpu_seconds,
                    "wall_seconds": limits.wall_seconds,
                    "address_space_bytes": limits.address_space_bytes,
                    "output_bytes": limits.output_bytes,
                    "file_descriptors": limits.file_descriptors,
                    "process_count": limits.process_count,
                },
                {"operation": "drop_capabilities", "sets": "all"},
                {"operation": "no_new_privileges", "enabled": True},
                {"operation": "close_fds", "fds": descriptors},
                {
                    "operation": "exec_interpreter",
                    "argv": (
                        interpreter,
                        "-I",
                        "-S",
                        "-B",
                        "/adapter/fixed_worker.py",
                    ),
                },
            ),
        },
        "tracee security plan",
    )


_TASK10_TOPOLOGY = (
    "outer_coordinator",
    "unshare_namespace_supervisor",
    "external_strace_tracer",
    "fixed_tracee_launcher",
    "fixed_worker",
)
_TASK10_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}
_TASK10_COMMANDS = (
    "unshare",
    "mount",
    "chroot",
    "strace",
    "python",
    "supervisor_python",
    "launcher",
)


_TASK10_SUPERVISOR_SOURCE = r'''
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys

if len(sys.argv) != 4 or sys.argv[1] != "--request-fd":
    raise RuntimeError("namespace supervisor request arguments are malformed")
request_fd = int(sys.argv[2])
request_status = os.fstat(request_fd)
if (
    not stat.S_ISREG(request_status.st_mode)
    or request_status.st_nlink != 1
    or stat.S_IMODE(request_status.st_mode) != 0o600
    or request_status.st_size <= 0
    or request_status.st_size > 16777216
):
    raise RuntimeError("namespace supervisor request file is rejected")
request_chunks = []
request_remaining = request_status.st_size
while request_remaining:
    request_chunk = os.read(
        request_fd, min(request_remaining, 1048576)
    )
    if not request_chunk:
        raise RuntimeError("namespace supervisor request ended early")
    request_chunks.append(request_chunk)
    request_remaining -= len(request_chunk)
if os.read(request_fd, 1):
    raise RuntimeError("namespace supervisor request grew while reading")
request_bytes = b"".join(request_chunks)
if hashlib.sha256(request_bytes).hexdigest() != sys.argv[3]:
    raise RuntimeError("namespace supervisor request hash mismatch")
request = json.loads(request_bytes.decode("utf-8", "strict"))
commands = request["commands"]
environment = request["environment"]
supervisor = Path(request["supervisor_directory"])
root = supervisor / "private-root"
root.mkdir(mode=0o700)
os.umask(0o077)
host_canary = supervisor / "host-canary-denied"
host_canary_fd = os.open(
    host_canary,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
    0o600,
)
try:
    os.write(host_canary_fd, b"task10-host-canary")
    os.fsync(host_canary_fd)
finally:
    os.close(host_canary_fd)


def execute(arguments, *, timeout=20):
    completed = subprocess.run(
        tuple(arguments),
        check=False,
        close_fds=True,
        cwd="/",
        env=environment,
        pass_fds=tuple(request["pass_fds"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[:2048].decode(
            "utf-8", "replace"
        )
        raise RuntimeError("namespace mount command failed: " + detail)


execute((commands["mount"], "--make-rprivate", "/"))
execute((
    commands["mount"], "-t", "tmpfs", "-o",
    "nodev,nosuid,size=256m", "tmpfs", str(root),
))


def mount_target(row):
    target = root / row["logical_path"].lstrip("/")
    if row["source_kind"] == "directory":
        target.mkdir(mode=0o755, parents=True, exist_ok=True)
    else:
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600,
        )
        os.close(descriptor)
    execute((commands["mount"], "--bind", row["source_path"], str(target)))
    mode = "rw" if row["read_only"] is False else "ro"
    execute((
        commands["mount"], "-o",
        "remount,bind," + mode + ",nodev,nosuid", str(target),
    ))


for mount_row in request["mounts"]:
    mount_target(mount_row)

root_loader = str(root) + request["runtime_loader_path"]
root_interpreter = str(root) + request["runtime_interpreter_path"]
entropy_directory = root / "dev"
entropy_directory.mkdir(mode=0o755)
entropy_target = entropy_directory / "urandom"
entropy_fd = os.open(
    entropy_target,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
    0o400,
)
os.close(entropy_fd)
execute((
    commands["mount"], "--bind", request["entropy_source"],
    str(entropy_target),
))
loader_directory = root / "lib64"
loader_directory.mkdir(mode=0o755)
loader_target = loader_directory / "ld-linux-x86-64.so.2"
loader_fd = os.open(
    loader_target,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
    0o500,
)
os.close(loader_fd)
execute((commands["mount"], "--bind", root_loader, str(loader_target)))
execute((
    commands["mount"], "-o", "remount,bind,ro,nodev,nosuid",
    str(loader_target),
))
execute((
    commands["mount"], "-o", "remount,bind,ro,nosuid",
    str(entropy_target),
))

ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
proceed_read, proceed_write = os.pipe2(os.O_CLOEXEC)
os.set_inheritable(ready_write, True)
os.set_inheritable(proceed_read, True)
infrastructure_fds = sorted(
    set(request["pass_fds"] + [ready_write, proceed_read])
)
limits = request["limits"]
trace_path = supervisor / "trace.log"
launcher_arguments = (
    root_interpreter,
    "-S", "-B", request["launcher_path"],
    str(root),
    request["runtime_loader_path"],
    request["runtime_interpreter_path"],
    str(ready_write),
    str(proceed_read),
    json.dumps(infrastructure_fds, separators=(",", ":")),
    json.dumps(limits, sort_keys=True, separators=(",", ":")),
    str(host_canary),
)
trace_arguments = (
    commands["strace"], "-ff", "-s", "65535", "-yy",
    "-e", "trace=%file,%network,%process,getrandom,prctl,capget,capset",
    "-o", str(trace_path), "--", *launcher_arguments,
)
tracee = subprocess.Popen(
    trace_arguments,
    executable=commands["strace"],
    close_fds=True,
    cwd="/",
    env={
        **environment,
        "LD_LIBRARY_PATH": str(root / "runtime" / "native"),
        "PYTHONHOME": str(root / "runtime"),
    },
    pass_fds=tuple(infrastructure_fds),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
os.close(ready_write)
os.close(proceed_read)
readiness = b""
while b"\n" not in readiness:
    readable, _, _ = select.select([ready_read], [], [], 30)
    if not readable:
        tracee.kill()
        raise RuntimeError("tracee bootstrap readiness timed out")
    chunk = os.read(ready_read, 65537 - len(readiness))
    if not chunk:
        break
    readiness += chunk
    if len(readiness) > 65536:
        tracee.kill()
        raise RuntimeError("tracee bootstrap readiness is oversized")
os.close(ready_read)
if not readiness:
    stdout, stderr = tracee.communicate(timeout=5)
    raise RuntimeError(
        "tracee exited before readiness: "
        + (stderr or stdout)[:2048].decode("utf-8", "replace")
    )
try:
    bootstrap = json.loads(readiness.decode("utf-8", "strict"))
except Exception as error:
    tracee.kill()
    raise RuntimeError("tracee bootstrap readiness is malformed") from error

libc = ctypes.CDLL(None, use_errno=True)
if libc.umount2(os.fsencode(str(entropy_target)), 0) != 0:
    tracee.kill()
    raise OSError(ctypes.get_errno(), "entropy bind unmount failed")
entropy_target.unlink()
entropy_directory.rmdir()
if libc.umount2(os.fsencode(str(loader_target)), 2) != 0:
    tracee.kill()
    raise OSError(ctypes.get_errno(), "loader bind unmount failed")
loader_target.unlink()
loader_directory.rmdir()
execute((
    commands["mount"], "-o", "remount,ro,nodev,nosuid", str(root),
))
visible_top_level = sorted(os.listdir(root))
if visible_top_level != ["adapter", "input", "output", "runtime"]:
    tracee.kill()
    raise RuntimeError("worker-visible root contains an undeclared class")
if os.write(proceed_write, b"G") != 1:
    tracee.kill()
    raise RuntimeError("tracee release write was short")
os.close(proceed_write)
try:
    stdout, stderr = tracee.communicate(timeout=limits["wall_seconds"] + 20)
except subprocess.TimeoutExpired:
    tracee.kill()
    stdout, stderr = tracee.communicate()
    raise RuntimeError("traced worker exceeded the wall limit")

raw_trace_paths = sorted(supervisor.glob("trace.log.*"))
if not raw_trace_paths:
    raise RuntimeError("strace produced no per-PID logs")
trace_bundle = bytearray()
for raw_trace_path in raw_trace_paths:
    suffix = raw_trace_path.name.rsplit(".", 1)[-1]
    if not suffix.isdigit() or not suffix or suffix.startswith("0"):
        raise RuntimeError("strace produced a malformed PID log name")
    raw_status = raw_trace_path.lstat()
    if (
        not stat.S_ISREG(raw_status.st_mode)
        or raw_status.st_nlink != 1
        or stat.S_IMODE(raw_status.st_mode) != 0o600
        or raw_status.st_size <= 0
        or raw_status.st_size > 16 * 1024 * 1024
    ):
        raise RuntimeError("strace per-PID log metadata is rejected")
    raw_trace = raw_trace_path.read_bytes()
    if len(raw_trace) != raw_status.st_size or not raw_trace.endswith(b"\n"):
        raise RuntimeError("strace per-PID log is incomplete")
    prefix = suffix.encode("ascii") + b" "
    for raw_line in raw_trace.splitlines(keepends=True):
        trace_bundle.extend(prefix)
        trace_bundle.extend(raw_line)
        if len(trace_bundle) > 16 * 1024 * 1024:
            raise RuntimeError("strace bundle is oversized")
trace_fd = os.open(
    trace_path,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
    0o600,
)
try:
    offset = 0
    while offset < len(trace_bundle):
        offset += os.write(trace_fd, trace_bundle[offset:])
    os.fsync(trace_fd)
finally:
    os.close(trace_fd)

mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
route_rows = Path("/proc/net/route").read_text(
    encoding="ascii"
).splitlines()[1:]
interfaces = sorted(
    line.split(":", 1)[0].strip()
    for line in Path("/proc/net/dev").read_text(
        encoding="ascii"
    ).splitlines()[2:]
    if ":" in line
)
root_line = next(
    line for line in mountinfo.splitlines()
    if line.split()[4] == str(root)
)
separator = root_line.split().index("-")
root_filesystem = root_line.split()[separator + 1]
root_read_only = "ro" in root_line.split()[5].split(",")
response = {
    "audit_run_id": request["audit_run_id"],
    "point_id": request["point_id"],
    "process_role": request["process_role"],
    "topology": request["topology"],
    "supervisor_waited_for_tracee": True,
    "supervisor_outside_chroot": True,
    "worker_exit_code": tracee.returncode,
    "stdout": stdout[:65536].decode("utf-8", "replace"),
    "stderr": stderr[:65536].decode("utf-8", "replace"),
    "namespace_identifiers": {
        name: os.readlink("/proc/self/ns/" + name)
        for name in ("user", "mnt", "net")
    },
    "mount_facts": {
        "root_filesystem": root_filesystem,
        "root_read_only": root_read_only,
        "output_writable": True,
        "visible_top_level": ["runtime", "adapter", "input", "output"],
        "supervisor_visible": False,
    },
    "environment_facts": {
        "names": bootstrap["environment_keys"],
        "parent_canary_present": (
            "TASK10_PARENT_CANARY" in bootstrap["environment_keys"]
        ),
    },
    "resource_limit_facts": {
        **limits,
        "no_new_privileges": bootstrap["no_new_privileges"] == 1,
        "capabilities_empty": (
            bootstrap["capget_code"] == 0
            and all(
                all(value == 0 for value in row)
                for row in bootstrap["capability_words"]
            )
            and not any(bootstrap["bounding_values"])
            and not any(bootstrap["ambient_values"])
        ),
    },
    "chroot_facts": {
        "current_directory": bootstrap["current_directory"],
        "host_canary_errno": bootstrap["host_canary_errno"],
        "host_canary_exists_outside": host_canary.is_file(),
        "isolated": (
            bootstrap["visible_top_level"]
            == [
                "adapter", "dev", "input", "lib64", "output", "runtime"
            ]
        ),
        "network_isolated": not route_rows and interfaces == ["lo"],
    },
}
attestation = json.dumps(
    response, sort_keys=True, separators=(",", ":")
).encode("utf-8")
attestation_fd = os.open(
    supervisor / "attestation.json",
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
    0o600,
)
try:
    offset = 0
    while offset < len(attestation):
        offset += os.write(attestation_fd, attestation[offset:])
    os.fsync(attestation_fd)
finally:
    os.close(attestation_fd)
print(attestation.decode("utf-8"))
'''


def _task10_validate_mount_manifest(value):
    manifest = _exact_keys(
        value,
        (
            "schema_version",
            "mounts",
            "runtime_interpreter_path",
            "runtime_loader_path",
        ),
        "private root mount manifest",
    )
    if manifest["schema_version"] != "private_root_mount_manifest_v1":
        raise _ContractError("private root mount manifest schema is unknown")
    if manifest["runtime_interpreter_path"] != "/runtime/bin/python3":
        raise _ContractError("private root interpreter path is not closed")
    loader = manifest["runtime_loader_path"]
    if loader is not None and (
        type(loader) is not str
        or not loader.startswith("/runtime/native/")
        or PurePosixPath(loader).as_posix() != loader
    ):
        raise _ContractError("private root loader path is malformed")
    rows = _require_exact_tuple(manifest["mounts"], "mounts")
    if not rows:
        raise _ContractError("private root mount manifest is empty")
    logical_paths = []
    writable = []
    for index, raw_row in enumerate(rows):
        row = _exact_keys(
            raw_row,
            (
                "logical_path",
                "source_path",
                "source_kind",
                "source_device",
                "source_inode",
                "source_size",
                "source_mode",
                "source_sha256",
                "read_only",
                "nodev",
                "nosuid",
            ),
            f"mounts[{index}]",
        )
        logical_path = _require_text(
            row["logical_path"], f"mounts[{index}].logical_path"
        )
        if row["nodev"] is not True or row["nosuid"] is not True:
            raise _ContractError("private root mount lacks nodev or nosuid")
        if row["read_only"] is False:
            writable.append(logical_path)
        elif row["read_only"] is not True:
            raise _ContractError("private root mount read_only is malformed")
        logical_paths.append(logical_path)
    if len(set(logical_paths)) != len(logical_paths):
        raise _ContractError("private root mount path is duplicated")
    if writable != ["/output"]:
        raise _ContractError("output must be the only writable mount")
    required = {
        "/adapter/scientific_capsule.py",
        "/adapter/fixed_worker.py",
        "/input/request.json",
        "/output",
    }
    if not required <= set(logical_paths) or any(
        path not in required and not path.startswith("/runtime/")
        for path in logical_paths
    ):
        raise _ContractError("private root mount classes are not exact")
    return _snapshot_json(
        {
            "schema_version": manifest["schema_version"],
            "mounts": rows,
            "runtime_interpreter_path": manifest[
                "runtime_interpreter_path"
            ],
            "runtime_loader_path": loader,
        },
        "private root mount manifest",
    )


def _task10_validate_command_identities(value):
    identities = _exact_keys(
        value, _TASK10_COMMANDS, "namespace supervisor commands"
    )
    normalized = {}
    for command in _TASK10_COMMANDS:
        record = _exact_keys(
            identities[command],
            ("path", "version", "sha256"),
            f"namespace supervisor command {command}",
        )
        path = _require_text(record["path"], f"{command}.path")
        if not PurePosixPath(path).is_absolute():
            raise _ContractError("namespace supervisor command path is relative")
        normalized[command] = {
            "path": path,
            "version": _require_text(record["version"], f"{command}.version"),
            "sha256": _require_sha256(record["sha256"], f"{command}.sha256"),
        }
    return _snapshot_json(normalized, "namespace supervisor commands")


def _run_namespace_supervisor(
    layout,
    mount_manifest,
    security_plan,
    *,
    audit_run_id,
    point_id,
    role,
    command_identities,
    runner,
):
    if type(layout) is not _RunDirectories:
        raise _ContractError("namespace supervisor requires an authentic layout")
    audit_id = _require_text(audit_run_id, "audit_run_id")
    point = _require_text(point_id, "point_id")
    process_role = _require_role(role, "role")
    if not callable(runner):
        raise _ContractError("namespace supervisor runner must be callable")
    mounts = _task10_validate_mount_manifest(mount_manifest)
    security = _exact_keys(
        security_plan,
        ("schema_version", "operations"),
        "tracee security plan",
    )
    if security["schema_version"] != "tracee_security_plan_v1":
        raise _ContractError("tracee security plan schema is unknown")
    operation_names = tuple(
        _exact_keys(item, tuple(item), "tracee operation")["operation"]
        for item in _require_exact_tuple(security["operations"], "operations")
    )
    if operation_names != (
        "chroot",
        "chdir",
        "set_limits",
        "drop_capabilities",
        "no_new_privileges",
        "close_fds",
        "exec_interpreter",
    ):
        raise _ContractError("tracee security operation order changed")
    commands = _task10_validate_command_identities(command_identities)
    payload = _snapshot_json(
        {
            "schema_version": "namespace_supervisor_request_v1",
            "audit_run_id": audit_id,
            "point_id": point,
            "process_role": process_role,
            "topology": _TASK10_TOPOLOGY,
            "supervisor_directory": layout.supervisor_directory,
            "mount_manifest": mounts,
            "security_plan": security_plan,
            "command_identities": commands,
            "environment": _TASK10_ENVIRONMENT,
            "unrelated_fds": (),
        },
        "namespace supervisor request",
    )
    try:
        raw_response = runner("run_namespace_supervisor", payload)
    except Exception as error:
        raise _ContractError("namespace supervisor runner failed") from error
    response = _exact_keys(
        raw_response,
        (
            "audit_run_id",
            "point_id",
            "process_role",
            "topology",
            "supervisor_waited_for_tracee",
            "supervisor_outside_chroot",
            "worker_exit_code",
            "stdout",
            "stderr",
            "namespace_identifiers",
            "mount_facts",
            "environment_facts",
            "resource_limit_facts",
            "chroot_facts",
        ),
        "namespace supervisor response",
    )
    if (
        response["audit_run_id"] != audit_id
        or response["point_id"] != point
        or response["process_role"] != process_role
        or tuple(response["topology"]) != _TASK10_TOPOLOGY
        or response["supervisor_waited_for_tracee"] is not True
        or response["supervisor_outside_chroot"] is not True
        or type(response["worker_exit_code"]) is not int
        or response["worker_exit_code"] != 0
        or type(response["stdout"]) is not str
        or type(response["stderr"]) is not str
        or response["stdout"]
        or response["stderr"]
    ):
        raise _ContractError("namespace supervisor response is contradictory")
    attestation_payload = {
        "schema_version": "process_attestation_v1",
        "process_role": process_role,
        "point_id": point,
        "namespace_identifiers": response["namespace_identifiers"],
        "mount_facts": response["mount_facts"],
        "environment_facts": response["environment_facts"],
        "resource_limit_facts": response["resource_limit_facts"],
        "chroot_facts": response["chroot_facts"],
    }
    return ProcessAttestation(
        **attestation_payload,
        attestation_sha256=_canonical_sha256(attestation_payload),
    )


def _task10_descriptor_sha256(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _production_namespace_supervisor_runner(action, raw_payload):
    if action != "run_namespace_supervisor":
        raise _ContractError("namespace supervisor action is unknown")
    payload = _adapters.thaw_json(raw_payload)
    supervisor = Path(payload["supervisor_directory"])
    launcher_path = supervisor / "fixed_tracee_launcher.py"
    launcher_bytes = emit_tracee_launcher()
    _write_preflight_snapshot(launcher_path, launcher_bytes)
    if _hash_preflight_command(launcher_path) != hashlib.sha256(
        launcher_bytes
    ).hexdigest():
        raise _ContractError("fixed tracee launcher snapshot changed")

    descriptors = []
    command_descriptors = {}
    entropy_descriptor = None
    try:
        for command in _TASK10_COMMANDS:
            identity = payload["command_identities"][command]
            descriptor = os.open(
                identity["path"],
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            descriptors.append(descriptor)
            status = os.fstat(descriptor)
            if (
                not stat.S_ISREG(status.st_mode)
                or _task10_descriptor_sha256(descriptor)
                != identity["sha256"]
            ):
                raise _ContractError(
                    "namespace supervisor command identity changed: "
                    + command
                )
            command_descriptors[command] = descriptor

        supervisor_mounts = []
        for row in payload["mount_manifest"]["mounts"]:
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            if row["source_kind"] == "directory":
                flags |= os.O_DIRECTORY
            descriptor = os.open(row["source_path"], flags)
            descriptors.append(descriptor)
            status = os.fstat(descriptor)
            if row["source_kind"] == "directory":
                if (
                    not stat.S_ISDIR(status.st_mode)
                    or (status.st_dev, status.st_ino)
                    != (row["source_device"], row["source_inode"])
                ):
                    raise _ContractError("namespace mount directory changed")
            elif (
                not stat.S_ISREG(status.st_mode)
                or status.st_nlink != 1
                or status.st_dev != row["source_device"]
                or status.st_ino != row["source_inode"]
                or status.st_size != row["source_size"]
                or stat.S_IMODE(status.st_mode) != row["source_mode"]
                or _task10_descriptor_sha256(descriptor)
                != row["source_sha256"]
            ):
                raise _ContractError("namespace mount file changed")
            copied_row = dict(row)
            copied_row["source_path"] = f"/proc/self/fd/{descriptor}"
            supervisor_mounts.append(copied_row)

        entropy_descriptor = os.open(
            "/dev/urandom", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        descriptors.append(entropy_descriptor)
        entropy_status = os.fstat(entropy_descriptor)
        if not stat.S_ISCHR(entropy_status.st_mode):
            raise _ContractError("interpreter entropy source is not a device")

        operations = payload["security_plan"]["operations"]
        limits = next(
            item for item in operations if item["operation"] == "set_limits"
        )
        limits = {
            name: limits[name]
            for name in (
                "cpu_seconds",
                "wall_seconds",
                "address_space_bytes",
                "output_bytes",
                "file_descriptors",
                "process_count",
            )
        }
        command_paths = {
            command: f"/proc/self/fd/{descriptor}"
            for command, descriptor in command_descriptors.items()
        }
        request = {
            "schema_version": "production_namespace_supervisor_request_v1",
            "audit_run_id": payload["audit_run_id"],
            "point_id": payload["point_id"],
            "process_role": payload["process_role"],
            "topology": payload["topology"],
            "supervisor_directory": payload["supervisor_directory"],
            "commands": command_paths,
            "mounts": supervisor_mounts,
            "runtime_loader_path": payload["mount_manifest"][
                "runtime_loader_path"
            ],
            "runtime_interpreter_path": payload["mount_manifest"][
                "runtime_interpreter_path"
            ],
            "launcher_path": str(launcher_path),
            "environment": payload["environment"],
            "limits": limits,
            "entropy_source": f"/proc/self/fd/{entropy_descriptor}",
            "pass_fds": sorted(set(descriptors)),
        }
        if request["runtime_loader_path"] is None:
            raise _ContractError("runtime snapshot has no executable loader")
        request_bytes = _canonical_bytes(request)
        if len(request_bytes) > _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT:
            raise _ContractError("namespace supervisor request is oversized")
        request_path = supervisor / "namespace-supervisor-request.json"
        try:
            request_write_descriptor = os.open(
                request_path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o600,
            )
            try:
                offset = 0
                while offset < len(request_bytes):
                    written = os.write(
                        request_write_descriptor, request_bytes[offset:]
                    )
                    if written <= 0:
                        raise _ContractError(
                            "namespace supervisor request write failed"
                        )
                    offset += written
                os.fchmod(request_write_descriptor, 0o600)
                os.fsync(request_write_descriptor)
            finally:
                os.close(request_write_descriptor)
        except OSError as error:
            raise _ContractError(
                "namespace supervisor request snapshot failed"
            ) from error
        request_descriptor = os.open(
            request_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        descriptors.append(request_descriptor)
        request_status = os.fstat(request_descriptor)
        request_sha256 = hashlib.sha256(request_bytes).hexdigest()
        if (
            not stat.S_ISREG(request_status.st_mode)
            or request_status.st_nlink != 1
            or stat.S_IMODE(request_status.st_mode) != 0o600
            or request_status.st_size != len(request_bytes)
            or _task10_descriptor_sha256(request_descriptor)
            != request_sha256
        ):
            raise _ContractError(
                "namespace supervisor request snapshot changed"
            )
        completed = subprocess.run(
            (
                payload["command_identities"]["unshare"]["path"],
                "-Urnm",
                command_paths["supervisor_python"],
                "-I",
                "-S",
                "-B",
                "-c",
                _TASK10_SUPERVISOR_SOURCE,
                "--request-fd",
                str(request_descriptor),
                request_sha256,
            ),
            executable=command_paths["unshare"],
            check=False,
            close_fds=True,
            cwd="/",
            env=dict(_TASK10_ENVIRONMENT),
            pass_fds=tuple(sorted(set(descriptors))),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=limits["wall_seconds"] + 60,
        )
        for command, descriptor in command_descriptors.items():
            if _task10_descriptor_sha256(descriptor) != payload[
                "command_identities"
            ][command]["sha256"]:
                raise _ContractError(
                    "namespace supervisor command changed during execution"
                )
        if (
            _task10_descriptor_sha256(request_descriptor) != request_sha256
        ):
            raise _ContractError(
                "namespace supervisor request changed during execution"
            )
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout)[
                :4096
            ].decode("utf-8", "replace")
            raise _ContractError(
                "production namespace supervisor failed: " + diagnostic
            )
        if completed.stderr:
            raise _ContractError("namespace supervisor wrote stderr")
        try:
            return json.loads(completed.stdout.decode("utf-8", "strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _ContractError(
                "namespace supervisor response is malformed"
            ) from error
    except (OSError, StopIteration, subprocess.SubprocessError) as error:
        if isinstance(error, _ContractError):
            raise
        raise _ContractError("production namespace supervisor failed") from error
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def run_namespace_supervisor(
    layout,
    runtime_snapshot,
    resource_limits,
    *,
    preflight_report,
    capsule_path,
    worker_path,
    request_path,
    audit_run_id,
    point_id,
    role,
):
    """Run one fixed worker beneath the persistent private-root supervisor."""

    if type(preflight_report) is not CapabilityPreflightReport:
        raise _ContractError("preflight_report must be exact")
    _validate_capability_preflight_report(preflight_report)
    if not preflight_report.available:
        raise _ContractError("capability preflight is unavailable")
    mount_manifest = _build_private_root_mount_manifest(
        layout,
        runtime_snapshot,
        capsule_path=capsule_path,
        worker_path=worker_path,
        request_path=request_path,
    )
    security_plan = apply_tracee_security_policy(
        resource_limits,
        private_root=str(Path(layout.supervisor_directory) / "private-root"),
        inherited_fds=tuple(sorted(layout.directory_fds.values())),
        interpreter_path="/runtime/bin/python3",
    )
    identities = {
        command: {
            "path": preflight_report.command_identities[command]["path"],
            "version": preflight_report.command_identities[command]["version"],
            "sha256": preflight_report.command_identities[command]["sha256"],
        }
        for command in _TASK10_COMMANDS
    }
    return _run_namespace_supervisor(
        layout,
        mount_manifest,
        security_plan,
        audit_run_id=audit_run_id,
        point_id=point_id,
        role=role,
        command_identities=identities,
        runner=_production_namespace_supervisor_runner,
    )


def construct_private_root(
    layout,
    runtime_snapshot,
    *,
    capsule_path,
    worker_path,
    request_path,
):
    """Construct the exact private-root manifest used by the supervisor."""

    return _build_private_root_mount_manifest(
        layout,
        runtime_snapshot,
        capsule_path=capsule_path,
        worker_path=worker_path,
        request_path=request_path,
    )


def launch_traced_tracee(
    layout,
    runtime_snapshot,
    resource_limits,
    *,
    preflight_report,
    capsule_path,
    worker_path,
    request_path,
    audit_run_id,
    point_id,
    role,
):
    """Launch the one fixed traced tracee through the canonical supervisor."""

    return run_namespace_supervisor(
        layout,
        runtime_snapshot,
        resource_limits,
        preflight_report=preflight_report,
        capsule_path=capsule_path,
        worker_path=worker_path,
        request_path=request_path,
        audit_run_id=audit_run_id,
        point_id=point_id,
        role=role,
    )


def _close_run_directories(layout):
    if type(layout) is not _RunDirectories:
        raise _ContractError("run layout has an unknown type")
    while layout._owned_fds:
        descriptor = layout._owned_fds.pop()
        matching_name = next(
            (
                name
                for name, candidate in layout.directory_fds.items()
                if candidate == descriptor
            ),
            None,
        )
        if matching_name is None:
            continue
        expected = tuple(layout.directory_identities[matching_name])
        try:
            status = os.fstat(descriptor)
        except OSError:
            continue
        if (status.st_dev, status.st_ino) == expected:
            os.close(descriptor)


def _task11_output_directory_status(layout):
    if type(layout) is not _RunDirectories:
        raise _ContractError("worker output requires an authentic layout")
    try:
        descriptor = layout.directory_fds["worker-output"]
        expected_identity = tuple(
            layout.directory_identities["worker-output"]
        )
        descriptor_status = os.fstat(descriptor)
        path_status = Path(layout.worker_output_directory).lstat()
    except (KeyError, OSError, TypeError) as error:
        raise _ContractError("worker output directory is unavailable") from error
    if (
        not stat.S_ISDIR(descriptor_status.st_mode)
        or stat.S_IMODE(descriptor_status.st_mode) != 0o700
        or (descriptor_status.st_dev, descriptor_status.st_ino)
        != expected_identity
        or (path_status.st_dev, path_status.st_ino) != expected_identity
        or not stat.S_ISDIR(path_status.st_mode)
    ):
        raise _ContractError("worker output directory identity changed")
    return descriptor, descriptor_status


def _task11_read_output_file(
    directory_descriptor,
    basename,
    *,
    directory_status,
    maximum_bytes,
    expected_mode,
):
    flags = (
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    )
    try:
        descriptor = os.open(
            basename,
            flags,
            dir_fd=directory_descriptor,
        )
    except OSError as error:
        raise _ContractError("worker output file open failed") from error
    try:
        before = os.fstat(descriptor)
        entry_before = os.stat(
            basename,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_dev != directory_status.st_dev
            or before.st_uid != directory_status.st_uid
            or before.st_gid != directory_status.st_gid
            or stat.S_IMODE(before.st_mode) != expected_mode
            or before.st_size <= 0
            or before.st_size > maximum_bytes
            or (entry_before.st_dev, entry_before.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise _ContractError("worker output file metadata is rejected")
        chunks = []
        total = 0
        while True:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, maximum_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise _ContractError("worker output file is oversized")
        after = os.fstat(descriptor)
        entry_after = os.stat(
            basename,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_nlink,
            before.st_size,
            before.st_mode,
            before.st_uid,
            before.st_gid,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_nlink,
            after.st_size,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        payload = b"".join(chunks)
        entry_identity_before = (
            entry_before.st_dev,
            entry_before.st_ino,
            entry_before.st_mode,
            entry_before.st_uid,
            entry_before.st_gid,
            entry_before.st_size,
            entry_before.st_mtime_ns,
            entry_before.st_ctime_ns,
        )
        entry_identity_after = (
            entry_after.st_dev,
            entry_after.st_ino,
            entry_after.st_mode,
            entry_after.st_uid,
            entry_after.st_gid,
            entry_after.st_size,
            entry_after.st_mtime_ns,
            entry_after.st_ctime_ns,
        )
        if (
            identity_after != identity_before
            or entry_identity_before != identity_before[:2]
            + identity_before[4:7]
            + identity_before[3:4]
            + identity_before[7:]
            or entry_identity_after != entry_identity_before
            or len(payload) != before.st_size
        ):
            raise _ContractError("worker output file changed while reading")
        return payload, before
    except OSError as error:
        raise _ContractError("worker output file read failed") from error
    finally:
        os.close(descriptor)


def _task11_validate_scratch_directory(
    directory_descriptor,
    basename,
    *,
    directory_status,
):
    flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | os.O_NONBLOCK
        | os.O_CLOEXEC
        | os.O_DIRECTORY
    )
    try:
        descriptor = os.open(basename, flags, dir_fd=directory_descriptor)
    except OSError as error:
        raise _ContractError("declared scratch directory open failed") from error
    try:
        before = os.fstat(descriptor)
        entry_before = os.stat(
            basename,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(before.st_mode)
            or before.st_dev != directory_status.st_dev
            or before.st_uid != directory_status.st_uid
            or before.st_gid != directory_status.st_gid
            or stat.S_IMODE(before.st_mode) != 0o700
            or (entry_before.st_dev, entry_before.st_ino)
            != (before.st_dev, before.st_ino)
            or tuple(os.listdir(descriptor))
        ):
            raise _ContractError("declared scratch directory is rejected")
        after = os.fstat(descriptor)
        entry_after = os.stat(
            basename,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_uid,
            before.st_gid,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_uid,
            after.st_gid,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        entry_identity = (
            entry_after.st_dev,
            entry_after.st_ino,
            entry_after.st_mode,
            entry_after.st_uid,
            entry_after.st_gid,
            entry_after.st_mtime_ns,
            entry_after.st_ctime_ns,
        )
        if (
            identity_after != identity_before
            or entry_identity != identity_before
            or tuple(os.listdir(descriptor))
        ):
            raise _ContractError("declared scratch directory changed")
        return before
    except OSError as error:
        raise _ContractError("declared scratch directory audit failed") from error
    finally:
        os.close(descriptor)


def ingest_worker_output(layout, *, maximum_bytes, declared_scratch=()):
    """Ingest one canonical result through the retained output dirfd."""

    limit = _require_nonnegative_integer(maximum_bytes, "maximum_bytes")
    if limit == 0:
        raise _ContractError("maximum_bytes must be positive")
    scratch_declarations = _require_exact_tuple(
        declared_scratch, "declared_scratch"
    )
    normalized_scratch = []
    for index, value in enumerate(scratch_declarations):
        declaration = _exact_keys(
            value,
            ("basename", "kind"),
            f"declared_scratch[{index}]",
        )
        name = declaration["basename"]
        if (
            type(name) is not str
            or not name
            or len(name.encode("utf-8")) > 255
            or "\x00" in name
            or name == "result.json"
            or "/" in name
            or name in {".", ".."}
        ):
            raise _ContractError("declared scratch basename is forbidden")
        kind = declaration["kind"]
        if kind not in {"regular", "directory"}:
            raise _ContractError("declared scratch kind is unknown")
        normalized_scratch.append((name, kind))
    scratch_names = tuple(name for name, _kind in normalized_scratch)
    if len(set(scratch_names)) != len(scratch_names):
        raise _ContractError("declared scratch basename is duplicated")

    directory_descriptor, directory_status = (
        _task11_output_directory_status(layout)
    )
    try:
        entries_before = tuple(sorted(os.listdir(directory_descriptor)))
    except OSError as error:
        raise _ContractError("worker output entries are unavailable") from error
    expected_entries = tuple(sorted(("result.json", *scratch_names)))
    if entries_before != expected_entries:
        raise _ContractError("worker output entry set is not exact")

    result_bytes, _result_status = _task11_read_output_file(
        directory_descriptor,
        "result.json",
        directory_status=directory_status,
        maximum_bytes=limit,
        expected_mode=0o600,
    )
    try:
        result_text = result_bytes.decode("utf-8", "strict")
        parsed = json.loads(result_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _ContractError("worker result JSON is malformed") from error
    result = _exact_keys(
        parsed,
        (
            "schema_version",
            "adapter_id",
            "request_sha256",
            "capsule_sha256",
            "local_result",
        ),
        "worker result transport",
    )
    if result["schema_version"] != "worker_result_transport_v1":
        raise _ContractError("worker result schema is unknown")
    _identifier(result["adapter_id"], "adapter_id")
    _require_sha256(result["request_sha256"], "request_sha256")
    _require_sha256(result["capsule_sha256"], "capsule_sha256")
    _snapshot_json(result["local_result"], "local_result")
    if _canonical_bytes(result) != result_bytes:
        raise _ContractError("worker result is not canonical JSON")

    scratch_records = []
    regular_snapshots = {"result.json": result_bytes}
    directory_snapshots = {}
    for scratch_name, scratch_kind in normalized_scratch:
        if scratch_kind == "regular":
            scratch_bytes, scratch_status = _task11_read_output_file(
                directory_descriptor,
                scratch_name,
                directory_status=directory_status,
                maximum_bytes=limit,
                expected_mode=0o600,
            )
            scratch_size = scratch_status.st_size
            scratch_sha256 = hashlib.sha256(scratch_bytes).hexdigest()
            regular_snapshots[scratch_name] = scratch_bytes
        else:
            scratch_status = _task11_validate_scratch_directory(
                directory_descriptor,
                scratch_name,
                directory_status=directory_status,
            )
            scratch_size = 0
            scratch_sha256 = None
            directory_snapshots[scratch_name] = (
                scratch_status.st_dev,
                scratch_status.st_ino,
                scratch_status.st_mode,
                scratch_status.st_uid,
                scratch_status.st_gid,
                scratch_status.st_mtime_ns,
                scratch_status.st_ctime_ns,
            )
        scratch_records.append(
            {
                "basename": scratch_name,
                "kind": scratch_kind,
                "size": scratch_size,
                "sha256": scratch_sha256,
            }
        )

    final_descriptor, final_status = _task11_output_directory_status(layout)
    if final_descriptor != directory_descriptor:
        raise _ContractError("worker output directory descriptor changed")
    try:
        entries_after = tuple(sorted(os.listdir(directory_descriptor)))
    except OSError as error:
        raise _ContractError("worker output entries are unavailable") from error
    if (
        entries_after != entries_before
        or (final_status.st_dev, final_status.st_ino)
        != (directory_status.st_dev, directory_status.st_ino)
    ):
        raise _ContractError("worker output changed during ingestion")
    for basename, expected_bytes in regular_snapshots.items():
        final_bytes, _final_file_status = _task11_read_output_file(
            directory_descriptor,
            basename,
            directory_status=directory_status,
            maximum_bytes=limit,
            expected_mode=0o600,
        )
        if final_bytes != expected_bytes:
            raise _ContractError("worker output file changed after ingestion")
    for basename, expected_identity in directory_snapshots.items():
        final_scratch_status = _task11_validate_scratch_directory(
            directory_descriptor,
            basename,
            directory_status=directory_status,
        )
        final_identity = (
            final_scratch_status.st_dev,
            final_scratch_status.st_ino,
            final_scratch_status.st_mode,
            final_scratch_status.st_uid,
            final_scratch_status.st_gid,
            final_scratch_status.st_mtime_ns,
            final_scratch_status.st_ctime_ns,
        )
        if final_identity != expected_identity:
            raise _ContractError(
                "declared scratch directory changed after ingestion"
            )
    final_descriptor, final_status = _task11_output_directory_status(layout)
    try:
        final_entries = tuple(sorted(os.listdir(final_descriptor)))
    except OSError as error:
        raise _ContractError("worker output entries are unavailable") from error
    if (
        final_descriptor != directory_descriptor
        or final_entries != entries_before
        or (final_status.st_dev, final_status.st_ino)
        != (directory_status.st_dev, directory_status.st_ino)
    ):
        raise _ContractError("worker output changed after final ingestion audit")
    return _snapshot_json(
        {
            "result": result,
            "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
            "scratch_entries": tuple(scratch_records),
        },
        "ingested worker output",
    )


_TASK11_TRACE_BYTES_LIMIT = 16 * 1024 * 1024
_TASK11_TRACE_LINE_LIMIT = 65536
_TASK11_TRACE_RECORD_LIMIT = 65536
_TASK11_FILE_SYSCALLS = frozenset(
    {
        "access",
        "faccessat",
        "faccessat2",
        "open",
        "openat",
        "stat",
        "lstat",
        "newfstatat",
        "readlink",
        "readlinkat",
        "unlink",
        "unlinkat",
        "rename",
        "renameat",
        "renameat2",
        "link",
        "linkat",
        "symlink",
        "symlinkat",
        "mkdir",
        "mkdirat",
        "rmdir",
        "chmod",
        "fchmodat",
        "chown",
        "lchown",
        "fchownat",
        "truncate",
        "utime",
        "utimes",
        "utimensat",
    }
)
_TASK11_NETWORK_SYSCALLS = frozenset(
    {
        "socket",
        "socketpair",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "sendto",
        "recvfrom",
        "sendmsg",
        "recvmsg",
        "shutdown",
        "getsockname",
        "getpeername",
        "setsockopt",
        "getsockopt",
    }
)
_TASK11_PROCESS_SYSCALLS = frozenset(
    {"clone", "clone3", "fork", "vfork", "execve", "execveat"}
)
_TASK11_IGNORED_SYSCALLS = frozenset(
    {
        "arch_prctl",
        "capget",
        "capset",
        "chdir",
        "chroot",
        "exit",
        "exit_group",
        "getcwd",
        "prctl",
    }
)
_TASK11_WRITE_FILE_SYSCALLS = frozenset(
    {
        "unlink",
        "unlinkat",
        "rename",
        "renameat",
        "renameat2",
        "link",
        "linkat",
        "symlink",
        "symlinkat",
        "mkdir",
        "mkdirat",
        "rmdir",
        "chmod",
        "fchmodat",
        "chown",
        "lchown",
        "fchownat",
        "truncate",
        "utime",
        "utimes",
        "utimensat",
    }
)
_TASK11_TRACE_ACCESS_KEYS = (
    "sequence",
    "pid",
    "syscall",
    "access_kind",
    "operation",
    "logical_path",
    "path_sha256",
    "succeeded",
    "allowed",
    "reason_code",
)
_TASK11_ALLOWED_REASON_CODES = frozenset(
    {
        "allowed_output_write",
        "allowed_request_read",
        "allowed_manifest_read",
        "allowed_runtime_lookup_miss",
    }
)
_TASK11_DENIED_REASON_CODES = frozenset(
    {
        "post_launch_exec",
        "post_launch_process_creation",
        "network_forbidden",
        "entropy_forbidden",
        "parent_traversal_forbidden",
        "undeclared_write",
        "undeclared_native_library",
        "undeclared_read",
        "resolved_path_changed",
    }
)


def _task11_validate_access_record_semantics(record):
    syscall_name = record["syscall"]
    if syscall_name in _TASK11_FILE_SYSCALLS:
        expected_kind = "file"
    elif syscall_name in _TASK11_NETWORK_SYSCALLS:
        expected_kind = "network"
    elif syscall_name == "getrandom":
        expected_kind = "entropy"
    elif syscall_name in _TASK11_PROCESS_SYSCALLS:
        expected_kind = "process"
    else:
        raise _ContractError("trace record syscall class is unknown")
    if record["access_kind"] != expected_kind:
        raise _ContractError("trace record syscall kind is contradictory")

    if expected_kind in {"network", "entropy"}:
        expected_operation = "attempt"
    elif expected_kind == "process":
        expected_operation = (
            "execute"
            if syscall_name in {"execve", "execveat"}
            else "create"
        )
    else:
        expected_operation = record["operation"]
        if expected_operation not in {"read", "write"}:
            raise _ContractError("trace file operation is unknown")
    if record["operation"] != expected_operation:
        raise _ContractError("trace record operation is contradictory")

    reason_code = record["reason_code"]
    expected_allowed = reason_code in _TASK11_ALLOWED_REASON_CODES
    if (
        reason_code
        not in _TASK11_ALLOWED_REASON_CODES | _TASK11_DENIED_REASON_CODES
        or record["allowed"] is not expected_allowed
    ):
        raise _ContractError("trace record reason is contradictory")
    if (
        (expected_kind == "network" and reason_code != "network_forbidden")
        or (expected_kind == "entropy" and reason_code != "entropy_forbidden")
        or (
            expected_kind == "process"
            and record["operation"] == "execute"
            and reason_code != "post_launch_exec"
        )
        or (
            expected_kind == "process"
            and record["operation"] == "create"
            and reason_code != "post_launch_process_creation"
        )
        or (
            expected_kind == "file"
            and reason_code
            in {
                "network_forbidden",
                "entropy_forbidden",
                "post_launch_exec",
                "post_launch_process_creation",
            }
        )
    ):
        raise _ContractError("trace record reason class is contradictory")
    logical_path = record["logical_path"]
    if logical_path.startswith("/"):
        expected_path_sha256 = hashlib.sha256(
            logical_path.encode("utf-8")
        ).hexdigest()
        if record["path_sha256"] != expected_path_sha256:
            raise _ContractError("trace record path hash is contradictory")
    elif expected_kind == "network" or expected_kind == "entropy":
        if record["path_sha256"] != hashlib.sha256(
            syscall_name.encode("utf-8")
        ).hexdigest():
            raise _ContractError("trace record operation hash is contradictory")
    elif expected_kind == "process" and record["operation"] == "create":
        if (
            logical_path != "<process>"
            or record["path_sha256"]
            != hashlib.sha256(b"<process>").hexdigest()
        ):
            raise _ContractError("trace process record is contradictory")

    if reason_code == "allowed_request_read" and (
        logical_path != "/input/request.json"
        or record["operation"] != "read"
    ):
        raise _ContractError("trace request-read reason is contradictory")
    if reason_code == "allowed_output_write" and (
        logical_path != "/output/result.json"
        or record["operation"] != "write"
        or syscall_name not in {"open", "openat"}
    ):
        raise _ContractError("trace output-write reason is contradictory")
    if reason_code == "allowed_runtime_lookup_miss" and (
        not logical_path.startswith("/runtime/")
        or record["operation"] != "read"
        or record["succeeded"] is not False
    ):
        raise _ContractError("trace runtime-miss reason is contradictory")
    if reason_code == "allowed_manifest_read" and (
        expected_kind != "file"
        or record["operation"] != "read"
        or logical_path == "/input/request.json"
        or not any(
            logical_path == root or logical_path.startswith(root + "/")
            for root in ("/runtime", "/adapter", "/input", "/output")
        )
    ):
        raise _ContractError("trace manifest-read reason is contradictory")


def _task11_split_trace_arguments(value):
    arguments = []
    start = 0
    depth = 0
    quote = False
    escaped = False
    for index, character in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = False
            continue
        if character == '"':
            quote = True
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
            if depth < 0:
                raise _ContractError("strace argument nesting is malformed")
        elif character == "," and depth == 0:
            arguments.append(value[start:index].strip())
            start = index + 1
    if quote or escaped or depth != 0:
        raise _ContractError("strace argument syntax is incomplete")
    arguments.append(value[start:].strip())
    return tuple(arguments)


def _task11_trace_string(value, field_name):
    if not value.startswith('"'):
        raise _ContractError(f"strace {field_name} is not a quoted path")
    if value.endswith("...") or re.search(r'"\.\.\.(?:,|$)', value):
        raise _ContractError(f"strace {field_name} is truncated")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise _ContractError(f"strace {field_name} is malformed") from error
    if type(decoded) is not str or "\x00" in decoded:
        raise _ContractError(f"strace {field_name} is malformed")
    return decoded


def _task11_normalize_logical_path(path):
    if type(path) is not str or not path.startswith("/") or "\x00" in path:
        raise _ContractError("strace path is not absolute after resolution")
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        raise _ContractError("strace path normalization escaped root")
    return normalized


def _task11_dirfd_path(value):
    if value == "AT_FDCWD":
        return "/"
    match = re.fullmatch(r"[0-9]+<([^<>]+)>", value)
    if match is None:
        raise _ContractError("strace directory FD is unresolved")
    normalized = _task11_normalize_logical_path(match.group(1))
    marker = "/supervisor/private-root"
    marker_index = normalized.rfind(marker)
    if marker_index >= 0:
        logical_path = normalized[marker_index + len(marker):]
        return logical_path or "/"
    return normalized


def _task11_resolve_trace_path(raw_path, dirfd=None):
    if raw_path.startswith("/"):
        return _task11_normalize_logical_path(raw_path)
    base = "/" if dirfd is None else _task11_dirfd_path(dirfd)
    return _task11_normalize_logical_path(posixpath.join(base, raw_path))


def _task11_file_paths(syscall_name, arguments):
    if syscall_name in {"open", "access", "stat", "lstat", "readlink",
                        "unlink", "mkdir", "rmdir", "chmod", "chown",
                        "lchown", "truncate", "utime", "utimes"}:
        return (
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[0], "path")
            ),
        )
    if syscall_name in {"openat", "faccessat", "faccessat2", "newfstatat",
                        "readlinkat", "unlinkat", "mkdirat", "fchmodat",
                        "fchownat", "utimensat"}:
        return (
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[1], "path"), arguments[0]
            ),
        )
    if syscall_name in {"rename", "link"}:
        return tuple(
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[index], "path")
            )
            for index in (0, 1)
        )
    if syscall_name in {"renameat", "renameat2", "linkat"}:
        return tuple(
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[path_index], "path"),
                arguments[fd_index],
            )
            for fd_index, path_index in ((0, 1), (2, 3))
        )
    if syscall_name == "symlink":
        return (
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[1], "path")
            ),
        )
    if syscall_name == "symlinkat":
        return (
            _task11_resolve_trace_path(
                _task11_trace_string(arguments[2], "path"), arguments[1]
            ),
        )
    raise _ContractError("strace file syscall is unsupported")


def _task11_trace_operation(syscall_name, arguments):
    if syscall_name in _TASK11_WRITE_FILE_SYSCALLS:
        return "write"
    if syscall_name in {"open", "openat"}:
        flags_index = 1 if syscall_name == "open" else 2
        if len(arguments) <= flags_index:
            raise _ContractError("strace open flags are missing")
        flags = arguments[flags_index]
        if any(
            marker in flags
            for marker in (
                "O_WRONLY",
                "O_RDWR",
                "O_CREAT",
                "O_TRUNC",
                "O_APPEND",
                "O_TMPFILE",
            )
        ):
            return "write"
    return "read"


def _task11_trace_has_parent_traversal(arguments):
    for argument in arguments:
        if not argument.startswith('"'):
            continue
        try:
            value = json.loads(argument)
        except json.JSONDecodeError:
            continue
        if type(value) is str and ".." in PurePosixPath(value).parts:
            return True
    return False


def _task11_path_class(path):
    for root in ("/runtime", "/adapter", "/input", "/output"):
        if path == root or path.startswith(root + "/"):
            return path
    return "<outside-private-root>"


def _task11_access_decision(
    path,
    operation,
    succeeded,
    manifest_paths,
    manifest_directories,
    *,
    syscall_name,
    parent_traversal,
):
    if parent_traversal:
        return False, "parent_traversal_forbidden"
    if operation == "write":
        if (
            path == "/output/result.json"
            and syscall_name in {"open", "openat"}
        ):
            return True, "allowed_output_write"
        return False, "undeclared_write"
    if path == "/input/request.json":
        return True, "allowed_request_read"
    if path in manifest_paths or path in manifest_directories:
        return True, "allowed_manifest_read"
    if path == "/runtime" or path.startswith("/runtime/"):
        if not succeeded:
            basename = PurePosixPath(path).name
            if basename.startswith("lib") and ".so" in basename:
                return False, "undeclared_native_library"
            return True, "allowed_runtime_lookup_miss"
    return False, "undeclared_read"


def _task11_complete_trace_lines(text):
    completed = []
    unfinished = {}
    for raw_line in text.splitlines():
        if not raw_line or len(raw_line.encode("utf-8")) > _TASK11_TRACE_LINE_LIMIT:
            raise _ContractError("strace line is empty or oversized")
        unfinished_match = re.fullmatch(
            r"([1-9][0-9]*) ([a-z][a-z0-9_]*)\((.*) <unfinished \.\.\.>",
            raw_line,
        )
        if unfinished_match is not None:
            pid = int(unfinished_match.group(1))
            if pid in unfinished:
                raise _ContractError("strace PID has nested unfinished calls")
            unfinished[pid] = (
                unfinished_match.group(2),
                unfinished_match.group(2) + "(" + unfinished_match.group(3),
            )
            continue
        resumed_match = re.fullmatch(
            r"([1-9][0-9]*) <\.\.\. ([a-z][a-z0-9_]*) resumed>(.*)",
            raw_line,
        )
        if resumed_match is not None:
            pid = int(resumed_match.group(1))
            pending = unfinished.pop(pid, None)
            if pending is None or pending[0] != resumed_match.group(2):
                raise _ContractError("strace continuation pair is malformed")
            completed.append(
                f"{pid} {pending[1]}{resumed_match.group(3)}"
            )
            continue
        completed.append(raw_line)
    if unfinished:
        raise _ContractError("strace has unfinished syscalls")
    return tuple(completed)


def _task11_expected_bootstrap_source():
    try:
        launcher_tree = ast.parse(
            emit_tracee_launcher().decode("utf-8", "strict")
        )
    except (SyntaxError, UnicodeDecodeError) as error:
        raise _ContractError("fixed tracee launcher source is malformed") from error
    candidates = []
    for node in launcher_tree.body:
        if (
            type(node) is ast.Assign
            and len(node.targets) == 1
            and type(node.targets[0]) is ast.Name
            and node.targets[0].id == "_BOOTSTRAP"
            and type(node.value) is ast.Constant
            and type(node.value.value) is str
        ):
            candidates.append(node.value.value)
    if len(candidates) != 1 or not candidates[0]:
        raise _ContractError("fixed tracee bootstrap source is not exact")
    return candidates[0]


def evaluate_strace(trace_bytes, mount_manifest):
    """Parse one complete followed-process trace and enforce access policy."""

    if (
        type(trace_bytes) is not bytes
        or not trace_bytes
        or len(trace_bytes) > _TASK11_TRACE_BYTES_LIMIT
        or not trace_bytes.endswith(b"\n")
    ):
        raise _ContractError("strace bytes are missing, oversized, or incomplete")
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    try:
        text = trace_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise _ContractError("strace is not strict UTF-8") from error
    if "\x00" in text:
        raise _ContractError("strace contains NUL")
    lines = _task11_complete_trace_lines(text)
    if not lines or len(lines) > _TASK11_TRACE_RECORD_LIMIT:
        raise _ContractError("strace record count is invalid")

    manifest = _task10_validate_mount_manifest(mount_manifest)
    manifest_paths = {
        row["logical_path"] for row in manifest["mounts"]
    }
    manifest_directories = {"/runtime", "/adapter", "/input", "/output"}
    for path in manifest_paths:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            manifest_directories.add(str(parent))
            if str(parent) == "/":
                break
            parent = parent.parent

    seen_pids = set()
    exited_pids = set()
    child_pids = set()
    isolated_pid = None
    resolved_private_root = None
    request_seen = False
    attempts = []
    violations = []
    sequence = 0
    for line in lines:
        exit_match = re.fullmatch(
            r"([1-9][0-9]*) \+\+\+ exited with ([0-9]+) \+\+\+",
            line,
        )
        if exit_match is not None:
            pid = int(exit_match.group(1))
            seen_pids.add(pid)
            exited_pids.add(pid)
            continue
        if re.fullmatch(r"[1-9][0-9]* --- [A-Z0-9]+ .* ---", line):
            continue
        match = re.fullmatch(
            r"([1-9][0-9]*) ([a-z][a-z0-9_]*)\((.*)\) += (.+)",
            line,
        )
        if match is None:
            raise _ContractError("strace line has an unknown form")
        pid = int(match.group(1))
        syscall_name = match.group(2)
        arguments = _task11_split_trace_arguments(match.group(3))
        result = match.group(4)
        succeeded = not result.startswith("-1 ")
        seen_pids.add(pid)

        if syscall_name == "execve":
            if not arguments:
                raise _ContractError("strace execve path is missing")
            exec_path = _task11_trace_string(arguments[0], "execve path")
            if exec_path == manifest["runtime_interpreter_path"]:
                if isolated_pid is None:
                    if not succeeded or len(arguments) != 3:
                        raise _ContractError(
                            "strace isolated exec is incomplete"
                        )
                    try:
                        exec_argv = json.loads(arguments[1])
                    except json.JSONDecodeError as error:
                        raise _ContractError(
                            "strace isolated exec argv is malformed"
                        ) from error
                    if (
                        type(exec_argv) is not list
                        or len(exec_argv) != 9
                        or exec_argv[:5]
                        != [exec_path, "-I", "-S", "-B", "-c"]
                        or exec_argv[5]
                        != _task11_expected_bootstrap_source()
                        or any(
                            type(value) is not str
                            or not value.isdecimal()
                            or int(value) < 3
                            for value in exec_argv[6:8]
                        )
                        or exec_argv[6] == exec_argv[7]
                        or type(exec_argv[8]) is not str
                        or not exec_argv[8].startswith("/")
                        or PurePosixPath(exec_argv[8]).name
                        != "host-canary-denied"
                        or posixpath.normpath(exec_argv[8]) != exec_argv[8]
                    ):
                        raise _ContractError(
                            "strace isolated exec flags are not exact"
                        )
                    isolated_pid = pid
                    continue
                access_allowed = False
                reason_code = "post_launch_exec"
            elif isolated_pid is None:
                continue
            else:
                access_allowed = False
                reason_code = "post_launch_exec"
            record = {
                "sequence": sequence,
                "pid": pid,
                "syscall": syscall_name,
                "access_kind": "process",
                "operation": "execute",
                "logical_path": _task11_path_class(exec_path),
                "path_sha256": hashlib.sha256(exec_path.encode()).hexdigest(),
                "succeeded": succeeded,
                "allowed": access_allowed,
                "reason_code": reason_code,
            }
            sequence += 1
            attempts.append(record)
            violations.append(record)
            continue

        if syscall_name in {"clone", "clone3", "fork", "vfork"}:
            child_match = re.match(r"([1-9][0-9]*)(?:<.*>)?$", result)
            if child_match is not None:
                child_pids.add(int(child_match.group(1)))
            if isolated_pid is None:
                continue
            record = {
                "sequence": sequence,
                "pid": pid,
                "syscall": syscall_name,
                "access_kind": "process",
                "operation": "create",
                "logical_path": "<process>",
                "path_sha256": hashlib.sha256(b"<process>").hexdigest(),
                "succeeded": succeeded,
                "allowed": False,
                "reason_code": "post_launch_process_creation",
            }
            sequence += 1
            attempts.append(record)
            violations.append(record)
            continue

        if syscall_name in _TASK11_NETWORK_SYSCALLS or syscall_name == "getrandom":
            if isolated_pid is None:
                continue
            record = {
                "sequence": sequence,
                "pid": pid,
                "syscall": syscall_name,
                "access_kind": "network" if syscall_name != "getrandom" else "entropy",
                "operation": "attempt",
                "logical_path": "<network>" if syscall_name != "getrandom" else "<entropy>",
                "path_sha256": hashlib.sha256(syscall_name.encode()).hexdigest(),
                "succeeded": succeeded,
                "allowed": False,
                "reason_code": "network_forbidden" if syscall_name != "getrandom" else "entropy_forbidden",
            }
            sequence += 1
            attempts.append(record)
            violations.append(record)
            continue

        if syscall_name in _TASK11_FILE_SYSCALLS:
            try:
                paths = _task11_file_paths(syscall_name, arguments)
                operation = _task11_trace_operation(
                    syscall_name, arguments
                )
            except IndexError as error:
                raise _ContractError(
                    "strace file syscall arguments are missing"
                ) from error
            if isolated_pid is None:
                continue
            if not request_seen and "/input/request.json" not in paths:
                continue
            if "/input/request.json" in paths:
                request_seen = True
            resolved_open_matches = True
            if succeeded and syscall_name in {"open", "openat"}:
                resolved_match = re.fullmatch(r"[0-9]+<([^<>]+)>", result)
                if resolved_match is None:
                    raise _ContractError(
                        "strace successful open lacks a resolved path"
                    )
                resolved_path = _task11_normalize_logical_path(
                    resolved_match.group(1)
                )
                if len(paths) != 1:
                    raise _ContractError(
                        "strace successful open resolved path changed"
                    )
                logical_path = paths[0]
                if resolved_path != logical_path:
                    marker = "/supervisor/private-root"
                    marker_index = resolved_path.rfind(marker)
                    if marker_index < 0:
                        raise _ContractError(
                            "strace successful open escaped the private root"
                        )
                    candidate_root = resolved_path[
                        : marker_index + len(marker)
                    ]
                    if (
                        (
                            resolved_private_root is not None
                            and candidate_root != resolved_private_root
                        )
                    ):
                        raise _ContractError(
                            "strace successful open private root changed"
                        )
                    resolved_private_root = candidate_root
                    resolved_logical = resolved_path[len(candidate_root):]
                    if not resolved_logical:
                        resolved_logical = "/"
                    resolved_open_matches = resolved_logical == logical_path
            parent_traversal = _task11_trace_has_parent_traversal(
                arguments
            )
            for path in paths:
                allowed, reason_code = _task11_access_decision(
                    path,
                    operation,
                    succeeded,
                    manifest_paths,
                    manifest_directories,
                    syscall_name=syscall_name,
                    parent_traversal=parent_traversal,
                )
                if not resolved_open_matches:
                    allowed = False
                    reason_code = "resolved_path_changed"
                record = {
                    "sequence": sequence,
                    "pid": pid,
                    "syscall": syscall_name,
                    "access_kind": "file",
                    "operation": operation,
                    "logical_path": _task11_path_class(path),
                    "path_sha256": hashlib.sha256(path.encode()).hexdigest(),
                    "succeeded": succeeded,
                    "allowed": allowed,
                    "reason_code": reason_code,
                }
                sequence += 1
                attempts.append(record)
                if not allowed:
                    violations.append(record)
            continue
        if syscall_name not in _TASK11_IGNORED_SYSCALLS:
            raise _ContractError("strace contains an unknown syscall")

    if isolated_pid is None or not request_seen:
        raise _ContractError("strace lacks the isolated worker or request access")
    if child_pids - seen_pids:
        raise _ContractError("strace is missing a child PID log")
    if seen_pids - exited_pids:
        raise _ContractError("strace is missing a PID exit record")
    body = {
        "schema_version": "trace_policy_report_v1",
        "trace_sha256": trace_sha256,
        "attempted_accesses": tuple(attempts),
        "violations": tuple(violations),
        "passed": not violations,
    }
    return TracePolicyReport(
        **body,
        report_sha256=_canonical_sha256(body),
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
        node["source_span_sha256"]
        for node in adapter.nodes
        if node["node_kind"] != "import"
    }
    oracle_spans = {
        node["source_span_sha256"]
        for node in oracle.nodes
        if node["node_kind"] != "import"
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
_INFRASTRUCTURE_STRONG_SCIENTIFIC_TOKENS = frozenset(
    {
        "answer",
        "coupling",
        "energy",
        "equation",
        "exchange",
        "formula",
        "hamiltonian",
        "magnetization",
        "phase",
        "spectrum",
    }
)
_INFRASTRUCTURE_ARITHMETIC_SCIENTIFIC_TOKENS = frozenset(
    set(_INFRASTRUCTURE_STRONG_SCIENTIFIC_TOKENS)
    | {"model", "observable", "scientific"}
)


def _lexical_tokens(value: str) -> set[str]:
    separated = _CASE_BOUNDARY_PATTERN.sub(r"\1 \2", value)
    return {
        token.lower()
        for token in _ASCII_ALNUM_TOKEN_PATTERN.findall(
            separated.replace("_", " ")
        )
    }


def _infrastructure_name_tokens(qualified_name: str) -> set[str]:
    leaf = qualified_name.rsplit(".", 1)[-1]
    return _lexical_tokens(leaf)


def _is_method_result_derivation(tokens: set[str]) -> bool:
    if not {"method", "result"} <= tokens:
        return False
    if "specific" in tokens:
        return True
    morphology = {
        "calculat": frozenset({"e", "es", "ed", "ing", "ion", "ions"}),
        "comput": frozenset(
            {"e", "es", "ed", "ing", "ation", "ations"}
        ),
        "deriv": frozenset(
            {"e", "es", "ed", "ing", "ation", "ations"}
        ),
        "evaluat": frozenset(
            {"e", "es", "ed", "ing", "ion", "ions"}
        ),
    }
    return any(
        token == stem + suffix
        for token in tokens
        for stem, suffixes in morphology.items()
        for suffix in suffixes
    )


def _reject_scientific_infrastructure_nodes(
    nodes: tuple[_FrozenJsonObject, ...]
) -> None:
    expected = set(_EXPECTED_INFRASTRUCTURE_ROOTS)
    for node in nodes:
        qualified_name = node["qualified_name"]
        if qualified_name in expected:
            continue
        tokens = _infrastructure_name_tokens(qualified_name)
        if (
            tokens & _INFRASTRUCTURE_STRONG_SCIENTIFIC_TOKENS
            or _is_method_result_derivation(tokens)
            or (
                "root" in tokens
                and bool(tokens & {"caller", "designated", "extra"})
            )
        ):
            raise _ContractError(
                "infrastructure closure contains a scientific or result "
                "derivation helper or undeclared root"
            )


def _docstring_value_ids(node: ast.AST) -> set[int]:
    docstrings = set()
    for candidate in ast.walk(node):
        if not isinstance(
            candidate,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        if not candidate.body:
            continue
        first = candidate.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and type(first.value.value) is str
        ):
            docstrings.add(id(first.value))
    return docstrings


def _assignment_parts(
    node: ast.AST,
) -> tuple[tuple[ast.expr, ...], ast.expr] | None:
    if isinstance(node, ast.Assign):
        return tuple(node.targets), node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return (node.target,), node.value
    if isinstance(node, ast.NamedExpr):
        return (node.target,), node.value
    if isinstance(node, ast.AugAssign):
        return (node.target,), node.value
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return (node.target,), node.iter
    if isinstance(node, ast.withitem) and node.optional_vars is not None:
        return (node.optional_vars,), node.context_expr
    return None


def _scope_assignments(node: ast.AST) -> tuple[ast.AST, ...]:
    assignments = []
    pending = [node]
    scope_boundaries = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Lambda,
    )
    while pending:
        candidate = pending.pop()
        if candidate is not node and isinstance(candidate, scope_boundaries):
            continue
        if _assignment_parts(candidate) is not None:
            assignments.append(candidate)
        pending.extend(reversed(tuple(ast.iter_child_nodes(candidate))))
    assignments.sort(
        key=lambda candidate: (
            getattr(candidate, "lineno", -1),
            getattr(candidate, "col_offset", -1),
        )
    )
    return tuple(assignments)


def _literal_may_flow_expression(
    node: ast.AST,
    literal_names: set[str],
    literal_types: tuple[type, ...],
    *,
    allow_signed_numeric: bool,
) -> bool:
    values: dict[int, bool] = {}
    pending: list[tuple[ast.AST, bool]] = [(node, False)]
    visited = 0
    while pending:
        candidate, expanded = pending.pop()
        if not expanded:
            visited += 1
            if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
                raise _ContractError(
                    "infrastructure literal provenance exceeds its bound"
                )
            pending.append((candidate, True))
            pending.extend(
                (child, False)
                for child in reversed(_literal_flow_operands(
                    candidate, allow_signed_numeric=allow_signed_numeric
                ))
            )
            continue
        if isinstance(candidate, ast.Constant):
            values[id(candidate)] = type(candidate.value) in literal_types
        elif isinstance(candidate, ast.Name):
            values[id(candidate)] = candidate.id in literal_names
        else:
            values[id(candidate)] = any(
                values.get(id(child), False)
                for child in _literal_flow_operands(
                    candidate, allow_signed_numeric=allow_signed_numeric
                )
            )
    return values.get(id(node), False)


_INFRASTRUCTURE_AST_NODE_LIMIT = 16_384
_INFRASTRUCTURE_DEF_USE_EDGE_LIMIT = 32_768
_INFRASTRUCTURE_ANALYSIS_STATE_LIMIT = 8_192
_INFRASTRUCTURE_ANALYSIS_STEP_LIMIT = 131_072


def _literal_flow_operands(
    node: ast.AST, *, allow_signed_numeric: bool
) -> tuple[ast.AST, ...]:
    if (
        allow_signed_numeric
        and isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
    ):
        return (node.operand,)
    if isinstance(node, ast.BinOp):
        return (node.left, node.right)
    if isinstance(node, ast.IfExp):
        return (node.body, node.orelse)
    if isinstance(node, ast.BoolOp):
        return tuple(node.values)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return tuple(node.elts)
    if isinstance(node, ast.Dict):
        return tuple(key for key in node.keys if key is not None) + tuple(
            node.values
        )
    if isinstance(node, ast.Call):
        return (node.func,) + tuple(node.args) + tuple(
            keyword.value for keyword in node.keywords
        )
    if isinstance(node, ast.Attribute):
        return (node.value,)
    if isinstance(node, ast.Subscript):
        return (node.value,)
    if isinstance(node, (ast.NamedExpr, ast.Starred)):
        return (node.value,)
    return ()


def _literal_bytes_expression(
    node: ast.AST, literal_names: set[str]
) -> bool:
    return _literal_may_flow_expression(
        node,
        literal_names,
        (bytes,),
        allow_signed_numeric=False,
    )


def _assigned_local_names(targets: tuple[ast.expr, ...]) -> set[str]:
    return {
        candidate.id
        for target in targets
        for candidate in ast.walk(target)
        if isinstance(candidate, ast.Name)
        and isinstance(candidate.ctx, ast.Store)
    }


def _literal_provenance_names(
    assignments: tuple[ast.AST, ...],
    expression_test: Callable[[ast.AST, set[str]], bool],
) -> set[str]:
    literal_names: set[str] = set()
    reverse_uses: dict[str, set[int]] = {}
    parts_by_index = []
    edge_count = 0
    for index, assignment in enumerate(assignments):
        parts = _assignment_parts(assignment)
        parts_by_index.append(parts)
        if parts is None:
            continue
        for candidate in ast.walk(parts[1]):
            if not (
                isinstance(candidate, ast.Name)
                and isinstance(candidate.ctx, ast.Load)
            ):
                continue
            reverse_uses.setdefault(candidate.id, set()).add(index)
            edge_count += 1
            if edge_count > _INFRASTRUCTURE_DEF_USE_EDGE_LIMIT:
                raise _ContractError(
                    "infrastructure literal provenance exceeds its bound"
                )
    pending = deque(range(len(assignments)))
    queued = set(pending)
    steps = 0
    while pending:
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure literal provenance exceeds its bound"
            )
        index = pending.popleft()
        queued.discard(index)
        parts = parts_by_index[index]
        if parts is None:
            continue
        targets, value = parts
        if not expression_test(value, literal_names):
            continue
        new_names = _assigned_local_names(targets) - literal_names
        literal_names.update(new_names)
        for name in new_names:
            for dependent in reverse_uses.get(name, ()):
                if dependent not in queued:
                    pending.append(dependent)
                    queued.add(dependent)
    return literal_names


def _target_tokens(target: ast.expr) -> set[str]:
    return {
        token
        for candidate in ast.walk(target)
        if isinstance(candidate, (ast.Name, ast.Attribute))
        for token in _lexical_tokens(
            candidate.id
            if isinstance(candidate, ast.Name)
            else candidate.attr
        )
    }


def _is_policy_literal_target(targets: tuple[ast.expr, ...]) -> bool:
    return any("policy" in _target_tokens(target) for target in targets)


def _scope_has_literal_policy_bytes_flow(node: ast.AST) -> bool:
    assignments = _scope_assignments(node)
    literal_names = _literal_provenance_names(
        assignments, _literal_bytes_expression
    )
    for assignment in assignments:
        parts = _assignment_parts(assignment)
        if parts is None:
            continue
        targets, value = parts
        if _is_policy_literal_target(targets) and _literal_bytes_expression(
            value, literal_names
        ):
            return True
    return False


def _assignment_scopes(node: ast.AST) -> tuple[ast.AST, ...]:
    scopes = [node]
    if isinstance(node, ast.ClassDef):
        scopes.extend(
            statement
            for statement in node.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    return tuple(scopes)


def _has_literal_policy_bytes_flow(node: ast.AST) -> bool:
    return any(
        _scope_has_literal_policy_bytes_flow(scope)
        for scope in _assignment_scopes(node)
    )


class _InfrastructureNumericProvenance(IntFlag):
    NONE = 0
    INPUT_OR_POLICY = 1
    NUMERIC_LITERAL = 2
    STRUCTURAL_CARDINALITY = 4
    STRUCTURAL_INDEX_OR_BOUND = 8
    LITERAL_DERIVED_ARITHMETIC = 16
    UNKNOWN = 32
    CALLABLE_TRANSPORT = 64
    COMPARISON_RESULT = 128
    FROZEN_THRESHOLD_COMPARISON = 256
    UNAPPROVED_COMPARISON = 512


_NUMERIC_LITERAL_PROVENANCE = (
    _InfrastructureNumericProvenance.NUMERIC_LITERAL
    | _InfrastructureNumericProvenance.LITERAL_DERIVED_ARITHMETIC
)
_NUMERIC_STRUCTURAL_PROVENANCE = (
    _InfrastructureNumericProvenance.STRUCTURAL_CARDINALITY
    | _InfrastructureNumericProvenance.STRUCTURAL_INDEX_OR_BOUND
)
_INFRASTRUCTURE_NUMERIC_PERMISSIONS = frozenset(
    {
        ("contract_validation", "builtins.len", "call_result"),
        ("contract_validation", "builtins.range", "iterator_result"),
        (
            "contract_validation",
            "builtins.enumerate",
            "iterator_result",
        ),
        ("contract_validation", "ast.BinOp", "cardinality_offset"),
        ("contract_validation", "ast.Subscript", "index"),
        ("contract_validation", "ast.Slice", "bound"),
        ("contract_validation", "ast.Name", "literal_control"),
        (
            "contract_validation",
            "builtins.len",
            "control_comparison",
        ),
        (
            "contract_validation",
            "builtins.len",
            "if_test",
        ),
        (
            "contract_validation",
            "identity.none",
            "if_expression_test",
        ),
        (
            "contract_validation",
            "structural_cardinality",
            "return",
        ),
        (
            "contract_validation",
            "attribute_callable",
            "call_result",
        ),
        (
            "event_and_counterfactual_transport",
            "occurrence_counter",
            "return",
        ),
        (
            "proof_adjudication_transport",
            "frozen_policy.threshold",
            "returned_comparison",
        ),
        (
            "proof_adjudication_transport",
            "frozen_policy.threshold",
            "if_test",
        ),
        (
            "proof_adjudication_transport",
            "frozen_policy.threshold",
            "if_expression_test",
        ),
    }
)


def _numeric_permission(purpose: str, binding: str, position: str) -> bool:
    return (
        purpose,
        binding,
        position,
    ) in _INFRASTRUCTURE_NUMERIC_PERMISSIONS


_NumericAnalysisKey = tuple[
    str,
    str,
    tuple[int, ...],
    tuple[tuple[str, int], ...],
]


def _infrastructure_reaching_purposes(
    resolved: Mapping[str, _ResolvedAstNode],
) -> dict[str, frozenset[str]]:
    reaching: dict[str, set[str]] = {
        qualified_name: set() for qualified_name in resolved
    }
    pending = deque()
    for root, purpose in sorted(_INFRASTRUCTURE_PURPOSE_BINDINGS.items()):
        if root not in resolved:
            raise _ContractError(
                "infrastructure numeric provenance is missing a root"
            )
        reaching[root].add(purpose)
        pending.append((root, purpose))
    steps = 0
    while pending:
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        source, purpose = pending.popleft()
        for destination in resolved[source].dependencies:
            if destination not in resolved:
                continue
            if purpose in reaching[destination]:
                continue
            reaching[destination].add(purpose)
            pending.append((destination, purpose))
    return {
        name: frozenset(purposes)
        for name, purposes in reaching.items()
    }


def _numeric_state_has_literal(
    state: _InfrastructureNumericProvenance,
) -> bool:
    return bool(state & _NUMERIC_LITERAL_PROVENANCE)


def _numeric_state_is_safe_structural(
    state: _InfrastructureNumericProvenance,
    purpose: str,
    *,
    binding: str,
) -> bool:
    allowed = (
        _NUMERIC_STRUCTURAL_PROVENANCE
        | _InfrastructureNumericProvenance.LITERAL_DERIVED_ARITHMETIC
    )
    return (
        bool(state & _NUMERIC_STRUCTURAL_PROVENANCE)
        and not bool(state & ~allowed)
        and _numeric_permission(purpose, binding, "return")
    )


def _bounded_infrastructure_ast_nodes(node: ast.AST) -> tuple[ast.AST, ...]:
    nodes = []
    pending = [node]
    while pending:
        candidate = pending.pop()
        nodes.append(candidate)
        if len(nodes) > _INFRASTRUCTURE_AST_NODE_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        pending.extend(reversed(tuple(ast.iter_child_nodes(candidate))))
    return tuple(nodes)


def _numeric_expression_state(
    node: ast.AST,
    names: Mapping[str, _InfrastructureNumericProvenance],
    *,
    purpose: str,
    local_names: frozenset[str],
    global_names: frozenset[str] = frozenset(),
    project_functions: Mapping[
        str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]
    ] | None = None,
    function_global_states: Mapping[
        str, Mapping[str, _InfrastructureNumericProvenance]
    ] | None = None,
    function_global_names: Mapping[str, frozenset[str]] | None = None,
    function_bindings: Mapping[
        str,
        Mapping[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]],
    ] | None = None,
    approved_project_classes: frozenset[str] = frozenset(),
    class_attribute_states: Mapping[
        str, _InfrastructureNumericProvenance
    ] | None = None,
    class_receiver_names: frozenset[str] = frozenset(),
    frozen_threshold_names: frozenset[str] = frozenset(),
    evaluated_project_calls: set[int] | None = None,
    summaries: Mapping[
        _NumericAnalysisKey, _InfrastructureNumericProvenance
    ] | None = None,
    requested: set[_NumericAnalysisKey] | None = None,
) -> _InfrastructureNumericProvenance:
    if project_functions is None:
        project_functions = {}
    if summaries is None:
        summaries = {}
    if function_global_states is None:
        function_global_states = {}
    if function_global_names is None:
        function_global_names = {}
    if function_bindings is None:
        function_bindings = {}
    if class_attribute_states is None:
        class_attribute_states = {}
    states: dict[int, _InfrastructureNumericProvenance] = {}
    pending: list[tuple[ast.AST, bool]] = [(node, False)]
    visited = 0
    while pending:
        candidate, expanded = pending.pop()
        if not expanded:
            visited += 1
            if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
                raise _ContractError(
                    "infrastructure numeric provenance exceeds its bound"
                )
            pending.append((candidate, True))
            pending.extend(
                (child, False)
                for child in reversed(tuple(ast.iter_child_nodes(candidate)))
            )
            continue
        child_state = _InfrastructureNumericProvenance.NONE
        for child in ast.iter_child_nodes(candidate):
            child_state |= states.get(
                id(child), _InfrastructureNumericProvenance.NONE
            )
        state = _InfrastructureNumericProvenance.NONE
        if isinstance(candidate, ast.Constant):
            if type(candidate.value) in (int, float, complex):
                state = _InfrastructureNumericProvenance.NUMERIC_LITERAL
        elif isinstance(candidate, ast.Name):
            state = names.get(
                candidate.id, _InfrastructureNumericProvenance.NONE
            )
        elif isinstance(candidate, ast.UnaryOp):
            operand_state = states.get(
                id(candidate.operand), _InfrastructureNumericProvenance.NONE
            )
            state = operand_state
            if isinstance(candidate.op, ast.Not):
                state |= (
                    _InfrastructureNumericProvenance.COMPARISON_RESULT
                    | _InfrastructureNumericProvenance.UNAPPROVED_COMPARISON
                )
            elif (
                isinstance(candidate.op, (ast.UAdd, ast.USub, ast.Invert))
                and operand_state
                & (
                    _InfrastructureNumericProvenance.INPUT_OR_POLICY
                    | _InfrastructureNumericProvenance.UNKNOWN
                )
            ):
                state |= _InfrastructureNumericProvenance.UNKNOWN
        elif isinstance(candidate, ast.BinOp):
            left = states.get(
                id(candidate.left), _InfrastructureNumericProvenance.NONE
            )
            right = states.get(
                id(candidate.right), _InfrastructureNumericProvenance.NONE
            )
            combined = left | right
            structural_offset = (
                isinstance(candidate.op, (ast.Add, ast.Sub))
                and bool(combined & _NUMERIC_STRUCTURAL_PROVENANCE)
                and not bool(
                    combined
                    & (
                        _InfrastructureNumericProvenance.INPUT_OR_POLICY
                        | _InfrastructureNumericProvenance.UNKNOWN
                    )
                )
                and _numeric_permission(
                    purpose, "ast.BinOp", "cardinality_offset"
                )
            )
            if structural_offset:
                state = (
                    combined
                    & ~_InfrastructureNumericProvenance.NUMERIC_LITERAL
                ) | _InfrastructureNumericProvenance.LITERAL_DERIVED_ARITHMETIC
            else:
                state = combined
                if _numeric_state_has_literal(combined):
                    state |= (
                        _InfrastructureNumericProvenance.
                        LITERAL_DERIVED_ARITHMETIC
                    )
                if combined & (
                    _InfrastructureNumericProvenance.INPUT_OR_POLICY
                    | _InfrastructureNumericProvenance.UNKNOWN
                ):
                    state |= _InfrastructureNumericProvenance.UNKNOWN
        elif isinstance(candidate, ast.IfExp):
            state = states.get(
                id(candidate.body), _InfrastructureNumericProvenance.NONE
            ) | states.get(
                id(candidate.orelse), _InfrastructureNumericProvenance.NONE
            )
        elif isinstance(candidate, ast.BoolOp):
            state = child_state
        elif isinstance(candidate, (ast.List, ast.Tuple, ast.Set)):
            state = child_state
        elif isinstance(candidate, ast.Dict):
            state = child_state
        elif isinstance(candidate, ast.Attribute):
            if (
                isinstance(candidate.value, ast.Name)
                and candidate.value.id in class_receiver_names
                and candidate.attr in class_attribute_states
            ):
                state = class_attribute_states[candidate.attr]
            else:
                state = states.get(
                    id(candidate.value),
                    _InfrastructureNumericProvenance.NONE,
                ) | _InfrastructureNumericProvenance.CALLABLE_TRANSPORT
        elif isinstance(candidate, ast.Subscript):
            state = states.get(
                id(candidate.value), _InfrastructureNumericProvenance.NONE
            )
        elif isinstance(candidate, ast.Call):
            function_state = states.get(
                id(candidate.func), _InfrastructureNumericProvenance.NONE
            )
            argument_state = _InfrastructureNumericProvenance.NONE
            for argument in candidate.args:
                argument_state |= states.get(
                    id(argument), _InfrastructureNumericProvenance.NONE
                )
            for keyword in candidate.keywords:
                argument_state |= states.get(
                    id(keyword.value),
                    _InfrastructureNumericProvenance.NONE,
                )
            call_name = (
                candidate.func.id
                if isinstance(candidate.func, ast.Name)
                and candidate.func.id not in local_names
                else None
            )
            project_function = project_functions.get(call_name or "")
            exact_builtin = (
                call_name is not None and call_name not in global_names
            )
            replaces_argument_state = (
                project_function is not None
                or exact_builtin
                and candidate.func.id == "len"
                and _numeric_permission(
                    purpose, "builtins.len", "call_result"
                )
                or exact_builtin
                and candidate.func.id in {"range", "enumerate"}
                and _numeric_permission(
                    purpose,
                    f"builtins.{candidate.func.id}",
                    "iterator_result",
                )
                or call_name in approved_project_classes
            )
            if (
                replaces_argument_state
                and argument_state
                & (
                    _InfrastructureNumericProvenance.COMPARISON_RESULT
                    | _InfrastructureNumericProvenance.
                    UNAPPROVED_COMPARISON
                )
            ):
                raise _ContractError(
                    "infrastructure comparison-bearing call input "
                    "violates its purpose"
                )
            if project_function is not None:
                callee_name, callee_node = project_function
                if evaluated_project_calls is not None:
                    evaluated_project_calls.add(id(candidate))
                key = _numeric_helper_analysis_key(
                    callee_name,
                    callee_node,
                    purpose,
                    tuple(
                        states.get(
                            id(argument),
                            _InfrastructureNumericProvenance.NONE,
                        )
                        for argument in candidate.args
                    ),
                    tuple(
                        (
                            keyword.arg,
                            states.get(
                                id(keyword.value),
                                _InfrastructureNumericProvenance.NONE,
                            ),
                        )
                        for keyword in candidate.keywords
                    ),
                    global_states=function_global_states.get(
                        callee_name, {}
                    ),
                    global_names=function_global_names.get(
                        callee_name, frozenset()
                    ),
                    project_functions=function_bindings.get(
                        callee_name, {}
                    ),
                    summaries=summaries,
                )
                if requested is not None:
                    requested.add(key)
                state = summaries.get(
                    key, _InfrastructureNumericProvenance.NONE
                )
            elif (
                exact_builtin
                and candidate.func.id == "len"
                and _numeric_permission(
                    purpose, "builtins.len", "call_result"
                )
                and not bool(
                    argument_state
                    & (
                        _NUMERIC_LITERAL_PROVENANCE
                        | _InfrastructureNumericProvenance.UNKNOWN
                    )
                )
            ):
                state = (
                    _InfrastructureNumericProvenance.STRUCTURAL_CARDINALITY
                )
            elif (
                exact_builtin
                and candidate.func.id in {"range", "enumerate"}
                and _numeric_permission(
                    purpose,
                    f"builtins.{candidate.func.id}",
                    "iterator_result",
                )
                and not bool(
                    argument_state
                    & _InfrastructureNumericProvenance.UNKNOWN
                )
            ):
                state = (
                    _InfrastructureNumericProvenance.
                    STRUCTURAL_INDEX_OR_BOUND
                )
            elif (
                call_name in approved_project_classes
                and not bool(
                    argument_state
                    & (
                        _NUMERIC_LITERAL_PROVENANCE
                        | _InfrastructureNumericProvenance.UNKNOWN
                    )
                )
            ):
                state = _InfrastructureNumericProvenance.INPUT_OR_POLICY
            elif (
                function_state
                & _InfrastructureNumericProvenance.CALLABLE_TRANSPORT
                and _numeric_permission(
                    purpose, "attribute_callable", "call_result"
                )
                and not bool(
                    (argument_state | function_state)
                    & (
                        _NUMERIC_LITERAL_PROVENANCE
                        | _InfrastructureNumericProvenance.UNKNOWN
                    )
                )
            ):
                state = (
                    function_state
                    & ~_InfrastructureNumericProvenance.CALLABLE_TRANSPORT
                ) | argument_state
            else:
                state = (
                    argument_state
                    | function_state
                    | _InfrastructureNumericProvenance.UNKNOWN
                )
        elif isinstance(candidate, ast.Compare):
            state = (
                child_state
                | _InfrastructureNumericProvenance.COMPARISON_RESULT
            )
            if _is_frozen_threshold_comparison(
                candidate, frozen_threshold_names
            ):
                state |= (
                    _InfrastructureNumericProvenance.
                    FROZEN_THRESHOLD_COMPARISON
                )
            else:
                state |= (
                    _InfrastructureNumericProvenance.
                    UNAPPROVED_COMPARISON
                )
        elif isinstance(candidate, ast.NamedExpr):
            state = states.get(
                id(candidate.value), _InfrastructureNumericProvenance.NONE
            )
        elif isinstance(candidate, ast.Starred):
            state = states.get(
                id(candidate.value), _InfrastructureNumericProvenance.NONE
            ) | _InfrastructureNumericProvenance.UNKNOWN
        else:
            state = child_state
        states[id(candidate)] = state
    return states.get(id(node), _InfrastructureNumericProvenance.NONE)


def _numeric_function_local_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> frozenset[str]:
    names = {
        argument.arg
        for argument in (
            tuple(node.args.posonlyargs)
            + tuple(node.args.args)
            + tuple(node.args.kwonlyargs)
        )
    }
    for argument in (node.args.vararg, node.args.kwarg):
        if argument is not None:
            names.add(argument.arg)
    for candidate in _bounded_infrastructure_ast_nodes(node):
        if isinstance(candidate, ast.Name) and isinstance(
            candidate.ctx, (ast.Store, ast.Del)
        ):
            names.add(candidate.id)
    return frozenset(names)


def _numeric_function_parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, ...]:
    names = tuple(
        argument.arg
        for argument in (
            tuple(node.args.posonlyargs)
            + tuple(node.args.args)
            + tuple(node.args.kwonlyargs)
        )
    )
    if node.args.vararg is not None:
        names += (node.args.vararg.arg,)
    if node.args.kwarg is not None:
        names += (node.args.kwarg.arg,)
    return names


def _numeric_helper_analysis_key(
    qualified_name: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    purpose: str,
    positional: tuple[_InfrastructureNumericProvenance, ...],
    keywords: tuple[
        tuple[str | None, _InfrastructureNumericProvenance], ...
    ],
    *,
    global_states: Mapping[
        str, _InfrastructureNumericProvenance
    ],
    global_names: frozenset[str],
    project_functions: Mapping[
        str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]
    ],
    summaries: Mapping[
        _NumericAnalysisKey, _InfrastructureNumericProvenance
    ],
) -> _NumericAnalysisKey:
    ordinary = tuple(node.args.posonlyargs) + tuple(node.args.args)
    keyword_only = tuple(node.args.kwonlyargs)
    states = {
        name: _InfrastructureNumericProvenance.NONE
        for name in _numeric_function_parameter_names(node)
    }
    bound_names = set()
    for index, state in enumerate(positional[:len(ordinary)]):
        states[ordinary[index].arg] |= state
        bound_names.add(ordinary[index].arg)
    remaining = positional[len(ordinary):]
    if node.args.vararg is not None:
        for state in remaining:
            states[node.args.vararg.arg] |= state
        if remaining:
            bound_names.add(node.args.vararg.arg)
    elif remaining:
        raise _ContractError(
            "infrastructure helper call has incompatible arguments"
        )
    allowed_keywords = {
        argument.arg for argument in ordinary + keyword_only
    }
    for name, state in keywords:
        if name is None:
            if node.args.kwarg is None:
                raise _ContractError(
                    "infrastructure helper call has incompatible arguments"
                )
            states[node.args.kwarg.arg] |= state
        elif name in allowed_keywords:
            states[name] |= state
            bound_names.add(name)
        elif node.args.kwarg is not None:
            states[node.args.kwarg.arg] |= state
        else:
            raise _ContractError(
                "infrastructure helper call has incompatible arguments"
            )
    positional_defaults = zip(
        ordinary[len(ordinary) - len(node.args.defaults):],
        node.args.defaults,
    )
    keyword_defaults = zip(keyword_only, node.args.kw_defaults)
    for argument, default in tuple(positional_defaults) + tuple(
        keyword_defaults
    ):
        if argument.arg in bound_names or default is None:
            continue
        states[argument.arg] |= _numeric_expression_state(
            default,
            global_states,
            purpose=purpose,
            local_names=frozenset(),
            global_names=global_names,
            project_functions=project_functions,
            summaries=summaries,
        )
    environment = tuple(
        (name, int(global_states.get(
            name, _InfrastructureNumericProvenance.NONE
        )))
        for name in sorted(global_names)
    )
    return (
        qualified_name,
        purpose,
        tuple(
            int(states[name])
            for name in _numeric_function_parameter_names(node)
        ),
        environment,
    )


def _event_counter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    purpose: str,
) -> frozenset[str]:
    if purpose != "event_and_counterfactual_transport":
        return frozenset()
    nodes = _bounded_infrastructure_ast_nodes(node)
    parents: dict[int, ast.AST] = {}
    for parent in nodes:
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    zero_initialized = {
        target.id
        for candidate in nodes
        if isinstance(candidate, (ast.Assign, ast.AnnAssign))
        for parts in (_assignment_parts(candidate),)
        if parts is not None
        for target in parts[0]
        if isinstance(target, ast.Name)
        if isinstance(parts[1], ast.Constant)
        if type(parts[1].value) is int and parts[1].value == 0
    }
    incremented_in_loop = set()
    for candidate in nodes:
        if not (
            isinstance(candidate, ast.AugAssign)
            and isinstance(candidate.target, ast.Name)
            and isinstance(candidate.op, ast.Add)
            and isinstance(candidate.value, ast.Constant)
            and type(candidate.value.value) is int
            and candidate.value.value == 1
        ):
            continue
        parent = parents.get(id(candidate))
        while parent is not None and parent is not node:
            if isinstance(parent, (ast.For, ast.AsyncFor)):
                incremented_in_loop.add(candidate.target.id)
                break
            parent = parents.get(id(parent))
    return frozenset(zero_initialized & incremented_in_loop)


def _numeric_subscript_field_path(node: ast.AST) -> tuple[str, ...] | None:
    fields = []
    candidate = node
    while isinstance(candidate, ast.Subscript):
        slice_node = candidate.slice
        if not (
            isinstance(slice_node, ast.Constant)
            and type(slice_node.value) is str
        ):
            return None
        fields.append(slice_node.value)
        candidate = candidate.value
    if not isinstance(candidate, ast.Name):
        return None
    return tuple(reversed(fields))


def _is_frozen_threshold_comparison(
    node: ast.AST,
    frozen_threshold_names: frozenset[str] = frozenset(),
) -> bool:
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and len(node.comparators) == 1
    ):
        return False
    paths = (
        _numeric_subscript_field_path(node.left),
        _numeric_subscript_field_path(node.comparators[0]),
    )
    if any(
        path is not None
        and path[-1:] == ("threshold",)
        and (
            path == ("threshold",)
            or path[-2:] == ("frozen_policy", "threshold")
        )
        for path in paths
    ):
        return True
    return any(
        isinstance(operand, ast.Name)
        and operand.id in frozen_threshold_names
        for operand in (node.left, node.comparators[0])
    )


def _is_input_none_identity_comparison(
    node: ast.AST,
    state: _InfrastructureNumericProvenance,
) -> bool:
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], (ast.Is, ast.IsNot))
        and len(node.comparators) == 1
    ):
        return False
    operands = (node.left, node.comparators[0])
    if not (
        sum(
            isinstance(operand, ast.Constant)
            and operand.value is None
            for operand in operands
        )
        == 1
        and any(isinstance(operand, ast.Name) for operand in operands)
    ):
        return False
    permitted_state = (
        _InfrastructureNumericProvenance.INPUT_OR_POLICY
        | _InfrastructureNumericProvenance.COMPARISON_RESULT
        | _InfrastructureNumericProvenance.UNAPPROVED_COMPARISON
    )
    return bool(
        state & _InfrastructureNumericProvenance.INPUT_OR_POLICY
    ) and not bool(state & ~permitted_state)


def _is_direct_structural_cardinality_comparison(
    node: ast.AST,
    state: _InfrastructureNumericProvenance,
) -> bool:
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(
            node.ops[0],
            (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE),
        )
        and len(node.comparators) == 1
    ):
        return False
    operands = (node.left, node.comparators[0])
    calls = tuple(
        operand for operand in operands if isinstance(operand, ast.Call)
    )
    literals = tuple(
        operand
        for operand in operands
        if isinstance(operand, ast.Constant)
        and type(operand.value) is int
        and 0 <= operand.value <= _INFRASTRUCTURE_AST_NODE_LIMIT
    )
    if not (len(calls) == 1 and len(literals) == 1):
        return False
    call = calls[0]
    if not (
        isinstance(call.func, ast.Name)
        and call.func.id == "len"
        and len(call.args) == 1
        and not call.keywords
    ):
        return False
    exact_state = (
        _InfrastructureNumericProvenance.STRUCTURAL_CARDINALITY
        | _InfrastructureNumericProvenance.NUMERIC_LITERAL
        | _InfrastructureNumericProvenance.COMPARISON_RESULT
        | _InfrastructureNumericProvenance.UNAPPROVED_COMPARISON
    )
    return state == exact_state


def _numeric_frozen_threshold_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> frozenset[str]:
    assignments = _scope_assignments(node)
    names = set()
    pending = deque(range(len(assignments)))
    steps = 0
    while pending:
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        assignment = assignments[pending.popleft()]
        parts = _assignment_parts(assignment)
        if parts is None:
            continue
        targets, value = parts
        path = _numeric_subscript_field_path(value)
        exact_field = path is not None and (
            path == ("threshold",)
            or path[-2:] == ("frozen_policy", "threshold")
        )
        alias = isinstance(value, ast.Name) and value.id in names
        if not (exact_field or alias):
            continue
        updated = _assigned_local_names(targets) - names
        if not updated:
            continue
        names.update(updated)
        pending.extend(range(len(assignments)))
    return frozenset(names)


def _validate_numeric_return_sink(
    state: _InfrastructureNumericProvenance,
    node: ast.AST,
    purpose: str,
    counter_names: frozenset[str],
) -> None:
    if state & _InfrastructureNumericProvenance.COMPARISON_RESULT:
        if (
            not bool(
                state
                & (
                    _NUMERIC_LITERAL_PROVENANCE
                    | _InfrastructureNumericProvenance.UNKNOWN
                )
            )
            and state
            & _InfrastructureNumericProvenance.
            FROZEN_THRESHOLD_COMPARISON
            and not bool(
                state
                & _InfrastructureNumericProvenance.
                UNAPPROVED_COMPARISON
            )
            and _numeric_permission(
                purpose,
                "frozen_policy.threshold",
                "returned_comparison",
            )
        ):
            return
        raise _ContractError(
            "infrastructure numeric threshold violates its purpose"
        )
    if state & _InfrastructureNumericProvenance.UNKNOWN:
        raise _ContractError(
            "infrastructure unknown numeric provenance violates its purpose"
        )
    if not _numeric_state_has_literal(state):
        return
    binding = "structural_cardinality"
    if (
        state
        & _InfrastructureNumericProvenance.STRUCTURAL_INDEX_OR_BOUND
        and isinstance(node, ast.Name)
        and node.id in counter_names
    ):
        binding = "occurrence_counter"
    if not _numeric_state_is_safe_structural(
        state, purpose, binding=binding
    ):
        raise _ContractError(
            "infrastructure numeric provenance violates its purpose"
        )


def _validate_numeric_control_sink(
    state: _InfrastructureNumericProvenance,
    node: ast.AST,
    purpose: str,
    *,
    position: str,
) -> None:
    if state & _InfrastructureNumericProvenance.COMPARISON_RESULT:
        if state & (
            _InfrastructureNumericProvenance.
            FROZEN_THRESHOLD_COMPARISON
        ):
            if (
                not bool(
                    state
                    & (
                        _NUMERIC_LITERAL_PROVENANCE
                        | _InfrastructureNumericProvenance.UNKNOWN
                        | _InfrastructureNumericProvenance.
                        UNAPPROVED_COMPARISON
                    )
                )
                and _numeric_permission(
                    purpose,
                    "frozen_policy.threshold",
                    position,
                )
            ):
                return
            raise _ContractError(
                "infrastructure numeric threshold control "
                "violates its purpose"
            )
        if (
            _is_input_none_identity_comparison(node, state)
            and _numeric_permission(
                purpose,
                "identity.none",
                position,
            )
        ):
            return
        if (
            _is_direct_structural_cardinality_comparison(node, state)
            and _numeric_permission(
                purpose,
                "builtins.len",
                position,
            )
        ):
            return
        if state & (
            _InfrastructureNumericProvenance.
            UNAPPROVED_COMPARISON
        ):
            raise _ContractError(
                "infrastructure comparison control violates its purpose"
            )
        if (
            not bool(
                state & _InfrastructureNumericProvenance.UNKNOWN
            )
            and state
            & _InfrastructureNumericProvenance.STRUCTURAL_CARDINALITY
            and _numeric_permission(
                purpose, "builtins.len", "control_comparison"
            )
        ):
            return
        raise _ContractError(
            "infrastructure comparison control violates its purpose"
        )
    if state & _InfrastructureNumericProvenance.UNKNOWN:
        raise _ContractError(
            "infrastructure unknown control provenance violates its purpose"
        )
    if not _numeric_state_has_literal(state):
        return
    if (
        isinstance(node, ast.Name)
        and _numeric_permission(
            purpose, "ast.Name", "literal_control"
        )
    ):
        return
    raise _ContractError(
        "infrastructure numeric control violates its purpose"
    )


def _validate_numeric_general_sink(
    state: _InfrastructureNumericProvenance,
    purpose: str,
    *,
    position: str,
) -> None:
    if state & _InfrastructureNumericProvenance.COMPARISON_RESULT:
        if (
            state
            & _InfrastructureNumericProvenance.
            FROZEN_THRESHOLD_COMPARISON
            and not bool(
                state
                & (
                    _InfrastructureNumericProvenance.
                    UNAPPROVED_COMPARISON
                    | _NUMERIC_LITERAL_PROVENANCE
                    | _InfrastructureNumericProvenance.UNKNOWN
                )
            )
            and _numeric_permission(
                purpose,
                "frozen_policy.threshold",
                position,
            )
        ):
            return
        raise _ContractError(
            "infrastructure comparison provenance violates its purpose"
        )
    if state & _InfrastructureNumericProvenance.UNKNOWN:
        raise _ContractError(
            "infrastructure unknown expression provenance violates its purpose"
        )
    if _numeric_state_has_literal(state):
        raise _ContractError(
            "infrastructure numeric expression provenance violates its purpose"
        )


def _validate_numeric_mutation_sink(
    state: _InfrastructureNumericProvenance,
    purpose: str,
    *,
    position: str,
) -> None:
    del purpose, position
    if state & (
        _NUMERIC_LITERAL_PROVENANCE
        | _NUMERIC_STRUCTURAL_PROVENANCE
        | _InfrastructureNumericProvenance.UNKNOWN
        | _InfrastructureNumericProvenance.COMPARISON_RESULT
        | _InfrastructureNumericProvenance.UNAPPROVED_COMPARISON
    ):
        raise _ContractError(
            "infrastructure mutation value provenance violates its purpose"
        )


def _validate_numeric_index_sink(
    state: _InfrastructureNumericProvenance,
    node: ast.AST,
    purpose: str,
) -> None:
    if state & _InfrastructureNumericProvenance.COMPARISON_RESULT:
        raise _ContractError(
            "infrastructure comparison index provenance violates its purpose"
        )
    if not bool(
        state
        & (
            _NUMERIC_LITERAL_PROVENANCE
            | _InfrastructureNumericProvenance.UNKNOWN
        )
    ):
        return
    binding = "ast.Slice" if isinstance(node, ast.Slice) else "ast.Subscript"
    position = "bound" if isinstance(node, ast.Slice) else "index"
    if not (
        state == _InfrastructureNumericProvenance.NUMERIC_LITERAL
        and _numeric_permission(purpose, binding, position)
    ):
        raise _ContractError(
            "infrastructure numeric index provenance violates its purpose"
        )


def _numeric_runtime_parent_fields(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[
    tuple[ast.AST, ...],
    Mapping[int, tuple[ast.AST, str, int | None]],
]:
    nodes = []
    parent_fields = {}
    pending = deque(
        (statement, node, "body", index)
        for index, statement in enumerate(node.body)
    )
    while pending:
        candidate, parent, field, index = pending.popleft()
        nodes.append(candidate)
        parent_fields[id(candidate)] = (parent, field, index)
        if len(nodes) > _INFRASTRUCTURE_AST_NODE_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        for child_field, value in ast.iter_fields(candidate):
            if isinstance(value, ast.AST):
                pending.append((value, candidate, child_field, None))
                continue
            if isinstance(value, list):
                pending.extend(
                    (child, candidate, child_field, child_index)
                    for child_index, child in enumerate(value)
                    if isinstance(child, ast.AST)
                )
    return tuple(nodes), parent_fields


def _numeric_target_evaluation_roots(
    target: ast.AST,
) -> tuple[ast.AST, ...]:
    roots = []
    pending = [target]
    visited = 0
    while pending:
        candidate = pending.pop()
        visited += 1
        if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        if isinstance(candidate, ast.Attribute):
            roots.append(candidate.value)
            continue
        if isinstance(candidate, ast.Subscript):
            roots.extend((candidate.value, candidate.slice))
            continue
        if isinstance(candidate, ast.Starred):
            pending.append(candidate.value)
            continue
        if isinstance(candidate, (ast.List, ast.Tuple)):
            pending.extend(reversed(candidate.elts))
            continue
        if isinstance(candidate, ast.Name):
            continue
        roots.append(candidate)
    return tuple(roots)


def _numeric_target_inert_expressions(target: ast.AST) -> frozenset[int]:
    return frozenset(
        id(candidate)
        for candidate in _bounded_infrastructure_ast_nodes(target)
        if isinstance(candidate, ast.expr)
        and isinstance(
            getattr(candidate, "ctx", None),
            (ast.Store, ast.Del),
        )
    )


def _numeric_guaranteed_noniterable_scalar_syntax(
    expression: ast.AST,
) -> bool:
    classifications = {}
    pending = [(expression, False)]
    visited = 0
    while pending:
        candidate, expanded = pending.pop()
        candidate_id = id(candidate)
        if candidate_id in classifications:
            continue
        if not expanded:
            visited += 1
            if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
                raise _ContractError(
                    "infrastructure binding scalar syntax exceeds its bound"
                )
            if isinstance(candidate, ast.Constant):
                pure_numeric = type(candidate.value) in (
                    bool,
                    int,
                    float,
                    complex,
                )
                classifications[candidate_id] = (
                    pure_numeric,
                    pure_numeric
                    or candidate.value is None
                    or candidate.value is Ellipsis,
                )
                continue
            if isinstance(candidate, ast.UnaryOp) and isinstance(
                candidate.op, ast.Not
            ):
                classifications[candidate_id] = (False, True)
                continue
            if (
                isinstance(candidate, ast.Compare)
                and candidate.ops
                and all(
                    isinstance(operator, (ast.Is, ast.IsNot))
                    for operator in candidate.ops
                )
            ):
                classifications[candidate_id] = (False, True)
                continue
            if isinstance(candidate, ast.UnaryOp) and isinstance(
                candidate.op, (ast.UAdd, ast.USub, ast.Invert)
            ):
                pending.append((candidate, True))
                pending.append((candidate.operand, False))
                continue
            if isinstance(candidate, ast.BinOp):
                pending.append((candidate, True))
                pending.append((candidate.right, False))
                pending.append((candidate.left, False))
                continue
            classifications[candidate_id] = (False, False)
            continue
        if isinstance(candidate, ast.UnaryOp):
            pure_numeric = classifications[id(candidate.operand)][0]
        else:
            pure_numeric = (
                classifications[id(candidate.left)][0]
                and classifications[id(candidate.right)][0]
            )
        classifications[candidate_id] = (pure_numeric, pure_numeric)
    return classifications[id(expression)][1]


def _numeric_binding_result_states(
    target: ast.AST,
    source: ast.AST,
    source_state: _InfrastructureNumericProvenance,
    *,
    binding_kind: str,
    expression_state: Callable[
        [ast.AST], _InfrastructureNumericProvenance
    ],
    purpose: str,
    local_names: frozenset[str],
    global_names: frozenset[str],
    project_functions: Mapping[
        str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]
    ],
) -> tuple[
    tuple[tuple[ast.expr, _InfrastructureNumericProvenance], ...],
    frozenset[int],
]:
    leaves = []
    classified_store_ids = set()
    pending_targets = [target]
    visited = 0
    while pending_targets:
        candidate = pending_targets.pop()
        visited += 1
        if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
            raise _ContractError(
                "infrastructure binding target exceeds its bound"
            )
        if not (
            isinstance(candidate, ast.expr)
            and isinstance(getattr(candidate, "ctx", None), ast.Store)
        ):
            raise _ContractError(
                "infrastructure binding target is unsupported"
            )
        classified_store_ids.add(id(candidate))
        if isinstance(candidate, (ast.Name, ast.Attribute, ast.Subscript)):
            leaves.append(candidate)
            continue
        if isinstance(candidate, ast.Starred):
            pending_targets.append(candidate.value)
            continue
        if isinstance(candidate, (ast.List, ast.Tuple)):
            pending_targets.extend(reversed(candidate.elts))
            continue
        raise _ContractError(
            "infrastructure binding target is unsupported"
        )

    # A source descriptor is ``(state, expression, elements, exactness)``.
    # Exactness keeps ordinary opaque values distinct from exact sequences,
    # exact synthetic scalars, and invalid source-side star expansion.
    opaque_source = "opaque"
    exact_source = "exact"
    invalid_source = "invalid"

    def has_starred_sequence_expansion(expression: ast.AST) -> bool:
        pending = [expression]
        steps = 0
        while pending:
            candidate = pending.pop()
            if not isinstance(candidate, (ast.List, ast.Tuple)):
                continue
            for element in candidate.elts:
                steps += 1
                if steps > _INFRASTRUCTURE_AST_NODE_LIMIT:
                    raise _ContractError(
                        "infrastructure binding source exceeds its bound"
                    )
                if isinstance(element, ast.Starred):
                    return True
                if isinstance(element, (ast.List, ast.Tuple)):
                    pending.append(element)
        return False

    def expression_source(expression: ast.AST, state=None):
        exactness = opaque_source
        if isinstance(expression, (ast.List, ast.Tuple)):
            exactness = (
                invalid_source
                if any(
                    isinstance(element, ast.Starred)
                    for element in expression.elts
                )
                else exact_source
            )
        elif _numeric_guaranteed_noniterable_scalar_syntax(expression):
            exactness = invalid_source
        return (
            expression_state(expression) if state is None else state,
            expression,
            None,
            exactness,
        )

    def fixed_source(state, exactness):
        return state, None, None, exactness

    def source_elements(descriptor):
        _state, expression, elements, exactness = descriptor
        if exactness != exact_source:
            return exactness, None
        if elements is not None:
            return exactness, elements
        if not isinstance(expression, (ast.List, ast.Tuple)):
            return exactness, None
        return exactness, tuple(
            expression_source(element) for element in expression.elts
        )

    def sequence_source(elements):
        state = _InfrastructureNumericProvenance.NONE
        for element in elements:
            state |= element[0]
        return state, None, tuple(elements), exact_source

    unknown_source = fixed_source(
        _InfrastructureNumericProvenance.UNKNOWN,
        opaque_source,
    )
    structural_source = fixed_source(
        _InfrastructureNumericProvenance.STRUCTURAL_INDEX_OR_BOUND,
        exact_source,
    )
    root_source = expression_source(source, source_state)
    structural_unpack = isinstance(target, (ast.List, ast.Tuple, ast.Starred))
    if (
        binding_kind == "for"
        or binding_kind in {"assignment", "augmented_assignment"}
        and structural_unpack
    ) and has_starred_sequence_expansion(source):
        raise _ContractError(
            "infrastructure exact binding source expansion is unsupported"
        )
    if binding_kind in {"assignment", "augmented_assignment"}:
        source_variants = (root_source,)
    elif binding_kind in {"with", "async_for"}:
        source_variants = (unknown_source,)
    elif binding_kind == "for":
        call_name = (
            source.func.id
            if isinstance(source, ast.Call)
            and isinstance(source.func, ast.Name)
            and source.func.id not in local_names
            and source.func.id not in global_names
            and source.func.id not in project_functions
            else None
        )
        exact_range = (
            call_name == "range"
            and 1 <= len(source.args) <= 3
            and not source.keywords
            and not any(
                isinstance(argument, ast.Starred)
                for argument in source.args
            )
            and _numeric_permission(
                purpose, "builtins.range", "iterator_result"
            )
        )
        exact_enumerate = (
            call_name == "enumerate"
            and 1 <= len(source.args) <= 2
            and not source.keywords
            and not any(
                isinstance(argument, ast.Starred)
                for argument in source.args
            )
            and _numeric_permission(
                purpose, "builtins.enumerate", "iterator_result"
            )
        )
        if exact_range:
            source_variants = (structural_source,)
        elif exact_enumerate:
            if has_starred_sequence_expansion(source.args[0]):
                raise _ContractError(
                    "infrastructure exact binding source expansion is "
                    "unsupported"
                )
            item_source = expression_source(source.args[0])
            item_kind, item_variants = source_elements(item_source)
            if item_kind == invalid_source:
                raise _ContractError(
                    "infrastructure exact binding source expansion is "
                    "unsupported"
                )
            if item_kind == opaque_source:
                item_variants = (unknown_source,)
            elif item_variants is None:
                raise _ContractError(
                    "infrastructure exact binding source shape is invalid"
                )
            source_variants = tuple(
                sequence_source((structural_source, item_variant))
                for item_variant in item_variants
            )
        else:
            source_kind, source_variants = source_elements(root_source)
            if source_kind == invalid_source:
                raise _ContractError(
                    "infrastructure exact binding source expansion is "
                    "unsupported"
                )
            if source_kind == opaque_source:
                source_variants = (unknown_source,)
            elif source_variants is None:
                raise _ContractError(
                    "infrastructure exact binding source shape is invalid"
                )
    else:
        raise _ContractError(
            "infrastructure binding provenance kind is unsupported"
        )

    joined_states = {
        id(leaf): _InfrastructureNumericProvenance.NONE for leaf in leaves
    }
    pending = [
        (target, descriptor)
        for descriptor in reversed(tuple(source_variants))
    ]
    steps = 0
    while pending:
        candidate, descriptor = pending.pop()
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure binding provenance exceeds its bound"
            )
        if isinstance(candidate, ast.Starred):
            pending.append((candidate.value, descriptor))
            continue
        if isinstance(candidate, (ast.List, ast.Tuple)):
            target_elements = tuple(candidate.elts)
            source_kind, exact_elements = source_elements(descriptor)
            starred_indices = tuple(
                index
                for index, element in enumerate(target_elements)
                if isinstance(element, ast.Starred)
            )
            if source_kind == invalid_source:
                raise _ContractError(
                    "infrastructure exact binding source expansion is "
                    "unsupported"
                )
            if source_kind == opaque_source:
                pairs = tuple(
                    (element, unknown_source)
                    for element in target_elements
                )
            elif exact_elements is None:
                raise _ContractError(
                    "infrastructure exact binding source shape is invalid"
                )
            elif not starred_indices:
                if len(target_elements) != len(exact_elements):
                    raise _ContractError(
                        "infrastructure exact binding arity is invalid"
                    )
                pairs = tuple(zip(target_elements, exact_elements))
            elif (
                len(starred_indices) == 1
                and len(exact_elements) >= len(target_elements) - 1
            ):
                starred_index = starred_indices[0]
                suffix_length = len(target_elements) - starred_index - 1
                middle_end = len(exact_elements) - suffix_length
                pairs = tuple(
                    zip(
                        target_elements[:starred_index],
                        exact_elements[:starred_index],
                    )
                ) + (
                    (
                        target_elements[starred_index],
                        sequence_source(
                            exact_elements[starred_index:middle_end]
                        ),
                    ),
                ) + tuple(
                    zip(
                        target_elements[starred_index + 1:],
                        exact_elements[middle_end:],
                    )
                )
            else:
                raise _ContractError(
                    "infrastructure exact starred binding arity is invalid"
                )
            pending.extend(reversed(pairs))
            continue
        if not isinstance(candidate, (ast.Name, ast.Attribute, ast.Subscript)):
            raise _ContractError(
                "infrastructure binding target is unsupported"
            )
        joined_states[id(candidate)] |= descriptor[0]

    return (
        tuple((leaf, joined_states[id(leaf)]) for leaf in leaves),
        frozenset(classified_store_ids),
    )


def _validate_numeric_function_for_purpose(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    purpose: str,
    *,
    parameter_states: tuple[int, ...] | None = None,
    global_states: Mapping[
        str, _InfrastructureNumericProvenance
    ] | None = None,
    global_names: frozenset[str] = frozenset(),
    project_functions: Mapping[
        str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]
    ] | None = None,
    function_global_states: Mapping[
        str, Mapping[str, _InfrastructureNumericProvenance]
    ] | None = None,
    function_global_names: Mapping[str, frozenset[str]] | None = None,
    function_bindings: Mapping[
        str,
        Mapping[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]],
    ] | None = None,
    approved_project_classes: frozenset[str] = frozenset(),
    class_attribute_states: Mapping[
        str, _InfrastructureNumericProvenance
    ] | None = None,
    class_receiver_names: frozenset[str] = frozenset(),
    summaries: Mapping[
        _NumericAnalysisKey, _InfrastructureNumericProvenance
    ] | None = None,
    requested: set[_NumericAnalysisKey] | None = None,
    enforce_return: bool = True,
) -> _InfrastructureNumericProvenance:
    if project_functions is None:
        project_functions = {}
    if summaries is None:
        summaries = {}
    if global_states is None:
        global_states = {}
    if function_global_states is None:
        function_global_states = {}
    if function_global_names is None:
        function_global_names = {}
    if function_bindings is None:
        function_bindings = {}
    if class_attribute_states is None:
        class_attribute_states = {}
    local_names = _numeric_function_local_names(node)
    argument_names = _numeric_function_parameter_names(node)
    if parameter_states is None:
        default_key = _numeric_helper_analysis_key(
            "<conservative>",
            node,
            purpose,
            (),
            (),
            global_states=global_states,
            global_names=global_names,
            project_functions=project_functions,
            summaries=summaries,
        )
        parameter_states = tuple(
            int(
                _InfrastructureNumericProvenance.INPUT_OR_POLICY
                | _InfrastructureNumericProvenance(state)
            )
            for state in default_key[2]
        )
    if len(parameter_states) != len(argument_names):
        raise _ContractError(
            "infrastructure helper summary has incompatible parameters"
        )
    names = dict(global_states)
    names.update({
        name: _InfrastructureNumericProvenance(state)
        for name, state in zip(argument_names, parameter_states)
    })
    counter_names = _event_counter_names(node, purpose)
    frozen_threshold_names = _numeric_frozen_threshold_names(node)
    runtime_nodes, parent_fields = _numeric_runtime_parent_fields(node)
    covered_expression_ids = set()
    sink_expression_ids = set()
    inert_expression_ids = {
        id(candidate)
        for candidate in runtime_nodes
        if isinstance(candidate, ast.expr)
        and isinstance(
            getattr(candidate, "ctx", None),
            (ast.Store, ast.Del),
        )
    }
    expected_store_target_ids = {
        id(candidate)
        for candidate in runtime_nodes
        if isinstance(candidate, ast.expr)
        and isinstance(getattr(candidate, "ctx", None), ast.Store)
    }
    classified_store_target_ids = set()
    evaluated_project_calls = set()

    def mark_expression_tree(expression: ast.AST) -> None:
        covered_expression_ids.update(
            id(candidate)
            for candidate in _bounded_infrastructure_ast_nodes(expression)
            if isinstance(candidate, ast.expr)
            and not isinstance(
                getattr(candidate, "ctx", None),
                (ast.Store, ast.Del),
            )
        )

    def mark_inert_tree(expression: ast.AST) -> None:
        inert_expression_ids.update(
            id(candidate)
            for candidate in _bounded_infrastructure_ast_nodes(expression)
            if isinstance(candidate, ast.expr)
        )

    def expression_state(
        expression: ast.AST,
    ) -> _InfrastructureNumericProvenance:
        mark_expression_tree(expression)
        return _numeric_expression_state(
            expression,
            names,
            purpose=purpose,
            local_names=local_names,
            global_names=global_names,
            project_functions=project_functions,
            function_global_states=function_global_states,
            function_global_names=function_global_names,
            function_bindings=function_bindings,
            approved_project_classes=approved_project_classes,
            class_attribute_states=class_attribute_states,
            class_receiver_names=class_receiver_names,
            frozen_threshold_names=frozen_threshold_names,
            evaluated_project_calls=evaluated_project_calls,
            summaries=summaries,
            requested=requested,
        )

    def sink_state(
        expression: ast.AST,
    ) -> _InfrastructureNumericProvenance:
        state = expression_state(expression)
        if isinstance(expression, ast.expr):
            sink_expression_ids.add(id(expression))
        return state

    def validate_control_sink(expression: ast.AST, *, position: str) -> None:
        state = sink_state(expression)
        if (
            position
            in {
                "if_test",
                "while_test",
                "assert_test",
                "if_expression_test",
            }
            and isinstance(expression, ast.UnaryOp)
            and isinstance(expression.op, ast.Not)
        ):
            _validate_numeric_control_sink(
                expression_state(expression.operand),
                expression.operand,
                purpose,
                position=position,
            )
            return
        _validate_numeric_control_sink(
            state,
            expression,
            purpose,
            position=position,
        )

    def validate_return_sink(
        expression: ast.expr,
        aggregate_state: _InfrastructureNumericProvenance,
    ) -> None:
        pending: list[
            tuple[
                ast.expr,
                _InfrastructureNumericProvenance | None,
            ]
        ] = [(expression, aggregate_state)]
        visited = 0
        while pending:
            candidate, known_state = pending.pop()
            visited += 1
            if visited > _INFRASTRUCTURE_AST_NODE_LIMIT:
                raise _ContractError(
                    "infrastructure numeric provenance exceeds its bound"
                )
            if isinstance(candidate, (ast.Tuple, ast.List)):
                if any(
                    isinstance(element, ast.Starred)
                    for element in candidate.elts
                ):
                    state = (
                        known_state
                        if known_state is not None
                        else expression_state(candidate)
                    )
                    _validate_numeric_return_sink(
                        state,
                        candidate,
                        purpose,
                        counter_names,
                    )
                    continue
                pending.extend(
                    (element, None)
                    for element in reversed(candidate.elts)
                )
                continue
            state = (
                known_state
                if known_state is not None
                else expression_state(candidate)
            )
            _validate_numeric_return_sink(
                state,
                candidate,
                purpose,
                counter_names,
            )

    def validate_binding_target(
        target: ast.AST,
        source: ast.AST,
        source_state: _InfrastructureNumericProvenance,
        *,
        binding_kind: str,
        position: str,
        hidden_value_unknown: bool = False,
    ) -> bool:
        leaf_states, classified_ids = _numeric_binding_result_states(
            target,
            source,
            source_state,
            binding_kind=binding_kind,
            expression_state=expression_state,
            purpose=purpose,
            local_names=local_names,
            global_names=global_names,
            project_functions=project_functions,
        )
        classified_store_target_ids.update(classified_ids)
        mutation_binding = False
        for leaf, state in leaf_states:
            if not isinstance(leaf, (ast.Attribute, ast.Subscript)):
                continue
            mutation_binding = True
            if hidden_value_unknown:
                state |= _InfrastructureNumericProvenance.UNKNOWN
            _validate_numeric_mutation_sink(
                state,
                purpose,
                position=position,
            )
        return mutation_binding

    assignments = _scope_assignments(node)
    parts_by_index = tuple(
        _assignment_parts(assignment) for assignment in assignments
    )
    reverse_uses: dict[str, set[int]] = {}
    edge_count = 0
    for index, parts in enumerate(parts_by_index):
        if parts is None:
            continue
        for candidate in ast.walk(parts[1]):
            if isinstance(candidate, ast.Name) and isinstance(
                candidate.ctx, ast.Load
            ):
                reverse_uses.setdefault(candidate.id, set()).add(index)
                edge_count += 1
                if edge_count > _INFRASTRUCTURE_DEF_USE_EDGE_LIMIT:
                    raise _ContractError(
                        "infrastructure numeric provenance exceeds its bound"
                    )
        assignment = assignments[index]
        if (
            isinstance(assignment, ast.AugAssign)
            and isinstance(assignment.target, ast.Name)
            and assignment.target.id in local_names
        ):
            reverse_uses.setdefault(assignment.target.id, set()).add(index)
            edge_count += 1
            if edge_count > _INFRASTRUCTURE_DEF_USE_EDGE_LIMIT:
                raise _ContractError(
                    "infrastructure numeric provenance exceeds its bound"
                )
    pending = deque(range(len(assignments)))
    queued = set(pending)
    steps = 0
    while pending:
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        index = pending.popleft()
        queued.discard(index)
        parts = parts_by_index[index]
        if parts is None:
            continue
        targets, value = parts
        assignment = assignments[index]
        source_state = expression_state(value)
        if isinstance(assignment, ast.withitem):
            binding_kind = "with"
        elif isinstance(assignment, ast.AsyncFor):
            binding_kind = "async_for"
        elif isinstance(assignment, ast.For):
            binding_kind = "for"
        elif isinstance(assignment, ast.AugAssign):
            binding_kind = "augmented_assignment"
        else:
            binding_kind = "assignment"
        leaf_states = tuple(
            leaf_state
            for target in targets
            for leaf_state in _numeric_binding_result_states(
                target,
                value,
                source_state,
                binding_kind=binding_kind,
                expression_state=expression_state,
                purpose=purpose,
                local_names=local_names,
                global_names=global_names,
                project_functions=project_functions,
            )[0]
        )
        for leaf, state in leaf_states:
            if not isinstance(leaf, ast.Name):
                continue
            target_name = leaf.id
            counter_zero = (
                target_name in counter_names
                and isinstance(value, ast.Constant)
                and type(value.value) is int
                and value.value == 0
                and not isinstance(assignment, ast.AugAssign)
            )
            counter_increment = (
                target_name in counter_names
                and isinstance(value, ast.Constant)
                and type(value.value) is int
                and value.value == 1
                and isinstance(assignment, ast.AugAssign)
                and isinstance(assignment.op, ast.Add)
            )
            if counter_zero or counter_increment:
                state = (
                    _InfrastructureNumericProvenance.
                    STRUCTURAL_INDEX_OR_BOUND
                    | _InfrastructureNumericProvenance.
                    LITERAL_DERIVED_ARITHMETIC
                )
            previous = names.get(
                target_name, _InfrastructureNumericProvenance.NONE
            )
            if isinstance(assignment, ast.AugAssign):
                state |= previous
                if not counter_increment:
                    if _numeric_state_has_literal(state):
                        state |= (
                            _InfrastructureNumericProvenance.
                            LITERAL_DERIVED_ARITHMETIC
                        )
                if state & (
                    _InfrastructureNumericProvenance.INPUT_OR_POLICY
                    | _InfrastructureNumericProvenance.UNKNOWN
                ):
                    state |= _InfrastructureNumericProvenance.UNKNOWN
            updated = previous | state
            if updated == previous:
                continue
            names[target_name] = updated
            for dependent in reverse_uses.get(target_name, ()):
                if dependent not in queued:
                    pending.append(dependent)
                    queued.add(dependent)
    return_state = _InfrastructureNumericProvenance.NONE
    for candidate in runtime_nodes:
        if isinstance(candidate, ast.Return):
            if candidate.value is None:
                continue
            state = expression_state(candidate.value)
            return_state |= state
            if enforce_return:
                sink_expression_ids.add(id(candidate.value))
                validate_return_sink(candidate.value, state)
            continue
        if isinstance(candidate, ast.IfExp):
            validate_control_sink(
                candidate.test,
                position="if_expression_test",
            )
            continue
        if isinstance(candidate, ast.If):
            validate_control_sink(
                candidate.test,
                position="if_test",
            )
            continue
        if isinstance(candidate, ast.While):
            validate_control_sink(
                candidate.test,
                position="while_test",
            )
            continue
        if isinstance(candidate, ast.Assert):
            validate_control_sink(
                candidate.test,
                position="assert_test",
            )
            if candidate.msg is not None:
                _validate_numeric_general_sink(
                    sink_state(candidate.msg),
                    purpose,
                    position="assert_message",
                )
            continue
        if isinstance(candidate, ast.withitem):
            context_state = sink_state(candidate.context_expr)
            _validate_numeric_control_sink(
                context_state,
                candidate.context_expr,
                purpose,
                position="with_context",
            )
            if candidate.optional_vars is not None:
                inert_expression_ids.update(
                    _numeric_target_inert_expressions(
                        candidate.optional_vars
                    )
                )
                for expression in _numeric_target_evaluation_roots(
                    candidate.optional_vars
                ):
                    _validate_numeric_general_sink(
                        sink_state(expression),
                        purpose,
                        position="with_target",
                    )
                validate_binding_target(
                    candidate.optional_vars,
                    candidate.context_expr,
                    context_state,
                    binding_kind="with",
                    position="with_binding",
                )
            continue
        if isinstance(candidate, (ast.For, ast.AsyncFor)):
            iterator_state = sink_state(candidate.iter)
            iterator_control_state = iterator_state
            if isinstance(candidate.iter, (ast.List, ast.Tuple)):
                iterator_control_state &= ~(
                    _InfrastructureNumericProvenance.NUMERIC_LITERAL
                )
            _validate_numeric_control_sink(
                iterator_control_state,
                candidate.iter,
                purpose,
                position="for_iterator",
            )
            inert_expression_ids.update(
                _numeric_target_inert_expressions(candidate.target)
            )
            for expression in _numeric_target_evaluation_roots(
                candidate.target
            ):
                _validate_numeric_general_sink(
                    sink_state(expression),
                    purpose,
                    position="for_target",
                )
            validate_binding_target(
                candidate.target,
                candidate.iter,
                iterator_state,
                binding_kind=(
                    "async_for"
                    if isinstance(candidate, ast.AsyncFor)
                    else "for"
                ),
                position="for_binding",
            )
            continue
        if isinstance(candidate, ast.NamedExpr):
            value_state = expression_state(candidate.value)
            if validate_binding_target(
                candidate.target,
                candidate.value,
                value_state,
                binding_kind="assignment",
                position="named_expression_binding",
            ):
                sink_expression_ids.add(id(candidate.value))
            continue
        if isinstance(candidate, ast.Subscript):
            _validate_numeric_index_sink(
                sink_state(candidate.slice), candidate.slice, purpose
            )
            continue
        if isinstance(candidate, ast.Expr):
            _validate_numeric_general_sink(
                sink_state(candidate.value),
                purpose,
                position="expression_statement",
            )
            continue
        if isinstance(candidate, ast.Raise):
            for expression in (candidate.exc, candidate.cause):
                if expression is None:
                    continue
                _validate_numeric_control_sink(
                    sink_state(expression),
                    expression,
                    purpose,
                    position="raise_expression",
                )
            continue
        if isinstance(candidate, ast.ExceptHandler):
            if candidate.type is not None:
                _validate_numeric_general_sink(
                    sink_state(candidate.type),
                    purpose,
                    position="except_handler_type",
                )
            continue
        if isinstance(candidate, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                tuple(candidate.targets)
                if isinstance(candidate, ast.Assign)
                else (candidate.target,)
            )
            for target in targets:
                inert_expression_ids.update(
                    _numeric_target_inert_expressions(target)
                )
                for expression in _numeric_target_evaluation_roots(target):
                    _validate_numeric_general_sink(
                        sink_state(expression),
                        purpose,
                        position="assignment_target",
                    )
            value_state = expression_state(candidate.value)
            mutation_bindings = tuple(
                validate_binding_target(
                    target,
                    candidate.value,
                    value_state,
                    binding_kind=(
                        "augmented_assignment"
                        if isinstance(candidate, ast.AugAssign)
                        else "assignment"
                    ),
                    position=(
                        "augmented_assignment_binding"
                        if isinstance(candidate, ast.AugAssign)
                        else "assignment_binding"
                    ),
                    hidden_value_unknown=isinstance(
                        candidate, ast.AugAssign
                    ),
                )
                for target in targets
            )
            if any(mutation_bindings):
                sink_expression_ids.add(id(candidate.value))
            if isinstance(candidate, ast.AnnAssign):
                mark_inert_tree(candidate.annotation)
            continue
        if isinstance(candidate, ast.Delete):
            for target in candidate.targets:
                inert_expression_ids.update(
                    _numeric_target_inert_expressions(target)
                )
                for expression in _numeric_target_evaluation_roots(target):
                    _validate_numeric_general_sink(
                        sink_state(expression),
                        purpose,
                        position="deletion_target",
                    )
            continue

    if expected_store_target_ids - classified_store_target_ids:
        raise _ContractError(
            "infrastructure mutation target coverage is incomplete"
        )

    runtime_expressions = tuple(
        candidate
        for candidate in runtime_nodes
        if isinstance(candidate, ast.expr)
    )
    for expression in runtime_expressions:
        if id(expression) in covered_expression_ids | inert_expression_ids:
            continue
        parent, field, _index = parent_fields[id(expression)]
        _validate_numeric_general_sink(
            sink_state(expression),
            purpose,
            position=f"{type(parent).__name__}.{field}",
        )

    project_call_ids = {
        id(candidate)
        for candidate in runtime_nodes
        if isinstance(candidate, ast.Call)
        and isinstance(candidate.func, ast.Name)
        and candidate.func.id not in local_names
        and candidate.func.id in project_functions
    }
    if project_call_ids - evaluated_project_calls:
        raise _ContractError(
            "infrastructure helper call evaluation coverage is incomplete"
        )
    classified_expression_ids = (
        covered_expression_ids | inert_expression_ids
    )
    if {
        id(expression) for expression in runtime_expressions
    } - classified_expression_ids:
        raise _ContractError(
            "infrastructure expression evaluation coverage is incomplete"
        )
    if sink_expression_ids - covered_expression_ids:
        raise _ContractError(
            "infrastructure expression sink coverage is inconsistent"
        )
    return return_state


def _validate_infrastructure_numeric_provenance(
    resolved: Mapping[str, _ResolvedAstNode],
) -> None:
    reaching = _infrastructure_reaching_purposes(resolved)
    constant_states: dict[
        str, _InfrastructureNumericProvenance
    ] = {}
    for item in _topological_resolved_nodes(resolved):
        if item.source.node_kind != "immutable_constant":
            continue
        node = item.source.node
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            raise _ContractError(
                "infrastructure constant provenance has an invalid node"
            )
        dependency_states = {}
        dependency_names = set()
        for dependency in item.dependencies:
            if dependency not in resolved:
                continue
            for bound_name in resolved[dependency].source.bound_names:
                dependency_names.add(bound_name)
                if dependency in constant_states:
                    dependency_states[bound_name] = constant_states[
                        dependency
                    ]
        constant_states[item.source.qualified_name] = (
            _numeric_expression_state(
                node.value,
                dependency_states,
                purpose="canonical_transport",
                local_names=frozenset(),
                global_names=frozenset(dependency_names),
            )
        )
    functions = {
        name: item.source.node
        for name, item in resolved.items()
        if isinstance(
            item.source.node, (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }
    project_functions: dict[
        str,
        dict[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]],
    ] = {}
    function_global_states: dict[
        str, dict[str, _InfrastructureNumericProvenance]
    ] = {}
    function_global_names: dict[str, frozenset[str]] = {}
    function_project_classes: dict[str, frozenset[str]] = {}
    for name, node in functions.items():
        bindings = {}
        global_states = {}
        global_names = set()
        approved_classes = set()
        for dependency in resolved[name].dependencies:
            if dependency not in resolved:
                continue
            for bound_name in resolved[dependency].source.bound_names:
                global_names.add(bound_name)
                if dependency in constant_states:
                    global_states[bound_name] = constant_states[dependency]
                else:
                    global_states[bound_name] = (
                        _InfrastructureNumericProvenance.UNKNOWN
                    )
                if resolved[dependency].source.node_kind == "class":
                    approved_classes.add(bound_name)
            dependency_node = functions.get(dependency)
            if dependency_node is None:
                continue
            for bound_name in resolved[dependency].source.bound_names:
                bindings[bound_name] = (dependency, dependency_node)
        project_functions[name] = bindings
        function_global_states[name] = global_states
        function_global_names[name] = frozenset(global_names)
        function_project_classes[name] = frozenset(approved_classes)
    class_analyses = 0
    for name, item in sorted(resolved.items()):
        class_node = item.source.node
        if not isinstance(class_node, ast.ClassDef):
            continue
        global_states = {}
        global_names = set()
        class_project_functions = {}
        class_project_classes = set()
        for dependency in item.dependencies:
            if dependency not in resolved:
                continue
            for bound_name in resolved[dependency].source.bound_names:
                global_names.add(bound_name)
                if dependency in constant_states:
                    global_states[bound_name] = constant_states[dependency]
                else:
                    global_states[bound_name] = (
                        _InfrastructureNumericProvenance.UNKNOWN
                    )
                if dependency in functions:
                    class_project_functions[bound_name] = (
                        dependency,
                        functions[dependency],
                    )
                if resolved[dependency].source.node_kind == "class":
                    class_project_classes.add(bound_name)
        class_assignments = tuple(
            statement
            for statement in class_node.body
            if isinstance(statement, (ast.Assign, ast.AnnAssign))
            and _assignment_parts(statement) is not None
        )
        class_attribute_states: dict[
            str, _InfrastructureNumericProvenance
        ] = {}
        class_attribute_names = frozenset(
            target_name
            for assignment in class_assignments
            for parts in (_assignment_parts(assignment),)
            if parts is not None
            for target_name in _assigned_local_names(parts[0])
        )
        pending_attributes = deque(range(len(class_assignments)))
        attribute_steps = 0
        while pending_attributes:
            attribute_steps += 1
            if attribute_steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
                raise _ContractError(
                    "infrastructure numeric provenance exceeds its bound"
                )
            assignment = class_assignments[pending_attributes.popleft()]
            parts = _assignment_parts(assignment)
            if parts is None:
                continue
            targets, value = parts
            attribute_environment = dict(global_states)
            attribute_environment.update(class_attribute_states)
            state = _numeric_expression_state(
                value,
                attribute_environment,
                purpose="canonical_transport",
                local_names=class_attribute_names,
                global_names=frozenset(global_names | class_attribute_names),
                project_functions=class_project_functions,
                function_global_states=function_global_states,
                function_global_names=function_global_names,
                function_bindings=project_functions,
                approved_project_classes=frozenset(class_project_classes),
            )
            changed = False
            for target_name in _assigned_local_names(targets):
                previous = class_attribute_states.get(
                    target_name, _InfrastructureNumericProvenance.NONE
                )
                updated = previous | state
                if updated == previous:
                    continue
                class_attribute_states[target_name] = updated
                changed = True
            if changed:
                pending_attributes.extend(range(len(class_assignments)))
        method_global_states = dict(global_states)
        method_global_states.update(class_attribute_states)
        method_global_names = frozenset(
            global_names | class_attribute_names
        )
        for method in class_node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            ordinary_arguments = (
                tuple(method.args.posonlyargs) + tuple(method.args.args)
            )
            receiver_names = frozenset(
                {ordinary_arguments[0].arg} if ordinary_arguments else ()
            )
            for purpose in sorted(reaching[name]):
                class_analyses += 1
                if class_analyses > _INFRASTRUCTURE_ANALYSIS_STATE_LIMIT:
                    raise _ContractError(
                        "infrastructure numeric provenance exceeds its bound"
                    )
                _validate_numeric_function_for_purpose(
                    method,
                    purpose,
                    global_states=method_global_states,
                    global_names=method_global_names,
                    project_functions=class_project_functions,
                    function_global_states=function_global_states,
                    function_global_names=function_global_names,
                    function_bindings=project_functions,
                    approved_project_classes=frozenset(
                        class_project_classes
                    ),
                    class_attribute_states=class_attribute_states,
                    class_receiver_names=receiver_names,
                )
    summaries: dict[
        _NumericAnalysisKey, _InfrastructureNumericProvenance
    ] = {}
    callers: dict[_NumericAnalysisKey, set[_NumericAnalysisKey]] = {}
    pending = deque()
    queued = set()

    def enqueue(key: _NumericAnalysisKey) -> None:
        if key not in summaries:
            if len(summaries) >= _INFRASTRUCTURE_ANALYSIS_STATE_LIMIT:
                raise _ContractError(
                    "infrastructure numeric provenance exceeds its bound"
                )
            summaries[key] = _InfrastructureNumericProvenance.NONE
        if key not in queued:
            pending.append(key)
            queued.add(key)

    for name, node in sorted(functions.items()):
        for purpose in sorted(reaching[name]):
            default_key = _numeric_helper_analysis_key(
                name,
                node,
                purpose,
                (),
                (),
                global_states=function_global_states[name],
                global_names=function_global_names[name],
                project_functions=project_functions[name],
                summaries=summaries,
            )
            enqueue(
                (
                    name,
                    purpose,
                    tuple(
                        int(
                            _InfrastructureNumericProvenance.INPUT_OR_POLICY
                            | _InfrastructureNumericProvenance(state)
                        )
                        for state in default_key[2]
                    ),
                    default_key[3],
                )
            )
    steps = 0
    while pending:
        steps += 1
        if steps > _INFRASTRUCTURE_ANALYSIS_STEP_LIMIT:
            raise _ContractError(
                "infrastructure numeric provenance exceeds its bound"
            )
        key = pending.popleft()
        queued.discard(key)
        name, purpose, parameter_states, environment = key
        if purpose not in reaching[name]:
            raise _ContractError(
                "infrastructure helper purpose context is inconsistent"
            )
        expected_environment = tuple(
            (
                global_name,
                int(function_global_states[name].get(
                    global_name,
                    _InfrastructureNumericProvenance.NONE,
                )),
            )
            for global_name in sorted(function_global_names[name])
        )
        if environment != expected_environment:
            raise _ContractError(
                "infrastructure helper environment is inconsistent"
            )
        requested: set[_NumericAnalysisKey] = set()
        result = _validate_numeric_function_for_purpose(
            functions[name],
            purpose,
            parameter_states=parameter_states,
            global_states=function_global_states[name],
            global_names=function_global_names[name],
            project_functions=project_functions[name],
            function_global_states=function_global_states,
            function_global_names=function_global_names,
            function_bindings=project_functions,
            approved_project_classes=function_project_classes[name],
            summaries=summaries,
            requested=requested,
            enforce_return=name in _INFRASTRUCTURE_PURPOSE_BINDINGS,
        )
        for callee in sorted(requested):
            if callee[0] not in functions:
                raise _ContractError(
                    "infrastructure helper summary target is unavailable"
                )
            callers.setdefault(callee, set()).add(key)
            enqueue(callee)
        updated = summaries[key] | result
        if updated == summaries[key]:
            continue
        summaries[key] = updated
        for caller in sorted(callers.get(key, ())):
            enqueue(caller)


def _ast_authored_tokens(node: ast.AST) -> set[str]:
    tokens = set()
    for candidate in ast.walk(node):
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
    return tokens


def _arithmetic_target_tokens(node: ast.AST) -> dict[int, set[str]]:
    target_tokens_by_expression: dict[int, set[str]] = {}
    for scope in _assignment_scopes(node):
        for assignment in _scope_assignments(scope):
            parts = _assignment_parts(assignment)
            if parts is None:
                continue
            targets, value = parts
            target_tokens = {
                token
                for target in targets
                for token in _target_tokens(target)
            }
            for candidate in ast.walk(value):
                if isinstance(candidate, ast.BinOp):
                    target_tokens_by_expression.setdefault(
                        id(candidate), set()
                    ).update(target_tokens)
    return target_tokens_by_expression


def _scan_infrastructure_ast_content(
    resolved: Mapping[str, _ResolvedAstNode],
) -> None:
    _validate_infrastructure_numeric_provenance(resolved)
    for item in resolved.values():
        tokens = set()
        literal_tokens = set()
        has_power = False
        has_policy_bytes_literal = _has_literal_policy_bytes_flow(
            item.source.node
        )
        arithmetic_target_tokens = _arithmetic_target_tokens(
            item.source.node
        )
        docstring_ids = _docstring_value_ids(item.source.node)
        for candidate in ast.walk(item.source.node):
            if isinstance(candidate, (ast.BinOp, ast.AugAssign)):
                if isinstance(candidate.op, ast.Pow):
                    has_power = True
                arithmetic_tokens = _ast_authored_tokens(candidate)
                if isinstance(candidate, ast.BinOp):
                    arithmetic_tokens.update(
                        arithmetic_target_tokens.get(id(candidate), set())
                    )
                if (
                    arithmetic_tokens
                    & _INFRASTRUCTURE_ARITHMETIC_SCIENTIFIC_TOKENS
                ):
                    raise _ContractError(
                        "infrastructure AST contains a scientific equation"
                    )
            if (
                isinstance(candidate, ast.Constant)
                and type(candidate.value) in (float, complex)
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
                if id(candidate) in docstring_ids:
                    continue
                if type(candidate.value) is bytes:
                    authored_value = candidate.value.decode(
                        "utf-8", errors="ignore"
                    )
                else:
                    authored_value = candidate.value
            if authored_value is not None:
                authored_tokens = _lexical_tokens(authored_value)
                tokens.update(authored_tokens)
                if isinstance(candidate, ast.Constant):
                    literal_tokens.update(authored_tokens)
                    if (
                        type(candidate.value) is bytes
                        and "policy" in authored_tokens
                    ):
                        has_policy_bytes_literal = True
        if tokens & {"formula", "hamiltonian"}:
            raise _ContractError(
                "infrastructure AST contains strong scientific content"
            )
        if {"scientific", "constant"} <= tokens:
            raise _ContractError(
                "infrastructure AST contains a scientific constant"
            )
        if has_power:
            raise _ContractError(
                "infrastructure AST contains a scientific power equation"
            )
        if _is_method_result_derivation(tokens):
            raise _ContractError(
                "infrastructure AST contains a method result derivation"
            )
        if (
            {"adapter", "definition"} <= literal_tokens
            or {"oracle", "definition"} <= literal_tokens
        ):
            raise _ContractError(
                "infrastructure AST contains a scientific definition"
            )
        if has_policy_bytes_literal:
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
    resolver.validate_future_annotation_modes()
    resolver.validate_external_import_usage()
    try:
        _scan_infrastructure_ast_content(resolver.resolved)
    except _ContractError as error:
        raise _ContractError(
            "infrastructure purpose scan rejected scientific or "
            "uncommitted content"
        ) from error
    nodes, dependency_edges, _emitted_source = _manifest_from_resolved(
        resolver.resolved
    )
    try:
        _reject_scientific_infrastructure_nodes(nodes)
    except _ContractError as error:
        raise _ContractError(
            "infrastructure purpose scan rejected scientific or "
            "uncommitted content"
        ) from error
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
    validated = _validate_infrastructure_closure_record(closure)
    material = _static_scan_material_from_resolved(
        resolver.resolved,
        closure_bundle_sha256=validated.bundle_sha256,
    )
    object.__setattr__(validated, "_static_scan_material", material)
    return validated


def _static_json_integer(token: str) -> int:
    digits = token[1:] if token.startswith("-") else token
    maximum_decimal_digits = (
        _STATIC_SCAN_INTEGER_BITS_LIMIT * 30_103 // 100_000
    ) + 1
    if len(digits) > maximum_decimal_digits:
        raise _ContractError(
            "scientific definition canonical JSON integer exceeds the bound"
        )
    value = int(token)
    if value.bit_length() > _STATIC_SCAN_INTEGER_BITS_LIMIT:
        raise _ContractError(
            "scientific definition canonical JSON integer exceeds the bound"
        )
    return value


def _static_exact_builtin_json_bytes(value: object) -> bytes:
    if _static_constant_size_upper(value) is None:
        raise _ContractError(
            "scientific definition canonical text is not exact built-in JSON"
        )
    stack = [(value, 0)]
    steps = 0
    while stack:
        item, depth = stack.pop()
        steps += 1
        if steps > _STATIC_SCAN_NODE_LIMIT:
            raise _ContractError(
                "scientific definition canonical text exceeds the node bound"
            )
        if depth > _STATIC_SCAN_DEPTH_LIMIT:
            raise _ContractError(
                "scientific definition canonical text exceeds the depth bound"
            )
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise _ContractError(
                    "scientific definition canonical text is not exact "
                    "built-in JSON"
                )
            stack.extend((key, depth + 1) for key in item)
            stack.extend((nested, depth + 1) for nested in item.values())
        elif type(item) is list:
            stack.extend((nested, depth + 1) for nested in item)
        elif item is None or type(item) in (bool, int, float, str):
            continue
        else:
            raise _ContractError(
                "scientific definition canonical text is not exact built-in JSON"
            )
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
        raise _ContractError(
            "scientific definition canonical text is not exact built-in JSON"
        ) from error
    _static_preflight_output_size(len(encoded))
    return encoded


def _scan_policy_forbidden_structures(
    value: object,
    *,
    role: str,
    path: tuple[str, ...] = (),
    parsed_text_depth: int = 0,
) -> None:
    material_budget = [0]
    _scan_policy_forbidden_structures_with_budget(
        value,
        role=role,
        path=path,
        parsed_text_depth=parsed_text_depth,
        material_budget=material_budget,
    )


def _scan_policy_forbidden_structures_with_budget(
    value: object,
    *,
    role: str,
    path: tuple[str, ...],
    parsed_text_depth: int,
    material_budget: list[int],
) -> None:
    if type(value) is _FrozenJsonObject:
        policy_items = _static_scan_exact_frozen_items(
            value,
            "scientific definition policy object",
            _STATIC_SCAN_NODE_LIMIT,
        )
    elif parsed_text_depth and type(value) is dict:
        policy_items = tuple(value.items())
    else:
        policy_items = None
    if policy_items is not None:
        items = {key: item for key, item in policy_items}
        if (
            role == "oracle"
            and path == ("input_schema",)
            and items.get("required") is not True
        ):
            raise _ContractError(
                "scientific definition has a weakened domain policy"
            )
        for key, item in policy_items:
            tokens = _lexical_tokens(key)
            if tokens & {
                "fingerprint",
                "fingerprints",
                "lookup",
                "categorical",
            }:
                raise _ContractError(
                    "scientific definition contains a forbidden policy "
                    "structure"
                )
            if tokens & {"derivation", "expression", "formula"}:
                raise _ContractError(
                    "scientific definition contains an arbitrary "
                    "derivation expression"
                )
            if "branch" in tokens and tokens & {
                "adapter",
                "benchmark",
                "id",
            }:
                raise _ContractError(
                    "scientific definition contains a benchmark or adapter "
                    "branch"
                )
            if {"canonical", "points"} <= tokens:
                raise _ContractError(
                    "scientific definition contains fixed canonical points"
                )
            if {"post", "hoc", "threshold"} <= tokens:
                raise _ContractError(
                    "scientific definition contains a post-hoc threshold"
                )
            if {"proof", "kind"} <= tokens and (
                type(item) is not str
                or item not in _adapters.OUTPUT_PROOF_KINDS
            ):
                raise _ContractError(
                    "scientific definition contains an unknown proof kind"
                )
            _scan_policy_forbidden_structures_with_budget(
                item,
                role=role,
                path=path + (key,),
                parsed_text_depth=parsed_text_depth,
                material_budget=material_budget,
            )
        return
    if type(value) is tuple or (
        parsed_text_depth and type(value) is list
    ):
        for item in value:
            _scan_policy_forbidden_structures_with_budget(
                item,
                role=role,
                path=path,
                parsed_text_depth=parsed_text_depth,
                material_budget=material_budget,
            )
        return
    if (
        type(value) is float
        and math.isfinite(value)
        and path[-1:] != ("secondary_bound",)
    ):
        significant_digits = _NON_DECIMAL_DIGIT_PATTERN.sub(
            "", repr(abs(value)).split("e", 1)[0]
        ).lstrip("0")
        if len(significant_digits) > 10:
            raise _ContractError(
                "scientific definition contains a numeric fingerprint"
            )
    if type(value) is str:
        normalized = value.strip().lower()
        if parsed_text_depth >= _STATIC_SCAN_DEPTH_LIMIT:
            raise _ContractError(
                "scientific definition canonical text exceeds the depth bound"
            )
        try:
            source_bytes = value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise _ContractError(
                "scientific definition canonical text is not UTF-8"
            ) from error
        if len(source_bytes) > _STATIC_SCAN_LITERAL_BYTES_LIMIT:
            raise _ContractError(
                "scientific definition canonical text exceeds the byte bound"
            )
        try:
            parsed = json.loads(
                value.strip(),
                parse_int=_static_json_integer,
                parse_constant=lambda _token: (_ for _ in ()).throw(
                    ValueError("non-finite JSON")
                ),
            )
        except _ContractError:
            raise
        except (TypeError, ValueError, RecursionError):
            parsed = _STATIC_CONSTANT_UNAVAILABLE
        if parsed is not _STATIC_CONSTANT_UNAVAILABLE:
            try:
                parsed_bytes = _static_exact_builtin_json_bytes(parsed)
                is_canonical_text = parsed_bytes == (
                    value.strip().encode("utf-8")
                )
            except _ContractError:
                raise
            except (
                TypeError,
                ValueError,
                UnicodeEncodeError,
                RecursionError,
            ):
                is_canonical_text = False
            if is_canonical_text:
                layer_material = len(source_bytes) + len(parsed_bytes)
                remaining_material = (
                    _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT
                    - material_budget[0]
                )
                if layer_material > remaining_material:
                    raise _ContractError(
                        "scientific definition canonical text exceeds the "
                        "material bound"
                    )
                material_budget[0] += layer_material
                _scan_policy_forbidden_structures_with_budget(
                    parsed,
                    role=role,
                    path=path,
                    parsed_text_depth=parsed_text_depth + 1,
                    material_budget=material_budget,
                )
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
        normalized_literal = _WHITESPACE_OR_HYPHEN_PATTERN.sub(
            "_", normalized
        )
        if normalized_literal in categorical_answer_literals:
            raise _ContractError(
                "scientific definition contains a categorical answer "
                "literal"
            )
        if "weakened" in _lexical_tokens(normalized):
            raise _ContractError(
                "scientific definition has a weakened domain policy"
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
                "scientific definition contains an arbitrary expression"
            )


_ORACLE_CONVERGENCE_REQUIRED_FIELDS = frozenset({"kind", "rule"})
_ORACLE_CONVERGENCE_ALLOWED_FIELDS = frozenset(
    {"kind", "rule", "secondary_bound"}
)
_ORACLE_CONVERGENCE_KIND = "residual_bound"
_ORACLE_CONVERGENCE_RULE = (
    "independent residual contracts under refinement"
)


def _validate_closed_oracle_convergence_contract(value: object) -> None:
    field_name = "oracle convergence policy contract"
    if type(value) is not _FrozenJsonObject:
        raise _ContractError(f"{field_name} must be an exact frozen object")
    supplied_fields = set(value)
    missing_fields = _ORACLE_CONVERGENCE_REQUIRED_FIELDS - supplied_fields
    unknown_fields = supplied_fields - _ORACLE_CONVERGENCE_ALLOWED_FIELDS
    if missing_fields:
        raise _ContractError(
            f"{field_name} is missing required field "
            f"{sorted(missing_fields)[0]}"
        )
    if unknown_fields:
        raise _ContractError(
            f"{field_name} contains unknown closed-policy field "
            f"{sorted(unknown_fields)[0]}"
        )
    if (
        type(value["kind"]) is not str
        or value["kind"] != _ORACLE_CONVERGENCE_KIND
    ):
        raise _ContractError(f"{field_name}.kind is not closed")
    if (
        type(value["rule"]) is not str
        or value["rule"] != _ORACLE_CONVERGENCE_RULE
    ):
        raise _ContractError(f"{field_name}.rule is not closed")
    if "secondary_bound" in value:
        secondary_bound = value["secondary_bound"]
        if (
            type(secondary_bound) not in (int, float)
            or secondary_bound <= 0
        ):
            raise _ContractError(
                f"{field_name}.secondary_bound must be a positive number"
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
            "scanner_version": _STATIC_SCANNER_VERSION,
            "scanner_sha256": _current_static_scanner_sha256(),
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
            f"{expected_role} policy has an invalid scientific static scan"
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
        _validate_closed_oracle_convergence_contract(
            canonical_definition.convergence_invariant_contract
        )
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
        canonical_payload,
        role=normalized_role,
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


def _static_scan_exact_frozen_items(
    value: object,
    field_name: str,
    item_limit: int,
) -> tuple[tuple[str, object], ...]:
    if type(value) is not _FrozenJsonObject:
        raise _ContractError(f"{field_name} must be an exact frozen object")
    try:
        namespace = object.__getattribute__(value, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(
            f"{field_name} frozen storage is not exact"
        ) from error
    if type(namespace) is not dict or set(namespace) != {"_items"}:
        raise _ContractError(f"{field_name} frozen storage is not exact")
    items = namespace["_items"]
    if type(items) is not tuple:
        raise _ContractError(f"{field_name} frozen storage is not exact")
    if len(items) > item_limit:
        raise _ContractError(f"{field_name} exceeds the closed bound")
    seen_keys = set()
    keys = []
    for pair in items:
        if type(pair) is not tuple or len(pair) != 2:
            raise _ContractError(f"{field_name} frozen storage is not exact")
        key, _item = pair
        if type(key) is not str or key in seen_keys:
            raise _ContractError(f"{field_name} frozen storage is not exact")
        seen_keys.add(key)
        keys.append(key)
    if keys != sorted(keys):
        raise _ContractError(
            f"{field_name} frozen storage is not canonical"
        )
    return items


def _preflight_static_scan_checks(
    value: object,
    role: str,
) -> dict[str, dict[str, object]]:
    def bounded_keys(
        mapping: Mapping[object, object],
        claimed_count: int,
        absolute_limit: int,
    ) -> list[object]:
        if claimed_count > absolute_limit:
            raise _ContractError(
                "static scan checks exceed the closed bound"
            )
        keys = []
        try:
            iterator = iter(mapping)
            for _index in range(claimed_count + 1):
                try:
                    key = next(iterator)
                except StopIteration:
                    break
                keys.append(key)
        except Exception as error:
            raise _ContractError(
                "static scan checks cannot be inspected"
            ) from error
        if len(keys) != claimed_count:
            raise _ContractError(
                "static scan checks have an inconsistent cardinality"
            )
        return keys

    expected_checks = set(_STATIC_SCAN_COMMON_CHECKS)
    if role == "infrastructure":
        expected_checks.add(_STATIC_SCAN_INFRASTRUCTURE_CHECK)
    if type(value) is _FrozenJsonObject:
        check_items = _static_scan_exact_frozen_items(
            value,
            "static scan checks",
            _STATIC_SCAN_CHECK_LIMIT,
        )
        if {key for key, _item in check_items} != expected_checks:
            raise _ContractError(
                "static scan checks are not the exact closed set"
            )
        normalized = {}
        for check_name, item in check_items:
            item_items = _static_scan_exact_frozen_items(
                item, "static scan check", 2
            )
            if {key for key, _item in item_items} != {
                "passed",
                "reason",
            }:
                raise _ContractError(
                    "static scan checks have an unknown shape"
                )
            item_values = {key: item_value for key, item_value in item_items}
            passed = _require_bool(
                item_values["passed"], "static scan check passed"
            )
            reason = item_values["reason"]
            if type(reason) is not str or not reason:
                raise _ContractError(
                    "static scan check reason must be nonempty text"
                )
            if len(reason) > _STATIC_SCAN_REASON_BYTES_LIMIT:
                raise _ContractError(
                    "static scan check reason exceeds the closed bound"
                )
            if len(reason.encode("utf-8")) > (
                _STATIC_SCAN_REASON_BYTES_LIMIT
            ):
                raise _ContractError(
                    "static scan check reason exceeds the closed bound"
                )
            normalized[check_name] = {
                "passed": passed,
                "reason": reason,
            }
        return {
            check_name: dict.__getitem__(normalized, check_name)
            for check_name in sorted(normalized)
        }
    if not isinstance(value, Mapping):
        raise _ContractError("static scan checks have an unknown shape")
    try:
        check_count = len(value)
    except Exception as error:
        raise _ContractError(
            "static scan checks cannot be bounded"
        ) from error
    try:
        supplied_checks = set(
            bounded_keys(
                value,
                check_count,
                _STATIC_SCAN_CHECK_LIMIT,
            )
        )
    except Exception as error:
        raise _ContractError(
            "static scan checks cannot be inspected"
        ) from error
    if supplied_checks != expected_checks:
        raise _ContractError(
            "static scan checks are not the exact closed set"
        )
    normalized = {}
    try:
        for check_name in expected_checks:
            item = value[check_name]
            if not isinstance(item, Mapping):
                raise _ContractError(
                    "static scan checks have an unknown shape"
                )
            item_count = len(item)
            if set(bounded_keys(item, item_count, 2)) != {
                "passed",
                "reason",
            }:
                raise _ContractError(
                    "static scan checks have an unknown shape"
                )
            passed = _require_bool(
                item["passed"], "static scan check passed"
            )
            reason = item["reason"]
            if type(reason) is not str or not reason:
                raise _ContractError(
                    "static scan check reason must be nonempty text"
                )
            if len(reason) > _STATIC_SCAN_REASON_BYTES_LIMIT:
                raise _ContractError(
                    "static scan check reason exceeds the closed bound"
                )
            if len(reason.encode("utf-8")) > (
                _STATIC_SCAN_REASON_BYTES_LIMIT
            ):
                raise _ContractError(
                    "static scan check reason exceeds the closed bound"
                )
            normalized[check_name] = {
                "passed": passed,
                "reason": reason,
            }
    except _ContractError:
        raise
    except Exception as error:
        raise _ContractError(
            "static scan checks cannot be inspected"
        ) from error
    return {
        check_name: dict.__getitem__(normalized, check_name)
        for check_name in sorted(normalized)
    }


def _static_scan_frozen_from_items(
    items: tuple[tuple[str, object], ...],
    field_name: str,
    item_limit: int,
) -> _FrozenJsonObject:
    if type(items) is not tuple or len(items) > item_limit:
        raise _ContractError(f"{field_name} frozen storage is not exact")
    keys = []
    for pair in items:
        if type(pair) is not tuple or len(pair) != 2:
            raise _ContractError(f"{field_name} frozen storage is not exact")
        key, _item = pair
        if type(key) is not str:
            raise _ContractError(f"{field_name} frozen storage is not exact")
        keys.append(key)
    if len(set(keys)) != len(keys) or keys != sorted(keys):
        raise _ContractError(
            f"{field_name} frozen storage is not canonical"
        )
    value = object.__new__(_FrozenJsonObject)
    try:
        namespace = object.__getattribute__(value, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(
            f"{field_name} frozen storage is not exact"
        ) from error
    if type(namespace) is not dict or namespace:
        raise _ContractError(f"{field_name} frozen storage is not exact")
    dict.__setitem__(namespace, "_items", items)
    if set(namespace) != {"_items"} or (
        dict.__getitem__(namespace, "_items") is not items
    ):
        raise _ContractError(f"{field_name} frozen storage is not exact")
    return value


def _freeze_preflighted_static_scan_checks(
    value: dict[str, dict[str, object]],
) -> _FrozenJsonObject:
    if type(value) is not dict or len(value) > _STATIC_SCAN_CHECK_LIMIT:
        raise _ContractError("static scan checks have an unknown shape")
    frozen_items = []
    for check_name in sorted(value):
        if type(check_name) is not str:
            raise _ContractError("static scan checks have an unknown shape")
        check = dict.__getitem__(value, check_name)
        if type(check) is not dict or set(check) != {"passed", "reason"}:
            raise _ContractError("static scan checks have an unknown shape")
        passed = dict.__getitem__(check, "passed")
        reason = dict.__getitem__(check, "reason")
        if type(passed) is not bool or type(reason) is not str:
            raise _ContractError("static scan checks have an unknown shape")
        frozen_check = _static_scan_frozen_from_items(
            (("passed", passed), ("reason", reason)),
            "static scan check",
            2,
        )
        frozen_items.append((check_name, frozen_check))
    return _static_scan_frozen_from_items(
        tuple(frozen_items),
        "static scan checks",
        _STATIC_SCAN_CHECK_LIMIT,
    )


def _static_scan_report_sha256(payload: dict[str, object]) -> str:
    field_names = (
        "schema_version",
        "role",
        "scanner_version",
        "scanner_sha256",
        "scanned_closure_sha256",
        "fingerprint_commitment_sha256",
        "checks",
        "passed",
    )
    if type(payload) is not dict or set(payload) != set(field_names):
        raise _ContractError("static scan report payload is not exact")
    canonical_payload = {}
    for field_name in field_names:
        value = dict.__getitem__(payload, field_name)
        if field_name == "checks":
            if type(value) is not dict:
                raise _ContractError(
                    "static scan report checks are not exact built-in data"
                )
            canonical_checks = {}
            for check_name in sorted(value):
                check = dict.__getitem__(value, check_name)
                if (
                    type(check_name) is not str
                    or type(check) is not dict
                    or set(check) != {"passed", "reason"}
                    or type(dict.__getitem__(check, "passed")) is not bool
                    or type(dict.__getitem__(check, "reason")) is not str
                ):
                    raise _ContractError(
                        "static scan report checks are not exact built-in data"
                    )
                canonical_checks[check_name] = {
                    "passed": dict.__getitem__(check, "passed"),
                    "reason": dict.__getitem__(check, "reason"),
                }
            value = canonical_checks
        elif field_name == "passed":
            if type(value) is not bool:
                raise _ContractError("static scan report payload is not exact")
        elif type(value) is not str:
            raise _ContractError("static scan report payload is not exact")
        canonical_payload[field_name] = value
    try:
        canonical_bytes = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
        raise _ContractError(
            "static scan report payload is not canonical"
        ) from error
    return hashlib.sha256(canonical_bytes).hexdigest()


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
        if self.scanner_version != _STATIC_SCANNER_VERSION:
            raise _ContractError(
                "StaticScanReport has an unsupported scanner version"
            )
        for field_name in (
            "scanner_sha256",
            "scanned_closure_sha256",
            "fingerprint_commitment_sha256",
            "report_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        preflight_checks = _preflight_static_scan_checks(
            self.checks, self.role
        )
        if self.scanner_sha256 != _current_static_scanner_sha256():
            raise _ContractError(
                "StaticScanReport has an unsupported scanner commitment"
            )
        passed = _require_bool(self.passed, "passed")
        all_checks_passed = all(
            dict.__getitem__(check, "passed")
            for check in dict.values(preflight_checks)
        )
        if passed != all_checks_passed:
            raise _ContractError(
                "static scan pass status does not match its checks"
            )
        payload = {
            "schema_version": self.schema_version,
            "role": self.role,
            "scanner_version": self.scanner_version,
            "scanner_sha256": self.scanner_sha256,
            "scanned_closure_sha256": self.scanned_closure_sha256,
            "fingerprint_commitment_sha256": (
                self.fingerprint_commitment_sha256
            ),
            "checks": preflight_checks,
            "passed": passed,
        }
        if self.report_sha256 != _static_scan_report_sha256(payload):
            raise _ContractError("static scan report hash mismatch")
        checks = _freeze_preflighted_static_scan_checks(preflight_checks)
        object.__setattr__(self, "checks", checks)


_SMALL_MATHEMATICAL_LITERALS = frozenset(
    {-2, -1, -0.5, 0, 0.5, 1, 2}
)
_STATIC_FORBIDDEN_NAME_TOKENS = frozenset(
    {
        "answer",
        "evidence",
        "expected",
        "registry",
        "report",
        "result",
        "target",
        "verdict",
    }
)
_STATIC_NATIVE_CALL_SUFFIXES = frozenset(
    {
        "cdll",
        "dlopen",
        "from_cython",
        "load_library",
        "loadlibrary",
        "lowlevelcallable",
    }
)
_STATIC_NUMPY_FILE_CALLABLES = frozenset(
    {
        "datasource",
        "fromfile",
        "fromregex",
        "genfromtxt",
        "load",
        "loadtxt",
        "memmap",
        "npzfile",
        "open_memmap",
        "recfromcsv",
        "recfromtxt",
        "save",
        "savetxt",
        "savez",
        "savez_compressed",
        "tofile",
    }
)
_STATIC_FORBIDDEN_CAPABILITY_NAMESPACES = (
    ("scipy", "io"),
)
_STATIC_SAFE_NUMERIC_CONSTANT_PATHS = frozenset(
    {
        ("numpy", "e"),
        ("numpy", "inf"),
        ("numpy", "nan"),
        ("numpy", "pi"),
    }
)
_STATIC_SAFE_NUMERIC_CALLABLE_PATHS = frozenset(
    {
        ("numpy", "array"),
        ("numpy", "diag"),
        ("numpy", "eye"),
        ("numpy", "kron"),
        ("numpy", "linalg", "eigh"),
        ("numpy", "linalg", "eigvalsh"),
        ("numpy", "linalg", "norm"),
        ("numpy", "max"),
        ("numpy", "sin"),
        ("numpy", "sqrt"),
        ("numpy", "trace"),
        ("numpy", "vdot"),
        ("numpy", "zeros"),
        ("scipy", "integrate", "quad"),
        ("scipy", "linalg", "eigh"),
    }
)
_STATIC_SAFE_NUMERIC_CALLABLE_OBJECT_PATHS = frozenset(
    {
        ("numpy", "sin"),
    }
)
_STATIC_SAFE_STDLIB_CALLABLE_PATHS = frozenset(
    {
        ("decimal", "Decimal"),
        ("math", "asinh"),
        ("math", "atan"),
        ("math", "atan2"),
        ("math", "comb"),
        ("math", "cos"),
        ("math", "cosh"),
        ("math", "exp"),
        ("math", "floor"),
        ("math", "isfinite"),
        ("math", "log"),
        ("math", "sin"),
        ("math", "sinh"),
        ("math", "sqrt"),
        ("string", "Formatter"),
    }
)
_STATIC_SAFE_STDLIB_CONSTANT_PATHS = frozenset()
_STATIC_SAFE_STDLIB_CALLABLE_OBJECT_PATHS = frozenset(
    {
        ("math", "asinh"),
        ("math", "atan"),
        ("math", "atan2"),
        ("math", "comb"),
        ("math", "cos"),
        ("math", "cosh"),
        ("math", "exp"),
        ("math", "floor"),
        ("math", "isfinite"),
        ("math", "log"),
        ("math", "sin"),
        ("math", "sinh"),
        ("math", "sqrt"),
    }
)
_STATIC_SAFE_STDLIB_METHOD_PATHS = frozenset(
    {
        ("string", "Formatter", "parse"),
    }
)
_STATIC_SAFE_OPERATOR_CALLABLE_PATHS = frozenset()


def _validate_static_fingerprints(value: object) -> tuple[str, ...]:
    if (
        type(value) is tuple
        and len(value) > _STATIC_SCAN_FINGERPRINT_COUNT_LIMIT
    ):
        raise _ContractError(
            "forbidden fingerprint count exceeds the closed bound"
        )
    fingerprints = _snapshot_sha256_tuple(
        value, "forbidden_fingerprints"
    )
    if not fingerprints:
        raise _ContractError("forbidden fingerprints must be nonempty")
    if len(set(fingerprints)) != len(fingerprints):
        raise _ContractError("forbidden fingerprints contain a duplicate")
    if fingerprints != tuple(sorted(fingerprints)):
        raise _ContractError(
            "forbidden fingerprints must use canonical ordering"
        )
    return fingerprints


def _validate_static_scan_material(
    closure: ScientificClosure | InfrastructureClosure,
    material: object,
) -> _StaticScanMaterial:
    if type(material) is not _StaticScanMaterial:
        raise _ContractError(
            "static scan requires builder-produced private material"
        )
    if material.closure_bundle_sha256 != closure.bundle_sha256:
        raise _ContractError("static scan material closure hash mismatch")
    if type(material.nodes) is not tuple or len(material.nodes) != len(
        closure.nodes
    ):
        raise _ContractError("static scan material node order mismatch")
    if len(material.nodes) > _STATIC_SCAN_NODE_LIMIT:
        raise _ContractError("static scan material exceeds the node bound")
    raw_bytes = 0
    emitted_bytes = 0
    for index, private_node in enumerate(material.nodes):
        if type(private_node) is not _StaticScanNodeMaterial:
            raise _ContractError("static scan material node is not exact")
        if (
            type(private_node.raw_source_span) is not bytes
            or type(private_node.emitted_node) is not bytes
        ):
            raise _ContractError("static scan material bytes are not exact")
        raw_bytes += len(private_node.raw_source_span)
        emitted_bytes += len(private_node.emitted_node) + bool(index)
        _preflight_static_material_totals(raw_bytes, emitted_bytes)
    if type(material.emitted_source) is not bytes:
        raise _ContractError("static scan emitted module bytes are not exact")
    _preflight_static_material_totals(
        raw_bytes, len(material.emitted_source)
    )
    emitted_nodes = []
    for manifest, private_node in zip(closure.nodes, material.nodes):
        if type(private_node) is not _StaticScanNodeMaterial:
            raise _ContractError("static scan material node is not exact")
        if isinstance(closure, ScientificClosure):
            material_module = private_node.qualified_name.rsplit(".", 1)[0]
            _require_scientific_module_role(
                material_module, closure.role
            )
        if private_node.qualified_name != manifest["qualified_name"]:
            raise _ContractError("static scan material node order mismatch")
        if (
            type(private_node.raw_source_span) is not bytes
            or type(private_node.emitted_node) is not bytes
        ):
            raise _ContractError("static scan material bytes are not exact")
        if (
            len(private_node.raw_source_span)
            > _STATIC_SCAN_LITERAL_BYTES_LIMIT
            or len(private_node.emitted_node)
            > _STATIC_SCAN_LITERAL_BYTES_LIMIT
        ):
            raise _ContractError(
                "static scan material contains an oversized literal"
            )
        if hashlib.sha256(private_node.raw_source_span).hexdigest() != (
            manifest["source_span_sha256"]
        ):
            raise _ContractError("static scan raw span hash mismatch")
        if hashlib.sha256(private_node.emitted_node).hexdigest() != (
            manifest["emitted_node_sha256"]
        ):
            raise _ContractError("static scan emitted node hash mismatch")
        if private_node.emitted_node != _normalized_emitted_node(
            private_node.raw_source_span
        ):
            raise _ContractError(
                "static scan raw and emitted node material disagree"
            )
        emitted_nodes.append(private_node.emitted_node)
    expected_emitted_source = b"\n".join(emitted_nodes)
    if material.emitted_source != expected_emitted_source:
        raise _ContractError("static scan emitted module bytes mismatch")
    emitted_source_sha256 = hashlib.sha256(
        material.emitted_source
    ).hexdigest()
    if material.emitted_source_sha256 != emitted_source_sha256:
        raise _ContractError("static scan emitted module hash mismatch")
    if isinstance(closure, ScientificClosure) and (
        closure.emitted_source_sha256 != emitted_source_sha256
    ):
        raise _ContractError("static scan closure emitted hash mismatch")
    return material


def _static_ast_depth(
    tree: ast.AST,
    *,
    node_limit: int | None = None,
    depth_limit: int | None = None,
) -> int:
    if node_limit is None:
        node_limit = _STATIC_SCAN_NODE_LIMIT
    if depth_limit is None:
        depth_limit = _STATIC_SCAN_DEPTH_LIMIT
    maximum = 0
    stack = [(tree, 1)]
    steps = 0
    while stack:
        node, depth = stack.pop()
        steps += 1
        if steps > node_limit:
            raise _ContractError("static scan AST exceeds the node bound")
        if depth > depth_limit:
            raise _ContractError("static scan AST exceeds the depth bound")
        maximum = max(maximum, depth)
        stack.extend(
            (child, depth + 1) for child in ast.iter_child_nodes(node)
        )
    return maximum


def _static_call_path(value: ast.AST) -> tuple[str, ...]:
    parts = []
    current = value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def _static_import_aliases(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    if not isinstance(tree, ast.Module):
        return {}
    nodes = tuple(ast.walk(tree))
    if len(nodes) > _STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT:
        raise _ContractError("static scan alias graph exceeds the node bound")
    aliases: dict[str, tuple[str, ...]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                target = tuple(alias.name.split("."))
                local_name = alias.asname or target[0]
                aliases[local_name] = (
                    target if alias.asname else (target[0],)
                )
        elif isinstance(statement, ast.ImportFrom) and statement.level == 0:
            if statement.module is None:
                continue
            module = tuple(statement.module.split("."))
            for alias in statement.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                aliases[local_name] = (
                    *module,
                    alias.name,
                )
    return aliases


def _static_resolved_call_path(
    value: ast.AST,
    aliases: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return _static_resolved_reference_path(value, aliases)


def _static_resolved_reference_path(
    value: ast.AST,
    aliases: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    authored = _static_call_path(value)
    if not authored:
        return ()
    prefix = aliases.get(authored[0])
    if prefix is None:
        return authored
    return (*prefix, *authored[1:])


def _static_forbidden_capability_path(path: tuple[str, ...]) -> bool:
    if not path:
        return False
    folded_path = tuple(part.casefold() for part in path)
    if folded_path[0] == "numpy" and any(
        part in _STATIC_NUMPY_FILE_CALLABLES for part in folded_path[1:]
    ):
        return True
    return any(
        folded_path[: len(namespace)] == namespace
        for namespace in _STATIC_FORBIDDEN_CAPABILITY_NAMESPACES
    )


def _static_module_object_path(path: tuple[str, ...]) -> bool:
    return ".".join(path) in _SAFE_EXTERNAL_IMPORT_MODULES


def _static_safe_external_symbol_paths() -> frozenset[tuple[str, ...]]:
    paths = frozenset(
        {
            *_STATIC_SAFE_NUMERIC_CONSTANT_PATHS,
            *_STATIC_SAFE_NUMERIC_CALLABLE_PATHS,
            *_STATIC_SAFE_NUMERIC_CALLABLE_OBJECT_PATHS,
            *_STATIC_SAFE_STDLIB_CALLABLE_PATHS,
            *_STATIC_SAFE_STDLIB_CONSTANT_PATHS,
            *_STATIC_SAFE_STDLIB_CALLABLE_OBJECT_PATHS,
        }
    )
    if any(
        type(path) is not tuple
        or len(path) < 2
        or any(type(part) is not str or not part for part in path)
        for path in paths
    ):
        raise _ContractError(
            "safe external symbol policy is not exact"
        )
    return paths


def _static_safe_external_import_symbol(path: tuple[str, ...]) -> bool:
    return path in _static_safe_external_symbol_paths()


def _static_external_module_has_safe_descendant(
    module_name: str,
) -> bool:
    module_path = tuple(module_name.split("."))
    return any(
        path[: len(module_path)] == module_path
        and len(path) > len(module_path)
        for path in _static_safe_external_symbol_paths()
    )


def _static_stdlib_path(path: tuple[str, ...]) -> bool:
    return bool(path) and path[0] in {"decimal", "math", "string"}


def _static_external_path(path: tuple[str, ...]) -> bool:
    return _static_numpy_scipy_path(path) or _static_stdlib_path(path)


def _static_numpy_scipy_path(path: tuple[str, ...]) -> bool:
    return bool(path) and path[0] in {"numpy", "scipy"}


def _static_operator_path(path: tuple[str, ...]) -> bool:
    return bool(path) and path[0] == "operator"


def _static_target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.List, ast.Tuple)):
        return tuple(
            name
            for element in target.elts
            for name in _static_target_names(element)
        )
    if isinstance(target, ast.Starred):
        return _static_target_names(target.value)
    return ()


def _static_statement_bound_names(statement: ast.stmt) -> tuple[str, ...]:
    if isinstance(statement, ast.Assign):
        return tuple(
            name
            for target in statement.targets
            for name in _static_target_names(target)
        )
    if isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
        return _static_target_names(statement.target)
    if isinstance(
        statement,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    ):
        return (statement.name,)
    return ()


def _scan_static_external_module_flows(
    tree: ast.AST,
    aliases: Mapping[str, tuple[str, ...]],
) -> None:
    """Reject external module objects outside direct approved paths."""

    for path in aliases.values():
        if _static_operator_path(path) and (
            path not in _STATIC_SAFE_OPERATOR_CALLABLE_PATHS
        ):
            raise _ContractError(
                "static scan rejected unapproved operator import"
            )
        if _static_external_path(path) and not (
            _static_module_object_path(path)
            or _static_safe_external_import_symbol(path)
        ):
            raise _ContractError(
                "static scan rejected unapproved external import"
            )

    def validate_reference(
        candidate: ast.AST,
        parent: ast.AST | None,
        active_aliases: Mapping[str, tuple[str, ...]],
        shadowed_names: frozenset[str],
    ) -> None:
        authored = _static_call_path(candidate)
        path = ()
        if authored:
            if authored[0] in shadowed_names:
                return
            path = _static_resolved_reference_path(
                candidate, active_aliases
            )
        elif isinstance(candidate, ast.Attribute) and isinstance(
            candidate.value, ast.Call
        ):
            factory_authored = _static_call_path(
                candidate.value.func
            )
            if (
                not factory_authored
                or factory_authored[0] in shadowed_names
            ):
                return
            factory_path = _static_resolved_call_path(
                candidate.value.func, active_aliases
            )
            path = (*factory_path, candidate.attr)
        else:
            return
        if _static_operator_path(path):
            if (
                isinstance(parent, ast.Call)
                and parent.func is candidate
                and path in _STATIC_SAFE_OPERATOR_CALLABLE_PATHS
            ):
                return
            raise _ContractError(
                "static scan rejected unapproved operator reference"
            )
        if _static_stdlib_path(path):
            if _static_module_object_path(path):
                raise _ContractError(
                    "static scan rejected external module object escape"
                )
            if isinstance(parent, ast.Call) and parent.func is candidate:
                if path in (
                    _STATIC_SAFE_STDLIB_CALLABLE_PATHS
                    | _STATIC_SAFE_STDLIB_METHOD_PATHS
                ):
                    return
                raise _ContractError(
                    "static scan rejected unapproved external stdlib "
                    "callable"
                )
            if path in (
                _STATIC_SAFE_STDLIB_CONSTANT_PATHS
                | _STATIC_SAFE_STDLIB_CALLABLE_OBJECT_PATHS
            ):
                return
            raise _ContractError(
                "static scan rejected unapproved external stdlib reference"
            )
        if not _static_numpy_scipy_path(path):
            return
        if _static_forbidden_capability_path(path):
            raise _ContractError(
                "static scan rejected unapproved file-capable reference"
            )
        if _static_module_object_path(path):
            raise _ContractError(
                "static scan rejected external module object escape"
            )
        if isinstance(parent, ast.Call) and parent.func is candidate:
            if path in _STATIC_SAFE_NUMERIC_CALLABLE_PATHS:
                return
            raise _ContractError(
                "static scan rejected unapproved external numeric callable"
            )
        if path in _STATIC_SAFE_NUMERIC_CONSTANT_PATHS or path in (
            _STATIC_SAFE_NUMERIC_CALLABLE_OBJECT_PATHS
        ):
            return
        raise _ContractError(
            "static scan rejected unapproved external numeric reference"
        )

    def scan_node(
        candidate: ast.AST,
        parent: ast.AST | None,
        active_aliases: dict[str, tuple[str, ...]],
        shadowed_names: frozenset[str],
    ) -> None:
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in candidate.decorator_list:
                scan_node(
                    decorator,
                    candidate,
                    active_aliases,
                    shadowed_names,
                )
            for default in (
                *candidate.args.defaults,
                *(
                    item
                    for item in candidate.args.kw_defaults
                    if item is not None
                ),
            ):
                scan_node(
                    default,
                    candidate,
                    active_aliases,
                    shadowed_names,
                )
            parameter_names = {
                argument.arg
                for argument in (
                    *candidate.args.posonlyargs,
                    *candidate.args.args,
                    *candidate.args.kwonlyargs,
                )
            }
            if candidate.args.vararg is not None:
                parameter_names.add(candidate.args.vararg.arg)
            if candidate.args.kwarg is not None:
                parameter_names.add(candidate.args.kwarg.arg)
            local_aliases = {
                name: path
                for name, path in active_aliases.items()
                if name not in parameter_names
            }
            scan_statements(
                candidate.body,
                local_aliases,
                frozenset((*shadowed_names, *parameter_names)),
            )
            return
        if isinstance(candidate, ast.Name):
            if not isinstance(candidate.ctx, ast.Load):
                return
            if isinstance(parent, ast.Attribute) and (
                parent.value is candidate
            ):
                return
            validate_reference(
                candidate,
                parent,
                active_aliases,
                shadowed_names,
            )
            return
        if isinstance(candidate, ast.Attribute):
            if isinstance(candidate.ctx, (ast.Store, ast.Del)):
                authored = _static_call_path(candidate)
                if authored and authored[0] not in shadowed_names:
                    path = _static_resolved_reference_path(
                        candidate, active_aliases
                    )
                    if _static_external_path(path) or (
                        _static_operator_path(path)
                    ):
                        raise _ContractError(
                            "static scan rejected external module or "
                            "derived-state mutation"
                        )
            if isinstance(candidate.ctx, ast.Load) and not (
                isinstance(parent, ast.Attribute)
                and parent.value is candidate
            ):
                validate_reference(
                    candidate,
                    parent,
                    active_aliases,
                    shadowed_names,
                )
            scan_node(
                candidate.value,
                candidate,
                active_aliases,
                shadowed_names,
            )
            return
        for child in ast.iter_child_nodes(candidate):
            scan_node(
                child,
                candidate,
                active_aliases,
                shadowed_names,
            )

    def scan_statements(
        statements: list[ast.stmt],
        active_aliases: dict[str, tuple[str, ...]],
        initial_shadowed_names: frozenset[str],
    ) -> None:
        shadowed_names = initial_shadowed_names
        for statement in statements:
            scan_node(
                statement,
                None,
                active_aliases,
                shadowed_names,
            )
            bound_names = _static_statement_bound_names(statement)
            if bound_names:
                shadowed_names = frozenset(
                    (*shadowed_names, *bound_names)
                )
                for name in bound_names:
                    active_aliases.pop(name, None)

    if isinstance(tree, ast.Module):
        scan_statements(list(tree.body), dict(aliases), frozenset())
    else:
        scan_node(tree, None, dict(aliases), frozenset())


_STATIC_CONSTANT_UNAVAILABLE = object()


def _static_constant_size_upper(value: object) -> int | None:
    stack = [value]
    steps = 0
    total = 0
    while stack:
        item = stack.pop()
        steps += 1
        if steps > _STATIC_SCAN_NODE_LIMIT:
            raise _ContractError(
                "static scan constant expression exceeds the node bound"
            )
        if type(item) is str:
            try:
                total += len(item.encode("utf-8"))
            except UnicodeEncodeError:
                return None
        elif type(item) is bytes:
            total += len(item)
        elif type(item) is int:
            if item.bit_length() > _STATIC_SCAN_INTEGER_BITS_LIMIT:
                raise _ContractError(
                    "static scan constant integer exceeds the bound"
                )
            total += max(1, item.bit_length()) + 2
        elif type(item) is float:
            if not math.isfinite(item):
                return None
            total += 32
        elif item is None or type(item) is bool:
            total += 5
        elif type(item) in (tuple, list):
            if len(item) > _STATIC_SCAN_NODE_LIMIT:
                raise _ContractError(
                    "static scan constant container exceeds the bound"
                )
            total += (8 * len(item)) + 2
            stack.extend(item)
        elif type(item) is dict:
            if len(item) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
                raise _ContractError(
                    "static scan constant mapping exceeds the lookup bound"
                )
            if any(type(key) is not str for key in item):
                return None
            total += (32 * len(item)) + 2
            stack.extend(item.keys())
            stack.extend(item.values())
        else:
            return None
        if total > _STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT:
            raise _ContractError(
                "static scan constant output exceeds the byte bound"
            )
    return total


def _static_constant_is_bounded(value: object) -> bool:
    return _static_constant_size_upper(value) is not None


def _static_preflight_output_size(size: int) -> None:
    if size > _STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT:
        raise _ContractError(
            "static scan constant output allocation exceeds the byte bound"
        )


def _static_format_decimal_value(digits: str) -> int:
    normalized = digits.lstrip("0") or "0"
    maximum = str(_STATIC_SCAN_FORMAT_WIDTH_LIMIT)
    if len(normalized) > len(maximum) or (
        len(normalized) == len(maximum) and normalized > maximum
    ):
        raise _ContractError(
            "static scan constant format width exceeds the bound"
        )
    return int(normalized)


def _static_closed_format_template(template: str) -> bool:
    try:
        parsed = string.Formatter().parse(template)
    except ValueError:
        return False
    field_count = 0
    try:
        for _literal, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            field_count += 1
            if field_count > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
                raise _ContractError(
                    "static scan constant format exceeds the field bound"
                )
            if field_name and not (
                field_name.isdecimal() or field_name.isidentifier()
            ):
                return False
            if conversion not in (None, "a", "r", "s"):
                return False
            if "{" in format_spec or "}" in format_spec:
                return False
            for digits in _DECIMAL_DIGIT_SEQUENCE_PATTERN.findall(
                format_spec
            ):
                _static_format_decimal_value(digits)
    except _ContractError:
        raise
    except ValueError:
        return False
    return True


def _static_closed_percent_template(template: str | bytes) -> bool:
    if type(template) is bytes:
        text = template.decode("latin-1")
    else:
        text = template
    if "*" in text:
        return False
    for digits in _DECIMAL_DIGIT_SEQUENCE_PATTERN.findall(text):
        _static_format_decimal_value(digits)
    return True


def _static_safe_format_scalar(value: object) -> bool:
    return value is None or type(value) in (
        bool,
        int,
        float,
        str,
        bytes,
    )


def _static_scalar_render_size_upper(value: object) -> int | None:
    if not _static_safe_format_scalar(value):
        return None
    size = _static_constant_size_upper(value)
    if size is None:
        return None
    return (12 * size) + 128


def _static_format_output_size_upper(
    template: str,
    arguments: tuple[object, ...],
    keywords: Mapping[str, object],
) -> int | None:
    if any(
        not _static_safe_format_scalar(value)
        for value in (*arguments, *keywords.values())
    ):
        return None
    try:
        parsed = string.Formatter().parse(template)
    except ValueError:
        return None
    render_bounds = tuple(
        _static_scalar_render_size_upper(value)
        for value in (*arguments, *keywords.values())
    )
    if any(bound is None for bound in render_bounds):
        return None
    maximum_render = max(render_bounds, default=0)
    total = 0
    field_count = 0
    try:
        for literal, field_name, format_spec, _conversion in parsed:
            total += len(literal.encode("utf-8"))
            if field_name is None:
                continue
            field_count += 1
            if field_count > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
                raise _ContractError(
                    "static scan constant format exceeds the field bound"
                )
            total += maximum_render
            total += 4 * sum(
                _static_format_decimal_value(digits)
                for digits in _DECIMAL_DIGIT_SEQUENCE_PATTERN.findall(
                    format_spec
                )
            )
            total += 128
            _static_preflight_output_size(total)
    except _ContractError:
        raise
    except ValueError:
        return None
    return total


def _static_percent_output_size_upper(
    template: str | bytes,
    operand: object,
) -> int | None:
    if type(operand) is tuple:
        values = operand
    elif type(operand) is dict:
        values = tuple(operand.values())
    else:
        values = (operand,)
    if any(not _static_safe_format_scalar(value) for value in values):
        return None
    render_bounds = tuple(
        _static_scalar_render_size_upper(value) for value in values
    )
    if any(bound is None for bound in render_bounds):
        return None
    maximum_render = max(render_bounds, default=0)
    if type(template) is bytes:
        text = template.decode("latin-1")
        total = len(template)
    else:
        text = template
        total = len(template.encode("utf-8"))
    field_count = 0
    index = 0
    while index < len(text):
        if text[index] != "%":
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == "%":
            index += 2
            continue
        field_count += 1
        index += 1
    if field_count > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
        raise _ContractError(
            "static scan constant format exceeds the field bound"
        )
    total += field_count * (maximum_render + 128)
    total += sum(
        _static_format_decimal_value(digits)
        for digits in _DECIMAL_DIGIT_SEQUENCE_PATTERN.findall(text)
    )
    return total


def _static_constant_slice(
    node: ast.AST,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if isinstance(node, ast.Slice):
        values = []
        for part in (node.lower, node.upper, node.step):
            if part is None:
                values.append(None)
                continue
            value = _static_constant_expression(part, cache, steps)
            if value is _STATIC_CONSTANT_UNAVAILABLE or type(value) is not int:
                return _STATIC_CONSTANT_UNAVAILABLE
            values.append(value)
        if values[2] == 0:
            return _STATIC_CONSTANT_UNAVAILABLE
        return slice(*values)
    index = _static_constant_expression(node, cache, steps)
    if type(index) not in (int, str):
        return _STATIC_CONSTANT_UNAVAILABLE
    return index


def _static_safe_truth_value(value: object) -> bool | None:
    if value is None or type(value) in (
        bool,
        int,
        float,
        str,
        bytes,
        tuple,
        list,
        dict,
    ):
        return bool(value)
    return None


def _static_constant_compare(
    node: ast.Compare,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    values = [
        _static_constant_expression(node.left, cache, steps),
        *(
            _static_constant_expression(item, cache, steps)
            for item in node.comparators
        ),
    ]
    if any(value is _STATIC_CONSTANT_UNAVAILABLE for value in values):
        return _STATIC_CONSTANT_UNAVAILABLE
    try:
        for left, operator, right in zip(values, node.ops, values[1:]):
            if isinstance(operator, ast.Eq):
                passed = type(left) is type(right) and left == right
            elif isinstance(operator, ast.NotEq):
                passed = type(left) is not type(right) or left != right
            elif isinstance(operator, ast.Lt):
                passed = left < right
            elif isinstance(operator, ast.LtE):
                passed = left <= right
            elif isinstance(operator, ast.Gt):
                passed = left > right
            elif isinstance(operator, ast.GtE):
                passed = left >= right
            elif isinstance(operator, ast.In):
                passed = left in right
            elif isinstance(operator, ast.NotIn):
                passed = left not in right
            elif isinstance(operator, ast.Is):
                passed = left is right
            elif isinstance(operator, ast.IsNot):
                passed = left is not right
            else:
                return _STATIC_CONSTANT_UNAVAILABLE
            if not passed:
                return False
        return True
    except (TypeError, ValueError):
        return _STATIC_CONSTANT_UNAVAILABLE


def _static_preflight_mapping_merge(
    left: Mapping[str, object],
    right: Mapping[str, object],
    *,
    reject_overlap: bool,
) -> int:
    left_keys = set(left)
    right_keys = set(right)
    overlap = left_keys & right_keys
    if reject_overlap and overlap:
        raise _ContractError(
            "static scan constant mapping has ambiguous keys"
        )
    projected_entries = len(left_keys) + len(right_keys) - len(overlap)
    if projected_entries > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
        raise _ContractError(
            "static scan mapping projected cardinality exceeds the bound"
        )
    left_size = _static_constant_size_upper(left)
    right_size = _static_constant_size_upper(right)
    if left_size is None or right_size is None:
        raise _ContractError(
            "static scan rejected unsupported constant mapping merge"
        )
    _static_preflight_output_size(left_size + right_size)
    return projected_entries


def _static_constant_binop(
    node: ast.BinOp,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    left = _static_constant_expression(node.left, cache, steps)
    right = _static_constant_expression(node.right, cache, steps)
    if (
        left is _STATIC_CONSTANT_UNAVAILABLE
        or right is _STATIC_CONSTANT_UNAVAILABLE
    ):
        return _STATIC_CONSTANT_UNAVAILABLE
    try:
        if isinstance(node.op, ast.Add):
            if type(left) is type(right) and type(left) in (
                str,
                bytes,
                tuple,
                list,
            ):
                left_size = _static_constant_size_upper(left)
                right_size = _static_constant_size_upper(right)
                if left_size is None or right_size is None:
                    return _STATIC_CONSTANT_UNAVAILABLE
                _static_preflight_output_size(left_size + right_size)
                return left + right
            if (
                type(left) in (int, float)
                and type(right) in (int, float)
            ):
                return left + right
        elif isinstance(node.op, ast.Sub) and (
            type(left) in (int, float) and type(right) in (int, float)
        ):
            return left - right
        elif isinstance(node.op, ast.Mult):
            if (
                type(left) in (str, bytes, tuple, list)
                and type(right) is int
            ):
                left_size = _static_constant_size_upper(left)
                if left_size is None:
                    return _STATIC_CONSTANT_UNAVAILABLE
                repetition_size = (
                    0
                    if right <= 0 or not left
                    else left_size * right
                )
                _static_preflight_output_size(
                    repetition_size
                )
                return left * right
            if (
                type(right) in (str, bytes, tuple, list)
                and type(left) is int
            ):
                right_size = _static_constant_size_upper(right)
                if right_size is None:
                    return _STATIC_CONSTANT_UNAVAILABLE
                repetition_size = (
                    0
                    if left <= 0 or not right
                    else right_size * left
                )
                _static_preflight_output_size(
                    repetition_size
                )
                return right * left
            if (
                type(left) in (int, float)
                and type(right) in (int, float)
            ):
                if (
                    type(left) is int
                    and type(right) is int
                    and left.bit_length() + right.bit_length()
                    > _STATIC_SCAN_INTEGER_BITS_LIMIT
                ):
                    raise _ContractError(
                        "static scan constant integer exceeds the bound"
                    )
                return left * right
        elif isinstance(node.op, ast.Div) and (
            type(left) in (int, float) and type(right) in (int, float)
        ):
            return left / right
        elif isinstance(node.op, ast.FloorDiv) and (
            type(left) in (int, float) and type(right) in (int, float)
        ):
            return left // right
        elif isinstance(node.op, ast.Mod):
            if type(left) in (str, bytes):
                if not _static_closed_percent_template(left):
                    return _STATIC_CONSTANT_UNAVAILABLE
                output_bound = _static_percent_output_size_upper(
                    left, right
                )
                if output_bound is None:
                    raise _ContractError(
                        "static scan rejected constant formatting operand"
                    )
                _static_preflight_output_size(output_bound)
                return left % right
            if (
                type(left) in (int, float)
                and type(right) in (int, float)
            ):
                return left % right
        elif isinstance(node.op, ast.Pow) and (
            type(left) in (int, float)
            and type(right) in (int, float)
            and abs(right) <= 64
        ):
            if (
                type(left) is int
                and type(right) is int
                and right > 0
                and left.bit_length() * right
                > _STATIC_SCAN_INTEGER_BITS_LIMIT
            ):
                raise _ContractError(
                    "static scan constant integer exceeds the bound"
                )
            return left**right
        elif (
            isinstance(node.op, ast.BitOr)
            and type(left) is dict
            and type(right) is dict
        ):
            _static_preflight_mapping_merge(
                left, right, reject_overlap=False
            )
            return left | right
    except _ContractError:
        raise
    except (ArithmeticError, OverflowError, TypeError, ValueError):
        return _STATIC_CONSTANT_UNAVAILABLE
    return _STATIC_CONSTANT_UNAVAILABLE


def _static_constant_joined_string(
    node: ast.JoinedStr,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    parts = []
    output_size = 0
    for part in node.values:
        if isinstance(part, ast.Constant) and type(part.value) is str:
            output_size += len(part.value.encode("utf-8"))
            _static_preflight_output_size(output_size)
            parts.append(part.value)
            continue
        if not isinstance(part, ast.FormattedValue):
            return _STATIC_CONSTANT_UNAVAILABLE
        value = _static_constant_expression(part.value, cache, steps)
        if value is _STATIC_CONSTANT_UNAVAILABLE:
            return _STATIC_CONSTANT_UNAVAILABLE
        if not _static_safe_format_scalar(value):
            raise _ContractError(
                "static scan rejected constant formatting operand"
            )
        if part.format_spec is None:
            format_spec = ""
        else:
            format_spec = _static_constant_expression(
                part.format_spec, cache, steps
            )
            if type(format_spec) is not str:
                return _STATIC_CONSTANT_UNAVAILABLE
        if not _static_closed_format_template("{" + ":" + format_spec + "}"):
            return _STATIC_CONSTANT_UNAVAILABLE
        render_bound = _static_scalar_render_size_upper(value)
        if render_bound is None:
            return _STATIC_CONSTANT_UNAVAILABLE
        projected_size = output_size + render_bound + 128
        projected_size += 4 * sum(
            _static_format_decimal_value(digits)
            for digits in _DECIMAL_DIGIT_SEQUENCE_PATTERN.findall(
                format_spec
            )
        )
        _static_preflight_output_size(projected_size)
        if part.conversion == 115:
            value = str(value)
        elif part.conversion == 114:
            value = repr(value)
        elif part.conversion == 97:
            value = ascii(value)
        elif part.conversion != -1:
            return _STATIC_CONSTANT_UNAVAILABLE
        try:
            formatted = format(value, format_spec)
        except (TypeError, ValueError):
            return _STATIC_CONSTANT_UNAVAILABLE
        output_size += len(formatted.encode("utf-8"))
        _static_preflight_output_size(output_size)
        parts.append(formatted)
    return "".join(parts)


def _static_constant_dict_call(
    node: ast.Call,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if len(node.args) > 1:
        return _STATIC_CONSTANT_UNAVAILABLE
    if len(node.keywords) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
        raise _ContractError(
            "static scan constant mapping exceeds the lookup bound"
        )
    result = {}
    if node.args:
        source = _static_constant_expression(node.args[0], cache, steps)
        if type(source) is dict:
            _static_preflight_mapping_merge(
                result, source, reject_overlap=False
            )
            result.update(source)
        elif type(source) in (tuple, list):
            if len(source) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
                raise _ContractError(
                    "static scan constant mapping exceeds the lookup bound"
                )
            for pair in source:
                if type(pair) not in (tuple, list) or len(pair) != 2:
                    return _STATIC_CONSTANT_UNAVAILABLE
                key, value = pair
                if type(key) is not str:
                    return _STATIC_CONSTANT_UNAVAILABLE
                _static_preflight_mapping_merge(
                    result, {key: value}, reject_overlap=False
                )
                result[key] = value
        else:
            return _STATIC_CONSTANT_UNAVAILABLE
    for keyword in node.keywords:
        if keyword.arg is None:
            value = _static_constant_expression(
                keyword.value, cache, steps
            )
            if type(value) is not dict:
                return _STATIC_CONSTANT_UNAVAILABLE
            _static_preflight_mapping_merge(
                result, value, reject_overlap=True
            )
            result.update(value)
            continue
        value = _static_constant_expression(keyword.value, cache, steps)
        if value is _STATIC_CONSTANT_UNAVAILABLE:
            return _STATIC_CONSTANT_UNAVAILABLE
        _static_preflight_mapping_merge(
            result, {keyword.arg: value}, reject_overlap=False
        )
        result[keyword.arg] = value
    return result


def _static_constant_builtin_call(
    node: ast.Call,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if not isinstance(node.func, ast.Name):
        return _STATIC_CONSTANT_UNAVAILABLE
    name = node.func.id
    if name not in {"bool", "bytes", "float", "int", "list", "str", "tuple"}:
        return _STATIC_CONSTANT_UNAVAILABLE
    if any(keyword.arg is None for keyword in node.keywords):
        raise _ContractError(
            "static scan rejected unsupported constant-producing call"
        )
    arguments = tuple(
        _static_constant_expression(argument, cache, steps)
        for argument in node.args
    )
    keywords = {
        keyword.arg: _static_constant_expression(
            keyword.value, cache, steps
        )
        for keyword in node.keywords
    }
    if any(
        value is _STATIC_CONSTANT_UNAVAILABLE
        for value in (*arguments, *keywords.values())
    ):
        return _STATIC_CONSTANT_UNAVAILABLE
    try:
        if name in {"tuple", "list"}:
            if keywords or len(arguments) > 1:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            source = arguments[0] if arguments else ()
            if type(source) not in (str, bytes, tuple, list, dict):
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            source_size = _static_constant_size_upper(source)
            if source_size is None:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            _static_preflight_output_size(source_size)
            return tuple(source) if name == "tuple" else list(source)
        if name == "bytes":
            if set(keywords) - {"encoding", "errors"}:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            if not arguments:
                if keywords:
                    raise _ContractError(
                        "static scan rejected unsupported "
                        "constant-producing call"
                    )
                return b""
            source = arguments[0]
            if len(arguments) > 3:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            if type(source) is int:
                if source < 0:
                    return _STATIC_CONSTANT_UNAVAILABLE
                _static_preflight_output_size(source)
            else:
                source_size = _static_constant_size_upper(source)
                if source_size is None:
                    raise _ContractError(
                        "static scan rejected unsupported "
                        "constant-producing call"
                    )
                _static_preflight_output_size(source_size * 4 + 16)
            return bytes(*arguments, **keywords)
        if name == "str":
            if set(keywords) - {"encoding", "errors"} or len(arguments) > 3:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            if not arguments:
                if keywords:
                    raise _ContractError(
                        "static scan rejected unsupported "
                        "constant-producing call"
                    )
                return ""
            source_size = _static_constant_size_upper(arguments[0])
            if source_size is None:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            _static_preflight_output_size(source_size * 12 + 128)
            return str(*arguments, **keywords)
        if keywords or len(arguments) > 1:
            raise _ContractError(
                "static scan rejected unsupported constant-producing call"
            )
        argument = arguments[0] if arguments else None
        if name == "bool":
            return bool(argument) if arguments else False
        if name == "int":
            return int(argument) if arguments else 0
        return float(argument) if arguments else 0.0
    except _ContractError:
        raise
    except (LookupError, TypeError, ValueError, OverflowError):
        return _STATIC_CONSTANT_UNAVAILABLE


def _static_constant_method_call(
    node: ast.Call,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if not isinstance(node.func, ast.Attribute):
        return _STATIC_CONSTANT_UNAVAILABLE
    receiver = _static_constant_expression(node.func.value, cache, steps)
    if node.func.attr in {"decode", "encode"} and type(receiver) in (
        str,
        bytes,
    ):
        arguments = tuple(
            _static_constant_expression(argument, cache, steps)
            for argument in node.args
        )
        keyword_values = {
            keyword.arg: _static_constant_expression(
                keyword.value, cache, steps
            )
            for keyword in node.keywords
            if keyword.arg is not None
        }
        if (
            len(keyword_values) != len(node.keywords)
            or any(
                value is _STATIC_CONSTANT_UNAVAILABLE
                for value in (*arguments, *keyword_values.values())
            )
        ):
            raise _ContractError(
                "static scan rejected unsupported constant-producing call"
            )
        receiver_size = _static_constant_size_upper(receiver)
        if receiver_size is None:
            raise _ContractError(
                "static scan rejected unsupported constant-producing call"
            )
        _static_preflight_output_size(receiver_size * 4 + 16)
        try:
            if node.func.attr == "decode" and type(receiver) is bytes:
                return receiver.decode(*arguments, **keyword_values)
            if node.func.attr == "encode" and type(receiver) is str:
                return receiver.encode(*arguments, **keyword_values)
        except (LookupError, TypeError, UnicodeError, ValueError):
            return _STATIC_CONSTANT_UNAVAILABLE
        raise _ContractError(
            "static scan rejected unsupported constant-producing call"
        )
    if node.func.attr == "join" and type(receiver) in (str, bytes):
        if len(node.args) != 1 or node.keywords:
            return _STATIC_CONSTANT_UNAVAILABLE
        items = _static_constant_expression(node.args[0], cache, steps)
        if type(items) not in (tuple, list) or any(
            type(item) is not type(receiver) for item in items
        ):
            return _STATIC_CONSTANT_UNAVAILABLE
        receiver_size = _static_constant_size_upper(receiver)
        item_sizes = tuple(
            _static_constant_size_upper(item) for item in items
        )
        if receiver_size is None or any(
            size is None for size in item_sizes
        ):
            return _STATIC_CONSTANT_UNAVAILABLE
        output_size = sum(item_sizes)
        output_size += receiver_size * max(0, len(items) - 1)
        _static_preflight_output_size(output_size)
        return receiver.join(items)
    if node.func.attr == "format" and type(receiver) is str:
        if not _static_closed_format_template(receiver):
            return _STATIC_CONSTANT_UNAVAILABLE
        arguments = []
        for argument in node.args:
            value = _static_constant_expression(argument, cache, steps)
            if value is _STATIC_CONSTANT_UNAVAILABLE:
                return _STATIC_CONSTANT_UNAVAILABLE
            if not _static_safe_format_scalar(value):
                raise _ContractError(
                    "static scan rejected constant formatting operand"
                )
            arguments.append(value)
        keywords = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                return _STATIC_CONSTANT_UNAVAILABLE
            value = _static_constant_expression(keyword.value, cache, steps)
            if value is _STATIC_CONSTANT_UNAVAILABLE:
                return _STATIC_CONSTANT_UNAVAILABLE
            if not _static_safe_format_scalar(value):
                raise _ContractError(
                    "static scan rejected constant formatting operand"
                )
            keywords[keyword.arg] = value
        output_bound = _static_format_output_size_upper(
            receiver,
            tuple(arguments),
            keywords,
        )
        if output_bound is None:
            return _STATIC_CONSTANT_UNAVAILABLE
        _static_preflight_output_size(output_bound)
        try:
            return receiver.format(*arguments, **keywords)
        except (IndexError, KeyError, TypeError, ValueError):
            return _STATIC_CONSTANT_UNAVAILABLE
    if type(receiver) in (str, bytes):
        arguments = tuple(
            _static_constant_expression(argument, cache, steps)
            for argument in node.args
        )
        keyword_values = tuple(
            _static_constant_expression(keyword.value, cache, steps)
            for keyword in node.keywords
            if keyword.arg is not None
        )
        if (
            all(
                value is not _STATIC_CONSTANT_UNAVAILABLE
                for value in arguments + keyword_values
            )
            and len(keyword_values) == len(node.keywords)
        ):
            raise _ContractError(
                "static scan rejected unsupported constant string method"
            )
    return _STATIC_CONSTANT_UNAVAILABLE


def _static_constant_type_method_call(
    node: ast.Call,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if not (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"bytes", "int", "str"}
    ):
        return _STATIC_CONSTANT_UNAVAILABLE
    owner = node.func.value.id
    method = node.func.attr
    arguments = tuple(
        _static_constant_expression(argument, cache, steps)
        for argument in node.args
    )
    keywords = {
        keyword.arg: _static_constant_expression(
            keyword.value, cache, steps
        )
        for keyword in node.keywords
        if keyword.arg is not None
    }
    if (
        len(keywords) != len(node.keywords)
        or any(
            value is _STATIC_CONSTANT_UNAVAILABLE
            for value in (*arguments, *keywords.values())
        )
    ):
        return _STATIC_CONSTANT_UNAVAILABLE
    try:
        if owner == "bytes" and method == "fromhex":
            if (
                len(arguments) != 1
                or keywords
                or type(arguments[0]) is not str
            ):
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            source_size = _static_constant_size_upper(arguments[0])
            if source_size is None:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            _static_preflight_output_size((source_size // 2) + 1)
            return bytes.fromhex(arguments[0])
        if owner == "int" and method == "from_bytes":
            if not arguments or type(arguments[0]) is not bytes:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            source_size = _static_constant_size_upper(arguments[0])
            if source_size is None:
                raise _ContractError(
                    "static scan rejected unsupported constant-producing call"
                )
            if source_size * 8 > _STATIC_SCAN_INTEGER_BITS_LIMIT:
                raise _ContractError(
                    "static scan constant integer exceeds the bound"
                )
            return int.from_bytes(*arguments, **keywords)
    except _ContractError:
        raise
    except (LookupError, TypeError, ValueError, OverflowError):
        return _STATIC_CONSTANT_UNAVAILABLE
    raise _ContractError(
        "static scan rejected unsupported constant-producing call"
    )


def _static_constant_expression(
    node: ast.AST,
    cache: dict[ast.AST, object],
    steps: list[int],
) -> object:
    if node in cache:
        return cache[node]
    steps[0] += 1
    step_limit = (
        steps[1] if len(steps) > 1 else _STATIC_SCAN_NODE_LIMIT
    )
    if steps[0] > step_limit:
        raise _ContractError(
            "static scan constant evaluator exceeds the node bound"
        )
    cache[node] = _STATIC_CONSTANT_UNAVAILABLE
    result = _STATIC_CONSTANT_UNAVAILABLE
    if isinstance(node, ast.Constant):
        result = node.value
    elif isinstance(node, (ast.Tuple, ast.List)):
        items = tuple(
            _static_constant_expression(item, cache, steps)
            for item in node.elts
        )
        if all(item is not _STATIC_CONSTANT_UNAVAILABLE for item in items):
            result = items if isinstance(node, ast.Tuple) else list(items)
    elif isinstance(node, ast.Dict):
        if len(node.keys) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT:
            raise _ContractError(
                "static scan constant mapping exceeds the lookup bound"
            )
        mapping = {}
        for key_node, value_node in zip(node.keys, node.values):
            value = _static_constant_expression(value_node, cache, steps)
            if value is _STATIC_CONSTANT_UNAVAILABLE:
                break
            if key_node is None:
                if type(value) is not dict:
                    break
                _static_preflight_mapping_merge(
                    mapping, value, reject_overlap=False
                )
                mapping.update(value)
                continue
            key = _static_constant_expression(key_node, cache, steps)
            if type(key) is not str:
                break
            _static_preflight_mapping_merge(
                mapping, {key: value}, reject_overlap=False
            )
            mapping[key] = value
        else:
            result = mapping
    elif isinstance(node, ast.UnaryOp):
        operand = _static_constant_expression(node.operand, cache, steps)
        if type(operand) in (int, float):
            if isinstance(node.op, ast.UAdd):
                result = +operand
            elif isinstance(node.op, ast.USub):
                result = -operand
        if isinstance(node.op, ast.Not):
            truth = _static_safe_truth_value(operand)
            if truth is not None:
                result = not truth
    elif isinstance(node, ast.BinOp):
        result = _static_constant_binop(node, cache, steps)
    elif isinstance(node, ast.BoolOp):
        values = []
        for expression in node.values:
            value = _static_constant_expression(expression, cache, steps)
            if value is _STATIC_CONSTANT_UNAVAILABLE:
                break
            values.append(value)
            truth = _static_safe_truth_value(value)
            if truth is None:
                break
            if isinstance(node.op, ast.And) and not truth:
                result = value
                break
            if isinstance(node.op, ast.Or) and truth:
                result = value
                break
        else:
            if values:
                result = values[-1]
    elif isinstance(node, ast.Compare):
        result = _static_constant_compare(node, cache, steps)
    elif isinstance(node, ast.IfExp):
        test = _static_constant_expression(node.test, cache, steps)
        truth = _static_safe_truth_value(test)
        if truth is not None:
            result = _static_constant_expression(
                node.body if truth else node.orelse,
                cache,
                steps,
            )
    elif isinstance(node, ast.JoinedStr):
        result = _static_constant_joined_string(node, cache, steps)
    elif isinstance(node, ast.Subscript):
        value = _static_constant_expression(node.value, cache, steps)
        index = _static_constant_slice(node.slice, cache, steps)
        if (
            type(value) in (str, bytes, tuple, list)
            and index is not _STATIC_CONSTANT_UNAVAILABLE
        ):
            try:
                result = value[index]
            except (IndexError, TypeError, ValueError):
                pass
        elif type(value) is dict and type(index) is str:
            result = value.get(index, _STATIC_CONSTANT_UNAVAILABLE)
    elif isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "dict"
        ):
            result = _static_constant_dict_call(node, cache, steps)
        elif isinstance(node.func, ast.Name):
            result = _static_constant_builtin_call(node, cache, steps)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"bytes", "int", "str"}
        ):
            result = _static_constant_type_method_call(
                node, cache, steps
            )
        else:
            result = _static_constant_method_call(node, cache, steps)
    if result is not _STATIC_CONSTANT_UNAVAILABLE:
        if not _static_constant_is_bounded(result):
            result = _STATIC_CONSTANT_UNAVAILABLE
    cache[node] = result
    return result


def _static_literal_fingerprints(value: object) -> set[str]:
    fingerprints = set()
    if (
        type(value) in (int, float)
        and value in _SMALL_MATHEMATICAL_LITERALS
    ):
        return fingerprints
    try:
        fingerprints.add(_canonical_sha256(value))
    except (TypeError, ValueError, RecursionError, _ContractError):
        pass
    if type(value) in (str, bytes):
        if type(value) is bytes:
            try:
                text = value.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
        else:
            text = value
        if len(text.encode("utf-8")) <= _STATIC_SCAN_LITERAL_BYTES_LIMIT:
            try:
                parsed = json.loads(
                    text,
                    parse_constant=lambda _token: (_ for _ in ()).throw(
                        ValueError("non-finite JSON")
                    ),
                )
                if _canonical_bytes(parsed) == text.encode("utf-8"):
                    fingerprints.add(_canonical_sha256(parsed))
            except (
                TypeError,
                ValueError,
                RecursionError,
                _ContractError,
            ):
                pass
    return fingerprints


class _StaticConstantBindingSubstituter(ast.NodeTransformer):
    def __init__(
        self,
        bindings: Mapping[str, object],
        helpers: Mapping[str, object],
        *,
        node_limit: int,
        call_stack: frozenset[str],
    ) -> None:
        self._bindings = bindings
        self._helpers = helpers
        self._node_limit = node_limit
        self._call_stack = call_stack

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if isinstance(node.ctx, ast.Load) and node.id in self._bindings:
            return ast.copy_location(
                ast.Constant(value=self._bindings[node.id]), node
            )
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        visited = self.generic_visit(node)
        if not isinstance(visited, ast.Call):
            return visited
        if (
            isinstance(visited.func, ast.Name)
            and visited.func.id in self._helpers
        ):
            helper = self._helpers[visited.func.id]
            if isinstance(helper, ast.FunctionDef):
                value = _static_evaluate_helper_call(
                    helper,
                    visited,
                    self._bindings,
                    self._helpers,
                    node_limit=self._node_limit,
                    call_stack=self._call_stack,
                )
            elif not visited.args and not visited.keywords:
                value = helper
            else:
                value = _STATIC_CONSTANT_UNAVAILABLE
            if value is not _STATIC_CONSTANT_UNAVAILABLE:
                return ast.copy_location(
                    ast.Constant(value=value), visited
                )
        return visited


def _static_constant_with_bindings(
    node: ast.AST,
    bindings: Mapping[str, object],
    helpers: Mapping[str, object],
    *,
    node_limit: int,
    call_stack: frozenset[str] = frozenset(),
) -> object:
    if (
        len(bindings) > node_limit
        or len(helpers) > node_limit
    ):
        raise _ContractError(
            "static scan constant bindings exceed the node bound"
        )
    try:
        source = ast.unparse(node)
        source_bytes = source.encode("utf-8")
    except (RecursionError, UnicodeEncodeError, ValueError) as error:
        raise _ContractError(
            "static scan could not normalize constant expression"
        ) from error
    if len(source_bytes) > _STATIC_SCAN_LITERAL_BYTES_LIMIT:
        raise _ContractError(
            "static scan constant expression exceeds the source bound"
        )
    try:
        copied = ast.parse(source, mode="eval").body
    except (SyntaxError, ValueError, RecursionError) as error:
        raise _ContractError(
            "static scan could not parse constant expression"
        ) from error
    substituted = _StaticConstantBindingSubstituter(
        bindings,
        helpers,
        node_limit=node_limit,
        call_stack=call_stack,
    ).visit(copied)
    return _static_constant_expression(
        substituted, {}, [0, node_limit]
    )


def _static_same_value(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _static_function_parameter_names(
    function: ast.FunctionDef,
) -> tuple[str, ...] | None:
    arguments = function.args
    if arguments.vararg is not None or arguments.kwarg is not None:
        return None
    return tuple(
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    )


def _static_expression_value(
    expression: ast.AST,
    bindings: Mapping[str, object],
    helpers: Mapping[str, object],
    *,
    node_limit: int,
    call_stack: frozenset[str],
) -> object:
    return _static_constant_with_bindings(
        expression,
        bindings,
        helpers,
        node_limit=node_limit,
        call_stack=call_stack,
    )


def _static_apply_container_mutation(
    statement: ast.stmt,
    bindings: dict[str, object],
    helpers: Mapping[str, object],
    *,
    node_limit: int,
    call_stack: frozenset[str],
) -> bool:
    parts = _assignment_parts(statement)
    if parts is not None:
        targets, expression = parts
        if len(targets) == 1 and isinstance(targets[0], ast.Subscript):
            target = targets[0]
            if not isinstance(target.value, ast.Name):
                return False
            name = target.value.id
            current = bindings.get(name, _STATIC_CONSTANT_UNAVAILABLE)
            key = _static_expression_value(
                target.slice,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            value = _static_expression_value(
                expression,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            if (
                type(current) is not dict
                or type(key) is not str
                or value is _STATIC_CONSTANT_UNAVAILABLE
            ):
                return False
            addition = {key: value}
            _static_preflight_mapping_merge(
                current, addition, reject_overlap=False
            )
            updated = dict(current)
            updated[key] = value
            bindings[name] = updated
            return True
    if not isinstance(statement, ast.Expr) or not isinstance(
        statement.value, ast.Call
    ):
        return False
    call = statement.value
    if not isinstance(call.func, ast.Attribute) or not isinstance(
        call.func.value, ast.Name
    ):
        return False
    name = call.func.value.id
    current = bindings.get(name, _STATIC_CONSTANT_UNAVAILABLE)
    if call.func.attr == "update" and type(current) is dict:
        if len(call.args) != 1 or call.keywords:
            return False
        update = _static_expression_value(
            call.args[0],
            bindings,
            helpers,
            node_limit=node_limit,
            call_stack=call_stack,
        )
        if type(update) is not dict:
            return False
        _static_preflight_mapping_merge(
            current, update, reject_overlap=False
        )
        updated = dict(current)
        updated.update(update)
        bindings[name] = updated
        return True
    if call.func.attr in {"append", "extend"} and type(current) is list:
        if len(call.args) != 1 or call.keywords:
            return False
        value = _static_expression_value(
            call.args[0],
            bindings,
            helpers,
            node_limit=node_limit,
            call_stack=call_stack,
        )
        if value is _STATIC_CONSTANT_UNAVAILABLE:
            return False
        additions = value if call.func.attr == "extend" else [value]
        if type(additions) not in (tuple, list):
            return False
        projected_size = _static_constant_size_upper(current)
        addition_size = _static_constant_size_upper(additions)
        if projected_size is None or addition_size is None:
            return False
        if len(current) + len(additions) > _STATIC_SCAN_NODE_LIMIT:
            raise _ContractError(
                "static scan incremental container exceeds the node bound"
            )
        _static_preflight_output_size(projected_size + addition_size)
        bindings[name] = [*current, *additions]
        return True
    return False


def _static_execute_statements(
    statements: Iterable[ast.stmt],
    initial_bindings: Mapping[str, object],
    helpers: Mapping[str, object],
    *,
    node_limit: int,
    call_stack: frozenset[str],
) -> tuple[bool, object, dict[str, object]]:
    bindings = dict(initial_bindings)
    for index, statement in enumerate(statements):
        if (
            index == 0
            and isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and type(statement.value.value) is str
        ):
            continue
        assignment = _static_simple_name_assignment(statement)
        if assignment is not None:
            name, expression = assignment
            value = _static_expression_value(
                expression,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            if value is _STATIC_CONSTANT_UNAVAILABLE:
                bindings.pop(name, None)
            else:
                bindings[name] = value
            continue
        if _static_apply_container_mutation(
            statement,
            bindings,
            helpers,
            node_limit=node_limit,
            call_stack=call_stack,
        ):
            continue
        if isinstance(statement, ast.If):
            test = _static_expression_value(
                statement.test,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            truth = _static_safe_truth_value(test)
            if truth is not None:
                returned, value, branch_bindings = (
                    _static_execute_statements(
                        statement.body if truth else statement.orelse,
                        bindings,
                        helpers,
                        node_limit=node_limit,
                        call_stack=call_stack,
                    )
                )
                if returned:
                    return True, value, branch_bindings
                bindings = branch_bindings
                continue
            left = _static_execute_statements(
                statement.body,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            right = _static_execute_statements(
                statement.orelse,
                bindings,
                helpers,
                node_limit=node_limit,
                call_stack=call_stack,
            )
            if left[0] and right[0]:
                if _static_same_value(left[1], right[1]):
                    return True, left[1], bindings
                return True, _STATIC_CONSTANT_UNAVAILABLE, bindings
            if left[0] != right[0]:
                return False, _STATIC_CONSTANT_UNAVAILABLE, {}
            bindings = {
                name: value
                for name, value in left[2].items()
                if name in right[2]
                and _static_same_value(value, right[2][name])
            }
            continue
        if isinstance(statement, ast.Return):
            if statement.value is None:
                return True, None, bindings
            return (
                True,
                _static_expression_value(
                    statement.value,
                    bindings,
                    helpers,
                    node_limit=node_limit,
                    call_stack=call_stack,
                ),
                bindings,
            )
        return False, _STATIC_CONSTANT_UNAVAILABLE, {}
    return False, _STATIC_CONSTANT_UNAVAILABLE, bindings


def _static_evaluate_helper_call(
    function: ast.FunctionDef,
    call: ast.Call,
    global_bindings: Mapping[str, object],
    helpers: Mapping[str, object],
    *,
    node_limit: int,
    call_stack: frozenset[str],
) -> object:
    if function.name in call_stack:
        return _STATIC_CONSTANT_UNAVAILABLE
    if len(call_stack) >= _STATIC_SCAN_DEPTH_LIMIT:
        raise _ContractError(
            "static scan constant helper calls exceed the depth bound"
        )
    parameter_names = _static_function_parameter_names(function)
    positional_names = tuple(
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
        )
    )
    posonly_names = {
        argument.arg for argument in function.args.posonlyargs
    }
    if parameter_names is None or len(call.args) > len(positional_names):
        return _STATIC_CONSTANT_UNAVAILABLE
    supplied: dict[str, object] = {}
    for name, argument in zip(positional_names, call.args):
        supplied[name] = _static_constant_expression(
            argument, {}, [0, node_limit]
        )
    for keyword in call.keywords:
        if (
            keyword.arg is None
            or keyword.arg not in parameter_names
            or keyword.arg in posonly_names
        ):
            return _STATIC_CONSTANT_UNAVAILABLE
        if keyword.arg in supplied:
            return _STATIC_CONSTANT_UNAVAILABLE
        supplied[keyword.arg] = _static_constant_expression(
            keyword.value, {}, [0, node_limit]
        )
    bindings = {
        name: value
        for name, value in global_bindings.items()
        if name not in parameter_names
    }
    positional_defaults = {
        name: default
        for name, default in zip(
            positional_names[
                len(positional_names) - len(function.args.defaults):
            ],
            function.args.defaults,
        )
    }
    keyword_defaults = {
        argument.arg: default
        for argument, default in zip(
            function.args.kwonlyargs,
            function.args.kw_defaults,
        )
        if default is not None
    }
    for name, default in {
        **positional_defaults,
        **keyword_defaults,
    }.items():
        if name in supplied:
            continue
        value = _static_expression_value(
            default,
            bindings,
            helpers,
            node_limit=node_limit,
            call_stack=call_stack | {function.name},
        )
        if value is not _STATIC_CONSTANT_UNAVAILABLE:
            supplied[name] = value
    bindings.update(
        {
            name: value
            for name, value in supplied.items()
            if value is not _STATIC_CONSTANT_UNAVAILABLE
        }
    )
    returned, value, _bindings = _static_execute_statements(
        function.body,
        bindings,
        helpers,
        node_limit=node_limit,
        call_stack=call_stack | {function.name},
    )
    return value if returned else _STATIC_CONSTANT_UNAVAILABLE


def _static_immutable_binding_value(value: object) -> bool:
    stack = [value]
    steps = 0
    while stack:
        item = stack.pop()
        steps += 1
        if steps > _STATIC_SCAN_NODE_LIMIT:
            raise _ContractError(
                "static scan constant binding exceeds the node bound"
            )
        if item is None or type(item) in (bool, int, float, str, bytes):
            continue
        if type(item) in (tuple, list):
            if len(item) > _STATIC_SCAN_NODE_LIMIT:
                raise _ContractError(
                    "static scan constant binding exceeds the node bound"
                )
            stack.extend(item)
            continue
        if type(item) is dict:
            if len(item) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT or any(
                type(key) is not str for key in item
            ):
                return False
            stack.extend(item.values())
            continue
        return False
    return True


def _static_simple_name_assignment(
    statement: ast.stmt,
) -> tuple[str, ast.AST] | None:
    parts = _assignment_parts(statement)
    if parts is None:
        return None
    targets, value = parts
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return None
    return targets[0].id, value


def _static_zero_argument_return(
    statement: ast.stmt,
) -> ast.AST | None:
    if not isinstance(statement, ast.FunctionDef):
        return None
    arguments = statement.args
    if (
        statement.decorator_list
        or arguments.posonlyargs
        or arguments.args
        or arguments.vararg is not None
        or arguments.kwonlyargs
        or arguments.kwarg is not None
        or arguments.defaults
        or arguments.kw_defaults
        or len(statement.body) != 1
        or not isinstance(statement.body[0], ast.Return)
        or statement.body[0].value is None
    ):
        return None
    return statement.body[0].value


def _static_reject_propagated_fingerprint(
    value: object,
    forbidden_fingerprints: frozenset[str],
) -> None:
    if value is _STATIC_CONSTANT_UNAVAILABLE:
        return
    if _static_literal_fingerprints(value) & forbidden_fingerprints:
        raise _ContractError(
            "static scan rejected propagated output fingerprint"
        )


def _scan_static_propagated_constants(
    tree: ast.AST,
    forbidden_fingerprints: frozenset[str],
    *,
    node_limit: int,
) -> None:
    if not isinstance(tree, ast.Module):
        return
    module_assignments = tuple(
        assignment
        for statement in tree.body
        if (assignment := _static_simple_name_assignment(statement))
        is not None
    )
    assignment_counts: dict[str, int] = {}
    for name, _value in module_assignments:
        assignment_counts[name] = assignment_counts.get(name, 0) + 1
    module_store_counts: dict[str, int] = {}
    for statement in tree.body:
        if isinstance(
            statement,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        for candidate in ast.walk(statement):
            if isinstance(candidate, ast.Name) and isinstance(
                candidate.ctx, (ast.Store, ast.Del)
            ):
                module_store_counts[candidate.id] = (
                    module_store_counts.get(candidate.id, 0) + 1
                )
    helpers: dict[str, object] = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, ast.FunctionDef)
    }
    bindings: dict[str, object] = {}
    for name, expression in module_assignments:
        if (
            assignment_counts[name] != 1
            or module_store_counts.get(name) != 1
        ):
            continue
        value = _static_constant_with_bindings(
            expression,
            bindings,
            helpers,
            node_limit=node_limit,
        )
        if value is _STATIC_CONSTANT_UNAVAILABLE:
            continue
        if not _static_immutable_binding_value(value):
            continue
        bindings[name] = value
        _static_reject_propagated_fingerprint(
            value, forbidden_fingerprints
        )
    for statement in tree.body:
        if not isinstance(statement, ast.FunctionDef):
            continue
        parameter_names = _static_function_parameter_names(statement)
        if parameter_names is None:
            continue
        initial_bindings = {
            name: value
            for name, value in bindings.items()
            if name not in parameter_names
        }
        returned, value, _local_bindings = _static_execute_statements(
            statement.body,
            initial_bindings,
            helpers,
            node_limit=node_limit,
            call_stack=frozenset({statement.name}),
        )
        if returned:
            _static_reject_propagated_fingerprint(
                value, forbidden_fingerprints
            )


def _static_expression_has_literal(value: ast.AST) -> bool:
    return any(
        isinstance(candidate, (ast.Constant, ast.Dict, ast.List, ast.Tuple))
        for candidate in ast.walk(value)
    )


def _scan_static_parameter_indexed_literals(
    tree: ast.AST,
    entry_function_name: str | None,
) -> None:
    if not isinstance(tree, ast.Module) or entry_function_name is None:
        return

    def is_literal_container(expression: ast.AST) -> bool:
        return isinstance(expression, (ast.Dict, ast.List, ast.Tuple)) or (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id in {"dict", "list", "tuple"}
            and _static_expression_has_literal(expression)
        )

    module_containers = {
        assignment[0]
        for statement in tree.body
        if (assignment := _static_simple_name_assignment(statement))
        is not None
        and is_literal_container(assignment[1])
    }
    entry = next(
        (
            statement
            for statement in tree.body
            if isinstance(statement, ast.FunctionDef)
            and statement.name == entry_function_name
        ),
        None,
    )
    if entry is None:
        return
    parameter_names = _static_function_parameter_names(entry)
    if parameter_names is None:
        raise _ContractError(
            "static scan cannot prove scientific parameter flow"
        )
    tainted_names = set(parameter_names)
    container_names = set(module_containers)
    for candidate in ast.walk(entry):
        assignment = (
            _static_simple_name_assignment(candidate)
            if isinstance(candidate, ast.stmt)
            else None
        )
        if assignment is None:
            continue
        target_name, expression = assignment
        if is_literal_container(expression) or (
            isinstance(expression, ast.Name)
            and expression.id in container_names
        ):
            container_names.add(target_name)
        if any(
            isinstance(item, ast.Name)
            and isinstance(item.ctx, ast.Load)
            and item.id in tainted_names
            for item in ast.walk(expression)
        ):
            tainted_names.add(target_name)
    for candidate in ast.walk(entry):
        if not isinstance(candidate, ast.Subscript):
            continue
        literal_container = is_literal_container(candidate.value) or (
            isinstance(candidate.value, ast.Name)
            and candidate.value.id in container_names
        )
        parameter_index = any(
            isinstance(item, ast.Name)
            and isinstance(item.ctx, ast.Load)
            and item.id in tainted_names
            for item in ast.walk(candidate.slice)
        )
        if literal_container and parameter_index:
            raise _ContractError(
                "static scan rejected literal mapping or sequence indexed "
                "by a scientific parameter"
            )


def _scan_static_ast(
    tree: ast.AST,
    *,
    role: str,
    forbidden_fingerprints: frozenset[str],
    node_limit: int | None = None,
    depth_limit: int | None = None,
    entry_function_name: str | None = None,
) -> None:
    if node_limit is None:
        node_limit = _STATIC_SCAN_NODE_LIMIT
    if depth_limit is None:
        depth_limit = _STATIC_SCAN_DEPTH_LIMIT
    _static_ast_depth(
        tree,
        node_limit=node_limit,
        depth_limit=depth_limit,
    )
    _scan_static_parameter_indexed_literals(tree, entry_function_name)
    nodes = tuple(ast.walk(tree))
    import_aliases = _static_import_aliases(tree)
    _scan_static_external_module_flows(tree, import_aliases)
    constant_cache: dict[ast.AST, object] = {}
    constant_steps = [0, node_limit]
    for candidate in nodes:
        if role != "infrastructure" and isinstance(
            candidate, (ast.Name, ast.Attribute)
        ):
            authored_name = (
                candidate.id
                if isinstance(candidate, ast.Name)
                else candidate.attr
            )
            if _lexical_tokens(authored_name) & (
                _STATIC_FORBIDDEN_NAME_TOKENS
            ):
                raise _ContractError(
                    "static scan rejected forbidden scientific vocabulary"
                )
        if isinstance(candidate, ast.Call):
            path = _static_resolved_call_path(
                candidate.func, import_aliases
            )
            folded_path = tuple(part.casefold() for part in path)
            if path and (
                folded_path[-1] in _STATIC_NATIVE_CALL_SUFFIXES
                or any(
                    part in {"ctypes", "cffi"} for part in folded_path
                )
                or (
                    "lowlevelcallable" in folded_path
                    and "scipy" in folded_path
                )
            ):
                raise _ContractError(
                    "static scan rejected undeclared native capability"
                )
        if isinstance(candidate, ast.expr):
            literal_value = _static_constant_expression(
                candidate,
                constant_cache,
                constant_steps,
            )
            if literal_value is _STATIC_CONSTANT_UNAVAILABLE:
                continue
            if _static_literal_fingerprints(literal_value) & (
                forbidden_fingerprints
            ):
                raise _ContractError(
                    "static scan rejected embedded output fingerprint"
                )
        if isinstance(candidate, ast.Dict) and (
            len(candidate.keys) > _STATIC_SCAN_LOOKUP_ENTRY_LIMIT
        ):
            raise _ContractError(
                "static scan lookup structure exceeds the closed bound"
            )
    for candidate in nodes:
        if isinstance(candidate, ast.If):
            test_tokens = _ast_authored_tokens(candidate.test)
            if test_tokens & {"benchmark", "adapter"} and any(
                isinstance(item, ast.Return)
                and item.value is not None
                and _static_expression_has_literal(item.value)
                for item in ast.walk(candidate)
            ):
                raise _ContractError(
                    "static scan rejected benchmark literal branch"
                )
        if isinstance(candidate, (ast.Assign, ast.AnnAssign)):
            parts = _assignment_parts(candidate)
            if parts is None:
                continue
            targets, value = parts
            target_tokens = {
                token
                for target in targets
                for token in _target_tokens(target)
            }
            if target_tokens & {"lookup", "table", "answer"} and isinstance(
                value, (ast.Dict, ast.List, ast.Tuple)
            ):
                raise _ContractError(
                    "static scan rejected parameter result lookup structure"
                )
    _scan_static_propagated_constants(
        tree,
        forbidden_fingerprints,
        node_limit=node_limit,
    )


def _scan_static_material_content(
    material: _StaticScanMaterial,
    *,
    role: str,
    forbidden_fingerprints: tuple[str, ...],
    entry_function_name: str | None,
) -> None:
    fingerprints = frozenset(forbidden_fingerprints)
    emitted_tree = _bounded_parse_utf8_python(
        material.emitted_source,
        byte_limit=_STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT,
        field_name="static scan hash-bound emitted material",
    )
    _static_ast_depth(
        emitted_tree,
        node_limit=_STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT,
        depth_limit=_STATIC_SCAN_AGGREGATE_AST_DEPTH_LIMIT,
    )
    for node in material.nodes:
        tree = _bounded_parse_utf8_python(
            node.raw_source_span,
            byte_limit=_STATIC_SCAN_LITERAL_BYTES_LIMIT,
            field_name="static scan hash-bound raw material",
        )
        _scan_static_ast(
            tree,
            role=role,
            forbidden_fingerprints=fingerprints,
            entry_function_name=entry_function_name,
        )
    _scan_static_ast(
        emitted_tree,
        role=role,
        forbidden_fingerprints=fingerprints,
        node_limit=_STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT,
        depth_limit=_STATIC_SCAN_AGGREGATE_AST_DEPTH_LIMIT,
        entry_function_name=entry_function_name,
    )


def _static_scan_checks(role: str) -> dict[str, dict[str, object]]:
    reasons = {
        "raw_ast_closed": "bounded raw AST passed",
        "dependency_graph_closed": "closed dependency graph passed",
        "imports_closed": "closed import policy passed",
        "capabilities_closed": "closed capability policy passed",
        "literal_context_closed": "literal context policy passed",
        "emitted_bytes_closed": "hash-bound emitted bytes passed",
        "fingerprints_absent": "forbidden fingerprints absent",
        "role_policy_closed": "closure role policy passed",
    }
    if role == "infrastructure":
        reasons[_STATIC_SCAN_INFRASTRUCTURE_CHECK] = (
            "exact infrastructure purpose policy passed"
        )
    return {
        name: {"passed": True, "reason": reasons[name]}
        for name in sorted(reasons)
    }


def scan_scientific_closure(closure, *, forbidden_fingerprints):
    """Scan one builder-produced closure against closed static policy."""

    material = getattr(closure, "_static_scan_material", None)
    if type(closure) is ScientificClosure:
        validated = _validate_scientific_closure_record(closure)
        role = validated.role
        entry_function_name = validated.entry_symbol.rsplit(":", 1)[1]
    elif type(closure) is InfrastructureClosure:
        validated = _validate_infrastructure_closure_record(closure)
        role = "infrastructure"
        entry_function_name = None
    else:
        raise _ContractError(
            "static scan closure must be an exact closure record"
        )
    validated_material = _validate_static_scan_material(
        validated, material
    )
    fingerprints = _validate_static_fingerprints(forbidden_fingerprints)
    _scan_static_material_content(
        validated_material,
        role=role,
        forbidden_fingerprints=fingerprints,
        entry_function_name=entry_function_name,
    )
    checks = _static_scan_checks(role)
    fingerprint_commitment_sha256 = _canonical_sha256(
        {
            "algorithm_version": _FINGERPRINT_ALGORITHM_VERSION,
            "fingerprints": fingerprints,
        }
    )
    values = {
        "schema_version": "static_scan_report_v1",
        "role": role,
        "scanner_version": _STATIC_SCANNER_VERSION,
        "scanner_sha256": _current_static_scanner_sha256(),
        "scanned_closure_sha256": validated.bundle_sha256,
        "fingerprint_commitment_sha256": (
            fingerprint_commitment_sha256
        ),
        "checks": checks,
        "passed": True,
    }
    values["report_sha256"] = _static_scan_report_sha256(values)
    return StaticScanReport(**values)


_STATIC_SCANNER_ENTRYPOINT_NAMES = (
    "_validate_task5_policy_commitment",
    "build_infrastructure_closure",
    "build_scientific_closure",
    "build_scientific_policy_commitment",
    "scan_scientific_closure",
)
_STATIC_SCANNER_SEMANTIC_MODULES = frozenset(
    {__name__, _adapters.__name__, _oracles.__name__}
)
_STATIC_SCANNER_EXTERNAL_INSTANCE_TYPES = frozenset(
    {
        ("dataclasses", "_FIELD_BASE"),
        ("json.decoder", "JSONDecoder"),
        ("json.encoder", "JSONEncoder"),
        ("sre_constants", "_NamedIntConstant"),
    }
)
_STATIC_SCANNER_EXTERNAL_OPAQUE_INSTANCE_TYPES = frozenset()
_STATIC_SCANNER_EXTERNAL_INSTANCE_SLOT_PATHS = {
    ("_json", "Scanner"): (
        "__call__",
        "object_hook",
        "object_pairs_hook",
        "parse_constant",
        "parse_float",
        "parse_int",
        "strict",
    ),
}
_STATIC_SCANNER_BUILTIN_BINDINGS = frozenset(
    set(_SAFE_AST_BUILTINS)
    | {
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "DeprecationWarning",
        "Exception",
        "FutureWarning",
        "Ellipsis",
        "IndexError",
        "KeyError",
        "LookupError",
        "NotImplementedError",
        "NotImplemented",
        "OSError",
        "OverflowError",
        "RecursionError",
        "RuntimeError",
        "StopIteration",
        "SyntaxError",
        "TypeError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "UnicodeError",
        "ValueError",
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bytearray",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "delattr",
        "format",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "hex",
        "id",
        "memoryview",
        "ord",
        "print",
        "property",
        "repr",
        "setattr",
        "staticmethod",
        "super",
        "vars",
    }
)
_STATIC_SCANNER_INTERNAL_RECEIVER_CLASS_BINDINGS = frozenset(
    {
        (__name__, "_AstClosureResolver"),
    }
)
_STATIC_SCANNER_EXTERNAL_RECEIVER_ACCESS_SITES = (
    (
        __name__,
        "_assert_no_symlink_components",
        "pathlib",
        "Path",
        ("__truediv__", "absolute", "anchor", "is_symlink", "parts"),
        (),
    ),
    (
        __name__,
        "_normalize_source_roots",
        "pathlib",
        "Path",
        ("is_dir", "resolve"),
        (("__str__", 1),),
    ),
    (
        __name__,
        "_bounded_read_python_source",
        "pathlib",
        "Path",
        ("anchor", "is_absolute", "parts"),
        (("open", 3),),
    ),
    (
        __name__,
        "_AstClosureResolver._find_module_path",
        "pathlib",
        "Path",
        (
            "__truediv__",
            "is_file",
            "is_symlink",
            "parts",
            "relative_to",
            "resolve",
            "with_suffix",
        ),
        (),
    ),
    (
        __name__,
        "_AstClosureResolver._load_module",
        "pathlib",
        "Path",
        ("__str__", "as_posix", "relative_to"),
        (("__str__", 1), ("name", 7)),
    ),
    (
        __name__,
        "_validate_ast_node_manifest",
        "pathlib",
        "PurePosixPath",
        ("__str__", "is_absolute", "parts"),
        (),
    ),
    (
        __name__,
        "_static_closed_format_template",
        "string",
        "Formatter",
        ("parse",),
        (),
    ),
    (
        __name__,
        "_static_format_output_size_upper",
        "string",
        "Formatter",
        ("parse",),
        (),
    ),
)
_STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS = frozenset(
    {
        ("pathlib", "Path", "absolute"),
        ("pathlib", "Path", "is_dir"),
        ("pathlib", "Path", "is_file"),
        ("pathlib", "Path", "is_symlink"),
        ("pathlib", "Path", "resolve"),
        ("pathlib", "PurePath", "__str__"),
        ("pathlib", "PurePath", "__truediv__"),
        ("pathlib", "PurePath", "anchor"),
        ("pathlib", "PurePath", "as_posix"),
        ("pathlib", "PurePath", "is_absolute"),
        ("pathlib", "PurePath", "parts"),
        ("pathlib", "PurePath", "relative_to"),
        ("pathlib", "PurePath", "with_suffix"),
        ("string", "Formatter", "parse"),
    }
)
_STATIC_SCANNER_EXTERNAL_RECEIVER_SEED_EXCLUSIONS = frozenset(
    {
        (
            __name__,
            "_static_external_receiver_class",
            "pathlib",
            "Path",
        ),
        (
            __name__,
            "_static_external_receiver_class",
            "pathlib",
            "PurePath",
        ),
        (
            __name__,
            "_static_external_receiver_class",
            "pathlib",
            "PurePosixPath",
        ),
        (
            __name__,
            "_static_external_receiver_dependency_manifest",
            "pathlib",
            "Path",
        ),
        (
            __name__,
            "_static_external_receiver_dependency_manifest",
            "pathlib",
            "PurePath",
        ),
        (
            __name__,
            "_static_external_receiver_dependency_manifest",
            "pathlib",
            "PurePosixPath",
        ),
    }
)


def _static_external_receiver_rule_manifest() -> dict[str, object]:
    sites = _STATIC_SCANNER_EXTERNAL_RECEIVER_ACCESS_SITES
    bindings = _STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS
    seed_exclusions = _STATIC_SCANNER_EXTERNAL_RECEIVER_SEED_EXCLUSIONS
    if (
        type(sites) is not tuple
        or type(bindings) is not frozenset
        or type(seed_exclusions) is not frozenset
    ):
        raise _ContractError(
            "static scanner external receiver manifest is not exact"
        )
    if len(sites) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT or len(
        bindings
    ) > _STATIC_SCANNER_COMMITMENT_ATTRIBUTE_LIMIT:
        raise _ContractError(
            "static scanner external receiver manifest exceeds its bound"
        )
    accessed_member_names = set()
    normalized_sites = []
    for site in sites:
        if type(site) is not tuple or len(site) != 6:
            raise _ContractError(
                "static scanner external receiver access site is not exact"
            )
        (
            project_module,
            project_qualname,
            receiver_module,
            receiver_qualname,
            member_names,
            collision_counts,
        ) = site
        text_values = (
            project_module,
            project_qualname,
            receiver_module,
            receiver_qualname,
        )
        if any(type(item) is not str or not item for item in text_values):
            raise _ContractError(
                "static scanner external receiver identity is not exact"
            )
        if any(
            len(item.encode("utf-8"))
            > _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT
            for item in text_values
        ):
            raise _ContractError(
                "static scanner external receiver identity exceeds its bound"
            )
        if (
            type(member_names) is not tuple
            or not member_names
            or member_names != tuple(sorted(member_names))
            or len(set(member_names)) != len(member_names)
            or any(type(name) is not str or not name for name in member_names)
        ):
            raise _ContractError(
                "static scanner external receiver members are not exact"
            )
        if (
            type(collision_counts) is not tuple
            or collision_counts != tuple(sorted(collision_counts))
            or len(set(collision_counts)) != len(collision_counts)
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or not item[0]
                or type(item[1]) is not int
                or item[1] < 1
                for item in collision_counts
            )
        ):
            raise _ContractError(
                "static scanner external receiver collision counts are not "
                "exact"
            )
        accessed_member_names.update(member_names)
        normalized_sites.append(
            [
                project_module,
                project_qualname,
                receiver_module,
                receiver_qualname,
                list(member_names),
                [list(item) for item in collision_counts],
            ]
        )
    for binding in bindings:
        if (
            type(binding) is not tuple
            or len(binding) != 3
            or any(type(item) is not str or not item for item in binding)
        ):
            raise _ContractError(
                "static scanner external receiver binding is not exact"
            )
        owner_class = _static_external_receiver_class(
            binding[0], binding[1]
        )
        actual_owner, _member = _static_exact_class_member(
            owner_class, binding[2]
        )
        if (
            type.__getattribute__(actual_owner, "__module__"),
            type.__getattribute__(actual_owner, "__qualname__"),
        ) != (binding[0], binding[1]):
            raise _ContractError(
                "static scanner external receiver binding owner is not exact"
            )
    if {binding[2] for binding in bindings} != accessed_member_names:
        raise _ContractError(
            "static scanner external receiver binding manifest is missing "
            "or contains an unreferenced binding"
        )
    for exclusion in seed_exclusions:
        if (
            type(exclusion) is not tuple
            or len(exclusion) != 4
            or any(type(item) is not str or not item for item in exclusion)
        ):
            raise _ContractError(
                "static scanner external receiver seed exclusion is not "
                "exact"
            )
    return {
        "access_sites": normalized_sites,
        "bindings": [list(item) for item in sorted(bindings)],
        "seed_exclusions": [
            list(item)
            for item in sorted(
                _STATIC_SCANNER_EXTERNAL_RECEIVER_SEED_EXCLUSIONS
            )
        ],
    }


def _static_external_instance_slot_manifest() -> list[dict[str, object]]:
    expected = {
        ("_json", "Scanner"): (
            "__call__",
            "object_hook",
            "object_pairs_hook",
            "parse_constant",
            "parse_float",
            "parse_int",
            "strict",
        ),
    }
    paths = _STATIC_SCANNER_EXTERNAL_INSTANCE_SLOT_PATHS
    if (
        type(paths) is not dict
        or paths != expected
        or _STATIC_SCANNER_EXTERNAL_OPAQUE_INSTANCE_TYPES != frozenset()
    ):
        raise _ContractError(
            "static scanner external instance slot policy is not inverse"
        )
    return [
        {
            "module": module_name,
            "qualname": qualname,
            "slots": list(paths[(module_name, qualname)]),
        }
        for module_name, qualname in sorted(paths)
    ]


def _static_scanner_rule_manifest() -> dict[str, object]:
    return {
        "commitment_version": "transitive_semantic_commitment_v6",
        "scanner_version": _STATIC_SCANNER_VERSION,
        "constant_evaluator_version": _STATIC_CONSTANT_EVALUATOR_VERSION,
        "ast_closure_version": _AST_CLOSURE_VERSION,
        "policy_structure_version": _POLICY_STRUCTURE_SCAN_VERSION,
        "fingerprint_algorithm_version": _FINGERPRINT_ALGORITHM_VERSION,
        "limits": {
            "node_count": _STATIC_SCAN_NODE_LIMIT,
            "ast_depth": _STATIC_SCAN_DEPTH_LIMIT,
            "literal_bytes": _STATIC_SCAN_LITERAL_BYTES_LIMIT,
            "source_file_bytes": _STATIC_SCAN_SOURCE_FILE_BYTES_LIMIT,
            "evaluated_output_bytes": (
                _STATIC_SCAN_EVALUATED_OUTPUT_BYTES_LIMIT
            ),
            "aggregate_material_bytes": (
                _STATIC_SCAN_AGGREGATE_MATERIAL_BYTES_LIMIT
            ),
            "fingerprint_count": _STATIC_SCAN_FINGERPRINT_COUNT_LIMIT,
            "lookup_entries": _STATIC_SCAN_LOOKUP_ENTRY_LIMIT,
            "aggregate_ast_nodes": _STATIC_SCAN_AGGREGATE_AST_NODE_LIMIT,
            "aggregate_ast_depth": _STATIC_SCAN_AGGREGATE_AST_DEPTH_LIMIT,
            "integer_bits": _STATIC_SCAN_INTEGER_BITS_LIMIT,
            "format_width": _STATIC_SCAN_FORMAT_WIDTH_LIMIT,
            "check_count": _STATIC_SCAN_CHECK_LIMIT,
            "reason_bytes": _STATIC_SCAN_REASON_BYTES_LIMIT,
        },
        "semantic_commitment_limits": {
            "node_count": _STATIC_SCANNER_COMMITMENT_NODE_LIMIT,
            "edge_count": _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT,
            "attribute_count": (
                _STATIC_SCANNER_COMMITMENT_ATTRIBUTE_LIMIT
            ),
            "depth": _STATIC_SCANNER_COMMITMENT_DEPTH_LIMIT,
            "value_bytes": _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT,
            "integer_bits": _STATIC_SCANNER_COMMITMENT_INTEGER_BITS_LIMIT,
            "material_bytes": (
                _STATIC_SCANNER_COMMITMENT_MATERIAL_BYTES_LIMIT
            ),
        },
        "separately_committed_data": sorted(
            f"{module_name}.{attribute_name}->{owner}"
            for (module_name, attribute_name), owner
            in _COMMITTED_DATA_OWNERS.items()
        ),
        "common_checks": sorted(_STATIC_SCAN_COMMON_CHECKS),
        "infrastructure_check": _STATIC_SCAN_INFRASTRUCTURE_CHECK,
        "small_mathematical_literals": sorted(
            _SMALL_MATHEMATICAL_LITERALS
        ),
        "forbidden_name_tokens": sorted(_STATIC_FORBIDDEN_NAME_TOKENS),
        "native_call_suffixes": sorted(_STATIC_NATIVE_CALL_SUFFIXES),
        "numpy_file_callables": sorted(_STATIC_NUMPY_FILE_CALLABLES),
        "forbidden_capability_namespaces": [
            list(path)
            for path in _STATIC_FORBIDDEN_CAPABILITY_NAMESPACES
        ],
        "safe_numeric_constant_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_NUMERIC_CONSTANT_PATHS)
        ],
        "safe_numeric_callable_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_NUMERIC_CALLABLE_PATHS)
        ],
        "safe_numeric_callable_object_paths": [
            list(path)
            for path in sorted(
                _STATIC_SAFE_NUMERIC_CALLABLE_OBJECT_PATHS
            )
        ],
        "safe_stdlib_callable_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_STDLIB_CALLABLE_PATHS)
        ],
        "safe_stdlib_constant_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_STDLIB_CONSTANT_PATHS)
        ],
        "safe_stdlib_callable_object_paths": [
            list(path)
            for path in sorted(
                _STATIC_SAFE_STDLIB_CALLABLE_OBJECT_PATHS
            )
        ],
        "safe_stdlib_method_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_STDLIB_METHOD_PATHS)
        ],
        "safe_operator_callable_paths": [
            list(path)
            for path in sorted(_STATIC_SAFE_OPERATOR_CALLABLE_PATHS)
        ],
        "safe_external_import_prefixes": list(
            _SAFE_EXTERNAL_IMPORT_PREFIXES
        ),
        "safe_external_import_modules": sorted(
            _SAFE_EXTERNAL_IMPORT_MODULES
        ),
        "forbidden_scientific_project_module_prefixes": (
            _forbidden_scientific_project_module_manifest()
        ),
        "forbidden_scientific_project_module_token_patterns": (
            _forbidden_scientific_project_module_token_manifest()
        ),
        "safe_ast_builtins": sorted(_SAFE_AST_BUILTINS),
        "semantic_builtin_bindings": sorted(
            _STATIC_SCANNER_BUILTIN_BINDINGS
        ),
        "semantic_external_instance_types": [
            list(item)
            for item in sorted(_STATIC_SCANNER_EXTERNAL_INSTANCE_TYPES)
        ],
        "semantic_external_opaque_instance_types": [
            list(item)
            for item in sorted(
                _STATIC_SCANNER_EXTERNAL_OPAQUE_INSTANCE_TYPES
            )
        ],
        "semantic_external_instance_slot_paths": (
            _static_external_instance_slot_manifest()
        ),
        "semantic_internal_receiver_class_bindings": [
            list(item)
            for item in sorted(
                _STATIC_SCANNER_INTERNAL_RECEIVER_CLASS_BINDINGS
            )
        ],
        "semantic_external_receiver_bindings": (
            _static_external_receiver_rule_manifest()
        ),
        "forbidden_dynamic_calls": sorted(_FORBIDDEN_DYNAMIC_CALLS),
        "entrypoints": list(_STATIC_SCANNER_ENTRYPOINT_NAMES),
    }


def _static_semantic_step(state: dict[str, object], depth: int) -> None:
    if depth > _STATIC_SCANNER_COMMITMENT_DEPTH_LIMIT:
        raise _ContractError(
            "static scanner semantic dependency exceeds the depth bound"
        )
    steps = state["steps"] + 1
    if steps > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
        raise _ContractError(
            "static scanner semantic dependency exceeds the node bound"
        )
    state["steps"] = steps
    edges = state["edges"] + 1
    if edges > _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT:
        raise _ContractError(
            "static scanner semantic dependency exceeds the edge bound"
        )
    state["edges"] = edges


def _static_semantic_attribute_step(
    state: dict[str, object],
) -> None:
    attributes = state["attributes"] + 1
    if attributes > _STATIC_SCANNER_COMMITMENT_ATTRIBUTE_LIMIT:
        raise _ContractError(
            "static scanner semantic dependency exceeds the attribute bound"
        )
    state["attributes"] = attributes


def _static_semantic_register(
    value: object,
    state: dict[str, object],
) -> tuple[str, bool]:
    identity = id(value)
    memo = state["memo"]
    existing = memo.get(identity)
    if existing is not None:
        return existing, False
    token = f"node_{len(memo):05d}"
    memo[identity] = token
    return token, True


def _static_semantic_code(
    value: CodeType,
    state: dict[str, object],
    depth: int,
) -> dict[str, object]:
    if type(value) is not CodeType:
        raise _ContractError("static scanner callable has no exact code")
    _static_semantic_step(state, depth)
    constants = []
    for constant in value.co_consts:
        if type(constant) is CodeType:
            constants.append(
                {
                    "kind": "code",
                    "value": _static_semantic_code(
                        constant, state, depth + 1
                    ),
                }
            )
        else:
            constants.append(
                _static_semantic_value(
                    constant,
                    state,
                    depth + 1,
                    binding_name="code_constant",
                )
            )
    summary = {
        "argcount": value.co_argcount,
        "posonlyargcount": value.co_posonlyargcount,
        "kwonlyargcount": value.co_kwonlyargcount,
        "nlocals": value.co_nlocals,
        "stacksize": value.co_stacksize,
        "flags": value.co_flags,
        "bytecode": value.co_code.hex(),
        "constants": constants,
        "names": list(value.co_names),
        "varnames": list(value.co_varnames),
        "freevars": list(value.co_freevars),
        "cellvars": list(value.co_cellvars),
    }
    exception_table = getattr(value, "co_exceptiontable", b"")
    if type(exception_table) is not bytes:
        raise _ContractError(
            "static scanner code exception table is not exact bytes"
        )
    summary["exception_table"] = exception_table.hex()
    return summary


def _static_code_binding_accesses(
    value: CodeType,
    namespace: Mapping[str, object],
) -> tuple[
    dict[str, tuple[tuple[str, ...], ...]],
    dict[str, tuple[str, ...]],
]:
    pending = [value]
    accesses: dict[str, set[tuple[str, ...]]] = {}
    class_members: dict[str, set[str]] = {}
    steps = 0
    while pending:
        code = pending.pop()
        steps += 1
        if steps > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner code dependency exceeds the node bound"
            )
        try:
            instructions = tuple(dis.get_instructions(code))
        except (TypeError, ValueError) as error:
            raise _ContractError(
                "static scanner cannot inspect dependency bytecode"
            ) from error
        local_classes: dict[str, set[str]] = {}
        for index, instruction in enumerate(instructions):
            if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
                continue
            name = instruction.argval
            if type(name) is not str:
                raise _ContractError(
                    "static scanner global bytecode name is not exact"
                )
            path = []
            cursor = index + 1
            while cursor < len(instructions) and instructions[
                cursor
            ].opname in {"LOAD_ATTR", "LOAD_METHOD"}:
                attribute_name = instructions[cursor].argval
                if type(attribute_name) is not str:
                    raise _ContractError(
                        "static scanner attribute bytecode name is not exact"
                    )
                path.append(attribute_name)
                cursor += 1
            accesses.setdefault(name, set()).add(tuple(path))
            dependency = namespace.get(name)
            if not isinstance(dependency, type) or (
                type.__getattribute__(dependency, "__module__"),
                type.__getattribute__(dependency, "__qualname__"),
            ) not in _STATIC_SCANNER_INTERNAL_RECEIVER_CLASS_BINDINGS:
                continue
            for call_index in range(
                index + 1, min(index + 17, len(instructions))
            ):
                if instructions[call_index].opname not in {
                    "CALL_FUNCTION",
                    "CALL_FUNCTION_KW",
                    "CALL_FUNCTION_EX",
                    "CALL_METHOD",
                }:
                    continue
                for store_index in range(
                    call_index + 1,
                    min(call_index + 4, len(instructions)),
                ):
                    if instructions[store_index].opname == "STORE_FAST":
                        local_name = instructions[store_index].argval
                        if type(local_name) is str:
                            local_classes.setdefault(local_name, set()).add(
                                name
                            )
                        break
                break
        for index, instruction in enumerate(instructions):
            if not (
                instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}
                and instruction.argval == "isinstance"
            ):
                continue
            local_names = set()
            class_names = set()
            for cursor in range(
                index + 1, min(index + 17, len(instructions))
            ):
                current = instructions[cursor]
                if current.opname == "LOAD_FAST" and type(
                    current.argval
                ) is str:
                    local_names.add(current.argval)
                elif current.opname in {"LOAD_GLOBAL", "LOAD_NAME"}:
                    class_name = current.argval
                    if type(class_name) is str and isinstance(
                        namespace.get(class_name), type
                    ) and (
                        type.__getattribute__(
                            namespace[class_name], "__module__"
                        ),
                        type.__getattribute__(
                            namespace[class_name], "__qualname__"
                        ),
                    ) in _STATIC_SCANNER_INTERNAL_RECEIVER_CLASS_BINDINGS:
                        class_names.add(class_name)
                elif current.opname in {
                    "CALL_FUNCTION",
                    "CALL_FUNCTION_KW",
                    "CALL_FUNCTION_EX",
                    "CALL_METHOD",
                }:
                    for local_name in local_names:
                        local_classes.setdefault(local_name, set()).update(
                            class_names
                        )
                    break
        for index, instruction in enumerate(instructions[:-1]):
            if instruction.opname != "LOAD_FAST":
                continue
            local_name = instruction.argval
            if local_name not in local_classes:
                continue
            attribute = instructions[index + 1]
            if attribute.opname != "LOAD_METHOD" or type(
                attribute.argval
            ) is not str:
                continue
            for class_name in local_classes[local_name]:
                class_members.setdefault(class_name, set()).add(
                    attribute.argval
                )
        pending.extend(
            constant
            for constant in code.co_consts
            if type(constant) is CodeType
        )
    return (
        {
            name: tuple(sorted(paths))
            for name, paths in sorted(accesses.items())
        },
        {
            name: tuple(sorted(members))
            for name, members in sorted(class_members.items())
        },
    )


def _static_code_class_usages(
    value: CodeType,
    namespace: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    """Resolve direct class calls and receiver slots without executing them.

    Each bytecode offset receives a bounded abstract stack/local state.  States
    reaching the same offset are joined before the instruction is evaluated so
    a class binding from either side of a branch remains visible, while a later
    sequential store still replaces the earlier value on that path.
    """

    usages: dict[str, dict[str, object]] = {}
    pending = [value]
    code_steps = 0
    instruction_steps = 0
    dataflow_steps = 0

    def class_binding(name: object) -> object:
        if type(name) is not str:
            return None
        candidate = namespace.get(name)
        if candidate is None and name in _STATIC_SCANNER_BUILTIN_BINDINGS:
            candidate = vars(_builtins).get(name)
        return candidate if isinstance(candidate, type) else None

    def usage(name: str) -> dict[str, object]:
        return usages.setdefault(
            name,
            {"constructed": False, "members": set()},
        )

    def abstract_value(
        *,
        classes: frozenset[str] = frozenset(),
        instances: frozenset[str] = frozenset(),
        members: frozenset[str] = frozenset(),
        may_other: bool = False,
        may_unbound: bool = False,
    ) -> tuple[object, ...]:
        return (
            classes,
            instances,
            members,
            may_other,
            may_unbound,
        )

    other_value = abstract_value(may_other=True)
    unbound_value = abstract_value(may_unbound=True)

    def join_value(left: object, right: object) -> object:
        if not (
            type(left) is tuple
            and len(left) == 5
            and type(right) is tuple
            and len(right) == 5
        ):
            raise _ContractError(
                "static scanner class usage value is not exact"
            )
        return abstract_value(
            classes=left[0] | right[0],
            instances=left[1] | right[1],
            members=left[2] | right[2],
            may_other=left[3] or right[3],
            may_unbound=left[4] or right[4],
        )

    def join_state(
        current: tuple[tuple[object, ...], dict[str, object]] | None,
        incoming: tuple[tuple[object, ...], dict[str, object]],
    ) -> tuple[tuple[object, ...], dict[str, object]]:
        if current is None:
            return incoming[0], dict(incoming[1])
        current_stack, current_locals = current
        incoming_stack, incoming_locals = incoming
        if len(current_stack) != len(incoming_stack):
            raise _ContractError(
                "static scanner class usage has inconsistent stack flow"
            )
        joined_stack = tuple(
            join_value(left, right)
            for left, right in zip(current_stack, incoming_stack)
        )
        joined_locals = {
            name: join_value(
                current_locals.get(name, unbound_value),
                incoming_locals.get(name, unbound_value),
            )
            for name in current_locals.keys() | incoming_locals.keys()
        }
        return joined_stack, joined_locals

    def stack_effect(instruction, *, jump: bool | None = None) -> int:
        kwargs = {} if jump is None else {"jump": jump}
        try:
            return dis.stack_effect(
                instruction.opcode,
                instruction.arg,
                **kwargs,
            )
        except (TypeError, ValueError):
            try:
                return dis.stack_effect(instruction.opcode, **kwargs)
            except (TypeError, ValueError) as error:
                raise _ContractError(
                    "static scanner class usage has unknown bytecode"
                ) from error

    def apply_effect(
        stack: list[object],
        instruction,
        *,
        jump: bool | None = None,
    ) -> None:
        effect = stack_effect(instruction, jump=jump)
        if effect < 0:
            if len(stack) < -effect:
                raise _ContractError(
                    "static scanner class usage stack underflowed"
                )
            del stack[effect:]
        elif effect > 0:
            stack.extend(other_value for _index in range(effect))

    def successors(instructions, index, instruction):
        next_index = index + 1
        target_offset = (
            instruction.argval
            if instruction.opcode in dis.hasjabs + dis.hasjrel
            and type(instruction.argval) is int
            else None
        )
        target_index = (
            offsets.get(target_offset)
            if target_offset is not None
            else None
        )
        opname = instruction.opname
        if opname in {
            "RETURN_VALUE",
            "RAISE_VARARGS",
            "RERAISE",
        }:
            return ()
        if target_offset is None:
            return ((next_index, None),) if next_index < len(instructions) else ()
        if target_index is None:
            raise _ContractError(
                "static scanner class usage jump target is unavailable"
            )
        if opname in {
            "JUMP_ABSOLUTE",
            "JUMP_FORWARD",
            "JUMP_BACKWARD",
            "JUMP_BACKWARD_NO_INTERRUPT",
            "CONTINUE_LOOP",
        }:
            return ((target_index, True),)
        branches = [(target_index, True)]
        if next_index < len(instructions):
            branches.append((next_index, False))
        return tuple(branches)

    while pending:
        code = pending.pop()
        code_steps += 1
        if code_steps > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner class usage exceeds the node bound"
            )
        try:
            instructions = tuple(dis.get_instructions(code))
        except (TypeError, ValueError) as error:
            raise _ContractError(
                "static scanner cannot inspect class usage bytecode"
            ) from error
        instruction_steps += len(instructions)
        if instruction_steps > _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT:
            raise _ContractError(
                "static scanner class usage exceeds the edge bound"
            )
        offsets = {
            instruction.offset: index
            for index, instruction in enumerate(instructions)
        }
        states: dict[
            int,
            tuple[tuple[object, ...], dict[str, object]],
        ] = {0: ((), {})}
        worklist = [0]
        worklist_index = 0
        while worklist_index < len(worklist):
            index = worklist[worklist_index]
            worklist_index += 1
            dataflow_steps += 1
            if dataflow_steps > _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT:
                raise _ContractError(
                    "static scanner class usage data flow exceeds the edge "
                    "bound"
                )
            stack_tuple, locals_state = states[index]
            stack = list(stack_tuple)
            locals_by_name = dict(locals_state)
            instruction = instructions[index]
            opname = instruction.opname
            if opname in {"LOAD_GLOBAL", "LOAD_NAME"}:
                name = instruction.argval
                if class_binding(name) is not None:
                    stack.append(
                        abstract_value(classes=frozenset({name}))
                    )
                    usage(name)
                else:
                    stack.append(other_value)
            elif opname == "LOAD_FAST":
                stack.append(
                    locals_by_name.get(instruction.argval, unbound_value)
                )
            elif opname == "STORE_FAST":
                if not stack:
                    raise _ContractError(
                        "static scanner class usage stack underflowed"
                    )
                locals_by_name[instruction.argval] = stack.pop()
            elif opname == "DELETE_FAST":
                locals_by_name.pop(instruction.argval, None)
            elif opname in {"LOAD_ATTR", "LOAD_METHOD"}:
                receiver = stack.pop() if stack else unbound_value
                receiver_names = receiver[0] | receiver[1]
                for name in receiver_names:
                    usage(name)["members"].add(instruction.argval)
                stack.append(
                    abstract_value(
                        members=receiver_names,
                        may_other=(
                            receiver[3]
                            or receiver[4]
                            or bool(receiver[2])
                        ),
                    )
                )
            elif opname in {
                "CALL_FUNCTION",
                "CALL_METHOD",
                "CALL",
            }:
                argument_count = instruction.arg or 0
                for _index in range(argument_count):
                    if stack:
                        stack.pop()
                called = stack.pop() if stack else unbound_value
                for name in called[0]:
                    usage(name)["constructed"] = True
                stack.append(
                    abstract_value(
                        instances=called[0],
                        may_other=(
                            called[3]
                            or called[4]
                            or bool(called[1])
                            or bool(called[2])
                        ),
                    )
                )
            elif opname == "CALL_FUNCTION_KW":
                argument_count = instruction.arg or 0
                if stack:
                    stack.pop()
                for _index in range(argument_count):
                    if stack:
                        stack.pop()
                called = stack.pop() if stack else unbound_value
                for name in called[0]:
                    usage(name)["constructed"] = True
                stack.append(
                    abstract_value(
                        instances=called[0],
                        may_other=(
                            called[3]
                            or called[4]
                            or bool(called[1])
                            or bool(called[2])
                        ),
                    )
                )
            elif opname == "CALL_FUNCTION_EX":
                if instruction.arg and instruction.arg & 1:
                    if stack:
                        stack.pop()
                if stack:
                    stack.pop()
                called = stack.pop() if stack else unbound_value
                for name in called[0]:
                    usage(name)["constructed"] = True
                stack.append(
                    abstract_value(
                        instances=called[0],
                        may_other=(
                            called[3]
                            or called[4]
                            or bool(called[1])
                            or bool(called[2])
                        ),
                    )
                )
            elif opname in {"PRECALL", "KW_NAMES", "PUSH_NULL", "CACHE"}:
                pass
            elif opname == "LOAD_CONST":
                stack.append(other_value)
            elif opname not in {
                "RETURN_VALUE",
                "RAISE_VARARGS",
                "RERAISE",
            }:
                apply_effect(stack, instruction)
                if stack and (
                    opname.startswith(("BINARY_", "INPLACE_", "UNARY_"))
                    or opname.startswith("BUILD_")
                    or opname
                    in {
                        "COMPARE_OP",
                        "CONTAINS_OP",
                        "FORMAT_VALUE",
                        "GET_ITER",
                        "IS_OP",
                    }
                ):
                    stack[-1] = other_value
            outgoing = (tuple(stack), locals_by_name)
            for successor, jump in successors(
                instructions, index, instruction
            ):
                successor_stack = list(outgoing[0])
                if instruction.opcode in dis.hasjabs + dis.hasjrel:
                    baseline_effect = stack_effect(instruction)
                    branch_effect = stack_effect(instruction, jump=jump)
                    difference = branch_effect - baseline_effect
                    if difference < 0:
                        if len(successor_stack) < -difference:
                            raise _ContractError(
                                "static scanner class usage branch stack "
                                "underflowed"
                            )
                        del successor_stack[difference:]
                    elif difference > 0:
                        successor_stack.extend(
                            other_value for _index in range(difference)
                        )
                incoming = (tuple(successor_stack), dict(outgoing[1]))
                joined = join_state(states.get(successor), incoming)
                if states.get(successor) != joined:
                    states[successor] = joined
                    worklist.append(successor)
        pending.extend(
            constant
            for constant in code.co_consts
            if type(constant) is CodeType
        )
    return usages


def _static_exact_class_member(
    value: type,
    name: str,
) -> tuple[type, object]:
    try:
        mro = type.__getattribute__(value, "__mro__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(
            "static scanner class hierarchy is not exact"
        ) from error
    if type(mro) is not tuple:
        raise _ContractError("static scanner class hierarchy is not exact")
    for owner in mro:
        if not isinstance(owner, type):
            raise _ContractError(
                "static scanner class hierarchy is not exact"
            )
        namespace = type.__getattribute__(owner, "__dict__")
        if type(namespace) is not MappingProxyType:
            raise _ContractError(
                "static scanner class namespace is not exact"
            )
        if name in namespace:
            return owner, namespace[name]
    raise _ContractError(
        "static scanner referenced class attribute is unavailable"
    )


def _static_external_receiver_class(
    module_name: str,
    qualname: str,
) -> type:
    if (module_name, qualname) == ("pathlib", "Path"):
        value = Path
    elif (module_name, qualname) == ("pathlib", "PurePath"):
        value = PurePath
    elif (module_name, qualname) == ("pathlib", "PurePosixPath"):
        value = PurePosixPath
    elif (module_name, qualname) == ("string", "Formatter"):
        namespace = object.__getattribute__(string, "__dict__")
        if type(namespace) is not dict or "Formatter" not in namespace:
            raise _ContractError(
                "static scanner external receiver class is unavailable"
            )
        value = namespace["Formatter"]
    else:
        raise _ContractError(
            "static scanner external receiver class is not allowlisted"
        )
    if not isinstance(value, type) or (
        type.__getattribute__(value, "__module__"),
        type.__getattribute__(value, "__qualname__"),
    ) != (module_name, qualname):
        raise _ContractError(
            "static scanner external receiver class identity changed"
        )
    return value


def _static_exact_project_function(
    module_name: str,
    qualname: str,
) -> FunctionType:
    if module_name == __name__:
        current: object = globals()
    elif module_name == _adapters.__name__:
        current = object.__getattribute__(_adapters, "__dict__")
    elif module_name == _oracles.__name__:
        current = object.__getattribute__(_oracles, "__dict__")
    else:
        raise _ContractError(
            "static scanner external receiver access site is outside the "
            "semantic module"
        )
    for part in qualname.split("."):
        if type(current) is dict:
            if part not in current:
                raise _ContractError(
                    "static scanner external receiver access site is "
                    "unavailable"
                )
            current = current[part]
            continue
        if isinstance(current, type):
            namespace = type.__getattribute__(current, "__dict__")
            if type(namespace) is not MappingProxyType or part not in namespace:
                raise _ContractError(
                    "static scanner external receiver access site is "
                    "unavailable"
                )
            current = namespace[part]
            if type(current) in (staticmethod, classmethod):
                current = current.__func__
            continue
        raise _ContractError(
            "static scanner external receiver access site is not exact"
        )
    if type(current) is not FunctionType or (
        current.__module__,
        current.__qualname__,
    ) != (module_name, qualname):
        raise _ContractError(
            "static scanner external receiver access site identity changed: "
            f"{module_name}.{qualname}"
        )
    return current


def _static_code_external_receiver_candidates(
    value: CodeType,
    receiver_class: type,
) -> tuple[dict[str, int], int, int]:
    pending = [value]
    code_steps = 0
    instruction_steps = 0
    candidates: dict[str, int] = {}
    member_names = set()
    mro = type.__getattribute__(receiver_class, "__mro__")
    if type(mro) is not tuple:
        raise _ContractError(
            "static scanner external receiver hierarchy is not exact"
        )
    for owner in mro:
        namespace = type.__getattribute__(owner, "__dict__")
        if type(namespace) is not MappingProxyType:
            raise _ContractError(
                "static scanner external receiver namespace is not exact"
            )
        member_names.update(namespace)
    while pending:
        code = pending.pop()
        code_steps += 1
        if code_steps > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner external receiver audit exceeds the node "
                "bound"
            )
        try:
            instructions = tuple(dis.get_instructions(code))
        except (TypeError, ValueError) as error:
            raise _ContractError(
                "static scanner cannot inspect external receiver access"
            ) from error
        instruction_steps += len(instructions)
        if instruction_steps > _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT:
            raise _ContractError(
                "static scanner external receiver audit exceeds the edge "
                "bound"
            )
        for instruction in instructions:
            candidate_name = None
            if instruction.opname in {"LOAD_ATTR", "LOAD_METHOD"} and (
                instruction.argval in member_names
            ):
                candidate_name = instruction.argval
            elif instruction.opname in {
                    "BINARY_OP",
                    "BINARY_TRUE_DIVIDE",
                    "INPLACE_TRUE_DIVIDE",
            } and (
                instruction.opname != "BINARY_OP"
                or instruction.argrepr in {"/", "/="}
            ):
                candidate_name = "__truediv__"
            elif (
                instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}
                and instruction.argval == "str"
            ):
                candidate_name = "__str__"
            if candidate_name is not None:
                candidates[candidate_name] = (
                    candidates.get(candidate_name, 0) + 1
                )
        pending.extend(
            constant
            for constant in code.co_consts
            if type(constant) is CodeType
        )
    return candidates, code_steps, instruction_steps


def _static_resolve_attribute_path(
    value: object,
    path: tuple[str, ...],
    state: dict[str, object],
) -> tuple[object, tuple[str, ...]]:
    current = value
    owners = []
    for name in path:
        _static_semantic_attribute_step(state)
        if type(current) is ModuleType:
            namespace = current.__dict__
            if type(namespace) is not dict or name not in namespace:
                raise _ContractError(
                    "static scanner referenced module attribute is unavailable: "
                    f"{current.__name__}.{name}"
                )
            owners.append(current.__name__)
            current = namespace[name]
            continue
        if isinstance(current, type):
            owner, current = _static_exact_class_member(current, name)
            owners.append(
                f"{type.__getattribute__(owner, '__module__')}."
                f"{type.__getattribute__(owner, '__qualname__')}"
            )
            continue
        current_type = type(current)
        try:
            owner, current = _static_exact_class_member(current_type, name)
        except _ContractError:
            pass
        else:
            owners.append(
                f"{type.__getattribute__(owner, '__module__')}."
                f"{type.__getattribute__(owner, '__qualname__')}"
            )
            continue
        raise _ContractError(
            "static scanner cannot statically resolve attribute dependency: "
            f"{'.'.join(path)}"
        )
    return current, tuple(owners)


def _static_semantic_module(
    value: ModuleType,
    state: dict[str, object],
    depth: int,
    *,
    attribute_paths: tuple[tuple[str, ...], ...],
    binding_name: str,
) -> dict[str, object]:
    if type(value) is not ModuleType or type(value.__name__) is not str:
        raise _ContractError("static scanner module dependency is not exact")
    summary: dict[str, object] = {
        "kind": "module",
        "name": value.__name__,
    }
    bindings = []
    for path in attribute_paths:
        if not path:
            continue
        committed_owner = _COMMITTED_DATA_OWNERS.get(
            (value.__name__, path[0])
        )
        if committed_owner is not None:
            for _name in path:
                _static_semantic_attribute_step(state)
            binding = {
                "kind": "separately_committed_data",
                "owner": committed_owner,
                "access_path": list(path[1:]),
            }
        else:
            resolved, owners = _static_resolve_attribute_path(
                value, path, state
            )
            binding = _static_semantic_value(
                resolved,
                state,
                depth + 1,
                binding_name=f"{binding_name}.{'.'.join(path)}",
            )
            binding = {
                "kind": "live_binding",
                "owners": list(owners),
                "value": binding,
            }
        bindings.append({"path": list(path), "binding": binding})
    summary["bindings"] = bindings
    return summary


def _static_code_receiver_methods(value: CodeType) -> tuple[str, ...]:
    if not value.co_varnames or value.co_argcount < 1:
        return ()
    receiver_name = value.co_varnames[0]
    methods = set()
    try:
        instructions = tuple(dis.get_instructions(value))
    except (TypeError, ValueError) as error:
        raise _ContractError(
            "static scanner cannot inspect receiver bytecode"
        ) from error
    for index, instruction in enumerate(instructions[:-1]):
        if not (
            instruction.opname == "LOAD_FAST"
            and instruction.argval == receiver_name
            and instructions[index + 1].opname in {
                "LOAD_ATTR",
                "LOAD_METHOD",
            }
            and type(instructions[index + 1].argval) is str
        ):
            continue
        methods.add(instructions[index + 1].argval)
    return tuple(sorted(methods))


def _static_semantic_function_globals(
    value: FunctionType,
    state: dict[str, object],
    depth: int,
    *,
    binding_name: str,
) -> dict[str, object]:
    namespace = value.__globals__
    code = value.__code__
    global_accesses, class_members = _static_code_binding_accesses(
        code, namespace
    )
    class_usages = _static_code_class_usages(code, namespace)
    dependencies = {}
    for name, attribute_paths in global_accesses.items():
        if name in namespace:
            dependency = namespace[name]
        elif name in _STATIC_SCANNER_BUILTIN_BINDINGS:
            builtin_namespace = vars(_builtins)
            if type(builtin_namespace) is not dict or (
                name not in builtin_namespace
            ):
                raise _ContractError(
                    "static scanner external function builtin is "
                    "unavailable"
                )
            dependency = builtin_namespace[name]
        else:
            raise _ContractError(
                "static scanner external function global is not closed: "
                f"{binding_name}.{name}"
            )
        if type(dependency) is ModuleType:
            binding = _static_semantic_module(
                dependency,
                state,
                depth + 1,
                attribute_paths=attribute_paths,
                binding_name=f"{binding_name}.globals.{name}",
            )
        else:
            usage = class_usages.get(name, {})
            binding = _static_semantic_value(
                dependency,
                state,
                depth + 1,
                binding_name=f"{binding_name}.globals.{name}",
                class_member_names=tuple(
                    sorted(
                        set(class_members.get(name, ()))
                        | set(usage.get("members", ()))
                    )
                ),
                constructed_class=(
                    usage.get("constructed") is True
                ),
            )
        dependencies[name] = {
            "access_paths": [list(path) for path in attribute_paths],
            "binding": binding,
        }
    if set(dependencies) != set(global_accesses):
        raise _ContractError(
            "static scanner external function global audit is not inverse"
        )
    return dependencies


def _static_semantic_function(
    value: FunctionType,
    state: dict[str, object],
    depth: int,
    *,
    token: str,
    binding_name: str,
) -> dict[str, object]:
    if type(value) is not FunctionType or type(value.__globals__) is not dict:
        raise _ContractError(
            "static scanner callable cannot be safely normalized"
        )
    module_name = value.__module__
    qualname = value.__qualname__
    if type(module_name) is not str or type(qualname) is not str:
        raise _ContractError(
            "static scanner callable identity is not exact"
        )
    if module_name not in _STATIC_SCANNER_SEMANTIC_MODULES or (
        qualname.startswith("__create_fn__.")
    ):
        dependencies = _static_semantic_function_globals(
            value,
            state,
            depth + 1,
            binding_name=binding_name,
        )
        closure_values = []
        for cell in value.__closure__ or ():
            try:
                cell_value = cell.cell_contents
            except ValueError as error:
                raise _ContractError(
                    "static scanner callable has an empty closure cell"
                ) from error
            closure_values.append(
                _static_semantic_value(
                    cell_value,
                    state,
                    depth + 1,
                    binding_name=f"{binding_name}.closure",
                )
            )
        return {
            "kind": "external_function",
            "token": token,
            "module": module_name,
            "qualname": qualname,
            "code": _static_semantic_code(
                value.__code__, state, depth + 1
            ),
            "defaults": _static_semantic_value(
                value.__defaults__,
                state,
                depth + 1,
                binding_name=f"{binding_name}.defaults",
            ),
            "kwdefaults": _static_semantic_value(
                value.__kwdefaults__,
                state,
                depth + 1,
                binding_name=f"{binding_name}.kwdefaults",
            ),
            "closure": closure_values,
            "annotations": _static_semantic_value(
                value.__annotations__,
                state,
                depth + 1,
                binding_name=f"{binding_name}.annotations",
            ),
            "globals": dependencies,
        }
    project_function_key = (module_name, qualname)
    committed_function = state["project_functions"].get(
        project_function_key
    )
    if committed_function is not None and committed_function is not value:
        raise _ContractError(
            "static scanner project function identity is ambiguous: "
            f"{module_name}.{qualname}"
        )
    state["project_functions"][project_function_key] = value
    code = value.__code__
    global_accesses, class_members = _static_code_binding_accesses(
        code, value.__globals__
    )
    class_usages = _static_code_class_usages(code, value.__globals__)
    dependencies = {}
    for name, attribute_paths in global_accesses.items():
        if name in value.__globals__:
            dependency = value.__globals__[name]
            if type(dependency) is BuiltinFunctionType:
                raise _ContractError(
                    "static scanner project callable binding was replaced "
                    "by an uninspectable builtin"
                )
        elif name in _STATIC_SCANNER_BUILTIN_BINDINGS:
            namespace = vars(_builtins)
            if type(namespace) is not dict or name not in namespace:
                raise _ContractError(
                    "static scanner allowlisted builtin binding is unavailable"
                )
            dependency = namespace[name]
        else:
            raise _ContractError(
                "static scanner global dependency is not explicitly bound: "
                f"{binding_name}.{name}"
            )
        committed_owner = _COMMITTED_DATA_OWNERS.get((module_name, name))
        if committed_owner is not None:
            dependencies[name] = {
                "kind": "separately_committed_data",
                "owner": committed_owner,
            }
            continue
        if type(dependency) is ModuleType:
            dependencies[name] = _static_semantic_module(
                dependency,
                state,
                depth + 1,
                attribute_paths=attribute_paths,
                binding_name=f"{binding_name}.{name}",
            )
        else:
            usage = class_usages.get(name, {})
            dependencies[name] = _static_semantic_value(
                dependency,
                state,
                depth + 1,
                binding_name=f"{binding_name}.{name}",
                class_member_names=tuple(
                    sorted(
                        set(class_members.get(name, ()))
                        | set(usage.get("members", ()))
                    )
                ),
                constructed_class=(
                    usage.get("constructed") is True
                ),
            )
    receiver_methods = {}
    qualname_parts = qualname.split(".")
    if len(qualname_parts) >= 2:
        owner = value.__globals__.get(qualname_parts[-2])
        if isinstance(owner, type):
            for name in _static_code_receiver_methods(code):
                try:
                    _member_owner, member = _static_exact_class_member(
                        owner, name
                    )
                except _ContractError:
                    continue
                descriptor_value = (
                    object.__getattribute__(member, "__func__")
                    if type(member) in (staticmethod, classmethod)
                    else member
                )
                if type(descriptor_value) is not FunctionType:
                    continue
                _static_semantic_attribute_step(state)
                receiver_methods[name] = _static_semantic_class_member(
                    _member_owner,
                    member,
                    state,
                    depth + 1,
                    binding_name=f"{binding_name}.receiver.{name}",
                )
    closure_values = []
    for cell in value.__closure__ or ():
        try:
            cell_value = cell.cell_contents
        except ValueError as error:
            raise _ContractError(
                "static scanner callable has an empty closure cell"
            ) from error
        closure_values.append(
            _static_semantic_value(
                cell_value,
                state,
                depth + 1,
                binding_name=f"{binding_name}.closure",
            )
        )
    return {
        "kind": "function",
        "token": token,
        "module": module_name,
        "qualname": qualname,
        "code": _static_semantic_code(code, state, depth + 1),
        "defaults": _static_semantic_value(
            value.__defaults__,
            state,
            depth + 1,
            binding_name=f"{binding_name}.defaults",
        ),
        "kwdefaults": _static_semantic_value(
            value.__kwdefaults__,
            state,
            depth + 1,
            binding_name=f"{binding_name}.kwdefaults",
        ),
        "closure": closure_values,
        "annotations": _static_semantic_value(
            value.__annotations__,
            state,
            depth + 1,
            binding_name=f"{binding_name}.annotations",
        ),
        "globals": dependencies,
        "receiver_methods": receiver_methods,
    }


def _static_semantic_class_member(
    owner: type,
    member: object,
    state: dict[str, object],
    depth: int,
    *,
    binding_name: str,
) -> dict[str, object]:
    descriptor_kind = "ordinary"
    descriptor_value = member
    if type(member) is staticmethod:
        descriptor_kind = "staticmethod"
        descriptor_value = object.__getattribute__(member, "__func__")
    elif type(member) is classmethod:
        descriptor_kind = "classmethod"
        descriptor_value = object.__getattribute__(member, "__func__")
    return {
        "owner_module": type.__getattribute__(owner, "__module__"),
        "owner_qualname": type.__getattribute__(owner, "__qualname__"),
        "descriptor_kind": descriptor_kind,
        "value": _static_semantic_value(
            descriptor_value,
            state,
            depth + 1,
            binding_name=binding_name,
        ),
    }


def _static_semantic_dataclass_fields(
    value: type,
    state: dict[str, object],
    depth: int,
    *,
    binding_name: str,
) -> object:
    try:
        _owner, field_mapping = _static_exact_class_member(
            value, "__dataclass_fields__"
        )
    except _ContractError:
        return None
    if type(field_mapping) is not dict:
        raise _ContractError(
            "static scanner dataclass fields are not exact"
        )
    normalized = []
    for field_name, field_value in field_mapping.items():
        if type(field_name) is not str:
            raise _ContractError(
                "static scanner dataclass field name is not exact"
            )
        try:
            declared_name = object.__getattribute__(field_value, "name")
            metadata = object.__getattribute__(field_value, "metadata")
            init = object.__getattribute__(field_value, "init")
            represent = object.__getattribute__(field_value, "repr")
            compare = object.__getattribute__(field_value, "compare")
            hash_value = object.__getattribute__(field_value, "hash")
        except AttributeError as error:
            raise _ContractError(
                "static scanner dataclass field metadata is not exact"
            ) from error
        if (
            declared_name != field_name
            or type(metadata) is not MappingProxyType
        ):
            raise _ContractError(
                "static scanner dataclass field metadata is not exact"
            )
        normalized.append(
            {
                "name": field_name,
                "metadata": _static_semantic_value(
                    metadata,
                    state,
                    depth + 1,
                    binding_name=(
                        f"{binding_name}.dataclass.{field_name}.metadata"
                    ),
                ),
                "init": init,
                "repr": represent,
                "compare": compare,
                "hash": hash_value,
            }
        )
    return normalized


def _static_semantic_enum_members(
    value: type,
    state: dict[str, object],
    depth: int,
    *,
    binding_name: str,
) -> object:
    namespace = type.__getattribute__(value, "__dict__")
    if type(namespace) is not MappingProxyType:
        raise _ContractError("static scanner enum namespace is not exact")
    member_mapping = namespace.get("_member_map_")
    if member_mapping is None:
        return None
    if type(member_mapping) is not dict:
        raise _ContractError("static scanner enum members are not exact")
    normalized = []
    for member_name, member in member_mapping.items():
        if type(member_name) is not str:
            raise _ContractError(
                "static scanner enum member name is not exact"
            )
        try:
            member_value = object.__getattribute__(member, "_value_")
        except AttributeError as error:
            raise _ContractError(
                "static scanner enum member value is not exact"
            ) from error
        normalized.append(
            {
                "name": member_name,
                "value": _static_semantic_value(
                    member_value,
                    state,
                    depth + 1,
                    binding_name=(
                        f"{binding_name}.enum.{member_name}"
                    ),
                ),
            }
        )
    return normalized


def _static_init_calls_post_init(value: type, init_member: object) -> bool:
    """Return whether the effective initializer can invoke ``__post_init__``."""

    if type(init_member) in (staticmethod, classmethod):
        init_member = object.__getattribute__(init_member, "__func__")
    if type(init_member) is not FunctionType:
        return False
    code = init_member.__code__
    if "__post_init__" in code.co_names:
        return True
    try:
        instructions = tuple(dis.get_instructions(code))
    except (TypeError, ValueError) as error:
        raise _ContractError(
            "static scanner cannot inspect class initializer bytecode"
        ) from error
    helper_loaded = False
    class_loaded = False
    for instruction in instructions:
        if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}:
            name = instruction.argval
            dependency = (
                init_member.__globals__.get(name)
                if type(name) is str
                else None
            )
            helper_loaded = helper_loaded or dependency is _initialize_contract
            class_loaded = class_loaded or dependency is value
            continue
        if instruction.opname in {
            "CALL_FUNCTION",
            "CALL_FUNCTION_KW",
            "CALL_FUNCTION_EX",
            "CALL_METHOD",
            "CALL",
        }:
            if helper_loaded and class_loaded:
                helper_code = getattr(_initialize_contract, "__code__", None)
                if type(helper_code) is CodeType and (
                    "__post_init__" in helper_code.co_names
                ):
                    return True
            helper_loaded = False
            class_loaded = False
        elif instruction.opcode in dis.hasjabs + dis.hasjrel:
            helper_loaded = False
            class_loaded = False
    return False


def _static_semantic_class(
    value: type,
    state: dict[str, object],
    depth: int,
    *,
    token: str,
    binding_name: str,
    member_names: tuple[str, ...],
    constructed: bool,
) -> dict[str, object]:
    module_name = value.__module__
    qualname = value.__qualname__
    if type(module_name) is not str or type(qualname) is not str:
        raise _ContractError("static scanner class identity is not exact")
    summary: dict[str, object] = {
        "kind": "class",
        "token": token,
        "module": module_name,
        "qualname": qualname,
        "constructed": constructed,
    }
    active_classes = state.setdefault("active_classes", set())
    class_identity = id(value)
    if class_identity in active_classes:
        return {
            "kind": "class_reference",
            "module": module_name,
            "qualname": qualname,
            "constructed": constructed,
        }
    active_classes.add(class_identity)
    try:
        mro = type.__getattribute__(value, "__mro__")
        if type(mro) is not tuple or any(
            not isinstance(owner, type) for owner in mro
        ):
            raise _ContractError(
                "static scanner class hierarchy is not exact"
            )
        summary["mro"] = [
            [
                type.__getattribute__(owner, "__module__"),
                type.__getattribute__(owner, "__qualname__"),
            ]
            for owner in mro
        ]
        protocol_members = set(member_names)
        effective_visit_owners = None
        if constructed and ast.NodeTransformer in mro and (
            "visit" in protocol_members
        ):
            effective_visit_owners = {}
            subclass_overrides = []
            for owner_index, owner in enumerate(mro):
                namespace = type.__getattribute__(owner, "__dict__")
                if type(namespace) is not MappingProxyType:
                    raise _ContractError(
                        "static scanner visitor namespace is not exact"
                    )
                for name in namespace:
                    if (
                        type(name) is str
                        and name.startswith("visit_")
                        and name not in effective_visit_owners
                    ):
                        effective_visit_owners[name] = owner
                        if owner_index == 0:
                            subclass_overrides.append(name)
            effective_names = tuple(sorted(effective_visit_owners))
            protocol_members.update(
                {"visit", "generic_visit", *effective_names}
            )
            summary["dynamic_visitor_protocol"] = {
                "base_visit": "visit",
                "generic_visit": "generic_visit",
                "overrides": sorted(subclass_overrides),
                "effective_slots": [
                    {
                        "name": name,
                        "owner_module": type.__getattribute__(
                            effective_visit_owners[name], "__module__"
                        ),
                        "owner_qualname": type.__getattribute__(
                            effective_visit_owners[name], "__qualname__"
                        ),
                    }
                    for name in effective_names
                ],
            }
        members = {}
        for name in sorted(protocol_members):
            _static_semantic_attribute_step(state)
            try:
                owner, member = _static_exact_class_member(value, name)
            except _ContractError:
                continue
            members[name] = _static_semantic_class_member(
                owner,
                member,
                state,
                depth + 1,
                binding_name=f"{binding_name}.{name}",
            )
        if effective_visit_owners is not None:
            expected_names = set(effective_visit_owners)
            committed_names = {
                name for name in members if name.startswith("visit_")
            }
            if committed_names != expected_names:
                raise _ContractError(
                    "static scanner dynamic visitor protocol coverage is "
                    "incomplete"
                )
            for name, expected_owner in effective_visit_owners.items():
                actual_owner, _member = _static_exact_class_member(
                    value, name
                )
                if actual_owner is not expected_owner:
                    raise _ContractError(
                        "static scanner dynamic visitor protocol owner is "
                        "inconsistent"
                    )
            summary["dynamic_visitor_protocol"]["audit"] = {
                "effective_slots": len(expected_names),
                "committed_slots": len(committed_names),
                "missing_slots": [],
                "unreferenced_slots": [],
            }
        summary["members"] = members
        if constructed:
            metaclass = type(value)
            metaclass_mro = type.__getattribute__(metaclass, "__mro__")
            summary["metaclass"] = {
                "module": type.__getattribute__(metaclass, "__module__"),
                "qualname": type.__getattribute__(metaclass, "__qualname__"),
                "mro": [
                    [
                        type.__getattribute__(owner, "__module__"),
                        type.__getattribute__(owner, "__qualname__"),
                    ]
                    for owner in metaclass_mro
                ],
            }
            call_owner, call_member = _static_exact_class_member(
                metaclass, "__call__"
            )
            lifecycle = {
                "metaclass.__call__": _static_semantic_class_member(
                    call_owner,
                    call_member,
                    state,
                    depth + 1,
                    binding_name=f"{binding_name}.metaclass.__call__",
                )
            }
            init_member = None
            for lifecycle_name in ("__new__", "__init__"):
                owner, member = _static_exact_class_member(
                    value, lifecycle_name
                )
                if lifecycle_name == "__init__":
                    init_member = member
                lifecycle[lifecycle_name] = (
                    _static_semantic_class_member(
                        owner,
                        member,
                        state,
                        depth + 1,
                        binding_name=(
                            f"{binding_name}.lifecycle.{lifecycle_name}"
                        ),
                    )
                )
            if _static_init_calls_post_init(value, init_member):
                try:
                    owner, member = _static_exact_class_member(
                        value, "__post_init__"
                    )
                except _ContractError as error:
                    raise _ContractError(
                        "static scanner class initializer references an "
                        "unavailable __post_init__"
                    ) from error
                lifecycle["__post_init__"] = (
                    _static_semantic_class_member(
                        owner,
                        member,
                        state,
                        depth + 1,
                        binding_name=(
                            f"{binding_name}.lifecycle.__post_init__"
                        ),
                    )
                )
            summary["lifecycle"] = lifecycle
            if module_name in _STATIC_SCANNER_SEMANTIC_MODULES:
                summary["dataclass_fields"] = (
                    _static_semantic_dataclass_fields(
                        value,
                        state,
                        depth + 1,
                        binding_name=binding_name,
                    )
                )
                summary["enum_members"] = _static_semantic_enum_members(
                    value,
                    state,
                    depth + 1,
                    binding_name=binding_name,
                )
        return summary
    finally:
        active_classes.remove(class_identity)


def _static_commitment_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
        raise _ContractError(
            "static scanner semantic commitment is not canonical"
        ) from error


def _static_exact_mappingproxy_mapping(value: object) -> dict:
    if type(value) is not MappingProxyType:
        raise _ContractError(
            "static scanner semantic mapping proxy is not exact"
        )
    referents = gc.get_referents(value)
    if (
        type(referents) is not list
        or len(referents) != 1
        or type(referents[0]) is not dict
    ):
        raise _ContractError(
            "static scanner semantic mapping proxy does not wrap an exact "
            "dict"
        )
    return referents[0]


def _static_semantic_set_sort_key(value: object, depth: int) -> object:
    if depth > _STATIC_SCANNER_COMMITMENT_DEPTH_LIMIT:
        raise _ContractError(
            "static scanner semantic set key exceeds the depth bound"
        )
    if value is None or type(value) in (bool, str):
        if type(value) is str:
            if len(value) > _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT:
                raise _ContractError(
                    "static scanner semantic set text exceeds the bound"
                )
            if len(value.encode("utf-8")) > (
                _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT
            ):
                raise _ContractError(
                    "static scanner semantic set text exceeds the bound"
                )
        return {"kind": type(value).__name__, "value": value}
    if value is Ellipsis:
        return {"kind": "ellipsis"}
    if value is NotImplemented:
        return {"kind": "not_implemented"}
    if type(value) is bytes:
        if len(value) > _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT:
            raise _ContractError(
                "static scanner semantic set bytes exceed the bound"
            )
        return {"kind": "bytes", "value": value.hex()}
    if type(value) is int:
        if value.bit_length() > _STATIC_SCANNER_COMMITMENT_INTEGER_BITS_LIMIT:
            raise _ContractError(
                "static scanner semantic set integer exceeds the bound"
            )
        return {"kind": "int", "value": value}
    value_type = type(value)
    value_type_identity = (
        type.__getattribute__(value_type, "__module__"),
        type.__getattribute__(value_type, "__qualname__"),
    )
    if value_type_identity == ("sre_constants", "_NamedIntConstant"):
        namespace = object.__getattribute__(value, "__dict__")
        if type(namespace) is not dict or set(namespace) != {"name"} or (
            type(namespace["name"]) is not str
        ):
            raise _ContractError(
                "static scanner named integer constant is not exact"
            )
        return {
            "kind": "named_int_constant",
            "name": namespace["name"],
            "value": int.__int__(value),
        }
    if isinstance(value, Enum):
        return {
            "kind": "external_enum_member",
            "module": value_type_identity[0],
            "qualname": value_type_identity[1],
            "name": object.__getattribute__(value, "_name_"),
            "value": _static_semantic_set_sort_key(
                object.__getattribute__(value, "_value_"), depth + 1
            ),
        }
    if type(value) is float:
        if math.isnan(value):
            return {"kind": "float", "value": "nan"}
        if math.isinf(value):
            return {
                "kind": "float",
                "value": "positive_inf" if value > 0 else "negative_inf",
            }
        return {"kind": "float", "value": value}
    if type(value) is complex:
        return {
            "kind": "complex",
            "real": _static_semantic_set_sort_key(value.real, depth + 1),
            "imag": _static_semantic_set_sort_key(value.imag, depth + 1),
        }
    if type(value) is tuple:
        if len(value) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner semantic set tuple exceeds the bound"
            )
        return {
            "kind": "tuple",
            "items": [
                _static_semantic_set_sort_key(item, depth + 1)
                for item in value
            ],
        }
    if type(value) is frozenset:
        if len(value) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner nested frozen set exceeds the bound"
            )
        items = [
            _static_semantic_set_sort_key(item, depth + 1)
            for item in value
        ]
        items.sort(key=_static_commitment_bytes)
        return {"kind": "frozenset", "items": items}
    raise _ContractError(
        "static scanner semantic set element cannot be safely ordered"
    )


def _static_semantic_native_callable(
    value: object,
    state: dict[str, object],
    depth: int,
    *,
    token: str,
    binding_name: str,
) -> dict[str, object]:
    value_type = type(value)
    allowed_types = {
        BuiltinFunctionType,
        ClassMethodDescriptorType,
        GetSetDescriptorType,
        MemberDescriptorType,
        MethodDescriptorType,
        MethodWrapperType,
        WrapperDescriptorType,
    }
    if value_type not in allowed_types:
        raise _ContractError(
            "static scanner native binding type is not allowlisted"
        )
    identity = {}
    for name in ("__module__", "__qualname__", "__name__"):
        try:
            item = object.__getattribute__(value, name)
        except AttributeError:
            item = None
        if item is not None and type(item) is not str:
            raise _ContractError(
                "static scanner native binding identity is not exact"
            )
        identity[name.removeprefix("__").removesuffix("__")] = item
    try:
        owner = object.__getattribute__(value, "__objclass__")
    except AttributeError:
        owner = None
    if owner is not None:
        if not isinstance(owner, type):
            raise _ContractError(
                "static scanner native binding owner is not exact"
            )
        identity["owner_module"] = type.__getattribute__(
            owner, "__module__"
        )
        identity["owner_qualname"] = type.__getattribute__(
            owner, "__qualname__"
        )
    identity["kind"] = "native_binding"
    identity["token"] = token
    identity["type_module"] = type.__getattribute__(
        value_type, "__module__"
    )
    identity["type_qualname"] = type.__getattribute__(
        value_type, "__qualname__"
    )
    try:
        bound_self = object.__getattribute__(value, "__self__")
    except AttributeError:
        identity["bound_self"] = None
    else:
        identity["bound_self"] = _static_semantic_value(
            bound_self,
            state,
            depth + 1,
            binding_name=f"{binding_name}.__self__",
        )
    return identity


def _static_semantic_value(
    value: object,
    state: dict[str, object],
    depth: int,
    *,
    binding_name: str,
    class_member_names: tuple[str, ...] = (),
    constructed_class: bool = False,
) -> object:
    _static_semantic_step(state, depth)
    value_type = type(value)
    value_type_module = type.__getattribute__(value_type, "__module__")
    semantic_instance = (
        type(value_type_module) is str
        and value_type_module in _STATIC_SCANNER_SEMANTIC_MODULES
        and value_type is not type
        and value_type is not _FrozenJsonObject
    )
    value_type_qualname = type.__getattribute__(value_type, "__qualname__")
    external_instance = (
        (value_type_module, value_type_qualname)
        in _STATIC_SCANNER_EXTERNAL_INSTANCE_TYPES
    )
    opaque_external_instance = (
        (value_type_module, value_type_qualname)
        in _STATIC_SCANNER_EXTERNAL_OPAQUE_INSTANCE_TYPES
    )
    external_instance_slots = (
        _STATIC_SCANNER_EXTERNAL_INSTANCE_SLOT_PATHS.get(
            (value_type_module, value_type_qualname)
        )
    )
    if value is None or type(value) in (bool, str):
        if type(value) is str and len(value.encode("utf-8")) > (
            _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT
        ):
            raise _ContractError(
                "static scanner semantic text exceeds the byte bound"
            )
        return value
    if value is Ellipsis:
        return {"kind": "ellipsis"}
    if value is NotImplemented:
        return {"kind": "not_implemented"}
    if type(value) is bytes:
        if len(value) > _STATIC_SCANNER_COMMITMENT_VALUE_BYTES_LIMIT:
            raise _ContractError(
                "static scanner semantic bytes exceed the byte bound"
            )
        return {"kind": "bytes", "hex": value.hex()}
    if type(value) is int:
        if value.bit_length() > _STATIC_SCANNER_COMMITMENT_INTEGER_BITS_LIMIT:
            raise _ContractError(
                "static scanner semantic integer exceeds the bound"
            )
        return value
    if type(value) is float:
        if math.isnan(value):
            return {"kind": "float", "value": "nan"}
        if math.isinf(value):
            return {
                "kind": "float",
                "value": "positive_inf" if value > 0 else "negative_inf",
            }
        return value
    if type(value) is complex:
        return {
            "kind": "complex",
            "real": _static_semantic_set_sort_key(value.real, depth + 1),
            "imag": _static_semantic_set_sort_key(value.imag, depth + 1),
        }
    if type(value) is CodeType:
        return {
            "kind": "code",
            "value": _static_semantic_code(value, state, depth + 1),
        }
    if type(value) is ModuleType:
        return _static_semantic_module(
            value,
            state,
            depth + 1,
            attribute_paths=(),
            binding_name=binding_name,
        )
    if type(value) in {
        BuiltinFunctionType,
        ClassMethodDescriptorType,
        GetSetDescriptorType,
        MemberDescriptorType,
        MethodDescriptorType,
        MethodWrapperType,
        WrapperDescriptorType,
    }:
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        return _static_semantic_native_callable(
            value,
            state,
            depth + 1,
            token=token,
            binding_name=binding_name,
        )
    if type(value) is property:
        slots = {}
        for slot_name in ("fget", "fset", "fdel", "__doc__"):
            try:
                slot_value = object.__getattribute__(value, slot_name)
            except (AttributeError, TypeError) as error:
                raise _ContractError(
                    "static scanner property binding is not exact"
                ) from error
            if slot_name == "__doc__" and slot_value is not None and (
                type(slot_value) is not str
            ):
                raise _ContractError(
                    "static scanner property documentation is not exact"
                )
            slots[slot_name] = _static_semantic_value(
                slot_value,
                state,
                depth + 1,
                binding_name=f"{binding_name}.property.{slot_name}",
            )
        return {
            "kind": "property_binding",
            "slots": slots,
        }
    if type(value) in (staticmethod, classmethod):
        descriptor_function = object.__getattribute__(value, "__func__")
        return {
            "kind": (
                "staticmethod_binding"
                if type(value) is staticmethod
                else "classmethod_binding"
            ),
            "function": _static_semantic_value(
                descriptor_function,
                state,
                depth + 1,
                binding_name=f"{binding_name}.__func__",
            ),
        }
    if type(value) is object:
        return {"kind": "sentinel", "binding": binding_name}
    if isinstance(value, type):
        module_name = type.__getattribute__(value, "__module__")
        qualname = type.__getattribute__(value, "__qualname__")
        if type(module_name) is not str or type(qualname) is not str:
            raise _ContractError(
                "static scanner class dependency identity is not exact"
            )
        return _static_semantic_class(
            value,
            state,
            depth + 1,
            token=f"class:{module_name}.{qualname}",
            binding_name=binding_name,
            member_names=class_member_names,
            constructed=constructed_class,
        )
    if isinstance(value, ast.AST):
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        try:
            namespace = object.__getattribute__(value, "__dict__")
        except AttributeError as error:
            raise _ContractError(
                "static scanner AST dependency has no exact state"
            ) from error
        if type(namespace) is not dict or any(
            type(name) is not str for name in namespace
        ):
            raise _ContractError(
                "static scanner AST dependency state is not exact"
            )
        return {
            "kind": "ast_node",
            "token": token,
            "module": type.__getattribute__(value_type, "__module__"),
            "qualname": type.__getattribute__(value_type, "__qualname__"),
            "state": [
                [
                    name,
                    _static_semantic_value(
                        namespace[name],
                        state,
                        depth + 1,
                        binding_name=f"{binding_name}.{name}",
                    ),
                ]
                for name in sorted(namespace)
            ],
        }
    if isinstance(value, Enum):
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        try:
            enum_name = object.__getattribute__(value, "_name_")
            enum_value = object.__getattribute__(value, "_value_")
        except AttributeError as error:
            raise _ContractError(
                "static scanner external enum member is not exact"
            ) from error
        if enum_name is not None and type(enum_name) is not str:
            raise _ContractError(
                "static scanner external enum name is not exact"
            )
        return {
            "kind": "external_enum_member",
            "token": token,
            "module": value_type_module,
            "qualname": value_type_qualname,
            "name": enum_name,
            "value": _static_semantic_value(
                enum_value,
                state,
                depth + 1,
                binding_name=f"{binding_name}._value_",
            ),
        }
    if external_instance:
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        try:
            namespace = object.__getattribute__(value, "__dict__")
        except AttributeError as error:
            raise _ContractError(
                "static scanner external instance has no exact state"
            ) from error
        if type(namespace) is not dict or any(
            type(name) is not str for name in namespace
        ):
            raise _ContractError(
                "static scanner external instance state is not exact"
            )
        return {
            "kind": "external_instance",
            "token": token,
            "module": value_type_module,
            "qualname": value_type_qualname,
            "integer_value": (
                int.__int__(value) if isinstance(value, int) else None
            ),
            "state": [
                [
                    name,
                    _static_semantic_value(
                        namespace[name],
                        state,
                        depth + 1,
                        binding_name=f"{binding_name}.{name}",
                    ),
                ]
                for name in sorted(namespace)
            ],
        }
    if external_instance_slots is not None:
        if (
            type(external_instance_slots) is not tuple
            or not external_instance_slots
            or external_instance_slots
            != tuple(sorted(external_instance_slots))
            or len(set(external_instance_slots))
            != len(external_instance_slots)
            or any(
                type(name) is not str or not name
                for name in external_instance_slots
            )
        ):
            raise _ContractError(
                "static scanner external instance slots are not exact"
            )
        namespace = type.__getattribute__(value_type, "__dict__")
        if type(namespace) is not MappingProxyType:
            raise _ContractError(
                "static scanner external instance type is not exact"
            )
        observed_slots = tuple(
            sorted(
                name
                for name, member in namespace.items()
                if type(member)
                in (MemberDescriptorType, WrapperDescriptorType)
            )
        )
        if observed_slots != external_instance_slots:
            raise _ContractError(
                "static scanner external instance slot audit is not inverse"
            )
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        slots = []
        for name in external_instance_slots:
            _static_semantic_attribute_step(state)
            owner, descriptor = _static_exact_class_member(
                value_type, name
            )
            if owner is not value_type:
                raise _ContractError(
                    "static scanner external instance slot owner is not "
                    "exact"
                )
            try:
                binding = object.__getattribute__(value, name)
            except (AttributeError, TypeError) as error:
                raise _ContractError(
                    "static scanner external instance slot is unavailable"
                ) from error
            slots.append(
                {
                    "name": name,
                    "descriptor": _static_semantic_class_member(
                        owner,
                        descriptor,
                        state,
                        depth + 1,
                        binding_name=f"{binding_name}.{name}.descriptor",
                    ),
                    "binding": _static_semantic_value(
                        binding,
                        state,
                        depth + 1,
                        binding_name=f"{binding_name}.{name}.binding",
                    ),
                }
            )
        if {slot["name"] for slot in slots} != set(
            external_instance_slots
        ):
            raise _ContractError(
                "static scanner external instance slots are not inverse"
            )
        return {
            "kind": "external_slotted_instance",
            "token": token,
            "module": value_type_module,
            "qualname": value_type_qualname,
            "slots": slots,
        }
    if opaque_external_instance:
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        return {
            "kind": "opaque_external_instance",
            "token": token,
            "module": value_type_module,
            "qualname": value_type_qualname,
        }
    if type(value) in (
        tuple,
        list,
        dict,
        set,
        frozenset,
        MappingProxyType,
        FunctionType,
    ) or type(value) is _FrozenJsonObject or (
        semantic_instance
    ):
        token, is_new = _static_semantic_register(value, state)
        if not is_new:
            return {"kind": "reference", "token": token}
        if type(value) is FunctionType:
            return _static_semantic_function(
                value,
                state,
                depth + 1,
                token=token,
                binding_name=binding_name,
            )
        if type(value) is _FrozenJsonObject:
            items = _static_scan_exact_frozen_items(
                value,
                "static scanner frozen dependency",
                _STATIC_SCANNER_COMMITMENT_NODE_LIMIT,
            )
            value = {key: item for key, item in items}
        if semantic_instance:
            try:
                namespace = object.__getattribute__(value, "__dict__")
            except AttributeError as error:
                raise _ContractError(
                    "static scanner project dependency has no exact state"
                ) from error
            if type(namespace) is not dict or any(
                type(name) is not str for name in namespace
            ):
                raise _ContractError(
                    "static scanner project dependency state is not exact"
                )
            return {
                "kind": "project_instance",
                "token": token,
                "module": value_type_module,
                "qualname": type.__getattribute__(
                    value_type, "__qualname__"
                ),
                "state": [
                    [
                        name,
                        _static_semantic_value(
                            namespace[name],
                            state,
                            depth + 1,
                            binding_name=f"{binding_name}.{name}",
                        ),
                    ]
                    for name in sorted(namespace)
                ],
            }
        if type(value) in (tuple, list):
            if len(value) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
                raise _ContractError(
                    "static scanner semantic sequence exceeds the bound"
                )
            return {
                "kind": type(value).__name__,
                "token": token,
                "items": [
                    _static_semantic_value(
                        item,
                        state,
                        depth + 1,
                        binding_name=f"{binding_name}.item",
                    )
                    for item in value
                ],
            }
        if type(value) in (set, frozenset):
            if len(value) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
                raise _ContractError(
                    "static scanner semantic set exceeds the bound"
                )
            ordered_values = sorted(
                value,
                key=lambda item: _static_commitment_bytes(
                    _static_semantic_set_sort_key(item, depth + 1)
                ),
            )
            items = [
                _static_semantic_value(
                    item,
                    state,
                    depth + 1,
                    binding_name=f"{binding_name}.item",
                )
                for item in ordered_values
            ]
            return {
                "kind": type(value).__name__,
                "token": token,
                "items": items,
            }
        if type(value) in (dict, MappingProxyType):
            mapping = (
                _static_exact_mappingproxy_mapping(value)
                if type(value) is MappingProxyType
                else value
            )
            if len(mapping) > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
                raise _ContractError(
                    "static scanner semantic mapping exceeds the bound"
                )
            return {
                "kind": "mapping",
                "token": token,
                "items": [
                    [
                        _static_semantic_value(
                            key,
                            state,
                            depth + 1,
                            binding_name=f"{binding_name}.key",
                        ),
                        _static_semantic_value(
                            item,
                            state,
                            depth + 1,
                            binding_name=f"{binding_name}.value",
                        ),
                    ]
                    for key, item in mapping.items()
                ],
            }
    if type(value) is type(_ENTRY_SYMBOL_PATTERN):
        pattern = value.pattern
        if type(pattern) not in (str, bytes) or not isinstance(
            value.flags, int
        ):
            raise _ContractError(
                "static scanner regular expression is not exact"
            )
        return {
            "kind": "regular_expression",
            "pattern": (
                pattern
                if type(pattern) is str
                else {"kind": "bytes", "hex": pattern.hex()}
            ),
            "flags": int.__int__(value.flags),
        }
    raise _ContractError(
        "static scanner dependency cannot be safely normalized: "
        f"{binding_name}"
    )


def _static_external_receiver_dependency_manifest(
    state: dict[str, object],
) -> dict[str, object]:
    rule_manifest = _static_external_receiver_rule_manifest()
    declared_sites = {
        (site[0], site[1], site[2], site[3])
        for site in _STATIC_SCANNER_EXTERNAL_RECEIVER_ACCESS_SITES
    }
    observed_seeds = set()
    for (project_module, project_qualname), function in sorted(
        state["project_functions"].items()
    ):
        global_accesses, _class_members = _static_code_binding_accesses(
            function.__code__, function.__globals__
        )
        for name, paths in global_accesses.items():
            dependency = function.__globals__.get(name)
            if dependency is Path:
                observed_seeds.add(
                    (
                        project_module,
                        project_qualname,
                        "pathlib",
                        "Path",
                    )
                )
            elif dependency is PurePosixPath:
                observed_seeds.add(
                    (
                        project_module,
                        project_qualname,
                        "pathlib",
                        "PurePosixPath",
                    )
                )
            elif dependency is PurePath:
                observed_seeds.add(
                    (
                        project_module,
                        project_qualname,
                        "pathlib",
                        "PurePath",
                    )
                )
            elif dependency is string and any(
                path and path[0] == "Formatter" for path in paths
            ):
                observed_seeds.add(
                    (
                        project_module,
                        project_qualname,
                        "string",
                        "Formatter",
                    )
                )
    seed_exclusions = _STATIC_SCANNER_EXTERNAL_RECEIVER_SEED_EXCLUSIONS
    if not seed_exclusions <= observed_seeds:
        raise _ContractError(
            "static scanner external receiver seed exclusion is unreferenced"
        )
    missing_seed_sites = observed_seeds - seed_exclusions - declared_sites
    if missing_seed_sites:
        first_missing = sorted(missing_seed_sites)[0]
        raise _ContractError(
            "static scanner external receiver semantic seed is missing from "
            "the access-site manifest: " + ".".join(first_missing)
        )
    audit_code_nodes = 0
    audit_instructions = 0
    live_bindings: dict[tuple[str, str, str], dict[str, object]] = {}
    receiver_members: dict[tuple[str, str], set[str]] = {}
    for receiver_module, receiver_qualname, member_name in (
        _STATIC_SCANNER_EXTERNAL_RECEIVER_BINDINGS
    ):
        receiver_members.setdefault(
            (receiver_module, receiver_qualname), set()
        ).add(member_name)
    for site in _STATIC_SCANNER_EXTERNAL_RECEIVER_ACCESS_SITES:
        (
            project_module,
            project_qualname,
            receiver_module,
            receiver_qualname,
            member_names,
            collision_counts,
        ) = site
        function = state["project_functions"].get(
            (project_module, project_qualname)
        )
        if type(function) is not FunctionType:
            raise _ContractError(
                "static scanner external receiver access site is outside "
                "the semantic roots"
            )
        receiver_class = _static_external_receiver_class(
            receiver_module, receiver_qualname
        )
        receiver_members.setdefault(
            (receiver_module, receiver_qualname), set()
        ).update(member_names)
        candidates, code_nodes, instructions = (
            _static_code_external_receiver_candidates(
                function.__code__, receiver_class
            )
        )
        audit_code_nodes += code_nodes
        audit_instructions += instructions
        if audit_code_nodes > _STATIC_SCANNER_COMMITMENT_NODE_LIMIT:
            raise _ContractError(
                "static scanner external receiver audit exceeds the node "
                "bound"
            )
        if audit_instructions > _STATIC_SCANNER_COMMITMENT_EDGE_LIMIT:
            raise _ContractError(
                "static scanner external receiver audit exceeds the edge "
                "bound"
            )
        for collision_name, collision_count in collision_counts:
            actual_count = candidates.get(collision_name, 0)
            if actual_count < collision_count:
                raise _ContractError(
                    "static scanner external receiver collision count is "
                    "not present"
                )
            remaining = actual_count - collision_count
            if remaining:
                candidates[collision_name] = remaining
            else:
                candidates.pop(collision_name)
        if set(candidates) != set(member_names) or any(
            count < 1 for count in candidates.values()
        ):
            raise _ContractError(
                "static scanner external receiver manifest is missing or "
                "contains an unreferenced binding"
            )
        for member_name in member_names:
            owner, member = _static_exact_class_member(
                receiver_class, member_name
            )
            owner_module = type.__getattribute__(owner, "__module__")
            owner_qualname = type.__getattribute__(owner, "__qualname__")
            binding_key = (owner_module, owner_qualname, member_name)
            existing = live_bindings.get(binding_key)
            if existing is None:
                live_bindings[binding_key] = {
                    "member": member,
                    "receivers": {
                        (receiver_module, receiver_qualname)
                    },
                }
            else:
                if existing["member"] is not member:
                    raise _ContractError(
                        "static scanner external receiver binding identity "
                        "is ambiguous"
                    )
                existing["receivers"].add(
                    (receiver_module, receiver_qualname)
                )
    bindings = []
    for (owner_module, owner_qualname, member_name), live in sorted(
        live_bindings.items()
    ):
        _static_semantic_attribute_step(state)
        bindings.append(
            {
                "receivers": [
                    list(item) for item in sorted(live["receivers"])
                ],
                "member": member_name,
                "owner_module": owner_module,
                "owner_qualname": owner_qualname,
                "binding": _static_semantic_value(
                    live["member"],
                    state,
                    1,
                    binding_name=(
                        "external_receiver."
                        f"{owner_module}.{owner_qualname}.{member_name}"
                    ),
                ),
            }
        )
    receiver_classes = []
    for (receiver_module, receiver_qualname), member_names in sorted(
        receiver_members.items()
    ):
        receiver_class = _static_external_receiver_class(
            receiver_module, receiver_qualname
        )
        receiver_classes.append(
            _static_semantic_class(
                receiver_class,
                state,
                1,
                token=(
                    f"external_class:{receiver_module}.{receiver_qualname}"
                ),
                binding_name=(
                    f"external_receiver_class."
                    f"{receiver_module}.{receiver_qualname}"
                ),
                member_names=tuple(sorted(member_names)),
                constructed=True,
            )
        )
    return {
        "rules": rule_manifest,
        "observed_seeds": [list(item) for item in sorted(observed_seeds)],
        "bindings": bindings,
        "receiver_classes": receiver_classes,
        "audit_code_nodes": audit_code_nodes,
        "audit_instructions": audit_instructions,
    }


def _static_scanner_dependency_manifest() -> dict[str, object]:
    state: dict[str, object] = {
        "steps": 0,
        "edges": 0,
        "attributes": 0,
        "memo": {},
        "project_functions": {},
    }
    entrypoints = {}
    for name in _STATIC_SCANNER_ENTRYPOINT_NAMES:
        value = globals().get(name)
        if type(value) is not FunctionType:
            raise _ContractError(
                "static scanner entrypoint is not an exact Python callable"
            )
        entrypoints[name] = _static_semantic_value(
            value,
            state,
            0,
            binding_name=name,
        )
    external_receiver_bindings = (
        _static_external_receiver_dependency_manifest(state)
    )
    return {
        "entrypoints": entrypoints,
        "external_receiver_bindings": external_receiver_bindings,
        "semantic_nodes": state["steps"],
        "semantic_edges": state["edges"],
        "semantic_attributes": state["attributes"],
    }


def _current_static_scanner_sha256() -> str:
    commitment = {
        "rules": _static_scanner_rule_manifest(),
        "dependencies": _static_scanner_dependency_manifest(),
    }
    try:
        commitment_bytes = _static_commitment_bytes(commitment)
    except (TypeError, ValueError, RecursionError) as error:
        raise _ContractError(
            "static scanner semantic commitment is not canonical"
        ) from error
    if len(commitment_bytes) > (
        _STATIC_SCANNER_COMMITMENT_MATERIAL_BYTES_LIMIT
    ):
        raise _ContractError(
            "static scanner semantic commitment exceeds the byte bound"
        )
    return hashlib.sha256(commitment_bytes).hexdigest()


_STATIC_SCANNER_SHA256 = _current_static_scanner_sha256()


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

    def revalidate(self) -> None:
        revalidate_runtime_snapshot(self)


_RUNTIME_RESOURCE_ROW_FIELDS = frozenset(
    {
        "logical_destination",
        "resolved_path",
        "link_identity",
        "file_type",
        "size",
        "mode",
        "sha256",
        "distribution",
        "version",
        "purpose",
    }
)
_RUNTIME_FILE_PURPOSES = frozenset(
    {
        "interpreter",
        "dynamic_loader",
        "dynamic_library",
        "declared_native_library",
        "imported_standard_library",
        "declared_distribution_file",
        "declared_backend_resource",
    }
)
_RUNTIME_BACKEND_CAPABILITIES = frozenset({"single_cpu_core"})
_RUNTIME_FIXED_STDLIB_MODULES = (
    "ctypes",
    "encodings",
    "json",
    "os",
    "resource",
)
_RUNTIME_COPY_BUFFER_BYTES = 65_536
_RUNTIME_RETAINED_STATE_TOKEN = object()


def _runtime_close_fd(descriptor):
    try:
        os.close(descriptor)
    except OSError:
        pass


class _RetainedRuntimeSnapshotState:
    __slots__ = (
        "token",
        "owner_ref",
        "root_fd",
        "root_identity",
        "files",
        "snapshot_material",
        "finalizer",
    )

    def __init__(
        self,
        *,
        owner,
        root_fd,
        root_identity,
        files,
        snapshot_material,
        authorization=None,
    ):
        if authorization is not _RUNTIME_RETAINED_STATE_TOKEN:
            raise _ContractError(
                "retained runtime snapshot state construction is not authorized"
            )
        object.__setattr__(self, "token", _RUNTIME_RETAINED_STATE_TOKEN)
        object.__setattr__(self, "owner_ref", weakref.ref(owner))
        object.__setattr__(self, "root_fd", root_fd)
        object.__setattr__(self, "root_identity", root_identity)
        object.__setattr__(self, "files", files)
        object.__setattr__(self, "snapshot_material", snapshot_material)
        object.__setattr__(
            self,
            "finalizer",
            weakref.finalize(owner, _runtime_close_fd, root_fd),
        )

    def __setattr__(self, name, value):
        raise AttributeError("retained runtime snapshot state is immutable")


def _runtime_event(event_recorder, event_name, details):
    if not callable(event_recorder):
        raise _ContractError("event_recorder must be callable")
    event_recorder(event_name, _snapshot_json(details, "event details"))


def _runtime_is_beneath(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _runtime_forbidden_roots():
    project_root = Path(__file__).resolve().parents[2]
    roots = {
        project_root,
        project_root.parent,
        project_root.parent.parent,
    }
    roots.add((Path.home() / ".config").resolve())
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        roots.add(Path(xdg_config).expanduser().resolve())
    return tuple(sorted(roots, key=str))


def _runtime_link_identity(path):
    supplied = Path(path)
    if not supplied.is_absolute():
        supplied = supplied.absolute()
    current = Path(supplied.anchor)
    links = []
    pending = list(supplied.parts[1:])
    seen_links = set()
    steps = 0
    while pending:
        steps += 1
        if steps > 256:
            raise _ContractError("runtime resource symlink traversal exceeds the bound")
        component = pending.pop(0)
        current /= component
        try:
            metadata = os.lstat(current)
        except OSError as error:
            raise _ContractError("runtime resource cannot be inspected") from error
        if stat.S_ISLNK(metadata.st_mode):
            link_key = (metadata.st_dev, metadata.st_ino)
            if link_key in seen_links:
                raise _ContractError("runtime resource symlink traversal contains a cycle")
            seen_links.add(link_key)
            try:
                authored_target = os.readlink(current)
                target = Path(authored_target)
                if not target.is_absolute():
                    target = current.parent / target
                target = Path(os.path.abspath(target))
                target_metadata = os.stat(target)
            except (OSError, RuntimeError) as error:
                raise _ContractError(
                    "runtime resource symlink target cannot be resolved"
                ) from error
            links.append(
                {
                    "path": str(current),
                    "device": metadata.st_dev,
                    "inode": metadata.st_ino,
                    "link_target": authored_target,
                    "target_path": str(target),
                    "target_device": target_metadata.st_dev,
                    "target_inode": target_metadata.st_ino,
                }
            )
            pending = list(target.parts[1:]) + pending
            current = Path(target.anchor)
    try:
        resolved = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise _ContractError("runtime resource cannot be resolved") from error
    return resolved, tuple(links)


def _runtime_hash_regular_file(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(_RUNTIME_COPY_BUFFER_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as error:
        raise _ContractError("runtime resource cannot be hashed") from error
    return digest.hexdigest()


def _runtime_file_row(
    path,
    *,
    logical_destination,
    purpose,
    distribution=None,
    version=None,
):
    if purpose not in _RUNTIME_FILE_PURPOSES:
        raise _ContractError("runtime resource has an unknown file purpose")
    resolved, link_identity = _runtime_link_identity(path)
    if any(
        _runtime_is_beneath(resolved, root)
        for root in _runtime_forbidden_roots()
    ):
        raise _ContractError("runtime resource is under a forbidden project or configuration root")
    try:
        metadata = resolved.stat()
    except OSError as error:
        raise _ContractError("runtime resource cannot be stated") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise _ContractError("runtime resource must be an exact regular file")
    destination = PurePosixPath(logical_destination)
    if (
        not destination.is_absolute()
        or not destination.parts
        or any(part in {"", ".", ".."} for part in destination.parts)
    ):
        raise _ContractError("runtime logical destination must be absolute and closed")
    return {
        "logical_destination": str(destination),
        "resolved_path": str(resolved),
        "link_identity": link_identity,
        "file_type": "regular",
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "sha256": _runtime_hash_regular_file(resolved),
        "distribution": distribution,
        "version": version,
        "purpose": purpose,
    }


def _runtime_capability_row(name):
    identity = {
        "kind": "declared_backend_capability",
        "name": name,
        "version": 1,
    }
    return {
        "logical_destination": f"/runtime/capabilities/{name}",
        "resolved_path": None,
        "link_identity": (),
        "file_type": "capability",
        "size": 0,
        "mode": 0,
        "sha256": _canonical_sha256(identity),
        "distribution": None,
        "version": None,
        "purpose": "declared_backend_capability",
    }


def _default_runtime_command_probe(argv):
    try:
        result = subprocess.run(
            argv,
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, ValueError) as error:
        raise _ContractError("runtime discovery command failed") from error
    if result.returncode != 0:
        raise _ContractError("runtime discovery command returned nonzero")
    return result.stdout


def _default_runtime_file_probe(operation, value):
    if operation == "resolve_interpreter":
        if value != "python3":
            raise _ContractError("runtime interpreter is not the declared python3")
        return Path(sys.executable)
    if operation == "distribution":
        try:
            distribution = _importlib_metadata.distribution(value)
        except _importlib_metadata.PackageNotFoundError as error:
            raise _ContractError("declared runtime distribution is unavailable") from error
        declared_files = distribution.files
        if declared_files is None:
            raise _ContractError("distribution file metadata is unavailable")
        files = []
        for item in declared_files:
            relative = Path(str(item))
            if relative.is_absolute() or any(
                part in {"", ".", ".."} for part in relative.parts
            ):
                raise _ContractError("distribution contains an unsafe file path")
            located = Path(distribution.locate_file(item))
            try:
                metadata = located.stat()
            except OSError as error:
                raise _ContractError(
                    "distribution file is missing or dangling"
                ) from error
            if not stat.S_ISREG(metadata.st_mode):
                raise _ContractError("distribution entry is not a regular file")
            files.append((PurePosixPath(*relative.parts).as_posix(), located))
        return {
            "name": distribution.metadata.get("Name", value),
            "version": distribution.version,
            "files": tuple(files),
        }
    if operation == "native_library":
        candidate = Path(value)
        if not candidate.is_absolute():
            raise _ContractError("declared native library must be an absolute path")
        return candidate
    if operation == "backend_resource":
        candidate = Path(value)
        if not candidate.is_absolute() or any(
            part in {"", ".", ".."} for part in candidate.parts
        ):
            raise _ContractError("backend resource must be an exact absolute file path")
        return candidate
    if operation == "imported_stdlib_files":
        stdlib_roots = tuple(sorted({
            Path(sysconfig.get_path(name)).resolve()
            for name in ("stdlib", "platstdlib")
            if sysconfig.get_path(name)
        }, key=str))
        probe_source = (
            "import importlib,json,sys\n"
            "if not sys.flags.dont_write_bytecode: raise RuntimeError('bytecode enabled')\n"
            f"names={_RUNTIME_FIXED_STDLIB_MODULES!r}\n"
            "[importlib.import_module(name) for name in names]\n"
            "paths=[]\n"
            "for module in tuple(sys.modules.values()):\n"
            " path=getattr(module,'__file__',None)\n"
            " if isinstance(path,str): paths.append(path)\n"
            "print(json.dumps(sorted(set(paths))))\n"
        )
        try:
            result = subprocess.run(
                (sys.executable, "-I", "-S", "-B", "-c", probe_source),
                check=False,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, ValueError) as error:
            raise _ContractError("stdlib import closure probe failed") from error
        if result.returncode != 0:
            raise _ContractError("stdlib import closure probe returned nonzero")
        try:
            discovered = json.loads(result.stdout)
        except (TypeError, ValueError) as error:
            raise _ContractError("stdlib import closure probe returned unsafe data") from error
        if type(discovered) is not list or any(
            type(path) is not str for path in discovered
        ):
            raise _ContractError("stdlib import closure probe returned unsafe paths")
        files = {}
        for path in discovered:
            try:
                resolved = Path(path).resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise _ContractError("stdlib module path cannot be resolved") from error
            if any(
                part in {"site-packages", "dist-packages"}
                for part in resolved.parts
            ):
                continue
            relatives = {
                PurePosixPath(*resolved.relative_to(root).parts).as_posix()
                for root in stdlib_roots
                if _runtime_is_beneath(resolved, root)
            }
            if len(relatives) != 1:
                raise _ContractError(
                    "stdlib module has no unique standard-library root"
                )
            relative = relatives.pop()
            existing = files.get(relative)
            if existing is not None and existing != resolved:
                raise _ContractError("stdlib relative path is ambiguous")
            files[relative] = resolved
        return tuple(sorted(files.items()))
    raise _ContractError("unknown runtime file probe operation")


def _runtime_ldd_paths(output):
    if type(output) is not str:
        raise _ContractError("ldd output must be exact text")
    if not output:
        raise _ContractError("ldd output must not be empty")
    entries = []
    shared_row = re.compile(
        r"^(?P<name>[^\s=]+)\s*=>\s*(?P<path>/\S+)\s+"
        r"\(0x[0-9A-Fa-f]+\)$"
    )
    direct_row = re.compile(
        r"^(?P<path>/\S+)\s+\(0x[0-9A-Fa-f]+\)$"
    )
    pseudo_row = re.compile(
        r"^(?:linux-vdso(?:32|64)?|linux-gate)\.so(?:\.[0-9]+)*\s+"
        r"(?:=>\s*)?\(0x[0-9A-Fa-f]+\)$"
    )
    loader_name = re.compile(
        r"^(?:ld-linux(?:-[A-Za-z0-9_.+-]+)?\.so(?:\.[0-9]+)*|"
        r"ld-musl-[A-Za-z0-9_.+-]+\.so(?:\.[0-9]+)*|"
        r"ld\.so(?:\.[0-9]+)*|ld64\.so(?:\.[0-9]+)*)$"
    )
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            raise _ContractError("ldd output contains an empty row")
        if re.search(r"=>\s*not found(?:\s|$)", line):
            raise _ContractError("ldd reported an unavailable library")
        if pseudo_row.fullmatch(line):
            continue
        shared = shared_row.fullmatch(line)
        direct = direct_row.fullmatch(line)
        if shared is not None:
            soname = shared.group("name")
            path = Path(shared.group("path"))
            soname_is_loader = loader_name.fullmatch(soname) is not None
            path_is_loader = loader_name.fullmatch(path.name) is not None
        elif direct is not None:
            path = Path(direct.group("path"))
            soname = path.name
            if loader_name.fullmatch(soname) is None:
                raise _ContractError("ldd absolute row is not a known loader")
            soname_is_loader = path_is_loader = True
        else:
            raise _ContractError("ldd output contains an unknown row")
        entries.append(
            (soname, path, soname_is_loader, path_is_loader)
        )
    return tuple(entries)


def discover_runtime_resources(
    requirements, *, command_probe=None, file_probe=None
):
    """Discover and hash the exact declared runtime resource closure."""

    if type(requirements) is not _adapters.RuntimeRequirements:
        raise _ContractError("requirements must be exact RuntimeRequirements")
    default_probes = command_probe is None and file_probe is None
    command = _default_runtime_command_probe if command_probe is None else command_probe
    files = _default_runtime_file_probe if file_probe is None else file_probe
    interpreter_supplied = files("resolve_interpreter", requirements.interpreter)
    interpreter_resolved, _links = _runtime_link_identity(interpreter_supplied)
    rows = [
        _runtime_file_row(
            interpreter_supplied,
            logical_destination="/runtime/bin/python3",
            purpose="interpreter",
        )
    ]
    ldd_output = command(("ldd", str(interpreter_resolved)))
    ldd_identities = {}
    parsed_ldd = sorted(
        _runtime_ldd_paths(ldd_output),
        key=lambda item: (str(item[1]), item[0], item[2], item[3]),
    )
    for soname, library, soname_loader, path_loader in parsed_ldd:
        row = _runtime_file_row(
            library,
            logical_destination="/runtime/native/pending",
            purpose="dynamic_library",
        )
        try:
            metadata = os.stat(row["resolved_path"], follow_symlinks=False)
        except OSError as error:
            raise _ContractError("ldd file identity cannot be stated") from error
        identity = (metadata.st_dev, metadata.st_ino)
        candidates = ldd_identities.setdefault(identity, [])
        if candidates:
            previous = candidates[0][1]
            if any(
                previous[field] != row[field]
                for field in ("size", "mode", "sha256")
            ):
                raise _ContractError("ldd file identity is ambiguous")
        candidates.append(
            (
                (
                    row["resolved_path"],
                    soname,
                    soname_loader,
                    path_loader,
                ),
                row,
                soname_loader or path_loader,
            )
        )
    grouped_ldd = []
    for identity, candidates in ldd_identities.items():
        representative = min(candidates, key=lambda item: item[0])
        links_by_identity = {}
        link_fields = (
            "path",
            "device",
            "inode",
            "link_target",
            "target_path",
            "target_device",
            "target_inode",
        )
        for _candidate_key, candidate_row, _loader_hint in candidates:
            if type(candidate_row) is not dict:
                raise _ContractError("ldd candidate row is not exact")
            candidate_links = dict.__getitem__(
                candidate_row, "link_identity"
            )
            if type(candidate_links) is not tuple:
                raise _ContractError("ldd link identity is not exact")
            for link in candidate_links:
                if type(link) is not dict or set(link) != set(link_fields):
                    raise _ContractError("ldd link identity is not exact")
                link_key = tuple(
                    dict.__getitem__(link, field) for field in link_fields
                )
                links_by_identity.setdefault(link_key, link)
        dict.__setitem__(
            representative[1],
            "link_identity",
            tuple(
                links_by_identity[key]
                for key in sorted(links_by_identity)
            ),
        )
        grouped_ldd.append(
            (representative[0], identity, representative[1], any(
                candidate[2] for candidate in candidates
            ))
        )
    grouped_ldd.sort(key=lambda item: (item[0], item[1]))
    if sum(item[3] for item in grouped_ldd) != 1:
        raise _ContractError("ldd output must resolve to exactly one loader")
    for index, (_key, _identity, row, is_loader) in enumerate(grouped_ldd):
        row["purpose"] = (
            "dynamic_loader" if is_loader else "dynamic_library"
        )
        row["logical_destination"] = (
            f"/runtime/native/ldd-{index}-{Path(row['resolved_path']).name}"
        )
        rows.append(row)
    stdlib_names = set()
    stdlib_extensions = []
    for item in files("imported_stdlib_files", requirements.packages):
        if type(item) is not tuple or len(item) != 2:
            raise _ContractError("stdlib file entry is not exact")
        relative_text, path = item
        if (
            type(relative_text) is not str
            or not relative_text
            or relative_text.startswith("/")
            or "//" in relative_text
        ):
            raise _ContractError("stdlib file path is unsafe")
        relative = PurePosixPath(relative_text)
        if (
            relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.as_posix() != relative_text
            or relative_text in stdlib_names
        ):
            raise _ContractError("stdlib file path is unsafe or duplicated")
        stdlib_names.add(relative_text)
        if ".so" in Path(relative_text).name:
            stdlib_extensions.append(Path(path))
        rows.append(
            _runtime_file_row(
                path,
                logical_destination=f"/runtime/stdlib/{relative_text}",
                purpose="imported_standard_library",
            )
        )
    if default_probes:
        known_identities = {
            (os.stat(row["resolved_path"]).st_dev,
             os.stat(row["resolved_path"]).st_ino)
            for row in rows
            if row["file_type"] == "regular"
        }
        extension_dependencies = []
        for extension in sorted(stdlib_extensions, key=str):
            extension_output = command(
                ("ldd", str(extension.resolve(strict=True)))
            )
            if extension_output.strip() == "statically linked":
                parsed = ()
            else:
                parsed = _runtime_ldd_paths(extension_output)
            if parsed and sum(
                soname_loader or path_loader
                for _soname, _path, soname_loader, path_loader in parsed
            ) != 1:
                raise _ContractError(
                    "stdlib extension ldd has an ambiguous loader"
                )
            for soname, library, soname_loader, path_loader in parsed:
                dependency = _runtime_file_row(
                    library,
                    logical_destination="/runtime/native/pending",
                    purpose="dynamic_library",
                )
                metadata = os.stat(dependency["resolved_path"])
                identity = (metadata.st_dev, metadata.st_ino)
                if identity in known_identities:
                    continue
                known_identities.add(identity)
                extension_dependencies.append(
                    (
                        dependency["resolved_path"],
                        soname,
                        soname_loader or path_loader,
                        dependency,
                    )
                )
        for index, (_path, _soname, is_loader, dependency) in enumerate(
            sorted(extension_dependencies, key=lambda item: item[:3])
        ):
            if is_loader:
                raise _ContractError(
                    "stdlib extension introduced a second loader"
                )
            dependency["logical_destination"] = (
                "/runtime/native/stdlib-"
                + str(index)
                + "-"
                + Path(dependency["resolved_path"]).name
            )
            rows.append(dependency)
    for package in requirements.packages:
        distribution = files("distribution", package)
        if type(distribution) is not dict or set(distribution) != {"name", "version", "files"}:
            raise _ContractError("distribution probe returned an unsafe record")
        if distribution["name"].casefold().replace("_", "-") != package.casefold().replace("_", "-"):
            raise _ContractError("distribution probe returned an undeclared package")
        relative_names = set()
        for item in distribution["files"]:
            if type(item) is not tuple or len(item) != 2:
                raise _ContractError("distribution file entry is not exact")
            relative_text, path = item
            if (
                type(relative_text) is not str
                or not relative_text
                or relative_text.startswith("/")
                or "//" in relative_text
            ):
                raise _ContractError("distribution file path is unsafe")
            relative = PurePosixPath(relative_text)
            if (
                relative.is_absolute()
                or any(part in {"", ".", ".."} for part in relative.parts)
                or relative.as_posix() != relative_text
                or relative_text in relative_names
            ):
                raise _ContractError("distribution file path is unsafe or duplicated")
            relative_names.add(relative_text)
            rows.append(
                _runtime_file_row(
                    path,
                    logical_destination=(
                        f"/runtime/distributions/{package}/{relative_text}"
                    ),
                    purpose="declared_distribution_file",
                    distribution=distribution["name"],
                    version=distribution["version"],
                )
            )
    for index, library in enumerate(requirements.native_libraries):
        path = files("native_library", library)
        rows.append(
            _runtime_file_row(
                path,
                logical_destination=f"/runtime/native/declared-{index}-{Path(path).name}",
                purpose="declared_native_library",
            )
        )
    for index, resource in enumerate(requirements.backend_resources):
        if resource in _RUNTIME_BACKEND_CAPABILITIES:
            rows.append(_runtime_capability_row(resource))
            continue
        candidate = Path(resource)
        if not candidate.is_absolute() or any(
            part in {"", ".", ".."} for part in candidate.parts
        ):
            raise _ContractError("unknown symbolic backend resource")
        path = files("backend_resource", resource)
        rows.append(
            _runtime_file_row(
                path,
                logical_destination=f"/runtime/backend/{index}-{Path(path).name}",
                purpose="declared_backend_resource",
            )
        )
    unique_paths = set()
    destinations = set()
    for row in rows:
        if row["logical_destination"] in destinations:
            raise _ContractError("runtime resource closure contains a duplicate")
        destinations.add(row["logical_destination"])
        if row["file_type"] == "regular":
            if row["resolved_path"] in unique_paths:
                raise _ContractError("runtime source file is mapped more than once")
            unique_paths.add(row["resolved_path"])
    for destination in destinations:
        prefix = destination.rstrip("/") + "/"
        if any(other.startswith(prefix) for other in destinations):
            raise _ContractError("runtime destinations contain a parent-file conflict")
    ordered = tuple(sorted(rows, key=lambda row: row["logical_destination"]))
    body = {
        "schema_version": "runtime_resource_manifest_v1",
        "resources": ordered,
    }
    return RuntimeResourceManifest(
        body["schema_version"], ordered, _canonical_sha256(body)
    )


def _validated_runtime_manifest(manifest):
    if type(manifest) is not RuntimeResourceManifest:
        raise _ContractError("runtime discovery returned an unsafe manifest")
    body = {
        "schema_version": manifest.schema_version,
        "resources": manifest.resources,
    }
    if manifest.manifest_sha256 != _canonical_sha256(body):
        raise _ContractError("runtime resource manifest hash changed")
    destinations = set()
    paths = set()
    for row in manifest.resources:
        if set(row) != _RUNTIME_RESOURCE_ROW_FIELDS:
            raise _ContractError("runtime resource manifest row is not exact")
        _require_sha256(row["sha256"], "runtime resource sha256")
        destination_text = row["logical_destination"]
        if (
            type(destination_text) is not str
            or not destination_text.startswith("/")
            or "//" in destination_text
            or PurePosixPath(destination_text).as_posix()
            != destination_text
            or any(
                part in {"", ".", ".."}
                for part in PurePosixPath(destination_text).parts[1:]
            )
        ):
            raise _ContractError("runtime resource destination is unsafe")
        if destination_text in destinations:
            raise _ContractError("runtime resource destination is duplicated")
        destinations.add(destination_text)
        if row["file_type"] == "capability":
            prefix = "/runtime/capabilities/"
            name = (
                destination_text[len(prefix) :]
                if destination_text.startswith(prefix)
                else ""
            )
            if (
                name not in _RUNTIME_BACKEND_CAPABILITIES
                or row != _runtime_capability_row(name)
            ):
                raise _ContractError("runtime capability row is malformed")
            continue
        if row["file_type"] != "regular" or row["purpose"] not in _RUNTIME_FILE_PURPOSES:
            raise _ContractError("runtime resource row has an unknown type")
        if row["resolved_path"] in paths:
            raise _ContractError("runtime resource file is duplicated")
        if (
            type(row["resolved_path"]) is not str
            or not Path(row["resolved_path"]).is_absolute()
            or type(row["size"]) is not int
            or row["size"] < 0
            or type(row["mode"]) is not int
            or not 0 <= row["mode"] <= 0o7777
            or type(row["link_identity"]) is not tuple
            or (
                row["purpose"] == "declared_distribution_file"
                and (
                    type(row["distribution"]) is not str
                    or not row["distribution"]
                    or type(row["version"]) is not str
                    or not row["version"]
                )
            )
            or (
                row["purpose"] != "declared_distribution_file"
                and (
                    row["distribution"] is not None
                    or row["version"] is not None
                )
            )
        ):
            raise _ContractError("runtime regular-file row is malformed")
        paths.add(row["resolved_path"])
    for destination in destinations:
        prefix = destination.rstrip("/") + "/"
        if any(other.startswith(prefix) for other in destinations):
            raise _ContractError(
                "runtime resource destinations contain a parent-file conflict"
            )
    return manifest


def _runtime_source_descriptor(row):
    path = Path(row["resolved_path"])
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise _ContractError("runtime source path is unsafe")
    directory_fd = descriptor = None
    try:
        directory_fd = _runtime_open_directory_path(path.parent)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        if directory_fd is not None:
            os.close(directory_fd)
        raise _ContractError("runtime source cannot be opened safely") from error
    os.close(directory_fd)
    return descriptor


def _runtime_open_directory_path(path):
    directory = Path(path)
    if not directory.is_absolute():
        raise _ContractError("runtime directory path must be absolute")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = None
    try:
        descriptor = os.open(directory.anchor, flags)
        for component in directory.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise _ContractError(
            "runtime directory path contains an unsafe component"
        ) from error


def _runtime_revalidate_link_identity(row):
    identities = row["link_identity"]
    if type(identities) is not tuple:
        raise _ContractError("runtime link identity must be an exact tuple")
    expected_keys = {
        "path",
        "device",
        "inode",
        "link_target",
        "target_path",
        "target_device",
        "target_inode",
    }
    for identity in identities:
        if set(identity) != expected_keys:
            raise _ContractError("runtime link identity record is not exact")
        try:
            link_metadata = os.lstat(identity["path"])
            link_target = os.readlink(identity["path"])
            target_metadata = os.stat(identity["target_path"])
        except OSError as error:
            raise _ContractError("runtime link identity is unavailable") from error
        if (
            not stat.S_ISLNK(link_metadata.st_mode)
            or link_metadata.st_dev != identity["device"]
            or link_metadata.st_ino != identity["inode"]
            or link_target != identity["link_target"]
            or target_metadata.st_dev != identity["target_device"]
            or target_metadata.st_ino != identity["target_inode"]
        ):
            raise _ContractError("runtime link identity changed")


def _runtime_stat_identity(metadata):
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _runtime_validate_source_descriptor(descriptor, row):
    try:
        metadata = os.fstat(descriptor)
    except OSError as error:
        raise _ContractError("runtime source cannot be stated") from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size != row["size"]
        or stat.S_IMODE(metadata.st_mode) != row["mode"]
    ):
        raise _ContractError("runtime source identity changed before copying")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(descriptor, _RUNTIME_COPY_BUFFER_BYTES)
        if type(chunk) is not bytes:
            raise _ContractError("runtime source returned unsafe bytes")
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
        if total > row["size"]:
            raise _ContractError("runtime source grew during validation")
    if total != row["size"] or digest.hexdigest() != row["sha256"]:
        raise _ContractError("runtime source bytes changed before copying")
    os.lseek(descriptor, 0, os.SEEK_SET)
    return metadata


def _runtime_copy_and_verify(
    source_fd, root_fd, basename, row, *, on_copy_complete
):
    destination_fd = None
    try:
        destination_fd = os.open(
            basename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=root_fd,
        )
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(source_fd, _RUNTIME_COPY_BUFFER_BYTES)
            if type(chunk) is not bytes:
                raise _ContractError("runtime source returned unsafe bytes")
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            offset = 0
            while offset < len(chunk):
                written = os.write(destination_fd, chunk[offset:])
                if written <= 0:
                    raise _ContractError("runtime snapshot write was short")
                offset += written
        if total != row["size"] or digest.hexdigest() != row["sha256"]:
            raise _ContractError("runtime source changed while copying")
        os.fsync(destination_fd)
        after_copy_source = os.fstat(source_fd)
        required_mode = 0o555 if row["mode"] & 0o111 else 0o444
        os.fchmod(destination_fd, required_mode)
        os.fsync(destination_fd)
    except OSError as error:
        raise _ContractError("runtime snapshot copy failed") from error
    finally:
        if destination_fd is not None:
            os.close(destination_fd)
    on_copy_complete()
    verification_fd = None
    try:
        verification_fd = os.open(
            basename,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        destination_metadata = os.fstat(verification_fd)
        if (
            not stat.S_ISREG(destination_metadata.st_mode)
            or destination_metadata.st_nlink != 1
            or destination_metadata.st_size != row["size"]
            or stat.S_IMODE(destination_metadata.st_mode) != required_mode
        ):
            raise _ContractError("runtime snapshot file identity is unsafe")
        os.lseek(source_fd, 0, os.SEEK_SET)
        os.lseek(verification_fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        total = 0
        while True:
            source_chunk = os.read(source_fd, _RUNTIME_COPY_BUFFER_BYTES)
            snapshot_chunk = os.read(verification_fd, _RUNTIME_COPY_BUFFER_BYTES)
            if source_chunk != snapshot_chunk:
                raise _ContractError("runtime snapshot byte comparison failed")
            if not source_chunk:
                break
            digest.update(snapshot_chunk)
            total += len(snapshot_chunk)
        if total != row["size"] or digest.hexdigest() != row["sha256"]:
            raise _ContractError("runtime snapshot hash comparison failed")
        after_compare_source = os.fstat(source_fd)
    except OSError as error:
        raise _ContractError("runtime snapshot cannot be reopened safely") from error
    finally:
        if verification_fd is not None:
            os.close(verification_fd)
    return (
        after_copy_source,
        after_compare_source,
        destination_metadata,
        required_mode,
    )


def _runtime_create_private_directory(parent_fd, basename):
    if (
        type(basename) is not str
        or basename in {"", ".", ".."}
        or "/" in basename
    ):
        raise _ContractError("private directory basename is unsafe")
    path_only_flag = getattr(os, "O_PATH", 0o10000000)
    os.mkdir(basename, 0o700, dir_fd=parent_fd)
    path_fd = directory_fd = None
    try:
        path_fd = os.open(
            basename,
            path_only_flag | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        created = os.fstat(path_fd)
        if not stat.S_ISDIR(created.st_mode):
            raise _ContractError("private directory creation changed type")
        os.chmod(f"/proc/self/fd/{path_fd}", 0o700)
        directory_fd = os.open(
            ".",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=path_fd,
        )
        opened = os.fstat(directory_fd)
        if (
            opened.st_dev != created.st_dev
            or opened.st_ino != created.st_ino
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            raise _ContractError("private directory identity or mode changed")
        return directory_fd
    except OSError as error:
        if directory_fd is not None:
            os.close(directory_fd)
        raise _ContractError("private directory cannot be secured") from error
    finally:
        if path_fd is not None:
            os.close(path_fd)


def build_runtime_snapshot(requirements, *, run_directory, event_recorder):
    """Build an exclusive immutable runtime snapshot and retain its dirfd."""

    manifest = _validated_runtime_manifest(
        discover_runtime_resources(requirements)
    )
    _runtime_event(
        event_recorder,
        "runtime_resources_discovered",
        {"manifest_sha256": manifest.manifest_sha256},
    )
    run_path = Path(run_directory)
    if not run_path.is_absolute():
        run_path = run_path.absolute()
    snapshot_path = run_path / "runtime-snapshot"
    parent_fd = run_fd = root_fd = state = None
    success = False
    try:
        if run_path.name in {"", ".", ".."}:
            raise _ContractError("run directory path is unsafe")
        parent_fd = _runtime_open_directory_path(run_path.parent)
        run_fd = _runtime_create_private_directory(parent_fd, run_path.name)
        root_fd = _runtime_create_private_directory(
            run_fd, "runtime-snapshot"
        )
        copied = []
        for index, row in enumerate(manifest.resources):
            if row["file_type"] == "capability":
                continue
            _runtime_revalidate_link_identity(row)
            source_fd = _runtime_source_descriptor(row)
            try:
                before = _runtime_validate_source_descriptor(source_fd, row)
                _runtime_event(
                    event_recorder,
                    "runtime_source_validated",
                    {"logical_destination": row["logical_destination"]},
                )
                basename = f"{index:04d}-{Path(row['resolved_path']).name}"
                (
                    after_copy,
                    after_compare,
                    destination,
                    required_mode,
                ) = _runtime_copy_and_verify(
                    source_fd,
                    root_fd,
                    basename,
                    row,
                    on_copy_complete=lambda: _runtime_event(
                        event_recorder,
                        "runtime_resource_copied",
                        {
                            "logical_destination": row[
                                "logical_destination"
                            ]
                        },
                    ),
                )
                if (
                    _runtime_stat_identity(before)
                    != _runtime_stat_identity(after_copy)
                    or _runtime_stat_identity(before)
                    != _runtime_stat_identity(after_compare)
                ):
                    raise _ContractError("runtime source changed during copying")
                copied.append(
                    {
                        "basename": basename,
                        "logical_destination": row["logical_destination"],
                        "device": destination.st_dev,
                        "inode": destination.st_ino,
                        "link_count": destination.st_nlink,
                        "size": destination.st_size,
                        "mode": required_mode,
                        "sha256": row["sha256"],
                    }
                )
                _runtime_event(
                    event_recorder,
                    "runtime_resource_byte_compared",
                    {"logical_destination": row["logical_destination"]},
                )
            finally:
                os.close(source_fd)
        root_metadata = os.fstat(root_fd)
        root_identity = {
            "logical_path": "/runtime",
            "device": root_metadata.st_dev,
            "inode": root_metadata.st_ino,
            "mode": 0o500,
        }
        snapshot_material = {
            "schema_version": "runtime_snapshot_v1",
            "manifest_sha256": manifest.manifest_sha256,
            "directory_identities": (root_identity,),
            "files": tuple(copied),
        }
        snapshot_sha256 = _canonical_sha256(snapshot_material)
        _runtime_event(
            event_recorder,
            "runtime_manifest_hashed",
            {"manifest_sha256": manifest.manifest_sha256},
        )
        os.fsync(root_fd)
        os.fchmod(root_fd, 0o500)
        os.fsync(root_fd)
        os.fchmod(run_fd, 0o500)
        os.fsync(run_fd)
        frozen_root = os.fstat(root_fd)
        if (
            frozen_root.st_dev != root_identity["device"]
            or frozen_root.st_ino != root_identity["inode"]
            or stat.S_IMODE(frozen_root.st_mode) != root_identity["mode"]
        ):
            raise _ContractError("runtime snapshot freeze identity changed")
        snapshot = RuntimeSnapshot(
            "runtime_snapshot_v1",
            manifest,
            str(snapshot_path),
            (root_identity,),
            snapshot_sha256,
        )
        state = _RetainedRuntimeSnapshotState(
            owner=snapshot,
            root_fd=root_fd,
            root_identity=_snapshot_json(root_identity, "root identity"),
            files=tuple(
                _snapshot_json(item, "runtime snapshot file")
                for item in copied
            ),
            snapshot_material=_snapshot_json(
                snapshot_material, "runtime snapshot material"
            ),
            authorization=_RUNTIME_RETAINED_STATE_TOKEN,
        )
        root_fd = None
        object.__setattr__(snapshot, "_retained_runtime_state", state)
        _runtime_event(
            event_recorder,
            "runtime_snapshot_frozen",
            {"snapshot_sha256": snapshot.snapshot_sha256},
        )
        _runtime_audit_snapshot_fd(
            object.__getattribute__(state, "root_fd"),
            object.__getattribute__(state, "root_identity"),
            object.__getattribute__(state, "files"),
        )
        success = True
        return snapshot
    except FileExistsError as error:
        raise _ContractError("run directory must be created exclusively") from error
    except OSError as error:
        raise _ContractError("runtime snapshot directory setup failed") from error
    finally:
        if state is not None and not success:
            finalizer = object.__getattribute__(state, "finalizer")
            if finalizer.alive:
                finalizer()
        if parent_fd is not None:
            os.close(parent_fd)
        if run_fd is not None:
            os.close(run_fd)
        if root_fd is not None and not success:
            os.close(root_fd)


def _runtime_hash_descriptor(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(descriptor, _RUNTIME_COPY_BUFFER_BYTES)
        if type(chunk) is not bytes:
            raise _ContractError("runtime snapshot returned unsafe bytes")
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
    return total, digest.hexdigest()


def _runtime_exact_record(value, expected_keys, field_name):
    if type(value) is not _FrozenJsonObject:
        raise _ContractError(f"{field_name} is not exact")
    try:
        namespace = object.__getattribute__(value, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(f"{field_name} storage is not exact") from error
    if type(namespace) is not dict or set(namespace) != {"_items"}:
        raise _ContractError(f"{field_name} storage is not exact")
    items = dict.__getitem__(namespace, "_items")
    if type(items) is not tuple or len(items) != len(expected_keys):
        raise _ContractError(f"{field_name} storage is not exact")
    record = {}
    keys = []
    for pair in items:
        if type(pair) is not tuple or len(pair) != 2:
            raise _ContractError(f"{field_name} storage is not exact")
        key, item = pair
        if type(key) is not str or key in record:
            raise _ContractError(f"{field_name} storage is not exact")
        keys.append(key)
        record[key] = item
    if keys != sorted(keys) or set(record) != expected_keys:
        raise _ContractError(f"{field_name} storage is not canonical")
    return record


def _runtime_audit_snapshot_fd(root_fd, root_identity, files):
    root = _runtime_exact_record(
        root_identity,
        {"logical_path", "device", "inode", "mode"},
        "runtime snapshot root identity",
    )
    if (
        root["logical_path"] != "/runtime"
        or type(root["device"]) is not int
        or type(root["inode"]) is not int
        or root["mode"] != 0o500
        or type(files) is not tuple
    ):
        raise _ContractError("runtime snapshot root identity is malformed")
    expected_files = tuple(
        _runtime_exact_record(
            item,
            {
                "basename",
                "logical_destination",
                "device",
                "inode",
                "link_count",
                "size",
                "mode",
                "sha256",
            },
            "runtime snapshot file identity",
        )
        for item in files
    )
    try:
        root_metadata = os.fstat(root_fd)
        initial_root_identity = (
            stat.S_ISDIR(root_metadata.st_mode),
            root_metadata.st_dev,
            root_metadata.st_ino,
            stat.S_IMODE(root_metadata.st_mode),
        )
        expected_root_identity = (
            True,
            root["device"],
            root["inode"],
            root["mode"],
        )
        if initial_root_identity != expected_root_identity:
            raise _ContractError("runtime snapshot root identity changed")
        expected_names = {item["basename"] for item in expected_files}
        initial_names = set(os.listdir(root_fd))
        if (
            len(expected_names) != len(expected_files)
            or any(
                type(name) is not str
                or name in {"", ".", ".."}
                or "/" in name
                for name in expected_names
            )
            or initial_names != expected_names
        ):
            raise _ContractError("runtime snapshot basename set changed")
        for expected in expected_files:
            descriptor = os.open(
                expected["basename"],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            try:
                before_hash = os.fstat(descriptor)
                before_identity = (
                    stat.S_ISREG(before_hash.st_mode),
                    before_hash.st_dev,
                    before_hash.st_ino,
                    before_hash.st_nlink,
                    before_hash.st_size,
                    stat.S_IMODE(before_hash.st_mode),
                    before_hash.st_mtime_ns,
                    before_hash.st_ctime_ns,
                )
                if (
                    not before_identity[0]
                    or before_hash.st_dev != expected["device"]
                    or before_hash.st_ino != expected["inode"]
                    or expected["link_count"] != 1
                    or before_hash.st_nlink != 1
                    or before_hash.st_size != expected["size"]
                    or stat.S_IMODE(before_hash.st_mode) != expected["mode"]
                ):
                    raise _ContractError(
                        "runtime snapshot file identity changed"
                    )
                total, digest = _runtime_hash_descriptor(descriptor)
                after_hash = os.fstat(descriptor)
                after_identity = (
                    stat.S_ISREG(after_hash.st_mode),
                    after_hash.st_dev,
                    after_hash.st_ino,
                    after_hash.st_nlink,
                    after_hash.st_size,
                    stat.S_IMODE(after_hash.st_mode),
                    after_hash.st_mtime_ns,
                    after_hash.st_ctime_ns,
                )
                if before_identity != after_identity:
                    raise _ContractError(
                        "runtime snapshot file changed while hashing"
                    )
                if total != expected["size"] or digest != expected["sha256"]:
                    raise _ContractError("runtime snapshot file bytes changed")
            finally:
                os.close(descriptor)
        final_root = os.fstat(root_fd)
        final_root_identity = (
            stat.S_ISDIR(final_root.st_mode),
            final_root.st_dev,
            final_root.st_ino,
            stat.S_IMODE(final_root.st_mode),
        )
        final_names = set(os.listdir(root_fd))
        if (
            final_root_identity != initial_root_identity
            or final_root_identity != expected_root_identity
            or final_names != initial_names
            or final_names != expected_names
        ):
            raise _ContractError("runtime snapshot root changed during audit")
    except OSError as error:
        raise _ContractError("runtime snapshot dirfd audit failed") from error


def revalidate_runtime_snapshot(snapshot):
    """Revalidate one builder-owned snapshot solely through retained dirfd."""

    if type(snapshot) is not RuntimeSnapshot:
        raise _ContractError("runtime snapshot must be exact RuntimeSnapshot")
    namespace = object.__getattribute__(snapshot, "__dict__")
    state = namespace.pop("_retained_runtime_state", None)
    if (
        type(state) is not _RetainedRuntimeSnapshotState
        or object.__getattribute__(state, "token")
        is not _RUNTIME_RETAINED_STATE_TOKEN
        or object.__getattribute__(state, "owner_ref")() is not snapshot
    ):
        raise _ContractError("runtime snapshot has no authentic retained dirfd state")
    root_fd = object.__getattribute__(state, "root_fd")
    root_identity = object.__getattribute__(state, "root_identity")
    files = object.__getattribute__(state, "files")
    snapshot_material = object.__getattribute__(state, "snapshot_material")
    finalizer = object.__getattribute__(state, "finalizer")
    owns_root_fd = False
    try:
        root_metadata = os.fstat(root_fd)
        owns_root_fd = (
            stat.S_ISDIR(root_metadata.st_mode)
            and root_metadata.st_dev == root_identity["device"]
            and root_metadata.st_ino == root_identity["inode"]
        )
        if not owns_root_fd:
            raise _ContractError(
                "runtime snapshot retained directory changed"
            )
        manifest = _validated_runtime_manifest(snapshot.manifest)
        if manifest.manifest_sha256 != snapshot_material["manifest_sha256"]:
            raise _ContractError("runtime snapshot manifest identity changed")
        if snapshot.directory_identities != (root_identity,):
            raise _ContractError("runtime snapshot directory identity changed")
        if snapshot.snapshot_sha256 != _canonical_sha256(snapshot_material):
            raise _ContractError("runtime snapshot commitment changed")
        _runtime_audit_snapshot_fd(root_fd, root_identity, files)
    except OSError as error:
        raise _ContractError("runtime snapshot retained dirfd revalidation failed") from error
    finally:
        if finalizer.alive:
            finalizer.detach()
        if owns_root_fd:
            _runtime_close_fd(root_fd)


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
        _validate_capability_preflight_report(self)


_CAPABILITY_PREFLIGHT_PROBES = (
    "namespaces_distinct",
    "root_user_mapping",
    "private_mount_propagation",
    "tmpfs_root",
    "readonly_bind",
    "readonly_root_writable_output",
    "chroot_interpreter",
    "capabilities_dropped",
    "environment_scrubbed",
    "network_isolated",
    "host_canary_denied",
    "strace_complete",
    "trace_access_evidence",
    "limits_no_new_privileges",
)
_CAPABILITY_PREFLIGHT_COMMANDS = (
    "unshare",
    "mount",
    "chroot",
    "strace",
    "python",
    "supervisor_python",
    "launcher",
)
_CAPABILITY_NAMESPACE_KEYS = (
    "host_user",
    "child_user",
    "host_mount",
    "child_mount",
    "host_network",
    "child_network",
)
_CAPABILITY_MOUNT_FACT_KEYS = (
    "root_private",
    "root_filesystem",
    "bind_read_only",
    "root_read_only",
    "nested_output_writable",
    "interpreter_entropy_device",
    "interpreter_entropy_read_only",
    "interpreter_entropy_only",
)
_CAPABILITY_PREFLIGHT_DIAGNOSTIC_MAX_BYTES = 1024
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_CAPABILITY_PREFLIGHT_NORMALIZED_FAILURE_REASONS = frozenset({
    "capability_command_identity_missing",
    "capability_command_identity_malformed",
    "capability_command_identity_unavailable",
    "capability_probe_runner_failed",
    "capability_probe_output_missing",
    "capability_probe_output_malformed",
})
_CAPABILITY_PREFLIGHT_CLOSED_REASONS = frozenset({
    "available",
    *_CAPABILITY_PREFLIGHT_NORMALIZED_FAILURE_REASONS,
    "capability_probe_output_contradictory",
    "capability_probe_nonce_mismatch",
    *(
        "capability_probe_" + name + "_failed"
        for name in _CAPABILITY_PREFLIGHT_PROBES
    ),
})


def _capability_preflight_evidence_contradicts(
    checks,
    codes,
    namespaces,
    mounts,
):
    if any((codes[name] == 0) != checks[name] for name in checks):
        return True
    semantic_checks = {
        "namespaces_distinct": all(
            namespaces["host_" + suffix]
            != namespaces["child_" + suffix]
            for suffix in ("user", "mount", "network")
        ),
        "private_mount_propagation": mounts["root_private"],
        "tmpfs_root": mounts["root_filesystem"] == "tmpfs",
        "readonly_bind": mounts["bind_read_only"],
        "readonly_root_writable_output": (
            mounts["root_read_only"]
            and mounts["nested_output_writable"]
        ),
    }
    return any(
        checks[name] != expected
        for name, expected in semantic_checks.items()
    )


def _validate_capability_preflight_report(report):
    expected_probes = set(_CAPABILITY_PREFLIGHT_PROBES)
    if set(report.checks) != expected_probes or any(
        type(report.checks[name]) is not bool for name in expected_probes
    ):
        raise _ContractError("capability preflight checks are not closed")
    if not set(report.command_identities) <= set(
        _CAPABILITY_PREFLIGHT_COMMANDS
    ):
        raise _ContractError("capability command identities are not closed")
    for command, identity in report.command_identities.items():
        if not isinstance(identity, Mapping):
            raise _ContractError("capability command identity malformed")
        values = _exact_keys(
            identity,
            ("path", "version", "sha256"),
            "capability command identity",
        )
        path = _require_text(values["path"], "command path")
        if not Path(path).is_absolute():
            raise _ContractError("capability command path must be absolute")
        _require_text(values["version"], "command version")
        _require_sha256(values["sha256"], "command sha256")
    namespaces = _exact_keys(
        report.namespace_identifiers,
        _CAPABILITY_NAMESPACE_KEYS,
        "namespace_identifiers",
    )
    namespace_kinds = {
        "host_user": "user",
        "child_user": "user",
        "host_mount": "mnt",
        "child_mount": "mnt",
        "host_network": "net",
        "child_network": "net",
    }
    for name, kind in namespace_kinds.items():
        value = namespaces[name]
        if type(value) is not str or re.fullmatch(
            re.escape(kind) + r":\[[0-9]+\]", value
        ) is None:
            raise _ContractError("capability namespace identifier malformed")
    mounts = _exact_keys(
        report.mount_facts,
        _CAPABILITY_MOUNT_FACT_KEYS,
        "mount_facts",
    )
    for name in _CAPABILITY_MOUNT_FACT_KEYS:
        if name in {"root_filesystem", "interpreter_entropy_device"}:
            continue
        _require_bool(mounts[name], "mount_facts." + name)
    if mounts["root_filesystem"] not in {"tmpfs", "unknown"}:
        raise _ContractError("capability root filesystem fact malformed")
    if mounts["interpreter_entropy_device"] != "/dev/urandom":
        raise _ContractError("capability entropy device fact malformed")
    result = _exact_keys(
        report.probe_result_codes,
        ("probes", "reason_code", "diagnostic"),
        "probe_result_codes",
    )
    codes = result["probes"]
    if not isinstance(codes, Mapping) or set(codes) != expected_probes:
        raise _ContractError("capability probe result codes are not closed")
    if any(type(codes[name]) is not int for name in expected_probes):
        raise _ContractError("capability probe result code is malformed")
    reason_code = _require_text(result["reason_code"], "preflight reason_code")
    if reason_code not in _CAPABILITY_PREFLIGHT_CLOSED_REASONS:
        raise _ContractError("preflight reason_code is not closed")
    diagnostic = _require_text(result["diagnostic"], "preflight diagnostic")
    if len(diagnostic.encode("utf-8")) > _CAPABILITY_PREFLIGHT_DIAGNOSTIC_MAX_BYTES:
        raise _ContractError("preflight diagnostic is oversized")
    contradictory = _capability_preflight_evidence_contradicts(
        report.checks,
        codes,
        namespaces,
        mounts,
    )
    if report.available:
        if set(report.command_identities) != set(
            _CAPABILITY_PREFLIGHT_COMMANDS
        ):
            raise _ContractError("available preflight requires every command")
        if not all(report.checks.values()) or any(
            codes[name] != 0 for name in expected_probes
        ):
            raise _ContractError("available preflight evidence contradicts status")
        if reason_code != "available":
            raise _ContractError("available preflight reason contradicts status")
        if contradictory:
            raise _ContractError("available preflight evidence is contradictory")
        if mounts["root_filesystem"] != "tmpfs" or not all(
            mounts[name]
            for name in _CAPABILITY_MOUNT_FACT_KEYS
            if name not in {"root_filesystem", "interpreter_entropy_device"}
        ):
            raise _ContractError("available preflight mount facts contradict status")
    else:
        if reason_code == "available":
            raise _ContractError("unavailable preflight reason contradicts status")
        if reason_code == "capability_probe_output_contradictory":
            if not contradictory:
                raise _ContractError(
                    "preflight contradiction reason lacks contradictory evidence"
                )
        elif reason_code.startswith("capability_probe_") and reason_code.endswith(
            "_failed"
        ) and reason_code != "capability_probe_runner_failed":
            if contradictory:
                raise _ContractError(
                    "preflight probe failure evidence is contradictory"
                )
            failed = tuple(
                name for name in _CAPABILITY_PREFLIGHT_PROBES
                if not report.checks[name]
            )
            expected_reason = (
                "capability_probe_" + failed[0] + "_failed"
                if failed else None
            )
            if (
                reason_code != expected_reason
                or set(report.command_identities)
                != set(_CAPABILITY_PREFLIGHT_COMMANDS)
            ):
                raise _ContractError(
                    "preflight probe failure reason contradicts evidence"
                )
        elif (
            reason_code not in _CAPABILITY_PREFLIGHT_NORMALIZED_FAILURE_REASONS
            and reason_code != "capability_probe_nonce_mismatch"
        ):
            raise _ContractError("unavailable preflight reason is invalid")
    body = {
        name: getattr(report, name)
        for name in _record_field_names(CapabilityPreflightReport)
        if name != "report_sha256"
    }
    if report.report_sha256 != _canonical_sha256(body):
        raise _ContractError("capability preflight report hash mismatch")


def _bounded_preflight_diagnostic(value):
    if type(value) is not str or not value:
        value = "capability preflight evidence unavailable"
    sanitized = []
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            sanitized.append("\ufffd")
        elif codepoint < 32 or codepoint == 127:
            sanitized.append(" ")
        else:
            sanitized.append(character)
    value = " ".join("".join(sanitized).split())
    if not value:
        value = "capability preflight evidence unavailable"
    retained = []
    retained_bytes = 0
    for character in value:
        encoded = character.encode("utf-8")
        if (
            retained_bytes + len(encoded)
            > _CAPABILITY_PREFLIGHT_DIAGNOSTIC_MAX_BYTES
        ):
            break
        retained.append(character)
        retained_bytes += len(encoded)
    return "".join(retained).strip()


def _preflight_report(
    *,
    audit_run_id,
    available,
    checks,
    command_identities,
    namespace_identifiers,
    mount_facts,
    probe_codes,
    reason_code,
    diagnostic,
    trace_sha256,
):
    body = {
        "schema_version": "capability_preflight_report_v1",
        "audit_run_id": audit_run_id,
        "available": available,
        "checks": checks,
        "command_identities": command_identities,
        "namespace_identifiers": namespace_identifiers,
        "mount_facts": mount_facts,
        "probe_result_codes": {
            "probes": probe_codes,
            "reason_code": reason_code,
            "diagnostic": _bounded_preflight_diagnostic(diagnostic),
        },
        "trace_sha256": trace_sha256,
    }
    return CapabilityPreflightReport(
        **body,
        report_sha256=_canonical_sha256(body),
    )


def _unavailable_preflight_report(
    *,
    audit_run_id,
    command_identities,
    reason_code,
    diagnostic,
    checks=None,
    probe_codes=None,
    namespace_identifiers=None,
    mount_facts=None,
    trace_sha256=_EMPTY_SHA256,
):
    normalized_checks = {
        name: False for name in _CAPABILITY_PREFLIGHT_PROBES
    }
    if checks is not None:
        for name in _CAPABILITY_PREFLIGHT_PROBES:
            if type(checks.get(name)) is bool:
                normalized_checks[name] = checks[name]
    normalized_codes = {
        name: -1 for name in _CAPABILITY_PREFLIGHT_PROBES
    }
    if probe_codes is not None:
        for name in _CAPABILITY_PREFLIGHT_PROBES:
            value = probe_codes.get(name)
            if type(value) is int:
                normalized_codes[name] = value
    normalized_namespaces = {
        "host_user": "user:[0]",
        "child_user": "user:[0]",
        "host_mount": "mnt:[0]",
        "child_mount": "mnt:[0]",
        "host_network": "net:[0]",
        "child_network": "net:[0]",
    }
    if isinstance(namespace_identifiers, Mapping):
        for name in _CAPABILITY_NAMESPACE_KEYS:
            value = namespace_identifiers.get(name)
            kind = "mnt" if name.endswith("mount") else name.split("_")[1]
            if type(value) is str and re.fullmatch(
                re.escape(kind) + r":\[[0-9]+\]", value
            ) is not None:
                normalized_namespaces[name] = value
    normalized_mounts = {
        "root_private": False,
        "root_filesystem": "unknown",
        "bind_read_only": False,
        "root_read_only": False,
        "nested_output_writable": False,
        "interpreter_entropy_device": "/dev/urandom",
        "interpreter_entropy_read_only": False,
        "interpreter_entropy_only": False,
    }
    if isinstance(mount_facts, Mapping):
        for name in _CAPABILITY_MOUNT_FACT_KEYS:
            value = mount_facts.get(name)
            if name == "root_filesystem" and value in {"tmpfs", "unknown"}:
                normalized_mounts[name] = value
            elif name == "interpreter_entropy_device" and value == "/dev/urandom":
                normalized_mounts[name] = value
            elif name not in {"root_filesystem", "interpreter_entropy_device"} and type(value) is bool:
                normalized_mounts[name] = value
    return _preflight_report(
        audit_run_id=audit_run_id,
        available=False,
        checks=normalized_checks,
        command_identities=command_identities,
        namespace_identifiers=normalized_namespaces,
        mount_facts=normalized_mounts,
        probe_codes=normalized_codes,
        reason_code=reason_code,
        diagnostic=diagnostic,
        trace_sha256=trace_sha256,
    )


def _create_preflight_scratch(scratch_parent, audit_run_id):
    try:
        parent = Path(scratch_parent).resolve(strict=True)
        parent_status = parent.stat()
    except OSError as error:
        raise _ContractError("preflight scratch parent is unavailable") from error
    if not stat.S_ISDIR(parent_status.st_mode):
        raise _ContractError("preflight scratch parent must be a directory")
    for counter in range(128):
        material = (
            audit_run_id.encode("utf-8")
            + b"\0"
            + str(os.getpid()).encode("ascii")
            + b"\0"
            + str(time.monotonic_ns()).encode("ascii")
            + b"\0"
            + str(counter).encode("ascii")
        )
        run_directory = parent / (
            "capability-preflight-" + hashlib.sha256(material).hexdigest()
        )
        try:
            os.mkdir(run_directory, 0o700)
        except FileExistsError:
            continue
        except OSError as error:
            raise _ContractError(
                "preflight scratch directory exclusive creation failed"
            ) from error
        created = run_directory.stat()
        if not stat.S_ISDIR(created.st_mode):
            raise _ContractError("preflight scratch path is not a directory")
        return run_directory
    raise _ContractError("preflight scratch directory uniqueness exhausted")


def _validated_preflight_command_identity(value, command):
    if not isinstance(value, Mapping):
        raise _ContractError("capability command identity malformed")
    identity = _exact_keys(
        value,
        ("command", "path", "version", "sha256"),
        "capability command identity",
    )
    if identity["command"] != command:
        raise _ContractError("capability command identity malformed")
    path = _require_text(identity["path"], "command path")
    if not Path(path).is_absolute():
        raise _ContractError("capability command identity malformed")
    version = _require_text(identity["version"], "command version")
    if len(version.encode("utf-8")) > 512:
        raise _ContractError("capability command identity malformed")
    digest = _require_sha256(identity["sha256"], "command sha256")
    return {"path": path, "version": version, "sha256": digest}


def _probe_evidence_shape(value):
    if not isinstance(value, Mapping):
        return None, "capability_probe_output_malformed"
    expected = (
        "audit_run_id",
        "checks",
        "probe_result_codes",
        "namespace_identifiers",
        "mount_facts",
        "trace_sha256",
        "diagnostic",
    )
    keys = set(value)
    if not set(expected) <= keys:
        return None, "capability_probe_output_missing"
    if keys != set(expected):
        return None, "capability_probe_output_malformed"
    checks = value["checks"]
    codes = value["probe_result_codes"]
    if not isinstance(checks, Mapping) or not isinstance(codes, Mapping):
        return None, "capability_probe_output_malformed"
    expected_probes = set(_CAPABILITY_PREFLIGHT_PROBES)
    if set(checks) != expected_probes or set(codes) != expected_probes:
        if not expected_probes <= set(checks) or not expected_probes <= set(codes):
            return None, "capability_probe_output_missing"
        return None, "capability_probe_output_malformed"
    if any(type(checks[name]) is not bool for name in expected_probes):
        return None, "capability_probe_output_malformed"
    if any(type(codes[name]) is not int for name in expected_probes):
        return None, "capability_probe_output_malformed"
    if any((codes[name] == 0) != checks[name] for name in expected_probes):
        return None, "capability_probe_output_contradictory"
    if not isinstance(value["namespace_identifiers"], Mapping):
        return None, "capability_probe_output_malformed"
    if not isinstance(value["mount_facts"], Mapping):
        return None, "capability_probe_output_malformed"
    namespaces = value["namespace_identifiers"]
    mounts = value["mount_facts"]
    if set(namespaces) != set(_CAPABILITY_NAMESPACE_KEYS):
        if not set(_CAPABILITY_NAMESPACE_KEYS) <= set(namespaces):
            return None, "capability_probe_output_missing"
        return None, "capability_probe_output_malformed"
    if set(mounts) != set(_CAPABILITY_MOUNT_FACT_KEYS):
        if not set(_CAPABILITY_MOUNT_FACT_KEYS) <= set(mounts):
            return None, "capability_probe_output_missing"
        return None, "capability_probe_output_malformed"
    if any(type(namespaces[name]) is not str for name in _CAPABILITY_NAMESPACE_KEYS):
        return None, "capability_probe_output_malformed"
    namespace_kinds = {
        "host_user": "user",
        "child_user": "user",
        "host_mount": "mnt",
        "child_mount": "mnt",
        "host_network": "net",
        "child_network": "net",
    }
    if any(
        re.fullmatch(
            re.escape(namespace_kinds[name]) + r":\[[0-9]+\]",
            namespaces[name],
        ) is None
        for name in _CAPABILITY_NAMESPACE_KEYS
    ):
        return None, "capability_probe_output_malformed"
    if mounts["root_filesystem"] not in {"tmpfs", "unknown"} or mounts[
        "interpreter_entropy_device"
    ] != "/dev/urandom":
        return None, "capability_probe_output_malformed"
    if any(
        type(mounts[name]) is not bool
        for name in _CAPABILITY_MOUNT_FACT_KEYS
        if name not in {"root_filesystem", "interpreter_entropy_device"}
    ):
        return None, "capability_probe_output_malformed"
    namespace_distinct = all(
        namespaces["host_" + suffix] != namespaces["child_" + suffix]
        for suffix in ("user", "mount", "network")
    )
    semantic_checks = {
        "namespaces_distinct": namespace_distinct,
        "private_mount_propagation": mounts["root_private"],
        "tmpfs_root": mounts["root_filesystem"] == "tmpfs",
        "readonly_bind": mounts["bind_read_only"],
        "readonly_root_writable_output": (
            mounts["root_read_only"]
            and mounts["nested_output_writable"]
        ),
    }
    if any(
        checks[name] != expected
        for name, expected in semantic_checks.items()
    ) or (
        all(checks.values())
        and not (
            mounts["interpreter_entropy_read_only"]
            and mounts["interpreter_entropy_only"]
        )
    ):
        return None, "capability_probe_output_contradictory"
    try:
        _require_text(value["audit_run_id"], "probe audit_run_id")
        _require_sha256(value["trace_sha256"], "probe trace_sha256")
    except _ContractError:
        return None, "capability_probe_output_malformed"
    if type(value["diagnostic"]) is not str:
        return None, "capability_probe_output_malformed"
    return dict(value), None


def _run_capability_preflight(*, scratch_parent, audit_run_id, runner):
    _require_text(audit_run_id, "audit_run_id")
    if not callable(runner):
        raise _ContractError("preflight runner must be callable")
    run_directory = _create_preflight_scratch(scratch_parent, audit_run_id)
    command_identities = {}
    for command in _CAPABILITY_PREFLIGHT_COMMANDS:
        raw_identity = None
        try:
            try:
                raw_identity = runner(
                    "identify",
                    {
                        "command": command,
                        "audit_run_id": audit_run_id,
                        "run_directory": str(run_directory),
                    },
                )
            except Exception as error:
                return _unavailable_preflight_report(
                    audit_run_id=audit_run_id,
                    command_identities=command_identities,
                    reason_code="capability_command_identity_unavailable",
                    diagnostic=str(error),
                )
            identity = _validated_preflight_command_identity(
                raw_identity, command
            )
        except _ContractError as error:
            missing = (
                isinstance(raw_identity, Mapping)
                and set(raw_identity)
                != {"command", "path", "version", "sha256"}
                and not {
                    "command", "path", "version", "sha256",
                } <= set(raw_identity)
            )
            kind = "missing" if missing else "malformed"
            return _unavailable_preflight_report(
                audit_run_id=audit_run_id,
                command_identities=command_identities,
                reason_code="capability_command_identity_" + kind,
                diagnostic=str(error),
            )
        command_identities[command] = identity
    probe_request = {
        "audit_run_id": audit_run_id,
        "run_directory": str(run_directory),
        "command_identities": command_identities,
    }
    try:
        raw_evidence = runner("probe", probe_request)
    except Exception as error:
        return _unavailable_preflight_report(
            audit_run_id=audit_run_id,
            command_identities=command_identities,
            reason_code="capability_probe_runner_failed",
            diagnostic=str(error),
        )
    evidence, shape_error = _probe_evidence_shape(raw_evidence)
    if shape_error is not None:
        raw_mapping = raw_evidence if isinstance(raw_evidence, Mapping) else {}
        return _unavailable_preflight_report(
            audit_run_id=audit_run_id,
            command_identities=command_identities,
            reason_code=shape_error,
            diagnostic="capability probe evidence is incomplete or invalid",
            checks=(
                raw_mapping.get("checks")
                if isinstance(raw_mapping.get("checks"), Mapping)
                else None
            ),
            probe_codes=(
                raw_mapping.get("probe_result_codes")
                if isinstance(raw_mapping.get("probe_result_codes"), Mapping)
                else None
            ),
            namespace_identifiers=(
                raw_mapping.get("namespace_identifiers")
                if isinstance(
                    raw_mapping.get("namespace_identifiers"), Mapping
                )
                else None
            ),
            mount_facts=(
                raw_mapping.get("mount_facts")
                if isinstance(raw_mapping.get("mount_facts"), Mapping)
                else None
            ),
            trace_sha256=(
                raw_mapping.get("trace_sha256")
                if type(raw_mapping.get("trace_sha256")) is str
                and re.fullmatch(
                    r"[0-9a-f]{64}", raw_mapping.get("trace_sha256")
                ) is not None
                else _EMPTY_SHA256
            ),
        )
    if evidence["audit_run_id"] != audit_run_id:
        return _unavailable_preflight_report(
            audit_run_id=audit_run_id,
            command_identities=command_identities,
            reason_code="capability_probe_nonce_mismatch",
            diagnostic="capability probe audit nonce mismatch",
            checks=evidence["checks"],
            probe_codes=evidence["probe_result_codes"],
            namespace_identifiers=evidence["namespace_identifiers"],
            mount_facts=evidence["mount_facts"],
            trace_sha256=evidence["trace_sha256"],
        )
    failed = tuple(
        name
        for name in _CAPABILITY_PREFLIGHT_PROBES
        if not evidence["checks"][name]
    )
    reason_code = "available"
    if failed:
        reason_code = "capability_probe_" + failed[0] + "_failed"
    return _preflight_report(
        audit_run_id=audit_run_id,
        available=not failed,
        checks=evidence["checks"],
        command_identities=command_identities,
        namespace_identifiers=evidence["namespace_identifiers"],
        mount_facts=evidence["mount_facts"],
        probe_codes=evidence["probe_result_codes"],
        reason_code=reason_code,
        diagnostic=evidence["diagnostic"],
        trace_sha256=evidence["trace_sha256"],
    )


_CAPABILITY_PREFLIGHT_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONHASHSEED": "0",
}
_CAPABILITY_PREFLIGHT_VERSION_ARGUMENTS = {
    "unshare": ("-V",),
    "mount": ("-V",),
    "chroot": ("--version",),
    "strace": ("-V",),
    "python": ("--version",),
    "supervisor_python": ("--version",),
}


def _hash_preflight_command(path):
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as error:
        raise _ContractError("capability command cannot be opened") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise _ContractError("capability command is not a regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or total != before.st_size:
            raise _ContractError("capability command changed while hashing")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _hash_preflight_descriptor(descriptor):
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise _ContractError("capability command is not a regular file")
    digest = hashlib.sha256()
    total = 0
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
    except OSError as error:
        raise _ContractError("capability command cannot be hashed") from error
    if (
        before.st_dev,
        before.st_ino,
        before.st_nlink,
        before.st_size,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_nlink,
        after.st_size,
        after.st_mode,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or total != before.st_size:
        raise _ContractError("capability command changed while hashing")
    return digest.hexdigest()


def _preflight_descriptor_identity(descriptor):
    status = os.fstat(descriptor)
    return (
        status.st_dev,
        status.st_ino,
        status.st_nlink,
        status.st_size,
        status.st_mode,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _preflight_snapshot_path(run_directory, command):
    snapshot_directory = Path(run_directory) / "command-snapshots"
    try:
        snapshot_directory.mkdir(mode=0o700)
    except FileExistsError:
        status = snapshot_directory.stat()
        if (
            not stat.S_ISDIR(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o700
        ):
            raise _ContractError("capability snapshot directory is unsafe")
    basename = "launcher.py" if command == "launcher" else command
    return snapshot_directory / basename


def _write_preflight_snapshot(snapshot_path, payload):
    try:
        descriptor = os.open(
            snapshot_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o500,
        )
    except OSError as error:
        raise _ContractError("capability snapshot cannot be created") from error
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise _ContractError("capability snapshot write failed")
            offset += written
        os.fsync(descriptor)
    except OSError as error:
        raise _ContractError("capability snapshot write failed") from error
    finally:
        os.close(descriptor)


def _snapshot_preflight_command(path, snapshot_path):
    try:
        source_fd = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as error:
        raise _ContractError("capability command cannot be opened") from error
    destination_fd = None
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise _ContractError("capability command is not a regular file")
        try:
            destination_fd = os.open(
                snapshot_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                0o500,
            )
        except OSError as error:
            raise _ContractError(
                "capability snapshot cannot be created"
            ) from error
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            offset = 0
            while offset < len(chunk):
                written = os.write(destination_fd, chunk[offset:])
                if written <= 0:
                    raise _ContractError("capability snapshot write failed")
                offset += written
        os.fsync(destination_fd)
        after = os.fstat(source_fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or total != before.st_size:
            raise _ContractError("capability command changed while snapshotting")
        return digest.hexdigest()
    except OSError as error:
        raise _ContractError("capability snapshot copy failed") from error
    finally:
        if destination_fd is not None:
            os.close(destination_fd)
        os.close(source_fd)


def _identify_preflight_command(command, *, run_directory):
    snapshot_path = _preflight_snapshot_path(run_directory, command)
    if command == "launcher":
        payload = _CAPABILITY_PREFLIGHT_LAUNCHER_SOURCE.encode("utf-8")
        _write_preflight_snapshot(snapshot_path, payload)
        digest = hashlib.sha256(payload).hexdigest()
        if _hash_preflight_command(snapshot_path) != digest:
            raise _ContractError("capability launcher snapshot changed")
        return {
            "command": command,
            "path": str(snapshot_path),
            "version": "task9-capability-launcher-v1",
            "sha256": digest,
        }
    if command == "python":
        candidate = sys.executable
    elif command == "supervisor_python":
        candidate = "/usr/bin/python3"
    else:
        candidate = shutil.which(command)
    if not candidate:
        raise _ContractError("capability command is unavailable")
    try:
        path = str(Path(candidate).resolve(strict=True))
    except OSError as error:
        raise _ContractError("capability command path cannot be resolved") from error
    digest = _snapshot_preflight_command(path, snapshot_path)
    if _hash_preflight_command(snapshot_path) != digest:
        raise _ContractError("capability command snapshot changed")
    arguments = _CAPABILITY_PREFLIGHT_VERSION_ARGUMENTS[command]
    snapshot_fd = None
    snapshot_identity = None
    try:
        snapshot_fd = os.open(
            snapshot_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        snapshot_identity = _preflight_descriptor_identity(snapshot_fd)
        if _hash_preflight_descriptor(snapshot_fd) != digest:
            raise _ContractError("capability command snapshot changed")
        completed = subprocess.run(
            (path, *arguments),
            executable=f"/proc/self/fd/{snapshot_fd}",
            check=False,
            close_fds=True,
            cwd="/",
            env=dict(_CAPABILITY_PREFLIGHT_ENVIRONMENT),
            pass_fds=(snapshot_fd,),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise _ContractError("capability command version probe failed") from error
    finally:
        if snapshot_fd is not None:
            if (
                snapshot_identity is not None
                and (
                    _preflight_descriptor_identity(snapshot_fd)
                    != snapshot_identity
                    or _hash_preflight_descriptor(snapshot_fd) != digest
                )
            ):
                os.close(snapshot_fd)
                raise _ContractError(
                    "capability command changed during version probe"
                )
            os.close(snapshot_fd)
    output = completed.stdout
    if completed.returncode != 0 or type(output) is not bytes:
        raise _ContractError("capability command version probe failed")
    try:
        version = output.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as error:
        raise _ContractError("capability command version is malformed") from error
    if not version or len(version.encode("utf-8")) > 512:
        raise _ContractError("capability command version is malformed")
    return {
        "command": command,
        "path": path,
        "version": version,
        "sha256": digest,
    }


_CAPABILITY_PREFLIGHT_CHILD_SOURCE = r'''
import ctypes
import json
import os
import resource
import socket

inherited_fds = []
descriptor_candidates = sorted(
    set(range(3, 64)) | set(__task9_infrastructure_fds__)
)
for descriptor in descriptor_candidates:
    try:
        os.fstat(descriptor)
    except OSError:
        continue
    inherited_fds.append(descriptor)

class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

class Data(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]

libc = ctypes.CDLL(None, use_errno=True)
header = Header(0x20080522, 0)
data = (Data * 2)()
capget_code = libc.capget(ctypes.byref(header), ctypes.byref(data))
cap_words = [
    [item.effective, item.permitted, item.inheritable] for item in data
]
bounding = []
ambient = []
for capability in range(64):
    bounded = libc.prctl(23, capability, 0, 0, 0)
    if bounded >= 0:
        bounding.append(bounded)
    ambient_value = libc.prctl(47, 2, capability, 0, 0)
    if ambient_value >= 0:
        ambient.append(ambient_value)
nnp = libc.prctl(39, 0, 0, 0, 0)

entropy_fd = os.open("/dev/urandom", os.O_RDONLY)
try:
    entropy_byte = os.read(entropy_fd, 1)
finally:
    os.close(entropy_fd)
if len(entropy_byte) != 1:
    raise RuntimeError("interpreter entropy device read failed")

with open("/runtime/probe.txt", "rb") as stream:
    permitted = stream.read().decode("ascii")
directory_fd = os.open("/runtime", os.O_RDONLY | os.O_DIRECTORY)
try:
    relative_fd = os.open("probe.txt", os.O_RDONLY, dir_fd=directory_fd)
    try:
        relative = os.read(relative_fd, 64).decode("ascii")
    finally:
        os.close(relative_fd)
finally:
    os.close(directory_fd)
host_canary_path = "__TASK9_HOST_CANARY_PATH__"
host_errno = 0
try:
    os.open(host_canary_path, os.O_RDONLY)
except OSError as error:
    host_errno = error.errno
long_errno = 0
try:
    os.open("/forbidden-task9-" + "x" * 512, os.O_RDONLY)
except OSError as error:
    long_errno = error.errno
network_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    network_code = network_socket.connect_ex(("192.0.2.1", 9))
finally:
    network_socket.close()

print(json.dumps({
    "marker": "task9-chrooted-interpreter",
    "cwd": os.getcwd(),
    "environment_keys": sorted(os.environ),
    "permitted_read": permitted,
    "relative_read": relative,
    "host_errno": host_errno,
    "host_canary_path": host_canary_path,
    "long_errno": long_errno,
    "network_code": network_code,
    "inherited_fds": inherited_fds,
    "capget_code": capget_code,
    "capability_words": cap_words,
    "bounding_values": bounding,
    "ambient_values": ambient,
    "no_new_privileges": nnp,
    "limits": {
        "core": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "file_size": list(resource.getrlimit(resource.RLIMIT_FSIZE)),
        "open_files": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
        "processes": list(resource.getrlimit(resource.RLIMIT_NPROC)),
    },
}, sort_keys=True, separators=(",", ":")))
'''


_CAPABILITY_PREFLIGHT_LAUNCHER_SOURCE = r'''
import ctypes
import json
import os
import resource
import sys

class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

class Data(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]

libc = ctypes.CDLL(None, use_errno=True)
for capability in range(64):
    result = libc.prctl(24, capability, 0, 0, 0)
    if result != 0 and ctypes.get_errno() != 22:
        raise OSError(ctypes.get_errno(), "bounding capability drop failed")
if libc.prctl(47, 4, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "ambient capability clear failed")
header = Header(0x20080522, 0)
data = (Data * 2)()
if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
    raise OSError(ctypes.get_errno(), "capability set clear failed")
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "no-new-privileges failed")
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
python_path = sys.argv[1]
worker_source = sys.argv[2]
environment = {"LANG": "C", "LC_ALL": "C", "PYTHONHASHSEED": "0"}
if os.environ != environment:
    raise RuntimeError("launcher environment is not closed")
infrastructure_fds = json.loads(sys.argv[3])
if (
    type(infrastructure_fds) is not list
    or not infrastructure_fds
    or any(type(value) is not int or value < 3 for value in infrastructure_fds)
    or infrastructure_fds != sorted(set(infrastructure_fds))
):
    raise RuntimeError("launcher infrastructure descriptors are malformed")
for descriptor in infrastructure_fds:
    try:
        os.close(descriptor)
    except OSError:
        pass
os.closerange(3, 64)
worker_globals = {
    "__name__": "__main__",
    "__file__": "<task9-worker>",
    "__package__": None,
    "__task9_infrastructure_fds__": tuple(infrastructure_fds),
}
exec(
    compile(worker_source, "<task9-worker>", "exec"),
    worker_globals,
    worker_globals,
)
'''


_CAPABILITY_PREFLIGHT_SUPERVISOR_SOURCE = r'''
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

request = json.loads(sys.argv[1])
commands = request["commands"]
run_directory = Path(request["run_directory"])
root = run_directory / "root"
host_output = run_directory / "host-output"
host_source = run_directory / "host-source"
root.mkdir(mode=0o700)
old_umask = os.umask(0)
try:
    host_output.mkdir(mode=0o777)
finally:
    os.umask(old_umask)
host_source.mkdir(mode=0o700)
probe_source = host_source / "probe.txt"
with probe_source.open("x", encoding="ascii") as stream:
    stream.write("task9-permitted-read")
host_canary = run_directory / "host-canary-denied-task9"
with host_canary.open("x", encoding="ascii") as stream:
    stream.write("task9-host-canary")

environment = {"LANG": "C", "LC_ALL": "C", "PYTHONHASHSEED": "0"}
command_fds = tuple(request["command_descriptors"].values())
def execute(arguments, *, timeout=20, pass_fds=()):
    result = subprocess.run(
        tuple(arguments), check=False, close_fds=True, cwd="/",
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, pass_fds=command_fds + tuple(pass_fds),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[:1024].decode(
            "utf-8", "replace"
        )
        raise RuntimeError("command failed: " + detail)
    return result

execute((commands["mount"], "--make-rprivate", "/"))
execute((
    commands["mount"], "-t", "tmpfs", "-o",
    "nodev,nosuid,size=128m", "tmpfs", str(root),
))

def target_for(source):
    return root / source.lstrip("/")

def bind_read_only(source, *, allow_device=False, logical_path=None):
    target = target_for(logical_path if logical_path is not None else source)
    source_path = Path(source)
    if source_path.is_dir():
        target.mkdir(mode=0o755, parents=True, exist_ok=True)
    else:
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if target.exists():
            if logical_path is None or not target.is_file():
                raise RuntimeError("bind target unexpectedly exists")
        else:
            with target.open("x", encoding="ascii"):
                pass
    execute((commands["mount"], "--bind", source, str(target)))
    remount_options = "remount,bind,ro,nosuid"
    if not allow_device:
        remount_options += ",nodev"
    execute((
        commands["mount"], "-o", remount_options,
        str(target),
    ))
    return target

runtime = root / "runtime"
runtime.mkdir(mode=0o755)
probe_target = runtime / "probe.txt"
with probe_target.open("x", encoding="ascii"):
    pass
execute((commands["mount"], "--bind", str(probe_source), str(probe_target)))
execute((
    commands["mount"], "-o", "remount,bind,ro,nodev,nosuid",
    str(probe_target),
))
entropy_target = bind_read_only("/dev/urandom", allow_device=True)
entropy_write_errno = 0
try:
    entropy_fd = os.open(entropy_target, os.O_WRONLY)
except OSError as error:
    entropy_write_errno = error.errno
else:
    os.close(entropy_fd)

mounted_sources = []
for source in request["runtime_sources"]:
    if Path(source).exists() and source not in mounted_sources:
        bind_read_only(source)
        mounted_sources.append(source)
bind_read_only(
    commands["python"], logical_path=request["python_logical_path"]
)
bind_read_only(
    commands["launcher"], logical_path=request["launcher_logical_path"]
)

output_target = root / "output"
output_target.mkdir(mode=0o755)
execute((commands["mount"], "--bind", str(host_output), str(output_target)))
execute((commands["mount"], "-o", "remount,bind,rw,nodev,nosuid", str(output_target)))

bind_errno = 0
try:
    with probe_target.open("a", encoding="ascii") as stream:
        stream.write("forbidden")
except OSError as error:
    bind_errno = error.errno

execute((
    commands["mount"], "-o", "remount,ro,nodev,nosuid", str(root),
))
root_errno = 0
try:
    with (root / "root-write-forbidden").open("x", encoding="ascii"):
        pass
except OSError as error:
    root_errno = error.errno
output_write_ok = False
with (output_target / "nested-output-writable").open("x", encoding="ascii") as stream:
    stream.write("task9-output")
output_write_ok = True

mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
root_line = next(
    line for line in mountinfo.splitlines()
    if line.split()[4] == str(root)
)
root_separator = root_line.split().index("-")
root_private = not any(
    token.startswith(("shared:", "master:", "propagate_from:"))
    for token in root_line.split()[6:root_separator]
)
root_fstype = root_line.split()[root_separator + 1]
entropy_line = next(
    line for line in mountinfo.splitlines()
    if line.split()[4] == str(entropy_target)
)
route_rows = []
for line in Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]:
    columns = line.split()
    if len(columns) >= 4:
        route_rows.append(columns[:4])
interfaces = sorted(
    line.split(":", 1)[0].strip()
    for line in Path("/proc/net/dev").read_text(
        encoding="ascii"
    ).splitlines()[2:]
    if ":" in line
)

trace_path = run_directory / "trace.log"
if trace_path.exists():
    raise RuntimeError("trace path unexpectedly exists")
child_arguments = (
    commands["chroot"], str(root), request["python_logical_path"],
    "-I", "-S", request["launcher_logical_path"],
    request["python_logical_path"], request["child_source"],
    json.dumps(sorted(command_fds), separators=(",", ":")),
)
trace = subprocess.run(
    (
        commands["strace"], "-f", "-s", "4096", "-yy",
        "-e", "trace=%file,%network,%process,getrandom", "-o", str(trace_path),
        "--", *child_arguments,
    ),
    check=False, close_fds=True, cwd="/", env=environment,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    pass_fds=command_fds,
)
trace_bytes = trace_path.read_bytes() if trace_path.is_file() else b""
child = None
try:
    child = json.loads(trace.stdout.decode("utf-8", "strict"))
except Exception:
    child = None

attestation = {
    "audit_run_id": request["audit_run_id"],
    "child_namespaces": {
        name: os.readlink("/proc/self/ns/" + name)
        for name in ("user", "mnt", "net")
    },
    "uid_map": Path("/proc/self/uid_map").read_text(encoding="ascii"),
    "root_private": root_private,
    "root_fstype": root_fstype,
    "bind_errno": bind_errno,
    "root_errno": root_errno,
    "output_write_ok": output_write_ok,
    "entropy_mount_line": entropy_line,
    "entropy_write_errno": entropy_write_errno,
    "executed_command_paths": commands,
    "route_rows": route_rows,
    "supervisor_environment_keys": sorted(os.environ),
    "interfaces": interfaces,
    "launcher_logical_path": request["launcher_logical_path"],
    "child": child,
    "trace_returncode": trace.returncode,
    "trace_stderr": trace.stderr[:1024].decode("utf-8", "replace"),
    "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
}
attestation_bytes = json.dumps(
    attestation, sort_keys=True, separators=(",", ":")
).encode("utf-8")
attestation_path = run_directory / "attestation.json"
attestation_fd = os.open(
    attestation_path,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
    0o600,
)
try:
    offset = 0
    while offset < len(attestation_bytes):
        offset += os.write(attestation_fd, attestation_bytes[offset:])
    os.fsync(attestation_fd)
finally:
    os.close(attestation_fd)
print("attestation retained")
'''


def _read_retained_preflight_file(
    path,
    *,
    maximum_bytes,
    expected_sha256=None,
):
    if expected_sha256 is not None:
        _require_sha256(expected_sha256, "retained preflight expected sha256")
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as error:
        raise _ContractError("retained preflight file cannot be opened") from error
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < 1
            or before.st_size > maximum_bytes
        ):
            raise _ContractError("retained preflight file identity is unsafe")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                raise _ContractError("retained preflight file is oversized")
        after = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_nlink,
            before.st_size,
            before.st_mode,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_nlink,
            after.st_size,
            after.st_mode,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        payload = b"".join(chunks)
        if identity_before != identity_after or len(payload) != before.st_size:
            raise _ContractError("retained preflight file changed while reading")
        if (
            expected_sha256 is not None
            and hashlib.sha256(payload).hexdigest() != expected_sha256
        ):
            raise _ContractError("retained preflight file digest changed")
        return payload
    except OSError as error:
        raise _ContractError("retained preflight file cannot be read") from error
    finally:
        os.close(descriptor)


def _open_preflight_execution_descriptors(payload):
    identities = payload["command_identities"]
    descriptors = {}
    descriptor_identities = {}
    snapshot_paths = {}
    try:
        for command in _CAPABILITY_PREFLIGHT_COMMANDS:
            identity = _validated_preflight_command_identity(
                {"command": command, **dict(identities[command])},
                command,
            )
            if _hash_preflight_command(identity["path"]) != identity["sha256"]:
                raise _ContractError(
                    "capability command origin changed before execution"
                )
            snapshot_path = _preflight_snapshot_path(
                payload["run_directory"], command
            )
            descriptor = os.open(
                snapshot_path,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            descriptors[command] = descriptor
            status = os.fstat(descriptor)
            if (
                not stat.S_ISREG(status.st_mode)
                or status.st_nlink != 1
                or stat.S_IMODE(status.st_mode) != 0o500
                or _hash_preflight_descriptor(descriptor) != identity["sha256"]
            ):
                raise _ContractError(
                    "capability snapshot changed before execution"
                )
            descriptor_identities[command] = (
                _preflight_descriptor_identity(descriptor)
            )
            snapshot_paths[command] = str(snapshot_path)
        return descriptors, descriptor_identities, snapshot_paths
    except (OSError, KeyError) as error:
        for descriptor in descriptors.values():
            os.close(descriptor)
        raise _ContractError(
            "capability execution descriptor cannot be retained"
        ) from error
    except Exception:
        for descriptor in descriptors.values():
            os.close(descriptor)
        raise


def _revalidate_preflight_execution_descriptors(
    descriptors,
    descriptor_identities,
    identities,
):
    for command in _CAPABILITY_PREFLIGHT_COMMANDS:
        descriptor = descriptors[command]
        status = os.fstat(descriptor)
        if (
            _preflight_descriptor_identity(descriptor)
            != descriptor_identities[command]
            or not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or stat.S_IMODE(status.st_mode) != 0o500
            or _hash_preflight_descriptor(descriptor)
            != identities[command]["sha256"]
        ):
            raise _ContractError("capability execution descriptor changed")


def _validate_preflight_attestation(
    facts,
    *,
    audit_run_id,
    command_paths,
    launcher_logical_path,
):
    expected_keys = {
        "audit_run_id",
        "bind_errno",
        "child",
        "child_namespaces",
        "entropy_mount_line",
        "entropy_write_errno",
        "executed_command_paths",
        "interfaces",
        "launcher_logical_path",
        "output_write_ok",
        "root_errno",
        "root_fstype",
        "root_private",
        "route_rows",
        "supervisor_environment_keys",
        "trace_returncode",
        "trace_sha256",
        "trace_stderr",
        "uid_map",
    }
    if type(facts) is not dict or set(facts) != expected_keys:
        raise _ContractError("capability attestation schema is not closed")
    if facts["audit_run_id"] != audit_run_id:
        raise _ContractError("capability attestation audit nonce contradicts")
    if (
        type(facts["executed_command_paths"]) is not dict
        or facts["executed_command_paths"] != command_paths
        or set(facts["executed_command_paths"])
        != set(_CAPABILITY_PREFLIGHT_COMMANDS)
        or any(
            type(value) is not str or not value.startswith("/proc/self/fd/")
            for value in facts["executed_command_paths"].values()
        )
        or facts["launcher_logical_path"] != launcher_logical_path
    ):
        raise _ContractError(
            "capability attestation execution paths contradict"
        )
    integer_fields = (
        "bind_errno",
        "entropy_write_errno",
        "root_errno",
        "trace_returncode",
    )
    boolean_fields = ("output_write_ok", "root_private")
    if any(type(facts[name]) is not int for name in integer_fields) or any(
        type(facts[name]) is not bool for name in boolean_fields
    ):
        raise _ContractError("capability attestation scalar is malformed")
    for name, maximum in (
        ("entropy_mount_line", 8192),
        ("root_fstype", 64),
        ("trace_stderr", 1024),
        ("uid_map", 8192),
    ):
        value = facts[name]
        if type(value) is not str or len(value.encode("utf-8")) > maximum:
            raise _ContractError("capability attestation text is malformed")
    if not facts["root_fstype"]:
        raise _ContractError("capability attestation text is malformed")
    _require_sha256(facts["trace_sha256"], "attestation trace sha256")

    namespaces = facts["child_namespaces"]
    if (
        type(namespaces) is not dict
        or set(namespaces) != {"user", "mnt", "net"}
        or any(type(value) is not str for value in namespaces.values())
    ):
        raise _ContractError("capability attestation namespaces malformed")
    routes = facts["route_rows"]
    if (
        type(routes) is not list
        or len(routes) > 1024
        or any(
            type(row) is not list
            or len(row) != 4
            or any(type(value) is not str for value in row)
            for row in routes
        )
    ):
        raise _ContractError("capability attestation routes malformed")
    interfaces = facts["interfaces"]
    if (
        type(interfaces) is not list
        or len(interfaces) > 64
        or any(type(value) is not str for value in interfaces)
        or interfaces != sorted(set(interfaces))
    ):
        raise _ContractError("capability attestation interfaces malformed")
    if facts["supervisor_environment_keys"] != [
        "LANG", "LC_ALL", "PYTHONHASHSEED",
    ]:
        raise _ContractError(
            "capability supervisor environment is not closed"
        )

    child = facts["child"]
    if child is None:
        return facts
    child_keys = {
        "ambient_values",
        "bounding_values",
        "capability_words",
        "capget_code",
        "cwd",
        "environment_keys",
        "host_canary_path",
        "host_errno",
        "inherited_fds",
        "limits",
        "long_errno",
        "marker",
        "network_code",
        "no_new_privileges",
        "permitted_read",
        "relative_read",
    }
    if type(child) is not dict or set(child) != child_keys:
        raise _ContractError("capability child attestation is not closed")
    for name in (
        "capget_code",
        "host_errno",
        "long_errno",
        "network_code",
        "no_new_privileges",
    ):
        if type(child[name]) is not int:
            raise _ContractError("capability child integer is malformed")
    for name in (
        "cwd",
        "host_canary_path",
        "marker",
        "permitted_read",
        "relative_read",
    ):
        value = child[name]
        if (
            type(value) is not str
            or not value
            or len(value.encode("utf-8")) > 8192
        ):
            raise _ContractError("capability child text is malformed")
    environment_keys = child["environment_keys"]
    if (
        type(environment_keys) is not list
        or len(environment_keys) > 16
        or any(type(value) is not str for value in environment_keys)
        or environment_keys != sorted(set(environment_keys))
    ):
        raise _ContractError("capability child environment is malformed")
    capability_words = child["capability_words"]
    if (
        type(capability_words) is not list
        or len(capability_words) != 2
        or any(
            type(row) is not list
            or len(row) != 3
            or any(type(value) is not int for value in row)
            for row in capability_words
        )
    ):
        raise _ContractError("capability child capability words malformed")
    for name in ("ambient_values", "bounding_values"):
        values = child[name]
        if (
            type(values) is not list
            or len(values) > 64
            or any(type(value) is not int for value in values)
        ):
            raise _ContractError("capability child capability list malformed")
    inherited_fds = child["inherited_fds"]
    if (
        type(inherited_fds) is not list
        or any(type(value) is not int for value in inherited_fds)
        or inherited_fds != sorted(set(inherited_fds))
    ):
        raise _ContractError("capability child inherited descriptors malformed")
    limits = child["limits"]
    if (
        type(limits) is not dict
        or set(limits) != {"core", "file_size", "open_files", "processes"}
        or any(
            type(value) is not list
            or len(value) != 2
            or any(type(item) is not int for item in value)
            for value in limits.values()
        )
    ):
        raise _ContractError("capability child limits malformed")
    return facts


def _production_probe_response(payload):
    identities = payload["command_identities"]
    host_namespaces = {
        name: os.readlink("/proc/self/ns/" + name)
        for name in ("user", "mnt", "net")
    }
    python_prefix = str(
        Path(identities["python"]["path"]).parent.parent.resolve(strict=True)
    )
    runtime_sources = [
        python_prefix,
        "/lib",
        "/lib64",
        "/usr/lib",
        "/usr/lib64",
    ]
    host_canary_path = str(
        Path(payload["run_directory"]) / "host-canary-denied-task9"
    )
    child_source = _CAPABILITY_PREFLIGHT_CHILD_SOURCE.replace(
        '"__TASK9_HOST_CANARY_PATH__"',
        json.dumps(host_canary_path),
    )
    launcher_logical_path = "/task9-preflight/launcher.py"
    (
        descriptors,
        descriptor_identities,
        snapshot_paths,
    ) = _open_preflight_execution_descriptors(payload)
    command_paths = {
        command: f"/proc/self/fd/{descriptor}"
        for command, descriptor in descriptors.items()
    }
    unshare_path = command_paths["unshare"]
    supervisor_python_path = command_paths["supervisor_python"]
    try:
        request = {
            "audit_run_id": payload["audit_run_id"],
            "run_directory": payload["run_directory"],
            "commands": command_paths,
            "command_descriptors": descriptors,
            "command_snapshot_paths": snapshot_paths,
            "runtime_sources": runtime_sources,
            "python_logical_path": identities["python"]["path"],
            "launcher_logical_path": launcher_logical_path,
            "child_source": child_source,
        }
        completed = subprocess.run(
            (
                identities["unshare"]["path"],
                "-Urnm",
                supervisor_python_path,
                "-S",
                "-B",
                "-c",
                _CAPABILITY_PREFLIGHT_SUPERVISOR_SOURCE,
                json.dumps(request, sort_keys=True, separators=(",", ":")),
            ),
            executable=unshare_path,
            check=False,
            close_fds=True,
            cwd="/",
            env=dict(_CAPABILITY_PREFLIGHT_ENVIRONMENT),
            pass_fds=tuple(descriptors.values()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        _revalidate_preflight_execution_descriptors(
            descriptors,
            descriptor_identities,
            identities,
        )
    finally:
        for descriptor in descriptors.values():
            os.close(descriptor)
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout)[:1024].decode(
            "utf-8", "replace"
        )
        raise _ContractError(
            "capability namespace supervisor failed: " + diagnostic
        )
    if completed.stdout != b"attestation retained\n":
        raise _ContractError("capability supervisor completion is malformed")
    attestation_bytes = _read_retained_preflight_file(
        Path(payload["run_directory"]) / "attestation.json",
        maximum_bytes=64 * 1024,
    )
    try:
        facts = json.loads(attestation_bytes.decode("utf-8", "strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _ContractError("capability attestation is malformed") from error
    facts = _validate_preflight_attestation(
        facts,
        audit_run_id=payload["audit_run_id"],
        command_paths=command_paths,
        launcher_logical_path=launcher_logical_path,
    )
    trace_bytes = _read_retained_preflight_file(
        Path(payload["run_directory"]) / "trace.log",
        maximum_bytes=2 * 1024 * 1024,
    )
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    if facts.get("trace_sha256") != trace_sha256:
        raise _ContractError("retained trace digest contradicts supervisor claim")
    try:
        trace_text = trace_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise _ContractError("retained trace is not valid UTF-8") from error
    child = facts.get("child")
    if not isinstance(child, Mapping) or type(trace_text) is not str:
        child = {}
        trace_text = ""
    child_namespaces = facts.get("child_namespaces", {})
    namespace_identifiers = {
        "host_user": host_namespaces["user"],
        "child_user": child_namespaces.get("user", "missing"),
        "host_mount": host_namespaces["mnt"],
        "child_mount": child_namespaces.get("mnt", "missing"),
        "host_network": host_namespaces["net"],
        "child_network": child_namespaces.get("net", "missing"),
    }
    namespace_distinct = all(
        namespace_identifiers["host_" + name]
        != namespace_identifiers["child_" + name]
        for name in ("user", "mount", "network")
    )
    uid_map_rows = []
    if type(facts.get("uid_map")) is str:
        for line in facts["uid_map"].splitlines():
            columns = line.split()
            if len(columns) == 3 and all(item.isdigit() for item in columns):
                uid_map_rows.append(tuple(int(item) for item in columns))
    root_mapping = any(
        inside == 0 and outside == os.getuid() and length >= 1
        for inside, outside, length in uid_map_rows
    )
    routes = facts.get("route_rows")
    interfaces = facts.get("interfaces")
    network_facts = (
        type(routes) is list
        and not any(
            type(row) is list
            and len(row) >= 4
            and row[1] == "00000000"
            and int(row[3], 16) & 1
            for row in routes
        )
        and type(interfaces) is list
        and set(interfaces) <= {"lo"}
        and type(child.get("network_code")) is int
        and child.get("network_code") != 0
    )
    limits = child.get("limits", {})
    capabilities_dropped = (
        child.get("capget_code") == 0
        and child.get("capability_words") == [[0, 0, 0], [0, 0, 0]]
        and isinstance(child.get("bounding_values"), list)
        and not any(child.get("bounding_values"))
        and isinstance(child.get("ambient_values"), list)
        and not any(child.get("ambient_values"))
    )
    limits_nnp = (
        child.get("no_new_privileges") == 1
        and limits.get("core") == [0, 0]
        and limits.get("file_size") == [1048576, 1048576]
        and limits.get("open_files") == [64, 64]
        and limits.get("processes") == [1, 1]
    )
    trace_complete = (
        facts.get("trace_returncode") == 0
        and "+++ exited with 0 +++" in trace_text
        and "unfinished ..." not in trace_text
        and "<... " not in trace_text
        and "openat(" in trace_text
        and ("socket(" in trace_text or "connect(" in trace_text)
    )
    relative_open = re.search(
        r'openat\(\d+<([^>]+/root/runtime)>, "probe\.txt", '
        r'[^\n]*\) = \d+<\1/probe\.txt>',
        trace_text,
    )
    launcher_open = re.search(
        r'(?:open|openat)\([^\n]*"'
        + re.escape(launcher_logical_path)
        + r'"[^\n]*\) = \d+',
        trace_text,
    )
    host_canary_denial = re.search(
        r'(?:open|openat)\([^\n]*"'
        + re.escape(host_canary_path)
        + r'"[^\n]*\) = -1 ENOENT',
        trace_text,
    )
    trace_access = (
        "/runtime/probe.txt" in trace_text
        and host_canary_denial is not None
        and "forbidden-task9-" + "x" * 256 in trace_text
        and "ENOENT" in trace_text
        and relative_open is not None
    )
    entropy_line = facts.get("entropy_mount_line", "")
    entropy_columns = entropy_line.split() if type(entropy_line) is str else []
    expected_entropy_target = str(
        Path(payload["run_directory"]) / "root" / "dev" / "urandom"
    )
    entropy_mount_read_only = (
        len(entropy_columns) > 6
        and entropy_columns[4] == expected_entropy_target
        and "ro" in entropy_columns[5].split(",")
    )
    device_paths = set(re.findall(r'"(/dev/[^"\\]+)', trace_text))
    entropy_only = device_paths == {"/dev/urandom"}
    checks = {
        "namespaces_distinct": namespace_distinct,
        "root_user_mapping": root_mapping,
        "private_mount_propagation": facts.get("root_private") is True,
        "tmpfs_root": facts.get("root_fstype") == "tmpfs",
        "readonly_bind": facts.get("bind_errno") == 30,
        "readonly_root_writable_output": (
            facts.get("root_errno") == 30
            and facts.get("output_write_ok") is True
        ),
        "chroot_interpreter": (
            child.get("marker") == "task9-chrooted-interpreter"
            and child.get("cwd") == "/"
            and child.get("permitted_read") == "task9-permitted-read"
            and child.get("relative_read") == "task9-permitted-read"
            and child.get("inherited_fds") == []
            and launcher_open is not None
        ),
        "capabilities_dropped": capabilities_dropped,
        "environment_scrubbed": child.get("environment_keys") == [
            "LANG", "LC_ALL", "PYTHONHASHSEED",
        ],
        "network_isolated": network_facts,
        "host_canary_denied": (
            child.get("host_canary_path") == host_canary_path
            and child.get("host_errno") == 2
            and host_canary_denial is not None
        ),
        "strace_complete": trace_complete,
        "trace_access_evidence": trace_access,
        "limits_no_new_privileges": limits_nnp,
    }
    codes = {name: 0 if passed else 1 for name, passed in checks.items()}
    failed = tuple(name for name in _CAPABILITY_PREFLIGHT_PROBES if not checks[name])
    diagnostic = "all capability probes passed"
    if failed:
        detail = facts.get("trace_stderr", "")
        diagnostic = "failed probes: " + ",".join(failed)
        if type(detail) is str and detail:
            diagnostic += "; trace: " + detail
    return {
        "audit_run_id": payload["audit_run_id"],
        "checks": checks,
        "probe_result_codes": codes,
        "namespace_identifiers": namespace_identifiers,
        "mount_facts": {
            "root_private": facts.get("root_private") is True,
            "root_filesystem": facts.get("root_fstype", "unknown"),
            "bind_read_only": facts.get("bind_errno") == 30,
            "root_read_only": facts.get("root_errno") == 30,
            "nested_output_writable": facts.get("output_write_ok") is True,
            "interpreter_entropy_device": "/dev/urandom",
            "interpreter_entropy_read_only": entropy_mount_read_only,
            "interpreter_entropy_only": entropy_only,
        },
        "trace_sha256": trace_sha256,
        "diagnostic": diagnostic,
    }


def _production_capability_preflight_runner(action, payload):
    if action == "identify":
        return _identify_preflight_command(
            payload["command"],
            run_directory=payload["run_directory"],
        )
    if action == "probe":
        return _production_probe_response(payload)
    raise _ContractError("unknown capability runner action")


def run_capability_preflight(*, scratch_parent):
    """Execute the complete production capability preflight once."""

    material = (
        str(os.getpid()).encode("ascii")
        + b"\0"
        + str(time.monotonic_ns()).encode("ascii")
    )
    audit_run_id = "capability-preflight-" + hashlib.sha256(material).hexdigest()
    return _run_capability_preflight(
        scratch_parent=scratch_parent,
        audit_run_id=audit_run_id,
        runner=_production_capability_preflight_runner,
    )


_COUNTERFACTUAL_DOMAIN_VERSION = "counterfactual_domain_v1"
_COUNTERFACTUAL_POINT_KINDS = frozenset({"canonical", "valid", "invalid"})
_METAMORPHIC_RELATION_KINDS = frozenset(
    {
        "scaling",
        "symmetry",
        "continuity",
        "bounds",
        "basis_gauge",
        "real_fourier",
    }
)
_EXPECTED_VALIDATION_OUTCOMES = frozenset({"accepted", "rejected"})
_EXPECTED_VALIDATION_REASONS = frozenset(
    {
        "none",
        "scientific_input_rejected",
        "numerical_control_rejected",
        "physical_size_rejected",
    }
)
_TETRAHEDRAL_BASIS_LABELS = (
    "spin_0",
    "spin_1",
    "spin_2",
    "spin_3",
)


@_seal_contract
@dataclass(frozen=True, init=False)
class CounterfactualPoint:
    schema_version: str
    domain_version: str
    adapter_id: str
    point_id: str
    run_nonce: str
    kind: str
    scientific_inputs: _FrozenJsonObject
    numerical_controls: _FrozenJsonObject
    problem_size: _FrozenJsonObject
    expected_validation: _FrozenJsonObject
    scientific_configuration: _FrozenJsonObject
    metamorphic_metadata: _FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, CounterfactualPoint)

    def __post_init__(self) -> None:
        if self.schema_version != "counterfactual_point_v1":
            raise _ContractError(
                "CounterfactualPoint has unknown schema_version"
            )
        if self.domain_version != _COUNTERFACTUAL_DOMAIN_VERSION:
            raise _ContractError(
                "CounterfactualPoint has unknown domain_version"
            )
        _identifier(self.adapter_id, "adapter_id")
        _identifier(self.point_id, "point_id")
        _require_sha256(self.run_nonce, "run_nonce")
        if self.kind not in _COUNTERFACTUAL_POINT_KINDS:
            raise _ContractError("CounterfactualPoint has unknown kind")
        for field_name in (
            "scientific_inputs",
            "numerical_controls",
            "problem_size",
            "expected_validation",
            "scientific_configuration",
            "metamorphic_metadata",
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_json(getattr(self, field_name), field_name),
            )
        expected = _exact_keys(
            self.expected_validation,
            ("outcome", "reason_code"),
            "expected_validation",
        )
        if expected["outcome"] not in _EXPECTED_VALIDATION_OUTCOMES:
            raise _ContractError("expected_validation has unknown outcome")
        if expected["reason_code"] not in _EXPECTED_VALIDATION_REASONS:
            raise _ContractError("expected_validation has unknown reason_code")
        if (expected["outcome"] == "accepted") != (
            expected["reason_code"] == "none"
        ):
            raise _ContractError("expected_validation outcome/reason mismatch")
        if (self.kind in {"canonical", "valid"}) != (
            expected["outcome"] == "accepted"
        ):
            raise _ContractError(
                "CounterfactualPoint kind/validation mismatch"
            )
        configuration_version = None
        if self.scientific_configuration:
            if "schema_version" not in self.scientific_configuration:
                raise _ContractError(
                    "scientific_configuration requires schema_version"
                )
            configuration_version = self.scientific_configuration[
                "schema_version"
            ]
            if configuration_version == "glt_scientific_configuration_v1":
                configuration = _exact_keys(
                    self.scientific_configuration,
                    (
                        "schema_version",
                        "representation",
                        "coordinates",
                        "gauge_phase_fraction",
                    ),
                    "scientific_configuration",
                )
                if configuration["representation"] not in {
                    "real_space", "fourier_space",
                }:
                    raise _ContractError(
                        "scientific_configuration has unknown representation"
                    )
                coordinates = _require_exact_tuple(
                    configuration["coordinates"],
                    "scientific_configuration.coordinates",
                )
                if len(coordinates) != 3 or any(
                    type(value) is not float
                    or not math.isfinite(value)
                    or value < -1.0
                    or value > 1.0
                    for value in coordinates
                ):
                    raise _ContractError(
                        "scientific_configuration coordinates are invalid"
                    )
                phase = configuration["gauge_phase_fraction"]
                if (
                    type(phase) is not float
                    or not math.isfinite(phase)
                    or phase < 0.0
                    or phase >= 1.0
                ):
                    raise _ContractError(
                        "scientific_configuration gauge phase is invalid"
                    )
            elif configuration_version == (
                "tetrahedral_basis_configuration_v1"
            ):
                configuration = _exact_keys(
                    self.scientific_configuration,
                    (
                        "schema_version",
                        "basis_labels",
                        "gauge_inverted",
                    ),
                    "scientific_configuration",
                )
                labels = _require_exact_tuple(
                    configuration["basis_labels"],
                    "scientific_configuration.basis_labels",
                )
                if (
                    len(labels) != len(_TETRAHEDRAL_BASIS_LABELS)
                    or set(labels) != set(_TETRAHEDRAL_BASIS_LABELS)
                ):
                    raise _ContractError(
                        "scientific_configuration basis labels are invalid"
                    )
                _require_bool(
                    configuration["gauge_inverted"],
                    "scientific_configuration.gauge_inverted",
                )
            else:
                raise _ContractError(
                    "scientific_configuration has unknown schema_version"
                )
        metadata = _exact_keys(
            self.metamorphic_metadata,
            ("relations",),
            "metamorphic_metadata",
        )
        relations = metadata["relations"]
        if type(relations) is not tuple:
            raise _ContractError(
                "metamorphic_metadata.relations must be an immutable tuple"
            )
        for relation in relations:
            if type(relation) is not _FrozenJsonObject:
                raise _ContractError("metamorphic relation must be a mapping")
            _exact_keys(
                relation,
                ("kind", "group"),
                "metamorphic relation",
            )
            relation_kind = relation.get("kind")
            if relation_kind not in _METAMORPHIC_RELATION_KINDS:
                raise _ContractError("metamorphic relation has unknown kind")
            _identifier(relation["group"], "metamorphic relation group")
        relation_kinds = tuple(
            relation["kind"] for relation in relations
        )
        has_tetrahedral_relations = (
            len(relation_kinds) == 2
            and set(relation_kinds) == {"basis_gauge", "symmetry"}
        )
        has_tetrahedral_configuration = configuration_version == (
            "tetrahedral_basis_configuration_v1"
        )
        if has_tetrahedral_configuration != has_tetrahedral_relations:
            raise _ContractError(
                "tetrahedral configuration/relation mismatch"
            )


_PRE_FREEZE_EVENT_NAMES = (
    "definition_and_provenance_validated",
    "scientific_closures_hashed",
    "scientific_policies_hashed",
    "infrastructure_partition_hashed",
    "runtime_snapshot_hashed",
    "capsules_hashed",
    "capability_preflight_hashed",
)
_FROZEN_HASH_FIELDS = frozenset(
    {
        "adapter_closure_sha256",
        "oracle_closure_sha256",
        "adapter_definition_sha256",
        "oracle_definition_sha256",
        "adapter_policy_sha256",
        "oracle_policy_sha256",
        "infrastructure_closure_sha256",
        "infrastructure_scan_sha256",
        "adapter_scan_sha256",
        "oracle_scan_sha256",
        "scanner_sha256",
        "dependency_partition_sha256",
        "runtime_snapshot_sha256",
        "adapter_capsule_sha256",
        "oracle_capsule_sha256",
        "worker_capsule_sha256",
    }
)


@_seal_contract
@dataclass(frozen=True, init=False)
class _FrozenHashSnapshot:
    schema_version: str
    audit_run_id: str
    adapter_definition: _FrozenJsonObject
    hash_material: _FrozenJsonObject
    capability_preflight: CapabilityPreflightReport
    infrastructure_command_hashes: _FrozenJsonObject
    frozen_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_contract(self, args, kwargs, _FrozenHashSnapshot)

    def __post_init__(self) -> None:
        if self.schema_version != "frozen_run_hashes_v1":
            raise _ContractError("frozen hashes have unknown schema_version")
        _require_text(self.audit_run_id, "audit_run_id")
        object.__setattr__(
            self,
            "adapter_definition",
            _snapshot_json(self.adapter_definition, "adapter_definition"),
        )
        object.__setattr__(
            self,
            "hash_material",
            _snapshot_json(self.hash_material, "hash_material"),
        )
        object.__setattr__(
            self,
            "capability_preflight",
            _snapshot_exact_record(
                self.capability_preflight,
                CapabilityPreflightReport,
                "capability_preflight",
            ),
        )
        object.__setattr__(
            self,
            "infrastructure_command_hashes",
            _snapshot_json(
                self.infrastructure_command_hashes,
                "infrastructure_command_hashes",
            ),
        )
        _require_sha256(self.frozen_sha256, "frozen_sha256")


def _snapshot_preflight_report(value):
    if type(value) is not CapabilityPreflightReport:
        raise _ContractError(
            "capability_preflight must be an exact CapabilityPreflightReport"
        )
    return CapabilityPreflightReport(
        **{
            name: getattr(value, name)
            for name in _record_field_names(CapabilityPreflightReport)
        }
    )


def _validated_frozen_hash_snapshot(value):
    if type(value) is not _FrozenHashSnapshot:
        raise _ContractError("frozen hashes snapshot mismatch or tamper")
    snapshot = _FrozenHashSnapshot(
        **{
            name: getattr(value, name)
            for name in _record_field_names(_FrozenHashSnapshot)
        }
    )
    payload = {
        "schema_version": snapshot.schema_version,
        "audit_run_id": snapshot.audit_run_id,
        "adapter_definition": snapshot.adapter_definition,
        "hash_material": snapshot.hash_material,
        "capability_preflight": {
            name: getattr(snapshot.capability_preflight, name)
            for name in _record_field_names(CapabilityPreflightReport)
        },
        "infrastructure_command_hashes": (
            snapshot.infrastructure_command_hashes
        ),
    }
    if snapshot.frozen_sha256 != _canonical_sha256(payload):
        raise _ContractError("frozen hashes snapshot mismatch or tamper")
    return snapshot


def _validated_ordering_events(value, expected_names):
    events = _require_exact_tuple(value, "ordered_events")
    if len(events) != len(expected_names):
        raise _ContractError("event ordering prerequisite mismatch")
    snapshots = []
    for index, (event, expected_name) in enumerate(zip(events, expected_names)):
        if type(event) is not EventRecord:
            raise _ContractError("ordered_events must contain exact EventRecord values")
        snapshot = EventRecord(event.sequence_number, event.event_name, event.details)
        if snapshot.sequence_number != index or snapshot.event_name != expected_name:
            raise _ContractError("event ordering prerequisite mismatch")
        snapshots.append(snapshot)
    return tuple(snapshots)


def _pre_freeze_event_details(payload):
    audit_run_id = payload["audit_run_id"]
    hashes = payload["hash_material"]
    return (
        {
            "audit_run_id": audit_run_id,
            "adapter_definition_sha256": hashes[
                "adapter_definition_sha256"
            ],
        },
        {
            "audit_run_id": audit_run_id,
            "adapter_closure_sha256": hashes["adapter_closure_sha256"],
            "oracle_closure_sha256": hashes["oracle_closure_sha256"],
        },
        {
            "audit_run_id": audit_run_id,
            "adapter_definition_sha256": hashes[
                "adapter_definition_sha256"
            ],
            "oracle_definition_sha256": hashes[
                "oracle_definition_sha256"
            ],
            "adapter_policy_sha256": hashes["adapter_policy_sha256"],
            "oracle_policy_sha256": hashes["oracle_policy_sha256"],
        },
        {
            "audit_run_id": audit_run_id,
            "infrastructure_closure_sha256": hashes[
                "infrastructure_closure_sha256"
            ],
            "infrastructure_scan_sha256": hashes[
                "infrastructure_scan_sha256"
            ],
            "adapter_scan_sha256": hashes["adapter_scan_sha256"],
            "oracle_scan_sha256": hashes["oracle_scan_sha256"],
            "scanner_sha256": hashes["scanner_sha256"],
            "dependency_partition_sha256": hashes[
                "dependency_partition_sha256"
            ],
        },
        {
            "audit_run_id": audit_run_id,
            "runtime_snapshot_sha256": hashes["runtime_snapshot_sha256"],
        },
        {
            "audit_run_id": audit_run_id,
            "adapter_capsule_sha256": hashes["adapter_capsule_sha256"],
            "oracle_capsule_sha256": hashes["oracle_capsule_sha256"],
            "worker_capsule_sha256": hashes["worker_capsule_sha256"],
        },
        {
            "audit_run_id": audit_run_id,
            "capability_preflight": payload["capability_preflight"],
            "capability_preflight_sha256": payload[
                "capability_preflight"
            ]["report_sha256"],
            "infrastructure_command_hashes": payload[
                "infrastructure_command_hashes"
            ],
        },
    )


def _validate_event_details_against_frozen_payload(events, payload):
    expected_details = _pre_freeze_event_details(payload)
    for index, expected in enumerate(expected_details):
        actual = events[index].details
        _exact_keys(
            actual,
            tuple(expected),
            f"ordered_events[{index}].details",
        )
        if _canonical_bytes(actual) != _canonical_bytes(expected):
            raise _ContractError("event details mismatch or tamper")


def _frozen_snapshot_payload(snapshot):
    return {
        "schema_version": snapshot.schema_version,
        "audit_run_id": snapshot.audit_run_id,
        "adapter_definition": snapshot.adapter_definition,
        "hash_material": snapshot.hash_material,
        "capability_preflight": {
            name: getattr(snapshot.capability_preflight, name)
            for name in _record_field_names(CapabilityPreflightReport)
        },
        "infrastructure_command_hashes": (
            snapshot.infrastructure_command_hashes
        ),
    }


def _frozen_hash_payload(
    definition,
    *,
    audit_run_id,
    hash_material,
    capability_preflight,
    infrastructure_command_hashes,
):
    validated_definition = _validate_adapter_definition(definition)
    definition_payload = _adapters.adapter_definition_to_frozen_json(
        validated_definition
    )
    hashes = _exact_keys(hash_material, _FROZEN_HASH_FIELDS, "hash_material")
    for field_name in hashes:
        _require_sha256(hashes[field_name], f"hash_material.{field_name}")
    definition_sha256 = _canonical_sha256(definition_payload)
    if hashes["adapter_definition_sha256"] != definition_sha256:
        raise _ContractError("adapter definition hash mismatch")

    preflight = _snapshot_preflight_report(capability_preflight)
    if preflight.audit_run_id != audit_run_id:
        raise _ContractError("capability preflight fresh nonce mismatch")
    if not preflight.available:
        raise _ContractError("capability preflight result is unavailable")
    preflight_body = {
        name: getattr(preflight, name)
        for name in _record_field_names(CapabilityPreflightReport)
        if name != "report_sha256"
    }
    if preflight.report_sha256 != _canonical_sha256(preflight_body):
        raise _ContractError("capability preflight report hash mismatch")

    command_hashes = _snapshot_json(
        infrastructure_command_hashes,
        "infrastructure_command_hashes",
    )
    if not command_hashes:
        raise _ContractError("infrastructure command hashes must be nonempty")
    for command_name in command_hashes:
        _identifier(command_name, "infrastructure command name")
        _require_sha256(
            command_hashes[command_name],
            f"infrastructure_command_hashes.{command_name}",
        )
    preflight_command_hashes = {}
    for command_name, identity in preflight.command_identities.items():
        identity_values = _exact_keys(
            identity,
            ("path", "version", "sha256"),
            "preflight command identity",
        )
        _require_text(identity_values["path"], "command path")
        _require_text(identity_values["version"], "command version")
        digest = identity_values["sha256"]
        preflight_command_hashes[command_name] = _require_sha256(
            digest,
            f"preflight.command_identities.{command_name}",
        )
    if _canonical_bytes(command_hashes) != _canonical_bytes(
        preflight_command_hashes
    ):
        raise _ContractError("infrastructure command hash mismatch")
    payload = {
        "schema_version": "frozen_run_hashes_v1",
        "audit_run_id": audit_run_id,
        "adapter_definition": definition_payload,
        "hash_material": hashes,
        "capability_preflight": {
            name: getattr(preflight, name)
            for name in _record_field_names(CapabilityPreflightReport)
        },
        "infrastructure_command_hashes": command_hashes,
    }
    return payload, preflight


def record_and_freeze_hashes(
    definition,
    *,
    audit_run_id,
    ordered_events,
    hash_material,
    capability_preflight,
    infrastructure_command_hashes,
    event_recorder,
    frozen_snapshot=None,
):
    """Freeze all pre-seed commitments or revalidate an existing freeze."""

    _require_text(audit_run_id, "audit_run_id")
    expected_events = _PRE_FREEZE_EVENT_NAMES
    if frozen_snapshot is not None:
        expected_events = (*expected_events, "frozen_hashes")
    events = _validated_ordering_events(ordered_events, expected_events)
    try:
        payload, preflight = _frozen_hash_payload(
            definition,
            audit_run_id=audit_run_id,
            hash_material=hash_material,
            capability_preflight=capability_preflight,
            infrastructure_command_hashes=infrastructure_command_hashes,
        )
        _validate_event_details_against_frozen_payload(events, payload)
        frozen_sha256 = _canonical_sha256(payload)
        candidate = _FrozenHashSnapshot(
            schema_version="frozen_run_hashes_v1",
            audit_run_id=audit_run_id,
            adapter_definition=payload["adapter_definition"],
            hash_material=payload["hash_material"],
            capability_preflight=preflight,
            infrastructure_command_hashes=payload[
                "infrastructure_command_hashes"
            ],
            frozen_sha256=frozen_sha256,
        )
    except _ContractError as error:
        if frozen_snapshot is not None:
            raise _ContractError(
                "post-freeze material changed or tampered"
            ) from error
        raise
    if frozen_snapshot is not None:
        stored = _validated_frozen_hash_snapshot(frozen_snapshot)
        if stored != candidate:
            raise _ContractError("post-freeze material changed or tampered")
        frozen_event = _exact_keys(
            events[-1].details,
            ("audit_run_id", "frozen_sha256"),
            "frozen hashes event details",
        )
        if (
            frozen_event["audit_run_id"] != stored.audit_run_id
            or frozen_event["frozen_sha256"] != stored.frozen_sha256
        ):
            raise _ContractError("frozen hashes event mismatch or tamper")
        return stored
    if not callable(event_recorder):
        raise _ContractError("event_recorder must be callable")
    event_recorder(
        "frozen_hashes",
        {
            "audit_run_id": audit_run_id,
            "frozen_sha256": candidate.frozen_sha256,
        },
    )
    return candidate


def acquire_run_seed(
    frozen_snapshot,
    *,
    ordered_events,
    random_bytes,
    event_recorder,
):
    """Acquire exactly 256 random bits only after the frozen-hashes event."""

    if type(frozen_snapshot) is not _FrozenHashSnapshot:
        raise _ContractError("random acquisition requires frozen hashes ordering")
    frozen = _validated_frozen_hash_snapshot(frozen_snapshot)
    events = _validated_ordering_events(
        ordered_events, (*_PRE_FREEZE_EVENT_NAMES, "frozen_hashes")
    )
    _validate_event_details_against_frozen_payload(
        events, _frozen_snapshot_payload(frozen)
    )
    frozen_event = _exact_keys(
        events[-1].details,
        ("audit_run_id", "frozen_sha256"),
        "frozen hashes event details",
    )
    if (
        frozen_event["audit_run_id"] != frozen.audit_run_id
        or frozen_event["frozen_sha256"] != frozen.frozen_sha256
    ):
        raise _ContractError("frozen hashes event mismatch or tamper")
    if not callable(random_bytes) or not callable(event_recorder):
        raise _ContractError("random provider and event recorder must be callable")
    seed = random_bytes(32)
    if type(seed) is not bytes or len(seed) != 32:
        raise _ContractError("run seed must be exactly 32 bytes")
    event_recorder(
        "random_seed_acquired",
        {
            "audit_run_id": frozen.audit_run_id,
            "seed_sha256": hashlib.sha256(seed).hexdigest(),
        },
    )
    return seed


def _counterfactual_digest(
    seed,
    adapter_id,
    point_kind,
    point_index,
    counter,
):
    message = (
        _COUNTERFACTUAL_DOMAIN_VERSION.encode("ascii")
        + b"\0"
        + adapter_id.encode("ascii")
        + b"\0"
        + point_kind.encode("ascii")
        + b"\0"
        + point_index.to_bytes(8, "big")
        + counter.to_bytes(8, "big")
    )
    return hmac.new(seed, message, hashlib.sha256).digest()


def _counterfactual_unit_interval(
    seed,
    adapter_id,
    point_kind,
    point_index,
    counter,
):
    digest = _counterfactual_digest(
        seed, adapter_id, point_kind, point_index, counter
    )
    numerator = int.from_bytes(digest[:8], "big")
    return numerator / float(1 << 64)


def _counterfactual_rule_kind(definition, field_name):
    rule = definition.counterfactual_domain.valid_rules.get(field_name)
    if type(rule) is _FrozenJsonObject:
        return rule.get("kind")
    return None


def _counterfactual_valid_value(
    schema,
    rule_kind,
    unit_value,
    variant,
    field_name,
):
    if schema.kind == "string":
        if field_name.endswith("_b"):
            return "axis_b"
        return "axis_a"
    if schema.kind == "boolean":
        return True
    if schema.kind == "integer":
        if rule_kind == "tetrahedral_positive_integer":
            return 4
        lower = schema.lower if schema.lower is not None else 1
        value = int(lower) + variant
        if schema.upper is not None:
            value = min(value, int(schema.upper))
        return value
    if schema.kind == "number":
        if schema.lower is not None and schema.upper is not None:
            fraction = 0.2 + 0.6 * unit_value
            return schema.lower + (schema.upper - schema.lower) * fraction
        if schema.lower is not None:
            offset = 0.5 + unit_value + 0.25 * variant
            return schema.lower + offset
        if schema.upper is not None:
            return schema.upper - (0.5 + unit_value + 0.25 * variant)
        magnitude = 0.5 + unit_value + 0.25 * variant
        if rule_kind in {"finite_nonzero", "finite_product_state_regime"}:
            return magnitude if unit_value >= 0.5 else -magnitude
        return magnitude if unit_value >= 0.5 else -magnitude
    if schema.kind == "list":
        return ()
    if schema.kind == "object":
        return {
            name: _counterfactual_valid_value(
                child,
                None,
                unit_value,
                variant,
                name,
            )
            for name, child in schema.properties
        }
    raise _ContractError("counterfactual schema kind is unsupported")


def _counterfactual_inputs(definition, seed, point_index, variant):
    values = {}
    domain_digest = hashlib.sha256(
        _canonical_bytes(
            {
                "valid_rules": definition.counterfactual_domain.valid_rules,
                "invalid_rules": definition.counterfactual_domain.invalid_rules,
            }
        )
    ).digest()
    domain_counter = int.from_bytes(domain_digest[:8], "big")
    for counter, (field_name, schema) in enumerate(
        definition.scientific_input_schema.properties, start=1
    ):
        unit_value = _counterfactual_unit_interval(
            seed,
            definition.adapter_id,
            "valid",
            point_index,
            (domain_counter + counter) % (1 << 64),
        )
        values[field_name] = _counterfactual_valid_value(
            schema,
            _counterfactual_rule_kind(definition, field_name),
            unit_value,
            variant,
            field_name,
        )
    for field_name, rule in definition.counterfactual_domain.valid_rules.items():
        if rule["kind"] != "finite_product_state_regime":
            continue
        reference = values[rule["reference_field"]]
        maximum_ratio = rule["maximum_absolute_ratio"]
        authored = values[field_name]
        fraction = abs(authored) / (1.0 + abs(authored))
        sign = -1.0 if authored < 0.0 else 1.0
        values[field_name] = sign * maximum_ratio * reference * fraction
    return values


def _counterfactual_canonical_inputs(definition):
    values = {}
    for field_name, schema in definition.scientific_input_schema.properties:
        values[field_name] = _counterfactual_valid_value(
            schema,
            _counterfactual_rule_kind(definition, field_name),
            0.75,
            0,
            field_name,
        )
    for field_name, rule in definition.counterfactual_domain.valid_rules.items():
        if rule["kind"] != "finite_product_state_regime":
            continue
        reference = values[rule["reference_field"]]
        maximum_ratio = rule["maximum_absolute_ratio"]
        authored = values[field_name]
        fraction = abs(authored) / (1.0 + abs(authored))
        sign = -1.0 if authored < 0.0 else 1.0
        values[field_name] = sign * maximum_ratio * reference * fraction
    return values


def _counterfactual_controls(definition, seed, point_index):
    values = {}
    for counter, (field_name, schema) in enumerate(
        definition.numerical_control_schema.properties, start=64
    ):
        unit_value = _counterfactual_unit_interval(
            seed,
            definition.adapter_id,
            "valid",
            point_index,
            counter,
        )
        if schema.kind == "integer" and (
            "iterations" in field_name or "subintervals" in field_name
        ):
            lower = int(schema.lower) if schema.lower is not None else 1
            value = max(lower, 64) + int(32.0 * unit_value)
            if schema.upper is not None:
                value = min(value, int(schema.upper))
            values[field_name] = value
        elif schema.kind == "number" and "threshold" in field_name:
            lower = float(schema.lower) if schema.lower is not None else 0.0
            increment = 1e-10 * (1.0 + unit_value)
            value = lower + increment
            if schema.upper is not None:
                value = min(value, float(schema.upper))
            values[field_name] = value
        else:
            values[field_name] = _counterfactual_valid_value(
                schema, None, unit_value, 0, field_name
            )
    return values


def _counterfactual_refined_controls(definition, level):
    values = {}
    multiplier = 1 << level
    for field_name, schema in definition.numerical_control_schema.properties:
        if schema.kind == "integer":
            lower = int(schema.lower) if schema.lower is not None else 1
            base = max(lower, 16)
            value = base * multiplier
            if schema.upper is not None:
                value = min(value, int(schema.upper))
        else:
            lower = schema.lower if schema.lower is not None else 0.0
            value = lower + 0.125 / multiplier
            if schema.upper is not None:
                value = min(value, schema.upper)
        values[field_name] = value
    return values


def _counterfactual_declared_sizes(definition):
    policy = definition.problem_size_policy
    if policy.kind == "not_applicable":
        return ({},)
    if policy.kind == "fixed_local":
        return (_adapters.thaw_json(policy.fixed_sizes),)
    allowed = _adapters.thaw_json(policy.allowed_sizes)
    sequence_lengths = [
        len(value) for value in allowed.values() if type(value) is list
    ]
    if not sequence_lengths or min(sequence_lengths) < 2:
        raise _ContractError(
            "scalable counterfactual policy requires two declared sizes"
        )
    sizes = []
    for index in range(2):
        sizes.append(
            {
                key: (value[index] if type(value) is list else value)
                for key, value in allowed.items()
            }
        )
    return tuple(sizes)


def _counterfactual_invalid_size(definition):
    declared = _counterfactual_declared_sizes(definition)[0]
    invalid = dict(declared)
    for key in sorted(invalid):
        value = invalid[key]
        if type(value) is int:
            invalid[key] = value + 1
            return invalid
        if type(value) is list and value and type(value[0]) is int:
            changed = list(value)
            changed[0] += 1
            invalid[key] = changed
            return invalid
    invalid["undeclared_size"] = 1
    return invalid


def _counterfactual_invalid_inputs(definition, valid_inputs):
    values = dict(valid_inputs)
    boundary_by_rule = {
        "nonpositive_or_nonfinite": 0,
        "zero_or_nonfinite": 0,
        "nontetrahedral_or_nonpositive": 3,
        "nonfinite": 0,
        "outside_product_state_regime_or_nonfinite": 0,
    }
    invalid_rules = definition.counterfactual_domain.invalid_rules
    for field_name, schema in definition.scientific_input_schema.properties:
        if schema.kind not in {"number", "integer"}:
            continue
        rule = invalid_rules[field_name]
        rule_kind = rule["kind"]
        if rule_kind not in boundary_by_rule:
            continue
        boundary = boundary_by_rule[rule_kind]
        values[field_name] = (
            boundary if schema.kind == "integer" else float(boundary)
        )
        return values
    raise _ContractError(
        "counterfactual invalid_rules have no numeric boundary"
    )


def _counterfactual_invalid_controls(definition, valid_controls):
    values = dict(valid_controls)
    field_name, schema = definition.numerical_control_schema.properties[0]
    if schema.kind == "integer":
        lower = int(schema.lower) if schema.lower is not None else 0
        values[field_name] = lower - 1
    else:
        lower = schema.lower if schema.lower is not None else 0.0
        values[field_name] = lower - 1.0
    return values


def _counterfactual_domain_inputs_are_valid(definition, inputs):
    for field_name, rule in definition.counterfactual_domain.valid_rules.items():
        if field_name in {
            "physical_size_rule",
            "problem_size_rule",
        }:
            continue
        rule_kind = rule["kind"]
        value = inputs[field_name]
        if rule_kind == "strictly_positive_finite":
            valid = type(value) in {int, float} and value > 0
        elif rule_kind == "finite_nonzero":
            valid = type(value) in {int, float} and value != 0
        elif rule_kind == "tetrahedral_positive_integer":
            valid = type(value) is int and value == 4
        elif rule_kind == "normalized_supported_direction":
            valid = value in {"axis_a", "axis_b"}
        elif rule_kind == "normalized_distinct_direction":
            supported_directions = tuple(
                inputs[candidate_name]
                for candidate_name, candidate_rule in (
                    definition.counterfactual_domain.valid_rules.items()
                )
                if candidate_rule["kind"] == (
                    "normalized_supported_direction"
                )
            )
            valid = (
                value in {"axis_a", "axis_b"}
                and supported_directions
                and all(
                    value != direction for direction in supported_directions
                )
            )
        elif rule_kind == "finite_product_state_regime":
            reference = inputs[rule["reference_field"]]
            maximum_ratio = rule["maximum_absolute_ratio"]
            valid = (
                type(value) in {int, float}
                and math.isfinite(value)
                and type(reference) in {int, float}
                and math.isfinite(reference)
                and reference > 0.0
                and abs(value) <= maximum_ratio * reference
            )
        elif rule_kind == "finite":
            valid = type(value) in {int, float} and math.isfinite(value)
        else:
            raise _ContractError(
                "counterfactual valid_rules has an unsupported field rule"
            )
        if not valid:
            return False
    return True


def _counterfactual_validation_reason(definition, point):
    validated = _validate_adapter_definition(definition)
    if type(point) is not CounterfactualPoint:
        raise _ContractError(
            "counterfactual validation requires an exact point"
        )
    if point.adapter_id != validated.adapter_id:
        raise _ContractError("counterfactual point adapter mismatch")
    declared_sizes = _counterfactual_declared_sizes(validated)
    if not any(
        _canonical_bytes(point.problem_size) == _canonical_bytes(size)
        for size in declared_sizes
    ):
        return "physical_size_rejected"
    try:
        inputs = _validate_inputs(validated, point.scientific_inputs)
    except _ContractError:
        return "scientific_input_rejected"
    if not _counterfactual_domain_inputs_are_valid(validated, inputs):
        return "scientific_input_rejected"
    configuration = point.scientific_configuration
    configuration_version = (
        configuration["schema_version"] if configuration else None
    )
    has_tetrahedral_rule = any(
        rule["kind"] == "tetrahedral_positive_integer"
        for rule in validated.counterfactual_domain.valid_rules.values()
    )
    if point.kind != "valid":
        configuration_is_valid = not configuration
    elif validated.backend_kind == "glt_fourier":
        configuration_is_valid = configuration_version == (
            "glt_scientific_configuration_v1"
        )
    elif has_tetrahedral_rule:
        configuration_is_valid = configuration_version == (
            "tetrahedral_basis_configuration_v1"
        )
    else:
        configuration_is_valid = not configuration
    if not configuration_is_valid:
        return "scientific_input_rejected"
    try:
        controls = _validate_controls(
            validated, point.numerical_controls
        )
    except _ContractError:
        return "numerical_control_rejected"
    if controls != point.numerical_controls:
        raise _ContractError("counterfactual controls snapshot mismatch")
    return "none"


def _counterfactual_relations(definition, scientific_configuration):
    configuration_version = (
        scientific_configuration["schema_version"]
        if scientific_configuration
        else None
    )
    backend_kind = definition.backend_kind
    size_kind = definition.problem_size_policy.kind
    if configuration_version == "tetrahedral_basis_configuration_v1":
        kinds = ("basis_gauge", "symmetry")
    elif backend_kind == "analytic":
        kinds = ("scaling", "continuity", "bounds")
    elif backend_kind in {"enumeration", "dense_ed"}:
        if size_kind == "fixed_local":
            kinds = ("scaling", "basis_gauge", "symmetry")
        else:
            kinds = ("scaling", "continuity")
    elif backend_kind == "glt_fourier":
        kinds = ("real_fourier", "symmetry")
    else:
        kinds = ("continuity", "bounds", "scaling")
    return tuple(
        {"kind": kind, "group": "counterfactual_probe"}
        for kind in kinds
    )


def _counterfactual_scientific_configuration(
    definition,
    seed,
    point_index,
):
    configuration_index = point_index // 2
    coordinates = tuple(
        2.0 * _counterfactual_unit_interval(
            seed,
            definition.adapter_id,
            "valid",
            configuration_index,
            128 + coordinate_index,
        ) - 1.0
        for coordinate_index in range(3)
    )
    phase = _counterfactual_unit_interval(
        seed,
        definition.adapter_id,
        "valid",
        configuration_index,
        131,
    )
    return {
        "schema_version": "glt_scientific_configuration_v1",
        "representation": (
            "real_space" if point_index % 2 == 0 else "fourier_space"
        ),
        "coordinates": coordinates,
        "gauge_phase_fraction": phase,
    }


def _counterfactual_tetrahedral_basis_configuration(
    definition,
    seed,
    point_index,
):
    ranked_labels = [
        label
        for _digest, label in sorted(
            (
                _counterfactual_digest(
                    seed,
                    definition.adapter_id,
                    "valid",
                    0,
                    144 + int(label[-1]),
                ),
                label,
            )
            for label in _TETRAHEDRAL_BASIS_LABELS
        )
    ]
    rotation = point_index % len(ranked_labels)
    basis_labels = tuple(
        ranked_labels[rotation:] + ranked_labels[:rotation]
    )
    gauge_inverted = bool(
        _counterfactual_digest(
            seed,
            definition.adapter_id,
            "valid",
            point_index,
            148,
        )[0] & 1
    )
    return {
        "schema_version": "tetrahedral_basis_configuration_v1",
        "basis_labels": basis_labels,
        "gauge_inverted": gauge_inverted,
    }


def _counterfactual_point(
    definition,
    seed,
    kind,
    point_index,
    scientific_inputs,
    numerical_controls,
    problem_size,
    expected_validation,
    scientific_configuration,
    metamorphic_metadata,
):
    nonce = _counterfactual_digest(
        seed, definition.adapter_id, kind, point_index, 0
    ).hex()
    return CounterfactualPoint(
        schema_version="counterfactual_point_v1",
        domain_version=_COUNTERFACTUAL_DOMAIN_VERSION,
        adapter_id=definition.adapter_id,
        point_id=f"{definition.adapter_id}_{kind}_{point_index}",
        run_nonce=nonce,
        kind=kind,
        scientific_inputs=scientific_inputs,
        numerical_controls=numerical_controls,
        problem_size=problem_size,
        expected_validation=expected_validation,
        scientific_configuration=scientific_configuration,
        metamorphic_metadata=metamorphic_metadata,
    )


def derive_counterfactual_points(definition, seed):
    """Derive answer-free probes with a versioned HMAC/SHA-256 stream."""

    if type(seed) is not bytes or len(seed) != 32:
        raise _ContractError("counterfactual seed must be exactly 32 bytes")
    validated = _validate_adapter_definition(definition)
    sizes = _counterfactual_declared_sizes(validated)
    accepted = {"outcome": "accepted", "reason_code": "none"}
    points = [
        _counterfactual_point(
            validated,
            seed,
            "canonical",
            0,
            _counterfactual_canonical_inputs(validated),
            _counterfactual_controls(validated, seed, 0),
            sizes[0],
            accepted,
            {},
            {"relations": ()},
        )
    ]

    backend_kind = validated.backend_kind
    size_kind = validated.problem_size_policy.kind
    if backend_kind == "analytic":
        valid_specs = tuple((index, sizes[0]) for index in range(3))
    elif backend_kind in {"enumeration", "dense_ed"}:
        if size_kind == "fixed_local":
            valid_specs = tuple((index, sizes[0]) for index in range(3))
        else:
            valid_specs = tuple(
                (size_index * 2 + repetition, size)
                for size_index, size in enumerate(sizes)
                for repetition in range(2)
            )
    elif backend_kind == "glt_fourier":
        valid_specs = tuple(
            (group_index * 2 + configuration_index, sizes[0])
            for group_index in range(3)
            for configuration_index in range(2)
        )
    else:
        valid_specs = tuple((index, sizes[0]) for index in range(3))

    iterative_inputs = None
    for point_index, problem_size in valid_specs:
        if backend_kind == "glt_fourier":
            input_index = point_index // 2
        elif backend_kind == "iterative_numeric":
            input_index = 0
        else:
            input_index = point_index
        scientific_inputs = _counterfactual_inputs(
            validated, seed, input_index, input_index + 1
        )
        if backend_kind == "iterative_numeric":
            if iterative_inputs is None:
                iterative_inputs = scientific_inputs
            scientific_inputs = iterative_inputs
            numerical_controls = _counterfactual_refined_controls(
                validated, point_index
            )
        else:
            control_index = (
                input_index
                if backend_kind == "glt_fourier"
                else point_index
            )
            numerical_controls = _counterfactual_controls(
                validated, seed, control_index
            )
        scientific_configuration = {}
        if backend_kind == "glt_fourier":
            scientific_configuration = _counterfactual_scientific_configuration(
                validated, seed, point_index
            )
        elif any(
            rule["kind"] == "tetrahedral_positive_integer"
            for rule in validated.counterfactual_domain.valid_rules.values()
        ):
            scientific_configuration = (
                _counterfactual_tetrahedral_basis_configuration(
                    validated, seed, point_index
                )
            )
        metadata = {
            "relations": _counterfactual_relations(
                validated, scientific_configuration
            )
        }
        points.append(
            _counterfactual_point(
                validated,
                seed,
                "valid",
                point_index,
                scientific_inputs,
                numerical_controls,
                problem_size,
                accepted,
                scientific_configuration,
                metadata,
            )
        )

    invalid_inputs = _counterfactual_inputs(validated, seed, 7, 1)
    invalid_controls = _counterfactual_controls(validated, seed, 7)
    invalid_size = sizes[0]
    if backend_kind == "iterative_numeric":
        invalid_controls = _counterfactual_invalid_controls(
            validated,
            _counterfactual_refined_controls(validated, 0),
        )
        invalid_reason = "numerical_control_rejected"
    elif size_kind in {"fixed_local", "scalable_same_observable"}:
        invalid_size = _counterfactual_invalid_size(validated)
        invalid_reason = "physical_size_rejected"
    else:
        invalid_inputs = _counterfactual_invalid_inputs(
            validated, invalid_inputs
        )
        invalid_reason = "scientific_input_rejected"
    points.append(
        _counterfactual_point(
            validated,
            seed,
            "invalid",
            0,
            invalid_inputs,
            invalid_controls,
            invalid_size,
            {"outcome": "rejected", "reason_code": invalid_reason},
            {},
            {"relations": ()},
        )
    )
    frozen_points = tuple(points)
    for point in frozen_points:
        observed_reason = _counterfactual_validation_reason(
            validated, point
        )
        if observed_reason != point.expected_validation["reason_code"]:
            raise _ContractError(
                "counterfactual validation expectation mismatch"
            )
    return frozen_points


def _task12_validated_local_result_values(definition, value):
    validated_definition = _validate_adapter_definition(definition)
    validated_result = _adapters.validate_local_observable_result(
        validated_definition, value
    )
    result_items = _static_scan_exact_frozen_items(
        validated_result,
        "validated local result",
        _STATIC_SCAN_NODE_LIMIT,
    )
    return validated_definition, validated_result, dict(result_items)


def collect_backend_diagnostics(definition, local_result):
    """Bind validated backend identities and operation data to one hash."""

    validated, _result, values = _task12_validated_local_result_values(
        definition, local_result
    )
    payload = {
        "backend_kind": validated.backend_kind,
        "backend_diagnostics": values["backend_diagnostics"],
        "operation_counts_or_sizes": values["operation_counts_or_sizes"],
    }
    payload["diagnostics_sha256"] = _canonical_sha256(payload)
    return _snapshot_json(payload, "collected backend diagnostics")


def _dense_ed_expected_dimension(problem_size):
    if "lattice_shapes" in problem_size:
        dimension = 1
        for extent in problem_size["lattice_shapes"]:
            if type(extent) is not int or extent <= 0:
                return None
            dimension *= extent
        return 1 << dimension
    if "periodic_chain_lengths" in problem_size:
        site_count = problem_size["periodic_chain_lengths"]
        if type(site_count) is not int or site_count <= 0:
            return None
        return 1 << site_count
    if "spin_counts" in problem_size:
        site_count = problem_size["spin_counts"]
        if type(site_count) is not int or site_count <= 0:
            return None
        return 1 << site_count
    if "spin_count" not in problem_size:
        return None
    site_count = problem_size["spin_count"]
    if type(site_count) is not int or site_count <= 0:
        return None
    local_dimension = 2
    if "spin_quantum_number" in problem_size:
        spin = problem_size["spin_quantum_number"]
        if type(spin) not in {int, float} or spin < 0.0:
            return None
        local_dimension = int(round(2.0 * spin + 1.0))
    return local_dimension**site_count


def _dense_ed_one_matrix_diagnostics_satisfied(diagnostics, expected_dimension):
    diagnostics = dict(
        _static_scan_exact_frozen_items(
            diagnostics,
            "dense ED matrix diagnostics",
            9,
        )
    )
    expected = {
        "basis_phase_radians",
        "basis_similarity_residual",
        "dimension",
        "matrix_norm",
        "hermiticity_norm",
        "maximum_eigenpair_residual",
        "orthogonality_residual",
        "basis_phase_radians",
        "basis_similarity_residual",
        "trace",
        "eigensolver",
    }
    if set(diagnostics) != expected:
        return False
    if diagnostics["dimension"] != expected_dimension:
        return False
    if diagnostics["eigensolver"] != "numpy.linalg.eigh":
        return False
    for name in (
        "hermiticity_norm",
        "matrix_norm",
        "maximum_eigenpair_residual",
        "orthogonality_residual",
        "trace",
    ):
        value = diagnostics[name]
        if type(value) not in {int, float} or not math.isfinite(value):
            return False
    if (
        diagnostics["matrix_norm"] < 0.0
        or diagnostics["basis_phase_radians"] < 0.0
        or diagnostics["basis_phase_radians"] >= math.pi / 2.0
        or diagnostics["basis_similarity_residual"] < 0.0
        or diagnostics["hermiticity_norm"] < 0.0
        or diagnostics["maximum_eigenpair_residual"] < 0.0
        or diagnostics["orthogonality_residual"] < 0.0
    ):
        return False
    scale = max(1.0, diagnostics["matrix_norm"])
    return (
        diagnostics["hermiticity_norm"] <= 1e-12 * scale
        and diagnostics["maximum_eigenpair_residual"] <= 1e-10 * scale
        and diagnostics["orthogonality_residual"] <= 1e-10
        and diagnostics["basis_similarity_residual"] <= 1e-10 * scale
    )


def _dense_ed_matrix_diagnostics_satisfied(definition, proof_inputs):
    proof_values = dict(
        _static_scan_exact_frozen_items(
            proof_inputs,
            "dense ED proof inputs",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    if "matrix_diagnostics_by_size" not in proof_values:
        return False
    rows = proof_values["matrix_diagnostics_by_size"]
    declared_sizes = _counterfactual_declared_sizes(definition)
    if type(rows) is not tuple or len(rows) != len(declared_sizes):
        return False
    for row, declared_size in zip(rows, declared_sizes):
        row_values = dict(
            _static_scan_exact_frozen_items(
                row, "dense ED size diagnostic row", 2
            )
        )
        if set(row_values) != {"problem_size", "diagnostics"}:
            return False
        observed_size = _adapters.thaw_json(row_values["problem_size"])
        if observed_size != declared_size:
            return False
        expected_dimension = _dense_ed_expected_dimension(declared_size)
        if expected_dimension is None or not (
            _dense_ed_one_matrix_diagnostics_satisfied(
                row_values["diagnostics"], expected_dimension
            )
        ):
            return False
    return True


def _dense_ed_method_evidence_satisfied(definition, proof_inputs):
    requirements = dict(
        _static_scan_exact_frozen_items(
            definition.convergence_contract.requirements,
            "dense ED convergence requirements",
            16,
        )
    )
    method = requirements.get("dense_ed_proof_kind")
    if method is None:
        return True
    proof_values = dict(
        _static_scan_exact_frozen_items(
            proof_inputs,
            "dense ED method proof inputs",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    declared_sizes = _counterfactual_declared_sizes(definition)
    rows = proof_values.get("matrix_diagnostics_by_size")
    if type(rows) is not tuple or len(rows) != len(declared_sizes):
        return False
    scales = []
    for row in rows:
        row_values = dict(
            _static_scan_exact_frozen_items(
                row, "dense ED method size row", 2
            )
        )
        diagnostics = dict(
            _static_scan_exact_frozen_items(
                row_values["diagnostics"],
                "dense ED method diagnostics",
                9,
            )
        )
        scales.append(max(1.0, diagnostics["matrix_norm"]))
    if method == "ground_space_covering":
        multiplicities = proof_values.get("ground_space_multiplicities")
        ranks = proof_values.get("projected_covering_ranks")
        residual_rows = proof_values.get(
            "covering_eigen_residuals_by_size"
        )
        if (
            type(multiplicities) is not tuple
            or type(ranks) is not tuple
            or type(residual_rows) is not tuple
            or len(multiplicities) != len(declared_sizes)
            or len(ranks) != len(declared_sizes)
            or len(residual_rows) != len(declared_sizes)
        ):
            return False
        for index, residuals in enumerate(residual_rows):
            if multiplicities[index] != 2 or ranks[index] != 2:
                return False
            if type(residuals) is not tuple or len(residuals) != 2:
                return False
            for residual in residuals:
                if (
                    type(residual) not in {int, float}
                    or not math.isfinite(residual)
                    or residual < 0.0
                    or residual > 1e-10 * scales[index]
                ):
                    return False
        return True
    if method == "linked_cell_product_ground_state":
        cancellation = proof_values.get(
            "linked_cell_cancellation_residuals"
        )
        ground_energy = proof_values.get(
            "product_ground_energy_residuals"
        )
        bond_counts = proof_values.get("interdimer_bond_counts")
        if (
            type(cancellation) is not tuple
            or type(ground_energy) is not tuple
            or type(bond_counts) is not tuple
            or len(cancellation) != len(declared_sizes)
            or len(ground_energy) != len(declared_sizes)
            or len(bond_counts) != len(declared_sizes)
        ):
            return False
        for index, declared_size in enumerate(declared_sizes):
            dimer_count = declared_size.get("orthogonal_dimer_counts")
            if (
                type(dimer_count) is not int
                or bond_counts[index] != 2 * (dimer_count - 1)
            ):
                return False
            for residual in (cancellation[index], ground_energy[index]):
                if (
                    type(residual) not in {int, float}
                    or not math.isfinite(residual)
                    or residual < 0.0
                    or residual > 1e-10 * scales[index]
                ):
                    return False
        return True
    return False


def interpret_output_proofs(definition, local_result):
    """Interpret only definition-bound generic output proof bindings."""

    validated, _result, values = _task12_validated_local_result_values(
        definition, local_result
    )
    fields = dict(
        _static_scan_exact_frozen_items(
            values["fields"], "validated local fields", _STATIC_SCAN_NODE_LIMIT
        )
    )
    units = dict(
        _static_scan_exact_frozen_items(
            values["units"], "validated local units", _STATIC_SCAN_NODE_LIMIT
        )
    )
    uncertainty = dict(
        _static_scan_exact_frozen_items(
            values["uncertainty"],
            "validated local uncertainty",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    convergence_values = dict(
        _static_scan_exact_frozen_items(
            values["raw_convergence_evidence"],
            "validated raw convergence evidence",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    certificate_values = dict(
        _static_scan_exact_frozen_items(
            convergence_values["certificate"],
            "validated convergence certificate",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    proof_inputs = dict(
        _static_scan_exact_frozen_items(
            certificate_values["proof_inputs"],
            "validated raw output proof inputs",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    proof_rows = {}
    for selector, binding in validated.output_schema:
        derived_value = fields[selector]
        if binding.proof_kind in {
            "all_residuals_within_bound_boolean",
            "no_finite_crossing_boolean",
            "no_finite_crossing_zero_limit",
        }:
            if binding.proof_kind == "all_residuals_within_bound_boolean":
                expected_keys = {
                    "candidate_values",
                    "residuals",
                    "residual_bound",
                    "lower_bound",
                    "certificate_checks_total",
                    "certificate_checks_satisfied",
                }
                supplied_keys = set(proof_inputs)
                if validated.backend_kind == "dense_ed":
                    expected_keys.add("matrix_diagnostics_by_size")
                if supplied_keys != expected_keys:
                    raise _ContractError(
                        "outer output proof evidence is malformed"
                    )
                if validated.backend_kind == "dense_ed" and not (
                    _dense_ed_matrix_diagnostics_satisfied(
                        validated,
                        certificate_values["proof_inputs"]
                    )
                ):
                    raise _ContractError(
                        "outer dense ED matrix evidence is malformed"
                    )
                candidate_values = proof_inputs["candidate_values"]
                residuals = proof_inputs["residuals"]
                if (
                    type(candidate_values) is not tuple
                    or type(residuals) is not tuple
                    or not candidate_values
                    or len(candidate_values) != len(residuals)
                ):
                    raise _ContractError(
                        "outer output proof evidence is malformed"
                    )
                lower_bound = proof_inputs["lower_bound"]
                residual_bound = proof_inputs["residual_bound"]
                checks_total = proof_inputs["certificate_checks_total"]
                checks_satisfied = proof_inputs[
                    "certificate_checks_satisfied"
                ]
                minimum = min(candidate_values)
                proof_satisfied = (
                    type(checks_total) is int
                    and type(checks_satisfied) is int
                    and checks_total > 0
                    and checks_satisfied == checks_total
                    and minimum == lower_bound
                )
                for index in range(len(candidate_values)):
                    if (
                        candidate_values[index] == minimum
                        and residuals[index] > residual_bound
                    ):
                        proof_satisfied = False
                derived_value = proof_satisfied
            else:
                expected_keys = {
                    "finite_parameter_separations",
                    "analytic_separation",
                    "identity_separation",
                    "limit_inverse_temperature_samples",
                    "limit_temperature_samples",
                }
                if set(proof_inputs) != expected_keys:
                    raise _ContractError(
                        "outer output proof evidence is malformed"
                    )
                separations = proof_inputs[
                    "finite_parameter_separations"
                ]
                analytic = proof_inputs["analytic_separation"]
                identity = proof_inputs["identity_separation"]
                inverse_samples = proof_inputs[
                    "limit_inverse_temperature_samples"
                ]
                temperature_samples = proof_inputs[
                    "limit_temperature_samples"
                ]
                limit_proved = (
                    type(inverse_samples) is tuple
                    and type(temperature_samples) is tuple
                    and len(inverse_samples) >= 3
                    and len(inverse_samples) == len(temperature_samples)
                )
                if limit_proved:
                    for index in range(len(inverse_samples)):
                        if (
                            inverse_samples[index] <= 0.0
                            or temperature_samples[index] <= 0.0
                            or abs(
                                inverse_samples[index]
                                * temperature_samples[index]
                                - 1.0
                            )
                            > 1e-12
                        ):
                            limit_proved = False
                    for index in range(1, len(inverse_samples)):
                        if (
                            inverse_samples[index]
                            <= inverse_samples[index - 1]
                            or temperature_samples[index]
                            >= temperature_samples[index - 1]
                        ):
                            limit_proved = False
                proof_satisfied = (
                    type(separations) is tuple
                    and bool(separations)
                    and all(value > 0.0 for value in separations)
                    and analytic > 0.0
                    and identity > 0.0
                    and abs(analytic - identity)
                    <= 1e-12 * max(1.0, abs(identity))
                    and limit_proved
                )
                if binding.proof_kind == "no_finite_crossing_boolean":
                    derived_value = not proof_satisfied
                else:
                    if not proof_satisfied:
                        raise _ContractError(
                            "outer zero-limit proof is incomplete"
                        )
                    derived_value = 0.0
            if fields[selector] != derived_value:
                raise _ContractError("outer-derived output proof mismatch")
        proof_rows[selector] = {
            "raw_field": binding.raw_field,
            "proof_kind": binding.proof_kind,
            "value": derived_value,
            "units": units[selector],
            "uncertainty": uncertainty[selector],
        }
    payload = {
        "selected_fields": tuple(validated.output_schema.selector_fields),
        "proofs": proof_rows,
    }
    payload["proof_sha256"] = _canonical_sha256(payload)
    return _snapshot_json(payload, "interpreted output proofs")


def _task12_nonincreasing(values):
    return all(
        later <= earlier for earlier, later in zip(values, values[1:])
    )


def derive_convergence_decision(definition, local_result):
    """Derive convergence from raw samples, never a worker boolean."""

    validated, _result, values = _task12_validated_local_result_values(
        definition, local_result
    )
    raw = values["raw_convergence_evidence"]
    raw_values = dict(
        _static_scan_exact_frozen_items(
            raw, "raw convergence evidence", _STATIC_SCAN_NODE_LIMIT
        )
    )
    kind = validated.convergence_contract.kind
    accepted = False
    if kind == "exact":
        accepted = True
    elif kind == "residual_bound":
        residuals = raw_values["residuals"]
        accepted = residuals[-1] <= raw_values["error_bound"]
    elif kind == "quadrature":
        estimates = raw_values["estimates"]
        bounds = raw_values["error_bounds"]
        accepted = (
            _task12_nonincreasing(bounds)
            and bounds[-1] <= raw_values["error_bound"]
            and abs(estimates[-1] - estimates[-2])
            <= bounds[-1] + bounds[-2]
        )
    elif kind == "finite_size":
        estimates = raw_values["estimates"]
        accepted = (
            max(estimates) - min(estimates) <= raw_values["error_bound"]
        )
    elif kind == "iterative":
        residuals = raw_values["residuals"]
        accepted = (
            residuals[-1] <= raw_values["error_bound"]
            and _task12_nonincreasing(residuals)
        )
    if validated.backend_kind == "dense_ed":
        certificate_values = dict(
            _static_scan_exact_frozen_items(
                raw_values["certificate"],
                "dense ED convergence certificate",
                _STATIC_SCAN_NODE_LIMIT,
            )
        )
        accepted = accepted and _dense_ed_matrix_diagnostics_satisfied(
            validated,
            certificate_values["proof_inputs"]
        )
        accepted = accepted and _dense_ed_method_evidence_satisfied(
            validated,
            certificate_values["proof_inputs"],
        )
    reason_code = (
        "outer_convergence_contract_satisfied"
        if accepted
        else "outer_convergence_contract_failed"
    )
    decision_values = {
        "schema_version": "convergence_decision_v1",
        "kind": kind,
        "accepted": accepted,
        "raw_evidence_sha256": _canonical_sha256(raw),
        "reason_code": reason_code,
    }
    decision_values["decision_sha256"] = _canonical_sha256(decision_values)
    return ConvergenceDecision(**decision_values)


def derive_oracle_decision(
    definition,
    oracle_outputs,
    *,
    execution_evidence_hashes,
    maximum_residual,
):
    """Derive one oracle decision from definition-bound raw outputs."""

    validated = _oracles.validate_oracle_definition(definition)
    outputs = _require_exact_tuple(oracle_outputs, "oracle_outputs")
    if not outputs:
        raise _ContractError("oracle_outputs must be nonempty")
    execution_hashes = _snapshot_sha256_tuple(
        execution_evidence_hashes, "execution_evidence_hashes"
    )
    if len(execution_hashes) != len(outputs):
        raise _ContractError(
            "oracle outputs must bind every execution evidence hash"
        )
    _validate_closed_oracle_convergence_contract(
        validated.convergence_invariant_contract
    )
    contract = dict(
        _static_scan_exact_frozen_items(
            validated.convergence_invariant_contract,
            "oracle convergence invariant contract",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    if (
        type(maximum_residual) not in {int, float}
        or not math.isfinite(maximum_residual)
        or maximum_residual < 0
    ):
        raise _ContractError("oracle maximum_residual is invalid")
    if (
        "secondary_bound" in contract
        and maximum_residual > contract["secondary_bound"]
    ):
        raise _ContractError("oracle maximum_residual exceeds secondary bound")
    residual_fields = tuple(
        name
        for name, schema in validated.result_schema.properties
        if schema.kind in {"number", "integer"}
    )
    invariant_fields = tuple(
        name
        for name, schema in validated.result_schema.properties
        if schema.kind == "boolean"
    )
    result_fields = tuple(
        name for name, _schema in validated.result_schema.properties
    )
    if (
        not result_fields
        or set(residual_fields) | set(invariant_fields) != set(result_fields)
    ):
        raise _ContractError(
            "oracle decision fields do not cover the result schema"
        )
    residual_values = {name: [] for name in residual_fields}
    invariant_values = {name: [] for name in invariant_fields}
    for index, output in enumerate(outputs):
        frozen_output = _snapshot_json(output, f"oracle_outputs[{index}]")
        _adapters._validate_value_against_schema(
            validated.result_schema,
            frozen_output,
            f"oracle_outputs[{index}]",
        )
        output_values = dict(
            _static_scan_exact_frozen_items(
                frozen_output,
                f"oracle_outputs[{index}]",
                _STATIC_SCAN_NODE_LIMIT,
            )
        )
        for name in residual_fields:
            residual = output_values[name]
            if (
                type(residual) not in {int, float}
                or not math.isfinite(residual)
                or residual < 0
            ):
                raise _ContractError("oracle residual is invalid")
            residual_values[name].append(residual)
        for name in invariant_fields:
            invariant = output_values[name]
            if type(invariant) is not bool:
                raise _ContractError("oracle invariant is invalid")
            invariant_values[name].append(invariant)
    accepted = all(
        value <= maximum_residual
        for values in residual_values.values()
        for value in values
    ) and all(
        value
        for values in invariant_values.values()
        for value in values
    )
    decision_values = {
        "schema_version": "oracle_decision_v1",
        "oracle_id": validated.oracle_id,
        "accepted": accepted,
        "oracle_execution_evidence_hashes": execution_hashes,
        "maximum_residual": maximum_residual,
        "residuals": {
            name: tuple(values) for name, values in residual_values.items()
        },
        "invariants": {
            name: tuple(values) for name, values in invariant_values.items()
        },
        "reason_code": (
            "outer_oracle_contract_satisfied"
            if accepted
            else "outer_oracle_contract_failed"
        ),
    }
    decision_values["decision_sha256"] = _canonical_sha256(decision_values)
    return OracleDecision(**decision_values)


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


def validate_process_attestation(
    value, *, expected_role, expected_point_id
):
    """Validate a process attestation against its coordinator binding."""

    role = _require_role(expected_role, "expected_role")
    point_id = _require_text(expected_point_id, "expected_point_id")
    values = _adapter_evidence_exact_record_values(
        value, ProcessAttestation, "process attestation"
    )
    if (
        values["process_role"] != role
        or values["point_id"] != point_id
    ):
        raise _ContractError("process attestation coordinator binding mismatch")
    payload = {
        name: values[name]
        for name in _record_field_names(ProcessAttestation)
        if name != "attestation_sha256"
    }
    if values["attestation_sha256"] != _canonical_sha256(payload):
        raise _ContractError("process attestation hash mismatch")
    return value


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
        if (
            len(self.attempted_accesses) > _TASK11_TRACE_RECORD_LIMIT
            or len(self.violations) > len(self.attempted_accesses)
        ):
            raise _ContractError("trace policy report is oversized")
        normalized_attempts = []
        for index, raw_record in enumerate(self.attempted_accesses):
            record = _exact_keys(
                raw_record,
                _TASK11_TRACE_ACCESS_KEYS,
                f"attempted_accesses[{index}]",
            )
            if (
                type(record["sequence"]) is not int
                or record["sequence"] != index
                or type(record["pid"]) is not int
                or record["pid"] <= 0
                or record["access_kind"]
                not in {"file", "network", "process", "entropy"}
                or record["operation"]
                not in {"read", "write", "execute", "create", "attempt"}
            ):
                raise _ContractError("trace attempted-access record is malformed")
            _identifier(record["syscall"], "trace syscall")
            _require_text(record["logical_path"], "trace logical_path")
            _require_sha256(record["path_sha256"], "trace path_sha256")
            _require_bool(record["succeeded"], "trace succeeded")
            _require_bool(record["allowed"], "trace allowed")
            _identifier(record["reason_code"], "trace reason_code")
            _task11_validate_access_record_semantics(record)
            normalized_attempts.append(record)
        expected_violations = tuple(
            record for record in normalized_attempts if not record["allowed"]
        )
        if tuple(
            _canonical_bytes(record) for record in self.violations
        ) != tuple(
            _canonical_bytes(record) for record in expected_violations
        ):
            raise _ContractError("trace policy violations do not match attempts")
        if self.passed is not (not expected_violations):
            raise _ContractError("trace policy passed status is contradictory")
        body = {
            "schema_version": self.schema_version,
            "trace_sha256": self.trace_sha256,
            "attempted_accesses": self.attempted_accesses,
            "violations": self.violations,
            "passed": self.passed,
        }
        if self.report_sha256 != _canonical_sha256(body):
            raise _ContractError("trace policy report hash mismatch")


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
    capsule_sha256: str
    worker_sha256: str
    result_transport: _FrozenJsonObject
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
        _require_sha256(self.capsule_sha256, "capsule_sha256")
        _require_sha256(self.worker_sha256, "worker_sha256")
        transport = _snapshot_json(
            self.result_transport, "result_transport"
        )
        transport_values = dict(
            _static_scan_exact_frozen_items(
                transport,
                "result transport",
                _STATIC_SCAN_NODE_LIMIT,
            )
        )
        if set(transport_values) != {
            "schema_version",
            "adapter_id",
            "request_sha256",
            "capsule_sha256",
            "local_result",
        }:
            raise _ContractError("result transport field set is not exact")
        if (
            transport_values["schema_version"]
            != "worker_result_transport_v1"
            or type(transport_values["adapter_id"]) is not str
            or not transport_values["adapter_id"]
            or transport_values["request_sha256"] != self.request_sha256
            or transport_values["capsule_sha256"] != self.capsule_sha256
            or self.result_sha256 != _canonical_sha256(transport)
        ):
            raise _ContractError("result transport binding mismatch")
        object.__setattr__(self, "result_transport", transport)
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
        payload = {
            "schema_version": self.schema_version,
            "point_id": self.point_id,
            "request_sha256": self.request_sha256,
            "result_sha256": self.result_sha256,
            "capsule_sha256": self.capsule_sha256,
            "worker_sha256": self.worker_sha256,
            "result_transport": self.result_transport,
            "trace_policy_report_sha256": (
                self.trace_policy_report.report_sha256
            ),
            "process_attestation_sha256": (
                self.process_attestation.attestation_sha256
            ),
            "backend_diagnostics": self.backend_diagnostics,
            "exit_status": self.exit_status,
        }
        if self.execution_sha256 != _canonical_sha256(payload):
            raise _ContractError("point execution evidence hash mismatch")


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
        expected_reason = (
            "outer_convergence_contract_satisfied"
            if self.accepted
            else "outer_convergence_contract_failed"
        )
        if self.reason_code != expected_reason:
            raise _ContractError(
                "convergence decision status and reason are contradictory"
            )
        _require_sha256(self.decision_sha256, "decision_sha256")
        payload = {
            name: getattr(self, name)
            for name in (
                "schema_version",
                "kind",
                "accepted",
                "raw_evidence_sha256",
                "reason_code",
            )
        }
        if self.decision_sha256 != _canonical_sha256(payload):
            raise _ContractError("convergence decision hash mismatch")


@_seal_contract
@dataclass(frozen=True, init=False)
class OracleDecision:
    schema_version: str
    oracle_id: str
    accepted: bool
    oracle_execution_evidence_hashes: tuple[str, ...]
    maximum_residual: float
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
        if (
            type(self.maximum_residual) not in {int, float}
            or not math.isfinite(self.maximum_residual)
            or self.maximum_residual < 0
        ):
            raise _ContractError("oracle maximum_residual is invalid")
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
        expected_reason = (
            "outer_oracle_contract_satisfied"
            if self.accepted
            else "outer_oracle_contract_failed"
        )
        if self.reason_code != expected_reason:
            raise _ContractError(
                "oracle decision status and reason are contradictory"
            )
        _require_sha256(self.decision_sha256, "decision_sha256")
        payload = {
            name: getattr(self, name)
            for name in (
                "schema_version",
                "oracle_id",
                "accepted",
                "oracle_execution_evidence_hashes",
                "maximum_residual",
                "residuals",
                "invariants",
                "reason_code",
            )
        }
        if self.decision_sha256 != _canonical_sha256(payload):
            raise _ContractError("oracle decision hash mismatch")


def _snapshot_exact_record(value: object, record_type: type, field_name: str):
    values = _adapter_evidence_exact_record_values(
        value, record_type, field_name
    )
    return record_type(**values)


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


_ADAPTER_EVIDENCE_NESTED_RECORD_TYPES = (
    ScientificClosure,
    ScientificPolicyCommitment,
    InfrastructureClosure,
    StaticScanReport,
    RuntimeResourceManifest,
    RuntimeSnapshot,
    ProcessAttestation,
    TracePolicyReport,
    PointExecutionEvidence,
    ConvergenceDecision,
    OracleDecision,
    EventRecord,
)


def _adapter_evidence_exact_record_values(value, record_type, field_name):
    if type(value) is not record_type:
        raise _ContractError(
            f"{field_name} must be an exact {record_type.__name__}"
        )
    names = _record_field_names(record_type)
    try:
        namespace = object.__getattribute__(value, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError(
            f"{field_name} record storage is unavailable"
        ) from error
    retained_fields = {
        ScientificClosure: {"_static_scan_material"},
        InfrastructureClosure: {"_static_scan_material"},
        RuntimeSnapshot: {"_retained_runtime_state"},
    }.get(record_type, set())
    actual_fields = set(namespace)
    if (
        type(namespace) is not dict
        or not set(names) <= actual_fields
        or actual_fields - set(names) not in (set(), retained_fields)
    ):
        raise _ContractError(f"{field_name} record storage is not exact")
    return {name: namespace[name] for name in names}


def _adapter_execution_evidence_hash_value(value, field_name):
    if type(value) is dict:
        if len(value) > _STATIC_SCAN_NODE_LIMIT or any(
            type(key) is not str for key in value
        ):
            raise _ContractError(f"{field_name} mapping is not bounded")
        return {
            key: _adapter_execution_evidence_hash_value(
                value[key], f"{field_name}.{key}"
            )
            for key in sorted(value)
        }
    if type(value) is _FrozenJsonObject:
        return {
            key: _adapter_execution_evidence_hash_value(
                item, f"{field_name}.{key}"
            )
            for key, item in _static_scan_exact_frozen_items(
                value,
                f"{field_name} evidence object",
                _STATIC_SCAN_NODE_LIMIT,
            )
        }
    if type(value) is tuple:
        return tuple(
            _adapter_execution_evidence_hash_value(
                item, f"{field_name}[{index}]"
            )
            for index, item in enumerate(value)
        )
    if type(value) in _ADAPTER_EVIDENCE_NESTED_RECORD_TYPES:
        values = _adapter_evidence_exact_record_values(
            value, type(value), field_name
        )
        return {
            field.name: _adapter_execution_evidence_hash_value(
                values[field.name],
                f"{field_name}.{field.name}",
            )
            for field in fields(type(value))
        }
    if type(value) is bytes:
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _ContractError(
                f"{field_name} contains non-UTF-8 evidence bytes"
            ) from error
    if value is None or type(value) in {bool, int, float, str}:
        return value
    raise _ContractError(f"{field_name} has an unsupported evidence type")


def _adapter_execution_evidence_sha256(value):
    values = _adapter_evidence_exact_record_values(
        value, AdapterExecutionEvidence, "evidence"
    )
    payload = {
        field.name: _adapter_execution_evidence_hash_value(
            values[field.name], field.name
        )
        for field in fields(AdapterExecutionEvidence)
        if field.name != "bundle_sha256"
    }
    return _canonical_sha256(payload)


_TASK12_EVIDENCE_EVENT_ORDER = (
    *_PRE_FREEZE_EVENT_NAMES,
    "frozen_hashes",
    "random_seed_acquired",
    "requests_written",
    "adapter_execution_completed",
    "oracle_execution_completed",
    "evidence_finalized",
)
_TASK12_EVIDENCE_EVENT_LIMIT = 4_096
_TASK12_POINT_EXECUTION_LIMIT = 256
_TASK12_VALIDATED_BINDING_FIELDS = (
    "authority_context_sha256",
    "adapter_id",
    "benchmark_id",
    "canonical_observable_id",
    "observable_identity",
    "scientific_inputs",
    "parameter_provenance",
    "numerical_controls",
    "numerical_control_provenance",
    "registry_snapshot_sha256",
    "selector_sha256",
)
_TASK12_ELIGIBILITY_COMMITMENT_FIELDS = (
    "benchmark_id",
    "disposition",
    "adapter_id",
    "oracle_id",
    "eligibility_row_sha256",
    "eligibility_catalog_sha256",
    "adapter_definition_sha256",
    "oracle_definition_sha256",
    "dependency_partition_sha256",
    "adapter_capsule_sha256",
    "oracle_capsule_sha256",
    "worker_capsule_sha256",
)


def _task12_exact_frozen_mapping(value, expected_fields, field_name):
    items = _static_scan_exact_frozen_items(
        value, field_name, _STATIC_SCAN_NODE_LIMIT
    )
    result = dict(items)
    if set(result) != set(expected_fields):
        raise _ContractError(f"{field_name} field set is not exact")
    return result


def validate_adapter_execution_evidence(value):
    """Validate that a success bundle is internally successful and bound."""

    evidence = value
    values = _adapter_evidence_exact_record_values(
        evidence, AdapterExecutionEvidence, "evidence"
    )
    validated_bindings = _task12_exact_frozen_mapping(
        values["validated_inputs_and_provenance"],
        _TASK12_VALIDATED_BINDING_FIELDS,
        "validated inputs and provenance",
    )
    eligibility_bindings = _task12_exact_frozen_mapping(
        values["eligibility_commitments"],
        _TASK12_ELIGIBILITY_COMMITMENT_FIELDS,
        "eligibility commitments",
    )
    adapter_policy = values["adapter_policy_commitment"]
    oracle_policy = values["oracle_policy_commitment"]
    adapter_closure = values["adapter_scientific_closure"]
    oracle_closure = values["oracle_scientific_closure"]
    adapter_policy_values = _adapter_evidence_exact_record_values(
        adapter_policy, ScientificPolicyCommitment, "adapter policy"
    )
    oracle_policy_values = _adapter_evidence_exact_record_values(
        oracle_policy, ScientificPolicyCommitment, "oracle policy"
    )
    adapter_definition = _parse_canonical_definition_bytes(
        adapter_policy_values["canonical_definition_bytes"], "adapter"
    )
    oracle_definition = _parse_canonical_definition_bytes(
        oracle_policy_values["canonical_definition_bytes"], "oracle"
    )
    adapter_closure_values = _adapter_evidence_exact_record_values(
        adapter_closure, ScientificClosure, "adapter closure"
    )
    oracle_closure_values = _adapter_evidence_exact_record_values(
        oracle_closure, ScientificClosure, "oracle closure"
    )
    if (
        adapter_policy_values["role"] != "adapter"
        or adapter_closure_values["role"] != "adapter"
    ):
        raise _ContractError("adapter evidence role mismatch")
    if (
        oracle_policy_values["role"] != "oracle"
        or oracle_closure_values["role"] != "oracle"
    ):
        raise _ContractError("oracle evidence role mismatch")
    for field_name in (
        "authority_context_sha256",
        "registry_snapshot_sha256",
        "selector_sha256",
    ):
        _require_sha256(validated_bindings[field_name], field_name)
    for field_name in _TASK12_ELIGIBILITY_COMMITMENT_FIELDS[4:]:
        _require_sha256(eligibility_bindings[field_name], field_name)
    if (
        values["authority_context_sha256"]
        != validated_bindings["authority_context_sha256"]
        or validated_bindings["adapter_id"]
        != adapter_policy_values["definition_id"]
        or eligibility_bindings["adapter_id"]
        != adapter_policy_values["definition_id"]
        or eligibility_bindings["oracle_id"]
        != oracle_policy_values["definition_id"]
        or eligibility_bindings["benchmark_id"]
        != validated_bindings["benchmark_id"]
        or eligibility_bindings["disposition"] != "eligible"
        or eligibility_bindings["eligibility_row_sha256"]
        != adapter_policy_values["eligibility_row_sha256"]
        or eligibility_bindings["eligibility_catalog_sha256"]
        != adapter_policy_values["eligibility_catalog_sha256"]
        or eligibility_bindings["adapter_definition_sha256"]
        != adapter_policy_values["canonical_definition_sha256"]
        or eligibility_bindings["oracle_definition_sha256"]
        != oracle_policy_values["canonical_definition_sha256"]
    ):
        raise _ContractError("evidence definition or eligibility binding mismatch")
    if (
        adapter_policy_values["entry_closure_sha256"]
        != adapter_closure_values["bundle_sha256"]
        or oracle_policy_values["entry_closure_sha256"]
        != oracle_closure_values["bundle_sha256"]
    ):
        raise _ContractError("scientific policy and closure hash mismatch")
    scans_by_role = {}
    fingerprint_commitments = set()
    for scan in values["static_scan_reports"]:
        scan_values = _adapter_evidence_exact_record_values(
            scan, StaticScanReport, "static scan report"
        )
        role = scan_values["role"]
        if role in scans_by_role or scan_values["passed"] is not True:
            raise _ContractError("static scan evidence is duplicated or failed")
        scans_by_role[role] = scan_values
        fingerprint_commitments.add(
            scan_values["fingerprint_commitment_sha256"]
        )
    if set(scans_by_role) != {"adapter", "oracle", "infrastructure"} or len(
        fingerprint_commitments
    ) != 1:
        raise _ContractError("static scan evidence set is incomplete")
    infrastructure_values = _adapter_evidence_exact_record_values(
        values["infrastructure_closure"],
        InfrastructureClosure,
        "infrastructure closure",
    )
    if (
        scans_by_role["adapter"]["scanned_closure_sha256"]
        != adapter_closure_values["bundle_sha256"]
        or scans_by_role["oracle"]["scanned_closure_sha256"]
        != oracle_closure_values["bundle_sha256"]
        or scans_by_role["infrastructure"]["scanned_closure_sha256"]
        != infrastructure_values["bundle_sha256"]
    ):
        raise _ContractError("scientific policy and static scan mismatch")
    convergence = values["convergence_decision"]
    convergence_values = _adapter_evidence_exact_record_values(
        convergence, ConvergenceDecision, "convergence decision"
    )
    if convergence_values["accepted"] is not True:
        raise _ContractError("convergence decision is not accepted")
    oracle_decision = values["oracle_decision"]
    oracle_decision_values = _adapter_evidence_exact_record_values(
        oracle_decision, OracleDecision, "oracle decision"
    )
    if oracle_decision_values["accepted"] is not True:
        raise _ContractError("oracle decision is not accepted")
    if (
        oracle_policy_values["definition_id"]
        != oracle_decision_values["oracle_id"]
    ):
        raise _ContractError("oracle decision identifier mismatch")
    oracle_execution_hashes = set(
        oracle_decision_values["oracle_execution_evidence_hashes"]
    )
    if not oracle_execution_hashes:
        raise _ContractError("oracle decision has no execution evidence")
    point_ids = set()
    observed_oracle_hashes = set()
    adapter_execution_count = 0
    adapter_raw_convergence = []
    adapter_convergence_decisions = []
    oracle_outputs = []
    oracle_execution_sequence = []
    if not values["point_executions"] or len(
        values["point_executions"]
    ) > _TASK12_POINT_EXECUTION_LIMIT:
        raise _ContractError("point execution evidence count is not bounded")
    for point in values["point_executions"]:
        point_values = _adapter_evidence_exact_record_values(
            point, PointExecutionEvidence, "point execution"
        )
        point_id = point_values["point_id"]
        if point_id in point_ids:
            raise _ContractError("point execution identifier is duplicated")
        point_ids.add(point_id)
        trace = point_values["trace_policy_report"]
        process = point_values["process_attestation"]
        trace_values = _adapter_evidence_exact_record_values(
            trace, TracePolicyReport, "point trace policy report"
        )
        process_values = _adapter_evidence_exact_record_values(
            process, ProcessAttestation, "point process attestation"
        )
        transport_values = _task12_exact_frozen_mapping(
            point_values["result_transport"],
            (
                "schema_version",
                "adapter_id",
                "request_sha256",
                "capsule_sha256",
                "local_result",
            ),
            "point result transport",
        )
        if (
            point_values["exit_status"] != 0
            or trace_values["passed"] is not True
            or transport_values["schema_version"]
            != "worker_result_transport_v1"
            or point_values["request_sha256"]
            != transport_values["request_sha256"]
            or point_values["capsule_sha256"]
            != transport_values["capsule_sha256"]
            or point_values["result_sha256"]
            != _canonical_sha256(point_values["result_transport"])
        ):
            raise _ContractError("point execution is not successful")
        if (
            point_values["worker_sha256"]
            != eligibility_bindings["worker_capsule_sha256"]
        ):
            raise _ContractError("point worker capsule binding mismatch")
        if process_values["point_id"] != point_id:
            raise _ContractError("point execution attestation mismatch")
        execution_hash = point_values["execution_sha256"]
        expected_role = (
            "oracle"
            if execution_hash in oracle_execution_hashes
            else "adapter"
        )
        validate_process_attestation(
            process,
            expected_role=expected_role,
            expected_point_id=point_id,
        )
        if expected_role == "oracle":
            if (
                point_values["capsule_sha256"]
                != eligibility_bindings["oracle_capsule_sha256"]
                or transport_values["adapter_id"]
                != oracle_policy_values["definition_id"]
            ):
                raise _ContractError("oracle execution capsule binding mismatch")
            oracle_output = _snapshot_json(
                transport_values["local_result"], "oracle local result"
            )
            _adapters._validate_value_against_schema(
                oracle_definition.result_schema,
                oracle_output,
                "oracle local result",
            )
            oracle_outputs.append(oracle_output)
            oracle_execution_sequence.append(execution_hash)
            observed_oracle_hashes.add(execution_hash)
        else:
            if (
                point_values["capsule_sha256"]
                != eligibility_bindings["adapter_capsule_sha256"]
                or transport_values["adapter_id"]
                != adapter_policy_values["definition_id"]
            ):
                raise _ContractError("adapter execution capsule binding mismatch")
            local_result = _adapters.validate_local_observable_result(
                adapter_definition, transport_values["local_result"]
            )
            if (
                local_result["capsule_sha256"]
                != point_values["capsule_sha256"]
                or local_result["request_sha256"]
                != point_values["request_sha256"]
                or _canonical_bytes(point_values["backend_diagnostics"])
                != _canonical_bytes(local_result["backend_diagnostics"])
            ):
                raise _ContractError(
                    "adapter execution local-result binding mismatch"
                )
            adapter_raw_convergence.append(
                local_result["raw_convergence_evidence"]
            )
            adapter_convergence_decisions.append(
                derive_convergence_decision(adapter_definition, local_result)
            )
            adapter_execution_count += 1
    if (
        observed_oracle_hashes != oracle_execution_hashes
        or adapter_execution_count == 0
    ):
        raise _ContractError("adapter/oracle execution evidence is incomplete")
    expected_raw_convergence_sha256 = _canonical_sha256(
        adapter_raw_convergence[0]
        if len(adapter_raw_convergence) == 1
        else tuple(adapter_raw_convergence)
    )
    if (
        convergence_values["raw_evidence_sha256"]
        != expected_raw_convergence_sha256
    ):
        raise _ContractError("convergence decision raw evidence mismatch")
    if (
        convergence_values["kind"]
        != adapter_definition.convergence_contract.kind
        or convergence_values["accepted"] is not all(
            decision.accepted
            for decision in adapter_convergence_decisions
        )
        or any(
            decision.kind != convergence_values["kind"]
            for decision in adapter_convergence_decisions
        )
    ):
        raise _ContractError(
            "convergence decision does not match derived raw evidence"
        )
    residual_fields = tuple(
        name
        for name, schema in oracle_definition.result_schema.properties
        if schema.kind in {"number", "integer"}
    )
    invariant_fields = tuple(
        name
        for name, schema in oracle_definition.result_schema.properties
        if schema.kind == "boolean"
    )
    expected_residuals = {
        name: tuple(output[name] for output in oracle_outputs)
        for name in residual_fields
    }
    expected_invariants = {
        name: tuple(output[name] for output in oracle_outputs)
        for name in invariant_fields
    }
    if (
        _canonical_bytes(oracle_decision_values["residuals"])
        != _canonical_bytes(expected_residuals)
        or _canonical_bytes(oracle_decision_values["invariants"])
        != _canonical_bytes(expected_invariants)
    ):
        raise _ContractError("oracle decision raw output mismatch")
    numerical_control_values = _adapter_execution_evidence_hash_value(
        validated_bindings["numerical_controls"], "numerical controls"
    )
    pending_controls = [numerical_control_values]
    positive_float_controls = []
    while pending_controls:
        control = pending_controls.pop()
        if type(control) is dict:
            pending_controls.extend(control.values())
        elif type(control) in {tuple, list}:
            pending_controls.extend(control)
        elif (
            type(control) is float
            and math.isfinite(control)
            and control > 0
        ):
            positive_float_controls.append(control)
    if (
        positive_float_controls
        and oracle_decision_values["maximum_residual"]
        > min(positive_float_controls)
    ):
        raise _ContractError(
            "oracle decision maximum residual exceeds numerical controls"
        )
    derived_oracle_decision = derive_oracle_decision(
        oracle_definition,
        tuple(oracle_outputs),
        execution_evidence_hashes=tuple(oracle_execution_sequence),
        maximum_residual=oracle_decision_values["maximum_residual"],
    )
    derived_oracle_values = _adapter_evidence_exact_record_values(
        derived_oracle_decision,
        OracleDecision,
        "derived oracle decision",
    )
    if _canonical_bytes(derived_oracle_values) != _canonical_bytes(
        oracle_decision_values
    ):
        raise _ContractError(
            "oracle decision does not match derived raw evidence"
        )
    events = values["ordering_events"]
    if not events or len(events) > _TASK12_EVIDENCE_EVENT_LIMIT:
        raise _ContractError("evidence ordering event count is not bounded")
    event_values = tuple(
        _adapter_evidence_exact_record_values(
            event, EventRecord, "ordering event"
        )
        for event in events
    )
    event_sequences = tuple(
        item["sequence_number"] for item in event_values
    )
    if event_sequences != tuple(range(len(events))):
        raise _ContractError("evidence event sequence is not contiguous")
    event_names = tuple(item["event_name"] for item in event_values)
    try:
        required_positions = tuple(
            event_names.index(name) for name in _TASK12_EVIDENCE_EVENT_ORDER
        )
    except ValueError as error:
        raise _ContractError("evidence ordering trace is incomplete") from error
    if (
        required_positions != tuple(sorted(required_positions))
        or any(event_names.count(name) != 1 for name in _TASK12_EVIDENCE_EVENT_ORDER)
    ):
        raise _ContractError("evidence ordering trace is contradictory")
    if values["bundle_sha256"] != _adapter_execution_evidence_sha256(
        evidence
    ):
        raise _ContractError("evidence bundle hash mismatch")
    return evidence


def _coordinator_artifact_material(value, field_name):
    return _canonical_bytes(
        _adapter_execution_evidence_hash_value(value, field_name)
    )


def _validate_coordinator_artifact_bindings(state, evidence):
    values = _adapter_evidence_exact_record_values(
        evidence, AdapterExecutionEvidence, "evidence"
    )
    eligibility = dict(
        _static_scan_exact_frozen_items(
            values["eligibility_commitments"],
            "eligibility commitments",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    dependency_partition_sha256 = eligibility.get(
        "dependency_partition_sha256"
    )
    _require_sha256(
        dependency_partition_sha256, "dependency_partition_sha256"
    )
    authority = state.get("authority_context")
    adapter_definition = state.get("adapter_definition")
    oracle_definition = state.get("oracle_definition")
    try:
        authority_storage = object.__getattribute__(authority, "__dict__")
    except (AttributeError, TypeError) as error:
        raise _ContractError("coordinator authority storage is unavailable") from error
    authority_names = _record_field_names(AdapterAuthorityContext)
    if (
        type(authority) is not AdapterAuthorityContext
        or type(authority_storage) is not dict
        or set(authority_storage) != set(authority_names)
        or type(adapter_definition) is not _AdapterDefinition
        or type(oracle_definition) is not _oracles.OracleDefinition
    ):
        raise _ContractError(
            "coordinator definition or authority binding mismatch"
        )
    authority_values = {
        name: authority_storage[name] for name in authority_names
    }
    adapter_definition_values = _adapter_evidence_exact_record_values(
        adapter_definition, _AdapterDefinition, "coordinator adapter definition"
    )
    oracle_definition_values = _adapter_evidence_exact_record_values(
        oracle_definition,
        _oracles.OracleDefinition,
        "coordinator oracle definition",
    )
    adapter_policy_values = _adapter_evidence_exact_record_values(
        values["adapter_policy_commitment"],
        ScientificPolicyCommitment,
        "coordinator adapter policy",
    )
    oracle_policy_values = _adapter_evidence_exact_record_values(
        values["oracle_policy_commitment"],
        ScientificPolicyCommitment,
        "coordinator oracle policy",
    )
    validated_bindings = dict(
        _static_scan_exact_frozen_items(
            values["validated_inputs_and_provenance"],
            "validated inputs and provenance",
            _STATIC_SCAN_NODE_LIMIT,
        )
    )
    if (
        authority_values["context_sha256"]
        != values["authority_context_sha256"]
        or adapter_definition_values["adapter_id"]
        != adapter_policy_values["definition_id"]
        or oracle_definition_values["oracle_id"]
        != oracle_policy_values["definition_id"]
        or authority_values["benchmark_name"]
        != validated_bindings["benchmark_id"]
        or authority_values["canonical_observable_id"]
        != validated_bindings["canonical_observable_id"]
        or any(
            _canonical_bytes(authority_values[field_name])
            != _canonical_bytes(validated_bindings[field_name])
            for field_name in (
                "observable_identity",
                "scientific_inputs",
                "parameter_provenance",
                "numerical_controls",
                "numerical_control_provenance",
            )
        )
        or authority_values["registry_snapshot_sha256"]
        != validated_bindings["registry_snapshot_sha256"]
        or authority_values["selector_sha256"]
        != validated_bindings["selector_sha256"]
    ):
        raise _ContractError(
            "coordinator definition or authority binding mismatch"
        )
    oracle_hashes = set(
        _adapter_evidence_exact_record_values(
            values["oracle_decision"], OracleDecision, "oracle decision"
        )["oracle_execution_evidence_hashes"]
    )
    adapter_points = []
    oracle_points = []
    request_hashes = []
    result_hashes = []
    trace_hashes = []
    attestation_hashes = []
    for point in values["point_executions"]:
        point_values = _adapter_evidence_exact_record_values(
            point, PointExecutionEvidence, "point execution"
        )
        request_hashes.append(point_values["request_sha256"])
        result_hashes.append(point_values["result_sha256"])
        trace_values = _adapter_evidence_exact_record_values(
            point_values["trace_policy_report"],
            TracePolicyReport,
            "point trace",
        )
        process_values = _adapter_evidence_exact_record_values(
            point_values["process_attestation"],
            ProcessAttestation,
            "point attestation",
        )
        trace_hashes.append(trace_values["report_sha256"])
        attestation_hashes.append(process_values["attestation_sha256"])
        if point_values["execution_sha256"] in oracle_hashes:
            oracle_points.append(point)
        else:
            adapter_points.append(point)
    oracle_values = _adapter_evidence_exact_record_values(
        values["oracle_decision"], OracleDecision, "oracle decision"
    )
    expected = {
        "scientific_closure": values["adapter_scientific_closure"],
        "oracle_closure": values["oracle_scientific_closure"],
        "static_scan": values["static_scan_reports"],
        "scientific_policy_commitment": (
            values["adapter_policy_commitment"],
            values["oracle_policy_commitment"],
        ),
        "infrastructure_closure": values["infrastructure_closure"],
        "dependency_partition": dependency_partition_sha256,
        "runtime_snapshot": values["runtime_snapshot"],
        "capability_preflight": values["capability_preflight_sha256"],
        "request_write": tuple(request_hashes),
        "isolation_setup": tuple(attestation_hashes),
        "worker_execution": tuple(adapter_points),
        "trace_policy": tuple(trace_hashes),
        "output_ingestion": tuple(result_hashes),
        "result_validation": tuple(result_hashes),
        "convergence": values["convergence_decision"],
        "oracle_isolation": tuple(oracle_points),
        "oracle_output": {
            "residuals": oracle_values["residuals"],
            "invariants": oracle_values["invariants"],
        },
        "oracle_decision": values["oracle_decision"],
        "runtime_snapshot_revalidation": True,
    }
    for stage, expected_value in expected.items():
        if stage not in state or _coordinator_artifact_material(
            state[stage], f"coordinator artifact {stage}"
        ) != _coordinator_artifact_material(
            expected_value, f"evidence artifact {stage}"
        ):
            raise _ContractError(
                f"coordinator artifact {stage} does not match evidence"
            )
    seed = state.get("seed_generation")
    if type(seed) is not bytes or seed.hex() != values["disclosed_seed_hex"]:
        raise _ContractError(
            "coordinator seed artifact does not match disclosed evidence"
        )


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
_FAILURE_TRANSITIONS = frozenset(
    {
        ("strict_recomputation_unavailable", "definition_validation", "unknown_adapter"),
        ("strict_recomputation_unavailable", "authority_validation", "authority_context_rejected"),
        ("adapter_ineligible", "eligibility_validation", "adapter_source_parse_only"),
        ("input_rejected", "scientific_input_validation", "scientific_input_rejected"),
        ("input_rejected", "numerical_control_validation", "numerical_control_rejected"),
        ("dependency_rejected", "eligibility_validation", "dependency_policy_rejected"),
        ("dependency_rejected", "scientific_closure", "dependency_policy_rejected"),
        ("dependency_rejected", "static_scan", "dependency_policy_rejected"),
        ("dependency_rejected", "dependency_partition", "dependency_policy_rejected"),
        ("dependency_rejected", "static_scan", "scientific_policy_rejected"),
        ("dependency_rejected", "scientific_policy_commitment", "scientific_policy_rejected"),
        ("dependency_rejected", "infrastructure_closure", "infrastructure_dependency_rejected"),
        ("dependency_rejected", "dependency_partition", "infrastructure_dependency_rejected"),
        ("strict_recomputation_unavailable", "runtime_snapshot", "runtime_resource_unavailable"),
        ("strict_recomputation_unavailable", "capability_preflight", "capability_preflight_failed"),
        ("strict_recomputation_unavailable", "seed_generation", "seed_generation_failed"),
        ("isolation_failed", "request_write", "request_write_failed"),
        ("isolation_failed", "isolation_setup", "namespace_setup_failed"),
        ("execution_failed", "worker_execution", "worker_timeout"),
        ("execution_failed", "worker_execution", "worker_signaled"),
        ("execution_failed", "worker_execution", "worker_nonzero_exit"),
        ("isolation_failed", "trace_policy", "trace_missing"),
        ("isolation_failed", "trace_policy", "trace_policy_violation"),
        ("execution_failed", "output_ingestion", "worker_output_rejected"),
        ("execution_failed", "result_validation", "local_result_rejected"),
        ("convergence_failed", "convergence", "convergence_contract_failed"),
        ("strict_recomputation_unavailable", "oracle_closure", "oracle_dependency_rejected"),
        ("dependency_rejected", "oracle_closure", "oracle_dependency_rejected"),
        ("oracle_failed", "oracle_isolation", "oracle_isolation_failed"),
        ("oracle_failed", "oracle_output", "oracle_output_rejected"),
        ("oracle_failed", "oracle_decision", "oracle_invariant_failed"),
        ("isolation_failed", "runtime_snapshot_revalidation", "runtime_snapshot_changed"),
        ("strict_recomputation_unavailable", "evidence_finalization", "evidence_hash_failed"),
    }
)
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
        if (self.status, self.stage, self.reason_code) not in (
            _FAILURE_TRANSITIONS
        ):
            raise _ContractError("failure transition is contradictory")
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
                validate_adapter_execution_evidence(self.evidence),
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


def _coordinator_failure_outcome(
    status,
    stage,
    reason_code,
    *,
    available_hashes=None,
    available_attestations=None,
):
    if available_hashes is None:
        available_hashes = {}
    if available_attestations is None:
        available_attestations = {}
    failure = AdapterRunFailure(
        schema_version="adapter_run_failure_v1",
        status=status,
        stage=stage,
        reason_code=reason_code,
        diagnostic=_FAILURE_DIAGNOSTICS[reason_code],
        available_hashes=available_hashes,
        available_attestations=available_attestations,
    )
    return AdapterRunOutcome(
        status=status,
        evidence=None,
        failure=failure,
    )


_COORDINATOR_TRANSITION_STAGES = (
    "scientific_closure",
    "oracle_closure",
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
    "oracle_isolation",
    "oracle_output",
    "oracle_decision",
    "runtime_snapshot_revalidation",
    "evidence_finalization",
)
_COORDINATOR_DEPENDENCY_TOKEN = object()


class _CoordinatorTransitionFailure(Exception):
    __slots__ = ("status", "reason_code")

    def __init__(self, status, reason_code):
        if type(status) is not str or type(reason_code) is not str:
            raise _ContractError(
                "coordinator transition failure must be closed text"
            )
        self.status = status
        self.reason_code = reason_code
        super().__init__(status, reason_code)


class _CoordinatorDependencyBundle:
    __slots__ = ("oracle_definition", "transition_operations")

    def __init__(
        self,
        *,
        oracle_definition,
        transition_operations,
        authorization=None,
    ):
        if authorization is not _COORDINATOR_DEPENDENCY_TOKEN:
            raise _ContractError(
                "coordinator dependency bundle construction is unauthorized"
            )
        validated_oracle = _oracles.validate_oracle_definition(
            oracle_definition
        )
        operations = _require_exact_tuple(
            transition_operations, "transition_operations"
        )
        if tuple(
            pair[0]
            for pair in operations
            if type(pair) is tuple and len(pair) == 2
        ) != _COORDINATOR_TRANSITION_STAGES or len(operations) != len(
            _COORDINATOR_TRANSITION_STAGES
        ):
            raise _ContractError(
                "coordinator transition operation set is not exact"
            )
        for stage, operation in operations:
            if stage not in _COORDINATOR_TRANSITION_STAGES or not callable(
                operation
            ):
                raise _ContractError(
                    "coordinator transition operation is malformed"
                )
        object.__setattr__(self, "oracle_definition", validated_oracle)
        object.__setattr__(self, "transition_operations", operations)

    def __setattr__(self, name, value):
        raise AttributeError("coordinator dependency bundle is immutable")


def _make_test_coordinator_dependency_bundle(
    *, oracle_definition, transition_operations
):
    return _CoordinatorDependencyBundle(
        oracle_definition=oracle_definition,
        transition_operations=transition_operations,
        authorization=_COORDINATOR_DEPENDENCY_TOKEN,
    )


def _run_isolated_recomputation_core(
    adapter_id,
    authority_context,
    *,
    run_parent,
    dependency_bundle=None,
):
    """Resolve the immutable production catalogs before any execution."""

    if type(adapter_id) is not str:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "definition_validation",
            "unknown_adapter",
        )
    catalog_row = _adapters.ADAPTER_ELIGIBILITY.get(adapter_id)
    resolved_adapter_id = adapter_id
    benchmark_id = adapter_id if catalog_row is not None else None
    if catalog_row is not None:
        if catalog_row.disposition != "eligible":
            return _coordinator_failure_outcome(
                "adapter_ineligible",
                "eligibility_validation",
                "adapter_source_parse_only",
            )
        resolved_adapter_id = catalog_row.adapter_id
    definition = _adapters.ADAPTER_DEFINITIONS.get(resolved_adapter_id)
    if definition is None:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "definition_validation",
            "unknown_adapter",
        )
    if catalog_row is None:
        matching_rows = tuple(
            (candidate_benchmark_id, row)
            for candidate_benchmark_id, row
            in _adapters.ADAPTER_ELIGIBILITY.items()
            if row.disposition == "eligible"
            and row.adapter_id == resolved_adapter_id
        )
        if len(matching_rows) != 1:
            return _coordinator_failure_outcome(
                "strict_recomputation_unavailable",
                "eligibility_validation",
                "dependency_policy_rejected",
            )
        benchmark_id, catalog_row = matching_rows[0]
    try:
        validated_definition = _validate_adapter_definition(definition)
    except _ContractError:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "definition_validation",
            "unknown_adapter",
        )
    try:
        validated_authority = validate_authority_context(
            authority_context,
            allow_test_producer=False,
        )
    except _ContractError:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "authority_validation",
            "authority_context_rejected",
        )
    if (
        validated_authority.benchmark_name != benchmark_id
        or _canonical_bytes(validated_authority.observable_identity)
        != _canonical_bytes(validated_definition.observable_identity)
    ):
        return _coordinator_failure_outcome(
            "dependency_rejected",
            "eligibility_validation",
            "dependency_policy_rejected",
            available_hashes={
                "authority_context_sha256": (
                    validated_authority.context_sha256
                )
            },
            available_attestations={"authority_validated": True},
        )
    try:
        _validate_inputs(
            validated_definition, validated_authority.scientific_inputs
        )
    except _ContractError:
        return _coordinator_failure_outcome(
            "input_rejected",
            "scientific_input_validation",
            "scientific_input_rejected",
            available_hashes={
                "authority_context_sha256": (
                    validated_authority.context_sha256
                )
            },
            available_attestations={
                "authority_validated": True,
                "eligibility_validated": True,
            },
        )
    try:
        _validate_controls(
            validated_definition, validated_authority.numerical_controls
        )
    except _ContractError:
        return _coordinator_failure_outcome(
            "input_rejected",
            "numerical_control_validation",
            "numerical_control_rejected",
            available_hashes={
                "authority_context_sha256": (
                    validated_authority.context_sha256
                )
            },
            available_attestations={
                "authority_validated": True,
                "eligibility_validated": True,
            },
        )
    if catalog_row.oracle_id != validated_definition.oracle_id:
        return _coordinator_failure_outcome(
            "dependency_rejected",
            "eligibility_validation",
            "dependency_policy_rejected",
            available_hashes={
                "authority_context_sha256": (
                    validated_authority.context_sha256
                )
            },
            available_attestations={"authority_validated": True},
        )
    if dependency_bundle is None:
        oracle_definition = _oracles.ORACLE_DEFINITIONS.get(
            validated_definition.oracle_id
        )
    elif type(dependency_bundle) is _CoordinatorDependencyBundle:
        candidate = dependency_bundle.oracle_definition
        candidate_values = _adapter_evidence_exact_record_values(
            candidate,
            _oracles.OracleDefinition,
            "coordinator dependency oracle",
        )
        oracle_definition = (
            candidate
            if candidate_values["oracle_id"]
            == validated_definition.oracle_id
            else None
        )
    else:
        raise _ContractError("coordinator dependency bundle is not authentic")
    if oracle_definition is None:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "oracle_closure",
            "oracle_dependency_rejected",
            available_hashes={
                "authority_context_sha256": (
                    validated_authority.context_sha256
                )
            },
            available_attestations={
                "authority_validated": True,
                "eligibility_validated": True,
            },
        )
    if dependency_bundle is None:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "oracle_closure",
            "oracle_dependency_rejected",
            available_hashes={
                "authority_context_sha256": validated_authority.context_sha256
            },
            available_attestations={
                "authority_validated": True,
                "eligibility_validated": True,
            },
        )
    state = {
        "adapter_definition": validated_definition,
        "oracle_definition": oracle_definition,
        "authority_context": validated_authority,
        "run_parent": run_parent,
    }
    for stage, operation in dependency_bundle.transition_operations:
        try:
            result = operation(MappingProxyType(dict(state)))
        except _CoordinatorTransitionFailure as error:
            return _coordinator_failure_outcome(
                error.status,
                stage,
                error.reason_code,
                available_hashes={
                    "authority_context_sha256": (
                        validated_authority.context_sha256
                    )
                },
                available_attestations={
                    "authority_validated": True,
                    "eligibility_validated": True,
                },
            )
        if type(result) is not dict:
            raise _ContractError(
                f"coordinator transition {stage} returned a non-mapping"
            )
        expected_keys = (
            {"evidence"}
            if stage == "evidence_finalization"
            else {"artifact"}
        )
        if set(result) != expected_keys:
            raise _ContractError(
                f"coordinator transition {stage} result is not exact"
            )
        state[stage] = result[next(iter(expected_keys))]
    final_result = state["evidence_finalization"]
    try:
        evidence = validate_adapter_execution_evidence(final_result)
        _validate_coordinator_artifact_bindings(state, evidence)
    except _ContractError:
        return _coordinator_failure_outcome(
            "strict_recomputation_unavailable",
            "evidence_finalization",
            "evidence_hash_failed",
            available_hashes={
                "authority_context_sha256": validated_authority.context_sha256
            },
            available_attestations={
                "authority_validated": True,
                "eligibility_validated": True,
            },
        )
    return AdapterRunOutcome(
        status="isolated_recomputation_succeeded",
        evidence=evidence,
        failure=None,
    )


def run_isolated_recomputation(adapter_id, authority_context, *, run_parent):
    """Run one production-bound recomputation without injectable services."""

    return _run_isolated_recomputation_core(
        adapter_id,
        authority_context,
        run_parent=run_parent,
    )
