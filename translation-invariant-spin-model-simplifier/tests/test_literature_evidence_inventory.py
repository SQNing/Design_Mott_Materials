import copy
import ast
import json
import shutil
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_inventory import (
    INVENTORY_ROOT,
    InventoryError,
    build_inventory_data,
    canonical_source_identity,
    derive_unresolved_status,
    load_canonical_observable_specs,
    load_and_validate_inventory,
    resolve_registry_selector,
    validate_inventory,
)
from validation.literature_evidence_schema import (
    EvidenceSchemaError,
    EvidenceRecord,
    ProvisionalEvidenceRecord,
)
from validation.literature_evidence_sources import authoritative_route_for_identity
from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS


@pytest.fixture(scope="module")
def loaded_inventory():
    return load_and_validate_inventory()


def mutable_inventory(loaded_inventory):
    return copy.deepcopy(loaded_inventory.as_plain_data())


def test_inventory_has_exact_registry_contract_record_and_locator_name_sets(
    loaded_inventory,
):
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    contract_names = {
        contract.benchmark_name for contract in loaded_inventory.contracts
    }
    record_names = {record.benchmark_name for record in loaded_inventory.records}
    locator_names = {
        row["benchmark_name"] for row in loaded_inventory.locator_inventory
    }
    filenames = {path.stem for path in (INVENTORY_ROOT / "records").glob("*.json")}

    assert len(registry_names) == 155
    assert len(loaded_inventory.contracts) == 155
    assert len(loaded_inventory.records) == 155
    assert len(loaded_inventory.locator_inventory) == 155
    assert filenames == registry_names == contract_names == record_names == locator_names


def test_contracts_define_complete_concrete_claim_identity(loaded_inventory):
    generic_observables = {
        "material_reference",
        "material_model_reference",
        "phase_diagram_reference",
        "phase_reference",
        "status",
    }
    required = {
        "subject",
        "system",
        "hamiltonian",
        "parameter_regime",
        "size_or_limit",
        "observable",
        "representation",
        "units",
        "conditions",
    }
    for contract in loaded_inventory.contracts:
        assert required <= set(contract.as_plain_data())
        assert contract.observable["identity"] not in generic_observables
        assert contract.observable["claim_fields"]
        assert {
            field["id"] for field in contract.representation["fields"]
        } == set(contract.observable["claim_fields"])


def test_contracts_reject_all_generic_placeholder_families(loaded_inventory):
    forbidden_exact = {
        "Registered literature claim identified by named fields",
        "multi_field_registered_claim",
        "source_defined_registered_regime",
        "registry_defined_or_dimensionless",
    }
    forbidden_patterns = ("registered literature claim", "source_defined", "registry_defined")
    subjects = []
    for contract in loaded_inventory.contracts:
        plain = contract.as_plain_data()
        subjects.append(contract.subject)
        checked = (
            contract.subject,
            contract.observable["identity"],
            contract.size_or_limit["category"],
            contract.units,
        )
        assert forbidden_exact.isdisjoint(checked)
        assert not any(
            pattern in value.lower()
            for value in checked
            for pattern in forbidden_patterns
        )
        assert not contract.observable["identity"].startswith(
            ("published_observable_", "material_model_", "phase_diagram_")
        )
        assert all(
            "under the declared parameter regime" not in semantic
            and "published published observable" not in semantic
            for semantic in contract.observable["semantics"]
        )
        for field in contract.representation["fields"]:
            assert field["units"]
            assert field["convention"]
    assert len(set(subjects)) == 155


def test_every_benchmark_has_an_explicit_canonical_observable_spec():
    registry_names = {entry["name"] for entry in LITERATURE_STANDARD_RESULTS}
    specs = load_canonical_observable_specs()
    assert set(specs) == registry_names
    for name, spec in specs.items():
        assert set(spec) == {"identity", "primary_semantic"}, name
        assert spec["identity"].strip()
        assert spec["primary_semantic"].strip()
        assert not spec["identity"].endswith(
            ("_reference", "_candidate", "_status", "_claim")
        )


