import sys
import csv
import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation import literature_reproduction_audit
from validation import literature_runtime_evidence
from validation.literature_reproduction_audit import build_literature_reproduction_audit
from validation.literature_reproduction_audit import (
    write_audit_csv,
    write_audit_markdown,
    write_remaining_strict_reproduction_gaps_markdown,
)
from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS
from validation import literature_spin_model_benchmarks
from validation.literature_runtime_evidence import (
    RuntimeEvidenceError,
    collect_runtime_evidence,
    parse_cri3_ferromagnetic_order,
    parse_yang_yang_xxx_ground_state_energy,
)


CR_I3_SOURCE_TEXT = """
In the chromium trihalides, Cr3+ ions are arranged in a honeycomb network.
Our magnetization and heat capacity measurements reveal long range
ferromagnetic order develops below TC = 61 K and evidence for strong
magnetic anisotropy developing upon cooling below TC.
"""

YANG_YANG_SOURCE_TEXT = """
Delta = -1,
f(Delta, 0) =-,' -ln2;                                      (31c)
Delta < -1,
"""

TAYLOR_ISING_SOURCE_TEXT = """
The two-point correlation function is
<s_i s_i+l> = (1 / Z_N) sum_(s_i) (s_i s_i+l) exp(-H beta). (5)
It is found in this situation to be equal to tanh^l(J beta).
"""

TASAKI_LSM_SOURCE_TEXT = """
By using the local twist version of the theorem, it was proved that a
one-dimensional spin system with a half-odd-integer S has gapless excitations
in the infinite volume limit provided that the ground state is unique.
"""

ONSAGER_SQUARE_ISING_SOURCE_TEXT = """
The two-way infinite crystal has an order-disorder transition at a
temperature T = Tc given by the condition
sinh(2 J/kTc) sinh(2 J'/kTc) = 1.
"""

DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT = """
The exchange coupling along the rungs J' is much larger than J along the
chains, J' >> J. The energy in this limit is approximately
Egs = -3/4 J' N, where N is the number of rungs and -3/4 J' the energy of
each rung singlet. An isolated rung-triplet has an energy J' above the rung
singlet.
"""

KITAEV_EXACT_SOLUTION_SOURCE_TEXT = """
The model has two phases (denoted by A and B). The exact solution is obtained
by a reduction to free real fermions. In phase B the fermions are gapless.
In the symmetric case (Jx = Jy = Jz) the zeros of the spectrum are given by
q = plus or minus q star.
"""

KITAEV_TRIANGLE_SOURCE_TEXT = """
The equation has solutions if and only if |Jx|, |Jy|, |Jz| satisfy the
triangle inequalities:
|Jx| <= |Jy| + |Jz|, |Jy| <= |Jx| + |Jz|, |Jz| <= |Jx| + |Jy|. (33)
The region defined by inequalities (33) is phase B; this phase is gapless.
In the symmetric case (Jx = Jy = Jz) the zeros of the spectrum are given by
q = plus or minus q star.
"""

SOURCE_SHA256 = "9ad3044b7528d53fd0aa3616eb2ab8190b196b3f46f9f0711e53d10be24815e0"
MISSING = object()
REQUIRED_RUNTIME_SOURCE_IDS = {
    "arxiv_1210a896b82f8e645da1",
    "doi_5ac1fc0c40596b19c09f",
    "doi_f31ef7e012b01a5ac71d",
    "doi_696bd9749ec01fc72d99",
    "doi_735636355d51385c61be",
    "doi_607b6dc8e2ebace9ef53",
    "doi_d3dec73b0de1021b7f2a",
}


def _require_runtime_cache():
    missing = sorted(
        source_id
        for source_id in REQUIRED_RUNTIME_SOURCE_IDS
        if not (literature_runtime_evidence.DEFAULT_CACHE_ROOT / source_id).is_dir()
    )
    if missing:
        pytest.skip(
            "provision source-cache directories before runtime integration: "
            + ", ".join(missing)
        )


def _runtime_source_parse_record(*, matched=True):
    return {
        "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
        "evidence_mode": "local_source_parse",
        "source_id": "doi_f31ef7e012b01a5ac71d",
        "source_sha256": SOURCE_SHA256,
        "registry_selector": {
            "path": ["standard_result"],
            "fields": ["ferromagnetic_order"],
        },
        "source_operand": {"ferromagnetic_order": True},
        "registry_operand": {"ferromagnetic_order": True},
        "comparison": {"kind": "exact_field_map", "matched": matched},
    }


def _extraction_trace():
    return {
        "benchmark_name": "cri3_honeycomb_ferromagnet_reference",
        "parser": "parse_cri3_ferromagnetic_order",
        "coordinate_space": "whitespace_normalized_extracted_text",
        "source_sha256": SOURCE_SHA256,
        "matched_anchors": [
            "honeycomb network",
            "long range ferromagnetic order develops below TC = 61 K",
        ],
        "text_spans": [[48, 65], [117, 174]],
    }


