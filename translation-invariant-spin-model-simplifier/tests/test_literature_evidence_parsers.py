import hashlib
import inspect
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from validation import literature_evidence_parsers as parser_module
from validation.literature_evidence_parsers import (
    SourceParserError,
    parse_source_target,
)
from validation.literature_evidence_schema import ExtractionTrace, SourceProvenance
from validation.literature_evidence_sources import VerifiedSource, load_verified_source


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_REAL_LAYOUT_PAYLOAD_SHA256 = {
    "arxiv_dbdd4b586780cd708b67": (
        "393c8b20697e3410e1a62fc6c56715cadc3f79098cda97325b9b095a1c3ec304"
    ),
    "doi_ebcdccab3f81a5059936": (
        "f5fc182cbf87f55375357e0bcd1c10ca1e665d09b33a5c52d39a74aa1aa63332"
    ),
    "doi_10f8d8a847e8ffd6e766": (
        "efc3e306602617a2dcf10a45ee05712067483dcf75477e0b2ed0f70c56e404a5"
    ),
    "doi_30de47257cfae45dcfca": (
        "250399f671a152e1af803094e42274dd68d36b21e80f73ddafac5b5132e54c97"
    ),
}


@lru_cache(maxsize=None)
def _cached_authoritative_source(source_id: str) -> VerifiedSource:
    source_dir = _PROJECT_ROOT / "source-cache" / source_id
    if not source_dir.is_dir():
        pytest.skip(f"authoritative parser-layout replay requires {source_dir}")
    inventory_root = _PROJECT_ROOT / "reference" / "literature-evidence"
    source_index = {
        item["source_id"]: item
        for item in json.loads(
            (inventory_root / "source-index.json").read_text(encoding="utf-8")
        )["sources"]
    }
    provisioning = {
        item["source_id"]: item
        for item in json.loads(
            (inventory_root / "source-provisioning.json").read_text(encoding="utf-8")
        )["sources"]
    }
    source = load_verified_source(
        source_dir,
        expected_source=source_index[source_id],
        provisioning_route=provisioning[source_id],
    )
    assert source.payload_sha256 == _REAL_LAYOUT_PAYLOAD_SHA256[source_id]
    return source


def _with_source_role(source: VerifiedSource, role: str) -> VerifiedSource:
    title = source.provenance.bibliographic_metadata["title"]
    citation_verification = dict(source.provenance.citation_metadata_verification)
    citation_verification["source_role_verification"] = {
        "status": "verified",
        "source_roles": [role],
        "bibliographic_title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
        "raw_payload_sha256": source.payload_sha256,
    }
    return replace(
        source,
        provenance=replace(
            source.provenance,
            citation_metadata_verification=citation_verification,
        ),
    )


def _verified_text_source(text: str) -> VerifiedSource:
    payload = text.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    title = "Parser fixture"
    provenance = SourceProvenance(
        source_id="doi_parser_fixture",
        source_identity={
            "kind": "doi",
            "value": "10.0000/parser.fixture",
            "canonical_url": "https://doi.org/10.0000/parser.fixture",
        },
        bibliographic_metadata={"title": title},
        retrieval_metadata={"url": "https://example.invalid/parser.txt"},
        media_type="text/plain",
        raw_payload_sha256=digest,
        raw_payload_byte_length=len(payload),
        license_access_notes={"access": "test_fixture"},
        citation_metadata_verification={
            "verified": True,
            "source_role_verification": {
                "status": "verified",
                "source_roles": ["primary_experimental", "primary_model"],
                "bibliographic_title_sha256": hashlib.sha256(
                    title.encode("utf-8")
                ).hexdigest(),
                "raw_payload_sha256": digest,
            },
        },
    )
    return VerifiedSource(
        source_id="doi_parser_fixture",
        provenance=provenance,
        payload_path=Path("/nonexistent/parser-fixture.txt"),
        payload_bytes=payload,
        payload_sha256=digest,
        extracted_text=text,
        extraction_tool={
            "tool": "utf8_text",
            "version": "stdlib",
            "deterministic": True,
        },
    )


def _parse_primary_claim(sentence: str, *, field_id: str = "zigzag_order"):
    return _parse_primary_claim_from_source(
        _verified_text_source("Results\n" + sentence + "\n"),
        field_id=field_id,
    )


def _parse_primary_claim_from_source(
    source: VerifiedSource, *, field_id: str = "zigzag_order"
):
    return parse_source_target(
        benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Neutron diffraction",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": field_id,
            "claim_context": "primary_experimental",
            "units": "not_applicable",
        },
    )


def test_numeric_equation_parser_extracts_runtime_value_and_complete_trace():
    source = _verified_text_source("Results\nEq. (3): gap/J = 0.41050(2)\nDiscussion\n")

    trace = parse_source_target(
        benchmark_name="haldane_spin1_chain_gap_reference",
        source=source,
        locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
        parser={
            "kind": "numeric",
            "field_id": "gap_over_j",
            "value_label": "gap/J",
            "units": "dimensionless_ratio",
            "uncertainty": "parenthetical_last_digits",
        },
    )

    assert isinstance(trace, ExtractionTrace)
    payload = trace.payload
    assert payload["source_id"] == source.source_id
    assert payload["source_sha256"] == source.payload_sha256
    assert (
        payload["extracted_text_sha256"]
        == hashlib.sha256(source.extracted_text.encode("utf-8")).hexdigest()
    )
    assert payload["raw_value"] == "0.41050(2)"
    assert payload["normalized_value"] == {"gap_over_j": 0.41050}
    assert payload["typed_claim"] == {
        "kind": "numeric",
        "fields": (
            {
                "id": "gap_over_j",
                "type": "number",
                "units": "dimensionless_ratio",
                "uncertainty": 0.00002,
            },
        ),
    }
    assert payload["excerpt"] == "Eq. (3): gap/J = 0.41050(2)"
    assert (
        payload["excerpt_sha256"]
        == hashlib.sha256(payload["excerpt"].encode("utf-8")).hexdigest()
    )
    assert (
        payload["value_sha256"]
        == hashlib.sha256(payload["raw_value"].encode("utf-8")).hexdigest()
    )
    assert payload["raw_value_sha256"] == payload["value_sha256"]
    assert payload["coordinates"]["coordinate_space"] == "verified_extracted_text_utf8"
    assert payload["coordinates"]["character_start"] == source.extracted_text.index(
        "Eq. (3)"
    )
    assert payload["coordinates"]["character_end"] == (
        payload["coordinates"]["character_start"] + len(payload["excerpt"])
    )
    assert payload["coordinates"]["page_number"] == 1
    assert payload["coordinates"]["line_start"] == 2
    assert payload["parser"]["id"] == "numeric"
    assert (
        payload["parser"]["code_sha256"]
        == hashlib.sha256(Path(parser_module.__file__).read_bytes()).hexdigest()
    )
    assert payload["unit_evidence"]["raw_units"] == "gap/J"
    assert payload["unit_evidence"]["normalized_units"] == "dimensionless_ratio"
    assert payload["unit_evidence"]["sha256"] == hashlib.sha256(b"gap/J").hexdigest()


def test_numeric_parser_returns_replaced_scientific_target_and_its_exact_span():
    source = _verified_text_source(
        "Results\nEq. (3): gap/J = 5.1050(3)e-1\nDiscussion\n"
    )

    trace = parse_source_target(
        benchmark_name="haldane_spin1_chain_gap_reference",
        source=source,
        locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
        parser={
            "kind": "numeric",
            "field_id": "gap_over_j",
            "value_label": "gap/J",
            "units": "dimensionless_ratio",
            "uncertainty": "parenthetical_last_digits",
        },
    )

    payload = trace.payload
    assert payload["raw_value"] == "5.1050(3)e-1"
    assert payload["normalized_value"] == {"gap_over_j": 0.51050}
    assert payload["typed_claim"]["fields"][0]["uncertainty"] == 0.00003
    value_coordinates = payload["value_coordinates"]
    expected_start = source.extracted_text.index("5.1050(3)e-1")
    assert value_coordinates["character_start"] == expected_start
    assert value_coordinates["character_end"] == expected_start + len("5.1050(3)e-1")