@pytest.mark.parametrize(
    "placeholder_identity",
    [
        "material_reference",
        "spin_liquid_candidate",
        "plaquette_order_candidate",
        "phase_status",
        "published_claim",
    ],
)
def test_inventory_rejects_status_like_observable_identities(
    loaded_inventory, placeholder_identity
):
    data = mutable_inventory(loaded_inventory)
    contract = data["contracts"][0]
    contract["observable"]["identity"] = placeholder_identity
    with pytest.raises(InventoryError, match="generic observable identity"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_representative_placeholder_fields_expand_to_scientific_observables(
    loaded_inventory,
):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }
    expected = {
        "ba3irti2o9_honeycomb_kitaev_reference": (
            "assessment_of_spin_liquid_behavior_in_ba3irti2o9",
            "published material-scale assessment of spin-liquid behavior",
        ),
        "herbertsmithite_kagome_qsl_reference": (
            "assessment_of_quantum_spin_liquid_behavior_in_herbertsmithite",
            "published experimental assessment of quantum-spin-liquid behavior",
        ),
        "checkerboard_heisenberg_plaquette_reference": (
            "assessment_of_plaquette_valence_bond_order_in_checkerboard_heisenberg_model",
            "published assessment of plaquette valence-bond order",
        ),
        "j1_j2_square_spin_half_neel_collinear_transition_reference": (
            "nonmagnetic_phase_window_in_j2_over_j1",
            "approximate nonmagnetic-phase interval in the J2/J1 coupling ratio",
        ),
        "two_dimensional_xy_bkt_universal_jump": (
            "universal_bkt_helicity_modulus_jump_relation",
            "universal relation between helicity modulus and transition temperature",
        ),
    }
    for benchmark_name, (identity, semantic) in expected.items():
        contract = contracts[benchmark_name]
        assert contract.observable["identity"] == identity
        assert semantic in contract.observable["semantics"]
        assert contract.conditions["physical_regime"]
        assert contract.conditions["source_claim_scope"]
        assert contract.conditions["model_parameters"] == contract.parameter_regime


def test_scientific_sequence_and_normalization_conventions_are_distinct(
    loaded_inventory,
):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }

    j1_j2 = contracts[
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    ]
    nonmagnetic_window = j1_j2.representation["fields"][0]
    assert nonmagnetic_window == {
        "id": "nonmagnetic_window_approx",
        "type": "list[number]",
        "units": "dimensionless_j2_over_j1",
        "convention": "closed_interval_endpoints_in_ascending_j2_over_j1",
    }

    bkt = contracts["two_dimensional_xy_bkt_universal_jump"]
    bkt_fields = {field["id"]: field for field in bkt.representation["fields"]}
    assert bkt_fields["helicity_modulus_at_t_1"] == {
        "id": "helicity_modulus_at_t_1",
        "type": "number",
        "units": "helicity_modulus_over_exchange_j",
        "convention": "rho_s_over_j_at_temperature_over_j_equal_one",
    }
    normalization = bkt.conditions["normalization_relation"]
    assert tuple(normalization["normalized_quantities"]) == ("rho_s/J", "T/J")
    assert normalization["universal_coefficient"] == (
        "must_be_parsed_from_authoritative_source"
    )

    expected_nonfallback = {
        "aklt_tan_theta": (
            "dimensionless_tangent_of_bilinear_biquadratic_angle",
            "tan_theta_in_declared_hamiltonian_parameterization",
        ),
        "spin_liquid_window_approx": (
            "dimensionless_j2_over_j1",
            "closed_interval_endpoints_in_ascending_j2_over_j1",
        ),
        "ground_state_spin_per_unit_cell": (
            "spin_angular_momentum_hbar",
            "total_ground_state_spin_per_crystallographic_unit_cell",
        ),
        "degenerate_dimer_coverings": (
            "count",
            "nonnegative_integer_number_of_exact_dimer_coverings",
        ),
        "ising_critical_field": (
            "field_over_exchange_j",
            "critical_transverse_field_normalized_by_exchange_j",
        ),
    }
    observed = {
        field["id"]: (field["units"], field["convention"])
        for contract in loaded_inventory.contracts
        for field in contract.representation["fields"]
        if field["id"] in expected_nonfallback
    }
    assert observed == expected_nonfallback
    forbidden_fallbacks = {
        "field_dependent_sequence",
        "scalar_or_structured_claim",
        "dimensionless_sequence",
        "dimensionless_observable",
        "ordered_values_under_declared_convention",
        "scalar_under_declared_hamiltonian_convention",
    }
    assert not {
        field[key]
        for contract in loaded_inventory.contracts
        for field in contract.representation["fields"]
        for key in ("units", "convention")
    }.intersection(forbidden_fallbacks)

    phase_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "phases" for field in item.representation["fields"])
    )
    phase_field = next(
        field for field in phase_contract.representation["fields"] if field["id"] == "phases"
    )
    assert phase_field["units"] == "not_applicable"
    assert phase_field["convention"] == "categorical_phase_label_set"

    coupling_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "couplings" for field in item.representation["fields"])
    )
    coupling_field = next(
        field
        for field in coupling_contract.representation["fields"]
        if field["id"] == "couplings"
    )
    assert coupling_field["units"] == "source_declared_coupling_units"
    assert coupling_field["convention"] == "named_hamiltonian_coupling_parameter_map"

    degeneracy_contract = next(
        item
        for item in loaded_inventory.contracts
        if any(field["id"] == "degeneracies" for field in item.representation["fields"])
    )
    degeneracy_field = next(
        field
        for field in degeneracy_contract.representation["fields"]
        if field["id"] == "degeneracies"
    )
    assert degeneracy_field["units"] == "count"
    assert degeneracy_field["convention"] == "ordered_nonnegative_integer_degeneracies"


