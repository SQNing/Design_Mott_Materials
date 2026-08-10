import dataclasses
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_adapters import (
    AdapterContractError,
    AdapterDefinition,
    ConvergenceContract,
    CounterfactualDomain,
    EligibilityDecision,
    FrozenJsonObject,
    ParameterSource,
    ProblemSizePolicy,
    ResourceLimits,
    RuntimeRequirements,
    ValueSchema,
    canonical_json_bytes,
    canonical_sha256,
    freeze_json,
    thaw_json,
)


def _number_schema(*, lower=0.0, upper=None, units="dimensionless"):
    return ValueSchema(
        kind="number",
        required=True,
        lower=lower,
        upper=upper,
        item_schema=None,
        properties=(),
        units=units,
    )


def _object_schema(properties):
    return ValueSchema(
        kind="object",
        required=True,
        lower=None,
        upper=None,
        item_schema=None,
        properties=properties,
        units="",
    )


def _adapter_values(observable_identity, fixed_sizes, valid_rules):
    scientific_inputs = _object_schema(
        (("exchange", _number_schema(lower=0.0, units="J")),)
    )
    numerical_controls = _object_schema(())
    output_schema = _object_schema(
        (("energy_per_site", _number_schema(units="J")),)
    )
    return {
        "adapter_id": "xxx_bethe_energy",
        "entry_symbol": (
            "validation.literature_evidence_adapters:adapter_xxx_bethe_energy"
        ),
        "observable_identity": observable_identity,
        "scientific_input_schema": scientific_inputs,
        "numerical_control_schema": numerical_controls,
        "parameter_sources": (
            ParameterSource(
                parameter_name="exchange",
                kind="canonical_model_parameter",
                details={"canonical_path": ["hamiltonian", "exchange"]},
            ),
        ),
        "output_schema": output_schema,
        "backend_kind": "analytic",
        "problem_size_policy": ProblemSizePolicy(
            kind="fixed_local",
            fixed_sizes=fixed_sizes,
            allowed_sizes={},
        ),
        "runtime_requirements": RuntimeRequirements(
            interpreter="python3",
            packages=(),
            native_libraries=(),
            backend_resources=(),
        ),
        "convergence_contract": ConvergenceContract(
            kind="exact",
            requirements={"uncertainty": 0.0},
        ),
        "counterfactual_domain": CounterfactualDomain(
            valid_rules=valid_rules,
            invalid_rules={"exchange": {"values": [0.0, -1.0]}},
        ),
        "oracle_id": "xxx_bethe_energy_series_oracle",
        "resource_limits": ResourceLimits(
            cpu_seconds=10,
            wall_seconds=20.0,
            address_space_bytes=256_000_000,
            output_bytes=64_000,
            file_descriptors=16,
            process_count=1,
        ),
    }


def _observable_identity():
    return {
        "subject": "ground-state energy",
        "system_or_material": "spin-half XXX chain",
        "hamiltonian": {"terms": ["exchange"]},
        "parameter_regime": {"exchange": [1.0]},
        "size_or_limit": {"kind": "thermodynamic_limit"},
        "observable_definition": {"field": "energy_per_site"},
        "units": {"energy_per_site": "J"},
        "conditions": {"temperature": [0.0]},
    }


class _CustomItemsMapping(Mapping):
    def __init__(self, visible, yielded_items):
        self._visible = visible
        self._yielded_items = yielded_items

    def __getitem__(self, key):
        return self._visible[key]

    def __iter__(self):
        return iter(self._visible)

    def __len__(self):
        return len(self._visible)

    def keys(self):
        return self._visible.keys()

    def items(self):
        return iter(self._yielded_items)


class _BrokenItemsMapping(Mapping):
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def items(self):
        raise RuntimeError("broken items traversal")


class _PartiallyMutatingItemsMapping(Mapping):
    def __init__(self):
        self._backing = {"first": 1}

    def __getitem__(self, key):
        return self._backing[key]

    def __iter__(self):
        return iter(self._backing)

    def __len__(self):
        return len(self._backing)

    def items(self):
        yield "first", 1
        self._backing["injected"] = 2
        raise RuntimeError("mapping mutated during traversal")