def test_numeric_parser_rejects_two_targets_with_the_same_label_in_one_excerpt():
    source = _verified_text_source("Eq. (3): gap/J = 0.41050(2); gap/J = 0.51050(2)\n")

    with pytest.raises(SourceParserError, match="ambiguous target label"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=source,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap_over_j",
                "value_label": "gap/J",
                "units": "dimensionless_ratio",
                "uncertainty": "parenthetical_last_digits",
            },
        )


@pytest.mark.parametrize(
    "malformed_token",
    ["0.41050oops", "1/2", "1+2", "1±0.1"],
)
def test_numeric_parser_rejects_a_valid_number_prefix_inside_a_malformed_token(
    malformed_token,
):
    source = _verified_text_source(f"Eq. (3): gap/J = {malformed_token}\n")

    with pytest.raises(SourceParserError, match="does not contain a numeric value"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=source,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap_over_j",
                "value_label": "gap/J",
                "units": "dimensionless_ratio",
                "uncertainty": "parenthetical_last_digits",
            },
        )


def test_numeric_parser_rejects_source_unit_conflicting_with_declared_normalization():
    source = _verified_text_source("Eq. (3): gap = 1.0 eV\n")

    with pytest.raises(SourceParserError, match="source units.*disagree"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=source,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap",
                "value_label": "gap",
                "units": "meV",
                "uncertainty": "parenthetical_last_digits",
            },
        )


def test_interval_parser_extracts_bounds_and_inclusivity_from_source_equation():
    source = _verified_text_source(
        "Phase diagram\n"
        "Eq. (7): spin-liquid window: 0.08 <= J2/J1 < 0.15\n"
        "Finite-size analysis\n"
    )

    trace = parse_source_target(
        benchmark_name="triangular_j1_j2_spin_liquid_window_reference",
        source=source,
        locator={"kind": "equation", "label": "Eq. (7)", "occurrence": 1},
        parser={
            "kind": "interval",
            "field_id": "j2_over_j1_window",
            "value_label": "spin-liquid window",
            "variable": "J2/J1",
            "units": "dimensionless_ratio",
            "output_type": "interval[number]",
        },
    )

    payload = trace.payload
    assert payload["raw_value"] == "0.08 <= J2/J1 < 0.15"
    assert payload["normalized_value"] == {
        "j2_over_j1_window": {
            "lower": 0.08,
            "upper": 0.15,
            "lower_inclusive": True,
            "upper_inclusive": False,
        }
    }
    assert payload["typed_claim"]["fields"] == (
        {
            "id": "j2_over_j1_window",
            "type": "interval[number]",
            "units": "dimensionless_ratio",
        },
    )
    assert payload["value_coordinates"]["character_start"] == (
        source.extracted_text.index("0.08 <= J2/J1 < 0.15")
    )


def test_interval_parser_can_emit_inventory_endpoint_sequence_without_losing_bounds():
    source = _verified_text_source("Claim: nonmagnetic window: 0.4 <= J2/J1 <= 0.6\n")

    trace = parse_source_target(
        benchmark_name="j1_j2_square_spin_half_neel_collinear_transition_reference",
        source=source,
        locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        parser={
            "kind": "interval",
            "field_id": "nonmagnetic_window_approx",
            "value_label": "nonmagnetic window",
            "variable": "J2/J1",
            "units": "dimensionless_j2_over_j1",
            "output_type": "list[number]",
        },
    )

    assert trace.payload["normalized_value"] == {
        "nonmagnetic_window_approx": (0.4, 0.6)
    }
    assert trace.payload["typed_claim"]["fields"][0]["type"] == "list[number]"
    assert trace.payload["typed_claim"]["bounds"] == {
        "lower": 0.4,
        "upper": 0.6,
        "lower_inclusive": True,
        "upper_inclusive": True,
    }


def test_interval_parser_rejects_an_empty_open_interval():
    source = _verified_text_source("Claim: window: 1 < x/J < 1\n")

    with pytest.raises(SourceParserError, match="interval must be nonempty"):
        parse_source_target(
            benchmark_name="triangular_j1_j2_spin_liquid_window_reference",
            source=source,
            locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
            parser={
                "kind": "interval",
                "field_id": "window",
                "value_label": "window",
                "variable": "x/J",
                "units": "dimensionless_ratio",
                "output_type": "interval[number]",
            },
        )


def test_interval_parser_rejects_explicit_source_unit_conflict():
    source = _verified_text_source("Claim: window: 0.1 < J2/J1 < 0.2 eV\n")

    with pytest.raises(SourceParserError, match="source units.*disagree"):
        parse_source_target(
            benchmark_name="triangular_j1_j2_spin_liquid_window_reference",
            source=source,
            locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
            parser={
                "kind": "interval",
                "field_id": "window",
                "value_label": "window",
                "variable": "J2/J1",
                "units": "dimensionless_j2_over_j1",
                "output_type": "list[number]",
            },
        )


def test_sequence_parser_preserves_runtime_phase_order():
    source = _verified_text_source(
        "Abstract\nClaim: phase sequence = ordered -> critical -> disordered\n"
    )

    trace = parse_source_target(
        benchmark_name="square_clock_q5_two_bkt_transitions",
        source=source,
        locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        parser={
            "kind": "sequence",
            "field_id": "phase_sequence",
            "value_label": "phase sequence",
            "delimiter": "->",
            "item_type": "string",
            "output_type": "list[string]",
            "units": "not_applicable",
        },
    )

    assert trace.payload["raw_value"] == "ordered -> critical -> disordered"
    assert trace.payload["normalized_value"] == {
        "phase_sequence": ("ordered", "critical", "disordered")
    }
    assert trace.payload["typed_claim"]["fields"][0]["type"] == "list[string]"


def test_set_parser_canonicalizes_order_but_reads_replaced_source_member():
    source = _verified_text_source(
        "Results\nClaim: competing phases = stripe, valence_bond, neel\n"
    )

    trace = parse_source_target(
        benchmark_name="j1_j2_j3_square_quantum_phase_reference",
        source=source,
        locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        parser={
            "kind": "set",
            "field_id": "phase_set",
            "value_label": "competing phases",
            "delimiter": ",",
            "item_type": "string",
            "output_type": "list[string]",
            "units": "not_applicable",
        },
    )

    assert trace.payload["raw_value"] == "stripe, valence_bond, neel"
    assert trace.payload["normalized_value"] == {
        "phase_set": ("neel", "stripe", "valence_bond")
    }
    assert trace.payload["typed_claim"]["fields"][0]["type"] == "list[string]"


def test_numeric_sequence_parser_reads_each_replaced_vector_component():
    source = _verified_text_source(
        "Wavevector components are reported in reciprocal lattice units (rlu).\n"
        "Figure 2 caption: ordering wavevector = 0.25, -0.125, 1.5\n"
    )

    trace = parse_source_target(
        benchmark_name="fecl3_honeycomb_antiferromagnet_reference",
        source=source,
        locator={
            "kind": "figure_caption",
            "anchor": "Figure 2 caption:",
            "occurrence": 1,
        },
        parser={
            "kind": "sequence",
            "field_id": "propagation_vector_hexagonal",
            "value_label": "ordering wavevector",
            "delimiter": ",",
            "item_type": "number",
            "output_type": "list[number]",
            "units": "reciprocal_lattice_unit",
            "unit_evidence": {
                "kind": "source_statements",
                "anchors": [
                    {
                        "text": (
                            "Wavevector components are reported in reciprocal "
                            "lattice units (rlu)."
                        ),
                        "occurrence": 1,
                    }
                ],
            },
        },
    )

    assert trace.payload["normalized_value"] == {
        "propagation_vector_hexagonal": (0.25, -0.125, 1.5)
    }
    assert trace.payload["typed_claim"]["fields"][0]["type"] == "list[number]"