def test_selectors_equal_literal_registry_claim_fields(loaded_inventory):
    literal_fields = _literal_registry_claim_fields()
    assert len(literal_fields) == 155
    for record in loaded_inventory.records:
        assert tuple(record.registry_selector["fields"]) == literal_fields[
            record.benchmark_name
        ]


def test_haldane_selector_excludes_runtime_curie_weiss_augmentation(loaded_inventory):
    record = next(
        item
        for item in loaded_inventory.records
        if item.benchmark_name == "haldane_spin1_chain_gap_reference"
    )
    contract = next(
        item
        for item in loaded_inventory.contracts
        if item.benchmark_name == record.benchmark_name
    )
    assert tuple(record.registry_selector["fields"]) == ("gap_over_j",)
    assert contract.observable["claim_fields"] == ("gap_over_j",)
    assert contract.subject == "Spin-1 Heisenberg-chain Haldane excitation gap"
    assert contract.size_or_limit["category"] == "thermodynamic_limit"
    assert contract.representation["fields"][0]["units"] == "dimensionless_ratio"


@pytest.mark.parametrize(
    ("benchmark_name", "subject_terms", "scope_category"),
    [
        (
            "aklt_spin1_chain_projector_ground_state",
            {"aklt", "projector", "ground", "state"},
            "exact_model_limit",
        ),
        (
            "xxz_spin_half_chain_phase_boundaries",
            {"xxz", "phase", "boundaries"},
            "thermodynamic_limit",
        ),
        (
            "square_spin_half_heisenberg_qmc_energy",
            {"square", "heisenberg", "qmc", "energy"},
            "thermodynamic_limit",
        ),
        (
            "alpha_rucl3_kitaev_gamma_zigzag_reference",
            {"alpha", "rucl3", "kitaev", "zigzag"},
            "published_experimental_material_conditions_pending_source_verification",
        ),
    ],
)
def test_representative_contract_categories_are_concrete(
    loaded_inventory, benchmark_name, subject_terms, scope_category
):
    contract = next(
        item for item in loaded_inventory.contracts if item.benchmark_name == benchmark_name
    )
    normalized_subject = set(contract.subject.lower().replace("-", " ").split())
    assert subject_terms <= normalized_subject
    assert contract.size_or_limit["category"] == scope_category
    assert contract.observable["identity"] not in {
        "material_reference",
        "phase_diagram_reference",
        "status",
        "multi_field_registered_claim",
    }


