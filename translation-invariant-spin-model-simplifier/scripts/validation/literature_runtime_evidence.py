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


def parse_onsager_square_ising_tc(source_text):
    """Derive the isotropic square-Ising critical temperature from Onsager."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Onsager critical condition requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    transition_match = re.search(
        r"order-disorder transition.{0,120}?temperature\s+T\s*=\s*T",
        normalized,
        flags=re.IGNORECASE,
    )
    condition_match = re.search(
        r"sinh\s*\(\s*2\s*J\s*/\s*kT[^)]*\)\s*"
        r"sinh\s*\(\s*2\s*J['′]?\s*/\s*kT[^)]*\)\s*=\s*1",
        normalized,
        flags=re.IGNORECASE,
    )
    if transition_match is None or condition_match is None:
        raise RuntimeEvidenceError(
            "Onsager critical condition must identify the order-disorder "
            "transition and sinh(2J/kTc) sinh(2J'/kTc) = 1"
        )
    return (
        {"tc_over_j": 2.0 / math.log(1.0 + math.sqrt(2.0))},
        {
            "parser": "parse_onsager_square_ising_tc",
            "derivation": (
                "J'=J and sinh(2J/kTc)^2=1 => "
                "Tc/J=2/log(1+sqrt(2)), with k=1"
            ),
            "matched_anchors": [
                "order-disorder transition temperature",
                "sinh(2J/kTc) sinh(2J'/kTc) = 1",
            ],
            "text_spans": [
                [transition_match.start(), transition_match.end()],
                [condition_match.start(), condition_match.end()],
            ],
        },
    )


def parse_dagotto_rice_strong_rung_limit(source_text):
    """Extract the decoupled two-leg-ladder rung spectrum."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Dagotto-Rice strong-rung limit requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    strong_rung_match = re.search(
        r"J['′]\s*(?:>>|≫)\s*J", normalized, flags=re.IGNORECASE
    )
    singlet_match = re.search(
        r"(?:-|−)\s*(?:3\s*/\s*4|3\s*4|4\s*3)\s*J['′].{0,80}?"
        r"energy of each rung singlet",
        normalized,
        flags=re.IGNORECASE,
    )
    triplet_match = re.search(
        r"isolated rung-triplet has an energy\s+J['′]\s+above the rung singlet",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        strong_rung_match is None
        or singlet_match is None
        or triplet_match is None
    ):
        raise RuntimeEvidenceError(
            "Dagotto-Rice strong-rung limit must state J' >> J, the -3J'/4 "
            "rung-singlet energy, and the J' triplet gap"
        )
    return (
        {"energy_per_rung": -0.75, "gap_to_triplet": 1.0},
        {
            "parser": "parse_dagotto_rice_strong_rung_limit",
            "derivation": (
                "Take the exact decoupled-rung endpoint Jleg=0, Jrung=1: "
                "Es=-3Jrung/4 and Et-Es=Jrung"
            ),
            "matched_anchors": [
                "J' much larger than J",
                "-3J'/4 energy of each rung singlet",
                "isolated rung triplet J' above singlet",
            ],
            "text_spans": [
                [strong_rung_match.start(), strong_rung_match.end()],
                [singlet_match.start(), singlet_match.end()],
                [triplet_match.start(), triplet_match.end()],
            ],
        },
    )


def parse_kitaev_exact_spin_liquid(source_text):
    """Extract the exact-solution and isotropic gapless-phase claims."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "Kitaev exact-solution claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    exact_match = re.search(
        r"exact solution is obtained by a reduction to free real fermions",
        normalized,
        flags=re.IGNORECASE,
    )
    phase_match = re.search(
        r"in phase B the fermions are gapless",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_match = re.search(
        r"symmetric case\s*\(\s*Jx\s*=\s*Jy\s*=\s*Jz\s*\)"
        r".{0,160}?zeros of the spectrum",
        normalized,
        flags=re.IGNORECASE,
    )
    if exact_match is None or phase_match is None or isotropic_match is None:
        raise RuntimeEvidenceError(
            "Kitaev exact-solution claim must identify the free-real-fermion "
            "solution, gapless phase B, and the symmetric isotropic point"
        )
    return (
        {
            "is_exactly_solvable": True,
            "isotropic_phase": "gapless_spin_liquid",
        },
        {
            "parser": "parse_kitaev_exact_spin_liquid",
            "matched_anchors": [
                "exact solution by free real fermions",
                "phase B fermions are gapless",
                "symmetric Jx=Jy=Jz spectrum zeros",
            ],
            "text_spans": [
                [exact_match.start(), exact_match.end()],
                [phase_match.start(), phase_match.end()],
                [isotropic_match.start(), isotropic_match.end()],
            ],
        },
    )


def parse_kitaev_gapless_triangle_condition(source_text):
    """Extract Kitaev's Eq. (33) gapless triangle criterion."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError("Kitaev gapless condition requires nonempty text")
    normalized = re.sub(r"\s+", " ", source_text).strip()
    prefix_match = re.search(
        r"solutions if and only if\s*\|Jx\s*\|\s*,\s*\|Jy\s*\|\s*,\s*\|Jz\s*\|"
        r"\s+satisfy the triangle inequalities",
        normalized,
        flags=re.IGNORECASE,
    )
    inequality_patterns = (
        r"\|Jx\s*\|\s*(?:<=|≤|6)\s*\|Jy\s*\|\s*\+\s*\|Jz\s*\|",
        r"\|Jy\s*\|\s*(?:<=|≤|6)\s*\|Jx\s*\|\s*\+\s*\|Jz\s*\|",
        r"\|Jz\s*\|\s*(?:<=|≤|6)\s*\|Jx\s*\|\s*\+\s*\|Jy\s*\|",
    )
    inequality_matches = [
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in inequality_patterns
    ]
    equation_match = re.search(r"\(33\)", normalized)
    phase_match = re.search(
        r"(?:phase B|marked by B).{0,80}?this phase is gapless",
        normalized,
        flags=re.IGNORECASE,
    )
    isotropic_match = re.search(
        r"symmetric case\s*\(\s*Jx\s*=\s*Jy\s*=\s*Jz\s*\)"
        r".{0,160}?zeros of the spectrum",
        normalized,
        flags=re.IGNORECASE,
    )
    if (
        prefix_match is None
        or any(match is None for match in inequality_matches)
        or equation_match is None
        or phase_match is None
        or isotropic_match is None
    ):
        raise RuntimeEvidenceError(
            "Kitaev gapless condition must contain all three Eq. (33) triangle "
            "inequalities, gapless phase B, and the symmetric isotropic point"
        )
    matches = [
        prefix_match,
        *inequality_matches,
        equation_match,
        phase_match,
        isotropic_match,
    ]
    return (
        {
            "gapless_condition": "triangle_inequalities",
            "isotropic_kitaev_point_gapless": True,
        },
        {
            "parser": "parse_kitaev_gapless_triangle_condition",
            "equation": "33",
            "matched_anchors": [
                "if and only if triangle inequalities",
                "three exchange triangle inequalities",
                "Eq. (33) gapless phase B",
                "symmetric Jx=Jy=Jz spectrum zeros",
            ],
            "text_spans": [[match.start(), match.end()] for match in matches],
        },
    )


