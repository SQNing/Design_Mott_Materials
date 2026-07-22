"""Runtime evidence extraction and comparison for literature benchmarks."""

from collections.abc import Mapping, Sequence
from pathlib import Path
import json
import math
import re

from validation.literature_evidence_inventory import load_and_validate_inventory
from validation.literature_evidence_sources import load_verified_source
from validation import literature_spin_model_benchmarks as benchmark_functions


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "source-cache"


class RuntimeEvidenceError(ValueError):
    """Raised when source text cannot establish the registered claim."""


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_string_sequence(value, *, unique=False):
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or not all(_is_nonempty_string(item) for item in value)
    ):
        return False
    return not unique or len(value) == len(set(value))


def _is_valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _contains_nonfinite(value):
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, Mapping):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_nonfinite(item) for item in value)
    return False


def _is_valid_operand(operand, selector_fields):
    if (
        not isinstance(operand, Mapping)
        or not operand
        or set(operand) != set(selector_fields)
        or _contains_nonfinite(operand)
    ):
        return False
    try:
        json.dumps(operand, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _exact_json_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, Sequence) and not isinstance(left, (str, bytes)):
        return len(left) == len(right) and all(
            _exact_json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _is_valid_text_spans(value):
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
    ):
        return False
    for span in value:
        if (
            not isinstance(span, Sequence)
            or isinstance(span, (str, bytes))
            or len(span) != 2
        ):
            return False
        start, end = span
        if type(start) is not int or type(end) is not int or start < 0 or start >= end:
            return False
    return True


def _is_valid_extraction_trace(trace, benchmark_name, source_sha256):
    return (
        isinstance(trace, Mapping)
        and trace.get("benchmark_name") == benchmark_name
        and trace.get("source_sha256") == source_sha256
        and trace.get("coordinate_space")
        == "whitespace_normalized_extracted_text"
        and _is_nonempty_string(trace.get("parser"))
        and _is_nonempty_string_sequence(trace.get("matched_anchors"))
        and _is_valid_text_spans(trace.get("text_spans"))
    )


def structurally_validate_runtime_evidence_bundle(benchmark_name, runtime_bundle):
    """Return a strict category for a well-formed bundle, without proving provenance.

    This validator checks internal structure and equality only. A caller must separately
    establish that the bundle came from the authoritative cache-backed collector.
    """

    if not isinstance(runtime_bundle, Mapping):
        return None
    record = runtime_bundle.get("runtime_evidence_record")
    if not isinstance(record, Mapping):
        return None
    if record.get("benchmark_name") != benchmark_name:
        return None
    if not _is_nonempty_string(record.get("source_id")):
        return None
    source_sha256 = record.get("source_sha256")
    if not _is_valid_sha256(source_sha256):
        return None
    selector = record.get("registry_selector")
    if not isinstance(selector, Mapping):
        return None
    selector_path = selector.get("path")
    selector_fields = selector.get("fields")
    if not _is_nonempty_string_sequence(selector_path):
        return None
    if not _is_nonempty_string_sequence(selector_fields, unique=True):
        return None
    source_operand = record.get("source_operand")
    registry_operand = record.get("registry_operand")
    if not _is_valid_operand(source_operand, selector_fields):
        return None
    if not _is_valid_operand(registry_operand, selector_fields):
        return None
    comparison = record.get("comparison")
    if (
        not isinstance(comparison, Mapping)
        or comparison.get("kind") != "exact_field_map"
        or comparison.get("matched") is not True
    ):
        return None
    if not _exact_json_equal(source_operand, registry_operand):
        return None
    mode = record.get("evidence_mode")
    if mode not in {"local_recompute", "local_source_parse"}:
        return None
    extraction_trace = runtime_bundle.get("extraction_trace")
    if not _is_valid_extraction_trace(
        extraction_trace, benchmark_name, source_sha256
    ):
        return None
    if mode == "local_recompute":
        computed_operand = record.get("computed_operand")
        if not _is_valid_operand(computed_operand, selector_fields):
            return None
        if not _exact_json_equal(computed_operand, source_operand):
            return None
        execution_trace = runtime_bundle.get("execution_trace")
        if not isinstance(execution_trace, Mapping):
            return None
        if execution_trace.get("benchmark_name") != benchmark_name:
            return None
        if execution_trace.get("source_sha256") != source_sha256:
            return None
        if not _is_nonempty_string(execution_trace.get("adapter")):
            return None
        if not isinstance(execution_trace.get("adapter_parameters"), Mapping):
            return None
        trace_computed_operand = execution_trace.get("computed_operand")
        if not _is_valid_operand(trace_computed_operand, selector_fields):
            return None
        if not _exact_json_equal(trace_computed_operand, computed_operand):
            return None
    return {
        "local_recompute": "strict_local_recomputed",
        "local_source_parse": "strict_local_source_parsed",
    }[mode]


