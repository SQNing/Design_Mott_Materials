import ast
import dataclasses
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_adapters import (
    ADAPTER_ELIGIBILITY,
    SOURCE_PARSE_ONLY_REASONS,
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
    _build_adapter_eligibility,
)


EXPECTED_ELIGIBILITY = (
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


MIGRATION_CANDIDATE_SOURCES = frozenset(
    {
        "blume_capel_spin1_zero_temperature_level_crossing",
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        "cubic_ising_critical_temperature_reference",
        "fcc_j1_j2_heisenberg_type_order_reference",
        "honeycomb_ising_ferromagnet_exact_tc",
        "honeycomb_j1_j2_spiral_ring_reference",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        "kagome_ising_ferromagnet_exact_tc",
        "majundar_ghosh_chain_exact_dimer_point",
        "one_dimensional_classical_ising_no_finite_t_transition",
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        "shastry_sutherland_exact_dimer_product",
        "simple_cubic_j1_j2_collinear_reference",
        "single_ion_spin1_anisotropy_levels",
        "square_fully_frustrated_ising_residual_entropy_reference",
        "takhtajan_babujian_spin1_critical_point",
        "transverse_field_ising_chain_critical_point",
        "transverse_field_ising_chain_gap",
        "triangular_ising_ferromagnet_exact_tc",
        "xx_spin_half_chain_free_fermion_energy",
        "xxz_spin_half_chain_phase_boundaries",
    }
)


def _legacy_local_recompute_candidate_names():
    runtime_source = (
        PROJECT_ROOT / "scripts" / "validation" / "literature_runtime_evidence.py"
    )
    tree = ast.parse(
        runtime_source.read_text(encoding="utf-8"), filename=str(runtime_source)
    )
    collectors = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "collect_runtime_evidence"
    ]
    assert len(collectors) == 1
    specs_assignments = [
        node
        for node in collectors[0].body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "specs"
            for target in node.targets
        )
    ]
    assert len(specs_assignments) == 1
    specs_literal = specs_assignments[0].value
    assert isinstance(specs_literal, ast.Tuple)

    candidate_names = []
    for spec in specs_literal.elts:
        assert isinstance(spec, ast.Dict)
        literal_fields = {
            key.value: value
            for key, value in zip(spec.keys, spec.values)
            if isinstance(key, ast.Constant) and type(key.value) is str
        }
        mode = literal_fields.get("mode")
        if not (
            isinstance(mode, ast.Constant) and mode.value == "local_recompute"
        ):
            continue
        benchmark_name = literal_fields.get("benchmark_name")
        assert isinstance(benchmark_name, ast.Constant)
        assert type(benchmark_name.value) is str
        candidate_names.append(benchmark_name.value)

    assert len(candidate_names) == 21
    assert len(set(candidate_names)) == 21
    return frozenset(candidate_names)


def test_eligibility_catalog_matches_all_42_normative_rows_field_for_field():
    actual = tuple(
        (
            benchmark_name,
            decision.selector_fields,
            decision.disposition,
            decision.adapter_id,
            decision.oracle_id,
            decision.reason,
        )
        for benchmark_name, decision in ADAPTER_ELIGIBILITY.items()
    )

    assert actual == EXPECTED_ELIGIBILITY
    assert tuple(field.name for field in dataclasses.fields(EligibilityDecision)) == (
        "selector_fields",
        "disposition",
        "adapter_id",
        "oracle_id",
        "reason",
    )
    assert ADAPTER_ELIGIBILITY[
        "two_leg_ladder_strong_rung_exact_limit"
    ].selector_fields == ("energy_per_rung", "gap_to_triplet")
    triangular = ADAPTER_ELIGIBILITY["triangular_nn_classical_120_reference"]
    assert (triangular.disposition, triangular.reason) == (
        "source_parse_only",
        "status_or_candidate_only",
    )
    cubic = ADAPTER_ELIGIBILITY["cubic_ising_critical_temperature_reference"]
    assert (cubic.disposition, cubic.reason) == (
        "source_parse_only",
        "target_equivalent_input",
    )