def test_inspected_contract_units_and_material_scope_are_scientific(loaded_inventory):
    contracts = {
        item.benchmark_name: item for item in loaded_inventory.contracts
    }
    locators = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }

    ni_ps3 = contracts["ni_ps3_honeycomb_antiferromagnet_reference"]
    assert ni_ps3.subject == "NiPS3 honeycomb antiferromagnetic order"
    assert ni_ps3.size_or_limit["category"] == (
        "published_experimental_material_conditions_pending_source_verification"
    )
    assert locators[ni_ps3.benchmark_name]["locator_class"] == "abstract"

    tfim = contracts["transverse_field_ising_chain_critical_point"]
    assert tfim.representation["fields"][0]["units"] == "dimensionless_ratio"

    xxz = contracts["xxz_spin_half_chain_phase_boundaries"]
    xxz_fields = {field["id"]: field for field in xxz.representation["fields"]}
    assert xxz_fields["gapless_interval"]["units"] == "dimensionless_anisotropy"

    aklt = contracts["aklt_spin1_chain_projector_ground_state"]
    aklt_fields = {field["id"]: field for field in aklt.representation["fields"]}
    assert aklt_fields["two_site_projector_eigenvalues"] == {
        "id": "two_site_projector_eigenvalues",
        "type": "list[number]",
        "units": "dimensionless_projector_eigenvalue",
        "convention": "ordered_two_site_projector_spectrum",
    }


def test_provisional_records_are_complete_and_fail_closed(loaded_inventory):
    required = {
        "source_id",
        "registry_selector",
        "canonical_observable_id",
        "evidence_mode",
        "target_locator_strategy",
        "parser_strategy",
        "comparator",
        "unresolved_reason",
    }
    forbidden = {
        "source_sha256",
        "parsed_target",
        "source_excerpt",
        "copied_target",
        "target_observable",
        "target_excerpt",
        "verdict",
        "pass",
        "strict",
        "strict_match",
        "strict_literature_match",
    }
    for record in loaded_inventory.records:
        plain = record.as_plain_data()
        assert required <= set(plain)
        assert not forbidden.intersection(_recursive_keys(plain))
        assert record.record_state == "unresolved"
        assert record.unresolved_reason.strip()
        assert derive_unresolved_status(record) == "unresolved"
        with pytest.raises(EvidenceSchemaError):
            EvidenceRecord(**plain)


def test_sources_are_133_unique_canonical_identities_covering_every_record(
    loaded_inventory,
):
    sources = loaded_inventory.source_index
    assert len(sources) == 133
    assert len({source["source_id"] for source in sources}) == 133
    assert len({tuple(source["canonical_identity"].items()) for source in sources}) == 133
    assert {source["source_id"] for source in sources} == {
        record.source_id for record in loaded_inventory.records
    }
    assert sum(len(source["benchmark_names"]) for source in sources) == 155

    by_url = {
        entry["source_url"]: canonical_source_identity(entry["source_url"])
        for entry in LITERATURE_STANDARD_RESULTS
    }
    assert len(set(by_url.values())) == 133
    assert canonical_source_identity(
        "https://doi.org/10.1103/PhysRevLett.26.832"
    ) == canonical_source_identity("https://DOI.org/10.1103/physrevlett.26.832")
    assert canonical_source_identity(
        "https://arxiv.org/abs/1409.0193"
    ) == canonical_source_identity("https://arxiv.org/pdf/1409.0193.pdf")

    for doi, expected_benchmarks in (
        (
            "10.1103/PhysRevLett.26.832",
            {
                "eight_vertex_zero_field_exact_solution_status",
                "square_ashkin_teller_exact_critical_line",
            },
        ),
        (
            "10.1103/PhysRevX.1.021002",
            {
                "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
                "yb2ti2o7_pyrochlore_exchange_reference",
            },
        ),
    ):
        identity = canonical_source_identity(f"https://doi.org/{doi}")
        matching = [
            source
            for source in sources
            if (
                f"{source['canonical_identity']['kind']}:"
                f"{source['canonical_identity']['value']}"
            )
            == identity
        ]
        assert len(matching) == 1
        assert set(matching[0]["benchmark_names"]) == expected_benchmarks


def test_corrected_material_primary_source_dois_are_registered(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry["source_url"] for entry in LITERATURE_STANDARD_RESULTS
    }
    assert registry_by_name["barlowite_kagome_material_reference"] == (
        "https://doi.org/10.1103/PhysRevLett.113.227203"
    )
    assert registry_by_name["garnet_gd3ga5o12_spin_liquid_reference"] == (
        "https://doi.org/10.1103/PhysRevLett.80.4570"
    )
    identities = {
        source["canonical_identity"]["value"]
        for source in loaded_inventory.source_index
    }
    assert "10.1103/physrevlett.113.227203" in identities
    assert "10.1103/physrevlett.80.4570" in identities
    assert "10.1103/physrevb.90.094426" not in identities
    assert "10.1103/physrevb.57.4986" not in identities


