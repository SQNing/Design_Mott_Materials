import dataclasses
import json
import math
import sys
from pathlib import Path
from types import MappingProxyType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_schema import (
    AdapterTrace,
    AuditOutcome,
    CanonicalObservable,
    ComparisonTrace,
    EvidenceRecord,
    EvidenceSchemaError,
    ExtractionTrace,
    SourceProvenance,
    canonical_json_bytes,
    validate_post_run_bijection,
    validate_pre_run_bijection,
)
from validation.literature_evidence_comparators import (
    ObservableComparisonError,
    compare_observables,
)


def observable(**overrides):
    values = {
        "canonical_observable_id": "haldane_gap_over_j",
        "benchmark_name": "haldane_gap_reference",
        "subject": "spin gap",
        "system": "spin-1 Heisenberg chain",
        "hamiltonian": {"terms": ["J S_i.S_j"]},
        "parameter_regime": {"J": 1.0},
        "size_or_limit": {"kind": "thermodynamic_limit"},
        "observable": {"quantity": "triplet_gap"},
        "representation": {"kind": "scalar"},
        "units": "dimensionless",
        "conditions": {"temperature": 0},
    }
    values.update(overrides)
    return CanonicalObservable(**values)


def source(**overrides):
    values = {
        "source_id": "white_huse_1993",
        "source_identity": {"doi": "10.1103/PhysRevB.48.3844"},
        "bibliographic_metadata": {"title": "Numerical study", "authors": ["White", "Huse"]},
        "retrieval_metadata": {"url": "https://example.test/paper.pdf", "date": "2026-07-15"},
        "media_type": "application/pdf",
        "raw_payload_sha256": "a" * 64,
        "raw_payload_byte_length": 1234,
        "license_access_notes": {"access": "publisher"},
        "citation_metadata_verification": {"verified": True, "method": "doi"},
    }
    values.update(overrides)
    return SourceProvenance(**values)


def record(name="haldane_gap_reference", **overrides):
    values = {
        "schema_version": "1",
        "benchmark_name": name,
        "evidence_mode": "local_source_parse",
        "source_id": "white_huse_1993",
        "source_sha256": "a" * 64,
        "registry_selector": {"path": ["standard_result", "gap"]},
        "canonical_observable_id": "haldane_gap_over_j",
        "target_locator": {"kind": "table", "label": "I"},
        "target_parser": "validation.parsers:parse_scalar",
        "normalization": {
            "kind": "ratio",
            "operations": [{"op": "scale", "factor": 1.0}],
        },
        "adapter": "validation.adapters:gap",
        "adapter_parameters": {"sizes": [32, 64]},
        "convergence": {"kind": "absolute", "tolerance": 1e-5},
        "comparison": {"kind": "absolute", "tolerance": 5e-5},
    }
    values.update(overrides)
    return EvidenceRecord(**values)


@pytest.mark.parametrize(
    ("factory", "field", "bad_value"),
    [
        (observable, "canonical_observable_id", ""),
        (observable, "benchmark_name", "  "),
        (source, "source_id", None),
        (record, "target_parser", ""),
        (record, "schema_version", " "),
    ],
)
def test_required_identifiers_are_nonempty(factory, field, bad_value):
    with pytest.raises(EvidenceSchemaError, match=field):
        factory(**{field: bad_value})