def test_eligibility_catalog_has_exact_29_eligible_and_13_source_parse_rows():
    assert len(ADAPTER_ELIGIBILITY) == 42
    assert sum(
        decision.disposition == "eligible"
        for decision in ADAPTER_ELIGIBILITY.values()
    ) == 29
    assert sum(
        decision.disposition == "source_parse_only"
        for decision in ADAPTER_ELIGIBILITY.values()
    ) == 13
    assert SOURCE_PARSE_ONLY_REASONS == frozenset(
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


def test_source_parse_rows_cannot_resolve_an_adapter():
    for decision in ADAPTER_ELIGIBILITY.values():
        if decision.disposition == "source_parse_only":
            assert decision.adapter_id is None
            assert decision.oracle_id is None


def test_candidate_sources_union_matches_normative_catalog():
    legacy_candidates = _legacy_local_recompute_candidate_names()

    assert len(legacy_candidates) == 21
    assert len(MIGRATION_CANDIDATE_SOURCES) == 21
    assert legacy_candidates.isdisjoint(MIGRATION_CANDIDATE_SOURCES)
    assert legacy_candidates | MIGRATION_CANDIDATE_SOURCES == set(
        ADAPTER_ELIGIBILITY
    )


def test_eligibility_catalog_is_immutable():
    existing = ADAPTER_ELIGIBILITY["xxx_spin_half_chain_bethe_ground_state"]

    with pytest.raises(TypeError):
        ADAPTER_ELIGIBILITY["xxx_spin_half_chain_bethe_ground_state"] = existing
    with pytest.raises(dataclasses.FrozenInstanceError):
        existing.disposition = "source_parse_only"


def test_eligibility_builder_rejects_a_duplicate_benchmark_id():
    duplicated_row = EXPECTED_ELIGIBILITY[0]

    with pytest.raises(AdapterContractError, match="duplicate.*benchmark"):
        _build_adapter_eligibility((duplicated_row, duplicated_row))


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


class BadRepr:
    def __repr__(self):
        raise RuntimeError("repr must not run")

    def __hash__(self):
        raise RuntimeError("hash must not run")


class _BrokenFrozenItems:
    def __iter__(self):
        raise RuntimeError("broken frozen traversal")


def _list_cycle():
    value = []
    value.append(value)
    return value


def _mapping_cycle():
    value = {}
    value["self"] = value
    return value


def _frozen_object_with_scalar_depth(scalar_depth):
    value = 0
    for _ in range(scalar_depth):
        value = {"nested": value}
    frozen = freeze_json(value)
    assert type(frozen) is FrozenJsonObject
    return frozen


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


@pytest.mark.parametrize("outer_kind", ("mapping", "sequence"))
def test_freeze_json_rejects_frozen_depth_128_embedded_one_level(outer_kind):
    frozen = _frozen_object_with_scalar_depth(128)
    outer = {"embedded": frozen} if outer_kind == "mapping" else [frozen]

    with pytest.raises(AdapterContractError, match="nesting"):
        freeze_json(outer)


@pytest.mark.parametrize("outer_kind", ("mapping", "sequence"))
def test_freeze_json_accepts_frozen_depth_127_embedded_one_level(outer_kind):
    frozen = _frozen_object_with_scalar_depth(127)
    outer = {"embedded": frozen} if outer_kind == "mapping" else [frozen]

    accepted = freeze_json(outer)
    embedded = accepted["embedded"] if outer_kind == "mapping" else accepted[0]
    encoded = canonical_json_bytes(accepted)
    digest = canonical_sha256(accepted)

    assert embedded is frozen
    assert encoded == canonical_json_bytes(accepted)
    assert digest == canonical_sha256(accepted)
    assert accepted == accepted
    assert hash(accepted) == hash(accepted)


def test_freeze_json_accepts_shared_legal_frozen_aliases_without_false_cycle():
    shared = _frozen_object_with_scalar_depth(127)

    accepted = freeze_json({"left": shared, "right": shared})
    digest = canonical_sha256(accepted)

    assert accepted["left"] is accepted["right"] is shared
    assert accepted == accepted
    assert hash(accepted) == hash(accepted)
    assert canonical_sha256(accepted) == digest


def test_freeze_json_at_root_remains_idempotent_at_depth_boundary():
    frozen = _frozen_object_with_scalar_depth(128)

    assert freeze_json(frozen) is frozen


def test_freeze_json_rejects_mutable_storage_in_exact_frozen_object():
    frozen = FrozenJsonObject({"value": 1})
    mutable_items = [("value", 1)]
    object.__setattr__(frozen, "_items", mutable_items)

    with pytest.raises(AdapterContractError, match="immutable"):
        freeze_json(frozen)


def test_excessive_frozen_json_nesting_is_rejected_on_direct_thaw():
    value = 0
    for _ in range(256):
        value = (value,)

    with pytest.raises(AdapterContractError, match="nesting"):
        thaw_json(value)


def test_thaw_json_normalizes_unexpected_frozen_traversal_failures():
    malformed = FrozenJsonObject({"value": 1})
    object.__setattr__(malformed, "_items", _BrokenFrozenItems())

    with pytest.raises(AdapterContractError, match="traversal"):
        thaw_json(malformed)


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


def test_json_accepts_1024_bit_integer_boundaries():
    boundary = 2**1024 - 1
    value = {"negative": -boundary, "positive": boundary}

    frozen = freeze_json(value, "payload")
    equal_frozen = freeze_json(value, "payload")
    encoded = canonical_json_bytes(frozen)
    digest = canonical_sha256(frozen)

    assert thaw_json(frozen, "payload") == value
    assert encoded == canonical_json_bytes(value)
    assert digest == canonical_sha256(value)
    assert len(digest) == 64
    assert frozen == frozen == equal_frozen
    assert hash(frozen) == hash(frozen) == hash(equal_frozen)


@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
@pytest.mark.parametrize(
    "operation",
    (freeze_json, thaw_json, canonical_json_bytes, canonical_sha256),
    ids=("freeze", "thaw", "canonical_bytes", "canonical_sha256"),
)
def test_json_rejects_integers_beyond_1024_bits(value, operation):
    with pytest.raises(AdapterContractError, match="value.*1024"):
        operation(value)


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
        selector_fields=("energy_per_site",),
        disposition="eligible",
        adapter_id="xxx_bethe_energy",
        oracle_id="xxx_bethe_energy_series_oracle",
        reason=None,
    )
    assert eligible.reason is None
    with pytest.raises(AdapterContractError):
        EligibilityDecision(("energy_per_site",), "eligible", None, None, None)
    with pytest.raises(AdapterContractError):
        EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            "xxx_bethe_energy",
            "xxx_bethe_energy_series_oracle",
            "no_independent_oracle",
        )
    with pytest.raises(AdapterContractError):
        EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            None,
            None,
            "arbitrary_reason",
        )
    source_only = EligibilityDecision(
        ("tc_over_j",),
        "source_parse_only",
        None,
        None,
        "target_equivalent_input",
    )
    assert source_only.adapter_id is source_only.oracle_id is None