def test_cri3_parser_extracts_ferromagnetic_order_from_source_text():
    parsed, trace = parse_cri3_ferromagnetic_order(CR_I3_SOURCE_TEXT)

    assert parsed == {"ferromagnetic_order": True}
    assert trace["parser"] == "parse_cri3_ferromagnetic_order"
    assert trace["matched_anchors"] == [
        "honeycomb network",
        "long range ferromagnetic order develops below TC = 61 K",
    ]
    assert len(trace["text_spans"]) == 2


@pytest.mark.parametrize(
    "source_text",
    [
        CR_I3_SOURCE_TEXT.replace("honeycomb network", "layered network"),
        CR_I3_SOURCE_TEXT.replace("ferromagnetic order develops", "magnetic response develops"),
        CR_I3_SOURCE_TEXT.replace("61 K", "unknown temperature"),
    ],
)
def test_cri3_parser_fails_closed_when_source_claim_is_incomplete(source_text):
    with pytest.raises(RuntimeEvidenceError, match="CrI3 source claim"):
        parse_cri3_ferromagnetic_order(source_text)


def test_yang_yang_parser_normalizes_hashed_pdf_fraction_glyphs():
    parsed, trace = parse_yang_yang_xxx_ground_state_energy(
        YANG_YANG_SOURCE_TEXT
    )

    assert parsed["energy_per_site"] == pytest.approx(0.25 - 0.6931471805599453)
    assert trace["parser"] == "parse_yang_yang_xxx_ground_state_energy"
    assert trace["equation"] == "31c"
    assert trace["normalization"] == "yang_yang_1966_fraction_glyph_one_quarter"


@pytest.mark.parametrize(
    "source_text",
    [
        YANG_YANG_SOURCE_TEXT.replace("(31c)", "(31d)"),
        YANG_YANG_SOURCE_TEXT.replace("ln2", "ln3"),
        YANG_YANG_SOURCE_TEXT.replace("-,'", "unknown"),
    ],
)
def test_yang_yang_parser_fails_closed_without_complete_equation(source_text):
    with pytest.raises(RuntimeEvidenceError, match=r"Yang-Yang Eq. \(31c\)"):
        parse_yang_yang_xxx_ground_state_energy(source_text)