def test_provisioning_has_one_publisher_specific_unacquired_route_per_source(
    loaded_inventory,
):
    routes = loaded_inventory.source_provisioning
    assert len(routes) == 133
    assert {route["source_id"] for route in routes} == {
        source["source_id"] for source in loaded_inventory.source_index
    }
    for route in routes:
        source = next(
            item
            for item in loaded_inventory.source_index
            if item["source_id"] == route["source_id"]
        )
        expected = authoritative_route_for_identity(source["canonical_identity"])
        assert route["authoritative_retrieval_route"] == {
            "kind": expected["kind"],
            "url": expected["url"],
        }
        assert route["access_mode"] == expected["access_mode"]
        assert route["authoritative_retrieval_route"]["kind"] != (
            "doi_content_negotiation"
        )
        assert route["expected_media_type"] in {
            "application/pdf",
            "application/xml",
        }
        assert route["expected_media_type"] == expected["expected_media_type"]
        assert route["redistributability"] == "unresolved"
        assert route["current_availability"] == "not_acquired"
        extension = "xml" if route["expected_media_type"] == "application/xml" else "pdf"
        assert route["local_cache_location"] == (
            f"source-cache/{route['source_id']}/source.{extension}"
        )


def test_locator_inventory_is_structured_target_free_and_complete(loaded_inventory):
    allowed_classes = {
        "equation",
        "table",
        "abstract",
        "body_text",
        "figure_caption",
        "supplemental",
        "metadata_field",
    }
    forbidden = {
        "answer",
        "value",
        "expected_value",
        "parsed_target",
        "source_excerpt",
        "copied_target",
        "verdict",
    }
    for row in loaded_inventory.locator_inventory:
        assert row["locator_class"] in allowed_classes
        assert row["expected_container"]
        assert row["target_representation"]["fields"]
        strategy = row["locator_strategy"]
        assert strategy["source_context_hint"]
        assert len(strategy["search_anchors"]) >= 2
        assert all(anchor.strip() for anchor in strategy["search_anchors"])
        assert strategy["rationale"]
        assert set(strategy["locator_basis"]) == {
            "citation_locator",
            "benchmark_name",
            "observable_semantics",
            "canonical_source_identity",
        }
        assert not forbidden.intersection(_recursive_keys(row))


def test_locator_forecasts_are_source_specific_and_honest(loaded_inventory):
    locators = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }

    phase_diagram = locators["honeycomb_kitaev_gamma_phase_diagram_reference"]
    assert phase_diagram["locator_class"] in {"body_text", "figure_caption"}
    assert "generic spin model for honeycomb iridates" in phase_diagram[
        "locator_strategy"
    ]["source_context_hint"]
    assert "phase diagram" in phase_diagram["locator_strategy"]["search_anchors"]

    qmc = locators["square_spin_half_heisenberg_qmc_energy"]
    assert qmc["expected_container"] != "main_text_or_supplemental_table"
    assert "QMC" in qmc["locator_strategy"]["source_context_hint"]

    material = locators["ni_ps3_honeycomb_antiferromagnet_reference"]
    assert material["locator_class"] in {"abstract", "body_text", "figure_caption"}
    assert "NiPS3" in material["locator_strategy"]["search_anchors"]
    assert "spin waves" in material["locator_strategy"]["search_anchors"]


def test_claim_surfaces_do_not_copy_registry_target_values(loaded_inventory):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    locator_by_name = {
        row["benchmark_name"]: row for row in loaded_inventory.locator_inventory
    }
    for contract, record in zip(loaded_inventory.contracts, loaded_inventory.records):
        standard_result = registry_by_name[contract.benchmark_name]["standard_result"]
        target_leaves = {
            (type(value).__name__, repr(value))
            for key, target in standard_result.items()
            if key not in {"computable_observables", "tolerance"}
            for value in _recursive_leaves(target)
        }
        locator = locator_by_name[contract.benchmark_name]
        identity_surfaces = (
            contract.observable,
            contract.representation,
            contract.conditions,
            record.target_locator_strategy,
            record.parser_strategy,
            record.comparator,
            locator["target_representation"],
        )
        identity_leaves = {
            (type(value).__name__, repr(value))
            for surface in identity_surfaces
            for value in _recursive_leaves(surface)
        }
        assert target_leaves.isdisjoint(identity_leaves), contract.benchmark_name