@pytest.mark.parametrize(
    "selector_fields",
    (
        pytest.param((), id="empty"),
        pytest.param(["energy_per_site"], id="list"),
        pytest.param(
            _CallerBackedTuple(["energy_per_site"]), id="tuple_subclass"
        ),
        pytest.param(
            ("energy_per_site", "energy_per_site"), id="duplicate"
        ),
        pytest.param(("EnergyPerSite",), id="not_lower_snake_case"),
        pytest.param(("\ud800",), id="non_utf8"),
    ),
)
def test_eligibility_selector_fields_are_exact_nonempty_unique_identifiers(
    selector_fields,
):
    with pytest.raises(AdapterContractError, match="selector_fields"):
        EligibilityDecision(
            selector_fields,
            "eligible",
            "xxx_bethe_energy",
            "xxx_bethe_integral_oracle",
            None,
        )


@pytest.mark.parametrize(
    ("field_name", "diagnostic"),
    (
        ("parameter_source_kind", "kind"),
        ("convergence_kind", "kind"),
        ("problem_size_kind", "kind"),
        ("backend_kind", "backend_kind"),
        ("eligibility_disposition", "disposition"),
        ("eligibility_reason", "reason"),
    ),
)
def test_enum_contracts_do_not_hash_or_repr_untrusted_values(
    field_name, diagnostic
):
    untrusted = BadRepr()

    if field_name == "parameter_source_kind":
        operation = lambda: ParameterSource("exchange", untrusted, {})
    elif field_name == "convergence_kind":
        operation = lambda: ConvergenceContract(untrusted, {})
    elif field_name == "problem_size_kind":
        operation = lambda: ProblemSizePolicy(untrusted, {}, {})
    elif field_name == "backend_kind":
        values = _adapter_values(
            _observable_identity(),
            {"spin_count": [2]},
            {"exchange": {"kind": "finite_interval", "bounds": [0.1, 3.0]}},
        )
        values["backend_kind"] = untrusted
        operation = lambda: AdapterDefinition(**values)
    elif field_name == "eligibility_disposition":
        operation = lambda: EligibilityDecision(
            ("energy_per_site",), untrusted, None, None, None
        )
    else:
        operation = lambda: EligibilityDecision(
            ("energy_per_site",),
            "source_parse_only",
            None,
            None,
            untrusted,
        )

    with pytest.raises(AdapterContractError, match=diagnostic):
        operation()


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