def test_taylor_ising_parser_derives_beta_one_correlation_length():
    parsed, trace = literature_runtime_evidence.parse_taylor_ising_correlation_length(
        TAYLOR_ISING_SOURCE_TEXT
    )

    assert parsed == {
        "correlation_length_beta_1_j_1": pytest.approx(
            -1.0 / literature_runtime_evidence.math.log(
                literature_runtime_evidence.math.tanh(1.0)
            )
        )
    }
    assert trace["parser"] == "parse_taylor_ising_correlation_length"
    assert trace["equation"] == "5"
    assert "exp(-l/xi)" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        TAYLOR_ISING_SOURCE_TEXT.replace("(5)", "(6)"),
        TAYLOR_ISING_SOURCE_TEXT.replace("<s_i s_i+l>", "observable"),
        TAYLOR_ISING_SOURCE_TEXT.replace("tanh^l", "tanh"),
        TAYLOR_ISING_SOURCE_TEXT.replace("J beta", "J gamma"),
    ],
)
def test_taylor_ising_parser_fails_closed_without_complete_equation(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Taylor Ising Eq. \\(5\\)"):
        literature_runtime_evidence.parse_taylor_ising_correlation_length(source_text)


def test_tasaki_lsm_parser_extracts_unique_ground_state_gaplessness_claim():
    parsed, trace = literature_runtime_evidence.parse_tasaki_lsm_half_integer_constraint(
        TASAKI_LSM_SOURCE_TEXT
    )

    assert parsed == {"unique_ground_state_implies_gapless_excitations": True}
    assert trace["parser"] == "parse_tasaki_lsm_half_integer_constraint"
    assert len(trace["text_spans"]) == 1


@pytest.mark.parametrize(
    "source_text",
    [
        TASAKI_LSM_SOURCE_TEXT.replace("one-dimensional", "two-dimensional"),
        TASAKI_LSM_SOURCE_TEXT.replace("half-odd-integer", "integer"),
        TASAKI_LSM_SOURCE_TEXT.replace("gapless excitations", "excitations"),
        TASAKI_LSM_SOURCE_TEXT.replace("infinite volume limit", "finite system"),
        TASAKI_LSM_SOURCE_TEXT.replace("ground state is unique", "ground state exists"),
    ],
)
def test_tasaki_lsm_parser_fails_closed_without_complete_theorem(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Tasaki LSM claim"):
        literature_runtime_evidence.parse_tasaki_lsm_half_integer_constraint(source_text)


def test_onsager_parser_derives_isotropic_square_ising_tc():
    parsed, trace = literature_runtime_evidence.parse_onsager_square_ising_tc(
        ONSAGER_SQUARE_ISING_SOURCE_TEXT
    )

    assert parsed == {
        "tc_over_j": pytest.approx(
            2.0
            / literature_runtime_evidence.math.log(
                1.0 + literature_runtime_evidence.math.sqrt(2.0)
            )
        )
    }
    assert trace["parser"] == "parse_onsager_square_ising_tc"
    assert "J'=J" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace(
            "order-disorder transition", "smooth crossover"
        ),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("sinh(2 J/kTc)", "cosh(2 J/kTc)"),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("sinh(2 J'/kTc)", "cosh(2 J'/kTc)"),
        ONSAGER_SQUARE_ISING_SOURCE_TEXT.replace("= 1", "= 2"),
    ],
)
def test_onsager_parser_fails_closed_without_transition_condition(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Onsager critical condition"):
        literature_runtime_evidence.parse_onsager_square_ising_tc(source_text)


def test_dagotto_rice_parser_extracts_exact_decoupled_rung_operands():
    parsed, trace = literature_runtime_evidence.parse_dagotto_rice_strong_rung_limit(
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT
    )

    assert parsed == {"energy_per_rung": -0.75, "gap_to_triplet": 1.0}
    assert trace["parser"] == "parse_dagotto_rice_strong_rung_limit"
    assert "Jleg=0" in trace["derivation"]


@pytest.mark.parametrize(
    "source_text",
    [
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("J' >> J", "J' = J"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("-3/4 J'", "-1/2 J'"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace("each rung singlet", "each rung"),
        DAGOTTO_RICE_STRONG_RUNG_SOURCE_TEXT.replace(
            "energy J' above", "energy 2J' above"
        ),
    ],
)
def test_dagotto_rice_parser_fails_closed_without_exact_rung_limit(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Dagotto-Rice strong-rung limit"):
        literature_runtime_evidence.parse_dagotto_rice_strong_rung_limit(source_text)


def test_kitaev_exact_solution_parser_extracts_isotropic_gapless_phase():
    parsed, trace = literature_runtime_evidence.parse_kitaev_exact_spin_liquid(
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT
    )

    assert parsed == {
        "is_exactly_solvable": True,
        "isotropic_phase": "gapless_spin_liquid",
    }
    assert trace["parser"] == "parse_kitaev_exact_spin_liquid"


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("exact solution", "approximation"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("free real fermions", "bosons"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("phase B", "phase C"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("fermions are gapless", "fermions are gapped"),
        KITAEV_EXACT_SOLUTION_SOURCE_TEXT.replace("Jx = Jy = Jz", "Jx differs from Jy"),
    ],
)
def test_kitaev_exact_solution_parser_fails_closed_without_full_claim(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitaev exact-solution claim"):
        literature_runtime_evidence.parse_kitaev_exact_spin_liquid(source_text)


def test_kitaev_triangle_parser_extracts_gapless_condition():
    parsed, trace = literature_runtime_evidence.parse_kitaev_gapless_triangle_condition(
        KITAEV_TRIANGLE_SOURCE_TEXT
    )

    assert parsed == {
        "gapless_condition": "triangle_inequalities",
        "isotropic_kitaev_point_gapless": True,
    }
    assert trace["parser"] == "parse_kitaev_gapless_triangle_condition"
    assert trace["equation"] == "33"


@pytest.mark.parametrize(
    "source_text",
    [
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("if and only if", "sometimes"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jx| <= |Jy| + |Jz|", "first condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jy| <= |Jx| + |Jz|", "second condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("|Jz| <= |Jx| + |Jy|", "third condition"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("(33)", "(34)"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("this phase is gapless", "this phase is gapped"),
        KITAEV_TRIANGLE_SOURCE_TEXT.replace("Jx = Jy = Jz", "Jx differs from Jy"),
    ],
)
def test_kitaev_triangle_parser_fails_closed_without_complete_condition(source_text):
    with pytest.raises(RuntimeEvidenceError, match="Kitaev gapless condition"):
        literature_runtime_evidence.parse_kitaev_gapless_triangle_condition(source_text)


def test_audit_rejects_legacy_prose_without_runtime_record():
    audit = build_literature_reproduction_audit(runtime_evidence_enabled=False)
    rows = {row["name"]: row for row in audit["rows"]}

    assert rows["majundar_ghosh_chain_exact_dimer_point"][
        "strict_literature_match_label"
    ] == "no"
    assert rows["cri3_honeycomb_ferromagnet_reference"][
        "strict_literature_match_label"
    ] == "no"


def test_structural_validator_accepts_matching_source_parse_bundle():
    category = (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", _source_parse_bundle()
        )
    )

    assert category == "strict_local_source_parsed"


def test_structural_validator_rejects_source_parse_when_comparison_does_not_match():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["comparison"]["matched"] = False

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_runtime_evidence_with_empty_source_hash():
    record = {**_runtime_source_parse_record(), "source_sha256": ""}
    extraction_trace = {**_extraction_trace(), "source_sha256": ""}
    bundle = {
        "runtime_evidence_record": record,
        "extraction_trace": extraction_trace,
    }

    assert _structural_label(bundle) == "no"


def _local_recompute_bundle(*, adapter="xxx_spin_half_chain_bethe_energy_per_site"):
    benchmark_name = "xxx_spin_half_chain_bethe_ground_state"
    operand = {"energy_per_site": -0.4431471805599453}
    record = {
        **_runtime_source_parse_record(),
        "benchmark_name": benchmark_name,
        "evidence_mode": "local_recompute",
        "source_operand": operand,
        "computed_operand": operand,
        "registry_operand": operand,
    }
    execution_trace = {
        "benchmark_name": benchmark_name,
        "source_sha256": record["source_sha256"],
        "adapter_parameters": {"exchange": 1.0},
        "computed_operand": operand,
    }
    if adapter is not None:
        execution_trace["adapter"] = adapter
    extraction_trace = {
        **_extraction_trace(),
        "benchmark_name": benchmark_name,
    }
    return {
        "runtime_evidence_record": record,
        "execution_trace": execution_trace,
        "extraction_trace": extraction_trace,
    }


def _source_parse_bundle():
    return {
        "runtime_evidence_record": _runtime_source_parse_record(),
        "extraction_trace": _extraction_trace(),
    }


def _mutate_bundle(bundle, *changes):
    mutated = deepcopy(bundle)
    for path, value in changes:
        target = mutated
        for key in path[:-1]:
            target = target[key]
        if value is MISSING:
            target.pop(path[-1], None)
        else:
            target[path[-1]] = value
    return mutated


def _normalized_changes(changes):
    if (
        len(changes) == 2
        and isinstance(changes[0], tuple)
        and all(isinstance(key, str) for key in changes[0])
    ):
        return (changes,)
    return changes


def _structural_label(bundle, *, benchmark_name=None):
    if benchmark_name is None:
        benchmark_name = bundle["runtime_evidence_record"]["benchmark_name"]
    category = (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            benchmark_name, bundle
        )
    )
    return "yes" if category is not None else "no"


def test_structural_validator_rejects_runtime_comparison_without_exact_field_map_kind():
    bundle = _mutate_bundle(
        _source_parse_bundle(),
        (("runtime_evidence_record", "comparison", "kind"), "approximate"),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "source_sha256",
    [
        pytest.param("a" * 63, id="wrong-length"),
        pytest.param("A" * 64, id="uppercase-hex"),
        pytest.param("g" * 64, id="non-hex"),
    ],
)
def test_structural_validator_rejects_malformed_source_sha256(source_sha256):
    bundle = _mutate_bundle(
        _source_parse_bundle(),
        (("runtime_evidence_record", "source_sha256"), source_sha256),
        (("extraction_trace", "source_sha256"), source_sha256),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "path,value",
    [
        pytest.param(
            ("runtime_evidence_record", "benchmark_name"),
            "wrong_benchmark",
            id="record-benchmark-mismatch",
        ),
        pytest.param(
            ("extraction_trace", "benchmark_name"),
            "wrong_benchmark",
            id="extraction-benchmark-mismatch",
        ),
        pytest.param(
            ("extraction_trace", "source_sha256"),
            "b" * 64,
            id="extraction-sha-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_runtime_or_extraction_identity_mismatch(path, value):
    benchmark_name = "cri3_honeycomb_ferromagnet_reference"
    bundle = _mutate_bundle(_source_parse_bundle(), (path, value))

    assert _structural_label(bundle, benchmark_name=benchmark_name) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("runtime_evidence_record", "source_operand"), MISSING),
            id="source-operand-missing",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_operand"), MISSING),
            id="registry-operand-missing",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), MISSING),
                (("runtime_evidence_record", "registry_operand"), MISSING),
            ),
            id="source-and-registry-operands-missing",
        ),
    ],
)
def test_structural_validator_rejects_source_parse_with_missing_required_operands(changes):
    bundle = _mutate_bundle(_source_parse_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_with_missing_computed_operand():
    bundle = _mutate_bundle(
        _local_recompute_bundle(),
        (("runtime_evidence_record", "computed_operand"), MISSING),
        (("execution_trace", "computed_operand"), MISSING),
    )

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "path,value",
    [
        pytest.param(("extraction_trace", "parser"), MISSING, id="parser-missing"),
        pytest.param(("extraction_trace", "parser"), "", id="parser-empty"),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            MISSING,
            id="matched-anchors-missing",
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"), [], id="matched-anchors-empty"
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            [""],
            id="matched-anchors-invalid-item",
        ),
        pytest.param(
            ("extraction_trace", "matched_anchors"),
            "anchor",
            id="matched-anchors-bare-string",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), MISSING, id="text-spans-missing"
        ),
        pytest.param(("extraction_trace", "text_spans"), [], id="text-spans-empty"),
        pytest.param(
            ("extraction_trace", "text_spans"), "0:1", id="text-spans-bare-string"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), [[0, 0]], id="text-span-empty"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"), [[-1, 2]], id="text-span-negative"
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [["0", 2]],
            id="text-span-noninteger",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[0, 1, 2]],
            id="text-span-wrong-arity",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[True, 2]],
            id="text-span-boolean-start",
        ),
        pytest.param(
            ("extraction_trace", "text_spans"),
            [[0, False]],
            id="text-span-boolean-end",
        ),
    ],
)
def test_structural_validator_rejects_malformed_extraction_trace_structure(path, value):
    bundle = _mutate_bundle(_source_parse_bundle(), (path, value))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("runtime_evidence_record", "source_id"), MISSING),
            id="source-id-missing",
        ),
        pytest.param(
            (("runtime_evidence_record", "source_id"), ""), id="source-id-empty"
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector"), None),
            id="selector-nonmapping",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), []),
            id="selector-path-empty",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), "path"),
            id="selector-path-bare-string",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), [""]),
            id="selector-path-empty-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "path"), ["  "]),
            id="selector-path-whitespace-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), []),
            id="selector-fields-empty",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), "field"),
            id="selector-fields-bare-string",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), [""]),
            id="selector-fields-empty-item",
        ),
        pytest.param(
            (("runtime_evidence_record", "registry_selector", "fields"), ["  "]),
            id="selector-fields-whitespace-item",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_selector", "fields"),
                ["ferromagnetic_order", "ferromagnetic_order"],
            ),
            id="selector-fields-duplicate",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_selector", "fields"),
                ["different_field"],
            ),
            id="selector-fields-do-not-match-operands",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), {}),
                (("runtime_evidence_record", "registry_operand"), {}),
            ),
            id="operands-empty",
        ),
        pytest.param(
            (
                (("runtime_evidence_record", "source_operand"), "value"),
                (("runtime_evidence_record", "registry_operand"), "value"),
            ),
            id="operands-nonmapping",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "source_operand"),
                {"different_field": True},
            ),
            id="source-operand-selector-key-mismatch",
        ),
        pytest.param(
            (
                ("runtime_evidence_record", "registry_operand"),
                {"different_field": True},
            ),
            id="registry-operand-selector-key-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_malformed_record_provenance_selector_or_operands(changes):
    bundle = _mutate_bundle(_source_parse_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            (("execution_trace", "adapter_parameters"), MISSING),
            id="adapter-parameters-missing",
        ),
        pytest.param(
            (("execution_trace", "adapter_parameters"), []),
            id="adapter-parameters-nonmapping",
        ),
        pytest.param(
            (("execution_trace", "computed_operand"), {}),
            id="trace-computed-operand-empty",
        ),
        pytest.param(
            (("execution_trace", "computed_operand"), "value"),
            id="trace-computed-operand-nonmapping",
        ),
        pytest.param(
            (("execution_trace", "benchmark_name"), "wrong_benchmark"),
            id="execution-benchmark-mismatch",
        ),
        pytest.param(
            (("execution_trace", "source_sha256"), "b" * 64),
            id="execution-sha-mismatch",
        ),
        pytest.param(
            (
                ("execution_trace", "computed_operand"),
                {"different_field": -0.4431471805599453},
            ),
            id="trace-computed-operand-selector-key-mismatch",
        ),
        pytest.param(
            (
                (
                    ("runtime_evidence_record", "computed_operand"),
                    {"different_field": -0.4431471805599453},
                ),
                (
                    ("execution_trace", "computed_operand"),
                    {"different_field": -0.4431471805599453},
                ),
            ),
            id="record-computed-operand-selector-key-mismatch",
        ),
    ],
)
def test_structural_validator_rejects_malformed_local_recompute_execution_structure(changes):
    bundle = _mutate_bundle(_local_recompute_bundle(), *_normalized_changes(changes))

    assert _structural_label(bundle) == "no"