class _CallerBackedTuple(tuple):
    def __new__(cls, backing):
        instance = tuple.__new__(cls, ())
        instance._backing = backing
        return instance

    def __iter__(self):
        return iter(self._backing)

    def __len__(self):
        return len(self._backing)

    def __getitem__(self, index):
        return self._backing[index]


def _list_cycle():
    value = []
    value.append(value)
    return value


def _mapping_cycle():
    value = {}
    value["self"] = value
    return value


def test_freeze_json_rejects_non_string_keys_unknown_objects_and_nonfinite_numbers():
    class Unknown:
        pass

    invalid_values = (
        {1: "non-string key"},
        {"nested": [{"value": Unknown()}]},
        {"nested": [{"value": object()}]},
        {"bytes": b"not JSON"},
        {"set": {1, 2}},
        {"callable": lambda: None},
        {"number": math.nan},
        {"number": math.inf},
        {"number": -math.inf},
    )

    for value in invalid_values:
        with pytest.raises(AdapterContractError):
            freeze_json(value)


def test_freeze_json_rejects_callable_containers_and_frozen_subclasses():
    class CallableMapping(dict):
        def __call__(self):
            return None

    class CallableList(list):
        def __call__(self):
            return None

    class MutableBackedFrozenJsonObject(FrozenJsonObject):
        def __init__(self, backing):
            super().__init__(backing)
            object.__setattr__(self, "_backing", backing)

        def __getitem__(self, key):
            return self._backing[key]

        def __iter__(self):
            return iter(self._backing)

        def __len__(self):
            return len(self._backing)

    accepted_callable_types = []
    for value in (CallableMapping(x=1), CallableList([1, 2])):
        try:
            freeze_json(value)
        except AdapterContractError:
            continue
        accepted_callable_types.append(type(value).__name__)
    assert accepted_callable_types == []

    backing = {"x": [1]}
    untrusted = MutableBackedFrozenJsonObject(backing)
    with pytest.raises(AdapterContractError):
        freeze_json(untrusted)
    with pytest.raises(AdapterContractError):
        thaw_json(untrusted)
    backing["x"].append(2)
    with pytest.raises(AdapterContractError):
        canonical_sha256(untrusted)

    exact_frozen = freeze_json({"x": [1]})
    assert type(exact_frozen) is FrozenJsonObject
    assert freeze_json(exact_frozen) is exact_frozen


def test_freeze_json_rejects_duplicate_mapping_items():
    duplicate_mapping = _CustomItemsMapping(
        {"x": 1},
        (("x", 1), ("x", 2)),
    )

    with pytest.raises(AdapterContractError, match="duplicate"):
        freeze_json(duplicate_mapping)


@pytest.mark.parametrize(
    "mapping",
    (_BrokenItemsMapping(), _PartiallyMutatingItemsMapping()),
    ids=("broken_items", "mutation_then_exception"),
)
@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_malformed_mapping_traversal_is_normalized(mapping, operation):
    with pytest.raises(AdapterContractError):
        operation(mapping)


@pytest.mark.parametrize(
    "cycle_factory", (_list_cycle, _mapping_cycle), ids=("list", "mapping")
)
@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_recursive_json_containers_are_rejected(cycle_factory, operation):
    with pytest.raises(AdapterContractError, match="cycle"):
        operation(cycle_factory())


@pytest.mark.parametrize(
    "operation", (freeze_json, canonical_json_bytes), ids=("freeze", "canonical")
)
def test_excessive_json_nesting_is_rejected(operation):
    value = 0
    for _ in range(256):
        value = [value]

    with pytest.raises(AdapterContractError, match="nesting"):
        operation(value)


def test_shared_noncyclic_json_aliases_are_copied_and_accepted():
    shared = {"values": [1, 2]}

    frozen = freeze_json({"left": shared, "right": shared})

    assert frozen["left"] == frozen["right"]
    assert frozen["left"] is not frozen["right"]
    assert thaw_json(frozen) == {
        "left": {"values": [1, 2]},
        "right": {"values": [1, 2]},
    }