def parse_kitaev_toric_code_degeneracy(source_text):
    """Derive the genus-one toric-code ground-state degeneracy."""

    if not isinstance(source_text, str) or not source_text.strip():
        raise RuntimeEvidenceError(
            "toric-code degeneracy claim requires nonempty text"
        )
    normalized = re.sub(r"\s+", " ", source_text).strip()
    torus_match = re.search(
        r"lattices on the torus and other 2-D surfaces",
        normalized,
        flags=re.IGNORECASE,
    )
    degeneracy_match = re.search(
        r"ground state.{0,120}?protected space.{0,80}?"
        r"4(?:\^\s*g|g)\s*-?fold degenerate,?\s*where g is the genus",
        normalized,
        flags=re.IGNORECASE,
    )
    if torus_match is None or degeneracy_match is None:
        raise RuntimeEvidenceError(
            "toric-code degeneracy claim must state the torus ground-state "
            "space is 4^g-fold degenerate with g the surface genus"
        )
    return (
        {"torus_ground_state_degeneracy": 4},
        {
            "parser": "parse_kitaev_toric_code_degeneracy",
            "derivation": "torus has genus g=1, so 4^g=4",
            "matched_anchors": [
                "lattices on the torus",
                "ground-state protected space is 4^g-fold degenerate",
                "g is the genus of the surface",
            ],
            "text_spans": [
                [torus_match.start(), torus_match.end()],
                [degeneracy_match.start(), degeneracy_match.end()],
            ],
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
        {
            "benchmark_name": "two_dimensional_square_ising_onsager_tc",
            "mode": "local_recompute",
            "parser": parse_onsager_square_ising_tc,
            "adapter": benchmark_functions.two_dimensional_ising_square_tc,
            "adapter_parameters": {"exchange": 1.0},
            "output_field": "tc_over_j",
        },
        {
            "benchmark_name": "two_leg_ladder_strong_rung_exact_limit",
            "mode": "local_recompute",
            "parser": parse_dagotto_rice_strong_rung_limit,
            "adapter": benchmark_functions.spin_ladder_strong_rung_gap_status,
            "adapter_parameters": {"j_rung": 1.0, "j_leg": 0.0},
            "output_fields": {
                "energy_per_rung": "rung_singlet_energy",
                "gap_to_triplet": "rung_gap",
            },
        },
        {
            "benchmark_name": "kitaev_honeycomb_exact_spin_liquid_limit",
            "mode": "local_source_parse",
            "parser": parse_kitaev_exact_spin_liquid,
        },
        {
            "benchmark_name": "kitaev_honeycomb_gapless_triangle_condition",
            "mode": "local_source_parse",
            "parser": parse_kitaev_gapless_triangle_condition,
        },
        {
            "benchmark_name": "square_toric_code_exact_topological_degeneracy",
            "mode": "local_recompute",
            "parser": parse_kitaev_toric_code_degeneracy,
            "adapter": benchmark_functions.toric_code_ground_state_degeneracy,
            "adapter_parameters": {"genus": 1},
            "output_field": "torus_ground_state_degeneracy",
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
            adapter_output = spec["adapter"](**parameters)
            if "output_fields" in spec:
                if not isinstance(adapter_output, Mapping):
                    raise RuntimeEvidenceError(
                        f"adapter for {benchmark_name} must return a mapping"
                    )
                missing_outputs = [
                    output_name
                    for output_name in spec["output_fields"].values()
                    if output_name not in adapter_output
                ]
                if missing_outputs:
                    raise RuntimeEvidenceError(
                        f"adapter for {benchmark_name} is missing output "
                        f"{missing_outputs[0]}"
                    )
                computed_operand = {
                    registry_field: adapter_output[output_name]
                    for registry_field, output_name in spec["output_fields"].items()
                }
            else:
                computed_operand = {spec["output_field"]: adapter_output}
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