def test_structured_fields_are_json_compatible_and_deeply_immutable():
    conditions = {"temperature": [0, {"units": "K"}]}
    item = observable(conditions=conditions)
    conditions["temperature"].append(99)

    assert item.conditions == {"temperature": (0, {"units": "K"})}
    with pytest.raises(TypeError):
        item.conditions["other"] = 1
    with pytest.raises(AttributeError):
        item.conditions["temperature"].append(1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.subject = "changed"


@pytest.mark.parametrize("value", [{1: "bad key"}, {"bad": {1}}, {"bad": math.nan}, {"bad": object()}])
def test_structured_fields_reject_non_json_values(value):
    with pytest.raises(EvidenceSchemaError, match="conditions"):
        observable(conditions=value)


def test_source_provenance_validates_hash_length_and_byte_length():
    with pytest.raises(EvidenceSchemaError, match="raw_payload_sha256"):
        source(raw_payload_sha256="abc")
    with pytest.raises(EvidenceSchemaError, match="raw_payload_byte_length"):
        source(raw_payload_byte_length=-1)


@pytest.mark.parametrize("mode", ["", "manual", "recompute", None])
def test_evidence_modes_are_closed(mode):
    with pytest.raises(EvidenceSchemaError, match="evidence_mode"):
        record(evidence_mode=mode)


@pytest.mark.parametrize("mode", ["local_recompute", "local_source_parse", "projection_only"])
def test_all_supported_evidence_modes_are_accepted(mode):
    assert record(evidence_mode=mode).evidence_mode == mode


@pytest.mark.parametrize(
    "normalization",
    [
        "divide by J",
        {"description": "divide by J"},
        {"kind": "ratio"},
        {"rules": {"by": "J"}},
    ],
)
def test_normalization_requires_kind_and_executable_or_field_rules(normalization):
    with pytest.raises(EvidenceSchemaError, match="normalization"):
        record(normalization=normalization)


@pytest.mark.parametrize("rule_key", ["rules", "executable", "fields", "operations"])
def test_normalization_rejects_truthy_free_text_rule_content(rule_key):
    with pytest.raises(EvidenceSchemaError, match="normalization"):
        record(normalization={"kind": "ratio", rule_key: "divide by J"})


@pytest.mark.parametrize(
    ("rule_key", "content"),
    [
        ("rules", {}),
        ("executable", []),
        ("fields", ()),
        ("operations", {}),
    ],
)
def test_normalization_rejects_empty_structured_rule_content(rule_key, content):
    with pytest.raises(EvidenceSchemaError, match="normalization"):
        record(normalization={"kind": "ratio", rule_key: content})


@pytest.mark.parametrize(
    ("rule_key", "content"),
    [
        ("rules", [{"op": "identity"}]),
        ("executable", {"callable": "validation.normalizers:divide"}),
        (
            "fields",
            {
                "gap_over_j": {
                    "source_field": "gap_over_j",
                    "operation": {"op": "identity"},
                }
            },
        ),
        ("operations", [{"operator": "reciprocal"}]),
    ],
)
def test_normalization_accepts_nonempty_machine_readable_rule_content(rule_key, content):
    item = record(normalization={"kind": "ratio", rule_key: content})

    assert item.normalization[rule_key]


@pytest.mark.parametrize(
    "normalization",
    [
        {"kind": "ratio", "rules": [{"description": "divide by J"}]},
        {"kind": "ratio", "operations": [{"description": "divide by J"}]},
        {"kind": "ratio", "fields": ["divide by J"]},
        {"kind": "ratio", "fields": {"result": {"description": "gap divided by J"}}},
        {"kind": "ratio", "executable": {"description": "divide by J"}},
        {"kind": "not valid", "operations": [{"op": "identity"}]},
        {"kind": "ratio", "operations": [{"op": "divide"}]},
        {"kind": "ratio", "operations": [{"op": "scale", "prose": "double it"}]},
        {"kind": "ratio", "operations": ["identity"]},
        {
            "kind": "ratio",
            "rules": [{"op": "identity"}],
            "operations": [{"op": "identity"}],
        },
        {"kind": "ratio", "executable": {"callable": "divide by J"}},
        {
            "kind": "ratio",
            "executable": {"callable": "validation.normalizers:divide", "version": 0},
        },
        {"kind": "ratio", "operations": [{"op": "identity"}], "description": "prose"},
    ],
)
def test_normalization_rejects_adversarial_non_grammar_payloads(normalization):
    with pytest.raises(EvidenceSchemaError, match="normalization"):
        record(normalization=normalization)


@pytest.mark.parametrize(
    "normalization",
    [
        {"kind": "identity", "operations": [{"op": "identity"}]},
        {
            "kind": "affine",
            "operations": [
                {"operator": "scale", "factor": 2.0},
                {"op": "offset", "value": -1.0},
            ],
        },
        {
            "kind": "field_projection",
            "fields": {
                "gap": {
                    "source_field": "raw_gap",
                    "operation": {"op": "negate"},
                },
            },
        },
        {
            "kind": "custom",
            "executable": {
                "callable": "validation.normalizers:divide_by_j",
                "version": 2,
            },
        },
    ],
)
def test_normalization_accepts_closed_machine_readable_grammar(normalization):
    assert record(normalization=normalization).normalization


FIELD_OPERATOR_CASES = [
    ("identity", {}),
    ("scale", {"factor": 2.0}),
    ("offset", {"value": 1.0}),
    ("reciprocal", {}),
    ("select_field", {"source_field": "alternate_gap"}),
    (
        "rename_field",
        {"source_field": "alternate_gap", "target_field": "normalized_gap"},
    ),
    ("map_value", {"mapping": {"raw": "normalized"}}),
    ("negate", {}),
    ("require_equal", {"expected": 0.5}),
]


@pytest.mark.parametrize(("operator", "arguments"), FIELD_OPERATOR_CASES)
def test_field_normalization_enforces_valid_args_for_every_operator(operator, arguments):
    operation = {"op": operator, **arguments}
    normalization = {
        "kind": "field_projection",
        "fields": {
            "result": {"source_field": "raw_result", "operation": operation},
        },
    }

    assert record(normalization=normalization).normalization["fields"]["result"]


@pytest.mark.parametrize(("operator", "arguments"), FIELD_OPERATOR_CASES)
def test_field_normalization_rejects_missing_required_operator_args(operator, arguments):
    operation = {"op": operator, **arguments}
    if arguments:
        operation.pop(next(iter(arguments)))
    else:
        operation.pop("op")
    normalization = {
        "kind": "field_projection",
        "fields": {
            "result": {"source_field": "raw_result", "operation": operation},
        },
    }

    with pytest.raises(EvidenceSchemaError, match=r"normalization fields\.result\.operation"):
        record(normalization=normalization)


@pytest.mark.parametrize(("operator", "arguments"), FIELD_OPERATOR_CASES)
def test_field_normalization_rejects_unknown_args_for_every_operator(operator, arguments):
    operation = {"operator": operator, **arguments, "description": "prose"}
    normalization = {
        "kind": "field_projection",
        "fields": {
            "result": {"source_field": "raw_result", "operation": operation},
        },
    }

    with pytest.raises(EvidenceSchemaError, match=r"normalization fields\.result\.operation"):
        record(normalization=normalization)


@pytest.mark.parametrize(
    "normalization",
    [
        {1: "bad", "kind": "identity", "operations": [{"op": "identity"}]},
        {"kind": "identity", "operations": [{1: "bad", "op": "identity"}]},
        {"kind": "identity", "operations": [{"op": []}]},
    ],
)
def test_normalization_malformed_keys_and_operators_raise_schema_errors(normalization):
    with pytest.raises(EvidenceSchemaError, match="normalization"):
        record(normalization=normalization)


@pytest.mark.parametrize(
    "canonical_id",
    ["", "Haldane_gap", "haldane gap", "haldane/gap", " haldane_gap", "haldane_gap ", "haldane\ngap", "haldane\tgap"],
)
def test_canonical_observable_id_requires_lowercase_snake_case(canonical_id):
    with pytest.raises(EvidenceSchemaError, match="canonical_observable_id"):
        observable(canonical_observable_id=canonical_id)
    with pytest.raises(EvidenceSchemaError, match="canonical_observable_id"):
        record(canonical_observable_id=canonical_id)


@pytest.mark.parametrize("identifier", [" name", "name ", "name\npart", "name\tpart", "a/b", "a\\b"])
def test_benchmark_and_source_identifiers_reject_unsafe_whitespace_and_paths(identifier):
    with pytest.raises(EvidenceSchemaError, match="benchmark_name"):
        observable(benchmark_name=identifier)
    with pytest.raises(EvidenceSchemaError, match="source_id"):
        source(source_id=identifier)


def test_benchmark_and_source_identifiers_preserve_legitimate_punctuation():
    assert observable(benchmark_name="gap.v2-reference").benchmark_name == "gap.v2-reference"
    assert source(source_id="doi:10.1000-example").source_id == "doi:10.1000-example"


@pytest.mark.parametrize(
    "field",
    ["target_observable", "target_excerpt", "parsed_target", "strict_literature_match", "strict_match", "pass", "verdict"],
)
def test_evidence_record_rejects_forbidden_keys_at_any_depth(field):
    with pytest.raises(EvidenceSchemaError, match=field):
        record(comparison={"kind": "absolute", "rules": {field: True}})


def test_evidence_record_rejects_top_level_forbidden_extra_keys():
    valid = record()
    values = {field.name: getattr(valid, field.name) for field in dataclasses.fields(valid)}
    values["verdict"] = "pass"

    with pytest.raises(EvidenceSchemaError, match="verdict"):
        EvidenceRecord(**values)


@pytest.mark.parametrize("trace_type", [ExtractionTrace, AdapterTrace, ComparisonTrace, AuditOutcome])
def test_runtime_types_are_frozen_and_copy_payloads(trace_type):
    payload = {"values": [1, {"ok": True}]}
    trace = trace_type(benchmark_name="haldane_gap_reference", payload=payload)
    payload["values"].append(2)

    assert trace.payload == {"values": (1, {"ok": True})}
    with pytest.raises(TypeError):
        trace.payload["changed"] = True
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.benchmark_name = "changed"


def test_canonical_json_bytes_is_deterministic_for_dataclasses_mappings_and_sequences():
    left = {"z": [3, {"b": 2, "a": 1}], "a": observable()}
    observable_mapping = {
        field.name: getattr(observable(), field.name)
        for field in dataclasses.fields(CanonicalObservable)
    }
    right = {"a": observable_mapping, "z": (3, {"a": 1, "b": 2})}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    decoded = canonical_json_bytes({"snowman": "\u2603"})
    assert decoded == b'{"snowman":"\xe2\x98\x83"}'
    assert json.loads(canonical_json_bytes(left))['a']["benchmark_name"] == "haldane_gap_reference"


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan, {"bad": object()}, {1: "bad"}])
def test_canonical_json_bytes_rejects_unsupported_and_nonfinite_values(value):
    with pytest.raises(EvidenceSchemaError):
        canonical_json_bytes(value)


