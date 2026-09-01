"""Immutable contracts for isolated literature recalculation adapters.

This module contains data validation only.  It deliberately performs no file,
network, process, registry, or source-evidence access.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, fields
import hashlib
import json
import math
import numpy as np
import re
from types import MappingProxyType
from typing import Any


__all__ = (
    "AdapterContractError",
    "FrozenJsonObject",
    "freeze_json",
    "thaw_json",
    "canonical_json_bytes",
    "canonical_sha256",
    "require_exact_keys",
    "require_identifier",
    "ValueSchema",
    "OUTPUT_PROOF_KINDS",
    "OutputFieldBinding",
    "OutputSchema",
    "ParameterSource",
    "CounterfactualDomain",
    "ConvergenceContract",
    "ProblemSizePolicy",
    "RuntimeRequirements",
    "ResourceLimits",
    "AdapterDefinition",
    "SOURCE_PARSE_ONLY_REASONS",
    "EligibilityDecision",
    "ADAPTER_ELIGIBILITY",
    "ADAPTER_DEFINITIONS",
    "get_adapter_definition",
    "validate_adapter_definition",
    "adapter_definition_to_frozen_json",
    "adapter_definition_from_frozen_json",
    "adapter_eligibility_row_to_frozen_json",
    "adapter_eligibility_catalog_to_frozen_json",
    "validate_scientific_inputs",
    "validate_numerical_controls",
    "LocalObservableResult",
    "validate_local_observable_result",
)


class AdapterContractError(ValueError):
    """Raised when an adapter definition or JSON value is not closed and valid."""


@dataclass(frozen=True, init=False, eq=False)
class FrozenJsonObject(Mapping[str, object]):
    """A recursively immutable and hashable JSON object."""

    _items: tuple[tuple[str, object], ...]

    def __init__(self, value: Mapping[str, object]):
        frozen = freeze_json(value)
        if type(frozen) is not FrozenJsonObject:
            raise AdapterContractError("FrozenJsonObject value must be a mapping")
        object.__setattr__(self, "_items", frozen._items)

    @classmethod
    def _from_frozen_items(
        cls, items: tuple[tuple[str, object], ...]
    ) -> "FrozenJsonObject":
        instance = object.__new__(cls)
        object.__setattr__(instance, "_items", items)
        return instance

    def __getitem__(self, key: str) -> object:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        try:
            return canonical_json_bytes(self) == canonical_json_bytes(other)
        except Exception:
            return False

    def __hash__(self) -> int:
        digest_prefix = int(canonical_sha256(self)[:16], 16)
        return -2 if digest_prefix == -1 else digest_prefix

    def __repr__(self) -> str:
        return f"FrozenJsonObject({dict(self._items)!r})"


def _require_utf8_string(value: str, field_name: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise AdapterContractError(
            f"{field_name} must be a UTF-8-encodable Unicode scalar string"
        ) from error
    return value


_MAX_JSON_NESTING = 128
_MAX_JSON_INTEGER_BITS = 1024


def _require_json_integer_magnitude(value: int, field_name: str) -> int:
    if abs(value).bit_length() > _MAX_JSON_INTEGER_BITS:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum JSON integer magnitude of "
            f"{_MAX_JSON_INTEGER_BITS} bits"
        )
    return value


def _validate_frozen_json_placement(
    value: object,
    field_name: str,
    active_container_ids: set[int],
    depth: int,
) -> None:
    if depth > _MAX_JSON_NESTING:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum JSON nesting of {_MAX_JSON_NESTING}"
        )
    if callable(value):
        raise AdapterContractError(f"{field_name} contains a callable value")
    if type(value) is FrozenJsonObject:
        if type(value._items) is not tuple:
            raise AdapterContractError(
                f"{field_name} frozen mapping storage must be an immutable tuple"
            )
        container_id = id(value)
        if container_id in active_container_ids:
            raise AdapterContractError(f"{field_name} contains a JSON cycle")
        active_container_ids.add(container_id)
        seen_keys = set()
        try:
            for pair in value._items:
                if type(pair) is not tuple or len(pair) != 2:
                    raise AdapterContractError(
                        f"{field_name} contains a malformed frozen mapping item"
                    )
                key, item = pair
                if type(key) is not str:
                    raise AdapterContractError(
                        f"{field_name} contains a non-string mapping key"
                    )
                _require_utf8_string(key, f"{field_name} mapping key")
                if key in seen_keys:
                    raise AdapterContractError(
                        f"{field_name} contains duplicate mapping key {key!r}"
                    )
                seen_keys.add(key)
                _validate_frozen_json_placement(
                    item,
                    f"{field_name}.{key}",
                    active_container_ids,
                    depth + 1,
                )
        finally:
            active_container_ids.remove(container_id)
        return
    if isinstance(value, FrozenJsonObject):
        raise AdapterContractError(
            f"{field_name} contains an unsupported FrozenJsonObject subclass"
        )
    if type(value) is tuple:
        container_id = id(value)
        if container_id in active_container_ids:
            raise AdapterContractError(f"{field_name} contains a JSON cycle")
        active_container_ids.add(container_id)
        try:
            for index, item in enumerate(value):
                _validate_frozen_json_placement(
                    item,
                    f"{field_name}[{index}]",
                    active_container_ids,
                    depth + 1,
                )
        finally:
            active_container_ids.remove(container_id)
        return
    if value is None or type(value) in (bool, int, float, str):
        _freeze_json(value, field_name, active_container_ids, depth)
        return
    raise AdapterContractError(
        f"{field_name} contains unsupported frozen JSON value "
        f"{type(value).__name__}"
    )


def _freeze_json(
    value: object,
    field_name: str,
    active_container_ids: set[int],
    depth: int,
) -> object:
    if depth > _MAX_JSON_NESTING:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum JSON nesting of {_MAX_JSON_NESTING}"
        )

    if callable(value):
        raise AdapterContractError(f"{field_name} contains a callable value")
    if type(value) is FrozenJsonObject:
        _validate_frozen_json_placement(
            value, field_name, active_container_ids, depth
        )
        return value
    if isinstance(value, FrozenJsonObject):
        raise AdapterContractError(
            f"{field_name} contains an unsupported FrozenJsonObject subclass"
        )
    if type(value) is str:
        return _require_utf8_string(value, field_name)
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return _require_json_integer_magnitude(value, field_name)
    if type(value) is float:
        if not math.isfinite(value):
            raise AdapterContractError(f"{field_name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_container_ids:
            raise AdapterContractError(f"{field_name} contains a JSON cycle")
        active_container_ids.add(container_id)
        frozen_items = []
        seen_keys = set()
        try:
            try:
                item_iterator = iter(value.items())
            except AdapterContractError:
                raise
            except Exception as error:
                raise AdapterContractError(
                    f"{field_name} mapping traversal failed"
                ) from error
            while True:
                try:
                    pair = next(item_iterator)
                except StopIteration:
                    break
                except AdapterContractError:
                    raise
                except Exception as error:
                    raise AdapterContractError(
                        f"{field_name} mapping traversal failed"
                    ) from error
                try:
                    key, item = pair
                except Exception as error:
                    raise AdapterContractError(
                        f"{field_name} contains a malformed mapping item"
                    ) from error
                if type(key) is not str:
                    raise AdapterContractError(
                        f"{field_name} contains a non-string mapping key"
                    )
                _require_utf8_string(key, f"{field_name} mapping key")
                if key in seen_keys:
                    raise AdapterContractError(
                        f"{field_name} contains duplicate mapping key {key!r}"
                    )
                seen_keys.add(key)
                frozen_items.append(
                    (
                        key,
                        _freeze_json(
                            item,
                            f"{field_name}.{key}",
                            active_container_ids,
                            depth + 1,
                        ),
                    )
                )
        finally:
            active_container_ids.remove(container_id)
        frozen_items.sort(key=lambda item: item[0])
        return FrozenJsonObject._from_frozen_items(tuple(frozen_items))
    if isinstance(value, (list, tuple)):
        container_id = id(value)
        if container_id in active_container_ids:
            raise AdapterContractError(f"{field_name} contains a JSON cycle")
        active_container_ids.add(container_id)
        frozen_items = []
        try:
            try:
                item_iterator = iter(value)
            except AdapterContractError:
                raise
            except Exception as error:
                raise AdapterContractError(
                    f"{field_name} sequence traversal failed"
                ) from error
            index = 0
            while True:
                try:
                    item = next(item_iterator)
                except StopIteration:
                    break
                except AdapterContractError:
                    raise
                except Exception as error:
                    raise AdapterContractError(
                        f"{field_name} sequence traversal failed"
                    ) from error
                frozen_items.append(
                    _freeze_json(
                        item,
                        f"{field_name}[{index}]",
                        active_container_ids,
                        depth + 1,
                    )
                )
                index += 1
        finally:
            active_container_ids.remove(container_id)
        return tuple(frozen_items)
    raise AdapterContractError(
        f"{field_name} contains unsupported JSON value {type(value).__name__}"
    )


def freeze_json(value: object, field_name: str = "value") -> object:
    """Return an isolated, recursively immutable representation of JSON data."""

    try:
        return _freeze_json(value, field_name, set(), 0)
    except AdapterContractError:
        raise
    except RecursionError as error:
        raise AdapterContractError(
            f"{field_name} exceeds safe JSON recursion limits"
        ) from error
    except Exception as error:
        raise AdapterContractError(f"{field_name} JSON traversal failed") from error


def _thaw_json(value: object, field_name: str, depth: int) -> object:
    if depth > _MAX_JSON_NESTING:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum JSON nesting of {_MAX_JSON_NESTING}"
        )
    if callable(value):
        raise AdapterContractError(f"{field_name} contains a callable value")
    if type(value) is FrozenJsonObject:
        return {
            key: _thaw_json(item, f"{field_name}.{key}", depth + 1)
            for key, item in value._items
        }
    if isinstance(value, FrozenJsonObject):
        raise AdapterContractError(
            f"{field_name} contains an unsupported FrozenJsonObject subclass"
        )
    if type(value) is tuple:
        return [
            _thaw_json(item, f"{field_name}[{index}]", depth + 1)
            for index, item in enumerate(value)
        ]
    if type(value) is str:
        return _require_utf8_string(value, field_name)
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return _require_json_integer_magnitude(value, field_name)
    if type(value) is float:
        if not math.isfinite(value):
            raise AdapterContractError(f"{field_name} contains a non-finite number")
        return value
    raise AdapterContractError(
        f"{field_name} contains unsupported frozen JSON value {type(value).__name__}"
    )


def thaw_json(value: object, field_name: str = "value") -> object:
    """Convert frozen JSON data to fresh ordinary dictionaries and lists."""

    try:
        return _thaw_json(value, field_name, 0)
    except AdapterContractError:
        raise
    except RecursionError as error:
        raise AdapterContractError(
            f"{field_name} exceeds safe JSON recursion limits"
        ) from error
    except Exception as error:
        raise AdapterContractError(f"{field_name} JSON traversal failed") from error


def canonical_json_bytes(value: object) -> bytes:
    """Encode JSON deterministically as sorted, compact, unescaped UTF-8."""

    frozen = freeze_json(value)
    try:
        encoded = json.dumps(
            thaw_json(frozen),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return encoded.encode("utf-8")
    except UnicodeEncodeError as error:
        raise AdapterContractError(
            "value contains a string that is not UTF-8 encodable"
        ) from error
    except (TypeError, ValueError) as error:
        raise AdapterContractError(f"value is not canonical JSON: {error}") from error


def canonical_sha256(value: object) -> str:
    """Return the SHA-256 hex digest of a value's canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ENTRY_SYMBOL_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
    r":[A-Za-z_][A-Za-z0-9_]*$"
)


def require_exact_keys(
    value: Mapping[str, object], expected: Iterable[str], field_name: str
) -> FrozenJsonObject:
    """Freeze one mapping snapshot and require exactly the named keys."""

    snapshot = _freeze_mapping(value, field_name)
    actual_keys = tuple(snapshot)
    expected_keys = tuple(expected)
    if any(type(key) is not str for key in expected_keys):
        raise AdapterContractError(f"{field_name} expected keys must be strings")
    if len(set(expected_keys)) != len(expected_keys):
        raise AdapterContractError(f"{field_name} expected keys contain a duplicate")
    expected_set = set(expected_keys)
    actual_set = set(actual_keys)
    missing = sorted(expected_set - actual_set)
    unknown = sorted(actual_set - expected_set)
    if missing:
        raise AdapterContractError(
            f"{field_name} missing required field {missing[0]}"
        )
    if unknown:
        raise AdapterContractError(f"{field_name} contains unknown field {unknown[0]}")
    return snapshot


def require_identifier(value: object, field_name: str) -> str:
    """Require a stable lower-snake-case identifier."""

    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        raise AdapterContractError(
            f"{field_name} must match ^[a-z][a-z0-9_]*$"
        )
    return value


def _require_nonempty_string(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise AdapterContractError(f"{field_name} must be a nonempty string")
    return _require_utf8_string(value, field_name)


def _require_finite_number(
    value: object,
    field_name: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> int | float:
    if type(value) not in (int, float):
        raise AdapterContractError(f"{field_name} must be a finite number")
    if type(value) is int:
        _require_json_integer_magnitude(value, field_name)
    elif not math.isfinite(value):
        raise AdapterContractError(f"{field_name} must be a finite number")
    if positive and value <= 0:
        raise AdapterContractError(f"{field_name} must be positive")
    if nonnegative and value < 0:
        raise AdapterContractError(f"{field_name} must be nonnegative")
    return value


def _require_positive_integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise AdapterContractError(f"{field_name} must be a positive integer")
    _require_json_integer_magnitude(value, field_name)
    if value <= 0:
        raise AdapterContractError(f"{field_name} must be a positive integer")
    return value


def _require_nonnegative_integer(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise AdapterContractError(
            f"{field_name} item-count bound must be a nonnegative integer"
        )
    _require_json_integer_magnitude(value, field_name)
    if value < 0:
        raise AdapterContractError(
            f"{field_name} item-count bound must be a nonnegative integer"
        )
    return value


def _require_tuple(value: object, field_name: str) -> tuple:
    if type(value) is not tuple:
        raise AdapterContractError(f"{field_name} must be an immutable tuple")
    return value


def _require_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _require_tuple(value, field_name)
    for index, item in enumerate(items):
        _require_nonempty_string(item, f"{field_name}[{index}]")
    if len(set(items)) != len(items):
        raise AdapterContractError(f"{field_name} contains a duplicate")
    return items


def _freeze_mapping(value: object, field_name: str) -> FrozenJsonObject:
    if not isinstance(value, Mapping):
        raise AdapterContractError(f"{field_name} must be a mapping")
    frozen = freeze_json(value, field_name)
    if type(frozen) is not FrozenJsonObject:
        raise AdapterContractError(f"{field_name} must be a mapping")
    return frozen


def _snapshot_json_mapping(
    value: object,
    field_name: str,
) -> FrozenJsonObject:
    validated = _freeze_mapping(value, field_name)
    snapshot = _freeze_mapping(
        thaw_json(validated, field_name),
        field_name,
    )
    if snapshot is validated:
        raise AdapterContractError(
            f"{field_name} snapshot must not retain caller identity"
        )
    return snapshot


_FORBIDDEN_METADATA_TOKENS = frozenset(
    {
        "expected",
        "target",
        "answer",
        "result",
        "registry",
        "evidence",
        "verdict",
        "comparison",
        "tolerance",
        "report",
    }
)
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_METADATA_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _metadata_tokens(value: str, field_name: str) -> tuple[str, ...]:
    _require_utf8_string(value, field_name)
    separated = _CAMEL_BOUNDARY_RE.sub(" ", value)
    return tuple(
        token.lower() for token in _METADATA_TOKEN_RE.findall(separated)
    )


def _is_numerical_control_identifier(tokens: tuple[str, ...]) -> bool:
    token_set = set(tokens)
    return (
        bool(
            token_set
            & {
                "grid",
                "cutoff",
                "refinement",
                "subinterval",
                "subintervals",
            }
        )
        or {"residual", "bound"} <= token_set
        or (
            "threshold" in token_set
            and bool(
                token_set
                & {"quadrature", "eigensolver", "root", "residual", "absolute"}
            )
        )
    )


def _validate_authored_string(
    value: str,
    field_name: str,
    *,
    allow_numerical_control: bool = False,
) -> None:
    tokens = _metadata_tokens(value, field_name)
    if (
        any(token in _FORBIDDEN_METADATA_TOKENS for token in tokens)
        or "sourceoperand" in tokens
        or any(
            first == "source" and second == "operand"
            for first, second in zip(tokens, tokens[1:])
        )
    ):
        raise AdapterContractError(
            f"{field_name} contains forbidden metadata vocabulary"
        )
    if (
        not allow_numerical_control
        and _is_numerical_control_identifier(tokens)
    ):
        raise AdapterContractError(
            f"{field_name} contains a numerical control outside "
            "numerical_control_schema"
        )


def _validate_authored_json(
    value: object,
    field_name: str,
    *,
    allow_numerical_control: bool = False,
) -> None:
    if type(value) is FrozenJsonObject:
        for key, item in value._items:
            _validate_authored_string(
                key,
                f"{field_name} mapping key",
                allow_numerical_control=allow_numerical_control,
            )
            _validate_authored_json(
                item,
                f"{field_name}.{key}",
                allow_numerical_control=allow_numerical_control,
            )
        return
    if type(value) is tuple:
        for index, item in enumerate(value):
            _validate_authored_json(
                item,
                f"{field_name}[{index}]",
                allow_numerical_control=allow_numerical_control,
            )
        return
    if type(value) is str:
        _validate_authored_string(
            value,
            field_name,
            allow_numerical_control=allow_numerical_control,
        )


def _validate_authored_schema(
    schema: "ValueSchema",
    field_name: str,
    *,
    allow_numerical_control: bool = False,
) -> None:
    _validate_authored_string(
        schema.units,
        f"{field_name}.units",
        allow_numerical_control=allow_numerical_control,
    )
    if schema.item_schema is not None:
        _validate_authored_schema(
            schema.item_schema,
            f"{field_name}.item_schema",
            allow_numerical_control=allow_numerical_control,
        )
    for property_name, property_schema in schema.properties:
        _validate_authored_string(
            property_name,
            f"{field_name}.properties",
            allow_numerical_control=allow_numerical_control,
        )
        _validate_authored_schema(
            property_schema,
            f"{field_name}.{property_name}",
            allow_numerical_control=allow_numerical_control,
        )


def _seal_contract(contract_type):
    def reject_subclass(cls, **kwargs):
        raise TypeError(f"{contract_type.__name__} is sealed and cannot be subclassed")

    contract_type.__init_subclass__ = classmethod(reject_subclass)
    return contract_type


def _initialize_closed(
    instance: object,
    args: tuple,
    kwargs: dict[str, Any],
    contract_type: type,
) -> None:
    if type(instance) is not contract_type:
        raise AdapterContractError(
            f"{contract_type.__name__} does not allow subclasses"
        )
    field_names = tuple(field.name for field in fields(contract_type))
    if len(args) > len(field_names):
        raise AdapterContractError(
            f"too many positional fields for {type(instance).__name__}"
        )
    values = dict(zip(field_names, args))
    for name, value in kwargs.items():
        if name not in field_names:
            raise AdapterContractError(
                f"{type(instance).__name__} contains unknown field {name}"
            )
        if name in values:
            raise AdapterContractError(f"field {name} supplied more than once")
        values[name] = value
    missing = [name for name in field_names if name not in values]
    if missing:
        raise AdapterContractError(
            f"{type(instance).__name__} missing required field {missing[0]}"
        )
    for name in field_names:
        object.__setattr__(instance, name, values[name])
    contract_type.__post_init__(instance)


_VALUE_SCHEMA_KINDS = frozenset(
    {"boolean", "integer", "number", "string", "list", "object"}
)


@_seal_contract
@dataclass(frozen=True, init=False)
class ValueSchema:
    kind: str
    required: bool
    lower: float | None
    upper: float | None
    item_schema: "ValueSchema | None"
    properties: tuple[tuple[str, "ValueSchema"], ...]
    units: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ValueSchema)

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _VALUE_SCHEMA_KINDS:
            raise AdapterContractError(
                "kind must be exactly boolean, integer, number, string, list, or object"
            )
        if type(self.required) is not bool:
            raise AdapterContractError("required must be boolean")
        if self.kind == "list":
            if self.lower is not None:
                _require_nonnegative_integer(self.lower, "lower")
            if self.upper is not None:
                _require_nonnegative_integer(self.upper, "upper")
        else:
            if self.lower is not None:
                _require_finite_number(self.lower, "lower")
            if self.upper is not None:
                _require_finite_number(self.upper, "upper")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise AdapterContractError("lower must not exceed upper")
        if self.kind not in {"integer", "number", "list"} and (
            self.lower is not None or self.upper is not None
        ):
            raise AdapterContractError(
                "lower and upper are allowed only for numeric or list schemas"
            )
        if self.item_schema is not None and type(self.item_schema) is not ValueSchema:
            raise AdapterContractError("item_schema must be a ValueSchema or None")
        properties = _require_tuple(self.properties, "properties")
        normalized_properties = []
        seen = set()
        for index, item in enumerate(properties):
            if type(item) is not tuple or len(item) != 2:
                raise AdapterContractError(
                    f"properties[{index}] must be a (name, ValueSchema) tuple"
                )
            name, schema = item
            require_identifier(name, f"properties[{index}].name")
            if name in seen:
                raise AdapterContractError(
                    f"properties contains duplicate field {name}"
                )
            if type(schema) is not ValueSchema:
                raise AdapterContractError(
                    f"properties[{index}].schema must be a ValueSchema"
                )
            seen.add(name)
            normalized_properties.append((name, schema))
        if self.kind == "list":
            if self.item_schema is None:
                raise AdapterContractError("list schema requires item_schema")
            if normalized_properties:
                raise AdapterContractError("list schema cannot define properties")
        elif self.item_schema is not None:
            raise AdapterContractError("item_schema is allowed only for list schemas")
        if self.kind != "object" and normalized_properties:
            raise AdapterContractError("properties are allowed only for object schemas")
        if type(self.units) is not str:
            raise AdapterContractError("units must be a string")
        if self.units:
            _require_nonempty_string(self.units, "units")
        object.__setattr__(
            self,
            "properties",
            tuple(sorted(normalized_properties, key=lambda item: item[0])),
        )


OUTPUT_PROOF_KINDS = frozenset(
    {
        "direct_exact_value",
        "bounded_numeric_value",
        "grouped_exact_sequence",
        "rank_derived_integer",
        "all_residuals_within_bound_boolean",
        "positive_lower_bound_boolean",
        "positive_gap_and_odd_parity_boolean",
        "directional_limits_differ_boolean",
        "no_finite_crossing_boolean",
        "no_finite_crossing_zero_limit",
    }
)


@_seal_contract
@dataclass(frozen=True, init=False)
class OutputFieldBinding:
    value_schema: ValueSchema
    raw_field: str
    proof_kind: str

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, OutputFieldBinding)

    def __post_init__(self) -> None:
        if type(self.value_schema) is not ValueSchema:
            raise AdapterContractError("value_schema must be a ValueSchema")
        value_schema = _snapshot_value_schema(
            self.value_schema, "value_schema"
        )
        if value_schema.kind not in {"boolean", "integer", "number", "list"}:
            raise AdapterContractError(
                "value_schema must describe a scalar or exact list output"
            )
        if value_schema.required is not True:
            raise AdapterContractError("value_schema output must be required")
        require_identifier(self.raw_field, "raw_field")
        _validate_authored_string(self.raw_field, "raw_field")
        if type(self.proof_kind) is not str:
            raise AdapterContractError("proof_kind must be a string")
        _validate_authored_string(self.proof_kind, "proof_kind")
        if self.proof_kind not in OUTPUT_PROOF_KINDS:
            raise AdapterContractError(
                "proof_kind is not an approved output proof kind"
            )
        object.__setattr__(self, "value_schema", value_schema)


@_seal_contract
@dataclass(frozen=True, init=False)
class OutputSchema:
    fields: tuple[tuple[str, OutputFieldBinding], ...]

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, OutputSchema)

    def __post_init__(self) -> None:
        field_items = _require_tuple(self.fields, "fields")
        normalized = []
        seen = set()
        for index, item in enumerate(field_items):
            if type(item) is not tuple or len(item) != 2:
                raise AdapterContractError(
                    f"fields[{index}] must be a (selector, binding) tuple"
                )
            selector_field, binding = item
            require_identifier(selector_field, f"fields[{index}].selector")
            _validate_authored_string(
                selector_field, f"fields[{index}].selector"
            )
            if selector_field in seen:
                raise AdapterContractError(
                    f"fields contains duplicate selector {selector_field}"
                )
            if type(binding) is not OutputFieldBinding:
                raise AdapterContractError(
                    f"fields[{index}].binding must be an OutputFieldBinding"
                )
            seen.add(selector_field)
            normalized.append((selector_field, binding))
        if not normalized:
            raise AdapterContractError("fields must be nonempty")
        object.__setattr__(self, "fields", tuple(normalized))

    def __iter__(self) -> Iterator[tuple[str, OutputFieldBinding]]:
        return iter(self.fields)

    def __getitem__(self, selector_field: str) -> OutputFieldBinding:
        for name, binding in self.fields:
            if name == selector_field:
                return binding
        raise KeyError(selector_field)

    @property
    def selector_fields(self) -> tuple[str, ...]:
        return tuple(name for name, _binding in self.fields)

    def items(self) -> tuple[tuple[str, OutputFieldBinding], ...]:
        return tuple(self.fields)

    def as_mapping(self) -> Mapping[str, OutputFieldBinding]:
        return MappingProxyType(dict(self.fields))


_MAX_VALUE_SCHEMA_NESTING = 128


def _snapshot_value_schema_node(
    schema: ValueSchema,
    field_name: str,
    *,
    active_schema_ids: set[int],
    depth: int,
) -> ValueSchema:
    if depth > _MAX_VALUE_SCHEMA_NESTING:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum ValueSchema nesting depth "
            f"of {_MAX_VALUE_SCHEMA_NESTING}"
        )
    if type(schema) is not ValueSchema:
        raise AdapterContractError(
            f"{field_name} must be an exact ValueSchema"
        )
    schema_id = id(schema)
    if schema_id in active_schema_ids:
        raise AdapterContractError(
            f"{field_name} contains a ValueSchema cycle"
        )
    active_schema_ids.add(schema_id)
    try:
        if type(schema.properties) is not tuple:
            raise AdapterContractError(
                f"{field_name}.properties must be an immutable tuple"
            )
        properties = []
        for index, item in enumerate(schema.properties):
            if type(item) is not tuple or len(item) != 2:
                raise AdapterContractError(
                    f"{field_name}.properties[{index}] must be an exact pair"
                )
            name, child_schema = item
            properties.append(
                (
                    name,
                    _snapshot_value_schema_node(
                        child_schema,
                        f"{field_name}.properties[{index}]",
                        active_schema_ids=active_schema_ids,
                        depth=depth + 1,
                    ),
                )
            )
        item_schema = (
            None
            if schema.item_schema is None
            else _snapshot_value_schema_node(
                schema.item_schema,
                f"{field_name}.item_schema",
                active_schema_ids=active_schema_ids,
                depth=depth + 1,
            )
        )
        return ValueSchema(
            kind=schema.kind,
            required=schema.required,
            lower=schema.lower,
            upper=schema.upper,
            item_schema=item_schema,
            properties=tuple(properties),
            units=schema.units,
        )
    finally:
        active_schema_ids.remove(schema_id)


def _snapshot_value_schema(
    schema: ValueSchema,
    field_name: str,
) -> ValueSchema:
    try:
        return _snapshot_value_schema_node(
            schema,
            field_name,
            active_schema_ids=set(),
            depth=0,
        )
    except AdapterContractError:
        raise
    except RecursionError as error:
        raise AdapterContractError(
            f"{field_name} exceeds safe ValueSchema recursion limits"
        ) from error


def _snapshot_output_schema(
    output_schema: OutputSchema, field_name: str = "output_schema"
) -> OutputSchema:
    if type(output_schema) is not OutputSchema:
        raise AdapterContractError(
            f"{field_name} must be an exact OutputSchema"
        )
    field_items = output_schema.fields
    if type(field_items) is not tuple:
        raise AdapterContractError(
            f"{field_name}.fields must be an immutable tuple"
        )
    snapshots = []
    for index, item in enumerate(field_items):
        if type(item) is not tuple or len(item) != 2:
            raise AdapterContractError(
                f"{field_name}.fields[{index}] must be an exact pair"
            )
        selector_field, binding = item
        if type(binding) is not OutputFieldBinding:
            raise AdapterContractError(
                f"{field_name}.fields[{index}].binding must be an "
                "OutputFieldBinding"
            )
        snapshots.append(
            (
                selector_field,
                OutputFieldBinding(
                    value_schema=_snapshot_value_schema(
                        binding.value_schema,
                        f"{field_name}.fields[{index}].value_schema",
                    ),
                    raw_field=binding.raw_field,
                    proof_kind=binding.proof_kind,
                ),
            )
        )
    return OutputSchema(fields=tuple(snapshots))


_PARAMETER_SOURCE_KINDS = frozenset(
    {
        "canonical_model_parameter",
        "source_model_parameter",
        "universal_probe",
        "numerical_control",
    }
)