def parse_cri3_ferromagnetic_order(source_text):
    """Extract the CrI3 honeycomb ferromagnetic-order claim from source text."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("CrI3 source claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    anchor_patterns = (
        ("honeycomb network", r"honeycomb network"),
        (
            "long range ferromagnetic order develops below TC = 61 K",
            r"long range ferromagnetic order develops.{0,120}?below T\s*C\s*=\s*61 K",
        ),
    )
    matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for _, pattern in anchor_patterns
    ]
    if any(match is None for match in matches):
        raise RuntimeEvidenceError(
            "CrI3 source claim must contain the honeycomb structure and "
            "61 K long-range ferromagnetic-order statements"
        )
    return (
        {"ferromagnetic_order": True},
        {
            "parser": "parse_cri3_ferromagnetic_order",
            "matched_anchors": [label for label, _ in anchor_patterns],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_yang_yang_xxx_ground_state_energy(source_text):
    """Parse Eq. (31c) using the locked Yang-Yang PDF's font mapping."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Yang-Yang Eq. (31c) requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    pattern = re.compile(
        r"=\s*-\s*,\s*'\s*[\-\N{MINUS SIGN}\N{EN DASH}\N{EM DASH}]\s*"
        r"ln\s*2\s*;.{0,100}?\(31c\)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(normalized)
    if match is None:
        raise RuntimeEvidenceError(
            "Yang-Yang Eq. (31c) must contain the locked one-quarter glyph, ln2, "
            "and equation label"
        )
    return (
        {"energy_per_site": 0.25 - math.log(2.0)},
        {
            "parser": "parse_yang_yang_xxx_ground_state_energy",
            "equation": "31c",
            "normalization": "yang_yang_1966_fraction_glyph_one_quarter",
            "matched_anchors": ["locked fraction glyph", "ln2", "(31c)"],
            "text_spans": [[match.start(), match.end()]],
        },
    )


def parse_taylor_ising_correlation_length(source_text):
    """Derive the Ising-chain correlation length from Taylor's Eq. (5)."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Taylor Ising Eq. (5) requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    correlation_match = re.search(
        r"(?:<\s*s_i\s+s_i\+l\s*>|hsi\s+si\+l\s+i)\s*=.{0,180}?\(5\)",
        normalized,
        flags=re.IGNORECASE,
    )
    decay_match = re.search(
        r"equal to\s+tanh(?:\^\s*l|l)\s*\(\s*J\s*(?:beta|β)\s*\)",
        normalized,
        flags=re.IGNORECASE,
    )
    if correlation_match is None or decay_match is None:
        raise RuntimeEvidenceError(
            "Taylor Ising Eq. (5) must define the two-point correlation and "
            "state its tanh(J beta) to the l-th-power decay"
        )
    return (
        {
            "correlation_length_beta_1_j_1": -1.0
            / math.log(math.tanh(1.0))
        },
        {
            "parser": "parse_taylor_ising_correlation_length",
            "equation": "5",
            "derivation": (
                "C(l)=tanh(J beta)^l=exp(-l/xi) => "
                "xi=-1/log(tanh(J beta)); beta=J=1"
            ),
            "matched_anchors": [
                "two-point correlation definition (5)",
                "equal to tanh^l(J beta)",
            ],
            "text_spans": [
                [correlation_match.start(), correlation_match.end()],
                [decay_match.start(), decay_match.end()],
            ],
        },
    )


def parse_tasaki_lsm_half_integer_constraint(source_text):
    """Extract Tasaki's half-odd-integer unique-ground-state constraint."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Tasaki LSM claim requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    claim_match = re.search(
        r"one-dimensional spin system with a half-odd-integer S has gapless "
        r"excitations in the infinite volume limit provided that the ground "
        r"state is unique",
        normalized,
        flags=re.IGNORECASE,
    )
    if claim_match is None:
        raise RuntimeEvidenceError(
            "Tasaki LSM claim must contain one-dimensionality, half-odd-integer "
            "spin, gapless excitations, the infinite-volume limit, and a unique "
            "ground state"
        )
    return (
        {"unique_ground_state_implies_gapless_excitations": True},
        {
            "parser": "parse_tasaki_lsm_half_integer_constraint",
            "matched_anchors": [
                "one-dimensional half-odd-integer spin",
                "unique ground state implies gapless excitations",
                "infinite volume limit",
            ],
            "text_spans": [[claim_match.start(), claim_match.end()]],
        },
    )


