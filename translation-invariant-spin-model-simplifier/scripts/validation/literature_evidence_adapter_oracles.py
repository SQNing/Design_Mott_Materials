"""Closed metadata contracts for independent recalculation oracles.

Task 4 intentionally leaves the production oracle catalog empty.  Later tasks
add answer-free scientific entry points only after the isolation contracts and
dependency partition are in place.  Importing this module performs no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from validation import literature_evidence_adapters as _adapters


__all__ = (
    "OracleDefinition",
    "ORACLE_DEFINITIONS",
    "get_oracle_definition",
    "validate_oracle_definition",
    "oracle_definition_to_frozen_json",
    "oracle_definition_from_frozen_json",
)


@_adapters._seal_contract
@dataclass(frozen=True, init=False)
class OracleDefinition:
    """Answer-free declaration of one independently bundled oracle."""

    oracle_id: str
    entry_symbol: str
    input_schema: _adapters.ValueSchema
    result_schema: _adapters.ValueSchema
    runtime_requirements: _adapters.RuntimeRequirements
    convergence_invariant_contract: _adapters.FrozenJsonObject
    resource_limits: _adapters.ResourceLimits

    def __init__(self, *args, **kwargs):
        _adapters._initialize_closed(self, args, kwargs, OracleDefinition)

    def __post_init__(self) -> None:
        _adapters.require_identifier(self.oracle_id, "oracle_id")
        if (
            type(self.entry_symbol) is not str
            or _adapters._ENTRY_SYMBOL_RE.fullmatch(self.entry_symbol) is None
        ):
            raise _adapters.AdapterContractError(
                "entry_symbol must be a fully qualified module:function symbol"
            )
        expected_symbol = (
            "validation.literature_evidence_adapter_oracles:oracle_"
            + self.oracle_id
        )
        if self.entry_symbol != expected_symbol:
            raise _adapters.AdapterContractError(
                "entry_symbol must be the exact unresolved oracle symbol"
            )
        input_schema = _adapters._snapshot_value_schema(
            self.input_schema, "input_schema"
        )
        result_schema = _adapters._snapshot_value_schema(
            self.result_schema, "result_schema"
        )
        if input_schema.kind != "object" or result_schema.kind != "object":
            raise _adapters.AdapterContractError(
                "oracle input_schema and result_schema must be object schemas"
            )
        runtime_requirements = _adapters._snapshot_runtime_requirements(
            self.runtime_requirements
        )
        convergence_invariant_contract = _adapters._snapshot_json_mapping(
            self.convergence_invariant_contract,
            "convergence_invariant_contract",
        )
        if not convergence_invariant_contract:
            raise _adapters.AdapterContractError(
                "convergence_invariant_contract must be nonempty"
            )
        resource_limits = _adapters._snapshot_resource_limits(
            self.resource_limits
        )
        _adapters._validate_authored_string(
            self.oracle_id,
            "oracle_id",
            allow_numerical_control=True,
        )
        _adapters._validate_authored_schema(
            input_schema,
            "input_schema",
            allow_numerical_control=True,
        )
        _adapters._validate_authored_schema(result_schema, "result_schema")
        _adapters._validate_authored_json(
            convergence_invariant_contract,
            "convergence_invariant_contract",
            allow_numerical_control=True,
        )
        for field_name in (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ):
            metadata = getattr(runtime_requirements, field_name)
            values = metadata if type(metadata) is tuple else (metadata,)
            for index, item in enumerate(values):
                _adapters._validate_authored_string(
                    item,
                    f"runtime_requirements.{field_name}[{index}]",
                )
        object.__setattr__(self, "input_schema", input_schema)
        object.__setattr__(self, "result_schema", result_schema)
        object.__setattr__(
            self, "runtime_requirements", runtime_requirements
        )
        object.__setattr__(
            self,
            "convergence_invariant_contract",
            convergence_invariant_contract,
        )
        object.__setattr__(self, "resource_limits", resource_limits)


def validate_oracle_definition(value: object) -> OracleDefinition:
    """Return a fresh revalidated oracle-definition snapshot."""

    if type(value) is not OracleDefinition:
        raise _adapters.AdapterContractError(
            "oracle definition must be an exact OracleDefinition"
        )
    try:
        return OracleDefinition(
            oracle_id=value.oracle_id,
            entry_symbol=value.entry_symbol,
            input_schema=value.input_schema,
            result_schema=value.result_schema,
            runtime_requirements=value.runtime_requirements,
            convergence_invariant_contract=(
                value.convergence_invariant_contract
            ),
            resource_limits=value.resource_limits,
        )
    except _adapters.AdapterContractError:
        raise
    except Exception as error:
        raise _adapters.AdapterContractError(
            "oracle definition revalidation failed"
        ) from error


_ORACLE_DEFINITION_JSON_FIELDS = (
    "oracle_id",
    "entry_symbol",
    "input_schema",
    "result_schema",
    "runtime_requirements",
    "convergence_invariant_contract",
    "resource_limits",
)


def oracle_definition_to_frozen_json(
    value: OracleDefinition,
) -> _adapters.FrozenJsonObject:
    """Serialize one validated oracle definition with a locked JSON schema."""

    definition = validate_oracle_definition(value)
    return _adapters._snapshot_json_mapping(
        {
            "oracle_id": definition.oracle_id,
            "entry_symbol": definition.entry_symbol,
            "input_schema": _adapters._value_schema_to_frozen_json(
                definition.input_schema
            ),
            "result_schema": _adapters._value_schema_to_frozen_json(
                definition.result_schema
            ),
            "runtime_requirements": {
                "interpreter": definition.runtime_requirements.interpreter,
                "packages": definition.runtime_requirements.packages,
                "native_libraries": (
                    definition.runtime_requirements.native_libraries
                ),
                "backend_resources": (
                    definition.runtime_requirements.backend_resources
                ),
            },
            "convergence_invariant_contract": (
                definition.convergence_invariant_contract
            ),
            "resource_limits": {
                field_name: getattr(definition.resource_limits, field_name)
                for field_name in (
                    "cpu_seconds",
                    "wall_seconds",
                    "address_space_bytes",
                    "output_bytes",
                    "file_descriptors",
                    "process_count",
                )
            },
        },
        "oracle_definition",
    )


def oracle_definition_from_frozen_json(value: object) -> OracleDefinition:
    """Deserialize and fully validate the locked oracle-definition schema."""

    definition = _adapters.require_exact_keys(
        value, _ORACLE_DEFINITION_JSON_FIELDS, "oracle_definition"
    )
    runtime = _adapters.require_exact_keys(
        definition["runtime_requirements"],
        (
            "interpreter",
            "packages",
            "native_libraries",
            "backend_resources",
        ),
        "runtime_requirements",
    )
    limit_fields = (
        "cpu_seconds",
        "wall_seconds",
        "address_space_bytes",
        "output_bytes",
        "file_descriptors",
        "process_count",
    )
    limits = _adapters.require_exact_keys(
        definition["resource_limits"],
        limit_fields,
        "resource_limits",
    )
    candidate = OracleDefinition(
        oracle_id=definition["oracle_id"],
        entry_symbol=definition["entry_symbol"],
        input_schema=_adapters._value_schema_from_frozen_json(
            definition["input_schema"], "input_schema"
        ),
        result_schema=_adapters._value_schema_from_frozen_json(
            definition["result_schema"], "result_schema"
        ),
        runtime_requirements=_adapters.RuntimeRequirements(
            interpreter=runtime["interpreter"],
            packages=_adapters._require_tuple(
                runtime["packages"], "runtime_requirements.packages"
            ),
            native_libraries=_adapters._require_tuple(
                runtime["native_libraries"],
                "runtime_requirements.native_libraries",
            ),
            backend_resources=_adapters._require_tuple(
                runtime["backend_resources"],
                "runtime_requirements.backend_resources",
            ),
        ),
        convergence_invariant_contract=(
            definition["convergence_invariant_contract"]
        ),
        resource_limits=_adapters.ResourceLimits(
            **{name: limits[name] for name in limit_fields}
        ),
    )
    validated = validate_oracle_definition(candidate)
    if _adapters.canonical_json_bytes(
        oracle_definition_to_frozen_json(validated)
    ) != _adapters.canonical_json_bytes(definition):
        raise _adapters.AdapterContractError(
            "oracle definition does not round-trip canonically"
        )
    return validated


def _task13_oracle_definition(adapter_id, oracle_id):
    adapter_definition = _adapters.ADAPTER_DEFINITIONS[adapter_id]
    adapter_fields_schema = _adapters.ValueSchema(
        "object",
        True,
        None,
        None,
        None,
        tuple(
            (selector, binding.value_schema)
            for selector, binding in adapter_definition.output_schema
        ),
        "",
    )
    input_schema = _adapters.ValueSchema(
        "object",
        True,
        None,
        None,
        None,
        (
            ("adapter_fields", adapter_fields_schema),
            (
                "scientific_inputs",
                adapter_definition.scientific_input_schema,
            ),
        ),
        "",
    )
    result_schema = _adapters.ValueSchema(
        "object",
        True,
        None,
        None,
        None,
        (
            (
                "invariant_satisfied",
                _adapters.ValueSchema(
                    "boolean", True, None, None, None, (), "dimensionless"
                ),
            ),
            (
                "residual_norm",
                _adapters.ValueSchema(
                    "number", True, 0.0, None, None, (), "dimensionless"
                ),
            ),
        ),
        "",
    )
    return OracleDefinition(
        oracle_id=oracle_id,
        entry_symbol=(
            "validation.literature_evidence_adapter_oracles:oracle_"
            + oracle_id
        ),
        input_schema=input_schema,
        result_schema=result_schema,
        runtime_requirements=_adapters.RuntimeRequirements(
            "python3", (), (), ("single_cpu_core",)
        ),
        convergence_invariant_contract={
            "kind": "residual_bound",
            "rule": "independent equation closure and invariant consistency",
            "secondary_bound": 1.0,
        },
        resource_limits=_adapters.ResourceLimits(
            60, 120, 2 * 1024**3, 1024**2, 64, 1
        ),
    )


_TASK13_ORACLE_ROWS = (
    ("xxx_bethe_energy", "xxx_bethe_integral_oracle"),
    ("square_ising_self_dual_tc", "square_ising_duality_residual_oracle"),
    ("pauling_entropy_combinatorics", "pauling_cluster_count_oracle"),
    ("aklt_projector_angle", "aklt_two_spin_spectrum_oracle"),
    (
        "honeycomb_ising_star_triangle_tc",
        "honeycomb_ising_critical_polynomial_oracle",
    ),
    (
        "kagome_ising_star_triangle_tc",
        "kagome_ising_critical_polynomial_oracle",
    ),
    (
        "ising_chain_transfer_matrix",
        "ising_chain_partition_analytic_oracle",
    ),
    (
        "triangular_ising_star_triangle_tc",
        "triangular_ising_critical_polynomial_oracle",
    ),
    (
        "spin_ice_tetrahedron_enumeration",
        "spin_ice_tetrahedron_matrix_oracle",
    ),
    ("toric_code_stabilizer_rank", "toric_code_logical_loop_oracle"),
    ("blume_capel_level_crossing", "blume_capel_configuration_oracle"),
    (
        "checkerboard_plaquette_enumeration",
        "checkerboard_total_spin_oracle",
    ),
    ("spin_ladder_rung_dense_ed", "spin_ladder_analytic_rung_oracle"),
    ("uls_two_site_su3_matrix", "uls_permutation_commutator_oracle"),
    ("compass_line_symmetry_matrix", "compass_spin_flip_oracle"),
    ("aklt_two_site_projector_ed", "aklt_clebsch_gordan_oracle"),
    ("majumdar_ghosh_dimer_ed", "majumdar_ghosh_projector_oracle"),
    ("shastry_sutherland_dimer_ed", "shastry_sutherland_bond_oracle"),
    ("spin1_single_ion_dense_ed", "spin1_m_quantum_number_oracle"),
)


def _build_task13_oracle_definitions(rows):
    definitions = {}
    for adapter_id, oracle_id in rows:
        if oracle_id in definitions:
            raise _adapters.AdapterContractError(
                f"duplicate oracle_id {oracle_id}"
            )
        definitions[oracle_id] = _task13_oracle_definition(
            adapter_id, oracle_id
        )
    return MappingProxyType(definitions)


ORACLE_DEFINITIONS: Mapping[str, OracleDefinition] = (
    _build_task13_oracle_definitions(_TASK13_ORACLE_ROWS)
)


def get_oracle_definition(oracle_id: str) -> OracleDefinition:
    """Return a production oracle declaration or fail closed."""

    _adapters.require_identifier(oracle_id, "oracle_id")
    try:
        return ORACLE_DEFINITIONS[oracle_id]
    except KeyError as error:
        raise _adapters.AdapterContractError(
            f"unknown oracle_id {oracle_id}"
        ) from error


def _task13_oracle_unpack(payload, numerical_controls):
    scientific_inputs = payload["scientific_inputs"]
    adapter_fields = payload["adapter_fields"]
    return scientific_inputs, adapter_fields


def _task13_oracle_measure(residual, invariant=True):
    residual = float(abs(residual))
    return {
        "residual_norm": residual,
        "invariant_satisfied": bool(invariant),
    }


def oracle_xxx_bethe_integral_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["exchange"])
    series = 0.0
    denominator_power = 3.0
    for index in range(32):
        series += 2.0 / ((2 * index + 1) * denominator_power)
        denominator_power *= 9.0
    next_term = 2.0 / (65.0 * denominator_power)
    tail_bound = next_term / (1.0 - 1.0 / 9.0)
    independent_energy = exchange * (0.25 - series)
    return _task13_oracle_measure(
        fields["energy_per_site"] - independent_energy,
        abs(fields["energy_per_site"] - independent_energy)
        <= abs(exchange) * tail_bound + 1e-14,
    )


def oracle_square_ising_duality_residual_oracle(
    payload, numerical_controls
):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    coupling = 1.0 / float(fields["tc_over_j"])
    dual_coupling = 0.5 * math.asinh(1.0 / math.sinh(2.0 * coupling))
    twice_dual = 0.5 * math.asinh(
        1.0 / math.sinh(2.0 * dual_coupling)
    )
    return _task13_oracle_measure(
        coupling - dual_coupling,
        abs(twice_dual - coupling) <= 1e-12,
    )


def oracle_pauling_cluster_count_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    spin_count = int(inputs["spins_per_tetrahedron"])
    local_ice_states = math.comb(spin_count, spin_count // 2)
    branch_count = 1
    branch_spin_count = 1
    cluster_counts = []
    cluster_spin_counts = []
    depth_entropies = []
    for _depth in range(4):
        cluster_count = local_ice_states * branch_count**spin_count
        cluster_spins = spin_count * branch_spin_count
        cluster_counts.append(cluster_count)
        cluster_spin_counts.append(cluster_spins)
        depth_entropies.append(math.log(cluster_count) / cluster_spins)
        branch_count = 3 * branch_count**3
        branch_spin_count = 1 + 3 * branch_spin_count
    bulk_entropies = []
    for depth in range(1, len(cluster_counts)):
        bulk_log_count = (
            math.log(cluster_counts[depth])
            - 3.0 * math.log(cluster_counts[depth - 1])
        )
        bulk_spin_count = (
            cluster_spin_counts[depth]
            - 3 * cluster_spin_counts[depth - 1]
        )
        bulk_entropies.append(bulk_log_count / bulk_spin_count)
    independent_entropy = bulk_entropies[-1]
    trend_invariant = True
    for index in range(1, len(depth_entropies)):
        if depth_entropies[index] >= depth_entropies[index - 1]:
            trend_invariant = False
    if not (
        cluster_counts[0] < cluster_counts[-1]
        and cluster_spin_counts[0] < cluster_spin_counts[-1]
    ):
        trend_invariant = False
    for value in bulk_entropies:
        if abs(value - independent_entropy) > 1e-14:
            trend_invariant = False
    return _task13_oracle_measure(
        fields["pauling_entropy_per_spin"] - independent_entropy,
        spin_count == 4 and trend_invariant,
    )


def oracle_aklt_two_spin_spectrum_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    scale = float(inputs["projector_scale"])
    magnetic = (1.0, 0.0, -1.0)
    dot_matrix = []
    for _row in range(9):
        dot_matrix.append([0.0] * 9)
    for first in range(3):
        for second in range(3):
            column = first * 3 + second
            dot_matrix[column][column] += magnetic[first] * magnetic[second]
            first_m = magnetic[first]
            second_m = magnetic[second]
            if first > 0 and second < 2:
                coefficient = 0.5 * math.sqrt(
                    2.0 - first_m * (first_m + 1.0)
                ) * math.sqrt(2.0 - second_m * (second_m - 1.0))
                row = (first - 1) * 3 + second + 1
                dot_matrix[row][column] += coefficient
            if first < 2 and second > 0:
                coefficient = 0.5 * math.sqrt(
                    2.0 - first_m * (first_m - 1.0)
                ) * math.sqrt(2.0 - second_m * (second_m + 1.0))
                row = (first + 1) * 3 + second - 1
                dot_matrix[row][column] += coefficient
    sector_vectors = []
    spin_two = [0.0] * 9
    spin_two[0] = 1.0
    sector_vectors.append(spin_two)
    spin_one = [0.0] * 9
    spin_one[1] = 1.0 / math.sqrt(2.0)
    spin_one[3] = -1.0 / math.sqrt(2.0)
    sector_vectors.append(spin_one)
    spin_zero = [0.0] * 9
    spin_zero[2] = 1.0 / math.sqrt(3.0)
    spin_zero[4] = -1.0 / math.sqrt(3.0)
    spin_zero[6] = 1.0 / math.sqrt(3.0)
    sector_vectors.append(spin_zero)
    sector_eigenvalues = []
    for vector in sector_vectors:
        expectation = 0.0
        for row in range(9):
            for column in range(9):
                expectation += (
                    vector[row] * dot_matrix[row][column] * vector[column]
                )
        sector_eigenvalues.append(expectation)
    equations = []
    targets = (scale, 0.0, 0.0)
    for index in range(3):
        eigenvalue = sector_eigenvalues[index]
        equations.append(
            [1.0, eigenvalue, eigenvalue * eigenvalue, targets[index]]
        )
    for pivot in range(3):
        pivot_value = equations[pivot][pivot]
        for column in range(pivot, 4):
            equations[pivot][column] /= pivot_value
        for row in range(3):
            if row == pivot:
                continue
            factor = equations[row][pivot]
            for column in range(pivot, 4):
                equations[row][column] -= factor * equations[pivot][column]
    bilinear = equations[1][3]
    biquadratic = equations[2][3]
    ratio_basis = biquadratic / bilinear
    residual = max(
        abs(fields["aklt_tan_theta"] - ratio_basis),
        abs(fields["theta_radians"] - math.atan(ratio_basis)),
    )
    sector_tolerance = 1e-12 * max(1.0, abs(scale))
    sector_invariant = (
        abs(sector_eigenvalues[0] - 1.0) <= sector_tolerance
        and abs(sector_eigenvalues[1] + 1.0) <= sector_tolerance
        and abs(sector_eigenvalues[2] + 2.0) <= sector_tolerance
    )
    return _task13_oracle_measure(
        residual, sector_invariant
    )


def oracle_honeycomb_ising_critical_polynomial_oracle(
    payload, numerical_controls
):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    honeycomb_coupling = 1.0 / float(fields["tc_over_j"])
    triangular_dual = 0.5 * math.asinh(
        1.0 / math.sinh(2.0 * honeycomb_coupling)
    )
    transformed = math.exp(4.0 * triangular_dual)
    residual = abs(transformed - 3.0) / (3.0 + transformed)
    return _task13_oracle_measure(
        residual,
        honeycomb_coupling > triangular_dual > 0.0,
    )


def oracle_kagome_ising_critical_polynomial_oracle(
    payload, numerical_controls
):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exponential_variable = math.exp(4.0 / float(fields["tc_over_j"]))
    polynomial = (
        exponential_variable * exponential_variable
        - 6.0 * exponential_variable
        - 3.0
    )
    residual = abs(polynomial) / (
        4.0
        + exponential_variable * exponential_variable
        + 6.0 * exponential_variable
    )
    return _task13_oracle_measure(residual, exponential_variable > 1.0)


def oracle_ising_chain_partition_analytic_oracle(
    payload, numerical_controls
):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    coupling = float(inputs["exchange"]) * float(
        inputs["inverse_temperature"]
    )
    partition_values = []
    for site_count in (2, 4, 6):
        partition = 0.0
        for state in range(1 << site_count):
            bond_sum = 0
            for site in range(site_count):
                first = 1 if ((state >> site) & 1) else -1
                next_site = (site + 1) % site_count
                second = 1 if ((state >> next_site) & 1) else -1
                bond_sum += first * second
            partition += math.exp(coupling * bond_sum)
        partition_values.append(partition)
    sum_squared_roots = partition_values[0]
    product_squared_roots = (
        sum_squared_roots * sum_squared_roots - partition_values[1]
    ) / 2.0
    discriminant = (
        sum_squared_roots * sum_squared_roots
        - 4.0 * product_squared_roots
    )
    leading_squared = 0.5 * (
        sum_squared_roots + math.sqrt(discriminant)
    )
    subleading_squared = 0.5 * (
        sum_squared_roots - math.sqrt(discriminant)
    )
    reconstructed_size_six = (
        leading_squared**3 + subleading_squared**3
    )
    invariant = (
        leading_squared > subleading_squared >= 0.0
        and abs(reconstructed_size_six - partition_values[2])
        <= 1e-11 * max(1.0, partition_values[2])
        and fields["finite_temperature_transition"] is False
        and fields["tc_over_j"] == 0.0
    )
    return _task13_oracle_measure(fields["tc_over_j"], invariant)


def oracle_triangular_ising_critical_polynomial_oracle(
    payload, numerical_controls
):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    triangular_coupling = 1.0 / float(fields["tc_over_j"])
    honeycomb_dual = 0.5 * math.asinh(
        1.0 / math.sinh(2.0 * triangular_coupling)
    )
    dual_residual = math.sinh(2.0 * honeycomb_dual) - math.sqrt(3.0)
    return _task13_oracle_measure(
        abs(dual_residual) / (1.0 + math.sqrt(3.0)),
        honeycomb_dual > triangular_coupling > 0.0,
    )


def oracle_spin_ice_tetrahedron_matrix_oracle(
    payload, numerical_controls
):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["exchange"])
    sector_basis = {}
    for up_count, energy_name in (
        (2, "two_in_two_out_energy"),
        (3, "three_in_one_out_energy"),
        (4, "all_in_all_out_energy"),
    ):
        charge = 2 * up_count - 4
        sector_basis[energy_name] = 0.5 * exchange * (
            charge * charge - 4
        )
    sector_basis["two_in_two_out_degeneracy"] = math.comb(4, 2)
    residual = 0.0
    for name in sector_basis:
        difference = abs(
            float(fields[name]) - float(sector_basis[name])
        )
        residual = max(residual, difference)
    return _task13_oracle_measure(residual)


def oracle_toric_code_logical_loop_oracle(payload, numerical_controls):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    width = 3
    z_loops = (0, 0)
    x_loops = (0, 0)
    for coordinate in range(width):
        z_loops = (
            z_loops[0] | (1 << (2 * coordinate)),
            z_loops[1] | (1 << (2 * coordinate * width + 1)),
        )
        x_loops = (
            x_loops[0] | (1 << (2 * coordinate * width)),
            x_loops[1] | (1 << (2 * coordinate + 1)),
        )
    commutators = []
    for z_loop in z_loops:
        row = []
        for x_loop in x_loops:
            overlap_bits = z_loop & x_loop
            overlap = 0
            while overlap_bits:
                overlap += overlap_bits & 1
                overlap_bits >>= 1
            row.append(overlap % 2)
        commutators.append(row)
    logical_loop_pairs = 0
    for index in range(2):
        if commutators[index][index] == 1:
            logical_loop_pairs += 1
    independent_degeneracy = 2**logical_loop_pairs
    return _task13_oracle_measure(
        fields["torus_ground_state_degeneracy"] - independent_degeneracy,
        commutators == [[1, 0], [0, 1]],
    )


def oracle_blume_capel_configuration_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["exchange"])
    ordered_bond_energy = -2.0 * exchange
    zero_state_energy = 0.0
    crossing = (zero_state_energy - ordered_bond_energy) / exchange
    return _task13_oracle_measure(
        fields["square_lattice_d_over_j_crossing"] - crossing
    )


def oracle_checkerboard_total_spin_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["exchange"])
    zero_sum_configuration = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
    )
    total = []
    for axis in range(3):
        component = 0.0
        for spin in zero_sum_configuration:
            component += spin[axis]
        total.append(component)
    norm_squared = 0.0
    for component in total:
        norm_squared += component * component
    spin_norm_sum = 4.0
    identity_energy = 0.5 * exchange * (
        norm_squared - spin_norm_sum
    )
    lower_bound = -0.5 * exchange * spin_norm_sum
    derived_zero_minimum = (
        abs(identity_energy - lower_bound) <= 1e-14
        and norm_squared == 0.0
    )
    return _task13_oracle_measure(
        identity_energy - lower_bound,
        derived_zero_minimum
        and fields["zero_total_spin_per_crossed_plaquette"] is True,
    )


def oracle_spin_ladder_analytic_rung_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["rung_exchange"])
    singlet = 0.5 * (0.0 - 2.0 * 0.5 * 1.5) * exchange
    triplet = 0.5 * (2.0 - 2.0 * 0.5 * 1.5) * exchange
    residual = max(
        abs(fields["energy_per_rung"] - singlet),
        abs(fields["gap_to_triplet"] - (triplet - singlet)),
    )
    return _task13_oracle_measure(residual)


def _task14_oracle_matrix_multiply(first, second):
    rows = len(first)
    inner = len(second)
    columns = len(second[0])
    product = []
    for row in range(rows):
        product_row = []
        for column in range(columns):
            value = 0.0j
            for index in range(inner):
                value += first[row][index] * second[index][column]
            product_row.append(value)
        product.append(product_row)
    return product


def _task14_oracle_commutator_norm(first, second):
    forward = _task14_oracle_matrix_multiply(first, second)
    backward = _task14_oracle_matrix_multiply(second, first)
    norm_squared = 0.0
    for row in range(len(first)):
        for column in range(len(first)):
            norm_squared += abs(forward[row][column] - backward[row][column]) ** 2
    return math.sqrt(norm_squared)


def _task14_oracle_kron(first, second):
    tensor = []
    for first_row in first:
        for second_row in second:
            row = []
            for first_value in first_row:
                for second_value in second_row:
                    row.append(first_value * second_value)
            tensor.append(row)
    return tensor


def _task14_oracle_su3_generators():
    zero = 0.0j
    one = 1.0 + 0.0j
    imaginary = 1.0j
    root_three = math.sqrt(3.0)
    return (
        ((zero, one, zero), (one, zero, zero), (zero, zero, zero)),
        ((zero, -imaginary, zero), (imaginary, zero, zero), (zero, zero, zero)),
        ((one, zero, zero), (zero, -one, zero), (zero, zero, zero)),
        ((zero, zero, one), (zero, zero, zero), (one, zero, zero)),
        ((zero, zero, -imaginary), (zero, zero, zero), (imaginary, zero, zero)),
        ((zero, zero, zero), (zero, zero, one), (zero, one, zero)),
        ((zero, zero, zero), (zero, zero, -imaginary), (zero, imaginary, zero)),
        (
            (one / root_three, zero, zero),
            (zero, one / root_three, zero),
            (zero, zero, -2.0 / root_three),
        ),
    )


def oracle_uls_permutation_commutator_oracle(payload, numerical_controls):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    sector_dot_values = (-2.0, -1.0, 1.0)
    permutation_values = (1.0, -1.0, 1.0)
    residual = 0.0
    for dot, permutation in zip(sector_dot_values, permutation_values):
        residual = max(residual, abs(dot + dot * dot - 1.0 - permutation))
    identity = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    exchange_operator = []
    for row in range(9):
        exchange_row = []
        first_row = row // 3
        second_row = row % 3
        for column in range(9):
            first_column = column // 3
            second_column = column % 3
            exchange_row.append(
                1.0
                if first_row == second_column
                and second_row == first_column
                else 0.0
            )
        exchange_operator.append(exchange_row)
    for generator in _task14_oracle_su3_generators():
        left = _task14_oracle_kron(generator, identity)
        right = _task14_oracle_kron(identity, generator)
        total = []
        for row in range(9):
            total_row = []
            for column in range(9):
                total_row.append(left[row][column] + right[row][column])
            total.append(total_row)
        residual = max(
            residual,
            _task14_oracle_commutator_norm(exchange_operator, total),
        )
    residual = max(
        residual, abs(fields["theta_radians"] - math.atan2(1.0, 1.0))
    )
    return _task13_oracle_measure(
        residual, residual <= 1e-12 and fields["su3_symmetric"] is True
    )


def _task14_compass_bond_line_parity_checks():
    satisfied = 0
    total = 0
    shapes = ((2, 2), (2, 3))
    for rows, columns in shapes:
        bonds = []
        for row in range(rows):
            for column in range(columns - 1):
                first = row * columns + column
                bonds.append(("x", (first, first + 1)))
        for row in range(rows - 1):
            for column in range(columns):
                first = row * columns + column
                bonds.append(("y", (first, first + columns)))
        lines = []
        for column in range(columns):
            support = []
            for row in range(rows):
                support.append(row * columns + column)
            lines.append(("x", tuple(support)))
        for row in range(rows):
            support = []
            for column in range(columns):
                support.append(row * columns + column)
            lines.append(("y", tuple(support)))
        for bond_axis, bond_support in bonds:
            for line_axis, line_support in lines:
                anticommuting_sites = 0
                if bond_axis != line_axis:
                    for site in bond_support:
                        if site in line_support:
                            anticommuting_sites += 1
                total += 1
                if anticommuting_sites % 2 == 0:
                    satisfied += 1
    return satisfied, total


def oracle_compass_spin_flip_oracle(payload, numerical_controls):
    _inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    parity_checks, required_checks = (
        _task14_compass_bond_line_parity_checks()
    )
    invariant = parity_checks == required_checks
    return _task13_oracle_measure(
        float(required_checks - parity_checks),
        invariant and fields["has_line_flip_symmetries"] is True,
    )


def oracle_aklt_clebsch_gordan_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    scale = float(inputs["projector_scale"])
    sector_values = []
    multiplicities = []
    for total_spin in (0, 1, 2):
        sector_values.append(0.0 if total_spin < 2 else 1.0)
        multiplicities.append(2 * total_spin + 1)
    residual = 0.0
    for index in range(3):
        residual = max(
            residual,
            abs(
                fields["two_site_projector_eigenvalues"][index]
                - sector_values[index]
            ),
        )
    root_two = math.sqrt(2.0)
    root_three = math.sqrt(3.0)
    root_six = math.sqrt(6.0)
    spin_two_vectors = (
        ((0, 1.0),),
        ((1, 1.0 / root_two), (3, 1.0 / root_two)),
        (
            (2, 1.0 / root_six),
            (4, 2.0 / root_six),
            (6, 1.0 / root_six),
        ),
        ((5, 1.0 / root_two), (7, 1.0 / root_two)),
        ((8, 1.0),),
    )
    vbs = [0.0] * 9
    vbs[2] = 1.0 / root_three
    vbs[4] = -1.0 / root_three
    vbs[6] = 1.0 / root_three
    projected_norm_squared = 0.0
    projector_trace = 0.0
    for vector in spin_two_vectors:
        overlap = 0.0
        vector_norm = 0.0
        for index, coefficient in vector:
            overlap += coefficient * vbs[index]
            vector_norm += coefficient * coefficient
        projected_norm_squared += overlap * overlap
        projector_trace += vector_norm
    residual = max(
        residual,
        abs(fields["vbs_ground_energy"] / scale),
        math.sqrt(projected_norm_squared),
        abs(projector_trace - 5.0),
    )
    return _task13_oracle_measure(
        residual, multiplicities == [1, 3, 5]
    )


def _task14_oracle_dimer_coverings(site_count):
    local_singlet = (0.0, 1.0 / math.sqrt(2.0), -1.0 / math.sqrt(2.0), 0.0)
    adjacent = [1.0]
    for dimer in range(site_count // 2):
        enlarged = [0.0] * (4 * len(adjacent))
        for lower_state, lower_amplitude in enumerate(adjacent):
            for local_state, local_amplitude in enumerate(local_singlet):
                combined_state = lower_state | (local_state << (2 * dimer))
                enlarged[combined_state] = lower_amplitude * local_amplitude
        adjacent = enlarged
    translated = [0.0] * len(adjacent)
    for state, amplitude in enumerate(adjacent):
        rotated = 0
        for site in range(site_count):
            if (state >> site) & 1:
                rotated |= 1 << ((site + 1) % site_count)
        translated[rotated] = amplitude
    return adjacent, translated


def _task14_oracle_pair_action(vector, first, second):
    acted = [0.0] * len(vector)
    for state, amplitude in enumerate(vector):
        first_bit = (state >> first) & 1
        second_bit = (state >> second) & 1
        acted[state] += amplitude * (
            0.25 if first_bit == second_bit else -0.25
        )
        if first_bit != second_bit:
            flipped = state ^ (1 << first) ^ (1 << second)
            acted[flipped] += 0.5 * amplitude
    return acted


def _task14_oracle_projector_residual(vector, sites):
    first = _task14_oracle_pair_action(vector, sites[0], sites[1])
    second = _task14_oracle_pair_action(vector, sites[1], sites[2])
    third = _task14_oracle_pair_action(vector, sites[0], sites[2])
    norm_squared = 0.0
    for index, amplitude in enumerate(vector):
        projected = 0.5 * amplitude + (2.0 / 3.0) * (
            first[index] + second[index] + third[index]
        )
        norm_squared += projected * projected
    return math.sqrt(norm_squared)


def oracle_majumdar_ghosh_projector_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    exchange = float(inputs["nearest_exchange"])
    maximum_projector_residual = 0.0
    minimum_gram_determinant = 1.0
    for site_count in (8, 10):
        coverings = (
            _task14_oracle_dimer_coverings(site_count)
        )
        overlap = 0.0
        for index in range(1 << site_count):
            overlap += coverings[0][index] * coverings[1][index]
        minimum_gram_determinant = min(
            minimum_gram_determinant, 1.0 - overlap * overlap
        )
        for covering in coverings:
            for site in range(site_count):
                residual = _task14_oracle_projector_residual(
                    covering,
                    (
                        site,
                        (site + 1) % site_count,
                        (site + 2) % site_count,
                    ),
                )
                maximum_projector_residual = max(
                    maximum_projector_residual, residual
                )
    energy_per_site = -3.0 * exchange / 8.0
    energy_residual = abs(
        fields["energy_per_site"] - energy_per_site
    ) / max(abs(exchange), 1e-300)
    residual = max(
        energy_residual,
        abs(fields["degenerate_dimer_coverings"] - 2),
        maximum_projector_residual,
    )
    return _task13_oracle_measure(
        residual, minimum_gram_determinant > 1e-12
    )


def oracle_shastry_sutherland_bond_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    intradimer = float(inputs["intradimer_exchange"])
    maximum_cancellation_residual = 0.0
    derived_energy_per_dimer = 0.0
    for dimer_count in (2, 4):
        site_count = 2 * dimer_count
        covering = _task14_oracle_dimer_coverings(site_count)[0]
        intradimer_expectation = 0.0
        for dimer in range(dimer_count):
            acted = _task14_oracle_pair_action(
                covering, 2 * dimer, 2 * dimer + 1
            )
            for index, amplitude in enumerate(covering):
                intradimer_expectation += amplitude * acted[index]
        derived_energy_per_dimer = (
            intradimer * intradimer_expectation / dimer_count
        )
        linked_cells = (
            ((0, 1, 2),)
            if dimer_count == 2
            else ((0, 1, 2), (2, 3, 5), (4, 5, 6))
        )
        for first_site, second_site, shared_site in linked_cells:
            first = _task14_oracle_pair_action(
                covering, first_site, shared_site
            )
            second = _task14_oracle_pair_action(
                covering, second_site, shared_site
            )
            norm_squared = 0.0
            for index in range(len(covering)):
                combined = first[index] + second[index]
                norm_squared += combined * combined
            maximum_cancellation_residual = max(
                maximum_cancellation_residual, math.sqrt(norm_squared)
            )
    residual = max(
        abs(fields["energy_per_dimer"] - derived_energy_per_dimer),
        abs(fields["energy_per_spin"] - 0.5 * derived_energy_per_dimer),
        maximum_cancellation_residual,
    )
    return _task13_oracle_measure(residual)


def oracle_spin1_m_quantum_number_oracle(payload, numerical_controls):
    inputs, fields = _task13_oracle_unpack(payload, numerical_controls)
    anisotropy = float(inputs["single_ion_anisotropy"])
    levels = []
    for magnetic in (-1, 0, 1):
        levels.append(anisotropy * magnetic * magnetic)
    levels.sort()
    grouped = []
    degeneracies = []
    for level in levels:
        if not grouped or level != grouped[-1]:
            grouped.append(level)
            degeneracies.append(1)
        else:
            degeneracies[-1] += 1
    residual = 0.0
    for index in range(3):
        residual = max(
            residual, abs(fields["levels"][index] - levels[index])
        )
    invariant = fields["degeneracies"] == degeneracies
    return _task13_oracle_measure(residual, invariant)
