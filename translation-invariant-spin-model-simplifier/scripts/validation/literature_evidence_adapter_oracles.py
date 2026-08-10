"""Closed metadata contracts for independent recalculation oracles.

Task 4 intentionally leaves the production oracle catalog empty.  Later tasks
add answer-free scientific entry points only after the isolation contracts and
dependency partition are in place.  Importing this module performs no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from validation import literature_evidence_adapters as _adapters


__all__ = (
    "OracleDefinition",
    "ORACLE_DEFINITIONS",
    "get_oracle_definition",
    "validate_oracle_definition",
    "oracle_definition_to_frozen_json",
    "oracle_definition_from_frozen_json",
)


@_adapters._seal_contract
@dataclass(frozen=True, init=False)
class OracleDefinition:
    """Answer-free declaration of one independently bundled oracle."""

    oracle_id: str
    entry_symbol: str
    input_schema: _adapters.ValueSchema
    result_schema: _adapters.ValueSchema
    runtime_requirements: _adapters.RuntimeRequirements
    convergence_invariant_contract: _adapters.FrozenJsonObject
    resource_limits: _adapters.ResourceLimits

    def __init__(self, *args, **kwargs):
        _adapters._initialize_closed(self, args, kwargs, OracleDefinition)

    def __post_init__(self) -> None:
        _adapters.require_identifier(self.oracle_id, "oracle_id")
        if (
            type(self.entry_symbol) is not str
            or _adapters._ENTRY_SYMBOL_RE.fullmatch(self.entry_symbol) is None
        ):
            raise _adapters.AdapterContractError(
                "entry_symbol must be a fully qualified module:function symbol"
            )
        expected_symbol = (
            "validation.literature_evidence_adapter_oracles:oracle_"
            + self.oracle_id
        )
        if self.entry_symbol != expected_symbol:
            raise _adapters.AdapterContractError(
                "entry_symbol must be the exact unresolved oracle symbol"
            )
        input_schema = _adapters._snapshot_value_schema(
            self.input_schema, "input_schema"
        )
        result_schema = _adapters._snapshot_value_schema(
            self.result_schema, "result_schema"
        )
        if input_schema.kind != "object" or result_schema.kind != "object":
            raise _adapters.AdapterContractError(
                "oracle input_schema and result_schema must be object schemas"
            )
        runtime_requirements = _adapters._snapshot_runtime_requirements(
            self.runtime_requirements
        )
        convergence_invariant_contract = _adapters._snapshot_json_mapping(
            self.convergence_invariant_contract,
            "convergence_invariant_contract",
        )
        if not convergence_invariant_contract:
            raise _adapters.AdapterContractError(
                "convergence_invariant_contract must be nonempty"
            )
        resource_limits = _adapters._snapshot_resource_limits(
            self.resource_limits
        )
        _adapters._validate_authored_string(
            self.oracle_id,
            "oracle_id",
            allow_numerical_control=True,
        )
        _adapters._validate_authored_schema(
            input_schema,
            "input_schema",
            allow_numerical_control=True,
        )
        _adapters._validate_authored_schema(result_schema, "result_schema")
        _adapters._validate_authored_json(
            convergence_invariant_contract,
            "convergence_invariant_contract",
            allow_numerical_control=True,
        )
        for field_name in (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ):
            metadata = getattr(runtime_requirements, field_name)
            values = metadata if type(metadata) is tuple else (metadata,)
            for index, item in enumerate(values):
                _adapters._validate_authored_string(
                    item,
                    f"runtime_requirements.{field_name}[{index}]",
                )
        object.__setattr__(self, "input_schema", input_schema)
        object.__setattr__(self, "result_schema", result_schema)
        object.__setattr__(
            self, "runtime_requirements", runtime_requirements
        )
        object.__setattr__(
            self,
            "convergence_invariant_contract",
            convergence_invariant_contract,
        )
        object.__setattr__(self, "resource_limits", resource_limits)


def validate_oracle_definition(value: object) -> OracleDefinition:
    """Return a fresh revalidated oracle-definition snapshot."""

    if type(value) is not OracleDefinition:
        raise _adapters.AdapterContractError(
            "oracle definition must be an exact OracleDefinition"
        )
    try:
        return OracleDefinition(
            oracle_id=value.oracle_id,
            entry_symbol=value.entry_symbol,
            input_schema=value.input_schema,
            result_schema=value.result_schema,
            runtime_requirements=value.runtime_requirements,
            convergence_invariant_contract=(
                value.convergence_invariant_contract
            ),
            resource_limits=value.resource_limits,
        )
    except _adapters.AdapterContractError:
        raise
    except Exception as error:
        raise _adapters.AdapterContractError(
            "oracle definition revalidation failed"
        ) from error


_ORACLE_DEFINITION_JSON_FIELDS = (
    "oracle_id",
    "entry_symbol",
    "input_schema",
    "result_schema",
    "runtime_requirements",
    "convergence_invariant_contract",
    "resource_limits",
)


def oracle_definition_to_frozen_json(
    value: OracleDefinition,
) -> _adapters.FrozenJsonObject:
    """Serialize one validated oracle definition with a locked JSON schema."""

    definition = validate_oracle_definition(value)
    return _adapters._snapshot_json_mapping(
        {
            "oracle_id": definition.oracle_id,
            "entry_symbol": definition.entry_symbol,
            "input_schema": _adapters._value_schema_to_frozen_json(
                definition.input_schema
            ),
            "result_schema": _adapters._value_schema_to_frozen_json(
                definition.result_schema
            ),
            "runtime_requirements": {
                "interpreter": definition.runtime_requirements.interpreter,
                "packages": definition.runtime_requirements.packages,
                "native_libraries": (
                    definition.runtime_requirements.native_libraries
                ),
                "backend_resources": (
                    definition.runtime_requirements.backend_resources
                ),
            },
            "convergence_invariant_contract": (
                definition.convergence_invariant_contract
            ),
            "resource_limits": {
                field_name: getattr(definition.resource_limits, field_name)
                for field_name in (
                    "cpu_seconds",
                    "wall_seconds",
                    "address_space_bytes",
                    "output_bytes",
                    "file_descriptors",
                    "process_count",
                )
            },
        },
        "oracle_definition",
    )


def oracle_definition_from_frozen_json(value: object) -> OracleDefinition:
    """Deserialize and fully validate the locked oracle-definition schema."""

    definition = _adapters.require_exact_keys(
        value, _ORACLE_DEFINITION_JSON_FIELDS, "oracle_definition"
    )
    runtime = _adapters.require_exact_keys(
        definition["runtime_requirements"],
        (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ),
        "runtime_requirements",
    )
    limit_fields = (
        "cpu_seconds",
        "wall_seconds",
        "address_space_bytes",
        "output_bytes",
        "file_descriptors",
        "process_count",
    )
    limits = _adapters.require_exact_keys(
        definition["resource_limits"],
        limit_fields,
        "resource_limits",
    )
    candidate = OracleDefinition(
        oracle_id=definition["oracle_id"],
        entry_symbol=definition["entry_symbol"],
        input_schema=_adapters._value_schema_from_frozen_json(
            definition["input_schema"], "input_schema"
        ),
        result_schema=_adapters._value_schema_from_frozen_json(
            definition["result_schema"], "result_schema"
        ),
        runtime_requirements=_adapters.RuntimeRequirements(
            interpreter=runtime["interpreter"],
            packages=_adapters._require_tuple(
                runtime["packages"], "runtime_requirements.packages"
            ),
            native_libraries=_adapters._require_tuple(
                runtime["native_libraries"],
                "runtime_requirements.native_libraries",
            ),
            backend_resources=_adapters._require_tuple(
                runtime["backend_resources"],
                "runtime_requirements.backend_resources",
            ),
        ),
        convergence_invariant_contract=(
            definition["convergence_invariant_contract"]
        ),
        resource_limits=_adapters.ResourceLimits(
            **{name: limits[name] for name in limit_fields}
        ),
    )
    validated = validate_oracle_definition(candidate)
    if _adapters.canonical_json_bytes(
        oracle_definition_to_frozen_json(validated)
    ) != _adapters.canonical_json_bytes(definition):
        raise _adapters.AdapterContractError(
            "oracle definition does not round-trip canonically"
        )
    return validated


ORACLE_DEFINITIONS: Mapping[str, OracleDefinition] = MappingProxyType({})


def get_oracle_definition(oracle_id: str) -> OracleDefinition:
    """Return a production oracle declaration or fail closed."""

    _adapters.require_identifier(oracle_id, "oracle_id")
    try:
        return ORACLE_DEFINITIONS[oracle_id]
    except KeyError as error:
        raise _adapters.AdapterContractError(
            f"unknown oracle_id {oracle_id}"
        ) from error