@pytest.mark.parametrize(
    "adapter",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
    ],
)
def test_structural_validator_rejects_local_recompute_without_named_adapter(adapter):
    bundle = _local_recompute_bundle(adapter=adapter)

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_when_trace_computed_operand_mismatches():
    bundle = _local_recompute_bundle()
    bundle["execution_trace"]["computed_operand"] = {"energy_per_site": -0.44}

    assert _structural_label(bundle) == "no"


def test_structural_validator_rejects_local_recompute_without_three_matching_operands():
    bundle = _local_recompute_bundle()
    record = bundle["runtime_evidence_record"]
    record["computed_operand"] = {"energy_per_site": -0.44}
    bundle["execution_trace"]["computed_operand"] = record["computed_operand"]

    assert _structural_label(bundle) == "no"


def test_runtime_collector_executes_xxx_adapter_on_audit_path(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, exchange):
        calls.append(exchange)
        return 0.25 - 0.6931471805599453

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "xxx_spin_half_chain_bethe_energy_per_site",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [1.0]
    record = evidence["xxx_spin_half_chain_bethe_ground_state"][
        "runtime_evidence_record"
    ]
    assert record["comparison"]["matched"] is True
    assert record["computed_operand"] == record["source_operand"]


def test_registry_selector_override_can_only_narrow_registered_fields():
    selector = {
        "path": ("standard_result",),
        "fields": ("formula", "correlation_length_beta_1_j_1"),
    }

    narrowed = literature_runtime_evidence._narrow_registry_selector(
        selector, ("correlation_length_beta_1_j_1",)
    )

    assert narrowed == {
        "path": ["standard_result"],
        "fields": ["correlation_length_beta_1_j_1"],
    }
    with pytest.raises(RuntimeEvidenceError, match="registered selector fields"):
        literature_runtime_evidence._narrow_registry_selector(
            selector, ("unregistered",)
        )