def compare(kind, literature, candidate, **kwargs):
    comparison = {"kind": kind, **kwargs.pop("comparison_overrides", {})}
    return compare_observables(
        benchmark_name="haldane_gap_reference",
        comparison=comparison,
        literature_operand=literature,
        candidate_operand=candidate,
        **kwargs,
    )


def test_exact_comparison_is_type_aware_for_scalars_booleans_and_strings():
    assert compare("exact", True, True).payload["matched"] is True
    assert compare("exact", "1", "1").payload["matched"] is True
    assert compare("exact", 1, 1.0).payload["matched"] is False
    result = compare("exact", True, 1)

    assert result.payload["matched"] is False
    assert "type" in result.payload["reason"]


def test_absolute_comparison_uses_tolerance_and_local_uncertainty_conservatively():
    passing = compare(
        "absolute", 1.0, 1.08,
        comparison_overrides={"tolerance": 0.1},
        local_uncertainty=0.02,
    )
    failing = compare(
        "absolute", 1.0, 1.081,
        comparison_overrides={"tolerance": 0.1},
        local_uncertainty=0.02,
    )

    assert passing.payload["matched"] is True
    assert passing.payload["error"] == pytest.approx(0.08)
    assert passing.payload["tolerance"] == 0.1
    assert failing.payload["matched"] is False
    assert "exceeds" in failing.payload["reason"]


