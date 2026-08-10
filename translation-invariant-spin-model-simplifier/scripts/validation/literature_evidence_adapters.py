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
import re
from types import MappingProxyType
from typing import Any


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
    return tuple(token.lower() for token in _METADATA_TOKEN_RE.findall(separated))


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
    if not allow_numerical_control and _is_numerical_control_identifier(tokens):
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
            raise AdapterContractError("proof_kind is not an approved output proof kind")
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
        raise AdapterContractError(f"{field_name} must be an exact ValueSchema")
    schema_id = id(schema)
    if schema_id in active_schema_ids:
        raise AdapterContractError(f"{field_name} contains a ValueSchema cycle")
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


def _snapshot_value_schema(schema: ValueSchema, field_name: str) -> ValueSchema:
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
        raise AdapterContractError(f"{field_name} must be an exact OutputSchema")
    field_items = output_schema.fields
    if type(field_items) is not tuple:
        raise AdapterContractError(f"{field_name}.fields must be an immutable tuple")
    snapshots = []
    for index, item in enumerate(field_items):
        if type(item) is not tuple or len(item) != 2:
            raise AdapterContractError(
                f"{field_name}.fields[{index}] must be an exact pair"
            )
        selector_field, binding = item
        if type(binding) is not OutputFieldBinding:
            raise AdapterContractError(
                f"{field_name}.fields[{index}].binding must be an OutputFieldBinding"
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
            "validation.literature_evidence_adapters:adapter_" + self.adapter_id
        ):
            raise AdapterContractError(
                "entry_symbol must be the exact unresolved adapter symbol"
            )
        observable_identity = require_exact_keys(
            self.observable_identity,
            _OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        for field_name in ("scientific_input_schema", "numerical_control_schema"):
            schema = getattr(self, field_name)
            if type(schema) is not ValueSchema or schema.kind != "object":
                raise AdapterContractError(
                    f"{field_name} must be an object ValueSchema"
                )
        if type(self.output_schema) is not OutputSchema:
            raise AdapterContractError("output_schema must be an OutputSchema")
        output_schema = _snapshot_output_schema(self.output_schema)
        parameter_sources = _require_tuple(self.parameter_sources, "parameter_sources")
        if any(type(item) is not ParameterSource for item in parameter_sources):
            raise AdapterContractError(
                "parameter_sources must contain only ParameterSource records"
            )
        for index, parameter_source in enumerate(parameter_sources):
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
            name for name, _ in self.scientific_input_schema.properties
        )
        if set(parameter_names) != set(scientific_names):
            raise AdapterContractError(
                "parameter_sources must bind every scientific input exactly once"
            )
        if type(self.backend_kind) is not str:
            raise AdapterContractError("backend_kind must be a string")
        if self.backend_kind not in _BACKEND_KINDS:
            raise AdapterContractError(f"unknown backend_kind {self.backend_kind!r}")
        for field_name, expected_type in (
            ("problem_size_policy", ProblemSizePolicy),
            ("runtime_requirements", RuntimeRequirements),
            ("convergence_contract", ConvergenceContract),
            ("counterfactual_domain", CounterfactualDomain),
            ("resource_limits", ResourceLimits),
        ):
            if type(getattr(self, field_name)) is not expected_type:
                raise AdapterContractError(
                    f"{field_name} must be a {expected_type.__name__}"
                )
        require_identifier(self.oracle_id, "oracle_id")
        _validate_authored_string(
            self.adapter_id, "adapter_id", allow_numerical_control=True
        )
        _validate_authored_string(
            self.oracle_id, "oracle_id", allow_numerical_control=True
        )
        _validate_authored_json(observable_identity, "observable_identity")
        _validate_authored_schema(
            self.scientific_input_schema, "scientific_input_schema"
        )
        _validate_authored_schema(
            self.numerical_control_schema,
            "numerical_control_schema",
            allow_numerical_control=True,
        )
        for selector_field, binding in output_schema:
            _validate_authored_string(selector_field, "output_schema selector")
            _validate_authored_string(binding.raw_field, "output_schema raw_field")
            _validate_authored_string(binding.proof_kind, "output_schema proof_kind")
            _validate_authored_schema(
                binding.value_schema, f"output_schema.{selector_field}"
            )
        _validate_authored_json(
            self.problem_size_policy.fixed_sizes, "problem_size_policy.fixed_sizes"
        )
        _validate_authored_json(
            self.problem_size_policy.allowed_sizes,
            "problem_size_policy.allowed_sizes",
        )
        for field_name in (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ):
            value = getattr(self.runtime_requirements, field_name)
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
            self.convergence_contract.requirements,
            "convergence_contract.requirements",
        )
        _validate_authored_json(
            self.counterfactual_domain.valid_rules,
            "counterfactual_domain.valid_rules",
        )
        _validate_authored_json(
            self.counterfactual_domain.invalid_rules,
            "counterfactual_domain.invalid_rules",
        )
        object.__setattr__(self, "observable_identity", observable_identity)
        object.__setattr__(self, "output_schema", output_schema)


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
    specs: tuple[tuple[str, str, str, int | float | None, int | float | None], ...]
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
                        0 if selector in _NONNEGATIVE_OUTPUT_SELECTORS else None,
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
                "direct_exact_value",
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
        observable_definition="positive self-duality root followed by temperature inversion",
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
        packages=("scipy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": "duality equation residual lies below the declared control"
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
            ("quadrature_max_subintervals", "integer", "steps", 1, 100000),
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
        observable_definition="field and anisotropy coordinates of BdG gap closings",
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
            "bound_rule": "neighboring momentum gaps and matrix residuals bound each closing"
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
        parameter_regime="positive first-neighbor scale and nonnegative second-neighbor scale",
        size_or_limit="infinite two-sublattice reciprocal lattice",
        observable_definition="coupling ratio where the exchange-kernel minimum becomes a surface",
        conditions="classical spins with translation-invariant single-wavevector probes",
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
            "bound_rule": "kernel minima are bracketed from both coupling sides"
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
        observable_definition="complete sixteen-configuration sector enumeration",
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
            "closure_rule": "all sixteen configurations and all sectors are exhausted"
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
        observable_definition="dense diagonalization of singlet and triplet sectors",
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
            "closure_rule": "complete four-dimensional spin basis is diagonalized"
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
        observable_definition="logarithmic local-state counting normalized per spin",
        conditions="all allowed ice configurations carry equal statistical weight",
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
            "closure_rule": "local combinatorics and shared-spin normalization are analytic"
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
        parameter_regime="positive common energy scale at the permutation-equivalent point",
        size_or_limit="one two-spin-one bond",
        observable_definition="coefficient angle and generator commutator closure",
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
            "closure_rule": "all total-spin sectors and generator identities are evaluated"
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
        observable_definition="bilinear-biquadratic coefficient ratio and angle",
        conditions="constant energy shift separated from exchange coefficients",
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
            "closure_rule": "spin-sector polynomial coefficients are derived symbolically"
        },
        valid_rules={"projector_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={"projector_scale": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="compass_line_symmetry_matrix",
        oracle_id="compass_spin_flip_oracle",
        backend_kind="dense_ed",
        subject="line-flip symmetry commutators",
        system_or_material="square-lattice quantum compass model",
        hamiltonian="directional Pauli exchange on horizontal and vertical bonds",
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
            "closure_rule": "every declared line operator and both shapes are exhausted"
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
        hamiltonian="bond-directional Kitaev exchange with three field components",
        parameter_regime="positive exchange and three finite nonzero field components",
        size_or_limit="thermodynamic two-band Majorana Brillouin zone",
        observable_definition="third-order mass, bulk gap, and parity from lower-level band data",
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
            "bound_rule": "gap lower bound is positive and band parity is stable under finer sampling"
        },
        valid_rules={
            "kitaev_exchange": {"kind": "strictly_positive_finite"},
            "field_x": {"kind": "finite_nonzero"},
            "field_y": {"kind": "finite_nonzero"},
            "field_z": {"kind": "finite_nonzero"},
        },
        invalid_rules={
            "kitaev_exchange": {"kind": "nonpositive_or_nonfinite"},
            "field_x": {"kind": "zero_or_nonfinite"},
            "field_y": {"kind": "zero_or_nonfinite"},
            "field_z": {"kind": "zero_or_nonfinite"},
        },
    ),
    _metadata_definition(
        adapter_id="toric_code_stabilizer_rank",
        oracle_id="toric_code_logical_loop_oracle",
        backend_kind="enumeration",
        subject="torus ground-space dimension from stabilizer rank",
        system_or_material="square-lattice toric code",
        hamiltonian="commuting star and plaquette stabilizers over edge qubits",
        parameter_regime="nonzero commuting stabilizer coefficients",
        size_or_limit="two declared periodic torus shapes",
        observable_definition="GF2 incidence-matrix rank and logical dimension",
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
            "closure_rule": "GF2 elimination and all stabilizer dependencies are exact"
        },
        valid_rules={"stabilizer_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={"stabilizer_scale": {"kind": "nonpositive_or_nonfinite"}},
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
        observable_definition="complete projector spectrum and local VBS expectation",
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
            "closure_rule": "all nine eigenvalues and spin-sector multiplicities are exhausted"
        },
        valid_rules={"projector_scale": {"kind": "strictly_positive_finite"}},
        invalid_rules={"projector_scale": {"kind": "nonpositive_or_nonfinite"}},
    ),
    _metadata_definition(
        adapter_id="blume_capel_level_crossing",
        oracle_id="blume_capel_configuration_oracle",
        backend_kind="enumeration",
        subject="uniform-state zero-temperature level crossing",
        system_or_material="square-lattice spin-one Blume-Capel model",
        hamiltonian="nearest-neighbor Ising exchange plus single-ion anisotropy",
        parameter_regime="positive exchange and finite single-ion coefficient",
        size_or_limit="one-site uniform-state cell with square bond count",
        observable_definition="uniform spin-state energies and their crossing ratio",
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
            "closure_rule": "all three uniform spin states and square bonds are counted"
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
        hamiltonian="complete-graph exchange on one crossed four-spin plaquette",
        parameter_regime="strictly positive normalized exchange",
        size_or_limit="one crossed four-spin plaquette",
        observable_definition="plaquette energy minimization and total-spin norms",
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
        packages=("numpy",),
        convergence_kind="exact",
        convergence_requirements={
            "closure_rule": "total-spin identity and all pair bonds are evaluated"
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
        observable_definition="positive star-triangle root and temperature inversion",
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
        packages=("scipy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": "star-triangle equation residual lies below the declared control"
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
        observable_definition="successive entropy estimates and a positive lower bound",
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
            ("quadrature_max_subintervals", "integer", "steps", 1, 100000),
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
            "bound_rule": "successive entropy intervals contract above a positive lower bound"
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
        packages=("scipy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": "critical polynomial residual lies below the declared control"
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
        parameter_regime="positive nearest exchange with dimer-point coupling relation",
        size_or_limit="two declared periodic even chain lengths",
        observable_definition="ground energy density and rank of translated dimer coverings",
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
            "size_rule": "both declared lengths obey the same projector identity and rank rule"
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
        parameter_regime="positive exchange and arbitrary finite positive inverse temperature",
        size_or_limit="infinite chain transfer-matrix limit",
        observable_definition="analytic eigenvalue separation and zero-temperature limiting point",
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
            "closure_rule": "both transfer eigenvalues and their analytic separation are explicit"
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
        hamiltonian="nearest-neighbor isotropic exchange on corner-sharing tetrahedra",
        parameter_regime="strictly positive exchange",
        size_or_limit="thermodynamic reciprocal-space Coulomb phase",
        observable_definition="tetrahedron spin sums and two directional polarization limits",
        conditions="zero field with two distinct normalized approach directions",
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
            ("constraint_residual_bound", "number", "dimensionless", 0.0, None),
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
            "bound_rule": "constraint residuals contract and directional limits remain distinct"
        },
        valid_rules={
            "exchange": {"kind": "strictly_positive_finite"},
            "approach_direction_a": {"kind": "normalized_supported_direction"},
            "approach_direction_b": {"kind": "normalized_distinct_direction"},
        },
        invalid_rules={
            "exchange": {"kind": "nonpositive_or_nonfinite"},
            "approach_direction_a": {"kind": "unsupported_or_unnormalized"},
            "approach_direction_b": {"kind": "unsupported_equal_or_unnormalized"},
        },
    ),
    _metadata_definition(
        adapter_id="shastry_sutherland_dimer_ed",
        oracle_id="shastry_sutherland_bond_oracle",
        backend_kind="dense_ed",
        subject="orthogonal-dimer product energy and interdimer cancellation",
        system_or_material="spin-half Shastry-Sutherland lattice cells",
        hamiltonian="intradimer and orthogonal interdimer Heisenberg exchange",
        parameter_regime="positive intradimer scale with finite linked-cell coupling",
        size_or_limit="two declared open linked orthogonal-dimer cells",
        observable_definition="singlet-product energy normalized per dimer and per spin",
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
            "closure_rule": "all intradimer expectations and linked-cell cancellations are exact"
        },
        valid_rules={
            "intradimer_exchange": {"kind": "strictly_positive_finite"},
            "interdimer_exchange": {"kind": "finite_product_state_regime"},
        },
        invalid_rules={
            "intradimer_exchange": {"kind": "nonpositive_or_nonfinite"},
            "interdimer_exchange": {"kind": "outside_product_state_regime_or_nonfinite"},
        },
    ),
    _metadata_definition(
        adapter_id="simple_cubic_j1_j2_fourier",
        oracle_id="simple_cubic_real_space_energy_oracle",
        backend_kind="glt_fourier",
        subject="Néel-to-collinear exchange crossing",
        system_or_material="classical simple-cubic J1-J2 Heisenberg model",
        hamiltonian="first- and second-neighbor isotropic exchange",
        parameter_regime="positive first-neighbor and nonnegative second-neighbor exchange",
        size_or_limit="infinite simple-cubic reciprocal lattice",
        observable_definition="crossing of minimized Néel and collinear Fourier branches",
        conditions="classical unit spins and translation-invariant wavevectors",
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
            "bound_rule": "both Fourier branches are minimized and their crossing is bracketed"
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
        observable_definition="complete three-state spectrum grouped by equal energies",
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
            "closure_rule": "all three magnetic quantum-number states are exhausted"
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
        hamiltonian="nearest-neighbor Ising bonds with odd plaquette frustration",
        parameter_regime="strictly positive common bond magnitude",
        size_or_limit="thermodynamic square-lattice limit",
        observable_definition="successive entropy series bounds and positive limiting density",
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
            ("series_refinement_terms", "integer", "terms", 1, 1000000),
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
            "sequence_rule": "successive entropy bounds contract above a positive lower bound"
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
        observable_definition="field-to-exchange coordinate of the BdG gap closing",
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
            "bound_rule": "the BdG gap minimum is bracketed and closes under finer sampling"
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
        observable_definition="positive critical-equation root and temperature inversion",
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
        packages=("scipy",),
        convergence_kind="residual_bound",
        convergence_requirements={
            "bound_rule": "critical-equation residual lies below the declared control"
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
        parameter_regime="arbitrary strictly positive exchange at half filling",
        size_or_limit="thermodynamic occupied-momentum integral",
        observable_definition="successive occupied-dispersion integral bounds per site",
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
            ("momentum_refinement_grid", "integer", "points", 16, 1000000),
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
            "bound_rule": "successive occupied-dispersion integral bounds overlap and contract"
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
            *(getattr(definition, field.name) for field in fields(AdapterDefinition))
        )
        if definition_snapshot.adapter_id in catalog:
            raise AdapterContractError(
                "duplicate adapter ID in definition catalog: "
                f"{definition_snapshot.adapter_id}"
            )
        catalog[definition_snapshot.adapter_id] = definition_snapshot
    if len(catalog) != 29:
        raise AdapterContractError("definition catalog must contain exactly 29 rows")

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
                f"definition oracle does not match eligibility for {adapter_id}"
            )
        if definition.output_schema.selector_fields != decision.selector_fields:
            raise AdapterContractError(
                f"definition selector fields do not match eligibility for {adapter_id}"
            )
        if definition.oracle_id in oracle_ids:
            raise AdapterContractError("definition catalog contains duplicate oracle ID")
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
        raise AdapterContractError("definition problem-size policy assignment mismatch")
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


ADAPTER_DEFINITIONS: Mapping[str, AdapterDefinition] = _build_adapter_definitions(
    _ADAPTER_DEFINITION_ROWS
)


def get_adapter_definition(adapter_id: str) -> AdapterDefinition:
    require_identifier(adapter_id, "adapter_id")
    try:
        return ADAPTER_DEFINITIONS[adapter_id]
    except KeyError as error:
        raise AdapterContractError(f"unknown adapter_id {adapter_id}") from error