def test_wavevector_label_alone_cannot_prove_reciprocal_lattice_units():
    source = _verified_text_source(
        "Figure 2 caption: ordering wavevector = 0.25, -0.125, 1.5\n"
    )

    with pytest.raises(
        SourceParserError,
        match="does not prove declared normalized units",
    ):
        parse_source_target(
            benchmark_name="fecl3_honeycomb_antiferromagnet_reference",
            source=source,
            locator={
                "kind": "figure_caption",
                "anchor": "Figure 2 caption:",
                "occurrence": 1,
            },
            parser={
                "kind": "sequence",
                "field_id": "propagation_vector_hexagonal",
                "value_label": "ordering wavevector",
                "delimiter": ",",
                "item_type": "number",
                "output_type": "list[number]",
                "units": "reciprocal_lattice_unit",
            },
        )


def test_equation_parser_returns_replaced_symbolic_relation_without_evaluating_it():
    source = _verified_text_source(
        "Critical line\n"
        "The critical condition is dimensionless.\n"
        "Eq. (12): critical condition: sinh(2 beta J)^2 = sqrt(3)\n"
    )

    trace = parse_source_target(
        benchmark_name="two_dimensional_square_ising_onsager_tc",
        source=source,
        locator={"kind": "equation", "label": "Eq. (12)", "occurrence": 1},
        parser={
            "kind": "equation",
            "field_id": "critical_condition",
            "value_label": "critical condition",
            "units": "dimensionless_equation",
            "unit_evidence": {
                "kind": "source_statements",
                "anchors": [
                    {
                        "text": "The critical condition is dimensionless.",
                        "occurrence": 1,
                    }
                ],
            },
        },
    )

    assert trace.payload["raw_value"] == "sinh(2 beta J)^2 = sqrt(3)"
    assert trace.payload["normalized_value"] == {
        "critical_condition": {
            "lhs": "sinh(2 beta J)^2",
            "relation": "=",
            "rhs": "sqrt(3)",
        }
    }
    assert trace.payload["typed_claim"]["fields"][0]["type"] == "equation"


def test_equation_parser_kind_alone_cannot_prove_dimensionless_units():
    source = _verified_text_source("Eq. (12): relation: E = J*S\n")

    with pytest.raises(
        SourceParserError,
        match="does not prove declared normalized units",
    ):
        parse_source_target(
            benchmark_name="two_dimensional_square_ising_onsager_tc",
            source=source,
            locator={"kind": "equation", "label": "Eq. (12)", "occurrence": 1},
            parser={
                "kind": "equation",
                "field_id": "critical_condition",
                "value_label": "relation",
                "units": "dimensionless_equation",
            },
        )


def test_equation_parser_rejects_explicit_source_unit_conflict():
    source = _verified_text_source("Eq. (12): relation: E = 1 eV\n")

    with pytest.raises(SourceParserError, match="source units.*disagree"):
        parse_source_target(
            benchmark_name="two_dimensional_square_ising_onsager_tc",
            source=source,
            locator={"kind": "equation", "label": "Eq. (12)", "occurrence": 1},
            parser={
                "kind": "equation",
                "field_id": "relation",
                "value_label": "relation",
                "units": "dimensionless_equation",
            },
        )


def test_scalar_string_parser_reads_replaced_abstract_categorical_label():
    source = _verified_text_source("Abstract: isotropic phase = gapless_spin_liquid\n")

    trace = parse_source_target(
        benchmark_name="kitaev_honeycomb_exact_spin_liquid_limit",
        source=source,
        locator={"kind": "abstract", "anchor": "Abstract:", "occurrence": 1},
        parser={
            "kind": "scalar_string",
            "field_id": "isotropic_phase",
            "value_label": "isotropic phase",
            "value_type": "categorical_label",
            "units": "not_applicable",
        },
    )

    assert trace.payload["raw_value"] == "gapless_spin_liquid"
    assert trace.payload["normalized_value"] == {
        "isotropic_phase": "gapless_spin_liquid"
    }
    assert trace.payload["typed_claim"]["fields"][0] == {
        "id": "isotropic_phase",
        "type": "string",
        "units": "not_applicable",
        "convention": "categorical_label",
    }


@pytest.mark.parametrize("source_label", ["120_degree", "consistent_with_Z2"])
def test_scalar_string_parser_accepts_inventory_categorical_label_shapes(
    source_label,
):
    source = _verified_text_source(f"Claim: reported order = {source_label}\n")

    trace = parse_source_target(
        benchmark_name="triangular_nn_classical_120_reference",
        source=source,
        locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        parser={
            "kind": "scalar_string",
            "field_id": "reported_order",
            "value_label": "reported order",
            "value_type": "categorical_label",
            "units": "not_applicable",
        },
    )

    assert trace.payload["raw_value"] == source_label
    assert trace.payload["normalized_value"] == {"reported_order": source_label}


def test_scalar_string_parser_preserves_safe_symbolic_expression_from_source():
    source = _verified_text_source("Eq. (4): gap formula = 2*J*abs(1-g)\n")

    trace = parse_source_target(
        benchmark_name="transverse_field_ising_chain_gap",
        source=source,
        locator={"kind": "equation", "label": "Eq. (4)", "occurrence": 1},
        parser={
            "kind": "scalar_string",
            "field_id": "gap_formula",
            "value_label": "gap formula",
            "value_type": "symbolic_expression",
            "units": "exchange_energy_unit",
        },
    )

    assert trace.payload["normalized_value"] == {"gap_formula": "2*J*abs(1-g)"}


def test_scalar_string_parser_preserves_safe_relation_and_absolute_value_tokens():
    expression = "|1+exp(iq1)+exp(iq2)|=|J1|/(2J2)"
    source = _verified_text_source(f"Claim: ring condition = {expression}\n")

    trace = parse_source_target(
        benchmark_name="honeycomb_j1_j2_spiral_ring_reference",
        source=source,
        locator={"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        parser={
            "kind": "scalar_string",
            "field_id": "ring_condition",
            "value_label": "ring condition",
            "value_type": "symbolic_expression",
            "units": "not_applicable",
        },
    )

    assert trace.payload["raw_value"] == expression
    assert trace.payload["normalized_value"] == {"ring_condition": expression}


def test_scalar_string_parser_rejects_executable_source_expression():
    source = _verified_text_source(
        "Eq. (4): gap formula = __import__('os').system('id')\n"
    )

    with pytest.raises(SourceParserError, match="unsupported token"):
        parse_source_target(
            benchmark_name="transverse_field_ising_chain_gap",
            source=source,
            locator={"kind": "equation", "label": "Eq. (4)", "occurrence": 1},
            parser={
                "kind": "scalar_string",
                "field_id": "gap_formula",
                "value_label": "gap formula",
                "value_type": "symbolic_expression",
                "units": "exchange_energy_unit",
            },
        )