def test_runtime_collector_recomputes_taylor_ising_correlation_length(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, beta, exchange):
        calls.append({"beta": beta, "exchange": exchange})
        return -1.0 / literature_runtime_evidence.math.log(
            literature_runtime_evidence.math.tanh(beta * exchange)
        )

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "classical_ising_chain_correlation_length",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [{"beta": 1.0, "exchange": 1.0}]
    record = evidence["one_dimensional_classical_ising_correlation_length"][
        "runtime_evidence_record"
    ]
    assert record["registry_selector"] == {
        "path": ["standard_result"],
        "fields": ["correlation_length_beta_1_j_1"],
    }
    assert "formula" not in record["source_operand"]
    assert record["source_operand"] == record["computed_operand"]
    assert record["computed_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_tasaki_lsm_constraint():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    bundle = evidence["lieb_schultz_mattis_half_integer_constraint"]
    record = bundle["runtime_evidence_record"]
    assert record["evidence_mode"] == "local_source_parse"
    assert record["source_operand"] == {
        "unique_ground_state_implies_gapless_excitations": True
    }
    assert record["source_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True
    assert "execution_trace" not in bundle


def test_runtime_collector_recomputes_onsager_square_ising_tc(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(exchange=1.0):
        calls.append(exchange)
        return 2.0 * exchange / literature_runtime_evidence.math.log(
            1.0 + literature_runtime_evidence.math.sqrt(2.0)
        )

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "two_dimensional_ising_square_tc",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [1.0]
    record = evidence["two_dimensional_square_ising_onsager_tc"][
        "runtime_evidence_record"
    ]
    assert record["source_operand"] == record["computed_operand"]
    assert record["computed_operand"] == record["registry_operand"]
    assert record["comparison"]["matched"] is True


def test_runtime_collector_recomputes_decoupled_two_leg_rung_spectrum(monkeypatch):
    _require_runtime_cache()
    calls = []

    def recorded_adapter(*, j_rung, j_leg):
        calls.append({"j_rung": j_rung, "j_leg": j_leg})
        return {
            "strong_rung_limit": True,
            "rung_singlet_energy": -0.75,
            "rung_triplet_energy": 0.25,
            "rung_gap": 1.0,
        }

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "spin_ladder_strong_rung_gap_status",
        recorded_adapter,
    )
    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert calls == [{"j_rung": 1.0, "j_leg": 0.0}]
    record = evidence["two_leg_ladder_strong_rung_exact_limit"][
        "runtime_evidence_record"
    ]
    expected = {"energy_per_rung": -0.75, "gap_to_triplet": 1.0}
    assert record["source_operand"] == expected
    assert record["computed_operand"] == expected
    assert record["registry_operand"] == expected
    assert record["comparison"]["matched"] is True


def test_runtime_collector_parses_two_distinct_kitaev_claims_from_shared_source():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    exact_record = evidence["kitaev_honeycomb_exact_spin_liquid_limit"][
        "runtime_evidence_record"
    ]
    triangle_record = evidence["kitaev_honeycomb_gapless_triangle_condition"][
        "runtime_evidence_record"
    ]
    assert exact_record["source_sha256"] == triangle_record["source_sha256"]
    assert exact_record["source_sha256"] == (
        "eb99541ee61044a6028edc53aad19dd80afed7e96778350a38420f36269e93ba"
    )
    assert exact_record["source_operand"] == {
        "is_exactly_solvable": True,
        "isotropic_phase": "gapless_spin_liquid",
    }
    assert triangle_record["source_operand"] == {
        "gapless_condition": "triangle_inequalities",
        "isotropic_kitaev_point_gapless": True,
    }
    assert exact_record["source_operand"] == exact_record["registry_operand"]
    assert triangle_record["source_operand"] == triangle_record["registry_operand"]
    assert exact_record["comparison"]["matched"] is True
    assert triangle_record["comparison"]["matched"] is True


def test_runtime_audit_writers_serialize_structured_evidence(tmp_path):
    _require_runtime_cache()
    audit = build_literature_reproduction_audit()
    csv_path = tmp_path / "audit.csv"
    markdown_path = tmp_path / "audit.md"
    gaps_path = tmp_path / "gaps.md"

    write_audit_csv(audit, csv_path)
    write_audit_markdown(audit, markdown_path)
    write_remaining_strict_reproduction_gaps_markdown(audit, gaps_path)

    with csv_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = {row["name"]: row for row in csv.DictReader(handle)}
    markdown_text = markdown_path.read_text(encoding="utf-8")
    gaps_text = gaps_path.read_text(encoding="utf-8")
    audit_rows = {row["name"]: row for row in audit["rows"]}
    for name in {
        "cri3_honeycomb_ferromagnet_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "two_dimensional_square_ising_onsager_tc",
        "two_leg_ladder_strong_rung_exact_limit",
        "xxx_spin_half_chain_bethe_ground_state",
    }:
        for field in (
            "runtime_evidence_record",
            "execution_trace",
            "extraction_trace",
        ):
            assert json.loads(csv_rows[name][field]) == audit_rows[name][field]
    assert "strict_local_recomputed: `4`" in markdown_text
    assert "strict_local_source_parsed: `4`" in markdown_text
    assert "Supported: `8`" in markdown_text
    assert "Missing: `147`" in markdown_text
    assert "Complete: `False`" in markdown_text
    assert "8 of 155 entries are strict" in gaps_text


def test_runtime_audit_has_exactly_the_eight_cache_backed_strict_routes():
    _require_runtime_cache()
    audit = build_literature_reproduction_audit()
    supported_names = {
        "cri3_honeycomb_ferromagnet_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "two_dimensional_square_ising_onsager_tc",
        "two_leg_ladder_strong_rung_exact_limit",
        "xxx_spin_half_chain_bethe_ground_state",
    }
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    strict_names = {
        row["name"]
        for row in audit["rows"]
        if row["strict_literature_match_label"] == "yes"
    }
    remaining_names = {
        row["name"]
        for row in audit["rows"]
        if row["strict_literature_match_label"] == "no"
    }

    assert strict_names == supported_names
    assert remaining_names == registry_names - supported_names
    assert len(remaining_names) == 147
    assert audit["runtime_evidence_coverage"] == {
        "supported_names": sorted(supported_names),
        "missing_names": sorted(registry_names - supported_names),
        "extra_names": [],
        "invalid_names": [],
        "supported": 8,
        "missing": 147,
        "extra": 0,
        "invalid": 0,
        "complete": False,
    }


def test_public_audit_api_rejects_runtime_evidence_injection():
    signature = inspect.signature(build_literature_reproduction_audit)

    assert "runtime_evidence_by_name" not in signature.parameters
    with pytest.raises(TypeError):
        build_literature_reproduction_audit(runtime_evidence_by_name={})


def test_runtime_disabled_audit_is_hermetic_and_has_no_strict_rows():
    audit = build_literature_reproduction_audit(runtime_evidence_enabled=False)

    assert audit["strict_category_counts"] == {
        "executable_projection": 0,
        "local_projection_only": 155,
        "reference_only": 0,
        "strict_local_recomputed": 0,
        "strict_local_source_parsed": 0,
    }
    assert all(row["runtime_evidence_record"] is None for row in audit["rows"])
    assert all(row["execution_trace"] is None for row in audit["rows"])
    assert all(row["extraction_trace"] is None for row in audit["rows"])
    assert audit["runtime_evidence_coverage"]["supported"] == 0
    assert audit["runtime_evidence_coverage"]["missing"] == 155
    assert audit["runtime_evidence_coverage"]["complete"] is False


def test_structural_validator_rejects_nonfinite_operands():
    for nonfinite in (float("nan"), float("inf"), float("-inf")):
        bundle = _source_parse_bundle()
        bundle["runtime_evidence_record"]["source_operand"] = {
            "ferromagnetic_order": nonfinite
        }
        bundle["runtime_evidence_record"]["registry_operand"] = {
            "ferromagnetic_order": nonfinite
        }

        assert (
            literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
                "cri3_honeycomb_ferromagnet_reference", bundle
            )
            is None
        )


def test_structural_validator_rejects_boolean_integer_false_match():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["source_operand"] = {
        "ferromagnetic_order": 1
    }

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        is None
    )