def test_selectors_resolve_only_registered_claim_operands_and_ignore_record_metadata(
    loaded_inventory,
):
    registry_by_name = {
        entry["name"]: entry for entry in LITERATURE_STANDARD_RESULTS
    }
    for record in loaded_inventory.records:
        registry_entry = registry_by_name[record.benchmark_name]
        selected = resolve_registry_selector(registry_entry, record.registry_selector)
        assert selected
        assert "computable_observables" not in selected
        assert "tolerance" not in selected

        plain = record.as_plain_data()
        for key in set(plain) - {"registry_selector"}:
            mutated = copy.deepcopy(plain)
            mutated[key] = _different_value(mutated[key])
            assert (
                resolve_registry_selector(registry_entry, mutated["registry_selector"])
                == selected
            )


def test_generated_artifact_surfaces_do_not_share_mutable_nested_objects():
    data = build_inventory_data(LITERATURE_STANDARD_RESULTS)
    contract_fields = data["contracts"][0]["representation"]["fields"]
    record = data["records"][0]
    locator = data["locator_inventory"][0]

    assert contract_fields is not record["parser_strategy"]["output_fields"]
    assert record["parser_strategy"]["output_fields"] is not record["comparator"]["fields"]
    assert record["target_locator_strategy"] is not locator["locator_strategy"]

    original_contract_units = contract_fields[0]["units"]
    original_comparator_units = record["comparator"]["fields"][0]["units"]
    original_locator_units = locator["target_representation"]["fields"][0]["units"]
    record["parser_strategy"]["output_fields"][0]["units"] = "mutated"

    assert contract_fields[0]["units"] == original_contract_units
    assert record["comparator"]["fields"][0]["units"] == original_comparator_units
    assert locator["target_representation"]["fields"][0]["units"] == original_locator_units


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda c: c.update(subject="generic"), "subject"),
        (lambda c: c.update(size_or_limit={"kind": "generic"}), "size or limit"),
        (lambda c: c.update(units="generic"), "top-level units"),
        (
            lambda c: c["conditions"].update(physical_regime="generic"),
            "physical regime",
        ),
        (
            lambda c: c["conditions"].update(source_claim_scope="generic"),
            "source claim scope",
        ),
        (
            lambda c: c["conditions"].update(backend_scope="generic"),
            "backend scope",
        ),
    ],
)
def test_inventory_rejects_corrupted_canonical_identity_dimensions(
    loaded_inventory, mutation, message
):
    data = mutable_inventory(loaded_inventory)
    mutation(data["contracts"][0])
    with pytest.raises(InventoryError, match=message):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["contracts"].pop(), "missing canonical contracts"),
        (
            lambda data: data["contracts"].append(copy.deepcopy(data["contracts"][0])),
            "duplicate canonical contract names",
        ),
        (
            lambda data: data["contracts"][0].update(benchmark_name="orphan_contract"),
            "orphan canonical contracts",
        ),
        (
            lambda data: data["records"][0].update(benchmark_name="orphan_record"),
            "missing provisional records",
        ),
    ],
)
def test_inventory_rejects_missing_orphan_and_duplicate_names(
    loaded_inventory, mutation, message
):
    data = mutable_inventory(loaded_inventory)
    mutation(data)
    with pytest.raises(InventoryError, match=message):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_generic_contract(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["contracts"][0]["observable"] = {
        "identity": "material_reference",
        "claim_fields": ["material_reference"],
    }
    with pytest.raises((InventoryError, EvidenceSchemaError), match="generic"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    "forbidden_key",
    ["parsed_target", "source_excerpt", "copied_target", "verdict", "pass"],
)
def test_inventory_rejects_forbidden_target_and_verdict_fields_recursively(
    loaded_inventory, forbidden_key
):
    data = mutable_inventory(loaded_inventory)
    data["records"][0]["parser_strategy"]["nested"] = {forbidden_key: "leak"}
    with pytest.raises((InventoryError, EvidenceSchemaError), match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    ("collection", "nested_key", "forbidden_key"),
    [
        ("contracts", "conditions", "verdict"),
        ("source_index", "canonical_identity", "source_excerpt"),
        (
            "source_provisioning",
            "authoritative_retrieval_route",
            "copied_target",
        ),
    ],
)
def test_all_inventory_artifacts_reject_recursive_evidence_leakage(
    loaded_inventory, collection, nested_key, forbidden_key
):
    data = mutable_inventory(loaded_inventory)
    data[collection][0][nested_key][forbidden_key] = "leak"
    with pytest.raises(InventoryError, match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize("source_hash", ["0" * 64, "a" * 64])
def test_provisional_record_rejects_any_source_hash(source_hash, loaded_inventory):
    plain = loaded_inventory.records[0].as_plain_data()
    plain["source_sha256"] = source_hash
    with pytest.raises(EvidenceSchemaError, match="source_sha256"):
        ProvisionalEvidenceRecord(**plain)


def test_inventory_rejects_bad_source_count_or_identity(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_index"].pop()
    with pytest.raises(InventoryError, match="133"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["source_index"][0]["canonical_identity"]["value"] = "10.0/fake"
    with pytest.raises(InventoryError, match="canonical source identity"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["records"][0]["source_id"] = data["records"][1]["source_id"]
    with pytest.raises(InventoryError, match="record source identity mismatch"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_provisional_record_requires_nonempty_unresolved_reason(loaded_inventory):
    plain = loaded_inventory.records[0].as_plain_data()
    plain["unresolved_reason"] = " "
    with pytest.raises(EvidenceSchemaError, match="unresolved_reason"):
        ProvisionalEvidenceRecord(**plain)


def test_inventory_rejects_locator_answer_leakage(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["target_representation"]["answer"] = 1
    with pytest.raises(InventoryError, match="forbidden"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_locator_source_or_empty_strategy(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["source_id"] = data["source_index"][1]["source_id"]
    with pytest.raises(InventoryError, match="locator source identity mismatch"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["locator_inventory"][0]["locator_strategy"] = {}
    data["records"][0]["target_locator_strategy"] = {}
    with pytest.raises(InventoryError, match="locator strategy"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_provisioning_mismatch(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["source_id"] = "orphan_source"
    with pytest.raises(InventoryError, match="provisioning"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    route = data["source_provisioning"][0]
    current_kind = route["authoritative_retrieval_route"]["kind"]
    route["authoritative_retrieval_route"]["kind"] = current_kind + "_mutated"
    with pytest.raises(InventoryError, match="retrieval route"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)

    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["current_availability"] = "unavailable"
    with pytest.raises(InventoryError, match="not_acquired"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize(
    "cache_location",
    [
        "source-cache/../../outside/source.pdf",
        "source-cache/",
        "source-cache//etc/passwd",
        "/source-cache/source.pdf",
        "source-cache/./source.pdf",
    ],
)
def test_inventory_rejects_unsafe_provisioning_cache_paths(
    loaded_inventory, cache_location
):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][0]["local_cache_location"] = cache_location
    with pytest.raises(InventoryError, match="local cache location"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_duplicate_provisioning_cache_paths(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_provisioning"][1]["local_cache_location"] = data[
        "source_provisioning"
    ][0]["local_cache_location"]
    with pytest.raises(InventoryError, match="duplicate local cache location"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_inventory_rejects_bad_canonical_source_url(loaded_inventory):
    data = mutable_inventory(loaded_inventory)
    data["source_index"][0]["canonical_url"] = "https://example.invalid/source"
    with pytest.raises(InventoryError, match="canonical URL"):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


@pytest.mark.parametrize("strategy_name", ["parser_strategy", "comparator"])
def test_inventory_rejects_empty_parser_or_comparator_strategy(
    loaded_inventory, strategy_name
):
    data = mutable_inventory(loaded_inventory)
    data["records"][0][strategy_name] = {}
    with pytest.raises(InventoryError, match=strategy_name.replace("_", " ")):
        validate_inventory(data, LITERATURE_STANDARD_RESULTS)


def test_loader_rejects_record_filename_mismatch(tmp_path):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    record_path = next((copied_root / "records").glob("*.json"))
    record_path.rename(record_path.with_name("wrong-record-filename.json"))
    with pytest.raises(InventoryError, match="record filenames"):
        load_and_validate_inventory(copied_root)


@pytest.mark.parametrize(
    "malformation", ["duplicate_key", "non_finite", "overflowing_float"]
)
def test_loader_rejects_ambiguous_or_nonstandard_json(tmp_path, malformation):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    record_path = next((copied_root / "records").glob("*.json"))
    raw = record_path.read_text(encoding="utf-8")
    if malformation == "duplicate_key":
        raw = raw.replace(
            '"benchmark_name":',
            '"benchmark_name": "duplicate",\n  "benchmark_name":',
            1,
        )
    elif malformation == "non_finite":
        raw = raw.replace('"schema_version": 1', '"schema_version": NaN', 1)
    else:
        raw = raw.replace('"schema_version": 1', '"schema_version": 1e999', 1)
    record_path.write_text(raw, encoding="utf-8")
    with pytest.raises(InventoryError, match="duplicate JSON key|non-finite JSON"):
        load_and_validate_inventory(copied_root)


def test_canonical_contract_artifact_is_independent_of_mutated_runtime_records(
    loaded_inventory,
):
    contract_path = INVENTORY_ROOT / "canonical-observables.json"
    before = contract_path.read_bytes()
    records = [record.as_plain_data() for record in loaded_inventory.records]
    records[0]["unresolved_reason"] = "mutated runtime metadata"
    records[0]["parser_strategy"] = {"kind": "manual_future_parse"}

    assert contract_path.read_bytes() == before


def test_canonical_contracts_are_not_regenerated_from_registry_observable_labels():
    baseline = build_inventory_data(LITERATURE_STANDARD_RESULTS)["contracts"]
    mutated_registry = copy.deepcopy(LITERATURE_STANDARD_RESULTS)
    for entry in mutated_registry:
        entry["observable"] = "generic_registry_label_that_must_not_define_contract"

    rebuilt = build_inventory_data(mutated_registry)["contracts"]

    assert rebuilt == baseline


def test_alternate_root_generation_reads_that_roots_canonical_contracts(tmp_path):
    copied_root = tmp_path / "literature-evidence"
    shutil.copytree(INVENTORY_ROOT, copied_root)
    contract_path = copied_root / "canonical-observables.json"
    document = json.loads(contract_path.read_text(encoding="utf-8"))
    marker = "alternate_root_exact_projector_and_vbs_observable"
    document["canonical_observables"][0]["observable"]["identity"] = marker
    contract_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    generated = build_inventory_data(
        LITERATURE_STANDARD_RESULTS, inventory_root=copied_root
    )

    assert generated["contracts"][0]["observable"]["identity"] == marker


def _recursive_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_recursive_keys(item))
        return keys
    if isinstance(value, (list, tuple)):
        keys = set()
        for item in value:
            keys.update(_recursive_keys(item))
        return keys
    return set()


def _different_value(value):
    if isinstance(value, str):
        return value + "_mutated"
    if isinstance(value, dict):
        return {"mutated": "metadata"}
    if isinstance(value, list):
        return ["mutated"]
    return None


def _recursive_leaves(value):
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _recursive_leaves(item)]
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _recursive_leaves(item)]
    return [value]


def _literal_registry_claim_fields():
    registry_path = (
        PROJECT_ROOT / "scripts" / "validation" / "literature_spin_model_benchmarks.py"
    )
    tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    list_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "LITERATURE_STANDARD_RESULTS"
            for target in node.targets
        ):
            list_nodes.append(node.value)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            function = node.value.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "LITERATURE_STANDARD_RESULTS"
                and function.attr == "extend"
            ):
                list_nodes.append(node.value.args[0])

    result = {}
    for list_node in list_nodes:
        for entry_node in list_node.elts:
            entry = {
                key.value: value
                for key, value in zip(entry_node.keys, entry_node.values)
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            name = ast.literal_eval(entry["name"])
            fields = tuple(
                key.value
                for key in entry["standard_result"].keys
                if isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value not in {"tolerance", "computable_observables"}
            )
            result[name] = fields
    return result