def test_frozen_json_equality_and_hash_use_canonical_types():
    frozen_integer = freeze_json({"x": 1})
    equal_integer = freeze_json({"x": 1})
    frozen_float = freeze_json({"x": 1.0})
    frozen_boolean = freeze_json({"x": True})

    assert frozen_integer == equal_integer == {"x": 1}
    assert {"x": 1} == frozen_integer
    assert hash(frozen_integer) == hash(equal_integer)
    assert frozen_integer != frozen_float
    assert frozen_integer != frozen_boolean
    assert frozen_float != frozen_boolean

    frozen_set = {frozen_integer, equal_integer, frozen_float, frozen_boolean}
    assert len(frozen_set) == 3
    lookup = {
        frozen_integer: "integer",
        frozen_float: "float",
        frozen_boolean: "boolean",
    }
    assert lookup[equal_integer] == "integer"
    assert lookup[freeze_json({"x": 1.0})] == "float"
    assert lookup[freeze_json({"x": True})] == "boolean"

    class MalformedMapping(dict):
        def items(self):
            raise RuntimeError("malformed mapping")

    assert frozen_integer != MalformedMapping(x=1)
    assert frozen_integer != object()


def test_freeze_json_recursively_prevents_mutation():
    caller_owned = {
        "model": {
            "couplings": [1.0, {"next_nearest": [0.25, 0.5]}],
            "labels": ["α", "β"],
        },
        "enabled": True,
    }
    expected = {
        "enabled": True,
        "model": {
            "couplings": [1.0, {"next_nearest": [0.25, 0.5]}],
            "labels": ["α", "β"],
        },
    }

    frozen = freeze_json(caller_owned)
    digest_before = canonical_sha256(frozen)
    hash_before = hash(frozen)

    caller_owned["model"]["couplings"][1]["next_nearest"].append(0.75)
    caller_owned["model"]["labels"][0] = "changed"
    caller_owned["new"] = "field"

    assert thaw_json(frozen) == expected
    assert canonical_sha256(frozen) == digest_before
    assert hash(frozen) == hash_before == hash(freeze_json(expected))
    assert isinstance(frozen["model"]["couplings"], tuple)
    with pytest.raises(TypeError):
        frozen["new"] = "field"
    with pytest.raises(TypeError):
        frozen["model"]["couplings"][1]["new"] = 1
    with pytest.raises(AttributeError):
        frozen["model"]["labels"].append("γ")


def test_canonical_json_is_sorted_compact_utf8_and_rejects_nan():
    value = {"z": "自旋", "a": [{"β": 2, "a": 1}], "space": "kept value"}

    encoded = canonical_json_bytes(value)

    assert encoded == (
        '{"a":[{"a":1,"β":2}],"space":"kept value","z":"自旋"}'.encode(
            "utf-8"
        )
    )
    assert canonical_sha256(value) == canonical_sha256(freeze_json(value))
    with pytest.raises(AdapterContractError):
        canonical_json_bytes({"nested": [1.0, math.nan]})


SURROGATE_JSON_VALUES = (
    pytest.param({"value": "\ud800"}, id="surrogate_string_value"),
    pytest.param({"\ud800": "value"}, id="surrogate_mapping_key"),
)


@pytest.mark.parametrize("value", SURROGATE_JSON_VALUES)
def test_freeze_json_rejects_non_utf8_unicode_strings(value):
    with pytest.raises(AdapterContractError, match="UTF-8"):
        freeze_json(value)


@pytest.mark.parametrize("value", SURROGATE_JSON_VALUES)
@pytest.mark.parametrize(
    "operation", (canonical_json_bytes, canonical_sha256), ids=("bytes", "sha256")
)
def test_canonical_json_normalizes_non_utf8_unicode_failures(value, operation):
    with pytest.raises(AdapterContractError, match="UTF-8"):
        operation(value)


def test_accepted_frozen_json_remains_reflexive_and_hashable():
    frozen = freeze_json({"label": "自旋", "nested": ["λ", {"spin": 1}]})
    digest = canonical_sha256(frozen)

    assert frozen == frozen
    assert hash(frozen) == hash(frozen)
    assert {frozen} == {freeze_json({"label": "自旋", "nested": ["λ", {"spin": 1}]})}
    assert canonical_sha256(frozen) == digest