def test_structural_validator_rejects_non_json_operand_values():
    bundle = _source_parse_bundle()
    bundle["runtime_evidence_record"]["source_operand"] = {
        "ferromagnetic_order": {"not", "json"}
    }
    bundle["runtime_evidence_record"]["registry_operand"] = {
        "ferromagnetic_order": {"not", "json"}
    }

    assert (
        literature_runtime_evidence.structurally_validate_runtime_evidence_bundle(
            "cri3_honeycomb_ferromagnet_reference", bundle
        )
        is None
    )


def test_malformed_collected_evidence_is_hidden_and_writers_remain_total(
    monkeypatch, tmp_path
):
    malformed_bundle = _source_parse_bundle()
    malformed_bundle["runtime_evidence_record"].pop("comparison")
    monkeypatch.setattr(
        literature_reproduction_audit,
        "collect_runtime_evidence",
        lambda registry_entries, *, cache_root: {
            "cri3_honeycomb_ferromagnet_reference": malformed_bundle
        },
    )

    audit = build_literature_reproduction_audit(cache_root=tmp_path)
    row = {row["name"]: row for row in audit["rows"]}[
        "cri3_honeycomb_ferromagnet_reference"
    ]
    assert row["strict_literature_match_label"] == "no"
    assert row["runtime_evidence_record"] is None
    assert row["execution_trace"] is None
    assert row["extraction_trace"] is None

    csv_path = tmp_path / "audit.csv"
    markdown_path = tmp_path / "audit.md"
    gaps_path = tmp_path / "gaps.md"
    write_audit_csv(audit, csv_path)
    write_audit_markdown(audit, markdown_path)
    write_remaining_strict_reproduction_gaps_markdown(audit, gaps_path)
    assert csv_path.is_file()
    assert markdown_path.is_file()
    assert gaps_path.is_file()