def test_table_numeric_parser_resolves_header_row_cell_and_uncertainty_column():
    source = _verified_text_source(
        "QMC extrapolation\n"
        "Ground-state energy is reported per site in units of J.\n"
        "Table II\n"
        "observable | value | uncertainty\n"
        "energy_per_site | -0.669437 | 0.000005\n"
        "spin_gap | 0.12 | 0.01\n"
    )

    trace = parse_source_target(
        benchmark_name="square_spin_half_heisenberg_qmc_energy",
        source=source,
        locator={
            "kind": "table",
            "label": "Table II",
            "occurrence": 1,
            "delimiter": "|",
            "row_label": "energy_per_site",
            "value_column": "value",
            "uncertainty_column": "uncertainty",
        },
        parser={
            "kind": "table_numeric",
            "field_id": "energy_per_site",
            "units": "exchange_energy_per_site",
            "unit_evidence": {
                "kind": "source_statements",
                "anchors": [
                    {
                        "text": (
                            "Ground-state energy is reported per site in " "units of J."
                        ),
                        "occurrence": 1,
                    }
                ],
            },
        },
    )

    payload = trace.payload
    assert payload["raw_value"] == "-0.669437"
    assert payload["normalized_value"] == {"energy_per_site": -0.669437}
    assert payload["typed_claim"]["fields"][0]["uncertainty"] == 0.000005
    assert payload["excerpt"] == "energy_per_site | -0.669437 | 0.000005"
    assert payload["table_coordinates"] == {
        "table_label": "Table II",
        "row_label": "energy_per_site",
        "row_number": 1,
        "value_column": "value",
        "value_column_number": 2,
        "uncertainty_column": "uncertainty",
        "uncertainty_column_number": 3,
    }
    assert payload["value_coordinates"]["character_start"] == (
        source.extracted_text.index("-0.669437")
    )


def test_energy_per_site_label_alone_cannot_prove_exchange_normalization():
    source = _verified_text_source(
        "Table II\n"
        "observable | value | uncertainty\n"
        "energy_per_site | -0.669437 | 0.000005\n"
    )

    with pytest.raises(
        SourceParserError,
        match="does not prove declared normalized units",
    ):
        parse_source_target(
            benchmark_name="square_spin_half_heisenberg_qmc_energy",
            source=source,
            locator={
                "kind": "table",
                "label": "Table II",
                "occurrence": 1,
                "delimiter": "|",
                "row_label": "energy_per_site",
                "value_column": "value",
                "uncertainty_column": "uncertainty",
            },
            parser={
                "kind": "table_numeric",
                "field_id": "energy_per_site",
                "units": "exchange_energy_per_site",
            },
        )


def test_table_numeric_parser_rejects_explicit_header_unit_conflict():
    source = _verified_text_source(
        "Table II\n"
        "observable | value_eV | uncertainty\n"
        "energy_per_site | -0.669437 | 0.000005\n"
    )

    with pytest.raises(SourceParserError, match="source units.*disagree"):
        parse_source_target(
            benchmark_name="square_spin_half_heisenberg_qmc_energy",
            source=source,
            locator={
                "kind": "table",
                "label": "Table II",
                "occurrence": 1,
                "delimiter": "|",
                "row_label": "energy_per_site",
                "value_column": "value_eV",
                "uncertainty_column": "uncertainty",
            },
            parser={
                "kind": "table_numeric",
                "field_id": "energy_per_site",
                "units": "exchange_energy_per_site",
            },
        )


def test_typed_claim_parser_extracts_primary_experimental_claim_components():
    source = _verified_text_source(
        "Results\n"
        "Neutron diffraction directly observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field.\n"
    )

    trace = parse_source_target(
        benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Neutron diffraction",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": "zigzag_order",
            "claim_context": "primary_experimental",
            "units": "not_applicable",
        },
    )

    payload = trace.payload
    assert payload["normalized_value"] == {"zigzag_order": True}
    assert payload["typed_claim"] == {
        "kind": "categorical",
        "subject": "alpha-RuCl3",
        "observable": "zigzag order",
        "scope": "material",
        "polarity": "affirmed",
        "qualifier": "directly_observed",
        "method": "neutron_diffraction",
        "source_role": "primary_experimental",
        "conditions": {
            "temperature": {
                "relation": "below",
                "value": 7.0,
                "units": "K",
                "uncertainty": 0.2,
            },
            "field": {"value": 0.0, "units": "T"},
        },
        "fields": (
            {
                "id": "zigzag_order",
                "type": "boolean",
                "units": "not_applicable",
            },
        ),
    }
    assert payload["raw_value"] == payload["excerpt"]
    assert payload["source_role_verification"]["raw_payload_sha256"] == (
        source.payload_sha256
    )


def test_typed_claim_value_span_excludes_source_line_indentation():
    sentence = (
        "Neutron diffraction directly observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n    " + sentence + "   \n")

    trace = parse_source_target(
        benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Neutron diffraction",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": "zigzag_order",
            "claim_context": "primary_experimental",
            "units": "not_applicable",
        },
    )

    coordinates = trace.payload["value_coordinates"]
    source_slice = source.extracted_text[
        coordinates["character_start"]:coordinates["character_end"]
    ]
    assert trace.payload["raw_value"] == sentence
    assert source_slice == trace.payload["raw_value"]


def test_typed_claim_parser_reads_alternative_method_and_numeric_field():
    source = _verified_text_source(
        "Results\n"
        "Magnetic resonant x-ray diffraction observed beta-Li2IrO3 material "
        "incommensurate spiral order below 38(1) K at 2.5(1) T field.\n"
    )

    trace = parse_source_target(
        benchmark_name="beta_li2iro3_spiral_kitaev_gamma_reference",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Magnetic resonant x-ray diffraction",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": "spiral_order",
            "claim_context": "primary_experimental",
            "units": "not_applicable",
        },
    )

    typed_claim = trace.payload["typed_claim"]
    assert typed_claim["method"] == "magnetic_resonant_xray_diffraction"
    assert typed_claim["conditions"]["temperature"] == {
        "relation": "below",
        "value": 38.0,
        "units": "K",
        "uncertainty": 1.0,
    }
    assert typed_claim["conditions"]["field"] == {
        "value": 2.5,
        "units": "T",
        "uncertainty": 0.1,
    }


def test_typed_claim_parser_returns_replaced_parenthesized_material_subject():
    source = _verified_text_source(
        "Results\n"
        "Neutron diffraction observed ZnCu3(OH)6Cl2 material spin liquid behavior "
        "below 0.05(1) K at zero field.\n"
    )

    trace = parse_source_target(
        benchmark_name="herbertsmithite_kagome_qsl_reference",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Neutron diffraction",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": "qsl_candidate",
            "claim_context": "primary_experimental",
            "units": "not_applicable",
        },
    )

    assert trace.payload["typed_claim"]["subject"] == "ZnCu3(OH)6Cl2"
    assert trace.payload["typed_claim"]["observable"] == "spin liquid behavior"


def test_typed_claim_parser_extracts_primary_model_claim_without_material_inference():
    source = _verified_text_source(
        "Results\n"
        "Exact diagonalization establishes Kitaev_honeycomb model gapless phase "
        "at zero field.\n"
    )

    trace = parse_source_target(
        benchmark_name="kitaev_honeycomb_exact_spin_liquid_limit",
        source=source,
        locator={
            "kind": "body_text",
            "anchor": "Exact diagonalization",
            "occurrence": 1,
        },
        parser={
            "kind": "typed_claim",
            "field_id": "is_exactly_solvable",
            "claim_context": "primary_model",
            "units": "not_applicable",
        },
    )

    assert trace.payload["normalized_value"] == {"is_exactly_solvable": True}
    assert trace.payload["typed_claim"] == {
        "kind": "categorical",
        "subject": "Kitaev_honeycomb",
        "observable": "gapless phase",
        "scope": "model",
        "polarity": "affirmed",
        "qualifier": "establishes",
        "method": "exact_diagonalization",
        "source_role": "primary_theoretical",
        "conditions": {"field": {"value": 0.0, "units": "T"}},
        "fields": (
            {
                "id": "is_exactly_solvable",
                "type": "boolean",
                "units": "not_applicable",
            },
        ),
    }