def test_thaw_json_rejects_non_utf8_unicode_strings():
    with pytest.raises(AdapterContractError, match="UTF-8"):
        thaw_json("\ud800")


def test_value_schema_units_reject_non_utf8_unicode_strings():
    with pytest.raises(AdapterContractError, match="UTF-8"):
        _number_schema(units="\ud800")


@pytest.mark.parametrize(
    "field_name",
    ("interpreter", "packages", "native_libraries", "backend_resources"),
)
def test_runtime_requirement_strings_reject_non_utf8_unicode(field_name):
    values = {
        "interpreter": "python3",
        "packages": (),
        "native_libraries": (),
        "backend_resources": (),
    }
    values[field_name] = "\ud800" if field_name == "interpreter" else ("\ud800",)

    with pytest.raises(AdapterContractError, match="UTF-8"):
        RuntimeRequirements(**values)


@pytest.mark.parametrize(
    "contract_type",
    (
        ValueSchema,
        ParameterSource,
        CounterfactualDomain,
        ConvergenceContract,
        ProblemSizePolicy,
        RuntimeRequirements,
        ResourceLimits,
        AdapterDefinition,
        EligibilityDecision,
    ),
    ids=lambda contract_type: contract_type.__name__,
)
def test_closed_contract_records_are_runtime_sealed(contract_type):
    with pytest.raises(TypeError, match="sealed|subclass"):
        type(f"Unsafe{contract_type.__name__}", (contract_type,), {})


def test_adapter_rejects_validation_bypassing_schema_subclass():
    try:
        bypass_type = type(
            "BypassingValueSchema",
            (ValueSchema,),
            {"__post_init__": lambda self: None},
        )
    except TypeError:
        return
    bypass = bypass_type(
        kind="object",
        required="not-boolean",
        lower=math.nan,
        upper=None,
        item_schema=None,
        properties=(("exchange", _number_schema()),),
        units=None,
    )
    values = _adapter_values(
        _observable_identity(),
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )
    values["scientific_input_schema"] = bypass

    with pytest.raises(AdapterContractError, match="scientific_input_schema"):
        AdapterDefinition(**values)


@pytest.mark.parametrize(
    "field_name", ("packages", "native_libraries", "backend_resources")
)
def test_runtime_requirements_reject_caller_backed_tuple_subclasses(field_name):
    values = {
        "interpreter": "python3",
        "packages": (),
        "native_libraries": (),
        "backend_resources": (),
    }
    values[field_name] = _CallerBackedTuple(["mutable_requirement"])

    with pytest.raises(AdapterContractError, match=field_name):
        RuntimeRequirements(**values)


def test_adapter_rejects_caller_backed_parameter_source_tuple_subclass():
    values = _adapter_values(
        _observable_identity(),
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )
    values["parameter_sources"] = _CallerBackedTuple(
        list(values["parameter_sources"])
    )

    with pytest.raises(AdapterContractError, match="parameter_sources"):
        AdapterDefinition(**values)