def test_collector_extraction_traces_declare_coordinate_space():
    _require_runtime_cache()

    evidence = collect_runtime_evidence(LITERATURE_STANDARD_RESULTS)

    assert set(evidence) == {
        "cri3_honeycomb_ferromagnet_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_gapless_triangle_condition",
        "lieb_schultz_mattis_half_integer_constraint",
        "one_dimensional_classical_ising_correlation_length",
        "two_dimensional_square_ising_onsager_tc",
        "two_leg_ladder_strong_rung_exact_limit",
        "xxx_spin_half_chain_bethe_ground_state",
    }
    assert all(
        bundle["extraction_trace"]["coordinate_space"]
        == "whitespace_normalized_extracted_text"
        for bundle in evidence.values()
    )


def test_structural_coverage_reports_missing_extra_and_invalid_names():
    valid_name = "cri3_honeycomb_ferromagnet_reference"
    invalid_name = "invalid_route"
    registry_entries = [{"name": valid_name}, {"name": invalid_name}]
    invalid_bundle = _source_parse_bundle()
    invalid_bundle["runtime_evidence_record"]["benchmark_name"] = invalid_name
    evidence = {
        valid_name: _source_parse_bundle(),
        invalid_name: invalid_bundle,
        "extra_route": _source_parse_bundle(),
    }

    coverage = literature_runtime_evidence.structurally_validate_runtime_evidence_coverage(
        registry_entries, evidence
    )

    assert coverage == {
        "supported_names": [valid_name],
        "missing_names": [],
        "extra_names": ["extra_route"],
        "invalid_names": [invalid_name],
        "supported": 1,
        "missing": 0,
        "extra": 1,
        "invalid": 1,
        "complete": False,
    }


def test_authoritative_runtime_coverage_collects_verified_local_sources(monkeypatch):
    _require_runtime_cache()
    calls = []
    real_collector = literature_runtime_evidence.collect_runtime_evidence

    def recorded_collector(registry_entries, *, cache_root):
        calls.append(cache_root)
        return real_collector(registry_entries, cache_root=cache_root)

    monkeypatch.setattr(
        literature_runtime_evidence, "collect_runtime_evidence", recorded_collector
    )
    coverage = literature_runtime_evidence.collect_runtime_evidence_coverage(
        LITERATURE_STANDARD_RESULTS,
        cache_root=literature_runtime_evidence.DEFAULT_CACHE_ROOT,
    )

    assert calls == [literature_runtime_evidence.DEFAULT_CACHE_ROOT]
    assert coverage["supported"] == 8
    assert coverage["missing"] == 147
    assert coverage["extra"] == 0
    assert coverage["invalid"] == 0
    assert coverage["complete"] is False


def test_runtime_completion_assertion_rejects_current_incomplete_coverage():
    _require_runtime_cache()

    with pytest.raises(RuntimeEvidenceError, match="147 missing"):
        literature_runtime_evidence.assert_complete_runtime_evidence(
            LITERATURE_STANDARD_RESULTS
        )