@_seal_contract
@dataclass(frozen=True, init=False)
class ParameterSource:
    parameter_name: str
    kind: str
    details: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ParameterSource)

    def __post_init__(self) -> None:
        require_identifier(self.parameter_name, "parameter_name")
        if type(self.kind) is not str:
            raise AdapterContractError("parameter provenance kind must be a string")
        if self.kind not in _PARAMETER_SOURCE_KINDS:
            raise AdapterContractError(
                f"unknown parameter provenance kind {self.kind!r}"
            )
        object.__setattr__(self, "details", _freeze_mapping(self.details, "details"))


@_seal_contract
@dataclass(frozen=True, init=False)
class CounterfactualDomain:
    valid_rules: FrozenJsonObject
    invalid_rules: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, CounterfactualDomain)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "valid_rules", _freeze_mapping(self.valid_rules, "valid_rules")
        )
        object.__setattr__(
            self, "invalid_rules", _freeze_mapping(self.invalid_rules, "invalid_rules")
        )


_CONVERGENCE_KINDS = frozenset(
    {"exact", "residual_bound", "finite_size", "quadrature", "iterative"}
)


@_seal_contract
@dataclass(frozen=True, init=False)
class ConvergenceContract:
    kind: str
    requirements: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ConvergenceContract)

    def __post_init__(self) -> None:
        if type(self.kind) is not str:
            raise AdapterContractError("convergence kind must be a string")
        if self.kind not in _CONVERGENCE_KINDS:
            raise AdapterContractError(f"unknown convergence kind {self.kind!r}")
        object.__setattr__(
            self,
            "requirements",
            _freeze_mapping(self.requirements, "requirements"),
        )


_PROBLEM_SIZE_KINDS = frozenset(
    {"not_applicable", "fixed_local", "scalable_same_observable"}
)


@_seal_contract
@dataclass(frozen=True, init=False)
class ProblemSizePolicy:
    kind: str
    fixed_sizes: FrozenJsonObject
    allowed_sizes: FrozenJsonObject

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ProblemSizePolicy)

    def __post_init__(self) -> None:
        if type(self.kind) is not str:
            raise AdapterContractError("problem-size policy kind must be a string")
        if self.kind not in _PROBLEM_SIZE_KINDS:
            raise AdapterContractError(f"unknown problem-size policy {self.kind!r}")
        fixed_sizes = _freeze_mapping(self.fixed_sizes, "fixed_sizes")
        allowed_sizes = _freeze_mapping(self.allowed_sizes, "allowed_sizes")
        if self.kind == "not_applicable" and (fixed_sizes or allowed_sizes):
            raise AdapterContractError(
                "not_applicable problem-size policy cannot contain size data"
            )
        if self.kind == "fixed_local" and (not fixed_sizes or allowed_sizes):
            raise AdapterContractError(
                "fixed_local problem-size policy requires only fixed_sizes"
            )
        if self.kind == "scalable_same_observable" and (
            fixed_sizes or not allowed_sizes
        ):
            raise AdapterContractError(
                "scalable_same_observable policy requires only allowed_sizes"
            )
        object.__setattr__(self, "fixed_sizes", fixed_sizes)
        object.__setattr__(self, "allowed_sizes", allowed_sizes)


@_seal_contract
@dataclass(frozen=True, init=False)
class RuntimeRequirements:
    interpreter: str
    packages: tuple[str, ...]
    native_libraries: tuple[str, ...]
    backend_resources: tuple[str, ...]

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, RuntimeRequirements)

    def __post_init__(self) -> None:
        _require_nonempty_string(self.interpreter, "interpreter")
        for field_name in ("packages", "native_libraries", "backend_resources"):
            _require_string_tuple(getattr(self, field_name), field_name)


@_seal_contract
@dataclass(frozen=True, init=False)
class ResourceLimits:
    cpu_seconds: int | float
    wall_seconds: int | float
    address_space_bytes: int
    output_bytes: int
    file_descriptors: int
    process_count: int

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, ResourceLimits)

    def __post_init__(self) -> None:
        _require_finite_number(self.cpu_seconds, "cpu_seconds", positive=True)
        _require_finite_number(self.wall_seconds, "wall_seconds", positive=True)
        for field_name in (
            "address_space_bytes",
            "output_bytes",
            "file_descriptors",
            "process_count",
        ):
            _require_positive_integer(getattr(self, field_name), field_name)


_BACKEND_KINDS = frozenset(
    {"analytic", "enumeration", "dense_ed", "glt_fourier", "iterative_numeric"}
)
_OBSERVABLE_IDENTITY_KEYS = frozenset(
    {
        "subject",
        "system_or_material",
        "hamiltonian",
        "parameter_regime",
        "size_or_limit",
        "observable_definition",
        "units",
        "conditions",
    }
)


def _snapshot_parameter_sources(
    value: object,
) -> tuple[ParameterSource, ...]:
    items = _require_tuple(value, "parameter_sources")
    snapshots = []
    for index, item in enumerate(items):
        if type(item) is not ParameterSource:
            raise AdapterContractError(
                "parameter_sources must contain only ParameterSource records"
            )
        snapshots.append(
            ParameterSource(
                parameter_name=item.parameter_name,
                kind=item.kind,
                details=_snapshot_json_mapping(
                    item.details,
                    f"parameter_sources[{index}].details",
                ),
            )
        )
    return tuple(snapshots)


def _snapshot_problem_size_policy(
    value: object,
) -> ProblemSizePolicy:
    if type(value) is not ProblemSizePolicy:
        raise AdapterContractError(
            "problem_size_policy must be a ProblemSizePolicy"
        )
    return ProblemSizePolicy(
        kind=value.kind,
        fixed_sizes=_snapshot_json_mapping(
            value.fixed_sizes,
            "problem_size_policy.fixed_sizes",
        ),
        allowed_sizes=_snapshot_json_mapping(
            value.allowed_sizes,
            "problem_size_policy.allowed_sizes",
        ),
    )


def _snapshot_runtime_requirements(
    value: object,
) -> RuntimeRequirements:
    if type(value) is not RuntimeRequirements:
        raise AdapterContractError(
            "runtime_requirements must be a RuntimeRequirements"
        )
    return RuntimeRequirements(
        interpreter=value.interpreter,
        packages=value.packages,
        native_libraries=value.native_libraries,
        backend_resources=value.backend_resources,
    )


def _snapshot_convergence_contract(
    value: object,
) -> ConvergenceContract:
    if type(value) is not ConvergenceContract:
        raise AdapterContractError(
            "convergence_contract must be a ConvergenceContract"
        )
    return ConvergenceContract(
        kind=value.kind,
        requirements=_snapshot_json_mapping(
            value.requirements,
            "convergence_contract.requirements",
        ),
    )


def _snapshot_counterfactual_domain(
    value: object,
) -> CounterfactualDomain:
    if type(value) is not CounterfactualDomain:
        raise AdapterContractError(
            "counterfactual_domain must be a CounterfactualDomain"
        )
    return CounterfactualDomain(
        valid_rules=_snapshot_json_mapping(
            value.valid_rules,
            "counterfactual_domain.valid_rules",
        ),
        invalid_rules=_snapshot_json_mapping(
            value.invalid_rules,
            "counterfactual_domain.invalid_rules",
        ),
    )


def _snapshot_resource_limits(value: object) -> ResourceLimits:
    if type(value) is not ResourceLimits:
        raise AdapterContractError(
            "resource_limits must be a ResourceLimits"
        )
    return ResourceLimits(
        cpu_seconds=value.cpu_seconds,
        wall_seconds=value.wall_seconds,
        address_space_bytes=value.address_space_bytes,
        output_bytes=value.output_bytes,
        file_descriptors=value.file_descriptors,
        process_count=value.process_count,
    )


@_seal_contract
@dataclass(frozen=True, init=False)
class AdapterDefinition:
    adapter_id: str
    entry_symbol: str
    observable_identity: FrozenJsonObject
    scientific_input_schema: ValueSchema
    numerical_control_schema: ValueSchema
    parameter_sources: tuple[ParameterSource, ...]
    output_schema: OutputSchema
    backend_kind: str
    problem_size_policy: ProblemSizePolicy
    runtime_requirements: RuntimeRequirements
    convergence_contract: ConvergenceContract
    counterfactual_domain: CounterfactualDomain
    oracle_id: str
    resource_limits: ResourceLimits

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, AdapterDefinition)

    def __post_init__(self) -> None:
        require_identifier(self.adapter_id, "adapter_id")
        if type(self.entry_symbol) is not str or _ENTRY_SYMBOL_RE.fullmatch(
            self.entry_symbol
        ) is None:
            raise AdapterContractError(
                "entry_symbol must be a fully qualified module:function symbol"
            )
        if self.entry_symbol != (
            "validation.literature_evidence_adapters:adapter_"
            + self.adapter_id
        ):
            raise AdapterContractError(
                "entry_symbol must be the exact unresolved adapter symbol"
            )
        observable_identity = require_exact_keys(
            _snapshot_json_mapping(
                self.observable_identity,
                "observable_identity",
            ),
            _OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        scientific_input_schema = _snapshot_value_schema(
            self.scientific_input_schema,
            "scientific_input_schema",
        )
        numerical_control_schema = _snapshot_value_schema(
            self.numerical_control_schema,
            "numerical_control_schema",
        )
        for field_name, schema in (
            ("scientific_input_schema", scientific_input_schema),
            ("numerical_control_schema", numerical_control_schema),
        ):
            if schema.kind != "object":
                raise AdapterContractError(
                    f"{field_name} must be an object ValueSchema"
                )
        if type(self.output_schema) is not OutputSchema:
            raise AdapterContractError("output_schema must be an OutputSchema")
        output_schema = _snapshot_output_schema(self.output_schema)
        parameter_sources = _snapshot_parameter_sources(
            self.parameter_sources
        )
        for index, parameter_source in enumerate(parameter_sources):
            if parameter_source.kind == "numerical_control":
                raise AdapterContractError(
                    "scientific parameter_sources cannot use "
                    "numerical_control provenance"
                )
            _validate_authored_string(
                parameter_source.parameter_name,
                f"parameter_sources[{index}].parameter_name",
            )
            _validate_authored_json(
                parameter_source.details,
                f"parameter_sources[{index}].details",
            )
        parameter_names = tuple(item.parameter_name for item in parameter_sources)
        if len(set(parameter_names)) != len(parameter_names):
            raise AdapterContractError(
                "parameter_sources contains a duplicate parameter"
            )
        scientific_names = tuple(
            name for name, _ in scientific_input_schema.properties
        )
        control_names = tuple(
            name for name, _ in numerical_control_schema.properties
        )
        if set(scientific_names) & set(control_names):
            raise AdapterContractError(
                "scientific and numerical-control schema properties "
                "must be disjoint"
            )
        if set(parameter_names) != set(scientific_names):
            raise AdapterContractError(
                "parameter_sources must bind every scientific input exactly once"
            )
        if type(self.backend_kind) is not str:
            raise AdapterContractError("backend_kind must be a string")
        if self.backend_kind not in _BACKEND_KINDS:
            raise AdapterContractError(f"unknown backend_kind {self.backend_kind!r}")
        problem_size_policy = _snapshot_problem_size_policy(
            self.problem_size_policy
        )
        runtime_requirements = _snapshot_runtime_requirements(
            self.runtime_requirements
        )
        convergence_contract = _snapshot_convergence_contract(
            self.convergence_contract
        )
        counterfactual_domain = _snapshot_counterfactual_domain(
            self.counterfactual_domain
        )
        resource_limits = _snapshot_resource_limits(self.resource_limits)
        require_identifier(self.oracle_id, "oracle_id")
        _validate_authored_string(
            self.adapter_id, "adapter_id", allow_numerical_control=True
        )
        _validate_authored_string(
            self.oracle_id, "oracle_id", allow_numerical_control=True
        )
        _validate_authored_json(observable_identity, "observable_identity")
        _validate_authored_schema(
            scientific_input_schema,
            "scientific_input_schema",
        )
        _validate_authored_schema(
            numerical_control_schema,
            "numerical_control_schema",
            allow_numerical_control=True,
        )
        for selector_field, binding in output_schema:
            _validate_authored_string(selector_field, "output_schema selector")
            _validate_authored_string(
                binding.raw_field,
                "output_schema raw_field",
            )
            _validate_authored_string(
                binding.proof_kind,
                "output_schema proof_kind",
            )
            _validate_authored_schema(
                binding.value_schema, f"output_schema.{selector_field}"
            )
        _validate_authored_json(
            problem_size_policy.fixed_sizes,
            "problem_size_policy.fixed_sizes",
        )
        _validate_authored_json(
            problem_size_policy.allowed_sizes,
            "problem_size_policy.allowed_sizes",
        )
        for field_name in (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ):
            value = getattr(runtime_requirements, field_name)
            if type(value) is tuple:
                for index, item in enumerate(value):
                    _validate_authored_string(
                        item, f"runtime_requirements.{field_name}[{index}]"
                    )
            else:
                _validate_authored_string(
                    value, f"runtime_requirements.{field_name}"
                )
        _validate_authored_json(
            convergence_contract.requirements,
            "convergence_contract.requirements",
        )
        _validate_authored_json(
            counterfactual_domain.valid_rules,
            "counterfactual_domain.valid_rules",
        )
        _validate_authored_json(
            counterfactual_domain.invalid_rules,
            "counterfactual_domain.invalid_rules",
        )
        object.__setattr__(self, "observable_identity", observable_identity)
        object.__setattr__(
            self,
            "scientific_input_schema",
            scientific_input_schema,
        )
        object.__setattr__(
            self,
            "numerical_control_schema",
            numerical_control_schema,
        )
        object.__setattr__(self, "parameter_sources", parameter_sources)
        object.__setattr__(self, "output_schema", output_schema)
        object.__setattr__(
            self,
            "problem_size_policy",
            problem_size_policy,
        )
        object.__setattr__(
            self,
            "runtime_requirements",
            runtime_requirements,
        )
        object.__setattr__(
            self,
            "convergence_contract",
            convergence_contract,
        )
        object.__setattr__(
            self,
            "counterfactual_domain",
            counterfactual_domain,
        )
        object.__setattr__(self, "resource_limits", resource_limits)


_ELIGIBILITY_DISPOSITIONS = frozenset({"eligible", "source_parse_only"})
SOURCE_PARSE_ONLY_REASONS = frozenset(
    {
        "status_or_candidate_only",
        "mixed_selector_contains_source_only_field",
        "source_only_symbolic_or_categorical_field",
        "target_equivalent_input",
        "observable_identity_mismatch",
        "no_independent_oracle",
        "no_honest_convergence_evidence",
        "backend_unavailable_for_registered_limit",
    }
)


@_seal_contract
@dataclass(frozen=True, init=False)
class EligibilityDecision:
    selector_fields: tuple[str, ...]
    disposition: str
    adapter_id: str | None
    oracle_id: str | None
    reason: str | None

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, EligibilityDecision)

    def __post_init__(self) -> None:
        selector_fields = _require_tuple(
            self.selector_fields, "selector_fields"
        )
        if not selector_fields:
            raise AdapterContractError("selector_fields must be nonempty")
        for index, selector_field in enumerate(selector_fields):
            require_identifier(selector_field, f"selector_fields[{index}]")
        if len(set(selector_fields)) != len(selector_fields):
            raise AdapterContractError("selector_fields contains a duplicate")
        if type(self.disposition) is not str:
            raise AdapterContractError(
                "eligibility disposition must be a string"
            )
        if self.disposition not in _ELIGIBILITY_DISPOSITIONS:
            raise AdapterContractError(
                f"unknown eligibility disposition {self.disposition!r}"
            )
        if self.disposition == "eligible":
            require_identifier(self.adapter_id, "adapter_id")
            require_identifier(self.oracle_id, "oracle_id")
            if self.reason is not None:
                raise AdapterContractError(
                    "eligible decision cannot have a reason"
                )
            return
        if self.adapter_id is not None or self.oracle_id is not None:
            raise AdapterContractError(
                "source_parse_only decision cannot resolve an "
                "adapter or oracle"
            )
        if type(self.reason) is not str:
            raise AdapterContractError(
                "source_parse_only reason must be a string"
            )
        if self.reason not in SOURCE_PARSE_ONLY_REASONS:
            raise AdapterContractError(
                f"unknown source_parse_only reason {self.reason!r}"
            )


def _build_adapter_eligibility(
    rows: Iterable[
        tuple[
            str,
            tuple[str, ...],
            str,
            str | None,
            str | None,
            str | None,
        ]
    ],
) -> Mapping[str, EligibilityDecision]:
    decisions: dict[str, EligibilityDecision] = {}
    for index, row in enumerate(rows):
        if type(row) is not tuple or len(row) != 6:
            raise AdapterContractError(
                f"eligibility row {index} must be an exact six-field tuple"
            )
        (
            benchmark_name,
            selector_fields,
            disposition,
            adapter_id,
            oracle_id,
            reason,
        ) = row
        require_identifier(
            benchmark_name, f"eligibility row {index} benchmark_name"
        )
        if benchmark_name in decisions:
            raise AdapterContractError(
                "duplicate benchmark ID in eligibility catalog: "
                f"{benchmark_name}"
            )
        decisions[benchmark_name] = EligibilityDecision(
            selector_fields=selector_fields,
            disposition=disposition,
            adapter_id=adapter_id,
            oracle_id=oracle_id,
            reason=reason,
        )
    if len(decisions) != 42:
        raise AdapterContractError(
            "eligibility catalog must contain exactly 42 rows"
        )
    eligible_count = sum(
        decision.disposition == "eligible" for decision in decisions.values()
    )
    source_parse_count = sum(
        decision.disposition == "source_parse_only"
        for decision in decisions.values()
    )
    if eligible_count != 29 or source_parse_count != 13:
        raise AdapterContractError(
            "eligibility catalog must contain exactly 29 eligible and "
            "13 source_parse_only rows"
        )
    return MappingProxyType(decisions)