@pytest.mark.parametrize(
    ("sentence", "claim_path", "expected"),
    [
        (
            "Neutron diffraction observed beta-RuCl3 material zigzag order "
            "below 7.0(2) K at zero field.",
            ("subject",),
            "beta-RuCl3",
        ),
        (
            "Neutron diffraction observed alpha-RuCl3 material stripy order "
            "below 7.0(2) K at zero field.",
            ("observable",),
            "stripy order",
        ),
        (
            "Neutron diffraction observed alpha-RuCl3 material zigzag order "
            "above 20.0(5) K at zero field.",
            ("conditions", "temperature", "relation"),
            "above",
        ),
        (
            "Neutron diffraction observed alpha-RuCl3 material zigzag order "
            "above 20.0(5) K at zero field.",
            ("conditions", "temperature", "value"),
            20.0,
        ),
        (
            "Neutron diffraction observed alpha-RuCl3 material zigzag order "
            "above 20.0(5) K at zero field.",
            ("conditions", "temperature", "uncertainty"),
            0.5,
        ),
    ],
)
def test_typed_claim_source_mutations_change_extracted_components(
    sentence, claim_path, expected
):
    trace = _parse_primary_claim(sentence)
    value = trace.payload["typed_claim"]
    for key in claim_path:
        value = value[key]
    assert value == expected


