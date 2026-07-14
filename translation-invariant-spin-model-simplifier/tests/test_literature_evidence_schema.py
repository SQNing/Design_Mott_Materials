import dataclasses
import json
import math
import sys
from pathlib import Path

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
        "normalization": {"kind": "ratio", "rules": {"denominator": "J"}},
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
    ["divide by J", {"description": "divide by J"}, {"kind": "ratio"}, {"rules": {"by": "J"}}],
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
        ("rules", {"denominator": "J"}),
        ("executable", {"callable": "validation.normalizers:divide"}),
        ("fields", ["gap", "J"]),
        ("operations", [{"operator": "divide", "operands": ["gap", "J"]}]),
    ],
)
def test_normalization_accepts_nonempty_machine_readable_rule_content(rule_key, content):
    item = record(normalization={"kind": "ratio", rule_key: content})

    assert item.normalization[rule_key]


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


def test_post_run_bijection_checks_outcomes_and_every_report_artifact():
    outcomes = [AuditOutcome("a", {}), AuditOutcome("a", {}), AuditOutcome("orphan", {})]
    reports = {
        "csv": ["a", "a"],
        "markdown": ["a", "report_orphan"],
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
        ["a", "b"], outcomes, {"csv": ["a", "b"], "markdown": ["b", "a"]}
    )