def test_relative_comparison_uses_relative_error_and_uncertainty():
    passing = compare(
        "relative", 10.0, 10.5,
        comparison_overrides={"tolerance": 0.06},
        local_uncertainty=0.1,
    )
    failing = compare(
        "relative", 10.0, 10.51,
        comparison_overrides={"tolerance": 0.06},
        local_uncertainty=0.1,
    )

    assert passing.payload["matched"] is True
    assert passing.payload["error"] == pytest.approx(0.05)
    assert failing.payload["matched"] is False


@pytest.mark.parametrize(
    ("kind", "literature", "candidate", "tolerance"),
    [
        ("absolute", -1e308, 1e308, 0.0),
        ("relative", 5e-324, 1e308, 0.0),
    ],
)
def test_out_of_float_range_exact_errors_use_json_safe_decimal_diagnostics(
    kind, literature, candidate, tolerance
):
    result = compare(
        kind,
        literature,
        candidate,
        comparison_overrides={"tolerance": tolerance},
    )

    assert result.payload["matched"] is False
    assert isinstance(result.payload["error"], str)
    assert "inf" not in result.payload["error"].lower()
    assert "inf" not in result.payload["reason"].lower()
    assert json.loads(canonical_json_bytes(result))["payload"]["error"] == result.payload["error"]