def test_typed_claim_polarity_mutation_changes_boolean_operand():
    trace = _parse_primary_claim(
        "Neutron diffraction did not observe alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )

    assert trace.payload["typed_claim"]["polarity"] == "negated"
    assert trace.payload["normalized_value"] == {"zigzag_order": False}


@pytest.mark.parametrize(
    ("sentence", "message"),
    [
        (
            "Neutron diffraction observed alpha-RuCl3 model zigzag order "
            "below 7.0(2) K at zero field.",
            "cannot be inferred",
        ),
        (
            "Neutron diffraction suggested alpha-RuCl3 material zigzag order "
            "below 7.0(2) K at zero field.",
            "not primary experimental",
        ),
        (
            "Neutron diffraction measured alpha-RuCl3 material below 7 K.",
            "must directly bind",
        ),
        (
            "This review reports that Neutron diffraction observed alpha-RuCl3 "
            "material zigzag order below 7.0(2) K at zero field.",
            "must directly bind",
        ),
    ],
)
def test_typed_claim_rejects_inference_absence_and_review_paraphrase(sentence, message):
    with pytest.raises(SourceParserError, match=message):
        _parse_primary_claim(sentence)


def test_primary_claim_rejects_review_bibliographic_provenance():
    sentence = (
        "Neutron diffraction observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n" + sentence + "\n")
    review_provenance = replace(
        source.provenance,
        bibliographic_metadata={"title": "A review of frustrated magnets"},
    )
    review_source = replace(source, provenance=review_provenance)

    with pytest.raises(SourceParserError, match="review bibliographic provenance"):
        parse_source_target(
            benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
            source=review_source,
            locator={
                "kind": "body_text",
                "anchor": "Neutron diffraction",
                "occurrence": 1,
            },
            parser={
                "kind": "typed_claim",
                "field_id": "zigzag_order",
                "claim_context": "primary_experimental",
                "units": "not_applicable",
            },
        )


def test_primary_claim_requires_positive_payload_bound_source_role_verification():
    sentence = (
        "Neutron diffraction observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n" + sentence + "\n")
    unverified_provenance = replace(
        source.provenance,
        bibliographic_metadata={
            "title": "Frustrated magnets: a perspective",
        },
        citation_metadata_verification={"verified": True},
    )
    unverified_source = replace(source, provenance=unverified_provenance)

    with pytest.raises(SourceParserError, match="positive source-role verification"):
        parse_source_target(
            benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
            source=unverified_source,
            locator={
                "kind": "body_text",
                "anchor": "Neutron diffraction",
                "occurrence": 1,
            },
            parser={
                "kind": "typed_claim",
                "field_id": "zigzag_order",
                "claim_context": "primary_experimental",
                "units": "not_applicable",
            },
        )


def test_primary_claim_rejects_title_mutation_against_role_attestation():
    sentence = (
        "Neutron diffraction observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n" + sentence + "\n")
    mutated_provenance = replace(
        source.provenance,
        bibliographic_metadata={
            "title": "Frustrated magnets: a perspective",
        },
    )
    mutated_source = replace(source, provenance=mutated_provenance)

    with pytest.raises(SourceParserError, match="title hash mismatch"):
        parse_source_target(
            benchmark_name="alpha_rucl3_kitaev_gamma_zigzag_reference",
            source=mutated_source,
            locator={
                "kind": "body_text",
                "anchor": "Neutron diffraction",
                "occurrence": 1,
            },
            parser={
                "kind": "typed_claim",
                "field_id": "zigzag_order",
                "claim_context": "primary_experimental",
                "units": "not_applicable",
            },
        )


def test_primary_claim_rejects_payload_hash_mutation_in_role_attestation():
    sentence = (
        "Neutron diffraction observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n" + sentence + "\n")
    citation_verification = dict(source.provenance.citation_metadata_verification)
    role_verification = dict(citation_verification["source_role_verification"])
    role_verification["raw_payload_sha256"] = "0" * 64
    citation_verification["source_role_verification"] = role_verification
    mutated_source = replace(
        source,
        provenance=replace(
            source.provenance,
            citation_metadata_verification=citation_verification,
        ),
    )

    with pytest.raises(SourceParserError, match="payload hash mismatch"):
        _parse_primary_claim_from_source(mutated_source)


@pytest.mark.parametrize(
    ("role_update", "message"),
    [
        ({"status": "unverified"}, "status is not verified"),
        (
            {"source_roles": ["primary_model"]},
            "does not cover the claim context",
        ),
    ],
)
def test_primary_claim_rejects_unverified_or_wrong_attested_role(role_update, message):
    sentence = (
        "Neutron diffraction observed alpha-RuCl3 material zigzag order "
        "below 7.0(2) K at zero field."
    )
    source = _verified_text_source("Results\n" + sentence + "\n")
    citation_verification = dict(source.provenance.citation_metadata_verification)
    role_verification = dict(citation_verification["source_role_verification"])
    role_verification.update(role_update)
    citation_verification["source_role_verification"] = role_verification
    mutated_source = replace(
        source,
        provenance=replace(
            source.provenance,
            citation_metadata_verification=citation_verification,
        ),
    )

    with pytest.raises(SourceParserError, match=message):
        _parse_primary_claim_from_source(mutated_source)


def test_field_map_combines_independently_located_runtime_subtraces():
    source = _verified_text_source(
        "Results\n"
        "Claim A: transition count = 2\n"
        "Claim B: phase sequence = ordered -> critical -> disordered\n"
    )

    trace = parse_source_target(
        benchmark_name="square_clock_q5_two_bkt_transitions",
        source=source,
        locator={"kind": "field_map"},
        parser={
            "kind": "field_map",
            "fields": [
                {
                    "locator": {
                        "kind": "body_text",
                        "anchor": "Claim A:",
                        "occurrence": 1,
                    },
                    "parser": {
                        "kind": "numeric",
                        "field_id": "transition_count",
                        "value_label": "transition count",
                        "units": "count",
                        "uncertainty": "parenthetical_last_digits",
                    },
                },
                {
                    "locator": {
                        "kind": "body_text",
                        "anchor": "Claim B:",
                        "occurrence": 1,
                    },
                    "parser": {
                        "kind": "sequence",
                        "field_id": "phase_sequence",
                        "value_label": "phase sequence",
                        "delimiter": "->",
                        "item_type": "string",
                        "output_type": "list[string]",
                        "units": "not_applicable",
                    },
                },
            ],
        },
    )

    assert trace.payload["normalized_value"] == {
        "transition_count": 2.0,
        "phase_sequence": ("ordered", "critical", "disordered"),
    }
    assert trace.payload["raw_value"] == {
        "transition_count": "2",
        "phase_sequence": "ordered -> critical -> disordered",
    }
    assert set(trace.payload["value_coordinates"]) == {
        "transition_count",
        "phase_sequence",
    }
    assert set(trace.payload["value_sha256"]) == {
        "transition_count",
        "phase_sequence",
    }
    assert trace.payload["raw_value_sha256"] == trace.payload["value_sha256"]
    assert len(trace.payload["field_traces"]) == 2
    assert trace.payload["typed_claim"]["kind"] == "field_map"
    assert trace.payload["typed_claim"]["claims"]["transition_count"]["kind"] == (
        "numeric"
    )
    assert trace.payload["typed_claim"]["claims"]["phase_sequence"]["kind"] == (
        "sequence"
    )


def test_field_map_rejects_reusing_one_source_value_for_two_output_fields():
    source = _verified_text_source("Claim: transition count = 2\n")
    field_spec = {
        "locator": {"kind": "body_text", "anchor": "Claim:", "occurrence": 1},
        "parser": {
            "kind": "numeric",
            "field_id": "first_count",
            "value_label": "transition count",
            "units": "count",
            "uncertainty": "parenthetical_last_digits",
        },
    }
    second_field_spec = {
        "locator": dict(field_spec["locator"]),
        "parser": {**field_spec["parser"], "field_id": "second_count"},
    }

    with pytest.raises(SourceParserError, match="duplicate field_map value span"):
        parse_source_target(
            benchmark_name="square_clock_q5_two_bkt_transitions",
            source=source,
            locator={"kind": "field_map"},
            parser={"kind": "field_map", "fields": [field_spec, second_field_spec]},
        )


def test_real_pdf_analytic_equation_layout_is_parsed_from_verified_payload():
    source = _cached_authoritative_source("arxiv_dbdd4b586780cd708b67")

    trace = parse_source_target(
        benchmark_name="single_ion_spin1_anisotropy_levels",
        source=source,
        locator={
            "kind": "equation",
            "label": "HSi Sj =",
            "occurrence": 1,
        },
        parser={
            "kind": "equation",
            "field_id": "bond_hamiltonian",
            "value_label": "HSi Sj",
            "units": "exchange_energy_unit",
        },
    )

    assert trace.payload["source_sha256"] == source.payload_sha256
    assert trace.payload["raw_value"] == (
        "HSi Sj = −JSi Sj + D(Si2 + Sj2 )/q − h(Si + Sj )/q"
    )
    assert trace.payload["normalized_value"] == {
        "bond_hamiltonian": {
            "lhs": "HSi Sj",
            "relation": "=",
            "rhs": "-JSi Sj + D(Si2 + Sj2 )/q - h(Si + Sj )/q",
        }
    }
    assert trace.payload["unit_evidence"]["raw_units"] == (trace.payload["raw_value"])
    assert (
        trace.payload["value_sha256"]
        == hashlib.sha256(trace.payload["raw_value"].encode("utf-8")).hexdigest()
    )


def test_bare_numbered_equation_source_mutation_changes_runtime_expression():
    def parse_rhs(rhs):
        source = _verified_text_source(f"H = {rhs}, (6)\n")
        return parse_source_target(
            benchmark_name="single_ion_spin1_anisotropy_levels",
            source=source,
            locator={"kind": "equation", "label": "H =", "occurrence": 1},
            parser={
                "kind": "equation",
                "field_id": "bond_hamiltonian",
                "value_label": "H",
                "units": "exchange_energy_unit",
            },
        )

    original = parse_rhs("-J*S1*S2")
    mutated = parse_rhs("-2*J*S1*S2")

    assert original.payload["normalized_value"] == {
        "bond_hamiltonian": {
            "lhs": "H",
            "relation": "=",
            "rhs": "-J*S1*S2",
        }
    }
    assert mutated.payload["normalized_value"] == {
        "bond_hamiltonian": {
            "lhs": "H",
            "relation": "=",
            "rhs": "-2*J*S1*S2",
        }
    }
    assert original.payload["value_sha256"] != mutated.payload["value_sha256"]


def test_real_pdf_fixed_width_qmc_table_number_preserves_aps_uncertainty():
    source = _cached_authoritative_source("doi_ebcdccab3f81a5059936")

    trace = parse_source_target(
        benchmark_name="square_heisenberg_qmc_energy_reference",
        source=source,
        locator={
            "kind": "table",
            "label": "TABLE II. QMC results for the ground-state energy",
            "occurrence": 1,
            "layout": "fixed_width",
            "header": (
                "L                   2E                         "
                "S( p , p )               C(L/2,L/2)"
            ),
            "row_label": "16",
            "value_column": "2E",
            "unit_anchor": "state energy per spin",
            "unit_anchor_occurrence": 1,
        },
        parser={
            "kind": "table_numeric",
            "field_id": "finite_size_minus_energy_per_spin",
            "units": "exchange_energy_per_spin",
            "uncertainty": "aps_pdftotext_parenthetical",
            "value_convention": "aps_pdftotext_minus_observable_magnitude",
            "unit_evidence": {
                "kind": "source_statements",
                "anchors": [
                    {"text": "state energy per spin", "occurrence": 1},
                    {
                        "text": "from the Hamiltonian written as (J51)",
                        "occurrence": 1,
                    },
                ],
            },
        },
    )

    assert trace.payload["raw_value"] == "0.669976~7!"
    assert trace.payload["normalized_value"] == {
        "finite_size_minus_energy_per_spin": 0.669976
    }
    assert trace.payload["typed_claim"]["fields"][0]["uncertainty"] == (0.000007)
    assert trace.payload["typed_claim"]["fields"][0]["convention"] == (
        "source_column_minus_energy_magnitude"
    )
    assert trace.payload["table_coordinates"] == {
        "table_label": "TABLE II. QMC results for the ground-state energy",
        "row_label": "16",
        "row_number": 7,
        "value_column": "2E",
        "value_column_number": 2,
        "layout": "fixed_width",
        "value_convention": "source_column_minus_energy_magnitude",
    }
    assert trace.payload["unit_evidence"]["raw_units"] == (
        "state energy per spin",
        "from the Hamiltonian written as (J51)",
    )
    assert len(trace.payload["unit_evidence"]["source_fragments"]) == 2


def test_fixed_width_table_source_mutation_changes_value_and_uncertainty():
    header = "L                   2E                         S"

    def parse_cell(cell):
        source = _verified_text_source(
            "The state energy per spin is tabulated.\n"
            "The Hamiltonian uses J as the exchange energy unit.\n"
            "TABLE II. QMC results\n"
            f"{header}\n"
            f"16             {cell}                    11.352~2!\n"
        )
        return parse_source_target(
            benchmark_name="square_heisenberg_qmc_energy_reference",
            source=source,
            locator={
                "kind": "table",
                "label": "TABLE II. QMC results",
                "occurrence": 1,
                "layout": "fixed_width",
                "header": header,
                "row_label": "16",
                "value_column": "2E",
                "unit_anchor": "state energy per spin",
                "unit_anchor_occurrence": 1,
            },
            parser={
                "kind": "table_numeric",
                "field_id": "finite_size_minus_energy_per_spin",
                "units": "exchange_energy_per_spin",
                "uncertainty": "aps_pdftotext_parenthetical",
                "value_convention": ("aps_pdftotext_minus_observable_magnitude"),
                "unit_evidence": {
                    "kind": "source_statements",
                    "anchors": [
                        {"text": "state energy per spin", "occurrence": 1},
                        {
                            "text": (
                                "The Hamiltonian uses J as the exchange " "energy unit."
                            ),
                            "occurrence": 1,
                        },
                    ],
                },
            },
        )

    original = parse_cell("0.669976~7!")
    mutated = parse_cell("0.671234~9!")

    assert original.payload["normalized_value"] == {
        "finite_size_minus_energy_per_spin": 0.669976
    }
    assert mutated.payload["normalized_value"] == {
        "finite_size_minus_energy_per_spin": 0.671234
    }
    assert original.payload["typed_claim"]["fields"][0]["uncertainty"] == (0.000007)
    assert mutated.payload["typed_claim"]["fields"][0]["uncertainty"] == (0.000009)


def test_fixed_width_table_rejects_malformed_aps_uncertainty_cell():
    header = "L                   2E                         S"
    source = _verified_text_source(
        "The state energy per spin is tabulated.\n"
        "TABLE II. QMC results\n"
        f"{header}\n"
        "16             0.669976oops                  11.352~2!\n"
    )

    with pytest.raises(
        SourceParserError,
        match="lacks encoded parenthetical uncertainty",
    ):
        parse_source_target(
            benchmark_name="square_heisenberg_qmc_energy_reference",
            source=source,
            locator={
                "kind": "table",
                "label": "TABLE II. QMC results",
                "occurrence": 1,
                "layout": "fixed_width",
                "header": header,
                "row_label": "16",
                "value_column": "2E",
                "unit_anchor": "state energy per spin",
                "unit_anchor_occurrence": 1,
            },
            parser={
                "kind": "table_numeric",
                "field_id": "finite_size_minus_energy_per_spin",
                "units": "exchange_energy_per_spin",
                "uncertainty": "aps_pdftotext_parenthetical",
                "value_convention": ("aps_pdftotext_minus_observable_magnitude"),
            },
        )


def test_real_pdf_dmrg_phase_window_uses_clause_boundaries_not_corrupt_glyphs():
    source = _cached_authoritative_source("doi_10f8d8a847e8ffd6e766")

    trace = parse_source_target(
        benchmark_name="j1_j2_triangular_spin_liquid_window_reference",
        source=source,
        locator={
            "kind": "body_text",
            "start_anchor": "By means of DMRG calcula-",
            "start_occurrence": 1,
            "end_anchor": "small correlation lengths",
            "end_occurrence": 1,
        },
        parser={
            "kind": "interval",
            "field_id": "spin_liquid_window_approx",
            "region_label": "we find a SL region bordered by",
            "variable": "J2",
            "lower_phase_anchor": "a 120◦ N´eel AF phase",
            "upper_phase_anchor": "a stripe AF phase",
            "normalization_anchor": "We set J1 = 1 as the energy scale.",
            "units": "dimensionless_j2_over_j1",
            "output_type": "list[number]",
        },
    )

    assert trace.payload["normalized_value"] == {
        "spin_liquid_window_approx": (0.07, 0.15)
    }
    assert trace.payload["typed_claim"]["bounds"] == {
        "lower": 0.07,
        "upper": 0.15,
        "boundary_semantics": "source_approximate_phase_borders",
        "lower_relation_token": "\x02",
        "upper_relation_token": "\x03",
    }
    assert trace.payload["raw_value"].startswith("0.07 and a stripe AF phase")
    assert trace.payload["raw_value"].endswith("0.15")
    assert trace.payload["unit_evidence"]["raw_units"] == (
        "We set J1 = 1 as the energy scale."
    )


def test_bordered_phase_window_mutation_changes_both_runtime_endpoints():
    parser = {
        "kind": "interval",
        "field_id": "spin_liquid_window_approx",
        "region_label": "we find a SL region bordered by",
        "variable": "J2",
        "lower_phase_anchor": "a 120 degree Neel AF phase",
        "upper_phase_anchor": "a stripe AF phase",
        "normalization_anchor": "We set J1 = 1 as the energy scale.",
        "units": "dimensionless_j2_over_j1",
        "output_type": "list[number]",
    }

    def parse_window(lower, upper, lower_relation="\x02", upper_relation="\x03"):
        source = _verified_text_source(
            "We set J1 = 1 as the energy scale.\n"
            "By DMRG, we find a SL region bordered by a 120 degree Neel AF "
            f"phase for J2 {lower_relation} {lower} and a stripe AF phase "
            f"for J2 {upper_relation} {upper}. End of claim.\n"
        )
        return parse_source_target(
            benchmark_name="j1_j2_triangular_spin_liquid_window_reference",
            source=source,
            locator={
                "kind": "body_text",
                "start_anchor": "By DMRG",
                "start_occurrence": 1,
                "end_anchor": "End of claim.",
                "end_occurrence": 1,
            },
            parser=parser,
        )

    original = parse_window("0.07", "0.15")
    mutated = parse_window("0.08", "0.17")

    assert original.payload["normalized_value"] == {
        "spin_liquid_window_approx": (0.07, 0.15)
    }
    assert mutated.payload["normalized_value"] == {
        "spin_liquid_window_approx": (0.08, 0.17)
    }
    assert original.payload["raw_value_sha256"] != (mutated.payload["raw_value_sha256"])


def test_bordered_phase_window_rejects_unknown_relation_or_reversed_bounds():
    parser = {
        "kind": "interval",
        "field_id": "spin_liquid_window_approx",
        "region_label": "we find a SL region bordered by",
        "variable": "J2",
        "lower_phase_anchor": "a Neel phase",
        "upper_phase_anchor": "a stripe phase",
        "normalization_anchor": "We set J1 = 1 as the energy scale.",
        "units": "dimensionless_j2_over_j1",
        "output_type": "list[number]",
    }

    def source_for(lower_relation, lower, upper_relation, upper):
        return _verified_text_source(
            "We set J1 = 1 as the energy scale.\n"
            "Claim: we find a SL region bordered by a Neel phase for J2 "
            f"{lower_relation} {lower} and a stripe phase for J2 "
            f"{upper_relation} {upper}. End.\n"
        )

    locator = {
        "kind": "body_text",
        "start_anchor": "Claim:",
        "start_occurrence": 1,
        "end_anchor": "End.",
        "end_occurrence": 1,
    }
    for lower_relation, upper_relation, message in (
        ("?", ">", "unsupported lower"),
        ("\x01", ">", "unsupported lower"),
        ("<", "\x04", "unsupported upper"),
    ):
        with pytest.raises(SourceParserError, match=message):
            parse_source_target(
                benchmark_name="j1_j2_triangular_spin_liquid_window_reference",
                source=source_for(lower_relation, "0.07", upper_relation, "0.15"),
                locator=locator,
                parser=parser,
            )
    with pytest.raises(SourceParserError, match="strictly ordered"):
        parse_source_target(
            benchmark_name="j1_j2_triangular_spin_liquid_window_reference",
            source=source_for("<", "0.15", ">", "0.07"),
            locator=locator,
            parser=parser,
        )


def test_real_pdf_direct_experimental_claim_is_role_gated_and_source_bound():
    unreviewed_source = _cached_authoritative_source("doi_30de47257cfae45dcfca")
    locator = {
        "kind": "abstract",
        "start_anchor": "We present a specific heat",
        "start_occurrence": 1,
        "end_anchor": "dimer-monomer state",
        "end_occurrence": 1,
    }
    parser = {
        "kind": "typed_claim",
        "field_id": "one_third_magnetization_plateau",
        "claim_context": "primary_experimental",
        "claim_syntax": "reported_material_finding",
        "subject_anchor": "azurite",
        "method_anchor": "specific heat and inelastic neutron scattering",
        "observable_anchor": "1=3 magnetization plateau phase",
        "finding_anchor": (
            "We establish that the magnetization plateau is a " "dimer-monomer state"
        ),
        "condition_anchor": (
            "magnetic fields up into the 1=3 magnetization plateau phase"
        ),
        "units": "not_applicable",
    }

    with pytest.raises(
        SourceParserError,
        match="requires positive source-role verification",
    ):
        parse_source_target(
            benchmark_name="azurite_diamond_chain_plateau_reference",
            source=unreviewed_source,
            locator=locator,
            parser=parser,
        )

    source = _with_source_role(unreviewed_source, "primary_experimental")
    trace = parse_source_target(
        benchmark_name="azurite_diamond_chain_plateau_reference",
        source=source,
        locator=locator,
        parser=parser,
    )

    assert trace.payload["normalized_value"] == {
        "one_third_magnetization_plateau": True
    }
    assert trace.payload["typed_claim"] == {
        "kind": "categorical",
        "subject": "azurite",
        "observable": "1=3 magnetization plateau phase",
        "scope": "material",
        "polarity": "affirmed",
        "qualifier": "establishes",
        "method": "specific_heat_and_inelastic_neutron_scattering",
        "source_role": "primary_experimental",
        "conditions": {
            "source_statement": (
                "magnetic fields up into the 1=3 magnetization plateau phase"
            )
        },
        "fields": (
            {
                "id": "one_third_magnetization_plateau",
                "type": "boolean",
                "units": "not_applicable",
            },
        ),
    }
    assert trace.payload["raw_value"] == trace.payload["excerpt"]
    assert trace.payload["source_role_verification"]["raw_payload_sha256"] == (
        source.payload_sha256
    )


def test_reported_material_finding_rejects_model_scope_and_suggestion():
    base = (
        "We present a specific heat and inelastic neutron scattering study in "
        "magnetic fields up into the 1=3 magnetization plateau phase of the "
        "diamond chain {scope} azurite. {finding} End.\n"
    )
    locator = {
        "kind": "abstract",
        "start_anchor": "We present a specific heat",
        "start_occurrence": 1,
        "end_anchor": "End.",
        "end_occurrence": 1,
    }

    def parser_for(finding):
        return {
            "kind": "typed_claim",
            "field_id": "one_third_magnetization_plateau",
            "claim_context": "primary_experimental",
            "claim_syntax": "reported_material_finding",
            "subject_anchor": "azurite",
            "method_anchor": ("specific heat and inelastic neutron scattering"),
            "observable_anchor": "1=3 magnetization plateau phase",
            "finding_anchor": finding,
            "condition_anchor": (
                "magnetic fields up into the 1=3 magnetization plateau phase"
            ),
            "units": "not_applicable",
        }

    direct_finding = (
        "We establish that the magnetization plateau is a dimer-monomer state."
    )
    for nonmaterial_scope in (
        "model",
        "immaterial model",
        "material model",
        "system",
    ):
        with pytest.raises(SourceParserError, match="material-scope marker"):
            parse_source_target(
                benchmark_name="azurite_diamond_chain_plateau_reference",
                source=_verified_text_source(
                    base.format(
                        scope=nonmaterial_scope,
                        finding=direct_finding,
                    )
                ),
                locator=locator,
                parser=parser_for(direct_finding),
            )

    suggested_finding = (
        "We suggest that the magnetization plateau is a dimer-monomer state."
    )
    with pytest.raises(SourceParserError, match="not a direct experimental"):
        parse_source_target(
            benchmark_name="azurite_diamond_chain_plateau_reference",
            source=_verified_text_source(
                base.format(scope="compound", finding=suggested_finding)
            ),
            locator=locator,
            parser=parser_for(suggested_finding),
        )


def test_parser_api_has_no_expected_or_registry_operand_parameter():
    parameter_names = set(inspect.signature(parse_source_target).parameters)

    assert parameter_names == {"benchmark_name", "source", "locator", "parser"}
    assert not any(
        marker in name
        for name in parameter_names
        for marker in ("expected", "target_value", "registry", "verdict")
    )


def test_parser_contract_maps_every_provisional_record_shape_to_runtime_dispatch():
    records_root = (
        Path(__file__).resolve().parents[1]
        / "reference"
        / "literature-evidence"
        / "records"
    )
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(records_root.glob("*.json"))
    ]
    output_types = {
        field["type"]
        for record in records
        for field in record["parser_strategy"]["output_fields"]
    }
    locator_classes = {
        record["target_locator_strategy"]["locator_class"] for record in records
    }
    multi_field_records = [
        record
        for record in records
        if len(record["parser_strategy"]["output_fields"]) > 1
    ]

    assert len(records) == 155
    assert output_types == parser_module.SUPPORTED_RECORD_OUTPUT_TYPES
    assert output_types == set(parser_module.PARSER_KINDS_BY_RECORD_OUTPUT_TYPE)
    assert locator_classes == set(parser_module.PARSER_KINDS_BY_RECORD_LOCATOR_CLASS)
    for record in records:
        locator_class = record["target_locator_strategy"]["locator_class"]
        locator_parser_kinds = parser_module.PARSER_KINDS_BY_RECORD_LOCATOR_CLASS[
            locator_class
        ]
        assert locator_parser_kinds
        for field in record["parser_strategy"]["output_fields"]:
            parser_kinds = parser_module.PARSER_KINDS_BY_RECORD_OUTPUT_TYPE[
                field["type"]
            ]
            assert parser_kinds
            assert parser_kinds <= parser_module.SUPPORTED_PARSER_KINDS
            assert locator_parser_kinds & parser_kinds, (
                record["benchmark_name"],
                locator_class,
                field["type"],
            )
    assert multi_field_records
    assert "field_map" in parser_module.SUPPORTED_PARSER_KINDS
    assert (
        set(parser_module._LEAF_TARGET_PARSERS)
        | {
            "field_map",
            "table_numeric",
        }
        == parser_module.SUPPORTED_PARSER_KINDS
    )