def _select_registry_operand(entry, selector):
    value = entry
    for component in selector["path"]:
        if not isinstance(value, Mapping) or component not in value:
            raise RuntimeEvidenceError(
                f"registry selector cannot resolve component {component}"
            )
        value = value[component]
    if not isinstance(value, Mapping):
        raise RuntimeEvidenceError("registry selector path does not resolve a mapping")
    fields = selector["fields"]
    missing = [field for field in fields if field not in value]
    if missing:
        raise RuntimeEvidenceError(
            f"registry selector cannot resolve field {missing[0]}"
        )
    return {field: value[field] for field in fields}


def _narrow_registry_selector(selector, fields=None):
    original_fields = tuple(selector["fields"])
    selected_fields = original_fields if fields is None else tuple(fields)
    if (
        not _is_nonempty_string_sequence(selected_fields, unique=True)
        or not set(selected_fields).issubset(original_fields)
    ):
        raise RuntimeEvidenceError(
            "runtime route fields must be a nonempty subset of registered selector fields"
        )
    return {
        "path": list(selector["path"]),
        "fields": list(selected_fields),
    }


def collect_runtime_evidence(registry_entries, *, cache_root=DEFAULT_CACHE_ROOT):
    """Execute supported strict evidence routes against the local source cache."""

    inventory = load_and_validate_inventory(registry_entries=registry_entries)
    source_by_id = {source["source_id"]: source for source in inventory.source_index}
    route_by_id = {
        route["source_id"]: route for route in inventory.source_provisioning
    }
    record_by_name = {record.benchmark_name: record for record in inventory.records}
    entry_by_name = {entry["name"]: entry for entry in registry_entries}
    evidence = {}
    specs = (
        {
            "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
            "mode": "local_source_parse",
            "parser": parse_cri3_ferromagnetic_order,
        },
        {
            "benchmark_name": "xxx_spin_half_chain_bethe_ground_state",
            "mode": "local_recompute",
            "parser": parse_yang_yang_xxx_ground_state_energy,
            "adapter": benchmark_functions.xxx_spin_half_chain_bethe_energy_per_site,
            "adapter_parameters": {"exchange": 1.0},
            "output_field": "energy_per_site",
        },
        {
            "benchmark_name": "one_dimensional_classical_ising_correlation_length",
            "mode": "local_recompute",
            "parser": parse_taylor_ising_correlation_length,
            "registry_fields": ("correlation_length_beta_1_j_1",),
            "adapter": benchmark_functions.classical_ising_chain_correlation_length,
            "adapter_parameters": {"beta": 1.0, "exchange": 1.0},
            "output_field": "correlation_length_beta_1_j_1",
        },
        {
            "benchmark_name": "lieb_schultz_mattis_half_integer_constraint",
            "mode": "local_source_parse",
            "parser": parse_tasaki_lsm_half_integer_constraint,
        },
    )
    for spec in specs:
        benchmark_name = spec["benchmark_name"]
        record = record_by_name[benchmark_name]
        source_dir = Path(cache_root) / record.source_id
        if not source_dir.is_dir():
            continue
        verified = load_verified_source(
            source_dir,
            expected_source=source_by_id[record.source_id],
            provisioning_route=route_by_id[record.source_id],
        )
        source_operand, extraction_trace = spec["parser"](
            verified.extracted_text
        )
        selector = _narrow_registry_selector(
            record.registry_selector, spec.get("registry_fields")
        )
        registry_operand = _select_registry_operand(
            entry_by_name[benchmark_name], selector
        )
        runtime_record = {
            "benchmark_name": benchmark_name,
            "evidence_mode": spec["mode"],
            "source_id": record.source_id,
            "source_sha256": verified.payload_sha256,
            "registry_selector": {
                "path": selector["path"],
                "fields": selector["fields"],
            },
            "source_operand": source_operand,
            "registry_operand": registry_operand,
        }
        bundle = {
            "extraction_trace": {
                "benchmark_name": benchmark_name,
                "source_sha256": verified.payload_sha256,
                "coordinate_space": "whitespace_normalized_extracted_text",
                **extraction_trace,
            },
        }
        operands = [source_operand, registry_operand]
        if spec["mode"] == "local_recompute":
            parameters = spec["adapter_parameters"]
            computed_operand = {
                spec["output_field"]: spec["adapter"](**parameters)
            }
            runtime_record["computed_operand"] = computed_operand
            operands.append(computed_operand)
            bundle["execution_trace"] = {
                "benchmark_name": benchmark_name,
                "source_sha256": verified.payload_sha256,
                "adapter": spec["adapter"].__name__,
                "adapter_parameters": dict(parameters),
                "computed_operand": computed_operand,
            }
        runtime_record["comparison"] = {
            "kind": "exact_field_map",
            "matched": all(
                _exact_json_equal(operand, operands[0])
                for operand in operands[1:]
            ),
        }
        bundle["runtime_evidence_record"] = runtime_record
        evidence[benchmark_name] = bundle
    return evidence