def test_value_schema_accepts_1024_bit_integer_bounds():
    boundary = 2**1024 - 1

    schema = ValueSchema(
        kind="number",
        required=True,
        lower=-boundary,
        upper=boundary,
        item_schema=None,
        properties=(),
        units="J",
    )

    assert schema.lower == -boundary
    assert schema.upper == boundary


def test_resource_limits_accept_1024_bit_integer_boundaries():
    boundary = 2**1024 - 1

    limits = ResourceLimits(
        cpu_seconds=boundary,
        wall_seconds=boundary,
        address_space_bytes=boundary,
        output_bytes=boundary,
        file_descriptors=boundary,
        process_count=boundary,
    )

    assert all(
        getattr(limits, field_name) == boundary
        for field_name in (
            "cpu_seconds",
            "wall_seconds",
            "address_space_bytes",
            "output_bytes",
            "file_descriptors",
            "process_count",
        )
    )


@pytest.mark.parametrize("field_name", ("lower", "upper"))
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
def test_value_schema_rejects_integers_beyond_1024_bits(field_name, value):
    values = {
        "kind": "number",
        "required": True,
        "lower": None,
        "upper": None,
        "item_schema": None,
        "properties": (),
        "units": "J",
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=f"{field_name}.*1024"):
        ValueSchema(**values)


@pytest.mark.parametrize(
    "field_name",
    (
        "cpu_seconds",
        "wall_seconds",
        "address_space_bytes",
        "output_bytes",
        "file_descriptors",
        "process_count",
    ),
)
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(2**1024, id="positive"),
        pytest.param(-(2**1024), id="negative"),
    ),
)
def test_resource_limits_reject_integers_beyond_1024_bits(field_name, value):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=f"{field_name}.*1024"):
        ResourceLimits(**values)


@pytest.mark.parametrize("contract_kind", ("value_schema", "resource_limits"))
@pytest.mark.parametrize(
    "value",
    (
        pytest.param(10**10000, id="positive"),
        pytest.param(-(10**10000), id="negative"),
    ),
)
def test_numeric_contracts_reject_extreme_integers_without_overflow(
    contract_kind, value
):
    with pytest.raises(AdapterContractError, match="1024"):
        if contract_kind == "value_schema":
            ValueSchema(
                kind="number",
                required=True,
                lower=value,
                upper=None,
                item_schema=None,
                properties=(),
                units="J",
            )
        else:
            ResourceLimits(
                cpu_seconds=value,
                wall_seconds=20,
                address_space_bytes=256_000_000,
                output_bytes=64_000,
                file_descriptors=16,
                process_count=1,
            )


@pytest.mark.parametrize(
    ("field_name", "diagnostic"),
    (
        ("cpu_seconds", "cpu_seconds must be positive"),
        ("wall_seconds", "wall_seconds must be positive"),
        ("address_space_bytes", "address_space_bytes must be a positive integer"),
        ("output_bytes", "output_bytes must be a positive integer"),
        ("file_descriptors", "file_descriptors must be a positive integer"),
        ("process_count", "process_count must be a positive integer"),
    ),
)
def test_resource_limits_preserve_within_bound_negative_errors(
    field_name, diagnostic
):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = -(2**1024 - 1)

    with pytest.raises(AdapterContractError, match=diagnostic):
        ResourceLimits(**values)


@pytest.mark.parametrize("field_name", ("cpu_seconds", "wall_seconds"))
@pytest.mark.parametrize("value", (True, math.nan, math.inf, -math.inf))
def test_resource_limits_reject_bool_and_nonfinite_float_times(field_name, value):
    values = {
        "cpu_seconds": 10,
        "wall_seconds": 20,
        "address_space_bytes": 256_000_000,
        "output_bytes": 64_000,
        "file_descriptors": 16,
        "process_count": 1,
    }
    values[field_name] = value

    with pytest.raises(AdapterContractError, match=field_name):
        ResourceLimits(**values)