@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("expected_value", 0.4105),
        ("registry_operand", {"gap_over_j": 0.4105}),
        ("parsed_target", 0.4105),
        ("verdict", True),
    ],
)
def test_parser_rejects_answer_shaped_inputs_explicitly(forbidden_key, forbidden_value):
    source = _verified_text_source("Eq. (3): gap/J = 0.41050(2)\n")
    parser = {
        "kind": "numeric",
        "field_id": "gap_over_j",
        "value_label": "gap/J",
        "units": "dimensionless_ratio",
        "uncertainty": "parenthetical_last_digits",
        forbidden_key: forbidden_value,
    }

    with pytest.raises(
        SourceParserError,
        match=rf"forbidden parser input key {forbidden_key}",
    ):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=source,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser=parser,
        )


def test_parser_rejects_payload_hash_mismatch_before_target_extraction():
    source = _verified_text_source("Eq. (3): gap/J = 0.41050(2)\n")
    tampered = replace(source, payload_bytes=b"tampered payload")

    with pytest.raises(SourceParserError, match="payload hash mismatch"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=tampered,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap_over_j",
                "value_label": "gap/J",
                "units": "dimensionless_ratio",
                "uncertainty": "parenthetical_last_digits",
            },
        )


def test_parser_rejects_extracted_text_not_derived_from_verified_payload():
    source = _verified_text_source("Eq. (3): gap/J = 0.41050(2)\n")
    tampered = replace(
        source,
        extracted_text="Eq. (3): gap/J = 9.99999(1)\n",
    )

    with pytest.raises(SourceParserError, match="deterministic payload extraction"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=tampered,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap_over_j",
                "value_label": "gap/J",
                "units": "dimensionless_ratio",
                "uncertainty": "parenthetical_last_digits",
            },
        )


def test_parser_fails_closed_when_the_runtime_target_is_removed():
    source = _verified_text_source("Eq. (3): the gap is discussed qualitatively\n")

    with pytest.raises(SourceParserError, match="does not contain a numeric value"):
        parse_source_target(
            benchmark_name="haldane_spin1_chain_gap_reference",
            source=source,
            locator={"kind": "equation", "label": "Eq. (3)", "occurrence": 1},
            parser={
                "kind": "numeric",
                "field_id": "gap_over_j",
                "value_label": "gap/J",
                "units": "dimensionless_ratio",
                "uncertainty": "parenthetical_last_digits",
            },
        )