def test_adapter_observable_identity_uses_one_exact_frozen_snapshot():
    visible = _observable_identity()
    inconsistent = _CustomItemsMapping(
        visible,
        (*visible.items(), ("target", -math.log(2.0))),
    )
    values = _adapter_values(
        inconsistent,
        {"spin_count": [2]},
        {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
    )

    with pytest.raises(AdapterContractError, match="observable_identity|target"):
        AdapterDefinition(**values)


def test_adapter_definition_rejects_missing_unknown_and_mutable_fields():
    observable_identity = {
        "subject": "ground-state energy",
        "system_or_material": "spin-half XXX chain",
        "hamiltonian": {"terms": ["exchange"]},
        "parameter_regime": {"exchange": [1.0]},
        "size_or_limit": {"kind": "thermodynamic_limit"},
        "observable_definition": {"field": "energy_per_site"},
        "units": {"energy_per_site": "J"},
        "conditions": {"temperature": [0.0]},
    }
    fixed_sizes = {"spin_count": [2]}
    valid_rules = {
        "exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}
    }
    values = _adapter_values(observable_identity, fixed_sizes, valid_rules)

    definition = AdapterDefinition(**values)
    identity_digest = canonical_sha256(definition.observable_identity)
    size_digest = canonical_sha256(definition.problem_size_policy.fixed_sizes)

    observable_identity["hamiltonian"]["terms"].append("target-dependent term")
    fixed_sizes["spin_count"].append(4)
    valid_rules["exchange"]["bounds"][0] = -100.0

    assert canonical_sha256(definition.observable_identity) == identity_digest
    assert canonical_sha256(definition.problem_size_policy.fixed_sizes) == size_digest
    assert thaw_json(definition.problem_size_policy.fixed_sizes) == {"spin_count": [2]}
    assert thaw_json(definition.counterfactual_domain.valid_rules) == {
        "exchange": {"bounds": [0.1, 3.0], "kind": "finite_interval"}
    }
    assert tuple(field.name for field in dataclasses.fields(AdapterDefinition)) == (
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

    missing = dict(values)
    missing.pop("oracle_id")
    with pytest.raises(AdapterContractError, match="missing.*oracle_id"):
        AdapterDefinition(**missing)

    with pytest.raises(AdapterContractError, match="unknown|unexpected"):
        AdapterDefinition(**values, expected_result=-math.log(2.0))

    mutable_sources = dict(values)
    mutable_sources["parameter_sources"] = list(values["parameter_sources"])
    with pytest.raises(AdapterContractError, match="parameter_sources"):
        AdapterDefinition(**mutable_sources)

    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.adapter_id = "changed"

    bad_identity = dict(values)
    bad_identity["observable_identity"] = {
        **thaw_json(definition.observable_identity),
        "target": -math.log(2.0),
    }
    with pytest.raises(AdapterContractError, match="observable_identity"):
        AdapterDefinition(**bad_identity)

    for backend_kind in ("", "python", "sparse_ed"):
        with pytest.raises(AdapterContractError, match="backend_kind"):
            AdapterDefinition(**{**values, "backend_kind": backend_kind})

    for invalid_contract in (
        lambda: ParameterSource("exchange", "registry_value", {}),
        lambda: ProblemSizePolicy("dynamic", {}, {}),
        lambda: ConvergenceContract("trust_me", {}),
        lambda: ConvergenceContract([], {}),
    ):
        with pytest.raises(AdapterContractError):
            invalid_contract()

    eligible = EligibilityDecision(
        disposition="eligible",
        adapter_id="xxx_bethe_energy",
        oracle_id="xxx_bethe_energy_series_oracle",
        reason=None,
    )
    assert eligible.reason is None
    with pytest.raises(AdapterContractError):
        EligibilityDecision("eligible", None, None, None)
    with pytest.raises(AdapterContractError):
        EligibilityDecision(
            "source_parse_only",
            "xxx_bethe_energy",
            "xxx_bethe_energy_series_oracle",
            "no_independent_oracle",
        )
    with pytest.raises(AdapterContractError):
        EligibilityDecision("source_parse_only", None, None, "arbitrary_reason")
    source_only = EligibilityDecision(
        "source_parse_only", None, None, "target_equivalent_input"
    )
    assert source_only.adapter_id is source_only.oracle_id is None


def test_schema_rejects_bool_where_numeric_is_required():
    for field_name in ("lower", "upper"):
        values = {
            "kind": "number",
            "required": True,
            "lower": 0.0,
            "upper": 1.0,
            "item_schema": None,
            "properties": (),
            "units": "J",
        }
        values[field_name] = True
        with pytest.raises(AdapterContractError, match=field_name):
            ValueSchema(**values)

    with pytest.raises(AdapterContractError, match="cpu_seconds"):
        ResourceLimits(
            cpu_seconds=True,
            wall_seconds=20,
            address_space_bytes=256_000_000,
            output_bytes=64_000,
            file_descriptors=16,
            process_count=1,
        )

    with pytest.raises(AdapterContractError, match="lower"):
        ValueSchema(
            kind="integer",
            required=True,
            lower=math.inf,
            upper=None,
            item_schema=None,
            properties=(),
            units="sites",
        )

    with pytest.raises(AdapterContractError, match="units"):
        ValueSchema(
            kind="number",
            required=True,
            lower=None,
            upper=None,
            item_schema=None,
            properties=(),
            units=None,
        )
