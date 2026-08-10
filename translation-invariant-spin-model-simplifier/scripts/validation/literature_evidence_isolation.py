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
from validation.literature_evidence_adapters import (
    AdapterContractError,
    AdapterDefinition,
    FrozenJsonObject,
    _CONVERGENCE_KINDS,
    _OBSERVABLE_IDENTITY_KEYS,
    _initialize_closed,
    _metadata_tokens,
    _require_json_integer_magnitude,
    _require_nonempty_string,
    _require_string_tuple,
    _require_tuple,
    _seal_contract,
    _snapshot_json_mapping,
    canonical_json_bytes,
    canonical_sha256,
    require_exact_keys,
    require_identifier,
    validate_adapter_definition,
    validate_numerical_controls,
    validate_scientific_inputs,
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
        raise AdapterContractError(
            f"{field_name} must be a lowercase SHA-256 hex digest"
        )
    return value


def _require_optional_sha256(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_sha256(value, field_name)


def _require_bool(value: object, field_name: str) -> bool:
    if type(value) is not bool:
        raise AdapterContractError(f"{field_name} must be a boolean")
    return value


def _require_nonnegative_integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise AdapterContractError(
            f"{field_name} must be a nonnegative integer"
        )
    _require_json_integer_magnitude(value, field_name)
    if value < 0:
        raise AdapterContractError(
            f"{field_name} must be a nonnegative integer"
        )
    return value


def _require_role(value: object, field_name: str = "role") -> str:
    if type(value) is not str or value not in _ROLES:
        raise AdapterContractError(f"{field_name} must be adapter or oracle")
    return value


def _snapshot_mapping_tuple(value: object, field_name: str) -> tuple:
    items = _require_tuple(value, field_name)
    return tuple(
        _snapshot_json_mapping(item, f"{field_name}[{index}]")
        for index, item in enumerate(items)
    )


def _snapshot_sha256_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _require_tuple(value, field_name)
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
        return {name: getattr(value, name) for name in names}
    if isinstance(value, Mapping):
        snapshot = require_exact_keys(value, names, field_name)
        return {name: snapshot[name] for name in names}
    raise AdapterContractError(
        f"{field_name} must be a mapping or exact {record_type.__name__}"
    )


def _normalize_record_error(field_name: str, constructor):
    try:
        return constructor()
    except AdapterContractError:
        raise
    except Exception as error:
        raise AdapterContractError(
            f"{field_name} validation failed"
        ) from error


def _record_to_frozen_json(
    value: object, record_type: type
) -> FrozenJsonObject:
    if type(value) is not record_type:
        raise AdapterContractError(
            f"value must be an exact {record_type.__name__}"
        )
    return _snapshot_json_mapping(
        {
            field.name: getattr(value, field.name)
            for field in fields(record_type)
        },
        record_type.__name__,
    )


def _validate_parameter_provenance(
    scientific_inputs: FrozenJsonObject,
    provenance: FrozenJsonObject,
) -> None:
    if set(scientific_inputs) != set(provenance):
        raise AdapterContractError(
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
        "locator",
        "commitment_sha256",
        "target_equivalent",
    )
    for parameter_name in provenance:
        record = require_exact_keys(
            provenance[parameter_name],
            expected,
            f"parameter_provenance.{parameter_name}",
        )
        if record["kind"] not in allowed_kinds:
            raise AdapterContractError(
                "parameter provenance has an unknown kind"
            )
        _require_nonempty_string(
            record["locator"],
            f"parameter_provenance.{parameter_name}.locator",
        )
        _require_sha256(
            record["commitment_sha256"],
            f"parameter_provenance.{parameter_name}.commitment_sha256",
        )
        if record["target_equivalent"] is not False:
            raise AdapterContractError(
                "target-equivalent parameter provenance is forbidden"
            )


def _validate_numerical_control_provenance(
    numerical_controls: FrozenJsonObject,
    provenance: FrozenJsonObject,
) -> None:
    if set(numerical_controls) != set(provenance):
        raise AdapterContractError(
            "numerical_control_provenance must bind every control exactly once"
        )
    expected = (
        "kind",
        "locator",
        "commitment_sha256",
        "registry_independent",
    )
    for control_name in provenance:
        record = require_exact_keys(
            provenance[control_name],
            expected,
            f"numerical_control_provenance.{control_name}",
        )
        if record["kind"] != "numerical_control":
            raise AdapterContractError(
                "numerical control provenance has an unknown kind"
            )
        _require_nonempty_string(
            record["locator"],
            f"numerical_control_provenance.{control_name}.locator",
        )
        _require_sha256(
            record["commitment_sha256"],
            f"numerical_control_provenance.{control_name}.commitment_sha256",
        )
        if record["registry_independent"] is not True:
            raise AdapterContractError(
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
    observable_identity: FrozenJsonObject
    canonical_spec_path: str
    canonical_spec_sha256: str
    scientific_inputs: FrozenJsonObject
    parameter_provenance: FrozenJsonObject
    numerical_controls: FrozenJsonObject
    numerical_control_provenance: FrozenJsonObject
    registry_snapshot_sha256: str
    selector_sha256: str
    forbidden_output_fingerprints: tuple[str, ...]
    fingerprint_algorithm_version: str
    context_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, AdapterAuthorityContext)

    def __post_init__(self) -> None:
        if self.schema_version != _AUTHORITY_SCHEMA_VERSION:
            raise AdapterContractError(
                "AdapterAuthorityContext has an unknown schema_version"
            )
        _require_nonempty_string(self.audit_run_id, "audit_run_id")
        _require_nonempty_string(self.benchmark_name, "benchmark_name")
        if self.producer_id not in _AUTHORITY_PRODUCERS:
            raise AdapterContractError(
                "authority context has an unknown producer"
            )
        _require_sha256(self.producer_code_sha256, "producer_code_sha256")
        _require_nonempty_string(
            self.canonical_observable_id, "canonical_observable_id"
        )
        observable_identity = require_exact_keys(
            _snapshot_json_mapping(
                self.observable_identity, "observable_identity"
            ),
            _OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        canonical_spec_path = _require_nonempty_string(
            self.canonical_spec_path, "canonical_spec_path"
        )
        parsed_path = PurePosixPath(canonical_spec_path)
        if (
            parsed_path.is_absolute()
            or ".." in parsed_path.parts
            or canonical_spec_path == "."
            or str(parsed_path) != canonical_spec_path
        ):
            raise AdapterContractError(
                "canonical_spec_path must be a relative normalized path"
            )
        _require_sha256(self.canonical_spec_sha256, "canonical_spec_sha256")
        scientific_inputs = _snapshot_json_mapping(
            self.scientific_inputs, "scientific_inputs"
        )
        parameter_provenance = _snapshot_json_mapping(
            self.parameter_provenance, "parameter_provenance"
        )
        numerical_controls = _snapshot_json_mapping(
            self.numerical_controls, "numerical_controls"
        )
        numerical_control_provenance = _snapshot_json_mapping(
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
            raise AdapterContractError(
                "forbidden_output_fingerprints must be nonempty"
            )
        if len(set(fingerprints)) != len(fingerprints):
            raise AdapterContractError(
                "forbidden_output_fingerprints contains a duplicate"
            )
        if fingerprints != tuple(sorted(fingerprints)):
            raise AdapterContractError(
                "forbidden_output_fingerprints must use canonical ordering"
            )
        if (
            self.fingerprint_algorithm_version
            != _FINGERPRINT_ALGORITHM_VERSION
        ):
            raise AdapterContractError("unknown fingerprint algorithm version")
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
            raise AdapterContractError("authority context hash mismatch")

    def calculated_context_sha256(self) -> str:
        payload = {
            field.name: getattr(self, field.name)
            for field in fields(AdapterAuthorityContext)
            if field.name != "context_sha256"
        }
        return canonical_sha256(payload)

    def to_frozen_json(self) -> FrozenJsonObject:
        return _record_to_frozen_json(self, AdapterAuthorityContext)


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
        raise AdapterContractError("allow_test_producer must be a boolean")
    context = _snapshot_authority_context(value)
    if (
        context.producer_id == _TEST_AUTHORITY_PRODUCER
        and not allow_test_producer
    ):
        raise AdapterContractError(
            "test authority producer requires explicit test-only opt-in"
        )
    return context


@_seal_contract
@dataclass(frozen=True, init=False)
class WorkerRequest:
    schema_version: str
    opaque_run_nonce: str
    adapter_id: str
    scientific_inputs: FrozenJsonObject
    numerical_controls: FrozenJsonObject
    capsule_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, WorkerRequest)

    def __post_init__(self) -> None:
        if self.schema_version != _WORKER_REQUEST_SCHEMA_VERSION:
            raise AdapterContractError(
                "WorkerRequest has an unknown schema_version"
            )
        nonce = _require_nonempty_string(
            self.opaque_run_nonce, "opaque_run_nonce"
        )
        if len(nonce.encode("utf-8")) > 256:
            raise AdapterContractError("opaque_run_nonce is too long")
        require_identifier(self.adapter_id, "adapter_id")
        scientific_inputs = _snapshot_json_mapping(
            self.scientific_inputs, "scientific_inputs"
        )
        numerical_controls = _snapshot_json_mapping(
            self.numerical_controls, "numerical_controls"
        )
        _require_sha256(self.capsule_sha256, "capsule_sha256")
        object.__setattr__(self, "scientific_inputs", scientific_inputs)
        object.__setattr__(self, "numerical_controls", numerical_controls)

    def to_frozen_json(self) -> FrozenJsonObject:
        return _record_to_frozen_json(self, WorkerRequest)


def make_worker_request(
    definition: AdapterDefinition,
    authority_context: AdapterAuthorityContext,
    *,
    opaque_run_nonce: str,
    capsule_sha256: str,
    allow_test_producer: bool = False,
    **extra_metadata: object,
) -> WorkerRequest:
    """Project only answer-free model inputs and controls into a request."""

    if extra_metadata:
        raise AdapterContractError("worker request contains extra metadata")
    if type(allow_test_producer) is not bool:
        raise AdapterContractError("allow_test_producer must be a boolean")
    validated_definition = validate_adapter_definition(definition)
    if type(authority_context) is not AdapterAuthorityContext:
        raise AdapterContractError(
            "authority_context must be a validated exact record"
        )
    context = validate_authority_context(
        authority_context,
        allow_test_producer=allow_test_producer,
    )
    scientific_inputs = validate_scientific_inputs(
        validated_definition, context.scientific_inputs
    )
    numerical_controls = validate_numerical_controls(
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
    text = _require_nonempty_string(value, field_name)
    if ":" not in text:
        raise AdapterContractError(
            f"{field_name} must contain module:function"
        )
    return text


def _require_edge_tuple(value: object, field_name: str) -> tuple:
    items = _require_tuple(value, field_name)
    normalized = []
    for index, item in enumerate(items):
        if type(item) is not tuple or len(item) != 2:
            raise AdapterContractError(
                f"{field_name}[{index}] must be an exact edge pair"
            )
        source, destination = item
        normalized.append(
            (
                _require_nonempty_string(source, f"{field_name}[{index}][0]"),
                _require_nonempty_string(
                    destination, f"{field_name}[{index}][1]"
                ),
            )
        )
    if len(set(normalized)) != len(normalized):
        raise AdapterContractError(f"{field_name} contains a duplicate edge")
    return tuple(normalized)


@_seal_contract
@dataclass(frozen=True, init=False)
class ScientificClosure:
    schema_version: str
    role: str
    entry_symbol: str
    nodes: tuple[FrozenJsonObject, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    emitted_source_sha256: str
    bundle_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ScientificClosure)

    def __post_init__(self) -> None:
        if self.schema_version != "scientific_closure_v1":
            raise AdapterContractError(
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
        raise AdapterContractError(
            "canonical_definition_bytes must be exact bytes"
        )
    if len(value) > 1_048_576:
        raise AdapterContractError("canonical_definition_bytes is oversized")
    try:
        decoded = value.decode("utf-8")
        parsed = json.loads(
            decoded,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {token}")
            ),
        )
    except (UnicodeDecodeError, ValueError, TypeError) as error:
        raise AdapterContractError(
            "canonical_definition_bytes is not canonical JSON"
        ) from error
    if canonical_json_bytes(parsed) != value:
        raise AdapterContractError(
            "canonical_definition_bytes is noncanonical"
        )
    frozen = _snapshot_json_mapping(parsed, "canonical_definition")
    expected = (
        _ADAPTER_DEFINITION_FIELDS
        if role == "adapter"
        else _ORACLE_DEFINITION_FIELDS
    )
    if set(frozen) != expected:
        raise AdapterContractError(
            "canonical definition fields contain an unknown or missing field"
        )
    return frozen


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
        raise AdapterContractError(
            "scientific policy commitment must be a mapping"
        )
    allowed = set(_SCIENTIFIC_POLICY_FIELDS)
    actual = set(value)
    if not actual <= allowed or not (allowed - {"combined_sha256"}) <= actual:
        raise AdapterContractError(
            "scientific policy commitment has unknown or missing fields"
        )
    payload = {}
    for key in _SCIENTIFIC_POLICY_FIELDS:
        if key == "combined_sha256" or key not in value:
            continue
        item = value[key]
        if key == "canonical_definition_bytes":
            if type(item) is not bytes:
                raise AdapterContractError(
                    "canonical_definition_bytes must be exact bytes"
                )
            try:
                item = item.decode("utf-8")
            except UnicodeDecodeError as error:
                raise AdapterContractError(
                    "canonical_definition_bytes must be UTF-8"
                ) from error
        payload[key] = item
    return canonical_sha256(payload)


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
    output_or_invariant_proof_bindings: FrozenJsonObject
    domain_sha256: str
    size_policy_sha256: str
    convergence_sha256: str
    static_scan_sha256: str
    combined_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ScientificPolicyCommitment)

    def __post_init__(self) -> None:
        if self.schema_version != "scientific_policy_commitment_v1":
            raise AdapterContractError(
                "ScientificPolicyCommitment has unknown schema_version"
            )
        role = _require_role(self.role)
        require_identifier(self.definition_id, "definition_id")
        canonical_definition = _parse_canonical_definition_bytes(
            self.canonical_definition_bytes, role
        )
        identifier_field = "adapter_id" if role == "adapter" else "oracle_id"
        if canonical_definition[identifier_field] != self.definition_id:
            raise AdapterContractError(
                "definition_id does not match canonical definition bytes"
            )
        expected_definition_hash = hashlib.sha256(
            self.canonical_definition_bytes
        ).hexdigest()
        if self.canonical_definition_sha256 != expected_definition_hash:
            raise AdapterContractError("canonical definition hash mismatch")
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
            raise AdapterContractError(
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
        bindings = _snapshot_json_mapping(
            self.output_or_invariant_proof_bindings,
            "output_or_invariant_proof_bindings",
        )
        if not bindings:
            raise AdapterContractError(
                "output_or_invariant_proof_bindings must be nonempty"
            )
        object.__setattr__(
            self, "output_or_invariant_proof_bindings", bindings
        )
        calculated = scientific_policy_combined_sha256(
            {
                field.name: getattr(self, field.name)
                for field in fields(ScientificPolicyCommitment)
            }
        )
        if self.combined_sha256 != calculated:
            raise AdapterContractError(
                "scientific policy combined hash mismatch"
            )


@_seal_contract
@dataclass(frozen=True, init=False)
class InfrastructureClosure:
    schema_version: str
    roots: tuple[str, ...]
    nodes: tuple[FrozenJsonObject, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    purpose_bindings: FrozenJsonObject
    bundle_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, InfrastructureClosure)

    def __post_init__(self) -> None:
        if self.schema_version != "infrastructure_closure_v1":
            raise AdapterContractError(
                "InfrastructureClosure has unknown schema_version"
            )
        roots = _require_string_tuple(self.roots, "roots")
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
            _snapshot_json_mapping(self.purpose_bindings, "purpose_bindings"),
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
    checks: FrozenJsonObject
    passed: bool
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, StaticScanReport)

    def __post_init__(self) -> None:
        if self.schema_version != "static_scan_report_v1":
            raise AdapterContractError(
                "StaticScanReport has unknown schema_version"
            )
        if self.role not in {"adapter", "oracle", "infrastructure"}:
            raise AdapterContractError("StaticScanReport has unknown role")
        _require_nonempty_string(self.scanner_version, "scanner_version")
        for field_name in (
            "scanner_sha256",
            "scanned_closure_sha256",
            "fingerprint_commitment_sha256",
            "report_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        object.__setattr__(
            self, "checks", _snapshot_json_mapping(self.checks, "checks")
        )
        _require_bool(self.passed, "passed")


@_seal_contract
@dataclass(frozen=True, init=False)
class RuntimeResourceManifest:
    schema_version: str
    resources: tuple[FrozenJsonObject, ...]
    manifest_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, RuntimeResourceManifest)

    def __post_init__(self) -> None:
        if self.schema_version != "runtime_resource_manifest_v1":
            raise AdapterContractError(
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
        raise AdapterContractError(
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
    directory_identities: tuple[FrozenJsonObject, ...]
    snapshot_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, RuntimeSnapshot)

    def __post_init__(self) -> None:
        if self.schema_version != "runtime_snapshot_v1":
            raise AdapterContractError(
                "RuntimeSnapshot has unknown schema_version"
            )
        object.__setattr__(
            self, "manifest", _snapshot_runtime_manifest(self.manifest)
        )
        _require_nonempty_string(self.snapshot_root, "snapshot_root")
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
    checks: FrozenJsonObject
    command_identities: FrozenJsonObject
    namespace_identifiers: FrozenJsonObject
    mount_facts: FrozenJsonObject
    probe_result_codes: FrozenJsonObject
    trace_sha256: str
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, CapabilityPreflightReport)

    def __post_init__(self) -> None:
        if self.schema_version != "capability_preflight_report_v1":
            raise AdapterContractError(
                "CapabilityPreflightReport has unknown schema_version"
            )
        _require_nonempty_string(self.audit_run_id, "audit_run_id")
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
                _snapshot_json_mapping(getattr(self, field_name), field_name),
            )
        _require_sha256(self.trace_sha256, "trace_sha256")
        _require_sha256(self.report_sha256, "report_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class ProcessAttestation:
    schema_version: str
    process_role: str
    point_id: str
    namespace_identifiers: FrozenJsonObject
    mount_facts: FrozenJsonObject
    environment_facts: FrozenJsonObject
    resource_limit_facts: FrozenJsonObject
    chroot_facts: FrozenJsonObject
    attestation_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ProcessAttestation)

    def __post_init__(self) -> None:
        if self.schema_version != "process_attestation_v1":
            raise AdapterContractError(
                "ProcessAttestation has unknown schema_version"
            )
        _require_role(self.process_role, "process_role")
        _require_nonempty_string(self.point_id, "point_id")
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
                _snapshot_json_mapping(getattr(self, field_name), field_name),
            )
        _require_sha256(self.attestation_sha256, "attestation_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class TracePolicyReport:
    schema_version: str
    trace_sha256: str
    attempted_accesses: tuple[FrozenJsonObject, ...]
    violations: tuple[FrozenJsonObject, ...]
    passed: bool
    report_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, TracePolicyReport)

    def __post_init__(self) -> None:
        if self.schema_version != "trace_policy_report_v1":
            raise AdapterContractError(
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
        raise AdapterContractError(
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
        raise AdapterContractError(
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
    backend_diagnostics: FrozenJsonObject
    exit_status: int
    execution_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, PointExecutionEvidence)

    def __post_init__(self) -> None:
        if self.schema_version != "point_execution_evidence_v1":
            raise AdapterContractError(
                "PointExecutionEvidence has unknown schema_version"
            )
        _require_nonempty_string(self.point_id, "point_id")
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
            _snapshot_json_mapping(
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
        _initialize_closed(self, args, kwargs, ConvergenceDecision)

    def __post_init__(self) -> None:
        if self.schema_version != "convergence_decision_v1":
            raise AdapterContractError(
                "ConvergenceDecision has unknown schema_version"
            )
        if self.kind not in _CONVERGENCE_KINDS:
            raise AdapterContractError("ConvergenceDecision has unknown kind")
        _require_bool(self.accepted, "accepted")
        _require_sha256(self.raw_evidence_sha256, "raw_evidence_sha256")
        require_identifier(self.reason_code, "reason_code")
        _require_sha256(self.decision_sha256, "decision_sha256")


@_seal_contract
@dataclass(frozen=True, init=False)
class OracleDecision:
    schema_version: str
    oracle_id: str
    accepted: bool
    oracle_execution_evidence_hashes: tuple[str, ...]
    residuals: FrozenJsonObject
    invariants: FrozenJsonObject
    reason_code: str
    decision_sha256: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, OracleDecision)

    def __post_init__(self) -> None:
        if self.schema_version != "oracle_decision_v1":
            raise AdapterContractError(
                "OracleDecision has unknown schema_version"
            )
        require_identifier(self.oracle_id, "oracle_id")
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
            _snapshot_json_mapping(self.residuals, "residuals"),
        )
        object.__setattr__(
            self,
            "invariants",
            _snapshot_json_mapping(self.invariants, "invariants"),
        )
        require_identifier(self.reason_code, "reason_code")
        _require_sha256(self.decision_sha256, "decision_sha256")


def _snapshot_exact_record(value: object, record_type: type, field_name: str):
    if type(value) is not record_type:
        raise AdapterContractError(
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
    details: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, EventRecord)

    def __post_init__(self) -> None:
        _require_nonnegative_integer(self.sequence_number, "sequence_number")
        require_identifier(self.event_name, "event_name")
        object.__setattr__(
            self, "details", _snapshot_json_mapping(self.details, "details")
        )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterExecutionEvidence:
    schema_version: str
    status: str
    authority_context_sha256: str
    validated_inputs_and_provenance: FrozenJsonObject
    eligibility_commitments: FrozenJsonObject
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
        _initialize_closed(self, args, kwargs, AdapterExecutionEvidence)

    def __post_init__(self) -> None:
        if self.schema_version != "adapter_execution_evidence_v1":
            raise AdapterContractError(
                "AdapterExecutionEvidence has unknown schema_version"
            )
        if self.status != "isolated_recomputation_succeeded":
            raise AdapterContractError(
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
                _snapshot_json_mapping(getattr(self, field_name), field_name),
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
        scans = _require_tuple(self.static_scan_reports, "static_scan_reports")
        object.__setattr__(
            self,
            "static_scan_reports",
            tuple(
                _snapshot_exact_record(item, StaticScanReport, "scan_report")
                for item in scans
            ),
        )
        events = _require_tuple(self.ordering_events, "ordering_events")
        object.__setattr__(
            self,
            "ordering_events",
            tuple(
                _snapshot_exact_record(item, EventRecord, "event")
                for item in events
            ),
        )
        points = _require_tuple(self.point_executions, "point_executions")
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
            raise AdapterContractError(
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
_FAILURE_SUCCESS_TOKENS = frozenset(
    {"success", "strictmatch", "verdict", "literaturematch", "successbundle"}
)


def _reject_failure_success_material(value: object, field_name: str) -> None:
    if type(value) is FrozenJsonObject:
        for key, item in value._items:
            tokens = _metadata_tokens(key, f"{field_name} mapping key")
            joined = "".join(tokens)
            if joined in _FAILURE_SUCCESS_TOKENS or any(
                token in _FAILURE_SUCCESS_TOKENS for token in tokens
            ):
                raise AdapterContractError(
                    f"{field_name} cannot contain a success bundle"
                )
            _reject_failure_success_material(item, f"{field_name}.{key}")
    elif type(value) is tuple:
        for index, item in enumerate(value):
            _reject_failure_success_material(item, f"{field_name}[{index}]")
    elif type(value) is str:
        tokens = _metadata_tokens(value, field_name)
        joined = "".join(tokens)
        if joined in _FAILURE_SUCCESS_TOKENS:
            raise AdapterContractError(
                f"{field_name} cannot contain a success bundle"
            )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterRunFailure:
    schema_version: str
    status: str
    stage: str
    reason_code: str
    diagnostic: str
    available_hashes: FrozenJsonObject
    available_attestations: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, AdapterRunFailure)

    def __post_init__(self) -> None:
        if self.schema_version != "adapter_run_failure_v1":
            raise AdapterContractError(
                "AdapterRunFailure has unknown schema_version"
            )
        if self.status not in FAILURE_STATUSES:
            raise AdapterContractError("failure status is not closed")
        if self.stage not in FAILURE_STAGES:
            raise AdapterContractError("failure stage is not closed")
        if self.reason_code not in FAILURE_REASON_CODES:
            raise AdapterContractError("failure reason_code is not closed")
        diagnostic = _require_nonempty_string(self.diagnostic, "diagnostic")
        if len(diagnostic.encode("utf-8")) > _FAILURE_DIAGNOSTIC_MAX_BYTES:
            raise AdapterContractError("failure diagnostic is oversized")
        available_hashes = _snapshot_json_mapping(
            self.available_hashes, "available_hashes"
        )
        for name, digest in available_hashes._items:
            _require_sha256(digest, f"available_hashes.{name}")
        available_attestations = _snapshot_json_mapping(
            self.available_attestations, "available_attestations"
        )
        _reject_failure_success_material(
            available_attestations, "available_attestations"
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
        _initialize_closed(self, args, kwargs, AdapterRunOutcome)

    def __post_init__(self) -> None:
        if self.status == "isolated_recomputation_succeeded":
            if type(self.evidence) is not AdapterExecutionEvidence:
                raise AdapterContractError(
                    "successful outcome requires evidence"
                )
            if self.failure is not None:
                raise AdapterContractError(
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
                raise AdapterContractError(
                    "failed outcome cannot carry evidence"
                )
            if type(self.failure) is not AdapterRunFailure:
                raise AdapterContractError("failed outcome requires failure")
            failure = validate_failure(self.failure)
            if failure.status != self.status:
                raise AdapterContractError(
                    "outcome status does not match failure status"
                )
            object.__setattr__(self, "failure", failure)
        else:
            raise AdapterContractError("AdapterRunOutcome has unknown status")