def test_relative_zero_fails_closed_without_absolute_fallback():
    result = compare(
        "relative", 0.0, 0.0,
        comparison_overrides={"tolerance": 0.01},
    )

    assert result.payload["matched"] is False
    assert result.payload["error"] is None
    assert "zero" in result.payload["reason"]


def test_relative_zero_uses_conservative_absolute_tolerance_fallback():
    passing = compare(
        "relative", 0.0, 0.04,
        comparison_overrides={"tolerance": 0.01, "absolute_tolerance": 0.05},
        local_uncertainty=0.01,
    )
    failing = compare(
        "relative", 0.0, 0.041,
        comparison_overrides={"tolerance": 0.01, "absolute_tolerance": 0.05},
        local_uncertainty=0.01,
    )

    assert passing.payload["matched"] is True
    assert passing.payload["error"] == pytest.approx(0.04)
    assert passing.payload["tolerance"] == 0.05
    assert "fallback" in passing.payload["reason"]
    assert failing.payload["matched"] is False


@pytest.mark.parametrize(
    ("candidate", "matched"),
    [(1.0, False), (1.0001, True), (2.9999, True), (3.0, True)],
)
def test_interval_comparison_enforces_endpoint_policy(candidate, matched):
    interval = {
        "lower": 1.0,
        "upper": 3.0,
        "lower_inclusive": False,
        "upper_inclusive": True,
    }

    result = compare("interval", interval, candidate)

    assert result.payload["matched"] is matched
    assert "interval" in result.payload["reason"]


def test_interval_comparison_rejects_malformed_intervals():
    bad_intervals = [
        {"lower": 2, "upper": 1, "lower_inclusive": True, "upper_inclusive": True},
        {"lower": 1, "upper": 2, "lower_inclusive": 1, "upper_inclusive": True},
        {"lower": 1, "upper": 2, "lower_inclusive": True},
        {"lower": 1, "upper": 2, "lower_inclusive": True, "upper_inclusive": True, "extra": 3},
    ]

    for interval in bad_intervals:
        with pytest.raises(ObservableComparisonError, match="interval"):
            compare("interval", interval, 1.5)


def test_set_comparison_is_unordered_and_type_aware():
    assert compare("set", [1, "x", True], [True, "x", 1]).payload["matched"] is True
    result = compare("set", [1], [1.0])

    assert result.payload["matched"] is False
    assert "missing" in result.payload["reason"]
    assert "extra" in result.payload["reason"]


@pytest.mark.parametrize(
    "operand",
    [[1, 1], [True, True], [[1]], [{"nested": 1}], "abc"],
)
def test_set_comparison_rejects_duplicates_nested_values_and_non_collections(operand):
    with pytest.raises(ObservableComparisonError, match="set"):
        compare("set", operand, [1, 2])


def test_sequence_comparison_is_ordered_type_aware_and_reports_length():
    assert compare("sequence", [1, "x", False], [1, "x", False]).payload["matched"] is True
    mismatch = compare("sequence", [1, 2], [2, 1])
    length = compare("sequence", [1, 2], [1])

    assert mismatch.payload["matched"] is False
    assert "index 0" in mismatch.payload["reason"]
    assert length.payload["matched"] is False
    assert "length" in length.payload["reason"]
    with pytest.raises(ObservableComparisonError, match="sequence"):
        compare("sequence", "ab", "ab")


def test_recursive_json_equality_ignores_container_implementations_only():
    literature = [{"values": [True, 2.0]}]
    candidate = (MappingProxyType({"values": (True, 2.0)}),)

    assert compare("sequence", literature, candidate).payload["matched"] is True
    assert compare(
        "typed_claim",
        {"result": {"values": [True, 2.0]}},
        MappingProxyType({"result": MappingProxyType({"values": (True, 2.0)})}),
    ).payload["matched"] is True
    assert compare("sequence", [[True]], ((1,),)).payload["matched"] is False