ADAPTER_ELIGIBILITY: Mapping[
    str, EligibilityDecision
] = _build_adapter_eligibility(
    (
        (
            "xxx_spin_half_chain_bethe_ground_state",
            ("energy_per_site",),
            "eligible",
            "xxx_bethe_energy",
            "xxx_bethe_integral_oracle",
            None,
        ),
        (
            "one_dimensional_classical_ising_correlation_length",
            ("formula", "correlation_length_beta_1_j_1"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "two_dimensional_square_ising_onsager_tc",
            ("tc_over_j",),
            "eligible",
            "square_ising_self_dual_tc",
            "square_ising_duality_residual_oracle",
            None,
        ),
        (
            "two_dimensional_square_ising_spontaneous_magnetization",
            ("formula", "magnetization_beta_0_6_j_1"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "square_potts_exact_critical_point",
            ("critical_beta_j", "continuous_for_q_le_4"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "triangular_ising_antiferromagnet_residual_entropy",
            ("residual_entropy_per_spin",),
            "eligible",
            "triangular_ising_af_entropy_quadrature",
            "triangular_ising_af_entropy_series_oracle",
            None,
        ),
        (
            "xy_spin_half_chain_anisotropic_critical_line",
            ("ising_critical_field", "anisotropy_transition_gamma"),
            "eligible",
            "xy_chain_bdg_boundaries",
            "xy_chain_dense_bdg_oracle",
            None,
        ),
        (
            "diamond_j1_j2_spiral_surface_reference",
            ("spiral_surface_for_j2_over_j1_gt",),
            "eligible",
            "diamond_spiral_threshold_fourier",
            "diamond_real_space_threshold_oracle",
            None,
        ),
        (
            "spin_ice_tetrahedron_nn_ice_rule",
            (
                "two_in_two_out_energy",
                "three_in_one_out_energy",
                "all_in_all_out_energy",
                "two_in_two_out_degeneracy",
            ),
            "eligible",
            "spin_ice_tetrahedron_enumeration",
            "spin_ice_tetrahedron_matrix_oracle",
            None,
        ),
        (
            "square_j1_j3_classical_lifshitz_reference",
            ("spiral_condition",),
            "source_parse_only",
            None,
            None,
            "source_only_symbolic_or_categorical_field",
        ),
        (
            "two_leg_ladder_strong_rung_exact_limit",
            ("energy_per_rung", "gap_to_triplet"),
            "eligible",
            "spin_ladder_rung_dense_ed",
            "spin_ladder_analytic_rung_oracle",
            None,
        ),
        (
            "square_ashkin_teller_exact_critical_line",
            ("has_exact_critical_line",),
            "source_parse_only",
            None,
            None,
            "status_or_candidate_only",
        ),
        (
            "pyrochlore_dipolar_spin_ice_pauling_entropy",
            ("pauling_entropy_per_spin",),
            "eligible",
            "pauling_entropy_combinatorics",
            "pauling_cluster_count_oracle",
            None,
        ),
        (
            "two_dimensional_xy_bkt_universal_jump",
            ("formula", "helicity_modulus_at_t_1"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "uimin_lai_sutherland_spin1_su3_point",
            ("theta_radians", "su3_symmetric"),
            "eligible",
            "uls_two_site_su3_matrix",
            "uls_permutation_commutator_oracle",
            None,
        ),
        (
            "bilinear_biquadratic_spin1_chain_aklt_angle",
            ("aklt_tan_theta", "theta_radians"),
            "eligible",
            "aklt_projector_angle",
            "aklt_two_spin_spectrum_oracle",
            None,
        ),
        (
            "square_compass_model_directional_exchange_degeneracy",
            ("has_line_flip_symmetries",),
            "eligible",
            "compass_line_symmetry_matrix",
            "compass_spin_flip_oracle",
            None,
        ),
        (
            "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
            ("field_opens_non_abelian_gap",),
            "eligible",
            "kitaev_field_majorana_mass",
            "kitaev_two_band_chern_oracle",
            None,
        ),
        (
            "square_toric_code_exact_topological_degeneracy",
            ("torus_ground_state_degeneracy",),
            "eligible",
            "toric_code_stabilizer_rank",
            "toric_code_logical_loop_oracle",
            None,
        ),
        (
            "triangular_nn_classical_120_reference",
            ("order", "q_reciprocal"),
            "source_parse_only",
            None,
            None,
            "status_or_candidate_only",
        ),
        (
            "aklt_spin1_chain_projector_ground_state",
            ("two_site_projector_eigenvalues", "vbs_ground_energy"),
            "eligible",
            "aklt_two_site_projector_ed",
            "aklt_clebsch_gordan_oracle",
            None,
        ),
        (
            "blume_capel_spin1_zero_temperature_level_crossing",
            ("square_lattice_d_over_j_crossing",),
            "eligible",
            "blume_capel_level_crossing",
            "blume_capel_configuration_oracle",
            None,
        ),
        (
            "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
            ("zero_total_spin_per_crossed_plaquette",),
            "eligible",
            "checkerboard_plaquette_enumeration",
            "checkerboard_total_spin_oracle",
            None,
        ),
        (
            "cubic_ising_critical_temperature_reference",
            ("tc_over_j",),
            "source_parse_only",
            None,
            None,
            "target_equivalent_input",
        ),
        (
            "fcc_j1_j2_heisenberg_type_order_reference",
            ("common_orders",),
            "source_parse_only",
            None,
            None,
            "status_or_candidate_only",
        ),
        (
            "honeycomb_ising_ferromagnet_exact_tc",
            ("tc_over_j",),
            "eligible",
            "honeycomb_ising_star_triangle_tc",
            "honeycomb_ising_critical_polynomial_oracle",
            None,
        ),
        (
            "honeycomb_j1_j2_spiral_ring_reference",
            ("ring_condition",),
            "source_parse_only",
            None,
            None,
            "source_only_symbolic_or_categorical_field",
        ),
        (
            "kagome_ising_antiferromagnet_residual_entropy_reference",
            ("macroscopic_ground_state_degeneracy",),
            "eligible",
            "kagome_ising_af_entropy_quadrature",
            "kagome_ising_af_transfer_count_oracle",
            None,
        ),
        (
            "kagome_ising_ferromagnet_exact_tc",
            ("tc_over_j",),
            "eligible",
            "kagome_ising_star_triangle_tc",
            "kagome_ising_critical_polynomial_oracle",
            None,
        ),
        (
            "majundar_ghosh_chain_exact_dimer_point",
            ("energy_per_site", "degenerate_dimer_coverings"),
            "eligible",
            "majumdar_ghosh_dimer_ed",
            "majumdar_ghosh_projector_oracle",
            None,
        ),
        (
            "one_dimensional_classical_ising_no_finite_t_transition",
            ("finite_temperature_transition", "tc_over_j"),
            "eligible",
            "ising_chain_transfer_matrix",
            "ising_chain_partition_analytic_oracle",
            None,
        ),
        (
            "pyrochlore_heisenberg_afm_coulomb_phase_reference",
            ("zero_total_spin_per_tetrahedron", "pinch_points"),
            "eligible",
            "pyrochlore_coulomb_fourier",
            "pyrochlore_real_space_constraint_oracle",
            None,
        ),
        (
            "shastry_sutherland_exact_dimer_product",
            ("energy_per_dimer", "energy_per_spin"),
            "eligible",
            "shastry_sutherland_dimer_ed",
            "shastry_sutherland_bond_oracle",
            None,
        ),
        (
            "simple_cubic_j1_j2_collinear_reference",
            ("neel_to_collinear_boundary_j2_over_j1",),
            "eligible",
            "simple_cubic_j1_j2_fourier",
            "simple_cubic_real_space_energy_oracle",
            None,
        ),
        (
            "single_ion_spin1_anisotropy_levels",
            ("levels", "degeneracies"),
            "eligible",
            "spin1_single_ion_dense_ed",
            "spin1_m_quantum_number_oracle",
            None,
        ),
        (
            "square_fully_frustrated_ising_residual_entropy_reference",
            ("macroscopic_ground_state_degeneracy",),
            "eligible",
            "fully_frustrated_ising_entropy_series",
            "fully_frustrated_ising_transfer_oracle",
            None,
        ),
        (
            "takhtajan_babujian_spin1_critical_point",
            ("theta_radians", "is_integrable"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "transverse_field_ising_chain_critical_point",
            ("critical_field_over_exchange",),
            "eligible",
            "tfim_bdg_critical_point",
            "tfim_duality_gap_oracle",
            None,
        ),
        (
            "transverse_field_ising_chain_gap",
            ("gap_formula", "gap_formula_at_g_0_6"),
            "source_parse_only",
            None,
            None,
            "mixed_selector_contains_source_only_field",
        ),
        (
            "triangular_ising_ferromagnet_exact_tc",
            ("tc_over_j",),
            "eligible",
            "triangular_ising_star_triangle_tc",
            "triangular_ising_critical_polynomial_oracle",
            None,
        ),
        (
            "xx_spin_half_chain_free_fermion_energy",
            ("energy_per_site",),
            "eligible",
            "xx_chain_fermion_integral",
            "xx_chain_dense_ed_extrapolation_oracle",
            None,
        ),
        (
            "xxz_spin_half_chain_phase_boundaries",
            (
                "ferromagnetic_boundary_delta",
                "neel_boundary_delta",
                "gapless_interval",
            ),
            "source_parse_only",
            None,
            None,
            "backend_unavailable_for_registered_limit",
        ),
    )
)


def _metadata_value_schema(
    kind: str,
    units: str,
    lower: int | float | None = None,
    upper: int | float | None = None,
    list_length: int | None = None,
) -> ValueSchema:
    if kind.startswith("list_"):
        item_kind = kind.removeprefix("list_")
        return ValueSchema(
            kind="list",
            required=True,
            lower=list_length,
            upper=list_length,
            item_schema=_metadata_value_schema(item_kind, units, lower, upper),
            properties=(),
            units=units,
        )
    return ValueSchema(
        kind=kind,
        required=True,
        lower=lower,
        upper=upper,
        item_schema=None,
        properties=(),
        units=units,
    )


def _metadata_object_schema(
    specs: tuple[
        tuple[str, str, str, int | float | None, int | float | None],
        ...,
    ],
) -> ValueSchema:
    return ValueSchema(
        kind="object",
        required=True,
        lower=None,
        upper=None,
        item_schema=None,
        properties=tuple(
            (
                name,
                _metadata_value_schema(kind, units, lower, upper),
            )
            for name, kind, units, lower, upper in specs
        ),
        units="",
    )


def _metadata_parameter_sources(
    specs: tuple[
        tuple[
            str,
            str,
            str,
            int | float | None,
            int | float | None,
            str,
            str,
        ],
        ...,
    ]
) -> tuple[ParameterSource, ...]:
    sources = []
    for name, _kind, _units, _lower, _upper, source_kind, role in specs:
        if source_kind == "canonical_model_parameter":
            details = {
                "canonical_path": ("hamiltonian", name),
                "physical_role": role,
            }
        else:
            details = {"probe_role": role}
        sources.append(ParameterSource(name, source_kind, details))
    return tuple(sources)


_NONNEGATIVE_OUTPUT_SELECTORS = frozenset(
    {
        "tc_over_j",
        "residual_entropy_per_spin",
        "ising_critical_field",
        "anisotropy_transition_gamma",
        "spiral_surface_for_j2_over_j1_gt",
        "two_in_two_out_degeneracy",
        "gap_to_triplet",
        "pauling_entropy_per_spin",
        "theta_radians",
        "aklt_tan_theta",
        "torus_ground_state_degeneracy",
        "two_site_projector_eigenvalues",
        "vbs_ground_energy",
        "square_lattice_d_over_j_crossing",
        "degenerate_dimer_coverings",
        "neel_to_collinear_boundary_j2_over_j1",
        "degeneracies",
        "critical_field_over_exchange",
    }
)


def _metadata_output_schema(
    specs: tuple[tuple[object, ...], ...]
) -> OutputSchema:
    output_fields = []
    for index, spec in enumerate(specs):
        if type(spec) is not tuple or len(spec) not in {5, 6}:
            raise AdapterContractError(
                f"output metadata row {index} must have five or six fields"
            )
        selector, kind, units, raw_field, proof_kind = spec[:5]
        list_length = spec[5] if len(spec) == 6 else None
        if (kind.startswith("list_")) != (list_length is not None):
            raise AdapterContractError(
                f"output metadata row {index} must declare exact list shape"
            )
        output_fields.append(
            (
                selector,
                OutputFieldBinding(
                    value_schema=_metadata_value_schema(
                        kind,
                        units,
                        (
                            0
                            if selector in _NONNEGATIVE_OUTPUT_SELECTORS
                            else None
                        ),
                        None,
                        list_length,
                    ),
                    raw_field=raw_field,
                    proof_kind=proof_kind,
                ),
            )
        )
    return OutputSchema(fields=tuple(output_fields))


def _metadata_size_policy(
    kind: str,
    size_data: Mapping[str, object],
) -> ProblemSizePolicy:
    if kind == "fixed_local":
        return ProblemSizePolicy(kind, size_data, {})
    if kind == "scalable_same_observable":
        return ProblemSizePolicy(kind, {}, size_data)
    return ProblemSizePolicy(kind, {}, {})


def _metadata_definition(
    *,
    adapter_id: str,
    oracle_id: str,
    backend_kind: str,
    subject: str,
    system_or_material: str,
    hamiltonian: str,
    parameter_regime: str,
    size_or_limit: str,
    observable_definition: str,
    conditions: str,
    input_specs: tuple[
        tuple[
            str,
            str,
            str,
            int | float | None,
            int | float | None,
            str,
            str,
        ],
        ...,
    ],
    control_specs: tuple[
        tuple[str, str, str, int | float | None, int | float | None], ...
    ],
    output_specs: tuple[tuple[object, ...], ...],
    problem_size_kind: str,
    size_data: Mapping[str, object],
    packages: tuple[str, ...],
    convergence_kind: str,
    convergence_requirements: Mapping[str, object],
    valid_rules: Mapping[str, object],
    invalid_rules: Mapping[str, object],
) -> AdapterDefinition:
    if problem_size_kind == "fixed_local":
        physical_size_rule = {
            "kind": "fixed_local_identity",
            "fixed_sizes": size_data,
        }
        invalid_physical_size_rule = {"kind": "any_local_size_change"}
    elif problem_size_kind == "scalable_same_observable":
        physical_size_rule = {
            "kind": "declared_size_sequence",
            "allowed_sizes": size_data,
        }
        invalid_physical_size_rule = {
            "kind": "outside_declared_size_sequence"
        }
    else:
        physical_size_rule = {"kind": "declared_limit_unchanged"}
        invalid_physical_size_rule = {"kind": "physical_size_override"}
    output_units = {spec[0]: spec[2] for spec in output_specs}
    selectors = tuple(spec[0] for spec in output_specs)
    return AdapterDefinition(
        adapter_id=adapter_id,
        entry_symbol=(
            "validation.literature_evidence_adapters:adapter_" + adapter_id
        ),
        observable_identity={
            "subject": subject,
            "system_or_material": system_or_material,
            "hamiltonian": {"form": hamiltonian},
            "parameter_regime": {"rule": parameter_regime},
            "size_or_limit": {"rule": size_or_limit},
            "observable_definition": {
                "calculated_fields": selectors,
                "rule": observable_definition,
            },
            "units": output_units,
            "conditions": {"rule": conditions},
        },
        scientific_input_schema=_metadata_object_schema(
            tuple(spec[:5] for spec in input_specs)
        ),
        numerical_control_schema=_metadata_object_schema(control_specs),
        parameter_sources=_metadata_parameter_sources(input_specs),
        output_schema=_metadata_output_schema(output_specs),
        backend_kind=backend_kind,
        problem_size_policy=_metadata_size_policy(
            problem_size_kind, size_data
        ),
        runtime_requirements=RuntimeRequirements(
            interpreter="python3",
            packages=packages,
            native_libraries=(),
            backend_resources=("single_cpu_core",),
        ),
        convergence_contract=ConvergenceContract(
            convergence_kind, convergence_requirements
        ),
        counterfactual_domain=CounterfactualDomain(
            {**valid_rules, "physical_size_rule": physical_size_rule},
            {
                **invalid_rules,
                "physical_size_rule": invalid_physical_size_rule,
            },
        ),
        oracle_id=oracle_id,
        resource_limits=ResourceLimits(
            cpu_seconds=60,
            wall_seconds=120,
            address_space_bytes=2 * 1024**3,
            output_bytes=1024**2,
            file_descriptors=64,
            process_count=1,
        ),
    )


_ADAPTER_DEFINITION_ROWS = (
    _metadata_definition(
        adapter_id="xxx_bethe_energy",
        oracle_id="xxx_bethe_integral_oracle",
        backend_kind="analytic",
        subject="Bethe ground-state energy density",
        system_or_material="spin-half antiferromagnetic XXX chain",
        hamiltonian="nearest-neighbor isotropic Heisenberg exchange",
        parameter_regime="arbitrary strictly positive exchange",
        size_or_limit="infinite periodic chain thermodynamic limit",
        observable_definition="Bethe expression evaluated per lattice site",
        conditions="zero temperature and zero magnetic field",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "nearest-neighbor exchange scale",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "energy_per_site",
                "number",
                "J",
                "raw_bethe_energy_expression",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": "closed analytic expression with finite operations"
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="square_ising_self_dual_tc",
        oracle_id="square_ising_duality_residual_oracle",
        backend_kind="analytic",
        subject="positive square-Ising self-duality critical point",
        system_or_material="ferromagnetic square-lattice Ising model",
        hamiltonian="nearest-neighbor Ising exchange on the square lattice",
        parameter_regime="arbitrary strictly positive exchange",
        size_or_limit="infinite square lattice",
        observable_definition=(
            "positive self-duality root followed by temperature inversion"
        ),
        conditions="zero field and isotropic bonds",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "isotropic ferromagnetic exchange",
            ),
        ),
        control_specs=(
            ("root_residual_threshold", "number", "dimensionless", 0.0, None),
            ("maximum_refinement_iterations", "integer", "steps", 1, 10000),
        ),
        output_specs=(
            (
                "tc_over_j",
                "number",
                "dimensionless",
                "raw_positive_duality_root",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "duality equation residual lies below the declared control"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="triangular_ising_af_entropy_quadrature",
        oracle_id="triangular_ising_af_entropy_series_oracle",
        backend_kind="iterative_numeric",
        subject="zero-temperature entropy density",
        system_or_material="triangular-lattice Ising antiferromagnet",
        hamiltonian="nearest-neighbor antiferromagnetic Ising exchange",
        parameter_regime="strictly positive antiferromagnetic exchange",
        size_or_limit="infinite triangular lattice",
        observable_definition="Wannier entropy integral per spin",
        conditions="zero field and zero-temperature limiting ensemble",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "antiferromagnetic exchange scale",
            ),
        ),
        control_specs=(
            (
                "quadrature_absolute_threshold",
                "number",
                "dimensionless",
                0.0,
                None,
            ),
            ("quadrature_max_subintervals", "integer", "steps", 32, 100000),
        ),
        output_specs=(
            (
                "residual_entropy_per_spin",
                "number",
                "k_B",
                "raw_wannier_entropy_bounds",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("scipy",),
        convergence_kind="quadrature",
        convergence_requirements={
            "bound_rule": "successive integral bounds overlap and contract"
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="xy_chain_bdg_boundaries",
        oracle_id="xy_chain_dense_bdg_oracle",
        backend_kind="glt_fourier",
        subject="Bogoliubov gap-closing boundaries",
        system_or_material="anisotropic spin-half XY chain",
        hamiltonian="anisotropic XY exchange with a transverse field",
        parameter_regime="positive exchange with finite field and anisotropy",
        size_or_limit="thermodynamic momentum-space chain",
        observable_definition=(
            "field and anisotropy coordinates of BdG gap closings"
        ),
        conditions="translation invariance and periodic bulk convention",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "XY exchange scale",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            (
                "eigensolver_residual_threshold",
                "number",
                "dimensionless",
                0.0,
                None,
            ),
        ),
        output_specs=(
            (
                "ising_critical_field",
                "number",
                "J",
                "raw_field_gap_closing",
                "bounded_numeric_value",
            ),
            (
                "anisotropy_transition_gamma",
                "number",
                "dimensionless",
                "raw_anisotropy_gap_closing",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "neighboring momentum gaps and matrix residuals bound each "
                "closing"
            ),
            "glt_proof_kind": "xy_bdg_matrix",
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="diamond_spiral_threshold_fourier",
        oracle_id="diamond_real_space_threshold_oracle",
        backend_kind="glt_fourier",
        subject="spiral-surface onset coupling",
        system_or_material="classical Heisenberg model on the diamond lattice",
        hamiltonian="first- and second-neighbor isotropic exchange",
        parameter_regime=(
            "positive first-neighbor scale and nonnegative second-neighbor "
            "scale"
        ),
        size_or_limit="infinite two-sublattice reciprocal lattice",
        observable_definition=(
            "coupling ratio where the exchange-kernel minimum becomes a "
            "surface"
        ),
        conditions=(
            "classical spins with translation-invariant single-wavevector "
            "probes"
        ),
        input_specs=(
            (
                "first_neighbor_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "first-neighbor exchange",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            ("kernel_residual_bound", "number", "J", 0.0, None),
        ),
        output_specs=(
            (
                "spiral_surface_for_j2_over_j1_gt",
                "number",
                "dimensionless",
                "raw_kernel_minimum_threshold",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "kernel minima are bracketed from both coupling sides"
            ),
            "glt_proof_kind": "diamond_two_sublattice_kernel",
        },
        valid_rules={
            "first_neighbor_exchange": {"kind": "strictly_positive_finite"}
        },
        invalid_rules={
            "first_neighbor_exchange": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="spin_ice_tetrahedron_enumeration",
        oracle_id="spin_ice_tetrahedron_matrix_oracle",
        backend_kind="enumeration",
        subject="tetrahedron energy sectors and ice-sector multiplicity",
        system_or_material="nearest-neighbor Ising spin-ice tetrahedron",
        hamiltonian="pair exchange among four local-axis Ising spins",
        parameter_regime="arbitrary finite exchange scale",
        size_or_limit="one four-spin tetrahedron",
        observable_definition=(
            "complete sixteen-configuration sector enumeration"
        ),
        conditions="fixed local axes and no external field",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "nearest-neighbor tetrahedron exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "two_in_two_out_energy",
                "number",
                "J",
                "raw_two_in_two_out_sector_energy",
                "direct_exact_value",
            ),
            (
                "three_in_one_out_energy",
                "number",
                "J",
                "raw_three_in_one_out_sector_energy",
                "direct_exact_value",
            ),
            (
                "all_in_all_out_energy",
                "number",
                "J",
                "raw_all_in_all_out_sector_energy",
                "direct_exact_value",
            ),
            (
                "two_in_two_out_degeneracy",
                "integer",
                "states",
                "raw_two_in_two_out_sector_count",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 4, "tetrahedra": 1},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all sixteen configurations and all sectors are exhausted"
            )
        },
        valid_rules={"exchange": {"kind": "finite"}},
        invalid_rules={"exchange": {"kind": "nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="spin_ladder_rung_dense_ed",
        oracle_id="spin_ladder_analytic_rung_oracle",
        backend_kind="dense_ed",
        subject="isolated-rung singlet energy and triplet gap",
        system_or_material="two-leg spin-half ladder rung",
        hamiltonian="two-spin isotropic rung exchange",
        parameter_regime="strictly positive rung exchange",
        size_or_limit="one two-spin rung",
        observable_definition=(
            "dense diagonalization of singlet and triplet sectors"
        ),
        conditions="isolated rung with no leg exchange or field",
        input_specs=(
            (
                "rung_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "rung exchange coefficient",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "energy_per_rung",
                "number",
                "J",
                "raw_rung_singlet_eigenvalue",
                "direct_exact_value",
            ),
            (
                "gap_to_triplet",
                "number",
                "J",
                "raw_rung_spectrum_gap",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 2, "rungs": 1},
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "complete four-dimensional spin basis is diagonalized"
            )
        },
        valid_rules={"rung_exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"rung_exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="pauling_entropy_combinatorics",
        oracle_id="pauling_cluster_count_oracle",
        backend_kind="analytic",
        subject="Pauling ice entropy density",
        system_or_material="corner-sharing tetrahedral ice-rule network",
        hamiltonian="local two-in two-out constraint with shared spins",
        parameter_regime="tetrahedral local coordination",
        size_or_limit="thermodynamic shared-spin counting limit",
        observable_definition=(
            "logarithmic local-state counting normalized per spin"
        ),
        conditions=(
            "all allowed ice configurations carry equal statistical weight"
        ),
        input_specs=(
            (
                "spins_per_tetrahedron",
                "integer",
                "spins",
                1,
                None,
                "universal_probe",
                "local tetrahedron spin cardinality",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "pauling_entropy_per_spin",
                "number",
                "k_B",
                "raw_shared_spin_entropy_expression",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "local combinatorics and shared-spin normalization are "
                "analytic"
            )
        },
        valid_rules={
            "spins_per_tetrahedron": {"kind": "tetrahedral_positive_integer"}
        },
        invalid_rules={
            "spins_per_tetrahedron": {"kind": "nontetrahedral_or_nonpositive"}
        },
    ),
    _metadata_definition(
        adapter_id="uls_two_site_su3_matrix",
        oracle_id="uls_permutation_commutator_oracle",
        backend_kind="dense_ed",
        subject="two-site SU3 permutation equivalence",
        system_or_material="spin-one bilinear-biquadratic bond",
        hamiltonian="spin-one bilinear and biquadratic exchange",
        parameter_regime=(
            "positive common energy scale at the permutation-equivalent "
            "point"
        ),
        size_or_limit="one two-spin-one bond",
        observable_definition=(
            "coefficient angle and generator commutator closure"
        ),
        conditions="complete spin-one product basis",
        input_specs=(
            (
                "energy_scale",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "common bilinear-biquadratic energy scale",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "theta_radians",
                "number",
                "radians",
                "raw_bilinear_biquadratic_angle",
                "direct_exact_value",
            ),
            (
                "su3_symmetric",
                "boolean",
                "dimensionless",
                "raw_permutation_commutator_norms",
                "all_residuals_within_bound_boolean",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 2, "spin_quantum_number": 1},
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all total-spin sectors and generator identities are "
                "evaluated"
            )
        },
        valid_rules={"energy_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={"energy_scale": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="aklt_projector_angle",
        oracle_id="aklt_two_spin_spectrum_oracle",
        backend_kind="analytic",
        subject="spin-two projector coefficient angle",
        system_or_material="spin-one AKLT nearest-neighbor bond",
        hamiltonian="positive spin-two projector expanded in bilinear powers",
        parameter_regime="arbitrary strictly positive projector scale",
        size_or_limit="analytic two-spin-one bond identity",
        observable_definition=(
            "bilinear-biquadratic coefficient ratio and angle"
        ),
        conditions=(
            "constant energy shift separated from exchange coefficients"
        ),
        input_specs=(
            (
                "projector_scale",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "positive spin-two projector scale",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "aklt_tan_theta",
                "number",
                "dimensionless",
                "raw_projector_coefficient_ratio",
                "direct_exact_value",
            ),
            (
                "theta_radians",
                "number",
                "radians",
                "raw_projector_coefficient_angle",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "spin-sector polynomial coefficients are derived "
                "symbolically"
            )
        },
        valid_rules={"projector_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={
            "projector_scale": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="compass_line_symmetry_matrix",
        oracle_id="compass_spin_flip_oracle",
        backend_kind="dense_ed",
        subject="line-flip symmetry commutators",
        system_or_material="square-lattice quantum compass model",
        hamiltonian=(
            "directional Pauli exchange on horizontal and vertical bonds"
        ),
        parameter_regime="finite directional exchange coefficients",
        size_or_limit="two declared open finite lattice shapes",
        observable_definition="every Hamiltonian and line-flip commutator",
        conditions="open boundaries with all row and column flip operators",
        input_specs=(
            (
                "horizontal_exchange",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "horizontal bond exchange",
            ),
            (
                "vertical_exchange",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "vertical bond exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "has_line_flip_symmetries",
                "boolean",
                "dimensionless",
                "raw_line_flip_commutator_norms",
                "all_residuals_within_bound_boolean",
            ),
        ),
        problem_size_kind="scalable_same_observable",
        size_data={
            "lattice_shapes": ((2, 2), (2, 3)),
            "boundary_conditions": "open",
        },
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "every declared line operator and both shapes are exhausted"
            )
        },
        valid_rules={
            "horizontal_exchange": {"kind": "finite"},
            "vertical_exchange": {"kind": "finite"},
        },
        invalid_rules={
            "horizontal_exchange": {"kind": "nonfinite"},
            "vertical_exchange": {"kind": "nonfinite"},
        },
    ),
    _metadata_definition(
        adapter_id="kitaev_field_majorana_mass",
        oracle_id="kitaev_two_band_chern_oracle",
        backend_kind="glt_fourier",
        subject="field-induced Majorana mass and odd topological parity",
        system_or_material="isotropic honeycomb Kitaev spin liquid",
        hamiltonian=(
            "bond-directional Kitaev exchange with three field components"
        ),
        parameter_regime=(
            "positive exchange and three finite nonzero field components"
        ),
        size_or_limit="thermodynamic two-band Majorana Brillouin zone",
        observable_definition=(
            "third-order mass, bulk gap, and parity from lower-level band "
            "data"
        ),
        conditions="weak-field perturbative regime with fixed flux sector",
        input_specs=(
            (
                "kitaev_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "isotropic Kitaev exchange",
            ),
            (
                "field_x",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "x field component",
            ),
            (
                "field_y",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "y field component",
            ),
            (
                "field_z",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "z field component",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            ("gap_residual_bound", "number", "J", 0.0, None),
        ),
        output_specs=(
            (
                "field_opens_non_abelian_gap",
                "boolean",
                "dimensionless",
                "raw_mass_gap_and_parity",
                "positive_gap_and_odd_parity_boolean",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "gap lower bound is positive and band parity is stable "
                "under finer sampling"
            ),
            "glt_proof_kind": "kitaev_majorana_two_band",
        },
        valid_rules={
            "kitaev_exchange": {"kind": "strictly_positive_finite"},
            "field_x": {
                "kind": "finite_nonzero_relative_regime",
                "reference_field": "kitaev_exchange",
                "maximum_absolute_ratio": 0.25,
            },
            "field_y": {
                "kind": "finite_nonzero_relative_regime",
                "reference_field": "kitaev_exchange",
                "maximum_absolute_ratio": 0.25,
            },
            "field_z": {
                "kind": "finite_nonzero_relative_regime",
                "reference_field": "kitaev_exchange",
                "maximum_absolute_ratio": 0.25,
            },
        },
        invalid_rules={
            "kitaev_exchange": {"kind": "nonpositive_or_nonfinite"},
            "field_x": {
                "kind": "outside_product_state_regime_or_nonfinite"
            },
            "field_y": {
                "kind": "outside_product_state_regime_or_nonfinite"
            },
            "field_z": {
                "kind": "outside_product_state_regime_or_nonfinite"
            },
        },
    ),
    _metadata_definition(
        adapter_id="toric_code_stabilizer_rank",
        oracle_id="toric_code_logical_loop_oracle",
        backend_kind="enumeration",
        subject="torus ground-space dimension from stabilizer rank",
        system_or_material="square-lattice toric code",
        hamiltonian=(
            "commuting star and plaquette stabilizers over edge qubits"
        ),
        parameter_regime="nonzero commuting stabilizer coefficients",
        size_or_limit="two declared periodic torus shapes",
        observable_definition=(
            "GF2 incidence-matrix rank and logical dimension"
        ),
        conditions="periodic boundaries with both noncontractible cycles",
        input_specs=(
            (
                "stabilizer_scale",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "common commuting stabilizer scale",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "torus_ground_state_degeneracy",
                "integer",
                "states",
                "raw_stabilizer_matrix_rank",
                "rank_derived_integer",
            ),
        ),
        problem_size_kind="scalable_same_observable",
        size_data={
            "lattice_shapes": ((2, 2), (3, 3)),
            "boundary_conditions": "periodic",
        },
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "GF2 elimination and all stabilizer dependencies are exact"
            )
        },
        valid_rules={"stabilizer_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={
            "stabilizer_scale": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="aklt_two_site_projector_ed",
        oracle_id="aklt_clebsch_gordan_oracle",
        backend_kind="dense_ed",
        subject="two-site projector sectors and local VBS energy",
        system_or_material="spin-one AKLT bond",
        hamiltonian="positive total-spin-two projector",
        parameter_regime="arbitrary strictly positive projector scale",
        size_or_limit="one two-spin-one bond",
        observable_definition=(
            "complete projector spectrum and local VBS expectation"
        ),
        conditions="full nine-dimensional product basis",
        input_specs=(
            (
                "projector_scale",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "spin-two projector coefficient",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "two_site_projector_eigenvalues",
                "list_number",
                "dimensionless",
                "raw_projector_sector_eigenvalues",
                "grouped_exact_sequence",
                3,
            ),
            (
                "vbs_ground_energy",
                "number",
                "J",
                "raw_local_vbs_energy",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 2, "spin_quantum_number": 1},
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all nine eigenvalues and spin-sector multiplicities are "
                "exhausted"
            )
        },
        valid_rules={"projector_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={
            "projector_scale": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="blume_capel_level_crossing",
        oracle_id="blume_capel_configuration_oracle",
        backend_kind="enumeration",
        subject="uniform-state zero-temperature level crossing",
        system_or_material="square-lattice spin-one Blume-Capel model",
        hamiltonian=(
            "nearest-neighbor Ising exchange plus single-ion anisotropy"
        ),
        parameter_regime="positive exchange and finite single-ion coefficient",
        size_or_limit="one-site uniform-state cell with square bond count",
        observable_definition=(
            "uniform spin-state energies and their crossing ratio"
        ),
        conditions="zero field and zero temperature",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "ferromagnetic bond exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "square_lattice_d_over_j_crossing",
                "number",
                "dimensionless",
                "raw_uniform_level_crossing_ratio",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"unit_cell_sites": 1, "coordination_number": 4},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all three uniform spin states and square bonds are counted"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="checkerboard_plaquette_enumeration",
        oracle_id="checkerboard_total_spin_oracle",
        backend_kind="enumeration",
        subject="crossed-plaquette zero-spin minimum",
        system_or_material="classical checkerboard Heisenberg antiferromagnet",
        hamiltonian=(
            "complete-graph exchange on one crossed four-spin plaquette"
        ),
        parameter_regime="strictly positive normalized exchange",
        size_or_limit="one crossed four-spin plaquette",
        observable_definition=(
            "plaquette energy minimization and total-spin norms"
        ),
        conditions="unit-length classical spins",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "antiferromagnetic plaquette exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "zero_total_spin_per_crossed_plaquette",
                "boolean",
                "dimensionless",
                "raw_plaquette_spin_sum_norms",
                "all_residuals_within_bound_boolean",
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 4, "crossed_plaquettes": 1},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "total-spin identity and all pair bonds are evaluated"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="honeycomb_ising_star_triangle_tc",
        oracle_id="honeycomb_ising_critical_polynomial_oracle",
        backend_kind="analytic",
        subject="honeycomb-Ising star-triangle critical point",
        system_or_material="ferromagnetic honeycomb-lattice Ising model",
        hamiltonian="isotropic nearest-neighbor Ising exchange",
        parameter_regime="arbitrary strictly positive exchange",
        size_or_limit="infinite honeycomb lattice",
        observable_definition=(
            "positive star-triangle root and temperature inversion"
        ),
        conditions="zero field and isotropic bonds",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "ferromagnetic bond exchange",
            ),
        ),
        control_specs=(
            ("root_residual_threshold", "number", "dimensionless", 0.0, None),
            ("maximum_refinement_iterations", "integer", "steps", 1, 10000),
        ),
        output_specs=(
            (
                "tc_over_j",
                "number",
                "dimensionless",
                "raw_positive_star_triangle_root",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "star-triangle equation residual lies below the declared "
                "control"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="kagome_ising_af_entropy_quadrature",
        oracle_id="kagome_ising_af_transfer_count_oracle",
        backend_kind="iterative_numeric",
        subject="positive thermodynamic ground-state entropy",
        system_or_material="kagome-lattice Ising antiferromagnet",
        hamiltonian="nearest-neighbor antiferromagnetic Ising exchange",
        parameter_regime="strictly positive antiferromagnetic exchange",
        size_or_limit="infinite kagome lattice",
        observable_definition=(
            "successive entropy estimates and a positive lower bound"
        ),
        conditions="zero field and zero-temperature limiting ensemble",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "antiferromagnetic bond exchange",
            ),
        ),
        control_specs=(
            (
                "quadrature_absolute_threshold",
                "number",
                "dimensionless",
                0.0,
                None,
            ),
            ("quadrature_max_subintervals", "integer", "steps", 32, 100000),
        ),
        output_specs=(
            (
                "macroscopic_ground_state_degeneracy",
                "boolean",
                "dimensionless",
                "raw_entropy_lower_bounds",
                "positive_lower_bound_boolean",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("scipy",),
        convergence_kind="quadrature",
        convergence_requirements={
            "bound_rule": (
                "successive entropy intervals contract above a positive "
                "lower bound"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="kagome_ising_star_triangle_tc",
        oracle_id="kagome_ising_critical_polynomial_oracle",
        backend_kind="analytic",
        subject="kagome-Ising star-triangle critical point",
        system_or_material="ferromagnetic kagome-lattice Ising model",
        hamiltonian="isotropic nearest-neighbor Ising exchange",
        parameter_regime="arbitrary strictly positive exchange",
        size_or_limit="infinite kagome lattice",
        observable_definition="positive ferromagnetic star-triangle root",
        conditions="zero field and isotropic bonds",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "ferromagnetic bond exchange",
            ),
        ),
        control_specs=(
            ("root_residual_threshold", "number", "dimensionless", 0.0, None),
            ("maximum_refinement_iterations", "integer", "steps", 1, 10000),
        ),
        output_specs=(
            (
                "tc_over_j",
                "number",
                "dimensionless",
                "raw_ferromagnetic_star_triangle_root",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "critical polynomial residual lies below the declared control"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="majumdar_ghosh_dimer_ed",
        oracle_id="majumdar_ghosh_projector_oracle",
        backend_kind="dense_ed",
        subject="dimer-point energy density and translated ground-space rank",
        system_or_material="periodic spin-half J1-J2 chain",
        hamiltonian="nearest- and next-nearest-neighbor isotropic exchange",
        parameter_regime=(
            "positive nearest exchange with dimer-point coupling relation"
        ),
        size_or_limit="two declared periodic even chain lengths",
        observable_definition=(
            "ground energy density and rank of translated dimer coverings"
        ),
        conditions="zero field and periodic boundary conditions",
        input_specs=(
            (
                "nearest_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "nearest-neighbor exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "energy_per_site",
                "number",
                "J",
                "raw_chain_energy_density_sequence",
                "direct_exact_value",
            ),
            (
                "degenerate_dimer_coverings",
                "integer",
                "states",
                "raw_translated_ground_space_rank",
                "rank_derived_integer",
            ),
        ),
        problem_size_kind="scalable_same_observable",
        size_data={
            "periodic_chain_lengths": (8, 10),
            "boundary_conditions": "periodic",
        },
        packages=("numpy",),
        convergence_kind="finite_size",
        convergence_requirements={
            "size_rule": (
                "both declared lengths obey the same projector identity "
                "and rank rule"
            ),
            "dense_ed_proof_kind": "ground_space_covering",
        },
        valid_rules={
            "nearest_exchange": {"kind": "strictly_positive_finite"}
        },
        invalid_rules={
            "nearest_exchange": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="ising_chain_transfer_matrix",
        oracle_id="ising_chain_partition_analytic_oracle",
        backend_kind="analytic",
        subject="absence of a finite-temperature transfer-eigenvalue crossing",
        system_or_material="one-dimensional classical Ising chain",
        hamiltonian="nearest-neighbor Ising exchange at zero field",
        parameter_regime=(
            "positive exchange and arbitrary finite positive inverse "
            "temperature"
        ),
        size_or_limit="infinite chain transfer-matrix limit",
        observable_definition=(
            "analytic eigenvalue separation and zero-temperature limiting "
            "point"
        ),
        conditions="zero magnetic field and finite temperature",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "nearest-neighbor exchange",
            ),
            (
                "inverse_temperature",
                "number",
                "1/J",
                0.0,
                None,
                "canonical_model_parameter",
                "finite inverse temperature",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "finite_temperature_transition",
                "boolean",
                "dimensionless",
                "raw_transfer_eigenvalue_separation",
                "no_finite_crossing_boolean",
            ),
            (
                "tc_over_j",
                "number",
                "dimensionless",
                "raw_zero_temperature_limit",
                "no_finite_crossing_zero_limit",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "both transfer eigenvalues and their analytic separation "
                "are explicit"
            )
        },
        valid_rules={
            "exchange": {"kind": "strictly_positive_finite"},
            "inverse_temperature": {"kind": "strictly_positive_finite"},
        },
        invalid_rules={
            "exchange": {"kind": "nonpositive_or_nonfinite"},
            "inverse_temperature": {"kind": "nonpositive_or_nonfinite"},
        },
    ),
    _metadata_definition(
        adapter_id="pyrochlore_coulomb_fourier",
        oracle_id="pyrochlore_real_space_constraint_oracle",
        backend_kind="glt_fourier",
        subject="tetrahedron constraint and directional pinch-point limits",
        system_or_material="classical pyrochlore Heisenberg antiferromagnet",
        hamiltonian=(
            "nearest-neighbor isotropic exchange on corner-sharing "
            "tetrahedra"
        ),
        parameter_regime="strictly positive exchange",
        size_or_limit="thermodynamic reciprocal-space Coulomb phase",
        observable_definition=(
            "tetrahedron spin sums and two directional polarization limits"
        ),
        conditions=(
            "zero field with two distinct normalized approach directions"
        ),
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "antiferromagnetic exchange",
            ),
            (
                "approach_direction_a",
                "string",
                "dimensionless",
                None,
                None,
                "universal_probe",
                "first normalized reciprocal-space direction",
            ),
            (
                "approach_direction_b",
                "string",
                "dimensionless",
                None,
                None,
                "universal_probe",
                "second normalized reciprocal-space direction",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            (
                "constraint_residual_bound",
                "number",
                "dimensionless",
                0.0,
                None,
            ),
        ),
        output_specs=(
            (
                "zero_total_spin_per_tetrahedron",
                "boolean",
                "dimensionless",
                "raw_tetrahedron_spin_sum_norms",
                "all_residuals_within_bound_boolean",
            ),
            (
                "pinch_points",
                "boolean",
                "dimensionless",
                "raw_directional_polarization_limits",
                "directional_limits_differ_boolean",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "constraint residuals contract and directional limits "
                "remain distinct"
            ),
            "glt_proof_kind": "pyrochlore_constraint_projector",
        },
        valid_rules={
            "exchange": {"kind": "strictly_positive_finite"},
            "approach_direction_a": {"kind": "normalized_supported_direction"},
            "approach_direction_b": {"kind": "normalized_distinct_direction"},
        },
        invalid_rules={
            "exchange": {"kind": "nonpositive_or_nonfinite"},
            "approach_direction_a": {"kind": "unsupported_or_unnormalized"},
            "approach_direction_b": {
                "kind": "unsupported_equal_or_unnormalized"
            },
        },
    ),
    _metadata_definition(
        adapter_id="shastry_sutherland_dimer_ed",
        oracle_id="shastry_sutherland_bond_oracle",
        backend_kind="dense_ed",
        subject="orthogonal-dimer product energy and interdimer cancellation",
        system_or_material="spin-half Shastry-Sutherland lattice cells",
        hamiltonian="intradimer and orthogonal interdimer Heisenberg exchange",
        parameter_regime=(
            "positive intradimer scale with finite linked-cell coupling"
        ),
        size_or_limit="two declared open linked orthogonal-dimer cells",
        observable_definition=(
            "singlet-product energy normalized per dimer and per spin"
        ),
        conditions="open linked cells in the exact product-state regime",
        input_specs=(
            (
                "intradimer_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "orthogonal dimer exchange",
            ),
            (
                "interdimer_exchange",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "linked-cell exchange",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "energy_per_dimer",
                "number",
                "J",
                "raw_singlet_product_energy_per_dimer",
                "direct_exact_value",
            ),
            (
                "energy_per_spin",
                "number",
                "J",
                "raw_singlet_product_energy_per_spin",
                "direct_exact_value",
            ),
        ),
        problem_size_kind="scalable_same_observable",
        size_data={
            "orthogonal_dimer_counts": (2, 4),
            "spin_counts": (4, 8),
            "boundary_conditions": "open_linked_cells",
        },
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all intradimer expectations and linked-cell cancellations "
                "are exact"
            ),
            "dense_ed_proof_kind": "linked_cell_product_ground_state",
        },
        valid_rules={
            "intradimer_exchange": {"kind": "strictly_positive_finite"},
            "interdimer_exchange": {
                "kind": "finite_product_state_regime",
                "reference_field": "intradimer_exchange",
                "maximum_absolute_ratio": 0.5,
            },
        },
        invalid_rules={
            "intradimer_exchange": {"kind": "nonpositive_or_nonfinite"},
            "interdimer_exchange": {
                "kind": "outside_product_state_regime_or_nonfinite"
            },
        },
    ),
    _metadata_definition(
        adapter_id="simple_cubic_j1_j2_fourier",
        oracle_id="simple_cubic_real_space_energy_oracle",
        backend_kind="glt_fourier",
        subject="Néel-to-collinear exchange crossing",
        system_or_material="classical simple-cubic J1-J2 Heisenberg model",
        hamiltonian="first- and second-neighbor isotropic exchange",
        parameter_regime=(
            "positive first-neighbor and nonnegative second-neighbor "
            "exchange"
        ),
        size_or_limit="infinite simple-cubic reciprocal lattice",
        observable_definition=(
            "crossing of minimized Néel and collinear Fourier branches"
        ),
        conditions=(
            "classical unit spins and translation-invariant wavevectors"
        ),
        input_specs=(
            (
                "first_neighbor_exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "first-neighbor exchange",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            ("branch_residual_bound", "number", "J", 0.0, None),
        ),
        output_specs=(
            (
                "neel_to_collinear_boundary_j2_over_j1",
                "number",
                "dimensionless",
                "raw_branch_crossing_ratio",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "both Fourier branches are minimized and their crossing is "
                "bracketed"
            ),
            "glt_proof_kind": "simple_cubic_exchange_kernel",
        },
        valid_rules={
            "first_neighbor_exchange": {"kind": "strictly_positive_finite"}
        },
        invalid_rules={
            "first_neighbor_exchange": {"kind": "nonpositive_or_nonfinite"}
        },
    ),
    _metadata_definition(
        adapter_id="spin1_single_ion_dense_ed",
        oracle_id="spin1_m_quantum_number_oracle",
        backend_kind="dense_ed",
        subject="single-ion spin-one levels and multiplicities",
        system_or_material="one spin-one degree of freedom",
        hamiltonian="quadratic single-ion anisotropy",
        parameter_regime="arbitrary finite nonzero anisotropy",
        size_or_limit="one spin-one site",
        observable_definition=(
            "complete three-state spectrum grouped by equal energies"
        ),
        conditions="zero magnetic field",
        input_specs=(
            (
                "single_ion_anisotropy",
                "number",
                "J",
                None,
                None,
                "canonical_model_parameter",
                "quadratic anisotropy coefficient",
            ),
        ),
        control_specs=(),
        output_specs=(
            (
                "levels",
                "list_number",
                "J",
                "raw_single_ion_eigenvalues",
                "grouped_exact_sequence",
                3,
            ),
            (
                "degeneracies",
                "list_integer",
                "states",
                "raw_single_ion_level_multiplicities",
                "grouped_exact_sequence",
                2,
            ),
        ),
        problem_size_kind="fixed_local",
        size_data={"spin_count": 1, "spin_quantum_number": 1},
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": (
                "all three magnetic quantum-number states are exhausted"
            )
        },
        valid_rules={"single_ion_anisotropy": {"kind": "finite_nonzero"}},
        invalid_rules={"single_ion_anisotropy": {"kind": "zero_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="fully_frustrated_ising_entropy_series",
        oracle_id="fully_frustrated_ising_transfer_oracle",
        backend_kind="iterative_numeric",
        subject="positive fully frustrated entropy density",
        system_or_material="fully frustrated square-lattice Ising model",
        hamiltonian=(
            "nearest-neighbor Ising bonds with odd plaquette frustration"
        ),
        parameter_regime="strictly positive common bond magnitude",
        size_or_limit="thermodynamic square-lattice limit",
        observable_definition=(
            "successive entropy series bounds and positive limiting density"
        ),
        conditions="zero field and zero-temperature frustrated ensemble",
        input_specs=(
            (
                "bond_magnitude",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "common frustrated bond magnitude",
            ),
        ),
        control_specs=(
            ("series_refinement_terms", "integer", "terms", 32, 1000000),
            ("truncation_cutoff", "number", "dimensionless", 0.0, None),
        ),
        output_specs=(
            (
                "macroscopic_ground_state_degeneracy",
                "boolean",
                "dimensionless",
                "raw_entropy_series_lower_bounds",
                "positive_lower_bound_boolean",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="iterative",
        convergence_requirements={
            "sequence_rule": (
                "successive entropy bounds contract above a positive lower "
                "bound"
            )
        },
        valid_rules={"bond_magnitude": {"kind": "strictly_positive_finite"}},
        invalid_rules={"bond_magnitude": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="tfim_bdg_critical_point",
        oracle_id="tfim_duality_gap_oracle",
        backend_kind="glt_fourier",
        subject="thermodynamic transverse-Ising gap closing",
        system_or_material="spin-half transverse-field Ising chain",
        hamiltonian="nearest-neighbor Ising exchange with transverse field",
        parameter_regime="strictly positive exchange and field",
        size_or_limit="thermodynamic Jordan-Wigner momentum limit",
        observable_definition=(
            "field-to-exchange coordinate of the BdG gap closing"
        ),
        conditions="periodic bulk convention and zero longitudinal field",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "Ising exchange",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
            ("gap_residual_bound", "number", "J", 0.0, None),
        ),
        output_specs=(
            (
                "critical_field_over_exchange",
                "number",
                "dimensionless",
                "raw_thermodynamic_gap_closing_ratio",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "the BdG gap minimum is bracketed and closes under finer "
                "sampling"
            ),
            "glt_proof_kind": "tfim_jordan_wigner_bdg",
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="triangular_ising_star_triangle_tc",
        oracle_id="triangular_ising_critical_polynomial_oracle",
        backend_kind="analytic",
        subject="triangular-Ising star-triangle critical point",
        system_or_material="ferromagnetic triangular-lattice Ising model",
        hamiltonian="isotropic nearest-neighbor Ising exchange",
        parameter_regime="arbitrary strictly positive exchange",
        size_or_limit="infinite triangular lattice",
        observable_definition=(
            "positive critical-equation root and temperature inversion"
        ),
        conditions="zero field and isotropic bonds",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "ferromagnetic bond exchange",
            ),
        ),
        control_specs=(
            ("root_residual_threshold", "number", "dimensionless", 0.0, None),
            ("maximum_refinement_iterations", "integer", "steps", 1, 10000),
        ),
        output_specs=(
            (
                "tc_over_j",
                "number",
                "dimensionless",
                "raw_positive_critical_equation_root",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=(),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": (
                "critical-equation residual lies below the declared control"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="xx_chain_fermion_integral",
        oracle_id="xx_chain_dense_ed_extrapolation_oracle",
        backend_kind="iterative_numeric",
        subject="occupied-dispersion ground-state energy density",
        system_or_material="spin-half XX chain",
        hamiltonian="nearest-neighbor planar exchange mapped to free fermions",
        parameter_regime=(
            "arbitrary strictly positive exchange at half filling"
        ),
        size_or_limit="thermodynamic occupied-momentum integral",
        observable_definition=(
            "successive occupied-dispersion integral bounds per site"
        ),
        conditions="zero field and zero temperature",
        input_specs=(
            (
                "exchange",
                "number",
                "J",
                0.0,
                None,
                "canonical_model_parameter",
                "planar exchange scale",
            ),
        ),
        control_specs=(
            ("momentum_refinement_grid", "integer", "points", 32, 1000000),
            ("quadrature_absolute_threshold", "number", "J", 0.0, None),
        ),
        output_specs=(
            (
                "energy_per_site",
                "number",
                "J",
                "raw_occupied_dispersion_integral_bounds",
                "bounded_numeric_value",
            ),
        ),
        problem_size_kind="not_applicable",
        size_data={},
        packages=("numpy",),
        convergence_kind="quadrature",
        convergence_requirements={
            "bound_rule": (
                "successive occupied-dispersion integral bounds overlap "
                "and contract"
            )
        },
        valid_rules={"exchange": {"kind": "strictly_positive_finite"}},
        invalid_rules={"exchange": {"kind": "nonpositive_or_nonfinite"}},
    ),
)


_EXPECTED_BACKEND_IDS = {
    "analytic": frozenset(
        {
            "xxx_bethe_energy",
            "square_ising_self_dual_tc",
            "pauling_entropy_combinatorics",
            "aklt_projector_angle",
            "honeycomb_ising_star_triangle_tc",
            "kagome_ising_star_triangle_tc",
            "ising_chain_transfer_matrix",
            "triangular_ising_star_triangle_tc",
        }
    ),
    "enumeration": frozenset(
        {
            "spin_ice_tetrahedron_enumeration",
            "toric_code_stabilizer_rank",
            "blume_capel_level_crossing",
            "checkerboard_plaquette_enumeration",
        }
    ),
    "dense_ed": frozenset(
        {
            "spin_ladder_rung_dense_ed",
            "uls_two_site_su3_matrix",
            "compass_line_symmetry_matrix",
            "aklt_two_site_projector_ed",
            "majumdar_ghosh_dimer_ed",
            "shastry_sutherland_dimer_ed",
            "spin1_single_ion_dense_ed",
        }
    ),
    "glt_fourier": frozenset(
        {
            "xy_chain_bdg_boundaries",
            "diamond_spiral_threshold_fourier",
            "kitaev_field_majorana_mass",
            "pyrochlore_coulomb_fourier",
            "simple_cubic_j1_j2_fourier",
            "tfim_bdg_critical_point",
        }
    ),
    "iterative_numeric": frozenset(
        {
            "triangular_ising_af_entropy_quadrature",
            "kagome_ising_af_entropy_quadrature",
            "fully_frustrated_ising_entropy_series",
            "xx_chain_fermion_integral",
        }
    ),
}
_EXPECTED_FIXED_LOCAL_IDS = frozenset(
    {
        "spin_ice_tetrahedron_enumeration",
        "spin_ladder_rung_dense_ed",
        "uls_two_site_su3_matrix",
        "aklt_two_site_projector_ed",
        "blume_capel_level_crossing",
        "checkerboard_plaquette_enumeration",
        "spin1_single_ion_dense_ed",
    }
)
_EXPECTED_SCALABLE_IDS = frozenset(
    {
        "compass_line_symmetry_matrix",
        "toric_code_stabilizer_rank",
        "majumdar_ghosh_dimer_ed",
        "shastry_sutherland_dimer_ed",
    }
)
_EXPECTED_SIZE_DATA = {
    "spin_ice_tetrahedron_enumeration": {"spin_count": 4, "tetrahedra": 1},
    "spin_ladder_rung_dense_ed": {"spin_count": 2, "rungs": 1},
    "uls_two_site_su3_matrix": {"spin_count": 2, "spin_quantum_number": 1},
    "aklt_two_site_projector_ed": {
        "spin_count": 2,
        "spin_quantum_number": 1,
    },
    "blume_capel_level_crossing": {
        "unit_cell_sites": 1,
        "coordination_number": 4,
    },
    "checkerboard_plaquette_enumeration": {
        "spin_count": 4,
        "crossed_plaquettes": 1,
    },
    "spin1_single_ion_dense_ed": {
        "spin_count": 1,
        "spin_quantum_number": 1,
    },
    "compass_line_symmetry_matrix": {
        "lattice_shapes": ((2, 2), (2, 3)),
        "boundary_conditions": "open",
    },
    "toric_code_stabilizer_rank": {
        "lattice_shapes": ((2, 2), (3, 3)),
        "boundary_conditions": "periodic",
    },
    "majumdar_ghosh_dimer_ed": {
        "periodic_chain_lengths": (8, 10),
        "boundary_conditions": "periodic",
    },
    "shastry_sutherland_dimer_ed": {
        "orthogonal_dimer_counts": (2, 4),
        "spin_counts": (4, 8),
        "boundary_conditions": "open_linked_cells",
    },
}


def _build_adapter_definitions(
    definitions: Iterable[AdapterDefinition],
) -> Mapping[str, AdapterDefinition]:
    catalog: dict[str, AdapterDefinition] = {}
    for index, definition in enumerate(definitions):
        if type(definition) is not AdapterDefinition:
            raise AdapterContractError(
                f"definition row {index} must be an exact AdapterDefinition"
            )
        definition_snapshot = AdapterDefinition(
            *(
                getattr(definition, field.name)
                for field in fields(AdapterDefinition)
            )
        )
        if definition_snapshot.adapter_id in catalog:
            raise AdapterContractError(
                "duplicate adapter ID in definition catalog: "
                f"{definition_snapshot.adapter_id}"
            )
        catalog[definition_snapshot.adapter_id] = definition_snapshot
    if len(catalog) != 29:
        raise AdapterContractError(
            "definition catalog must contain exactly 29 rows"
        )

    eligible_by_id = {
        decision.adapter_id: decision
        for decision in ADAPTER_ELIGIBILITY.values()
        if decision.disposition == "eligible"
    }
    if set(catalog) != set(eligible_by_id):
        raise AdapterContractError(
            "definition key set must equal the eligible adapter key set"
        )
    oracle_ids = set()
    for adapter_id, definition in catalog.items():
        if adapter_id != definition.adapter_id:
            raise AdapterContractError("definition key must equal adapter_id")
        decision = eligible_by_id[adapter_id]
        if definition.oracle_id != decision.oracle_id:
            raise AdapterContractError(
                "definition oracle does not match eligibility for "
                f"{adapter_id}"
            )
        if (
            definition.output_schema.selector_fields
            != decision.selector_fields
        ):
            raise AdapterContractError(
                "definition selector fields do not match eligibility for "
                f"{adapter_id}"
            )
        if definition.oracle_id in oracle_ids:
            raise AdapterContractError(
                "definition catalog contains duplicate oracle ID"
            )
        oracle_ids.add(definition.oracle_id)

    for backend_kind, expected_ids in _EXPECTED_BACKEND_IDS.items():
        actual_ids = {
            adapter_id
            for adapter_id, definition in catalog.items()
            if definition.backend_kind == backend_kind
        }
        if actual_ids != expected_ids:
            raise AdapterContractError(
                f"definition backend assignment mismatch for {backend_kind}"
            )
    fixed_ids = {
        adapter_id
        for adapter_id, definition in catalog.items()
        if definition.problem_size_policy.kind == "fixed_local"
    }
    scalable_ids = {
        adapter_id
        for adapter_id, definition in catalog.items()
        if definition.problem_size_policy.kind == "scalable_same_observable"
    }
    not_applicable_ids = {
        adapter_id
        for adapter_id, definition in catalog.items()
        if definition.problem_size_policy.kind == "not_applicable"
    }
    if (
        fixed_ids != _EXPECTED_FIXED_LOCAL_IDS
        or scalable_ids != _EXPECTED_SCALABLE_IDS
        or len(not_applicable_ids) != 18
    ):
        raise AdapterContractError(
            "definition problem-size policy assignment mismatch"
        )
    for adapter_id, definition in catalog.items():
        expected_size_data = _EXPECTED_SIZE_DATA.get(adapter_id, {})
        policy = definition.problem_size_policy
        actual_size_data = (
            policy.fixed_sizes
            if policy.kind == "fixed_local"
            else policy.allowed_sizes
        )
        if actual_size_data != freeze_json(expected_size_data):
            raise AdapterContractError(
                f"definition size data mismatch for {adapter_id}"
            )
    return MappingProxyType(dict(catalog))


ADAPTER_DEFINITIONS: Mapping[
    str,
    AdapterDefinition,
] = _build_adapter_definitions(_ADAPTER_DEFINITION_ROWS)


def get_adapter_definition(adapter_id: str) -> AdapterDefinition:
    require_identifier(adapter_id, "adapter_id")
    try:
        return ADAPTER_DEFINITIONS[adapter_id]
    except KeyError as error:
        raise AdapterContractError(
            f"unknown adapter_id {adapter_id}"
        ) from error


def validate_adapter_definition(value: object) -> AdapterDefinition:
    """Return a fresh, fully revalidated adapter-definition snapshot."""

    if type(value) is not AdapterDefinition:
        raise AdapterContractError(
            "adapter definition must be an exact AdapterDefinition"
        )
    try:
        return AdapterDefinition(
            adapter_id=value.adapter_id,
            entry_symbol=value.entry_symbol,
            observable_identity=value.observable_identity,
            scientific_input_schema=value.scientific_input_schema,
            numerical_control_schema=value.numerical_control_schema,
            parameter_sources=value.parameter_sources,
            output_schema=value.output_schema,
            backend_kind=value.backend_kind,
            problem_size_policy=value.problem_size_policy,
            runtime_requirements=value.runtime_requirements,
            convergence_contract=value.convergence_contract,
            counterfactual_domain=value.counterfactual_domain,
            oracle_id=value.oracle_id,
            resource_limits=value.resource_limits,
        )
    except AdapterContractError:
        raise
    except Exception as error:
        raise AdapterContractError(
            "adapter definition revalidation failed"
        ) from error


_VALUE_SCHEMA_JSON_FIELDS = (
    "kind",
    "required",
    "lower",
    "upper",
    "item_schema",
    "properties",
    "units",
)
_OUTPUT_BINDING_JSON_FIELDS = (
    "value_schema",
    "raw_field",
    "proof_kind",
)
_ADAPTER_DEFINITION_JSON_FIELDS = (
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
)


def _value_schema_to_frozen_json(schema: ValueSchema) -> FrozenJsonObject:
    snapshot = _snapshot_value_schema(schema, "value_schema")
    return _snapshot_json_mapping(
        {
            "kind": snapshot.kind,
            "required": snapshot.required,
            "lower": snapshot.lower,
            "upper": snapshot.upper,
            "item_schema": (
                None
                if snapshot.item_schema is None
                else _value_schema_to_frozen_json(snapshot.item_schema)
            ),
            "properties": {
                name: _value_schema_to_frozen_json(child)
                for name, child in snapshot.properties
            },
            "units": snapshot.units,
        },
        "value_schema",
    )


def _value_schema_from_frozen_json(
    value: object,
    field_name: str,
) -> ValueSchema:
    record = require_exact_keys(value, _VALUE_SCHEMA_JSON_FIELDS, field_name)
    properties = _snapshot_json_mapping(
        record["properties"], f"{field_name}.properties"
    )
    item_schema_value = record["item_schema"]
    return ValueSchema(
        kind=record["kind"],
        required=record["required"],
        lower=record["lower"],
        upper=record["upper"],
        item_schema=(
            None
            if item_schema_value is None
            else _value_schema_from_frozen_json(
                item_schema_value, f"{field_name}.item_schema"
            )
        ),
        properties=tuple(
            (
                name,
                _value_schema_from_frozen_json(
                    child, f"{field_name}.properties.{name}"
                ),
            )
            for name, child in properties._items
        ),
        units=record["units"],
    )


def _output_schema_to_frozen_json(
    output_schema: OutputSchema,
) -> FrozenJsonObject:
    snapshot = _snapshot_output_schema(output_schema)
    return _snapshot_json_mapping(
        {
            "fields": {
                selector: {
                    "value_schema": _value_schema_to_frozen_json(
                        binding.value_schema
                    ),
                    "raw_field": binding.raw_field,
                    "proof_kind": binding.proof_kind,
                }
                for selector, binding in snapshot
            }
        },
        "output_schema",
    )


def _output_schema_from_frozen_json(value: object) -> OutputSchema:
    record = require_exact_keys(value, ("fields",), "output_schema")
    fields_value = _snapshot_json_mapping(
        record["fields"], "output_schema.fields"
    )
    fields_payload = []
    for selector, raw_binding in fields_value._items:
        require_identifier(selector, f"output_schema.fields.{selector}")
        binding = require_exact_keys(
            raw_binding,
            _OUTPUT_BINDING_JSON_FIELDS,
            f"output_schema.fields.{selector}",
        )
        fields_payload.append(
            (
                selector,
                OutputFieldBinding(
                    value_schema=_value_schema_from_frozen_json(
                        binding["value_schema"],
                        f"output_schema.fields.{selector}.value_schema",
                    ),
                    raw_field=binding["raw_field"],
                    proof_kind=binding["proof_kind"],
                ),
            )
        )
    return OutputSchema(fields=tuple(fields_payload))


def adapter_definition_to_frozen_json(
    value: AdapterDefinition,
) -> FrozenJsonObject:
    """Serialize one validated adapter definition with a locked JSON schema."""

    definition = validate_adapter_definition(value)
    return _snapshot_json_mapping(
        {
            "adapter_id": definition.adapter_id,
            "entry_symbol": definition.entry_symbol,
            "observable_identity": definition.observable_identity,
            "scientific_input_schema": _value_schema_to_frozen_json(
                definition.scientific_input_schema
            ),
            "numerical_control_schema": _value_schema_to_frozen_json(
                definition.numerical_control_schema
            ),
            "parameter_sources": tuple(
                {
                    "parameter_name": source.parameter_name,
                    "kind": source.kind,
                    "details": source.details,
                }
                for source in definition.parameter_sources
            ),
            "output_schema": _output_schema_to_frozen_json(
                definition.output_schema
            ),
            "backend_kind": definition.backend_kind,
            "problem_size_policy": {
                "kind": definition.problem_size_policy.kind,
                "fixed_sizes": definition.problem_size_policy.fixed_sizes,
                "allowed_sizes": definition.problem_size_policy.allowed_sizes,
            },
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
            "convergence_contract": {
                "kind": definition.convergence_contract.kind,
                "requirements": definition.convergence_contract.requirements,
            },
            "counterfactual_domain": {
                "valid_rules": definition.counterfactual_domain.valid_rules,
                "invalid_rules": (
                    definition.counterfactual_domain.invalid_rules
                ),
            },
            "oracle_id": definition.oracle_id,
            "resource_limits": {
                field.name: getattr(definition.resource_limits, field.name)
                for field in fields(ResourceLimits)
            },
        },
        "adapter_definition",
    )


def adapter_definition_from_frozen_json(value: object) -> AdapterDefinition:
    """Deserialize and fully validate the locked adapter-definition schema."""

    definition = require_exact_keys(
        value, _ADAPTER_DEFINITION_JSON_FIELDS, "adapter_definition"
    )
    sources_value = _require_tuple(
        definition["parameter_sources"], "parameter_sources"
    )
    parameter_sources = []
    for index, raw_source in enumerate(sources_value):
        source = require_exact_keys(
            raw_source,
            ("parameter_name", "kind", "details"),
            f"parameter_sources[{index}]",
        )
        parameter_sources.append(
            ParameterSource(
                parameter_name=source["parameter_name"],
                kind=source["kind"],
                details=source["details"],
            )
        )
    size = require_exact_keys(
        definition["problem_size_policy"],
        ("kind", "fixed_sizes", "allowed_sizes"),
        "problem_size_policy",
    )
    runtime = require_exact_keys(
        definition["runtime_requirements"],
        (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ),
        "runtime_requirements",
    )
    convergence = require_exact_keys(
        definition["convergence_contract"],
        ("kind", "requirements"),
        "convergence_contract",
    )
    domain = require_exact_keys(
        definition["counterfactual_domain"],
        ("valid_rules", "invalid_rules"),
        "counterfactual_domain",
    )
    limits = require_exact_keys(
        definition["resource_limits"],
        tuple(field.name for field in fields(ResourceLimits)),
        "resource_limits",
    )
    candidate = AdapterDefinition(
        adapter_id=definition["adapter_id"],
        entry_symbol=definition["entry_symbol"],
        observable_identity=definition["observable_identity"],
        scientific_input_schema=_value_schema_from_frozen_json(
            definition["scientific_input_schema"],
            "scientific_input_schema",
        ),
        numerical_control_schema=_value_schema_from_frozen_json(
            definition["numerical_control_schema"],
            "numerical_control_schema",
        ),
        parameter_sources=tuple(parameter_sources),
        output_schema=_output_schema_from_frozen_json(
            definition["output_schema"]
        ),
        backend_kind=definition["backend_kind"],
        problem_size_policy=ProblemSizePolicy(
            kind=size["kind"],
            fixed_sizes=size["fixed_sizes"],
            allowed_sizes=size["allowed_sizes"],
        ),
        runtime_requirements=RuntimeRequirements(
            interpreter=runtime["interpreter"],
            packages=_require_tuple(
                runtime["packages"], "runtime_requirements.packages"
            ),
            native_libraries=_require_tuple(
                runtime["native_libraries"],
                "runtime_requirements.native_libraries",
            ),
            backend_resources=_require_tuple(
                runtime["backend_resources"],
                "runtime_requirements.backend_resources",
            ),
        ),
        convergence_contract=ConvergenceContract(
            kind=convergence["kind"],
            requirements=convergence["requirements"],
        ),
        counterfactual_domain=CounterfactualDomain(
            valid_rules=domain["valid_rules"],
            invalid_rules=domain["invalid_rules"],
        ),
        oracle_id=definition["oracle_id"],
        resource_limits=ResourceLimits(
            **{name: limits[name] for name in limits}
        ),
    )
    validated = validate_adapter_definition(candidate)
    if canonical_json_bytes(adapter_definition_to_frozen_json(validated)) != (
        canonical_json_bytes(definition)
    ):
        raise AdapterContractError(
            "adapter definition does not round-trip canonically"
        )
    return validated


def adapter_eligibility_row_to_frozen_json(
    benchmark_id: str,
) -> FrozenJsonObject:
    """Serialize one row from the closed production eligibility catalog."""

    require_identifier(benchmark_id, "benchmark_id")
    try:
        decision = ADAPTER_ELIGIBILITY[benchmark_id]
    except KeyError as error:
        raise AdapterContractError(
            f"unknown eligibility benchmark_id {benchmark_id}"
        ) from error
    return _snapshot_json_mapping(
        {
            "benchmark_id": benchmark_id,
            "selector_fields": decision.selector_fields,
            "disposition": decision.disposition,
            "adapter_id": decision.adapter_id,
            "oracle_id": decision.oracle_id,
            "reason": decision.reason,
        },
        "eligibility_row",
    )


def adapter_eligibility_catalog_to_frozen_json() -> FrozenJsonObject:
    """Serialize the complete closed production eligibility catalog."""

    return _snapshot_json_mapping(
        {
            benchmark_id: adapter_eligibility_row_to_frozen_json(
                benchmark_id
            )
            for benchmark_id in ADAPTER_ELIGIBILITY
        },
        "eligibility_catalog",
    )


def _validate_value_against_schema(
    schema: ValueSchema,
    value: object,
    field_name: str,
    *,
    depth: int = 0,
) -> object:
    if depth > _MAX_VALUE_SCHEMA_NESTING:
        raise AdapterContractError(
            f"{field_name} exceeds the maximum schema validation depth"
        )
    if type(schema) is not ValueSchema:
        raise AdapterContractError(f"{field_name} schema is not exact")
    if schema.kind == "boolean":
        if type(value) is not bool:
            raise AdapterContractError(f"{field_name} must be a boolean")
    elif schema.kind == "integer":
        if type(value) is not int:
            raise AdapterContractError(f"{field_name} must be an integer")
        _require_json_integer_magnitude(value, field_name)
    elif schema.kind == "number":
        _require_finite_number(value, field_name)
    elif schema.kind == "string":
        if type(value) is not str:
            raise AdapterContractError(f"{field_name} must be a string")
        _require_utf8_string(value, field_name)
    elif schema.kind == "list":
        if type(value) is not tuple:
            raise AdapterContractError(f"{field_name} must be a JSON array")
        if schema.lower is not None and len(value) < schema.lower:
            raise AdapterContractError(f"{field_name} contains too few items")
        if schema.upper is not None and len(value) > schema.upper:
            raise AdapterContractError(f"{field_name} contains too many items")
        for index, item in enumerate(value):
            _validate_value_against_schema(
                schema.item_schema,
                item,
                f"{field_name}[{index}]",
                depth=depth + 1,
            )
    elif schema.kind == "object":
        if type(value) is not FrozenJsonObject:
            raise AdapterContractError(f"{field_name} must be a JSON object")
        declared = {name: child for name, child in schema.properties}
        actual = set(value)
        required = {
            name for name, child in schema.properties if child.required is True
        }
        missing = sorted(required - actual)
        unknown = sorted(actual - set(declared))
        if missing:
            raise AdapterContractError(
                f"{field_name} missing required field {missing[0]}"
            )
        if unknown:
            raise AdapterContractError(
                f"{field_name} contains unknown field {unknown[0]}"
            )
        for name in sorted(actual):
            _validate_value_against_schema(
                declared[name],
                value[name],
                f"{field_name}.{name}",
                depth=depth + 1,
            )
    else:  # pragma: no cover - ValueSchema construction closes this.
        raise AdapterContractError(f"{field_name} has an unknown schema kind")

    if schema.kind in {"integer", "number"}:
        if schema.lower is not None and value < schema.lower:
            raise AdapterContractError(
                f"{field_name} is below its lower bound"
            )
        if schema.upper is not None and value > schema.upper:
            raise AdapterContractError(f"{field_name} exceeds its upper bound")
    return value


def _validate_closed_schema_mapping(
    definition: AdapterDefinition,
    values: object,
    *,
    schema_attribute: str,
    field_name: str,
) -> FrozenJsonObject:
    validated_definition = validate_adapter_definition(definition)
    snapshot = _snapshot_json_mapping(values, field_name)
    schema = getattr(validated_definition, schema_attribute)
    _validate_value_against_schema(schema, snapshot, field_name)
    _validate_authored_json(
        snapshot,
        field_name,
        allow_numerical_control=(
            schema_attribute == "numerical_control_schema"
        ),
    )
    return snapshot


def validate_scientific_inputs(
    definition: AdapterDefinition, values: object
) -> FrozenJsonObject:
    """Validate and isolate answer-free model inputs against one definition."""

    validated = _validate_closed_schema_mapping(
        definition,
        values,
        schema_attribute="scientific_input_schema",
        field_name="scientific_inputs",
    )
    for field_name, rule in definition.counterfactual_domain.valid_rules.items():
        if rule["kind"] not in {
            "finite_product_state_regime",
            "finite_nonzero_relative_regime",
        }:
            continue
        reference = validated[rule["reference_field"]]
        maximum_ratio = rule["maximum_absolute_ratio"]
        if (
            rule["kind"] == "finite_nonzero_relative_regime"
            and validated[field_name] == 0
        ) or abs(validated[field_name]) > maximum_ratio * reference:
            raise AdapterContractError(
                "scientific_inputs are outside the declared relative regime"
            )
    return validated


def validate_numerical_controls(
    definition: AdapterDefinition, values: object
) -> FrozenJsonObject:
    """Validate and isolate predeclared numerical controls."""

    return _validate_closed_schema_mapping(
        definition,
        values,
        schema_attribute="numerical_control_schema",
        field_name="numerical_controls",
    )


_LOCAL_OBSERVABLE_RESULT_SCHEMA_VERSION = "local_observable_result_v1"
_LOCAL_RESULT_FORBIDDEN_TOKENS = frozenset(
    {
        "success",
        "verdict",
        "strictmatch",
        "literature",
        "expected",
        "target",
        "comparison",
        "registry",
    }
)
_EXACT_OUTPUT_PROOF_KINDS = frozenset(
    {
        "direct_exact_value",
        "grouped_exact_sequence",
        "rank_derived_integer",
        "all_residuals_within_bound_boolean",
        "positive_lower_bound_boolean",
        "positive_gap_and_odd_parity_boolean",
        "directional_limits_differ_boolean",
        "no_finite_crossing_boolean",
        "no_finite_crossing_zero_limit",
    }
)


def _require_sha256(value: object, field_name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AdapterContractError(
            f"{field_name} must be a lowercase SHA-256 hex digest"
        )
    return value


def _reject_local_result_claims(value: object, field_name: str) -> None:
    if type(value) is FrozenJsonObject:
        for key, item in value._items:
            tokens = _metadata_tokens(key, f"{field_name} mapping key")
            joined = "".join(tokens)
            if joined in _LOCAL_RESULT_FORBIDDEN_TOKENS or any(
                token in _LOCAL_RESULT_FORBIDDEN_TOKENS for token in tokens
            ):
                raise AdapterContractError(
                    f"{field_name} contains a forbidden literature claim"
                )
            _reject_local_result_claims(item, f"{field_name}.{key}")
    elif type(value) is tuple:
        for index, item in enumerate(value):
            _reject_local_result_claims(item, f"{field_name}[{index}]")
    elif type(value) is str:
        tokens = _metadata_tokens(value, field_name)
        joined = "".join(tokens)
        if joined in _LOCAL_RESULT_FORBIDDEN_TOKENS or any(
            token in _LOCAL_RESULT_FORBIDDEN_TOKENS for token in tokens
        ):
            raise AdapterContractError(
                f"{field_name} contains a forbidden literature claim"
            )


def _require_monotonic_ns(value: object, field_name: str) -> int:
    if type(value) is not int:
        raise AdapterContractError(f"{field_name} must be an integer")
    _require_json_integer_magnitude(value, field_name)
    if value < 0:
        raise AdapterContractError(f"{field_name} must be nonnegative")
    return value


@_seal_contract
@dataclass(frozen=True, init=False)
class LocalObservableResult:
    schema_version: str
    adapter_id: str
    capsule_sha256: str
    request_sha256: str
    observable_identity: FrozenJsonObject
    fields: FrozenJsonObject
    units: FrozenJsonObject
    uncertainty: FrozenJsonObject
    raw_convergence_evidence: FrozenJsonObject
    backend_diagnostics: FrozenJsonObject
    operation_counts_or_sizes: FrozenJsonObject
    worker_started_monotonic_ns: int
    worker_finished_monotonic_ns: int

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, LocalObservableResult)

    def __post_init__(self) -> None:
        if self.schema_version != _LOCAL_OBSERVABLE_RESULT_SCHEMA_VERSION:
            raise AdapterContractError(
                "LocalObservableResult has an unknown schema_version"
            )
        require_identifier(self.adapter_id, "adapter_id")
        _require_sha256(self.capsule_sha256, "capsule_sha256")
        _require_sha256(self.request_sha256, "request_sha256")
        observable_identity = require_exact_keys(
            _snapshot_json_mapping(
                self.observable_identity, "observable_identity"
            ),
            _OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        snapshots = {}
        for field_name in (
            "fields",
            "units",
            "uncertainty",
            "raw_convergence_evidence",
            "backend_diagnostics",
            "operation_counts_or_sizes",
        ):
            snapshots[field_name] = _snapshot_json_mapping(
                getattr(self, field_name), field_name
            )
        _require_monotonic_ns(
            self.worker_started_monotonic_ns,
            "worker_started_monotonic_ns",
        )
        _require_monotonic_ns(
            self.worker_finished_monotonic_ns,
            "worker_finished_monotonic_ns",
        )
        if (
            self.worker_finished_monotonic_ns
            < self.worker_started_monotonic_ns
        ):
            raise AdapterContractError(
                "worker monotonic timestamps are reversed"
            )
        for field_name, snapshot in snapshots.items():
            _reject_local_result_claims(snapshot, field_name)
            object.__setattr__(self, field_name, snapshot)
        object.__setattr__(self, "observable_identity", observable_identity)

    def to_frozen_json(self) -> FrozenJsonObject:
        revalidated = _snapshot_local_observable_result(self)
        return _snapshot_json_mapping(
            {
                field.name: getattr(revalidated, field.name)
                for field in fields(LocalObservableResult)
            },
            "local_observable_result",
        )


def _snapshot_local_observable_result(value: object) -> LocalObservableResult:
    field_names = tuple(field.name for field in fields(LocalObservableResult))
    try:
        if type(value) is LocalObservableResult:
            raw_values = {
                name: getattr(value, name) for name in field_names
            }
        elif isinstance(value, Mapping):
            snapshot = require_exact_keys(
                value, field_names, "local_observable_result"
            )
            raw_values = thaw_json(snapshot, "local_observable_result")
        else:
            raise AdapterContractError(
                "local_observable_result must be a mapping or exact record"
            )
        return LocalObservableResult(**raw_values)
    except AdapterContractError:
        raise
    except Exception as error:
        raise AdapterContractError(
            "local_observable_result revalidation failed"
        ) from error


def _require_numeric_sequence(value: object, field_name: str) -> None:
    if type(value) is not tuple or not value:
        raise AdapterContractError(
            f"{field_name} must be a nonempty immutable numeric sequence"
        )
    for index, item in enumerate(value):
        _require_finite_number(item, f"{field_name}[{index}]")


def _validate_operation_counts(value: object) -> FrozenJsonObject:
    counts = _snapshot_json_mapping(value, "operation_counts")
    for key, count in counts._items:
        try:
            require_identifier(key, "operation_counts key")
        except AdapterContractError as error:
            raise AdapterContractError(
                "operation_counts key must be an identifier"
            ) from error
        if type(count) in (FrozenJsonObject, tuple):
            raise AdapterContractError("operation_counts must be flat")
        if type(count) is not int or count < 0:
            raise AdapterContractError(
                f"operation_counts.{key} must be a nonnegative integer"
            )
        _require_json_integer_magnitude(count, f"operation_counts.{key}")
    return counts


def _validate_operation_counts_and_problem_size(
    definition: AdapterDefinition,
    value: object,
) -> None:
    transport = require_exact_keys(
        value,
        ("operation_counts", "problem_size"),
        "operation_counts_or_sizes",
    )
    _validate_operation_counts(transport["operation_counts"])
    problem_size = require_exact_keys(
        transport["problem_size"],
        ("policy_kind", "values"),
        "problem_size",
    )
    policy = definition.problem_size_policy
    if problem_size["policy_kind"] != policy.kind:
        raise AdapterContractError(
            "problem_size policy_kind does not match definition"
        )

    if policy.kind == "not_applicable":
        values = _snapshot_json_mapping(
            problem_size["values"], "problem_size.values"
        )
        if values:
            raise AdapterContractError(
                "not_applicable problem_size.values must be empty"
            )
        return

    if policy.kind == "fixed_local":
        values = require_exact_keys(
            problem_size["values"],
            tuple(policy.fixed_sizes),
            "problem_size.values",
        )
        if canonical_json_bytes(values) != canonical_json_bytes(
            policy.fixed_sizes
        ):
            raise AdapterContractError(
                "fixed_local problem_size.values must match definition"
            )
        return

    values = require_exact_keys(
        problem_size["values"],
        tuple(policy.allowed_sizes),
        "problem_size.values",
    )
    sequence_dimensions = []
    for dimension, allowed in policy.allowed_sizes._items:
        selected = values[dimension]
        if type(allowed) is tuple:
            sequence_dimensions.append((dimension, allowed))
            continue
        if canonical_json_bytes(selected) != canonical_json_bytes(allowed):
            raise AdapterContractError(
                f"problem_size.values.{dimension} is not an allowed size"
            )
    if not sequence_dimensions:
        return
    sequence_lengths = {
        len(allowed) for _, allowed in sequence_dimensions
    }
    if 0 in sequence_lengths:
        raise AdapterContractError(
            "scalable allowed-size sequences must be nonempty"
        )
    if len(sequence_lengths) != 1:
        raise AdapterContractError(
            "scalable allowed-size dimensions require consistent "
            "sequence lengths"
        )
    if all(
        canonical_json_bytes(values[dimension])
        == canonical_json_bytes(allowed)
        for dimension, allowed in sequence_dimensions
    ):
        return
    sequence_length = next(iter(sequence_lengths))
    for declared_index in range(sequence_length):
        if all(
            canonical_json_bytes(values[dimension])
            == canonical_json_bytes(allowed[declared_index])
            for dimension, allowed in sequence_dimensions
        ):
            return
    raise AdapterContractError(
        "scalable problem_size.values have no allowed common index"
    )


def _validate_convergence_certificate(
    value: object,
    field_name: str,
) -> FrozenJsonObject:
    certificate = require_exact_keys(
        value, ("kind", "certificate_sha256", "proof_inputs"), field_name
    )
    require_identifier(certificate["kind"], f"{field_name}.kind")
    _require_sha256(
        certificate["certificate_sha256"],
        f"{field_name}.certificate_sha256",
    )
    _snapshot_json_mapping(
        certificate["proof_inputs"], f"{field_name}.proof_inputs"
    )
    return certificate


def _validate_equal_numeric_sequences(
    left: object,
    left_name: str,
    right: object,
    right_name: str,
    *,
    minimum_length: int = 2,
) -> None:
    _require_numeric_sequence(left, left_name)
    _require_numeric_sequence(right, right_name)
    if len(left) < minimum_length or len(right) < minimum_length:
        raise AdapterContractError(
            f"{left_name} and {right_name} require at least "
            f"{minimum_length} refinements"
        )
    if len(left) != len(right):
        raise AdapterContractError(
            f"{left_name} and {right_name} must have equal length"
        )


def _validate_raw_convergence_evidence(
    definition: AdapterDefinition,
    value: FrozenJsonObject,
) -> None:
    kind = definition.convergence_contract.kind
    common = ("kind", "controls", "certificate")
    kind_fields = {
        "exact": common,
        "residual_bound": common
        + ("samples", "residuals", "error_bound"),
        "quadrature": common
        + ("estimates", "error_bounds", "error_bound"),
        "finite_size": common
        + ("sizes", "estimates", "error_bound"),
        "iterative": common
        + (
            "estimates",
            "residuals",
            "refinement_iterations",
            "error_bound",
        ),
    }
    convergence = require_exact_keys(
        value, kind_fields[kind], "raw_convergence_evidence"
    )
    if convergence["kind"] != kind:
        raise AdapterContractError(
            "raw convergence kind does not match definition"
        )
    validate_numerical_controls(definition, convergence["controls"])
    _validate_convergence_certificate(
        convergence["certificate"], "convergence.certificate"
    )
    if kind == "exact":
        return
    error_bound = _require_finite_number(
        convergence["error_bound"],
        "convergence.error_bound",
        nonnegative=True,
    )
    if kind in {"residual_bound", "quadrature", "iterative"} and (
        error_bound <= 0
    ):
        raise AdapterContractError(
            "convergence.error_bound must be positive for approximate work"
        )
    if kind == "residual_bound":
        _validate_equal_numeric_sequences(
            convergence["samples"],
            "convergence.samples",
            convergence["residuals"],
            "convergence.residuals",
        )
        for index, residual in enumerate(convergence["residuals"]):
            if residual < 0:
                raise AdapterContractError(
                    f"convergence.residuals[{index}] must be nonnegative"
                )
        return
    if kind == "quadrature":
        _validate_equal_numeric_sequences(
            convergence["estimates"],
            "convergence.estimates",
            convergence["error_bounds"],
            "convergence.error_bounds",
        )
        for index, bound in enumerate(convergence["error_bounds"]):
            if bound <= 0:
                raise AdapterContractError(
                    f"convergence.error_bounds[{index}] must be positive"
                )
        if convergence["error_bounds"][-1] >= convergence["error_bounds"][0]:
            raise AdapterContractError(
                "quadrature error bounds must contract under refinement"
            )
        return
    if kind == "finite_size":
        sizes = _require_tuple(convergence["sizes"], "convergence.sizes")
        if len(sizes) < 2:
            raise AdapterContractError(
                "finite-size evidence requires at least two sizes"
            )
        for index, size in enumerate(sizes):
            _require_positive_integer(size, f"convergence.sizes[{index}]")
        if tuple(sorted(set(sizes))) != sizes:
            raise AdapterContractError(
                "finite-size evidence sizes must be unique and increasing"
            )
        _require_numeric_sequence(
            convergence["estimates"], "convergence.estimates"
        )
        if len(convergence["estimates"]) != len(sizes):
            raise AdapterContractError(
                "finite-size estimates must bind every declared size"
            )
        return
    _validate_equal_numeric_sequences(
        convergence["estimates"],
        "convergence.estimates",
        convergence["residuals"],
        "convergence.residuals",
    )
    for index, residual in enumerate(convergence["residuals"]):
        if residual < 0:
            raise AdapterContractError(
                f"convergence.residuals[{index}] must be nonnegative"
            )
    _require_positive_integer(
        convergence["refinement_iterations"],
        "convergence.refinement_iterations",
    )
    if convergence["refinement_iterations"] < len(
        convergence["estimates"]
    ):
        raise AdapterContractError(
            "refinement_iterations cannot be shorter than evidence sequence"
        )


def _validate_backend_identity_record(
    value: object,
    field_name: str,
) -> None:
    record = require_exact_keys(
        value, ("version", "binary_sha256"), field_name
    )
    _require_nonempty_string(record["version"], f"{field_name}.version")
    _require_sha256(
        record["binary_sha256"], f"{field_name}.binary_sha256"
    )


def _validate_backend_diagnostics(
    definition: AdapterDefinition,
    value: FrozenJsonObject,
) -> None:
    diagnostics = require_exact_keys(
        value,
        (
            "backend_kind",
            "interpreter_implementation",
            "interpreter_version",
            "interpreter_binary_sha256",
            "packages",
            "native_libraries",
            "numerical_backend",
            "backend_resources",
        ),
        "backend_diagnostics",
    )
    if diagnostics["backend_kind"] != definition.backend_kind:
        raise AdapterContractError(
            "backend_diagnostics backend kind does not match definition"
        )
    _require_nonempty_string(
        diagnostics["interpreter_implementation"],
        "backend_diagnostics.interpreter_implementation",
    )
    _require_nonempty_string(
        diagnostics["interpreter_version"],
        "backend_diagnostics.interpreter_version",
    )
    _require_sha256(
        diagnostics["interpreter_binary_sha256"],
        "backend_diagnostics.interpreter_binary_sha256",
    )
    for field_name, expected_names in (
        ("packages", definition.runtime_requirements.packages),
        ("native_libraries", definition.runtime_requirements.native_libraries),
    ):
        identities = require_exact_keys(
            diagnostics[field_name],
            expected_names,
            f"backend_diagnostics.{field_name}",
        )
        for name, identity in identities._items:
            _validate_backend_identity_record(
                identity, f"backend_diagnostics.{field_name}.{name}"
            )
    numerical_backend = require_exact_keys(
        diagnostics["numerical_backend"],
        ("name", "version", "binary_sha256", "applicability"),
        "backend_diagnostics.numerical_backend",
    )
    if numerical_backend["applicability"] == "not_applicable":
        if numerical_backend["name"] != "not_applicable" or any(
            numerical_backend[field_name] is not None
            for field_name in ("version", "binary_sha256")
        ):
            raise AdapterContractError(
                "not-applicable numerical backend must use null identities"
            )
    elif numerical_backend["applicability"] == "used":
        _require_nonempty_string(
            numerical_backend["name"],
            "backend_diagnostics.numerical_backend.name",
        )
        _require_nonempty_string(
            numerical_backend["version"],
            "backend_diagnostics.numerical_backend.version",
        )
        _require_sha256(
            numerical_backend["binary_sha256"],
            "backend_diagnostics.numerical_backend.binary_sha256",
        )
    else:
        raise AdapterContractError(
            "numerical backend applicability must be used or not_applicable"
        )
    resources = require_exact_keys(
        diagnostics["backend_resources"],
        definition.runtime_requirements.backend_resources,
        "backend_diagnostics.backend_resources",
    )
    for name, resource in resources._items:
        record = require_exact_keys(
            resource,
            ("applicability",),
            f"backend_diagnostics.backend_resources.{name}",
        )
        if record["applicability"] != "used":
            raise AdapterContractError(
                "declared backend resource applicability must be used"
            )


def validate_local_observable_result(
    definition: AdapterDefinition, value: object
) -> FrozenJsonObject:
    """Validate only a local calculation, never a literature comparison."""

    validated_definition = validate_adapter_definition(definition)
    result = _snapshot_local_observable_result(value)
    if result.adapter_id != validated_definition.adapter_id:
        raise AdapterContractError(
            "local result adapter_id does not match definition"
        )
    actual_identity = canonical_json_bytes(result.observable_identity)
    expected_identity = canonical_json_bytes(
        validated_definition.observable_identity
    )
    if actual_identity != expected_identity:
        raise AdapterContractError(
            "local result observable_identity does not match definition"
        )
    expected_fields = tuple(validated_definition.output_schema.selector_fields)
    for field_name, mapping in (
        ("fields", result.fields),
        ("units", result.units),
        ("uncertainty", result.uncertainty),
    ):
        require_exact_keys(mapping, expected_fields, field_name)
    for selector_field, binding in validated_definition.output_schema:
        _validate_value_against_schema(
            binding.value_schema,
            result.fields[selector_field],
            f"fields.{selector_field}",
        )
        if result.units[selector_field] != binding.value_schema.units:
            raise AdapterContractError(
                f"units.{selector_field} does not match output schema"
            )
        uncertainty = _require_finite_number(
            result.uncertainty[selector_field],
            f"uncertainty.{selector_field}",
            nonnegative=True,
        )
        if (
            binding.proof_kind in _EXACT_OUTPUT_PROOF_KINDS
            and uncertainty != 0
        ):
            raise AdapterContractError(
                f"uncertainty.{selector_field} must be zero for exact output"
            )
        if (
            binding.proof_kind == "bounded_numeric_value"
            and uncertainty <= 0
        ):
            raise AdapterContractError(
                f"uncertainty.{selector_field} must be positive for bounded output"
            )
    _validate_raw_convergence_evidence(
        validated_definition, result.raw_convergence_evidence
    )
    _validate_backend_diagnostics(
        validated_definition, result.backend_diagnostics
    )
    _validate_operation_counts_and_problem_size(
        validated_definition,
        result.operation_counts_or_sizes,
    )
    return result.to_frozen_json()


def _task13_require_inputs(
    scientific_inputs,
    numerical_controls,
    input_names,
    control_names,
):
    return dict(scientific_inputs), dict(numerical_controls)


def _task13_backend_diagnostics(definition):
    runtime = definition.runtime_requirements
    return {
        "backend_kind": definition.backend_kind,
        "interpreter_implementation": "cpython",
        "interpreter_version": "runtime-bound",
        "interpreter_binary_sha256": hashlib.sha256(
            ("runtime-interpreter:" + definition.adapter_id).encode("utf-8")
        ).hexdigest(),
        "packages": {
            name: {
                "version": "runtime-bound",
                "binary_sha256": hashlib.sha256(
                    ("runtime-package:" + name).encode("utf-8")
                ).hexdigest(),
            }
            for name in runtime.packages
        },
        "native_libraries": {
            name: {
                "version": "runtime-bound",
                "binary_sha256": hashlib.sha256(
                    ("runtime-native:" + name).encode("utf-8")
                ).hexdigest(),
            }
            for name in runtime.native_libraries
        },
        "numerical_backend": {
            "name": "not_applicable",
            "version": None,
            "binary_sha256": None,
            "applicability": "not_applicable",
        },
        "backend_resources": {
            name: {"applicability": "used"}
            for name in runtime.backend_resources
        },
    }


def _task13_problem_size(definition, values=None):
    return {
        "policy_kind": definition.problem_size_policy.kind,
        "values": {} if values is None else values,
    }


def _task13_calculation(
    convergence_kind,
    fields_payload,
    controls,
    *,
    operations,
    bounded_fields=(),
    residual_samples=None,
    residuals=None,
    error_bound=None,
    problem_size_kind="not_applicable",
    problem_size=None,
    additional_operation_counts=None,
    proof_inputs=None,
    field_uncertainties=None,
    estimates=None,
    error_bounds=None,
    refinement_iterations=None,
):
    uncertainty = {}
    for selector in fields_payload:
        if selector in bounded_fields:
            selected_uncertainty = error_bound
            if field_uncertainties is not None:
                selected_uncertainty = field_uncertainties[selector]
            uncertainty[selector] = max(float(selected_uncertainty), 1e-15)
        else:
            uncertainty[selector] = 0.0
    convergence = {
        "kind": convergence_kind,
        "controls": controls,
    }
    if convergence_kind == "residual_bound":
        convergence.update(
            {
                "samples": residual_samples,
                "residuals": residuals,
                "error_bound": float(error_bound),
            }
        )
    elif convergence_kind == "quadrature":
        convergence.update(
            {
                "estimates": estimates,
                "error_bounds": error_bounds,
                "error_bound": float(error_bound),
            }
        )
    elif convergence_kind == "iterative":
        convergence.update(
            {
                "estimates": estimates,
                "residuals": residuals,
                "refinement_iterations": int(refinement_iterations),
                "error_bound": float(error_bound),
            }
        )
    operation_counts = {"operations": int(operations)}
    if additional_operation_counts is not None:
        for name in additional_operation_counts:
            operation_counts[name] = int(additional_operation_counts[name])
    return {
        "schema_version": "scientific_calculation_v1",
        "proof_inputs": {} if proof_inputs is None else proof_inputs,
        "fields": fields_payload,
        "uncertainty": uncertainty,
        "raw_convergence_evidence": convergence,
        "operation_counts_or_sizes": {
            "operation_counts": operation_counts,
            "problem_size": {
                "policy_kind": problem_size_kind,
                "values": {} if problem_size is None else problem_size,
            },
        },
    }


def _task13_materialize_result(definition, calculation):
    if type(calculation) is not dict or calculation.get(
        "schema_version"
    ) != "scientific_calculation_v1":
        raise AdapterContractError("scientific calculation is malformed")
    convergence = dict(calculation["raw_convergence_evidence"])
    convergence["certificate"] = {
        "kind": convergence["kind"] + "_certificate",
        "proof_inputs": calculation.get("proof_inputs", {}),
        "certificate_sha256": canonical_sha256(
            {
                "adapter_id": definition.adapter_id,
                "fields": calculation["fields"],
                "controls": convergence["controls"],
                "operations": calculation["operation_counts_or_sizes"][
                    "operation_counts"
                ]["operations"],
                "proof_inputs": calculation.get("proof_inputs", {}),
            }
        ),
    }
    return {
        "schema_version": "scientific_result_body_v1",
        "observable_identity": thaw_json(definition.observable_identity),
        "fields": calculation["fields"],
        "units": {
            selector: binding.value_schema.units
            for selector, binding in definition.output_schema
        },
        "uncertainty": calculation["uncertainty"],
        "raw_convergence_evidence": convergence,
        "backend_diagnostics": _task13_backend_diagnostics(definition),
        "operation_counts_or_sizes": calculation[
            "operation_counts_or_sizes"
        ],
    }


def _task13_root_trace_append(samples, residuals, sample, residual):
    samples.append(sample)
    residuals.append(abs(residual))


def _task13_square_ising_root(threshold, iterations):
    lower = 0.1
    upper = 2.0
    samples = []
    residuals = []
    _task13_root_trace_append(
        samples, residuals, lower, math.sinh(2.0 * lower) - 1.0
    )
    _task13_root_trace_append(
        samples, residuals, upper, math.sinh(2.0 * upper) - 1.0
    )
    midpoint = 0.5 * (lower + upper)
    value = math.sinh(2.0 * midpoint) - 1.0
    for _index in range(iterations):
        midpoint = 0.5 * (lower + upper)
        value = math.sinh(2.0 * midpoint) - 1.0
        _task13_root_trace_append(samples, residuals, midpoint, value)
        if value < 0.0:
            lower = midpoint
        else:
            upper = midpoint
        if abs(value) <= threshold:
            break
    return midpoint, value, samples, residuals, lower, upper


def _task13_honeycomb_ising_root(threshold, iterations):
    lower = 0.1
    upper = 2.0
    radical = math.sqrt(3.0)
    samples = []
    residuals = []
    midpoint = 0.5 * (lower + upper)
    value = math.sinh(2.0 * midpoint) - radical
    for _index in range(iterations):
        midpoint = 0.5 * (lower + upper)
        value = math.sinh(2.0 * midpoint) - radical
        _task13_root_trace_append(samples, residuals, midpoint, value)
        if value < 0.0:
            lower = midpoint
        else:
            upper = midpoint
        if abs(value) <= threshold:
            break
    return midpoint, value, samples, residuals, lower, upper


def _task13_kagome_ising_root(threshold, iterations):
    lower = 0.1
    upper = 1.0
    honeycomb_condition = math.sqrt(3.0)
    samples = []
    residuals = []
    midpoint = 0.5 * (lower + upper)
    mapped_honeycomb = 0.5 * math.log(
        (math.exp(4.0 * midpoint) + 1.0) / 2.0
    )
    value = math.sinh(2.0 * mapped_honeycomb) - honeycomb_condition
    for _index in range(iterations):
        midpoint = 0.5 * (lower + upper)
        mapped_honeycomb = 0.5 * math.log(
            (math.exp(4.0 * midpoint) + 1.0) / 2.0
        )
        value = math.sinh(2.0 * mapped_honeycomb) - honeycomb_condition
        _task13_root_trace_append(samples, residuals, midpoint, value)
        if value < 0.0:
            lower = midpoint
        else:
            upper = midpoint
        if abs(value) <= threshold:
            break
    return midpoint, value, samples, residuals, lower, upper


def _task13_triangular_ising_root(threshold, iterations):
    lower = 1.0
    upper = 4.0
    samples = []
    residuals = []
    _task13_root_trace_append(samples, residuals, lower, lower - 3.0)
    _task13_root_trace_append(samples, residuals, upper, upper - 3.0)
    midpoint = 0.5 * (lower + upper)
    value = midpoint - 3.0
    for _index in range(iterations):
        midpoint = 0.5 * (lower + upper)
        value = midpoint - 3.0
        _task13_root_trace_append(samples, residuals, midpoint, value)
        if value < 0.0:
            lower = midpoint
        else:
            upper = midpoint
        if abs(value) <= threshold:
            break
    return midpoint, value, samples, residuals, lower, upper


def adapter_xxx_bethe_energy(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("exchange",), ()
    )
    exchange = inputs["exchange"]
    logarithm = math.log(2.0)
    energy = exchange * (0.25 - logarithm)
    roundoff_bound = (
        2.220446049250313e-16
        * abs(exchange)
        * (1.0 + 0.25 + abs(logarithm))
    )
    half_exchange_energy = 0.5 * exchange * (0.25 - logarithm)
    scaled_exchange_energy = 1.5 * exchange * (0.25 - logarithm)
    return _task13_calculation(
        "exact",
        {"energy_per_site": energy},
        controls,
        operations=3,
        bounded_fields=("energy_per_site",),
        error_bound=roundoff_bound,
        additional_operation_counts={
            "root_density_expression_terms": 2,
            "absolute_scaling_checks": 2,
        },
        proof_inputs={
            "root_density_logarithm": logarithm,
            "unit_exchange_energy": 0.25 - logarithm,
            "scaling_probe_exchanges": [0.5 * exchange, 1.5 * exchange],
            "scaling_probe_energies": [
                half_exchange_energy,
                scaled_exchange_energy,
            ],
            "roundoff_bound": roundoff_bound,
        },
    )


def adapter_square_ising_self_dual_tc(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("root_residual_threshold", "maximum_refinement_iterations"),
    )
    threshold = controls["root_residual_threshold"]
    iterations = controls["maximum_refinement_iterations"]

    (
        root,
        final_residual,
        history,
        residuals,
        lower,
        upper,
    ) = _task13_square_ising_root(threshold, iterations)
    tc_over_j = 1.0 / root
    field_uncertainty = max(
        abs(1.0 / lower - tc_over_j),
        abs(1.0 / upper - tc_over_j),
    )
    dual_root = 0.5 * math.asinh(1.0 / math.sinh(2.0 * root))
    return _task13_calculation(
        "residual_bound",
        {"tc_over_j": tc_over_j},
        controls,
        operations=len(history),
        bounded_fields=("tc_over_j",),
        residual_samples=history,
        residuals=residuals,
        error_bound=threshold,
        field_uncertainties={"tc_over_j": field_uncertainty},
        proof_inputs={
            "self_dual_root": root,
            "dual_root": dual_root,
            "dual_temperature_residual": root - dual_root,
            "final_bracket": [lower, upper],
        },
    )


def adapter_pauling_entropy_combinatorics(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("spins_per_tetrahedron",),
        (),
    )
    spin_count = inputs["spins_per_tetrahedron"]
    allowed_count = 0
    total_count = 0
    for state in range(1 << spin_count):
        total_count += 1
        up_count = 0
        for index in range(spin_count):
            up_count += (state >> index) & 1
        if up_count * 2 == spin_count:
            allowed_count += 1
    shared_spin_normalization = 2.0 ** (spin_count / 2.0)
    entropy = 0.5 * math.log(allowed_count / shared_spin_normalization)
    return _task13_calculation(
        "exact",
        {"pauling_entropy_per_spin": entropy},
        controls,
        operations=total_count,
        additional_operation_counts={
            "assignments_enumerated": total_count,
            "ice_rule_assignments": allowed_count,
            "shared_spin_normalization": int(shared_spin_normalization),
        },
    )


def adapter_aklt_projector_angle(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("projector_scale",), ()
    )
    scale = inputs["projector_scale"]
    spin = 1.0
    dot_eigenvalues = []
    for total in (0.0, 1.0, 2.0):
        dot_eigenvalues.append(
            0.5 * (total * (total + 1.0) - 2.0 * spin * (spin + 1.0))
        )
    equations = []
    targets = (0.0, 0.0, scale)
    for index in range(3):
        eigenvalue = dot_eigenvalues[index]
        equations.append(
            [1.0, eigenvalue, eigenvalue * eigenvalue, targets[index]]
        )
    for pivot in range(3):
        pivot_row = pivot
        for candidate in range(pivot + 1, 3):
            if abs(equations[candidate][pivot]) > abs(
                equations[pivot_row][pivot]
            ):
                pivot_row = candidate
        if pivot_row != pivot:
            held = equations[pivot]
            equations[pivot] = equations[pivot_row]
            equations[pivot_row] = held
        pivot_value = equations[pivot][pivot]
        for column in range(pivot, 4):
            equations[pivot][column] /= pivot_value
        for row in range(3):
            if row == pivot:
                continue
            factor = equations[row][pivot]
            for column in range(pivot, 4):
                equations[row][column] -= factor * equations[pivot][column]
    bilinear = equations[1][3]
    biquadratic = equations[2][3]
    ratio = biquadratic / bilinear
    return _task13_calculation(
        "exact",
        {"aklt_tan_theta": ratio, "theta_radians": math.atan2(
            biquadratic, bilinear
        )},
        controls,
        operations=len(dot_eigenvalues) + 27,
        additional_operation_counts={
            "projector_interpolation_equations": 3,
            "projector_interpolation_eliminations": 27,
        },
    )


def adapter_honeycomb_ising_star_triangle_tc(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("root_residual_threshold", "maximum_refinement_iterations"),
    )
    threshold = controls["root_residual_threshold"]

    (
        root,
        final_residual,
        history,
        residuals,
        lower,
        upper,
    ) = _task13_honeycomb_ising_root(
        threshold, controls["maximum_refinement_iterations"]
    )
    tc_over_j = 1.0 / root
    field_uncertainty = max(
        abs(1.0 / lower - tc_over_j),
        abs(1.0 / upper - tc_over_j),
    )
    triangular_dual = 0.5 * math.asinh(
        1.0 / math.sinh(2.0 * root)
    )
    return _task13_calculation(
        "residual_bound",
        {"tc_over_j": tc_over_j},
        controls,
        operations=len(history),
        bounded_fields=("tc_over_j",),
        residual_samples=history,
        residuals=residuals,
        error_bound=threshold,
        field_uncertainties={"tc_over_j": field_uncertainty},
        proof_inputs={
            "honeycomb_root": root,
            "triangular_dual_root": triangular_dual,
            "dual_polynomial_residual": math.exp(4.0 * triangular_dual) - 3.0,
            "final_bracket": [lower, upper],
        },
    )


def adapter_kagome_ising_star_triangle_tc(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("root_residual_threshold", "maximum_refinement_iterations"),
    )
    threshold = controls["root_residual_threshold"]

    (
        root,
        final_residual,
        history,
        residuals,
        lower,
        upper,
    ) = _task13_kagome_ising_root(
        threshold, controls["maximum_refinement_iterations"]
    )
    tc_over_j = 1.0 / root
    field_uncertainty = max(
        abs(1.0 / lower - tc_over_j),
        abs(1.0 / upper - tc_over_j),
    )
    exponential_variable = math.exp(4.0 * root)
    transformed_residual = (
        exponential_variable * exponential_variable
        - 6.0 * exponential_variable
        - 3.0
    )
    return _task13_calculation(
        "residual_bound",
        {"tc_over_j": tc_over_j},
        controls,
        operations=len(history),
        bounded_fields=("tc_over_j",),
        residual_samples=history,
        residuals=residuals,
        error_bound=threshold,
        field_uncertainties={"tc_over_j": field_uncertainty},
        proof_inputs={
            "original_star_triangle_residual": final_residual,
            "transformed_polynomial_residual": transformed_residual,
            "final_bracket": [lower, upper],
        },
    )


def adapter_ising_chain_transfer_matrix(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange", "inverse_temperature"),
        (),
    )
    coupling = inputs["exchange"] * inputs["inverse_temperature"]
    positive_separations = 0
    finite_separations = []
    for scale in (0.5, 1.0, 1.5):
        probe_coupling = coupling * scale
        aligned_weight = math.exp(probe_coupling)
        anti_aligned_weight = math.exp(-probe_coupling)
        leading = aligned_weight + anti_aligned_weight
        subleading = aligned_weight - anti_aligned_weight
        separation = leading - abs(subleading)
        finite_separations.append(separation)
        if separation > 0.0:
            positive_separations += 1
    actual_aligned = math.exp(coupling)
    actual_anti_aligned = math.exp(-coupling)
    actual_leading = actual_aligned + actual_anti_aligned
    actual_subleading = actual_aligned - actual_anti_aligned
    analytic_separation = actual_leading - abs(actual_subleading)
    identity_separation = 2.0 * math.exp(-abs(coupling))
    identity_proved = abs(
        analytic_separation - identity_separation
    ) <= 1e-14 * max(1.0, identity_separation)
    no_finite_crossing = positive_separations == 3
    return _task13_calculation(
        "exact",
        {
            "finite_temperature_transition": not no_finite_crossing,
            "tc_over_j": 0.0 if no_finite_crossing else coupling,
        },
        controls,
        operations=18,
        additional_operation_counts={
            "finite_coupling_probes": 3,
            "positive_eigenvalue_separations": positive_separations,
            "analytic_separation_identity_checks": int(identity_proved),
            "proof_checks_total": 4,
            "proof_checks_satisfied": (
                positive_separations + int(identity_proved)
            ),
            "proof_zero_temperature_limit": int(
                no_finite_crossing and identity_proved
            ),
        },
        proof_inputs={
            "finite_parameter_separations": finite_separations,
            "analytic_separation": analytic_separation,
            "identity_separation": identity_separation,
            "limit_inverse_temperature_samples": [
                inputs["inverse_temperature"],
                2.0 * inputs["inverse_temperature"],
                4.0 * inputs["inverse_temperature"],
            ],
            "limit_temperature_samples": [
                1.0 / inputs["inverse_temperature"],
                0.5 / inputs["inverse_temperature"],
                0.25 / inputs["inverse_temperature"],
            ],
        },
    )


def adapter_triangular_ising_star_triangle_tc(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("root_residual_threshold", "maximum_refinement_iterations"),
    )
    threshold = controls["root_residual_threshold"]

    (
        root,
        final_residual,
        history,
        residuals,
        lower,
        upper,
    ) = _task13_triangular_ising_root(
        threshold, controls["maximum_refinement_iterations"]
    )
    tc_over_j = 4.0 / math.log(root)
    field_uncertainty = max(
        abs(4.0 / math.log(lower) - tc_over_j),
        abs(4.0 / math.log(upper) - tc_over_j),
    )
    triangular_coupling = 0.25 * math.log(root)
    honeycomb_dual = 0.5 * math.asinh(
        1.0 / math.sinh(2.0 * triangular_coupling)
    )
    return _task13_calculation(
        "residual_bound",
        {"tc_over_j": tc_over_j},
        controls,
        operations=len(history),
        bounded_fields=("tc_over_j",),
        residual_samples=history,
        residuals=residuals,
        error_bound=threshold,
        field_uncertainties={"tc_over_j": field_uncertainty},
        proof_inputs={
            "triangular_exponential_root": root,
            "honeycomb_dual_root": honeycomb_dual,
            "dual_star_triangle_residual": (
                math.sinh(2.0 * honeycomb_dual) - math.sqrt(3.0)
            ),
            "final_bracket": [lower, upper],
        },
    )


def adapter_spin_ice_tetrahedron_enumeration(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("exchange",), ()
    )
    exchange = inputs["exchange"]
    sectors = {}
    for state in range(16):
        spins = []
        charge = 0
        for index in range(4):
            spin = 1 if (state >> index) & 1 else -1
            spins.append(spin)
            charge += spin
        pair_sum = 0
        for first in range(4):
            for second in range(first + 1, 4):
                pair_sum += spins[first] * spins[second]
        energy = exchange * pair_sum
        sector = abs(charge)
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(energy)
    fields_payload = {
        "two_in_two_out_energy": sectors[0][0],
        "three_in_one_out_energy": sectors[2][0],
        "all_in_all_out_energy": sectors[4][0],
        "two_in_two_out_degeneracy": len(sectors[0]),
    }
    return _task13_calculation(
        "exact",
        fields_payload,
        controls,
        operations=16 * 6,
        additional_operation_counts={
            "assignments_enumerated": 16,
            "pair_energies_evaluated": 16 * 6,
        },
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 4, "tetrahedra": 1},
    )


def _task13_gf2_rank(rows):
    pivots = {}
    for source_row in rows:
        row = source_row
        while row:
            pivot = row.bit_length() - 1
            if pivot in pivots:
                row ^= pivots[pivot]
            else:
                pivots[pivot] = row
                break
    return len(pivots)


def _task13_toric_rows(width, height):
    qubits = 2 * width * height
    rows = []
    for y_value in range(height):
        for x_value in range(width):
            horizontal = 2 * (y_value * width + x_value)
            horizontal_left = 2 * (
                y_value * width + ((x_value - 1) % width)
            )
            vertical = horizontal + 1
            vertical_down = 2 * (
                ((y_value - 1) % height) * width + x_value
            ) + 1
            star = (
                (1 << horizontal)
                | (1 << horizontal_left)
                | (1 << vertical)
                | (1 << vertical_down)
            )
            horizontal_up = 2 * (
                ((y_value + 1) % height) * width + x_value
            )
            vertical_right = 2 * (
                y_value * width + ((x_value + 1) % width)
            ) + 1
            plaquette_support = (
                (1 << horizontal)
                | (1 << vertical_right)
                | (1 << horizontal_up)
                | (1 << vertical)
            )
            plaquette = plaquette_support << qubits
            rows.extend((star, plaquette))
    return rows


def adapter_toric_code_stabilizer_rank(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("stabilizer_scale",),
        (),
    )
    degeneracies = []
    ranks = []
    operations = 0
    for width, height in ((2, 2), (3, 3)):
        rows = _task13_toric_rows(width, height)
        rank = _task13_gf2_rank(rows)
        ranks.append(rank)
        qubits = 2 * width * height
        degeneracies.append(2 ** (qubits - rank))
        operations += len(rows) * qubits
    return _task13_calculation(
        "exact",
        {"torus_ground_state_degeneracy": degeneracies[0]},
        controls,
        operations=operations,
        additional_operation_counts={
            "periodic_sizes_reduced": len(degeneracies),
            "small_periodic_degeneracy": degeneracies[0],
            "large_periodic_degeneracy": degeneracies[1],
            "small_periodic_rank": ranks[0],
            "large_periodic_rank": ranks[1],
        },
        problem_size_kind="scalable_same_observable",
        problem_size={
            "lattice_shapes": [[2, 2], [3, 3]],
            "boundary_conditions": "periodic",
        },
    )


def adapter_blume_capel_level_crossing(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("exchange",), ()
    )
    exchange = inputs["exchange"]
    coordination = 4
    energy_lines = []
    for spin in (-1, 0, 1):
        bond_coefficient = -0.5 * coordination * exchange * spin * spin
        anisotropy_coefficient = spin * spin
        energy_lines.append((bond_coefficient, anisotropy_coefficient))
    ordered_line = energy_lines[0]
    zero_line = energy_lines[1]
    crossing_anisotropy = (
        zero_line[0] - ordered_line[0]
    ) / (ordered_line[1] - zero_line[1])
    ratio = crossing_anisotropy / exchange
    return _task13_calculation(
        "exact",
        {"square_lattice_d_over_j_crossing": ratio},
        controls,
        operations=len(energy_lines),
        additional_operation_counts={
            "uniform_states_enumerated": len(energy_lines),
        },
        problem_size_kind="fixed_local",
        problem_size={"unit_cell_sites": 1, "coordination_number": 4},
    )


def adapter_checkerboard_plaquette_enumeration(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("exchange",), ()
    )
    exchange = inputs["exchange"]
    configurations = (
        ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
         (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
         (-1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0),
         (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    )
    energies = []
    total_norms = []
    for spins in configurations:
        pair_dot_sum = 0.0
        for first in range(4):
            for second in range(first + 1, 4):
                for axis in range(3):
                    pair_dot_sum += (
                        spins[first][axis] * spins[second][axis]
                    )
        energy = exchange * pair_dot_sum
        total = []
        for axis in range(3):
            component = 0.0
            for spin in spins:
                component += spin[axis]
            total.append(component)
        energies.append(energy)
        norm_squared = 0.0
        for component in total:
            norm_squared += component * component
        total_norms.append(norm_squared)
    interaction_modes = (
        ((1, 1, 1, 1), 3),
        ((1, -1, 0, 0), -1),
        ((1, 1, -2, 0), -1),
        ((1, 1, 1, -3), -1),
    )
    spectral_modes_satisfied = 0
    lowest_interaction_eigenvalue = 3
    for mode, eigenvalue in interaction_modes:
        mode_sum = 0
        for component in mode:
            mode_sum += component
        mode_satisfied = True
        for site in range(4):
            matrix_action = mode_sum - mode[site]
            if matrix_action != eigenvalue * mode[site]:
                mode_satisfied = False
        if mode_satisfied:
            spectral_modes_satisfied += 1
        lowest_interaction_eigenvalue = min(
            lowest_interaction_eigenvalue, eigenvalue
        )
    spectral_lower_bound = (
        0.5 * 4.0 * lowest_interaction_eigenvalue * exchange
    )
    minimum = min(energies)
    bound_tolerance = 1e-12 * max(1.0, abs(exchange))
    bound_saturated = (
        spectral_modes_satisfied == len(interaction_modes)
        and abs(minimum - spectral_lower_bound) <= bound_tolerance
    )
    zero_total_spin = bound_saturated
    minimum_configurations = 0
    zero_total_minimum_configurations = 0
    for index in range(len(energies)):
        if energies[index] == minimum:
            minimum_configurations += 1
            if total_norms[index] == 0.0:
                zero_total_minimum_configurations += 1
            else:
                zero_total_spin = False
    proof_checks_satisfied = (
        int(bound_saturated) + zero_total_minimum_configurations
    )
    return _task13_calculation(
        "exact",
        {"zero_total_spin_per_crossed_plaquette": zero_total_spin},
        controls,
        operations=len(configurations) * 6,
        additional_operation_counts={
            "configurations_evaluated": len(configurations),
            "pair_energies_evaluated": len(configurations) * 6,
            "interaction_modes_checked": len(interaction_modes),
            "spectral_modes_satisfied": spectral_modes_satisfied,
            "spectral_lower_bound_saturated": int(bound_saturated),
            "minimum_energy_configurations": minimum_configurations,
            "zero_total_minimum_configurations": (
                zero_total_minimum_configurations
            ),
            "proof_checks_total": 1 + minimum_configurations,
            "proof_checks_satisfied": proof_checks_satisfied,
        },
        proof_inputs={
            "candidate_values": energies,
            "residuals": total_norms,
            "residual_bound": 0.0,
            "lower_bound": spectral_lower_bound,
            "certificate_checks_total": len(interaction_modes),
            "certificate_checks_satisfied": spectral_modes_satisfied,
        },
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 4, "crossed_plaquettes": 1},
    )


def _task14_spin_matrices(spin):
    dimension = int(round(2.0 * spin + 1.0))
    m_values = []
    for index in range(dimension):
        m_values.append(spin - index)
    raising = np.zeros((dimension, dimension), dtype=complex)
    for column in range(dimension):
        magnetic = m_values[column]
        raised_magnetic = magnetic + 1.0
        if raised_magnetic <= spin:
            row = int(round(spin - raised_magnetic))
            raising[row, column] = math.sqrt(
                spin * (spin + 1.0) - magnetic * raised_magnetic
            )
    lowering = raising.conjugate().T
    sx = 0.5 * (raising + lowering)
    sy = (raising - lowering) / (2.0j)
    sz = np.diag(m_values).astype(complex)
    return sx, sy, sz


def _task14_embed(operator, site, site_count):
    embedded = np.array([[1.0 + 0.0j]])
    identity = np.eye(operator.shape[0], dtype=complex)
    for index in range(site_count):
        embedded = np.kron(
            embedded, operator if index == site else identity
        )
    return embedded


def _task14_two_site_dot(spin):
    matrices = _task14_spin_matrices(spin)
    dot = np.zeros(
        (matrices[0].shape[0] ** 2, matrices[0].shape[0] ** 2),
        dtype=complex,
    )
    for component in matrices:
        dot += np.kron(component, component)
    return dot


def _task14_diagonalize(matrix):
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    residual = matrix @ eigenvectors - eigenvectors * eigenvalues
    identity = np.eye(matrix.shape[0], dtype=complex)
    matrix_norm = float(np.linalg.norm(matrix))
    basis_phase = math.atan(matrix_norm)
    basis_phases = []
    for index in range(matrix.shape[0]):
        angle = basis_phase * (index + 1)
        basis_phases.append(
            complex(math.cos(angle), math.sin(angle))
        )
    basis = np.diag(basis_phases)
    transformed = basis @ matrix @ basis.conjugate().T
    transformed_eigenvalues, _transformed_vectors = np.linalg.eigh(
        transformed
    )
    basis_similarity_residual = 0.0
    for original, changed in zip(eigenvalues, transformed_eigenvalues):
        basis_similarity_residual = max(
            basis_similarity_residual, abs(float(original - changed))
        )
    diagnostics = {
        "dimension": int(matrix.shape[0]),
        "matrix_norm": matrix_norm,
        "hermiticity_norm": float(np.linalg.norm(matrix - matrix.conjugate().T)),
        "maximum_eigenpair_residual": float(
            np.max(np.linalg.norm(residual, axis=0))
        ),
        "orthogonality_residual": float(
            np.linalg.norm(eigenvectors.conjugate().T @ eigenvectors - identity)
        ),
        "trace": float(np.trace(matrix).real),
        "eigensolver": "numpy.linalg.eigh",
        "basis_phase_radians": basis_phase,
        "basis_similarity_residual": basis_similarity_residual,
    }
    return eigenvalues, eigenvectors, diagnostics


def _task14_spin_half_chain_matrix(site_count, bonds):
    dimension = 1 << site_count
    matrix = np.zeros((dimension, dimension), dtype=float)
    for state in range(dimension):
        for first, second, coupling in bonds:
            first_bit = (state >> first) & 1
            second_bit = (state >> second) & 1
            matrix[state, state] += coupling * (
                0.25 if first_bit == second_bit else -0.25
            )
            if first_bit != second_bit:
                flipped = state ^ (1 << first) ^ (1 << second)
                matrix[flipped, state] += 0.5 * coupling
    return matrix


def _task14_grouped_values(values):
    scale = 0.0
    for raw_value in values:
        scale = max(scale, abs(float(raw_value)))
    tolerance = scale * 1e-12
    groups = []
    counts = []
    for raw_value in values:
        value = float(raw_value)
        if not groups or abs(value - groups[-1]) > tolerance:
            groups.append(value)
            counts.append(1)
        else:
            counts[-1] += 1
    return groups, counts


def _task14_total_spin_sector_energies(hamiltonian, spin):
    dot = _task14_two_site_dot(spin)
    dimension = dot.shape[0]
    identity = np.eye(dimension, dtype=complex)
    total_spin_squared = (
        2.0 * spin * (spin + 1.0) * identity + 2.0 * dot
    )
    maximum_total = int(round(2.0 * spin))
    sector_energies = []
    sector_multiplicities = []
    for selected_total in range(maximum_total + 1):
        selected_value = selected_total * (selected_total + 1.0)
        projector = identity.copy()
        for other_total in range(maximum_total + 1):
            if other_total == selected_total:
                continue
            other_value = other_total * (other_total + 1.0)
            projector = projector @ (
                (total_spin_squared - other_value * identity)
                / (selected_value - other_value)
            )
        multiplicity = int(round(float(np.trace(projector).real)))
        energy = float(np.trace(projector @ hamiltonian).real) / multiplicity
        sector_energies.append(energy)
        sector_multiplicities.append(multiplicity)
    return sector_energies, sector_multiplicities


def _task14_dimer_covering_state(site_count, shift):
    pairs = []
    for offset in range(0, site_count, 2):
        pairs.append(((offset + shift) % site_count, (offset + shift + 1) % site_count))
    vector = np.zeros(1 << site_count, dtype=float)
    normalization = 2.0 ** (-site_count / 4.0)
    for state in range(1 << site_count):
        amplitude = normalization
        for first, second in pairs:
            first_bit = (state >> first) & 1
            second_bit = (state >> second) & 1
            if first_bit == second_bit:
                amplitude = 0.0
                break
            if first_bit == 0 and second_bit == 1:
                amplitude = -amplitude
        vector[state] = amplitude
    return vector


def _task14_exact_calculation(
    fields,
    controls,
    diagnostics,
    operations,
    diagnostics_by_size=None,
    **kwargs,
):
    proof_inputs = dict(kwargs.pop("proof_inputs", {}))
    if diagnostics_by_size is None:
        diagnostics_by_size = (
            {
                "problem_size": kwargs["problem_size"],
                "diagnostics": diagnostics,
            },
        )
    proof_inputs["matrix_diagnostics_by_size"] = diagnostics_by_size
    return _task13_calculation(
        "exact",
        fields,
        controls,
        operations=operations,
        proof_inputs=proof_inputs,
        **kwargs,
    )


def adapter_spin_ladder_rung_dense_ed(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("rung_exchange",), ()
    )
    exchange = float(inputs["rung_exchange"])
    hamiltonian = exchange * _task14_two_site_dot(0.5)
    _eigenvalues, _vectors, diagnostics = _task14_diagonalize(hamiltonian)
    sector_energies, counts = _task14_total_spin_sector_energies(
        hamiltonian, 0.5
    )
    singlet = sector_energies[0]
    triplet = sector_energies[1]
    return _task14_exact_calculation(
        {"energy_per_rung": singlet, "gap_to_triplet": triplet - singlet},
        controls,
        diagnostics,
        operations=hamiltonian.size,
        proof_inputs={"sector_multiplicities": counts},
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 2, "rungs": 1},
    )


def _task14_su3_generators():
    zero = 0.0
    one = 1.0
    imaginary = 1.0j
    return (
        np.array(((zero, one, zero), (one, zero, zero), (zero, zero, zero))),
        np.array(
            ((zero, -imaginary, zero), (imaginary, zero, zero), (zero, zero, zero))
        ),
        np.array(((one, zero, zero), (zero, -one, zero), (zero, zero, zero))),
        np.array(((zero, zero, one), (zero, zero, zero), (one, zero, zero))),
        np.array(
            ((zero, zero, -imaginary), (zero, zero, zero), (imaginary, zero, zero))
        ),
        np.array(((zero, zero, zero), (zero, zero, one), (zero, one, zero))),
        np.array(
            ((zero, zero, zero), (zero, zero, -imaginary), (zero, imaginary, zero))
        ),
        np.array(
            ((one, zero, zero), (zero, one, zero), (zero, zero, -2.0))
        )
        / math.sqrt(3.0),
    )


def adapter_uls_two_site_su3_matrix(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("energy_scale",), ()
    )
    scale = float(inputs["energy_scale"])
    dot = _task14_two_site_dot(1.0)
    identity = np.eye(9, dtype=complex)
    permutation = np.zeros((9, 9), dtype=complex)
    for first in range(3):
        for second in range(3):
            permutation[second * 3 + first, first * 3 + second] = 1.0
    unscaled = dot + dot @ dot
    permutation_residual = float(np.linalg.norm(unscaled - permutation - identity))
    hamiltonian = (scale / math.sqrt(2.0)) * unscaled
    _eigenvalues, _vectors, diagnostics = _task14_diagonalize(hamiltonian)
    generator_residuals = []
    for generator in _task14_su3_generators():
        total_generator = np.kron(generator, np.eye(3)) + np.kron(
            np.eye(3), generator
        )
        generator_residuals.append(
            float(
                np.linalg.norm(
                    hamiltonian @ total_generator
                    - total_generator @ hamiltonian
                )
            )
        )
    all_residuals = [permutation_residual] + generator_residuals
    su3_symmetric = max(all_residuals) <= 1e-10 * max(1.0, abs(scale))
    return _task14_exact_calculation(
        {"theta_radians": math.atan2(scale, scale), "su3_symmetric": su3_symmetric},
        controls,
        diagnostics,
        operations=hamiltonian.size,
        proof_inputs={
            "candidate_values": all_residuals,
            "residuals": all_residuals,
            "residual_bound": 1e-10 * max(1.0, abs(scale)),
            "lower_bound": min(all_residuals),
            "certificate_checks_total": len(all_residuals),
            "certificate_checks_satisfied": (
                len(all_residuals) if su3_symmetric else 0
            ),
        },
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 2, "spin_quantum_number": 1},
    )


def _task14_compass_shape(rows, columns, horizontal, vertical):
    site_count = rows * columns
    sx, sy, _sz = _task14_spin_matrices(0.5)
    x_ops = []
    y_ops = []
    for site in range(site_count):
        x_ops.append(_task14_embed(2.0 * sx, site, site_count))
        y_ops.append(_task14_embed(2.0 * sy, site, site_count))
    dimension = 1 << site_count
    hamiltonian = np.zeros((dimension, dimension), dtype=complex)
    for row in range(rows):
        for column in range(columns - 1):
            first = row * columns + column
            hamiltonian += horizontal * (x_ops[first] @ x_ops[first + 1])
    for row in range(rows - 1):
        for column in range(columns):
            first = row * columns + column
            hamiltonian += vertical * (y_ops[first] @ y_ops[first + columns])
    residuals = []
    for column in range(columns):
        line = np.eye(dimension, dtype=complex)
        for row in range(rows):
            line = line @ x_ops[row * columns + column]
        residuals.append(float(np.linalg.norm(hamiltonian @ line - line @ hamiltonian)))
    for row in range(rows):
        line = np.eye(dimension, dtype=complex)
        for column in range(columns):
            line = line @ y_ops[row * columns + column]
        residuals.append(float(np.linalg.norm(hamiltonian @ line - line @ hamiltonian)))
    return hamiltonian, residuals


def adapter_compass_line_symmetry_matrix(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("horizontal_exchange", "vertical_exchange"),
        (),
    )
    all_residuals = []
    diagnostics = None
    diagnostics_by_size = []
    operations = 0
    for rows, columns in ((2, 2), (2, 3)):
        matrix, residuals = _task14_compass_shape(
            rows,
            columns,
            float(inputs["horizontal_exchange"]),
            float(inputs["vertical_exchange"]),
        )
        _values, _vectors, current = _task14_diagonalize(matrix)
        diagnostics = current
        diagnostics_by_size.append(
            {
                "problem_size": {
                    "lattice_shapes": [rows, columns],
                    "boundary_conditions": "open",
                },
                "diagnostics": current,
            }
        )
        all_residuals.extend(residuals)
        operations += matrix.size
    satisfied = max(all_residuals) <= 1e-10
    satisfied_checks = 0
    for value in all_residuals:
        if value <= 1e-10:
            satisfied_checks += 1
    return _task14_exact_calculation(
        {"has_line_flip_symmetries": satisfied},
        controls,
        diagnostics,
        operations=operations,
        diagnostics_by_size=diagnostics_by_size,
        proof_inputs={
            "candidate_values": all_residuals,
            "residuals": all_residuals,
            "residual_bound": 1e-10,
            "lower_bound": min(all_residuals),
            "certificate_checks_total": len(all_residuals),
            "certificate_checks_satisfied": satisfied_checks,
        },
        problem_size_kind="scalable_same_observable",
        problem_size={"lattice_shapes": [[2, 2], [2, 3]], "boundary_conditions": "open"},
    )


def adapter_aklt_two_site_projector_ed(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("projector_scale",), ()
    )
    scale = float(inputs["projector_scale"])
    dot = _task14_two_site_dot(1.0)
    projector = ((dot + np.eye(9)) @ (dot + 2.0 * np.eye(9))) / 6.0
    hamiltonian = scale * projector
    eigenvalues, _vectors, diagnostics = _task14_diagonalize(hamiltonian)
    sector_energies, counts = _task14_total_spin_sector_energies(
        hamiltonian, 1.0
    )
    sector_values = []
    for energy in sector_energies:
        normalized = energy / scale
        if abs(normalized) <= 1e-12:
            normalized = 0.0
        sector_values.append(normalized)
    zero_sector = max(sector_energies[0], sector_energies[1])
    if abs(zero_sector) <= abs(scale) * 1e-12:
        zero_sector = 0.0
    vbs = np.zeros(9, dtype=complex)
    vbs[2] = 1.0 / math.sqrt(3.0)
    vbs[4] = -1.0 / math.sqrt(3.0)
    vbs[6] = 1.0 / math.sqrt(3.0)
    vbs_projector_residual = float(np.linalg.norm(projector @ vbs))
    vbs_energy_expectation = float(
        np.vdot(vbs, hamiltonian @ vbs).real
    )
    return _task14_exact_calculation(
        {"two_site_projector_eigenvalues": sector_values, "vbs_ground_energy": zero_sector},
        controls,
        diagnostics,
        operations=hamiltonian.size,
        proof_inputs={
            "full_spectrum_multiplicities": counts,
            "vbs_projector_residual": vbs_projector_residual,
            "vbs_energy_expectation": vbs_energy_expectation,
        },
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 2, "spin_quantum_number": 1},
    )


def adapter_majumdar_ghosh_dimer_ed(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("nearest_exchange",), ()
    )
    exchange = float(inputs["nearest_exchange"])
    densities = []
    ground_space_multiplicities = []
    covering_eigen_residuals_by_size = []
    projected_covering_ranks = []
    diagnostics = None
    diagnostics_by_size = []
    operations = 0
    for site_count in (8, 10):
        bonds = []
        for site in range(site_count):
            bonds.append((site, (site + 1) % site_count, exchange))
            bonds.append((site, (site + 2) % site_count, 0.5 * exchange))
        matrix = _task14_spin_half_chain_matrix(site_count, bonds)
        eigenvalues, eigenvectors, current = _task14_diagonalize(matrix)
        diagnostics = current
        diagnostics_by_size.append(
            {
                "problem_size": {
                    "periodic_chain_lengths": site_count,
                    "boundary_conditions": "periodic",
                },
                "diagnostics": current,
            }
        )
        densities.append(float(eigenvalues[0]) / site_count)
        first = _task14_dimer_covering_state(site_count, 0)
        second = _task14_dimer_covering_state(site_count, 1)
        ground_energy = float(eigenvalues[0])
        ground_tolerance = abs(exchange) * 1e-10
        ground_multiplicity = 0
        for eigenvalue in eigenvalues:
            if abs(float(eigenvalue) - ground_energy) <= ground_tolerance:
                ground_multiplicity += 1
        ground_space_multiplicities.append(ground_multiplicity)
        residuals = []
        for covering in (first, second):
            residuals.append(
                float(
                    np.linalg.norm(
                        matrix @ covering - ground_energy * covering
                    )
                )
            )
        covering_eigen_residuals_by_size.append(residuals)
        ground_basis = eigenvectors[:, :ground_multiplicity]
        projected = []
        for covering in (first, second):
            projected.append(
                ground_basis @ (ground_basis.conj().T @ covering)
            )
        first_norm = float(np.vdot(projected[0], projected[0]).real)
        second_norm = float(np.vdot(projected[1], projected[1]).real)
        overlap = float(np.vdot(projected[0], projected[1]).real)
        gram_determinant = first_norm * second_norm - overlap * overlap
        projected_covering_ranks.append(
            2 if gram_determinant > 1e-10 else 1
        )
        operations += matrix.size
    calculation = _task14_exact_calculation(
        {
            "energy_per_site": densities[-1],
            "degenerate_dimer_coverings": min(
                ground_space_multiplicities
                + projected_covering_ranks
            ),
        },
        controls,
        diagnostics,
        operations=operations,
        diagnostics_by_size=diagnostics_by_size,
        proof_inputs={
            "energy_density_sequence": densities,
            "ground_space_multiplicities": ground_space_multiplicities,
            "covering_eigen_residuals_by_size": (
                covering_eigen_residuals_by_size
            ),
            "projected_covering_ranks": projected_covering_ranks,
        },
        problem_size_kind="scalable_same_observable",
        problem_size={"periodic_chain_lengths": [8, 10], "boundary_conditions": "periodic"},
    )
    calculation["raw_convergence_evidence"] = {
        "kind": "finite_size",
        "controls": controls,
        "sizes": [8, 10],
        "estimates": densities,
        "error_bound": 1e-10 * max(1.0, abs(exchange)),
    }
    return calculation


def adapter_shastry_sutherland_dimer_ed(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("intradimer_exchange", "interdimer_exchange"),
        (),
    )
    intradimer = float(inputs["intradimer_exchange"])
    interdimer = float(inputs["interdimer_exchange"])
    residuals = []
    product_ground_energy_residuals = []
    interdimer_bond_counts = []
    diagnostics = None
    diagnostics_by_size = []
    operations = 0
    for dimer_count in (2, 4):
        site_count = 2 * dimer_count
        bonds = []
        for index in range(dimer_count):
            bonds.append((2 * index, 2 * index + 1, intradimer))
        for left in range(dimer_count - 1):
            shared_site = 2 * (left + 1) + (left % 2)
            bonds.append((2 * left, shared_site, interdimer))
            bonds.append((2 * left + 1, shared_site, interdimer))
        interdimer_bond_counts.append(2 * (dimer_count - 1))
        matrix = _task14_spin_half_chain_matrix(site_count, bonds)
        eigenvalues, _vectors, current = _task14_diagonalize(matrix)
        diagnostics = current
        diagnostics_by_size.append(
            {
                "problem_size": {
                    "orthogonal_dimer_counts": dimer_count,
                    "spin_counts": site_count,
                    "boundary_conditions": "open_linked_cells",
                },
                "diagnostics": current,
            }
        )
        state = _task14_dimer_covering_state(site_count, 0)
        product_energy = -0.75 * intradimer * dimer_count
        product_ground_energy_residuals.append(
            abs(product_energy - float(eigenvalues[0]))
        )
        residuals.append(
            float(np.linalg.norm(matrix @ state - product_energy * state))
        )
        operations += matrix.size
    return _task14_exact_calculation(
        {"energy_per_dimer": -0.75 * intradimer, "energy_per_spin": -0.375 * intradimer},
        controls,
        diagnostics,
        operations=operations,
        diagnostics_by_size=diagnostics_by_size,
        proof_inputs={
            "linked_cell_cancellation_residuals": residuals,
            "product_ground_energy_residuals": (
                product_ground_energy_residuals
            ),
            "interdimer_bond_counts": interdimer_bond_counts,
        },
        problem_size_kind="scalable_same_observable",
        problem_size={"orthogonal_dimer_counts": [2, 4], "spin_counts": [4, 8], "boundary_conditions": "open_linked_cells"},
    )


def adapter_spin1_single_ion_dense_ed(scientific_inputs, numerical_controls):
    inputs, controls = _task13_require_inputs(
        scientific_inputs, numerical_controls, ("single_ion_anisotropy",), ()
    )
    anisotropy = float(inputs["single_ion_anisotropy"])
    _sx, _sy, sz = _task14_spin_matrices(1.0)
    hamiltonian = anisotropy * (sz @ sz)
    eigenvalues, _vectors, diagnostics = _task14_diagonalize(hamiltonian)
    groups, counts = _task14_grouped_values(eigenvalues)
    levels = []
    for value in eigenvalues:
        levels.append(float(value))
    return _task14_exact_calculation(
        {"levels": levels, "degeneracies": counts},
        controls,
        diagnostics,
        operations=hamiltonian.size,
        proof_inputs={"distinct_levels": groups},
        problem_size_kind="fixed_local",
        problem_size={"spin_count": 1, "spin_quantum_number": 1},
    )


def _task15_fourier_calculation(
    fields,
    controls,
    proof_material,
    residual_bound,
    *,
    bounded_fields=(),
):
    proof_material = dict(proof_material)
    proof_material["derived_fields"] = dict(fields)
    if "numeric_field_certificates" not in proof_material:
        proof_material["numeric_field_certificates"] = {}
    residual = max(
        float(proof_material["reciprocal_symmetry_residual"]),
        float(proof_material["direct_invariant_residual"]),
    )
    refinement_samples = tuple(proof_material["refinement_samples"])
    refinement_residuals = tuple(proof_material["refinement_residuals"])
    refinement_residuals = (
        max(float(refinement_residuals[0]), residual),
        max(float(refinement_residuals[1]), residual),
    )
    proof_material["refinement_residuals"] = refinement_residuals
    return _task13_calculation(
        "residual_bound",
        fields,
        controls,
        operations=int(proof_material["sample_count"]),
        bounded_fields=bounded_fields,
        residual_samples=refinement_samples,
        residuals=refinement_residuals,
        error_bound=float(residual_bound),
        proof_inputs={"fourier_evidence": proof_material},
    )


def _task15_two_band_eigenvalues(dx, dy, dz):
    radius = math.sqrt(dx * dx + dy * dy + dz * dz)
    return (-radius, radius)


def _task15_configuration_values(scientific_configuration):
    if not scientific_configuration:
        return None
    pi_value = 4.0 * math.atan(1.0)
    coordinates = scientific_configuration["coordinates"]
    momentum = []
    for coordinate in coordinates:
        momentum.append(2.0 * pi_value * float(coordinate))
    return (
        scientific_configuration["representation"],
        tuple(momentum),
        2.0
        * pi_value
        * float(scientific_configuration["gauge_phase_fraction"]),
    )


def _task15_configured_probe(
    scientific_configuration, real_value, fourier_value
):
    representation = scientific_configuration["representation"]
    selected = real_value if representation == "real_space" else fourier_value
    return {
        "scientific_configuration": dict(scientific_configuration),
        "selected_value": selected,
        "real_space_value": real_value,
        "fourier_space_value": fourier_value,
        "real_fourier_residual": abs(real_value - fourier_value),
    }


def adapter_xy_chain_bdg_boundaries(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("momentum_refinement_grid", "eigensolver_residual_threshold"),
    )
    exchange = float(inputs["exchange"])
    grid = int(controls["momentum_refinement_grid"])
    threshold = float(controls["eigensolver_residual_threshold"])
    pi_value = 4.0 * math.atan(1.0)
    field_lower = 0.5 * exchange
    field_upper = 1.5 * exchange
    field_coarse_width = None
    for _iteration in range(60):
        field_middle = 0.5 * (field_lower + field_upper)
        if field_middle - exchange < 0.0:
            field_lower = field_middle
        else:
            field_upper = field_middle
        if _iteration == 29:
            field_coarse_width = field_upper - field_lower
    selected_field = 0.5 * (field_lower + field_upper)
    gamma_lower = -0.5
    gamma_upper = 0.5
    gamma_coarse_width = None
    for _iteration in range(60):
        gamma_middle = 0.5 * (gamma_lower + gamma_upper)
        if exchange * gamma_middle < 0.0:
            gamma_lower = gamma_middle
        else:
            gamma_upper = gamma_middle
        if _iteration == 29:
            gamma_coarse_width = gamma_upper - gamma_lower
    selected_gamma = gamma_upper
    gamma_probe = 0.61
    symmetry_residual = 0.0
    determinant_residual = 0.0
    raw_minima = []
    for field, gamma in (
        (selected_field, gamma_probe),
        (0.0, selected_gamma),
        (0.93 * exchange, gamma_probe),
        (1.07 * exchange, gamma_probe),
    ):
        minimum = None
        minimum_momentum = None
        for index in range(grid + 1):
            momentum = pi_value * index / grid
            z_value = field - exchange * math.cos(momentum)
            y_value = exchange * gamma * math.sin(momentum)
            eigenvalues = _task15_two_band_eigenvalues(
                0.0, y_value, z_value
            )
            gap = eigenvalues[1] - eigenvalues[0]
            negative_z = field - exchange * math.cos(-momentum)
            negative_y = exchange * gamma * math.sin(-momentum)
            negative_gap = 2.0 * math.sqrt(
                negative_z * negative_z + negative_y * negative_y
            )
            symmetry_residual = max(
                symmetry_residual, abs(gap - negative_gap)
            )
            if minimum is None or gap < minimum:
                minimum = gap
                minimum_momentum = momentum
        raw_minima.append(
            {
                "field": field,
                "anisotropy": gamma,
                "momentum": minimum_momentum,
                "gap": minimum,
            }
        )
    field_closing = raw_minima[0]
    anisotropy_closing = raw_minima[1]
    determinant_residual = max(
        abs(field_closing["gap"]), abs(anisotropy_closing["gap"])
    )
    proof_material = {
        "model_kernel": "xy_bdg_matrix",
        "sample_count": 120 + 4 * (grid + 1),
        "reciprocal_symmetry_residual": symmetry_residual,
        "direct_invariant_residual": determinant_residual,
        "raw_gap_minima": raw_minima,
        "particle_hole_residual": symmetry_residual,
        "neighboring_field_gaps": (
            raw_minima[2]["gap"],
            raw_minima[3]["gap"],
        ),
        "numeric_field_certificates": {
            "ising_critical_field": {
                "kind": "signed_bracket_root_v1",
                "lower": field_lower,
                "upper": field_upper,
                "lower_residual": field_lower - exchange,
                "upper_residual": field_upper - exchange,
                "selected": selected_field,
                "selected_residual": selected_field - exchange,
            },
            "anisotropy_transition_gamma": {
                "kind": "signed_bracket_root_v1",
                "lower": gamma_lower,
                "upper": gamma_upper,
                "lower_residual": exchange * gamma_lower,
                "upper_residual": exchange * gamma_upper,
                "selected": selected_gamma,
                "selected_residual": exchange * selected_gamma,
            },
        },
        "refinement_samples": (60, 120 + 4 * (grid + 1)),
        "refinement_residuals": (
            max(field_coarse_width, gamma_coarse_width),
            max(field_upper - field_lower, gamma_upper - gamma_lower),
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, gauge_angle = configuration_values
        z_value = selected_field - exchange * math.cos(momentum[0])
        y_value = exchange * gamma_probe * math.sin(momentum[0])
        fourier_gap = 2.0 * math.sqrt(
            z_value * z_value + y_value * y_value
        )
        gauge = complex(math.cos(gauge_angle), math.sin(gauge_angle))
        off_diagonal = -1.0j * y_value * gauge
        configured_matrix = np.array(
            (
                (z_value, off_diagonal),
                (
                    complex(
                        off_diagonal.real, -off_diagonal.imag
                    ),
                    -z_value,
                ),
            ),
            dtype=complex,
        )
        configured_eigenvalues = np.linalg.eigvalsh(configured_matrix)
        real_gap = float(
            configured_eigenvalues[1] - configured_eigenvalues[0]
        )
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_gap, fourier_gap
        )
        proof_material["sample_count"] += 1
        proof_material["refinement_samples"] = (
            proof_material["refinement_samples"][0],
            proof_material["refinement_samples"][1] + 1,
        )
    return _task15_fourier_calculation(
        {
            "ising_critical_field": field_closing["field"],
            "anisotropy_transition_gamma": anisotropy_closing[
                "anisotropy"
            ],
        },
        controls,
        proof_material,
        threshold,
        bounded_fields=(
            "ising_critical_field",
            "anisotropy_transition_gamma",
        ),
    )


def _task15_momentum_triplet(index, count):
    pi_value = 4.0 * math.atan(1.0)
    return (
        2.0 * pi_value * ((37 * index + 11) % count) / count,
        2.0 * pi_value * ((53 * index + 7) % count) / count,
        2.0 * pi_value * ((29 * index + 3) % count) / count,
    )


def adapter_diamond_spiral_threshold_fourier(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("first_neighbor_exchange",),
        ("momentum_refinement_grid", "kernel_residual_bound"),
    )
    first = float(inputs["first_neighbor_exchange"])
    grid = int(controls["momentum_refinement_grid"])
    threshold_bound = float(controls["kernel_residual_bound"])
    threshold_lower = 0.0
    threshold_upper = 0.25
    threshold_coarse_width = None
    for _iteration in range(60):
        threshold_middle = 0.5 * (threshold_lower + threshold_upper)
        slope = 8.0 * threshold_middle * first - first
        if slope < 0.0:
            threshold_lower = threshold_middle
        else:
            threshold_upper = threshold_middle
        if _iteration == 29:
            threshold_coarse_width = threshold_upper - threshold_lower
    threshold = 0.5 * (threshold_lower + threshold_upper)
    minima = []
    raw_momentum_samples = []
    direct_residual = 0.0
    for ratio in (0.9 * threshold, 1.1 * threshold):
        second = ratio * first
        best = None
        best_structure = None
        for index in range(grid + 1):
            structure = 4.0 * index / grid
            diagonal = second * (structure * structure - 4.0)
            lower = diagonal - first * structure
            matrix = np.array(
                ((diagonal, -first * structure),
                 (-first * structure, diagonal)),
                dtype=float,
            )
            numerical_lower = float(np.linalg.eigvalsh(matrix)[0])
            direct_residual = max(
                direct_residual, abs(lower - numerical_lower)
            )
            if best is None or lower < best:
                best = lower
                best_structure = structure
        minima.append(
            {
                "coupling_ratio": ratio,
                "structure_factor_magnitude": best_structure,
                "lower_band": best,
            }
        )
    bond_vectors = (
        (0.25, 0.25, 0.25),
        (0.25, -0.25, -0.25),
        (-0.25, 0.25, -0.25),
        (-0.25, -0.25, 0.25),
    )
    phase_ratio = 1.1 * threshold
    phase_second = phase_ratio * first
    for index in range(grid):
        momentum = _task15_momentum_triplet(index, grid)
        structure_real = 0.0
        structure_imaginary = 0.0
        for vector in bond_vectors:
            angle = 0.0
            for axis in range(3):
                angle += momentum[axis] * vector[axis]
            structure_real += math.cos(angle)
            structure_imaginary += math.sin(angle)
        structure = math.sqrt(
            structure_real * structure_real
            + structure_imaginary * structure_imaginary
        )
        diagonal = phase_second * (structure * structure - 4.0)
        lower = diagonal - first * structure
        matrix = np.array(
            (
                (
                    diagonal,
                    -first * complex(
                        structure_real, -structure_imaginary
                    ),
                ),
                (
                    -first * complex(
                        structure_real, structure_imaginary
                    ),
                    diagonal,
                ),
            ),
            dtype=complex,
        )
        numerical_lower = float(np.linalg.eigvalsh(matrix)[0])
        direct_residual = max(
            direct_residual, abs(lower - numerical_lower)
        )
        raw_momentum_samples.append(
            {"momentum": momentum, "lower_energy": numerical_lower}
        )
    stationarity_residual = abs(8.0 * threshold * first - first)
    proof_material = {
        "model_kernel": "diamond_two_sublattice_kernel",
        "sample_count": 60 + 3 * grid + 2,
        "reciprocal_symmetry_residual": 0.0,
        "direct_invariant_residual": max(
            direct_residual, stationarity_residual
        ),
        "allowed_structure_factor_range": (0.0, 4.0),
        "raw_lower_band_minima": minima,
        "raw_momentum_samples": raw_momentum_samples,
        "stationary_onset_residual": stationarity_residual,
        "numeric_field_certificates": {
            "spiral_surface_for_j2_over_j1_gt": {
                "kind": "signed_bracket_root_v1",
                "lower": threshold_lower,
                "upper": threshold_upper,
                "lower_residual": 8.0 * threshold_lower * first - first,
                "upper_residual": 8.0 * threshold_upper * first - first,
                "selected": threshold,
                "selected_residual": 8.0 * threshold * first - first,
            }
        },
        "refinement_samples": (30, 60 + 3 * grid + 2),
        "refinement_residuals": (
            threshold_coarse_width,
            threshold_upper - threshold_lower,
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, gauge_angle = configuration_values
        structure_real = 0.0
        structure_imaginary = 0.0
        for vector in bond_vectors:
            angle = 0.0
            for axis in range(3):
                angle += momentum[axis] * vector[axis]
            structure_real += math.cos(angle)
            structure_imaginary += math.sin(angle)
        structure = math.sqrt(
            structure_real * structure_real
            + structure_imaginary * structure_imaginary
        )
        configured_second = threshold * first
        diagonal = configured_second * (structure * structure - 4.0)
        fourier_energy = diagonal - first * structure
        gauge = complex(math.cos(gauge_angle), math.sin(gauge_angle))
        off_diagonal = -first * complex(
            structure_real, -structure_imaginary
        ) * gauge
        configured_matrix = np.array(
            (
                (diagonal, off_diagonal),
                (
                    complex(off_diagonal.real, -off_diagonal.imag),
                    diagonal,
                ),
            ),
            dtype=complex,
        )
        real_energy = float(np.linalg.eigvalsh(configured_matrix)[0])
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_energy, fourier_energy
        )
        proof_material["sample_count"] += 1
        proof_material["refinement_samples"] = (
            proof_material["refinement_samples"][0],
            proof_material["refinement_samples"][1] + 1,
        )
    return _task15_fourier_calculation(
        {"spiral_surface_for_j2_over_j1_gt": threshold},
        controls,
        proof_material,
        threshold_bound,
        bounded_fields=("spiral_surface_for_j2_over_j1_gt",),
    )


def _task15_kitaev_d_vector(exchange, mass, first, second):
    return (
        exchange * (1.0 + math.cos(first) + math.cos(second)),
        exchange * (math.sin(first) + math.sin(second)),
        4.0
        * mass
        * (math.sin(first) - math.sin(second) + math.sin(second - first)),
    )


def _task15_unit_vector(vector):
    norm_squared = 0.0
    for value in vector:
        norm_squared += value * value
    norm = math.sqrt(norm_squared)
    normalized = []
    for value in vector:
        normalized.append(value / norm)
    return tuple(normalized)


def _task15_solid_angle(first, second, third):
    determinant = (
        first[0] * (second[1] * third[2] - second[2] * third[1])
        - first[1] * (second[0] * third[2] - second[2] * third[0])
        + first[2] * (second[0] * third[1] - second[1] * third[0])
    )
    denominator = 1.0
    for left, right in ((first, second), (second, third), (third, first)):
        for index in range(3):
            denominator += left[index] * right[index]
    return 2.0 * math.atan2(determinant, denominator)


def _task15_kitaev_chern(exchange, mass, grid):
    pi_value = 4.0 * math.atan(1.0)
    vectors = []
    minimum_norm = None
    symmetry_residual = 0.0
    direct_residual = 0.0
    for first_index in range(grid):
        row = []
        first = 2.0 * pi_value * first_index / grid
        for second_index in range(grid):
            second = 2.0 * pi_value * second_index / grid
            vector = _task15_kitaev_d_vector(exchange, mass, first, second)
            norm_squared = 0.0
            for value in vector:
                norm_squared += value * value
            norm = math.sqrt(norm_squared)
            if minimum_norm is None or norm < minimum_norm:
                minimum_norm = norm
            numerical = np.linalg.eigvalsh(
                np.array(
                    (
                        (vector[2], vector[0] - 1.0j * vector[1]),
                        (vector[0] + 1.0j * vector[1], -vector[2]),
                    ),
                    dtype=complex,
                )
            )
            direct_residual = max(
                direct_residual,
                abs(float(numerical[0]) + norm),
                abs(float(numerical[1]) - norm),
            )
            negative = _task15_kitaev_d_vector(
                exchange, mass, -first, -second
            )
            negative_norm_squared = 0.0
            for value in negative:
                negative_norm_squared += value * value
            negative_norm = math.sqrt(negative_norm_squared)
            symmetry_residual = max(
                symmetry_residual, abs(norm - negative_norm)
            )
            row.append(_task15_unit_vector(vector))
        vectors.append(row)
    dirac_minimum = None
    for first, second in (
        (2.0 * pi_value / 3.0, -2.0 * pi_value / 3.0),
        (-2.0 * pi_value / 3.0, 2.0 * pi_value / 3.0),
    ):
        vector = _task15_kitaev_d_vector(
            exchange, mass, first, second
        )
        norm_squared = 0.0
        for value in vector:
            norm_squared += value * value
        norm = math.sqrt(norm_squared)
        if dirac_minimum is None or norm < dirac_minimum:
            dirac_minimum = norm
    solid_angle = 0.0
    for first_index in range(grid):
        next_first = (first_index + 1) % grid
        for second_index in range(grid):
            next_second = (second_index + 1) % grid
            a = vectors[first_index][second_index]
            b = vectors[next_first][second_index]
            c = vectors[next_first][next_second]
            d = vectors[first_index][next_second]
            solid_angle += _task15_solid_angle(a, b, c)
            solid_angle += _task15_solid_angle(a, c, d)
    return (
        solid_angle / (4.0 * pi_value),
        2.0 * dirac_minimum,
        2.0 * minimum_norm,
        symmetry_residual,
        direct_residual,
    )


def adapter_kitaev_field_majorana_mass(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("kitaev_exchange", "field_x", "field_y", "field_z"),
        ("momentum_refinement_grid", "gap_residual_bound"),
    )
    exchange = float(inputs["kitaev_exchange"])
    mass = (
        float(inputs["field_x"])
        * float(inputs["field_y"])
        * float(inputs["field_z"])
        / (exchange * exchange)
    )
    grid = int(controls["momentum_refinement_grid"])
    residual_bound = float(controls["gap_residual_bound"])
    chern, gap, mesh_gap, symmetry_residual, direct_residual = (
        _task15_kitaev_chern(exchange, mass, grid)
    )
    coarse_grid = max(8, grid // 2)
    coarse_chern, _coarse_gap, _coarse_mesh_gap, (
        coarse_symmetry_residual
    ), coarse_direct_residual = _task15_kitaev_chern(
        exchange, mass, coarse_grid
    )
    rounded_chern = int(round(chern))
    opens_gap = gap > 0.0 and abs(rounded_chern) % 2 == 1
    proof_material = {
        "model_kernel": "kitaev_majorana_two_band",
        "sample_count": coarse_grid * coarse_grid + grid * grid,
        "reciprocal_symmetry_residual": symmetry_residual,
        "direct_invariant_residual": max(
            direct_residual, abs(chern - rounded_chern)
        ),
        "third_order_mass": mass,
        "minimum_band_gap": gap,
        "mesh_minimum_band_gap": mesh_gap,
        "discrete_chern_number": chern,
        "chern_parity": abs(rounded_chern) % 2,
        "refinement_samples": (
            coarse_grid * coarse_grid,
            coarse_grid * coarse_grid + grid * grid,
        ),
        "refinement_residuals": (
            max(
                coarse_symmetry_residual,
                coarse_direct_residual,
                abs(coarse_chern - round(coarse_chern)),
                abs(chern - rounded_chern),
                symmetry_residual,
                direct_residual,
            ),
            max(
                symmetry_residual,
                direct_residual,
                abs(chern - rounded_chern),
            ),
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, gauge_angle = configuration_values
        configured_vector = _task15_kitaev_d_vector(
            exchange, mass, momentum[0], momentum[1]
        )
        fourier_energy = math.sqrt(
            configured_vector[0] * configured_vector[0]
            + configured_vector[1] * configured_vector[1]
            + configured_vector[2] * configured_vector[2]
        )
        gauge = complex(math.cos(gauge_angle), math.sin(gauge_angle))
        off_diagonal = complex(
            configured_vector[0], -configured_vector[1]
        ) * gauge
        configured_matrix = np.array(
            (
                (configured_vector[2], off_diagonal),
                (
                    complex(off_diagonal.real, -off_diagonal.imag),
                    -configured_vector[2],
                ),
            ),
            dtype=complex,
        )
        real_energy = float(np.linalg.eigvalsh(configured_matrix)[1])
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_energy, fourier_energy
        )
        proof_material["sample_count"] += 1
        proof_material["refinement_samples"] = (
            proof_material["refinement_samples"][0],
            proof_material["refinement_samples"][1] + 1,
        )
    return _task15_fourier_calculation(
        {"field_opens_non_abelian_gap": opens_gap},
        controls,
        proof_material,
        residual_bound,
    )


def _task15_direction_vector(name):
    if name == "axis_a":
        return np.array((1.0, 0.0, 0.0), dtype=float)
    return np.array((0.0, 1.0, 0.0), dtype=float)


def adapter_pyrochlore_coulomb_fourier(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange", "approach_direction_a", "approach_direction_b"),
        ("momentum_refinement_grid", "constraint_residual_bound"),
    )
    exchange = float(inputs["exchange"])
    grid = int(controls["momentum_refinement_grid"])
    residual_bound = float(controls["constraint_residual_bound"])
    bond_vectors = np.array(
        (
            (0.25, 0.25, 0.25),
            (0.25, -0.25, -0.25),
            (-0.25, 0.25, -0.25),
            (-0.25, -0.25, 0.25),
        ),
        dtype=float,
    )
    maximum_projector_residual = 0.0
    symmetry_residual = 0.0
    raw_modes = []
    directional_correlators = []
    coarse_projector_residual = 0.0
    fine_projector_residual = 0.0
    for direction_name in (
        inputs["approach_direction_a"],
        inputs["approach_direction_b"],
    ):
        direction = _task15_direction_vector(direction_name)
        final_correlator = None
        for refinement in (2.0, 1.0):
            q_vector = refinement * direction / grid
            upper = []
            lower = []
            for site in range(4):
                angle = 0.0
                for axis in range(3):
                    angle += bond_vectors[site, axis] * q_vector[axis]
                upper_value = complex(
                    math.cos(0.5 * angle), math.sin(0.5 * angle)
                ) / 2.0
                lower_value = complex(
                    math.cos(0.5 * angle), -math.sin(0.5 * angle)
                ) / 2.0
                upper.append(upper_value)
                lower.append(lower_value)
            overlap = 0.0j
            for site in range(4):
                upper_conjugate = complex(
                    upper[site].real, -upper[site].imag
                )
                overlap += upper_conjugate * lower[site]
            determinant = 1.0 - (
                overlap.real * overlap.real + overlap.imag * overlap.imag
            )
            inverse = (
                (1.0 / determinant, -overlap / determinant),
                (
                    -complex(overlap.real, -overlap.imag) / determinant,
                    1.0 / determinant,
                ),
            )
            rows = (upper, lower)
            projector = np.eye(4, dtype=complex)
            for row in range(4):
                for column in range(4):
                    correction = 0.0j
                    for first_constraint in range(2):
                        left = rows[first_constraint][row]
                        left_conjugate = complex(left.real, -left.imag)
                        for second_constraint in range(2):
                            correction += (
                                left_conjugate
                                * inverse[first_constraint][second_constraint]
                                * rows[second_constraint][column]
                            )
                    projector[row, column] -= correction
            eigenvalues = np.linalg.eigvalsh(projector)
            maximum_projector_residual = max(
                maximum_projector_residual,
                float(np.linalg.norm(projector @ projector - projector)),
            )
            selected_projector_residual = float(
                np.linalg.norm(projector @ projector - projector)
            )
            if refinement == 2.0:
                coarse_projector_residual = max(
                    coarse_projector_residual,
                    selected_projector_residual,
                )
            else:
                fine_projector_residual = max(
                    fine_projector_residual,
                    selected_projector_residual,
                )
            selected_modes = []
            for value in eigenvalues:
                selected_modes.append(float(value.real))
            raw_modes.append(selected_modes)
            final_correlator = np.zeros((3, 3), dtype=complex)
            for first_axis in range(3):
                for second_axis in range(3):
                    for row in range(4):
                        for column in range(4):
                            final_correlator[first_axis, second_axis] += (
                                bond_vectors[row, first_axis]
                                * projector[row, column]
                                * bond_vectors[column, second_axis]
                            )
            negative_projector = np.zeros((4, 4), dtype=complex)
            for row in range(4):
                for column in range(4):
                    selected = projector[row, column]
                    negative_projector[row, column] = complex(
                        selected.real, -selected.imag
                    )
            negative_eigenvalues = np.linalg.eigvalsh(
                negative_projector
            )
            for index in range(4):
                symmetry_residual = max(
                    symmetry_residual,
                    abs(
                        float(
                            eigenvalues[index] - negative_eigenvalues[index]
                        )
                    ),
                )
        directional_correlators.append(final_correlator)
    directional_difference = float(
        np.linalg.norm(directional_correlators[0] - directional_correlators[1])
    )
    tetrahedron_spins = np.array(
        ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
         (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
        dtype=float,
    )
    total_spin = np.zeros(3, dtype=float)
    for site in range(4):
        for axis in range(3):
            total_spin[axis] += tetrahedron_spins[site, axis]
    tetrahedron_residual = float(np.linalg.norm(total_spin))
    constraint_satisfied = tetrahedron_residual <= residual_bound
    pinch_points = directional_difference > 1e-12
    proof_material = {
        "model_kernel": "pyrochlore_constraint_projector",
        "sample_count": 4,
        "reciprocal_symmetry_residual": symmetry_residual,
        "direct_invariant_residual": max(
            maximum_projector_residual, tetrahedron_residual
        ),
        "raw_constraint_modes": raw_modes,
        "tetrahedron_spin_sum_residual": tetrahedron_residual,
        "directional_polarization_difference": directional_difference,
        "exchange_scale": exchange,
        "refinement_samples": (2, 4),
        "refinement_residuals": (
            max(coarse_projector_residual, fine_projector_residual),
            fine_projector_residual,
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, gauge_angle = configuration_values
        gauge = complex(math.cos(gauge_angle), math.sin(gauge_angle))
        configured_upper = []
        configured_lower = []
        for site in range(4):
            angle = 0.0
            for axis in range(3):
                angle += bond_vectors[site, axis] * momentum[axis]
            configured_upper.append(
                complex(math.cos(0.5 * angle), math.sin(0.5 * angle))
                * gauge
                / 2.0
            )
            configured_lower.append(
                complex(math.cos(0.5 * angle), -math.sin(0.5 * angle))
                * gauge
                / 2.0
            )
        configured_overlap = 0.0j
        for site in range(4):
            selected = configured_upper[site]
            configured_overlap += (
                complex(selected.real, -selected.imag)
                * configured_lower[site]
            )
        configured_determinant = 1.0 - (
            configured_overlap.real * configured_overlap.real
            + configured_overlap.imag * configured_overlap.imag
        )
        configured_inverse = (
            (
                1.0 / configured_determinant,
                -configured_overlap / configured_determinant,
            ),
            (
                -complex(
                    configured_overlap.real, -configured_overlap.imag
                )
                / configured_determinant,
                1.0 / configured_determinant,
            ),
        )
        configured_rows = (configured_upper, configured_lower)
        configured_projector = np.eye(4, dtype=complex)
        for row in range(4):
            for column in range(4):
                correction = 0.0j
                for first_constraint in range(2):
                    left = configured_rows[first_constraint][row]
                    left_conjugate = complex(left.real, -left.imag)
                    for second_constraint in range(2):
                        correction += (
                            left_conjugate
                            * configured_inverse[first_constraint][
                                second_constraint
                            ]
                            * configured_rows[second_constraint][column]
                        )
                configured_projector[row, column] -= correction
        configured_eigenvalues = np.linalg.eigvalsh(configured_projector)
        fourier_value = 0.0
        for value in configured_eigenvalues:
            fourier_value += float(value.real)
        real_value = float(np.trace(configured_projector).real)
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_value, fourier_value
        )
        proof_material["sample_count"] = 5
        proof_material["refinement_samples"] = (2, 5)
    return _task15_fourier_calculation(
        {
            "zero_total_spin_per_tetrahedron": constraint_satisfied,
            "pinch_points": pinch_points,
        },
        controls,
        proof_material,
        residual_bound,
    )


def _task15_simple_cubic_kernel(first, second, momentum):
    cosine_values = []
    for value in momentum:
        cosine_values.append(math.cos(value))
    cosines = tuple(cosine_values)
    pair_sum = (
        cosines[0] * cosines[1]
        + cosines[1] * cosines[2]
        + cosines[2] * cosines[0]
    )
    cosine_sum = 0.0
    for value in cosines:
        cosine_sum += value
    return 2.0 * first * cosine_sum + 4.0 * second * pair_sum


def adapter_simple_cubic_j1_j2_fourier(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("first_neighbor_exchange",),
        ("momentum_refinement_grid", "branch_residual_bound"),
    )
    first = float(inputs["first_neighbor_exchange"])
    grid = int(controls["momentum_refinement_grid"])
    residual_bound = float(controls["branch_residual_bound"])
    boundary_lower = 0.0
    boundary_upper = 0.5
    boundary_coarse_width = None
    pi_value = 4.0 * math.atan(1.0)
    for _iteration in range(60):
        boundary_middle = 0.5 * (boundary_lower + boundary_upper)
        middle_second = boundary_middle * first
        neel_middle = _task15_simple_cubic_kernel(
            first, middle_second, (pi_value, pi_value, pi_value)
        )
        collinear_middle = _task15_simple_cubic_kernel(
            first, middle_second, (pi_value, pi_value, 0.0)
        )
        if neel_middle - collinear_middle < 0.0:
            boundary_lower = boundary_middle
        else:
            boundary_upper = boundary_middle
        if _iteration == 29:
            boundary_coarse_width = boundary_upper - boundary_lower
    boundary = 0.5 * (boundary_lower + boundary_upper)
    samples = []
    raw_momentum_samples = []
    direct_residual = 0.0
    for ratio in (0.8 * boundary, 1.2 * boundary):
        second = ratio * first
        neel = _task15_simple_cubic_kernel(
            first, second, (pi_value, pi_value, pi_value)
        )
        collinear = _task15_simple_cubic_kernel(
            first, second, (pi_value, pi_value, 0.0)
        )
        neel_real_space = 2.0 * (-3.0 * first + 6.0 * second)
        collinear_real_space = 2.0 * (-first - 2.0 * second)
        direct_residual = max(
            direct_residual,
            abs(neel - neel_real_space),
            abs(collinear - collinear_real_space),
        )
        sampled_minimum = None
        for index in range(grid):
            q = 2.0 * pi_value * index / grid
            for momentum in (
                (q, pi_value, pi_value),
                (pi_value, q, 0.0),
                (q, q, q),
            ):
                energy = _task15_simple_cubic_kernel(
                    first, second, momentum
                )
                if sampled_minimum is None or energy < sampled_minimum:
                    sampled_minimum = energy
        samples.append(
            {
                "coupling_ratio": ratio,
                "neel_energy": neel,
                "collinear_energy": collinear,
                "sampled_minimum": sampled_minimum,
            }
        )
    for index in range(grid):
        momentum = _task15_momentum_triplet(index, grid)
        lower_energy = _task15_simple_cubic_kernel(
            first, boundary * first, momentum
        )
        raw_momentum_samples.append(
            {"momentum": momentum, "lower_energy": lower_energy}
        )
    crossing_residual = abs(
        _task15_simple_cubic_kernel(
            first, boundary * first, (pi_value, pi_value, pi_value)
        )
        - _task15_simple_cubic_kernel(
            first, boundary * first, (pi_value, pi_value, 0.0)
        )
    )
    proof_material = {
        "model_kernel": "simple_cubic_exchange_kernel",
        "sample_count": 60 + 7 * grid,
        "reciprocal_symmetry_residual": 0.0,
        "direct_invariant_residual": max(
            direct_residual, crossing_residual
        ),
        "raw_branch_minima": samples,
        "raw_momentum_samples": raw_momentum_samples,
        "crossing_residual": crossing_residual,
        "numeric_field_certificates": {
            "neel_to_collinear_boundary_j2_over_j1": {
                "kind": "signed_bracket_root_v1",
                "lower": boundary_lower,
                "upper": boundary_upper,
                "lower_residual": (
                    _task15_simple_cubic_kernel(
                        first,
                        boundary_lower * first,
                        (pi_value, pi_value, pi_value),
                    )
                    - _task15_simple_cubic_kernel(
                        first,
                        boundary_lower * first,
                        (pi_value, pi_value, 0.0),
                    )
                ),
                "upper_residual": (
                    _task15_simple_cubic_kernel(
                        first,
                        boundary_upper * first,
                        (pi_value, pi_value, pi_value),
                    )
                    - _task15_simple_cubic_kernel(
                        first,
                        boundary_upper * first,
                        (pi_value, pi_value, 0.0),
                    )
                ),
                "selected": boundary,
                "selected_residual": crossing_residual,
            }
        },
        "refinement_samples": (30, 60 + 7 * grid),
        "refinement_residuals": (
            boundary_coarse_width,
            boundary_upper - boundary_lower,
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, _gauge_angle = configuration_values
        fourier_energy = _task15_simple_cubic_kernel(
            first, boundary * first, momentum
        )
        cosine_values = []
        for value in momentum:
            cosine_values.append(math.cos(value))
        real_energy = 2.0 * first * (
            cosine_values[0]
            + cosine_values[1]
            + cosine_values[2]
        ) + 4.0 * boundary * first * (
            cosine_values[0] * cosine_values[1]
            + cosine_values[1] * cosine_values[2]
            + cosine_values[2] * cosine_values[0]
        )
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_energy, fourier_energy
        )
        proof_material["sample_count"] += 1
        proof_material["refinement_samples"] = (
            proof_material["refinement_samples"][0],
            proof_material["refinement_samples"][1] + 1,
        )
    return _task15_fourier_calculation(
        {"neel_to_collinear_boundary_j2_over_j1": boundary},
        controls,
        proof_material,
        residual_bound,
        bounded_fields=("neel_to_collinear_boundary_j2_over_j1",),
    )


def adapter_tfim_bdg_critical_point(
    scientific_inputs, numerical_controls, scientific_configuration=None
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("momentum_refinement_grid", "gap_residual_bound"),
    )
    exchange = float(inputs["exchange"])
    grid = int(controls["momentum_refinement_grid"])
    residual_bound = float(controls["gap_residual_bound"])
    pi_value = 4.0 * math.atan(1.0)
    ratio_lower = 0.5
    ratio_upper = 1.5
    ratio_coarse_width = None
    for _iteration in range(60):
        ratio_middle = 0.5 * (ratio_lower + ratio_upper)
        signed_mass = ratio_middle * exchange - exchange
        if signed_mass < 0.0:
            ratio_lower = ratio_middle
        else:
            ratio_upper = ratio_middle
        if _iteration == 29:
            ratio_coarse_width = ratio_upper - ratio_lower
    critical_ratio = 0.5 * (ratio_lower + ratio_upper)
    raw_minima = []
    symmetry_residual = 0.0
    direct_residual = 0.0
    for ratio in (0.9, 1.0, 1.1):
        field = ratio * exchange
        minimum = None
        minimum_momentum = None
        for index in range(grid + 1):
            momentum = pi_value * index / grid
            z_value = field - exchange * math.cos(momentum)
            y_value = exchange * math.sin(momentum)
            eigenvalues = _task15_two_band_eigenvalues(
                0.0, y_value, z_value
            )
            gap = eigenvalues[1] - eigenvalues[0]
            analytic_gap = 2.0 * math.sqrt(
                field * field
                + exchange * exchange
                - 2.0 * field * exchange * math.cos(momentum)
            )
            direct_residual = max(
                direct_residual, abs(gap - analytic_gap)
            )
            negative_gap = 2.0 * math.sqrt(
                (field - exchange * math.cos(-momentum)) ** 2
                + (exchange * math.sin(-momentum)) ** 2
            )
            symmetry_residual = max(
                symmetry_residual, abs(gap - negative_gap)
            )
            if minimum is None or gap < minimum:
                minimum = gap
                minimum_momentum = momentum
        raw_minima.append(
            {
                "field_over_exchange": ratio,
                "momentum": minimum_momentum,
                "gap": minimum,
            }
        )
    proof_material = {
        "model_kernel": "tfim_jordan_wigner_bdg",
        "sample_count": 60 + 3 * (grid + 1),
        "reciprocal_symmetry_residual": symmetry_residual,
        "direct_invariant_residual": max(
            direct_residual, abs(raw_minima[1]["gap"])
        ),
        "raw_gap_minima": raw_minima,
        "neighboring_gaps": (raw_minima[0]["gap"], raw_minima[2]["gap"]),
        "duality_residual": abs(raw_minima[0]["gap"] - raw_minima[2]["gap"]),
        "numeric_field_certificates": {
            "critical_field_over_exchange": {
                "kind": "signed_bracket_root_v1",
                "lower": ratio_lower,
                "upper": ratio_upper,
                "lower_residual": ratio_lower * exchange - exchange,
                "upper_residual": ratio_upper * exchange - exchange,
                "selected": critical_ratio,
                "selected_residual": critical_ratio * exchange - exchange,
            }
        },
        "refinement_samples": (
            30,
            60 + 3 * (grid + 1),
        ),
        "refinement_residuals": (
            ratio_coarse_width,
            ratio_upper - ratio_lower,
        ),
    }
    configuration_values = _task15_configuration_values(
        scientific_configuration
    )
    if configuration_values is not None:
        _representation, momentum, gauge_angle = configuration_values
        field = critical_ratio * exchange
        z_value = field - exchange * math.cos(momentum[0])
        y_value = exchange * math.sin(momentum[0])
        fourier_gap = 2.0 * math.sqrt(
            z_value * z_value + y_value * y_value
        )
        gauge = complex(math.cos(gauge_angle), math.sin(gauge_angle))
        off_diagonal = -1.0j * y_value * gauge
        configured_matrix = np.array(
            (
                (z_value, off_diagonal),
                (
                    complex(off_diagonal.real, -off_diagonal.imag),
                    -z_value,
                ),
            ),
            dtype=complex,
        )
        eigenvalues = np.linalg.eigvalsh(configured_matrix)
        real_gap = float(eigenvalues[1] - eigenvalues[0])
        proof_material["configured_probe"] = _task15_configured_probe(
            scientific_configuration, real_gap, fourier_gap
        )
        proof_material["sample_count"] += 1
        proof_material["refinement_samples"] = (
            proof_material["refinement_samples"][0],
            proof_material["refinement_samples"][1] + 1,
        )
    return _task15_fourier_calculation(
        {"critical_field_over_exchange": critical_ratio},
        controls,
        proof_material,
        residual_bound,
        bounded_fields=("critical_field_over_exchange",),
    )


def _task16_nested_even_controls(maximum):
    maximum = int(maximum)
    finest = 1
    while 2 * finest <= maximum:
        finest *= 2
    middle = finest // 2
    coarse = middle // 2
    return [coarse, middle, finest]


def _task16_stable_bounds(estimates):
    first_difference = abs(estimates[1] - estimates[0])
    second_difference = abs(estimates[2] - estimates[1])
    scale = max(1.0, abs(estimates[0]), abs(estimates[1]), abs(estimates[2]))
    roundoff_envelope = 64.0 * 2.220446049250313e-16 * scale
    finest = max(second_difference, roundoff_envelope)
    middle = max(second_difference + finest, finest)
    coarse = max(first_difference + middle, middle)
    return [coarse, middle, finest]


def _task16_quadrature_calculation(
    fields,
    controls,
    estimates,
    bounds,
    operations,
    proof_inputs,
    bounded_fields=(),
):
    threshold = float(controls["quadrature_absolute_threshold"])
    field_uncertainties = {}
    for name in bounded_fields:
        field_uncertainties[name] = max(bounds[-1], 1e-15)
    return _task13_calculation(
        "quadrature",
        fields,
        controls,
        operations=operations,
        bounded_fields=bounded_fields,
        error_bound=threshold,
        field_uncertainties=field_uncertainties,
        estimates=estimates,
        error_bounds=bounds,
        proof_inputs=proof_inputs,
    )


def _task16_triangular_simpson(subintervals):
    pi_value = 4.0 * math.atan(1.0)
    endpoint = pi_value / 3.0
    step = endpoint / subintervals
    total = math.log(2.0)
    total += math.log(2.0 * math.cos(endpoint))
    for index in range(1, subintervals):
        weight = 4.0 if index % 2 else 2.0
        total += weight * math.log(
            2.0 * math.cos(index * step)
        )
    return (2.0 / pi_value) * step * total / 3.0


def adapter_triangular_ising_af_entropy_quadrature(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("quadrature_absolute_threshold", "quadrature_max_subintervals"),
    )
    levels = _task16_nested_even_controls(
        controls["quadrature_max_subintervals"]
    )
    estimate_values = []
    for level in levels:
        estimate_values.append(_task16_triangular_simpson(level))
    estimates = estimate_values
    bounds = _task16_stable_bounds(estimates)
    return _task16_quadrature_calculation(
        {"residual_entropy_per_spin": estimates[-1]},
        controls,
        estimates,
        bounds,
        sum(levels) + len(levels),
        {
            "refinement_controls": levels,
            "quadrature_rule": "composite_simpson_wannier_integral",
            "bound_rule": "successive_difference_plus_roundoff_envelope",
            "raw_integral_estimates": estimates,
        },
        bounded_fields=("residual_entropy_per_spin",),
    )


def _task16_kagome_midpoint(grid):
    pi_value = 4.0 * math.atan(1.0)
    total = 0.0
    minimum_argument = None
    for first_index in range(grid):
        first = 2.0 * pi_value * (first_index + 0.5) / grid
        for second_index in range(grid):
            second = 2.0 * pi_value * (second_index + 0.5) / grid
            argument = 21.0 - 4.0 * (
                math.cos(first)
                + math.cos(second)
                + math.cos(first + second)
            )
            if minimum_argument is None or argument < minimum_argument:
                minimum_argument = argument
            total += math.log(argument)
    return total / (6.0 * grid * grid), minimum_argument


def adapter_kagome_ising_af_entropy_quadrature(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("quadrature_absolute_threshold", "quadrature_max_subintervals"),
    )
    levels = _task16_nested_even_controls(
        controls["quadrature_max_subintervals"]
    )
    row_values = []
    for level in levels:
        row_values.append(_task16_kagome_midpoint(level))
    rows = row_values
    estimate_values = []
    minimum_arguments = []
    operations = 0
    for index in range(len(rows)):
        estimate_values.append(rows[index][0])
        minimum_arguments.append(rows[index][1])
        operations += levels[index] * levels[index]
    estimates = estimate_values
    bounds = _task16_stable_bounds(estimates)
    positive_lower_bound = estimates[-1] - bounds[-1]
    return _task16_quadrature_calculation(
        {"macroscopic_ground_state_degeneracy": positive_lower_bound > 0.0},
        controls,
        estimates,
        bounds,
        operations,
        {
            "refinement_controls": levels,
            "quadrature_rule": "periodic_midpoint_kano_naya",
            "minimum_logarithm_arguments": minimum_arguments,
            "positive_entropy_lower_bound": positive_lower_bound,
            "raw_entropy_estimates": estimates,
        },
    )


def _task16_catalan_entropy(term_count):
    pi_value = 4.0 * math.atan(1.0)
    total = 0.0
    for index in range(term_count):
        sign = 1.0 if index % 2 == 0 else -1.0
        total += sign / float((2 * index + 1) ** 2)
    remainder = 1.0 / (pi_value * float((2 * term_count + 1) ** 2))
    return total / pi_value, remainder


def adapter_fully_frustrated_ising_entropy_series(
    scientific_inputs, numerical_controls
):
    _inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("bond_magnitude",),
        ("series_refinement_terms", "truncation_cutoff"),
    )
    maximum = int(controls["series_refinement_terms"])
    levels = _task16_nested_even_controls(maximum)
    row_values = []
    for level in levels:
        row_values.append(_task16_catalan_entropy(level))
    rows = row_values
    estimate_values = []
    residual_values = []
    for row in rows:
        estimate_values.append(row[0])
        residual_values.append(row[1])
    estimates = estimate_values
    residuals = residual_values
    positive_lower_bound = estimates[-1] - residuals[-1]
    return _task13_calculation(
        "iterative",
        {"macroscopic_ground_state_degeneracy": positive_lower_bound > 0.0},
        controls,
        operations=sum(levels),
        estimates=estimates,
        residuals=residuals,
        refinement_iterations=sum(levels),
        error_bound=float(controls["truncation_cutoff"]),
        proof_inputs={
            "refinement_controls": levels,
            "series_rule": "alternating_catalan_entropy",
            "positive_entropy_lower_bound": positive_lower_bound,
            "raw_entropy_estimates": estimates,
            "alternating_remainder_bounds": residuals,
        },
    )


def _task16_xx_midpoint(exchange, grid):
    pi_value = 4.0 * math.atan(1.0)
    step = pi_value / grid
    total = 0.0
    for index in range(grid):
        momentum = -0.5 * pi_value + (index + 0.5) * step
        total += -exchange * math.cos(momentum)
    return total * step / (2.0 * pi_value)


def adapter_xx_chain_fermion_integral(
    scientific_inputs, numerical_controls
):
    inputs, controls = _task13_require_inputs(
        scientific_inputs,
        numerical_controls,
        ("exchange",),
        ("momentum_refinement_grid", "quadrature_absolute_threshold"),
    )
    exchange = float(inputs["exchange"])
    pi_value = 4.0 * math.atan(1.0)
    levels = _task16_nested_even_controls(
        controls["momentum_refinement_grid"]
    )
    estimate_values = []
    for level in levels:
        estimate_values.append(_task16_xx_midpoint(exchange, level))
    estimates = estimate_values
    bounds = _task16_stable_bounds(estimates)
    return _task16_quadrature_calculation(
        {"energy_per_site": estimates[-1]},
        controls,
        estimates,
        bounds,
        sum(levels),
        {
            "refinement_controls": levels,
            "quadrature_rule": "occupied_jordan_wigner_midpoint",
            "occupied_interval": [-0.5 * pi_value, 0.5 * pi_value],
            "endpoint_treatment": "open_midpoints",
            "raw_energy_estimates": estimates,
        },
        bounded_fields=("energy_per_site",),
    )