def structurally_validate_runtime_evidence_coverage(
    registry_entries, evidence_by_name
):
    """Summarize exact-name structural coverage without establishing provenance."""

    registry_names = {entry["name"] for entry in registry_entries}
    evidence_names = (
        set(evidence_by_name) if isinstance(evidence_by_name, Mapping) else set()
    )
    extra_names = sorted(evidence_names - registry_names)
    missing_names = sorted(registry_names - evidence_names)
    supported_names = []
    invalid_names = []
    for benchmark_name in sorted(registry_names & evidence_names):
        category = structurally_validate_runtime_evidence_bundle(
            benchmark_name, evidence_by_name[benchmark_name]
        )
        if category is None:
            invalid_names.append(benchmark_name)
        else:
            supported_names.append(benchmark_name)
    complete = not missing_names and not extra_names and not invalid_names
    return {
        "supported_names": supported_names,
        "missing_names": missing_names,
        "extra_names": extra_names,
        "invalid_names": invalid_names,
        "supported": len(supported_names),
        "missing": len(missing_names),
        "extra": len(extra_names),
        "invalid": len(invalid_names),
        "complete": complete,
    }


def collect_runtime_evidence_coverage(
    registry_entries, *, cache_root=DEFAULT_CACHE_ROOT
):
    """Collect authoritative local evidence and report exact registry coverage."""

    evidence = collect_runtime_evidence(registry_entries, cache_root=cache_root)
    return structurally_validate_runtime_evidence_coverage(
        registry_entries, evidence
    )


def assert_complete_runtime_evidence(
    registry_entries, *, cache_root=DEFAULT_CACHE_ROOT
):
    """Raise unless authoritative runtime evidence exactly covers the registry."""

    coverage = collect_runtime_evidence_coverage(
        registry_entries, cache_root=cache_root
    )
    if not coverage["complete"]:
        raise RuntimeEvidenceError(
            "runtime evidence incomplete: "
            f"{coverage['missing']} missing, {coverage['extra']} extra, "
            f"{coverage['invalid']} invalid"
        )
    return coverage