def test_typed_claim_requires_exact_keys_and_recursive_type_aware_values():
    claim = {"phase": "Haldane", "degeneracy": 4, "flags": {"gapped": True}}
    assert compare("typed_claim", claim, dict(claim)).payload["matched"] is True

    result = compare(
        "typed_claim",
        claim,
        {"phase": "Haldane", "degeneracy": 4.0, "extra": None},
    )

    assert result.payload["matched"] is False
    assert "missing fields: flags" in result.payload["reason"]
    assert "extra fields: extra" in result.payload["reason"]
    assert "mismatched fields: degeneracy" in result.payload["reason"]


def test_typed_claim_value_and_units_fields_are_claim_content_not_an_envelope():
    claim = {"value": "Haldane", "units": "phase_label"}

    assert compare("typed_claim", claim, dict(claim)).payload["matched"] is True
    mismatch = compare(
        "typed_claim",
        claim,
        {"value": "trivial", "units": "phase_label"},
    )

    assert mismatch.payload["matched"] is False
    assert "mismatched fields: value" in mismatch.payload["reason"]


@pytest.mark.parametrize("operand", [[], "claim", {1: "bad"}, {"bad": object()}])
def test_typed_claim_rejects_malformed_claims(operand):
    with pytest.raises(ObservableComparisonError, match="typed claim"):
        compare("typed_claim", operand, {"ok": True})


def test_enveloped_operands_require_matching_nonempty_units_and_preserve_operands():
    literature = {"value": 1.0, "units": "eV"}
    candidate = {"value": 1.01, "units": "eV"}
    result = compare(
        "absolute", literature, candidate,
        comparison_overrides={"tolerance": 0.02},
    )

    assert result.payload["original_literature_operand"] == literature
    assert result.payload["original_candidate_operand"] == candidate
    assert result.payload["literature_value"] == 1.0
    assert result.payload["candidate_value"] == 1.01
    assert result.payload["units"] == "eV"
    assert result.payload["matched"] is True


def test_unit_mismatch_is_a_failed_trace_not_malformed_data():
    result = compare(
        "absolute",
        {"value": 1.0, "units": "eV"},
        {"value": 1.0, "units": "meV"},
        comparison_overrides={"tolerance": 0.0},
    )

    assert result.payload["matched"] is False
    assert result.payload["units"] == {"literature": "eV", "candidate": "meV"}
    assert "unit mismatch" in result.payload["reason"]


@pytest.mark.parametrize(
    ("kind", "literature_value", "candidate_value", "comparison_overrides"),
    [
        ("exact", [1], [1], {}),
        ("absolute", "bad", 1.0, {"tolerance": 0.0}),
        ("relative", 1.0, "bad", {"tolerance": 0.0}),
        ("interval", {"lower": 0}, 0, {}),
        ("set", [{"nested": 1}], [1], {}),
        ("sequence", "bad", ["bad"], {}),
        ("typed_claim", {"bad": object()}, {"ok": True}, {}),
    ],
)
def test_unit_mismatch_does_not_hide_kind_specific_malformed_operands(
    kind, literature_value, candidate_value, comparison_overrides
):
    with pytest.raises(ObservableComparisonError):
        compare(
            kind,
            {"value": literature_value, "units": "eV"},
            {"value": candidate_value, "units": "meV"},
            comparison_overrides=comparison_overrides,
        )


@pytest.mark.parametrize(
    ("literature", "candidate"),
    [
        ({"value": 1, "units": "eV"}, 1),
        ({"value": 1}, {"value": 1, "units": "eV"}),
        ({"value": 1, "units": ""}, {"value": 1, "units": ""}),
        ({"value": 1, "units": "  "}, {"value": 1, "units": "  "}),
        ({"value": 1, "units": "eV", "extra": True}, {"value": 1, "units": "eV"}),
    ],
)
def test_malformed_or_one_sided_envelopes_raise(literature, candidate):
    with pytest.raises(ObservableComparisonError, match="envelope"):
        compare("exact", literature, candidate)


