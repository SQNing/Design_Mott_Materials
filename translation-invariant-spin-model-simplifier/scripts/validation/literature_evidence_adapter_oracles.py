"""Closed metadata contracts for independent recalculation oracles.

Task 4 intentionally leaves the production oracle catalog empty.  Later tasks
add answer-free scientific entry points only after the isolation contracts and
dependency partition are in place.  Importing this module performs no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from validation.literature_evidence_adapters import (
    AdapterContractError,
    FrozenJsonObject,
    ResourceLimits,
    RuntimeRequirements,
    ValueSchema,
    _ENTRY_SYMBOL_RE,
    _initialize_closed,
    _seal_contract,
    _snapshot_json_mapping,
    _snapshot_resource_limits,
    _snapshot_runtime_requirements,
    _snapshot_value_schema,
    _validate_authored_json,
    _validate_authored_schema,
    _validate_authored_string,
    require_identifier,
)


@_seal_contract
@dataclass(frozen=True, init=False)
class OracleDefinition:
    """Answer-free declaration of one independently bundled oracle."""

    oracle_id: str
    entry_symbol: str
    input_schema: ValueSchema
    result_schema: ValueSchema
    runtime_requirements: RuntimeRequirements
    convergence_invariant_contract: FrozenJsonObject
    resource_limits: ResourceLimits

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, OracleDefinition)

    def __post_init__(self) -> None:
        require_identifier(self.oracle_id, "oracle_id")
        if (
            type(self.entry_symbol) is not str
            or _ENTRY_SYMBOL_RE.fullmatch(self.entry_symbol) is None
        ):
            raise AdapterContractError(
                "entry_symbol must be a fully qualified module:function symbol"
            )
        expected_symbol = (
            "validation.literature_evidence_adapter_oracles:oracle_"
            + self.oracle_id
        )
        if self.entry_symbol != expected_symbol:
            raise AdapterContractError(
                "entry_symbol must be the exact unresolved oracle symbol"
            )
        input_schema = _snapshot_value_schema(
            self.input_schema, "input_schema"
        )
        result_schema = _snapshot_value_schema(
            self.result_schema, "result_schema"
        )
        if input_schema.kind != "object" or result_schema.kind != "object":
            raise AdapterContractError(
                "oracle input_schema and result_schema must be object schemas"
            )
        runtime_requirements = _snapshot_runtime_requirements(
            self.runtime_requirements
        )
        convergence_invariant_contract = _snapshot_json_mapping(
            self.convergence_invariant_contract,
            "convergence_invariant_contract",
        )
        if not convergence_invariant_contract:
            raise AdapterContractError(
                "convergence_invariant_contract must be nonempty"
            )
        resource_limits = _snapshot_resource_limits(self.resource_limits)
        _validate_authored_string(
            self.oracle_id,
            "oracle_id",
            allow_numerical_control=True,
        )
        _validate_authored_schema(
            input_schema,
            "input_schema",
            allow_numerical_control=True,
        )
        _validate_authored_schema(result_schema, "result_schema")
        _validate_authored_json(
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
                _validate_authored_string(
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
        raise AdapterContractError(
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
    except AdapterContractError:
        raise
    except Exception as error:
        raise AdapterContractError(
            "oracle definition revalidation failed"
        ) from error


ORACLE_DEFINITIONS: Mapping[str, OracleDefinition] = MappingProxyType({})


def get_oracle_definition(oracle_id: str) -> OracleDefinition:
    """Return a production oracle declaration or fail closed."""

    require_identifier(oracle_id, "oracle_id")
    try:
        return ORACLE_DEFINITIONS[oracle_id]
    except KeyError as error:
        raise AdapterContractError(f"unknown oracle_id {oracle_id}") from error
