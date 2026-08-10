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
        return value
    if isinstance(value, FrozenJsonObject):
        raise AdapterContractError(
            f"{field_name} contains an unsupported FrozenJsonObject subclass"
        )
    if type(value) is str:
        return _require_utf8_string(value, field_name)
    if value is None or type(value) in (bool, int):
        return value
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


def thaw_json(value: object, field_name: str = "value") -> object:
    """Convert frozen JSON data to fresh ordinary dictionaries and lists."""

    if callable(value):
        raise AdapterContractError(f"{field_name} contains a callable value")
    if type(value) is FrozenJsonObject:
        return {
            key: thaw_json(item, f"{field_name}.{key}")
            for key, item in value._items
        }
    if isinstance(value, FrozenJsonObject):
        raise AdapterContractError(
            f"{field_name} contains an unsupported FrozenJsonObject subclass"
        )
    if type(value) is tuple:
        return [
            thaw_json(item, f"{field_name}[{index}]")
            for index, item in enumerate(value)
        ]
    if type(value) is str:
        return _require_utf8_string(value, field_name)
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise AdapterContractError(f"{field_name} contains a non-finite number")
        return value
    raise AdapterContractError(
        f"{field_name} contains unsupported frozen JSON value {type(value).__name__}"
    )


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
    if type(value) is float and not math.isfinite(value):
        raise AdapterContractError(f"{field_name} must be a finite number")
    if positive and value <= 0:
        raise AdapterContractError(f"{field_name} must be positive")
    if nonnegative and value < 0:
        raise AdapterContractError(f"{field_name} must be nonnegative")
    return value


def _require_positive_integer(value: object, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise AdapterContractError(f"{field_name} must be a positive integer")
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
        if self.kind not in {"integer", "number"} and (
            self.lower is not None or self.upper is not None
        ):
            raise AdapterContractError(
                "lower and upper are allowed only for integer or number schemas"
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
        if type(self.kind) is not str or self.kind not in _PARAMETER_SOURCE_KINDS:
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
        if type(self.kind) is not str or self.kind not in _CONVERGENCE_KINDS:
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
        if type(self.kind) is not str or self.kind not in _PROBLEM_SIZE_KINDS:
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
    output_schema: ValueSchema
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
        observable_identity = require_exact_keys(
            self.observable_identity,
            _OBSERVABLE_IDENTITY_KEYS,
            "observable_identity",
        )
        for field_name in (
            "scientific_input_schema",
            "numerical_control_schema",
            "output_schema",
        ):
            schema = getattr(self, field_name)
            if type(schema) is not ValueSchema or schema.kind != "object":
                raise AdapterContractError(
                    f"{field_name} must be an object ValueSchema"
                )
        parameter_sources = _require_tuple(self.parameter_sources, "parameter_sources")
        if any(type(item) is not ParameterSource for item in parameter_sources):
            raise AdapterContractError(
                "parameter_sources must contain only ParameterSource records"
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
        if (
            type(self.backend_kind) is not str
            or self.backend_kind not in _BACKEND_KINDS
        ):
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
        object.__setattr__(self, "observable_identity", observable_identity)


_ELIGIBILITY_DISPOSITIONS = frozenset({"eligible", "source_parse_only"})
_SOURCE_PARSE_ONLY_REASONS = frozenset(
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
    disposition: str
    adapter_id: str | None
    oracle_id: str | None
    reason: str | None

    def __init__(self, *args, **kwargs):
        _initialize_closed(self, args, kwargs, EligibilityDecision)

    def __post_init__(self) -> None:
        if (
            type(self.disposition) is not str
            or self.disposition not in _ELIGIBILITY_DISPOSITIONS
        ):
            raise AdapterContractError(
                f"unknown eligibility disposition {self.disposition!r}"
            )
        if self.disposition == "eligible":
            require_identifier(self.adapter_id, "adapter_id")
            require_identifier(self.oracle_id, "oracle_id")
            if self.reason is not None:
                raise AdapterContractError("eligible decision cannot have a reason")
            return
        if self.adapter_id is not None or self.oracle_id is not None:
            raise AdapterContractError(
                "source_parse_only decision cannot resolve an adapter or oracle"
            )
        if (
            type(self.reason) is not str
            or self.reason not in _SOURCE_PARSE_ONLY_REASONS
        ):
            raise AdapterContractError(
                f"unknown source_parse_only reason {self.reason!r}"
            )