@pytest.mark.parametrize(
    ("comparison", "message"),
    [
        ({}, "kind"),
        ({"kind": "unknown"}, "unsupported"),
        ({"kind": "exact", "tolerance": 1}, "config"),
        ({"kind": "absolute"}, "tolerance"),
        ({"kind": "relative", "tolerance": 0.1, "extra": 1}, "config"),
        ({"kind": "interval", "absolute_tolerance": 1}, "config"),
    ],
)
def test_comparison_config_is_closed_and_requires_kind_specific_fields(comparison, message):
    with pytest.raises(ObservableComparisonError, match=message):
        compare_observables(
            benchmark_name="haldane_gap_reference",
            comparison=comparison,
            literature_operand=1,
            candidate_operand=1,
        )


@pytest.mark.parametrize("value", [-1, math.inf, -math.inf, math.nan, True, "0.1"])
def test_tolerances_and_uncertainty_must_be_finite_nonnegative_numbers(value):
    with pytest.raises(ObservableComparisonError, match="tolerance"):
        compare("absolute", 1.0, 1.0, comparison_overrides={"tolerance": value})
    with pytest.raises(ObservableComparisonError, match="uncertainty"):
        compare(
            "absolute", 1.0, 1.0,
            comparison_overrides={"tolerance": 0.1},
            local_uncertainty=value,
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "1"])
def test_numeric_comparators_reject_nonfinite_and_nonnumeric_operands(value):
    with pytest.raises(ObservableComparisonError, match="numeric"):
        compare("absolute", value, 1.0, comparison_overrides={"tolerance": 0.1})
    with pytest.raises(ObservableComparisonError, match="numeric"):
        compare("interval", {"lower": 0, "upper": 2, "lower_inclusive": True, "upper_inclusive": True}, value)


def test_numeric_comparators_safely_support_arbitrary_size_json_integers():
    huge = 10**1000

    absolute = compare(
        "absolute",
        huge,
        huge,
        comparison_overrides={"tolerance": huge},
        local_uncertainty=huge,
    )
    interval = compare(
        "interval",
        {
            "lower": -huge,
            "upper": huge,
            "lower_inclusive": True,
            "upper_inclusive": True,
        },
        0,
    )

    assert absolute.payload["matched"] is True
    assert interval.payload["matched"] is True


def test_numeric_integer_conversion_failures_are_comparison_errors():
    class UnrenderableInt(int):
        def __str__(self):
            raise OverflowError("integer cannot be rendered")

    unrenderable = UnrenderableInt(1)
    requests = [
        ("absolute", unrenderable, 0, {"tolerance": 0}, None),
        ("absolute", 0, 0, {"tolerance": unrenderable}, None),
        ("absolute", 0, 0, {"tolerance": 0}, unrenderable),
        (
            "interval",
            {
                "lower": unrenderable,
                "upper": unrenderable,
                "lower_inclusive": True,
                "upper_inclusive": True,
            },
            0,
            {},
            None,
        ),
    ]

    for kind, literature, candidate, comparison_overrides, uncertainty in requests:
        with pytest.raises(ObservableComparisonError):
            compare(
                kind,
                literature,
                candidate,
                comparison_overrides=comparison_overrides,
                local_uncertainty=uncertainty,
            )


def test_local_uncertainty_is_rejected_for_non_numeric_comparators():
    with pytest.raises(ObservableComparisonError, match="uncertainty"):
        compare("exact", 1, 1, local_uncertainty=0.0)


def test_tolerance_boundary_rejects_a_genuinely_larger_error():
    result = compare(
        "absolute",
        0.0,
        1.0000000000005,
        comparison_overrides={"tolerance": 1.0},
    )

    assert result.payload["matched"] is False


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_exact_comparison_rejects_nonfinite_numbers(value):
    with pytest.raises(ObservableComparisonError, match="non-finite"):
        compare("exact", value, value)


def test_invalid_benchmark_name_is_a_comparison_request_error():
    with pytest.raises(ObservableComparisonError, match="benchmark_name"):
        compare_observables(
            benchmark_name="bad/name",
            comparison={"kind": "exact"},
            literature_operand=1,
            candidate_operand=1,
        )


def test_comparison_trace_payload_is_complete_immutable_and_canonical_serializable():
    comparison = {"kind": "absolute", "tolerance": 0.2}
    result = compare_observables(
        benchmark_name="haldane_gap_reference",
        comparison=comparison,
        literature_operand=1.0,
        candidate_operand=1.1,
        local_uncertainty=0.01,
    )

    assert isinstance(result, ComparisonTrace)
    assert result.payload == {
        "original_literature_operand": 1.0,
        "original_candidate_operand": 1.1,
        "literature_value": 1.0,
        "candidate_value": 1.1,
        "units": None,
        "comparison": comparison,
        "error": pytest.approx(0.1),
        "tolerance": 0.2,
        "local_uncertainty": 0.01,
        "matched": True,
        "reason": (
            "absolute error 0.1 plus local uncertainty 0.01 "
            "is within tolerance 0.2"
        ),
    }
    with pytest.raises(TypeError):
        result.payload["matched"] = False
    assert json.loads(canonical_json_bytes(result))["payload"]["matched"] is True


def test_pre_run_bijection_reports_duplicates_missing_and_orphans_together():
    records = [record("a"), record("a"), record("orphan")]
    with pytest.raises(EvidenceSchemaError) as caught:
        validate_pre_run_bijection(["a", "a", "missing"], records)

    message = str(caught.value)
    assert "duplicate registry names: a" in message
    assert "duplicate evidence record names: a" in message
    assert "missing evidence records: missing" in message
    assert "orphan evidence records: orphan" in message


def test_pre_run_bijection_accepts_exact_names_in_any_order():
    validate_pre_run_bijection(["a", "b"], [record("b"), record("a")])


@pytest.mark.parametrize(
    "names",
    ["ab", b"ab", {"a": 1}, {"a", "b"}, frozenset({"a", "b"})],
)
def test_pre_run_bijection_rejects_non_ordered_name_collections(names):
    with pytest.raises(EvidenceSchemaError, match="registry_names"):
        validate_pre_run_bijection(names, [record("a"), record("b")])


def test_pre_run_bijection_accepts_ordered_generators_and_keeps_duplicates():
    names = (name for name in ["a", "a"])
    with pytest.raises(EvidenceSchemaError, match="duplicate registry names: a"):
        validate_pre_run_bijection(names, [record("a"), record("a")])


def test_post_run_bijection_checks_outcomes_and_every_report_artifact():
    outcomes = [AuditOutcome("a", {}), AuditOutcome("a", {}), AuditOutcome("orphan", {})]
    reports = {
        "csv": ["a", "a"],
        "markdown": ["a", "report_orphan"],
        "pdf": ["a"],
    }
    with pytest.raises(EvidenceSchemaError) as caught:
        validate_post_run_bijection(["a", "missing"], outcomes, reports)

    message = str(caught.value)
    assert "duplicate outcome names: a" in message
    assert "missing outcomes: missing" in message
    assert "orphan outcomes: orphan" in message
    assert "duplicate csv report names: a" in message
    assert "missing csv report names: missing" in message
    assert "missing markdown report names: missing" in message
    assert "orphan markdown report names: report_orphan" in message


def test_post_run_bijection_accepts_exact_names_for_all_artifacts():
    outcomes = [AuditOutcome("b", {}), AuditOutcome("a", {})]
    validate_post_run_bijection(
        ["a", "b"],
        outcomes,
        {
            "csv": ["a", "b"],
            "markdown": ["b", "a"],
            "pdf": ["a", "b"],
        },
    )


@pytest.mark.parametrize(
    "reports",
    [
        {},
        {"csv": ["a"], "markdown": ["a"]},
        {"csv": ["a"], "markdown": ["a"], "pdf": ["a"], "json": ["a"]},
        {"csv": ["a"], "markdown": ["a"], "pdf": ["a"], 1: ["a"]},
    ],
)
def test_post_run_bijection_requires_exact_report_artifacts(reports):
    with pytest.raises(EvidenceSchemaError, match="report artifacts"):
        validate_post_run_bijection(["a"], [AuditOutcome("a", {})], reports)


@pytest.mark.parametrize(
    "names",
    ["ab", b"ab", {"a": 1}, {"a", "b"}, frozenset({"a", "b"})],
)
def test_post_run_bijection_rejects_non_ordered_report_name_collections(names):
    reports = {"csv": names, "markdown": ["a", "b"], "pdf": ["a", "b"]}
    with pytest.raises(EvidenceSchemaError, match="csv report names"):
        validate_post_run_bijection(
            ["a", "b"], [AuditOutcome("a", {}), AuditOutcome("b", {})], reports
        )
